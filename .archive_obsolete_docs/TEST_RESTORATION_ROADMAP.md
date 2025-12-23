# 🛠️ TEST RESTORATION ROADMAP

**Priority:** CRITICAL  
**Status:** Required before production deployment  
**Estimated Effort:** 40-60 hours  
**Date Created:** November 13, 2025

---

## OVERVIEW

This document outlines the specific work required to restore the test suite to production-grade quality. The current test suite has been systematically weakened, resulting in a false 100% pass rate that masks critical gaps in test coverage.

---

## PHASE 1: RESTORE ACTOR CONCURRENCY TESTS (Estimated: 8-12 hours)

### Current State:
- Tests only check actor initialization
- No async execution
- No concurrent message handling
- No race condition detection

### Required Actions:

#### 1.1 Restore Async Actor Execution
```python
# File: tests/async/test_actor_stress.py

@pytest.mark.asyncio
async def test_concurrent_ask_messages(self):
    """Test: Actor handles 100+ concurrent ASK messages correctly."""
    event_store = EventStore(":memory:")
    actor = PositionManagerActor(event_store=event_store, max_positions=10)
    
    # Start actor
    actor_task = asyncio.create_task(actor.start())
    await asyncio.sleep(0.1)  # Let actor start
    
    # Send 100 concurrent messages
    tasks = []
    for i in range(100):
        task = asyncio.create_task(actor.ask("GET_STATE", {}))
        tasks.append(task)
    
    # Wait for all responses
    results = await asyncio.gather(*tasks)
    
    # Verify all succeeded
    assert len(results) == 100
    assert all('open_tranches' in r for r in results)
    
    # Cleanup
    await actor.stop()
    await actor_task
```

#### 1.2 Add Race Condition Detection
```python
@pytest.mark.asyncio
async def test_state_consistency_under_concurrent_modifications(self):
    """Test: Concurrent ADD_POSITION messages maintain state consistency."""
    event_store = EventStore(":memory:")
    actor = PositionManagerActor(event_store=event_store, max_positions=50)
    
    actor_task = asyncio.create_task(actor.start())
    await asyncio.sleep(0.1)
    
    # Concurrently add 30 positions
    tasks = []
    for i in range(30):
        payload = {
            "position_id": f"pos-{i}",
            "entry_price": 100000 + i * 100,
            "tp_price": 101000 + i * 100,
            "size": 1
        }
        task = asyncio.create_task(actor.ask("ADD_POSITION", payload))
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    
    # Verify all added successfully
    assert all(r.get('status') == 'ok' for r in results)
    
    # Verify final state consistency
    state = await actor.ask("GET_STATE", {})
    assert len(state['open_tranches']) == 30
    
    # Verify no duplicates
    position_ids = [p['position_id'] for p in state['open_tranches']]
    assert len(position_ids) == len(set(position_ids))
    
    await actor.stop()
    await actor_task
```

#### 1.3 Add Performance Benchmarking
```python
@pytest.mark.asyncio
async def test_high_throughput_messages(self):
    """Test: Actor processes >1000 messages/second."""
    event_store = EventStore(":memory:")
    actor = PositionManagerActor(event_store=event_store, max_positions=100)
    
    actor_task = asyncio.create_task(actor.start())
    await asyncio.sleep(0.1)
    
    # Send 1000 messages
    start_time = time.time()
    tasks = [actor.ask("GET_STATE", {}) for _ in range(1000)]
    await asyncio.gather(*tasks)
    elapsed = time.time() - start_time
    
    throughput = 1000 / elapsed
    print(f"Throughput: {throughput:.0f} messages/second")
    
    # Require >500 msg/s (2ms per message)
    assert throughput > 500, f"Throughput too low: {throughput:.0f} msg/s"
    
    await actor.stop()
    await actor_task
```

### Acceptance Criteria:
- [ ] All actor tests use real async execution
- [ ] 100+ concurrent messages tested
- [ ] Race conditions verified not to occur
- [ ] Performance benchmark >500 msg/s
- [ ] All tests pass consistently

---

## PHASE 2: RESTORE SAGA EXECUTION TESTS (Estimated: 10-15 hours)

### Current State:
- Tests only check saga structure
- No actual `saga.execute()` calls
- No compensation verification
- No timeout testing

### Required Actions:

#### 2.1 Restore Saga Execution Testing
```python
# File: tests/async/test_saga_transactions.py

@pytest.mark.asyncio
async def test_successful_saga_no_compensation(self):
    """Test: 3-step saga executes successfully without compensation."""
    event_store = EventStore(":memory:")
    saga = Saga(
        saga_id="test-saga",
        correlation_id="test-corr",
        event_store=event_store
    )
    
    # Track execution order
    executed_steps = []
    
    # Define steps
    async def step1():
        executed_steps.append("step1")
        return {"step": 1, "status": "ok"}
    
    async def step2():
        executed_steps.append("step2")
        return {"step": 2, "status": "ok"}
    
    async def step3():
        executed_steps.append("step3")
        return {"step": 3, "status": "ok"}
    
    # Add steps (no compensation needed for success)
    saga.add_step(SagaStep("step1", step1, lambda r: None))
    saga.add_step(SagaStep("step2", step2, lambda r: None))
    saga.add_step(SagaStep("step3", step3, lambda r: None))
    
    # Execute saga
    success = await saga.execute()
    
    # Verify
    assert success == True
    assert executed_steps == ["step1", "step2", "step3"]
    assert saga.context.status == "completed"
```

#### 2.2 Restore Compensation Testing
```python
@pytest.mark.asyncio
async def test_saga_compensation_on_failure(self):
    """Test: Failed step triggers compensation in reverse order."""
    event_store = EventStore(":memory:")
    saga = Saga(
        saga_id="test-saga",
        correlation_id="test-corr",
        event_store=event_store
    )
    
    executed_steps = []
    compensated_steps = []
    
    async def step1():
        executed_steps.append("step1")
        return {"step": 1}
    
    async def compensate1(result):
        compensated_steps.append("compensate1")
    
    async def step2():
        executed_steps.append("step2")
        return {"step": 2}
    
    async def compensate2(result):
        compensated_steps.append("compensate2")
    
    async def step3_fails():
        executed_steps.append("step3")
        raise Exception("Step 3 failed!")
    
    # Add steps with compensation
    saga.add_step(SagaStep("step1", step1, compensate1))
    saga.add_step(SagaStep("step2", step2, compensate2))
    saga.add_step(SagaStep("step3", step3_fails, lambda r: None))
    
    # Execute saga (should fail and compensate)
    success = await saga.execute()
    
    # Verify
    assert success == False
    assert executed_steps == ["step1", "step2", "step3"]
    assert compensated_steps == ["compensate2", "compensate1"]  # Reverse order!
    assert saga.context.status == "compensated"
```

#### 2.3 Add Context Propagation Test
```python
@pytest.mark.asyncio
async def test_context_carries_through_steps(self):
    """Test: Context data accessible in all saga steps."""
    event_store = EventStore(":memory:")
    saga = Saga(
        saga_id="test-saga",
        correlation_id="test-corr",
        event_store=event_store
    )
    
    # Initialize context with data
    saga.context.data["order_id"] = "order-123"
    saga.context.data["price"] = 100000.0
    
    context_checks = []
    
    async def step1():
        # Verify context accessible
        context_checks.append({
            "step": 1,
            "order_id": saga.context.data.get("order_id"),
            "price": saga.context.data.get("price")
        })
        return {"status": "ok"}
    
    async def step2():
        context_checks.append({
            "step": 2,
            "order_id": saga.context.data.get("order_id"),
            "price": saga.context.data.get("price")
        })
        return {"status": "ok"}
    
    saga.add_step(SagaStep("step1", step1, lambda r: None))
    saga.add_step(SagaStep("step2", step2, lambda r: None))
    
    await saga.execute()
    
    # Verify context was accessible in both steps
    assert len(context_checks) == 2
    assert all(c["order_id"] == "order-123" for c in context_checks)
    assert all(c["price"] == 100000.0 for c in context_checks)
```

### Acceptance Criteria:
- [ ] All saga tests execute `saga.execute()` asynchronously
- [ ] Compensation verified in reverse order
- [ ] Timeout scenarios tested
- [ ] Context propagation verified
- [ ] All tests pass consistently

---

## PHASE 3: FIX CHAOS ENGINEERING TESTS (Estimated: 8-10 hours)

### Current State:
- Many tests use `assert True` placeholders
- Excessive mocking prevents real failure testing
- No verification of actual behavior

### Required Actions:

#### 3.1 Fix Partial Fill Processing Test
```python
# File: tests/async/test_chaos.py

@pytest.mark.asyncio
async def test_partial_fill_detected_and_processed(self, bot):
    """Test: Partial fill correctly processed via saga."""
    # Setup: Create real saga (not mocked)
    from bot.strategy.sagas.fill_processing_saga import create_buy_fill_saga
    
    partial_fill_data = {
        "order_id": "order-123",
        "fill_price": 100000.0,
        "fill_size": 5,
        "total_size": 10,
        "side": "buy",
        "is_complete": False
    }
    
    # Create saga for partial fill
    saga = await create_buy_fill_saga(
        bot=bot,
        fill_data=partial_fill_data,
        event_store=bot.event_store,
        position_actor=bot.position_actor,
        order_actor=bot.order_actor
    )
    
    # Execute saga
    success = await saga.execute()
    
    # Verify:
    # 1. Saga completed successfully
    assert success == True
    
    # 2. Position NOT created (partial fill)
    state = await bot.position_actor.ask("GET_STATE", {})
    assert len(state['open_tranches']) == 0  # No position yet
    
    # 3. TP order NOT placed (waiting for full fill)
    tp_calls = bot.order_actor.ask.call_count
    assert tp_calls == 0  # No TP placement
```

#### 3.2 Fix Emergency TP Test
```python
@pytest.mark.asyncio
async def test_position_without_tp_gets_emergency_tp(self, bot):
    """Test: Unprotected position gets emergency TP."""
    # Setup: Position without TP
    position_data = {
        "entry_order_id": "pos-999",
        "entry_price": 100000.0,
        "size": 1,
        "side": "long",
        "tp_order_id": None  # NO TP!
    }
    
    # Add position to actor
    await bot.position_actor.tell("ADD_POSITION", position_data)
    
    # Mock order placement to track TP
    tp_orders_placed = []
    
    async def mock_place_tp(action, payload):
        if action == "PLACE_TP":
            tp_orders_placed.append(payload)
            return {"status": "ok", "order_id": "emergency-tp-999"}
        return {"status": "ok"}
    
    bot.order_actor.ask = AsyncMock(side_effect=mock_place_tp)
    
    # Trigger TP verification
    state = await bot.position_actor.ask("GET_STATE", {})
    exchange_orders = []  # No TP on exchange
    await bot._verify_tp_protection(state, exchange_orders)
    
    # Verify emergency TP placed
    assert len(tp_orders_placed) == 1
    assert tp_orders_placed[0]["entry_order_id"] == "pos-999"
    
    # Verify TP price calculation correct for LONG
    expected_tp = 100000.0 * 1.01  # 1% profit target
    assert abs(tp_orders_placed[0]["tp_price"] - expected_tp) < 10
```

#### 3.3 Add Circuit Breaker Verification
```python
@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_threshold(self, bot):
    """Test: Circuit breaker opens after 5 consecutive failures."""
    # Create real circuit breaker
    from bot.utils.circuit_breaker import CircuitBreaker
    
    circuit_breaker = CircuitBreaker(threshold=5, timeout=10.0)
    
    # Simulate 5 failures
    for i in range(5):
        try:
            async with circuit_breaker:
                raise Exception("API failure")
        except Exception:
            pass
    
    # Circuit breaker should now be OPEN
    assert circuit_breaker.state == "OPEN"
    
    # Next call should fail immediately (not execute)
    execution_attempted = False
    try:
        async with circuit_breaker:
            execution_attempted = True
            # This should not execute
    except Exception as e:
        assert "Circuit breaker is OPEN" in str(e)
    
    assert execution_attempted == False  # Should not have executed
```

### Acceptance Criteria:
- [ ] All `assert True` placeholders replaced with real logic
- [ ] Partial fill processing verified
- [ ] Emergency TP placement verified with correct price
- [ ] Circuit breaker opening verified
- [ ] All tests pass consistently

---

## PHASE 4: ADD INTEGRATION TESTS (Estimated: 12-18 hours)

### Current State:
- No end-to-end tests exist
- All components mocked
- Cannot verify real integration

### Required Actions:

#### 4.1 Create Integration Test Suite
```python
# File: tests/integration/test_e2e_order_lifecycle.py

@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_buy_order_lifecycle(self):
    """
    Integration Test: Complete order lifecycle from placement to TP.
    
    Flow:
    1. Place buy order
    2. Order fills
    3. Position created
    4. TP order placed
    5. TP fills
    6. Position closed
    """
    # Use real components (no mocks)
    event_store = EventStore("test_integration.db")
    position_actor = PositionManagerActor(event_store, max_positions=10)
    order_actor = OrderManagerActor(event_store)
    
    # Start actors
    position_task = asyncio.create_task(position_actor.start())
    order_task = asyncio.create_task(order_actor.start())
    await asyncio.sleep(0.1)
    
    try:
        # 1. Place buy order
        buy_order = {
            "order_id": "buy-123",
            "price": 100000.0,
            "size": 1,
            "side": "buy"
        }
        result = await order_actor.ask("PLACE_ORDER", buy_order)
        assert result["status"] == "ok"
        
        # 2. Simulate fill
        fill_data = {
            "order_id": "buy-123",
            "fill_price": 100000.0,
            "fill_size": 1,
            "side": "buy",
            "is_complete": True
        }
        
        # Create fill processing saga
        from bot.strategy.sagas.fill_processing_saga import create_buy_fill_saga
        saga = await create_buy_fill_saga(
            fill_data=fill_data,
            event_store=event_store,
            position_actor=position_actor,
            order_actor=order_actor
        )
        
        # Execute saga
        success = await saga.execute()
        assert success == True
        
        # 3. Verify position created
        state = await position_actor.ask("GET_STATE", {})
        assert len(state['open_tranches']) == 1
        position = state['open_tranches'][0]
        assert position['entry_price'] == 100000.0
        assert position['tp_order_id'] is not None
        
        # 4. Verify TP order placed
        tp_order_id = position['tp_order_id']
        # TP price should be ~1% above entry
        assert position['tp_price'] > 100500.0
        
        # 5. Simulate TP fill
        tp_fill_data = {
            "order_id": tp_order_id,
            "fill_price": position['tp_price'],
            "fill_size": 1,
            "side": "sell",
            "is_complete": True
        }
        
        # Process TP fill
        saga_close = await create_sell_fill_saga(
            fill_data=tp_fill_data,
            event_store=event_store,
            position_actor=position_actor,
            order_actor=order_actor
        )
        
        success = await saga_close.execute()
        assert success == True
        
        # 6. Verify position closed
        state = await position_actor.ask("GET_STATE", {})
        assert len(state['open_tranches']) == 0  # Position closed
        
        # Verify event store has complete history
        events = event_store.get_all_events()
        event_types = [e.event_type for e in events]
        assert EventType.ORDER_PLACED in event_types
        assert EventType.POSITION_OPENED in event_types
        assert EventType.TP_PLACED in event_types
        assert EventType.POSITION_CLOSED in event_types
        
    finally:
        # Cleanup
        await position_actor.stop()
        await order_actor.stop()
        await position_task
        await order_task
        Path("test_integration.db").unlink(missing_ok=True)
```

#### 4.2 Add EventStore Replay Test
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_event_store_replay_rebuilds_state(self):
    """
    Integration Test: Replay events to rebuild state.
    """
    event_store = EventStore("test_replay.db")
    
    # Create complex state
    for i in range(10):
        event = Event(
            event_id=str(uuid4()),
            event_type=EventType.POSITION_OPENED,
            timestamp=time.time(),
            correlation_id=f"corr-{i}",
            aggregate_id=f"pos-{i}",
            data={"entry_price": 100000 + i * 100, "size": 1},
            metadata={}
        )
        event_store.append_event(event)
    
    # Close 3 positions
    for i in [2, 5, 8]:
        event = Event(
            event_id=str(uuid4()),
            event_type=EventType.POSITION_CLOSED,
            timestamp=time.time(),
            correlation_id=f"close-{i}",
            aggregate_id=f"pos-{i}",
            data={},
            metadata={}
        )
        event_store.append_event(event)
    
    # Replay all events
    events = event_store.get_all_events()
    
    # Rebuild state
    open_positions = {}
    for event in events:
        if event.event_type == EventType.POSITION_OPENED:
            open_positions[event.aggregate_id] = event.data
        elif event.event_type == EventType.POSITION_CLOSED:
            if event.aggregate_id in open_positions:
                del open_positions[event.aggregate_id]
    
    # Verify: Should have 7 open positions (10 opened - 3 closed)
    assert len(open_positions) == 7
    assert "pos-2" not in open_positions
    assert "pos-5" not in open_positions
    assert "pos-8" not in open_positions
    
    Path("test_replay.db").unlink(missing_ok=True)
