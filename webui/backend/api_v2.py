"""
GridBot WebUI Backend v2.0 - API Blueprint

Multi-instrument API with:
- Instance-scoped endpoints
- No global mutable state
- Explicit staleness metadata
- WebSocket per-instrument streams
"""

from flask import Blueprint, jsonify, request
from functools import wraps
import time
from typing import Optional

# Create blueprint for v2 API
api_v2 = Blueprint('api_v2', __name__, url_prefix='/api/v2')


# ============================================================================
# RESPONSE HELPERS
# ============================================================================

def api_response(data, stale_after_ms: int = 5000):
    """Wrap data in standard API response format."""
    return jsonify({
        'success': True,
        'data': data,
        'timestamp': int(time.time() * 1000),
        'staleAfterMs': stale_after_ms,
    })


def api_error(code: str, message: str, status_code: int = 400):
    """Return error response."""
    return jsonify({
        'success': False,
        'data': None,
        'timestamp': int(time.time() * 1000),
        'staleAfterMs': 0,
        'error': {
            'code': code,
            'message': message,
        }
    }), status_code


def validate_instance_id(func):
    """Decorator to validate instance_id format."""
    @wraps(func)
    def wrapper(instance_id, *args, **kwargs):
        if not instance_id or '_' not in instance_id:
            return api_error('INVALID_INSTANCE_ID', 
                           f'Invalid instance ID: {instance_id}. Expected format: SYMBOL_MODE')
        return func(instance_id, *args, **kwargs)
    return wrapper


def _derive_controlling_authority(heartbeat: dict, guardian: dict, trading: dict) -> str:
    """
    Determine which authority is currently in control.
    
    AUTHORITY CHAIN (in order of precedence):
    1. Heartbeat - Technical permission. If system is down, nothing else matters.
    2. Guardian - Capital permission. If risk limits hit, trading is forbidden.
    3. User - Manual override. If user paused, strategy respects that.
    4. Trading - Strategic intent. Strategy is in control.
    
    This answers the critical question: "Why is nothing happening?"
    - If heartbeat: "System is dead, fix infrastructure"
    - If guardian: "Risk protection active, review limits"
    - If user: "You paused it, resume when ready"
    - If trading: "Strategy is in control, check strategy logic"
    """
    # Check heartbeat first - system must be alive
    if heartbeat.get('status') in ('dead', 'unhealthy'):
        return 'heartbeat'
    
    # Check guardian - risk limits must not be hit
    if guardian.get('status') == 'blocked':
        return 'guardian'
    
    # Check trading intent - is it user-paused?
    if trading.get('intent') == 'hold' and trading.get('source') == 'user':
        return 'user'
    
    # Default to trading bot
    return 'trading'


# ============================================================================
# INSTANCE ENDPOINTS
# ============================================================================

@api_v2.route('/instances', methods=['GET'])
def list_instances():
    """
    List all registered trading instances.
    
    Returns:
        List of instance identities with symbol, mode, exchange.
    """
    # Import here to avoid circular imports
    from instance_manager import get_all_instances
    
    instances = get_all_instances()
    
    result = []
    for instance_id, config in instances.items():
        symbol = config.get('symbol', instance_id.split('_')[0])
        mode = config.get('mode', instance_id.split('_')[1] if '_' in instance_id else 'LONG')
        
        result.append({
            'instanceId': instance_id,
            'symbol': symbol,
            'mode': mode,
            'exchange': config.get('exchange', 'deribit'),
            'displayName': f"{symbol} {mode}",
            'enabled': config.get('enabled', True),
        })
    
    return api_response(result)


