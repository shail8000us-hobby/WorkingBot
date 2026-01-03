"""
System Health Module

Checks health status of backend components and authority layers.

AUTHORITY LAYERS (v2.1):
========================
The trading system has three independent decision-makers:

1. HEARTBEAT - Technical permission ("Is system alive?")
   - Monitors: API connection, WebSocket, backend process
   - If dead: Nothing will trade, even if strategy wants to

2. GUARDIAN - Capital permission ("Is trading ALLOWED?")
   - Monitors: Daily loss limits, position limits, margin requirements
   - If blocked: Trading is forbidden even if system is alive

3. TRADING - Strategic intent ("What does strategy WANT?")
   - Monitors: Strategy signals, grid levels, market conditions
   - Can be: active (trading), hold (paused), error (broken)

The UI must show ALL THREE separately so traders know:
- WHO is in control right now
- WHY they are in control
- WHAT action to take (different for each authority)
"""

from typing import Literal, Optional
import time

HealthStatus = Literal['healthy', 'degraded', 'down']
HeartbeatStatus = Literal['alive', 'degraded', 'dead']
GuardianStatus = Literal['allowed', 'cautious', 'blocked']
TradingIntent = Literal['active', 'hold', 'exit', 'error']


def check_backend() -> HealthStatus:
    """
    Check backend health.
    
    Returns 'healthy', 'degraded', or 'down'.
    """
    # If this code is running, backend is at least healthy
    return 'healthy'


def check_database() -> HealthStatus:
    """
    Check database connectivity.
    
    Returns 'healthy', 'degraded', or 'down'.
    """
    try:
        # TODO: Implement actual database health check
        # For now, assume healthy if we can import sqlite
        import sqlite3
        return 'healthy'
    except Exception:
        return 'down'


def check_exchange() -> HealthStatus:
    """
    Check exchange API connectivity.
    
    Returns 'healthy', 'degraded', or 'down'.
    """
    try:
        # TODO: Implement actual exchange health check
        # This should:
        # 1. Check if API key is configured
        # 2. Make a lightweight API call (e.g., get server time)
        # 3. Check latency
        
        # Placeholder - assume healthy
        return 'healthy'
    except Exception:
        return 'down'


def get_full_health_status() -> dict:
    """
    Get comprehensive health status.
    
    Returns:
        {
            'backend': HealthStatus,
            'database': HealthStatus,
            'exchange': HealthStatus,
            'overall': HealthStatus,
            'details': {...}
        }
    """
    backend = check_backend()
    database = check_database()
    exchange = check_exchange()
    
    # Overall is worst of all
    statuses = [backend, database, exchange]
    if 'down' in statuses:
        overall = 'down'
    elif 'degraded' in statuses:
        overall = 'degraded'
    else:
        overall = 'healthy'
    
    return {
        'backend': backend,
        'database': database,
        'exchange': exchange,
        'overall': overall,
        'details': {
            'backend_version': '2.0.0',
            'uptime_seconds': 0,  # TODO: Track actual uptime
        }
    }


# ============================================================================
# AUTHORITY LAYER: HEARTBEAT
# ============================================================================

def get_heartbeat_status(instance_id: str) -> dict:
    """
    Get heartbeat (technical permission) status for an instance.
    
    Heartbeat answers: "Is the system alive?"
    
    Returns:
        {
            'status': 'alive' | 'degraded' | 'dead',
            'lastSeen': timestamp_ms,  # Last heartbeat received
            'message': str,            # Human-readable description
        }
    """
    try:
        # TODO: Replace with actual heartbeat check from guardian/heartbeat bot
        # This should query the actual heartbeat monitoring system
        
        # For now, check if we can access instance data as a proxy
        from instance_manager import get_instance
        instance = get_instance(instance_id)
        
        if not instance:
            return {
                'status': 'dead',
                'lastSeen': 0,
                'message': 'Instance not found',
            }
        
        # Check if bot process is running
        # TODO: Implement actual process check
        last_heartbeat = instance.get('last_heartbeat', time.time())
        age_seconds = time.time() - last_heartbeat
        
        if age_seconds > 60:  # No heartbeat for 60+ seconds
            return {
                'status': 'dead',
                'lastSeen': int(last_heartbeat * 1000),
                'message': f'No heartbeat for {int(age_seconds)}s',
            }
        elif age_seconds > 30:  # Degraded if 30+ seconds
            return {
                'status': 'degraded',
                'lastSeen': int(last_heartbeat * 1000),
                'message': 'Heartbeat delayed',
            }
        else:
            return {
                'status': 'alive',
                'lastSeen': int(last_heartbeat * 1000),
                'message': 'System operational',
            }
    except Exception as e:
        return {
            'status': 'dead',
            'lastSeen': 0,
            'message': f'Error checking heartbeat: {str(e)}',
        }


