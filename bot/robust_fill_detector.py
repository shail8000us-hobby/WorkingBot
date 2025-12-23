"""
Robust Fill Detection Manager for Delta Exchange
Combines WebSocket, polling, and position sync for maximum reliability
Works on both testnet and live trading environments
"""

import time
import logging
import threading
from typing import Dict, List, Optional, Callable
from datetime import datetime, timezone
import os

from .order_status_poller import OrderStatusPoller, get_order_poller
from .position_synchronizer import PositionSynchronizer, get_position_synchronizer
from .websocket_fill_detector import WebSocketFillDetector, get_fill_detector

log = logging.getLogger(__name__)

class RobustFillDetector:
    """
    Unified fill detection system combining multiple methods
    Provides maximum reliability for both testnet and live trading
    """
    
    def __init__(self, delta_client, 
                 poll_interval: float = 5.0,
                 sync_interval: float = 30.0,
                 websocket_reconnect_interval: float = 5.0):
        """
        Initialize robust fill detector
        
        Args:
            delta_client: Delta Exchange client instance
            poll_interval: Order polling interval in seconds
            sync_interval: Position sync interval in seconds
            websocket_reconnect_interval: WebSocket reconnection interval
        """
        self.delta_client = delta_client
        self.running = False
        
        # Initialize components
        self.order_poller = OrderStatusPoller(delta_client, poll_interval)
        self.position_sync = PositionSynchronizer(delta_client, sync_interval)
        self.websocket_detector = WebSocketFillDetector(delta_client, websocket_reconnect_interval)
        
        # Unified callbacks
        self.fill_callbacks: List[Callable] = []
        self.lock = threading.RLock()
        
        # Statistics
        self.stats = {
            'websocket_fills': 0,
            'polling_fills': 0,
            'sync_fills': 0,
            'total_fills': 0,
            'start_time': None
        }
        
        # Register internal callbacks
        self._register_internal_callbacks()
        
        log.info("✅ Robust Fill Detector initialized")
    
    def _register_internal_callbacks(self):
        """Register internal callbacks for unified handling"""
        # WebSocket fill callback
        self.websocket_detector.add_fill_callback(self._handle_websocket_fill)
        
        # Order poller fill callback
        self.order_poller.add_fill_callback(self._handle_polling_fill)
    
    def add_fill_callback(self, callback: Callable):
        """Add unified fill callback"""
        with self.lock:
            self.fill_callbacks.append(callback)
            log.debug(f"Added unified fill callback: {callback.__name__}")
    
    def start(self):
        """Start all fill detection methods"""
        if self.running:
            log.warning("Robust fill detection already running")
            return
        
        self.running = True
        self.stats['start_time'] = datetime.now(timezone.utc)
        
        # Start all components
        self.order_poller.start_polling()
        self.position_sync.start_sync()
        # WebSocket detector disabled temporarily due to 403 errors (polling is sufficient)
        # self.websocket_detector.start()
        
        log.info("🚀 Robust fill detection started (Polling + Position Sync)")
    
    def stop(self):
        """Stop all fill detection methods"""
        self.running = False
        
        # Stop all components
        self.order_poller.stop_polling()
        self.position_sync.stop_sync()
        self.websocket_detector.stop()
        
        log.info("⏹️ Robust fill detection stopped")
    
    def _handle_websocket_fill(self, fill_data: Dict):
        """Handle WebSocket fill detection"""
        try:
            with self.lock:
                self.stats['websocket_fills'] += 1
                self.stats['total_fills'] += 1
            
            log.info(f"🔔 WebSocket fill: Order {fill_data['order_id']} filled")
            self._notify_unified_fill(fill_data, 'websocket')
            
        except Exception as e:
            log.error(f"Error handling WebSocket fill: {e}")
    
    def _handle_polling_fill(self, fill_data: Dict):
        """Handle polling fill detection"""
        try:
            with self.lock:
                self.stats['polling_fills'] += 1
                self.stats['total_fills'] += 1
            
            log.info(f"🔔 Polling fill: Order {fill_data['order_id']} filled")
            self._notify_unified_fill(fill_data, 'polling')
            
        except Exception as e:
            log.error(f"Error handling polling fill: {e}")
    
    def _notify_unified_fill(self, fill_data: Dict, source: str):
        """Notify all callbacks about fill with source information"""
        try:
            # Add source information
            fill_data['detection_source'] = source
            fill_data['detection_time'] = datetime.now(timezone.utc).isoformat()
            
            # Call all registered callbacks
            for callback in self.fill_callbacks:
                try:
                    callback(fill_data)
                except Exception as e:
                    log.error(f"Error in unified fill callback {callback.__name__}: {e}")
                    
        except Exception as e:
            log.error(f"Error notifying unified fill: {e}")
    
    def force_sync(self):
        """Force immediate synchronization"""
        log.info("🔄 Forcing immediate synchronization...")
        self.position_sync.force_sync()
    
    def get_stats(self) -> Dict:
        """Get comprehensive statistics"""
        with self.lock:
            websocket_stats = self.websocket_detector.get_stats()
            polling_stats = self.order_poller.get_stats()
            sync_stats = self.position_sync.get_stats()
            
            uptime = None
            if self.stats['start_time']:
                uptime = (datetime.now(timezone.utc) - self.stats['start_time']).total_seconds()
            
            return {
                'running': self.running,
                'uptime_seconds': uptime,
                'fill_stats': self.stats.copy(),
                'websocket': websocket_stats,
                'polling': polling_stats,
                'position_sync': sync_stats
            }
    
    def get_health_status(self) -> Dict:
        """Get health status of all components"""
        websocket_connected = self.websocket_detector.is_connected()
        polling_running = self.order_poller.is_running()
        sync_running = self.position_sync.running
        
        overall_health = 'healthy' if (websocket_connected or polling_running) else 'degraded'
        
        return {
            'overall_health': overall_health,
            'websocket_connected': websocket_connected,
            'polling_active': polling_running,
            'sync_active': sync_running,
            'redundancy_level': 'high' if (websocket_connected and polling_running) else 'medium' if polling_running else 'low'
        }
    
    def add_order(self, order_id: str):
        """Add order to tracking"""
        self.order_poller.add_order(order_id)
        log.info(f"📝 Added order {order_id} to tracking")
    
    def remove_order(self, order_id: str):
        """Remove order from tracking"""
        self.order_poller.remove_order(order_id)
        log.info(f"🗑️ Removed order {order_id} from tracking")
    
    def get_positions(self):
        """Get current positions"""
        return self.position_sync.get_positions()
    
    def get_order_status(self, order_id: str):
        """Get order status"""
        return self.order_poller.get_order_status(order_id)


