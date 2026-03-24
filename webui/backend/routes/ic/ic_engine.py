"""
IC Engine — Iron Condor P&L Calculations

Core financial math for the Iron Condor:
- Net credit calculation
- Max profit / max loss (dynamic after rolls)
- Unrealized P&L per leg and total
- Realized P&L on close
- P&L as percentage of max profit

All formulas from IC_ALGO_PLAN.md §8.

Created: 2026-03-24
"""

import logging
from typing import Dict, Optional

from .ic_constants import LOT_SIZE_BTC, LEG_SP, LEG_LP, LEG_SC, LEG_LC

log = logging.getLogger('ic_engine')


def compute_net_credit(legs: Dict) -> float:
    """
    Compute net credit per BTC from entry premiums of all 4 legs.

    Net credit = sell premiums - buy premiums

    Returns:
        Net credit in USD per BTC (positive = credit collected)
    """
    credit = 0.0
    for leg_key, leg in legs.items():
        if leg.get('action') == 'sell':
            credit += leg.get('entry_premium', 0.0)
        elif leg.get('action') == 'buy':
            credit -= leg.get('entry_premium', 0.0)
    return credit


def compute_max_profit(net_credit_per_btc: float, lots: int) -> float:
    """
    Max profit = net credit (in USD).

    §8.1: max_profit_usd = net_credit_per_btc × lots × LOT_SIZE_BTC
    """
    return net_credit_per_btc * lots * LOT_SIZE_BTC


def compute_max_loss(
    short_put_strike: float,
    long_put_strike: float,
    short_call_strike: float,
    long_call_strike: float,
    effective_net_credit: float,
    lots: int,
) -> float:
    """
    Max loss (DYNAMIC — recalculated after each roll).

    §8.2: After asymmetric rolls, use the WIDER wing:
      wing_put  = SP - LP
      wing_call = LC - SC
      max_loss_per_btc = max(wing_put, wing_call) - effective_net_credit
      max_loss_usd = max_loss_per_btc × lots × LOT_SIZE_BTC  (negative)

    Args:
        effective_net_credit: entry_net_credit + cumulative_roll_credit

    Returns:
        Max loss in USD (negative value)
    """
    wing_put = short_put_strike - long_put_strike
    wing_call = long_call_strike - short_call_strike
    max_wing = max(wing_put, wing_call)

    if max_wing <= 0:
        log.warning("Max wing width is <= 0 — invalid condor structure")
        return 0.0

    max_loss_per_btc = max_wing - effective_net_credit
    max_loss_usd = -(max_loss_per_btc * lots * LOT_SIZE_BTC)
    return max_loss_usd  # Returns negative


def compute_effective_net_credit(cycle: Dict) -> float:
    """
    Effective net credit = entry credit + cumulative roll credit/debit.

    §9.6: This changes after every roll.
    """
    entry = cycle.get('entry_net_credit', 0.0)
    roll = cycle.get('cumulative_roll_credit', 0.0)
    return entry + roll


def compute_leg_pnl(leg: Dict) -> float:
    """
    Compute unrealized P&L for a single leg (USD per BTC).

    §8.3:
      Sell leg: pnl = entry_premium - mark_premium (positive if premium fell)
      Buy leg:  pnl = mark_premium - entry_premium (positive if premium rose)
    """
    entry = leg.get('entry_premium', 0.0)
    mark = leg.get('mark_premium', 0.0)

    if leg.get('action') == 'sell':
        return entry - mark
    elif leg.get('action') == 'buy':
        return mark - entry
    return 0.0


def compute_unrealized_pnl(legs: Dict, lots: int) -> float:
    """
    Compute total unrealized P&L across all legs.

    §8.3:
      total_pnl_per_btc = sum(leg_pnl for all legs)
      unrealized_pnl_usd = total_pnl_per_btc × lots × LOT_SIZE_BTC
    """
    total_pnl_per_btc = sum(compute_leg_pnl(leg) for leg in legs.values())
    return total_pnl_per_btc * lots * LOT_SIZE_BTC


