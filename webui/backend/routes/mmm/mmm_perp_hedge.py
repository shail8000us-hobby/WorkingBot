"""
MMM Perpetual Futures Delta Hedge — Money Mind & Method

Fix #26: BTCUSD perpetual futures used to neutralize portfolio delta.
Linear instrument (delta-only, zero gamma) enables delta-neutral selling.

Runs after each adjustment (Step 7.5) and before P&L update (Step 8).
Perp MUST be closed FIRST before options on session stop (§26.10).

Design (§26.2):
  - Portfolio margin mode: perp is a separate instrument, not cross-margin
  - Full delta neutralization at configurable hedge_ratio (0.3–1.0)
  - Funding rate accepted as cost
  - Perp + adjustments run simultaneously (institutional approach)

Created: February 22, 2026
"""

import asyncio  # M-3 fix: moved from inline imports inside retry loop to module top
import logging
import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple

log = logging.getLogger('mmm_perp_hedge')

# BTC perpetual contract on Delta Exchange
BTCUSD_SYMBOL = 'BTCUSD'

# H-1 fix: import from canonical source instead of duplicating the constant
from .mmm_constants import LOT_SIZE_BTC


def _D(x) -> Decimal:
    """Decimal precision helper (Fix #19 pattern)."""
    return Decimal(str(x))


# =============================================================================
# State Management
# =============================================================================

def _init_perp_state() -> Dict:
    """Initial blank perp hedge state, stored at session['perp_hedge']."""
    return {
        'lots': 0,               # signed; positive = long, negative = short
        'avg_entry': 0.0,        # average fill price of current position
        'realized_pnl': 0.0,     # cumulative realized P&L from all closes
        'unrealized_pnl': 0.0,   # mark-to-market P&L on current position
        'last_hedge_time': None,  # ISO8601 timestamp of last execution
        'total_hedge_count': 0,   # total hedge executions this session
        'last_flip_at': None,     # timestamp of last long↔short flip
        'target_lots': 0,         # target lots from last hedge computation
        'last_delta': 0.0,        # portfolio_delta at last hedge
    }


def get_perp_state(session: Dict) -> Dict:
    """Get (or create) the perp_hedge state dict from session."""
    if 'perp_hedge' not in session:
        session['perp_hedge'] = _init_perp_state()
    return session['perp_hedge']


def is_perp_hedge_enabled(session: Dict) -> bool:
    """Return True if perp delta hedging is enabled."""
    return session.get('params', {}).get('perp_hedge_enabled', False)


# =============================================================================
# Delta Computation
# =============================================================================

