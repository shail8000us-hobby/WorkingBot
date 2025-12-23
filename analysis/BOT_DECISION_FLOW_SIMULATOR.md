# GridBot Decision Flow Simulator
## Step-by-Step Bot Logic Walkthrough with Real Scenarios

**Date**: November 8, 2025  
**Purpose**: Understand EXACT bot behavior in all scenarios before production  
**Status**: Pre-Production Verification (Testnet Down)

---

## 📋 Table of Contents

1. [Basic Scenarios (Simple Logic)](#basic-scenarios)
2. [Intermediate Scenarios (Multi-Step Logic)](#intermediate-scenarios)
3. [Advanced Scenarios (Complex Decision Trees)](#advanced-scenarios)
4. [Edge Case Scenarios (Rare but Critical)](#edge-case-scenarios)
5. [Order Placement Logic Deep Dive](#order-placement-logic)
6. [Decision Matrix Reference](#decision-matrix)

---

## 🎯 Bot Configuration (Example)

```env
# Grid Settings
GRID_MODE=long
REF_PRICE=95000
GRID_STEP_INR=1000
GRID_LOWER=90000
GRID_UPPER=100000
ORDER_SIZE_LOTS=100
MAX_OPEN_POSITIONS=5
TP_OFFSET_INR=1000

# Safety Settings
EXECUTE_ORDERS=True
VOLATILITY_SAFETY_ENABLED=True
MARGIN_UTILIZATION_THRESHOLD=40
EQUITY_FLOOR_INR=50000
MAX_TRANCHES_PER_MINUTE=2
GUARDIAN_MAX_ACCOUNT_LOSS_INR=10000
```

---

## 📊 BASIC SCENARIOS (Simple Logic)

### Scenario 1: Bot Startup (No Positions)

**Initial State:**
- Market Price: $94,500
- Positions: 0
- Pending Orders: 0
- Equity: ₹100,000

**Bot Decision Flow:**

```
STEP 1: STARTUP INITIALIZATION
├─ Load config from grid_config.env
├─ Initialize modules:
│  ├─ PositionManager
│  ├─ OrderManager  
│  ├─ GridCalculator
│  ├─ SafetyGatekeeper
│  └─ WebSocket connections
└─ Status: ✅ All modules loaded

STEP 2: SAFETY CHECKS
├─ Check emergency flag: .guardian_emergency_stop
│  └─ ❌ File not found → SAFE ✅
├─ Check EXECUTE_ORDERS environment variable
│  └─ ✅ Value: True → Orders ENABLED
├─ Check I_UNDERSTAND_LIVE (for live mode)
│  └─ ✅ Mode: demo → Skip check
├─ Check volatility safety
│  ├─ Fetch current IV/RV from Delta Exchange
│  ├─ Current IV: 28% (max: 35%)
│  ├─ Current RV: 32% (max: 40%)
│  └─ ✅ VOLATILITY SAFE
└─ Status: ✅ All safety checks passed

STEP 3: RECONCILIATION
├─ Check for orphaned positions from previous session
│  └─ Query exchange for open positions with BOT- prefix
│  └─ Found: 0 positions
├─ Check for orphaned orders
│  └─ Query exchange for open orders with BOT- prefix
│  └─ Found: 0 orders
└─ Status: ✅ Clean slate

STEP 4: CALCULATE INITIAL BUY PRICE
├─ Current Market Price: $94,500
├─ REF_PRICE: $95,000
├─ GRID_STEP: $1,000
├─ Mode: LONG
│
├─ Logic: Find nearest grid level BELOW current price
│  ├─ Calculate offset from REF: $94,500 - $95,000 = -$500
│  ├─ Steps from REF: -$500 / $1,000 = -0.5 steps
│  ├─ Round DOWN to whole step: -1 step
│  ├─ Next BUY level: $95,000 + (-1 × $1,000) = $94,000
│  └─ Verify in grid bounds:
│     ├─ $94,000 >= $90,000 (GRID_LOWER) ✅
│     └─ $94,000 <= $100,000 (GRID_UPPER) ✅
│
└─ DECISION: Place BUY order at $94,000

STEP 5: ORDER PLACEMENT CHECKS
├─ Gatekeeper check: can_place_orders()
│  ├─ Emergency flag: ✅ None
│  ├─ EXECUTE_ORDERS: ✅ True  
│  ├─ Volatility: ✅ Safe
│  ├─ Margin utilization: 0% ✅ (threshold: 40%)
│  └─ Result: ✅ APPROVED
│
├─ Duplicate order prevention
│  ├─ Check recent orders cache: Empty
│  ├─ Check pending_buy tracker: None
│  └─ ✅ Not a duplicate
│
├─ Exposure limiter check
│  ├─ Tranches in last 60s: 0
│  ├─ Max allowed: 2 per minute
│  └─ ✅ Within limits
│
└─ Status: ✅ All checks passed

STEP 6: EXECUTE BUY ORDER
├─ Generate order details:
│  ├─ Side: BUY
│  ├─ Price: $94,000
│  ├─ Size: 100 lots
│  ├─ Type: LIMIT
│  ├─ Client Order ID: BOT-LONG-BUY-1731024000-abc123
│  └─ Time In Force: GTC (Good Till Cancel)
│
├─ Submit to exchange (via API client with circuit breaker)
│  ├─ API Response: {"order_id": "DX-789456", "status": "open"}
│  └─ ✅ Order placed successfully
│
├─ Update internal state:
│  ├─ Save to pending_buy tracker
│  │  └─ {order_id: DX-789456, price: 94000, size: 100, placed_at: ...}
│  ├─ Record in recent_orders cache (duplicate prevention)
│  └─ Log to bot_live.log
│
└─ Status: ✅ Order placed and tracked

FINAL STATE:
├─ Market Price: $94,500
├─ Pending BUY: $94,000 (100 lots) - Order ID: DX-789456
├─ Positions: 0
├─ Next Action: Wait for fill
```

**Calculation Summary:**
- REF: $95,000
- Current: $94,500  
- Step: $1,000
- **Next BUY = $95,000 - $1,000 = $94,000** ✅

---

### Scenario 2: First BUY Order Fills (Partial Fill)

**Initial State:**
- Market Price: $94,000 (dropped to buy level)
- Pending BUY: $94,000 (100 lots) - Order ID: DX-789456
- Positions: 0

**WebSocket Fill Event Received:**
```json
{
  "order_id": "DX-789456",
  "side": "buy",
  "fill_price": 94000,
  "fill_size": 43,
  "cumulative_filled": 43,
  "total_order_size": 100,
  "is_complete": false,
  "remaining": 57
}
```

**Bot Decision Flow:**

```
STEP 1: FILL DETECTION
├─ WebSocket receives fill notification
├─ Fill Detector validates:
│  ├─ Order ID: DX-789456 ✅ (matches pending_buy)
│  ├─ Not a duplicate: ✅ (check seen_fills cache)
│  └─ Mark as processed in cache
└─ Route to gridbot._process_incremental_fill()

STEP 2: IDENTIFY FILL TYPE
├─ Check pending_buy tracker
│  └─ Found: {order_id: DX-789456, ...}
├─ Side: BUY → LONG mode handler
├─ is_complete: False → PARTIAL FILL
└─ Route to: long_handler.handle_buy_fill()

STEP 3: LONG HANDLER PROCESSES PARTIAL FILL
├─ Log: "🎯 BUY incremental fill: 43 lots @ $94,000 (43/100)"
│
├─ Calculate position for THIS partial fill:
│  ├─ Fill size: 43 lots
│  ├─ Entry price: $94,000
│  ├─ Notional: 43 × $94,000 = ₹4,042,000
│  └─ Create position record
│
├─ Calculate TP price for THIS position:
│  ├─ Entry: $94,000
│  ├─ TP offset: $1,000
│  ├─ TP price: $94,000 + $1,000 = $95,000
│  └─ Verify TP within bounds (≤ GRID_UPPER) ✅
│
├─ Place TP SELL order:
│  ├─ Gatekeeper check: ✅ Approved
│  ├─ Side: SELL
│  ├─ Price: $95,000
│  ├─ Size: 43 lots (matches position)
│  ├─ Type: LIMIT
│  ├─ Submit to exchange
│  └─ Response: {order_id: "DX-789457", status: "open"}
│
├─ Save position with TP:
│  └─ position_manager.add_position({
│       id: "pos_001",
│       side: "long",
│       entry_price: 94000,
│       size: 43,
│       tp_price: 95000,
│       tp_id: "DX-789457",
│       status: "open"
│     })
│
└─ Log: "✅ Created position: 43 lots, TP @ $95,000"

STEP 4: UPDATE PENDING_BUY FOR REMAINING SIZE
├─ Original size: 100 lots
├─ Filled: 43 lots
├─ Remaining: 57 lots
│
├─ Update pending_buy tracker:
│  └─ {order_id: DX-789456, size: 57, cumulative: 43, ...}
│
└─ Status: Still waiting for remaining 57 lots

STEP 5: CHECK IF SHOULD PLACE NEXT GRID BUY
├─ Logic: NO - Original order still partially open
├─ Reason: Wait for complete fill or cancellation
└─ Action: Continue monitoring

FINAL STATE:
├─ Market Price: $94,000
├─ Pending BUY: $94,000 (57 lots remaining) - Order ID: DX-789456
├─ Positions: 1
│  └─ Position #1: 43 lots @ $94,000, TP @ $95,000 (Order: DX-789457)
├─ Total Exposure: ₹4,042,000
├─ Next Action: Wait for remaining fill or place next grid level
```

**Key Calculations:**
- **Partial Fill Size**: 43 lots (from exchange)
- **TP Price**: $94,000 + $1,000 = $95,000 ✅
- **TP Size**: 43 lots (matches position exactly) ✅
- **Remaining Order**: 100 - 43 = 57 lots ✅

---

### Scenario 3: First BUY Order Completes (Full Fill)

**Initial State:**
- Market continues at $94,000
- Pending BUY: $94,000 (57 lots remaining)
- Positions: 1 (43 lots with TP)

**WebSocket Fill Event:**
```json
{
  "order_id": "DX-789456",
  "side": "buy",
  "fill_price": 94000,
  "fill_size": 57,
  "cumulative_filled": 100,
  "total_order_size": 100,
  "is_complete": true,
  "remaining": 0
}
```

**Bot Decision Flow:**

```
STEP 1: DETECT COMPLETE FILL
├─ Fill Detector receives event
├─ is_complete: true → FULL ORDER FILLED
└─ Route to long_handler.handle_buy_fill()

STEP 2: PROCESS FINAL PARTIAL FILL
├─ Log: "🎯 BUY incremental fill: 57 lots @ $94,000 (100/100 COMPLETE)"
│
├─ Create position for final 57 lots:
│  ├─ Entry: $94,000
│  ├─ Size: 57 lots
│  └─ TP: $95,000
│
├─ Place TP SELL order:
│  ├─ Size: 57 lots
│  ├─ Price: $95,000
│  └─ Response: {order_id: "DX-789458"}
│
└─ Add position: Position #2 (57 lots @ $94,000)

STEP 3: CLEAR PENDING_BUY TRACKER
├─ Order DX-789456 is 100% filled
├─ No longer "pending"
├─ Action: position_manager.clear_pending_buy()
└─ Status: ✅ Pending buy cleared

STEP 4: CALCULATE NEXT GRID BUY LEVEL
├─ Current level just filled: $94,000
├─ Grid step: $1,000
├─ Mode: LONG (buy lower)
│
├─ Next BUY level: $94,000 - $1,000 = $93,000
│
├─ Verify within bounds:
│  ├─ $93,000 >= $90,000 (GRID_LOWER) ✅
│  └─ $93,000 <= $100,000 (GRID_UPPER) ✅
│
└─ DECISION: Place new BUY at $93,000

STEP 5: POSITION CAPACITY CHECK
├─ Current open positions: 2
├─ MAX_OPEN_POSITIONS: 5
├─ Can open more: 5 - 2 = 3 slots available
└─ ✅ APPROVED to place next BUY

STEP 6: SAFETY CHECKS FOR NEXT BUY
├─ Gatekeeper:
│  ├─ Emergency flag: ✅ None
│  ├─ Volatility: ✅ Safe (IV: 28%, RV: 32%)
│  ├─ Margin utilization: 15% ✅ (threshold: 40%)
│  └─ Result: ✅ APPROVED
│
├─ Duplicate prevention:
│  ├─ Check recent orders: No $93,000 BUY in last 60s
│  └─ ✅ Not duplicate
│
├─ Exposure limiter:
│  ├─ Tranches placed in last 60s: 2 (from initial + TP placements)
│  ├─ Max per minute: 2
│  └─ ⚠️ AT LIMIT - Must wait ~30s
│
└─ DECISION: QUEUE order or wait

STEP 7: ORDER THROTTLING
├─ Exposure limiter returned: False
├─ Reason: "Tranche rate limit: 2/2 per minute"
│
├─ Options:
│  A) Queue order (if EXPOSURE_GROWTH_QUEUE_ENABLED=true)
│  B) Wait for window to expire
│
├─ Configuration check: QUEUE_ENABLED=true
│
├─ Action: exposure_limiter.queue_order({
│     side: 'buy',
│     price: 93000,
│     amount: 100,
│     queued_at: <timestamp>
│  })
│
└─ Log: "📦 Order queued: BUY @ $93,000 (queue depth: 1)"

STEP 8: BACKGROUND QUEUE PROCESSING
├─ Every 5 seconds: Check if queued orders can be placed
│
├─ After 30s: Exposure window refreshed
│  ├─ Tranches in last 60s: 0 (old ones expired)
│  ├─ Can place: ✅ Yes
│  └─ Dequeue order
│
├─ Place dequeued BUY order:
│  ├─ Price: $93,000
│  ├─ Size: 100 lots
│  ├─ Submit to exchange
│  └─ Response: {order_id: "DX-789459"}
│
└─ Log: "✅ Dequeued order: BUY @ $93,000"

FINAL STATE:
├─ Market Price: $94,000
├─ Pending BUY: $93,000 (100 lots) - Order ID: DX-789459
├─ Positions: 2
│  ├─ Position #1: 43 lots @ $94,000, TP @ $95,000 (DX-789457)
│  └─ Position #2: 57 lots @ $94,000, TP @ $95,000 (DX-789458)
├─ Total Exposure: ₹9,400,000 (100 lots @ $94,000)
├─ Queue: Empty
├─ Next Action: Wait for $93,000 fill or TP fills
```

**Key Logic:**
- **Full fill detection**: `is_complete: true` ✅
- **Pending cleared**: After 100% fill ✅
- **Next grid**: $94,000 - $1,000 = $93,000 ✅
- **Throttling**: Exposure limiter queued order ✅
- **Auto-dequeue**: After rate limit window ✅

---

## 🔄 INTERMEDIATE SCENARIOS (Multi-Step Logic)

### Scenario 4: TP Fill (Position Close + Next Grid)

**Initial State:**
- Market Price: $95,000 (rallied to TP level)
- Positions: 2
  - Position #1: 43 lots @ $94,000, TP @ $95,000 (DX-789457)
  - Position #2: 57 lots @ $94,000, TP @ $95,000 (DX-789458)
- Pending BUY: $93,000 (100 lots) - DX-789459

**WebSocket Fill Event (TP):**
```json
{
  "order_id": "DX-789457",
  "side": "sell",
  "fill_price": 95000,
  "fill_size": 43,
  "is_complete": true
}
```

**Bot Decision Flow:**

```
STEP 1: IDENTIFY TP FILL
├─ Fill Detector receives SELL fill
├─ Check if matches any TP order:
│  └─ position_manager.find_position_by_order_id("DX-789457")
│  └─ Found: Position #1 (tp_id matches)
│
└─ Route to: long_handler.handle_tp_fill()

STEP 2: CLOSE POSITION
├─ Position details:
│  ├─ Entry: $94,000
│  ├─ Exit (TP): $95,000
│  ├─ Size: 43 lots
│  ├─ Profit per lot: $95,000 - $94,000 = $1,000
│  └─ Total profit: 43 × $1,000 = ₹43,000
│
├─ Update position status:
│  └─ position_manager.close_position("pos_001", {
│       exit_price: 95000,
│       realized_pnl: 43000,
│       closed_at: <timestamp>
│     })
│
├─ Release capacity:
│  ├─ Open positions before: 2
│  ├─ After close: 1
│  └─ Available slots: 5 - 1 = 4
│
└─ Log: "💰 TP FILLED: Closed 43 lots @ $95,000, Profit: ₹43,000"

STEP 3: CALCULATE NEXT GRID LEVEL
├─ TP level that just filled: $95,000
├─ Mode: LONG
├─ Direction after TP: Place next BUY BELOW
│
├─ Find next BUY level:
│  ├─ Current market: $95,000
│  ├─ REF_PRICE: $95,000
│  ├─ Offset: $95,000 - $95,000 = 0
│  ├─ We're AT ref price
│  │
│  ├─ Logic: Place BUY one step below current
│  ├─ Next BUY: $95,000 - $1,000 = $94,000
│  │
│  ├─ BUT: Check if $94,000 BUY already exists
│  │  └─ pending_buy: $93,000 (not $94,000)
│  │  └─ open_positions: None at $94,000 (Position #2 had $94,000 entry but different TP)
│  │
│  └─ WAIT: We already have Position #2 at $94,000 still open!
│
├─ Decision Tree:
│  ├─ Option A: Don't place duplicate level
│  ├─ Option B: Grid already filled at $94,000
│  └─ DECISION: Skip $94,000, continue with existing $93,000 BUY
│
└─ Action: NO new order needed

STEP 4: EQUITY UPDATE
├─ Before TP: ₹100,000
├─ Profit: +₹43,000
├─ After TP: ₹143,000
│
├─ Check equity floor:
│  ├─ Current: ₹143,000
│  ├─ Floor: ₹50,000
│  └─ ✅ Well above floor
│
└─ Update equity tracker

FINAL STATE:
├─ Market Price: $95,000
├─ Pending BUY: $93,000 (100 lots) - DX-789459
├─ Positions: 1
│  └─ Position #2: 57 lots @ $94,000, TP @ $95,000 (DX-789458)
├─ Closed Positions: 1
│  └─ Position #1: 43 lots, Entry $94K, Exit $95K, PnL +₹43,000
├─ Equity: ₹143,000 (+₹43,000)
├─ Next Action: Wait for $93,000 BUY or Position #2 TP
```

**Key Calculations:**
- **Profit**: ($95,000 - $94,000) × 43 = ₹43,000 ✅
- **Capacity released**: 2 → 1 positions ✅
- **Next grid check**: Already covered by existing orders ✅

---

### Scenario 5: Price Gap (Market Drops 3 Steps)

**Current State:**
- Market Price: $95,000
- Pending BUY: $93,000

**Sudden Market Event:**
- Market CRASHES from $95,000 → $91,500 (instant drop)
- This skips 3 grid levels!

**Bot Decision Flow:**

```
STEP 1: PRICE GAP DETECTION
├─ WebSocket price update: $91,500
├─ Previous price: $95,000
├─ Drop: $95,000 - $91,500 = $3,500
├─ Grid steps skipped: $3,500 / $1,000 = 3.5 steps
│
└─ ⚠️ PRICE GAP DETECTED (>1 step)

STEP 2: DETERMINE CURRENT POSITION
├─ Current market: $91,500
├─ REF_PRICE: $95,000
├─ We're now BELOW ref by: $3,500
│
├─ Expected grid levels between $95K and $91.5K:
│  ├─ $94,000 (REF - 1 step)
│  ├─ $93,000 (REF - 2 steps) ← We have pending BUY here
│  ├─ $92,000 (REF - 3 steps) ← MISSED
│  └─ $91,000 (REF - 4 steps) ← Current level
│
└─ Analysis: Market jumped past $93K and $92K levels

STEP 3: CHECK PENDING ORDER STATUS
├─ Query exchange for order DX-789459 ($93,000 BUY)
│
├─ Possible scenarios:
│  A) Order filled during crash
│  B) Order still open (price didn't touch it)
│  C) Order partially filled
│
├─ Exchange response: "Order partially filled"
│  ├─ Filled: 30 lots @ $93,000
│  ├─ Remaining: 70 lots
│  └─ Status: Still open
│
└─ Decision: Process the 30-lot fill first

STEP 4: PROCESS PARTIAL FILL FROM $93K
├─ Create position for 30 lots @ $93,000
├─ Calculate TP: $93,000 + $1,000 = $94,000
├─ Place TP order: 30 lots @ $94,000
└─ Update pending_buy: 70 lots remaining

STEP 5: PRICE GAP RECOVERY LOGIC
├─ Current market: $91,500
├─ Nearest grid level BELOW: $91,000
├─ Distance: $91,500 - $91,000 = $500
│
├─ Bot Logic Options:
│  A) Place new BUY at $91,000 (next grid level)
│  B) Wait for $93,000 to fully fill first
│  C) Cancel $93,000 and place at current level
│
├─ STRATEGY: grid_calculator.find_nearest_grid_below($91,500)
│  ├─ Input: current_price = $91,500
│  ├─ REF: $95,000
│  ├─ STEP: $1,000
│  │
│  ├─ Calculation:
│  │  ├─ Offset: $91,500 - $95,000 = -$3,500
│  │  ├─ Steps: -$3,500 / $1,000 = -3.5
│  │  ├─ Round DOWN: -4 steps
│  │  └─ Level: $95,000 + (-4 × $1,000) = $91,000
│  │
│  └─ Result: $91,000
│
└─ DECISION: Place BUY at $91,000 (skip $92,000 level)

STEP 6: CAPACITY CHECK
├─ Current positions: 1 ($94K entry) + 1 ($93K entry) = 2
├─ Pending: 70 lots @ $93,000
├─ If we add $91K: Would be 3 positions
├─ MAX_OPEN_POSITIONS: 5
└─ ✅ Can add more (2 slots available)

STEP 7: PLACE $91K BUY ORDER
├─ Gatekeeper check:
│  ├─ Volatility: ⚠️ Might spike during crash!
│  │  └─ Check IV/RV...
│  │  └─ IV: 45% (max: 35%) ❌ EXCEEDED
│  └─ Result: ❌ BLOCKED by volatility safety
│
├─ Log: "🌊 VOLATILITY UNSAFE - Order blocked"
├─ Log: "⏳ Will retry when IV normalizes"
│
└─ Action: DO NOT place $91K order yet

STEP 8: VOLATILITY MONITORING
├─ Bot enters "volatility halt" state
├─ Creates flag: .volatility_halt
├─ Every 60s: Re-check IV/RV
│
├─ After 5 minutes: IV drops to 32%
│  └─ ✅ Volatility safe again
│
├─ Clear .volatility_halt flag
└─ Resume normal trading

STEP 9: PLACE QUEUED $91K ORDER
├─ Volatility now safe
├─ Re-run gap recovery logic
│  └─ Still at $91,500 → Need $91K BUY
│
├─ Gatekeeper: ✅ All checks pass
├─ Place BUY order:
│  ├─ Price: $91,000
│  ├─ Size: 100 lots
│  └─ Order ID: DX-789460
│
└─ Log: "✅ Gap recovery: Placed BUY @ $91,000"

FINAL STATE:
├─ Market Price: $91,500
├─ Pending BUYs:
│  ├─ $93,000 (70 lots) - DX-789459
│  └─ $91,000 (100 lots) - DX-789460
├─ Positions: 2
│  ├─ Position #2: 57 lots @ $94,000, TP @ $95,000
│  └─ Position #3: 30 lots @ $93,000, TP @ $94,000
├─ Skipped Level: $92,000 (intentional - price gap logic)
├─ Volatility: Back to safe levels
└─ Next Action: Wait for fills at $93K or $91K
```

**Key Logic:**
- **Gap detection**: Price moved >1 grid step ✅
- **Find nearest grid**: `find_nearest_grid_below()` → $91,000 ✅
- **Skip intermediate**: $92,000 skipped (gap recovery) ✅
- **Volatility halt**: Blocked order during IV spike ✅
- **Auto-resume**: Placed order when safe ✅

---

## 🚀 ADVANCED SCENARIOS (Complex Decision Trees)

### Scenario 6: Max Positions Reached + Margin Alert

**Initial State:**
- Market continues dropping
- Positions fill at: $94K, $93K, $91K, $90K
- Now have 5 positions (MAX reached)
- Market at $89,500

**Bot Decision Flow:**

```
STEP 1: NEXT GRID CALCULATION
├─ Market: $89,500
├─ Last BUY filled: $90,000
├─ Next grid level: $90,000 - $1,000 = $89,000
│
└─ Attempt to place BUY @ $89,000

STEP 2: POSITION CAPACITY CHECK
├─ Current open positions: 5
│  ├─ $94,000: 57 lots
│  ├─ $93,000: 100 lots (30 + 70 fills)
│  ├─ $91,000: 100 lots
│  ├─ $90,000: 100 lots
│  └─ Total: 357 lots
│
├─ MAX_OPEN_POSITIONS: 5
├─ Available slots: 5 - 5 = 0
│
└─ ❌ CAPACITY FULL - Cannot place new BUY

STEP 3: POSITION MANAGER DECISION
├─ position_manager.can_open_position()
│  └─ Returns: False, "Max positions reached"
│
├─ Log: "⚠️ Cannot place $89K BUY - Max 5 positions"
├─ Log: "📊 Waiting for TP fill to free capacity"
│
└─ Action: SKIP order placement, wait for TP

STEP 4: MARGIN UTILIZATION CHECK (Background)
├─ Total exposure calculation:
│  ├─ 57 × $94,000 = ₹5,358,000
│  ├─ 100 × $93,000 = ₹9,300,000
│  ├─ 100 × $91,000 = ₹9,100,000
│  ├─ 100 × $90,000 = ₹9,000,000
│  └─ Total: ₹32,758,000
│
├─ Account equity: ₹143,000 (from earlier profit)
├─ Leverage: 20x (Delta Exchange default for BTC)
│
├─ Required margin: ₹32,758,000 / 20 = ₹1,637,900
├─ Margin utilization: (₹1,637,900 / ₹143,000) × 100 = 1,145%
│
└─ ⚠️ This would exceed account equity!

STEP 5: REALITY CHECK
├─ Problem: Numbers don't align
├─ Reason: This is DELTA EXCHANGE TESTNET simulation
│  └─ Actual Delta uses CONTRACTS not LOTS
│  └─ 1 contract = $1 of BTC
│
├─ Corrected calculation (if using real Delta):
│  ├─ Position size would be in USD notional
│  ├─ E.g., 100 lots might = $100 notional
│  └─ Margin would be fraction of equity
│
└─ For this simulation: Assume realistic leverage

STEP 6: GUARDIAN BOT MONITORING (Parallel Process)
├─ Guardian checks every 60s:
│  ├─ Total unrealized PnL
│  ├─ Margin utilization %
│  ├─ Distance to liquidation
│  └─ Account equity
│
├─ Current state:
│  ├─ Entry avg: ~$91,700 (weighted)
│  ├─ Market: $89,500
│  ├─ Unrealized loss: ~₹2,200 per lot × 357 lots = -₹785,400
│  ├─ Equity after loss: ₹143,000 - ₹785,400 = -₹642,400
│  │
│  └─ ⚠️ ACCOUNT IN DRAWDOWN
│
├─ Guardian loss limit check:
│  ├─ GUARDIAN_MAX_ACCOUNT_LOSS_INR: ₹10,000
│  ├─ Current loss: ₹785,400
│  ├─ Threshold: 80% of ₹10,000 = ₹8,000
│  │
│  └─ ❌ LOSS LIMIT BREACHED
│
└─ EMERGENCY ACTION TRIGGERED

STEP 7: GUARDIAN EMERGENCY STOP
├─ Guardian detects critical loss
├─ Actions taken:
│  1. Create .guardian_emergency_stop flag
│  2. Send Telegram alert:
│     "🚨 EMERGENCY STOP: Loss limit breached"
│  3. Log to guardian.log:
│     "Total loss: ₹785,400 > ₹10,000 limit"
│  4. DO NOT auto-close positions (preserve state)
│
└─ Status: 🛑 TRADING HALTED

STEP 8: MAIN BOT RESPONSE
├─ Next order placement attempt
├─ Gatekeeper check: can_place_orders()
│  ├─ Check .guardian_emergency_stop flag
│  │  └─ ✅ File exists
│  │
│  └─ Result: ❌ BLOCKED
│
├─ Log: "🚨 SAFETY GATEKEEPER: ORDER BLOCKED"
├─ Log: "Reason: EMERGENCY FLAG EXISTS"
├─ Log: "To resume trading:"
├─ Log: "  1. Investigate why flag was created"
├─ Log: "  2. Fix underlying issue"
├─ Log: "  3. Remove flag: rm .guardian_emergency_stop"
│
└─ Bot continues running but CANNOT place orders

STEP 9: EXISTING POSITIONS STILL ACTIVE
├─ TPs remain on exchange (not cancelled)
├─ If market rallies:
│  └─ TPs can still fill
│  └─ Losses reduced automatically
│
└─ Manual intervention required to resume trading

FINAL STATE:
├─ Market Price: $89,500
├─ Pending BUYs: None (capacity full + emergency stop)
├─ Positions: 5 (all open with TPs)
├─ Unrealized PnL: -₹785,400
├─ Equity: -₹642,400 (massive drawdown)
├─ Emergency Stop: 🛑 ACTIVE
├─ Action Required: Manual review + flag removal
```

**Critical Learning:**
- **Position limits work**: Stopped at 5 positions ✅
- **Guardian monitors**: Detected excessive loss ✅
- **Emergency stop triggered**: Prevented further damage ✅
- **TPs stay active**: Can still recover if market rallies ✅
- **Manual intervention needed**: Cannot auto-resume ✅

---

## 📖 EDGE CASE SCENARIOS (Rare but Critical)

### Scenario 7: Duplicate Fill (WebSocket + REST)

**Setup:**
- Network glitchy
- Bot receives same fill notification twice

**Bot Decision Flow:**

```
STEP 1: FIRST FILL NOTIFICATION (WebSocket)
├─ Fill data: {order_id: "DX-100", size: 50, ...}
├─ Fill Detector processes:
│  ├─ Check seen_fills cache: Not found
│  ├─ Generate unique key: "DX-100_50_94000_<timestamp>"
│  ├─ Add to cache
│  └─ Process fill normally
│
└─ Position created: 50 lots @ $94,000

STEP 2: DUPLICATE NOTIFICATION (REST API poll)
├─ 10 seconds later...
├─ REST API returns: Same fill {order_id: "DX-100", size: 50}
│
├─ Fill Detector receives:
│  ├─ Generate key: "DX-100_50_94000_<timestamp>"
│  ├─ Check cache: ✅ FOUND (marked as processed)
│  ├─ Log: "⏩ Duplicate fill detected - Skipping"
│  └─ Return early (do not process)
│
└─ Result: ✅ Duplicate prevented

FINAL STATE:
├─ Positions: 1 (50 lots) ← Correct
├─ NOT 2 positions ← Duplicate avoided ✅
└─ Cache cleaned after 300s
```

**Protection**: `seen_fills` cache with TTL ✅

---

### Scenario 8: Concurrent Fills (2 Orders Fill Simultaneously)

**Setup:**
- Pending BUY @ $93,000 (100 lots)
- Pending BUY @ $91,000 (100 lots)
- Market crashes through both levels instantly
- Both fill within 100ms of each other

**Bot Decision Flow:**

```
STEP 1: WEBSOCKET RECEIVES 2 FILLS (Almost Simultaneous)
├─ T=0ms: Fill #1 arrives (DX-200, $93K, 100 lots)
├─ T=50ms: Fill #2 arrives (DX-201, $91K, 100 lots)
│
└─ Both queued in fill_detector

STEP 2: FILL QUEUE PROCESSING (Sequential)
├─ Fill Detector uses threading.Queue
├─ FIFO processing (First In, First Out)
│
├─ Worker thread picks Fill #1:
│  ├─ Process $93K fill
│  ├─ Create position
│  ├─ Place TP
│  ├─ Update pending_buy
│  └─ Duration: ~500ms
│
├─ Worker thread picks Fill #2:
│  ├─ Process $91K fill
│  ├─ Create position
│  ├─ Place TP
│  └─ Duration: ~500ms
│
└─ Total processing: ~1 second (sequential, not parallel)

STEP 3: STATE LOCK PROTECTION
├─ position_manager uses threading.Lock
│
├─ Fill #1 processing:
│  ├─ Acquire lock
│  ├─ Modify positions dict
│  ├─ Release lock
│
├─ Fill #2 processing:
│  ├─ Wait for lock (blocked until Fill #1 done)
│  ├─ Acquire lock
│  ├─ Modify positions dict
│  ├─ Release lock
│
└─ Result: No race condition ✅

FINAL STATE:
├─ Positions: 2 (one @ $93K, one @ $91K)
├─ TPs placed: 2 (sequential placement)
├─ State consistent: ✅ No corruption
└─ Processing order: Deterministic (FIFO)
```

**Protection**: Sequential queue + state locks ✅

---

### Scenario 9: Orphaned Position (Bot Crash + Restart)

**Setup:**
- Bot places BUY @ $92,000
- Order fills while bot is restarting
- Bot comes back online
- Position exists on exchange but NOT in bot's memory

**Bot Decision Flow:**

```
STEP 1: BOT STARTUP AFTER CRASH
├─ Load config
├─ Initialize modules
├─ WebSocket reconnect
│
└─ RECONCILIATION PHASE begins

STEP 2: ORPHANED ORDER DETECTION
├─ Query exchange: GET /orders (open orders)
│  └─ Response: [
│       {id: "DX-300", client_order_id: "BOT-LONG-BUY-...", status: "filled"},
│       ...
│     ]
│
├─ Filter BOT- prefix orders
├─ Found: Order DX-300 (filled during downtime)
│
├─ Action: reconciliation.adopt_orphaned_order()
│  ├─ Create fill_data from order:
│  │  └─ {order_id: "DX-300", fill_price: 92000, fill_size: 100}
│  ├─ Route to long_handler.handle_buy_fill()
│  └─ Process as normal fill
│
└─ Result: Position created for 100 lots @ $92K

STEP 3: ORPHANED POSITION DETECTION
├─ Query exchange: GET /positions
│  └─ Response: [
│       {size: 100, entry_price: 92000, unrealized_pnl: ...},
│       ...
│     ]
│
├─ Check if position_manager has this position
│  └─ Not found in local state
│
├─ Action: reconciliation.adopt_orphaned_position()
│  ├─ Add to positions dict
│  ├─ Calculate expected TP: $92K + $1K = $93K
│  ├─ Check if TP order exists:
│  │  └─ Query exchange for SELL @ $93K
│  │  └─ Not found
│  │
│  └─ MISSING TP DETECTED

STEP 4: MISSING TP PLACEMENT
├─ Position: 100 lots @ $92,000 (no TP)
│
├─ safe_place_tp() called:
│  ├─ Calculate TP: $93,000
│  ├─ Gatekeeper check: ✅ Approved
│  ├─ Place TP order: 100 lots @ $93,000
│  └─ Response: {order_id: "DX-301"}
│
├─ Link TP to position:
│  └─ position_manager.update_position({
│       tp_id: "DX-301",
│       tp_price: 93000
│     })
│
└─ Log: "🔧 Reconciled orphaned position + placed missing TP"

STEP 5: SYNC VERIFICATION
├─ Compare exchange state vs bot state:
│  ├─ Positions: Match ✅
│  ├─ Open orders: Match ✅
│  ├─ TPs: All have TPs ✅
│  └─ Pending tracker: Synced ✅
│
└─ Status: 🟢 FULLY RECONCILED

FINAL STATE:
├─ Bot restarted and synced
├─ Orphaned position adopted
├─ Missing TP placed
├─ Ready to resume normal trading
└─ Zero data loss from crash ✅
```

**Protection**: Startup reconciliation + TP detection ✅

---

## 🎛️ ORDER PLACEMENT LOGIC DEEP DIVE

### Complete Order Placement Decision Tree

```
┌─────────────────────────────────────────────┐
│  TRIGGER: Price Update / Fill Event         │
└─────────────┬───────────────────────────────┘
              │
              ▼
   ┌──────────────────────┐
   │ Should place order?  │
   │ (Handler logic)      │
   └──────┬───────────────┘
          │
          ├─ NO → Wait for next trigger
          │
          ├─ YES
          │
          ▼
   ┌────────────────────────────────┐
   │ STEP 1: Calculate Order Price  │
   │                                │
   │ • LONG Mode:                   │
   │   - BUY: Next grid level DOWN  │
   │   - TP: Entry + TP_OFFSET      │
   │                                │
   │ • SHORT Mode:                  │
   │   - SELL: Next grid level UP   │
   │   - TP: Entry - TP_OFFSET      │
   └────────┬───────────────────────┘
            │
            ▼
   ┌────────────────────────────────┐
   │ STEP 2: Verify Grid Bounds     │
   │                                │
   │ if price < GRID_LOWER: ❌      │
   │ if price > GRID_UPPER: ❌      │
   │ else: ✅ Proceed              │
   └────────┬───────────────────────┘
            │
            ▼
   ┌────────────────────────────────┐
   │ STEP 3: Position Capacity      │
   │                                │
   │ open_positions >= MAX? ❌      │
   │ else: ✅ Proceed              │
   └────────┬───────────────────────┘
            │
            ▼
   ┌────────────────────────────────┐
   │ STEP 4: Duplicate Detection    │
   │                                │
   │ • Check pending_buy/sell       │
   │ • Check recent_orders cache    │
   │ • Check throttle timing        │
   │                                │
   │ if duplicate: ❌               │
   │ else: ✅ Proceed              │
   └────────┬───────────────────────┘
            │
            ▼
   ┌────────────────────────────────┐
   │ STEP 5: Safety Gatekeeper      │
   │                                │
   │ Check #1: Emergency flag       │
   │ ├─ .guardian_emergency_stop    │
   │ └─ exists? ❌ BLOCK            │
   │                                │
   │ Check #2: EXECUTE_ORDERS       │
   │ ├─ env var = False? ❌ BLOCK   │
   │ └─ env var = True? ✅          │
   │                                │
   │ Check #3: I_UNDERSTAND_LIVE    │
   │ ├─ (only for live mode)        │
   │ └─ not set? ❌ BLOCK           │
   │                                │
   │ Check #4: Volatility Safety    │
   │ ├─ IV > max? ❌ BLOCK          │
   │ ├─ RV > max? ❌ BLOCK          │
   │ └─ spread > max? ❌ BLOCK      │
   │                                │
   │ Check #5: Margin Utilization   │
   │ ├─ util > threshold? ❌ BLOCK  │
   │ └─ (only for BUY orders)       │
   │                                │
   │ Check #6: Confirmation Guard   │
   │ ├─ waiting for confirm? ❌     │
   │ └─ timeout? ✅ Proceed        │
   │                                │
   │ ALL PASS? ✅ Proceed          │
   │ ANY FAIL? ❌ ABORT            │
   └────────┬───────────────────────┘
            │
            ▼
   ┌────────────────────────────────┐
   │ STEP 6: Exposure Limiter       │
   │                                │
   │ • Count orders in last 60s     │
   │ • tranches >= max? ⚠️          │
   │   ├─ Queue enabled? → QUEUE    │
   │   └─ No queue? → ❌ ABORT     │
   │                                │
   │ • notional >= max? ⚠️          │
   │   └─ Same as above             │
   │                                │
   │ • Within limits? ✅ Proceed   │
   └────────┬───────────────────────┘
            │
            ▼
   ┌────────────────────────────────┐
   │ STEP 7: Generate Order Details │
   │                                │
   │ • client_order_id:             │
   │   "BOT-{MODE}-{SIDE}-{TS}-{ID}"│
   │ • price: (from Step 1)         │
   │ • size: ORDER_SIZE_LOTS        │
   │ • type: LIMIT                  │
   │ • time_in_force: GTC           │
   └────────┬───────────────────────┘
            │
            ▼
   ┌────────────────────────────────┐
   │ STEP 8: Submit to Exchange     │
   │ (via Circuit Breaker)          │
   │                                │
   │ Circuit Breaker checks:        │
   │ ├─ State: OPEN? ❌ Raise error │
   │ ├─ State: HALF_OPEN? ⚠️ Test  │
   │ └─ State: CLOSED? ✅ Allow    │
   │                                │
   │ API call:                      │
   │ └─ exchange.create_order(...)  │
   │                                │
   │ Response:                      │
   │ ├─ Success: {order_id: ...}    │
   │ │   └─ Circuit: ✅ Record success│
   │ │                              │
   │ └─ Error:                      │
   │     ├─ Check if IGNORED_ERROR  │
   │     │   └─ Yes: ✅ Don't count │
   │     └─ Real error: ❌ Count    │
   │         └─ threshold reached?  │
   │             └─ OPEN circuit    │
   └────────┬───────────────────────┘
            │
            ▼
   ┌────────────────────────────────┐
   │ STEP 9: Update Internal State  │
   │                                │
   │ • Save to pending tracker      │
   │ • Add to recent_orders cache   │
   │ • Record in exposure limiter   │
   │ • Update last_order_time       │
   │ • Log to bot_live.log          │
   └────────┬───────────────────────┘
            │
            ▼
   ┌────────────────────────────────┐
   │ ORDER PLACED SUCCESSFULLY ✅   │
   │                                │
   │ • Exchange has order           │
   │ • Bot tracking internally      │
   │ • WebSocket monitoring fills   │
   │ • Ready for next event         │
   └────────────────────────────────┘
```

### Example Calculation Walkthrough

**Scenario**: Place next LONG BUY after fill

**Given:**
- Last fill: $94,000
- REF_PRICE: $95,000
- GRID_STEP: $1,000
- MODE: long

**Calculation:**
```python
# Step 1: Next grid level
last_fill_price = 94000
grid_step = 1000
mode = 'long'

if mode == 'long':
    # BUY lower
    next_price = last_fill_price - grid_step
    # next_price = 94000 - 1000 = 93000
    
# Step 2: Verify bounds
grid_lower = 90000
grid_upper = 100000

if next_price < grid_lower:
    # 93000 < 90000? No ✅
    pass
    
if next_price > grid_upper:
    # 93000 > 100000? No ✅
    pass

# Step 3: Round to tick size (Delta = $0.50)
tick_size = 0.5
next_price_rounded = round(next_price / tick_size) * tick_size
# 93000 / 0.5 = 186000
# round(186000) = 186000  
# 186000 * 0.5 = 93000 ✅

# Result: Place BUY @ $93,000
```

**TP Calculation** (after fill):
```python
# Fill received at $93,000
entry_price = 93000
tp_offset = 1000
mode = 'long'

if mode == 'long':
    # TP above entry (sell higher)
    tp_price = entry_price + tp_offset
    # tp_price = 93000 + 1000 = 94000
    
# Verify TP within bounds
if tp_price > grid_upper:
    # 94000 > 100000? No ✅
    tp_price = grid_upper  # Cap at upper bound

# Result: Place TP @ $94,000
```

---

## 📊 DECISION MATRIX REFERENCE

### Quick Reference: Bot Actions by Scenario

| Market Event | Bot Checks | Bot Action | Result |
|--------------|-----------|------------|--------|
| **Price drops to grid level** | Capacity, Gatekeeper, Throttle | Place BUY order | New pending order |
| **BUY order partial fill** | Validate fill | Create position + TP | Position opened, TP placed |
| **BUY order complete fill** | Clear pending | Calculate next grid | Next BUY queued/placed |
| **TP order fills** | Find position | Close position | Profit realized, capacity freed |
| **Price gaps >1 step** | Find nearest grid | Place at current level | Skip intermediate levels |
| **Max positions reached** | Capacity check | Skip order | Wait for TP fill |
| **Volatility spike** | IV/RV check | Halt trading | Create .volatility_halt flag |
| **Volatility normalizes** | IV/RV recheck | Resume trading | Remove halt flag |
| **Margin util > threshold** | Gatekeeper | Block BUY orders | Reduce-only mode |
| **Emergency flag exists** | Gatekeeper | Block ALL orders | Manual intervention needed |
| **Duplicate fill notification** | seen_fills cache | Skip processing | Prevent double position |
| **Concurrent fills** | Sequential queue | Process FIFO | Maintain state consistency |
| **Bot restart** | Reconciliation | Adopt orphaned positions | Sync with exchange |
| **Missing TP detected** | Position scan | Place TP order | Ensure all positions protected |
| **Rate limit hit** | Exposure limiter | Queue order | Auto-place when window clears |

---

## 🎯 Next Steps for Production Readiness

### Recommended Testing Sequence:

1. **Paper Trading Simulation** (This document)
   - ✅ Walk through all scenarios mentally
   - ✅ Verify calculations make sense
   - ✅ Understand decision trees

2. **Config Validation**
   - [ ] Review all grid_config.env values
   - [ ] Confirm grid bounds are realistic
   - [ ] Set conservative position limits
   - [ ] Enable all safety features

3. **Dry Run (EXECUTE_ORDERS=False)**
   - [ ] Run bot with real market data
   - [ ] Observe logs for order placement logic
   - [ ] No actual orders placed
   - [ ] Verify behavior matches expectations

4. **Micro-Scale Test (Testnet - when available)**
   - [ ] Minimum position sizes
   - [ ] 1-2 grid levels only
   - [ ] Watch for 24 hours
   - [ ] Verify all scenarios work

5. **Production Launch (Small Scale)**
   - [ ] Start with 1-2% of capital
   - [ ] Monitor closely for 1 week
   - [ ] Gradually increase if stable
   - [ ] Full deployment after confidence built

---

**Would you like me to:**
1. Create more specific scenarios for your trading strategy?
2. Build a simulation script that runs these scenarios with fake data?
3. Generate test cases for specific grid configurations?
4. Deep-dive into any particular decision tree?

This document should serve as your **pre-flight checklist** before production! 🚀
