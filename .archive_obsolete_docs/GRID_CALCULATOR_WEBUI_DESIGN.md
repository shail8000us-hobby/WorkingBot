# 📐 Grid Calculator WebUI Design Specification

**Date**: November 9, 2025  
**Status**: 🎨 DESIGN PHASE (Not yet coded)  
**Purpose**: Design WebUI panels for grid configuration and real-time calculation preview

---

## 🎯 Overview

This design adds **4 new panels** to the WebUI dashboard:

1. **Grid Configuration Panel** - Edit grid parameters (linked to `grid_config.env`)
2. **LONG Mode Preview** - Show calculations for bullish grid
3. **SHORT Mode Preview** - Show calculations for bearish grid
4. **Grid Visualization** - Visual representation of grid levels

All calculations are powered by `bot/strategy/modules/grid_calculator.py`

---

## 📊 Panel 1: Grid Configuration Panel

### Location
**Dashboard Section**: "Configuration" tab  
**Position**: Top of configuration section (above existing config cards)  
**Title**: "🎯 Grid Geometry & Direction"

### Layout (Card-based Design)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 🎯 Grid Geometry & Direction                            [9 settings] ⓘ │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Trading Direction                                                      │
│  ┌──────────────────────────────────────────────────────────────┐     │
│  │  [  LONG  ]  [ SHORT ]        Current: LONG                  │     │
│  │  🟢 Bullish   🔴 Bearish                                      │     │
│  └──────────────────────────────────────────────────────────────┘     │
│                                                                         │
│  Grid Boundaries                                                        │
│  ┌────────────────────────┬────────────────────────┬──────────────────┐│
│  │ Lower Bound            │ Reference Price        │ Upper Bound      ││
│  │ [  99000  ] USD       │ [ 103800  ] USD       │ [ 110000 ] USD  ││
│  │ Grid bottom            │ Starting point         │ Grid top         ││
│  └────────────────────────┴────────────────────────┴──────────────────┘│
│                                                                         │
│  Grid Spacing                                                           │
│  ┌────────────────────────┬────────────────────────┬──────────────────┐│
│  │ Step Size              │ Symbol                 │ Tick Size        ││
│  │ [  500  ] USD         │ [ BTCUSD ]            │ [ 0.5 ] USD     ││
│  │ Price between levels   │ Trading pair           │ Min price incr.  ││
│  └────────────────────────┴────────────────────────┴──────────────────┘│
│                                                                         │
│  Position Management                                                    │
│  ┌────────────────────────┬────────────────────────┬──────────────────┐│
│  │ Lot Size               │ Max Open Positions     │ Heartbeat        ││
│  │ [  1  ] units         │ [  5  ] positions     │ [ 20 ] seconds  ││
│  │ Contracts per order    │ Max concurrent         │ Update frequency ││
│  └────────────────────────┴────────────────────────┴──────────────────┘│
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  📊 Grid Span: $11,000 (99,000 → 110,000)                       │ │
│  │  📏 Grid Levels: 23 levels (11,000 / 500 + 1)                   │ │
│  │  💰 Max Capital: ~$5,000 (5 positions × 1 lot × ~$100,000)      │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  [ Cancel ]  [ Preview Calculations ]  [ Save & Apply ]                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Input Fields (Mapped to grid_config.env)

| Field | Config Key | Type | Validation | Default |
|-------|-----------|------|------------|---------|
| Trading Direction | `GRIDBOT_GRID_MODE` | Toggle | LONG or SHORT | LONG |
| Lower Bound | `GRIDBOT_LOWER` | Number | > 0, < Upper | 99000 |
| Reference Price | `GRIDBOT_REF` | Number | Lower ≤ Ref ≤ Upper | 103800 |
| Upper Bound | `GRIDBOT_UPPER` | Number | > Lower | 110000 |
| Step Size | `GRIDBOT_STEP` | Number | > 0, < (Upper-Lower) | 500 |
| Symbol | `GRIDBOT_SYMBOL` | Text | Valid ticker | BTCUSD |
| Tick Size | `tick_size` (hardcoded) | Number | > 0 | 0.5 |
| Lot Size | `GRIDBOT_LOT` | Number | > 0 | 1 |
| Max Open Positions | `GRIDBOT_MAX_OPEN` | Number | 1-20 | 5 |
| Heartbeat | `GRIDBOT_HB_SEC` | Number | 5-60 seconds | 20 |

