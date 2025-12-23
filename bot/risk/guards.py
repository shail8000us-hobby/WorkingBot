import os
import sys
import logging
from decimal import Decimal
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config

# Import emergency override system
try:
    from bot.safety.emergency_override import should_check_monitoring
    OVERRIDE_AVAILABLE = True
except ImportError:
    OVERRIDE_AVAILABLE = False
    # Fallback: always check if import fails
    def should_check_monitoring():
        return True

log = logging.getLogger("runner")


class RiskBreach(Exception):
    """Raised when a trade violates canary risk limits."""
    pass


def _to_dec(name: str, default) -> Decimal:
    v = os.getenv(name, str(default)).strip()
    return Decimal(v) if v != "" else Decimal(default)


def assert_can_trade(account_snapshot: dict, pending_open_orders: int, intended_qty, intended_price) -> None:
    """Hard-stop checks based on actual PnL from bot's positions.
    
    Simple logic:
    1. Get unrealized PnL for bot's open positions (in USD)
    2. Convert to INR: PnL_INR = PnL_USD × 85
    3. If loss > MAX_ACCOUNT_LOSS_INR → Block new orders
    4. Otherwise → Allow trading
    
    No balance checks, no complex notional calculations.
    
    🚨 EMERGENCY OVERRIDE: Can be disabled via WebUI for emergency situations.
    """
    # Load YAML config
    config = get_config()
    
    # Check Guardian emergency flag first (highest priority - cannot be overridden)
    guardian_flag = Path(config.paths.guardian_emergency_flag if hasattr(config.paths, 'guardian_emergency_flag') else ".guardian_emergency_stop")
    if guardian_flag.exists():
        raise RiskBreach(
            "GUARDIAN EMERGENCY STOP ACTIVE!\n"
            "Guardian Bot has closed all positions due to loss limit breach.\n"
            "Trading is BLOCKED until manual review.\n"
            f"Delete {guardian_flag} file only after reviewing the situation."
        )
    
    # Basic checks (cannot be overridden - critical for safety)
    if not config.safety.i_understand_live:
        raise RiskBreach("Refusing: I_UNDERSTAND_LIVE must be YES.")
    if not config.safety.execute_orders:
        raise RiskBreach("Execution disabled: EXECUTE_ORDERS is not true.")

    # 🚨 EMERGENCY OVERRIDE CHECK
    # If monitoring is disabled via WebUI, skip safety limit checks
    monitoring_enabled = should_check_monitoring()
    
    if not monitoring_enabled:
        log.warning("⚠️" * 30)
        log.warning("🚨 EMERGENCY OVERRIDE ACTIVE: Safety monitoring DISABLED")
        log.warning("   Loss limits, order counts, and quantity checks are BYPASSED")
        log.warning("   Re-enable monitoring in WebUI as soon as possible!")
        log.warning("⚠️" * 30)
        # Skip all safety limit checks below
        return
    
    # Normal safety checks (only executed if monitoring is enabled)
    max_loss_inr = Decimal(str(config.capital_protection.max_loss_inr))
    max_open_orders_cap = config.risk_limits.max_open_orders
    max_qty_cap = Decimal(str(config.risk_limits.max_qty_per_order))
    usd_to_inr_rate = Decimal(str(config.risk_limits.usd_to_inr_rate))

    # Get unrealized PnL from bot's positions (in USD)
    unrealized_pnl_usd = Decimal(str(account_snapshot.get("unrealized_pnl_usd", "0")))
    # Convert to INR
    unrealized_pnl_inr = unrealized_pnl_usd * usd_to_inr_rate
    
    open_orders_count = int(account_snapshot.get("open_orders_count", 0))
    
    # 1) Check if current loss exceeds limit
    # Example: Position 1: -$10, Position 2: -$15, Position 3: +$5 = -$20 total
    # Loss in INR = 20 × 85 = ₹1,700
    if unrealized_pnl_inr < 0:
        current_loss_inr = -unrealized_pnl_inr  # Convert negative to positive
        log.debug(f"Risk check: Current loss = ${-unrealized_pnl_usd:.2f} × {usd_to_inr_rate} = ₹{current_loss_inr:.2f} vs max = ₹{max_loss_inr}")
        
        if current_loss_inr >= max_loss_inr:
            # BLOCK new orders, but just log signal
            log.warning(f"⚠️ RISK SIGNAL: Loss limit reached! ₹{current_loss_inr:.2f} >= ₹{max_loss_inr}")
            raise RiskBreach(f"Loss limit reached: ₹{current_loss_inr:.2f} >= ₹{max_loss_inr}. Stop trading.")
    else:
        # In profit, all good
        log.debug(f"Risk check: Current PnL = ${unrealized_pnl_usd:.2f} × {usd_to_inr_rate} = ₹{unrealized_pnl_inr:.2f} (PROFIT)")

    # 2) Order count fence
    total_orders = open_orders_count + int(pending_open_orders)
    log.debug(f"Risk check: open={open_orders_count} + pending={pending_open_orders} = {total_orders} vs max={max_open_orders_cap}")
    
    if total_orders >= max_open_orders_cap:
        raise RiskBreach(f"Too many open orders. ({total_orders} >= {max_open_orders_cap})")

    # 3) Quantity fence
    if Decimal(str(intended_qty)) > max_qty_cap:
        raise RiskBreach(f"Order qty exceeds limit: {intended_qty} > {max_qty_cap}")
