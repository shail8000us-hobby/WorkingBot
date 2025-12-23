"""
Configuration management API endpoints.
RESTful API for managing bot configuration via WebUI.
"""

from flask import Blueprint, request, jsonify
from pathlib import Path
from typing import Dict, Any

from config.models import RootConfig, StrategyOverride
from config.loader import get_config, reload_config, save_config
from config.strategy_manager import StrategyManager
from config.watcher import ConfigHistory


# Create blueprint
config_api = Blueprint('config_api', __name__, url_prefix='/api/config')

# Global instances
_strategy_manager: StrategyManager = None
_config_history: ConfigHistory = None


def get_strategy_manager() -> StrategyManager:
    """Get global strategy manager instance"""
    global _strategy_manager
    if _strategy_manager is None:
        _strategy_manager = StrategyManager()
    return _strategy_manager


def get_config_history() -> ConfigHistory:
    """Get global config history instance"""
    global _config_history
    if _config_history is None:
        _config_history = ConfigHistory(max_history=20)
        # Save current config as first version
        _config_history.save_version(get_config())
    return _config_history


# ═══════════════════════════════════════════════════════════════════════════
# CONFIG ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@config_api.route('/current', methods=['GET'])
def get_current_config():
    """Get current configuration as JSON"""
    try:
        config = get_config()
        return jsonify({
            'status': 'success',
            'config': config.dict(exclude_none=True)
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@config_api.route('/reload', methods=['POST'])
def reload_current_config():
    """Reload configuration from disk"""
    try:
        config = reload_config()
        
        # Save to history
        history = get_config_history()
        history.save_version(config)
        
        return jsonify({
            'status': 'success',
            'message': 'Configuration reloaded successfully',
            'config': config.dict(exclude_none=True)
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400


@config_api.route('/update', methods=['POST'])
def update_config():
    """Update configuration (hot reload)"""
    try:
        new_config_data = request.json
        
        if not new_config_data:
            return jsonify({
                'status': 'error',
                'message': 'No configuration data provided'
            }), 400
        
        # Validate new config
        new_config = RootConfig(**new_config_data)
        new_config.validate_cross_field_constraints()
        
        # Save to file
        save_config(new_config, 'config.yaml')
        
        # Reload
        reload_config()
        
        # Save to history
        history = get_config_history()
        history.save_version(new_config)
        
        return jsonify({
            'status': 'success',
            'message': 'Configuration updated successfully',
            'config': new_config.dict(exclude_none=True)
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400


@config_api.route('/validate', methods=['POST'])
def validate_config():
    """Validate configuration without applying"""
    try:
        config_data = request.json
        
        if not config_data:
            return jsonify({
                'status': 'error',
                'message': 'No configuration data provided'
            }), 400
        
        # Try to create and validate
        config = RootConfig(**config_data)
        config.validate_cross_field_constraints()
        
        return jsonify({
            'status': 'success',
            'valid': True,
            'message': 'Configuration is valid'
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'valid': False,
            'message': str(e)
        }), 400


# ═══════════════════════════════════════════════════════════════════════════
# STRATEGY ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@config_api.route('/strategies', methods=['GET'])
def list_strategies():
    """List all defined strategies"""
    try:
        manager = get_strategy_manager()
        
        strategies = []
        for name in manager.list_strategies():
            try:
                summary = manager.get_strategy_summary(name)
                strategies.append(summary)
            except Exception as e:
                print(f"Error getting summary for {name}: {e}")
        
        return jsonify({
            'status': 'success',
            'strategies': strategies,
            'active': manager.active_strategies
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@config_api.route('/strategies/<name>', methods=['GET'])
def get_strategy(name: str):
    """Get specific strategy configuration"""
    try:
        manager = get_strategy_manager()
        strategy = manager.get_strategy(name)
        summary = manager.get_strategy_summary(name)
        
        return jsonify({
            'status': 'success',
            'strategy': summary,
            'config': strategy.dict(exclude_none=True)
        })
    except KeyError:
        return jsonify({
            'status': 'error',
            'message': f'Strategy not found: {name}'
        }), 404
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@config_api.route('/strategies/<name>/activate', methods=['POST'])
def activate_strategy(name: str):
    """Activate a strategy"""
    try:
        manager = get_strategy_manager()
        manager.activate_strategy(name)
        
        # Update config file
        config = get_config()
        if name not in config.active_strategies:
            config.active_strategies.append(name)
            save_config(config, 'config.yaml')
        
        return jsonify({
            'status': 'success',
            'message': f'Strategy activated: {name}',
            'active': manager.active_strategies
        })
    except KeyError:
        return jsonify({
            'status': 'error',
            'message': f'Strategy not found: {name}'
        }), 404
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@config_api.route('/strategies/<name>/deactivate', methods=['POST'])
def deactivate_strategy(name: str):
    """Deactivate a strategy"""
    try:
        manager = get_strategy_manager()
        manager.deactivate_strategy(name)
        
        # Update config file
        config = get_config()
        if name in config.active_strategies:
            config.active_strategies.remove(name)
            save_config(config, 'config.yaml')
        
        return jsonify({
            'status': 'success',
            'message': f'Strategy deactivated: {name}',
            'active': manager.active_strategies
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@config_api.route('/strategies', methods=['POST'])
def create_strategy():
    """Create new strategy"""
    try:
        data = request.json
        
        if not data or 'name' not in data:
            return jsonify({
                'status': 'error',
                'message': 'Strategy name required'
            }), 400
        
        # Create strategy override
        strategy_def = StrategyOverride(
            name=data['name'],
            description=data.get('description'),
            extends=data.get('extends'),
            overrides=data.get('overrides', {}),
            enabled=data.get('enabled', True)
        )
        
        # Add to manager
        manager = get_strategy_manager()
        manager.add_strategy(strategy_def)
        
        # Save config
        config = get_config()
        save_config(config, 'config.yaml')
        
        return jsonify({
            'status': 'success',
            'message': f'Strategy created: {data["name"]}',
            'strategy': manager.get_strategy_summary(data['name'])
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400


@config_api.route('/strategies/<name>', methods=['DELETE'])
def delete_strategy(name: str):
    """Delete strategy"""
    try:
        manager = get_strategy_manager()
        manager.remove_strategy(name)
        
        # Save config
        config = get_config()
        save_config(config, 'config.yaml')
        
        return jsonify({
            'status': 'success',
            'message': f'Strategy deleted: {name}'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


# ═══════════════════════════════════════════════════════════════════════════
# HISTORY ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@config_api.route('/history', methods=['GET'])
def get_history():
    """Get configuration history"""
    try:
        history = get_config_history()
        versions = history.list_versions()
        
        return jsonify({
            'status': 'success',
            'versions': versions,
            'current_index': history.current_index
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@config_api.route('/history/rollback', methods=['POST'])
def rollback_config():
    """Rollback to previous configuration"""
    try:
        steps = request.json.get('steps', 1) if request.json else 1
        
        history = get_config_history()
        previous_config = history.rollback(steps)
        
        # Save rolled-back config
        save_config(previous_config, 'config.yaml')
        reload_config()
        
        return jsonify({
            'status': 'success',
            'message': f'Rolled back {steps} version(s)',
            'config': previous_config.dict(exclude_none=True)
        })
        
    except ValueError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@config_api.route('/history/rollforward', methods=['POST'])
def rollforward_config():
    """Roll forward to newer configuration"""
    try:
        steps = request.json.get('steps', 1) if request.json else 1
        
        history = get_config_history()
        newer_config = history.rollforward(steps)
        
        # Save rolled-forward config
        save_config(newer_config, 'config.yaml')
        reload_config()
        
        return jsonify({
            'status': 'success',
            'message': f'Rolled forward {steps} version(s)',
            'config': newer_config.dict(exclude_none=True)
        })
        
    except ValueError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


# ═══════════════════════════════════════════════════════════════════════════
# SECTION ENDPOINTS (for easy partial updates)
# ═══════════════════════════════════════════════════════════════════════════

@config_api.route('/sections/<section>', methods=['GET'])
def get_section(section: str):
    """Get specific configuration section"""
    try:
        config = get_config()
        section_data = getattr(config, section, None)
        
        if section_data is None:
            return jsonify({
                'status': 'error',
                'message': f'Section not found: {section}'
            }), 404
        
        # Convert to dict
        if hasattr(section_data, 'dict'):
            section_dict = section_data.dict(exclude_none=True)
        else:
            section_dict = section_data
        
        return jsonify({
            'status': 'success',
            'section': section,
            'data': section_dict
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@config_api.route('/sections/<section>', methods=['PUT'])
def update_section(section: str):
    """Update specific configuration section"""
    try:
        new_section_data = request.json
        
        if not new_section_data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400
        
        # Get current config
        config = get_config()
        config_dict = config.dict()
        
        # Update section
        config_dict[section] = new_section_data
        
        # Validate
        new_config = RootConfig(**config_dict)
        new_config.validate_cross_field_constraints()
        
        # Save
        save_config(new_config, 'config.yaml')
        reload_config()
        
        # Save to history
        history = get_config_history()
        history.save_version(new_config)
        
        return jsonify({
            'status': 'success',
            'message': f'Section updated: {section}',
            'data': new_section_data
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400
