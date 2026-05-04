"""
ENV to YAML mapping table.
Maps all 245+ environment variables to YAML paths.
"""

from typing import Dict, Any

# Complete mapping of ENV variables to YAML paths
ENV_TO_YAML_MAPPING: Dict[str, str] = {
    # Trading mode
    'TRADING_MODE': 'trading_mode',
    
    # Bot configuration
    'GRIDBOT_SYMBOL': 'bot.symbol',
    'GRIDBOT_GRID_MODE': 'bot.mode',
    'GRIDBOT_TRADING_ENABLED': 'bot.trading_enabled',
    'GRIDBOT_HB_SEC': 'bot.heartbeat_seconds',
    
    # Grid geometry
    'GRIDBOT_LOWER': 'grid.geometry.lower',
    'GRIDBOT_UPPER': 'grid.geometry.upper',
    'GRIDBOT_STEP': 'grid.geometry.step',
    'GRIDBOT_REF': 'grid.geometry.reference',

    # RANGE mode (dual-zone)
    'GRIDBOT_ANCHOR': 'dual_mode.anchor',
    'GRIDBOT_HYSTERESIS': 'dual_mode.hysteresis',
    
    # Grid limits
    'GRIDBOT_MAX_OPEN': 'grid.limits.max_open_positions',
    'GRIDBOT_LOT': 'grid.limits.lot_size',
    'GRIDBOT_LOT_SIZE': 'grid.limits.lot_size',
    'MAX_OPEN_ORDERS': 'grid.limits.max_open_orders',
    'MAX_QTY_PER_ORDER': 'grid.limits.max_qty_per_order',
    
    # Grid behavior
    'GRIDBOT_STRICT_GRID': 'grid.behavior.strict_grid',
    'GRIDBOT_RUNG_SNAP_MODE': 'grid.behavior.rung_snap_mode',
    'GRIDBOT_TICK_SIZE': 'grid.behavior.tick_size',
    'GRIDBOT_DYNAMIC_TICK_SIZE': 'grid.behavior.dynamic_tick_size',
    'GRIDBOT_SEED_INITIAL_COUNT': 'grid.behavior.seed_initial_count',
    
    # Smart gap fill
    'SMART_GAP_FILL': 'grid.smart_gap_fill.enabled',
    'GAP_FILL_ORDER_TYPE': 'grid.smart_gap_fill.order_type',
    'MAX_GAP_FILL_LEVELS': 'grid.smart_gap_fill.max_levels',
    
    # Capital protection - Equity floor
    'EQUITY_FLOOR_INR': 'capital_protection.equity_floor.floor_inr',
    'EQUITY_FLOOR_CHECK_INTERVAL': 'capital_protection.equity_floor.check_interval',
    'EQUITY_FLOOR_REQUIRE_ACK': 'capital_protection.equity_floor.require_acknowledgment',
    
    # Capital protection - Drawdown cap
    'DRAWDOWN_CAP_ENABLED': 'capital_protection.drawdown_cap.enabled',
    'DRAWDOWN_MAX_PCT': 'capital_protection.drawdown_cap.max_pct',
    'DRAWDOWN_WINDOW_DAYS': 'capital_protection.drawdown_cap.window_days',
    'DRAWDOWN_HYSTERESIS_PCT': 'capital_protection.drawdown_cap.hysteresis_pct',
    'DRAWDOWN_CHECK_INTERVAL': 'capital_protection.drawdown_cap.check_interval',
    
    # Capital protection - Two-man rule
    'TWO_MAN_RULE_ENABLED': 'capital_protection.two_man_rule.enabled',
    'TWO_MAN_RULE_TIMEOUT_SEC': 'capital_protection.two_man_rule.timeout_seconds',
    'TWO_MAN_RULE_AUTO_REVERT': 'capital_protection.two_man_rule.auto_revert',
    
    # Capital protection - Exposure growth
    'EXPOSURE_GROWTH_ENABLED': 'capital_protection.exposure_growth.enabled',
    'MAX_NEW_TRANCHES_PER_MINUTE': 'capital_protection.exposure_growth.max_tranches_per_minute',
    'MAX_NOTIONAL_INR_PER_MINUTE': 'capital_protection.exposure_growth.max_notional_inr_per_minute',
    'EXPOSURE_GROWTH_QUEUE_ENABLED': 'capital_protection.exposure_growth.queue_enabled',
    
    # Capital protection - Pending budget
    'MAX_PENDING_NOTIONAL_INR': 'capital_protection.pending_budget.max_notional_inr',
    'PENDING_BUDGET_BUFFER_PCT': 'capital_protection.pending_budget.buffer_pct',
    
    # Safety - Flash move
    'FLASH_MOVE_ENABLED': 'safety.flash_move.enabled',
    'FLASH_MOVE_THRESHOLD_PCT': 'safety.flash_move.threshold_pct',
    'FLASH_MOVE_WINDOW_SECONDS': 'safety.flash_move.window_seconds',
    'FLASH_MOVE_COOLDOWN_SECONDS': 'safety.flash_move.cooldown_seconds',
    
    # Safety - Spread guard
    'SPREAD_GUARD_ENABLED': 'safety.spread_guard.enabled',
    'SPREAD_EXPLOSION_MULTIPLIER': 'safety.spread_guard.explosion_multiplier',
    
    # Safety - Volatility
    'VOLATILITY_SAFETY_ENABLED': 'safety.volatility.enabled',
    'VOLATILITY_MAX_IV': 'safety.volatility.max_iv',
    'VOLATILITY_MAX_RV': 'safety.volatility.max_rv',
    'VOLATILITY_MAX_SPREAD': 'safety.volatility.max_spread',
    'VOLATILITY_CHECK_INTERVAL': 'safety.volatility.check_interval',
    'VOLATILITY_AUTO_RESUME': 'safety.volatility.auto_resume',
    'VOLATILITY_RESUME_BUFFER': 'safety.volatility.resume_buffer',
    
    # Safety - Circuit breaker
    'CIRCUIT_BREAKER_ENABLED': 'safety.circuit_breaker.enabled',
    'CIRCUIT_BREAKER_FAILURE_THRESHOLD': 'safety.circuit_breaker.failure_threshold',
    'CIRCUIT_BREAKER_TIMEOUT': 'safety.circuit_breaker.timeout_seconds',
    'CIRCUIT_BREAKER_HALF_OPEN_CALLS': 'safety.circuit_breaker.half_open_calls',
    
    # Safety - Confirmation guard
    'CONFIRMATION_GUARD_ENABLED': 'safety.confirmation_guard.enabled',
    'CONFIRMATION_POLL_INTERVAL': 'safety.confirmation_guard.poll_interval',
    'CONFIRMATION_CHAOS_THRESHOLD': 'safety.confirmation_guard.chaos_threshold',
    
    # Guardian
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
    'GUARDIAN_COOLDOWN': 'guardian.cooldown',
    
    # Liquidation protection
    'LIQUIDATION_PROTECTION_ENABLED': 'liquidation_protection.enabled',
    'MARGIN_UTILIZATION_MAX': 'liquidation_protection.margin_utilization_max',
    'MARGIN_UTILIZATION_WARNING_1': 'liquidation_protection.margin_utilization_warning_1',
    'MARGIN_UTILIZATION_WARNING_2': 'liquidation_protection.margin_utilization_warning_2',
    'MARGIN_EMERGENCY_RESERVE': 'liquidation_protection.margin_emergency_reserve',
    'REDUCE_ONLY_MODE_AT_UTILIZATION': 'liquidation_protection.reduce_only_at_utilization',
    'LIQUIDATION_DISTANCE_MIN': 'liquidation_protection.liquidation_distance_min',
    'LIQUIDATION_DISTANCE_TARGET': 'liquidation_protection.liquidation_distance_target',
    'LIQUIDATION_DISTANCE_CRITICAL': 'liquidation_protection.liquidation_distance_critical',
    'REAL_TIME_MONITORING_ENABLED': 'liquidation_protection.real_time_monitoring',
    'WEBSOCKET_MARGIN_UPDATES': 'liquidation_protection.websocket_margin_updates',
    'WEBSOCKET_PORTFOLIO_UPDATES': 'liquidation_protection.websocket_portfolio_updates',
    'MARGIN_UTILIZATION_CRITICAL': 'liquidation_protection.margin_utilization_critical',
    'MARGIN_UTILIZATION_WARNING': 'liquidation_protection.margin_utilization_warning',
    'LIQUIDATION_DISTANCE_WARNING': 'liquidation_protection.liquidation_distance_warning',
    'GUARDIAN_AUTO_MARGIN_TOPUP': 'liquidation_protection.auto_margin_topup',
    'GUARDIAN_AUTO_TOPUP_AMOUNT_INR': 'liquidation_protection.auto_topup_amount_inr',
    
    # Startup
    'GRIDBOT_SYNC_DURATION': 'startup.sync_duration',
    'GRIDBOT_STRICT_START': 'startup.strict_start',
    'GRIDBOT_FORGET_EXCHANGE_ON_START': 'startup.forget_exchange_on_start',
    'GRIDBOT_ENABLE_SMART_RECOVERY': 'startup.enable_smart_recovery',
    'GRIDBOT_CANCEL_ALL_ON_START': 'startup.cancel_all_on_start',
    'GRIDBOT_CANCEL_SCOPE': 'startup.cancel_scope',
    
    # Shutdown
    'GRIDBOT_SHUTDOWN_DURATION': 'shutdown.shutdown_duration',
    
    # Order execution
    'GRIDBOT_POST_ONLY_MODE': 'order_execution.post_only_mode',
    'GRIDBOT_PRICE_BUFFER_PCT': 'order_execution.price_buffer_pct',
    'GRIDBOT_FILL_THRESHOLD': 'order_execution.fill_threshold',
    'GRIDBOT_MAX_RETRIES': 'order_execution.max_retries',
    'GRIDBOT_RETRY_DELAY': 'order_execution.retry_delay',
    'GRIDBOT_COOLDOWN_SECONDS': 'order_execution.cooldown_seconds',
    'GRIDBOT_TAG_PREFIX': 'order_execution.tag_prefix',
    'GRIDBOT_ADOPT_UNTAGGED': 'order_execution.adopt_untagged',
    
    # Heartbeat
    'ENABLE_HEARTBEAT': 'heartbeat.enabled',
    'HEARTBEAT_TIMEOUT': 'heartbeat.timeout',
    'HEARTBEAT_UPDATE_INTERVAL': 'heartbeat.update_interval',
    'HEARTBEAT_MONITOR_INTERVAL': 'heartbeat.monitor_interval',
    'HEARTBEAT_FILE': 'heartbeat.file',
    'HEARTBEAT_ACTION': 'heartbeat.action',
    
    # Health check
    'GRIDBOT_HEALTH_CHECK_ENABLED': 'health_check.enabled',
    'GRIDBOT_HEALTH_CHECK_INTERVAL': 'health_check.interval',
    
    # Performance logging
    'GRIDBOT_LOG_PERFORMANCE': 'performance_logging.enabled',
    'GRIDBOT_PERFORMANCE_INTERVAL': 'performance_logging.interval',
    
    # API endpoints
    'DEMO_PUBLIC_BASE_URL': 'api.demo_public_url',
    'DEMO_PRIVATE_BASE_URL': 'api.demo_private_url',
    'LIVE_PUBLIC_BASE_URL': 'api.live_public_url',
    'LIVE_PRIVATE_BASE_URL': 'api.live_private_url',
    
    # Telegram
    'TELEGRAM_BOT_TOKEN': 'telegram.bot_token',
    'TELEGRAM_CHAT_ID': 'telegram.chat_id',
    'LIVE_TELEGRAM_BOT_TOKEN': 'telegram.live_bot_token',
    'LIVE_TELEGRAM_CHAT_ID': 'telegram.live_chat_id',
    'DEMO_TELEGRAM_BOT_TOKEN': 'telegram.demo_bot_token',
    'DEMO_TELEGRAM_CHAT_ID': 'telegram.demo_chat_id',
    
    # Logging
    'LOG_LEVEL': 'logging.level',
    
    # WebUI
    'WEBUI_PORT': 'webui.port',
    'WEBUI_ALLOWED_ORIGINS': 'webui.allowed_origins',
    
    # Risk limits
    'MAX_ACCOUNT_LOSS_INR': 'risk_limits.max_account_loss_inr',
    'USD_TO_INR_RATE': 'risk_limits.usd_to_inr_rate',
    'GRIDBOT_MAX_DRIFT_ALERTS': 'risk_limits.max_drift_alerts',
    'GRIDBOT_MAX_DISRUPTION_EVENTS': 'risk_limits.max_disruption_events',
    'GRIDBOT_EMERGENCY_PRICE_BUFFER': 'risk_limits.emergency_price_buffer',
    
    # Execution safety
    'I_UNDERSTAND_LIVE': 'execution_safety.i_understand_live',
    'EXECUTE_ORDERS': 'execution_safety.execute_orders',
    'REQUIRE_LIVE_PASSWORD': 'execution_safety.require_live_password',
    'LIVE_TRADING_PASSWORD': 'execution_safety.live_trading_password',
}


