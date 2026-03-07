# Open Positions Panel — Institutional-Grade Robustness Plan

**Date:** February 24, 2026 (Revised)  
**Author:** AI Copilot (deep audit of screenshot + codebase)  
**Scope:** OptionsPanel.js (4,284 lines) + PendingOrdersPanel + BatchOrderPanel + PortfolioSummaryStrip + ScalingStrategyPanel + Backend positions.py  
**Goal:** Make the open positions panel an institutional-grade **monitoring dashboard** — accurate, clear, and impossible to misread during volatile markets

---

## Key Context: Algo-Managed Positions

**Positions are created and managed by various algorithms (bots)**, not manually. Each algo handles its own:
- Position sizing and entry logic
- Risk management and exit triggers
- Delta hedging and rebalancing

The Max Loss, SL/TP, and Take Profit columns are **manual override tools** — the user sets them only when they want extra safety beyond what the algos already provide. Empty Max Loss / TP columns are **normal and expected**, not a flaw.

This means the positions panel is primarily a **read-only monitoring dashboard** with optional manual intervention capabilities. The improvements should focus on:
1. **Visibility** — Can I instantly understand what the algos are doing?
2. **Data accuracy** — Are the numbers I'm reading correct and unambiguous?
3. **Situational awareness** — Do I know the current risk state at a glance?
4. **Override capability** — When I DO need to intervene, can I do it fast?

---

## Screenshot Audit — Flaws & Inconsistencies Found

Analyzing the attached screenshot against the codebase, here are **35 specific issues** organized by severity:

---

### CRITICAL (Data Integrity / Misleading Display)

| # | Issue | Evidence from Screenshot | Root Cause in Code |
|---|-------|--------------------------|-------------------|
| C1 | **SL/TP column shows checkmarks `✓` for all rows but no SL or TP is actually configured** | Checkmarks imply protection is active when it isn't | `SLTPIndicator.js` shows a checkmark icon even when no SL/TP is configured. Since the user sets these only for extra safety, a blank or neutral icon is correct for "algo-managed, no manual override". A checkmark actively **lies** to the user. |
| C2 | **PnL percentage -774.58% is misleading** | Row 6: Put 65,600, PnL -$3.9093, shown as -774.58% | Percentage uses cashflow ($0.50) as denominator. For algo-placed positions, PnL-relative-to-margin or PnL-in-USD is far more meaningful. Seeing "-774%" causes unnecessary panic when the actual dollar loss is $3.90. |
| C3 | **Greeks bar shows Δ +6.5236 with no dollar-equivalent context** | Summary strip: `Δ +6.5236` | A delta of +6.52 is meaningful to a quant, but for quick situational awareness the user needs: "≈ $414K directional BTC exposure" or "equivalent to 6.52 BTC long". The raw number alone doesn't communicate urgency. |
| C4 | **No margin utilization display** | Backend fetches `blocked_margin_usd` but nowhere in the UI | Without this, the user can't tell at a glance if the algos have consumed 30% or 90% of available margin. This is the single most important "am I safe?" indicator for algo-managed portfolios. |
| C5 | **Expiry badges show no urgency for 0DTE** | All show "24/02/2026" with the same calm green icon | ALL positions expire **today** (0DTE). This should be the loudest signal on the panel. A calm green date chip with no countdown makes 0DTE look like a monthly expiry. |
| C6 | **PoP shows "-" for deep ITM positions** | Rows 4, 5, 6 show blank PoP | `calculatePoP` silently returns undefined for edge cases. Should show "< 1%" or "N/A" with tooltip explaining why — not a blank that looks like a data loading failure. |

---

### HIGH (UX / Comprehension Issues)

