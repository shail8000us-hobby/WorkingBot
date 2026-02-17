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
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from .mmm_state import recompute_side_lots
from .mmm_constants import LOT_SIZE_BTC

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

        # Check original lots at active strike
        orig_lots = side_state.get('original_lots', 0)
        orig_prem = side_state.get('original_premium', 0)
        if orig_lots > 0 and active_strike > 0:
            try:
                current = fetch_premium_fn(active_strike, option_type)
                if current <= threshold:
                    profit = (orig_prem - current) * orig_lots
                    closeable.append({
                        'side': side_key,
                        'strike': active_strike,
                        'lots': orig_lots,
                        'entry_premium': orig_prem,
                        'current_premium': current,
                        'type': 'original',
                        'profit': profit,
                    })
            except Exception as e:
                log.warning(f"Error fetching {side_key} original premium: {e}")

        # Check adjustment fills at active strike
        for i, fill in enumerate(side_state.get('adjustment_fills', [])):
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
                            'fill_index': i,
                            'profit': profit,
                        })
                except Exception as e:
                    log.warning(f"Error fetching adj fill premium: {e}")

        # Check frozen positions
        for i, frozen in enumerate(side_state.get('frozen_positions', [])):
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
                            'frozen_index': i,
                            'profit': profit,
                        })
                except Exception as e:
                    log.warning(f"Error fetching frozen premium: {e}")

    if closeable:
        log.info(
            f"Found {len(closeable)} position(s) eligible for close-at-5"
        )
        # Bug #4 fix: sort by (side, type, index) descending so that
        # higher indices within the SAME array are popped first,
        # preserving correctness of lower indices.
        _type_order = {'frozen': 2, 'adjustment': 1, 'original': 0}
        closeable.sort(
            key=lambda p: (
                p.get('side', ''),
                _type_order.get(p.get('type', ''), -1),
                p.get('frozen_index', p.get('fill_index', -1)),
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
    """
    side = position['side']
    strike = position['strike']
    lots = position['lots']
    entry_prem = position['entry_premium']
    pos_type = position['type']

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
            return {
                'success': False,
                'error': result.get('error', 'Buy-back not filled'),
            }

        close_price = result.get('fill_price', 0)
        realized_pnl = (entry_prem - close_price) * lots * LOT_SIZE_BTC

        # Update state: remove the closed position
        _remove_closed_position(session, side, position, pos_type)

        # Record realized P&L
        session['realized_pnl'] = session.get('realized_pnl', 0) + realized_pnl
        session['close_at_5_count'] = session.get('close_at_5_count', 0) + 1
        session['updated_at'] = datetime.utcnow().isoformat()

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
    """Remove a closed position from state."""
    side_state = session.get(side, {})

    if pos_type == 'original':
        side_state['original_lots'] = 0
        side_state['original_premium'] = 0.0

    elif pos_type == 'adjustment':
        idx = position.get('fill_index')
        fills = side_state.get('adjustment_fills', [])
        if idx is not None and 0 <= idx < len(fills):
            # Bug #4 fix: verify the fill matches before popping
            target = fills[idx]
            if (target.get('lots') == position.get('lots')
                    and abs(target.get('premium', 0) - position.get('entry_premium', 0)) < 0.01):
                fills.pop(idx)
            else:
                # Index shifted — find by content match
                log.warning(f"Fill index {idx} mismatch, searching by content")
                for i in range(len(fills) - 1, -1, -1):
                    f = fills[i]
                    if (f.get('lots') == position.get('lots')
                            and abs(f.get('premium', 0) - position.get('entry_premium', 0)) < 0.01):
                        fills.pop(i)
                        break

    elif pos_type == 'frozen':
        idx = position.get('frozen_index')
        frozen = side_state.get('frozen_positions', [])
        if idx is not None and 0 <= idx < len(frozen):
            # Bug #4 fix: verify frozen matches before popping
            target = frozen[idx]
            if (target.get('lots') == position.get('lots')
                    and abs(target.get('entry_premium', 0) - position.get('entry_premium', 0)) < 0.01):
                frozen.pop(idx)
            else:
                log.warning(f"Frozen index {idx} mismatch, searching by content")
                for i in range(len(frozen) - 1, -1, -1):
                    f = frozen[i]
                    if (f.get('lots') == position.get('lots')
                            and abs(f.get('entry_premium', 0) - position.get('entry_premium', 0)) < 0.01):
                        frozen.pop(i)
                        break

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