def compute_pnl_pct(unrealized_pnl_usd: float, max_profit_usd: float) -> float:
    """
    P&L as percentage of max profit.

    §8.4: pnl_pct = (unrealized_pnl_usd / max_profit_usd) × 100
    """
    if max_profit_usd == 0:
        return 0.0
    return (unrealized_pnl_usd / max_profit_usd) * 100


def compute_realized_pnl(legs: Dict, lots: int) -> float:
    """
    Compute realized P&L when a cycle is closed.

    §8.5: For each closed leg:
      Sell: realized = (entry_premium - close_premium) × lots × LOT_SIZE_BTC
      Buy:  realized = (close_premium - entry_premium) × lots × LOT_SIZE_BTC
    """
    total = 0.0
    for leg_key, leg in legs.items():
        entry = leg.get('entry_premium', 0.0)
        close = leg.get('close_premium')
        if close is None:
            continue

        if leg.get('action') == 'sell':
            total += (entry - close) * lots * LOT_SIZE_BTC
        elif leg.get('action') == 'buy':
            total += (close - entry) * lots * LOT_SIZE_BTC

    return total


def update_cycle_pnl(cycle: Dict, lots: int) -> None:
    """
    Recompute all P&L fields on a cycle. Called every heartbeat.

    Updates:
      - unrealized_pnl_usd
      - pnl_as_pct_of_max_profit
      - max_loss_usd (dynamic after rolls)
      - max_adverse_excursion_usd
    """
    legs = cycle.get('legs', {})
    if not legs:
        return

    # Unrealized P&L
    unrealized = compute_unrealized_pnl(legs, lots)
    cycle['unrealized_pnl_usd'] = round(unrealized, 6)

    # Max profit stays fixed at entry credit
    max_profit = cycle.get('max_profit_usd', 0.0)

    # P&L as % of max profit
    cycle['pnl_as_pct_of_max_profit'] = round(
        compute_pnl_pct(unrealized, max_profit), 2
    )

    # Dynamic max loss
    effective_credit = compute_effective_net_credit(cycle)
    max_loss = compute_max_loss(
        cycle.get('short_put_strike', 0),
        cycle.get('long_put_strike', 0),
        cycle.get('short_call_strike', 0),
        cycle.get('long_call_strike', 0),
        effective_credit,
        lots,
    )
    cycle['max_loss_usd'] = round(max_loss, 6)

    # Track max adverse excursion (worst unrealized loss)
    if unrealized < cycle.get('max_adverse_excursion_usd', 0):
        cycle['max_adverse_excursion_usd'] = round(unrealized, 6)


def compute_roll_credit(
    old_close_premiums: Dict[str, float],  # {leg_key: close_price}
    new_entry_premiums: Dict[str, float],  # {leg_key: entry_price}
    old_legs: Dict,
    new_legs: Dict,
) -> float:
    """
    Compute the credit/debit from a roll operation.

    §9.3: roll_credit = net proceeds from closing old + net proceeds from opening new.

    Returns:
        Positive = collected credit, negative = paid debit
    """
    credit = 0.0

    # Closing old legs: buy back what was sold, sell what was bought
    for leg_key, close_prem in old_close_premiums.items():
        old_leg = old_legs.get(leg_key, {})
        if old_leg.get('action') == 'sell':
            # Buying back a short: costs money (negative)
            credit -= close_prem
        elif old_leg.get('action') == 'buy':
            # Selling a long: collects money (positive)
            credit += close_prem

    # Opening new legs: sell new shorts, buy new longs
    for leg_key, entry_prem in new_entry_premiums.items():
        new_leg = new_legs.get(leg_key, {})
        if new_leg.get('action') == 'sell':
            # Selling new short: collects money (positive)
            credit += entry_prem
        elif new_leg.get('action') == 'buy':
            # Buying new long: costs money (negative)
            credit -= entry_prem

    return credit
