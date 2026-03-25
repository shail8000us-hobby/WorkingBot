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
import asyncio
import threading
import json
from flask import Blueprint, request, jsonify, make_response
from datetime import datetime, timezone

# Import cache for performance optimization
try:
    from webui.backend.cache import cache, CACHE_TIMEOUTS
except ImportError:
    from cache import cache, CACHE_TIMEOUTS


def _run_async(coro):
    """Run async coroutine in the current thread's asyncio event loop.

    Flask routes run in real OS threads (threading async mode), so we can
    create a fresh event loop and run the coroutine directly.
    """
    loop = asyncio.DefaultEventLoopPolicy().new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(None)

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
from .mmm_constants import LOT_SIZE_BTC, strike_key
from .mmm_monitor import (
    start_session_monitor, stop_session_monitor,
    pause_session_monitor, resume_session_monitor,
    get_monitor, get_all_monitors, compute_live_pnl,
)

log = logging.getLogger('mmm_api')

# =============================================================================
# Blueprint
# =============================================================================

mmm_bp = Blueprint('mmm', __name__, url_prefix='/api/mmm')


def _overlay_live_pnl(sessions_list):
    """Replace stored P&L with live-computed values for running sessions.

    The stored unrealized_pnl is a CACHE that can be stale between heartbeats.
    For running sessions, compute_live_pnl() returns authoritative values
    computed from the monitor's in-memory state + cached prices.
    For stopped sessions, stored values are the final state — no overlay needed.

    This function is the architectural fix that makes PnL correct at every
    REST read, regardless of when the last heartbeat ran or what mid-heartbeat
    events (close, shift, reduce) updated realized_pnl without refreshing
    unrealized_pnl.
    """
    monitors = get_all_monitors()
    if not monitors:
        return
    for s in sessions_list:
        sid = s.get('session_id', '')
        if sid not in monitors:
            continue
        live = compute_live_pnl(sid)
        if live is None:
            continue
        s['realized_pnl'] = round(live['realized'], 6)
        s['unrealized_pnl'] = round(live['unrealized'], 6)
        s['total_fees'] = round(live['fees'], 6)
        s['net_pnl'] = round(live['net_pnl'], 6)
        # Keep peak_pnl consistent: if live net_pnl exceeds stored peak, update it
        if live['net_pnl'] > s.get('peak_pnl', 0):
            s['peak_pnl'] = round(live['net_pnl'], 6)


def _invalidate_sessions_cache():
    """No-op: list_sessions is no longer cached (real-time via WebSocket)."""
    pass


def _check_guardian_signal() -> str:
    """Check if trading is allowed via global guardian."""
    try:
        from webui.backend.trading_control import get_signal
        return get_signal()
    except Exception:
        return 'GO'


# =============================================================================
# DTE Presets
# =============================================================================

@mmm_bp.route('/dte-presets', methods=['GET'])
def get_dte_presets():
    """
    List available DTE presets.

    Returns:
        {success: true, presets: [...]}
    """
    try:
        from .mmm_dte_presets import list_presets, DTE_PRESETS, SHORT_STRADDLE_CATEGORY, build_short_straddle_preset
        # Include dynamic preset with example values (5h) for UI display
        preset_details = {k: v for k, v in DTE_PRESETS.items()}
        try:
            preset_details[SHORT_STRADDLE_CATEGORY] = build_short_straddle_preset(5.0)
        except ValueError:
            pass  # Should never fail at 5h, but be safe
        return jsonify({
            'success': True,
            'presets': list_presets(),
            'preset_details': preset_details,
        })
    except Exception as e:
        log.exception("Failed to get DTE presets")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/aggregate-pnl', methods=['GET'])
def get_aggregate_pnl():
    """
    Get aggregate PnL across all active sessions.

    Returns:
        {success: true, aggregate: {...}}
    """
    try:
        from .mmm_dte_presets import check_aggregate_pnl
        storage = get_storage()
        all_sessions = storage.list_sessions(active_only=True)
        # Filter to truly active sessions (RUNNING, PAUSED, BOTH_SIDES_UP)
        active = [s for s in all_sessions
                  if s.get('strategy_status') in ('RUNNING', 'PAUSED', 'BOTH_SIDES_UP',
                                                  'STARTING', 'PARTIAL_ENTRY')]
        # ARCHITECTURAL FIX: live P&L overlay — aggregate safety check
        # must use live values, not stale stored fields
        _overlay_live_pnl(active)
        result = check_aggregate_pnl(active)
        return jsonify({'success': True, 'aggregate': result})
    except Exception as e:
        log.exception("Failed to get aggregate PnL")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Session CRUD
# =============================================================================

