"""
IC Adjuster — Iron Condor Adjustment Decision Engine

Determines what adjustment action to take when a breach is detected:
- Roll tested side (spread in direction of price movement)
- Optionally roll untested side closer for extra credit
- Emergency close if both sides breached
- Guardrails: cooldown, max adjustments, gamma death zone, negative credit

From IC_ALGO_PLAN.md §9.

Created: 2026-03-24
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from .ic_constants import (
    ADJ_ROLL_CALL_UP, ADJ_ROLL_PUT_DOWN, ADJ_ROLL_BOTH, ADJ_EMERGENCY_CLOSE,
)

log = logging.getLogger('ic_adjuster')

# Sentinel return values for adjustment decisions
DECISION_NO_ACTION = 'no_action'
DECISION_ROLL_CALL = 'roll_call'
DECISION_ROLL_PUT = 'roll_put'
DECISION_ROLL_BOTH = 'roll_both'
DECISION_EMERGENCY_CLOSE = 'emergency_close'
DECISION_EXIT_CYCLE = 'exit_cycle'


def decide_adjustment(
    cycle: Dict,
    session: Dict,
    call_threatened: bool,
    put_threatened: bool,
    minutes_to_expiry: float,
) -> str:
    """
    Main adjustment decision function.

    §9.2 Decision Tree:
      Both sides threatened → emergency close
      Only call threatened → roll call spread up
      Only put threatened → roll put spread down
      No breach → no action

    §9.5 Guardrails checked before any roll.

    Returns:
        Decision constant (DECISION_*)
    """
    if not cycle or (not call_threatened and not put_threatened):
        return DECISION_NO_ACTION

    params = session.get('params', {})

    # Check guardrails before any roll decision
    guardrail_result = _check_guardrails(cycle, session, params, minutes_to_expiry)
    if guardrail_result is not None:
        return guardrail_result

    # §9.2: Both sides threatened = emergency
    if call_threatened and put_threatened:
        log.warning("Both sides breached — emergency close")
        return DECISION_EMERGENCY_CLOSE

    # Single-side breach
    if call_threatened:
        log.info("Call side breached — roll call spread up")
        if params.get('roll_untested_side_enabled', True):
            return DECISION_ROLL_BOTH  # Roll both: call up + put up
        return DECISION_ROLL_CALL

    if put_threatened:
        log.info("Put side breached — roll put spread down")
        if params.get('roll_untested_side_enabled', True):
            return DECISION_ROLL_BOTH  # Roll both: put down + call down
        return DECISION_ROLL_PUT

    return DECISION_NO_ACTION


def _check_guardrails(
    cycle: Dict,
    session: Dict,
    params: Dict,
    minutes_to_expiry: float,
) -> Optional[str]:
    """
    Check adjustment guardrails before executing a roll.

    Returns:
        DECISION_EXIT_CYCLE if a guardrail blocks the roll,
        None if guardrails pass.
    """
    # §9.5: Max adjustments per cycle
    adj_count = cycle.get('adjustment_count', 0)
    max_adj = params.get('max_adjustments_per_cycle', 3)
    if adj_count >= max_adj:
        log.info(
            f"Max adjustments ({max_adj}) reached — exiting cycle instead of rolling"
        )
        return DECISION_EXIT_CYCLE

    # §9.5: Adjustment cooldown
    cooldown_sec = params.get('adjustment_cooldown_sec', 300)
    last_adj = session.get('last_adjustment_time')
    if last_adj:
        try:
            last_time = datetime.fromisoformat(last_adj.replace('Z', '+00:00'))
            elapsed = (datetime.now(timezone.utc) - last_time).total_seconds()
            if elapsed < cooldown_sec:
                log.debug(
                    f"Adjustment cooldown: {elapsed:.0f}s elapsed < {cooldown_sec}s — skipping"
                )
                return DECISION_NO_ACTION
        except (ValueError, TypeError):
            pass

    # §C.7: Near-expiry guard — don't roll into gamma death zone
    close_at_dte = params.get('close_at_dte', 1)
    dte_guard_minutes = (close_at_dte + 1) * 1440  # 1 day buffer above close_at_dte
    if minutes_to_expiry < dte_guard_minutes:
        log.info(
            f"DTE too low for roll ({minutes_to_expiry:.0f} min < "
            f"{dte_guard_minutes:.0f} min) — exiting cycle instead"
        )
        return DECISION_EXIT_CYCLE

    # §C.2: Negative credit guard — refuse roll if effective credit would go <= 0
    # This is a pre-check using estimated roll cost; exact check happens in ic_roller.py
    effective_credit = cycle.get('entry_net_credit', 0) + cycle.get('cumulative_roll_credit', 0)
    if effective_credit <= 0:
        log.warning(
            f"Effective net credit is already ${effective_credit:.2f} (≤ 0) — "
            "exiting cycle instead of rolling (guaranteed loss)"
        )
        return DECISION_EXIT_CYCLE

    return None


def create_adjustment_event(
    adj_type: str,
    trigger: str,
    spot: float,
    old_strikes: Dict[str, float],
    new_strikes: Dict[str, float],
    roll_credit: float,
    cumulative_roll_credit: float,
) -> Dict:
    """
    Create an adjustment event record.

    §9.4 format.
    """
    return {
        'event_id': f"adj_{time.time():.6f}",
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'type': adj_type,
        'trigger': trigger,
        'spot_at_trigger': spot,
        'old_strikes': old_strikes,
        'new_strikes': new_strikes,
        'roll_credit': round(roll_credit, 4),
        'cumulative_roll_credit': round(cumulative_roll_credit, 4),
    }


def record_adjustment(
    session: Dict,
    cycle: Dict,
    adjustment_event: Dict,
) -> None:
    """
    Record an adjustment event on the cycle and session.

    Updates:
      - cycle.adjustments[]
      - cycle.adjustment_count
      - session.last_adjustment_time
      - session.recent_adjustment_times[]
    """
    if 'adjustments' not in cycle:
        cycle['adjustments'] = []
    cycle['adjustments'].append(adjustment_event)
    cycle['adjustment_count'] = cycle.get('adjustment_count', 0) + 1

    session['last_adjustment_time'] = datetime.now(timezone.utc).isoformat()

    # Track for circuit breaker
    from .ic_safety import record_adjustment_time
    record_adjustment_time(session)

    log.info(
        f"[{session.get('session_id', '?')}] "
        f"Adjustment #{cycle['adjustment_count']}: {adjustment_event.get('type')} "
        f"roll_credit=${adjustment_event.get('roll_credit', 0):.4f}"
    )


def estimate_roll_credit_viable(
    cycle: Dict,
    estimated_roll_credit: float,
) -> bool:
    """
    §C.2: Check if a roll would make effective credit go negative.

    Returns True if the roll is viable (credit stays positive).
    """
    effective = cycle.get('entry_net_credit', 0) + cycle.get('cumulative_roll_credit', 0)
    new_effective = effective + estimated_roll_credit
    if new_effective <= 0:
        log.warning(
            f"Roll would make effective credit ${new_effective:.2f} (≤ 0) — "
            "refusing roll"
        )
        return False
    return True
