#!/usr/bin/env python3
"""
Unified API Client - Shared WebSocket & REST API Layer
Provides a single interface for all systems (bot, recovery, reconciliation)

Features:
- Optional WebSocket support (for real-time price/fills)
- Always-available REST API
- Automatic fallback (WebSocket → REST)
- Connection pooling
- Circuit breaker
- Rate limiting
- Health monitoring

Created: November 20, 2025
"""

import asyncio
import time
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
from loguru import logger as log

from bot.api.async_delta_client import AsyncDeltaClient
from bot.delta_websocket.async_ws_manager import AsyncWebSocketManager


class CircuitBreaker:
    """Simple circuit breaker for API calls"""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = 0
        self.state = "closed"  # closed, open, half_open
    
    def record_success(self):
        """Record successful call"""
        self.failures = 0
        self.state = "closed"
    
    def record_failure(self):
        """Record failed call"""
        self.failures += 1
        self.last_failure_time = time.time()
        
        if self.failures >= self.failure_threshold:
            self.state = "open"
            log.warning(f"🔴 Circuit breaker OPEN - {self.failures} failures")
    
    def can_attempt(self) -> bool:
        """Check if we can attempt a call"""
        if self.state == "closed":
            return True
        
        if self.state == "open":
            # Check if timeout has passed
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "half_open"
                log.info("🟡 Circuit breaker HALF_OPEN - attempting recovery")
                return True
            return False
        
        # half_open state
        return True


