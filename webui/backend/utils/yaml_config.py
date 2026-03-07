"""
YAML Config Integration for WebUI
Provides utilities for WebUI routes to read/write config.yaml instead of grid_config.env
"""

import os
import logging
from pathlib import Path
from typing import Any, Dict, Optional
import yaml

from webui.backend.sealed import sealed

log = logging.getLogger("webui_yaml_config")

# Base directory
BASE_DIR = Path(__file__).parent.parent.parent

# Config file paths
YAML_CONFIG_FILE = BASE_DIR / "config.yaml"
# Legacy reference - now using config.yaml
ENV_CONFIG_FILE = BASE_DIR / "config.yaml"


def get_yaml_config() -> Optional[Dict[str, Any]]:
    """
    Load YAML configuration from config.yaml
    
    Returns:
        dict: Configuration dictionary or None if failed
    """
    try:
        import sys
        sys.path.insert(0, str(BASE_DIR))
        from config.loader import get_config
        yaml_config = get_config()
        # Pydantic v2 uses model_dump() instead of dict()
        return yaml_config.model_dump() if hasattr(yaml_config, 'model_dump') else yaml_config.dict()
    except Exception as e:
        log.warning(f"Failed to load YAML config: {e}")
        return None


def get_config_value(yaml_path: str, env_var: str = None, default: Any = None) -> Any:
    """
    Get configuration value with fallback from YAML → env var → default
    
    Args:
        yaml_path: Dot-notation path in YAML (e.g., "safety.execute_orders")
        env_var: Environment variable name (fallback)
        default: Default value if both fail
        
    Returns:
        Configuration value
        
    Example:
        value = get_config_value("safety.execute_orders", "EXECUTE_ORDERS", False)
    """
    # Try YAML first
    yaml_config = get_yaml_config()
    if yaml_config:
        try:
            # Navigate nested dict using dot notation
            value = yaml_config
            for key in yaml_path.split('.'):
                value = value[key]
            return value
        except (KeyError, TypeError):
            pass
    
    # Fallback to environment variable
    if env_var:
        env_value = os.getenv(env_var)
        if env_value is not None:
            # Try to convert to appropriate type
            if default is not None:
                if isinstance(default, bool):
                    return env_value.lower() in ('true', '1', 'yes')
                elif isinstance(default, int):
                    return int(env_value)
                elif isinstance(default, float):
                    return float(env_value)
            return env_value
    
    # Final fallback
    return default


