"""
mmm_reverse.py — Controlled Reverse Mode for MMM algo

When reverse mode is ON, the normal MMM adjustment logic is completely suspended.
Only reverse entry logic runs. When OFF, this module has zero effect.

Follows the mmm_scaler.py / mmm_close_at_5.py isolation pattern.

Created: 2026-03-26
"""

import logging
import math
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from .mmm_constants import LOT_SIZE_BTC
from .mmm_activity import (
    log_activity, ACTIVITY_REVERSE_ENTRY,
    ACTIVITY_REVERSE_CLOSED, ACTIVITY_REVERSE_DISABLED,
    ACTIVITY_REVERSE_STATUS,
)
from .mmm_regime import ACTION_BLOCK_ALL_SELLS, ACTION_FORCE_REDUCE

log = logging.getLogger(__name__)


# =============================================================================
# State initialization
# =============================================================================

def initialize_reverse_state(session: Dict) -> None:
    """
    Set session['_reverse'] to the initial state dict.
    Call this if '_reverse' key is missing (for session restore compatibility).
    Idempotent if called on a session that already has the key.
    """
    session['_reverse'] = {
        'active': False,
        'enabled_at': None,
        'disabled_at': None,
        'disable_reason': None,
        'slots_used': 0,
        'slots_remaining': 5,
        'last_reverse_side': None,
        'last_reverse_at': None,
        'adjustment_count': 0,
        'total_lots': 0,
        'positions': [],
        'total_premium_collected': 0.0,
        'realized_pnl': 0.0,
        'unrealized_pnl': 0.0,
        'net_pnl': 0.0,
        'delta_exposure': 0.0,
        'history': [],
    }


# =============================================================================
# Eligibility checks
# =============================================================================

def _check_time_window(session: Dict) -> bool:
    """
    Return True if current UTC time is within the configured reverse window.
    Three ways to configure:
      - reverse_time_start / reverse_time_end (HH:MM strings)
      - enabled_at + reverse_duration_mins
      - Empty = always within window while active
    """
    params = session.get('params', {})
    rev = session.get('_reverse', {})

    time_start = params.get('reverse_time_start', '')
    time_end = params.get('reverse_time_end', '')
    duration_mins = int(params.get('reverse_duration_mins', 120) or 0)

    now = datetime.now(timezone.utc)

    # If explicit start/end window strings given, check against them
    if time_start and time_end:
        try:
            h_s, m_s = [int(x) for x in time_start.split(':')]
            h_e, m_e = [int(x) for x in time_end.split(':')]
            cur_mins = now.hour * 60 + now.minute
            start_mins = h_s * 60 + m_s
            end_mins = h_e * 60 + m_e
            if start_mins <= end_mins:
                return start_mins <= cur_mins <= end_mins
            else:
                # Overnight window
                return cur_mins >= start_mins or cur_mins <= end_mins
        except (ValueError, AttributeError):
            pass  # Fall through to duration check

    # If enabled_at + duration_mins set, check elapsed
    enabled_at = rev.get('enabled_at')
    if enabled_at and duration_mins > 0:
        if isinstance(enabled_at, str):
            try:
                enabled_at = datetime.fromisoformat(enabled_at)
                if enabled_at.tzinfo is None:
                    enabled_at = enabled_at.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                return True
        elapsed_mins = (now - enabled_at).total_seconds() / 60.0
        return elapsed_mins <= duration_mins

    # No window constraints — always within window
    return True


