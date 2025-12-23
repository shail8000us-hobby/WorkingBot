"""
Position Closing Saga for handling position closure.
Implements safe position closing with compensation.
"""

import asyncio
import time
from typing import Dict, Any, Optional, List
from uuid import uuid4

from loguru import logger as log

from bot.strategy.actors.base_actor import Message
from bot.strategy.actors.position_actor import PositionManagerActor
from bot.strategy.actors.order_actor import OrderManagerActor
from bot.strategy.sagas.saga_coordinator import Saga, SagaStep
from bot.strategy.modules.event_store import EventStore


async def create_position_closing_saga(
    position_id: str,
    reason: str,
    correlation_id: str,
    position_actor: PositionManagerActor,
    order_actor: OrderManagerActor,
    event_store: EventStore
) -> Saga:
    """
    Create saga for closing a position safely.
    
    Steps:
    1. Cancel TP order associated with position
    2. Remove position from state
    3. Update metrics
    
    Args:
        position_id: Position ID to close
        reason: Reason for closing (manual, stop_loss, error, etc.)
        correlation_id: Correlation ID
        position_actor: Position manager actor
        order_actor: Order manager actor
        event_store: Event store
        
    Returns:
        Configured saga
    """
    saga = Saga(
        saga_id=f"close-position-{position_id}-{int(time.time()*1000)}",
        correlation_id=correlation_id,
        event_store=event_store,
        timeout=30.0
    )
    
    # Store results for compensation
    position_data: Optional[Dict] = None
    tp_cancelled: bool = False
    
    # STEP 1: Get Position Data
    async def get_position_action() -> Dict[str, Any]:
        nonlocal position_data
        
        log.info(f"[SAGA] Getting position data for {position_id}")
        
        # Get all positions and find target
        reply_queue = asyncio.Queue()
        await position_actor.mailbox.put(
            Message("GET_OPEN_POSITIONS", {}, reply_queue, correlation_id)
        )
        
        positions = await asyncio.wait_for(reply_queue.get(), timeout=5.0)
        
        # Find position
        for pos in positions:
            if pos["position_id"] == position_id:
                position_data = pos
                break
        
        if not position_data:
            raise Exception(f"Position not found: {position_id}")
        
        log.info(f"[SAGA] Found position: entry={position_data['entry_price']}, tp={position_data['tp_price']}")
        return position_data
    
    async def get_position_compensation(result: Dict[str, Any]) -> None:
        # No compensation needed for read operation
        pass
    
    saga.add_step(SagaStep(
        name="get_position",
        action=get_position_action,
        compensation=get_position_compensation,
        critical=False
    ))
    
    # STEP 2: Cancel TP Order
    async def cancel_tp_action() -> Dict[str, Any]:
        nonlocal tp_cancelled
        
        if not position_data:
            raise Exception("No position data available")
        
        log.info(f"[SAGA] Finding TP orders at price {position_data['tp_price']}")
        
        # Get open orders
        reply_queue = asyncio.Queue()
        await order_actor.mailbox.put(
            Message("GET_OPEN_ORDERS", {}, reply_queue, correlation_id)
        )
        
        result = await asyncio.wait_for(reply_queue.get(), timeout=10.0)
        
        if result["status"] != "ok":
            log.warning(f"[SAGA] Failed to get open orders: {result.get('error')}")
            return {"cancelled": False}
        
        orders = result.get("orders", [])
        
        # Find TP order at position's TP price
        tp_order = None
        for order in orders:
            if (order.get("side") == "sell" and 
                abs(float(order.get("limit_price", 0)) - position_data["tp_price"]) < 0.01):
                tp_order = order
                break
        
        if tp_order:
            order_id = tp_order.get("id", tp_order.get("order_id"))
            log.info(f"[SAGA] Cancelling TP order: {order_id}")
            
            # Cancel TP order
            await order_actor.mailbox.put(
                Message("CANCEL_ORDER", {"order_id": order_id}, None, correlation_id)
            )
            
            tp_cancelled = True
            return {"cancelled": True, "order_id": order_id}
        else:
            log.warning(f"[SAGA] No TP order found at price {position_data['tp_price']}")
            return {"cancelled": False}
    
    async def cancel_tp_compensation(result: Dict[str, Any]) -> None:
        if not result.get("cancelled") or not position_data:
            return
        
        log.info(f"[SAGA] Compensating: Re-placing TP order at {position_data['tp_price']}")
        
        # Re-place TP order
        await order_actor.mailbox.put(
            Message("PLACE_TP", {
                "price": position_data["tp_price"],
                "size": position_data["size"],
                "position_id": position_id
            }, None, correlation_id)
        )
    
    saga.add_step(SagaStep(
        name="cancel_tp",
        action=cancel_tp_action,
        compensation=cancel_tp_compensation,
        critical=False  # TP might already be filled
    ))
    
    # STEP 3: Remove Position
    async def remove_position_action() -> Dict[str, Any]:
        log.info(f"[SAGA] Removing position {position_id} (reason: {reason})")
        
        # Remove position
        reply_queue = asyncio.Queue()
        await position_actor.mailbox.put(
            Message("REMOVE_POSITION", {"position_id": position_id}, reply_queue, correlation_id)
        )
        
        result = await asyncio.wait_for(reply_queue.get(), timeout=5.0)
        
        if result["status"] != "ok":
            raise Exception(f"Failed to remove position: {result.get('error')}")
        
        return {"removed": True, "position": result.get("position")}
    
    async def remove_position_compensation(result: Dict[str, Any]) -> None:
        if not result.get("removed") or not position_data:
            return
        
        log.info(f"[SAGA] Compensating: Restoring position {position_id}")
        
        # Re-add position
        await position_actor.mailbox.put(
            Message("ADD_POSITION", position_data, None, correlation_id)
        )
    
    saga.add_step(SagaStep(
        name="remove_position",
        action=remove_position_action,
        compensation=remove_position_compensation,
        critical=True  # Position must be removed
    ))
    
    return saga


