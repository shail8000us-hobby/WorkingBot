"""
Order Confirmation Guard - Strict Fill Acknowledgment Lock

This module prevents the bot from placing new orders when there are unconfirmed
fills. It ensures that every order is properly acknowledged before continuing.

Key Features:
1. Tracks all pending orders awaiting fill confirmation
2. Blocks new orders until fill confirmation + TP placement
3. Periodically polls exchange for missing confirmations
4. Detects chaos/outages (delayed confirmations)
5. Auto-resumes when confirmations received

Philosophy: "Don't trade in the dark without a torch"
- If we can't confirm fills, the exchange might be having issues
- Better to wait than to double-fill or create chaos positions

Configuration (from YAML):
- safety.confirmation_guard.enabled
- safety.confirmation_guard.poll_interval
- safety.confirmation_guard.chaos_threshold
"""

import os
import sys
import time
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from threading import Lock
from pathlib import Path

# Add project root to path for config imports
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.loader import get_config
from bot.state.store import StateStore
from bot.utils.atomic_file import atomic_write_json

log = logging.getLogger("confirmation_guard")

# Order states
class OrderState:
    PENDING = "pending"           # Order placed, waiting for fill
    FILLED = "filled"             # Fill confirmed, waiting for TP
    TP_PLACED = "tp_placed"       # TP order placed, waiting for TP fill
    COMPLETED = "completed"       # TP filled, cycle complete
    CANCELLED = "cancelled"       # Order cancelled
    FAILED = "failed"             # Order failed


