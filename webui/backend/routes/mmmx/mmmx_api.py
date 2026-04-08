"""
MMMX API — Flask Blueprint for MMMX REST Routes

Phase 1 routes (minimal — no trigger logic yet):
  POST   /api/mmmx/session                    Create new session
  GET    /api/mmmx/sessions                   List all sessions
  GET    /api/mmmx/session/<id>               Get session by ID
  PATCH  /api/mmmx/session/<id>/params        Hot-reload params
  POST   /api/mmmx/session/<id>/stop          Stop session monitor
  GET    /api/mmmx/session/<id>/audit         Get audit log
  GET    /api/mmmx/session/<id>/activity      Get activity log
  GET    /api/mmmx/session/<id>/param-history Get param change history

Spec: MMMX_IMPLEMENTATION_PLAN.md Section 1 + 4.

Isolation: Zero runtime imports from the MMM route package.
"""

import asyncio
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

from flask import Blueprint, jsonify, request

log = logging.getLogger('mmmx_api')

mmmx_bp = Blueprint('mmmx', __name__)


def _err(message: str, status: int = 400):
    return jsonify({'ok': False, 'error': message}), status


def _ok(data: Any = None, **kwargs):
    payload = {'ok': True}
    if data is not None:
        payload['data'] = data
    payload.update(kwargs)
    return jsonify(payload), 200


def _stop_session_internal(session_id: str, reason: str, source: str = 'operator_stop'):
    """
    Shared stop flow used by /stop and /kill-switch.

    Returns:
      {
        'ok': bool,
        'status': int,
        'error': str,
        'session': dict,
        'monitor_alive': bool,
      }
    """
    from .mmmx_storage import get_storage
    from .mmmx_monitor import stop_session_monitor, get_monitor
    from .mmmx_state import transition_status
    from .mmmx_websocket import emit_status_change, emit_session_stopped
    from .mmmx_activity import log_activity

    storage = get_storage()
    session = storage.load_session(session_id)
    if session is None:
        return {
            'ok': False,
            'status': 404,
            'error': f"Session not found: {session_id}",
        }

    # Stop the monitor thread/listener pair (terminal stop semantics).
    stop_session_monitor(session_id, reason=reason)

    old_status = session.get('status', 'RUNNING')
    if old_status in ('RUNNING', 'PAUSED', 'GATES_PASSED'):
        try:
            transition_status(session, 'COMPLETE', reason=reason)
        except ValueError as exc:
            log.warning(f"_stop_session_internal: illegal transition from {old_status}: {exc}")

    current_gen = storage.get_generation(session_id)
    try:
        storage.save_session(session, expected_gen=current_gen)
    except Exception as exc:
        log.error(f"_stop_session_internal save error: {exc}")

    try:
        emit_status_change(session_id, old_status, session.get('status', old_status), reason)
        emit_session_stopped(session_id, reason)
    except Exception:
        pass

    log_activity(
        event_type='session_stopped',
        message=f"Session stopped: {reason}",
        session_id=session_id,
        data={
            'reason': reason,
            'source': source,
            'old_status': old_status,
            'new_status': session.get('status'),
        },
    )

    monitor = get_monitor(session_id)
    return {
        'ok': True,
        'session': session,
        'monitor_alive': monitor.is_alive() if monitor else False,
    }


# ── POST /api/mmmx/session ─────────────────────────────────────────────────────

@mmmx_bp.route('/api/mmmx/session', methods=['POST'])
def create_session():
    """
    Create a new MMMX session in DRAFT state.

    Body (JSON): optional params overrides merged onto defaults.
    Returns: {ok, session_id, session}
    """
    from .mmmx_config import validate_params, ConfigError
    from .mmmx_state import create_session as _create
    from .mmmx_storage import get_storage
    from .mmmx_activity import log_activity
    from .mmmx_websocket import emit_session_created

    body = request.get_json(silent=True) or {}
    params = body.get('params', {})

    try:
        validate_params(params)
    except ConfigError as exc:
        return _err(str(exc))

    session = _create(params=params if params else None)
    storage = get_storage()

    try:
        storage.save_session(session, expected_gen=None)
    except Exception as exc:
        log.error(f"create_session storage error: {exc}")
        return _err("Failed to persist session", 500)

    log_activity(
        event_type='session_created',
        message=f"MMMX session created: {session['session_id'][:8]}",
        session_id=session['session_id'],
        data={'session_id': session['session_id']},
    )

    try:
        emit_session_created(
            session['session_id'],
            {'status': session['status'], 'created_at': session['created_at']},
        )
    except Exception:
        pass

    return _ok(data=session)


# ── GET /api/mmmx/sessions ─────────────────────────────────────────────────────

@mmmx_bp.route('/api/mmmx/sessions', methods=['GET'])
def list_sessions():
    """List all MMMX sessions (lightweight — no full data blob)."""
    from .mmmx_storage import get_storage

    status_filter = request.args.get('status')
    storage = get_storage()

    try:
        sessions = storage.list_sessions(status_filter=status_filter)
    except Exception as exc:
        log.error(f"list_sessions error: {exc}")
        return _err("Failed to list sessions", 500)

    return _ok(data=sessions, count=len(sessions))


