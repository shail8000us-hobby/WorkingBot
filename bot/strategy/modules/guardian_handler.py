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

    async def read_signal(self) -> tuple[str, str]:
        """
        Read Guardian's GO/STOP signal from EventStore (SQL database).

        CRITICAL RULE: No Guardian = No Trading (KISS principle)
        Guardian provides ALL safety checks. If Guardian is not running or stops,
        GridBot MUST stop trading immediately.

        Guardian monitors ALL risk:
        - Volatility (IV/RV/spread)
        - Loss limits (max_account_loss_inr)
        - Position size (max_position_size)
        - Liquidation distance (min_liquidation_distance_inr)

        Returns:
            (signal, reason) - 'GO'/'STOP' and reason string
        """
        try:
            # Read latest Guardian signal from EventStore
            # Guardian publishes GUARDIAN_SIGNAL_GO or GUARDIAN_SIGNAL_STOP events
            # Rate-limited debug logging (every 30 seconds instead of every call)
            if self._should_log('guardian_check', interval_seconds=30):
                log.debug(f"Checking Guardian signals in database: {self.event_store.db_path}")

            events = self.event_store.get_events_by_type(
                [EventType.GUARDIAN_SIGNAL_GO, EventType.GUARDIAN_SIGNAL_STOP],
                limit=1
            )

            # Only log event count if we haven't logged recently
            if self._should_log('guardian_events_count', interval_seconds=30):
                log.debug(f"Found {len(events)} Guardian events")

            if not events:
                log.warning("⚠️  No Guardian signal found yet - Guardian may be starting up")
                log.warning("   Bot will wait for Guardian signal before placing orders")
                return 'STOP', 'Waiting for Guardian signal'

            latest_event = events[0]
            signal = 'GO' if latest_event.event_type == EventType.GUARDIAN_SIGNAL_GO else 'STOP'
            reason = latest_event.data.get('reason', 'No reason provided')
            timestamp = latest_event.timestamp
            details = latest_event.data.get('details', {})

            # Check signal age (Guardian publishes every 5s)
            signal_age = time.time() - timestamp

            # Log Guardian status - rate limit to every 10s (balance visibility vs spam)
            should_log_guardian = self._should_log('guardian_status', interval_seconds=10)

            if signal == 'GO':
                if should_log_guardian:
                    log.info(f"🛡️  Guardian: 🟢 GO - Trading allowed (signal age: {signal_age:.1f}s)")
                    # Log key safety metrics from Guardian
                    if details:
                        iv = details.get('iv', 0)
                        rv = details.get('rv', 0)
                        pnl_inr = details.get('pnl_inr', 0)
                        max_loss = details.get('max_loss_limit', 0)
                        log.info(f"   📊 IV: {iv:.1f}%, RV: {rv:.1f}%, PnL: ₹{pnl_inr:.2f}/₹{max_loss:.0f}")
            else:
                # STOP signal - ALWAYS log (critical safety information)
                log.warning(f"🛡️  Guardian: 🔴 STOP - Trading blocked (signal age: {signal_age:.1f}s)")
                log.warning(f"   Reason: {reason}")

            # CRITICAL: Check if Guardian is still alive
            # Increased from 60s to 120s to handle API rate limiting scenarios where
            # Delta API may block requests for 60s, causing Guardian signal to appear stale
            # JAN 27, 2026: Fixed to prevent stop/start cycle during rate limiting
            # MAR 01, 2026: Fixed startup vs shutdown detection for stale signals
            if signal_age > 120:  # 120 seconds = 24 missed cycles (was 60s = 12 cycles)
                if not self._get_running():
                    if not self._get_started_once():
                        # STARTUP: Bot hasn't started yet and Guardian signal is stale.
                        # SAFETY: Do NOT assume GO — stale signals mean Guardian may be down.
                        # Block trading until a fresh signal arrives.
                        log.warning(f"⚠️  Guardian signal stale ({signal_age:.0f}s) during STARTUP - blocking until fresh signal")
                        log.warning(f"   Original signal: {signal} - {reason}")
                        log.warning(f"   Will not start trading until Guardian publishes a fresh signal (within 120s).")
                        return 'STOP', f'Guardian signal stale at startup ({signal_age:.0f}s old) — waiting for fresh signal'
                    else:
                        # SHUTDOWN: Bot was running but stopped. Don't trigger new shutdown.
                        log.warning(f"⚠️  Guardian signal stale ({signal_age:.0f}s) but bot already shutting down - ignoring")
                        return 'STOP', f'Guardian signal stale (bot already shutting down)'

                log.error(f"🚨 CRITICAL: Guardian signal is stale ({signal_age:.0f}s old)")
                log.error(f"🛑 Guardian appears to have STOPPED. Shutting down bot for safety.")
                log.error(f"🛑 RULE: No Guardian = No Trading")
                # Trigger bot shutdown
                self._set_running(False)
                return 'STOP', f'CRITICAL: Guardian stopped - Signal stale ({signal_age:.0f}s old)'

            return signal, reason

        except Exception as e:
            log.error(f"🚨 CRITICAL: Error reading Guardian signal: {e}")
            log.error(f"🛑 Cannot verify Guardian status. Stopping bot for safety.")
            log.error(f"🛑 RULE: No Guardian = No Trading")
            # Trigger bot shutdown
            self._set_running(False)
            return 'STOP', f'CRITICAL: Guardian signal read error: {str(e)}'

    async def check_transition_and_retry(self) -> None:
        """
        Canonical STOP→GO transition handler (runs every 15s via health_monitor_loop).

        Responsibilities:
        - Retry missed grid orders queued during STOP
        - A3 multi-step gap fill
        - resume_grid() to place next entry if no missed orders

        check_transitions() handles only GO→STOP (cancel pending entries).
        Having ONE handler per direction eliminates the _last_guardian_signal race
        and prevents duplicate order placement on the same transition.
        """
        try:
            # Read current Guardian signal
            signal, reason = await self.read_signal()

            # Check for STOP -> GO transition
            if self._last_guardian_signal == 'STOP' and signal == 'GO':
                transition_time = time.time()
                log.info("=" * 80)
                log.info("🟢 GUARDIAN TRANSITION DETECTED: STOP -> GO")
                log.info(f"   Blocked Duration: {transition_time - self._guardian_transition_time:.1f}s")
                log.info(f"   Missed Grid Orders: {len(self._missed_grid_orders)}")
                log.info("=" * 80)

                # Retry explicitly queued missed grid orders first
                if self._missed_grid_orders:
                    await self.retry_missed_orders()

                # A3: Check for multi-step price moves during the STOP period
                await self.fill_multi_step_missed_grids()

                # If no missed orders were queued (or all were skipped), place the
                # next regular entry order so the grid resumes immediately.
                # This is the only place resume_grid() is called on STOP→GO.
                state = await self.position_actor.ask("GET_STATE", {})
                has_pending = state.get("pending_buy") or state.get("pending_sell")
                if not has_pending:
                    await self.resume_grid()

            # Track signal for next check (single writer for STOP→GO direction)
            if self._last_guardian_signal != signal:
                self._last_guardian_signal = signal
                self._guardian_transition_time = time.time()

        except Exception as e:
            log.error(f"Error checking Guardian transition: {e}")

    async def retry_missed_orders(self) -> None:
        """
        Retry placing grid orders that were missed due to Guardian STOP signal.
        Only retries orders that are still valid based on current bot state.
        """
        if not self._missed_grid_orders:
            return

        log.info(f"🔄 Retrying {len(self._missed_grid_orders)} missed grid orders...")

        # ✅ CRITICAL: Verify Guardian signal is still GO before retrying
        signal, reason = await self.read_signal()
        if signal == 'STOP':
            log.warning(f"⚠️  Guardian is STOP again during retry attempt")
            log.warning(f"   Reason: {reason}")
            log.warning(f"   Missed orders will remain queued for next GO signal")
            return  # Exit early, keep orders in list for next transition

        # Get current bot state
        state = await self.position_actor.ask("GET_STATE", {})
        open_positions = state.get("open_tranches", [])
        pending_buy = state.get("pending_buy")
        pending_sell = state.get("pending_sell")

        retried = 0
        skipped = 0
        processed_orders = []  # Track which orders we've processed
        guardian_stopped = False

        for missed_order in list(self._missed_grid_orders):  # Copy to allow modification
            price, side, reason, timestamp = missed_order

            # ✅ Defense in depth: Check Guardian again if retrying multiple orders
            if len(self._missed_grid_orders) > 1 and retried > 0:
                signal, _ = await self.read_signal()
                if signal == 'STOP':
                    log.warning(f"⚠️  Guardian changed to STOP during retry loop - stopping")
                    log.warning(f"   Remaining orders will be retried on next GO signal")
                    guardian_stopped = True
                    break  # Stop retry loop, remaining orders stay in list

            # Check if this order is still needed
            if side == "buy":
                # Skip if we already have a pending buy
                if pending_buy:
                    log.info(f"   ⏭️  Skipping BUY @ ${price:,.0f} - already have pending buy @ ${pending_buy.get('price'):,.0f}")
                    skipped += 1
                    processed_orders.append(missed_order)  # Mark as processed
                    continue

                # Skip if price is no longer valid
                if not self.grid_calc.is_within_bounds(price):
                    log.info(f"   ⏭️  Skipping BUY @ ${price:,.0f} - price out of grid bounds")
                    skipped += 1
                    processed_orders.append(missed_order)  # Mark as processed
                    continue

                # Skip if a position already exists near this level — prevents
                # double-entry if the BUY filled during STOP but state was not updated.
                already_held = any(
                    abs(p.get('entry_price', 0) - price) < self.grid_step * 0.3
                    for p in open_positions
                )
                if already_held:
                    log.info(f"   ⏭️  Skipping BUY @ ${price:,.0f} - position already exists near this level")
                    skipped += 1
                    processed_orders.append(missed_order)
                    continue

                # Retry placing BUY order
                try:
                    result = await self.order_actor.ask("PLACE_BUY", {
                        "price": price,
                        "size": self.lot_size
                    }, timeout=10.0)

                    if result.get("status") == "ok":
                        log.info(f"   ✅ Retried BUY @ ${price:,.0f} successfully (order_id: {result.get('order_id')})")
                        retried += 1
                        processed_orders.append(missed_order)  # Mark as processed

                        # Update pending buy state
                        await self.position_actor.tell("SET_PENDING_BUY", {
                            "order_id": result["order_id"],
                            "price": price,
                            "size": self.lot_size
                        })
                    else:
                        log.warning(f"   ❌ Failed to retry BUY @ ${price:,.0f}: {result.get('error')}")
                        skipped += 1
                        processed_orders.append(missed_order)  # Mark as processed

                except Exception as e:
                    log.error(f"   ❌ Error retrying BUY @ ${price:,.0f}: {e}")
                    skipped += 1
                    processed_orders.append(missed_order)  # Mark as processed

            elif side == "sell":
                # Skip if we already have a pending sell
                if pending_sell:
                    log.info(f"   ⏭️  Skipping SELL @ ${price:,.0f} - already have pending sell @ ${pending_sell.get('price'):,.0f}")
                    skipped += 1
                    processed_orders.append(missed_order)
                    continue

                # Skip if price is outside grid bounds
                if not self.grid_calc.is_within_bounds(price):
                    log.info(f"   ⏭️  Skipping SELL @ ${price:,.0f} - price out of grid bounds")
                    skipped += 1
                    processed_orders.append(missed_order)
                    continue

                # Skip if the level is at or below current market price.
                # A limit SELL at or below market fills immediately as a market order,
                # bypassing grid structure. This is the most critical SHORT-mode guard.
                current_price_check = self._get_current_price()
                if current_price_check and price <= current_price_check:
                    log.warning(f"   ⏭️  Skipping SELL @ ${price:,.0f} - level at/below market (${current_price_check:,.0f}), would fill as market order")
                    skipped += 1
                    processed_orders.append(missed_order)
                    continue

                # Skip if at max position capacity
                if len(open_positions) >= self.max_positions:
                    log.info(f"   ⏭️  Skipping SELL @ ${price:,.0f} - at max positions ({self.max_positions})")
                    skipped += 1
                    processed_orders.append(missed_order)
                    continue

                # Skip if a position already exists near this level (idempotency guard).
                # Prevents double-entry if the SELL filled during STOP but state was not updated.
                already_held = any(
                    abs(p.get('entry_price', 0) - price) < self.grid_step * 0.3
                    for p in open_positions
                )
                if already_held:
                    log.info(f"   ⏭️  Skipping SELL @ ${price:,.0f} - position already exists near this level")
                    skipped += 1
                    processed_orders.append(missed_order)
                    continue

                # Retry placing SELL order (SHORT mode entry)
                try:
                    result = await self.order_actor.ask("PLACE_SELL", {
                        "price": price,
                        "size": self.lot_size
                    }, timeout=10.0)

                    if result.get("status") == "ok":
                        log.info(f"   ✅ Retried SELL @ ${price:,.0f} successfully (order_id: {result.get('order_id')})")
                        retried += 1
                        processed_orders.append(missed_order)

                        # Update pending sell state locally too — prevents a second SELL
                        # being placed later in this same retry batch
                        pending_sell = {
                            "order_id": result["order_id"],
                            "price": price,
                            "size": self.lot_size
                        }
                        await self.position_actor.tell("SET_PENDING_SELL", pending_sell)
                    else:
                        log.warning(f"   ❌ Failed to retry SELL @ ${price:,.0f}: {result.get('error')}")
                        skipped += 1
                        processed_orders.append(missed_order)

                except Exception as e:
                    log.error(f"   ❌ Error retrying SELL @ ${price:,.0f}: {e}")
                    skipped += 1
                    processed_orders.append(missed_order)

            # Small delay between retries
            await asyncio.sleep(0.3)

        # Remove processed orders from the list
        self._missed_grid_orders = [order for order in self._missed_grid_orders
                                   if order not in processed_orders]

        if guardian_stopped:
            log.info(f"🔄 Partial retry: {retried} succeeded, {skipped} skipped, {len(self._missed_grid_orders)} remain queued")
        else:
            log.info(f"🔄 Retry complete: {retried} succeeded, {skipped} skipped")

    async def fill_multi_step_missed_grids(self) -> None:
        """
        A3: Detect and fill grid levels missed during a multi-step price move
        while Guardian was in STOP state.

        When the market moves 2+ grid steps during STOP, the explicit
        _missed_grid_orders list may only have 1 entry (or none if the move
        happened entirely in STOP). This method calculates the full set of
        missed levels from the current position state vs. current price.

        LONG: detects downward gaps, back-fills missed BUY levels still below market.
        SHORT: detects upward gaps, back-fills missed SELL levels still above market.
              If price spiked and never retraced, SHORT A3 fills nothing — correct.

        Safety: capped at 5 fills per cycle, respects max_positions,
        re-checks Guardian before each fill.
        """
        MAX_MISSED_FILLS_PER_CYCLE = 5

        if self.mode not in ("LONG", "SHORT"):
            return

        # Verify Guardian is still GO
        signal, reason = await self.read_signal()
        if signal == 'STOP':
            return

        # Get current state (shared for both modes)
        state = await self.position_actor.ask("GET_STATE", {})
        positions = state.get("open_tranches", [])
        num_positions = len(positions)

        current_price = self._get_current_price()
        if not current_price or current_price <= 0:
            return

        if self.mode == "LONG":
            pending_buy = state.get("pending_buy")

            # If we already have a pending buy, don't interfere
            if pending_buy:
                return

            # If at max positions, nothing to do
            if num_positions >= self.max_positions:
                return

            if positions:
                lowest_entry = min(p.get('entry_price', float('inf')) for p in positions)
            else:
                # No positions: reference is our starting point
                lowest_entry = self.ref_price

            # How many steps from the lowest position to current price?
            price_gap = lowest_entry - current_price
            if price_gap <= self.grid_step:
                # Price hasn't moved more than 1 step below — no multi-step gap
                return

            steps_missed = int(price_gap / self.grid_step)
            if steps_missed < 2:
                return

            # Build list of missed grid levels (below lowest position, above current price)
            missed_levels = []
            for i in range(1, steps_missed + 1):
                level = lowest_entry - (i * self.grid_step)
                # Must be within grid bounds
                if level < self.grid_calc.lower:
                    break
                # Must be below current price (would have triggered as buy)
                if level >= current_price:
                    continue
                # Skip if a position already exists at this level (within tolerance)
                already_held = any(
                    abs(p.get('entry_price', 0) - level) < self.grid_step * 0.3
                    for p in positions
                )
                if already_held:
                    continue
                missed_levels.append(level)

            if not missed_levels:
                return

            # Sort highest first (closest to current price)
            missed_levels.sort(reverse=True)

            # Cap at safety limit
            slots_available = self.max_positions - num_positions
            fill_count = min(len(missed_levels), MAX_MISSED_FILLS_PER_CYCLE, slots_available)
            missed_levels = missed_levels[:fill_count]

            log.info(f"📊 A3: Multi-step gap detected — {steps_missed} steps missed, filling {len(missed_levels)} levels")

            filled = 0
            for level in missed_levels:
                # Re-check Guardian before each fill
                signal, _ = await self.read_signal()
                if signal == 'STOP':
                    log.warning(f"⚠️  Guardian went STOP during multi-step fill — stopping ({filled}/{len(missed_levels)} filled)")
                    break

                # Re-verify price is still below this level
                current_price = self._get_current_price()
                if current_price and current_price >= level:
                    log.info(f"   ⏭️  Skipping ${level:,.0f} — price bounced above it (${current_price:,.0f})")
                    continue

                try:
                    result = await self.order_actor.ask("PLACE_BUY", {
                        "price": level,
                        "size": self.lot_size
                    }, timeout=10.0)

                    if result.get("status") == "ok":
                        log.info(f"   ✅ A3 filled missed grid BUY @ ${level:,.0f} (order_id: {result.get('order_id')})")
                        filled += 1

                        # Register pending buy — enforces Single Pending Order Rule
                        await self.position_actor.tell("SET_PENDING_BUY", {
                            "order_id": result["order_id"],
                            "price": level,
                            "size": self.lot_size
                        })

                        # SINGLE PENDING ORDER RULE: only one entry order at a time.
                        # Break immediately after the first successful placement.
                        # The next A3 cycle (after this fill is processed) will handle
                        # the subsequent level if price is still in multi-step gap.
                        break
                    else:
                        log.warning(f"   ❌ A3 failed BUY @ ${level:,.0f}: {result.get('error')}")
                except Exception as e:
                    log.error(f"   ❌ A3 error placing BUY @ ${level:,.0f}: {e}")

            if filled > 0:
                log.info(f"📊 A3: Multi-step recovery complete — {filled} level queued (Single Pending Order Rule)")

        elif self.mode == "SHORT":
            pending_sell = state.get("pending_sell")

            # If we already have a pending sell, don't interfere
            if pending_sell:
                return

            # If at max positions, nothing to do
            if num_positions >= self.max_positions:
                return

            if positions:
                highest_entry = max(p.get('entry_price', float('-inf')) for p in positions)
            else:
                # No positions: reference is our starting point
                highest_entry = self.ref_price

            # How many steps has price moved above the highest position?
            price_gap = current_price - highest_entry
            if price_gap <= self.grid_step:
                # Price hasn't moved more than 1 step above — no multi-step gap
                return

            steps_missed = int(price_gap / self.grid_step)
            if steps_missed < 2:
                return

            # Build list of missed grid levels (above highest position).
            # CRITICAL: only include levels still ABOVE current price.
            # A level at or below current price means market already blew through it —
            # placing a limit SELL there would fill immediately as a market order.
            missed_levels = []
            for i in range(1, steps_missed + 1):
                level = highest_entry + (i * self.grid_step)
                # Must be within grid bounds
                if level > self.grid_calc.upper:
                    break
                # Must be above current price (valid limit SELL entry)
                if level <= current_price:
                    continue
                # Safety buffer: don't place within 0.3 steps of market — too close.
                # Use <= so the boundary level itself is also excluded (off-by-one fix).
                if level <= current_price + (self.grid_step * 0.3):
                    continue
                # Skip if a position already exists at this level (within tolerance)
                already_held = any(
                    abs(p.get('entry_price', 0) - level) < self.grid_step * 0.3
                    for p in positions
                )
                if already_held:
                    continue
                missed_levels.append(level)

            if not missed_levels:
                return

            # Sort ascending — lowest first (closest to current price, most likely to trigger first)
            missed_levels.sort()

            # Cap at safety limit
            slots_available = self.max_positions - num_positions
            fill_count = min(len(missed_levels), MAX_MISSED_FILLS_PER_CYCLE, slots_available)
            missed_levels = missed_levels[:fill_count]

            log.info(f"📊 A3 SHORT: Multi-step gap detected — {steps_missed} steps missed, filling {len(missed_levels)} levels")

            filled = 0
            for level in missed_levels:
                # Re-check Guardian before each fill
                signal, _ = await self.read_signal()
                if signal == 'STOP':
                    log.warning(f"⚠️  Guardian went STOP during multi-step fill — stopping ({filled}/{len(missed_levels)} filled)")
                    break

                # Re-verify level is still above current price before placing.
                # Price may have spiked further during this loop.
                current_price = self._get_current_price()
                if current_price and level <= current_price:
                    log.info(f"   ⏭️  Skipping ${level:,.0f} — price spiked above it (${current_price:,.0f})")
                    continue

                try:
                    result = await self.order_actor.ask("PLACE_SELL", {
                        "price": level,
                        "size": self.lot_size
                    }, timeout=10.0)

                    if result.get("status") == "ok":
                        log.info(f"   ✅ A3 filled missed grid SELL @ ${level:,.0f} (order_id: {result.get('order_id')})")
                        filled += 1

                        # Register pending sell — enforces Single Pending Order Rule
                        await self.position_actor.tell("SET_PENDING_SELL", {
                            "order_id": result["order_id"],
                            "price": level,
                            "size": self.lot_size
                        })

                        # SINGLE PENDING ORDER RULE: only one entry order at a time.
                        # Break immediately — next A3 cycle handles the subsequent level.
                        break
                    else:
                        log.warning(f"   ❌ A3 failed SELL @ ${level:,.0f}: {result.get('error')}")
                except Exception as e:
                    log.error(f"   ❌ A3 error placing SELL @ ${level:,.0f}: {e}")

            if filled > 0:
                log.info(f"📊 A3 SHORT: Multi-step recovery complete — {filled} level queued (Single Pending Order Rule)")

    async def check_transitions(self) -> None:
        """
        Handle GO→STOP transition: cancel all pending entry orders immediately.

        STOP→GO is handled exclusively by check_transition_and_retry() (runs every 15s
        via health_monitor_loop). Having one handler per direction prevents duplicate
        order placement and eliminates the _last_guardian_signal write race.
        """
        try:
            current_signal, reason = await self.read_signal()

            # Only act on GO → STOP transition
            if self._last_guardian_signal == "GO" and current_signal == "STOP":
                log.warning("=" * 70)
                log.warning("🔴 GUARDIAN SIGNAL: GO → STOP")
                log.warning(f"   Reason: {reason}")
                log.warning("   Action: Cancelling all pending entry orders")
                log.warning("=" * 70)
                await self.cancel_pending_entries()
                # Update signal so we don't cancel again next tick
                self._last_guardian_signal = current_signal

        except Exception as e:
            log.error(f"Error checking Guardian transitions: {e}")

    async def cancel_pending_entries(self) -> None:
        """
        Cancel all pending entry orders when Guardian turns STOP.

        This prevents orders from filling during dangerous market conditions
        when the bot is blocked from placing protective TP orders.
        """
        try:
            cancelled_count = 0

            # Cancel BOTH sides regardless of current mode.
            # After a mode switch or a resume_grid() malfunction, a stale order from
            # the opposite mode may still be in state — cancelling both is always safe.
            state = await self.position_actor.ask("GET_STATE", {})

            pending_buy = state.get("pending_buy")
            if pending_buy:
                order_id = pending_buy.get("order_id")
                price = pending_buy.get("price", 0)
                log.info(f"📋 Cancelling pending BUY order: {order_id} @ ${price:,.0f}")
                try:
                    await self.order_actor.tell("CANCEL_ORDER", {"order_id": order_id})
                    await self.position_actor.tell("CLEAR_PENDING_BUY", {"order_id": order_id})
                    cancelled_count += 1
                    log.info(f"✅ Cancelled BUY order {order_id}")
                except Exception as cancel_error:
                    log.error(f"Failed to cancel BUY order {order_id}: {cancel_error}")

            pending_sell = state.get("pending_sell")
            if pending_sell:
                order_id = pending_sell.get("order_id")
                price = pending_sell.get("price", 0)
                log.info(f"📋 Cancelling pending SELL order: {order_id} @ ${price:,.0f}")
                try:
                    await self.order_actor.tell("CANCEL_ORDER", {"order_id": order_id})
                    await self.position_actor.tell("CLEAR_PENDING_SELL", {"order_id": order_id})
                    cancelled_count += 1
                    log.info(f"✅ Cancelled SELL order {order_id}")
                except Exception as cancel_error:
                    log.error(f"Failed to cancel SELL order {order_id}: {cancel_error}")

            if cancelled_count > 0:
                log.info(f"🧹 Cancelled {cancelled_count} pending entry order(s) due to Guardian STOP")
                if human_log:
                    human_log.info(f"Guardian stopped trading - cancelled {cancelled_count} pending order(s)")
            else:
                log.info("✓ No pending entry orders to cancel")

        except Exception as e:
            log.error(f"Error cancelling pending entry orders: {e}")

    async def resume_grid(self) -> None:
        """
        Resume grid trading when Guardian signal turns from STOP to GO.

        Uses proper GridCalculator logic to determine next entry level based on:
        - Current market price
        - Existing open positions
        - Grid strategy (LONG/SHORT)

        This ensures the bot resumes exactly as per the documented grid strategy
        without disrupting the single pending order rule or grid logic.
        """
        try:
            # Check if we have the current price
            current_price = self._get_current_price()
            if not current_price:
                log.warning("Cannot resume grid - no current price available")
                return

            # Get current state via actor model (never access .state directly)
            state = await self.position_actor.ask("GET_STATE", {})

            # Check if we already have a pending order
            if self.mode == "LONG":
                pending = state.get("pending_buy")
                if pending:
                    log.info(f"✓ Pending BUY order already exists @ ${pending.get('price', 0):,.0f}")
                    return
            elif self.mode == "SHORT":
                pending = state.get("pending_sell")
                if pending:
                    log.info(f"✓ Pending SELL order already exists @ ${pending.get('price', 0):,.0f}")
                    return

            # Get current positions — use open_tranches (the actor's canonical key)
            positions = state.get("open_tranches", [])

            # Use GridCalculator to determine proper next entry level
            # This follows the exact logic documented in logic_strategy.md
            if self.mode == "LONG":
                # GridCalculator determines next BUY based on:
                # - If positions exist: lowest_entry - step
                # - If no positions: proper grid level below current price
                next_buy_level = self.grid_calc.compute_next_buy_level(
                    open_positions=positions,
                    current_price=current_price
                )

                if next_buy_level and next_buy_level >= self.grid_calc.lower:
                    log.info(f"🟢 Resuming LONG grid - placing BUY @ ${next_buy_level:,.0f}")
                    log.info(f"   Current price: ${current_price:,.0f}")
                    log.info(f"   Open positions: {len(positions)}")

                    order_resp = await self.order_actor.ask("PLACE_BUY", {
                        "price": next_buy_level,
                        "size": self.lot_size
                    }, timeout=10.0)

                    if order_resp.get('status') == 'ok':
                        order_id = order_resp.get('order_id')
                        log.info(f"✅ Grid resumed - BUY order {order_id} @ ${next_buy_level:,.0f}")
                        # Register pending buy so single-pending-order rule is enforced
                        await self.position_actor.tell("SET_PENDING_BUY", {
                            "order_id": order_id,
                            "price": next_buy_level,
                            "size": self.lot_size
                        })
                        if human_log:
                            human_log.info(f"Grid trading resumed - BUY order @ ${next_buy_level:,.0f}")
                    else:
                        log.warning(f"Failed to resume grid: {order_resp.get('error')}")
                else:
                    log.info(f"✓ Next BUY level ${next_buy_level or 'N/A'} outside grid bounds or unavailable")

            elif self.mode == "SHORT":
                # GridCalculator determines next SELL based on:
                # - If positions exist: highest_entry + step
                # - If no positions: proper grid level above current price
                next_sell_level = self.grid_calc.compute_next_sell_level(
                    open_positions=positions,
                    current_price=current_price
                )

                if next_sell_level and next_sell_level <= self.grid_calc.upper:
                    log.info(f"🟢 Resuming SHORT grid - placing SELL @ ${next_sell_level:,.0f}")
                    log.info(f"   Current price: ${current_price:,.0f}")
                    log.info(f"   Open positions: {len(positions)}")

                    order_resp = await self.order_actor.ask("PLACE_SELL", {
                        "price": next_sell_level,
                        "size": self.lot_size
                    }, timeout=10.0)

                    if order_resp.get('status') == 'ok':
                        order_id = order_resp.get('order_id')
                        log.info(f"✅ Grid resumed - SELL order {order_id} @ ${next_sell_level:,.0f}")
                        # Register pending sell so single-pending-order rule is enforced
                        await self.position_actor.tell("SET_PENDING_SELL", {
                            "order_id": order_id,
                            "price": next_sell_level,
                            "size": self.lot_size
                        })
                        if human_log:
                            human_log.info(f"Grid trading resumed - SELL order @ ${next_sell_level:,.0f}")
                    else:
                        log.warning(f"Failed to resume grid: {order_resp.get('error')}")
                else:
                    log.info(f"✓ Next SELL level ${next_sell_level or 'N/A'} outside grid bounds or unavailable")

        except Exception as e:
            log.error(f"Error resuming grid trading: {e}")

    async def health_monitor_loop(self) -> None:
        """
        CRITICAL: Monitor Guardian bot health every 15 seconds.

        RULE: No Guardian = No Trading (KISS principle)
        If Guardian stops or becomes unresponsive, GridBot MUST stop immediately.

        CRITICAL FIX (Dec 11, 2025):
        Also checks for Guardian signal transitions (STOP -> GO) and retries missed orders.
        """
        log.info("🛡️  Guardian health monitor started - checking every 15 seconds")
        log.info("🛡️  RULE: No Guardian = No Trading")
        log.info("🔄 Auto-retry: Missed orders will be retried when Guardian signal becomes GO")

        while self._get_running():
            try:
                # Check Guardian signal to verify it's alive
                signal, reason = await self.read_signal()

                # Check for signal transition and retry missed orders
                await self.check_transition_and_retry()

                # If Guardian stopped, read_signal already set _running = False
                # This loop will exit naturally
                if not self._get_running():
                    log.error("🚨 Guardian health monitor detected bot shutdown - exiting")
                    break

                # Sleep for 15 seconds before next check
                await asyncio.sleep(15)

            except Exception as e:
                log.error(f"🚨 Guardian health monitor error: {e}")
                log.error(f"🛑 Cannot monitor Guardian. Stopping bot for safety.")
                self._set_running(False)
                break
