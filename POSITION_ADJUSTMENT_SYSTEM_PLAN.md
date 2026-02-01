# Position Adjustment System - Complete Implementation Plan

**Created:** January 31, 2026  
**Purpose:** Replicate Sensibull-like position adjustment workflow for informed options trading decisions  
**Status:** Implementation Plan

---

## 1. Executive Summary

This system enables traders to:
1. View current open positions with live payoff graph
2. Click "Adjust Position" button to open an options chain selector
3. Add/remove proposed trades while seeing **real-time payoff changes**
4. Preview combined payoff (existing + proposed trades) with metrics comparison
5. Execute via existing autoloop mechanism for Delta Exchange low-liquidity handling

### Key Differentiator from Sensibull
- Uses **autoloop execution** (1 order at a time per round) to handle Delta Exchange's low liquidity
- Uses existing **SSR/Smart/Limit order types** already designed for this exchange
- Shows **before vs after** comparison with institutional-grade metrics

---

## 2. User Flow (Step by Step)

### Step 1: View Current Positions
- User navigates to Options → Open Positions (existing panel)
- Current positions display with payoff graph below
- **NEW**: "Adjust Position" button appears next to existing controls

### Step 2: Open Adjustment Mode
- User clicks "Adjust Position"
- A slide-out panel opens showing:
  - **Left side**: Options chain (strikes, expiries, B/S buttons)
  - **Right side**: Real-time payoff comparison graph

### Step 3: Select New Trades
- User clicks B (Buy) or S (Sell) on any strike
- Qty input appears for each selected strike
- Payoff graph updates **instantly** showing:
  - **Solid line**: Current position payoff
  - **Dashed line**: Proposed combined payoff
- Metrics panel shows before/after comparison:
  - Max Profit, Max Loss, Breakeven, PoP, Greeks

### Step 4: Review & Confirm
- User clicks "Review Changes"
- Summary dialog shows:
  - Current positions
  - Proposed new trades
  - Net premium (credit/debit)
  - Combined metrics

### Step 5: Execute
- User clicks "Execute All"
- System uses existing `batch_add` API with autoloop
- Progress indicator shows fill status per order
- Confirmation on completion

---

## 3. Architecture Overview

### 3.1 New Files Structure (Minimal Invasion)

```
webui/frontend/src/components/positionAdjustment/
├── index.js                          # Exports
├── PositionAdjustmentPanel.js        # Main slide-out panel container
├── AdjustmentChainTable.js           # Options chain with B/S selectors
├── AdjustmentPayoffChart.js          # Dual-line payoff comparison
├── AdjustmentMetricsPanel.js         # Before/After metrics comparison
├── ProposedTradesTable.js            # List of selected new trades
├── AdjustmentReviewDialog.js         # Final review before execution
├── AdjustmentExecutionProgress.js    # Real-time fill progress
├── hooks/
│   └── usePayoffCalculation.js       # Payoff calculation hook
└── utils/
    └── adjustmentPayoffEngine.js     # Payoff calculation engine

webui/backend/routes/
└── position_adjustment.py            # API for adjustment calculations (optional)
```

### 3.2 Integration Points (Minimal Changes)

| Existing File | Change Required |
|---------------|-----------------|
| `OptionsPanel.js` | Add "Adjust Position" button + state for adjustment mode |
| No other files modified | ✅ All new code in separate directory |

### 3.3 Reused Components & Utilities

| Existing Resource | Purpose |
|-------------------|---------|
| `probabilityCalc.js` | PoP calculations |
| `constants.js` | Contract multipliers, risk-free rate |
| `chainAPI.js` | Fetch options chain data |
| `batch_add` API | Execute multiple orders |
| `autoloop` mechanism | Handle low liquidity |
| `OptionsPayoffDiagram.js` | Reference for payoff chart (reuse logic) |
| Dark theme styles | Match existing UI |

---

## 4. Component Specifications

### 4.1 PositionAdjustmentPanel (Main Container)

**Location:** `positionAdjustment/PositionAdjustmentPanel.js`

**Props:**
```javascript
{
  open: boolean,           // Panel visibility
  onClose: () => void,     // Close handler
  currentPositions: [],    // Existing options positions from OptionsPanel
  spotPrice: number,       // Current underlying price
  underlying: string,      // 'BTC' or 'ETH'
  onExecuteComplete: () => void  // Refresh callback
}
```

**State:**
```javascript
{
  selectedExpiry: string,       // Current expiry filter
  proposedTrades: [],           // User-selected new trades
  chainData: {},                // Options chain data
  showReviewDialog: boolean,    // Review dialog visibility
  executing: boolean,           // Execution in progress
  executionProgress: {},        // Per-order fill status
}
```

