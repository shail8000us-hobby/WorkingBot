"""
MMM Pure Straddle Roll — ATM straddle with roll-only risk management

This module handles the heartbeat logic for STRADDLE_ROLL sessions.
Unlike STRADDLE_WITH_ADJUSTMENT, the MMM adjustment engine is NEVER
called between rolls (enforced by min_trigger_move=9999 in the preset).

Each heartbeat does exactly three things in order:
  1. Hard stop check — if total loss ≥ max_loss_amount → market order close all, STOP
  2. Expiry guard — if < 10 min left → close all (limit), STOP
                    if < 90 min left → hold, skip roll
  3. Roll trigger — if spot moved ≥ (CE premium + PE premium) points → roll

Nothing else. CE:PE ratio is always 1:1. No adjustments. No wind-down.
No harvest. Hard stop uses market orders (taker) for guaranteed fill.

Two public functions:
  - execute_pure_straddle_roll(): async entry point from mmm_monitor.py Step 5.4
  - cleanup_pure_roll_lock(): called on session stop (mmm_exit_all.py, mmm_guardian.py)

Reference: tasks/STRADDLE_ROLL_PURE_IMPL.md

Created: 2026-04-10
"""

import logging
import threading
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Tuple, Any

from .mmm_constants import LOT_SIZE_BTC
from .mmm_pnl_core import compute_current_total_pnl as _pnl_total
from .mmm_dte_presets import STRADDLE_ROLL_CATEGORY
from .mmm_state import derive_strategy_type
from .mmm_close_at_5 import close_position
from .mmm_engine import get_engine
from .mmm_margin_guardian import TIER_RED, TIER_CRITICAL
from .mmm_activity import log_activity
from webui.backend.sealed import sealed

log = logging.getLogger('mmm_straddle_roll_pure')

# ── Decimal precision (same convention as mmm_straddle_adjustment.py) ──────────

def _D(x) -> Decimal:
    """Convert float/int to Decimal via string to avoid IEEE 754 rounding errors."""
    if isinstance(x, Decimal):
        return x
    try:
        return Decimal(str(x))
    except Exception:
        return Decimal('0')


_LOT_DECIMAL = _D(LOT_SIZE_BTC)

# ══════════════════════════════════════════════════════════════════════════════
# § Dynamic Trigger Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _compute_dynamic_trigger(monitor, session: dict, sid: str) -> float:
    """
    Compute the dynamic roll trigger from the FRESH ATM straddle price at the
    current spot, and update session['_straddle_dynamic_trigger_pts'].

    Uses preview_atm_straddle() (synchronous, chain cache — no REST call per beat)
    to get CE_mid + PE_mid at the current ATM strike (closest to current spot).
    This value naturally shrinks as theta decays and does NOT inflate from the
    intrinsic value of the existing ITM/OTM position legs.

    WHY fresh ATM, not existing position prices:
    For a short straddle with existing legs at strike K and spot at S:
        existing_CE_mid + existing_PE_mid  ≈  |S - K| + time_value  ≥  |S - K|
    This means |spot - K| < existing_CE + existing_PE always (time_value > 0),
    so the roll condition spot_move ≥ trigger can NEVER be satisfied.
    Fresh ATM premiums (at current spot's ATM strike) do not carry intrinsic
    value relative to the current spot, so the condition CAN be satisfied.

    Returns the updated dynamic trigger pts, or 0.0 if unavailable
    (caller falls back to fixed trigger in that case).
    """
    params = session.get('params', {})
    if not params.get('straddle_dynamic_trigger_enabled', True):
        return 0.0

    expiry = params.get('expiry', '')
    if not expiry:
        return 0.0

    try:
        preview = monitor.initializer.preview_atm_straddle(expiry)
    except Exception as e:
        log.debug(f"[{sid}] [STRADDLE_ROLL] Dynamic trigger: preview_atm_straddle failed: {e}")
        return 0.0

    if not preview or not preview.get('success'):
        log.debug(
            f"[{sid}] [STRADDLE_ROLL] Dynamic trigger: ATM preview unavailable "
            f"({preview.get('error', '?') if preview else 'None'}) — keeping prior value"
        )
        return 0.0

    ce_mid = preview.get('ce', {}).get('mid_price', 0)
    pe_mid = preview.get('pe', {}).get('mid_price', 0)
    atm_strike = preview.get('atm_strike', 0)

    if not (ce_mid > 0 and pe_mid > 0):
        log.debug(
            f"[{sid}] [STRADDLE_ROLL] Dynamic trigger: invalid ATM prices "
            f"(CE_mid={ce_mid}, PE_mid={pe_mid}) — keeping prior value"
        )
        return 0.0

    raw_pts = ce_mid + pe_mid
    min_floor = float(params.get('straddle_min_trigger_pts', 200))
    effective_pts = max(raw_pts, min_floor)

    old_pts = session.get('_straddle_dynamic_trigger_pts', 0)
    session['_straddle_dynamic_trigger_pts'] = round(effective_pts, 2)

    if abs(effective_pts - old_pts) > 5:  # only log on meaningful change
        floor_note = f' [floor={min_floor:.0f}]' if effective_pts == min_floor else ''
        log.info(
            f"[{sid}] [STRADDLE_ROLL] Dynamic trigger: "
            f"{old_pts:.0f} → {effective_pts:.0f}pts "
            f"(fresh ATM={atm_strike:.0f}: CE_mid={ce_mid:.2f} + PE_mid={pe_mid:.2f}{floor_note})"
        )

    return effective_pts


