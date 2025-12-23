# Fill Processing Test Plan - November 8, 2025

## Objective
Verify that architectural fixes enable complete fill processing: WebSocket detection → Queue → Worker → Callback → TP order + Next grid order

---

## Pre-Test Checklist

### 1. Code Changes Verified ✅
- [x] WebSocketHandler: Validation, statistics, error handling added
- [x] FillDetector: Blocking fixed, deadlock prevented, thread-safe stats
- [x] Syntax validation: No Python compilation errors
- [x] Documentation: ARCHITECTURAL_FIXES_NOV8_2025.md created

### 2. Environment Ready
- [ ] Bot stopped: `pm2 stop gridbot-live`
- [ ] Clean logs: `pm2 flush gridbot-live` (optional)
- [ ] State verified: Check `runtime_state.json` for current positions
- [ ] Market conditions: Verify market is active (not maintenance)

### 3. Monitoring Setup
- [ ] Terminal 1: `pm2 logs gridbot-live --lines 100`
- [ ] Terminal 2: `tail -f bot/logs/bot.log`
- [ ] Terminal 3: Available for commands
- [ ] Telegram notifications: Enabled

---

## Test Execution

### Phase 1: Bot Startup Verification

**Action**: Start bot
```bash
pm2 start gridbot-live
```

**Expected Logs** (within 10 seconds):
```
✅ WebSocketHandler initialized
✅ FillDetector initialized (queue_size=100, dedup_size=5000)
✅ Registered fill callback: <bound method>
✅ WebSocket manager validated (methods: on_price_update, on_fill)
🚀 Fill processor worker started
✅ WebSocket connected to wss://socket.india.delta.exchange
```

**Verification Checklist**:
- [ ] All modules initialized without errors
- [ ] Fill processor thread started
- [ ] WebSocket connected
- [ ] Callbacks registered
- [ ] No validation errors

**Failure Recovery**:
- If validation fails → Check WebSocket manager has required methods
- If thread fails to start → Check threading.Lock initialization
- If connection fails → Check network/exchange status

---

### Phase 2: WebSocket Data Flow Verification

**Monitoring** (first 2 minutes):
```bash
grep "price_update\|heartbeat\|No messages" bot/logs/bot.log | tail -20
```

**Expected Behavior**:
- Price updates every 1-2 seconds
- Heartbeat warnings if no messages for 30+ seconds
- **Critical**: Should NOT see "No messages for 39s" repeatedly

**Verification Checklist**:
- [ ] Price updates flowing
- [ ] Latency < 1 second
- [ ] No data starvation warnings
- [ ] Orderbook updates visible

**If Data Starvation Detected**:
- 🚨 CRITICAL ISSUE: REST API fallback needed
- Document in logs: timestamps, frequency, duration
- Bot will be blind to fills during starvation periods

---

### Phase 3: Fill Detection Test (CRITICAL)

**Scenario**: Wait for pending order to fill OR place test order

**Current Pending Order**:
- Order ID: 1027796346
- Price: $101,500
- Side: BUY
- Size: 1 lot

**Alternative**: Place test order at market price if impatient

**Expected Log Sequence** (within 1 second of fill):
```
🎯 FINAL FILL: buy +1.0 lots @ avg $101,500.00
📥 process_websocket_fill() CALLED - Order: 1027796346
✅ Fill validation passed
✅ Fill queued successfully: 1027796346 @ $101,500 (queue depth: 1, total queued: 1)
🔄 Processing fill: BUY 1.0 @ $101,500.00 (Order: 1027796346)
✅ Fresh state loaded from disk before fill processing
✅ Fill processed successfully via callback
```

**Verification Checklist**:
- [ ] "📥 process_websocket_fill() CALLED" appears
- [ ] "✅ Fill queued successfully" appears
- [ ] "🔄 Processing fill" appears
- [ ] "✅ Fill processed successfully" appears
- [ ] No errors between detection and callback completion
- [ ] All logs appear within 1 second of fill

