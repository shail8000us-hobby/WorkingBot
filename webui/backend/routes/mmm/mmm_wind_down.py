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
from datetime import datetime, timezone
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
    3. wind_down_on_atm: activates when original strike goes ATM (set via
       _atm_wind_down_triggered session flag by the monitor heartbeat)

    Returns:
        True if wind-down should be active
    """
    params = session.get('params', {})

    # Master switch: wind_down_enabled must be True for ANY wind-down path.
    # Previously, wind_down_on_atm bypassed this check, which was a bug —
    # users would disable wind-down via the master switch but ATM trigger
    # would still activate it silently.
    if not params.get('wind_down_enabled', False):
        return False

    # ATM-triggered wind-down: if wind_down_on_atm is enabled AND wind_down_enabled
    # is True AND the monitor detected an original strike going ATM.
    if params.get('wind_down_on_atm', False) and session.get('_atm_wind_down_triggered', False):
        return True

    wd_hours = params.get('wind_down_hours_before_expiry', 0)

    if wd_hours > 0:
        # Time-based activation
        expiry_str = params.get('expiry', '')
        if not expiry_str:
            return False

        try:
            # Use canonical expiry parser: DDMMYYYY → 5:30 PM IST (12:00 UTC)
            from .mmm_initializer import expiry_to_utc_datetime
            expiry_iso = expiry_to_utc_datetime(expiry_str)
            expiry_dt = datetime.fromisoformat(expiry_iso)
            # Robust v2 Fix #14: Use timezone-aware UTC
            now = datetime.now(timezone.utc)
            # Make expiry_dt timezone-aware if it isn't already
            if expiry_dt.tzinfo is None:
                expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
            hours_remaining = (expiry_dt - now).total_seconds() / 3600.0

            if hours_remaining <= wd_hours:
                return True
            return False
        except Exception as e:
            log.warning(f"Wind-down: failed to parse expiry '{expiry_str}': {e}")
            return False

    # wind_down_enabled is True but no hours threshold → always active
    # (user manually toggled it on via WebUI with hours=0)
    return True


def get_wind_down_status(session: Dict) -> Dict[str, Any]:
    """
    Return detailed wind-down status for logging and heartbeat emission.

    Returns:
        {
            'active': bool,
            'enabled': bool,
            'hours_before_expiry': float,
            'hours_remaining': float | None,   # None if no expiry or hours=0
            'activates_in_hours': float | None, # None if already active or no time gate
        }
    """
    params = session.get('params', {})
    enabled = params.get('wind_down_enabled', False)
    wd_hours = params.get('wind_down_hours_before_expiry', 0)

    if not enabled:
        return {'active': False, 'enabled': False, 'hours_before_expiry': wd_hours,
                'hours_remaining': None, 'activates_in_hours': None}

    if wd_hours <= 0:
        return {'active': True, 'enabled': True, 'hours_before_expiry': 0,
                'hours_remaining': None, 'activates_in_hours': None}

    expiry_str = params.get('expiry', '')
    if not expiry_str:
        return {'active': False, 'enabled': True, 'hours_before_expiry': wd_hours,
                'hours_remaining': None, 'activates_in_hours': None}

    try:
        from .mmm_initializer import expiry_to_utc_datetime
        expiry_iso = expiry_to_utc_datetime(expiry_str)
        expiry_dt = datetime.fromisoformat(expiry_iso)
        # Robust v2 Fix #14: Use timezone-aware UTC
        now = datetime.now(timezone.utc)
        # Make expiry_dt timezone-aware if it isn't already
        if expiry_dt.tzinfo is None:
            expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
        hours_remaining = (expiry_dt - now).total_seconds() / 3600.0
        active = hours_remaining <= wd_hours
        activates_in = max(0.0, hours_remaining - wd_hours) if not active else None
        return {
            'active': active,
            'enabled': True,
            'hours_before_expiry': wd_hours,
            'hours_remaining': round(hours_remaining, 2),
            'activates_in_hours': round(activates_in, 2) if activates_in is not None else None,
        }
    except Exception as e:
        log.warning(f"Wind-down status: failed to parse expiry '{expiry_str}': {e}")
        return {'active': False, 'enabled': True, 'hours_before_expiry': wd_hours,
                'hours_remaining': None, 'activates_in_hours': None}


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

    # Fix #23: Read from positions[] (Unified Ledger) for LIFO order.
    # Active positions sorted newest-first (by created_at, fallback to list reverse)
    from .mmm_state import _migrate_side_to_positions
    if 'positions' not in side_state:
        _migrate_side_to_positions(side_state)

    active_positions = [
        p for p in side_state.get('positions', [])
        if p.get('status') == 'active'
    ]

    # LIFO: non-original first (adjustments/shift_entries), then original last resort
    non_orig = [p for p in active_positions if p.get('type') != 'original']
    orig_list = [p for p in active_positions if p.get('type') == 'original']

    for pos in reversed(non_orig):   # newest-first (preserve list insertion order)
        if remaining <= 0:
            break
        pos_lots = pos.get('lots', 0)
        if pos_lots <= 0:
            continue
        close_from_this = min(remaining, pos_lots)
        close_records.append({
            'lots': close_from_this,
            'premium': pos.get('entry_premium', pos.get('premium', 0)),
            'strike': pos['strike'],
            'source': 'adjustment',
            '_pos_id': pos['id'],   # Fix #23: ID-based removal
        })
        remaining -= close_from_this

    for pos in orig_list:   # CRITICAL: use original_strike, not active_strike
        if remaining <= 0:
            break
        pos_lots = pos.get('lots', 0)
        if pos_lots <= 0:
            continue
        close_from_orig = min(remaining, pos_lots)
        close_records.append({
            'lots': close_from_orig,
            'premium': pos.get('entry_premium', pos.get('premium', 0)),
            'strike': pos['strike'],
            'source': 'original',
            '_pos_id': pos['id'],   # Fix #23: ID-based removal
        })
        remaining -= close_from_orig

    return close_records


def apply_lifo_removals(
    side_state: Dict,
    close_records: List[Dict],
) -> float:
    """
    Apply LIFO lot reductions to side_state based on close records.

    Fix #23: Uses ID-based lookup in positions[] (Unified Ledger).
    Fully closes positions whose lots reach 0; partially reduces others.

    Args:
        side_state: Session side state (mutated in place)
        close_records: From get_lifo_close_fills()

    Returns:
        Weighted average entry premium of closed lots
    """
    from datetime import datetime, timezone
    from .mmm_state import recompute_side_lots

    total_lots_closed = 0
    weighted_premium_sum = 0.0
    now = datetime.now(timezone.utc).isoformat()

    positions = side_state.get('positions', [])
    pos_index = {p['id']: p for p in positions}   # O(1) lookup by ID

    for record in close_records:
        lots = record['lots']
        premium = record['premium']
        weighted_premium_sum += premium * lots
        total_lots_closed += lots

        pos_id = record.get('_pos_id')
        if pos_id and pos_id in pos_index:
            pos = pos_index[pos_id]
            pos['lots'] = max(0, pos['lots'] - lots)
            if pos['lots'] == 0:
                pos['status'] = 'closed'
                pos['closed_at'] = now

    # Recompute derived views and scalars from updated positions[]
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
