"""
Strategy Routes
===============
REST API endpoints for options strategy builder.

Endpoints:
- POST /create          - Create new strategy
- GET  /templates       - Get strategy templates
- GET  /active          - Get active strategies
- GET  /<id>            - Get strategy details
- POST /execute/<id>    - Execute strategy
- POST /close/<id>      - Close strategy
- GET  /pnl/<id>        - Get strategy P&L
- GET  /payoff/<id>     - Get payoff diagram
- DELETE /<id>          - Delete strategy

Created: January 5, 2026
"""

import asyncio
import logging
from functools import wraps
from flask import Blueprint, jsonify, request

from .strategy_manager import StrategyManager
from .strategy_definitions import StrategyDefinitions

log = logging.getLogger(__name__)

# Blueprint defined in __init__.py
from . import options_strategy_bp


# ==================== Helpers ====================

def run_async(coro):
    """Helper to run async function in sync context"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if loop.is_running():
        # Create new loop in thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    else:
        return loop.run_until_complete(coro)


def handle_errors(f):
    """Error handling decorator"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            log.warning(f"Validation error: {e}")
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            log.error(f"API error in {f.__name__}: {e}", exc_info=True)
            return jsonify({'error': 'Internal server error', 'details': str(e)}), 500
    return wrapper


# ==================== Template Endpoints ====================

@options_strategy_bp.route('/templates', methods=['GET'])
@handle_errors
def get_templates():
    """
    Get available strategy templates
    
    Response:
        {
            templates: [
                {
                    type: "straddle",
                    name: "Straddle",
                    description: "...",
                    legs: 2,
                    parameters: ["strike"]
                },
                ...
            ]
        }
    """
    templates = [
        # Straddle variants
        {
            'type': 'long_straddle',
            'name': 'Long Straddle',
            'description': 'Buy ATM call + put. Profit from large moves either direction.',
            'legs': 2,
            'parameters': ['strike'],
            'direction': 'neutral',
            'max_loss': 'Premium paid',
            'max_profit': 'Unlimited',
            'position': 'long'
        },
        {
            'type': 'short_straddle',
            'name': 'Short Straddle',
            'description': 'Sell ATM call + put. Profit if price stays near strike. High risk.',
            'legs': 2,
            'parameters': ['strike'],
            'direction': 'neutral',
            'max_loss': 'Unlimited',
            'max_profit': 'Premium received',
            'position': 'short'
        },
        # Strangle variants
        {
            'type': 'long_strangle',
            'name': 'Long Strangle',
            'description': 'Buy OTM call + put. Cheaper than straddle, needs bigger move.',
            'legs': 2,
            'parameters': ['call_strike', 'put_strike'],
            'direction': 'neutral',
            'max_loss': 'Premium paid',
            'max_profit': 'Unlimited',
            'position': 'long'
        },
        {
            'type': 'short_strangle',
            'name': 'Short Strangle',
            'description': 'Sell OTM call + put. Profit if price stays in range. High risk.',
            'legs': 2,
            'parameters': ['call_strike', 'put_strike'],
            'direction': 'neutral',
            'max_loss': 'Unlimited',
            'max_profit': 'Premium received',
            'position': 'short'
        },
        # Iron Condor
        {
            'type': 'iron_condor',
            'name': 'Iron Condor',
            'description': 'Sell strangle, buy wings. Profit if price stays in range.',
            'legs': 4,
            'parameters': ['put_long_strike', 'put_short_strike', 'call_short_strike', 'call_long_strike'],
            'direction': 'neutral',
            'max_loss': 'Width - credit',
            'max_profit': 'Credit received'
        },
        # Iron Butterfly
        {
            'type': 'iron_butterfly',
            'name': 'Iron Butterfly',
            'description': 'Sell straddle, buy wings at same center. Max profit at strike.',
            'legs': 4,
            'parameters': ['center_strike', 'wing_width'],
            'direction': 'neutral',
            'max_loss': 'Width - credit',
            'max_profit': 'Credit received'
        },
        # Vertical Spreads
        {
            'type': 'call_spread',
            'name': 'Bull Call Spread',
            'description': 'Buy call, sell higher call. Bullish with limited risk.',
            'legs': 2,
            'parameters': ['long_strike', 'short_strike'],
            'direction': 'bullish',
            'max_loss': 'Net debit',
            'max_profit': 'Spread width - debit'
        },
        {
            'type': 'put_spread',
            'name': 'Bear Put Spread',
            'description': 'Buy put, sell lower put. Bearish with limited risk.',
            'legs': 2,
            'parameters': ['long_strike', 'short_strike'],
            'direction': 'bearish',
            'max_loss': 'Net debit',
            'max_profit': 'Spread width - debit'
        }
    ]
    
    return jsonify({'templates': templates})


