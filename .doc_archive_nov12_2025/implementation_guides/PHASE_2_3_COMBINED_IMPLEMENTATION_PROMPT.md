# Phase 2 + 3 Combined Implementation Prompt for Claude Opus 4.1

**Target**: Complete Phases 2 & 3 in ONE single-shot implementation  
**Estimated Scope**: ~3500-4000 lines of new code  
**Timeline**: 6-8 weeks work → 1 AI session  
**Cost Optimization**: Combine 2 phases to save API costs

---

## CONTEXT: Current System State

### What's Already Working (Phase 0 + 1)
- ✅ **Event Sourcing**: SQLite event store with WAL mode (`bot/strategy/modules/event_store.py`)
- ✅ **State Projection**: Rebuild state from events (`bot/strategy/modules/state_projector.py`)
- ✅ **Dual-Write**: Events + JSON persistence active
- ✅ **19 Tests Passing**: Complete test coverage for event sourcing
- ✅ **Production Stable**: Bot running with event logging

### Current Architecture (Threading Model - TO BE REPLACED)
```python
# CURRENT: Multiple threads with locks
Main Thread
├─ WebSocket Thread (blocking I/O)
├─ Fill Queue Worker Thread
├─ Heartbeat Thread (periodic tasks)
└─ REST Fallback Thread (conditional)

# Synchronization: threading.Lock, threading.RLock
# State Access: Requires lock acquisition
# Concurrency Issues: Deadlock risk, race conditions
```

### Target Architecture (Async + Actor Model + Saga Pattern)
```python
# PHASE 2+3: Single event loop with actors and sagas
Single Event Loop (asyncio)
├─ Async WebSocket (non-blocking)
├─ Async REST API (non-blocking)
├─ Actor System (message passing)
│   ├─ PositionManagerActor (mailbox queue)
│   ├─ OrderManagerActor (mailbox queue)
│   └─ MonitoringActor (mailbox queue)
├─ Saga Coordinator (transaction boundaries)
│   ├─ Fill Processing Saga (compensating transactions)
│   └─ Position Closing Saga (rollback on failure)
└─ Async Periodic Tasks (no threads)

# Synchronization: NONE (single-threaded actors)
# State Access: Message passing only
# Concurrency: Zero locks, zero deadlocks
```

---

## YOUR MISSION

Implement **Phase 2 (Async Architecture)** AND **Phase 3 (Saga Pattern)** together in a SINGLE, production-ready implementation.

### Phase 2 Goals (Async Migration)
1. Replace all threading with `asyncio`
2. Implement Actor Model for state management (zero locks)
3. Convert REST API client to async (`httpx`)
4. Convert WebSocket manager to async (`websockets`)
5. Migrate all blocking I/O to async

### Phase 3 Goals (Saga Pattern)
1. Implement Saga Coordinator for transaction boundaries
2. Add compensating transactions for rollback
3. Create Fill Processing Saga (position → TP → grid order)
4. Add Position Closing Saga (TP fill → close position → place buy)
5. Implement chaos testing for compensation logic

### Combined Benefits
- **No more deadlocks** (actor model = zero locks)
- **Transactional safety** (saga pattern = rollback on failure)
- **Better performance** (-30% CPU, -40% memory)
- **Simpler code** (-3000 lines, -80% complexity)

---

## DELIVERABLES

### 1. Async REST API Client (NEW FILE)
**File**: `bot/api/async_delta_client.py`

**Requirements**:
- Use `httpx.AsyncClient` for all HTTP calls
- Connection pooling with limits (max 10 connections)
- Automatic retry with exponential backoff (3 retries, 1s/2s/4s)
- Timeout handling (10s default)
- Signature generation for Delta Exchange auth
- Context manager support (`async with`)

**Methods to Implement**:
```python
class AsyncDeltaClient:
    async def place_order(symbol, side, price, size) -> dict
    async def cancel_order(order_id) -> dict
    async def get_open_orders(symbol) -> list[dict]
    async def get_positions(symbol) -> list[dict]
    async def get_ticker(symbol) -> dict
    async def get_orderbook(symbol, depth=10) -> dict
```

