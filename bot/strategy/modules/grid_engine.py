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

    # ── _is_cooldown_ready → MOVED here P6.2 ──
    def is_cooldown_ready(self) -> bool:
        """
        Check if cooldown period has elapsed since last order.

        Returns:
            True if ready to place order, False if in cooldown
        """
        if self.cooldown_seconds <= 0:
            return True

        elapsed = time.time() - self._last_order_time
        if elapsed < self.cooldown_seconds:
            remaining = self.cooldown_seconds - elapsed
            log.debug(f"Cooldown active: {remaining:.1f}s remaining")
            return False

        return True

    # ── _comprehensive_safety_check → MOVED here P6.3 ──
    async def comprehensive_safety_check(self, context: str = "order placement") -> tuple:
        """
        Comprehensive safety check - validates ALL safety mechanisms.

        Args:
            context: What action is being checked (for logging)

        Returns:
            (can_proceed, reason) - True if safe, False with reason if blocked
        """
        # 0. Early exit: Skip all checks if bot is already shutting down
        # JAN 27, 2026: Prevents Guardian signal errors during graceful shutdown
        if not self._get_running():
            return False, "Bot is shutting down"

        # 1. Check Guardian GO/STOP signal
        signal, reason = await self._guardian_ref.read_signal()
        if signal == 'STOP':
            halt_reason = (
                f"🛑 GUARDIAN HALT: Trading blocked by Guardian\n"
                f"   Reason: {reason}\n"
                f"   ⏰ Waiting for Guardian to publish GO signal..."
            )
            log.warning(halt_reason)
            return False, halt_reason

        # 2. Check cooldown period
        if not self.is_cooldown_ready():
            elapsed = time.time() - self._last_order_time
            remaining = self.cooldown_seconds - elapsed

            reason = (
                f"⏱️  COOLDOWN: Order placement rate-limited\n"
                f"   Seconds since last order: {elapsed:.1f}s\n"
                f"   Cooldown period: {self.cooldown_seconds:.1f}s\n"
                f"   ⏰ Can place order in: {remaining:.1f}s"
            )
            log.info(reason)
            return False, reason  # Return FULL detailed message

        # 3. Check price availability
        current_price = self._get_current_price()
        if not current_price:
            reason = (
                f"📍 NO PRICE DATA: Cannot place orders without current price\n"
                f"   ⏰ Waiting for price update from WebSocket..."
            )
            log.warning(reason)
            log.warning(f"   📍 Trading BLOCKED for: {context}")
            return False, reason  # Return FULL detailed message

        # 5. Check grid bounds
        if not self.grid_calc.is_within_bounds(current_price):
            reason = (
                f"📊 PRICE OUT OF GRID: Current price outside trading range\n"
                f"   Current Price: ${current_price:,.0f}\n"
                f"   Grid Lower: ${self.grid_calc.lower:,.0f}\n"
                f"   Grid Upper: ${self.grid_calc.upper:,.0f}\n"
                f"   ⏰ Can trade when price enters grid range"
            )
            log.info(reason)
            log.info(f"   📊 Trading BLOCKED for: {context}")
            return False, reason  # Return FULL detailed message

        # 6. Check price health (NOV 13 monitoring system)
        try:
            can_place, health_reason = self.price_monitor.can_place_orders()
            if not can_place:
                reason = (
                    f"🏥 PRICE HEALTH CHECK FAILED: {health_reason}\n"
                    f"   ⏰ Waiting for price data to stabilize..."
                )
                log.warning(reason)
                return False, reason  # Return FULL detailed message
        except Exception as e:
            log.debug(f"Price health check error (proceeding): {e}")

        # All checks passed
        return True, "All safety checks passed"

    # ── _should_recalculate_grid_level → MOVED here P6.2 ──
    def should_recalculate_grid_level(self, proposed_price: float) -> bool:
        if self._last_accepted_order_price is None:
            return True

        current_price = self._get_current_price()
        price_diff = abs(current_price - self._last_accepted_order_price)
        if price_diff < self._min_price_move_threshold:
            log.debug(f"Price moved only ${price_diff:.2f}, threshold is ${self._min_price_move_threshold:.2f} - skipping recalculation")
            return False

        return True

    # ── _log_detailed_grid_status → MOVED here P6.4 ──
    def log_detailed_grid_status(
        self,
        positions: list,
        pending_buy: Optional[Dict],
        pending_sell: Optional[Dict],
        current_price: float
    ) -> None:
        """
        Log detailed grid status with timeline for each position/loop.
        Shows mode, grid config, and detailed position info.
        """
        from datetime import datetime

        # Header with mode and grid configuration
        log.info("=" * 70)
        log.info(f"📊 GRID STATUS REPORT | Mode: {self.mode}")
        log.info(f"   Reference: ${self.grid_calc.ref:,.0f} | Step: ${self.grid_calc.step:,.0f}")
        log.info(f"   Lower: ${self.grid_calc.lower:,.0f} | Upper: ${self.grid_calc.upper:,.0f}")
        log.info(f"   Current Price: ${current_price:,.0f}")
        log.info("-" * 70)

        # Pending order info
        pending_order = pending_buy if self.mode == 'LONG' else pending_sell
        order_type = "BUY" if self.mode == 'LONG' else "SELL"

        if pending_order:
            pending_price = pending_order.get('price', 0)
            pending_time = pending_order.get('timestamp', 0)
            pending_order_id = pending_order.get('order_id', 'N/A')

            if pending_time:
                pending_dt = datetime.fromtimestamp(pending_time)
                time_str = pending_dt.strftime("%H:%M:%S")
            else:
                time_str = "N/A"

            distance = abs(current_price - pending_price)
            distance_pct = (distance / current_price * 100) if current_price > 0 else 0

            log.info(f"⏳ PENDING {order_type} ORDER:")
            log.info(f"   Price: ${pending_price:,.0f} | Distance: ${distance:,.0f} ({distance_pct:.2f}%)")
            log.info(f"   Order ID: {pending_order_id} | Placed at: {time_str}")
        else:
            log.info(f"⚠️  NO PENDING {order_type} ORDER")

        log.info("-" * 70)

        # Position details (Loops)
        if positions:
            log.info(f"📈 ACTIVE POSITIONS ({len(positions)} loops):")
            log.info("")

            # Sort positions by entry price (lowest first for LONG, highest first for SHORT)
            sorted_positions = sorted(
                positions,
                key=lambda p: p.get('entry_price', 0),
                reverse=(self.mode == 'SHORT')
            )

            for idx, pos in enumerate(sorted_positions, 1):
                entry_price = pos.get('entry_price', 0)
                tp_price = pos.get('tp_price', 0)
                entry_time = pos.get('timestamp', 0)
                position_id = pos.get('position_id', 'N/A')
                tp_order_id = pos.get('tp_order_id', 'N/A')
                entry_order_id = pos.get('entry_order_id', 'N/A')

                # Calculate PnL
                if self.mode == 'LONG':
                    pnl = current_price - entry_price
                else:
                    pnl = entry_price - current_price
                pnl_pct = (pnl / entry_price * 100) if entry_price > 0 else 0

                # Distance to TP
                tp_distance = abs(tp_price - current_price)
                tp_distance_pct = (tp_distance / current_price * 100) if current_price > 0 else 0

                # Format entry time
                if entry_time:
                    entry_dt = datetime.fromtimestamp(entry_time)
                    entry_time_str = entry_dt.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    entry_time_str = "N/A"

                # PnL color
                pnl_color = "\033[32m" if pnl > 0 else "\033[31m" if pnl < 0 else "\033[37m"

                log.info(f"   Loop {idx}:")
                log.info(f"      Entry: ${entry_price:,.0f} at {entry_time_str}")
                log.info(f"      TP Order: ${tp_price:,.0f} (ID: {tp_order_id})")
                log.info(f"      PnL: {pnl_color}${pnl:,.0f} ({pnl_pct:+.2f}%)\033[0m | Distance to TP: ${tp_distance:,.0f} ({tp_distance_pct:.2f}%)")
                log.info("")
        else:
            log.info("📭 NO ACTIVE POSITIONS")

        # Next grid level
        if self._fill_processor_ref:
            if self.mode == 'LONG':
                next_level = self._fill_processor_ref.calculate_next_grid_level('BUY', current_price)
                if next_level:
                    log.info(f"   → Next BUY level: ${next_level:,.0f}")
            else:
                next_level = self._fill_processor_ref.calculate_next_grid_level('SELL', current_price)
                if next_level:
                    log.info(f"   → Next SELL level: ${next_level:,.0f}")

        log.info("=" * 70)
