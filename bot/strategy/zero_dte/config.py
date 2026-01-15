"""
Configuration loader for Zero DTE bot
"""
import os
import yaml
from pathlib import Path
from typing import Optional
from loguru import logger

from config.schemas.zero_dte_schemas import ZeroDTEConfig


def load_config(config_path: Optional[str] = None) -> ZeroDTEConfig:
    """
    Load and validate Zero DTE configuration
    
    Args:
        config_path: Path to YAML config file. Defaults to config/zero_dte_config.yaml
        
    Returns:
        Validated ZeroDTEConfig object
    """
    if config_path is None:
        # Default path relative to project root
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / "config" / "zero_dte_config.yaml"
    else:
        config_path = Path(config_path)
    
    if not config_path.exists():
        logger.warning(f"Config file not found at {config_path}, using defaults")
        return ZeroDTEConfig()
    
    try:
        with open(config_path, 'r') as f:
            raw_config = yaml.safe_load(f)
        
        # Validate with Pydantic
        config = ZeroDTEConfig(**raw_config)
        logger.info(f"Loaded 0DTE config: {config.strategy.name} v{config.strategy.version}")
        
        return config
        
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse config YAML: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        raise


def save_config(config: ZeroDTEConfig, config_path: Optional[str] = None) -> bool:
    """
    Save configuration to YAML file
    
    Args:
        config: ZeroDTEConfig object to save
        config_path: Path to save config file
        
    Returns:
        True if successful
    """
    if config_path is None:
        project_root = Path(__file__).parent.parent.parent
        config_path = project_root / "config" / "zero_dte_config.yaml"
    else:
        config_path = Path(config_path)
    
    try:
        config_dict = config.dict()
        
        with open(config_path, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
        
        logger.info(f"Saved 0DTE config to {config_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save config: {e}")
        return False


def update_config(updates: dict, config_path: Optional[str] = None) -> ZeroDTEConfig:
    """
    Update specific configuration values
    
    Args:
        updates: Dictionary of updates (nested keys supported)
        config_path: Path to config file
        
    Returns:
        Updated ZeroDTEConfig object
    """
    config = load_config(config_path)
    config_dict = config.dict()
    
    # Apply updates
    def deep_update(base: dict, updates: dict):
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                deep_update(base[key], value)
            else:
                base[key] = value
    
    deep_update(config_dict, updates)
    
    # Re-validate
    new_config = ZeroDTEConfig(**config_dict)
    save_config(new_config, config_path)
    
    return new_config
