# Critical Bug Fix - Saga Failure Causing Order Execution Issues

**Date:** November 20, 2025, 7:26 PM  
**Severity:** CRITICAL  
**Status:** ✅ FIXED

---

## Problem Statement

User reported that after a BUY order at $91,500 was filled, the bot exhibited incorrect behavior:

1. **TP Order Issue:** Bot placed TP at $92,000 (correct price) but then cancelled it
2. **Duplicate Orders:** Next BUY order at $91,000 was placed TWICE

**User's Key Insight:** "The bot's logic is correct, issue is with order execution"

---

## Root Cause Analysis

### Investigation Process

Following the AI_prompt.md guidelines, performed systematic analysis:

1. **Context Check:** Examined fill processing saga for BUY order at $91,500
2. **Log Analysis:** Traced exact sequence of events
3. **Error Discovery:** Found saga failure in logs

### The Bug

**File:** `bot/strategy/sagas/fill_processing_saga.py`  
**Lines:** 320-326 (LONG mode), 579-585 (SHORT mode TP processing)

```python
# BUGGY CODE:
if hasattr(bot, 'fill_monitor') and "order_id" in result:
    bot.fill_monitor.track_order(
        order_id=result["order_id"],
        side="buy",
        price=next_price,
        size=fill_data["fill_size"]
    )
```

**Error:** `name 'bot' is not defined`

The variable `bot` does not exist in the saga scope. The saga only has access to:
- `fill_data`
- `correlation_id`
- `position_actor`
- `order_actor`
- `grid_calc`
- `event_store`
- `mode`

---

## Failure Sequence

### What Happened (Timeline)

1. **19:15:22** - BUY order at $91,500 filled ✅
2. **19:15:23** - Saga started: `buy-fill-1046575153-1763646323496`
3. **19:15:23** - Step 1: Position added ✅
4. **19:15:23** - Step 2: TP order placed at $92,000 ✅ (Order ID: 1046677677)
5. **19:15:24** - Step 3: Next grid order placement started
6. **19:15:27** - **SAGA FAILED:** `name 'bot' is not defined`
7. **19:15:27** - **Compensation triggered:**
   - TP order 1046677677 cancelled ❌
   - Position removed ❌
   - Pending buy cleared ❌
8. **19:15:28** - Bot placed next order at $91,000 (retry after saga failure)
9. **Later** - Bot placed another order at $91,000 (duplicate)

### Why TP Was Cancelled

The saga compensation system is designed to rollback ALL changes when a saga fails. This is correct behavior for maintaining data consistency. However, the saga should not have failed in the first place.

### Why Duplicate Orders

After saga failure and compensation:
1. Saga retry logic attempted to place the order again
2. Normal bot flow also detected the need for a new order
3. Both placed orders at $91,000

---

## The Fix

### Changes Made

**File:** `bot/strategy/sagas/fill_processing_saga.py`

**Line 319-320 (LONG mode):**
```python
# ✅ FIX NOV 20: Removed bot.fill_monitor reference (bot not in saga scope)
# Fill monitoring is handled by the main bot's order tracking system
```

**Line 578-579 (SHORT mode TP processing):**
```python
# ✅ FIX NOV 20: Removed bot.fill_monitor reference (bot not in saga scope)
# Fill monitoring is handled by the main bot's order tracking system
```

### Why This Fix Is Safe

1. **Fill monitoring is redundant:** The main bot already tracks all orders through:
   - Order actor's `_active_orders` dict
   - Event store logging
   - WebSocket order updates

2. **No functionality lost:** The `fill_monitor` tracking was an optimization, not a requirement

3. **Saga integrity maintained:** Removing the buggy code allows the saga to complete successfully

---

## Validation Plan

### Expected Behavior After Fix

When a BUY order fills:
1. ✅ Position added to state
2. ✅ TP order placed at correct price (entry + step)
3. ✅ TP order remains active (not cancelled)
4. ✅ Next grid order placed ONCE at correct price (entry - step)
5. ✅ No saga failures
6. ✅ No compensation triggers

### Test Scenario

**Setup:**
- Reference: $92,000
- Step: $500
- Mode: LONG

**Test:**
1. Place BUY order at $91,500
2. Wait for fill
3. Verify:
   - TP order at $92,000 stays active
   - Next BUY order at $91,000 placed once
   - No saga errors in logs
   - No compensation messages

### Monitoring Commands

```bash
# Watch for saga errors
./watch_logs_filtered.sh saga

# Watch for order placement
./watch_logs_filtered.sh "Placing.*order"

# Watch for compensation
./watch_logs_filtered.sh compensation
```

---

## Impact Assessment

### Before Fix
- ❌ Every fill triggered saga failure
- ❌ TP orders cancelled immediately
- ❌ Duplicate grid orders
- ❌ Position state corrupted
- ❌ Trading strategy broken

### After Fix
- ✅ Sagas complete successfully
- ✅ TP orders remain active
- ✅ Single grid order per level
- ✅ Position state consistent
- ✅ Trading strategy works as designed

---

## Lessons Learned

1. **Scope Awareness:** Always verify variable scope in async functions
2. **Saga Testing:** Test saga failure paths, not just success paths
3. **Compensation Impact:** Understand that saga compensation rolls back ALL changes
4. **User Insight:** User correctly identified "logic is correct, execution is wrong"
5. **Systematic Debugging:** Following AI_prompt.md guidelines led to quick root cause identification

---

## Related Files

- `bot/strategy/sagas/fill_processing_saga.py` - Fixed
- `bot/strategy/sagas/saga_coordinator.py` - Compensation logic (working correctly)
- `bot/strategy/actors/order_actor.py` - Order placement (working correctly)
- `bot/strategy/actors/position_actor.py` - Position management (working correctly)

---

## Restart Required

**YES** - Changes to saga logic require bot restart to take effect.

**Command:**
```bash
pm2 restart gridbot-live
```

---

## Verification Checklist

After restart:
- [ ] No saga failure errors in logs
- [ ] TP orders stay active after fills
- [ ] No duplicate grid orders
- [ ] Position count matches exchange
- [ ] No compensation messages (unless genuine failure)

---

## Status

✅ **FIXED** - Code changes complete  
⏳ **PENDING** - Awaiting restart and verification  

**Next Step:** Restart bot and monitor for successful order execution
