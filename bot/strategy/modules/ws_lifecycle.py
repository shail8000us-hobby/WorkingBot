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
    from bot.utils.human_log import human_log
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
            human_log.fetching_price(self.symbol)
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
                human_log.missing_data("price")  # Trader-friendly alert
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
                        human_log.price_data_flowing(price)  # Trader-friendly update
                    else:
                        log.debug(f"📊 [PRICE UPDATE] ${price:,.2f}")
                        human_log.price_data_flowing(price)  # Trader-friendly update

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
