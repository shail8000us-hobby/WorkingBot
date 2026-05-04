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
    """Set grid mode to LONG, SHORT, or RANGE (dual-zone)."""
    try:
        data = request.get_json()
        new_mode = data.get('mode', '').upper()
        auto_restart = data.get('auto_restart', True)  # Default: restart automatically

        if new_mode not in ['LONG', 'SHORT', 'RANGE']:
            return jsonify({
                'success': False,
                'error': 'Mode must be LONG, SHORT, or RANGE'
            }), 400

        # RANGE mode: write dual_mode section and enable both instances
        if new_mode == 'RANGE':
            return _activate_range_mode(data, auto_restart)
        
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


def _activate_range_mode(data: dict, auto_restart: bool):
    """Write dual_mode config and enable both LONG + SHORT instances for RANGE mode."""
    try:
        symbol = data.get('symbol', 'BTCUSD').upper()
        anchor = float(data.get('anchor', 75000))
        lower = float(data.get('lower', 73000))
        upper = float(data.get('upper', 77000))
        step = float(data.get('step', 500))
        lot_size = int(data.get('lot_size', 5))
        hysteresis = float(data.get('hysteresis', 200))
        max_open = int(data.get('max_open_positions', 20))
        product_id = int(data.get('product_id', 27))

        if not (lower < anchor < upper):
            return jsonify({'success': False, 'error': 'RANGE config invalid: lower < anchor < upper required'}), 400

        with open(CONFIG_FILE, 'r') as f:
            config_data = yaml.safe_load(f)

        # Write dual_mode section
        config_data['dual_mode'] = {
            'enabled': True,
            'symbol': symbol,
            'anchor': anchor,
            'lower': lower,
            'upper': upper,
            'step': step,
            'lot_size': lot_size,
            'hysteresis': hysteresis,
            'max_open_positions': max_open,
        }

        # Enable both instances with zone-specific bounds, disable others for same symbol
        long_name = f"{symbol}_LONG"
        short_name = f"{symbol}_SHORT"

        if 'instances' not in config_data:
            config_data['instances'] = {}

        ref_long = (lower + anchor) / 2
        ref_short = (anchor + upper) / 2

        for inst_name, ref, inst_lower, inst_upper in [
            (long_name,  ref_long,  lower,  anchor),
            (short_name, ref_short, anchor, upper),
        ]:
            if inst_name not in config_data['instances']:
                config_data['instances'][inst_name] = {}
            inst = config_data['instances'][inst_name]
            inst['symbol'] = symbol
            inst['mode'] = inst_name.split('_')[-1]
            inst['enabled'] = True
            inst['product_id'] = product_id
            if 'grid' not in inst:
                inst['grid'] = {}
            inst['grid']['geometry'] = {
                'reference': ref,
                'lower': inst_lower,
                'upper': inst_upper,
                'step': step,
            }
            inst['grid'].setdefault('limits', {}).update({
                'max_open_positions': max_open,
                'lot_size': lot_size,
                'max_open_orders': max_open,
                'max_qty_per_order': lot_size,
            })
            inst['grid'].setdefault('behavior', {
                'strict_grid': True,
                'rung_snap_mode': 'below',
                'tick_size': 0.5,
                'dynamic_tick_size': True,
                'seed_initial_count': 0,
            })
            inst.setdefault('safety', {
                'max_account_loss_inr': 250000,
                'min_liquidation_distance_pct': 50,
                'rsi': {'enabled': False},
            })

        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

        reload_config()
        log.info(f"RANGE mode activated: anchor={anchor}, [{lower}, {upper}], H={hysteresis}")

        return jsonify({
            'success': True,
            'mode': 'RANGE',
            'changed': True,
            'message': f'RANGE mode activated — {long_name} and {short_name} configured',
            'anchor': anchor,
            'lower': lower,
            'upper': upper,
            'hysteresis': hysteresis,
            'warning': 'Restart both gridbot instances and their Guardian processes for RANGE mode to take effect',
        })

    except Exception as e:
        log.error(f"Error activating RANGE mode: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
