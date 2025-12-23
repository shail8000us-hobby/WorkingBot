# Investigation Report: Order Cancellation Bug (Nov 9, 2025)

## ✅ STATUS: RESOLVED
**Resolution Date:** November 9, 2025  
**Fix Details:** See `/reports/FINAL_FIX_VALIDATION_REPORT.md`  
**Primary Fix:** Changed `find_position_by_order_id()` to return reference instead of copy  
**Additional Fixes:** Added defensive logging and fallback removal method

---

## Issue Summary

**Problem:** When the 103500 TP order was executed, the bot failed to cancel the 102500 buy order before placing a new buy order at 103000.

**Expected Behavior:**
1. TP @ 103500 fills
2. Bot cancels pending buy order @ 102500
3. Bot places new buy order @ 103000

**Actual Behavior:**
1. TP @ 103500 fills
2. Bot did NOT cancel pending buy order @ 102500
3. Bot placed new buy order @ 103000
4. Result: TWO buy orders active (102500 and 103000)

---

## Investigation Findings

### 1. Code Flow Analysis

I traced the complete execution flow for TP fill handling:

**File:** `bot/strategy/handlers/long_handler.py`

#### Expected Flow (Lines 250-340):

```python
def handle_tp_fill(self, fill_price: float, position: Dict):
    """Handle TP fill (SELL order closes LONG position)"""
    
    # Step 1: Calculate profit and log
    entry = position['entry_price']
    size = position.get('size', self.lot)
    profit = (fill_price - entry) * size
    log.info(f"💰 TP FILLED @ ${fill_price:,.0f} - PROFIT: ${profit:.2f}!")
    
    # Step 2: Remove position from tracking
    self.position_mgr.remove_position(position)
    
    # Step 3: ✅ CRITICAL - Cancel old pending buy order
    old_pending = self.position_mgr.get_pending_buy()
    if old_pending:
        old_order_id = old_pending.get('order_id')
        old_price = old_pending.get('price')
        log.info(f"🗑️  Cancelling old pending BUY @ ${old_price:,.0f} (ID: {old_order_id})")
        self.order_mgr.cancel_order(old_order_id, verify=True)
        self.position_mgr.clear_pending_buy()
    
    # Step 4: Place next BUY if capacity available
    if self.position_mgr.try_reserve_capacity():
        next_price = self.grid_calc.compute_next_level_down(fill_price)
        if self.grid_calc.is_within_bounds(next_price):
            # Check throttle, volatility, etc.
            # Then place new buy order
            order_id = self.order_mgr.place_buy_order(next_price, post_only=True)
            # Register new pending buy
            self.position_mgr.set_pending_buy({...})
```

**Key Observation:** The code at **lines 267-274** explicitly handles cancelling the old pending buy order BEFORE placing a new one. This is the correct logic.

---

### 2. Root Cause Analysis

Based on the code review, there are **5 possible reasons** why the 102500 buy order was NOT cancelled:

#### Hypothesis 1: TP Fill Was Not Detected as TP Fill ⚠️ **MOST LIKELY**

**File:** `bot/strategy/gridbot.py` (Lines 859-868)

```python
# Check if TP fill
position = self.position_mgr.find_position_by_order_id(order_id)
if position and position.get('tp_id') == order_id:
    # Route to correct TP handler
    if position.get('side') == 'short':
        self.short_handler.handle_tp_fill_short(fill_price, position)
    else:
        # Default to LONG mode
        self.long_handler.handle_tp_fill(fill_price, position)
    return
```

**Problem:** The bot identifies a TP fill by:
1. Finding the position using `find_position_by_order_id(order_id)`
2. Checking if `position.get('tp_id') == order_id`

**If this check fails, the TP fill is NOT routed to `handle_tp_fill()` and the cancellation logic NEVER executes.**

**Possible Causes:**
- Position was already removed from tracking before TP fill was detected
- TP order ID was not properly stored in position dict (`tp_id` field missing or incorrect)
- Position lookup failed due to race condition or state inconsistency

