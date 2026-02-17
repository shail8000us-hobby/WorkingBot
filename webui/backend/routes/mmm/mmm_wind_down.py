"""
MMM Wind-Down Mode — Money Mind & Method

Near expiry (or after a user-defined cutoff), the algo switches from
"sell more to hedge" to "buy back to reduce". This shrinks the position
book as expiry approaches, arriving at expiry with minimal or zero exposure.

Wind-down mode changes the response to a trigger:
  Normal mode:  aggressor triggers → SELL more of hedge side (grow book)
  Wind-down:    aggressor triggers → BUY BACK some of aggressor side (shrink book)

Additionally, during wind-down the close-at-threshold is elevated (e.g. from 5 to 20)
to opportunistically harvest near-max profits before expiry volatility can reverse them.

Created: February 17, 2026
"""

import logging
import math
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

log = logging.getLogger('mmm_wind_down')

# Lot size constant (same as mmm_engine)
LOT_SIZE_BTC = 0.001


def is_wind_down_active(session: Dict) -> bool:
    """
    Check if wind-down mode should be active based on session params.

    Activation logic:
    1. wind_down_enabled must be True
    2. wind_down_hours_before_expiry > 0: activate if hours_to_expiry <= value
       (0 = disabled / manual-only via wind_down_enabled toggle)

    Returns:
        True if wind-down should be active
    """
    params = session.get('params', {})

    if not params.get('wind_down_enabled', False):
        return False

    wd_hours = params.get('wind_down_hours_before_expiry', 0)

    if wd_hours > 0:
        # Time-based activation
        expiry_str = params.get('expiry', '')
        if not expiry_str:
            return False

        try:
            # Parse expiry — handle multiple formats
            expiry_dt = _parse_expiry(expiry_str)
            now = datetime.utcnow()
            hours_remaining = (expiry_dt - now).total_seconds() / 3600.0

            if hours_remaining <= wd_hours:
                return True
            return False
        except Exception as e:
            log.warning(f"Wind-down: failed to parse expiry '{expiry_str}': {e}")
            return False

    # wind_down_enabled is True but no hours threshold → always active
    # (user manually toggled it on via WebUI)
    return True


def _parse_expiry(expiry_str: str) -> datetime:
    """Parse expiry string into datetime (UTC)."""
    # Try ISO format first
    for fmt in [
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%S.%fZ',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d',
    ]:
        try:
            return datetime.strptime(expiry_str.strip(), fmt)
        except ValueError:
            continue

    raise ValueError(f"Cannot parse expiry: {expiry_str}")


def compute_wind_down_action(
    session: Dict,
    aggressor_side: str,
    ce_now: float,
    pe_now: float,
) -> Dict[str, Any]:
    """
    Compute the wind-down buy-back action for a triggered aggressor.

    Instead of selling more of the hedge side, buy back a fraction
    of the aggressor side's lots to reduce exposure.

    Uses LIFO (close newest first) — removes the most expensive/risky
    adjustment fills before original positions.

    Args:
        session: Full session dict
        aggressor_side: 'ce' or 'pe' — the side that triggered
        ce_now: Current CE premium
        pe_now: Current PE premium

    Returns:
        {
            action: 'buyback' | 'skip' | 'normal' | 'pause',
            lots_to_close: int,
            side: str,            # 'ce' or 'pe'
            reason: str,
            at_floor: bool,       # True if at min_lots_to_keep
        }
    """
    params = session.get('params', {})
    buyback_pct = params.get('wind_down_buyback_pct', 0.25)
    min_keep = params.get('wind_down_min_lots_to_keep', 0)
    floor_action = params.get('wind_down_floor_action', 'skip')

    side_state = session.get(aggressor_side, {})
    active_lots = side_state.get('active_lots', 0)

    # How many lots are available to close (above the floor)?
    available = active_lots - min_keep

    if available <= 0:
        # At floor — decide based on floor_action param
        log.info(
            f"Wind-down: {aggressor_side.upper()} at floor "
            f"({active_lots} lots, min_keep={min_keep}). "
            f"Action: {floor_action}"
        )
        return {
            'action': floor_action,  # 'skip', 'normal', or 'pause'
            'lots_to_close': 0,
            'side': aggressor_side,
            'reason': (
                f'{aggressor_side.upper()} at minimum lots '
                f'({active_lots}/{min_keep})'
            ),
            'at_floor': True,
        }

    # Calculate lots to buy back
    lots_to_close = max(1, math.floor(available * buyback_pct))

    # Never close more than available
    lots_to_close = min(lots_to_close, available)

    log.info(
        f"Wind-down buyback: {aggressor_side.upper()} "
        f"close {lots_to_close}/{active_lots} lots "
        f"({buyback_pct*100:.0f}% of {available} available, "
        f"keeping ≥{min_keep})"
    )

    return {
        'action': 'buyback',
        'lots_to_close': lots_to_close,
        'side': aggressor_side,
        'reason': (
            f'Wind-down: buy back {lots_to_close} '
            f'{aggressor_side.upper()} lots '
            f'({buyback_pct*100:.0f}% of available)'
        ),
        'at_floor': False,
    }


