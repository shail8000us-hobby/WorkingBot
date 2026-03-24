"""
IC Greeks — Iron Condor Portfolio Greeks

Computes portfolio-level Greeks from per-leg exchange data.
Used for risk monitoring and display.

From IC_ALGO_PLAN.md §C.4.

Created: 2026-03-24
"""

import logging
from typing import Dict

log = logging.getLogger('ic_greeks')


def compute_portfolio_greeks(legs: Dict, lots: int) -> Dict[str, float]:
    """
    Sum Greeks across all 4 legs, accounting for long/short signs.

    §C.4:
      For sell legs: negate the Greek (selling a +0.16 delta call = -0.16 portfolio delta)
      For buy legs: keep the Greek as-is

    Args:
        legs: Dict of leg_key -> leg_state
        lots: Number of lots per leg

    Returns:
        Dict with portfolio delta, gamma, theta, vega
    """
    portfolio = {'delta': 0.0, 'gamma': 0.0, 'theta': 0.0, 'vega': 0.0}

    for leg_key, leg in legs.items():
        sign = -1 if leg.get('action') == 'sell' else +1

        for greek in ('delta', 'gamma', 'theta', 'vega'):
            mark_key = f'mark_{greek}'
            value = leg.get(mark_key, 0.0) or 0.0
            portfolio[greek] += sign * value * lots

    # Round for display
    for greek in portfolio:
        portfolio[greek] = round(portfolio[greek], 6)

    return portfolio


def update_leg_greeks(leg: Dict, ticker_data: Dict) -> None:
    """
    Update a single leg's Greeks from exchange ticker data.

    Args:
        leg: Leg state dictionary (mutated in place)
        ticker_data: Data from exchange API (expected to have greeks)
    """
    greeks = ticker_data.get('greeks', {})
    if not greeks:
        return

    leg['mark_delta'] = float(greeks.get('delta', 0.0) or 0.0)
    leg['mark_gamma'] = float(greeks.get('gamma', 0.0) or 0.0)
    leg['mark_theta'] = float(greeks.get('theta', 0.0) or 0.0)
    leg['mark_vega'] = float(greeks.get('vega', 0.0) or 0.0)


def is_portfolio_skewed(portfolio_greeks: Dict, threshold: float = 0.05) -> bool:
    """
    Check if the condor's net delta is significantly skewed.

    §C.4: |delta| > 0.05 = condor is skewed

    Args:
        portfolio_greeks: Output of compute_portfolio_greeks()
        threshold: Delta threshold for skew detection

    Returns:
        True if net delta exceeds threshold
    """
    return abs(portfolio_greeks.get('delta', 0.0)) > threshold
