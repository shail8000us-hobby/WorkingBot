"""
IC Strike Selector — Iron Condor Entry Logic

Selects the 4 strikes for an iron condor entry:
  1. Short Put (SP) — OTM put at target delta
  2. Long Put (LP) — further OTM put (wing)
  3. Short Call (SC) — OTM call at target delta
  4. Long Call (LC) — further OTM call (wing)

From IC_ALGO_PLAN.md §7.

Created: 2026-03-24
"""

import logging
from typing import Dict, List, Optional, Tuple

from .ic_constants import LEG_SP, LEG_LP, LEG_SC, LEG_LC
from .ic_state import create_leg_state

log = logging.getLogger('ic_strike_selector')


def select_strikes(
    spot_price: float,
    available_puts: List[Dict],
    available_calls: List[Dict],
    params: Dict,
) -> Optional[Dict]:
    """
    Select all 4 strikes for an iron condor.

    §7.1 Algorithm:
      1. SP: put strike where |delta| ≈ short_put_delta_target
      2. LP: nearest available strike at or beyond (SP - wing_width_usd)
      3. SC: call strike where |delta| ≈ short_call_delta_target
      4. LC: nearest available strike at or beyond (SC + wing_width_usd)
      5. Validate: LP < SP < spot < SC < LC

    Args:
        spot_price: Current BTC spot price
        available_puts: List of {strike, delta, bid, ask, premium, symbol}
                        sorted by strike ascending
        available_calls: List of {strike, delta, bid, ask, premium, symbol}
                         sorted by strike ascending
        params: Session parameters

    Returns:
        Dict with keys SP, LP, SC, LC, each containing leg state,
        or None if valid selection not found
    """
    if not available_puts or not available_calls:
        log.warning("No available strikes — cannot select IC legs")
        return None

    put_delta_target = params.get('short_put_delta_target', 0.16)
    call_delta_target = params.get('short_call_delta_target', 0.16)
    wing_width_usd = params.get('wing_width_usd', 1000)
    lots = params.get('lots', 10)
    min_credit = params.get('min_net_credit_per_btc', 10.0)
    min_credit_ratio = params.get('min_credit_to_wing_ratio', 0.03)

    # Step 1: Select Short Put (using delta)
    sp_data = _select_by_delta(
        strikes=[s for s in available_puts if s['strike'] < spot_price],
        target_delta=put_delta_target,
        option_type='put',
    )
    if not sp_data:
        log.warning("Could not find suitable short put strike")
        return None

    # Step 2: Select Long Put (wing)
    lp_target = sp_data['strike'] - wing_width_usd
    lp_data = _select_wing_strike(
        strikes=[s for s in available_puts if s['strike'] < sp_data['strike']],
        target_strike=lp_target,
        direction='below',
    )
    if not lp_data:
        log.warning("Could not find suitable long put (wing) strike")
        return None

    # Step 3: Select Short Call (using delta)
    sc_data = _select_by_delta(
        strikes=[s for s in available_calls if s['strike'] > spot_price],
        target_delta=call_delta_target,
        option_type='call',
    )
    if not sc_data:
        log.warning("Could not find suitable short call strike")
        return None

    # Step 4: Select Long Call (wing)
    lc_target = sc_data['strike'] + wing_width_usd
    lc_data = _select_wing_strike(
        strikes=[s for s in available_calls if s['strike'] > sc_data['strike']],
        target_strike=lc_target,
        direction='above',
    )
    if not lc_data:
        log.warning("Could not find suitable long call (wing) strike")
        return None

    # Step 5: Validate strict ordering LP < SP < spot < SC < LC
    if not (lp_data['strike'] < sp_data['strike'] < spot_price <
            sc_data['strike'] < lc_data['strike']):
        log.warning(
            f"Invalid strike ordering: LP={lp_data['strike']}, SP={sp_data['strike']}, "
            f"spot={spot_price}, SC={sc_data['strike']}, LC={lc_data['strike']}"
        )
        return None

    # Compute estimated net credit
    sp_premium = sp_data.get('bid', sp_data.get('premium', 0))
    lp_premium = lp_data.get('ask', lp_data.get('premium', 0))
    sc_premium = sc_data.get('bid', sc_data.get('premium', 0))
    lc_premium = lc_data.get('ask', lc_data.get('premium', 0))

    net_credit = (sp_premium + sc_premium) - (lp_premium + lc_premium)

    # Validate: net credit must be positive
    if net_credit <= 0:
        log.warning(f"Net credit ${net_credit:.2f}/BTC is <= 0 — rejecting entry")
        return None

    # Validate: minimum net credit
    if net_credit < min_credit:
        log.warning(
            f"Net credit ${net_credit:.2f}/BTC below minimum ${min_credit} — skipping entry"
        )
        return None

    # Validate: credit-to-wing ratio
    actual_wing = max(
        sp_data['strike'] - lp_data['strike'],
        lc_data['strike'] - sc_data['strike'],
    )
    if actual_wing > 0:
        ratio = net_credit / actual_wing
        if ratio < min_credit_ratio:
            log.warning(
                f"Credit/wing ratio {ratio:.4f} below minimum {min_credit_ratio} — "
                f"skipping entry (bad risk:reward)"
            )
            return None

    # Build leg states
    legs = {
        LEG_SP: create_leg_state(
            leg_key=LEG_SP, strike=sp_data['strike'], lots=lots,
            side='put', action='sell', entry_premium=sp_premium,
        ),
        LEG_LP: create_leg_state(
            leg_key=LEG_LP, strike=lp_data['strike'], lots=lots,
            side='put', action='buy', entry_premium=lp_premium,
        ),
        LEG_SC: create_leg_state(
            leg_key=LEG_SC, strike=sc_data['strike'], lots=lots,
            side='call', action='sell', entry_premium=sc_premium,
        ),
        LEG_LC: create_leg_state(
            leg_key=LEG_LC, strike=lc_data['strike'], lots=lots,
            side='call', action='buy', entry_premium=lc_premium,
        ),
    }

    # Store product symbols for order placement
    for leg_key, strike_data in [(LEG_SP, sp_data), (LEG_LP, lp_data),
                                  (LEG_SC, sc_data), (LEG_LC, lc_data)]:
        if 'symbol' in strike_data:
            legs[leg_key]['product_symbol'] = strike_data['symbol']

    log.info(
        f"Selected IC strikes: LP={lp_data['strike']}, SP={sp_data['strike']}, "
        f"SC={sc_data['strike']}, LC={lc_data['strike']} — "
        f"net credit ${net_credit:.2f}/BTC"
    )

    return legs