def _get_effective_trigger_pts(session: dict, params: dict) -> float:
    """
    Return the effective roll trigger distance in points.

    Dynamic mode (straddle_dynamic_trigger_enabled=True, default):
        Use _straddle_dynamic_trigger_pts (current straddle mark, updated each heartbeat).
        Floored at straddle_min_trigger_pts (default 200 pts).

    Fixed mode (straddle_dynamic_trigger_enabled=False):
        Use _straddle_roll_trigger_pts (entry premium at last roll — original behaviour).

    Falls back to the fixed trigger if the dynamic value is not yet populated.
    """
    if params.get('straddle_dynamic_trigger_enabled', True):
        dynamic_pts = session.get('_straddle_dynamic_trigger_pts', 0)
        if dynamic_pts > 0:
            return float(dynamic_pts)
        # Dynamic not yet computed (first heartbeat); fall through to fixed
    return float(session.get('_straddle_roll_trigger_pts', 0))


# ── Half-roll breadcrumb states ─────────────────────────────────────────────────
HALF_ROLL_NONE                  = None
HALF_ROLL_CE_CLOSED_PE_OPEN     = 'ce_closed_pe_open'
HALF_ROLL_PE_CLOSED_CE_OPEN     = 'pe_closed_ce_open'
HALF_ROLL_BOTH_CLOSED_NO_REENTRY = 'both_closed_no_reentry'
HALF_ROLL_CE_ENTERED_PE_PENDING = 'ce_entered_pe_pending'

# ── Session-level roll lock (prevents concurrent roll attempts) ─────────────────

_pure_roll_locks: Dict[str, threading.Lock] = {}
_pure_roll_locks_lock = threading.Lock()


def _get_pure_roll_lock(session_id: str) -> threading.Lock:
    with _pure_roll_locks_lock:
        if session_id not in _pure_roll_locks:
            _pure_roll_locks[session_id] = threading.Lock()
        return _pure_roll_locks[session_id]


def cleanup_pure_roll_lock(session_id: str):
    """Remove lock when session ends. Called from mmm_exit_all.py and mmm_guardian.py."""
    with _pure_roll_locks_lock:
        _pure_roll_locks.pop(session_id, None)


# ══════════════════════════════════════════════════════════════════════════════
# § Hard Stop: close all positions with MARKET ORDERS
# ══════════════════════════════════════════════════════════════════════════════

async def _close_all_market_order(monitor, session: dict, sid: str) -> int:
    """
    Close all active CE and PE positions using market orders.
    Used ONLY for hard stop. Never use for normal roll execution.

    Continues closing remaining positions even if one fails (partial close
    is better than no close). Returns count of successfully closed positions.
    """
    executor = monitor.executor
    initializer = monitor.initializer
    closed = 0
    failed = 0

    for side_key in ('ce', 'pe'):
        side_state = session.get(side_key, {})
        active_positions = [
            p for p in side_state.get('positions', [])
            if p.get('status') == 'active' and p.get('lots', 0) > 0
        ]
        for pos in active_positions:
            try:
                result = await close_position(
                    executor, initializer, session, pos,
                    pnl_attribution_key='hard_stop',
                    hedge_guard=False,
                    mechanism='emergency',
                    side=side_key,
                    order_type='market',
                )
                if result.get('success'):
                    closed += 1
                    log.warning(
                        f"[{sid}] Hard stop: closed {side_key.upper()} "
                        f"{pos.get('lots')} lots @ {pos.get('strike')} — market order"
                    )
                else:
                    failed += 1
                    log.critical(
                        f"[{sid}] Hard stop: FAILED to close {side_key.upper()} "
                        f"{pos.get('lots')} lots @ {pos.get('strike')}: "
                        f"{result.get('error', '?')}"
                    )
            except Exception as e:
                failed += 1
                log.critical(
                    f"[{sid}] Hard stop: exception closing {side_key.upper()} "
                    f"{pos.get('lots')} lots @ {pos.get('strike')}: {e}",
                    exc_info=True,
                )

    if failed > 0:
        log.critical(
            f"[{sid}] Hard stop completed with {failed} FAILED close(s). "
            f"Check exchange for open positions. Closed: {closed}."
        )
    return closed


# ══════════════════════════════════════════════════════════════════════════════
# § Roll Gate Check
# ══════════════════════════════════════════════════════════════════════════════

