# Root Cause Analysis: Guardian API Timeout Issue
**Date:** December 14, 2025  
**Issue:** Bot shutdown due to stale Guardian signal during API timeouts

---

## 🔍 Deep Dive: The Real Problem

### What I Found Initially (Symptom)
- Guardian signal became stale (51 seconds old)
- Bot shutdown at 05:57:43 AM
- Multiple API timeouts from 05:57:00 to 05:57:33

### What I Found Now (Root Cause)

**Critical Bug in `integrated_monitor.py`:**

```python
def get_status(self) -> Dict:
    # Called every 5 seconds by Guardian
    positions = self.fetch_positions()      # API call #1: GET /v2/positions/margined
    balance = self.fetch_balances()         # API call #2: GET /v2/wallet/balances
                                            # └─ INTERNALLY calls fetch_positions() AGAIN!
    open_orders = self.fetch_open_orders()  # API call #3: GET /v2/orders
```

**The Chain Reaction:**
1. Guardian tries to generate signal every 5 seconds
2. `_get_pnl_details()` calls `liquidation_monitor.get_status()`
3. `get_status()` makes **4 API calls** (positions fetched TWICE!)
4. Each call has 15-second timeout
5. When Delta Exchange is slow:
   - First timeout: 15s (positions)
   - Retry + Second timeout: 15s (balances + positions again)
   - Retry + Third timeout: 15s (orders)
   - **Total: 30-45+ seconds blocked**
6. Signal publishing blocked → Bot thinks Guardian died → Shutdown

---

## 🐛 The Bugs

### Bug #1: Duplicate API Calls
**File:** `bot/liquidation/integrated_monitor.py`  
**Lines:** 550, 367

```python
# Line 550 in get_status():
positions = self.fetch_positions()  # ❌ First call

# Line 367 in fetch_balances():
positions = self.fetch_positions()  # ❌ Second call (same data!)
```

**Impact:** Doubles API load, doubles timeout risk

### Bug #2: Sequential Blocking Calls  
All API calls execute sequentially, blocking Guardian's event loop:
```python
positions = self.fetch_positions()      # Blocks for 0-15s
balance = self.fetch_balances()         # Blocks for 0-15s  
open_orders = self.fetch_open_orders()  # Blocks for 0-15s
# Total: 0-45s blocked (cascading timeouts)
```

**Impact:** One slow endpoint blocks entire signal generation

### Bug #3: No Caching/Memoization
- Fresh API calls every 5 seconds
- No cache even when data unchanged
- Unnecessary load on Delta Exchange API

**Impact:** Higher chance of rate limiting and timeouts

### Bug #4: No Timeout Protection
- Guardian's `_generate_signal()` has no timeout wrapper
- Can block indefinitely during API issues
- My previous fix added 4s timeout (symptom fix, not root cause fix)

---

## ✅ The Complete Solution

### Fix #1: Eliminate Duplicate fetch_positions() Call ⭐ CRITICAL

**File:** `bot/liquidation/integrated_monitor.py`  
**Method:** `fetch_balances()`

**Problem:**
```python
def fetch_balances(self) -> AccountBalance:
    # ... existing code ...
    
    # ❌ BUG: Fetches positions AGAIN (already fetched in get_status)
    positions = self.fetch_positions()
```

**Solution:** Accept positions as parameter:
```python
def fetch_balances(self, positions: List[Position] = None) -> AccountBalance:
    """
    Fetch account balance from Delta Exchange
    
    Args:
        positions: Optional pre-fetched positions to avoid duplicate API call
    """
    try:
        response = self.delta_client.get_wallet_balances()
        
        # ... balance extraction ...
        
        # ✅ FIX: Use provided positions or fetch only if needed
        total_upnl_usd = 0
        if positions is None:
            positions = self.fetch_positions()  # Only fetch if not provided
        
        # Calculate PnL from positions
        for pos in positions:
            pnl_usd = pos.unrealized_pnl / 85
            total_upnl_usd += pnl_usd
```

**Then update get_status():**
```python
def get_status(self) -> Dict:
    # Fetch data - positions only ONCE
    positions = self.fetch_positions()          # ✅ Single call
    balance = self.fetch_balances(positions)    # ✅ Reuse positions
    open_orders = self.fetch_open_orders()
```

**Impact:**  
- ✅ Cuts API calls from 4 to 3 per cycle  
- ✅ Reduces timeout risk by 25%  
- ✅ Reduces load on Delta Exchange

---

### Fix #2: Add Async/Concurrent API Calls

**File:** `bot/liquidation/integrated_monitor.py`  
**Method:** `get_status()`

**Current (Sequential):**
```python
positions = self.fetch_positions()      # 0-15s
balance = self.fetch_balances()         # 0-15s
open_orders = self.fetch_open_orders()  # 0-15s
# Total: 0-45s
```

