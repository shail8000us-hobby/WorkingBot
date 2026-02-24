# Options Payoff Diagram — Production-Grade Improvement Plan

**Date:** February 24, 2026  
**Author:** AI Copilot (post deep audit)  
**Scope:** OptionsPayoffDiagram.js (1,800 lines) + payoff_engine.py (594 lines)  
**Goal:** Fix incorrect blue "On Target Date" line, remove debug artifacts, make institutional grade  
**Pre-commit:** `451f93d10` (SSR branch)

---

## Problem Statement

The **blue "On Target Date" line** in the Payoff Graph is incorrect while the **green "On Expiry" line** is correct. Additionally, debug text is visible in production and the component needs robustness improvements.

---

## Root Cause Analysis

### BUG 1 (D12): Debug Text Visible in Production
- **Location:** `OptionsPayoffDiagram.js` line ~1468
- **Renders:** `Debug: 3 total alerts, 0 shown for expiry (2026-02-24).`
- **Fix:** Remove or gate behind `NODE_ENV === 'development'`

### BUG 2 (CRITICAL): Risk-Free Rate Mismatch — Root Cause of Wrong Blue Line
| Location | Risk-Free Rate |
|----------|---------------|
| Frontend `OptionsPayoffDiagram.js` line 191 | **`r = 0.05` (5%)** |
| Backend `payoff_engine.py` line 52 | **`r = 0.0` (0%)** |

**Impact:** The Black-Scholes formula uses `e^(-rT)` for discounting. With `r=0.05`:
- Call prices are inflated (higher `S·N(d1)`, lower `K·e^(-rT)·N(d2)`)
- Put prices are deflated
- `theoAtCurrentSpot ≠ markPrice`, creating a **baseline offset** that shifts the entire blue curve

**Why this is wrong:** For **crypto options** (BTC/ETH), the industry standard risk-free rate is **0%** — no carry cost, no dividends. Delta Exchange uses 0%. The 5% is a stock-market assumption.

### BUG 3: Blue Line Baseline Drift from IV Solver Inaccuracy
Even with the rate fixed, the IV solver (Newton-Raphson + bisection, lines 74-99) may converge to an IV where `theoAtCurrentSpot ≠ markPrice`. The projection formula:
```
targetPayoff = currentUnrealizedPnL + (theoAtThisPrice - theoAtCurrentSpot) * sign * size * 0.001
```
If `theoAtCurrentSpot ≠ markPrice`, there's a constant offset error on every point. The blue line won't pass through the known current P&L at spot.

**Fix:** Compute blue line directly as:
```
targetPayoff = (theoAtThisPrice - entryPrice) * sign * absSize * multiplier
```
This eliminates the intermediate `theoAtCurrentSpot` subtraction.

### BUG 4: ETH Contract Multiplier Hardcoded Wrong
Contract multiplier is hardcoded to `0.001` everywhere (lines 369, 399, 418). ETH positions use `0.01`.

**Impact:** ETH options P&L shown at **10x wrong** value.

---

## Current Architecture

```
OptionsPayoffDiagram.js (1,800 lines)
├── Black-Scholes model (normalCDF, normalPDF, bsPrice, impliedVol) — lines 1-99
├── parsedPositions useMemo — lines 168-280
├── chartData useMemo (payoff calculation) — lines 285-565
├── Alert fetching + state (7 useState hooks) — lines 150-165, 570-600
├── Zoom handlers — lines 610-736
├── Render: positions chips, metrics strip, chart, sliders, alerts — lines 770-1800
│
payoff_engine.py (594 lines) — backend, NOT used by frontend
├── Black-Scholes (duplicate of frontend)
├── Greeks calculation
├── Probability of Profit (PoP)
├── Price distribution
├── Strategy payoff API
```

---

## Implementation Phases

### Phase A: Critical Fixes (1-2 hours) — DO FIRST

| # | Fix | Lines | Risk |
|---|-----|-------|------|
| A1 | Change `riskFreeRate` from `0.05` → `0.0` | Line 191 | Low — corrects BS pricing |
| A2 | Simplify blue line formula to eliminate baseline drift | Lines 395-470 | Medium — changes projection math |
| A3 | Remove debug text (D12) | Line ~1468 | Zero — debug only |
| A4 | Detect asset from symbol, use correct multiplier (0.001 BTC, 0.01 ETH) | Lines 369, 399, 418, 476 | Low — data fix |

#### A1 Detail: Risk-Free Rate Fix
```js
// BEFORE (line 191):
const riskFreeRate = 0.05;

// AFTER:
const riskFreeRate = 0.0; // Crypto standard — 0% (no carry cost, matches Delta Exchange)
```

#### A2 Detail: Blue Line Formula Fix
```js
// BEFORE (current approach — drift-prone):
// 1. Calculate currentUnrealizedPnL from market data
// 2. Calculate theoAtCurrentSpot via BS
// 3. Calculate theoAtThisPrice via BS
// 4. projectedChange = (theoAtThisPrice - theoAtCurrentSpot) * sign * size * mult
// 5. targetPayoff = currentUnrealizedPnL + projectedChange
// Problem: if theoAtCurrentSpot ≠ markPrice, there's a constant offset

// AFTER (direct approach — no drift):
// For each position at each price point:
// theoAtThisPrice = BS(price, strike, remainingYears, r, iv, type)
// targetPayoff += (theoAtThisPrice - entryPrice) * sign * absSize * multiplier
// This computes the theoretical P&L directly — no intermediate subtraction
```

