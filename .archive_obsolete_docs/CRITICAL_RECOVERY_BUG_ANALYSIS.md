# 🚨 CRITICAL: Recovery Engine Duplicate Order Bug

**Date:** November 20, 2025, 1:35 AM  
**Severity:** 🔴 **CRITICAL** - Causes duplicate positions  
**Status:** ❌ **MUST FIX BEFORE DEPLOYMENT**

---

## 🐛 **The Bug**

### **What Happened:**
Bot placed **8 duplicate market BUY orders** at startup:
- All at different grid levels (88798, 88812, 88789, 88864, 88866, 88870, 88808, 88877)
- All placed within seconds
- All marked as "Taker" (market orders)
- All from recovery system

### **Screenshot Evidence:**
```
Symbol  | Side | Qty | Execution Price | Fill Type | Order Type
BTC-USD | Buy  | 1   | 88798          | Normal    | Market    | Taker
BTC-USD | Buy  | 1   | 88812          | Normal    | Market    | Taker
BTC-USD | Buy  | 1   | 88789          | Normal    | Market    | Taker
... (8 total orders)
```

---

## 🔍 **Root Cause Analysis**

### **Problem 1: Recovery Loop Places ALL Grids**

**File:** `bot/strategy/recovery/base_recovery_engine.py` (lines 346-366)

```python
# CURRENT CODE (BROKEN):
for grid_price in missed_grids:
    await self.rate_limiter.acquire()
    result = await self._recover_single_grid_with_retry(grid_price)
    # ❌ NO CHECK if position already exists!
    # ❌ NO CHECK if order already pending!
    # ❌ Places ALL missed grids without limit!
```

**Issue:**
- If 8 grids are missed, it places 8 orders
- No position existence check
- No pending order check
- Violates "single pending order" rule

---

### **Problem 2: Max Grids Not Enforced**

**File:** `bot/strategy/recovery/startup_recovery.py` (lines 63-96)

```python
# CURRENT CODE (WEAK):
max_grids = 3  # Default
missed = []

while grid > current_price and grid >= lower and len(missed) < max_grids:
    missed.append(grid)
    grid -= step
```

**Issue:**
- `max_grids` is calculated but not strictly enforced
- If config is missing, defaults to 3
- But recovery loop still processes ALL grids returned

---

### **Problem 3: No Position Existence Check**

**File:** `bot/strategy/recovery/base_recovery_engine.py` (lines 564-581)

```python
# CURRENT CODE (INCOMPLETE):
async def _has_position_at_grid(self, grid_price: float) -> bool:
    try:
        response = await self.bot.position_actor.ask({
            'type': 'GET_POSITIONS',
            'payload': {}
        })
        positions = response.get('positions', [])
        tolerance = 1.0
        
        return any(
            abs(pos.get('entry_price', 0) - grid_price) < tolerance
            for pos in positions
        )
    except Exception as e:
        self.logger.error(f"Error checking positions: {e}")
        return False  # ❌ Returns False on error (unsafe!)
```

**Issue:**
- Method exists but is NEVER CALLED before placing order
- Returns `False` on error (assumes no position - unsafe)
- Should return `True` on error (fail-safe)

---

### **Problem 4: No Pending Order Check**

**File:** `bot/strategy/recovery/base_recovery_engine.py`

**Missing:** No check for pending orders at grid level before placing recovery order

**Issue:**
- If a pending order already exists at grid level, recovery places duplicate
- Violates "single pending order" rule from logic.md

---

### **Problem 5: Race Condition**

**Scenario:**
1. Startup recovery starts
2. Detects 8 missed grids
3. Starts placing orders in loop
4. Meanwhile, normal grid logic also places orders
5. Result: Duplicate orders

**Issue:**
- No locking between recovery and normal trading
- No coordination with order actor
- No check if order already in flight

---

## 🛠️ **Required Fixes**

### **Fix 1: Enforce Max Grids Limit (CRITICAL)**

**File:** `bot/strategy/recovery/startup_recovery.py`

