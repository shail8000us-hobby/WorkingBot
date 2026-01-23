# Phase 1 Testing Guide
**Date:** January 24, 2026  
**Version:** 1.0  
**Branch:** BTEH

---

## 🧪 Manual Testing Checklist

### 1. Options Panel - Quick Filters
**Test Scenario:** Verify filters work with multiple positions

**Steps:**
1. Navigate to Options panel
2. Ensure you have 10+ option positions (mix of calls/puts, ITM/OTM)
3. Test P&L Filter:
   - Click "Profit" - only profitable positions should show
   - Click "Loss" - only losing positions should show
   - Click "All" - all positions should show
4. Test Moneyness Filter:
   - Click "ITM" - only in-the-money options should show
   - Click "ATM" - only at-the-money options should show (±2%)
   - Click "OTM" - only out-of-the-money options should show
5. Test combined filters:
   - Select "Profit" + "ITM" - only profitable ITM positions
   - Verify filter count shows correct number
6. Verify localStorage persistence:
   - Set filters, refresh page
   - Filters should remember previous state

**Expected Results:**
- ✅ Filters apply immediately without lag
- ✅ Filter count badge shows correct number
- ✅ Portfolio summary stats update with filtered positions
- ✅ Filters persist across page refreshes

---

### 2. Options Panel - Portfolio Summary Cards
**Test Scenario:** Verify summary stats are accurate

**Steps:**
1. Check Portfolio Summary Cards display:
   - Total Positions count
   - Total P&L (green if positive, red if negative)
   - Winners / Losers split
   - Win Rate percentage
2. Apply filters and verify stats update
3. Add a new position and verify stats refresh

**Expected Results:**
- ✅ All stats accurate and color-coded correctly
- ✅ Stats update when filters applied
- ✅ Stats refresh when positions change

---

### 3. Options Panel - Collapsible Greeks
**Test Scenario:** Greeks section can collapse/expand

**Steps:**
1. Locate "Portfolio Greeks" section
2. Click on the section header
3. Verify section collapses
4. Click again to expand
5. Refresh page - state should persist

**Expected Results:**
- ✅ Greeks section toggles smoothly
- ✅ Expand/collapse icon changes correctly
- ✅ State persists in localStorage
- ✅ No "Invariant failed" errors

---

### 4. Options Panel - Row Color Coding
**Test Scenario:** Rows have appropriate background colors

**Steps:**
1. Find a position with P&L > $5
2. Verify row has green background
3. Find a position with P&L < -$5
4. Verify row has red background
5. Find a position with small P&L (-$5 to $5)
6. Verify row has subtle call/put coloring only

**Expected Results:**
- ✅ Strong green for significant profits
- ✅ Strong red for significant losses
- ✅ Subtle colors for small P&L
- ✅ Visual hierarchy is clear

---

### 5. Payoff Diagram - Probability Overlay
**Test Scenario:** Probability distribution shows on chart

**Steps:**
1. Open any payoff diagram
2. Look for dotted green line
3. Verify it shows bell curve shape
4. Hover over chart points
5. Verify tooltip shows probability percentage
6. Check legend shows "Probability Distribution"

**Expected Results:**
- ✅ Dotted green line visible
- ✅ Bell curve centered near current price
- ✅ Tooltip shows probability %
- ✅ Secondary Y-axis (0-100%) on right side

---

### 6. Strategy Builder - PoP Badge
**Test Scenario:** Probability of Profit displays correctly

**Steps:**
1. Open Strategy Builder
2. Create a simple call spread:
   - Buy 1 call at strike A
   - Sell 1 call at strike A+5000
3. Check metrics section for PoP badge
4. Verify PoP is reasonable (40-70% typical)
5. Try different strategies (put spread, iron condor)

**Expected Results:**
- ✅ PoP badge shows percentage
- ✅ Green badge if PoP > 50%
- ✅ Orange badge if PoP ≤ 50%
- ✅ Calculation is accurate (compare to manual calc)

---

### 7. Futures Panel - Leverage Indicator
**Test Scenario:** Leverage shows with correct risk colors

**Steps:**
1. Navigate to Futures Panel (if you have futures positions)
2. Check Leverage column
3. Verify color coding:
   - Green for leverage < 3x
   - Orange for 3x ≤ leverage < 5x
   - Red with warning icon for leverage ≥ 5x
4. Hover over leverage chip for tooltip

**Expected Results:**
- ✅ Leverage displayed with risk label
- ✅ Colors match risk tiers
- ✅ Tooltip shows risk explanation
- ✅ High leverage shows warning icon

---

### 8. Futures Panel - Liquidation Proximity
**Test Scenario:** Liquidation distance bar is accurate

**Steps:**
1. Check Liquidation Distance column
2. Verify progress bar shows:
   - Green if > 20% from liquidation
   - Orange if 10-20% from liquidation
   - Red if < 10% from liquidation
3. Hover for tooltip showing exact distance
4. If any position < 10% from liq, verify alert appears

**Expected Results:**
- ✅ Progress bar matches liquidation distance
- ✅ Colors match risk levels
- ✅ Tooltip shows current/liq prices
- ✅ Critical alert shows for risky positions

