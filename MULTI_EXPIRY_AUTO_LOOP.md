# Multi-Expiry Auto-Loop Feature Documentation

> **For AI Context**: This document explains the Multi-Expiry Auto-Loop feature in the Options Trading Platform. It allows users to repeat batch orders across multiple option expiries automatically.

---

## Feature Overview

The **Multi-Expiry Auto-Loop** is an execution automation system that:
1. Takes a user-selected set of options positions
2. Groups them by expiry date
3. Executes batch orders for each expiry independently
4. Repeats the execution for N rounds
5. Waits for all orders to fill before proceeding to the next round
6. Persists state across page refreshes for recovery

---

## Architecture

### State Management

```javascript
// Primary state stored in OptionsPanel.js
const [expiryLoopState, setExpiryLoopState] = useState({});

// Structure of expiryLoopState:
{
  "300126": {  // Expiry code (DDMMYY format)
    running: true,           // Is loop currently executing?
    currentRound: 3,         // Current round number (1-indexed)
    totalRounds: 10,         // Total rounds configured
    progress: {              // Per-symbol progress for current round
      "P-BTC-86000-300126": { filled: true, orderId: "123", status: "filled" },
      "C-BTC-90000-300126": { filled: false, orderId: "456", status: "pending" }
    },
    error: null,             // Error message if loop failed
    startTime: 1706500000000, // Unix timestamp when loop started
    completed: false,        // Did loop complete all rounds?
    interrupted: false,      // Was loop interrupted by page refresh?
    interruptedAt: null      // When was it interrupted?
  },
  "270126": {
    // ... another expiry's state
  }
}
```

### Persistence

State is persisted to `localStorage` for recovery:

```javascript
// Key: 'expiryLoopState'
// Saved: On every state change
// Restored: On component mount

// On page refresh, running loops are marked as interrupted:
{
  "300126": {
    running: false,  // Changed from true
    error: "⚠️ Loop interrupted at round 3/10. Page was refreshed.",
    interrupted: true,
    interruptedAt: 1706500500000
  }
}
```

---

## User Flow

### 1. Selection Phase
```
User selects positions in table (checkboxes)
    ↓
System groups selections by expiry code
    ↓
UI shows "Auto-Loop Execution Plan" with per-expiry breakdown
```

### 2. Configuration Phase
```
User sets:
  - Number of rounds (1-1000)
  - Execution mode: "Immediate" (market) or "Smart" (limit first)
  - Order quantities via Batch Qty column
```

### 3. Execution Phase
```
User clicks "▶ Start" for an expiry
    ↓
Loop begins:
    For round 1 to N:
        1. Place all orders for this expiry
        2. Poll order status every 2 seconds
        3. Wait until ALL orders are filled
        4. Play success sound
        5. Wait 1 second
        6. Proceed to next round
    ↓
Loop completes or user clicks "Stop"
```

### 4. Recovery Phase (if page refreshed)
```
Page loads
    ↓
Read expiryLoopState from localStorage
    ↓
For any loop that was "running":
    Mark as interrupted
    Show error banner: "Loop interrupted at round X/Y"
    ↓
User can:
    - Dismiss the warning
    - Check their orders on exchange
    - Restart the loop
```

---

## Code Reference

### Key Functions

| Function | Location | Purpose |
|----------|----------|---------|
| `executePerExpiryLoop(expiryCode)` | OptionsPanel.js ~L2631 | Main loop execution |
| `stopPerExpiryLoop(expiryCode)` | OptionsPanel.js ~L2810 | Stop a running loop |
| `clearExpiryLoopError(expiryCode)` | OptionsPanel.js ~L2853 | Dismiss error state |
| `getOrdersForExpiry(expiryCode)` | OptionsPanel.js ~L2612 | Get orders to execute |
| `selectedExpiriesForLoop` | OptionsPanel.js ~L2577 | Get unique expiries from selection |

### API Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/options/batch_add` | POST | Place multiple orders |
| `/api/options/batch_order_status` | POST | Check order fill status |

### Request/Response Format

**Batch Add Request:**
```json
{
  "orders": [
    { "symbol": "P-BTC-86000-300126", "side": "sell", "size": 5 },
    { "symbol": "C-BTC-90000-300126", "side": "sell", "size": 3 }
  ],
  "order_preference": "maker_first",
  "confirm": true
}
```

**Batch Add Response:**
```json
{
  "success": true,
  "results": [
    { "symbol": "P-BTC-86000-300126", "success": true, "order_id": "123", "execution_type": "limit_placed" },
    { "symbol": "C-BTC-90000-300126", "success": true, "order_id": "456", "execution_type": "market" }
  ],
  "successful": 2,
  "failed": 0
}
```

