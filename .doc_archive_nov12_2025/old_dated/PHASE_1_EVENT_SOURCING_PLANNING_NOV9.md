# Phase 1: Event Sourcing State Management - Planning Document

**Date**: November 9, 2025  
**Duration**: 4-6 weeks (Weeks 1-6)  
**Goal**: Replace file-based state with append-only event log  
**Score Impact**: 7.6/10 → 8.5/10  
**Status**: 📋 PLANNING

---

## Executive Summary

Phase 1 transforms GridBot's state management from **snapshot-based JSON files** to **event sourcing with SQLite**. This architectural change provides:

- ✅ **ACID guarantees** (atomic, consistent, isolated, durable)
- ✅ **Zero data loss** (Write-Ahead Logging persists immediately)
- ✅ **Full audit trail** (every state change recorded)
- ✅ **Time travel debugging** (rebuild state at any point in history)
- ✅ **Crash recovery** (deterministic state reconstruction from events)

---

## Problem Statement

### Current State (File-Based Snapshots)

**Architecture**:
```
State Updates → In-Memory Dict → Periodic Write (15s) → JSON File
                                      ↓ (crash here)
                                   [DATA LOSS]
```

**Critical Issues**:
1. **15-second persistence gap**: Phase 0 fixed immediate persistence but still uses JSON
2. **Non-atomic writes**: Backup → Write → Rename can corrupt both files if crashed mid-operation
3. **No audit trail**: Can't trace why state changed or when
4. **Staleness threshold**: State >5 minutes old is discarded (reconciliation gap)
5. **Schema fragility**: JSON schema changes require migration scripts

**Current Code** (`bot/strategy/modules/position_manager.py`):
```python
def persist_runtime_state(self, filename: str = 'runtime_state.json', force: bool = False) -> None:
    # 1. Create backup (can fail)
    shutil.copy2(filename, backup_file)
    
    # 2. Build state dict (in-memory)
    data = {
        'timestamp': time.time(),
        'open_tranches': self.open_tranches.copy(),
        'pending_buy': self.pending_buy.copy() if self.pending_buy else None,
        # ...
    }
    
    # 3. Write to temp file (can fail)
    with open(temp_file, 'w') as f:
        json.dump(state_with_metadata, f, indent=2)
    
    # 4. Atomic rename (can corrupt if crash between 1-3)
    os.replace(temp_file, filename)
```

**Problems**:
- If crash between steps 1-3: Both backup and primary can be corrupt
- No history: Only current state saved (lost context of changes)
- No idempotency: Can't safely replay operations

---

## Target State (Event Sourcing)

### Architecture Transformation

```
State Updates → Event → SQLite WAL → Immediate Persistence (ACID)
                         ↓
                    Event Log (immutable) → Rebuild State from Events
                                          → Query history at any timestamp
```

**Benefits**:
- **Atomic**: Each event write is a single transaction
- **Durable**: SQLite WAL ensures persistence before commit returns
- **Auditable**: Every change has timestamp, correlation ID, metadata
- **Rebuildable**: State can be reconstructed from events at any point
- **Testable**: Replay events to test state transitions

---

## Phase 1 Roadmap

### Week 1-2: Event Store Foundation

#### Deliverable 1.1: Event Schema Definition

**File**: `bot/strategy/modules/event_store.py` (NEW)

**Event Types**:
```python
class EventType(Enum):
    # Position Lifecycle
    POSITION_OPENED = "position_opened"      # Entry order filled
    POSITION_CLOSED = "position_closed"      # TP order filled
    
    # Order Lifecycle
    ORDER_PLACED = "order_placed"            # BUY/SELL order placed
    ORDER_FILLED = "order_filled"            # Order completely filled
    ORDER_PARTIAL_FILLED = "order_partial_filled"  # Partial fill
    ORDER_CANCELLED = "order_cancelled"      # Order cancelled
    
    # TP Management
    TP_PLACED = "tp_placed"                  # TP order placed
    TP_RETRY_SCHEDULED = "tp_retry_scheduled"  # TP placement failed, retry scheduled
    TP_RETRY_SUCCEEDED = "tp_retry_succeeded"  # TP retry succeeded
    TP_RETRY_EXHAUSTED = "tp_retry_exhausted"  # TP retry failed permanently
    
    # System Events
    BOT_STARTED = "bot_started"              # Bot startup
    BOT_STOPPED = "bot_stopped"              # Bot shutdown
    STATE_RECONCILED = "state_reconciled"    # Exchange reconciliation
```