# ============================================================================
# AUTHORITY LAYER: GUARDIAN
# ============================================================================

def get_guardian_status(instance_id: str) -> dict:
    """
    Get guardian (capital permission) status for an instance.
    
    Guardian answers: "Is trading ALLOWED by risk rules?"
    
    Returns:
        {
            'status': 'allowed' | 'cautious' | 'blocked',
            'reason': str | None,      # Why blocked (if blocked)
            'limits': {                 # Current limit status
                'dailyLoss': { 'current': float, 'max': float, 'percent': float },
                'positions': { 'current': int, 'max': int },
                'margin': { 'used': float, 'available': float, 'percent': float },
            }
        }
    """
    try:
        # TODO: Replace with actual guardian bot integration
        # This should query the guardian's current state
        
        from instance_manager import get_instance
        instance = get_instance(instance_id)
        
        if not instance:
            return {
                'status': 'blocked',
                'reason': 'Instance not found',
                'limits': None,
            }
        
        # Get configured limits
        config = instance.get('config', {})
        daily_loss_limit = config.get('daily_loss_limit', 100)
        max_positions = config.get('max_positions', 10)
        
        # Get current values
        # TODO: Get actual values from trading state
        current_daily_loss = 0
        current_positions = 0
        margin_used = 0
        margin_available = 1000
        
        # Calculate percentages
        daily_loss_pct = (current_daily_loss / daily_loss_limit * 100) if daily_loss_limit > 0 else 0
        margin_pct = (margin_used / (margin_used + margin_available) * 100) if (margin_used + margin_available) > 0 else 0
        
        # Determine status
        if daily_loss_pct >= 100:
            status = 'blocked'
            reason = 'Daily loss limit reached'
        elif daily_loss_pct >= 80 or margin_pct >= 80:
            status = 'cautious'
            reason = 'Approaching risk limits'
        else:
            status = 'allowed'
            reason = None
        
        return {
            'status': status,
            'reason': reason,
            'limits': {
                'dailyLoss': {
                    'current': current_daily_loss,
                    'max': daily_loss_limit,
                    'percent': daily_loss_pct,
                },
                'positions': {
                    'current': current_positions,
                    'max': max_positions,
                },
                'margin': {
                    'used': margin_used,
                    'available': margin_available,
                    'percent': margin_pct,
                },
            }
        }
    except Exception as e:
        return {
            'status': 'blocked',
            'reason': f'Error checking guardian: {str(e)}',
            'limits': None,
        }


# ============================================================================
# AUTHORITY LAYER: TRADING INTENT
# ============================================================================

def get_trading_intent(instance_id: str) -> dict:
    """
    Get trading intent (strategic intent) status for an instance.
    
    Trading intent answers: "What does the STRATEGY want to do?"
    
    Returns:
        {
            'intent': 'active' | 'hold' | 'exit' | 'error',
            'source': 'strategy' | 'user' | 'system',  # Who set this intent
            'reason': str | None,    # Why this intent
            'since': timestamp_ms,   # When intent was set
        }
    """
    try:
        from instance_manager import get_instance
        instance = get_instance(instance_id)
        
        if not instance:
            return {
                'intent': 'error',
                'source': 'system',
                'reason': 'Instance not found',
                'since': 0,
            }
        
        # Get trading state from instance
        trading_state = instance.get('trading_state', 'active')
        
        # Map trading state to intent
        if trading_state == 'paused':
            return {
                'intent': 'hold',
                'source': 'user',  # Assume user paused
                'reason': 'Trading paused by user',
                'since': int(instance.get('state_changed_at', time.time()) * 1000),
            }
        elif trading_state == 'halted':
            return {
                'intent': 'hold',
                'source': 'system',
                'reason': 'Trading halted by system',
                'since': int(instance.get('state_changed_at', time.time()) * 1000),
            }
        elif trading_state == 'error':
            return {
                'intent': 'error',
                'source': 'system',
                'reason': instance.get('last_error', 'Unknown error'),
                'since': int(instance.get('state_changed_at', time.time()) * 1000),
            }
        elif trading_state == 'exiting':
            return {
                'intent': 'exit',
                'source': instance.get('exit_source', 'strategy'),
                'reason': 'Closing all positions',
                'since': int(instance.get('state_changed_at', time.time()) * 1000),
            }
        else:
            return {
                'intent': 'active',
                'source': 'strategy',
                'reason': 'Strategy executing normally',
                'since': int(instance.get('state_changed_at', time.time()) * 1000),
            }
    except Exception as e:
        return {
            'intent': 'error',
            'source': 'system',
            'reason': f'Error checking trading intent: {str(e)}',
            'since': 0,
        }