@sealed
def _check_pure_roll_gates(
    monitor,
    session: dict,
    sid: str,
    spot: float,
    minutes_to_expiry: float,
) -> Tuple[bool, str, dict]:
    """
    Gates for STRADDLE_ROLL pure roll. Returns (can_roll, reason, context).

    Gates:
      0  — In-progress lock
      1  — Master switch (straddle_roll_enabled)
      1.5 — Strategy status (RUNNING or ACTIVE)
      2  — Correct preset (STRADDLE_ROLL only)
      2.5 — Both legs have active positions
      3  — Time to expiry ≥ straddle_roll_min_time_to_expiry
      4  — Margin tier not RED or CRITICAL
      5  — IV spike: SOFT WARNING ONLY — does not block roll
      6  — Max rolls not exhausted
      7  — Cooldown elapsed (with emergency bypass at 2× trigger_pts)
      8  — Distance trigger (spot_move ≥ trigger_pts in points)
      10 — Loss abort (total_loss < original_credit × loss_abort_mult)

    CRITICAL: All failure returns MUST be 3-tuples (False, str, {}).
    """
    params = session.get('params', {})
    roll_count = session.get('_straddle_roll_count', 0)
    straddle_roll_enabled           = params.get('straddle_roll_enabled', False)
    straddle_roll_max_per_session   = params.get('straddle_roll_max_per_session', 0)
    straddle_roll_cooldown_mins     = params.get('straddle_roll_cooldown_mins', 15)
    straddle_roll_emergency_mult    = params.get('straddle_roll_emergency_mult', 2.0)
    straddle_roll_min_time_to_expiry = params.get('straddle_roll_min_time_to_expiry', 90)
    straddle_roll_iv_spike_mult     = params.get('straddle_roll_iv_spike_mult', 2.0)
    straddle_roll_trigger_pct       = params.get('straddle_roll_trigger_pct', 1.0)
    straddle_roll_loss_abort_mult   = params.get('straddle_roll_loss_abort_mult', 3.0)

    # ── Gate 0 — Not already rolling ─────────────────────────────────────────
    if session.get('_straddle_roll_in_progress'):
        return False, 'roll_already_in_progress', {}

    # ── Gate 1 — Master switch ────────────────────────────────────────────────
    if not straddle_roll_enabled:
        return False, 'disabled', {}

    # ── Gate 1.5 — Strategy status ────────────────────────────────────────────
    status = session.get('strategy_status')
    if status not in (None, 'RUNNING', 'ACTIVE'):
        return False, 'session_not_running', {}

    # ── Gate 2 — Correct strategy identity ───────────────────────────────────
    strategy_type = session.get('strategy_type') or derive_strategy_type(params)
    if strategy_type != STRADDLE_ROLL_CATEGORY:
        return False, 'wrong_preset', {}

    # ── Gate 2.5 — Both legs have active positions ────────────────────────────
    ce_positions = [p for p in session.get('ce', {}).get('positions', [])
                    if p.get('status') == 'active' and p.get('lots', 0) > 0]
    pe_positions = [p for p in session.get('pe', {}).get('positions', [])
                    if p.get('status') == 'active' and p.get('lots', 0) > 0]
    if not ce_positions or not pe_positions:
        return False, 'leg_asymmetry', {}

    # ── Gate 3 — Time to expiry (double-check — Step 2 already filtered) ──────
    if minutes_to_expiry < straddle_roll_min_time_to_expiry:
        return False, 'insufficient_time', {}

    # ── Gate 4 — Margin safety ────────────────────────────────────────────────
    mg = getattr(monitor, '_margin_guardian', None)
    if mg is None or mg.last_tier in (TIER_RED, TIER_CRITICAL):
        return False, 'margin_safety_blocked', {}

    # ── Gate 5 — IV spike check (SOFT WARNING — does NOT block roll) ──────────
    # High IV when BTC is moving = higher premium on new straddle.
    # Blocking the roll here is counterproductive. Margin gate (Gate 4) is
    # the real protection against dangerous market conditions.
    monitor_iv_data = getattr(monitor, '_last_iv_data', None) or {}
    if not session.get('_straddle_entry_iv') and monitor_iv_data:
        ce_iv = monitor_iv_data.get('ce_iv', 0)
        pe_iv = monitor_iv_data.get('pe_iv', 0)
        if ce_iv > 0 or pe_iv > 0:
            session['_straddle_entry_iv'] = (
                (ce_iv + pe_iv) / 2 if (ce_iv and pe_iv) else max(ce_iv, pe_iv)
            )
    entry_iv = session.get('_straddle_entry_iv', 0)
    ce_iv = monitor_iv_data.get('ce_iv', 0)
    pe_iv = monitor_iv_data.get('pe_iv', 0)
    current_iv = (ce_iv + pe_iv) / 2 if (ce_iv and pe_iv) else max(ce_iv, pe_iv)
    if entry_iv > 0 and current_iv > entry_iv * straddle_roll_iv_spike_mult:
        log.warning(
            f"[{sid}] [STRADDLE_ROLL] IV spike noted (current={current_iv:.1f} > "
            f"{entry_iv:.1f} × {straddle_roll_iv_spike_mult}) — proceeding with roll. "
            f"High IV = higher new premium. Margin gate is the real protection."
        )
        session['_straddle_last_roll_iv_spike'] = True  # audit trail — does NOT block

    # ── Gate 6 — Max rolls not exhausted ─────────────────────────────────────
    # Special case: straddle_roll_max_per_session == 0 means no-roll mode (hard stop only).
    if straddle_roll_max_per_session == 0:
        return False, 'no_roll_mode', {}
    if roll_count < straddle_roll_max_per_session:
        session['_straddle_roll_blocked'] = False
        session['_straddle_roll_block_logged'] = False
    else:
        session['_straddle_roll_blocked'] = True
        if not session.get('_straddle_roll_block_logged'):
            log.warning(
                f"[{sid}] [STRADDLE_ROLL] Max rolls exhausted "
                f"({roll_count}/{straddle_roll_max_per_session})"
            )
            log_activity(
                'straddle_roll_blocked',
                f"⛔ All {straddle_roll_max_per_session} rolls exhausted. "
                f"Hard stop (${params.get('max_loss_amount', '?')}) is now only exit.",
                sid, 'error',
            )
            # Fire Telegram exhaustion alert — exactly once
            try:
                from .mmm_telegram import send_telegram_message
                _atm = session.get('ce', {}).get('active_strike', 0)
                _msg = (
                    f"⚠️ *STRADDLE\\_ROLL — MAX ROLLS EXHAUSTED*\n\n"
                    f"Session: `{sid}`\n"
                    f"Rolls used: *{roll_count}/{straddle_roll_max_per_session}*\n"
                    f"Current ATM: *{_atm:.0f}*\n"
                    f"Hard stop: *${params.get('max_loss_amount', '?'):.2f}*\n\n"
                    f"No more rolls this session. "
                    f"Only exits: hard stop or expiry close."
                )
                import asyncio
                asyncio.create_task(send_telegram_message(_msg))
            except Exception:
                pass  # fire-and-forget
            session['_straddle_roll_block_logged'] = True
        return False, 'max_rolls_exhausted', {}

    # ── Gate 7 — Cooldown elapsed (with emergency bypass) ────────────────────
    last_roll_at = session.get('_straddle_last_roll_at')
    if last_roll_at is None:
        elapsed_secs = float('inf')
    else:
        try:
            last_dt = datetime.fromisoformat(last_roll_at)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            elapsed_secs = (datetime.now(timezone.utc) - last_dt).total_seconds()
        except (ValueError, TypeError):
            elapsed_secs = float('inf')

    normal_cooldown = elapsed_secs >= straddle_roll_cooldown_mins * 60
    _g7_atm = session.get('ce', {}).get('active_strike', 0)
    _g7_spot_move = abs(spot - _g7_atm) if _g7_atm > 0 else 0
    # Gate 7 uses the effective trigger (dynamic or fixed) for emergency bypass
    _g7_trigger = _get_effective_trigger_pts(session, params) or (
        straddle_roll_trigger_pct / 100.0 * spot if spot > 0 else 0
    )
    emergency_bypass = (
        _g7_trigger > 0 and
        _g7_spot_move >= _g7_trigger * straddle_roll_emergency_mult
    )
    if not (normal_cooldown or emergency_bypass):
        return False, 'cooldown_not_elapsed', {}

    # ── Gate 8 — Distance trigger ─────────────────────────────────────────────
    # Dynamic mode (default): trigger = current straddle mark (CE mid + PE mid),
    #   floored at straddle_min_trigger_pts.  Shrinks with theta decay.
    # Fixed mode: trigger = entry premium collected at last roll.
    current_atm_strike = session.get('ce', {}).get('active_strike', 0)
    if not current_atm_strike or current_atm_strike <= 0:
        return False, 'invalid_atm_strike', {}

    spot_move_pts = abs(spot - current_atm_strike)

    trigger_pts = _get_effective_trigger_pts(session, params)
    if trigger_pts <= 0:
        # Dynamic value not yet populated or dynamic disabled: fall back to fixed trigger.
        # Heal from entry_premium on positions if _straddle_roll_trigger_pts is also missing.
        fixed_pts = session.get('_straddle_roll_trigger_pts', 0)
        if fixed_pts <= 0:
            _ce_lots = sum(p.get('lots', 0) for p in ce_positions)
            _pe_lots = sum(p.get('lots', 0) for p in pe_positions)
            _ce_avg = (
                sum(float(p.get('entry_premium', 0)) * p.get('lots', 0) for p in ce_positions) / _ce_lots
            ) if _ce_lots > 0 else 0
            _pe_avg = (
                sum(float(p.get('entry_premium', 0)) * p.get('lots', 0) for p in pe_positions) / _pe_lots
            ) if _pe_lots > 0 else 0
            fixed_pts = _ce_avg + _pe_avg
            if fixed_pts > 0:
                session['_straddle_roll_trigger_pts'] = round(fixed_pts, 2)
                log.info(f"[{sid}] [STRADDLE_ROLL] Gate 8 fallback: healed trigger_pts={fixed_pts:.2f}pts from positions")
        if fixed_pts > 0:
            trigger_pts = fixed_pts
        else:
            # Last resort: pct-based floor
            pct_fallback = straddle_roll_trigger_pct / 100.0 * spot if spot > 0 else 0
            if pct_fallback > 0:
                trigger_pts = pct_fallback
                log.warning(
                    f"[{sid}] [STRADDLE_ROLL] Gate 8 pct-fallback: trigger_pts={trigger_pts:.2f}pts "
                    f"(no entry_premium on positions — check position state)"
                )
            else:
                return False, 'no_trigger_pts', {}

    dynamic_label = (
        'dynamic' if params.get('straddle_dynamic_trigger_enabled', True)
        and session.get('_straddle_dynamic_trigger_pts', 0) > 0
        else 'fixed'
    )
    if spot_move_pts < trigger_pts:
        return False, (
            f'distance_below_trigger ({spot_move_pts:.0f} < {trigger_pts:.0f} pts [{dynamic_label}])'
        ), {}

    # ── Gate 10 — Loss abort ──────────────────────────────────────────────────
    total_pnl_dec  = _D(_pnl_total(session))
    total_loss_dec = abs(min(total_pnl_dec, _D(0)))
    original_credit_dec = _D(session.get('_straddle_initial_credit', 0))
    if original_credit_dec <= 0:
        return False, 'no_initial_credit', {}
    loss_threshold_dec = _D(straddle_roll_loss_abort_mult) * original_credit_dec
    if total_loss_dec > loss_threshold_dec:
        return False, 'loss_abort', {}

    # ── All gates passed ──────────────────────────────────────────────────────
    return True, '', {
        'roll_count': roll_count,
        'ce_positions': ce_positions,
        'pe_positions': pe_positions,
        'trigger_pts': trigger_pts,
        'spot_move_pts': spot_move_pts,
    }


