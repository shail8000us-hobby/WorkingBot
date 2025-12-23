"""
ENV to YAML converter.
Automatically converts grid_config.env to config.yaml format.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from config.env_mapping import (
    ENV_TO_YAML_MAPPING,
    set_nested_value,
    get_nested_value,
    infer_converter,
    convert_bool,
    convert_int,
    convert_float
)
from config.models import RootConfig


def env_to_dict(env_file: Optional[Path] = None) -> Dict[str, Any]:
    """Convert ENV file to nested dict structure
    
    Args:
        env_file: Path to ENV file (uses loaded env vars if None)
        
    Returns:
        Nested dict matching YAML structure
    """
    if env_file:
        load_dotenv(env_file)
    
    # Initialize with structure matching RootConfig
    yaml_dict = {
        'version': '2.0',
        'trading_mode': 'demo',
        'bot': {},
        'grid': {
            'geometry': {},
            'limits': {},
            'behavior': {},
            'smart_gap_fill': {}
        },
        'capital_protection': {
            'equity_floor': {},
            'drawdown_cap': {},
            'two_man_rule': {},
            'exposure_growth': {},
            'pending_budget': {}
        },
        'safety': {
            'flash_move': {},
            'spread_guard': {},
            'volatility': {},
            'circuit_breaker': {},
            'confirmation_guard': {}
        },
        'guardian': {},
        'liquidation_protection': {},
        'startup': {},
        'shutdown': {},
        'order_execution': {},
        'heartbeat': {},
        'health_check': {},
        'performance_logging': {},
        'api': {},
        'telegram': {},
        'logging': {},
        'webui': {},
        'risk_limits': {},
        'execution_safety': {},
        'strategies': [],
        'active_strategies': []
    }
    
    # Process all mapped ENV variables
    for env_key, yaml_path in ENV_TO_YAML_MAPPING.items():
        env_value = os.getenv(env_key)
        
        if env_value is None:
            continue
        
        # Convert value to appropriate type
        yaml_value = _convert_value(env_value, yaml_path)
        
        # Set in nested dict
        set_nested_value(yaml_dict, yaml_path, yaml_value)
    
    # Set defaults for required fields not in ENV
    _set_defaults(yaml_dict)
    
    return yaml_dict


def _convert_value(value: str, yaml_path: str) -> Any:
    """Convert string value to proper type based on field
    
    Args:
        value: String value from ENV
        yaml_path: YAML path (used to infer type)
        
    Returns:
        Converted value
    """
    # Special case mappings
    if yaml_path == 'trading_mode':
        return value.lower()  # demo or live
    
    # Telegram chat IDs should be strings
    if 'chat_id' in yaml_path:
        return str(value)
    
    # Token fields should be strings
    if 'token' in yaml_path or 'password' in yaml_path:
        return str(value)
    
    # Enum fields that might be mistaken for booleans
    if yaml_path in ['startup.cancel_scope', 'order_execution.post_only_mode', 'grid.behavior.rung_snap_mode']:
        return str(value).lower()
    
    # I_UNDERSTAND_LIVE must remain string
    if yaml_path == 'execution_safety.i_understand_live':
        return str(value).upper()
    
    # Boolean fields (but check for special cases first)
    if any(keyword in yaml_path.lower() for keyword in ['enabled', 'strict', 'forget', 'adopt', 'require', 'daily']):
        # Skip if it's actually an enum or int field
        if not any(x in yaml_path for x in ['scope', 'mode', 'amount', 'threshold']):
            return convert_bool(value)
    
    # Boolean fields explicit
    if 'cancel' in yaml_path.lower() and yaml_path != 'startup.cancel_scope':
        if value.lower() in ('true', 'false', '0', '1', 'yes', 'no'):
            return convert_bool(value)
    
    # Integer fields
    if any(keyword in yaml_path.lower() for keyword in ['_inr', 'interval', 'timeout', 'duration', 'delay', 'retries', 'window', 'port', 'count', 'levels', 'cooldown']):
        # Skip if it's a float field
        if not any(x in yaml_path for x in ['_pct', 'rate', 'multiplier', 'buffer', 'critical', 'distance']):
            try:
                return convert_int(value)
            except:
                pass
    
    # Threshold fields can be int or float depending on context
    if 'threshold' in yaml_path.lower():
        try:
            # Try int first
            val = float(value)
            if val == int(val) and val <= 100:
                return int(val)
            return val
        except:
            pass
    
    # Float fields
    if any(keyword in yaml_path.lower() for keyword in ['_pct', 'multiplier', 'rate', 'buffer', 'tick_size', 'fill_threshold', 'critical', 'distance']):
        try:
            return convert_float(value)
        except:
            pass
    
    # Default: use inferred converter
    converter = infer_converter(value)
    return converter(value)


def _set_defaults(yaml_dict: Dict[str, Any]) -> None:
    """Set default values for required fields not in ENV
    
    Args:
        yaml_dict: YAML dict to update with defaults
    """
    # Set defaults using RootConfig defaults
    defaults = {
        'shutdown.cancel_buy_orders': True,
        'shutdown.keep_tp_orders': True,
        'capital_protection.equity_floor.enabled': True,
        'telegram.enabled': True,
        'webui.enabled': True,
        'webui.auth_enabled': False,
    }
    
    for path, default_value in defaults.items():
        current = get_nested_value(yaml_dict, path)
        if current is None:
            set_nested_value(yaml_dict, path, default_value)


class EnvToYamlConverter:
    """Convert grid_config.env to config.yaml"""
    
    def __init__(self, env_file: Path):
        """Initialize converter
        
        Args:
            env_file: Path to grid_config.env
        """
        self.env_file = Path(env_file)
        
        if not self.env_file.exists():
            raise FileNotFoundError(f"ENV file not found: {env_file}")
        
        load_dotenv(self.env_file)
        
    def convert(self) -> Dict[str, Any]:
        """Convert ENV to YAML dict
        
        Returns:
            YAML-compatible dict
        """
        return env_to_dict(self.env_file)
    
    def save_yaml(self, output_file: Path):
        """Convert and save as YAML
        
        Args:
            output_file: Output YAML file path
        """
        import yaml
        
        yaml_dict = self.convert()
        
        # Validate by creating RootConfig
        try:
            config = RootConfig(**yaml_dict)
            config.validate_cross_field_constraints()
            print("✅ Configuration validated successfully")
        except Exception as e:
            print(f"⚠️  Validation warning: {e}")
            print("⚠️  Continuing anyway - manual review recommended")
        
        # Create parent directory
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Save as YAML
        with open(output_file, 'w') as f:
            yaml.dump(yaml_dict, f, default_flow_style=False, sort_keys=False, indent=2)
        
        print(f"✅ Converted {self.env_file} → {output_file}")
        
    def generate_comparison_report(self) -> str:
        """Generate before/after comparison report
        
        Returns:
            Formatted comparison report
        """
        yaml_dict = self.convert()
        
        report = []
        report.append("=" * 80)
        report.append("ENV → YAML CONVERSION REPORT")
        report.append("=" * 80)
        report.append(f"Source: {self.env_file}")
        report.append(f"Total ENV variables: {len(ENV_TO_YAML_MAPPING)}")
        report.append("=" * 80)
        
        # Group by section
        sections = {}
        for env_key, yaml_path in sorted(ENV_TO_YAML_MAPPING.items()):
            section = yaml_path.split('.')[0]
            if section not in sections:
                sections[section] = []
            sections[section].append((env_key, yaml_path))
        
        for section, mappings in sorted(sections.items()):
            report.append(f"\n[{section.upper()}]")
            report.append("-" * 80)
            
            for env_key, yaml_path in mappings:
                env_value = os.getenv(env_key)
                yaml_value = get_nested_value(yaml_dict, yaml_path)
                
                if env_value is not None:
                    report.append(f"\n{env_key}:")
                    report.append(f"  ENV:  {env_value!r}")
                    report.append(f"  YAML: {yaml_value!r} ({type(yaml_value).__name__})")
                    report.append(f"  Path: {yaml_path}")
        
        report.append("\n" + "=" * 80)
        report.append("SUMMARY")
        report.append("=" * 80)
        mapped_count = sum(1 for env_key in ENV_TO_YAML_MAPPING if os.getenv(env_key) is not None)
        report.append(f"Mapped variables: {mapped_count}/{len(ENV_TO_YAML_MAPPING)}")
        report.append("=" * 80)
        
        return "\n".join(report)


# CLI tool
if __name__ == '__main__':
    import sys
    
    # Get ENV file path from args or use default
    env_file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('grid_config.env')
    output_file = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('config.yaml')
    
    print(f"🔄 Converting {env_file} to {output_file}...")
    
    try:
        # Create converter
        converter = EnvToYamlConverter(env_file)
        
        # Generate YAML
        converter.save_yaml(output_file)
        
        # Generate comparison report
        report = converter.generate_comparison_report()
        report_file = output_file.parent / 'migration_report.txt'
        with open(report_file, 'w') as f:
            f.write(report)
        print(f"✅ Migration report saved: {report_file}")
        
        # Validate it loads correctly
        from config.loader import ConfigLoader
        loader = ConfigLoader(output_file)
        config = loader.load()
        print("✅ YAML config loads successfully")
        
        print("\n" + "=" * 80)
        print("✅ MIGRATION COMPLETE!")
        print("=" * 80)
        print(f"Next steps:")
        print(f"  1. Review {output_file}")
        print(f"  2. Review {report_file}")
        print(f"  3. Test with: python -c 'from config.loader import get_config; get_config()'")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