# ── GET /api/mmmx/session/<id> ────────────────────────────────────────────────

@mmmx_bp.route('/api/mmmx/session/<session_id>', methods=['GET'])
def get_session(session_id: str):
    """Return full session dict for a given session_id."""
    from .mmmx_storage import get_storage
    from .mmmx_monitor import get_monitor
    from .mmmx_integrity import build_integrity_signature

    storage = get_storage()
    session = storage.load_session(session_id)
    if session is None:
        return _err(f"Session not found: {session_id}", 404)

    monitor = get_monitor(session_id)
    session['_monitor_alive'] = monitor.is_alive() if monitor else False
    session['_monitor_generation'] = monitor._my_generation if monitor else None
    session['_integrity'] = build_integrity_signature(session, source='snapshot')

    return _ok(data=session)


# ── PATCH /api/mmmx/session/<id>/params ───────────────────────────────────────

@mmmx_bp.route('/api/mmmx/session/<session_id>/params', methods=['PATCH'])
def hot_reload_params(session_id: str):
    """
    Hot-reload session params while RUNNING or PAUSED.

    Body: {params: {key: value, ...}}
    Supports partial success: allowlisted keys are applied; others returned in
    'rejected' dict with reason. HTTP 422 only when ALL keys are rejected.

    Response: {ok, applied, rejected, audit_id}
    """
    from .mmmx_config import split_hot_reload_patch
    from .mmmx_engine import recalc_hard_stop
    from .mmmx_storage import get_storage, GenerationConflict
    from .mmmx_param_audit import record_param_change
    from .mmmx_websocket import emit_params_changed
    from .mmmx_activity import log_activity

    body = request.get_json(silent=True) or {}
    patch = body.get('params', {})

    if not patch:
        return _err("No params provided in body.params")

    applied, rejected = split_hot_reload_patch(patch)

    # All keys rejected → fatal
    if not applied:
        return jsonify({'ok': False, 'applied': {}, 'rejected': rejected}), 422

    storage = get_storage()
    session = storage.load_session(session_id)
    if session is None:
        return _err(f"Session not found: {session_id}", 404)

    old_params = dict(session.get('params', {}))
    session['params'] = {**old_params, **applied}

    # Recalculate hard stop if multiplier changed
    if 'hard_stop_multiplier' in applied:
        session['hard_stop_usd'] = recalc_hard_stop(session)

    current_gen = storage.get_generation(session_id)
    try:
        storage.save_session(session, expected_gen=current_gen)
    except GenerationConflict as exc:
        return _err(f"Session save conflict (monitor running?) — retry: {exc}", 409)
    except Exception as exc:
        log.error(f"hot_reload_params save error: {exc}")
        return _err("Failed to save params", 500)

    diff = record_param_change(
        session_id=session_id,
        old_params=old_params,
        new_params=session['params'],
        changed_by='operator',
        storage=storage,
    )

    try:
        emit_params_changed(session_id, diff)
    except Exception:
        pass

    log_activity(
        event_type='params_changed',
        message=f"Params hot-reloaded: {list(applied.keys())}",
        session_id=session_id,
        data=diff,
    )

    return jsonify({'ok': True, 'applied': applied, 'rejected': rejected, 'audit_id': ''}), 200


# ── POST /api/mmmx/session/<id>/stop ─────────────────────────────────────────

@mmmx_bp.route('/api/mmmx/session/<session_id>/stop', methods=['POST'])
def stop_session(session_id: str):
    """
    Stop the MMMX monitor for a session and transition to COMPLETE.

    Does NOT place any orders — just stops the thread and updates status.
    For a graceful close_all, use the close endpoint (Phase 4).
    """
    body = request.get_json(silent=True) or {}
    reason = body.get('reason', 'operator stop')

    result = _stop_session_internal(
        session_id=session_id,
        reason=reason,
        source='operator_stop',
    )
    if not result.get('ok'):
        return _err(result.get('error', 'Failed to stop session'), result.get('status', 500))

    session = result['session']
    return _ok(data={
        'session_id':        session_id,
        'status':            session.get('status'),
        'monitor_alive':     result.get('monitor_alive', False),
    })


# ── POST /api/mmmx/kill-switch ──────────────────────────────────────────────