**Error Handling**:
- `httpx.TimeoutException` → Retry with backoff
- `httpx.HTTPStatusError` (4xx) → Raise immediately (don't retry)
- `httpx.HTTPStatusError` (5xx) → Retry with backoff
- Network errors → Circuit breaker pattern

---

### 2. Async WebSocket Manager (NEW FILE)
**File**: `bot/delta_websocket/async_ws_manager.py`

**Requirements**:
- Use `websockets` library for connection
- Automatic reconnection with exponential backoff
- Subscription management (maintain subscriptions across reconnects)
- Message routing to handlers (async callbacks)
- Heartbeat monitoring (Delta sends heartbeat every 30s)
- Graceful shutdown on SIGINT/SIGTERM

**Channels to Subscribe**:
- `v2/user_trades` (fills)
- `orders` (order updates)
- `positions` (position updates)
- `margins` (margin updates)
- `v2/ticker` (price updates)
- `l2_orderbook` (orderbook snapshots)

**Methods to Implement**:
```python
class AsyncWebSocketManager:
    async def connect() -> None
    async def disconnect() -> None
    async def subscribe(channel, symbols) -> None
    async def _message_loop() -> AsyncIterator[dict]
    async def _handle_heartbeat() -> None
    def register_handler(msg_type, callback) -> None
```

---

### 3. Actor System (NEW FILE)
**File**: `bot/strategy/actors/base_actor.py`

**Requirements**:
- Base `Actor` class with mailbox (`asyncio.Queue`)
- Message dataclass with type, payload, reply channel
- Automatic message dispatching to handler methods
- Graceful shutdown (process remaining messages)
- Error handling (log errors, continue processing)

**Actor Base Class**:
```python
@dataclass
class Message:
    type: str
    payload: dict
    reply_to: Optional[asyncio.Queue] = None
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))

class Actor:
    def __init__(self, name: str):
        self.name = name
        self.mailbox = asyncio.Queue()
        self._running = False
    
    async def start(self):
        """Start actor message loop"""
        self._running = True
        while self._running:
            msg = await self.mailbox.get()
            await self._handle_message(msg)
    
    async def _handle_message(self, msg: Message):
        """Route message to handler method"""
        handler_name = f"_handle_{msg.type.lower()}"
        if handler := getattr(self, handler_name, None):
            await handler(msg.payload, msg.reply_to, msg.correlation_id)
        else:
            log.warning(f"No handler for message type: {msg.type}")
    
    async def stop(self):
        """Graceful shutdown"""
        self._running = False
```

---

### 4. PositionManagerActor (NEW FILE)
**File**: `bot/strategy/actors/position_actor.py`

**Requirements**:
- Inherits from `Actor`
- Manages `open_tranches`, `pending_buy`, `pending_sell` state
- Single-threaded (NO LOCKS NEEDED)
- Logs events to EventStore on state changes
- Handles messages: `ADD_POSITION`, `REMOVE_POSITION`, `GET_STATE`, `SET_PENDING_BUY`, `CLEAR_PENDING_BUY`, etc.

**State Management**:
```python
class PositionManagerActor(Actor):
    def __init__(self, event_store: EventStore):
        super().__init__("PositionManager")
        self.event_store = event_store
        self.state = {
            "open_tranches": [],
            "pending_buy": None,
            "pending_sell": None,
            "last_buy_order_time": 0,
            "last_sell_order_time": 0
        }
    
    async def _handle_add_position(self, payload, reply_to, correlation_id):
        """Add position (no lock needed - single threaded)"""
        position = payload
        self.state["open_tranches"].append(position)
        
        # Log event
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=EventType.POSITION_OPENED,
            timestamp=time.time(),
            correlation_id=correlation_id,
            aggregate_id=position["position_id"],
            data=position,
            metadata={"actor": self.name}
        )
        self.event_store.append_event(event)
        
        if reply_to:
            await reply_to.put({"status": "ok", "position_id": position["position_id"]})
    
    async def _handle_get_state(self, payload, reply_to, correlation_id):
        """Get current state (read-only, no lock needed)"""
        if reply_to:
            await reply_to.put(self.state.copy())
```

**Message Handlers to Implement**:
- `_handle_add_position`
- `_handle_remove_position`
- `_handle_set_pending_buy`
- `_handle_clear_pending_buy`
- `_handle_set_pending_sell`
- `_handle_clear_pending_sell`
- `_handle_get_state`
- `_handle_get_open_positions`

---

### 5. OrderManagerActor (NEW FILE)
**File**: `bot/strategy/actors/order_actor.py`

**Requirements**:
- Inherits from `Actor`
- Uses `AsyncDeltaClient` for order placement
- Handles messages: `PLACE_BUY`, `PLACE_SELL`, `PLACE_TP`, `CANCEL_ORDER`
- Logs all order events to EventStore
- Implements retry logic (3 retries with backoff)
- Validates orders before placement (price, size, capacity)

**Order Placement Logic**:
```python
class OrderManagerActor(Actor):
    def __init__(self, api_client: AsyncDeltaClient, event_store: EventStore):
        super().__init__("OrderManager")
        self.api_client = api_client
        self.event_store = event_store
    
    async def _handle_place_buy(self, payload, reply_to, correlation_id):
        """Place BUY order with retry"""
        price = payload["price"]
        size = payload["size"]
        
        for attempt in range(3):
            try:
                result = await self.api_client.place_order(
                    symbol="BTCUSD",
                    side="buy",
                    price=price,
                    size=size
                )
                
                # Log event
                event = Event(
                    event_id=str(uuid.uuid4()),
                    event_type=EventType.ORDER_PLACED,
                    timestamp=time.time(),
                    correlation_id=correlation_id,
                    aggregate_id=result["order_id"],
                    data={"side": "buy", "price": price, "size": size, "order_id": result["order_id"]},
                    metadata={"actor": self.name, "attempt": attempt + 1}
                )
                self.event_store.append_event(event)
                
                if reply_to:
                    await reply_to.put({"status": "ok", "order_id": result["order_id"]})
                return
            
            except Exception as e:
                log.error(f"Order placement failed (attempt {attempt + 1}): {e}")
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s
                else:
                    if reply_to:
                        await reply_to.put({"status": "error", "error": str(e)})
```

---

### 6. Saga Coordinator (NEW FILE)
**File**: `bot/strategy/sagas/saga_coordinator.py`

**Requirements**:
- Define `SagaStep` dataclass (action + compensation)
- Implement `Saga` class with step execution and rollback
- Log all saga events to EventStore
- Handle partial failures with automatic compensation
- Support nested sagas (saga within saga)

**Saga Implementation**:
```python
@dataclass
class SagaStep:
    name: str
    action: Callable[[], Awaitable[dict]]  # Forward action
    compensation: Callable[[dict], Awaitable[None]]  # Rollback action

class Saga:
    """Saga coordinator with automatic compensation"""
    
    def __init__(self, saga_id: str, correlation_id: str, event_store: EventStore):
        self.saga_id = saga_id
        self.correlation_id = correlation_id
        self.event_store = event_store
        self.steps: list[SagaStep] = []
        self.completed_steps: list[tuple[str, dict]] = []
    
    def add_step(self, step: SagaStep):
        """Add step to saga"""
        self.steps.append(step)
    
    async def execute(self) -> bool:
        """Execute saga with automatic compensation on failure"""
        try:
            for step in self.steps:
                log.info(f"[SAGA {self.saga_id}] Executing step: {step.name}")
                result = await step.action()
                self.completed_steps.append((step.name, result))
                
                # Log saga step event
                event = Event(
                    event_id=str(uuid.uuid4()),
                    event_type=EventType.SAGA_STEP_COMPLETED,
                    timestamp=time.time(),
                    correlation_id=self.correlation_id,
                    aggregate_id=self.saga_id,
                    data={"step": step.name, "result": result},
                    metadata={"saga_id": self.saga_id}
                )
                self.event_store.append_event(event)
            
            log.info(f"[SAGA {self.saga_id}] ✅ Completed successfully")
            return True
        
        except Exception as e:
            log.error(f"[SAGA {self.saga_id}] ❌ Failed at step {len(self.completed_steps)}: {e}")
            await self._compensate()
            return False
    
    async def _compensate(self):
        """Rollback completed steps in REVERSE order"""
        log.warning(f"[SAGA {self.saga_id}] 🔄 Starting compensation for {len(self.completed_steps)} steps")
        
        for step_name, result in reversed(self.completed_steps):
            try:
                # Find step definition
                step = next(s for s in self.steps if s.name == step_name)
                await step.compensation(result)
                log.info(f"[SAGA {self.saga_id}] ↩️ Compensated: {step_name}")
                
                # Log compensation event
                event = Event(
                    event_id=str(uuid.uuid4()),
                    event_type=EventType.SAGA_STEP_COMPENSATED,
                    timestamp=time.time(),
                    correlation_id=self.correlation_id,
                    aggregate_id=self.saga_id,
                    data={"step": step_name},
                    metadata={"saga_id": self.saga_id}
                )
                self.event_store.append_event(event)
            
            except Exception as e:
                log.critical(f"[SAGA {self.saga_id}] 🚨 COMPENSATION FAILED for {step_name}: {e}")
                # Manual intervention required - log to critical channel
```

---

### 7. Fill Processing Saga (NEW FILE)
**File**: `bot/strategy/sagas/fill_processing_saga.py`

**Requirements**:
- Handles BUY fill: Add position → Place TP → Place next grid order
- Handles SELL fill (TP): Remove position → Place new BUY order
- Implements compensation for each step
- Logs all saga events for audit trail

**BUY Fill Saga**:
```python
async def create_buy_fill_saga(
    fill_data: dict,
    correlation_id: str,
    position_actor: PositionManagerActor,
    order_actor: OrderManagerActor,
    grid_calc: GridCalculator,
    event_store: EventStore
) -> Saga:
    """Create saga for processing BUY fill"""
    
    saga = Saga(
        saga_id=f"buy-fill-{fill_data['order_id']}",
        correlation_id=correlation_id,
        event_store=event_store
    )
    
    # STEP 1: Add Position
    position_id = str(uuid.uuid4())
    
    async def add_position_action():
        tp_price = grid_calc.compute_tp_price(fill_data["fill_price"], "LONG")
        position = {
            "position_id": position_id,
            "entry_price": fill_data["fill_price"],
            "tp_price": tp_price,
            "size": fill_data["fill_size"],
            "correlation_id": correlation_id
        }
        
        reply_queue = asyncio.Queue()
        await position_actor.mailbox.put(
            Message("ADD_POSITION", position, reply_queue, correlation_id)
        )
        result = await reply_queue.get()
        return position
    
    async def add_position_compensation(position):
        # Rollback: Remove position
        await position_actor.mailbox.put(
            Message("REMOVE_POSITION", {"position_id": position_id}, None, correlation_id)
        )
    
    saga.add_step(SagaStep(
        name="add_position",
        action=add_position_action,
        compensation=add_position_compensation
    ))
    
    # STEP 2: Place TP Order
    async def place_tp_action():
        tp_price = grid_calc.compute_tp_price(fill_data["fill_price"], "LONG")
        reply_queue = asyncio.Queue()
        await order_actor.mailbox.put(
            Message("PLACE_TP", {
                "price": tp_price,
                "size": fill_data["fill_size"],
                "position_id": position_id
            }, reply_queue, correlation_id)
        )
        result = await reply_queue.get()
        return result
    
    async def place_tp_compensation(tp_result):
        # Rollback: Cancel TP order
        await order_actor.mailbox.put(
            Message("CANCEL_ORDER", {"order_id": tp_result["order_id"]}, None, correlation_id)
        )
    
    saga.add_step(SagaStep(
        name="place_tp",
        action=place_tp_action,
        compensation=place_tp_compensation
    ))
    
    # STEP 3: Place Next Grid Order (if fill is complete)
    if fill_data.get("is_complete", True):
        async def place_grid_action():
            next_price = grid_calc.compute_next_level_down(fill_data["fill_price"])
            reply_queue = asyncio.Queue()
            await order_actor.mailbox.put(
                Message("PLACE_BUY", {
                    "price": next_price,
                    "size": 1
                }, reply_queue, correlation_id)
            )
            result = await reply_queue.get()
            return result
        
        async def place_grid_compensation(grid_result):
            # Rollback: Cancel grid order
            await order_actor.mailbox.put(
                Message("CANCEL_ORDER", {"order_id": grid_result["order_id"]}, None, correlation_id)
            )
        
        saga.add_step(SagaStep(
            name="place_grid_order",
            action=place_grid_action,
            compensation=place_grid_compensation
        ))
    
    return saga
```

---

### 8. Async Main Bot (NEW FILE)
**File**: `bot/strategy/async_gridbot.py`

**Requirements**:
- Single `asyncio` event loop
- Start all actors as concurrent tasks
- Connect async WebSocket and handle messages
- Route fills to saga coordinator
- Periodic tasks (heartbeat, monitoring) using `asyncio.create_task`
- Graceful shutdown on SIGINT/SIGTERM

**Main Loop**:
```python
class AsyncGridBot:
    def __init__(self):
        self.event_store = EventStore("bot_events_LONG.db")
        self.api_client = AsyncDeltaClient(api_key, api_secret)
        
        # Actors
        self.position_actor = PositionManagerActor(self.event_store)
        self.order_actor = OrderManagerActor(self.api_client, self.event_store)
        
        # WebSocket
        self.ws_manager = AsyncWebSocketManager(api_key, api_secret)
        
        # Grid Calculator (pure functions, no state)
        self.grid_calc = GridCalculator(lower=99000, upper=112000, step=500)
        
        self._running = False
    
    async def start(self):
        """Start all async tasks"""
        self._running = True
        
        # Start actors
        actor_tasks = [
            asyncio.create_task(self.position_actor.start()),
            asyncio.create_task(self.order_actor.start())
        ]
        
        # WebSocket connection
        ws_task = asyncio.create_task(self._ws_message_loop())
        
        # Periodic tasks
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        # Wait for all tasks
        try:
            await asyncio.gather(
                *actor_tasks,
                ws_task,
                heartbeat_task,
                monitoring_task
            )
        except asyncio.CancelledError:
            log.info("Graceful shutdown initiated")
    
    async def _ws_message_loop(self):
        """Process WebSocket messages"""
        await self.ws_manager.connect()
        
        async for message in self.ws_manager.messages():
            msg_type = message.get("type")
            
            if msg_type == "user_trades":
                # Fill detected - create saga
                await self._handle_fill(message["data"])
            
            elif msg_type == "v2/ticker":
                # Price update - broadcast to actors
                # (implementation details...)
    
    async def _handle_fill(self, fill_data):
        """Process fill via saga"""
        correlation_id = f"fill-{fill_data['order_id']}-{int(time.time()*1000)}"
        
        if fill_data["side"] == "buy":
            saga = await create_buy_fill_saga(
                fill_data,
                correlation_id,
                self.position_actor,
                self.order_actor,
                self.grid_calc,
                self.event_store
            )
        else:  # sell (TP fill)
            saga = await create_sell_fill_saga(...)
        
        # Execute saga with automatic compensation
        success = await saga.execute()
        
        if not success:
            log.error(f"Saga failed - state rolled back: {correlation_id}")
            # Optionally: Send alert to Telegram
    
    async def _heartbeat_loop(self):
        """Periodic heartbeat tasks"""
        while self._running:
            await asyncio.sleep(15)
            
            # Get state from actor
            reply_queue = asyncio.Queue()
            await self.position_actor.mailbox.put(
                Message("GET_STATE", {}, reply_queue)
            )
            state = await reply_queue.get()
            
            # Log heartbeat
            log.info(f"[HB] Positions: {len(state['open_tranches'])}/5, Pending: {state['pending_buy'] is not None}")
    
    async def _monitoring_loop(self):
        """Write monitoring data for WebUI"""
        while self._running:
            await asyncio.sleep(5)
            
            # Get state from actor
            reply_queue = asyncio.Queue()
            await self.position_actor.mailbox.put(
                Message("GET_STATE", {}, reply_queue)
            )
            state = await reply_queue.get()
            
            # Write to monitoring snapshot
            await self._write_monitoring_snapshot(state)
    
    async def stop(self):
        """Graceful shutdown"""
        log.info("Stopping AsyncGridBot...")
        self._running = False
        
        await self.position_actor.stop()
        await self.order_actor.stop()
        await self.ws_manager.disconnect()
        
        log.info("✅ AsyncGridBot stopped")
```

---

### 9. Comprehensive Tests (NEW FILE)
**File**: `tests/test_async_actors_saga.py`

**Requirements**:
- Test actor message passing (100 messages, verify order)
- Test saga success path (all steps complete)
- Test saga failure at each step (verify compensation)
- Test concurrent saga execution (10 sagas in parallel)
- Chaos testing (inject random failures, verify rollback)
- Performance tests (1000 messages/sec throughput)

**Chaos Test Example**:
```python
@pytest.mark.asyncio
async def test_saga_compensation_on_tp_failure():
    """Test saga rollback when TP placement fails"""
    
    # Setup mocks
    event_store = EventStore(":memory:")
    position_actor = PositionManagerActor(event_store)
    order_actor = MockOrderActor(fail_on="PLACE_TP")  # Inject failure
    
    # Start actors
    asyncio.create_task(position_actor.start())
    asyncio.create_task(order_actor.start())
    
    # Create saga
    saga = await create_buy_fill_saga(
        fill_data={"order_id": "12345", "fill_price": 100000, "fill_size": 1, "is_complete": True},
        correlation_id="test-123",
        position_actor=position_actor,
        order_actor=order_actor,
        grid_calc=GridCalculator(lower=99000, upper=112000, step=500),
        event_store=event_store
    )
    
    # Execute saga (should fail at PLACE_TP)
    success = await saga.execute()
    
    # Verify failure
    assert not success, "Saga should fail"
    
    # Verify compensation: Position should be removed
    reply_queue = asyncio.Queue()
    await position_actor.mailbox.put(Message("GET_STATE", {}, reply_queue))
    state = await reply_queue.get()
    
    assert len(state["open_tranches"]) == 0, "Position should be rolled back"
    
    # Verify event log
    events = event_store.get_events_by_correlation("test-123")
    assert any(e.event_type == EventType.SAGA_STEP_COMPENSATED for e in events)
```

**Test Coverage Requirements**:
- ✅ 100% coverage of actor message handlers
- ✅ 100% coverage of saga steps and compensations
- ✅ Edge cases: Empty queue, slow handlers, timeout
- ✅ Failure scenarios: Network errors, API errors, validation errors
- ✅ Performance: <50ms p99 latency for message processing

---

### 10. Migration Script (NEW FILE)
**File**: `scripts/migrate_to_async.py`

**Requirements**:
- Gradual cutover from threaded to async
- Shadow mode: Run both versions in parallel, compare state
- State verification: Ensure async state matches threaded state
- Performance comparison: Measure latency improvement
- Rollback script if issues detected

**Migration Steps**:
```python
# 1. Deploy async version with legacy_mode=True (shadow mode)
# 2. Run for 24 hours, log state snapshots every 1 minute
# 3. Compare async state vs threaded state (should be 100% match)
# 4. If validation passes, switch to async_mode=True
# 5. Monitor for 7 days, verify stability
# 6. Remove threaded code after validation
```

---

## INTEGRATION POINTS

### With Existing Event Store (Phase 1)
- Actors use `EventStore.append_event()` for all state changes
- Saga coordinator logs saga events for audit trail
- No changes to `event_store.py` or `state_projector.py`

### With Existing Position Manager (Threaded)
- Keep `position_manager.py` for backward compatibility
- New `position_actor.py` inherits logic, removes locks
- Dual-write period: Both systems active, compare states

### With Existing WebSocket (Threaded)
- Keep `bot/delta_websocket/ws_manager.py` for legacy mode
- New `async_ws_manager.py` uses `websockets` library
- Gradual cutover: Start with async, fallback to threaded if issues

---

## ERROR HANDLING REQUIREMENTS

### Async API Client Errors
- **Timeout** (10s): Retry 3 times with exponential backoff (1s, 2s, 4s)
- **Rate Limit** (429): Wait for `Retry-After` header, then retry
- **Auth Error** (401): Critical error, stop bot, alert user
- **Network Error**: Circuit breaker opens after 5 failures, retry after 60s

### Actor Mailbox Errors
- **Message Handling Exception**: Log error, continue processing queue
- **Mailbox Full**: Apply backpressure (slow down message senders)
- **Actor Crash**: Restart actor, replay unprocessed messages

### Saga Compensation Errors
- **Compensation Fails**: Log critical error, send Telegram alert
- **Partial Compensation**: Mark saga as "needs manual intervention"
- **Compensation Timeout**: Retry compensation 3 times, then escalate

---

## PERFORMANCE TARGETS

### Latency
- Fill detection → Saga start: <10ms
- Saga execution (3 steps): <100ms p99
- Actor message processing: <5ms p99
- API call (order placement): <500ms p99

### Throughput
- Actor mailbox: 1000 messages/sec
- Concurrent sagas: 10 sagas in parallel
- WebSocket messages: 100 messages/sec

### Resource Usage
- Memory: -30% compared to threaded version
- CPU: -20% compared to threaded version
- File descriptors: <50 (single event loop)

---

## TESTING REQUIREMENTS

### Unit Tests (pytest)
- ✅ Test each actor independently (mock dependencies)
- ✅ Test saga step execution and compensation
- ✅ Test async API client (mock httpx responses)
- ✅ Test async WebSocket (mock websockets connection)

### Integration Tests
- ✅ Test full flow: Fill → Saga → Position + TP + Grid order
- ✅ Test actor communication (message passing)
- ✅ Test event store integration (verify events logged)

### Chaos Tests
- ✅ Inject failures at each saga step (verify compensation)
- ✅ Inject network errors (verify retry logic)
- ✅ Kill actors mid-processing (verify restart)
- ✅ Flood with 1000 messages/sec (verify no crashes)

### Performance Tests
- ✅ Measure latency under load (1000 fills/min)
- ✅ Memory leak test (run for 24 hours, monitor memory)
- ✅ Concurrent saga test (100 sagas in parallel)

**Minimum Test Coverage**: 90% (pytest-cov)

---

## CODE QUALITY REQUIREMENTS

### Type Hints
- ✅ 100% type hint coverage (use `mypy --strict`)
- ✅ Use `typing` module for complex types (`AsyncIterator`, `Awaitable`, etc.)

### Docstrings
- ✅ Google-style docstrings for all classes and functions
- ✅ Include Args, Returns, Raises sections
- ✅ Examples for complex logic

### Logging
- ✅ Use structured logging (JSON format)
- ✅ Include correlation_id in all logs
- ✅ Log levels: DEBUG (verbose), INFO (important), WARNING (unexpected), ERROR (failures), CRITICAL (manual intervention)

### Error Messages
- ✅ Descriptive error messages with context
- ✅ Include correlation_id, saga_id, actor_name in errors
- ✅ Actionable guidance (e.g., "Check API credentials")

---

## DEPLOYMENT STRATEGY

### Week 1 (Shadow Mode)
- Deploy async version alongside threaded version
- Both versions write to event store
- Compare state snapshots every 1 minute
- Verify 100% consistency

### Week 2 (Gradual Cutover)
- Switch reads to async version (keep threaded writes)
- Monitor for 7 days
- Verify no errors

### Week 3 (Full Migration)
- Switch writes to async version
- Keep threaded version as backup (disabled)
- Monitor for 7 days

### Week 4 (Cleanup)
- Remove threaded code
- Update documentation
- Celebrate! 🎉

---

## WHAT SUCCESS LOOKS LIKE

After implementation, you should have:

1. ✅ **Zero Locks**: No `threading.Lock` or `threading.RLock` in codebase
2. ✅ **Zero Threads**: Single `asyncio` event loop
3. ✅ **Actor System**: 3+ actors with message passing
4. ✅ **Saga Pattern**: 2+ sagas with compensation logic
5. ✅ **100% Tests Passing**: All new tests pass
6. ✅ **Performance Improvement**: -30% CPU, -40% memory
7. ✅ **Transactional Safety**: Rollback on any failure
8. ✅ **Production Ready**: Can deploy to staging immediately

---

## EXAMPLE OUTPUT STRUCTURE

After running your implementation, I should see:

```
bot/
├── api/
│   └── async_delta_client.py           (NEW - 300 lines)
├── delta_websocket/
│   └── async_ws_manager.py             (NEW - 400 lines)
├── strategy/
│   ├── actors/
│   │   ├── base_actor.py               (NEW - 150 lines)
│   │   ├── position_actor.py           (NEW - 300 lines)
│   │   └── order_actor.py              (NEW - 350 lines)
│   ├── sagas/
│   │   ├── saga_coordinator.py         (NEW - 200 lines)
│   │   ├── fill_processing_saga.py     (NEW - 400 lines)
│   │   └── position_closing_saga.py    (NEW - 300 lines)
│   └── async_gridbot.py                (NEW - 600 lines)
tests/
├── test_async_actors_saga.py           (NEW - 800 lines)
└── test_chaos_compensation.py          (NEW - 400 lines)
scripts/
└── migrate_to_async.py                 (NEW - 200 lines)

Total New Lines: ~4,400 lines
Total Files: 12 new files
```

---

## FINAL CHECKLIST

Before submitting your implementation, verify:

- [ ] All 12 files created
- [ ] All type hints added (`mypy --strict` passes)
- [ ] All docstrings added (Google style)
- [ ] All tests passing (pytest, >90% coverage)
- [ ] Performance targets met (latency, throughput)
- [ ] Error handling complete (retry, circuit breaker, compensation)
- [ ] Logging structured (JSON format, correlation IDs)
- [ ] Integration with Phase 1 Event Store working
- [ ] Migration script ready
- [ ] Zero breaking changes (backward compatible)

---

## COST OPTIMIZATION NOTES

**Why combine Phases 2 + 3?**

1. **Shared Context**: Both phases modify same files (async + saga together)
2. **Cost Savings**: 1 API call instead of 2 separate calls
3. **Better Integration**: Saga pattern works best with async (no locks)
4. **Faster Delivery**: 6-8 weeks → 1 implementation session

**Estimated Token Usage**:
- Input: ~8,000 tokens (this prompt)
- Output: ~15,000 tokens (4,400 lines of code + tests)
- Total: ~23,000 tokens (≈ $0.35 on Claude Opus 4.1)

**Alternative**: Running Phase 2 and Phase 3 separately would cost 2x ($0.70) and require 2 sessions.

---

## READY TO START?

Read this entire prompt carefully, then implement ALL deliverables in a SINGLE response. No questions, no clarifications - just production-ready code that passes all tests.

**Your implementation should**:
1. Work out of the box (no syntax errors)
2. Pass all tests (90%+ coverage)
3. Meet performance targets
4. Be ready for staging deployment

Good luck! 🚀
