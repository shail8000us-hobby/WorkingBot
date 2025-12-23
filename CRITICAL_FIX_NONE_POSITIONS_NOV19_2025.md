# CRITICAL FIX: None Position IDs Bug - November 19, 2025

## Problem Summary

The bot was stuck in an infinite loop placing emergency TP orders for positions with `None` IDs, resulting in 91+ failed orders between 10:48 AM and 12:25 PM.

## Root Cause

1. **Positions added without proper IDs**: Earlier recovery attempts (9:00-9:29 AM) added positions with `position_id = None`
2. **No validation**: PositionActor accepted positions with None IDs
3. **Persistent state**: Broken positions remained in memory across restarts
4. **Infinite loop**: Reconciliation system kept trying to place emergency TPs for these broken positions every 5 minutes

## Fixes Applied

### Fix 1: Position Validation in PositionActor
**File**: `bot/strategy/actors/position_actor.py`

Added validation to reject positions with None IDs:
```python
# CRITICAL FIX NOV 19: Validate position_id is not None
position_id = payload.get("position_id")
if not position_id or position_id == "None" or str(position_id).lower() == "none":
    log.error(f"❌ REJECTED position with invalid ID: {position_id}")
    return {"status": "error", "error": "Invalid position_id - cannot be None"}
```

Also added support for `entry_order_id` and `tp_order_id` fields for reconciliation compatibility.

### Fix 2: Broken Position Cleanup
**File**: `bot/strategy/actors/position_actor.py`

Added cleanup logic in state validation to remove positions with None IDs:
```python
# CRITICAL FIX NOV 19: Remove positions with None IDs
broken_positions = [p for p in valid_tranches if not p.get('position_id') or str(p.get('position_id')).lower() == 'none']
if broken_positions:
    log.critical(f"🚨 Found {len(broken_positions)} positions with None IDs - REMOVING THEM")
    # Remove and update state
```

### Fix 3: Skip Emergency TP for Broken Positions
**File**: `bot/strategy/async_gridbot.py`

Added validation to skip emergency TP placement for positions with None IDs:
```python
# CRITICAL FIX NOV 19: Skip emergency TP for broken positions with None IDs
if not entry_order_id or str(entry_order_id).lower() == "none":
    log.critical(f"❌ [EMERGENCY TP] SKIPPING - Position has None entry_order_id")
    return

if not position_id or str(position_id).lower() == "none":
    log.critical(f"❌ [EMERGENCY TP] SKIPPING - Position has None position_id")
    return
```

### Fix 4: Add entry_order_id to Normal Saga Positions
**File**: `bot/strategy/sagas/fill_processing_saga.py`

Updated both BUY and SELL sagas to include `entry_order_id`:
```python
position = {
    "position_id": position_id,
    "entry_order_id": position_id,  # For reconciliation compatibility
    "entry_price": fill_data["fill_price"],
    "tp_price": tp_price,
    "size": fill_data["fill_size"],
    "correlation_id": correlation_id
}
```

### Fix 5: Store tp_order_id After TP Placement
**File**: `bot/strategy/sagas/fill_processing_saga.py`

Added logic to update position with `tp_order_id` after successful TP placement:
```python
tp_order_id = result.get("order_id")
if tp_order_id:
    await position_actor.mailbox.put(
        Message("UPDATE_POSITION", {
            "position_id": position_id,
            "tp_order_id": str(tp_order_id)
        }, None, correlation_id)
    )
```

### Fix 6: Recovery Positions Already Fixed (Earlier)
**File**: `bot/strategy/async_gridbot.py`

Recovery positions already include both fields:
```python
position_data = {
    'position_id': str(order_id),
    'entry_order_id': str(order_id),  # For reconciliation compatibility
    'entry_price': grid_level,
    'actual_entry': fill_price,
    'tp_price': tp_price,
    'tp_order_id': str(tp_order_id),  # For reconciliation TP verification
    'size': self.lot_size,
    'is_opportunistic': True,
    'saved_capital': saved_capital
}
```

## Expected Behavior After Restart

1. **State validation runs on startup**
   - Detects 5 positions with None IDs
   - Removes them automatically
   - Logs: "🚨 Found 5 positions with None IDs - REMOVING THEM"

2. **No more emergency TP spam**
   - Reconciliation will find 0 unprotected positions
   - Or skip emergency TP if any broken positions remain

3. **Future positions validated**
   - Any attempt to add position with None ID will be rejected
   - Error logged: "❌ REJECTED position with invalid ID"

4. **All new positions include proper IDs**
   - `position_id`: Order ID
   - `entry_order_id`: Order ID (for reconciliation)
   - `tp_order_id`: TP order ID (set after TP placement)

## Testing Checklist

After restart:
- [ ] Check logs for "Found X positions with None IDs - REMOVING THEM"
- [ ] Verify reconciliation shows "All positions have TP protection"
- [ ] Confirm no "EMERGENCY TP" messages for None positions
- [ ] Verify new positions have all required ID fields
- [ ] Check that opportunistic recovery completes successfully

## Files Modified

1. `bot/strategy/actors/position_actor.py` - Validation and cleanup
2. `bot/strategy/async_gridbot.py` - Emergency TP skip logic
3. `bot/strategy/sagas/fill_processing_saga.py` - Add entry_order_id and tp_order_id

## Related Issues Fixed

- Opportunistic recovery positions now have proper IDs
- Normal saga positions now have proper IDs
- Reconciliation system can properly verify all positions
- Emergency TP system won't spam exchange with invalid orders

## Status

✅ **ALL FIXES APPLIED** - Ready for bot restart