@mmmx_bp.route('/api/mmmx/kill-switch', methods=['POST'])
def kill_switch():
    """
    Operator emergency kill switch.

    Body:
      {
        "scope": "session" | "global",
        "session_id": "...",   # required when scope=session
        "reason": "..."         # optional
      }

    Behavior:
      - scope=session: terminal-stop the specified session
      - scope=global: terminal-stop all active sessions (RUNNING/PAUSED/GATES_PASSED)
    """
    from .mmmx_storage import get_storage
    from .mmmx_websocket import emit_kill_switch_progress

    body = request.get_json(silent=True) or {}
    scope = str(body.get('scope', 'session')).strip().lower()
    reason = str(body.get('reason', 'operator kill switch')).strip() or 'operator kill switch'

    if scope not in ('session', 'global'):
        return _err("scope must be one of: session, global", 422)

    storage = get_storage()
    target_session_ids = []
    correlation_id = f"kill-{uuid4().hex[:12]}"

    if scope == 'session':
        sid = body.get('session_id')
        if not sid:
            return _err("session_id is required for scope=session", 422)
        target_session_ids = [sid]
    else:
        try:
            sessions = storage.list_sessions()
        except Exception as exc:
            log.error(f"kill_switch list_sessions error: {exc}")
            return _err("Failed to list sessions for global kill switch", 500)

        target_session_ids = [
            s.get('session_id')
            for s in sessions
            if s.get('session_id')
            and s.get('status') in ('RUNNING', 'PAUSED', 'GATES_PASSED')
        ]

    stopped = []
    failed = []

    try:
        emit_kill_switch_progress(
            correlation_id=correlation_id,
            scope=scope,
            stage='accepted',
            status='accepted',
            details={
                'reason': reason,
                'requested_count': len(target_session_ids),
            },
        )
    except Exception:
        pass

    for idx, sid in enumerate(target_session_ids, start=1):
        result = _stop_session_internal(
            session_id=sid,
            reason=reason,
            source=f'kill_switch_{scope}',
        )

        if result.get('ok'):
            stopped.append({
                'session_id': sid,
                'status': result.get('session', {}).get('status'),
                'monitor_alive': result.get('monitor_alive', False),
            })
            try:
                emit_kill_switch_progress(
                    correlation_id=correlation_id,
                    scope=scope,
                    stage='session_result',
                    status='stopped',
                    session_id=sid,
                    details={
                        'new_status': result.get('session', {}).get('status'),
                        'monitor_alive': result.get('monitor_alive', False),
                        'processed_count': idx,
                        'requested_count': len(target_session_ids),
                    },
                )
            except Exception:
                pass
        else:
            failed.append({
                'session_id': sid,
                'error': result.get('error', 'Unknown error'),
                'status': result.get('status', 500),
            })
            try:
                emit_kill_switch_progress(
                    correlation_id=correlation_id,
                    scope=scope,
                    stage='session_result',
                    status='failed',
                    session_id=sid,
                    details={
                        'error': result.get('error', 'Unknown error'),
                        'status': result.get('status', 500),
                        'processed_count': idx,
                        'requested_count': len(target_session_ids),
                    },
                )
            except Exception:
                pass

    try:
        emit_kill_switch_progress(
            correlation_id=correlation_id,
            scope=scope,
            stage='completed',
            status='completed' if not failed else 'completed_with_failures',
            details={
                'requested_count': len(target_session_ids),
                'stopped_count': len(stopped),
                'failed_count': len(failed),
                'reason': reason,
            },
        )
    except Exception:
        pass

    return _ok(data={
        'correlation_id': correlation_id,
        'scope': scope,
        'reason': reason,
        'requested_count': len(target_session_ids),
        'stopped_count': len(stopped),
        'failed_count': len(failed),
        'stopped': stopped,
        'failed': failed,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    })


# ── POST /api/mmmx/session/<id>/start-monitor ────────────────────────────────

@mmmx_bp.route('/api/mmmx/session/<session_id>/start-monitor', methods=['POST'])
def start_monitor(session_id: str):
    """
    Start (or restart) the heartbeat monitor for a session.

    Used after manual reconcile + resume (Phase 9 reconciliation).
    Session must exist in DB. Status transitions to RUNNING are handled
    by the initializer (Phase 7); this endpoint just starts the thread.
    """
    from .mmmx_storage import get_storage
    from .mmmx_monitor import start_session_monitor

    storage = get_storage()
    session = storage.load_session(session_id)
    if session is None:
        return _err(f"Session not found: {session_id}", 404)

    try:
        monitor = start_session_monitor(session_id)
    except Exception as exc:
        log.error(f"start_monitor error: {exc}")
        return _err(f"Failed to start monitor: {exc}", 500)

    return _ok(data={
        'session_id':  session_id,
        'generation':  monitor._my_generation,
        'alive':       monitor.is_alive(),
    })


# ── GET /api/mmmx/session/<id>/audit ─────────────────────────────────────────

@mmmx_bp.route('/api/mmmx/session/<session_id>/audit', methods=['GET'])
def get_audit(session_id: str):
    """Return audit log entries for a session."""
    from .mmmx_storage import get_storage

    limit = min(int(request.args.get('limit', 100)), 500)
    storage = get_storage()
    events = storage.get_audit_events(session_id, limit=limit)
    return _ok(data=events, count=len(events))


# ── GET /api/mmmx/session/<id>/activity ──────────────────────────────────────

