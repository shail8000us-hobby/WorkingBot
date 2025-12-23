"""
Universal configuration loader.
Supports both ENV and YAML formats with validation.
"""

import yaml
import os
from pathlib import Path
from typing import Union, Optional
from dotenv import load_dotenv

from config.models import RootConfig
from config.env_mapping import (
    ENV_TO_YAML_MAPPING,
    set_nested_value,
    get_nested_value,
    convert_bool,
    convert_int,
    convert_float,
    convert_str,
    infer_converter
)


class ConfigLoader:
    """Load and validate configuration from YAML or ENV files"""
    
    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """Initialize config loader
        
        Args:
            config_path: Path to config file (auto-detected if None)
        """
        self.config_path = Path(config_path) if config_path else self._detect_config()
        
    def _detect_config(self) -> Path:
        """Auto-detect configuration file"""
        candidates = [
            Path('config.yaml'),
            Path('config/config.yaml'),
            Path('config.yaml'),
        ]
        
        for path in candidates:
            if path.exists():
                print(f"✅ Detected config file: {path}")
                return path
                
        raise FileNotFoundError(
            "No configuration file found. Looking for:\n" +
            "\n".join(f"  - {p}" for p in candidates)
        )
        
    def load(self) -> RootConfig:
        """Load and validate configuration
        
        Returns:
            Validated RootConfig instance
        """
        print(f"📖 Loading configuration from: {self.config_path}")
        
        if self.config_path.suffix in ['.yaml', '.yml']:
            config = self._load_yaml()
        elif self.config_path.suffix == '.env' or self.config_path.name.endswith('.env'):
            config = self._load_env()
        else:
            raise ValueError(f"Unsupported config format: {self.config_path}")
        
        # Validate cross-field constraints
        config.validate_cross_field_constraints()
        
        print("✅ Configuration loaded and validated successfully")
        return config
        
    def _load_yaml(self) -> RootConfig:
        """Load YAML configuration with validation"""
        with open(self.config_path) as f:
            data = yaml.safe_load(f)
        
        if data is None:
            raise ValueError(f"Empty YAML file: {self.config_path}")
        
        # Validate against Pydantic models
        config = RootConfig(**data)
        return config
        
    def _load_env(self) -> RootConfig:
        """Load ENV configuration (backward compatibility)"""
        from config.env_converter import env_to_dict
        
        # Load environment variables
        load_dotenv(self.config_path)
        
        # Convert to dict structure
        data = env_to_dict()
        
        # Validate against Pydantic models
        config = RootConfig(**data)
        return config
        
    def save_yaml(self, config: RootConfig, output_path: Union[str, Path]):
        """Save configuration as YAML
        
        Args:
            config: Configuration to save
            output_path: Output file path
        """
        output_path = Path(output_path)
        
        # Convert to dict
        data = config.dict(exclude_none=True)
        
        # Create parent directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save as YAML
        with open(output_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, indent=2)
        
        print(f"✅ Configuration saved to: {output_path}")


# Global configuration instance (singleton)
_config: Optional[RootConfig] = None
_config_loader: Optional[ConfigLoader] = None


def get_config(reload: bool = False) -> RootConfig:
    """Get global configuration instance
    
    Args:
        reload: Force reload from disk
        
    Returns:
        Global RootConfig instance
    """
    global _config, _config_loader
    
    if _config is None or reload:
        if _config_loader is None:
            _config_loader = ConfigLoader()
        _config = _config_loader.load()
    
    return _config


def reload_config() -> RootConfig:
    """Reload configuration from disk
    
    Returns:
        Reloaded RootConfig instance
    """
    return get_config(reload=True)


def save_config(config: RootConfig, path: Union[str, Path] = "config.yaml"):
    """Save configuration to YAML file
    
    Args:
        config: Configuration to save
        path: Output file path
    """
    loader = ConfigLoader()
    loader.save_yaml(config, path)


def get_api_credentials(trading_mode: Optional[str] = None):
    """Get API credentials from environment variables
    
    This function loads credentials from secrets/api_keys.env and returns
    the appropriate keys based on trading mode.
    
    Args:
        trading_mode: 'live' or 'demo'. If None, uses config.trading_mode
        
    Returns:
        dict with 'api_key' and 'api_secret'
    """
    # Load secrets from .env file (security best practice)
    secrets_file = Path(__file__).parent.parent / 'secrets' / 'api_keys.env'
    if secrets_file.exists():
        load_dotenv(secrets_file, override=True)
    
    # Get trading mode from config if not specified
    if trading_mode is None:
        config = get_config()
        trading_mode = config.trading_mode
    
    # Get appropriate credentials based on mode
    if trading_mode == 'live':
        api_key = os.getenv('LIVE_DELTA_API_KEY') or os.getenv('DELTA_API_KEY')
        api_secret = os.getenv('LIVE_DELTA_API_SECRET') or os.getenv('DELTA_API_SECRET')
    else:  # demo/testnet
        api_key = os.getenv('DEMO_DELTA_API_KEY') or os.getenv('DELTA_API_KEY')
        api_secret = os.getenv('DEMO_DELTA_API_SECRET') or os.getenv('DELTA_API_SECRET')
    
    return {
        'api_key': api_key,
        'api_secret': api_secret
    }
