# Research: Auto-Loop Execution Bugs

**Date**: February 1, 2026  
**Phase**: Phase 0 - Problem Analysis & Research

## Problem Analysis

### Bug 1: Incorrect Quantity Ratios

**Current Behavior**: When executing auto-loop with trades that have different quantities (e.g., 1 lot of strike A, 2 lots of strike B), the system executes 1 lot of each strike instead of maintaining the ratio.

**Root Cause Location**: 
- File: `webui/frontend/src/components/positionAdjustment/AdjustmentReviewDialog.js`
- Lines: ~238-243

```javascript
const perLoopOrders = trades.map((trade) => ({
  symbol: trade.symbol,
  side: trade.side,
  size: Math.round((trade.quantity || 1) / actualLoops), // BUG: Division results in 0 for smaller quantities
  totalSize: trade.quantity || 1,
}));
```

**Problem**: When `actualLoops` is greater than `trade.quantity`, the division results in a fractional value less than 1, which gets rounded to 0 or 1. This loses the ratio information.

**Example**:
- Trade A: 1 lot, 3 rounds → `1/3 = 0.33` → rounds to `0`
- Trade B: 2 lots, 3 rounds → `2/3 = 0.67` → rounds to `1`
- Result: Both execute 1 lot per round (should be 1 and 2 in the first round, 0 and 0 in others)

**Similar Issue in OptionsPanel.js**: The `executeAutoLoop` function has the same logic for calculating batch orders but it's less clear if it has the exact same bug. Need to verify.

---

### Bug 2: Round Starts Before Previous Completes

**Current Behavior**: Round 2 starts placing orders before round 1 orders are confirmed as filled.

**Root Cause Location**: 
- File: `webui/frontend/src/components/positionAdjustment/AdjustmentReviewDialog.js`
- Lines: ~297-302
- File: `webui/frontend/src/components/options/OptionsPanel.js`
- Lines: ~2530-2540

**Problem**: The code waits 500ms between loops unconditionally:

```javascript
if (loop < actualLoops && !stopExecutionRef.current) {
  console.log(`[Execution] Loop ${loop} complete, waiting 500ms before next...`);
  await new Promise(resolve => setTimeout(resolve, 500));
}
```

This wait happens AFTER the `executeBatch` returns, but `executeBatch` may return before all orders are actually filled if there are pending limit orders. The polling logic inside `executeBatch` has a maximum poll count (30 polls = 60 seconds), but if orders are still pending after that, it just gives up and returns.

**Flow Issue**:
1. Round 1 places orders
2. Some orders fill immediately (market)
3. Some orders are pending (limit)
4. Polling starts but may timeout
5. `executeBatch` returns (even if some pending)
6. 500ms wait
7. Round 2 starts ← **BUG**: Should not start if round 1 incomplete

---

## Research Findings

### Decision: How to Handle Quantity Ratios

**Decision**: Use GCD (Greatest Common Divisor) to preserve ratios

**Rationale**: 
- The codebase already has GCD calculation in `AdjustmentReviewDialog.js` (line ~137)
- GCD allows representing ratios like 1:2 or 3:1:2 accurately
- Each round should execute quantities in the GCD ratio, not divided quantities

**Implementation**:
- For trades with quantities [1, 2], GCD = 1
- Round 1: place [1, 2]
- Round 2: place [1, 2]
- Round 3: place [1, 2]
- Total: [3, 6] which maintains the 1:2 ratio

**Alternative Considered**: Dynamic per-round sizing where first rounds get more
- **Rejected because**: Creates uneven execution that may not match user intent for strategies that require exact ratios

---

### Decision: When to Start Next Round

**Decision**: Start next round only after ALL orders from previous round are confirmed filled

**Rationale**:
- Prevents position doubling
- Prevents margin errors
- Provides clear execution state
- Matches user expectation

**Implementation**:
- After `executeBatch` places orders, check all orders are filled
- If any order is still pending after polling timeout, STOP the auto-loop with error
- Only proceed to next round if `allFilled === true`
- Add explicit check: `if (!allFilled) throw new Error('Round X incomplete')`

**Alternative Considered**: Allow partial fills and adjust next round quantities
- **Rejected because**: Too complex, creates confusing state, hard to debug

---

### Decision: Polling Strategy for Fills

**Decision**: Poll order status every 2 seconds for up to 60 seconds (30 polls)

**Rationale**:
- Current implementation already uses 2-second polling
- 60 seconds is reasonable for limit orders to fill
- Provides feedback to user every 2 seconds

**Implementation**:
- Keep existing polling logic but add stricter validation
- If polling times out, throw error and stop auto-loop
- Log each poll attempt for debugging

**Alternative Considered**: Websocket-based real-time updates
- **Rejected because**: Would require backend changes, out of scope for this bug fix

---

### Decision: Progress Tracking UI

**Decision**: Show per-symbol status in real-time during execution

**Rationale**:
- Existing code has `executionProgress` state with per-symbol tracking
- UI already renders progress in the dialog
- Just need to ensure updates happen correctly

**Implementation**:
- Preserve existing progress structure: `{ [symbol]: { status, filled, size, fillPrice } }`
- Update progress after each API call and poll
- Ensure `setExecutionProgress` is called with complete state

**Alternative Considered**: Add detailed log viewer in UI
- **Rejected because**: Console logging is sufficient for debugging, UI should stay simple

---

## Technology Stack Confirmation

### Frontend
- **Framework**: React 17+
- **State Management**: useState, useRef (no Redux needed)
- **UI Library**: Material-UI
- **HTTP Client**: axios via `apiShim.js`

### Backend API (No Changes Needed)
- **Endpoints Used**:
  - `POST /api/options/batch_add` - Place multiple orders
  - `POST /api/options/batch_order_status` - Check order status
  - `POST /api/options/ssr-order` - SSR execution mode
  
### Testing Approach
- **Manual Testing**: Execute auto-loop scenarios with different quantity ratios
- **Test Cases**:
  1. 1:1 ratio (baseline)
  2. 1:2 ratio (most common issue)
  3. 3:1:2 ratio (complex multi-strike)
  4. 1:1:1 with 5 rounds (stress test)
- **Monitoring**: Browser console logs, network tab for API calls

---

## Open Questions Resolved

### Q: Should we change the GCD calculation logic?
**A**: No, the existing GCD calculation is correct. The bug is in how we use it.

### Q: Do we need to handle partial fills?
**A**: No, out of scope. Current API either fills completely or not at all.

### Q: Should we add execution history/audit log?
**A**: No, keep it simple. Console logs are sufficient for debugging.

### Q: What if orders fill at different prices across rounds?
**A**: This is expected behavior. Each round is independent. User should monitor average fill price.

---

## References

- Existing code: `webui/frontend/src/components/positionAdjustment/AdjustmentReviewDialog.js`
- Existing code: `webui/frontend/src/components/options/OptionsPanel.js`
- API documentation: Backend handles batch orders and status polling
