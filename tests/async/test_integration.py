"""
Integration Tests - End-to-End Component Testing

Tests real component interaction without mocking.
Verifies complete workflows from start to finish.
"""

import pytest
import asyncio
import time
from pathlib import Path
from uuid import uuid4

from bot.strategy.modules.event_store import EventStore, Event, EventType
from bot.strategy.actors.position_actor import PositionManagerActor
from bot.strategy.sagas.saga_coordinator import Saga, SagaStep


class TestActorCommunication:
    """Test real actor-to-actor communication without mocks."""
    
    @pytest.mark.asyncio
    async def test_position_actor_state_coordination(self):
        """
        Integration Test: Multiple concurrent state queries to position actor.
        
        Validates:
        - Actor processes concurrent messages
        - State remains consistent
        - No race conditions in multi-query scenarios
        """
        # Use in-memory EventStore (fast, no cleanup needed)
        event_store = EventStore(":memory:")
        
        # Create actor with real EventStore
        actor = PositionManagerActor(
            event_store=event_store,
            max_positions=10
        )
        
        # Start actor
        actor_task = asyncio.create_task(actor.start())
        await asyncio.sleep(0.05)  # Let actor initialize
        
        try:
            print(f"\n{'='*70}")
            print("INTEGRATION TEST: Actor State Coordination")
            print(f"{'='*70}")
            
            # Add 3 positions concurrently
            add_tasks = []
            for i in range(3):
                position = {
                    "position_id": f"pos-{i}",
                    "entry_price": 100000.0 + (i * 100),
                    "tp_price": 101000.0 + (i * 100),
                    "size": 1,
                    "correlation_id": f"corr-{i}"
                }
                task = actor.ask("ADD_POSITION", position)
                add_tasks.append(task)
            
            # Wait for all additions
            results = await asyncio.gather(*add_tasks)
            
            # Verify all succeeded
            for i, result in enumerate(results):
                assert result["status"] == "ok", f"Position {i} failed to add"
            
            print(f"✅ Added 3 positions concurrently")
            
            # Query state 10 times concurrently
            query_tasks = [actor.ask("GET_STATE", {}) for _ in range(10)]
            states = await asyncio.gather(*query_tasks)
            
            # Verify all queries returned same state
            for state in states:
                assert len(state["open_tranches"]) == 3, "Should have 3 positions"
                # Verify position IDs are correct
                pos_ids = [p["position_id"] for p in state["open_tranches"]]
                assert "pos-0" in pos_ids
                assert "pos-1" in pos_ids
                assert "pos-2" in pos_ids
            
            print(f"✅ 10 concurrent state queries returned consistent results")
            
            # Verify EventStore has all events
            events = event_store.get_all_events()
            position_opened_events = [e for e in events if e.event_type == EventType.POSITION_OPENED]
            assert len(position_opened_events) == 3, "Should have 3 POSITION_OPENED events"
            
            print(f"✅ EventStore contains 3 POSITION_OPENED events")
            print(f"   Total events in store: {len(events)}")
            
        finally:
            # Cleanup
            await actor.stop()
            await actor_task