**Layout:**
```
┌─────────────────────────────────────────────────────────────┐
│ Position Adjustment                              [X Close]   │
├─────────────────────────────────────────────────────────────┤
│ Expiry: [Dropdown]  Clear All  Review (3 trades)            │
├─────────────────────────────┬───────────────────────────────┤
│                             │                               │
│   OPTIONS CHAIN TABLE       │   PAYOFF COMPARISON CHART     │
│   (AdjustmentChainTable)    │   (AdjustmentPayoffChart)     │
│                             │                               │
│   Strike | Call B/S | Put B/S│   ── Current (solid)         │
│   80000  |  [B] [S] | [B] [S]│   -- Proposed (dashed)        │
│   81000  |  [B] [S] | [B] [S]│                               │
│   82000  |  [B] [S] | [B] [S]│   [Before] → [After]         │
│   ...                        │   Max P: $X → $Y             │
│                             │   Max L: $X → $Y             │
├─────────────────────────────┴───────────────────────────────┤
│ PROPOSED TRADES (ProposedTradesTable)                       │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Strike  │ Type │ Side │  Qty  │ Premium │    [Delete]  │ │
│ │ 81000   │ Call │ Buy  │  10   │ $45.50  │       [X]    │ │
│ │ 83000   │ Put  │ Sell │  10   │ $28.30  │       [X]    │ │
│ └─────────────────────────────────────────────────────────┘ │
│ Net Premium: +$170 (Credit)                [Review & Execute] │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 AdjustmentChainTable

**Purpose:** Display options chain with quick B/S selection buttons

**Features:**
- Strike prices centered
- Call side on left, Put side on right
- B (Buy) / S (Sell) buttons for each option
- Green highlight for Buy, Red for Sell
- Qty input appears after selection
- LTP, IV, OI data displayed
- Current spot price highlighted (ATM row)

**Data Source:** Uses existing `chainAPI.getChainData()`

### 4.3 AdjustmentPayoffChart

**Purpose:** Real-time dual-line payoff comparison

**Features:**
- **Solid green/red line**: Current positions payoff at expiry
- **Dashed blue line**: Proposed combined payoff at expiry
- Vertical dotted line at current spot
- Shaded profit/loss zones
- Breakeven markers for both scenarios
- Interactive tooltip showing P&L at any price

**Technical:**
- Reuse calculation logic from `OptionsPayoffDiagram.js`
- Use `recharts` (already in project)
- Calculate payoff for 100 price points

### 4.4 AdjustmentMetricsPanel

**Purpose:** Side-by-side comparison of key metrics

**Layout:**
```
┌─────────────────┬────────────────┬────────────────┐
│ Metric          │ Current        │ After Adjust   │
├─────────────────┼────────────────┼────────────────┤
│ Max Profit      │ $1,250         │ $2,100 (+68%)  │
│ Max Loss        │ -$3,500        │ -$2,800 (-20%) │
│ Breakeven       │ $81,234        │ $80,500, 84,200│
│ PoP             │ 45%            │ 62% ▲          │
│ Net Delta       │ -0.35          │ -0.12          │
│ Net Theta       │ +$45/day       │ +$72/day       │
│ Net Vega        │ -$120          │ -$85           │
└─────────────────┴────────────────┴────────────────┘
```

### 4.5 ProposedTradesTable

**Purpose:** List of user-selected trades to add

**Features:**
- Strike, Type (Call/Put), Side (Buy/Sell), Qty, Premium
- Delete button per row
- Edit qty inline
- Net premium calculation (credit/debit)

### 4.6 AdjustmentReviewDialog

**Purpose:** Final confirmation before execution

**Content:**
- Summary of all proposed trades
- Total premium (pay/receive)
- Before/After metrics comparison
- Order execution settings (order type, rounds)
- Execute button with progress

### 4.7 AdjustmentExecutionProgress

**Purpose:** Show real-time execution status

**Features:**
- List of orders with status indicators
- ✓ Filled / ⏳ Pending / ❌ Failed
- Fill price display
- Progress bar for overall completion
- Cancel button to stop remaining orders

---

## 5. Payoff Calculation Engine

### 5.1 Core Algorithm

```javascript
// adjustmentPayoffEngine.js

/**
 * Calculate combined payoff for existing + proposed positions
 * 
 * @param {Array} currentPositions - Existing positions from API
 * @param {Array} proposedTrades - User-selected new trades
 * @param {number} spotPrice - Current underlying price
 * @param {number} rangePercent - Price range for chart (±%)
 * @returns {Object} { chartData, metrics }
 */
