"""
MMM API — Money Mind & Method

REST endpoints for MMM session management:
- Session CRUD (create, read, list, delete)
- Session control (start, pause, resume, stop)
- Parameter management (get, update with hot-reload)
- Both-sides-up user decision endpoint

Maps to MMM_DEVELOPMENT_PLAN.md Phase 1, Tasks 1.4-1.7.
Logic follows MONEY_POWER_CALCULATION_LOGIC.md throughout.

Created: February 15, 2026
"""

import logging
import threading
from flask import Blueprint, request, jsonify
from datetime import datetime

from .mmm_storage import get_storage
from .mmm_state import (
    create_session,
    initialize_side_from_entry,
    get_session_summary,
    DEFAULT_PARAMS,
    HOT_RELOAD_PARAMS,
)
from .mmm_config import validate_params, get_hot_reload_params, get_param_info
from .mmm_websocket import (
    emit_status_change,
    emit_params_changed,
    emit_session_created,
    emit_session_deleted,
)
from .mmm_initializer import get_initializer, normalize_expiry
from .mmm_constants import LOT_SIZE_BTC
from .mmm_monitor import (
    start_session_monitor, stop_session_monitor,
    pause_session_monitor, resume_session_monitor,
    get_monitor, get_all_monitors,
)

log = logging.getLogger('mmm_api')

# =============================================================================
# Blueprint
# =============================================================================

mmm_bp = Blueprint('mmm', __name__, url_prefix='/api/mmm')


def _check_guardian_signal() -> str:
    """Check if trading is allowed via global guardian."""
    try:
        from webui.backend.trading_control import get_signal
        return get_signal()
    except Exception:
        return 'GO'


# =============================================================================
# Session CRUD
# =============================================================================

@mmm_bp.route('/sessions', methods=['GET'])
def list_sessions():
    """
    List all MMM sessions.

    Query params:
        active_only: bool - If true, only return active sessions
        summary: bool - If true, return compact summaries

    Returns:
        {success: true, sessions: [...], count: int}
    """
    try:
        active_only = request.args.get('active_only', 'false').lower() == 'true'
        summary_mode = request.args.get('summary', 'false').lower() == 'true'

        storage = get_storage()
        sessions = storage.list_sessions(active_only=active_only)

        if summary_mode:
            sessions = [get_session_summary(s) for s in sessions]

        return jsonify({
            'success': True,
            'sessions': sessions,
            'count': len(sessions),
        })

    except Exception as e:
        log.exception("Failed to list MMM sessions")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>', methods=['GET'])
