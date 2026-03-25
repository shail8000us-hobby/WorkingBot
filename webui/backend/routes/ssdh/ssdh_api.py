"""
SSDH API — Flask Blueprint

REST API endpoints for the SSDH engine.
Registered in app.py as: app.register_blueprint(ssdh_bp, url_prefix='/api/ssdh')

Endpoints:
  GET  /api/ssdh/sessions              → list all sessions
  GET  /api/ssdh/sessions/<id>         → get session state
  POST /api/ssdh/sessions/start        → create + start session (2-phase: preview first)
  POST /api/ssdh/sessions/<id>/stop    → graceful stop
  POST /api/ssdh/sessions/<id>/kill    → emergency kill switch
  GET  /api/ssdh/presets               → list presets
  GET  /api/ssdh/health                → engine health check

Two-phase start:
  POST /api/ssdh/sessions/start {confirm: false}  → returns preview only
  POST /api/ssdh/sessions/start {confirm: true}   → runs entry + starts monitor

Created: March 21, 2026
"""

import asyncio
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from flask import Blueprint, request, jsonify

log = logging.getLogger('ssdh_api')

ssdh_bp = Blueprint('ssdh', __name__)

# Global executor instance (shared — created fresh client per call)
_executor = None
_executor_lock = threading.Lock()


def _get_executor():
    global _executor
    with _executor_lock:
        if _executor is None:
            from .ssdh_executor import SSDHExecutor
            _executor = SSDHExecutor()
        return _executor


# =============================================================================
# GET /api/ssdh/sessions
# =============================================================================

@ssdh_bp.route('/sessions', methods=['GET'])
def list_sessions():
    """List all sessions with summary."""
    try:
        from .ssdh_state import load_sessions
        from .ssdh_monitor import get_monitor

        sessions = load_sessions()
        result   = []
        for sid, s in sessions.items():
            monitor = get_monitor(sid)
            result.append({
                'session_id':  sid,
                'status':      s.get('status'),
                'strategy':    s.get('strategy'),
                'net_pnl':     s.get('net_pnl', 0.0),
                'realized_pnl':s.get('realized_pnl', 0.0),
                'total_fees':  s.get('total_fees', 0.0),
                'created_at':  s.get('created_at'),
                'started_at':  s.get('started_at'),
                'closed_at':   s.get('closed_at'),
                'close_reason':s.get('close_reason'),
                'is_live':     monitor is not None and monitor.is_running(),
            })
        result.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return jsonify({'sessions': result, 'count': len(result)})
    except Exception as e:
        log.exception("list_sessions error: %s", e)
        return jsonify({'error': str(e)}), 500


# =============================================================================
# GET /api/ssdh/sessions/<session_id>
# =============================================================================

@ssdh_bp.route('/sessions/<session_id>', methods=['GET'])
def get_session(session_id: str):
    """Get full session state including positions."""
    try:
        from .ssdh_state import load_sessions
        from .ssdh_monitor import get_monitor

        sessions = load_sessions()
        if session_id not in sessions:
            return jsonify({'error': 'Session not found'}), 404

        session = sessions[session_id]
        monitor = get_monitor(session_id)

        # Attach live state from running monitor if available
        if monitor:
            live = monitor.get_session()
            if live:
                session = live

        return jsonify({'session': session, 'is_live': monitor is not None and monitor.is_running()})
    except Exception as e:
        log.exception("get_session error: %s", e)
        return jsonify({'error': str(e)}), 500


# =============================================================================
# POST /api/ssdh/sessions/start
# =============================================================================

