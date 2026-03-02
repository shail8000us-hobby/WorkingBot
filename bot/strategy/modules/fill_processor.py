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

    # ========================================================================
    # P5.3: Next Grid Level Calculator
    # ========================================================================

    def calculate_next_grid_level(self, side: str, current_price: float) -> Optional[float]:
        """
        Calculate the next grid level for order placement.
        Skips recovered grid levels to prevent duplicate positions.

        Args:
            side: 'BUY' or 'SELL'
            current_price: Current market price

        Returns:
            Next grid level price or None if out of range
        """
        try:
            if side == 'BUY':
                # For LONG mode, buy below current price
                # Find next grid level below current price
                next_level = self.grid_calc.lower
                while next_level < current_price:
                    next_level += self.grid_calc.step

                # Go one step back to get level below current price
                next_level -= self.grid_calc.step

                # Skip recovered grid levels (NOV 20)
                while (next_level in self._recovered_grids and
                       next_level >= self.grid_calc.lower):
                    next_level -= self.grid_calc.step

                # Ensure it's within grid bounds
                if next_level >= self.grid_calc.lower and next_level <= self.grid_calc.upper:
                    return next_level
            else:
                # For SHORT mode, sell above current price
                next_level = self.grid_calc.upper
                while next_level > current_price:
                    next_level -= self.grid_calc.step

                # Go one step forward to get level above current price
                next_level += self.grid_calc.step

                # Skip recovered grid levels (NOV 20)
                while (next_level in self._recovered_grids and
                       next_level <= self.grid_calc.upper):
                    next_level += self.grid_calc.step

                # Ensure it's within grid bounds
                if next_level >= self.grid_calc.lower and next_level <= self.grid_calc.upper:
                    return next_level

            return None

        except Exception as e:
            log.debug(f"Error calculating next grid level: {e}")
            return None

    # ========================================================================
    # P5.4: Saga Completion Tracking
    # ========================================================================

    async def track_saga_completion(self, task: asyncio.Task, correlation_id: str) -> None:
        """
        Track saga completion for metrics.

        CRITICAL FIX (Dec 11, 2025):
        Check if saga skipped order placement due to Guardian STOP.
        If so, track the missed order for retry when Guardian gives GO signal.

        DEC 23: Track successfully placed orders in Fill Monitor for exchange maintenance protection.
        """
        try:
            saga = await task  # Task returns the Saga object now, not just boolean

            if saga and saga.context.status == "completed":
                self._sagas_completed += 1
                log.info(f"Saga completed successfully: {correlation_id}")

                # DEC 23: Track placed orders in Fill Monitor
                for step_name, step_result in saga.context.step_results.items():
                    if isinstance(step_result, dict) and step_result.get('status') == 'ok':
                        # Check if this step placed an order
                        if 'order_id' in step_result and step_result['order_id']:
                            order_id = str(step_result['order_id'])

                            # Extract order details if available
                            price = step_result.get('price', 0)
                            size = step_result.get('size', 1)

                            # Infer side from step name
                            side = 'unknown'
                            if 'buy' in step_name.lower() or 'grid' in step_name.lower():
                                side = 'buy'
                            elif 'sell' in step_name.lower() or 'tp' in step_name.lower():
                                side = 'sell'

                            # Track in Fill Monitor
                            if price > 0 and side != 'unknown':
                                self.track_order_in_fill_monitor(order_id, side, price, size)

                                # DEC 23 Layer 2: Post-Order Verification (async, non-blocking)
                                # Verify order status immediately after placement
                                asyncio.create_task(self.verify_order_after_placement(
                                    order_id=order_id,
                                    expected_side=side,
                                    expected_price=price,
                                    timeout=5
                                ))

                # Check step_results for skipped orders due to Guardian STOP
                for step_name, step_result in saga.context.step_results.items():
                    if isinstance(step_result, dict):
                        if step_result.get('status') == 'skipped' and 'guardian_stop' in step_result.get('reason', ''):
                            # Extract missed order info
                            missed_order = step_result.get('missed_order')
                            if missed_order:
                                price = missed_order.get('price')
                                side = missed_order.get('side')
                                reason = step_result.get('reason', 'Unknown')

                                log.warning(f"📝 Tracking missed order for retry: {side.upper()} @ ${price:,.0f}")
                                if self._guardian_ref is not None:
                                    self._guardian_ref._missed_grid_orders.append((price, side, reason, time.time()))
            else:
                self._sagas_failed += 1
                log.warning(f"Saga failed/compensated: {correlation_id}")
        except Exception as e:
            self._sagas_failed += 1
            log.error(f"Saga execution error: {e}")

    def track_order_in_fill_monitor(self, order_id: str, side: str, price: float, size: int) -> None:
        """Placeholder — will be replaced with direct call in P5.6."""
        pass  # Replaced in P5.6

    async def verify_order_after_placement(self, order_id: str, expected_side: str, expected_price: float, timeout: int = 5) -> bool:
        """Placeholder — will be replaced with real impl in P5.6."""
        return False  # Replaced in P5.6
