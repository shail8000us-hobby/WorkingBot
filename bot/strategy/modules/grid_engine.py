"""
Grid Engine — extracted from async_gridbot.py Phase 6

Responsibilities:
- Safety gating (cooldown, price bounds, Guardian signal, price health)
- Order target calculation (next buy/sell level, recalculation threshold)
- Grid order placement (_place_grid_order, _place_initial_order)
- Entry trigger (_check_and_place_entry_order — called on every ticker update)
- Grid seeding (seed_missed_grid_levels)
- Grid status logging (_log_detailed_grid_status)

NOT Responsible For:
- Fill processing (→ FillProcessor)
- WebSocket lifecycle (→ WSLifecycle)
- Exchange reconciliation (→ ExchangeSync)
- Health monitoring (→ HealthMonitor)
- Guardian signal reading beyond GO/STOP (→ GuardianHandler)
"""

import asyncio
import time
from typing import Dict, List, Optional, Any

from loguru import logger as log

try:
    from bot.utils.human_logger import human_log
except ImportError:
    human_log = None


class GridEngine:
    """Grid order placement, safety gating, and entry trigger."""

    def __init__(
        self,
        position_actor,
        order_actor,
        grid_calc,
        price_monitor,
        pre_order_logger,
        anomaly_detector,
        config,
        mode: str,
        lot_size: float,
        product_id: int,
        cooldown_seconds: int,
        api_client,
        grid_step: float,
    ):
        # Injected dependencies
        self.position_actor = position_actor
        self.order_actor = order_actor
        self.grid_calc = grid_calc
        self.price_monitor = price_monitor
        self.pre_order_logger = pre_order_logger
        self.anomaly_detector = anomaly_detector
        self.config = config
        self.mode = mode
        self.lot_size = lot_size
        self.product_id = product_id
        self.cooldown_seconds = cooldown_seconds
        self.api_client = api_client

        # GridEngine-owned state
        self._last_order_time: float = 0
        self._last_accepted_order_price: Optional[float] = None
        self._min_price_move_threshold: float = grid_step / 2
        self._was_halted: bool = False
        self._last_block_reason: Optional[str] = None
        self._last_safety_block_log: float = 0
        self._order_placement_lock = asyncio.Lock()

        # Runtime refs (set via set_runtime_refs after actors start)
        self._get_running = lambda: True
        self._get_current_price = lambda: None
        self._get_initial_order_placed = lambda: False
        self._set_initial_order_placed = lambda v: None
        self._guardian_ref = None
        self._state_coordinator_ref = None
        self._fill_processor_ref = None
        self._recovered_grids: set = set()

    def set_runtime_refs(self, **kwargs):
        """Wire live references after all components are constructed."""
        for key, val in kwargs.items():
            setattr(self, key, val)
