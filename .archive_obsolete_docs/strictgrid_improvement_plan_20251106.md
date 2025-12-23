# Strict Grid Improvement Plan - November 6, 2025

## Current Understanding

### What is "Strict Grid"?

Strict Grid is a **two-part trading discipline** that ensures grid trading remains clean, profitable, and executable:

---

## Part 1: Grid Alignment Validation (✅ ALREADY IMPLEMENTED)

### Purpose
Prevent orders at non-grid prices that would break the grid structure.

### Current Implementation
- Located in: `bot/strategy/modules/order_manager.py` (Line 144-177)
- Function: `_is_price_grid_aligned()`
- Validates BEFORE placing any order
- Rejects orders like $108,700 when grid is $90k, $90.3k, $90.6k...

### Example
```
Grid: $90,000 + (n × $300)
Valid: $90,000, $90,300, $90,600, ..., $108,600, $108,900, $109,200
Invalid: $108,700 ❌ (not on grid, REJECTED)
```

### Status
✅ **WORKING** - Successfully blocked $108,700 order attempt today

---

## Part 2: Market-Aware Grid Execution (❌ NOT YET IMPLEMENTED)

### Purpose
**ONE-TIME BEHAVIOR AT BOT STARTUP ONLY**: Place initial order at nearest MAKER level below market price.

### When This Applies
- ✅ **Bot startup** (first order placement)
- ❌ **NOT during normal operation** (after first fill, normal grid logic resumes)

### Business Logic

**Problem**: At startup, if grid calculation says place BUY at $120 but market is trading at $102:
- $120 BUY = TAKER order (market above this price) ❌ Fills immediately, pays fee
- Normal grid logic would place this order blindly

**Solution**: At **startup only**, bot should:
1. Calculate what grid says to place (e.g., $120)
2. Check current market price (e.g., $102)
3. If calculated price is ABOVE market, skip to **nearest grid level BELOW market**
4. Place that as MAKER order (e.g., $100)
5. **After first fill**, resume normal grid behavior (place next order one step below filled position)

### Comprehensive Example - Bot Startup Behavior

**Grid Configuration:**
```
GRIDBOT_LOWER = 800
GRIDBOT_UPPER = 1500
GRIDBOT_STEP = 10
GRIDBOT_REF = 1000
```

**Valid Grid Levels:**
```
800, 810, 820, 830, 840, 850, 860, 870, 880, 890, 
900, 910, 920, 930, 940, 950, 960, 970, 980, 990, 
1000, 1010, 1020, 1030, 1040, 1050...1500
```

**Market Conditions at Startup:**
```
Current LTP (Last Traded Price): 960
No existing positions (fresh start)
```

---

### Scenario 1: WITHOUT Strict Grid Part 2 (Current Behavior)

**Bot Logic:**
```python
# No positions, so calculate from reference
target = GRIDBOT_REF - GRIDBOT_STEP
target = 1000 - 10 = 990
```

**What Happens:**
1. Bot calculates: "Place BUY @ 990"
2. Bot sends order: BUY @ 990
3. **Market is at 960** (below 990)
4. Order fills **IMMEDIATELY** as **TAKER** order ❌
5. Bot pays TAKER fee (0.05%)
6. Bot now has position at 990, waits for TP at 1000

**Problem:**
- Bot bought ABOVE current market price (990 when market at 960)
- This is NOT "buying the dip" - it's buying a rally
- Paid TAKER fees instead of earning MAKER rebate
- Lost 0.07% in fees = ₹70 per ₹1,00,000

---

### Scenario 2: WITH Strict Grid Part 2 (New Behavior)

**Bot Logic at Startup:**
```python
# Calculate from reference
calculated_target = GRIDBOT_REF - GRIDBOT_STEP
calculated_target = 1000 - 10 = 990

# Check market price
current_ltp = 960

# Is calculated target above market?
if calculated_target >= current_ltp:
    # YES - Skip to nearest grid level BELOW market
    log.warning(f"Calculated BUY @ {calculated_target} is ABOVE market {current_ltp}")
    log.info("Applying Strict Grid: Finding nearest MAKER level...")
    
    # Find all grid levels below LTP
    # Grid levels below 960: 950, 940, 930, 920...
    # Nearest one: 950
    target = 950
else:
    # NO - Use calculated target
    target = calculated_target
```

