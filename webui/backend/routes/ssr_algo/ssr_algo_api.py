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
            price_tolerance=price_tolerance
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
        
        # Select strikes
        selector = get_strike_selector()
        strikes = selector.select_all_strikes(
            session['underlying'],
            session['expiry'],
            session.get('strike_config', {})
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
                    position_group = {
                        'trigger_id': 0,
                        'atm_strike': strikes['atm']['strike'],
                        'atm_ce_premium': strikes['atm']['ce_premium'],
                        'atm_pe_premium': strikes['atm']['pe_premium'],
                        'rounds_executed': completed_rounds,
                        'atm_ce': {
                            'symbol': strikes['atm']['ce_symbol'],
                            'size': -1 * completed_rounds,  # Multiply by rounds
                            'filled': True,
                            'entry_price': strikes['atm']['ce_premium']
                        },
                        'atm_pe': {
                            'symbol': strikes['atm']['pe_symbol'],
                            'size': -1 * completed_rounds,  # Multiply by rounds
                            'filled': True,
                            'entry_price': strikes['atm']['pe_premium']
                        },
                        'otm_ce_buy': {
                            'symbol': strikes['otm_ce_buy']['symbol'],
                            'size': 2 * completed_rounds,  # Multiply by rounds
                            'filled': True,
                            'selected_premium': strikes['otm_ce_buy']['premium'],
                            'entry_price': strikes['otm_ce_buy']['premium']
                        },
                        'otm_pe_buy': {
                            'symbol': strikes['otm_pe_buy']['symbol'],
                            'size': 2 * completed_rounds,  # Multiply by rounds
                            'filled': True,
                            'selected_premium': strikes['otm_pe_buy']['premium'],
                            'entry_price': strikes['otm_pe_buy']['premium']
                        },
                        'far_otm_ce': {
                            'symbol': strikes['far_otm_ce']['symbol'],
                            'size': -1 * completed_rounds,  # Multiply by rounds
                            'filled': True,
                            'selected_premium': strikes['far_otm_ce']['premium'],
                            'entry_price': strikes['far_otm_ce']['premium']
                        },
                        'far_otm_pe': {
                            'symbol': strikes['far_otm_pe']['symbol'],
                            'size': -1 * completed_rounds,  # Multiply by rounds
                            'filled': True,
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
                    'monitor': monitor_statuses.get(s.get('session_id'))
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
    """
    try:
        storage = get_storage()
        session = storage.get_session(session_id)
        
        if not session:
            return jsonify({
                'success': False,
                'error': f'Session not found: {session_id}'
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
            # New fields for adjustment triggers
            'adjustment_triggers': payoff_data.get('adjustment_triggers', {}),
            'far_otm_ce_strike': payoff_data.get('far_otm_ce_strike'),
            'far_otm_pe_strike': payoff_data.get('far_otm_pe_strike'),
            'atm_strike': payoff_data.get('atm_strike')
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