@sealed
def update_yaml_config(updates: Dict[str, Any]) -> bool:
    """
    Update YAML configuration file
    
    Args:
        updates: Dictionary of dot-notation paths and new values
                 e.g., {"safety.execute_orders": True, "grid.limits.lot_size": 2}
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Load current YAML
        with open(YAML_CONFIG_FILE, 'r') as f:
            config = yaml.safe_load(f)
        
        # Apply updates
        for path, value in updates.items():
            keys = path.split('.')
            current = config
            
            # Navigate to parent
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            
            # Set value
            current[keys[-1]] = value
        
        # Write back to file
        with open(YAML_CONFIG_FILE, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        log.info(f"Updated YAML config with {len(updates)} changes")
        return True
        
    except Exception as e:
        log.error(f"Failed to update YAML config: {e}")
        return False


# Configuration mapping: YAML path → env var
CONFIG_MAP = {
    # Safety
    "safety.execute_orders": "EXECUTE_ORDERS",
    "safety.live_acknowledgment": "I_UNDERSTAND_LIVE",
    "safety.volatility.enabled": "VOLATILITY_SAFETY_ENABLED",
    "safety.volatility.max_iv": "VOLATILITY_MAX_IV",
    "safety.volatility.max_rv": "VOLATILITY_MAX_RV",
    "safety.volatility.max_spread": "VOLATILITY_MAX_SPREAD",
    "safety.volatility.check_interval": "VOLATILITY_CHECK_INTERVAL",
    "safety.volatility.auto_resume": "VOLATILITY_AUTO_RESUME",
    "safety.volatility.resume_buffer": "VOLATILITY_RESUME_BUFFER",
    "safety.circuit_breaker.enabled": "CIRCUIT_BREAKER_ENABLED",
    "safety.circuit_breaker.failure_threshold": "CIRCUIT_BREAKER_FAILURE_THRESHOLD",
    "safety.circuit_breaker.timeout_seconds": "CIRCUIT_BREAKER_TIMEOUT",
    "safety.circuit_breaker.half_open_calls": "CIRCUIT_BREAKER_HALF_OPEN_CALLS",
    "safety.confirmation_guard.enabled": "CONFIRMATION_GUARD_ENABLED",
    "safety.confirmation_guard.poll_interval": "CONFIRMATION_POLL_INTERVAL",
    "safety.confirmation_guard.chaos_threshold": "CONFIRMATION_CHAOS_THRESHOLD",
    
    # Capital Protection
    "capital_protection.equity_floor.enabled": "EQUITY_FLOOR_INR",  # enabled if > 0
    "capital_protection.equity_floor.floor_inr": "EQUITY_FLOOR_INR",
    "capital_protection.equity_floor.check_interval": "EQUITY_FLOOR_CHECK_INTERVAL",
    "capital_protection.equity_floor.require_acknowledgment": "EQUITY_FLOOR_REQUIRE_ACK",
    "capital_protection.drawdown_cap.enabled": "DRAWDOWN_CAP_ENABLED",
    "capital_protection.drawdown_cap.max_pct": "DRAWDOWN_MAX_PCT",
    "capital_protection.drawdown_cap.window_days": "DRAWDOWN_WINDOW_DAYS",
    "capital_protection.drawdown_cap.hysteresis_pct": "DRAWDOWN_HYSTERESIS_PCT",
    "capital_protection.drawdown_cap.check_interval": "DRAWDOWN_CHECK_INTERVAL",
    "capital_protection.two_man_rule.enabled": "TWO_MAN_RULE_ENABLED",
    "capital_protection.two_man_rule.timeout_seconds": "TWO_MAN_RULE_TIMEOUT_SEC",
    "capital_protection.two_man_rule.auto_revert": "TWO_MAN_RULE_AUTO_REVERT",
    "capital_protection.exposure_growth.enabled": "EXPOSURE_GROWTH_ENABLED",
    "capital_protection.exposure_growth.max_tranches_per_minute": "MAX_NEW_TRANCHES_PER_MINUTE",
    "capital_protection.exposure_growth.max_notional_inr_per_minute": "MAX_NOTIONAL_INR_PER_MINUTE",
    "capital_protection.exposure_growth.queue_enabled": "EXPOSURE_GROWTH_QUEUE_ENABLED",
    "capital_protection.pending_budget.max_notional_inr": "MAX_PENDING_NOTIONAL_INR",
    "capital_protection.pending_budget.buffer_pct": "PENDING_BUDGET_BUFFER_PCT",
    
    # Guardian
    "guardian.enabled": "GUARDIAN_ENABLED",
    "guardian.check_interval": "GUARDIAN_CHECK_INTERVAL",
    "guardian.max_account_loss_inr": "GUARDIAN_MAX_ACCOUNT_LOSS_INR",
    "guardian.usd_to_inr_rate": "USD_TO_INR_RATE",
    "guardian.liquidation_critical": "GUARDIAN_LIQUIDATION_CRITICAL",
    "guardian.auto_close_positions": "GUARDIAN_AUTO_CLOSE_POSITIONS",
    "guardian.close_order_type": "GUARDIAN_CLOSE_ORDER_TYPE",
    "guardian.cancel_orders_on_emergency": "GUARDIAN_CANCEL_ORDERS_ON_EMERGENCY",
    
    # Liquidation Protection
    "liquidation_protection.enabled": "LIQUIDATION_PROTECTION_ENABLED",
    "liquidation_protection.margin_utilization_max": "MARGIN_UTILIZATION_MAX",
    "liquidation_protection.margin_utilization_warning_1": "MARGIN_UTILIZATION_WARNING_1",
    "liquidation_protection.margin_utilization_warning_2": "MARGIN_UTILIZATION_WARNING_2",
    "liquidation_protection.margin_emergency_reserve": "MARGIN_EMERGENCY_RESERVE",
    "liquidation_protection.liquidation_distance_min": "LIQUIDATION_DISTANCE_MIN",
    "liquidation_protection.liquidation_distance_target": "LIQUIDATION_DISTANCE_TARGET",
    "liquidation_protection.liquidation_distance_critical": "LIQUIDATION_DISTANCE_CRITICAL",
    
    # Risk Limits
    "risk_limits.max_account_loss_inr": "MAX_ACCOUNT_LOSS_INR",
    "risk_limits.usd_to_inr_rate": "USD_TO_INR_RATE",
    "risk_limits.max_drift_alerts": "MAX_DRIFT_ALERTS",
    "risk_limits.max_disruption_events": "MAX_DISRUPTION_EVENTS",
    "risk_limits.emergency_price_buffer": "EMERGENCY_PRICE_BUFFER",
    
    # Grid
    "grid.geometry.lower": "GRIDBOT_LOWER",
    "grid.geometry.upper": "GRIDBOT_UPPER",
    "grid.geometry.step": "GRIDBOT_STEP",
    "grid.geometry.reference": "GRIDBOT_REF",
    "grid.limits.max_open_positions": "GRIDBOT_MAX_OPEN",
    "grid.limits.lot_size": "GRIDBOT_LOT",
    "grid.limits.max_open_orders": "MAX_OPEN_ORDERS",
    "grid.behavior.strict_grid": "STRICT_GRID",
    
    # Trading
    "trading_mode": "TRADING_MODE",
    "bot.mode": "GRIDBOT_GRID_MODE",
}


def get_env_to_yaml_mapping() -> Dict[str, str]:
    """Get reverse mapping: env var → YAML path"""
    return {v: k for k, v in CONFIG_MAP.items()}
