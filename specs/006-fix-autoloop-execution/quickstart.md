# Quick Start: Fix Auto-Loop Execution Bugs

**Date**: February 1, 2026  
**Phase**: Phase 1 - Design

## Overview

This guide explains how to fix the two critical bugs in auto-loop execution:
1. **Quantity Ratio Bug**: System executes 1 lot of each strike instead of maintaining configured ratios
2. **Round Timing Bug**: Round 2 starts before round 1 orders are confirmed filled

---

## Files to Modify

### Primary Files
1. **`webui/frontend/src/components/positionAdjustment/AdjustmentReviewDialog.js`**
   - Lines to modify: ~238-243 (quantity calculation), ~297-302 (round timing)
   - Functions affected: `executeOrders()`, `executeBatch()`

2. **`webui/frontend/src/components/options/OptionsPanel.js`**
   - Lines to modify: ~2389-2550 (executeAutoLoop function)
   - Similar fixes needed

---

## Fix #1: Quantity Ratio Preservation

### Current (Buggy) Code

```javascript
// AdjustmentReviewDialog.js, line ~238
const perLoopOrders = trades.map((trade) => ({
  symbol: trade.symbol,
  side: trade.side,
  size: Math.round((trade.quantity || 1) / actualLoops), // ❌ BUG
  totalSize: trade.quantity || 1,
}));
```

**Problem**: Division by rounds loses ratio information when quantities are small.

### Fixed Code

```javascript
// Calculate GCD once (already exists in code around line 137)
const tradesGCD = calculateGCD(trades.map(t => t.quantity || 1));

// Fix the per-loop calculation
const perLoopOrders = trades.map((trade) => {
  // Each round executes the same ratio
  const ratio = (trade.quantity || 1) / tradesGCD;
  const perRoundQty = Math.round(ratio * tradesGCD); // ✅ Preserves ratio
  
  return {
    symbol: trade.symbol,
    side: trade.side,
    size: perRoundQty,
    totalSize: trade.quantity || 1,
    originalQuantity: trade.quantity || 1,
  };
});
```

**Explanation**: 
- If trades are [1, 2], GCD is 1
- Ratio for trade 1: 1/1 = 1
- Ratio for trade 2: 2/1 = 2
- Each round places [1, 2] maintaining the 1:2 ratio ✅

---

## Fix #2: Wait for Round Completion

### Current (Buggy) Code

```javascript
// AdjustmentReviewDialog.js, line ~297
const loopResult = await executeBatch(loopOrders, isSSR, ssrMode, roundProgress);

// Update total filled
Object.entries(loopResult).forEach(([symbol, result]) => {
  if (result.filled) {
    totalFilled[symbol] = (totalFilled[symbol] || 0) + result.size;
  }
});

// Wait before next loop
if (loop < actualLoops && !stopExecutionRef.current) {
  console.log(`[Execution] Loop ${loop} complete, waiting 500ms before next...`);
  await new Promise(resolve => setTimeout(resolve, 500)); // ❌ Doesn't verify all filled
}
```

**Problem**: Code waits 500ms but doesn't verify all orders are actually filled.

### Fixed Code

```javascript
const loopResult = await executeBatch(loopOrders, isSSR, ssrMode, roundProgress);

// ✅ VERIFY ALL FILLED before proceeding
const allFilled = Object.values(loopResult).every(r => r.filled === true);

if (!allFilled) {
  const unfilledSymbols = Object.entries(loopResult)
    .filter(([sym, res]) => !res.filled)
    .map(([sym]) => sym);
  
  throw new Error(
    `Round ${loop} incomplete: Orders not filled for ${unfilledSymbols.join(', ')}`
  );
}

console.log(`[Execution] ✅ Round ${loop} complete: All orders filled`);

// Update total filled
Object.entries(loopResult).forEach(([symbol, result]) => {
  if (result.filled) {
    totalFilled[symbol] = (totalFilled[symbol] || 0) + result.size;
  }
});

// Wait before next loop (only if all filled)
if (loop < actualLoops && !stopExecutionRef.current) {
  console.log(`[Execution] Waiting 500ms before round ${loop + 1}...`);
  await new Promise(resolve => setTimeout(resolve, 500));
}
```

**Explanation**: 
- After `executeBatch` returns, verify every order is filled
- If ANY order is not filled, throw error and stop
- Only proceed to next round if `allFilled === true` ✅

---

## Fix #3: Improve executeBatch() Validation

### Current Code Issue

The `executeBatch` function may return before all orders are filled if polling times out.

### Add Explicit Timeout Check