@mmm_bp.route('/sessions', methods=['GET'])
def list_sessions():
    """
    List all MMM sessions.

    Query params:
        active_only: bool - If true, only return active sessions
        summary: bool - If true, return compact summaries (uses optimized SQL query)

    Returns:
        {success: true, sessions: [...], count: int}
    """
    try:
        active_only = request.args.get('active_only', 'false').lower() == 'true'
        summary_mode = request.args.get('summary', 'false').lower() == 'true'

        storage = get_storage()

        if summary_mode:
            # Optimized path: uses SQLite json_extract() to avoid
            # deserializing 8+ MB of full session JSON blobs.
            # ~10ms vs ~10s for 28 sessions.
            sessions = storage.list_session_summaries(active_only=active_only)
        else:
            sessions = storage.list_sessions(active_only=active_only)

        # ARCHITECTURAL FIX: For running sessions, replace stored P&L (which
        # can be stale between heartbeats) with live-computed values from the
        # monitor's cached prices. This eliminates the stale-unrealized bug
        # class entirely — no more race windows between close events and
        # heartbeat step 8.
        _overlay_live_pnl(sessions)

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

        # ARCHITECTURAL FIX: live P&L overlay for running sessions
        _overlay_live_pnl([data])

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

        # M-7 fix: Validate expiry format at CREATE time (before session exists in storage)
        expiry_str = validated.get('expiry', '')
        if expiry_str:
            try:
                d, m, y = int(expiry_str[0:2]), int(expiry_str[2:4]), int(expiry_str[4:8])
                from datetime import datetime as _dt
                _dt(y, m, d)  # Validate it's a real date
            except (ValueError, IndexError):
                return jsonify({
                    'success': False,
                    'error': f"Invalid expiry format: '{expiry_str}'. Expected DDMMYYYY.",
                }), 400

        # Liquidity gate: check chain has enough liquid strikes (fresh mode only)
        if mode == 'fresh' and expiry_str:
            try:
                from .mmm_initializer import MMMInitializer
                from .mmm_dte_presets import check_chain_liquidity
                initializer = MMMInitializer()
                chain_result = initializer.get_full_chain(expiry_str)
                if chain_result.get('success') and chain_result.get('chain'):
                    liq = check_chain_liquidity(chain_result['chain'])
                    if not liq['liquid']:
                        return jsonify({
                            'success': False,
                            'error': liq['message'],
                        }), 400
            except Exception as e:
                log.warning(f"Liquidity gate check failed (non-blocking): {e}")

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

            session['entry_time'] = datetime.now(timezone.utc).isoformat()

            # ── TRADE AUDIT: Mode B import — 2 rows (CE + PE) ─────────────
            try:
                from .mmm_audit_log import get_audit_log as _get_aud
                from .mmm_audit_remark import build_trade_remark as _btr
                _sid = session.get('session_id', '')
                for _sk, _sd in [('CE', ce_data), ('PE', pe_data)]:
                    _sp = float(_sd.get('premium', 0))
                    _sl = int(_sd.get('lots', 0))
                    _ss = float(_sd.get('strike', 0))
                    _get_aud().enqueue_trade(
                        session_id=_sid,
                        action='SELL',
                        option_type=_sk,
                        strike=_ss,
                        quantity_requested=_sl,
                        quantity_filled=_sl,
                        premium=_sp,
                        event_type='ENTRY',
                        mechanism='import',
                        realized_pnl_usd=None,
                        remark=_btr(action='SELL', event_type='ENTRY',
                                    side=_sk.lower(), strike=int(_ss),
                                    lots=_sl, premium=_sp,
                                    mechanism='import'),
                    )
            except Exception:
                pass

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
        _invalidate_sessions_cache()

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
            # Idempotent delete: if already gone, return success.
            # Returning 404 here would trip the frontend circuit breaker and
            # break all subsequent API calls (orders, positions, sessions).
            log.info(f"DELETE {session_id}: already absent, returning success (idempotent)")
            return jsonify({
                'success': True,
                'message': f'Session {session_id} not found (already deleted)',
            })

        status = session.get('strategy_status', 'IDLE')
        if status not in ('IDLE', 'STOPPED'):
            return jsonify({
                'success': False,
                'error': f"Cannot delete session in {status} state. Stop it first.",
            }), 400

        storage.delete_session(session_id)
        _invalidate_sessions_cache()
        
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
        # H-6 fix: allow starting from PAUSED state (not just IDLE)
        if status not in ('IDLE', 'PAUSED'):
            return jsonify({
                'success': False,
                'error': f"Cannot start session in {status} state. Must be IDLE or PAUSED.",
            }), 400

        # IMP-8: Pre-entry regime checks — warnings only, do not block start
        pre_entry_warnings = _check_pre_entry_conditions(session)

        # Phase 0: Aggregate PnL safety check across all active sessions
        try:
            from .mmm_dte_presets import check_aggregate_pnl
            all_sessions = storage.list_sessions(active_only=True)
            active = [s for s in all_sessions
                      if s.get('strategy_status') in ('RUNNING', 'PAUSED', 'BOTH_SIDES_UP',
                                                      'STARTING', 'PARTIAL_ENTRY')
                      and s.get('session_id') != session_id]
            _overlay_live_pnl(active)
            global_max = session.get('params', {}).get('global_max_loss', 50000.0)
            agg_check = check_aggregate_pnl(active, global_max)
            if not agg_check['safe']:
                return jsonify({
                    'success': False,
                    'error': agg_check['message'],
                    'aggregate_pnl': agg_check,
                }), 400
        except Exception as e:
            log.warning(f"Aggregate PnL check failed (non-blocking): {e}")

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
                'pre_entry_warnings': pre_entry_warnings,
            })

        # =====================================================================
        # Import mode or already-executed: go directly to RUNNING
        # =====================================================================
        old_status = status
        new_status = 'RUNNING'

        storage.update_session(session_id, {
            'strategy_status': new_status,
            'entry_time': session.get('entry_time') or datetime.now(timezone.utc).isoformat(),
            'last_heartbeat': datetime.now(timezone.utc).isoformat(),
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
            'pre_entry_warnings': pre_entry_warnings,
        })

    except Exception as e:
        log.exception(f"Failed to start MMM session {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


def _check_pre_entry_conditions(session: dict) -> list:
    """
    IMP-8: Run pre-entry regime checks before starting a session.
    Returns a list of warning strings. Never blocks the start — warnings only.
    """
    from datetime import datetime, timezone, timedelta
    warnings = []
    params = session.get('params', {})

    # Check 1: Momentum — BTC moved > 0.5% in last 10 min
    # We approximate using the session's current spot vs the last known price.
    # If no recent price info available, skip this check.
    price_history = session.get('analytics', {}).get('spot_price_history', [])
    if len(price_history) >= 2:
        recent = price_history[-1]
        old_ts = recent.get('ts', '')
        old_price = recent.get('price', 0)
        current_price = session.get('analytics', {}).get('last_spot_price', 0)
        if old_price > 0 and current_price > 0:
            move_pct = abs(current_price - old_price) / old_price * 100
            if move_pct > 0.5:
                warnings.append(
                    f"Momentum: BTC moved {move_pct:.1f}% recently. "
                    f"Market has momentum — consider waiting for calmer conditions."
                )

    # Check 2: Strike width — CE and PE not equidistant from spot
    spot_price = session.get('analytics', {}).get('last_spot_price', 0)
    ce_strike = session.get('ce', {}).get('active_strike', 0) or session.get('ce', {}).get('original_strike', 0)
    pe_strike = session.get('pe', {}).get('active_strike', 0) or session.get('pe', {}).get('original_strike', 0)
    if spot_price > 0 and ce_strike > 0 and pe_strike > 0:
        ce_otm_pct = (ce_strike - spot_price) / spot_price * 100
        pe_otm_pct = (spot_price - pe_strike) / spot_price * 100
        asymmetry = abs(ce_otm_pct - pe_otm_pct)
        if asymmetry > 0.5:
            warnings.append(
                f"Strike width: CE is {ce_otm_pct:.1f}% OTM but PE is {pe_otm_pct:.1f}% OTM. "
                f"Consider symmetric strikes for delta neutrality."
            )

    # Check 3: Session time — entry within 30 min of market open (09:30 IST)
    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc + timedelta(hours=5, minutes=30)
    market_open_ist = now_ist.replace(hour=9, minute=30, second=0, microsecond=0)
    mins_since_open = (now_ist - market_open_ist).total_seconds() / 60
    if 0 <= mins_since_open < 30:
        warnings.append(
            f"Early entry: {mins_since_open:.0f} minutes since market open (09:30 IST). "
            f"Price discovery may cause early adjustments."
        )

    # Check 4: Remaining expiry — entry < 2 hours to expiry
    expiry_str = params.get('expiry', '')
    if expiry_str:
        try:
            from .mmm_initializer import expiry_to_utc_datetime
            expiry_dt_str = expiry_to_utc_datetime(expiry_str, params)
            expiry_dt = datetime.fromisoformat(expiry_dt_str.replace('Z', '+00:00'))
            if expiry_dt.tzinfo is None:
                expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
            mins_to_expiry = (expiry_dt - now_utc).total_seconds() / 60
            if 0 < mins_to_expiry < 120:
                warnings.append(
                    f"Low time to expiry: {mins_to_expiry:.0f} minutes remain. "
                    f"Wind-down will activate almost immediately."
                )
        except Exception:
            pass

    return warnings


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
        entry_result = _run_async(
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
        rollback_ok = entry_result.get('rollback_ok', False)

        # Check for partial fill (one leg filled, other failed)
        ce_ok = ce_res.get('success', False) if isinstance(ce_res, dict) else False
        pe_ok = pe_res.get('success', False) if isinstance(pe_res, dict) else False

        if (ce_ok or pe_ok) and rollback_ok:
            # Rollback succeeded — positions are FLAT. No manual intervention needed.
            # The successful leg was bought back. Return to IDLE cleanly.
            filled_side = 'CE' if ce_ok else 'PE'
            failed_side = 'PE' if ce_ok else 'CE'
            session = storage.get_session(session_id)
            session['strategy_status'] = 'IDLE'
            session.pop('partial_entry', None)
            # Clear any fill data set during the failed attempt
            session['ce']['entry_fill_price'] = None
            session['ce']['entry_order_id'] = None
            session['pe']['entry_fill_price'] = None
            session['pe']['entry_order_id'] = None
            session['initial_total_premium'] = 0
            session['actual_total_premium'] = 0
            session['total_premium_collected'] = 0
            storage.save_session(session)

            log_activity('entry_rolled_back',
                f"Entry failed ({failed_side} did not fill) but {filled_side} was successfully "
                f"rolled back. Positions are flat. Session reset to IDLE — re-execute when ready.",
                session_id=session_id, severity='warning',
                details={'ce_filled': ce_ok, 'pe_filled': pe_ok, 'rollback_ok': True})
            emit_status_change(session_id, 'STARTING', 'IDLE',
                f'Entry rolled back cleanly: {filled_side} bought back. Ready to retry.')
            # Clear stale "placing order..." progress messages
            from .mmm_activity import resolve_progress_activities
            resolve_progress_activities(session_id)

        elif ce_ok or pe_ok:
            # Rollback FAILED — one leg is still open (orphan position). Need manual fix.
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
                'rollback_failed': True,
                'ce_result': str(ce_res)[:300],
                'pe_result': str(pe_res)[:300],
                'timestamp': datetime.now(timezone.utc).isoformat(),
            }
            storage.save_session(session)

            filled_side = 'CE' if ce_ok else 'PE'
            failed_side = 'PE' if ce_ok else 'CE'
            log_activity('partial_entry',
                f"PARTIAL ENTRY: {filled_side} filled, {failed_side} failed, "
                f"AND rollback also failed — ORPHAN POSITION open! "
                f"Use 'Retry Leg' or manually close {filled_side} on exchange.",
                session_id=session_id, severity='error',
                details={'ce_filled': ce_ok, 'pe_filled': pe_ok, 'rollback_ok': False})
            emit_status_change(session_id, 'STARTING', 'PARTIAL_ENTRY',
                f'Orphan position: {filled_side} open, rollback failed')

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
    ce_strike_key = strike_key(session['ce'].get('active_strike', 0))
    pe_strike_key = strike_key(session['pe'].get('active_strike', 0))
    session['ce']['trigger_snapshot'] = {ce_strike_key: ce_fill}
    session['pe']['trigger_snapshot'] = {pe_strike_key: pe_fill}

    # Record exchange commissions via ledger (CRIT-1 fix)
    _ce_od = ce_res.get('order_details') or {}
    _pe_od = pe_res.get('order_details') or {}
    _ce_comm = float(_ce_od.get('paid_commission', 0) or _ce_od.get('commission', 0) or 0)
    _pe_comm = float(_pe_od.get('paid_commission', 0) or _pe_od.get('commission', 0) or 0)
    from .mmm_pnl_core import record_fee as _pnl_fee
    if _ce_comm:
        _pnl_fee(session, _ce_comm, 'sell_initial',
                 order_id=str(ce_res.get('order_id', '')), side='ce')
    if _pe_comm:
        _pnl_fee(session, _pe_comm, 'sell_initial',
                 order_id=str(pe_res.get('order_id', '')), side='pe')

    actual_premium = (ce_fill + pe_fill) * lots * LOT_SIZE_BTC
    session['actual_total_premium'] = actual_premium
    session['total_premium_collected'] = actual_premium
    session['ce_premium_collected'] = ce_fill * lots * LOT_SIZE_BTC
    session['pe_premium_collected'] = pe_fill * lots * LOT_SIZE_BTC
    session['execution_timestamp'] = datetime.now(timezone.utc).isoformat()

    # Transition to RUNNING
    session['strategy_status'] = 'RUNNING'
    session['entry_time'] = datetime.now(timezone.utc).isoformat()
    session['last_heartbeat'] = datetime.now(timezone.utc).isoformat()
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

    # ── TRADE AUDIT: initial entry (Mode A — both legs filled) ───────────
    try:
        from .mmm_audit_log import get_audit_log as _get_aud
        from .mmm_audit_remark import build_trade_remark as _btr
        _aud = _get_aud()
        for _side, _fill, _res in [('ce', ce_fill, ce_res), ('pe', pe_fill, pe_res)]:
            _filled = _res.get('filled_size', lots)
            if not _filled or _filled <= 0:
                _filled = lots
            _strike = int(session[_side].get('active_strike', 0) or 0)
            _aud.enqueue_trade(
                session_id=session_id,
                action='SELL',
                option_type=_side.upper(),
                strike=_strike,
                quantity_requested=lots,
                quantity_filled=_filled,
                premium=_fill,
                event_type='ENTRY',
                mechanism='fresh_entry',
                order_id=str(_res.get('order_id', '')),
                expiry=session.get('params', {}).get('expiry', ''),
                spot_price_usd=float(session.get('_regime_spot_price', 0) or 0),
                remark=_btr(
                    'SELL', 'ENTRY',
                    side=_side, strike=_strike,
                    lots=_filled, premium=_fill,
                    mechanism='fresh_entry',
                    is_partial=(_filled < lots),
                ),
            )
    except Exception:
        pass
    # ── END TRADE AUDIT ──────────────────────────────────────────────────

    # Clear stale "placing order..." progress messages now that entry is complete
    from .mmm_activity import resolve_progress_activities
    resolve_progress_activities(session_id)

    log_activity('session_started',
        f"Session {session_id} is now RUNNING — heartbeat monitor active",
        session_id=session_id, severity='success')

    # ── SESSION EVENT: lifecycle started ─────────────────────────────────
    try:
        from .mmm_audit_log import get_event_log as _get_evl
        from .mmm_audit_remark import build_event_remark as _ber
        _get_evl().enqueue_event(
            session_id=session_id,
            event_category='SESSION_LIFECYCLE',
            event_type='started',
            severity='INFO',
            remark=_ber('SESSION_LIFECYCLE', 'started'),
            details={
                'ce_strike': session.get('ce', {}).get('active_strike'),
                'pe_strike': session.get('pe', {}).get('active_strike'),
                'ce_fill': ce_fill, 'pe_fill': pe_fill,
                'lots': lots,
                'expiry': session.get('params', {}).get('expiry'),
            },
        )
    except Exception:
        pass
    # ── END SESSION EVENT ─────────────────────────────────────────────────

    # Start the heartbeat monitor
    start_session_monitor(session_id, session)


@mmm_bp.route('/session/<session_id>/resolve-partial-entry', methods=['POST'])
def resolve_partial_entry(session_id: str):
    """
    Resolve a PARTIAL_ENTRY state by manually confirming both fill prices.

    Use this when one leg failed during entry but you manually filled it on the
    exchange. Provide the fill prices for both CE and PE sides, and the algo
    will transition to RUNNING and start the heartbeat monitor.

    Body (JSON):
        {
            ce_fill_price: float,   # Actual fill price for CE leg
            pe_fill_price: float,   # Actual fill price for PE leg
        }

    Returns:
        { success: bool, status: 'RUNNING' }
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
        if status != 'PARTIAL_ENTRY':
            return jsonify({
                'success': False,
                'error': f"Session must be in PARTIAL_ENTRY state. Current: {status}",
            }), 400

        data = request.get_json() or {}
        ce_fill_price = data.get('ce_fill_price')
        pe_fill_price = data.get('pe_fill_price')

        if ce_fill_price is None or pe_fill_price is None:
            return jsonify({
                'success': False,
                'error': 'Both ce_fill_price and pe_fill_price are required.',
            }), 400

        try:
            ce_fill = float(ce_fill_price)
            pe_fill = float(pe_fill_price)
        except (ValueError, TypeError):
            return jsonify({
                'success': False,
                'error': 'ce_fill_price and pe_fill_price must be valid numbers.',
            }), 400

        if ce_fill <= 0 or pe_fill <= 0:
            return jsonify({
                'success': False,
                'error': 'Fill prices must be greater than zero.',
            }), 400

        from .mmm_activity import log_activity

        # Update fill prices for both sides
        session['ce']['entry_fill_price'] = ce_fill
        session['ce']['original_premium'] = ce_fill
        session['pe']['entry_fill_price'] = pe_fill
        session['pe']['original_premium'] = pe_fill

        # Update trigger snapshots to actual fill prices
        ce_strike_key = strike_key(session['ce'].get('active_strike', 0))
        pe_strike_key = strike_key(session['pe'].get('active_strike', 0))
        session['ce']['trigger_snapshot'] = {ce_strike_key: ce_fill}
        session['pe']['trigger_snapshot'] = {pe_strike_key: pe_fill}

        lots = session.get('lots', 0) or session['ce'].get('original_lots', 0)
        actual_premium = (ce_fill + pe_fill) * lots * LOT_SIZE_BTC
        session['actual_total_premium'] = actual_premium
        session['total_premium_collected'] = actual_premium
        session['ce_premium_collected'] = ce_fill * lots * LOT_SIZE_BTC
        session['pe_premium_collected'] = pe_fill * lots * LOT_SIZE_BTC

        # Clear partial entry state
        session.pop('partial_entry', None)

        # Transition to RUNNING
        session['strategy_status'] = 'RUNNING'
        session['entry_time'] = datetime.now(timezone.utc).isoformat()
        session['last_heartbeat'] = datetime.now(timezone.utc).isoformat()
        session['execution_timestamp'] = datetime.now(timezone.utc).isoformat()

        storage.save_session(session)

        emit_status_change(session_id, 'PARTIAL_ENTRY', 'RUNNING',
                           'Partial entry resolved — both fills confirmed')

        log_activity('entry_complete',
            f"Partial entry resolved: CE@${ce_fill:.2f} + PE@${pe_fill:.2f}. "
            f"Session transitioning to RUNNING.",
            session_id=session_id, severity='success',
            details={'ce_fill': ce_fill, 'pe_fill': pe_fill,
                     'total_premium': actual_premium})

        log.info(
            f"MMM {session_id}: Partial entry resolved — "
            f"CE@${ce_fill:.2f}, PE@${pe_fill:.2f}, starting monitor."
        )

        # Start the heartbeat monitor
        start_session_monitor(session_id, session)

        return jsonify({
            'success': True,
            'message': 'Partial entry resolved — session is now RUNNING',
            'status': 'RUNNING',
        })

    except Exception as e:
        log.exception(f"Failed to resolve partial entry for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>/retry-partial-leg', methods=['POST'])
def retry_partial_leg(session_id: str):
    """
    Retry the failed leg of a PARTIAL_ENTRY state.

    Launches a background thread to execute only the missing leg (CE or PE).
    If successful, transitions to RUNNING. If it fails again, remains in
    PARTIAL_ENTRY — the user can try again or use resolve-partial-entry to
    manually confirm.

    Returns immediately (non-blocking).
        { success: bool, status: 'STARTING', retrying_side: 'CE'|'PE' }
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
        if status != 'PARTIAL_ENTRY':
            return jsonify({
                'success': False,
                'error': f"Session must be in PARTIAL_ENTRY state. Current: {status}",
            }), 400

        partial = session.get('partial_entry', {})
        ce_filled = partial.get('ce_filled', False)
        pe_filled = partial.get('pe_filled', False)

        # Verify the fill prices already recorded for the filled side
        if ce_filled and not pe_filled:
            # PE failed — retry PE
            retrying_side = 'PE'
            symbol = session.get('pe', {}).get('symbol', '')
            lots = session.get('lots', 0) or session.get('ce', {}).get('original_lots', 0)
        elif pe_filled and not ce_filled:
            # CE failed — retry CE
            retrying_side = 'CE'
            symbol = session.get('ce', {}).get('symbol', '')
            lots = session.get('lots', 0) or session.get('pe', {}).get('original_lots', 0)
        else:
            return jsonify({
                'success': False,
                'error': 'Cannot determine which leg to retry. Use resolve-partial-entry instead.',
            }), 400

        if not symbol:
            return jsonify({
                'success': False,
                'error': f'{retrying_side} symbol not found. Cannot retry.',
            }), 400

        from .mmm_activity import log_activity
        log_activity('partial_entry_retry',
            f"Retrying failed {retrying_side} leg: SELL {lots} {symbol}",
            session_id=session_id, severity='progress',
            details={'side': retrying_side, 'symbol': symbol, 'lots': lots})

        # Launch background thread to retry just the missing leg
        t = threading.Thread(
            target=_retry_partial_leg_background,
            args=(session_id, retrying_side.lower(), symbol, lots),
            daemon=True,
            name=f'mmm-retry-{session_id}',
        )
        t.start()

        return jsonify({
            'success': True,
            'message': f'Retrying {retrying_side} leg in background',
            'status': 'PARTIAL_ENTRY',
            'retrying_side': retrying_side,
        })

    except Exception as e:
        log.exception(f"Failed to retry partial leg for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


def _retry_partial_leg_background(
    session_id: str, side: str, symbol: str, lots: int
):
    """
    Background thread: retry the failed leg of a PARTIAL_ENTRY.
    If successful, transition to RUNNING and start the monitor.
    """
    from .mmm_executor import get_executor
    from .mmm_activity import log_activity

    storage = get_storage()
    side_upper = side.upper()

    try:
        executor = get_executor()
        result = _run_async(
            executor.smart_execute(symbol, 'sell', lots, session_id=session_id)
        )
    except Exception as e:
        log.exception(f"MMM {session_id}: Retry {side_upper} leg crashed")
        log_activity('partial_entry_retry_failed',
            f"Retry {side_upper} crashed: {str(e)}",
            session_id=session_id, severity='error')
        return

    if not result.get('success'):
        log_activity('partial_entry_retry_failed',
            f"Retry {side_upper} failed: {result.get('error', 'Unknown error')}. "
            f"Session remains in PARTIAL_ENTRY. Try again or use Manual Resolve.",
            session_id=session_id, severity='error',
            details={'error': result.get('error'), 'side': side_upper})
        return

    # Update session with new fill
    fill_price = result.get('fill_price', 0)
    session = storage.get_session(session_id)
    if not session:
        log.error(f"MMM {session_id}: Session not found after retry success")
        return

    session[side]['entry_fill_price'] = fill_price
    session[side]['entry_order_id'] = result.get('order_id')
    session[side]['original_premium'] = fill_price

    # Record exchange commission via ledger (CRIT-1 fix)
    _od = result.get('order_details') or {}
    _commission = float(_od.get('paid_commission', 0) or _od.get('commission', 0) or 0)
    if _commission:
        from .mmm_pnl_core import record_fee as _pnl_fee
        _pnl_fee(session, _commission, 'sell_retry',
                 order_id=str(result.get('order_id', '')), side=side)

    # Update trigger snapshot for retried side
    retried_strike_key = strike_key(session[side].get('active_strike', 0))
    session[side]['trigger_snapshot'] = {retried_strike_key: fill_price}

    # Compute total premium from both fills
    ce_fill = session['ce'].get('entry_fill_price', 0) or 0
    pe_fill = session['pe'].get('entry_fill_price', 0) or 0
    lots_count = session.get('lots', 0) or session['ce'].get('original_lots', 0)
    actual_premium = (ce_fill + pe_fill) * lots_count * LOT_SIZE_BTC
    session['actual_total_premium'] = actual_premium
    session['total_premium_collected'] = actual_premium
    session['ce_premium_collected'] = ce_fill * lots_count * LOT_SIZE_BTC
    session['pe_premium_collected'] = pe_fill * lots_count * LOT_SIZE_BTC

    # Update trigger snapshots on both sides from their fill prices
    ce_strike_key = strike_key(session['ce'].get('active_strike', 0))
    pe_strike_key = strike_key(session['pe'].get('active_strike', 0))
    if ce_fill > 0:
        session['ce']['trigger_snapshot'] = {ce_strike_key: ce_fill}
    if pe_fill > 0:
        session['pe']['trigger_snapshot'] = {pe_strike_key: pe_fill}

    # Clear partial entry state and transition to RUNNING
    session.pop('partial_entry', None)
    session['strategy_status'] = 'RUNNING'
    session['entry_time'] = datetime.now(timezone.utc).isoformat()
    session['last_heartbeat'] = datetime.now(timezone.utc).isoformat()
    session['execution_timestamp'] = datetime.now(timezone.utc).isoformat()
    storage.save_session(session)

    emit_status_change(session_id, 'PARTIAL_ENTRY', 'RUNNING',
                       f'{side_upper} retry filled — both legs now confirmed')

    log_activity('entry_complete',
        f"Retry {side_upper} leg filled @ ${fill_price:.2f}. "
        f"CE@${ce_fill:.2f} + PE@${pe_fill:.2f} = ${actual_premium:.2f} total. "
        f"Session now RUNNING.",
        session_id=session_id, severity='success',
        details={'side': side_upper, 'fill_price': fill_price,
                 'ce_fill': ce_fill, 'pe_fill': pe_fill,
                 'total_premium': actual_premium})

    log.info(
        f"MMM {session_id}: Retry {side_upper} filled@${fill_price:.2f} — "
        f"total_premium=${actual_premium:.2f}. Starting monitor."
    )

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
        # Handle heartbeat race: storage may show PAUSED while monitor is mid-heartbeat.
        # Treat as success — same pattern as resume_session M-10 fix.
        if status == 'PAUSED':
            return jsonify({
                'success': True,
                'message': f'Session {session_id} is already paused',
                'status': 'PAUSED',
            })
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
    If the monitor thread is dead (e.g. watchdog max restarts), creates
    a fresh monitor instance and resets the watchdog restart counter.
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
        # M-10 fix: Only allow resume from PAUSED or RUNNING state
        # RUNNING can happen due to heartbeat race — treat as success
        if status == 'RUNNING':
            return jsonify({
                'success': True,
                'message': f'Session {session_id} is already running',
                'status': 'RUNNING',
            })
        if status != 'PAUSED':
            return jsonify({
                'success': False,
                'error': f"Cannot resume session in {status} state. Must be PAUSED.",
            }), 400

        old_status = status
        new_status = 'RUNNING'

        # Reset watchdog restart counter so the session gets a fresh set
        # of restart attempts after manual intervention.
        session['_watchdog_restarts'] = 0
        session['strategy_status'] = new_status
        session['last_heartbeat'] = datetime.now(timezone.utc).isoformat()
        # Clear whipsaw state — manual resume is an explicit user override
        session.pop('_whipsaw_paused_at', None)
        session.pop('_whipsaw_consecutive_alternating', None)
        session.pop('_paused_reason', None)
        session.pop('_paused_at', None)
        session.pop('_paused_resume_at', None)
        storage.save_session(session)

        emit_status_change(session_id, old_status, new_status, 'User resumed')

        # Check if a live monitor exists. If not (watchdog killed it),
        # start a brand new one instead of calling resume() on a dead object.
        from .mmm_monitor import get_monitor, start_session_monitor
        monitor = get_monitor(session_id)
        if monitor and getattr(monitor, '_running', False):
            # Reset watchdog counter on the LIVE monitor's in-memory session
            # so the watchdog won't immediately give up on next timeout.
            monitor.session['_watchdog_restarts'] = 0
            # Clear whipsaw state from live monitor's in-memory session too
            monitor.session.pop('_whipsaw_paused_at', None)
            monitor.session.pop('_whipsaw_consecutive_alternating', None)
            monitor.session.pop('_paused_reason', None)
            monitor.session.pop('_paused_at', None)
            monitor.session.pop('_paused_resume_at', None)
            monitor.resume('User resumed')
        else:
            # Monitor is dead — start a fresh one
            log.info(f"[{session_id}] Resume: monitor is dead, starting fresh instance")
            new_monitor = start_session_monitor(session_id, session)
            # Re-register with watchdog
            try:
                from .mmm_watchdog import MMMWatchdog
                MMMWatchdog.get_instance().register(new_monitor)
            except Exception as we:
                log.warning(f"[{session_id}] Resume: watchdog register failed: {we}")

        log.info(f"MMM session {session_id} resumed (watchdog restarts reset to 0)")

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

        # ── Step 1: Mark session STOPPED in DB ────────────────────────────────
        storage.update_session(session_id, {
            'strategy_status': new_status,
            'stopped_at': datetime.now(timezone.utc).isoformat(),
            'stop_reason': reason,
        })

        # ── Step 2: Stop monitor — triggers _save_my_session() inside ─────────
        # monitor.stop() sets session['strategy_status']='STOPPED' then calls
        # _save_my_session() (full save_session / data_json replace) then sets
        # _save_disabled=True.  After this point the monitor CANNOT write to DB.
        # This full save persists final realized_pnl / unrealized_pnl / total_fees
        # from the in-memory session but leaves net_pnl=None (never set by hb).
        stop_session_monitor(session_id, reason)

        # ── Step 3: Compute and persist net_pnl from the now-final DB state ───
        # We read back the values that _save_my_session() just wrote so we get
        # the most accurate R/U/F, then write only net_pnl.  No monitor is alive
        # so no further save_session() can overwrite this.
        try:
            _final = storage.get_session(session_id)
            if _final:
                # Derive final P&L from ledger (single source of truth)
                from .mmm_pnl_core import compute_realized_pnl as _pnl_r, compute_fees as _pnl_f
                _r = _pnl_r(_final)
                _u = _final.get('unrealized_pnl', 0) or 0
                _f = _pnl_f(_final)
                storage.update_session(session_id, {
                    'net_pnl': round(_r + _u - _f, 6),
                })
                log.info(
                    f"[{session_id}] Final P&L persisted (ledger-derived): "
                    f"R={_r:.4f} U={_u:.4f} F={_f:.4f} "
                    f"net={round(_r + _u - _f, 6):.4f}"
                )
        except Exception as _pnl_err:
            log.warning(f"[{session_id}] Could not persist final net_pnl: {_pnl_err}")
        # ── END PNL-STOP-FIX ──────────────────────────────────────────────────
        emit_status_change(session_id, old_status, new_status, reason)
        log.info(f"MMM session {session_id} stopped: {reason}")

        # ── SESSION EVENT: lifecycle stopped ──────────────────────────────
        try:
            from .mmm_audit_log import get_event_log as _get_evl
            from .mmm_audit_remark import build_event_remark as _ber
            _get_evl().enqueue_event(
                session_id=session_id,
                event_category='SESSION_LIFECYCLE',
                event_type='stopped',
                severity='INFO',
                remark=_ber('SESSION_LIFECYCLE', 'stopped', reason=reason),
                details={'reason': reason, 'new_status': new_status},
            )
        except Exception:
            pass
        # ── END SESSION EVENT ─────────────────────────────────────────────

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
# Global Graceful Exit — close all positions then stop
# =============================================================================

@mmm_bp.route('/session/<session_id>/exit_all', methods=['POST'])
def exit_all_session(session_id: str):
    """
    Initiate a global graceful exit for a session.

    Sets strategy_status = 'EXITING'. The next heartbeat detects this and
    calls run_exit_all() which closes all CE/PE positions across all strikes
    using the existing close_position() engine, then calls stop().

    Allowed from: RUNNING, PAUSED, BOTH_SIDES_UP, PARTIAL_ENTRY
    Not allowed from: EXITING (already in progress), STOPPED, IDLE

    Returns HTTP 202 Accepted (exit initiated asynchronously).
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({'success': False, 'error': f'Session not found: {session_id}'}), 404

        status = session.get('strategy_status', 'IDLE')

        if status == 'EXITING':
            return jsonify({
                'success': False,
                'error': 'Exit already in progress',
                'current_status': status,
            }), 409

        if status in ('STOPPED', 'IDLE'):
            return jsonify({
                'success': False,
                'error': f'Session is already {status} — nothing to exit',
                'current_status': status,
            }), 409

        data = request.get_json(silent=True) or {}
        reason = data.get('reason', 'user_requested')
        initiated_at = datetime.now(timezone.utc).isoformat()

        # Compute position summary for response
        def _lots(side_key):
            ss = session.get(side_key, {})
            return {
                'active_lots': ss.get('active_lots', 0),
                'frozen_lots': ss.get('frozen_total_lots', 0),
                'total_lots': ss.get('total_lots', 0),
            }

        # Set EXITING status atomically
        exit_fields = {
            'strategy_status': 'EXITING',
            '_exit_all_requested': True,
            '_exit_all_initiated_at': initiated_at,
            '_exit_all_reason': reason,
            '_exit_all_rounds_attempted': 0,
            '_exit_all_failed_positions': [],
            '_exit_all_partial': False,
            '_exit_all_completed_at': None,
        }
        storage.update_session(session_id, exit_fields)

        # Mirror into the live monitor's in-memory session (if running)
        monitor = get_monitor(session_id)
        if monitor:
            for k, v in exit_fields.items():
                monitor.session[k] = v

        emit_status_change(session_id, status, 'EXITING', f'Exit All initiated: {reason}')

        # Force the heartbeat to run immediately so exit starts without waiting
        # for the next scheduled interval
        if monitor:
            monitor.force_heartbeat()

        # Audit: activity log
        try:
            from .mmm_activity import log_activity
            log_activity(
                'session_exit_all_initiated',
                f'\U0001f6aa Exit All initiated (reason={reason}, from={status})',
                session_id, 'warning',
                {'reason': reason, 'prior_status': status, 'initiated_at': initiated_at},
            )
        except Exception:
            pass

        # Audit: event log
        try:
            from .mmm_audit_log import get_event_log as _get_evl
            from .mmm_audit_remark import build_event_remark as _ber
            _get_evl().enqueue_event(
                session_id=session_id,
                event_category='SESSION_LIFECYCLE',
                event_type='exit_all_initiated',
                severity='WARNING',
                remark=f'Exit All initiated — closing all positions (reason={reason})',
                details={'reason': reason, 'prior_status': status},
            )
        except Exception:
            pass

        log.warning(f"[{session_id}] EXIT ALL initiated from {status} (reason={reason})")

        return jsonify({
            'success': True,
            'message': f'Exit All initiated for session {session_id}',
            'session_id': session_id,
            'initiated_at': initiated_at,
            'prior_status': status,
            'positions_to_close': {
                'ce': _lots('ce'),
                'pe': _lots('pe'),
            },
        }), 202

    except Exception as e:
        log.exception(f"Failed to initiate exit_all for session {session_id}")
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
            # Return 200 (not 400) so the browser console doesn't show a red
            # network error.  This is a normal race condition: the session may
            # have transitioned out of BOTH_SIDES_UP between the time the UI
            # showed the alert and the time the user clicked.
            return jsonify({
                'success': False,
                'stale': True,
                'error': f"Session is no longer in BOTH_SIDES_UP state (current: {status})",
            }), 200

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
            'both_sides_decided_at': datetime.now(timezone.utc).isoformat(),
            'last_heartbeat': datetime.now(timezone.utc).isoformat(),
        }

        # Track in adjustment history
        history_entry = {
            'type': 'both_sides_decision',
            'decision': decision,
            'timestamp': datetime.now(timezone.utc).isoformat(),
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


@mmm_bp.route('/parameter_suggestions', methods=['GET'])
def get_parameter_suggestions():
    """
    Compute cross-session parameter suggestions based on the last N completed sessions.
    Returns human-readable suggestions the operator can accept or reject.
    This is decision support — nothing is auto-applied.

    Query params:
      n  — number of recent sessions to analyse (default 3, min 2)
    """
    try:
        n = max(2, int(request.args.get('n', 3)))
        storage = get_storage()
        all_sessions = storage.list_sessions() or []

        # Only completed sessions with meaningful analytics
        completed = [
            s for s in all_sessions
            if s.get('strategy_status') in ('STOPPED', 'COMPLETE')
            and s.get('session_id')
        ]
        # Most recent N
        completed = sorted(completed, key=lambda s: s.get('updated_at', ''), reverse=True)[:n]

        if len(completed) < 2:
            return jsonify({
                'success': True,
                'suggestions': [],
                'message': f'Need at least 2 completed sessions (have {len(completed)}). '
                           'Run more sessions to unlock suggestions.',
            })

        suggestions = []

        # Aggregate metrics across sessions using real session fields
        whipsaw_ratios, shield_exhausted_pct = [], []
        for s in completed:
            fires_total = (
                s.get('_atm_shield_count_ce', 0) + s.get('_atm_shield_count_pe', 0)
            )
            max_fires = s.get('params', {}).get('atm_shield_max_per_session', 3) * 2

            if fires_total > 0:
                # Whipsaw proxy: reversal_count / adjustment_count
                # High ratio = price kept reversing → shields likely fired on oscillations
                rev = s.get('reversal_count', 0)
                adj = max(1, s.get('adjustment_count', 1))
                whipsaw_ratios.append(rev / adj)
                shield_exhausted_pct.append(1.0 if fires_total >= max_fires else 0.0)

        avg_whipsaw = sum(whipsaw_ratios) / len(whipsaw_ratios) if whipsaw_ratios else 0
        avg_efficiency = 1.0  # reserved — requires per-fire buyback tracking not yet implemented
        pct_exhausted = sum(shield_exhausted_pct) / len(shield_exhausted_pct) if shield_exhausted_pct else 0

        sample_params = completed[0].get('params', {})

        # Rule 1: High whipsaw ratio → fire less eagerly
        if avg_whipsaw > 0.4:
            cur_prox = sample_params.get('atm_shield_proximity_pct', 0.5)
            cur_cool = sample_params.get('atm_shield_cooldown_mins', 10)
            suggestions.append({
                'param': 'atm_shield_proximity_pct',
                'current': cur_prox,
                'suggested': round(max(0.2, cur_prox * 0.85), 2),
                'reason': (
                    f'Shield fired and price reversed {avg_whipsaw*100:.0f}% of the time '
                    f'(threshold: 40%). Shield is firing too eagerly in oscillating conditions. '
                    f'Tighten proximity (fire closer to ATM) to reduce false fires.'
                ),
            })
            suggestions.append({
                'param': 'atm_shield_cooldown_mins',
                'current': cur_cool,
                'suggested': min(30, round(cur_cool * 1.3)),
                'reason': (
                    f'High whipsaw ratio ({avg_whipsaw*100:.0f}%). '
                    f'Extending cooldown reduces rapid-fire shield activation in choppy markets.'
                ),
            })

        # Rule 2: Low shield efficiency → reduce recovery lot aggression
        if avg_efficiency < 0.8:
            cur_split = sample_params.get('atm_shield_loss_split_aggressor', 0.3)
            suggestions.append({
                'param': 'atm_shield_loss_split_aggressor',
                'current': cur_split,
                'suggested': round(max(0.1, cur_split * 0.8), 2),
                'reason': (
                    f'Shield recovered only {avg_efficiency*100:.0f}% of buyback cost '
                    f'(threshold: 80%). Recovery lots are over-recovering — '
                    f'reduce aggressor split to sell fewer recovery lots per fire.'
                ),
            })

        # Rule 3: Shield exhausted most sessions → increase max_per_session
        if pct_exhausted > 0.5:
            cur_max = sample_params.get('atm_shield_max_per_session', 3)
            suggestions.append({
                'param': 'atm_shield_max_per_session',
                'current': cur_max,
                'suggested': min(10, cur_max + 1),
                'reason': (
                    f'Shield was exhausted in {pct_exhausted*100:.0f}% of sessions '
                    f'(threshold: 50%). Increase max_per_session to give the shield '
                    f'more capacity in future sessions.'
                ),
            })

        return jsonify({
            'success': True,
            'sessions_analysed': len(completed),
            'metrics': {
                'avg_whipsaw_ratio': round(avg_whipsaw, 3),
                'avg_shield_efficiency': round(avg_efficiency, 3),
                'pct_sessions_exhausted': round(pct_exhausted, 3),
            },
            'suggestions': suggestions,
            'message': (
                f'Based on {len(completed)} completed sessions. '
                'All suggestions require operator confirmation — nothing is auto-applied.'
            ),
        })

    except Exception as e:
        log.exception("Failed to compute parameter suggestions")
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

        margin_data = _run_async(fetch_margin_utilization(rest))

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

        async def _fetch_all():
            import asyncio as _aio
            margin_task = fetch_margin_utilization(rest)
            positions_task = rest.get_positions_margined()
            margin_data, raw_positions = await _aio.gather(
                margin_task, positions_task, return_exceptions=True
            )
            if isinstance(margin_data, Exception):
                margin_data = {'success': False, 'error': str(margin_data)}
            if isinstance(raw_positions, Exception):
                raw_positions = []
            return margin_data, raw_positions

        margin_data, raw_positions = _run_async(_fetch_all())

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

        log.info(f"[{session_id}] Received param update request: {list(data.keys())}")

        # Validate with hot-reload restriction if running
        validated, errors = validate_params(data, hot_only=is_running)
        if errors:
            log.warning(f"[{session_id}] Param validation errors: {errors}")
            return jsonify({
                'success': False,
                'error': 'Parameter validation failed',
                'details': errors,
            }), 400

        if not validated:
            submitted_keys = set(data.keys())
            from .mmm_config import PARAM_RULES
            unknown_keys = [k for k in submitted_keys if k not in PARAM_RULES]
            log.warning(
                f"[{session_id}] No valid parameters after validation. "
                f"Submitted: {list(submitted_keys)}, Unknown (skipped): {unknown_keys}"
            )
            return jsonify({
                'success': False,
                'error': 'No valid parameters to update',
                'details': f'All {len(submitted_keys)} submitted parameters were either unknown or filtered out. '
                           f'Unknown parameters (skipped): {unknown_keys}' if unknown_keys else
                           'All submitted parameters were filtered out (possibly non-hot parameters while session is running).',
            }), 400

        # Merge with existing params
        # M-8 fix: shallow copy to avoid mutating session dict before persist succeeds
        current_params = dict(session.get('params', {}))
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

        # IMP-10: Cap raise impact preview — compute warning before applying
        cap_raise_warning = None
        if 'max_lots_per_side' in changed_keys and is_running:
            old_cap = session.get('params', {}).get('max_lots_per_side', 100)
            new_cap = validated['max_lots_per_side']
            if new_cap > old_cap:
                ce_lots = session.get('ce', {}).get('total_lots', 0)
                pe_lots = session.get('pe', {}).get('total_lots', 0)
                ce_unrealized = session.get('ce', {}).get('unrealized_pnl', 0) or 0
                pe_unrealized = session.get('pe', {}).get('unrealized_pnl', 0) or 0
                total_unrealized = ce_unrealized + pe_unrealized
                heavy_lots = max(ce_lots, pe_lots)
                light_lots = max(min(ce_lots, pe_lots), 1)
                ratio_now = heavy_lots / light_lots if light_lots > 0 else 0
                cap_raise_warning = {
                    'old_cap': old_cap,
                    'new_cap': new_cap,
                    'current_ce_lots': ce_lots,
                    'current_pe_lots': pe_lots,
                    'current_unrealized_loss': round(total_unrealized, 2),
                    'asymmetry_ratio': round(ratio_now, 1),
                    'message': (
                        f"Cap raise {old_cap} → {new_cap}: "
                        f"CE={ce_lots} lots, PE={pe_lots} lots, "
                        f"unrealized ${total_unrealized:+,.0f}. "
                        f"Raising PE cap does NOT reduce CE exposure. "
                        f"Current asymmetry ratio: {ratio_now:.1f}:1."
                    ),
                }
                log.warning(
                    f"[{session_id}] IMP-10 Cap raise: {old_cap} → {new_cap}. "
                    f"CE={ce_lots}, PE={pe_lots}, uPnL=${total_unrealized:+.0f}"
                )

        # Set auto-expiry timestamp when breakeven_high_risk_mode is toggled ON.
        # The engine reads _high_risk_mode_expires_at to auto-expire after 4 hours.
        # Must use datetime.now(timezone.utc) — NOT datetime.utcnow() (robustv2 fix #14).
        session_updates = {'params': current_params}
        if 'breakeven_high_risk_mode' in changed_keys:
            from datetime import timedelta
            if validated.get('breakeven_high_risk_mode', False):
                expires_at = (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()
                session_updates['_high_risk_mode_expires_at'] = expires_at
                log.info(f"[{session_id}] breakeven_high_risk_mode enabled; expires at {expires_at}")
            else:
                # Explicitly clear when toggled OFF so expiry doesn't linger
                session_updates['_high_risk_mode_expires_at'] = None

        # Persist
        storage.update_session(session_id, session_updates)

        # Emit WebSocket update
        emit_params_changed(session_id, {k: validated[k] for k in changed_keys})

        # ── SESSION EVENT: param changes (one event per changed param) ─────
        try:
            from .mmm_audit_log import get_event_log as _get_evl
            from .mmm_audit_remark import build_event_remark as _ber
            _orig_params = session.get('params', {})
            for _pk in changed_keys:
                _get_evl().enqueue_event(
                    session_id=session_id,
                    event_category='PARAM_CHANGE',
                    event_type='hot_reload',
                    severity='INFO',
                    remark=_ber('PARAM_CHANGE', 'hot_reload',
                                param=_pk,
                                old_value=_orig_params.get(_pk),
                                new_value=current_params.get(_pk)),
                    details={
                        'param': _pk,
                        'old_value': _orig_params.get(_pk),
                        'new_value': current_params.get(_pk),
                    },
                )
        except Exception:
            pass

        log.info(f"MMM session {session_id} params updated: {changed_keys}")

        response = {
            'success': True,
            'message': f'Updated {len(changed_keys)} parameter(s)',
            'params': current_params,
            'changed': changed_keys,
        }
        if cap_raise_warning:
            response['cap_raise_warning'] = cap_raise_warning
        return jsonify(response)

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
            'timestamp': datetime.now(timezone.utc).isoformat(),
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
        category = request.args.get('category')

        activity_log = get_activity_log()
        activities = activity_log.get_recent(
            limit=limit,
            session_id=session_id,
            severity=severity,
            category=category,
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


@mmm_bp.route('/preview_atm_straddle', methods=['POST'])
def preview_atm_straddle():
    """
    Find the ATM strike for a SHORT_STRADDLE session.
    Returns the same strike for both CE and PE.

    Body: { expiry: str, underlying: str (optional) }
    """
    try:
        data = request.get_json(force=True)
        expiry = data.get('expiry')
        underlying = data.get('underlying', 'BTC')

        if not expiry:
            return jsonify({'success': False, 'error': 'expiry is required'}), 400

        initializer = get_initializer()
        result = initializer.preview_atm_straddle(expiry, underlying)

        if result.get('success'):
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        log.exception("Failed to preview ATM straddle")
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

        # SAFETY: Validate entry expiry matches session creation expiry.
        # The session ID encodes the expiry (e.g. mmm24feb26-2 ↔ 24022026).
        # If these diverge, all trades go to wrong-dated contracts.
        creation_expiry = session.get('params', {}).get('expiry', '')
        if creation_expiry and creation_expiry != expiry:
            return jsonify({
                'success': False,
                'error': (
                    f'Expiry mismatch: session was created with expiry {creation_expiry} '
                    f'but entry specifies {expiry}. This would route trades to wrong contracts. '
                    f'Use the correct expiry or create a new session.'
                ),
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
        # L-1 fix: pass session params so configurable expiry_hour/minute_utc are used
        session['expiry_time'] = expiry_to_utc_datetime(expiry, session.get('params', {}))
        session['initial_total_premium'] = total_premium
        session['entry_time'] = datetime.now(timezone.utc).isoformat()
        session['updated_at'] = datetime.now(timezone.utc).isoformat()
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

        # SAFETY: Validate entry expiry matches session creation expiry.
        # The session ID encodes the expiry (e.g. mmm24feb26-2 ↔ 24022026).
        # If these diverge, all trades go to wrong-dated contracts.
        creation_expiry = session.get('params', {}).get('expiry', '')
        if creation_expiry and creation_expiry != expiry:
            return jsonify({
                'success': False,
                'error': (
                    f'Expiry mismatch: session was created with expiry {creation_expiry} '
                    f'but import specifies {expiry}. This would route trades to wrong contracts. '
                    f'Use the correct expiry or create a new session.'
                ),
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
        # L-1 fix: pass session params so configurable expiry_hour/minute_utc are used
        session['expiry_time'] = expiry_to_utc_datetime(expiry, session.get('params', {}))
        session['initial_total_premium'] = total_premium
        session['entry_time'] = datetime.now(timezone.utc).isoformat()
        session['updated_at'] = datetime.now(timezone.utc).isoformat()
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
        except Exception as e:
            log.warning(f"[{session_id}] spot price fetch failed during adoption: {e}")  # M-5 fix

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
                                    strike_key(active_strike): live_mark,
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

        result = _run_async(executor.execute_entry(ce_symbol, pe_symbol, lots))

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
            # H-1 fix: include LOT_SIZE_BTC to match correct calculation at line ~580
            ce_fill = ce_res.get('fill_price', 0)
            pe_fill = pe_res.get('fill_price', 0)
            actual_premium = (ce_fill + pe_fill) * lots * LOT_SIZE_BTC

            session['actual_total_premium'] = actual_premium
            # Keep strategy_status as IDLE — user starts session manually
            session['execution_timestamp'] = datetime.now(timezone.utc).isoformat()
            session['updated_at'] = datetime.now(timezone.utc).isoformat()

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
                'heartbeat_count': monitor.session.get('_heartbeat_counter', 0),
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
                        session_id=session_id,
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
                    # M-9 fix: guard against None return from apply_lifo_removals
                    if avg_entry is None:
                        log.warning(f"[{session_id}] avg_entry is None for {side_key} — defaulting to 0")
                        avg_entry = 0.0
                    session[side_key] = side_state

                    group_realized = (avg_entry - fill_price) * group_lots * LOT_SIZE_BTC
                    total_realized += group_realized
                    # Record exchange commission (fee) — Delta uses 'paid_commission' for actual fees
                    _od = result.get('order_details') or {}
                    _commission = float(_od.get('paid_commission', 0) or _od.get('commission', 0) or 0)

                    # ── P&L via ledger (single source of truth) ──────
                    _mr_close_oid = str(result.get('order_id', '') or '')
                    from .mmm_pnl_core import record_close as _pnl_mr_rec
                    _pnl_mr_rec(
                        session=session,
                        order_id=_mr_close_oid,
                        symbol=result.get('symbol', ''),
                        option_side=side_key,
                        strike=strike_val,
                        lots=int(group_lots),
                        entry_premium=float(avg_entry),
                        close_premium=float(fill_price),
                        commission=abs(float(_commission)) if _commission else 0.0,
                        source='manual_reduce',
                    )
                    # ── END P&L via ledger ────────────────────────────

                    # Stamp close_order_id for FillSyncer matching
                    _mr_close_coid = str(result.get('client_order_id', '') or '')
                    for _mp in side_state.get('positions', []):
                        if (_mp.get('status') == 'closed'
                                and _mp.get('_estimated_pnl_booked') is None):
                            if _mr_close_oid:
                                _mp['close_order_id'] = _mr_close_oid
                            if _mr_close_coid:
                                _mp['close_client_order_id'] = _mr_close_coid
                            _mp_entry = float(_mp.get('entry_premium', 0) or 0)
                            _mp_lots = float(_mp.get('_closed_lots', _mp.get('lots', 0)) or 0)
                            if _mp_lots > 0 and _mp_entry > 0:
                                _mp['_estimated_pnl_booked'] = round(
                                    (_mp_entry - fill_price) * _mp_lots * LOT_SIZE_BTC, 8)
                                _mp['_estimated_commission_booked'] = round(
                                    abs(_commission) * _mp_lots / group_lots, 8) if _commission and group_lots else 0.0

                    reduction_record = {
                        'side': side_key.upper(),
                        'lots': group_lots,
                        'strike': strike_val,
                        'avg_entry_price': round(avg_entry, 4),
                        'fill_price': round(fill_price, 4),
                        'realized_pnl': round(group_realized, 2),
                        'timestamp': datetime.now(timezone.utc).isoformat(),
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

                    # ── TRADE AUDIT: manual reduce BUY ───────────────────────────
                    try:
                        from .mmm_audit_log import get_audit_log as _get_aud
                        from .mmm_audit_remark import build_trade_remark as _btr
                        _get_aud().enqueue_trade(
                            session_id=session_id,
                            action='BUY',
                            option_type=side_key.upper(),
                            strike=int(strike_val),
                            quantity_requested=group_lots,
                            quantity_filled=group_lots,
                            premium=float(fill_price),
                            event_type='EXIT',
                            mechanism='operator',
                            expiry=session.get('params', {}).get('expiry', ''),
                            spot_price_usd=float(session.get('_regime_spot_price', 0) or 0),
                            whipsaw_state=str(session.get('_whipsaw_state', '') or ''),
                            margin_tier=str(session.get('_margin_tier', '') or ''),
                            remark=_btr(
                                'BUY', 'EXIT',
                                side=side_key, strike=int(strike_val),
                                lots=group_lots, premium=float(fill_price),
                                mechanism='operator',
                            ),
                        )
                    except Exception:
                        pass
                    # ── END TRADE AUDIT ──────────────────────────────────────────

        _run_async(_do_reduce())

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

            ce_now, pe_now = _run_async(_fetch_premiums())
            if ce_now > 0 and pe_now > 0:
                update_trigger_snapshots(session, ce_now, pe_now)
                log.info(
                    f'[{session_id}] Manual reduce: trigger snapshots reset '
                    f'CE={ce_now:.2f} PE={pe_now:.2f}'
                )
        except Exception as snap_err:
            log.warning(f'[{session_id}] Could not reset trigger snapshots after manual reduce: {snap_err}')

        session['updated_at'] = datetime.now(timezone.utc).isoformat()

        # AUDIT FIX (stale-unrealized bug): realized_pnl increased from the closes but
        # unrealized_pnl is stale (still includes the just-closed positions' contributions).
        # Refresh it via the monitor's cached prices before saving so that the REST response
        # to the frontend's fetchSessions() call returns an accurate net_pnl.
        try:
            from .mmm_monitor import get_monitor as _get_mon
            _mon = _get_mon(session_id)
            if _mon and hasattr(_mon, '_engine') and hasattr(_mon, '_make_fetch_fn'):
                _fresh = _mon._engine.compute_unrealized_pnl(session, _mon._make_fetch_fn())
                session['unrealized_pnl'] = _fresh
                log.debug(f"[{session_id}] P&L refresh after manual reduce: unrealized={_fresh:.4f}")
        except Exception as _e:
            log.warning(f"[{session_id}] P&L refresh after manual reduce failed (non-critical): {_e}")

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
        except Exception as e:
            log.warning(f"[{session_id}] WS emit failed after manual reduce: {e}")  # M-6 fix

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


@mmm_bp.route('/session/<session_id>/option-chain', methods=['GET'])
def get_option_chain(session_id: str):
    """
    Return all available OTM strikes for this session's expiry with live premiums.
    Used by the Inject Position dialog strike picker.

    Returns:
        {
            success: bool,
            spot_price: float,
            ce: [{ strike, premium, bid, ask, mark_price, delta, oi }, ...],
            pe: [{ strike, premium, bid, ask, mark_price, delta, oi }, ...],
        }
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)
        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        expiry = session.get('params', {}).get('expiry', '')
        underlying = session.get('params', {}).get('underlying', 'BTC')
        if not expiry:
            return jsonify({'success': False, 'error': 'Session has no expiry'}), 400

        initializer = get_initializer()
        from .mmm_initializer import normalize_expiry
        expiry_norm = normalize_expiry(expiry)
        chain_data = initializer.chain_service.get_chain_data(underlying, expiry_norm)
        if not chain_data or not chain_data.get('chain'):
            return jsonify({'success': False, 'error': f'No chain data for {expiry_norm}'}), 404

        spot_price = chain_data.get('spot_price', 0)
        chain = chain_data['chain']

        ce_strikes, pe_strikes = [], []
        for entry in chain:
            strike = entry.get('strike', 0)
            if not strike:
                continue
            for opt_type, above_spot, bucket in [('call', True, ce_strikes), ('put', False, pe_strikes)]:
                if above_spot and strike <= spot_price:
                    continue
                if not above_spot and strike >= spot_price:
                    continue
                od = entry.get(opt_type) or {}
                bid = od.get('bid', 0) or 0
                ask = od.get('ask', 0) or 0
                mark = od.get('mark_price', 0) or 0
                premium = mark if mark > 0 else ((bid + ask) / 2 if bid > 0 and ask > 0 else bid)
                if premium <= 0:
                    continue
                bucket.append({
                    'strike': strike,
                    'premium': round(premium, 2),
                    'bid': round(bid, 2),
                    'ask': round(ask, 2),
                    'mark_price': round(mark, 2),
                    'delta': round(od.get('delta', 0) or 0, 3),
                    'oi': od.get('oi', 0) or 0,
                })

        ce_strikes.sort(key=lambda x: x['strike'])
        pe_strikes.sort(key=lambda x: x['strike'], reverse=True)

        return jsonify({
            'success': True,
            'spot_price': round(spot_price, 0),
            'ce': ce_strikes,
            'pe': pe_strikes,
        })
    except Exception as e:
        log.exception(f'get_option_chain failed for {session_id}')
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>/inject-position', methods=['POST'])
def inject_position(session_id: str):
    """
    Operator-inject: Open a new short option position and register it in
    the running algo session ledger so the algo manages it going forward.

    Useful when the algo missed an entry or the operator wants to manually
    add exposure while keeping the risk management loop intact.

    Body (JSON):
        side   : str   — 'ce' or 'pe'
        lots   : int   — number of lots to sell
        strike : float — strike price to sell at

    Safety guards:
        - Session must be RUNNING or PAUSED
        - Lots + current active_lots must not exceed max_lots_per_side
        - Guardian signal must be GO

    After a successful fill the position is added to positions[] with
    type='manual' and recompute_side_lots() rebuilds all derived fields.
    Trigger snapshots are reset to current premiums so the next heartbeat
    uses a fresh baseline.

    Returns:
        {
            success        : bool,
            side           : str,
            lots           : int,
            strike         : float,
            fill_price     : float,
            order_id       : str,
            new_active_lots: int,
        }
    """
    from .mmm_trigger import update_trigger_snapshots
    from .mmm_executor import get_executor
    from .mmm_activity import log_activity
    from .mmm_initializer import get_initializer
    from .mmm_state import recompute_side_lots as _recompute

    try:
        data = request.get_json(force=True) or {}
        side_param = data.get('side', '').lower()
        lots_param = int(data.get('lots', 0))
        strike_raw = data.get('strike')
        adopt = bool(data.get('adopt', False))
        adopt_fill_price = data.get('fill_price')  # required when adopt=True

        if side_param not in ('ce', 'pe'):
            return jsonify({'success': False, 'error': "side must be 'ce' or 'pe'"}), 400
        if lots_param <= 0:
            return jsonify({'success': False, 'error': 'lots must be a positive integer'}), 400
        if not strike_raw:
            return jsonify({'success': False, 'error': 'strike is required'}), 400

        strike_val = float(strike_raw)
        if strike_val <= 0:
            return jsonify({'success': False, 'error': 'strike must be a positive number'}), 400

        if adopt:
            if adopt_fill_price is None:
                return jsonify({'success': False, 'error': 'fill_price is required in adopt mode'}), 400
            adopt_fill_price = float(adopt_fill_price)
            if adopt_fill_price <= 0:
                return jsonify({'success': False, 'error': 'fill_price must be a positive number'}), 400
        else:
            # Guardian check only needed when actually placing an order
            signal = _check_guardian_signal()
            if signal != 'GO':
                return jsonify({'success': False, 'error': f'Guardian signal is {signal}'}), 403

        storage = get_storage()
        session = storage.get_session(session_id)
        if not session:
            return jsonify({'success': False, 'error': f'Session not found: {session_id}'}), 404

        status = session.get('strategy_status', 'IDLE')
        if status not in ('RUNNING', 'PAUSED'):
            return jsonify({
                'success': False,
                'error': f'Session must be RUNNING or PAUSED. Current: {status}',
            }), 400

        params = session.get('params', {})
        side_state = session.get(side_param, {})

        if not adopt:
            # --- Cap check (only for real orders — adopt registers existing exposure) ---
            max_lots = int(params.get('max_lots_per_side', 100))
            current_lots = side_state.get('active_lots', 0)
            if current_lots + lots_param > max_lots:
                return jsonify({
                    'success': False,
                    'error': (
                        f'Would exceed max_lots_per_side ({max_lots}). '
                        f'Current active: {current_lots}, requesting: {lots_param}.'
                    ),
                }), 400

        expiry = params.get('expiry', '')
        option_type = 'call' if side_param == 'ce' else 'put'
        executor = get_executor()
        initializer = get_initializer()
        symbol = initializer.build_symbol(option_type, 'BTC', strike_val, expiry)

        if adopt:
            fill_price = adopt_fill_price
            order_id = ''
            client_order_id = ''
            log_activity(
                'manual_inject',
                f'📌 Adopt: register existing {lots_param} {side_param.upper()} @ {int(strike_val)} '
                f'(fill ${fill_price:.2f}) — no order placed',
                session_id, 'info',
                {'side': side_param.upper(), 'strike': strike_val, 'lots': lots_param,
                 'fill_price': fill_price, 'adopt': True},
            )
        else:
            log_activity(
                'manual_inject',
                f'💉 Inject: SELL {lots_param} {side_param.upper()} @ {int(strike_val)} ({symbol})',
                session_id, 'info',
                {'side': side_param.upper(), 'strike': strike_val, 'lots': lots_param},
            )

            result = _run_async(executor.smart_execute(
                symbol=symbol,
                side='sell',
                size=lots_param,
                reduce_only=False,
                session_id=session_id,
            ))

            if not result.get('success'):
                err = result.get('error', 'execution failed')
                log_activity(
                    'manual_inject',
                    f'💉 Inject FAILED: {side_param.upper()} @ {int(strike_val)} — {err}',
                    session_id, 'error',
                    {'side': side_param.upper(), 'strike': strike_val, 'error': err},
                )
                return jsonify({'success': False, 'error': err}), 500

            fill_price = float(result.get('fill_price', 0))
            order_id = str(result.get('order_id', ''))
            client_order_id = str(result.get('client_order_id', ''))

            # Record exchange commission via ledger (CRIT-1 fix)
            _od = result.get('order_details') or {}
            _commission = float(_od.get('paid_commission', 0) or _od.get('commission', 0) or 0)
            if _commission:
                from .mmm_pnl_core import record_fee as _pnl_fee
                _pnl_fee(session, _commission, 'sell_inject',
                         order_id=str(result.get('order_id', '')),
                         side=side_param)

        now = datetime.now(timezone.utc).isoformat()

        # --- Record fill in positions[] (Unified Ledger) ---
        counter = side_state.get('_pos_counter', 0) + 1
        side_state['_pos_counter'] = counter
        side_state.setdefault('positions', []).append({
            'id': f"{side_param}_manual_{counter:03d}",
            'strike': strike_val,
            'lots': lots_param,
            'entry_premium': fill_price,
            'premium': fill_price,
            'type': 'manual',
            'status': 'active',
            'created_at': now,
            'fill_confirmed_at': now,           # reconciliation: settlement-lag guard
            'order_id': order_id,               # reconciliation: verify fill via exchange
            'client_order_id': client_order_id, # reconciliation: per-session fill attribution
            'shifted_at': None,
            'closed_at': None,
            'realized_pnl': None,
            'timestamp': now,
            'source': 'operator_inject',
        })
        side_state = _recompute(side_state)
        session[side_param] = side_state

        # ── TRADE AUDIT: operator inject / adopt ─────────────────────────
        try:
            from .mmm_audit_log import get_audit_log as _get_aud
            from .mmm_audit_remark import build_trade_remark as _btr
            _mech = 'adopt' if adopt else 'operator'
            _get_aud().enqueue_trade(
                session_id=session_id,
                action='SELL',
                option_type=side_param.upper(),
                strike=int(strike_val),
                quantity_requested=lots_param,
                quantity_filled=lots_param,
                premium=fill_price,
                event_type='ENTRY',
                mechanism=_mech,
                order_id=order_id,
                expiry=params.get('expiry', ''),
                spot_price_usd=float(session.get('_regime_spot_price', 0) or 0),
                remark=_btr(
                    'SELL', 'ENTRY',
                    side=side_param, strike=int(strike_val),
                    lots=lots_param, premium=fill_price,
                    mechanism=_mech,
                ),
            )
        except Exception:
            pass
        # ── END TRADE AUDIT ──────────────────────────────────────────────

        # Track total premium collected
        premium_collected = fill_price * lots_param * LOT_SIZE_BTC
        session['total_premium_collected'] = (
            session.get('total_premium_collected', 0) + premium_collected
        )
        _spk = 'ce_premium_collected' if side_param.lower() == 'ce' else 'pe_premium_collected'
        session[_spk] = session.get(_spk, 0) + premium_collected

        # Audit trail entry (no adjustment_count increment — this is not an algo decision)
        session.setdefault('adjustment_history', []).append({
            'side': side_param.upper(),
            'aggressor': 'OPERATOR',
            'lots_sold': lots_param,
            'premium': fill_price,
            'strike': strike_val,
            'timestamp': now,
            'type': 'manual',
            'premium_collected': premium_collected,
            'adjustment_number': session.get('adjustment_count', 0),
            'source': 'operator_inject',
            'spot': session.get('_regime_spot_price', 0),
        })
        if len(session['adjustment_history']) > 200:
            session['adjustment_history'] = session['adjustment_history'][-200:]

        # --- Reset trigger snapshots with fresh premiums ---
        try:
            other_side = 'pe' if side_param == 'ce' else 'ce'
            other_state = session.get(other_side, {})
            other_strike = other_state.get('active_strike', 0)
            other_option_type = 'put' if other_side == 'pe' else 'call'
            other_sym = initializer.build_symbol(other_option_type, 'BTC', other_strike, expiry)

            async def _fetch_other_mid():
                return await executor.get_mid_price(other_sym)

            other_mid = _run_async(_fetch_other_mid()) or 0.0
            ce_now = fill_price if side_param == 'ce' else other_mid
            pe_now = fill_price if side_param == 'pe' else other_mid
            if ce_now > 0 and pe_now > 0:
                update_trigger_snapshots(session, ce_now, pe_now)
                log.info(
                    f'[{session_id}] Inject: trigger snapshots reset '
                    f'CE={ce_now:.2f} PE={pe_now:.2f}'
                )
        except Exception as snap_err:
            log.warning(f'[{session_id}] Could not reset trigger snapshots after inject: {snap_err}')

        session['updated_at'] = now
        storage.save_session(session)

        # --- WebSocket notification ---
        try:
            from .mmm_websocket import emit_manual_injection
            emit_manual_injection(
                session_id=session_id,
                side=side_param.upper(),
                lots=lots_param,
                strike=strike_val,
                fill_price=fill_price,
                order_id=order_id,
            )
        except Exception as ws_err:
            log.warning(f'[{session_id}] WS emit failed after inject: {ws_err}')

        _action = 'Adopt' if adopt else 'Inject'
        log_activity(
            'manual_inject',
            f'💉 {_action} OK: {lots_param} {side_param.upper()} @ {int(strike_val)} '
            f'fill ${fill_price:.2f} (new active: {side_state.get("active_lots", 0)} lots)',
            session_id, 'success',
            {
                'side': side_param.upper(),
                'strike': strike_val,
                'lots': lots_param,
                'fill_price': fill_price,
                'order_id': order_id,
                'new_active_lots': side_state.get('active_lots', 0),
                'adopt': adopt,
            },
        )

        log.info(
            f'[{session_id}] {_action} complete: {side_param.upper()} '
            f'{lots_param} lots @ {strike_val} fill=${fill_price:.2f}'
        )

        # Breakeven + gamma cache invalidation — positions changed after inject fill
        try:
            from .mmm_breakeven_engine import get_breakeven_engine
            from .mmm_gamma_detector import get_gamma_detector
            get_breakeven_engine().invalidate_cache(session_id)
            get_gamma_detector().invalidate_cache(session_id)
        except Exception:
            pass

        return jsonify({
            'success': True,
            'side': side_param.upper(),
            'lots': lots_param,
            'strike': strike_val,
            'fill_price': fill_price,
            'order_id': order_id,
            'new_active_lots': side_state.get('active_lots', 0),
            'adopted': adopt,
        })

    except Exception as e:
        log.exception(f'Failed to inject position for {session_id}')
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>/set-active-strike', methods=['POST'])
def set_active_strike(session_id: str):
    """
    Switch the algo's monitoring focal point to a different open strike.

    No order is placed — purely a state update. The algo will start fetching
    premium and computing loss-delta at the new strike on the next heartbeat.

    Trigger snapshots are reset to current live premiums so the next heartbeat
    starts from a fresh baseline (no false-positive adjustment on switch).

    Body (JSON):
        side   : str   — 'ce' or 'pe'
        strike : float — target strike (must have active/shifted positions)

    Returns:
        {success, side, old_strike, new_strike}
    """
    from .mmm_trigger import update_trigger_snapshots
    from .mmm_executor import get_executor
    from .mmm_initializer import get_initializer
    from .mmm_activity import log_activity

    try:
        data = request.get_json(force=True) or {}
        side_param = data.get('side', '').lower()
        strike_raw = data.get('strike')

        if side_param not in ('ce', 'pe'):
            return jsonify({'success': False, 'error': "side must be 'ce' or 'pe'"}), 400
        if not strike_raw:
            return jsonify({'success': False, 'error': 'strike is required'}), 400

        strike_val = float(strike_raw)
        if strike_val < 1000:
            return jsonify({'success': False, 'error': 'strike must be >= 1000'}), 400

        storage = get_storage()
        session = storage.get_session(session_id)
        if not session:
            return jsonify({'success': False, 'error': f'Session not found: {session_id}'}), 404

        status = session.get('strategy_status', 'IDLE')
        if status not in ('RUNNING', 'PAUSED'):
            return jsonify({
                'success': False,
                'error': f'Session must be RUNNING or PAUSED. Current: {status}',
            }), 400

        side_state = session.get(side_param, {})
        positions = side_state.get('positions', [])

        # Confirm target strike has open positions
        target_lots = sum(
            p.get('lots', 0) for p in positions
            if p.get('status') in ('active', 'shifted')
            and abs(float(p.get('strike', 0)) - strike_val) < 1
        )
        if target_lots <= 0:
            return jsonify({
                'success': False,
                'error': f'No open positions at {int(strike_val)} {side_param.upper()}',
            }), 400

        old_strike = side_state.get('active_strike', 0)
        if abs(old_strike - strike_val) < 1:
            # Allow the operation if all positions at this strike are shifted (frozen) —
            # user needs to un-shift them even though active_strike already points here.
            active_lots_here = sum(
                p.get('lots', 0) for p in positions
                if p.get('status') == 'active'
                and abs(float(p.get('strike', 0)) - strike_val) < 1
            )
            if active_lots_here > 0:
                return jsonify({'success': False, 'error': 'That strike is already active'}), 400

        params = session.get('params', {})
        expiry = params.get('expiry', '')
        option_type = 'call' if side_param == 'ce' else 'put'
        executor = get_executor()
        initializer = get_initializer()

        # Un-shift positions at the new active strike so they become active again
        # (positions may be 'shifted'/frozen from a previous strike shift)
        for _pos in side_state.get('positions', []):
            if _pos.get('status') == 'shifted' and abs(float(_pos.get('strike', 0)) - strike_val) < 1:
                _pos['status'] = 'active'
                _pos['shifted_at'] = None

        side_state['active_strike'] = strike_val
        side_state['active_strike_pinned'] = True  # User explicitly chose — disable auto-ATM
        from .mmm_state import recompute_side_lots as _recompute_sas
        side_state = _recompute_sas(side_state)
        session[side_param] = side_state

        log_activity(
            'set_active_strike',
            f'📌 Active strike: {side_param.upper()} {int(old_strike)} → {int(strike_val)}',
            session_id, 'info',
            {'side': side_param.upper(), 'old_strike': old_strike, 'new_strike': strike_val},
        )

        # Reset trigger snapshots with fresh live premiums
        try:
            other_side = 'pe' if side_param == 'ce' else 'ce'
            other_state = session.get(other_side, {})
            other_strike = other_state.get('active_strike', 0)
            new_sym = initializer.build_symbol(option_type, 'BTC', strike_val, expiry)
            other_option_type = 'put' if other_side == 'pe' else 'call'
            other_sym = (
                initializer.build_symbol(other_option_type, 'BTC', other_strike, expiry)
                if other_strike else None
            )

            async def _fetch_both():
                new_mid = await executor.get_mid_price(new_sym)
                other_mid = await executor.get_mid_price(other_sym) if other_sym else 0.0
                return new_mid, other_mid

            new_mid, other_mid = _run_async(_fetch_both())
            ce_now = new_mid if side_param == 'ce' else other_mid
            pe_now = new_mid if side_param == 'pe' else other_mid
            # Use whichever premium is available for the unresolved side
            ce_use = ce_now if ce_now > 0 else pe_now
            pe_use = pe_now if pe_now > 0 else ce_now
            if ce_use > 0 or pe_use > 0:
                update_trigger_snapshots(session, ce_use, pe_use)
                log.info(
                    f'[{session_id}] Set-active-strike: trigger snapshots reset '
                    f'CE={ce_use:.2f} PE={pe_use:.2f}'
                )
        except Exception as snap_err:
            log.warning(
                f'[{session_id}] Could not reset trigger snapshots after set-active-strike: {snap_err}'
            )
            # Fallback: ensure the new active strike has a trigger_snapshot entry.
            # Use 0 as placeholder — the heartbeat heal will replace it with
            # the live premium on the next beat (prevents indefinite 0.0 gauge).
            from .mmm_constants import strike_key as _sk
            _sk_val = _sk(strike_val)
            snap = side_state.setdefault('trigger_snapshot', {})
            if _sk_val not in snap or snap.get(_sk_val, 0) == 0:
                log.warning(
                    f'[{session_id}] Set-active-strike fallback: trigger_snapshot[{_sk_val}] '
                    f'left at 0 — heartbeat heal will initialise on next beat'
                )

        session['updated_at'] = datetime.now(timezone.utc).isoformat()
        storage.save_session(session)

        try:
            from .mmm_websocket import emit_to_session
            emit_to_session(session_id, 'mmm_active_strike_changed', {
                'session_id': session_id,
                'side': side_param.upper(),
                'old_strike': old_strike,
                'new_strike': strike_val,
            })
        except Exception as ws_err:
            log.warning(f'[{session_id}] WS emit failed after set-active-strike: {ws_err}')

        log.info(
            f'[{session_id}] Active strike changed: {side_param.upper()} '
            f'{int(old_strike)} → {int(strike_val)}'
        )

        return jsonify({
            'success': True,
            'side': side_param.upper(),
            'old_strike': old_strike,
            'new_strike': strike_val,
        })

    except Exception as e:
        log.exception(f'Failed to set active strike for {session_id}')
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>/close-strike', methods=['POST'])
def close_strike_route(session_id: str):
    """
    Operator manual: Buy back ALL open lots at a specific strike and remove
    them from the algo's position ledger.

    Use case: strike is approaching ATM (delta risk rising) and the operator
    wants to close the risky position and optionally re-establish farther OTM
    via inject-position. This avoids needing perp futures for delta hedging.

    If the closed strike was the active_strike, the algo automatically
    promotes the remaining open strike with the most lots as the new
    active_strike. Trigger snapshots are reset accordingly.

    Body (JSON):
        side   : str   — 'ce' or 'pe'
        strike : float — strike to close entirely

    Safety guards:
        - Session must be RUNNING or PAUSED
        - Guardian signal must be GO
        - In-flight guard: positions marked _being_closed before order placement

    Returns:
        {success, side, strike, lots_closed, fill_price, realized_pnl, new_active_strike}
    """
    from .mmm_trigger import update_trigger_snapshots
    from .mmm_executor import get_executor
    from .mmm_initializer import get_initializer
    from .mmm_activity import log_activity
    from .mmm_state import recompute_side_lots as _recompute
    from collections import defaultdict

    try:
        data = request.get_json(force=True) or {}
        side_param = data.get('side', '').lower()
        strike_raw = data.get('strike')

        if side_param not in ('ce', 'pe'):
            return jsonify({'success': False, 'error': "side must be 'ce' or 'pe'"}), 400
        if not strike_raw:
            return jsonify({'success': False, 'error': 'strike is required'}), 400

        strike_val = float(strike_raw)
        if strike_val < 1000:
            return jsonify({'success': False, 'error': 'strike must be >= 1000'}), 400

        # Guardian check before any order
        signal = _check_guardian_signal()
        if signal != 'GO':
            return jsonify({'success': False, 'error': f'Guardian signal is {signal}'}), 403

        storage = get_storage()
        session = storage.get_session(session_id)
        if not session:
            return jsonify({'success': False, 'error': f'Session not found: {session_id}'}), 404

        status = session.get('strategy_status', 'IDLE')
        if status not in ('RUNNING', 'PAUSED'):
            return jsonify({
                'success': False,
                'error': f'Session must be RUNNING or PAUSED. Current: {status}',
            }), 400

        side_state = session.get(side_param, {})
        positions = side_state.get('positions', [])

        # Collect all open positions at this strike (active + shifted/frozen)
        target_positions = [
            p for p in positions
            if p.get('status') in ('active', 'shifted')
            and abs(float(p.get('strike', 0)) - strike_val) < 1
            and not p.get('_being_closed')
        ]

        if not target_positions:
            return jsonify({
                'success': False,
                'error': f'No open positions at {int(strike_val)} {side_param.upper()}',
            }), 400

        total_lots = sum(p.get('lots', 0) for p in target_positions)
        if total_lots <= 0:
            return jsonify({'success': False, 'error': 'Total lots at strike is 0'}), 400

        # In-flight guard: mark before placing order (prevents duplicate if state-removal crashes)
        for p in target_positions:
            p['_being_closed'] = True

        params = session.get('params', {})
        expiry = params.get('expiry', '')
        option_type = 'call' if side_param == 'ce' else 'put'
        executor = get_executor()
        initializer = get_initializer()
        symbol = initializer.build_symbol(option_type, 'BTC', strike_val, expiry)

        log_activity(
            'manual_close_strike',
            f'🔴 Close Strike: BUY {total_lots} {side_param.upper()} @ {int(strike_val)} ({symbol})',
            session_id, 'info',
            {'side': side_param.upper(), 'strike': strike_val, 'lots': total_lots},
        )

        result = _run_async(executor.smart_execute(
            symbol=symbol,
            side='buy',
            size=total_lots,
            reduce_only=True,
            session_id=session_id,
        ))

        if not result.get('success'):
            err = result.get('error', 'execution failed')
            for p in target_positions:
                p.pop('_being_closed', None)
            log_activity(
                'manual_close_strike',
                f'🔴 Close Strike FAILED: {side_param.upper()} @ {int(strike_val)} — {err}',
                session_id, 'error',
                {'side': side_param.upper(), 'strike': strike_val, 'error': err},
            )
            return jsonify({'success': False, 'error': err}), 500

        fill_price = float(result.get('fill_price', 0))
        order_id = str(result.get('order_id', ''))

        # ── TRADE AUDIT: manual close-strike BUY ──────────────────────────
        try:
            from .mmm_audit_log import get_audit_log as _get_aud
            from .mmm_audit_remark import build_trade_remark as _btr
            _get_aud().enqueue_trade(
                session_id=session_id,
                action='BUY',
                option_type=side_param.upper(),
                strike=int(strike_val),
                quantity_requested=total_lots,
                quantity_filled=total_lots,
                premium=fill_price,
                event_type='EXIT',
                mechanism='operator',
                order_id=order_id,
                expiry=expiry,
                spot_price_usd=float(session.get('_regime_spot_price', 0) or 0),
                whipsaw_state=str(session.get('_whipsaw_state', '') or ''),
                margin_tier=str(session.get('_margin_tier', '') or ''),
                remark=_btr(
                    'BUY', 'EXIT',
                    side=side_param, strike=int(strike_val),
                    lots=total_lots, premium=fill_price,
                    mechanism='operator',
                ),
            )
        except Exception:
            pass
        # ── END TRADE AUDIT ───────────────────────────────────────────────

        # Extract commission for ledger recording (pnl_core handles session['total_fees'])
        _od = result.get('order_details') or {}
        _commission = float(_od.get('paid_commission', 0) or _od.get('commission', 0) or 0)

        now = datetime.now(timezone.utc).isoformat()

        # Mark all target positions as closed and compute realized P&L.
        # CLOSE-STRIKE-FIX: stamp _estimated_pnl_booked so fill_sync computes a
        # correction only (not a full re-book), matching the close_at_5 pattern.
        total_realized = 0.0
        for p in target_positions:
            entry = float(p.get('entry_premium', p.get('premium', 0)))
            lots = p.get('lots', 0)
            realized = (entry - fill_price) * lots * LOT_SIZE_BTC
            p['status'] = 'closed'
            p['closed_at'] = now
            p['realized_pnl'] = round(realized, 6)
            p['_estimated_pnl_booked'] = round(realized, 8)
            p['_estimated_commission_booked'] = (
                round(abs(_commission) * lots / total_lots, 8)
                if _commission and total_lots else 0.0
            )
            p.pop('_being_closed', None)
            total_realized += realized

        # If closing the active_strike, promote the open strike with most lots
        old_active = side_state.get('active_strike', 0)
        new_active = old_active
        if abs(old_active - strike_val) < 1:
            # BUG FIX: include 'shifted' positions in candidates — all non-active-strike
            # open positions have status='shifted', so filtering for 'active' only always
            # yields an empty list, causing new_active=0 and active_lots=0 with frozen stuck.
            remaining = [
                p for p in positions
                if p.get('status') in ('active', 'shifted')
                and abs(float(p.get('strike', 0)) - strike_val) >= 1
            ]
            if remaining:
                by_strike = defaultdict(int)
                for p in remaining:
                    by_strike[float(p['strike'])] += p.get('lots', 0)
                new_active = max(by_strike, key=by_strike.get)
                # BUG FIX: un-shift positions at the promoted strike so recompute sees them
                # as active (mirrors the logic in set_active_strike).
                for _pos in positions:
                    if (_pos.get('status') == 'shifted'
                            and abs(float(_pos.get('strike', 0)) - new_active) < 1):
                        _pos['status'] = 'active'
                        _pos['shifted_at'] = None
            else:
                new_active = 0
            side_state['active_strike'] = new_active
            log.info(
                f'[{session_id}] active_strike auto-promoted after close: '
                f'{side_param.upper()} {int(old_active)} → {int(new_active) if new_active else "none"}'
            )

        side_state = _recompute(side_state)
        session[side_param] = side_state

        # Reset trigger snapshots to reflect new state
        try:
            other_side = 'pe' if side_param == 'ce' else 'ce'
            other_state = session.get(other_side, {})
            other_strike = other_state.get('active_strike', 0)
            other_option_type = 'put' if other_side == 'pe' else 'call'
            other_sym = (
                initializer.build_symbol(other_option_type, 'BTC', other_strike, expiry)
                if other_strike else None
            )

            async def _fetch_snap():
                new_strike_mid = 0.0
                if new_active and abs(new_active - strike_val) >= 1:
                    new_sym = initializer.build_symbol(option_type, 'BTC', new_active, expiry)
                    new_strike_mid = await executor.get_mid_price(new_sym)
                other_mid = (
                    await executor.get_mid_price(other_sym)
                    if other_sym and other_strike else 0.0
                )
                return new_strike_mid, other_mid

            new_mid, other_mid = _run_async(_fetch_snap())
            ce_now = new_mid if side_param == 'ce' else other_mid
            pe_now = new_mid if side_param == 'pe' else other_mid
            ce_use = ce_now if ce_now > 0 else pe_now
            pe_use = pe_now if pe_now > 0 else ce_now
            if ce_use > 0 or pe_use > 0:
                update_trigger_snapshots(session, ce_use, pe_use)
        except Exception as snap_err:
            log.warning(f'[{session_id}] Could not reset trigger snapshots after close-strike: {snap_err}')

        # ── P&L via ledger (single source of truth) ──────────────────
        # Record the aggregate close for this strike group.
        # fill_sync will confirm with actual exchange fill later.
        from .mmm_pnl_core import record_close as _pnl_cbs_rec
        # Compute weighted avg entry across all target positions
        _cbs_w_sum = sum(
            float(p.get('entry_premium', p.get('premium', 0))) * p.get('lots', 0)
            for p in target_positions
        )
        _cbs_avg_entry = _cbs_w_sum / total_lots if total_lots > 0 else 0
        _pnl_cbs_rec(
            session=session,
            order_id=order_id,
            symbol=symbol,
            option_side=side_param,
            strike=strike_val,
            lots=int(total_lots),
            entry_premium=float(_cbs_avg_entry),
            close_premium=float(fill_price),
            commission=abs(float(_commission)) if _commission else 0.0,
            source='close_by_strike',
        )
        session['total_realized_pnl'] = session.get('total_realized_pnl', 0.0) + total_realized
        # ── END P&L via ledger ────────────────────────────────────────

        # Refresh unrealized now that these positions are gone.
        try:
            _mon = get_monitor(session_id)
            if _mon:
                _fresh_u = _mon._engine.compute_unrealized_pnl(session, _mon._make_fetch_fn())
                session['unrealized_pnl'] = _fresh_u
        except Exception:
            pass

        session['updated_at'] = now
        storage.save_session(session)

        try:
            from .mmm_websocket import emit_to_session
            emit_to_session(session_id, 'mmm_strike_closed', {
                'session_id': session_id,
                'side': side_param.upper(),
                'strike': strike_val,
                'lots_closed': total_lots,
                'fill_price': fill_price,
                'realized_pnl': round(total_realized, 2),
                'new_active_strike': new_active,
            })
        except Exception as ws_err:
            log.warning(f'[{session_id}] WS emit failed after close-strike: {ws_err}')

        log_activity(
            'manual_close_strike',
            f'🔴 Close Strike OK: {side_param.upper()} @ {int(strike_val)} '
            f'fill ${fill_price:.2f}, P&L ${total_realized:.2f}',
            session_id, 'success',
            {
                'side': side_param.upper(),
                'strike': strike_val,
                'lots': total_lots,
                'fill_price': fill_price,
                'realized_pnl': round(total_realized, 2),
                'order_id': order_id,
            },
        )

        log.info(
            f'[{session_id}] Close strike complete: {side_param.upper()} '
            f'{total_lots} lots @ {strike_val} fill=${fill_price:.2f} P&L=${total_realized:.2f}'
        )

        # ── TRADE AUDIT: operator close-strike ───────────────────────────
        try:
            from .mmm_audit_log import get_audit_log as _get_aud
            from .mmm_audit_remark import build_trade_remark as _btr
            # Weighted average entry premium across all closed positions
            _w_entry = sum(
                float(p.get('entry_premium', p.get('premium', 0)) or 0) * p.get('lots', 0)
                for p in target_positions
            )
            _avg_entry = _w_entry / total_lots if total_lots > 0 else 0.0
            _get_aud().enqueue_trade(
                session_id=session_id,
                action='BUY',
                option_type=side_param.upper(),
                strike=int(strike_val),
                quantity_requested=total_lots,
                quantity_filled=total_lots,
                premium=fill_price,
                event_type='EXIT',
                mechanism='operator',
                order_id=order_id,
                expiry=params.get('expiry', ''),
                closing_entry_premium=round(_avg_entry, 4),
                closing_entry_lots=total_lots,
                realized_pnl_usd=float(total_realized),
                spot_price_usd=float(session.get('_regime_spot_price', 0) or 0),
                remark=_btr(
                    'BUY', 'EXIT',
                    side=side_param, strike=int(strike_val),
                    lots=total_lots, premium=fill_price,
                    mechanism='operator',
                    entry_premium=round(_avg_entry, 4),
                    realized_pnl=float(total_realized),
                ),
            )
        except Exception:
            pass
        # ── END TRADE AUDIT ──────────────────────────────────────────────

        return jsonify({
            'success': True,
            'side': side_param.upper(),
            'strike': strike_val,
            'lots_closed': total_lots,
            'fill_price': fill_price,
            'realized_pnl': round(total_realized, 2),
            'order_id': order_id,
            'new_active_strike': new_active,
        })

    except Exception as e:
        log.exception(f'Failed to close strike for {session_id}')
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>/adjust-active-lots', methods=['POST'])
def adjust_active_lots(session_id: str):
    """
    Operator manual: Increase or decrease active lots on one side by placing
    an order at the current active strike.

    - delta > 0: SELL delta lots at active_strike (adds to ledger as 'manual' position)
    - delta < 0: BUY |delta| lots at active_strike (partial close, LIFO from active positions)

    Body (JSON):
        side  : str — 'ce' or 'pe'
        delta : int — lots to add (positive) or remove (negative), nonzero

    Safety guards:
        - Session must be RUNNING or PAUSED
        - Guardian signal must be GO
        - For increase: active_lots + delta must not exceed max_lots_per_side
        - For decrease: |delta| must not exceed current active_lots at active_strike

    Returns:
        { success, side, delta, active_strike, fill_price, order_id, new_active_lots,
          realized_pnl (decrease only) }
    """
    from .mmm_trigger import update_trigger_snapshots
    from .mmm_executor import get_executor
    from .mmm_activity import log_activity
    from .mmm_initializer import get_initializer
    from .mmm_state import recompute_side_lots as _recompute

    try:
        data = request.get_json(force=True) or {}
        side_param = data.get('side', '').lower()
        delta = int(data.get('delta', 0))

        if side_param not in ('ce', 'pe'):
            return jsonify({'success': False, 'error': "side must be 'ce' or 'pe'"}), 400
        if delta == 0:
            return jsonify({'success': False, 'error': 'delta must be nonzero'}), 400

        signal = _check_guardian_signal()
        if signal != 'GO':
            return jsonify({'success': False, 'error': f'Guardian signal is {signal}'}), 403

        storage = get_storage()
        session = storage.get_session(session_id)
        if not session:
            return jsonify({'success': False, 'error': f'Session not found: {session_id}'}), 404

        status = session.get('strategy_status', 'IDLE')
        if status not in ('RUNNING', 'PAUSED'):
            return jsonify({'success': False,
                            'error': f'Session must be RUNNING or PAUSED. Current: {status}'}), 400

        side_state = session.get(side_param, {})
        active_strike = side_state.get('active_strike', 0)
        if not active_strike:
            return jsonify({'success': False,
                            'error': f'No active strike for {side_param.upper()}'}), 400

        positions = side_state.get('positions', [])
        params = session.get('params', {})
        expiry = params.get('expiry', '')
        option_type = 'call' if side_param == 'ce' else 'put'
        initializer = get_initializer()
        executor = get_executor()
        symbol = initializer.build_symbol(option_type, 'BTC', active_strike, expiry)
        now = datetime.now(timezone.utc).isoformat()

        if delta > 0:
            # ── INCREASE: sell delta lots at active_strike ─────────────────
            active_lots = side_state.get('active_lots', 0)
            max_lots = params.get('max_lots_per_side', 999)
            if active_lots + delta > max_lots:
                return jsonify({'success': False,
                                'error': f'Would exceed max_lots_per_side ({max_lots}). '
                                         f'Current active: {active_lots}'}), 400

            log_activity(
                'manual_adjust_lots',
                f'➕ Adjust Lots: SELL {delta} {side_param.upper()} @ {int(active_strike)}',
                session_id, 'info',
                {'side': side_param.upper(), 'strike': active_strike,
                 'lots': delta, 'direction': 'increase'},
            )

            result = _run_async(executor.smart_execute(
                symbol=symbol, side='sell', size=delta, session_id=session_id,
            ))

            if not result.get('success'):
                err = result.get('error', 'execution failed')
                log_activity(
                    'manual_adjust_lots',
                    f'➕ Adjust Lots FAILED: {side_param.upper()} @ {int(active_strike)} '
                    f'+{delta} — {err}',
                    session_id, 'error',
                    {'side': side_param.upper(), 'strike': active_strike,
                     'lots': delta, 'error': err},
                )
                return jsonify({'success': False, 'error': err}), 500

            fill_price = float(result.get('fill_price', 0))
            order_id = str(result.get('order_id', ''))

            _od = result.get('order_details') or {}
            _commission = float(_od.get('paid_commission', 0) or _od.get('commission', 0) or 0)
            if _commission:
                try:
                    from .mmm_pnl_core import record_fee as _pnl_fee
                    _pnl_fee(session, _commission, 'sell_adjust',
                             order_id=order_id, side=side_param)
                except Exception:
                    pass

            positions.append({
                'id': f"{side_param}_adj_{now.replace(':', '').replace('-', '').replace('.', '')[:18]}",
                'strike': active_strike,
                'lots': delta,
                'entry_premium': fill_price,
                'premium': fill_price,
                'type': 'manual',
                'status': 'active',
                'created_at': now,
                'shifted_at': None,
                'closed_at': None,
                'realized_pnl': None,
                'timestamp': now,
                'source': 'operator_adjust',
                'order_id': order_id,
            })
            side_state['positions'] = positions
            side_state = _recompute(side_state)
            session[side_param] = side_state

            try:
                from .mmm_audit_log import get_audit_log as _get_aud
                from .mmm_audit_remark import build_trade_remark as _btr
                _get_aud().enqueue_trade(
                    session_id=session_id,
                    action='SELL', option_type=side_param.upper(),
                    strike=int(active_strike),
                    quantity_requested=delta, quantity_filled=delta,
                    premium=fill_price, event_type='ENTRY', mechanism='operator',
                    order_id=order_id, expiry=expiry,
                    spot_price_usd=float(session.get('_regime_spot_price', 0) or 0),
                    whipsaw_state=str(session.get('_whipsaw_state', '') or ''),
                    margin_tier=str(session.get('_margin_tier', '') or ''),
                    remark=_btr('SELL', 'ENTRY', side=side_param,
                                strike=int(active_strike), lots=delta,
                                premium=fill_price, mechanism='operator'),
                )
            except Exception:
                pass

            try:
                # Set the adjusted side's trigger snapshot to fill_price so the
                # next heartbeat does not immediately re-trigger on stale excess.
                # Only update the adjusted side — we don't know current market
                # price for the other side and it wasn't part of this adjustment.
                side_state = session.get(side_param, {})
                if 'trigger_snapshot' not in side_state:
                    side_state['trigger_snapshot'] = {}
                side_state['trigger_snapshot'][strike_key(active_strike)] = fill_price
            except Exception as snap_err:
                log.warning(f'[{session_id}] Could not reset trigger snapshots after adjust: {snap_err}')

            session['updated_at'] = now
            storage.save_session(session)

            try:
                from .mmm_websocket import emit_manual_injection
                emit_manual_injection(
                    session_id=session_id, side=side_param.upper(),
                    lots=delta, strike=active_strike,
                    fill_price=fill_price, order_id=order_id,
                )
            except Exception:
                pass

            log_activity(
                'manual_adjust_lots',
                f'➕ Adjust Lots OK: +{delta} {side_param.upper()} @ {int(active_strike)} '
                f'fill ${fill_price:.2f} (active: {side_state.get("active_lots", 0)})',
                session_id, 'success',
                {'side': side_param.upper(), 'strike': active_strike,
                 'lots': delta, 'fill_price': fill_price},
            )

            return jsonify({
                'success': True,
                'side': side_param,
                'delta': delta,
                'active_strike': active_strike,
                'fill_price': fill_price,
                'order_id': order_id,
                'new_active_lots': side_state.get('active_lots', 0),
            })

        else:
            # ── DECREASE: buy back |delta| lots from active_strike ─────────
            abs_delta = abs(delta)
            active_lots = side_state.get('active_lots', 0)
            if abs_delta > active_lots:
                return jsonify({'success': False,
                                'error': f'Cannot remove {abs_delta} lots — only '
                                         f'{active_lots} active on {side_param.upper()}'}), 400

            target_positions = [
                p for p in positions
                if p.get('status') == 'active'
                and abs(float(p.get('strike', 0)) - active_strike) < 1
                and not p.get('_being_closed')
            ]
            if not target_positions:
                return jsonify({'success': False,
                                'error': f'No active positions at {int(active_strike)} '
                                         f'to reduce on {side_param.upper()}'}), 400

            total_available = sum(p.get('lots', 0) for p in target_positions)
            if abs_delta > total_available:
                return jsonify({'success': False,
                                'error': f'Active lots at {int(active_strike)}: '
                                         f'{total_available}, requested: {abs_delta}'}), 400

            # LIFO: reduce newest positions first
            target_positions.sort(key=lambda p: p.get('created_at', ''), reverse=True)

            # In-flight guard before placing order
            for p in target_positions:
                p['_being_closed'] = True

            log_activity(
                'manual_adjust_lots',
                f'➖ Adjust Lots: BUY {abs_delta} {side_param.upper()} @ {int(active_strike)} '
                f'(partial close)',
                session_id, 'info',
                {'side': side_param.upper(), 'strike': active_strike,
                 'lots': abs_delta, 'direction': 'decrease'},
            )

            result = _run_async(executor.smart_execute(
                symbol=symbol, side='buy', size=abs_delta,
                reduce_only=True, session_id=session_id,
            ))

            if not result.get('success'):
                err = result.get('error', 'execution failed')
                for p in target_positions:
                    p.pop('_being_closed', None)
                log_activity(
                    'manual_adjust_lots',
                    f'➖ Adjust Lots FAILED: {side_param.upper()} @ {int(active_strike)} '
                    f'-{abs_delta} — {err}',
                    session_id, 'error',
                    {'side': side_param.upper(), 'strike': active_strike,
                     'lots': abs_delta, 'error': err},
                )
                return jsonify({'success': False, 'error': err}), 500

            fill_price = float(result.get('fill_price', 0))
            order_id = str(result.get('order_id', ''))
            _od = result.get('order_details') or {}
            _commission = float(_od.get('paid_commission', 0) or _od.get('commission', 0) or 0)

            # Distribute lot reduction across positions (LIFO)
            remaining = abs_delta
            total_realized = 0.0
            for p in target_positions:
                if remaining <= 0:
                    break
                p_lots = p.get('lots', 0)
                to_remove = min(remaining, p_lots)
                entry = float(p.get('entry_premium', p.get('premium', 0)))
                realized = (entry - fill_price) * to_remove * LOT_SIZE_BTC
                comm_share = (
                    round(abs(_commission) * to_remove / abs_delta, 8)
                    if _commission else 0.0
                )

                if to_remove >= p_lots:
                    # Close this position entirely
                    p['lots'] = 0
                    p['status'] = 'closed'
                    p['closed_at'] = now
                    p['realized_pnl'] = round(realized, 6)
                    p['_estimated_pnl_booked'] = round(realized, 8)
                    p['_estimated_commission_booked'] = comm_share
                else:
                    # Partial: split off a closed sub-position, keep remainder active
                    closed_pos = dict(p)
                    ts_suffix = now.replace(':', '').replace('-', '').replace('.', '')[:14]
                    closed_pos['id'] = f"{p['id']}_partial_{ts_suffix}"
                    closed_pos['lots'] = to_remove
                    closed_pos['status'] = 'closed'
                    closed_pos['closed_at'] = now
                    closed_pos['realized_pnl'] = round(realized, 6)
                    closed_pos['_estimated_pnl_booked'] = round(realized, 8)
                    closed_pos['_estimated_commission_booked'] = comm_share
                    closed_pos.pop('_being_closed', None)
                    positions.append(closed_pos)
                    p['lots'] = p_lots - to_remove

                p.pop('_being_closed', None)
                total_realized += realized
                remaining -= to_remove

            if _commission:
                try:
                    from .mmm_pnl_core import record_fee as _pnl_fee
                    _pnl_fee(session, _commission, 'buy_adjust',
                             order_id=order_id, side=side_param)
                except Exception:
                    pass

            side_state['positions'] = positions
            side_state = _recompute(side_state)
            session[side_param] = side_state

            try:
                from .mmm_audit_log import get_audit_log as _get_aud
                from .mmm_audit_remark import build_trade_remark as _btr
                _get_aud().enqueue_trade(
                    session_id=session_id,
                    action='BUY', option_type=side_param.upper(),
                    strike=int(active_strike),
                    quantity_requested=abs_delta, quantity_filled=abs_delta,
                    premium=fill_price, event_type='EXIT', mechanism='operator',
                    order_id=order_id, expiry=expiry,
                    spot_price_usd=float(session.get('_regime_spot_price', 0) or 0),
                    whipsaw_state=str(session.get('_whipsaw_state', '') or ''),
                    margin_tier=str(session.get('_margin_tier', '') or ''),
                    remark=_btr('BUY', 'EXIT', side=side_param,
                                strike=int(active_strike), lots=abs_delta,
                                premium=fill_price, mechanism='operator'),
                )
            except Exception:
                pass

            session['updated_at'] = now
            storage.save_session(session)

            try:
                from .mmm_websocket import emit_manual_injection
                emit_manual_injection(
                    session_id=session_id, side=side_param.upper(),
                    lots=-abs_delta, strike=active_strike,
                    fill_price=fill_price, order_id=order_id,
                )
            except Exception:
                pass

            log_activity(
                'manual_adjust_lots',
                f'➖ Adjust Lots OK: -{abs_delta} {side_param.upper()} @ {int(active_strike)} '
                f'fill ${fill_price:.2f} P&L ${total_realized:.4f} '
                f'(active: {side_state.get("active_lots", 0)})',
                session_id, 'success',
                {'side': side_param.upper(), 'strike': active_strike,
                 'lots': abs_delta, 'fill_price': fill_price,
                 'realized_pnl': total_realized},
            )

            return jsonify({
                'success': True,
                'side': side_param,
                'delta': delta,
                'active_strike': active_strike,
                'fill_price': fill_price,
                'order_id': order_id,
                'realized_pnl': round(total_realized, 6),
                'new_active_lots': side_state.get('active_lots', 0),
            })

    except Exception as e:
        log.exception(f'Failed to adjust active lots for {session_id}')
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>/reconcile', methods=['POST'])
def reconcile_session(session_id: str):
    """
    Force an immediate exchange reconciliation for any session (including PAUSED).

    Queries actual exchange positions and auto-corrects phantom positions
    where the session shows lots that the exchange no longer has (e.g.,
    expired options, manually closed positions).

    Safe to call on RUNNING, PAUSED, or STOPPED sessions.
    """
    import asyncio
    try:
        monitor = get_monitor(session_id)
        if monitor:
            # Running/paused monitor — force reconciliation on next heartbeat
            monitor.session['_recon_counter'] = 0
            monitor.session['_force_recon'] = True

            if monitor.is_running and not monitor.is_paused:
                # For running sessions, trigger immediate heartbeat
                monitor.force_heartbeat()
                return jsonify({
                    'success': True,
                    'message': 'Reconciliation triggered — will run on next heartbeat (forced)',
                })
            else:
                # For paused sessions: run reconciliation directly via async
                async def run_recon():
                    await monitor._reconcile_exchange_positions()
                    monitor._save_my_session()

                _run_async(run_recon())
                last_recon = monitor.session.get('last_reconciliation', {})
                discrepancies = last_recon.get('discrepancies', [])
                auto_corrected = [d for d in discrepancies if d.get('auto_corrected')]
                return jsonify({
                    'success': True,
                    'message': f'Reconciliation complete — {len(discrepancies)} discrepancies found, '
                               f'{len(auto_corrected)} auto-corrected',
                    'discrepancies': discrepancies,
                })
        else:
            # No active monitor — load from storage and reconcile directly
            storage = get_storage()
            session = storage.get_session(session_id)
            if not session:
                return jsonify({'success': False, 'error': 'Session not found'}), 404

            # Check if the session's expiry has passed — if so, ALL positions
            # should be 0 on exchange (auto-settled). Mark them expired.
            from datetime import datetime, timezone
            from .mmm_state import recompute_side_lots
            expiry_str = session.get('params', {}).get('expiry', '')
            corrections = []
            _now = datetime.now(timezone.utc).isoformat()

            # Parse expiry: DDMMYYYY format
            is_expired = False
            if expiry_str and len(expiry_str) == 8:
                try:
                    exp_date = datetime.strptime(expiry_str, '%d%m%Y').replace(
                        hour=23, minute=59, tzinfo=timezone.utc)
                    is_expired = datetime.now(timezone.utc) > exp_date
                except ValueError:
                    pass

            if is_expired:
                # Expired session — all exchange positions should be 0.
                # Close ALL non-closed positions (active, shifted, frozen, etc.)
                for side_key in ['ce', 'pe']:
                    side = session.get(side_key, {})
                    closed_count = 0
                    closed_lots = 0

                    for pos in side.get('positions', []):
                        if pos.get('status') not in ('closed', 'expired'):
                            old_status = pos.get('status', '?')
                            old_lots = pos.get('lots', 0)
                            pos['status'] = 'closed'
                            pos['closed_at'] = _now
                            pos['close_reason'] = f'expired_reconcile (was {old_status})'
                            closed_count += 1
                            closed_lots += old_lots

                    if closed_count > 0:
                        recompute_side_lots(side)
                        corrections.append(
                            f"{side_key.upper()}: closed {closed_count} positions "
                            f"({closed_lots} lots) — all expired"
                        )

                if corrections:
                    session['last_reconciliation'] = {
                        'timestamp': _now,
                        'type': 'expired_cleanup',
                        'corrections': corrections,
                    }
                    storage.save_session(session)

                return jsonify({
                    'success': True,
                    'message': f'Expired session cleanup — {len(corrections)} corrections applied',
                    'corrections': corrections,
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Session has no active monitor. Start or resume the session first.',
                }), 400

    except Exception as e:
        log.exception(f"Failed to reconcile session {session_id}")
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
                path="/v2/positions/margined",
            )
            return resp.get('result', [])

        positions_raw = _run_async(fetch())

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
            'timestamp': datetime.now(timezone.utc).isoformat(),
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

        orders_raw = _run_async(fetch())

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
            'timestamp': datetime.now(timezone.utc).isoformat(),
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
            snap = side.get('trigger_snapshot', {})
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