@mmmx_bp.route('/api/mmmx/session/<session_id>/activity', methods=['GET'])
def get_activity(session_id: str):
    """Return recent activity log entries for a session."""
    from .mmmx_activity import get_activity_log

    limit = min(int(request.args.get('limit', 100)), 500)
    entries = get_activity_log().get_recent(session_id=session_id, limit=limit)
    return _ok(data=entries, count=len(entries))


# ── GET /api/mmmx/session/<id>/param-history ─────────────────────────────────

@mmmx_bp.route('/api/mmmx/session/<session_id>/param-history', methods=['GET'])
def get_param_history(session_id: str):
    """Return param hot-reload history for a session."""
    from .mmmx_param_audit import get_param_history as _gph

    limit = min(int(request.args.get('limit', 50)), 200)
    history = _gph(session_id, limit=limit)
    return _ok(data=history, count=len(history))


# ── GET /api/mmmx/health ─────────────────────────────────────────────────────

@mmmx_bp.route('/api/mmmx/health', methods=['GET'])
def health():
    """Return MMMX system health (monitor count, WS health, watchdog status)."""
    from .mmmx_monitor import get_all_monitors
    from .mmmx_websocket import get_ws_health
    from .mmmx_watchdog import get_watchdog

    monitors = get_all_monitors()
    watchdog = get_watchdog()
    return _ok(data={
        'active_monitors':  sum(1 for m in monitors.values() if m.is_alive()),
        'total_monitors':   len(monitors),
        'ws':               get_ws_health(),
        'watchdog_alive':   watchdog.is_alive(),
        'last_watchdog_tick': watchdog.last_tick_at,
        'timestamp':        datetime.now(timezone.utc).isoformat(),
    })


# ── POST /api/mmmx/session/<id>/pause ────────────────────────────────────────

@mmmx_bp.route('/api/mmmx/session/<session_id>/pause', methods=['POST'])
def pause_session(session_id: str):
    """
    Pause the MMMX monitor for a session.

    CRITICAL: Stops the monitor ONLY. The Premium Listener MUST remain alive
    (positions are still open; CB_NEAR_ITM protection must keep running).
    Never calls stop_session_monitor() — that would kill the listener too.
    """
    from .mmmx_storage import get_storage
    from .mmmx_state import transition_status
    from .mmmx_monitor import get_monitor
    from .mmmx_websocket import emit_status_change
    from .mmmx_activity import log_activity

    storage = get_storage()
    session = storage.load_session(session_id)
    if session is None:
        return _err(f"Session not found: {session_id}", 404)

    old_status = session.get('status')
    try:
        transition_status(session, 'PAUSED', reason='operator_pause')
    except ValueError as exc:
        return _err(str(exc), 409)

    # Stop ONLY the monitor — do NOT call stop_session_monitor() (kills listener)
    monitor = get_monitor(session_id)
    if monitor:
        monitor.stop(reason='operator_pause')

    current_gen = storage.get_generation(session_id)
    try:
        storage.save_session(session, expected_gen=current_gen)
    except Exception as exc:
        log.error(f"pause_session save error: {exc}")

    try:
        emit_status_change(session_id, old_status, 'PAUSED', 'operator_pause')
    except Exception:
        pass

    try:
        from .mmmx_telegram import send_alert
        send_alert(
            "\u23f8 Session paused by operator. Listener still active.",
            alert_type=f'pause_{session_id[:8]}',
            session_id=session_id,
            dedup_ttl=30,
        )
    except Exception:
        pass

    log_activity(
        event_type='session_paused',
        message='Session paused by operator',
        session_id=session_id,
    )

    return _ok(data={'status': 'PAUSED'})


# ── POST /api/mmmx/session/<id>/resume ───────────────────────────────────────

@mmmx_bp.route('/api/mmmx/session/<session_id>/resume', methods=['POST'])
def resume_session(session_id: str):
    """
    Resume a paused MMMX session.

    Transitions PAUSED → RUNNING, then calls start_session_monitor() which
    bumps generation and co-starts a fresh Premium Listener.
    """
    from .mmmx_storage import get_storage
    from .mmmx_state import transition_status
    from .mmmx_monitor import start_session_monitor
    from .mmmx_websocket import emit_status_change
    from .mmmx_activity import log_activity

    storage = get_storage()
    session = storage.load_session(session_id)
    if session is None:
        return _err(f"Session not found: {session_id}", 404)

    old_status = session.get('status')
    try:
        transition_status(session, 'RUNNING', reason='operator_resume')
    except ValueError as exc:
        return _err(str(exc), 409)

    current_gen = storage.get_generation(session_id)
    try:
        storage.save_session(session, expected_gen=current_gen)
    except Exception as exc:
        log.error(f"resume_session save error: {exc}")

    try:
        monitor = start_session_monitor(session_id)
    except Exception as exc:
        log.error(f"resume_session start_monitor error: {exc}")
        return _err(f"Failed to start monitor: {exc}", 500)

    try:
        emit_status_change(session_id, old_status, 'RUNNING', 'operator_resume')
    except Exception:
        pass

    log_activity(
        event_type='session_resumed',
        message='Session resumed by operator',
        session_id=session_id,
    )

    return _ok(data={'status': 'RUNNING', 'generation': monitor._my_generation})


