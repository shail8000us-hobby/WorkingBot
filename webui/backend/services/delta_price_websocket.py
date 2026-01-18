"""
Delta Exchange WebSocket Price Service

Connects to Delta Exchange WebSocket API to fetch real-time BTC and ETH index prices.
Broadcasts prices to frontend clients via Socket.IO.

Created: January 18, 2026
Author: SSR Bot
"""

import json
import logging
import time
import threading
from typing import Dict, Optional, Callable
import websocket

log = logging.getLogger(__name__)

class DeltaPriceWebSocket:
    """
    WebSocket client for Delta Exchange index prices
    
    Subscribes to real-time spot price feeds for BTC (.DEXBTUSD) and ETH (.DEETHUSD)
    and broadcasts updates via callback.
    """
    
    # Delta Exchange India WebSocket URL
    WS_URL = 'wss://socket.india.delta.exchange'
    
    # Index symbols for Delta Exchange India
    BTC_INDEX = '.DEXBTUSD'
    ETH_INDEX = '.DEETHUSD'
    
    def __init__(self, on_price_update: Optional[Callable] = None):
        """
        Initialize WebSocket client
        
        Args:
            on_price_update: Callback function(symbol, price) called on price updates
        """
        self.ws: Optional[websocket.WebSocketApp] = None
        self.ws_thread: Optional[threading.Thread] = None
        self.running = False
        self.connected = False
        
        # Price storage
        self.prices: Dict[str, float] = {
            'BTC': 0.0,
            'ETH': 0.0
        }
        self.last_update: Dict[str, float] = {
            'BTC': 0.0,
            'ETH': 0.0
        }
        
        # Callback for price updates
        self.on_price_update = on_price_update
        
        # Reconnection settings
        self.reconnect_delay = 5  # seconds
        self.max_reconnect_attempts = 10
        self.reconnect_attempts = 0
        
    def on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            
            # Check if it's a spot price update
            if data.get('type') == 'v2/spot_price':
                symbol = data.get('s')  # Delta API uses 's' for symbol (not 'symbol')
                price = data.get('p')   # Delta API uses 'p' for price (not 'price')
                
                if not symbol or price is None:  # Check for None to allow 0 price
                    return
                    
                # Map Delta symbols to our symbols
                if symbol == self.BTC_INDEX:
                    asset = 'BTC'
                elif symbol == self.ETH_INDEX:
                    asset = 'ETH'
                else:
                    return
                
                # Update price (safe float conversion)
                price = float(price)
                self.prices[asset] = price
                self.last_update[asset] = time.time()
                
                log.info(f"[DeltaWS] {asset} price update: ${price:,.2f}")
                
                # Trigger callback
                if self.on_price_update:
                    try:
                        self.on_price_update(asset, price)
                    except Exception as e:
                        log.error(f"[DeltaWS] Error in price update callback: {e}")
                        
        except json.JSONDecodeError as e:
            log.error(f"[DeltaWS] Error decoding message: {e}")
        except Exception as e:
            log.error(f"[DeltaWS] Error processing message: {e}", exc_info=True)
    
    def on_error(self, ws, error):
        """Handle WebSocket errors"""
        log.error(f"[DeltaWS] WebSocket Error: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close"""
        self.connected = False
        log.warning(f"[DeltaWS] Connection closed - Status: {close_status_code}, Message: {close_msg}")
        
        # Attempt reconnection if still running
        if self.running and self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            log.info(f"[DeltaWS] Attempting reconnection ({self.reconnect_attempts}/{self.max_reconnect_attempts}) in {self.reconnect_delay}s...")
            time.sleep(self.reconnect_delay)
            if self.running:
                self._connect()
    
    def on_open(self, ws):
        """Subscribe to spot price channels when connection opens"""
        self.connected = True
        self.reconnect_attempts = 0
        log.info("[DeltaWS] Connection established")
        
        # Subscribe to BTC and ETH spot price feeds
        subscribe_message = {
            "type": "subscribe",
            "payload": {
                "channels": [
                    {
                        "name": "v2/spot_price",
                        "symbols": [self.BTC_INDEX, self.ETH_INDEX]
                    }
                ]
            }
        }
        
        try:
            ws.send(json.dumps(subscribe_message))
            log.info(f"[DeltaWS] Subscribed to {self.BTC_INDEX} and {self.ETH_INDEX} spot price feeds")
        except Exception as e:
            log.error(f"[DeltaWS] Error sending subscription: {e}")
    
    def _connect(self):
        """Internal method to create and start WebSocket connection"""
        try:
            websocket.enableTrace(False)
            
            self.ws = websocket.WebSocketApp(
                self.WS_URL,
                on_open=self.on_open,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close
            )
            
            # Run WebSocket connection (blocking call)
            self.ws.run_forever(
                ping_interval=30,
                ping_timeout=10,
                reconnect=5  # Auto-reconnect after 5 seconds on disconnect
            )
            
        except Exception as e:
            log.error(f"[DeltaWS] Error in WebSocket connection: {e}", exc_info=True)
            self.connected = False
    
    def start(self):
        """Start the WebSocket connection in a background thread"""
        if self.running:
            log.warning("[DeltaWS] WebSocket already running")
            return
        
        self.running = True
        self.reconnect_attempts = 0
        
        # Start WebSocket in a daemon thread
        self.ws_thread = threading.Thread(target=self._connect, daemon=True)
        self.ws_thread.start()
        
        log.info("[DeltaWS] WebSocket service started")
    
    def stop(self):
        """Stop the WebSocket connection"""
        self.running = False
        
        if self.ws:
            try:
                self.ws.close()
            except Exception as e:
                log.error(f"[DeltaWS] Error closing WebSocket: {e}")
        
        log.info("[DeltaWS] WebSocket service stopped")
    
    def get_price(self, symbol: str) -> Optional[float]:
        """
        Get latest price for a symbol
        
        Args:
            symbol: 'BTC' or 'ETH'
            
        Returns:
            Latest price or None if not available
        """
        if symbol in self.prices and self.prices[symbol] > 0:
            return self.prices[symbol]
        return None
    
    def get_all_prices(self) -> Dict[str, float]:
        """Get all latest prices"""
        return self.prices.copy()
    
    def is_connected(self) -> bool:
        """Check if WebSocket is connected"""
        return self.connected
    
    def get_status(self) -> Dict:
        """Get service status"""
        return {
            'connected': self.connected,
            'running': self.running,
            'prices': self.prices.copy(),
            'last_update': self.last_update.copy(),
            'reconnect_attempts': self.reconnect_attempts
        }


# Global instance
_price_ws: Optional[DeltaPriceWebSocket] = None


def get_price_websocket() -> DeltaPriceWebSocket:
    """Get global WebSocket instance (singleton)"""
    global _price_ws
    if _price_ws is None:
        _price_ws = DeltaPriceWebSocket()
    return _price_ws


def start_price_service(socketio_instance):
    """
    Start the price WebSocket service and connect it to Socket.IO
    
    Args:
        socketio_instance: Flask-SocketIO instance for broadcasting
    """
    price_ws = get_price_websocket()
    
    # Set up callback to broadcast prices via Socket.IO
    def broadcast_price(symbol: str, price: float):
        try:
            socketio_instance.emit('market_price_update', {
                'symbol': symbol,
                'price': price,
                'timestamp': time.time()
            })
        except Exception as e:
            log.error(f"[DeltaWS] Error broadcasting price: {e}")
    
    price_ws.on_price_update = broadcast_price
    price_ws.start()
    
    log.info("[DeltaWS] Price broadcast service started")
    return price_ws
