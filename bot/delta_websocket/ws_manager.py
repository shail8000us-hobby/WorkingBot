"""
╔══════════════════════════════════════════════════════════════════════════╗
║                    🔒 PRODUCTION-LOCKED v1.0.0-stable 🔒                 ║
║                                                                          ║
║  Status: ✅ FINALIZED & APPROVED                                        ║
║  Date: 2025-10-21                                                       ║
║  Owner: Shailendra Singh Rajawat                                        ║
║                                                                          ║
║  ⚠️  CHANGES REQUIRE MAC PASSWORD APPROVAL ⚠️                            ║
╚══════════════════════════════════════════════════════════════════════════╝

🔐 PROTECTED BY:
  • Git pre-commit hooks (password authentication required)
  • SHA256 integrity verification on bot startup
  • File system immutability (read-only permissions)
  • Audit logging of all modifications
  
⚠️  DO NOT MODIFY WITHOUT:
  1. Understanding full impact on WebSocket communication
  2. Review of fill detection logic
  3. Testing WebSocket reconnection scenarios
  4. Explicit approval from owner with Mac password
  5. Update to checksums after approval

================================================================================

WebSocket Manager
High-level interface for Delta Exchange WebSocket integration

CRITICAL FEATURES (DO NOT BREAK):
- Dual-channel fill detection (v2/user_trades PRIMARY, orders FALLBACK)
- Multi-layer deduplication (_processed_order_fills tracking)
- Maker/taker role extraction (fee monitoring)
- Commission tracking (profitability analysis)
- Thread-safe callback management

Manages:
- Connection lifecycle
- Channel subscriptions
- Event routing
- Data caching
- Integration with grid bot
"""

__VERSION__ = "1.0.0-stable"
__STATUS__ = "🔒 PRODUCTION-LOCKED"
__FINALIZED_DATE__ = "2025-10-21"
__OWNER__ = "Shailendra Singh Rajawat"

import os
import logging
import time
import threading
from typing import Dict, Optional, Callable, Any
from collections import deque
from datetime import datetime

from .delta_ws import DeltaWebSocket

log = logging.getLogger("runner")