# ── POST /api/mmmx/session/<id>/force-heartbeat ─────────────────────────────

@mmmx_bp.route('/api/mmmx/session/<session_id>/force-heartbeat', methods=['POST'])
def force_heartbeat(session_id: str):
    """
    Force a heartbeat run immediately by waking the session monitor.

    Body (optional): {reason}

    Allowed statuses: RUNNING, PAUSED.
    Uses the existing listener/monitor wake path from Phase 7.
    """
    from .mmmx_storage import get_storage, GenerationConflict
    from .mmmx_monitor import get_monitor
    from .mmmx_premium_listener import get_listener
    from .mmmx_activity import log_activity

    body = request.get_json(silent=True) or {}
    reason = str(body.get('reason', 'operator_manual')).strip() or 'operator_manual'

    storage = get_storage()
    session = storage.load_session(session_id)
    if session is None:
        return _err(f"Session not found: {session_id}", 404)

    if session.get('status') not in ('RUNNING', 'PAUSED'):
        return _err(
            f"Force heartbeat requires RUNNING or PAUSED session, got {session.get('status')}",
            409,
        )

    monitor = get_monitor(session_id)
    if monitor is None or not monitor.is_alive():
        return _err("Monitor is not active for this session", 409)

    listener = get_listener(session_id)

    # Always wake monitor in-memory first (synchronous and race-safe).
    try:
                monitor.signal_force_check()
    except Exception as exc:
                log.error(f"force_heartbeat monitor wake failed: {exc}")

    # Keep session markers consistent with listener path.
    if listener is not None:
        try:
            listener.force_heartbeat(session, reason)
        except Exception as exc:
            log.error(f"force_heartbeat listener path failed: {exc}")
            session['_force_check'] = True
            session['_listener_force_count'] = session.get('_listener_force_count', 0) + 1
    else:
        session['_force_check'] = True
        session['_listener_force_count'] = session.get('_listener_force_count', 0) + 1

    save_ok = True
    current_gen = storage.get_generation(session_id)
    try:
        storage.save_session(session, expected_gen=current_gen)
    except GenerationConflict:
        # Heartbeat wake has already been signaled; conflict only means a concurrent save won.
        save_ok = False
        log.warning(
            f"force_heartbeat save conflict for {session_id[:8]} — "
            "wake signal sent, session markers may lag one beat"
        )
    except Exception as exc:
        save_ok = False
        log.error(f"force_heartbeat save error: {exc}")

    log_activity(
        event_type='force_heartbeat',
        message=f"Force heartbeat requested: {reason}",
        session_id=session_id,
        data={
            'reason': reason,
            'listener_attached': listener is not None,
            'save_ok': save_ok,
        },
    )

    return _ok(data={
        'queued': True,
        'reason': reason,
        'listener_attached': listener is not None,
        'monitor_alive': True,
        'save_ok': save_ok,
        'listener_force_count': session.get('_listener_force_count', 0),
    })


# ── GET /api/mmmx/session/<id>/scan_strikes ──────────────────────────────────

