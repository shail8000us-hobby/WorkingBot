"""
Robust Order Status Poller for Delta Exchange
Works on both testnet and live trading environments
"""

import time
import logging
import threading
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import requests
import os

from config.loader import get_config

log = logging.getLogger(__name__)

@dataclass
class OrderStatus:
    """Order status information"""
    order_id: str
    status: str  # open, filled, cancelled, rejected
    filled_size: float
    remaining_size: float
    average_price: Optional[float]
    last_updated: datetime

class OrderStatusPoller:
    """
    Robust order status polling system for Delta Exchange
    Works on both testnet and live trading
    """
    
    def __init__(self, delta_client, poll_interval: float = 5.0):
        """
        Initialize order status poller
        
        Args:
            delta_client: Delta Exchange client instance
            poll_interval: Polling interval in seconds (default: 5s)
        """
        self.delta_client = delta_client
        self.poll_interval = poll_interval
        self.running = False
        self.poll_thread = None
        self.order_statuses: Dict[str, OrderStatus] = {}
        self.fill_callbacks: List[Callable] = []
        self.lock = threading.RLock()
        
        # Get API configuration from YAML
        cfg = get_config()
        self.api_key = os.getenv('DELTA_API_KEY')  # Credentials still from env for security
        self.api_secret = os.getenv('DELTA_API_SECRET')  # Credentials still from env for security
        
        # Get base URL from config based on trading mode
        if cfg.trading_mode == 'live':
            self.base_url = cfg.api.live.base_url
        else:
            self.base_url = cfg.api.demo.base_url
        
        log.info(f"✅ Order Status Poller initialized (interval: {poll_interval}s, mode: {cfg.trading_mode})")
    
    def add_fill_callback(self, callback: Callable):
        """Add callback function for fill notifications"""
        with self.lock:
            self.fill_callbacks.append(callback)
            log.debug(f"Added fill callback: {callback.__name__}")
    
    def start_polling(self):
        """Start the polling thread"""
        if self.running:
            log.warning("Order status polling already running")
            return
        
        self.running = True
        self.poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.poll_thread.start()
        log.info("🔄 Order status polling started")
    
    def stop_polling(self):
        """Stop the polling thread"""
        self.running = False
        if self.poll_thread:
            self.poll_thread.join(timeout=2)
        log.info("⏹️ Order status polling stopped")
    
    def _poll_loop(self):
        """Main polling loop"""
        while self.running:
            try:
                self._poll_order_statuses()
                time.sleep(self.poll_interval)
            except Exception as e:
                log.error(f"Error in order status polling: {e}")
                time.sleep(self.poll_interval)
    
    def _poll_order_statuses(self):
        """Poll order statuses from exchange"""
        try:
            # Get all open orders from exchange
            open_orders = self._get_open_orders()
            
            with self.lock:
                # Check each order for status changes
                for order_data in open_orders:
                    order_id = str(order_data.get('id', ''))
                    # Delta Exchange uses 'state' instead of 'status'
                    current_status = order_data.get('state', 'unknown')
                    
                    # Check if status changed
                    if order_id in self.order_statuses:
                        old_status = self.order_statuses[order_id].status
                        if old_status != current_status:
                            log.info(f"🔄 Order {order_id} status changed: {old_status} → {current_status}")
                            
                            # Update order status
                            self._update_order_status(order_id, order_data)
                            
                            # Notify fill if order was filled
                            if current_status == 'filled':
                                self._notify_fill(order_id, order_data)
                    else:
                        # New order detected
                        log.info(f"🆕 New order detected: {order_id} ({current_status})")
                        self._update_order_status(order_id, order_data)
                        
                        if current_status == 'filled':
                            self._notify_fill(order_id, order_data)
                            
        except Exception as e:
            log.error(f"Error polling order statuses: {e}")
    
    def _get_open_orders(self) -> List[Dict]:
        """Get open orders from exchange"""
        try:
            # Check tracked orders individually
            orders = []
            with self.lock:
                for order_id in list(self.order_statuses.keys()):
                    try:
                        # Get order status from exchange
                        order_data = self._get_order_status(order_id)
                        if order_data:
                            orders.append(order_data)
                    except Exception as e:
                        log.debug(f"Error checking order {order_id}: {e}")
            return orders
        except Exception as e:
            log.error(f"Error fetching open orders: {e}")
            return []
    
    def _get_order_status(self, order_id: str) -> Optional[Dict]:
        """Get status of a specific order from exchange"""
        try:
            # Use delta client to get order details
            if hasattr(self.delta_client, 'get_order'):
                response = self.delta_client.get_order(order_id)
                if response and response.get('success'):
                    order_data = response['result']
                    # Ensure we have the right field names
                    if 'state' not in order_data and 'status' in order_data:
                        order_data['state'] = order_data['status']
                    return order_data
            return None
        except Exception as e:
            log.debug(f"Error fetching order {order_id}: {e}")
            return None
    
    def _fetch_orders_via_api(self) -> List[Dict]:
        """Fetch orders via direct API call"""
        try:
            # This would need proper authentication
            # For now, return empty list
            log.warning("Direct API fallback not implemented yet")
            return []
        except Exception as e:
            log.error(f"Error in API fallback: {e}")
            return []
    
    def _update_order_status(self, order_id: str, order_data: Dict):
        """Update order status in memory"""
        try:
            # Debug: log the order data structure
            log.debug(f"Order {order_id} data: {order_data}")
            
            status = OrderStatus(
                order_id=order_id,
                status=order_data.get('state', 'unknown'),  # Use 'state' field
                filled_size=float(order_data.get('filled_size', 0)),
                remaining_size=float(order_data.get('remaining_size', 0)),
                average_price=float(order_data.get('average_price')) if order_data.get('average_price') else None,
                last_updated=datetime.now(timezone.utc)
            )
            
            self.order_statuses[order_id] = status
            log.debug(f"Updated order {order_id}: {status.status}")
            
        except Exception as e:
            log.error(f"Error updating order status for {order_id}: {e}")
    
    def _notify_fill(self, order_id: str, order_data: Dict):
        """Notify all callbacks about order fill"""
        try:
            fill_data = {
                'order_id': order_id,
                'status': 'filled',
                'filled_size': float(order_data.get('filled_size', 0)),
                'average_price': float(order_data.get('average_price')) if order_data.get('average_price') else None,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            # Call all registered callbacks
            for callback in self.fill_callbacks:
                try:
                    callback(fill_data)
                except Exception as e:
                    log.error(f"Error in fill callback {callback.__name__}: {e}")
            
            log.info(f"✅ Order {order_id} FILLED: {fill_data['filled_size']} @ {fill_data['average_price']}")
            
        except Exception as e:
            log.error(f"Error notifying fill for order {order_id}: {e}")
    
    def get_order_status(self, order_id: str) -> Optional[OrderStatus]:
        """Get current status of an order"""
        with self.lock:
            return self.order_statuses.get(order_id)
    
    def get_all_orders(self) -> Dict[str, OrderStatus]:
        """Get all tracked orders"""
        with self.lock:
            return self.order_statuses.copy()
    
    def add_order(self, order_id: str, initial_status: str = 'open'):
        """Add an order to tracking"""
        with self.lock:
            if order_id not in self.order_statuses:
                self.order_statuses[order_id] = OrderStatus(
                    order_id=order_id,
                    status=initial_status,
                    filled_size=0.0,
                    remaining_size=1.0,  # Default, will be updated on first poll
                    average_price=None,
                    last_updated=datetime.now(timezone.utc)
                )
                log.info(f"📝 Added order {order_id} to tracking")
    
    def remove_order(self, order_id: str):
        """Remove an order from tracking"""
        with self.lock:
            if order_id in self.order_statuses:
                del self.order_statuses[order_id]
                log.info(f"🗑️ Removed order {order_id} from tracking")
    
    def is_running(self) -> bool:
        """Check if polling is running"""
        return self.running
    
    def get_stats(self) -> Dict:
        """Get polling statistics"""
        with self.lock:
            total_orders = len(self.order_statuses)
            open_orders = sum(1 for o in self.order_statuses.values() if o.status == 'open')
            filled_orders = sum(1 for o in self.order_statuses.values() if o.status == 'filled')
            
            return {
                'total_orders': total_orders,
                'open_orders': open_orders,
                'filled_orders': filled_orders,
                'poll_interval': self.poll_interval,
                'running': self.running
            }


# Global poller instance
_order_poller = None

def get_order_poller(delta_client=None, poll_interval: float = 5.0) -> OrderStatusPoller:
    """Get or create global order poller instance"""
    global _order_poller
    
    if _order_poller is None and delta_client is not None:
        _order_poller = OrderStatusPoller(delta_client, poll_interval)
        log.info("🌐 Global order poller created")
    
    return _order_poller

def start_order_polling(delta_client, poll_interval: float = 5.0):
    """Start global order polling"""
    global _order_poller
    
    if _order_poller is None:
        _order_poller = OrderStatusPoller(delta_client, poll_interval)
    
    _order_poller.start_polling()
    return _order_poller

def stop_order_polling():
    """Stop global order polling"""
    global _order_poller
    
    if _order_poller:
        _order_poller.stop_polling()

def add_fill_callback(callback: Callable):
    """Add fill callback to global poller"""
    global _order_poller
    
    if _order_poller:
        _order_poller.add_fill_callback(callback)
    else:
        log.warning("Order poller not initialized, callback not added")
