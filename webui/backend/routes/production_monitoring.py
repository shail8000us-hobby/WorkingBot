"""
Production Monitoring API Routes
================================
Enhanced monitoring endpoints that integrate new production-ready utilities.
Provides real-time health, risk, validation, and execution statistics.

Created: January 12, 2026
"""

from flask import Blueprint, jsonify, request
import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Create blueprint
production_monitoring_bp = Blueprint(
    'production_monitoring', 
    __name__, 
    url_prefix='/api/production'
)

# ============================================================================
# Health Monitor Integration
# ============================================================================

def get_health_monitor():
    """Get system health monitor instance"""
    try:
        from ..utils.health_monitor import health_monitor
        return health_monitor
    except ImportError as e:
        logger.warning(f"Health monitor not available: {e}")
        return None


@production_monitoring_bp.route('/health', methods=['GET'])
def get_system_health():
    """
    Get comprehensive system health report
    
    Returns:
        - overall_status: healthy, degraded, or critical
        - cpu_percent: Current CPU usage
        - memory_percent: Current memory usage
        - disk_percent: Current disk usage
        - api_status: Delta API health status
        - last_check: Timestamp of last check
    """
    try:
        monitor = get_health_monitor()
        if not monitor:
            return jsonify({
                'status': 'unavailable',
                'message': 'Health monitor not initialized',
                'fallback_health': {
                    'overall_status': 'unknown',
                    'cpu_percent': 0,
                    'memory_percent': 0,
                    'timestamp': datetime.utcnow().isoformat()
                }
            }), 200
        
        report = monitor.get_health_report()
        return jsonify({
            'status': 'success',
            'health': report,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting system health: {e}", exc_info=True)
        return jsonify({'error': str(e), 'status': 'error'}), 500


@production_monitoring_bp.route('/health/check', methods=['POST'])
def trigger_health_check():
    """
    Trigger an immediate health check
    
    Returns:
        Updated health report after fresh check
    """
    try:
        monitor = get_health_monitor()
        if not monitor:
            return jsonify({'error': 'Health monitor not available'}), 503
        
        # Run fresh check
        report = monitor.check_health_now()
        
        return jsonify({
            'status': 'success',
            'health': report,
            'message': 'Health check completed',
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error running health check: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Rate Limiter Status
# ============================================================================

def get_rate_limiters():
    """Get rate limiter instances"""
    try:
        from ..utils.rate_limiter import (
            DELTA_API_LIMITER, 
            DELTA_ORDER_LIMITER, 
            DELTA_PUBLIC_LIMITER
        )
        return {
            'api': DELTA_API_LIMITER,
            'order': DELTA_ORDER_LIMITER,
            'public': DELTA_PUBLIC_LIMITER
        }
    except ImportError as e:
        logger.warning(f"Rate limiters not available: {e}")
        return None


@production_monitoring_bp.route('/rate-limits', methods=['GET'])
def get_rate_limit_status():
    """
    Get current rate limiter status for all endpoints
    
    Returns:
        - api: General API rate limit status
        - order: Order placement rate limit status
        - public: Public endpoint rate limit status
        Each includes:
            - remaining: Remaining requests in current window
            - reset_time: Seconds until window resets
            - max_requests: Maximum requests per window
    """
    try:
        limiters = get_rate_limiters()
        if not limiters:
            return jsonify({
                'status': 'unavailable',
                'message': 'Rate limiters not initialized'
            }), 200
        
        status = {}
        for name, limiter in limiters.items():
            status[name] = {
                'remaining': limiter.get_remaining_requests(),
                'reset_time': round(limiter.get_reset_time(), 1),
                'max_requests': limiter.max_requests,
                'time_window': limiter.time_window,
                'usage_percent': round(
                    (1 - limiter.get_remaining_requests() / limiter.max_requests) * 100, 
                    1
                )
            }
        
        return jsonify({
            'status': 'success',
            'rate_limits': status,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting rate limit status: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Risk Manager Integration
# ============================================================================

def get_risk_manager():
    """Get risk manager instance"""
    try:
        from ..options_strategy.advanced_risk_manager import risk_manager
        return risk_manager
    except ImportError as e:
        logger.warning(f"Risk manager not available: {e}")
        return None


@production_monitoring_bp.route('/risk', methods=['GET'])
def get_risk_report():
    """
    Get comprehensive risk report
    
    Returns:
        - risk_level: Current risk level (low, medium, high, critical)
        - var_95: Value at Risk at 95% confidence
        - var_99: Value at Risk at 99% confidence
        - sharpe_ratio: Risk-adjusted returns
        - max_drawdown: Maximum observed drawdown
        - volatility_regime: Current market volatility regime
    """
    try:
        manager = get_risk_manager()
        if not manager:
            return jsonify({
                'status': 'unavailable',
                'message': 'Risk manager not initialized',
                'fallback_risk': {
                    'risk_level': 'unknown',
                    'can_trade': True,
                    'timestamp': datetime.utcnow().isoformat()
                }
            }), 200
        
        report = manager.get_risk_report()
        return jsonify({
            'status': 'success',
            'risk': report,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting risk report: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@production_monitoring_bp.route('/risk/can-trade', methods=['GET'])
def check_can_trade():
    """
    Quick check if trading is allowed based on risk parameters
    
    Returns:
        - can_trade: Boolean - whether trading is allowed
        - reason: Explanation if trading is blocked
        - risk_level: Current risk level
    """
    try:
        manager = get_risk_manager()
        if not manager:
            return jsonify({
                'can_trade': True,
                'reason': 'Risk manager not available - defaulting to allow',
                'risk_level': 'unknown'
            })
        
        report = manager.get_risk_report()
        
        # Determine if trading should be blocked
        can_trade = True
        reason = "Risk levels acceptable"
        
        if report.get('risk_level') == 'critical':
            can_trade = False
            reason = "Risk level is CRITICAL - trading blocked"
        elif report.get('drawdown', 0) > 20:
            can_trade = False
            reason = f"Max drawdown exceeded ({report.get('drawdown', 0):.1f}%)"
        
        return jsonify({
            'can_trade': can_trade,
            'reason': reason,
            'risk_level': report.get('risk_level', 'unknown'),
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error checking trade permission: {e}", exc_info=True)
        return jsonify({
            'can_trade': True,
            'reason': f'Error checking risk: {str(e)} - defaulting to allow',
            'risk_level': 'error'
        })


# ============================================================================
# Execution Statistics
# ============================================================================

# Global executor instance for stats (created on first access)
_executor_instance = None

def get_leg_executor():
    """Get leg executor instance for stats"""
    global _executor_instance
    try:
        if _executor_instance is None:
            from ..options_strategy.leg_executor import LegExecutor
            _executor_instance = LegExecutor()
        return _executor_instance
    except ImportError as e:
        logger.warning(f"Leg executor not available: {e}")
        return None


@production_monitoring_bp.route('/execution/stats', methods=['GET'])
def get_execution_stats():
    """
    Get current execution statistics
    
    Returns:
        - orders_placed: Total orders placed
        - orders_filled: Successfully filled orders
        - orders_failed: Failed orders
        - fill_rate: Percentage of successful fills
        - rate_limit_waits: Times rate limiting triggered
        - validation_failures: Pre-execution validation failures
    """
    try:
        executor = get_leg_executor()
        if not executor:
            return jsonify({
                'status': 'unavailable',
                'message': 'Executor not initialized'
            }), 200
        
        stats = executor.get_execution_stats()
        return jsonify({
            'status': 'success',
            'stats': stats,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting execution stats: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@production_monitoring_bp.route('/execution/stats/reset', methods=['POST'])
def reset_execution_stats():
    """Reset execution statistics"""
    try:
        executor = get_leg_executor()
        if not executor:
            return jsonify({'error': 'Executor not available'}), 503
        
        executor.reset_stats()
        return jsonify({
            'status': 'success',
            'message': 'Execution statistics reset',
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error resetting stats: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Validation Status
# ============================================================================

def get_validators():
    """Get validator instances"""
    try:
        from ..options_strategy.option_validator import OptionValidator, ValidationLevel
        from ..options_strategy.data_validator import MarketDataValidator
        return {
            'option_validator': OptionValidator(validation_level=ValidationLevel.STANDARD),
            'data_validator': MarketDataValidator()
        }
    except ImportError as e:
        logger.warning(f"Validators not available: {e}")
        return None


@production_monitoring_bp.route('/validate/option', methods=['POST'])
def validate_option():
    """
    Validate an option symbol or order parameters
    
    Request body:
        {
            "symbol": "C-BTCUSD-95000-20260115" (optional),
            "strike": 95000 (optional),
            "expiry": "2026-01-15" (optional),
            "side": "buy" (optional),
            "quantity": 1 (optional)
        }
    
    Returns:
        - is_valid: Boolean
        - errors: List of validation errors
        - warnings: List of validation warnings
    """
    try:
        validators = get_validators()
        if not validators:
            return jsonify({
                'is_valid': True,
                'errors': [],
                'warnings': ['Validator not available - skipping validation'],
                'status': 'unavailable'
            })
        
        data = request.get_json() or {}
        validator = validators['option_validator']
        
        results = {
            'is_valid': True,
            'errors': [],
            'warnings': []
        }
        
        # Validate symbol if provided
        if data.get('symbol'):
            symbol_result = validator.validate_option_symbol(data['symbol'])
            results['errors'].extend(symbol_result.errors)
            results['warnings'].extend(symbol_result.warnings)
            if not symbol_result.is_valid:
                results['is_valid'] = False
        
        # Validate order parameters if provided
        if any(key in data for key in ['side', 'quantity']):
            order_result = validator.validate_order_parameters(data)
            results['errors'].extend(order_result.errors)
            results['warnings'].extend(order_result.warnings)
            if not order_result.is_valid:
                results['is_valid'] = False
        
        return jsonify({
            'status': 'success',
            **results,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error validating option: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@production_monitoring_bp.route('/validate/strategy', methods=['POST'])
def validate_strategy():
    """
    Validate a multi-leg strategy before execution
    
    Request body:
        {
            "strategy_type": "straddle",
            "legs": [
                {"symbol": "...", "side": "buy", "quantity": 1},
                {"symbol": "...", "side": "buy", "quantity": 1}
            ]
        }
    
    Returns:
        - is_valid: Boolean
        - errors: List of validation errors
        - warnings: List of validation warnings
    """
    try:
        validators = get_validators()
        if not validators:
            return jsonify({
                'is_valid': True,
                'errors': [],
                'warnings': ['Validator not available'],
                'status': 'unavailable'
            })
        
        data = request.get_json() or {}
        validator = validators['option_validator']
        
        legs = data.get('legs', [])
        strategy_type = data.get('strategy_type', '')
        
        # Validate legs
        legs_result = validator.validate_strategy_legs(legs)
        
        # Validate structure if strategy type provided
        if strategy_type:
            structure_result = validator.validate_strategy_structure(strategy_type, legs)
            legs_result.errors.extend(structure_result.errors)
            legs_result.warnings.extend(structure_result.warnings)
            if not structure_result.is_valid:
                legs_result.is_valid = False
        
        return jsonify({
            'status': 'success',
            'is_valid': legs_result.is_valid,
            'errors': legs_result.errors,
            'warnings': legs_result.warnings,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error validating strategy: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Combined Dashboard Data
# ============================================================================

@production_monitoring_bp.route('/dashboard', methods=['GET'])
def get_dashboard_data():
    """
    Get all production monitoring data in a single call for dashboard
    
    Returns combined data:
        - health: System health status
        - rate_limits: Rate limiter status
        - risk: Risk metrics
        - execution: Execution statistics
    """
    try:
        dashboard_data = {
            'health': None,
            'rate_limits': None,
            'risk': None,
            'execution': None,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Get health
        monitor = get_health_monitor()
        if monitor:
            dashboard_data['health'] = monitor.get_health_report()
        
        # Get rate limits
        limiters = get_rate_limiters()
        if limiters:
            dashboard_data['rate_limits'] = {
                name: {
                    'remaining': limiter.get_remaining_requests(),
                    'max': limiter.max_requests,
                    'usage_percent': round(
                        (1 - limiter.get_remaining_requests() / limiter.max_requests) * 100,
                        1
                    )
                }
                for name, limiter in limiters.items()
            }
        
        # Get risk
        risk_mgr = get_risk_manager()
        if risk_mgr:
            dashboard_data['risk'] = risk_mgr.get_risk_report()
        
        # Get execution stats
        executor = get_leg_executor()
        if executor:
            dashboard_data['execution'] = executor.get_execution_stats()
        
        return jsonify({
            'status': 'success',
            'dashboard': dashboard_data
        })
        
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