@mmmx_bp.route('/api/mmmx/session/<session_id>/scan_strikes', methods=['GET'])
def scan_strikes_endpoint(session_id: str):
    """
    Scan for CE/PE strike candidates.

    Session must be DRAFT, GATES_PASSED or RUNNING. Fetches live chain from
    OptionsChainService; returns {reason: 'no_live_chain'} if unavailable,
    {reason: 'no_expiry_set'} if session has no expiry configured yet.

    Query params: otm_pct (default 15)
    """
    from .mmmx_storage import get_storage
    from .mmmx_initializer import scan_strikes
    from .mmmx_constants import SessionStatus
    from datetime import datetime as _dt

    storage = get_storage()
    session = storage.load_session(session_id)
    if session is None:
        return _err(f"Session not found: {session_id}", 404)

    status = session.get('status')
    if status not in (SessionStatus.DRAFT, SessionStatus.GATES_PASSED, SessionStatus.RUNNING):
        return _err(
            f"Session must be DRAFT, GATES_PASSED or RUNNING to scan strikes, got {status}", 409
        )

    try:
        otm_pct = float(request.args.get('otm_pct', 15))
    except (TypeError, ValueError):
        return _err("Invalid otm_pct parameter", 400)

    # Resolve expiry: session stores DDMMYY (6-char); chain service needs DDMMYYYY (8-char)
    # Fallback to params.target_expiry_ddmmyy for sessions created before the state-init fix
    expiry_ddmmyy = (
        session.get('expiry_ddmmyy')
        or session.get('params', {}).get('target_expiry_ddmmyy')
        or ''
    )
    if not expiry_ddmmyy:
        return _ok(data={'ce': None, 'pe': None, 'reason': 'no_expiry_set'})

    try:
        if len(expiry_ddmmyy) == 6 and expiry_ddmmyy.isdigit():
            expiry_ddmmyyyy = _dt.strptime(expiry_ddmmyy, '%d%m%y').strftime('%d%m%Y')
        elif len(expiry_ddmmyy) == 8 and expiry_ddmmyy.isdigit():
            expiry_ddmmyyyy = expiry_ddmmyy
        else:
            return _ok(data={'ce': None, 'pe': None, 'reason': 'no_live_chain'})
    except ValueError:
        return _ok(data={'ce': None, 'pe': None, 'reason': 'no_live_chain'})

    # Fetch live chain from OptionsChainService
    try:
        try:
            from webui.backend.options_chain.chain_service import OptionsChainService
        except ImportError:
            from options_chain.chain_service import OptionsChainService

        svc = OptionsChainService()
        spot = svc._get_spot_price('BTC')
        if spot <= 0:
            return _ok(data={'ce': None, 'pe': None, 'reason': 'no_live_chain'})

        chain_data = svc.get_chain_data('BTC', expiry_ddmmyyyy)
        if not chain_data or not chain_data.get('chain'):
            return _ok(data={'ce': None, 'pe': None, 'reason': 'no_live_chain'})

        # Flatten {strike, call: {...}, put: {...}} → [{symbol, strike, bid, ask, delta}]
        # Also keep a symbol→full_data lookup for mark_price/iv enrichment in response.
        chain_flat = []
        sym_lookup: dict = {}
        for entry in chain_data.get('chain', []):
            strike = entry.get('strike')
            for opt in (entry.get('call'), entry.get('put')):
                if opt:
                    sym = opt.get('symbol', '')
                    flat = {
                        'strike': strike,
                        'symbol': sym,
                        'bid':    opt.get('bid', 0.0),
                        'ask':    opt.get('ask', 0.0),
                        'delta':  opt.get('delta', 0.0),
                    }
                    chain_flat.append(flat)
                    sym_lookup[sym] = opt  # preserve mark_price, iv for response

    except Exception as exc:
        log.warning(f"[scan_strikes][{session_id[:8]}] chain fetch failed: {exc}")
        return _ok(data={'ce': None, 'pe': None, 'reason': 'no_live_chain'})

    candidates = scan_strikes(
        asset='BTC',
        expiry=expiry_ddmmyy,
        otm_pct=otm_pct,
        chain=chain_flat,
        spot=spot,
    )

    if candidates is None:
        return _ok(data={'ce': None, 'pe': None, 'reason': 'no_live_chain'})

    ce_full = sym_lookup.get(candidates.ce_symbol, {})
    pe_full = sym_lookup.get(candidates.pe_symbol, {})

    return _ok(data={
        'ce': {
            'strike':     candidates.ce_strike,
            'symbol':     candidates.ce_symbol,
            'delta':      candidates.ce_delta,
            'bid':        candidates.ce_bid,
            'ask':        candidates.ce_ask,
            'mark_price': ce_full.get('mark_price'),
            'iv':         ce_full.get('iv'),
        },
        'pe': {
            'strike':     candidates.pe_strike,
            'symbol':     candidates.pe_symbol,
            'delta':      candidates.pe_delta,
            'bid':        candidates.pe_bid,
            'ask':        candidates.pe_ask,
            'mark_price': pe_full.get('mark_price'),
            'iv':         pe_full.get('iv'),
        },
        'spot': spot,
    })


# ── POST /api/mmmx/session/<id>/deploy_tranche1 ──────────────────────────────

