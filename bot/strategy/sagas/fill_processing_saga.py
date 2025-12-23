"""
Fill Processing Saga for handling order fills.
Implements transactional processing with automatic compensation.
"""

import asyncio
import time
from typing import Dict, Any, Optional
from uuid import uuid4

from loguru import logger as log

from bot.strategy.actors.base_actor import Message
from bot.strategy.actors.position_actor import PositionManagerActor
from bot.strategy.actors.order_actor import OrderManagerActor
from bot.strategy.sagas.saga_coordinator import Saga, SagaStep
from bot.strategy.modules.event_store import EventStore
from bot.strategy.modules.grid_calculator import GridCalculator


async def create_buy_fill_saga(
    fill_data: Dict[str, Any],
    correlation_id: str,
    position_actor: PositionManagerActor,
    order_actor: OrderManagerActor,
    grid_calc: GridCalculator,
    event_store: EventStore,
    mode: str = "LONG"
) -> Saga:
    """
    Create saga for processing BUY fill.
    
    Steps:
    1. Add position to state
    1.5. Clear pending buy order
    2. Place TP order
    3. Place next grid order (if fill complete)
    
    Args:
        fill_data: Fill information
        correlation_id: Correlation ID
        position_actor: Position manager actor
        order_actor: Order manager actor
        grid_calc: Grid calculator
        event_store: Event store
        mode: Trading mode (LONG/SHORT)
        
    Returns:
        Configured saga
    """
    saga = Saga(
        saga_id=f"buy-fill-{fill_data['order_id']}-{int(time.time()*1000)}",
        correlation_id=correlation_id,
        event_store=event_store,
        timeout=30.0
    )
    
    # Generate position ID
    position_id = str(uuid4())
    
    # Store results for compensation
    position_result: Optional[Dict] = None
    tp_result: Optional[Dict] = None
    grid_result: Optional[Dict] = None
    
    # STEP 1: Add Position
    async def add_position_action() -> Dict[str, Any]:
        nonlocal position_result
        
        # Use main GridCalculator method for TP price calculation
        if mode == "LONG":
            tp_price = grid_calc.compute_tp_price(fill_data["fill_price"])
        else:  # SHORT
            tp_price = grid_calc.compute_tp_price_short(fill_data["fill_price"])
        
        position = {
            "position_id": position_id,
            "entry_order_id": position_id,  # For reconciliation compatibility
            "entry_price": fill_data["fill_price"],
            "tp_price": tp_price,
            "size": fill_data["fill_size"],
            "correlation_id": correlation_id
        }
        
        log.info(f"[SAGA] Adding position: {position_id} @ {fill_data['fill_price']}")
        
        # Send message to actor
        reply_queue = asyncio.Queue()
        await position_actor.mailbox.put(
            Message("ADD_POSITION", position, reply_queue, correlation_id)
        )
        
        # Wait for reply
        result = await asyncio.wait_for(reply_queue.get(), timeout=5.0)
        
        if result["status"] != "ok":
            raise Exception(f"Failed to add position: {result.get('error')}")
        
        position_result = position
        return position
    
    async def add_position_compensation(position: Dict[str, Any]) -> None:
        log.info(f"[SAGA] Compensating: Removing position {position_id}")
        
        # Remove position
        await position_actor.mailbox.put(
            Message("REMOVE_POSITION", {"position_id": position_id}, None, correlation_id)
        )
    
    saga.add_step(SagaStep(
        name="add_position",
        action=add_position_action,
        compensation=add_position_compensation,
        critical=False
    ))
    
    # STEP 1.5: Clear pending buy (entry order filled)
    async def clear_pending_buy_action() -> Dict[str, Any]:
        log.info(f"[SAGA] Clearing pending buy for order {fill_data['order_id']}")
        
        # Clear pending buy since entry order filled
        await position_actor.mailbox.put(
            Message("CLEAR_PENDING_BUY", {"order_id": fill_data["order_id"]}, None, correlation_id)
        )
        
        return {"cleared": True}
    
    async def clear_pending_buy_compensation(result: Dict[str, Any]) -> None:
        # No compensation needed for clearing pending
        pass
    
    saga.add_step(SagaStep(
        name="clear_pending_buy",
        action=clear_pending_buy_action,
        compensation=clear_pending_buy_compensation,
        critical=False
    ))
    
    # STEP 2: Place TP Order
    async def place_tp_action() -> Dict[str, Any]:
        nonlocal tp_result
        
        if not position_result:
            raise Exception("No position result available")
        
        tp_price = position_result["tp_price"]
        
        log.info(f"[SAGA] Placing TP order @ {tp_price} for position {position_id}")
        
        # CRITICAL FIX (Dec 12, 2025): Check Guardian signal before placing TP order
        # This prevents unhedged positions during Guardian STOP periods
        from bot.strategy.modules.event_store import EventType
        import time as time_module
        
        try:
            guardian_events = event_store.get_events_by_type(
                [EventType.GUARDIAN_SIGNAL_GO, EventType.GUARDIAN_SIGNAL_STOP],
                limit=1
            )
            
            if guardian_events:
                latest_guardian = guardian_events[0]
                signal = 'GO' if latest_guardian.event_type == EventType.GUARDIAN_SIGNAL_GO else 'STOP'
                signal_age = time_module.time() - latest_guardian.timestamp
                
                if signal == 'STOP':
                    reason = latest_guardian.data.get('reason', 'No reason provided')
                    log.warning(f"⚠️ [SAGA] Guardian signal is STOP - Cannot place TP SELL order")
                    log.warning(f"   Reason: {reason}")
                    log.warning(f"   ⚠️  MISSED TP ORDER: SELL @ ${tp_price:,.0f}")
                    log.warning(f"   💡 TIP: TP order will be scheduled for retry when Guardian signal becomes GO")
                    
                    # Schedule TP retry via position actor
                    try:
                        await position_actor.mailbox.put(
                            Message("SCHEDULE_TP_RETRY", {
                                "position": {
                                    "position_id": position_id,
                                    "entry_price": fill_data["fill_price"],
                                    "tp_price": tp_price,
                                    "size": fill_data["fill_size"]
                                },
                                "retry_count": 0,
                                "max_retries": 5
                            }, None, correlation_id)
                        )
                        log.info(f"⏰ [SAGA] TP order scheduled for retry")
                    except Exception as e:
                        log.error(f"❌ [SAGA] Failed to schedule TP retry: {e}")
                    
                    return {"status": "skipped", "reason": f"guardian_stop: {reason}", "tp_scheduled_for_retry": True}
                
                if signal_age > 30:
                    log.warning(f"⚠️ [SAGA] Guardian signal is stale ({signal_age:.0f}s old) - Proceeding with caution")
            else:
                log.warning(f"⚠️ [SAGA] No Guardian signal found - Cannot place TP order safely")
                return {"status": "skipped", "reason": "no_guardian_signal"}
                
        except Exception as guardian_error:
            log.error(f"❌ [SAGA] Error checking Guardian signal: {guardian_error}")
            return {"status": "skipped", "reason": f"guardian_check_error: {str(guardian_error)}"}
        
        # Send message to actor
        reply_queue = asyncio.Queue()
        await order_actor.mailbox.put(
            Message("PLACE_TP", {
                "price": tp_price,
                "size": fill_data["fill_size"],
                "position_id": position_id
            }, reply_queue, correlation_id)
        )
        
        # Wait for reply
        result = await asyncio.wait_for(reply_queue.get(), timeout=10.0)
        
        if result["status"] != "ok":
            # TP placement failed - schedule for retry queue
            log.warning(f"⚠️ [SAGA] TP placement failed: {result.get('error')} - scheduling retry")
            
            # Schedule TP retry via position actor
            try:
                await position_actor.mailbox.put(
                    Message("SCHEDULE_TP_RETRY", {
                        "position": {
                            "position_id": position_id,
                            "entry_price": fill_data["fill_price"],
                            "tp_price": tp_price,
                            "size": fill_data["fill_size"]
                        },
                        "retry_count": 0,
                        "max_retries": 5
                    }, None, correlation_id)
                )
                log.info(f"⏰ [SAGA] Position scheduled for TP retry")
            except Exception as e:
                log.error(f"❌ [SAGA] Failed to schedule TP retry: {e}")
            raise Exception(f"TP placement failed and retry scheduling failed: {e}")
        else:
            tp_order_id = result.get("order_id")
            log.info(f"✅ [SAGA] TP order placed successfully: {tp_order_id}")
            
            # Update position with tp_order_id for reconciliation
            if tp_order_id:
                try:
                    await position_actor.mailbox.put(
                        Message("UPDATE_POSITION", {
                            "position_id": position_id,
                            "tp_order_id": str(tp_order_id)
                        }, None, correlation_id)
                    )
                except Exception as e:
                    log.warning(f"Failed to update position with tp_order_id: {e}")
        
        return result
    
    async def place_tp_compensation(tp_order: Dict[str, Any]) -> None:
        if not tp_order or "order_id" not in tp_order:
            log.warning("[SAGA] No TP order to compensate")
            return
        
        log.info(f"[SAGA] Compensating: Cancelling TP order {tp_order['order_id']}")
        
        # Cancel TP order
        await order_actor.mailbox.put(
            Message("CANCEL_ORDER", {"order_id": tp_order["order_id"]}, None, correlation_id)
        )
    
    saga.add_step(SagaStep(
        name="place_tp",
        action=place_tp_action,
        compensation=place_tp_compensation,
        critical=False
    ))
    
    # STEP 3: Place Next Grid Order (if fill is complete)
    if fill_data.get("is_complete", True):
        async def place_grid_action() -> Dict[str, Any]:
            nonlocal grid_result
            
            next_price = grid_calc.compute_next_level_down(fill_data["fill_price"])
            
            log.info(f"[SAGA] Placing next grid order @ {next_price}")
            
            # CRITICAL FIX (Dec 11, 2025): Check Guardian signal before placing order
            from bot.strategy.modules.event_store import EventType
            import time as time_module
            
            try:
                guardian_events = event_store.get_events_by_type(
                    [EventType.GUARDIAN_SIGNAL_GO, EventType.GUARDIAN_SIGNAL_STOP],
                    limit=1
                )
                
                if guardian_events:
                    latest_guardian = guardian_events[0]
                    signal = 'GO' if latest_guardian.event_type == EventType.GUARDIAN_SIGNAL_GO else 'STOP'
                    signal_age = time_module.time() - latest_guardian.timestamp
                    
                    if signal == 'STOP':
                        reason = latest_guardian.data.get('reason', 'No reason provided')
                        log.warning(f"⚠️ [SAGA] Guardian signal is STOP - Cannot place grid BUY order")
                        log.warning(f"   Reason: {reason}")
                        log.warning(f"   ⚠️  MISSED GRID ORDER: BUY @ ${next_price:,.0f}")
                        log.warning(f"   💡 TIP: Order will auto-retry when Guardian signal becomes GO")
                        return {"status": "skipped", "reason": f"guardian_stop: {reason}", "missed_order": {"price": next_price, "side": "buy"}}
                    
                    if signal_age > 30:
                        log.warning(f"⚠️ [SAGA] Guardian signal is stale ({signal_age:.0f}s old) - Proceeding with caution")
                else:
                    log.warning(f"⚠️ [SAGA] No Guardian signal found - Cannot place order safely")
                    return {"status": "skipped", "reason": "no_guardian_signal"}
                    
            except Exception as guardian_error:
                log.error(f"❌ [SAGA] Error checking Guardian signal: {guardian_error}")
                return {"status": "skipped", "reason": f"guardian_check_error: {str(guardian_error)}"}
            
            # Check if valid grid level
            if not grid_calc.is_price_grid_aligned(next_price):
                log.warning(f"[SAGA] Invalid grid level: {next_price} - skipping")
                return {"status": "skipped", "reason": "invalid_grid_level"}
            
            # SINGLE PENDING ORDER RULE: Cancel ALL other pending BUY orders
            # CRITICAL FIX (Dec 11, 2025): Wait for cancellation confirmation and track results
            # Get all open orders from exchange
            orders_queue = asyncio.Queue()
            await order_actor.mailbox.put(
                Message("GET_OPEN_ORDERS", {}, orders_queue, correlation_id)
            )
            
            try:
                open_orders_response = await asyncio.wait_for(orders_queue.get(), timeout=5.0)
                open_orders = open_orders_response.get("orders", [])
                
                # Get bot's tag prefix for identification
                bot_tag_prefix = getattr(order_actor, 'tag_prefix', 'GBOT_')
                
                # Track cancellation results
                orders_to_cancel = []
                cancellation_results = []
                
                # Collect ALL pending BUY orders that need cancellation
                for order in open_orders:
                    if order.get("side") == "buy" and order.get("state") == "open":
                        order_price = float(order.get("limit_price", 0))
                        order_id = str(order.get("id"))
                        is_reduce_only = order.get("reduce_only", False)
                        client_order_id = order.get("client_order_id", "")
                        
                        # Skip TP orders (reduce_only=True)
                        if is_reduce_only:
                            continue
                        
                        # CRITICAL: Skip manual orders (no bot tag)
                        if not client_order_id.startswith(bot_tag_prefix):
                            log.info(f"[SAGA] Preserving manual/external order #{order_id} @ ${order_price} (tag: {client_order_id})")
                            continue
                        
                        # Cancel this BUY order if it's not the exact price we want
                        if abs(order_price - next_price) > 0.01:
                            log.info(f"[SAGA] SINGLE PENDING ORDER RULE: Cancelling bot order #{order_id} @ ${order_price} (tag: {client_order_id}, keeping only ${next_price})")
                            orders_to_cancel.append((order_id, order_price))
                
                # Execute cancellations and wait for confirmation
                for order_id, order_price in orders_to_cancel:
                    try:
                        cancel_reply_queue = asyncio.Queue()
                        await order_actor.mailbox.put(
                            Message("CANCEL_ORDER", {"order_id": order_id}, cancel_reply_queue, correlation_id)
                        )
                        cancel_result = await asyncio.wait_for(cancel_reply_queue.get(), timeout=5.0)
                        
                        if cancel_result.get("status") == "ok":
                            log.info(f"✅ [SAGA] Successfully canceled order #{order_id} @ ${order_price}")
                            cancellation_results.append((order_id, True))
                        else:
                            log.error(f"❌ [SAGA] Failed to cancel order #{order_id}: {cancel_result.get('error')}")
                            cancellation_results.append((order_id, False))
                        
                        await asyncio.sleep(0.1)  # Small delay between cancellations
                    except asyncio.TimeoutError:
                        log.error(f"❌ [SAGA] Timeout cancelling order {order_id}")
                        cancellation_results.append((order_id, False))
                    except Exception as cancel_error:
                        log.error(f"❌ [SAGA] Exception cancelling order {order_id}: {cancel_error}")
                        cancellation_results.append((order_id, False))
                
                # Report cancellation summary
                successful_cancels = sum(1 for _, success in cancellation_results if success)
                failed_cancels = sum(1 for _, success in cancellation_results if not success)
                
                if orders_to_cancel:
                    log.info(f"📊 [SAGA] Cancellation summary: {successful_cancels} succeeded, {failed_cancels} failed out of {len(orders_to_cancel)} total")
                
                # Clear tracked pending_buy state only after cancellations complete
                await position_actor.mailbox.put(
                    Message("CLEAR_PENDING_BUY", {}, None, correlation_id)
                )
                
                await asyncio.sleep(0.3)  # Allow cancellations to settle on exchange
                
            except asyncio.TimeoutError:
                log.error(f"❌ [SAGA] Timeout getting open orders - CANNOT ensure single pending order rule!")
            except Exception as e:
                log.error(f"❌ [SAGA] Error in single pending order cleanup: {e}")
            
            # Verify no duplicate order exists at target price before placing
            # Check exchange state, not just bot state
            verify_queue = asyncio.Queue()
            await order_actor.mailbox.put(
                Message("GET_OPEN_ORDERS", {}, verify_queue, correlation_id)
            )
            
            try:
                verify_response = await asyncio.wait_for(verify_queue.get(), timeout=5.0)
                verify_orders = verify_response.get("orders", [])
                
                # Check if there's already a BUY order at next_price
                for order in verify_orders:
                    if order.get("side") == "buy" and order.get("state") == "open":
                        order_price = float(order.get("limit_price", 0))
                        is_reduce_only = order.get("reduce_only", False)
                        
                        if not is_reduce_only and abs(order_price - next_price) < 0.01:
                            log.warning(f"⚠️ [SAGA] Order already exists at ${next_price} (#{order.get('id')}) - skipping placement")
                            return {"status": "skipped", "reason": "duplicate_order_on_exchange"}
            except Exception as verify_error:
                log.warning(f"⚠️ [SAGA] Could not verify orders on exchange: {verify_error}")
            
            # ✅ CRITICAL FIX NOV 20 (8:25PM): Set pending buy state BEFORE placing order
            # This prevents race condition where order creation event triggers duplicate placement
            # We set a temporary pending state, then update with real order_id after placement
            await position_actor.mailbox.put(
                Message("SET_PENDING_BUY", {
                    "order_id": "PENDING",  # Temporary placeholder
                    "price": next_price,
                    "size": fill_data["fill_size"],
                    "timestamp": time.time()
                }, None, correlation_id)
            )
            log.info(f"[SAGA] Pre-set pending buy state at ${next_price} (prevents race condition)")
            
            # Send message to actor
            reply_queue = asyncio.Queue()
            await order_actor.mailbox.put(
                Message("PLACE_BUY", {
                    "price": next_price,
                    "size": fill_data["fill_size"]  # Use same size as filled order
                }, reply_queue, correlation_id)
            )
            
            # Wait for reply
            result = await asyncio.wait_for(reply_queue.get(), timeout=10.0)
            
            if result["status"] != "ok":
                # Grid order failure is non-critical - clear the pending state
                log.warning(f"[SAGA] Grid order failed (non-critical): {result.get('error')}")
                await position_actor.mailbox.put(
                    Message("CLEAR_PENDING_BUY", {}, None, correlation_id)
                )
                return {"status": "failed", "error": result.get("error")}
            
            # ✅ FIX NOV 20: Removed bot.fill_monitor reference (bot not in saga scope)
            # Fill monitoring is handled by the main bot's order tracking system
            
            # Update pending buy state with real order_id
            if "order_id" in result:
                await position_actor.mailbox.put(
                    Message("SET_PENDING_BUY", {
                        "order_id": result["order_id"],
                        "price": next_price,
                        "size": fill_data["fill_size"],
                        "timestamp": time.time()
                    }, None, correlation_id)
                )
                log.info(f"[SAGA] Updated pending buy state: {result['order_id']} @ ${next_price}")
            
            grid_result = result
            return result
        
        async def place_grid_compensation(grid_order: Dict[str, Any]) -> None:
            if not grid_order or grid_order.get("status") != "ok" or "order_id" not in grid_order:
                log.warning("[SAGA] No grid order to compensate")
                return
            
            log.info(f"[SAGA] Compensating: Cancelling grid order {grid_order['order_id']}")
            
            # Cancel grid order
            await order_actor.mailbox.put(
                Message("CANCEL_ORDER", {"order_id": grid_order["order_id"]}, None, correlation_id)
            )
        
        saga.add_step(SagaStep(
            name="place_grid_order",
            action=place_grid_action,
            compensation=place_grid_compensation,
            critical=False  # Grid order failure is not critical
        ))
    
    return saga


