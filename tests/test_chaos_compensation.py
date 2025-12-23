"""
Chaos testing for saga compensation.
Tests failure injection and recovery scenarios.
"""

import asyncio
import pytest
import random
import time
from typing import Dict, Any, Optional, List
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


class ChaosActor(Actor):
    """Actor that randomly fails for chaos testing."""
    
    def __init__(self, name: str, failure_rate: float = 0.3):
        """
        Initialize chaos actor.
        
        Args:
            name: Actor name
            failure_rate: Probability of failure (0-1)
        """
        super().__init__(name)
        self.failure_rate = failure_rate
        self.operations = []
        self.failed_operations = []
    
    async def _handle_operation(
        self,
        payload: Dict[str, Any],
        reply_to: Optional[asyncio.Queue],
        correlation_id: str
    ) -> Dict[str, Any]:
        """Handle operation with random failure."""
        operation_id = payload.get("operation_id", str(uuid4()))
        
        # Random failure
        if random.random() < self.failure_rate:
            self.failed_operations.append(operation_id)
            raise Exception(f"Chaos failure for operation {operation_id}")
        
        # Success
        self.operations.append(operation_id)
        await asyncio.sleep(random.uniform(0.01, 0.05))  # Random delay
        
        return {"status": "ok", "operation_id": operation_id}


class ChaosSaga:
    """Saga with chaos injection."""
    
    def __init__(
        self,
        saga_id: str,
        event_store: EventStore,
        num_steps: int = 5,
        failure_probability: float = 0.2
    ):
        """
        Initialize chaos saga.
        
        Args:
            saga_id: Saga ID
            event_store: Event store
            num_steps: Number of steps
            failure_probability: Probability of step failure
        """
        self.saga = Saga(
            saga_id=saga_id,
            correlation_id=f"chaos-{saga_id}",
            event_store=event_store
        )
        
        self.executed_steps = []
        self.compensated_steps = []
        self.failure_probability = failure_probability
        
        # Add chaos steps
        for i in range(num_steps):
            self._add_chaos_step(i)
    
    def _add_chaos_step(self, step_index: int):
        """Add a chaos step to saga."""
        step_name = f"step_{step_index}"
        
        async def action():
            # Random failure
            if random.random() < self.failure_probability:
                raise Exception(f"Chaos failure at {step_name}")
            
            # Success
            self.executed_steps.append(step_name)
            await asyncio.sleep(random.uniform(0.01, 0.05))
            return {"step": step_name, "result": f"data_{step_index}"}
        
        async def compensation(result):
            self.compensated_steps.append(step_name)
            await asyncio.sleep(random.uniform(0.01, 0.03))
            
            # Random compensation failure
            if random.random() < self.failure_probability * 0.5:  # Lower rate for compensation
                raise Exception(f"Compensation failure for {step_name}")
        
        self.saga.add_step(SagaStep(step_name, action, compensation))
    
    async def execute(self) -> bool:
        """Execute chaos saga."""
        return await self.saga.execute()


@pytest.mark.asyncio
async def test_chaos_random_failures():
    """Test saga with random failures."""
    event_store = EventStore(":memory:")
    
    success_count = 0
    failure_count = 0
    compensation_count = 0
    
    # Run 100 chaos sagas
    for i in range(100):
        chaos_saga = ChaosSaga(
            saga_id=f"chaos-{i}",
            event_store=event_store,
            num_steps=5,
            failure_probability=0.3  # 30% failure rate
        )
        
        success = await chaos_saga.execute()
        
        if success:
            success_count += 1
            # Verify all steps executed
            assert len(chaos_saga.executed_steps) == 5
            assert len(chaos_saga.compensated_steps) == 0
        else:
            failure_count += 1
            # Verify compensation occurred
            if chaos_saga.compensated_steps:
                compensation_count += 1
                # Compensated steps should be subset of executed steps in reverse order
                # If executed steps are [step_0, step_1, step_2] and step_3 failed,
                # compensation should be [step_2, step_1, step_0]
                assert len(chaos_saga.compensated_steps) <= len(chaos_saga.executed_steps)
                # Verify each compensated step was actually executed
                for step in chaos_saga.compensated_steps:
                    assert step in chaos_saga.executed_steps
    
    print(f"\nChaos Test Results:")
    print(f"Success: {success_count}/100")
    print(f"Failures: {failure_count}/100")
    print(f"Compensated: {compensation_count}/{failure_count}")
    
    # Should have some failures and compensations
    assert failure_count > 10  # With 30% failure rate, expect failures
    assert compensation_count > 0  # Some should compensate successfully


