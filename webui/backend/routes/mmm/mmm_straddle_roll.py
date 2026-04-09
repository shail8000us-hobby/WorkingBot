"""
MMM Straddle Roll — Full ATM Reset for SHORT_STRADDLE sessions

When BTC moves far enough from the current ATM strike, this module:
1. Buys back BOTH legs (ITM first, then OTM) sequentially
2. Sells new CE + PE at the new ATM strike
3. Tracks roll count, credits, and enforces safety gates

Two public functions:
- check_straddle_roll_gates(): 12 sync gates, returns (bool, str, dict)
- execute_straddle_roll(): async entry point from mmm_monitor.py Step 5.4

Reference: tasks/MMM_STRADDLE_ROLL_PLAN.md Rev 3.3 FINAL

Created: 2026-03-20
"""

import logging
import threading
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Tuple, Any

from .mmm_constants import LOT_SIZE_BTC
from .mmm_pnl_core import compute_current_total_pnl as _pnl_total
from .mmm_dte_presets import SHORT_STRADDLE_CATEGORY
from .mmm_close_at_5 import close_position
from .mmm_engine import get_engine
from .mmm_wind_down import is_wind_down_active
from .mmm_margin_guardian import TIER_RED, TIER_CRITICAL
from .mmm_activity import log_activity
from webui.backend.sealed import sealed

log = logging.getLogger('mmm_straddle_roll')


# ══════════════════════════════════════════════════════════════════════════════
# § Decimal Precision (HIGH-RISK FIX H-1)
# ══════════════════════════════════════════════════════════════════════════════

def _D(x) -> Decimal:
    """Convert float/int to Decimal via string to avoid IEEE 754 rounding errors."""
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


_LOT_DECIMAL = _D(LOT_SIZE_BTC)  # 0.001 BTC as Decimal constant


# ══════════════════════════════════════════════════════════════════════════════
# § Session-Level Roll Locks (CRITICAL FIX C-1)
# ══════════════════════════════════════════════════════════════════════════════

_roll_locks: Dict[str, threading.Lock] = {}
_roll_locks_lock = threading.Lock()


def _get_roll_lock(session_id: str) -> threading.Lock:
    """Get or create a lock for this session - prevents concurrent roll attempts."""
    with _roll_locks_lock:
        if session_id not in _roll_locks:
            _roll_locks[session_id] = threading.Lock()
        return _roll_locks[session_id]


def _cleanup_roll_lock(session_id: str):
    """Remove lock when session ends (call from mmm_monitor.py stop_monitor)."""
    with _roll_locks_lock:
        _roll_locks.pop(session_id, None)


# ══════════════════════════════════════════════════════════════════════════════
# § Half-Roll Recovery States (CRITICAL FIX C-3)
# ══════════════════════════════════════════════════════════════════════════════

HALF_ROLL_NONE = None
HALF_ROLL_CE_CLOSED_PE_OPEN = 'ce_closed_pe_open'
HALF_ROLL_PE_CLOSED_CE_OPEN = 'pe_closed_ce_open'
HALF_ROLL_BOTH_CLOSED_NO_REENTRY = 'both_closed_no_reentry'
HALF_ROLL_CE_ENTERED_PE_PENDING = 'ce_entered_pe_pending'