export function calculateCombinedPayoff(currentPositions, proposedTrades, spotPrice, rangePercent = 15) {
  const priceRange = generatePriceRange(spotPrice, rangePercent);
  
  // Calculate payoff for current positions only
  const currentPayoff = priceRange.map(price => ({
    price,
    pnl: calculatePositionsPayoff(currentPositions, price)
  }));
  
  // Calculate payoff for current + proposed
  const combinedPositions = [...currentPositions, ...formatProposedAsPositions(proposedTrades)];
  const combinedPayoff = priceRange.map(price => ({
    price,
    pnl: calculatePositionsPayoff(combinedPositions, price)
  }));
  
  // Calculate metrics for both scenarios
  const currentMetrics = calculateMetrics(currentPayoff, currentPositions, spotPrice);
  const combinedMetrics = calculateMetrics(combinedPayoff, combinedPositions, spotPrice);
  
  return {
    chartData: priceRange.map((price, i) => ({
      price,
      current: currentPayoff[i].pnl,
      combined: combinedPayoff[i].pnl
    })),
    currentMetrics,
    combinedMetrics
  };
}

/**
 * Calculate single position payoff at a given price (at expiry)
 */
function calculateSinglePositionPayoff(position, priceAtExpiry) {
  const { strike, type, size, entryPrice } = position;
  const isCall = type === 'call' || type === 'C';
  const isLong = size > 0;
  
  // Intrinsic value at expiry
  let intrinsic = 0;
  if (isCall) {
    intrinsic = Math.max(0, priceAtExpiry - strike);
  } else {
    intrinsic = Math.max(0, strike - priceAtExpiry);
  }
  
  // P&L = (Intrinsic - Premium) * |size| * direction * contractMultiplier
  const direction = isLong ? 1 : -1;
  const premium = Math.abs(entryPrice);
  const pnl = (intrinsic * direction - premium * direction) * Math.abs(size) * 0.001; // BTC contract = 0.001
  
  return pnl;
}
```

### 5.2 Metrics Calculation

```javascript
function calculateMetrics(payoffData, positions, spotPrice) {
  const pnls = payoffData.map(d => d.pnl);
  
  return {
    maxProfit: Math.max(...pnls),
    maxLoss: Math.min(...pnls),
    breakevens: findBreakevens(payoffData),
    pop: calculateStrategyPoP(positions, spotPrice),
    netDelta: calculateNetGreek(positions, 'delta'),
    netTheta: calculateNetGreek(positions, 'theta'),
    netVega: calculateNetGreek(positions, 'vega'),
    netPremium: calculateNetPremium(positions),
  };
}

function findBreakevens(payoffData) {
  const breakevens = [];
  for (let i = 1; i < payoffData.length; i++) {
    const prev = payoffData[i - 1].pnl;
    const curr = payoffData[i].pnl;
    if ((prev <= 0 && curr >= 0) || (prev >= 0 && curr <= 0)) {
      // Linear interpolation for precise breakeven
      const ratio = Math.abs(prev) / (Math.abs(prev) + Math.abs(curr));
      const breakeven = payoffData[i - 1].price + ratio * (payoffData[i].price - payoffData[i - 1].price);
      breakevens.push(breakeven);
    }
  }
  return breakevens;
}
```

---

## 6. API Integration

### 6.1 Options Chain Data

Uses existing endpoint:
```
GET /api/options-chain/data?underlying=BTC&expiry=01022026
```

### 6.2 Order Execution

Uses existing batch endpoint with autoloop:
```javascript
// Execute via batch_add (same as current autoloop)
POST /api/options/batch_add
{
  orders: [
    { symbol: "C-BTC-82000-010226", size: 10, side: "buy" },
    { symbol: "P-BTC-80000-010226", size: 10, side: "sell" }
  ],
  order_preference: "maker_first",  // or "ssr", "market_only"
  confirm: true
}
```

### 6.3 Order Status Polling

Uses existing endpoint:
```
POST /api/options/batch_order_status
{ order_ids: ["123", "456"] }
```

### 6.4 (Optional) Backend Payoff API

If frontend calculation becomes slow, add:
```
POST /api/position-adjustment/calculate-payoff
{
  current_positions: [...],
  proposed_trades: [...],
  spot_price: 81234,
  range_percent: 15
}
```

---

## 7. Integration with OptionsPanel

### 7.1 Changes to OptionsPanel.js

**Minimal changes required:**

```javascript
// At top: Import new component
import PositionAdjustmentPanel from '../positionAdjustment';

// In state section: Add adjustment mode state
const [adjustmentPanelOpen, setAdjustmentPanelOpen] = useState(false);

// In render: Add button (near existing controls)
<Button 
  variant="outlined" 
  color="primary"
  startIcon={<TuneIcon />}
  onClick={() => setAdjustmentPanelOpen(true)}
  sx={{ ml: 1 }}
>
  Adjust Position
</Button>

