"""
Robustness API Blueprint

This module handles all API routes related to trading robustness features including
circuit breakers, confirmation guard, volatility safety, audit reports, and gatekeeper.

Routes:
- GET  /api/robustness/gatekeeper/status - Get safety gatekeeper status
- GET  /api/robustness/loss-limits - Get loss limits configuration
- GET  /api/robustness/circuit-breakers - Get circuit breaker statistics
- POST /api/robustness/circuit-breakers/reset - Reset all circuit breakers
- GET  /api/robustness/audit/report - Get order audit report
- GET  /api/robustness/audit/orders/<origin> - Get orders by origin
- GET  /api/robustness/guardian/hysteresis - Get Guardian hysteresis config
- GET  /api/robustness/volatility/status - Get current volatility status
- POST /api/robustness/volatility/update - Manually trigger volatility update
- POST /api/robustness/volatility/update-config - Update volatility configuration
- GET  /api/robustness/confirmation-guard/status - Get order confirmation guard status
- POST /api/robustness/confirmation-guard/reset - Reset confirmation guard

Dependencies:
- bot.safety.* (safety systems)
- bot.volatility.* (volatility tracking)
- bot.orders.audit (order auditing)
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request

log = logging.getLogger(__name__)

# Create blueprint
robustness_bp = Blueprint('robustness', __name__)

# File paths
BASE_DIR = Path(__file__).parent.parent.parent.parent
CONFIG_FILE = BASE_DIR / "config.yaml"

# Import YAML config loader
from config.loader import get_config, reload_config
import yaml

# Import YAML config helper
from webui.backend.utils.yaml_config import get_config_value

# ============================================================================
# Safety Gatekeeper Routes
# ============================================================================

@robustness_bp.route('/api/robustness/gatekeeper/status', methods=['GET'])
def get_gatekeeper_status():
    """Get safety gatekeeper status and statistics"""
    try:
        from bot.safety.gatekeeper import get_gatekeeper_stats
        stats = get_gatekeeper_stats()
        return jsonify({
            'success': True,
            'stats': stats,
            'enabled': True
        }), 200
    except Exception as e:
        log.error(f"Error getting gatekeeper status: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'enabled': False
        }), 500


@robustness_bp.route('/api/robustness/loss-limits', methods=['GET'])
def get_loss_limits():
    """Get loss limits configuration and validation status"""
    try:
        from bot.safety.loss_limits import get_loss_limits_config
        config = get_loss_limits_config()
        return jsonify({
            'success': True,
            'config': config
        }), 200
    except Exception as e:
        log.error(f"Error getting loss limits: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# Circuit Breaker Routes
# ============================================================================

@robustness_bp.route('/api/robustness/circuit-breakers', methods=['GET'])
def get_circuit_breakers():
    """Get circuit breaker statistics"""
    try:
        from bot.safety.circuit_breaker import get_all_circuit_breaker_stats
        stats = get_all_circuit_breaker_stats()
        return jsonify({
            'success': True,
            'circuit_breakers': stats
        }), 200
    except Exception as e:
        log.error(f"Error getting circuit breaker stats: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'circuit_breakers': {}
        }), 500


@robustness_bp.route('/api/robustness/circuit-breakers/reset', methods=['POST'])
def reset_circuit_breakers():
    """Reset all circuit breakers (manual intervention)"""
    try:
        from bot.safety.circuit_breaker import reset_all_circuit_breakers
        reset_all_circuit_breakers()
        return jsonify({
            'success': True,
            'message': 'All circuit breakers reset'
        }), 200
    except Exception as e:
        log.error(f"Error resetting circuit breakers: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# Order Audit Routes
# ============================================================================

@robustness_bp.route('/api/robustness/audit/report', methods=['GET'])
def get_audit_report():
    """Get order audit report"""
    try:
        from bot.orders.audit import generate_audit_report
        
        # Get query parameters
        days = int(request.args.get('days', 7))
        start_time = datetime.utcnow() - timedelta(days=days)
        
        report = generate_audit_report(start_time=start_time)
        return jsonify({
            'success': True,
            'report': report
        }), 200
    except Exception as e:
        log.error(f"Error generating audit report: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'report': {}
        }), 500


@robustness_bp.route('/api/robustness/audit/orders/<origin>', methods=['GET'])
def get_orders_by_origin(origin):
    """Get orders by origin from audit log"""
    try:
        from bot.orders.audit import get_orders_by_origin
        
        # Get query parameters
        days = int(request.args.get('days', 7))
        start_time = datetime.utcnow() - timedelta(days=days)
        
        orders = get_orders_by_origin(origin, start_time=start_time)
        return jsonify({
            'success': True,
            'origin': origin,
            'orders': orders,
            'count': len(orders)
        }), 200
    except Exception as e:
        log.error(f"Error getting orders by origin {origin}: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'orders': []
        }), 500


# ============================================================================
# Guardian Hysteresis Routes
# ============================================================================

@robustness_bp.route('/api/robustness/guardian/hysteresis', methods=['GET'])
def get_guardian_hysteresis():
    """Get Guardian hysteresis configuration"""
    try:
        # Load config to extract hysteresis values
        config = {}
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip().strip('"').strip("'")
        
        # Helper to get value from config dict
        def get_val(key, default):
            return float(config.get(key, default))
        
        hysteresis = {
            '80': {
                'trigger': get_val('GUARDIAN_HYSTERESIS_80_TRIGGER', 80),
                'reset': get_val('GUARDIAN_HYSTERESIS_80_RESET', 75)
            },
            '90': {
                'trigger': get_val('GUARDIAN_HYSTERESIS_90_TRIGGER', 90),
                'reset': get_val('GUARDIAN_HYSTERESIS_90_RESET', 85)
            },
            '100': {
                'trigger': get_val('GUARDIAN_HYSTERESIS_100_TRIGGER', 100),
                'reset': get_val('GUARDIAN_HYSTERESIS_100_RESET', 95)
            }
        }
        return jsonify({
            'success': True,
            'hysteresis': hysteresis
        }), 200
    except Exception as e:
        log.error(f"Error getting guardian hysteresis: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# Volatility Safety Routes
# ============================================================================

@robustness_bp.route('/api/robustness/volatility/status', methods=['GET'])
def get_volatility_status():
    """Get current volatility status (IV/RV)"""
    try:
        # Read from status file written by Trading Bot
        volatility_file = BASE_DIR / '.volatility_status.json'
        
        if not volatility_file.exists():
            # Return default status if file doesn't exist
            return jsonify({
                'success': True,
                'status': {
                    'enabled': True,
                    'iv': None,
                    'rv': None,
                    'spread': None,
                    'is_safe': True,
                    'violation_reason': None,
                    'last_update': None,
                    'thresholds': {
                        'max_iv': float(get_config_value('safety.volatility.max_iv', 'VOLATILITY_MAX_IV', 35)),
                        'max_rv': float(get_config_value('safety.volatility.max_rv', 'VOLATILITY_MAX_RV', 40)),
                        'max_spread': float(get_config_value('safety.volatility.max_spread', 'VOLATILITY_MAX_SPREAD', 10))
                    },
                    'settings': {
                        'check_interval': int(get_config_value('safety.volatility.check_interval', 'VOLATILITY_CHECK_INTERVAL', 300)),
                        'auto_resume': get_config_value('safety.volatility.auto_resume', 'VOLATILITY_AUTO_RESUME', True),
                        'resume_buffer': float(get_config_value('safety.volatility.resume_buffer', 'VOLATILITY_RESUME_BUFFER', 5.0))
                    }
                }
            }), 200
        
        with open(volatility_file, 'r') as f:
            status = json.load(f)

        status = status or {}
        
        # Get thresholds from YAML config (force reload to get latest values)
        from config.loader import reload_config
        yaml_config = reload_config()
        
        status['thresholds'] = {
            'max_iv': float(yaml_config.safety.volatility.max_iv),
            'max_rv': float(yaml_config.safety.volatility.max_rv),
            'max_spread': float(yaml_config.safety.volatility.max_spread)
        }
        
        status['config'] = {
            'check_interval': int(yaml_config.safety.volatility.check_interval),
            'auto_resume': yaml_config.safety.volatility.auto_resume,
            'resume_buffer': float(yaml_config.safety.volatility.resume_buffer)
        }
        
        return jsonify({
            'success': True,
            'status': status
        }), 200
        
    except Exception as e:
        log.error(f"Error getting volatility status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@robustness_bp.route('/api/robustness/volatility/update', methods=['POST'])
def update_volatility():
    """Manually trigger volatility update using robust collector"""
    try:
        from bot.volatility.delta_volatility_collector import get_collector
        
        # v6.0: Multi-symbol support
        symbol = request.args.get('symbol', 'BTCUSD')
        collector = get_collector(symbol=symbol)
        
        # Trigger immediate collection
        iv_data = collector._fetch_and_store_iv()
        rv_data_1d = collector._fetch_and_store_rv('1d')
        
        success = iv_data is not None and rv_data_1d is not None
        
        # Get latest values to return
        latest = collector.get_latest_values()
        
        return jsonify({
            'success': success,
            'message': 'Volatility data updated' if success else 'Update failed',
            'data': latest
        }), 200
    except Exception as e:
        import traceback
        log.error(f"Volatility update error: {e}")
        log.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@robustness_bp.route('/api/robustness/volatility/update-config', methods=['POST'])
def update_volatility_config():
    """Update volatility configuration in config.yaml"""
    try:
        data = request.get_json()
        
        # Validate input
        allowed_keys = {'max_iv', 'max_rv', 'max_spread', 'check_interval'}
        if not any(key in allowed_keys for key in data.keys()):
            return jsonify({
                'success': False,
                'error': 'No valid configuration keys provided'
            }), 400
        
        # Read current YAML config
        with open(CONFIG_FILE, 'r') as f:
            config = yaml.safe_load(f)
        
        # Ensure safety.volatility section exists
        if 'safety' not in config:
            config['safety'] = {}
        if 'volatility' not in config['safety']:
            config['safety']['volatility'] = {}
        
        # Update values
        updated = {}
        for key in allowed_keys:
            if key in data:
                config['safety']['volatility'][key] = float(data[key])
                updated[key] = float(data[key])
        
        # Write updated config
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        # Trigger config reload in WebUI backend
        reload_config()
        
        # Touch file to ensure Guardian's file watcher detects the change
        # (watchdog on macOS can miss modifications from some editors/patterns)
        import os
        import time
        time.sleep(0.1)  # Small delay to ensure write is complete
        os.utime(CONFIG_FILE, None)  # Update modification time
        
        return jsonify({
            'success': True,
            'message': 'Volatility thresholds updated successfully',
            'updated': updated
        }), 200
    except Exception as e:
        log.error(f"Error updating volatility config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# Order Confirmation Guard Routes
# ============================================================================

@robustness_bp.route('/api/robustness/confirmation-guard/status', methods=['GET'])
def get_confirmation_guard_status():
    """Get order confirmation guard status"""
    try:
        from bot.safety.order_confirmation_guard import get_confirmation_guard
        
        guard = get_confirmation_guard()
        stats = guard.get_stats()
        
        return jsonify({
            'success': True,
            'stats': stats
        }), 200
    except Exception as e:
        log.error(f"Error getting confirmation guard status: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'stats': {
                'enabled': False,
                'pending_orders_count': 0,
                'pending_orders': []
            }
        }), 500


@robustness_bp.route('/api/robustness/confirmation-guard/reset', methods=['POST'])
def reset_confirmation_guard():
    """Reset confirmation guard (clear all pending orders)"""
    try:
        from bot.safety.order_confirmation_guard import get_confirmation_guard
        
        guard = get_confirmation_guard()
        guard.reset()
        
        return jsonify({
            'success': True,
            'message': 'Confirmation guard reset successfully'
        }), 200
    except Exception as e:
        log.error(f"Error resetting confirmation guard: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# Helper Functions
# ============================================================================

def _atomic_write_text(filepath, content):
    """Write text to file atomically"""
    import tempfile
    import shutil
    
    filepath = Path(filepath)
    temp_file = filepath.with_suffix(filepath.suffix + '.tmp')
    try:
        with open(temp_file, 'w') as f:
            f.write(content)
        shutil.move(str(temp_file), str(filepath))
    except Exception:
        if temp_file.exists():
            temp_file.unlink()
        raise