# ==================== Strategy CRUD ====================

@options_strategy_bp.route('/create', methods=['POST'])
@handle_errors
def create_strategy():
    """
    Create a new strategy
    
    Request:
        {
            strategy_type: "straddle" | "strangle" | "iron_condor" | ...,
            underlying: "BTC" | "ETH",
            expiry: "YYMMDD",
            params: {
                // Type-specific parameters
                strike: 95000,  // for straddle
                // or
                call_strike: 96000,  // for strangle
                put_strike: 94000
            }
        }
        
    Response:
        {
            success: true,
            strategy: { ... }
        }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    strategy_type = data.get('strategy_type')
    underlying = data.get('underlying', 'BTC')
    expiry = data.get('expiry')
    params = data.get('params', {})
    
    if not strategy_type:
        return jsonify({'error': 'strategy_type required'}), 400
    
    if not expiry:
        return jsonify({'error': 'expiry required'}), 400
    
    manager = StrategyManager()
    strategy = manager.create_strategy(
        strategy_type=strategy_type,
        underlying=underlying,
        expiry=expiry,
        params=params
    )
    
    log.info(f"Created strategy: {strategy.name}")
    
    return jsonify({
        'success': True,
        'strategy': strategy.to_dict()
    })


@options_strategy_bp.route('/create-custom', methods=['POST'])
@handle_errors
def create_custom_strategy():
    """
    Create a custom strategy with manual legs
    
    Request:
        {
            name: "My Custom Strategy",
            underlying: "BTC",
            expiry: "YYMMDD",
            legs: [
                {option_type: "call", strike: 95000, side: "buy", quantity: 1},
                {option_type: "put", strike: 93000, side: "sell", quantity: 2}
            ]
        }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    name = data.get('name', 'Custom Strategy')
    underlying = data.get('underlying', 'BTC')
    expiry = data.get('expiry')
    legs = data.get('legs', [])
    
    if not expiry:
        return jsonify({'error': 'expiry required'}), 400
    
    if not legs:
        return jsonify({'error': 'legs required'}), 400
    
    manager = StrategyManager()
    strategy = manager.create_custom_strategy(
        name=name,
        underlying=underlying,
        expiry=expiry,
        legs=legs
    )
    
    return jsonify({
        'success': True,
        'strategy': strategy.to_dict()
    })


@options_strategy_bp.route('/active', methods=['GET'])
@handle_errors
def get_active_strategies():
    """
    Get all active strategies
    
    Query params:
        underlying: Filter by underlying (BTC/ETH)
        
    Response:
        {
            strategies: [...]
        }
    """
    underlying = request.args.get('underlying')
    
    manager = StrategyManager()
    strategies = manager.get_active_strategies()
    
    if underlying:
        strategies = [s for s in strategies if s.underlying == underlying]
    
    return jsonify({
        'strategies': [s.to_dict() for s in strategies]
    })


@options_strategy_bp.route('/list', methods=['GET'])
@handle_errors
def list_strategies():
    """
    List all strategies with filters
    
    Query params:
        status: Filter by status
        underlying: Filter by underlying
        limit: Max results (default 50)
    """
    status = request.args.get('status')
    underlying = request.args.get('underlying')
    limit = request.args.get('limit', 50, type=int)
    
    manager = StrategyManager()
    strategies = manager.get_all_strategies(
        status=status,
        underlying=underlying,
        limit=limit
    )
    
    return jsonify({
        'strategies': [s.to_dict() for s in strategies]
    })


@options_strategy_bp.route('/summary', methods=['GET'])
@handle_errors
def get_summary():
    """Get strategies summary statistics"""
    manager = StrategyManager()
    summary = manager.get_strategies_summary()
    return jsonify(summary)