```python
async def calculate_missed_grids(self) -> List[float]:
    """Calculate missed grids with STRICT safety limits."""
    try:
        current_price = await self.bot.get_current_price()
        reference = self.config.grid.geometry.reference
        step = self.config.grid.geometry.step
        lower = self.config.grid.geometry.lower
        upper = self.config.grid.geometry.upper
        
        # STRICT max grids limit
        MAX_GRIDS = 3  # Hard-coded safety limit
        
        missed = []
        
        if self.bot.mode == "LONG":
            grid = reference - step
            while grid > current_price and grid >= lower:
                missed.append(grid)
                grid -= step
                
                # CRITICAL: Stop at max grids
                if len(missed) >= MAX_GRIDS:
                    self.logger.warning(f"Max grids limit reached ({MAX_GRIDS}) - stopping")
                    break
        else:
            grid = reference + step
            while grid < current_price and grid <= upper:
                missed.append(grid)
                grid += step
                
                # CRITICAL: Stop at max grids
                if len(missed) >= MAX_GRIDS:
                    self.logger.warning(f"Max grids limit reached ({MAX_GRIDS}) - stopping")
                    break
        
        self.logger.info(f"Calculated {len(missed)} missed grids (max: {MAX_GRIDS})")
        return missed[:MAX_GRIDS]  # Double-check limit
        
    except Exception as e:
        self.logger.error(f"Error calculating missed grids: {e}")
        return []  # Fail-safe: return empty list
```

---

### **Fix 2: Add Position Check Before Recovery**

**File:** `bot/strategy/recovery/base_recovery_engine.py`

```python
async def _recover_single_grid(self, grid_price: float, attempt_id: str, retry: int) -> RecoveryAttempt:
    """Recover a single grid level with COMPREHENSIVE safety checks."""
    timestamp = time.time()
    
    # Check 1: Already recovered
    if grid_price in self.recovered_grids:
        return RecoveryAttempt(
            attempt_id=attempt_id,
            grid_price=grid_price,
            timestamp=timestamp,
            status=RecoveryStatus.SKIPPED,
            error="already_recovered"
        )
    
    # Check 2: Position already exists (CRITICAL)
    has_position = await self._has_position_at_grid(grid_price)
    if has_position:
        self.logger.info(f"Grid {grid_price} already has position - skipping recovery")
        self.recovered_grids.add(grid_price)  # Mark as recovered
        return RecoveryAttempt(
            attempt_id=attempt_id,
            grid_price=grid_price,
            timestamp=timestamp,
            status=RecoveryStatus.SKIPPED,
            error="position_exists"
        )
    
    # Check 3: Pending order exists (CRITICAL)
    has_pending = await self._has_pending_order_at_grid(grid_price)
    if has_pending:
        self.logger.info(f"Grid {grid_price} already has pending order - skipping recovery")
        return RecoveryAttempt(
            attempt_id=attempt_id,
            grid_price=grid_price,
            timestamp=timestamp,
            status=RecoveryStatus.SKIPPED,
            error="pending_order_exists"
        )
    
    # Check 4: Rate limit
    if not await self.rate_limiter.acquire():
        return RecoveryAttempt(
            attempt_id=attempt_id,
            grid_price=grid_price,
            timestamp=timestamp,
            status=RecoveryStatus.FAILED,
            error="rate_limit_exceeded"
        )
    
    # Proceed with recovery...
```

---

### **Fix 3: Add Pending Order Check**

**File:** `bot/strategy/recovery/base_recovery_engine.py`

```python
async def _has_pending_order_at_grid(self, grid_price: float) -> bool:
    """Check if pending order exists at grid level (with tolerance)."""
    try:
        # Get open orders
        open_orders = await self.bot.get_open_orders()
        tolerance = 1.0
        
        # Check for matching orders
        for order in open_orders:
            order_price = order.get('limit_price', 0)
            if abs(order_price - grid_price) < tolerance:
                # Found matching order
                return True
        
        return False
        
    except Exception as e:
        self.logger.error(f"Error checking pending orders: {e}")
        return True  # Fail-safe: assume order exists (prevents duplicate)
```

