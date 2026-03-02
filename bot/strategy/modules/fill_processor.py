"""
Fill Processor — extracted from async_gridbot.py Phase 5

Responsibilities:
- Fill deduplication (fill_id + order_id based)
- Saga dispatch (4 modes: LONG buy/sell, SHORT sell/buy)
- Saga completion tracking (metrics + missed order detection)
- FillMonitor integration (missed fill callback + order tracking)
- Post-order verification (Layer 2 safety)
- WebSocket order update handling (fill detection via orders channel)
- Next grid level calculation

NOT Responsible For:
- Order placement (→ GridEngine)
- Price tracking (→ WSLifecycle)
- Guardian signals (→ GuardianHandler)
- Exchange reconciliation (→ ExchangeSync)
"""

import asyncio
import time
from collections import deque
from typing import Dict, List, Optional, Set, Callable, Any

from loguru import logger as log

try:
    from bot.utils.human_logger import human_log
except ImportError:
    human_log = None

# Saga imports
from bot.strategy.sagas.fill_processing_saga import (
    create_buy_fill_saga,
    create_sell_fill_saga,
    create_short_entry_saga,
    create_short_tp_saga,
)


class FillProcessor:
    """Central fill processing, deduplication, and saga dispatch."""

    def __init__(
        self,
        position_actor,
        order_actor,
        saga_orchestrator,
        grid_calc,
        event_store,
        fill_monitor,
        pre_order_logger,
        anomaly_detector,
        mode: str,
        product_id: int,
        lot_size: float,
        max_positions: int,
        tp_offset: float,
        symbol: str,
    ):
        self.position_actor = position_actor
        self.order_actor = order_actor
        self.saga_orchestrator = saga_orchestrator
        self.grid_calc = grid_calc
        self.event_store = event_store
        self.fill_monitor = fill_monitor
        self.pre_order_logger = pre_order_logger
        self.anomaly_detector = anomaly_detector
        self.mode = mode
        self.product_id = product_id
        self.lot_size = lot_size
        self.max_positions = max_positions
        self.tp_offset = tp_offset
        self.symbol = symbol

        # Fill dedup state (same types as orchestrator)
        self._seen_fill_ids: Set[str] = set()
        self._fill_id_timestamps: deque = deque(maxlen=1000)
        self._fill_id_cleanup_interval: float = 300
        self._last_fill_id_cleanup: float = time.time()

        # Metrics
        self._fills_processed: int = 0
        self._sagas_completed: int = 0
        self._sagas_failed: int = 0

        # Shared references (set by orchestrator)
        self._recovered_grids: Set = set()  # reference to orchestrator's set
        self._guardian_ref = None  # reference to GuardianHandler for missed order tracking

        # Runtime callbacks
        self._get_running: Callable = lambda: False
        self._get_current_price: Callable = lambda: None
        self._get_initial_order_placed: Callable = lambda: False
        self._set_initial_order_placed: Callable = lambda v: None
        self._set_last_safety_check_time: Callable = lambda v: None
        self._api_client_ref = None  # for verify_order_after_placement

    def set_runtime_refs(self, **kwargs):
        """Wire runtime references after construction."""
        for key, value in kwargs.items():
            setattr(self, key, value)

    # ========================================================================
    # P5.2: Fill Deduplication Helpers
    # ========================================================================

    def is_fill_seen(self, fill_id: str) -> bool:
        return fill_id in self._seen_fill_ids

    def mark_fill_seen(self, fill_id: str) -> None:
        self._seen_fill_ids.add(fill_id)
        self._fill_id_timestamps.append((fill_id, time.time()))

    def is_order_fill_seen(self, order_id: str) -> bool:
        """Check if order fill already processed (deduplication by order_id)."""
        return f"order-{order_id}" in self._seen_fill_ids

    def mark_order_fill_seen(self, order_id: str) -> None:
        """Mark order fill as processed (deduplication by order_id)."""
        fill_marker = f"order-{order_id}"
        self._seen_fill_ids.add(fill_marker)
        self._fill_id_timestamps.append((fill_marker, time.time()))

    def cleanup_old_fill_ids(self) -> None:
        now = time.time()
        if now - self._last_fill_id_cleanup < self._fill_id_cleanup_interval:
            return

        cutoff_time = now - 300
        while self._fill_id_timestamps and self._fill_id_timestamps[0][1] < cutoff_time:
            old_fill_id, _ = self._fill_id_timestamps.popleft()
            self._seen_fill_ids.discard(old_fill_id)

        self._last_fill_id_cleanup = now
        log.debug(f"Cleaned up old fill IDs, current cache size: {len(self._seen_fill_ids)}")
