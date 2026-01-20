# Critical Bug Fix: Missed Fill Detection (Jan 20, 2026)

## Problem Summary
Order 1130290549 (BUY @ $92,500) filled on exchange at **04:33:37 AM** but bot never detected it.

### Root Cause
**WebSocket Message Queue Overflow**
- At 04:31:12 AM (2 minutes before fill): Queue overflow
- **26,801 messages DROPPED** due to slow consumer
- Fill notification was in those dropped messages
- Bot still thinks order is pending (2+ hours later)

### Impact
- **Unhedged position**: 0.005 BTC at $92,500 entry with NO TP order
- Position count incorrect (shows 5, should be 6)
- Safety systems failed to detect:
  - Orphan TP detection only runs at startup
  - Reconciliation loop doesn't actually reconcile
  - Safety gatekeeper only logs timestamp

---

## Phase 2 Implementation (COMPLETED)

### 1. ✅ Increased WebSocket Queue Size
**File:** `bot/delta_websocket/async_ws_manager.py` line 251
- **Before:** `asyncio.Queue(maxsize=10000)`
- **After:** `asyncio.Queue(maxsize=50000)`
- **Impact:** 5x larger buffer prevents message drops during burst traffic
- **Risk:** ✅ None - just allocates more memory (~8MB additional)

### 2. ✅ Fill Polling Fallback
**File:** `bot/strategy/async_gridbot.py`
- **New method:** `_fill_polling_fallback_loop()`
- **Behavior:**
  - Polls exchange every 60 seconds for recent fills
  - Checks against `_seen_fill_ids` for deduplication
  - Processes missed fills through normal `_process_fill()` handler
  - Logs WARNING when missed fill is detected
- **Added to tasks:** Line 1570
- **Risk:** ✅ Low - uses existing deduplication, isolated task
- **Impact:** Catches missed fills within 60 seconds

### 3. ✅ Unhedged Position Detection
**File:** `bot/strategy/async_gridbot.py`
- **New method:** `_check_for_unhedged_positions()`
- **Modified:** `_safety_gatekeeper_loop()` line 3616
- **Behavior:**
  - Runs every 5 minutes (existing safety gatekeeper interval)
  - Queries bot positions vs exchange orders
  - Detects positions without TP orders
  - Logs CRITICAL ERROR with position details
  - Provides manual remediation instructions
- **Risk:** ✅ Low - read-only check, doesn't modify state
- **Impact:** Alerts on unhedged positions within 5 minutes

---

## Testing Checklist

### Before Restart
- [x] Review all code changes
- [x] Verify no trading logic modified
- [x] Verify no order execution modified
- [ ] **MANUALLY PLACE TP ORDER** for $92,500 position (SELL @ $93,000, reduce_only)

### After Restart
- [ ] Verify bot starts successfully
- [ ] Check logs for "Fill polling fallback started"
- [ ] Check logs for "Safety gatekeeper loop started"
- [ ] Monitor for first "Fill polling: No missed fills" (after 3 min)
- [ ] Monitor for first safety check run (after 5 min)
- [ ] Verify WebSocket queue size in stats endpoint

### Production Monitoring (First 24 Hours)
- [ ] Watch for "FILL POLLING FALLBACK: Missed fill detected"
- [ ] Watch for "CRITICAL: UNHEDGED POSITIONS DETECTED"
- [ ] Monitor WebSocket message drop warnings
- [ ] Check PM2 logs for task health
- [ ] Verify all 5 existing positions still have TP orders

---

## Files Modified

1. **bot/delta_websocket/async_ws_manager.py**
   - Line 251: Increased queue size 10K → 50K

2. **bot/strategy/async_gridbot.py**
   - Line 1570: Added fill_polling task to task list
   - Line 3595: Added `_fill_polling_fallback_loop()` method
   - Line 3616: Modified `_safety_gatekeeper_loop()` to call unhedged check
   - Line 3625: Added `_check_for_unhedged_positions()` method

---

## Deployment Instructions

### 1. Protect Existing Position (DO FIRST)
```bash
# Go to Delta Exchange and manually place:
# - Type: SELL LIMIT
# - Price: $93,000
# - Size: 0.005 BTC (5 contracts)
# - Reduce Only: YES
# - Tag: GBOT_MANUAL_TP_92500
```

### 2. Restart Bot
```bash
pm2 restart gridbot-BTCUSD-LONG
pm2 logs gridbot-BTCUSD-LONG --lines 50
```

### 3. Verify Startup
Look for these log lines:
```
🔄 Fill polling fallback started - checking every 60 seconds
Safety gatekeeper loop started - checking every 5 minutes
```

### 4. First 10 Minutes
```bash
# Watch logs continuously
pm2 logs gridbot-BTCUSD-LONG

# Expected within 5 minutes:
🔒 Running periodic safety check (5-minute interval)...
✅ All positions have TP orders  # Or CRITICAL alert if still unhedged

# Expected within 3 minutes:
✅ Fill polling: No missed fills  # Or WARNING if more missed fills found
```

---

## Rollback Plan (If Issues Occur)

If bot behaves unexpectedly after restart:

```bash
# 1. Stop the bot
pm2 stop gridbot-BTCUSD-LONG

# 2. Revert changes
cd /Users/ssr/Projects/WorkingBot
git diff bot/delta_websocket/async_ws_manager.py
git diff bot/strategy/async_gridbot.py

# 3. If you have backup/git:
git checkout bot/delta_websocket/async_ws_manager.py
git checkout bot/strategy/async_gridbot.py

# 4. Restart with old code
pm2 restart gridbot-BTCUSD-LONG
```

---

## Future Improvements (Phase 3)

### Periodic Reconciliation (Next Week)
- Enable `_recover_from_state()` every 15 minutes
- Full position/order reconciliation
- Auto-heal orphaned positions

### WebSocket Reliability
- Add circuit breaker for WebSocket failures
- Auto-switch to REST polling if WebSocket unhealthy
- Better back-pressure handling in message consumer

### Monitoring Dashboards
- Add "Messages Dropped" counter
- Add "Unhedged Positions" widget
- Add "Last Reconciliation" timestamp
- Add "Fill Polling Status" indicator

---

## Lessons Learned

1. **Single Point of Failure:** WebSocket is only delivery mechanism for critical events
2. **Queue Sizing:** 10K was insufficient for burst traffic
3. **Safety Layers:** All 4 safety systems failed to catch this
4. **No Active Reconciliation:** Only runs at startup, not during runtime
5. **Monitoring Gaps:** No alerts on message drops or unhedged positions

---

## Change Log

**2026-01-20 06:45 AM**
- Increased WebSocket queue size (10K → 50K)
- Added fill polling fallback (60s interval)
- Added unhedged position detection (5min interval)
- Documented incident and fixes

**Status:** ✅ Ready for production deployment
**Approver:** [Pending]
**Deployed:** [Pending]
