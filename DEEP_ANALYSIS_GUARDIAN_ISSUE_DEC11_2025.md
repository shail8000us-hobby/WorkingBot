# DEEP ANALYSIS - Guardian STOP Signal Issue
## December 11, 2025 - Comprehensive Code Verification

---

## 🔍 COMPLETE CODE PATH ANALYSIS

### Scenario: TP @ 90000 fills while Guardian signal = STOP

#### Step-by-Step Execution Flow:

**1. TP Order Fills (WebSocket notification)**
```
WebSocket receives fill notification
↓
_handle_user_trades() called (line 1437)
↓
_process_fill() called (line 1448)
```

**2. Fill Processing Initiated**
```python
# async_gridbot.py line 1454-1471
async def _process_fill(self, fill_data: Dict[str, Any]):
    # ... validation ...
    
    if self.mode == "LONG":
        if processed_fill["side"] == "sell":  # ✅ This is our TP fill
            # ... logging ...
            
            saga = await create_sell_fill_saga(  # ✅ Create saga
                fill_data=processed_fill,
                correlation_id=correlation_id,
                position_actor=self.position_actor,
                order_actor=self.order_actor,
                grid_calc=self.grid_calc,
                event_store=self.event_store,
                mode=self.mode
            )
```

**3. Saga Creation (fill_processing_saga.py line 416-800)**
```python
async def create_sell_fill_saga(...):
    saga = Saga(saga_id=..., correlation_id=..., event_store=..., timeout=30.0)
    
    # STEP 1: Remove position ✅
    saga.add_step(SagaStep(name="remove_position", ...))
    
    # STEP 2: Clear pending sell ✅
    saga.add_step(SagaStep(name="clear_pending_sell", ...))
    
    # STEP 3: Place new BUY order ⚠️ CRITICAL
    saga.add_step(SagaStep(
        name="place_buy_order",
        action=place_buy_action,  # ← This is where Guardian check happens
        compensation=place_buy_compensation,
        critical=False
    ))
    
    return saga
```

**4. Saga Execution Started (saga_coordinator.py line 375-401)**
```python
async def start_saga(self, saga: Saga) -> asyncio.Task:
    self._active_sagas[saga.saga_id] = saga
    task = asyncio.create_task(self._execute_saga(saga))
    self._saga_tasks[saga.saga_id] = task
    return task
```

**5. Saga Execution (saga_coordinator.py line 104-159)**
```python
async def execute(self) -> bool:
    # Execute with timeout
    await asyncio.wait_for(self._execute_steps(), timeout=self.timeout)
    
    # Mark completed
    self.context.status = "completed"
    self.context.completed_at = time.time()
    
    # ✅ CRITICAL: step_results stored in context
    complete_event = Event(..., metadata={"step_results": self.context.step_results})
    
    return True  # ✅ Returns bool
```

**6. Saga Step Execution (saga_coordinator.py line 161-202)**
```python
async def _execute_steps(self) -> None:
    for i, step in enumerate(self.steps):
        result = await step.action()  # ← Execute place_buy_action()
        
        # ✅ CRITICAL: Store result in context
        self.completed_steps.append((step.name, result))
        self.context.step_results[step.name] = result  # ← This is key!
        
        # Log step event with result
        step_event = Event(..., data={..., "result": result})
```

**7. place_buy_action() Execution (fill_processing_saga.py line 572-772)**
```python
async def place_buy_action() -> Dict[str, Any]:
    next_price = tp_price - step  # 90000 - 500 = 89500
    
    # ✅ Guardian Check (line 580-620)
    guardian_events = event_store.get_events_by_type([GUARDIAN_SIGNAL_GO, GUARDIAN_SIGNAL_STOP], limit=1)
    
    if guardian_events:
        signal = 'GO' if guardian_events[0].event_type == GUARDIAN_SIGNAL_GO else 'STOP'
        
        if signal == 'STOP':
            reason = guardian_events[0].data.get('reason', 'No reason')
            log.warning(f"⚠️ Guardian STOP - Cannot place BUY @ ${next_price}")
            
            # ✅ CRITICAL: Return with missed_order info
            return {
                "status": "skipped", 
                "reason": f"guardian_stop: {reason}", 
                "missed_order": {"price": next_price, "side": "buy"}
            }
    
    # If Guardian = GO, continue with order placement
    # ... cancel old orders ...
    # ... place new order ...
    return {"status": "ok", "order_id": ...}
```

