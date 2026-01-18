"""
YAML Configuration API Routes

Provides read/write access to config.yaml through REST API.
Manages config.yaml as single source of truth.
Replaces legacy grid_config.env management.

Includes backward-compatible /api/config/all endpoint that flattens YAML to env var format.
"""

from flask import Blueprint, request, jsonify
import logging
from pathlib import Path
import yaml
from typing import Any, Dict
from datetime import datetime

log = logging.getLogger(__name__)

yaml_config_bp = Blueprint('yaml_config', __name__)

BASE_DIR = Path(__file__).parent.parent.parent.parent
CONFIG_FILE = BASE_DIR / "config.yaml"


def flatten_config(config: Dict, parent_key: str = '', sep: str = '_') -> Dict[str, str]:
    """
    Flatten nested YAML config to environment variable style keys.
    
    Example:
        {'bot': {'symbol': 'BTCUSD'}} -> {'BOT_SYMBOL': 'BTCUSD'}
    """
    items = []
    for k, v in config.items():
        new_key = f"{parent_key}{sep}{k}".upper() if parent_key else k.upper()
        
        if isinstance(v, dict):
            items.extend(flatten_config(v, new_key, sep=sep).items())
        elif isinstance(v, (list, tuple)):
            # Convert lists to comma-separated strings
            items.append((new_key, ','.join(str(x) for x in v)))
        elif v is None:
            items.append((new_key, ''))
        elif isinstance(v, bool):
            items.append((new_key, 'true' if v else 'false'))
        else:
            items.append((new_key, str(v)))
    
    return dict(items)


def is_secret_key(key_name: str) -> bool:
    """Check if a config key represents a secret"""
    secret_indicators = ['KEY', 'SECRET', 'PASSWORD', 'TOKEN', 'CREDENTIALS']
    return any(secret in key_name.upper() for secret in secret_indicators)


