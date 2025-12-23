# Phase 1: Event Sourcing State Management - Complete Implementation Prompt

**Date**: November 11, 2025  
**Target AI**: Claude Opus 4.1  
**Goal**: Single-shot complete implementation of Phase 1 Event Sourcing  
**Estimated Output**: ~1000-1200 lines of production-ready code

---

## Context

You are implementing Phase 1 of a 6-phase architectural upgrade for a production cryptocurrency trading bot (GridBot). The bot currently uses JSON file-based state management with a 15-second persistence gap, causing potential data loss on crashes.

### Current System
- **Language**: Python 3.9+
- **Architecture**: Threaded (threading.RLock for state management)
- **State Storage**: JSON files (`runtime_state.json`)
- **Trading Exchange**: Delta Exchange (derivatives)
- **State**: Positions, pending orders, order timestamps
- **Critical Path**: Fill detection → Position management → TP placement → Next grid order

### Phase 0 Status: ✅ COMPLETE
- Fill queue increased to 1000
- Lock logging added
- Force persistence implemented
- Unknown order ID handling upgraded

---

## Objective

Implement a complete Event Sourcing system with SQLite that:

1. ✅ Provides ACID guarantees (zero data loss)
2. ✅ Maintains full audit trail (every state change logged)
3. ✅ Enables crash recovery (rebuild state from events)
4. ✅ Supports dual-write mode (events + legacy JSON for safety)
5. ✅ Has zero production downtime during migration

---

## Deliverables (Create 3 New Files + Tests)

### File 1: `bot/strategy/modules/event_store.py` (NEW)

**Requirements:**

#### 1. Event Schema (dataclasses)

```python
class EventType(Enum):
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    TP_PLACED = "tp_placed"
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"

@dataclass
class Event:
    event_id: str          # UUID
    event_type: EventType
    timestamp: float       # time.time()
    correlation_id: str    # Links related events
    aggregate_id: str      # Position ID or Order ID
    data: dict            # Event-specific payload
    metadata: dict        # Bot version, environment, etc.
```

#### 2. EventStore Class

**Methods Required:**
- `__init__(db_path: str)` - Initialize database, create tables
- `append_event(event: Event) -> None` - Append event (NEVER updates, only appends)
- `get_events_since(timestamp: float) -> list[Event]` - For replay
- `get_events_by_correlation(correlation_id: str) -> list[Event]` - Related events
- `get_events_by_aggregate(aggregate_id: str) -> list[Event]` - Entity history
- `_row_to_event(row: tuple) -> Event` - Deserialize from DB row
- `_connection()` - Context manager for DB connections

#### 3. Technical Requirements

**SQLite Configuration:**
- `PRAGMA journal_mode=WAL` - Write-Ahead Logging for concurrent reads
- `PRAGMA synchronous=NORMAL` - Performance optimization (safe with WAL)
- Connection pooling via context manager

