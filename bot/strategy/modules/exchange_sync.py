"""
Exchange Sync & Reconciliation — extracted from async_gridbot.py Phase 3

Responsibilities:
- Reconcile orphaned orders at startup
- Clean up misaligned grid orders
- Reconcile fills after WebSocket reconnect
- Full exchange sync (8-step orphan/TP recovery)
- Ensure grid coverage
- Detect and handle exchange maintenance
- Sync positions from exchange on startup

NOT Responsible For:
- Order placement logic (→ GridEngine, Phase 6)
- Fill processing (→ FillProcessor, Phase 5)
- Guardian signal reading (→ GuardianHandler, Phase 1)
- Health monitoring (→ HealthMonitor, Phase 2)
"""

import asyncio
import time
from typing import Dict, List, Optional, Callable, Any
from loguru import logger as log


class ExchangeSync:
    """Exchange state synchronization and reconciliation."""

    def __init__(
        self,
        api_client,
        position_actor,
        order_actor,
        event_store,
        grid_calc,
        mode: str,
        symbol: str,
        product_id: int,
        grid_step: float,
        lot_size: float,
        max_positions: int,
        tp_offset: float,
        should_log_fn: Callable,
    ):
        self.api_client = api_client
        self.position_actor = position_actor
        self.order_actor = order_actor
        self.event_store = event_store
        self.grid_calc = grid_calc
        self.mode = mode
        self.symbol = symbol
        self.product_id = product_id
        self.grid_step = grid_step
        self.lot_size = lot_size
        self.max_positions = max_positions
        self.tp_offset = tp_offset
        self._should_log = should_log_fn

        # Runtime references (set by orchestrator via set_runtime_refs)
        self._get_running: Callable = lambda: False
        self._get_current_price: Callable = lambda: None
        self._fetch_current_price_callback: Optional[Callable] = None
        self._process_fill_callback: Optional[Callable] = None

    def set_runtime_refs(self, **kwargs):
        """Wire runtime references after construction."""
        for key, value in kwargs.items():
            setattr(self, key, value)
