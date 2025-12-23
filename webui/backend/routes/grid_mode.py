"""
Grid Mode Toggle API - LONG/SHORT switching endpoint

Provides WebUI with ability to toggle between LONG and SHORT grid modes
"""

from flask import Blueprint, jsonify, request
import os
import logging
from pathlib import Path

from config.loader import get_config

def get_config_value(yaml_path: str, env_var: str = None, default: any = None):
    """Get config value from YAML using dot notation"""
    try:
        cfg = get_config()
        value = cfg
        for key in yaml_path.split('.'):
            value = getattr(value, key)
        return value
    except (AttributeError, KeyError):
        return default

log = logging.getLogger(__name__)

grid_mode_bp = Blueprint('grid_mode', __name__)

CONFIG_FILE = Path(__file__).parent.parent.parent.parent / "config.yaml"

# Import YAML config loader
from config.loader import get_config, reload_config
import yaml


@grid_mode_bp.route('/api/bot/grid-mode', methods=['GET'])
def get_grid_mode():
    """Get current grid mode (LONG/SHORT)"""
    try:
        mode = get_config_value('grid.mode', 'GRIDBOT_GRID_MODE', 'LONG').upper()
        return jsonify({
            'success': True,
            'mode': mode,
            'description': 'LONG = Buy below, SHORT = Sell above'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@grid_mode_bp.route('/api/bot/grid-mode', methods=['POST'])
def toggle_grid_mode():
    """Toggle between LONG and SHORT mode (with auto-restart)"""
    try:
        data = request.get_json()
        new_mode = data.get('mode', '').upper()
        auto_restart = data.get('auto_restart', True)  # Default: restart automatically
        
        if new_mode not in ['LONG', 'SHORT']:
            return jsonify({
                'success': False,
                'error': 'Mode must be LONG or SHORT'
            }), 400
        
        # Get current mode to check if actual change
        current_mode = get_config_value('grid.mode', 'GRIDBOT_GRID_MODE', 'LONG').upper()
        if current_mode == new_mode:
            return jsonify({
                'success': True,
                'mode': new_mode,
                'message': f'Already in {new_mode} mode',
                'changed': False
            })
        
        # Read YAML config file
        with open(CONFIG_FILE, 'r') as f:
            config_data = yaml.safe_load(f)
        
        # Update grid mode in YAML
        if 'grid' not in config_data:
            config_data['grid'] = {}
        if 'behavior' not in config_data['grid']:
            config_data['grid']['behavior'] = {}
        
        config_data['grid']['behavior']['mode'] = new_mode
        
        # Write back to YAML
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
        
        # Reload config
        reload_config()
        
        # Update environment variable
        os.environ['GRIDBOT_GRID_MODE'] = new_mode
        
        log.info(f"Grid mode changed: {current_mode} → {new_mode}")
        
        # Auto-restart bot if enabled
        restart_status = None
        if auto_restart:
            try:
                from webui.backend.utils.pm2_adapter import get_pm2_adapter, should_use_pm2
                
                if should_use_pm2():
                    pm2 = get_pm2_adapter()
                    success, message = pm2.restart_process('gridbot-live')
                    restart_status = {
                        'success': success,
                        'message': message
                    }
                    log.info(f"Bot restart triggered: {message}")
                else:
                    restart_status = {
                        'success': False,
                        'message': 'PM2 not enabled - please restart bot manually'
                    }
            except Exception as e:
                log.error(f"Error restarting bot: {e}")
                restart_status = {
                    'success': False,
                    'message': f'Restart failed: {str(e)}'
                }
        
        response = {
            'success': True,
            'mode': new_mode,
            'changed': True,
            'message': f'Grid mode switched to {new_mode}',
        }
        
        if restart_status:
            response['restart'] = restart_status
            if restart_status['success']:
                response['message'] += ' - Bot restarted successfully'
            else:
                response['message'] += f" - {restart_status['message']}"
        else:
            response['warning'] = 'Bot restart required for mode transition to take effect'
            response['requires_restart'] = True
        
        return jsonify(response)
        
    except Exception as e:
        log.error(f"Error toggling grid mode: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
