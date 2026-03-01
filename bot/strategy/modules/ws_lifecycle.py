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
        self._on_position_update_callback: Optional[Callable] = None
        self._on_ticker_update_callback: Optional[Callable] = None
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
        self.api_client.ws_manager.register_handler("positions", self._on_position_update_callback)
        self.api_client.ws_manager.register_handler("v2/ticker", self._on_ticker_update_callback)

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
