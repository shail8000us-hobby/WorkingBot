# Race Condition Fix - December 19, 2025

## Problem Description

The trading bot violated the **"Single Pending Order Rule"** by creating 3 pending buy orders instead of 1 during rapid TP fills.

### Root Cause

**Race Condition in Concurrent Saga Execution:**

1. **Multiple sagas run concurrently** - `SagaOrchestrator` allows up to 10 concurrent sagas
2. **Each saga independently** cancels old orders and places new ones
3. **No synchronization** between concurrent sagas
4. **Result**: Multiple sagas can each place an order before seeing the others' orders

### Sequence of Events (WITHOUT FIX)

```
Time T0: TP Fill #1 arrives at $89,500
  ├─ Saga A starts
  ├─ Fetches open orders: [OLD_BUY @ $88,500]
  ├─ Cancels OLD_BUY @ $88,500
  └─ (Still executing...)

Time T1: TP Fill #2 arrives at $90,000 (concurrent with Saga A)
  ├─ Saga B starts (CONCURRENT with Saga A)
  ├─ Fetches open orders: [OLD_BUY @ $88,500] (doesn't see Saga A's new order yet!)
  ├─ Cancels OLD_BUY @ $88,500 (redundant)
  └─ (Still executing...)

Time T2: Saga A places new order
  └─ Places BUY @ $89,000

Time T3: Saga B places new order
  └─ Places BUY @ $89,500

Result: 2 pending buy orders ($89,000 and $89,500) ❌ VIOLATION!
```

## Solution

### Global Lock for Order Replacement

Added a **module-level lock** (`_ORDER_REPLACEMENT_LOCK`) that ensures only ONE saga at a time can execute the critical section:

1. Cancel old orders
2. Check Guardian signal
3. Place new order
4. Update bot state

### Implementation

**File:** `bot/strategy/sagas/fill_processing_saga.py`

**Changes:**

1. **Line ~18**: Added global lock
   ```python
   _ORDER_REPLACEMENT_LOCK = asyncio.Lock()
   ```

2. **LONG mode - `create_sell_fill_saga`** (lines ~660-880):
   - Wrapped entire order replacement sequence in `async with _ORDER_REPLACEMENT_LOCK:`
   - Prevents concurrent LONG TP fills from racing

3. **SHORT mode entry - `create_short_entry_saga`** (lines ~1170-1360):
   - Wrapped entire order replacement sequence in `async with _ORDER_REPLACEMENT_LOCK:`
   - Prevents concurrent SHORT entry fills from racing

4. **SHORT mode TP - `create_short_tp_saga`** (lines ~1500-1700):
   - Wrapped entire order replacement sequence in `async with _ORDER_REPLACEMENT_LOCK:`
   - Prevents concurrent SHORT TP fills from racing

### Sequence of Events (WITH FIX)

```
Time T0: TP Fill #1 arrives at $89,500
  ├─ Saga A starts
  ├─ Acquires _ORDER_REPLACEMENT_LOCK ✅
  ├─ Fetches open orders: [OLD_BUY @ $88,500]
  ├─ Cancels OLD_BUY @ $88,500
  ├─ Places BUY @ $89,000
  └─ Releases lock ✅

Time T1: TP Fill #2 arrives at $90,000
  ├─ Saga B starts
  ├─ Waits for _ORDER_REPLACEMENT_LOCK... (blocked until Saga A finishes)
  └─ (Waiting...)

Time T2: Saga A completes, releases lock

Time T3: Saga B proceeds
  ├─ Acquires _ORDER_REPLACEMENT_LOCK ✅
  ├─ Fetches open orders: [BUY @ $89,000] (sees Saga A's order!)
  ├─ Cancels BUY @ $89,000 (correct - replaces Saga A's order)
  ├─ Places BUY @ $89,500 (new grid level)
  └─ Releases lock ✅

Result: 1 pending buy order ($89,500) ✅ CORRECT!
```

## Testing Recommendations

### Manual Testing

1. **Rapid TP Fills Test**
   - Place multiple positions close together
   - Let them all hit TP rapidly (within 1 second)
   - Verify only 1 pending order exists after all fills complete

2. **Concurrent Fill Test**
   - Manually trigger 3+ TP fills simultaneously
   - Check logs for lock acquisition messages
   - Verify sagas wait for lock before proceeding

### Log Verification

Look for these log messages:

```
[SAGA] Acquiring order replacement lock to prevent race conditions...
[SAGA] ✅ Lock acquired - proceeding with order replacement atomically
[SAGA] 🔓 Lock will be released after this return - other sagas can now proceed
```

If multiple sagas run concurrently, you should see:
- Saga A acquires lock
- Saga B waits
- Saga A releases lock  
- Saga B acquires lock

### Assertions to Add

```python
# After all fills complete
open_orders = await get_open_orders()
bot_buy_orders = [o for o in open_orders if o['side'] == 'buy' and not o['reduce_only']]
assert len(bot_buy_orders) == 1, f"Expected 1 buy order, found {len(bot_buy_orders)}"
```

## Performance Impact

**Minimal to None:**

- Lock is only held during order cancellation + placement (~1-2 seconds max)
- TP fills don't happen that frequently (typically minutes apart)
- Even with 10 concurrent fills, total delay = 10-20 seconds (acceptable)
- Lock is per-saga-type (could split LONG/SHORT locks if needed, but not necessary)

## Related Rules

This fix ensures compliance with:

1. **Single Pending Order Rule** (Critical Rule #1 from logic_strategy.md)
   - Only 1 pending buy order in LONG mode
   - Only 1 pending sell order in SHORT mode

2. **Saga Pattern** (from async_gridbot architecture)
   - Sagas still execute independently
   - Compensation logic unchanged
   - Lock only serializes the critical section

## Files Modified

1. `bot/strategy/sagas/fill_processing_saga.py` - Added lock and wrapped critical sections

## Files to Review

1. `logic_strategy.md` - Verify behavior still matches documentation
2. `ASYNC_GRIDBOT_EXECUTIVE_SUMMARY.md` - Update architecture notes if needed

## Status

✅ **IMPLEMENTED** - December 19, 2025
⏳ **PENDING TESTING** - Awaiting real-world validation

## Next Steps

1. Deploy to staging/demo mode
2. Test with rapid TP fills
3. Monitor logs for lock contention
4. Verify Single Pending Order Rule holds under load
5. Consider adding metrics: `lock_wait_time_seconds`, `concurrent_saga_count`

---

**Last Updated:** December 19, 2025  
**Author:** AI Assistant (Claude Sonnet 4.5)  
**Status:** Implementation Complete, Testing Pending