async def create_sell_fill_saga(
    fill_data: Dict[str, Any],
    correlation_id: str,
    position_actor: PositionManagerActor,
    order_actor: OrderManagerActor,
    grid_calc: GridCalculator,
    event_store: EventStore,
    mode: str = "LONG"
) -> Saga:
    """
    Create saga for processing SELL fill (TP hit).
    
    Steps:
    1. Find and remove position by TP price
    2. Clear pending sell order
    3. Place new BUY order at grid level
    
    Args:
        fill_data: Fill information
        correlation_id: Correlation ID
        position_actor: Position manager actor
        order_actor: Order manager actor
        grid_calc: Grid calculator
        event_store: Event store
        mode: Trading mode (LONG/SHORT)
        
    Returns:
        Configured saga
    """
    saga = Saga(
        saga_id=f"sell-fill-{fill_data['order_id']}-{int(time.time()*1000)}",
        correlation_id=correlation_id,
        event_store=event_store,
        timeout=30.0
    )
    
    # Store results for compensation
    position_removed: Optional[Dict] = None
    pending_cleared: bool = False
    buy_result: Optional[Dict] = None
    
    # STEP 1: Find and Remove Position
    async def remove_position_action() -> Dict[str, Any]:
        nonlocal position_removed
        
        log.info(f"[SAGA] Finding position by TP price: {fill_data['fill_price']}")
        
        # Find position by TP price
        reply_queue = asyncio.Queue()
        await position_actor.mailbox.put(
            Message("GET_POSITION_BY_TP", {"tp_price": fill_data["fill_price"]}, reply_queue, correlation_id)
        )
        
        position = await asyncio.wait_for(reply_queue.get(), timeout=5.0)
        
        if not position:
            raise Exception(f"No position found with TP price: {fill_data['fill_price']}")
        
        log.info(f"[SAGA] Removing position: {position['position_id']}")
        
        # Remove position
        reply_queue = asyncio.Queue()
        await position_actor.mailbox.put(
            Message("REMOVE_POSITION", {"position_id": position["position_id"]}, reply_queue, correlation_id)
        )
        
        result = await asyncio.wait_for(reply_queue.get(), timeout=5.0)
        
        if result["status"] != "ok":
            raise Exception(f"Failed to remove position: {result.get('error')}")
        
        position_removed = position
        return position
    
    async def remove_position_compensation(position: Dict[str, Any]) -> None:
        if not position:
            log.warning("[SAGA] No position to restore")
            return
        
        log.info(f"[SAGA] Compensating: Restoring position {position['position_id']}")
        
        # Re-add position
        await position_actor.mailbox.put(
            Message("ADD_POSITION", position, None, correlation_id)
        )
    
    saga.add_step(SagaStep(
        name="remove_position",
        action=remove_position_action,
        compensation=remove_position_compensation,
        critical=True  # Critical - position must be removed
    ))
    
    # STEP 2: Clear Pending Sell
    async def clear_pending_action() -> Dict[str, Any]:
        nonlocal pending_cleared
        
        log.info(f"[SAGA] Clearing pending sell for order {fill_data['order_id']}")
        
        # Clear pending sell
        reply_queue = asyncio.Queue()
        await position_actor.mailbox.put(
            Message("CLEAR_PENDING_SELL", {"order_id": fill_data["order_id"]}, reply_queue, correlation_id)
        )
        
        result = await asyncio.wait_for(reply_queue.get(), timeout=5.0)
        
        pending_cleared = result.get("cleared", False)
        return {"cleared": pending_cleared}
    
    async def clear_pending_compensation(result: Dict[str, Any]) -> None:
        # No compensation needed for clearing pending
        pass
    
    saga.add_step(SagaStep(
        name="clear_pending_sell",
        action=clear_pending_action,
        compensation=clear_pending_compensation,
        critical=False
    ))
    
    # STEP 3: Place New BUY Order
    if fill_data.get("is_complete", True):
        async def place_buy_action() -> Dict[str, Any]:
            nonlocal buy_result
            
            if not position_removed:
                raise Exception("No position data available")
            
            # FIX NOV 14: Calculate next buy level from TP price (market moved UP to TP)
            # New BUY should be 1 step BELOW TP, not 1 step below old entry
            # CRITICAL FIX (Dec 18, 2025): Use fill_price directly for consistency
            tp_price = fill_data["fill_price"]  # Use fill price directly
            next_price = grid_calc.compute_next_level_down(tp_price)
            
            log.info(f"[SAGA] TP filled @ {fill_data['fill_price']}, calculating new BUY @ {next_price} (TP - 1 step)")
            
            # ============================================================================
            # SINGLE WRITER PATTERN (Dec 19, 2025) - Institutional Grade Solution
            # ============================================================================
            # Instead of saga doing everything (cancel + place + update state),
            # delegate to OrderActor which owns all order operations.
            #
            # Benefits:
            # - OrderActor mailbox provides natural serialization (no locks!)
            # - Concurrent sagas can't race - mailbox processes one at a time
            # - Fast: No blocking, async event loop continues
            # - Clean: Saga focuses on business logic, OrderActor handles infrastructure
            #
            # This is how institutional trading systems prevent race conditions.
            # ============================================================================
            
            log.info(f"[SAGA] Delegating atomic order replacement to OrderActor...")
            
            reply_queue = asyncio.Queue()
            await order_actor.mailbox.put(
                Message("REPLACE_PENDING_BUY_ORDER", {
                    "price": next_price,
                    "size": fill_data["fill_size"],
                    "check_guardian": True  # OrderActor will check Guardian signal
                }, reply_queue, correlation_id)
            )
            
            # Wait for atomic operation to complete
            result = await asyncio.wait_for(reply_queue.get(), timeout=15.0)
            
            if result["status"] == "skipped":
                reason = result.get("reason", "unknown")
                log.warning(f"⚠️ [SAGA] Order replacement skipped: {reason}")
                log.warning(f"   Cancelled {len(result.get('cancelled_orders', []))} old orders")
                if "missed_order" in result:
                    missed = result["missed_order"]
                    log.warning(f"   ⚠️  MISSED GRID ORDER: {missed['side'].upper()} @ ${missed['price']:,.0f}")
                return result
            
            if result["status"] != "ok":
                error = result.get("error", "unknown")
                log.error(f"❌ [SAGA] Order replacement FAILED: {error}")
                return result
            
            # Success!
            order_id = result["order_id"]
            cancelled_count = len(result.get("cancelled_orders", []))
            
            log.info(f"✅ [SAGA] Atomic order replacement completed:")
            log.info(f"   Cancelled: {cancelled_count} old BUY orders")
            log.info(f"   Placed: BUY #{order_id} @ ${next_price:,.0f}")
            log.info(f"   📊 Summary: TP @ ${tp_price:,.0f} → {cancelled_count} cancelled → New BUY @ ${next_price:,.0f}")
            
            # Update pending buy state in PositionActor
            await position_actor.mailbox.put(
                Message("SET_PENDING_BUY", {
                    "order_id": order_id,
                    "price": next_price,
                    "size": 1
                }, None, correlation_id)
            )
            
            buy_result = result
            return result
        
        async def place_buy_compensation(buy_order: Dict[str, Any]) -> None:
            if not buy_order or buy_order.get("status") != "ok" or "order_id" not in buy_order:
                log.warning("[SAGA] No buy order to compensate")
                return
            
            log.info(f"[SAGA] Compensating: Cancelling buy order {buy_order['order_id']}")
            
            # Cancel buy order
            await order_actor.mailbox.put(
                Message("CANCEL_ORDER", {"order_id": buy_order["order_id"]}, None, correlation_id)
            )
            
            # Clear pending buy
            await position_actor.mailbox.put(
                Message("CLEAR_PENDING_BUY", {"order_id": buy_order["order_id"]}, None, correlation_id)
            )
        
        saga.add_step(SagaStep(
            name="place_buy_order",
            action=place_buy_action,
            compensation=place_buy_compensation,
            critical=False  # Buy order failure is not critical
        ))
    
    return saga