### Real-time Calculations

As user types, show live updates:
- **Grid Span**: `Upper - Lower` (e.g., "$11,000")
- **Grid Levels**: `Math.floor((Upper - Lower) / Step) + 1` (e.g., "23 levels")
- **Max Capital Estimate**: `Max Open × Lot Size × Ref Price` (rough estimate)

### Validation Rules (From GridCalculator)

```javascript
// Client-side validation (mirroring grid_calculator.py lines 56-77)
if (step <= 0) {
  error = "Step must be positive";
}
if (lower >= upper) {
  error = "Lower bound must be less than upper bound";
}
if (!(lower <= ref && ref <= upper)) {
  error = "Reference must be within grid bounds";
}
if (tickSize <= 0) {
  error = "Tick size must be positive";
}
```

### Actions

1. **Cancel**: Discard changes, reload from backend
2. **Preview Calculations**: Open modal showing LONG/SHORT preview panels
3. **Save & Apply**: 
   - Validate all inputs
   - POST to `/api/config/update` with changes
   - Update `grid_config.env`
   - Show success notification
   - Refresh calculation panels

---

## 📊 Panel 2: LONG Mode Calculation Preview

### Location
**Dashboard Section**: "Configuration" tab  
**Position**: Below Grid Configuration Panel  
**Visibility**: Always visible, but grayed out if `GRIDBOT_GRID_MODE=SHORT`

### Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 📈 LONG Mode Grid Calculations                          [Real-time] ⓘ  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Grid Settings                                                          │
│  Lower: $99,000  |  Ref: $103,800  |  Upper: $110,000  |  Step: $500   │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ 1️⃣ BUY Order Sequence                                             │ │
│  │                                                                    │ │
│  │ Shows: Where BUY orders will be placed as price falls            │ │
│  │ Logic: compute_next_buy_level() from grid_calculator.py          │ │
│  │                                                                    │ │
│  │ Current Market Price: $103,000                                    │ │
│  │                                                                    │ │
│  │ 📍 No Positions Scenario:                                         │ │
│  │   Next BUY: $103,800 - $500 = $103,300 (at REF - STEP)          │ │
│  │   Reason: Starting from reference level                          │ │
│  │                                                                    │ │
│  │ 📍 With 1 Position @ $103,300:                                    │ │
│  │   Next BUY: $103,300 - $500 = $102,800 (one step below)         │ │
│  │   Reason: Buy below lowest open position                         │ │
│  │                                                                    │ │
│  │ 📍 With 2 Positions @ [$103,300, $102,800]:                      │ │
│  │   Next BUY: $102,800 - $500 = $102,300                           │ │
│  │                                                                    │ │
│  │ 📍 Full Sequence (5 max positions):                               │ │
│  │   BUY #1: $103,300  →  BUY #2: $102,800  →  BUY #3: $102,300    │ │
│  │   BUY #4: $101,800  →  BUY #5: $101,300                          │ │
│  │                                                                    │ │
│  │ ⚠️ Lower Bound Check:                                             │ │
│  │   $101,300 > $99,000 ✅ (within grid bounds)                     │ │
│  │   If price reaches $99,000, no more BUY orders                   │ │
│  └────────────────────────────────────────────────────────────────── │ │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ 2️⃣ Target Price (TP) Sequence                                     │ │
│  │                                                                    │ │
│  │ Shows: SELL prices (take profit) for each BUY entry              │ │
│  │ Logic: compute_tp_price() from grid_calculator.py                │ │
│  │                                                                    │ │
│  │ Formula: TP = Entry Price + Step                                 │ │
│  │                                                                    │ │
│  │ Position #1: Entry $103,300  →  TP: $103,800  (profit: $500)    │ │
│  │ Position #2: Entry $102,800  →  TP: $103,300  (profit: $500)    │ │
│  │ Position #3: Entry $102,300  →  TP: $102,800  (profit: $500)    │ │
│  │ Position #4: Entry $101,800  →  TP: $102,300  (profit: $500)    │ │
│  │ Position #5: Entry $101,300  →  TP: $101,800  (profit: $500)    │ │
│  │                                                                    │ │
│  │ 💰 Total Potential Profit: $2,500 ($500 × 5 positions)           │ │
│  │                                                                    │ │
│  │ ⚠️ Upper Bound Check:                                             │ │
│  │   Highest TP: $103,800 ≤ $110,000 ✅ (within grid bounds)       │ │
│  └────────────────────────────────────────────────────────────────── │ │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ 3️⃣ Next BUY After TP Fill                                         │ │
│  │                                                                    │ │
│  │ Shows: What happens after a TP SELL executes                     │ │
│  │ Logic: compute_next_buy_level() after position closes            │ │
│  │                                                                    │ │
│  │ Scenario: Position #1 TP filled @ $103,800                       │ │
│  │   Current Positions: [$102,800, $102,300, $101,800, $101,300]   │ │
│  │   Lowest Entry: $101,300                                         │ │
│  │   Next BUY: $101,300 - $500 = $100,800                           │ │
│  │                                                                    │ │
│  │ Scenario: All TPs filled (no positions)                          │ │
│  │   Market Price: $103,000                                         │ │
│  │   Next BUY: Use Strict Grid logic                                │ │
│  │     → find_nearest_grid_below($103,000)                          │ │
│  │     → $102,500 (nearest grid level below market)                 │ │
│  │     → Ensures MAKER order (no immediate fill)                    │ │
│  │                                                                    │ │
│  │ 🎯 Grid Cycle:                                                    │ │
│  │   BUY @ $102,500 → Wait for fill → TP @ $103,000                │ │
│  │   → Next BUY @ $102,000 → Repeat                                 │ │
│  └────────────────────────────────────────────────────────────────── │ │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ 🔍 Grid Level Visualization                                       │ │
│  │                                                                    │ │
│  │  $110,000 ─────────────────────── ← UPPER BOUND                  │ │
│  │  $109,500 ─────────────────────── ○ Grid Level 23               │ │
│  │  $109,000 ─────────────────────── ○ Grid Level 22               │ │
│  │     ...                                                           │ │
│  │  $103,800 ─────────────────────── ★ REFERENCE (Starting point)  │ │
│  │  $103,300 ─────────────────────── ● Next BUY (no positions)     │ │
│  │  $103,000 ─────────────────────── 📍 MARKET PRICE               │ │
│  │  $102,800 ─────────────────────── ○ Grid Level 15               │ │
│  │  $102,300 ─────────────────────── ○ Grid Level 14               │ │
│  │     ...                                                           │ │
│  │  $99,500  ─────────────────────── ○ Grid Level 2                │ │
│  │  $99,000  ─────────────────────── ← LOWER BOUND                 │ │
│  │                                                                    │ │
│  │  Legend:                                                          │ │
│  │  ○ Available grid levels   ● Active orders   ★ Reference         │ │
│  │  📍 Current market price   ■ Filled positions                    │ │
│  └────────────────────────────────────────────────────────────────── │ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Source (API Endpoint)

