"""
Instance Manager API Routes

Provides REST API endpoints for managing multiple bot instances.
Supports creating, starting, stopping, and monitoring bot instances.
"""

from flask import Blueprint, jsonify, request
import logging
import json
from pathlib import Path
from typing import Optional, Dict, Any
import subprocess
import os
import yaml

logger = logging.getLogger(__name__)

# Create blueprint
instance_bp = Blueprint('instance_manager', __name__, url_prefix='/api/instances')

# Instance configuration directory
INSTANCES_DIR = Path('data/instances')
INSTANCES_DIR.mkdir(parents=True, exist_ok=True)

# PM2 ecosystem file
PM2_ECOSYSTEM_FILE = Path('ecosystem.config.js')


def get_pm2_adapter():
    """Get PM2 adapter instance"""
    try:
        from webui.backend.utils.pm2_adapter import PM2Adapter, should_use_pm2
        if should_use_pm2():
            return PM2Adapter()
        return None
    except ImportError:
        return None


def load_instance_config(instance_id: str) -> Optional[Dict[str, Any]]:
    """Load instance configuration from file"""
    config_file = INSTANCES_DIR / f"{instance_id}.json"
    if not config_file.exists():
        return None
    
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load instance config {instance_id}: {e}")
        return None


def save_instance_config(instance_id: str, config: Dict[str, Any]) -> bool:
    """Save instance configuration to file"""
    config_file = INSTANCES_DIR / f"{instance_id}.json"
    
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save instance config {instance_id}: {e}")
        return False


def delete_instance_config(instance_id: str) -> bool:
    """Delete instance configuration file"""
    config_file = INSTANCES_DIR / f"{instance_id}.json"
    
    try:
        if config_file.exists():
            config_file.unlink()
        return True
    except Exception as e:
        logger.error(f"Failed to delete instance config {instance_id}: {e}")
        return False


def list_instance_configs() -> Dict[str, Dict[str, Any]]:
    """List all instance configurations"""
    instances = {}
    
    for config_file in INSTANCES_DIR.glob("*.json"):
        instance_id = config_file.stem
        config = load_instance_config(instance_id)
        if config:
            instances[instance_id] = config
    
    return instances


def get_instance_status(instance_id: str, pm2: Optional[Any] = None) -> Dict[str, Any]:
    """Get instance runtime status from PM2"""
    if pm2 is None:
        pm2 = get_pm2_adapter()
    
    if not pm2:
        return {
            'status': 'unknown',
            'message': 'PM2 not available'
        }
    
    # Get PM2 status
    pm2_status = pm2.get_bot_status(instance_id)
    
    if not pm2_status:
        return {
            'status': 'stopped',
            'pid': None,
            'uptime': 0,
            'cpu': 0,
            'memory': 0
        }
    
    return {
        'status': pm2_status.get('status', 'unknown'),
        'pid': pm2_status.get('pid'),
        'uptime': pm2_status.get('uptime', 0),
        'cpu': pm2_status.get('cpu', 0),
        'memory': pm2_status.get('memory', 0),
        'restarts': pm2_status.get('restarts', 0)
    }


def apply_strategy_template(template: str) -> Dict[str, Any]:
    """Apply strategy template to get grid configuration"""
    templates = {
        'conservative': {
            'lower_range': 90000,
            'upper_range': 110000,
            'grid_step': 1000,
            'lot_size': 1,
            'take_profit_percent': 0.5,
            'stop_loss_percent': 2.0
        },
        'aggressive': {
            'lower_range': 85000,
            'upper_range': 105000,
            'grid_step': 200,
            'lot_size': 5,
            'take_profit_percent': 0.3,
            'stop_loss_percent': 3.0
        },
        'balanced': {
            'lower_range': 88000,
            'upper_range': 108000,
            'grid_step': 500,
            'lot_size': 2,
            'take_profit_percent': 0.4,
            'stop_loss_percent': 2.5
        },
        'custom': {
            'lower_range': 90000,
            'upper_range': 110000,
            'grid_step': 500,
            'lot_size': 1,
            'take_profit_percent': 0.5,
            'stop_loss_percent': 2.0
        }
    }
    
    return templates.get(template, templates['balanced'])


