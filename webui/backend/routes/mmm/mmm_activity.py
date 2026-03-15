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
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
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
    'order_retrying': 'Retrying Order',

    # Entry
    'entry_starting': 'Starting Entry',
    'entry_complete': 'Entry Complete',
    'entry_failed': 'Entry Failed',
    'entry_rollback': 'Rolling Back Entry',
    'entry_rollback_ok': 'Rollback Complete',
    'entry_rollback_failed': 'Rollback Failed',

    # Session lifecycle
    'session_created': 'Session Created',
    'session_initialized': 'Session Initialized',
    'session_starting': 'Session Starting',
    'session_started': 'Session Started',
    'session_paused': 'Session Paused',
    'session_resumed': 'Session Resumed',
    'session_stopped': 'Session Stopped',

    # Adjustments
    'adjustment_triggered': 'Adjustment Triggered',
    'adjustment_complete': 'Adjustment Complete',
    'adjustment_skipped': 'Adjustment Skipped',
    'strike_shift': 'Strike Shift',
    'shift_post_fill_error': 'Shift Post-Fill Error',
    'trigger_cleared_by_close_at_5': 'Trigger Cleared',

    # Safety
    'safety_warning': 'Safety Warning',
    'safety_block': 'Safety Block',
    'trigger_stale': 'Stale Trigger',
    'max_loss_breach': 'Max Loss Breach',
    'adjustments_stopped': 'Adjustments Stopped',

    # Close-at-5
    'close_at_5': 'Position Closed',

    # Wind-down & Margin
    'wind_down': 'Wind-Down',
    'atm_wind_down': 'ATM Wind-Down',
    'atm_auto_close': 'ATM Auto-Close',
    'margin_wind_down': 'Margin Wind-Down',
    'margin_block_sells': 'Margin Block',

    # Regime
    'regime_control': 'Regime Control',
    'regime_block': 'Regime Block',
    'regime_emergency': 'Regime Emergency',

    # Both sides
    'both_sides_auto_decision': 'Both Sides Decision',

    # Perp Hedge
    'perp_hedge': 'Perp Hedge',

    # Emergency
    'emergency_order': 'Emergency Order',
    'emergency_placing': 'Emergency Placing',
    'emergency_filled': 'Emergency Filled',
    'emergency_error': 'Emergency Error',

    # Circuit breaker
    'heartbeat_partial': 'Partial Heartbeat',
    'heartbeat_miss': 'Missed Heartbeat',
    'heartbeat_error': 'Heartbeat Error',

    # Stale data
    'stale_price_warning': 'Stale Price',

    # Lot lifecycle (M1/M2/M3/Split Ledger)
    'harvest': 'Position Harvested',
    'recycle': 'Lot Recycling',
    'shift_recycle': 'Shift-Time Recycle',
    'rebalance_boost': 'Rebalance Boost',
    'trend_boost': 'Trend Boost',
    'whipsaw_guard': 'Whipsaw Guard',
    'atm_shield': 'ATM Shield',

    # Breakeven Engine
    'breakeven_zone_change': 'Breakeven Zone Change',
    'breakeven_band_contracting': 'Breakeven Band Contracting',
    'breakeven_narrow_band': 'Narrow Breakeven Band',

    # Gamma Detector Engine
    'gamma_zone_change': 'Gamma Zone Change',
    'gamma_danger_detected': 'Gamma Danger Detected',

    # FSU: Favorable Scale-Up
    'scale_up_triggered': 'Scale-Up Triggered',
    'scale_up_complete': 'Scale-Up Complete',
    'scale_up_failed': 'Scale-Up Failed',
    'scale_up_no_strikes': 'Scale-Up No Strikes',

    # Hot reload
    'hot_reload': 'Hot Reload',

    # General
    'info': 'Info',
    'warning': 'Warning',
    'error': 'Error',
}

