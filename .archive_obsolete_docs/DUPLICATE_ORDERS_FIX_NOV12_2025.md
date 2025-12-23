# DUPLICATE ORDERS FIX - November 12, 2025

## Problem Identified

The bot was placing the SAME order repeatedly at 99000 because:

1. **No exchange order check on startup** - Bot didn't query Delta Exchange for existing open orders before placing new ones
2. **State desync** - Bot's internal state didn't match exchange reality
3. **No deduplication logic** - Every bot restart triggered a new order placement

Result: 5+ duplicate BUY orders at 99000 price level (as shown in user's screenshot)

## Root Cause

In `bot/strategy/async_gridbot.py`, the `_place_initial_order()` method:
- ✅ Checked bot's internal state for pending orders
- ❌ Did NOT check Delta Exchange for actual open orders
- ❌ Resulted in duplicate order placement on every restart

## Fix Applied

### 1. Added Exchange Order Check (Lines 480-520)

```python
# CRITICAL: Check exchange for existing open orders BEFORE placing new ones
log.info("🔍 Checking exchange for existing open orders...")
try:
    exchange_orders = await self.api_client.get_open_orders(product_id=self.product_id)
    if exchange_orders and len(exchange_orders) > 0:
        log.warning(f"⚠️  Found {len(exchange_orders)} existing open order(s) on exchange:")
        for order in exchange_orders:
            order_id = order.get('id')
            side = order.get('side')
            price = order.get('limit_price')
            size = order.get('size')
            log.warning(f"   Order {order_id}: {side} {size} @ ${price:,.2f}")
        
        # Sync the first relevant order to bot state
        for order in exchange_orders:
            order_side = order.get('side')
            if (self.mode == "LONG" and order_side == "buy") or (self.mode == "SHORT" and order_side == "sell"):
                order_id = order.get('id')
                order_price = order.get('limit_price')
                log.info(f"✅ Syncing existing order {order_id} to bot state")
                
                if order_side == "buy":
                    await self.position_actor.tell("SET_PENDING_BUY", {
                        "order_id": order_id,
                        "price": order_price,
                        "timestamp": time.time()
                    })
                else:
                    await self.position_actor.tell("SET_PENDING_SELL", {
                        "order_id": order_id,
                        "price": order_price,
                        "timestamp": time.time()
                    })
                
                self._initial_order_placed = True
                log.info("✅ Existing exchange order synced - bot will track it")
                return
        
        log.warning("⚠️  Existing orders found but none match current mode - continuing with new order")
    else:
        log.info("✅ No existing orders on exchange - safe to place new order")
except Exception as e:
    log.error(f"❌ Failed to check exchange orders: {e}")
    log.warning("⚠️  Proceeding with caution - may result in duplicate orders")
```

### 2. Created Cleanup Script

`cancel_duplicate_orders.py` - Utility to cancel all duplicate orders before starting bot

## Fix Behavior

**Before Fix:**
1. Bot starts
2. Checks internal state (empty on first start)
3. Places new order at 99000
4. Bot restarts (for any reason)
5. Internal state lost/reset
6. Places ANOTHER order at 99000
7. Repeat → 5+ duplicate orders

**After Fix:**
1. Bot starts
2. Checks internal state
3. **🆕 Queries Delta Exchange for existing open orders**
4. **🆕 If found, syncs existing order to bot state**
5. **🆕 Skips placing new order**
6. Bot tracks the existing order
7. No duplicates created

## How to Use

### Step 1: Cancel Existing Duplicates

```bash
python3 cancel_duplicate_orders.py
```

This will:
- Show all open orders
- Ask for confirmation
- Cancel all orders
- Provide summary

### Step 2: Start Bot with Fixed Code

```bash
python3 -m bot.run
```

Bot will now:
- ✅ Check exchange before placing orders
- ✅ Sync any existing orders to its state
- ✅ Avoid creating duplicates
- ✅ Log what it's doing for visibility

## Expected Log Output

When bot starts and finds existing orders:

```
🔍 Checking exchange for existing open orders...
⚠️  Found 1 existing open order(s) on exchange:
   Order 1033703977: buy 1 @ $99,000.00
✅ Syncing existing order 1033703977 to bot state
✅ Existing exchange order synced - bot will track it
```

When bot starts with no existing orders:

```
🔍 Checking exchange for existing open orders...
✅ No existing orders on exchange - safe to place new order
📍 Placing initial MAKER BUY order @ $99,000.00
✅ Initial MAKER BUY placed @ $99,000.00 (Order: 1033704123)
```

## Testing Checklist

- [x] Fix implemented in async_gridbot.py
- [x] Cleanup script created
- [ ] Cancel duplicate orders manually
- [ ] Start bot and verify single order placement
- [ ] Restart bot and verify no new duplicates
- [ ] Monitor for 30 minutes to ensure stability

## Files Modified

1. `bot/strategy/async_gridbot.py` - Added exchange order check in `_place_initial_order()`
2. `cancel_duplicate_orders.py` - NEW cleanup utility

## Safety Notes

- ⚠️ Always cancel duplicate orders before starting bot
- ⚠️ Monitor first few restarts to ensure fix is working
- ⚠️ Check Delta Exchange UI to verify order count matches expectations
- ✅ Bot now logs exchange order checks for transparency

## Next Steps

1. Cancel the 5 duplicate orders from screenshot
2. Start bot with fixed code
3. Verify only 1 order is placed
4. Test bot restart to ensure no new duplicates
5. Monitor for proper fill handling

---

**Status**: FIX READY FOR TESTING
**Date**: November 12, 2025 11:07 PM
**Priority**: CRITICAL (prevents capital lock-up in duplicate orders)
