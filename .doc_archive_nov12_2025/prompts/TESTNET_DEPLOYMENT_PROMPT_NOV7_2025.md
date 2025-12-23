# 🚀 TESTNET DEPLOYMENT PROMPT - November 7, 2025

## 📋 **CRITICAL: Apply These Fixes to Your Testnet Computer**

**Testnet Computer**: Different machine running same codebase  
**Live Computer**: This machine (fixes already applied)  
**Purpose**: Keep both environments synchronized with production-ready fixes

---

## ✅ **FIXES APPLIED ON LIVE (Copy to Testnet)**

### **FIX #1: Add Mutex Locks to OrderManager** ✅ CRITICAL

**File**: `bot/strategy/modules/order_manager.py`

**Step 1**: Add import at top of file (around line 14):
```python
import threading
```

**Step 2**: Add lock initialization in `__init__` method (around line 118, after order logger setup):
```python
# ✅ FIX NOV 6: Add order placement lock to prevent race conditions
self._order_lock = threading.RLock()  # Reentrant lock (same thread can re-acquire)
log.info("✅ OrderManager: Order placement lock initialized")
```

**Step 3**: Wrap `place_buy_order()` with lock (around line 208):

Find:
```python
def place_buy_order(
    self,
    price: float,
    post_only: bool = False,
    emergency_stop_check: Optional[Callable[[], bool]] = None,
    volatility_check: Optional[Callable[[], tuple]] = None,
    liquidation_check: Optional[Callable[[], tuple]] = None
) -> Optional[str]:
    """
    Place BUY order with safety checks
    
    Args:
        ...
    """
    # Safety check: Price validation
    if not price or price <= 0:
        log.error(f"❌ Invalid price: {price} - must be positive")
        return None
```

Replace with:
```python
def place_buy_order(
    self,
    price: float,
    post_only: bool = False,
    emergency_stop_check: Optional[Callable[[], bool]] = None,
    volatility_check: Optional[Callable[[], tuple]] = None,
    liquidation_check: Optional[Callable[[], tuple]] = None
) -> Optional[str]:
    """
    Place BUY order with safety checks
    
    ✅ FIX NOV 6: Added function-level lock to prevent race conditions
    
    Args:
        ...
    """
    # ✅ FIX NOV 6: Acquire lock before ANY logic to prevent race conditions
    with self._order_lock:
        # Safety check: Price validation
        if not price or price <= 0:
            log.error(f"❌ Invalid price: {price} - must be positive")
            return None
        
        # Safety check: Quantity validation
        if not self.lot_size or self.lot_size <= 0:
            log.error(f"❌ Invalid lot size: {self.lot_size} - must be positive")
            return None
        
        # Quantize price first (for duplicate check)
        price = self.grid_calc.quantize_price(price)
        
        # ✅ FIX NOV 6: Check if order already pending at this price (while holding lock)
        current_pending = self.position_mgr.get_pending_buy()
        if current_pending:
            pending_price = current_pending.get('price')
            if pending_price and abs(float(pending_price) - float(price)) < 1e-6:
                log.warning(f"⚠️ BUY order already pending @ ${price:,.0f} - skipping duplicate")
                return current_pending.get('order_id')
        
        # ... REST OF YOUR EXISTING CODE (all indented inside the `with` block) ...
        # Make sure ALL the existing logic stays inside the `with self._order_lock:` block
        # until the final return statement
```

**Step 4**: Before the LAST line of `place_buy_order()` (before final `return None`), ensure the lock scope ends:
```python
        except Exception as e:
            log.error(f"❌ Error placing BUY order: {e}")
            import traceback
            log.error(traceback.format_exc())
            return None
    # Lock released here
```

**Step 5**: Repeat same pattern for `place_sell_order()` (around line 369):
- Wrap entire function body with `with self._order_lock:`
- Add duplicate check after quantizing price
- Check `get_pending_sell()` instead of `get_pending_buy()`

---

### **FIX #2: Grid Alignment Validation**

**File**: `bot/strategy/modules/position_manager.py`

**Location**: Find `add_position()` method (around line 80-120)

**Add this code at the START of the function** (after the `with self._state_lock:` line if it exists):

