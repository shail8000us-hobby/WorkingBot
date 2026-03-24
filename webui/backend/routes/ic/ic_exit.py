"""
IC Exit — Iron Condor Exit Logic

Exit conditions checked every heartbeat, in priority order:
  1. Emergency: Both sides threatened
  2. Max loss
  3. DTE too low
  4. Profit target

From IC_ALGO_PLAN.md §10.

Created: 2026-03-24
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from .ic_constants import (
    EXIT_PROFIT_TARGET, EXIT_MAX_LOSS, EXIT_DTE_CLOSE,
    EXIT_EMERGENCY, EXIT_MANUAL, EXIT_EXPIRED,
    STRATEGY_EXIT_PENDING, STRATEGY_EXITED, STRATEGY_CYCLING,
    LEG_CLOSED,
)
from .ic_engine import compute_realized_pnl

log = logging.getLogger('ic_exit')


def check_exit_conditions(
    cycle: Dict,
    params: Dict,
    minutes_to_expiry: float,
    call_threatened: bool = False,
    put_threatened: bool = False,
) -> Optional[str]:
    """
    Check all exit conditions in priority order.

    §10.1:
      Priority 1: Emergency (both sides threatened)
      Priority 2: Max loss
      Priority 3: DTE too low
      Priority 4: Profit target

    Args:
        cycle: Current cycle state
        params: Session params
        minutes_to_expiry: Minutes until options expire
        call_threatened: Is call side breached?
        put_threatened: Is put side breached?

    Returns:
        Exit reason string, or None if no exit triggered
    """
    if not cycle:
        return None

    # Priority 1 — Emergency: Both sides threatened
    if call_threatened and put_threatened:
        log.warning("EXIT: Both sides threatened — emergency close")
        return EXIT_EMERGENCY

    # Priority 2 — Max Loss
    unrealized = cycle.get('unrealized_pnl_usd', 0.0)
    max_loss = cycle.get('max_loss_usd', 0.0)  # Negative
    max_loss_pct = params.get('max_loss_pct', 100)

    if max_loss < 0:
        threshold = max_loss * (max_loss_pct / 100)
        if unrealized <= threshold:
            log.warning(
                f"EXIT: Max loss hit — unrealized ${unrealized:.4f} <= "
                f"threshold ${threshold:.4f}"
            )
            return EXIT_MAX_LOSS

    # Priority 3 — DTE Close
    close_at_dte = params.get('close_at_dte', 1)
    dte_minutes = close_at_dte * 1440  # Convert days to minutes
    if minutes_to_expiry <= dte_minutes:
        log.info(
            f"EXIT: DTE close — {minutes_to_expiry:.0f} min to expiry <= "
            f"{dte_minutes:.0f} min threshold ({close_at_dte} days)"
        )
        return EXIT_DTE_CLOSE

    # Priority 4 — Profit Target
    pnl_pct = cycle.get('pnl_as_pct_of_max_profit', 0.0)
    profit_target = params.get('profit_target_pct', 50)

    if pnl_pct >= profit_target:
        log.info(
            f"EXIT: Profit target hit — P&L {pnl_pct:.1f}% >= "
            f"target {profit_target}%"
        )
        return EXIT_PROFIT_TARGET

    return None


def prepare_close_orders(cycle: Dict) -> list:
    """
    Generate the list of close orders needed to exit all legs.

    §10.2: Close short legs first (buy back), then long legs (sell).

    Returns:
        List of order specs: [{leg_key, action, ...}]
    """
    legs = cycle.get('legs', {})
    orders = []

    # Close short legs first (buy back)
    for leg_key in ('SP', 'SC'):
        leg = legs.get(leg_key)
        if leg and leg.get('status') == 'open':
            orders.append({
                'leg_key': leg_key,
                'close_action': 'buy',  # Buy back short
                'strike': leg.get('strike'),
                'side': leg.get('side'),
                'lots': leg.get('lots', 0),
            })

    # Close long legs (sell)
    for leg_key in ('LP', 'LC'):
        leg = legs.get(leg_key)
        if leg and leg.get('status') == 'open':
            orders.append({
                'leg_key': leg_key,
                'close_action': 'sell',  # Sell long
                'strike': leg.get('strike'),
                'side': leg.get('side'),
                'lots': leg.get('lots', 0),
            })

    return orders


def finalize_cycle_close(
    session: Dict,
    cycle: Dict,
    exit_reason: str,
    close_premiums: Dict[str, float] = None,
) -> float:
    """
    Finalize a cycle closure: compute realized P&L, update session.

    §10.2 steps 2-5:
      - Calculate realized P&L
      - Update session totals
      - Move cycle to history

    Args:
        session: Session state (mutated)
        cycle: Current cycle (mutated)
        exit_reason: Why the cycle was closed
        close_premiums: {leg_key: fill_price} for closed legs

    Returns:
        Realized P&L in USD for this cycle
    """
    now = datetime.now(timezone.utc).isoformat()
    legs = cycle.get('legs', {})
    lots = session.get('params', {}).get('lots', 10)

    # Record close premiums on legs
    if close_premiums:
        for leg_key, close_price in close_premiums.items():
            if leg_key in legs:
                legs[leg_key]['close_premium'] = close_price
                legs[leg_key]['close_time'] = now
                legs[leg_key]['status'] = LEG_CLOSED

    # Compute realized P&L
    realized_pnl = compute_realized_pnl(legs, lots)

    # Update cycle
    cycle['closed_at'] = now
    cycle['exit_reason'] = exit_reason
    cycle['exit_pnl_usd'] = round(realized_pnl, 6)

    # Update session
    session['cycles_completed'] = session.get('cycles_completed', 0) + 1
    session['total_realized_pnl'] = round(
        session.get('total_realized_pnl', 0.0) + realized_pnl, 6
    )

    # Track daily loss (only add losses)
    if realized_pnl < 0:
        session['daily_loss_usd'] = round(
            session.get('daily_loss_usd', 0.0) + abs(realized_pnl), 6
        )

    # Archive cycle to history
    from .ic_state import archive_cycle
    archive_cycle(session)

    log.info(
        f"[{session.get('session_id', '?')}] "
        f"Cycle {cycle.get('cycle_id')} closed: reason={exit_reason}, "
        f"realized=${realized_pnl:.6f}, total=${session['total_realized_pnl']:.6f}"
    )

    return realized_pnl


def check_expiry(cycle: Dict, current_time: datetime, expiry_time: datetime) -> bool:
    """
    §C.5: Check if options have expired.

    Returns True if current_time >= expiry_time.
    """
    if not expiry_time:
        return False
    return current_time >= expiry_time