@mmm_bp.route('/session/<session_id>/breakeven', methods=['GET'])
def get_breakeven(session_id: str):
    """
    GET /api/mmm/session/<session_id>/breakeven

    Returns the latest breakeven analysis result for the session.
    Reads from session state (_breakeven_result) set by the heartbeat.
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)
        if not session:
            return jsonify({'success': False, 'error': f'Session not found: {session_id}'}), 404

        result = session.get('_breakeven_result')
        if result is None:
            # Session exists but no breakeven computed yet
            return jsonify({
                'success': True,
                'breakeven': None,
                'message': 'No breakeven data yet — session may not have started heartbeats',
            })

        return jsonify({'success': True, 'breakeven': result})

    except Exception as e:
        log.exception(f"Failed to get breakeven for session {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>/gamma', methods=['GET'])
def get_gamma(session_id: str):
    """
    GET /api/mmm/session/<session_id>/gamma
    Returns latest gamma detector result for the session.
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)
        if not session:
            return jsonify({'success': False, 'error': f'Session not found: {session_id}'}), 404

        result = session.get('_gamma_result')
        if result is None:
            return jsonify({
                'success': True,
                'gamma': None,
                'message': 'No gamma data yet — session may not have started heartbeats',
            })

        return jsonify({'success': True, 'gamma': result})

    except Exception as e:
        log.exception(f"Failed to get gamma for session {session_id}")
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

        ticker_results = _run_async(fetch_all())

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
            'timestamp': datetime.now(timezone.utc).isoformat(),
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
                    if start_dt.tzinfo is None:
                        start_dt = start_dt.replace(tzinfo=timezone.utc)
                    current_duration = (datetime.now(timezone.utc) - start_dt).total_seconds()
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