| # | Issue | Evidence | Impact |
|---|-------|----------|--------|
| H1 | **Cashflow column values are incomprehensible** | Row 6: size -2, entry $252.35, cashflow $0.50 | Cashflow = `entry × size × 0.001` (BTC contract multiplier). The raw USD number is correct but without visible formula context, "$0.50" next to a "$3.90 loss" makes no sense. The column needs a tooltip showing the breakdown or should show a more intuitive unit. |
| H2 | **No spread or liquidity indicator** | Bid $2,182 / Ask $2,232 on row 6 = $50 spread (2.3%) | The user can mentally calculate spread from bid/ask, but a subtly color-coded spread indicator (green < 1%, yellow 1-5%, red > 5%) would instantly flag illiquid positions that are expensive to close in an emergency. |
| H3 | **No "which algo created this" indicator** | 8 flat rows, no grouping or source attribution | Multiple algos place positions. The user can't tell which algo owns which position. Adding a small algo-source tag would help answer "why does this position exist?" |
| H4 | **Pending order not linked to its position** | `C-BTC-64800-240226 SELL 8 @ $44.00` in pending panel, 64,800 Call in table (size -52) | The pending order is scaling into the 64,800 Call but there's no visual connection. A small "⏳+8" badge on the position row would make the relationship obvious. |
| H5 | **IV column has no context** | 50.1%, 52.4%, 79.8%, 32.4% | Is 32.4% IV high or low for a deep ITM put? No IV rank/percentile. The 32.4% is likely a data quality artifact for a deep ITM option — should be flagged. |
| H6 | **Size column lacks units** | `-62`, `-52`, `-45`, etc. | No "lots" or "contracts" label. Header should say "Size (cts)" or show a unit suffix. |
| H7 | **No stale data indicator** | LIVE PRICES badge at bottom-right shows age, but no per-data-source indicator | If the backend hasn't updated in 15+ seconds, the user doesn't know prices are stale until they notice the timestamp. A subtle color shift on the data strip would help. |
| H8 | **Number formatting inconsistency** | Bid shows `$3.00` and `$2182.00` in same column | Some prices are single-digit, some four-digit. Thousands separator missing on large values ($2,182 not $2182). |

---

### MEDIUM (Missing Monitoring Features)

| # | Issue | Description |
|---|-------|-------------|
| M1 | **No P&L trend indicator** | P&L is a static number updated every poll. A tiny up/down arrow or color flash showing whether P&L improved or worsened since last update would add crucial context for algo monitoring. |
| M2 | **No notional exposure summary** | The 8 positions represent some total BTC notional. The Greeks bar shows delta but not the raw notional value of the short options position. |
| M3 | **No portfolio-level max profit / max loss / breakeven inline** | The payoff diagram has this data but it's in a separate section. A compact `Max Profit: +$X / Max Loss: -$Y / BEs: $A, $B` line above the table would be invaluable. |
| M4 | **No position-level delta contribution** | Can't tell which position is the biggest delta driver without mental math. A tiny "Δ contribution: 40%" badge would instantly show concentration risk. |
| M5 | **No mark price (mid-market)** | Entry and bid/ask are shown but no calculated mid-price. Algos often base decisions on mid-price; showing it helps the user understand algo logic. |
| M6 | **No realized vs. unrealized P&L breakdown** | If algos have partially closed positions, the realized portion is invisible in this table. |
| M7 | **No "time in position"** | No indicator of when positions were entered. For 0DTE, knowing "entered 45m ago" vs "entered 4h ago" changes the entire risk interpretation. |
| M8 | **Drag handles consume space** | Each row has a `⠿` drag handle — useful for manual reorder but takes column space. For an algo-monitoring dashboard, this could be behind a toggle. |

---

### LOW (Polish & Technical Debt)

| # | Issue | Description |
|---|-------|-------------|
| L1 | **4,284 lines in OptionsPanel.js** | Still a God component. Table rendering alone is ~600 lines. |
| L2 | **No unit tests for displayed calculations** | Greeks aggregation, PnL%, PoP, cashflow — all untested. A formula bug silently corrupts what the user sees. |
| L3 | **`calculateSmartScaling` called inline during render** | Recalculates on every render for every row. Should be memoized. |
| L4 | **No error boundary per position row** | One malformed position data kills the entire table. |
| L5 | **Console.log statements in production** | Multiple `console.log` in handlers. |
| L6 | **5s polling as primary data source** | WebSocket should be primary with polling as fallback. |
| L7 | **No loading skeleton for refreshes** | Rows flash/jump on data update. |

