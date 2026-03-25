"""
IC API — Iron Condor

REST endpoints for IC session management:
- Session CRUD (create, read, list, delete)
- Session control (start, pause, resume, stop)
- Parameter management (get, update with hot-reload)
- Cycle history and adjustment log

From IC_ALGO_PLAN.md §12.

Created: 2026-03-24
"""

import logging
import threading
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify

from .ic_storage import get_storage
from .ic_state import create_session
from .ic_config import DEFAULT_PARAMS, validate_params, get_param_info, get_hot_reload_params
from .ic_websocket import (
    emit_status_change, emit_params_changed,
    emit_session_created, emit_session_deleted,
)
from .ic_constants import (
    STATUS_IDLE, STATUS_RUNNING, STATUS_PAUSED, STATUS_STOPPED,
    STRATEGY_IDLE,
)

log = logging.getLogger('ic_api')

# ─── Blueprint ────────────────────────────────────────────────────────────────

ic_bp = Blueprint('ic', __name__, url_prefix='/api/ic')

# In-memory monitor registry
_monitors = {}  # session_id -> ICMonitor


# =============================================================================
# Session CRUD
# =============================================================================

@ic_bp.route('/sessions', methods=['GET'])
def list_sessions():
    """
    List all IC sessions.

    Query params:
        active_only: bool - If true, only return active sessions

    Returns:
        {success: true, sessions: [...], count: int}
    """
    try:
        active_only = request.args.get('active_only', 'false').lower() == 'true'
        storage = get_storage()
        sessions = storage.list_sessions(active_only=active_only)

        return jsonify({
            'success': True,
            'sessions': sessions,
            'count': len(sessions),
        })

    except Exception as e:
        log.exception("Failed to list IC sessions")
        return jsonify({'success': False, 'error': str(e)}), 500


