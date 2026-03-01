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