@pytest.mark.asyncio
async def test_chaos_actor_failures():
    """Test actors with random failures."""
    event_store = EventStore(":memory:")
    
    # Create chaos actors
    actors = []
    for i in range(5):
        actor = ChaosActor(f"chaos-actor-{i}", failure_rate=0.2)
        await actor.start()
        actors.append(actor)
    
    try:
        # Send 20 operations to each actor
        tasks = []
        for actor in actors:
            for j in range(20):
                msg = Message("OPERATION", {"operation_id": f"{actor.name}-op-{j}"})
                tasks.append(actor.send(msg))
        
        # Wait for all sends
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Wait for processing
        await asyncio.sleep(2.0)
        
        # Check results
        for actor in actors:
            total_ops = len(actor.operations) + len(actor.failed_operations)
            print(f"{actor.name}: {len(actor.operations)} success, {len(actor.failed_operations)} failed")
            
            # Should have processed some operations
            assert total_ops > 0
            
            # With 20% failure rate, expect some failures
            if total_ops >= 20:
                assert len(actor.failed_operations) > 0
    
    finally:
        for actor in actors:
            await actor.stop()


@pytest.mark.asyncio
async def test_chaos_concurrent_sagas():
    """Test concurrent sagas with chaos."""
    event_store = EventStore(":memory:")
    orchestrator = SagaOrchestrator(event_store, max_concurrent_sagas=20)
    
    # Create 50 chaos sagas to run concurrently
    sagas = []
    for i in range(50):
        chaos_saga = ChaosSaga(
            saga_id=f"concurrent-chaos-{i}",
            event_store=event_store,
            num_steps=3,
            failure_probability=0.25
        )
        sagas.append(chaos_saga)
    
    # Start all sagas
    tasks = []
    start_time = time.time()
    
    for chaos_saga in sagas:
        try:
            task = await orchestrator.start_saga(chaos_saga.saga)
            tasks.append(task)
        except Exception as e:
            # May hit concurrent limit
            print(f"Failed to start saga: {e}")
    
    # Wait for completion
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.time() - start_time
    
    # Count results
    success_count = sum(1 for r in results if r is True)
    failure_count = sum(1 for r in results if r is False)
    error_count = sum(1 for r in results if isinstance(r, Exception))
    
    print(f"\nConcurrent Chaos Results:")
    print(f"Time: {elapsed:.2f}s")
    print(f"Success: {success_count}")
    print(f"Failed/Compensated: {failure_count}")
    print(f"Errors: {error_count}")
    
    # Get metrics
    metrics = orchestrator.get_metrics()
    print(f"Orchestrator - Completed: {metrics['total_completed']}, Failed: {metrics['total_failed']}, Compensated: {metrics['total_compensated']}")
    
    # Verify reasonable distribution
    assert success_count > 0
    assert failure_count > 0
    assert elapsed < 10  # Should complete within 10 seconds