**New Backend Endpoint**: `GET /api/grid/calculations?mode=LONG`

**Request Parameters**:
```json
{
  "mode": "LONG",
  "lower": 99000,
  "upper": 110000,
  "step": 500,
  "ref": 103800,
  "tick_size": 0.5,
  "current_price": 103000,  // Optional, from LTP
  "open_positions": [        // Optional, from runtime state
    {"entry_price": 103300, "qty": 1},
    {"entry_price": 102800, "qty": 1}
  ]
}
```

**Response**:
```json
{
  "success": true,
  "mode": "LONG",
  "grid_config": {
    "lower": 99000,
    "upper": 110000,
    "step": 500,
    "ref": 103800,
    "tick_size": 0.5,
    "total_levels": 23
  },
  "buy_sequence": [
    {
      "order_num": 1,
      "price": 103300,
      "reason": "REF - STEP (starting from reference)",
      "within_bounds": true
    },
    {
      "order_num": 2,
      "price": 102800,
      "reason": "One step below previous",
      "within_bounds": true
    }
    // ... up to max_open positions
  ],
  "tp_sequence": [
    {
      "position_num": 1,
      "entry": 103300,
      "tp": 103800,
      "profit": 500,
      "within_bounds": true
    }
    // ... for each buy order
  ],
  "next_buy_after_tp": {
    "scenario": "TP filled at $103,800",
    "remaining_positions": 4,
    "lowest_entry": 101300,
    "next_buy": 100800,
    "reason": "One step below lowest remaining position"
  },
  "grid_levels": [
    {"price": 99000, "type": "lower_bound"},
    {"price": 99500, "type": "grid_level"},
    // ... all grid levels
    {"price": 103800, "type": "reference"},
    // ...
    {"price": 110000, "type": "upper_bound"}
  ],
  "validation": {
    "all_buys_within_bounds": true,
    "all_tps_within_bounds": true,
    "max_capital_required": 515000  // 5 positions × 1 lot × ~103000
  }
}
```

