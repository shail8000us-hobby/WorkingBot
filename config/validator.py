"""
YAML Configuration Validator
Validates config.yaml against schema and business logic rules
"""

import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import logging

log = logging.getLogger(__name__)


@dataclass
class ValidationError:
    """Represents a configuration validation error"""
    path: str
    message: str
    severity: str  # 'error', 'warning', 'info'
    line_number: Optional[int] = None
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of configuration validation"""
    valid: bool
    errors: List[ValidationError]
    warnings: List[ValidationError]
    info: List[ValidationError]
    
    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0
    
    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0
    
    def format_report(self) -> str:
        """Format validation results as a human-readable report"""
        lines = []
        lines.append("═" * 80)
        lines.append("CONFIGURATION VALIDATION REPORT")
        lines.append("═" * 80)
        
        if self.valid:
            lines.append("✅ Configuration is VALID")
        else:
            lines.append("❌ Configuration has ERRORS")
        
        if self.errors:
            lines.append(f"\n🚨 ERRORS ({len(self.errors)}):")
            for err in self.errors:
                lines.append(f"  ├─ {err.path}: {err.message}")
                if err.suggestion:
                    lines.append(f"  │  💡 {err.suggestion}")
        
        if self.warnings:
            lines.append(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warn in self.warnings:
                lines.append(f"  ├─ {warn.path}: {warn.message}")
                if warn.suggestion:
                    lines.append(f"  │  💡 {warn.suggestion}")
        
        if self.info:
            lines.append(f"\nℹ️  INFO ({len(self.info)}):")
            for inf in self.info:
                lines.append(f"  ├─ {inf.path}: {inf.message}")
        
        lines.append("═" * 80)
        return "\n".join(lines)


class ConfigValidator:
    """
    Validates YAML configuration against schema and business rules
    """
    
    def __init__(self, schema_path: Optional[Path] = None):
        """Initialize validator with schema"""
        if schema_path is None:
            schema_path = Path(__file__).parent / "schema.yaml"
        
        self.schema_path = schema_path
        self.schema = self._load_schema()
    
    def _load_schema(self) -> Dict:
        """Load schema YAML"""
        if not self.schema_path.exists():
            log.warning(f"Schema file not found: {self.schema_path}")
            return {}
        
        with open(self.schema_path, 'r') as f:
            return yaml.safe_load(f) or {}
    
    def validate(self, config: Dict[str, Any]) -> ValidationResult:
        """
        Validate configuration against schema and business rules
        
        Returns ValidationResult with all errors, warnings, and info
        """
        errors = []
        warnings = []
        info = []
        
        # 1. Check required fields
        errors.extend(self._validate_required_fields(config))
        
        # 2. Check data types
        errors.extend(self._validate_types(config))
        
        # 3. Check value ranges
        errors.extend(self._validate_ranges(config))
        
        # 4. Check business logic constraints
        errors.extend(self._validate_business_logic(config))
        
        # 5. Check for deprecated keys
        warnings.extend(self._check_deprecated_keys(config))
        
        # 6. Check for unknown keys
        warnings.extend(self._check_unknown_keys(config))
        
        # 7. Safety checks
        errors.extend(self._validate_safety_rules(config))
        
        # 8. Grid logic validation
        errors.extend(self._validate_grid_logic(config))
        
        # 9. API endpoint validation
        errors.extend(self._validate_api_endpoints(config))
        
        # 10. Mode consistency checks
        errors.extend(self._validate_mode_consistency(config))
        
        valid = len(errors) == 0
        
        return ValidationResult(
            valid=valid,
            errors=errors,
            warnings=warnings,
            info=info
        )
    
    def _validate_required_fields(self, config: Dict) -> List[ValidationError]:
        """Check that all required fields are present"""
        errors = []
        
        required_top_level = ['version', 'trading_mode', 'bot', 'grid', 'safety']
        for field in required_top_level:
            if field not in config:
                errors.append(ValidationError(
                    path=field,
                    message=f"Required field '{field}' is missing",
                    severity='error',
                    suggestion=f"Add '{field}:' to your config.yaml"
                ))
        
        # Check nested required fields
        if 'bot' in config:
            if 'symbol' not in config['bot']:
                errors.append(ValidationError(
                    path='bot.symbol',
                    message="Required field 'symbol' is missing from bot config",
                    severity='error',
                    suggestion="Add 'symbol: BTCUSD' under bot:"
                ))
        
        if 'grid' in config:
            if 'geometry' not in config['grid']:
                errors.append(ValidationError(
                    path='grid.geometry',
                    message="Required field 'geometry' is missing from grid config",
                    severity='error'
                ))
            if 'limits' not in config['grid']:
                errors.append(ValidationError(
                    path='grid.limits',
                    message="Required field 'limits' is missing from grid config",
                    severity='error'
                ))
        
        return errors
    
    def _validate_types(self, config: Dict) -> List[ValidationError]:
        """Validate that field types match schema"""
        errors = []
        
        # Check trading_mode
        if 'trading_mode' in config:
            if not isinstance(config['trading_mode'], str):
                errors.append(ValidationError(
                    path='trading_mode',
                    message=f"Expected string, got {type(config['trading_mode']).__name__}",
                    severity='error'
                ))
        
        # Check grid geometry types
        if 'grid' in config and 'geometry' in config['grid']:
            geo = config['grid']['geometry']
            for field in ['lower', 'upper', 'step', 'reference']:
                if field in geo and not isinstance(geo[field], (int, float)):
                    errors.append(ValidationError(
                        path=f'grid.geometry.{field}',
                        message=f"Expected number, got {type(geo[field]).__name__}",
                        severity='error'
                    ))
        
        return errors
    
    def _validate_ranges(self, config: Dict) -> List[ValidationError]:
        """Validate that numeric values are within allowed ranges"""
        errors = []
        
        # Grid step validation
        if 'grid' in config and 'geometry' in config['grid']:
            geo = config['grid']['geometry']
            if 'step' in geo:
                step = geo['step']
                if step <= 0:
                    errors.append(ValidationError(
                        path='grid.geometry.step',
                        message=f"Step must be > 0, got {step}",
                        severity='error'
                    ))
                if step > 10000:
                    errors.append(ValidationError(
                        path='grid.geometry.step',
                        message=f"Step seems very large ({step}), did you mean {step/10}?",
                        severity='warning'
                    ))
        
        # Margin thresholds
        if 'liquidation_protection' in config:
            lp = config['liquidation_protection']
            if 'margin_utilization_max' in lp:
                margin_max = lp['margin_utilization_max']
                if not (0 <= margin_max <= 100):
                    errors.append(ValidationError(
                        path='liquidation_protection.margin_utilization_max',
                        message=f"Margin utilization must be between 0-100%, got {margin_max}",
                        severity='error'
                    ))
        
        return errors
    
    def _validate_business_logic(self, config: Dict) -> List[ValidationError]:
        """Validate business logic constraints"""
        errors = []
        
        # Grid range validation
        if 'grid' in config and 'geometry' in config['grid']:
            geo = config['grid']['geometry']
            if 'lower' in geo and 'upper' in geo:
                if geo['upper'] <= geo['lower']:
                    errors.append(ValidationError(
                        path='grid.geometry',
                        message=f"Grid upper ({geo['upper']}) must be > lower ({geo['lower']})",
                        severity='error',
                        suggestion=f"Set upper to at least {geo['lower'] + 1000}"
                    ))
            
            if 'reference' in geo and 'lower' in geo and 'upper' in geo:
                ref = geo['reference']
                lower = geo['lower']
                upper = geo['upper']
                if not (lower <= ref <= upper):
                    errors.append(ValidationError(
                        path='grid.geometry.reference',
                        message=f"Reference price ({ref}) must be between lower ({lower}) and upper ({upper})",
                        severity='error',
                        suggestion=f"Set reference to a value between {lower} and {upper}"
                    ))
        
        # Max open orders vs max positions
        if 'grid' in config and 'limits' in config['grid']:
            limits = config['grid']['limits']
            if 'max_open_orders' in limits and 'max_open_positions' in limits:
                if limits['max_open_orders'] < limits['max_open_positions']:
                    errors.append(ValidationError(
                        path='grid.limits',
                        message=f"max_open_orders ({limits['max_open_orders']}) should be >= max_open_positions ({limits['max_open_positions']})",
                        severity='warning',
                        suggestion="Consider setting max_open_orders = max_open_positions * 2"
                    ))
        
        return errors
    
    def _check_deprecated_keys(self, config: Dict) -> List[ValidationError]:
        """Check for deprecated configuration keys"""
        warnings = []
        
        deprecated_keys = {
            'api.demo_public_url': 'Use api.demo.public_url instead',
            'api.demo_private_url': 'Use api.demo.private_url instead',
            'api.demo_ws_url': 'Use api.demo.websocket_url instead',
            'api.live_public_url': 'Use api.live.public_url instead',
            'api.live_private_url': 'Use api.live.private_url instead',
            'api.live_ws_url': 'Use api.live.websocket_url instead',
        }
        
        if 'api' in config:
            for old_key, suggestion in deprecated_keys.items():
                key = old_key.split('.')[1]
                if key in config['api']:
                    warnings.append(ValidationError(
                        path=f'api.{key}',
                        message=f"Deprecated key '{key}'",
                        severity='warning',
                        suggestion=suggestion
                    ))
        
        return warnings
    
    def _check_unknown_keys(self, config: Dict) -> List[ValidationError]:
        """Check for unknown configuration keys (might be typos)"""
        warnings = []
        
        # Define known top-level keys
        known_top_level = {
            'version', 'trading_mode', 'bot', 'trading', 'grid', 'capital', 
            'capital_protection', 'safety', 'risk_limits', 'guardian', 
            'liquidation_protection', 'startup', 'shutdown', 'order_execution',
            'heartbeat', 'monitoring', 'health_check', 'performance_logging',
            'logging', 'api', 'notifications', 'webui', 'reconciliation',
            'execution_safety', 'telegram', 'strategies', 'active_strategies'
        }
        
        for key in config.keys():
            if key not in known_top_level:
                warnings.append(ValidationError(
                    path=key,
                    message=f"Unknown top-level key '{key}' (might be a typo)",
                    severity='warning',
                    suggestion="Check spelling or remove if not needed"
                ))
        
        return warnings
    
    def _validate_safety_rules(self, config: Dict) -> List[ValidationError]:
        """Validate critical safety rules"""
        errors = []
        
        if 'safety' not in config:
            errors.append(ValidationError(
                path='safety',
                message="Safety configuration is missing - CRITICAL!",
                severity='error',
                suggestion="Add safety: section with execute_orders and i_understand_live"
            ))
            return errors
        
        safety = config['safety']
        
        # Check for live trading acknowledgment
        if config.get('trading_mode') == 'live':
            if safety.get('execute_orders') is True:
                if safety.get('i_understand_live') != 'YES':
                    errors.append(ValidationError(
                        path='safety.i_understand_live',
                        message="CRITICAL: Live trading requires i_understand_live: 'YES'",
                        severity='error',
                        suggestion="Set safety.i_understand_live: 'YES' to enable live trading"
                    ))
        
        # Warn if execute_orders is true in demo mode
        if config.get('trading_mode') == 'demo':
            if safety.get('execute_orders') is True:
                errors.append(ValidationError(
                    path='safety.execute_orders',
                    message="Warning: execute_orders is true in demo mode",
                    severity='info',
                    suggestion="This is OK for testing, but verify your settings"
                ))
        
        return errors
    
    def _validate_grid_logic(self, config: Dict) -> List[ValidationError]:
        """Validate grid trading logic and constraints"""
        errors = []
        
        if 'grid' not in config:
            return errors
        
        grid = config['grid']
        
        # Validate geometry
        if 'geometry' in grid:
            geo = grid['geometry']
            if all(k in geo for k in ['lower', 'upper', 'step']):
                lower = geo['lower']
                upper = geo['upper']
                step = geo['step']
                
                # Calculate number of grid levels
                range_size = upper - lower
                num_levels = range_size / step
                
                if num_levels < 2:
                    errors.append(ValidationError(
                        path='grid.geometry',
                        message=f"Grid has only {num_levels:.1f} levels - need at least 2",
                        severity='error',
                        suggestion=f"Reduce step size to {range_size / 10} or increase range"
                    ))
                
                if num_levels > 1000:
                    errors.append(ValidationError(
                        path='grid.geometry',
                        message=f"Grid has {num_levels:.0f} levels - this is excessive!",
                        severity='warning',
                        suggestion="Consider increasing step size or reducing range"
                    ))
        
        # Validate limits
        if 'limits' in grid:
            limits = grid['limits']
            if 'lot_size' in limits and 'max_qty_per_order' in limits:
                lot_size = limits['lot_size']
                max_qty = limits['max_qty_per_order']
                if lot_size > max_qty:
                    errors.append(ValidationError(
                        path='grid.limits',
                        message=f"lot_size ({lot_size}) > max_qty_per_order ({max_qty})",
                        severity='error',
                        suggestion=f"Set max_qty_per_order to at least {lot_size}"
                    ))
        
        return errors
    
    def _validate_api_endpoints(self, config: Dict) -> List[ValidationError]:
        """Validate Delta Exchange API endpoint URLs"""
        errors = []
        
        if 'api' not in config:
            errors.append(ValidationError(
                path='api',
                message="API configuration is missing",
                severity='error',
                suggestion="Add api: section with demo and live endpoints"
            ))
            return errors
        
        api = config['api']
        
        # Check for nested structure (preferred)
        for mode in ['demo', 'live']:
            if mode in api:
                mode_config = api[mode]
                for endpoint in ['public_url', 'private_url', 'websocket_url']:
                    if endpoint in mode_config:
                        url = mode_config[endpoint]
                        if not isinstance(url, str):
                            errors.append(ValidationError(
                                path=f'api.{mode}.{endpoint}',
                                message=f"URL must be a string, got {type(url).__name__}",
                                severity='error'
                            ))
                        elif not url.startswith(('http://', 'https://', 'wss://')):
                            errors.append(ValidationError(
                                path=f'api.{mode}.{endpoint}',
                                message=f"Invalid URL format: {url}",
                                severity='error',
                                suggestion="URL must start with http://, https://, or wss://"
                            ))
        
        # Validate websocket URLs specifically
        trading_mode = config.get('trading_mode', 'demo')
        if trading_mode in api:
            if 'websocket_url' in api[trading_mode]:
                ws_url = api[trading_mode]['websocket_url']
                if not ws_url.startswith('wss://'):
                    errors.append(ValidationError(
                        path=f'api.{trading_mode}.websocket_url',
                        message=f"WebSocket URL should start with wss://, got: {ws_url}",
                        severity='warning',
                        suggestion="Use wss:// for secure WebSocket connections"
                    ))
        
        return errors
    
    def _validate_mode_consistency(self, config: Dict) -> List[ValidationError]:
        """Validate consistency between trading_mode and other settings"""
        errors = []
        
        trading_mode = config.get('trading_mode')
        if not trading_mode:
            return errors
        
        # Check safety.trading_mode consistency
        if 'safety' in config:
            safety_mode = config['safety'].get('trading_mode')
            if safety_mode and safety_mode != trading_mode:
                errors.append(ValidationError(
                    path='safety.trading_mode',
                    message=f"Inconsistent: top-level trading_mode is '{trading_mode}' but safety.trading_mode is '{safety_mode}'",
                    severity='error',
                    suggestion=f"Set safety.trading_mode to '{trading_mode}' or remove it (uses top-level by default)"
                ))
        
        return errors


def validate_config_file(config_path: Path) -> ValidationResult:
    """
    Validate a configuration file
    
    Args:
        config_path: Path to config.yaml
    
    Returns:
        ValidationResult with all errors and warnings
    """
    if not config_path.exists():
        return ValidationResult(
            valid=False,
            errors=[ValidationError(
                path=str(config_path),
                message=f"Configuration file not found: {config_path}",
                severity='error'
            )],
            warnings=[],
            info=[]
        )
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return ValidationResult(
            valid=False,
            errors=[ValidationError(
                path=str(config_path),
                message=f"YAML parsing error: {e}",
                severity='error',
                line_number=getattr(e, 'problem_mark', None)
            )],
            warnings=[],
            info=[]
        )
    
    validator = ConfigValidator()
    return validator.validate(config)


if __name__ == '__main__':
    """Standalone validation tool"""
    import sys
    
    config_path = Path('config.yaml')
    if len(sys.argv) > 1:
        config_path = Path(sys.argv[1])
    
    print(f"Validating: {config_path}")
    result = validate_config_file(config_path)
    print(result.format_report())
    
    sys.exit(0 if result.valid else 1)
