"""
MMM Activity Log — Background Activities Tracker

Maintains an in-memory + persisted ring buffer of background activity events
so the WebUI can show users what the algo is doing in real-time:
- Order placement, fill waits, repricing, fills, errors
- Heartbeat execution, adjustments, reversals
- Safety events, session state changes

Created: February 15, 2026
"""

import json
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import deque

log = logging.getLogger('mmm_activity')

# Persist file
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
ACTIVITY_FILE = os.path.join(DATA_DIR, 'mmm_activity_log.json')

# Maximum activities to keep in memory and on disk
# Fix #16: Increased from 200 to 500 for better post-crash debugging
MAX_ACTIVITIES = 500

# Activity types
ACTIVITY_TYPES = {
    # Order lifecycle
    'order_placing': 'Placing Order',
    'order_placed': 'Order Placed',
    'order_waiting_fill': 'Waiting for Fill',
    'order_fill_check': 'Checking Fill Status',
    'order_filled': 'Order Filled',
    'order_repricing': 'Repricing Order',
    'order_amended': 'Order Amended',
    'order_cancelled': 'Order Cancelled',
    'order_failed': 'Order Failed',

    # Entry
    'entry_starting': 'Starting Entry',
    'entry_complete': 'Entry Complete',
    'entry_failed': 'Entry Failed',

    # Session lifecycle
    'session_created': 'Session Created',
    'session_initialized': 'Session Initialized',
    'session_starting': 'Session Starting',
    'session_started': 'Session Started',
    'session_paused': 'Session Paused',
    'session_resumed': 'Session Resumed',
    'session_stopped': 'Session Stopped',

    # Heartbeat
    'heartbeat_start': 'Heartbeat Running',
    'heartbeat_complete': 'Heartbeat Complete',
    'heartbeat_error': 'Heartbeat Error',

    # Adjustments
    'adjustment_triggered': 'Adjustment Triggered',
    'adjustment_complete': 'Adjustment Complete',

    # Safety
    'safety_warning': 'Safety Warning',
    'safety_block': 'Safety Block',
    'trigger_stale': 'Stale Trigger',

    # General
    'info': 'Info',
    'warning': 'Warning',
    'error': 'Error',
}

# Severity levels
SEVERITY_INFO = 'info'
SEVERITY_SUCCESS = 'success'
SEVERITY_WARNING = 'warning'
SEVERITY_ERROR = 'error'
SEVERITY_PROGRESS = 'progress'  # For ongoing actions (placing, waiting)