@options_strategy_bp.route('/<strategy_id>', methods=['GET'])
@handle_errors
def get_strategy(strategy_id):
    """
    Get strategy details
    
    Response:
        {
            strategy: {...},
            history: [...]
        }
    """
    manager = StrategyManager()
    strategy = manager.get_strategy(strategy_id)
    
    if not strategy:
        return jsonify({'error': 'Strategy not found'}), 404
    
    history = manager.get_execution_history(strategy_id)
    
    return jsonify({
        'strategy': strategy.to_dict(),
        'history': history
    })


@options_strategy_bp.route('/<strategy_id>', methods=['DELETE'])
@handle_errors
def delete_strategy(strategy_id):
    """
    Delete a strategy (only if not executed)
    """
    manager = StrategyManager()
    
    success = manager.delete_strategy(strategy_id)
    
    if not success:
        return jsonify({
            'error': 'Cannot delete: strategy not found or already executed'
        }), 400
    
    return jsonify({'success': True})


# ==================== Execution Endpoints ====================

@options_strategy_bp.route('/execute/<strategy_id>', methods=['POST'])
@handle_errors
def execute_strategy(strategy_id):
    """
    Execute a configured strategy
    
    Request:
        {
            execution_mode: "sequential" | "parallel",
            order_type: "market" | "limit"
        }
    """
    data = request.get_json() or {}
    
    execution_mode = data.get('execution_mode', 'sequential')
    order_type = data.get('order_type', 'limit')
    
    manager = StrategyManager()
    
    result = run_async(
        manager.execute_strategy(
            strategy_id=strategy_id,
            execution_mode=execution_mode,
            order_type=order_type
        )
    )
    
    status_code = 200 if result.get('success') else 400
    return jsonify(result), status_code


@options_strategy_bp.route('/close/<strategy_id>', methods=['POST'])
@handle_errors
def close_strategy(strategy_id):
    """
    Close an active strategy
    
    Closes all leg positions at market
    """
    manager = StrategyManager()
    
    result = run_async(
        manager.close_strategy(strategy_id)
    )
    
    status_code = 200 if result.get('success') else 400
    return jsonify(result), status_code