// At end of component: Add panel
<PositionAdjustmentPanel
  open={adjustmentPanelOpen}
  onClose={() => setAdjustmentPanelOpen(false)}
  currentPositions={sortedPositions}
  spotPrice={btcPrice || ethPrice}
  underlying={/* derive from positions */}
  onExecuteComplete={() => {
    fetchPositions();
    setAdjustmentPanelOpen(false);
  }}
/>
```

### 7.2 No Other Changes Required

- Uses existing chain API
- Uses existing batch execution
- Uses existing autoloop logic (can be called via API)
- Uses existing styling/theme

---

## 8. Styling Guidelines

### 8.1 Dark Theme Consistency

Match existing dark theme:
```javascript
const styles = {
  panel: {
    backgroundColor: '#1a1a2e',
    borderRadius: '12px',
    border: '1px solid rgba(255, 255, 255, 0.1)',
  },
  buyButton: {
    backgroundColor: '#2e7d32',  // Green
    color: '#fff',
  },
  sellButton: {
    backgroundColor: '#c62828',  // Red  
    color: '#fff',
  },
  profitColor: '#4caf50',
  lossColor: '#f44336',
  chartLine: {
    current: '#4caf50',
    proposed: '#2196f3',  // Blue dashed
  },
};
```

### 8.2 Responsive Design

- Panel slides from right on desktop
- Full-screen modal on mobile
- Chain table scrollable
- Chart maintains aspect ratio

---

## 9. Implementation Phases

### Phase 1: Core Components (2-3 hours)
1. Create folder structure
2. PositionAdjustmentPanel skeleton
3. AdjustmentChainTable with B/S buttons
4. Basic state management

### Phase 2: Payoff Engine (1-2 hours)
1. adjustmentPayoffEngine.js
2. AdjustmentPayoffChart with dual lines
3. Integration with chain selection

### Phase 3: Metrics & Review (1 hour)
1. AdjustmentMetricsPanel
2. ProposedTradesTable
3. AdjustmentReviewDialog

### Phase 4: Execution (1 hour)
1. Integration with batch_add API
2. AdjustmentExecutionProgress
3. Autoloop support

### Phase 5: Polish (30 min)
1. Error handling
2. Loading states
3. Animations
4. Testing

**Total Estimated Time: 5-7 hours**

---

## 10. Risk Mitigation

### 10.1 Safety Features

| Risk | Mitigation |
|------|------------|
| Accidental execution | Confirm dialog required |
| Order size errors | Max size validation |
| Guardian stop | Check before execution |
| Network failure | Retry mechanism |
| Partial fills | Clear progress display |

### 10.2 Fallback Behavior

- If chain data unavailable: Show error, allow retry
- If payoff calc fails: Show current positions only
- If execution fails: Show which orders failed, allow retry
- If panel crashes: ErrorBoundary isolates from OptionsPanel

---

## 11. Testing Checklist

### 11.1 Functional Tests

- [ ] Chain loads for all available expiries
- [ ] B/S selection updates proposed trades
- [ ] Qty changes reflect in calculations
- [ ] Payoff chart shows both lines
- [ ] Metrics calculate correctly
- [ ] Review dialog shows all data
- [ ] Execution uses autoloop
- [ ] Progress updates in real-time
- [ ] Completion refreshes positions

### 11.2 Edge Cases

- [ ] Empty positions (no current positions)
- [ ] Single expiry
- [ ] Large position sizes
- [ ] Near-expiry options
- [ ] Mixed BTC/ETH (filter by underlying)
- [ ] Network timeout during execution

---

## 12. Future Enhancements

1. **Strategy Templates**: Quick adjustments like "Roll Up", "Add Hedge", "Close Half"
2. **P&L Scenarios**: Show payoff at multiple target dates
3. **IV Change Impact**: What-if IV changes by ±5%
4. **Position Cloning**: Copy existing position to new expiry
5. **Margin Impact**: Show margin change before execution
6. **Smart Suggestions**: AI-recommended adjustments based on market conditions

---

## 13. File Creation Order

1. `index.js` - Exports
2. `utils/adjustmentPayoffEngine.js` - Core calculation engine
3. `hooks/usePayoffCalculation.js` - React hook wrapper
4. `AdjustmentChainTable.js` - Options chain display
5. `ProposedTradesTable.js` - Selected trades list
6. `AdjustmentPayoffChart.js` - Dual-line chart
7. `AdjustmentMetricsPanel.js` - Before/after comparison
8. `AdjustmentReviewDialog.js` - Confirmation dialog
9. `AdjustmentExecutionProgress.js` - Execution status
10. `PositionAdjustmentPanel.js` - Main container
11. **Modify** `OptionsPanel.js` - Add button + panel import

---

**End of Plan Document**

Ready to proceed with implementation.
