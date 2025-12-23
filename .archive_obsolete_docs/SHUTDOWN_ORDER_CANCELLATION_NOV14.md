# Shutdown Order Cancellation Fix - November 14, 2025

## Problem Identified

**Issue:** Bot was not cancelling pending entry orders on shutdown, leading to:
- Orphaned entry orders filling after bot stops
- New positions opening without TP protection
- Unmonitored positions with no automatic profit-taking

## Root Cause Analysis

**File:** `bot/strategy/async_gridbot.py`  
**Method:** `async def stop()` (line 965)

The shutdown sequence was:
1. Stop saga orchestrator
2. Stop actors
3. Disconnect WebSocket
4. Close API client

**Missing:** No cancellation of pending entry orders before shutdown

## Solution Implemented

### 1. Added Pending Order Cancellation to Shutdown Sequence

**File:** `bot/strategy/async_gridbot.py`  
**Lines:** 965-981

```python
async def stop(self) -> None:
    """Gracefully stop all components."""
    log.info("Stopping AsyncGridBot...")
    self._running = False
    
    # NOV 14: Cancel pending entry orders before shutdown
    await self._cancel_pending_orders_on_shutdown()
    
    # NOV 13: Send shutdown notification
    await self._send_shutdown_notification()
    
    # Stop saga orchestrator
    await self.saga_orchestrator.stop_all(timeout=30.0)
    
    # Stop actors
    await self.position_actor.stop(timeout=5.0)
    await self.order_actor.stop(timeout=5.0)
```

### 2. New Method: `_cancel_pending_orders_on_shutdown()`

**File:** `bot/strategy/async_gridbot.py`  
**Lines:** 3013-3134

**Functionality:**
- Retrieves current state from PositionActor
- Cancels pending BUY orders (LONG mode entry orders)
- Cancels pending SELL orders (SHORT mode entry orders)
- Clears pending order state from PositionActor
- Provides detailed logging of actions taken

**What is Cancelled:**
- `pending_buy` - Entry order in LONG mode
- `pending_sell` - Entry order in SHORT mode

**What is Preserved:**
- Open positions (in `open_tranches`)
- TP orders (reduce_only=True) protecting existing positions
- Manual orders/positions (never touched by bot)

## Code Flow

### Shutdown Sequence (Updated)

```
1. stop() called
   ↓
2. _cancel_pending_orders_on_shutdown()
   ↓
   2a. Get state from position_actor.ask("GET_STATE")
   ↓
   2b. Check pending_buy
       → If exists: order_actor.ask("CANCEL_ORDER", {order_id})
       → Clear: position_actor.tell("CLEAR_PENDING_BUY")
   ↓
   2c. Check pending_sell
       → If exists: order_actor.ask("CANCEL_ORDER", {order_id})
       → Clear: position_actor.tell("CLEAR_PENDING_SELL")
   ↓
   2d. Log summary (cancelled count, preserved positions)
   ↓
3. _send_shutdown_notification()
   ↓
4. Stop saga orchestrator
   ↓
5. Stop actors
   ↓
6. Disconnect WebSocket
   ↓
7. Close API client
   ↓
8. Complete shutdown
```

## Integration Points

### OrderActor Integration
- Uses existing `_handle_cancel_order()` method
- **File:** `bot/strategy/actors/order_actor.py`, line 455
- **Message type:** "CANCEL_ORDER"
- **Payload:** `{"order_id": <string>}`
- **Response:** `{"status": "ok"|"error", "order_id": <string>}`

### PositionActor Integration
- Uses existing `_handle_get_state()` method (line 320)
- Uses existing `_handle_clear_pending_buy()` method (line 217)
- Uses existing `_handle_clear_pending_sell()` method (line 256)
- **No new methods required**

### API Integration
- Uses existing `AsyncDeltaClient.cancel_order()` method
- **File:** `bot/api/async_delta_client.py`
- Cancellation happens via OrderActor for proper event logging

## Error Handling

1. **State Retrieval Failure:**
   - Logs warning
   - Skips cancellation gracefully
   - Continues shutdown sequence

2. **Individual Order Cancellation Failure:**
   - Logs error with order details
   - Continues to next pending order
   - Does not block shutdown

3. **Unexpected Exceptions:**
   - Caught at method level
   - Full traceback logged
   - Shutdown proceeds normally

## Logging Output

### Example 1: Pending Orders Cancelled
```
======================================================================
🧹 SHUTDOWN: Cancelling pending entry orders...
======================================================================
🗑️  Cancelling pending BUY @ $99,000 (Order: 12345678)
   ✅ Cancelled pending BUY order
======================================================================
✅ Cancelled 1 pending entry order(s)
📊 Preserving 3 open position(s) with TP protection
======================================================================
```

### Example 2: No Pending Orders
```
======================================================================
🧹 SHUTDOWN: Cancelling pending entry orders...
======================================================================
ℹ️  No pending entry orders to cancel
📊 Preserving 3 open position(s) with TP protection
======================================================================
```

## Testing Checklist

- [ ] Test shutdown with pending BUY order (LONG mode)
- [ ] Test shutdown with pending SELL order (SHORT mode)
- [ ] Test shutdown with no pending orders
- [ ] Test shutdown with both BUY and SELL pending
- [ ] Verify open positions are preserved
- [ ] Verify TP orders remain active
- [ ] Test error handling (network failure during cancel)
- [ ] Verify state cleanup in PositionActor
- [ ] Check event logging in EventStore

## Migration Notes

### Before This Fix
```python
# OLD BEHAVIOR
1. Bot stops
2. Pending BUY @ $99,000 still on exchange
3. Price moves to $99,000
4. Order fills → new position opened
5. Bot is stopped → NO TP PLACED
6. Position unprotected
```

### After This Fix
```python
# NEW BEHAVIOR
1. Bot stops
2. Pending BUY @ $99,000 cancelled
3. Price moves to $99,000
4. No fill (order cancelled)
5. Existing positions preserved with TPs
6. Clean shutdown
```

## Related Files

- `bot/strategy/async_gridbot.py` - Main bot class (stop method updated)
- `bot/strategy/actors/order_actor.py` - Order cancellation handler
- `bot/strategy/actors/position_actor.py` - State management
- `bot/api/async_delta_client.py` - API cancel_order method

## Compatibility

- ✅ Backward compatible (no breaking changes)
- ✅ Works with existing actor message protocol
- ✅ Works with existing event logging
- ✅ No changes to saga patterns
- ✅ No database schema changes

## Future Enhancements

1. **Option to preserve pending orders:**
   - Add `cancel_pending_on_shutdown` config parameter
   - Default: True (safe default)
   - Advanced users can set False to keep orders active

2. **Selective cancellation:**
   - Option to cancel only orders beyond certain distance from market
   - Preserve very close pending orders that are likely to fill safely

3. **Restart detection:**
   - If bot restarts within X seconds, re-establish cancelled orders
   - Requires persistent state tracking across restarts

## Verification Commands

```bash
# Check for pending orders after shutdown
# Should return empty list for bot-placed orders
python -c "from bot.api.async_delta_client import AsyncDeltaClient; import asyncio; client = AsyncDeltaClient(...); asyncio.run(client.get_open_orders())"

# Check position actor state file
cat bot/reports/state.json | jq '.pending_buy, .pending_sell'
# Should show: null, null
```

## Author
AsyncGridBot Team - November 14, 2025

## Status
✅ IMPLEMENTED  
⏳ AWAITING PRODUCTION TESTING
