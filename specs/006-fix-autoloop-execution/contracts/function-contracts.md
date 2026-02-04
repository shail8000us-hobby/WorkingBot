# API Contracts: Auto-Loop Execution

**Date**: February 1, 2026  
**Phase**: Phase 1 - Design

## Internal Function Contracts

These are not HTTP APIs but internal JavaScript function contracts that need to be fixed.

---

### executeOrders() - AdjustmentReviewDialog

**Purpose**: Execute trades through auto-loop with multiple rounds

**Input Parameters**:
```javascript
{
  trades: Trade[],          // Array of trades with quantities
  orderType: string,        // Execution type (market_only, maker_first, etc.)
  executionMode: string,    // "autoloop" or "all_at_once"
  loopRounds: number,       // Number of rounds for autoloop mode
}
```

**Preconditions**:
- `trades.length > 0`
- All trades have `quantity >= 1`
- `loopRounds >= 1` when `executionMode === "autoloop"`
- `orderType` is valid

**Postconditions**:
- If successful: All orders across all rounds are filled
- If failed: Execution stops at first failure, error is set
- State updated: `executing=false`, either `executionSuccess=true` or `executionError != null`

**Side Effects**:
- Updates `executionProgress` state multiple times
- Updates `currentRound` state
- Calls backend API multiple times
- May call `onExecute` callback on success

**Error Handling**:
- Throws error if any round fails to complete
- Sets `executionError` with descriptive message
- Logs all errors to console

---

### executeBatch() - AdjustmentReviewDialog

**Purpose**: Execute a single batch of orders and wait for fills

**Input Parameters**:
```javascript
{
  orders: RoundOrder[],     // Orders for this round
  isSSR: boolean,           // Whether using SSR execution
  ssrMode: string,          // SSR mode if applicable
  roundProgress: Object,    // Progress object to update
}
```

**Preconditions**:
- `orders.length > 0`
- All orders have `size >= 1`
- `roundProgress` is initialized with all symbols

**Postconditions**:
- All orders are either filled or failed
- `roundProgress` is updated with final status
- Returns object mapping symbol → fill status

**Return Value**:
```javascript
{
  [symbol: string]: {
    filled: boolean,
    size: number,
    orderId: string,
    error?: string,
  }
}
```

**Side Effects**:
- Calls backend API (`/api/options/batch_add` or `/api/options/ssr-order`)
- Polls order status via `/api/options/batch_order_status`
- Updates `executionProgress` state
- May take 2-60 seconds to complete

**Error Handling**:
- If API call fails, updates progress with error and returns
- If polling times out, marks as failed
- Logs all API responses

---

### calculatePerRoundOrders() - NEW Function

**Purpose**: Calculate the correct orders for each round maintaining quantity ratios

**Input Parameters**:
```javascript
{
  trades: Trade[],
  currentRound: number,
  totalRounds: number,
  gcd: number,
}
```

**Algorithm**:
```javascript
function calculatePerRoundOrders(trades, currentRound, totalRounds, gcd) {
  return trades.map(trade => {
    // Each round gets the GCD-proportional quantity
    const ratio = trade.quantity / gcd;
    const perRoundQty = Math.round(ratio);
    
    return {
      symbol: trade.symbol,
      side: trade.side,
      size: perRoundQty,
      totalSize: trade.quantity,
      originalQuantity: trade.quantity,
    };
  });
}
```

**Return Value**:
```javascript
RoundOrder[] // One order per trade, with correct size
```

**Preconditions**:
- `gcd > 0`
- All trades have `quantity >= gcd`

**Postconditions**:
- Sum of all orders' `size` = sum of all trades' `quantity` when multiplied by rounds
- Ratios between orders match ratios between original trade quantities

---

## Backend API Contracts (No Changes Needed)

These APIs are already correct; the bug is in how we call them.

---

### POST /api/options/batch_add

**Purpose**: Place multiple orders in a single batch

**Request Body**:
```json
{
  "orders": [
    {
      "symbol": "C-BTC-50000-29JAN26",
      "side": "buy",
      "size": 2
    }
  ],
  "order_preference": "maker_first",
  "confirm": true
}
```

**Response**:
```json
{
  "success": true,
  "results": [
    {
      "symbol": "C-BTC-50000-29JAN26",
      "success": true,
      "order_id": "abc123",
      "execution_type": "limit_filled",
      "fill_price": 1250.50,
      "size": 2,
      "message": "Order filled"
    }
  ]
}
```

**execution_type Values**:
- `"market"` - Filled immediately via market order
- `"limit_filled"` - Limit order filled immediately
- `"limit"` - Limit order placed, pending fill
- `"market_fallback"` - Fell back to market execution

---

### POST /api/options/batch_order_status

**Purpose**: Check status of multiple orders

**Request Body**:
```json
{
  "order_ids": ["abc123", "def456"]
}
```

**Response**:
```json
{
  "success": true,
  "orders": [
    {
      "order_id": "abc123",
      "state": "filled",
      "fill_price": 1250.50,
      "filled_size": 2,
      "remaining_size": 0
    }
  ]
}
```

**state Values**:
- `"filled"` - Order completely filled
- `"open"` - Order still pending
- `"cancelled"` - Order cancelled
- `"rejected"` - Order rejected

---

### POST /api/options/ssr-order

**Purpose**: Place single order using SSR (Smart Sequential Routing)

**Request Body**:
```json
{
  "symbol": "C-BTC-50000-29JAN26",
  "side": "buy",
  "quantity": 2,
  "ssrMode": "standard"
}
```

**Response**:
```json
{
  "success": true,
  "order_id": "ssr_123",
  "message": "SSR order placed"
}
```

**ssrMode Values**:
- `"standard"` - 2 ticks below market
- `"aggressive"` - 3-8% margin
- `"conservative"` - 1-2% margin

---

## Contract Validation

### Test Cases for executeOrders()

**Test 1**: Single round, equal quantities
```javascript
Input: trades=[{qty:2}, {qty:2}], rounds=1
Expected: Round 1 places [2, 2]
```

**Test 2**: Multiple rounds, equal quantities
```javascript
Input: trades=[{qty:3}, {qty:3}], rounds=3
Expected: Round 1 [1,1], Round 2 [1,1], Round 3 [1,1]
```

**Test 3**: Multiple rounds, unequal quantities (BUG CASE)
```javascript
Input: trades=[{qty:1}, {qty:2}], rounds=3
Expected: Round 1 [1,2], Round 2 [1,2], Round 3 [1,2]
Current (Buggy): Round 1 [1,1], Round 2 [1,1], Round 3 [1,1]
```

**Test 4**: Complex ratio
```javascript
Input: trades=[{qty:3}, {qty:1}, {qty:2}], rounds=2
Expected: Round 1 [3,1,2], Round 2 [3,1,2]
```

### Test Cases for executeBatch()

**Test 1**: All orders fill immediately
```javascript
Input: orders=[{symbol:'A', size:1}, {symbol:'B', size:2}]
Expected: Returns {A: {filled:true}, B: {filled:true}}
```

**Test 2**: Some orders pending
```javascript
Input: orders=[{symbol:'A', size:1}, {symbol:'B', size:2}]
Backend: A fills, B pending
Expected: Polls until B fills or timeout
```

**Test 3**: Order placement fails
```javascript
Input: orders=[{symbol:'A', size:100}]
Backend: Margin error
Expected: Returns {A: {filled:false, error:'Insufficient margin'}}
```