@ic_bp.route('/session/<session_id>', methods=['GET'])
def get_session(session_id: str):
    """
    Get a specific session by ID.

    Returns:
        {success: true, session: {...}}
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}',
            }), 404

        return jsonify({'success': True, 'session': session})

    except Exception as e:
        log.exception(f"Failed to get IC session {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ic_bp.route('/session/create', methods=['POST'])
def create_session_endpoint():
    """
    Create a new IC session.

    Request body:
        {
            name: str (optional),
            params: {
                lots: int,
                expiry_dte: int,
                wing_width_usd: float,
                short_put_delta_target: float,
                short_call_delta_target: float,
                simulate: bool,
                ... (any key from DEFAULT_PARAMS)
            }
        }

    Returns:
        {success: true, session: {...}}
    """
    try:
        data = request.get_json() or {}

        # Validate parameters
        user_params = data.get('params', {})
        validated, errors = validate_params(user_params)
        if errors:
            return jsonify({
                'success': False,
                'error': 'Parameter validation failed',
                'details': errors,
            }), 400

        # Create session state
        name = data.get('name', 'BTC IC Weekly')
        session = create_session(name=name, params=validated)

        # Persist
        storage = get_storage()
        storage.save_session(session)

        # Emit WebSocket
        emit_session_created(session['session_id'], {
            'session_id': session['session_id'],
            'name': session['name'],
            'status': session['status'],
            'strategy_status': session['strategy_status'],
            'created_at': session['created_at'],
        })

        log.info(f"Created IC session {session['session_id']}")

        return jsonify({
            'success': True,
            'session': session,
        }), 201

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        log.exception("Failed to create IC session")
        return jsonify({'success': False, 'error': str(e)}), 500


@ic_bp.route('/session/<session_id>', methods=['DELETE'])
def delete_session(session_id: str):
    """Delete a session. Only allowed for IDLE or STOPPED sessions."""
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({
                'success': True,
                'message': f'Session {session_id} not found (already deleted)',
            })

        status = session.get('status', STATUS_IDLE)
        if status not in (STATUS_IDLE, STATUS_STOPPED):
            return jsonify({
                'success': False,
                'error': f"Cannot delete session in {status} state. Stop it first.",
            }), 400

        storage.delete_session(session_id)
        emit_session_deleted(session_id)
        log.info(f"Deleted IC session {session_id}")

        return jsonify({
            'success': True,
            'message': f'Session {session_id} deleted',
        })

    except Exception as e:
        log.exception(f"Failed to delete IC session {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Session Control
# =============================================================================

@ic_bp.route('/session/<session_id>/start', methods=['POST'])
def start_session(session_id: str):
    """
    Start an IC session (begins IC heartbeat monitoring + auto-cycle).
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}',
            }), 404

        status = session.get('status', STATUS_IDLE)
        if status not in (STATUS_IDLE, STATUS_PAUSED):
            return jsonify({
                'success': False,
                'error': f"Cannot start session in {status} state. Must be IDLE or PAUSED.",
            }), 400

        old_status = status
        session['status'] = STATUS_RUNNING
        # strategy_status will transition to ENTRY_PENDING in the monitor loop

        storage.save_session(session)

        # Start the monitor
        from .ic_monitor import ICMonitor
        if session_id in _monitors:
            _monitors[session_id].stop()

        monitor = ICMonitor(session_id, session)
        _monitors[session_id] = monitor
        monitor.start()

        emit_status_change(session_id, old_status, STATUS_RUNNING, 'Started')
        log.info(f"IC session {session_id} started")

        from .ic_activity import log_activity
        log_activity('session_started',
            f"Session {session_id} is now RUNNING",
            session_id=session_id, severity='info')

        return jsonify({
            'success': True,
            'message': f'Session {session_id} started',
            'status': STATUS_RUNNING,
        })

    except Exception as e:
        log.exception(f"Failed to start IC session {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ic_bp.route('/session/<session_id>/pause', methods=['POST'])
def pause_session(session_id: str):
    """Pause a running IC session."""
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        if session.get('status') != STATUS_RUNNING:
            return jsonify({
                'success': False,
                'error': f"Can only pause RUNNING sessions",
            }), 400

        session['status'] = STATUS_PAUSED
        storage.save_session(session)

        # Monitor will self-pause by checking status
        if session_id in _monitors:
            _monitors[session_id].session['status'] = STATUS_PAUSED

        emit_status_change(session_id, STATUS_RUNNING, STATUS_PAUSED, 'Paused by user')
        log.info(f"IC session {session_id} paused")

        return jsonify({'success': True, 'status': STATUS_PAUSED})

    except Exception as e:
        log.exception(f"Failed to pause IC session {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ic_bp.route('/session/<session_id>/resume', methods=['POST'])
def resume_session(session_id: str):
    """Resume a paused IC session."""
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        if session.get('status') != STATUS_PAUSED:
            return jsonify({
                'success': False,
                'error': f"Can only resume PAUSED sessions",
            }), 400

        session['status'] = STATUS_RUNNING
        storage.save_session(session)

        if session_id in _monitors:
            _monitors[session_id].session['status'] = STATUS_RUNNING

        emit_status_change(session_id, STATUS_PAUSED, STATUS_RUNNING, 'Resumed by user')
        log.info(f"IC session {session_id} resumed")

        return jsonify({'success': True, 'status': STATUS_RUNNING})

    except Exception as e:
        log.exception(f"Failed to resume IC session {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ic_bp.route('/session/<session_id>/stop', methods=['POST'])
def stop_session(session_id: str):
    """Stop an IC session completely."""
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        old_status = session.get('status')

        # Stop the monitor
        if session_id in _monitors:
            _monitors[session_id].stop()
            del _monitors[session_id]

        session['status'] = STATUS_STOPPED
        storage.save_session(session)

        emit_status_change(session_id, old_status, STATUS_STOPPED, 'Stopped by user')
        log.info(f"IC session {session_id} stopped")

        return jsonify({'success': True, 'status': STATUS_STOPPED})

    except Exception as e:
        log.exception(f"Failed to stop IC session {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Parameters
# =============================================================================

@ic_bp.route('/session/<session_id>/params', methods=['GET'])
def get_params(session_id: str):
    """Get session parameters with metadata."""
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        return jsonify({
            'success': True,
            'params': session.get('params', {}),
            'param_info': get_param_info(),
        })

    except Exception as e:
        log.exception(f"Failed to get IC params for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ic_bp.route('/session/<session_id>/params', methods=['PUT'])
def update_params(session_id: str):
    """
    Update session parameters (with hot-reload validation).

    Request body:
        { params: { key: value, ... } }
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        data = request.get_json() or {}
        new_params = data.get('params', {})

        # Check hot-reload restrictions if running
        is_running = session.get('status') == STATUS_RUNNING
        validated, errors = validate_params(new_params, hot_only=is_running)

        if errors:
            return jsonify({
                'success': False,
                'error': 'Validation failed',
                'details': errors,
            }), 400

        # Merge
        current_params = session.get('params', {})
        current_params.update(validated)
        session['params'] = current_params

        storage.save_session(session)

        # Update in-memory monitor if running
        if session_id in _monitors:
            _monitors[session_id].session['params'] = current_params

        emit_params_changed(session_id, validated)
        log.info(f"IC session {session_id} params updated: {list(validated.keys())}")

        return jsonify({
            'success': True,
            'params': current_params,
            'updated': list(validated.keys()),
        })

    except Exception as e:
        log.exception(f"Failed to update IC params for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ic_bp.route('/defaults', methods=['GET'])
def get_defaults():
    """Get default IC parameters and their metadata."""
    return jsonify({
        'success': True,
        'defaults': DEFAULT_PARAMS,
        'param_info': get_param_info(),
    })


# =============================================================================
# Cycle History & Activity
# =============================================================================

@ic_bp.route('/session/<session_id>/cycles', methods=['GET'])
def get_cycle_history(session_id: str):
    """Get cycle history for a session."""
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        history = session.get('cycle_history', [])
        current = session.get('current_cycle')

        return jsonify({
            'success': True,
            'cycle_history': history,
            'current_cycle': current,
            'cycles_completed': session.get('cycles_completed', 0),
            'total_realized_pnl': session.get('total_realized_pnl', 0),
        })

    except Exception as e:
        log.exception(f"Failed to get IC cycle history for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ic_bp.route('/session/<session_id>/activities', methods=['GET'])
def get_activities(session_id: str):
    """Get recent activity log for a session."""
    try:
        from .ic_activity import get_recent_activities
        count = int(request.args.get('count', 50))
        activities = get_recent_activities(count=count, session_id=session_id)

        return jsonify({
            'success': True,
            'activities': activities,
            'count': len(activities),
        })

    except Exception as e:
        log.exception(f"Failed to get IC activities for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500