class OrderConfirmationGuard:
    """
    Guards against placing new orders when previous orders lack confirmation.
    
    Strict Mode Rules:
    1. Track every BUY order placed
    2. Wait for fill confirmation from exchange
    3. Wait for TP order placement
    4. Block ALL new BUY orders until confirmation received
    5. Auto-poll exchange every N seconds for confirmations
    """
    
    def __init__(self):
        """Initialize the confirmation guard"""
        # Load configuration from YAML
        yaml_config = get_config()
        
        self.enabled = yaml_config.safety.confirmation_guard.enabled
        self.poll_interval = yaml_config.safety.confirmation_guard.poll_interval
        self.chaos_threshold = yaml_config.safety.confirmation_guard.chaos_threshold
        
        # State
        self._lock = Lock()
        self._pending_orders: Dict[str, Dict[str, Any]] = {}  # client_id -> order info
        self._last_poll_time: Optional[datetime] = None
        
        # Statistics
        self._total_orders = 0
        self._blocks = 0
        self._chaos_detections = 0
        self._last_block_reason: Optional[str] = None
        
        # Persistence
        self._state_file = self._get_state_file()
        self._store = StateStore(self._state_file, default={'pending_orders': {}})
        self._load_state()
        
        log.info("=" * 70)
        log.info("🔒 ORDER CONFIRMATION GUARD INITIALIZED")
        log.info("=" * 70)
        log.info(f"Enabled: {self.enabled}")
        log.info(f"Poll Interval: {self.poll_interval}s")
        log.info(f"Chaos Threshold: {self.chaos_threshold}s")
        log.info(f"Pending Orders: {len(self._pending_orders)}")
        log.info("=" * 70)
    
    def _get_state_file(self) -> Path:
        """Get mode-specific state file path"""
        try:
            from bot.utils.env_loader import get_current_mode
            mode = get_current_mode()
        except Exception:
            mode = "demo"
        
        state_dir = Path(__file__).parent.parent.parent / "bot" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        return state_dir / f"confirmation_guard_{mode}.json"
    
    def _load_state(self):
        """Load pending orders from disk"""
        try:
            if self._state_file.exists():
                data = self._store.locked_read()
                self._pending_orders = data.get('pending_orders', {})
                
                for order_id, order in self._pending_orders.items():
                    if 'timestamp' in order:
                        order['timestamp'] = datetime.fromisoformat(order['timestamp'])
                
                log.info(f"Loaded {len(self._pending_orders)} pending orders from state file")
        except Exception as e:
            log.error(f"Failed to load confirmation guard state: {e}")
            self._pending_orders = {}
    
    def _save_state(self):
        """Save pending orders to disk"""
        try:
            # Convert datetime to string for JSON serialization
            serializable_orders = {}
            for order_id, order in self._pending_orders.items():
                order_copy = order.copy()
                if 'timestamp' in order_copy and isinstance(order_copy['timestamp'], datetime):
                    order_copy['timestamp'] = order_copy['timestamp'].isoformat()
                serializable_orders[order_id] = order_copy
            
            data = {
                'pending_orders': serializable_orders,
                'last_updated': datetime.utcnow().isoformat()
            }
            
            atomic_write_json(self._state_file, data, indent=2)
        except Exception as e:
            log.error(f"Failed to save confirmation guard state: {e}")
    
    def register_order(self, client_id: str, order_details: Dict[str, Any]):
        """
        Register a new order that needs confirmation.
        
        Args:
            client_id: Bot-assigned order ID
            order_details: Dict with keys: exchange_id, symbol, side, price, amount
        """
        with self._lock:
            self._pending_orders[client_id] = {
                'exchange_id': order_details.get('exchange_id'),
                'symbol': order_details.get('symbol'),
                'side': order_details.get('side'),
                'price': order_details.get('price'),
                'amount': order_details.get('amount'),
                'state': OrderState.PENDING,
                'timestamp': datetime.utcnow(),
                'tp_order_id': None
            }
            self._total_orders += 1
            
            log.info(
                f"📝 Registered order {client_id}: "
                f"{order_details.get('side')} {order_details.get('amount')} "
                f"@ {order_details.get('price')}"
            )
            
            self._save_state()
    
    def confirm_fill(self, client_id: str, fill_details: Optional[Dict[str, Any]] = None):
        """
        Confirm that an order was filled.
        
        Args:
            client_id: Bot-assigned order ID
            fill_details: Optional details about the fill
        """
        with self._lock:
            if client_id in self._pending_orders:
                self._pending_orders[client_id]['state'] = OrderState.FILLED
                self._pending_orders[client_id]['fill_time'] = datetime.utcnow()
                
                if fill_details:
                    self._pending_orders[client_id]['fill_price'] = fill_details.get('fill_price')
                
                log.info(f"✅ Fill confirmed for order {client_id}")
                self._save_state()
            else:
                log.warning(f"Attempted to confirm unknown order {client_id}")
    
    def confirm_tp_placed(self, buy_client_id: str, tp_client_id: str):
        """
        Confirm that TP order was placed for a filled buy order.
        
        Args:
            buy_client_id: Original buy order client ID
            tp_client_id: TP order client ID
        """
        with self._lock:
            if buy_client_id in self._pending_orders:
                self._pending_orders[buy_client_id]['state'] = OrderState.TP_PLACED
                self._pending_orders[buy_client_id]['tp_order_id'] = tp_client_id
                self._pending_orders[buy_client_id]['tp_placed_time'] = datetime.utcnow()
                
                log.info(f"✅ TP placed for order {buy_client_id} (TP: {tp_client_id})")
                
                # Now we can remove from pending (cycle complete for buy side)
                del self._pending_orders[buy_client_id]
                log.info(f"🎉 Order {buy_client_id} confirmed complete, removed from pending")
                
                self._save_state()
            else:
                log.warning(f"Attempted to confirm TP for unknown order {buy_client_id}")
    
    def can_place_new_order(self) -> Tuple[bool, Optional[str]]:
        """
        Check if bot is allowed to place a new order.
        
        Returns:
            Tuple of (can_place, reason)
        """
        if not self.enabled:
            return True, None
        
        with self._lock:
            # Check if there are any pending orders
            if not self._pending_orders:
                return True, None
            
            # Get oldest pending order
            oldest_order_id = min(
                self._pending_orders.keys(),
                key=lambda k: self._pending_orders[k]['timestamp']
            )
            oldest_order = self._pending_orders[oldest_order_id]
            
            wait_time = (datetime.utcnow() - oldest_order['timestamp']).total_seconds()
            
            # Check for chaos (order confirmation delayed too long)
            if wait_time > self.chaos_threshold:
                self._chaos_detections += 1
                reason = (
                    f"🚨 CHAOS DETECTED: Order {oldest_order_id} pending for {wait_time:.0f}s "
                    f"(threshold: {self.chaos_threshold}s). Exchange may be having issues."
                )
                log.error(reason)
                
                # Send Telegram alert
                self._send_chaos_alert(oldest_order_id, wait_time)
            else:
                reason = (
                    f"⏳ Waiting for confirmation: Order {oldest_order_id} "
                    f"(state: {oldest_order['state']}, pending: {wait_time:.0f}s)"
                )
                log.warning(reason)
            
            self._blocks += 1
            self._last_block_reason = reason
            
            return False, reason
    
    def _send_chaos_alert(self, order_id: str, wait_time: float):
        """Send Telegram alert for chaos detection"""
        try:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'tools'))
            from telepush import send_telegram_alert
            
            order = self._pending_orders[order_id]
            
            message = (
                f"🚨 EXCHANGE CHAOS DETECTED!\n\n"
                f"Order Confirmation Delayed:\n"
                f"• Order ID: {order_id}\n"
                f"• Type: {order['side'].upper()}\n"
                f"• Price: {order['price']}\n"
                f"• Pending: {wait_time:.0f} seconds\n"
                f"• Threshold: {self.chaos_threshold}s\n\n"
                f"⚠️ Bot has STOPPED placing new orders\n"
                f"⚠️ Exchange may be experiencing issues\n\n"
                f"Action: Manually check exchange status"
            )
            
            send_telegram_alert(message)
            log.info("Chaos alert sent via Telegram")
            
        except Exception as e:
            log.error(f"Failed to send chaos alert: {e}")
    
    def poll_confirmations(self, exchange_api):
        """
        Poll exchange for pending order confirmations.
        
        This should be called periodically (e.g., every 10 seconds).
        
        Args:
            exchange_api: Exchange API object with methods to check order status
        """
        if not self.enabled:
            return
        
        # Rate limit polling
        if self._last_poll_time:
            elapsed = (datetime.utcnow() - self._last_poll_time).total_seconds()
            if elapsed < self.poll_interval:
                return
        
        with self._lock:
            if not self._pending_orders:
                return
            
            log.debug(f"Polling {len(self._pending_orders)} pending orders...")
            
            for client_id, order in list(self._pending_orders.items()):
                try:
                    # Check order status on exchange
                    exchange_id = order.get('exchange_id')
                    if not exchange_id:
                        continue
                    
                    # Fetch order from exchange
                    exchange_order = exchange_api.fetch_order(exchange_id, order['symbol'])
                    
                    if exchange_order and exchange_order.get('status') == 'closed':
                        # Order was filled!
                        log.info(f"✅ Detected fill for order {client_id} via polling")
                        self.confirm_fill(client_id, {
                            'fill_price': exchange_order.get('average')
                        })
                    
                except Exception as e:
                    log.debug(f"Error polling order {client_id}: {e}")
            
            self._last_poll_time = datetime.utcnow()
    
    def clear_stale_orders(self, max_age_hours: int = 24):
        """
        Clear orders that are too old (safety cleanup).
        
        Args:
            max_age_hours: Maximum age in hours before order is considered stale
        """
        with self._lock:
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            
            stale_orders = [
                order_id for order_id, order in self._pending_orders.items()
                if order['timestamp'] < cutoff_time
            ]
            
            for order_id in stale_orders:
                log.warning(f"Clearing stale order {order_id} (age > {max_age_hours}h)")
                del self._pending_orders[order_id]
            
            if stale_orders:
                self._save_state()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get confirmation guard statistics"""
        with self._lock:
            pending_list = []
            for order_id, order in self._pending_orders.items():
                wait_time = (datetime.utcnow() - order['timestamp']).total_seconds()
                pending_list.append({
                    'client_id': order_id,
                    'state': order['state'],
                    'side': order['side'],
                    'price': order['price'],
                    'wait_time_seconds': wait_time,
                    'timestamp': order['timestamp'].isoformat()
                })
            
            return {
                'enabled': self.enabled,
                'total_orders_registered': self._total_orders,
                'blocks': self._blocks,
                'chaos_detections': self._chaos_detections,
                'last_block_reason': self._last_block_reason,
                'pending_orders_count': len(self._pending_orders),
                'pending_orders': pending_list,
                'poll_interval': self.poll_interval,
                'chaos_threshold': self.chaos_threshold
            }
    
    def reset(self):
        """Reset the guard (for testing or manual intervention)"""
        with self._lock:
            log.warning("🔓 Confirmation Guard manually reset - clearing all pending orders")
            self._pending_orders = {}
            self._save_state()


# Global singleton instance
_guard: Optional[OrderConfirmationGuard] = None


def get_confirmation_guard() -> OrderConfirmationGuard:
    """Get or create global confirmation guard instance"""
    global _guard
    if _guard is None:
        _guard = OrderConfirmationGuard()
    return _guard
