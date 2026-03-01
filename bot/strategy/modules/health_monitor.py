"""
Health Monitor — extracted from async_gridbot.py Phase 2

Responsibilities:
- Heartbeat loop (5s cycle, 15s detailed status, 60s grid report)
- Monitoring loop (5s snapshot JSON writes)
- Actor/saga/WebSocket health checks
- Memory usage monitoring
- Event loop watchdog (freeze detection)
- External heartbeat file writer

NOT Responsible For:
- Order placement
- Fill processing
- Guardian signal reading (→ GuardianHandler)
- Exchange sync
"""

import asyncio
import gc
import json
import os
import time
from pathlib import Path
from typing import Dict, Optional, Callable, Any

import aiofiles
from loguru import logger as log

try:
    from bot.utils.human_logger import human_log
except ImportError:
    human_log = None


class HealthMonitor:
    """Read-only health monitoring and heartbeat system."""

    def __init__(
        self,
        position_actor,
        order_actor,
        saga_orchestrator,
        api_client,
        grid_calc,
        price_monitor,
        fill_monitor,
        mode: str,
        symbol: str,
        symbol_name: str,
        max_positions: int,
        instance_name: str,
        config,
        should_log_fn: Callable,
    ):
        self.position_actor = position_actor
        self.order_actor = order_actor
        self.saga_orchestrator = saga_orchestrator
        self.api_client = api_client
        self.grid_calc = grid_calc
        self.price_monitor = price_monitor
        self.fill_monitor = fill_monitor
        self.mode = mode
        self.symbol = symbol
        self.symbol_name = symbol_name
        self.max_positions = max_positions
        self.instance_name = instance_name
        self.config = config
        self._should_log = should_log_fn

        # Watchdog state
        self._watchdog_timeout = 60.0
        self._watchdog_check_interval = 10.0

        # Heartbeat tracking
        self._last_hb_price = None

        # Runtime references (set by orchestrator)
        self._get_running: Callable = lambda: False
        self._get_current_price: Callable = lambda: None
        self._get_start_time: Callable = lambda: 0
        self._get_fills_processed: Callable = lambda: 0
        self._get_sagas_completed: Callable = lambda: 0
        self._get_sagas_failed: Callable = lambda: 0
        self._get_last_price_update: Callable = lambda: 0
        self._get_initial_order_placed: Callable = lambda: False
        self._get_last_heartbeat_time: Callable = lambda: 0
        self._set_last_heartbeat_time: Callable = lambda v: None
        self._get_last_block_reason: Callable = lambda: None
        self._set_last_block_reason: Callable = lambda v: None
        self._get_tp_offset: Callable = lambda: 500
        self._get_pre_order_logger: Callable = lambda: None
        self._get_anomaly_detector: Callable = lambda: None
        self._tp_retry_callback: Optional[Callable] = None
        self._check_guardian_transitions_callback: Optional[Callable] = None
        self._log_grid_status_callback: Optional[Callable] = None
        self._format_pending_order_callback: Optional[Callable] = None
        self._emergency_stop_callback: Optional[Callable] = None

    def set_runtime_refs(self, **kwargs):
        """Wire runtime references after construction."""
        for key, value in kwargs.items():
            setattr(self, key, value)

    # ========================================================================
    # P2.2: External Heartbeat File Writer
    # ========================================================================

    async def update_external_heartbeat(self) -> None:
        """
        Update external .heartbeat file for PM2 monitoring.
        This file is monitored by the heartbeat-monitor process.
        """
        try:
            heartbeat_file = Path(".heartbeat")

            heartbeat_data = {
                "timestamp": time.time(),
                "pid": os.getpid(),
                "mode": self.mode,
                "symbol": self.symbol,
                "uptime": time.time() - self._get_start_time(),
                "status": "running",  # Guardian controls halt state
                "last_price": self._get_current_price(),
                "fills_processed": self._get_fills_processed()
            }

            # Write heartbeat file (async I/O)
            async with aiofiles.open(heartbeat_file, "w") as f:
                await f.write(json.dumps(heartbeat_data, indent=2))

        except Exception as e:
            log.debug(f"Guardian health export error: {e}")
