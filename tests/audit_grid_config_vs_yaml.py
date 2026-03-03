#!/usr/bin/env python3
"""
Audit grid_config.env vs config.yaml
Identifies which settings from grid_config.env are missing in config.yaml
"""

import re
from pathlib import Path
import yaml

# Load grid_config.env and extract all settings
grid_config_path = Path("grid_config.env")
grid_settings = {}

with open(grid_config_path, 'r') as f:
    for line in f:
        line = line.strip()
        # Skip comments and empty lines
        if not line or line.startswith('#'):
            continue
        # Match KEY=VALUE pattern
        match = re.match(r'^([A-Z_][A-Z0-9_]*)=(.*)$', line)
        if match:
            key, value = match.groups()
            grid_settings[key] = value

# Load config.yaml
config_yaml_path = Path("config.yaml")
with open(config_yaml_path, 'r') as f:
    yaml_config = yaml.safe_load(f)

# Flatten YAML config to dotted keys
def flatten_dict(d, parent_key='', sep='.'):
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

yaml_flat = flatten_dict(yaml_config)

# Define mapping from grid_config.env keys to YAML keys
MAPPING = {
    'TRADING_MODE': 'trading_mode',
    'GRIDBOT_LOWER': 'grid.geometry.lower',
    'GRIDBOT_UPPER': 'grid.geometry.upper',
    'GRIDBOT_STEP': 'grid.geometry.step',
    'GRIDBOT_REF': 'grid.geometry.reference',
    'GRIDBOT_SYMBOL': 'bot.symbol',
    'GRIDBOT_LOT': 'grid.limits.lot_size',
    'GRIDBOT_MAX_OPEN': 'grid.limits.max_open_positions',
    'GRIDBOT_HB_SEC': 'bot.heartbeat_seconds',
    'GRIDBOT_SEED_INITIAL_COUNT': 'grid.behavior.seed_initial_count',
    'GRIDBOT_GRID_MODE': 'bot.mode',
    'SMART_GAP_FILL': 'grid.smart_gap_fill.enabled',
    'GAP_FILL_ORDER_TYPE': 'grid.smart_gap_fill.order_type',
    'MAX_GAP_FILL_LEVELS': 'grid.smart_gap_fill.max_levels',
    'GRIDBOT_STRICT_GRID': 'grid.behavior.strict_grid',
    'GRIDBOT_RUNG_SNAP_MODE': 'grid.behavior.rung_snap_mode',
    'GRIDBOT_TICK_SIZE': 'grid.behavior.tick_size',
    'GRIDBOT_DYNAMIC_TICK_SIZE': 'grid.behavior.dynamic_tick_size',
    'GRIDBOT_SYNC_DURATION': 'startup.sync_duration',
    'GRIDBOT_SHUTDOWN_DURATION': 'shutdown.shutdown_duration',
    'GRIDBOT_STRICT_START': 'startup.strict_start',
    'GRIDBOT_FORGET_EXCHANGE_ON_START': 'startup.forget_exchange_on_start',
    'GRIDBOT_ENABLE_SMART_RECOVERY': 'startup.enable_smart_recovery',
    'GRIDBOT_CANCEL_ALL_ON_START': 'startup.cancel_all_on_start',
    'GRIDBOT_CANCEL_SCOPE': 'startup.cancel_scope',
    'GRIDBOT_TAG_PREFIX': 'order_execution.tag_prefix',
    'GRIDBOT_ADOPT_UNTAGGED': 'order_execution.adopt_untagged',
    'GRIDBOT_POST_ONLY_MODE': 'order_execution.post_only_mode',
    'GRIDBOT_PRICE_BUFFER_PCT': 'order_execution.price_buffer_pct',
    'GRIDBOT_FILL_THRESHOLD': 'order_execution.fill_threshold',
    'GRIDBOT_MAX_RETRIES': 'order_execution.max_retries',
    'GRIDBOT_RETRY_DELAY': 'order_execution.retry_delay',
    'GRIDBOT_COOLDOWN_SECONDS': 'order_execution.cooldown_seconds',
    'GRIDBOT_HEALTH_CHECK_ENABLED': 'health_check.enabled',
    'GRIDBOT_HEALTH_CHECK_INTERVAL': 'health_check.interval',
    'GRIDBOT_LOG_PERFORMANCE': 'performance_logging.enabled',
    'GRIDBOT_PERFORMANCE_INTERVAL': 'performance_logging.interval',
    'I_UNDERSTAND_LIVE': 'safety.i_understand_live',
    'EXECUTE_ORDERS': 'safety.execute_orders',
    'MAX_ACCOUNT_LOSS_INR': 'risk_limits.max_account_loss_inr',
    'USD_TO_INR_RATE': 'risk_limits.usd_to_inr_rate',
    'MAX_OPEN_ORDERS': 'grid.limits.max_open_orders',
    'GRIDBOT_LOT_SIZE': 'grid.limits.lot_size',
    'MAX_QTY_PER_ORDER': 'grid.limits.max_qty_per_order',
    'ENABLE_HEARTBEAT': 'heartbeat.enabled',
    'HEARTBEAT_TIMEOUT': 'heartbeat.timeout',
    'HEARTBEAT_UPDATE_INTERVAL': 'heartbeat.update_interval',
    'HEARTBEAT_MONITOR_INTERVAL': 'heartbeat.monitor_interval',
    'HEARTBEAT_FILE': 'heartbeat.file',
    'HEARTBEAT_ACTION': 'heartbeat.action',
    'VOLATILITY_SAFETY_ENABLED': 'safety.volatility.enabled',
    'VOLATILITY_MAX_IV': 'safety.volatility.max_iv',
    'VOLATILITY_MAX_RV': 'safety.volatility.max_rv',
    'VOLATILITY_MAX_SPREAD': 'safety.volatility.max_spread',
    'VOLATILITY_CHECK_INTERVAL': 'safety.volatility.check_interval',
    'VOLATILITY_AUTO_RESUME': 'safety.volatility.auto_resume',
    'VOLATILITY_RESUME_BUFFER': 'safety.volatility.resume_buffer',
    'GUARDIAN_ENABLED': 'guardian.enabled',
    'GUARDIAN_CHECK_INTERVAL': 'guardian.check_interval',
    'GUARDIAN_MAX_ACCOUNT_LOSS_INR': 'guardian.max_account_loss_inr',
    'GUARDIAN_USD_TO_INR_RATE': 'guardian.usd_to_inr_rate',
    'GUARDIAN_LIQUIDATION_CRITICAL': 'guardian.liquidation_critical',
    'GUARDIAN_AUTO_CLOSE_POSITIONS': 'guardian.auto_close_positions',
    'GUARDIAN_CLOSE_ORDER_TYPE': 'guardian.close_order_type',
    'GUARDIAN_CANCEL_ORDERS_ON_EMERGENCY': 'guardian.cancel_orders_on_emergency',
    'GUARDIAN_ALERT_THRESHOLD_80': 'guardian.alert_threshold_80',
    'GUARDIAN_ALERT_THRESHOLD_90': 'guardian.alert_threshold_90',
    'GUARDIAN_DAILY_SUMMARY': 'guardian.daily_summary',
    'CONFIRMATION_GUARD_ENABLED': 'safety.confirmation_guard.enabled',
    'CIRCUIT_BREAKER_ENABLED': 'safety.circuit_breaker.enabled',
    'CIRCUIT_BREAKER_FAILURE_THRESHOLD': 'safety.circuit_breaker.failure_threshold',
    'CIRCUIT_BREAKER_TIMEOUT': 'safety.circuit_breaker.timeout',
    'EQUITY_FLOOR_INR': 'capital_protection.equity_floor.floor_inr',
    'EQUITY_FLOOR_CHECK_INTERVAL': 'capital_protection.equity_floor.check_interval',
    'EQUITY_FLOOR_REQUIRE_ACK': 'capital_protection.equity_floor.require_acknowledgment',
    'DRAWDOWN_CAP_ENABLED': 'capital_protection.drawdown_cap.enabled',
    'DRAWDOWN_MAX_PCT': 'capital_protection.drawdown_cap.max_pct',
    'DRAWDOWN_WINDOW_DAYS': 'capital_protection.drawdown_cap.window_days',
    'DRAWDOWN_HYSTERESIS_PCT': 'capital_protection.drawdown_cap.hysteresis_pct',
    'DRAWDOWN_CHECK_INTERVAL': 'capital_protection.drawdown_cap.check_interval',
    'TWO_MAN_RULE_ENABLED': 'capital_protection.two_man_rule.enabled',
    'TWO_MAN_RULE_TIMEOUT_SEC': 'capital_protection.two_man_rule.timeout_seconds',
    'TWO_MAN_RULE_AUTO_REVERT': 'capital_protection.two_man_rule.auto_revert',
    'EXPOSURE_GROWTH_ENABLED': 'capital_protection.exposure_growth.enabled',
    'MAX_NEW_TRANCHES_PER_MINUTE': 'capital_protection.exposure_growth.max_tranches_per_minute',
    'MAX_NOTIONAL_INR_PER_MINUTE': 'capital_protection.exposure_growth.max_notional_inr_per_minute',
    'EXPOSURE_GROWTH_QUEUE_ENABLED': 'capital_protection.exposure_growth.queue_enabled',
    'MAX_PENDING_NOTIONAL_INR': 'capital_protection.pending_budget.max_notional_inr',
    'PENDING_BUDGET_BUFFER_PCT': 'capital_protection.pending_budget.buffer_pct',
    'LIQUIDATION_PROTECTION_ENABLED': 'liquidation_protection.enabled',
    'MARGIN_UTILIZATION_MAX': 'liquidation_protection.margin_utilization_max',
    'MARGIN_UTILIZATION_WARNING_1': 'liquidation_protection.margin_utilization_warning_1',
    'MARGIN_UTILIZATION_WARNING_2': 'liquidation_protection.margin_utilization_warning_2',
    'MARGIN_EMERGENCY_RESERVE': 'liquidation_protection.margin_emergency_reserve',
    'LIQUIDATION_DISTANCE_MIN': 'liquidation_protection.liquidation_distance_min',
    'LIQUIDATION_DISTANCE_TARGET': 'liquidation_protection.liquidation_distance_target',
    'LIQUIDATION_DISTANCE_CRITICAL': 'liquidation_protection.liquidation_distance_critical',
    'REAL_TIME_MONITORING_ENABLED': 'liquidation_protection.real_time_monitoring',
    'WEBSOCKET_MARGIN_UPDATES': 'liquidation_protection.websocket_margin_updates',
    'WEBSOCKET_PORTFOLIO_UPDATES': 'liquidation_protection.websocket_portfolio_updates',
    'MARGIN_UTILIZATION_CRITICAL': 'liquidation_protection.margin_utilization_critical',
    'MARGIN_UTILIZATION_WARNING': 'liquidation_protection.margin_utilization_warning',
    'LIQUIDATION_DISTANCE_WARNING': 'liquidation_protection.liquidation_distance_warning',
    'WEBUI_ALLOWED_ORIGINS': 'webui.allowed_origins',
    'WEBUI_PORT': 'webui.port',
    'ERROR_COLLECTOR_ENABLED': 'webui.errors.collector_enabled',
    'ERROR_DB_PATH': 'webui.errors.db_path',
}