def compute_required_hedge(
    session: Dict,
    portfolio_delta: float,
) -> Dict[str, Any]:
    """
    Compute the perp hedge action required to neutralize portfolio delta.

    Args:
        session: Full session dict
        portfolio_delta: Net delta of all options positions (from Step 3.5)

    Returns:
        {
            action: 'buy' | 'sell' | 'none',
            lots_to_trade: int,    # always positive; use 'action' for direction
            target_lots: int,      # signed target position
            effective_delta: float, # residual delta before proposed hedge
            reason: str,
        }
    """
    params = session.get('params', {})
    delta_threshold = params.get('perp_hedge_delta_threshold', 0.02)
    rebalance_band = params.get('perp_hedge_rebalance_band', 0.005)
    hedge_ratio = params.get('perp_hedge_ratio', 1.0)
    max_lots = params.get('perp_hedge_max_lots', 50)

    perp = get_perp_state(session)
    current_lots = perp.get('lots', 0)

    # Effective delta = options delta + perp delta contribution
    # positive lots = long perp = positive delta contribution
    perp_delta = current_lots * LOT_SIZE_BTC
    effective_delta = portfolio_delta + perp_delta

    # Compute signed target lots to neutralize portfolio delta
    # target = -portfolio_delta * hedge_ratio / LOT_SIZE_BTC
    raw_target = -portfolio_delta * hedge_ratio / LOT_SIZE_BTC
    target_lots = int(round(raw_target))

    # Cap at max_lots (preserve sign)
    if abs(target_lots) > max_lots:
        sign = 1 if target_lots > 0 else -1
        target_lots = sign * max_lots

    lots_delta = target_lots - current_lots

    # Gate: only open a new position if |portfolio_delta| >= delta_threshold
    if current_lots == 0:
        if abs(portfolio_delta) < delta_threshold:
            return {
                'action': 'none',
                'lots_to_trade': 0,
                'target_lots': 0,
                'effective_delta': effective_delta,
                'reason': (
                    f'|Δ|={abs(portfolio_delta):.4f} below threshold '
                    f'{delta_threshold:.4f} — no hedge needed'
                ),
            }
    else:
        # Existing position: only rebalance if |effective_delta| >= rebalance_band
        if abs(effective_delta) < rebalance_band:
            return {
                'action': 'none',
                'lots_to_trade': 0,
                'target_lots': current_lots,
                'effective_delta': effective_delta,
                'reason': (
                    f'|effective_Δ|={abs(effective_delta):.4f} within '
                    f'rebalance band {rebalance_band:.4f} — holding'
                ),
            }

    if lots_delta == 0:
        return {
            'action': 'none',
            'lots_to_trade': 0,
            'target_lots': target_lots,
            'effective_delta': effective_delta,
            'reason': 'Already at target lots — no trade needed',
        }

    action = 'buy' if lots_delta > 0 else 'sell'
    lots_to_trade = abs(lots_delta)

    post_hedge_delta = portfolio_delta + target_lots * LOT_SIZE_BTC

    log.info(
        f"Perp hedge: portfolio_Δ={portfolio_delta:+.4f}, "
        f"current={current_lots:+d} lots, target={target_lots:+d} lots, "
        f"action={action} {lots_to_trade}, "
        f"post_Δ≈{post_hedge_delta:+.4f}"
    )

    return {
        'action': action,
        'lots_to_trade': lots_to_trade,
        'target_lots': target_lots,
        'effective_delta': effective_delta,
        'reason': (
            f'{action.upper()} {lots_to_trade} lots: '
            f'Δ={portfolio_delta:+.4f} → ~{post_hedge_delta:+.4f}'
        ),
    }


# =============================================================================
# Cooldown
# =============================================================================

def _is_cooldown_active(session: Dict) -> Tuple[bool, float]:
    """
    Check if minimum cooldown between hedge executions has elapsed.

    Returns:
        (is_active: bool, seconds_remaining: float)
    """
    params = session.get('params', {})
    cooldown_sec = params.get('perp_hedge_cooldown_sec', 30)

    perp = get_perp_state(session)
    last_hedge = perp.get('last_hedge_time')

    if not last_hedge:
        return False, 0.0

    try:
        last_dt = datetime.fromisoformat(last_hedge)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
        remaining = cooldown_sec - elapsed
        if remaining > 0:
            return True, remaining
        return False, 0.0
    except Exception as e:
        log.warning(f"Perp hedge cooldown check failed: {e}")
        return False, 0.0


# =============================================================================
# State Updates
# =============================================================================

