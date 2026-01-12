"""
Option Validation Module for WorkingBot
=======================================
Comprehensive validation for option contracts, strategies, and orders.
Ensures data integrity and trading rule compliance BEFORE execution.

Imported from OptionBot project with adaptations.
Original: options_trading_bot/options/option_validator.py

Usage:
    from webui.backend.options_strategy.option_validator import OptionValidator, ValidationLevel
    
    validator = OptionValidator(level=ValidationLevel.STANDARD)
    
    # Validate before placing order
    result = validator.validate_order_parameters(order_params)
    if not result.is_valid:
        raise ValidationError(result.errors[0])
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """Validation strictness levels"""
    BASIC = "basic"        # Minimum checks (fast)
    STANDARD = "standard"  # Recommended for production
    STRICT = "strict"      # Maximum validation (slower)


@dataclass
class ValidationResult:
    """
    Result of validation check.
    
    Attributes:
        is_valid: True if all checks passed
        errors: List of critical errors (block execution)
        warnings: List of non-critical warnings (allow execution)
    """
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_error(self, message: str):
        """Add validation error (will set is_valid to False)"""
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str):
        """Add validation warning (does not affect is_valid)"""
        self.warnings.append(message)
    
    def merge(self, other: 'ValidationResult'):
        """Merge another validation result into this one"""
        if not other.is_valid:
            self.is_valid = False
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            'is_valid': self.is_valid,
            'errors': self.errors,
            'warnings': self.warnings,
            'error_count': len(self.errors),
            'warning_count': len(self.warnings)
        }


class OptionValidator:
    """
    Comprehensive option validation system.
    
    Validates:
    - Option contract parameters (symbol, strike, expiry)
    - Strategy structure (straddle, strangle, iron condor, etc.)
    - Order parameters (side, quantity, price)
    - Market data quality (bid-ask spread, volume)
    
    Example:
        validator = OptionValidator(ValidationLevel.STANDARD)
        
        # Validate strategy legs
        for leg in strategy.legs:
            result = validator.validate_leg(leg)
            if not result.is_valid:
                return error_response(result.errors)
        
        # Validate complete strategy
        result = validator.validate_strategy_structure(strategy_type, legs)
    """

    def __init__(self, validation_level: ValidationLevel = ValidationLevel.STANDARD):
        self.validation_level = validation_level

        # Validation thresholds (configurable)
        self.min_days_to_expiry = 0       # 0 = allow same-day expiry
        self.max_days_to_expiry = 365     # 1 year max
        self.min_strike_price = 0.01
        self.max_strike_price = 10_000_000  # Increased for BTC options
        self.min_option_price = 0.0       # Allow zero for OTM options
        self.max_option_price = 1_000_000
        self.max_bid_ask_spread_pct = 50  # 50% of mid price
        self.min_volume_threshold = 0     # Relaxed for illiquid options
        self.min_open_interest_threshold = 0

        logger.info(f"OptionValidator initialized with {validation_level.value} level")

    # =========================================================================
    # Public Validation APIs
    # =========================================================================
    
    def validate_option_symbol(self, symbol: str) -> ValidationResult:
        """
        Validate option symbol format.
        
        Expected formats:
        - Delta Exchange: C-BTC-95000-310126 or P-ETH-3500-280226
        - Format: {C|P}-{UNDERLYING}-{STRIKE}-{DDMMYY}
        
        Args:
            symbol: Option symbol to validate
            
        Returns:
            ValidationResult with errors/warnings
        """
        result = ValidationResult()
        
        if not symbol or not isinstance(symbol, str):
            result.add_error("Symbol must be a non-empty string")
            return result
        
        if len(symbol) < 10:
            result.add_error(f"Symbol too short: {symbol}")
            return result
        
        if len(symbol) > 50:
            result.add_error(f"Symbol too long: {symbol}")
            return result
        
        # Parse Delta Exchange format
        parts = symbol.split('-')
        if len(parts) < 4:
            result.add_error(f"Invalid symbol format: {symbol}. Expected: C-BTC-95000-310126")
            return result
        
        option_type = parts[0].upper()
        if option_type not in ['C', 'P']:
            result.add_error(f"Invalid option type in symbol: {option_type}. Must be C or P")
        
        underlying = parts[1].upper()
        if underlying not in ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE']:
            result.add_warning(f"Unusual underlying asset: {underlying}")
        
        try:
            strike = float(parts[2])
            if strike <= 0:
                result.add_error(f"Invalid strike price: {strike}")
        except ValueError:
            result.add_error(f"Cannot parse strike price from symbol: {parts[2]}")
        
        # Validate expiry format (DDMMYY)
        expiry_str = parts[3]
        if len(expiry_str) != 6:
            result.add_error(f"Invalid expiry format in symbol: {expiry_str}. Expected DDMMYY")
        else:
            try:
                day = int(expiry_str[:2])
                month = int(expiry_str[2:4])
                year = int(expiry_str[4:6]) + 2000
                expiry_date = datetime(year, month, day)
                
                if expiry_date.date() < datetime.now().date():
                    result.add_error(f"Option has already expired: {expiry_date.date()}")
            except ValueError as e:
                result.add_error(f"Cannot parse expiry date: {expiry_str} - {e}")
        
        return result

    def validate_strike_price(self, strike: float, underlying: str = None, spot_price: float = None) -> ValidationResult:
        """
        Validate strike price.
        
        Args:
            strike: Strike price to validate
            underlying: Optional underlying asset for context
            spot_price: Optional spot price for distance check
            
        Returns:
            ValidationResult with errors/warnings
        """
        result = ValidationResult()
        
        if not isinstance(strike, (int, float)):
            result.add_error("Strike price must be a number")
            return result
        
        if strike < self.min_strike_price:
            result.add_error(f"Strike price too low: {strike} (minimum: {self.min_strike_price})")
        
        if strike > self.max_strike_price:
            result.add_error(f"Strike price too high: {strike} (maximum: {self.max_strike_price})")
        
        # Check distance from spot if provided
        if spot_price and spot_price > 0:
            distance_pct = abs(strike - spot_price) / spot_price * 100
            if distance_pct > 100:
                result.add_warning(f"Strike is {distance_pct:.1f}% away from spot price")
        
        return result

    def validate_expiry_date(self, expiry: datetime) -> ValidationResult:
        """
        Validate expiry date.
        
        Args:
            expiry: Expiry datetime to validate
            
        Returns:
            ValidationResult with errors/warnings
        """
        result = ValidationResult()
        
        if not isinstance(expiry, datetime):
            result.add_error("Expiry must be a datetime object")
            return result
        
        now = datetime.now(timezone.utc) if expiry.tzinfo else datetime.now()
        
        if expiry <= now:
            result.add_error("Option has already expired")
            return result
        
        days_to_expiry = (expiry - now).days
        
        if days_to_expiry < self.min_days_to_expiry:
            result.add_warning(f"Option expires very soon ({days_to_expiry} days)")
        
        if days_to_expiry > self.max_days_to_expiry:
            result.add_warning(f"Option expires very far out ({days_to_expiry} days)")
        
        return result

    def validate_option_type(self, option_type: str) -> ValidationResult:
        """
        Validate option type (call/put).
        
        Args:
            option_type: Option type string
            
        Returns:
            ValidationResult with errors/warnings
        """
        result = ValidationResult()
        
        if not option_type:
            result.add_error("Option type is required")
            return result
        
        normalized = str(option_type).lower()
        valid_types = ['call', 'put', 'c', 'p']
        
        if normalized not in valid_types:
            result.add_error(f"Invalid option type: {option_type}. Must be one of: {valid_types}")
        
        return result

    def validate_order_parameters(self, order_params: Dict[str, Any]) -> ValidationResult:
        """
        Validate order parameters before submission.
        
        Args:
            order_params: Dictionary with order parameters:
                - symbol: Option symbol
                - side: 'buy' or 'sell'
                - size/quantity: Position size
                - order_type: 'market_order' or 'limit_order'
                - limit_price: Required for limit orders
                
        Returns:
            ValidationResult with errors/warnings
        """
        result = ValidationResult()

        # Required fields
        required_fields = ['symbol', 'side', 'order_type']
        for field in required_fields:
            if field not in order_params:
                result.add_error(f"Missing required field: {field}")

        # Validate symbol
        if 'symbol' in order_params:
            symbol_result = self.validate_option_symbol(order_params['symbol'])
            result.merge(symbol_result)

        # Validate quantity/size
        quantity = order_params.get('size') or order_params.get('quantity')
        if quantity is None:
            result.add_error("Missing required field: size or quantity")
        elif not isinstance(quantity, (int, float)) or quantity <= 0:
            result.add_error("Quantity must be a positive number")
        elif isinstance(quantity, float) and quantity != int(quantity):
            # Delta Exchange doesn't support fractional quantities for options
            result.add_error("Fractional quantities are not supported for options")

        # Validate side
        if 'side' in order_params:
            side = str(order_params['side']).lower()
            if side not in ['buy', 'sell']:
                result.add_error("Side must be 'buy' or 'sell'")

        # Validate order type
        if 'order_type' in order_params:
            order_type = str(order_params['order_type']).lower()
            valid_types = ['market_order', 'limit_order', 'stop_order', 'stop_limit_order']
            if order_type not in valid_types:
                result.add_error(f"Invalid order type. Must be one of: {valid_types}")

            # Validate limit price for limit orders
            if order_type in ['limit_order', 'stop_limit_order']:
                if 'limit_price' not in order_params:
                    result.add_error("Limit price required for limit orders")
                elif order_params['limit_price'] <= 0:
                    result.add_error("Limit price must be positive")

            # Validate stop price for stop orders
            if order_type in ['stop_order', 'stop_limit_order']:
                if 'stop_price' not in order_params:
                    result.add_error("Stop price required for stop orders")
                elif order_params['stop_price'] <= 0:
                    result.add_error("Stop price must be positive")

        return result

    def validate_strategy_legs(self, legs: List[Dict[str, Any]]) -> ValidationResult:
        """
        Validate individual strategy legs.
        
        Args:
            legs: List of leg dictionaries with symbol, side, size, etc.
            
        Returns:
            ValidationResult with errors/warnings
        """
        result = ValidationResult()
        
        if not legs:
            result.add_error("Strategy must have at least one leg")
            return result
        
        if len(legs) > 6:
            result.add_error("Maximum 6 legs allowed per strategy")
        
        for i, leg in enumerate(legs):
            leg_result = self.validate_order_parameters(leg)
            
            # Prefix errors/warnings with leg number
            for error in leg_result.errors:
                result.add_error(f"Leg {i+1}: {error}")
            for warning in leg_result.warnings:
                result.add_warning(f"Leg {i+1}: {warning}")
        
        return result

    def validate_strategy_structure(self, strategy_type: str, legs: List[Dict[str, Any]]) -> ValidationResult:
        """
        Validate strategy structure based on type.
        
        Args:
            strategy_type: Type of strategy (straddle, strangle, iron_condor, etc.)
            legs: List of strategy legs
            
        Returns:
            ValidationResult with errors/warnings
        """
        result = ValidationResult()
        
        strategy_type_lower = strategy_type.lower().replace(' ', '_').replace('-', '_')
        
        if strategy_type_lower in ['straddle', 'long_straddle', 'short_straddle']:
            result.merge(self._validate_straddle_structure(legs))
        elif strategy_type_lower in ['strangle', 'long_strangle', 'short_strangle']:
            result.merge(self._validate_strangle_structure(legs))
        elif strategy_type_lower in ['iron_condor']:
            result.merge(self._validate_iron_condor_structure(legs))
        elif strategy_type_lower in ['butterfly', 'long_butterfly', 'short_butterfly']:
            result.merge(self._validate_butterfly_structure(legs))
        elif strategy_type_lower in ['vertical_spread', 'call_spread', 'put_spread']:
            result.merge(self._validate_spread_structure(legs))
        else:
            # Generic validation for unknown strategy types
            result.add_warning(f"Unknown strategy type: {strategy_type}. Using generic validation.")
            result.merge(self.validate_strategy_legs(legs))
        
        # Check expiry alignment (all legs should have same expiry for most strategies)
        result.merge(self._validate_expiry_alignment(strategy_type_lower, legs))
        
        # Check underlying consistency
        result.merge(self._validate_underlying_consistency(legs))
        
        return result

    def validate_bid_ask_spread(self, bid: float, ask: float) -> ValidationResult:
        """
        Validate bid-ask spread for liquidity assessment.
        
        Args:
            bid: Bid price
            ask: Ask price
            
        Returns:
            ValidationResult with errors/warnings
        """
        result = ValidationResult()
        
        if bid is None or ask is None:
            return result  # No spread info available
        
        if bid < 0 or ask < 0:
            result.add_error("Bid and ask cannot be negative")
            return result
        
        if bid > ask:
            result.add_error("Bid cannot be higher than ask (crossed market)")
            return result
        
        # Check spread width
        mid_price = (bid + ask) / 2 if (bid > 0 and ask > 0) else max(bid, ask)
        if mid_price > 0:
            spread_pct = ((ask - bid) / mid_price) * 100
            if spread_pct > self.max_bid_ask_spread_pct:
                result.add_warning(f"Wide bid-ask spread ({spread_pct:.1f}%) indicates poor liquidity")
        
        return result

    # =========================================================================
    # Private Validation Helpers
    # =========================================================================
    
    def _validate_straddle_structure(self, legs: List[Dict]) -> ValidationResult:
        """Validate straddle: 1 call + 1 put, same strike, same expiry"""
        result = ValidationResult()
        
        if len(legs) != 2:
            result.add_error(f"Straddle must have exactly 2 legs, got {len(legs)}")
            return result
        
        # Parse leg info
        call_legs = [l for l in legs if self._is_call(l)]
        put_legs = [l for l in legs if self._is_put(l)]
        
        if len(call_legs) != 1 or len(put_legs) != 1:
            result.add_error("Straddle must have exactly one call and one put")
            return result
        
        call_strike = self._get_strike(call_legs[0])
        put_strike = self._get_strike(put_legs[0])
        
        if call_strike != put_strike:
            result.add_error(f"Straddle legs must have same strike. Call: {call_strike}, Put: {put_strike}")
        
        # Check same direction (both buy or both sell)
        call_side = call_legs[0].get('side', '').lower()
        put_side = put_legs[0].get('side', '').lower()
        
        if call_side != put_side:
            result.add_warning(f"Straddle legs have different sides. Call: {call_side}, Put: {put_side}")
        
        return result

    def _validate_strangle_structure(self, legs: List[Dict]) -> ValidationResult:
        """Validate strangle: 1 call + 1 put, different strikes"""
        result = ValidationResult()
        
        if len(legs) != 2:
            result.add_error(f"Strangle must have exactly 2 legs, got {len(legs)}")
            return result
        
        call_legs = [l for l in legs if self._is_call(l)]
        put_legs = [l for l in legs if self._is_put(l)]
        
        if len(call_legs) != 1 or len(put_legs) != 1:
            result.add_error("Strangle must have exactly one call and one put")
            return result
        
        call_strike = self._get_strike(call_legs[0])
        put_strike = self._get_strike(put_legs[0])
        
        if call_strike == put_strike:
            result.add_warning("Strangle with same strikes is actually a straddle")
        
        # Typical strangle: put strike < call strike
        if put_strike > call_strike:
            result.add_warning(f"Unusual strangle: put strike ({put_strike}) > call strike ({call_strike})")
        
        return result

    def _validate_iron_condor_structure(self, legs: List[Dict]) -> ValidationResult:
        """Validate iron condor: 4 legs (2 calls + 2 puts)"""
        result = ValidationResult()
        
        if len(legs) != 4:
            result.add_error(f"Iron condor must have exactly 4 legs, got {len(legs)}")
            return result
        
        call_legs = [l for l in legs if self._is_call(l)]
        put_legs = [l for l in legs if self._is_put(l)]
        
        if len(call_legs) != 2 or len(put_legs) != 2:
            result.add_error("Iron condor must have exactly 2 calls and 2 puts")
        
        return result

    def _validate_butterfly_structure(self, legs: List[Dict]) -> ValidationResult:
        """Validate butterfly: 3 legs"""
        result = ValidationResult()
        
        if len(legs) != 3:
            result.add_error(f"Butterfly must have exactly 3 legs, got {len(legs)}")
        
        return result

    def _validate_spread_structure(self, legs: List[Dict]) -> ValidationResult:
        """Validate vertical spread: 2 legs of same type"""
        result = ValidationResult()
        
        if len(legs) != 2:
            result.add_error(f"Spread must have exactly 2 legs, got {len(legs)}")
            return result
        
        # Both should be same type (both calls or both puts)
        types = [self._get_option_type(l) for l in legs]
        if types[0] != types[1]:
            result.add_warning("Spread legs have different option types")
        
        return result

    def _validate_expiry_alignment(self, strategy_type: str, legs: List[Dict]) -> ValidationResult:
        """Check that legs have appropriate expiry alignment"""
        result = ValidationResult()
        
        expiries = [self._get_expiry(l) for l in legs]
        expiries = [e for e in expiries if e]  # Filter None
        
        if not expiries:
            return result
        
        unique_expiries = set(expiries)
        
        if len(unique_expiries) > 1:
            # Calendar spreads have different expiries by design
            if 'calendar' not in strategy_type and 'diagonal' not in strategy_type:
                result.add_warning(f"Strategy has {len(unique_expiries)} different expiry dates")
        
        return result

    def _validate_underlying_consistency(self, legs: List[Dict]) -> ValidationResult:
        """Check that all legs have same underlying asset"""
        result = ValidationResult()
        
        underlyings = [self._get_underlying(l) for l in legs]
        underlyings = [u for u in underlyings if u]  # Filter None
        
        if not underlyings:
            return result
        
        unique_underlyings = set(underlyings)
        
        if len(unique_underlyings) > 1:
            result.add_error(f"Strategy legs must have same underlying asset. Found: {unique_underlyings}")
        
        return result

    # =========================================================================
    # Symbol Parsing Helpers
    # =========================================================================
    
    def _is_call(self, leg: Dict) -> bool:
        """Check if leg is a call option"""
        symbol = leg.get('symbol', '')
        return symbol.startswith('C-') or symbol.startswith('C_')
    
    def _is_put(self, leg: Dict) -> bool:
        """Check if leg is a put option"""
        symbol = leg.get('symbol', '')
        return symbol.startswith('P-') or symbol.startswith('P_')
    
    def _get_option_type(self, leg: Dict) -> str:
        """Get option type from leg"""
        if self._is_call(leg):
            return 'call'
        if self._is_put(leg):
            return 'put'
        return 'unknown'
    
    def _get_strike(self, leg: Dict) -> Optional[float]:
        """Extract strike price from leg symbol"""
        symbol = leg.get('symbol', '')
        parts = symbol.split('-')
        if len(parts) >= 3:
            try:
                return float(parts[2])
            except ValueError:
                return None
        return None
    
    def _get_expiry(self, leg: Dict) -> Optional[str]:
        """Extract expiry from leg symbol"""
        symbol = leg.get('symbol', '')
        parts = symbol.split('-')
        if len(parts) >= 4:
            return parts[3]
        return None
    
    def _get_underlying(self, leg: Dict) -> Optional[str]:
        """Extract underlying asset from leg symbol"""
        symbol = leg.get('symbol', '')
        parts = symbol.split('-')
        if len(parts) >= 2:
            return parts[1].upper()
        return None