**Event Structure**:
```python
@dataclass
class Event:
    event_id: str          # UUID v4
    event_type: EventType
    timestamp: float       # time.time() (Unix timestamp)
    correlation_id: str    # Links related events (fill → position → TP)
    aggregate_id: str      # Position ID or Order ID
    data: dict            # Event-specific payload
    metadata: dict        # Bot version, environment, session, etc.
```

**Example Event Payloads**:

```python
# POSITION_OPENED Event
{
    "event_id": "550e8400-e29b-41d4-a716-446655440000",
    "event_type": "position_opened",
    "timestamp": 1699564800.123,
    "correlation_id": "fill-12345678-1699564800000",
    "aggregate_id": "pos_1699564800_65000",
    "data": {
        "position_id": "pos_1699564800_65000",
        "entry_price": 65000.0,
        "tp_price": 66000.0,
        "size": 1,
        "side": "long",
        "fill_order_id": "12345678",
        "grid_aligned": True
    },
    "metadata": {
        "bot_version": "2.0",
        "session_tag": "GBOT_1699564800",
        "grid_mode": "LONG",
        "environment": "production"
    }
}

# ORDER_PLACED Event
{
    "event_id": "660e8400-e29b-41d4-a716-446655440001",
    "event_type": "order_placed",
    "timestamp": 1699564800.456,
    "correlation_id": "fill-12345678-1699564800000",
    "aggregate_id": "87654321",
    "data": {
        "order_id": "87654321",
        "side": "buy",
        "price": 64000.0,
        "size": 1,
        "order_type": "limit",
        "post_only": True,
        "client_order_id": "BOT-BUY-1699564800-xyz"
    },
    "metadata": {
        "bot_version": "2.0",
        "placed_after_fill": "12345678",
        "grid_level": 64000.0
    }
}
```

**Testing**: Create unit tests for event serialization/deserialization

---

#### Deliverable 1.2: SQLite Event Store Implementation

**File**: `bot/strategy/modules/event_store.py`