@instance_bp.route('', methods=['GET'])
@instance_bp.route('/', methods=['GET'])
def get_instances():
    """
    V6.0 API: List all configured instances (Instance = Symbol + Mode)
    Root endpoint for /api/instances
    
    Reads from config/symbols.yaml and returns instances in v6.0 format.
    """
    try:
        from config.loader import get_all_instances
        
        # Get all instances from YAML config (returns Dict[name, InstanceConfig])
        instances = get_all_instances(enabled_only=False)
        instance_list = []
        
        for name, config in instances.items():
            # InstanceConfig has attributes like symbol, mode, product_id, grid, safety, etc.
            grid_geom = config.grid.geometry if config.grid else None
            grid_limits = config.grid.limits if config.grid else None
            
            instance_list.append({
                'name': name,
                'symbol': config.symbol,
                'mode': config.mode.value if hasattr(config.mode, 'value') else str(config.mode),
                'enabled': config.enabled,
                'product_id': config.product_id,
                'grid': {
                    'lower': grid_geom.lower if grid_geom else None,
                    'upper': grid_geom.upper if grid_geom else None,
                    'step': grid_geom.step if grid_geom else None,
                    'reference': grid_geom.reference if grid_geom else None,
                } if grid_geom else {},
                'safety': {
                    'max_positions': grid_limits.max_open_positions if grid_limits else None,
                    'lot_size': grid_limits.lot_size if grid_limits else None,
                } if grid_limits else {},
                'rsi': {
                    'stop_threshold': config.safety.rsi.stop_threshold if config.safety and config.safety.rsi else None,
                    'resume_threshold': config.safety.rsi.resume_threshold if config.safety and config.safety.rsi else None,
                } if config.safety and config.safety.rsi else {},
                'database_file': f"data/bot_events_{name}.db",
                'monitoring_file': f"data/monitoring_snapshot_{name}.json"
            })
        
        return jsonify({
            'instances': instance_list,
            'count': len(instance_list),
            'enabled_count': sum(1 for i in instance_list if i.get('enabled', False)),
            'config_version': '6.0'
        })
    except Exception as e:
        logger.error(f"Error loading instances: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'instances': []}), 500


def parse_instance_name(instance_name):
    """Parse instance name like BTCUSD_LONG into {symbol, mode}"""
    if not instance_name or '_' not in instance_name:
        return None
    parts = instance_name.rsplit('_', 1)
    if len(parts) != 2:
        return None
    symbol, mode = parts
    if mode not in ['LONG', 'SHORT']:
        return None
    return {'symbol': symbol, 'mode': mode}


@instance_bp.route('/list', methods=['GET'])
def list_instances():
    """
    List all bot instances with their status
    
    Returns:
        - List of instances with configuration and runtime status
    """
    try:
        pm2 = get_pm2_adapter()
        configs = list_instance_configs()
        
        instances = []
        for instance_id, config in configs.items():
            # Get runtime status
            status = get_instance_status(instance_id, pm2)
            
            # Combine config and status
            instance = {
                'id': instance_id,
                'name': config.get('name', instance_id),
                'mode': config.get('mode', 'demo'),
                'strategy': config.get('strategy', 'balanced'),
                'grid': config.get('grid', {}),
                'status': status['status'],
                'pid': status.get('pid'),
                'uptime': status.get('uptime', 0),
                'cpu': status.get('cpu', 0),
                'memory': status.get('memory', 0),
                'created_at': config.get('created_at'),
                'pnl': config.get('pnl', 0),
                'positions': config.get('positions', 0)
            }
            instances.append(instance)
        
        return jsonify({
            'status': 'success',
            'instances': instances,
            'count': len(instances)
        })
        
    except Exception as e:
        logger.error(f"Error listing instances: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@instance_bp.route('/create', methods=['POST'])
def create_instance():
    """
    Create a new bot instance
    
    Body:
        - name: Instance name
        - mode: Trading mode (demo/live)
        - strategy: Strategy template (conservative/aggressive/balanced/custom)
        - grid: Optional grid configuration override
    
    Returns:
        - Created instance details
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('name'):
            return jsonify({'error': 'Instance name is required'}), 400
        
        name = data['name']
        mode = data.get('mode', 'demo')
        strategy = data.get('strategy', 'balanced')
        
        # Generate instance ID (sanitized name)
        instance_id = name.lower().replace(' ', '_').replace('-', '_')
        
        # Check if instance already exists
        if load_instance_config(instance_id):
            return jsonify({'error': f'Instance {instance_id} already exists'}), 409
        
        # Apply strategy template
        grid_config = apply_strategy_template(strategy)
        
        # Override with custom grid if provided
        if data.get('grid'):
            grid_config.update(data['grid'])
        
        # Create instance configuration
        from datetime import datetime
        config = {
            'id': instance_id,
            'name': name,
            'mode': mode,
            'strategy': strategy,
            'grid': grid_config,
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'pnl': 0,
            'positions': 0,
            'enabled': False
        }
        
        # Save configuration
        if not save_instance_config(instance_id, config):
            return jsonify({'error': 'Failed to save instance configuration'}), 500
        
        # Create instance-specific config.yaml
        config_file = INSTANCES_DIR / f"{instance_id}_config.yaml"
        
        # Load base config
        base_config_path = Path('config.yaml')
        if base_config_path.exists():
            with open(base_config_path, 'r') as f:
                base_config = yaml.safe_load(f)
        else:
            base_config = {}
        
        # Update with instance-specific settings
        base_config['trading_mode'] = mode
        base_config['grid'] = {
            'lower_range': grid_config['lower_range'],
            'upper_range': grid_config['upper_range'],
            'grid_step': grid_config['grid_step'],
            'lot_size': grid_config['lot_size']
        }
        base_config['take_profit_percent'] = grid_config['take_profit_percent']
        base_config['stop_loss_percent'] = grid_config['stop_loss_percent']
        
        # Save instance config
        with open(config_file, 'w') as f:
            yaml.dump(base_config, f, default_flow_style=False)
        
        logger.info(f"Created instance {instance_id} ({name}) - {mode} mode, {strategy} strategy")
        
        return jsonify({
            'status': 'success',
            'instance': config
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating instance: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@instance_bp.route('/<instance_id>/start', methods=['POST'])
def start_instance(instance_id: str):
    """
    Start a bot instance
    
    Path params:
        - instance_id: Instance ID to start
    
    Returns:
        - Success status
    """
    try:
        # Load instance config
        config = load_instance_config(instance_id)
        if not config:
            return jsonify({'error': f'Instance {instance_id} not found'}), 404
        
        # Get PM2 adapter
        pm2 = get_pm2_adapter()
        if not pm2:
            return jsonify({'error': 'PM2 not available'}), 503
        
        # Check if already running
        status = get_instance_status(instance_id, pm2)
        if status['status'] == 'online':
            return jsonify({'error': f'Instance {instance_id} is already running'}), 409
        
        # Get instance config file
        config_file = INSTANCES_DIR / f"{instance_id}_config.yaml"
        if not config_file.exists():
            return jsonify({'error': f'Instance config file not found'}), 404
        
        # Start with PM2
        result = pm2.start_bot(
            name=instance_id,
            script='bot/gridbot.py',
            config_file=str(config_file),
            mode=config.get('mode', 'demo')
        )
        
        if result.get('error'):
            return jsonify({'error': result['error']}), 500
        
        # Update instance config
        config['enabled'] = True
        save_instance_config(instance_id, config)
        
        logger.info(f"Started instance {instance_id}")
        
        return jsonify({
            'status': 'success',
            'message': f'Instance {instance_id} started',
            'pm2_result': result
        })
        
    except Exception as e:
        logger.error(f"Error starting instance {instance_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@instance_bp.route('/<instance_id>/stop', methods=['POST'])
def stop_instance(instance_id: str):
    """
    Stop a bot instance
    
    Path params:
        - instance_id: Instance ID to stop
    
    Returns:
        - Success status
    """
    try:
        # Load instance config
        config = load_instance_config(instance_id)
        if not config:
            return jsonify({'error': f'Instance {instance_id} not found'}), 404
        
        # Get PM2 adapter
        pm2 = get_pm2_adapter()
        if not pm2:
            return jsonify({'error': 'PM2 not available'}), 503
        
        # Stop with PM2
        result = pm2.stop_bot(instance_id)
        
        if result.get('error'):
            return jsonify({'error': result['error']}), 500
        
        # Update instance config
        config['enabled'] = False
        save_instance_config(instance_id, config)
        
        logger.info(f"Stopped instance {instance_id}")
        
        return jsonify({
            'status': 'success',
            'message': f'Instance {instance_id} stopped',
            'pm2_result': result
        })
        
    except Exception as e:
        logger.error(f"Error stopping instance {instance_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@instance_bp.route('/<instance_id>/restart', methods=['POST'])
def restart_instance(instance_id: str):
    """
    Restart a bot instance
    
    Path params:
        - instance_id: Instance ID to restart
    
    Returns:
        - Success status
    """
    try:
        # Load instance config
        config = load_instance_config(instance_id)
        if not config:
            return jsonify({'error': f'Instance {instance_id} not found'}), 404
        
        # Get PM2 adapter
        pm2 = get_pm2_adapter()
        if not pm2:
            return jsonify({'error': 'PM2 not available'}), 503
        
        # Restart with PM2
        result = pm2.restart_bot(instance_id)
        
        if result.get('error'):
            return jsonify({'error': result['error']}), 500
        
        logger.info(f"Restarted instance {instance_id}")
        
        return jsonify({
            'status': 'success',
            'message': f'Instance {instance_id} restarted',
            'pm2_result': result
        })
        
    except Exception as e:
        logger.error(f"Error restarting instance {instance_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@instance_bp.route('/<instance_id>/delete', methods=['DELETE'])
def delete_instance(instance_id: str):
    """
    Delete a bot instance
    
    Path params:
        - instance_id: Instance ID to delete
    
    Returns:
        - Success status
    """
    try:
        # Load instance config
        config = load_instance_config(instance_id)
        if not config:
            return jsonify({'error': f'Instance {instance_id} not found'}), 404
        
        # Get PM2 adapter
        pm2 = get_pm2_adapter()
        
        # Stop if running
        if pm2:
            status = get_instance_status(instance_id, pm2)
            if status['status'] == 'online':
                pm2.stop_bot(instance_id)
            
            # Delete from PM2
            pm2.delete_bot(instance_id)
        
        # Delete config files
        delete_instance_config(instance_id)
        
        config_file = INSTANCES_DIR / f"{instance_id}_config.yaml"
        if config_file.exists():
            config_file.unlink()
        
        logger.info(f"Deleted instance {instance_id}")
        
        return jsonify({
            'status': 'success',
            'message': f'Instance {instance_id} deleted'
        })
        
    except Exception as e:
        logger.error(f"Error deleting instance {instance_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@instance_bp.route('/<instance_id>/logs', methods=['GET'])
def get_instance_logs(instance_id: str):
    """
    Get logs for a bot instance
    
    Path params:
        - instance_id: Instance ID
    
    Query params:
        - lines: Number of log lines to return (default: 100)
    
    Returns:
        - Log lines
    """
    try:
        # Load instance config
        config = load_instance_config(instance_id)
        if not config:
            return jsonify({'error': f'Instance {instance_id} not found'}), 404
        
        lines = request.args.get('lines', 100, type=int)
        
        # Get PM2 adapter
        pm2 = get_pm2_adapter()
        if not pm2:
            return jsonify({'error': 'PM2 not available'}), 503
        
        # Get logs from PM2
        logs = pm2.get_logs(instance_id, lines=lines)
        
        return jsonify({
            'status': 'success',
            'logs': logs,
            'instance_id': instance_id
        })
        
    except Exception as e:
        logger.error(f"Error getting logs for instance {instance_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@instance_bp.route('/<instance_id>/configure', methods=['POST'])
def configure_instance(instance_id: str):
    """
    Update instance configuration
    
    Path params:
        - instance_id: Instance ID
    
    Body:
        - grid: Grid configuration
        - strategy: Strategy template
        - Other configuration fields
    
    Returns:
        - Updated configuration
    """
    try:
        # Load instance config
        config = load_instance_config(instance_id)
        if not config:
            return jsonify({'error': f'Instance {instance_id} not found'}), 404
        
        data = request.get_json()
        
        # Update configuration
        if 'grid' in data:
            config['grid'].update(data['grid'])
        
        if 'strategy' in data:
            config['strategy'] = data['strategy']
            # Reapply template
            template_config = apply_strategy_template(data['strategy'])
            config['grid'].update(template_config)
        
        # Save updated config
        if not save_instance_config(instance_id, config):
            return jsonify({'error': 'Failed to save configuration'}), 500
        
        # Update instance config.yaml
        config_file = INSTANCES_DIR / f"{instance_id}_config.yaml"
        if config_file.exists():
            with open(config_file, 'r') as f:
                yaml_config = yaml.safe_load(f)
            
            yaml_config['grid'] = {
                'lower_range': config['grid']['lower_range'],
                'upper_range': config['grid']['upper_range'],
                'grid_step': config['grid']['grid_step'],
                'lot_size': config['grid']['lot_size']
            }
            yaml_config['take_profit_percent'] = config['grid']['take_profit_percent']
            yaml_config['stop_loss_percent'] = config['grid']['stop_loss_percent']
            
            with open(config_file, 'w') as f:
                yaml.dump(yaml_config, f, default_flow_style=False)
        
        logger.info(f"Updated configuration for instance {instance_id}")
        
        return jsonify({
            'status': 'success',
            'instance': config
        })
        
    except Exception as e:
        logger.error(f"Error configuring instance {instance_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@instance_bp.route('/summary', methods=['GET'])
def get_instances_summary():
    """
    Get summary statistics for all instances
    
    Returns:
        - Total instances, running count, aggregate stats
    """
    try:
        pm2 = get_pm2_adapter()
        configs = list_instance_configs()
        
        total = len(configs)
        running = 0
        stopped = 0
        total_cpu = 0
        total_memory = 0
        total_pnl = 0
        total_positions = 0
        
        for instance_id, config in configs.items():
            status = get_instance_status(instance_id, pm2)
            
            if status['status'] == 'online':
                running += 1
                total_cpu += status.get('cpu', 0)
                total_memory += status.get('memory', 0)
            else:
                stopped += 1
            
            total_pnl += config.get('pnl', 0)
            total_positions += config.get('positions', 0)
        
        return jsonify({
            'status': 'success',
            'summary': {
                'total': total,
                'running': running,
                'stopped': stopped,
                'cpu': round(total_cpu, 2),
                'memory': round(total_memory, 2),
                'pnl': round(total_pnl, 2),
                'positions': total_positions
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting instances summary: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@instance_bp.route('/toggle', methods=['POST'])
def toggle_instance():
    """
    Toggle instance enabled/disabled status in config.yaml
    
    Request Body:
        instance: Instance name (e.g., "BTCUSD_LONG", "ETHUSD_LONG")
    
    Returns:
        - Updated instance status
    """
    try:
        data = request.get_json() or {}
        instance_name = data.get('instance')
        
        if not instance_name:
            return jsonify({'success': False, 'error': 'Instance name is required'}), 400
        
        # Load config.yaml
        config_path = Path('config.yaml')
        if not config_path.exists():
            return jsonify({'success': False, 'error': 'config.yaml not found'}), 404
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Check if instances section exists
        if 'instances' not in config:
            return jsonify({'success': False, 'error': 'No instances configured in config.yaml'}), 404
        
        # Find and toggle the instance
        if instance_name not in config['instances']:
            return jsonify({'success': False, 'error': f'Instance {instance_name} not found'}), 404
        
        current_enabled = config['instances'][instance_name].get('enabled', False)
        new_enabled = not current_enabled
        config['instances'][instance_name]['enabled'] = new_enabled
        
        # Save config.yaml
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        logger.info(f"✅ Toggled instance {instance_name}: enabled={new_enabled}")
        
        return jsonify({
            'success': True,
            'instance': instance_name,
            'enabled': new_enabled,
            'message': f'Instance {instance_name} {"enabled" if new_enabled else "disabled"}'
        })
        
    except Exception as e:
        logger.error(f"Error toggling instance: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
