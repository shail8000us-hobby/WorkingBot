"""
Guardian Signal Handler — extracted from async_gridbot.py Phase 1

Responsibilities:
- Read Guardian GO/STOP signal from EventStore
- Detect signal transitions (STOP→GO, GO→STOP)
- Manage missed grid orders during STOP periods
- Retry missed orders on GO resume
- Multi-step missed grid recovery (A3 fix)
- Cancel pending entry orders on STOP
- Resume grid trading on GO
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from loguru import logger as log

from bot.strategy.modules.event_store import EventStore, EventType

try:
    from bot.utils.human_logger import human_log
except ImportError:
    human_log = None


class GuardianHandler:
    """Handles Guardian signal reading, transitions, and missed-order recovery."""

    def __init__(
        self,
        event_store: EventStore,
        position_actor,       # PositionManagerActor
        order_actor,          # OrderManagerActor
        grid_calc,            # GridCalculator
        mode: str,            # "LONG" or "SHORT"
        grid_step: float,
        max_positions: int,
        lot_size: float,
        ref_price: float,
        should_log_fn: Callable,  # (key: str, interval: float) -> bool
    ):
        self.event_store = event_store
        self.position_actor = position_actor
        self.order_actor = order_actor
        self.grid_calc = grid_calc
        self.mode = mode
        self.grid_step = grid_step
        self.max_positions = max_positions
        self.lot_size = lot_size
        self.ref_price = ref_price
        self._should_log = should_log_fn

        # Guardian state
        self._last_guardian_signal: Optional[str] = None
        self._guardian_transition_time: float = 0
        self._missed_grid_orders: List = []

        # Runtime references (set by orchestrator via set_runtime_refs)
        self._get_running: Callable = lambda: False
        self._get_current_price: Callable = lambda: None
        self._set_running: Callable = lambda v: None
        self._get_started_once: Callable = lambda: False

    def set_runtime_refs(
        self,
        get_running: Callable,        # () -> bool
        get_current_price: Callable,   # () -> Optional[float]
        set_running: Callable,         # (bool) -> None
        get_started_once: Callable,    # () -> bool
    ):
        """Wire runtime references after construction."""
        self._get_running = get_running
        self._get_current_price = get_current_price
        self._set_running = set_running
        self._get_started_once = get_started_once