```javascript
// In executeBatch(), after polling loop (line ~450)
if (pendingOrders.length > 0) {
  console.log(`[Execution] Polling for ${pendingOrders.length} pending orders...`);
  // ... existing polling code ...
  
  // ✅ ADD THIS CHECK
  if (pollCount >= maxPolls && !allFilled) {
    console.error(`[Execution] Polling timeout: ${maxPolls * 2}s elapsed`);
    // Mark unfilled orders as failed
    Object.keys(roundProgress).forEach(symbol => {
      if (roundProgress[symbol].status === 'pending') {
        roundProgress[symbol].status = 'failed';
        roundProgress[symbol].error = 'Polling timeout: order did not fill';
        results[symbol] = { ...results[symbol], filled: false, error: 'Timeout' };
      }
    });
    setExecutionProgress({ ...roundProgress });
  }
}
```

---

## Testing Checklist

### Manual Test Scenarios

**Test 1: Equal Quantities**
```
Config: 2 lots of strike A, 2 lots of strike B, 2 rounds
Expected: Round 1 [2, 2], Round 2 [2, 2]
Verify: Console logs show correct quantities, UI shows 2 rounds completed
```

**Test 2: Unequal Quantities (BUG CASE)**
```
Config: 1 lot of strike A, 2 lots of strike B, 3 rounds
Expected: Round 1 [1, 2], Round 2 [1, 2], Round 3 [1, 2]
Verify: Total filled = 3A + 6B, maintains 1:2 ratio
```

**Test 3: Complex Ratio**
```
Config: 3 lots A, 1 lot B, 2 lots C, 2 rounds
Expected: Round 1 [3, 1, 2], Round 2 [3, 1, 2]
Verify: Total filled = 6A + 2B + 4C
```

**Test 4: Round Completion Wait**
```
Config: Any trades, use limit orders (not market)
Expected: Round 2 starts only after all round 1 orders show "filled"
Verify: Console logs show "Round 1 complete: All orders filled" before "Starting round 2"
```

**Test 5: Timeout Handling**
```
Config: Place limit orders that won't fill (far from market)
Expected: Auto-loop stops with timeout error after ~60 seconds
Verify: Error message shows which symbols didn't fill
```

### Browser Console Checks

Look for these log patterns:
```
✅ Good:
[Execution] Autoloop mode - 3 loops, GCD=1
[Execution] Loop 1/3 - placing C-BTC-50000:1, C-BTC-51000:2
[Execution] ✅ Round 1 complete: All orders filled
[Execution] Waiting 500ms before round 2...
[Execution] Loop 2/3 - placing C-BTC-50000:1, C-BTC-51000:2

❌ Bad (current bug):
[Execution] Loop 1/3 - placing C-BTC-50000:1, C-BTC-51000:1  // Wrong ratio!
[Execution] Loop 1 complete, waiting 500ms before next...
[Execution] Loop 2/3 - placing ...  // Started without verifying fills!
```

---

## Implementation Steps

1. **Create feature branch**
   ```bash
   git checkout -b 006-fix-autoloop-execution
   ```

2. **Modify AdjustmentReviewDialog.js**
   - Line ~238: Fix quantity calculation to preserve ratios
   - Line ~297: Add fill verification before next round
   - Line ~450: Add timeout handling in executeBatch

3. **Modify OptionsPanel.js** (similar fixes)
   - Line ~2400: Fix quantity calculation
   - Line ~2480: Add fill verification
   - Line ~2540: Add timeout handling

4. **Test thoroughly**
   - Test equal quantities (baseline)
   - Test unequal quantities (bug scenario)
   - Test round completion timing
   - Test timeout scenarios

5. **Verify logs**
   - Check console for correct quantities
   - Verify round timing (no premature starts)
   - Verify error handling

6. **Commit and create PR**
   ```bash
   git add .
   git commit -m "Fix auto-loop quantity ratios and round timing"
   git push origin 006-fix-autoloop-execution
   ```

---

## Common Pitfalls

### Pitfall 1: Forgetting to preserve original quantity
**Problem**: Modifying trade.quantity directly
**Solution**: Always use originalQuantity field

### Pitfall 2: Not handling SSR vs non-SSR differently
**Problem**: Different execution paths return different progress formats
**Solution**: Both paths must return same result structure

### Pitfall 3: Assuming all orders fill immediately
**Problem**: Limit orders may be pending
**Solution**: Always poll and verify fills

---

## Rollback Plan

If the fix causes issues:

1. **Revert the branch**
   ```bash
   git revert HEAD
   ```

2. **Hotfix for critical production**
   - Disable auto-loop feature in UI
   - Force users to use "all at once" mode only

3. **Alternative implementation**
   - Instead of GCD, use simple multiplication
   - Example: If user wants [1, 2] × 3 rounds, place [3, 6] in one shot

---

## Success Criteria

- [ ] Test 1: Equal quantities works as before (no regression)
- [ ] Test 2: Unequal quantities maintains ratio (1:2 stays 1:2)
- [ ] Test 3: Complex ratios work (3:1:2 stays 3:1:2)
- [ ] Test 4: Round 2 only starts after round 1 filled
- [ ] Test 5: Timeout is handled gracefully with clear error
- [ ] Console logs show correct execution flow
- [ ] UI updates show correct progress
- [ ] No new bugs introduced in non-autoloop modes