**What Happens:**
1. Bot calculates: "Normal grid says 990"
2. Bot checks market: "LTP is 960"
3. Bot decides: **"990 > 960, this would be TAKER order"**
4. Bot searches: "Find nearest grid level below 960"
   - Grid levels: ...930, 940, **950**, 960, 970...
   - Nearest below 960: **950**
5. Bot places: **BUY @ 950** as **MAKER order** ✅
6. Order sits in orderbook, waits for market to dip to 950
7. When filled, bot earns MAKER rebate (-0.02%)
8. Bot now has position at 950, places TP at 960

**Benefits:**
- True "buy the dip" behavior (buying BELOW market)
- Earns MAKER rebate instead of paying TAKER fee
- Saves 0.07% = ₹70 per ₹1,00,000
- Better entry price (950 vs 990 = 40 points better!)

---

### After First Fill - Normal Operation Resumes

**After the 950 order fills:**
```python
# Now bot has position at 950
# Next order calculation (NORMAL GRID LOGIC):
positions = [{'entry_price': 950}]
next_buy = min(positions) - step
next_buy = 950 - 10 = 940

# No special check needed now - this is normal grid operation
# Place BUY @ 940 (one step below last position)
```

**Normal grid behavior continues:**
- Buy at 940 fills → Place buy at 930
- Buy at 930 fills → Place buy at 920
- Position at 950 hits TP at 960 → Close position
- And so on...

**Strict Grid Part 2 ONLY applies at:**
1. ✅ **Initial bot startup** (no positions)
2. ✅ **Bot restart after crash** (positions exist, but checking first order)
3. ❌ **NOT during normal fills** (grid ladder logic takes over)

---

### Visual Comparison

```
Grid Levels:  ...920  930  940  950  960  970  980  990  1000  1010...
                                          ↑
                                        LTP = 960

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WITHOUT Strict Grid:
Reference = 1000
Calculate: 1000 - 10 = 990
Place BUY @ 990 ❌ (ABOVE market, fills as TAKER)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

WITH Strict Grid:
Reference = 1000
Calculate: 1000 - 10 = 990
Check: 990 > 960? YES
Skip to: Nearest grid below 960 = 950
Place BUY @ 950 ✅ (BELOW market, MAKER order)
```

---

## Why This Matters (One-Time Startup Optimization)

### 1. **Fee Optimization on First Order**
- MAKER orders: **EARN** trading fee rebates (Delta: -0.02%)
- TAKER orders: **PAY** trading fees (Delta: 0.05%)
- Difference: **0.07% per trade** = ₹70 per ₹1,00,000 trade
- On first order alone: **Saves/earns ₹140** (0.07% × 2 = saves TAKER fee + earns MAKER rebate)

### 2. **Better Entry Price on Startup**
- Example: 950 vs 990 = **40 points better entry** (4% price improvement!)
- On ₹1,00,000 position: **₹4,000 better entry**
- Plus TP is closer (960 vs 1000), faster profit realization

### 3. **True Grid Discipline from Day One**
- Grid trading philosophy = buy dips, sell rips
- Buying above market (990 when LTP 960) = buying a rally = NOT grid strategy
- **Strict Grid ensures**: First order follows grid philosophy (buy below market)

---

## Current Bot Behavior (NOV 6, 2025)

### What's Implemented
✅ Part 1: Grid alignment validation
✅ Grid calculation: `compute_next_buy_level()`
✅ Order rejection for misaligned prices

### What's Missing
❌ Part 2: Market-aware grid level selection
❌ LTP comparison before placing orders
❌ Skipping non-MAKER grid levels

### Today's Incident
```
LTP: $103,011
Calculated BUY: $108,700 (ref $109k - step $300)
Result: REJECTED (not grid-aligned)
```