# Activity categories for frontend filtering
ACTIVITY_CATEGORIES = {
    'orders': {'order_placing', 'order_placed', 'order_waiting_fill', 'order_fill_check',
               'order_filled', 'order_repricing', 'order_amended', 'order_cancelled',
               'order_failed', 'order_retrying', 'entry_starting', 'entry_complete',
               'entry_failed', 'entry_rollback', 'entry_rollback_ok', 'entry_rollback_failed',
               'emergency_order', 'emergency_placing', 'emergency_filled', 'emergency_error'},
    'adjustments': {'adjustment_triggered', 'adjustment_complete', 'adjustment_skipped',
                    'strike_shift', 'shift_post_fill_error',
                    'trigger_cleared_by_close_at_5',
                    'close_at_5', 'wind_down', 'atm_wind_down', 'atm_auto_close',
                    'margin_wind_down', 'margin_block_sells', 'perp_hedge',
                    'both_sides_auto_decision',
                    'harvest', 'recycle', 'shift_recycle', 'rebalance_boost', 'trend_boost',
                    'scale_up_triggered', 'scale_up_complete', 'scale_up_failed',
                    'scale_up_no_strikes'},
    'safety': {'safety_warning', 'safety_block', 'trigger_stale', 'max_loss_breach',
               'adjustments_stopped', 'regime_control', 'regime_block', 'regime_emergency',
               'stale_price_warning', 'heartbeat_partial', 'heartbeat_miss', 'heartbeat_error',
               'whipsaw_guard',
               'breakeven_zone_change', 'breakeven_band_contracting', 'breakeven_narrow_band',
               'gamma_zone_change', 'gamma_danger_detected'},
    'system': {'session_created', 'session_initialized', 'session_starting', 'session_started',
               'session_paused', 'session_resumed', 'session_stopped', 'hot_reload',
               'info', 'warning', 'error'},
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
        self._lock = threading.RLock()  # C-8 fix: thread-safe access
        self._activities: deque = deque(maxlen=MAX_ACTIVITIES)
        # M-21 fix: create directory in __init__ not in _save_to_disk()
        os.makedirs(os.path.dirname(ACTIVITY_FILE), exist_ok=True)
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

    # M-7 fix: activity types that must always persist regardless of throttle
    _ALWAYS_PERSIST_TYPES = frozenset({
        'safety_event', 'auto_close', 'max_loss', 'emergency',
        'session_stop', 'session_stopped', 'session_pause', 'session_paused',
        'watchdog', 'error',
    })

    def _should_persist(self, activity: Dict) -> bool:
        """M-7 fix: determine if this activity bypasses the throttle.

        Critical and error severity events, plus safety/session-lifecycle event
        types, always write to disk so post-crash debugging has full context.
        """
        # Always persist critical/error/warning severity
        if activity.get('severity') in ('critical', 'error', 'warning'):
            return True
        # Always persist important lifecycle types
        if activity.get('type') in self._ALWAYS_PERSIST_TYPES:
            return True
        # For all other events: apply the 1-in-2 throttle
        return self._counter % 2 == 0

    def _save_to_disk(self, activity: Dict = None):
        """Persist activities to disk (throttled — every 2nd write).

        Fix #16: Atomic write (write to .tmp then rename) prevents corruption
        on crash mid-write. Throttling reduced from 1-in-5 to 1-in-2.
        M-7 fix: critical/error/warning severity and safety event types bypass
        the throttle so they are always persisted for post-crash debugging.
        Fix: use unique tmp file per call to avoid race between concurrent
        heartbeat threads (Thread A renames .tmp away before Thread B can).
        H-12 fix: lock around os.rename() critical section.
        """
        self._counter += 1
        if activity is not None and not self._should_persist(activity):
            return
        tmp_file = None
        try:
            import tempfile
            fd, tmp_file = tempfile.mkstemp(
                suffix='.tmp',
                dir=os.path.dirname(ACTIVITY_FILE),
                prefix='mmm_activity_',
            )
            with self._lock:
                with os.fdopen(fd, 'w') as f:
                    json.dump({
                        'activities': list(self._activities),
                        'updated_at': datetime.now(timezone.utc).isoformat(),
                    }, f, indent=2, default=str)
                    f.flush()
                    os.fsync(f.fileno())
                # Atomic rename — survives crash between write and rename
                os.rename(tmp_file, ACTIVITY_FILE)
        except Exception as e:
            log.warning(f"Could not save activity log: {e}")
            # Clean up temp file if rename failed
            try:
                if tmp_file and os.path.exists(tmp_file):
                    os.unlink(tmp_file)
            except Exception as _e:
                log.error(f"Temp cleanup failed: {_e}")  # L-7 fix

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
            'info', 'warning', 'safety_warning', 'trigger_stale',
            'wind_down', 'regime_control',
        }
        if activity_type in _DEDUP_TYPES:
            # Use first 80 chars of message as dedup key (ignores changing numbers)
            dedup_key = (activity_type, session_id or '', message[:80])
            now = datetime.now(timezone.utc)
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

        # Determine category for frontend filtering
        category = 'system'
        for cat, types in ACTIVITY_CATEGORIES.items():
            if activity_type in types:
                category = cat
                break

        # Audit fix: monotonic _id_counter guarantees uniqueness (collision with same-second + same-index is fixed)
        self._id_counter = getattr(self, '_id_counter', 0) + 1
        activity = {
            'id': f"act_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{self._id_counter:06d}",
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'type': activity_type,
            'type_label': ACTIVITY_TYPES.get(activity_type, activity_type),
            'category': category,
            'message': message,
            'session_id': session_id,
            'severity': severity,
            'details': details or {},
        }

        self._activities.append(activity)
        self._save_to_disk(activity)  # M-7 fix: pass activity for critical bypass

        # Also emit via WebSocket for real-time updates
        try:
            from .mmm_websocket import emit_activity
            emit_activity(activity)
        except ImportError:
            pass  # WebSocket not available
        except Exception as e:
            log.warning(f"Activity WS emit failed: {e}")  # M-23 fix

        return activity

    def get_recent(
        self,
        limit: int = 50,
        session_id: str = None,
        severity: str = None,
        category: str = None,
    ) -> List[Dict]:
        """
        Get recent activities, newest first.

        Args:
            limit: Max number to return
            session_id: Filter by session (optional)
            severity: Filter by severity (optional)
            category: Filter by category: orders|adjustments|safety|system (optional)

        Returns:
            List of activity dicts
        """
        with self._lock:
            items = list(self._activities)
        items.reverse()  # Newest first

        if session_id:
            items = [a for a in items if a.get('session_id') == session_id]
        if severity:
            items = [a for a in items if a.get('severity') == severity]
        if category:
            items = [a for a in items if a.get('category') == category]

        return items[:limit]

    def clear(self, session_id: str = None):
        """Clear activities, optionally for a specific session only."""
        with self._lock:  # M-22 fix: atomic clear under lock
            if session_id:
                to_keep = [a for a in self._activities if a.get('session_id') != session_id]
                self._activities.clear()
                for a in to_keep:
                    self._activities.append(a)
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
        with self._lock:  # M-24 fix: atomic resolve under lock
            to_keep = [a for a in self._activities if should_keep(a)]
            self._activities.clear()
            for a in to_keep:
                self._activities.append(a)
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