---

### **Fix 4: Improve Error Handling (Fail-Safe)**

**File:** `bot/strategy/recovery/base_recovery_engine.py`

```python
async def _has_position_at_grid(self, grid_price: float) -> bool:
    """Check if position exists at grid level (with tolerance)."""
    try:
        response = await self.bot.position_actor.ask({
            'type': 'GET_POSITIONS',
            'payload': {}
        })
        positions = response.get('positions', [])
        tolerance = 1.0
        
        return any(
            abs(pos.get('entry_price', 0) - grid_price) < tolerance
            for pos in positions
        )
    except Exception as e:
        self.logger.error(f"Error checking positions: {e}")
        return True  # ✅ FAIL-SAFE: Assume position exists (prevents duplicate)
```

---

### **Fix 5: Add Recovery Lock**

**File:** `bot/strategy/async_gridbot.py`

```python
def __init__(self, ...):
    # ... existing code ...
    
    # Recovery lock (prevent concurrent recovery)
    self._recovery_in_progress = False
    self._recovery_lock = asyncio.Lock()

async def start(self):
    # ... existing code ...
    
    # Startup recovery with lock
    async with self._recovery_lock:
        if not self._recovery_in_progress:
            self._recovery_in_progress = True
            try:
                log.info("🔄 Checking for startup recovery...")
                startup_result = await self.startup_recovery.execute_recovery()
                # ... handle result ...
            finally:
                self._recovery_in_progress = False
```

---

## 🎯 **Testing Plan**

### **Test 1: Max Grids Enforcement**
1. Set reference: 90000, market: 80000 (10 grids missed)
2. Start bot
3. **Expected:** Only 3 recovery orders placed
4. **Verify:** Check logs for "Max grids limit reached"

### **Test 2: Position Existence Check**
1. Manually create position at grid level
2. Start bot with missed grids
3. **Expected:** Recovery skips grid with existing position
4. **Verify:** Check logs for "already has position - skipping"

### **Test 3: Pending Order Check**
1. Manually place order at grid level
2. Start bot with missed grids
3. **Expected:** Recovery skips grid with pending order
4. **Verify:** Check logs for "already has pending order - skipping"

### **Test 4: Race Condition**
1. Start bot with multiple missed grids
2. Monitor order placement
3. **Expected:** No duplicate orders
4. **Verify:** Check exchange orders list

---

## 📊 **Impact Assessment**

### **Current State:**
- ❌ **8 duplicate positions** created
- ❌ **Capital locked** in duplicate orders
- ❌ **Risk exposure** multiplied by 8x
- ❌ **Grid alignment** broken
- ❌ **PnL tracking** incorrect

### **After Fix:**
- ✅ **Max 3 recovery orders** per session
- ✅ **No duplicates** - position check prevents
- ✅ **No race conditions** - lock prevents
- ✅ **Fail-safe** - errors prevent orders
- ✅ **Grid alignment** maintained

---

## 🚨 **CRITICAL PRIORITY**

**DO NOT START BOT** until these fixes are applied!

**Estimated Fix Time:** 30 minutes  
**Testing Time:** 1 hour  
**Total:** 1.5 hours

---

## 📝 **Summary**

The recovery engine has a **critical bug** that places **ALL missed grids** without proper safety checks. This causes:

1. **Duplicate positions** (8 orders in your case)
2. **Capital over-allocation**
3. **Risk exposure multiplication**
4. **Grid misalignment**

**Root Causes:**
1. No max grids enforcement in recovery loop
2. No position existence check before placing order
3. No pending order check
4. Fail-unsafe error handling
5. No recovery lock

**All 5 issues must be fixed before deployment.**

---

**Created:** November 20, 2025, 1:35 AM  
**Status:** ❌ **CRITICAL - DO NOT DEPLOY**  
**Priority:** 🔴 **HIGHEST**