### Backend Implementation (Pseudo-code)

```python
# File: webui/backend/routes/grid_calculations.py

from bot.strategy.modules.grid_calculator import GridCalculator

@app.route('/api/grid/calculations', methods=['GET'])
def get_grid_calculations():
    """Calculate grid sequences using GridCalculator"""
    
    # Get parameters from query string or config
    mode = request.args.get('mode', 'LONG')
    lower = float(request.args.get('lower', 99000))
    upper = float(request.args.get('upper', 110000))
    step = float(request.args.get('step', 500))
    ref = float(request.args.get('ref', 103800))
    tick_size = float(request.args.get('tick_size', 0.5))
    max_open = int(request.args.get('max_open', 5))
    current_price = float(request.args.get('current_price', ref))
    
    # Initialize GridCalculator
    calc = GridCalculator(
        lower=lower,
        upper=upper,
        step=step,
        ref=ref,
        tick_size=tick_size
    )
    
    # Calculate BUY sequence (simulate max_open positions)
    buy_sequence = []
    open_positions = []
    
    for i in range(max_open):
        if mode == 'LONG':
            next_buy = calc.compute_next_buy_level(
                open_positions=open_positions,
                current_price=current_price
            )
        else:
            next_buy = calc.compute_next_sell_level(
                open_positions=open_positions,
                current_price=current_price
            )
        
        if next_buy is None:
            break
        
        buy_sequence.append({
            'order_num': i + 1,
            'price': next_buy,
            'reason': _get_reason(i, open_positions, ref, step),
            'within_bounds': calc.is_within_bounds(next_buy)
        })
        
        # Simulate position opening
        open_positions.append({'entry_price': next_buy, 'qty': 1})
    
    # Calculate TP sequence
    tp_sequence = []
    for i, pos in enumerate(open_positions):
        if mode == 'LONG':
            tp = calc.compute_tp_price(pos['entry_price'])
        else:
            tp = calc.compute_tp_price_short(pos['entry_price'])
        
        tp_sequence.append({
            'position_num': i + 1,
            'entry': pos['entry_price'],
            'tp': tp,
            'profit': abs(tp - pos['entry_price']),
            'within_bounds': calc.is_within_bounds(tp)
        })
    
    # Calculate next BUY after first TP fills
    remaining_positions = open_positions[1:]  # Remove first position
    if mode == 'LONG':
        next_buy_after_tp = calc.compute_next_buy_level(
            open_positions=remaining_positions,
            current_price=current_price
        )
    else:
        next_buy_after_tp = calc.compute_next_sell_level(
            open_positions=remaining_positions,
            current_price=current_price
        )
    
    # Get all grid levels
    grid_levels = calc.get_grid_levels()
    
    return jsonify({
        'success': True,
        'mode': mode,
        'grid_config': {
            'lower': lower,
            'upper': upper,
            'step': step,
            'ref': ref,
            'tick_size': tick_size,
            'total_levels': len(grid_levels)
        },
        'buy_sequence': buy_sequence,
        'tp_sequence': tp_sequence,
        'next_buy_after_tp': {
            'price': next_buy_after_tp,
            'remaining_positions': len(remaining_positions)
        },
        'grid_levels': [{'price': p, 'type': _classify_level(p, lower, upper, ref)} 
                        for p in grid_levels],
        'validation': {
            'all_buys_within_bounds': all(b['within_bounds'] for b in buy_sequence),
            'all_tps_within_bounds': all(t['within_bounds'] for t in tp_sequence)
        }
    })
```

---

## 📊 Panel 3: SHORT Mode Calculation Preview

### Location
**Dashboard Section**: "Configuration" tab  
**Position**: Below LONG Mode Panel  
**Visibility**: Always visible, but grayed out if `GRIDBOT_GRID_MODE=LONG`

