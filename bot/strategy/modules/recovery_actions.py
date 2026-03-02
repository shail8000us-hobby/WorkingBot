"""
RecoveryActions — Phase 7 extracted module.

Handles background safety/recovery loops:
  - safety_gatekeeper_loop       (periodic unhedged-position check)
  - check_for_unhedged_positions (detect positions without TP orders)
  - fill_polling_fallback_loop   (REST fill poll every 60 s)
  - process_tp_retry_queue       (retry failed TP placements)
  - reconciliation_action_processor / execute_reconciliation_action
  - place_emergency_tp_for_position
"""

from __future__ import annotations

import asyncio
import json
import time
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional

log = logging.getLogger(__name__)

try:
    from bot.utils import human_log
except ImportError:
    class _FallbackHumanLog:
        def monitoring_active(self): pass
        def error(self, msg): log.error(msg)
    human_log = _FallbackHumanLog()


class RecoveryActions:
    """Background safety and recovery loops extracted from AsyncGridBot."""

    def __init__(
        self,
        position_actor,
        order_actor,
        api_client,
        fill_processor,
        product_id: str,
        symbol: str,
        mode: str,
        lot_size: int,
    ):
        self.position_actor = position_actor
        self.order_actor = order_actor
        self.api_client = api_client
        self.fill_processor = fill_processor
        self.product_id = product_id
        self.symbol = symbol
        self.mode = mode
        self.lot_size = lot_size

        # Runtime refs — set via set_runtime_refs() once the orchestrator is live
        self._get_running: Callable[[], bool] = lambda: True
        self._get_last_safety_check_time: Callable[[], float] = lambda: 0.0
        self._set_last_safety_check_time: Callable[[float], None] = lambda v: None

    def set_runtime_refs(self, **kwargs) -> None:
        """Wire runtime callbacks after bot is fully initialised."""
        for key, value in kwargs.items():
            setattr(self, key, value)

    # =========================================================================
    # Safety gatekeeper (moved from async_gridbot._safety_gatekeeper_loop)
    # =========================================================================

    async def safety_gatekeeper_loop(self) -> None:
        """
        Periodic safety check loop - runs every 5 minutes.
        Also triggered by state changes (via _process_fill).
        """
        log.info("Safety gatekeeper loop started - checking every 5 minutes")
        human_log.monitoring_active()  # Human-readable

        while self._get_running():
            try:
                current_time = time.time()

                # Check if 5 minutes (300 seconds) have elapsed since last check
                if current_time - self._get_last_safety_check_time() >= 300:
                    log.info("🔒 Running periodic safety check (5-minute interval)...")

                    # CRITICAL FIX (Jan 20, 2026): Check for unhedged positions
                    # Detects positions without TP orders (missed fills due to WebSocket drops)
                    await self.check_for_unhedged_positions()

                    # Safety limit checking removed - Guardian monitors all risk parameters
                    self._set_last_safety_check_time(current_time)

                # Sleep for 30 seconds, then check again
                await asyncio.sleep(30)

            except Exception as e:
                log.error(f"Safety gatekeeper error: {e}")
                await asyncio.sleep(60)  # Back off on error

    async def check_for_unhedged_positions(self) -> None:
        """
        CRITICAL FIX (Jan 20, 2026): Check for unhedged positions.

        Detects positions that exist on exchange but don't have TP orders.
        This can happen when:
        - WebSocket fill notification is dropped
        - Bot crashes after fill but before placing TP
        - TP order placement fails during Guardian STOP
        """
        try:
            # Get positions from bot memory
            state = await self.position_actor.ask("GET_STATE", {})
            bot_positions = state.get("open_tranches", [])

            # Get all open orders from exchange
            open_orders = await self.api_client.list_orders(symbol=self.symbol, states='open')

            # Find positions without TP orders
            unhedged_positions = []

            for position in bot_positions:
                tp_order_id = position.get("tp_order_id")
                tp_price = position.get("tp_price")
                entry_price = position.get("entry_price")

                if not tp_order_id:
                    # Position has no TP order ID - check if TP exists by price
                    tp_exists = any(
                        abs(float(o.get('limit_price', 0)) - tp_price) < 0.01
                        and o.get('reduce_only', False)
                        and o.get('side', '').lower() == ('sell' if self.mode == 'LONG' else 'buy')
                        for o in open_orders
                    )

                    if not tp_exists:
                        unhedged_positions.append({
                            'position_id': position.get('position_id'),
                            'entry_price': entry_price,
                            'tp_price': tp_price,
                            'size': position.get('size')
                        })

            if unhedged_positions:
                log.error("=" * 80)
                log.error("⚠️  CRITICAL: UNHEDGED POSITIONS DETECTED")
                log.error(f"   Found {len(unhedged_positions)} position(s) without TP orders")
                log.error("=" * 80)

                for pos in unhedged_positions:
                    log.error(f"   Position: Entry=${pos['entry_price']:,.0f}, Expected TP=${pos['tp_price']:,.0f}, Size={pos['size']}")
                    log.error(f"   Position ID: {pos['position_id']}")
                    log.error(f"   ⚠️  RECOMMENDED: Manually place TP order at ${pos['tp_price']:,.0f} (reduce_only=True)")

                log.error("=" * 80)

                # Log to human logger for visibility
                human_log.error(f"UNHEDGED POSITIONS: {len(unhedged_positions)} positions without TP orders")
            else:
                log.debug("✅ All positions have TP orders")

        except Exception as e:
            log.error(f"Error checking for unhedged positions: {e}")

    # =========================================================================
    # Fill polling fallback (moved from async_gridbot._fill_polling_fallback_loop)
    # =========================================================================

    async def fill_polling_fallback_loop(self) -> None:
        """
        CRITICAL FIX (Jan 20, 2026): Fill polling fallback.

        Polls exchange for recent fills every 60 seconds as backup for WebSocket.
        This catches fills that were missed due to:
        - WebSocket message queue overflow
        - WebSocket disconnection
        - WebSocket delivery failures

        Uses existing fill deduplication (_seen_fill_ids) to prevent double-processing.
        """
        log.info("🔄 Fill polling fallback started - checking every 60 seconds")
        log.info("   This is a safety backup for WebSocket fill notifications")

        await asyncio.sleep(30)  # FIX C5: Reduced from 120s to 30s to minimize blind spot at startup

        while self._get_running():
            try:
                # Query recent fills (last 5 minutes) using /v2/fills endpoint
                current_time_us = int(time.time() * 1_000_000)  # Current time in microseconds
                five_min_ago_us = current_time_us - (5 * 60 * 1_000_000)  # 5 minutes ago

                recent_fills = await self.api_client.rest_client.get_fills(
                    product_id=self.product_id,
                    start_time=five_min_ago_us
                )

                if recent_fills:
                    # Process only fills we haven't seen via WebSocket
                    new_fills_found = 0

                    for fill in recent_fills:
                        # Fill records have 'id' field directly (not order_id)
                        fill_id = str(fill.get('id'))
                        order_id = str(fill.get('order_id'))

                        # FIX C2: Check BOTH fill_id and order_id for consistent deduplication
                        # WebSocket may have stored fill under exchange_fill_id or order-{order_id}
                        already_seen = (
                            self.fill_processor.is_fill_seen(fill_id) or
                            self.fill_processor.is_fill_seen(f"fill-{fill_id}") or
                            self.fill_processor.is_order_fill_seen(order_id)
                        )

                        if not already_seen:
                            # New fill detected! Process it
                            new_fills_found += 1
                            log.warning("=" * 80)
                            log.warning("⚠️  FILL POLLING FALLBACK: Missed fill detected!")
                            log.warning(f"   Fill ID: {fill_id}")
                            log.warning(f"   Order ID: {order_id}")
                            log.warning(f"   Price: ${float(fill.get('price', 0)):,.2f}")
                            log.warning(f"   Side: {fill.get('side', '').upper()}")
                            log.warning(f"   Size: {fill.get('size')}")
                            log.warning("   This fill was NOT received via WebSocket")
                            log.warning("=" * 80)

                            # Create a fill-like object for processing
                            fill_data = {
                                'id': fill_id,
                                'order_id': order_id,
                                'product_id': fill.get('product_id'),
                                'size': fill.get('size'),
                                'price': fill.get('price'),
                                'side': fill.get('side'),
                                'timestamp': fill.get('created_at')
                            }

                            # Process the fill through normal fill handler
                            await self.fill_processor.process_fill(fill_data)

                    if new_fills_found > 0:
                        log.error(f"🚨 Fill polling found {new_fills_found} missed fill(s)")
                    else:
                        log.debug("✅ Fill polling: No missed fills")

                # Wait 60 seconds before next poll
                await asyncio.sleep(60)

            except Exception as e:
                log.error(f"Fill polling fallback error: {e}")
                await asyncio.sleep(60)  # Continue despite errors

    # =========================================================================
    # TP retry queue (moved from async_gridbot._process_tp_retry_queue)
    # =========================================================================

    async def process_tp_retry_queue(self) -> None:
        """
        Process TP retry queue - retry failed TP placements.

        Runs every 30s as part of health check loop.
        Retries positions in queue that are due for retry.
        """
        try:
            # Get due retries from position actor
            result = await self.position_actor.ask("GET_DUE_RETRIES", {}, timeout=5.0)

            due_retries = result.get("retries", [])
            total_queue_size = result.get("total_queue_size", 0)

            if not due_retries:
                if total_queue_size > 0:
                    log.debug(f"TP retry queue: {total_queue_size} pending (none due yet)")
                return

            log.info(f"⏰ Processing {len(due_retries)} due TP retries (queue: {total_queue_size})")

            for retry_entry in due_retries:
                position = retry_entry.get("position", {})
                retry_count = retry_entry.get("retry_count", 0)
                max_retries = retry_entry.get("max_retries", 5)

                position_id = position.get("position_id")
                entry_price = position.get("entry_price")
                tp_price = position.get("tp_price")
                size = position.get("size", 1)

                # Check if exhausted
                if retry_count >= max_retries:
                    log.critical(f"🚨 TP retry exhausted for position {position_id} @ ${entry_price:,.0f}")
                    log.critical(f"   Retried {retry_count} times - MANUAL INTERVENTION REQUIRED")

                    # Remove from queue
                    await self.position_actor.tell("REMOVE_FROM_RETRY_QUEUE", {
                        "retry_entry": retry_entry
                    })

                    # Send Telegram alert
                    try:
                        from bot.utils.notifier import TelegramNotifier
                        notifier = TelegramNotifier()
                        notifier.send(
                            f"🚨 TP RETRY EXHAUSTED\n\n"
                            f"Position: {position_id}\n"
                            f"Entry: ${entry_price:,.0f}\n"
                            f"TP: ${tp_price:,.0f}\n"
                            f"Retries: {retry_count}/{max_retries}\n\n"
                            f"⚠️ MANUAL TP PLACEMENT REQUIRED"
                        )
                    except Exception:
                        pass  # Telegram not critical

                    continue

                # Attempt TP placement
                log.info(f"⏰ Retrying TP placement (attempt {retry_count + 1}/{max_retries})")
                log.info(f"   Position: {position_id} @ ${entry_price:,.0f} → ${tp_price:,.0f}")

                try:
                    # Place TP via order actor
                    result = await self.order_actor.ask("PLACE_TP", {
                        "price": tp_price,
                        "size": size,
                        "position_id": position_id
                    }, timeout=15.0)

                    if result.get("status") == "ok":
                        tp_order_id = result.get("order_id")
                        log.info(f"✅ TP retry successful: Order {tp_order_id}")

                        # Update position with TP order ID
                        await self.position_actor.tell("UPDATE_POSITION", {
                            "position_id": position_id,
                            "tp_order_id": tp_order_id,
                            "tp_price": tp_price
                        })

                        # Remove from retry queue
                        await self.position_actor.tell("REMOVE_FROM_RETRY_QUEUE", {
                            "retry_entry": retry_entry
                        })

                        log.info(f"✅ Position {position_id} protected with TP")
                    else:
                        # Retry failed - reschedule
                        log.warning(f"⚠️ TP retry failed: {result.get('error')}")
                        log.warning(f"   Will retry again in 10 seconds")

                        # Reschedule with incremented retry count
                        await self.position_actor.tell("SCHEDULE_TP_RETRY", {
                            "position": position,
                            "retry_count": retry_count,  # Will be incremented in handler
                            "max_retries": max_retries
                        })

                        # Remove old entry
                        await self.position_actor.tell("REMOVE_FROM_RETRY_QUEUE", {
                            "retry_entry": retry_entry
                        })

                except Exception as e:
                    log.error(f"❌ TP retry exception: {e}")
                    log.error(f"   Will retry again in 10 seconds")

                    # Reschedule with incremented retry count
                    await self.position_actor.tell("SCHEDULE_TP_RETRY", {
                        "position": position,
                        "retry_count": retry_count,
                        "max_retries": max_retries
                    })

                    # Remove old entry
                    await self.position_actor.tell("REMOVE_FROM_RETRY_QUEUE", {
                        "retry_entry": retry_entry
                    })

        except Exception as e:
            log.error(f"TP retry queue processing error: {e}")

    # =========================================================================
    # Reconciliation action processor (moved from async_gridbot)
    # =========================================================================

    async def reconciliation_action_processor(self) -> None:
        """
        Process actions from standalone reconciliation engine.
        Reads action_queue.json and executes corrections.
        """
        action_queue_file = Path("data/reconciliation/action_queue.json")

        log.info("📋 Reconciliation action processor started")

        while self._get_running():
            try:
                # Check if action queue exists
                if not action_queue_file.exists():
                    await asyncio.sleep(10)
                    continue

                # Load action queue
                with open(action_queue_file) as f:
                    data = json.load(f)
                    actions = data.get("actions", [])

                # Process pending actions
                pending_actions = [a for a in actions if a.get("status") == "pending"]

                if pending_actions:
                    log.info(f"📋 Processing {len(pending_actions)} reconciliation action(s)")

                for action in pending_actions:
                    try:
                        await self.execute_reconciliation_action(action)

                        # Mark as completed
                        action["status"] = "completed"
                        action["completed_at"] = time.time()

                    except Exception as e:
                        log.error(f"Error executing action {action.get('id')}: {e}")
                        action["status"] = "failed"
                        action["error"] = str(e)
                        action["failed_at"] = time.time()

                # Write updated queue
                if pending_actions:
                    temp_file = action_queue_file.with_suffix('.tmp')
                    with open(temp_file, 'w') as f:
                        json.dump(data, f, indent=2)
                    temp_file.replace(action_queue_file)

                # Wait before next check
                await asyncio.sleep(10)  # Check every 10 seconds

            except Exception as e:
                log.error(f"Reconciliation action processor error: {e}")
                await asyncio.sleep(30)

    async def execute_reconciliation_action(self, action: Dict) -> None:
        """Execute a single reconciliation action"""
        action_type = action.get("type")
        action_id = action.get("id")

        log.info(f"🔧 Executing {action_type} (ID: {action_id})")

        if action_type == "process_missed_fill":
            # Process missed fill
            await self.fill_processor.process_missed_fill_by_params(
                order_id=action["order_id"],
                side=action["side"],
                fill_price=action["fill_price"],
                fill_size=action["fill_size"]
            )
            log.info(f"✅ Processed missed fill for order {action['order_id']}")

        elif action_type == "place_emergency_tp":
            # Place emergency TP
            position_id = action["position_id"]
            tp_price = action["tp_price"]

            # Get position details
            state = await self.position_actor.ask("GET_STATE", {})
            position = None
            for pos in state.get("open_tranches", []):
                if pos.get("position_id") == position_id:
                    position = pos
                    break

            if position:
                await self.place_emergency_tp_for_position(position, tp_price)
                log.info(f"✅ Placed emergency TP for position {position_id}")
            else:
                log.warning(f"⚠️  Position {position_id} not found")

        elif action_type == "cancel_orphaned_order":
            # Cancel orphaned order
            order_id = action["order_id"]

            try:
                result = await self.order_actor.ask("CANCEL_ORDER", {
                    "order_id": order_id
                }, timeout=10.0)

                if result.get("status") == "ok":
                    log.info(f"✅ Cancelled orphaned order {order_id}")
                else:
                    log.warning(f"⚠️  Failed to cancel order {order_id}: {result.get('error')}")
            except Exception as e:
                log.error(f"Error cancelling order {order_id}: {e}")

        elif action_type == "flag_corrupted_state":
            # Flag corrupted state (log only)
            position_id = action["position_id"]
            field = action["field"]
            log.critical(f"🚨 CORRUPTED STATE: Position {position_id} has invalid {field}")
            log.critical(f"   Manual intervention required!")

        else:
            log.warning(f"⚠️  Unknown action type: {action_type}")

    # =========================================================================
    # Emergency TP placement (moved from async_gridbot._place_emergency_tp_for_position)
    # =========================================================================

    async def place_emergency_tp_for_position(self, position: Dict, tp_price: float) -> None:
        """Place emergency TP for a position"""
        try:
            position_id = position.get("position_id")
            size = position.get("size", self.lot_size)

            result = await self.order_actor.ask("PLACE_TP", {
                "price": tp_price,
                "size": size,
                "position_id": position_id
            }, timeout=10.0)

            if result.get("status") == "ok":
                tp_order_id = result.get("order_id")

                # Update position with TP order ID
                await self.position_actor.tell("UPDATE_POSITION_TP", {
                    "position_id": position_id,
                    "tp_order_id": tp_order_id
                })

                log.info(f"✅ Emergency TP placed: {tp_order_id} @ ${tp_price:,.0f}")
            else:
                log.error(f"❌ Emergency TP failed: {result.get('error')}")

        except Exception as e:
            log.error(f"Error placing emergency TP: {e}")
