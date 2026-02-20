"""
SSR ALGO API - REST Endpoints

Provides REST API for SSR Algo session management:
- Session CRUD operations
- Strike preview
- Session control (start, pause, resume, stop)
- Status and payoff data

Created: February 2, 2026
"""

import logging
from flask import Blueprint, request, jsonify
from datetime import datetime
from threading import Thread

from .ssr_algo_storage import get_storage
from .ssr_algo_engine import get_strike_selector
from .ssr_algo_executor import get_executor
from .ssr_algo_payoff import get_payoff_calculator
from .ssr_algo_monitor import (
    start_session_monitor,
    stop_session_monitor,
    pause_session_monitor,
    resume_session_monitor,
    get_session_monitor_status,
    get_all_monitor_statuses
)

log = logging.getLogger('ssr_algo_api')

# Create blueprint
ssr_algo_bp = Blueprint('ssr_algo', __name__, url_prefix='/api/ssr_algo')


def check_guardian_signal():
    """Check if trading is allowed."""
    try:
        from webui.backend.trading_control import get_signal
        return get_signal()
    except Exception:
        return 'GO'  # Default to GO if module not available


def _is_within_time_window_for_start(session: dict) -> bool:
    """Helper: check whether current time is within session's start/end window.

    This matches the monitor's _is_within_time_window logic to prevent starting
    sessions outside configured trading hours.
    """
    start_time_str = session.get('start_time')
    end_time_str = session.get('end_time')

    if not start_time_str or not end_time_str:
        return True

    now = datetime.now()
    try:
        start_parts = start_time_str.split(':')
        end_parts = end_time_str.split(':')

        start_time = now.replace(
            hour=int(start_parts[0]),
            minute=int(start_parts[1]),
            second=0,
            microsecond=0
        )
        end_time = now.replace(
            hour=int(end_parts[0]),
            minute=int(end_parts[1]),
            second=0,
            microsecond=0
        )

        # Handle overnight windows (e.g., 22:00 to 06:00)
        if end_time <= start_time:
            if now >= start_time or now <= end_time:
                return True
            return False

        return start_time <= now <= end_time
    except Exception as e:
        log.error(f"Error parsing time window in start check: {e}")
        return True


def _reconcile_position_filled_status(session: dict, storage=None):
    """
    Reconcile position group leg `filled` flags with actual filled_orders.
    
    The filled flag on position legs was not being updated when orders filled.
    This function cross-references filled_orders symbols with position leg symbols
    and sets filled=True for any leg whose symbol appears in filled_orders.
    
    If a change is made and storage is provided, persists the update.
    """
    filled_symbols = {}
    for order in session.get('filled_orders', []):
        symbol = order.get('symbol')
        fp = order.get('fill_price', 0)
        if symbol:
            # Keep the latest (or highest) fill price for each symbol
            if symbol not in filled_symbols or (fp and fp > filled_symbols[symbol]):
                filled_symbols[symbol] = fp
    
    if not filled_symbols:
        return
    
    positions = session.get('positions', [])
    changed = False
    for pos_group in positions:
        for leg_key in ['atm_ce', 'atm_pe', 'otm_ce_buy', 'otm_pe_buy', 'far_otm_ce', 'far_otm_pe']:
            leg = pos_group.get(leg_key)
            if leg and not leg.get('filled') and leg.get('symbol') in filled_symbols:
                leg['filled'] = True
                fp = filled_symbols[leg['symbol']]
                if fp and fp > 0:
                    leg['fill_price'] = fp
                changed = True
    
    if changed and storage:
        try:
            storage.update_session(session.get('session_id'), {'positions': positions})
        except Exception as e:
            log.debug(f"Failed to persist position reconciliation: {e}")


# =============================================================================
# Session CRUD Endpoints
# =============================================================================

@ssr_algo_bp.route('/sessions', methods=['GET'])
def list_sessions():
    """
    List all SSR Algo sessions.
    
    Query params:
        active_only: bool - If true, only return active sessions
    
    Returns:
        {sessions: [...], count: int}
    """
    try:
        active_only = request.args.get('active_only', 'false').lower() == 'true'
        storage = get_storage()
        sessions = storage.list_sessions(active_only=active_only)
        
        # Reconcile position filled status for all sessions
        for session in sessions:
            _reconcile_position_filled_status(session, storage)
        
        return jsonify({
            'success': True,
            'sessions': sessions,
            'count': len(sessions)
        })
        
    except Exception as e:
        log.exception("Failed to list sessions")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ssr_algo_bp.route('/session/<session_id>', methods=['GET'])
