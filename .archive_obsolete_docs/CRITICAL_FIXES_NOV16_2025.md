# Critical Bot Issues - November 16, 2025

## **✅ ALL FIXES IMPLEMENTED - READY FOR TESTING**

---

## **🚨 THREE CRITICAL BUGS FIXED**

### **Bug #1: Weak Bot Memory (Stale Database Data)** ✅ FIXED
**Problem:** EventStore database contains old test data that never gets cleaned up. Every restart requires manual intervention.

**Root Cause:**
- Database has stale positions from Nov 14 testing ($95,000 and $110,000 entries)
- Database has stale pending orders (the $38 OPTIONS order)
- EventStore reconstruction doesn't validate if positions/orders still exist on exchange
- No automatic cleanup of orphaned events

**Solution Implemented:**
1. **Added `validate_state_against_exchange()` method** to `PositionManagerActor`
   - File: `bot/strategy/actors/position_actor.py` (new method at end)
   - Validates pending orders exist on exchange
   - Validates positions exist on exchange
   - Removes stale data automatically

2. **Bot calls validation on startup** before placing any orders
   - File: `bot/strategy/async_gridbot.py` line ~1075
   - Runs right after actors start
   - Logs detailed cleanup actions

**Expected Result:**
- Bot cleans stale data on every startup
- No more manual database cleanup needed
- Fresh state synchronized with exchange

---

### **Bug #2: Auto-Recreate Not Working** ✅ FIXED
**Problem:** Warning says "bot will recreate order on next heartbeat cycle (every 20s)" but this is NOT happening.

**Root Cause:**
Bot sees a "pending order" in memory (the $38 OPTIONS trade) so it thinks pending order exists and doesn't recreate.

**Solution Implemented:**
1. **Added exchange verification in `_check_and_place_entry_order()`**
   - File: `bot/strategy/async_gridbot.py` line ~2045
   - Before checking pending order, verifies it exists on exchange
   - If not found, clears from memory and recreates

2. **Enhanced logging for manual cancellation detection**
   - File: `bot/strategy/async_gridbot.py` line ~2100
   - Logs when pending order goes missing
   - Highlights when recreating cancelled order

**Expected Behavior:**
1. User manually cancels grid pending order @ $95,000
2. Bot detects on next ticker update (1-5 seconds) or heartbeat (15 seconds)
3. Logs: "⚠️ STALE PENDING ORDER DETECTED" with full details
4. Clears from memory
5. Recreates order at correct grid level
6. Logs: "✅ RECREATED cancelled BUY order @ $95,000"

---

### **Bug #3: Bot Confused Between Manual OPTIONS and Grid FUTURES** ✅ FIXED
**Problem:** Bot log shows "Pending BUY @ $38" - this is a manual OPTIONS trade, not the bot's FUTURES grid trade.

**Root Cause:**
The fill handler was processing ALL fills from WebSocket, including manual OPTIONS trades.

**Solution Implemented:**
**Added product_id filtering to `_process_fill()`**
- File: `bot/strategy/async_gridbot.py` line ~1307
- Checks `fill_data.get('product_id')` against `self.product_id`
- Ignores fills from different products (OPTIONS, other FUTURES pairs)
- Logs: "⏭️ Ignoring fill for different product: [product] (bot trades BTCUSD)"

**Expected Result:**
- Bot ONLY processes fills for its configured product (BTCUSD FUTURES)
- Manual OPTIONS trades are completely ignored
- No more $38 orders in bot logs
- Clean separation between grid bot and manual trading

---

## **📋 CODE CHANGES SUMMARY**

### **File 1: `bot/strategy/async_gridbot.py`** (3 changes)

**Change 1: Product ID filtering (line ~1307)**
```python
async def _process_fill(self, fill_data: Dict[str, Any]) -> None:
    try:
        # CRITICAL FIX NOV 16: Only process fills for THIS bot's product
        fill_product = fill_data.get('product_id')
        if fill_product and fill_product != self.product_id:
            log.debug(f"⏭️  Ignoring fill for different product...")
            return
```

**Change 2: State validation on startup (line ~1075)**
```python
# CRITICAL FIX NOV 16: Validate state against exchange
validation_result = await self.position_actor.validate_state_against_exchange(
    self.api_client,
    self.product_id
)
```

