"""
Configuration Routes Blueprint

This module handles all API routes related to configuration management.

⚠️ DEPRECATION NOTICE: This module manages grid_config.env and is being phased out.
   New configuration should use yaml_config_api.py and config.yaml as single source of truth.
   Legacy routes maintained for backward compatibility during migration.

Routes:
- GET  /api/config - Get current configuration
- POST /api/config - Update configuration
- GET  /api/config/verify - Verify configuration integrity
- POST /api/config/apply - Apply pending configuration changes
- GET  /api/diagnostics/config-usage - Get config usage statistics
- GET  /api/config/feature-flags - Get feature flags (Week 3)
- POST /api/config/feature-flags - Toggle feature flag (Week 3)

Dependencies:
- bot.config.aliases (configuration aliasing)
- bot.utils.env_loader (mode management)
- dotenv for env file manipulation
- Atomic file writes

Refactored from app.py (8,850 lines)
Date: 2025-10-31
Updated: 2025-11-12 (Feature flags)
Updated: 2025-11-15 (YAML migration notice)
"""

import os
import logging
import sys
from pathlib import Path
from datetime import datetime
from flask import Blueprint, jsonify, request

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from webui.backend.utils.auth import require_auth
from webui.backend.utils.yaml_config import get_config_value

try:
    from bot.config.aliases import (
        ALIAS_TO_CANONICAL,
        legacy_key_used,
        strip_legacy_keys,
        upgrade_mapping
    )
    from bot.refactor.compat import usage_snapshot
    ALIASES_AVAILABLE = True
except ImportError:
    ALIASES_AVAILABLE = False

log = logging.getLogger(__name__)

# Create blueprint
config_bp = Blueprint('config', __name__)

# File paths
BASE_DIR = Path(__file__).parent.parent.parent.parent
CONFIG_FILE = BASE_DIR / "grid_config.env"

# ============================================================================
# Route Handlers
# ============================================================================

@config_bp.route('/api/config', methods=['GET'])
@require_auth
def get_config():
    """
    Get current configuration
    
    Returns the current configuration from grid_config.env with optional
    redaction of sensitive keys.
    
    v6.0: Supports per-instance configuration
    Query params:
        instance: Optional instance name (e.g., BTCUSD_LONG)
    
    Returns:
        JSON response with configuration
    
    Example:
        GET /api/config?instance=BTCUSD_LONG
    """
    try:
        # v6.0: Extract instance parameter
        instance = request.args.get('instance')
        
        log.info(f"Config request from {request.remote_addr}" + 
                (f" for instance {instance}" if instance else ""))
        
        config = _load_config(redact=True, instance=instance)
        return jsonify(config), 200
        
    except Exception as e:
        log.error(f"Config fetch failed: {e}")
        return jsonify({'error': str(e)}), 500