async def create_short_entry_saga(
    fill_data: Dict[str, Any],
    correlation_id: str,
    position_actor: PositionManagerActor,
    order_actor: OrderManagerActor,
    grid_calc: Any,
    event_store: EventStore
) -> Saga:
    """
    Create saga for processing SELL fill in SHORT mode (entry).
    
    In SHORT mode:
    - SELL opens a position
    - TP is BELOW entry (BUY back at lower price)
    - Next SELL is ABOVE current entry
    
    Steps:
    1. Add position to state
    1.5. Clear pending sell order
    2. Place TP order (BUY at entry - step)
    3. Place next SELL order (if fill complete)
    
    Args:
        fill_data: Fill information
        correlation_id: Correlation ID
        position_actor: Position manager actor
        order_actor: Order manager actor
        grid_calc: Grid calculator
        event_store: Event store
        
    Returns:
        Configured saga
    """
    saga = Saga(
        saga_id=f"short-entry-{fill_data['order_id']}-{int(time.time()*1000)}",
        correlation_id=correlation_id,
        event_store=event_store,
        timeout=30.0
    )
    
    # Generate position ID
    position_id = str(uuid4())
    
    # Store results for compensation
    position_result: Optional[Dict] = None
    tp_result: Optional[Dict] = None
    grid_result: Optional[Dict] = None
    
    # STEP 1: Add Position
    async def add_position_action() -> Dict[str, Any]:
        nonlocal position_result
        
        # SHORT mode: TP is BELOW entry
        tp_price = grid_calc.compute_tp_price_short(fill_data["fill_price"])
        
        position = {
            "position_id": position_id,
            "entry_order_id": position_id,  # For reconciliation compatibility
            "entry_price": fill_data["fill_price"],
            "tp_price": tp_price,
            "size": fill_data["fill_size"],
            "correlation_id": correlation_id
        }
        
        log.info(f"[SHORT-SAGA] Adding position: {position_id} @ {fill_data['fill_price']} (TP @ {tp_price})")
        
        # Send message to actor
        reply_queue = asyncio.Queue()
        await position_actor.mailbox.put(
            Message("ADD_POSITION", position, reply_queue, correlation_id)
        )
        
        # Wait for reply
        result = await asyncio.wait_for(reply_queue.get(), timeout=5.0)
        
        if result["status"] != "ok":
            raise Exception(f"Failed to add position: {result.get('error')}")
        
        position_result = position
        return position
    
    async def add_position_compensation(position: Dict[str, Any]) -> None:
        log.info(f"[SHORT-SAGA] Compensating: Removing position {position_id}")
        
        # Remove position
        await position_actor.mailbox.put(
            Message("REMOVE_POSITION", {"position_id": position_id}, None, correlation_id)
        )
    
    saga.add_step(SagaStep(
        name="add_position",
        action=add_position_action,
        compensation=add_position_compensation,
        critical=False
    ))
    
    # STEP 1.5: Clear pending sell (entry order filled)
    async def clear_pending_sell_action() -> Dict[str, Any]:
        log.info(f"[SHORT-SAGA] Clearing pending sell for order {fill_data['order_id']}")
        
        # Clear pending sell since entry order filled
        await position_actor.mailbox.put(
            Message("CLEAR_PENDING_SELL", {"order_id": fill_data["order_id"]}, None, correlation_id)
        )
        
        return {"cleared": True}
    
    async def clear_pending_sell_compensation(result: Dict[str, Any]) -> None:
        # No compensation needed for clearing pending
        pass
    
    saga.add_step(SagaStep(
        name="clear_pending_sell",
        action=clear_pending_sell_action,
        compensation=clear_pending_sell_compensation,
        critical=False
    ))
    
    # STEP 2: Place TP Order (BUY at lower price)
    async def place_tp_action() -> Dict[str, Any]:
        nonlocal tp_result
        
        if not position_result:
            raise Exception("No position result available")
        
        tp_price = position_result["tp_price"]
        
        log.info(f"[SHORT-SAGA] Placing TP (BUY) @ {tp_price} for position {position_id}")
        
        # CRITICAL FIX (Dec 12, 2025): Check Guardian signal before placing TP order
        # This prevents unhedged positions during Guardian STOP periods
        from bot.strategy.modules.event_store import EventType
        import time as time_module
        
        try:
            guardian_events = event_store.get_events_by_type(
                [EventType.GUARDIAN_SIGNAL_GO, EventType.GUARDIAN_SIGNAL_STOP],
                limit=1
            )
            
            if guardian_events:
                latest_guardian = guardian_events[0]
                signal = 'GO' if latest_guardian.event_type == EventType.GUARDIAN_SIGNAL_GO else 'STOP'
                signal_age = time_module.time() - latest_guardian.timestamp
                
                if signal == 'STOP':
                    reason = latest_guardian.data.get('reason', 'No reason provided')
                    log.warning(f"⚠️ [SHORT-SAGA] Guardian signal is STOP - Cannot place TP BUY order")
                    log.warning(f"   Reason: {reason}")
                    log.warning(f"   ⚠️  MISSED TP ORDER: BUY @ ${tp_price:,.0f}")
                    log.warning(f"   💡 TIP: TP order will be scheduled for retry when Guardian signal becomes GO")
                    
                    # Schedule TP retry via position actor
                    try:
                        await position_actor.mailbox.put(
                            Message("SCHEDULE_TP_RETRY", {
                                "position": {
                                    "position_id": position_id,
                                    "entry_price": fill_data["fill_price"],
                                    "tp_price": tp_price,
                                    "size": fill_data["fill_size"]
                                },
                                "retry_count": 0,
                                "max_retries": 5
                            }, None, correlation_id)
                        )
                        log.info(f"⏰ [SHORT-SAGA] TP order scheduled for retry")
                    except Exception as e:
                        log.error(f"❌ [SHORT-SAGA] Failed to schedule TP retry: {e}")
                    
                    return {"status": "skipped", "reason": f"guardian_stop: {reason}", "tp_scheduled_for_retry": True}
                
                if signal_age > 30:
                    log.warning(f"⚠️ [SHORT-SAGA] Guardian signal is stale ({signal_age:.0f}s old) - Proceeding with caution")
            else:
                log.warning(f"⚠️ [SHORT-SAGA] No Guardian signal found - Cannot place TP order safely")
                return {"status": "skipped", "reason": "no_guardian_signal"}
                
        except Exception as guardian_error:
            log.error(f"❌ [SHORT-SAGA] Error checking Guardian signal: {guardian_error}")
            return {"status": "skipped", "reason": f"guardian_check_error: {str(guardian_error)}"}
        
        # Send message to actor
        reply_queue = asyncio.Queue()
        await order_actor.mailbox.put(
            Message("PLACE_TP", {
                "price": tp_price,
                "size": fill_data["fill_size"],  # Use same size as filled order
                "position_id": position_id,
                "side": "buy"  # SHORT mode TP is a BUY
            }, reply_queue, correlation_id)
        )
        
        # Wait for reply
        result = await asyncio.wait_for(reply_queue.get(), timeout=10.0)
        
        if result["status"] != "ok":
            # TP placement failed - schedule for retry queue
            log.warning(f"⚠️ [SHORT-SAGA] TP placement failed: {result.get('error')} - scheduling retry")
            
            # Schedule TP retry via position actor
            try:
                await position_actor.mailbox.put(
                    Message("SCHEDULE_TP_RETRY", {
                        "position": {
                            "position_id": position_id,
                            "entry_price": fill_data["fill_price"],
                            "tp_price": tp_price,
                            "size": fill_data["fill_size"]
                        },
                        "retry_count": 0,
                        "max_retries": 5
                    }, None, correlation_id)
                )
                log.info(f"⏰ [SHORT-SAGA] Position scheduled for TP retry")
            except Exception as e:
                log.error(f"❌ [SHORT-SAGA] Failed to schedule TP retry: {e}")
            
            # Return success with retry flag to allow saga to continue to Step 3
            return {"status": "ok", "tp_scheduled_for_retry": True, "error": result.get('error')}
        
        tp_result = result
        return result
    
    async def place_tp_compensation(tp_order: Dict[str, Any]) -> None:
        if not tp_order or "order_id" not in tp_order:
            log.warning("[SHORT-SAGA] No TP order to compensate")
            return
        
        log.info(f"[SHORT-SAGA] Compensating: Cancelling TP order {tp_order['order_id']}")
        
        # Cancel TP order
        await order_actor.mailbox.put(
            Message("CANCEL_ORDER", {"order_id": tp_order["order_id"]}, None, correlation_id)
        )
    
    saga.add_step(SagaStep(
        name="place_tp",
        action=place_tp_action,
        compensation=place_tp_compensation,
        critical=False
    ))
    
    # STEP 3: Place Next SELL Order (if fill is complete)
    if fill_data.get("is_complete", True):
        async def place_grid_action() -> Dict[str, Any]:
            nonlocal grid_result
            
            # SHORT mode: next SELL is UP from current entry
            next_price = grid_calc.compute_next_level_up(fill_data["fill_price"])
            
            log.info(f"[SHORT-SAGA] Placing next SELL order @ {next_price}")
            
            # ============================================================================
            # SINGLE WRITER PATTERN (Dec 19, 2025): Delegate to OrderActor
            # ============================================================================
            # OrderActor atomically handles: cancel old orders + Guardian check + place new order
            # Mailbox serialization prevents race conditions (no lock needed)
            reply_queue = asyncio.Queue()
            await order_actor.mailbox.put(
                Message("REPLACE_PENDING_SELL_ORDER", {
                    "price": next_price,
                    "size": fill_data["fill_size"],
                    "check_guardian": True
                }, reply_queue, correlation_id)
            )
            
            # Wait for atomic operation result
            result = await asyncio.wait_for(reply_queue.get(), timeout=15.0)
            
            if result["status"] == "skipped":
                reason = result.get("reason", "unknown")
                log.warning(f"⚠️ [SHORT-SAGA] Order placement skipped: {reason}")
                if "guardian_stop" in reason:
                    log.warning(f"   ⚠️  MISSED GRID ORDER: SELL @ ${next_price:,.0f}")
                    log.warning(f"   💡 TIP: Order will auto-retry when Guardian signal becomes GO")
                return result
            
            if result["status"] != "ok":
                log.warning(f"[SHORT-SAGA] Grid order failed (non-critical): {result.get('error')}")
                return {"status": "failed", "error": result.get("error")}
            
            # Update position actor state with new order
            if "order_id" in result:
                await position_actor.mailbox.put(
                    Message("SET_PENDING_SELL", {
                        "order_id": result["order_id"],
                        "price": next_price,
                        "size": fill_data["fill_size"],
                        "timestamp": time.time()
                    }, None, correlation_id)
                )
                log.info(f"✅ [SHORT-SAGA] Order placed atomically: {result['order_id']} @ ${next_price}")
            
            grid_result = result
            return result
        
        async def place_grid_compensation(grid_order: Dict[str, Any]) -> None:
            if not grid_order or grid_order.get("status") != "ok" or "order_id" not in grid_order:
                log.warning("[SHORT-SAGA] No grid order to compensate")
                return
            
            log.info(f"[SHORT-SAGA] Compensating: Cancelling grid order {grid_order['order_id']}")
            
            # Cancel grid order
            await order_actor.mailbox.put(
                Message("CANCEL_ORDER", {"order_id": grid_order["order_id"]}, None, correlation_id)
            )
        
        saga.add_step(SagaStep(
            name="place_grid_order",
            action=place_grid_action,
            compensation=place_grid_compensation,
            critical=False  # Grid order failure is not critical
        ))
    
    return saga