class RateLimiter:
    """Simple rate limiter"""
    
    def __init__(self, max_requests: int = 10, window: int = 1):
        self.max_requests = max_requests
        self.window = window
        self.requests = []
    
    async def acquire(self):
        """Acquire rate limit token"""
        now = time.time()
        
        # Remove old requests outside window
        self.requests = [r for r in self.requests if now - r < self.window]
        
        # Check if we're at limit
        if len(self.requests) >= self.max_requests:
            # Calculate wait time
            oldest = self.requests[0]
            wait_time = self.window - (now - oldest)
            if wait_time > 0:
                log.debug(f"Rate limit reached, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
        
        # Add this request
        self.requests.append(time.time())


class UnifiedAPIClient:
    """
    Unified API client for all systems.
    
    Supports:
    - Optional WebSocket (for real-time data)
    - Always-available REST API
    - Automatic fallback
    - Connection pooling
    - Circuit breaker
    - Rate limiting
    
    Usage:
        # Bot (needs WebSocket)
        client = UnifiedAPIClient(
            api_key=key,
            api_secret=secret,
            enable_websocket=True,
            symbol="BTCUSD",
            product_id=27
        )
        
        # Recovery/Reconciliation (REST only)
        client = UnifiedAPIClient(
            api_key=key,
            api_secret=secret,
            enable_websocket=False
        )
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = False,
        enable_websocket: bool = True,
        symbol: Optional[str] = None,
        product_id: Optional[int] = None,
        require_websocket: bool = False
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.symbol = symbol
        self.product_id = product_id
        
        # REST API client (always available)
        self.rest_client = AsyncDeltaClient(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet
        )
        
        # WebSocket manager (PRIMARY for trading bot)
        self.ws_enabled = enable_websocket
        self.ws_manager = None
        self.ws_active = False
        self.require_websocket = require_websocket
        
        # CRITICAL FIX: WebSocket is PRIMARY for trading bot
        if require_websocket and not enable_websocket:
            raise ValueError("WebSocket is REQUIRED for trading bot (set enable_websocket=True)")
        
        if enable_websocket:
            if not symbol or not product_id:
                raise ValueError("symbol and product_id required for WebSocket")
            
            # Get WebSocket URL from config
            from config.loader import get_config
            config = get_config()
            if testnet:
                ws_base_url = config.api.demo_ws_url
            else:
                ws_base_url = config.api.live_ws_url
            
            self.ws_manager = AsyncWebSocketManager(
                api_key=api_key,
                api_secret=api_secret,
                base_url=ws_base_url,
                testnet=testnet
            )
        
        # Fallback state
        self.rest_fallback_active = False
        self.last_price_update = 0
        self.current_price = None
        # CRITICAL FIX: Reduce staleness threshold from 35s to 10s
        # Previous system had no issues with 10s threshold
        self.price_stale_threshold = 10  # seconds (was 35s, causing staleness issues)
        
        # Circuit breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            timeout=60
        )
        
        # Rate limiter (10 requests per second)
        self.rate_limiter = RateLimiter(
            max_requests=10,
            window=1
        )
        
        log.info(f"✅ UnifiedAPIClient initialized (WebSocket: {enable_websocket}, Required: {require_websocket})")
        if require_websocket:
            log.info("⚠️  WebSocket is PRIMARY - REST is fallback only")
    
    # ========================================================================
    # CONNECTION MANAGEMENT
    # ========================================================================
    
    async def connect(self):
        """Connect WebSocket (if enabled)"""
        if self.ws_manager:
            try:
                await self.ws_manager.connect()
                self.ws_active = True
                log.info("✅ WebSocket connected")
            except Exception as e:
                log.error(f"WebSocket connection failed: {e}")
                self.ws_active = False
                self.rest_fallback_active = True
    
    async def disconnect(self):
        """Disconnect WebSocket (if enabled)"""
        if self.ws_manager:
            try:
                await self.ws_manager.disconnect()
                self.ws_active = False
                log.info("✅ WebSocket disconnected")
            except Exception as e:
                log.error(f"WebSocket disconnect error: {e}")
    
    async def reconnect_websocket(self):
        """Reconnect WebSocket with aggressive retry"""
        if self.ws_manager:
            try:
                log.info("🔄 Reconnecting WebSocket...")
                await self.ws_manager.disconnect()
                await asyncio.sleep(2)
                await self.ws_manager.connect()
                self.ws_active = True
                self.rest_fallback_active = False
                log.info("✅ WebSocket reconnected")
            except Exception as e:
                log.error(f"WebSocket reconnection failed: {e}")
                self.ws_active = False
                self.rest_fallback_active = True
    
    async def start_websocket_health_monitor(self):
        """
        CRITICAL FIX: Aggressive WebSocket health monitoring.
        Checks every 5 seconds and reconnects immediately if down.
        This was in the previous working system.
        """
        if not self.ws_manager or not self.require_websocket:
            return
        
        log.info("🏥 Starting WebSocket health monitor (5s interval)")
        
        while True:
            try:
                await asyncio.sleep(5)
                
                # Check if WebSocket is down
                if not self.ws_active:
                    log.warning("⚠️  WebSocket down - attempting reconnection...")
                    await self.reconnect_websocket()
                
                # Check price staleness
                if self.current_price and self.last_price_update:
                    age = time.time() - self.last_price_update
                    if age > self.price_stale_threshold:
                        log.warning(f"⚠️  Price stale ({age:.1f}s) - triggering reconnection...")
                        await self.reconnect_websocket()
                
            except Exception as e:
                log.error(f"WebSocket health monitor error: {e}")
    
    # ========================================================================
    # WEBSOCKET SUBSCRIPTIONS (Optional)
    # ========================================================================
    
    def subscribe_price(self, callback: Callable):
        """Subscribe to price updates (WebSocket only)"""
        if not self.ws_manager:
            raise ValueError("WebSocket not enabled")
        self.ws_manager.register_handler("price", callback)
    
    def subscribe_fills(self, callback: Callable):
        """Subscribe to fill updates (WebSocket only)"""
        if not self.ws_manager:
            raise ValueError("WebSocket not enabled")
        self.ws_manager.register_handler("fill", callback)
    
    def subscribe_orders(self, callback: Callable):
        """Subscribe to order updates (WebSocket only)"""
        if not self.ws_manager:
            raise ValueError("WebSocket not enabled")
        self.ws_manager.register_handler("order", callback)
    
    async def subscribe_channels(self):
        """Subscribe to WebSocket channels"""
        if not self.ws_manager:
            return
        
        try:
            # Subscribe to ticker (public channel)
            await self.ws_manager.subscribe("v2/ticker", [self.symbol])
            
            # Subscribe to user trades (private channel - subscribed after auth)
            await self.ws_manager.subscribe("v2/user_trades", [self.symbol])
            
            # Subscribe to orders (private channel)
            await self.ws_manager.subscribe("orders", [self.symbol])
            
            # Subscribe to positions (private channel)
            await self.ws_manager.subscribe("positions", [self.symbol])
            
            log.info("✅ Subscribed to WebSocket channels")
        except Exception as e:
            log.error(f"Channel subscription failed: {e}")
    
    # ========================================================================
    # PRICE METHODS (WebSocket with REST fallback)
    # ========================================================================
    
    async def get_current_price(self) -> float:
        """
        Get current price.
        Uses WebSocket if available and fresh, otherwise falls back to REST.
        """
        # If WebSocket is active and price is fresh, use it
        if self.ws_active and self.current_price and not self._is_price_stale():
            return self.current_price
        
        # Otherwise, use REST
        return await self._get_price_from_rest()
    
    def _is_price_stale(self) -> bool:
        """Check if WebSocket price is stale"""
        if self.last_price_update == 0:
            # Don't log warning on first check, only after some time
            return True
        
        age = time.time() - self.last_price_update
        is_stale = age > self.price_stale_threshold
        
        if is_stale:
            log.warning(f"⚠️ PRICE STALE: ${self.current_price:,.2f} | Age: {age:.1f}s | Threshold: {self.price_stale_threshold}s | Source: REST_API")
        
        return is_stale
    
    async def _get_price_from_rest(self) -> float:
        """Get price from REST API"""
        try:
            await self.rate_limiter.acquire()
            
            if not self.circuit_breaker.can_attempt():
                log.warning("Circuit breaker open - using cached price")
                return self.current_price if self.current_price else 0.0
            
            ticker = await self.rest_client.get_ticker(self.symbol)
            price = float(ticker.get('mark_price', 0))
            
            # Update cache
            self.current_price = price
            self.last_price_update = time.time()
            
            self.circuit_breaker.record_success()
            return price
        
        except Exception as e:
            log.error(f"REST price fetch failed: {e}")
            self.circuit_breaker.record_failure()
            
            # Return cached price if available
            if self.current_price:
                return self.current_price
            raise
    
    def update_price_from_websocket(self, price: float):
        """Update price from WebSocket (called by price handler)"""
        self.current_price = price
        self.last_price_update = time.time()
        self.ws_active = True  # Mark WebSocket as active when receiving updates
        log.debug(f"💚 UnifiedAPIClient price updated: ${price:,.2f} | last_update: {self.last_price_update}")
    
    # ========================================================================
    # ORDER METHODS (Always REST)
    # ========================================================================
    
    async def get_order(self, order_id: str) -> Dict:
        """Get order details"""
        await self.rate_limiter.acquire()
        
        if not self.circuit_breaker.can_attempt():
            raise Exception("Circuit breaker open")
        
        try:
            result = await self.rest_client.get_order(order_id)
            self.circuit_breaker.record_success()
            return result
        except Exception as e:
            self.circuit_breaker.record_failure()
            raise
    
    async def list_orders(self, **kwargs) -> List[Dict]:
        """List orders"""
        await self.rate_limiter.acquire()
        
        if not self.circuit_breaker.can_attempt():
            raise Exception("Circuit breaker open")
        
        try:
            result = await self.rest_client.list_orders(**kwargs)
            self.circuit_breaker.record_success()
            return result
        except Exception as e:
            self.circuit_breaker.record_failure()
            raise
    
    async def place_order(self, **kwargs) -> Dict:
        """Place order"""
        await self.rate_limiter.acquire()
        
        if not self.circuit_breaker.can_attempt():
            raise Exception("Circuit breaker open")
        
        try:
            result = await self.rest_client.place_order(**kwargs)
            self.circuit_breaker.record_success()
            return result
        except Exception as e:
            self.circuit_breaker.record_failure()
            raise
    
    async def cancel_order(self, order_id: str, **kwargs) -> Dict:
        """Cancel order"""
        await self.rate_limiter.acquire()
        
        if not self.circuit_breaker.can_attempt():
            raise Exception("Circuit breaker open")
        
        try:
            result = await self.rest_client.cancel_order(order_id, **kwargs)
            self.circuit_breaker.record_success()
            return result
        except Exception as e:
            self.circuit_breaker.record_failure()
            raise
    
    # ========================================================================
    # POSITION METHODS (Always REST)
    # ========================================================================
    
    async def get_positions(self) -> List[Dict]:
        """Get positions"""
        await self.rate_limiter.acquire()
        
        if not self.circuit_breaker.can_attempt():
            raise Exception("Circuit breaker open")
        
        try:
            # Pass product_id to get positions for specific product
            result = await self.rest_client.get_positions(product_id=27)  # BTCUSD product_id
            self.circuit_breaker.record_success()
            return result
        except Exception as e:
            self.circuit_breaker.record_failure()
            raise
    
    async def get_ticker(self, symbol: str) -> Dict:
        """Get ticker"""
        await self.rate_limiter.acquire()
        
        if not self.circuit_breaker.can_attempt():
            raise Exception("Circuit breaker open")
        
        try:
            result = await self.rest_client.get_ticker(symbol)
            self.circuit_breaker.record_success()
            return result
        except Exception as e:
            self.circuit_breaker.record_failure()
            raise
    
    # ========================================================================
    # HEALTH MONITORING
    # ========================================================================
    
    def get_health_status(self) -> Dict:
        """Get health status of all connections"""
        return {
            'websocket': {
                'enabled': self.ws_enabled,
                'active': self.ws_active,
                'connected': self.ws_manager.is_connected() if self.ws_manager else False,
                'price_age': time.time() - self.last_price_update if self.last_price_update else None
            },
            'rest': {
                'active': True,
                'fallback_active': self.rest_fallback_active,
                'circuit_breaker': {
                    'state': self.circuit_breaker.state,
                    'failures': self.circuit_breaker.failures
                },
                'rate_limiter': {
                    'requests_in_window': len(self.rate_limiter.requests)
                }
            }
        }
    
    def is_healthy(self) -> bool:
        """Check if client is healthy"""
        # If WebSocket is enabled, it should be connected
        if self.ws_enabled:
            if not self.ws_active:
                return False
            if self._is_price_stale():
                return False
        
        # Circuit breaker should not be open
        if self.circuit_breaker.state == "open":
            return False
        
        return True
