"""
MMM Strike Shift — Money Mind & Method

Handles strike shifting when hedge premium drops below shift_threshold.
Freezes current positions at the old strike and finds a new, closer strike
with sufficient premium.

Maps to MONEY_POWER_CALCULATION_LOGIC.md:
  §10: Strike Shifting

Created: February 15, 2026
"""

import logging
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime

from .mmm_state import recompute_side_lots
from .mmm_constants import strike_key as _strike_key

log = logging.getLogger('mmm_strike_shift')


def check_shift_needed(
    session: Dict,
    side: str,
    current_premium: float,
) -> bool:
    """
    §10: Check if the hedge side's premium has dropped below shift_threshold.

    Uses dynamic threshold: max(shift_threshold, hedge_entry_premium * shift_threshold_pct)
    when shift_threshold_pct > 0. This prefers fewer lots at higher premium over
    many lots at dying premium.

    Args:
        session: Full session dict
        side: 'ce' or 'pe' — the hedge side
        current_premium: Current premium at the active strike

    Returns:
        True if strike shift is needed
    """
    params = session.get('params', {})
    threshold_floor = params.get('shift_threshold', 50.0)
    threshold_pct = params.get('shift_threshold_pct', 0.0)
    
    sid = session.get('session_id', 'unknown')

    # Dynamic threshold: use hedge entry premium * pct if configured
    effective_threshold = threshold_floor
    hedge_entry_premium = 0
    
    if threshold_pct > 0:
        side_state = session.get(side, {})
        hedge_entry_premium = side_state.get('original_premium', 0)
        # If original was shifted, use latest adjustment fill premium
        if hedge_entry_premium == 0:
            fills = side_state.get('adjustment_fills', [])
            if fills:
                hedge_entry_premium = fills[-1].get('premium', 0)
        dynamic = hedge_entry_premium * threshold_pct
        effective_threshold = max(threshold_floor, dynamic)
        
        # DETAILED LOGGING for debugging
        log.info(
            f"[{sid}] 🔍 SHIFT CHECK: {side.upper()} | "
            f"Current: ${current_premium:.2f}, "
            f"Entry: ${hedge_entry_premium:.2f}, "
            f"Floor: ${threshold_floor:.2f}, "
            f"Pct: {threshold_pct:.0%}, "
            f"Dynamic: ${dynamic:.2f}, "
            f"Effective: ${effective_threshold:.2f}"
        )

    if current_premium < effective_threshold:
        log.info(
            f"[{sid}] ✅ SHIFT NEEDED: {side.upper()} premium "
            f"${current_premium:.2f} < ${effective_threshold:.2f} "
            f"(floor=${threshold_floor:.2f}, pct={threshold_pct:.0%}, entry=${hedge_entry_premium:.2f})"
        )
        return True
    else:
        log.info(
            f"[{sid}] ❌ NO SHIFT: {side.upper()} premium "
            f"${current_premium:.2f} >= ${effective_threshold:.2f} "
            f"(still above threshold)"
        )

    return False


def freeze_current_positions(
    session: Dict,
    side: str,
) -> Dict[str, Any]:
    """
    §10: Freeze all active positions at the current strike.

    Move original lots + adjustment fills → frozen_positions.
    Clear adjustment_fills at the old strike.

    Args:
        session: Full session dict (mutated in place)
        side: 'ce' or 'pe'

    Returns:
        {frozen_lots, old_strike, frozen_entry}
    """
    side_state = session.get(side, {})
    old_strike = side_state.get('active_strike', 0)
    original_lots = side_state.get('original_lots', 0)
    original_premium = side_state.get('original_premium', 0)

    frozen_lots = 0

    # Freeze original lots
    if original_lots > 0:
        side_state.setdefault('frozen_positions', []).append({
            'strike': old_strike,
            'lots': original_lots,
            'entry_premium': original_premium,
            'type': 'original',
            'frozen_at': datetime.utcnow().isoformat(),
        })
        frozen_lots += original_lots

    # Freeze adjustment fills
    for fill in side_state.get('adjustment_fills', []):
        lots = fill.get('lots', 0)
        prem = fill.get('premium', 0)
        if lots > 0:
            side_state['frozen_positions'].append({
                'strike': old_strike,
                'lots': lots,
                'entry_premium': prem,
                'type': 'adjustment',
                'frozen_at': datetime.utcnow().isoformat(),
            })
            frozen_lots += lots

    # Reset active — these will be re-established at the new strike
    side_state['adjustment_fills'] = []
    side_state['original_lots'] = 0
    side_state['original_premium'] = 0.0

    recompute_side_lots(side_state)
    session[side] = side_state

    log.info(
        f"Frozen {frozen_lots} lots at strike {old_strike} "
        f"for {side.upper()}"
    )

    return {
        'frozen_lots': frozen_lots,
        'old_strike': old_strike,
    }


