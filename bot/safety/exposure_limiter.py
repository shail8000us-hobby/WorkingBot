"""
Exposure Growth Rate Limiter

Prevents "flash cascade" fills during rapid market moves by limiting
how fast positions can be opened.

Key Features:
- Tracks order timestamps in sliding 60-second window
- Limits max tranches opened per minute
- Limits max notional value per minute
- Optional queueing of excess orders
"""

import os
import logging
import sys
import time
from pathlib import Path
from typing import Tuple, Optional, List, Dict
from collections import deque
from datetime import datetime, timedelta

# Add project root to path for config imports
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.loader import get_config

log = logging.getLogger("exposure_limiter")
# YAML Config Integration
try:
    from config.loader import get_config
    YAML_CONFIG_AVAILABLE = True
except Exception:
    YAML_CONFIG_AVAILABLE = False
    def get_config(): return None


class ExposureGrowthLimiter:
    """
    Limits how fast positions can be opened to prevent flash cascade fills.
    
    Tracks:
    - Number of tranches opened in last 60 seconds
    - Total notional value added in last 60 seconds
    - Queue of pending orders (if queueing enabled)
    """
    
    def __init__(self):
        """Initialize exposure limiter"""
        # Load configuration from YAML
        cfg = get_config()
        self.enabled = cfg.capital_protection.exposure_growth.enabled
        self.max_tranches_per_minute = cfg.capital_protection.exposure_growth.max_tranches_per_minute
        self.max_notional_per_minute = cfg.capital_protection.exposure_growth.max_notional_inr_per_minute
        self.queue_enabled = cfg.capital_protection.exposure_growth.queue_enabled
        
        # Sliding window tracking (timestamp, notional)
        self._order_history: deque = deque(maxlen=100)  # Last 100 orders
        
        # Queued orders (if enabled)
        self._queued_orders: List[Dict] = []
        
        # Statistics
        self._total_checks = 0
        self._total_blocks = 0
        self._total_queued = 0
        
        if self.enabled:
            log.info("=" * 70)
            log.info("⚡ EXPOSURE GROWTH RATE LIMITER INITIALIZED")
            log.info("=" * 70)
            log.info(f"Max Tranches/Min: {self.max_tranches_per_minute}")
            log.info(f"Max Notional/Min: ₹{self.max_notional_per_minute:,.0f}")
            log.info(f"Queue Enabled: {self.queue_enabled}")
            log.info("=" * 70)
    
    def can_place_order(self, notional_value: float) -> Tuple[bool, Optional[str]]:
        """
        Check if a new order can be placed given current exposure growth.
        
        Args:
            notional_value: Notional value of the order (price × qty)
            
        Returns:
            Tuple of (can_place: bool, reason: Optional[str])
        """
        if not self.enabled:
            return True, None
        
        self._total_checks += 1
        
        # Remove orders older than 60 seconds
        cutoff_time = time.time() - 60
        while self._order_history and self._order_history[0]['timestamp'] < cutoff_time:
            self._order_history.popleft()
        
        # Count tranches in last 60 seconds
        tranches_in_window = len(self._order_history)
        
        # Sum notional in last 60 seconds
        notional_in_window = sum(o['notional'] for o in self._order_history)
        
        # Check tranche limit
        if tranches_in_window >= self.max_tranches_per_minute:
            self._total_blocks += 1
            reason = (
                f"⏱️ Tranche rate limit: {tranches_in_window}/{self.max_tranches_per_minute} per minute. "
                f"Preventing flash cascade fills."
            )
            
            if self.queue_enabled:
                self._total_queued += 1
                reason += f" Order queued ({len(self._queued_orders) + 1} in queue)."
            
            return False, reason
        
        # Check notional limit
        effective_limit = max(self.max_notional_per_minute, notional_value)
        if notional_in_window + notional_value > effective_limit:
            self._total_blocks += 1
            reason = (
                f"💰 Notional rate limit: ₹{notional_in_window:,.0f} + ₹{notional_value:,.0f} "
                f"> ₹{self.max_notional_per_minute:,.0f} per minute. "
                f"Preventing excessive exposure growth."
            )
            
            if self.queue_enabled:
                self._total_queued += 1
                reason += f" Order queued ({len(self._queued_orders) + 1} in queue)."
            
            return False, reason
        
        # All checks passed
        return True, None
    
    def register_order(self, notional_value: float):
        """
        Register an order that was placed.
        
        Args:
            notional_value: Notional value of the order
        """
        if not self.enabled:
            return
        
        self._order_history.append({
            'timestamp': time.time(),
            'notional': notional_value
        })
        
        log.debug(
            f"Registered order: ₹{notional_value:,.0f} | "
            f"Window: {len(self._order_history)} tranches, "
            f"₹{sum(o['notional'] for o in self._order_history):,.0f} notional"
        )
    
    def queue_order(self, order_details: Dict):
        """
        Queue an order for later placement.
        
        Args:
            order_details: Order details dict
        """
        if not self.queue_enabled:
            return
        
        order_details['queued_at'] = time.time()
        self._queued_orders.append(order_details)
        
        log.info(
            f"📦 Order queued: {order_details.get('side')} @ {order_details.get('price')} "
            f"(queue depth: {len(self._queued_orders)})"
        )
    
    def process_queue(self) -> List[Dict]:
        """
        Process queued orders and return those that can now be placed.
        
        Returns:
            List of order details that can be placed
        """
        if not self.queue_enabled or not self._queued_orders:
            return []
        
        processable = []
        remaining = []
        
        for order in self._queued_orders:
            notional = order.get('price', 0) * order.get('amount', 0)
            can_place, _ = self.can_place_order(notional)
            
            if can_place:
                processable.append(order)
                log.info(f"✅ Dequeued order: {order.get('side')} @ {order.get('price')}")
            else:
                remaining.append(order)
        
        self._queued_orders = remaining
        return processable
    
    def get_stats(self) -> Dict:
        """Get limiter statistics"""
        # Calculate current window stats
        cutoff_time = time.time() - 60
        recent_orders = [o for o in self._order_history if o['timestamp'] >= cutoff_time]
        
        return {
            'enabled': self.enabled,
            'max_tranches_per_minute': self.max_tranches_per_minute,
            'max_notional_per_minute': self.max_notional_per_minute,
            'queue_enabled': self.queue_enabled,
            'total_checks': self._total_checks,
            'total_blocks': self._total_blocks,
            'total_queued': self._total_queued,
            'current_window': {
                'tranches': len(recent_orders),
                'notional_inr': sum(o['notional'] for o in recent_orders),
                'utilization_pct': (len(recent_orders) / self.max_tranches_per_minute * 100) if self.max_tranches_per_minute > 0 else 0
            },
            'queue_depth': len(self._queued_orders)
        }
    
    def reset(self):
        """Reset limiter state (for testing or manual intervention)"""
        self._order_history.clear()
        self._queued_orders.clear()
        log.warning("Exposure limiter reset - cleared all tracking")


# Global singleton instance
_limiter: Optional[ExposureGrowthLimiter] = None


def get_exposure_limiter() -> ExposureGrowthLimiter:
    """Get or create global exposure limiter instance"""
    global _limiter
    if _limiter is None:
        _limiter = ExposureGrowthLimiter()
    return _limiter

def reload_exposure_limiter():
    """Reload exposure limiter configuration"""
    global _limiter
    _limiter = None  # Force recreation on next get_exposure_limiter() call