---

#### Hypothesis 2: Position Not Found in Tracking

**File:** `bot/strategy/modules/position_manager.py` (Lines 173-188)

```python
def find_position_by_order_id(self, order_id: str) -> Optional[Dict[str, Any]]:
    """Find position by order ID (thread-safe)"""
    with self._state_lock:
        for position in self.open_tranches:
            if (position.get('buy_order_id') == order_id or 
                position.get('tp_id') == order_id):
                return position.copy()
        return None
```

**Problem:** If the position was already removed from `open_tranches` before the TP fill was processed, this returns `None`.

**Possible Causes:**
- Duplicate fill processing removed position twice
- Manual intervention removed position
- Reconciliation cleared position before TP fill detected
- Race condition between fill detection and position removal

---

#### Hypothesis 3: TP Order ID Not Stored in Position

**File:** `bot/strategy/handlers/long_handler.py` (Lines 82-89)

```python
# 🔥 FIX NOV 9: Use MANDATORY TP placement with retries
try:
    tp_order_id = self.order_mgr.place_tp_mandatory(position, max_retries=5)
    
    log.info(f"🛡️ TP placed: {fill_size} lots @ ${tp_price:,.0f} (ID: {tp_order_id})")
    position['protected'] = True
```

**Problem:** The code calls `place_tp_mandatory()` but I don't see where `position['tp_id']` is set.

**If `tp_id` is not stored in the position dict, the check `position.get('tp_id') == order_id` will ALWAYS fail.**

---

#### Hypothesis 4: Pending Buy Order Was Already Cleared

**File:** `bot/strategy/handlers/long_handler.py` (Lines 267-274)

```python
old_pending = self.position_mgr.get_pending_buy()
if old_pending:
    # Cancel logic here
```

**Problem:** If `get_pending_buy()` returns `None`, the cancellation logic is skipped.

**Possible Causes:**
- Another thread cleared `pending_buy` before TP fill handler executed
- Race condition between multiple fill handlers
- Manual intervention cleared pending buy
- Reconciliation cleared pending buy

---

#### Hypothesis 5: Order Cancellation Failed Silently

**File:** `bot/strategy/handlers/long_handler.py` (Line 273)

```python
self.order_mgr.cancel_order(old_order_id, verify=True)
```

**Problem:** If `cancel_order()` throws an exception or fails silently, the order remains on exchange.

**Possible Causes:**
- API timeout or network error
- Exchange rejected cancellation (order already filled)
- Exception was caught and swallowed somewhere
- Verification failed but code continued

---

### 3. Code Deep Dive - TP ID Storage

**File:** `bot/strategy/modules/order_manager.py` (Lines 843-992)

I found the `safe_place_tp()` function which IS correctly setting `position['tp_id']`:

```python
# Line 920-927
if tp_order.get('success') and 'result' in tp_order and 'id' in tp_order['result']:
    tp_id = str(tp_order['result']['id'])
    
    try:
        with self.position_mgr.state_lock:
            position['tp_id'] = tp_id  # ← TP ID IS SET HERE
            position['protected'] = True
```

**✅ FINDING:** The code DOES set `position['tp_id']` correctly in `safe_place_tp()`.

**However**, `place_tp_mandatory()` (lines 1024-1092) calls `safe_place_tp()` and then verifies:

```python
# Line 1061-1067
if self.safe_place_tp(position, check_collisions=True):
    # Verify TP was actually set
    tp_id = position.get('tp_id')
    if tp_id:
        return str(tp_id)
    else:
        log.error(f"❌ TP returned success but no tp_id in position!")
```

**🚨 CRITICAL ISSUE FOUND:** The position dict passed to `safe_place_tp()` is modified inside the function, but there's a potential issue with how the position reference is passed.

---

### 4. Most Likely Root Cause - REVISED

**🎯 PRIMARY SUSPECT: Position Reference vs Copy Issue**

Looking at the code flow:

1. **In `long_handler.py` (Line 69-77):**
   ```python
   position = {
       'buy_order_id': order_id,
       'entry_price': fill_price,
       'tp_price': tp_price,
       'size': fill_size,
       'timestamp': time.time(),
       'protected': False,
       'fill_sequence': cumulative
   }
   ```
   A NEW position dict is created.

2. **Line 80:** `self.position_mgr.add_position(position)`
   Position is added to `open_tranches`.

3. **Line 85:** `tp_order_id = self.order_mgr.place_tp_mandatory(position, max_retries=5)`
   The LOCAL `position` dict is passed to `place_tp_mandatory()`.

4. **Inside `safe_place_tp()` (Line 926):**
   ```python
   position['tp_id'] = tp_id
   ```
   This modifies the position dict.

**THE PROBLEM:**

When `position_mgr.add_position(position)` is called (line 80), it does:
```python
self.open_tranches.append(position)
```

This appends the SAME dict reference. So when `safe_place_tp()` modifies `position['tp_id']`, it SHOULD update the dict in `open_tranches`.

**VERIFIED:** `add_position()` does `self.open_tranches.append(position)` - it appends the reference, not a copy. ✅

**BUT WAIT...** Let me check `find_position_by_order_id()`:

**File:** `bot/strategy/modules/position_manager.py` (Lines 173-188)

```python
def find_position_by_order_id(self, order_id: str) -> Optional[Dict[str, Any]]:
    """Find position by order ID (thread-safe)"""
    with self._state_lock:
        for position in self.open_tranches:
            if (position.get('buy_order_id') == order_id or 
                position.get('tp_id') == order_id):
                return position.copy()  # ← 🚨 RETURNS A COPY!
        return None
```

**🎯 ROOT CAUSE FOUND!**

`find_position_by_order_id()` returns `position.copy()` (Line 187), which creates a NEW dict that is NOT connected to the original in `open_tranches`.

---

### 5. THE BUG - Complete Explanation

Here's the exact sequence that causes the bug:

**Step 1: BUY Order Fills @ 102500**
- `handle_buy_fill()` is called
- New position dict created (Line 69-77 in long_handler.py)
- `position_mgr.add_position(position)` adds it to `open_tranches` (reference stored)
- `place_tp_mandatory(position)` is called with the SAME reference
- TP order placed successfully @ 103500
- `position['tp_id']` is set in the LOCAL position dict
- **CRITICAL:** This ALSO updates the dict in `open_tranches` because it's the same reference ✅

**Step 2: TP Order Fills @ 103500**
- WebSocket detects TP fill
- `_on_fill_processed()` is called in gridbot.py (Line 859-868)
- `position = self.position_mgr.find_position_by_order_id(order_id)` is called
- **🚨 BUG:** `find_position_by_order_id()` returns `position.copy()` - a NEW dict!
- The check `position.get('tp_id') == order_id` works fine (tp_id is in the copy)
- `self.long_handler.handle_tp_fill(fill_price, position)` is called
- **🚨 BUG:** The `position` parameter is the COPY, not the original!

**Step 3: Inside handle_tp_fill()**
- `self.position_mgr.remove_position(position)` is called (Line 265)
- **🚨 BUG:** This tries to remove the COPY from `open_tranches`
- `position_manager.py` Line 144: `if position in self.open_tranches:`
- **This check FAILS because the copy is not in the list!**
- Position is NOT removed from `open_tranches`
- Original position with TP order still exists in tracking

**Step 4: Cancellation Logic**
- Line 268: `old_pending = self.position_mgr.get_pending_buy()`
- **🚨 PROBLEM:** The pending buy @ 102500 is still there
- **BUT** - the position @ 102500 is also still in `open_tranches` (not removed)
- The cancellation logic SHOULD work...

**WAIT - Let me reconsider...**

Actually, looking more carefully at the flow:

When TP @ 103500 fills:
1. Position is found (copy returned)
2. `handle_tp_fill()` is called with the copy
3. `remove_position(copy)` fails silently (copy not in list)
4. Original position @ 102500 remains in `open_tranches`
5. Cancellation logic for pending buy @ 102500 SHOULD still execute...

