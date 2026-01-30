"""
Unified Loss Limits Validation

Ensures that Guardian and Trader loss limits are consistent and safe.
Catches configuration errors before they cause financial losses.

The Rule:
- Guardian limit should be ≤ Trader limit
- Guardian is the last line of defense and should trigger first
- Recommend 5-10% buffer between limits

Why This Matters:
- Trader limit: 10,000 INR
- Guardian limit: 15,000 INR (WRONG!)
- Result: You lose an extra 5,000 INR unnecessarily

With validation:
- Bot refuses to start with bad config
- Forces you to fix before trading
- Saves you from expensive mistakes
"""

import os
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path for config imports
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.loader import get_config

log = logging.getLogger("loss_limits")


class LossLimitsValidator:
    """Validates loss limit configuration"""
    
    def __init__(self):
        self.trader_limit: Optional[float] = None
        self.guardian_limit: Optional[float] = None
        self.validated = False
    
    def load_limits(self) -> Dict[str, float]:
        """Load limits from YAML config"""
        cfg = get_config()
        
        # V6.0 multi-instance: Get SYMBOL from env or default to BTCUSD
        symbol = os.environ.get('SYMBOL', 'BTCUSD')
        mode = os.environ.get('MODE', 'LONG')
        instance_key = f"{symbol}_{mode}"
        
        try:
            # Try v6.0 per-instance config first
            if cfg is None or not hasattr(cfg, 'instances') or cfg.instances is None:
                raise AttributeError("No instances config")
            instance = cfg.instances[instance_key]
            self.trader_limit = instance.safety.max_account_loss_inr
            
            # Guardian config (global for now)
            if hasattr(cfg, 'safety') and hasattr(cfg.safety, 'guardian'):
                self.guardian_limit = cfg.safety.guardian.max_account_loss_inr
            else:
                # Default: Guardian limit = 90% of trader limit
                self.guardian_limit = self.trader_limit * 0.9
                
        except (AttributeError, KeyError, TypeError):
            # Fallback: Use safe defaults
            log.warning(f"Could not load limits for {instance_key}, using defaults")
            self.trader_limit = 10000  # Default 10k INR
            self.guardian_limit = 9000  # 90% of trader
        
        return {
            'trader': self.trader_limit,
            'guardian': self.guardian_limit
        }
    
    def validate(self, strict: bool = True) -> bool:
        """
        Validate loss limits configuration.
        
        Args:
            strict: If True, raise ValueError on errors. If False, only warn.
        
        Returns:
            bool: True if valid, False otherwise
        
        Raises:
            ValueError: If strict=True and validation fails
        """
        limits = self.load_limits()
        
        log.info("=" * 70)
        log.info("💰 LOSS LIMITS VALIDATION")
        log.info("=" * 70)
        log.info(f"Trader limit:   ₹{self.trader_limit:,.2f}")
        log.info(f"Guardian limit: ₹{self.guardian_limit:,.2f}")
        log.info("")
        
        errors = []
        warnings = []
        
        # Check 1: Guardian limit too high (CRITICAL ERROR)
        if self.guardian_limit > self.trader_limit and self.trader_limit > 0:
            error_msg = (
                f"Guardian limit (₹{self.guardian_limit:,.2f}) is HIGHER than "
                f"Trader limit (₹{self.trader_limit:,.2f})"
            )
            errors.append(error_msg)
            
            log.error("🚨 CONFIGURATION ERROR DETECTED!")
            log.error("")
            log.error(error_msg)
            log.error("")
            log.error("This means:")
            log.error(f"  • Trader will stop trading at ₹{self.trader_limit:,.2f} loss")
            log.error(f"  • Guardian won't act until ₹{self.guardian_limit:,.2f} loss")
            log.error(f"  • You'll lose an extra ₹{self.guardian_limit - self.trader_limit:,.2f}!")
            log.error("")
            log.error("Recommended fix:")
            recommended = self.trader_limit * 0.95
            log.error(f"  GUARDIAN_MAX_ACCOUNT_LOSS_INR={recommended:.2f}")
            log.error("  (95% of trader limit for safety margin)")
            log.error("")
        
        # Check 2: Guardian limit is 0 (WARNING)
        if self.guardian_limit == 0:
            warning_msg = "Guardian limit is 0 - no loss protection!"
            warnings.append(warning_msg)
            
            log.warning("⚠️  WARNING: Guardian limit is 0!")
            log.warning("   Guardian will NOT protect against losses")
            log.warning("   Recommend setting GUARDIAN_MAX_ACCOUNT_LOSS_INR")
            log.warning("")
        
        # Check 3: Trader limit is 0 (WARNING)
        if self.trader_limit == 0:
            warning_msg = "Trader limit is 0 - no loss protection!"
            warnings.append(warning_msg)
            
            log.warning("⚠️  WARNING: Trader limit is 0!")
            log.warning("   Trader will NOT stop on losses")
            log.warning("   Recommend setting MAX_ACCOUNT_LOSS_INR")
            log.warning("")
        
        # Check 4: Limits are too close (WARNING)
        if self.trader_limit > 0 and self.guardian_limit > 0:
            buffer = self.trader_limit - self.guardian_limit
            buffer_pct = (buffer / self.trader_limit) * 100
            
            if buffer < (self.trader_limit * 0.05):  # Less than 5% buffer
                warning_msg = f"Limits are very close (buffer: ₹{buffer:,.2f}, {buffer_pct:.1f}%)"
                warnings.append(warning_msg)
                
                log.warning("⚠️  WARNING: Limits are very close!")
                log.warning(f"   Buffer: ₹{buffer:,.2f} ({buffer_pct:.1f}%)")
                log.warning("   Recommend at least 5% buffer")
                recommended = self.trader_limit * 0.95
                log.warning(f"   Suggested: GUARDIAN_MAX_ACCOUNT_LOSS_INR={recommended:.2f}")
                log.warning("")
            else:
                log.info(f"✅ Good buffer: ₹{buffer:,.2f} ({buffer_pct:.1f}%)")
                log.info("")
        
        # Check 5: Both limits are set and Guardian < Trader (GOOD!)
        if (self.trader_limit > 0 and self.guardian_limit > 0 and 
            self.guardian_limit <= self.trader_limit):
            log.info("✅ Configuration is VALID")
            log.info("   Guardian will act before Trader stops")
            log.info("   This is the correct setup!")
            log.info("")
        
        # Summary
        if errors:
            log.error("=" * 70)
            log.error(f"❌ VALIDATION FAILED: {len(errors)} error(s)")
            for i, err in enumerate(errors, 1):
                log.error(f"   {i}. {err}")
            log.error("=" * 70)
            
            if strict:
                raise ValueError(
                    f"Loss limits validation failed: {'; '.join(errors)}"
                )
            return False
        
        if warnings:
            log.warning("=" * 70)
            log.warning(f"⚠️  {len(warnings)} warning(s) - review recommended")
            for i, warn in enumerate(warnings, 1):
                log.warning(f"   {i}. {warn}")
            log.warning("=" * 70)
        else:
            log.info("=" * 70)
            log.info("✅ VALIDATION PASSED - No issues found")
            log.info("=" * 70)
        
        self.validated = True
        return True
    
    def get_config(self) -> Dict[str, Any]:
        """Get current loss limits configuration"""
        if not self.validated:
            self.load_limits()
        
        buffer = 0.0
        buffer_pct = 0.0
        
        if self.trader_limit > 0 and self.guardian_limit > 0:
            buffer = self.trader_limit - self.guardian_limit
            buffer_pct = (buffer / self.trader_limit) * 100
        
        return {
            'trader_limit_inr': self.trader_limit,
            'guardian_limit_inr': self.guardian_limit,
            'buffer_inr': buffer,
            'buffer_percent': buffer_pct,
            'is_valid': self.guardian_limit <= self.trader_limit if self.trader_limit > 0 else True,
            'validated': self.validated
        }


# Global validator instance
_validator = LossLimitsValidator()


def validate_loss_limits(strict: bool = True) -> bool:
    """
    Validate loss limits configuration.
    
    Call this on bot startup to catch configuration errors early.
    
    Args:
        strict: If True, raise ValueError on errors. If False, only warn.
    
    Returns:
        bool: True if valid, False otherwise
    
    Raises:
        ValueError: If strict=True and validation fails
    
    Example:
        # In bot startup code:
        from bot.safety.loss_limits import validate_loss_limits
        
        try:
            validate_loss_limits(strict=True)
        except ValueError as e:
            log.error(f"Configuration error: {e}")
            sys.exit(1)
    """
    return _validator.validate(strict=strict)


def get_loss_limits_config() -> Dict[str, Any]:
    """
    Get current loss limits configuration.
    
    Returns:
        dict: Loss limits config with validation status
    """
    return _validator.get_config()