**Fixed (Concurrent):**
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def get_status_async(self) -> Dict:
    """Fetch all data concurrently to avoid cascading timeouts"""
    try:
        # Execute all API calls concurrently
        with ThreadPoolExecutor(max_workers=3) as executor:
            loop = asyncio.get_event_loop()
            positions_future = loop.run_in_executor(executor, self.fetch_positions)
            orders_future = loop.run_in_executor(executor, self.fetch_open_orders)
            
            # Wait for positions first (needed for balance calculation)
            positions = await positions_future
            
            # Fetch balance with positions already loaded
            balance_future = loop.run_in_executor(
                executor, 
                self.fetch_balances, 
                positions
            )
            
            # Wait for remaining calls
            balance = await balance_future
            open_orders = await orders_future
        
        # ... rest of get_status logic ...
```

**Impact:**  
- ✅ Max wait time = slowest endpoint (not sum of all)
- ✅ 15s worst case (vs 45s sequential)
- ✅ 66% faster data collection

---

### Fix #3: Add Response Caching

**File:** `bot/liquidation/integrated_monitor.py`

**Add caching decorator:**
```python
from functools import lru_cache, wraps
import time

def cached_with_ttl(ttl_seconds=3):
    """Cache result for TTL seconds"""
    def decorator(func):
        cache = {}
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            cache_key = str(args) + str(kwargs)
            
            if cache_key in cache:
                result, timestamp = cache[cache_key]
                if now - timestamp < ttl_seconds:
                    return result
            
            result = func(*args, **kwargs)
            cache[cache_key] = (result, now)
            return result
        
        return wrapper
    return decorator

@cached_with_ttl(ttl_seconds=3)  # Cache for 3 seconds
def fetch_positions(self) -> List[Position]:
    """Fetch positions with 3-second cache"""
    # ... existing implementation ...
```

**Impact:**  
- ✅ Reduces API calls if Guardian/WebUI query simultaneously
- ✅ Protects against accidental rapid polling
- ✅ Smoother experience during high load

---

### Fix #4: Already Applied (Symptom Fix)

**File:** `bot/guardian/engine/risk_decision_engine.py`  
**Applied in previous fix:**
```python
# Wrap signal generation with 4-second timeout
signal_data = await asyncio.wait_for(
    asyncio.to_thread(self._generate_signal),
    timeout=4.0
)
```

**Keep this** - it's a good safety net even after root cause fixes.

---

## 📊 Impact Analysis

### Before All Fixes
```
API Calls per cycle: 4 (positions fetched 2x)
Sequential execution: 0-45s worst case
No timeout protection
No caching

Result: Cascading timeouts → Signal stale → Bot shutdown
```

### After Previous Fix Only (Symptom)
```
API Calls per cycle: 4 (still duplicate)
Sequential execution: 0-45s worst case
4s timeout protection ✅
No caching

Result: Degraded signals during timeouts (partial fix)
```

### After All Fixes (Root Cause)
```
API Calls per cycle: 3 ✅ (duplicate removed)
Concurrent execution: 0-15s worst case ✅
4s timeout protection ✅
3s response caching ✅

Result: No degraded signals, proper resilience
```

---

## 🚀 Implementation Priority

### Priority 1 (CRITICAL - Do First)
**Fix #1:** Eliminate duplicate fetch_positions()  
- Simplest fix
- Biggest immediate impact
- No architectural changes needed

### Priority 2 (HIGH - Do Soon)  
**Fix #2:** Concurrent API calls
- Prevents cascading timeouts
- Significant performance improvement

### Priority 3 (MEDIUM - Nice to Have)
**Fix #3:** Response caching
- Reduces API load
- Improves reliability

---

## 🧪 Testing Plan

### Test 1: Simulate API Timeout
```python
# In delta_client.py, temporarily add:
time.sleep(10)  # Simulate slow API

# Expected: Guardian still publishes signals every 5s
# Expected: No bot shutdown
```

### Test 2: Verify Duplicate Removal
```python
# Add counter in fetch_positions():
self.fetch_count = getattr(self, 'fetch_count', 0) + 1
print(f"fetch_positions called: {self.fetch_count} times")

# Run for 30 seconds
# Expected: ~6 calls (every 5s)
# Before fix: ~12 calls (duplicate)
```

### Test 3: Measure Performance
```python
import time

start = time.time()
status = liquidation_monitor.get_status()
elapsed = time.time() - start

print(f"get_status() took {elapsed:.2f}s")

# Expected: <1s normal, <15s worst case
# Before: <3s normal, <45s worst case
```

---

## 📝 Files to Modify

### Must Fix (Priority 1)
1. `bot/liquidation/integrated_monitor.py`
   - Line 367: Remove duplicate fetch_positions()
   - Line 330: Update fetch_balances() signature
   - Line 551: Pass positions to fetch_balances()

### Should Fix (Priority 2)
2. `bot/liquidation/integrated_monitor.py`
   - Add async get_status_async() method
   - Use ThreadPoolExecutor for concurrent calls

### Nice to Have (Priority 3)
3. `bot/liquidation/integrated_monitor.py`
   - Add @cached_with_ttl decorator
   - Apply to fetch_positions(), fetch_balances(), fetch_open_orders()

---

## ✅ Summary

**Previous Fix:** Added timeout protection (symptom)  
**This Fix:** Eliminate duplicate API calls + concurrent execution (root cause)  
**Result:** Guardian remains responsive even during API slowdowns  
**Benefit:** No more false shutdowns, better performance, lower API load

---

**Analysis Date:** December 14, 2025  
**Status:** Root cause identified, fixes designed, ready to implement