### Layout (Mirror of LONG Mode)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 📉 SHORT Mode Grid Calculations                         [Real-time] ⓘ  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Grid Settings                                                          │
│  Lower: $99,000  |  Ref: $103,800  |  Upper: $110,000  |  Step: $500   │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ 1️⃣ SELL Order Sequence                                            │ │
│  │                                                                    │ │
│  │ Shows: Where SELL orders will be placed as price rises           │ │
│  │ Logic: compute_next_sell_level() from grid_calculator.py         │ │
│  │                                                                    │ │
│  │ Current Market Price: $104,000                                    │ │
│  │                                                                    │ │
│  │ 📍 No Positions Scenario:                                         │ │
│  │   Next SELL: $103,800 + $500 = $104,300 (at REF + STEP)         │ │
│  │   Reason: Starting from reference level                          │ │
│  │                                                                    │ │
│  │ 📍 With 1 Position @ $104,300:                                    │ │
│  │   Next SELL: $104,300 + $500 = $104,800 (one step above)        │ │
│  │   Reason: Sell above highest open position                       │ │
│  │                                                                    │ │
│  │ 📍 With 2 Positions @ [$104,300, $104,800]:                      │ │
│  │   Next SELL: $104,800 + $500 = $105,300                          │ │
│  │                                                                    │ │
│  │ 📍 Full Sequence (5 max positions):                               │ │
│  │   SELL #1: $104,300  →  SELL #2: $104,800  →  SELL #3: $105,300 │ │
│  │   SELL #4: $105,800  →  SELL #5: $106,300                        │ │
│  │                                                                    │ │
│  │ ⚠️ Upper Bound Check:                                             │ │
│  │   $106,300 < $110,000 ✅ (within grid bounds)                    │ │
│  │   If price reaches $110,000, no more SELL orders                 │ │
│  └────────────────────────────────────────────────────────────────── │ │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ 2️⃣ Target Price (TP) Sequence                                     │ │
│  │                                                                    │ │
│  │ Shows: BUY prices (take profit) for each SELL entry              │ │
│  │ Logic: compute_tp_price_short() from grid_calculator.py          │ │
│  │                                                                    │ │
│  │ Formula: TP = Entry Price - Step (buy back lower)                │ │
│  │                                                                    │ │
│  │ Position #1: Entry $104,300  →  TP: $103,800  (profit: $500)    │ │
│  │ Position #2: Entry $104,800  →  TP: $104,300  (profit: $500)    │ │
│  │ Position #3: Entry $105,300  →  TP: $104,800  (profit: $500)    │ │
│  │ Position #4: Entry $105,800  →  TP: $105,300  (profit: $500)    │ │
│  │ Position #5: Entry $106,300  →  TP: $105,800  (profit: $500)    │ │
│  │                                                                    │ │
│  │ 💰 Total Potential Profit: $2,500 ($500 × 5 positions)           │ │
│  │                                                                    │ │
│  │ ⚠️ Lower Bound Check:                                             │ │
│  │   Lowest TP: $103,800 ≥ $99,000 ✅ (within grid bounds)         │ │
│  └────────────────────────────────────────────────────────────────── │ │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ 3️⃣ Next SELL After TP Fill                                        │ │
│  │                                                                    │ │
│  │ Shows: What happens after a TP BUY executes                      │ │
│  │ Logic: compute_next_sell_level() after position closes           │ │
│  │                                                                    │ │
│  │ Scenario: Position #1 TP filled @ $103,800                       │ │
│  │   Current Positions: [$104,800, $105,300, $105,800, $106,300]   │ │
│  │   Highest Entry: $106,300                                        │ │
│  │   Next SELL: $106,300 + $500 = $106,800                          │ │
│  │                                                                    │ │
│  │ Scenario: All TPs filled (no positions)                          │ │
│  │   Market Price: $104,000                                         │ │
│  │   Next SELL: Use Strict Grid logic                               │ │
│  │     → find_nearest_grid_above($104,000)                          │ │
│  │     → $104,500 (nearest grid level above market)                 │ │
│  │     → Ensures MAKER order (no immediate fill)                    │ │
│  │                                                                    │ │
│  │ 🎯 Grid Cycle:                                                    │ │
│  │   SELL @ $104,500 → Wait for fill → TP @ $104,000               │ │
│  │   → Next SELL @ $105,000 → Repeat                                │ │
│  └────────────────────────────────────────────────────────────────── │ │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ 🔍 Grid Level Visualization (Same as LONG, but inverted logic)   │ │
│  │                                                                    │ │
│  │  $110,000 ─────────────────────── ← UPPER BOUND                  │ │
│  │  $109,500 ─────────────────────── ○ Grid Level 23               │ │
│  │     ...                                                           │ │
│  │  $106,300 ─────────────────────── ● Next SELL (5 positions)     │ │
│  │  $105,800 ─────────────────────── ○ Grid Level                  │ │
│  │  $104,300 ─────────────────────── ● Next SELL (no positions)    │ │
│  │  $104,000 ─────────────────────── 📍 MARKET PRICE               │ │
│  │  $103,800 ─────────────────────── ★ REFERENCE (Starting point)  │ │
│  │     ...                                                           │ │
│  │  $99,000  ─────────────────────── ← LOWER BOUND                 │ │
│  └────────────────────────────────────────────────────────────────── │ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Differences from LONG Mode