**Two problems here:**
1. Reference $109,000 not grid-aligned (should be $108,900 or $109,200)
2. Even if aligned at $108,900, this would be TAKER order (above market)

---

## Implementation Plan

### Fix 1: Validate and Correct Reference Price

**File**: `grid_config.env`
**Current**: `GRIDBOT_REF=109000`
**Should be**: `GRIDBOT_REF=109200` (or $108,900)

**Calculation**:
```python
lower = 90000
step = 300
ref = 109000

# Find nearest grid-aligned reference
offset = (ref - lower) % step  # 109000 - 90000 = 19000 % 300 = 100
if offset != 0:
    # Round to nearest grid level
    aligned_ref = lower + round((ref - lower) / step) * step
    # 90000 + round(19000/300) * 300
    # 90000 + round(63.33) * 300
    # 90000 + 63 * 300 = 108900
    # OR
    # 90000 + 64 * 300 = 109200
```

**Options**:
- `GRIDBOT_REF=108900` (conservative, lower reference)
- `GRIDBOT_REF=109200` (aggressive, higher reference)

---

### Fix 2: Implement Startup-Only Market-Aware Grid Selection

**New Function**: `get_startup_maker_buy_level()` 

**Location**: `bot/strategy/modules/grid_calculator.py`

**Purpose**: ONE-TIME USE at bot startup to find nearest MAKER buy level

**Complete Implementation**:
```python
def get_startup_maker_buy_level(
    self,
    current_price: float,
    open_positions: List[Dict]
) -> Optional[float]:
    """
    Get initial BUY level for bot startup that ensures MAKER order placement.
    
    This function is ONLY used at bot startup (no positions or first order).
    After the first fill, normal grid logic (compute_next_buy_level) takes over.
    
    Logic:
    1. Calculate normal next buy level from grid logic
    2. If that level is ABOVE current market price (would be TAKER):
       - Skip to nearest grid level BELOW market
       - Ensures first order is a MAKER order
    3. If that level is already BELOW market:
       - Use it as-is (already a MAKER order)
    
    Example:
        Grid: 800-1500, Step: 10, Ref: 1000
        LTP: 960, No positions
        
        Normal calculation: 1000 - 10 = 990 (ABOVE market 960)
        Strict Grid: Find nearest below 960 = 950 ✅
    
    Args:
        current_price: Current market price (LTP)
        open_positions: Existing positions (usually empty at startup)
        
    Returns:
        Price below current market (MAKER order), or None if out of bounds
    """
    # Step 1: Calculate what normal grid logic says
    calculated_target = self.compute_next_buy_level(open_positions)
    
    if calculated_target is None:
        log.warning("⚠️ Grid calculation returned None (out of bounds)")
        return None
    
    # Step 2: Check if calculated target would be MAKER or TAKER
    if calculated_target >= current_price:
        # Would be TAKER order (fills immediately)
        log.warning("=" * 80)
        log.warning(f"🔍 STRICT GRID STARTUP CHECK")
        log.warning(f"   Calculated BUY: ${calculated_target:,.2f}")
        log.warning(f"   Current Market: ${current_price:,.2f}")
        log.warning(f"   ⚠️  Calculated price is ABOVE market (would be TAKER order)")
        log.warning(f"   🎯 Finding nearest grid level BELOW market for MAKER order...")
        log.warning("=" * 80)
        
        # Find highest grid level BELOW current price
        maker_target = self.find_nearest_grid_below(current_price)
        
        if maker_target:
            log.info(f"✅ Strict Grid: Placing BUY @ ${maker_target:,.2f} (MAKER order)")
            log.info(f"   Skipped: ${calculated_target:,.2f} (would have been TAKER)")
            log.info(f"   Benefit: {calculated_target - maker_target:,.2f} points better entry + MAKER rebate")
        else:
            log.error(f"❌ No valid grid level below market ${current_price:,.2f}")
            log.error(f"   Grid lower bound: ${self.lower:,.2f}")
        
        return maker_target
    else:
        # Already below market - use as-is
        log.info(f"✅ Calculated BUY ${calculated_target:,.2f} is below market ${current_price:,.2f}")
        log.info(f"   Placing as MAKER order (no adjustment needed)")
        return calculated_target


def find_nearest_grid_below(self, price: float) -> Optional[float]:
    """
    Find nearest grid level strictly below given price.
    
    Used by Strict Grid to find MAKER order levels.
    
    Example:
        Grid: 800, 810, 820, 830...950, 960, 970...
        Price: 960
        Returns: 950 (nearest level below 960)
    
    Args:
        price: Reference price (usually current market price)
        
    Returns:
        Nearest grid level below price, or None if out of bounds
    """
    # Start from lower boundary and work up
    grid_level = self.lower
    last_valid = None
    
    # Find all levels below price
    while grid_level < price:
        if self.is_within_bounds(grid_level):
            last_valid = grid_level
        grid_level += self.step
        
        # Safety: prevent infinite loop
        if grid_level > self.upper:
            break
    
    return last_valid
```