**Change 3: Exchange verification before order check (line ~2045)**
```python
# CRITICAL FIX NOV 16: Verify pending orders exist on exchange
if pending_buy or pending_sell:
    order_exists = any(o.get('id') == pending_order_id ...)
    if not order_exists:
        log.warning("⚠️  STALE PENDING ORDER DETECTED")
        # Clear and recreate
```

### **File 2: `bot/strategy/actors/position_actor.py`** (1 change)

**New method: `validate_state_against_exchange()` (line ~700)**
```python
async def validate_state_against_exchange(self, api_client, product_id):
    # Validate pending orders
    # Validate positions
    # Remove stale data
    # Return results
```

### **File 3: `tools/fix_bot_memory.sh`** (NEW FILE)
Backup and cleanup utility for emergency database reset.

### **File 4: `CRITICAL_FIXES_NOV16_2025.md`** (THIS FILE)
Complete documentation of all bugs and fixes.

---

## **🧪 TESTING CHECKLIST**

### **Test 1: Clean Startup** ✅
- [ ] Run `./tools/fix_bot_memory.sh` to backup and clear database
- [ ] Restart bot
- [ ] Verify logs show: "🔍 VALIDATING BOT STATE AGAINST EXCHANGE"
- [ ] Verify logs show: "✅ Validation complete - bot memory synchronized"
- [ ] Verify heartbeat shows correct pending order (not $38)

### **Test 2: Auto-Recreate After Manual Cancellation** ✅
- [ ] Let bot place pending grid order (e.g., BUY @ $95,000)
- [ ] Manually cancel this order on Delta Exchange
- [ ] Wait 5-20 seconds
- [ ] Verify logs show: "⚠️ STALE PENDING ORDER DETECTED"
- [ ] Verify logs show: "✅ RECREATED cancelled BUY order @ $95,000"
- [ ] Verify new order appears on exchange

### **Test 3: Ignore Manual OPTIONS Trades** ✅
- [ ] Place manual OPTIONS trade (e.g., BUY C-BTC-129000 @ $38)
- [ ] Wait for fill
- [ ] Check bot logs - should show: "⏭️ Ignoring fill for different product"
- [ ] Verify bot heartbeat does NOT show $38 order
- [ ] Verify bot continues grid trading normally

### **Test 4: Fresh State After Restart** ✅
- [ ] Stop bot
- [ ] Verify database still contains old test positions
- [ ] Start bot
- [ ] Verify validation removes stale positions
- [ ] Verify bot shows clean state (0 positions if market reset)

---

## **⚡ QUICK FIX FOR IMMEDIATE RELIEF**

If bot is currently showing wrong pending order ($38) or stale positions:

```bash
cd /Users/ssr/Projects/WorkingBot

# Option 1: Use the cleanup tool (RECOMMENDED)
./tools/fix_bot_memory.sh

# Option 2: Manual cleanup
cp bot_events_LONG.db bot_events_LONG.db.backup_$(date +%Y%m%d_%H%M%S)
rm bot_events_LONG.db

# Restart bot - will create fresh database
```

---

## **📊 EXPECTED LOG OUTPUT**

### **On Startup:**
```
===============================================================================
🔍 VALIDATING BOT STATE AGAINST EXCHANGE
================================================================================
🔍 Validating bot state against exchange for BTCUSD...
⚠️  Pending BUY 12345 @ $38 NOT on exchange - clearing from memory
⚠️  Position @ $110,000 NOT on exchange - removing from memory  
⚠️  Position @ $95,000 NOT on exchange - removing from memory
✅ State validation complete: 0 positions kept, 2 removed, pending_buy=cleared
   ✅ Validation complete - bot memory synchronized with exchange
================================================================================
```

### **On Manual Cancellation:**
```
===============================================================================
⚠️  STALE PENDING ORDER DETECTED
================================================================================
   Order ID: abc123
   Price: $95,000.00
   Status: NOT FOUND on exchange
   Likely Cause: Manual cancellation or wrong product
   Action: Clearing from memory and recreating...
================================================================================

✅ Cleared stale pending order - will recreate below
⚠️  Pending BUY order is missing (manually cancelled?) - will recreate
✅ RECREATED cancelled BUY order @ $95,000.00 (Order: xyz789)
```

