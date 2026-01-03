"""
Settings API Blueprint
Handles settings-related endpoints including risk limits
"""

from flask import Blueprint, request, jsonify
import logging
from config.loader import get_config

log = logging.getLogger(__name__)

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/api/settings/risk-limits', methods=['GET'])
def get_risk_limits():
    """
    Get risk limits configuration from config.yaml
    """
    try:
        cfg = get_config()
        
        # Extract risk limits from config with defaults
        risk_limits = {
            'max_position_size': 0,
            'max_daily_loss': 0,
            'max_drawdown_percent': 20.0,
            'max_open_orders': 50,
            'max_leverage': 1.0,
            'stop_on_margin_call': True,
            'auto_reduce_on_loss': False,
            'loss_reduction_threshold': 10.0,
            'emergency_stop_loss': 0,
            'max_slippage_percent': 1.0,
        }
        
        # Try to get from config structure
        try:
            if hasattr(cfg, 'guardian'):
                if hasattr(cfg.guardian, 'max_account_loss_inr'):
                    val = float(cfg.guardian.max_account_loss_inr)
                    risk_limits['max_daily_loss'] = val
                    risk_limits['emergency_stop_loss'] = val
        except (AttributeError, ValueError, TypeError) as e:
            log.debug(f"Could not get guardian limits: {e}")
        
        try:
            if hasattr(cfg, 'grid') and hasattr(cfg.grid, 'limits'):
                if hasattr(cfg.grid.limits, 'max_qty_per_order'):
                    # Convert to approximate INR (rough estimate)
                    risk_limits['max_position_size'] = float(cfg.grid.limits.max_qty_per_order) * 100
                if hasattr(cfg.grid.limits, 'max_open_orders'):
                    risk_limits['max_open_orders'] = int(cfg.grid.limits.max_open_orders)
        except (AttributeError, ValueError, TypeError) as e:
            log.debug(f"Could not get grid limits: {e}")
        
        return jsonify({
            'data': risk_limits,
            'status': 'live'
        }), 200
        
    except Exception as e:
        log.error(f"Error getting risk limits: {e}")
        return jsonify({
            'data': {
                'max_position_size': 0,
                'max_daily_loss': 0,
                'max_drawdown_percent': 0,
                'max_open_orders': 0,
                'max_leverage': 0,
                'stop_on_margin_call': False,
                'auto_reduce_on_loss': False,
                'loss_reduction_threshold': 0,
                'emergency_stop_loss': 0,
                'max_slippage_percent': 0,
            },
            'status': 'error',
            'error': str(e)
        }), 500

@settings_bp.route('/api/settings/risk-limits/update', methods=['POST'])
def update_risk_limits():
    """
    Update risk limits configuration
    Note: This is a placeholder - actual implementation would update config.yaml
    """
    try:
        data = request.get_json()
        
        # For now, just acknowledge the request
        # In a full implementation, this would update config.yaml
        log.info(f"Risk limits update requested: {list(data.keys()) if data else 'no data'}")
        
        return jsonify({
            'success': True,
            'message': 'Risk limits update received (not yet implemented to persist to config)'
        }), 200
        
    except Exception as e:
        log.error(f"Error updating risk limits: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