@yaml_config_bp.route('/api/yaml-config', methods=['GET'])
def get_yaml_config():
    """
    Get current YAML configuration
    
    Returns:
        JSON response with full config or specific section
    """
    try:
        # Get section parameter (optional)
        section = request.args.get('section')
        
        # Load YAML config
        with open(CONFIG_FILE, 'r') as f:
            config = yaml.safe_load(f)
        
        # Return specific section or full config
        if section:
            keys = section.split('.')
            result = config
            for key in keys:
                result = result.get(key, {})
            return jsonify({'success': True, 'data': result})
        
        return jsonify({'success': True, 'data': config})
        
    except Exception as e:
        log.error(f"Error reading YAML config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def _convert_flat_key_to_path(flat_key: str) -> tuple:
    """
    Convert flat config key to YAML path, returning (path, should_skip)
    
    Returns tuple of (path_string, should_skip_boolean)
    should_skip is True if this is a duplicate/redundant key that shouldn't be saved
    
    Examples:
        GRIDBOT_REF -> ('grid.geometry.reference', False)
        GRID_GEOMETRY_REFERENCE -> ('grid.geometry.reference', False)
        BOT_MODE -> ('bot.mode', False)
    """
    # Legacy aliases mapping (old frontend field names)
    legacy_map = {
        'GRIDBOT_REF': 'grid.geometry.reference',
        'GRIDBOT_LOWER': 'grid.geometry.lower',
        'GRIDBOT_UPPER': 'grid.geometry.upper',
        'GRIDBOT_STEP': 'grid.geometry.step',
        'GRIDBOT_LOT': 'grid.limits.lot_size',
        'GRIDBOT_MAX_OPEN': 'grid.limits.max_open_positions',
        'GRIDBOT_GRID_MODE': 'bot.mode',
        'GRIDBOT_SYMBOL': 'bot.symbol',
        'GRIDBOT_SEED_INITIAL_COUNT': 'grid.behavior.seed_initial_count',
        'GRIDBOT_POST_ONLY_MODE': 'order_execution.post_only_mode',
        'GRIDBOT_PRICE_BUFFER_PCT': 'order_execution.price_buffer_pct',
        'EXECUTE_ORDERS': 'execution_safety.execute_orders',
        'I_UNDERSTAND_LIVE': 'execution_safety.i_understand_live',
        'TRADING_MODE': 'trading_mode',
        'GRIDBOT_STRICT_GRID': 'grid.behavior.strict_grid',
        'GRIDBOT_RUNG_SNAP_MODE': 'grid.behavior.rung_snap_mode',
        'GRIDBOT_TICK_SIZE': 'grid.behavior.tick_size',
        'GRIDBOT_DYNAMIC_TICK_SIZE': 'grid.behavior.dynamic_tick_size',
        'GRIDBOT_STRICT_START': 'startup.strict_start',
        'GRIDBOT_FORGET_EXCHANGE_ON_START': 'startup.forget_exchange_on_start',
        'GRIDBOT_ENABLE_SMART_RECOVERY': 'startup.enable_smart_recovery',
        'GRIDBOT_CANCEL_ALL_ON_START': 'startup.cancel_all_on_start',
        'GRIDBOT_CANCEL_SCOPE': 'startup.cancel_scope',
        'SMART_GAP_FILL': 'grid.smart_gap_fill.enabled',
        'GAP_FILL_ORDER_TYPE': 'grid.smart_gap_fill.order_type',
        'MAX_GAP_FILL_LEVELS': 'grid.smart_gap_fill.max_levels',
        'GRIDBOT_TAG_PREFIX': 'order_execution.tag_prefix',
        'GRIDBOT_ADOPT_UNTAGGED': 'order_execution.adopt_untagged',
        'GRIDBOT_FILL_THRESHOLD': 'order_execution.fill_threshold',
        'GRIDBOT_MAX_RETRIES': 'order_execution.max_retries',
        'GRIDBOT_RETRY_DELAY': 'order_execution.retry_delay',
        'GRIDBOT_COOLDOWN_SECONDS': 'order_execution.cooldown_seconds',
        'GRIDBOT_HEALTH_CHECK_ENABLED': 'health_check.enabled',
        'GRIDBOT_HEALTH_CHECK_INTERVAL': 'health_check.interval',
        'GRIDBOT_LOG_PERFORMANCE': 'performance_logging.enabled',
        'GRIDBOT_PERFORMANCE_INTERVAL': 'performance_logging.interval',
        'GRIDBOT_MAX_DRIFT_ALERTS': 'emergency.max_drift_alerts',
        'GRIDBOT_MAX_DISRUPTION_EVENTS': 'emergency.max_disruption_events',
        'GRIDBOT_EMERGENCY_PRICE_BUFFER': 'risk_limits.emergency_price_buffer',
        'GRIDBOT_MARKET_DISRUPTION_COOLDOWN': 'emergency.market_disruption_cooldown',
        'MAX_ACCOUNT_LOSS_INR': 'guardian.max_account_loss_inr',
        'USD_TO_INR_RATE': 'guardian.usd_to_inr_rate',
        'MAX_QTY_PER_ORDER': 'grid.limits.max_qty_per_order',
        'MAINTENANCE_MARGIN_PERCENT': 'liquidation_protection.maintenance_margin_percent',
        'AUTO_MARGIN_TOPUP_ENABLED': 'liquidation_protection.auto_margin_topup',
        'AUTO_TOPUP_THRESHOLD': 'liquidation_protection.auto_topup_threshold',
        'AUTO_TOPUP_TARGET': 'liquidation_protection.auto_topup_target',
        'MAX_TOPUPS_PER_POSITION': 'liquidation_protection.max_topups_per_position',
        'MIN_BALANCE_RESERVE_PERCENT': 'liquidation_protection.min_balance_reserve_percent',
        'MARGIN_WARNING_THRESHOLD': 'liquidation_protection.margin_warning_threshold',
        'MARGIN_DANGER_THRESHOLD': 'liquidation_protection.margin_danger_threshold',
        'MARGIN_CRITICAL_THRESHOLD': 'liquidation_protection.margin_critical_threshold',
        'DISTANCE_TO_LIQ_WARNING': 'liquidation_protection.distance_to_liq_warning',
        'TELEGRAM_BOT_TOKEN': 'telegram.bot_token',
        'TELEGRAM_CHAT_ID': 'telegram.chat_id',
        'ENABLE_HEARTBEAT': 'heartbeat.enabled',
        'HEARTBEAT_TIMEOUT': 'heartbeat.timeout',
        'HEARTBEAT_UPDATE_INTERVAL': 'heartbeat.update_interval',
        'HEARTBEAT_MONITOR_INTERVAL': 'heartbeat.monitor_interval',
        'HEARTBEAT_FILE': 'heartbeat.file',
        'HEARTBEAT_ACTION': 'heartbeat.action',
        'GRIDBOT_HB_SEC': 'bot.heartbeat_seconds',
    }
    
    # Check legacy aliases first
    if flat_key in legacy_map:
        return (legacy_map[flat_key], False)
    
    # Convert UPPER_SNAKE_CASE to dot.separated.path
    # Example: GRID_GEOMETRY_REFERENCE -> grid.geometry.reference
    path = flat_key.lower().replace('_', '.')
    
    # Skip keys that are too deeply nested (likely auto-generated duplicates)
    # If path has more than 4 levels, it's probably a duplicate
    if path.count('.') > 4:
        return (path, True)
    
    return (path, False)


@yaml_config_bp.route('/api/yaml-config', methods=['POST'])
def update_yaml_config():
    """
    Update YAML configuration
    
    Request body (nested format):
        {
            "updates": {
                "safety.execute_orders": true,
                "grid.limits.lot_size": 2
            }
        }
    
    OR flat format (legacy compatibility):
        {
            "GRIDBOT_REF": 93000,
            "GRIDBOT_STEP": 500
        }
    
    Returns:
        JSON response with success status
    """
    try:
        data = request.get_json()
        
        # Support both formats:
        # 1. Nested: {"updates": {"grid.geometry.reference": 93000}}
        # 2. Flat: {"GRIDBOT_REF": 93000} or {"GRID_GEOMETRY_REFERENCE": 93000}
        if 'updates' in data:
            # Nested format
            updates = data.get('updates', {})
        else:
            # Flat format - convert all keys to nested paths
            # ONLY process keys that are in the legacy map to prevent duplicates
            legacy_keys = {
                'GRIDBOT_REF', 'GRIDBOT_LOWER', 'GRIDBOT_UPPER', 'GRIDBOT_STEP',
                'GRIDBOT_LOT', 'GRIDBOT_MAX_OPEN', 'GRIDBOT_GRID_MODE', 'GRIDBOT_SYMBOL',
                'GRIDBOT_SEED_INITIAL_COUNT', 'GRIDBOT_POST_ONLY_MODE', 'GRIDBOT_PRICE_BUFFER_PCT',
                'EXECUTE_ORDERS', 'I_UNDERSTAND_LIVE', 'TRADING_MODE',
                'GRIDBOT_STRICT_GRID', 'GRIDBOT_RUNG_SNAP_MODE', 'GRIDBOT_TICK_SIZE', 'GRIDBOT_DYNAMIC_TICK_SIZE',
                'GRIDBOT_STRICT_START', 'GRIDBOT_FORGET_EXCHANGE_ON_START', 'GRIDBOT_ENABLE_SMART_RECOVERY',
                'GRIDBOT_CANCEL_ALL_ON_START', 'GRIDBOT_CANCEL_SCOPE',
                'SMART_GAP_FILL', 'GAP_FILL_ORDER_TYPE', 'MAX_GAP_FILL_LEVELS',
                'GRIDBOT_TAG_PREFIX', 'GRIDBOT_ADOPT_UNTAGGED', 'GRIDBOT_FILL_THRESHOLD',
                'GRIDBOT_MAX_RETRIES', 'GRIDBOT_RETRY_DELAY', 'GRIDBOT_COOLDOWN_SECONDS',
                'GRIDBOT_HEALTH_CHECK_ENABLED', 'GRIDBOT_HEALTH_CHECK_INTERVAL',
                'GRIDBOT_LOG_PERFORMANCE', 'GRIDBOT_PERFORMANCE_INTERVAL',
                'GRIDBOT_MAX_DRIFT_ALERTS', 'GRIDBOT_MAX_DISRUPTION_EVENTS',
                'GRIDBOT_EMERGENCY_PRICE_BUFFER', 'GRIDBOT_MARKET_DISRUPTION_COOLDOWN',
                'MAX_ACCOUNT_LOSS_INR', 'USD_TO_INR_RATE', 'MAX_QTY_PER_ORDER',
                'MAINTENANCE_MARGIN_PERCENT', 'AUTO_MARGIN_TOPUP_ENABLED', 'AUTO_TOPUP_THRESHOLD',
                'AUTO_TOPUP_TARGET', 'MAX_TOPUPS_PER_POSITION', 'MIN_BALANCE_RESERVE_PERCENT',
                'MARGIN_WARNING_THRESHOLD', 'MARGIN_DANGER_THRESHOLD', 'MARGIN_CRITICAL_THRESHOLD',
                'DISTANCE_TO_LIQ_WARNING', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID',
                'ENABLE_HEARTBEAT', 'HEARTBEAT_TIMEOUT', 'HEARTBEAT_UPDATE_INTERVAL',
                'HEARTBEAT_MONITOR_INTERVAL', 'HEARTBEAT_FILE', 'HEARTBEAT_ACTION', 'GRIDBOT_HB_SEC'
            }
            
            updates = {}
            skipped_count = 0
            for key, value in data.items():
                # Skip meta keys
                if key in ['confirmed', 'require_confirmation']:
                    continue
                
                # ONLY process known legacy keys to prevent creating duplicate nested structures
                if key not in legacy_keys:
                    skipped_count += 1
                    continue
                    
                # Convert flat key to nested path
                path, should_skip = _convert_flat_key_to_path(key)
                if should_skip:
                    skipped_count += 1
                    continue
                updates[path] = value
            
        
        if not updates:
            return jsonify({'success': False, 'error': 'No updates provided'}), 400
        
        # Load current config
        with open(CONFIG_FILE, 'r') as f:
            config = yaml.safe_load(f)
        
        # Apply updates
        for path, value in updates.items():
            keys = path.split('.')
            current = config
            
            # Navigate to parent
            for i, key in enumerate(keys[:-1]):
                if key not in current:
                    current[key] = {}
                elif not isinstance(current[key], dict):
                    # Current key exists but is not a dict (e.g., it's a string or number)
                    # This means we're trying to set a nested value where a scalar exists
                    # Convert it to a dict to allow nesting
                    log.warning(f"Converting {'.'.join(keys[:i+1])} from {type(current[key]).__name__} to dict to allow nested path")
                    current[key] = {}
                current = current[key]
            
            # Set value
            current[keys[-1]] = value
        
        # Write back
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        return jsonify({
            'success': True,
            'message': f'Updated {len(updates)} configuration values',
            'updated_keys': list(updates.keys())
        })
        
    except Exception as e:
        log.error(f"Error updating YAML config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@yaml_config_bp.route('/api/yaml-config/validate', methods=['POST'])
def validate_yaml_config():
    """
    Validate YAML configuration without saving
    
    Request body:
        {
            "config": {...}  // Full or partial config
        }
    
    Returns:
        JSON response with validation results
    """
    try:
        from config.loader import validate_config_dict
        
        data = request.get_json()
        config_data = data.get('config', {})
        
        # Validate using Pydantic models
        errors = validate_config_dict(config_data)
        
        if errors:
            return jsonify({
                'success': False,
                'valid': False,
                'errors': errors
            })
        
        return jsonify({
            'success': True,
            'valid': True,
            'message': 'Configuration is valid'
        })
        
    except Exception as e:
        log.error(f"Error validating config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@yaml_config_bp.route('/api/yaml-config/schema', methods=['GET'])
def get_config_schema():
    """
    Get Pydantic schema for configuration
    
    Returns:
        JSON schema for frontend validation
    """
    try:
        from config.models import GridBotConfig
        
        schema = GridBotConfig.schema()
        
        return jsonify({
            'success': True,
            'schema': schema
        })
        
    except Exception as e:
        log.error(f"Error getting schema: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@yaml_config_bp.route('/api/yaml-config/backup', methods=['POST'])
def backup_config():
    """
    Create backup of current config.yaml
    
    Returns:
        JSON response with backup file path
    """
    try:
        from datetime import datetime
        import shutil
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = BASE_DIR / f"config.yaml.backup_{timestamp}"
        
        shutil.copy2(CONFIG_FILE, backup_file)
        
        return jsonify({
            'success': True,
            'backup_file': str(backup_file),
            'timestamp': timestamp
        })
        
    except Exception as e:
        log.error(f"Error creating backup: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@yaml_config_bp.route('/api/yaml-config/restore', methods=['POST'])
def restore_config():
    """
    Restore config from backup
    
    Request body:
        {
            "backup_file": "config.yaml.backup_20251115_123456"
        }
    
    Returns:
        JSON response with success status
    """
    try:
        import shutil
        
        data = request.get_json()
        backup_file = data.get('backup_file')
        
        if not backup_file:
            return jsonify({'success': False, 'error': 'No backup file specified'}), 400
        
        backup_path = BASE_DIR / backup_file
        
        if not backup_path.exists():
            return jsonify({'success': False, 'error': 'Backup file not found'}), 404
        
        # Create safety backup of current config
        safety_backup = BASE_DIR / f"config.yaml.before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(CONFIG_FILE, safety_backup)
        
        # Restore from backup
        shutil.copy2(backup_path, CONFIG_FILE)
        
        return jsonify({
            'success': True,
            'message': f'Restored config from {backup_file}',
            'safety_backup': str(safety_backup)
        })
        
    except Exception as e:
        log.error(f"Error restoring config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# BACKWARD COMPATIBILITY ENDPOINTS
# ============================================================================

@yaml_config_bp.route('/api/config/all', methods=['GET'])
def get_all_config_compat():
    """
    Get ALL configuration in flat format (backward compatible with legacy .env API)
    
    This endpoint replaces the old config.py /api/config/all endpoint.
    Returns YAML config flattened to environment variable style keys.
    
    Query Parameters:
        symbol (optional): Symbol name (e.g., "BTCUSD", "ETHUSD")
                          If not provided, returns first enabled symbol (v4.0 compat)
    
    Returns:
        JSON response with config dict matching old format
    """
    try:
        # ========== v5.0 MULTI-SYMBOL SUPPORT ==========
        # Get optional symbol parameter from query string
        requested_symbol = request.args.get('symbol')
        
        log.info(f"🎯 YAML CONFIG API: /api/config/all called (symbol={requested_symbol or 'auto'})")
        log.info(f"🎯 THIS IS yaml_config_api.get_all_config_compat() - NOT config.get_all_config()")
        
        # Load YAML config
        with open(CONFIG_FILE, 'r') as f:
            yaml_data = yaml.safe_load(f)
        
        # Flatten to env var style
        flat_config = flatten_config(yaml_data)
        
        # ========== v5.0 MULTI-SYMBOL SUPPORT ==========
        # Initialize symbol variables
        selected_symbol = None
        symbol_config = None
        
        # Select which symbol's config to return
        if 'symbols' in yaml_data and yaml_data['symbols']:
            if requested_symbol:
                # Specific symbol requested - find it
                for sym_name, sym_cfg in yaml_data['symbols'].items():
                    if sym_name == requested_symbol:
                        selected_symbol = sym_name
                        symbol_config = sym_cfg
                        log.info(f"✅ Found requested symbol: {requested_symbol}")
                        break
                
                # If requested symbol not found, return error
                if not symbol_config:
                    log.warning(f"⚠️ Requested symbol '{requested_symbol}' not found in config")
                    return jsonify({
                        'success': False,
                        'error': f"Symbol '{requested_symbol}' not found in configuration",
                        'available_symbols': list(yaml_data['symbols'].keys())
                    }), 404
            else:
                # No symbol requested - use first enabled symbol (v4.0 backward compat)
                for sym_name, sym_cfg in yaml_data['symbols'].items():
                    if sym_cfg.get('enabled', False):
                        selected_symbol = sym_name
                        symbol_config = sym_cfg
                        log.info(f"✅ Auto-selected first enabled symbol: {selected_symbol}")
                        break
            
            # If we found a symbol, extract its config to legacy flat keys
            if symbol_config and selected_symbol:
                # Grid geometry
                grid_geom = symbol_config.get('grid', {}).get('geometry', {})
                flat_config['GRID_GEOMETRY_REFERENCE'] = grid_geom.get('reference', '')
                flat_config['GRID_GEOMETRY_LOWER'] = grid_geom.get('lower', '')
                flat_config['GRID_GEOMETRY_UPPER'] = grid_geom.get('upper', '')
                flat_config['GRID_GEOMETRY_STEP'] = grid_geom.get('step', '')
                
                # Grid limits
                grid_limits = symbol_config.get('grid', {}).get('limits', {})
                flat_config['GRID_LIMITS_LOT_SIZE'] = grid_limits.get('lot_size', '')
                flat_config['GRID_LIMITS_MAX_OPEN_POSITIONS'] = grid_limits.get('max_open_positions', '')
                flat_config['GRID_LIMITS_MAX_QTY_PER_ORDER'] = grid_limits.get('max_qty_per_order', '')
                
                # Bot mode and symbol
                flat_config['BOT_MODE'] = symbol_config.get('mode', '')
                flat_config['BOT_SYMBOL'] = selected_symbol  # Use selected_symbol instead of first_symbol
                
                # Grid behavior
                grid_behavior = symbol_config.get('grid', {}).get('behavior', {})
                flat_config['GRID_BEHAVIOR_STRICT_GRID'] = grid_behavior.get('strict_grid', '')
                flat_config['GRID_BEHAVIOR_RUNG_SNAP_MODE'] = grid_behavior.get('rung_snap_mode', '')
                flat_config['GRID_BEHAVIOR_TICK_SIZE'] = grid_behavior.get('tick_size', '')
                flat_config['GRID_BEHAVIOR_DYNAMIC_TICK_SIZE'] = grid_behavior.get('dynamic_tick_size', '')
                flat_config['GRID_BEHAVIOR_SEED_INITIAL_COUNT'] = grid_behavior.get('seed_initial_count', '')
            elif not selected_symbol:
                # No symbol could be selected - log warning
                log.warning("⚠️ No symbol selected - returning base config without symbol-specific settings")
        
        # Add backward compatibility aliases for old frontend field names
        legacy_aliases = {
            # Grid geometry aliases (EXISTING - 8 fields)
            'GRIDBOT_REF': flat_config.get('GRID_GEOMETRY_REFERENCE', ''),
            'GRIDBOT_LOWER': flat_config.get('GRID_GEOMETRY_LOWER', ''),
            'GRIDBOT_UPPER': flat_config.get('GRID_GEOMETRY_UPPER', ''),
            'GRIDBOT_STEP': flat_config.get('GRID_GEOMETRY_STEP', ''),
            'GRIDBOT_LOT': flat_config.get('GRID_LIMITS_LOT_SIZE', ''),
            'GRIDBOT_MAX_OPEN': flat_config.get('GRID_LIMITS_MAX_OPEN_POSITIONS', ''),
            'GRIDBOT_GRID_MODE': flat_config.get('BOT_MODE', ''),
            'GRIDBOT_SYMBOL': flat_config.get('BOT_SYMBOL', ''),
            
            # Seeding system (EXISTING - 1 field)
            'GRIDBOT_SEED_INITIAL_COUNT': flat_config.get('GRID_BEHAVIOR_SEED_INITIAL_COUNT', ''),
            
            # Order execution (EXISTING - 2 fields)
            'GRIDBOT_POST_ONLY_MODE': flat_config.get('ORDER_EXECUTION_POST_ONLY_MODE', ''),
            'GRIDBOT_PRICE_BUFFER_PCT': flat_config.get('ORDER_EXECUTION_PRICE_BUFFER_PCT', ''),
            
            # Safety (EXISTING - 2 fields)
            'EXECUTE_ORDERS': flat_config.get('EXECUTION_SAFETY_EXECUTE_ORDERS', ''),
            'I_UNDERSTAND_LIVE': flat_config.get('EXECUTION_SAFETY_I_UNDERSTAND_LIVE', ''),
            
            # Trading mode (EXISTING - 1 field)
            'TRADING_MODE': flat_config.get('TRADING_MODE', ''),
            
            # ========== NEW MAPPINGS (51 fields) ==========
            
            # Grid Behavior (4 fields)
            'GRIDBOT_STRICT_GRID': flat_config.get('GRID_BEHAVIOR_STRICT_GRID', ''),
            'GRIDBOT_RUNG_SNAP_MODE': flat_config.get('GRID_BEHAVIOR_RUNG_SNAP_MODE', ''),
            'GRIDBOT_TICK_SIZE': flat_config.get('GRID_BEHAVIOR_TICK_SIZE', ''),
            'GRIDBOT_DYNAMIC_TICK_SIZE': flat_config.get('GRID_BEHAVIOR_DYNAMIC_TICK_SIZE', ''),
            
            # Startup (5 fields)
            'GRIDBOT_STRICT_START': flat_config.get('STARTUP_STRICT_START', ''),
            'GRIDBOT_FORGET_EXCHANGE_ON_START': flat_config.get('STARTUP_FORGET_EXCHANGE_ON_START', ''),
            'GRIDBOT_ENABLE_SMART_RECOVERY': flat_config.get('STARTUP_ENABLE_SMART_RECOVERY', ''),
            'GRIDBOT_CANCEL_ALL_ON_START': flat_config.get('STARTUP_CANCEL_ALL_ON_START', ''),
            'GRIDBOT_CANCEL_SCOPE': flat_config.get('STARTUP_CANCEL_SCOPE', ''),
            
            # Smart Gap Fill (3 fields)
            'SMART_GAP_FILL': flat_config.get('GRID_SMART_GAP_FILL_ENABLED', ''),
            'GAP_FILL_ORDER_TYPE': flat_config.get('GRID_SMART_GAP_FILL_ORDER_TYPE', ''),
            'MAX_GAP_FILL_LEVELS': flat_config.get('GRID_SMART_GAP_FILL_MAX_LEVELS', ''),
            
            # Order Execution (3 fields)
            'GRIDBOT_TAG_PREFIX': flat_config.get('ORDER_EXECUTION_TAG_PREFIX', ''),
            'GRIDBOT_ADOPT_UNTAGGED': flat_config.get('ORDER_EXECUTION_ADOPT_UNTAGGED', ''),
            'GRIDBOT_FILL_THRESHOLD': flat_config.get('ORDER_EXECUTION_FILL_THRESHOLD', ''),
            
            # Timing & Retries (3 fields)
            'GRIDBOT_MAX_RETRIES': flat_config.get('ORDER_EXECUTION_MAX_RETRIES', ''),
            'GRIDBOT_RETRY_DELAY': flat_config.get('ORDER_EXECUTION_RETRY_DELAY', ''),
            'GRIDBOT_COOLDOWN_SECONDS': flat_config.get('ORDER_EXECUTION_COOLDOWN_SECONDS', ''),
            
            # Health & Monitoring (4 fields)
            'GRIDBOT_HEALTH_CHECK_ENABLED': flat_config.get('HEALTH_CHECK_ENABLED', ''),
            'GRIDBOT_HEALTH_CHECK_INTERVAL': flat_config.get('HEALTH_CHECK_INTERVAL', ''),
            'GRIDBOT_LOG_PERFORMANCE': flat_config.get('PERFORMANCE_LOGGING_ENABLED', ''),
            'GRIDBOT_PERFORMANCE_INTERVAL': flat_config.get('PERFORMANCE_LOGGING_INTERVAL', ''),
            
            # Emergency Limits (4 fields)
            'GRIDBOT_MAX_DRIFT_ALERTS': flat_config.get('EMERGENCY_MAX_DRIFT_ALERTS', ''),
            'GRIDBOT_MAX_DISRUPTION_EVENTS': flat_config.get('EMERGENCY_MAX_DISRUPTION_EVENTS', ''),
            'GRIDBOT_EMERGENCY_PRICE_BUFFER': flat_config.get('RISK_LIMITS_EMERGENCY_PRICE_BUFFER', ''),
            'GRIDBOT_MARKET_DISRUPTION_COOLDOWN': flat_config.get('EMERGENCY_MARKET_DISRUPTION_COOLDOWN', ''),
            
            # Loss Limits (3 fields)
            'MAX_ACCOUNT_LOSS_INR': flat_config.get('GUARDIAN_MAX_ACCOUNT_LOSS_INR', ''),
            'USD_TO_INR_RATE': flat_config.get('GUARDIAN_USD_TO_INR_RATE', ''),
            'MAX_QTY_PER_ORDER': flat_config.get('GRID_LIMITS_MAX_QTY_PER_ORDER', ''),
            
            # Margin & Liquidation (10 fields)
            'MAINTENANCE_MARGIN_PERCENT': flat_config.get('LIQUIDATION_PROTECTION_MAINTENANCE_MARGIN_PERCENT', ''),
            'AUTO_MARGIN_TOPUP_ENABLED': flat_config.get('LIQUIDATION_PROTECTION_AUTO_MARGIN_TOPUP', ''),
            'AUTO_TOPUP_THRESHOLD': flat_config.get('LIQUIDATION_PROTECTION_AUTO_TOPUP_THRESHOLD', ''),
            'AUTO_TOPUP_TARGET': flat_config.get('LIQUIDATION_PROTECTION_AUTO_TOPUP_TARGET', ''),
            'MAX_TOPUPS_PER_POSITION': flat_config.get('LIQUIDATION_PROTECTION_MAX_TOPUPS_PER_POSITION', ''),
            'MIN_BALANCE_RESERVE_PERCENT': flat_config.get('LIQUIDATION_PROTECTION_MIN_BALANCE_RESERVE_PERCENT', ''),
            'MARGIN_WARNING_THRESHOLD': flat_config.get('LIQUIDATION_PROTECTION_MARGIN_WARNING_THRESHOLD', ''),
            'MARGIN_DANGER_THRESHOLD': flat_config.get('LIQUIDATION_PROTECTION_MARGIN_DANGER_THRESHOLD', ''),
            'MARGIN_CRITICAL_THRESHOLD': flat_config.get('LIQUIDATION_PROTECTION_MARGIN_CRITICAL_THRESHOLD', ''),
            'DISTANCE_TO_LIQ_WARNING': flat_config.get('LIQUIDATION_PROTECTION_DISTANCE_TO_LIQ_WARNING', ''),
            
            # Telegram (2 fields)
            'TELEGRAM_BOT_TOKEN': flat_config.get('TELEGRAM_BOT_TOKEN', ''),
            'TELEGRAM_CHAT_ID': flat_config.get('TELEGRAM_CHAT_ID', ''),
            
            # Heartbeat (6 fields)
            'ENABLE_HEARTBEAT': flat_config.get('HEARTBEAT_ENABLED', ''),
            'HEARTBEAT_TIMEOUT': flat_config.get('HEARTBEAT_TIMEOUT', ''),
            'HEARTBEAT_UPDATE_INTERVAL': flat_config.get('HEARTBEAT_UPDATE_INTERVAL', ''),
            'HEARTBEAT_MONITOR_INTERVAL': flat_config.get('HEARTBEAT_MONITOR_INTERVAL', ''),
            'HEARTBEAT_FILE': flat_config.get('HEARTBEAT_FILE', ''),
            'HEARTBEAT_ACTION': flat_config.get('HEARTBEAT_ACTION', ''),
            
            # Bot Heartbeat (1 field)
            'GRIDBOT_HB_SEC': flat_config.get('BOT_HEARTBEAT_SECONDS', ''),
        }
        
        # Merge legacy aliases into flat_config
        flat_config.update(legacy_aliases)
        
        # Build metadata for each config key
        metadata = {}
        secrets_meta = {}
        
        for key, value in flat_config.items():
            # Determine section from key prefix
            section = _get_key_section(key)
            
            # Check if secret
            is_secret = is_secret_key(key)
            
            # Build metadata entry
            metadata[key] = {
                'section': section,
                'redacted': is_secret,
                'has_value': bool(value),
                'source_key': key,
                'legacy_sources': []
            }
            
            # Redact secrets and track in secrets metadata
            if is_secret:
                flat_config[key] = '***REDACTED***'
                secrets_meta[key] = {
                    'redacted': True,
                    'has_value': bool(value)
                }
        
        # ========== v5.0 MULTI-SYMBOL RESPONSE ==========
        # Include symbol information in response
        response_data = {
            'success': True,
            'config': flat_config,
            'meta': metadata,  # Added metadata for frontend compatibility
            'secrets': secrets_meta,
            'source': 'config.yaml',  # Indicate this comes from YAML
            'symbol': selected_symbol if selected_symbol else None,  # Which symbol this config is for
            'symbol_enabled': symbol_config.get('enabled', False) if symbol_config else False,
            'available_symbols': list(yaml_data.get('symbols', {}).keys())  # All available symbols
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        log.error(f"Error getting all config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@yaml_config_bp.route('/api/config/flat', methods=['GET'])
def get_flat_config_compat():
    """
    Get flattened configuration (v5.0 multi-symbol support)
    
    Query Parameters:
        symbol (optional): Specific symbol to get config for (e.g., 'BTCUSD', 'ETHUSD')
                          If not provided, returns first enabled symbol (v4.0 compat)
    
    Returns:
        JSON response with flat config AND metadata
    """
    try:
        from flask import request
        
        # v5.0: Check for symbol parameter
        requested_symbol = request.args.get('symbol')
        
        # Load YAML config
        with open(CONFIG_FILE, 'r') as f:
            yaml_data = yaml.safe_load(f)
        
        # v5.0: Select which symbol's config to flatten
        selected_symbol = None
        symbol_enabled = False
        
        if requested_symbol:
            # Specific symbol requested - find it in config
            for sym_name, sym_cfg in yaml_data.get('symbols', {}).items():
                if sym_name == requested_symbol:
                    selected_symbol = sym_name
                    symbol_enabled = sym_cfg.get('enabled', False)
                    # Replace top-level bot config with this symbol's config
                    yaml_data['bot']['symbol'] = sym_name
                    yaml_data['bot']['mode'] = sym_cfg.get('mode', 'LONG')
                    yaml_data['bot']['product_id'] = sym_cfg.get('product_id', 0)
                    # v5.0: grid is nested inside symbol, so create top-level grid for flattening
                    if 'grid' not in yaml_data:
                        yaml_data['grid'] = {}
                    sym_grid = sym_cfg.get('grid', {})
                    yaml_data['grid']['geometry'] = sym_grid.get('geometry', {})
                    yaml_data['grid']['limits'] = sym_grid.get('limits', {})
                    yaml_data['grid']['behavior'] = sym_grid.get('behavior', {})
                    yaml_data['grid']['smart_gap_fill'] = sym_grid.get('smart_gap_fill', {})
                    break
            
            if not selected_symbol:
                # Symbol not found
                return jsonify({
                    'success': False,
                    'error': f'Symbol {requested_symbol} not found in config',
                    'available_symbols': list(yaml_data.get('symbols', {}).keys())
                }), 404
        else:
            # No symbol specified - use first enabled (v4.0 backward compat)
            for sym_name, sym_cfg in yaml_data.get('symbols', {}).items():
                if sym_cfg.get('enabled', False):
                    selected_symbol = sym_name
                    symbol_enabled = True
                    # Use this symbol's config
                    yaml_data['bot']['symbol'] = sym_name
                    yaml_data['bot']['mode'] = sym_cfg.get('mode', 'LONG')
                    yaml_data['bot']['product_id'] = sym_cfg.get('product_id', 0)
                    # v5.0: grid is nested inside symbol, so create top-level grid for flattening
                    if 'grid' not in yaml_data:
                        yaml_data['grid'] = {}
                    sym_grid = sym_cfg.get('grid', {})
                    yaml_data['grid']['geometry'] = sym_grid.get('geometry', {})
                    yaml_data['grid']['limits'] = sym_grid.get('limits', {})
                    yaml_data['grid']['behavior'] = sym_grid.get('behavior', {})
                    yaml_data['grid']['smart_gap_fill'] = sym_grid.get('smart_gap_fill', {})
                    break
        
        # Ensure grid structure exists even if no symbol was selected/enabled
        if 'grid' not in yaml_data:
            yaml_data['grid'] = {
                'geometry': {},
                'limits': {},
                'behavior': {},
                'smart_gap_fill': {}
            }
        
        # Flatten
        flat_config = flatten_config(yaml_data)
        
        # Add legacy aliases for backward compatibility with old frontend field names
        legacy_aliases = {
            # Grid geometry aliases (EXISTING - 8 fields)
            'GRIDBOT_REF': flat_config.get('GRID_GEOMETRY_REFERENCE', ''),
            'GRIDBOT_LOWER': flat_config.get('GRID_GEOMETRY_LOWER', ''),
            'GRIDBOT_UPPER': flat_config.get('GRID_GEOMETRY_UPPER', ''),
            'GRIDBOT_STEP': flat_config.get('GRID_GEOMETRY_STEP', ''),
            'GRIDBOT_LOT': flat_config.get('GRID_LIMITS_LOT_SIZE', ''),
            'GRIDBOT_MAX_OPEN': flat_config.get('GRID_LIMITS_MAX_OPEN_POSITIONS', ''),
            'GRIDBOT_GRID_MODE': flat_config.get('BOT_MODE', ''),
            'GRIDBOT_SYMBOL': flat_config.get('BOT_SYMBOL', ''),
            
            # Seeding system (EXISTING - 1 field)
            'GRIDBOT_SEED_INITIAL_COUNT': flat_config.get('GRID_BEHAVIOR_SEED_INITIAL_COUNT', ''),
            
            # Order execution (EXISTING - 2 fields)
            'GRIDBOT_POST_ONLY_MODE': flat_config.get('ORDER_EXECUTION_POST_ONLY_MODE', ''),
            'GRIDBOT_PRICE_BUFFER_PCT': flat_config.get('ORDER_EXECUTION_PRICE_BUFFER_PCT', ''),
            
            # Safety (EXISTING - 2 fields)
            'EXECUTE_ORDERS': flat_config.get('EXECUTION_SAFETY_EXECUTE_ORDERS', ''),
            'I_UNDERSTAND_LIVE': flat_config.get('EXECUTION_SAFETY_I_UNDERSTAND_LIVE', ''),
            
            # Trading mode (EXISTING - 1 field)
            'TRADING_MODE': flat_config.get('TRADING_MODE', ''),
            
            # ========== NEW MAPPINGS (51 fields) ==========
            
            # Grid Behavior (4 fields)
            'GRIDBOT_STRICT_GRID': flat_config.get('GRID_BEHAVIOR_STRICT_GRID', ''),
            'GRIDBOT_RUNG_SNAP_MODE': flat_config.get('GRID_BEHAVIOR_RUNG_SNAP_MODE', ''),
            'GRIDBOT_TICK_SIZE': flat_config.get('GRID_BEHAVIOR_TICK_SIZE', ''),
            'GRIDBOT_DYNAMIC_TICK_SIZE': flat_config.get('GRID_BEHAVIOR_DYNAMIC_TICK_SIZE', ''),
            
            # Startup (5 fields)
            'GRIDBOT_STRICT_START': flat_config.get('STARTUP_STRICT_START', ''),
            'GRIDBOT_FORGET_EXCHANGE_ON_START': flat_config.get('STARTUP_FORGET_EXCHANGE_ON_START', ''),
            'GRIDBOT_ENABLE_SMART_RECOVERY': flat_config.get('STARTUP_ENABLE_SMART_RECOVERY', ''),
            'GRIDBOT_CANCEL_ALL_ON_START': flat_config.get('STARTUP_CANCEL_ALL_ON_START', ''),
            'GRIDBOT_CANCEL_SCOPE': flat_config.get('STARTUP_CANCEL_SCOPE', ''),
            
            # Smart Gap Fill (3 fields)
            'SMART_GAP_FILL': flat_config.get('GRID_SMART_GAP_FILL_ENABLED', ''),
            'GAP_FILL_ORDER_TYPE': flat_config.get('GRID_SMART_GAP_FILL_ORDER_TYPE', ''),
            'MAX_GAP_FILL_LEVELS': flat_config.get('GRID_SMART_GAP_FILL_MAX_LEVELS', ''),
            
            # Order Execution (3 fields)
            'GRIDBOT_TAG_PREFIX': flat_config.get('ORDER_EXECUTION_TAG_PREFIX', ''),
            'GRIDBOT_ADOPT_UNTAGGED': flat_config.get('ORDER_EXECUTION_ADOPT_UNTAGGED', ''),
            'GRIDBOT_FILL_THRESHOLD': flat_config.get('ORDER_EXECUTION_FILL_THRESHOLD', ''),
            
            # Timing & Retries (3 fields)
            'GRIDBOT_MAX_RETRIES': flat_config.get('ORDER_EXECUTION_MAX_RETRIES', ''),
            'GRIDBOT_RETRY_DELAY': flat_config.get('ORDER_EXECUTION_RETRY_DELAY', ''),
            'GRIDBOT_COOLDOWN_SECONDS': flat_config.get('ORDER_EXECUTION_COOLDOWN_SECONDS', ''),
            
            # Health & Monitoring (4 fields)
            'GRIDBOT_HEALTH_CHECK_ENABLED': flat_config.get('HEALTH_CHECK_ENABLED', ''),
            'GRIDBOT_HEALTH_CHECK_INTERVAL': flat_config.get('HEALTH_CHECK_INTERVAL', ''),
            'GRIDBOT_LOG_PERFORMANCE': flat_config.get('PERFORMANCE_LOGGING_ENABLED', ''),
            'GRIDBOT_PERFORMANCE_INTERVAL': flat_config.get('PERFORMANCE_LOGGING_INTERVAL', ''),
            
            # Emergency Limits (4 fields)
            'GRIDBOT_MAX_DRIFT_ALERTS': flat_config.get('EMERGENCY_MAX_DRIFT_ALERTS', ''),
            'GRIDBOT_MAX_DISRUPTION_EVENTS': flat_config.get('EMERGENCY_MAX_DISRUPTION_EVENTS', ''),
            'GRIDBOT_EMERGENCY_PRICE_BUFFER': flat_config.get('RISK_LIMITS_EMERGENCY_PRICE_BUFFER', ''),
            'GRIDBOT_MARKET_DISRUPTION_COOLDOWN': flat_config.get('EMERGENCY_MARKET_DISRUPTION_COOLDOWN', ''),
            
            # Loss Limits (3 fields)
            'MAX_ACCOUNT_LOSS_INR': flat_config.get('GUARDIAN_MAX_ACCOUNT_LOSS_INR', ''),
            'USD_TO_INR_RATE': flat_config.get('GUARDIAN_USD_TO_INR_RATE', ''),
            'MAX_QTY_PER_ORDER': flat_config.get('GRID_LIMITS_MAX_QTY_PER_ORDER', ''),
            
            # Margin & Liquidation (10 fields)
            'MAINTENANCE_MARGIN_PERCENT': flat_config.get('LIQUIDATION_PROTECTION_MAINTENANCE_MARGIN_PERCENT', ''),
            'AUTO_MARGIN_TOPUP_ENABLED': flat_config.get('LIQUIDATION_PROTECTION_AUTO_MARGIN_TOPUP', ''),
            'AUTO_TOPUP_THRESHOLD': flat_config.get('LIQUIDATION_PROTECTION_AUTO_TOPUP_THRESHOLD', ''),
            'AUTO_TOPUP_TARGET': flat_config.get('LIQUIDATION_PROTECTION_AUTO_TOPUP_TARGET', ''),
            'MAX_TOPUPS_PER_POSITION': flat_config.get('LIQUIDATION_PROTECTION_MAX_TOPUPS_PER_POSITION', ''),
            'MIN_BALANCE_RESERVE_PERCENT': flat_config.get('LIQUIDATION_PROTECTION_MIN_BALANCE_RESERVE_PERCENT', ''),
            'MARGIN_WARNING_THRESHOLD': flat_config.get('LIQUIDATION_PROTECTION_MARGIN_WARNING_THRESHOLD', ''),
            'MARGIN_DANGER_THRESHOLD': flat_config.get('LIQUIDATION_PROTECTION_MARGIN_DANGER_THRESHOLD', ''),
            'MARGIN_CRITICAL_THRESHOLD': flat_config.get('LIQUIDATION_PROTECTION_MARGIN_CRITICAL_THRESHOLD', ''),
            'DISTANCE_TO_LIQ_WARNING': flat_config.get('LIQUIDATION_PROTECTION_DISTANCE_TO_LIQ_WARNING', ''),
            
            # Telegram (2 fields)
            'TELEGRAM_BOT_TOKEN': flat_config.get('TELEGRAM_BOT_TOKEN', ''),
            'TELEGRAM_CHAT_ID': flat_config.get('TELEGRAM_CHAT_ID', ''),
            
            # Heartbeat (6 fields)
            'ENABLE_HEARTBEAT': flat_config.get('HEARTBEAT_ENABLED', ''),
            'HEARTBEAT_TIMEOUT': flat_config.get('HEARTBEAT_TIMEOUT', ''),
            'HEARTBEAT_UPDATE_INTERVAL': flat_config.get('HEARTBEAT_UPDATE_INTERVAL', ''),
            'HEARTBEAT_MONITOR_INTERVAL': flat_config.get('HEARTBEAT_MONITOR_INTERVAL', ''),
            'HEARTBEAT_FILE': flat_config.get('HEARTBEAT_FILE', ''),
            'HEARTBEAT_ACTION': flat_config.get('HEARTBEAT_ACTION', ''),
            
            # Bot Heartbeat (1 field)
            'GRIDBOT_HB_SEC': flat_config.get('BOT_HEARTBEAT_SECONDS', ''),
        }
        flat_config.update(legacy_aliases)
        
        # Build metadata for each config key
        metadata = {}
        for key, value in flat_config.items():
            # Determine section from key prefix
            section = _get_key_section(key)
            
            # Check if secret
            is_secret = is_secret_key(key)
            
            metadata[key] = {
                'section': section,
                'redacted': is_secret,
                'has_value': bool(value),
                'source_key': key,
                'legacy_sources': []
            }
            
            # Redact secrets
            if is_secret:
                flat_config[key] = '***REDACTED***'
        
        return jsonify({
            'success': True,
            'config': flat_config,
            'meta': metadata,
            'source': 'config.yaml',
            # v5.0 multi-symbol fields
            'symbol': selected_symbol,
            'symbol_enabled': symbol_enabled,
            'available_symbols': list(yaml_data.get('symbols', {}).keys())
        }), 200
        
    except Exception as e:
        log.error(f"Error getting flat config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Alias for /api/config (connectionManager expects this)
@yaml_config_bp.route('/api/config', methods=['GET'])
def get_config_alias():
    """Alias for /api/config/flat - used by connectionManager state sync"""
    return get_flat_config_compat()



def _get_key_section(key_name):
    """Determine which section a config key belongs to"""
    key_upper = key_name.upper()
    
    # Map config keys to logical sections
    if any(x in key_upper for x in ['GRID_GEOMETRY', 'GRID_LIMITS', 'GRID_BEHAVIOR', 'GRID_SMART']):
        return 'Grid Configuration'
    elif any(x in key_upper for x in ['BOT_MODE', 'BOT_SYMBOL', 'BOT_HEARTBEAT']):
        return 'Trading'
    elif any(x in key_upper for x in ['GUARDIAN', 'CAPITAL_PROTECTION', 'SAFETY', 'LIQUIDATION']):
        return 'Risk Management'
    elif any(x in key_upper for x in ['STARTUP', 'SHUTDOWN', 'ORDER_EXECUTION', 'HEARTBEAT']):
        return 'Execution Control'
    elif any(x in key_upper for x in ['TELEGRAM', 'NOTIFICATION', 'ALERT']):
        return 'Notifications'
    elif any(x in key_upper for x in ['API_', 'WEBUI_']):
        return 'System'
    elif any(x in key_upper for x in ['LOG', 'DEBUG', 'PERFORMANCE']):
        return 'Logging'
    else:
        return 'General'


@yaml_config_bp.route('/api/auth/config', methods=['GET'])
def get_auth_config():
    """
    Get authentication configuration
    
    Returns:
        JSON with auth settings
    """
    try:
        # FIX: Don't call get_config() - it's too slow (100+ seconds)
        # Read auth settings directly from YAML without Pydantic validation
        with open(CONFIG_FILE, 'r') as f:
            yaml_data = yaml.safe_load(f)
        
        auth_enabled = False
        auth_user = 'admin'
        
        if yaml_data and 'webui' in yaml_data and 'auth' in yaml_data['webui']:
            auth_enabled = yaml_data['webui']['auth'].get('enabled', False)
            auth_user = yaml_data['webui']['auth'].get('user', 'admin')
        
        return jsonify({
            'success': True,
            'auth_enabled': auth_enabled,
            'auth_user': auth_user
        }), 200
        
    except Exception as e:
        log.error(f"Error getting auth config: {e}")
        return jsonify({
            'success': True,
            'auth_enabled': False,
            'auth_user': 'admin'
        }), 200


@yaml_config_bp.route('/api/config/confirm-runtime', methods=['POST'])
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


# =============================================================================
# BACKWARD COMPATIBILITY ALIASES FOR OLD FRONTEND
# =============================================================================

@yaml_config_bp.route('/api/config', methods=['POST'])
def legacy_update_config_short():
    """Backward compatibility alias for /api/yaml-config POST (used by frontend apiClient)"""
    return update_yaml_config()


@yaml_config_bp.route('/api/config/update', methods=['POST'])
def legacy_update_config():
    """Backward compatibility alias for /api/yaml-config POST"""
    return update_yaml_config()


@yaml_config_bp.route('/api/config/verify', methods=['GET'])
def legacy_verify_config():
    """
    Backward compatibility: Verify configuration is valid
    
    FIX: Returns quick syntax check only - Pydantic validation is too slow (100+ seconds)
    """
    try:
        # Quick YAML syntax check only
        with open(CONFIG_FILE, 'r') as f:
            yaml_data = yaml.safe_load(f)
        
        if not yaml_data:
            return jsonify({
                'success': False,
                'valid': False,
                'error': 'Empty configuration file'
            }), 400
        
        return jsonify({
            'success': True,
            'valid': True,
            'message': 'Configuration syntax is valid (fast check)',
            'source': 'config.yaml',
            'note': 'Full Pydantic validation skipped for performance'
        }), 200
        
    except Exception as e:
        log.error(f"Config validation failed: {e}")
        return jsonify({
            'success': False,
            'valid': False,
            'error': str(e)
        }), 400


@yaml_config_bp.route('/api/config/apply', methods=['POST'])
def legacy_apply_config():
    """Backward compatibility: Apply configuration changes (same as update)"""
    return update_yaml_config()


@yaml_config_bp.route('/api/config/feature-flags', methods=['GET'])
def legacy_get_feature_flags():
    """
    Backward compatibility: Get feature flags from config
    
    OPTIMIZED: Returns default flags immediately without loading full config
    to prevent 100+ second delays caused by Pydantic validation.
    """
    try:
        # FIX: Don't call get_config() - it takes 100+ seconds!
        # Return sensible defaults immediately
        flags = {
            'hot_reload_enabled': True,
            'webui_enabled': True,
            'guardian_enabled': True,
            'liquidation_protection_enabled': True,
            'health_check_enabled': True,
            'risk_analytics_enabled': True,
            'guardian_dashboard': True,
            'new_state_management': True,
            'data_aggregator': True,
            'circuit_breakers': True,
            'metrics_logging': True,
            'enhanced_health_checks': True,
            'new_webui_system': True
        }
        
        return jsonify({
            'success': True,
            'flags': flags
        }), 200
        
    except Exception as e:
        log.error(f"Error getting feature flags: {e}")
        return jsonify({
            'success': True,  # Still return success with defaults
            'flags': {
                'hot_reload_enabled': True,
                'webui_enabled': True,
                'guardian_enabled': True,
                'liquidation_protection_enabled': True,
                'health_check_enabled': True,
                'risk_analytics_enabled': True
            }
        }), 200


@yaml_config_bp.route('/api/config/feature-flags', methods=['POST'])
def legacy_update_feature_flags():
    """Backward compatibility: Update feature flags"""
    try:
        data = request.get_json()
        flag_updates = data.get('flags', {})
        
        if not flag_updates:
            return jsonify({'success': False, 'error': 'No flags provided'}), 400
        
        # Convert flag updates to YAML path format
        updates = {}
        flag_mapping = {
            'hot_reload_enabled': 'hot_reload.enabled',
            'webui_enabled': 'webui.enabled',
            'guardian_enabled': 'guardian.enabled',
            'liquidation_protection_enabled': 'liquidation_protection.enabled',
            'health_check_enabled': 'health_check.enabled',
            'risk_analytics_enabled': 'risk_analytics.enabled',
        }
        
        for flag, value in flag_updates.items():
            if flag in flag_mapping:
                updates[flag_mapping[flag]] = value
        
        # Load current config
        with open(CONFIG_FILE, 'r') as f:
            config = yaml.safe_load(f)
        
        # Apply updates
        for path, value in updates.items():
            keys = path.split('.')
            current = config
            
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            
            current[keys[-1]] = value
            log.info(f"Updated feature flag {path} = {value}")
        
        # Write back
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        return jsonify({
            'success': True,
            'message': f'Updated {len(updates)} feature flags',
            'updated_flags': list(flag_updates.keys())
        }), 200
        
    except Exception as e:
        log.error(f"Error updating feature flags: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@yaml_config_bp.route('/api/yaml-config/opportunistic-recovery', methods=['GET'])
def get_opportunistic_recovery_config():
    """
    Get opportunistic recovery configuration
    
    Returns:
        JSON response with opportunistic recovery settings
    """
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = yaml.safe_load(f)
        
        # Navigate to opportunistic recovery config
        opp_recovery = config.get('safety', {}).get('volatility', {}).get('opportunistic_recovery', {})
        
        return jsonify({
            'success': True,
            'data': {
                'enabled': opp_recovery.get('enabled', False),
                'max_orders_volatility': opp_recovery.get('max_orders_volatility', 5),
                'max_orders_startup': opp_recovery.get('max_orders_startup', 2),
                'cooldown_seconds': opp_recovery.get('cooldown_seconds', 30),
                'execution_delay_ms': opp_recovery.get('execution_delay_ms', 300),
                'min_profit_margin': opp_recovery.get('min_profit_margin', 500)
            }
        })
        
    except Exception as e:
        log.error(f"Error reading opportunistic recovery config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@yaml_config_bp.route('/api/yaml-config/opportunistic-recovery', methods=['POST'])
def update_opportunistic_recovery_config():
    """
    Update opportunistic recovery configuration
    
    Request body:
        {
            "enabled": true,
            "max_orders_volatility": 5,
            "max_orders_startup": 2,
            "execution_delay_ms": 300,
            "min_profit_margin": 500
        }
    
    Returns:
        JSON response with success status
    """
    try:
        data = request.get_json()
        
        # Load current config
        with open(CONFIG_FILE, 'r') as f:
            config = yaml.safe_load(f)
        
        # Ensure nested structure exists
        if 'safety' not in config:
            config['safety'] = {}
        if 'volatility' not in config['safety']:
            config['safety']['volatility'] = {}
        if 'opportunistic_recovery' not in config['safety']['volatility']:
            config['safety']['volatility']['opportunistic_recovery'] = {}
        
        opp_recovery = config['safety']['volatility']['opportunistic_recovery']
        
        # Update fields if provided
        updated_fields = []
        
        if 'enabled' in data:
            opp_recovery['enabled'] = bool(data['enabled'])
            updated_fields.append('enabled')
            log.info(f"Opportunistic recovery enabled: {data['enabled']}")
        
        if 'max_orders_volatility' in data:
            opp_recovery['max_orders_volatility'] = int(data['max_orders_volatility'])
            updated_fields.append('max_orders_volatility')
        
        if 'max_orders_startup' in data:
            opp_recovery['max_orders_startup'] = int(data['max_orders_startup'])
            updated_fields.append('max_orders_startup')
        
        if 'cooldown_seconds' in data:
            opp_recovery['cooldown_seconds'] = int(data['cooldown_seconds'])
            updated_fields.append('cooldown_seconds')
        
        if 'execution_delay_ms' in data:
            opp_recovery['execution_delay_ms'] = int(data['execution_delay_ms'])
            updated_fields.append('execution_delay_ms')
        
        if 'min_profit_margin' in data:
            opp_recovery['min_profit_margin'] = int(data['min_profit_margin'])
            updated_fields.append('min_profit_margin')
        
        # Write back to YAML
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        log.info(f"Updated opportunistic recovery config: {updated_fields}")
        
        return jsonify({
            'success': True,
            'message': f'Updated {len(updated_fields)} opportunistic recovery settings',
            'updated_fields': updated_fields,
            'current_config': opp_recovery
        })
        
    except Exception as e:
        log.error(f"Error updating opportunistic recovery config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# MULTI-SYMBOL CONFIG ENDPOINTS (v5.0)
# ============================================================================

@yaml_config_bp.route('/api/config/symbols/<symbol_name>', methods=['GET'])
def get_symbol_config(symbol_name):
    """
    Get configuration for a specific symbol
    
    Returns flattened config with GRIDBOT_* fields for this symbol only.
    This allows frontend to edit each symbol independently.
    
    Args:
        symbol_name: Symbol key (e.g., 'BTCUSD', 'ETHUSD')
    
    Example:
        GET /api/config/symbols/BTCUSD
        Response: {
            "success": true,
            "symbol": "BTCUSD",
            "config": {
                "GRIDBOT_REF": 88500,
                "GRIDBOT_LOWER": 85000,
                "GRIDBOT_UPPER": 92000,
                "GRIDBOT_STEP": 100,
                ...
            }
        }
    """
    try:
        symbol_name = symbol_name.upper()
        
        with open(CONFIG_FILE, 'r') as f:
            config = yaml.safe_load(f)
        
        # Support both v5.0 (symbols) and v6.0 (instances)
        config_version = config.get('version', '4.0')
        
        if config_version.startswith('6'):
            # V6.0: Check instances instead of symbols
            instances = config.get('instances', {})
            
            # Find all instances for this symbol (e.g., BTCUSD_LONG, BTCUSD_SHORT)
            symbol_instances = {
                inst_name: inst_config 
                for inst_name, inst_config in instances.items() 
                if inst_config.get('symbol') == symbol_name
            }
            
            if not symbol_instances:
                available = sorted(set(inst.get('symbol') for inst in instances.values() if inst.get('symbol')))
                return jsonify({
                    'success': False,
                    'error': f"Symbol '{symbol_name}' not found",
                    'available_symbols': available
                }), 404
            
            # Use enabled instance, or first instance if none enabled
            symbol_config = None
            instance_name = None
            for inst_name, inst_config in symbol_instances.items():
                if inst_config.get('enabled', False):
                    symbol_config = inst_config
                    instance_name = inst_name
                    break
            
            if not symbol_config:
                # No enabled instance, use first one
                instance_name = list(symbol_instances.keys())[0]
                symbol_config = symbol_instances[instance_name]
        else:
            # V5.0: Check symbols section
            symbols = config.get('symbols', {})
            
            if symbol_name not in symbols:
                available = list(symbols.keys())
                return jsonify({
                    'success': False,
                    'error': f"Symbol '{symbol_name}' not found",
                    'available_symbols': available
                }), 404
            
            symbol_config = symbols[symbol_name]
            instance_name = f"{symbol_name}_{symbol_config.get('mode', 'LONG')}"
        
        # Build flattened config for frontend (using legacy field names)
        flat_config = {}
        
        # Grid geometry
        grid = symbol_config.get('grid', {})
        geometry = grid.get('geometry', {})
        flat_config['GRIDBOT_REF'] = geometry.get('reference', 0)
        flat_config['GRIDBOT_LOWER'] = geometry.get('lower', 0)
        flat_config['GRIDBOT_UPPER'] = geometry.get('upper', 0)
        flat_config['GRIDBOT_STEP'] = geometry.get('step', 0)
        
        # Grid limits
        limits = grid.get('limits', {})
        flat_config['GRIDBOT_LOT'] = limits.get('lot_size', 0)
        flat_config['GRIDBOT_MAX_OPEN'] = limits.get('max_open_positions', 0)
        flat_config['MAX_QTY_PER_ORDER'] = limits.get('max_qty_per_order', 0)
        
        # Grid behavior
        behavior = grid.get('behavior', {})
        flat_config['GRIDBOT_STRICT_GRID'] = behavior.get('strict_grid', True)
        flat_config['GRIDBOT_RUNG_SNAP_MODE'] = behavior.get('rung_snap_mode', 'nearest')
        flat_config['GRIDBOT_TICK_SIZE'] = behavior.get('tick_size', 0.5)
        flat_config['GRIDBOT_DYNAMIC_TICK_SIZE'] = behavior.get('dynamic_tick_size', False)
        flat_config['GRIDBOT_SEED_INITIAL_COUNT'] = behavior.get('seed_initial_count', 5)
        
        # Smart gap fill
        gap_fill = grid.get('smart_gap_fill', {})
        flat_config['SMART_GAP_FILL'] = gap_fill.get('enabled', False)
        flat_config['GAP_FILL_ORDER_TYPE'] = gap_fill.get('order_type', 'limit')
        flat_config['MAX_GAP_FILL_LEVELS'] = gap_fill.get('max_levels', 3)
        
        # Bot mode and symbol
        flat_config['GRIDBOT_GRID_MODE'] = symbol_config.get('mode', 'LONG')
        flat_config['GRIDBOT_SYMBOL'] = symbol_name
        flat_config['PRODUCT_ID'] = symbol_config.get('product_id', 0)
        flat_config['ENABLED'] = symbol_config.get('enabled', False)
        
        # Safety settings (per-symbol)
        safety = symbol_config.get('safety', {})
        flat_config['MAX_ACCOUNT_LOSS_INR'] = safety.get('max_account_loss_inr', 7000)
        flat_config['MIN_LIQUIDATION_DISTANCE_PCT'] = safety.get('min_liquidation_distance_pct', 5)
        
        # RSI settings (per-symbol if available, else global)
        rsi = safety.get('rsi', config.get('safety', {}).get('rsi', {}))
        flat_config['RSI_ENABLED'] = rsi.get('enabled', True)
        flat_config['RSI_LONG_THRESHOLD'] = rsi.get('long_threshold', 30)
        flat_config['RSI_SHORT_THRESHOLD'] = rsi.get('short_threshold', 70)
        
        return jsonify({
            'success': True,
            'symbol': symbol_name,
            'enabled': symbol_config.get('enabled', False),
            'mode': symbol_config.get('mode', 'LONG'),
            'config': flat_config
        })
        
    except Exception as e:
        log.error(f"Error getting symbol config for {symbol_name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@yaml_config_bp.route('/api/config/symbols/<symbol_name>', methods=['POST'])
def update_symbol_config(symbol_name):
    """
    Update configuration for a specific symbol
    
    This saves changes to the correct symbol section in config.yaml,
    ensuring no cross-contamination between symbols.
    
    Args:
        symbol_name: Symbol key (e.g., 'BTCUSD', 'ETHUSD')
    
    Request Body:
        {
            "GRIDBOT_REF": 88500,
            "GRIDBOT_LOWER": 85000,
            "GRIDBOT_STEP": 100,
            ...
        }
    
    Returns:
        JSON response with success status
    """
    try:
        symbol_name = symbol_name.upper()
        data = request.get_json()
        
        with open(CONFIG_FILE, 'r') as f:
            config = yaml.safe_load(f)
        
        # Support both v5.0 (symbols) and v6.0 (instances)
        config_version = config.get('version', '4.0')
        
        if config_version.startswith('6'):
            # V6.0: Check instances instead of symbols
            instances = config.get('instances', {})
            
            # Find all instances for this symbol
            symbol_instances = {
                inst_name: inst_config 
                for inst_name, inst_config in instances.items() 
                if inst_config.get('symbol') == symbol_name
            }
            
            if not symbol_instances:
                return jsonify({
                    'success': False,
                    'error': f"Symbol '{symbol_name}' not found"
                }), 404
            
            # Use enabled instance, or first instance if none enabled
            instance_name = None
            for inst_name, inst_config in symbol_instances.items():
                if inst_config.get('enabled', False):
                    instance_name = inst_name
                    break
            
            if not instance_name:
                instance_name = list(symbol_instances.keys())[0]
            
            symbol_config = config['instances'][instance_name]
            config_path = ['instances', instance_name]
        else:
            # V5.0: Check symbols section
            symbols = config.get('symbols', {})
            
            if symbol_name not in symbols:
                return jsonify({
                    'success': False,
                    'error': f"Symbol '{symbol_name}' not found"
                }), 404
            
            symbol_config = symbols[symbol_name]
            config_path = ['symbols', symbol_name]
        
        updated_fields = []
        
        # Map flat keys to nested symbol config paths
        field_mappings = {
            # Grid geometry
            'GRIDBOT_REF': ('grid', 'geometry', 'reference'),
            'GRIDBOT_LOWER': ('grid', 'geometry', 'lower'),
            'GRIDBOT_UPPER': ('grid', 'geometry', 'upper'),
            'GRIDBOT_STEP': ('grid', 'geometry', 'step'),
            
            # Grid limits
            'GRIDBOT_LOT': ('grid', 'limits', 'lot_size'),
            'GRIDBOT_MAX_OPEN': ('grid', 'limits', 'max_open_positions'),
            'MAX_QTY_PER_ORDER': ('grid', 'limits', 'max_qty_per_order'),
            
            # Grid behavior
            'GRIDBOT_STRICT_GRID': ('grid', 'behavior', 'strict_grid'),
            'GRIDBOT_RUNG_SNAP_MODE': ('grid', 'behavior', 'rung_snap_mode'),
            'GRIDBOT_TICK_SIZE': ('grid', 'behavior', 'tick_size'),
            'GRIDBOT_DYNAMIC_TICK_SIZE': ('grid', 'behavior', 'dynamic_tick_size'),
            'GRIDBOT_SEED_INITIAL_COUNT': ('grid', 'behavior', 'seed_initial_count'),
            
            # Smart gap fill
            'SMART_GAP_FILL': ('grid', 'smart_gap_fill', 'enabled'),
            'GAP_FILL_ORDER_TYPE': ('grid', 'smart_gap_fill', 'order_type'),
            'MAX_GAP_FILL_LEVELS': ('grid', 'smart_gap_fill', 'max_levels'),
            
            # Bot mode
            'GRIDBOT_GRID_MODE': ('mode',),
            'ENABLED': ('enabled',),
            
            # Safety
            'MAX_ACCOUNT_LOSS_INR': ('safety', 'max_account_loss_inr'),
            'MIN_LIQUIDATION_DISTANCE_PCT': ('safety', 'min_liquidation_distance_pct'),
            
            # RSI (per-symbol)
            'RSI_ENABLED': ('safety', 'rsi', 'enabled'),
            'RSI_LONG_THRESHOLD': ('safety', 'rsi', 'long_threshold'),
            'RSI_SHORT_THRESHOLD': ('safety', 'rsi', 'short_threshold'),
        }
        
        for flat_key, value in data.items():
            if flat_key in field_mappings:
                path = field_mappings[flat_key]
                
                # Navigate and create nested structure
                current = symbol_config
                for key in path[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                
                # Convert value type
                if isinstance(value, str):
                    # Try to convert string to appropriate type
                    if value.lower() in ('true', 'false'):
                        value = value.lower() == 'true'
                    else:
                        try:
                            if '.' in value:
                                value = float(value)
                            else:
                                value = int(value)
                        except ValueError:
                            pass  # Keep as string
                
                # Set the value
                current[path[-1]] = value
                updated_fields.append(flat_key)
                log.info(f"Updated {symbol_name}.{'.'.join(path)} = {value}")
        
        # Write back to YAML
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        return jsonify({
            'success': True,
            'symbol': symbol_name,
            'message': f'Updated {len(updated_fields)} fields for {symbol_name}',
            'updated_fields': updated_fields
        })
        
    except Exception as e:
        log.error(f"Error updating symbol config for {symbol_name}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@yaml_config_bp.route('/api/config/symbols/<symbol_name>/enable', methods=['POST'])
def enable_symbol(symbol_name):
    """
    Enable a symbol for trading
    
    Args:
        symbol_name: Symbol key (e.g., 'BTCUSD', 'ETHUSD')
    """
    try:
        symbol_name = symbol_name.upper()
        
        with open(CONFIG_FILE, 'r') as f:
            config = yaml.safe_load(f)
        
        # Support both v5.0 (symbols) and v6.0 (instances)
        config_version = config.get('version', '4.0')
        
        if config_version.startswith('6'):
            # V6.0: Check instances instead of symbols
            instances = config.get('instances', {})
            
            # Find primary instance for this symbol (first one)
            instance_name = None
            for inst_name, inst_config in instances.items():
                if inst_config.get('symbol') == symbol_name:
                    instance_name = inst_name
                    break
            
            if not instance_name:
                return jsonify({
                    'success': False,
                    'error': f"Symbol '{symbol_name}' not found"
                }), 404
            
            config['instances'][instance_name]['enabled'] = True
        else:
            # V5.0: Check symbols section
            symbols = config.get('symbols', {})
            
            if symbol_name not in symbols:
                return jsonify({
                    'success': False,
                    'error': f"Symbol '{symbol_name}' not found"
                }), 404
            
            config['symbols'][symbol_name]['enabled'] = True
        
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        log.info(f"✅ Enabled symbol: {symbol_name}")
        
        return jsonify({
            'success': True,
            'symbol': symbol_name,
            'enabled': True,
            'message': f'{symbol_name} is now enabled for trading'
        })
        
    except Exception as e:
        log.error(f"Error enabling symbol {symbol_name}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@yaml_config_bp.route('/api/config/symbols/<symbol_name>/disable', methods=['POST'])
def disable_symbol(symbol_name):
    """
    Disable a symbol from trading
    
    Args:
        symbol_name: Symbol key (e.g., 'BTCUSD', 'ETHUSD')
    """
    try:
        symbol_name = symbol_name.upper()
        
        with open(CONFIG_FILE, 'r') as f:
            config = yaml.safe_load(f)
        
        # Support both v5.0 (symbols) and v6.0 (instances)
        config_version = config.get('version', '4.0')
        
        if config_version.startswith('6'):
            # V6.0: Check instances instead of symbols
            instances = config.get('instances', {})
            
            # Find primary instance for this symbol (first one)
            instance_name = None
            for inst_name, inst_config in instances.items():
                if inst_config.get('symbol') == symbol_name:
                    instance_name = inst_name
                    break
            
            if not instance_name:
                return jsonify({
                    'success': False,
                    'error': f"Symbol '{symbol_name}' not found"
                }), 404
            
            config['instances'][instance_name]['enabled'] = False
        else:
            # V5.0: Check symbols section
            symbols = config.get('symbols', {})
            
            if symbol_name not in symbols:
                return jsonify({
                    'success': False,
                    'error': f"Symbol '{symbol_name}' not found"
                }), 404
            
            config['symbols'][symbol_name]['enabled'] = False
        
        if not instance_name:
            return jsonify({
                'success': False,
                'error': f"Symbol '{symbol_name}' not found"
            }), 404
        
        config['instances'][instance_name]['enabled'] = False
        
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        log.info(f"⛔ Disabled symbol: {symbol_name} (instance: {instance_name})")
        
        return jsonify({
            'success': True,
            'symbol': symbol_name,
            'enabled': False,
            'message': f'{symbol_name} is now disabled'
        })
        
    except Exception as e:
        log.error(f"Error disabling symbol {symbol_name}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@yaml_config_bp.route('/api/config/symbols', methods=['PUT'])
def create_symbol():
    """
    Create a new symbol configuration
    
    Request Body:
        {
            "symbol": "SOLUSD",
            "product_id": 12345,
            "mode": "LONG",
            "enabled": false,
            "grid": {
                "lower": 100,
                "upper": 200,
                "step": 5,
                "reference": 150
            },
            "lot_size": 1,
            "max_open_positions": 10
        }
    
    Returns:
        JSON response with success status
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        symbol_name = data.get('symbol', '').upper()
        if not symbol_name:
            return jsonify({'success': False, 'error': 'Symbol name is required'}), 400
        
        product_id = data.get('product_id')
        if not product_id:
            return jsonify({'success': False, 'error': 'Product ID is required'}), 400
        
        with open(CONFIG_FILE, 'r') as f:
            config = yaml.safe_load(f)
        
        # Initialize symbols section if doesn't exist
        if 'symbols' not in config:
            config['symbols'] = {}
        
        # Check if symbol already exists
        if symbol_name in config['symbols']:
            return jsonify({
                'success': False, 
                'error': f"Symbol '{symbol_name}' already exists"
            }), 409
        
        # Get grid config from request or use defaults
        grid = data.get('grid', {})
        lower = grid.get('lower', 0)
        upper = grid.get('upper', 0)
        step = grid.get('step', 100)
        reference = grid.get('reference', (lower + upper) / 2 if lower and upper else 0)
        
        # Create symbol config structure matching existing symbols
        new_symbol_config = {
            'enabled': data.get('enabled', False),
            'mode': data.get('mode', 'LONG').upper(),
            'product_id': str(product_id),
            'grid': {
                'geometry': {
                    'reference': str(reference),
                    'lower': str(lower),
                    'upper': str(upper),
                    'step': str(step)
                },
                'limits': {
                    'max_open_positions': str(data.get('max_open_positions', 10)),
                    'lot_size': str(data.get('lot_size', 1)),
                    'short_lot_size': str(data.get('short_lot_size', 1)),
                    'max_open_orders': 20,
                    'max_qty_per_order': str(data.get('max_qty_per_order', 1))
                },
                'behavior': {
                    'strict_grid': 'true',
                    'rung_snap_mode': 'below',
                    'tick_size': str(data.get('tick_size', '0.5')),
                    'dynamic_tick_size': 'true',
                    'seed_initial_count': '0'
                },
                'smart_gap_fill': {
                    'order_type': 'limit',
                    'max_levels': '3',
                    'enabled': 'false'
                }
            },
            'safety': {
                'max_account_loss_inr': str(data.get('max_account_loss_inr', 25000)),
                'min_liquidation_distance_pct': data.get('min_liquidation_distance_pct', 50.0),
                'rsi': {
                    'enabled': True,
                    'long_threshold': 19.5,
                    'short_threshold': 25
                }
            }
        }
        
        config['symbols'][symbol_name] = new_symbol_config
        
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        log.info(f"✅ Created new symbol: {symbol_name} (product_id: {product_id})")
        
        return jsonify({
            'success': True,
            'symbol': symbol_name,
            'product_id': product_id,
            'message': f"Symbol '{symbol_name}' created successfully"
        }), 201
        
    except Exception as e:
        log.error(f"Error creating symbol: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@yaml_config_bp.route('/api/config/symbols/<symbol_name>', methods=['DELETE'])
def delete_symbol(symbol_name):
    """
    Delete a symbol configuration
    
    Args:
        symbol_name: Symbol key (e.g., 'SOLUSD')
    
    Returns:
        JSON response with success status
    """
    try:
        symbol_name = symbol_name.upper()
        
        with open(CONFIG_FILE, 'r') as f:
            config = yaml.safe_load(f)
        
        symbols = config.get('symbols', {})
        
        if symbol_name not in symbols:
            return jsonify({
                'success': False,
                'error': f"Symbol '{symbol_name}' not found"
            }), 404
        
        # Check if symbol is enabled - don't delete enabled symbols
        if symbols[symbol_name].get('enabled', False):
            return jsonify({
                'success': False,
                'error': f"Cannot delete enabled symbol. Disable '{symbol_name}' first."
            }), 400
        
        del config['symbols'][symbol_name]
        
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        log.info(f"🗑️ Deleted symbol: {symbol_name}")
        
        return jsonify({
            'success': True,
            'symbol': symbol_name,
            'message': f"Symbol '{symbol_name}' deleted successfully"
        })
        
    except Exception as e:
        log.error(f"Error deleting symbol {symbol_name}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