@ssdh_bp.route('/sessions/start', methods=['POST'])
def start_session():
    """
    Two-phase session start.
    Phase 1 (confirm=false): validate params, scan chain, return preview.
    Phase 2 (confirm=true):  create session, run atomic entry, start monitor.
    """
    try:
        body    = request.get_json(force=True) or {}
        confirm = body.get('confirm', False)

        # ── Validate + merge params ──────────────────────────────────────────
        from .ssdh_config   import validate_params, compute_intraday_max_loss
        from .ssdh_presets  import apply_preset_to_params
        from .ssdh_state    import create_session, persist_session, STATUS_INITIALIZING
        from .ssdh_activity import log_activity

        preset_name = body.get('preset', 'ssdh')
        raw_params  = {k: v for k, v in body.items() if k not in ('confirm', 'preset')}

        merged = apply_preset_to_params(raw_params, preset_name)
        validated, errors = validate_params(merged)
        if errors:
            return jsonify({'error': 'Parameter validation failed', 'details': errors}), 400

        params = validated

        # ── Choose preview path: manual legs (chain picker) or auto-scan ─────
        raw_legs = body.get('legs')
        use_manual_legs = (raw_legs and isinstance(raw_legs, list) and len(raw_legs) >= 2)

        if use_manual_legs:
            # Chain-picker flow: legs are pre-selected by user from live chain
            required = ['expiry']
        else:
            # Auto-scan flow: needs premium targets to find strikes
            required = ['initial_lots', 'desired_ce_premium', 'desired_pe_premium',
                        'long_hedge_premium_target', 'expiry']

        missing = [k for k in required if k not in params]
        if missing:
            return jsonify({'error': f'Missing required params: {missing}'}), 400

        # ── Build entry preview ───────────────────────────────────────────────
        if use_manual_legs:
            preview = _build_preview_from_legs(raw_legs, params)
        else:
            preview = _build_preview(params)

        if not preview.get('ok'):
            return jsonify({'error': preview.get('error', 'Chain scan failed')}), 400

        # Compute max_loss if not provided
        if 'max_loss_amount' not in params:
            params['max_loss_amount'] = compute_intraday_max_loss(
                preview['theoretical_max_loss'],
                params.get('intraday_max_loss_multiplier', 1.75),
            )

        # ── Cross-engine conflict check ──────────────────────────────────────
        conflict = _check_cross_engine_conflict()
        if conflict:
            return jsonify({
                'error':    'Cross-engine conflict',
                'detail':   conflict,
                'warning':  True,
            }), 409

        if not confirm:
            # Return preview only
            return jsonify({
                'preview':    preview,
                'params':     params,
                'confirmed':  False,
                'message':    'Preview only. POST with confirm=true to execute entry.',
            })

        # ── Phase 2: Create session + run entry ──────────────────────────────
        session_id = _generate_session_id()
        session    = create_session(session_id, params)
        session['status'] = STATUS_INITIALIZING

        now = datetime.now(timezone.utc).isoformat()
        session['started_at'] = now
        session['session_end_time'] = _add_hours(now, params.get('session_window_hours', 4.0))

        # Store spot at entry for vega spike detector
        session['spot_at_entry'] = preview.get('spot_price')

        persist_session(session)
        log_activity('session_created', f"Session {session_id} created", session_id, 'info')

        # Build legs for AtomicEntryOrchestrator
        legs = _build_legs(preview, params, session_id)

        # Run entry in a background thread (it's async; Flask is sync greenlet)
        def _run_entry():
            try:
                loop = asyncio.DefaultEventLoopPolicy().new_event_loop()
                asyncio.set_event_loop(loop)

                from .ssdh_entry   import AtomicEntryOrchestrator
                from .ssdh_monitor import OPTMonitor, register_monitor
                from .ssdh_state   import STATUS_RUNNING, persist_session as _ps

                orchestrator = AtomicEntryOrchestrator()
                executor     = _get_executor()

                result = loop.run_until_complete(
                    orchestrator.execute_entry(session, executor, legs)
                )

                if result.get('success'):
                    session['status'] = STATUS_RUNNING
                    _ps(session)
                    monitor = OPTMonitor()
                    register_monitor(session_id, monitor)
                    monitor.start(session)
                    log_activity('session_started', f'Session {session_id} running', session_id, 'success')
                else:
                    from .ssdh_state import STATUS_ABORTED
                    session['status'] = STATUS_ABORTED
                    _ps(session)
                    log_activity('session_stopped',
                        f'Entry failed: {result.get("error")}', session_id, 'error')
                loop.close()
            except Exception as e:
                log.exception("[%s] _run_entry error: %s", session_id, e)
                try:
                    from .ssdh_state import STATUS_ABORTED
                    session['status'] = STATUS_ABORTED
                    persist_session(session)
                except Exception:
                    pass

        try:
            from eventlet.patcher import original as _ep_original
            RealThread = _ep_original('threading').Thread
        except (ImportError, AttributeError):
            import threading as _th
            RealThread = _th.Thread

        t = RealThread(target=_run_entry, daemon=True, name=f'ssdh_entry_{session_id}')
        t.start()

        return jsonify({
            'session_id': session_id,
            'status':     'INITIALIZING',
            'preview':    preview,
            'confirmed':  True,
            'message':    'Entry started. Monitor /api/ssdh/sessions/' + session_id + ' for status.',
        }), 202

    except Exception as e:
        log.exception("start_session error: %s", e)
        return jsonify({'error': str(e)}), 500