@sealed
def check_straddle_roll_gates(
    monitor,
    session: dict,
    sid: str,
    spot: float,
    distance_pct: float,
    minutes_to_expiry: float,
) -> Tuple[bool, str, dict]:
    """
    Run SYNC gates only: Gates 0, 1, 1.5, 2, 2.5, 3, 4, 5, 5.5, 6, 7, 8, 10.
    Gate 9 (ATM viability) is intentionally EXCLUDED — preview_atm_straddle is
    sync but is called inside execute_straddle_roll after all other gates pass.

    Returns (can_roll: bool, reason: str, context_dict: dict).
    context_dict keys on success:
      - roll_count (int)    — pre-roll count
      - ce_positions (list) — active CE positions (verified non-empty by Gate 2.5)
      - pe_positions (list) — active PE positions (verified non-empty by Gate 2.5)

    CRITICAL: ALL failure returns MUST be 3-tuples: (False, 'reason_string', {})
    NEVER return a 2-tuple. The caller always unpacks 3 values.

    SIDE EFFECTS:
    - May write session['_straddle_entry_iv'] (Gate 5.5 lazy IV capture)
    - Writes session['_straddle_roll_blocked'] and '_straddle_roll_block_logged' (Gate 6)
    - May write session['strategy_status'] = 'PAUSED' (Gate 6 auto-pause on exhaustion)
    """
    # ── Preamble — extract params from session
    params = session.get('params', {})
    roll_count = session.get('_straddle_roll_count', 0)
    straddle_roll_enabled = params.get('straddle_roll_enabled', False)
    straddle_roll_max_per_session = params.get('straddle_roll_max_per_session', 3)
    straddle_roll_cooldown_mins = params.get('straddle_roll_cooldown_mins', 15)
    straddle_roll_emergency_mult = params.get('straddle_roll_emergency_mult', 2.0)
    straddle_roll_min_time_to_expiry = params.get('straddle_roll_min_time_to_expiry', 90)
    straddle_roll_iv_spike_mult = params.get('straddle_roll_iv_spike_mult', 2.0)
    straddle_roll_trigger_pct = params.get('straddle_roll_trigger_pct', 1.0)
    straddle_roll_loss_abort_mult = params.get('straddle_roll_loss_abort_mult', 3.0)

    # ── Gate 0 — Not already rolling (CRITICAL FIX C-1) ──────────────────────
    # Defense-in-depth: check session flag as well as lock (lock is primary guard)
    if session.get('_straddle_roll_in_progress'):
        return False, 'roll_already_in_progress', {}

    # ── Gate 1 — Master switch ────────────────────────────────────────────────
    if not straddle_roll_enabled:
        return False, 'disabled', {}

    # ── Gate 1.5 — Strategy status ────────────────────────────────────────────
    status = session.get('strategy_status')
    if status not in (None, 'RUNNING', 'ACTIVE'):
        return False, 'session_not_running', {}

    # ── Gate 2 — Correct preset ───────────────────────────────────────────────
    if params.get('_preset_source') != SHORT_STRADDLE_CATEGORY:
        return False, 'wrong_preset', {}

    # ── Gate 2.5 — Leg symmetry ───────────────────────────────────────────────
    # Position filter: status='active' confirmed from mmm_engine.py line 871.
    ce_positions = [p for p in session.get('ce', {}).get('positions', [])
                    if p.get('status') == 'active' and p.get('lots', 0) > 0]
    pe_positions = [p for p in session.get('pe', {}).get('positions', [])
                    if p.get('status') == 'active' and p.get('lots', 0) > 0]
    # Rolling with one empty leg re-enters only that leg → naked position.
    if not ce_positions or not pe_positions:
        return False, 'leg_asymmetry', {}

    # ── Gate 3 — Wind-down not active ────────────────────────────────────────
    if is_wind_down_active(session):
        return False, 'wind_down_active', {}

    # ── Gate 4 — Time to expiry ───────────────────────────────────────────────
    if minutes_to_expiry < straddle_roll_min_time_to_expiry:
        return False, 'insufficient_time', {}

    # ── Gate 5 — Margin safety ────────────────────────────────────────────────
    mg = getattr(monitor, '_margin_guardian', None)
    if mg is None or mg.last_tier in (TIER_RED, TIER_CRITICAL):
        return False, 'margin_safety_blocked', {}

    # ── Gate 5.5 — IV spike check ────────────────────────────────────────────
    monitor_iv_data = getattr(monitor, '_last_iv_data', None) or {}

    # Lazy IV capture: set _straddle_entry_iv on first heartbeat that has real IV data.
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
            f"[{sid}] IV spike noted (current={current_iv:.1f} > "
            f"{entry_iv:.1f} × {straddle_roll_iv_spike_mult}) "
            f"— proceeding with roll. High IV = higher new premium. "
            f"Margin gate (Gate 5) is the real protection."
        )
        session['_straddle_last_roll_iv_spike'] = True  # audit trail
        # Do NOT block — fall through to remaining gates

    # ── Gate 6 — Max rolls not exhausted ─────────────────────────────────────
    if roll_count < straddle_roll_max_per_session:
        # Auto-clear blocked flag — handles hot-reload where user raised max_per_session
        session['_straddle_roll_blocked'] = False
        session['_straddle_roll_block_logged'] = False
    else:
        session['_straddle_roll_blocked'] = True
        # Auto-pause + alert: fire exactly once on first exhaustion heartbeat.
        if not session.get('_straddle_roll_block_logged'):
            log.warning(
                f"[{sid}] Max straddle rolls exhausted "
                f"({roll_count}/{straddle_roll_max_per_session}) — auto-pausing"
            )
            session['strategy_status'] = 'PAUSED'
            log_activity(
                'straddle_roll_blocked',
                f"⛔ All {straddle_roll_max_per_session} rolls exhausted — session paused. "
                f"max_loss still active. Resume or close manually.",
                sid, 'error',
            )
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
    # Emergency bypass uses same trigger_pts as Gate 8.
    # Compute spot_move_pts here too since Gate 8 hasn't run yet at this point.
    # NOTE: current_atm_strike is read at top of Gate 8 — but Gate 7 runs before Gate 8.
    # Read it locally here for the bypass check.
    _g7_atm = session.get('ce', {}).get('active_strike', 0)
    _g7_spot_move = abs(spot - _g7_atm) if _g7_atm > 0 else 0
    _g7_trigger = session.get('_straddle_roll_trigger_pts', 0) or (
        straddle_roll_trigger_pct / 100.0 * spot if spot > 0 else 0
    )
    emergency_bypass = (
        _g7_trigger > 0 and
        _g7_spot_move >= _g7_trigger * straddle_roll_emergency_mult
    )
    if not (normal_cooldown or emergency_bypass):
        return False, 'cooldown_not_elapsed', {}

    # ── Gate 8 — Distance trigger (premium-points based) ─────────────────────
    # Roll fires when spot has moved ≥ (CE_entry_premium + PE_entry_premium) points.
    # This is the financial breakeven of a short straddle seller.
    # Fallback chain: session key → live positions → pct-based floor → block.
    current_atm_strike = session.get('ce', {}).get('active_strike', 0)
    if not current_atm_strike or current_atm_strike <= 0:
        return False, 'invalid_atm_strike', {}

    spot_move_pts = abs(spot - current_atm_strike)

    trigger_pts = session.get('_straddle_roll_trigger_pts', 0)
    if trigger_pts <= 0:
        # Fallback 1: compute live from active positions
        _ce_pos = [p for p in session.get('ce', {}).get('positions', [])
                   if p.get('status') == 'active' and p.get('lots', 0) > 0]
        _pe_pos = [p for p in session.get('pe', {}).get('positions', [])
                   if p.get('status') == 'active' and p.get('lots', 0) > 0]
        _ce_lots = sum(p.get('lots', 0) for p in _ce_pos)
        _pe_lots = sum(p.get('lots', 0) for p in _pe_pos)
        _ce_avg = (sum(float(p.get('entry_premium', 0)) * p.get('lots', 0)
                       for p in _ce_pos) / _ce_lots) if _ce_lots > 0 else 0
        _pe_avg = (sum(float(p.get('entry_premium', 0)) * p.get('lots', 0)
                       for p in _pe_pos) / _pe_lots) if _pe_lots > 0 else 0
        trigger_pts = _ce_avg + _pe_avg
        if trigger_pts > 0:
            session['_straddle_roll_trigger_pts'] = round(trigger_pts, 2)
            log.info(f"[{sid}] Gate 8 fallback: healed trigger_pts={trigger_pts:.2f}pts from positions")
        else:
            # Fallback 2: pct-based floor (wrong but better than blocking all rolls)
            pct_fallback = straddle_roll_trigger_pct / 100.0 * spot if spot > 0 else 0
            if pct_fallback > 0:
                trigger_pts = pct_fallback
                log.warning(
                    f"[{sid}] Gate 8 pct-fallback: trigger_pts={trigger_pts:.2f}pts "
                    f"(no entry_premium on positions — check position state)"
                )
            else:
                return False, 'no_trigger_pts', {}

    if spot_move_pts < trigger_pts:
        return False, (
            f'distance_below_trigger ({spot_move_pts:.0f} < {trigger_pts:.0f} pts)'
        ), {}

    # ── Gate 10 — Loss abort using total P&L (HIGH-RISK FIX H-1: Decimal precision) ──
    # BATCH-D FIX BUG-1: Use canonical _pnl_total() which includes fees and reverse_pnl.
    # Previous inline formula omitted total_fees and reverse_pnl (same pattern as M-01 BUG-2).
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
    }


