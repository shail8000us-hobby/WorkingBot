"""
Safety Gatekeeper - Single Checkpoint for All Order Placement

This module provides a single, authoritative function that ALL order-placing
code must call before executing any trade. It checks multiple safety conditions
and returns True only if ALL conditions are met.

Benefits:
- Single source of truth for trading permission
- Impossible to bypass accidentally
- Easy to maintain and audit
- Prevents trading during emergencies
- Includes volatility-based safety checks

Usage:
    from bot.safety.gatekeeper import can_place_orders
    
    if not can_place_orders():
        log.warning("Order blocked by safety gatekeeper")
        return None
    
    # Safe to place order
    order = exchange.create_order(...)
"""

import os
import logging
import sys
import time
import traceback
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

log = logging.getLogger("gatekeeper")

# Add project root to path for config imports
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# YAML Config Integration
try:
    from config.loader import get_config
    YAML_CONFIG_AVAILABLE = True
except Exception:
    YAML_CONFIG_AVAILABLE = False
    def get_config(): return None

def _load_config():
    """Load configuration from config.yaml"""
    # Config is loaded via get_config() - no need to load dotenv
    pass

# Volatility Safety - DEPRECATED (Guardian monitors this now)
# Kept for backward compatibility only
try:
    from bot.volatility.iv_rv_tracker import get_volatility_tracker
    VOLATILITY_SAFETY_AVAILABLE = False  # Disabled - Guardian handles this
except Exception:
    VOLATILITY_SAFETY_AVAILABLE = False
    def get_volatility_tracker(): return None

# Order Confirmation Guard Integration
try:
    from bot.safety.order_confirmation_guard import get_confirmation_guard
    CONFIRMATION_GUARD_AVAILABLE = True
except Exception:
    CONFIRMATION_GUARD_AVAILABLE = False
    def get_confirmation_guard(): return None

# Liquidation/Margin Protection - DEPRECATED (Guardian monitors this now)
# Kept for backward compatibility only
try:
    from bot.liquidation.integrated_monitor import IntegratedLiquidationMonitor
    LIQUIDATION_PROTECTION_AVAILABLE = False  # Disabled - Guardian handles this
except Exception:
    LIQUIDATION_PROTECTION_AVAILABLE = False
    MarginUtilizationMonitor = None