# =============================================================================
# POST /api/ssdh/sessions/<session_id>/stop
# =============================================================================

@ssdh_bp.route('/sessions/<session_id>/stop', methods=['POST'])
def stop_session(session_id: str):
    """Graceful stop — triggers wind-down exit sequence."""
    try:
        from .ssdh_monitor import get_monitor
        from .ssdh_state   import load_sessions, STATUS_WIND_DOWN, CLOSE_MANUAL, persist_session

        monitor = get_monitor(session_id)
        sessions = load_sessions()
        if session_id not in sessions:
            return jsonify({'error': 'Session not found'}), 404

        session = sessions[session_id]

        if monitor:
            # Trigger graceful exit via monitor
            def _do_stop():
                try:
                    loop = asyncio.DefaultEventLoopPolicy().new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(
                        monitor._trigger_exit(monitor.get_session() or session,
                                               CLOSE_MANUAL, 'operator_stop')
                    )
                    loop.close()
                except Exception as e:
                    log.error("stop_session _do_stop: %s", e)

            try:
                from eventlet.patcher import original as _ep_original
                RealThread = _ep_original('threading').Thread
            except (ImportError, AttributeError):
                import threading as _th
                RealThread = _th.Thread

            t = RealThread(target=_do_stop, daemon=True)
            t.start()
        else:
            session['status'] = STATUS_WIND_DOWN
            session['close_reason'] = CLOSE_MANUAL
            persist_session(session)

        return jsonify({'session_id': session_id, 'status': 'wind_down_initiated'})
    except Exception as e:
        log.exception("stop_session error: %s", e)
        return jsonify({'error': str(e)}), 500


# =============================================================================
# POST /api/ssdh/sessions/<session_id>/kill
# =============================================================================

@ssdh_bp.route('/sessions/<session_id>/kill', methods=['POST'])
def kill_session(session_id: str):
    """Emergency kill switch — market-close all positions immediately."""
    try:
        from .ssdh_state   import load_sessions, persist_session
        from .ssdh_monitor import get_monitor, unregister_monitor

        sessions = load_sessions()
        if session_id not in sessions:
            return jsonify({'error': 'Session not found'}), 404

        session = sessions[session_id]
        monitor = get_monitor(session_id)
        if monitor:
            live = monitor.get_session()
            if live:
                session = live

        result_holder = {}

        def _do_kill():
            try:
                loop = asyncio.DefaultEventLoopPolicy().new_event_loop()
                asyncio.set_event_loop(loop)
                from .ssdh_kill import run_kill_switch
                result = loop.run_until_complete(run_kill_switch(session, _get_executor()))
                result_holder.update(result)
                loop.close()
                if monitor:
                    monitor.stop()
                    unregister_monitor(session_id)
            except Exception as e:
                log.exception("kill_session _do_kill: %s", e)
                result_holder['error'] = str(e)

        try:
            from eventlet.patcher import original as _ep_original
            RealThread = _ep_original('threading').Thread
        except (ImportError, AttributeError):
            import threading as _th
            RealThread = _th.Thread

        t = RealThread(target=_do_kill, daemon=True)
        t.start()
        t.join(timeout=30)   # Wait up to 30s for kill to complete

        return jsonify({
            'session_id':       session_id,
            'kill_result':      result_holder,
            'message':          'Kill switch activated',
        })
    except Exception as e:
        log.exception("kill_session error: %s", e)
        return jsonify({'error': str(e)}), 500


