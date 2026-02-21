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
from .mmm_initializer import get_initializer, normalize_expiry, expiry_to_utc_datetime
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

        # Safety check: Never overwrite a non-STOPPED session
        storage = get_storage()
        existing = storage.get_session(session['session_id'])
        if existing:
            ex_status = existing.get('strategy_status', 'IDLE')
            if ex_status not in ('IDLE', 'STOPPED'):
                log.error(
                    f"Session ID collision! {session['session_id']} already exists "
                    f"with status {ex_status}. Refusing to overwrite."
                )
                return jsonify({
                    'success': False,
                    'error': (
                        f"Session '{session['session_id']}' already exists and is "
                        f"{ex_status}. Cannot overwrite an active session. "
                        f"Please stop it first or use a different expiry."
                    ),
                }), 409  # 409 Conflict
            else:
                # Existing IDLE/STOPPED session — safe to overwrite (recycle the slot)
                log.info(
                    f"Recycling existing {ex_status} session {session['session_id']}"
                )

        # Persist
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


@mmm_bp.route('/session/<session_id>/margin', methods=['GET'])
def get_session_margin_status(session_id: str):
    """
    Get real-time margin utilization and guardian tier for a session.
    Always fetches live exchange wallet data — margin is account-level
    (covers ALL positions: all algos + manual trades).
    Guardian tier thresholds come from session params.
    """
    import asyncio

    try:
        storage = get_storage()
        session = storage.get_session(session_id)
        if not session:
            return jsonify({'success': False, 'error': f'Session not found: {session_id}'}), 404

        params = session.get('params', {})
        guardian_enabled = params.get('margin_monitor_enabled', False)

        # Always fetch real-time margin data from exchange
        from .mmm_margin_guardian import fetch_margin_utilization, evaluate_margin_tier
        from bot.api.async_delta_client import AsyncDeltaClient
        from config.loader import get_api_credentials

        creds = get_api_credentials()
        testnet = creds.get('testnet', False) or False
        rest = AsyncDeltaClient(
            api_key=creds.get('api_key', ''),
            api_secret=creds.get('api_secret', ''),
            testnet=testnet,
        )

        loop = asyncio.new_event_loop()
        try:
            margin_data = loop.run_until_complete(fetch_margin_utilization(rest))
        finally:
            loop.close()

        if not margin_data.get('success'):
            return jsonify({
                'success': False,
                'error': margin_data.get('error', 'Failed to fetch margin data'),
            }), 502

        tier_result = evaluate_margin_tier(margin_data['utilization_pct'], params)

        # Get guardian state from running monitor if available
        monitor = get_monitor(session_id)
        guardian_state = {}
        if monitor and hasattr(monitor, '_margin_guardian'):
            mg = monitor._margin_guardian
            guardian_state = {
                'last_tier': mg.last_tier,
                'last_utilization': mg.last_utilization,
            }

        return jsonify({
            'success': True,
            'enabled': guardian_enabled,
            'tier': tier_result['tier'],
            'utilization_pct': margin_data['utilization_pct'],
            'actions': tier_result['actions'],
            'headroom_pct': tier_result['headroom_pct'],
            'next_threshold': tier_result['next_threshold'],
            'margin_data': {
                'position_margin': margin_data.get('position_margin', 0),
                'order_margin': margin_data.get('order_margin', 0),
                'available_balance': margin_data.get('available_balance', 0),
                'balance': margin_data.get('balance', 0),
                'net_equity': margin_data.get('net_equity', 0),
                'blocked_margin': margin_data.get('blocked_margin', 0),
                'portfolio_margin': margin_data.get('portfolio_margin', 0),
                'total_margin_used': margin_data.get('total_margin_used', 0),
                'cross_position_margin': margin_data.get('cross_position_margin', 0),
                'cross_order_margin': margin_data.get('cross_order_margin', 0),
                'asset_symbol': margin_data.get('asset_symbol', 'USD'),
            },
            'guardian_state': guardian_state,
            'thresholds': {
                'green': params.get('margin_green_pct', 50),
                'yellow': params.get('margin_yellow_pct', 60),
                'orange': params.get('margin_orange_pct', 75),
                'red': params.get('margin_red_pct', 85),
                'critical': params.get('margin_critical_pct', 90),
                'target': params.get('margin_target_pct', 50),
            },
        })

    except Exception as e:
        log.exception(f"Failed to get margin status for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/exchange/margin', methods=['GET'])
def get_exchange_margin():
    """
    Get real-time ACCOUNT-LEVEL margin utilization from Delta Exchange.

    This is exchange-wide: covers ALL positions from all algos, manual trades,
    every product. The exchange is the single source of truth for margin.

    Returns wallet breakdown + all open positions.
    """
    import asyncio

    try:
        from .mmm_margin_guardian import fetch_margin_utilization
        from bot.api.async_delta_client import AsyncDeltaClient
        from config.loader import get_api_credentials

        creds = get_api_credentials()
        testnet = creds.get('testnet', False) or False
        rest = AsyncDeltaClient(
            api_key=creds.get('api_key', ''),
            api_secret=creds.get('api_secret', ''),
            testnet=testnet,
        )

        loop = asyncio.new_event_loop()
        try:
            # Fetch wallet + positions in parallel
            async def _fetch_all():
                import asyncio as _aio
                margin_task = fetch_margin_utilization(rest)
                positions_task = rest.get_positions_margined()
                margin_data, raw_positions = await _aio.gather(
                    margin_task, positions_task, return_exceptions=True
                )
                # Handle exceptions from gather
                if isinstance(margin_data, Exception):
                    margin_data = {'success': False, 'error': str(margin_data)}
                if isinstance(raw_positions, Exception):
                    raw_positions = []
                return margin_data, raw_positions

            margin_data, raw_positions = loop.run_until_complete(_fetch_all())
        finally:
            loop.close()

        if not margin_data.get('success'):
            return jsonify({
                'success': False,
                'error': margin_data.get('error', 'Failed to fetch exchange margin'),
            }), 502

        # Filter and format open positions
        positions = []
        for pos in raw_positions:
            size = float(pos.get('size', 0) or 0)
            if size == 0:
                continue
            entry_price = float(pos.get('entry_price', 0) or 0)
            mark_price = float(pos.get('mark_price', 0) or 0)
            margin = float(pos.get('margin', 0) or 0)
            unrealized = float(pos.get('unrealized_pnl', 0) or 0)
            product = pos.get('product', {})
            symbol = product.get('symbol', pos.get('product_symbol', 'UNKNOWN'))
            contract_type = product.get('contract_type', '')

            positions.append({
                'symbol': symbol,
                'size': size,
                'side': 'long' if size > 0 else 'short',
                'entry_price': entry_price,
                'mark_price': mark_price,
                'margin': margin,
                'unrealized_pnl': unrealized,
                'contract_type': contract_type,
                'product_id': pos.get('product_id', 0),
            })

        # Sort: largest position first (margin may be 0 in portfolio mode)
        positions.sort(key=lambda p: abs(p['size']), reverse=True)

        utilization = margin_data['utilization_pct']

        return jsonify({
            'success': True,
            'utilization_pct': utilization,
            'margin_data': {
                'position_margin': margin_data.get('position_margin', 0),
                'order_margin': margin_data.get('order_margin', 0),
                'available_balance': margin_data.get('available_balance', 0),
                'balance': margin_data.get('balance', 0),
                'net_equity': margin_data.get('net_equity', 0),
                'blocked_margin': margin_data.get('blocked_margin', 0),
                'portfolio_margin': margin_data.get('portfolio_margin', 0),
                'total_margin_used': margin_data.get('total_margin_used', 0),
                'cross_position_margin': margin_data.get('cross_position_margin', 0),
                'cross_order_margin': margin_data.get('cross_order_margin', 0),
                'asset_symbol': margin_data.get('asset_symbol', 'USD'),
            },
            'positions': positions,
            'position_count': len(positions),
            'timestamp': margin_data.get('timestamp', 0),
        })

    except Exception as e:
        log.exception("Failed to get exchange margin")
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
        session['expiry_time'] = expiry_to_utc_datetime(expiry)
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
        session['expiry_time'] = expiry_to_utc_datetime(expiry)
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
# Phase 2C: Adopt Existing Positions from Exchange
# =============================================================================

@mmm_bp.route('/exchange-positions', methods=['GET'])
def get_exchange_positions():
    """
    Fetch all open SHORT BTC options positions from Delta Exchange.

    Powers the "Adopt from Exchange" UI: shows what's open on the exchange
    so the user can select which positions to bring under MMM management.

    Query params:
        expiry: str   (optional, DDMMYYYY — filter to specific expiry)

    Returns:
        {
            success: bool,
            positions: [ {symbol, side, strike, expiry, lots, entry_price,
                          mark_price, unrealized_pnl, iv, delta, theta} ],
            spot_price: float,
            expiries_with_positions: [str],
        }
    """
    try:
        from .mmm_adopter import fetch_exchange_btc_options

        expiry = request.args.get('expiry')
        if expiry:
            expiry = normalize_expiry(expiry)

        result = fetch_exchange_btc_options(expiry_filter=expiry)
        return jsonify(result), 200 if result.get('success') else 500

    except Exception as e:
        log.exception("Failed to fetch exchange positions")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>/adopt', methods=['POST'])
def adopt_positions(session_id: str):
    """
    Adopt existing exchange positions into an IDLE session.

    This is the core of the "Adopt from Exchange" feature. It takes
    user-selected positions, classifies them into active/frozen per side,
    validates them, and builds the full session state.

    Once adopted, the session behaves identically to an import-mode session.
    No changes to monitor, engine, trigger, safety, or any runtime modules.

    Body (JSON):
        positions: [
            {
                symbol: str,
                strike: float,
                lots: int,
                entry_price: float,
                role: str  ('active' or 'frozen'),
                side: str  ('CE' or 'PE'),
            }
        ]
        expiry: str        (DDMMYYYY — required)
        trigger_mode: str  ('current_prices' | 'entry_prices', default 'current_prices')
    """
    try:
        from .mmm_adopter import (
            classify_positions,
            validate_adoptable,
            build_adopted_session_state,
        )

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
                'error': f'Session must be in IDLE or STOPPED status to adopt. '
                         f'Current: {status}',
            }), 400

        data = request.get_json(force=True)

        positions = data.get('positions', [])
        if not positions:
            return jsonify({
                'success': False,
                'error': 'No positions provided. Select at least one CE and one PE position.',
            }), 400

        expiry = data.get('expiry', '')
        if not expiry:
            return jsonify({
                'success': False,
                'error': 'Expiry date is required.',
            }), 400

        expiry = normalize_expiry(expiry)
        trigger_mode = data.get('trigger_mode', 'current_prices')

        # Validate each position has required fields
        required_pos_fields = ['symbol', 'strike', 'lots', 'entry_price', 'side']
        for i, pos in enumerate(positions):
            missing = [f for f in required_pos_fields if f not in pos or pos[f] is None]
            if missing:
                return jsonify({
                    'success': False,
                    'error': f'Position {i+1} missing fields: {", ".join(missing)}',
                }), 400

        # Get spot price for classification
        spot_price = 0.0
        try:
            from .mmm_initializer import get_initializer
            initializer = get_initializer()
            spot_price = initializer.get_spot_price('BTC')
        except Exception:
            pass

        # Classify positions into active/frozen per side
        classified = classify_positions(positions, spot_price)

        # Validate
        max_lots = session.get('params', {}).get('max_lots_per_side', 100)
        validation = validate_adoptable(classified, session_id=session_id, max_lots_per_side=max_lots)

        if not validation['valid']:
            return jsonify({
                'success': False,
                'error': 'Validation failed: ' + '; '.join(validation['errors']),
                'errors': validation['errors'],
                'warnings': validation['warnings'],
            }), 400

        # Build session state
        build_adopted_session_state(
            session,
            classified,
            trigger_mode=trigger_mode,
            expiry=expiry,
        )

        # If trigger_mode is current_prices, fetch live premiums now
        if trigger_mode == 'current_prices':
            for side_key in ('ce', 'pe'):
                side_data = session.get(side_key, {})
                active_strike = side_data.get('active_strike')
                symbol = side_data.get('symbol', '')
                if symbol and active_strike:
                    try:
                        from bot.api.delta_client import DeltaClient
                        dc = DeltaClient()
                        ticker_resp = dc._req('GET', f'/v2/tickers/{symbol}')
                        if ticker_resp.get('success'):
                            live_mark = float(ticker_resp.get('result', {}).get('mark_price', 0))
                            if live_mark > 0:
                                side_data['trigger_snapshot'] = {
                                    str(int(active_strike)): live_mark,
                                }
                                side_data['current_price'] = live_mark
                                log.info(
                                    f"[Adopt] Set {side_key.upper()} trigger to current price: "
                                    f"strike={active_strike}, trigger={live_mark:.2f}"
                                )
                    except Exception as e:
                        log.warning(f"[Adopt] Could not fetch live price for {symbol}: {e}")

        # Store adoption snapshot
        session['adoption_snapshot']['spot_at_adoption'] = spot_price
        session['adoption_snapshot']['premiums_at_adoption'] = {
            'ce': session.get('ce', {}).get('trigger_snapshot', {}),
            'pe': session.get('pe', {}).get('trigger_snapshot', {}),
        }

        # Save
        storage.save_session(session)

        emit_status_change(session_id, 'IDLE', 'IDLE', 'Positions adopted from exchange')

        from .mmm_activity import log_activity
        ce = session.get('ce', {})
        pe = session.get('pe', {})
        log_activity('session_adopted',
            f"Adopted {len(positions)} positions: "
            f"CE {ce.get('active_strike')}×{ce.get('active_lots')} "
            f"({ce.get('frozen_total_lots', 0)} frozen), "
            f"PE {pe.get('active_strike')}×{pe.get('active_lots')} "
            f"({pe.get('frozen_total_lots', 0)} frozen), "
            f"trigger_mode={trigger_mode}",
            session_id=session_id, severity='success',
            details={
                'positions_adopted': len(positions),
                'trigger_mode': trigger_mode,
                'validation': validation,
            })

        log.info(
            f"MMM session {session_id} ADOPTED: "
            f"CE={ce.get('active_strike')}×{ce.get('active_lots')} + "
            f"{ce.get('frozen_total_lots', 0)} frozen, "
            f"PE={pe.get('active_strike')}×{pe.get('active_lots')} + "
            f"{pe.get('frozen_total_lots', 0)} frozen"
        )

        return jsonify({
            'success': True,
            'message': 'Positions adopted successfully',
            'session_id': session_id,
            'adopted': {
                'ce_active': {
                    'strike': ce.get('active_strike'),
                    'lots': ce.get('active_lots'),
                },
                'ce_frozen': [
                    {'strike': fp.get('strike'), 'lots': fp.get('lots')}
                    for fp in ce.get('frozen_positions', [])
                ],
                'pe_active': {
                    'strike': pe.get('active_strike'),
                    'lots': pe.get('active_lots'),
                },
                'pe_frozen': [
                    {'strike': fp.get('strike'), 'lots': fp.get('lots')}
                    for fp in pe.get('frozen_positions', [])
                ],
                'total_premium_collected': session.get('initial_total_premium', 0),
                'trigger_mode': trigger_mode,
            },
            'warnings': validation.get('warnings', []),
        })

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        log.exception(f"Failed to adopt positions for session {session_id}")
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