def _select_by_delta(
    strikes: List[Dict],
    target_delta: float,
    option_type: str,
) -> Optional[Dict]:
    """
    Select the strike with |delta| closest to target_delta.

    For puts: delta is negative, so we compare abs(delta)
    For calls: delta is positive, so we use abs(delta)
    """
    if not strikes:
        return None

    best = None
    best_diff = float('inf')

    for s in strikes:
        delta = abs(s.get('delta', 0.0) or 0.0)
        diff = abs(delta - target_delta)
        if diff < best_diff:
            best_diff = diff
            best = s

    return best


def _select_wing_strike(
    strikes: List[Dict],
    target_strike: float,
    direction: str,  # 'above' or 'below'
) -> Optional[Dict]:
    """
    Select the nearest available strike at or beyond the target wing distance.

    For LP (below SP): target = SP - wing_width, pick nearest available <= target
    For LC (above SC): target = SC + wing_width, pick nearest available >= target
    """
    if not strikes:
        return None

    if direction == 'below':
        # Find nearest strike <= target_strike
        candidates = [s for s in strikes if s['strike'] <= target_strike]
        if not candidates:
            # No strike far enough — use the furthest available
            return min(strikes, key=lambda s: s['strike']) if strikes else None
        return max(candidates, key=lambda s: s['strike'])

    elif direction == 'above':
        # Find nearest strike >= target_strike
        candidates = [s for s in strikes if s['strike'] >= target_strike]
        if not candidates:
            # No strike far enough — use the furthest available
            return max(strikes, key=lambda s: s['strike']) if strikes else None
        return min(candidates, key=lambda s: s['strike'])

    return None


def select_new_strikes_for_roll(
    spot_price: float,
    available_strikes: List[Dict],
    side: str,  # 'call' or 'put'
    wing_width_usd: float,
    delta_target: float,
    lots: int,
) -> Optional[Tuple[Dict, Dict]]:
    """
    Select new short + long strikes for a roll.

    After a roll, new strikes are re-centered around current spot,
    using the same delta targeting as entry.

    Args:
        side: 'call' or 'put'
        available_strikes: Available option strikes for this side

    Returns:
        (new_short_data, new_long_data) or None
    """
    if not available_strikes:
        return None

    if side == 'call':
        # New short call above spot
        candidates = [s for s in available_strikes if s['strike'] > spot_price]
        short_data = _select_by_delta(candidates, delta_target, 'call')
        if not short_data:
            return None

        # New long call = short + wing_width
        lc_target = short_data['strike'] + wing_width_usd
        long_candidates = [s for s in available_strikes if s['strike'] > short_data['strike']]
        long_data = _select_wing_strike(long_candidates, lc_target, 'above')
        if not long_data:
            return None

    elif side == 'put':
        # New short put below spot
        candidates = [s for s in available_strikes if s['strike'] < spot_price]
        short_data = _select_by_delta(candidates, delta_target, 'put')
        if not short_data:
            return None

        # New long put = short - wing_width
        lp_target = short_data['strike'] - wing_width_usd
        long_candidates = [s for s in available_strikes if s['strike'] < short_data['strike']]
        long_data = _select_wing_strike(long_candidates, lp_target, 'below')
        if not long_data:
            return None

    else:
        return None

    return short_data, long_data
