"""
IC Cycle — Iron Condor Cycle Lifecycle Management

Manages the open → monitor → close → repeat cycle:
  - Creating new cycles
  - Determining next expiry
  - Scheduling new cycle after close
  - Cycle state transitions

From IC_ALGO_PLAN.md §10.3.

Created: 2026-03-24
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

from .ic_constants import (
    STRATEGY_IDLE, STRATEGY_ENTRY_PENDING, STRATEGY_ACTIVE,
    STRATEGY_EXITED, STRATEGY_CYCLING,
)
from .ic_state import create_cycle_state, compute_cycle_strikes, compute_entry_credit

log = logging.getLogger('ic_cycle')


def should_open_new_cycle(session: Dict) -> bool:
    """
    Determine if a new cycle should be opened.

    Conditions:
      - auto_cycle is enabled
      - strategy_status is IDLE or CYCLING
      - No daily loss limit hit
      - No circuit breaker active
      - No active cycle
    """
    params = session.get('params', {})

    if not params.get('auto_cycle', True):
        return False

    status = session.get('strategy_status', STRATEGY_IDLE)
    if status not in (STRATEGY_IDLE, STRATEGY_CYCLING):
        return False

    if session.get('max_daily_loss_hit', False):
        return False

    if session.get('circuit_breaker_active', False):
        return False

    if session.get('current_cycle') is not None:
        return False

    return True


def should_wait_cycle_delay(session: Dict) -> bool:
    """
    Check if we should wait before opening the next cycle (cycle_delay_sec).

    Returns True if we need to wait more.
    """
    params = session.get('params', {})
    delay = params.get('cycle_delay_sec', 30)

    # Check when last cycle was closed
    history = session.get('cycle_history', [])
    if not history:
        return False  # No previous cycle — start immediately

    last_close = history[-1].get('closed_at')
    if not last_close:
        return False

    try:
        closed_time = datetime.fromisoformat(last_close.replace('Z', '+00:00'))
        elapsed = (datetime.now(timezone.utc) - closed_time).total_seconds()
        return elapsed < delay
    except (ValueError, TypeError):
        return False


def prepare_new_cycle(session: Dict) -> Dict:
    """
    Create a new cycle state and attach it to the session.

    §10.3:
      1. Increment cycle_number
      2. Create cycle state
      3. Set strategy_status to ENTRY_PENDING

    Returns:
        The new cycle state dict
    """
    session['cycle_number'] = session.get('cycle_number', 0) + 1
    cycle_number = session['cycle_number']
    expiry = session.get('expiry', '')

    cycle = create_cycle_state(
        cycle_number=cycle_number,
        expiry=expiry,
        lots=session.get('params', {}).get('lots', 10),
    )

    session['current_cycle'] = cycle
    session['strategy_status'] = STRATEGY_ENTRY_PENDING

    log.info(
        f"[{session.get('session_id', '?')}] "
        f"Prepared new cycle {cycle['cycle_id']} (expiry={expiry})"
    )

    return cycle


def activate_cycle(session: Dict, legs: Dict) -> None:
    """
    Activate a cycle after all 4 legs are filled.

    Sets legs, computes strikes/credit, sets strategy_status to ACTIVE.
    """
    cycle = session.get('current_cycle')
    if not cycle:
        log.error("Cannot activate cycle — no current_cycle")
        return

    cycle['legs'] = legs
    lots = session.get('params', {}).get('lots', 10)

    # Compute strike summary
    compute_cycle_strikes(cycle)

    # Compute entry credit
    compute_entry_credit(cycle, lots)

    session['strategy_status'] = STRATEGY_ACTIVE

    log.info(
        f"[{session.get('session_id', '?')}] "
        f"Cycle {cycle['cycle_id']} ACTIVE — "
        f"net credit ${cycle['entry_net_credit']:.2f}/BTC = "
        f"${cycle['entry_net_credit_usd']:.6f} USD"
    )


def transition_to_cycling(session: Dict) -> None:
    """Transition to CYCLING state after closing a cycle (before next entry)."""
    session['strategy_status'] = STRATEGY_CYCLING


def transition_to_idle(session: Dict) -> None:
    """Transition to IDLE state (no auto-cycle or manual stop)."""
    session['strategy_status'] = STRATEGY_IDLE


def determine_next_expiry(
    current_expiry: str,
    dte_remaining: float,
    params: Dict,
) -> str:
    """
    Determine the expiry for the next cycle.

    §10.3: If DTE remaining in current expiry, keep it.
    Otherwise, pick next weekly expiry.

    Args:
        current_expiry: Current expiry date string
        dte_remaining: Days remaining until current expiry
        params: Session params

    Returns:
        Expiry date string for next cycle
    """
    close_at_dte = params.get('close_at_dte', 1)

    if dte_remaining > close_at_dte + 1:
        # Current expiry still has enough DTE
        return current_expiry

    # Need next expiry — add 7 days to current
    if current_expiry:
        try:
            current_date = datetime.strptime(current_expiry, '%Y-%m-%d')
            next_date = current_date + timedelta(days=7)
            return next_date.strftime('%Y-%m-%d')
        except ValueError:
            pass

    # Fallback: calculate from now + target DTE
    target_dte = params.get('expiry_dte', 7)
    next_date = datetime.now(timezone.utc) + timedelta(days=target_dte)
    return next_date.strftime('%Y-%m-%d')