# Type converters for different field types
def convert_bool(value: str) -> bool:
    """Convert string to boolean"""
    if isinstance(value, bool):
        return value
    return value.lower() in ('true', '1', 'yes', 'on')


def convert_int(value: str) -> int:
    """Convert string to integer"""
    if isinstance(value, int):
        return value
    return int(value)


def convert_float(value: str) -> float:
    """Convert string to float"""
    if isinstance(value, float):
        return value
    return float(value)


def convert_str(value: str) -> str:
    """Pass through string"""
    return str(value)


# Get nested value from dict using dot notation
def get_nested_value(data: dict, path: str) -> Any:
    """Get value from nested dict using dot notation
    
    Example:
        get_nested_value({'a': {'b': {'c': 1}}}, 'a.b.c') -> 1
    """
    keys = path.split('.')
    value = data
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
    return value


# Set nested value in dict using dot notation
def set_nested_value(data: dict, path: str, value: Any) -> None:
    """Set value in nested dict using dot notation
    
    Example:
        set_nested_value({}, 'a.b.c', 1) -> {'a': {'b': {'c': 1}}}
    """
    keys = path.split('.')
    d = data
    for key in keys[:-1]:
        if key not in d:
            d[key] = {}
        d = d[key]
    d[keys[-1]] = value


# Determine type converter based on value
def infer_converter(value: str) -> callable:
    """Infer appropriate type converter from value"""
    if value.lower() in ('true', 'false', '0', '1', 'yes', 'no', 'on', 'off'):
        return convert_bool
    try:
        int(value)
        return convert_int
    except ValueError:
        pass
    try:
        float(value)
        return convert_float
    except ValueError:
        pass
    return convert_str
