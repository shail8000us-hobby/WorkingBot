"""
GCD Batch Utility — shared module for Patience execution engine.

Computes GCD-balanced lot schedules for multi-leg option card execution.
No external dependencies. Pure math.

Why GCD matters on thin markets:
    Delta Exchange India 30 DTE options have thin order books (2-3 lots on bid).
    GCD + autoloop drip-feeds balanced rounds with maker_only orders that sit
    and wait. This is the execution intelligence for illiquid markets — better
    than aggressive algorithms that eat through the book.

Example:
    Legs: [BUY 20 CE 75000, SELL 20 CE 80000, BUY 10 PE 65000, SELL 10 PE 60000]
    GCD  = 10
    Ratio = [2, 2, 1, 1]
    Rounds = 10
    Round 1: BUY 2 CE 75000, SELL 2 CE 80000, BUY 1 PE 65000, SELL 1 PE 60000
    ...repeat 10 times...
    Max unhedged exposure = 1 round of lots

Created: March 14, 2026
"""

from math import gcd
from functools import reduce
from typing import List


def compute_gcd(numbers: List[int]) -> int:
    """GCD of a list of positive integers."""
    if not numbers:
        return 1
    return reduce(gcd, numbers)


def compute_gcd_schedule(legs: List[dict]) -> dict:
    """
    Compute GCD execution schedule for a set of option legs.

    Args:
        legs: List of leg dicts, each must have 'lot_count' or 'lots' key.
              Also passed through: leg_id, direction, option_type, etc.

    Returns:
        {
            'gcd': int,             # greatest common divisor of all lots
            'total_rounds': int,    # gcd value (number of balanced rounds)
            'per_round': [          # one entry per leg per round
                {
                    ...all leg fields...,
                    'lots_this_round': int   # lots to place per round
                },
                ...
            ]
        }

    Raises:
        ValueError: if legs list is empty or any lots value is <= 0
    """
    if not legs:
        raise ValueError("compute_gcd_schedule: legs list is empty")

    lots_list = []
    for leg in legs:
        lots = int(leg.get('lots') or leg.get('lot_count') or 0)
        if lots <= 0:
            raise ValueError(
                f"compute_gcd_schedule: leg {leg.get('leg_id', '?')} has lots={lots} (must be > 0)"
            )
        lots_list.append(lots)

    g = compute_gcd(lots_list)
    ratios = [l // g for l in lots_list]
    total_rounds = g

    per_round = []
    for i, leg in enumerate(legs):
        per_round.append({
            **leg,
            'lots_this_round': ratios[i],
        })

    return {
        'gcd': g,
        'total_rounds': total_rounds,
        'per_round': per_round,
    }


def schedule_summary(schedule: dict) -> str:
    """Human-readable summary of a GCD schedule."""
    g = schedule['gcd']
    rounds = schedule['total_rounds']
    legs = schedule['per_round']
    leg_summary = ', '.join(
        f"{l['direction']} {l['lots_this_round']} {l.get('option_type', '')} {l.get('strike', '')}"
        for l in legs
    )
    return f"GCD={g}, {rounds} rounds × [{leg_summary}]"