---

### Fix 3: Update Order Manager to Use New Function

**File**: `bot/strategy/modules/order_manager.py`

**Current Call** (Line 236):
```python
def place_buy_order(self, price: float, ...):
    if not self._is_price_grid_aligned(price):
        log.error("REJECTED: Not grid-aligned")
        return None
```

**Should Also Check**:
```python
def place_buy_order(self, price: float, ...):
    # Check 1: Grid alignment
    if not self._is_price_grid_aligned(price):
        log.error("REJECTED: Not grid-aligned")
        return None
    
    # Check 2: MAKER order validation (NEW)
    if self.current_price and price >= self.current_price:
        log.error(f"REJECTED: BUY ${price:,.0f} above market ${self.current_price:,.0f}")
        log.error(f"   This would be a TAKER order (not grid trading)")
        return None
```

---

### Fix 4: Update GridBot Startup Logic (ONE-TIME USE)

**File**: `bot/strategy/gridbot.py` (Line 1041)

**Current**:
```python
positions = self.position_mgr.get_positions()
target = self.grid_calc.compute_next_buy_level(positions)

if target:
    order_id = self.order_mgr.place_buy_order(target)
```

**Should Be**:
```python
positions = self.position_mgr.get_positions()

# STARTUP ONLY: Use Strict Grid to ensure MAKER order
# After first fill, normal grid logic resumes
log.info("🎯 Calculating initial BUY order (Strict Grid enabled)...")
target = self.grid_calc.get_startup_maker_buy_level(
    current_price=self.current_price,
    open_positions=positions
)

if target:
    log.info(f"📍 Placing initial MAKER BUY @ ${target:,.0f}")
    log.info(f"   Current Market: ${self.current_price:,.0f}")
    log.info(f"   This is a ONE-TIME startup optimization")
    log.info(f"   After fill, normal grid logic will resume")
    
    order_id = self.order_mgr.place_buy_order(target)
    if order_id:
        log.info(f"✅ Initial order placed successfully (MAKER order)")
        log.info(f"   After this fills, bot will use normal compute_next_buy_level()")
else:
    log.warning("⚠️ No valid MAKER BUY level available at startup")
    log.info(f"   Market: ${self.current_price:,.0f}")
    log.info(f"   Grid: ${self.grid_calc.lower:,.0f} - ${self.grid_calc.upper:,.0f}")
    log.info(f"   Bot will wait for market to enter grid range...")
```

**IMPORTANT**: This logic ONLY runs at bot startup. After the first order fills:
- Fill handler triggers: `on_buy_filled()`
- Next order uses: `compute_next_buy_level(positions)` (normal grid logic)
- No more Strict Grid checks - regular grid ladder continues

---

## Testing Plan - Startup Behavior Only

### Test Case 1: Comprehensive Example (From Documentation)
```
Grid: Lower=800, Upper=1500, Step=10, Ref=1000
Market Price: 960
No positions (fresh startup)

Traditional Calculation: 1000 - 10 = 990
Strict Grid Check: 990 >= 960? YES
Action: Find nearest below 960 = 950
Expected: Place BUY @ 950 (MAKER order)

After 950 fills:
  Normal grid logic resumes
  Next BUY = 950 - 10 = 940
  No Strict Grid check (this is normal operation)
```

