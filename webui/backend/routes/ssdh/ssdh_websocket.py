"""
SSDH WebSocket — Real-time UI event emission

Fire-and-forget emitters for the /ssdh SocketIO namespace.
Separate from MMM's default / namespace.

All emit functions swallow exceptions — never let WebSocket failures
affect trading logic.

Created: March 21, 2026
"""

import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional

log = logging.getLogger('ssdh_websocket')

# Module-level SocketIO singleton — set via init_websocket()
_socketio = None
_consecutive_failures = 0
_last_successful_emit = None
_FAILURE_THRESHOLD = 10
_ws_lock = threading.Lock()

SSDH_NAMESPACE = '/ssdh'


def init_websocket(socketio) -> None:
    """Store the Flask-SocketIO instance. Called from app.py after blueprint registration."""
    global _socketio
    _socketio = socketio
    log.info("SSDH WebSocket initialized (namespace: %s)", SSDH_NAMESPACE)


def get_ws_health() -> dict:
    """Returns WebSocket health metrics. Thread-safe snapshot."""
    with _ws_lock:
        return {
            'consecutive_failures':  _consecutive_failures,
            'last_successful_emit':  _last_successful_emit.isoformat() if _last_successful_emit else None,
            'is_stale':              _consecutive_failures >= _FAILURE_THRESHOLD,
            'socketio_initialized':  _socketio is not None,
        }


def _emit(event: str, data: Dict[str, Any]) -> None:
    """
    Internal: emit to /ssdh namespace.
    Tracks consecutive failures. After _FAILURE_THRESHOLD failures, flags as stale.
    """
    global _consecutive_failures, _last_successful_emit

    if _socketio is None:
        with _ws_lock:
            _consecutive_failures += 1
        log.error("_socketio is None — cannot emit %s", event)
        return

    try:
        data['timestamp'] = datetime.now(timezone.utc).isoformat()
        _socketio.emit(event, data, namespace=SSDH_NAMESPACE)
        with _ws_lock:
            _consecutive_failures = 0
            _last_successful_emit = datetime.now(timezone.utc)
    except Exception as e:
        with _ws_lock:
            _consecutive_failures += 1
            current = _consecutive_failures
        log.error("Failed to emit %s: %s (consecutive_failures=%d)", event, e, current)
        if current == _FAILURE_THRESHOLD:
            log.critical(
                "SSDH WebSocket stale! %d consecutive emission failures. "
                "UI may be out of sync.", _FAILURE_THRESHOLD
            )


# =============================================================================
# Public emit functions
# =============================================================================

def emit_state_update(session_id: str, session: dict) -> None:
    """
    Full session snapshot. Emitted every heartbeat.
    Event: 'ssdh_state_update'
    """
    from .ssdh_state import get_active_positions, ENTRY_COMPLETE
    from .ssdh_engine import OPTEngine
    engine = OPTEngine()
    time_remaining = engine.compute_time_remaining(session)

    active = get_active_positions(session)
    positions_payload = [
        {
            'pos_id':          p['pos_id'],
            'side':            p['side'],
            'direction':       p['direction'],
            'pos_type':        p['pos_type'],
            'strike':          p['strike'],
            'lots':            p['lots'],
            'entry_premium':   p['entry_premium'],
            'current_premium': p.get('current_premium'),
            'unrealized_pnl':  p.get('unrealized_pnl', 0.0),
            'status':          p['status'],
        }
        for p in active
    ]

    _emit('ssdh_state_update', {
        'session_id':        session_id,
        'status':            session.get('status'),
        'entry_state':       session.get('entry_state'),
        'positions':         positions_payload,
        'net_pnl':           session.get('net_pnl', 0.0),
        'unrealized_pnl':    session.get('unrealized_pnl', 0.0),
        'realized_pnl':      session.get('realized_pnl', 0.0),
        'total_fees':        session.get('total_fees', 0.0),
        'peak_net_pnl':      session.get('peak_net_pnl', 0.0),
        'time_remaining_secs': time_remaining,
        'structure_ok':      session.get('_structure_ok', True),
    })


def emit_leg_entry(session_id: str, position: dict) -> None:
    """Emitted when a leg fills during entry. Event: 'ssdh_leg_entry'"""
    _emit('ssdh_leg_entry', {
        'session_id':    session_id,
        'pos_id':        position['pos_id'],
        'side':          position['side'],
        'direction':     position['direction'],
        'pos_type':      position['pos_type'],
        'strike':        position['strike'],
        'lots':          position['lots'],
        'entry_premium': position['entry_premium'],
    })


def emit_leg_close(session_id: str, position: dict, realized_pnl: float) -> None:
    """Emitted when a leg closes. Event: 'ssdh_leg_close'"""
    _emit('ssdh_leg_close', {
        'session_id':   session_id,
        'pos_id':       position['pos_id'],
        'side':         position['side'],
        'direction':    position['direction'],
        'close_reason': position.get('close_reason'),
        'close_premium':position.get('close_premium'),
        'realized_pnl': realized_pnl,
    })


def emit_wind_down(session_id: str, reason: str) -> None:
    """Event: 'ssdh_wind_down'"""
    _emit('ssdh_wind_down', {'session_id': session_id, 'reason': reason})


def emit_session_closed(session_id: str, session: dict) -> None:
    """Event: 'ssdh_session_closed'"""
    from datetime import datetime as _dt, timezone as _tz
    started = session.get('started_at')
    closed  = session.get('closed_at')
    duration = 0
    if started and closed:
        try:
            s = _dt.fromisoformat(started.replace('Z', '+00:00'))
            c = _dt.fromisoformat(closed.replace('Z', '+00:00'))
            duration = int((c - s).total_seconds())
        except Exception:
            pass

    _emit('ssdh_session_closed', {
        'session_id':    session_id,
        'net_pnl':       session.get('net_pnl', 0.0),
        'realized_pnl':  session.get('realized_pnl', 0.0),
        'total_fees':    session.get('total_fees', 0.0),
        'close_reason':  session.get('close_reason'),
        'duration_secs': duration,
    })


def emit_structure_break(session_id: str, missing_leg: str) -> None:
    """Event: 'ssdh_structure_break'"""
    _emit('ssdh_structure_break', {
        'session_id':  session_id,
        'missing_leg': missing_leg,
    })


def emit_vega_spike(session_id: str, ce_ratio: float, pe_ratio: float) -> None:
    """Event: 'ssdh_vega_spike'"""
    _emit('ssdh_vega_spike', {
        'session_id': session_id,
        'ce_ratio':   ce_ratio,
        'pe_ratio':   pe_ratio,
        'avg_ratio':  (ce_ratio + pe_ratio) / 2 if (ce_ratio and pe_ratio) else 0,
    })


def emit_kill_switch(session_id: str) -> None:
    """Event: 'ssdh_kill_switch'"""
    _emit('ssdh_kill_switch', {'session_id': session_id})