---

### 9. Futures Panel - Asset Grouping
**Test Scenario:** Positions grouped by asset

**Steps:**
1. If you have BTC and ETH futures positions:
2. Verify they appear in separate accordion groups
3. Check each group shows:
   - Asset name (BTC, ETH, etc.)
   - Position count
   - Total P&L for asset
4. Click to collapse/expand groups
5. Refresh page - state should persist

**Expected Results:**
- ✅ Positions grouped correctly
- ✅ Group headers show accurate stats
- ✅ Accordions collapse/expand smoothly
- ✅ State persists in localStorage

---

### 10. Backend Payoff Engine - API Test
**Test Scenario:** Backend payoff calculation works

**Steps:**
1. Open browser DevTools → Network tab
2. Create a strategy in Strategy Builder
3. Look for POST to `/api/options-strategy/payoff/calculate`
4. Verify response contains:
   - price_points array
   - payoff_values_expiry array
   - payoff_values_current array
   - max_profit, max_loss
   - breakeven_points array
5. Verify chart updates with backend data

**Expected Results:**
- ✅ API endpoint responds in < 100ms
- ✅ Response structure is correct
- ✅ Payoff values are accurate
- ✅ Chart displays smoothly

---

### 11. Performance Testing
**Test Scenario:** UI remains responsive with many positions

**Steps:**
1. Have 20+ option positions open
2. Apply different filters rapidly
3. Collapse/expand Greeks section
4. Scroll through positions table
5. Open multiple payoff diagrams

**Expected Results:**
- ✅ Filter changes apply instantly (< 100ms)
- ✅ No lag when scrolling
- ✅ Payoff diagrams render in < 500ms
- ✅ No console errors or warnings

---

### 12. API Greeks vs Calculated
**Test Scenario:** Verify API Greeks are used

**Steps:**
1. Open browser console
2. Load Options panel with positions
3. Look for console logs:
   - "Using API Greeks for [symbol]" (green)
   - OR "Falling back to calculated Greeks for [symbol]" (orange)
4. Verify most positions use API Greeks
5. Check network tab - should see `/api/tickers/` calls

**Expected Results:**
- ✅ API Greeks used when available
- ✅ Graceful fallback to calculated
- ✅ Console logs show Greeks source
- ✅ 5-second cache reduces API calls

---

## 🐛 Known Issues to Test

### Issue 1: Ticker 404 Errors
**Symptom:** Console shows 404 for `/api/ticker/` endpoints  
**Expected:** Backend might not have all ticker endpoints  
**Test:** Verify app still functions with fallback Greeks

### Issue 2: WebSocket Connection
**Symptom:** WebSocket connection errors in console  
**Expected:** WebSocket is optional, app works without it  
**Test:** Verify app loads and functions normally

---

## 📊 Performance Benchmarks

| Feature | Target | Acceptable | Needs Work |
|---------|--------|------------|------------|
| Greeks Calculation | < 50ms | < 100ms | > 200ms |
| Filter Application | < 50ms | < 100ms | > 200ms |
| Payoff Chart Render | < 300ms | < 500ms | > 1000ms |
| Table Scroll (20+ rows) | 60fps | 30fps | < 30fps |
| API Response Time | < 100ms | < 300ms | > 500ms |

**How to Measure:**
```javascript
// In browser console
console.time('filter');
// Apply filter
console.timeEnd('filter');
```

---

## 🔍 Visual Regression Testing

### Screenshots to Capture
1. **Options Panel - Default View**
   - All positions visible
   - Portfolio stats showing
   - Greeks expanded

2. **Options Panel - Filtered View**
   - P&L filter applied
   - Filter count badge visible
   - Updated stats

3. **Payoff Diagram - With Probability**
   - Dotted green probability line
   - Secondary Y-axis visible
   - Tooltip showing probability

4. **Futures Panel - Risk Indicators**
   - Leverage chips color-coded
   - Liquidation bars visible
   - Asset grouping expanded

5. **Futures Panel - Critical Alert**
   - Red alert for near-liquidation position
   - All position details visible

---

## ✅ Final QA Checklist

Before marking Phase 1 complete, verify:

- [ ] No console errors on page load
- [ ] All filters work correctly
- [ ] Portfolio stats are accurate
- [ ] Greeks section is collapsible
- [ ] Row colors reflect P&L correctly
- [ ] Probability overlay shows on payoff charts
- [ ] PoP badges display in Strategy Builder
- [ ] Leverage indicators work (if have futures)
- [ ] Liquidation warnings work (if have futures)
- [ ] Asset grouping works (if have futures)
- [ ] Backend payoff API responds
- [ ] Performance is acceptable (see benchmarks)
- [ ] localStorage persists user preferences
- [ ] Page refreshes don't lose settings

---

## 🚀 Sign-Off

**Tested By:** _________________  
**Date:** _________________  
**Build Version:** _________________  
**Branch:** BTEH  
**Tag:** phase1-complete

**Overall Status:** ☐ PASS ☐ FAIL ☐ NEEDS WORK

**Notes:**
_______________________________________________
_______________________________________________
_______________________________________________
