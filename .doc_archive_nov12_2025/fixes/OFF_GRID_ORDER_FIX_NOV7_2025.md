# OFF-GRID ORDER FIX - November 7, 2025

## Problem Summary

Bot was placing orders at **OFF-GRID prices** like **$101,640.6** instead of grid-aligned prices like **$101,400** or **$101,700** (300-step grid from $90,000 to $110,000).

### Root Cause
Bot calculated correct grid-aligned prices (e.g., $108,900 from REF=$109,200 - STEP=$300) but placed LIMIT orders **ABOVE** current market price (~$101,640). The exchange immediately executed these as **TAKER orders at market price**, resulting in off-grid fills.

**Math Proof of OFF-GRID**:
```
Grid: LOWER=90000, STEP=300
Order: 101640.6

Offset = 101640.6 - 90000 = 11640.6
Remainder = 11640.6 % 300 = 240.6 ❌ (should be 0!)

Nearest valid levels: 101400, 101700
```

---

## Solution: 4-Layer Defense System

### Layer 1: Order Manager Validation (PRIMARY DEFENSE)

**File**: `bot/strategy/modules/order_manager.py`

#### Change 1: Add market price tracking
**Location**: After line ~118 (in `__init__` method, after `self._order_lock`)

```python
# ✅ FIX NOV 7: Store current market price for validation
self.current_market_price: Optional[float] = None
```

#### Change 2: Add update method
**Location**: After `__init__` method ends, before "Client Order ID Generation" section

```python
# ========================================================================
# Market Price Update (NOV 7 FIX)
# ========================================================================

def update_market_price(self, price: float) -> None:
    """
    Update current market price for order validation
    
    ✅ FIX NOV 7: Store market price to validate BUY/SELL orders
    are placed as MAKER (below/above market), not TAKER (at market)
    
    Args:
        price: Current market price from WebSocket ticker
    """
    self.current_market_price = price
```

#### Change 3: Add BUY validation
**Location**: In `place_buy_order()` method, after grid alignment check (~line 280), before "Safety check: Emergency stop"

```python
# ✅ FIX NOV 7: Validate BUY price is BELOW market (prevent TAKER execution)
current_market_price = self.current_market_price

if current_market_price and price >= current_market_price:
    log.error("=" * 80)
    log.error(f"❌ REJECTED: BUY price {price:,.2f} is AT or ABOVE market {current_market_price:,.2f}!")
    log.error(f"   This would execute as TAKER at market price (off-grid)!")
    log.error(f"   BUY orders must be placed BELOW market for MAKER execution.")
    log.error(f"   Suggested: Place at nearest grid level below market")
    log.error("=" * 80)
    
    # Send alert
    try:
        from bot.utils.notifier import TelegramNotifier
        notifier = TelegramNotifier()
        alert_msg = (
            f"🚨 Market Price Violation!\n\n"
            f"Attempted BUY: ${price:,.2f}\n"
            f"Market Price: ${current_market_price:,.2f}\n"
            f"This order was BLOCKED to prevent TAKER execution!\n\n"
            f"Bot logic needs adjustment."
        )
        notifier.send(alert_msg)
    except Exception:
        pass
    
    return None
```

#### Change 4: Add SELL validation
**Location**: In `place_sell_order()` method, after duplicate check (~line 460), before "Safety check: Emergency stop"

```python
# ✅ FIX NOV 7: Validate SELL price is ABOVE market (prevent TAKER execution)
current_market_price = self.current_market_price

if current_market_price and price <= current_market_price:
    log.error("=" * 80)
    log.error(f"❌ REJECTED: SELL price {price:,.2f} is AT or BELOW market {current_market_price:,.2f}!")
    log.error(f"   This would execute as TAKER at market price (off-grid)!")
    log.error(f"   SELL orders must be placed ABOVE market for MAKER execution.")
    log.error(f"   Suggested: Place at nearest grid level above market")
    log.error("=" * 80)
    
    # Send alert
    try:
        from bot.utils.notifier import TelegramNotifier
        notifier = TelegramNotifier()
        alert_msg = (
            f"🚨 Market Price Violation!\n\n"
            f"Attempted SELL: ${price:,.2f}\n"
            f"Market Price: ${current_market_price:,.2f}\n"
            f"This order was BLOCKED to prevent TAKER execution!\n\n"
            f"Bot logic needs adjustment."
        )
        notifier.send(alert_msg)
    except Exception:
        pass
    
    return None
```