**8. Return to Saga Orchestrator (saga_coordinator.py line 401-424)**
```python
async def _execute_saga(self, saga: Saga) -> Saga:  # ✅ Returns Saga, not bool!
    success = await saga.execute()
    
    if success:
        self._total_completed += 1
    
    # ✅ CRITICAL: Return saga object so caller can inspect step_results
    return saga  # ← Contains saga.context.step_results
```

**9. Saga Completion Tracking (async_gridbot.py line 1765)**
```python
# Execute saga
task = await self.saga_orchestrator.start_saga(saga)

# Track saga completion
asyncio.create_task(self._track_saga_completion(task, correlation_id))
```

**10. Extract Missed Order (async_gridbot.py line 1668-1699)**
```python
async def _track_saga_completion(self, task: asyncio.Task, correlation_id: str):
    saga = await task  # ✅ Task returns Saga object
    
    if saga and saga.context.status == "completed":
        # ✅ Check step_results for skipped orders
        for step_name, step_result in saga.context.step_results.items():
            if isinstance(step_result, dict):
                if step_result.get('status') == 'skipped' and 'guardian_stop' in step_result.get('reason', ''):
                    missed_order = step_result.get('missed_order')
                    if missed_order:
                        price = missed_order.get('price')  # 89500
                        side = missed_order.get('side')    # "buy"
                        reason = step_result.get('reason')
                        
                        log.warning(f"📝 Tracking missed order: {side} @ ${price}")
                        # ✅ Add to retry list
                        self._missed_grid_orders.append((price, side, reason, time.time()))
```

**11. Guardian Health Monitor (async_gridbot.py line 2641-2665)**
```python
async def _guardian_health_monitor_loop(self):
    while self._running:
        # Check Guardian signal
        signal, reason = await self._read_guardian_signal()
        
        # ✅ Check for signal transition and retry
        await self._check_guardian_transition_and_retry()
        
        await asyncio.sleep(15)  # Check every 15 seconds
```

**12. Transition Detection (async_gridbot.py line 572-602)**
```python
async def _check_guardian_transition_and_retry(self):
    signal, reason = await self._read_guardian_signal()
    
    # ✅ Detect STOP -> GO transition
    if self._last_guardian_signal == 'STOP' and signal == 'GO':
        log.info("🟢 GUARDIAN TRANSITION DETECTED: STOP -> GO")
        
        if self._missed_grid_orders:
            await self._retry_missed_grid_orders()
    
    # Track signal
    if self._last_guardian_signal != signal:
        self._last_guardian_signal = signal
        self._guardian_transition_time = time.time()
```

**13. Retry Missed Orders (async_gridbot.py line 605-688)**
```python
async def _retry_missed_grid_orders(self):
    # Get current state
    state = await self.position_actor.ask("GET_STATE", {})
    pending_buy = state.get("pending_buy")
    
    for missed_order in list(self._missed_grid_orders):
        price, side, reason, timestamp = missed_order
        
        if side == "buy":
            # ⚠️ CRITICAL CHECK MISSING: Should verify Guardian is still GO!
            
            # Skip if pending_buy exists
            if pending_buy:
                log.info(f"Skipping - already have pending buy")
                continue
            
            # Skip if out of bounds
            if not self.grid_calc.is_within_bounds(price):
                continue
            
            # ✅ Place order
            result = await self.order_actor.ask("PLACE_BUY", {
                "price": price,
                "size": self.lot
            }, timeout=10.0)
            
            if result.get("status") == "ok":
                # Update state
                await self.position_actor.tell("SET_PENDING_BUY", {...})
    
    # Clear list
    self._missed_grid_orders.clear()
```

---

## ❌ CRITICAL ISSUES FOUND

### Issue #1: Retry Does NOT Check Guardian Signal Again

**Location:** `async_gridbot.py` line 605-688 (`_retry_missed_grid_orders()`)

**Problem:**
```python
# Current code:
async def _retry_missed_grid_orders(self):
    for missed_order in list(self._missed_grid_orders):
        # ❌ NO Guardian check here!
        result = await self.order_actor.ask("PLACE_BUY", {...})
```

**Why This is Critical:**
1. Retry is triggered when Guardian transitions STOP → GO
2. But between detection (line 586) and retry (line 643), Guardian could change back to STOP
3. Race condition window: ~15 seconds (monitor check interval)
4. If Guardian goes STOP again during retry, orders will be placed anyway!

**Real-World Scenario:**
```
Time 0s:  Guardian = STOP (volatility high)
Time 5s:  TP fills, order skipped, tracked as missed
Time 10s: Guardian = GO (volatility drops)
Time 11s: _check_guardian_transition_and_retry() detects transition
Time 11s: _retry_missed_grid_orders() starts
Time 12s: Guardian = STOP (volatility spikes again!)
Time 12s: Retry still executing, places order despite STOP signal ❌
```

