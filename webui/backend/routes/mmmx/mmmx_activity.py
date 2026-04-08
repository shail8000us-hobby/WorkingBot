"""
MMMX Activity Log — Background Activities Ring Buffer

In-memory + DB-persisted ring buffer of activity events so the WebUI
can show what the algo is doing in real-time.

Spec: MMMX_IMPLEMENTATION_PLAN.md Section 1 (mmmx_activity.py module).

All events are namespaced mmmx_* to prevent collisions with MMM.
"""

import logging
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .mmmx_constants import MAX_ACTIVITY_ENTRIES, WS_EVENT_PREFIX

log = logging.getLogger('mmmx_activity')

# ── Activity type registry ────────────────────────────────────────────────────
ACTIVITY_TYPES = {
    # Session lifecycle
    'session_created':          'Session Created',
    'session_gates_passed':     'Entry Gates Passed',
    'session_started':          'Session Started',
    'session_paused':           'Session Paused',
    'session_resumed':          'Session Resumed',
    'session_stopped':          'Session Stopped',
    'session_complete':         'Session Complete',
    'session_error':            'Session Error',

    # Heartbeat
    'heartbeat_start':          'Heartbeat Started',
    'heartbeat_complete':       'Heartbeat Complete',
    'heartbeat_skipped':        'Heartbeat Skipped (PnL incomplete)',

    # Tranche lifecycle
    'tranche_deploying':        'Deploying Tranche',
    'tranche_deployed':         'Tranche Deployed',
    'tranche_deploy_failed':    'Tranche Deploy Failed',
    'tranche_closed':           'Tranche Closed',
    'tranche_repositioned':     'Tranche Repositioned',

    # Safety / triggers
    'hard_stop_fired':          'Hard Stop Fired',
    'dte_close_fired':          'DTE Close Fired',
    'atm_shield_fired':         'ATM Shield Fired',
    'atm_shield_aborted':       'ATM Shield Aborted',
    'delta_gate_fired':         'Delta Gate Fired',
    'iv_catastrophe_fired':     'IV Catastrophe Gate Fired',
    'near_itm_fired':           'Near-ITM Close Fired',

    # Profit booking
    'profit_booking_queued':    'Profit Booking Queued',
    'profit_booking_executed':  'Profit Booking Executed',
    'profit_booking_skipped':   'Profit Booking Skipped',

    # Hedging
    'hedge_scheduled':          'Hedge Scheduled',
    'hedge_executing':          'Hedge Executing',
    'hedge_executed':           'Hedge Executed',
    'hedge_displaced':          'Hedge Displaced (informational)',
    'hedge_closed':             'Hedge Closed',

    # Deployment queue
    'queue_populated':          'Deployment Queue Populated',
    'queue_cleared':            'Deployment Queue Cleared (Retracement)',

    # Orders
    'order_placing':            'Placing Order',
    'order_placed':             'Order Placed',
    'order_filled':             'Order Filled',
    'order_repricing':          'Repricing Order',
    'order_failed':             'Order Failed',
    'order_partial_fill':       'Partial Fill Recorded',

    # Param changes
    'params_changed':           'Params Hot-Reloaded',

    # Safety events
    'naked_position_detected':  'Naked Position Detected',
    'stale_monitor_detected':   'Stale Monitor Detected',
    'generation_guard_fired':   'Generation Guard Fired',
    'circuit_breaker_open':     'Circuit Breaker OPEN',
    'circuit_breaker_closed':   'Circuit Breaker CLOSED',

    # Whipsaw
    'whipsaw_score_updated':    'Whipsaw Score Updated',
    'whipsaw_cooldown_start':   'Whipsaw COOLDOWN Started',
    'whipsaw_cooldown_end':     'Whipsaw COOLDOWN Ended',
}


class MMMXActivityLog:
    """Thread-safe in-memory activity log with DB persistence."""

    def __init__(self, storage=None):
        self._buffer: deque = deque(maxlen=MAX_ACTIVITY_ENTRIES)
        self._lock = threading.Lock()
        self._storage = storage   # injected to avoid circular import

    def set_storage(self, storage) -> None:
        self._storage = storage

    def log_activity(
        self,
        event_type: str,
        message: str,
        session_id: Optional[str] = None,
        level: str = 'info',
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Append an activity event to the ring buffer and DB.

        Args:
            event_type: Key from ACTIVITY_TYPES (unrecognized types accepted with warning).
            message: Human-readable description.
            session_id: MMMX session ID or None for process-level events.
            level: 'info' | 'warning' | 'error' | 'critical'
            data: Optional extra context.

        Returns:
            The event dict that was appended.
        """
        if event_type not in ACTIVITY_TYPES:
            log.warning(f"Unknown MMMX activity type: {event_type!r}")

        entry: Dict[str, Any] = {
            'type':        event_type,
            'label':       ACTIVITY_TYPES.get(event_type, event_type),
            'message':     message,
            'session_id':  session_id,
            'level':       level,
            'timestamp':   datetime.now(timezone.utc).isoformat(),
            'data':        data or {},
        }

        with self._lock:
            self._buffer.appendleft(entry)

        if self._storage is not None:
            try:
                self._storage.append_activity(
                    event_type=event_type,
                    data=entry,
                    session_id=session_id,
                )
            except Exception as exc:
                log.error(f"Failed to persist activity to DB: {exc}")

        return entry

    def get_recent(
        self,
        session_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Return recent activities from the in-memory buffer."""
        with self._lock:
            entries = list(self._buffer)

        if session_id:
            entries = [e for e in entries if e.get('session_id') == session_id]

        return entries[:limit]

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()


# ── Singleton ─────────────────────────────────────────────────────────────────
_instance: Optional[MMMXActivityLog] = None
_init_lock = threading.Lock()


def get_activity_log(storage=None) -> MMMXActivityLog:
    global _instance
    if _instance is None:
        with _init_lock:
            if _instance is None:
                _instance = MMMXActivityLog(storage=storage)
    elif storage is not None and _instance._storage is None:
        _instance.set_storage(storage)
    return _instance


def log_activity(
    event_type: str,
    message: str,
    session_id: Optional[str] = None,
    level: str = 'info',
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Module-level shortcut."""
    return get_activity_log().log_activity(
        event_type=event_type,
        message=message,
        session_id=session_id,
        level=level,
        data=data,
    )