async def create_emergency_close_all_saga(
    correlation_id: str,
    position_actor: PositionManagerActor,
    order_actor: OrderManagerActor,
    event_store: EventStore
) -> Saga:
    """
    Create saga for emergency closure of all positions.
    
    Steps:
    1. Cancel all open orders
    2. Remove all positions
    3. Clear all pending orders
    
    Args:
        correlation_id: Correlation ID
        position_actor: Position manager actor
        order_actor: Order manager actor
        event_store: Event store
        
    Returns:
        Configured saga
    """
    saga = Saga(
        saga_id=f"emergency-close-all-{int(time.time()*1000)}",
        correlation_id=correlation_id,
        event_store=event_store,
        timeout=60.0  # Longer timeout for multiple operations
    )
    
    # Store results for compensation
    cancelled_orders: List[str] = []
    removed_positions: List[Dict] = []
    
    # STEP 1: Cancel All Orders
    async def cancel_all_orders_action() -> Dict[str, Any]:
        nonlocal cancelled_orders
        
        log.warning("[SAGA] EMERGENCY: Cancelling all open orders")
        
        # Get open orders
        reply_queue = asyncio.Queue()
        await order_actor.mailbox.put(
            Message("GET_OPEN_ORDERS", {}, reply_queue, correlation_id)
        )
        
        result = await asyncio.wait_for(reply_queue.get(), timeout=10.0)
        
        if result["status"] != "ok":
            log.error(f"[SAGA] Failed to get open orders: {result.get('error')}")
            return {"cancelled_count": 0}
        
        orders = result.get("orders", [])
        
        # Cancel each order
        for order in orders:
            order_id = order.get("id", order.get("order_id"))
            
            try:
                log.info(f"[SAGA] Cancelling order: {order_id}")
                await order_actor.mailbox.put(
                    Message("CANCEL_ORDER", {"order_id": order_id}, None, correlation_id)
                )
                cancelled_orders.append(order_id)
            except Exception as e:
                log.error(f"[SAGA] Failed to cancel order {order_id}: {e}")
        
        log.info(f"[SAGA] Cancelled {len(cancelled_orders)} orders")
        return {"cancelled_count": len(cancelled_orders), "order_ids": cancelled_orders}
    
    async def cancel_all_orders_compensation(result: Dict[str, Any]) -> None:
        # Cannot reliably restore cancelled orders
        log.warning("[SAGA] Cannot compensate cancelled orders - manual intervention may be needed")
    
    saga.add_step(SagaStep(
        name="cancel_all_orders",
        action=cancel_all_orders_action,
        compensation=cancel_all_orders_compensation,
        critical=False  # Continue even if some cancellations fail
    ))
    
    # STEP 2: Remove All Positions
    async def remove_all_positions_action() -> Dict[str, Any]:
        nonlocal removed_positions
        
        log.warning("[SAGA] EMERGENCY: Removing all positions")
        
        # Get all positions
        reply_queue = asyncio.Queue()
        await position_actor.mailbox.put(
            Message("GET_OPEN_POSITIONS", {}, reply_queue, correlation_id)
        )
        
        positions = await asyncio.wait_for(reply_queue.get(), timeout=5.0)
        
        # Remove each position
        for position in positions:
            try:
                log.info(f"[SAGA] Removing position: {position['position_id']}")
                
                reply_queue = asyncio.Queue()
                await position_actor.mailbox.put(
                    Message("REMOVE_POSITION", {"position_id": position["position_id"]}, reply_queue, correlation_id)
                )
                
                result = await asyncio.wait_for(reply_queue.get(), timeout=5.0)
                
                if result["status"] == "ok":
                    removed_positions.append(position)
            except Exception as e:
                log.error(f"[SAGA] Failed to remove position {position['position_id']}: {e}")
        
        log.info(f"[SAGA] Removed {len(removed_positions)} positions")
        return {"removed_count": len(removed_positions), "positions": removed_positions}
    
    async def remove_all_positions_compensation(result: Dict[str, Any]) -> None:
        if not removed_positions:
            return
        
        log.info(f"[SAGA] Compensating: Restoring {len(removed_positions)} positions")
        
        for position in removed_positions:
            try:
                await position_actor.mailbox.put(
                    Message("ADD_POSITION", position, None, correlation_id)
                )
            except Exception as e:
                log.error(f"[SAGA] Failed to restore position {position['position_id']}: {e}")
    
    saga.add_step(SagaStep(
        name="remove_all_positions",
        action=remove_all_positions_action,
        compensation=remove_all_positions_compensation,
        critical=True  # All positions must be removed
    ))
    
    # STEP 3: Clear Pending Orders
    async def clear_pending_orders_action() -> Dict[str, Any]:
        log.info("[SAGA] Clearing pending buy/sell orders")
        
        # Clear pending buy
        await position_actor.mailbox.put(
            Message("CLEAR_PENDING_BUY", {}, None, correlation_id)
        )
        
        # Clear pending sell
        await position_actor.mailbox.put(
            Message("CLEAR_PENDING_SELL", {}, None, correlation_id)
        )
        
        return {"cleared": True}
    
    async def clear_pending_orders_compensation(result: Dict[str, Any]) -> None:
        # Cannot restore cleared pending orders
        pass
    
    saga.add_step(SagaStep(
        name="clear_pending_orders",
        action=clear_pending_orders_action,
        compensation=clear_pending_orders_compensation,
        critical=False
    ))
    
    return saga