### Test Case 2: Current Bot Configuration
```
Grid: $90k - $110k, Step $300, Ref $109,200 (after fix)
Market Price: $103,011
No positions (startup)

Traditional Calculation: 109,200 - 300 = 108,900
Strict Grid Check: 108,900 >= 103,011? YES
Action: Find nearest below 103,011
  Grid levels: ...102,600, 102,900, 103,200...
  Nearest below 103,011 = 102,900
Expected: Place BUY @ $102,900 (MAKER order)

After $102,900 fills:
  Normal grid: 102,900 - 300 = 102,600
  Place BUY @ $102,600 (no Strict Grid check)
```

### Test Case 3: Market Below Grid
```
Grid: $90k - $110k, Step $300
Market Price: $89,500
No positions (startup)

Traditional Calculation: 109,000 - 300 = 108,700
Strict Grid Check: 108,700 >= 89,500? YES
Action: Find nearest below 89,500
  find_nearest_grid_below(89,500)
  Lower bound is $90,000
  No grid level below $89,500
Expected: Return None, log warning, bot waits
```

### Test Case 4: Market Above Reference
```
Grid: $90k - $110k, Step $300, Ref $109,200
Market Price: $111,000 (above upper bound)
No positions (startup)

Traditional Calculation: 109,200 - 300 = 108,900
Strict Grid Check: 108,900 >= 111,000? NO
Action: Use calculated target (already below market)
Expected: Place BUY @ $108,900 (MAKER order)
```

### Test Case 5: Calculated Target Already Below Market
```
Grid: $90k - $110k, Step $300, Ref $95,000
Market Price: $103,000
No positions (startup)

Traditional Calculation: 95,000 - 300 = 94,700
Strict Grid Check: 94,700 >= 103,000? NO
Action: Use calculated target (no adjustment needed)
Expected: Place BUY @ $94,700 (MAKER order, no change)
```

### Test Case 6: After First Fill (Normal Operation)
```
Grid: $90k - $110k, Step $300
Market Price: $103,000
Positions: [{entry_price: 102,900}] (first order filled)

Calculation: compute_next_buy_level([102,900])
  = 102,900 - 300 = 102,600
NO STRICT GRID CHECK (not startup anymore)
Expected: Place BUY @ $102,600 directly
```

---

## Success Criteria

1. ✅ All BUY orders placed BELOW current market price
2. ✅ All BUY orders are MAKER orders (earn fee rebates)
3. ✅ No TAKER orders on initial grid placement
4. ✅ Grid alignment validation still active
5. ✅ Bot logs clearly show "MAKER order" and market price comparison

---

## Risk Assessment