def is_reverse_mode_on(session: Dict) -> bool:
    """
    Returns True only if ALL pre-conditions pass:
    1. reverse_enabled == True
    2. Session is RUNNING
    3. Within configured time window
    4. slots_used < reverse_num_slots
    5. adjustment_count < reverse_max_adjustments
    6. reverse net_pnl > -reverse_max_loss
    7. Core safety clean (margin GREEN, trailing stop OK, max_loss buffer > 30%)
    8. Regime not ACTION_BLOCK_ALL_SELLS or ACTION_FORCE_REDUCE

    Does NOT check aggressor-side regime block — that requires aggressor param.
    Use can_execute_reverse(session, aggressor) for full gate including aggressor
    regime check.
    """
    params = session.get('params', {})

    # 1. Master switch
    if not params.get('reverse_enabled', False):
        return False

    # 2. Session must be RUNNING
    if session.get('strategy_status') != 'RUNNING':
        return False

    rev = session.get('_reverse', {})

    # 3. Active flag (set by enable_reverse_mode)
    if not rev.get('active', False):
        return False

    # 4. Time window
    if not _check_time_window(session):
        return False

    # 5. Slots remaining
    num_slots = int(params.get('reverse_num_slots', 5) or 1)
    if rev.get('slots_used', 0) >= num_slots:
        return False

    # 6. Max adjustments
    max_adj = int(params.get('reverse_max_adjustments', 3) or 1)
    if rev.get('adjustment_count', 0) >= max_adj:
        return False

    # 7. Reverse max loss
    max_loss = float(params.get('reverse_max_loss', 100.0) or 0)
    if max_loss > 0 and rev.get('net_pnl', 0.0) <= -max_loss:
        return False

    # 8. Core safety guards
    # max_loss buffer > 30%
    max_loss_buffer_pct = session.get('_max_loss_buffer_pct', 100)
    if max_loss_buffer_pct <= 30:
        return False

    # Trailing stop OK
    trailing_stop_ok = session.get('_trailing_stop_ok', True)
    if not trailing_stop_ok:
        return False

    # Margin tier GREEN
    margin_tier = session.get('_margin_tier', 'GREEN')
    if margin_tier != 'GREEN':
        return False

    # 9. Regime not block-all / force-reduce
    regime_action = session.get('_regime_action', 'NORMAL')
    if regime_action in (ACTION_BLOCK_ALL_SELLS, ACTION_FORCE_REDUCE):
        return False

    return True


def can_execute_reverse(session: Dict, aggressor: str) -> bool:
    """
    Full gate for reverse entry. Calls is_reverse_mode_on() PLUS checks
    should_block_sell on the aggressor side (not hedge side — reverse sells
    the aggressor side, so regime block must be checked on aggressor).
    """
    if not is_reverse_mode_on(session):
        return False

    # Check regime block on aggressor side
    try:
        from .mmm_regime import MMMRegimeEngine
        regime = MMMRegimeEngine()
        blocked, reason = regime.should_block_sell(session, aggressor)
        if blocked:
            log.debug(f"[REVERSE] Aggressor-side regime blocks {aggressor}: {reason}")
            return False
    except Exception as _e:
        log.debug(f"[REVERSE] Regime check failed (non-blocking): {_e}")

    return True


# =============================================================================
# Slot size calculation
# =============================================================================