@mmmx_bp.route('/api/mmmx/session/<session_id>/deploy_tranche1', methods=['POST'])
def deploy_tranche1(session_id: str):
    """
    Operator-confirmed manual Tranche 1 deploy.

    Body (JSON): {ce_symbol, ce_strike, pe_symbol, pe_strike, lots}
    Optional: {ce_premium, ce_delta, pe_premium, pe_delta, spot, iv_rank}

    Session must be RUNNING or GATES_PASSED.
    Calls deploy_manual_tranche1 (all-or-nothing).
    """
    from .mmmx_storage import get_storage
    from .mmmx_constants import SessionStatus
    from .mmmx_executor import get_executor
    from .mmmx_audit_log import get_audit_log
    import asyncio as _asyncio

    body = request.get_json(silent=True) or {}

    required = ('ce_symbol', 'ce_strike', 'pe_symbol', 'pe_strike', 'lots')
    missing = [f for f in required if f not in body]
    if missing:
        return _err(f"Missing required fields: {missing}", 422)

    storage = get_storage()
    session = storage.load_session(session_id)
    if session is None:
        return _err(f"Session not found: {session_id}", 404)

    status = session.get('status')
    if status not in (SessionStatus.DRAFT, SessionStatus.GATES_PASSED, SessionStatus.RUNNING):
        return _err(f"Session must be DRAFT, GATES_PASSED, or RUNNING to deploy, got {status}", 409)

    # DRAFT → GATES_PASSED: parse expiry from CE symbol and auto-transition.
    # CE symbol format: C-BTC-{STRIKE}-{DDMMYY}  e.g. C-BTC-70000-260426
    if status == SessionStatus.DRAFT:
        try:
            ce_sym = str(body['ce_symbol'])
            parts = ce_sym.split('-')
            # parts: ['C', 'BTC', '70000', '260426']
            ddmmyy = parts[-1]  # last segment
            if len(ddmmyy) != 6 or not ddmmyy.isdigit():
                return _err(
                    f"Cannot parse expiry from CE symbol '{ce_sym}'. "
                    "Expected format C-BTC-STRIKE-DDMMYY (e.g. C-BTC-70000-260426).",
                    422,
                )
            dd, mm, yy = ddmmyy[:2], ddmmyy[2:4], ddmmyy[4:]
            yyyy = f"20{yy}"
            from datetime import timezone as _tz, datetime as _dt
            expiry_date = f"{dd}-{mm}-{yyyy}"
            # Delta Exchange BTC monthly options expire at 10:00 AM IST = 04:30 UTC
            expiry_datetime = _dt(int(yyyy), int(mm), int(dd), 4, 30, 0,
                                  tzinfo=_tz.utc).isoformat()
            session['expiry_date'] = expiry_date
            session['expiry_ddmmyy'] = ddmmyy
            session['expiry_datetime'] = expiry_datetime
        except (IndexError, ValueError) as exc:
            return _err(f"Expiry parse error from CE symbol: {exc}", 422)

        # Transition DRAFT → GATES_PASSED
        try:
            from .mmmx_state import transition_status
            transition_status(session, SessionStatus.GATES_PASSED,
                              reason='auto_gates_passed_on_deploy')
        except ValueError as exc:
            return _err(f"Cannot transition to GATES_PASSED: {exc}", 409)

    executor = get_executor()
    audit    = get_audit_log()

    try:
        from .mmmx_initializer import deploy_manual_tranche1
        result = _asyncio.run(deploy_manual_tranche1(
            session=session,
            executor=executor,
            audit=audit,
            ce_symbol=str(body['ce_symbol']),
            pe_symbol=str(body['pe_symbol']),
            ce_lots=int(body['lots']),
            pe_lots=int(body['lots']),
            spot=float(body.get('spot') or 0.0),
            iv_rank=float(body.get('iv_rank') or 0.0),
            ce_strike=float(body['ce_strike']),
            ce_premium=float(body.get('ce_premium') or 0.0),
            ce_delta=float(body.get('ce_delta') or 0.0),
            pe_strike=float(body['pe_strike']),
            pe_premium=float(body.get('pe_premium') or 0.0),
            pe_delta=float(body.get('pe_delta') or 0.0),
        ))
    except Exception as exc:
        log.error(f"deploy_tranche1 error: {exc}")
        return _err(str(exc), 422)

    if isinstance(result, dict) and not result.get('success', True):
        return jsonify({'ok': False, 'reason': result.get('reason', 'deploy failed')}), 422

    # Save updated session
    current_gen = storage.get_generation(session_id)
    try:
        storage.save_session(session, expected_gen=current_gen)
    except Exception as exc:
        log.error(f"deploy_tranche1 save error: {exc}")

    return _ok(data={'tranche': result})


# ── POST /api/mmmx/session/<id>/check-gates ──────────────────────────────────

@mmmx_bp.route('/api/mmmx/session/<session_id>/check-gates', methods=['POST'])
def check_gates(session_id: str):
    """
    Manually transition a DRAFT session to GATES_PASSED after operator review.

    Body (JSON): {expiry_ddmmyy}  e.g. "260426" for 26 Apr 2026.

    Sets expiry fields on the session and transitions DRAFT → GATES_PASSED.
    Use this when you want to select strikes before deploying.
    """
    from .mmmx_storage import get_storage
    from .mmmx_constants import SessionStatus
    from .mmmx_state import transition_status
    from datetime import timezone as _tz, datetime as _dt

    body = request.get_json(silent=True) or {}
    ddmmyy = str(body.get('expiry_ddmmyy', '')).strip()

    if not ddmmyy or len(ddmmyy) != 6 or not ddmmyy.isdigit():
        return _err("expiry_ddmmyy must be a 6-digit string e.g. '260426' for 26 Apr 2026", 422)

    storage = get_storage()
    session = storage.load_session(session_id)
    if session is None:
        return _err(f"Session not found: {session_id}", 404)

    if session.get('status') != SessionStatus.DRAFT:
        return _err(f"Session must be DRAFT to check gates, got {session.get('status')}", 409)

    dd, mm, yy = ddmmyy[:2], ddmmyy[2:4], ddmmyy[4:]
    yyyy = f"20{yy}"
    try:
        expiry_datetime = _dt(int(yyyy), int(mm), int(dd), 4, 30, 0,
                              tzinfo=_tz.utc).isoformat()
    except ValueError as exc:
        return _err(f"Invalid expiry date: {exc}", 422)

    session['expiry_date'] = f"{dd}-{mm}-{yyyy}"
    session['expiry_ddmmyy'] = ddmmyy
    session['expiry_datetime'] = expiry_datetime

    try:
        transition_status(session, SessionStatus.GATES_PASSED, reason='operator_gates_check')
    except ValueError as exc:
        return _err(str(exc), 409)

    current_gen = storage.get_generation(session_id)
    try:
        storage.save_session(session, expected_gen=current_gen)
    except Exception as exc:
        log.error(f"check_gates save error: {exc}")

    return _ok(data={
        'status':           session['status'],
        'expiry_date':      session['expiry_date'],
        'expiry_ddmmyy':    session['expiry_ddmmyy'],
        'expiry_datetime':  session['expiry_datetime'],
    })