print("=" * 100)
print("GRID_CONFIG.ENV vs CONFIG.YAML AUDIT")
print("=" * 100)
print()

# Check which grid_config settings are mapped and match
matched = []
mismatched = []
missing_in_yaml = []

for env_key, yaml_key in MAPPING.items():
    if env_key in grid_settings:
        env_value = grid_settings[env_key]
        yaml_value = yaml_flat.get(yaml_key)
        
        if yaml_value is not None:
            # Convert for comparison
            env_str = str(env_value).lower().strip()
            yaml_str = str(yaml_value).lower().strip()
            
            # Handle boolean conversions
            if env_str in ('true', '1', 'yes'):
                env_str = 'true'
            if env_str in ('false', '0', 'no'):
                env_str = 'false'
            if yaml_str in ('true', '1', 'yes'):
                yaml_str = 'true'
            if yaml_str in ('false', '0', 'no'):
                yaml_str = 'false'
                
            if env_str == yaml_str:
                matched.append((env_key, yaml_key, env_value))
            else:
                mismatched.append((env_key, yaml_key, env_value, yaml_value))
        else:
            missing_in_yaml.append((env_key, yaml_key, env_value))

# Check for unmapped grid_config settings
unmapped = []
for env_key in grid_settings:
    if env_key not in MAPPING and not env_key.startswith(('DEMO_', 'LIVE_', 'TELEGRAM_', 'DELTA_', 'AI_', 'OLLAMA_', 'WEBUI_AUTH')):
        unmapped.append((env_key, grid_settings[env_key]))