def _get_reverse_slot_size(session: Dict) -> int:
    """Calculate the lot size per reverse slot."""
    params = session.get('params', {})
    override = int(params.get('reverse_slot_size_override', 0) or 0)
    if override > 0:
        return override
    max_lots = session.get('max_lots_per_side', params.get('max_lots_per_side', 10))
    capacity_pct = float(params.get('reverse_capacity_pct', 10.0) or 10.0)
    num_slots = max(1, int(params.get('reverse_num_slots', 5) or 5))
    total_reverse_lots = math.floor(max_lots * capacity_pct / 100)
    return max(1, total_reverse_lots // num_slots)


# =============================================================================
# Alternating & cooldown checks
# =============================================================================

def _check_alternating(session: Dict, aggressor: str) -> bool:
    """
    Strict alternating enforcement.
    Returns True if this aggressor side can enter (different from last, or first entry).
    """
    last = session.get('_reverse', {}).get('last_reverse_side')
    if last is None:
        return True   # first entry, OK
    if last == aggressor:
        return False  # same side blocked
    return True       # different side, OK


def _check_cooldown(session: Dict) -> bool:
    """
    Returns True if cooldown has elapsed since the last reverse entry.
    """
    rev = session.get('_reverse', {})
    last_at = rev.get('last_reverse_at')
    if last_at is None:
        return True
    cooldown_mins = float(session.get('params', {}).get('reverse_cooldown_mins', 5) or 0)
    if cooldown_mins <= 0:
        return True
    if isinstance(last_at, str):
        try:
            last_at = datetime.fromisoformat(last_at)
            if last_at.tzinfo is None:
                last_at = last_at.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return True
    elapsed = (datetime.now(timezone.utc) - last_at).total_seconds() / 60.0
    return elapsed >= cooldown_mins


# =============================================================================
# Main entry execution
# =============================================================================

async def process_reverse_entry(
    session: Dict,
    aggressor: str,
    hedge: str,
    ce_now: float,
    pe_now: float,
    engine,
) -> None:
    """
    Main entry point called from mmm_monitor.py when outcome is OUTCOME_CE/PE
    and reverse mode is active.

    Decides whether to execute a reverse entry or silently drop the trigger.
    Normal MMM _process_adjustment() NEVER runs while this is active — this is
    the hard mutual exclusion guaranteed by the if/else in mmm_monitor.py.

    Args:
        session: Live session dict
        aggressor: 'ce' or 'pe'
        hedge: opposite of aggressor
        ce_now: current CE premium
        pe_now: current PE premium
        engine: MMMEngine instance (for executor and initializer)
    """
    sid = session.get('session_id', '')

    # Ensure _reverse key exists (session restore compatibility)
    if '_reverse' not in session:
        initialize_reverse_state(session)

    # Gate 1: Full eligibility check including aggressor-side regime
    if not can_execute_reverse(session, aggressor):
        log.debug(f"[{sid}] [REVERSE] Entry gate blocked for {aggressor}")
        return

    # Gate 2: Alternating
    if not _check_alternating(session, aggressor):
        log.info(
            f"[{sid}] [REVERSE] Alternating blocked: last={session['_reverse'].get('last_reverse_side')}, "
            f"aggressor={aggressor} — trigger silently dropped"
        )
        return

    # Gate 3: Cooldown
    if not _check_cooldown(session):
        log.info(f"[{sid}] [REVERSE] Cooldown active — trigger silently dropped")
        return

    # Calculate slot size
    slot_size = _get_reverse_slot_size(session)

    # Determine strike and premium for the aggressor side
    strike = float(session.get(aggressor, {}).get('active_strike', 0) or 0)
    current_premium = ce_now if aggressor == 'ce' else pe_now

    if strike <= 0:
        log.warning(f"[{sid}] [REVERSE] No active strike for {aggressor} — cannot execute")
        return

    if not current_premium or current_premium <= 0:
        log.warning(f"[{sid}] [REVERSE] No valid premium for {aggressor} — cannot execute")
        return

    # Build symbol
    expiry = session.get('params', {}).get('expiry', '')
    option_type = 'call' if aggressor == 'ce' else 'put'
    try:
        symbol = engine.initializer.build_symbol(option_type, 'BTC', strike, expiry)
    except Exception as sym_err:
        log.error(f"[{sid}] [REVERSE] Symbol build failed: {sym_err}")
        return

    log.info(
        f"[{sid}] [REVERSE] Executing entry: SELL {slot_size} {aggressor.upper()} "
        f"@ {strike} ({symbol}) premium={current_premium:.2f}"
    )

    # Execute SELL via engine executor
    try:
        result = await engine.executor.smart_execute(
            symbol=symbol,
            side='sell',
            size=slot_size,
            session_id=sid,
        )
    except Exception as exec_err:
        log.error(f"[{sid}] [REVERSE] Execution error: {exec_err}")
        return

    if not result.get('success'):
        log.error(
            f"[{sid}] [REVERSE] Order failed: {result.get('error', 'unknown')}"
        )
        return

    fill_price = float(result.get('fill_price', current_premium) or current_premium)
    filled_lots = int(result.get('filled_size', slot_size) or slot_size)
    if filled_lots <= 0:
        filled_lots = slot_size

    # Record exchange commission if available
    _od = result.get('order_details') or {}
    _commission = float(_od.get('paid_commission', 0) or _od.get('commission', 0) or 0)
    if _commission:
        try:
            from .mmm_pnl_core import record_fee as _pnl_fee
            _pnl_fee(session, _commission, 'sell_reverse',
                     order_id=str(result.get('order_id', '')),
                     symbol=symbol, side=aggressor)
        except Exception as fee_err:
            log.warning(f"[{sid}] [REVERSE] Fee recording failed: {fee_err}")

    now = datetime.now(timezone.utc)

    # Build position record
    pos = {
        'id': f"rev_{aggressor}_{now.strftime('%H%M%S')}",
        'option_type': aggressor,
        'strike': strike,
        'entry_premium': fill_price,
        'entry_time': now.isoformat(),
        'lots': filled_lots,
        'status': 'open',
        'unrealized_pnl': 0.0,
        'realized_pnl': 0.0,
    }

    rev = session['_reverse']
    rev.setdefault('positions', []).append(pos)

    # Update reverse state
    num_slots = int(session.get('params', {}).get('reverse_num_slots', 5) or 5)
    rev['slots_used'] = rev.get('slots_used', 0) + 1
    rev['slots_remaining'] = max(0, num_slots - rev['slots_used'])
    rev['last_reverse_side'] = aggressor
    rev['last_reverse_at'] = now
    rev['adjustment_count'] = rev.get('adjustment_count', 0) + 1
    rev['total_lots'] = rev.get('total_lots', 0) + filled_lots
    premium_usd = fill_price * filled_lots * LOT_SIZE_BTC
    rev['total_premium_collected'] = rev.get('total_premium_collected', 0.0) + premium_usd

    # Log activity
    log_activity(
        ACTIVITY_REVERSE_ENTRY,
        f'[REVERSE] Sold {filled_lots} {aggressor.upper()} @ {strike} '
        f'fill={fill_price:.2f} slot={rev["slots_used"]}/{num_slots}',
        sid, 'info',
        {
            'aggressor': aggressor,
            'strike': strike,
            'fill_price': fill_price,
            'lots': filled_lots,
            'slot': rev['slots_used'],
            'total_slots': num_slots,
            'position_id': pos['id'],
        }
    )

    # Emit WebSocket event
    try:
        from .mmm_websocket import emit_reverse_entry
        emit_reverse_entry(sid, rev, pos)
    except Exception:
        pass  # WS emit is best-effort; never block trading

    log.info(
        f"[{sid}] [REVERSE] Entry recorded: {pos['id']} "
        f"lots={filled_lots} fill={fill_price:.2f} "
        f"slots={rev['slots_used']}/{num_slots}"
    )


# =============================================================================
# Mark-to-Market
# =============================================================================

def update_reverse_mtm(session: Dict, ce_now: float, pe_now: float) -> None:
    """
    Called every heartbeat to update reverse position unrealized P&L and
    delta exposure. Safe to call if _reverse key is missing.
    """
    rev = session.get('_reverse', {})
    positions = rev.get('positions', [])

    for pos in positions:
        if pos.get('status') != 'open':
            continue
        current = ce_now if pos['option_type'] == 'ce' else pe_now
        if current is None or current <= 0:
            continue
        pos['unrealized_pnl'] = (
            (pos['entry_premium'] - current) * pos['lots'] * LOT_SIZE_BTC
        )

    rev['unrealized_pnl'] = sum(
        p['unrealized_pnl'] for p in positions if p.get('status') == 'open'
    )
    rev['net_pnl'] = rev.get('realized_pnl', 0.0) + rev['unrealized_pnl']

    # Approximate delta (display-only — not included in perp hedge V1)
    # Short call: negative delta ~0.3 per lot; Short put: positive delta ~0.3 per lot
    ce_lots = sum(
        p['lots'] for p in positions
        if p.get('status') == 'open' and p.get('option_type') == 'ce'
    )
    pe_lots = sum(
        p['lots'] for p in positions
        if p.get('status') == 'open' and p.get('option_type') == 'pe'
    )
    rev['delta_exposure'] = round((-ce_lots + pe_lots) * 0.3 * LOT_SIZE_BTC, 6)


# =============================================================================
# Close-at-threshold
# =============================================================================

async def check_reverse_close_at_threshold(
    session: Dict,
    ce_now: float,
    pe_now: float,
    engine,
) -> None:
    """
    For each open reverse position, if current_premium <= reverse_close_at_threshold,
    buy back for profit.
    """
    rev = session.get('_reverse', {})
    params = session.get('params', {})
    threshold = float(params.get('reverse_close_at_threshold', 8.0) or 0)
    if threshold <= 0:
        return

    for pos in list(rev.get('positions', [])):
        if pos.get('status') != 'open':
            continue
        current = ce_now if pos['option_type'] == 'ce' else pe_now
        if current is None or current <= 0:
            continue
        if current <= threshold:
            await _close_reverse_position(
                session, pos, current, engine, reason='threshold'
            )


async def _close_reverse_position(
    session: Dict,
    pos: Dict,
    current_premium: float,
    engine,
    reason: str = 'manual',
) -> None:
    """
    Execute BUY to close a single reverse position.
    Updates pos['status'], computes realized_pnl, updates session['_reverse'].
    """
    sid = session.get('session_id', '')
    option_type = pos['option_type']
    strike = pos['strike']
    lots = pos['lots']
    expiry = session.get('params', {}).get('expiry', '')

    if lots <= 0:
        return

    option_str = 'call' if option_type == 'ce' else 'put'
    try:
        symbol = engine.initializer.build_symbol(option_str, 'BTC', strike, expiry)
    except Exception as sym_err:
        log.error(f"[{sid}] [REVERSE] Close symbol build failed: {sym_err}")
        return

    log.info(
        f"[{sid}] [REVERSE] Closing {pos['id']}: BUY {lots} {option_type.upper()} "
        f"@ {strike} current={current_premium:.2f} reason={reason}"
    )

    try:
        result = await engine.executor.smart_execute(
            symbol=symbol,
            side='buy',
            size=lots,
            reduce_only=True,
            session_id=sid,
        )
    except Exception as exec_err:
        log.error(f"[{sid}] [REVERSE] Close execution error: {exec_err}")
        return

    if not result.get('success'):
        log.error(
            f"[{sid}] [REVERSE] Close failed for {pos['id']}: "
            f"{result.get('error', 'unknown')}"
        )
        return

    close_fill = float(result.get('fill_price', current_premium) or current_premium)
    realized = (pos['entry_premium'] - close_fill) * lots * LOT_SIZE_BTC

    # Record close in pnl_core for fee attribution
    try:
        from .mmm_pnl_core import record_close as _pnl_close
        _pnl_close(
            session,
            lots_closed=lots,
            close_premium=close_fill,
            entry_premium=pos['entry_premium'],
            source='reverse_close',
            side=option_type,
            strike=strike,
            order_id=str(result.get('order_id', '')),
        )
    except Exception as pnl_err:
        log.warning(f"[{sid}] [REVERSE] record_close failed: {pnl_err}")
        # Still update reverse state even if ledger record fails

    # Update position
    pos['status'] = 'closed'
    pos['realized_pnl'] = realized
    pos['close_premium'] = close_fill
    pos['close_time'] = datetime.now(timezone.utc).isoformat()
    pos['close_reason'] = reason

    # Update reverse state
    rev = session['_reverse']
    rev['realized_pnl'] = rev.get('realized_pnl', 0.0) + realized
    rev['total_lots'] = max(0, rev.get('total_lots', 0) - lots)
    rev['net_pnl'] = rev['realized_pnl'] + rev.get('unrealized_pnl', 0.0)

    log_activity(
        ACTIVITY_REVERSE_CLOSED,
        f'[REVERSE] Closed {pos["id"]}: {lots} {option_type.upper()} @ {strike} '
        f'pnl=${realized:.2f} reason={reason}',
        sid, 'success',
        {
            'position_id': pos['id'],
            'option_type': option_type,
            'strike': strike,
            'lots': lots,
            'entry_premium': pos['entry_premium'],
            'close_premium': close_fill,
            'realized_pnl': realized,
            'reason': reason,
        }
    )

    # Emit WebSocket event
    try:
        from .mmm_websocket import emit_reverse_closed
        emit_reverse_closed(sid, rev, pos, reason)
    except Exception:
        pass


# =============================================================================
# Close all reverse positions
# =============================================================================

async def close_all_reverse_positions(
    session: Dict,
    engine,
    reason: str = 'manual',
) -> None:
    """
    Close all open reverse positions. Called when:
    - Operator turns off reverse mode
    - Auto-disable on max_loss or emergency
    - _auto_close_all() (called first before CE/PE)
    - Wind-down activation

    Args:
        session: Live session dict
        engine: MMMEngine instance
        reason: human-readable close reason
    """
    sid = session.get('session_id', '')
    rev = session.get('_reverse', {})
    open_positions = [p for p in rev.get('positions', []) if p.get('status') == 'open']

    if not open_positions:
        log.debug(f"[{sid}] [REVERSE] close_all: no open positions")
    else:
        log.info(
            f"[{sid}] [REVERSE] Closing all {len(open_positions)} open positions: reason={reason}"
        )

        # Fetch fresh premiums for close
        try:
            from .mmm_initializer import get_initializer
            initializer = get_initializer()
            for pos in open_positions:
                option_type = pos['option_type']
                try:
                    strike = pos['strike']
                    expiry = session.get('params', {}).get('expiry', '')
                    opt_str = 'call' if option_type == 'ce' else 'put'
                    symbol = initializer.build_symbol(opt_str, 'BTC', strike, expiry)
                    # Use last known premium as fallback
                    current = pos.get('entry_premium', 0)
                    try:
                        rest = engine.executor._create_rest_client()
                        ticker = await rest._request_with_retry(
                            method='GET',
                            path=f'/v2/tickers/{symbol}'
                        )
                        mark = ticker.get('result', {}).get('mark_price')
                        if mark:
                            current = float(mark)
                    except Exception:
                        pass  # Use fallback price
                    await _close_reverse_position(session, pos, current, engine, reason=reason)
                except Exception as pos_err:
                    log.error(f"[{sid}] [REVERSE] Error closing position {pos.get('id')}: {pos_err}")
        except Exception as outer_err:
            log.error(f"[{sid}] [REVERSE] close_all error: {outer_err}")

    # Deactivate reverse if reason is not partial
    if reason != 'partial':
        rev['active'] = False


# =============================================================================
# Emergency detection
# =============================================================================

def check_reverse_emergency(session: Dict) -> bool:
    """
    Returns True if core positions are bleeding hard this heartbeat and reverse
    should auto-disable.

    Compares _prev_core_net_pnl to current total P&L to detect sudden core loss.
    Called from mmm_monitor.py M2M phase after update_reverse_mtm().
    """
    params = session.get('params', {})
    threshold = float(params.get('reverse_unhedged_emergency_loss', 200.0) or 0)
    if threshold <= 0:
        return False

    prev = session.get('_prev_core_net_pnl', None)
    if prev is None:
        return False

    try:
        from .mmm_pnl_core import compute_current_total_pnl
        current_pnl = compute_current_total_pnl(session)
    except Exception:
        return False

    # core_loss_this_beat = how much P&L dropped from prev snapshot
    core_loss_this_beat = float(prev) - float(current_pnl)
    return core_loss_this_beat > threshold


# =============================================================================
# Enable / Disable
# =============================================================================

def disable_reverse_mode(session: Dict, reason: str) -> None:
    """
    Auto-disable reverse mode. Sets active=False, records reason, turns off
    the param switch so next heartbeat doesn't re-enable.
    """
    rev = session.get('_reverse', {})
    rev['active'] = False
    rev['disabled_at'] = datetime.now(timezone.utc).isoformat()
    rev['disable_reason'] = reason
    session.get('params', {})['reverse_enabled'] = False

    sid = session.get('session_id', '')
    log_activity(
        ACTIVITY_REVERSE_DISABLED,
        f'[REVERSE] Auto-disabled: {reason}',
        sid, 'warning',
        {'reason': reason}
    )
    log.warning(f"[{sid}] [REVERSE] Auto-disabled: {reason}")

    # Emit WebSocket event
    try:
        from .mmm_websocket import emit_reverse_disabled
        emit_reverse_disabled(sid, reason)
    except Exception:
        pass


def enable_reverse_mode(session: Dict) -> None:
    """
    Enable reverse mode. Resets slots/positions for a new activation window.
    Called by the API endpoint when operator turns reverse ON.
    """
    initialize_reverse_state(session)  # reset to fresh state
    session['_reverse']['active'] = True
    session['_reverse']['enabled_at'] = datetime.now(timezone.utc)

    sid = session.get('session_id', '')
    log_activity(
        ACTIVITY_REVERSE_STATUS,
        '[REVERSE] Enabled by operator',
        sid, 'info',
        {'action': 'enabled'}
    )
    log.info(f"[{sid}] [REVERSE] Enabled by operator")

    # Emit WebSocket event
    try:
        from .mmm_websocket import emit_reverse_status
        emit_reverse_status(sid, session['_reverse'])
    except Exception:
        pass
