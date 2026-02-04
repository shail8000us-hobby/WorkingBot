# Data Model: Auto-Loop Execution

**Date**: February 1, 2026  
**Phase**: Phase 1 - Design

## Entities

### Trade (Input)

Represents a single trade to be executed through auto-loop.

**Fields**:
- `symbol`: string - Option symbol (e.g., "C-BTC-50000-29JAN26")
- `side`: string - "buy" or "sell"
- `type`: string - "call" or "put"
- `strike`: number - Strike price
- `quantity`: number - **Total quantity across all rounds** (this is the key field causing bugs)
- `ltp`: number - Last traded price
- `premium`: number - Premium amount
- `expiry`: string - Expiry date
- `spotPrice`: number - Current spot price
- `delta`: number - Option delta
- `theta`: number - Option theta
- `vega`: number - Option vega
- `iv`: number - Implied volatility

**Validation Rules**:
- `quantity` must be >= 1
- `symbol` must match pattern `[CP]-[A-Z]+-\\d+-\\d+`
- `side` must be one of ["buy", "sell"]

**State Transitions**: Input only, no state changes

---

### RoundOrder (Computed)

Represents the orders to execute in a single round.

**Fields**:
- `symbol`: string - From Trade
- `side`: string - From Trade  
- `size`: number - **Quantity for THIS round** (calculated, not user input)
- `totalSize`: number - Total quantity from Trade (for tracking)
- `originalQuantity`: number - Original quantity from Trade (preserved for ratio calculation)

**Validation Rules**:
- `size` must be >= 1 (if 0, filter out the order)
- `size` <= `totalSize`
- Sum of `size` across all rounds must equal `totalSize`

**Relationships**:
- Derived from Trade
- Multiple RoundOrders can reference the same Trade (one per round)

---

### ExecutionProgress (State Tracking)

Tracks the status of individual orders during execution.

**Fields**:
- `symbol`: string - Key for the map
- `status`: string - "placing" | "pending" | "monitoring" | "filled" | "failed" | "cancelled"
- `filled`: boolean - Whether order is fully filled
- `orderId`: string - Backend order ID (if available)
- `size`: number - Quantity being tracked
- `totalFilled`: number - Cumulative quantity filled across rounds (optional)
- `fillPrice`: number - Actual fill price (optional)
- `error`: string - Error message if failed (optional)

**Validation Rules**:
- `status` must be one of the defined values
- If `status === "filled"`, then `filled === true`
- If `status === "failed"`, then `error` must be set

**State Transitions**:
```
placing → pending → filled
        ↓         ↓
        failed    cancelled
        
placing → filled (for market orders)
```

---

### AutoLoopState (Component State)

Top-level state for the auto-loop execution.

**Fields**:
- `executing`: boolean - Whether auto-loop is running
- `currentRound`: number - Current round number (1-indexed)
- `loopRounds`: number - Total number of rounds configured
- `executionMode`: string - "autoloop" | "all_at_once"
- `orderType`: string - "market_only" | "maker_first" | etc.
- `executionProgress`: Map<string, ExecutionProgress> - Status per symbol
- `executionSuccess`: boolean - Whether all rounds completed successfully
- `executionError`: string | null - Error message if failed
- `stopExecutionRef`: React.RefObject<boolean> - User-initiated stop signal

**Validation Rules**:
- `currentRound` <= `loopRounds`
- If `executing === true`, then `executionError === null`
- If `executionSuccess === true`, then `executing === false`

---

## Key Calculations

### Per-Round Quantity Calculation

**Current (Buggy)**:
```javascript
size = Math.round(trade.quantity / totalRounds)
```

**Problem**: For quantity=1, rounds=3 → size=0 (loses quantity)

**Fixed**:
```javascript
// Each round executes the GCD quantity
size = (trade.quantity / gcd) * 1  // Where gcd is computed once for all trades
```

**Example**:
- Trades: [{ qty: 1 }, { qty: 2 }]
- GCD: 1
- Round 1: [1, 2]
- Round 2: [1, 2]
- Round 3: [1, 2]
- Total: [3, 6] ✅ Maintains 1:2 ratio

---

### Fill Confirmation Check

**Logic**:
```javascript
// After executeBatch completes
const allFilled = Object.values(executionProgress)
  .every(p => p.filled === true);

if (!allFilled) {
  throw new Error(`Round ${currentRound} incomplete: not all orders filled`);
}

// Only proceed to next round if allFilled === true
```

---

## Data Flow

```
User Configuration
  ↓
[Trade[], rounds: number] → Calculate GCD
  ↓
For each round:
  ↓
  Generate RoundOrder[] (each has size = GCD * multiplier)
  ↓
  Execute batch (place all orders)
  ↓
  Poll for fills (update ExecutionProgress)
  ↓
  Verify all filled
  ↓
  If all filled && more rounds remaining → next round
  If any failed || not filled → STOP with error
  ↓
Execution Complete
```

---

## State Management

### useState Variables

```javascript
const [executing, setExecuting] = useState(false);
const [currentRound, setCurrentRound] = useState(0);
const [loopRounds, setLoopRounds] = useState(1);
const [executionMode, setExecutionMode] = useState('autoloop');
const [orderType, setOrderType] = useState('maker_first');
const [executionProgress, setExecutionProgress] = useState({});
const [executionSuccess, setExecutionSuccess] = useState(false);
const [executionError, setExecutionError] = useState(null);
const [confirmed, setConfirmed] = useState(false);

const stopExecutionRef = useRef(false);
```

### Key State Updates

1. **Start Execution**: Set `executing=true`, reset progress
2. **Round Start**: Increment `currentRound`, reset progress for round
3. **Order Placed**: Update progress[symbol] to "pending"
4. **Order Filled**: Update progress[symbol] to "filled"
5. **Round Complete**: Verify all filled before proceeding
6. **Execution Complete**: Set `executing=false`, `executionSuccess=true`
7. **Execution Failed**: Set `executing=false`, `executionError=message`

---

## Error Scenarios

### Scenario 1: Order Placement Fails
- **Detection**: API returns `success: false`
- **Action**: Set progress[symbol].status = "failed", stop auto-loop
- **User Impact**: Clear error message, can retry

### Scenario 2: Order Stuck Pending
- **Detection**: Polling timeout (30 polls, 60 seconds)
- **Action**: Throw error, stop auto-loop
- **User Impact**: Can manually check order status, cancel if needed

### Scenario 3: Insufficient Margin
- **Detection**: API returns margin error
- **Action**: Stop auto-loop immediately, show error
- **User Impact**: Must free up margin before retrying

### Scenario 4: User Clicks Stop
- **Detection**: `stopExecutionRef.current === true`
- **Action**: Break loop after current round completes
- **User Impact**: Partial execution, must track what was filled