---

### Layer 2: Grid Calculator Intelligence (SECONDARY DEFENSE)

**File**: `bot/strategy/modules/grid_calculator.py`

#### Change 1: Update `compute_next_buy_level()` signature
**Location**: Line ~78

**FIND**:
```python
def compute_next_buy_level(
    self,
    open_positions: List[Dict[str, Any]]
) -> Optional[float]:
```

**REPLACE WITH**:
```python
def compute_next_buy_level(
    self,
    open_positions: List[Dict[str, Any]],
    current_price: Optional[float] = None
) -> Optional[float]:
```

#### Change 2: Update docstring
**Location**: In same method, update the docstring

**FIND**:
```python
"""
Compute the next BUY level for grid trading

✅ FIX NOV 6: Added defensive grid alignment validation

Logic:
- If no positions: BUY at (ref - step)
- If positions exist: BUY at (lowest_entry - step)
- Quantize to tick size
- Return None if outside grid bounds

Args:
    open_positions: List of open position dicts with 'entry_price' key
    
Returns:
    Next BUY price (quantized), or None if no BUY needed
"""
```

**REPLACE WITH**:
```python
"""
Compute the next BUY level for grid trading

✅ FIX NOV 6: Added defensive grid alignment validation
✅ FIX NOV 7: Added current_price to prevent placing BUY above market

Logic:
- If no positions: BUY at (ref - step), or nearest grid below market if ref is too high
- If positions exist: BUY at (lowest_entry - step)
- Quantize to tick size
- Return None if outside grid bounds

Args:
    open_positions: List of open position dicts with 'entry_price' key
    current_price: Optional current market price (for validation)
    
Returns:
    Next BUY price (quantized), or None if no BUY needed
"""
```

#### Change 3: Update no-positions logic
**Location**: In same method, ~line 110

**FIND**:
```python
else:
    lowest_entry = self.ref
```

**REPLACE WITH**:
```python
else:
    # ✅ FIX NOV 7: If no positions and market price available, ensure we place BELOW market
    if current_price and current_price < self.ref:
        # Market is below REF, find nearest grid level below market
        lowest_entry = self.find_nearest_grid_below(current_price)
        if lowest_entry:
            log.info(f"📍 No positions + market below REF: using ${lowest_entry:,.0f} instead of REF ${self.ref:,.0f}")
        else:
            # No valid level below market within grid
            return None
    else:
        lowest_entry = self.ref
```

#### Change 4: Update `compute_next_sell_level()` signature
**Location**: Line ~145

**FIND**:
```python
def compute_next_sell_level(
    self,
    open_positions: List[Dict[str, Any]]
) -> Optional[float]:
```

**REPLACE WITH**:
```python
def compute_next_sell_level(
    self,
    open_positions: List[Dict[str, Any]],
    current_price: Optional[float] = None
) -> Optional[float]:
```

#### Change 5: Update SELL docstring
**Location**: In same method

**FIND**:
```python
"""
Compute the next SELL level for SHORT grid trading

✅ FIX NOV 6: Added defensive grid alignment validation

Logic (mirror of compute_next_buy_level):
- If no positions: SELL at (ref + step)
- If positions exist: SELL at (highest_entry + step)
- Quantize to tick size
- Return None if outside grid bounds

Args:
    open_positions: List of open position dicts with 'entry_price' key
    
Returns:
    Next SELL price (quantized), or None if no SELL needed
"""
```

**REPLACE WITH**:
```python
"""
Compute the next SELL level for SHORT grid trading

✅ FIX NOV 6: Added defensive grid alignment validation
✅ FIX NOV 7: Added current_price to prevent placing SELL below market

Logic (mirror of compute_next_buy_level):
- If no positions: SELL at (ref + step), or nearest grid above market if ref is too low
- If positions exist: SELL at (highest_entry + step)
- Quantize to tick size
- Return None if outside grid bounds

Args:
    open_positions: List of open position dicts with 'entry_price' key
    current_price: Optional current market price (for validation)
    
Returns:
    Next SELL price (quantized), or None if no SELL needed
"""
```