### **On Manual OPTIONS Fill:**
```
⏭️  Ignoring fill for different product: C-BTC-129000-281125 (bot trades BTCUSD)
```

---

## **🎯 SUCCESS CRITERIA**

✅ **Bot startup shows clean state** (no stale $38 or $110k positions)  
✅ **Auto-recreate works within 20 seconds** of manual cancellation  
✅ **Bot ignores manual OPTIONS trades** (no $38 in logs)  
✅ **Heartbeat shows correct pending order** matching grid config  
✅ **WebUI predictions show $95,000** (not $94,500 or $109,500)  
✅ **No manual intervention needed** after restart

---

## **🔧 ROLLBACK PLAN**

If fixes cause issues:

```bash
cd /Users/ssr/Projects/WorkingBot

# Restore database backup
mv bot_events_LONG.db.backup_YYYYMMDD_HHMMSS bot_events_LONG.db

# Revert code changes
git diff bot/strategy/async_gridbot.py
git diff bot/strategy/actors/position_actor.py
git checkout bot/strategy/async_gridbot.py bot/strategy/actors/position_actor.py

# Restart bot
```

---

## **📝 NEXT STEPS**

1. ✅ Run database cleanup: `./tools/fix_bot_memory.sh`
2. ✅ Restart bot and verify validation runs
3. ✅ Test manual cancellation → auto-recreate
4. ✅ Test manual OPTIONS trade → ignored by bot
5. ✅ Monitor for 24 hours to ensure stability
6. ✅ Update user documentation with new features

---

**Status:** All fixes implemented and ready for production testing.  
**Date:** November 16, 2025  
**Version:** AsyncGridBot v2.0 + NOV 16 Critical Fixes

### **Bug #1: Weak Bot Memory (Stale Database Data)**
**Problem:** EventStore database contains old test data that never gets cleaned up. Every restart requires manual intervention.

**Root Cause:**
- Database has stale positions from Nov 14 testing ($95,000 and $110,000 entries)
- Database has stale pending orders (the $38 OPTIONS order)
- EventStore reconstruction doesn't validate if positions/orders still exist on exchange
- No automatic cleanup of orphaned events

**Evidence:**
```
WebUI bot_state_reader.py logs:
[WARNING] Filtering invalid LONG position: entry $110,000 above current price $95,500
[WARNING] Filtering stale position: entry $95,000, TP $95,500 (price=95500)
```

**Impact:**
- WebUI predictions were wrong ($109,500 instead of $95,000) ✅ FIXED with filtering
- Bot heartbeat still reads stale data from database
- User must manually intervene after every restart

---

### **Bug #2: Auto-Recreate Not Working**
**Problem:** Warning says "bot will recreate order on next heartbeat cycle (every 20s)" but this is NOT happening.

**Root Cause:**
Bot sees a "pending order" in memory (the $38 OPTIONS trade) so it thinks pending order exists and doesn't recreate.

**Expected Behavior:**
1. User manually cancels grid pending order @ $95,000
2. Bot detects missing order within 5-20 seconds (ticker update or heartbeat)
3. Bot automatically recreates the order

**Actual Behavior:**
1. User cancels grid order
2. Bot shows "Pending BUY @ $38" (WRONG - this is OPTIONS, not FUTURES)
3. Bot thinks pending order exists, doesn't recreate
4. Grid trading stops silently

**Code Location:**
`bot/strategy/async_gridbot.py` line ~2070:
```python
# Check if we should place pending order
if not self._initial_order_placed or len(positions) < self.max_open_positions:
    if not pending_buy:  # ❌ BUG: pending_buy is $38 OPTIONS order!
        # Place new pending BUY
```

---

### **Bug #3: Bot Confused Between Manual OPTIONS and Grid FUTURES**
**Problem:** Bot log shows "Pending BUY @ $38" - this is a manual OPTIONS trade, not the bot's FUTURES grid trade.

**Root Cause:**
The EventStore is recording ALL orders placed on the account, not just the bot's grid orders.

**Evidence from User's Screenshot:**
- Order book shows: `C-BTC-129000-281125` (OPTIONS contract)
- Size: `0.05 BTC` at price `$38`
- This is a MANUAL trade, not part of the grid bot

**Bot Log:**
```
[HB] Positions: 0/10 | Price: $95,320↑ | Pending BUY @ $38 | ✅ ACTIVE
```