# =============================================================================
# Performance Intelligence Endpoints
# =============================================================================

@mmm_bp.route('/session/<session_id>/performance', methods=['GET'])
def get_session_performance(session_id: str):
    """Get performance intelligence for a session."""
    try:
        from .mmm_performance import get_performance_storage, analyze_session

        storage = get_performance_storage()
        record = storage.get(session_id)

        if record:
            return jsonify({
                'success': True,
                'performance': record,
                'session_id': session_id,
                'source': 'persistent_storage',
            })

        # Fallback: compute live for running sessions
        from .mmm_storage import get_storage
        sess_storage = get_storage()
        session = sess_storage.get_session(session_id)
        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        live_record = analyze_session(session)
        return jsonify({
            'success': True,
            'performance': live_record,
            'session_id': session_id,
            'source': 'live_session',
        })

    except Exception as e:
        log.exception(f"Failed to get performance for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/performance/summary', methods=['GET'])
def get_performance_summary():
    """Get aggregated performance summary across all sessions."""
    try:
        from .mmm_performance import get_performance_storage

        storage = get_performance_storage()
        summary = storage.get_summary()
        history = storage.get_all(limit=50)

        return jsonify({
            'success': True,
            'summary': summary,
            'history': history,
        })

    except Exception as e:
        log.exception("Failed to get performance summary")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Perpetual Futures Delta Hedge Endpoints (§26.13)
# =============================================================================

@mmm_bp.route('/session/<session_id>/hedge/status', methods=['GET'])
def get_hedge_status(session_id: str):
    """
    GET /api/mmm/session/<session_id>/hedge/status

    Returns current perp hedge state, position, P&L, and config.
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}',
            }), 404

        from .mmm_perp_hedge import get_perp_summary, is_perp_hedge_enabled

        params = session.get('params', {})
        return jsonify({
            'success': True,
            'session_id': session_id,
            'hedge': get_perp_summary(session),
            'config': {
                'perp_hedge_enabled': params.get('perp_hedge_enabled', False),
                'perp_hedge_delta_threshold': params.get('perp_hedge_delta_threshold', 0.02),
                'perp_hedge_ratio': params.get('perp_hedge_ratio', 1.0),
                'perp_hedge_rebalance_band': params.get('perp_hedge_rebalance_band', 0.005),
                'perp_hedge_max_lots': params.get('perp_hedge_max_lots', 50),
                'perp_hedge_cooldown_sec': params.get('perp_hedge_cooldown_sec', 30),
            },
        })

    except Exception as e:
        log.exception(f"Failed to get hedge status for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>/hedge/toggle', methods=['POST'])
def toggle_hedge(session_id: str):
    """
    POST /api/mmm/session/<session_id>/hedge/toggle

    Enable or disable perp delta hedging. Hot-reloadable param.

    Request body (optional):
        { "enabled": true/false }
    If omitted, toggles current state.
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}',
            }), 404

        data = request.get_json(silent=True) or {}
        params = session.get('params', {})
        current = params.get('perp_hedge_enabled', False)
        new_value = data.get('enabled', not current)

        params['perp_hedge_enabled'] = bool(new_value)
        storage.update_session(session_id, {'params': params})

        # Also update monitor's live session if running
        # M-11 note: We update storage above. The monitor reloads params from
        # storage at heartbeat start (H-10 fix), so this in-memory update is
        # only for immediate effect within the current heartbeat interval.
        monitor = get_monitor(session_id)
        if monitor and hasattr(monitor, 'session'):
            monitor.session.get('params', {})['perp_hedge_enabled'] = bool(new_value)

        from .mmm_websocket import emit_params_changed
        emit_params_changed(session_id, {'perp_hedge_enabled': bool(new_value)})

        action = 'enabled' if new_value else 'disabled'
        log.info(f"Perp hedge {action} for session {session_id}")

        return jsonify({
            'success': True,
            'message': f'Perp hedge {action}',
            'perp_hedge_enabled': bool(new_value),
        })

    except Exception as e:
        log.exception(f"Failed to toggle hedge for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>/hedge/close', methods=['POST'])
def close_hedge(session_id: str):
    """
    POST /api/mmm/session/<session_id>/hedge/close

    Manually close the entire perp hedge position.
    The session continues running — only the perp is closed.

    Request body (optional):
        { "reason": "manual close" }
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}',
            }), 404

        perp_lots = session.get('perp_hedge', {}).get('lots', 0)
        if perp_lots == 0:
            return jsonify({
                'success': True,
                'message': 'No perp position to close',
                'lots_closed': 0,
            })

        # Need to execute async close via the monitor's event loop
        monitor = get_monitor(session_id)
        if not monitor or not monitor.is_running:
            return jsonify({
                'success': False,
                'error': 'Session monitor not running — cannot execute close',
            }), 400

        import asyncio
        from .mmm_perp_hedge import close_all_perp

        data = request.get_json(silent=True) or {}
        reason = data.get('reason', 'Manual hedge close via API')

        loop = getattr(monitor, '_loop', None)
        if not loop or loop.is_closed():
            return jsonify({
                'success': False,
                'error': 'Monitor event loop not available',
            }), 500

        future = asyncio.run_coroutine_threadsafe(
            close_all_perp(monitor.session, monitor.executor, reason),
            loop,
        )
        from concurrent.futures import TimeoutError as FuturesTimeoutError
        try:
            result = future.result(timeout=30)
        except (FuturesTimeoutError, TimeoutError):
            # The async call may take long if exchange API is slow.
            future.cancel()
            log.warning(f"[{session_id}] hedge/close timed out after 30s")
            return jsonify({
                'success': False,
                'error': 'Hedge close timed out after 30s — the exchange API may be slow. Try again.',
            }), 504

        if result.get('success'):
            storage.save_session(monitor.session)
            return jsonify({
                'success': True,
                'message': f"Perp position closed: {result.get('lots_closed', 0)} lots",
                'lots_closed': result.get('lots_closed', 0),
                'fill_price': result.get('fill_price', 0),
                'realized_pnl': result.get('realized_pnl', 0),
            })
        else:
            return jsonify({
                'success': False,
                'error': f"Close failed: {result.get('reason', 'unknown')}",
            }), 500

    except Exception as e:
        log.exception(f"Failed to close hedge for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =========================================================================
# AGGREGATE METRICS & SYSTEM HEALTH
# =========================================================================

@mmm_bp.route('/metrics/aggregate', methods=['GET'])
def get_aggregate_metrics():
    """
    Return aggregated metrics across all MMM sessions.
    
    Provides system-wide observability:
    - Active session count and health grades
    - Watchdog status and cooldown states
    - Circuit breaker summary per session
    - Total restarts and anomalies
    
    Returns:
        JSON with aggregate health metrics
    """
    try:
        from .mmm_watchdog import MMMWatchdog
        from .mmm_monitor import get_monitor
        
        storage = get_storage()
        sessions = storage.list_sessions()
        
        # Collect per-session health data
        session_health = []
        total_restarts = 0
        grade_counts = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0, 'N/A': 0}
        circuit_open_count = 0
        
        for session in sessions:
            sid = session.get('session_id', session.get('id', ''))
            status = session.get('strategy_status', 'UNKNOWN')
            restarts = session.get('_watchdog_restarts', 0)
            total_restarts += restarts
            
            # Get live health if monitor is running
            monitor = None
            try:
                monitor = get_monitor(sid)
            except (KeyError, AttributeError):
                pass
            
            health_summary = None
            grade = 'N/A'
            circuit_summary = None
            
            if monitor:
                # Get heartbeat health
                health = getattr(monitor, '_health', None)
                if health:
                    try:
                        health_summary = health.summary()
                        grade = health_summary.get('grade', 'N/A')
                    except Exception:
                        pass
                
                # Get circuit breaker status
                circuit = getattr(monitor, '_circuit', None)
                if circuit:
                    try:
                        circuit_summary = circuit.summary()
                        if circuit_summary.get('is_open'):
                            circuit_open_count += 1
                    except Exception:
                        pass
            else:
                # Use persisted health data for stopped sessions
                grade = session.get('_health_grade', 'N/A')
            
            grade_counts[grade] = grade_counts.get(grade, 0) + 1
            
            session_health.append({
                'session_id': sid,
                'status': status,
                'grade': grade,
                'restarts': restarts,
                'monitor_active': monitor is not None and getattr(monitor, 'is_running', False),
                'circuit_open': circuit_summary.get('is_open') if circuit_summary else False,
                'health_updated_at': session.get('_health_summary', {}).get('updated_at') if not monitor else None,
            })
        
        # Watchdog status
        watchdog = MMMWatchdog.get_instance()
        watchdog_status = watchdog.status()
        
        # Compute overall system health
        active_sessions = [s for s in session_health if s['status'] == 'RUNNING']
        healthy_sessions = [s for s in active_sessions if s['grade'] in ('A', 'B')]
        
        if not active_sessions:
            system_health = 'IDLE'
        elif len(healthy_sessions) == len(active_sessions) and circuit_open_count == 0:
            system_health = 'HEALTHY'
        elif len(healthy_sessions) >= len(active_sessions) * 0.5:
            system_health = 'DEGRADED'
        else:
            system_health = 'CRITICAL'
        
        return jsonify({
            'success': True,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'system_health': system_health,
            'summary': {
                'total_sessions': len(sessions),
                'active_sessions': len(active_sessions),
                'healthy_sessions': len(healthy_sessions),
                'circuits_open': circuit_open_count,
                'total_watchdog_restarts': total_restarts,
                'grade_distribution': grade_counts,
            },
            'watchdog': watchdog_status,
            'sessions': session_health,
        })
        
    except Exception as e:
        log.exception("Failed to get aggregate metrics")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/emergency/stop-all', methods=['POST'])
def emergency_stop_all():
    """
    Emergency procedure: Stop all running MMM sessions.
    
    Use this when:
    - System-wide anomaly detected
    - Manual intervention required across all sessions
    - Preparing for maintenance
    
    Returns:
        JSON with list of stopped sessions
    """
    try:
        from .mmm_monitor import get_monitor
        from .mmm_activity import log_activity
        
        storage = get_storage()
        data = request.get_json(silent=True) or {}
        reason = data.get('reason', 'Emergency stop via API')
        
        stopped = []
        failed = []
        
        # Get all running sessions
        sessions = storage.list_sessions()
        running_sessions = [s for s in sessions if s.get('strategy_status') == 'RUNNING']
        
        for session in running_sessions:
            sid = session.get('session_id', session.get('id', ''))
            try:
                monitor = get_monitor(sid)
                if monitor and monitor.is_running:
                    monitor.stop(reason)
                    session['strategy_status'] = 'PAUSED'
                    session['_emergency_stop'] = {
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'reason': reason,
                    }
                    storage.save_session(session)
                    stopped.append(sid)
                    log_activity('emergency', f'🚨 Emergency stop: {reason}', sid, 'critical')
            except Exception as e:
                log.error(f"Failed to stop {sid}: {e}")
                failed.append({'session_id': sid, 'error': str(e)})
        
        # Log system-wide activity
        log_activity(
            'emergency',
            f'🚨 EMERGENCY STOP ALL: {len(stopped)} sessions stopped, {len(failed)} failed',
            None,
            'critical'
        )
        
        return jsonify({
            'success': True,
            'stopped_count': len(stopped),
            'stopped_sessions': stopped,
            'failed_count': len(failed),
            'failed_sessions': failed,
            'reason': reason,
        })
        
    except Exception as e:
        log.exception("Emergency stop-all failed")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/emergency/health-check', methods=['GET'])
def emergency_health_check():
    """
    Deep system health check for emergency situations.
    
    Checks:
    - Database connectivity
    - Exchange API reachability
    - WebSocket health
    - Watchdog thread status
    - Memory usage
    
    Returns:
        JSON with detailed health status
    """
    try:
        import psutil
        from .mmm_watchdog import MMMWatchdog
        from .mmm_websocket import get_ws_health
        
        checks = {}
        
        # 1. Storage health
        try:
            storage = get_storage()
            sessions = storage.list_sessions()
            checks['storage'] = {
                'status': 'OK',
                'session_count': len(sessions),
            }
        except Exception as e:
            checks['storage'] = {'status': 'ERROR', 'error': str(e)}
        
        # 2. Watchdog health
        try:
            watchdog = MMMWatchdog.get_instance()
            wd_status = watchdog.status()
            checks['watchdog'] = {
                'status': 'OK' if wd_status.get('running') else 'STOPPED',
                **wd_status,
            }
        except Exception as e:
            checks['watchdog'] = {'status': 'ERROR', 'error': str(e)}
        
        # 3. WebSocket health
        try:
            ws_health = get_ws_health()
            checks['websocket'] = {
                'status': 'OK' if ws_health.get('connected', 0) > 0 else 'IDLE',
                **ws_health,
            }
        except Exception as e:
            checks['websocket'] = {'status': 'UNKNOWN', 'error': str(e)}
        
        # 4. Memory usage
        try:
            process = psutil.Process()
            mem_info = process.memory_info()
            checks['memory'] = {
                'status': 'OK' if mem_info.rss < 2 * 1024 * 1024 * 1024 else 'HIGH',  # 2GB threshold
                'rss_mb': round(mem_info.rss / (1024 * 1024), 1),
                'vms_mb': round(mem_info.vms / (1024 * 1024), 1),
            }
        except Exception as e:
            checks['memory'] = {'status': 'UNKNOWN', 'error': str(e)}
        
        # 5. Thread count
        try:
            import threading
            thread_count = threading.active_count()
            checks['threads'] = {
                'status': 'OK' if thread_count < 100 else 'HIGH',
                'count': thread_count,
            }
        except Exception as e:
            checks['threads'] = {'status': 'UNKNOWN', 'error': str(e)}
        
        # Overall status
        all_ok = all(c.get('status') in ('OK', 'IDLE') for c in checks.values())
        any_error = any(c.get('status') == 'ERROR' for c in checks.values())
        
        if any_error:
            overall = 'ERROR'
        elif all_ok:
            overall = 'HEALTHY'
        else:
            overall = 'DEGRADED'
        
        return jsonify({
            'success': True,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'overall_status': overall,
            'checks': checks,
        })
        
    except Exception as e:
        log.exception("Emergency health check failed")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/emergency/pause-all', methods=['POST'])
def emergency_pause_all():
    """
    Emergency procedure: Pause all running MMM sessions without stopping monitors.
    
    Unlike stop-all which fully stops the monitor, this keeps heartbeats running
    but prevents new order placement. Useful for temporary market conditions.
    
    Returns:
        JSON with list of paused sessions
    """
    try:
        from .mmm_activity import log_activity
        
        storage = get_storage()
        data = request.get_json(silent=True) or {}
        reason = data.get('reason', 'Emergency pause via API')
        
        paused = []
        already_paused = []
        failed = []
        
        sessions = storage.list_sessions()
        running_sessions = [s for s in sessions if s.get('strategy_status') == 'RUNNING']
        
        for session in running_sessions:
            sid = session.get('session_id', session.get('id', ''))
            try:
                session['strategy_status'] = 'PAUSED'
                session['_emergency_pause'] = {
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'reason': reason,
                }
                storage.save_session(session)
                paused.append(sid)
                log_activity('emergency', f'⏸️ Emergency pause: {reason}', sid, 'warning')
            except Exception as e:
                log.error(f"Failed to pause {sid}: {e}")
                failed.append({'session_id': sid, 'error': str(e)})
        
        # Log system-wide activity
        log_activity(
            'emergency',
            f'⏸️ EMERGENCY PAUSE ALL: {len(paused)} sessions paused',
            None,
            'warning'
        )
        
        return jsonify({
            'success': True,
            'paused_count': len(paused),
            'paused_sessions': paused,
            'already_paused': len(already_paused),
            'failed_count': len(failed),
            'failed_sessions': failed,
            'reason': reason,
        })
        
    except Exception as e:
        log.exception("Emergency pause-all failed")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/emergency/close-all-positions', methods=['POST'])
def emergency_close_all_positions():
    """
    Emergency procedure: Force close all positions across all sessions.
    
    WARNING: This uses market/taker orders to close positions immediately.
    Use only in true emergencies when position risk must be eliminated.
    
    Request body:
        reason: Reason for emergency close (required)
        session_ids: Optional list of specific sessions; omit for all
        dry_run: If true, only report what would be closed (default false)
    
    Returns:
        JSON with positions closed and P&L impact
    """
    import asyncio
    
    try:
        from .mmm_monitor import get_monitor, get_all_monitors
        from .mmm_activity import log_activity
        
        storage = get_storage()
        data = request.get_json(silent=True) or {}
        reason = data.get('reason')
        session_ids = data.get('session_ids')  # Optional filter
        dry_run = data.get('dry_run', False)
        
        if not reason:
            return jsonify({
                'success': False, 
                'error': 'reason is required for emergency close',
            }), 400
        
        results = []
        total_positions_closed = 0
        total_realized_pnl = 0.0
        
        # Get target sessions
        if session_ids:
            monitors_to_close = {
                sid: get_monitor(sid) 
                for sid in session_ids 
                if get_monitor(sid)
            }
        else:
            monitors_to_close = get_all_monitors()
        
        if dry_run:
            # Just report what would be closed
            for sid, monitor in monitors_to_close.items():
                session = monitor.session if monitor else storage.get_session(sid)
                if not session:
                    continue
                
                positions = []
                for side_key in ['ce', 'pe']:
                    side = session.get(side_key, {})
                    for pos_type in ['entry', 'adj1', 'adj2', 'adj3']:
                        pos = side.get(pos_type, {})
                        if pos.get('open') and pos.get('lots', 0) > 0:
                            positions.append({
                                'side': side_key,
                                'type': pos_type,
                                'strike': pos.get('strike'),
                                'lots': pos.get('lots'),
                            })
                
                if positions:
                    results.append({
                        'session_id': sid,
                        'positions_to_close': positions,
                        'position_count': len(positions),
                    })
            
            return jsonify({
                'success': True,
                'dry_run': True,
                'sessions_affected': len(results),
                'results': results,
                'reason': reason,
            })
        
        # Actual close operation
        async def close_session_positions(sid: str, monitor):
            nonlocal total_positions_closed, total_realized_pnl
            
            if not monitor:
                return {'session_id': sid, 'error': 'Monitor not found'}
            
            try:
                # Use the monitor's internal close method
                await monitor._auto_close_all(
                    f'EMERGENCY: {reason}',
                    emergency=True,
                )
                
                # Count closed positions
                session = monitor.session
                positions_closed = []
                for side_key in ['ce', 'pe']:
                    side = session.get(side_key, {})
                    for pos_type in ['entry', 'adj1', 'adj2', 'adj3']:
                        pos = side.get(pos_type, {})
                        # Check if position was just closed
                        if not pos.get('open') and pos.get('close_time'):
                            positions_closed.append(f"{side_key}_{pos_type}")
                
                return {
                    'session_id': sid,
                    'success': True,
                    'positions_closed': positions_closed,
                }
                
            except Exception as e:
                log.error(f"Failed to close positions for {sid}: {e}")
                return {
                    'session_id': sid,
                    'success': False,
                    'error': str(e),
                }
        
        # Execute closures
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            tasks = [
                close_session_positions(sid, monitor) 
                for sid, monitor in monitors_to_close.items()
            ]
            results = loop.run_until_complete(asyncio.gather(*tasks))
        finally:
            loop.close()
        
        # Log system-wide
        successful = [r for r in results if r.get('success')]
        failed = [r for r in results if not r.get('success')]
        
        log_activity(
            'emergency',
            f'🚨 EMERGENCY CLOSE ALL POSITIONS: {len(successful)} sessions closed, reason: {reason}',
            None,
            'critical'
        )
        
        return jsonify({
            'success': True,
            'dry_run': False,
            'sessions_closed': len(successful),
            'sessions_failed': len(failed),
            'results': results,
            'reason': reason,
        })
        
    except Exception as e:
        log.exception("Emergency close-all-positions failed")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/emergency/reset-circuit/<session_id>', methods=['POST'])
def emergency_reset_circuit(session_id: str):
    """
    Emergency procedure: Manually reset a session's circuit breaker to CLOSED.
    
    Use when:
    - Exchange API is confirmed healthy but breaker is stuck OPEN
    - After resolving a known exchange outage
    - Manual recovery from transient failures
    
    Returns:
        JSON with circuit state before/after reset
    """
    try:
        from .mmm_monitor import get_monitor
        from .mmm_activity import log_activity
        
        data = request.get_json(silent=True) or {}
        reason = data.get('reason', 'Manual circuit reset via API')
        
        monitor = get_monitor(session_id)
        if not monitor:
            return jsonify({
                'success': False,
                'error': f'Session not found or not running: {session_id}',
            }), 404
        
        # Access the circuit breaker
        circuit = getattr(monitor, '_circuit', None)
        if not circuit:
            return jsonify({
                'success': False,
                'error': 'Circuit breaker not available for this session',
            }), 400
        
        # Reset the circuit
        reset_info = circuit.reset()
        
        log_activity(
            'emergency',
            f'🔄 Circuit breaker reset: {reset_info["previous_state"]} → CLOSED ({reason})',
            session_id,
            'warning'
        )
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'reason': reason,
            **reset_info,
            'new_circuit_state': circuit.summary(),
        })
        
    except Exception as e:
        log.exception(f"Emergency circuit reset failed for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/session/<session_id>/clear-backoff', methods=['POST'])
def clear_session_backoff(session_id: str):
    """
    Clear watchdog exponential backoff for a session.
    
    Use after manual intervention to allow immediate restart if needed.
    
    Returns:
        JSON with success status
    """
    try:
        from .mmm_watchdog import MMMWatchdog
        
        storage = get_storage()
        session = storage.get_session(session_id)
        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404
        
        # Clear watchdog backoff
        watchdog = MMMWatchdog.get_instance()
        watchdog.clear_backoff(session_id)
        
        # Also reset restart count if requested
        data = request.get_json(silent=True) or {}
        if data.get('reset_restart_count'):
            session['_watchdog_restarts'] = 0
            storage.save_session(session)
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': 'Backoff cleared',
            'restart_count_reset': data.get('reset_restart_count', False),
        })
        
    except Exception as e:
        log.exception(f"Failed to clear backoff for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/audit/trail', methods=['GET'])
def get_audit_trail():
    """
    Query the MMM activity/audit trail with filtering.
    
    Query parameters:
        session_id: Filter by session ID (optional)
        severity: Filter by severity level: info, warning, error, critical (optional)
        type: Filter by activity type (optional)
        since: ISO timestamp to filter events after (optional)
        limit: Max number of results (default 100, max 500)
    
    Returns:
        JSON with filtered audit trail entries
    """
    try:
        from .mmm_activity import get_activity_log
        
        activity_log = get_activity_log()
        
        # Parse query params
        session_id = request.args.get('session_id')
        severity = request.args.get('severity')
        activity_type = request.args.get('type')
        since = request.args.get('since')
        limit = min(int(request.args.get('limit', 100)), 500)
        
        # Use get_recent which supports session_id and severity filtering
        activities = activity_log.get_recent(
            limit=limit,
            session_id=session_id,
            severity=severity,
        )
        
        # Apply additional filters not supported by get_recent
        filtered = activities
        
        if activity_type:
            types = activity_type.split(',')
            filtered = [a for a in filtered if a.get('type') in types]
        
        if since:
            try:
                since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
                filtered = [a for a in filtered if datetime.fromisoformat(
                    a.get('timestamp', '').replace('Z', '+00:00')
                ) >= since_dt]
            except (ValueError, TypeError):
                pass
        
        # Already sorted newest first by get_recent
        
        return jsonify({
            'success': True,
            'count': len(filtered),
            'activities': filtered,
            'filters_applied': {
                'session_id': session_id,
                'severity': severity,
                'type': activity_type,
                'since': since,
                'limit': limit,
            },
        })
        
    except Exception as e:
        log.exception("Failed to get audit trail")
        return jsonify({'success': False, 'error': str(e)}), 500


@mmm_bp.route('/audit/export', methods=['GET'])
def export_audit_trail():
    """
    Export audit trail as JSON for external analysis.
    
    Query parameters:
        session_id: Filter by session ID (optional)
        include_sessions: Include session state snapshots (default false)
    
    Returns:
        JSON export file for download
    """
    try:
        from .mmm_activity import get_activity_log
        from .mmm_watchdog import MMMWatchdog
        
        activity_log = get_activity_log()
        storage = get_storage()
        
        session_id = request.args.get('session_id')
        include_sessions = request.args.get('include_sessions', 'false').lower() == 'true'
        
        # Get all activities (up to 500 which is MAX_ACTIVITIES)
        activities = activity_log.get_recent(limit=500, session_id=session_id)
        
        export_data = {
            'export_timestamp': datetime.now(timezone.utc).isoformat(),
            'export_type': 'mmm_audit_trail',
            'version': '1.0',
            'activity_count': len(activities),
            'activities': activities,
        }
        
        # Include watchdog status
        watchdog = MMMWatchdog.get_instance()
        export_data['watchdog_status'] = watchdog.status()
        
        # Include session states if requested
        if include_sessions:
            sessions = storage.list_sessions()
            if session_id:
                sessions = [s for s in sessions if s.get('session_id') == session_id]
            
            # Remove sensitive data
            for s in sessions:
                s.pop('api_key', None)
                s.pop('api_secret', None)
            
            export_data['sessions'] = sessions
        
        response = make_response(json.dumps(export_data, indent=2, default=str))
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Disposition'] = f'attachment; filename=mmm_audit_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        return response
        
    except Exception as e:
        log.exception("Failed to export audit trail")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# P&L Curve — on-demand portfolio landscape endpoint
# =============================================================================

@mmm_bp.route('/session/<session_id>/pnl-curve', methods=['GET'])
def get_pnl_curve(session_id: str):
    """
    Compute and return the portfolio P&L landscape for chart display.

    Uses the intrinsic-only model from BreakevenEngine: no live premium fetches,
    fast (~1ms). Called on-demand when the Risk tab opens or user clicks Refresh.

    Query parameters:
        n_points: Number of curve sample points (default 120, max 300)

    Returns:
        curve_points: [{spot, pnl}, ...] across the scan range
        strike_markers: [{strike, side, lots, entry_premium, pos_type}, ...]
        breakeven: last known breakeven result from session
        gamma: last known gamma result from session (or null)
        spot_price: spot used for the curve
        scan_range_pct: how wide the chart is (% of spot, each side)
    """
    try:
        from .mmm_breakeven_engine import get_breakeven_engine

        # --- 1. Load live session (prefer monitor's in-memory state) ---
        monitor = get_monitor(session_id)
        if monitor and getattr(monitor, '_running', False) and hasattr(monitor, 'session'):
            session = monitor.session
        else:
            storage = get_storage()
            session = storage.get_session(session_id)

        if not session:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        params = session.get('params', {})

        # --- 2. Determine spot price ---
        # Priority: breakeven_result.spot → gamma_result.spot → _regime_spot_price
        # This ensures the endpoint works even when breakeven/gamma engines are disabled.
        be_result = session.get('_breakeven_result') or {}
        gamma_result = session.get('_gamma_result') or {}
        spot_price = (
            be_result.get('spot_price') or
            gamma_result.get('spot_price') or
            session.get('_regime_spot_price') or
            0.0
        )
        if spot_price <= 0:
            return jsonify({'success': False, 'error': 'No spot price available — session not yet started or no heartbeat'}), 422

        # --- 3. Collect positions ---
        be_engine = get_breakeven_engine()
        positions = be_engine._collect_open_positions(session)

        if not positions:
            return jsonify({
                'success': True,
                'session_id': session_id,
                'spot_price': spot_price,
                'curve_points': [],
                'strike_markers': [],
                'breakeven': be_result or None,
                'gamma': session.get('_gamma_result') or None,
                'scan_range_pct': 0.0,
                'positions_count': 0,
            })

        # --- 4. Compute scan range (use engine formula + floor at 15%) ---
        engine_range = be_engine._compute_scan_range(spot_price, positions, params)
        min_range = spot_price * 0.15  # always show at least ±15% for useful chart
        scan_range = max(engine_range, min_range)
        scan_range_pct = round(scan_range / spot_price * 100.0, 2)

        # --- 5. Generate curve points ---
        n_points = min(int(request.args.get('n_points', 120)), 300)
        if n_points < 20:
            n_points = 20

        spot_lo = max(spot_price - scan_range, 1.0)
        spot_hi = spot_price + scan_range
        step = (spot_hi - spot_lo) / (n_points - 1)

        curve_points = []
        for i in range(n_points):
            s = spot_lo + i * step
            pnl = be_engine._compute_pnl_at_spot(positions, s, session)
            curve_points.append({
                'spot': round(s, 2),
                'pnl': round(pnl, 4),
            })

        # --- 6. Zero-crossing breakeven from curve (works even when BE engine disabled) ---
        computed_breakeven = None
        if not be_result:
            # Find all sign-change intervals and interpolate exact zero crossings
            zero_crossings = []
            for i in range(len(curve_points) - 1):
                p0 = curve_points[i]
                p1 = curve_points[i + 1]
                if p0['pnl'] * p1['pnl'] <= 0 and (p0['pnl'] != 0 or p1['pnl'] != 0):
                    # Linear interpolation
                    d = p1['pnl'] - p0['pnl']
                    cross = p0['spot'] - p0['pnl'] * (p1['spot'] - p0['spot']) / d if d != 0 else (p0['spot'] + p1['spot']) / 2
                    zero_crossings.append(round(cross, 2))
            if len(zero_crossings) >= 2:
                computed_breakeven = {
                    'lower_breakeven': min(zero_crossings),
                    'upper_breakeven': max(zero_crossings),
                    'source': 'curve_zero_crossing',
                }
            elif len(zero_crossings) == 1:
                # Only one side (deep ITM or all profit) — still useful
                zc = zero_crossings[0]
                if zc < spot_price:
                    computed_breakeven = {'lower_breakeven': zc, 'upper_breakeven': None, 'source': 'curve_zero_crossing'}
                else:
                    computed_breakeven = {'lower_breakeven': None, 'upper_breakeven': zc, 'source': 'curve_zero_crossing'}

        # --- 7. P&L at spot from curve (nearest point) ---
        pnl_at_spot = None
        if curve_points:
            nearest = min(curve_points, key=lambda p: abs(p['spot'] - spot_price))
            pnl_at_spot = nearest['pnl']

        # --- 8. Strike markers (for vertical reference lines on chart) ---
        strike_markers = []
        for pos in positions:
            strike_markers.append({
                'strike': pos['strike'],
                'side': 'CE' if pos['option_type'] == 'call' else 'PE',
                'lots': pos['lots'],
                'entry_premium': pos['entry_premium'],
                'pos_type': pos.get('pos_type', 'unknown'),
            })

        return jsonify({
            'success': True,
            'session_id': session_id,
            'spot_price': spot_price,
            'curve_points': curve_points,
            'strike_markers': strike_markers,
            'breakeven': be_result or None,
            'computed_breakeven': computed_breakeven,
            'pnl_at_spot': pnl_at_spot,
            'gamma': session.get('_gamma_result') or None,
            'scan_range_pct': scan_range_pct,
            'positions_count': len(positions),
            'computed_at': datetime.now(timezone.utc).isoformat(),
        })

    except Exception as e:
        log.exception(f"Failed to compute P&L curve for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ─────────────────────────────────────────────────────────────────────────────
# Trade Audit API  (position_audit_log + session_event_log)
# ─────────────────────────────────────────────────────────────────────────────

@mmm_bp.route('/session/<session_id>/audit/trades', methods=['GET'])
def get_trade_audit(session_id: str):
    """
    GET /api/mmm/session/<id>/audit/trades
    ?side=CE&event_type=ADJUSTMENT&page=1&limit=100

    Returns paginated rows from position_audit_log for a session.
    """
    from .mmm_audit_log import get_audit_log
    side        = request.args.get('side')
    event_type  = request.args.get('event_type')
    page        = max(1, int(request.args.get('page', 1)))
    limit       = min(500, max(1, int(request.args.get('limit', 100))))
    rows = get_audit_log().query_session(session_id, side, event_type, page, limit)
    return jsonify({'rows': rows, 'page': page, 'limit': limit, 'count': len(rows)})


@mmm_bp.route('/session/<session_id>/audit/strike_summary', methods=['GET'])
def get_strike_summary_audit(session_id: str):
    """
    GET /api/mmm/session/<id>/audit/strike_summary
    ?include_unrealized=true

    Returns per-(strike, option_type) aggregated P&L, qty, status.
    Optionally fetches live premiums for ACTIVE rows.
    """
    from .mmm_audit_log import get_audit_log
    summary = get_audit_log().get_strike_summary(session_id)

    if request.args.get('include_unrealized') == 'true':
        storage = get_storage()
        session = storage.get_session(session_id)
        if session:
            try:
                from .mmm_executor import get_executor
                from .mmm_initializer import get_initializer
                executor = get_executor()
                initializer = get_initializer()
                params = session.get('params', {})
                expiry = params.get('expiry', '')

                async def _fetch_all():
                    results = {}
                    for row in summary:
                        if row.get('status') == 'ACTIVE' and (row.get('open_qty') or 0) > 0:
                            try:
                                ot = 'call' if row['option_type'] == 'CE' else 'put'
                                sym = initializer.build_symbol(ot, 'BTC', row['strike'], expiry)
                                mid = await executor.get_mid_price(sym)
                                results[(row['strike'], row['option_type'])] = mid
                            except Exception:
                                pass
                    return results

                premiums = _run_async(_fetch_all())
                for row in summary:
                    key = (row.get('strike'), row.get('option_type'))
                    mid = premiums.get(key)
                    if mid and mid > 0:
                        row['current_premium'] = round(mid, 2)
                        avg_sell = row.get('avg_sell_price') or 0
                        open_qty = row.get('open_qty') or 0
                        row['unrealized_pnl_usd'] = round(
                            (avg_sell - mid) * open_qty * 0.001, 6
                        )
            except Exception as e:
                log.warning('Could not fetch unrealized premiums for strike summary: %s', e)

    return jsonify({'summary': summary})


@mmm_bp.route('/session/<session_id>/audit/pnl', methods=['GET'])
def get_pnl_attribution_audit(session_id: str):
    """
    GET /api/mmm/session/<id>/audit/pnl

    P&L breakdown by event_type. Source of truth: must equal session['realized_pnl'].
    """
    from .mmm_audit_log import get_audit_log
    return jsonify(get_audit_log().get_pnl_attribution(session_id))


@mmm_bp.route('/session/<session_id>/audit/reconcile', methods=['GET'])
def reconcile_audit_endpoint(session_id: str):
    """
    GET /api/mmm/session/<id>/audit/reconcile

    Compare audit log totals against live session state.
    Returns { is_clean, pnl_ok, pnl_delta, position_discrepancies }.
    HTTP 200 if clean, 409 if discrepancy found.
    """
    from .mmm_audit_reconciler import reconcile_session
    storage = get_storage()
    session = storage.get_session(session_id)
    if not session:
        return jsonify({'success': False, 'error': f'Session not found: {session_id}'}), 404
    result = reconcile_session(session_id, session)
    return jsonify(result), 200


@mmm_bp.route('/session/<session_id>/audit/events', methods=['GET'])
def get_session_events_audit(session_id: str):
    """
    GET /api/mmm/session/<id>/audit/events
    ?category=REGIME&severity=WARN&limit=100

    Returns operational event log rows for a session.
    """
    from .mmm_audit_log import get_event_log
    category = request.args.get('category')
    severity = request.args.get('severity')
    limit    = min(500, max(1, int(request.args.get('limit', 100))))
    rows = get_event_log().query_session(session_id, category, severity, limit)
    return jsonify({'events': rows, 'count': len(rows)})


@mmm_bp.route('/session/<session_id>/audit/execution-events', methods=['GET'])
def get_session_execution_events(session_id: str):
    """
    GET /api/mmm/session/<id>/audit/execution-events
    ?limit=100

    Returns pre-fill execution intent events (ORDER_INTENT, ORDER_CONFIRMED,
    EXIT_ROUND_START, EXIT_ROUND_END) for a session.
    """
    from .mmm_audit_log import get_event_log
    limit = min(500, max(1, int(request.args.get('limit', 100))))
    rows = get_event_log().query_session(session_id, category='EXECUTION_INTENT', limit=limit)
    return jsonify({'events': rows, 'count': len(rows)})