@sealed
async def execute_straddle_roll(
    monitor,
    session: dict,
    sid: str,
    minutes_to_expiry: float,
) -> bool:
    """
    Main entry point from mmm_monitor.py Step 5.4.

    Protected by session-level lock to prevent concurrent roll attempts (CRITICAL FIX C-1).

    Flow:
      1. Acquire lock (non-blocking)
      2. Set in-progress flag
      3. Call _execute_straddle_roll_inner() with all logic
      4. Clear flag and release lock in finally block

    Returns True if roll was executed this beat.
    """
    # ──────────────────────────────────────────────────────────────────────────
    # CRITICAL FIX C-1: Acquire session roll lock before ANY session modifications
    # ──────────────────────────────────────────────────────────────────────────
    roll_lock = _get_roll_lock(sid)
    if not roll_lock.acquire(blocking=False):
        log.debug(f"[{sid}] Roll already in progress — skipping")
        return False

    try:
        session['_straddle_roll_in_progress'] = True
        session['_straddle_roll_start_time'] = datetime.now(timezone.utc).isoformat()

        return await _execute_straddle_roll_inner(monitor, session, sid, minutes_to_expiry)

    finally:
        session.pop('_straddle_roll_in_progress', None)
        session.pop('_straddle_roll_start_time', None)
        roll_lock.release()