async def create_short_tp_saga(
    fill_data: Dict[str, Any],
    correlation_id: str,
    position_actor: PositionManagerActor,
    order_actor: OrderManagerActor,
    grid_calc: Any,
    event_store: EventStore
) -> Saga:
    """
    Create saga for processing BUY fill in SHORT mode (TP close).
    
    In SHORT mode:
    - BUY closes a position (TP hit)
    - Find position by TP price
    - Place new SELL order to continue grid
    
    Steps:
    1. Find and remove position by TP price
    2. Clear pending buy order
    3. Place new SELL order at grid level
    
    Args:
        fill_data: Fill information
        correlation_id: Correlation ID
        position_actor: Position manager actor
        order_actor: Order manager actor
        grid_calc: Grid calculator
        event_store: Event store
        
    Returns:
        Configured saga
    """
    saga = Saga(
        saga_id=f"short-tp-{fill_data['order_id']}-{int(time.time()*1000)}",
        correlation_id=correlation_id,
        event_store=event_store,
        timeout=30.0
    )
    
    # Store results for compensation
    position_removed: Optional[Dict] = None
    pending_cleared: bool = False
    sell_result: Optional[Dict] = None
    
    # STEP 1: Find and Remove Position
    async def remove_position_action() -> Dict[str, Any]:
        nonlocal position_removed
        
        log.info(f"[SHORT-SAGA] Finding position by TP price: {fill_data['fill_price']}")
        
        # Find position by TP price
        reply_queue = asyncio.Queue()
        await position_actor.mailbox.put(
            Message("GET_POSITION_BY_TP", {"tp_price": fill_data["fill_price"]}, reply_queue, correlation_id)
        )
        
        position = await asyncio.wait_for(reply_queue.get(), timeout=5.0)
        
        if not position:
            raise Exception(f"No position found with TP price: {fill_data['fill_price']}")
        
        log.info(f"[SHORT-SAGA] Removing position: {position['position_id']}")
        
        # Remove position
        reply_queue = asyncio.Queue()
        await position_actor.mailbox.put(
            Message("REMOVE_POSITION", {"position_id": position["position_id"]}, reply_queue, correlation_id)
        )
        
        result = await asyncio.wait_for(reply_queue.get(), timeout=5.0)
        
        if result["status"] != "ok":
            raise Exception(f"Failed to remove position: {result.get('error')}")
        
        position_removed = position
        return position
    
    async def remove_position_compensation(position: Dict[str, Any]) -> None:
        if not position:
            log.warning("[SHORT-SAGA] No position to restore")
            return
        
        log.info(f"[SHORT-SAGA] Compensating: Restoring position {position['position_id']}")
        
        # Re-add position
        await position_actor.mailbox.put(
            Message("ADD_POSITION", position, None, correlation_id)
        )
    
    saga.add_step(SagaStep(
        name="remove_position",
        action=remove_position_action,
        compensation=remove_position_compensation,
        critical=True  # Critical - position must be removed
    ))
    
    # STEP 2: Clear Pending Buy
    async def clear_pending_action() -> Dict[str, Any]:
        nonlocal pending_cleared
        
        log.info(f"[SHORT-SAGA] Clearing pending buy for order {fill_data['order_id']}")
        
        # Clear pending buy
        reply_queue = asyncio.Queue()
        await position_actor.mailbox.put(
            Message("CLEAR_PENDING_BUY", {"order_id": fill_data["order_id"]}, reply_queue, correlation_id)
        )
        
        result = await asyncio.wait_for(reply_queue.get(), timeout=5.0)
        
        pending_cleared = result.get("cleared", False)
        return {"cleared": pending_cleared}
    
    async def clear_pending_compensation(result: Dict[str, Any]) -> None:
        # No compensation needed for clearing pending
        pass
    
    saga.add_step(SagaStep(
        name="clear_pending_buy",
        action=clear_pending_action,
        compensation=clear_pending_compensation,
        critical=False
    ))
    
    # STEP 3: Place New SELL Order
    if fill_data.get("is_complete", True):
        async def place_sell_action() -> Dict[str, Any]:
            nonlocal sell_result
            
            if not position_removed:
                raise Exception("No position data available")
            
            # FIX NOV 14: Calculate next sell level from TP price (market moved DOWN to TP)
            # New SELL should be 1 step ABOVE TP, not 1 step above old entry
            # This prevents placing order 2 steps away from TP
            tp_price = position_removed["tp_price"]
            next_price = grid_calc.compute_next_level_up(tp_price)
            
            log.info(f"[SHORT-SAGA] TP filled @ {fill_data['fill_price']}, placing new SELL @ {next_price} (TP + 1 step)")
            
            # ============================================================================
            # SINGLE WRITER PATTERN (Dec 19, 2025): Delegate to OrderActor
            # ============================================================================
            # OrderActor atomically handles: cancel old orders + Guardian check + place new order
            # Mailbox serialization prevents race conditions (no lock needed)
            reply_queue = asyncio.Queue()
            await order_actor.mailbox.put(
                Message("REPLACE_PENDING_SELL_ORDER", {
                    "price": next_price,
                    "size": fill_data["fill_size"],
                    "check_guardian": True
                }, reply_queue, correlation_id)
            )
            
            # Wait for atomic operation result
            result = await asyncio.wait_for(reply_queue.get(), timeout=15.0)
            
            if result["status"] == "skipped":
                reason = result.get("reason", "unknown")
                log.warning(f"⚠️ [SHORT-SAGA] Order placement skipped: {reason}")
                return result
            
            if result["status"] != "ok":
                log.warning(f"[SHORT-SAGA] Sell order failed (non-critical): {result.get('error')}")
                return {"status": "failed", "error": result.get("error")}
            
            # Update position actor state with new order
            if "order_id" in result:
                await position_actor.mailbox.put(
                    Message("SET_PENDING_SELL", {
                        "order_id": result["order_id"],
                        "price": next_price,
                        "size": fill_data["fill_size"],
                        "timestamp": time.time()
                    }, None, correlation_id)
                )
                log.info(f"✅ [SHORT-SAGA] Order placed atomically: {result['order_id']} @ ${next_price}")
            
            sell_result = result
            return result
        
        async def place_sell_compensation(sell_order: Dict[str, Any]) -> None:
            if not sell_order or sell_order.get("status") != "ok" or "order_id" not in sell_order:
                log.warning("[SHORT-SAGA] No sell order to compensate")
                return
            
            log.info(f"[SHORT-SAGA] Compensating: Cancelling sell order {sell_order['order_id']}")
            
            # Cancel sell order
            await order_actor.mailbox.put(
                Message("CANCEL_ORDER", {"order_id": sell_order["order_id"]}, None, correlation_id)
            )
            
            # Clear pending sell
            await position_actor.mailbox.put(
                Message("CLEAR_PENDING_SELL", {"order_id": sell_order["order_id"]}, None, correlation_id)
            )
        
        saga.add_step(SagaStep(
            name="place_sell_order",
            action=place_sell_action,
            compensation=place_sell_compensation,
            critical=False  # Sell order failure is not critical
        ))
    
    return saga