def update_perp_state_after_fill(
    session: Dict,
    action: str,
    lots_traded: int,
    fill_price: float,
    target_lots: int,
) -> float:
    """
    Update perp_hedge state after a successful fill.

    Computes realized P&L if the fill closes/reduces an existing position.
    Uses weighted average for position additions.

    Args:
        session: Full session dict (mutated in place)
        action: 'buy' or 'sell'
        lots_traded: absolute number of lots filled
        fill_price: execution fill price
        target_lots: signed target lots (stored for reference)

    Returns:
        realized_pnl: P&L realized from this fill (0.0 if only opening)
    """
    perp = get_perp_state(session)
    old_lots = perp.get('lots', 0)
    old_avg = perp.get('avg_entry', 0.0)
    now = datetime.now(timezone.utc).isoformat()

    # Signed lots change: buy → +lots, sell → -lots
    signed_lots = lots_traded if action == 'buy' else -lots_traded
    new_lots = old_lots + signed_lots

    flipped = (
        old_lots != 0 and
        ((old_lots > 0 and new_lots < 0) or (old_lots < 0 and new_lots > 0))
    )

    realized_pnl = 0.0

    if old_lots == 0:
        # Opening new position
        perp['avg_entry'] = fill_price
        perp['lots'] = new_lots

    elif (old_lots > 0 and signed_lots > 0) or (old_lots < 0 and signed_lots < 0):
        # Adding to same-direction position: weighted average entry
        total = abs(old_lots) + abs(signed_lots)
        perp['avg_entry'] = float(
            (_D(old_avg) * _D(abs(old_lots)) + _D(fill_price) * _D(abs(signed_lots)))
            / _D(total)
        )
        perp['lots'] = new_lots

    elif not flipped:
        # Reducing position (same sign, smaller magnitude)
        lots_closed = abs(signed_lots)
        direction = 1 if old_lots > 0 else -1
        realized_pnl = float(
            (_D(fill_price) - _D(old_avg)) * _D(direction)
            * _D(lots_closed) * _D(LOT_SIZE_BTC)
        )
        perp['lots'] = new_lots
        if new_lots == 0:
            perp['avg_entry'] = 0.0

    else:
        # Position flipped: close old, open new
        lots_closed = abs(old_lots)
        direction = 1 if old_lots > 0 else -1
        realized_pnl = float(
            (_D(fill_price) - _D(old_avg)) * _D(direction)
            * _D(lots_closed) * _D(LOT_SIZE_BTC)
        )
        remaining = abs(new_lots)
        perp['avg_entry'] = fill_price if remaining > 0 else 0.0
        perp['lots'] = new_lots
        perp['last_flip_at'] = now

    perp['realized_pnl'] = perp.get('realized_pnl', 0.0) + realized_pnl
    perp['last_hedge_time'] = now
    perp['total_hedge_count'] = perp.get('total_hedge_count', 0) + 1
    perp['last_delta'] = session.get('portfolio_delta', 0.0)
    perp['target_lots'] = target_lots

    # Best estimate of unrealized P&L at fill price until next mark update
    if perp['lots'] != 0 and perp['avg_entry'] != 0.0:
        perp['unrealized_pnl'] = float(
            (_D(fill_price) - _D(perp['avg_entry']))
            * _D(perp['lots']) * _D(LOT_SIZE_BTC)
        )
    else:
        perp['unrealized_pnl'] = 0.0

    log.info(
        f"Perp fill: {action} {lots_traded} @ {fill_price:.2f}, "
        f"realized={realized_pnl:+.4f}, "
        f"position={perp['lots']:+d} lots @ {perp['avg_entry']:.2f}"
        + (' [FLIP]' if flipped else '')
    )

    return realized_pnl


def update_perp_mark_pnl(session: Dict, mark_price: float):
    """
    Update unrealized P&L at current BTC mark price.

    Called at top of run_perp_hedge() each heartbeat to keep
    perp_hedge.unrealized_pnl fresh for safety checks.

    Args:
        session: Full session dict (mutated in place)
        mark_price: Current BTC mark price (from session['_regime_spot_price'])
    """
    perp = get_perp_state(session)
    lots = perp.get('lots', 0)
    avg_entry = perp.get('avg_entry', 0.0)

    if lots == 0 or avg_entry == 0.0:
        perp['unrealized_pnl'] = 0.0
        return

    perp['unrealized_pnl'] = float(
        (_D(mark_price) - _D(avg_entry)) * _D(lots) * _D(LOT_SIZE_BTC)
    )


# =============================================================================
# Execution
# =============================================================================

async def _execute_hedge_order(
    executor,
    session: Dict,
    action: str,
    lots: int,
) -> Dict[str, Any]:
    """
    Place a perp hedge order via smart_execute.

    Retries ONCE on failure (§26.7). Escalates to CRITICAL on second failure.

    Args:
        executor: MMMExecutor instance
        session: Full session dict
        action: 'buy' or 'sell'
        lots: absolute number of lots to trade

    Returns:
        {success, fill_price, filled_size, error}
    """
    sid = session.get('session_id', '?')
    log.info(f"[{sid}] Perp hedge: {action.upper()} {lots} lots {BTCUSD_SYMBOL}")

    for attempt in range(1, 3):  # max 2 attempts
        try:
            result = await executor.smart_execute(
                symbol=BTCUSD_SYMBOL,
                side=action,
                size=lots,
                reduce_only=False,  # Perp can flip direction in one order
            )
            if result.get('success'):
                log.info(
                    f"[{sid}] Perp hedge filled (attempt {attempt}): "
                    f"{action} {lots} @ {result.get('fill_price', 0):.2f}"
                )
                return result
            else:
                error_msg = result.get('error', 'unknown')
                if attempt == 1:
                    log.warning(
                        f"[{sid}] Perp hedge order failed (attempt 1), retrying: "
                        f"{error_msg}"
                    )
                    await asyncio.sleep(2)  # Brief pause before retry
                    continue
                else:
                    log.critical(
                        f"[{sid}] Perp hedge order FAILED after 2 attempts: "
                        f"{action} {lots} lots — {error_msg}. "
                        f"Manual intervention may be required."
                    )
                    return result
        except Exception as e:
            if attempt == 1:
                log.warning(
                    f"[{sid}] Perp hedge execution exception (attempt 1), "
                    f"retrying: {e}"
                )
                await asyncio.sleep(2)
                continue
            else:
                log.critical(
                    f"[{sid}] Perp hedge execution FAILED after 2 attempts: "
                    f"{action} {lots} lots — {e}. "
                    f"Manual intervention may be required."
                )
                return {'success': False, 'error': str(e)}

    # Should not reach here, but safety fallback
    return {'success': False, 'error': 'Exhausted retries'}