def get_session(session_id: str):
    """
    Get a specific session by ID.
    
    Returns:
        Session data or 404
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)
        
        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}'
            }), 404
        
        # Reconcile position filled status
        _reconcile_position_filled_status(session, storage)
        
        return jsonify({
            'success': True,
            'session': session
        })
        
    except Exception as e:
        log.exception(f"Failed to get session {session_id}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ssr_algo_bp.route('/session/create', methods=['POST'])
def create_session():
    """
    Create a new SSR Algo session.
    
    Request body:
        {
            underlying: str (BTC|ETH),
            expiry: str (DDMMYY),
            auto_loop_rounds: int (1-10),
            order_type: str (ssr|maker|market),
            start_time: str (HH:MM),
            end_time: str (HH:MM),
            strike_config: {
                otm_buy_percent_min: int,
                otm_buy_percent_max: int,
                far_otm_percent_min: int,
                far_otm_percent_max: int
            },
            circuit_breaker_config: {
                enabled: bool,
                max_adjustments_per_day: int,
                max_adjustments_per_session: int,
                max_daily_loss_usd: int,
                cooldown_minutes: int
            },
            dwell_time_minutes: int (1-60),
            price_tolerance: int (50-500)
        }
    
    Returns:
        Created session with strike preview
    """
    try:
        data = request.get_json()
        
        underlying = data.get('underlying', 'BTC').upper()
        expiry = data.get('expiry')
        auto_loop_rounds = data.get('auto_loop_rounds', 2)
        order_type = data.get('order_type', 'ssr')
        start_time = data.get('start_time', '15:00')
        end_time = data.get('end_time', '21:00')
        strike_config = data.get('strike_config', {
            'otm_buy_percent_min': 45,
            'otm_buy_percent_max': 49,
            'far_otm_percent_min': 20,
            'far_otm_percent_max': 30
        })
        circuit_breaker_config = data.get('circuit_breaker_config', None)
        exit_rules = data.get('exit_rules', None)
        delta_hedge_config = data.get('delta_hedge_config', None)
        iv_filter_config = data.get('iv_filter_config', None)
        dwell_time_minutes = data.get('dwell_time_minutes', 10)
        price_tolerance = data.get('price_tolerance', 100)

        if not expiry:
            return jsonify({
                'success': False,
                'error': 'Expiry is required'
            }), 400
        
        # Create session
        storage = get_storage()
        session = storage.create_session(
            underlying=underlying,
            expiry=expiry,
            auto_loop_rounds=auto_loop_rounds,
            order_type=order_type,
            start_time=start_time,
            end_time=end_time,
            strike_config=strike_config,
            circuit_breaker_config=circuit_breaker_config,
            dwell_time_minutes=dwell_time_minutes,
            price_tolerance=price_tolerance,
            exit_rules=exit_rules,
            delta_hedge_config=delta_hedge_config,
            iv_filter_config=iv_filter_config
        )
        
        # Preview strikes
        selector = get_strike_selector()
        strikes = selector.select_all_strikes(underlying, expiry, strike_config)
        
        return jsonify({
            'success': True,
            'session': session,
            'strikes_preview': strikes if strikes.get('success') else None,
            'strikes_error': strikes.get('error') if not strikes.get('success') else None
        })
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        log.exception("Failed to create session")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ssr_algo_bp.route('/session/<session_id>', methods=['DELETE'])
def delete_session(session_id: str):
    """
    Delete a session.
    
    Only allowed for IDLE or STOPPED sessions.
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)
        
        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}'
            }), 404
        
        if session.get('status') not in ['IDLE', 'STOPPED']:
            return jsonify({
                'success': False,
                'error': f"Cannot delete session in {session.get('status')} state. Stop it first."
            }), 400
        
        storage.delete_session(session_id)
        
        return jsonify({
            'success': True,
            'message': f'Session {session_id} deleted'
        })
        
    except Exception as e:
        log.exception(f"Failed to delete session {session_id}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =============================================================================
# Strike Preview
# =============================================================================

@ssr_algo_bp.route('/preview_strikes', methods=['POST'])
def preview_strikes():
    """
    Preview strike selection without creating a session.
    
    Request body:
        {
            underlying: str,
            expiry: str,
            strike_config: {...}
        }
    
    Returns:
        Selected strikes with premiums and ranges
    """
    try:
        data = request.get_json()
        
        underlying = data.get('underlying', 'BTC').upper()
        expiry = data.get('expiry')
        strike_config = data.get('strike_config', {
            'otm_buy_percent_min': 45,
            'otm_buy_percent_max': 49,
            'far_otm_percent_min': 20,
            'far_otm_percent_max': 30
        })
        
        if not expiry:
            return jsonify({
                'success': False,
                'error': 'Expiry is required'
            }), 400
        
        selector = get_strike_selector()
        strikes = selector.select_all_strikes(underlying, expiry, strike_config)

        # Add IV context to preview
        iv_context = None
        try:
            from .ssr_algo_vol_analyzer import get_vol_analyzer
            vol_analyzer = get_vol_analyzer()
            iv_context = vol_analyzer.get_iv_context(underlying, expiry)
            if iv_context:
                recommendation = vol_analyzer.get_entry_recommendation(iv_context)
                strikes['iv_context'] = iv_context
                strikes['iv_recommendation'] = recommendation
        except Exception:
            pass

        return jsonify(strikes)

    except Exception as e:
        log.exception("Failed to preview strikes")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =============================================================================
# Session Control
# =============================================================================

@ssr_algo_bp.route('/session/<session_id>/start', methods=['POST'])
def start_session(session_id: str):
    """
    Start a session - select strikes and execute auto-loop.
    
    Only allowed for IDLE sessions.
    """
    try:
        # Check guardian
        signal = check_guardian_signal()
        if signal != 'GO':
            return jsonify({
                'success': False,
                'error': f'Guardian signal is {signal}. Trading disabled.'
            }), 403
        
        storage = get_storage()
        session = storage.get_session(session_id)
        
        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}'
            }), 404
        
        if session.get('status') != 'IDLE':
            return jsonify({
                'success': False,
                'error': f"Cannot start session in {session.get('status')} state"
            }), 400

        # Prevent starting a session outside its configured trading window
        if not _is_within_time_window_for_start(session):
            return jsonify({
                'success': False,
                'error': 'Cannot start session outside configured time window (start_time/end_time).'
            }), 400
        
        # Update status
        storage.update_session(session_id, {
            'status': 'SELECTING_STRIKES',
            'started_at': datetime.utcnow().isoformat()
        })
        
        # Log the start with more detail
        storage.add_log(session_id, f"🚀 SSR Algo session starting for {session['underlying']}", 'info', {
            'underlying': session['underlying'],
            'expiry': session['expiry'],
            'rounds': session.get('auto_loop_rounds', 2)
        })
        storage.add_log(session_id, f"🔍 Scanning option chain for optimal strikes...", 'info')
        
        # === IV Context Check (Phase 4) ===
        iv_context = None
        try:
            from .ssr_algo_vol_analyzer import get_vol_analyzer
            vol_analyzer = get_vol_analyzer()
            iv_context = vol_analyzer.get_iv_context(session['underlying'], session['expiry'])

            iv_filter = session.get('iv_filter_config', {})
            if iv_filter.get('enabled', False) and iv_context.get('iv_rank', 50) > 0:
                recommendation = vol_analyzer.get_entry_recommendation(iv_context)
                if not recommendation.get('should_enter', True):
                    storage.add_log(session_id, f"IV filter blocked entry: {recommendation.get('reason')}", 'warn')
                    storage.update_session(session_id, {
                        'status': 'IDLE',
                        'started_at': None
                    })
                    return jsonify({
                        'success': False,
                        'error': f"IV filter: {recommendation.get('reason')}",
                        'iv_context': iv_context
                    }), 400
                storage.add_log(session_id, f"IV Rank: {iv_context.get('iv_rank', 0):.0f}% — {recommendation.get('reason', '')}", 'info')
        except Exception as e:
            log.debug(f"IV context check skipped: {e}")

        # === Regime Check (Phase 7) ===
        regime_adjustments = None
        active_strike_config = session.get('strike_config', {})
        try:
            from .ssr_algo_regime import get_regime_adapter
            regime_adapter = get_regime_adapter()

            from .ssr_algo_engine import get_strike_selector as _gs
            _temp_selector = _gs()
            spot = _temp_selector._get_spot_price(session['underlying'])
            if spot:
                regime_adjustments = regime_adapter.get_regime_adjustments(session['underlying'], spot)
                if regime_adjustments.get('regime') != 'ranging':
                    active_strike_config = regime_adapter.adjust_strike_config(active_strike_config, regime_adjustments)
                    storage.add_log(session_id,
                        f"Regime: {regime_adjustments.get('description', 'unknown')}",
                        'info')
        except Exception as e:
            log.debug(f"Regime check skipped: {e}")

        # Select strikes
        selector = get_strike_selector()
        strikes = selector.select_all_strikes(
            session['underlying'],
            session['expiry'],
            active_strike_config
        )
        
        if not strikes.get('success'):
            storage.add_log(session_id, f"❌ Strike selection failed: {strikes.get('error')}", 'error')
            storage.update_session(session_id, {
                'status': 'IDLE',
                'started_at': None
            })
            return jsonify({
                'success': False,
                'error': strikes.get('error', 'Strike selection failed')
            }), 400
        
        # Log successful strike selection with comprehensive details
        atm_strike = strikes['atm']['strike']
        storage.add_log(session_id, f"✅ ATM Strike selected: ${atm_strike:,.0f}", 'success', {
            'atm_strike': atm_strike,
            'atm_ce': strikes['atm']['ce_symbol'],
            'atm_pe': strikes['atm']['pe_symbol']
        })
        
        # Log each leg with entry price
        storage.add_log(session_id, f"📊 SELL ATM CE: {strikes['atm']['ce_symbol']} @ ${strikes['atm']['ce_premium']:.2f}", 'order')
        storage.add_log(session_id, f"📊 SELL ATM PE: {strikes['atm']['pe_symbol']} @ ${strikes['atm']['pe_premium']:.2f}", 'order')
        storage.add_log(session_id, f"📈 BUY OTM CE: {strikes['otm_ce_buy']['symbol']} @ ${strikes['otm_ce_buy']['premium']:.2f} (x2)", 'order')
        storage.add_log(session_id, f"📈 BUY OTM PE: {strikes['otm_pe_buy']['symbol']} @ ${strikes['otm_pe_buy']['premium']:.2f} (x2)", 'order')
        storage.add_log(session_id, f"📊 SELL Far OTM CE: {strikes['far_otm_ce']['symbol']} @ ${strikes['far_otm_ce']['premium']:.2f}", 'order')
        storage.add_log(session_id, f"📊 SELL Far OTM PE: {strikes['far_otm_pe']['symbol']} @ ${strikes['far_otm_pe']['premium']:.2f}", 'order')
        
        # Calculate and log net premium
        net_premium = (
            strikes['atm']['ce_premium'] + strikes['atm']['pe_premium'] +
            strikes['far_otm_ce']['premium'] + strikes['far_otm_pe']['premium'] -
            2 * strikes['otm_ce_buy']['premium'] - 2 * strikes['otm_pe_buy']['premium']
        )
        storage.add_log(session_id, f"💰 Net Premium: ${net_premium:.2f} (credit)", 'success' if net_premium > 0 else 'warn')
        
        # Build orders
        orders = selector.build_orders_from_strikes(
            strikes,
            session['underlying'],
            session['expiry']
        )
        
        # Update to executing
        storage.update_session(session_id, {'status': 'EXECUTING_AUTO_LOOP'})
        
        # Start execution in background thread
        def execute_in_background():
            try:
                executor = get_executor()
                
                # Log session start
                rounds = session.get('auto_loop_rounds', 2)
                lot_size = session.get('lot_size', 1)
                storage.add_log(session_id, f"⚡ Starting {rounds} auto-loop rounds (Lot: {lot_size})", 'order')
                storage.add_log(session_id, f"📝 Order type: {session.get('order_type', 'ssr').upper()}", 'info')
                
                def progress_callback(round_num, total, result):
                    """Safe progress callback with type checking."""
                    try:
                        log.info(f"[{session_id}] Progress: {round_num}/{total}")
                        
                        # Type safety: ensure result is a dict
                        if not isinstance(result, dict):
                            log.warning(f"[{session_id}] Progress callback received non-dict result: {type(result)}")
                            storage.add_log(session_id, f"⚠️ Round {round_num}/{total}: Unexpected result format", 'warn')
                            return
                        
                        if result.get('success'):
                            # Log each order in the round
                            order_results = result.get('results', [])
                            
                            # Type safety: ensure order_results is a list
                            if not isinstance(order_results, list):
                                log.warning(f"[{session_id}] order_results is not a list: {type(order_results)}")
                                order_results = []
                            
                            storage.add_log(session_id, f"━━━━━ Round {round_num}/{total} ━━━━━", 'info')
                            
                            pending_orders = []
                            for r in order_results:
                                # Type safety: skip non-dict items
                                if not isinstance(r, dict):
                                    log.warning(f"[{session_id}] Skipping non-dict order result: {type(r)}")
                                    continue
                                
                                symbol = r.get('symbol', 'Unknown')
                                side = r.get('side', '?')
                                size = r.get('size', 0)
                                order_id = r.get('order_id') or ''
                                
                                # Ensure order_id is a string before slicing
                                if not isinstance(order_id, str):
                                    order_id = str(order_id) if order_id else ''
                                
                                # Format: 🟢 BUY SPY250219C00549000 x2 (ID: abc123)
                                emoji = '🟢' if str(side).upper() == 'BUY' else '🔴'
                                order_id_display = order_id[:8] if order_id else 'N/A'
                                storage.add_log(session_id, f"  {emoji} {str(side).upper()} {symbol} x{abs(size) if isinstance(size, (int, float)) else size} (#{order_id_display})", 'order')
                                
                                if order_id:
                                    pending_orders.append({
                                        'order_id': order_id,
                                        'symbol': r.get('symbol', ''),
                                        'side': r.get('side', ''),
                                        'size': r.get('size', 0),
                                        'round': round_num
                                    })
                            if pending_orders:
                                storage.add_pending_orders(session_id, pending_orders)
                                storage.add_log(session_id, f"⏳ {len(pending_orders)} orders pending confirmation...", 'info')
                        else:
                            error_msg = result.get('error', 'Unknown error')
                            storage.add_log(session_id, f"⚠️ Round {round_num}/{total} had issues: {error_msg}", 'warn')
                    except Exception as e:
                        log.exception(f"[{session_id}] Error in progress callback: {e}")
                        storage.add_log(session_id, f"⚠️ Progress callback error: {e}", 'warn')
                
                result = executor.execute_rounds(
                    session_id=session_id,
                    orders=orders,
                    rounds=session.get('auto_loop_rounds', 2),
                    order_type=session.get('order_type', 'ssr'),
                    progress_callback=progress_callback
                )
                
                if result.get('success'):
                    # Get the number of completed rounds to calculate actual position sizes
                    completed_rounds = result.get('completed_rounds', 1)
                    
                    # Create position group with entry_price for payoff calculation
                    # Position sizes are multiplied by the number of completed rounds
                    # CRITICAL: Do NOT mark as filled=True here - positions become "filled"
                    # only when individual orders fill on exchange via update_order_filled()
                    position_group = {
                        'trigger_id': 0,
                        'atm_strike': strikes['atm']['strike'],
                        'atm_ce_premium': strikes['atm']['ce_premium'],
                        'atm_pe_premium': strikes['atm']['pe_premium'],
                        'rounds_executed': completed_rounds,
                        'atm_ce': {
                            'symbol': strikes['atm']['ce_symbol'],
                            'size': -1 * completed_rounds,  # Multiply by rounds
                            'filled': False,  # Will be set to True when order fills
                            'entry_price': strikes['atm']['ce_premium']
                        },
                        'atm_pe': {
                            'symbol': strikes['atm']['pe_symbol'],
                            'size': -1 * completed_rounds,  # Multiply by rounds
                            'filled': False,
                            'entry_price': strikes['atm']['pe_premium']
                        },
                        'otm_ce_buy': {
                            'symbol': strikes['otm_ce_buy']['symbol'],
                            'size': 2 * completed_rounds,  # Multiply by rounds
                            'filled': False,
                            'selected_premium': strikes['otm_ce_buy']['premium'],
                            'entry_price': strikes['otm_ce_buy']['premium']
                        },
                        'otm_pe_buy': {
                            'symbol': strikes['otm_pe_buy']['symbol'],
                            'size': 2 * completed_rounds,  # Multiply by rounds
                            'filled': False,
                            'selected_premium': strikes['otm_pe_buy']['premium'],
                            'entry_price': strikes['otm_pe_buy']['premium']
                        },
                        'far_otm_ce': {
                            'symbol': strikes['far_otm_ce']['symbol'],
                            'size': -1 * completed_rounds,  # Multiply by rounds
                            'filled': False,
                            'selected_premium': strikes['far_otm_ce']['premium'],
                            'entry_price': strikes['far_otm_ce']['premium']
                        },
                        'far_otm_pe': {
                            'symbol': strikes['far_otm_pe']['symbol'],
                            'size': -1 * completed_rounds,  # Multiply by rounds
                            'filled': False,
                            'selected_premium': strikes['far_otm_pe']['premium'],
                            'entry_price': strikes['far_otm_pe']['premium']
                        },
                        'executed_at': datetime.utcnow().isoformat()
                    }
                    
                    # Add position group
                    storage.add_position_group(session_id, position_group)
                    storage.add_log(session_id, "📊 Position group recorded", 'success')
                    
                    # CRITICAL: Calculate and store max loss points for monitoring
                    try:
                        payoff_calc = get_payoff_calculator()
                        updated_session = storage.get_session(session_id)
                        payoff_data = payoff_calc.calculate_session_payoff(updated_session)
                        max_loss_points = payoff_data.get('max_loss_points', {})
                        
                        max_loss_upper = max_loss_points.get('max_loss_upper')
                        max_loss_lower = max_loss_points.get('max_loss_lower')
                        max_loss_value = max_loss_points.get('max_loss_value')
                        max_profit_value = max_loss_points.get('max_profit_value')
                        
                        # Store max loss zones in session
                        storage.update_session(session_id, {
                            'max_loss_upper': max_loss_upper,
                            'max_loss_lower': max_loss_lower,
                            'max_loss_value': max_loss_value,
                            'max_profit_value': max_profit_value,
                            'breakevens': payoff_data.get('breakevens', []),
                            'net_premium': payoff_data.get('net_premium', 0)
                        })
                        
                        log.info(f"[{session_id}] Max loss zones stored: lower=${max_loss_lower}, upper=${max_loss_upper}")
                        storage.add_log(session_id, f"📈 Max loss zones calculated: ⬇️ ${max_loss_lower:,.0f} | ⬆️ ${max_loss_upper:,.0f}" if max_loss_lower and max_loss_upper else "⚠️ Could not calculate max loss zones", 'info' if max_loss_lower else 'warn')
                        
                        if max_loss_value:
                            storage.add_log(session_id, f"📊 Max Loss: ${abs(max_loss_value):,.2f} | Max Profit: ${max_profit_value:,.2f}", 'info')
                    except Exception as e:
                        log.error(f"[{session_id}] Failed to calculate max loss zones: {e}")
                        storage.add_log(session_id, f"⚠️ Could not calculate max loss zones: {e}", 'warn')
                    
                    # Place limit exit orders for sell legs (multiplied by completed rounds)
                    sell_positions = [
                        {'symbol': strikes['atm']['ce_symbol'], 'size': 1 * completed_rounds},
                        {'symbol': strikes['atm']['pe_symbol'], 'size': 1 * completed_rounds},
                        {'symbol': strikes['far_otm_ce']['symbol'], 'size': 1 * completed_rounds},
                        {'symbol': strikes['far_otm_pe']['symbol'], 'size': 1 * completed_rounds}
                    ]
                    executor.place_limit_exit_orders(session_id, sell_positions, exit_price=3.0)
                    storage.add_log(session_id, f"🎯 Placed limit exit orders at $3 for {len(sell_positions) * completed_rounds} sell legs ({completed_rounds} rounds)", 'order')
                    
                    # Update to monitoring and set rounds_completed
                    storage.update_session(session_id, {
                        'status': 'MONITORING',
                        'rounds_completed': completed_rounds
                    })
                    log.info(f"[{session_id}] Started monitoring (rounds_completed={completed_rounds})")
                    
                    # Log monitoring started with actual max loss zones
                    storage.add_log(session_id, f"🟢 All {session.get('auto_loop_rounds', 2)} rounds completed successfully!", 'success')
                    storage.add_log(session_id, f"👁️ Now monitoring price for max loss zones", 'info')
                    
                    # Use calculated max loss points if available, fall back to strikes
                    trigger_lower = max_loss_lower if max_loss_lower else strikes['far_otm_pe']['strike']
                    trigger_upper = max_loss_upper if max_loss_upper else strikes['far_otm_ce']['strike']
                    storage.add_log(session_id, f"📍 Trigger zones: ⬇️ ${trigger_lower:,.0f} | ⬆️ ${trigger_upper:,.0f}", 'trigger')
                    
                    # Start price monitor for max loss detection
                    start_session_monitor(
                        session_id=session_id,
                        get_session_callback=storage.get_session,
                        update_session_callback=storage.update_session,
                        adjustment_callback=None  # Auto-adjustment is built into monitor
                    )
                    storage.add_log(session_id, "🔄 Price monitor started (checking every 5 seconds)", 'info')
                    log.info(f"[{session_id}] Price monitor started")
                    
                else:
                    # Execution had issues - but if ANY rounds completed, continue to monitoring
                    # This makes the algo more resilient to transient issues
                    completed_rounds = result.get('completed_rounds', 0)
                    error_msg = result.get('error', 'Unknown error')
                    
                    if completed_rounds > 0:
                        # Some rounds succeeded - positions are placed, continue monitoring
                        log.warning(f"[{session_id}] Partial execution: {completed_rounds} rounds completed. Error: {error_msg}")
                        storage.update_session(session_id, {
                            'status': 'MONITORING',
                            'rounds_completed': completed_rounds,
                            'warning': f'Partial execution ({completed_rounds} rounds). {error_msg}'
                        })
                        
                        # Start monitor anyway
                        start_session_monitor(
                            session_id=session_id,
                            get_session_callback=storage.get_session,
                            update_session_callback=storage.update_session,
                            adjustment_callback=None
                        )
                        log.info(f"[{session_id}] Price monitor started despite partial execution")
                        storage.add_log(session_id, f"⚠️ Partial execution: {completed_rounds} rounds completed", 'warn')
                        storage.add_log(session_id, f"📍 Error: {error_msg}", 'error')
                        storage.add_log(session_id, "🔄 Continuing to monitoring mode with partial positions", 'info')
                    else:
                        # Zero rounds completed - actual failure, use ERROR state
                        storage.update_session(session_id, {
                            'status': 'ERROR',
                            'error': error_msg,
                            'error_at': datetime.utcnow().isoformat()
                        })
                        storage.add_log(session_id, f"❌ Execution failed: {error_msg}", 'error')
                        storage.add_log(session_id, "💡 Session moved to ERROR state. Click 'Retry' or 'Stop' to proceed.", 'info')
                        log.error(f"[{session_id}] Execution failed completely: {error_msg}")
                    
            except Exception as e:
                log.exception(f"[{session_id}] Background execution failed")
                storage.update_session(session_id, {
                    'status': 'ERROR',
                    'error': str(e),
                    'error_at': datetime.utcnow().isoformat()
                })
                storage.add_log(session_id, f"❌ Critical error: {e}", 'error')
                storage.add_log(session_id, "💡 Session moved to ERROR state. Check logs for details.", 'info')
        
        thread = Thread(target=execute_in_background, daemon=True)
        thread.start()
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'status': 'EXECUTING_AUTO_LOOP',
            'strikes': strikes,
            'message': 'Session started, executing auto-loop in background'
        })
        
    except Exception as e:
        log.exception(f"Failed to start session {session_id}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ssr_algo_bp.route('/session/<session_id>/retry', methods=['POST'])
def retry_session(session_id: str):
    """
    Retry a session in ERROR state.
    
    Clears the error and restarts from IDLE state.
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)
        
        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}'
            }), 404
        
        if session.get('status') not in ['ERROR', 'STOPPED']:
            return jsonify({
                'success': False,
                'error': f"Cannot retry session in {session.get('status')} state. Only ERROR or STOPPED sessions can be retried."
            }), 400
        
        # Clear error state and reset to IDLE
        storage.update_session(session_id, {
            'status': 'IDLE',
            'error': None,
            'error_at': None,
            'started_at': None,
            'positions': [],  # Clear partial positions
            'pending_orders': [],
            'filled_orders': [],
            'rounds_completed': 0,
            'rounds_placed': 0
        })
        storage.add_log(session_id, "🔄 Session reset - ready to retry", 'info')
        
        log.info(f"[{session_id}] Session reset to IDLE for retry")
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'status': 'IDLE',
            'message': 'Session reset to IDLE. Click Start to retry.'
        })
        
    except Exception as e:
        log.exception(f"Failed to retry session {session_id}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ssr_algo_bp.route('/session/<session_id>/pause', methods=['POST'])
def pause_session(session_id: str):
    """
    Pause a running session.
    
    Monitoring continues but triggers are blocked.
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)
        
        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}'
            }), 404
        
        if session.get('status') != 'MONITORING':
            return jsonify({
                'success': False,
                'error': f"Cannot pause session in {session.get('status')} state"
            }), 400
        
        # Pause the price monitor
        pause_session_monitor(session_id)
        
        storage.update_session(session_id, {'status': 'PAUSED'})
        storage.add_log(session_id, "⏸️ Session paused by user", 'warn')
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'status': 'PAUSED'
        })
        
    except Exception as e:
        log.exception(f"Failed to pause session {session_id}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ssr_algo_bp.route('/session/<session_id>/resume', methods=['POST'])
def resume_session(session_id: str):
    """
    Resume a paused session.
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)
        
        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}'
            }), 404
        
        if session.get('status') != 'PAUSED':
            return jsonify({
                'success': False,
                'error': f"Cannot resume session in {session.get('status')} state"
            }), 400
        
        # Resume the price monitor
        resume_session_monitor(session_id)
        
        storage.update_session(session_id, {'status': 'MONITORING'})
        storage.add_log(session_id, "▶️ Session resumed - monitoring active", 'success')
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'status': 'MONITORING'
        })
        
    except Exception as e:
        log.exception(f"Failed to resume session {session_id}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ssr_algo_bp.route('/session/<session_id>/stop', methods=['POST'])
def stop_session(session_id: str):
    """
    Stop a running session.
    
    Can stop from any active state.
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)
        
        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}'
            }), 404
        
        if session.get('status') == 'STOPPED':
            return jsonify({
                'success': False,
                'error': 'Session already stopped'
            }), 400
        
        if session.get('status') == 'IDLE':
            return jsonify({
                'success': False,
                'error': 'Session not started'
            }), 400
        
        # Stop the price monitor
        stop_session_monitor(session_id)
        
        # Request stop from executor if executing
        if session.get('status') == 'EXECUTING_AUTO_LOOP':
            executor = get_executor()
            executor.request_stop(session_id)
        
        storage.add_log(session_id, "🛑 Session stopped by user", 'error')
        storage.update_session(session_id, {
            'status': 'STOPPED',
            'stopped_at': datetime.utcnow().isoformat()
        })
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'status': 'STOPPED'
        })
        
    except Exception as e:
        log.exception(f"Failed to stop session {session_id}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ssr_algo_bp.route('/session/<session_id>/exit', methods=['POST'])
def exit_session(session_id: str):
    """
    Manually trigger full position exit for a session.

    Closes ALL open positions via market orders and stops the session.
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}'
            }), 404

        active_statuses = ['MONITORING', 'PAUSED', 'EXECUTING_AUTO_LOOP']
        if session.get('status') not in active_statuses:
            return jsonify({
                'success': False,
                'error': f"Cannot exit session in {session.get('status')} state. Must be {', '.join(active_statuses)}"
            }), 400

        from .ssr_algo_exit_manager import get_exit_manager
        exit_mgr = get_exit_manager()

        storage.add_log(session_id, "Manual exit requested by user", 'warn')
        result = exit_mgr.execute_full_exit(session_id, 'MANUAL_EXIT')

        if result.get('success'):
            return jsonify({
                'success': True,
                'session_id': session_id,
                'status': 'STOPPED',
                'orders_placed': result.get('orders_placed', 0),
                'message': f"Exit complete. {result.get('orders_placed', 0)} orders placed."
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Exit failed'),
                'session_id': session_id
            }), 500

    except Exception as e:
        log.exception(f"Failed to exit session {session_id}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =============================================================================
# Status and Monitoring
# =============================================================================

@ssr_algo_bp.route('/status', methods=['GET'])
def get_status():
    """
    Get status of all active sessions.
    """
    try:
        storage = get_storage()
        active = storage.get_active_sessions()
        
        # Get monitor statuses
        monitor_statuses = get_all_monitor_statuses()
        
        return jsonify({
            'success': True,
            'active_count': len(active),
            'sessions': [
                {
                    'session_id': s.get('session_id'),
                    'underlying': s.get('underlying'),
                    'expiry': s.get('expiry'),
                    'status': s.get('status'),
                    'trigger_count': s.get('trigger_count', 0),
                    'started_at': s.get('started_at'),
                    'monitor': monitor_statuses.get(s.get('session_id')),
                    'current_dte_phase': s.get('current_dte_phase'),
                    'live_greeks': s.get('live_greeks'),
                    'live_pnl': s.get('live_pnl'),
                    'current_regime': s.get('current_regime'),
                }
                for s in active
            ]
        })
        
    except Exception as e:
        log.exception("Failed to get status")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ssr_algo_bp.route('/session/<session_id>/payoff', methods=['GET'])
def get_session_payoff(session_id: str):
    """
    Get payoff data for a session.
    
    Returns payoff curve, max loss points, breakevens, etc.
    Also checks and updates pending orders before calculating payoff.
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)
        
        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}'
            }), 404
        
        # CRITICAL: Check and update pending orders before calculating payoff
        # This ensures filled_orders list is up-to-date
        from .ssr_algo_executor import get_executor
        executor = get_executor()
        fill_check = executor.check_and_update_pending_orders(session_id, storage)
        
        # Reload session after fill updates
        session = storage.get_session(session_id)
        
        if not session:
            return jsonify({
                'success': False,
                'error': f'Session {session_id} was deleted during payoff calculation'
            }), 404
        
        # Calculate payoff
        calc = get_payoff_calculator()
        payoff_data = calc.calculate_session_payoff(session)
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'positions': session.get('positions', []),
            'closed_positions': session.get('closed_positions', []),
            'payoff_curve': payoff_data.get('payoff_curve', []),
            'max_loss_points': payoff_data.get('max_loss_points', {}),
            'breakevens': payoff_data.get('breakevens', []),
            'net_premium': payoff_data.get('net_premium', 0),
            'greeks': payoff_data.get('greeks', {}),
            'spot_price': payoff_data.get('spot_price', 0),
            'position_count': payoff_data.get('position_count', 0),
            # Adjustment triggers and far OTM strikes
            'adjustment_triggers': payoff_data.get('adjustment_triggers', {}),
            'far_otm_ce_strike': payoff_data.get('far_otm_ce_strike'),
            'far_otm_pe_strike': payoff_data.get('far_otm_pe_strike'),
            'atm_strike': payoff_data.get('atm_strike'),
            # Order fill status
            'pending_orders_count': payoff_data.get('pending_orders_count', 0),
            'warning': payoff_data.get('warning'),
            'fill_check': fill_check.get('filled', 0) if fill_check.get('success') else 0
        })
        
    except Exception as e:
        log.exception(f"Failed to get payoff for {session_id}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =============================================================================
# Monitor Status
# =============================================================================

@ssr_algo_bp.route('/session/<session_id>/monitor', methods=['GET'])
def get_session_monitor(session_id: str):
    """
    Get monitor status for a specific session.
    
    Returns current price, dwell tracking, and zone status.
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)
        
        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}'
            }), 404
        
        # Get monitor status
        monitor_status = get_session_monitor_status(session_id)
        
        # Get payoff for max loss points
        calc = get_payoff_calculator()
        payoff_data = calc.calculate_session_payoff(session)
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'session_status': session.get('status'),
            'monitor': monitor_status,
            'max_loss_points': payoff_data.get('max_loss_points', {}),
            'breakevens': payoff_data.get('breakevens', []),
            'adjustments': session.get('adjustments', [])
        })
        
    except Exception as e:
        log.exception(f"Failed to get monitor status for {session_id}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ssr_algo_bp.route('/monitors', methods=['GET'])
def get_all_monitors():
    """
    Get status of all active monitors.
    """
    try:
        statuses = get_all_monitor_statuses()
        
        return jsonify({
            'success': True,
            'monitor_count': len(statuses),
            'monitors': statuses
        })
        
    except Exception as e:
        log.exception("Failed to get monitor statuses")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =============================================================================
# Live Greeks & MTM P&L (Phase 1)
# =============================================================================

@ssr_algo_bp.route('/session/<session_id>/greeks', methods=['GET'])
def get_session_greeks(session_id: str):
    """
    Get live Greeks and MTM P&L for a session (forces fresh fetch).

    Returns:
        {
            success: bool,
            session_id: str,
            live_greeks: {net_delta, net_gamma, net_theta, net_vega},
            live_pnl: {unrealized_pnl, realized_pnl, total_pnl, per_leg_pnl},
            position_greeks: [...per-leg data...],
            greeks_updated_at: str
        }
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}'
            }), 404

        if not session.get('positions'):
            return jsonify({
                'success': True,
                'session_id': session_id,
                'live_greeks': session.get('live_greeks', {}),
                'live_pnl': session.get('live_pnl', {}),
                'position_greeks': [],
                'greeks_updated_at': session.get('greeks_updated_at'),
                'message': 'No open positions'
            })

        from .ssr_algo_greeks import get_greeks_fetcher
        greeks_fetcher = get_greeks_fetcher()

        # Fresh fetch
        position_greeks = greeks_fetcher.fetch_position_greeks(session)
        portfolio_greeks = greeks_fetcher.calculate_portfolio_greeks(
            position_greeks, session.get('underlying', 'BTC')
        )
        mtm_pnl = greeks_fetcher.calculate_mtm_pnl(session, position_greeks)

        updated_at = datetime.utcnow().isoformat()

        # Update session storage with fresh values
        storage.update_session(session_id, {
            'live_greeks': portfolio_greeks,
            'live_pnl': mtm_pnl,
            'greeks_updated_at': updated_at
        })

        return jsonify({
            'success': True,
            'session_id': session_id,
            'live_greeks': portfolio_greeks,
            'live_pnl': mtm_pnl,
            'position_greeks': position_greeks,
            'greeks_updated_at': updated_at
        })

    except Exception as e:
        log.exception(f"Failed to get Greeks for {session_id}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =============================================================================
# Health Check
# =============================================================================

@ssr_algo_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for SSR Algo module."""
    return jsonify({
        'success': True,
        'module': 'ssr_algo',
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat()
    })


# =============================================================================
# Order Tracking
# =============================================================================

@ssr_algo_bp.route('/session/<session_id>/sync_orders', methods=['POST'])
def sync_session_orders(session_id: str):
    """
    Check and sync pending orders with exchange.
    
    Updates fill status and logs when orders are confirmed filled.
    This should be called periodically by the frontend to get accurate state.
    
    Returns:
        {
            success: bool,
            filled: int,          # Number of orders just confirmed filled
            pending: int,         # Number of orders still pending
            fills: List[Dict],    # Details of filled orders
            rounds_completed: int,
            rounds_placed: int
        }
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)
        
        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}'
            }), 404
        
        executor = get_executor()
        result = executor.check_and_update_pending_orders(session_id, storage)
        
        if result.get('success') and result.get('filled', 0) > 0:
            # Log the fills
            for fill in result.get('fills', []):
                storage.add_log(
                    session_id, 
                    f"✅ Order filled: {fill.get('symbol')} @ ${fill.get('fill_price', 0):.2f}",
                    'success',
                    {'order_id': fill.get('order_id'), 'fill_price': fill.get('fill_price')}
                )
        
        # Get updated session for current counts
        updated_session = storage.get_session(session_id)
        
        if not updated_session:
            return jsonify({
                'success': False,
                'error': f'Session {session_id} was deleted during sync'
            }), 404
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'filled': result.get('filled', 0),
            'pending': result.get('pending', 0),
            'fills': result.get('fills', []),
            'rounds_completed': updated_session.get('rounds_completed', 0),
            'rounds_placed': updated_session.get('rounds_placed', 0),
            'pending_orders': updated_session.get('pending_orders', []),
            'filled_orders': updated_session.get('filled_orders', [])
        })
        
    except Exception as e:
        log.exception(f"Failed to sync orders for {session_id}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ssr_algo_bp.route('/session/<session_id>/pending_orders', methods=['GET'])
def get_pending_orders(session_id: str):
    """
    Get pending (unfilled) orders for a session.
    
    Returns:
        {
            success: bool,
            pending_count: int,
            pending_orders: List[Dict],
            filled_count: int,
            filled_orders: List[Dict]
        }
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)
        
        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}'
            }), 404
        
        pending = session.get('pending_orders', [])
        filled = session.get('filled_orders', [])
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'pending_count': len(pending),
            'pending_orders': pending,
            'filled_count': len(filled),
            'filled_orders': filled,
            'rounds_placed': session.get('rounds_placed', 0),
            'rounds_completed': session.get('rounds_completed', 0)
        })
        
    except Exception as e:
        log.exception(f"Failed to get pending orders for {session_id}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@ssr_algo_bp.route('/session/<session_id>/logs', methods=['GET'])
def get_session_logs(session_id: str):
    """
    Get activity logs for a specific session.
    
    Query params:
        limit: int - Maximum number of logs to return (default: 50)
        since: str - Only return logs after this ISO timestamp
    
    Returns:
        {success: bool, logs: [...], count: int}
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)
        
        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}'
            }), 404
        
        logs = session.get('logs', [])
        
        # Filter by timestamp if provided
        since = request.args.get('since')
        if since:
            logs = [l for l in logs if l.get('timestamp', '') > since]
        
        # Apply limit
        limit = int(request.args.get('limit', 50))
        logs = logs[-limit:]  # Get most recent logs
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'logs': logs,
            'count': len(logs)
        })
        
    except Exception as e:
        log.exception(f"Failed to get logs for {session_id}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================
# Phase 10: Analytics, RV/IV, and Roll Endpoints
# ============================================================

@ssr_algo_bp.route('/analytics', methods=['GET'])
def get_aggregate_analytics():
    """
    Get aggregate analytics across all sessions.

    Returns win rate, total P&L, average return on premium, etc.
    """
    try:
        from .ssr_algo_analytics import get_analytics

        storage = get_storage()
        sessions = storage.list_sessions()
        analytics = get_analytics()

        result = analytics.get_aggregate_analytics(sessions)

        return jsonify({
            'success': True,
            **result
        })

    except Exception as e:
        log.exception("Failed to get aggregate analytics")
        return jsonify({'success': False, 'error': str(e)}), 500


@ssr_algo_bp.route('/session/<session_id>/analytics', methods=['GET'])
def get_session_analytics(session_id: str):
    """
    Get analytics for a specific session.

    Returns P&L breakdown, execution quality, hedge efficiency, etc.
    """
    try:
        from .ssr_algo_analytics import get_analytics

        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({'success': False, 'error': f'Session not found: {session_id}'}), 404

        analytics = get_analytics()
        result = analytics.get_session_analytics(session)

        return jsonify({
            'success': True,
            'analytics': result
        })

    except Exception as e:
        log.exception(f"Failed to get analytics for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ssr_algo_bp.route('/session/<session_id>/rv_iv', methods=['GET'])
def get_session_rv_iv(session_id: str):
    """
    Get RV/IV analysis for a session's underlying.

    Returns realized vol, implied vol, ratio, signal, and history.
    """
    try:
        from .ssr_algo_rv_tracker import get_rv_tracker

        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({'success': False, 'error': f'Session not found: {session_id}'}), 404

        rv_tracker = get_rv_tracker()
        underlying = session.get('underlying', 'BTC')
        expiry = session.get('expiry', '')

        snapshot = rv_tracker.get_rv_iv_snapshot(underlying, expiry)
        history = rv_tracker.get_rv_iv_history(underlying)

        return jsonify({
            'success': True,
            'session_id': session_id,
            'underlying': underlying,
            'snapshot': snapshot,
            'history': history
        })

    except Exception as e:
        log.exception(f"Failed to get RV/IV for {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500


@ssr_algo_bp.route('/session/<session_id>/roll', methods=['POST'])
def roll_session(session_id: str):
    """
    Roll session to next expiry — close current positions and create new session.

    Request body:
        {
            "next_expiry": "DDMMYYYY" or "DDMMYY"
        }
    """
    try:
        from .ssr_algo_exit_manager import get_exit_manager

        data = request.get_json() or {}
        next_expiry = data.get('next_expiry')

        if not next_expiry:
            return jsonify({'success': False, 'error': 'next_expiry is required'}), 400

        storage = get_storage()
        session = storage.get_session(session_id)

        if not session:
            return jsonify({'success': False, 'error': f'Session not found: {session_id}'}), 404

        if session.get('status') not in ('MONITORING', 'PAUSED'):
            return jsonify({
                'success': False,
                'error': f"Cannot roll session in '{session.get('status')}' state. Must be MONITORING or PAUSED."
            }), 400

        exit_mgr = get_exit_manager()
        result = exit_mgr.execute_roll(session_id, next_expiry)

        if result.get('success'):
            return jsonify({
                'success': True,
                'message': f"Rolled to new session {result['new_session_id']} with expiry {next_expiry}",
                **result
            })
        else:
            return jsonify({'success': False, **result}), 500

    except Exception as e:
        log.exception(f"Failed to roll session {session_id}")
        return jsonify({'success': False, 'error': str(e)}), 500