@pytest.mark.asyncio
async def test_chaos_network_failures():
    """Test network failure scenarios."""
    
    class NetworkChaosClient:
        """Client that simulates network issues."""
        
        def __init__(self):
            self.request_count = 0
            self.failure_pattern = [False, False, True, False, True]  # Pattern of failures
        
        async def place_order(self, **kwargs):
            self.request_count += 1
            
            # Simulate network failure
            if self.failure_pattern[self.request_count % len(self.failure_pattern)]:
                await asyncio.sleep(0.1)  # Network delay
                raise Exception("Network timeout")
            
            return {"order_id": str(uuid4())}
        
        async def cancel_order(self, order_id: str):
            self.request_count += 1
            
            # Simulate network failure
            if self.failure_pattern[self.request_count % len(self.failure_pattern)]:
                raise Exception("Network error")
            
            return {"status": "cancelled"}
        
        async def get_open_orders(self, symbol: Optional[str] = None):
            return []
        
        async def close(self):
            pass
    
    # Test with network chaos
    event_store = EventStore(":memory:")
    client = NetworkChaosClient()
    order_actor = OrderManagerActor(client, event_store, max_retries=3)
    
    await order_actor.start()
    
    try:
        # Try to place orders
        results = []
        for i in range(10):
            result = await order_actor.ask("PLACE_BUY", {"price": 100000, "size": 1})
            results.append(result)
            await asyncio.sleep(0.1)
        
        # Some should succeed despite network issues
        success_count = sum(1 for r in results if r["status"] == "ok")
        failure_count = sum(1 for r in results if r["status"] == "error")
        
        print(f"Network Chaos: {success_count} success, {failure_count} failures")
        
        # With retries, more should succeed than fail
        assert success_count >= failure_count
    
    finally:
        await order_actor.stop()


@pytest.mark.asyncio
async def test_chaos_memory_pressure():
    """Test behavior under memory pressure."""
    event_store = EventStore(":memory:")
    
    # Create actor with small mailbox
    actor = ChaosActor("memory-test", failure_rate=0.1)
    actor.mailbox = asyncio.Queue(maxsize=10)  # Very small mailbox
    
    await actor.start()
    
    try:
        # Flood with messages
        send_count = 0
        full_count = 0
        
        for i in range(100):
            try:
                msg = Message("OPERATION", {"operation_id": f"op-{i}", "data": "x" * 1000})
                await asyncio.wait_for(actor.send(msg), timeout=0.01)
                send_count += 1
            except (asyncio.QueueFull, asyncio.TimeoutError):
                full_count += 1
            
            # Small delay to allow processing
            if i % 10 == 0:
                await asyncio.sleep(0.1)
        
        print(f"Memory Pressure: {send_count} sent, {full_count} rejected")
        
        # Should have rejected some due to full mailbox
        assert full_count > 0
        
        # Should have processed some
        await asyncio.sleep(1.0)
        assert len(actor.operations) > 0
    
    finally:
        await actor.stop()


@pytest.mark.asyncio
async def test_chaos_cascade_failure():
    """Test cascading failure scenario."""
    event_store = EventStore(":memory:")
    
    # Create chain of dependent sagas
    cascade_results = []
    
    async def create_cascade_saga(index: int, should_fail: bool):
        saga = Saga(
            saga_id=f"cascade-{index}",
            correlation_id=f"cascade-{index}",
            event_store=event_store
        )
        
        # Step that depends on previous saga
        async def dependent_action():
            if index > 0 and cascade_results[index - 1] is False:
                raise Exception(f"Previous saga {index - 1} failed")
            
            if should_fail:
                raise Exception(f"Saga {index} deliberate failure")
            
            return {"index": index}
        
        async def dependent_compensation(result):
            pass
        
        saga.add_step(SagaStep(f"dependent-{index}", dependent_action, dependent_compensation))
        
        success = await saga.execute()
        cascade_results.append(success)
        return success
    
    # Create cascade: saga 2 will fail, causing 3 and 4 to fail
    results = []
    for i, should_fail in enumerate([False, False, True, False, False]):
        success = await create_cascade_saga(i, should_fail)
        results.append(success)
    
    print(f"Cascade Results: {results}")
    
    # First two should succeed
    assert results[0] is True
    assert results[1] is True
    
    # Third fails deliberately
    assert results[2] is False
    
    # Fourth and fifth fail due to cascade
    assert results[3] is False
    assert results[4] is False