def _check_flip_rate(session: Dict, action: str, current_lots: int) -> tuple:
    """M-8 fix: rate-limit perp hedge direction flips.

    Each flip costs bid-ask spread + slippage. In choppy markets this drag
    can exceed $0.30-0.50 per flip; 480 flips/4 hours = up to $240 drag.

    Returns:
        (allowed: bool, reason: str)
    """
    # A flip happens when the new action would reverse the current position
    is_flip = (action == 'buy' and current_lots < 0) or \
              (action == 'sell' and current_lots > 0)
    if not is_flip:
        return True, 'not a flip'

    params = session.get('params', {})
    max_flips = params.get('perp_hedge_max_flips_per_hour', 6)
    perp = session.setdefault('perp_hedge', {})

    # Prune timestamps older than 1 hour
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    flip_timestamps = perp.get('flip_timestamps', [])
    recent_flips = [
        t for t in flip_timestamps
        if datetime.fromisoformat(t) > one_hour_ago
    ]
    perp['flip_timestamps'] = recent_flips  # Persist pruned list

    if len(recent_flips) >= max_flips:
        return (
            False,
            f"Perp hedge paused: {len(recent_flips)} flips in last hour (max {max_flips})"
        )
    return True, 'flip allowed'


def _record_flip(session: Dict):
    """M-8 fix: record a direction flip timestamp."""
    perp = session.setdefault('perp_hedge', {})
    timestamps = perp.setdefault('flip_timestamps', [])
    timestamps.append(datetime.now(timezone.utc).isoformat())