# =============================================================================
# GET /api/ssdh/presets
# =============================================================================

@ssdh_bp.route('/presets', methods=['GET'])
def list_presets():
    """List available strategy presets."""
    try:
        from .ssdh_presets import list_presets as _list
        return jsonify({'presets': _list()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# GET /api/ssdh/health
# =============================================================================

@ssdh_bp.route('/health', methods=['GET'])
def health():
    """Engine health check."""
    try:
        from .ssdh_state    import load_sessions
        from .ssdh_monitor  import _monitors
        from .ssdh_websocket import get_ws_health

        sessions    = load_sessions()
        live_count  = sum(1 for m in _monitors.values() if m.is_running())
        return jsonify({
            'status':      'ok',
            'sessions':    len(sessions),
            'live':        live_count,
            'ws_health':   get_ws_health(),
        })
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500


# =============================================================================
# GET /api/ssdh/sessions/<session_id>/activity
# =============================================================================

@ssdh_bp.route('/sessions/<session_id>/activity', methods=['GET'])
def get_session_activity(session_id: str):
    """Last N activity log entries for a session."""
    try:
        from .ssdh_activity import get_recent_activities
        limit = int(request.args.get('limit', 20))
        entries = get_recent_activities(session_id=session_id, limit=limit)
        return jsonify({'activities': entries, 'count': len(entries)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# =============================================================================
# Helpers
# =============================================================================

def _generate_session_id() -> str:
    now = datetime.now(timezone.utc)
    uid = uuid.uuid4().hex[:6]
    return f"ssdh_{now.strftime('%d%m%y')}_{uid}"


def _add_hours(iso_str: str, hours: float) -> str:
    from datetime import timedelta
    dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
    return (dt + timedelta(hours=hours)).isoformat()


def _check_cross_engine_conflict() -> Optional[str]:
    """
    Returns conflict description if MMM has an active session using overlapping margin,
    or None if no conflict.
    """
    try:
        from webui.backend.routes.mmm.mmm_state import DEFAULT_PARAMS
        # Simple check: look for running MMM sessions
        import os, json
        mmm_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'data', 'mmm_sessions.json'
        )
        # MMM uses SQLite now, skip file check — just return no conflict
        return None
    except Exception:
        return None


def _build_preview(params: dict) -> dict:
    """
    Scans the options chain for target strikes and builds an entry preview.
    Returns preview dict with strike details, net credit, max loss, breakevens.
    """
    try:
        from .ssdh_reconciler import expiry_to_symbol_suffix

        initial_lots     = int(params.get('initial_lots', 1))
        ce_premium_tgt   = float(params.get('desired_ce_premium', 0))
        pe_premium_tgt   = float(params.get('desired_pe_premium', 0))
        hedge_premium_tgt= float(params.get('long_hedge_premium_target', 0))
        hedge_ratio      = float(params.get('long_hedge_lots_ratio', 2.0))
        expiry           = params.get('expiry', '')

        # Try to fetch a live quote for a sample symbol to get spot price
        spot_price = _fetch_spot_price()

        # Compute lot sizes
        hedge_lots = int(initial_lots * hedge_ratio)

        # Gross credit = (ce_premium_tgt + pe_premium_tgt) × initial_lots × LOT_SIZE_BTC
        # Debit        = (hedge_premium_tgt × 2) × hedge_lots × LOT_SIZE_BTC
        from .ssdh_state import LOT_SIZE_BTC
        gross_credit = (ce_premium_tgt + pe_premium_tgt) * initial_lots * LOT_SIZE_BTC
        gross_debit  = (hedge_premium_tgt * 2) * hedge_lots * LOT_SIZE_BTC
        net_credit   = gross_credit - gross_debit

        # Theoretical max loss (at long strike, at expiry)
        # Max loss = net debit if structure is net debit, or bounded by long strike distance
        # For SSDH: max loss ≈ (long_hedge_premium × hedge_lots - short_premium × short_lots) × LOT_SIZE_BTC
        theoretical_max_loss = abs(gross_debit - gross_credit) * 1.2  # conservative estimate

        # Estimated strikes (illustrative — real entry scans live chain)
        short_ce_strike = round(spot_price * 1.00 / 1000) * 1000 if spot_price else ce_premium_tgt
        short_pe_strike = short_ce_strike
        long_ce_strike  = round(spot_price * 1.04 / 1000) * 1000 if spot_price else ce_premium_tgt * 2
        long_pe_strike  = round(spot_price * 0.96 / 1000) * 1000 if spot_price else ce_premium_tgt * 2

        expiry_suffix = expiry_to_symbol_suffix(expiry) if len(expiry) == 8 else expiry

        legs = [
            {
                'leg_id':    'short_ce',
                'side':      'CE',
                'direction': 'short',
                'pos_type':  'core',
                'strike':    short_ce_strike,
                'lots':      initial_lots,
                'target_premium': ce_premium_tgt,
                'symbol':    f'C-BTC-{int(short_ce_strike)}-{expiry_suffix}',
            },
            {
                'leg_id':    'short_pe',
                'side':      'PE',
                'direction': 'short',
                'pos_type':  'core',
                'strike':    short_pe_strike,
                'lots':      initial_lots,
                'target_premium': pe_premium_tgt,
                'symbol':    f'P-BTC-{int(short_pe_strike)}-{expiry_suffix}',
            },
            {
                'leg_id':    'long_ce',
                'side':      'CE',
                'direction': 'long',
                'pos_type':  'hedge',
                'strike':    long_ce_strike,
                'lots':      hedge_lots,
                'target_premium': hedge_premium_tgt,
                'symbol':    f'C-BTC-{int(long_ce_strike)}-{expiry_suffix}',
            },
            {
                'leg_id':    'long_pe',
                'side':      'PE',
                'direction': 'long',
                'pos_type':  'hedge',
                'strike':    long_pe_strike,
                'lots':      hedge_lots,
                'target_premium': hedge_premium_tgt,
                'symbol':    f'P-BTC-{int(long_pe_strike)}-{expiry_suffix}',
            },
        ]

        multiplier = float(params.get('intraday_max_loss_multiplier', 1.75))
        return {
            'ok':                   True,
            'legs':                 legs,
            'spot_price':           spot_price,
            'gross_credit':         round(gross_credit, 6),
            'gross_debit':          round(gross_debit, 6),
            'net_credit':           round(net_credit, 6),
            'theoretical_max_loss': round(theoretical_max_loss, 6),
            'intraday_max_loss':    round(theoretical_max_loss * multiplier, 6),
            'breakeven_upper':      long_ce_strike,
            'breakeven_lower':      long_pe_strike,
            'expiry':               expiry,
            'expiry_suffix':        expiry_suffix,
        }
    except Exception as e:
        log.warning("_build_preview error: %s", e)
        return {'ok': False, 'error': str(e)}


def _build_preview_from_legs(provided_legs: list, params: dict) -> dict:
    """
    Build preview from manually-selected legs (chain picker flow).
    Legs already have symbol, strike, lots, target_premium from live chain.
    """
    try:
        from .ssdh_state import LOT_SIZE_BTC
        from .ssdh_reconciler import expiry_to_symbol_suffix

        legs = []
        short_ce = short_pe = long_ce = long_pe = None

        for leg in provided_legs:
            normalized = {
                'leg_id':         str(leg.get('leg_id', f"leg_{len(legs)}")),
                'side':           leg['side'],
                'direction':      leg['direction'],
                'pos_type':       leg['pos_type'],
                'strike':         float(leg['strike']),
                'lots':           int(leg['lots']),
                'target_premium': float(leg['target_premium']),
                'symbol':         str(leg['symbol']),
            }
            legs.append(normalized)
            key = (leg['direction'], leg['side'])
            if key == ('short', 'CE'):   short_ce = normalized
            elif key == ('short', 'PE'): short_pe = normalized
            elif key == ('long', 'CE'):  long_ce  = normalized
            elif key == ('long', 'PE'):  long_pe  = normalized

        gross_credit = sum(
            l['target_premium'] * l['lots'] * LOT_SIZE_BTC
            for l in legs if l['direction'] == 'short'
        )
        gross_debit = sum(
            l['target_premium'] * l['lots'] * LOT_SIZE_BTC
            for l in legs if l['direction'] == 'long'
        )
        net_credit = gross_credit - gross_debit
        theoretical_max_loss = max(gross_debit - gross_credit, gross_credit * 0.3)

        base_lots = int(params.get('initial_lots', 1))
        breakeven_upper = round(
            short_ce['strike'] + net_credit / (base_lots * LOT_SIZE_BTC), 0
        ) if short_ce and net_credit > 0 else (short_ce['strike'] if short_ce else 0)
        breakeven_lower = round(
            short_pe['strike'] - net_credit / (base_lots * LOT_SIZE_BTC), 0
        ) if short_pe and net_credit > 0 else (short_pe['strike'] if short_pe else 0)

        multiplier = float(params.get('intraday_max_loss_multiplier', 1.75))
        expiry = params.get('expiry', '')
        expiry_suffix = expiry_to_symbol_suffix(expiry) if len(expiry) == 8 else expiry
        spot_price = _fetch_spot_price()

        return {
            'ok':                   True,
            'legs':                 legs,
            'spot_price':           spot_price,
            'gross_credit':         round(gross_credit, 6),
            'gross_debit':          round(gross_debit, 6),
            'net_credit':           round(net_credit, 6),
            'theoretical_max_loss': round(theoretical_max_loss, 6),
            'intraday_max_loss':    round(theoretical_max_loss * multiplier, 6),
            'breakeven_upper':      breakeven_upper,
            'breakeven_lower':      breakeven_lower,
            'expiry':               expiry,
            'expiry_suffix':        expiry_suffix,
            'source':               'manual_chain_picker',
        }
    except Exception as e:
        log.warning("_build_preview_from_legs error: %s", e)
        return {'ok': False, 'error': str(e)}


def _fetch_spot_price() -> float:
    """Fetch current BTC spot price. Returns 0 on failure."""
    try:
        import json, urllib.request
        url = 'https://api.delta.exchange/v2/tickers/BTCUSD'
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
        return float((data.get('result') or {}).get('mark_price', 0) or 0)
    except Exception:
        return 0.0


def _build_legs(preview: dict, params: dict, session_id: str) -> list:
    """Convert preview legs to LegSpec dicts for AtomicEntryOrchestrator."""
    from .ssdh_executor import _generate_client_order_id

    legs = []
    for leg in preview.get('legs', []):
        side      = leg['side']
        direction = leg['direction']

        # Map to executor side chars
        side_char = 'c' if side == 'CE' else 'p'
        type_char = 's' if direction == 'short' else 'l'

        coid = _generate_client_order_id(session_id, side_char, type_char)

        legs.append({
            'leg_id':          leg['leg_id'],
            'symbol':          leg['symbol'],
            'side':            side,
            'direction':       direction,
            'pos_type':        leg['pos_type'],
            'strike':          leg['strike'],
            'lots':            leg['lots'],
            'order_side':      'sell' if direction == 'short' else 'buy',
            'client_order_id': coid,
        })
        # Attach symbol back to be available on positions for reconciler
        # (stored in leg spec; position will carry it after create_position)

    return legs
