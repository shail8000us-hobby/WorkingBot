"""
IC WebSocket — Iron Condor

WebSocket event emission for real-time UI updates.
All events prefixed with 'ic_' to isolate from MMM events.

From IC_ALGO_PLAN.md §13.

Created: 2026-03-24
"""

import logging
import threading
from typing import Dict, Any
from datetime import datetime, timezone

log = logging.getLogger('ic_websocket')

# SocketIO instance — set during init
_socketio = None

# Emission failure tracking (same pattern as mmm_websocket)
_consecutive_failures = 0
_last_successful_emit = None
_FAILURE_THRESHOLD = 10
_ws_lock = threading.Lock()


def init_websocket(socketio):
    """Initialize WebSocket with the Flask-SocketIO instance."""
    global _socketio
    _socketio = socketio
    log.info("IC WebSocket initialized")


def get_ws_health() -> Dict:
    """Return WebSocket health metrics."""
    with _ws_lock:
        return {
            'consecutive_failures': _consecutive_failures,
            'last_successful_emit': _last_successful_emit.isoformat() if _last_successful_emit else None,
            'is_stale': _consecutive_failures >= _FAILURE_THRESHOLD,
            'socketio_initialized': _socketio is not None,
        }


def _emit(event: str, data: Dict[str, Any]):
    """Emit a WebSocket event with failure tracking."""
    global _consecutive_failures, _last_successful_emit

    if _socketio is None:
        with _ws_lock:
            _consecutive_failures += 1
        log.error(f"IC _socketio is None! Cannot emit {event}")
        return

    try:
        data['timestamp'] = datetime.now(timezone.utc).isoformat()
        _socketio.emit(event, data, namespace='/')
        with _ws_lock:
            _consecutive_failures = 0
            _last_successful_emit = datetime.now(timezone.utc)
    except Exception as e:
        with _ws_lock:
            _consecutive_failures += 1
            current_failures = _consecutive_failures
        log.error(f"IC WS emit {event} failed: {e} (failures={current_failures})")


# ─── IC-specific Events ───────────────────────────────────────────────────────

def emit_heartbeat(
    session_id: str,
    spot_price: float,
    unrealized_pnl: float,
    pnl_pct: float,
    portfolio_greeks: Dict,
    cycle_data: Dict = None,
    status: str = '',
    strategy_status: str = '',
):
    """Emit IC heartbeat data every interval."""
    payload = {
        'session_id': session_id,
        'spot_price': spot_price,
        'unrealized_pnl': unrealized_pnl,
        'pnl_pct': pnl_pct,
        'portfolio_greeks': portfolio_greeks,
        'status': status,
        'strategy_status': strategy_status,
    }
    if cycle_data:
        payload['cycle'] = cycle_data
    _emit('ic_heartbeat', payload)


def emit_status_change(session_id: str, old_status: str, new_status: str,
                       reason: str = ''):
    """Emit strategy status change."""
    _emit('ic_status_change', {
        'session_id': session_id,
        'old_status': old_status,
        'new_status': new_status,
        'reason': reason,
    })


def emit_cycle_opened(session_id: str, cycle_data: Dict):
    """Emit when a new cycle is opened."""
    _emit('ic_cycle_opened', {
        'session_id': session_id,
        'cycle': cycle_data,
    })


def emit_cycle_closed(session_id: str, cycle_summary: Dict):
    """Emit when a cycle is closed."""
    _emit('ic_cycle_closed', {
        'session_id': session_id,
        'cycle': cycle_summary,
    })


def emit_adjustment(
    session_id: str,
    adj_type: str,
    trigger: str,
    old_strikes: Dict,
    new_strikes: Dict,
    roll_credit: float,
    cumulative_roll_credit: float,
    adjustment_count: int,
):
    """Emit adjustment (roll) event."""
    _emit('ic_adjustment', {
        'session_id': session_id,
        'type': adj_type,
        'trigger': trigger,
        'old_strikes': old_strikes,
        'new_strikes': new_strikes,
        'roll_credit': roll_credit,
        'cumulative_roll_credit': cumulative_roll_credit,
        'adjustment_count': adjustment_count,
    })


def emit_safety(session_id: str, safety_event: Dict):
    """Emit safety event."""
    _emit('ic_safety', {
        'session_id': session_id,
        **safety_event,
    })


def emit_pnl_update(
    session_id: str,
    unrealized_pnl: float,
    max_profit: float,
    max_loss: float,
    pnl_pct: float,
    total_realized: float,
):
    """Emit P&L update every heartbeat."""
    _emit('ic_pnl_update', {
        'session_id': session_id,
        'unrealized_pnl': unrealized_pnl,
        'max_profit': max_profit,
        'max_loss': max_loss,
        'pnl_pct': pnl_pct,
        'total_realized': total_realized,
    })


def emit_session_created(session_id: str, session_summary: Dict):
    """Emit new session created event."""
    _emit('ic_session_created', {
        'session_id': session_id,
        'summary': session_summary,
    })


def emit_session_deleted(session_id: str):
    """Emit session deleted event."""
    _emit('ic_session_deleted', {
        'session_id': session_id,
    })


def emit_params_changed(session_id: str, changed_params: Dict):
    """Emit parameter hot-reload event."""
    _emit('ic_params_changed', {
        'session_id': session_id,
        'changed_params': changed_params,
    })


def emit_activity(activity: Dict):
    """Emit a background activity event for UI."""
    _emit('ic_activity', activity)


def emit_breach_alert(
    session_id: str,
    breach_type: str,
    spot: float,
    short_strike: float,
    distance_pct: float,
):
    """Emit breach proximity alert."""
    _emit('ic_breach_alert', {
        'session_id': session_id,
        'breach_type': breach_type,
        'spot': spot,
        'short_strike': short_strike,
        'distance_pct': distance_pct,
    })
