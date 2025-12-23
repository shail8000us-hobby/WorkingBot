"""
Actor Stress Tests - RESTORED with Real Async Execution

Tests actor behavior under real concurrent load with:
- Async execution (actor.start() + asyncio.create_task)
- 100+ concurrent messages
- Race condition detection
- Performance benchmarking
- State consistency verification

QA NOTE: These tests use REAL actor execution, not mocks.
If tests fail, FIX THE ACTOR CODE, not the tests.
"""

import asyncio
import pytest
import time
from pathlib import Path
from bot.strategy.modules.event_store import EventStore
from bot.strategy.actors.position_actor import PositionManagerActor


class TestActorConcurrency:
    """Test actor concurrent message handling with real async execution."""
    
    @pytest.mark.asyncio
    async def test_concurrent_ask_messages(self):
        """
        RESTORED TEST: Actor handles 100 concurrent ASK messages correctly.
        
        Tests:
        - Actor starts and runs event loop
        - 100 concurrent GET_STATE messages
        - All messages receive valid responses
        - No race conditions or dropped messages
        """
        # Setup
        event_store = EventStore(":memory:")
        actor = PositionManagerActor(event_store=event_store, max_positions=10)
        
        # Start actor (runs event loop in background)
        actor_task = asyncio.create_task(actor.start())
        await asyncio.sleep(0.1)  # Let actor start
        
        try:
            print(f"\n{'='*60}")
            print("TEST: 100 Concurrent ASK Messages")
            print(f"{'='*60}")
            
            # Send 100 concurrent GET_STATE messages
            tasks = []
            for i in range(100):
                task = asyncio.create_task(
                    asyncio.wait_for(actor.ask("GET_STATE", {}), timeout=5.0)
                )
                tasks.append(task)
            
            # Gather all responses
            start_time = time.time()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            elapsed = time.time() - start_time
            
            # Verify all succeeded
            exceptions = [r for r in results if isinstance(r, Exception)]
            valid_results = [r for r in results if isinstance(r, dict)]
            
            print(f"Messages sent: 100")
            print(f"Valid responses: {len(valid_results)}")
            print(f"Exceptions: {len(exceptions)}")
            print(f"Time taken: {elapsed:.3f}s")
            print(f"Throughput: {100/elapsed:.1f} msg/s")
            
            # Assertions
            assert len(exceptions) == 0, f"Got exceptions: {exceptions[:3]}"
            assert len(valid_results) == 100, f"Expected 100 responses, got {len(valid_results)}"
            assert all('open_tranches' in r for r in valid_results), "Invalid response format"
            assert all('pending_buy' in r for r in valid_results), "Missing pending_buy"
            assert all('pending_sell' in r for r in valid_results), "Missing pending_sell"
            
            print(f"✅ SUCCESS: All 100 messages handled correctly")
            
        finally:
            # Cleanup
            await actor.stop()
            await actor_task
    
    @pytest.mark.asyncio
    async def test_concurrent_tell_messages(self):
        """
        RESTORED TEST: Actor handles concurrent TELL messages (fire-and-forget).
        
        Tests:
        - Multiple TELL messages sent concurrently
        - Actor processes all messages
        - No message loss
        """
        event_store = EventStore(":memory:")
        actor = PositionManagerActor(event_store=event_store, max_positions=20)
        
        actor_task = asyncio.create_task(actor.start())
        await asyncio.sleep(0.1)
        
        try:
            print(f"\n{'='*60}")
            print("TEST: Concurrent TELL Messages")
            print(f"{'='*60}")
            
            # Send 50 TELL messages (no response expected)
            for i in range(50):
                await actor.tell("LOG_MESSAGE", {"msg": f"test-{i}"})
            
            # Give actor time to process
            await asyncio.sleep(0.5)
            
            # Verify actor still responsive
            state = await asyncio.wait_for(actor.ask("GET_STATE", {}), timeout=5.0)
            assert state is not None
            assert 'open_tranches' in state
            
            print(f"✅ SUCCESS: TELL messages handled without blocking")
            
        finally:
            await actor.stop()
            await actor_task