---

## Improvement Plan — 6 Phases

### Phase 6: Monitoring Clarity (CRITICAL — Do First)

**risk:** Low (display-only changes, no logic modified)  
**Impact:** CRITICAL — directly fixes misleading information  
**Estimated effort:** 4-6 hours  
**Principle:** The panel is an algo-monitoring dashboard. Every pixel should answer: "Are my algos healthy?"

| Task | Description | File(s) |
|------|-------------|---------|
| 6.1 | **Fix SL/TP indicator states** — Replace misleading checkmarks with three clear states: `—` (no manual override set, normal for algo positions), 🛡 (green shield: manual SL+TP active), ⚠️ (partial: only SL or only TP). Tooltip: "Manual override — set SL/TP for extra protection beyond algo risk management." | `SLTPIndicator.js` |
| 6.2 | **Margin utilization bar** — Show `Margin: $X / $Y (Z%)` in the PortfolioSummaryStrip using already-fetched `blocked_margin_usd`. Color: green < 50%, yellow 50-75%, red > 75%. This is the #1 "am I safe?" signal for algo-managed portfolios. | `PortfolioSummaryStrip.js` |
| 6.3 | **0DTE countdown timer** — For positions expiring today, replace static date chip with live countdown: `⏰ 2h 23m` with color coding (green > 2h, yellow 30m-2h, red < 30m, pulsing < 5m). For non-0DTE, show `3d 14h`. | `OptionsPanel.js` (expiry cell) |
| 6.4 | **Delta dollar-equivalent in Greeks bar** — Next to `Δ +6.5236`, show `≈ $414K BTC exposure` (delta × spot price). Tooltip: "Your portfolio moves ≈$6,523 for every $1,000 BTC price change." | `PortfolioSummaryStrip.js` |
| 6.5 | **Fix PoP for edge cases** — Return `"< 1%"` when PoP is extremely low instead of undefined. Return `"> 99%"` for extremely high. Show `"N/A"` with tooltip for cases where calculation is invalid. | `probabilityCalc.js`, `OptionsPanel.js` |
| 6.6 | **Stale data indicator** — If position data is > 10s old, turn the "LIVE PRICES" badge yellow. If > 30s, turn red with "STALE" label. | `PortfolioSummaryStrip.js` or header area |

---

### Phase 7: Data Presentation Fixes

**Risk:** Low — display changes only  
**Impact:** High — eliminates confusion  
**Estimated effort:** 3-5 hours

| Task | Description | File(s) |
|------|-------------|---------|
| 7.1 | **Fix PnL percentage** — Show PnL in USD prominently (the real number that matters). Show percentage as secondary in a tooltip or sub-text. If percentage is shown, use margin as denominator (not cashflow) to avoid absurd -774% numbers. Add tooltip: "PnL vs margin deployed for this position." | `OptionsPanel.js` (PnL cell) |
| 7.2 | **Cashflow tooltip with formula breakdown** — On hover: `"Entry ($252.35) × Contracts (2) × Multiplier (0.001) = $0.5047 USD collected"`. This answers "where does $0.50 come from?" | `OptionsPanel.js` (cashflow cell) |
| 7.3 | **Add spread indicator to bid/ask** — Show `Spread: $50 (2.3%)` as a subtle sub-line below bid/ask, or a colored dot: green (tight, < 1%), yellow (moderate, 1-5%), red (wide, > 5%). Helps assess exit cost. | `OptionsPanel.js` (bid/ask cells) |
| 7.4 | **IV reasonableness flag** — Color IV cell yellow when value is suspiciously low (< 15%) or high (> 200%) for the position type. Tooltip: "IV may be unreliable for deep ITM options." | `OptionsPanel.js` (IV cell) |
| 7.5 | **Size column header with units** — Change "Size" → "Size (cts)" in the column header. | `OptionsPanel.js` |
| 7.6 | **Number formatting consistency** — All USD values use `toLocaleString()` with 2 decimal places. Thousands separator on bid/ask/entry for values > 999. Currently: `$2182.00` → `$2,182.00`. | Throughout table cells |

