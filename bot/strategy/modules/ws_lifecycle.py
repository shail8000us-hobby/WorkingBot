"""
WebSocket Lifecycle & REST Fallback — extracted from async_gridbot.py Phase 4

Responsibilities:
- WebSocket handler registration and channel subscription
- WebSocket message loop consumer
- Ticker update handler (price tracking)
- Position update handler (liquidation detection)
- REST fallback activation/deactivation
- REST price polling and order status checking
- WebSocket reconnection
- Price fetching (both WS and REST)

NOT Responsible For:
- Order update (fill detection) handler (→ FillProcessor, Phase 5)
- Fill processing / saga creation (→ FillProcessor, Phase 5)
- Order placement logic (→ GridEngine, Phase 6)
- Grid calculations (→ GridEngine, Phase 6)
- Guardian signal reading (→ GuardianHandler, Phase 1)
- Health monitoring (→ HealthMonitor, Phase 2)
- Exchange sync (→ ExchangeSync, Phase 3)
"""

import asyncio
import time
from typing import Dict, Optional, Callable, Any
from loguru import logger as log

try:
    from bot.utils.human_logger import human_log
except ImportError:
    human_log = None


class WSLifecycle:
    """WebSocket connection management, price tracking, and REST fallback."""

    def __init__(
        self,
        api_client,
        position_actor,
        price_monitor,
        mode: str,
        symbol: str,
        product_id: int,
        max_positions: int,
        should_log_fn: Callable,
        config: dict,
    ):
        self.api_client = api_client
        self.position_actor = position_actor
        self.price_monitor = price_monitor
        self.mode = mode
        self.symbol = symbol
        self.product_id = product_id
        self.max_positions = max_positions
        self._should_log = should_log_fn
        self.config = config

        # WS / price state (owned by WSLifecycle)
        self.current_price: Optional[float] = None
        self._last_price: Optional[float] = None
        self._last_price_update: float = 0
        self._rest_fallback_active: bool = False
        self._rest_fallback_task = None
        self._last_price_log_time: float = 0

        # Runtime callbacks (set by orchestrator via set_runtime_refs)
        self._get_running: Callable = lambda: False
        self._get_start_time: Callable = lambda: time.time()
        self._on_ticker_callback: Optional[Callable] = None
        self._on_order_update_callback: Optional[Callable] = None
        self._process_fill_callback: Optional[Callable] = None
        self._full_exchange_sync_callback: Optional[Callable] = None

    def set_runtime_refs(self, **kwargs):
        """Wire runtime references after construction."""
        for key, value in kwargs.items():
            setattr(self, key, value)

    # ── Price Fetching ────────────────────────────────────────────────

    async def get_current_price(self) -> float:
        """
        Get current market price (async method for recovery engines).

        JAN 29 2026: Added to support recovery engines that need async price fetching.

        Returns:
            Current market price, or fetches from API if not available.
        """
        if self.current_price and self.current_price > 0:
            return self.current_price

        # Fetch if not available
        await self.fetch_current_price()
        return self.current_price or 0.0

    async def fetch_current_price(self) -> None:
        """Fetch current market price via REST API."""
        try:
            log.info(f"Fetching current price for {self.symbol}...")
            if human_log: human_log.fetching_price(self.symbol)
            ticker_data = await self.api_client.get_ticker(self.symbol)

            if ticker_data:
                # get_ticker returns a list, get first item
                if isinstance(ticker_data, list) and len(ticker_data) > 0:
                    ticker = ticker_data[0]
                else:
                    ticker = ticker_data

                # Try multiple price fields
                self.current_price = float(
                    ticker.get('close') or
                    ticker.get('last_price') or
                    ticker.get('mark_price') or
                    0
                )

                # Update price monitor so bot can pass health check at startup
                if self.current_price > 0:
                    self.price_monitor.update_price(self.current_price, source="REST_API")

                log.info(f"Current market price: ${self.current_price:,.2f}")
            else:
                log.warning("Could not fetch current price - will use WebSocket data")

        except Exception as e:
            log.error(f"Error fetching current price: {e}")

    # ── WebSocket Setup ───────────────────────────────────────────────

    def register_handlers(self) -> None:
        """Register WebSocket message handlers."""
        # NOTE: Removed v2/user_trades handler to prevent duplicate fill processing
        # Delta Exchange sends fills via orders channel (state=closed, reason=fill)
        self.api_client.ws_manager.register_handler("orders", self._on_order_update_callback)
        self.api_client.ws_manager.register_handler("positions", self._handle_position_update)
        self.api_client.ws_manager.register_handler("v2/ticker", self._handle_ticker_update)

    async def subscribe_channels(self) -> None:
        """Subscribe to WebSocket channels."""
        await self.api_client.subscribe_channels()

    async def message_loop(self) -> None:
        """WebSocket message processing loop."""
        log.info("📡 WebSocket message loop started")

        try:
            async for message in self.api_client.ws_manager.messages():
                if not self._get_running():
                    break

                # Messages are routed via handlers registered above

        except Exception as e:
            log.error(f"WebSocket message loop error: {e}")

        log.info("WebSocket message loop ended")

    # ── WebSocket Handlers ────────────────────────────────────────────

    async def _handle_position_update(self, message: Dict[str, Any]) -> None:
        """
        Handle position update messages from exchange.

        FIX H6: Detect exchange-initiated liquidations and position changes.
        If the exchange liquidates a position, we must update internal state
        to avoid placing orders against positions that no longer exist.
        """
        try:
            position_data = message if isinstance(message, dict) else {}

            # Check for relevant position fields
            product_id = position_data.get('product_id')
            if product_id and product_id != self.product_id:
                return  # Not our product

            size = position_data.get('size', 0)
            entry_price = position_data.get('entry_price', 0)
            liquidation_price = position_data.get('liquidation_price')
            margin = position_data.get('margin')

            # Detect liquidation: position size went to zero unexpectedly
            # or exchange sends a specific liquidation event
            is_liquidation = position_data.get('is_liquidated', False)
            reason = position_data.get('reason', '')

            if is_liquidation or 'liquidat' in str(reason).lower():
                log.critical("🚨 LIQUIDATION DETECTED via position channel!")
                log.critical(f"   Product: {product_id}")
                log.critical(f"   Size: {size}, Entry: {entry_price}")
                log.critical(f"   Reason: {reason}")

                # Send Telegram alert
                try:
                    from tools.telepush import send_telegram_alert
                    send_telegram_alert(
                        f"🚨 LIQUIDATION DETECTED!\n"
                        f"Size: {size}, Entry: ${entry_price:,.0f}\n"
                        f"Reason: {reason}",
                        self.config
                    )
                except Exception:
                    pass

                # Trigger emergency reconciliation to sync internal state
                log.critical("   🔄 Triggering emergency exchange sync...")
                asyncio.create_task(self._full_exchange_sync_callback())

            # Log significant position changes at debug level
            elif size != 0 or entry_price != 0:
                log.debug(f"📊 Position update: size={size}, entry=${entry_price:,.0f}, liq=${liquidation_price}")

        except Exception as e:
            log.error(f"Error handling position update: {e}", exc_info=True)

    async def _handle_ticker_update(self, message: Dict[str, Any]) -> None:
        """
        Handle ticker update messages and check for entry opportunities.
        This is the core order placement trigger.
        """
        try:
            # Extract price from ticker message (try multiple fields)
            ticker_data = (
                message.get('close') or
                message.get('last_traded_price') or
                message.get('mark_price') or
                message.get('last')
            )
            if not ticker_data:
                log.warning(f"⚠️ Ticker message has no price data: {message}")
                if human_log: human_log.missing_data("price")  # Trader-friendly alert
                return

            # Update current price
            price = float(ticker_data)
            old_price = self.current_price
            self.current_price = price
            self._last_price = price  # Store for heartbeat
            self._last_price_update = time.time()

            # NOV 20: Update UnifiedAPIClient price cache
            self.api_client.update_price_from_websocket(price)

            # NOV 13: Update price health monitor
            self.price_monitor.update_price(price, source="WEBSOCKET")

            # Debug: Log ticker updates (rate-limited to avoid spam)
            if self._should_log('websocket_ticker', interval_seconds=60):
                log.debug(f"💚 WebSocket ticker: ${price:,.2f} (age: 0s)")

            # Log price updates periodically (every 30s) or on significant changes
            time_since_log = time.time() - self._last_price_log_time

            price_change = abs(price - old_price) if old_price else 0
            significant_change = price_change > (price * 0.001)  # 0.1% change

            if time_since_log >= 30 or significant_change:
                # Get bid/ask if available
                bid = message.get('bid')
                ask = message.get('ask')

                if bid and ask:
                    spread = float(ask) - float(bid)
                    log.debug(
                        f"📊 [PRICE UPDATE] ${price:,.2f} | "
                        f"Bid: ${float(bid):,.2f} | Ask: ${float(ask):,.2f} | "
                        f"Spread: ${spread:.2f}"
                    )
                else:
                    # Price change indicator
                    if old_price:
                        if price > old_price:
                            indicator = "↑"
                        elif price < old_price:
                            indicator = "↓"
                        else:
                            indicator = "→"
                        log.debug(f"📊 [PRICE UPDATE] ${price:,.2f} {indicator}")
                        if human_log: human_log.price_data_flowing(price)  # Trader-friendly update
                    else:
                        log.debug(f"📊 [PRICE UPDATE] ${price:,.2f}")
                        if human_log: human_log.price_data_flowing(price)  # Trader-friendly update

                self._last_price_log_time = time.time()

            # Check if we should place an entry order
            await self._on_ticker_callback()

        except Exception as e:
            log.error(f"Ticker update error: {e}")

    # ── WebSocket Reconnection ────────────────────────────────────────

    async def reconnect_websocket(self) -> None:
        """Attempt to reconnect WebSocket."""
        try:
            log.info("🔄 [WEBSOCKET] Attempting reconnection...")

            # Disconnect existing connection
            await self.api_client.disconnect()
            await asyncio.sleep(2)

            # Reconnect
            await self.api_client.connect()

            # Re-subscribe to channels
            await self.subscribe_channels()

            log.info("✅ [WEBSOCKET] Reconnection successful")

        except Exception as e:
            log.error(f"❌ [WEBSOCKET] Reconnection failed: {e}")
            raise

    # ── REST Fallback Monitor ─────────────────────────────────────────

    async def rest_fallback_monitor_loop(self) -> None:
        """
        Monitor WebSocket health and activate REST fallback when needed.

        Activates REST polling when:
        - WebSocket has not sent price update for > 35s (Delta heartbeat + buffer)
        - No price data received at all

        Deactivates REST polling when:
        - WebSocket recovers (fresh price update received)

        Triggers WebSocket reconnection when:
        - Price is critically stale (>300s / 5 minutes)
        """
        log.info("🔄 [REST FALLBACK MONITOR] Loop started")
        log.debug(f"🔄 [REST FALLBACK MONITOR] self._get_running() = {self._get_running()}")
        if human_log: human_log.rest_fallback_active()  # Human-readable

        last_reconnect_attempt = 0
        reconnect_cooldown = 60.0  # Wait 60s between reconnection attempts
        ws_starvation_threshold = 40.0  # 30s Delta heartbeat + 10s buffer (increased from 35s)
        critically_stale_threshold = 300.0  # 5 minutes = dead connection

        try:
            while self._get_running():
                try:
                    # Check if we have price data
                    if self._last_price_update == 0:
                        # No price data yet - check how long we've been waiting
                        wait_time = time.time() - self._get_start_time()
                        if wait_time > 15 and not self._rest_fallback_active:
                            log.warning(f"🚨 [REST FALLBACK] No WebSocket data for {wait_time:.1f}s since start")
                            log.warning(f"   Activating REST fallback to get initial price...")
                            await self._activate_rest_fallback()

                    elif self._last_price_update > 0:
                        age = time.time() - self._last_price_update

                        # Check if critically stale (dead connection)
                        if age > critically_stale_threshold:
                            time_since_last_reconnect = time.time() - last_reconnect_attempt

                            if time_since_last_reconnect > reconnect_cooldown:
                                log.critical("=" * 80)
                                log.critical(f"🚨 CRITICAL: WebSocket DEAD for {age:.1f}s (>5 minutes)")
                                log.critical("   Attempting automatic reconnection...")
                                log.critical("=" * 80)

                                try:
                                    # Attempt to reconnect WebSocket
                                    await self.reconnect_websocket()
                                    last_reconnect_attempt = time.time()

                                    # Send Telegram alert (if notifications implemented)
                                    try:
                                        from bot.utils.notifier import TelegramNotifier
                                        notifier = TelegramNotifier()
                                        notifier.send(
                                            f"🔄 WebSocket Reconnection\n\n"
                                            f"Price was stale for {age:.1f}s\n"
                                            f"Automatic reconnection triggered\n\n"
                                            f"Monitoring for recovery..."
                                        )
                                    except Exception:
                                        pass  # Telegram not critical
                                except Exception as e:
                                    log.error(f"❌ WebSocket reconnection failed: {e}")

                        # Activate fallback if WebSocket starved
                        if age > ws_starvation_threshold and not self._rest_fallback_active:
                            log.warning(f"🚨 [REST FALLBACK] WebSocket starved for {age:.1f}s > {ws_starvation_threshold}s threshold")
                            await self._activate_rest_fallback()

                        # Deactivate fallback if WebSocket recovered
                        elif age < 10 and self._rest_fallback_active:
                            log.info(f"✅ [REST FALLBACK] WebSocket recovered (age: {age:.1f}s)")
                            await self._deactivate_rest_fallback()

                    # Check every second
                    await asyncio.sleep(1.0)

                except Exception as e:
                    log.error(f"❌ [REST FALLBACK MONITOR] Error in loop: {e}")
                    await asyncio.sleep(5.0)  # Back off on error

        except asyncio.CancelledError:
            log.info("🔄 [REST FALLBACK MONITOR] Loop cancelled")
            raise

        log.info("🔄 [REST FALLBACK MONITOR] Loop exited")
        log.debug(f"🔄 [REST FALLBACK MONITOR] Final self._get_running() = {self._get_running()}")

    async def _activate_rest_fallback(self) -> None:
        """Activate REST API polling as fallback for WebSocket."""
        if self._rest_fallback_active:
            return  # Already active

        log.warning("=" * 80)
        log.warning("🔄 ACTIVATING REST API FALLBACK - WebSocket Starvation Detected")
        if self._last_price_update > 0:
            log.warning(f"   Last WebSocket update: {time.time() - self._last_price_update:.1f}s ago")
        log.warning(f"   Polling interval: 5.0s")
        log.warning("=" * 80)

        self._rest_fallback_active = True

        # Start polling task
        self._rest_fallback_task = asyncio.create_task(
            self._rest_polling_loop(),
            name="RestFallbackPoller"
        )

        log.info("✅ [REST FALLBACK] Polling task started")

    async def _deactivate_rest_fallback(self) -> None:
        """Deactivate REST API fallback when WebSocket recovers."""
        if not self._rest_fallback_active:
            return  # Already inactive

        log.info("=" * 80)
        log.info("✅ DEACTIVATING REST API FALLBACK - WebSocket Recovered")
        log.info("=" * 80)

        self._rest_fallback_active = False

        # Cancel polling task
        if self._rest_fallback_task and not self._rest_fallback_task.done():
            log.info("⏳ [REST FALLBACK] Cancelling polling task...")
            self._rest_fallback_task.cancel()
            try:
                await self._rest_fallback_task
            except asyncio.CancelledError:
                pass  # Expected

        self._rest_fallback_task = None
        log.info("✅ [REST FALLBACK] Deactivated successfully")

    # ── REST Polling ──────────────────────────────────────────────────

    async def _rest_polling_loop(self) -> None:
        """
        Background loop that polls REST API for price and order updates.

        Runs while _rest_fallback_active == True.
        Polls every 5 seconds.
        """
        log.info("🔄 [REST FALLBACK] Polling loop started")

        while self._rest_fallback_active and self._get_running():
            try:
                # Poll current price
                await self._poll_price_via_rest()

                # Poll pending orders for fill detection
                await self._poll_pending_orders_via_rest()

                await asyncio.sleep(5.0)

            except asyncio.CancelledError:
                break  # Task cancelled
            except Exception as e:
                log.error(f"❌ [REST FALLBACK] Polling error: {e}")
                await asyncio.sleep(5.0)

        log.info("✅ [REST FALLBACK] Polling loop exited")

    async def _poll_price_via_rest(self) -> None:
        """Poll current price via REST API and update internal state."""
        try:
            # Get ticker from REST API (uses symbol, not product_id)
            ticker = await self.api_client.get_ticker(self.symbol)

            if ticker and "close" in ticker:
                price = float(ticker["close"])

                # Update internal price tracking
                self.current_price = price
                self._last_price_update = time.time()
                # NOTE: Do NOT update last WebSocket time - this is REST data

                log.debug(f"📊 [REST FALLBACK] Price update: ${price:,.2f}")

                # NOV 13: Update price health monitor with REST source
                self.price_monitor.update_price(price, source="REST_API")

            else:
                log.warning(f"⚠️  [REST FALLBACK] Invalid ticker response: {ticker}")

        except Exception as e:
            log.error(f"❌ [REST FALLBACK] Failed to poll price: {e}")

    async def _poll_pending_orders_via_rest(self) -> None:
        """Poll pending orders via REST API to detect fills."""
        try:
            # Get current state from position actor (NOV 13: Fixed ask() signature - needs payload)
            state_response = await self.position_actor.ask("GET_STATE", {}, timeout=10)
            if not state_response or "state" not in state_response:
                return

            state = state_response["state"]
            pending_buy = state.get("pending_buy")
            pending_sell = state.get("pending_sell")

            # Check each pending order
            for order_info in [pending_buy, pending_sell]:
                if not order_info:
                    continue

                order_id = order_info.get("order_id")
                expected_side = order_info.get("side", "buy")

                if not order_id:
                    continue

                # Query order status from exchange
                await self._check_order_status_rest(order_id, expected_side)

        except Exception as e:
            log.error(f"❌ [REST FALLBACK] Failed to poll pending orders: {e}")

    async def _check_order_status_rest(self, order_id: str, expected_side: str) -> None:
        """Check order status via REST API and process if filled."""
        try:
            # Get order details from exchange
            order = await self.api_client.get_order(order_id)

            if not order:
                log.warning(f"⚠️  [REST FALLBACK] Could not get order {order_id}")
                return

            state = order.get("state", "unknown")

            # If order is filled, process it
            if state == "filled":
                side = order.get("side", expected_side)
                avg_fill_price = float(order.get("average_fill_price") or order.get("limit_price", 0))
                filled_size = int(order.get("size", 0))

                log.info(f"🔔 [REST FALLBACK] FILL DETECTED via REST polling!")
                log.info(f"   Order ID: {order_id}")
                log.info(f"   Side: {side}, Price: ${avg_fill_price:,.2f}, Size: {filled_size}")

                # Process the fill through normal fill handling
                fill_data = {
                    "order_id": order_id,
                    "side": side,
                    "fill_price": avg_fill_price,
                    "fill_size": filled_size,
                    "timestamp": time.time(),
                    "source": "REST_POLLING"
                }

                await self._process_fill_callback(fill_data)

        except Exception as e:
            log.error(f"❌ [REST FALLBACK] Error checking order {order_id}: {e}")