#### Change 6: Update SELL no-positions logic
**Location**: In same method

**FIND**:
```python
else:
    highest_entry = self.ref
```

**REPLACE WITH**:
```python
else:
    # ✅ FIX NOV 7: If no positions and market price available, ensure we place ABOVE market
    if current_price and current_price > self.ref:
        # Market is above REF, find nearest grid level above market
        highest_entry = self.find_nearest_grid_above(current_price)
        if highest_entry:
            log.info(f"📍 No positions + market above REF: using ${highest_entry:,.0f} instead of REF ${self.ref:,.0f}")
        else:
            # No valid level above market within grid
            return None
    else:
        highest_entry = self.ref
```

---

### Layer 3: Reconciliation Layer (TERTIARY DEFENSE)

**File**: `bot/strategy/modules/reconciliation.py`

#### Change 1: Update `ensure_single_correct_pending_buy()` signature
**Location**: Line ~204

**FIND**:
```python
def ensure_single_correct_pending_buy(self) -> None:
    """
    Invariant enforcer: Ensure exactly ONE pending buy at the correct price
    
    Extracted from Lines 1166-1189 (gbot_ws.py)
    
    Called after:
    - Fill detection (TP fills)
    - Config changes (hot-reload)
    - Periodic heartbeat (every ~10s)
    
    NOTE: Skips enforcement for Strict Grid startup orders to prevent
    cancellation of intentionally placed MAKER orders at non-standard prices.
    """
```

**REPLACE WITH**:
```python
def ensure_single_correct_pending_buy(self, current_price: Optional[float] = None) -> None:
    """
    Invariant enforcer: Ensure exactly ONE pending buy at the correct price
    
    ✅ FIX NOV 7: Added current_price parameter to prevent placing BUY above market
    
    Extracted from Lines 1166-1189 (gbot_ws.py)
    
    Called after:
    - Fill detection (TP fills)
    - Config changes (hot-reload)
    - Periodic heartbeat (every ~10s)
    
    NOTE: Skips enforcement for Strict Grid startup orders to prevent
    cancellation of intentionally placed MAKER orders at non-standard prices.
    
    Args:
        current_price: Optional current market price for validation
    """
```

#### Change 2: Pass current_price to grid calculator
**Location**: In same method, ~line 228

**FIND**:
```python
# Compute target BUY price based on current positions
positions = self.position_mgr.get_positions()
target = self.grid_calc.compute_next_buy_level(positions)
```

**REPLACE WITH**:
```python
# Compute target BUY price based on current positions
positions = self.position_mgr.get_positions()
target = self.grid_calc.compute_next_buy_level(positions, current_price)
```

#### Change 3: Update `ensure_single_correct_pending_sell()` signature
**Location**: Line ~293

**FIND**:
```python
def ensure_single_correct_pending_sell(self) -> None:
    """
    Invariant enforcer: Ensure exactly ONE pending sell at the correct price (SHORT mode)
    
    SHORT mode equivalent of ensure_single_correct_pending_buy().
    
    Called after:
    - Fill detection (TP fills in SHORT mode)
    - Config changes (hot-reload)
    - Periodic heartbeat (every ~10s)
    
    NOTE: Skips enforcement for Strict Grid startup orders to prevent
    cancellation of intentionally placed MAKER orders at non-standard prices.
    """
```

**REPLACE WITH**:
```python
def ensure_single_correct_pending_sell(self, current_price: Optional[float] = None) -> None:
    """
    Invariant enforcer: Ensure exactly ONE pending sell at the correct price (SHORT mode)
    
    ✅ FIX NOV 7: Added current_price parameter to prevent placing SELL below market
    
    SHORT mode equivalent of ensure_single_correct_pending_buy().
    
    Called after:
    - Fill detection (TP fills in SHORT mode)
    - Config changes (hot-reload)
    - Periodic heartbeat (every ~10s)
    
    NOTE: Skips enforcement for Strict Grid startup orders to prevent
    cancellation of intentionally placed MAKER orders at non-standard prices.
    
    Args:
        current_price: Optional current market price for validation
    """
```

