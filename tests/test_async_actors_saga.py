"""
Comprehensive tests for async actors and saga pattern.
Tests actor message passing, saga execution, and compensation.
"""

import asyncio
import pytest
import time
from typing import Dict, Any, Optional
from uuid import uuid4

from bot.strategy.actors.base_actor import Actor, Message
from bot.strategy.actors.position_actor import PositionManagerActor
from bot.strategy.actors.order_actor import OrderManagerActor
from bot.strategy.sagas.saga_coordinator import Saga, SagaStep, SagaOrchestrator
from bot.strategy.sagas.fill_processing_saga import (
    create_buy_fill_saga,
    create_sell_fill_saga,
    GridCalculator
)
from bot.strategy.modules.event_store import EventStore
from bot.api.async_delta_client import AsyncDeltaClient


# Mock API Client for testing
class MockAsyncDeltaClient(AsyncDeltaClient):
    """Mock API client for testing."""
    
    def __init__(self, fail_on: Optional[str] = None):
        """
        Initialize mock client.
        
        Args:
            fail_on: Operation to fail on (e.g., "PLACE_TP")
        """
        self.fail_on = fail_on
        self.placed_orders = []
        self.cancelled_orders = []
    
    async def place_order(self, **kwargs) -> Dict[str, Any]:
        """Mock order placement."""
        if self.fail_on and kwargs.get("side") == self.fail_on:
            raise Exception(f"Mock failure on {self.fail_on}")
        
        order_id = str(uuid4())
        self.placed_orders.append({
            "order_id": order_id,
            **kwargs
        })
        
        return {"id": order_id, "status": "pending"}
    
    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Mock order cancellation."""
        if self.fail_on == "cancel":
            raise Exception("Mock failure on cancel")
        
        self.cancelled_orders.append(order_id)
        return {"id": order_id, "status": "cancelled"}
    
    async def get_open_orders(self, symbol: Optional[str] = None) -> list:
        """Mock get open orders."""
        return [o for o in self.placed_orders if o["order_id"] not in self.cancelled_orders]
    
    async def close(self):
        """Mock close."""
        pass


# Mock Order Actor for controlled failures
class MockOrderActor(OrderManagerActor):
    """Mock order actor that can inject failures."""
    
    def __init__(self, event_store: EventStore, fail_on: Optional[str] = None):
        """
        Initialize mock order actor.
        
        Args:
            event_store: Event store
            fail_on: Message type to fail on
        """
        mock_client = MockAsyncDeltaClient(fail_on=fail_on.replace("PLACE_", "").lower() if fail_on else None)
        super().__init__(mock_client, event_store)
        self.fail_on = fail_on
    
    async def _handle_place_tp(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """Override to inject failure."""
        if self.fail_on == "PLACE_TP":
            raise Exception("Mock TP placement failure")
        
        return await super()._handle_place_tp(payload, reply_to, correlation_id)


# Test Actor class
class TestActor(Actor):
    """Test actor for unit tests."""
    
    def __init__(self):
        super().__init__("TestActor")
        self.received_messages = []
    
    async def _handle_test(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """Handle test message."""
        self.received_messages.append(payload)
        
        # Simulate processing
        await asyncio.sleep(0.01)
        
        return {"status": "ok", "echo": payload.get("data")}
    
    async def _handle_slow(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """Handle slow message."""
        await asyncio.sleep(0.2)  # Slow processing
        return {"status": "ok"}
    
    async def _handle_error(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> None:
        """Handle error message."""
        raise Exception("Test error")


@pytest.mark.asyncio
async def test_actor_message_passing():
    """Test basic actor message passing."""
    actor = TestActor()
    
    # Start actor
    await actor.start()
    
    try:
        # Send messages
        for i in range(10):
            await actor.send(Message("TEST", {"data": f"message_{i}"}))
        
        # Wait for processing
        await asyncio.sleep(0.2)
        
        # Verify all messages received
        assert len(actor.received_messages) == 10
        assert actor.received_messages[0]["data"] == "message_0"
        assert actor.received_messages[9]["data"] == "message_9"
        
        # Test ask pattern
        result = await actor.ask("TEST", {"data": "ask_test"})
        assert result["status"] == "ok"
        assert result["echo"] == "ask_test"
    
    finally:
        await actor.stop()


@pytest.mark.asyncio
async def test_actor_message_order():
    """Test that messages are processed in order."""
    actor = TestActor()
    
    await actor.start()
    
    try:
        # Send 100 messages
        for i in range(100):
            await actor.send(Message("TEST", {"data": i}))
        
        # Wait for processing
        await asyncio.sleep(1.5)
        
        # Verify order preserved
        for i in range(100):
            assert actor.received_messages[i]["data"] == i
    
    finally:
        await actor.stop()


@pytest.mark.asyncio
async def test_actor_error_handling():
    """Test actor error handling."""
    actor = TestActor()
    
    await actor.start()
    
    try:
        # Send error message
        await actor.send(Message("ERROR", {}))
        
        # Send normal message after error
        await actor.send(Message("TEST", {"data": "after_error"}))
        
        # Wait for processing
        await asyncio.sleep(0.1)
        
        # Verify normal message processed despite error
        assert len(actor.received_messages) == 1
        assert actor.received_messages[0]["data"] == "after_error"
        
        # Verify error count
        assert actor._error_count == 1
    
    finally:
        await actor.stop()


@pytest.mark.asyncio
async def test_actor_timeout():
    """Test actor ask timeout."""
    actor = TestActor()
    
    await actor.start()
    
    try:
        # Test timeout on slow message
        with pytest.raises(asyncio.TimeoutError):
            await actor.ask("SLOW", {}, timeout=0.1)
    
    finally:
        await actor.stop()


@pytest.mark.asyncio
async def test_position_actor():
    """Test position manager actor."""
    event_store = EventStore(":memory:")
    actor = PositionManagerActor(event_store, max_positions=3)
    
    await actor.start()
    
    try:
        # Add positions
        for i in range(3):
            result = await actor.ask("ADD_POSITION", {
                "position_id": f"pos_{i}",
                "entry_price": 100000 + i * 1000,
                "tp_price": 100500 + i * 1000,
                "size": 1
            })
            assert result["status"] == "ok"
        
        # Try to add beyond capacity
        result = await actor.ask("ADD_POSITION", {
            "position_id": "pos_3",
            "entry_price": 103000,
            "tp_price": 103500,
            "size": 1
        })
        assert result["status"] == "error"
        assert "Max positions" in result["error"]
        
        # Get state
        state = await actor.ask("GET_STATE", {})
        assert len(state["open_tranches"]) == 3
        
        # Remove position
        result = await actor.ask("REMOVE_POSITION", {"position_id": "pos_1"})
        assert result["status"] == "ok"
        
        # Verify removal
        state = await actor.ask("GET_STATE", {})
        assert len(state["open_tranches"]) == 2
        
        # Set pending buy
        result = await actor.ask("SET_PENDING_BUY", {
            "order_id": "buy_123",
            "price": 99000,
            "size": 1
        })
        assert result["status"] == "ok"
        
        # Verify pending buy
        state = await actor.ask("GET_STATE", {})
        assert state["pending_buy"] is not None
        assert state["pending_buy"]["order_id"] == "buy_123"
        
        # Clear pending buy
        result = await actor.ask("CLEAR_PENDING_BUY", {"order_id": "buy_123"})
        assert result["status"] == "ok"
        
        # Verify cleared
        state = await actor.ask("GET_STATE", {})
        assert state["pending_buy"] is None
    
    finally:
        await actor.stop()


@pytest.mark.asyncio
async def test_saga_success_path():
    """Test saga successful execution."""
    event_store = EventStore(":memory:")
    
    # Track execution
    steps_executed = []
    
    # Create saga
    saga = Saga(
        saga_id="test-saga",
        correlation_id="test-123",
        event_store=event_store
    )
    
    # Add steps
    async def step1_action():
        steps_executed.append("step1")
        return {"result": "step1_done"}
    
    async def step1_compensation(result):
        steps_executed.append("compensate_step1")
    
    saga.add_step(SagaStep("step1", step1_action, step1_compensation))
    
    async def step2_action():
        steps_executed.append("step2")
        return {"result": "step2_done"}
    
    async def step2_compensation(result):
        steps_executed.append("compensate_step2")
    
    saga.add_step(SagaStep("step2", step2_action, step2_compensation))
    
    # Execute saga
    success = await saga.execute()
    
    # Verify success
    assert success is True
    assert steps_executed == ["step1", "step2"]
    assert saga.context.status == "completed"


@pytest.mark.asyncio
async def test_saga_failure_compensation():
    """Test saga compensation on failure."""
    event_store = EventStore(":memory:")
    
    # Track execution
    steps_executed = []
    
    # Create saga
    saga = Saga(
        saga_id="test-saga-fail",
        correlation_id="test-456",
        event_store=event_store
    )
    
    # Add steps
    async def step1_action():
        steps_executed.append("step1")
        return {"result": "step1_done"}
    
    async def step1_compensation(result):
        steps_executed.append("compensate_step1")
    
    saga.add_step(SagaStep("step1", step1_action, step1_compensation))
    
    async def step2_action():
        steps_executed.append("step2")
        raise Exception("Step 2 failed!")
    
    async def step2_compensation(result):
        steps_executed.append("compensate_step2")
    
    saga.add_step(SagaStep("step2", step2_action, step2_compensation))
    
    # Execute saga (should fail and compensate)
    success = await saga.execute()
    
    # Verify failure and compensation
    assert success is False
    assert steps_executed == ["step1", "step2", "compensate_step1"]
    assert saga.context.status == "compensated"


@pytest.mark.asyncio
async def test_saga_compensation_on_tp_failure():
    """Test saga rollback when TP placement fails."""
    # Setup
    event_store = EventStore(":memory:")
    position_actor = PositionManagerActor(event_store)
    order_actor = MockOrderActor(event_store, fail_on="PLACE_TP")
    grid_calc = GridCalculator(lower=99000, upper=112000, step=500)
    
    # Start actors
    await position_actor.start()
    await order_actor.start()
    
    try:
        # Create saga
        fill_data = {
            "order_id": "12345",
            "fill_price": 100000,
            "fill_size": 1,
            "is_complete": True
        }
        
        saga = await create_buy_fill_saga(
            fill_data=fill_data,
            correlation_id="test-tp-fail",
            position_actor=position_actor,
            order_actor=order_actor,
            grid_calc=grid_calc,
            event_store=event_store
        )
        
        # Execute saga (should fail at PLACE_TP)
        success = await saga.execute()
        
        # Verify failure
        assert not success, "Saga should fail"
        
        # Verify compensation: Position should be removed
        state = await position_actor.ask("GET_STATE", {})
        assert len(state["open_tranches"]) == 0, "Position should be rolled back"
        
        # Verify events logged
        events = event_store.get_events_by_correlation("test-tp-fail")
        event_types = [e.event_type.value for e in events]
        assert "saga_step_compensated" in event_types
    
    finally:
        await position_actor.stop()
        await order_actor.stop()


@pytest.mark.asyncio
async def test_concurrent_sagas():
    """Test multiple concurrent sagas."""
    event_store = EventStore(":memory:")
    orchestrator = SagaOrchestrator(event_store)
    
    # Create 10 sagas
    sagas = []
    for i in range(10):
        saga = Saga(
            saga_id=f"concurrent-{i}",
            correlation_id=f"concurrent-{i}",
            event_store=event_store
        )
        
        # Add simple step
        async def action(idx=i):
            await asyncio.sleep(0.01)
            return {"index": idx}
        
        async def compensation(result):
            pass
        
        saga.add_step(SagaStep(f"step-{i}", action, compensation))
        sagas.append(saga)
    
    # Start all sagas concurrently
    tasks = []
    for saga in sagas:
        task = await orchestrator.start_saga(saga)
        tasks.append(task)
    
    # Wait for all to complete
    results = await asyncio.gather(*tasks)
    
    # Verify all completed
    assert all(results)
    
    # Check metrics
    metrics = orchestrator.get_metrics()
    assert metrics["total_completed"] == 10
    assert metrics["total_failed"] == 0


@pytest.mark.asyncio
async def test_actor_mailbox_overflow():
    """Test actor behavior with mailbox overflow."""
    actor = TestActor()
    actor.mailbox = asyncio.Queue(maxsize=5)  # Small mailbox
    
    await actor.start()
    
    try:
        # Fill mailbox using put_nowait to avoid blocking
        for i in range(5):
            actor.mailbox.put_nowait(Message("TEST", {"data": i}))
        
        # Try to send when full
        with pytest.raises(asyncio.QueueFull):
            actor.mailbox.put_nowait(Message("TEST", {"data": "overflow"}))
        
        # Process messages
        await asyncio.sleep(0.2)
        
        # Verify 5 messages processed
        assert len(actor.received_messages) >= 5
    
    finally:
        await actor.stop()


@pytest.mark.asyncio
async def test_performance_throughput():
    """Test actor message throughput."""
    actor = TestActor()
    
    await actor.start()
    
    try:
        # Send 1000 messages
        start_time = time.time()
        
        for i in range(1000):
            await actor.send(Message("TEST", {"data": i}))
        
        # Wait for processing
        while len(actor.received_messages) < 1000:
            await asyncio.sleep(0.01)
        
        elapsed = time.time() - start_time
        throughput = 1000 / elapsed
        
        print(f"Throughput: {throughput:.0f} messages/sec")
        
        # Should handle at least 50 messages/sec (accounting for logging overhead)
        assert throughput >= 50
    
    finally:
        await actor.stop()


@pytest.mark.asyncio
async def test_saga_timeout():
    """Test saga timeout handling."""
    event_store = EventStore(":memory:")
    
    saga = Saga(
        saga_id="timeout-saga",
        correlation_id="timeout-test",
        event_store=event_store,
        timeout=0.1  # 100ms timeout
    )
    
    # Add slow step
    async def slow_action():
        await asyncio.sleep(0.5)  # Longer than timeout
        return {"result": "done"}
    
    async def slow_compensation(result):
        pass
    
    saga.add_step(SagaStep("slow_step", slow_action, slow_compensation))
    
    # Execute (should timeout)
    success = await saga.execute()
    
    # Verify timeout
    assert not success
    assert "timeout" in saga.context.error.lower()


@pytest.mark.asyncio
async def test_full_buy_fill_saga():
    """Test complete buy fill saga execution."""
    # Setup
    event_store = EventStore(":memory:")
    position_actor = PositionManagerActor(event_store)
    
    mock_client = MockAsyncDeltaClient()
    order_actor = OrderManagerActor(mock_client, event_store)
    
    grid_calc = GridCalculator(lower=99000, upper=112000, step=500)
    
    # Start actors
    await position_actor.start()
    await order_actor.start()
    
    try:
        # Create buy fill saga
        fill_data = {
            "order_id": "buy_12345",
            "fill_price": 100000,
            "fill_size": 1,
            "is_complete": True
        }
        
        saga = await create_buy_fill_saga(
            fill_data=fill_data,
            correlation_id="test-buy-fill",
            position_actor=position_actor,
            order_actor=order_actor,
            grid_calc=grid_calc,
            event_store=event_store
        )
        
        # Execute saga
        success = await saga.execute()
        
        # Verify success
        assert success
        
        # Verify position added
        state = await position_actor.ask("GET_STATE", {})
        assert len(state["open_tranches"]) == 1
        assert state["open_tranches"][0]["entry_price"] == 100000
        assert state["open_tranches"][0]["tp_price"] == 100500  # entry + tp_offset
        
        # Verify TP order placed
        assert len(mock_client.placed_orders) == 2  # TP + grid order
        tp_order = [o for o in mock_client.placed_orders if o["side"] == "sell"][0]
        assert tp_order["price"] == 100500
        
        # Verify grid order placed
        grid_order = [o for o in mock_client.placed_orders if o["side"] == "buy"][0]
        assert grid_order["price"] == 99500  # next level down
    
    finally:
        await position_actor.stop()
        await order_actor.stop()


@pytest.mark.asyncio
async def test_full_sell_fill_saga():
    """Test complete sell fill (TP hit) saga execution."""
    # Setup
    event_store = EventStore(":memory:")
    position_actor = PositionManagerActor(event_store)
    
    mock_client = MockAsyncDeltaClient()
    order_actor = OrderManagerActor(mock_client, event_store)
    
    grid_calc = GridCalculator(lower=99000, upper=112000, step=500)
    
    # Start actors
    await position_actor.start()
    
    await order_actor.start()
    
    try:
        # First add a position
        await position_actor.ask("ADD_POSITION", {
            "position_id": "pos_test",
            "entry_price": 100000,
            "tp_price": 100500,
            "size": 1
        })
        
        # Create sell fill saga (TP hit)
        fill_data = {
            "order_id": "sell_12345",
            "fill_price": 100500,  # TP price
            "fill_size": 1,
            "is_complete": True
        }
        
        saga = await create_sell_fill_saga(
            fill_data=fill_data,
            correlation_id="test-sell-fill",
            position_actor=position_actor,
            order_actor=order_actor,
            grid_calc=grid_calc,
            event_store=event_store
        )
        
        # Execute saga
        success = await saga.execute()
        
        # Verify success
        assert success
        
        # Verify position removed
        state = await position_actor.ask("GET_STATE", {})
        assert len(state["open_tranches"]) == 0
        
        # Verify new buy order placed
        assert len(mock_client.placed_orders) == 1
        buy_order = mock_client.placed_orders[0]
        assert buy_order["side"] == "buy"
        assert buy_order["price"] == 99500  # next level down from entry
    
    finally:
        await position_actor.stop()
        await order_actor.stop()
