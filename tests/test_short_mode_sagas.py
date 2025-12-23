"""
Tests for SHORT mode saga functionality.

Verifies:
- create_short_entry_saga() processes SELL fills correctly
- create_short_tp_saga() processes BUY fills correctly  
- TP prices are calculated correctly for SHORT mode
- Grid progression works in SHORT mode
"""

import pytest
import asyncio
from typing import Dict, Any

from bot.strategy.sagas.fill_processing_saga import (
    create_short_entry_saga,
    create_short_tp_saga,
)
from bot.strategy.sagas.saga_coordinator import SagaOrchestrator
from bot.strategy.actors.position_actor import PositionManagerActor
from bot.strategy.actors.order_actor import OrderManagerActor
from bot.strategy.modules.event_store import EventStore
from bot.strategy.modules.grid_calculator import GridCalculator


class MockAsyncDeltaClient:
    """Mock Delta API client for testing."""
    
    def __init__(self):
        self.orders_placed = []
        self.orders_cancelled = []
        
    async def place_order(self, **kwargs):
        order_id = f"ORD-{len(self.orders_placed) + 1}"
        self.orders_placed.append({
            "order_id": order_id,
            **kwargs
        })
        return {
            "success": True,
            "result": {
                "id": order_id,
                **kwargs
            }
        }
    
    async def cancel_order(self, order_id: str):
        self.orders_cancelled.append(order_id)
        return {"success": True}


@pytest.mark.asyncio
async def test_short_entry_saga_sell_fill():
    """Test SHORT mode entry saga when SELL fills."""
    # Setup
    event_store = EventStore(":memory:")
    position_actor = PositionManagerActor(event_store)
    
    mock_client = MockAsyncDeltaClient()
    order_actor = OrderManagerActor(mock_client, event_store)
    
    grid_calc = GridCalculator(lower=95000, upper=110000, step=500, ref=100000)
    
    await position_actor.start()
    await order_actor.start()
    
    # SELL fill data (entry in SHORT mode)
    fill_data = {
        "order_id": "TEST-SELL-1",
        "fill_price": 100500.0,
        "fill_size": 1,
        "is_complete": True
    }
    
    # Create and execute saga
    saga = await create_short_entry_saga(
        fill_data=fill_data,
        correlation_id="test-001",
        position_actor=position_actor,
        order_actor=order_actor,
        grid_calc=grid_calc,
        event_store=event_store
    )
    
    orchestrator = SagaOrchestrator(event_store)
    
    task = await orchestrator.start_saga(saga)
    result = await task
    
    # Verify position was added
    state = await position_actor.ask("GET_STATE", {})
    assert len(state["open_tranches"]) == 1
    
    position = state["open_tranches"][0]
    assert position["entry_price"] == 100500.0
    
    # Verify TP is BELOW entry (SHORT mode)
    assert position["tp_price"] == 100000.0  # 100500 - 500
    assert position["tp_price"] < position["entry_price"]
    
    # Verify next SELL order was placed ABOVE entry
    assert len(mock_client.orders_placed) >= 2  # TP + next grid order
    
    # Find the grid order (not the TP)
    grid_orders = [o for o in mock_client.orders_placed if o.get("side") == "sell" and o.get("price") != 100000.0]
    assert len(grid_orders) == 1
    assert grid_orders[0]["price"] == 101000.0  # 100500 + 500
    
    await position_actor.stop()
    await order_actor.stop()


@pytest.mark.asyncio
async def test_short_tp_saga_buy_fill():
    """Test SHORT mode TP saga when BUY fills (closes position)."""
    # Setup
    event_store = EventStore(":memory:")
    position_actor = PositionManagerActor(event_store)
    
    mock_client = MockAsyncDeltaClient()
    order_actor = OrderManagerActor(mock_client, event_store)
    
    grid_calc = GridCalculator(lower=95000, upper=110000, step=500, ref=100000)
    
    await position_actor.start()
    await order_actor.start()
    
    # Add a SHORT position manually
    await position_actor.ask("ADD_POSITION", {
        "position_id": "POS-001",
        "entry_price": 100500.0,
        "tp_price": 100000.0,
        "size": 1,
        "correlation_id": "setup"
    })
    
    # BUY fill data (TP hit in SHORT mode)
    fill_data = {
        "order_id": "TEST-BUY-1",
        "fill_price": 100000.0,
        "fill_size": 1,
        "is_complete": True
    }
    
    # Create and execute saga
    saga = await create_short_tp_saga(
        fill_data=fill_data,
        correlation_id="test-002",
        position_actor=position_actor,
        order_actor=order_actor,
        grid_calc=grid_calc,
        event_store=event_store
    )
    
    orchestrator = SagaOrchestrator(event_store)
    
    
    task = await orchestrator.start_saga(saga)
    result = await task
    
    # Verify position was removed
    state = await position_actor.ask("GET_STATE", {})
    assert len(state["open_tranches"]) == 0
    
    # Verify new SELL order was placed
    sell_orders = [o for o in mock_client.orders_placed if o.get("side") == "sell"]
    assert len(sell_orders) >= 1
    
    # Next SELL should be UP from closed position entry
    assert sell_orders[-1]["price"] == 101000.0  # 100500 + 500
    
    await position_actor.stop()
    await order_actor.stop()