# =============================================================================
# Manual Position Reduction
# =============================================================================

@mmm_bp.route('/session/<session_id>/reduce-position', methods=['POST'])
def reduce_position(session_id: str):
    """
    Manually reduce open position size by buying back N lots.

    Works while the algo is RUNNING or PAUSED — the heartbeat continues
    uninterrupted. This is a risk-reducing action and does NOT count as
    an adjustment (adjustment_count unchanged, whipsaw guard unaffected).

    Body (JSON):
        side   : str   — 'ce', 'pe', or 'both'
        lots   : int   — number of lots to buy back per side
        strike : float — optional: specific strike to close (null = LIFO auto)

    After a successful fill the trigger snapshots are reset to current
    premiums so the next heartbeat doesn't misfire against a stale baseline.

    Returns:
        {
            success       : bool,
            results       : [{side, lots, strike, fill_price, realized_pnl}, ...],
            total_realized: float,
            errors        : [str],
        }
    """
    import asyncio
    from collections import defaultdict
    from .mmm_wind_down import get_lifo_close_fills, apply_lifo_removals
    from .mmm_trigger import update_trigger_snapshots
    from .mmm_executor import get_executor
    from .mmm_activity import log_activity
    from .mmm_initializer import get_initializer

    try:
        data = request.get_json(force=True) or {}
        side_param = data.get('side', '').lower()
        lots_param = int(data.get('lots', 0))
        strike_param = data.get('strike')  # None → LIFO

        if side_param not in ('ce', 'pe', 'both'):
            return jsonify({'success': False, 'error': "side must be 'ce', 'pe', or 'both'"}), 400
        if lots_param <= 0:
            return jsonify({'success': False, 'error': 'lots must be a positive integer'}), 400

        storage = get_storage()
        session = storage.get_session(session_id)
        if not session:
            return jsonify({'success': False, 'error': f'Session not found: {session_id}'}), 404

        status = session.get('strategy_status', 'IDLE')
        if status not in ('RUNNING', 'PAUSED', 'BOTH_SIDES_UP'):
            return jsonify({
                'success': False,
                'error': f'Session must be RUNNING or PAUSED. Current: {status}',
            }), 400

        sides_to_process = ['ce', 'pe'] if side_param == 'both' else [side_param]
        executor = get_executor()
        initializer = get_initializer()
        expiry = session.get('params', {}).get('expiry', '')

        results = []
        errors = []
        total_realized = 0.0

        async def _do_reduce():
            nonlocal total_realized
            for side_key in sides_to_process:
                side_state = session.get(side_key, {})
                active_lots = side_state.get('active_lots', 0)
                option_type = 'call' if side_key == 'ce' else 'put'

                if active_lots <= 0:
                    errors.append(f'{side_key.upper()}: no open lots to reduce')
                    continue

                max_lots = active_lots
                lots_to_close = min(lots_param, max_lots)

                if lots_to_close <= 0:
                    errors.append(f'{side_key.upper()}: requested {lots_param} > available {max_lots}')
                    continue

                # --- Build close records (LIFO or specific strike) ---
                if strike_param:
                    # User specified a strike: target that strike only
                    active_strike = side_state.get('active_strike', 0)
                    orig_strike = side_state.get('original_strike') or active_strike
                    target_strike = float(strike_param)

                    # Find matching fills at that strike
                    close_records = []
                    remaining = lots_to_close

                    adj_fills = list(side_state.get('adjustment_fills', []))
                    for i in range(len(adj_fills) - 1, -1, -1):
                        if remaining <= 0:
                            break
                        fill = adj_fills[i]
                        fill_strike = fill.get('strike') or active_strike
                        if abs(float(fill_strike) - target_strike) < 1:
                            take = min(remaining, fill.get('lots', 0))
                            if take > 0:
                                close_records.append({
                                    'lots': take,
                                    'premium': fill.get('premium', 0),
                                    'strike': fill_strike,
                                    'source': 'adjustment',
                                    'fill_index': i,
                                })
                                remaining -= take

                    if remaining > 0 and abs(orig_strike - target_strike) < 1:
                        orig_lots = side_state.get('original_lots', 0)
                        take = min(remaining, orig_lots)
                        if take > 0:
                            close_records.append({
                                'lots': take,
                                'premium': side_state.get('original_premium', 0),
                                'strike': orig_strike,
                                'source': 'original',
                                'fill_index': -1,
                            })
                            remaining -= take

                    if not close_records:
                        errors.append(
                            f'{side_key.upper()}: no fills found at strike {target_strike}'
                        )
                        continue
                else:
                    close_records = get_lifo_close_fills(side_state, lots_to_close)

                if not close_records:
                    errors.append(f'{side_key.upper()}: no LIFO records found')
                    continue

                # --- Group by actual strike, place one order per strike ---
                by_strike = defaultdict(lambda: {'lots': 0, 'records': [], 'wp_sum': 0.0})
                for rec in close_records:
                    rec_strike = rec.get('strike') or side_state.get('active_strike', 0)
                    by_strike[rec_strike]['lots'] += rec['lots']
                    by_strike[rec_strike]['records'].append(rec)
                    by_strike[rec_strike]['wp_sum'] += rec.get('premium', 0) * rec['lots']

                side_any_failed = False
                for strike_val, group in by_strike.items():
                    group_lots = group['lots']
                    symbol = initializer.build_symbol(
                        option_type, 'BTC', strike_val, expiry
                    )

                    log_activity(
                        'manual_reduce',
                        f'✂️ Manual Reduce: BUY {group_lots} {side_key.upper()} @ {strike_val} ({symbol})',
                        session_id, 'info',
                        {'side': side_key.upper(), 'strike': strike_val, 'lots': group_lots}
                    )

                    result = await executor.smart_execute(
                        symbol=symbol,
                        side='buy',
                        size=group_lots,
                        reduce_only=True,
                    )

                    if not result.get('success'):
                        err = result.get('error', 'execution failed')
                        errors.append(
                            f'{side_key.upper()} @ {strike_val}: {err}'
                        )
                        log_activity(
                            'manual_reduce',
                            f'✂️ Manual Reduce FAILED: {side_key.upper()} @ {strike_val} — {err}',
                            session_id, 'error',
                            {'side': side_key.upper(), 'strike': strike_val, 'error': err}
                        )
                        side_any_failed = True
                        continue

                    fill_price = result.get('fill_price', 0)
                    avg_entry = apply_lifo_removals(side_state, group['records'])
                    session[side_key] = side_state

                    group_realized = (avg_entry - fill_price) * group_lots * LOT_SIZE_BTC
                    total_realized += group_realized
                    session['realized_pnl'] = session.get('realized_pnl', 0) + group_realized
                    session['manual_reduction_pnl'] = (
                        session.get('manual_reduction_pnl', 0) + group_realized
                    )

                    reduction_record = {
                        'side': side_key.upper(),
                        'lots': group_lots,
                        'strike': strike_val,
                        'avg_entry_price': round(avg_entry, 4),
                        'fill_price': round(fill_price, 4),
                        'realized_pnl': round(group_realized, 2),
                        'timestamp': datetime.utcnow().isoformat(),
                    }
                    session.setdefault('manual_reductions', []).append(reduction_record)

                    results.append(reduction_record)

                    log_activity(
                        'manual_reduce',
                        f'✂️ Manual Reduce OK: Bought {group_lots} {side_key.upper()} '
                        f'@ {strike_val} fill ${fill_price:.2f} '
                        f'(entry ${avg_entry:.2f}, P&L ${group_realized:.2f})',
                        session_id, 'success',
                        reduction_record
                    )

        asyncio.run(_do_reduce())

        # --- Reset trigger snapshots with fresh live premiums ---
        # Fetch current premiums for both sides so the heartbeat doesn't
        # misfirer against a stale snapshot after position size changed.
        try:
            from .mmm_executor import get_executor as _ge
            from .mmm_initializer import get_initializer as _gi

            async def _fetch_premiums():
                _executor = _ge()
                _initializer = _gi()
                _expiry = session.get('params', {}).get('expiry', '')
                ce_state = session.get('ce', {})
                pe_state = session.get('pe', {})
                ce_strike = ce_state.get('active_strike', 0)
                pe_strike = pe_state.get('active_strike', 0)
                ce_sym = _initializer.build_symbol('call', 'BTC', ce_strike, _expiry)
                pe_sym = _initializer.build_symbol('put', 'BTC', pe_strike, _expiry)
                ce_mid = await _executor.get_mid_price(ce_sym)
                pe_mid = await _executor.get_mid_price(pe_sym)
                return ce_mid or 0.0, pe_mid or 0.0

            ce_now, pe_now = asyncio.run(_fetch_premiums())
            if ce_now > 0 and pe_now > 0:
                update_trigger_snapshots(session, ce_now, pe_now)
                log.info(
                    f'[{session_id}] Manual reduce: trigger snapshots reset '
                    f'CE={ce_now:.2f} PE={pe_now:.2f}'
                )
        except Exception as snap_err:
            log.warning(f'[{session_id}] Could not reset trigger snapshots after manual reduce: {snap_err}')

        session['updated_at'] = datetime.utcnow().isoformat()
        storage.save_session(session)

        # Emit WebSocket event so frontend updates immediately
        try:
            from .mmm_websocket import emit_to_session
            emit_to_session(session_id, 'mmm_manual_reduce', {
                'session_id': session_id,
                'results': results,
                'total_realized_pnl': round(total_realized, 2),
                'errors': errors,
            })
        except Exception:
            pass

        log.info(
            f'[{session_id}] Manual reduce complete: '
            f'{len(results)} fills, P&L ${total_realized:.2f}, '
            f'{len(errors)} errors'
        )

        return jsonify({
            'success': len(results) > 0,
            'results': results,
            'total_realized_pnl': round(total_realized, 2),
            'errors': errors,
        })

    except Exception as e:
        log.exception(f'Failed to reduce position for {session_id}')
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>/force-heartbeat', methods=['POST'])
def force_heartbeat(session_id: str):
    """Force an immediate heartbeat for a running session.

    Skips the inter-heartbeat wait timer so the next heartbeat runs
    within 500ms.  The heartbeat itself is identical to a normal one —
    same trigger evaluation, safety checks, and guards.  After the
    forced heartbeat, the monitor resumes its default interval schedule.
    """
    try:
        monitor = get_monitor(session_id)
        if not monitor:
            return jsonify({
                'success': False,
                'error': 'No active monitor for this session',
            }), 404

        if not monitor.is_running:
            return jsonify({
                'success': False,
                'error': 'Session is not running',
            }), 400

        accepted = monitor.force_heartbeat()
        return jsonify({
            'success': accepted,
            'message': '⚡ Force heartbeat triggered — next beat will run immediately',
        })
    except Exception as e:
        log.exception(f"Failed to force heartbeat for {session_id}")
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
def get_exchange_positions_direct():
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
                'max': params.get('max_adjustments', 100),
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
            'portfolio_delta': session.get('portfolio_delta', 0),
        }

        return jsonify({'success': True, 'safety': safety_data})

    except Exception as e:
        log.exception(f"Failed to get safety status for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =========================================================================
# Algo Walkthrough
# =========================================================================

@mmm_bp.route('/session/<session_id>/walkthrough', methods=['GET'])
def get_walkthrough(session_id: str):
    """Get the algo-calculation walkthrough log for a session."""
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        from .mmm_walkthrough import build_full_walkthrough
        walkthrough = build_full_walkthrough(session)

        return jsonify({
            'success': True,
            'walkthrough': walkthrough,
            'session_id': session_id,
        })

    except Exception as e:
        log.exception(f"Failed to get walkthrough for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =========================================================================
# Greeks, IV & Fees
# =========================================================================

@mmm_bp.route('/session/<session_id>/beat-health', methods=['GET'])
def get_beat_health(session_id: str):
    """
    Return heartbeat health telemetry for a session.

    Includes latency percentiles, miss rate, health grade (A-F),
    circuit breaker state, and watchdog status.
    """
    try:
        from .mmm_monitor import get_monitor
        monitor = get_monitor(session_id)

        if not monitor:
            # Session may be stopped — return stored snapshot from session
            storage = get_storage()
            session = storage.get_session(session_id)
            if not session:
                return jsonify({'success': False, 'error': 'Session not found'}), 404
            beat_health = session.get('_beat_health', {})
            circuit_state = session.get('_circuit_state', {})
            return jsonify({
                'success': True,
                'session_id': session_id,
                'monitor_active': False,
                'beat_health': beat_health,
                'circuit': circuit_state,
                'watchdog': {'running': False},
            })

        health_summary = monitor._health.summary() if hasattr(monitor, '_health') else {}
        circuit_summary = monitor._circuit.summary() if hasattr(monitor, '_circuit') else {}

        from .mmm_watchdog import MMMWatchdog
        watchdog_status = MMMWatchdog.get_instance().status()

        return jsonify({
            'success': True,
            'session_id': session_id,
            'monitor_active': True,
            'beat_health': health_summary,
            'circuit': circuit_summary,
            'watchdog': watchdog_status,
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>/regime', methods=['GET'])
def get_regime_status(session_id: str):
    """
    Return full regime controls status for a session.

    Includes all three control states (vol, gamma, trend), current aggregate
    action, metric details, and recent history arrays.
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)
        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        from .mmm_regime import MMMRegimeEngine
        engine = MMMRegimeEngine()
        regime_status = engine.get_regime_status(session)

        # Add history arrays (last 20 data points)
        regime_status['vol_iv_history'] = (session.get('_vol_iv_history', []) or [])[-20:]
        regime_status['vol_spot_history'] = (session.get('_vol_spot_history', []) or [])[-20:]
        regime_status['gamma_history'] = (session.get('_gamma_history', []) or [])[-20:]
        regime_status['vol_regime_since'] = session.get('_vol_regime_since')
        regime_status['gamma_regime_since'] = session.get('_gamma_regime_since')
        regime_status['trend_since'] = session.get('_trend_since')
        regime_status['gamma_blocked_count'] = session.get('_gamma_blocked_count', 0)

        # Observation mode: regime_enabled is OFF — data collected but not enforced
        params = session.get('params', {})
        if not params.get('regime_enabled', False):
            regime_status['observation_mode'] = True

        return jsonify({
            'success': True,
            'session_id': session_id,
            **regime_status,
        })

    except Exception as e:
        log.exception(f"Failed to get regime status for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>/greeks-iv', methods=['GET'])
def get_greeks_iv(session_id: str):
    """
    Fetch live Greeks, IV, and position data for all open positions in a session.

    For each unique (strike, option_type) in the session, fetches the
    Delta Exchange ticker to get Greeks (delta, gamma, theta, vega, rho),
    IV (mark_iv, bid_iv, ask_iv), mark_price, and spot price.

    Returns:
        {success, positions: [{side, strike, lots, greeks: {...}, iv: {...}, ...}]}
    """
    import asyncio
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        expiry = session.get('params', {}).get('expiry', '')
        if not expiry:
            return jsonify({'success': False, 'error': 'Session has no expiry'}), 400

        from .mmm_initializer import get_initializer
        initializer = get_initializer()

        # Collect all unique (strike, option_type, lots) from session
        position_map = {}  # key=(strike, opt_type) -> {lots, entries}
        for side_key in ['ce', 'pe']:
            side = session.get(side_key, {})
            if not side:
                continue
            opt = 'call' if side_key == 'ce' else 'put'
            side_label = side_key.upper()

            # Original lots at active strike
            active_strike = side.get('active_strike', 0)
            orig_lots = side.get('original_lots', 0)
            orig_prem = side.get('original_premium', 0)
            if active_strike and orig_lots > 0:
                key = (float(active_strike), opt)
                if key not in position_map:
                    position_map[key] = {'side': side_label, 'lots': 0, 'entries': []}
                position_map[key]['lots'] += orig_lots
                position_map[key]['entries'].append({
                    'type': 'original', 'lots': orig_lots, 'premium': orig_prem,
                })

            # Adjustment fills
            for fill in side.get('adjustment_fills', []):
                fill_strike = float(fill.get('strike', active_strike) or active_strike)
                fill_lots = fill.get('lots', 0)
                fill_prem = fill.get('premium', 0)
                if fill_strike and fill_lots > 0:
                    key = (fill_strike, opt)
                    if key not in position_map:
                        position_map[key] = {'side': side_label, 'lots': 0, 'entries': []}
                    position_map[key]['lots'] += fill_lots
                    position_map[key]['entries'].append({
                        'type': 'adjustment', 'lots': fill_lots, 'premium': fill_prem,
                    })

            # Frozen positions
            for frozen in side.get('frozen_positions', []):
                f_strike = float(frozen.get('strike', 0))
                f_lots = frozen.get('lots', 0)
                f_prem = frozen.get('entry_premium', 0)
                if f_strike and f_lots > 0:
                    key = (f_strike, opt)
                    if key not in position_map:
                        position_map[key] = {'side': side_label, 'lots': 0, 'entries': [],
                                             'frozen': True}
                    position_map[key]['lots'] += f_lots
                    position_map[key]['entries'].append({
                        'type': 'frozen', 'lots': f_lots, 'premium': f_prem,
                    })

        if not position_map:
            return jsonify({'success': True, 'positions': [], 'spot_price': 0})

        # Build symbols and fetch tickers in parallel
        from config.loader import get_api_credentials
        from bot.api.async_delta_client import AsyncDeltaClient

        creds = get_api_credentials()
        client = AsyncDeltaClient(
            api_key=creds.get('api_key', ''),
            api_secret=creds.get('api_secret', ''),
            testnet=creds.get('testnet', False) or False,
        )

        async def fetch_all():
            tasks = []
            keys = []
            for (strike, opt) in position_map:
                symbol = initializer.build_symbol(opt, 'BTC', strike, expiry)
                keys.append((strike, opt))
                tasks.append(
                    client._request_with_retry(
                        method="GET", path=f"/v2/tickers/{symbol}",
                    )
                )
            results = await asyncio.gather(*tasks, return_exceptions=True)
            return list(zip(keys, results))

        ticker_results = asyncio.run(fetch_all())

        # Also fetch spot price
        try:
            spot_price = initializer.get_spot_price()
        except Exception:
            spot_price = 0

        # Build response
        positions = []
        for (strike, opt), resp in ticker_results:
            info = position_map[(strike, opt)]
            side_label = info['side']
            total_lots = info['lots']
            entries = info['entries']
            is_frozen = info.get('frozen', False)

            # Weighted average entry premium
            total_lot_prem = sum(e['lots'] * e['premium'] for e in entries)
            avg_entry = total_lot_prem / total_lots if total_lots else 0

            # Parse ticker data
            greeks = {}
            iv = {}
            mark_price = 0
            if isinstance(resp, Exception):
                log.warning(f"Failed to fetch ticker for {opt}@{strike}: {resp}")
            else:
                data = resp.get('result', resp)
                mark_price = float(data.get('mark_price', 0))
                # Greeks — ticker returns per-1-BTC option Greeks.
                # 1 lot = LOT_SIZE_BTC (0.001 BTC), so multiply by
                # LOT_SIZE_BTC to get per-lot Greeks.
                # MMM only holds SHORT positions, so negate to get
                # position Greeks (matching Delta Exchange position display).
                # Result: per-lot position Greek = ticker_greek × LOT_SIZE_BTC × (-1)
                from .mmm_constants import LOT_SIZE_BTC
                g = data.get('greeks', {})
                greeks = {}
                for gk in ('delta', 'gamma', 'theta', 'vega', 'rho'):
                    raw = _safe_float(g.get(gk))
                    if raw is not None:
                        greeks[gk] = -raw * LOT_SIZE_BTC
                    else:
                        greeks[gk] = None
                # IV — stored as decimals (0.60 = 60%)
                iv = {
                    'mark_iv': _safe_float(data.get('mark_iv', data.get('quotes', {}).get('mark_iv'))),
                    'bid_iv': _safe_float(data.get('bid_iv', data.get('quotes', {}).get('bid_iv'))),
                    'ask_iv': _safe_float(data.get('ask_iv', data.get('quotes', {}).get('ask_iv'))),
                }

            # P&L calc: (entry - current) * lots * LOT_SIZE_BTC
            from .mmm_constants import LOT_SIZE_BTC  # noqa: F811
            pnl = (avg_entry - mark_price) * total_lots * LOT_SIZE_BTC if mark_price else None

            positions.append({
                'side': side_label,
                'strike': strike,
                'option_type': opt,
                'lots': total_lots,
                'avg_entry': round(avg_entry, 2),
                'mark_price': round(mark_price, 2),
                'pnl': round(pnl, 6) if pnl is not None else None,
                'greeks': greeks,
                'iv': iv,
                'frozen': is_frozen,
                'entries': entries,
            })

        # Sort: active before frozen, CE before PE, then by strike
        positions.sort(key=lambda p: (p.get('frozen', False), p['side'], p['strike']))

        return jsonify({
            'success': True,
            'positions': positions,
            'spot_price': spot_price,
            'timestamp': datetime.utcnow().isoformat(),
        })

    except Exception as e:
        log.exception(f"Failed to get Greeks/IV for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


def _safe_float(val):
    """Convert value to float, returning None on failure."""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None

# =========================================================================
# Session Analytics
# =========================================================================

@mmm_bp.route('/session/<session_id>/analytics', methods=['GET'])
def get_session_analytics(session_id: str):
    """
    Get institutional-level session analytics for exposure tracking.
    
    Checks persistent analytics storage first (survives session deletion),
    then falls back to live session data.
    
    Returns comprehensive metrics:
    - Session duration and timing
    - Initial vs current vs peak exposure
    - Cumulative trading volume
    - Auto-close and manual close statistics
    - Adjustment breakdown by side and type
    - Risk event timeline (reversals, shifts, both_sides_up)
    - P&L milestones
    - Greeks tracking
    """
    try:
        from .mmm_analytics_storage import get_analytics_storage
        
        # Try persistent storage first (includes deleted/expired sessions)
        analytics_storage = get_analytics_storage()
        stored_analytics = analytics_storage.get_session_analytics(session_id)
        
        if stored_analytics:
            # Return stored analytics directly
            return jsonify({
                'success': True,
                'analytics': stored_analytics,
                'session_id': session_id,
                'source': 'persistent_storage'
            })
        
        # Fallback to live session (for new sessions not yet persisted)
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        analytics = session.get('analytics', {})
        
        # Compute current duration if still running
        if session.get('strategy_status') == 'RUNNING':
            start_time = analytics.get('session_start_time')
            if start_time:
                try:
                    start_dt = datetime.fromisoformat(start_time)
                    current_duration = (datetime.utcnow() - start_dt).total_seconds()
                except (ValueError, TypeError):
                    current_duration = analytics.get('session_duration_seconds', 0)
            else:
                current_duration = 0
        else:
            current_duration = analytics.get('session_duration_seconds', 0)

        # Build response with computed fields
        response_analytics = {
            **analytics,
            'current_duration_seconds': current_duration,
            'session_status': session.get('strategy_status', 'UNKNOWN'),
            'expiry': session.get('params', {}).get('expiry', ''),
            
            # Current live exposure
            'current_ce_lots': session.get('ce', {}).get('total_lots', 0),
            'current_pe_lots': session.get('pe', {}).get('total_lots', 0),
            'current_combined_lots': (
                session.get('ce', {}).get('total_lots', 0) +
                session.get('pe', {}).get('total_lots', 0)
            ),
            
            # Final P&L
            'final_realized_pnl': session.get('realized_pnl', 0),
            'final_total_pnl': (
                session.get('realized_pnl', 0) +
                session.get('unrealized_pnl', 0)
            ),
            
            # Counters
            'total_adjustments': session.get('adjustment_count', 0),
            'total_reversals': session.get('reversal_count', 0),
            'total_shifts': session.get('shift_count', 0),
            'total_close_at_5': session.get('close_at_5_count', 0),
        }

        return jsonify({
            'success': True,
            'analytics': response_analytics,
            'session_id': session_id,
            'source': 'live_session'
        })

    except Exception as e:
        log.exception(f"Failed to get analytics for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/analytics/history', methods=['GET'])
def get_analytics_history():
    """
    Get historical analytics for all sessions (includes deleted/expired).
    
    Query parameters:
    - limit: Max records to return (default: 50, max: 200)
    - status: Filter by session status (RUNNING, STOPPED, etc.)
    - expiry: Filter by expiry date (e.g., 19022026)
    
    Returns persistent analytics records that survive session deletion.
    """
    try:
        from .mmm_analytics_storage import get_analytics_storage
        
        # Get query parameters
        limit = request.args.get('limit', 50, type=int)
        limit = min(limit, 200)  # Cap at 200
        
        status_filter = request.args.get('status', None)
        expiry_filter = request.args.get('expiry', None)
        
        # Fetch from persistent storage
        analytics_storage = get_analytics_storage()
        history = analytics_storage.get_all_analytics(
            limit=limit,
            status_filter=status_filter,
            expiry_filter=expiry_filter
        )
        
        return jsonify({
            'success': True,
            'analytics': history,
            'count': len(history),
            'filters': {
                'limit': limit,
                'status': status_filter,
                'expiry': expiry_filter
            }
        })
    
    except Exception as e:
        log.exception("Failed to get analytics history")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/analytics/aggregated', methods=['GET'])
def get_aggregated_analytics():
    """
    Get INSTITUTIONAL-GRADE aggregated analytics across ALL historical sessions.
    
    Provides actionable business intelligence to answer:
    1. Capital Requirements: How much capital needed to scale?
    2. Risk Analytics: What's the probability of auto-close/max-loss?
    3. Profitability: Is this strategy actually profitable?
    4. Strategy Performance: How aggressive is the algo?
    
    Returns comprehensive metrics:
    - Overview: Total sessions, win rate, total P&L
    - Capital Requirements: Max lots ever, scaling guidance
    - Risk Analytics: Auto-close probability, drawdown analysis
    - Profitability: Best/worst/average P&L, profit factor
    - Strategy Performance: Adjustment frequency, trading volume
    - Recent Sessions: Last 10 sessions summary
    
    Use this to make data-driven decisions about scaling and risk management.
    """
    try:
        from .mmm_analytics_aggregator import get_aggregator
        
        aggregator = get_aggregator()
        aggregated = aggregator.get_aggregated_analytics()
        
        return jsonify({
            'success': True,
            'aggregated': aggregated,
        })
    
    except Exception as e:
        log.exception("Failed to get aggregated analytics")
        return jsonify({'success': False, 'error': str(e)}), 500