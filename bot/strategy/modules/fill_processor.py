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

    # ========================================================================
    # P5.6: Fill Monitor Integration — track orders + post-placement verification
    # ========================================================================

    def track_order_in_fill_monitor(self, order_id: str, side: str, price: float, size: int) -> None:
        """
        Track an order in Fill Monitor after placement.

        This enables Fill Monitor to verify the order status and detect fills
        that may have been missed by WebSocket.

        Args:
            order_id: Exchange order ID
            side: Order side ('buy' or 'sell')
            price: Order price
            size: Order size
        """
        try:
            self.fill_monitor.track_order(
                order_id=order_id,
                side=side,
                price=price,
                size=size,
                placed_at=time.time()
            )
            log.debug(f"[FillMonitor] Tracking order {order_id}: {side.upper()} @ ${price:,.0f}")
        except Exception as e:
            log.error(f"❌ Error tracking order in Fill Monitor: {e}")

    async def verify_order_after_placement(self, order_id: str, expected_side: str, expected_price: float, timeout: int = 5) -> bool:
        """
        Verify order status immediately after placement (Layer 2).

        This catches fills that happen during WebSocket reconnection or exchange maintenance.
        Checks every 1 second for up to 5 seconds.

        Args:
            order_id: Order ID to verify
            expected_side: Expected order side ('buy' or 'sell')
            expected_price: Expected order price
            timeout: Maximum time to wait (seconds)

        Returns:
            True if order filled immediately, False otherwise
        """
        try:
            start_time = time.time()
            check_count = 0

            while time.time() - start_time < timeout:
                await asyncio.sleep(1)
                check_count += 1

                # Query exchange for order status
                order = await self._api_client_ref.get_order(order_id)

                if not order:
                    log.warning(f"[PostOrderVerification] Order {order_id} not found on exchange")
                    return False

                state = order.get('state', '').lower()
                unfilled_size = order.get('unfilled_size', 0)

                # Check if filled
                if state == 'closed' and unfilled_size == 0:
                    avg_price = order.get('average_fill_price', expected_price)
                    log.warning("=" * 80)
                    log.warning("⚡ IMMEDIATE FILL DETECTED (Post-Order Verification)!")
                    log.warning(f"   Order ID: {order_id}")
                    log.warning(f"   Side: {expected_side.upper()}")
                    log.warning(f"   Expected Price: ${expected_price:,.0f}")
                    log.warning(f"   Filled Price: ${avg_price:,.0f}")
                    log.warning(f"   Detection Time: {check_count}s after placement")
                    log.warning(f"   Reason: Order filled before WebSocket notification")
                    log.warning("=" * 80)

                    # Create fill data and process
                    fill_data = {
                        'id': f'immediate-fill-{order_id}-{int(time.time()*1000)}',
                        'order_id': str(order_id),
                        'side': expected_side,
                        'price': avg_price,
                        'size': order.get('size', 1),
                        'product_id': self.product_id,
                        'is_complete': True,
                        'unfilled_size': 0
                    }

                    await self.process_fill(fill_data)
                    return True

                # Check if cancelled (shouldn't happen but handle it)
                if state == 'cancelled':
                    log.info(f"[PostOrderVerification] Order {order_id} was cancelled")
                    return False

            # Timeout - order still open (normal case)
            log.debug(f"[PostOrderVerification] Order {order_id} verified as open after {timeout}s")
            return False

        except Exception as e:
            log.error(f"❌ [PostOrderVerification] Error verifying order {order_id}: {e}")
            return False

    # ========================================================================
    # P5.5: THE CRITICAL METHOD — process_fill
    # ========================================================================

    async def process_fill(self, fill_data: Dict[str, Any]) -> None:
        """
        Process fill via saga.

        CRITICAL: Multiple systems can call this (WebSocket, Fill Monitor, Post-Order Verification).
        Deduplication prevents double-processing using BOTH fill_id AND order_id.

        Args:
            fill_data: Fill information
        """
        try:
            fill_id = str(fill_data.get('id', ''))
            order_id = str(fill_data.get("order_id", ''))

            # CRITICAL: Check BOTH fill_id and order_id for deduplication
            # Fill Monitor creates synthetic fill_ids, so order_id is the true unique key
            if self.is_fill_seen(fill_id):
                log.debug(f"⏭️  Skipping already processed fill: {fill_id}")
                return

            if order_id and self.is_order_fill_seen(order_id):
                log.debug(f"⏭️  Skipping already processed order fill: {order_id}")
                return

            # Mark BOTH fill_id and order_id as seen
            self.mark_fill_seen(fill_id)
            if order_id:
                self.mark_order_fill_seen(order_id)
                # Mark in Fill Monitor too (prevents Fill Monitor from re-detecting)
                self.fill_monitor.mark_filled(order_id, source="processing")

            self.cleanup_old_fill_ids()

            fill_product = fill_data.get('product_id')
            if fill_product and fill_product != self.product_id:
                log.debug(f"⏭️  Ignoring fill for different product: {fill_product} (bot trades product_id={self.product_id})")
                return

            order_id = fill_data.get("order_id")

            self._fills_processed += 1

            # Generate correlation ID
            correlation_id = f"fill-{fill_data.get('id', '')}-{int(time.time()*1000)}"

            # Prepare fill data
            # CRITICAL FIX NOV 14: Don't default is_complete to True
            # Partial fills must be explicitly marked, otherwise position size will be wrong
            is_complete = fill_data.get("is_complete")
            if is_complete is None:
                # If not provided, check unfilled_size
                unfilled_size = fill_data.get("unfilled_size", 0)
                is_complete = (unfilled_size == 0)
                log.warning(f"⚠️  is_complete not provided in fill data, inferring from unfilled_size: {is_complete}")

            processed_fill = {
                "order_id": fill_data.get("order_id"),
                "fill_price": float(fill_data.get("price", 0)),
                "fill_size": int(fill_data.get("size", 0)),
                "side": fill_data.get("side"),
                "is_complete": is_complete
            }

            # Enhanced logging (matching old GridBot style)
            log.info(f"🔔 Processing fill: {processed_fill['side'].upper()} {processed_fill['fill_size']} @ ${processed_fill['fill_price']:,.0f}")

            # Mark bot as started on first fill
            if not self._get_initial_order_placed():
                self._set_initial_order_placed(True)
                log.info("✅ Bot marked as ACTIVE (first fill processed)")

            # Human-readable narrative logging
            if human_log:
                human_log.order_filled(
                    processed_fill.get("order_id", "unknown"),
                    processed_fill["side"].upper(),
                    processed_fill["fill_price"]
                )

            # Create appropriate saga based on MODE and SIDE
            if self.mode == "LONG":
                if processed_fill["side"] == "buy":
                    # LONG mode: BUY = Entry
                    # Calculate TP price for new position
                    tp_price = processed_fill['fill_price'] + self.grid_calc.step
                    log.info(f"   💰 New position opened | Entry: ${processed_fill['fill_price']:,.0f} → Target: ${tp_price:,.0f}")

                    # Get current position count
                    state = await self.position_actor.ask("GET_STATE", {})
                    current_positions = len(state.get("open_tranches", []))
                    log.info(f"   📊 Active positions: {current_positions + 1}/{self.max_positions}")

                    # Human-readable position update
                    if human_log:
                        human_log.position_updated(size=current_positions + 1)

                    # Calculate next buy level
                    next_buy = self.calculate_next_grid_level('BUY', processed_fill['fill_price'])
                    if next_buy:
                        log.info(f"   ⬇️  Next BUY level: ${next_buy:,.0f}")

                    saga = await create_buy_fill_saga(
                        fill_data=processed_fill,
                        correlation_id=correlation_id,
                        position_actor=self.position_actor,
                        order_actor=self.order_actor,
                        grid_calc=self.grid_calc,
                        event_store=self.event_store,
                        mode=self.mode
                    )
                else:  # sell
                    # LONG mode: SELL = TP close
                    # Get position details for profit calculation
                    state = await self.position_actor.ask("GET_STATE", {})
                    positions = state.get("open_tranches", [])

                    # Find the position that was closed
                    order_id = processed_fill.get("order_id")
                    closed_position = None
                    for pos in positions:
                        if pos.get("tp_order_id") == order_id:
                            closed_position = pos
                            break

                    if closed_position:
                        entry_price = closed_position.get("entry_price", 0)
                        exit_price = processed_fill['fill_price']
                        profit = exit_price - entry_price
                        profit_pct = (profit / entry_price * 100) if entry_price > 0 else 0

                        log.info(f"   ✅ Position closed | Entry: ${entry_price:,.0f} → Exit: ${exit_price:,.0f}")
                        log.info(f"   💵 Profit: ${profit:,.0f} ({profit_pct:+.2f}%)")

                    # Get updated position count
                    remaining_positions = len(positions) - 1
                    log.info(f"   📊 Active positions: {remaining_positions}/{self.max_positions}")

                    # Human-readable position update with PnL
                    if human_log:
                        if closed_position:
                            human_log.position_updated(size=remaining_positions, pnl=profit)
                        else:
                            human_log.position_updated(size=remaining_positions)

                    saga = await create_sell_fill_saga(
                        fill_data=processed_fill,
                        correlation_id=correlation_id,
                        position_actor=self.position_actor,
                        order_actor=self.order_actor,
                        grid_calc=self.grid_calc,
                        event_store=self.event_store,
                        mode=self.mode
                    )

            elif self.mode == "SHORT":
                if processed_fill["side"] == "sell":
                    # SHORT mode: SELL = Entry
                    # Calculate TP price for new position (below entry)
                    tp_price = processed_fill['fill_price'] - self.grid_calc.step
                    log.info(f"   💰 New SHORT position opened | Entry: ${processed_fill['fill_price']:,.0f} → Target: ${tp_price:,.0f}")

                    # Get current position count
                    state = await self.position_actor.ask("GET_STATE", {})
                    current_positions = len(state.get("open_tranches", []))
                    log.info(f"   📊 Active positions: {current_positions + 1}/{self.max_positions}")

                    # Human-readable position update
                    if human_log:
                        human_log.position_updated(size=current_positions + 1)

                    # Calculate next sell level (UP from current)
                    next_sell = self.calculate_next_grid_level('SELL', processed_fill['fill_price'])
                    if next_sell:
                        log.info(f"   ⬆️  Next SELL level: ${next_sell:,.0f}")

                    saga = await create_short_entry_saga(
                        fill_data=processed_fill,
                        correlation_id=correlation_id,
                        position_actor=self.position_actor,
                        order_actor=self.order_actor,
                        grid_calc=self.grid_calc,
                        event_store=self.event_store
                    )
                else:  # buy
                    # SHORT mode: BUY = TP close
                    # Get position details for profit calculation
                    state = await self.position_actor.ask("GET_STATE", {})
                    positions = state.get("open_tranches", [])

                    # Find the position that was closed
                    order_id = processed_fill.get("order_id")
                    closed_position = None
                    for pos in positions:
                        if pos.get("tp_order_id") == order_id:
                            closed_position = pos
                            break

                    if closed_position:
                        entry_price = closed_position.get("entry_price", 0)
                        exit_price = processed_fill['fill_price']
                        profit = entry_price - exit_price  # SHORT profit
                        profit_pct = (profit / entry_price * 100) if entry_price > 0 else 0

                        log.info(f"   ✅ SHORT position closed | Entry: ${entry_price:,.0f} → Exit: ${exit_price:,.0f}")
                        log.info(f"   💵 Profit: ${profit:,.0f} ({profit_pct:+.2f}%)")

                    # Get updated position count
                    remaining_positions = len(positions) - 1
                    log.info(f"   📊 Active positions: {remaining_positions}/{self.max_positions}")

                    # Human-readable position update with PnL
                    if human_log:
                        if closed_position:
                            human_log.position_updated(size=remaining_positions, pnl=profit)
                        else:
                            human_log.position_updated(size=remaining_positions)

                    saga = await create_short_tp_saga(
                        fill_data=processed_fill,
                        correlation_id=correlation_id,
                        position_actor=self.position_actor,
                        order_actor=self.order_actor,
                        grid_calc=self.grid_calc,
                        event_store=self.event_store
                    )
            else:
                raise ValueError(f"Unknown trading mode: {self.mode}")

            # Execute saga
            task = await self.saga_orchestrator.start_saga(saga)

            # Track saga completion
            asyncio.create_task(self.track_saga_completion(task, correlation_id))

            # Safety check removed - Guardian monitors risk parameters
            # Fill processed successfully
            self._set_last_safety_check_time(time.time())

        except Exception as e:
            log.error(f"Error processing fill: {e}")