---

### Phase 8: Algo Awareness & Intelligence

**Risk:** Medium — new UI elements  
**Impact:** High — transforms panel from "raw data table" to "algo monitoring dashboard"  
**Estimated effort:** 8-10 hours

| Task | Description | File(s) |
|------|-------------|---------|
| 8.1 | **Algo source tag per position** — Each position row gets a small colored tag showing which algo created it (e.g., 🦋 SSR, 📊 MMM, 🎯 Manual, ⚡ 0DTE). Source comes from backend metadata or symbol-pattern matching. | `OptionsPanel.js`, Backend: add `source_algo` field |
| 8.2 | **Pending order → position linking** — When a pending order matches a position symbol, show a badge on the position row: `⏳ +8 pending @ $44`. Clicking scrolls to/highlights the pending order in the panel above. | `OptionsPanel.js`, `PendingOrdersPanel.js` |
| 8.3 | **Strategy auto-detection** — Group positions by detected strategy structure (straddle, strangle, condor, butterfly, naked). Show a subtle group header: `Short Strangle: 62K PE / 65.6K CE`. Helps the user understand algo intent at a glance. | New: `StrategyDetector.js` (utility), `OptionsPanel.js` (rendering) |
| 8.4 | **P&L trend indicator** — When P&L changes on refresh, flash the cell green (improved) or red (worsened) for 500ms. Also add a tiny ▲/▼ arrow showing direction of last change. | `OptionsPanel.js` (PnL cell) |
| 8.5 | **Inline portfolio summary** — Above the table, below the Greeks bar: `Max Profit: +$12.50 | Max Loss: -$8.30 | Breakevens: $61,200 / $66,800`. Data sourced from payoff engine. | `PortfolioSummaryStrip.js` or new `PortfolioRiskSummary.js` |
| 8.6 | **Position delta contribution** — In each row's tooltip or as a subtle sub-text: "Δ contribution: 42% of portfolio delta". Instantly shows concentration risk. | `OptionsPanel.js` |

---

### Phase 9: Override & Emergency Tools

**Risk:** Medium (touches order execution)  
**Impact:** High — enables fast manual intervention when algos need help  
**Estimated effort:** 6-8 hours  
**Principle:** Algos manage risk, but the user needs fast override capability for edge cases.

| Task | Description | File(s) |
|------|-------------|---------|
| 9.1 | **"Flatten All" emergency button** — One-click with 2-step confirmation. Shows preview: which positions, estimated market slippage per position (spread × size), total cost. | New: `FlattenAllButton.js`, Backend: `position_liquidation.py` (route exists) |
| 9.2 | **"Kill Switch" in header** — Small red ⏹ button in the positions panel header that stops all algos, cancels all pending orders, and freezes new order placement. Currently exists in a separate System Health panel — surface it here where it's needed most. | `OptionsPanel.js` header |
| 9.3 | **One-click max-loss for any position** — When the user DOES want to add manual protection, the Max Loss column should allow: (a) click to set a value, (b) show a smart suggestion as placeholder (e.g., `"3× premium"` greyed out), (c) confirm with single click. Current flow already works but the suggestion would speed it up. | `MaxLossIndicator.js` |
| 9.4 | **Close group of losing positions** — Select multiple rows (checkboxes already exist) → "Close Selected" button that shows preview of total locked-in loss before confirming. Faster than closing one by one. | `BatchOrderPanel.js` |
| 9.5 | **Audit trail per position** — Click a position to expand and see: entry time, which algo placed it, number of adds/reduces, partial close history. Answers "why does this position exist and what happened to it?" | New: `PositionAuditTrail.js` |

