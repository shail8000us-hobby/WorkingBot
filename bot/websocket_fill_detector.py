"""
Robust WebSocket Fill Detection for Delta Exchange
Handles fill notifications with reconnection and fallback mechanisms
Works on both testnet and live trading environments
"""

import time
import logging
import threading
import json
import websocket
import sys
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config

log = logging.getLogger(__name__)

@dataclass
class FillEvent:
    """Fill event data"""
    order_id: str
    symbol: str
    side: str  # buy or sell
    size: float
    price: float
    timestamp: datetime
    fill_id: str
    role: str  # maker or taker

class WebSocketFillDetector:
    """
    Robust WebSocket fill detection for Delta Exchange
    Handles reconnections and provides fallback mechanisms
    """
    
    def __init__(self, delta_client, reconnect_interval: float = 5.0):
        """
        Initialize WebSocket fill detector
        
        Args:
            delta_client: Delta Exchange client instance
            reconnect_interval: Reconnection interval in seconds
        """
        self.delta_client = delta_client
        self.reconnect_interval = reconnect_interval
        self.ws = None
        self.running = False
        self.reconnect_thread = None
        self.fill_callbacks: List[Callable] = []
        self.lock = threading.RLock()
        
        # WebSocket configuration
        self.ws_url = self._get_websocket_url()
        self.subscribed_channels = []
        
        # Reconnection settings
        self.max_reconnect_attempts = 10
        self.reconnect_attempts = 0
        self.last_heartbeat = time.time()
        self.heartbeat_timeout = 30.0  # 30 seconds
        
        log.info(f"✅ WebSocket Fill Detector initialized (URL: {self.ws_url})")
    
    def _get_websocket_url(self) -> str:
        """Get WebSocket URL from YAML configuration based on trading mode"""
        cfg = get_config()
        if cfg.safety.trading_mode == 'demo':
            return cfg.api.demo.websocket_url
        else:
            return cfg.api.live.websocket_url
    
    def add_fill_callback(self, callback: Callable):
        """Add callback function for fill notifications"""
        with self.lock:
            self.fill_callbacks.append(callback)
            log.debug(f"Added fill callback: {callback.__name__}")
    
    def start(self):
        """Start WebSocket connection and fill detection"""
        if self.running:
            log.warning("WebSocket fill detection already running")
            return
        
        self.running = True
        self._connect()
        
        # Start reconnection monitoring
        self.reconnect_thread = threading.Thread(target=self._reconnect_loop, daemon=True)
        self.reconnect_thread.start()
        
        log.info("🔄 WebSocket fill detection started")
    
    def stop(self):
        """Stop WebSocket connection and fill detection"""
        self.running = False
        
        if self.ws:
            self.ws.close()
            self.ws = None
        
        if self.reconnect_thread:
            self.reconnect_thread.join(timeout=2)
        
        log.info("⏹️ WebSocket fill detection stopped")
    
    def _connect(self):
        """Establish WebSocket connection"""
        try:
            log.info(f"🔌 Connecting to WebSocket: {self.ws_url}")
            
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            
            # Start WebSocket in a separate thread
            ws_thread = threading.Thread(target=self.ws.run_forever, daemon=True)
            ws_thread.start()
            
            # Wait for connection
            time.sleep(1)
            
        except Exception as e:
            log.error(f"Error connecting to WebSocket: {e}")
            self._schedule_reconnect()
    
    def _on_open(self, ws):
        """Handle WebSocket connection open"""
        log.info("✅ WebSocket connected")
        self.reconnect_attempts = 0
        self.last_heartbeat = time.time()
        
        # Subscribe to user trades channel
        self._subscribe_to_user_trades()
    
    def _on_message(self, ws, message):
        """Handle WebSocket messages"""
        try:
            data = json.loads(message)
            self.last_heartbeat = time.time()
            
            # Handle different message types
            if data.get('type') == 'v2/user_trades':
                self._handle_user_trades(data)
            elif data.get('type') == 'pong':
                log.debug("Received pong")
            elif data.get('type') == 'subscription':
                log.info(f"✅ Subscribed to: {data.get('channel')}")
            else:
                log.debug(f"Received message: {data.get('type', 'unknown')}")
                
        except Exception as e:
            log.error(f"Error processing WebSocket message: {e}")
    
    def _on_error(self, ws, error):
        """Handle WebSocket errors"""
        log.error(f"WebSocket error: {error}")
        self._schedule_reconnect()
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close"""
        log.warning(f"WebSocket closed: {close_status_code} - {close_msg}")
        self._schedule_reconnect()
    
    def _subscribe_to_user_trades(self):
        """Subscribe to user trades channel"""
        try:
            subscribe_msg = {
                "type": "subscribe",
                "channels": [
                    {
                        "name": "v2/user_trades",
                        "symbols": ["BTCUSD"]  # Add more symbols as needed
                    }
                ]
            }
            
            self.ws.send(json.dumps(subscribe_msg))
            log.info("📡 Subscribed to v2/user_trades channel")
            
        except Exception as e:
            log.error(f"Error subscribing to user trades: {e}")
    
    def _handle_user_trades(self, data):
        """Handle user trades messages"""
        try:
            trades = data.get('trades', [])
            
            for trade in trades:
                # Extract trade information
                fill_event = FillEvent(
                    order_id=str(trade.get('o', '')),  # order_id
                    symbol=trade.get('sy', ''),        # symbol
                    side=trade.get('S', ''),           # side
                    size=float(trade.get('s', 0)),     # size
                    price=float(trade.get('p', 0)),    # price
                    timestamp=datetime.now(timezone.utc),
                    fill_id=trade.get('f', ''),        # fill_id
                    role=trade.get('r', '')            # role (maker/taker)
                )
                
                # Notify callbacks
                self._notify_fill(fill_event)
                
                log.info(f"✅ Fill detected: {fill_event.symbol} {fill_event.side} {fill_event.size} @ {fill_event.price} (Order: {fill_event.order_id})")
                
        except Exception as e:
            log.error(f"Error handling user trades: {e}")
    
    def _notify_fill(self, fill_event: FillEvent):
        """Notify all callbacks about fill"""
        try:
            fill_data = {
                'order_id': fill_event.order_id,
                'symbol': fill_event.symbol,
                'side': fill_event.side,
                'size': fill_event.size,
                'price': fill_event.price,
                'timestamp': fill_event.timestamp.isoformat(),
                'fill_id': fill_event.fill_id,
                'role': fill_event.role
            }
            
            # Call all registered callbacks
            for callback in self.fill_callbacks:
                try:
                    callback(fill_data)
                except Exception as e:
                    log.error(f"Error in fill callback {callback.__name__}: {e}")
                    
        except Exception as e:
            log.error(f"Error notifying fill: {e}")
    
    def _reconnect_loop(self):
        """Reconnection monitoring loop"""
        while self.running:
            try:
                # Check if connection is stale
                if (self.ws is None or 
                    time.time() - self.last_heartbeat > self.heartbeat_timeout):
                    
                    if self.reconnect_attempts < self.max_reconnect_attempts:
                        log.warning(f"🔄 Attempting reconnection ({self.reconnect_attempts + 1}/{self.max_reconnect_attempts})")
                        self._connect()
                        self.reconnect_attempts += 1
                    else:
                        log.error("❌ Max reconnection attempts reached, stopping")
                        self.running = False
                        break
                
                time.sleep(self.reconnect_interval)
                
            except Exception as e:
                log.error(f"Error in reconnection loop: {e}")
                time.sleep(self.reconnect_interval)
    
    def _schedule_reconnect(self):
        """Schedule reconnection attempt"""
        if self.running and self.reconnect_attempts < self.max_reconnect_attempts:
            log.info(f"🔄 Scheduling reconnection in {self.reconnect_interval}s")
            self.reconnect_attempts += 1
    
    def send_ping(self):
        """Send ping to keep connection alive"""
        try:
            if self.ws:
                self.ws.send(json.dumps({"type": "ping"}))
                log.debug("Sent ping")
        except Exception as e:
            log.error(f"Error sending ping: {e}")
    
    def is_connected(self) -> bool:
        """Check if WebSocket is connected"""
        return (self.ws is not None and 
                time.time() - self.last_heartbeat < self.heartbeat_timeout)
    
    def get_stats(self) -> Dict:
        """Get WebSocket statistics"""
        with self.lock:
            return {
                'connected': self.is_connected(),
                'reconnect_attempts': self.reconnect_attempts,
                'last_heartbeat': self.last_heartbeat,
                'callbacks_count': len(self.fill_callbacks),
                'running': self.running
            }


# Global fill detector instance
_fill_detector = None

def get_fill_detector(delta_client=None, reconnect_interval: float = 5.0) -> WebSocketFillDetector:
    """Get or create global fill detector instance"""
    global _fill_detector
    
    if _fill_detector is None and delta_client is not None:
        _fill_detector = WebSocketFillDetector(delta_client, reconnect_interval)
        log.info("🌐 Global fill detector created")
    
    return _fill_detector

def start_fill_detection(delta_client, reconnect_interval: float = 5.0):
    """Start global fill detection"""
    global _fill_detector
    
    if _fill_detector is None:
        _fill_detector = WebSocketFillDetector(delta_client, reconnect_interval)
    
    _fill_detector.start()
    return _fill_detector

def stop_fill_detection():
    """Stop global fill detection"""
    global _fill_detector
    
    if _fill_detector:
        _fill_detector.stop()

def add_fill_callback(callback: Callable):
    """Add fill callback to global detector"""
    global _fill_detector
    
    if _fill_detector:
        _fill_detector.add_fill_callback(callback)
    else:
        log.warning("Fill detector not initialized, callback not added")