def get_lifo_close_fills(
    side_state: Dict,
    lots_to_close: int,
) -> List[Dict]:
    """
    Determine which fills to close in LIFO order (newest adjustment first).

    Returns a list of {lots, premium, strike, source} describing which
    fills are consumed. Newest adjustment fills are consumed first,
    then original lots as last resort.

    Args:
        side_state: Session side state (ce or pe dict)
        lots_to_close: Number of lots to buy back

    Returns:
        List of fill records to close
    """
    remaining = lots_to_close
    close_records = []

    # 1. Close adjustment fills in reverse order (LIFO — newest first)
    adj_fills = list(side_state.get('adjustment_fills', []))
    for i in range(len(adj_fills) - 1, -1, -1):
        if remaining <= 0:
            break
        fill = adj_fills[i]
        fill_lots = fill.get('lots', 0)
        if fill_lots <= 0:
            continue

        close_from_this = min(remaining, fill_lots)
        close_records.append({
            'lots': close_from_this,
            'premium': fill.get('premium', 0),
            'strike': fill.get('strike', 0),
            'source': 'adjustment',
            'fill_index': i,
        })
        remaining -= close_from_this

    # 2. If still need more, close from original lots (last resort)
    if remaining > 0:
        orig_lots = side_state.get('original_lots', 0)
        if orig_lots > 0:
            close_from_orig = min(remaining, orig_lots)
            close_records.append({
                'lots': close_from_orig,
                'premium': side_state.get('original_premium', 0),
                'strike': side_state.get('active_strike', 0),
                'source': 'original',
                'fill_index': -1,
            })
            remaining -= close_from_orig

    return close_records


def apply_lifo_removals(
    side_state: Dict,
    close_records: List[Dict],
) -> float:
    """
    Remove lots from side_state based on LIFO close records.

    Mutates side_state in place: reduces adjustment_fills lots and
    original_lots as needed.

    Args:
        side_state: Session side state (mutated)
        close_records: From get_lifo_close_fills()

    Returns:
        Weighted average entry premium of closed lots
    """
    total_lots_closed = 0
    weighted_premium_sum = 0.0

    for record in close_records:
        lots = record['lots']
        premium = record['premium']
        weighted_premium_sum += premium * lots
        total_lots_closed += lots

        if record['source'] == 'adjustment':
            idx = record['fill_index']
            adj_fills = side_state.get('adjustment_fills', [])
            if 0 <= idx < len(adj_fills):
                adj_fills[idx]['lots'] -= lots
                if adj_fills[idx]['lots'] <= 0:
                    adj_fills[idx]['lots'] = 0  # Will be cleaned up below

        elif record['source'] == 'original':
            side_state['original_lots'] = max(
                0, side_state.get('original_lots', 0) - lots
            )

    # Clean up zero-lot adjustment fills
    adj_fills = side_state.get('adjustment_fills', [])
    side_state['adjustment_fills'] = [f for f in adj_fills if f.get('lots', 0) > 0]

    # Recompute derived lots
    from .mmm_state import recompute_side_lots
    recompute_side_lots(side_state)

    avg_entry = weighted_premium_sum / total_lots_closed if total_lots_closed > 0 else 0
    return avg_entry


def get_wind_down_close_threshold(session: Dict) -> float:
    """
    During wind-down, return the elevated close threshold.

    Falls back to normal close_at_threshold if wind-down is not active.
    """
    params = session.get('params', {})

    if is_wind_down_active(session):
        return params.get('wind_down_close_threshold', 20.0)

    return params.get('close_at_threshold', 5.0)