def find_new_strike(
    initializer,
    session: Dict,
    side: str,
    spot_price: float,
) -> Optional[Dict[str, Any]]:
    """
    §10: Scan the chain for a new strike closer to spot with premium >= threshold.

    For CE (calls): Find OTM call with strike > spot, premium >= threshold
    For PE (puts): Find OTM put with strike < spot, premium >= threshold

    Args:
        initializer: MMMInitializer instance for chain access
        session: Full session dict
        side: 'ce' or 'pe'
        spot_price: Current BTC spot price

    Returns:
        {strike, premium, symbol} or None if no suitable strike found
    """
    params = session.get('params', {})
    threshold_floor = params.get('shift_threshold', 50.0)
    threshold_pct = params.get('shift_threshold_pct', 0.0)
    expiry = params.get('expiry', '')

    # Dynamic threshold for candidate filtering
    effective_threshold = threshold_floor
    if threshold_pct > 0:
        side_state = session.get(side, {})
        hedge_entry_premium = side_state.get('original_premium', 0)
        if hedge_entry_premium == 0:
            fills = side_state.get('adjustment_fills', [])
            if fills:
                hedge_entry_premium = fills[-1].get('premium', 0)
        effective_threshold = max(threshold_floor, hedge_entry_premium * threshold_pct)

    if not expiry:
        log.error("No expiry set in session params")
        return None

    try:
        chain_result = initializer.get_full_chain(expiry)
        if not chain_result or not chain_result.get('success'):
            log.error("Failed to fetch chain data for strike shift")
            return None

        chain_list = chain_result.get('chain', [])
        if not chain_list:
            log.error("Empty chain data for strike shift")
            return None

        option_type = 'call' if side == 'ce' else 'put'
        candidates = []
        old_strike = session.get(side, {}).get('active_strike', 0)

        for row in chain_list:
            strike = row.get('strike', 0)
            option_data = row.get(option_type, {})
            if not option_data:
                continue

            bid = float(option_data.get('bid', 0) or 0)
            mark = float(option_data.get('mark_price', 0) or 0)
            symbol = option_data.get('symbol', '')

            # Use bid for selling (§15.5)
            premium = bid if bid > 0 else mark

            if premium < effective_threshold:
                continue

            # Must be OTM
            if option_type == 'call' and strike <= spot_price:
                continue
            if option_type == 'put' and strike >= spot_price:
                continue

            # Don't re-select the current active strike
            if abs(strike - old_strike) < 1:
                continue

            candidates.append({
                'strike': strike,
                'premium': premium,
                'symbol': symbol,
                'distance_from_spot': abs(strike - spot_price),
            })

        if not candidates:
            log.warning(
                f"No suitable strike found for {side.upper()} shift "
                f"(effective_threshold={effective_threshold})"
            )
            return None

        # §10 FIX: Sort by proximity to shift_target_premium (default 100)
        # This ensures we pick an OTM strike with manageable premium,
        # NOT the closest-to-spot (which can be near-ATM with 500+ premium)
        target_premium = params.get('shift_target_premium', 100.0)

        candidates.sort(key=lambda c: abs(c['premium'] - target_premium))

        best = candidates[0]
        log.info(
            f"Found new strike for {side.upper()}: "
            f"{best['strike']} @ {best['premium']:.2f} "
            f"(target premium: {target_premium:.2f})"
        )
        return best

    except Exception as e:
        log.exception(f"Error finding new strike: {e}")
        return None


def activate_new_strike(
    session: Dict,
    side: str,
    new_strike: float,
    fill_premium: float,
    lots: int,
) -> Dict:
    """
    Set the new active strike after a shift.

    Args:
        session: Full session dict (mutated in place)
        side: 'ce' or 'pe'
        new_strike: The new strike price
        fill_premium: Premium obtained from selling at new strike
        lots: Number of lots sold at new strike

    Returns:
        Updated session
    """
    side_state = session.get(side, {})

    side_state['active_strike'] = new_strike

    # FIX: Update symbol to match the new active strike.
    # Without this, reconciliation checks the stale original symbol,
    # making exchange positions at the current strike invisible.
    # Build symbol from the new strike + session expiry.
    expiry = session.get('params', {}).get('expiry', '')
    option_type = 'call' if side == 'ce' else 'put'
    from .mmm_initializer import MMMInitializer
    try:
        _init = MMMInitializer()
        side_state['symbol'] = _init.build_symbol(option_type, 'BTC', new_strike, expiry)
        log.info(f"Symbol updated for {side.upper()}: {side_state['symbol']}")
    except Exception as e:
        log.warning(f"Failed to update symbol for {side.upper()} shift: {e}")

    # FIX: Shifted positions are adjustments, not original entry.
    # This ensures calculate_reversal_loss() includes them in risk assessment.
    side_state['original_lots'] = 0
    side_state['original_premium'] = 0.0

    side_state.setdefault('adjustment_fills', []).append({
        'lots': lots,
        'premium': fill_premium,
        'strike': new_strike,
        'timestamp': datetime.utcnow().isoformat(),
        'type': 'strike_shift',
    })

    # Set trigger snapshot at the new strike
    side_state.setdefault('trigger_snapshot', {})[_strike_key(new_strike)] = fill_premium

    recompute_side_lots(side_state)
    session[side] = side_state

    # NOTE: shift_count is incremented by _process_strike_shift() in mmm_monitor.py
    # Do NOT increment here to avoid double-counting.
    session['updated_at'] = datetime.utcnow().isoformat()

    log.info(
        f"Strike shift complete: {side.upper()} now active at "
        f"{new_strike} with {lots} lots @ {fill_premium:.2f}"
    )

    return session