@options_strategy_bp.route('/quick-execute', methods=['POST'])
@handle_errors
def quick_execute_strategy():
    """
    Create and execute a strategy in one step.
    Used by the Strategy Builder workflow for immediate execution.
    
    Request:
        {
            strategy_type: "long_straddle" | "iron_condor" | ...,
            name: "My Strategy",
            underlying: "BTC",
            expiry: "DDMMYYYY",
            legs: [
                {symbol: "...", option_type: "call", strike: 95000, side: "buy", quantity: 1},
                {symbol: "...", option_type: "put", strike: 93000, side: "sell", quantity: 2}
            ],
            execution_mode: "parallel" | "sequential",
            order_type: "market" | "limit"
        }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Extract parameters
    strategy_type = data.get('strategy_type', 'custom')
    name = data.get('name', f'Quick {strategy_type}')
    underlying = data.get('underlying', 'BTC')
    expiry = data.get('expiry')
    legs = data.get('legs', [])
    execution_mode = data.get('execution_mode', 'parallel')
    order_type = data.get('order_type', 'limit')
    
    if not expiry:
        return jsonify({'error': 'expiry required'}), 400
    
    if not legs or len(legs) == 0:
        return jsonify({'error': 'legs required'}), 400
    
    manager = StrategyManager()
    
    # Step 1: Create the strategy
    strategy = manager.create_custom_strategy(
        name=name,
        underlying=underlying,
        expiry=expiry,
        legs=legs,
        strategy_type=strategy_type
    )
    
    if not strategy:
        return jsonify({'error': 'Failed to create strategy'}), 400
    
    # Step 2: Execute the strategy
    result = run_async(
        manager.execute_strategy(
            strategy_id=str(strategy.id),
            execution_mode=execution_mode,
            order_type=order_type
        )
    )
    
    if not result.get('success'):
        return jsonify({
            'error': result.get('error', 'Execution failed'),
            'strategy': strategy.to_dict()
        }), 400
    
    return jsonify({
        'success': True,
        'strategy': strategy.to_dict(),
        'execution': result,
        'message': f'Strategy executed with {len(legs)} legs in {execution_mode} mode'
    })


# ==================== P&L Endpoints ====================

@options_strategy_bp.route('/pnl/<strategy_id>', methods=['GET'])
@handle_errors
def get_strategy_pnl(strategy_id):
    """
    Get current P&L for a strategy
    
    Response:
        {
            strategy_id: "...",
            total_pnl: 125.50,
            entry_cost: 500.00,
            current_value: 625.50,
            pnl_percent: 25.1,
            legs: [...]
        }
    """
    manager = StrategyManager()
    
    result = run_async(
        manager.calculate_strategy_pnl(strategy_id)
    )
    
    if 'error' in result:
        return jsonify(result), 400
    
    return jsonify(result)


@options_strategy_bp.route('/payoff/<strategy_id>', methods=['GET'])
@handle_errors
def get_payoff_diagram(strategy_id):
    """
    Get payoff diagram data
    
    Query params:
        price_range_pct: % above/below current price (default 20)
        num_points: Number of price points (default 100)
        
    Response:
        {
            price_points: [90000, 91000, ...],
            payoff_values: [-100, -50, 0, 50, ...],
            max_profit: 500,
            max_loss: -200,
            breakeven_points: [93000, 97000]
        }
    """
    price_range = request.args.get('price_range_pct', 20.0, type=float)
    num_points = request.args.get('num_points', 100, type=int)
    
    manager = StrategyManager()
    
    result = manager.get_payoff_diagram(
        strategy_id=strategy_id,
        price_range_pct=price_range,
        num_points=num_points
    )
    
    if 'error' in result:
        return jsonify(result), 400
    
    return jsonify(result)


# ==================== Monitoring Endpoints (Phase 3) ====================

@options_strategy_bp.route('/monitor/start', methods=['POST'])
@handle_errors
def start_monitor():
    """
    Start the strategy monitoring service
    
    Monitors active strategies for exit conditions
    """
    from .strategy_monitor import start_strategy_monitor
    
    monitor = start_strategy_monitor()
    
    return jsonify({
        'success': True,
        'message': 'Strategy monitor started',
        'status': monitor.get_monitoring_status()
    })


@options_strategy_bp.route('/monitor/stop', methods=['POST'])
@handle_errors
def stop_monitor():
    """Stop the strategy monitoring service"""
    from .strategy_monitor import stop_strategy_monitor
    
    stop_strategy_monitor()
    
    return jsonify({
        'success': True,
        'message': 'Strategy monitor stopped'
    })


@options_strategy_bp.route('/monitor/status', methods=['GET'])
@handle_errors
def monitor_status():
    """Get monitoring service status"""
    from .strategy_monitor import get_strategy_monitor
    
    monitor = get_strategy_monitor()
    
    return jsonify(monitor.get_monitoring_status())


@options_strategy_bp.route('/monitor/check/<strategy_id>', methods=['POST'])
@handle_errors
def force_check_strategy(strategy_id):
    """Force check exit conditions for a strategy"""
    from .strategy_monitor import get_strategy_monitor
    
    monitor = get_strategy_monitor()
    result = run_async(monitor.force_check(strategy_id))
    
    return jsonify(result)


# ==================== Auto-Entry Endpoints (Phase 3) ====================

@options_strategy_bp.route('/auto-entry/start', methods=['POST'])
@handle_errors
def start_auto_entry():
    """Start auto-entry monitoring for pending strategies"""
    from .strategy_auto_entry import start_auto_entry
    
    service = start_auto_entry()
    
    return jsonify({
        'success': True,
        'message': 'Auto-entry service started',
        'status': service.get_status()
    })


@options_strategy_bp.route('/auto-entry/stop', methods=['POST'])
@handle_errors
def stop_auto_entry():
    """Stop auto-entry monitoring"""
    from .strategy_auto_entry import stop_auto_entry
    
    stop_auto_entry()
    
    return jsonify({
        'success': True,
        'message': 'Auto-entry service stopped'
    })


@options_strategy_bp.route('/auto-entry/status', methods=['GET'])
@handle_errors
def auto_entry_status():
    """Get auto-entry service status"""
    from .strategy_auto_entry import get_auto_entry_service
    
    service = get_auto_entry_service()
    
    return jsonify(service.get_status())


@options_strategy_bp.route('/auto-entry/check/<strategy_id>', methods=['GET'])
@handle_errors
def check_entry_conditions(strategy_id):
    """Check if entry conditions are met for a strategy"""
    from .strategy_auto_entry import get_auto_entry_service
    
    service = get_auto_entry_service()
    result = run_async(service.check_entry_conditions(strategy_id))
    
    return jsonify(result)


# ==================== Risk Validation Endpoints (Phase 3) ====================

@options_strategy_bp.route('/risk/validate/<strategy_id>', methods=['GET'])
@handle_errors
def validate_strategy_risk(strategy_id):
    """
    Validate risk for a strategy before execution
    
    Response:
        {
            passed: true/false,
            checks: [...],
            errors: [...],
            warnings: [...],
            overall_risk: "low/medium/high/critical"
        }
    """
    from .strategy_risk import get_risk_validator
    
    manager = StrategyManager()
    strategy = manager.get_strategy(strategy_id)
    
    if not strategy:
        return jsonify({'error': 'Strategy not found'}), 404
    
    validator = get_risk_validator()
    result = validator.validate_strategy(strategy)
    
    return jsonify(result.to_dict())


@options_strategy_bp.route('/risk/limits', methods=['GET'])
@handle_errors
def get_risk_limits():
    """Get current risk limits"""
    from .strategy_risk import get_risk_validator
    
    validator = get_risk_validator()
    
    return jsonify({
        'limits': validator.limits.to_dict()
    })


@options_strategy_bp.route('/risk/limits', methods=['PUT'])
@handle_errors
def update_risk_limits():
    """Update risk limits"""
    from .strategy_risk import get_risk_validator
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    validator = get_risk_validator()
    validator.update_limits(data)
    
    return jsonify({
        'success': True,
        'limits': validator.limits.to_dict()
    })


# ==================== Notification Endpoints (Phase 3) ====================

@options_strategy_bp.route('/notifications', methods=['GET'])
@handle_errors
def get_notifications():
    """
    Get notification history
    
    Query params:
        strategy_id: Filter by strategy
        event_type: Filter by event type
        unread_only: Only unread notifications
        limit: Max results (default 50)
    """
    from .strategy_notifications import get_notification_service
    
    strategy_id = request.args.get('strategy_id')
    event_type = request.args.get('event_type')
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'
    limit = request.args.get('limit', 50, type=int)
    
    service = get_notification_service()
    notifications = service.get_notifications(
        strategy_id=strategy_id,
        event_type=event_type,
        unread_only=unread_only,
        limit=limit
    )
    
    return jsonify({
        'notifications': notifications,
        'unread_count': service.get_unread_count(strategy_id)
    })


@options_strategy_bp.route('/notifications/read', methods=['POST'])
@handle_errors
def mark_notifications_read():
    """Mark notifications as read"""
    from .strategy_notifications import get_notification_service
    
    data = request.get_json() or {}
    notification_ids = data.get('notification_ids', [])
    mark_all = data.get('mark_all', False)
    strategy_id = data.get('strategy_id')
    
    service = get_notification_service()
    
    if mark_all:
        service.mark_all_read(strategy_id)
    elif notification_ids:
        service.mark_as_read(notification_ids)
    
    return jsonify({'success': True})


@options_strategy_bp.route('/notifications/clear', methods=['POST'])
@handle_errors
def clear_notifications():
    """Clear notification history"""
    from .strategy_notifications import get_notification_service
    
    data = request.get_json() or {}
    strategy_id = data.get('strategy_id')
    
    service = get_notification_service()
    service.clear_history(strategy_id)
    
    return jsonify({'success': True})


# ==================== Automation Control ====================

@options_strategy_bp.route('/automation/start-all', methods=['POST'])
@handle_errors
def start_all_automation():
    """Start all automation services (monitor + auto-entry)"""
    from .strategy_monitor import start_strategy_monitor
    from .strategy_auto_entry import start_auto_entry
    
    monitor = start_strategy_monitor()
    auto_entry = start_auto_entry()
    
    return jsonify({
        'success': True,
        'message': 'All automation services started',
        'monitor_status': monitor.get_monitoring_status(),
        'auto_entry_status': auto_entry.get_status()
    })


@options_strategy_bp.route('/automation/stop-all', methods=['POST'])
@handle_errors
def stop_all_automation():
    """Stop all automation services"""
    from .strategy_monitor import stop_strategy_monitor
    from .strategy_auto_entry import stop_auto_entry
    
    stop_strategy_monitor()
    stop_auto_entry()
    
    return jsonify({
        'success': True,
        'message': 'All automation services stopped'
    })


@options_strategy_bp.route('/automation/status', methods=['GET'])
@handle_errors
def automation_status():
    """Get status of all automation services"""
    from .strategy_monitor import get_strategy_monitor
    from .strategy_auto_entry import get_auto_entry_service
    
    monitor = get_strategy_monitor()
    auto_entry = get_auto_entry_service()
    
    return jsonify({
        'monitor': monitor.get_monitoring_status(),
        'auto_entry': auto_entry.get_status()
    })


# ==================== Health Check ====================

@options_strategy_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    from .strategy_monitor import get_strategy_monitor
    from .strategy_auto_entry import get_auto_entry_service
    
    manager = StrategyManager()
    summary = manager.get_strategies_summary()
    
    monitor = get_strategy_monitor()
    auto_entry = get_auto_entry_service()
    
    return jsonify({
        'status': 'healthy',
        'module': 'options_strategy',
        'active_strategies': summary.get('active_count', 0),
        'total_strategies': summary.get('total_count', 0),
        'automation': {
            'monitor_running': monitor.is_running(),
            'auto_entry_running': auto_entry.is_running()
        }
    })


@options_strategy_bp.route('/logs', methods=['GET'])
@handle_errors
def get_strategy_logs():
    """
    Get recent logs from options strategy execution
    
    Query params:
        lines: number of lines to return (default: 100, max: 500)
        level: filter by level (info, warning, error, all)
    
    Response:
        {
            logs: ["log line 1", "log line 2", ...],
            count: 150
        }
    """
    import os
    from pathlib import Path
    
    lines = min(int(request.args.get('lines', 100)), 500)
    level_filter = request.args.get('level', 'all').lower()
    
    # Read from backend error log (contains all logging output)
    log_file = Path(__file__).parent.parent.parent / 'logs' / 'launchagent_webui_error.log'
    
    if not log_file.exists():
        return jsonify({'logs': [], 'count': 0})
    
    try:
        # Read last N lines from log file
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        # Filter for options strategy related logs
        strategy_logs = []
        for line in all_lines[-lines * 3:]:  # Read more to ensure we get enough after filtering
            line_stripped = line.strip()
            if not line_stripped:
                continue
            
            # Filter for strategy-related logs
            if any(keyword in line_stripped for keyword in [
                'strategy', 'Strategy', 'STRATEGY',
                'leg_executor', 'leg', 'Leg',
                'option', 'Option', 'OPTIONS',
                'Executing', 'Order', 'order',
                'Delta Exchange', 'product_symbol',
                'limit_price', 'size=', 'quantity=',
                '🚀', '✅', '❌', '⚠️', '⏳'
            ]):
                # Apply level filter
                if level_filter != 'all':
                    line_lower = line_stripped.lower()
                    if level_filter == 'error' and 'error' not in line_lower:
                        continue
                    if level_filter == 'warning' and 'warning' not in line_lower:
                        continue
                    if level_filter == 'info' and ('error' in line_lower or 'warning' in line_lower):
                        continue
                
                strategy_logs.append(line_stripped)
        
        # Return last N lines
        recent_logs = strategy_logs[-lines:] if len(strategy_logs) > lines else strategy_logs
        
        return jsonify({
            'logs': recent_logs,
            'count': len(recent_logs)
        })
    
    except Exception as e:
        log.error(f"Failed to read logs: {e}")
        return jsonify({
            'logs': [f"Error reading logs: {str(e)}"],
            'count': 1
        })


@options_strategy_bp.route('/execution-status', methods=['GET'])
@handle_errors
def get_execution_status():
    """
    Get detailed execution status for recent orders with market prices
    
    Response:
        {
            executions: [
                {
                    symbol: "C-BTC-90000-270226",
                    side: "buy",
                    quantity: 5,
                    filled_qty: 3,
                    order_price: 3850.0,
                    fill_price: 3845.0,
                    market_price: 3852.0,
                    status: "partial",
                    order_id: "1234567"
                },
                ...
            ],
            logs: ["recent log lines"]
        }
    """
    log.info("📊 Fetching execution status...")
    manager = StrategyManager()
    
    # Get active strategies
    active_strategies = manager.get_active_strategies()
    log.info(f"Found {len(active_strategies)} active strategies")
    
    executions = []
    
    # Build execution status from active strategies
    for strategy in active_strategies:
        log.info(f"Processing strategy {strategy.id} with {len(strategy.legs)} legs")
        for leg in strategy.legs:
            # Skip legs with no order activity (never executed or failed with no data)
            if leg.status == 'pending' and not leg.order_id and leg.current_price == 0:
                continue
            
            # Skip old failed legs with no useful data
            if leg.status == 'failed' and not leg.order_id and leg.current_price == 0:
                continue
                
            exec_status = {
                'symbol': leg.symbol,
                'side': leg.side,
                'quantity': leg.quantity,
                'filled_qty': leg.filled_qty,
                'order_price': leg.current_price,
                'fill_price': leg.avg_fill_price,
                'market_price': leg.current_bid if leg.side == 'sell' else leg.current_ask,
                'status': leg.status,
                'order_id': leg.order_id,
                'timestamp': strategy.executed_at or strategy.created_at
            }
            executions.append(exec_status)
            log.info(f"  Leg: {leg.symbol} | Status: {leg.status} | Qty: {leg.quantity} | Filled: {leg.filled_qty} | Order ID: {leg.order_id}")
    
    # Sort by timestamp (most recent first) and limit to last 50
    executions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    executions = executions[:50]
    
    # Get recent logs
    from pathlib import Path
    log_file = Path(__file__).parent.parent.parent / 'logs' / 'launchagent_webui_error.log'
    
    logs = []
    if log_file.exists():
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
            
            # Get last 50 strategy-related log lines
            for line in all_lines[-300:]:
                line_stripped = line.strip()
                if any(keyword in line_stripped for keyword in [
                    'Executing', 'Order', 'placed', 'filled', 'waiting',
                    'lot', 'lots', 'market price', 'execution',
                    '🚀', '✅', '❌', 'ℹ️', '⚠️', 'Leg', 'Strategy'
                ]):
                    logs.append(line_stripped)
            
            logs = logs[-50:]  # Last 50 relevant logs
            log.info(f"Returning {len(logs)} log lines")
        except Exception as e:
            log.error(f"Failed to read logs: {e}")
    
    log.info(f"✅ Returning {len(executions)} executions and {len(logs)} logs")
    return jsonify({
        'executions': executions,
        'logs': logs
    })


# ==================== MV Straddle Routes ====================

@options_strategy_bp.route('/mv-straddle/preview', methods=['POST'])
def preview_mv_straddle():
    """
    Preview MV Straddle before execution
    
    Request body:
    {
        "underlying": "BTC",
        "expiry": "25012026",
        "strike": null,
        "direction": "long",
        "quantity": 1,
        "autoStrike": true,
        "strikeOffset": 0
    }
    
    Returns:
        Preview with legs, analytics, volatility analysis
    """
    try:
        data = request.json
        log.info(f"📊 MV Straddle preview request: {data}")
        
        manager = StrategyManager()
        
        result = manager.get_mv_straddle_preview(
            underlying=data.get('underlying', 'BTC'),
            expiry=data.get('expiry'),
            strike=data.get('strike'),
            direction=data.get('direction', 'long'),
            quantity=data.get('quantity', 1),
            auto_strike=data.get('autoStrike', True),
            strike_offset=data.get('strikeOffset', 0)
        )
        
        if result.get('success'):
            log.info(f"✅ Preview generated successfully")
            return jsonify(result)
        else:
            log.error(f"❌ Preview failed: {result.get('error')}")
            return jsonify(result), 400
            
    except Exception as e:
        log.error(f"❌ Error in preview_mv_straddle: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@options_strategy_bp.route('/mv-straddle/create', methods=['POST'])
def create_mv_straddle():
    """
    Create and execute MV Straddle
    
    Request body: Same as preview
    
    Returns:
        Created strategy with execution results
    """
    try:
        data = request.json
        log.info(f"🚀 MV Straddle create request: {data}")
        
        manager = StrategyManager()
        
        # Create strategy
        result = manager.create_mv_straddle(
            name=data.get('name', f"MV Straddle {datetime.now().strftime('%Y-%m-%d %H:%M')}"),
            underlying=data.get('underlying', 'BTC'),
            expiry=data.get('expiry'),
            strike=data.get('strike'),
            direction=data.get('direction', 'long'),
            quantity=data.get('quantity', 1),
            auto_strike=data.get('autoStrike', True),
            strike_offset=data.get('strikeOffset', 0),
            preview_only=False
        )
        
        if not result.get('success'):
            log.error(f"❌ Create failed: {result.get('error')}")
            return jsonify(result), 400
        
        strategy = result['strategy']
        log.info(f"✅ Strategy created: {strategy['id']}")
        
        # Execute legs
        from .leg_executor import LegExecutor
        executor = LegExecutor()
        
        execution_result = executor.execute_strategy(
            strategy_id=strategy['id'],
            legs=strategy['legs']
        )
        
        log.info(f"Execution result: {execution_result}")
        
        return jsonify({
            'success': True,
            'strategy': strategy,
            'execution': execution_result
        })
        
    except Exception as e:
        log.error(f"❌ Error in create_mv_straddle: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@options_strategy_bp.route('/mv-straddle/<strategy_id>/close-leg', methods=['POST'])
def close_mv_straddle_leg(strategy_id):
    """
    Close one leg of MV Straddle
    
    Request body:
    {
        "leg_type": "call"  // or "put"
    }
    """
    try:
        data = request.json
        leg_type = data.get('leg_type')
        
        if not leg_type or leg_type not in ['call', 'put']:
            return jsonify({
                'success': False,
                'error': 'leg_type must be "call" or "put"'
            }), 400
        
        log.info(f"🔧 Close {leg_type} leg of strategy {strategy_id}")
        
        manager = StrategyManager()
        result = manager.close_mv_straddle_leg(strategy_id, leg_type)
        
        if result.get('success'):
            log.info(f"✅ Closed {leg_type} leg successfully")
            return jsonify(result)
        else:
            log.error(f"❌ Close leg failed: {result.get('error')}")
            return jsonify(result), 400
            
    except Exception as e:
        log.error(f"❌ Error closing leg: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@options_strategy_bp.route('/mv-straddle/<strategy_id>/roll', methods=['POST'])
def roll_mv_straddle(strategy_id):
    """
    Roll MV Straddle to new expiry
    
    Request body:
    {
        "new_expiry": "01022026",
        "new_strike": null,
        "keep_same_strike": true
    }
    """
    try:
        data = request.json
        new_expiry = data.get('new_expiry')
        
        if not new_expiry:
            return jsonify({
                'success': False,
                'error': 'new_expiry is required'
            }), 400
        
        log.info(f"🔄 Roll strategy {strategy_id} to expiry {new_expiry}")
        
        manager = StrategyManager()
        result = manager.roll_mv_straddle(
            strategy_id=strategy_id,
            new_expiry=new_expiry,
            new_strike=data.get('new_strike'),
            keep_same_strike=data.get('keep_same_strike', True)
        )
        
        if result.get('success'):
            log.info(f"✅ Rolled successfully")
            return jsonify(result)
        else:
            log.error(f"❌ Roll failed: {result.get('error')}")
            return jsonify(result), 400
            
    except Exception as e:
        log.error(f"❌ Error rolling: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@options_strategy_bp.route('/mv-straddle/<strategy_id>/adjust-ratio', methods=['POST'])
def adjust_mv_straddle_ratio(strategy_id):
    """
    Adjust MV Straddle call:put ratio
    
    Request body:
    {
        "call_quantity": 2,
        "put_quantity": 1
    }
    """
    try:
        data = request.json
        call_qty = data.get('call_quantity')
        put_qty = data.get('put_quantity')
        
        if call_qty is None or put_qty is None:
            return jsonify({
                'success': False,
                'error': 'call_quantity and put_quantity are required'
            }), 400
        
        log.info(f"⚙️ Adjust ratio of strategy {strategy_id} to {call_qty}:{put_qty}")
        
        manager = StrategyManager()
        result = manager.adjust_mv_straddle_ratio(
            strategy_id=strategy_id,
            call_quantity=call_qty,
            put_quantity=put_qty
        )
        
        if result.get('success'):
            log.info(f"✅ Ratio adjusted successfully")
            return jsonify(result)
        else:
            log.error(f"❌ Adjust ratio failed: {result.get('error')}")
            return jsonify(result), 400
            
    except Exception as e:
        log.error(f"❌ Error adjusting ratio: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
