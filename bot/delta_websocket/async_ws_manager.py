"""
Async WebSocket manager for Delta Exchange.
Uses websockets library for async WebSocket connection with automatic reconnection.
FIXED: Race conditions, authentication, and multiple recv() calls.
ENHANCED: Ping/pong, circuit breaker, statistics, task management per Delta Exchange docs.
"""

import asyncio
import json
import time
import hmac
import hashlib
import random
from dataclasses import dataclass, field
from typing import Dict, List, Callable, Optional, AsyncIterator, Any, Set
from uuid import uuid4
from enum import Enum
from collections import deque

import websockets
from websockets.legacy.client import WebSocketClientProtocol
from loguru import logger as log

# Human-readable logging for traders
from bot.utils.human_logger import human_log


class ConnectionState(Enum):
    """WebSocket connection state."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"


@dataclass
class ConnectionStats:
    """Track connection statistics."""
    messages_received: int = 0
    messages_sent: int = 0
    reconnections: int = 0
    authentication_attempts: int = 0
    subscription_attempts: int = 0
    last_message_time: float = 0
    last_heartbeat_time: float = 0
    connection_start_time: float = 0
    total_uptime: float = 0
    error_counts: Dict[str, int] = field(default_factory=dict)


@dataclass
class Subscription:
    """WebSocket subscription details."""
    
    channel: str
    symbols: List[str]
    id: str = field(default_factory=lambda: str(uuid4()))
    subscribed: bool = False


class AsyncWebSocketManager:
    """
    Async WebSocket manager for Delta Exchange.
    
    Features:
    - Automatic reconnection with exponential backoff
    - Subscription management across reconnects
    - Message routing to handlers
    - Heartbeat monitoring
    - Graceful shutdown
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = None,
        testnet: bool = False,
        heartbeat_interval: int = 30,
        reconnect_delay: float = 1.0,
        max_reconnect_delay: float = 60.0
    ):
        """
        Initialize async WebSocket manager.
        
        Args:
            api_key: Delta Exchange API key
            api_secret: Delta Exchange API secret
            base_url: WebSocket base URL (auto-detected from env if None)
            testnet: Whether to use testnet
            heartbeat_interval: Expected heartbeat interval in seconds
            reconnect_delay: Initial reconnect delay
            max_reconnect_delay: Maximum reconnect delay
        """
        import os
        self.api_key = api_key
        self.api_secret = api_secret
        
        # Auto-detect WebSocket URL
        if base_url is None:
            if testnet:
                # Delta Exchange testnet WebSocket endpoint
                self.base_url = "wss://socket-ind.testnet.deltaex.org"
            else:
                # Delta Exchange India production WebSocket endpoint
                self.base_url = "wss://socket.india.delta.exchange"
        else:
            self.base_url = base_url
        self.heartbeat_interval = heartbeat_interval
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay
        
        # Connection state management
        self.state = ConnectionState.DISCONNECTED
        self._connection_lock = asyncio.Lock()
        self._reconnecting = False
        
        # WebSocket connection
        self._ws: Optional[WebSocketClientProtocol] = None
        self._running = False
        
        # Subscriptions
        self._subscriptions: Dict[str, Subscription] = {}
        
        # Message handlers
        self._handlers: Dict[str, List[Callable]] = {}
        
        # CRITICAL FIX NOV 14: Reconnection callback for fill reconciliation
        self._reconnect_callback: Optional[Callable] = None
        
        # Heartbeat monitoring (enhanced with ping/pong)
        self._last_heartbeat = time.time()
        self._last_pong_time = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._message_handler_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None
        self.ping_interval = 30  # Send ping every 30 seconds (Delta Exchange server heartbeat)
        self.heartbeat_timeout = 35  # 35s timeout per Delta Exchange specs (30s + 5s buffer)
        
        # Message queues with bounded size (created in connect())
        self._message_queue: Optional[asyncio.Queue] = None
        self._outbound_queue: Optional[asyncio.Queue] = None
        self._send_handler_task: Optional[asyncio.Task] = None
        
        # Reconnection state with circuit breaker
        self._reconnect_attempts = 0
        self._current_reconnect_delay = self.reconnect_delay
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5
        self.circuit_breaker_timeout = 300  # 5 minutes
        self.circuit_breaker_open_until = None
        
        # Statistics tracking
        self.stats = ConnectionStats()
        self.message_timestamps = deque(maxlen=1000)
        
        # Task management
        self.background_tasks: Set[asyncio.Task] = set()
        self._connected = False
    
    @property
    def ws(self) -> Optional[WebSocketClientProtocol]:
        """
        Public accessor for WebSocket connection.
        
        Returns:
            WebSocket connection or None if not connected
        """
        return self._ws
    
    def _ws_is_alive(self) -> bool:
        """
        Check if WebSocket object is alive and usable.
        
        CRITICAL: Handles multiple WebSocket implementations (websockets, aiohttp, etc.)
        and prevents AttributeError on .closed/.open/.connected access.
        
        Supports:
        - websockets.asyncio.client.ClientConnection (.state property with State enum)
        - websockets.legacy.client.WebSocketClientProtocol (.closed property)
        - aiohttp.ClientWebSocketResponse (._closed property)
        
        Returns:
            True if WebSocket exists and is not closed/terminated
        """
        if self._ws is None:
            return False
        
        try:
            # Try websockets.asyncio.client.ClientConnection API (.state property with State enum)
            if hasattr(self._ws, 'state'):
                from websockets.protocol import State
                return self._ws.state == State.OPEN
            
            # Try websockets legacy API (.closed property)
            if hasattr(self._ws, 'closed'):
                return not self._ws.closed
            
            # Try aiohttp ClientWebSocketResponse API
            if hasattr(self._ws, '_closed'):
                return not self._ws._closed
            
            # Try .open property (some implementations)
            if hasattr(self._ws, 'open'):
                return self._ws.open
            
            # Fallback: check if object exists
            # If we got here, we have a WebSocket object but can't determine state
            # Log warning and assume it's alive
            log.warning(f"WebSocket object type: {type(self._ws)} - using existence as alive check")
            return True
            
        except Exception as e:
            log.error(f"Error checking WebSocket state: {e}")
            return False
    
    @property
    def is_connected(self) -> bool:
        """
        Check if WebSocket is connected and authenticated.
        
        Returns:
            True if connected and authenticated, False otherwise
        """
        return (
            self._ws_is_alive() and
            self.state in [ConnectionState.CONNECTED, ConnectionState.AUTHENTICATED]
        )
    
    async def connect(self) -> None:
        """
        Connect to WebSocket and start message loop.
        Uses lock to prevent race conditions from multiple simultaneous connects.
        
        Raises:
            Exception: If connection fails
        """
        # Prevent concurrent connection attempts
        async with self._connection_lock:
            if self.state in [ConnectionState.CONNECTING, ConnectionState.CONNECTED, ConnectionState.AUTHENTICATED]:
                log.warning(f"Connection already in progress or established (state: {self.state.value})")
                return
            
            self.state = ConnectionState.CONNECTING
            self._running = True
            
            # Create message queues within running event loop
            if self._message_queue is None:
                # Larger queue to handle bursts (10K messages)
                # Message queue holds pre-routed messages for async iteration
                self._message_queue = asyncio.Queue(maxsize=10000)
            if self._outbound_queue is None:
                self._outbound_queue = asyncio.Queue(maxsize=100)
            
            try:
                # Connect to WebSocket
                # Delta Exchange WebSocket connects directly to base URL (no /v2/ws path)
                ws_url = self.base_url
                log.info(f"Connecting to WebSocket: {ws_url}")
                
                self._ws = await websockets.connect(
                    ws_url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10
                )
                
                self._connected = True
                self.state = ConnectionState.CONNECTED
                self._reconnect_attempts = 0
                self._current_reconnect_delay = self.reconnect_delay
                
                log.info("✅ WebSocket connected successfully")
                
                # Track connection start time for statistics
                self.stats.connection_start_time = time.time()
                
                # Start all background tasks
                tasks = [
                    self._message_handler(),
                    self._monitor_heartbeat(),
                    self._ping_loop(),
                    self._send_handler(),
                ]
                
                for coro in tasks:
                    task = asyncio.create_task(coro)
                    self.background_tasks.add(task)
                    task.add_done_callback(self.background_tasks.discard)
                
                # Authenticate
                await self._authenticate()
                
                # Enable heartbeat monitoring on server
                await self._enable_heartbeat()
                
                # Restore public subscriptions only (private come after auth)
                await self._restore_public_subscriptions()
                
            except Exception as e:
                log.error(f"Failed to connect to WebSocket: {e}")
                self._connected = False
                self.state = ConnectionState.DISCONNECTED
                self.stats.error_counts['connection_failed'] = self.stats.error_counts.get('connection_failed', 0) + 1
                raise
    
    async def disconnect(self) -> None:
        """Disconnect from WebSocket gracefully with full cleanup."""
        log.info("Disconnecting WebSocket...")
        self._running = False
        self.state = ConnectionState.DISCONNECTED
        
        # Update statistics
        if self.stats.connection_start_time:
            uptime = time.time() - self.stats.connection_start_time
            self.stats.total_uptime += uptime
            self.stats.connection_start_time = 0
        
        # Reset subscription states for reconnection
        for subscription in self._subscriptions.values():
            subscription.subscribed = False
        
        # Clean up all background tasks
        await self._cleanup_tasks()
        
        # Close WebSocket connection
        if self._ws:
            await self._ws.close()
            self._ws = None
        
        self._connected = False
        log.info("WebSocket disconnected")
    
    async def _cleanup_tasks(self):
        """
        Clean up all background tasks.
        
        FIX NOV 14: Avoid RecursionError by cancelling tasks without waiting.
        The recursion error occurs when cancelling deeply nested task chains.
        Instead, we cancel tasks and let them exit naturally.
        """
        log.info("Cleaning up background tasks...")
        
        # Cancel all tasks but don't gather them (avoids recursion)
        tasks_to_cancel = list(self.background_tasks.copy())
        for task in tasks_to_cancel:
            if not task.done():
                try:
                    task.cancel()
                except Exception as e:
                    log.debug(f"Error cancelling task: {e}")
        
        # Give tasks a moment to cancel, but don't wait indefinitely
        # This prevents the RecursionError that occurs in gather()
        try:
            await asyncio.sleep(0.1)  # Brief pause to allow cancellation
        except:
            pass
        
        self.background_tasks.clear()
        log.info("All background tasks cleaned up")
    
    async def subscribe(self, channel: str, symbols: List[str]) -> None:
        """
        Subscribe to WebSocket channel.
        
        Args:
            channel: Channel name (e.g., "user_trades", "v2/ticker", "l2_orderbook")
            symbols: List of symbols to subscribe
        """
        # Check if already subscribed and active
        for existing_sub in self._subscriptions.values():
            if (existing_sub.channel == channel and 
                set(existing_sub.symbols) == set(symbols) and 
                existing_sub.subscribed):
                log.debug(f"Already subscribed to {channel}: {symbols}")
                return
        
        # Check if we need authentication for private channels (per Delta Exchange docs)
        private_channels = ['orders', 'positions', 'user_trades', 'margins']
        if channel in private_channels and self.state != ConnectionState.AUTHENTICATED:
            log.debug(f"Private channel {channel} subscription queued - will subscribe after authentication")
            # Store for later subscription after authentication
            subscription = Subscription(channel=channel, symbols=symbols)
            self._subscriptions[subscription.id] = subscription
            return
        
        # Check if connected
        if self.state not in [ConnectionState.CONNECTED, ConnectionState.AUTHENTICATED]:
            log.warning(f"Cannot subscribe - not connected (state: {self.state.value})")
            return
        
        subscription = Subscription(channel=channel, symbols=symbols)
        self._subscriptions[subscription.id] = subscription
        
        await self._send_subscription(subscription)
    
    async def unsubscribe(self, channel: str, symbols: List[str]) -> None:
        """
        Unsubscribe from WebSocket channel.
        
        Args:
            channel: Channel name
            symbols: List of symbols to unsubscribe
        """
        # Find matching subscription
        for sub_id, sub in list(self._subscriptions.items()):
            if sub.channel == channel and set(sub.symbols) == set(symbols):
                del self._subscriptions[sub_id]
                
                if self._connected:
                    await self._send_unsubscription(sub)
                break
    
    def register_handler(self, msg_type: str, callback: Callable) -> None:
        """
        Register message handler.
        
        Args:
            msg_type: Message type to handle
            callback: Async callback function
        """
        if msg_type not in self._handlers:
            self._handlers[msg_type] = []
        
        self._handlers[msg_type].append(callback)
        log.info(f"Registered handler for message type: {msg_type}")
    
    def unregister_handler(self, msg_type: str, callback: Callable) -> None:
        """
        Unregister message handler.
        
        Args:
            msg_type: Message type
            callback: Callback to remove
        """
        if msg_type in self._handlers:
            self._handlers[msg_type].remove(callback)
    
    def register_reconnect_callback(self, callback: Callable) -> None:
        """
        CRITICAL FIX NOV 14: Register callback to execute after reconnection.
        
        This allows the bot to reconcile missed fills after WebSocket reconnects.
        
        Args:
            callback: Async callback function to execute after successful reconnection
        """
        self._reconnect_callback = callback
        log.info("Registered reconnection callback for fill reconciliation")
    
    async def messages(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Async iterator for WebSocket messages.
        
        Yields:
            Parsed WebSocket messages
        """
        while self._running:
            try:
                message = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=1.0
                )
                yield message
            except asyncio.TimeoutError:
                continue
    
    def _generate_signature(self, secret: str, message: str) -> str:
        """
        Generate HMAC signature for authentication.
        
        Args:
            secret: API secret
            message: Message to sign
            
        Returns:
            Hex-encoded signature
        """
        return hmac.new(
            secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    async def _authenticate(self) -> None:
        """
        Authenticate WebSocket connection with proper HMAC signature.
        
        Delta Exchange WebSocket auth format:
        - Signature: HMAC-SHA256(api_secret, 'GET' + timestamp + '/live')
        - Timestamp: Unix timestamp in SECONDS (not milliseconds)
        """
        if self.state != ConnectionState.CONNECTED:
            log.warning(f"Cannot authenticate - not connected (state: {self.state.value})")
            return
        
        # Generate signature: method + timestamp + '/live'
        method = 'GET'
        timestamp = str(int(time.time()))  # SECONDS, not milliseconds
        path = '/live'
        signature_data = method + timestamp + path
        signature = self._generate_signature(self.api_secret, signature_data)
        
        auth_message = {
            "type": "auth",
            "payload": {
                "api-key": self.api_key,
                "signature": signature,
                "timestamp": timestamp
            }
        }
        
        await self._send_message(auth_message)
        self.stats.authentication_attempts += 1
        log.info(f"Sent authentication message (timestamp={timestamp})")
    
    async def _restore_public_subscriptions(self) -> None:
        """Restore public subscriptions after reconnection (before authentication)."""
        # All public channels per Delta Exchange WebSocket documentation
        public_channels = [
            'v2/ticker', 'l2_orderbook', 'all_trades',
            'candlestick_1m', 'candlestick_3m', 'candlestick_5m', 'candlestick_15m',
            'candlestick_30m', 'candlestick_1h', 'candlestick_2h', 'candlestick_4h',
            'candlestick_6h', 'candlestick_12h', 'candlestick_1d', 'candlestick_1w',
            'candlestick_2w', 'candlestick_30d', 'announcements'
        ]
        
        for subscription in self._subscriptions.values():
            if subscription.channel in public_channels:
                if subscription.subscribed:
                    subscription.subscribed = False  # Reset state
                await self._send_subscription(subscription)
    
    async def _restore_subscriptions(self) -> None:
        """Restore all subscriptions after reconnection (deprecated - use specific methods)."""
        await self._restore_public_subscriptions()
        # Private subscriptions are restored automatically after authentication
    
    async def _send_subscription(self, subscription: Subscription) -> None:
        """
        Send subscription message.
        
        Args:
            subscription: Subscription details
        """
        sub_message = {
            "type": "subscribe",
            "payload": {
                "channels": [
                    {
                        "name": subscription.channel,
                        "symbols": subscription.symbols
                    }
                ]
            }
        }
        
        await self._send_message(sub_message)
        subscription.subscribed = True
        self.stats.subscription_attempts += 1
        log.info(f"Subscribed to {subscription.channel}: {subscription.symbols}")
    
    async def _send_unsubscription(self, subscription: Subscription) -> None:
        """
        Send unsubscription message.
        
        Args:
            subscription: Subscription details
        """
        unsub_message = {
            "type": "unsubscribe",
            "payload": {
                "channels": [
                    {
                        "name": subscription.channel,
                        "symbols": subscription.symbols
                    }
                ]
            }
        }
        
        await self._send_message(unsub_message)
        subscription.subscribed = False
        log.info(f"Unsubscribed from {subscription.channel}: {subscription.symbols}")
    
    def _ensure_connected(self) -> None:
        """
        Ensure WebSocket is in a valid state for operations.
        
        Raises:
            Exception: If not in valid state
        """
        if self.state == ConnectionState.DISCONNECTED:
            raise Exception("WebSocket not connected")
        elif self.state == ConnectionState.CONNECTING:
            raise Exception("WebSocket connection in progress")
    
    async def _message_handler(self) -> None:
        """
        Single message handler - prevents multiple recv() calls.
        This is the ONLY coroutine that calls recv() on the WebSocket.
        
        NOV 13: Added safety check for _ws before recv() to prevent AttributeError.
        """
        try:
            while self._running and self.state in [ConnectionState.CONNECTED, ConnectionState.AUTHENTICATED]:
                try:
                    # Safety check: ensure WebSocket exists before recv()
                    if not self._ws:
                        log.warning("WebSocket connection lost in message handler")
                        self.state = ConnectionState.DISCONNECTED
                        await self._handle_reconnect()
                        break
                    
                    # Receive message (only one coroutine calls this)
                    message_str = await self._ws.recv()
                    
                    # Update heartbeat timestamp
                    self._last_heartbeat = time.time()
                    
                    # Parse message
                    message = json.loads(message_str)
                    
                    # Process message
                    await self._process_message(message)
                
                except websockets.exceptions.ConnectionClosed as e:
                    log.warning(f"WebSocket connection closed: {e}")
                    self.state = ConnectionState.DISCONNECTED
                    await self._handle_reconnect()
                    break
                
                except json.JSONDecodeError as e:
                    log.error(f"Failed to parse WebSocket message: {e}")
                    continue
                
                except Exception as e:
                    log.error(f"Error in message handler: {e}")
                    continue
        
        except asyncio.CancelledError:
            log.info("Message handler cancelled")
        except Exception as e:
            log.error(f"Fatal error in message handler: {e}")
            self.state = ConnectionState.DISCONNECTED
    
    async def _process_message(self, message: Dict[str, Any]) -> None:
        """
        Process incoming WebSocket message with statistics tracking.
        
        Args:
            message: Parsed JSON message
        """
        # Track statistics
        self.stats.messages_received += 1
        self.stats.last_message_time = time.time()
        self.message_timestamps.append(time.time())
        
        msg_type = message.get("type")
        
        # Handle pong (response to our ping)
        if msg_type == "pong":
            self.last_pong_time = time.time()
            log.debug("Received pong")  # Keep for AI/system
            human_log.heartbeat_ok()  # Trader-friendly
            return
        
        # Handle authentication success (exact match per Delta Exchange docs)
        if msg_type == "success" and message.get("message") == "Authenticated":
            self.state = ConnectionState.AUTHENTICATED
            self.stats.authentication_attempts += 1
            log.info("✅ Authentication successful")
            human_log.websocket_authenticated()  # Trader-friendly
            # Subscribe to private channels now
            await self._subscribe_private_channels()
            return
        
        # Handle heartbeat
        if msg_type == "heartbeat":
            self.stats.last_heartbeat_time = time.time()
            # Heartbeat received - no log (too frequent, not actionable)
            return
        
        # Handle subscription confirmations and Delta Exchange specific errors
        if msg_type == "subscriptions":
            channels = message.get('channels', [])
            for channel_info in channels:
                if 'error' in channel_info:
                    error_msg = channel_info.get('error', '')
                    channel_name = channel_info.get('name', 'unknown')
                    
                    # Private channel error before auth is expected
                    if "Unauthorized" in error_msg or "authenticate" in error_msg.lower():
                        log.debug(f"Waiting for auth before subscribing to {channel_name}")
                    elif "Invalid" in error_msg or "not found" in error_msg.lower():
                        log.error(f"❌ Invalid channel or symbol: {channel_info}")
                        self.stats.error_counts['invalid_subscription'] = self.stats.error_counts.get('invalid_subscription', 0) + 1
                    else:
                        log.error(f"❌ Subscription error: {channel_info}")
                        self.stats.error_counts['subscription_error'] = self.stats.error_counts.get('subscription_error', 0) + 1
                else:
                    channel_name = channel_info.get('name', 'unknown')
                    log.info(f"✅ Subscription confirmed: {channel_name}")
                    # Aggregate subscriptions for human-friendly message
                    active_channels = [ch.get('name', 'unknown') for ch in channels if 'error' not in ch]
                    if active_channels:
                        human_log.subscriptions_active(active_channels)
            return
        
        # Handle errors
        if msg_type == "error":
            error_msg = message.get('error') or message.get('message') or str(message)
            log.error(f"WebSocket error: {error_msg}")
            return
        
        # Route to handlers
        await self._route_message(message)
        
        # Add to queue for async iteration
        # Note: Messages are already processed via _route_message(),
        # this queue is only for the messages() iterator (if used)
        try:
            self._message_queue.put_nowait(message)
        except asyncio.QueueFull:
            # Rate limit this warning (only log every 100 drops)
            if not hasattr(self, '_queue_drop_count'):
                self._queue_drop_count = 0
            self._queue_drop_count += 1
            if self._queue_drop_count % 100 == 1:
                log.warning(f"Message queue full - dropped {self._queue_drop_count} messages (queue consumer may be slow)")
    
    async def _subscribe_private_channels(self) -> None:
        """Subscribe to private channels after authentication (per Delta Exchange docs)."""
        log.info("Subscribing to private channels after authentication")
        
        # All private channels per Delta Exchange WebSocket documentation
        private_channels = ['orders', 'positions', 'user_trades', 'margins']
        
        for sub_id, subscription in list(self._subscriptions.items()):
            if subscription.channel in private_channels and not subscription.subscribed:
                await self._send_subscription(subscription)
    
    async def _route_message(self, message: Dict[str, Any]) -> None:
        """
        Route message to registered handlers.
        
        Args:
            message: Message to route
        """
        msg_type = message.get("type", "")
        
        # Check for specific handlers
        if msg_type in self._handlers:
            handler_count = len(self._handlers[msg_type])
            
            # Rate-limit ticker routing logs (too frequent)
            should_log = msg_type != "v2/ticker" or (time.time() - getattr(self, '_last_ticker_route_log', 0) > 60)
            
            if should_log:
                log.debug(f"Routing {msg_type} to {handler_count} handler(s)")  # Keep for AI/system
                human_log.message_routed(msg_type, handler_count)  # Trader-friendly
                if msg_type == "v2/ticker":
                    self._last_ticker_route_log = time.time()
            
            for handler in self._handlers[msg_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(message)
                    else:
                        handler(message)
                except Exception as e:
                    log.error(f"Error in message handler for {msg_type}: {e}", exc_info=True)
                    human_log.handler_failed(msg_type, str(e))  # Trader-friendly error
        
        # Check for wildcard handlers
        if "*" in self._handlers:
            for handler in self._handlers["*"]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(message)
                    else:
                        handler(message)
                except Exception as e:
                    log.error(f"Error in wildcard handler: {e}")
    
    async def _monitor_heartbeat(self) -> None:
        """
        Monitor heartbeat and reconnect if needed.
        Uses defined heartbeat_timeout property (35s = 30s ping + 5s buffer).
        """
        while self._running:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                # Check last heartbeat (only if connected/authenticated)
                if self.state not in [ConnectionState.CONNECTED, ConnectionState.AUTHENTICATED]:
                    continue
                
                time_since_heartbeat = time.time() - self._last_heartbeat
                
                # Use configured timeout (35s default per Delta Exchange docs)
                if time_since_heartbeat > self.heartbeat_timeout:
                    log.warning(f"⚠️ No heartbeat for {time_since_heartbeat:.0f}s (timeout: {self.heartbeat_timeout}s) - reconnecting...")
                    human_log.heartbeat_delayed(time_since_heartbeat)  # Trader-friendly warning
                    human_log.reconnecting()  # About to reconnect
                    await self._handle_reconnect()
                    break
            
            except asyncio.CancelledError:
                log.info("Heartbeat monitor cancelled")
                break
            except Exception as e:
                log.error(f"Error in heartbeat monitor: {e}")
    
    async def _handle_reconnect(self) -> None:
        """
        Handle WebSocket reconnection with exponential backoff and circuit breaker.
        
        NOV 13: Fixed to properly clean up and restart all background tasks.
        NOV 14: Added timeout and RecursionError fix to prevent hanging.
        """
        if not self._running:
            return
        
        # Check circuit breaker
        if self.circuit_breaker_open_until and time.time() < self.circuit_breaker_open_until:
            remaining = self.circuit_breaker_open_until - time.time()
            log.warning(f"🔴 Circuit breaker open - waiting {remaining:.0f}s")
            return
        
        # Prevent concurrent reconnection attempts
        if self._reconnecting:
            log.debug("Reconnection already in progress")
            return
        
        self._reconnecting = True
        
        try:
            log.info("🔄 Starting reconnection process...")
            
            # Step 1: Clean shutdown of existing connection
            self._connected = False
            old_state = self.state
            self.state = ConnectionState.DISCONNECTED
            self._reconnect_attempts += 1
            self.stats.reconnections += 1
            
            # Step 2: Clean up all background tasks (they've likely exited anyway)
            # FIX NOV 14: Add timeout to prevent hanging on task cleanup
            log.debug("Cleaning up background tasks before reconnect...")
            try:
                await asyncio.wait_for(self._cleanup_tasks(), timeout=5.0)
            except asyncio.TimeoutError:
                log.warning("Task cleanup timed out - forcing clear")
                self.background_tasks.clear()
            except Exception as e:
                log.error(f"Error during task cleanup: {e}")
                self.background_tasks.clear()
            
            # Step 3: Close existing WebSocket
            if self._ws:
                try:
                    await asyncio.wait_for(self._ws.close(), timeout=2.0)
                except asyncio.TimeoutError:
                    log.warning("WebSocket close timed out")
                except Exception as e:
                    log.debug(f"Error closing old WebSocket: {e}")
                self._ws = None
            
            # Step 4: Calculate backoff delay
            base_delay = min(2 ** self._reconnect_attempts, 30)
            jitter = random.uniform(0, 0.5)
            delay = base_delay + jitter
            
            log.info(f"🔄 Reconnecting in {delay:.1f}s (attempt {self._reconnect_attempts})")
            await asyncio.sleep(delay)
            
            # Step 5: Reconnect (this will restart all tasks)
            try:
                # Must bypass the state check in connect() since we're in DISCONNECTED
                async with self._connection_lock:
                    # Force reconnection even if state looks wrong
                    self.state = ConnectionState.DISCONNECTED
                    self._running = True  # Ensure running flag is set
                    
                    # Connect to WebSocket
                    ws_url = self.base_url
                    log.info(f"Reconnecting to WebSocket: {ws_url}")
                    
                    self._ws = await websockets.connect(
                        ws_url,
                        ping_interval=20,
                        ping_timeout=10,
                        close_timeout=10
                    )
                    
                    self._connected = True
                    self.state = ConnectionState.CONNECTED
                    self._reconnect_attempts = 0
                    self._current_reconnect_delay = self.reconnect_delay
                    
                    log.info("✅ WebSocket reconnected successfully")
                    
                    # Track connection start time
                    self.stats.connection_start_time = time.time()
                    
                    # Step 6: Restart all background tasks
                    log.info("Restarting background tasks...")
                    tasks = [
                        self._message_handler(),
                        self._monitor_heartbeat(),
                        self._ping_loop(),
                        self._send_handler(),
                    ]
                    
                    for coro in tasks:
                        task = asyncio.create_task(coro)
                        self.background_tasks.add(task)
                        task.add_done_callback(self.background_tasks.discard)
                    
                    # Step 7: Re-authenticate
                    await self._authenticate()
                    
                    # Step 8: Re-enable heartbeat
                    await self._enable_heartbeat()
                    
                    # Step 9: Restore subscriptions
                    await self._restore_public_subscriptions()
                    
                    # CRITICAL FIX NOV 14: Trigger reconnection callback for fill reconciliation
                    if self._reconnect_callback:
                        log.info("🔄 Triggering reconnection callback for fill reconciliation...")
                        try:
                            await self._reconnect_callback()
                            log.info("✅ Reconnection callback completed successfully")
                        except Exception as callback_error:
                            log.error(f"❌ Reconnection callback failed: {callback_error}")
                            # Don't fail the reconnection if callback fails
                
                # Success - reset failures
                self.consecutive_failures = 0
                log.info("✅ Reconnection complete - all tasks restarted")
                
            except Exception as e:
                self.consecutive_failures += 1
                log.error(f"Reconnection failed: {e} (consecutive failures: {self.consecutive_failures})")
                self.stats.error_counts['reconnect_failed'] = self.stats.error_counts.get('reconnect_failed', 0) + 1
                
                # Open circuit breaker if too many failures
                if self.consecutive_failures >= self.max_consecutive_failures:
                    self.circuit_breaker_open_until = time.time() + self.circuit_breaker_timeout
                    log.error(f"🔴 Circuit breaker opened for {self.circuit_breaker_timeout}s")
                    return
                
                # Schedule next reconnection attempt
                if self._running:
                    self._reconnecting = False
                    asyncio.create_task(self._handle_reconnect())
        finally:
            self._reconnecting = False
    
    async def _handle_heartbeat(self) -> None:
        """Send heartbeat response if required."""
        # Delta Exchange doesn't require heartbeat response
        pass
    
    async def _enable_heartbeat(self):
        """Enable heartbeat monitoring after connection (Delta Exchange recommendation)."""
        heartbeat_message = {"type": "enable_heartbeat"}
        await self._send_message(heartbeat_message)
        log.info("Heartbeat enabled on server")
    
    async def _ping_loop(self):
        """
        Send periodic ping messages (Delta Exchange recommendation).
        
        NOV 13 v3: Loop continues on errors (doesn't exit permanently).
        Only exits on cancellation or shutdown.
        """
        while self._running:
            try:
                await asyncio.sleep(self.ping_interval)
                
                # Verify still running
                if not self._running:
                    break
                
                # Skip ping if not connected (wait for reconnect)
                if self.state not in [ConnectionState.CONNECTED, ConnectionState.AUTHENTICATED]:
                    log.debug("Ping loop: not connected, waiting...")
                    continue
                
                # Send ping if WebSocket exists and is alive
                if self._ws_is_alive():
                    ping_message = {"type": "ping"}
                    await self._send_message(ping_message)
                    log.debug("Sent ping")  # Keep for AI/system
                    # Human log only shows pong response
                else:
                    log.debug("Ping loop: WebSocket not alive, skipping ping")
                    human_log.connection_unstable()  # Trader-friendly alert
                    # Don't exit - wait for reconnect
                    
            except asyncio.CancelledError:
                log.info("Ping loop cancelled")
                break
            except Exception as e:
                log.error(f"Error in ping loop: {e}")
                self.stats.error_counts['ping_failed'] = self.stats.error_counts.get('ping_failed', 0) + 1
                # Continue loop - don't exit on errors
                await asyncio.sleep(1)  # Brief pause before retry
        
        log.debug("Ping loop exited")
    
    async def _send_handler(self):
        """
        Dedicated coroutine for sending messages (prevents blocking).
        
        NOV 13 v3: Loop continues on errors (doesn't exit permanently).
        Re-queues messages when WebSocket unavailable for retry after reconnect.
        """
        while self._running:
            try:
                # Wait for message with timeout to check shutdown
                message = await asyncio.wait_for(
                    self._outbound_queue.get(),
                    timeout=1.0
                )
                
                # Verify WebSocket is available and open before sending
                if self._ws_is_alive():
                    await self._ws.send(json.dumps(message))
                    self.stats.messages_sent += 1
                else:
                    log.debug(f"Send handler: WebSocket not alive, re-queuing message")
                    human_log.websocket_not_ready()  # Trader-friendly alert
                    # Re-queue message for retry after reconnect (if queue not full)
                    if not self._outbound_queue.full():
                        await self._outbound_queue.put(message)
                    else:
                        log.warning("Outbound queue full, dropping message")
                        human_log.queue_growing("outbound", self._outbound_queue.qsize())
                    await asyncio.sleep(0.5)  # Brief pause to avoid tight loop
                    
            except asyncio.TimeoutError:
                continue  # Check if still running
            except asyncio.CancelledError:
                log.info("Send handler cancelled")
                break
            except websockets.exceptions.ConnectionClosed as e:
                log.debug(f"Connection closed while sending: {e}")
                human_log.disconnected()  # Trader-friendly critical alert
                # Don't exit - continue loop and wait for reconnect
                await asyncio.sleep(0.5)
            except Exception as e:
                log.error(f"Error in send handler: {e}")
                self.stats.error_counts['send_failed'] = self.stats.error_counts.get('send_failed', 0) + 1
                # Continue loop - don't exit on errors
                await asyncio.sleep(0.5)
        
        log.debug("Send handler exited")
    
    async def _send_message(self, message: Dict[str, Any]) -> None:
        """
        Thread-safe message sending via queue.
        
        Args:
            message: Message to send
            
        Raises:
            Exception: If queue is full or manager not running
        """
        if not self._running:
            raise Exception("WebSocket manager not running")
        
        try:
            await self._outbound_queue.put(message)
        except asyncio.QueueFull:
            log.warning("Outbound queue full - dropping message")
            self.stats.error_counts['queue_full'] = self.stats.error_counts.get('queue_full', 0) + 1
            raise Exception("Message queue full")
    
    def get_message_rate(self, window_seconds: int = 60) -> float:
        """Calculate messages per second over time window."""
        if not self.message_timestamps:
            return 0.0
        
        current_time = time.time()
        cutoff_time = current_time - window_seconds
        
        recent_messages = [
            ts for ts in self.message_timestamps 
            if ts > cutoff_time
        ]
        
        return len(recent_messages) / window_seconds if window_seconds > 0 else 0.0
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        current_time = time.time()
        current_uptime = 0
        
        if self.stats.connection_start_time:
            current_uptime = current_time - self.stats.connection_start_time
        
        return {
            "state": self.state.value,
            "messages_received": self.stats.messages_received,
            "messages_sent": self.stats.messages_sent,
            "reconnections": self.stats.reconnections,
            "last_message_time": self.stats.last_message_time,
            "last_heartbeat_time": self.stats.last_heartbeat_time,
            "total_uptime": self.stats.total_uptime,
            "current_uptime": current_uptime,
            "message_rate_1min": self.get_message_rate(60),
            "message_rate_5min": self.get_message_rate(300),
            "message_queue_size": self._message_queue.qsize(),
            "outbound_queue_size": self._outbound_queue.qsize(),
            "active_subscriptions": len(self._subscriptions),
            "consecutive_failures": self.consecutive_failures,
            "circuit_breaker_open": bool(
                self.circuit_breaker_open_until and 
                current_time < self.circuit_breaker_open_until
            ),
            "error_counts": dict(self.stats.error_counts),
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check.
        
        Returns:
            Dict with health status, issues, and statistics
        """
        current_time = time.time()
        issues = []
        
        # Check connection state
        if self.state not in [ConnectionState.CONNECTED, ConnectionState.AUTHENTICATED]:
            issues.append(f"Not connected (state: {self.state.value})")
        
        # Check WebSocket object exists and is alive
        if self._ws is None:
            issues.append("WebSocket object is None")
        elif not self._ws_is_alive():
            issues.append("WebSocket is closed or terminated")
        
        # Check recent messages
        if self.stats.last_message_time:
            time_since_message = current_time - self.stats.last_message_time
            if time_since_message > 60:
                issues.append(f"No messages for {time_since_message:.0f}s")
        elif self.state in [ConnectionState.CONNECTED, ConnectionState.AUTHENTICATED]:
            # Connected but never received messages
            issues.append("Connected but no messages received yet")
        
        # Check heartbeat
        if self.stats.last_heartbeat_time:
            time_since_heartbeat = current_time - self.stats.last_heartbeat_time
            if time_since_heartbeat > self.heartbeat_timeout:
                issues.append(f"Heartbeat timeout: {time_since_heartbeat:.0f}s > {self.heartbeat_timeout}s")
        
        # Check queue sizes
        if self._message_queue.qsize() > self._message_queue.maxsize * 0.8:
            issues.append(f"Message queue near full: {self._message_queue.qsize()}/{self._message_queue.maxsize}")
        
        if self._outbound_queue.qsize() > self._outbound_queue.maxsize * 0.8:
            issues.append(f"Outbound queue near full: {self._outbound_queue.qsize()}/{self._outbound_queue.maxsize}")
        
        # Check consecutive failures
        if self.consecutive_failures > 0:
            issues.append(f"Consecutive failures: {self.consecutive_failures}")
        
        # Check circuit breaker
        if self.circuit_breaker_open_until and current_time < self.circuit_breaker_open_until:
            remaining = self.circuit_breaker_open_until - current_time
            issues.append(f"Circuit breaker open for {remaining:.0f}s")
        
        # Check reconnection status
        if self._reconnecting:
            issues.append("Reconnection in progress")
        
        return {
            "healthy": len(issues) == 0,
            "issues": issues,
            "timestamp": current_time,
            "is_connected": self.is_connected,
            "state": self.state.value,
            "stats": self.get_connection_stats()
        }