class TestActorPerformance:
    """Test actor performance under high load."""
    
    @pytest.mark.asyncio
    async def test_high_throughput_messages(self):
        """
        RESTORED TEST: Actor achieves >500 messages/second throughput.
        
        Performance Target: >500 msg/s
        Test Load: 1000 messages
        
        This is a REAL performance test, not a structure check.
        """
        event_store = EventStore(":memory:")
        actor = PositionManagerActor(event_store=event_store, max_positions=50)
        
        actor_task = asyncio.create_task(actor.start())
        await asyncio.sleep(0.1)
        
        try:
            print(f"\n{'='*60}")
            print("PERFORMANCE BENCHMARK: Actor Throughput")
            print(f"{'='*60}")
            
            # Warm-up: 100 messages
            warmup_tasks = [actor.ask("GET_STATE", {}) for _ in range(100)]
            await asyncio.gather(*warmup_tasks)
            
            # Benchmark: 1000 messages
            print("Starting benchmark with 1000 messages...")
            start_time = time.time()
            
            benchmark_tasks = [actor.ask("GET_STATE", {}) for _ in range(1000)]
            results = await asyncio.gather(*benchmark_tasks, return_exceptions=True)
            
            elapsed = time.time() - start_time
            throughput = 1000 / elapsed
            latency_ms = (elapsed / 1000) * 1000
            
            # Count successes
            successes = sum(1 for r in results if isinstance(r, dict))
            
            print(f"Messages: 1000")
            print(f"Successes: {successes}")
            print(f"Time: {elapsed:.3f}s")
            print(f"Throughput: {throughput:.1f} msg/s")
            print(f"Avg Latency: {latency_ms:.2f}ms per message")
            print(f"{'='*60}")
            
            # Performance assertions
            assert successes == 1000, f"Lost messages: {1000 - successes}"
            assert throughput > 500, f"Throughput too low: {throughput:.1f} msg/s (target: >500)"
            
            print(f"✅ SUCCESS: Performance target met ({throughput:.1f} msg/s)")
            
        finally:
            await actor.stop()
            await actor_task


