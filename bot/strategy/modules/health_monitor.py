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

    # ========================================================================
    # P2.3: Heartbeat Loop + Pending Order Formatter
    # ========================================================================

    def _format_pending_order_info(self, pending_order: Optional[Dict], current_price: float, side: str) -> str:
        if not pending_order:
            return ""

        pending_price = pending_order.get('price')
        if not pending_price:
            return ""

        try:
            pending_price_float = float(pending_price)
            current_price_float = float(current_price)

            if side == "buy":
                # FIX M2: Remove ANSI escape codes that corrupt log files
                color_indicator = "✅" if pending_price_float < current_price_float else "⚠️"
                label = "BUY"
            else:
                color_indicator = "✅" if pending_price_float > current_price_float else "⚠️"
                label = "SELL"

            return f" | {color_indicator} Pending {label} @ ${pending_price_float:,.0f}"
        except (ValueError, TypeError):
            label = "BUY" if side == "buy" else "SELL"
            return f" | Pending {label} @ ${pending_price}"

    async def heartbeat_loop(self) -> None:
        """Periodic heartbeat tasks with detailed status logging."""
        # FIX M1: Use config value and f-string
        heartbeat_interval = getattr(self.config.bot, 'heartbeat_seconds', 5)
        log.info(f"💓 Heartbeat loop started (every {heartbeat_interval}s)")

        heartbeat_counter = 0

        while self._get_running():
            try:
                await asyncio.sleep(heartbeat_interval)  # FIX M1: Use config interval
                heartbeat_counter += 1

                # NOV 13: Update watchdog timestamp
                self._set_last_heartbeat_time(time.time())

                # Update external heartbeat file every cycle (5s)
                await self.update_external_heartbeat()

                # Get state from position actor (every 15s for detailed status)
                if heartbeat_counter % 3 == 0:
                    state = await self.position_actor.ask("GET_STATE", {}, timeout=10)

                    positions = state.get("open_tranches", [])
                    pending_buy = state.get("pending_buy")
                    pending_sell = state.get("pending_sell")

                    # Get current price and volatility status
                    current_price = self._get_current_price()

                    # Get bid/ask from WebSocket if available
                    bid_price = None
                    ask_price = None
                    spread = None

                    try:
                        if hasattr(self.api_client, 'ws_manager') and hasattr(self.api_client.ws_manager, 'ticker_data'):
                            ticker_data = getattr(self.api_client.ws_manager, 'ticker_data', {})
                            bid_price = ticker_data.get('bid')
                            ask_price = ticker_data.get('ask')
                            if bid_price and ask_price and bid_price > 0 and ask_price > 0:
                                spread = ask_price - bid_price
                    except Exception:
                        pass

                    # Check volatility status with REAL DATA
                    # Volatility display REMOVED - Guardian monitors this
                    # Check Guardian log for volatility status
                    volatility_status = "🛡️  Guardian"
                    volatility_detail = ""

                    # Format detailed status log (matching old GridBot style)
                    if current_price:
                        # Color codes for positions
                        positions_str = f"\033[36m{len(positions)}/{self.max_positions}\033[0m"  # Cyan

                        # Price change indicator (green up, red down, white unchanged)
                        if self._last_hb_price is not None:
                            try:
                                current_float = float(current_price)
                                last_float = float(self._last_hb_price)
                                if current_float > last_float:
                                    price_color = "\033[32m"  # Green up
                                    price_change = "↑"
                                elif current_float < last_float:
                                    price_color = "\033[31m"  # Red down
                                    price_change = "↓"
                                else:
                                    price_color = "\033[37m"  # White unchanged
                                    price_change = "→"
                            except (ValueError, TypeError):
                                price_color = "\033[37m"
                                price_change = ""
                        else:
                            price_color = "\033[33m"  # Yellow for first time
                            price_change = ""

                        # Pending order info with color coding
                        pending_order = pending_buy if self.mode == 'LONG' else pending_sell
                        side = "buy" if self.mode == 'LONG' else "sell"
                        pending_info = self._format_pending_order_info(pending_order, current_price, side)

                        # Build detailed log message with bid/ask if available
                        # Add trading status indicator
                        trading_status = ""
                        if not self._get_initial_order_placed():
                            trading_status = " | ⏸️  NOT STARTED"
                        elif self._get_last_block_reason():
                            # If we have a pending order, bot is ACTIVE (not blocked)
                            if pending_buy or pending_sell:
                                trading_status = " | ✅ ACTIVE"
                                self._set_last_block_reason(None)  # Clear stale block reason
                            else:
                                trading_status = " | 🚫 BLOCKED"
                        else:
                            trading_status = " | ✅ ACTIVE"

                        if bid_price and ask_price:
                            log.info(
                                f"[HB] Positions: {positions_str} | "
                                f"Price: {price_color}${current_price:,.0f}{price_change}\033[0m | "
                                f"\033[35mBid: ${bid_price:,.1f} | Ask: ${ask_price:,.1f}\033[0m | "
                                f"Spread: ${spread:.1f} | "
                                f"Volatility: {volatility_status}{pending_info}{trading_status}"
                            )
                        else:
                            log.info(
                                f"[HB] Positions: {positions_str} | "
                                f"Price: {price_color}${current_price:,.0f}{price_change}\033[0m | "
                                f"Volatility: {volatility_status}{pending_info}{trading_status}"
                            )

                        # Store for next comparison
                        self._last_hb_price = current_price

                        # Log detailed grid status (every 60s instead of 30s)
                        if heartbeat_counter % 12 == 0:
                            if self._log_grid_status_callback:
                                self._log_grid_status_callback(positions, pending_buy, pending_sell, current_price)

            except Exception as e:
                log.error(f"Heartbeat error: {e}")