# Global robust fill detector instance
_robust_detector = None

def get_robust_fill_detector(delta_client=None, 
                           poll_interval: float = 5.0,
                           sync_interval: float = 30.0,
                           websocket_reconnect_interval: float = 5.0) -> RobustFillDetector:
    """Get or create global robust fill detector instance"""
    global _robust_detector
    
    if _robust_detector is None and delta_client is not None:
        _robust_detector = RobustFillDetector(
            delta_client, 
            poll_interval, 
            sync_interval, 
            websocket_reconnect_interval
        )
        log.info("🌐 Global robust fill detector created")
    
    return _robust_detector

def start_robust_fill_detection(delta_client, 
                              poll_interval: float = 5.0,
                              sync_interval: float = 30.0,
                              websocket_reconnect_interval: float = 5.0):
    """Start global robust fill detection"""
    global _robust_detector
    
    if _robust_detector is None:
        _robust_detector = RobustFillDetector(
            delta_client, 
            poll_interval, 
            sync_interval, 
            websocket_reconnect_interval
        )
    
    _robust_detector.start()
    return _robust_detector

def stop_robust_fill_detection():
    """Stop global robust fill detection"""
    global _robust_detector
    
    if _robust_detector:
        _robust_detector.stop()

def add_fill_callback(callback: Callable):
    """Add fill callback to global detector"""
    global _robust_detector
    
    if _robust_detector:
        _robust_detector.add_fill_callback(callback)
    else:
        log.warning("Robust fill detector not initialized, callback not added")

def force_sync():
    """Force immediate synchronization"""
    global _robust_detector
    
    if _robust_detector:
        _robust_detector.force_sync()

def get_health_status():
    """Get health status"""
    global _robust_detector
    
    if _robust_detector:
        return _robust_detector.get_health_status()
    else:
        return {'overall_health': 'not_initialized'}
