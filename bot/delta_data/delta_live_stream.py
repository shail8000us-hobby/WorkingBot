"""
Delta Exchange Live Data Streamer
=================================
Real-time OHLCV candle streaming via WebSocket.
Production-ready for Delta Exchange India API.

Author: WorkingBot
Version: 1.0.0
"""

import websocket
import json
import threading
import time
from typing import Callable, List, Dict, Optional, Any
from datetime import datetime
import logging
from queue import Queue, Empty
from dataclasses import dataclass, field
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """WebSocket connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CLOSED = "closed"


@dataclass
class StreamStats:
    """Statistics for streaming operations."""
    messages_received: int = 0
    candles_received: int = 0
    tickers_received: int = 0
    errors: int = 0
    reconnections: int = 0
    start_time: float = field(default_factory=time.time)
    last_message_time: float = 0
    
    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.start_time
    
    @property
    def messages_per_minute(self) -> float:
        uptime = self.uptime_seconds
        if uptime < 60:
            return self.messages_received
        return self.messages_received / (uptime / 60)


class DeltaLiveStreamer:
    """
    Real-time OHLCV data streaming from Delta Exchange WebSocket.
    
    Features:
    - Candlestick channel for real-time candle updates
    - Ticker channel for 24h OHLC and volume
    - Mark price channel for derivatives pricing
    - Automatic reconnection with exponential backoff
    - Message queue for async processing
    - Connection health monitoring
    
    Usage:
        def on_candle(candle):
            print(f"{candle['symbol']}: {candle['close']}")
        
        streamer = DeltaLiveStreamer(on_candle=on_candle)
        streamer.subscribe_candles(["BTCUSD", "ETHUSD"], "1m")
        streamer.start()
        
        # Keep running...
        time.sleep(3600)
        streamer.stop()
    """
    
    # WebSocket URLs
    WS_URL_PRODUCTION = "wss://socket.india.delta.exchange"
    WS_URL_TESTNET = "wss://socket-ind.testnet.deltaex.org"
    
    # Supported resolutions for candlesticks
    SUPPORTED_RESOLUTIONS = [
        "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "1d", "1w"
    ]
    
    # Connection settings
    PING_INTERVAL = 30
    PING_TIMEOUT = 10
    RECONNECT_DELAY_BASE = 5
    RECONNECT_DELAY_MAX = 300
    MAX_RECONNECT_ATTEMPTS = 100
    
    def __init__(
        self,
        on_candle: Optional[Callable[[Dict], None]] = None,
        on_ticker: Optional[Callable[[Dict], None]] = None,
        on_mark_price: Optional[Callable[[Dict], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_connect: Optional[Callable[[], None]] = None,
        on_disconnect: Optional[Callable[[str], None]] = None,
        testnet: bool = False,
        use_queue: bool = False
    ):
        """
        Initialize the live data streamer.
        
        Args:
            on_candle: Callback for candle updates
            on_ticker: Callback for ticker updates
            on_mark_price: Callback for mark price updates
            on_error: Callback for errors
            on_connect: Callback on successful connection
            on_disconnect: Callback on disconnection
            testnet: Use testnet environment
            use_queue: Use message queue instead of callbacks
        """
        self.ws_url = self.WS_URL_TESTNET if testnet else self.WS_URL_PRODUCTION
        self.testnet = testnet
        self.ws: Optional[websocket.WebSocketApp] = None
        self.ws_thread: Optional[threading.Thread] = None
        
        # Connection state
        self.state = ConnectionState.DISCONNECTED
        self.is_running = False
        self.reconnect_attempts = 0
        
        # Callbacks
        self.on_candle_callback = on_candle
        self.on_ticker_callback = on_ticker
        self.on_mark_price_callback = on_mark_price
        self.on_error_callback = on_error
        self.on_connect_callback = on_connect
        self.on_disconnect_callback = on_disconnect
        
        # Subscription tracking
        self.subscriptions: List[Dict] = []
        self._pending_subscriptions: List[Dict] = []
        
        # Message queue (optional)
        self.use_queue = use_queue
        self.message_queue: Queue = Queue() if use_queue else None
        
        # Statistics
        self.stats = StreamStats()
        
        # Health check
        self._health_check_thread: Optional[threading.Thread] = None
        self._last_pong_time = 0
        
        logger.info(f"Initialized DeltaLiveStreamer (testnet={testnet})")
        logger.info(f"WebSocket URL: {self.ws_url}")
    
    def _on_message(self, ws: websocket.WebSocket, message: str) -> None:
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(message)
            self.stats.messages_received += 1
            self.stats.last_message_time = time.time()
            
            message_type = data.get("type", "")
            
            # Handle candlestick updates
            if message_type.startswith("candlestick_"):
                self._handle_candle(data)
            
            # Handle ticker updates
            elif message_type == "v2/ticker":
                self._handle_ticker(data)
            
            # Handle mark price updates
            elif message_type == "mark_price":
                self._handle_mark_price(data)
            
            # Handle subscription confirmations
            elif message_type == "subscriptions":
                self._handle_subscription_response(data)
            
            # Handle pong
            elif message_type == "pong":
                self._last_pong_time = time.time()
                logger.debug("Received pong")
            
            # Log unknown message types
            else:
                logger.debug(f"Unhandled message type: {message_type}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message: {e}")
            self.stats.errors += 1
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            self.stats.errors += 1
            if self.on_error_callback:
                self.on_error_callback(str(e))
    
    def _handle_candle(self, data: Dict) -> None:
        """Process candlestick message."""
        candle = {
            "symbol": data.get("symbol"),
            "resolution": data.get("resolution"),
            "candle_start_time": data.get("candle_start_time"),
            "timestamp": datetime.now().isoformat(),
            "open": float(data.get("open", 0)),
            "high": float(data.get("high", 0)),
            "low": float(data.get("low", 0)),
            "close": float(data.get("close", 0)),
            "volume": float(data.get("volume", 0))
        }
        
        self.stats.candles_received += 1
        
        if self.use_queue:
            self.message_queue.put(("candle", candle))
        elif self.on_candle_callback:
            self.on_candle_callback(candle)
    
    def _handle_ticker(self, data: Dict) -> None:
        """Process ticker message."""
        ticker = {
            "symbol": data.get("symbol"),
            "product_id": data.get("product_id"),
            "timestamp": datetime.now().isoformat(),
            "open": float(data.get("open", 0)),
            "high": float(data.get("high", 0)),
            "low": float(data.get("low", 0)),
            "close": float(data.get("close", 0)),
            "volume": float(data.get("volume", 0)),
            "turnover": float(data.get("turnover", 0)),
            "turnover_usd": float(data.get("turnover_usd", 0)),
            "mark_price": data.get("mark_price"),
            "spot_price": data.get("spot_price"),
            "oi": data.get("oi"),  # Open interest
        }
        
        self.stats.tickers_received += 1
        
        if self.use_queue:
            self.message_queue.put(("ticker", ticker))
        elif self.on_ticker_callback:
            self.on_ticker_callback(ticker)
    
    def _handle_mark_price(self, data: Dict) -> None:
        """Process mark price message."""
        mark_price = {
            "symbol": data.get("symbol"),
            "product_id": data.get("product_id"),
            "timestamp": datetime.now().isoformat(),
            "price": data.get("price"),
            "implied_volatility": data.get("implied_volatility"),
            "delta": data.get("delta"),
            "gamma": data.get("gamma"),
            "theta": data.get("theta"),
            "vega": data.get("vega"),
            "rho": data.get("rho"),
        }
        
        if self.use_queue:
            self.message_queue.put(("mark_price", mark_price))
        elif self.on_mark_price_callback:
            self.on_mark_price_callback(mark_price)
    
    def _handle_subscription_response(self, data: Dict) -> None:
        """Process subscription confirmation."""
        channels = data.get("channels", [])
        logger.info(f"Subscription confirmed for {len(channels)} channel(s)")
        
        for channel in channels:
            name = channel.get("name")
            symbols = channel.get("symbols", [])
            
            if "error" in channel:
                logger.error(f"Subscription error for {name}: {channel['error']}")
            else:
                logger.info(f"  - {name}: {symbols}")
    
    def _on_error(self, ws: websocket.WebSocket, error: Exception) -> None:
        """Handle WebSocket errors."""
        error_msg = str(error)
        logger.error(f"WebSocket error: {error_msg}")
        self.stats.errors += 1
        
        if self.on_error_callback:
            self.on_error_callback(error_msg)
    
    def _on_close(
        self, 
        ws: websocket.WebSocket, 
        close_status_code: int, 
        close_msg: str
    ) -> None:
        """Handle WebSocket close."""
        logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
        self.state = ConnectionState.DISCONNECTED
        
        if self.on_disconnect_callback:
            self.on_disconnect_callback(close_msg or "Connection closed")
        
        # Attempt reconnection if still running
        if self.is_running:
            self._schedule_reconnect()
    
    def _on_open(self, ws: websocket.WebSocket) -> None:
        """Handle WebSocket connection open."""
        logger.info("WebSocket connected")
        self.state = ConnectionState.CONNECTED
        self.reconnect_attempts = 0
        self._last_pong_time = time.time()
        
        if self.on_connect_callback:
            self.on_connect_callback()
        
        # Subscribe to pending channels
        self._send_subscriptions()
    
    def _send_subscriptions(self) -> None:
        """Send all pending subscriptions."""
        if not self.subscriptions:
            return
        
        subscribe_msg = {
            "type": "subscribe",
            "payload": {
                "channels": self.subscriptions
            }
        }
        
        try:
            self.ws.send(json.dumps(subscribe_msg))
            logger.info(f"Sent subscription for {len(self.subscriptions)} channel(s)")
        except Exception as e:
            logger.error(f"Failed to send subscription: {e}")
    
    def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt with exponential backoff."""
        if self.reconnect_attempts >= self.MAX_RECONNECT_ATTEMPTS:
            logger.error("Max reconnection attempts reached. Stopping.")
            self.is_running = False
            return
        
        self.reconnect_attempts += 1
        self.stats.reconnections += 1
        self.state = ConnectionState.RECONNECTING
        
        # Exponential backoff with jitter
        delay = min(
            self.RECONNECT_DELAY_BASE * (2 ** (self.reconnect_attempts - 1)),
            self.RECONNECT_DELAY_MAX
        )
        
        logger.info(f"Reconnecting in {delay}s (attempt {self.reconnect_attempts})")
        
        def reconnect():
            time.sleep(delay)
            if self.is_running:
                self._connect()
        
        reconnect_thread = threading.Thread(target=reconnect, daemon=True)
        reconnect_thread.start()
    
    def _connect(self) -> None:
        """Establish WebSocket connection."""
        self.state = ConnectionState.CONNECTING
        
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )
        
        # Run WebSocket in thread
        self.ws_thread = threading.Thread(
            target=self.ws.run_forever,
            kwargs={
                "ping_interval": self.PING_INTERVAL,
                "ping_timeout": self.PING_TIMEOUT
            },
            daemon=True
        )
        self.ws_thread.start()
    
    def subscribe_candles(
        self, 
        symbols: List[str], 
        resolution: str = "1m"
    ) -> None:
        """
        Subscribe to candlestick updates.
        
        Args:
            symbols: List of symbols (e.g., ["BTCUSD", "ETHUSD"])
            resolution: Candle resolution (1m, 5m, 15m, 1h, etc.)
        """
        if resolution not in self.SUPPORTED_RESOLUTIONS:
            raise ValueError(f"Invalid resolution: {resolution}. "
                           f"Valid: {self.SUPPORTED_RESOLUTIONS}")
        
        channel = {
            "name": f"candlestick_{resolution}",
            "symbols": symbols
        }
        
        self.subscriptions.append(channel)
        logger.info(f"Added candlestick subscription: {resolution} for {symbols}")
        
        # Send immediately if connected
        if self.state == ConnectionState.CONNECTED and self.ws:
            self._send_subscriptions()
    
    def subscribe_mark_price(self, symbols: List[str]) -> None:
        """
        Subscribe to mark price updates.
        
        Args:
            symbols: List of symbols (e.g., ["BTCUSD", "ETHUSD"])
        """
        # Mark price symbols need MARK: prefix
        mark_symbols = [f"MARK:{s}" if not s.startswith("MARK:") else s 
                       for s in symbols]
        
        channel = {
            "name": "mark_price",
            "symbols": mark_symbols
        }
        
        self.subscriptions.append(channel)
        logger.info(f"Added mark price subscription for {mark_symbols}")
        
        if self.state == ConnectionState.CONNECTED and self.ws:
            self._send_subscriptions()
    
    def subscribe_ticker(self, symbols: List[str]) -> None:
        """
        Subscribe to ticker updates (24h OHLC, volume).
        
        Args:
            symbols: List of symbols or ["all"] for all products
        """
        channel = {
            "name": "v2/ticker",
            "symbols": symbols
        }
        
        self.subscriptions.append(channel)
        logger.info(f"Added ticker subscription for {symbols}")
        
        if self.state == ConnectionState.CONNECTED and self.ws:
            self._send_subscriptions()
    
    def subscribe_funding_rate(self, symbols: List[str]) -> None:
        """
        Subscribe to funding rate updates (perpetuals only).
        
        Args:
            symbols: List of perpetual futures symbols
        """
        channel = {
            "name": "funding_rate",
            "symbols": symbols
        }
        
        self.subscriptions.append(channel)
        logger.info(f"Added funding rate subscription for {symbols}")
        
        if self.state == ConnectionState.CONNECTED and self.ws:
            self._send_subscriptions()
    
    def unsubscribe(self, channel_name: str, symbols: Optional[List[str]] = None) -> None:
        """
        Unsubscribe from a channel.
        
        Args:
            channel_name: Channel to unsubscribe from
            symbols: Specific symbols (optional, unsubscribes all if None)
        """
        unsubscribe_msg = {
            "type": "unsubscribe",
            "payload": {
                "channels": [{
                    "name": channel_name,
                    "symbols": symbols or []
                }]
            }
        }
        
        if self.ws and self.state == ConnectionState.CONNECTED:
            try:
                self.ws.send(json.dumps(unsubscribe_msg))
                logger.info(f"Unsubscribed from {channel_name}")
            except Exception as e:
                logger.error(f"Failed to unsubscribe: {e}")
    
    def start(self) -> threading.Thread:
        """
        Start the WebSocket connection.
        
        Returns:
            The WebSocket thread
        """
        if self.is_running:
            logger.warning("Streamer already running")
            return self.ws_thread
        
        logger.info("Starting live data streamer...")
        self.is_running = True
        self.stats = StreamStats()
        
        self._connect()
        
        return self.ws_thread
    
    def stop(self) -> None:
        """Stop the WebSocket connection."""
        logger.info("Stopping live data streamer...")
        self.is_running = False
        self.state = ConnectionState.CLOSED
        
        if self.ws:
            self.ws.close()
        
        # Wait for thread to finish
        if self.ws_thread and self.ws_thread.is_alive():
            self.ws_thread.join(timeout=5)
        
        logger.info("Live data streamer stopped")
    
    def get_message(self, timeout: float = 1.0) -> Optional[tuple]:
        """
        Get message from queue (only if use_queue=True).
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            Tuple of (message_type, data) or None
        """
        if not self.use_queue:
            raise RuntimeError("Message queue not enabled. Set use_queue=True")
        
        try:
            return self.message_queue.get(timeout=timeout)
        except Empty:
            return None
    
    def get_stats(self) -> Dict:
        """Get streaming statistics."""
        return {
            "state": self.state.value,
            "uptime_seconds": self.stats.uptime_seconds,
            "messages_received": self.stats.messages_received,
            "candles_received": self.stats.candles_received,
            "tickers_received": self.stats.tickers_received,
            "errors": self.stats.errors,
            "reconnections": self.stats.reconnections,
            "messages_per_minute": self.stats.messages_per_minute,
            "last_message_age": (
                time.time() - self.stats.last_message_time 
                if self.stats.last_message_time > 0 else None
            )
        }
    
    def is_healthy(self, max_message_age: float = 60) -> bool:
        """
        Check if the streamer is healthy.
        
        Args:
            max_message_age: Maximum seconds since last message
            
        Returns:
            True if healthy
        """
        if self.state != ConnectionState.CONNECTED:
            return False
        
        if self.stats.last_message_time == 0:
            # No messages yet, give it some time
            return self.stats.uptime_seconds < 30
        
        message_age = time.time() - self.stats.last_message_time
        return message_age < max_message_age