**Database Schema:**
```sql
CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    timestamp REAL NOT NULL,
    correlation_id TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    data TEXT NOT NULL,  -- JSON
    metadata TEXT NOT NULL,  -- JSON
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

**Indexes:**
- `idx_timestamp` on `timestamp` (for time-range queries)
- `idx_correlation` on `correlation_id` (for transaction tracking)
- `idx_aggregate` on `aggregate_id` (for entity history)

**Error Handling:**
- Use `contextlib.contextmanager` for safe connections
- Rollback on any exception
- Proper connection cleanup in finally block

---

### File 2: `bot/strategy/modules/state_projector.py` (NEW)

**Requirements:**

#### 1. StateProjector Class

**Constructor:**
- Takes `EventStore` instance

**Methods:**
- `project_current_state() -> dict` - Rebuild state from ALL events
- `project_state_at(timestamp: float) -> dict` - Time-travel to specific point

#### 2. Event Handling Logic

**State Structure to Rebuild:**
```python
{
    "open_tranches": [],        # List of position dicts
    "pending_buy": None,         # Order dict or None
    "pending_sell": None,        # Order dict or None
    "last_buy_order_time": 0,   # float timestamp
    "last_sell_order_time": 0,  # float timestamp
    "tp_orders": {}             # Dict[position_id, order_id]
}
```

**Event Processing:**

| Event Type | Action |
|------------|--------|
| `POSITION_OPENED` | Append to `open_tranches` |
| `POSITION_CLOSED` | Remove from `open_tranches` by `aggregate_id` |
| `ORDER_PLACED` | Update `pending_buy/sell` + timestamps based on side |
| `ORDER_FILLED` | Clear `pending_buy/sell` based on side |
| `TP_PLACED` | Store in `tp_orders[position_id] = order_id` |
| `ORDER_CANCELLED` | Clean up cancelled orders |

#### 3. Edge Cases to Handle

- **Empty event log**: Return clean state
- **Duplicate events**: Idempotent processing (same event twice = same result)
- **Out-of-order events**: Sort by timestamp before replay
- **Corrupted event data**: Skip with warning, continue processing

---

### File 3: `tests/test_event_sourcing.py` (NEW)

**Requirements:**

#### 1. Unit Tests for EventStore (pytest)

**Test Coverage:**
- `test_event_store_initialization` - DB created, tables exist, indexes exist
- `test_append_and_retrieve_event` - Write event, read it back, verify data
- `test_get_events_since` - Append 10 events, query from middle, verify order
- `test_get_events_by_correlation` - Multiple events with same correlation_id
- `test_concurrent_writes` - 100 threads append events, verify all persisted
- `test_wal_mode_enabled` - Check `PRAGMA journal_mode` returns 'wal'
- `test_rollback_on_error` - Force error during append, verify rollback

#### 2. Unit Tests for StateProjector

**Test Coverage:**
- `test_project_empty_state` - No events → clean state
- `test_project_with_positions` - `POSITION_OPENED` events → `open_tranches` populated
- `test_project_with_order_lifecycle` - `ORDER_PLACED` → `ORDER_FILLED` → pending cleared
- `test_time_travel` - Append events at different timestamps, project at T-5min
- `test_idempotency` - Process same event twice, verify state unchanged

#### 3. Integration Tests

**Test Coverage:**
- `test_crash_recovery_simulation`:
  - Append 50 events (positions, orders, fills)
  - Create new EventStore instance (simulate restart)
  - Project state, verify matches expected
- `test_dual_write_compatibility`:
  - Write events AND JSON
  - Compare projected state vs JSON state
  - Verify 100% match

#### 4. Performance Tests

**Test Coverage:**
- `test_append_latency` - Measure p50/p99 latency for 1000 appends (target: <5ms p99)
- `test_replay_performance` - 10k events, measure projection time (target: <1s)

---

### File 4: Integration Code (MODIFY EXISTING)

**File:** `bot/strategy/modules/position_manager.py`

#### Modifications Needed:

**1. Add imports:**
```python
from bot.strategy.modules.event_store import EventStore, Event, EventType
import uuid
```

**2. Update `__init__`:**
```python
def __init__(self, grid_calc, mode="LONG", event_store: EventStore = None, legacy_mode=True):
    # Existing initialization...
    
    # ✅ PHASE 1: Event sourcing
    self.event_store = event_store or EventStore("bot_events.db")
    self.legacy_mode = legacy_mode  # Dual-write flag
    self.mode = mode
```

**3. Update `add_position` method:**
```python
def add_position(self, position: Dict[str, Any], correlation_id: str = None) -> None:
    with self._state_lock:
        # Existing logic: append to open_tranches
        self.open_tranches.append(position)
        
        # ✅ PHASE 1: Append event
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.POSITION_OPENED,
            timestamp=time.time(),
            correlation_id=correlation_id,
            aggregate_id=position.get("position_id", str(uuid.uuid4())),
            data=position,
            metadata={"bot_version": "2.0", "mode": self.mode}
        )
        self.event_store.append_event(event)
        
        # ✅ PHASE 1: Dual write (legacy persistence for safety)
        if self.legacy_mode:
            self.persist_runtime_state(force=True)
        
        log.info(f"✅ Position added + event logged: {position.get('entry_price')}")
