"""
IC Safety — Iron Condor Safety System

Three-layer safety system for defined-risk IC strategy:
  Layer 1: Session-level hard stops (daily loss, margin, data confidence)
  Layer 2: Cycle-level hard stops (max loss, max adjustments, emergency)
  Layer 3: Circuit breaker (rapid adjustment storm, fill timeout cascade)

From IC_ALGO_PLAN.md §11.

Created: 2026-03-24
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from .ic_constants import (
    SAFETY_INFO, SAFETY_WARNING, SAFETY_ALERT, SAFETY_CRITICAL,
    SAFETY_ACTION_CONTINUE, SAFETY_ACTION_WARN, SAFETY_ACTION_PAUSE, SAFETY_ACTION_STOP,
)

log = logging.getLogger('ic_safety')


def create_safety_event(
    event_type: str,
    level: str,
    message: str,
    action: str,
) -> Dict:
    """Create a standardized safety event dict."""
    return {
        'type': event_type,
        'level': level,
        'message': message,
        'action': action,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Layer 1 — Session-level Hard Stops
# =============================================================================

def check_daily_loss_limit(session: Dict) -> Optional[Dict]:
    """
    Check if daily loss limit has been exceeded.

    Returns safety event if triggered, None otherwise.
    """
    daily_loss = abs(session.get('daily_loss_usd', 0.0))
    max_daily = session.get('params', {}).get('max_daily_loss_usd', 500)

    if daily_loss >= max_daily:
        return create_safety_event(
            'daily_loss_limit',
            SAFETY_CRITICAL,
            f"Daily loss ${daily_loss:.2f} exceeds limit ${max_daily}",
            SAFETY_ACTION_STOP,
        )
    elif daily_loss >= max_daily * 0.8:
        return create_safety_event(
            'daily_loss_warning',
            SAFETY_WARNING,
            f"Daily loss ${daily_loss:.2f} approaching limit ${max_daily} (80%+)",
            SAFETY_ACTION_WARN,
        )
    return None


def check_margin(session: Dict, available_margin_pct: float) -> Optional[Dict]:
    """
    Check if margin is below safety threshold.

    Args:
        available_margin_pct: Available margin as % of required margin

    Returns safety event if triggered, None otherwise.
    """
    threshold = session.get('params', {}).get('margin_safety_pct', 20)

    if available_margin_pct < threshold:
        return create_safety_event(
            'margin_low',
            SAFETY_CRITICAL,
            f"Available margin {available_margin_pct:.1f}% below safety threshold {threshold}%",
            SAFETY_ACTION_PAUSE,
        )
    return None


def check_data_confidence(session: Dict) -> Optional[Dict]:
    """
    Check if data fetch failures exceed threshold (>3 consecutive).

    Returns safety event if triggered, None otherwise.
    """
    failures = session.get('consecutive_fetch_failures', 0)

    if failures > 3:
        return create_safety_event(
            'data_confidence_low',
            SAFETY_ALERT,
            f"{failures} consecutive premium fetch failures — data unreliable",
            SAFETY_ACTION_PAUSE,
        )
    return None


# =============================================================================
# Layer 2 — Cycle-level Hard Stops
# =============================================================================

def check_max_loss(cycle: Dict, params: Dict) -> Optional[Dict]:
    """
    Check if unrealized loss has hit the max loss threshold.

    §10.1 Priority 2: |unrealized_pnl| >= |max_loss| × (max_loss_pct/100)
    """
    if not cycle:
        return None

    unrealized = cycle.get('unrealized_pnl_usd', 0.0)
    max_loss = cycle.get('max_loss_usd', 0.0)  # Negative
    max_loss_pct = params.get('max_loss_pct', 100)

    if max_loss == 0:
        return None

    # Both are negative for losses
    threshold = max_loss * (max_loss_pct / 100)

    if unrealized <= threshold:
        return create_safety_event(
            'max_loss_hit',
            SAFETY_CRITICAL,
            f"Unrealized loss ${unrealized:.4f} hit max loss threshold ${threshold:.4f}",
            SAFETY_ACTION_STOP,
        )
    return None


def check_max_adjustments(cycle: Dict, params: Dict) -> Optional[Dict]:
    """
    Check if adjustment count has hit the per-cycle cap.

    §9.5: If reached, go to EXIT_PENDING instead of adjusting.
    """
    if not cycle:
        return None

    count = cycle.get('adjustment_count', 0)
    max_adj = params.get('max_adjustments_per_cycle', 3)

    if count >= max_adj:
        return create_safety_event(
            'max_adjustments_hit',
            SAFETY_ALERT,
            f"Adjustment count {count} hit maximum {max_adj} — exiting cycle",
            SAFETY_ACTION_STOP,
        )
    return None


def check_emergency_breach(
    call_threatened: bool,
    put_threatened: bool,
) -> Optional[Dict]:
    """
    Check if both sides are threatened simultaneously.

    §9.5: Emergency close threshold — close immediately regardless of guardrails.
    """
    if call_threatened and put_threatened:
        return create_safety_event(
            'emergency_both_breached',
            SAFETY_CRITICAL,
            "Both call and put sides breached — emergency close required",
            SAFETY_ACTION_STOP,
        )
    return None


# =============================================================================
# Layer 3 — Circuit Breaker
# =============================================================================

def check_circuit_breaker(session: Dict) -> Optional[Dict]:
    """
    Check for rapid adjustment storm (3+ adjustments in 60 minutes).

    §11 Layer 3: Pause 30 minutes, alert operator.
    """
    if not session.get('params', {}).get('circuit_breaker_enabled', True):
        return None

    # Check if circuit breaker is currently active
    cb_until = session.get('circuit_breaker_until')
    if cb_until:
        try:
            cb_time = datetime.fromisoformat(cb_until.replace('Z', '+00:00'))
            if datetime.now(timezone.utc) < cb_time:
                remaining_mins = (cb_time - datetime.now(timezone.utc)).seconds / 60
                return create_safety_event(
                    'circuit_breaker_active',
                    SAFETY_ALERT,
                    f"Circuit breaker active — {remaining_mins:.0f} minutes remaining",
                    SAFETY_ACTION_PAUSE,
                )
            else:
                # Reset circuit breaker
                session['circuit_breaker_active'] = False
                session['circuit_breaker_until'] = None
        except (ValueError, TypeError):
            pass

    # Check recent adjustments
    recent_times = session.get('recent_adjustment_times', [])
    now = time.time()
    one_hour_ago = now - 3600

    # Clean old entries
    recent_times = [t for t in recent_times if t > one_hour_ago]
    session['recent_adjustment_times'] = recent_times

    if len(recent_times) >= 3:
        return create_safety_event(
            'circuit_breaker_triggered',
            SAFETY_CRITICAL,
            f"{len(recent_times)} adjustments in the last 60 minutes — circuit breaker engaged",
            SAFETY_ACTION_PAUSE,
        )
    return None


def record_adjustment_time(session: Dict) -> None:
    """Record the current time as an adjustment event for circuit breaker tracking."""
    if 'recent_adjustment_times' not in session:
        session['recent_adjustment_times'] = []
    session['recent_adjustment_times'].append(time.time())


def activate_circuit_breaker(session: Dict, pause_minutes: int = 30) -> None:
    """Activate the circuit breaker with a pause duration."""
    from datetime import timedelta
    session['circuit_breaker_active'] = True
    cb_until = datetime.now(timezone.utc) + timedelta(minutes=pause_minutes)
    session['circuit_breaker_until'] = cb_until.isoformat()
    log.warning(
        f"[{session.get('session_id', '?')}] Circuit breaker activated — "
        f"pausing for {pause_minutes} minutes until {cb_until}"
    )


# =============================================================================
# Aggregate Safety Gate
# =============================================================================

def run_safety_gate(
    session: Dict,
    cycle: Optional[Dict] = None,
    available_margin_pct: float = 100.0,
    call_threatened: bool = False,
    put_threatened: bool = False,
) -> Tuple[bool, Optional[Dict]]:
    """
    Run all safety checks in priority order.

    Returns:
        (is_blocked, safety_event)
        is_blocked: True if heartbeat should be aborted
        safety_event: The triggering event, if any
    """
    params = session.get('params', {})

    # Layer 1
    event = check_daily_loss_limit(session)
    if event and event['action'] == SAFETY_ACTION_STOP:
        return True, event

    event = check_margin(session, available_margin_pct)
    if event and event['action'] in (SAFETY_ACTION_PAUSE, SAFETY_ACTION_STOP):
        return True, event

    event = check_data_confidence(session)
    if event and event['action'] == SAFETY_ACTION_PAUSE:
        return True, event

    # Layer 2
    if cycle:
        event = check_emergency_breach(call_threatened, put_threatened)
        if event:
            return True, event

        event = check_max_loss(cycle, params)
        if event:
            return True, event

    # Layer 3
    event = check_circuit_breaker(session)
    if event and event['action'] == SAFETY_ACTION_PAUSE:
        return True, event

    return False, None