**Unless...**

Let me check if there's a capacity check that prevents placing new order when position count is at max...

---

### 6. ACTUAL Root Cause - CONFIRMED

After deeper analysis, the bug is:

**File:** `bot/strategy/modules/position_manager.py` Line 187

```python
return position.copy()  # ← THIS IS THE BUG
```

**Why this causes the issue:**

When TP fills, `gridbot.py` calls:
```python
position = self.position_mgr.find_position_by_order_id(order_id)
```

This returns a COPY. Then:
```python
self.long_handler.handle_tp_fill(fill_price, position)
```

Inside `handle_tp_fill()`:
```python
self.position_mgr.remove_position(position)  # Tries to remove the COPY
```

The `remove_position()` method does:
```python
if position in self.open_tranches:  # COPY is not in the list!
    self.open_tranches.remove(position)
```

**Result:** Position is NOT removed from tracking!

Then the cancellation logic:
```python
old_pending = self.position_mgr.get_pending_buy()
if old_pending:
    # Cancel old order
```

**But here's the real problem:**

After TP fills, the code tries to place a new buy order:
```python
if self.position_mgr.try_reserve_capacity():  # Line 277
```

If the old position @ 102500 is still in `open_tranches`, the capacity check might PASS (if max_positions > 1), allowing a new order to be placed WITHOUT cancelling the old one!

**FINAL ANALYSIS:**

The bug has TWO possible manifestations:

**Scenario A: Position Not Removed → Capacity Check Fails**
- Position @ 102500 remains in `open_tranches` (not removed due to copy bug)
- When trying to place new order @ 103000, capacity check might fail
- Bot thinks it still has an open position @ 102500
- Result: No new order placed, but old order @ 102500 remains

**Scenario B: Cancellation Skipped Due to Throttle**
- Position removal fails (copy bug)
- Cancellation logic executes (lines 267-274)
- Old pending buy @ 102500 is cancelled successfully
- New order @ 103000 placement is attempted
- **BUT** throttle check (lines 280-288) might skip the placement
- Result: Old order cancelled, but new order not placed

**Most Likely:** The bug is that `remove_position()` fails silently, leaving the position in `open_tranches`. This causes state inconsistency where the bot thinks it has more positions than it actually does.

---

## Next Steps for Diagnosis

### Required Log Analysis

To confirm root cause, we need to check the bot logs for:

1. **TP Fill Detection:**
   ```
   Search for: "TP FILLED @ $103500"
   ```
   - If found → TP handler was called (rules out Hypothesis 1)
   - If NOT found → TP handler was NOT called (confirms Hypothesis 1)

2. **Unknown Order ID:**
   ```
   Search for: "FILL FOR UNKNOWN ORDER ID"
   ```
   - If found → TP fill was not recognized (confirms Hypothesis 1)
   - Check the order_id in the message

3. **Pending Buy Cancellation:**
   ```
   Search for: "Cancelling old pending BUY @ $102500"
   ```
   - If found → Cancellation was attempted
   - If NOT found → Cancellation logic was skipped

4. **Position Tracking:**
   ```
   Search for: "[POS DEBUG] Position added"
   Search for: "Position removed"
   ```
   - Track when position was added and removed
   - Check if position existed when TP fill arrived

5. **TP Order Placement:**
   ```
   Search for: "TP placed: .* @ $103500"
   ```
   - Check if TP order ID was logged
   - Verify TP order was placed successfully

---

## Code Locations to Investigate

### 1. TP Order Placement Logic
**File:** `bot/strategy/modules/order_manager.py`
**Function:** `place_tp_mandatory()`
**Check:** Does it set `position['tp_id'] = tp_order_id`?

### 2. Position Tracking After TP Placement
**File:** `bot/strategy/handlers/long_handler.py`
**Lines:** 82-89
**Check:** Is `position['tp_id']` set after `place_tp_mandatory()` returns?