# ── POST /api/mmmx/session/<id>/profit_book ──────────────────────────────────

@mmmx_bp.route('/api/mmmx/session/<session_id>/profit_book', methods=['POST'])
def profit_book(session_id: str):
    """
    Queue a tranche for profit booking.

    Body: {tranche_id, target_pct}
    Session must be RUNNING.
    """
    from .mmmx_storage import get_storage
    from .mmmx_constants import SessionStatus
    from .mmmx_profit_booking import queue_close
    from .mmmx_activity import log_activity

    body = request.get_json(silent=True) or {}
    tranche_id = body.get('tranche_id')
    target_pct = body.get('target_pct')

    if tranche_id is None or target_pct is None:
        return _err("Body must contain tranche_id and target_pct", 422)

    try:
        target_pct = float(target_pct)
    except (TypeError, ValueError):
        return _err("target_pct must be a number", 422)

    storage = get_storage()
    session = storage.load_session(session_id)
    if session is None:
        return _err(f"Session not found: {session_id}", 404)

    if session.get('status') != SessionStatus.RUNNING:
        return _err(f"Session must be RUNNING, got {session.get('status')}", 409)

    try:
        queue_close(session, tranche_id, target_pct)
    except ValueError as exc:
        return _err(str(exc), 422)

    current_gen = storage.get_generation(session_id)
    try:
        storage.save_session(session, expected_gen=current_gen)
    except Exception as exc:
        log.error(f"profit_book save error: {exc}")

    log_activity(
        event_type='profit_book_queued',
        message=f"Tranche {tranche_id} queued for profit booking at {target_pct}%",
        session_id=session_id,
        data={'tranche_id': tranche_id, 'target_pct': target_pct},
    )

    return _ok(data={'queue': session.get('_profit_booking_queue', [])})


# ── POST /api/mmmx/session/<id>/confirm-reconcile ────────────────────────────

@mmmx_bp.route('/api/mmmx/session/<session_id>/confirm-reconcile', methods=['POST'])
def confirm_reconcile(session_id: str):
    """
    Apply an operator reconciliation decision.

    Body: {divergence_id, action, notes}
      action: 'accept_db' | 'accept_exchange' | 'manual_close'

    Returns {ok, session_id} on success.
    """
    from .mmmx_storage import get_storage
    from .mmmx_reconciler import apply_recon_confirmation
    from .mmmx_activity import log_activity

    storage = get_storage()
    session = storage.load_session(session_id)
    if session is None:
        return _err(f"Session not found: {session_id}", 404)

    body = request.get_json(silent=True) or {}
    action = body.get('action', '')
    if action not in ('accept_db', 'accept_exchange', 'manual_close'):
        return _err(
            f"Invalid action {action!r}. Must be one of: "
            "'accept_db', 'accept_exchange', 'manual_close'",
            422,
        )

    try:
        apply_recon_confirmation(session, body)
    except ValueError as exc:
        return _err(str(exc), 422)

    current_gen = storage.get_generation(session_id)
    try:
        storage.save_session(session, expected_gen=current_gen)
    except Exception as exc:
        log.error(f"confirm_reconcile save error: {exc}")

    log_activity(
        event_type='recon_confirmed',
        message=(
            f"Reconciliation decision: {action} for "
            f"divergence {body.get('divergence_id', '')!r}"
        ),
        session_id=session_id,
        data=body,
    )

    return _ok(session_id=session_id)


# ── POST /api/mmmx/session/<id>/reconcile ────────────────────────────────────

@mmmx_bp.route('/api/mmmx/session/<session_id>/reconcile', methods=['POST'])
def reconcile(session_id: str):
    """
    Trigger manual reconciliation of session state against exchange positions.

    Returns a ReconciliationReport. No session state is mutated.
    """
    from .mmmx_storage import get_storage
    from .mmmx_reconciler import reconcile_with_exchange
    import asyncio as _asyncio

    storage = get_storage()
    session = storage.load_session(session_id)
    if session is None:
        return _err(f"Session not found: {session_id}", 404)

    try:
        report = _asyncio.run(reconcile_with_exchange(session))
        return _ok(data=asdict(report))
    except Exception as exc:
        log.error(f"reconcile error: {exc}")
        return _err(f"Reconciliation failed: {exc}", 500)
