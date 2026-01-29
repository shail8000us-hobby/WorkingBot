# GridBot Trading Logic - Actual Code Behavior

**Generated:** December 12, 2025  
**Based On:** Real code analysis of `async_gridbot.py`, `fill_processing_saga.py`, `grid_calculator.py`

---

## Configuration Used for Examples

```
Reference Price: $90,000
Grid Step: $500
Grid Levels: ...88,500 | 89,000 | 89,500 | 90,000 | 90,500 | 91,000 | 91,500 | 92,000...
```

---

## Core Logic (From Real Code)

### Grid Calculator (`grid_calculator.py`)

**LONG Mode - Next BUY Level:**
```python
# Lines 78-142 in grid_calculator.py
if open_positions:
    lowest_entry = min(p['entry_price'] for p in open_positions)
    target = lowest_entry - step
else:
    if current_price < ref:
        target = find_nearest_grid_below(current_price)
    else:
        target = ref - step
```

**SHORT Mode - Next SELL Level:**
```python
# Lines 144-208 in grid_calculator.py
if open_positions:
    highest_entry = max(p['entry_price'] for p in open_positions)
    target = highest_entry + step
else:
    if current_price > ref:
        target = find_nearest_grid_above(current_price)
    else:
        target = ref + step
```

**TP Price Calculation:**
```python
# Lines 210-234 in grid_calculator.py
def compute_tp_price(entry_price):      # LONG mode
    return entry_price + step

def compute_tp_price_short(entry_price): # SHORT mode
    return entry_price - step
```

### Fill Processing Sagas (`fill_processing_saga.py`)

**After BUY Fill (LONG entry):**
1. Add position with TP = entry + step
2. Place TP SELL order at TP price
3. Calculate next BUY = fill_price - step
4. Cancel ALL other pending BUY orders (Single Pending Order Rule)
5. Place new BUY order

**After SELL Fill (LONG TP close):**
1. Find position by TP price
2. Remove position from state
3. Calculate next BUY = TP_price - step (NOT entry - step!)
4. Cancel ALL other pending BUY orders
5. Place new BUY order at calculated price

**After SELL Fill (SHORT entry):**
1. Add position with TP = entry - step
2. Place TP BUY order at TP price
3. Calculate next SELL = fill_price + step
4. Cancel ALL other pending SELL orders
5. Place new SELL order

**After BUY Fill (SHORT TP close):**
1. Find position by TP price
2. Remove position from state
3. Calculate next SELL = TP_price + step (NOT entry + step!)
4. Cancel ALL other pending SELL orders
5. Place new SELL order

---

## LONG MODE Scenario

### Market: $90,000 → $88,700 → $90,100

#### Phase 1: Market at $90,000 (Startup)

**Bot Action:**
- Market = Reference ($90,000), no positions
- Initial BUY target = ref - step = $89,500
- Places **BUY @ $89,500**

```
State: Pending BUY @ $89,500
Positions: 0
```

---

#### Phase 2: Market Drops to $89,500

**Event:** BUY @ $89,500 FILLS

**Saga: `create_buy_fill_saga`**
```
Step 1: Add position
  - Entry: $89,500
  - TP: $89,500 + $500 = $90,000

Step 2: Place TP order
  - SELL @ $90,000 (reduce_only=True)

Step 3: Calculate next BUY
  - next_price = fill_price - step
  - next_price = $89,500 - $500 = $89,000
  - Place BUY @ $89,000
```

```
State:
  Position #1: Entry $89,500, TP $90,000
  Pending BUY @ $89,000
  TP Order: SELL @ $90,000
```

---

#### Phase 3: Market Drops to $89,000

**Event:** BUY @ $89,000 FILLS

**Saga: `create_buy_fill_saga`**
```
Step 1: Add position
  - Entry: $89,000
  - TP: $89,000 + $500 = $89,500

Step 2: Place TP order
  - SELL @ $89,500 (reduce_only=True)

Step 3: Calculate next BUY
  - next_price = $89,000 - $500 = $88,500
  - Place BUY @ $88,500
```

```
State:
  Position #1: Entry $89,500, TP $90,000
  Position #2: Entry $89,000, TP $89,500
  Pending BUY @ $88,500
  TP Orders: SELL @ $90,000, SELL @ $89,500
```

---

#### Phase 4: Market at $88,700 (Bottom)