**Timing Check**:
- WebSocket detection → Queue: < 0.1s
- Queue → Worker pickup: < 1s
- Worker → Callback complete: < 2s
- **Total latency**: < 3 seconds

---

### Phase 4: Order Placement Verification (CRITICAL)

**Expected Actions** (within 5 seconds of fill):
1. **TP Order Placement**:
   - Side: SELL
   - Size: 1 lot
   - Price: $101,500 + TP_DISTANCE (check config)
   - Order type: Limit

2. **Next Grid BUY Order**:
   - Side: BUY
   - Size: 1 lot
   - Price: $101,500 - GRID_SPACING (check config)
   - Order type: Limit

**Expected Logs**:
```
📤 Placing TP order: SELL 1 @ $102,000 (protective)
✅ TP order placed: [order_id]
📤 Placing next grid order: BUY 1 @ $101,000
✅ Next grid order placed: [order_id]
💾 State persisted: 1 positions, next buy: [order_id]
```

**Verification Checklist**:
- [ ] TP order placed successfully
- [ ] TP order ID logged
- [ ] Next grid order placed successfully
- [ ] Next grid order ID logged
- [ ] State file updated (check `runtime_state.json`)
- [ ] Position count incremented
- [ ] No errors during order placement

**Via Delta Exchange UI**:
- [ ] TP order visible in "Open Orders"
- [ ] Next grid order visible in "Open Orders"
- [ ] Position shown in "Positions"
- [ ] P&L tracking started

---

### Phase 5: State Consistency Check

**Action**: Verify runtime state matches reality

```bash
cat runtime_state.json | jq '.'
```

**Expected State**:
```json
{
  "version": "2.0",
  "open_tranches": [
    {
      "order_id": "1027796346",
      "entry_price": 101500.0,
      "size": 1.0,
      "entry_time": "2025-11-08T19:14:02Z",
      "tp_order_id": "[new_tp_order_id]",
      "status": "filled"
    }
  ],
  "pending_buy": {
    "order_id": "[new_buy_order_id]",
    "price": 101000.0,
    "size": 1.0
  },
  "last_persist": "2025-11-08T[current_time]Z",
  "checksum": "[hash]"
}
```

**Verification Checklist**:
- [ ] open_tranches contains filled position
- [ ] tp_order_id matches TP order from logs
- [ ] pending_buy contains new grid order
- [ ] last_persist timestamp recent (< 30s)
- [ ] checksum present

---

### Phase 6: Statistics Verification

**Action**: Check callback and queue statistics

```bash
# In Python console or via bot command
from bot.strategy.modules.websocket_handler import WebSocketHandler
from bot.strategy.modules.fill_detector import FillDetector

# WebSocket Handler Stats
handler.get_stats()
# Expected: {'fills': 1, 'fill_errors': 0, 'total_errors': 0}

# Fill Detector Stats
detector.get_queue_stats()
# Expected: {'current_depth': 0, 'max_depth': 1, 'total_queued': 1, 
#            'total_processed': 1, 'drops': 0, 'is_processing': True}
```

**Verification Checklist**:
- [ ] fills = 1 (one successful fill processed)
- [ ] fill_errors = 0 (no errors)
- [ ] total_queued = 1
- [ ] total_processed = 1
- [ ] drops = 0 (no queue overflows)
- [ ] is_processing = True (worker thread alive)

---

## Success Criteria

### Minimum Requirements (MUST PASS)
- [x] Bot starts without errors
- [ ] WebSocket data flowing (no starvation)
- [ ] Fill detected by WebSocket
- [ ] `process_websocket_fill()` called
- [ ] Fill queued successfully
- [ ] Worker thread processes fill
- [ ] Callback executes without errors
- [ ] TP order placed
- [ ] Next grid order placed
- [ ] State persisted correctly

### Performance Requirements
- [ ] Total latency < 5 seconds (fill detection → order placement)
- [ ] No queue blocking (WebSocket thread never stalls)
- [ ] No deadlocks (all locks acquired/released properly)
- [ ] Statistics accurate (matches actual events)