#### Change 4: Pass current_price for SELL
**Location**: In same method, ~line 318

**FIND**:
```python
# Compute target SELL price based on current positions
positions = self.position_mgr.get_positions()
target = self.grid_calc.compute_next_sell_level(positions)
```

**REPLACE WITH**:
```python
# Compute target SELL price based on current positions
positions = self.position_mgr.get_positions()
target = self.grid_calc.compute_next_sell_level(positions, current_price)
```

---

### Layer 4: Main Loop Integration (GLUE LAYER)

**File**: `bot/strategy/gridbot.py`

#### Change 1: Update market price in OrderManager
**Location**: In `_handle_ticker()` method, ~line 340

**FIND**:
```python
try:
    # Update price tracking
    self.previous_price = self.current_price
    self.current_price = ticker_data.get('last', 0)
    self.last_price_update = time.time()  # Record timestamp
```

**REPLACE WITH**:
```python
try:
    # Update price tracking
    self.previous_price = self.current_price
    self.current_price = ticker_data.get('last', 0)
    self.last_price_update = time.time()  # Record timestamp
    
    # ✅ FIX NOV 7: Update order manager with current market price for validation
    self.order_mgr.update_market_price(self.current_price)
```

#### Change 2: Pass current_price to reconciliation
**Location**: In `run()` main loop, ~line 1285

**FIND**:
```python
# Enforce pending order invariant (mode-aware)
try:
    if self.grid_mode == 'LONG':
        self.reconciler.ensure_single_correct_pending_buy()
    else:
        self.reconciler.ensure_single_correct_pending_sell()
except Exception as e:
    log.warning(f"Invariant enforcement failed: {e}")
```

**REPLACE WITH**:
```python
# Enforce pending order invariant (mode-aware)
try:
    if self.grid_mode == 'LONG':
        self.reconciler.ensure_single_correct_pending_buy(self.current_price)
    else:
        self.reconciler.ensure_single_correct_pending_sell(self.current_price)
except Exception as e:
    log.warning(f"Invariant enforcement failed: {e}")
```

---

## Test Results (Windows Bot - Nov 7, 2025)

```
✅ Bot started successfully
✅ Initial order: $101,700 (market: $101,949) - BELOW market, MAKER order
✅ No off-grid orders detected
✅ No TAKER executions
✅ No order rejections
✅ Bot stable with 0 restarts
✅ Running for 40+ minutes without issues
```

**Log Evidence**:
```
2025-11-07 10:17:40: 🎯 Calculating initial order (Strict Grid enabled for LONG mode)...
2025-11-07 10:17:40: 📍 Placing initial MAKER BUY @ $101,700
2025-11-07 10:17:40:    Current Market: $101,949
2025-11-07 10:17:41: ✅ Initial MAKER BUY placed @ $101,700 (Volatility: SAFE)
2025-11-07 10:17:41: 🔒 Protected from reconciliation until fill

2025-11-07 10:35:42: [HB] Positions: 0/10, Price: $102,169 | Bid: $102,168.2
```

---

## How This Fix Works

### Before Fix ❌
```
1. Bot: "No positions, use REF"
   → Target = 109200 - 300 = 108900

2. Bot: "Place BUY at $108,900"
   → Market is $101,640

3. Exchange: "BUY limit at $108,900 is ABOVE market!"
   → Executes immediately as TAKER at $101,640.6

4. Result: OFF-GRID FILL at $101,640.6 ❌
```

### After Fix ✅
```
1. Bot: "No positions, use REF"
   → Target would be 109200 - 300 = 108900

2. Grid Calculator: "Wait! Market is $101,949 < REF $109,200"
   → Recalculate: Find nearest grid BELOW market
   → New target = $101,700 (grid-aligned, below market)

3. Order Manager: "Validate: $101,700 < $101,949 ✅"
   → Place LIMIT order at $101,700

4. Exchange: "BUY limit at $101,700 is BELOW market"
   → Order sits as MAKER, waits for price to drop

5. Result: ON-GRID FILL at $101,700 when market reaches it ✅
```