```python
def add_position(self, entry_price: float, size: int, side: str, order_id: str) -> Dict:
    """
    Add new position with grid alignment validation
    
    ✅ FIX NOV 6: Validate entry_price is grid-aligned before adding
    """
    with self._state_lock:  # Your existing lock (if present)
        # ✅ FIX NOV 6: Validate entry price is grid-aligned BEFORE adding
        if hasattr(self, 'grid_calc') and self.grid_calc:
            if not self.grid_calc.is_price_grid_aligned(entry_price):
                log.error(f"🚨 CRITICAL: Attempted to add position @ ${entry_price:,.2f} (OFF-GRID!)")
                log.error(f"   Grid Step: {self.grid_calc.step}")
                log.error(f"   Rounding to nearest grid level...")
                
                # Snap to nearest grid level
                corrected_price = self.grid_calc.find_nearest_grid_level(entry_price)
                log.warning(f"   Corrected from ${entry_price:,.2f} to ${corrected_price:,.2f}")
                entry_price = corrected_price
        
        # ... REST OF YOUR EXISTING add_position() CODE ...
```

---

### **FIX #3: Grid Calculator Defensive Checks**

**File**: `bot/strategy/modules/grid_calculator.py`

**Location**: Find `compute_next_buy_level()` method (around line 70-100)

**Add defensive checks BEFORE calculating target**:

```python
def compute_next_buy_level(self, open_positions: List[Dict[str, Any]]) -> Optional[float]:
    """
    Compute the next BUY level for grid trading
    
    ✅ FIX NOV 6: Added defensive grid alignment validation
    """
    # Find lowest entry price
    if open_positions:
        lowest_entry = min(p['entry_price'] for p in open_positions)
        
        # ✅ FIX NOV 6: Validate lowest_entry is grid-aligned
        if not self.is_price_grid_aligned(lowest_entry):
            log.error(f"⚠️ Position entry ${lowest_entry:,.2f} is OFF-GRID!")
            log.error(f"   Snapping to nearest grid level...")
            lowest_entry = self.find_nearest_grid_level(lowest_entry)
            log.warning(f"   Corrected to: ${lowest_entry:,.2f}")
    else:
        lowest_entry = self.ref
    
    # Calculate target one step below
    target = lowest_entry - self.step
    
    # ✅ FIX NOV 6: Double-check target is grid-aligned
    if not self.is_price_grid_aligned(target):
        log.critical(f"🚨 CRITICAL: Calculated target ${target:,.2f} is OFF-GRID!")
        log.critical(f"   This should NEVER happen if entry prices are valid!")
        # Force snap to grid
        target = self.find_nearest_grid_level(target)
        log.critical(f"   Emergency correction to: ${target:,.2f}")
    
    # Validate within bounds
    if not self.is_within_bounds(target):
        return None
    
    return self.quantize_price(target)
```

**Repeat for `compute_next_sell_level()`** (same logic, but `target = lowest_entry + self.step`)

---

### **FIX #4: Cancel Order Pre-Check**

**File**: `bot/strategy/modules/order_manager.py`

**Location**: Find `cancel_order()` method (around line 500-600)

**Add this code at the START of the method**:

```python
def cancel_order(self, order_id: str, verify: bool = True, max_retries: int = 5) -> bool:
    """
    Cancel order with pre-check
    
    ✅ FIX NOV 6: Check order state BEFORE cancel to avoid 404 cascade
    """
    # ✅ FIX NOV 6: Query order state BEFORE attempting cancel
    try:
        order_status = self.api_client.get_order(order_id)
        if order_status.get('success'):
            state = order_status.get('result', {}).get('state', '').lower()
            
            if state == 'filled':
                log.info(f"✅ Order {order_id} already filled - skipping cancel")
                return True  # No need to cancel
            
            if state in ['cancelled', 'rejected']:
                log.info(f"✅ Order {order_id} already {state} - skipping cancel")
                return True
    except Exception as e:
        log.warning(f"⚠️ Could not pre-check order state for {order_id}: {e}")
    
    # ... REST OF YOUR EXISTING cancel_order() CODE ...
```

---

### **FIX #5: Circuit Breaker Error Classification**

**File**: `bot/api/delta_client.py` (or wherever your circuit breaker is)

**Location**: Find the `CircuitBreaker` class or circuit breaker logic

**Add IGNORED_ERRORS list**:

```python
class CircuitBreaker:
    # ✅ FIX NOV 6: Errors that should NOT trigger circuit breaker
    IGNORED_ERRORS = [
        'order_not_found',
        'order_already_cancelled',
        'order_already_filled',
        'insufficient_margin',  # User error, not API failure
        'invalid_price',  # Validation error, not API failure
        'insufficient_balance'
    ]
    
    def __init__(self, failure_threshold=5, timeout=30):  # ✅ Changed from 3 to 5, 60 to 30
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        # ... rest of init ...
    
    def record_failure(self, error_response: Dict):
        """
        Record API failure
        
        ✅ FIX NOV 6: Exclude expected errors from failure count
        """
        error_code = error_response.get('error', {}).get('code', '')
        
        # ✅ FIX NOV 6: Skip expected errors
        if error_code in self.IGNORED_ERRORS:
            log.debug(f"Circuit breaker: Ignoring '{error_code}' (expected)")
            return
        
        # Record actual failure
        self.failure_count += 1
        
        if self.failure_count >= self.failure_threshold:
            self._open_circuit()
```

