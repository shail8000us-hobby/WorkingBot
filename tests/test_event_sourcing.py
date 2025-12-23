"""
Comprehensive test suite for Event Sourcing implementation.
Tests EventStore, StateProjector, and integration scenarios.
"""

import json
import os
import pytest
import sqlite3
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import List

from bot.strategy.modules.event_store import Event, EventType, EventStore
from bot.strategy.modules.state_projector import StateProjector


class TestEventStore:
    """Unit tests for EventStore class."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database file for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            yield tmp.name
        # Cleanup
        try:
            os.unlink(tmp.name)
            os.unlink(tmp.name + '-wal')  # Remove WAL file if exists
            os.unlink(tmp.name + '-shm')  # Remove shared memory file if exists
        except FileNotFoundError:
            pass
    
    @pytest.fixture
    def event_store(self, temp_db):
        """Create an EventStore instance with temporary database."""
        return EventStore(temp_db)
    
    @pytest.fixture
    def sample_event(self):
        """Create a sample event for testing."""
        return Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.POSITION_OPENED,
            timestamp=time.time(),
            correlation_id=str(uuid.uuid4()),
            aggregate_id="pos_test123",
            data={
                "position_id": "pos_test123",
                "entry_price": 65000.0,
                "tp_price": 66000.0,
                "size": 1,
                "mode": "LONG"
            },
            metadata={"bot_version": "2.0", "test": True}
        )
    
    def test_event_store_initialization(self, temp_db):
        """Test that EventStore creates database with correct schema."""
        store = EventStore(temp_db)
        
        # Verify database file exists
        assert os.path.exists(temp_db)
        
        # Verify tables and indexes exist
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Check events table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='events'
        """)
        assert cursor.fetchone() is not None
        
        # Check indexes exist
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name LIKE 'idx_%'
        """)
        indexes = [row[0] for row in cursor.fetchall()]
        assert 'idx_timestamp' in indexes
        assert 'idx_correlation' in indexes
        assert 'idx_aggregate' in indexes
        
        conn.close()
    
    def test_append_and_retrieve_event(self, event_store, sample_event):
        """Test appending an event and retrieving it."""
        # Append event
        event_store.append_event(sample_event)
        
        # Retrieve all events
        events = event_store.get_all_events()
        assert len(events) == 1
        
        # Verify event data
        retrieved = events[0]
        assert retrieved.event_id == sample_event.event_id
        assert retrieved.event_type == sample_event.event_type
        assert retrieved.correlation_id == sample_event.correlation_id
        assert retrieved.aggregate_id == sample_event.aggregate_id
        assert retrieved.data == sample_event.data
        assert retrieved.metadata == sample_event.metadata
    
    def test_get_events_since(self, event_store):
        """Test retrieving events after a specific timestamp."""
        base_time = time.time()
        events = []
        
        # Create 10 events at different timestamps
        for i in range(10):
            event = Event(
                event_id=str(uuid.uuid4()),
                event_type=EventType.ORDER_PLACED,
                timestamp=base_time + i,
                correlation_id="test_correlation",
                aggregate_id=f"order_{i}",
                data={"index": i},
                metadata={}
            )
            events.append(event)
            event_store.append_event(event)
        
        # Query from middle
        middle_time = base_time + 4.5
        recent_events = event_store.get_events_since(middle_time)
        
        # Should get events 5-9 (5 events)
        assert len(recent_events) == 5
        assert all(e.timestamp > middle_time for e in recent_events)
        assert recent_events[0].data['index'] == 5
        assert recent_events[-1].data['index'] == 9
    
    def test_get_events_by_correlation(self, event_store):
        """Test retrieving events with same correlation ID."""
        correlation_id = str(uuid.uuid4())
        
        # Create related events
        for i in range(3):
            event = Event(
                event_id=str(uuid.uuid4()),
                event_type=EventType.ORDER_PLACED,
                timestamp=time.time() + i,
                correlation_id=correlation_id,
                aggregate_id=f"order_{i}",
                data={"step": i},
                metadata={}
            )
            event_store.append_event(event)
        
        # Create unrelated event
        unrelated = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.POSITION_CLOSED,
            timestamp=time.time(),
            correlation_id=str(uuid.uuid4()),
            aggregate_id="other",
            data={},
            metadata={}
        )
        event_store.append_event(unrelated)
        
        # Query by correlation
        related_events = event_store.get_events_by_correlation(correlation_id)
        assert len(related_events) == 3
        assert all(e.correlation_id == correlation_id for e in related_events)
    
    def test_concurrent_writes(self, event_store):
        """Test thread safety with concurrent event appends."""
        num_threads = 100
        events_per_thread = 1
        all_event_ids = []
        
        def append_events(thread_id):
            event = Event(
                event_id=f"event_{thread_id}_{uuid.uuid4()}",
                event_type=EventType.ORDER_FILLED,
                timestamp=time.time(),
                correlation_id="concurrent_test",
                aggregate_id=f"thread_{thread_id}",
                data={"thread": thread_id},
                metadata={}
            )
            event_store.append_event(event)
            all_event_ids.append(event.event_id)
        
        # Start threads
        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=append_events, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # Verify all events persisted
        events = event_store.get_all_events()
        assert len(events) == num_threads
        
        # Verify all event IDs present
        stored_ids = {e.event_id for e in events}
        for event_id in all_event_ids:
            assert event_id in stored_ids
    
    def test_wal_mode_enabled(self, event_store):
        """Test that WAL mode is properly enabled."""
        assert event_store.verify_wal_mode() == True
    
    def test_rollback_on_error(self, event_store):
        """Test that transactions rollback on error."""
        # Create valid event
        valid_event = Event(
            event_id="test_123",
            event_type=EventType.POSITION_OPENED,
            timestamp=time.time(),
            correlation_id="test",
            aggregate_id="pos_1",
            data={},
            metadata={}
        )
        
        # Append valid event
        event_store.append_event(valid_event)
        
        # Try to append duplicate (should fail)
        with pytest.raises(sqlite3.IntegrityError):
            event_store.append_event(valid_event)
        
        # Verify only one event in store
        events = event_store.get_all_events()
        assert len(events) == 1
    
    def test_event_count_and_latest_timestamp(self, event_store):
        """Test event count and latest timestamp methods."""
        # Empty store
        assert event_store.get_event_count() == 0
        assert event_store.get_latest_event_timestamp() is None
        
        # Add events
        timestamps = []
        for i in range(5):
            ts = time.time() + i
            timestamps.append(ts)
            event = Event(
                event_id=str(uuid.uuid4()),
                event_type=EventType.ORDER_PLACED,
                timestamp=ts,
                correlation_id="test",
                aggregate_id=f"order_{i}",
                data={},
                metadata={}
            )
            event_store.append_event(event)
        
        # Verify count and latest timestamp
        assert event_store.get_event_count() == 5
        assert event_store.get_latest_event_timestamp() == max(timestamps)


class TestStateProjector:
    """Unit tests for StateProjector class."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database file for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            yield tmp.name
        # Cleanup
        try:
            os.unlink(tmp.name)
            os.unlink(tmp.name + '-wal')
            os.unlink(tmp.name + '-shm')
        except FileNotFoundError:
            pass
    
    @pytest.fixture
    def projector(self, temp_db):
        """Create a StateProjector with temporary database."""
        store = EventStore(temp_db)
        return StateProjector(store)
    
    def test_project_empty_state(self, projector):
        """Test projecting state with no events."""
        state = projector.project_current_state()
        
        # Verify clean state structure
        assert state['open_tranches'] == []
        assert state['pending_buy'] is None
        assert state['pending_sell'] is None
        assert state['last_buy_order_time'] == 0
        assert state['last_sell_order_time'] == 0
        assert state['tp_orders'] == {}
    
    def test_project_with_positions(self, projector):
        """Test projecting state with position events."""
        # Add position opened events
        for i in range(3):
            event = Event(
                event_id=str(uuid.uuid4()),
                event_type=EventType.POSITION_OPENED,
                timestamp=time.time() + i,
                correlation_id="test",
                aggregate_id=f"pos_{i}",
                data={
                    "position_id": f"pos_{i}",
                    "entry_price": 65000 + i * 1000,
                    "size": 1
                },
                metadata={}
            )
            projector.event_store.append_event(event)
        
        # Project state
        state = projector.project_current_state()
        
        # Verify positions
        assert len(state['open_tranches']) == 3
        assert state['open_tranches'][0]['position_id'] == 'pos_0'
        assert state['open_tranches'][1]['entry_price'] == 66000
    
    def test_project_with_order_lifecycle(self, projector):
        """Test order placed → filled lifecycle."""
        order_id = "order_123"
        ts = time.time()
        
        # Order placed
        placed_event = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.ORDER_PLACED,
            timestamp=ts,
            correlation_id="test",
            aggregate_id=order_id,
            data={
                "order_id": order_id,
                "side": "buy",
                "price": 64000.0,
                "size": 1
            },
            metadata={}
        )
        projector.event_store.append_event(placed_event)
        
        # Project after placement
        state1 = projector.project_current_state()
        assert state1['pending_buy'] is not None
        assert state1['pending_buy']['order_id'] == order_id
        assert state1['last_buy_order_time'] == ts
        
        # Order filled
        filled_event = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.ORDER_FILLED,
            timestamp=ts + 10,
            correlation_id="test",
            aggregate_id=order_id,
            data={
                "order_id": order_id,
                "side": "buy",
                "fill_price": 64000.0
            },
            metadata={}
        )
        projector.event_store.append_event(filled_event)
        
        # Project after fill
        state2 = projector.project_current_state()
        assert state2['pending_buy'] is None
        assert state2['last_buy_order_time'] == ts  # Timestamp unchanged
    
    def test_time_travel(self, projector):
        """Test projecting state at different points in time."""
        base_time = time.time()
        
        # Add events at different times
        events_data = [
            (base_time, EventType.POSITION_OPENED, "pos_1"),
            (base_time + 5, EventType.ORDER_PLACED, "order_1"),
            (base_time + 10, EventType.POSITION_OPENED, "pos_2"),
            (base_time + 15, EventType.ORDER_FILLED, "order_1"),
            (base_time + 20, EventType.POSITION_CLOSED, "pos_1"),
        ]
        
        for ts, event_type, aggregate_id in events_data:
            data = {}
            if event_type == EventType.POSITION_OPENED:
                data = {"position_id": aggregate_id, "entry_price": 65000}
            elif event_type == EventType.ORDER_PLACED:
                data = {"order_id": aggregate_id, "side": "buy"}
            elif event_type == EventType.ORDER_FILLED:
                data = {"order_id": aggregate_id, "side": "buy"}
            elif event_type == EventType.POSITION_CLOSED:
                data = {"position_id": aggregate_id}
            
            event = Event(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                timestamp=ts,
                correlation_id="time_travel",
                aggregate_id=aggregate_id,
                data=data,
                metadata={}
            )
            projector.event_store.append_event(event)
        
        # Project at T+7 (after first position and order placed)
        state_t7 = projector.project_state_at(base_time + 7)
        assert len(state_t7['open_tranches']) == 1
        assert state_t7['pending_buy'] is not None
        
        # Project at T+17 (order filled, both positions open)
        state_t17 = projector.project_state_at(base_time + 17)
        assert len(state_t17['open_tranches']) == 2
        assert state_t17['pending_buy'] is None
        
        # Project at current (pos_1 closed)
        state_current = projector.project_current_state()
        assert len(state_current['open_tranches']) == 1
        assert state_current['open_tranches'][0]['position_id'] == 'pos_2'
    
    def test_idempotency(self, projector):
        """Test that processing same event twice produces same state."""
        position_id = "pos_duplicate"
        
        # Create duplicate events (same data)
        for _ in range(2):
            event = Event(
                event_id=str(uuid.uuid4()),  # Different event IDs
                event_type=EventType.POSITION_OPENED,
                timestamp=time.time(),
                correlation_id="test",
                aggregate_id=position_id,  # Same aggregate
                data={
                    "position_id": position_id,
                    "entry_price": 65000.0,
                    "size": 1
                },
                metadata={}
            )
            projector.event_store.append_event(event)
        
        # Project state
        state = projector.project_current_state()
        
        # Should only have one position (idempotent)
        assert len(state['open_tranches']) == 1
        assert state['open_tranches'][0]['position_id'] == position_id
    
    def test_tp_order_tracking(self, projector):
        """Test TP order placement and tracking."""
        position_id = "pos_with_tp"
        tp_order_id = "tp_order_123"
        
        # Open position
        pos_event = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.POSITION_OPENED,
            timestamp=time.time(),
            correlation_id="tp_test",
            aggregate_id=position_id,
            data={"position_id": position_id, "entry_price": 65000},
            metadata={}
        )
        projector.event_store.append_event(pos_event)
        
        # Place TP order
        tp_event = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.TP_PLACED,
            timestamp=time.time() + 1,
            correlation_id="tp_test",
            aggregate_id=tp_order_id,
            data={
                "position_id": position_id,
                "order_id": tp_order_id,
                "price": 66000
            },
            metadata={}
        )
        projector.event_store.append_event(tp_event)
        
        # Project and verify
        state = projector.project_current_state()
        assert position_id in state['tp_orders']
        assert state['tp_orders'][position_id] == tp_order_id
    
    def test_state_validation(self, projector):
        """Test state validation method."""
        # Valid state
        valid_state = {
            'open_tranches': [{'position_id': 'pos_1'}],
            'pending_buy': None,
            'pending_sell': None,
            'last_buy_order_time': 0,
            'last_sell_order_time': 0,
            'tp_orders': {}
        }
        errors = projector.validate_state(valid_state)
        assert len(errors) == 0
        
        # Invalid state - missing field
        invalid_state = {
            'open_tranches': [],
            'pending_buy': None
        }
        errors = projector.validate_state(invalid_state)
        assert len(errors) > 0
        assert any('Missing required field' in e for e in errors)
        
        # Invalid state - wrong type
        invalid_state2 = valid_state.copy()
        invalid_state2['open_tranches'] = "not_a_list"
        errors = projector.validate_state(invalid_state2)
        assert any('must be a list' in e for e in errors)


