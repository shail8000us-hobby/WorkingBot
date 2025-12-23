"""
Pending Order Budget Control - Capital At Risk Management

Limits total capital committed to pending BUY orders to prevent over-commitment.
This ensures you don't have too much capital "locked" in orders waiting to fill.

Key Features:
- Real-time calculation of pending order notional value
- Buffer zone for early warnings
- Exchange API integration for live order data
- Supports both absolute limits and percentage-based alerts

Configuration (from YAML):
- capital_protection.pending_budget.max_notional_inr
- capital_protection.pending_budget.buffer_pct
"""

import os
import sys
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# Add project root to path for config imports
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.loader import get_config

log = logging.getLogger("pending_budget")


class PendingBudgetControl:
    """
    Controls total capital at risk in pending BUY orders.
    
    Prevents over-commitment by tracking and limiting the total notional
    value of all open BUY orders.
    """
    
    def __init__(self, delta_client=None, config=None):
        """
        Initialize pending budget control.
        
        Args:
            delta_client: Delta Exchange client for fetching orders (optional)
            config: Configuration dict (optional, uses env vars if not provided)
        """
        self.exchange = delta_client
        self.config = config or {}
        
        # Load configuration from YAML
        yaml_config = get_config()
        self.max_pending_notional = yaml_config.capital_protection.pending_budget.max_notional_inr
        self.buffer_pct = yaml_config.capital_protection.pending_budget.buffer_pct
        self.enabled = self.max_pending_notional > 0
        
        # Alert threshold (trigger warning before hitting limit)
        self.alert_threshold = self.max_pending_notional * (1 - self.buffer_pct / 100)
        
        # Statistics
        self._check_count = 0
        self._block_count = 0
        self._alert_count = 0
        self._last_pending = 0
        
        if self.enabled:
            log.info("=" * 70)
            log.info("💰 PENDING BUDGET CONTROL INITIALIZED")
            log.info("=" * 70)
            log.info(f"Max Pending Notional: ₹{self.max_pending_notional:,}")
            log.info(f"Alert Threshold: ₹{self.alert_threshold:,} ({100 - self.buffer_pct:.0f}%)")
            log.info(f"Buffer: {self.buffer_pct}%")
            log.info("=" * 70)
        else:
            log.info("Pending budget control DISABLED (MAX_PENDING_NOTIONAL_INR=0)")
    
    def set_exchange(self, exchange_client):
        """Set exchange client (for deferred initialization)"""
        self.exchange = exchange_client
    
    def get_pending_orders(self) -> List[Dict]:
        """
        Fetch all open BUY orders from exchange.
        
        Returns:
            List of pending BUY orders
        """
        if not self.exchange:
            log.warning("No exchange client available for pending orders check")
            return []
        
        try:
            # Fetch all open orders (CCXT format - returns list directly)
            open_orders = self.exchange.fetch_open_orders()
            
            # fetch_open_orders returns a list of orders in CCXT format
            if not isinstance(open_orders, list):
                log.warning(f"Unexpected open orders response format (expected list): {type(open_orders)}")
                return []
            
            # Filter for BUY orders only (not reduce-only)
            # Check both 'reduce_only' and nested 'info.reduce_only'
            pending_buys = []
            for order in open_orders:
                if order.get('side') == 'buy':
                    reduce_only = order.get('reduce_only', order.get('info', {}).get('reduce_only', False))
                    if not reduce_only:
                        pending_buys.append(order)
            
            return pending_buys
            
        except Exception as e:
            log.error(f"Failed to fetch pending orders: {e}")
            return []
    
    def calculate_pending_notional(self, pending_orders: Optional[List[Dict]] = None) -> float:
        """
        Calculate total notional value of pending BUY orders.
        Ignores reduce-only orders as they don't increase exposure.
        
        Args:
            pending_orders: Optional pre-fetched orders (if None, will fetch)
            
        Returns:
            Total notional value in INR
        """
        if pending_orders is None:
            pending_orders = self.get_pending_orders()
        
        total_notional_inr = 0.0
        USD_TO_INR = 85.0
        
        for order in pending_orders:
            try:
                # Skip reduce-only orders (they close positions, don't increase exposure)
                if order.get('reduceOnly', False) or order.get('reduce_only', False):
                    log.debug(f"Skipping reduce-only order {order.get('id')}")
                    continue
                
                # CCXT format uses 'price' and 'amount' fields
                price_usd = float(order.get('price', 0))
                size = float(order.get('amount', 0))
                
                if price_usd > 0 and size > 0:
                    # Calculate notional value in USD, then convert to INR
                    notional_usd = price_usd * size
                    notional_inr = notional_usd * USD_TO_INR
                    total_notional_inr += notional_inr
                    log.debug(f"Order {order.get('id')}: ₹{price_usd:,.0f} × {size} = ₹{notional_inr:,.0f}")
            except (TypeError, ValueError) as e:
                log.warning(f"Failed to parse order notional: {e}, order: {order.get('id')}")
        
        self._last_pending = total_notional_inr
        return total_notional_inr
    
    def can_place_order(self, order_price: float, order_size: float) -> Tuple[bool, Optional[str]]:
        """
        Check if a new order can be placed without exceeding budget.
        
        Args:
            order_price: Limit price of proposed order
            order_size: Size of proposed order
            
        Returns:
            Tuple of (allowed: bool, reason: Optional[str])
        """
        if not self.enabled:
            return True, None
        
        self._check_count += 1
        
        # Calculate notional value of new order
        new_order_notional = order_price * order_size
        
        # Get current pending orders
        pending_orders = self.get_pending_orders()
        current_pending = self.calculate_pending_notional(pending_orders)
        
        # Calculate projected total
        projected_total = current_pending + new_order_notional
        
        # Check if would exceed limit
        if projected_total > self.max_pending_notional:
            self._block_count += 1
            reason = (
                f"Pending budget exceeded: ₹{projected_total:,.0f} > ₹{self.max_pending_notional:,} "
                f"(current: ₹{current_pending:,.0f} + new: ₹{new_order_notional:,.0f})"
            )
            log.warning(f"💰 {reason}")
            return False, reason
        
        # Check if approaching limit (alert zone)
        elif projected_total >= self.alert_threshold:
            self._alert_count += 1
            utilization_pct = (projected_total / self.max_pending_notional) * 100
            log.warning(
                f"⚠️  Pending budget at {utilization_pct:.0f}% "
                f"(₹{projected_total:,.0f}/₹{self.max_pending_notional:,})"
            )
            # Still allow, just warn
            return True, None
        
        # All good
        return True, None
    
    def get_current_usage(self) -> Dict:
        """
        Get current pending budget usage.
        
        Returns:
            Dict with current pending, limit, and utilization
        """
        if not self.enabled:
            return {
                'enabled': False
            }
        
        pending_orders = self.get_pending_orders()
        current_pending = self.calculate_pending_notional(pending_orders)
        
        utilization_pct = (current_pending / self.max_pending_notional * 100) if self.max_pending_notional > 0 else 0
        available = max(0, self.max_pending_notional - current_pending)
        
        return {
            'enabled': True,
            'current_pending': current_pending,
            'max_pending': self.max_pending_notional,
            'available': available,
            'utilization_pct': utilization_pct,
            'alert_threshold': self.alert_threshold,
            'in_alert_zone': current_pending >= self.alert_threshold,
            'order_count': len(pending_orders)
        }
    
    def get_stats(self) -> Dict:
        """Get budget control statistics"""
        usage = self.get_current_usage()
        
        return {
            **usage,
            'check_count': self._check_count,
            'block_count': self._block_count,
            'alert_count': self._alert_count,
            'last_pending': self._last_pending,
            'block_rate': self._block_count / max(self._check_count, 1)
        }


# Global singleton instance
_controller: Optional[PendingBudgetControl] = None


def get_pending_budget_control(delta_client=None, config=None) -> PendingBudgetControl:
    """Get or create global pending budget control instance"""
    global _controller
    if _controller is None:
        _controller = PendingBudgetControl(delta_client=delta_client, config=config)
    return _controller