async def run_perp_hedge(
    session: Dict,
    executor,
    portfolio_delta: float,
    btc_mark_price: float,
) -> Dict[str, Any]:
    """
    Main perp hedge entry point — called each heartbeat (Step 7.5).

    1. Update mark P&L with latest BTC price
    2. Check if perp hedge is enabled
    3. Guard: skip if P&L calculation incomplete (Fix #2 stale-delta guard)
    4. Compute required hedge
    5. Check cooldown
    6. Execute hedge order
    7. Update state + emit events

    Args:
        session: Full session dict (mutated in place)
        executor: MMMExecutor instance
        portfolio_delta: Net portfolio delta (from Step 3.5, cached)
        btc_mark_price: Current BTC mark price (session['_regime_spot_price'])

    Returns:
        {action, lots_traded, fill_price, realized_pnl, reason}
    """
    sid = session.get('session_id', '?')

    # 1. Update mark P&L regardless of hedge execution
    update_perp_mark_pnl(session, btc_mark_price)

    # 2. Check master switch
    if not is_perp_hedge_enabled(session):
        return {
            'action': 'skipped', 'lots_traded': 0, 'fill_price': 0,
            'realized_pnl': 0, 'reason': 'perp_hedge_enabled=False',
        }

    # 3. Fix #2 guard: skip if P&L data is incomplete (stale delta)
    if session.get('_pnl_calculation_incomplete'):
        log.warning(
            f"[{sid}] Perp hedge skipped: P&L calculation incomplete "
            f"(stale delta may cause wrong-direction trade)"
        )
        return {
            'action': 'skipped', 'lots_traded': 0, 'fill_price': 0,
            'realized_pnl': 0,
            'reason': 'P&L calculation incomplete — delta unreliable',
        }

    # 4. Compute required hedge
    required = compute_required_hedge(session, portfolio_delta)
    if required['action'] == 'none':
        log.debug(f"[{sid}] Perp hedge: {required['reason']}")
        return {
            'action': 'none', 'lots_traded': 0, 'fill_price': 0,
            'realized_pnl': 0, 'reason': required['reason'],
        }

    # 5. Cooldown check
    in_cooldown, remaining = _is_cooldown_active(session)
    if in_cooldown:
        log.debug(
            f"[{sid}] Perp hedge cooldown: {remaining:.1f}s remaining"
        )
        return {
            'action': 'skipped', 'lots_traded': 0, 'fill_price': 0,
            'realized_pnl': 0,
            'reason': f'Cooldown: {remaining:.1f}s remaining',
        }

    # 5.5 M-8 fix: rate-limit perp direction flips to avoid spread drag
    action = required['action']
    lots = required['lots_to_trade']
    current_lots = session.get('perp_hedge', {}).get('lots', 0)
    flip_allowed, flip_reason = _check_flip_rate(session, action, current_lots)
    if not flip_allowed:
        log.warning(f"[{sid}] {flip_reason}")
        try:
            from .mmm_websocket import emit_safety
            emit_safety(
                sid, 'perp_hedge_flip_blocked', 'warning',
                f'[PERP HEDGE] {flip_reason}',
                {'action': action, 'lots': lots},
            )
        except Exception:
            pass
        return {
            'action': 'skipped', 'lots_traded': 0, 'fill_price': 0,
            'realized_pnl': 0, 'reason': flip_reason,
        }

    # 6. Execute hedge order
    result = await _execute_hedge_order(executor, session, action, lots)

    if not result.get('success'):
        from .mmm_websocket import emit_safety
        emit_safety(
            sid, 'perp_hedge_failed', 'critical',
            f"Perp hedge order FAILED after retries: {action} {lots} lots — "
            f"{result.get('error', 'unknown')}. Manual check required.",
            {'action': action, 'lots': lots, 'error': result.get('error')},
        )
        return {
            'action': 'failed', 'lots_traded': 0, 'fill_price': 0,
            'realized_pnl': 0,
            'reason': f"Order failed: {result.get('error', 'unknown')}",
        }

    # 7. Update state and emit events
    fill_price = result.get('fill_price', 0)
    filled_lots = result.get('filled_size', lots)

    # Capture old lots BEFORE state update (needed for flip event)
    old_lots = session.get('perp_hedge', {}).get('lots', 0)

    realized_pnl = update_perp_state_after_fill(
        session, action, filled_lots, fill_price, required['target_lots']
    )

    # M-8 fix: record flip timestamp if this was a direction flip
    is_flip = (action == 'buy' and old_lots < 0) or (action == 'sell' and old_lots > 0)
    if is_flip:
        _record_flip(session)

    # Pass old_lots for flip detection in _emit_perp_events
    required['_old_lots'] = old_lots
    _emit_perp_events(session, action, filled_lots, fill_price, required)

    return {
        'action': action,
        'lots_traded': filled_lots,
        'fill_price': fill_price,
        'realized_pnl': realized_pnl,
        'reason': required['reason'],
    }