def get_session(session_id: str):
    """
    Get a specific session by ID.

    Query params:
        summary: bool - If true, return compact summary

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

        summary_mode = request.args.get('summary', 'false').lower() == 'true'
        data = get_session_summary(session) if summary_mode else session

        return jsonify({'success': True, 'session': data})

    except Exception as e:
        log.exception(f"Failed to get MMM session {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/create', methods=['POST'])
def create_session_endpoint():
    """
    Create a new MMM session.

    Request body:
        {
            mode: str ('fresh' | 'import'),
            params: {
                desired_ce_premium: float,
                desired_pe_premium: float,
                initial_lots: int,
                expiry: str,
                adjustment_interval: int,
                ... (any key from DEFAULT_PARAMS)
            },
            import_data: {          // only for mode='import'
                ce: { strike, premium, lots },
                pe: { strike, premium, lots }
            }
        }

    Returns:
        {success: true, session: {...}}
    """
    try:
        data = request.get_json() or {}

        mode = data.get('mode', 'fresh')
        if mode not in ('fresh', 'import'):
            return jsonify({
                'success': False,
                'error': "mode must be 'fresh' or 'import'",
            }), 400

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
        session = create_session(mode=mode, params=validated)

        # For import mode, initialize sides immediately
        if mode == 'import':
            import_data = data.get('import_data', {})
            ce_data = import_data.get('ce')
            pe_data = import_data.get('pe')

            if not ce_data or not pe_data:
                return jsonify({
                    'success': False,
                    'error': "import mode requires import_data with 'ce' and 'pe' fields",
                }), 400

            for side_key, side_data in [('ce', ce_data), ('pe', pe_data)]:
                strike = side_data.get('strike')
                premium = side_data.get('premium')
                lots = side_data.get('lots')

                if not all([strike, premium, lots]):
                    return jsonify({
                        'success': False,
                        'error': f"import_data.{side_key} requires strike, premium, and lots",
                    }), 400

                initialize_side_from_entry(
                    session,
                    side=side_key,
                    strike=float(strike),
                    premium=float(premium),
                    lots=int(lots),
                )

            session['entry_time'] = datetime.utcnow().isoformat()

        # Persist
        storage = get_storage()
        storage.save_session(session)

        # Emit WebSocket
        emit_session_created(session['session_id'], get_session_summary(session))

        log.info(f"Created MMM session {session['session_id']} (mode={mode})")

        return jsonify({
            'success': True,
            'session': session,
        }), 201

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        log.exception("Failed to create MMM session")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>', methods=['DELETE'])
def delete_session(session_id: str):
    """
    Delete a session. Only allowed for IDLE or STOPPED sessions.
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}',
            }), 404

        status = session.get('strategy_status', 'IDLE')
        if status not in ('IDLE', 'STOPPED'):
            return jsonify({
                'success': False,
                'error': f"Cannot delete session in {status} state. Stop it first.",
            }), 400

        storage.delete_session(session_id)
        
        # Also delete all activities for this session
        from .mmm_activity import get_activity_log
        activity_log = get_activity_log()
        activity_log.clear(session_id)
        
        # Emit deletion event so UI can refetch activities
        emit_session_deleted(session_id)
        
        log.info(f"Deleted MMM session {session_id} and its activities")

        return jsonify({
            'success': True,
            'message': f'Session {session_id} deleted',
        })

    except Exception as e:
        log.exception(f"Failed to delete MMM session {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Session Control — Section 7: Triggers, Section 9: Reversal
# =============================================================================

@mmm_bp.route('/session/<session_id>/start', methods=['POST'])
def start_session(session_id: str):
    """
    Start an MMM session (NON-BLOCKING).

    For 'fresh' mode: launches a background thread to execute entry SELL orders
    on the exchange, then starts the heartbeat monitor when both legs fill.

    For 'import' mode: skips order placement, goes directly to monitoring.

    Returns immediately with status='STARTING' (fresh) or 'RUNNING' (import).
    """
    try:
        # Check guardian
        signal = _check_guardian_signal()
        if signal != 'GO':
            return jsonify({
                'success': False,
                'error': f'Guardian signal is {signal}. Trading disabled.',
            }), 403

        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}',
            }), 404

        status = session.get('strategy_status', 'IDLE')
        if status not in ('IDLE',):
            return jsonify({
                'success': False,
                'error': f"Cannot start session in {status} state. Must be IDLE.",
            }), 400

        # Check if session has been initialized (both sides have positions)
        ce_lots = session.get('ce', {}).get('original_lots', 0)
        pe_lots = session.get('pe', {}).get('original_lots', 0)

        if ce_lots == 0 or pe_lots == 0:
            return jsonify({
                'success': False,
                'error': 'Session must be initialized first. Use Config Panel to set up CE and PE strikes.',
            }), 400

        # =====================================================================
        # Execute Entry Orders on Exchange (if not already done)
        # =====================================================================
        entry_mode = session.get('entry_mode', 'fresh')
        already_executed = session.get('ce', {}).get('entry_fill_price') is not None

        if entry_mode == 'fresh' and not already_executed:
            ce_symbol = session.get('ce', {}).get('symbol', '')
            pe_symbol = session.get('pe', {}).get('symbol', '')
            lots = session.get('lots', 0) or ce_lots

            if not ce_symbol or not pe_symbol:
                return jsonify({
                    'success': False,
                    'error': 'CE/PE symbols not set. Re-initialize the session.',
                }), 400

            # Set status to STARTING immediately (non-blocking)
            storage.update_session(session_id, {
                'strategy_status': 'STARTING',
            })
            emit_status_change(session_id, 'IDLE', 'STARTING', 'Entry orders being placed...')

            from .mmm_activity import log_activity
            log_activity('session_starting',
                f"Starting session {session_id}: SELL {lots} CE ({ce_symbol}) + SELL {lots} PE ({pe_symbol})",
                session_id=session_id, severity='progress',
                details={'ce_symbol': ce_symbol, 'pe_symbol': pe_symbol, 'lots': lots})

            # Launch background thread for entry execution
            t = threading.Thread(
                target=_execute_entry_background,
                args=(session_id, ce_symbol, pe_symbol, lots),
                daemon=True,
                name=f'mmm-entry-{session_id}',
            )
            t.start()

            return jsonify({
                'success': True,
                'message': f'Session {session_id} entry orders launching in background',
                'status': 'STARTING',
                'entry_executed': False,
                'async': True,
            })

        # =====================================================================
        # Import mode or already-executed: go directly to RUNNING
        # =====================================================================
        old_status = status
        new_status = 'RUNNING'

        storage.update_session(session_id, {
            'strategy_status': new_status,
            'entry_time': session.get('entry_time') or datetime.utcnow().isoformat(),
            'last_heartbeat': datetime.utcnow().isoformat(),
        })

        emit_status_change(session_id, old_status, new_status, 'Started')
        log.info(f"MMM session {session_id} started — monitor launching")

        from .mmm_activity import log_activity
        log_activity('session_started',
            f"Session {session_id} is now RUNNING — heartbeat monitor active",
            session_id=session_id, severity='success')

        # Start the heartbeat monitor
        updated = storage.get_session(session_id)
        start_session_monitor(session_id, updated)

        return jsonify({
            'success': True,
            'message': f'Session {session_id} started',
            'status': new_status,
            'entry_executed': False,
        })

    except Exception as e:
        log.exception(f"Failed to start MMM session {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


def _execute_entry_background(session_id: str, ce_symbol: str, pe_symbol: str, lots: int):
    """
    Background thread: execute CE + PE entry orders, then start monitor.

    Handles partial fills: if one leg succeeds and the other fails,
    the successful leg is recorded so the user can manually close it.
    """
    import asyncio
    from .mmm_executor import get_executor
    from .mmm_activity import log_activity

    storage = get_storage()

    try:
        executor = get_executor()
        entry_result = asyncio.run(
            executor.execute_entry(ce_symbol, pe_symbol, lots, session_id)
        )
    except Exception as e:
        log.exception(f"MMM {session_id}: Entry execution crashed in background")
        log_activity('entry_failed',
            f"Entry execution crashed: {str(e)}",
            session_id=session_id, severity='error')
        storage.update_session(session_id, {'strategy_status': 'ERROR'})
        emit_status_change(session_id, 'STARTING', 'ERROR',
            f'Entry execution failed: {str(e)}')
        return

    if not entry_result.get('success'):
        error_msg = entry_result.get('error', 'Unknown execution error')
        ce_res = entry_result.get('ce', {})
        pe_res = entry_result.get('pe', {})

        # Check for partial fill (one leg filled, other failed)
        ce_ok = ce_res.get('success', False) if isinstance(ce_res, dict) else False
        pe_ok = pe_res.get('success', False) if isinstance(pe_res, dict) else False

        if ce_ok or pe_ok:
            # PARTIAL FILL — record what we have so it can be managed
            session = storage.get_session(session_id)
            if ce_ok:
                session['ce']['entry_fill_price'] = ce_res.get('fill_price', 0)
                session['ce']['entry_order_id'] = ce_res.get('order_id')
            if pe_ok:
                session['pe']['entry_fill_price'] = pe_res.get('fill_price', 0)
                session['pe']['entry_order_id'] = pe_res.get('order_id')

            session['strategy_status'] = 'PARTIAL_ENTRY'
            session['partial_entry'] = {
                'ce_filled': ce_ok,
                'pe_filled': pe_ok,
                'ce_result': str(ce_res)[:300],
                'pe_result': str(pe_res)[:300],
                'timestamp': datetime.utcnow().isoformat(),
            }
            storage.save_session(session)

            filled_side = 'CE' if ce_ok else 'PE'
            failed_side = 'PE' if ce_ok else 'CE'
            log_activity('partial_entry',
                f"PARTIAL ENTRY: {filled_side} filled but {failed_side} failed! "
                f"Manual intervention needed.",
                session_id=session_id, severity='error',
                details={'ce_filled': ce_ok, 'pe_filled': pe_ok})
            emit_status_change(session_id, 'STARTING', 'PARTIAL_ENTRY',
                f'Partial entry: {filled_side} filled, {failed_side} failed')
        else:
            # Both legs failed — clear premiums so UI doesn't show fake positions
            log_activity('entry_failed',
                f"Entry orders failed: {error_msg}",
                session_id=session_id, severity='error',
                details={'ce_result': str(ce_res)[:200], 'pe_result': str(pe_res)[:200]})
            session = storage.get_session(session_id)
            session['strategy_status'] = 'IDLE'
            # Reset premiums to 0 since no fills happened
            if 'ce' in session:
                session['ce']['original_premium'] = 0
                session['ce']['entry_fill_price'] = None
            if 'pe' in session:
                session['pe']['original_premium'] = 0
                session['pe']['entry_fill_price'] = None
            session['initial_total_premium'] = 0
            storage.save_session(session)
            emit_status_change(session_id, 'STARTING', 'IDLE',
                f'Entry failed: {error_msg}')
            # Clear stale "placing order..." progress messages
            from .mmm_activity import resolve_progress_activities
            resolve_progress_activities(session_id)
        return

    # ====== SUCCESS: Both legs filled ======
    ce_res = entry_result.get('ce', {})
    pe_res = entry_result.get('pe', {})
    ce_fill = ce_res.get('fill_price', 0)
    pe_fill = pe_res.get('fill_price', 0)

    session = storage.get_session(session_id)

    session['ce']['entry_fill_price'] = ce_fill
    session['ce']['entry_order_id'] = ce_res.get('order_id')
    session['ce']['original_premium'] = ce_fill
    session['pe']['entry_fill_price'] = pe_fill
    session['pe']['entry_order_id'] = pe_res.get('order_id')
    session['pe']['original_premium'] = pe_fill

    # Track all order IDs placed by this session (isolation audit trail)
    session.setdefault('mmm_order_ids', [])
    if ce_res.get('order_id'):
        session['mmm_order_ids'].append(str(ce_res['order_id']))
    if pe_res.get('order_id'):
        session['mmm_order_ids'].append(str(pe_res['order_id']))

    # Update trigger snapshots to actual fill prices
    ce_strike_key = str(int(session['ce'].get('active_strike', 0)))
    pe_strike_key = str(int(session['pe'].get('active_strike', 0)))
    session['ce']['trigger_snapshot'] = {ce_strike_key: ce_fill}
    session['pe']['trigger_snapshot'] = {pe_strike_key: pe_fill}

    actual_premium = (ce_fill + pe_fill) * lots * LOT_SIZE_BTC
    session['actual_total_premium'] = actual_premium
    session['total_premium_collected'] = actual_premium
    session['execution_timestamp'] = datetime.utcnow().isoformat()

    # Transition to RUNNING
    session['strategy_status'] = 'RUNNING'
    session['entry_time'] = datetime.utcnow().isoformat()
    session['last_heartbeat'] = datetime.utcnow().isoformat()
    storage.save_session(session)

    emit_status_change(session_id, 'STARTING', 'RUNNING', 'Entry orders filled')

    log.info(
        f"MMM {session_id}: Entry executed — "
        f"CE filled@${ce_fill:.2f}, PE filled@${pe_fill:.2f}, "
        f"total_premium=${actual_premium:.2f}"
    )

    log_activity('entry_complete',
        f"Entry filled: CE@${ce_fill:.2f} + PE@${pe_fill:.2f} = ${actual_premium:.2f} total",
        session_id=session_id, severity='success',
        details={'ce_fill': ce_fill, 'pe_fill': pe_fill, 'total_premium': actual_premium})

    # Clear stale "placing order..." progress messages now that entry is complete
    from .mmm_activity import resolve_progress_activities
    resolve_progress_activities(session_id)

    log_activity('session_started',
        f"Session {session_id} is now RUNNING — heartbeat monitor active",
        session_id=session_id, severity='success')

    # Start the heartbeat monitor
    start_session_monitor(session_id, session)


@mmm_bp.route('/session/<session_id>/pause', methods=['POST'])
def pause_session(session_id: str):
    """
    Pause a running session. Heartbeat stops, positions remain open.
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}',
            }), 404

        status = session.get('strategy_status', 'IDLE')
        if status not in ('RUNNING', 'BOTH_SIDES_UP'):
            return jsonify({
                'success': False,
                'error': f"Cannot pause session in {status} state. Must be RUNNING.",
            }), 400

        old_status = status
        new_status = 'PAUSED'

        storage.update_session(session_id, {
            'strategy_status': new_status,
        })

        emit_status_change(session_id, old_status, new_status, 'User paused')
        pause_session_monitor(session_id, 'User paused')
        log.info(f"MMM session {session_id} paused")

        return jsonify({
            'success': True,
            'message': f'Session {session_id} paused',
            'status': new_status,
        })

    except Exception as e:
        log.exception(f"Failed to pause MMM session {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>/resume', methods=['POST'])
def resume_session(session_id: str):
    """
    Resume a paused session. Heartbeat resumes.
    """
    try:
        # Check guardian
        signal = _check_guardian_signal()
        if signal != 'GO':
            return jsonify({
                'success': False,
                'error': f'Guardian signal is {signal}. Trading disabled.',
            }), 403

        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}',
            }), 404

        status = session.get('strategy_status', 'IDLE')
        if status != 'PAUSED':
            return jsonify({
                'success': False,
                'error': f"Cannot resume session in {status} state. Must be PAUSED.",
            }), 400

        old_status = status
        new_status = 'RUNNING'

        storage.update_session(session_id, {
            'strategy_status': new_status,
            'last_heartbeat': datetime.utcnow().isoformat(),
        })

        emit_status_change(session_id, old_status, new_status, 'User resumed')
        resume_session_monitor(session_id, 'User resumed')
        log.info(f"MMM session {session_id} resumed")

        return jsonify({
            'success': True,
            'message': f'Session {session_id} resumed',
            'status': new_status,
        })

    except Exception as e:
        log.exception(f"Failed to resume MMM session {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>/stop', methods=['POST'])
def stop_session(session_id: str):
    """
    Stop a session. Heartbeat stops. Positions should be managed manually or
    auto-close engine handles them.

    Request body (optional):
        { reason: str }
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}',
            }), 404

        status = session.get('strategy_status', 'IDLE')
        if status in ('IDLE', 'STOPPED'):
            return jsonify({
                'success': False,
                'error': f'Session already in {status} state',
            }), 400

        data = request.get_json(silent=True) or {}
        reason = data.get('reason', 'User stopped')

        old_status = status
        new_status = 'STOPPED'

        storage.update_session(session_id, {
            'strategy_status': new_status,
            'stopped_at': datetime.utcnow().isoformat(),
            'stop_reason': reason,
        })

        stop_session_monitor(session_id, reason)
        emit_status_change(session_id, old_status, new_status, reason)
        log.info(f"MMM session {session_id} stopped: {reason}")

        return jsonify({
            'success': True,
            'message': f'Session {session_id} stopped',
            'status': new_status,
            'reason': reason,
        })

    except Exception as e:
        log.exception(f"Failed to stop MMM session {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Both-Sides-Up User Decision — Section 8
# =============================================================================

@mmm_bp.route('/session/<session_id>/both_sides_decision', methods=['POST'])
def both_sides_decision(session_id: str):
    """
    User's decision on both-sides-up scenario.

    Section 8: When both CE and PE premiums exceed triggers simultaneously,
    the algo pauses and asks the user which side to adjust.

    Request body:
        {
            decision: str ('adjust_ce' | 'adjust_pe' | 'skip')
        }
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}',
            }), 404

        status = session.get('strategy_status', 'IDLE')
        if status != 'BOTH_SIDES_UP':
            return jsonify({
                'success': False,
                'error': f"Session is not in BOTH_SIDES_UP state (current: {status})",
            }), 400

        data = request.get_json() or {}
        decision = data.get('decision', '')

        if decision not in ('adjust_ce', 'adjust_pe', 'skip'):
            return jsonify({
                'success': False,
                'error': "decision must be 'adjust_ce', 'adjust_pe', or 'skip'",
            }), 400

        # Record the decision and resume
        updates = {
            'strategy_status': 'RUNNING',
            'both_sides_decision': decision,
            'both_sides_decided_at': datetime.utcnow().isoformat(),
            'last_heartbeat': datetime.utcnow().isoformat(),
        }

        # Track in adjustment history
        history_entry = {
            'type': 'both_sides_decision',
            'decision': decision,
            'timestamp': datetime.utcnow().isoformat(),
        }
        adj_history = session.get('adjustment_history', [])
        adj_history.append(history_entry)
        updates['adjustment_history'] = adj_history

        storage.update_session(session_id, updates)

        emit_status_change(session_id, 'BOTH_SIDES_UP', 'RUNNING',
                           f'Both-sides decision: {decision}')

        log.info(f"MMM session {session_id} both-sides decision: {decision}")

        return jsonify({
            'success': True,
            'message': f'Decision recorded: {decision}',
            'status': 'RUNNING',
        })

    except Exception as e:
        log.exception(f"Failed to process both-sides decision for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Parameter Management — Section 19: Hot Reload
# =============================================================================

@mmm_bp.route('/params/info', methods=['GET'])
def get_params_info():
    """
    Get parameter metadata: types, ranges, hot-reload status, descriptions.
    Used by WebUI to render the config panel dynamically.
    """
    try:
        return jsonify({
            'success': True,
            'params': get_param_info(),
            'defaults': DEFAULT_PARAMS,
            'hot_reload_params': list(get_hot_reload_params()),
        })
    except Exception as e:
        log.exception("Failed to get param info")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>/params', methods=['GET'])
def get_session_params(session_id: str):
    """Get current parameters for a session."""
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}',
            }), 404

        return jsonify({
            'success': True,
            'params': session.get('params', DEFAULT_PARAMS),
            'status': session.get('strategy_status', 'IDLE'),
        })

    except Exception as e:
        log.exception(f"Failed to get params for session {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>/params', methods=['PATCH'])
def update_session_params(session_id: str):
    """
    Update parameters for a session.

    If session is RUNNING/PAUSED, only hot-reloadable parameters may be changed.
    If session is IDLE, any parameter may be changed.

    Request body:
        { param_name: value, ... }

    Returns:
        {success: true, params: {...}, changed: [...]}
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}',
            }), 404

        status = session.get('strategy_status', 'IDLE')
        is_running = status in ('RUNNING', 'PAUSED', 'BOTH_SIDES_UP')

        data = request.get_json() or {}
        if not data:
            return jsonify({
                'success': False,
                'error': 'No parameters provided',
            }), 400

        # Validate with hot-reload restriction if running
        validated, errors = validate_params(data, hot_only=is_running)
        if errors:
            return jsonify({
                'success': False,
                'error': 'Parameter validation failed',
                'details': errors,
            }), 400

        if not validated:
            return jsonify({
                'success': False,
                'error': 'No valid parameters to update',
            }), 400

        # Merge with existing params
        current_params = session.get('params', {})
        changed_keys = []

        for key, value in validated.items():
            if current_params.get(key) != value:
                current_params[key] = value
                changed_keys.append(key)

        if not changed_keys:
            return jsonify({
                'success': True,
                'message': 'No parameters changed (values identical)',
                'params': current_params,
                'changed': [],
            })

        # Persist
        storage.update_session(session_id, {'params': current_params})

        # Emit WebSocket update
        emit_params_changed(session_id, {k: validated[k] for k in changed_keys})

        log.info(f"MMM session {session_id} params updated: {changed_keys}")

        return jsonify({
            'success': True,
            'message': f'Updated {len(changed_keys)} parameter(s)',
            'params': current_params,
            'changed': changed_keys,
        })

    except Exception as e:
        log.exception(f"Failed to update params for session {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Session History & Diagnostics
# =============================================================================

@mmm_bp.route('/session/<session_id>/history', methods=['GET'])
def get_session_history(session_id: str):
    """
    Get adjustment history and P&L timeline for a session.

    Query params:
        limit: int - Max number of P&L history entries (default: 200)
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}',
            }), 404

        limit = int(request.args.get('limit', 200))

        pnl_history = session.get('pnl_history', [])
        if len(pnl_history) > limit:
            pnl_history = pnl_history[-limit:]

        return jsonify({
            'success': True,
            'adjustment_history': session.get('adjustment_history', []),
            'pnl_history': pnl_history,
            'summary': get_session_summary(session),
        })

    except Exception as e:
        log.exception(f"Failed to get history for session {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>/state', methods=['GET'])
def get_session_state(session_id: str):
    """
    Get full CE/PE state (detailed positions) for diagnostics.
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}',
            }), 404

        return jsonify({
            'success': True,
            'ce': session.get('ce', {}),
            'pe': session.get('pe', {}),
            'last_aggressor': session.get('last_aggressor', 'NONE'),
            'adjustment_count': session.get('adjustment_count', 0),
            'reversal_count': session.get('reversal_count', 0),
            'shift_count': session.get('shift_count', 0),
            'close_at_5_count': session.get('close_at_5_count', 0),
            'cooldown_active': session.get('cooldown_active', False),
        })

    except Exception as e:
        log.exception(f"Failed to get state for session {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Health / Status
# =============================================================================

@mmm_bp.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint."""
    try:
        storage = get_storage()
        active_count = len(storage.get_active_session_ids())
        total_count = storage.get_session_count()

        return jsonify({
            'success': True,
            'status': 'healthy',
            'active_sessions': active_count,
            'total_sessions': total_count,
            'timestamp': datetime.utcnow().isoformat(),
        })

    except Exception as e:
        log.exception("MMM health check failed")
        return jsonify({
            'success': False,
            'status': 'unhealthy',
            'error': str(e),
        }), 500


# =============================================================================
# Background Activity Log
# =============================================================================

@mmm_bp.route('/activities', methods=['GET'])
def get_activities():
    """
    Get recent background activity log entries.

    Query params:
        limit: int (default 50, max 200)
        session_id: str (optional filter)
        severity: str (optional filter: info|success|warning|error|progress)

    Returns:
        { success, activities: [...], count: int }
    """
    try:
        from .mmm_activity import get_activity_log

        limit = min(int(request.args.get('limit', 50)), 200)
        session_id = request.args.get('session_id')
        severity = request.args.get('severity')

        activity_log = get_activity_log()
        activities = activity_log.get_recent(
            limit=limit,
            session_id=session_id,
            severity=severity,
        )

        return jsonify({
            'success': True,
            'activities': activities,
            'count': len(activities),
        })

    except Exception as e:
        log.exception("Failed to get activities")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Phase 2: Initialization — Strike Selection & Entry
# =============================================================================

@mmm_bp.route('/expiries', methods=['GET'])
def get_expiries():
    """
    Get available BTC option expiry dates.

    Query params:
        underlying: str (default 'BTC')

    Returns:
        { success, expiries: ['DDMMYYYY', ...] }
    """
    try:
        underlying = request.args.get('underlying', 'BTC')
        initializer = get_initializer()
        expiries = initializer.get_available_expiries(underlying)

        return jsonify({
            'success': True,
            'expiries': expiries,
            'underlying': underlying,
        })

    except Exception as e:
        log.exception("Failed to fetch expiries")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/spot-price', methods=['GET'])
def get_spot_price():
    """
    Get current BTC spot price.

    Query params:
        underlying: str (default 'BTC')
    """
    try:
        underlying = request.args.get('underlying', 'BTC')
        initializer = get_initializer()
        spot = initializer.get_spot_price(underlying)

        return jsonify({
            'success': True,
            'spot_price': spot,
            'underlying': underlying,
        })

    except Exception as e:
        log.exception("Failed to fetch spot price")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/preview-strikes', methods=['POST'])
def preview_strikes():
    """
    Preview which strikes would be selected for given desired premiums.

    Section 3, Mode A: Auto-find strikes closest to desired premium.

    Body (JSON):
        desired_ce_premium: float  (required)
        desired_pe_premium: float  (required)
        expiry: str                (required, any format)
        underlying: str            (optional, default 'BTC')

    Returns:
        {
            success, spot_price,
            ce: { strike, premium, symbol, bid, ask, delta, oi },
            pe: { strike, premium, symbol, bid, ask, delta, oi },
            alternatives: { ce: [...], pe: [...] }
        }
    """
    try:
        data = request.get_json(force=True)

        desired_ce = data.get('desired_ce_premium')
        desired_pe = data.get('desired_pe_premium')
        expiry = data.get('expiry')
        underlying = data.get('underlying', 'BTC')

        if desired_ce is None or desired_pe is None:
            return jsonify({
                'success': False,
                'error': 'desired_ce_premium and desired_pe_premium are required',
            }), 400

        if not expiry:
            return jsonify({
                'success': False,
                'error': 'expiry is required',
            }), 400

        try:
            desired_ce = float(desired_ce)
            desired_pe = float(desired_pe)
        except (TypeError, ValueError):
            return jsonify({
                'success': False,
                'error': 'Premium values must be numbers',
            }), 400

        if desired_ce <= 0 or desired_pe <= 0:
            return jsonify({
                'success': False,
                'error': 'Premium values must be positive',
            }), 400

        initializer = get_initializer()
        result = initializer.preview_strikes(desired_ce, desired_pe, expiry, underlying)

        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        log.exception("Failed to preview strikes")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/check-liquidity', methods=['POST'])
def check_liquidity():
    """
    Check bid-side liquidity for a specific option symbol.

    Section 15.6: Check before selling.

    Body (JSON):
        symbol: str   (option symbol, e.g. 'C-BTC-100000-150226')
        lots: int     (how many lots we want to sell)
    """
    try:
        data = request.get_json(force=True)
        symbol = data.get('symbol')
        lots = data.get('lots', 1)

        if not symbol:
            return jsonify({
                'success': False,
                'error': 'symbol is required',
            }), 400

        initializer = get_initializer()
        result = initializer.check_liquidity(symbol, int(lots))

        return jsonify({
            'success': True,
            **result,
        })

    except Exception as e:
        log.exception("Failed to check liquidity")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>/init-fresh', methods=['POST'])
def init_session_fresh(session_id: str):
    """
    Initialize a session with fresh entry (Mode A / confirmed strikes).

    After preview-strikes, the user confirms their chosen CE & PE strikes.
    This endpoint records the entry into the session state.

    Body (JSON):
        ce_strike: float       (chosen CE strike)
        ce_premium: float      (premium at which we sell CE — typically bid)
        ce_symbol: str         (full option symbol)
        pe_strike: float       (chosen PE strike)
        pe_premium: float      (premium at which we sell PE — typically bid)
        pe_symbol: str         (full option symbol)
        lots: int              (number of lots per side)
        expiry: str            (expiry date)

    This does NOT place orders — it just initializes the session state.
    Order placement will be handled by the bot engine (Phase 4).
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}',
            }), 404

        status = session.get('strategy_status', 'IDLE')
        if status not in ('IDLE', 'STOPPED'):
            return jsonify({
                'success': False,
                'error': f'Session must be in IDLE or STOPPED status to initialize. '
                         f'Current: {status}',
            }), 400

        data = request.get_json(force=True)

        # Validate required fields
        required_fields = [
            'ce_strike', 'ce_premium', 'ce_symbol',
            'pe_strike', 'pe_premium', 'pe_symbol',
            'lots', 'expiry',
        ]
        missing = [f for f in required_fields if f not in data or data[f] is None]
        if missing:
            return jsonify({
                'success': False,
                'error': f'Missing required fields: {", ".join(missing)}',
            }), 400

        ce_strike = float(data['ce_strike'])
        ce_premium = float(data['ce_premium'])
        pe_strike = float(data['pe_strike'])
        pe_premium = float(data['pe_premium'])
        lots = int(data['lots'])
        expiry = normalize_expiry(data['expiry'])

        if lots <= 0:
            return jsonify({
                'success': False,
                'error': 'lots must be positive',
            }), 400

        # Initialize CE side
        initialize_side_from_entry(
            session,
            side='ce',
            strike=ce_strike,
            premium=ce_premium,
            lots=lots,
        )

        # Initialize PE side
        initialize_side_from_entry(
            session,
            side='pe',
            strike=pe_strike,
            premium=pe_premium,
            lots=lots,
        )

        # Store symbols
        session['ce']['symbol'] = data['ce_symbol']
        session['pe']['symbol'] = data['pe_symbol']

        # Calculate total premium (Section 3: Initial State After Entry)
        # Premiums are per-BTC, 1 lot = LOT_SIZE_BTC
        total_premium = (ce_premium + pe_premium) * lots * LOT_SIZE_BTC

        # Update session
        # Keep strategy_status as IDLE (ready to start)
        session['entry_mode'] = 'fresh'
        session['expiry'] = expiry
        session['params']['expiry'] = expiry
        session['initial_total_premium'] = total_premium
        session['entry_time'] = datetime.utcnow().isoformat()
        session['updated_at'] = datetime.utcnow().isoformat()
        session['lots'] = lots

        storage.save_session(session)

        emit_status_change(session_id, 'IDLE', 'IDLE', 'Initialized with fresh entry')

        from .mmm_activity import log_activity
        log_activity('session_initialized',
            f"Fresh init: CE {ce_strike}@{ce_premium:.2f} + PE {pe_strike}@{pe_premium:.2f}, {lots} lots, expiry={expiry}",
            session_id=session_id, severity='info',
            details={'ce_strike': ce_strike, 'ce_premium': ce_premium,
                     'pe_strike': pe_strike, 'pe_premium': pe_premium,
                     'lots': lots, 'expiry': expiry, 'total_premium': total_premium})

        log.info(
            f"MMM session {session_id} initialized FRESH: "
            f"CE={ce_strike}@{ce_premium}, PE={pe_strike}@{pe_premium}, "
            f"lots={lots}, expiry={expiry}, total_premium={total_premium}"
        )

        return jsonify({
            'success': True,
            'message': 'Session initialized with fresh entry',
            'session_id': session_id,
            'entry': {
                'ce_strike': ce_strike,
                'ce_premium': ce_premium,
                'pe_strike': pe_strike,
                'pe_premium': pe_premium,
                'lots': lots,
                'expiry': expiry,
                'total_premium': total_premium,
            },
        })

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        log.exception(f"Failed to init-fresh session {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>/init-import', methods=['POST'])
def init_session_import(session_id: str):
    """
    Initialize a session by importing an existing position (Mode B).

    Section 3, Mode B: User already has positions on the exchange.
    They provide the fill details manually.

    Body (JSON):
        ce_strike: float       (existing CE strike)
        ce_fill_price: float   (price at which CE was sold)
        ce_symbol: str         (symbol)
        pe_strike: float       (existing PE strike)
        pe_fill_price: float   (price at which PE was sold)
        pe_symbol: str         (symbol)
        lots: int              (number of lots per side)
        expiry: str            (expiry date)
        current_ce_price: float (optional — current mark for P&L calc)
        current_pe_price: float (optional — current mark for P&L calc)
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}',
            }), 404

        status = session.get('strategy_status', 'IDLE')
        if status not in ('IDLE', 'STOPPED'):
            return jsonify({
                'success': False,
                'error': f'Session must be in IDLE or STOPPED status to import. '
                         f'Current: {status}',
            }), 400

        data = request.get_json(force=True)

        required_fields = [
            'ce_strike', 'ce_fill_price', 'ce_symbol',
            'pe_strike', 'pe_fill_price', 'pe_symbol',
            'lots', 'expiry',
        ]
        missing = [f for f in required_fields if f not in data or data[f] is None]
        if missing:
            return jsonify({
                'success': False,
                'error': f'Missing required fields: {", ".join(missing)}',
            }), 400

        ce_strike = float(data['ce_strike'])
        ce_fill = float(data['ce_fill_price'])
        pe_strike = float(data['pe_strike'])
        pe_fill = float(data['pe_fill_price'])
        lots = int(data['lots'])
        expiry = normalize_expiry(data['expiry'])

        if lots <= 0:
            return jsonify({
                'success': False,
                'error': 'lots must be positive',
            }), 400

        # Initialize CE side
        initialize_side_from_entry(
            session,
            side='ce',
            strike=ce_strike,
            premium=ce_fill,
            lots=lots,
        )

        # Initialize PE side
        initialize_side_from_entry(
            session,
            side='pe',
            strike=pe_strike,
            premium=pe_fill,
            lots=lots,
        )

        # Store symbols
        session['ce']['symbol'] = data['ce_symbol']
        session['pe']['symbol'] = data['pe_symbol']

        total_premium = (ce_fill + pe_fill) * lots * LOT_SIZE_BTC

        # Keep strategy_status as IDLE (ready to start)
        session['entry_mode'] = 'import'
        session['expiry'] = expiry
        session['params']['expiry'] = expiry
        session['initial_total_premium'] = total_premium
        session['entry_time'] = datetime.utcnow().isoformat()
        session['updated_at'] = datetime.utcnow().isoformat()
        session['lots'] = lots

        # If the user provided current prices, set them for initial P&L
        if data.get('current_ce_price') is not None:
            session['ce']['current_price'] = float(data['current_ce_price'])
        if data.get('current_pe_price') is not None:
            session['pe']['current_price'] = float(data['current_pe_price'])

        storage.save_session(session)

        emit_status_change(session_id, 'IDLE', 'IDLE', 'Initialized with imported position')

        from .mmm_activity import log_activity
        log_activity('session_initialized',
            f"Import init: CE {ce_strike}@{ce_fill:.2f} + PE {pe_strike}@{pe_fill:.2f}, {lots} lots, expiry={expiry}",
            session_id=session_id, severity='info',
            details={'ce_strike': ce_strike, 'ce_fill_price': ce_fill,
                     'pe_strike': pe_strike, 'pe_fill_price': pe_fill,
                     'lots': lots, 'expiry': expiry, 'total_premium': total_premium})

        log.info(
            f"MMM session {session_id} initialized IMPORT: "
            f"CE={ce_strike}@{ce_fill}, PE={pe_strike}@{pe_fill}, "
            f"lots={lots}, expiry={expiry}, total_premium={total_premium}"
        )

        return jsonify({
            'success': True,
            'message': 'Session initialized with imported position',
            'session_id': session_id,
            'entry': {
                'ce_strike': ce_strike,
                'ce_fill_price': ce_fill,
                'pe_strike': pe_strike,
                'pe_fill_price': pe_fill,
                'lots': lots,
                'expiry': expiry,
                'total_premium': total_premium,
            },
        })

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        log.exception(f"Failed to init-import session {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Phase 2 Enhanced: Full Chain Data & Manual Selection & Smart Execution
# =============================================================================

@mmm_bp.route('/chain-data', methods=['GET'])
def get_chain_data():
    """
    Get the full options chain for manual strike browsing.

    Powers the MMMStrikeSelector component — user sees all strikes
    with bid/ask/mid/delta/OI and clicks to select CE and PE.

    Query params:
        expiry: str        (required, any format)
        underlying: str    (optional, default 'BTC')

    Returns:
        {
            success, spot_price, atm_strike,
            chain: [{ strike, call: {...}, put: {...}, moneyness_call, moneyness_put }],
            strike_count
        }
    """
    try:
        expiry = request.args.get('expiry')
        underlying = request.args.get('underlying', 'BTC')

        if not expiry:
            return jsonify({
                'success': False,
                'error': 'expiry is required',
            }), 400

        initializer = get_initializer()
        result = initializer.get_full_chain(expiry, underlying)

        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        log.exception("Failed to get chain data")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/validate-selection', methods=['POST'])
def validate_selection():
    """
    Validate a manually selected CE+PE pair before execution.

    Called when user picks specific strikes from the chain browser.
    Returns warnings/errors about liquidity, ITM risk, spread width.

    Body (JSON):
        ce_symbol: str    (required)
        pe_symbol: str    (required)
        lots: int         (required)
        expiry: str       (required)
        underlying: str   (optional, default 'BTC')

    Returns:
        {
            valid: bool,
            spot_price, ce: {...}, pe: {...},
            warnings: [...], errors: [...],
            estimated_total_premium
        }
    """
    try:
        data = request.get_json(force=True)

        ce_symbol = data.get('ce_symbol')
        pe_symbol = data.get('pe_symbol')
        lots = data.get('lots')
        expiry = data.get('expiry')
        underlying = data.get('underlying', 'BTC')

        if not all([ce_symbol, pe_symbol, lots, expiry]):
            return jsonify({
                'success': False,
                'error': 'ce_symbol, pe_symbol, lots, and expiry are required',
            }), 400

        initializer = get_initializer()
        result = initializer.validate_manual_selection(
            ce_symbol, pe_symbol, int(lots), expiry, underlying
        )

        return jsonify({
            'success': True,
            **result,
        })

    except Exception as e:
        log.exception("Failed to validate selection")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>/execute-entry', methods=['POST'])
def execute_entry(session_id: str):
    """
    Execute smart entry — place CE and PE sell orders at mid-price.

    Uses mmm_executor.py for smart execution:
      1. Fetch orderbook → calculate mid-price
      2. Place limit sell at mid-price (post-only)
      3. Wait 60s for fill
      4. If not filled, amend to new mid-price
      5. Repeat up to 10 times

    The session must already be in 'initialized' status (via init-fresh
    or init-import with pending execution).

    Body (JSON):
        mode: str    ('auto' or 'manual') — just for logging

    Returns:
        {
            success: bool,
            ce_result: { filled, fill_price, order_id, execution_type, attempts },
            pe_result: { ... },
            total_premium_collected: float,
        }
    """
    try:
        # Check guardian signal
        signal = _check_guardian_signal()
        if signal != 'GO':
            return jsonify({
                'success': False,
                'error': f'Trading blocked by guardian signal: {signal}',
            }), 403

        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}',
            }), 404

        status = session.get('strategy_status', 'IDLE')
        if status not in ('IDLE', 'STOPPED'):
            return jsonify({
                'success': False,
                'error': (
                    f'Session must be in IDLE status to execute entry. '
                    f'Current: {status}'
                ),
            }), 400

        ce = session.get('ce', {})
        pe = session.get('pe', {})
        lots = session.get('lots', 0)

        ce_symbol = ce.get('symbol')
        pe_symbol = pe.get('symbol')

        if not ce_symbol or not pe_symbol:
            return jsonify({
                'success': False,
                'error': 'Session CE/PE symbols not set. Initialize first.',
            }), 400

        if lots <= 0:
            return jsonify({
                'success': False,
                'error': 'Session lots not set.',
            }), 400

        # Execute via mmm_executor
        from .mmm_executor import get_executor
        import asyncio
        executor = get_executor()

        result = asyncio.run(executor.execute_entry(ce_symbol, pe_symbol, lots))

        if result.get('success'):
            # Update session with actual fill prices
            ce_res = result.get('ce', {})
            pe_res = result.get('pe', {})

            if ce_res.get('filled'):
                session['ce']['entry_fill_price'] = ce_res['fill_price']
                session['ce']['entry_order_id'] = ce_res.get('order_id')
            if pe_res.get('filled'):
                session['pe']['entry_fill_price'] = pe_res['fill_price']
                session['pe']['entry_order_id'] = pe_res.get('order_id')

            # Calculate actual total premium
            ce_fill = ce_res.get('fill_price', 0)
            pe_fill = pe_res.get('fill_price', 0)
            actual_premium = (ce_fill * lots) + (pe_fill * lots)

            session['actual_total_premium'] = actual_premium
            # Keep strategy_status as IDLE — user starts session manually
            session['execution_timestamp'] = datetime.utcnow().isoformat()
            session['updated_at'] = datetime.utcnow().isoformat()

            storage.save_session(session)

            emit_status_change(session_id, 'IDLE', 'IDLE', 'Entry executed')

            log.info(
                f"MMM {session_id} entry executed: "
                f"CE filled={ce_res.get('filled')}@{ce_fill}, "
                f"PE filled={pe_res.get('filled')}@{pe_fill}, "
                f"total_premium={actual_premium}"
            )

        return jsonify(result)

    except Exception as e:
        log.exception(f"Failed to execute entry for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Phase 3+: Monitor & Live Data Endpoints
# =============================================================================

@mmm_bp.route('/session/<session_id>/monitor', methods=['GET'])
def get_monitor_status(session_id: str):
    """Get heartbeat monitor status for a session."""
    try:
        monitor = get_monitor(session_id)
        if not monitor:
            return jsonify({
                'success': True,
                'monitor': None,
                'message': 'No active monitor for this session',
            })

        return jsonify({
            'success': True,
            'monitor': {
                'session_id': session_id,
                'running': monitor.is_running,
                'paused': monitor.is_paused,
                'heartbeat_count': getattr(monitor, '_heartbeat_count', 0),
            },
        })
    except Exception as e:
        log.exception(f"Failed to get monitor status for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/monitors', methods=['GET'])
def list_monitors():
    """Get all active monitors."""
    try:
        monitors = get_all_monitors()
        result = {}
        for sid, mon in monitors.items():
            result[sid] = {
                'running': mon.is_running,
                'paused': mon.is_paused,
            }

        return jsonify({
            'success': True,
            'monitors': result,
            'count': len(result),
        })
    except Exception as e:
        log.exception("Failed to list monitors")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>/positions', methods=['GET'])
def get_positions(session_id: str):
    """Get all positions for a session (active, adjustment, frozen)."""
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        positions = []
        for side_key in ['ce', 'pe']:
            side = session.get(side_key, {})
            if not side:
                continue

            label = side_key.upper()

            # Original position
            if side.get('original_lots', 0) > 0:
                positions.append({
                    'type': 'original',
                    'side': label,
                    'strike': side.get('active_strike') or side.get('original_strike'),
                    'lots': side['original_lots'],
                    'premium': side.get('original_premium'),
                    'symbol': side.get('symbol'),
                })

            # Adjustment fills
            for fill in (side.get('adjustment_fills') or []):
                positions.append({
                    'type': 'adjustment',
                    'side': label,
                    'strike': fill.get('strike') or side.get('active_strike'),
                    'lots': fill.get('lots', 0),
                    'premium': fill.get('premium'),
                    'timestamp': fill.get('timestamp'),
                })

            # Frozen positions
            for fpos in (side.get('frozen_positions') or []):
                positions.append({
                    'type': 'frozen',
                    'side': label,
                    'strike': fpos.get('strike'),
                    'lots': fpos.get('lots', 0),
                    'premium': fpos.get('premium'),
                })

        # Include last reconciliation data if available
        recon = session.get('last_reconciliation')

        return jsonify({
            'success': True,
            'positions': positions,
            'last_reconciliation': recon,
        })

    except Exception as e:
        log.exception(f"Failed to get positions for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/exchange/positions', methods=['GET'])
def get_exchange_positions():
    """
    Query ACTUAL exchange positions (options only).

    Returns the REAL state on the exchange, independent of any session.
    This is the \"source of truth\" the algo should match.
    """
    import asyncio
    try:
        from config.loader import get_api_credentials
        from bot.api.async_delta_client import AsyncDeltaClient

        creds = get_api_credentials()
        client = AsyncDeltaClient(
            api_key=creds.get('api_key', ''),
            api_secret=creds.get('api_secret', ''),
            testnet=creds.get('testnet', False) or False,
        )

        async def fetch():
            resp = await client._request_with_retry(
                method="GET",
                path="/v2/positions",
                params={"product_types": "options"},
            )
            return resp.get('result', [])

        positions_raw = asyncio.run(fetch())

        positions = []
        for pos in (positions_raw if isinstance(positions_raw, list) else []):
            size = float(pos.get('size', 0))
            if abs(size) < 0.01:
                continue

            product = pos.get('product', {})
            positions.append({
                'symbol': product.get('symbol', '') or pos.get('symbol', ''),
                'size': size,
                'abs_size': abs(size),
                'side': 'short' if size < 0 else 'long',
                'entry_price': float(pos.get('entry_price', 0)),
                'mark_price': float(pos.get('mark_price', 0)),
                'unrealized_pnl': float(pos.get('unrealized_pnl', 0)),
                'product_id': product.get('id'),
                'strike': product.get('strike_price'),
                'option_type': product.get('contract_type', ''),
            })

        return jsonify({
            'success': True,
            'positions': positions,
            'count': len(positions),
            'timestamp': datetime.utcnow().isoformat(),
        })

    except Exception as e:
        log.exception("Failed to fetch exchange positions")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/exchange/orders', methods=['GET'])
def get_exchange_orders():
    """
    Query ACTUAL open orders on the exchange (options only).

    Returns pending/open orders the algo may have placed.
    """
    import asyncio
    try:
        from config.loader import get_api_credentials
        from bot.api.async_delta_client import AsyncDeltaClient

        creds = get_api_credentials()
        client = AsyncDeltaClient(
            api_key=creds.get('api_key', ''),
            api_secret=creds.get('api_secret', ''),
            testnet=creds.get('testnet', False) or False,
        )

        async def fetch():
            resp = await client._request_with_retry(
                method="GET",
                path="/v2/orders",
                params={"state": "open"},
            )
            return resp.get('result', [])

        orders_raw = asyncio.run(fetch())

        orders = []
        for o in (orders_raw if isinstance(orders_raw, list) else []):
            product = o.get('product', {})
            orders.append({
                'order_id': o.get('id', ''),
                'symbol': product.get('symbol', '') or o.get('product_symbol', ''),
                'side': o.get('side', ''),
                'size': int(o.get('size', 0)),
                'unfilled_size': int(o.get('unfilled_size', 0)),
                'price': float(o.get('limit_price', 0)),
                'state': o.get('state', ''),
                'order_type': o.get('order_type', ''),
                'created_at': o.get('created_at', ''),
                'product_id': product.get('id'),
            })

        return jsonify({
            'success': True,
            'orders': orders,
            'count': len(orders),
            'timestamp': datetime.utcnow().isoformat(),
        })

    except Exception as e:
        log.exception("Failed to fetch exchange orders")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>/triggers', methods=['GET'])
def get_triggers(session_id: str):
    """Get current trigger data for a session."""
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        triggers = {}
        for side_key in ['ce', 'pe']:
            side = session.get(side_key, {})
            if not side:
                continue
            snap = session.get('trigger_snapshots', {}).get(side_key, {})
            active_strike = str(side.get('active_strike', ''))
            trigger_val = snap.get(active_strike, 0)

            triggers[side_key] = {
                'active_strike': side.get('active_strike'),
                'trigger_value': trigger_val,
                'active_lots': side.get('active_lots', 0),
                'total_lots': side.get('total_lots', 0),
            }

        return jsonify({
            'success': True,
            'triggers': triggers,
            'last_aggressor': session.get('last_aggressor'),
            'cooldown_active': session.get('cooldown_active', False),
        })

    except Exception as e:
        log.exception(f"Failed to get triggers for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>/pnl-timeline', methods=['GET'])
def get_pnl_timeline(session_id: str):
    """Get P&L timeline data points for charting."""
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        limit = request.args.get('limit', 100, type=int)
        timeline = session.get('pnl_timeline', [])

        # Return last N data points
        if len(timeline) > limit:
            timeline = timeline[-limit:]

        return jsonify({
            'success': True,
            'timeline': timeline,
            'current': {
                'realized_pnl': session.get('realized_pnl', 0),
                'unrealized_pnl': session.get('unrealized_pnl', 0),
                'total_fees': session.get('total_fees', 0),
                'peak_pnl': session.get('peak_pnl', 0),
                'total_premium_collected': session.get('total_premium_collected', 0),
            },
        })

    except Exception as e:
        log.exception(f"Failed to get P&L timeline for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>/safety', methods=['GET'])
def get_safety_status(session_id: str):
    """Get safety checker status for a session."""
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        params = session.get('params', {})

        safety_data = {
            'position_cap': {
                'ce_lots': session.get('ce', {}).get('total_lots', 0),
                'pe_lots': session.get('pe', {}).get('total_lots', 0),
                'max': params.get('max_lots_per_side', 100),
            },
            'adjustments': {
                'count': session.get('adjustment_count', 0),
                'max': params.get('max_adjustments', 30),
            },
            'max_loss': {
                'current': session.get('realized_pnl', 0) + session.get('unrealized_pnl', 0),
                'limit': params.get('max_loss_amount', 5000),
            },
            'peak_pnl': session.get('peak_pnl', 0),
            'trailing_stop': {
                'enabled': params.get('trailing_stop_pct', 0) > 0,
                'pct': params.get('trailing_stop_pct', 0),
                'floor': session.get('peak_pnl', 0) * (1 - params.get('trailing_stop_pct', 0.5)),
            },
            'cooldown_active': session.get('cooldown_active', False),
            'reversal_count': session.get('reversal_count', 0),
        }

        return jsonify({'success': True, 'safety': safety_data})

    except Exception as e:
        log.exception(f"Failed to get safety status for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500