# ══════════════════════════════════════════════════════════════════════════════
# § 4-Leg Roll Execution
# ══════════════════════════════════════════════════════════════════════════════

async def _execute_4_leg_roll(
    monitor,
    session: dict,
    sid: str,
    spot: float,
    roll_lots: int,
    trigger_pts: float,
    spot_move_pts: float,
) -> bool:
    """
    Execute the 4-leg roll: close ITM, close OTM, sell new CE, sell new PE.
    Uses LIMIT orders throughout. STOPS session on any failure after Step 2.
    Returns True if all 4 legs completed successfully.
    """
    params = session.get('params', {})
    executor = monitor.executor
    initializer = monitor.initializer
    engine = get_engine()

    # ── Lot count sanity: use actual active position lots, not params.initial_lots ──
    # params.initial_lots may be stale (e.g. set to 1 at creation but session was
    # initialized with a different lot size). Always roll the same number of lots
    # that are currently active so the straddle stays symmetric.
    _active_ce_lots = sum(
        p.get('lots', 0) for p in session.get('ce', {}).get('positions', [])
        if p.get('status') == 'active' and p.get('lots', 0) > 0
    )
    if _active_ce_lots > 0 and _active_ce_lots != roll_lots:
        log.info(
            f"[{sid}] [STRADDLE_ROLL] lot count corrected: "
            f"params.initial_lots={roll_lots} → active CE lots={_active_ce_lots}"
        )
        roll_lots = _active_ce_lots

    # ── Gate 9 — ATM preview (freshness + same-strike + min credit + spread) ──
    expiry = params.get('expiry', '')
    try:
        roll_preview = monitor.initializer.preview_atm_straddle(expiry)
    except Exception as _preview_err:
        log.warning(f"[{sid}] [STRADDLE_ROLL] Gate 9: ATM preview failed: {_preview_err} — skipping roll")
        return False
    if not roll_preview or not roll_preview.get('success'):
        log.warning(f"[{sid}] [STRADDLE_ROLL] Gate 9: ATM preview failure: {roll_preview.get('error', '?')}")
        return False

    # Price freshness check (preview_atm_straddle uses chain cache — no WS timestamp)
    preview_timestamp = roll_preview.get('timestamp')
    if preview_timestamp:
        age_seconds = (datetime.now(timezone.utc) - preview_timestamp).total_seconds()
        max_age = params.get('straddle_roll_price_max_age_secs', 5)
        if age_seconds > max_age:
            log.warning(
                f"[{sid}] [STRADDLE_ROLL] Gate 9: preview too stale ({age_seconds:.1f}s) — skipping"
            )
            return False
    # No timestamp = chain-cache preview; freshness is guaranteed by chain service — proceed

    new_atm_strike  = roll_preview.get('atm_strike', 0)
    new_ce_premium  = roll_preview.get('ce', {}).get('mid_price', 0)
    new_pe_premium  = roll_preview.get('pe', {}).get('mid_price', 0)
    old_atm_strike  = session.get('ce', {}).get('active_strike', 0)

    if not new_atm_strike or new_atm_strike <= 0:
        log.warning(f"[{sid}] [STRADDLE_ROLL] Gate 9: invalid ATM strike — skipping")
        return False

    # Same-strike guard
    if new_atm_strike == old_atm_strike:
        log.warning(
            f"[{sid}] [STRADDLE_ROLL] Gate 9 same-strike: new ATM ({new_atm_strike:.0f}) == "
            f"old ATM ({old_atm_strike:.0f}) — spot hasn't crossed a strike boundary (spot={spot:.0f})"
        )
        return False

    if new_ce_premium <= 0 or new_pe_premium <= 0:
        log.warning(f"[{sid}] [STRADDLE_ROLL] Gate 9: invalid premiums in preview — skipping")
        return False

    # Min credit check
    new_mid_credit = (new_ce_premium + new_pe_premium) * roll_lots * LOT_SIZE_BTC
    slippage_factor = params.get('straddle_roll_slippage_factor', 0.03)
    effective_credit = new_mid_credit * (1 - slippage_factor)
    original_credit = session.get('_straddle_initial_credit', 0)
    min_credit_pct = params.get('straddle_roll_min_credit_pct', 0.30)
    if original_credit > 0 and effective_credit < min_credit_pct * original_credit:
        log.warning(
            f"[{sid}] [STRADDLE_ROLL] Gate 9 min-credit: new ATM credit ${effective_credit:.4f} "
            f"< {min_credit_pct:.0%} of original ${original_credit:.4f} — skipping"
        )
        return False

    # Spread check
    max_spread_pct = params.get('straddle_roll_max_spread_pct', 15.0)
    ce_bid = roll_preview.get('ce', {}).get('bid', 0)
    ce_ask = roll_preview.get('ce', {}).get('ask', 0)
    pe_bid = roll_preview.get('pe', {}).get('bid', 0)
    pe_ask = roll_preview.get('pe', {}).get('ask', 0)
    if ce_ask > 0 and ce_bid > 0 and pe_ask > 0 and pe_bid > 0:
        ce_spread_pct = (ce_ask - ce_bid) / ce_ask * 100
        pe_spread_pct = (pe_ask - pe_bid) / pe_ask * 100
        avg_spread_pct = (ce_spread_pct + pe_spread_pct) / 2
        if avg_spread_pct > max_spread_pct:
            log.warning(
                f"[{sid}] [STRADDLE_ROLL] Gate 9 spread: CE={ce_spread_pct:.1f}%, "
                f"PE={pe_spread_pct:.1f}%, avg={avg_spread_pct:.1f}% > {max_spread_pct:.0f}% — skipping"
            )
            return False

    # All gates passed — execute 4 legs
    ce_positions = [p for p in session.get('ce', {}).get('positions', [])
                    if p.get('status') == 'active' and p.get('lots', 0) > 0]
    pe_positions = [p for p in session.get('pe', {}).get('positions', [])
                    if p.get('status') == 'active' and p.get('lots', 0) > 0]
    roll_count = session.get('_straddle_roll_count', 0)

    # Determine ITM/OTM based on current spot
    if spot >= old_atm_strike:
        itm_side, otm_side = 'ce', 'pe'
        itm_positions, otm_positions = ce_positions, pe_positions
    else:
        itm_side, otm_side = 'pe', 'ce'
        itm_positions, otm_positions = pe_positions, ce_positions

    total_itm_lots = sum(p.get('lots', 0) for p in itm_positions)
    total_otm_lots = sum(p.get('lots', 0) for p in otm_positions)

    # ── Step 2 — Close ITM leg ────────────────────────────────────────────────
    for pos in itm_positions:
        result = await close_position(
            executor, initializer, session, pos,
            pnl_attribution_key='straddle_roll',
            hedge_guard=False,
            mechanism='straddle_roll',
            side=itm_side,
        )
        if not result.get('success'):
            log.error(f"[{sid}] [STRADDLE_ROLL] Roll aborted: {itm_side.upper()} close failed @ {pos.get('strike', 0)}")
            return False
        pos_lots = pos.get('lots', 0)
        if pos_lots > 0 and result.get('lots_closed', pos_lots) < pos_lots:
            log.error(
                f"[{sid}] [STRADDLE_ROLL] Roll aborted: partial {itm_side.upper()} close "
                f"({result.get('lots_closed')}/{pos_lots} lots)"
            )
            return False

    # ITM closed — set recovery breadcrumb
    session['_straddle_half_roll_state'] = (
        HALF_ROLL_CE_CLOSED_PE_OPEN if itm_side == 'ce' else HALF_ROLL_PE_CLOSED_CE_OPEN
    )
    session['_straddle_half_roll_itm_closed_at'] = datetime.now(timezone.utc).isoformat()

    # ── Step 3 — Close OTM leg ────────────────────────────────────────────────
    for pos in otm_positions:
        result = await close_position(
            executor, initializer, session, pos,
            pnl_attribution_key='straddle_roll',
            hedge_guard=False,
            mechanism='straddle_roll',
            side=otm_side,
        )
        if not result.get('success'):
            log.critical(
                f"[{sid}] [STRADDLE_ROLL] HALF-ROLLED: {itm_side.upper()} closed, "
                f"{otm_side.upper()} close failed — STOPPING session"
            )
            log_activity(
                'straddle_roll_blocked',
                f"⛔ Half-roll: {itm_side.upper()} closed, {otm_side.upper()} close failed",
                sid, 'error',
            )
            try:
                from .mmm_telegram import alert_half_roll_detected
                alert_half_roll_detected(sid, itm_side, otm_side, 'close_failed')
            except Exception:
                pass
            session['strategy_status'] = 'STOPPED'
            return False
        pos_lots = pos.get('lots', 0)
        if pos_lots > 0 and result.get('lots_closed', pos_lots) < pos_lots:
            log.critical(
                f"[{sid}] [STRADDLE_ROLL] HALF-ROLLED: partial {otm_side.upper()} close — STOPPING"
            )
            session['strategy_status'] = 'STOPPED'
            return False

    # Both closed — update breadcrumb
    session['_straddle_half_roll_state'] = HALF_ROLL_BOTH_CLOSED_NO_REENTRY
    session['_straddle_half_roll_both_closed_at'] = datetime.now(timezone.utc).isoformat()

    # Optional: re-fetch ATM if BTC moved significantly during close execution
    try:
        fresh_spot = await monitor._fetch_spot_price()
        if fresh_spot and fresh_spot > 0:
            move_during_close = abs(fresh_spot - spot)
            if move_during_close > trigger_pts * 0.25:
                fresh_preview = monitor.initializer.preview_atm_straddle(expiry)
                if fresh_preview and fresh_preview.get('success'):
                    new_atm_strike  = fresh_preview.get('atm_strike', new_atm_strike)
                    new_ce_premium  = fresh_preview.get('ce', {}).get('mid_price', new_ce_premium)
                    new_pe_premium  = fresh_preview.get('pe', {}).get('mid_price', new_pe_premium)
                    log.info(
                        f"[{sid}] [STRADDLE_ROLL] ATM refreshed post-close: "
                        f"BTC moved {move_during_close:.0f}pts during execution"
                    )
    except Exception:
        pass  # non-critical — proceed with original preview data

    # ── Step 4 — Sell new CE at new ATM ───────────────────────────────────────
    result_ce = await engine.execute_adjustment(
        session, 'ce', new_atm_strike, roll_lots,
        ce_now=new_ce_premium, pe_now=new_pe_premium,
        adj_type='straddle_roll',
    )
    if not result_ce.get('success'):
        log.critical(f"[{sid}] [STRADDLE_ROLL] CE re-entry failed at {new_atm_strike} — STOPPING")
        session['strategy_status'] = 'STOPPED'
        return False

    session['_straddle_half_roll_state'] = HALF_ROLL_CE_ENTERED_PE_PENDING

    # ── Step 5 — Sell new PE at new ATM ───────────────────────────────────────
    pe_lots = result_ce.get('lots_sold', roll_lots)
    result_pe = await engine.execute_adjustment(
        session, 'pe', new_atm_strike, pe_lots,
        ce_now=new_ce_premium, pe_now=new_pe_premium,
        adj_type='straddle_roll',
    )
    if not result_pe.get('success'):
        log.critical(
            f"[{sid}] [STRADDLE_ROLL] PE re-entry failed — NAKED CE at {new_atm_strike} — STOPPING"
        )
        log_activity(
            'straddle_roll_blocked',
            f"⛔ NAKED CE: PE re-entry failed at {new_atm_strike:.0f} — session STOPPED. Close CE manually.",
            sid, 'error',
        )
        try:
            from .mmm_telegram import alert_half_roll_detected
            alert_half_roll_detected(sid, 'ce', 'pe', 'reentry_pe_failed_naked_ce')
        except Exception:
            pass
        session['strategy_status'] = 'STOPPED'
        return False

    # Full roll completed — clear breadcrumb
    session['_straddle_half_roll_state'] = HALF_ROLL_NONE

    # ── Step 6 — Update state ─────────────────────────────────────────────────
    ce_lots_sold = result_ce.get('lots_sold', roll_lots)
    pe_lots_sold = result_pe.get('lots_sold', pe_lots)
    ce_fill_dec  = _D(result_ce.get('fill_price', new_ce_premium))
    pe_fill_dec  = _D(result_pe.get('fill_price', new_pe_premium))

    new_roll_credit = float(
        (ce_fill_dec * _D(ce_lots_sold) + pe_fill_dec * _D(pe_lots_sold)) * _LOT_DECIMAL
    )

    session['_straddle_roll_count'] = roll_count + 1
    session['_straddle_last_roll_at'] = datetime.now(timezone.utc).isoformat()
    session['_straddle_cumulative_credit'] = (
        session.get('_straddle_cumulative_credit',
                     session.get('_straddle_initial_credit', 0))
        + new_roll_credit
    )

    new_trigger_pts = ce_fill_dec + pe_fill_dec
    session['_straddle_roll_trigger_pts'] = float(round(new_trigger_pts, 2))
    # Reset dynamic trigger so it is recomputed fresh on next heartbeat from new entry
    session.pop('_straddle_dynamic_trigger_pts', None)

    log.info(
        f"[{sid}] [STRADDLE_ROLL] Roll #{roll_count+1} complete: "
        f"{old_atm_strike:.0f}→{new_atm_strike:.0f} | "
        f"trigger updated: {float(new_trigger_pts):.2f}pts "
        f"(CE={float(ce_fill_dec):.2f} + PE={float(pe_fill_dec):.2f})"
    )

    # ── Step 7 — Post-roll state reset ────────────────────────────────────────
    for key in (
        '_trend_regime', '_trend_tier', '_trend_direction', '_trend_anchor_spot',
        '_trend_since', '_trend_high', '_trend_low', '_trend_calm_beats',
        '_trend_plateau_beats', '_trend_t4_beats', '_trend_ema', '_trend_ema_prev',
        '_trend_ema_slope', '_trend_move_pct', '_trend_acceleration_move_pct',
        '_effective_min_trigger_move', '_theta_accelerated',
        '_straddle_entry_iv',      # recaptured on next heartbeat for new straddle
        '_straddle_last_roll_iv_spike',
        '_adaptive_tier', '_adaptive_interval',
    ):
        session.pop(key, None)

    # ── Step 8 — Audit log ────────────────────────────────────────────────────
    try:
        from .mmm_audit_log import get_event_log
        get_event_log().enqueue_event(
            session_id=sid,
            event_category='STRADDLE_ROLL',
            event_type='pure_roll_executed',
            severity='WARN',
            remark=(
                f"Pure Roll #{roll_count+1}: {old_atm_strike:.0f}→{new_atm_strike:.0f} | "
                f"spot={spot:.0f} | moved={spot_move_pts:.0f}pts | "
                f"trigger={trigger_pts:.0f}pts | "
                f"lots={ce_lots_sold}+{pe_lots_sold} | "
                f"credit=${new_roll_credit:.3f}"
            ),
            details={
                'roll_number': roll_count + 1,
                'old_strike': old_atm_strike,
                'new_strike': new_atm_strike,
                'spot': spot,
                'spot_move_pts': round(spot_move_pts, 2),
                'trigger_pts': round(trigger_pts, 2),
                'roll_lots': roll_lots,
                'itm_side': itm_side,
                'total_itm_lots_closed': total_itm_lots,
                'total_otm_lots_closed': total_otm_lots,
                'ce_lots_sold': ce_lots_sold,
                'pe_lots_sold': pe_lots_sold,
                'new_ce_premium': float(ce_fill_dec),
                'new_pe_premium': float(pe_fill_dec),
                'new_roll_credit': new_roll_credit,
                'new_trigger_pts': float(new_trigger_pts),
                'cumulative_credit': session['_straddle_cumulative_credit'],
            }
        )
    except Exception:
        pass  # audit failure must never abort the roll

    # ── Step 9 — Activity log + Telegram ─────────────────────────────────────
    log_activity(
        'straddle_roll',
        f"[PURE] Roll #{roll_count+1}: ATM {old_atm_strike:.0f}→{new_atm_strike:.0f} "
        f"({spot_move_pts:.0f}pts moved, trigger was {trigger_pts:.0f}pts) | "
        f"{roll_lots} lots | credit ${new_roll_credit:.3f} | "
        f"next trigger ±{float(new_trigger_pts):.0f}pts",
        sid, 'warning',
    )

    try:
        from .mmm_telegram import alert_straddle_roll_executed
        alert_straddle_roll_executed(
            sid, roll_count + 1,
            old_atm_strike, new_atm_strike,
            roll_lots, new_roll_credit,
        )
    except Exception:
        pass  # fire-and-forget

    return True