### Reliability Requirements
- [ ] No crashes under normal operation
- [ ] Error isolation working (callback errors don't crash system)
- [ ] Resource cleanup (no memory leaks over time)

---

## Failure Scenarios & Recovery

### Scenario 1: "process_websocket_fill() CALLED" Never Appears
**Root Cause**: Callback not registered or WebSocket handler not routing

**Debug Steps**:
1. Check callback registration: `grep "Registered fill callback" bot/logs/bot.log`
2. Check WebSocket routing: Look for fill detection in ws_manager
3. Check validation: WebSocket manager might have failed validation

**Recovery**: Review callback wiring in gridbot.py initialization

---

### Scenario 2: "Fill queued successfully" Never Appears
**Root Cause**: Validation failing or queue operation error

**Debug Steps**:
1. Check fill validation logs (order_id, fill_price checks)
2. Check queue full errors (should be logged if queue overflowing)
3. Check for exceptions in process_websocket_fill()

**Recovery**: Review fill_detector.py validation logic

---

### Scenario 3: "Processing fill" Never Appears
**Root Cause**: Worker thread not running or queue not being consumed

**Debug Steps**:
1. Check worker thread status: `grep "Fill processor worker started" bot/logs/bot.log`
2. Check for worker thread crashes: `grep "Error in fill processor" bot/logs/bot.log`
3. Check queue depth: If growing unbounded, worker is stuck

**Recovery**: Review _process_fill_queue() for errors or deadlocks

---

### Scenario 4: "Fill processed successfully" Never Appears
**Root Cause**: Callback execution failing or deadlock

**Debug Steps**:
1. Check for callback errors: `grep "Error in fill processed callback" bot/logs/bot.log`
2. Check for deadlock: If logs stop abruptly, thread may be blocked
3. Check state lock: Verify state_lock not held during callback execution

**Recovery**: Review _process_single_fill_safe() implementation

---

### Scenario 5: Orders Not Placed After Callback Success
**Root Cause**: Issue in fill handler logic (long_handler/short_handler)

**Debug Steps**:
1. Check handler logs: Look for order placement attempts
2. Check position manager state: Verify position recorded correctly
3. Check order manager: Verify order placement logic executing

**Recovery**: Review handlers/long_handler.py or handlers/short_handler.py

---

## Post-Test Analysis

### If Test Passes ✅
1. Document success in ARCHITECTURAL_FIXES_NOV8_2025.md
2. Update test status: "Integration Testing: PASSED"
3. Proceed to Phase 3: Stress Testing (multiple concurrent fills)
4. Plan REST API fallback implementation (WebSocket starvation still exists)

### If Test Fails ❌
1. Capture complete logs: `pm2 logs gridbot-live > test_failure_logs.txt`
2. Capture state file: `cp runtime_state.json test_failure_state.json`
3. Document failure mode in new file: `TEST_FAILURE_ANALYSIS_[timestamp].md`
4. Provide user with:
   - Exact failure point (which log never appeared)
   - Relevant code section (file + line numbers)
   - Proposed fix or additional debugging needed

---

## Long-Term Monitoring (24h Production Run)

After successful test, monitor for 24 hours:

**Metrics to Track**:
- Total fills processed
- Average fill processing latency
- Queue depth over time
- Worker thread uptime
- Callback error rate
- WebSocket starvation events
- State persistence frequency

**Alert Conditions**:
- Queue depth > 50 (system overload)
- Fill errors > 5% (callback problems)
- WebSocket starvation > 10 events/hour (needs REST fallback)
- Worker thread crashes (critical failure)
- State checksum mismatches (data corruption)

---

**Test Plan Created**: November 8, 2025  
**Version**: 1.0  
**Status**: Ready for execution  
**Risk Level**: MEDIUM (WebSocket starvation unresolved, but fill processing should work during data flow periods)