@pytest.mark.asyncio
async def test_short_mode_tp_price_calculation():
    """Test that SHORT mode calculates TP correctly (BELOW entry)."""
    grid_calc = GridCalculator(lower=95000, upper=110000, step=500, ref=100000)
    
    # SHORT mode: TP should be BELOW entry
    entry_price = 100500.0
    tp_price = grid_calc.compute_tp_price_short(entry_price)
    
    assert tp_price == 100000.0
    assert tp_price < entry_price
    assert entry_price - tp_price == 500.0


@pytest.mark.asyncio
async def test_short_mode_next_level_up():
    """Test that SHORT mode places next SELL ABOVE current entry."""
    grid_calc = GridCalculator(lower=95000, upper=110000, step=500, ref=100000)
    
    # SHORT mode: next SELL should be UP from entry
    entry_price = 100500.0
    next_sell = grid_calc.compute_next_level_up(entry_price)
    
    assert next_sell == 101000.0
    assert next_sell > entry_price
    assert next_sell - entry_price == 500.0


@pytest.mark.asyncio
async def test_short_entry_saga_clears_pending_sell():
    """Test that SHORT entry saga clears pending_sell."""
    # Setup
    event_store = EventStore(":memory:")
    position_actor = PositionManagerActor(event_store)
    
    mock_client = MockAsyncDeltaClient()
    order_actor = OrderManagerActor(mock_client, event_store)
    
    grid_calc = GridCalculator(lower=95000, upper=110000, step=500, ref=100000)
    
    await position_actor.start()
    await order_actor.start()
    
    # Set a pending sell
    await position_actor.ask("SET_PENDING_SELL", {
        "order_id": "TEST-SELL-1",
        "price": 100500.0,
        "size": 1
    })
    
    # Verify it's set
    state = await position_actor.ask("GET_STATE", {})
    assert state["pending_sell"] is not None
    
    # SELL fill
    fill_data = {
        "order_id": "TEST-SELL-1",
        "fill_price": 100500.0,
        "fill_size": 1,
        "is_complete": True
    }
    
    # Execute saga
    saga = await create_short_entry_saga(
        fill_data=fill_data,
        correlation_id="test-003",
        position_actor=position_actor,
        order_actor=order_actor,
        grid_calc=grid_calc,
        event_store=event_store
    )
    
    orchestrator = SagaOrchestrator(event_store)
    
    
    task = await orchestrator.start_saga(saga)
    await task
    
    # Verify pending_sell was cleared
    state = await position_actor.ask("GET_STATE", {})
    assert state["pending_sell"] is None
    
    await position_actor.stop()
    await order_actor.stop()


@pytest.mark.asyncio
async def test_short_tp_saga_clears_pending_buy():
    """Test that SHORT TP saga clears pending_buy."""
    # Setup
    event_store = EventStore(":memory:")
    position_actor = PositionManagerActor(event_store)
    
    mock_client = MockAsyncDeltaClient()
    order_actor = OrderManagerActor(mock_client, event_store)
    
    grid_calc = GridCalculator(lower=95000, upper=110000, step=500, ref=100000)
    
    await position_actor.start()
    await order_actor.start()
    
    # Add a position
    await position_actor.ask("ADD_POSITION", {
        "position_id": "POS-001",
        "entry_price": 100500.0,
        "tp_price": 100000.0,
        "size": 1,
        "correlation_id": "setup"
    })
    
    # Set a pending buy (the TP order)
    await position_actor.ask("SET_PENDING_BUY", {
        "order_id": "TEST-BUY-1",
        "price": 100000.0,
        "size": 1
    })
    
    # BUY fill (TP hit)
    fill_data = {
        "order_id": "TEST-BUY-1",
        "fill_price": 100000.0,
        "fill_size": 1,
        "is_complete": True
    }
    
    # Execute saga
    saga = await create_short_tp_saga(
        fill_data=fill_data,
        correlation_id="test-004",
        position_actor=position_actor,
        order_actor=order_actor,
        grid_calc=grid_calc,
        event_store=event_store
    )
    
    orchestrator = SagaOrchestrator(event_store)
    
    
    task = await orchestrator.start_saga(saga)
    await task
    
    # Verify pending_buy was cleared
    state = await position_actor.ask("GET_STATE", {})
    assert state["pending_buy"] is None
    
    await position_actor.stop()
    await order_actor.stop()