# ══════════════════════════════════════════════════════════════════════════════
# § Public Entry Point
# ══════════════════════════════════════════════════════════════════════════════

@sealed
async def execute_pure_straddle_roll(
    monitor,
    session: dict,
    sid: str,
    minutes_to_expiry: float,
) -> bool:
    """
    Main entry point from mmm_monitor.py Step 5.4 (elif branch).
    Called every heartbeat for STRADDLE_ROLL sessions.

    Executes the three-step decision tree:
      1. Hard stop check (market order close all)
      2. Expiry guard
      3. Roll trigger check + execution

    Protected by session-level lock to prevent concurrent roll attempts.
    Returns True if any action was taken (hard stop, expiry close, or roll).
    """
    params = session.get('params', {})

    # ── STEP 1 — HARD STOP ────────────────────────────────────────────────────
    # Check before anything else. Uses market orders for immediate fill.
    max_loss_amount = float(params.get('max_loss_amount', 0))
    use_market_stop = params.get('straddle_roll_hard_stop_market_order', True)

    if max_loss_amount > 0:
        total_pnl = _pnl_total(session)
        if total_pnl <= -max_loss_amount:
            log.critical(
                f"[{sid}] [STRADDLE_ROLL] HARD STOP: loss ${-total_pnl:.2f} ≥ "
                f"limit ${max_loss_amount:.2f} — closing all positions "
                f"({'MARKET' if use_market_stop else 'LIMIT'} orders)"
            )
            log_activity(
                'hard_stop',
                f"🚨 Hard stop: loss ${-total_pnl:.2f} ≥ ${max_loss_amount:.2f}",
                sid, 'critical',
            )

            if use_market_stop:
                closed = await _close_all_market_order(monitor, session, sid)
            else:
                # Fallback: standard close (should not happen — preset sets True)
                try:
                    await monitor._auto_close_all(reason='hard_stop')
                    closed = -1
                except Exception:
                    closed = 0

            session['strategy_status'] = 'STOPPED'

            try:
                from .mmm_telegram import alert_max_loss_breach
                await alert_max_loss_breach(
                    session_id=sid,
                    total_pnl=total_pnl,
                    max_loss=max_loss_amount,
                )
            except Exception:
                pass

            return True

    # ── STEP 2 — EXPIRY GUARD ─────────────────────────────────────────────────
    min_time = params.get('straddle_roll_min_time_to_expiry', 90)
    auto_close_mins = params.get('auto_close_mins', 10)

    if minutes_to_expiry < auto_close_mins:
        log.info(
            f"[{sid}] [STRADDLE_ROLL] Expiry close: {minutes_to_expiry:.0f}min remaining — "
            f"closing all positions"
        )
        log_activity(
            'expiry_close',
            f"⏰ Auto-close at expiry: {minutes_to_expiry:.0f}min remaining",
            sid, 'warning',
        )
        try:
            await monitor._auto_close_all(reason='expiry')
        except Exception as e:
            log.error(f"[{sid}] [STRADDLE_ROLL] Expiry close failed: {e}", exc_info=True)
        session['strategy_status'] = 'STOPPED'
        return True

    if minutes_to_expiry < min_time:
        log.info(
            f"[{sid}] [STRADDLE_ROLL] Inside {min_time}min expiry window — "
            f"holding, roll suppressed"
        )
        return False

    # ── STEP 3 — ROLL TRIGGER ─────────────────────────────────────────────────
    roll_lock = _get_pure_roll_lock(sid)
    if not roll_lock.acquire(blocking=False):
        log.debug(f"[{sid}] [STRADDLE_ROLL] Roll already in progress — skipping")
        return False

    try:
        # Fetch live spot
        spot = await monitor._fetch_spot_price()
        if not spot or spot <= 0:
            return False

        # Update dynamic trigger from live WS mark prices (sync, reads WS cache)
        _compute_dynamic_trigger(monitor, session, sid)

        # Run sync gates (Gate 0 checks _straddle_roll_in_progress — must NOT be set yet)
        can_roll, reason, ctx = _check_pure_roll_gates(
            monitor, session, sid, spot, minutes_to_expiry
        )
        if not can_roll:
            log.warning(f"[{sid}] [STRADDLE_ROLL] Roll blocked: {reason} | spot={spot:.0f} atm={session.get('ce',{}).get('active_strike',0):.0f} dyn_trig={session.get('_straddle_dynamic_trigger_pts',0):.0f} fix_trig={session.get('_straddle_roll_trigger_pts',0):.0f} tte={minutes_to_expiry:.0f}min")
            return False

        # All gates passed — mark roll in progress to block concurrent beats
        session['_straddle_roll_in_progress'] = True

        roll_count   = ctx['roll_count']
        trigger_pts  = ctx['trigger_pts']
        spot_move_pts = ctx['spot_move_pts']

        # Determine roll lot size (for pure roll: always initial_lots — no scaling)
        initial_lots = params.get('initial_lots', 1)
        if not initial_lots or initial_lots <= 0:
            log.error(f"[{sid}] [STRADDLE_ROLL] initial_lots missing — cannot roll")
            return False

        roll_fired = await _execute_4_leg_roll(
            monitor, session, sid, spot, initial_lots, trigger_pts, spot_move_pts
        )
        return roll_fired

    finally:
        session.pop('_straddle_roll_in_progress', None)
        roll_lock.release()
