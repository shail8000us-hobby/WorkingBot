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

from webui.backend.sealed import sealed


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
    @sealed
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

    # ── _update_last_order_time → MOVED here P6.5 ──
    def update_last_order_time(self, order_price: Optional[float] = None) -> None:
        self._last_order_time = time.time()
        if order_price is not None:
            self._last_accepted_order_price = order_price

    # ── _place_grid_order → MOVED here P6.5 ──
    async def place_grid_order(self, state: Dict, side: str) -> None:
        current_price = self._get_current_price()
        # CRITICAL: Need current price to calculate and place orders
        if not current_price:
            log.debug(f"Cannot place {side} order - current price not available yet")
            return

        pending_key = f"pending_{side}"
        if state.get(pending_key):
            return

        if len(state["open_tranches"]) >= self.position_actor.max_positions:
            return

        positions = state["open_tranches"]

        # FIX MAR 2 2026: Pass current_price to prevent placing above market (BUY)
        # or below market (SELL). Without this, compute_next_buy_level defaults to
        # ref - step when there are no positions, which can be above market price,
        # causing post-only orders to be rejected in an infinite loop.
        calc_method = f"compute_next_{side}_level"
        target = getattr(self.grid_calc, calc_method)(positions, current_price=current_price)

        if not target:
            log.info(f"⚠️  No {side.upper()} target calculated")
            log.info(f"   Current positions: {len(positions)}/{self.position_actor.max_positions}")
            if current_price:
                log.info(f"   Current price: ${current_price:,.2f}")
            else:
                log.info(f"   Current price: Not available")
            log.info(f"   Grid bounds: ${self.grid_calc.lower:,.0f} - ${self.grid_calc.upper:,.0f}")
            if positions:
                position_prices = [p.get('entry_price', 0) for p in positions]
                log.info(f"   Position levels: {[f'${p:,.0f}' for p in sorted(position_prices)]}")
            return

        if not self.grid_calc.is_within_bounds(target):
            log.debug(f"{side.upper()} target ${target:,.2f} is out of bounds ({self.grid_calc.lower} - {self.grid_calc.upper})")
            return

        # FIX MAR 2 2026: Post-only safety guard — prevent placing orders that
        # would cross the spread (BUY above market / SELL below market).
        # These get rejected with immediate_execution_post_only and create
        # an infinite retry loop.
        if current_price:
            if side == "buy" and target >= current_price:
                log.debug(f"⏭️  Skipping BUY @ ${target:,.0f} — at/above market ${current_price:,.0f} (would cross spread)")
                return
            elif side == "sell" and target <= current_price:
                log.debug(f"⏭️  Skipping SELL @ ${target:,.0f} — at/below market ${current_price:,.0f} (would cross spread)")
                return

        if target:
            try:
                self.pre_order_logger.log_decision(
                    side=side,
                    price=target,
                    current_price=current_price,
                    current_positions=len(positions),
                    max_positions=self.position_actor.max_positions,
                    grid_step=self.grid_calc.step,
                    reasons=[f"Grid level placement ({self.mode} mode)"]
                )
            except Exception as e:
                log.warning(f"Pre-order logging failed: {e}")

            try:
                anomaly_detected = self.anomaly_detector.check_before_order(
                    side=side,
                    price=target,
                    current_price=current_price
                )
            except Exception as e:
                log.warning(f"Anomaly detection failed: {e}")
                anomaly_detected = False

            if anomaly_detected:
                log.warning(f"⚠️  Anomaly detected before {side.upper()} order @ ${target:,.2f} - proceeding with caution")

            # CRITICAL FIX (Nov 20, 2025): Use separate lot sizes for LONG/SHORT
            if side == "sell":
                size = getattr(self.config.grid.limits, 'short_lot_size', self.lot_size)
            else:
                size = self.lot_size

            # SHORT mode: use REPLACE_PENDING_SELL_ORDER to enforce single-entry-order
            # invariant. Phase 1b (orphan sweep) catches stale exchange orders even when
            # bot state shows no pending_sell (e.g. after a restart before state was synced).
            # known_pending_id is omitted — pending_sell was confirmed None at line 220.
            if side == "sell" and self.mode == "SHORT":
                action = "REPLACE_PENDING_SELL_ORDER"
                order_payload = {"price": target, "size": size, "check_guardian": True}
            else:
                action = f"PLACE_{side.upper()}"
                order_payload = {"price": target, "size": size}

            result = await self.order_actor.ask(action, order_payload, timeout=20.0)

            if result.get("status") == "ok":
                order_id = result.get("order_id")

                self.update_last_order_time(target)

                await self.position_actor.tell(f"SET_PENDING_{side.upper()}", {
                    "order_id": order_id,
                    "price": target,
                    "size": self.lot_size,
                    "timestamp": time.time()
                })

                log.info(f"✅ {side.upper()} order placed @ ${target:,.2f} (Order: {order_id})")
            else:
                # FIX MAR 2 2026: Log error and apply cooldown to prevent rapid retry spam.
                # Without this, failed orders retry on every ticker update (~1-2s).
                error_msg = result.get("error", "unknown")
                log.warning(f"❌ {side.upper()} order FAILED @ ${target:,.2f}: {error_msg}")
                # Apply cooldown even on failure to prevent hammering the exchange
                self.update_last_order_time(target)

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

    # ── _check_and_place_entry_order → MOVED here P6.6 ──
    async def check_and_place_entry_order(self) -> None:
        """Check if we should place a new entry order based on current grid state.

        CRITICAL SAFETY INTEGRATION:
        - Calls comprehensive_safety_check() before EVERY order
        - This includes Guardian signal, account loss limits, margin, and volatility
        - If ANY check fails, order is blocked
        - Ensures grid trading respects ALL safety boundaries

        JAN 29 2026: Added recovery_in_progress check to prevent conflicts.
        """
        async with self._order_placement_lock:
            try:
                if not self._get_initial_order_placed() or not self._get_current_price():
                    return

                # Check if recovery is in progress - skip normal order placement
                if self._state_coordinator_ref and self._state_coordinator_ref.is_recovery_in_progress():
                    log.debug("Skipping normal order placement - recovery in progress")
                    return

                # COMPREHENSIVE SAFETY CHECK before placing any order
                can_proceed, reason = await self.comprehensive_safety_check("entry order placement")
                if not can_proceed:
                    # Mark as halted when blocked
                    self._was_halted = True

                    # Log detailed reason on state change or periodically (every 60s)
                    if self._last_block_reason != reason:
                        # Reason changed - log immediately with full detailed message
                        log.warning("")
                        log.warning("=" * 70)
                        log.warning("🚫 TRADING HALTED")
                        log.warning("=" * 70)
                        # reason is already a multi-line detailed message, log it directly
                        for line in reason.split('\n'):
                            if line.strip():
                                log.warning(line)
                        log.warning("=" * 70)
                        log.warning("")
                        self._last_block_reason = reason
                        self._last_safety_block_log = time.time()
                    elif time.time() - self._last_safety_block_log > 300:
                        # Same reason but 5 minutes passed - brief reminder
                        first_line = reason.split('\n')[0] if '\n' in reason else reason
                        log.info(f"ℹ️  Still blocked: {first_line}")
                        self._last_safety_block_log = time.time()
                    # Silently skip if same reason and logged recently
                    return

                # GUARDIAN RESUME - Reset halt flag
                if self._was_halted:
                    log.info("✅ Guardian resumed trading - resuming normal grid operations")
                    self._was_halted = False  # Reset flag

                # Price bounds already checked in comprehensive check
                # Volatility already checked in comprehensive check

                # Get current state
                state = await self.position_actor.ask("GET_STATE", {})

                # Place grid order based on mode
                side = "buy" if self.mode == "LONG" else "sell"
                await self.place_grid_order(state, side)

            except Exception as e:
                log.error(f"Entry check error: {e}", exc_info=True)

    # ── seed_missed_grid_levels → MOVED here P6.7 ──
    async def seed_missed_grid_levels(self, count: int) -> None:
        """
        Seed missed grid levels - place multiple entry orders at grid intervals.

        For LONG mode: Places BUY orders below current price
        For SHORT mode: Places SELL orders above current price

        Uses existing order placement logic via OrderManagerActor.
        Bot handles TPs automatically when fills occur.

        Args:
            count: Number of grid levels to seed
        """
        if count <= 0:
            return

        current_price = self._get_current_price()

        log.info("=" * 70)
        log.info(f"🌱 SEEDING {count} MISSED GRID LEVELS ({self.mode} MODE)")
        log.info(f"📍 Current Price: ${current_price:,.0f}")
        log.info("=" * 70)

        for i in range(count):
            try:
                if self.mode == 'LONG':
                    # Buy below current price (going down)
                    level = current_price - (i + 1) * self.grid_calc.step

                    if level >= self.grid_calc.lower:
                        # Place order via OrderManagerActor
                        order_resp = await self.order_actor.ask({
                            'action': 'place_buy_order',
                            'price': level,
                            'post_only': True
                        })

                        if order_resp.get('status') == 'success':
                            order_id = order_resp.get('order_id')
                            log.info(f"  ✅ Grid BUY placed @ ${level:,.0f} (ID: {order_id})")
                        else:
                            log.warning(f"  ⚠️  Failed to place BUY @ ${level:,.0f}: {order_resp.get('error')}")
                    else:
                        log.warning(f"  ⚠️  Level ${level:,.0f} below grid lower bound, stopping")
                        break

                elif self.mode == 'SHORT':
                    # Sell above current price (going up)
                    level = current_price + (i + 1) * self.grid_calc.step

                    if level <= self.grid_calc.upper:
                        # Place order via OrderManagerActor
                        order_resp = await self.order_actor.ask({
                            'action': 'place_sell_order',
                            'price': level,
                            'post_only': True
                        })

                        if order_resp.get('status') == 'success':
                            order_id = order_resp.get('order_id')
                            log.info(f"  ✅ Grid SELL placed @ ${level:,.0f} (ID: {order_id})")
                        else:
                            log.warning(f"  ⚠️  Failed to place SELL @ ${level:,.0f}: {order_resp.get('error')}")
                    else:
                        log.warning(f"  ⚠️  Level ${level:,.0f} above grid upper bound, stopping")
                        break

                # Rate limiting between orders
                await asyncio.sleep(0.2)

            except Exception as e:
                log.error(f"❌ Error seeding grid level {i+1}: {e}")
                continue

        log.info("=" * 70)
        log.info(f"✅ SEEDING COMPLETE - Bot will manage TPs automatically")
        log.info("=" * 70)

    # ── _place_initial_order → MOVED here P6.8 ──
    async def place_initial_order(self) -> None:
        """
        Place initial entry order on startup.
        Only places order if no positions or pending orders exist.
        """
        try:
            log.info("Checking if initial order should be placed...")

            # Pre-order volatility check REMOVED - Guardian handles this
            # Guardian publishes GO/STOP signals based on volatility
            # Trading bot will read Guardian signal (Phase 2.6)

            # Get current state
            state = await self.position_actor.ask("GET_STATE", {})

            # Check if we already have positions or pending orders
            has_positions = len(state.get("open_tranches", [])) > 0
            has_pending = state.get("pending_buy") or state.get("pending_sell")

            if has_positions:
                log.info(f"✓ Found {len(state['open_tranches'])} existing position(s) - no initial order needed")
                self._set_initial_order_placed(True)
                return

            if has_pending:
                log.info("✓ Pending order already exists in bot state - no initial order needed")
                self._set_initial_order_placed(True)
                return

            # CRITICAL: Check exchange for existing open orders BEFORE placing new ones
            log.info("🔍 Checking exchange for existing open orders...")
            try:
                exchange_orders = await self.api_client.rest_client.get_open_orders(product_id=self.product_id)

                # CRITICAL FIX: Filter by product_id manually (API returns all products)
                if exchange_orders:
                    exchange_orders = [o for o in exchange_orders if o.get('product_id') == self.product_id]

                if exchange_orders and len(exchange_orders) > 0:
                    log.warning(f"⚠️  Found {len(exchange_orders)} existing open order(s) on exchange:")
                    if human_log:
                        human_log.existing_orders_found(len(exchange_orders))  # Human-readable
                    for order in exchange_orders:
                        order_id = order.get('id')
                        side = order.get('side')
                        price = order.get('limit_price')
                        size = order.get('size')
                        order_type = order.get('order_type', 'UNKNOWN')

                        # Convert price to float for formatting (API might return string)
                        try:
                            price_float = float(price) if price else 0
                            log.warning(f"   Order {order_id}: {side} {size} @ ${price_float:,.2f} [type={order_type}]")
                        except (ValueError, TypeError):
                            log.warning(f"   Order {order_id}: {side} {size} @ {price} [type={order_type}]")

                    # SHORT mode: if 2+ bot-tagged SELL limit orders exist at startup,
                    # cancel ALL before syncing — enforces single-entry-order invariant.
                    # (Single order = sync as usual; 0 orders = fall through to placement.)
                    if self.mode == "SHORT":
                        tag = getattr(self.order_actor, 'tag_prefix', 'GBOT_')
                        short_sell_candidates = [
                            o for o in exchange_orders
                            if (o.get('order_type', '').lower() == 'limit_order'
                                and not o.get('bracket_order')
                                and not o.get('stop_order_type')
                                and o.get('side') == 'sell'
                                and o.get('client_order_id', '').startswith(tag))
                        ]
                        if len(short_sell_candidates) > 1:
                            log.warning(
                                f"⚠️  Startup invariant violation: found {len(short_sell_candidates)} "
                                f"bot-tagged SELL orders — cancelling ALL to enforce "
                                f"single-entry-order invariant"
                            )
                            for orphan in short_sell_candidates:
                                oid = str(orphan.get('id'))
                                try:
                                    await self.api_client.cancel_order(oid, self.product_id)
                                    log.info(f"   Cancelled orphan SELL #{oid} @ ${float(orphan.get('limit_price', 0)):,.0f}")
                                except Exception as e:
                                    log.warning(f"   Failed to cancel orphan SELL #{oid}: {e}")
                            log.info("   All startup orphan SELLs cancelled — will place fresh entry order")
                            exchange_orders = []  # Clear so sync loop is skipped; falls through to placement

                    # Sync the first relevant order to bot state
                    # CRITICAL: Only sync LIMIT orders, NEVER stop/stop-limit/market orders
                    # This prevents interfering with manual stop losses or other manual trades
                    for order in exchange_orders:
                        order_side = order.get('side')
                        order_type = order.get('order_type', '').lower()
                        bracket_order = order.get('bracket_order')  # Bracket orders (SL/TP) have this field
                        stop_order_type = order.get('stop_order_type')  # Stop orders have this field

                        # Log all order details for debugging
                        log.info(f"   📋 Order details: type={order_type}, bracket={bracket_order}, stop_type={stop_order_type}")

                        # Skip non-limit orders (stop, stop-limit, market, etc.)
                        # Skip bracket orders (user's manual stop-loss/take-profit brackets)
                        if order_type != 'limit_order':
                            log.info(f"   ⏭️  Skipping {order_type} order {order.get('id')} - bot only manages plain limit orders")
                            continue

                        if bracket_order:
                            log.info(f"   ⏭️  Skipping bracket order {order.get('id')} - this is a manual SL/TP order")
                            continue

                        if stop_order_type:
                            log.info(f"   ⏭️  Skipping stop order {order.get('id')} (type={stop_order_type}) - manual stop order")
                            continue

                        if (self.mode == "LONG" and order_side == "buy") or (self.mode == "SHORT" and order_side == "sell"):
                            order_id = order.get('id')
                            order_price = order.get('limit_price')

                            # Convert price to float (API returns string)
                            try:
                                order_price_float = float(order_price) if order_price else 0
                            except (ValueError, TypeError):
                                log.error(f"Invalid price format from exchange: {order_price}")
                                continue

                            log.info(f"✅ Syncing existing LIMIT order {order_id} to bot state @ ${order_price_float:,.2f}")

                            if order_side == "buy":
                                await self.position_actor.tell("SET_PENDING_BUY", {
                                    "order_id": order_id,
                                    "price": order_price_float,  # Store as float
                                    "size": order.get("size", self.lot_size),
                                    "timestamp": time.time()
                                })
                            else:
                                await self.position_actor.tell("SET_PENDING_SELL", {
                                    "order_id": order_id,
                                    "price": order_price_float,  # Store as float
                                    "size": order.get("size", self.lot_size),
                                    "timestamp": time.time()
                                })

                            self._set_initial_order_placed(True)
                            log.info("✅ Existing exchange LIMIT order synced - bot will track it")
                            return

                    log.warning("⚠️  Existing orders found but none are bot-managed LIMIT orders - continuing with new order")
                else:
                    log.info("✅ No existing orders on exchange - safe to place new order")
            except Exception as e:
                log.error(f"❌ Failed to check exchange orders: {e}")
                log.warning("⚠️  Proceeding with caution - may result in duplicate orders")

            current_price = self._get_current_price()
            if not current_price:
                log.warning("⚠️  Current price not available - cannot place initial order")
                return

            # COMPREHENSIVE SAFETY CHECK before initial order
            can_proceed, reason = await self.comprehensive_safety_check("initial order placement")
            if not can_proceed:
                # Log detailed blocking reason prominently
                log.warning("")
                log.warning("=" * 70)
                log.warning("🚫 TRADING BLOCKED AT STARTUP")
                log.warning("=" * 70)
                for line in reason.split('\n'):
                    if line.strip():
                        log.warning(line)
                log.warning("=" * 70)
                log.warning("💡 Bot will start trading automatically when conditions are met")
                log.warning("=" * 70)
                log.warning("")

                # Mark as "placed" so entry order check loop runs and shows updates
                self._set_initial_order_placed(True)
                self._last_block_reason = reason
                self._last_safety_block_log = time.time()
                return

            # Check if price is within grid bounds (already checked in comprehensive, but log it)
            if not self.grid_calc.is_within_bounds(current_price):
                log.warning(f"⚠️  Current price ${current_price:,.2f} outside grid bounds")
                log.info(f"   Grid: ${self.grid_calc.lower:,.0f} - ${self.grid_calc.upper:,.0f}")
                log.info("   Waiting for price to enter grid range...")
                return

            # Calculate initial entry level
            positions = state.get("open_tranches", [])

            if self.mode == "LONG":
                # Check if we already have a pending buy order
                pending_buy = state.get("pending_buy")
                if pending_buy:
                    log.info(f"ℹ️  Pending BUY order already exists: {pending_buy.get('order_id')} @ ${pending_buy.get('price'):,.0f}")
                    return

                if not self.should_recalculate_grid_level(current_price):
                    log.debug(f"Price hasn't moved enough to recalculate grid level")
                    return

                target = self.grid_calc.compute_next_buy_level(positions, current_price=current_price)

                # Skip recovered grid levels (NOV 20)
                while target and target in self._recovered_grids:
                    log.info(f"🔄 Skipping recovered grid level: ${target:,.0f}")
                    # Find next level below the recovered one
                    target = target - self.grid_calc.step
                    if not self.grid_calc.is_within_bounds(target):
                        target = None
                        break

                if target and self.grid_calc.is_within_bounds(target):
                    log.info(f"📍 Placing initial MAKER BUY order @ ${target:,.2f}")
                    log.info(f"   Current market: ${current_price:,.2f}")
                    if human_log:
                        human_log.initial_order_placed("BUY", target)  # Human-readable

                    # Place order via order actor (timeout=20s to allow for retries)
                    result = await self.order_actor.ask("PLACE_BUY", {
                        "price": target,
                        "size": self.lot_size  # Use configured lot size
                    }, timeout=20.0)

                    if result.get("status") == "ok":
                        order_id = result.get("order_id")

                        self.update_last_order_time(target)

                        await self.position_actor.tell("SET_PENDING_BUY", {
                            "order_id": order_id,
                            "price": target,
                            "size": self.lot_size,
                            "timestamp": time.time()
                        })

                        log.info(f"✅ Initial MAKER BUY placed @ ${target:,.2f} (Order: {order_id})")
                        self._set_initial_order_placed(True)
                    else:
                        log.error(f"❌ Failed to place initial order: {result.get('error')}")
                else:
                    log.warning(f"⚠️  No valid buy level available (target={target})")

            else:  # SHORT mode
                # Check if we already have a pending sell order
                pending_sell = state.get("pending_sell")
                if pending_sell:
                    pending_price = pending_sell.get("price")
                    pending_order_id = pending_sell.get("order_id")
                    log.info(f"✅ Already have pending SELL @ ${pending_price:,.2f} (Order: {pending_order_id})")
                    log.info("   Not placing duplicate order - using existing one")
                    if human_log:
                        human_log.duplicate_order_detected("SELL", pending_price)
                    self._set_initial_order_placed(True)
                    return

                # Calculate next sell level above current price
                target = self.grid_calc.compute_next_sell_level(positions, current_price=current_price)

                # Skip recovered grid levels (NOV 20)
                while target and target in self._recovered_grids:
                    log.info(f"🔄 Skipping recovered grid level: ${target:,.0f}")
                    # Find next level above the recovered one
                    target = target + self.grid_calc.step
                    if not self.grid_calc.is_within_bounds(target):
                        target = None
                        break

                if target and self.grid_calc.is_within_bounds(target):
                    log.info(f"📍 Placing initial MAKER SELL order @ ${target:,.2f}")
                    log.info(f"   Current market: ${current_price:,.2f}")

                    # Place order via order actor (timeout=20s to allow for retries)
                    result = await self.order_actor.ask("PLACE_SELL", {
                        "price": target,
                        "size": self.lot_size
                    }, timeout=20.0)

                    if result.get("status") == "ok":
                        order_id = result.get("order_id")

                        self.update_last_order_time(target)

                        await self.position_actor.tell("SET_PENDING_SELL", {
                            "order_id": order_id,
                            "price": target,
                            "size": self.lot_size,
                            "timestamp": time.time()
                        })

                        log.info(f"✅ Initial MAKER SELL placed @ ${target:,.2f} (Order: {order_id})")
                        self._set_initial_order_placed(True)
                    else:
                        log.error(f"❌ Failed to place initial order: {result.get('error')}")
                else:
                    log.warning(f"⚠️  No valid sell level available (target={target})")

        except Exception as e:
            log.error(f"Error placing initial order: {e}", exc_info=True)