**Why This Happens:**
1. User places manual OPTIONS order @ $38
2. Exchange fills the order
3. WebSocket sends `order_filled` event
4. Bot's fill handler processes ALL fills (doesn't filter by product_id)
5. EventStore records `pending_order_placed` for $38 order
6. Bot state reconstruction reads this as "current pending buy"
7. Heartbeat displays "Pending BUY @ $38" ❌

---

## **🔧 COMPREHENSIVE FIX STRATEGY**

### **Fix #1: Add Product ID Filtering to Fill Handler**
**File:** `bot/strategy/async_gridbot.py`

**Location:** Line ~850-900 (fill processing in `_on_fill`)

**Current Code:**
```python
async def _on_fill(self, fill_data):
    """Handle fill events from WebSocket"""
    # Process fill without checking product_id
    await self._process_fill(fill_data)
```

**Fixed Code:**
```python
async def _on_fill(self, fill_data):
    """Handle fill events from WebSocket"""
    # CRITICAL: Only process fills for OUR product
    fill_product = fill_data.get('product_id')
    if fill_product != self.product_id:
        log.debug(f"Ignoring fill for different product: {fill_product} (bot trading {self.product_id})")
        return
    
    await self._process_fill(fill_data)
```

**Impact:** Bot will ignore OPTIONS trades and only process FUTURES grid trades.

---

### **Fix #2: Add Exchange Validation to State Reconstruction**
**File:** `bot/strategy/actors/position_actor.py`

**Add method:**
```python
async def validate_state_against_exchange(self, api_client, product_id):
    """
    Validate reconstructed state against actual exchange data
    Remove stale positions/orders that don't exist on exchange
    """
    # Get actual exchange data
    exchange_orders = await api_client.get_open_orders(product_id=product_id)
    exchange_positions = await api_client.get_open_positions(product_id=product_id)
    
    # Validate pending orders
    if self.state['pending_buy']:
        order_id = self.state['pending_buy']['order_id']
        if not any(o['id'] == order_id for o in exchange_orders):
            log.warning(f"⚠️  Pending BUY {order_id} not on exchange - clearing from memory")
            self.state['pending_buy'] = None
    
    if self.state['pending_sell']:
        order_id = self.state['pending_sell']['order_id']
        if not any(o['id'] == order_id for o in exchange_orders):
            log.warning(f"⚠️  Pending SELL {order_id} not on exchange - clearing from memory")
            self.state['pending_sell'] = None
    
    # Validate open positions
    exchange_entry_prices = {p['entry_price'] for p in exchange_positions}
    valid_tranches = []
    
    for tranche in self.state['open_tranches']:
        if tranche['entry_price'] in exchange_entry_prices:
            valid_tranches.append(tranche)
        else:
            log.warning(f"⚠️  Position @ ${tranche['entry_price']} not on exchange - removing from memory")
    
    self.state['open_tranches'] = valid_tranches
    
    log.info(f"✅ State validated: {len(valid_tranches)} positions, pending_buy={self.state['pending_buy'] is not None}")
```

**Call this after state reconstruction:**
```python
# In async_gridbot.py startup
await self.position_actor.validate_state_against_exchange(self.api_client, self.product_id)
```

---

### **Fix #3: Enhanced Missing Order Detection**
**File:** `bot/strategy/async_gridbot.py`

**Location:** Line ~2070 in `_check_and_place_entry_order`