---

## Files to Update on macOS

**Option 1: Copy from Windows**
```bash
# Copy these 4 files from Windows to macOS:
scp user@windows:/d/Projects/WorkingBot/bot/strategy/modules/order_manager.py \
    bot/strategy/modules/order_manager.py

scp user@windows:/d/Projects/WorkingBot/bot/strategy/modules/grid_calculator.py \
    bot/strategy/modules/grid_calculator.py

scp user@windows:/d/Projects/WorkingBot/bot/strategy/modules/reconciliation.py \
    bot/strategy/modules/reconciliation.py

scp user@windows:/d/Projects/WorkingBot/bot/strategy/gridbot.py \
    bot/strategy/gridbot.py
```

**Option 2: Apply changes manually** using the diff blocks in this document.

---

## Verification Checklist for macOS

After updating, verify:

- [ ] Bot starts without errors
- [ ] Initial order is placed BELOW market (LONG mode) or ABOVE market (SHORT mode)
- [ ] Check logs for "📍 Placing initial MAKER BUY @ $X,XXX"
- [ ] Verify "Current Market: $X,XXX" shows order is below market
- [ ] No logs showing "REJECTED" or "AT or ABOVE market"
- [ ] All orders show as MAKER orders, not TAKER
- [ ] No off-grid fills (all fills at 300-step intervals: 90000, 90300, 90600, etc.)
- [ ] PM2 shows 0 restarts after 5+ minutes

**Search for problems**:
```bash
# Check for rejections
grep -i "rejected\|blocked\|at or above\|at or below" bot/logs/*.log

# Check for TAKER executions (exclude Strict Grid logs)
grep -i "taker" bot/logs/*.log | grep -v "Strict Grid"

# Verify all fills are grid-aligned
grep -i "fill detected" bot/logs/*.log

# Check for off-grid orders
grep -i "off-grid" bot/logs/*.log
```

---

## Summary Table

| Component | What Changed | Why |
|-----------|--------------|-----|
| **OrderManager** | Added market price validation | PRIMARY: Reject orders that would execute as TAKER |
| **GridCalculator** | Added current_price parameter | SECONDARY: Calculate correct level when market != REF |
| **Reconciliation** | Pass current_price to calculator | TERTIARY: Ensure reconciliation uses market-aware logic |
| **GridBot** | Update price & pass to reconciliation | GLUE: Connect all layers with real-time price |

---

## Key Concepts

### MAKER vs TAKER Orders
- **MAKER**: Order sits in orderbook, adds liquidity, gets rebate
  - BUY limit BELOW market price
  - SELL limit ABOVE market price
- **TAKER**: Order matches immediately, removes liquidity, pays fee
  - BUY limit AT or ABOVE market price ← **This was our problem!**
  - SELL limit AT or BELOW market price

### Grid Alignment
Valid prices must be: `LOWER + (N × STEP)` where N is an integer

Example with LOWER=90000, STEP=300:
```
✅ 90000 (N=0)
✅ 90300 (N=1)
✅ 90600 (N=2)
...
✅ 101400 (N=38)
✅ 101700 (N=39)
❌ 101640.6 (N=38.802) ← OFF-GRID!
✅ 102000 (N=40)
```

---

## Troubleshooting

### If bot rejects orders:
```
❌ REJECTED: BUY price 108900.00 is AT or ABOVE market 101949.00!
```
**This is CORRECT behavior!** The fix is working. The bot is preventing off-grid orders.

### If no orders are placed:
Check if market is outside grid bounds:
```bash
grep "Grid:" bot/logs/*.log
grep "Market:" bot/logs/*.log
```

If market > UPPER (LONG) or market < LOWER (SHORT), bot won't place orders (as designed).

### If still seeing TAKER executions:
Check if this is the Strict Grid startup order:
```bash
grep "TAKER" bot/logs/*.log
```

Strict Grid logs may mention "would have been TAKER" but the actual order should be MAKER.

---

**Fix Date**: November 7, 2025  
**Tested On**: Windows Bot (Delta Exchange India Testnet)  
**Status**: ✅ WORKING - No off-grid orders in 40+ minutes of testing