class SafetyGatekeeper:
    """
    Safety gatekeeper that checks all safety conditions before allowing trades.
    
    This is a singleton - only one instance should exist per bot process.
    """
    
    _instance: Optional['SafetyGatekeeper'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, exchange_ops=None):
        """Initialize gatekeeper (only once)"""
        if self._initialized:
            return
        
        self._initialized = True
        self._check_count = 0
        self._block_count = 0
        self._last_block_reason = None
        self.exchange_ops = exchange_ops
        self.margin_monitor = None
        
        log.info("=" * 70)
        log.info("🛡️  SAFETY GATEKEEPER INITIALIZED")
        log.info("=" * 70)
        log.info("All order placement must pass through gatekeeper")
        log.info("Checking: Emergency flag, EXECUTE_ORDERS, I_UNDERSTAND_LIVE, Mode, Margin Utilization")
        log.info("=" * 70)
    
    def can_place_orders(self, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Check if orders can be placed right now.
        
        Returns True only if ALL safety conditions are met:
        1. No emergency flag exists
        2. EXECUTE_ORDERS is enabled
        3. I_UNDERSTAND_LIVE is set (for live mode)
        4. Trading mode is valid
        5. No other safety blocks
        
        Args:
            context: Optional context dict for logging (e.g., {'origin': 'smart_gap_fill'})
        
        Returns:
            bool: True if safe to place orders, False otherwise
        """
        self._check_count += 1
        context = context or {}
        origin = context.get('origin', 'unknown')
        
        # Check 1: Emergency flag
        emergency_flag = Path('.guardian_emergency_stop')
        if emergency_flag.exists():
            self._block_count += 1
            self._last_block_reason = "emergency_flag"
            
            log.error("=" * 70)
            log.error("🚨 SAFETY GATEKEEPER: ORDER BLOCKED")
            log.error("=" * 70)
            log.error("Reason: EMERGENCY FLAG EXISTS")
            log.error(f"Flag location: {emergency_flag.absolute()}")
            log.error(f"Origin: {origin}")
            log.error("")
            log.error("ALL TRADING IS BLOCKED")
            log.error("")
            log.error("To resume trading:")
            log.error("  1. Investigate why emergency flag was created")
            log.error("  2. Fix the underlying issue")
            log.error(f"  3. Remove flag: rm {emergency_flag}")
            log.error("  4. Restart bot")
            log.error("=" * 70)
            return False
        
        # Check 2: EXECUTE_ORDERS flag
        cfg = get_config()
        execute_orders_enabled = cfg.safety.execute_orders
        
        if not execute_orders_enabled:
            self._block_count += 1
            self._last_block_reason = "execute_orders_disabled"
            
            log.warning("=" * 70)
            log.warning("⚠️  SAFETY GATEKEEPER: ORDER BLOCKED")
            log.warning("=" * 70)
            log.warning("Reason: EXECUTE_ORDERS not enabled")
            log.warning(f"Current value: {execute_orders_enabled}")
            log.warning(f"Origin: {origin}")
            log.warning("")
            log.warning("Bot is in DRY-RUN mode (no real orders)")
            log.warning("")
            log.warning("To enable real trading:")
            log.warning("  Set safety.execute_orders: true in config.yaml")
            log.warning("=" * 70)
            return False
        
        # Check 3: Trading mode validation
        trading_mode = cfg.safety.trading_mode.lower()
        if trading_mode not in ('demo', 'live'):
            self._block_count += 1
            self._last_block_reason = "invalid_trading_mode"
            
            log.error("=" * 70)
            log.error("🚨 SAFETY GATEKEEPER: ORDER BLOCKED")
            log.error("=" * 70)
            log.error("Reason: INVALID TRADING_MODE")
            log.error(f"Current value: {trading_mode}")
            log.error(f"Valid values: demo, live")
            log.error(f"Origin: {origin}")
            log.error("=" * 70)
            return False
        
        # Check 4: Live mode acknowledgment (only for live trading)
        if trading_mode == 'live':
            i_understand = cfg.safety.i_understand_live.upper()
            
            if i_understand != 'YES':
                self._block_count += 1
                self._last_block_reason = "live_not_acknowledged"
                
                log.error("=" * 70)
                log.error("🚨 SAFETY GATEKEEPER: ORDER BLOCKED")
                log.error("=" * 70)
                log.error("Reason: LIVE TRADING NOT ACKNOWLEDGED")
                log.error(f"Current value: {i_understand}")
                log.error(f"Origin: {origin}")
                log.error("")
                log.error("You are attempting to trade with REAL MONEY")
                log.error("but have not acknowledged the risks.")
                log.error("")
                log.error("To enable live trading:")
                log.error("  Set safety.live_trading_acknowledged=true in config.yaml")
                log.error("")
                log.error("⚠️  WARNING: Live trading involves real financial risk!")
                log.error("=" * 70)
                return False
        
        # Check 5: Volatility safety REMOVED - Guardian monitors this
        # Guardian checks IV/RV/spread and publishes GO/STOP signal
        # Trading bot will read Guardian signal in Phase 2.6
        
        # Check 6: Order Confirmation Guard (unconfirmed fills)
        if CONFIRMATION_GUARD_AVAILABLE:
            try:
                guard = get_confirmation_guard()
                if guard:
                    can_place, conf_reason = guard.can_place_new_order()
                    if not can_place:
                        self._block_count += 1
                        self._last_block_reason = f"confirmation: {conf_reason}"
                        
                        log.warning("=" * 70)
                        log.warning("🔒 SAFETY GATEKEEPER: ORDER BLOCKED")
                        log.warning("=" * 70)
                        log.warning("Reason: WAITING FOR FILL CONFIRMATION")
                        log.warning(f"Details: {conf_reason}")
                        log.warning(f"Origin: {origin}")
                        log.warning("")
                        log.warning("Cannot place new orders until previous order is confirmed.")
                        log.warning("Bot will resume automatically when confirmation received.")
                        log.warning("=" * 70)
                        return False
            except Exception as e:
                log.debug(f"Confirmation guard check failed (non-fatal): {e}")
        
        # Check 6.5: Margin/Position/Liquidation checking REMOVED - Guardian monitors this
        # Guardian checks:
        #   - Position size (max_position_size)
        #   - Liquidation distance (min_liquidation_distance_inr)
        # Trading bot will read Guardian signal in Phase 2.6
        
        # Check 7: Equity Floor (if breach flag exists)
        equity_floor_breach = Path('.equity_floor_breach')
        if equity_floor_breach.exists():
            self._block_count += 1
            self._last_block_reason = "equity_floor_breach"
            
            log.error("=" * 70)
            log.error("🚨 SAFETY GATEKEEPER: ORDER BLOCKED")
            log.error("=" * 70)
            log.error("Reason: EQUITY FLOOR BREACH")
            log.error(f"Origin: {origin}")
            log.error("")
            log.error("Account equity has fallen below the hard floor.")
            log.error("Manual operator acknowledgment required:")
            log.error("  1. Review account status")
            log.error("  2. Determine root cause")
            log.error("  3. Create acknowledgment: touch .operator_ack_equity_floor")
            log.error("  4. Remove breach flag: rm .equity_floor_breach")
            log.error("=" * 70)
            return False
        
        # Check 8: Pending Order Budget
        max_pending_notional = cfg.capital_protection.pending_budget.max_notional_inr
        if max_pending_notional > 0:
            try:
                from bot.api.exchange_ops import get_exchange_ops
                exchange_ops = get_exchange_ops()
                
                # Fetch all pending BUY orders
                open_orders = exchange_ops.fetch_open_orders()
                pending_buy_orders = [o for o in open_orders if o.get('side') == 'buy' and not o.get('reduceOnly')]
                
                # Calculate total pending notional
                total_pending = sum(float(o.get('price', 0)) * float(o.get('amount', 0)) for o in pending_buy_orders)
                
                buffer_pct = cfg.capital.pending_budget_buffer_pct
                alert_threshold = max_pending_notional * (1 - buffer_pct / 100)
                
                if total_pending >= max_pending_notional:
                    self._block_count += 1
                    self._last_block_reason = f"pending_budget_exceeded: {total_pending:,.0f}/{max_pending_notional:,.0f}"
                    
                    log.warning("=" * 70)
                    log.warning("💰 SAFETY GATEKEEPER: ORDER BLOCKED")
                    log.warning("=" * 70)
                    log.warning("Reason: PENDING ORDER BUDGET EXCEEDED")
                    log.warning(f"Current Pending: ₹{total_pending:,.2f}")
                    log.warning(f"Budget Limit: ₹{max_pending_notional:,.2f}")
                    log.warning(f"Open Orders: {len(pending_buy_orders)}")
                    log.warning(f"Origin: {origin}")
                    log.warning("")
                    log.warning("Too much capital at risk in pending orders.")
                    log.warning("Wait for some orders to fill or cancel before placing new ones.")
                    log.warning("=" * 70)
                    return False
                    
                elif total_pending >= alert_threshold:
                    log.warning(
                        f"⚠️  Pending budget at {(total_pending/max_pending_notional*100):.0f}% "
                        f"(₹{total_pending:,.0f}/₹{max_pending_notional:,.0f})"
                    )
                    
            except Exception as e:
                log.debug(f"Pending budget check failed (non-fatal): {e}")
        
        # Check 9: Exposure Growth Rate Limiter
        try:
            from bot.safety.exposure_limiter import get_exposure_limiter
            limiter = get_exposure_limiter()
            
            if limiter.enabled:
                # Estimate notional value (will be more accurate when order is actually placed)
                notional_estimate = context.get('notional_value')

                if notional_estimate is None:
                    price = context.get('price') or context.get('trigger_price') or context.get('limit_price')
                    quantity = context.get('size') or context.get('quantity') or context.get('qty')
                    try:
                        if price is not None and quantity is not None:
                            notional_estimate = float(price) * abs(float(quantity))
                    except (TypeError, ValueError):
                        notional_estimate = None

                if notional_estimate is None:
                    try:
                        reference_price = cfg.grid.reference_price
                    except (TypeError, ValueError):
                        reference_price = 110000.0
                    try:
                        lot_size = abs(cfg.grid.lot_size)
                    except (TypeError, ValueError):
                        lot_size = 1.0
                    notional_estimate = reference_price * lot_size
                
                can_place, limit_reason = limiter.can_place_order(notional_estimate)
                if not can_place:
                    self._block_count += 1
                    self._last_block_reason = f"exposure_growth: {limit_reason}"
                    
                    log.warning("=" * 70)
                    log.warning("⚡ SAFETY GATEKEEPER: ORDER BLOCKED")
                    log.warning("=" * 70)
                    log.warning("Reason: EXPOSURE GROWTH RATE LIMIT")
                    log.warning(f"Details: {limit_reason}")
                    log.warning(f"Origin: {origin}")
                    log.warning("=" * 70)
                    return False
        except Exception as e:
            log.debug(f"Exposure growth check failed (non-fatal): {e}")
        
        # Check 10: Drawdown Cap Protective Mode
        drawdown_protective_mode = Path('.drawdown_protective_mode')
        if drawdown_protective_mode.exists():
            # Only block BUY orders, allow TP (reduce-only) orders
            if not context.get('reduce_only', False):
                self._block_count += 1
                self._last_block_reason = "drawdown_protective_mode"
                
                log.warning("=" * 70)
                log.warning("📉 SAFETY GATEKEEPER: ORDER BLOCKED")
                log.warning("=" * 70)
                log.warning("Reason: DRAWDOWN PROTECTIVE MODE ACTIVE")
                log.warning(f"Origin: {origin}")
                log.warning("")
                log.warning("30-day drawdown limit exceeded.")
                log.warning("Only TP (exit) orders allowed.")
                log.warning("New BUY orders blocked until drawdown recovers.")
                log.warning("=" * 70)
                return False
        
        # Check 11: Additional safety checks from context
        if context.get('force_block', False):
            self._block_count += 1
            self._last_block_reason = context.get('block_reason', 'force_block')
            
            log.warning("=" * 70)
            log.warning("⚠️  SAFETY GATEKEEPER: ORDER BLOCKED")
            log.warning("=" * 70)
            log.warning(f"Reason: {self._last_block_reason}")
            log.warning(f"Origin: {origin}")
            log.warning("=" * 70)
            return False
        
        # All checks passed!
        if self._check_count % 100 == 1:  # Log every 100th check to avoid spam
            log.debug(
                f"✅ Gatekeeper: Check #{self._check_count} passed "
                f"(blocked: {self._block_count}, origin: {origin})"
            )
        
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get gatekeeper statistics"""
        return {
            'checks': self._check_count,
            'blocks': self._block_count,
            'last_block_reason': self._last_block_reason,
            'block_rate': self._block_count / max(self._check_count, 1)
        }
    
    def reset_stats(self):
        """Reset statistics (for testing)"""
        self._check_count = 0
        self._block_count = 0
        self._last_block_reason = None


# Global singleton instance
_gatekeeper = SafetyGatekeeper()


def can_place_orders(context: Optional[Dict[str, Any]] = None) -> bool:
    """
    Check if orders can be placed right now.
    
    This is the ONLY function that should be called to check trading permission.
    ALL order placement code MUST call this first.
    
    Args:
        context: Optional context dict for logging (e.g., {'origin': 'smart_gap_fill'})
    
    Returns:
        bool: True if safe to place orders, False otherwise
    
    Example:
        from bot.safety.gatekeeper import can_place_orders
        
        def place_buy_order(price, size):
            if not can_place_orders({'origin': 'grid_buy'}):
                log.warning("Order blocked by gatekeeper")
                return None
    """
    # Load latest config first
    _load_config()
    return _gatekeeper.can_place_orders(context)


def get_gatekeeper_stats() -> Dict[str, Any]:
    """Get gatekeeper statistics"""
    return _gatekeeper.get_stats()


def reset_gatekeeper_stats():
    """Reset gatekeeper statistics (for testing)"""
    _gatekeeper.reset_stats()