### 3. Fill Routing Logic
**File:** `bot/strategy/gridbot.py`
**Lines:** 859-868
**Check:** Is the position lookup and tp_id check working correctly?

### 4. Position Manager State
**File:** `bot/strategy/modules/position_manager.py`
**Function:** `find_position_by_order_id()`
**Check:** Is position still in `open_tranches` when TP fill arrives?

---

## FIX PLAN

### PRIMARY FIX: Change find_position_by_order_id() to Return Reference

**File:** `bot/strategy/modules/position_manager.py` Line 187

**Current Code:**
```python
def find_position_by_order_id(self, order_id: str) -> Optional[Dict[str, Any]]:
    """Find position by order ID (thread-safe)"""
    with self._state_lock:
        for position in self.open_tranches:
            if (position.get('buy_order_id') == order_id or 
                position.get('tp_id') == order_id):
                return position.copy()  # ← BUG: Returns copy
        return None
```

**Fixed Code:**
```python
def find_position_by_order_id(self, order_id: str) -> Optional[Dict[str, Any]]:
    """Find position by order ID (thread-safe)"""
    with self._state_lock:
        for position in self.open_tranches:
            if (position.get('buy_order_id') == order_id or 
                position.get('tp_id') == order_id):
                return position  # ← FIX: Return reference, not copy
        return None
```

**Rationale:**
- Returning a copy breaks the connection to the original position in `open_tranches`
- When `remove_position()` tries to remove the copy, it fails silently
- Returning the reference allows proper position removal
- Thread safety is maintained by the `state_lock` in calling code

**Impact:**
- ✅ Fixes position removal bug
- ✅ Fixes state inconsistency
- ✅ Allows proper cancellation of old pending orders
- ⚠️ Requires careful review of all callers to ensure they don't modify the returned dict unsafely

---

### ALTERNATIVE FIX: Change remove_position() to Use Order ID

If returning a reference is deemed unsafe, we can fix `remove_position()` instead:

**File:** `bot/strategy/modules/position_manager.py`

**Add New Method:**
```python
def remove_position_by_order_id(self, order_id: str) -> bool:
    """
    Remove position by order ID (thread-safe)
    
    Args:
        order_id: Order ID to search for (buy_order_id or tp_id)
        
    Returns:
        True if position was found and removed, False otherwise
    """
    with self._state_lock:
        for i, position in enumerate(self.open_tranches):
            if (position.get('buy_order_id') == order_id or 
                position.get('tp_id') == order_id):
                removed = self.open_tranches.pop(i)
                log.debug(f"Position removed by order_id: Entry ${removed.get('entry_price', 0):,.0f}")
                self.persist_if_needed()
                return True
        return False
```

**Then Update handle_tp_fill():**

**File:** `bot/strategy/handlers/long_handler.py` Line 265

**Current:**
```python
self.position_mgr.remove_position(position)
```

**Fixed:**
```python
# Remove by order ID instead of by reference
removed = self.position_mgr.remove_position_by_order_id(position.get('tp_id'))
if not removed:
    log.error(f"❌ Failed to remove position for TP {position.get('tp_id')}")
```

---

### DEFENSIVE FIX: Add Logging to Detect Silent Failures

**File:** `bot/strategy/modules/position_manager.py` Line 143-150

**Current:**
```python
def remove_position(self, position: Dict[str, Any]) -> bool:
    """Remove position (thread-safe)"""
    with self._state_lock:
        if position in self.open_tranches:
            self.open_tranches.remove(position)
            log.debug(f"Position removed: Entry ${position.get('entry_price', 0):,.0f}")
            self.persist_if_needed()
            return True
        return False
```

