"""
MMM Close-at-5 — Money Mind & Method

Scans ALL open positions (original + adjustment + frozen) every heartbeat.
If any position's premium drops to <= close_at_threshold (default 5),
buy it back to lock in realized profit.

Maps to MONEY_POWER_CALCULATION_LOGIC.md:
  §11: Close-at-5 Rule

Created: February 15, 2026
"""

import logging
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from .mmm_state import recompute_side_lots
from .mmm_constants import LOT_SIZE_BTC

# Fix #19: Decimal precision helper — mirrors mmm_engine._D
def _D(x) -> Decimal:
    return Decimal(str(x))

_LOT = _D(LOT_SIZE_BTC)

log = logging.getLogger('mmm_close_at_5')


def scan_closeable_positions(
    session: Dict,
    fetch_premium_fn,
    threshold_override: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    §11: Scan ALL positions across both sides for premiums <= threshold.

    Args:
        session: Full session dict
        fetch_premium_fn: callable(strike, option_type) → current_premium
        threshold_override: If provided, use this instead of params threshold.
                           Used by wind-down mode to elevate the close threshold.

    Returns:
        List of positions that should be closed, each:
        {side, strike, lots, entry_premium, current_premium, type, profit}
    """
    params = session.get('params', {})
    threshold = threshold_override if threshold_override is not None else params.get('close_at_threshold', 5.0)
    closeable = []

    for side_key in ['ce', 'pe']:
        side_state = session.get(side_key, {})
        option_type = 'call' if side_key == 'ce' else 'put'
        active_strike = side_state.get('active_strike', 0)

        # Fix #23: Look up original position ID from positions[] for ID-based removal
        # Audit fix: skip positions marked _being_closed (in-flight guard)
        orig_pos_id = None
        orig_being_closed = False
        for _p in side_state.get('positions', []):
            if _p.get('type') == 'original' and _p.get('status') == 'active':
                orig_pos_id = _p.get('id')
                orig_being_closed = _p.get('_being_closed', False)
                break

        # Check original lots at original strike (Fix #9: use original_strike, not
        # active_strike. In current flow they're the same until a shift occurs, at
        # which point original_lots becomes 0 anyway. Using original_strike here is
        # the correct defensive approach — avoids premium mismatch if the two ever
        # diverge in future code paths).
        orig_lots = side_state.get('original_lots', 0)
        orig_prem = side_state.get('original_premium', 0)
        orig_strike = side_state.get('original_strike', active_strike)
        if orig_lots > 0 and orig_strike > 0 and not orig_being_closed:
            try:
                current = fetch_premium_fn(orig_strike, option_type)
                if current <= threshold:
                    profit = (orig_prem - current) * orig_lots
                    closeable.append({
                        'side': side_key,
                        'strike': orig_strike,
                        'lots': orig_lots,
                        'entry_premium': orig_prem,
                        'current_premium': current,
                        'type': 'original',
                        'profit': profit,
                        '_pos_id': orig_pos_id,  # Fix #23: ID-based removal
                    })
            except Exception as e:
                log.warning(f"Error fetching {side_key} original premium: {e}")


        # Check adjustment fills at active strike
        # Fix #8: removal is content-match based (with Fix #23 ID fallback)
        for fill in side_state.get('adjustment_fills', []):
            lots = fill.get('lots', 0)
            prem = fill.get('premium', 0)
            strike = fill.get('strike', active_strike)
            if lots > 0:
                try:
                    current = fetch_premium_fn(strike, option_type)
                    if current <= threshold:
                        profit = (prem - current) * lots
                        closeable.append({
                            'side': side_key,
                            'strike': strike,
                            'lots': lots,
                            'entry_premium': prem,
                            'current_premium': current,
                            'type': 'adjustment',
                            'profit': profit,
                            '_pos_id': fill.get('_pos_id'),  # Fix #23: ID-based removal
                        })
                except Exception as e:
                    log.warning(f"Error fetching adj fill premium: {e}")

        # Check frozen positions
        # Fix #8: removal is content-match based (with Fix #23 ID fallback)
        for frozen in side_state.get('frozen_positions', []):
            lots = frozen.get('lots', 0)
            prem = frozen.get('entry_premium', 0)
            strike = frozen.get('strike', 0)
            if lots > 0 and strike > 0:
                try:
                    current = fetch_premium_fn(strike, option_type)
                    if current <= threshold:
                        profit = (prem - current) * lots
                        closeable.append({
                            'side': side_key,
                            'strike': strike,
                            'lots': lots,
                            'entry_premium': prem,
                            'current_premium': current,
                            'type': 'frozen',
                            'profit': profit,
                            '_pos_id': frozen.get('_pos_id'),  # Fix #23: ID-based removal
                        })
                except Exception as e:
                    log.warning(f"Error fetching frozen premium: {e}")

    # Log scan summary for debugging (even when nothing is closeable)
    session_id = session.get('session_id', '?')
    total_checked = 0
    for side_key in ['ce', 'pe']:
        ss = session.get(side_key, {})
        total_checked += (1 if ss.get('original_lots', 0) > 0 else 0)
        total_checked += len([f for f in ss.get('adjustment_fills', []) if f.get('lots', 0) > 0])
        total_checked += len([f for f in ss.get('frozen_positions', []) if f.get('lots', 0) > 0])

    if not closeable and total_checked > 0:
        log.debug(
            f"[{session_id}] Close-at-5 scan: checked {total_checked} positions, "
            f"none below threshold {threshold:.1f}"
        )

    if closeable:
        log.info(
            f"[{session_id}] Found {len(closeable)} position(s) eligible for close-at-5 "
            f"(threshold={threshold:.1f})"
        )
        # Fix #8: content-match-first removal makes index-based sorting unnecessary.
        # Sort by profit descending — close the most profitable positions first.
        # (Frozen > adjustment > original ordering is preserved as a secondary key
        # so higher-premium frozen positions don't accidentally beat active strikes.)
        _type_order = {'frozen': 2, 'adjustment': 1, 'original': 0}
        closeable.sort(
            key=lambda p: (
                p.get('side', ''),
                _type_order.get(p.get('type', ''), -1),
                p.get('profit', 0),
            ),
            reverse=True,
        )

    return closeable


async def close_position(
    executor,
    initializer,
    session: Dict,
    position: Dict,
) -> Dict[str, Any]:
    """
    §11: Buy back a single position at market/ask price.

    Args:
        executor: MMMExecutor instance
        initializer: MMMInitializer instance for symbol building
        session: Full session dict (mutated in place)
        position: Position dict from scan_closeable_positions

    Returns:
        {success, realized_pnl, close_premium, lots_closed}

    Audit fix (double-close guard): Sets _being_closed=True on the position in
    positions[] BEFORE placing the exchange order. If the order fills but
    _remove_closed_position() crashes, the position stays in-state but is marked
    as in-flight. scan_closeable_positions() skips '_being_closed' positions, so
    the next heartbeat will NOT place a duplicate buy order on the exchange.
    On failure, the flag is cleared to allow retry on the next scan cycle.
    """
    side = position['side']
    strike = position['strike']
    lots = position['lots']
    entry_prem = position['entry_premium']
    pos_type = position['type']
    pos_id = position.get('_pos_id')

    # Audit fix: Mark position as in-flight in the ledger BEFORE placing order.
    # This prevents a duplicate buy order if the state-removal crashes post-fill.
    side_state = session.get(side, {})
    if pos_id:
        for pos in side_state.get('positions', []):
            if pos.get('id') == pos_id:
                if pos.get('_being_closed'):
                    log.warning(
                        f"Close-at-5: Skipping {side.upper()} pos_id={pos_id} — "
                        f"already marked _being_closed (in-flight guard). "
                        f"Previous close may have partially succeeded."
                    )
                    return {
                        'success': False,
                        'error': 'Position already being closed (in-flight guard)',
                    }
                pos['_being_closed'] = True
                break

    # Build symbol
    expiry = session.get('params', {}).get('expiry', '')
    option_type = 'call' if side == 'ce' else 'put'
    symbol = initializer.build_symbol(option_type, 'BTC', strike, expiry)

    log.info(
        f"Close-at-5: Buying back {lots} {side.upper()} @ {strike} "
        f"({symbol}), current ~{position.get('current_premium', 0):.2f}"
    )

    try:
        result = await executor.smart_execute(
            symbol=symbol,
            side='buy',
            size=lots,
            reduce_only=True,
        )

        if not result.get('success'):
            # Clear in-flight flag so position can be retried next heartbeat
            if pos_id:
                for pos in side_state.get('positions', []):
                    if pos.get('id') == pos_id:
                        pos.pop('_being_closed', None)
                        break
            return {
                'success': False,
                'error': result.get('error', 'Buy-back not filled'),
            }

        close_price = result.get('fill_price', 0)
        # Fix #19: Decimal arithmetic to prevent float rounding accumulation
        realized_pnl = float((_D(entry_prem) - _D(close_price)) * _D(lots) * _LOT)

        # Update state: remove the closed position
        # Note: _being_closed flag is removed by _remove_closed_position since it
        # sets status='closed' on the position or removes it entirely.
        _remove_closed_position(session, side, position, pos_type)

        # Record realized P&L
        session['realized_pnl'] = session.get('realized_pnl', 0) + realized_pnl
        session['close_at_5_count'] = session.get('close_at_5_count', 0) + 1
        session['updated_at'] = datetime.now(timezone.utc).isoformat()

        # Analytics: Track auto-close event (no trading logic impact)
        analytics = session.setdefault('analytics', {})
        analytics.setdefault('auto_close_events', []).append({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'side': side,
            'strike': strike,
            'lots': lots,
            'reason': 'close_at_threshold',
            'realized_pnl': realized_pnl,
        })
        analytics['auto_close_total_lots'] = analytics.get('auto_close_total_lots', 0) + lots

        log.info(
            f"Close-at-5 success: {lots} {side.upper()} @ {strike}, "
            f"realized P&L: {realized_pnl:.2f}"
        )

        return {
            'success': True,
            'realized_pnl': realized_pnl,
            'close_premium': close_price,
            'lots_closed': lots,
            'side': side,
            'strike': strike,
        }

    except Exception as e:
        # Clear in-flight flag on unexpected exception so position can be retried
        if pos_id:
            for pos in side_state.get('positions', []):
                if pos.get('id') == pos_id:
                    pos.pop('_being_closed', None)
                    break
        log.exception(f"Close-at-5 execution failed: {e}")
        return {
            'success': False,
            'error': str(e),
        }




def _remove_closed_position(
    session: Dict,
    side: str,
    position: Dict,
    pos_type: str,
):
    """
    Mark a position as closed in state.

    Fix #23: Uses ID-based O(1) lookup in positions[] when _pos_id is available.
    Falls back to content-match for pre-migration sessions or missing IDs.
    """
    side_state = session.get(side, {})
    now = datetime.now(timezone.utc).isoformat()

    pos_id = position.get('_pos_id')

    # Fix #23: Primary path — ID-based lookup in positions[] (O(1), always correct)
    if pos_id:
        found = False
        for pos in side_state.get('positions', []):
            if pos.get('id') == pos_id:
                pos['status'] = 'closed'
                pos['closed_at'] = now
                found = True
                break
        if not found:
            log.warning(
                f"Close-at-5 ID-based removal: pos_id={pos_id} not found in "
                f"positions[]. Position may already be closed."
            )
        recompute_side_lots(side_state)
        session[side] = side_state
        return

    # Fallback: content-match (Fix #8 logic for pre-migration sessions).
    # After first heartbeat recompute, _pos_id is always present.
    if pos_type == 'original':
        side_state['original_lots'] = 0
        side_state['original_premium'] = 0.0

    elif pos_type == 'adjustment':
        fills = side_state.get('adjustment_fills', [])
        target_lots = position.get('lots')
        target_prem = position.get('entry_premium', 0)
        target_strike = position.get('strike', 0)
        found = False
        for i in range(len(fills) - 1, -1, -1):
            f = fills[i]
            if (f.get('lots') == target_lots
                    and abs(f.get('premium', 0) - target_prem) < 0.01
                    and (target_strike == 0 or abs(f.get('strike', 0) - target_strike) < 1)):
                fills.pop(i)
                found = True
                break
        if not found:
            log.warning(
                f"Close-at-5 adjustment content-match failed: "
                f"lots={target_lots}, prem≈{target_prem:.2f}, strike={target_strike}. "
                f"Position may already have been removed."
            )

    elif pos_type == 'frozen':
        frozen = side_state.get('frozen_positions', [])
        target_lots = position.get('lots')
        target_prem = position.get('entry_premium', 0)
        target_strike = position.get('strike', 0)
        found = False
        for i in range(len(frozen) - 1, -1, -1):
            f = frozen[i]
            if (f.get('lots') == target_lots
                    and abs(f.get('entry_premium', 0) - target_prem) < 0.01
                    and (target_strike == 0 or abs(f.get('strike', 0) - target_strike) < 1)):
                frozen.pop(i)
                found = True
                break
        if not found:
            log.warning(
                f"Close-at-5 frozen content-match failed: "
                f"lots={target_lots}, prem≈{target_prem:.2f}, strike={target_strike}. "
                f"Position may already have been removed."
            )

    recompute_side_lots(side_state)
    session[side] = side_state


def check_side_fully_closed(session: Dict, side: str) -> bool:
    """
    §11: Check if all positions on a side have been closed.

    Returns:
        True if the side has zero total lots
    """
    side_state = session.get(side, {})
    return side_state.get('total_lots', 0) == 0


def check_both_sides_closed(session: Dict) -> bool:
    """
    §11: Check if both sides are fully closed.
    This is the BEST outcome — all sold options expired/closed worthless.

    Returns:
        True if both CE and PE have zero total lots
    """
    return (
        check_side_fully_closed(session, 'ce') and
        check_side_fully_closed(session, 'pe')
    )
