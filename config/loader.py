"""
Universal configuration loader.
Supports both ENV and YAML formats with validation.

V6.0 MULTI-INSTANCE ARCHITECTURE:
Instance = Symbol + Mode (e.g., BTCUSD_LONG, BTCUSD_SHORT)

Key functions:
- get_config(): Get global RootConfig
- get_instance_config(name): Get config for specific instance
- get_all_instances(): Get all enabled instances
- get_instances_for_symbol(symbol): Get instances for a symbol
"""

import yaml
import os
import fcntl
from pathlib import Path
from typing import Union, Optional, List, Dict
from dotenv import load_dotenv

from config.models import RootConfig, InstanceConfig, GridMode
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
        # Get the project root directory (3 levels up from config/loader.py)
        project_root = Path(__file__).parent.parent
        
        # FIX M5: Use absolute paths based on project root to avoid CWD dependency
        candidates = [
            project_root / 'config.yaml',  # Project root (absolute path) - primary
            Path('config.yaml'),  # Current directory (fallback for dev)
            project_root / 'config' / 'config.yaml',  # Config subdirectory
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
        
        # Save as YAML with file locking (prevents concurrent write corruption)
        lock_path = output_path.with_suffix('.lock')
        with open(lock_path, 'w') as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            try:
                with open(output_path, 'w') as f:
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False, indent=2)
            finally:
                fcntl.flock(lock_file, fcntl.LOCK_UN)
        
        print(f"✅ Configuration saved to: {output_path}")


# Global configuration instance (singleton)
_config: Optional[RootConfig] = None
_config_loader: Optional[ConfigLoader] = None
_reload_in_progress: bool = False  # Re-entrancy guard for reload

# Cached API credentials (load_dotenv is expensive — opens a file FD every call)
_cached_credentials: Optional[dict] = None
_credentials_mode: Optional[str] = None  # trading mode the cache was built for


def get_config(reload: bool = False) -> RootConfig:
    """Get global configuration instance
    
    Args:
        reload: Force reload from disk
        
    Returns:
        Global RootConfig instance
    """
    global _config, _config_loader, _reload_in_progress
    
    # RE-ENTRANCY GUARD: Prevent recursive reload_config() calls
    if reload and _reload_in_progress:
        # Return current config instead of triggering recursion
        return _config if _config else RootConfig()
    
    if _config is None or reload:
        if reload:
            _reload_in_progress = True
        try:
            if _config_loader is None:
                _config_loader = ConfigLoader()
            _config = _config_loader.load()
        finally:
            if reload:
                _reload_in_progress = False
    
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
    """Get API credentials from environment variables.

    Credentials are cached after the first load so that load_dotenv() is only
    ever called ONCE per trading-mode.  Calling load_dotenv() on every request
    opens a new file descriptor each time which quickly exhausts the OS limit
    ([Errno 24] Too many open files) and causes 500 errors across the board.

    Args:
        trading_mode: 'live' or 'demo'. If None, uses config.trading_mode

    Returns:
        dict with 'api_key' and 'api_secret'
    """
    global _cached_credentials, _credentials_mode

    # Resolve trading mode first (cheap — uses already-cached config singleton)
    if trading_mode is None:
        config = get_config()
        trading_mode = config.trading_mode

    # Return cached result if trading mode hasn't changed
    if _cached_credentials is not None and _credentials_mode == trading_mode:
        return _cached_credentials

    # Load the .env file ONCE and cache env vars into the process environment.
    # load_dotenv() is safe to call once — subsequent os.getenv() calls are free.
    secrets_file = Path(__file__).parent.parent / 'secrets' / 'api_keys.env'
    if secrets_file.exists():
        load_dotenv(secrets_file, override=True)

    # Get appropriate credentials based on mode
    if trading_mode == 'live':
        api_key = os.getenv('LIVE_DELTA_API_KEY') or os.getenv('DELTA_API_KEY')
        api_secret = os.getenv('LIVE_DELTA_API_SECRET') or os.getenv('DELTA_API_SECRET')
    else:  # demo/testnet
        api_key = os.getenv('DEMO_DELTA_API_KEY') or os.getenv('DELTA_API_KEY')
        api_secret = os.getenv('DEMO_DELTA_API_SECRET') or os.getenv('DELTA_API_SECRET')

    _cached_credentials = {'api_key': api_key, 'api_secret': api_secret}
    _credentials_mode = trading_mode
    
    # FIX M6: Fail fast if credentials are missing instead of returning None silently
    if not api_key or not api_secret:
        import warnings
        warnings.warn(
            f"API credentials not found for {trading_mode} mode! "
            f"Check secrets/api_keys.env or environment variables.",
            RuntimeWarning,
            stacklevel=2
        )
    
    return _cached_credentials