### Low Risk
- Adding validation (doesn't change existing behavior if market is below grid)
- Logging improvements for transparency

### Medium Risk
- Skipping grid levels (changes order of fills)
- Need to ensure position tracking still works correctly

### Mitigation
- Test extensively in DEMO mode first
- Add comprehensive logging at each decision point
- Keep existing grid alignment check as safety net

---

## Implementation Order

1. **Phase 1** (CRITICAL - Do First):
   - Fix `GRIDBOT_REF` to grid-aligned value ($108,900 or $109,200)
   - Restart bot to verify it can place initial order
   - Expected: Bot places BUY (might be TAKER if above market - this phase doesn't include Strict Grid yet)

2. **Phase 2** (Implement Startup-Only Strict Grid):
   - Add `find_nearest_grid_below()` to `grid_calculator.py`
   - Add `get_startup_maker_buy_level()` to `grid_calculator.py`
   - Update `gridbot.py` startup logic (Line ~1041) to use new function
   - **DO NOT** modify fill handlers (they stay unchanged)
   - **DO NOT** modify normal grid calculation (compute_next_buy_level)

3. **Phase 3** (Testing - Startup Only):
   - Stop bot: `pm2 stop gridbot-demo`
   - Start bot: `pm2 start gridbot-demo`
   - Watch logs: Should show Strict Grid check and MAKER order placement
   - Wait for first fill
   - Verify: After fill, bot uses normal `compute_next_buy_level()` (no Strict Grid)
   - Verify: Second and subsequent orders don't show Strict Grid logs

4. **Phase 4** (Validation):
   - Restart bot multiple times with different market prices
   - Confirm: First order always MAKER (below market)
   - Confirm: After first fill, normal grid behavior
   - Check: Fee structure in Delta Exchange UI (MAKER rebate on first trade)
   - Document: Startup logs showing Strict Grid in action

---

## Files to Modify

| File | Purpose | Priority |
|------|---------|----------|
| `grid_config.env` | Fix GRIDBOT_REF to grid-aligned value | 🔴 CRITICAL |
| `bot/strategy/modules/grid_calculator.py` | Add market-aware functions | 🟡 HIGH |
| `bot/strategy/modules/order_manager.py` | Add MAKER validation | 🟡 HIGH |
| `bot/strategy/gridbot.py` | Update startup logic ONLY (Line ~1041) | � HIGH |

---

## Expected Benefits (Startup Optimization)

### Financial Impact (Per Bot Restart)
- **Save 0.07% on first trade** (MAKER rebate vs TAKER fee)
- On ₹1,00,000 first position: **₹70 saved**
- Better entry price: Additional **2-4% price improvement** depending on ref vs market gap
  - Example: 950 vs 990 entry = 4% better = **₹4,000 improvement** on ₹1,00,000 position

### Trading Quality at Startup
- True grid discipline from first trade (buy dip, not rally)
- Better entry prices on bot startup
- Faster TP realization (closer TP target)

### Bot Reliability
- No more "first order filled immediately" confusion at startup
- Clearer logs explaining ONE-TIME startup optimization
- After first fill, normal grid logic (unchanged, battle-tested)
- Easy to understand: "startup = special, after that = normal"

---

## Next Steps

## Critical Understanding - What Changes and What Doesn't

### ✅ CHANGES (Startup Only)
- **Bot startup logic** (Line ~1041 in gridbot.py)
- **New functions** in grid_calculator.py:
  - `get_startup_maker_buy_level()` - ONE-TIME use at startup
  - `find_nearest_grid_below()` - Helper for finding MAKER levels
- **First order placement** - Uses Strict Grid check

### ❌ DOES NOT CHANGE (Normal Operation)
- **`compute_next_buy_level()`** - Unchanged, still used after first fill
- **Fill handlers** - No modifications needed
- **Position tracking** - No changes
- **Take-profit logic** - No changes
- **Grid calculator core** - Only additions, no modifications to existing functions
- **All orders after first fill** - Normal grid logic (position - step)

### Flow Diagram

```
Bot Starts (No Positions)
    ↓
Calculate from reference: 1000 - 10 = 990
    ↓
🆕 Strict Grid Check: Is 990 >= 960 (LTP)? YES
    ↓
🆕 Find nearest below 960 = 950
    ↓
Place BUY @ 950 ✅ (MAKER order)
    ↓
[Wait for fill...]
    ↓
950 fills → on_buy_filled()
    ↓
⚡ Normal Grid Logic Resumes (NO MORE STRICT GRID)
    ↓
Calculate: 950 - 10 = 940
    ↓
Place BUY @ 940 (normal, no special check)
    ↓
940 fills → Calculate: 940 - 10 = 930
    ↓
930 fills → Calculate: 930 - 10 = 920
    ↓
[Normal grid trading continues...]
```

---

**User Decision Required:**
1. Choose GRIDBOT_REF: $108,900 (conservative) or $109,200 (aggressive)?
2. Approve implementation plan for **startup-only** Strict Grid?
3. Understand this is **ONE-TIME behavior** at startup, not ongoing?

**Awaiting your confirmation to proceed...**

---

*Document created: November 6, 2025*
*Status: Planning Phase*
*Priority: HIGH - Fix reference first, then implement market-aware logic*