**No fills** - BUY @ $88,500 not reached

```
State (unchanged):
  Position #1: Entry $89,500, TP $90,000
  Position #2: Entry $89,000, TP $89,500
  Pending BUY @ $88,500
  TP Orders: SELL @ $90,000, SELL @ $89,500
```

---

#### Phase 5: Market Rises to $89,500

**Event:** TP SELL @ $89,500 FILLS (closes Position #2)

**Saga: `create_sell_fill_saga`**
```
Step 1: Find position by TP price ($89,500)
  - Found: Position #2 (Entry $89,000)
  - Remove position from state

Step 2: Clear pending sell

Step 3: Calculate next BUY
  - CRITICAL: Uses TP_price, not entry_price!
  - next_price = TP_price - step
  - next_price = $89,500 - $500 = $89,000
  
Step 4: Single Pending Order Rule
  - Cancel old BUY @ $88,500 ✓
  
Step 5: Place new BUY @ $89,000
```

```
State:
  Position #1: Entry $89,500, TP $90,000
  Pending BUY @ $89,000 (moved UP from $88,500)
  TP Order: SELL @ $90,000
```

**Profit: $500** (bought at $89,000, sold at $89,500)

---

#### Phase 6: Market Rises to $90,000

**Event:** TP SELL @ $90,000 FILLS (closes Position #1)

**Saga: `create_sell_fill_saga`**
```
Step 1: Find position by TP price ($90,000)
  - Found: Position #1 (Entry $89,500)
  - Remove position from state

Step 3: Calculate next BUY
  - next_price = $90,000 - $500 = $89,500

Step 4: Single Pending Order Rule
  - Cancel old BUY @ $89,000 ✓

Step 5: Place new BUY @ $89,500
```

```
State:
  Positions: 0 (all closed)
  Pending BUY @ $89,500
```

**Profit: $500** (bought at $89,500, sold at $90,000)

---

#### Phase 7: Market at $90,100 (Final)

**No fills** - BUY @ $89,500 not reached (below market)

```
Final State:
  Positions: 0
  Pending BUY @ $89,500
  
Total Profit: $1,000 (2 round trips × $500)
```

---

## SHORT MODE Scenario

### Market: $90,000 → $91,700 → $89,800

#### Phase 1: Market at $90,000 (Startup)

**Bot Action:**
- Market = Reference ($90,000), no positions
- Initial SELL target = ref + step = $90,500
- Places **SELL @ $90,500**

```
State: Pending SELL @ $90,500
Positions: 0
```

---

#### Phase 2: Market Rises to $90,500

**Event:** SELL @ $90,500 FILLS (opens SHORT position)

**Saga: `create_short_entry_saga`**
```
Step 1: Add position
  - Entry: $90,500
  - TP: $90,500 - $500 = $90,000

Step 2: Place TP order
  - BUY @ $90,000 (reduce_only=True)

Step 3: Calculate next SELL
  - next_price = fill_price + step
  - next_price = $90,500 + $500 = $91,000
  - Place SELL @ $91,000
```

```
State:
  Position #1: Entry $90,500, TP $90,000
  Pending SELL @ $91,000
  TP Order: BUY @ $90,000
```

---

#### Phase 3: Market Rises to $91,000

**Event:** SELL @ $91,000 FILLS

**Saga: `create_short_entry_saga`**
```
Step 1: Add position
  - Entry: $91,000
  - TP: $91,000 - $500 = $90,500

Step 2: Place TP order
  - BUY @ $90,500

Step 3: Calculate next SELL
  - next_price = $91,000 + $500 = $91,500
  - Place SELL @ $91,500
```

```
State:
  Position #1: Entry $90,500, TP $90,000
  Position #2: Entry $91,000, TP $90,500
  Pending SELL @ $91,500
  TP Orders: BUY @ $90,000, BUY @ $90,500
```

---

#### Phase 4: Market Rises to $91,500

**Event:** SELL @ $91,500 FILLS

**Saga: `create_short_entry_saga`**
```
Step 1: Add position
  - Entry: $91,500
  - TP: $91,500 - $500 = $91,000

Step 3: Calculate next SELL
  - next_price = $91,500 + $500 = $92,000
  - Place SELL @ $92,000
```

```
State:
  Position #1: Entry $90,500, TP $90,000
  Position #2: Entry $91,000, TP $90,500
  Position #3: Entry $91,500, TP $91,000
  Pending SELL @ $92,000
  TP Orders: BUY @ $90,000, BUY @ $90,500, BUY @ $91,000
```

---

#### Phase 5: Market at $91,700 (Peak)

**No fills** - SELL @ $92,000 not reached

```
State (unchanged):
  3 SHORT positions open
  Pending SELL @ $92,000
```

---

#### Phase 6: Market Drops to $91,000

**Event:** TP BUY @ $91,000 FILLS (closes Position #3)

**Saga: `create_short_tp_saga`**
```
Step 1: Find position by TP price ($91,000)
  - Found: Position #3 (Entry $91,500)
  - Remove position

Step 3: Calculate next SELL
  - CRITICAL: Uses TP_price, not entry_price!
  - next_price = TP_price + step
  - next_price = $91,000 + $500 = $91,500

Step 4: Single Pending Order Rule
  - Cancel old SELL @ $92,000 ✓

Step 5: Place new SELL @ $91,500
```

```
State:
  Position #1: Entry $90,500, TP $90,000
  Position #2: Entry $91,000, TP $90,500
  Pending SELL @ $91,500 (moved DOWN from $92,000)
  TP Orders: BUY @ $90,000, BUY @ $90,500
```

**Profit: $500** (sold at $91,500, bought back at $91,000)

---

#### Phase 7: Market Drops to $90,500

**Event:** TP BUY @ $90,500 FILLS (closes Position #2)

**Saga: `create_short_tp_saga`**
```
Step 3: Calculate next SELL
  - next_price = $90,500 + $500 = $91,000

Step 4: Cancel old SELL @ $91,500

Step 5: Place new SELL @ $91,000
```

```
State:
  Position #1: Entry $90,500, TP $90,000
  Pending SELL @ $91,000
  TP Order: BUY @ $90,000
```

**Profit: $500** (sold at $91,000, bought back at $90,500)

---

#### Phase 8: Market Drops to $90,000

**Event:** TP BUY @ $90,000 FILLS (closes Position #1)

**Saga: `create_short_tp_saga`**
```
Step 3: Calculate next SELL
  - next_price = $90,000 + $500 = $90,500

Step 4: Cancel old SELL @ $91,000

Step 5: Place new SELL @ $90,500
```

```
State:
  Positions: 0 (all closed)
  Pending SELL @ $90,500
```

**Profit: $500** (sold at $90,500, bought back at $90,000)

---

#### Phase 9: Market at $89,800 (Final)

**No fills** - SELL @ $90,500 not reached (above market)

```
Final State:
  Positions: 0
  Pending SELL @ $90,500
  
Total Profit: $1,500 (3 round trips × $500)
```

---

## Critical Rules (From Code)

### 1. Single Pending Order Rule
```python
# fill_processing_saga.py lines 322-404, 691-771, 1146-1228, 1507-1589
# Bot maintains EXACTLY ONE pending entry order at any time
# When TP fills, old pending order is CANCELLED before placing new one
```

### 2. Next Order After TP Fill
```python
# fill_processing_saga.py line 635 (LONG) and 1459 (SHORT)
# CRITICAL: Uses TP price, NOT entry price
# LONG:  next_buy = tp_price - step (moves ORDER UP toward market)
# SHORT: next_sell = tp_price + step (moves ORDER DOWN toward market)
```

### 3. Bot Order Identification (Fixed Dec 12, 2025)
```python
# async_gridbot.py lines 1775-1785
# Entry orders: client_order_id starts with "GBOT_" or "BOT-"
# TP orders: reduce_only=True (no client_order_id needed)
is_bot_order = is_entry_order or is_tp_order
```

### 4. Guardian Integration
```python
# Before placing ANY order, bot checks Guardian signal
# Guardian STOP = No order placement (order is queued for retry)
# Guardian GO = Normal operation
```

---

## Summary Table

| Scenario | Entry Direction | TP Direction | Next Order After TP | Order Movement |
|----------|-----------------|--------------|---------------------|----------------|
| LONG | BUY (down) | SELL (up) | BUY at TP - step | Order moves UP |
| SHORT | SELL (up) | BUY (down) | SELL at TP + step | Order moves DOWN |

---

**File Location:** `/Users/ssr/Projects/WorkingBot/logic_strategy.md`  
**Last Updated:** January 29, 2026

---

## 🔄 OPPORTUNISTIC RECOVERY SYSTEM (Jan 29, 2026)

### Overview

Recovery system handles missed grid levels when:
1. **Startup Recovery:** Bot starts and market has moved past grid levels
2. **Guardian Recovery:** Guardian resumes (STOP → GO) and market moved during halt

### Critical Rule: Grid-Aligned TP Orders

**Recovery ALWAYS places TP at grid level**, NOT at fill price + step.

### LONG Mode Recovery Example

**Scenario:**
- Halt Price: $100 (reference point)
- Current Price: $81 (market dropped)
- Grid Step: $5
- Mode: LONG

**Missed Grids Calculation:**
```
Starting from $100, going down to $81:
- $95 (100 - 5)
- $90 (95 - 5)
- $85 (90 - 5)
Missed grids: [95, 90, 85]
```

**Recovery Orders Placed:**
```
Grid $95: Market BUY at $81 → TP SELL at $100 (95 + 5)
Grid $90: Market BUY at $81 → TP SELL at $95  (90 + 5)
Grid $85: Market BUY at $81 → TP SELL at $90  (85 + 5)
```

**Why This Works:**
- Entry fills at ~$81 (current market)
- But TP is placed at grid level (grid_price + step)
- This maintains grid structure
- When market rises, TPs hit in sequence: $85→$90, $90→$95, $95→$100

### SHORT Mode Recovery Example

**Scenario:**
- Halt Price: $100 (reference point)
- Current Price: $119 (market rose)
- Grid Step: $5
- Mode: SHORT

**Missed Grids Calculation:**
```
Starting from $100, going up to $119:
- $105 (100 + 5)
- $110 (105 + 5)
- $115 (110 + 5)
Missed grids: [105, 110, 115]
```

**Recovery Orders Placed:**
```
Grid $105: Market SELL at $119 → TP BUY at $100 (105 - 5)
Grid $110: Market SELL at $119 → TP BUY at $105 (110 - 5)
Grid $115: Market SELL at $119 → TP BUY at $110 (115 - 5)
```

**Why This Works:**
- Entry fills at ~$119 (current market)
- But TP is placed at grid level (grid_price - step)
- When market drops, TPs hit in sequence: $115→$110, $110→$105, $105→$100

### Safety Mechanisms

1. **Position Check:** Skips grid if position already exists
2. **Order Check:** Skips grid if pending order exists at grid level
3. **Max Grids:**
   - Startup Recovery: 3 grids (configurable)
   - Guardian Recovery: 5 grids (configurable)
4. **Circuit Breaker:** Opens after 3 failures, auto-recovers after 60s
5. **Rate Limiter:** 0.5 orders/sec (prevents API abuse)
6. **Single Execution:** Startup recovery runs ONCE per session
7. **Grid Snapping:** Halt price snapped to valid grid level

### Integration with Normal Trading

**Recovery runs ONLY:**
- During startup (before normal trading)
- During Guardian resume (trading halted)

**Protection:**
- `recovery_in_progress` flag set during recovery
- `_check_and_place_entry_order()` checks this flag
- Normal order placement BLOCKED during recovery
- Fill processing sagas still work (handle recovery fills)
- Single Pending Order Rule preserved

**After Recovery:**
- `recovery_in_progress` flag cleared
- Normal trading resumes
- Bot follows standard grid logic per #file:logic_strategy.md

### Code Locations

```
bot/strategy/recovery/
├── base_recovery_engine.py    # Safety mechanisms
├── startup_recovery.py         # Startup recovery logic
├── guardian_recovery.py        # Guardian resume recovery
└── recovery_monitor.py         # Health monitoring

bot/strategy/async_gridbot.py
├── place_recovery_order()      # Line 5134 - Places market + TP orders
├── get_current_price()          # Line 2829 - Price fetching for engines
└── get_open_orders()            # Line 5219 - Order checking

bot/strategy/simple_state_coordinator.py
├── _check_and_run_recovery()   # Line 155 - Startup recovery
└── _run_guardian_recovery()    # Line 100 - Guardian recovery
```

---

**File Location:** `/Users/ssr/Projects/WorkingBot/logic_strategy.md`  
**Last Updated:** January 29, 2026