| Aspect | LONG Mode | SHORT Mode |
|--------|-----------|------------|
| Entry Orders | BUY below market | SELL above market |
| Next Level Logic | `compute_next_buy_level()` | `compute_next_sell_level()` |
| TP Calculation | Entry + Step | Entry - Step |
| Position Direction | Decrease as price falls | Increase as price rises |
| Profit Direction | Price goes UP | Price goes DOWN |
| Strict Grid Helper | `find_nearest_grid_below()` | `find_nearest_grid_above()` |

---

## 🎨 UI/UX Considerations

### Color Coding

| Element | LONG Mode | SHORT Mode |
|---------|-----------|------------|
| Panel Background | Light green tint | Light red tint |
| Order Prices | Green text | Red text |
| TP Prices | Light green | Light red |
| Profit Values | Green | Green (profit is profit!) |
| Buttons | Green accent | Red accent |

### Real-time Updates

**Trigger**: Any change to grid configuration inputs

**Update Flow**:
1. User edits Lower/Upper/Step/Ref in Configuration Panel
2. Frontend debounces input (500ms delay)
3. Call `/api/grid/calculations` with new parameters
4. Update both LONG and SHORT panels simultaneously
5. Highlight changed values

### Loading States

```
┌─────────────────────────────────────────────────────────────┐
│ 📈 LONG Mode Grid Calculations                              │
│                                                             │
│  [  Loading calculations...  ]                             │
│  ⏳ Computing buy sequence, TP levels, and grid layout...  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Error States

```
┌─────────────────────────────────────────────────────────────┐
│ 📈 LONG Mode Grid Calculations                              │
│                                                             │
│  ⚠️ Invalid Grid Configuration                              │
│  Lower bound ($110,000) must be less than upper ($99,000)  │
│                                                             │
│  Please fix the configuration above to see calculations.   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Responsive Design

**Desktop (≥1280px)**:
- Configuration Panel: Full width
- LONG/SHORT Panels: Side-by-side (50% each)

**Tablet (768px-1279px)**:
- Configuration Panel: Full width
- LONG/SHORT Panels: Stacked (100% each)

**Mobile (≤767px)**:
- Configuration Panel: Full width, compact inputs
- LONG/SHORT Panels: Tabs (show one at a time)

---

## 🔗 Integration Points

### Frontend Components to Create

1. **`GridConfigurationPanel.js`** (350 lines)
   - Input fields for all 9 settings
   - Real-time validation
   - Live calculation summary
   - Save/Cancel actions

2. **`GridCalculationPreview.js`** (400 lines)
   - Fetches calculations from API
   - Displays BUY/SELL sequences
   - Shows TP levels
   - Grid visualization

3. **`GridLevelChart.js`** (200 lines)
   - Visual chart of grid levels
   - Highlights active zones
   - Shows market price indicator

### Backend Routes to Create

1. **`GET /api/grid/calculations`**
   - Accepts: mode, lower, upper, step, ref, tick_size, max_open
   - Returns: Full calculation breakdown (see Panel 2 response)

2. **`POST /api/config/grid`** (optional)
   - Specialized endpoint for grid-only updates
   - Validates grid parameters before saving

### State Management