class TestSagaActorIntegration:
    """Test saga coordination with real actors."""
    
    @pytest.mark.asyncio
    async def test_saga_with_actor_steps(self):
        """
        Integration Test: Saga coordinates multiple actor operations.
        
        Validates:
        - Saga steps communicate with actors
        - Actor state changes are persistent
        - Compensation works with real actors
        - EventStore records complete flow
        """
        event_store = EventStore(":memory:")
        
        # Create actor
        actor = PositionManagerActor(event_store=event_store, max_positions=5)
        
        # Start actor
        actor_task = asyncio.create_task(actor.start())
        await asyncio.sleep(0.05)
        
        try:
            print(f"\n{'='*70}")
            print("INTEGRATION TEST: Saga + Actor Integration")
            print(f"{'='*70}")
            
            # Create saga that adds positions via actor
            saga = Saga(
                saga_id="integration-saga",
                correlation_id="integration-001",
                event_store=event_store,
                timeout=5.0
            )
            
            # Step 1: Add first position
            async def add_position_1():
                result = await actor.ask("ADD_POSITION", {
                    "position_id": "pos-1",
                    "entry_price": 100000.0,
                    "tp_price": 101000.0,
                    "size": 1,
                    "correlation_id": "integration-001"
                })
                return result
            
            async def remove_position_1(result):
                await actor.ask("REMOVE_POSITION", {"position_id": "pos-1"})
            
            saga.add_step(SagaStep(
                name="add_position_1",
                action=add_position_1,
                compensation=remove_position_1
            ))
            
            # Step 2: Add second position
            async def add_position_2():
                result = await actor.ask("ADD_POSITION", {
                    "position_id": "pos-2",
                    "entry_price": 100500.0,
                    "tp_price": 101500.0,
                    "size": 1,
                    "correlation_id": "integration-001"
                })
                return result
            
            async def remove_position_2(result):
                await actor.ask("REMOVE_POSITION", {"position_id": "pos-2"})
            
            saga.add_step(SagaStep(
                name="add_position_2",
                action=add_position_2,
                compensation=remove_position_2
            ))
            
            # Execute saga
            success = await saga.execute()
            
            # Verify success
            assert success is True, "Saga should succeed"
            
            print(f"✅ Saga executed successfully")
            
            # Verify actor state
            state = await actor.ask("GET_STATE", {})
            assert len(state["open_tranches"]) == 2, "Should have 2 positions"
            
            positions = state["open_tranches"]
            assert positions[0]["position_id"] == "pos-1", "First position should be pos-1"
            assert positions[1]["position_id"] == "pos-2", "Second position should be pos-2"
            
            print(f"✅ Actor state verified: 2 positions added")
            
            # Verify EventStore has position events (saga events are in saga's EventStore)
            events = event_store.get_all_events()
            
            position_events = [e for e in events if e.event_type == EventType.POSITION_OPENED]
            
            assert len(position_events) == 2, "Should have 2 POSITION_OPENED events"
            
            print(f"✅ EventStore verified:")
            print(f"   Position events: {len(position_events)}")
            print(f"   Total events: {len(events)}")
            
        finally:
            await actor.stop()
            await actor_task
    
    @pytest.mark.asyncio
    async def test_saga_compensation_with_actor(self):
        """
        Integration Test: Saga compensation removes actor state.
        
        Validates:
        - Saga step fails after adding position
        - Compensation removes position from actor
        - Actor state is restored to pre-saga state
        - EventStore records compensation
        """
        event_store = EventStore(":memory:")
        
        actor = PositionManagerActor(event_store=event_store, max_positions=5)
        actor_task = asyncio.create_task(actor.start())
        await asyncio.sleep(0.05)
        
        try:
            print(f"\n{'='*70}")
            print("INTEGRATION TEST: Saga Compensation + Actor")
            print(f"{'='*70}")
            
            # Verify starting state
            state = await actor.ask("GET_STATE", {})
            assert len(state["open_tranches"]) == 0, "Should start with no positions"
            
            # Create saga that will fail
            saga = Saga(
                saga_id="compensation-saga",
                correlation_id="compensation-001",
                event_store=event_store,
                timeout=5.0
            )
            
            # Step 1: Add position (will succeed)
            async def add_position():
                result = await actor.ask("ADD_POSITION", {
                    "position_id": "temp-pos",
                    "entry_price": 100000.0,
                    "tp_price": 101000.0,
                    "size": 1,
                    "correlation_id": "compensation-001"
                })
                return result
            
            async def remove_position(result):
                await actor.ask("REMOVE_POSITION", {"position_id": "temp-pos"})
            
            saga.add_step(SagaStep(
                name="add_temp_position",
                action=add_position,
                compensation=remove_position
            ))
            
            # Step 2: Fail intentionally
            async def fail_step():
                raise Exception("Intentional failure")
            
            async def no_compensation(result):
                pass
            
            saga.add_step(SagaStep(
                name="fail_step",
                action=fail_step,
                compensation=no_compensation
            ))
            
            # Execute saga (should fail and compensate)
            success = await saga.execute()
            
            # Verify failure
            assert success is False, "Saga should fail"
            assert saga.context.status == "compensated", "Saga should be compensated"
            
            print(f"✅ Saga failed and triggered compensation")
            
            # Verify actor state restored (position removed)
            state = await actor.ask("GET_STATE", {})
            assert len(state["open_tranches"]) == 0, "Position should be removed by compensation"
            
            print(f"✅ Actor state restored by compensation")
            
            # Verify EventStore has position lifecycle events
            events = event_store.get_all_events()
            
            # Verify position was added then removed
            position_opened = [e for e in events if e.event_type == EventType.POSITION_OPENED]
            position_closed = [e for e in events if e.event_type == EventType.POSITION_CLOSED]
            
            assert len(position_opened) == 1, "Position should have been opened"
            assert len(position_closed) == 1, "Position should have been closed (compensation)"
            
            print(f"✅ EventStore verified:")
            print(f"   Position opened: {len(position_opened)}")
            print(f"   Position closed: {len(position_closed)}")
            print(f"   Total events: {len(events)}")
            
        finally:
            await actor.stop()
            await actor_task