class TestIntegration:
    """Integration tests for complete event sourcing system."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database file for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            yield tmp.name
        # Cleanup
        try:
            os.unlink(tmp.name)
            os.unlink(tmp.name + '-wal')
            os.unlink(tmp.name + '-shm')
        except FileNotFoundError:
            pass
    
    def test_crash_recovery_simulation(self, temp_db):
        """Test recovering state after simulated crash."""
        # Phase 1: Create events before "crash"
        store1 = EventStore(temp_db)
        
        # Generate 50 mixed events
        correlation_id = str(uuid.uuid4())
        for i in range(50):
            event_type = [
                EventType.POSITION_OPENED,
                EventType.ORDER_PLACED,
                EventType.ORDER_FILLED,
                EventType.TP_PLACED,
                EventType.POSITION_CLOSED
            ][i % 5]
            
            data = {}
            aggregate_id = f"entity_{i}"
            
            if event_type == EventType.POSITION_OPENED:
                data = {"position_id": aggregate_id, "entry_price": 65000 + i}
            elif event_type == EventType.ORDER_PLACED:
                data = {"order_id": aggregate_id, "side": "buy" if i % 2 == 0 else "sell"}
            elif event_type == EventType.ORDER_FILLED:
                data = {"order_id": f"entity_{i-1}", "side": "buy" if (i-1) % 2 == 0 else "sell"}
            elif event_type == EventType.TP_PLACED:
                data = {"position_id": f"entity_{i-4}", "order_id": aggregate_id}
            elif event_type == EventType.POSITION_CLOSED:
                data = {"position_id": f"entity_{i-4}"}
            
            event = Event(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                timestamp=time.time() + i,
                correlation_id=correlation_id,
                aggregate_id=aggregate_id,
                data=data,
                metadata={"sequence": i}
            )
            store1.append_event(event)
        
        # Project state before "crash"
        projector1 = StateProjector(store1)
        state_before = projector1.project_current_state()
        
        # Phase 2: Simulate crash and recovery
        del store1  # "Crash"
        del projector1
        
        # Create new instances (simulate restart)
        store2 = EventStore(temp_db)
        projector2 = StateProjector(store2)
        
        # Recover state
        state_after = projector2.project_current_state()
        
        # Verify state matches
        assert len(state_after['open_tranches']) == len(state_before['open_tranches'])
        assert state_after['pending_buy'] == state_before['pending_buy']
        assert state_after['pending_sell'] == state_before['pending_sell']
        assert state_after['tp_orders'] == state_before['tp_orders']
    
    def test_dual_write_compatibility(self, temp_db):
        """Test that event-sourced state matches JSON state."""
        store = EventStore(temp_db)
        projector = StateProjector(store)
        
        # Simulate dual-write scenario
        json_state = {
            'open_tranches': [],
            'pending_buy': None,
            'pending_sell': None,
            'last_buy_order_time': 0,
            'last_sell_order_time': 0,
            'tp_orders': {}
        }
        
        # Simulate operations with dual write
        operations = [
            ('position_open', 'pos_1', 65000),
            ('order_place', 'order_1', 'buy'),
            ('position_open', 'pos_2', 66000),
            ('order_fill', 'order_1', 'buy'),
            ('tp_place', 'pos_1', 'tp_1'),
            ('position_close', 'pos_1', None),
        ]
        
        for op_type, entity_id, param in operations:
            ts = time.time()
            
            # Update JSON state (legacy)
            if op_type == 'position_open':
                json_state['open_tranches'].append({
                    'position_id': entity_id,
                    'entry_price': param
                })
            elif op_type == 'order_place':
                order = {'order_id': entity_id, 'side': param}
                if param == 'buy':
                    json_state['pending_buy'] = order
                    json_state['last_buy_order_time'] = ts
                else:
                    json_state['pending_sell'] = order
                    json_state['last_sell_order_time'] = ts
            elif op_type == 'order_fill':
                if param == 'buy':
                    json_state['pending_buy'] = None
                else:
                    json_state['pending_sell'] = None
            elif op_type == 'tp_place':
                json_state['tp_orders'][entity_id] = param
            elif op_type == 'position_close':
                json_state['open_tranches'] = [
                    p for p in json_state['open_tranches'] 
                    if p['position_id'] != entity_id
                ]
                if entity_id in json_state['tp_orders']:
                    del json_state['tp_orders'][entity_id]
            
            # Write event (new system)
            event_type_map = {
                'position_open': EventType.POSITION_OPENED,
                'order_place': EventType.ORDER_PLACED,
                'order_fill': EventType.ORDER_FILLED,
                'tp_place': EventType.TP_PLACED,
                'position_close': EventType.POSITION_CLOSED,
            }
            
            data = {}
            if op_type == 'position_open':
                data = {'position_id': entity_id, 'entry_price': param}
            elif op_type == 'order_place':
                data = {'order_id': entity_id, 'side': param}
            elif op_type == 'order_fill':
                data = {'order_id': entity_id, 'side': param}
            elif op_type == 'tp_place':
                data = {'position_id': entity_id, 'order_id': param}
            elif op_type == 'position_close':
                data = {'position_id': entity_id}
            
            event = Event(
                event_id=str(uuid.uuid4()),
                event_type=event_type_map[op_type],
                timestamp=ts,
                correlation_id="dual_write_test",
                aggregate_id=entity_id,
                data=data,
                metadata={}
            )
            store.append_event(event)
        
        # Compare states
        projected_state = projector.project_current_state()
        
        # Verify match
        assert len(projected_state['open_tranches']) == len(json_state['open_tranches'])
        assert projected_state['pending_buy'] == json_state['pending_buy']
        assert projected_state['pending_sell'] == json_state['pending_sell']
        assert projected_state['tp_orders'] == json_state['tp_orders']


class TestPerformance:
    """Performance tests for event sourcing system."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database file for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            yield tmp.name
        # Cleanup
        try:
            os.unlink(tmp.name)
            os.unlink(tmp.name + '-wal')
            os.unlink(tmp.name + '-shm')
        except FileNotFoundError:
            pass
    
    def test_append_latency(self, temp_db):
        """Test append latency for 1000 events."""
        store = EventStore(temp_db)
        latencies = []
        
        for i in range(1000):
            event = Event(
                event_id=str(uuid.uuid4()),
                event_type=EventType.ORDER_PLACED,
                timestamp=time.time(),
                correlation_id="perf_test",
                aggregate_id=f"order_{i}",
                data={"index": i, "price": 65000 + i},
                metadata={"test": "performance"}
            )
            
            start = time.perf_counter()
            store.append_event(event)
            latency = (time.perf_counter() - start) * 1000  # Convert to ms
            latencies.append(latency)
        
        # Calculate percentiles
        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p99 = latencies[int(len(latencies) * 0.99)]
        
        print(f"\nAppend Latency - P50: {p50:.2f}ms, P99: {p99:.2f}ms")
        
        # Assert performance targets
        assert p99 < 5.0, f"P99 latency {p99:.2f}ms exceeds 5ms target"
    
    def test_replay_performance(self, temp_db):
        """Test replay performance for 10k events."""
        store = EventStore(temp_db)
        
        # Generate 10k events
        print("\nGenerating 10k events...")
        for i in range(10000):
            event_type = [
                EventType.POSITION_OPENED,
                EventType.ORDER_PLACED,
                EventType.ORDER_FILLED,
                EventType.POSITION_CLOSED
            ][i % 4]
            
            event = Event(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                timestamp=time.time() + i,
                correlation_id="replay_test",
                aggregate_id=f"entity_{i}",
                data={"index": i},
                metadata={}
            )
            store.append_event(event)
        
        # Measure replay time
        projector = StateProjector(store)
        
        start = time.perf_counter()
        state = projector.project_current_state()
        replay_time = time.perf_counter() - start
        
        print(f"Replay 10k events: {replay_time:.3f}s")
        
        # Assert performance target
        assert replay_time < 1.0, f"Replay time {replay_time:.3f}s exceeds 1s target"
