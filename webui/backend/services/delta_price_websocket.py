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
    
    def __init__(self, on_price_update: Optional[Callable] = None, on_ticker_update: Optional[Callable] = None):
        """
        Initialize WebSocket client
        
        Args:
            on_price_update: Callback function(symbol, price) called on price updates
            on_ticker_update: Callback function(symbol, ticker_data) called on ticker updates (bid/ask)
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
        
        # Options ticker subscriptions (symbol -> True)
        self.subscribed_options: Dict[str, bool] = {}
        self.subscribed_options_lock = threading.Lock()
        
        # Callbacks
        self.on_price_update = on_price_update
        self.on_ticker_update = on_ticker_update
        
        # Reconnection settings
        self.reconnect_delay = 5  # seconds
        self.max_reconnect_attempts = 10
        self.reconnect_attempts = 0
        
    def on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            
            # Handle spot price updates (BTC/ETH index)
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
            
            # Handle v2/ticker updates (options bid/ask)
            elif data.get('type') == 'v2/ticker':
                symbol = data.get('symbol')
                if not symbol:
                    return
                
                # Extract ticker data
                ticker_data = {
                    'symbol': symbol,
                    'best_bid': float(data.get('best_bid_price', 0) or 0),
                    'best_ask': float(data.get('best_ask_price', 0) or 0),
                    'mark_price': float(data.get('mark_price', 0) or 0),
                    'timestamp': time.time()
                }
                
                # Trigger ticker callback
                if self.on_ticker_update:
                    try:
                        self.on_ticker_update(symbol, ticker_data)
                    except Exception as e:
                        log.error(f"[DeltaWS] Error in ticker update callback: {e}")
                        
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
        
        # Re-subscribe to any options tickers
        with self.subscribed_options_lock:
            if self.subscribed_options:
                self._subscribe_to_options_tickers(list(self.subscribed_options.keys()))
    
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
            'reconnect_attempts': self.reconnect_attempts,
            'subscribed_options': list(self.subscribed_options.keys())
        }
    
    def _subscribe_to_options_tickers(self, symbols: list):
        """
        Internal method to subscribe to options ticker updates
        
        Args:
            symbols: List of option symbols to subscribe to (e.g., ['BTC-29MAR24-65000-C', ...])
        """
        if not symbols or not self.ws or not self.connected:
            return
        
        subscribe_message = {
            "type": "subscribe",
            "payload": {
                "channels": [
                    {
                        "name": "v2/ticker",
                        "symbols": symbols
                    }
                ]
            }
        }
        
        try:
            self.ws.send(json.dumps(subscribe_message))
            log.info(f"[DeltaWS] Subscribed to {len(symbols)} options tickers")
        except Exception as e:
            log.error(f"[DeltaWS] Error subscribing to options tickers: {e}")
    
    def subscribe_options(self, symbols: list):
        """
        Subscribe to real-time ticker updates for options
        
        Args:
            symbols: List of option symbols to subscribe to (e.g., ['BTC-29MAR24-65000-C', ...])
        """
        if not symbols:
            return
        
        with self.subscribed_options_lock:
            # Add to subscribed set
            for symbol in symbols:
                self.subscribed_options[symbol] = True
            
            # Subscribe if connected
            if self.connected:
                self._subscribe_to_options_tickers(symbols)
            else:
                log.warning(f"[DeltaWS] Not connected, will subscribe to {len(symbols)} options when connected")
    
    def unsubscribe_options(self, symbols: list):
        """
        Unsubscribe from options ticker updates
        
        Args:
            symbols: List of option symbols to unsubscribe from
        """
        if not symbols or not self.ws or not self.connected:
            return
        
        with self.subscribed_options_lock:
            # Remove from subscribed set
            for symbol in symbols:
                self.subscribed_options.pop(symbol, None)
        
        unsubscribe_message = {
            "type": "unsubscribe",
            "payload": {
                "channels": [
                    {
                        "name": "v2/ticker",
                        "symbols": symbols
                    }
                ]
            }
        }
        
        try:
            self.ws.send(json.dumps(unsubscribe_message))
            log.info(f"[DeltaWS] Unsubscribed from {len(symbols)} options tickers")
        except Exception as e:
            log.error(f"[DeltaWS] Error unsubscribing from options tickers: {e}")


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
        # Update Alert Monitor (Sync with Live Price Widget)
        if symbol == 'BTC':
            try:
                # Ensure backend is in path to match alert_routes import context
                from pathlib import Path
                import sys
                backend_dir = str(Path(__file__).parent.parent)
                if backend_dir not in sys.path:
                    sys.path.insert(0, backend_dir)
                
                from services.price_alert_monitor import get_price_alert_monitor
                get_price_alert_monitor().update_price(price)
            except Exception as e:
                log.error(f"[DeltaWS] Failed to update alert monitor: {e}")

        try:
            socketio_instance.emit('market_price_update', {
                'symbol': symbol,
                'price': price,
                'timestamp': time.time()
            })
        except Exception as e:
            log.error(f"[DeltaWS] Error broadcasting price: {e}")
    
    # Set up callback to broadcast ticker updates (bid/ask)
    def broadcast_ticker(symbol: str, ticker_data: dict):
        try:
            socketio_instance.emit('options_ticker_update', {
                'symbol': symbol,
                'best_bid': ticker_data['best_bid'],
                'best_ask': ticker_data['best_ask'],
                'mark_price': ticker_data['mark_price'],
                'timestamp': ticker_data['timestamp']
            })
        except Exception as e:
            log.error(f"[DeltaWS] Error broadcasting ticker: {e}")
    
    price_ws.on_price_update = broadcast_price
    price_ws.on_ticker_update = broadcast_ticker
    price_ws.start()
    
    log.info("[DeltaWS] Price broadcast service started")
    return price_ws
