"""
SSDH Activity Log — Background Activities Tracker

In-memory ring buffer + persisted JSON log of SSDH session events.
Separate from MMM's mmm_activity_log.json.

Ring buffer capped at 500 entries. Atomic write on every change.
Fire-and-forget: log_activity() never raises.

Created: March 21, 2026
"""

import json
import logging
import os
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger('ssdh_activity')

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'data'
)
ACTIVITY_FILE = os.path.join(DATA_DIR, 'ssdh_activity_log.json')
MAX_ACTIVITIES = 500

# =============================================================================
# Activity types
# =============================================================================

ACTIVITY_TYPES = {
    # Order lifecycle
    'order_placing':          'Placing Order',
    'order_placed':           'Order Placed',
    'order_filled':           'Order Filled',
    'order_failed':           'Order Failed',
    'order_repricing':        'Repricing Order',
    'order_cancelled':        'Order Cancelled',

    # Entry
    'entry_starting':         'Starting Entry',
    'entry_leg_filled':       'Leg Filled',
    'entry_complete':         'Entry Complete',
    'entry_failed':           'Entry Failed',
    'entry_rollback':         'Rolling Back Entry',
    'entry_rollback_ok':      'Entry Rollback Complete',
    'entry_rollback_failed':  'Entry Rollback Failed',

    # Session lifecycle
    'session_created':        'Session Created',
    'session_started':        'Session Started',
    'session_stopped':        'Session Stopped',
    'session_closed':         'Session Closed',

    # Heartbeat
    'heartbeat_pnl':          'Heartbeat P&L',
    'heartbeat_error':        'Heartbeat Error',
    'premium_fetch_failed':   'Premium Fetch Failed',
    'premium_stale':          'Using Stale Premium',

    # Exit
    'wind_down_started':      'Wind Down Started',
    'leg_closing':            'Closing Leg',
    'leg_closed':             'Leg Closed',
    'leg_close_failed':       'Leg Close Failed',
    'exit_complete':          'Exit Complete',
    'exit_partial':           'Exit Partial',

    # Safety
    'max_loss_breach':        'Max Loss Breached',
    'trailing_stop':          'Trailing Stop Triggered',
    'time_exit':              'Time Window Elapsed',
    'structure_break':        'Structure Integrity Broken',
    'vega_spike':             'Vega Spike Detected',
    'margin_warning':         'Margin Warning',
    'circuit_open':           'Circuit Breaker Open',

    # Kill switch
    'kill_switch':            'Kill Switch Activated',

    # Reconciliation
    'reconciliation_run':     'Reconciliation Run',
    'reconciliation_mismatch':'Reconciliation Mismatch',
}

# =============================================================================
# Ring buffer
# =============================================================================

_activities: deque = deque(maxlen=MAX_ACTIVITIES)
_lock = threading.Lock()


def _persist_async() -> None:
    """Write ring buffer to ACTIVITY_FILE atomically (temp → fsync → rename)."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        snapshot = list(_activities)
        tmp = ACTIVITY_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, ACTIVITY_FILE)
    except Exception as e:
        log.warning("ssdh_activity: persist failed: %s", e)


def log_activity(
    activity_type: str,
    message: str,
    session_id: Optional[str] = None,
    severity: str = 'info',
    details: Optional[dict] = None,
) -> None:
    """
    Fire-and-forget. Never raises.
    severity: 'info' | 'success' | 'warning' | 'error' | 'progress'
    """
    try:
        label = ACTIVITY_TYPES.get(activity_type, activity_type)
        entry = {
            'type':       activity_type,
            'label':      label,
            'message':    str(message),
            'session_id': session_id,
            'severity':   severity,
            'details':    details or {},
            'timestamp':  datetime.now(timezone.utc).isoformat(),
        }
        with _lock:
            _activities.append(entry)
        _persist_async()
    except Exception as e:
        log.warning("log_activity failed (swallowed): %s", e)


def get_recent_activities(session_id: Optional[str] = None, limit: int = 100) -> list:
    """Returns recent activities, optionally filtered by session_id."""
    with _lock:
        snapshot = list(_activities)

    if session_id:
        snapshot = [a for a in snapshot if a.get('session_id') == session_id]

    return snapshot[-limit:]


def load_persisted_activities() -> None:
    """Load persisted activities from disk into the in-memory ring buffer on startup."""
    try:
        if not os.path.exists(ACTIVITY_FILE):
            return
        with open(ACTIVITY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            with _lock:
                for entry in data[-MAX_ACTIVITIES:]:
                    _activities.append(entry)
    except Exception as e:
        log.warning("load_persisted_activities failed: %s", e)