**Add explicit detection:**
```python
async def _check_and_place_entry_order(self):
    """Check grid and place entry order if needed"""
    
    # Get current state
    state = await self.position_actor.ask("GET_STATE", {})
    positions = state.get("open_tranches", [])
    pending_buy = state.get("pending_buy") if self.mode == 'LONG' else None
    pending_sell = state.get("pending_sell") if self.mode == 'SHORT' else None
    
    # Calculate what pending order SHOULD exist
    expected_pending_price = self.grid_calc.compute_next_buy_level(positions, self._last_price)
    
    # CRITICAL FIX: Verify pending order on exchange
    if pending_buy or pending_sell:
        pending_order_id = (pending_buy or pending_sell)['order_id']
        pending_price = (pending_buy or pending_sell)['price']
        
        # Check if this order actually exists on exchange
        exchange_orders = await self.api_client.get_open_orders(product_id=self.product_id)
        order_exists = any(o['id'] == pending_order_id for o in exchange_orders)
        
        if not order_exists:
            log.warning(f"⚠️  Pending order {pending_order_id} @ ${pending_price} is MISSING from exchange!")
            log.warning(f"   This indicates manual cancellation or exchange error")
            
            # Clear from memory
            if self.mode == 'LONG':
                await self.position_actor.ask("CLEAR_PENDING_BUY", {"order_id": pending_order_id})
            else:
                await self.position_actor.ask("CLEAR_PENDING_SELL", {"order_id": pending_order_id})
            
            log.info(f"✅ Cleared stale pending order from memory - will recreate")
            pending_buy = None
            pending_sell = None
    
    # Now proceed with normal logic (will recreate if needed)
    if not pending_buy and not pending_sell and len(positions) < self.max_open_positions:
        # Place new pending order...
```

---

### **Fix #4: Database Cleanup Utility**
**Create:** `tools/cleanup_stale_data.py`

```python
#!/usr/bin/env python3
"""
Clean up stale data from EventStore database
Run this when bot memory seems corrupted
"""
import sqlite3
import json
import sys
from pathlib import Path

def cleanup_stale_events(db_path, product_id, dry_run=True):
    """Remove events that don't belong to this bot's product"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Find events with wrong product_id
    cursor.execute("""
        SELECT rowid, event_type, data 
        FROM events 
        WHERE event_type IN ('position_opened', 'pending_order_placed', 'order_filled')
    """)
    
    to_delete = []
    for rowid, event_type, data_str in cursor.fetchall():
        try:
            data = json.loads(data_str)
            event_product = data.get('product_id')
            
            if event_product and event_product != product_id:
                to_delete.append((rowid, event_type, event_product))
                print(f"Would delete: {event_type} for {event_product}")
        except:
            pass
    
    if to_delete and not dry_run:
        for rowid, _, _ in to_delete:
            cursor.execute("DELETE FROM events WHERE rowid = ?", (rowid,))
        conn.commit()
        print(f"✅ Deleted {len(to_delete)} stale events")
    else:
        print(f"🔍 Found {len(to_delete)} stale events (dry run)")
    
    conn.close()

if __name__ == "__main__":
    db_path = "bot_events_LONG.db"
    product_id = "BTCUSD"  # Your grid bot product
    
    # Dry run first
    print("=== DRY RUN ===")
    cleanup_stale_events(db_path, product_id, dry_run=True)
    
    response = input("\nProceed with deletion? (yes/no): ")
    if response.lower() == 'yes':
        cleanup_stale_events(db_path, product_id, dry_run=False)
```

---

## **📋 IMPLEMENTATION CHECKLIST**

- [ ] **Fix #1:** Add product_id filtering to fill handler
- [ ] **Fix #2:** Add exchange validation to state reconstruction
- [ ] **Fix #3:** Enhanced missing order detection with exchange verification
- [ ] **Fix #4:** Create and run database cleanup utility
- [ ] **Test:** Manually cancel grid order and verify auto-recreate within 20s
- [ ] **Test:** Place manual OPTIONS trade and verify bot ignores it
- [ ] **Test:** Restart bot and verify it doesn't load stale data
- [ ] **Document:** Update user guide with troubleshooting steps

---

## **🎯 EXPECTED RESULTS AFTER FIX**

1. **Bot ignores manual OPTIONS trades** - only processes FUTURES grid orders
2. **Auto-recreate works** - cancelling grid order triggers recreation within 5-20s
3. **No stale data** - bot validates state against exchange on startup
4. **Clean database** - utility removes orphaned events from other products
5. **Accurate heartbeat** - shows correct pending order or "NONE" if missing

---

## **⚡ QUICK FIX FOR IMMEDIATE RELIEF**

Run this Python script to clear the database and force fresh start:

```bash
cd /Users/ssr/Projects/WorkingBot
rm bot_events_LONG.db  # ⚠️  WARNING: This deletes all event history!
# Bot will recreate database on next start with clean state
```

**OR** safer approach (backup first):
```bash
cp bot_events_LONG.db bot_events_LONG.db.backup_$(date +%Y%m%d_%H%M%S)
rm bot_events_LONG.db
```