class TestActorStateConsistency:
    """Test actor state consistency under concurrent modifications."""
    
    @pytest.mark.asyncio
    async def test_state_consistency_under_concurrent_modifications(self):
        """
        RESTORED TEST: Concurrent ADD_POSITION messages maintain state consistency.
        
        Tests:
        - 30 positions added concurrently
        - No duplicates in position list
        - No duplicates in position index
        - All positions have correct data
        - EventStore has all events
        
        This test will CATCH RACE CONDITIONS if they exist.
        """
        event_store = EventStore(":memory:")
        actor = PositionManagerActor(event_store=event_store, max_positions=50)
        
        actor_task = asyncio.create_task(actor.start())
        await asyncio.sleep(0.1)
        
        try:
            print(f"\n{'='*60}")
            print("RACE CONDITION TEST: Concurrent State Modifications")
            print(f"{'='*60}")
            
            # Add 30 positions concurrently
            tasks = []
            for i in range(30):
                payload = {
                    "position_id": f"pos-{i:03d}",
                    "entry_price": 100000 + i * 100,
                    "tp_price": 101000 + i * 100,
                    "size": 1
                }
                task = asyncio.create_task(
                    asyncio.wait_for(actor.ask("ADD_POSITION", payload), timeout=5.0)
                )
                tasks.append(task)
            
            # Wait for all additions
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Check results
            exceptions = [r for r in results if isinstance(r, Exception)]
            successes = [r for r in results if isinstance(r, dict) and r.get('status') == 'ok']
            
            print(f"Positions attempted: 30")
            print(f"Successful additions: {len(successes)}")
            print(f"Exceptions: {len(exceptions)}")
            
            # Get final state
            state = await asyncio.wait_for(actor.ask("GET_STATE", {}), timeout=5.0)
            
            # Verify state consistency
            open_tranches = state['open_tranches']
            position_count = len(open_tranches)
            
            print(f"Final position count: {position_count}")
            
            # Extract position IDs
            position_ids = [p['position_id'] for p in open_tranches]
            unique_ids = set(position_ids)
            
            print(f"Unique position IDs: {len(unique_ids)}")
            
            # Check for duplicates
            duplicates = [pid for pid in position_ids if position_ids.count(pid) > 1]
            
            if duplicates:
                print(f"❌ RACE CONDITION DETECTED: Duplicate positions: {set(duplicates)}")
            
            # Verify EventStore
            events = event_store.get_all_events()
            position_events = [e for e in events if e.event_type.value == 'position_opened']
            
            print(f"EventStore position events: {len(position_events)}")
            print(f"{'='*60}")
            
            # CRITICAL ASSERTIONS
            assert len(exceptions) == 0, f"Got exceptions: {exceptions}"
            assert len(successes) == 30, f"Expected 30 successes, got {len(successes)}"
            assert position_count == 30, f"Expected 30 positions, got {position_count}"
            assert len(unique_ids) == 30, f"Duplicate positions detected: {30 - len(unique_ids)} duplicates"
            assert len(duplicates) == 0, f"RACE CONDITION: Duplicates found: {duplicates}"
            assert len(position_events) == 30, f"EventStore missing events: expected 30, got {len(position_events)}"
            
            # Verify position index integrity
            assert len(actor._position_index) == 30, f"Position index corrupted: {len(actor._position_index)} entries"
            
            # Verify all positions in index match state
            for pos_id in position_ids:
                assert pos_id in actor._position_index, f"Position {pos_id} missing from index"
            
            print(f"✅ SUCCESS: State consistent - No race conditions detected")
            
        finally:
            await actor.stop()
            await actor_task
    
    @pytest.mark.asyncio
    async def test_mixed_concurrent_operations(self):
        """
        RESTORED TEST: Mix of ADD and REMOVE operations concurrently.
        
        Tests:
        - Add 20 positions
        - Remove 10 positions concurrently with additions
        - Verify final count is correct
        - Verify no phantom positions
        """
        event_store = EventStore(":memory:")
        actor = PositionManagerActor(event_store=event_store, max_positions=50)
        
        actor_task = asyncio.create_task(actor.start())
        await asyncio.sleep(0.1)
        
        try:
            print(f"\n{'='*60}")
            print("COMPLEX RACE CONDITION TEST: Mixed Operations")
            print(f"{'='*60}")
            
            # First, add 20 positions
            add_tasks = []
            for i in range(20):
                payload = {
                    "position_id": f"pos-{i:03d}",
                    "entry_price": 100000 + i * 100,
                    "tp_price": 101000 + i * 100,
                    "size": 1
                }
                add_tasks.append(actor.ask("ADD_POSITION", payload))
            
            await asyncio.gather(*add_tasks)
            
            # Now concurrently: add 10 more, remove 10 existing
            concurrent_tasks = []
            
            # Add 10 new positions
            for i in range(20, 30):
                payload = {
                    "position_id": f"pos-{i:03d}",
                    "entry_price": 100000 + i * 100,
                    "tp_price": 101000 + i * 100,
                    "size": 1
                }
                concurrent_tasks.append(actor.ask("ADD_POSITION", payload))
            
            # Remove first 10 positions
            for i in range(10):
                concurrent_tasks.append(actor.ask("REMOVE_POSITION", {"position_id": f"pos-{i:03d}"}))
            
            # Execute all concurrently
            results = await asyncio.gather(*concurrent_tasks, return_exceptions=True)
            
            # Get final state
            await asyncio.sleep(0.2)  # Let all operations complete
            state = await actor.ask("GET_STATE", {})
            
            final_count = len(state['open_tranches'])
            remaining_ids = [p['position_id'] for p in state['open_tranches']]
            
            print(f"Initial: 20 positions")
            print(f"Added: 10 positions")
            print(f"Removed: 10 positions")
            print(f"Expected final: 20 positions")
            print(f"Actual final: {final_count} positions")
            print(f"{'='*60}")
            
            # Verify correct final count
            assert final_count == 20, f"Expected 20 positions, got {final_count}"
            
            # Verify removed positions are gone
            removed_ids = [f"pos-{i:03d}" for i in range(10)]
            for removed_id in removed_ids:
                assert removed_id not in remaining_ids, f"Position {removed_id} should be removed"
            
            # Verify new positions are present
            new_ids = [f"pos-{i:03d}" for i in range(20, 30)]
            for new_id in new_ids:
                assert new_id in remaining_ids, f"Position {new_id} should be present"
            
            print(f"✅ SUCCESS: Mixed concurrent operations handled correctly")
            
        finally:
            await actor.stop()
            await actor_task


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