class MMMActivityLog:
    """
    Thread-safe activity log for MMM background operations.

    Activities are stored in a ring buffer (deque) and persisted to disk.
    The WebUI polls this to show users what's happening behind the scenes.
    """

    def __init__(self):
        self._activities: deque = deque(maxlen=MAX_ACTIVITIES)
        self._load_from_disk()
        self._counter = 0
        # Recommendation #6: Activity log dedup tracking
        # Maps (type, session_id, message_prefix) → last_logged_timestamp
        self._dedup_cache: Dict[tuple, datetime] = {}
        self._DEDUP_INTERVAL_SECS = 30  # Suppress identical events within this window

    def _load_from_disk(self):
        """Load persisted activities on startup."""
        try:
            if os.path.exists(ACTIVITY_FILE):
                with open(ACTIVITY_FILE, 'r') as f:
                    data = json.load(f)
                    for item in data.get('activities', []):
                        self._activities.append(item)
                log.info(f"Loaded {len(self._activities)} activities from disk")
        except Exception as e:
            log.warning(f"Could not load activity log: {e}")

    def _save_to_disk(self):
        """Persist activities to disk (throttled — every 2nd write).

        Fix #16: Atomic write (write to .tmp then rename) prevents corruption
        on crash mid-write. Throttling reduced from 1-in-5 to 1-in-2.
        """
        self._counter += 1
        if self._counter % 2 != 0:
            return
        try:
            os.makedirs(os.path.dirname(ACTIVITY_FILE), exist_ok=True)
            tmp_file = ACTIVITY_FILE + '.tmp'
            with open(tmp_file, 'w') as f:
                json.dump({
                    'activities': list(self._activities),
                    'updated_at': datetime.utcnow().isoformat(),
                }, f, indent=2, default=str)
                f.flush()
                os.fsync(f.fileno())
            # Atomic rename — survives crash between write and rename
            os.rename(tmp_file, ACTIVITY_FILE)
        except Exception as e:
            log.warning(f"Could not save activity log: {e}")
            # Clean up temp file if rename failed
            try:
                if os.path.exists(tmp_file):
                    os.unlink(tmp_file)
            except Exception:
                pass

    def add(
        self,
        activity_type: str,
        message: str,
        session_id: str = None,
        severity: str = SEVERITY_INFO,
        details: Dict = None,
    ) -> Dict:
        """
        Add a new activity to the log.

        Args:
            activity_type: One of ACTIVITY_TYPES keys
            message: Human-readable description
            session_id: Associated session ID (optional)
            severity: info | success | warning | error | progress
            details: Additional structured data

        Returns:
            The activity dict that was added, or None if deduplicated
        """
        # Recommendation #6: Deduplicate spammy events
        # Only dedup types that fire every heartbeat; never dedup critical events
        _DEDUP_TYPES = {
            'heartbeat_start', 'heartbeat_complete', 'info', 'warning',
            'safety_warning', 'trigger_stale',
        }
        if activity_type in _DEDUP_TYPES:
            # Use first 80 chars of message as dedup key (ignores changing numbers)
            dedup_key = (activity_type, session_id or '', message[:80])
            now = datetime.utcnow()
            last = self._dedup_cache.get(dedup_key)
            if last and (now - last).total_seconds() < self._DEDUP_INTERVAL_SECS:
                return None  # Suppress duplicate
            self._dedup_cache[dedup_key] = now

            # Prune stale dedup entries every 100 adds
            if len(self._dedup_cache) > 500:
                cutoff = now
                self._dedup_cache = {
                    k: v for k, v in self._dedup_cache.items()
                    if (cutoff - v).total_seconds() < self._DEDUP_INTERVAL_SECS * 10
                }

        activity = {
            'id': f"act_{datetime.utcnow().strftime('%H%M%S')}_{len(self._activities) % 1000:03d}",
            'timestamp': datetime.utcnow().isoformat(),
            'type': activity_type,
            'type_label': ACTIVITY_TYPES.get(activity_type, activity_type),
            'message': message,
            'session_id': session_id,
            'severity': severity,
            'details': details or {},
        }

        self._activities.append(activity)
        self._save_to_disk()

        # Also emit via WebSocket for real-time updates
        try:
            from .mmm_websocket import emit_activity
            emit_activity(activity)
        except Exception:
            pass  # WebSocket not available

        return activity

    def get_recent(
        self,
        limit: int = 50,
        session_id: str = None,
        severity: str = None,
    ) -> List[Dict]:
        """
        Get recent activities, newest first.

        Args:
            limit: Max number to return
            session_id: Filter by session (optional)
            severity: Filter by severity (optional)

        Returns:
            List of activity dicts
        """
        items = list(self._activities)
        items.reverse()  # Newest first

        if session_id:
            items = [a for a in items if a.get('session_id') == session_id]
        if severity:
            items = [a for a in items if a.get('severity') == severity]

        return items[:limit]

    def clear(self, session_id: str = None):
        """Clear activities, optionally for a specific session only."""
        if session_id:
            self._activities = deque(
                (a for a in self._activities if a.get('session_id') != session_id),
                maxlen=MAX_ACTIVITIES,
            )
        else:
            self._activities.clear()
        self._save_to_disk()

    def resolve_progress(self, session_id: str = None):
        """
        Remove all 'progress' severity activities for a session.
        Call this when entry completes or fails to clear stale 'fetching...' messages.
        """
        def should_keep(a):
            if a.get('severity') != 'progress':
                return True
            if session_id and a.get('session_id') != session_id:
                return True
            return False

        before = len(self._activities)
        self._activities = deque(
            (a for a in self._activities if should_keep(a)),
            maxlen=MAX_ACTIVITIES,
        )
        removed = before - len(self._activities)
        if removed > 0:
            log.info(f"Resolved {removed} progress activities for session {session_id}")
            self._save_to_disk()
            # Emit refresh to frontend
            try:
                from .mmm_websocket import emit_activities_updated
                emit_activities_updated()
            except Exception:
                pass


# =============================================================================
# Singleton
# =============================================================================

_activity_instance = None


def get_activity_log() -> MMMActivityLog:
    """Get singleton activity log instance."""
    global _activity_instance
    if _activity_instance is None:
        _activity_instance = MMMActivityLog()
    return _activity_instance


# =============================================================================
# Convenience helpers — call these from executor, monitor, api
# =============================================================================

def log_activity(
    activity_type: str,
    message: str,
    session_id: str = None,
    severity: str = SEVERITY_INFO,
    details: Dict = None,
) -> Dict:
    """Shortcut to add an activity to the global log."""
    return get_activity_log().add(
        activity_type=activity_type,
        message=message,
        session_id=session_id,
        severity=severity,
        details=details,
    )


def resolve_progress_activities(session_id: str = None):
    """Clear all 'progress' activities for a session (call when entry done)."""
    return get_activity_log().resolve_progress(session_id)