#### A3 Detail: Debug Text Removal
```js
// REMOVE this line entirely (or wrap in dev check):
<Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
  Debug: {activeAlerts.length} total alerts, {filteredAlerts.length} shown for expiry ({currentExpiryStr || 'all'}).
</Typography>
```

#### A4 Detail: Contract Multiplier Detection
```js
// Add helper at top of component:
const getMultiplier = (symbol) => {
  if (!symbol) return 0.001;
  return symbol.toUpperCase().includes('ETH') ? 0.01 : 0.001;
};

// Replace all hardcoded 0.001 in payoff calculations with:
const multiplier = getMultiplier(pos.symbol);
```

---

### Phase B: Accuracy & Robustness (2-3 hours)

| # | Improvement | Detail |
|---|------------|--------|
| B1 | NaN/Infinity guards | Wrap BS output in `isFinite()` checks; fallback to intrinsic |
| B2 | Input validation | Validate positions before processing (non-zero size, valid strike, etc.) |
| B3 | IV solver convergence check | If solver doesn't converge (theoAtSpot vs markPrice > 5%), use exchange-provided IV from `pos.greeks.iv` if available |
| B4 | Add Probability of Profit (PoP) | Port `calculate_probability_of_profit` from backend or call API endpoint |
| B5 | Error boundary | Wrap chart in React error boundary so calculation failures don't crash the panel |

---

### Phase C: UX Polish (2-3 hours)

| # | Improvement | Detail |
|---|------------|--------|
| C1 | Remove duplicate content | Bottom stats row (line ~1624) duplicates top metrics strip; bottom positions chips (line ~1640) duplicates top positions box |
| C2 | Add Greeks to tooltip | Show portfolio Δ, θ at hovered price point |
| C3 | Multi-expiry indicator | Visual badge showing which positions expire first vs later |
| C4 | Replace emoji alert icon | SVG path instead of 🔔 in chart `<text>` element |
| C5 | Expiry line dual-color | Red below zero, green above (currently always green) |

---

### Phase D: Component Extraction (3-4 hours)

| # | New File | Contents | Lines |
|---|----------|----------|-------|
| D1 | `payoffCalculator.js` | BS model, IV solver, payoff loop — pure functions, testable | ~200 |
| D2 | `usePayoffData.js` | Hook wrapping parsedPositions + chartData useMemos | ~300 |
| D3 | `usePayoffAlerts.js` | Hook for alert state + CRUD (7 useState + fetch) | ~80 |
| D4 | `PayoffAlertDialog.js` | Alert creation dialog JSX | ~120 |
| D5 | `PayoffControls.js` | Target price slider + date slider | ~150 |

**Result:** OptionsPayoffDiagram.js ~1,800 → ~500 lines (thin render shell)

---

### Phase E: Advanced Features (Future/Deferred)

| # | Feature | Detail |
|---|---------|--------|
| E1 | Multi-target-date overlay | Show 2-3 blue lines for different dates simultaneously |
| E2 | IV smile interpolation | Use variance interpolation for wing strikes |
| E3 | Probability distribution overlay | Faint bell curve showing probability density |
| E4 | Backend-computed payoff | API endpoint returning payoff curves (single source of truth) |
| E5 | Scenario comparison mode | Compare current portfolio vs "what if I add X" |

---

## Files Inventory

| Phase | File | Action |
|-------|------|--------|
| A | `OptionsPayoffDiagram.js` | Fix r=0, fix blue line formula, remove debug, fix multiplier |
| B | `OptionsPayoffDiagram.js` | Add guards, validation, error boundary |
| C | `OptionsPayoffDiagram.js` | Remove duplicates, enhance tooltip, dual-color line |
| D | **NEW** `payoffCalculator.js` | Extract pure math functions |
| D | **NEW** `usePayoffData.js` | Extract data hook |
| D | **NEW** `usePayoffAlerts.js` | Extract alert hook |
| D | **NEW** `PayoffAlertDialog.js` | Extract dialog |
| D | **NEW** `PayoffControls.js` | Extract sliders |

---

## Testing Strategy

### After Phase A (Critical)
1. Open payoff diagram with existing BTC positions
2. Verify blue line passes through current market P&L at spot price
3. Verify green expiry line unchanged
4. Verify debug text gone
5. If ETH positions exist, verify correct P&L scale

### After Phase B (Robustness)
1. Test with deep OTM positions (IV solver edge case)
2. Test with expired positions (daysToExpiry = 0)
3. Test with closed positions (size = 0)
4. Verify no NaN/Infinity in chart

### After Phase C (UX)
1. Visual check — no duplicate information
2. Hover tooltip shows Greeks
3. Alert icons render correctly

### Smoke Test
```bash
cd webui/frontend && npm run build 2>&1 | tail -5
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Blue line formula change produces wrong values | Compare old vs new at 5 price points before committing |
| IV solver calibration breaks for edge cases | Add fallback to exchange-provided IV |
| ETH multiplier change surprises users | P&L values were already wrong — this fixes them |
| Component extraction breaks rendering | Extract one at a time, test after each |

---

## Approval

- [ ] Phase A approved — critical fixes
- [ ] Phase B approved — robustness
- [ ] Phase C approved — UX polish
- [ ] Phase D approved — extraction
- [ ] Phase E acknowledged — future

**Starting with Phase A immediately.**