class WebSocketManager:
    """
    WebSocket Manager for Grid Bot
    
    Provides high-level interface for:
    - Real-time price updates
    - Instant fill notifications
    - Position monitoring
    - Margin updates
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        symbol: str = "BTCUSD"
    ):
        """
        Initialize WebSocket Manager
        
        Args:
            api_key: Delta Exchange API key
            api_secret: Delta Exchange API secret
            symbol: Trading symbol
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.symbol = symbol
        
        # WebSocket client
        self.ws = None
        
        # Data cache (thread-safe)
        self.lock = threading.Lock()
        self.ticker_data = {}
        self.orderbook_data = {}
        self.recent_trades = deque(maxlen=100)
        
        # User data
        self.user_trades = deque(maxlen=100)
        self.orders = {}  # order_id -> order_data
        self.positions = {}  # symbol -> position_data
        self.margins = {}
        
        # Fill tracking for deduplication
        self._processed_order_fills = set()  # Track order_ids that had fills processed
        
        # Event callbacks
        self.fill_callbacks = []
        self.order_callbacks = []
        self.position_callbacks = []
        self.price_callbacks = []
        
        # Disconnect tracking for alerts
        self._disconnect_alert_sent = False
        self._disconnect_threshold = 60  # seconds
        
        # Initialize Telegram notifier
        self._notifier = None
        try:
            from bot.utils.notifier import TelegramNotifier
            self._notifier = TelegramNotifier()
        except Exception as e:
            log.debug(f"Telegram notifier not available: {e}")
        
        # ✅ FIX NOV 7 2025 (BUG #3): Adaptive REST polling for faster fill detection
        self._rest_polling_enabled = False
        self._rest_polling_thread = None
        self._rest_api_client = None
        self._rest_poll_interval = 10.0  # Default: 10s (adaptive: 2s high vol, 10s normal)
        self._volatility_threshold = 0.02  # 2% volatility threshold
        self._last_price = None
        self._price_history = deque(maxlen=20)  # Track last 20 prices for volatility
        
        # Fill detection latency monitoring
        self._fill_detection_times = deque(maxlen=100)  # Track last 100 fill detection times
        
        log.info(f"📡 WebSocket Manager initialized for {symbol}")
    
    def connect(self):
        """
        Connect to WebSocket and subscribe to channels
        """
        try:
            # Create WebSocket client (uses DELTA_WEBSOCKET_URL from env)
            self.ws = DeltaWebSocket(
                api_key=self.api_key,
                api_secret=self.api_secret
            )
            
            # Register event handlers
            self.ws.on('v2/user_trades', self._on_user_trade)  # ✅ FIXED: Was 'user_trades'
            self.ws.on('orders', self._on_order_update)
            self.ws.on('positions', self._on_position_update)
            self.ws.on('margins', self._on_margin_update)
            self.ws.on('v2/ticker', self._on_ticker_update)
            self.ws.on('l2_orderbook', self._on_orderbook_update)
            self.ws.on('all_trades', self._on_market_trade)
            
            # Connect
            self.ws.connect()
            
            # Subscribe to channels
            log.info("📡 Subscribing to channels...")
            
            # CRITICAL FIX: Private channels ALSO need symbols as LIST (per Delta docs)!
            # Use v2/user_trades (not user_trades) for fills
            self.ws.subscribe('v2/user_trades', [self.symbol])  # ✅ Symbol as list!
            self.ws.subscribe('orders', [self.symbol])  # ✅ Symbol as list!
            self.ws.subscribe('positions', ['all'])  # ✅ All positions
            self.ws.subscribe('margins')  # No symbol needed
            
            # Public channels (need symbol as list)
            self.ws.subscribe('v2/ticker', [self.symbol])
            self.ws.subscribe('l2_orderbook', [self.symbol])
            self.ws.subscribe('all_trades', [self.symbol])
            
            log.info("✅ WebSocket Manager connected and subscribed!")
            
        except Exception as e:
            log.error(f"❌ WebSocket Manager connection failed: {e}")
            raise
    
    def disconnect(self):
        """
        Disconnect from WebSocket
        """
        if self.ws:
            self.ws.disconnect()
            self.ws = None
    
    # ========================================================================
    # Event Handlers (Private)
    # ========================================================================
    
    def _on_user_trade(self, data: Dict):
        """
        Handle user trade (fill) event from v2/user_trades channel
        
        v2/user_trades format (abbreviated keys):
        - "sy": symbol
        - "f": fill_id
        - "o": order_id
        - "S": side
        - "s": size filled
        - "p": fill price
        - "r": role (maker/taker)
        
        This is THE MOST CRITICAL event for capital preservation!
        Instant fill detection = instant TP placement = less exposure
        """
        try:
            # v2/user_trades sends data directly, not in 'payload'
            # Check both formats for compatibility
            if 'payload' in data:
                payload = data['payload']
            else:
                payload = data
            
            # DEBUG: Log RAW fill event
            log.info(f"🔍 DEBUG: RAW v2/user_trade event: {payload}")
            
            # v2/user_trades uses abbreviated keys
            order_id = payload.get('o') or payload.get('order_id')  # 'o' for v2, fallback to old format
            fill_price_raw = payload.get('p') or payload.get('fill_price', 0)  # 'p' for v2
            fill_size_raw = payload.get('s') or payload.get('fill_size', 0)  # 's' for v2
            side = payload.get('S') or payload.get('side')  # 'S' for v2
            fill_role = payload.get('r', 'unknown')  # 'r' = role: 'maker' or 'taker'
            commission = payload.get('c', '0')  # 'c' = commission (negative = you earn)
            
            log.info(f"🔍 [FILL DEBUG] v2/user_trade: order_id={order_id}, price={fill_price_raw}, size={fill_size_raw}")
            
            # Validate critical fields (fuzzing fix)
            if order_id is None:
                log.error(f"⚠️ WebSocket fill event missing order_id: {payload}")
                return
            
            if not isinstance(order_id, (str, int)):
                log.error(f"⚠️ WebSocket fill event has invalid order_id type {type(order_id)}: {payload}")
                return
            
            # Convert and validate numeric fields
            try:
                fill_price = float(fill_price_raw)
                fill_size = float(fill_size_raw)
                
                if fill_price <= 0:
                    log.error(f"⚠️ WebSocket fill event has invalid fill_price {fill_price}: {payload}")
                    return
                
                if fill_size <= 0:
                    log.error(f"⚠️ WebSocket fill event has invalid fill_size {fill_size}: {payload}")
                    return
                    
            except (ValueError, TypeError) as e:
                log.error(f"⚠️ WebSocket fill event has non-numeric price/size: {e}, payload: {payload}")
                return
            
            with self.lock:
                self.user_trades.append({
                    'timestamp': datetime.now().isoformat(),
                    'data': payload
                })
                
                # Mark this order as processed to prevent duplicate processing via orders channel
                if order_id:
                    self._processed_order_fills.add(order_id)
            
            # Enhanced logging with maker/taker role and commission
            log.info(f"🎯 FILL DETECTED via WebSocket (v2/user_trades - PRIMARY): "
                    f"{side} {fill_size} @ {fill_price} as {fill_role.upper()} "
                    f"(commission: {commission}, order: {order_id})")
            
            # Normalize to standard format for callbacks
            normalized_fill = {
                'order_id': str(order_id),
                'fill_price': fill_price,
                'fill_size': fill_size,
                'side': side,
                'role': fill_role,
                'commission': commission
            }
            
            # Trigger callbacks
            for callback in self.fill_callbacks:
                try:
                    callback(normalized_fill)
                except Exception as e:
                    log.error(f"Error in fill callback: {e}")
        
        except Exception as e:
            log.error(f"Error handling user trade: {e}")
            import traceback
            log.error(traceback.format_exc())
    
    def _on_order_update(self, data: Dict):
        """
        Handle order update event
        
        Delta sends two types:
        1. Snapshot (action='snapshot'): Initial state, data in 'result' array
        2. Update (action='update'): Real-time updates, data in root level
        
        CRITICAL: Detects fills via reason="fill" as fallback
        when v2/user_trades doesn't work!
        """
        try:
            action = data.get('action', '')
            
            # Handle snapshot (initial orders list)
            if action == 'snapshot':
                result = data.get('result', [])
                log.debug(f"📋 Order snapshot received: {len(result)} orders")
                
                with self.lock:
                    for order in result:
                        order_id = order.get('id')
                        if order_id:
                            self.orders[order_id] = order
                
                # Trigger order callbacks for each
                for order in result:
                    for callback in self.order_callbacks:
                        try:
                            callback(order)
                        except Exception as e:
                            log.error(f"Error in order callback: {e}")
                return
            
            # Handle update (real-time order changes)
            # Data is at root level (not in 'payload')
            order_id = data.get('id')
            reason = data.get('reason', '')
            state = data.get('state', '')
            
            # DEBUG: Log updates (not snapshots)
            if action == 'update':
                log.info(f"📋 ORDER UPDATE: ID={order_id}, reason={reason}, state={state}")
            
            with self.lock:
                if order_id:
                    self.orders[order_id] = data
            
            # CRITICAL: Detect fills from order updates (FALLBACK ONLY)
            # ✅ FIX NOV 8: Support PARTIAL FILLS - track incremental fills per order
            # Strategy: Place TP for EACH partial fill immediately, next grid only when order complete
            if reason == 'fill':
                # Extract order data
                total_size = float(data.get('size', 0))
                unfilled_size = float(data.get('unfilled_size', 0))
                current_filled = total_size - unfilled_size
                avg_price = float(data.get('average_fill_price', 0))
                side = data.get('side', '')
                order_state = data.get('state', '')
                
                # Initialize partial fill tracking if needed
                if not hasattr(self, '_order_fill_tracking'):
                    self._order_fill_tracking = {}  # {order_id: last_filled_size}
                
                # Get previous filled amount for this order
                previous_filled = self._order_fill_tracking.get(order_id, 0)
                
                # Calculate INCREMENTAL fill (this fill only, not cumulative)
                new_fill_size = current_filled - previous_filled
                
                if new_fill_size > 0:
                    # NEW incremental fill detected!
                    fill_percentage = (current_filled / total_size * 100) if total_size > 0 else 0
                    
                    # Check if order is now complete
                    is_complete = (unfilled_size == 0 or order_state in ['closed', 'cancelled'])
                    
                    if is_complete:
                        log.info(f"🎯 FINAL FILL: {side} +{new_fill_size} lots @ avg ${avg_price:,.2f} | Total: {current_filled}/{total_size} (100%) [order: {order_id}]")
                    else:
                        log.info(f"⏳ PARTIAL FILL: {side} +{new_fill_size} lots @ avg ${avg_price:,.2f} | Total: {current_filled}/{total_size} ({fill_percentage:.1f}%) [order: {order_id}]")
                    
                    # Update tracking with current filled amount
                    self._order_fill_tracking[order_id] = current_filled
                    
                    # Trigger callback with INCREMENTAL fill data
                    normalized_fill = {
                        'order_id': str(order_id),
                        'fill_price': avg_price,              # Exchange's weighted average price
                        'fill_size': new_fill_size,           # ← INCREMENTAL (this fill only: 10, 47, 23...)
                        'cumulative_filled': current_filled,  # Total filled so far (for logging)
                        'total_order_size': total_size,       # Original order size
                        'unfilled_size': unfilled_size,       # Remaining unfilled
                        'side': side,
                        'is_complete': is_complete            # ← KEY: True when order 100% filled
                    }
                    
                    # 🔍 DEBUG NOV 8: Log callback execution
                    log.info(f"🔔 Triggering {len(self.fill_callbacks)} fill callback(s) for order {order_id}")
                    
                    if not self.fill_callbacks:
                        log.critical(f"❌ CRITICAL: NO FILL CALLBACKS REGISTERED! Fill will be lost!")
                        log.critical(f"   Order: {order_id}, Price: ${avg_price:,.0f}, Size: {new_fill_size}")
                    
                    for idx, callback in enumerate(self.fill_callbacks):
                        try:
                            log.info(f"   Calling callback #{idx+1}...")
                            callback(normalized_fill)
                            log.info(f"   ✅ Callback #{idx+1} completed")
                        except Exception as e:
                            log.error(f"❌ Error in fill callback #{idx+1}: {e}")
                            import traceback
                            log.error(traceback.format_exc())
                    
                    # Cleanup tracking when order complete
                    if is_complete:
                        log.info(f"✅ ORDER COMPLETE: {side} {current_filled} lots @ avg ${avg_price:,.2f} [order: {order_id}]")
                        
                        # Remove from tracking (free memory)
                        if order_id in self._order_fill_tracking:
                            del self._order_fill_tracking[order_id]
                        
                        # Add to processed fills (prevent duplicate processing)
                        self._processed_order_fills.add(order_id)
                        
                        # Clean old processed fills (keep last 1000)
                        if len(self._processed_order_fills) > 1000:
                            old_fills = list(self._processed_order_fills)[:500]
                            for old_fill in old_fills:
                                self._processed_order_fills.discard(old_fill)
                else:
                    # No new fill (duplicate WebSocket message or already processed)
                    log.debug(f"Duplicate fill message for order {order_id}, no new fill detected (current: {current_filled}, previous: {previous_filled})")
            
            # Trigger order callbacks (for non-snapshot updates)
            if action == 'update':
                for callback in self.order_callbacks:
                    try:
                        callback(data)
                    except Exception as e:
                        log.error(f"Error in order callback: {e}")
        
        except Exception as e:
            log.error(f"Error handling order update: {e}")
            import traceback
            log.error(traceback.format_exc())
    
    def _on_position_update(self, data: Dict):
        """
        Handle position update event
        
        Real-time position monitoring for risk management
        """
        try:
            payload = data.get('payload', {})
            symbol = payload.get('product_symbol')
            
            with self.lock:
                self.positions[symbol] = payload
            
            size = payload.get('size', 0)
            entry_price = payload.get('entry_price', 0)
            unrealized_pnl = payload.get('unrealized_pnl', 0)
            
            log.debug(f"📊 Position {symbol}: size={size}, entry={entry_price}, pnl={unrealized_pnl}")
            
            # Trigger callbacks
            for callback in self.position_callbacks:
                try:
                    callback(payload)
                except Exception as e:
                    log.error(f"Error in position callback: {e}")
        
        except Exception as e:
            log.error(f"Error handling position update: {e}")
    
    def _on_margin_update(self, data: Dict):
        """
        Handle margin update event
        
        Critical for liquidation protection!
        """
        try:
            payload = data.get('payload', {})
            
            with self.lock:
                self.margins = payload
            
            available_balance = payload.get('available_balance', 0)
            margin_used = payload.get('position_margin', 0)
            
            log.debug(f"💰 Margin: available={available_balance}, used={margin_used}")
        
        except Exception as e:
            log.error(f"Error handling margin update: {e}")
    
    def _on_ticker_update(self, data: Dict):
        """
        Handle ticker (price) update event
        
        Real-time price updates (no more polling!)
        """
        try:
            # Delta sends ticker data at root level, not under 'payload'
            # Check for both formats for compatibility
            if 'payload' in data:
                payload = data['payload']
            else:
                # Remove 'type' key and use rest as payload
                payload = {k: v for k, v in data.items() if k != 'type'}
            
            # Helper to safely convert to float
            def safe_float(value, default=0.0):
                try:
                    return float(value) if value else default
                except (ValueError, TypeError):
                    return default
            
            # Extract bid/ask from quotes object if present
            quotes = payload.get('quotes', {})
            best_bid = quotes.get('best_bid') or payload.get('best_bid')
            best_ask = quotes.get('best_ask') or payload.get('best_ask')
            
            with self.lock:
                # Normalize field names for easier access
                self.ticker_data = {
                    'last': safe_float(payload.get('close')),
                    'bid': safe_float(best_bid),
                    'ask': safe_float(best_ask),
                    'mark_price': safe_float(payload.get('mark_price')),
                    'spot_price': safe_float(payload.get('spot_price')),
                    'open': safe_float(payload.get('open')),
                    'high': safe_float(payload.get('high')),
                    'low': safe_float(payload.get('low')),
                    'volume': safe_float(payload.get('volume')),
                    'symbol': payload.get('symbol'),
                    'timestamp': payload.get('timestamp'),
                    # Keep original data too
                    '_raw': payload
                }
            
            last_price = self.ticker_data['last']
            bid = self.ticker_data['bid']
            ask = self.ticker_data['ask']
            
            # ✅ FIX NOV 7 2025 (BUG #3): Track price history for volatility calculation
            if last_price and last_price > 0:
                self._last_price = last_price
                self._price_history.append(last_price)
            
            log.debug(f"💹 Price: {last_price} (bid: {bid}, ask: {ask})")
            
            # Trigger callbacks
            for callback in self.price_callbacks:
                try:
                    callback(self.ticker_data)
                except Exception as e:
                    log.error(f"Error in price callback: {e}")
        
        except Exception as e:
            log.error(f"Error handling ticker update: {e}")
    
    def _on_orderbook_update(self, data: Dict):
        """
        Handle orderbook update event
        """
        try:
            payload = data.get('payload', {})
            
            with self.lock:
                self.orderbook_data = payload
            
            log.debug("📖 Orderbook updated")
        
        except Exception as e:
            log.error(f"Error handling orderbook update: {e}")
    
    def _on_market_trade(self, data: Dict):
        """
        Handle market trade event
        """
        try:
            payload = data.get('payload', {})
            
            with self.lock:
                self.recent_trades.append(payload)
        
        except Exception as e:
            log.error(f"Error handling market trade: {e}")
    
    # ========================================================================
    # Public API
    # ========================================================================
    
    def get_ticker(self) -> Optional[Dict]:
        """
        Get latest ticker data
        
        Returns:
            Ticker data or None
        """
        with self.lock:
            return self.ticker_data.copy() if self.ticker_data else None
    
    def get_last_price(self) -> Optional[float]:
        """
        Get last traded price
        
        Returns:
            Last price or None
        """
        ticker = self.get_ticker()
        if ticker:
            return float(ticker.get('close', 0))
        return None
    
    def get_positions(self) -> Dict:
        """
        Get all positions
        
        Returns:
            Dictionary of positions
        """
        with self.lock:
            return self.positions.copy()
    
    def get_position(self, symbol: str) -> Optional[Dict]:
        """
        Get position for specific symbol
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Position data or None
        """
        with self.lock:
            return self.positions.get(symbol)
    
    def get_margins(self) -> Dict:
        """
        Get margin data
        
        Returns:
            Margin data
        """
        with self.lock:
            return self.margins.copy()
    
    def get_orders(self) -> Dict:
        """
        Get all orders
        
        Returns:
            Dictionary of orders
        """
        with self.lock:
            return self.orders.copy()
    
    def get_order(self, order_id: str) -> Optional[Dict]:
        """
        Get specific order
        
        Args:
            order_id: Order ID
        
        Returns:
            Order data or None
        """
        with self.lock:
            return self.orders.get(order_id)
    
    # ========================================================================
    # Callback Registration
    # ========================================================================
    
    def on_fill(self, callback: Callable):
        """
        Register callback for fill events
        
        Args:
            callback: Function to call on fill
        """
        self.fill_callbacks.append(callback)
        log.info(f"✅ Registered fill callback (total callbacks: {len(self.fill_callbacks)})")
        log.info(f"   Callback function: {callback.__name__ if hasattr(callback, '__name__') else str(callback)}")
    
    def on_order_update(self, callback: Callable):
        """
        Register callback for order updates
        
        Args:
            callback: Function to call on order update
        """
        self.order_callbacks.append(callback)
        log.debug("Registered order callback")
    
    def on_position_update(self, callback: Callable):
        """
        Register callback for position updates
        
        Args:
            callback: Function to call on position update
        """
        self.position_callbacks.append(callback)
        log.debug("Registered position callback")
    
    def on_price_update(self, callback: Callable):
        """
        Register callback for price updates
        
        Args:
            callback: Function to call on price update
        """
        self.price_callbacks.append(callback)
        log.debug("Registered price callback")
    
    def is_connected(self) -> bool:
        """
        Check if WebSocket is connected
        
        Returns:
            True if connected and authenticated
        """
        return self.ws and self.ws.connected and self.ws.authenticated
    
    def check_health_and_alert(self):
        """
        Check WebSocket health and send Telegram alert if disconnected >60s
        Should be called periodically (e.g., every 30 seconds)
        """
        if not self.ws:
            return
        
        # Check if disconnected
        if not self.is_connected():
            # Get metrics to check disconnect duration
            metrics = self.ws.metrics
            if metrics.last_disconnect_time:
                disconnect_duration = time.time() - metrics.last_disconnect_time
                
                # Alert if disconnected >60s and haven't alerted yet
                if disconnect_duration > self._disconnect_threshold and not self._disconnect_alert_sent:
                    self._send_disconnect_alert(disconnect_duration, metrics.disconnect_reason)
                    self._disconnect_alert_sent = True
        else:
            # Reset alert flag when reconnected
            if self._disconnect_alert_sent:
                self._send_reconnect_notification()
                self._disconnect_alert_sent = False
    
    def _send_disconnect_alert(self, duration: float, reason: str):
        """Send Telegram alert about WebSocket disconnection"""
        if not self._notifier or not self._notifier.enabled:
            return
        
        message = (
            f"⚠️ WEBSOCKET DISCONNECTED!\n\n"
            f"Duration: {duration:.0f}s\n"
            f"Reason: {reason or 'Unknown'}\n"
            f"Symbol: {self.symbol}\n\n"
            f"Bot may be trading blind!\n"
            f"Check logs and restart if needed."
        )
        
        try:
            self._notifier.send(message)
            log.warning(f"📱 Sent WebSocket disconnect alert (duration: {duration:.0f}s)")
        except Exception as e:
            log.error(f"Failed to send disconnect alert: {e}")
    
    def _send_reconnect_notification(self):
        """Send Telegram notification about successful reconnection"""
        if not self._notifier or not self._notifier.enabled:
            return
        
        message = (
            f"✅ WEBSOCKET RECONNECTED\n\n"
            f"Connection restored for {self.symbol}\n"
            f"Bot is back online!"
        )
        
        try:
            self._notifier.send(message)
            log.info(f"📱 Sent WebSocket reconnect notification")
        except Exception as e:
            log.error(f"Failed to send reconnect notification: {e}")
    
    # ========================================================================
    # ✅ FIX NOV 7 2025 (BUG #3): Adaptive REST Polling for Faster Fill Detection
    # ========================================================================
    
    def start_adaptive_rest_polling(self, api_client):
        """
        Start adaptive REST polling thread for faster fill detection
        
        Polling interval adapts based on volatility:
        - High volatility (>2%): 2s intervals
        - Normal volatility: 10s intervals
        
        Args:
            api_client: DeltaRestClient instance for API calls
        """
        if self._rest_polling_enabled:
            log.warning("⚠️ Adaptive REST polling already enabled")
            return
        
        self._rest_polling_enabled = True
        self._rest_api_client = api_client
        
        self._rest_polling_thread = threading.Thread(
            target=self._adaptive_rest_polling_loop,
            name="AdaptiveRESTPolling",
            daemon=True
        )
        self._rest_polling_thread.start()
        log.info("✅ Adaptive REST polling started (2s high vol, 10s normal)")
    
    def stop_adaptive_rest_polling(self):
        """Stop adaptive REST polling thread"""
        self._rest_polling_enabled = False
        if self._rest_polling_thread:
            log.info("Stopping adaptive REST polling...")
    
    def _calculate_recent_volatility(self) -> float:
        """
        Calculate recent volatility from price history
        
        Returns:
            Volatility as percentage (0.0 - 1.0+)
        """
        if len(self._price_history) < 2:
            return 0.0
        
        prices = list(self._price_history)
        min_price = min(prices)
        max_price = max(prices)
        
        if min_price == 0:
            return 0.0
        
        volatility = (max_price - min_price) / min_price
        return volatility
    
    def _adaptive_rest_polling_loop(self):
        """
        Adaptive REST polling loop (runs in separate thread)
        
        Polls open orders via REST and checks for fills that WebSocket missed.
        Adapts polling interval based on market volatility.
        """
        log.info("🔄 Adaptive REST polling loop started")
        
        while self._rest_polling_enabled:
            try:
                # Calculate volatility
                volatility = self._calculate_recent_volatility()
                
                # Adapt polling interval
                if volatility > self._volatility_threshold:
                    poll_interval = 2.0  # High volatility: 2s
                    log.debug(f"🔥 High volatility ({volatility:.2%}) - polling every 2s")
                else:
                    poll_interval = 10.0  # Normal: 10s
                
                # Update interval
                self._rest_poll_interval = poll_interval
                
                # Reconcile open orders via REST
                self._reconcile_open_orders_via_rest()
                
                # Sleep until next poll
                time.sleep(poll_interval)
                
            except Exception as e:
                log.error(f"❌ Error in adaptive REST polling: {e}")
                time.sleep(5)  # Back off on error
        
        log.info("🛑 Adaptive REST polling loop stopped")
    
    def _reconcile_open_orders_via_rest(self):
        """
        Reconcile open orders via REST API
        
        Checks if any orders tracked as 'open' have actually filled
        (to catch fills that WebSocket missed)
        """
        if not self._rest_api_client:
            return
        
        try:
            # Get cached open orders
            with self.lock:
                cached_open_orders = {
                    oid: data for oid, data in self.orders.items()
                    if data.get('state') == 'open'
                }
            
            if not cached_open_orders:
                return  # No open orders to check
            
            # Query REST API for current order states
            for order_id, cached_data in list(cached_open_orders.items()):
                try:
                    # Query order state via REST
                    resp = self._rest_api_client.get_order(
                        product_id=cached_data.get('product_id'),
                        order_id=order_id
                    )
                    
                    if not resp.get('success') or 'result' not in resp:
                        continue
                    
                    rest_order = resp['result']
                    rest_state = rest_order.get('state', '')
                    
                    # Check if filled
                    if rest_state == 'filled' and order_id not in self._processed_order_fills:
                        # WebSocket missed this fill!
                        log.warning(f"⚠️ REST polling caught missed fill: Order {order_id}")
                        
                        # Simulate user_trade event to trigger fill detection
                        self._processed_order_fills.add(order_id)
                        
                        # Update cached order state
                        with self.lock:
                            if order_id in self.orders:
                                self.orders[order_id]['state'] = 'filled'
                        
                        # Trigger fill callbacks
                        fill_data = {
                            'order_id': order_id,
                            'price': rest_order.get('average_fill_price') or rest_order.get('limit_price'),
                            'size': rest_order.get('size'),
                            'side': rest_order.get('side'),
                            'fill_type': rest_order.get('order_type'),
                            'product_id': rest_order.get('product_id'),
                            'created_at': rest_order.get('created_at'),
                            '_detected_via': 'rest_polling'  # Flag for monitoring
                        }
                        
                        log.info(f"🔄 Triggering fill callbacks for REST-detected fill")
                        for callback in self.fill_callbacks:
                            try:
                                callback(fill_data)
                            except Exception as cb_err:
                                log.error(f"Error in fill callback: {cb_err}")
                    
                    # Check if cancelled
                    elif rest_state == 'cancelled':
                        with self.lock:
                            if order_id in self.orders:
                                self.orders[order_id]['state'] = 'cancelled'
                        log.debug(f"Order {order_id} is cancelled (updated from REST)")
                
                except Exception as order_err:
                    log.debug(f"Error checking order {order_id}: {order_err}")
                    continue
        
        except Exception as e:
            log.error(f"❌ Error in REST order reconciliation: {e}")