# CLI Interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Delta Exchange live data streamer")
    parser.add_argument("--symbols", nargs="+", default=["BTCUSD"], help="Symbols to stream")
    parser.add_argument("--resolution", default="1m", help="Candle resolution")
    parser.add_argument("--ticker", action="store_true", help="Subscribe to ticker")
    parser.add_argument("--testnet", action="store_true", help="Use testnet")
    parser.add_argument("--duration", type=int, default=60, help="Run duration in seconds")
    
    args = parser.parse_args()
    
    def on_candle(candle):
        print(f"[CANDLE] {candle['symbol']} {candle['resolution']}: "
              f"O={candle['open']:.2f} H={candle['high']:.2f} "
              f"L={candle['low']:.2f} C={candle['close']:.2f} V={candle['volume']}")
    
    def on_ticker(ticker):
        print(f"[TICKER] {ticker['symbol']}: "
              f"Close={ticker['close']} Volume={ticker['volume']} "
              f"Mark={ticker['mark_price']}")
    
    def on_error(error):
        print(f"[ERROR] {error}")
    
    def on_connect():
        print("[CONNECTED] WebSocket connected successfully")
    
    def on_disconnect(reason):
        print(f"[DISCONNECTED] {reason}")
    
    streamer = DeltaLiveStreamer(
        on_candle=on_candle,
        on_ticker=on_ticker,
        on_error=on_error,
        on_connect=on_connect,
        on_disconnect=on_disconnect,
        testnet=args.testnet
    )
    
    streamer.subscribe_candles(args.symbols, args.resolution)
    
    if args.ticker:
        streamer.subscribe_ticker(args.symbols)
    
    streamer.start()
    
    print(f"\nStreaming for {args.duration} seconds...")
    print("Press Ctrl+C to stop\n")
    
    try:
        start_time = time.time()
        while time.time() - start_time < args.duration:
            time.sleep(1)
            
            # Print stats every 10 seconds
            if int(time.time() - start_time) % 10 == 0:
                stats = streamer.get_stats()
                print(f"\n[STATS] Messages: {stats['messages_received']}, "
                      f"Candles: {stats['candles_received']}, "
                      f"Rate: {stats['messages_per_minute']:.1f}/min")
                
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        streamer.stop()
        
        print("\nFinal Statistics:")
        stats = streamer.get_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