print(f"📊 SUMMARY")
print(f"─" * 100)
print(f"Total grid_config.env settings: {len(grid_settings)}")
print(f"Mapped and matching:            {len(matched)}")
print(f"Mapped but mismatched:          {len(mismatched)}")
print(f"Missing in config.yaml:         {len(missing_in_yaml)}")
print(f"Unmapped (need analysis):       {len(unmapped)}")
print()

if mismatched:
    print(f"\n⚠️  MISMATCHED VALUES ({len(mismatched)})")
    print(f"─" * 100)
    for env_key, yaml_key, env_val, yaml_val in mismatched:
        print(f"  {env_key}")
        print(f"    grid_config.env: {env_val}")
        print(f"    config.yaml:     {yaml_val} → {yaml_key}")
        print()

if missing_in_yaml:
    print(f"\n❌ MISSING IN CONFIG.YAML ({len(missing_in_yaml)})")
    print(f"─" * 100)
    for env_key, yaml_key, env_val in missing_in_yaml:
        print(f"  {env_key} = {env_val}")
        print(f"    Should be at: {yaml_key}")
        print()

if unmapped:
    print(f"\n🔍 UNMAPPED SETTINGS (Need Manual Review) ({len(unmapped)})")
    print(f"─" * 100)
    for env_key, env_val in sorted(unmapped):
        print(f"  {env_key} = {env_val}")
    print()

print(f"\n✅ MATCHED ({len(matched)})")
print(f"─" * 100)
for env_key, yaml_key, env_val in matched[:20]:  # Show first 20
    print(f"  ✓ {env_key} → {yaml_key}")
if len(matched) > 20:
    print(f"  ... and {len(matched) - 20} more")
print()

print("=" * 100)
print("END OF AUDIT")
print("=" * 100)