async def close_all_perp(
    session: Dict,
    executor,
    reason: str = 'session_stop',
) -> Dict[str, Any]:
    """
    §26.10: Close entire perp position unconditionally.

    Called FIRST in _auto_close_all() before any options close.
    Also called when both sides are fully closed via close-at-5.

    Args:
        session: Full session dict (mutated in place)
        executor: MMMExecutor instance
        reason: Human-readable reason for close

    Returns:
        {success, lots_closed, fill_price, realized_pnl, reason}
    """
    sid = session.get('session_id', '?')
    perp = get_perp_state(session)
    current_lots = perp.get('lots', 0)

    if current_lots == 0:
        log.info(f"[{sid}] Perp close-all: no position to close")
        return {
            'success': True, 'lots_closed': 0, 'fill_price': 0,
            'realized_pnl': 0, 'reason': 'No perp position to close',
        }

    # To close: opposite direction of current position
    action = 'sell' if current_lots > 0 else 'buy'
    lots = abs(current_lots)

    log.info(
        f"[{sid}] Perp close-all: {action.upper()} {lots} lots "
        f"({BTCUSD_SYMBOL}), reason={reason}"
    )

    result = await _execute_hedge_order(executor, session, action, lots)

    if not result.get('success'):
        from .mmm_websocket import emit_safety
        emit_safety(
            sid, 'perp_close_failed', 'critical',
            f"CRITICAL: Perp position close FAILED — {action} {lots} lots: "
            f"{result.get('error', 'unknown')}. Manual intervention required.",
            {
                'action': action, 'lots': lots,
                'error': result.get('error'), 'reason': reason,
            },
        )
        log.critical(
            f"[{sid}] Perp close-all FAILED: {action} {lots} lots — "
            f"{result.get('error', 'unknown')}. Manual close required."
        )
        return {
            'success': False, 'lots_closed': 0, 'fill_price': 0,
            'realized_pnl': 0,
            'reason': f"Close failed: {result.get('error', 'unknown')}",
        }

    fill_price = result.get('fill_price', 0)
    filled_lots = result.get('filled_size', lots)
    realized_pnl = update_perp_state_after_fill(
        session, action, filled_lots, fill_price, 0
    )

    log.info(
        f"[{sid}] Perp close-all complete: {filled_lots} lots @ {fill_price:.2f}, "
        f"realized_pnl={realized_pnl:+.4f}, reason={reason}"
    )

    return {
        'success': True,
        'lots_closed': filled_lots,
        'fill_price': fill_price,
        'realized_pnl': realized_pnl,
        'reason': reason,
    }


# =============================================================================
# Helpers
# =============================================================================

def get_perp_total_pnl(session: Dict) -> float:
    """Return total perp P&L (realized + unrealized)."""
    perp = session.get('perp_hedge', {})
    return perp.get('realized_pnl', 0.0) + perp.get('unrealized_pnl', 0.0)


def get_perp_summary(session: Dict) -> Dict:
    """
    Return perp hedge summary for heartbeat emission.

    Returns:
        {
            enabled, lots, avg_entry, realized_pnl, unrealized_pnl,
            total_pnl, last_hedge_time, total_hedge_count, last_delta,
            target_lots, symbol,
        }
    """
    enabled = is_perp_hedge_enabled(session)
    perp = session.get('perp_hedge', {})
    realized = perp.get('realized_pnl', 0.0)
    unrealized = perp.get('unrealized_pnl', 0.0)

    return {
        'enabled': enabled,
        'lots': perp.get('lots', 0),
        'avg_entry': perp.get('avg_entry', 0.0),
        'realized_pnl': realized,
        'unrealized_pnl': unrealized,
        'total_pnl': realized + unrealized,
        'last_hedge_time': perp.get('last_hedge_time'),
        'total_hedge_count': perp.get('total_hedge_count', 0),
        'last_delta': perp.get('last_delta', 0.0),
        'target_lots': perp.get('target_lots', 0),
        'symbol': BTCUSD_SYMBOL,
    }


def _emit_perp_events(
    session: Dict,
    action: str,
    lots: int,
    fill_price: float,
    required: Dict,
):
    """Emit WebSocket events after a perp hedge execution."""
    from .mmm_websocket import emit_perp_hedge_execution
    perp = get_perp_state(session)
    sid = session.get('session_id', '?')

    emit_perp_hedge_execution(
        session_id=sid,
        action=action,
        lots=lots,
        fill_price=fill_price,
        effective_delta=required.get('effective_delta', 0),
        target_lots=required.get('target_lots', 0),
        current_lots=perp.get('lots', 0),
        realized_pnl=perp.get('realized_pnl', 0.0),
        unrealized_pnl=perp.get('unrealized_pnl', 0.0),
    )

    # §26.13: Emit flip event when position direction changes
    old_lots = required.get('_old_lots', 0)
    new_lots = perp.get('lots', 0)
    flipped = (
        old_lots != 0 and new_lots != 0 and
        ((old_lots > 0 and new_lots < 0) or (old_lots < 0 and new_lots > 0))
    )
    if flipped:
        from .mmm_websocket import emit_perp_hedge_flip
        old_dir = 'long' if old_lots > 0 else 'short'
        new_dir = 'long' if new_lots > 0 else 'short'
        emit_perp_hedge_flip(
            session_id=sid,
            old_direction=old_dir,
            new_direction=new_dir,
            lots_closed=abs(old_lots),
            new_lots=new_lots,
            realized_pnl=perp.get('realized_pnl', 0.0),
            fill_price=fill_price,
        )