**Database Schema**:
```sql
CREATE TABLE IF NOT EXISTS events (
    -- Primary Key
    event_id TEXT PRIMARY KEY,
    
    -- Event Metadata
    event_type TEXT NOT NULL,
    timestamp REAL NOT NULL,
    correlation_id TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    
    -- Event Data (JSON)
    data TEXT NOT NULL,
    metadata TEXT NOT NULL,
    
    -- Audit Fields
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes for fast queries
    INDEX idx_timestamp (timestamp),
    INDEX idx_correlation (correlation_id),
    INDEX idx_aggregate (aggregate_id),
    INDEX idx_event_type (event_type)
);

-- Sequence tracking for snapshots
CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    last_event_id TEXT NOT NULL,
    state_json TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Implementation**:

```python
class EventStore:
    def __init__(self, db_path="bot_events.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database with WAL mode for concurrent access"""
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
            conn.execute("PRAGMA synchronous=NORMAL")  # Balance safety/performance
            # Create tables (schema above)
    
    @contextmanager
    def _connection(self):
        """Context manager for database connections with transaction support"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Access columns by name
        try:
            yield conn
            conn.commit()  # Auto-commit on success
        except Exception:
            conn.rollback()  # Auto-rollback on error
            raise
        finally:
            conn.close()
    
    def append_event(self, event: Event) -> None:
        """
        Append event to log (NEVER updates, only appends)
        
        This is the ONLY way to modify the event log.
        Events are immutable once written.
        """
        with self._connection() as conn:
            conn.execute("""
                INSERT INTO events (
                    event_id, event_type, timestamp, correlation_id, 
                    aggregate_id, data, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id,
                event.event_type.value,
                event.timestamp,
                event.correlation_id,
                event.aggregate_id,
                json.dumps(event.data),
                json.dumps(event.metadata)
            ))
    
    def get_events_since(self, timestamp: float) -> list[Event]:
        """Fetch events after timestamp (for replay)"""
        with self._connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM events 
                WHERE timestamp > ? 
                ORDER BY timestamp ASC
            """, (timestamp,))
            return [self._row_to_event(row) for row in cursor.fetchall()]
    
    def get_events_by_correlation(self, correlation_id: str) -> list[Event]:
        """Fetch all events in a transaction (for debugging)"""
        with self._connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM events 
                WHERE correlation_id = ? 
                ORDER BY timestamp ASC
            """, (correlation_id,))
            return [self._row_to_event(row) for row in cursor.fetchall()]
    
    def get_events_by_aggregate(self, aggregate_id: str) -> list[Event]:
        """Fetch all events for a specific aggregate (position/order)"""
        with self._connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM events 
                WHERE aggregate_id = ? 
                ORDER BY timestamp ASC
            """, (aggregate_id,))
            return [self._row_to_event(row) for row in cursor.fetchall()]
```

**Testing**:
1. Concurrent write test (multiple threads appending events)
2. Crash recovery test (kill process mid-write, verify no corruption)
3. Performance test (append 10,000 events, measure latency)
4. Query performance test (query by timestamp, correlation ID, aggregate ID)

**Target Performance**:
- Append latency: <5ms (p99)
- Query latency: <10ms (p99)
- Concurrent writers: 3+ threads
- Database size: <100MB per 1M events

---

### Week 3-4: State Projection Engine

#### Deliverable 1.3: Event Replay to Rebuild State

**File**: `bot/strategy/modules/state_projector.py` (NEW)

**Purpose**: Rebuild current state from event log

**Implementation**:

```python
class StateProjector:
    """
    Rebuilds current state from event log
    
    This is a PURE FUNCTION - given events, produces state.
    No side effects, no I/O (except reading from event store).
    """
    
    def __init__(self, event_store: EventStore):
        self.event_store = event_store
    
    def project_current_state(self, until_timestamp: Optional[float] = None) -> dict:
        """
        Replay all events to build current state
        
        Args:
            until_timestamp: If provided, build state as of this timestamp (time travel)
        
        Returns:
            Complete bot state dict
        """
        # Initialize empty state
        state = {
            "open_tranches": [],
            "pending_buy": None,
            "pending_sell": None,
            "last_buy_order_time": 0,
            "last_sell_order_time": 0,
            "tp_retry_queue": [],
            "session_tag": None,
            "bot_started_at": None
        }
        
        # Fetch events (optionally until timestamp for time travel)
        if until_timestamp:
            events = self.event_store.get_events_since(0)
            events = [e for e in events if e.timestamp <= until_timestamp]
        else:
            events = self.event_store.get_events_since(0)
        
        # Replay events to build state
        for event in events:
            state = self._apply_event(state, event)
        
        return state
    
    def _apply_event(self, state: dict, event: Event) -> dict:
        """
        Apply single event to state (pure function)
        
        This is the HEART of event sourcing - defines how events change state.
        """
        if event.event_type == EventType.POSITION_OPENED:
            # Add position to open_tranches
            state["open_tranches"].append(event.data)
        
        elif event.event_type == EventType.POSITION_CLOSED:
            # Remove position by aggregate_id
            state["open_tranches"] = [
                p for p in state["open_tranches"] 
                if p["position_id"] != event.aggregate_id
            ]
        
        elif event.event_type == EventType.ORDER_PLACED:
            # Track pending order
            if event.data["side"] == "buy":
                state["pending_buy"] = event.data
                state["last_buy_order_time"] = event.timestamp
            else:
                state["pending_sell"] = event.data
                state["last_sell_order_time"] = event.timestamp
        
        elif event.event_type == EventType.ORDER_FILLED:
            # Clear pending order
            if event.data["side"] == "buy":
                state["pending_buy"] = None
            else:
                state["pending_sell"] = None
        
        elif event.event_type == EventType.TP_PLACED:
            # Update position with TP order ID
            for pos in state["open_tranches"]:
                if pos["position_id"] == event.aggregate_id:
                    pos["tp_order_id"] = event.data["order_id"]
                    pos["tp_price"] = event.data["price"]
                    break
        
        elif event.event_type == EventType.TP_RETRY_SCHEDULED:
            # Add to retry queue
            state["tp_retry_queue"].append({
                "position_id": event.aggregate_id,
                "attempts": event.data["attempts"],
                "next_retry": event.data["next_retry"]
            })
        
        elif event.event_type == EventType.BOT_STARTED:
            state["session_tag"] = event.data["session_tag"]
            state["bot_started_at"] = event.timestamp
        
        # More event types...
        
        return state
```

**Testing Strategy**:
1. **Unit tests**: Test each event type application
2. **Integration tests**: Record 100 events, rebuild state, compare with in-memory state
3. **Property tests**: Replaying same events always produces same state
4. **Time travel tests**: Rebuild state at T-1hour, T-1day, verify accuracy

**Test Coverage Target**: >95%

---

### Week 5-6: Migration & Dual Write

#### Deliverable 1.4: Hybrid State Management (Transition Period)

**File**: `bot/strategy/modules/position_manager.py` (MODIFIED)

**Strategy**: Dual write to both event store AND JSON files during transition

**Implementation**:

```python
class PositionManager:
    def __init__(
        self,
        max_open: int,
        grid_calculator: Any = None,
        session_tag: str = "",
        event_store: Optional[EventStore] = None,  # NEW
        legacy_mode: bool = True  # NEW: Gradual migration flag
    ):
        self._state_lock = threading.Lock()
        self.event_store = event_store
        self.legacy_mode = legacy_mode
        
        # Existing state
        self.open_tranches = []
        self.pending_buy = None
        # ...
    
    def add_position(self, position: Dict[str, Any], correlation_id: str) -> None:
        """
        Add new position with event sourcing
        
        NEW: Dual write during migration
        - Write to event store (new)
        - Write to JSON file (legacy, for safety)
        """
        with self._state_lock:
            # DUAL WRITE #1: Update in-memory state (existing)
            self.open_tranches.append(position)
            
            # DUAL WRITE #2: Append event (NEW)
            if self.event_store:
                event = Event(
                    event_id=str(uuid.uuid4()),
                    event_type=EventType.POSITION_OPENED,
                    timestamp=time.time(),
                    correlation_id=correlation_id,
                    aggregate_id=position["position_id"],
                    data=position,
                    metadata={
                        "bot_version": "2.0",
                        "mode": self.grid_mode,
                        "session_tag": self.session_tag
                    }
                )
                self.event_store.append_event(event)
                log.debug(f"✅ Event appended: POSITION_OPENED (ID: {event.event_id})")
            
            # DUAL WRITE #3: Legacy persistence (for backward compatibility)
            if self.legacy_mode:
                self.persist_runtime_state(force=True)
                log.debug(f"✅ Legacy JSON persisted (dual write mode)")
```

**Migration Path**:

**Week 5**:
- ✅ Implement dual write in staging
- ✅ Run for 1 week with both systems active
- ✅ Compare event-sourced state with JSON state every hour
- ✅ Alert on any discrepancies

**Week 6**:
- ✅ Verify 100% consistency between event store and JSON
- ✅ Deploy to production with dual write
- ✅ Monitor for 1 week
- ✅ Prepare to disable legacy JSON (Phase 2)

**Rollback Safety**:
- Legacy JSON still written → Can rollback to Phase 0 anytime
- Event store is additive → No data loss if we revert
- Both systems independent → Failure in one doesn't affect the other

---

## Testing Plan

### Unit Tests

**Target**: `bot/strategy/modules/test_event_store.py`

```python
def test_event_append():
    """Test single event append"""
    store = EventStore(":memory:")  # In-memory DB for tests
    event = Event(...)
    store.append_event(event)
    retrieved = store.get_events_since(0)
    assert len(retrieved) == 1
    assert retrieved[0].event_id == event.event_id

def test_event_replay():
    """Test state reconstruction from events"""
    store = EventStore(":memory:")
    # Append 100 events
    for i in range(100):
        store.append_event(create_test_event(i))
    
    # Rebuild state
    projector = StateProjector(store)
    state = projector.project_current_state()
    
    # Verify state matches expected
    assert len(state["open_tranches"]) == expected_count

def test_concurrent_writes():
    """Test multiple threads appending events"""
    store = EventStore(":memory:")
    threads = []
    for i in range(10):
        t = threading.Thread(target=lambda: store.append_event(create_test_event(i)))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    # Verify all events written
    events = store.get_events_since(0)
    assert len(events) == 10
```

### Integration Tests

**Target**: `tests/integration/test_event_sourcing.py`

```python
def test_crash_recovery_with_events():
    """Test bot crash recovery using event store"""
    # 1. Start bot, place orders, create positions
    bot = create_test_bot(use_event_store=True)
    bot.run(duration_seconds=60)
    
    # 2. Force crash (kill process)
    bot._shutdown_requested = True
    
    # 3. Restart bot
    bot2 = create_test_bot(use_event_store=True)
    
    # 4. Verify state recovered from events
    assert len(bot2.position_mgr.open_tranches) == len(bot.position_mgr.open_tranches)

def test_dual_write_consistency():
    """Test event store and JSON produce same state"""
    bot = create_test_bot(use_event_store=True, legacy_mode=True)
    bot.run(duration_seconds=3600)  # 1 hour
    
    # Compare state from events vs JSON
    event_state = bot.projector.project_current_state()
    json_state = bot.position_mgr.load_runtime_state()
    
    assert event_state == json_state
```

### Performance Tests

**Target**: `tests/performance/test_event_store_perf.py`

```python
def test_append_latency():
    """Measure event append latency"""
    store = EventStore("test_perf.db")
    latencies = []
    
    for i in range(10000):
        start = time.time()
        store.append_event(create_test_event(i))
        latencies.append(time.time() - start)
    
    p50 = np.percentile(latencies, 50)
    p99 = np.percentile(latencies, 99)
    
    assert p50 < 0.003  # 3ms
    assert p99 < 0.005  # 5ms

def test_replay_performance():
    """Measure state reconstruction time"""
    store = EventStore("test_perf.db")
    # Append 100k events
    for i in range(100000):
        store.append_event(create_test_event(i))
    
    projector = StateProjector(store)
    start = time.time()
    state = projector.project_current_state()
    duration = time.time() - start
    
    assert duration < 5.0  # 5 seconds for 100k events
```

---

## Risk Management

### Risk Matrix

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **SQLite corruption** | LOW | HIGH | WAL mode + checksums + backups |
| **Event schema changes** | MEDIUM | MEDIUM | Versioned events + migration scripts |
| **Performance degradation** | LOW | MEDIUM | Benchmark before/after + rollback plan |
| **Dual write inconsistency** | MEDIUM | HIGH | Automated comparison tests + alerts |
| **Disk space exhaustion** | LOW | HIGH | Monitor DB size + retention policy |

### Contingency Plans

**If SQLite corrupts**:
1. Restore from JSON backup (legacy mode still active)
2. Investigate corruption cause
3. Implement additional checksums/validation

**If performance degrades**:
1. Add indexes to slow queries
2. Implement snapshot optimization (cache state every N events)
3. Rollback to JSON-only mode

**If dual write diverges**:
1. Pause trading immediately
2. Compare states line-by-line
3. Fix bug in event application logic
4. Replay events to correct state

---

## Success Criteria

### Phase 1 Complete When:

✅ **Event Store Operational**:
- SQLite database created with WAL mode
- All event types defined and tested
- Append latency <5ms (p99)

✅ **State Projection Working**:
- Can rebuild state from events
- 100% accuracy (matches in-memory state)
- Replay 100k events in <5 seconds

✅ **Dual Write Validated**:
- Both systems active in staging for 1 week
- Zero discrepancies detected
- Rollback tested and verified

✅ **Production Deployed**:
- Dual write active in production
- Monitoring dashboard showing event metrics
- Zero corruption incidents

### Metrics to Track

| Metric | Target | Current (Phase 0) |
|--------|--------|-------------------|
| State persistence latency | <5ms (p99) | <100ms (p99) |
| Data loss on crash | 0 events | 0-15s of data |
| Audit trail coverage | 100% operations | 0% |
| Recovery time objective (RTO) | <30 seconds | <5 minutes |
| Recovery point objective (RPO) | 0 data loss | Up to 15s loss |

---

## Next Steps After Phase 1

Once Phase 1 is complete (event store proven in production):

1. **Week 7-8**: Disable legacy JSON persistence (event-only mode)
2. **Week 7-14**: Implement Phase 2 (Async Architecture Migration)
3. **Add event-driven features**:
   - Real-time dashboard (subscribe to events)
   - Audit log viewer (query historical events)
   - Replay mode (test strategies on historical data)

---

## Resources Required

### Development Time
- Senior Engineer: 4-6 weeks full-time
- QA Engineer: 2 weeks (testing + validation)
- DevOps Engineer: 1 week (monitoring + deployment)

### Infrastructure
- SQLite (included in Python, no additional cost)
- Disk space: ~100MB per 1M events (~1GB per 10M events)
- No additional servers (runs on existing bot machine)

### Documentation
- Event schema documentation
- Migration guide (Phase 0 → Phase 1)
- Troubleshooting guide (SQLite corruption, performance issues)
- Monitoring playbook (alerts, dashboards)

---

**Phase 1 Status**: 📋 **PLANNING COMPLETE**  
**Ready for**: Implementation (Week 1 starts after Phase 0 deployed)  
**Estimated Completion**: 4-6 weeks from start

---

**End of Phase 1 Planning Document**