---

### Phase 10: Table Architecture & Performance

**Risk:** High — structural refactor  
**Impact:** Medium-High — maintainability, extensibility  
**Estimated effort:** 8-10 hours

| Task | Description | File(s) |
|------|-------------|---------|
| 10.1 | **Extract `PositionsTable.js`** — The entire table (headers + rows + DnD + sorting) is ~600 lines embedded in OptionsPanel. Extract with well-defined props interface. | New: `PositionsTable.js`, `OptionsPanel.js` |
| 10.2 | **Extract `PositionRow.js`** — Each row is ~200 lines inside `.map()`. Extract as memoized component. | New: `PositionRow.js` |
| 10.3 | **Memoize `calculateSmartScaling`** — Currently computed inline during every render for every row. Cache results keyed on position state. | `OptionsPanel.js` or `PositionRow.js` |
| 10.4 | **Error boundary per row** — One malformed position shouldn't crash the whole table. | `PositionsTable.js` |
| 10.5 | **Virtualized rendering** — For 50+ positions, use `react-virtuoso` or `react-window`. | `PositionsTable.js` |
| 10.6 | **Reduce polling, prioritize WebSocket** — WebSocket for bid/ask/PnL updates. Polling at 15s as fallback only. | `useOptionsPositions.js` |

---

### Phase 11: Institutional Polish

**Risk:** Low — cosmetic changes  
**Impact:** Medium — professional appearance  
**Estimated effort:** 4-6 hours

| Task | Description | File(s) |
|------|-------------|---------|
| 11.1 | **Column header units** — "Entry (USD)", "Bid (USD)", "IV (%)", "Size (cts)". | `OptionsPanel.js` |
| 11.2 | **Row color by P&L state** — Subtle tint: green = profitable, neutral = flat, warm = losing but within algo management, red = losing beyond expected range. The "expected range" could be algo-reported or a simple threshold. | `OptionsPanel.js` |
| 11.3 | **Export to clipboard/CSV** — Copy positions data for pasting into spreadsheets or sharing. | New: `ExportButton.js` |
| 11.4 | **Compact/Comfortable toggle** — Dense mode (12px/28px rows) for power users, comfortable mode (14px/40px) for readability. | `OptionsPanel.js` header |
| 11.5 | **Drag handle toggle** — Default: hidden (sorting by P&L/delta/expiry). Toggle to show when manual reorder is desired. Frees column space for monitoring. | `OptionsPanel.js` |
| 11.6 | **Unit tests for displayed calculations** — Greeks aggregation, PnL formatting, PoP edge cases, cashflow formula. | New: test files |

---

## Priority Matrix (Revised for Algo-Managed Context)

```
                    EFFORT →
                Low          Medium         High
           ┌────────────┬─────────────┬────────────────┐
  CRITICAL │ 6.1 (SL/TP │ 6.2 (Margin │ 9.1 (Flatten   │
  Impact   │  fix)       │  bar)       │  All)           │
    ↑      │ 6.3 (0DTE  │ 6.4 (Delta  │                │
    |      │  timer)     │  $-equiv)   │                │
    |      │ 6.5 (PoP   │ 7.1 (PnL%)  │                │
    |      │  fix)       │             │                │
           ├────────────┼─────────────┼────────────────┤
  HIGH     │ 7.2 (Cash  │ 7.3 (Spread)│ 8.1 (Algo      │
           │  tooltip)   │ 8.2 (Link   │  source tag)   │
           │ 7.5 (Units)│  orders)    │ 8.3 (Strategy  │
           │ 7.6 (Nums) │ 8.4 (PnL    │  detect)       │
           │ 6.6 (Stale)│  trend)     │ 8.5 (Inline    │
           │             │ 9.3 (ML     │  summary)      │
           │             │  suggest)   │                │
           ├────────────┼─────────────┼────────────────┤
  MEDIUM   │ 11.1-11.5  │ 10.1-10.6   │ 9.5 (Audit     │
           │ (Polish)    │ (Arch)      │  trail)         │
           └────────────┴─────────────┴────────────────┘
```