```

**4. Add similar event logging to:**
- `remove_position()` → `POSITION_CLOSED` event
- `set_pending_buy()` → `ORDER_PLACED` event
- `clear_pending_buy()` → `ORDER_FILLED` event

---

## Technical Constraints

1. **Python Version**: 3.9+ (support type hints with `list[Event]`)
2. **SQLite Version**: 3.7.0+ (for WAL mode)
3. **Thread Safety**: EventStore must be thread-safe (use connection per operation)
4. **Backward Compatibility**: Must NOT break existing JSON-based state management
5. **Performance**: Event append < 5ms p99, replay 10k events < 1s
6. **Disk Space**: Estimate 100 bytes per event, 1MB per 10k events

---

## Success Criteria

After implementation, the system must:

1. ✅ Pass all 15+ unit tests
2. ✅ Pass crash recovery test (100 simulations)
3. ✅ Dual-write mode: Event log matches JSON state (1 week test)
4. ✅ Performance: <5ms event append latency (p99)
5. ✅ Zero production errors during staging deployment

---

## File Structure After Implementation

```
bot/
├── strategy/
│   └── modules/
│       ├── event_store.py          ← NEW (Event, EventType, EventStore)
│       ├── state_projector.py      ← NEW (StateProjector)
│       └── position_manager.py     ← MODIFIED (dual-write integration)
tests/
└── test_event_sourcing.py          ← NEW (15+ tests)
```

---

## Implementation Order

1. **Start with event_store.py** (foundation)
2. **Then state_projector.py** (depends on EventStore)
3. **Write comprehensive tests** (ensure correctness before integration)
4. **Finally integrate into position_manager.py** (minimal changes)

---

## Code Quality Requirements

- ✅ Type hints for all function signatures
- ✅ Docstrings for all classes and public methods
- ✅ Comprehensive error handling (try/except with specific exceptions)
- ✅ Logging at INFO level for key operations
- ✅ Use `logging.getLogger("event_store")` for module logger
- ✅ **NO placeholder comments** like `# TODO` or `# ... rest of implementation`

---

## Example Event Data Payloads

### POSITION_OPENED
```python
{
    "position_id": "pos_abc123",
    "entry_price": 65000.0,
    "tp_price": 66000.0,
    "size": 1,
    "mode": "LONG",
    "created_at": 1699564800.123
}
```

### ORDER_PLACED
```python
{
    "order_id": "ord_xyz789",
    "side": "buy",
    "price": 64000.0,
    "size": 1,
    "order_type": "limit_order"
}
```

### ORDER_FILLED
```python
{
    "order_id": "ord_xyz789",
    "side": "buy",
    "fill_price": 64000.0,
    "fill_size": 1,
    "cumulative_filled": 1
}
```

### POSITION_CLOSED
```python
{
    "position_id": "pos_abc123",
    "exit_price": 66000.0,
    "pnl": 1000.0,
    "close_reason": "TP_HIT"
}
```

---

## Rollback Strategy (If Issues Found)

1. Set `legacy_mode=True` in all instances (default)
2. Event log continues to write (for audit), but state reads from JSON
3. Monitor for 48 hours, compare event log vs JSON (should match)
4. If discrepancies found, fix projection logic, replay events

---

## Output Format

Provide **complete, production-ready code** for all 4 files with:

- ✅ Full implementations (no placeholder comments)
- ✅ Comprehensive error handling
- ✅ Logging statements
- ✅ Type hints
- ✅ Docstrings
- ✅ All 15+ tests implemented
- ✅ Complete `_row_to_event` method
- ✅ Complete position_manager.py modifications

---

## Critical: No Placeholders

**DO NOT** include comments like:
- `# TODO: Implement this`
- `# ... rest of the implementation`
- `# Add more tests here`
- `# Implement other event types`

**PROVIDE COMPLETE CODE** for every method, every test, every feature specified above.

---

## Ready to Execute

Generate the complete implementation now. Include all 4 files with full code.