def invalidate_credentials_cache():
    """Force credentials to be reloaded on the next get_api_credentials() call.

    Call this if the secrets/api_keys.env file changes at runtime.
    """
    global _cached_credentials, _credentials_mode
    _cached_credentials = None
    _credentials_mode = None


# ═══════════════════════════════════════════════════════════════════════════
# V6.0 INSTANCE HELPERS (Instance = Symbol + Mode)
# ═══════════════════════════════════════════════════════════════════════════

def get_instance_config(instance_name: str) -> Optional[InstanceConfig]:
    """Get configuration for a specific instance
    
    V6.0 ARCHITECTURE: Instance = Symbol + Mode
    
    Args:
        instance_name: Instance name (e.g., "BTCUSD_LONG", "ETHUSD_SHORT")
        
    Returns:
        InstanceConfig if found and enabled, None otherwise
        
    Example:
        config = get_instance_config("BTCUSD_LONG")
        if config:
            print(f"Grid range: {config.grid.geometry.lower} - {config.grid.geometry.upper}")
            print(f"RSI stop threshold: {config.get_rsi_config().stop_threshold}")
    """
    root_config = get_config()
    
    # V6.0: Check instances section first
    if root_config.instances and instance_name in root_config.instances:
        instance = root_config.instances[instance_name]
        return instance if instance.enabled else None
    
    # V5.0 fallback: Try to construct from symbols section
    if root_config.symbols:
        # Parse instance name: SYMBOL_MODE
        parts = instance_name.rsplit('_', 1)
        if len(parts) == 2:
            symbol, mode = parts
            if symbol in root_config.symbols:
                symbol_config = root_config.symbols[symbol]
                # Only return if mode matches
                if symbol_config.mode.value == mode and symbol_config.enabled:
                    # Convert SymbolConfig to InstanceConfig (compatibility layer)
                    return _symbol_to_instance_config(symbol, symbol_config)
    
    return None


def get_all_instances(enabled_only: bool = True) -> Dict[str, InstanceConfig]:
    """Get all configured instances
    
    Args:
        enabled_only: If True, only return enabled instances
        
    Returns:
        Dict mapping instance names to InstanceConfig
        
    Example:
        for name, config in get_all_instances().items():
            print(f"{name}: {config.mode.value} mode, product_id={config.product_id}")
    """
    root_config = get_config()
    instances = {}
    
    # V6.0: Use instances section
    if root_config.instances:
        for name, config in root_config.instances.items():
            if not enabled_only or config.enabled:
                instances[name] = config
        return instances
    
    # V5.0 fallback: Convert symbols to instances
    if root_config.symbols:
        for symbol, config in root_config.symbols.items():
            if not enabled_only or config.enabled:
                instance_name = f"{symbol}_{config.mode.value}"
                instances[instance_name] = _symbol_to_instance_config(symbol, config)
    
    return instances


def get_instances_for_symbol(symbol: str, enabled_only: bool = True) -> Dict[str, InstanceConfig]:
    """Get all instances for a specific symbol
    
    V6.0 enables running LONG and SHORT on same symbol simultaneously.
    
    Args:
        symbol: Symbol name (e.g., "BTCUSD")
        enabled_only: If True, only return enabled instances
        
    Returns:
        Dict mapping instance names to InstanceConfig for the given symbol
        
    Example:
        btc_instances = get_instances_for_symbol("BTCUSD")
        # Could return: {"BTCUSD_LONG": ..., "BTCUSD_SHORT": ...}
    """
    all_instances = get_all_instances(enabled_only=enabled_only)
    return {
        name: config 
        for name, config in all_instances.items() 
        if config.symbol == symbol
    }