---

## Recommended Execution Order

```
Week 1:  Phase 6 (Monitoring Clarity)  — fixes misleading display, adds margin/countdown
Week 2:  Phase 7 (Data Presentation)   — fixes PnL%, cashflow confusion, formatting
Week 3:  Phase 8 (Algo Intelligence)   — transforms from raw table to algo dashboard
Week 4:  Phase 9 (Override Tools)      — fast manual intervention when needed
Week 5:  Phase 10 (Architecture)       — technical debt, performance
Week 6:  Phase 11 (Polish)             — professional finish
```

---

## Quick Wins (< 30 min each)

1. **Fix SL/TP indicator** (C1) — Replace checkmark with dash `—` when no manual override set
2. **Add 0DTE countdown** (6.3) — Replace static date chip with hours/minutes remaining
3. **Fix PoP blanks** (6.5) — Return "< 1%" instead of undefined for deep ITM
4. **Size column units** (7.5) — "Size (cts)" header
5. **Number formatting** (7.6) — Add thousands separators on large values
6. **Cashflow tooltip** (7.2) — Show formula breakdown on hover

---

## Backend Changes Required

| API | Change | Purpose |
|-----|--------|---------|
| `GET /api/positions` | Add `mark_price` (mid), `spread_pct`, `margin_per_contract` per position | Better data for monitoring |
| `GET /api/positions` | Add `margin_available`, `margin_utilization_pct` to summary | #1 safety indicator |
| `GET /api/positions` | Add `source_algo` per position (which bot placed it) | Algo attribution |
| `GET /api/positions` | Add `pnl_vs_margin_pct` alongside existing `pnl_percentage` | Better PnL context |
| `GET /api/positions` | Add `entered_at` timestamp per position | Time-in-position |

---

## Success Criteria (Algo-Monitoring Dashboard)

- [ ] **Margin utilization visible at all times** (the #1 safety metric)
- [ ] **SL/TP indicator is honest** (no misleading checkmarks)
- [ ] **0DTE positions show countdown** (urgency is visible)
- [ ] **Delta has dollar-equivalent** context
- [ ] **PnL% uses meaningful denominator** (no -774% panic)
- [ ] **Each position shows which algo owns it**
- [ ] **Pending orders linked to positions**
- [ ] **Spread/liquidity visible** (exit cost awareness)
- [ ] **Stale data is flagged**
- [ ] **One-click flatten available** for emergency override
- [ ] **Numbers are consistently formatted**

---

## Non-Goals (Out of Scope)

- Auto-suggesting Max Loss / TP for algo positions (algos handle their own risk)
- Auto-closing positions on threshold breach (algos decide when to exit)
- Portfolio-level circuit breaker that overrides algos (algos are the risk managers)
- TypeScript migration (separate initiative)
- Mobile-responsive redesign (separate project)

---

## Design Philosophy: Trust the Algos, Verify the Dashboard

The previous plan assumed a manual trading desk where every position needs explicit protection. The corrected model:

| Concern | Wrong Assumption | Correct Model |
|---------|-----------------|---------------|
| Max Loss empty | Danger! Unprotected! | Normal — algo manages exits |
| TP empty | Missing protection! | Normal — algo decides profit-taking |
| Deep ITM put bleeding | Catastrophic tail risk! | Algo placed it deliberately, has exit logic |
| SL/TP checkmarks | Must all be set | Should show "no manual override" as neutral |
| Portfolio circuit breaker | Must auto-flatten | User intervenes manually if algos fail |
| Position sizing | Panel should enforce limits | Algos enforce their own limits |

The panel's job is: **Show the truth clearly, warn about anomalies, and provide fast manual override when the user decides they need it.**

---

**Ready to implement? Start with Phase 6 (Monitoring Clarity) — fixes the 6 most misleading elements.**