---

## 🧪 **TESTING STEPS (Run on Testnet)**

### **Step 1: Syntax Validation**
```bash
cd /path/to/testnet/bot
python3 -m py_compile bot/strategy/modules/order_manager.py
python3 -m py_compile bot/strategy/modules/position_manager.py
python3 -m py_compile bot/strategy/modules/grid_calculator.py
```

### **Step 2: Run Unit Tests (if available)**
```bash
pytest tests/test_concurrency.py -v
pytest tests/ -v
```

### **Step 3: Start Bot and Monitor**
```bash
# Stop current bot
python3 bot_stopper.py

# Start with fixes
python3 bot_launcher.py

# Monitor logs in real-time
tail -f logs/bot_live.log | grep -E "DUPLICATE|OFF-GRID|Circuit breaker|⚠️|❌"
```

### **Step 4: Watch for These Indicators**

**✅ GOOD SIGNS:**
- `✅ OrderManager: Order placement lock initialized`
- `⚠️ BUY/SELL order already pending @ $X - skipping duplicate` (if duplicate attempted)
- `✅ Order X already filled - skipping cancel` (if cancel attempted on filled order)
- `Circuit breaker: Ignoring 'order_not_found' (expected)` (if 404 occurs)

**❌ BAD SIGNS (Requires Investigation):**
- Multiple orders placed at same price within 1 second
- `🚨 CRITICAL: Calculated target $X is OFF-GRID!`
- `Circuit breaker OPEN` (if triggered by expected errors)

---

## 📊 **VALIDATION CHECKLIST**

After applying fixes, run bot for 1-2 hours on testnet and verify:

- [ ] ✅ Zero duplicate orders at same price
- [ ] ✅ Zero off-grid order attempts
- [ ] ✅ Circuit breaker does NOT trigger on 404 errors
- [ ] ✅ Fill detection working normally
- [ ] ✅ Bot survives high volatility without hanging
- [ ] ✅ Position count never exceeds LOT_SIZE per level

---

## 🚨 **ROLLBACK PLAN** (If Something Breaks)

If bot crashes or behaves incorrectly after applying fixes:

1. **Immediate Stop**:
   ```bash
   python3 bot_stopper.py
   ```

2. **Revert Changes**:
   ```bash
   git status  # See what changed
   git checkout -- bot/strategy/modules/order_manager.py
   git checkout -- bot/strategy/modules/position_manager.py
   git checkout -- bot/strategy/modules/grid_calculator.py
   ```

3. **Restart Old Version**:
   ```bash
   python3 bot_launcher.py
   ```

4. **Report Issue**: Save logs and report what went wrong

---

## 📝 **NOTES**

1. **These fixes are IDENTICAL** to what's running on your live computer
2. **Test on testnet FIRST** before any live deployment
3. **Monitor for 24 hours** on testnet before considering production
4. **Keep logs** of both testnet and live for comparison

---

## ✅ **COMPLETION VERIFICATION**

After applying all fixes, verify your testnet code matches live:

```bash
# On testnet computer
cd /path/to/testnet/bot

# Check if threading import exists
grep "import threading" bot/strategy/modules/order_manager.py

# Check if lock initialization exists
grep "_order_lock = threading.RLock()" bot/strategy/modules/order_manager.py

# Check if lock usage exists in place_buy_order
grep -A 3 "with self._order_lock:" bot/strategy/modules/order_manager.py

# Check grid alignment validation
grep "is_price_grid_aligned" bot/strategy/modules/position_manager.py

# Check cancel pre-check
grep "already filled - skipping cancel" bot/strategy/modules/order_manager.py

# Check circuit breaker
grep "IGNORED_ERRORS" bot/api/delta_client.py
```

All commands should return matches if fixes are applied correctly.

---

**Status**: Ready for Testnet Deployment  
**Est. Time**: 30-45 minutes to apply all fixes  
**Risk Level**: Low (fixes are defensive, add safety checks)  
**Testing Required**: 24 hours on testnet before live consideration

---

**Good luck! 🚀**