```javascript
// Frontend state structure
const [gridConfig, setGridConfig] = useState({
  mode: 'LONG',
  lower: 99000,
  upper: 110000,
  step: 500,
  ref: 103800,
  tickSize: 0.5,
  symbol: 'BTCUSD',
  lotSize: 1,
  maxOpen: 5,
  heartbeat: 20
});

const [calculations, setCalculations] = useState({
  long: null,    // Response from /api/grid/calculations?mode=LONG
  short: null    // Response from /api/grid/calculations?mode=SHORT
});

const [validationErrors, setValidationErrors] = useState([]);
```

---

## 📝 Code Mapping to grid_calculator.py

| Function | Panel Usage | Lines in grid_calculator.py |
|----------|-------------|------------------------------|
| `compute_next_buy_level()` | LONG: BUY sequence | 79-120 |
| `compute_next_sell_level()` | SHORT: SELL sequence | 122-186 |
| `compute_tp_price()` | LONG: TP sequence | 188-200 |
| `compute_tp_price_short()` | SHORT: TP sequence | 202-214 |
| `quantize_price()` | All price displays | 239-280 |
| `is_within_bounds()` | Validation checks | 282-303 |
| `get_grid_levels()` | Grid visualization | 305-335 |
| `is_price_grid_aligned()` | Alignment checks | 337-358 |
| `find_nearest_grid_below()` | LONG: Strict Grid | 380-409 |
| `find_nearest_grid_above()` | SHORT: Strict Grid | 411-439 |
| `get_startup_maker_buy_level()` | LONG: First order logic | 441-515 |
| `get_startup_maker_sell_level()` | SHORT: First order logic | 517-579 |

---

## 🚀 Implementation Phases

### Phase 1: Backend API (2-3 hours)
1. Create `webui/backend/routes/grid_calculations.py`
2. Implement `/api/grid/calculations` endpoint
3. Add helper functions for sequence generation
4. Write unit tests for API

### Phase 2: Configuration Panel (3-4 hours)
1. Create `GridConfigurationPanel.js`
2. Wire up to `/api/config/update`
3. Add validation logic
4. Implement real-time summary

### Phase 3: Calculation Previews (4-5 hours)
1. Create `GridCalculationPreview.js`
2. Implement LONG mode display
3. Implement SHORT mode display
4. Add loading/error states

### Phase 4: Grid Visualization (2-3 hours)
1. Create `GridLevelChart.js`
2. Add interactive chart
3. Integrate with calculation panels

### Phase 5: Integration & Testing (2-3 hours)
1. Add to main App.js
2. Test all scenarios
3. Mobile responsiveness
4. Documentation

**Total Estimated Time**: 13-18 hours

---

## ✅ Testing Checklist

### Unit Tests
- [ ] GridCalculator integration (Python)
- [ ] API endpoint responses
- [ ] Frontend validation logic
- [ ] Price calculation accuracy

### Integration Tests
- [ ] Config save → API → File update
- [ ] Calculation preview refresh on config change
- [ ] Mode toggle LONG ↔ SHORT
- [ ] Grid bounds validation

### UI/UX Tests
- [ ] All fields accept valid input
- [ ] Validation errors display correctly
- [ ] Real-time calculations update
- [ ] Mobile layout works
- [ ] Loading states show
- [ ] Error states display

### Edge Cases
- [ ] Lower = Upper (invalid)
- [ ] Step > (Upper - Lower) (invalid)
- [ ] Ref outside bounds (invalid)
- [ ] Max Open = 0 (invalid)
- [ ] Negative values (invalid)
- [ ] Market price outside grid (edge case)

---

## 📚 References

- **Code**: `bot/strategy/modules/grid_calculator.py` (lines 1-634)
- **Config**: `grid_config.env` (lines 66-78)
- **Existing UI**: Screenshot showing current grid parameters panel
- **API Pattern**: `webui/backend/routes/config.py` (existing config endpoints)

---

## 🎯 Success Criteria

1. ✅ User can edit all 9 grid parameters in one panel
2. ✅ Changes auto-save to `grid_config.env`
3. ✅ Real-time preview of BUY/SELL sequences
4. ✅ Clear display of TP levels and profit estimates
5. ✅ Visual grid level chart
6. ✅ Mode toggle updates both config and previews
7. ✅ All calculations match `grid_calculator.py` logic exactly
8. ✅ Mobile-responsive design
9. ✅ < 1 second calculation refresh time
10. ✅ Zero calculation errors (100% accuracy)

---

**End of Design Document**

*Ready for implementation approval. No coding has been done yet.*