**Batch Status Request:**
```json
{
  "order_ids": ["123", "456"]
}
```

**Batch Status Response:**
```json
{
  "success": true,
  "orders": [
    { "order_id": "123", "state": "filled", "fill_price": 0.0234 },
    { "order_id": "456", "state": "filled", "fill_price": 0.0156 }
  ]
}
```

---

## UI Components

### Auto-Loop Execution Plan Panel
Shows when `autoLoopEnabled` is true and positions are selected.

```
┌─────────────────────────────────────────────────────────────────┐
│ 📋 Auto-Loop Execution Plan (2 expiries)     [🚀 Start ALL]   │
├─────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 300126    3 orders × 10 rounds                    [▶ Start] │ │
│ └─────────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ 270126    2 orders × 10 rounds                    [▶ Start] │ │
│ └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Running Loop Display
Shows while a loop is executing:

```
┌─────────────────────────────────────────────────────────────────┐
│ 300126    R5/10                              [Stop]            │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ ✅ P86000  ⏳ C90000  ⏳ P88000                              │ │
│ └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Error/Interrupted State
Shows after error or page refresh:

```
┌─────────────────────────────────────────────────────────────────┐
│ 300126    ⚠️ Loop interrupted at round 5/10. Page was refreshed │
│                                                          [✕]   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Execution Modes

### Smart Mode (Default)
1. Place limit orders at mid-price
2. Poll every 2 seconds for fills
3. Wait indefinitely for all fills
4. No timeout - user must stop if stuck

### Immediate Mode
1. Place market orders
2. Orders fill immediately (or fail)
3. Higher fees but guaranteed execution

---

## Error Handling

| Error Type | Handling |
|------------|----------|
| Order placement fails | Stop loop, show error with round number |
| Order cancelled externally | Stop loop, show "Order was cancelled" |
| Order rejected | Stop loop, show rejection reason |
| Network error | Retry 3 times, then stop with error |
| Page refresh | Mark as interrupted, preserve state |
| User clicks Stop | Clean stop after current poll cycle |

---

## Stop Mechanism

Uses a ref-based flag pattern:

```javascript
const expiryStopRefs = useRef({});

// To stop a loop:
const stopPerExpiryLoop = (expiryCode) => {
  expiryStopRefs.current[expiryCode] = true;
  console.log(`[AUTO-LOOP:${expiryCode}] Stop requested`);
};

// Inside the loop:
for (let round = 1; round <= totalRounds; round++) {
  if (expiryStopRefs.current[expiryCode]) {
    // Clean exit
    break;
  }
  // ... execute round
}
```

---

## Symbol Format

Options symbols follow this format:
```
[TYPE]-[UNDERLYING]-[STRIKE]-[EXPIRY]

Examples:
P-BTC-86000-300126  = Put, BTC, $86000 strike, expires 30-Jan-2026
C-BTC-90000-300126  = Call, BTC, $90000 strike, expires 30-Jan-2026
```

Expiry code parsing:
```javascript
// "300126" → 30th day, 01 month, 2026 year
const day = expiryCode.substring(0, 2);   // "30"
const month = expiryCode.substring(2, 4); // "01"
const year = "20" + expiryCode.substring(4, 6); // "2026"
```

---

## Performance Considerations

- **Polling Interval**: 2 seconds between status checks
- **Round Delay**: 1 second between rounds
- **Max Concurrent Loops**: No hard limit, but each loop polls independently
- **State Size**: ~500 bytes per expiry in localStorage

---

## Future Improvements

1. **Condition-Based Start**: Start loop when IV > X%
2. **Time-Based Start**: Schedule loop for specific time
3. **Profit Target Stop**: Stop loop when total profit reaches $X
4. **Dynamic Sizing**: Increase/decrease size based on fills
5. **Cross-Expiry Coordination**: Wait for all expiries before next round

---

## Related Files

| File | Purpose |
|------|---------|
| `OptionsPanel.js` | Main component with loop logic |
| `routes/options/options_control.py` | Backend batch order endpoints |
| `utils/order_handler.py` | Order placement logic |
| `HONEST_BOT_ANALYSIS.md` | Context about bot capabilities |

---

## Glossary

| Term | Definition |
|------|------------|
| **Expiry Code** | 6-digit code (DDMMYY) identifying option expiration |
| **Round** | One complete execution of all orders in the batch |
| **Loop** | Multiple rounds executed sequentially |
| **Per-Expiry Loop** | Independent loop for each expiry date |
| **Interrupted** | Loop was running when page was refreshed |
| **Stop Ref** | React ref used to signal loop termination |
