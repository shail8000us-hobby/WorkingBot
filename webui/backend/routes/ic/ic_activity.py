"""
IC Activity — Iron Condor Activity Logging

Standardized activity logging for the IC algo.
Each entry is tagged with algo='ic' for cross-algo filtering.

From IC_ALGO_PLAN.md §C.12.

Created: 2026-03-24
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

log = logging.getLogger('ic_activity')

# In-memory activity log (persisted via session state)
_activity_buffer = []
MAX_BUFFER_SIZE = 200


def log_activity(
    activity_type: str,
    message: str,
    session_id: str = '',
    severity: str = 'info',
    details: Dict[str, Any] = None,
) -> Dict:
    """
    Log an IC activity event.

    §C.12: Tagged with algo='ic' for isolation from MMM.

    Args:
        activity_type: Type of activity (e.g., 'cycle_opened', 'adjustment', 'exit')
        message: Human-readable message
        session_id: IC session ID
        severity: 'info' | 'warning' | 'error' | 'critical'
        details: Additional structured details

    Returns:
        The activity event dict
    """
    event = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'algo': 'ic',
        'type': activity_type,
        'message': message,
        'session_id': session_id,
        'severity': severity,
        'details': details or {},
    }

    _activity_buffer.append(event)

    # Trim buffer
    if len(_activity_buffer) > MAX_BUFFER_SIZE:
        _activity_buffer[:] = _activity_buffer[-MAX_BUFFER_SIZE:]

    # Also log to Python logger
    log_fn = getattr(log, severity, log.info)
    log_fn(f"[IC/{session_id}] {activity_type}: {message}")

    return event


def get_recent_activities(
    count: int = 50,
    session_id: str = None,
) -> list:
    """
    Get recent IC activity events.

    Args:
        count: Max events to return
        session_id: Filter by session ID (None = all sessions)

    Returns:
        List of activity events, newest first
    """
    events = _activity_buffer
    if session_id:
        events = [e for e in events if e.get('session_id') == session_id]
    return list(reversed(events[-count:]))


def clear_activities():
    """Clear the activity buffer."""
    _activity_buffer.clear()