def parse_instance_name(instance_name: str) -> tuple:
    """Parse instance name into symbol and mode
    
    Args:
        instance_name: Instance name (e.g., "BTCUSD_LONG")
        
    Returns:
        Tuple of (symbol, mode) or (None, None) if invalid
        
    Example:
        symbol, mode = parse_instance_name("BTCUSD_LONG")
        # Returns: ("BTCUSD", "LONG")
    """
    parts = instance_name.rsplit('_', 1)
    if len(parts) == 2 and parts[1] in ['LONG', 'SHORT']:
        return parts[0], parts[1]
    return None, None


def make_instance_name(symbol: str, mode: str) -> str:
    """Create instance name from symbol and mode
    
    Args:
        symbol: Symbol name (e.g., "BTCUSD")
        mode: Trading mode ("LONG" or "SHORT")
        
    Returns:
        Instance name (e.g., "BTCUSD_LONG")
    """
    return f"{symbol}_{mode.upper()}"


def _symbol_to_instance_config(symbol: str, symbol_config) -> InstanceConfig:
    """Convert v5.0 SymbolConfig to v6.0 InstanceConfig (internal helper)
    
    This provides backward compatibility for v5.0 configs.
    """
    from config.models import (
        InstanceConfig, InstanceGridConfig, InstanceGridGeometry,
        InstanceGridLimits, InstanceGridBehavior, InstanceSmartGapFill,
        InstanceSafetyConfig, InstanceCapitalAllocation, InstanceRSIConfig
    )
    
    # Build grid config
    grid = InstanceGridConfig(
        geometry=InstanceGridGeometry(
            lower=symbol_config.grid.geometry.lower,
            upper=symbol_config.grid.geometry.upper,
            step=symbol_config.grid.geometry.step,
            reference=symbol_config.grid.geometry.reference
        ),
        limits=InstanceGridLimits(
            max_open_positions=symbol_config.grid.limits.max_open_positions,
            lot_size=symbol_config.grid.limits.lot_size,
            max_open_orders=symbol_config.grid.limits.max_open_orders,
            max_qty_per_order=symbol_config.grid.limits.max_qty_per_order
        ),
        behavior=InstanceGridBehavior(
            strict_grid=symbol_config.grid.behavior.strict_grid,
            rung_snap_mode=symbol_config.grid.behavior.rung_snap_mode,
            tick_size=symbol_config.grid.behavior.tick_size,
            dynamic_tick_size=getattr(symbol_config.grid.behavior, 'dynamic_tick_size', False),
            seed_initial_count=getattr(symbol_config.grid.behavior, 'seed_initial_count', 0)
        ),
        smart_gap_fill=InstanceSmartGapFill(
            enabled=symbol_config.grid.smart_gap_fill.enabled if symbol_config.grid.smart_gap_fill else False,
            order_type=symbol_config.grid.smart_gap_fill.order_type if symbol_config.grid.smart_gap_fill else 'maker',
            max_levels=symbol_config.grid.smart_gap_fill.max_levels if symbol_config.grid.smart_gap_fill else 0
        ) if symbol_config.grid.smart_gap_fill else None
    )
    
    # Build safety config with mode-appropriate RSI defaults
    rsi_config = (
        InstanceRSIConfig.for_long_mode() 
        if symbol_config.mode.value == 'LONG' 
        else InstanceRSIConfig.for_short_mode()
    )
    
    safety = InstanceSafetyConfig(
        max_account_loss_inr=symbol_config.safety.max_account_loss_inr,
        min_liquidation_distance_pct=symbol_config.safety.min_liquidation_distance_pct,
        rsi=rsi_config
    )
    
    # Build capital allocation
    capital = None
    if symbol_config.capital:
        capital = InstanceCapitalAllocation(
            allocated_usd=symbol_config.capital.allocated_usd,
            max_position_value_usd=symbol_config.capital.max_position_value_usd
        )
    
    return InstanceConfig(
        symbol=symbol,
        mode=symbol_config.mode,
        product_id=symbol_config.product_id,
        enabled=symbol_config.enabled,
        capital=capital,
        grid=grid,
        safety=safety
    )