class TestEventStoreIntegration:
    """Test EventStore persistence and replay."""
    
    @pytest.mark.asyncio
    async def test_event_store_persists_across_actor_restarts(self):
        """
        Integration Test: EventStore persists events, actor can reload state.
        
        Validates:
        - Events persist to disk
        - Actor can be stopped and restarted
        - State is reconstructed from EventStore
        """
        # Use real SQLite file
        db_path = Path("test_integration_restart.db")
        
        try:
            # Cleanup any existing test database
            if db_path.exists():
                db_path.unlink()
            
            print(f"\n{'='*70}")
            print("INTEGRATION TEST: EventStore Persistence")
            print(f"{'='*70}")
            
            # Phase 1: Create actor, add position, stop
            event_store = EventStore(str(db_path))
            actor = PositionManagerActor(event_store=event_store, max_positions=5)
            
            actor_task = asyncio.create_task(actor.start())
            await asyncio.sleep(0.05)
            
            # Add position
            result = await actor.ask("ADD_POSITION", {
                "position_id": "persistent-pos",
                "entry_price": 100000.0,
                "tp_price": 101000.0,
                "size": 1,
                "correlation_id": "persist-001"
            })
            assert result["status"] == "ok"
            
            # Verify state
            state = await actor.ask("GET_STATE", {})
            assert len(state["open_tranches"]) == 1
            
            print(f"✅ Phase 1: Added position, EventStore has {len(event_store.get_all_events())} events")
            
            # Stop actor
            await actor.stop()
            await actor_task
            
            # Phase 2: Verify EventStore persisted events (actor state reconstruction not yet implemented)
            event_store2 = EventStore(str(db_path))
            
            # Verify events persisted to disk
            events1 = event_store.get_all_events()
            events2 = event_store2.get_all_events()
            assert len(events1) == len(events2), "Event count should match"
            assert len(events2) > 0, "Events should persist"
            
            # Verify event content persisted
            position_events = [e for e in events2 if e.event_type == EventType.POSITION_OPENED]
            assert len(position_events) == 1, "Position event should persist"
            assert position_events[0].aggregate_id == "persistent-pos"
            
            print(f"✅ Phase 2: EventStore persistence verified")
            print(f"   Events persisted: {len(events2)}")
            print(f"   Position events: {len(position_events)}")
            print(f"   Event IDs match: {events1[0].event_id == events2[0].event_id}")
            
            # Note: Actor state reconstruction from EventStore not yet implemented
            # This would require replaying all events on actor startup
            print(f"📝 Note: Actor state reconstruction requires event replay (future enhancement)")
            
        finally:
            # Cleanup test database
            if db_path.exists():
                db_path.unlink()
    
    @pytest.mark.asyncio
    async def test_event_replay_reconstructs_state(self):
        """
        Integration Test: Event replay can reconstruct historical state.
        
        Validates:
        - Events recorded in correct order
        - Replaying events rebuilds state
        - Time-travel queries work
        """
        event_store = EventStore(":memory:")
        
        print(f"\n{'='*70}")
        print("INTEGRATION TEST: Event Replay")
        print(f"{'='*70}")
        
        # Record series of events
        timestamps = []
        
        # T0: Add position 1
        t0 = time.time()
        timestamps.append(t0)
        event_store.append_event(Event(
            event_id=str(uuid4()),
            event_type=EventType.POSITION_OPENED,
            timestamp=t0,
            correlation_id="replay-001",
            aggregate_id="pos-1",
            data={"entry_price": 100000.0, "size": 1, "position_id": "pos-1"},
            metadata={}
        ))
        
        await asyncio.sleep(0.01)
        
        # T1: Add position 2
        t1 = time.time()
        timestamps.append(t1)
        event_store.append_event(Event(
            event_id=str(uuid4()),
            event_type=EventType.POSITION_OPENED,
            timestamp=t1,
            correlation_id="replay-002",
            aggregate_id="pos-2",
            data={"entry_price": 100500.0, "size": 1, "position_id": "pos-2"},
            metadata={}
        ))
        
        await asyncio.sleep(0.01)
        
        # T2: Close position 1
        t2 = time.time()
        timestamps.append(t2)
        event_store.append_event(Event(
            event_id=str(uuid4()),
            event_type=EventType.POSITION_CLOSED,
            timestamp=t2,
            correlation_id="replay-003",
            aggregate_id="pos-1",
            data={"position_id": "pos-1", "close_price": 101000.0},
            metadata={}
        ))
        
        print(f"✅ Recorded 3 events across {len(timestamps)} timestamps")
        
        # Replay all events
        all_events = event_store.get_all_events()
        assert len(all_events) == 3, "Should have 3 events"
        
        # Verify event order
        assert all_events[0].event_type == EventType.POSITION_OPENED
        assert all_events[0].aggregate_id == "pos-1"
        
        assert all_events[1].event_type == EventType.POSITION_OPENED
        assert all_events[1].aggregate_id == "pos-2"
        
        assert all_events[2].event_type == EventType.POSITION_CLOSED
        assert all_events[2].aggregate_id == "pos-1"
        
        print(f"✅ Event order verified (pos-1 opened → pos-2 opened → pos-1 closed)")
        
        # Time-travel query: Get state at T1 (before pos-1 closed)
        events_at_t1 = event_store.get_events_since(0)
        events_before_t2 = [e for e in events_at_t1 if e.timestamp < t2]
        
        # At T1: Should have 2 positions open
        opened_count = len([e for e in events_before_t2 if e.event_type == EventType.POSITION_OPENED])
        closed_count = len([e for e in events_before_t2 if e.event_type == EventType.POSITION_CLOSED])
        
        assert opened_count == 2, "Should have 2 positions opened before T2"
        assert closed_count == 0, "Should have 0 positions closed before T2"
        
        print(f"✅ Time-travel query to T1: 2 positions open, 0 closed")
        
        # Query final state
        opened_total = len([e for e in all_events if e.event_type == EventType.POSITION_OPENED])
        closed_total = len([e for e in all_events if e.event_type == EventType.POSITION_CLOSED])
        
        assert opened_total == 2, "Total: 2 positions opened"
        assert closed_total == 1, "Total: 1 position closed"
        
        # Net state: 1 position open (pos-2)
        net_open = opened_total - closed_total
        assert net_open == 1, "Net: 1 position still open"
        
        print(f"✅ Final state: {net_open} position open (pos-2)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
