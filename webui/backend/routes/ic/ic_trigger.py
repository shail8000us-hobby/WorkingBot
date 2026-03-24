"""
IC Trigger — Iron Condor Breach Detection

Detects when BTC spot price approaches short strikes,
signaling that adjustment (rolling) is needed.

From IC_ALGO_PLAN.md §9.1 and §6.2.

Created: 2026-03-24
"""

import logging
from typing import Dict, Tuple, Optional

log = logging.getLogger('ic_trigger')


def is_call_side_threatened(spot: float, sc_strike: float, breach_pct: float) -> bool:
    """
    Check if the call side is threatened.

    §9.1: distance_pct = (SC - spot) / spot × 100
           Threatened if distance_pct <= breach_pct

    Args:
        spot: Current BTC spot price
        sc_strike: Short call strike price
        breach_pct: Breach threshold in percent (e.g., 5.0)

    Returns:
        True if spot is dangerously close to short call
    """
    if spot <= 0 or sc_strike <= 0:
        return False
    distance_pct = (sc_strike - spot) / spot * 100
    return distance_pct <= breach_pct


def is_put_side_threatened(spot: float, sp_strike: float, breach_pct: float) -> bool:
    """
    Check if the put side is threatened.

    §9.1: distance_pct = (spot - SP) / spot × 100
           Threatened if distance_pct <= breach_pct

    Args:
        spot: Current BTC spot price
        sp_strike: Short put strike price
        breach_pct: Breach threshold in percent (e.g., 5.0)

    Returns:
        True if spot is dangerously close to short put
    """
    if spot <= 0 or sp_strike <= 0:
        return False
    distance_pct = (spot - sp_strike) / spot * 100
    return distance_pct <= breach_pct


def get_breach_status(
    spot: float,
    sp_strike: float,
    sc_strike: float,
    breach_pct: float,
) -> Tuple[bool, bool, str]:
    """
    Evaluate breach status for both sides.

    Returns:
        (call_threatened, put_threatened, breach_type)
        breach_type: 'none' | 'call' | 'put' | 'both'
    """
    call = is_call_side_threatened(spot, sc_strike, breach_pct)
    put = is_put_side_threatened(spot, sp_strike, breach_pct)

    if call and put:
        return call, put, 'both'
    elif call:
        return call, put, 'call'
    elif put:
        return call, put, 'put'
    else:
        return call, put, 'none'


def get_call_distance_pct(spot: float, sc_strike: float) -> float:
    """Distance from spot to short call as % of spot."""
    if spot <= 0:
        return 999.0
    return (sc_strike - spot) / spot * 100


def get_put_distance_pct(spot: float, sp_strike: float) -> float:
    """Distance from spot to short put as % of spot."""
    if spot <= 0:
        return 999.0
    return (spot - sp_strike) / spot * 100


def should_use_rapid_check(
    spot: float,
    sp_strike: float,
    sc_strike: float,
    breach_pct: float,
) -> bool:
    """
    §6.2: Use rapid heartbeat when spot is within 2× breach_pct
    of any short strike.

    Returns:
        True if rapid_check_interval should be used instead of normal interval
    """
    call_dist = get_call_distance_pct(spot, sc_strike)
    put_dist = get_put_distance_pct(spot, sp_strike)
    rapid_threshold = 2 * breach_pct
    return call_dist <= rapid_threshold or put_dist <= rapid_threshold