@pytest.mark.asyncio
async def test_chaos_recovery():
    """Test recovery after chaos."""
    event_store = EventStore(":memory:")
    
    # Actor that tracks state
    class StatefulActor(Actor):
        def __init__(self):
            super().__init__("StatefulActor")
            self.state = {"counter": 0, "items": []}
            self.failure_count = 0
        
        async def _handle_increment(self, payload, reply_to, correlation_id):
            # Fail first 3 times
            if self.failure_count < 3:
                self.failure_count += 1
                raise Exception("Temporary failure")
            
            # Succeed after failures
            self.state["counter"] += 1
            self.state["items"].append(payload.get("item"))
            return {"status": "ok", "counter": self.state["counter"]}
    
    actor = StatefulActor()
    await actor.start()
    
    try:
        # Try operation multiple times until success
        max_attempts = 5
        success = False
        
        for attempt in range(max_attempts):
            result = await actor.ask("INCREMENT", {"item": f"item_{attempt}"}, timeout=1.0)
            if result.get("status") == "ok":
                success = True
                break
            else:
                print(f"Attempt {attempt + 1} failed: {result.get('error')}")
                await asyncio.sleep(0.1)
        
        # Should eventually succeed
        assert success
        assert actor.state["counter"] == 1
        
        # Subsequent operations should work
        result = await actor.ask("INCREMENT", {"item": "item_final"})
        assert result["counter"] == 2
    
    finally:
        await actor.stop()


@pytest.mark.asyncio
async def test_chaos_stress_test():
    """Stress test with high load and failures."""
    event_store = EventStore(":memory:")
    orchestrator = SagaOrchestrator(event_store, max_concurrent_sagas=50)
    
    # Create many actors
    actors = []
    for i in range(10):
        actor = ChaosActor(f"stress-actor-{i}", failure_rate=0.15)
        await actor.start()
        actors.append(actor)
    
    try:
        # Create many sagas
        saga_tasks = []
        
        for i in range(100):
            saga = Saga(
                saga_id=f"stress-saga-{i}",
                correlation_id=f"stress-{i}",
                event_store=event_store
            )
            
            # Add steps that use actors
            for j, actor in enumerate(random.sample(actors, min(3, len(actors)))):
                async def step_action(a=actor, idx=i):
                    return await a.ask("OPERATION", {"operation_id": f"saga-{idx}"}, timeout=2.0)
                
                async def step_compensation(result):
                    pass
                
                saga.add_step(SagaStep(f"step-{j}", step_action, step_compensation))
            
            # Start saga
            try:
                task = await orchestrator.start_saga(saga)
                saga_tasks.append(task)
            except Exception:
                pass  # May hit limit
        
        # Wait for completion
        start_time = time.time()
        results = await asyncio.gather(*saga_tasks, return_exceptions=True)
        elapsed = time.time() - start_time
        
        # Analyze results
        success_count = sum(1 for r in results if r is True)
        failure_count = sum(1 for r in results if r is False)
        
        print(f"\nStress Test Results:")
        print(f"Time: {elapsed:.2f}s")
        print(f"Sagas: {len(saga_tasks)}")
        print(f"Success: {success_count}")
        print(f"Failed: {failure_count}")
        
        # Get actor metrics
        for actor in actors:
            metrics = actor.get_metrics()
            print(f"{actor.name}: processed={metrics['processed_count']}, errors={metrics['error_count']}")
        
        # Should complete in reasonable time
        assert elapsed < 30
        
        # Should have processed many operations
        total_ops = sum(len(a.operations) for a in actors)
        assert total_ops > 50
    
    finally:
        for actor in actors:
            await actor.stop()
        
        await orchestrator.stop_all()