@api_v2.route('/instances/<instance_id>', methods=['GET'])
@validate_instance_id
def get_instance_state(instance_id: str):
    """
    Get full state for a single instance.
    
    Args:
        instance_id: Instance identifier (e.g., BTCUSD_LONG)
    """
    from instance_manager import get_instance
    from trading_state import get_positions, get_orders, get_pnl, get_grid_state
    from system_health import get_heartbeat_status, get_guardian_status, get_trading_intent
    
    instance = get_instance(instance_id)
    if not instance:
        return api_error('INSTANCE_NOT_FOUND', f'Instance {instance_id} not found', 404)
    
    symbol = instance.get('symbol', instance_id.split('_')[0])
    
    # Gather all state
    positions = get_positions(instance_id)
    orders = get_orders(instance_id)
    pnl = get_pnl(instance_id)
    grid = get_grid_state(instance_id)
    
    # NEW: Authority layer data - the three decision-makers
    heartbeat = get_heartbeat_status(instance_id)
    guardian = get_guardian_status(instance_id)
    trading_intent = get_trading_intent(instance_id)
    
    # Derive controlling authority
    controlling_authority = _derive_controlling_authority(heartbeat, guardian, trading_intent)
    
    return api_response({
        'identity': {
            'instanceId': instance_id,
            'symbol': symbol,
            'mode': instance.get('mode', 'LONG'),
            'exchange': instance.get('exchange', 'deribit'),
        },
        'tradingState': instance.get('trading_state', 'active'),
        # NEW: Authority layer - answers "why is nothing happening?"
        'authority': {
            'heartbeat': heartbeat,
            'guardian': guardian,
            'trading': trading_intent,
        },
        'controlledBy': controlling_authority,
        'positions': positions,
        'orders': orders,
        'pnl': pnl,
        'grid': grid,
    })


@api_v2.route('/instances/<instance_id>/positions', methods=['GET'])
@validate_instance_id
def get_instance_positions(instance_id: str):
    """Get positions for an instance."""
    from trading_state import get_positions
    
    positions = get_positions(instance_id)
    return api_response(positions)


@api_v2.route('/instances/<instance_id>/orders', methods=['GET'])
@validate_instance_id
def get_instance_orders(instance_id: str):
    """Get orders for an instance."""
    from trading_state import get_orders
    
    orders = get_orders(instance_id)
    return api_response(orders)


@api_v2.route('/instances/<instance_id>/grid', methods=['GET'])
@validate_instance_id
def get_instance_grid(instance_id: str):
    """Get grid configuration for an instance."""
    from trading_state import get_grid_state
    
    grid = get_grid_state(instance_id)
    return api_response(grid)


# ============================================================================
# TRADING ACTIONS
# ============================================================================

@api_v2.route('/instances/<instance_id>/trading/pause', methods=['POST'])
@validate_instance_id
def pause_instance_trading(instance_id: str):
    """Pause trading for an instance."""
    from trading_control import pause_trading
    
    success = pause_trading(instance_id)
    
    if success:
        return api_response({'success': True, 'message': f'Trading paused for {instance_id}'})
    else:
        return api_error('PAUSE_FAILED', f'Failed to pause trading for {instance_id}')


@api_v2.route('/instances/<instance_id>/trading/resume', methods=['POST'])
@validate_instance_id
def resume_instance_trading(instance_id: str):
    """Resume trading for an instance."""
    from trading_control import resume_trading
    
    success = resume_trading(instance_id)
    
    if success:
        return api_response({'success': True, 'message': f'Trading resumed for {instance_id}'})
    else:
        return api_error('RESUME_FAILED', f'Failed to resume trading for {instance_id}')


@api_v2.route('/instances/<instance_id>/trading/kill', methods=['POST'])
@validate_instance_id
def kill_instance_trading(instance_id: str):
    """Emergency stop for an instance."""
    from trading_control import emergency_stop
    
    success = emergency_stop(instance_id)
    
    if success:
        return api_response({
            'success': True, 
            'message': f'EMERGENCY STOP executed for {instance_id}'
        })
    else:
        return api_error('KILL_FAILED', f'Failed to stop trading for {instance_id}')


# ============================================================================
# GLOBAL ENDPOINTS
# ============================================================================

@api_v2.route('/global/health', methods=['GET'])
def get_system_health():
    """Get overall system health status."""
    from system_health import check_backend, check_database, check_exchange
    
    return api_response({
        'backend': check_backend(),
        'database': check_database(),
        'exchange': check_exchange(),
    }, stale_after_ms=2000)


@api_v2.route('/global/kill-all', methods=['POST'])
def kill_all_trading():
    """Emergency stop all trading across all instances."""
    from trading_control import emergency_stop_all
    
    result = emergency_stop_all()
    
    return api_response({
        'success': result['success'],
        'instancesStopped': result['count'],
        'message': 'EMERGENCY STOP executed for all instances',
    })


# ============================================================================
# REGISTRATION
# ============================================================================

def register_api_v2(app):
    """Register the v2 API blueprint with the Flask app."""
    app.register_blueprint(api_v2)
    print("✓ API v2 registered at /api/v2")