@pytest.mark.asyncio
async def test_short_mode_partial_fill_skips_next_order():
    """Test that partial fills don't place next grid order in SHORT mode."""
    # Setup
    event_store = EventStore(":memory:")
    position_actor = PositionManagerActor(event_store)
    
    mock_client = MockAsyncDeltaClient()
    order_actor = OrderManagerActor(mock_client, event_store)
    
    grid_calc = GridCalculator(lower=95000, upper=110000, step=500, ref=100000)
    
    await position_actor.start()
    await order_actor.start()
    
    # Partial SELL fill
    fill_data = {
        "order_id": "TEST-SELL-1",
        "fill_price": 100500.0,
        "fill_size": 0.5,
        "is_complete": False  # Partial fill
    }
    
    # Execute saga
    saga = await create_short_entry_saga(
        fill_data=fill_data,
        correlation_id="test-005",
        position_actor=position_actor,
        order_actor=order_actor,
        grid_calc=grid_calc,
        event_store=event_store
    )
    
    orchestrator = SagaOrchestrator(event_store)
    
    
    task = await orchestrator.start_saga(saga)
    await task
    
    # Position should be added
    state = await position_actor.ask("GET_STATE", {})
    assert len(state["open_tranches"]) == 1
    
    # TP order should be placed, but NO next grid order (SELL) due to partial fill
    # Note: OrderManager places all TPs as SELL regardless of mode (uses reduce_only flag)
    all_orders = mock_client.orders_placed
    
    # Should have 1 TP order but no grid order (step 3 skipped)
    assert len(all_orders) == 1  # Only TP order
    assert all_orders[0].get("reduce_only") == True  # TP order
    
    await position_actor.stop()
    await order_actor.stop()


@pytest.mark.asyncio
async def test_short_mode_duplicate_order_prevention():
    """Test that duplicate SELL orders are prevented in SHORT mode."""
    # Setup
    event_store = EventStore(":memory:")
    position_actor = PositionManagerActor(event_store)
    
    mock_client = MockAsyncDeltaClient()
    order_actor = OrderManagerActor(mock_client, event_store)
    
    grid_calc = GridCalculator(lower=95000, upper=110000, step=500, ref=100000)
    
    await position_actor.start()
    await order_actor.start()
    
    # Set pending SELL at the level we're about to calculate
    await position_actor.ask("SET_PENDING_SELL", {
        "order_id": "EXISTING-SELL",
        "price": 101000.0,
        "size": 1
    })
    
    # Add a position that will trigger placing order at 101000
    await position_actor.ask("ADD_POSITION", {
        "position_id": "POS-001",
        "entry_price": 100500.0,
        "tp_price": 100000.0,
        "size": 1,
        "correlation_id": "setup"
    })
    
    # BUY fill at TP
    fill_data = {
        "order_id": "TEST-BUY-1",
        "fill_price": 100000.0,
        "fill_size": 1,
        "is_complete": True
    }
    
    # Execute saga
    saga = await create_short_tp_saga(
        fill_data=fill_data,
        correlation_id="test-006",
        position_actor=position_actor,
        order_actor=order_actor,
        grid_calc=grid_calc,
        event_store=event_store
    )
    
    orchestrator = SagaOrchestrator(event_store)
    
    
    task = await orchestrator.start_saga(saga)
    await task
    
    # Should NOT place duplicate SELL order
    sell_orders = [o for o in mock_client.orders_placed if o.get("side") == "sell"]
    # No new SELL should be placed since one already pending at that level
    assert len(sell_orders) == 0
    
    await position_actor.stop()
    await order_actor.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