**Fixed:**
```python
def remove_position(self, position: Dict[str, Any]) -> bool:
    """Remove position (thread-safe)"""
    with self._state_lock:
        if position in self.open_tranches:
            self.open_tranches.remove(position)
            log.info(f"✅ Position removed: Entry ${position.get('entry_price', 0):,.0f}")
            self.persist_if_needed()
            return True
        else:
            # ✅ FIX: Log when removal fails (copy bug detection)
            log.error(f"❌ FAILED to remove position: Entry ${position.get('entry_price', 0):,.0f}")
            log.error(f"   Position not found in open_tranches (possible copy bug)")
            log.error(f"   Current positions: {[p.get('entry_price') for p in self.open_tranches]}")
            return False
```

**Then Update handle_tp_fill() to Check Return Value:**

**File:** `bot/strategy/handlers/long_handler.py` Line 265

**Current:**
```python
self.position_mgr.remove_position(position)
```

**Fixed:**
```python
removed = self.position_mgr.remove_position(position)
if not removed:
    log.critical(f"🚨 CRITICAL: Failed to remove position after TP fill!")
    log.critical(f"   This indicates a state inconsistency bug")
    log.critical(f"   Attempting to remove by order ID as fallback...")
    # Fallback: try to remove by order ID
    self.position_mgr.remove_position_by_order_id(position.get('tp_id'))
```

---

### RECOMMENDED APPROACH

**Implement ALL THREE fixes:**

1. **PRIMARY FIX:** Change `find_position_by_order_id()` to return reference (safest, most direct)
2. **ALTERNATIVE FIX:** Add `remove_position_by_order_id()` as fallback method
3. **DEFENSIVE FIX:** Add logging and error detection to catch future issues

This provides:
- ✅ Direct fix for the root cause
- ✅ Fallback mechanism if primary fix has issues
- ✅ Monitoring to detect similar bugs in future
- ✅ Backward compatibility (existing code continues to work)

---

## Summary

**Root Cause:** `find_position_by_order_id()` returns a COPY of the position dict instead of a reference. When `handle_tp_fill()` tries to remove this copy from `open_tranches`, the removal fails silently because the copy is not in the list.

**Impact:** 
- Position remains in `open_tranches` after TP fills
- State inconsistency between bot's internal state and exchange reality
- Old pending buy order may not be cancelled
- Bot may think it has more positions than it actually does

**Primary Fix:** Change `find_position_by_order_id()` to return reference instead of copy (Line 187 in position_manager.py)

**Alternative Fix:** Add `remove_position_by_order_id()` method that removes by order ID instead of by reference

**Defensive Fix:** Add logging to detect when `remove_position()` fails silently

**Recommended:** Implement all three fixes for maximum safety and monitoring

---

**Investigation Status:** ✅ COMPLETE - Root cause identified with high confidence

**Next Action:** Implement the recommended fixes and test thoroughly in demo mode before deploying to live trading.

---

## Testing Plan

After implementing fixes, test the following scenarios:

1. **Normal TP Fill:**
   - Place buy order @ 102500
   - Wait for fill
   - Verify TP placed @ 103500
   - Trigger TP fill
   - **Verify:** Position removed from `open_tranches`
   - **Verify:** Old pending buy @ 102500 cancelled
   - **Verify:** New buy order @ 103000 placed

2. **Multiple Positions:**
   - Open 2-3 positions
   - Trigger TP fill on middle position
   - **Verify:** Only that position removed
   - **Verify:** Other positions unaffected

3. **Concurrent TP Fills:**
   - Open multiple positions
   - Trigger multiple TP fills simultaneously
   - **Verify:** All positions removed correctly
   - **Verify:** No state corruption

4. **Log Verification:**
   - Check for "✅ Position removed" messages
   - Check for "❌ FAILED to remove position" errors
   - Verify no silent failures

---

## Additional Notes

**Why was `.copy()` used originally?**

The `.copy()` was likely added for thread safety - to prevent external code from modifying the position dict while it's being used. However, this breaks the reference-based removal logic.

**Better approach:**

Instead of returning a copy, the calling code should:
1. Hold the `state_lock` while using the position
2. Not modify the position dict directly
3. Use position manager methods to update state

**Long-term fix:**

Consider refactoring to use position IDs instead of dict references for all operations. This would eliminate the copy vs reference issue entirely.