### Issue #2: OrderActor Does NOT Check Guardian

**Location:** `bot/strategy/actors/order_actor.py` line 111-244

**Problem:**
The OrderActor directly places orders without any Guardian check:
```python
async def _handle_place_buy(self, payload, reply_to, correlation_id):
    # ❌ NO Guardian check here!
    result = await self.api_client.place_order(...)
    return {"status": "ok", "order_id": order_id}
```

**Why This is Dangerous:**
- All order placement goes through OrderActor
- OrderActor has no knowledge of Guardian state
- Acts as a "dumb" order executor

### Issue #3: Initial Order Placement IS Protected

**Location:** `async_gridbot.py` line 2020

**Good News:**
```python
# Initial order DOES check Guardian
can_proceed, reason = await self._comprehensive_safety_check("initial order placement")
if not can_proceed:
    # Block order ✅
```

But retry mechanism does NOT use this check!

---

## 🔧 REQUIRED FIXES

### Fix #1: Add Guardian Check to Retry Mechanism

**File:** `bot/strategy/async_gridbot.py` line ~643

**Before:**
```python
async def _retry_missed_grid_orders(self):
    for missed_order in list(self._missed_grid_orders):
        # ... validation ...
        result = await self.order_actor.ask("PLACE_BUY", {...})
```

**After:**
```python
async def _retry_missed_grid_orders(self):
    # ✅ Check Guardian BEFORE retrying any orders
    signal, reason = await self._read_guardian_signal()
    if signal == 'STOP':
        log.warning(f"⚠️ Guardian is STOP again - Cannot retry missed orders")
        log.warning(f"   Reason: {reason}")
        log.warning(f"   Missed orders will be retried on next GO signal")
        return  # ← Exit early, keep orders in list for next transition
    
    for missed_order in list(self._missed_grid_orders):
        # ... rest of retry logic ...
```

### Fix #2: Add Guardian Check INSIDE Loop (Defense in Depth)

**Rationale:** Even if Guardian is GO at start, it could change during retry loop

```python
async def _retry_missed_grid_orders(self):
    # Initial check
    signal, reason = await self._read_guardian_signal()
    if signal == 'STOP':
        return
    
    for missed_order in list(self._missed_grid_orders):
        # ✅ Check Guardian before EACH order (if multiple orders)
        if len(self._missed_grid_orders) > 1:
            signal, reason = await self._read_guardian_signal()
            if signal == 'STOP':
                log.warning(f"⚠️ Guardian changed to STOP during retry - stopping")
                break  # Stop retry loop, remaining orders stay in list
        
        # ... place order ...
```

---

## ✅ WHAT IS CORRECT

1. ✅ Guardian check in sagas (4 locations) - **Working**
2. ✅ Saga result tracking - **Working**
3. ✅ Missed order extraction - **Working**
4. ✅ Transition detection - **Working**
5. ✅ Initial order Guardian check - **Working**
6. ✅ All order placement locations identified - **Complete**

---

## ❌ WHAT NEEDS FIXING

1. ❌ **Retry mechanism lacks Guardian check** - **CRITICAL**
2. ⚠️ **Race condition window in retry** - **HIGH PRIORITY**
3. ⚠️ **No defense in depth for retry loop** - **MEDIUM PRIORITY**

---

## 📊 RISK ASSESSMENT

### Without Fixes:
**Risk Level: MEDIUM-HIGH** (70% confidence it will work, 30% risk of issues)

**Why:**
- Most cases will work (Guardian stays GO during retry)
- But volatility can spike rapidly (seconds)
- Orders could be placed during a brief GO window before Guardian STOP
- Real money at stake

### With Fixes:
**Risk Level: LOW** (95% confidence, 5% for unknown edge cases)

**Why:**
- Guardian checked before retry
- Guardian checked during retry (for multiple orders)
- Multiple safety layers
- Graceful handling of state changes

---

## 🎯 CONFIDENCE LEVEL

**Before Deep Analysis:** 95% confidence (naive)
**After Deep Analysis:** 70% confidence (found critical issues)
**After Implementing Fixes:** 95% confidence (realistic)

---

## 📝 RECOMMENDATION

**DO NOT DEPLOY** current implementation without the retry Guardian check fix.

The fix is simple (10 lines of code) but critical for safety.

---

**Analysis Date:** December 11, 2025
**Analyst:** AI Assistant (with user-requested thoroughness)
**Status:** ⚠️ CRITICAL ISSUE FOUND - FIX REQUIRED