async def _execute_straddle_roll_inner(
    monitor,
    session: dict,
    sid: str,
    minutes_to_expiry: float,
) -> bool:
    """Inner implementation (runs inside lock). All existing roll logic."""
    params = session.get('params', {})

    # ── 1. Spot fetch (async) ─────────────────────────────────────────────────
    spot = await monitor._fetch_spot_price()
    if not spot or spot <= 0:
        return False

    # ── 2. Active strike guard + distance computation ─────────────────────────
    current_atm_strike = session.get('ce', {}).get('active_strike', 0)
    if not current_atm_strike or current_atm_strike <= 0:
        return False

    distance_pct = abs(spot - current_atm_strike) / current_atm_strike * 100

    # ── 3. Sync gates (1, 1.5, 2, 2.5, 3, 4, 5, 5.5, 6, 7, 8, 10) ──────────
    can_roll, reason, ctx = check_straddle_roll_gates(
        monitor, session, sid, spot, distance_pct, minutes_to_expiry
    )
    if not can_roll:
        if reason and reason != 'max_rolls_exhausted':
            log.debug(f"[{sid}] Straddle roll blocked: {reason}")
        return False

    # Extract positions from ctx — Gate 2.5 verified both non-empty
    ce_positions = ctx['ce_positions']
    pe_positions = ctx['pe_positions']
    roll_count = ctx['roll_count']

    # ══════════════════════════════════════════════════════════════════════════
    # HIGH-RISK FIX H-2: Position Size Validation
    # ══════════════════════════════════════════════════════════════════════════
    ce_available = sum(p.get('lots', 0) for p in ce_positions if p.get('status') == 'active')
    pe_available = sum(p.get('lots', 0) for p in pe_positions if p.get('status') == 'active')
    max_rollable = min(ce_available, pe_available)

    if max_rollable <= 0:
        log.error(
            f"[{sid}] Roll aborted: no active lots available "
            f"(CE={ce_available}, PE={pe_available})"
        )
        return False

    # ── 4. Step 0: lot sizing WITH POSITION CAP ────────────────────────────────
    initial_lots = params.get('initial_lots', 0)
    if not initial_lots or initial_lots <= 0:
        log.error(f"[{sid}] Roll aborted: initial_lots missing or zero in session params")
        return False
    lot_scale = params.get('straddle_roll_lot_scale', 1.0)
    desired_roll_lots = max(1, int(initial_lots * (lot_scale ** roll_count)))

    # Cap at available size (HIGH-RISK FIX H-2 continued)
    roll_lots = min(desired_roll_lots, max_rollable)

    if roll_lots < desired_roll_lots:
        log.warning(
            f"[{sid}] Roll lots capped: desired {desired_roll_lots}, available {max_rollable} "
            f"— rolling {roll_lots} lots"
        )

    # ── 5. Gate 9 inline (sync, no await) ─────────────────────────────────────
    expiry = params.get('expiry', '')
    try:
        roll_preview = monitor.initializer.preview_atm_straddle(expiry)
    except Exception as _preview_err:
        log.warning(f"[{sid}] Gate 9: ATM preview failed: {_preview_err} — skipping roll")
        return False
    if not roll_preview or not roll_preview.get('success'):
        log.warning(f"[{sid}] Gate 9: ATM preview failure: {roll_preview.get('error', '?')}")
        return False

    # ──────────────────────────────────────────────────────────────────────────
    # CRITICAL FIX C-2: Validate price freshness
    # ──────────────────────────────────────────────────────────────────────────
    preview_timestamp = roll_preview.get('timestamp')
    if preview_timestamp:
        age_seconds = (datetime.now(timezone.utc) - preview_timestamp).total_seconds()
        straddle_roll_price_max_age_secs = params.get('straddle_roll_price_max_age_secs', 5)
        if age_seconds > straddle_roll_price_max_age_secs:
            log.warning(
                f"[{sid}] Gate 9: Roll preview too stale ({age_seconds:.1f}s old) — "
                f"market may have moved, skipping roll"
            )
            return False
    else:
        # Missing timestamp field — reject to be safe
        log.warning(f"[{sid}] Gate 9: Roll preview missing timestamp — cannot validate freshness")
        return False

    # Additional preview data validation
    new_atm_strike = roll_preview.get('atm_strike', 0)
    if not new_atm_strike or new_atm_strike <= 0:
        log.warning(f"[{sid}] Gate 9: Invalid ATM strike from preview — skipping roll")
        return False

    # CHANGE 3-B: Same-strike guard — no point rolling to the same strike
    old_atm_strike = session.get('ce', {}).get('active_strike', 0)
    if new_atm_strike == old_atm_strike:
        log.info(
            f"[{sid}] Roll skipped: new ATM strike ({new_atm_strike:.0f}) == "
            f"old ATM ({old_atm_strike:.0f}) — spot move insufficient for strike migration"
        )
        return False
    new_ce_premium = roll_preview.get('ce', {}).get('mid_price', 0)
    new_pe_premium = roll_preview.get('pe', {}).get('mid_price', 0)
    if new_ce_premium <= 0 or new_pe_premium <= 0:
        log.warning(f"[{sid}] Gate 9: Invalid premiums from preview — skipping roll")
        return False

    new_mid_credit = (new_ce_premium + new_pe_premium) * roll_lots * LOT_SIZE_BTC
    effective_credit = new_mid_credit * (1 - params.get('straddle_roll_slippage_factor', 0.03))
    # Direct access safe: Gate 10 verified original_credit > 0.
    original_credit = session['_straddle_initial_credit']
    if effective_credit < params.get('straddle_roll_min_credit_pct', 0.30) * original_credit:
        log.info(
            f"[{sid}] Gate 9: new ATM credit ${effective_credit:.4f} "
            f"< {params.get('straddle_roll_min_credit_pct', 0.30):.0%} of "
            f"original ${original_credit:.4f} — skipping roll"
        )
        return False

    # CHANGE 3-D: Spread check — reject if bid-ask spread is too wide
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
                f"[{sid}] Gate 9 spread: CE spread={ce_spread_pct:.1f}%, "
                f"PE spread={pe_spread_pct:.1f}%, avg={avg_spread_pct:.1f}% "
                f"> max {max_spread_pct:.0f}% — skipping roll (illiquid)"
            )
            return False

    # ══════════════════════════════════════════════════════════════════════════
    # All 12 gates passed — execute 4-leg roll
    # ══════════════════════════════════════════════════════════════════════════

    # ── Preamble: resolve executor/engine context ─────────────────────────────
    executor = monitor.executor
    initializer = monitor.initializer
    engine = get_engine()

    # ── Step 1 — Retrieve ATM preview data (local, never stored in session) ──
    new_atm_strike = roll_preview.get('atm_strike', 0)
    if not new_atm_strike or new_atm_strike <= 0:
        log.warning(f"[{sid}] Roll aborted: preview returned no ATM strike")
        return False
    new_ce_premium = roll_preview.get('ce', {}).get('mid_price', 0)
    new_pe_premium = roll_preview.get('pe', {}).get('mid_price', 0)
    old_atm_strike = current_atm_strike

    # ── Step 2 — Close ITM leg first (dynamic, direction-aware) ──────────────
    if spot >= current_atm_strike:
        itm_side, otm_side = 'ce', 'pe'
        itm_positions, otm_positions = ce_positions, pe_positions
    else:
        itm_side, otm_side = 'pe', 'ce'
        itm_positions, otm_positions = pe_positions, ce_positions

    # Pre-compute lots to close from position sizes
    total_itm_lots_closed = sum(p.get('lots', 0) for p in itm_positions)
    total_otm_lots_closed = sum(p.get('lots', 0) for p in otm_positions)

    for pos in itm_positions:
        result = await close_position(
            executor, initializer, session, pos,
            pnl_attribution_key='straddle_roll',
            hedge_guard=False,
            mechanism='straddle_roll',
            side=itm_side,
        )
        if not result.get('success'):
            log.error(f"[{sid}] Roll aborted: {itm_side.upper()} close failed at {pos.get('strike', 0)}")
            return False
        pos_lots = pos.get('lots', 0)
        if pos_lots > 0 and result.get('lots_closed', pos_lots) < pos_lots:
            log.error(
                f"[{sid}] Roll aborted: partial close on {itm_side.upper()} "
                f"({result.get('lots_closed')}/{pos_lots} lots) — aborting to avoid hybrid position"
            )
            return False

    # SUCCESS: ITM leg closed — set recovery breadcrumb (CRITICAL FIX C-3)
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
                f"[{sid}] Roll HALF-ROLLED: {itm_side.upper()} closed, "
                f"{otm_side.upper()} close failed — session stopped"
            )
            log_activity(
                'straddle_roll_blocked',
                f"⛔ Half-roll: {itm_side.upper()} closed, {otm_side.upper()} close failed",
                sid, 'error',
            )

            # CRITICAL FIX C-3: Fire Telegram alert for half-roll
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
                f"[{sid}] Roll HALF-ROLLED: {itm_side.upper()} closed, "
                f"{otm_side.upper()} partial fill "
                f"({result.get('lots_closed')}/{pos_lots} lots) — session stopped"
            )
            session['strategy_status'] = 'STOPPED'
            return False

    # SUCCESS: Both legs closed — update breadcrumb (CRITICAL FIX C-3)
    session['_straddle_half_roll_state'] = HALF_ROLL_BOTH_CLOSED_NO_REENTRY
    session['_straddle_half_roll_both_closed_at'] = datetime.now(timezone.utc).isoformat()

    # ── Step 4 — Sell new CE at new ATM ───────────────────────────────────────
    result_ce = await engine.execute_adjustment(
        session, 'ce', new_atm_strike, roll_lots,
        ce_now=new_ce_premium, pe_now=new_pe_premium,
        adj_type='straddle_roll',
    )
    if not result_ce.get('success'):
        log.critical(f"[{sid}] Roll re-entry failed: CE sell at {new_atm_strike}")
        session['strategy_status'] = 'STOPPED'
        return False
    if result_ce.get('partial_fill'):
        log.warning(
            f"[{sid}] Roll CE partial fill: {result_ce.get('lots_sold')}/{roll_lots} lots. "
            f"Position temporarily asymmetric — safety checks will handle."
        )

    # SUCCESS: CE re-entered — update breadcrumb (CRITICAL FIX C-3)
    session['_straddle_half_roll_state'] = HALF_ROLL_CE_ENTERED_PE_PENDING

    # ── Step 5 — Sell new PE at new ATM ───────────────────────────────────────
    # H-2 fix: if CE partial fill, sell matching PE lots
    pe_lots = result_ce.get('lots_sold', roll_lots)
    result_pe = await engine.execute_adjustment(
        session, 'pe', new_atm_strike, pe_lots,
        ce_now=new_ce_premium, pe_now=new_pe_premium,
        adj_type='straddle_roll',
    )
    if result_pe.get('partial_fill'):
        log.warning(
            f"[{sid}] Roll PE partial fill: {result_pe.get('lots_sold')}/{pe_lots} lots. "
            f"Position asymmetric after roll — safety checks will handle."
        )
    if not result_pe.get('success'):
        log.critical(f"[{sid}] Roll re-entry failed: PE sell at {new_atm_strike}")
        log_activity(
            'straddle_roll_blocked',
            f"⛔ NAKED CE: PE re-entry failed at {new_atm_strike:.0f} — "
            f"session stopped. Close CE manually.",
            sid, 'error',
        )

        # CRITICAL FIX C-3: Fire CRITICAL Telegram alert for naked CE
        try:
            from .mmm_telegram import alert_half_roll_detected
            alert_half_roll_detected(sid, 'ce', 'pe', 'reentry_pe_failed_naked_ce')
        except Exception:
            pass

        session['strategy_status'] = 'STOPPED'
        return False

    # SUCCESS: Full roll completed — clear breadcrumb (CRITICAL FIX C-3)
    session['_straddle_half_roll_state'] = HALF_ROLL_NONE

    # ── Step 6 — Update roll tracking state (HIGH-RISK FIX H-1: Decimal precision) ──
    ce_lots_sold = result_ce.get('lots_sold', roll_lots)
    pe_lots_sold = result_pe.get('lots_sold', pe_lots)

    # Use Decimal for financial precision
    ce_fill_price_dec = _D(result_ce.get('fill_price', new_ce_premium))
    pe_fill_price_dec = _D(result_pe.get('fill_price', new_pe_premium))

    new_roll_credit = float(
        (ce_fill_price_dec * _D(ce_lots_sold) + pe_fill_price_dec * _D(pe_lots_sold))
        * _LOT_DECIMAL
    )

    session['_straddle_roll_count'] = roll_count + 1
    session['_straddle_last_roll_at'] = datetime.now(timezone.utc).isoformat()
    session['_straddle_cumulative_credit'] = (
        session.get('_straddle_cumulative_credit',
                     session.get('_straddle_initial_credit', 0))
        + new_roll_credit
    )

    # Update premium-based trigger for NEXT roll — use actual fill prices, not preview.
    new_trigger_pts = ce_fill_price_dec + pe_fill_price_dec
    session['_straddle_roll_trigger_pts'] = float(round(new_trigger_pts, 2))
    log.info(
        f"[{sid}] Roll trigger updated: "
        f"{new_trigger_pts:.2f}pts (CE={float(ce_fill_price_dec):.2f} + PE={float(pe_fill_price_dec):.2f})"
    )

    # ── Step 7 — Event log ────────────────────────────────────────────────────
    try:
        from .mmm_audit_log import get_event_log
        get_event_log().enqueue_event(
            session_id=sid,
            event_category='STRADDLE_ROLL',
            event_type='roll_executed',
            severity='WARN',
            remark=(
                f"Roll #{roll_count+1}: {old_atm_strike:.0f}→{new_atm_strike:.0f} | "
                f"spot={spot:.0f} | dist={distance_pct:.2f}% | "
                f"closed={total_itm_lots_closed}+{total_otm_lots_closed} lots | "
                f"re-entered={ce_lots_sold}+{pe_lots_sold} lots | "
                f"new_credit=${new_roll_credit:.3f}"
            ),
            details={
                'roll_number': roll_count + 1,
                'old_strike': old_atm_strike,
                'new_strike': new_atm_strike,
                'spot': spot,
                'distance_pct': round(distance_pct, 4),
                'roll_lots': roll_lots,
                'itm_side': itm_side,
                'total_itm_lots_closed': total_itm_lots_closed,
                'total_otm_lots_closed': total_otm_lots_closed,
                'ce_lots_sold': ce_lots_sold,
                'pe_lots_sold': pe_lots_sold,
                'new_ce_premium': new_ce_premium,
                'new_pe_premium': new_pe_premium,
                'new_roll_credit': new_roll_credit,
                'cumulative_credit': session['_straddle_cumulative_credit'],
            }
        )
    except Exception:
        pass  # fire-and-forget, never let audit failure crash the roll

    # ── Step 8 — Activity log + Telegram + return ─────────────────────────────
    log_activity(
        'straddle_roll',
        f"Roll #{roll_count+1}: ATM {old_atm_strike:.0f}→{new_atm_strike:.0f} "
        f"(dist {distance_pct:.2f}%) | {roll_lots} lots | credit ${new_roll_credit:.3f}",
        sid, 'warning',
    )

    # CHANGE 3-E: Telegram alert on successful roll
    try:
        from .mmm_telegram import alert_straddle_roll_executed
        alert_straddle_roll_executed(
            sid, roll_count + 1,
            old_atm_strike, new_atm_strike,
            roll_lots, new_roll_credit,
        )
    except ImportError:
        pass  # alert function not yet defined — will be added
    except Exception:
        pass  # fire-and-forget

    # CHANGE 3-A: Post-roll clean state reset — stale regime/trigger state
    # from the old strike position must not leak into the new position's first beat.
    session.pop('_trend_regime', None)
    session.pop('_trend_tier', None)
    session.pop('_trend_direction', None)
    session.pop('_trend_anchor_spot', None)
    session.pop('_trend_since', None)
    session.pop('_trend_high', None)
    session.pop('_trend_low', None)
    session.pop('_trend_calm_beats', None)
    session.pop('_trend_plateau_beats', None)
    session.pop('_trend_t4_beats', None)
    session.pop('_trend_ema', None)
    session.pop('_trend_ema_prev', None)
    session.pop('_trend_ema_slope', None)
    session.pop('_trend_move_pct', None)
    session.pop('_trend_acceleration_move_pct', None)
    session.pop('_effective_min_trigger_move', None)
    session.pop('_theta_accelerated', None)
    session.pop('_straddle_entry_iv', None)  # re-capture on next heartbeat
    # Clear IV spike audit trail from this roll
    session.pop('_straddle_last_roll_iv_spike', None)
    # Reset adaptive interval
    session.pop('_adaptive_tier', None)
    session.pop('_adaptive_interval', None)

    log.info(
        f"[{sid}] Post-roll state reset: regime/trend/IV/adaptive cleared for clean slate"
    )

    return True