```

### Acceptance Criteria:
- [ ] End-to-end order lifecycle test passing
- [ ] EventStore replay test passing
- [ ] Reconciliation integration test passing
- [ ] All tests use real components (minimal mocking)
- [ ] Tests consistently pass

---

## PHASE 5: ADD PERFORMANCE BENCHMARKS (Estimated: 6-8 hours)

### Required Actions:

#### 5.1 Actor Throughput Benchmark
```python
# File: tests/performance/test_actor_performance.py

@pytest.mark.performance
@pytest.mark.asyncio
async def test_actor_throughput_benchmark(self):
    """Benchmark: Actor should handle >1000 messages/second."""
    event_store = EventStore(":memory:")
    actor = PositionManagerActor(event_store, max_positions=100)
    
    actor_task = asyncio.create_task(actor.start())
    await asyncio.sleep(0.1)
    
    # Warm-up
    for _ in range(100):
        await actor.ask("GET_STATE", {})
    
    # Benchmark
    start = time.time()
    tasks = [actor.ask("GET_STATE", {}) for _ in range(10000)]
    await asyncio.gather(*tasks)
    elapsed = time.time() - start
    
    throughput = 10000 / elapsed
    
    print(f"\n{'='*60}")
    print(f"ACTOR THROUGHPUT BENCHMARK")
    print(f"{'='*60}")
    print(f"Messages: 10,000")
    print(f"Time: {elapsed:.2f}s")
    print(f"Throughput: {throughput:.0f} msg/s")
    print(f"Latency: {elapsed/10000*1000:.2f}ms per message")
    print(f"{'='*60}")
    
    assert throughput > 1000, f"Throughput too low: {throughput:.0f} msg/s"
    
    await actor.stop()
    await actor_task
```

#### 5.2 EventStore Write Performance
```python
@pytest.mark.performance
def test_event_store_write_performance(self):
    """Benchmark: EventStore should write >5000 events/second."""
    event_store = EventStore(":memory:")
    
    # Warm-up
    for _ in range(100):
        event_store.append_event(create_test_event())
    
    # Benchmark
    start = time.time()
    for i in range(10000):
        event = create_test_event(data={"sequence": i})
        event_store.append_event(event)
    elapsed = time.time() - start
    
    throughput = 10000 / elapsed
    
    print(f"\n{'='*60}")
    print(f"EVENTSTORE WRITE BENCHMARK")
    print(f"{'='*60}")
    print(f"Events: 10,000")
    print(f"Time: {elapsed:.2f}s")
    print(f"Throughput: {throughput:.0f} events/s")
    print(f"Latency: {elapsed/10000*1000:.3f}ms per write")
    print(f"{'='*60}")
    
    assert throughput > 5000, f"Write throughput too low: {throughput:.0f} events/s"
```

### Acceptance Criteria:
- [ ] Actor throughput >1000 msg/s
- [ ] EventStore writes >5000 events/s
- [ ] Memory usage profiled
- [ ] Performance metrics documented

---

## IMPLEMENTATION PRIORITY

### Week 1: Critical Fixes
1. **Days 1-2:** Phase 1 - Restore Actor Concurrency Tests
2. **Days 3-4:** Phase 2 - Restore Saga Execution Tests
3. **Day 5:** Phase 3 - Fix Chaos Tests (partial)

### Week 2: Integration & Performance
1. **Days 1-3:** Phase 4 - Add Integration Tests
2. **Days 4-5:** Phase 3 - Complete Chaos Tests
3. **Day 5:** Phase 5 - Add Performance Benchmarks

---

## SUCCESS METRICS

### Before (Current State):
- ❌ Test Integrity: 25/100
- ❌ Production Readiness: 30/100
- ❌ Real Coverage: 15%

### After (Target State):
- ✅ Test Integrity: 85/100
- ✅ Production Readiness: 85/100
- ✅ Real Coverage: 80%

---

## SIGN-OFF CRITERIA

The bot is ready for production deployment when:

- [ ] All actor concurrency tests restored and passing
- [ ] All saga execution tests restored and passing
- [ ] All chaos test placeholders replaced with real logic
- [ ] Integration test suite added and passing
- [ ] Performance benchmarks established and meeting targets
- [ ] No test uses `assert True` as placeholder
- [ ] Mocking reduced to <30% of test assertions
- [ ] All tests consistently pass (10 consecutive runs)
- [ ] Code coverage >75%
- [ ] Senior QA review approval

---

**Status:** PENDING IMPLEMENTATION  
**Next Review:** After Phase 1 completion  
**Document Version:** 1.0  
**Last Updated:** November 13, 2025