@config_bp.route('/api/config/all-legacy', methods=['GET'])
def get_all_config():
    """
    Get ALL configuration from grid_config.env (LEGACY - use /api/config/all from yaml_config_bp instead)
    
    Returns complete configuration with metadata about secrets.
    
    Returns:
        JSON response with config and secrets metadata
    """
    try:
        config = _load_config(redact=True)
        
        # Build secrets metadata
        secrets_meta = {}
        for key, value in config.items():
            if _is_secret_key(key):
                secrets_meta[key] = {
                    'redacted': True,
                    'has_value': bool(value) and value != '***REDACTED***'
                }
        
        return jsonify({
            'success': True,
            'config': config,
            'secrets': secrets_meta
        }), 200
        
    except Exception as e:
        log.error(f"Error getting all config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@config_bp.route('/api/config/flat', methods=['GET'])
def get_flat_config():
    """
    Get flattened configuration with metadata
    
    Returns configuration in flat format expected by frontend,
    with metadata about each parameter (section, redacted status, etc.)
    
    Returns:
        JSON response with flat config and metadata
    
    Example:
        GET /api/config/flat
        Response: {
            "success": true,
            "config": {"SYMBOL": "BTCUSD", ...},
            "meta": {"SYMBOL": {"section": "Trading", "redacted": false, ...}, ...}
        }
    """
    try:
        config = _load_config(redact=True)
        
        # Build metadata for each config key
        metadata = {}
        for key in config.keys():
            metadata[key] = {
                'section': _get_key_section(key),
                'redacted': _is_secret_key(key),
                'has_value': bool(config[key]),
                'source_key': key,
                'legacy_sources': []
            }
        
        return jsonify({
            'success': True,
            'config': config,
            'meta': metadata
        }), 200
        
    except Exception as e:
        log.error(f"Flat config fetch failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@config_bp.route('/api/config/update', methods=['POST'])
def update_all_config():
    """
    Update multiple configuration values in grid_config.env
    
    CRITICAL VALIDATION: Rejects requests with empty critical parameters
    to prevent configuration corruption when switching grid modes or bulk updates.
    
    Request Body:
        {
            "KEY_NAME": "value",
            "ANOTHER_KEY": "value2",
            ...
        }
    
    Returns:
        JSON response with success status
    """
    try:
        updates = request.json
        
        if not updates:
            return jsonify({
                'success': False,
                'error': 'No configuration updates provided'
            }), 400
        
        # CRITICAL VALIDATION: Define required parameters that must not be empty
        CRITICAL_PARAMETERS = {
            'GRIDBOT_TICK_SIZE', 'GRIDBOT_LOWER', 'GRIDBOT_UPPER', 'GRIDBOT_STEP',
            'GRIDBOT_LOT', 'GRIDBOT_MAX_OPEN', 'GRIDBOT_SYMBOL', 'GRIDBOT_REF',
            'TRADING_MODE', 'GRIDBOT_GRID_MODE', 'GRIDBOT_SEED_INITIAL_COUNT'
        }
        
        # Check if any critical parameters are being set to empty
        empty_critical = []
        for key in CRITICAL_PARAMETERS:
            if key in updates and (updates[key] == '' or updates[key] is None):
                empty_critical.append(key)
        
        # Load current config to detect changes
        current_config = _load_config(redact=False)
        
        # Analyze changes and generate impact summary
        changes_summary = _analyze_config_changes(current_config, updates)
        
        # Add validation errors to the changes summary
        if empty_critical:
            changes_summary['validation_errors'] = empty_critical
            changes_summary['has_errors'] = True
            changes_summary['error_message'] = 'Cannot save: The following critical parameters are empty'
        else:
            changes_summary['has_errors'] = False
        
        # ALWAYS require confirmation unless explicitly confirmed
        if not request.json.get('confirmed', False):
            log.warning(f"Configuration save requires confirmation. Changes: {changes_summary.get('total_changes', 0)}, Errors: {len(empty_critical)}")
            return jsonify({
                'success': False,
                'require_confirmation': True,
                'changes_summary': changes_summary,
                'message': 'Please review and confirm your configuration changes'
            }), 200  # 200 OK but requires confirmation
        
        # If confirmed but has validation errors, reject
        if empty_critical:
            log.error(f"BLOCKED: Attempt to set critical parameters to empty: {empty_critical}")
            return jsonify({
                'success': False,
                'error': 'Configuration validation failed',
                'message': f'Cannot set critical parameters to empty values',
                'empty_parameters': empty_critical,
                'details': 'Please fill in all required grid parameters before saving. Critical parameters must have values.'
            }), 400
        
        log.info(f"Config update: {len(updates)} parameter(s)" + (" [CONFIRMED]" if request.json.get('confirmed') else ""))
        
        # Remove the 'confirmed' flag from updates (don't save it to config)
        updates_to_save = {k: v for k, v in updates.items() if k != 'confirmed'}
        
        # Read current file
        with open(CONFIG_FILE, 'r') as f:
            lines = f.readlines()
        
        # Update lines (SKIP EMPTY VALUES - critical bug fix)
        updated_lines = []
        updated_keys = set()
        skipped_empty = []
        
        for line in lines:
            stripped = line.strip()
            # Check if this line contains a key we want to update
            if stripped and not stripped.startswith('#') and '=' in stripped:
                key = stripped.split('=', 1)[0].strip()
                if key in updates_to_save:
                    # CRITICAL FIX: Skip empty values to prevent config corruption
                    value = updates_to_save[key]
                    if value == '' or value is None:
                        skipped_empty.append(key)
                        log.warning(f"Skipping empty value for {key} (would corrupt config)")
                        updated_lines.append(line)  # Keep original line
                        continue
                    
                    # Strip quotes from select/dropdown values to prevent os.getenv() issues
                    # WebUI might send quoted values, but .env format doesn't need them
                    if isinstance(value, str) and value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]  # Remove surrounding quotes
                    
                    # Preserve indentation
                    indent = len(line) - len(line.lstrip())
                    updated_lines.append(' ' * indent + f'{key}={value}\n')
                    updated_keys.add(key)
                    continue
            updated_lines.append(line)
        
        # Add any new keys that weren't found (skip empty values)
        for key, value in updates_to_save.items():
            if key not in updated_keys and key not in skipped_empty:
                if value == '' or value is None:
                    skipped_empty.append(key)
                    log.warning(f"Skipping new empty parameter {key}")
                    continue
                # Strip quotes from select/dropdown values
                if isinstance(value, str) and value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                updated_lines.append(f'{key}={value}\n')
                updated_keys.add(key)
        
        # Write back atomically
        _atomic_write_text(CONFIG_FILE, ''.join(updated_lines))
        
        if skipped_empty:
            log.warning(f"Skipped {len(skipped_empty)} empty parameters: {skipped_empty[:5]}...")
        
        # AUTO-CONFIRM: Check if bot is waiting for confirmation and auto-create the file
        import glob
        import time
        time.sleep(1)  # Give bot 1 second to detect the config change
        
        # Look for any .confirm_* files that bot is waiting for
        log_file = BASE_DIR / 'bot' / 'logs' / 'bot.log'
        if log_file.exists():
            try:
                # Read last 100 lines of bot log
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    recent_logs = ''.join(lines[-100:])
                
                # Check if bot is waiting for confirmation
                if 'touch .confirm_' in recent_logs:
                    import re
                    match = re.search(r'touch\s+(\.confirm_[a-f0-9]+)', recent_logs)
                    if match:
                        confirm_file = match.group(1)
                        confirm_path = BASE_DIR / confirm_file
                        if not confirm_path.exists():
                            confirm_path.touch()
                            log.info(f"✅ AUTO-CONFIRMED: Created {confirm_file} for bot")
            except Exception as e:
                log.warning(f"Failed to auto-confirm: {e}")
        
        # Generate appropriate message based on whether this was confirmed
        if request.json.get('confirmed'):
            message = f'✅ Configuration changes applied successfully! Updated {len(updated_keys)} parameter(s).'
        else:
            message = f'Updated {len(updated_keys)} configuration value(s)'
        
        response = {
            'success': True,
            'message': message,
            'updated_keys': list(updated_keys)
        }
        
        if skipped_empty:
            response['warning'] = f'Skipped {len(skipped_empty)} empty parameters (would corrupt config)'
            response['skipped_keys'] = skipped_empty[:10]
        
        return jsonify(response), 200
        
    except Exception as e:
        log.error(f"Config update failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@config_bp.route('/api/config', methods=['POST'])
def update_config():
    """
    Save configuration changes
    
    Updates grid_config.env with new configuration values.
    Validates keys and handles legacy alias mapping.
    
    CRITICAL VALIDATION: Rejects requests with empty critical parameters
    to prevent configuration corruption.
    
    Request Body:
        {
            "KEY_NAME": "value",
            ...
        }
    
    Returns:
        JSON response with success status
    """
    try:
        new_config = request.json
        if not new_config:
            return jsonify({
                'success': False,
                'message': 'No configuration data provided'
            }), 400
        
        # CRITICAL VALIDATION: Define required parameters that must not be empty
        CRITICAL_PARAMETERS = {
            'GRIDBOT_TICK_SIZE', 'GRIDBOT_LOWER', 'GRIDBOT_UPPER', 'GRIDBOT_STEP',
            'GRIDBOT_LOT', 'GRIDBOT_MAX_OPEN', 'GRIDBOT_SYMBOL', 'GRIDBOT_REF',
            'TRADING_MODE', 'GRIDBOT_GRID_MODE', 'GRIDBOT_SEED_INITIAL_COUNT'
        }
        
        # Check if any critical parameters are being set to empty or invalid
        empty_critical = []
        invalid_critical = []
        
        for key in CRITICAL_PARAMETERS:
            if key in new_config:
                value = new_config[key]
                
                # Check for empty values
                if value == '' or value is None:
                    empty_critical.append(key)
                    continue
                
                # Validate numeric parameters
                try:
                    if key in ['GRIDBOT_STEP', 'GRIDBOT_TICK_SIZE', 'GRIDBOT_LOT']:
                        num_val = float(value)
                        if num_val <= 0:
                            invalid_critical.append(f"{key} must be > 0 (got {num_val})")
                    
                    elif key in ['GRIDBOT_LOWER', 'GRIDBOT_UPPER', 'GRIDBOT_REF']:
                        num_val = float(value)
                        if num_val <= 0:
                            invalid_critical.append(f"{key} must be > 0 (got {num_val})")
                    
                    elif key == 'GRIDBOT_MAX_OPEN':
                        num_val = int(value)
                        if num_val < 0:
                            invalid_critical.append(f"{key} must be >= 0 (got {num_val})")
                
                except (ValueError, TypeError):
                    invalid_critical.append(f"{key} must be a valid number")
        
        # Validate grid bounds relationship
        if 'GRIDBOT_LOWER' in new_config and 'GRIDBOT_UPPER' in new_config:
            try:
                lower = float(new_config['GRIDBOT_LOWER'])
                upper = float(new_config['GRIDBOT_UPPER'])
                if lower >= upper:
                    invalid_critical.append(f"GRIDBOT_LOWER ({lower}) must be < GRIDBOT_UPPER ({upper})")
            except (ValueError, TypeError):
                pass  # Already caught above
        
        # Load current config
        if not CONFIG_FILE.exists():
            return jsonify({
                'success': False,
                'message': 'Configuration file not found'
            }), 404
        
        # Load current config to detect changes
        current_config = _load_config(redact=False)
        
        # Analyze changes and generate impact summary
        changes_summary = _analyze_config_changes(current_config, new_config)
        
        # Add validation errors to the changes summary
        all_errors = empty_critical + invalid_critical
        if all_errors:
            changes_summary['validation_errors'] = all_errors
            changes_summary['has_errors'] = True
            changes_summary['error_message'] = 'Cannot save: Configuration validation failed'
        else:
            changes_summary['has_errors'] = False
        
        # Reject immediately if there are validation errors
        if all_errors:
            log.error(f"BLOCKED: Configuration validation failed: {all_errors}")
            return jsonify({
                'success': False,
                'validation_errors': all_errors,
                'message': 'Configuration validation failed'
            }), 422  # Unprocessable Entity
        
        # ALWAYS require confirmation unless explicitly confirmed
        if not new_config.get('confirmed', False):
            log.warning(f"Configuration save requires confirmation. Changes: {changes_summary.get('total_changes', 0)}")
            return jsonify({
                'success': False,
                'require_confirmation': True,
                'changes_summary': changes_summary,
                'message': 'Please review and confirm your configuration changes'
            }), 200  # Return 200 so frontend can handle confirmation dialog
        
        # If confirmed but has validation errors, reject (redundant check for safety)
        if all_errors:
            log.error(f"BLOCKED: Attempt to save invalid configuration: {all_errors}")
            return jsonify({
                'success': False,
                'validation_errors': all_errors,
                'message': 'Configuration validation failed'
            }), 422
        
        log.info(f"Config updated: {list(new_config.keys())}" + (" [CONFIRMED]" if new_config.get('confirmed') else ""))
        
        # Remove the 'confirmed' flag from config (don't save it to file)
        config_to_save = {k: v for k, v in new_config.items() if k != 'confirmed'}
        
        with open(CONFIG_FILE, 'r') as f:
            lines = f.readlines()
        
        # Update values (ONLY IF NOT EMPTY - critical bug fix)
        updated_keys = []
        skipped_empty = []
        for key, value in config_to_save.items():
            # CRITICAL FIX: Skip empty values to prevent config corruption
            if value == '' or value is None:
                skipped_empty.append(key)
                log.warning(f"Skipping empty value for {key} (would corrupt config)")
                continue
            
            updated = False
            for i, line in enumerate(lines):
                if line.strip().startswith(f'{key}='):
                    lines[i] = f'{key}={value}\n'
                    updated = True
                    updated_keys.append(key)
                    break
            
            if not updated:
                # Add new key
                lines.append(f'{key}={value}\n')
                updated_keys.append(key)
        
        # Write back atomically
        _atomic_write_text(CONFIG_FILE, ''.join(lines))
        
        if skipped_empty:
            log.warning(f"Skipped {len(skipped_empty)} empty parameters: {skipped_empty[:5]}...")
        log.info(f"Config updated: {updated_keys}")
        
        # Generate appropriate message based on whether this was confirmed
        if new_config.get('confirmed'):
            message = f'✅ Configuration changes applied successfully! Updated {len(updated_keys)} parameter(s).'
        else:
            message = f'Configuration updated ({len(updated_keys)} keys)'
        
        response = {
            'success': True,
            'message': message,
            'updated_keys': updated_keys
        }
        
        if skipped_empty:
            response['warning'] = f'Skipped {len(skipped_empty)} empty parameters (would corrupt config)'
            response['skipped_keys'] = skipped_empty[:10]  # Show first 10
        
        return jsonify(response), 200
        
    except Exception as e:
        log.error(f"Config update failed: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400


@config_bp.route('/api/config/verify', methods=['GET'])
def verify_config():
    """
    Verify configuration file integrity
    
    Checks that the configuration file exists, is readable, and contains
    required keys.
    
    Returns:
        JSON response with verification status
    """
    try:
        if not CONFIG_FILE.exists():
            return jsonify({
                'valid': False,
                'errors': ['Configuration file not found'],
                'warnings': []
            }), 404
        
        # Try to load config
        try:
            config = _load_config(redact=False)
        except Exception as e:
            return jsonify({
                'valid': False,
                'errors': [f'Failed to parse config: {str(e)}'],
                'warnings': []
            }), 500
        
        # Check for required keys
        required_keys = ['SYMBOL', 'GRID_SIZE', 'API_KEY', 'API_SECRET']
        missing_keys = []
        
        for key in required_keys:
            if key not in config or not config[key]:
                missing_keys.append(key)
        
        errors = []
        warnings = []
        
        if missing_keys:
            errors.append(f'Missing required keys: {", ".join(missing_keys)}')
        
        valid = len(errors) == 0
        
        return jsonify({
            'valid': valid,
            'errors': errors,
            'warnings': warnings,
            'config_keys': list(config.keys()),
            'config_file': str(CONFIG_FILE)
        }), 200
        
    except Exception as e:
        log.error(f"Config verification failed: {e}")
        return jsonify({
            'valid': False,
            'errors': [str(e)],
            'warnings': []
        }), 500


@config_bp.route('/api/config/apply', methods=['POST'])
def apply_config():
    """
    Apply pending configuration changes
    
    Reloads configuration and restarts bot if running to apply changes.
    
    Returns:
        JSON response with success status
    """
    try:
        # Verify config first
        verify_response = verify_config()
        verify_data = verify_response[0].get_json()
        
        if not verify_data.get('valid'):
            return jsonify({
                'success': False,
                'message': 'Configuration is invalid',
                'errors': verify_data.get('errors', [])
            }), 400
        
        # Check if bot is running
        from webui.backend.utils.process_helpers import is_bot_running
        bot_running = is_bot_running()
        
        if bot_running:
            return jsonify({
                'success': True,
                'message': 'Configuration verified. Please restart bot to apply changes.',
                'restart_required': True
            }), 200
        else:
            return jsonify({
                'success': True,
                'message': 'Configuration applied successfully',
                'restart_required': False
            }), 200
        
    except Exception as e:
        log.error(f"Config apply failed: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@config_bp.route('/api/config/confirm-runtime', methods=['POST'])
def confirm_runtime_config():
    """
    Confirm runtime configuration changes by creating the confirmation file
    
    When bot detects config changes while running, it waits for a .confirm_XXXXX file.
    This endpoint creates that file to allow the bot to proceed with the new config.
    
    Request Body:
        {
            "confirm_file": ".confirm_81c62db5"  # The filename from bot logs
        }
    
    Returns:
        JSON response with success status
    """
    try:
        data = request.get_json()
        confirm_file = data.get('confirm_file')
        
        if not confirm_file:
            return jsonify({
                'success': False,
                'error': 'Missing confirm_file parameter'
            }), 400
        
        # Validate filename format (must start with .confirm_ and be alphanumeric)
        if not confirm_file.startswith('.confirm_') or not confirm_file[9:].replace('_', '').isalnum():
            return jsonify({
                'success': False,
                'error': 'Invalid confirmation file format'
            }), 400
        
        # Create the confirmation file in project root
        confirm_path = BASE_DIR / confirm_file
        
        # Check if file already exists
        if confirm_path.exists():
            return jsonify({
                'success': True,
                'message': 'Configuration already confirmed',
                'file_path': str(confirm_path)
            }), 200
        
        # Create the confirmation file
        confirm_path.touch()
        log.info(f"✅ Created runtime config confirmation file: {confirm_file}")
        
        return jsonify({
            'success': True,
            'message': 'Configuration confirmed successfully. Bot will proceed with changes.',
            'file_path': str(confirm_path)
        }), 200
        
    except Exception as e:
        log.error(f"Failed to create confirmation file: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@config_bp.route('/api/config/reset', methods=['POST'])
def get_config_usage_diagnostics():
    """
    Get configuration alias usage statistics
    
    Returns statistics about legacy configuration key usage if the
    compatibility system is available.
    
    Returns:
        JSON response with usage statistics
    """
    try:
        if not ALIASES_AVAILABLE:
            return jsonify({
                'status': 'success',
                'message': 'Config compatibility system not available',
                'usage': {},
                'total_legacy_uses': 0
            }), 200
        
        snapshot = usage_snapshot()
        total_legacy_uses = sum(snapshot.values())
        now = datetime.utcnow().isoformat() + "Z"
        
        return jsonify({
            'status': 'success',
            'timestamp': now,
            'usage': snapshot,
            'total_legacy_uses': total_legacy_uses,
            'aliases_tracked': len(snapshot)
        }), 200
        
    except Exception as e:
        log.error(f"Config usage diagnostics failed: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


# ============================================================================
# Helper Functions
# ============================================================================

# ============================================================================
# Helper Functions
# ============================================================================

def _analyze_config_changes(current_config, new_config):
    """
    Analyze configuration changes and generate impact summary
    
    Returns dict with:
    - requires_confirmation: bool
    - critical_changes: list of critical parameter changes
    - impact_summary: dict describing bot behavior changes
    - warnings: list of warnings
    """
    changes = []
    critical_changes = []
    impact_summary = {
        'grid_mode_change': None,
        'grid_geometry_change': False,
        'trading_mode_change': None,
        'position_limit_change': False,
        'other_changes': []
    }
    warnings = []
    
    # Track changes
    for key, new_value in new_config.items():
        if key == 'confirmed':  # Skip confirmation flag
            continue
            
        current_value = current_config.get(key, '')
        if str(current_value) != str(new_value):
            changes.append({
                'parameter': key,
                'old_value': current_value,
                'new_value': new_value
            })
            
            # Analyze Grid Mode change
            if key == 'GRIDBOT_GRID_MODE':
                old_mode = str(current_value).upper()
                new_mode = str(new_value).upper()
                if old_mode != new_mode:
                    impact_summary['grid_mode_change'] = {
                        'from': old_mode,
                        'to': new_mode,
                        'impact': _get_grid_mode_impact(old_mode, new_mode)
                    }
                    critical_changes.append(f"Grid Mode: {old_mode} → {new_mode}")
            
            # Analyze Grid Geometry changes
            elif key in ['GRIDBOT_LOWER', 'GRIDBOT_UPPER', 'GRIDBOT_STEP', 'GRIDBOT_REF']:
                impact_summary['grid_geometry_change'] = True
                critical_changes.append(f"{key}: {current_value} → {new_value}")
                warnings.append(f"Changing {key} will rebuild the entire grid structure")
            
            # Analyze Trading Mode change
            elif key == 'TRADING_MODE':
                old_mode = str(current_value).lower()
                new_mode = str(new_value).lower()
                if old_mode != new_mode:
                    impact_summary['trading_mode_change'] = {
                        'from': old_mode,
                        'to': new_mode,
                        'impact': 'CRITICAL: Switching between demo and live trading!'
                    }
                    critical_changes.append(f"Trading Mode: {old_mode.upper()} → {new_mode.upper()}")
                    warnings.append("⚠️ REQUIRES BOT RESTART to take effect")
            
            # Analyze Position Limit change
            elif key == 'GRIDBOT_MAX_OPEN':
                impact_summary['position_limit_change'] = True
                critical_changes.append(f"Max Positions: {current_value} → {new_value}")
                warnings.append(f"Bot will limit open positions to {new_value}")
            
            # Track other changes
            else:
                impact_summary['other_changes'].append({
                    'parameter': key,
                    'old': current_value,
                    'new': new_value
                })
    
    # Determine if confirmation is required
    requires_confirmation = (
        impact_summary['grid_mode_change'] is not None or
        impact_summary['grid_geometry_change'] or
        impact_summary['trading_mode_change'] is not None or
        impact_summary['position_limit_change']
    )
    
    return {
        'requires_confirmation': requires_confirmation,
        'total_changes': len(changes),
        'critical_changes': critical_changes,
        'impact_summary': impact_summary,
        'warnings': warnings,
        'changes': changes[:10]  # Limit to first 10 for display
    }


def _get_grid_mode_impact(old_mode, new_mode):
    """Generate human-readable impact description for grid mode change"""
    impacts = {
        ('LONG', 'SHORT'): {
            'order_direction': 'Bot will now SELL above current price instead of BUY below',
            'position_type': 'Switching from bullish (LONG) to bearish (SHORT) strategy',
            'risk': 'Existing LONG positions will remain. New orders will be SHORT.',
            'action_required': 'Consider closing existing LONG positions before switching'
        },
        ('SHORT', 'LONG'): {
            'order_direction': 'Bot will now BUY below current price instead of SELL above',
            'position_type': 'Switching from bearish (SHORT) to bullish (LONG) strategy',
            'risk': 'Existing SHORT positions will remain. New orders will be LONG.',
            'action_required': 'Consider closing existing SHORT positions before switching'
        }
    }
    
    return impacts.get((old_mode, new_mode), {
        'order_direction': f'Grid mode changing from {old_mode} to {new_mode}',
        'position_type': 'Trading strategy will change',
        'risk': 'Review existing positions',
        'action_required': 'Ensure this change aligns with your trading strategy'
    })


def _load_config(redact=True, instance=None):
    """
    Load configuration from grid_config.env
    
    Args:
        redact: Whether to redact sensitive keys
        instance: Optional instance name (ignored for legacy .env config)
        
    Returns:
        Dict of configuration key-value pairs
    """
    config = {}
    
    # If grid_config.env doesn't exist, return empty config
    # (system now uses config.yaml as primary source)
    if not CONFIG_FILE.exists():
        log.warning(f"Legacy config file {CONFIG_FILE} not found - system uses config.yaml")
        return config
    
    with open(CONFIG_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Redact sensitive keys
                if redact and _is_secret_key(key):
                    value = '***REDACTED***'
                
                config[key] = value
    
    return config


def _is_secret_key(key_name):
    """Check if a config key represents a secret"""
    secret_indicators = ['KEY', 'SECRET', 'PASSWORD', 'TOKEN', 'CREDENTIALS']
    return any(secret in key_name.upper() for secret in secret_indicators)


def _get_key_section(key_name):
    """Determine which section a config key belongs to"""
    key_upper = key_name.upper()
    
    if any(x in key_upper for x in ['API_KEY', 'API_SECRET', 'SECRET']):
        return 'Authentication'
    elif any(x in key_upper for x in ['SYMBOL', 'PRODUCT_ID', 'GRID', 'PRICE', 'TRADE']):
        return 'Trading'
    elif any(x in key_upper for x in ['GUARDIAN', 'CAPITAL', 'PROTECTION', 'LIMIT']):
        return 'Risk Management'
    elif any(x in key_upper for x in ['TELEGRAM', 'NOTIFICATION', 'ALERT']):
        return 'Notifications'
    elif any(x in key_upper for x in ['LOG', 'DEBUG', 'VERBOSE']):
        return 'Logging'
    else:
        return 'General'


@config_bp.route('/api/auth/config', methods=['GET'])
def get_auth_config():
    """Get authentication configuration"""
    try:
        auth_enabled = get_config_value('webui.disable_auth', 'WEBUI_DISABLE_AUTH', False) != True
        return jsonify({
            'success': True,
            'auth_enabled': auth_enabled,
            'auth_required': auth_enabled
        }), 200
    except Exception as e:
        log.error(f"Error getting auth config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@config_bp.route('/api/config/feature-flags', methods=['GET'])
def get_feature_flags():
    """Get feature flags (Week 3)"""
    try:
        from webui.backend.config import get_all_flags
        flags = get_all_flags()
        return jsonify({
            'success': True,
            'flags': flags
        }), 200
    except Exception as e:
        log.error(f"Error getting feature flags: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@config_bp.route('/api/config/feature-flags', methods=['POST'])
@require_auth
def toggle_feature_flag():
    """Toggle feature flag (Week 3, admin only)"""
    try:
        data = request.get_json()
        flag_name = data.get('flag')
        enabled = data.get('enabled')
        
        if not flag_name:
            return jsonify({
                'success': False,
                'error': 'Missing flag name'
            }), 400
        
        from webui.backend.config import toggle_feature
        success = toggle_feature(flag_name, enabled)
        
        if success:
            return jsonify({
                'success': True,
                'flag': flag_name,
                'enabled': enabled
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to save feature flag'
            }), 500
    except Exception as e:
        log.error(f"Error toggling feature flag: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


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
