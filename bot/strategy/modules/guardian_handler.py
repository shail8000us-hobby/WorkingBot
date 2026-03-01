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
                        # STARTUP: Bot hasn't started yet. A stale signal from days ago
                        # should NOT block startup. Guardian will publish fresh signals
                        # once it's running. Treat stale signals as expired during startup.
                        log.warning(f"⚠️  Guardian signal stale ({signal_age:.0f}s) during STARTUP - treating as expired")
                        log.warning(f"   Original signal: {signal} - {reason}")
                        log.warning(f"   Stale signals do not block startup. Guardian will publish fresh signals.")
                        return 'GO', f'Guardian signal expired during startup ({signal_age:.0f}s old)'
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
        Check if Guardian signal transitioned from STOP to GO.
        If yes, retry placing missed grid orders that were skipped.

        CRITICAL FIX (Dec 11, 2025):
        When Guardian blocks order placement during saga execution,
        we need to retry those missed orders when Guardian gives GO signal.
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

                # Retry missed grid orders
                if self._missed_grid_orders:
                    await self.retry_missed_orders()

                # A3: Check for multi-step price moves during the STOP period
                await self.fill_multi_step_missed_grids()

            # Track signal for next check
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
                    log.info(f"   ⏭️  Skipping SELL @ ${price:,.0f} - already have pending sell")
                    skipped += 1
                    processed_orders.append(missed_order)  # Mark as processed
                    continue

                # Retry placing SELL order (this shouldn't happen often)
                # SELL orders are usually for positions, not grid seeding
                log.warning(f"   ⚠️  Skipping SELL @ ${price:,.0f} - SELL retry not implemented")
                skipped += 1
                processed_orders.append(missed_order)  # Mark as processed

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
        """Stub — replaced in P1.5 with real implementation."""
        log.warning("fill_multi_step_missed_grids stub called — real method arrives in P1.5")
