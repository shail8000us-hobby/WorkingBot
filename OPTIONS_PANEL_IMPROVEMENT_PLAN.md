# Options Panel — Production-Grade Improvement Plan

**Date:** February 23, 2026  
**Author:** AI Copilot (post deep audit)  
**Scope:** Navigation + Options Panel UX/Architecture  
**Guiding Principle:** Zero functional regressions. Every change must be backward-compatible.

---

## Executive Summary

After auditing **22 files / ~14,560 lines** in the Options system, **1,691 lines** in App.js, and **~3,200 lines** across hooks, stores, contexts, and utilities, this plan addresses **38 specific improvements** across 5 phases. Each phase is independently deployable and testable.

---

## Current Architecture Snapshot  (Updated Feb 23, 2026)

```
App.js (1750 lines — updated)
├── 24 nav sections with `group` property (6 groups)
├── Sidebar.js (138 lines — grouped rendering, complete prefetch map)
├── MobileNav (inline, 40 lines — grouped with dividers)
│
└── OptionsPanel.js (7011 lines — Phase 2 header declutter applied)
    ├── Primary bar: Title + Status + Count + Turbo + [?] + Sound + Refresh + [▼]
    ├── Secondary toolbar: Collapsible — Poll, Custom Order, Hidden, Payoff, Adjust
    ├── Keyboard shortcuts → tooltip (was permanent 40px bar)
    ├── ScalingStrategy → collapsible, default collapsed, shows summary
    ├── ExpiryMaxLossPanel → collapsible, default collapsed, shows count
    ├── 55 useState hooks (+ 3 new collapse states)
    ├── 28 useEffect hooks
    └── Sub-components: 21 files (unchanged)
```

---

## Phase 1: Navigation Grouping & Visual Hierarchy  ✅ COMPLETED (Feb 23, 2026)

**Risk:** Low — CSS/JSX only, no logic changes  
**Impact:** High — immediate UX clarity  
**Estimated effort:** 2-3 hours  
**Actual effort:** ~1.5 hours  
**Commit:** `becc7a5fc` (plan), Phase 1 code in next commit

### Problem
24 flat navigation buttons in a single scrollable row. Users must scroll horizontally to find options-related tabs. No visual distinction between "Grid Bot" features and "Options Trading" features.

### Changes

#### 1.1 — Group navigation sections with visual dividers

Current flat list becomes grouped with subtle divider lines and group headers:

```
[Grid Bot]           Dashboard | Portfolio | Config | Risk & Safety | Positions
                     ─────────────────────────────────────────────────
[Options Trading]    📈 Options | 🔗 Chain | 🏗️ Strategy | 📊 MV Straddle
                     ─────────────────────────────────────────────────
[Algorithms]         💰 MMM | 🦋 SSR ALGO | ⏱️ 0DTE
                     ─────────────────────────────────────────────────
[Signals & ML]       📊 TradingView | RSI | ML
                     ─────────────────────────────────────────────────
[System]             Bot Mgmt | System Health | Intelligence | Todo
                     ─────────────────────────────────────────────────
[Labs]               🧪 Experimental | 🚀 Advanced
```

**Files to modify:**
- `App.js` — Add `group` property to each section definition
- `Sidebar.js` — Render group headers + dividers between groups
- `MobileNav` (in App.js) — Same grouping for mobile

#### 1.2 — Deduplicate nav icons

| Section | Current Icon | Proposed Icon |
|---------|-------------|---------------|
| Options | TrendingUp (duplicate) | `CandlestickChart` or keep TrendingUp but unique color |
| Options Chain | BarChart3 (shared with RSI) | `Link2` or `TableProperties` |
| Strategy Builder | Layers3 (shared with Positions) | `Blocks` or `Puzzle` |
| MV Straddle | TrendingUp (duplicate) | `Scale` or `ArrowLeftRight` |
| MMM | TrendingUp (duplicate) | `Coins` or `DollarSign` |
| 0DTE | Zap (shared with SSR ALGO) | `Timer` or `Clock` |

**Files to modify:**
- `App.js` — Update icon assignments in `sections` useMemo

#### 1.3 — Add badge to Options tab showing open positions count

Currently only `positions` and `dashboard` tabs have badges. Options tab should show the count of open options positions.

**Files to modify:**
- `App.js` — Add options positions count to state (or derive from store), pass as `badge` to the `options` section

#### 1.4 — Complete the Sidebar prefetch map

Currently only 11 of 24 sections are in `sectionChunkMap`. All 24 should have prefetch entries.

**Files to modify:**
- `Sidebar.js` — Add missing entries to `sectionChunkMap`

---

## Phase 2: Options Panel Header Declutter  ✅ COMPLETED (Feb 23, 2026)

**Risk:** Low — UI reorganization, no logic changes  
**Impact:** High — cleaner header, less visual noise  
**Estimated effort:** 3-4 hours  
**Actual effort:** ~1.5 hours  
**Build:** Clean (0 errors)

### Problem
The header row packs **12+ controls** in a single flex row:
- Title + Status Badge + Position Count + Custom Order indicator + Reset Order btn + Show Hidden btn + Payoff Selection count + Poll Interval toggle + Turbo Mode toggle + Adjust Position btn + Sound Settings icon + Refresh icon

This overflows on screens < 1440px and creates visual chaos.

### Changes

#### 2.1 — Split header into Primary Bar + Secondary Toolbar

**Primary Bar (always visible):**
```
[ShowChartIcon] Options Positions  [3 positions] [Guardian: OK]     [🔄 Refresh]
```

**Secondary Toolbar (collapsible, icon-driven):**
```
[⚡ Turbo] [🔊 Sound] [⏱ Poll: 5s] [👁 2 hidden] [🔀 Custom order] [🎯 Adjust] [⚙️ Settings ▾]
```

The settings gear menu consolidates: Poll Interval, Column Visibility, Reset Order, Show Hidden.

#### 2.2 — Make Keyboard Shortcuts bar a tooltip, not permanent UI

Currently takes ~40px of permanent vertical space showing static text:
```
⌨️ Shortcuts: B = Buy | S = Sell | C = Close | R = Refresh | Esc = Cancel
```

Change to: A small `[?]` icon button in the toolbar → tooltip/popover showing shortcuts on hover.

**Files to modify:**
- `OptionsPanel.js` — Lines ~4060-4080 (keyboard shortcuts bar) → convert to Tooltip
- `OptionsPanel.js` — Lines ~3571-3695 (header row) → split into two rows

#### 2.3 — Make Position Scaling Strategy section collapsible (default: collapsed)

Currently the "Strategy: Fixed Size / Profit-Based / Delta Neutral" + parameter inputs + description alert are **always visible** (~200px of vertical space). Most sessions use the same settings.

Change: Wrap in a collapsible section with a compact summary when collapsed:
```
📊 Strategy: Fixed Size (5 per click)  [▼ Expand]
```

**Files to modify:**
- `OptionsPanel.js` — Lines ~3845-4055 (strategy section) → wrap in collapsible with summary

#### 2.4 — Make ExpiryMaxLossPanel collapsible (default: collapsed)

Currently always visible between header and position table. Convert to collapsible with inline summary.

**Files to modify:**
- `OptionsPanel.js` — Where `<ExpiryMaxLossPanel>` is rendered (~line 3770)

---

## Phase 3: Sticky Summary & Greeks Bar  ✅ COMPLETED (Feb 23, 2026)

**Risk:** Low — positioning change only  
**Impact:** High — critical trading info always visible  
**Estimated effort:** 2-3 hours  
**Actual effort:** ~45 minutes  
**Build:** Clean (0 errors)

### Problem
Total PnL, Calls/Puts count, and Portfolio Greeks are rendered **below** the positions table (after scrolling past 500px max-height table). During active trading, this critical information is off-screen.

### Changes

#### 3.1 — Create a sticky summary strip above the positions table

```
┌──────────────────────────────────────────────────────────────────────┐
│ 💰 Total PnL: +$1,245.30  |  📈 4C / 📉 3P  |  Δ +0.0234  θ -12.5 │
│ BTC: Long 0.0034 equiv  |  ETH: Short 0.0012 equiv                  │
└──────────────────────────────────────────────────────────────────────┘
```

This strip sits **above** the `<TableContainer>` and has `position: sticky; top: 0; z-index: 10` within the card.

#### 3.2 — Move Greeks from below table to the sticky strip

The current "Portfolio Greeks" box (~lines 6023-6161) moves into the sticky summary. The detailed view remains expandable below the table for users who want the full breakdown.

**Files to modify:**
- `OptionsPanel.js` — Move summary/Greeks rendering (~lines 5990-6165) to above the table
- New: Create a `PortfolioSummaryStrip` sub-component (extracted from OptionsPanel)

---

## Phase 4: Component Extraction (OptionsPanel.js Decomposition)

**Risk:** Medium — structural refactor, must not break any functionality  
**Impact:** Critical — maintainability, testability, performance  
**Estimated effort:** 6-8 hours  
**Strategy:** Extract ONE component at a time, test after each extraction

### Problem
OptionsPanel.js is **6,887 lines** with **55 useState** hooks. This is the #1 architectural debt. Every state change re-evaluates all memos and callbacks. Performance degrades as position count grows.

### Extraction Plan (ordered by isolation — easiest first)

#### 4.1 — Extract `PendingOrdersPanel` component

**Lines to extract:** ~4097-4222 (collapsible pending orders table)  
**State to move:** `pendingOrders`, `pendingOrdersError`, `pendingOrdersCollapsed`  
**Props it needs:** `pollInterval` (to fetch on interval)  
**Callbacks to parent:** `onCancelOrder(order)` → triggers parent refresh  
**New file:** `components/options/PendingOrdersPanel.js` (~130 lines)

#### 4.2 — Extract `BatchOrderPanel` component

**Lines to extract:** ~5116-5930 (the entire blue batch order box)  
**State to move:** `selectedStrikes`, `orderQuantity`, `multiplierMode`, `executionMode`, `batchQuantities`, `batchOrderResults`, `batchExecuting`, `pendingBatchOrders`, `batchConfirmDialog`  
**Props it needs:** `positions`, `sortedPositions`, `status`, `pollInterval`  
**Callbacks to parent:** `onBatchExecuted()` → triggers parent refresh  
**New file:** `components/options/BatchOrderPanel.js` (~820 lines)

#### 4.3 — Extract `AutoLoopController` component

**Lines to extract:** Auto-loop state + UI from BatchOrderPanel  
**State to move:** `autoLoopEnabled`, `autoLoopRounds`, `autoLoopRunning`, `autoLoopCurrentRound`, `autoLoopProgress`, `autoLoopError`, `autoLoopLastRun`, `expiryLoopState`  
**Refs to move:** `autoLoopStopRef`, `expiryStopRefs`  
**New file:** `components/options/AutoLoopController.js` (~450 lines)  
**Note:** Extract as a custom hook `useAutoLoop` + UI component. The hook manages all loop state; the component renders the UI.

#### 4.4 — Extract `ScalingStrategyPanel` component

**Lines to extract:** ~3845-4055 (strategy selection + parameters + BTC/ETH spot display)  
**State to move:** `scalingStrategy`, `scalingParams`  
**Props it needs:** `spotPrices` (BTC, ETH)  
**New file:** `components/options/ScalingStrategyPanel.js` (~210 lines)

#### 4.5 — Extract `AddPositionDialog` component

**Lines to extract:** ~6200-6830 (the "Add to Position" premium redesign dialog)  
**State to move:** `addDialog`, `submittingOrder`, `lastUsedSize`  
**Props it needs:** `position`, `status`, `scalingStrategy`, `skipConfirmStrikes`  
**Callbacks to parent:** `onOrderPlaced()`, `onSkipConfirmUpdate()`  
**New file:** `components/options/AddPositionDialog.js` (~640 lines)

#### 4.6 — Extract `PortfolioSummaryStrip` component

**Lines to extract:** ~5990-6165 (summary chips + Greeks inline display)  
**Props it needs:** `sortedPositions`, `aggregatedGreeks`, `getPnlColor`, `formatPnl`  
**New file:** `components/options/PortfolioSummaryStrip.js` (~180 lines)

### Post-extraction OptionsPanel.js target: ~3,500-4,000 lines

The remaining core handles: position table rendering, DnD ordering, expiry filtering, WebSocket integration, data fetching. This is still significant but much more manageable.

---

## Phase 5: State Management Consolidation

**Risk:** Medium-High — touches data flow  
**Impact:** High — eliminates state bugs, improves performance  
**Estimated effort:** 4-6 hours  
**Note:** Do this AFTER Phase 4 extractions are stable

### Changes

#### 5.1 — Create `usePersistedState` hook

Replace the **15 separate useEffect hooks** that each save one state value to localStorage with a single reusable hook:

```js
// Before (repeated 15 times):
const [turboMode, setTurboMode] = useState(() => {
  const saved = localStorage.getItem('options_turbo_mode');
  return saved ? JSON.parse(saved) : false;
});
useEffect(() => {
  debouncedSave('options_turbo_mode', turboMode);
}, [turboMode, debouncedSave]);

// After:
const [turboMode, setTurboMode] = usePersistedState('options_turbo_mode', false);
```

**New file:** `hooks/usePersistedState.js` (~40 lines)  
**Eliminates:** ~150 lines of boilerplate from OptionsPanel

#### 5.2 — Create `useOptionsPositions` hook

Consolidate position-related state and fetching into one hook:

```js
const {
  positions, futuresPositions, pendingOrders, status,
  loading, error, refreshing,
  handleRefresh, pollInterval, setPollInterval,
} = useOptionsPositions();
```

**State moved:** `positions`, `futuresPositions`, `pendingOrders`, `status`, `loading`, `error`, `refreshing`, `pollInterval`  
**Logic moved:** `fetchDashboard`, `fetchPositions`, `fetchFuturesPositions`, `fetchPendingOrders`, `fetchStatus`, polling useEffect, WebSocket setup  
**New file:** `hooks/useOptionsPositions.js` (~350 lines)

#### 5.3 — Create `useOptionsSettings` hook

Consolidate all settings-related state:

```js
const {
  slTpSettings, maxLossSettings, expiryMaxLossSettings, tpSettings,
  loadAll, updateSLTP, updateMaxLoss, updateExpiryMaxLoss, updateTakeProfit,
} = useOptionsSettings();
```

**State moved:** `slTpSettings`, `maxLossSettings`, `expiryMaxLossSettings`, `tpSettings`  
**Logic moved:** All load* and handle*Update functions  
**New file:** `hooks/useOptionsSettings.js` (~200 lines)

#### 5.4 — Standardize API client usage

Current state: `apiShim` (simple), `apiClient` (full-featured), raw `fetch()` — all three used inconsistently.

Plan: All Options panel API calls → use `apiShim` (which already works correctly). Add retry + circuit breaker to `apiShim` by wrapping `apiClient`'s resilience features. Don't change calling code.

**Files to modify:**
- `utils/apiShim.ts` — Add retry/circuit-breaker wrapper (delegate to `apiClient` internals)

---

## Deferred / Future Phases (Not in Scope Now)

These are real issues found during the audit but should NOT be done in this sprint to avoid scope creep:

| ID | Issue | Why Deferred |
|----|-------|-------------|
| D1 | TypeScript migration for Options system | Too large; needs its own initiative |
| D2 | Web Worker for Black-Scholes/Monte Carlo | Performance optimization, not UX |
| D3 | Consolidate 3 WebSocket connections | Requires backend changes |
| D4 | React Router for deep-linking | Fundamental architecture change |
| D5 | Remove `key={activeSection}` to preserve state | Requires careful state management redesign |
| D6 | Mobile-first responsive redesign for all panels | Separate UX project |
| D7 | `GreeksDashboard.js` is imported but unused | Cleanup task, not urgent |
| D8 | `InstanceContextBar` / `FloatingActionBar` dead code | Cleanup task |
| D9 | `MLDecisionCenter` settings dialog doesn't save | Bug fix, separate ticket |
| D10 | AutoloopContext `totalOrdersFilled` tracking bug | Bug fix, separate ticket |
| D11 | Console.log cleanup for production | Cleanup task |
| D12 | Debug text visible in OptionsPayoffDiagram | Bug fix, minor |

---

## Implementation Order & Dependencies

```
Phase 1 (Nav Grouping)      ──── No dependencies, start immediately
     │
Phase 2 (Header Declutter)  ──── No dependencies, can parallel with Phase 1
     │
Phase 3 (Sticky Summary)    ──── Independent, can parallel
     │
Phase 4 (Component Extract) ──── Depends on Phase 2 & 3 being stable
     │                            Extract in order: 4.1 → 4.2 → 4.3 → 4.4 → 4.5 → 4.6
     │                            TEST after each extraction
     │
Phase 5 (State Consolidation) ── Depends on Phase 4 being stable
                                  Extract hooks in order: 5.1 → 5.2 → 5.3 → 5.4
                                  TEST after each hook extraction
```

---

## Testing Strategy

### After Each Phase

1. **Visual regression:** Open the Options panel, verify all sections render correctly
2. **Functional test:** Place a test order (sell 1 lot), verify execution flow
3. **Batch test:** Select 2+ positions, execute batch order, verify results
4. **Auto-loop test:** Start a 2-round auto-loop, verify fill tracking & stop
5. **Payoff diagram:** Verify payoff chart renders with correct profit/loss areas
6. **SL/TP test:** Set a stop-loss on a position, verify indicator shows correctly
7. **Max Loss test:** Set per-expiry max-loss, verify indicator colors
8. **Turbo mode:** Toggle turbo mode, verify keyboard shortcuts work
9. **Sound test:** Execute a trade, verify sound plays (if enabled)
10. **Mobile test:** Open on phone/tablet, verify navigation works

### Smoke Test Command
```bash
# Build frontend and verify no compilation errors
cd webui/frontend && npm run build 2>&1 | tail -5

# Start backend + verify health
launchctl restart com.gridbot.webui && sleep 5 && curl -s http://127.0.0.1:5555/api/health
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Phase 4 extraction breaks position table | Extract markup first, verify render, then move state |
| Phase 5 hook extraction causes stale closures | Use refs for values read in callbacks (existing pattern) |
| localStorage migration breaks user settings | Read from both old keys + new keys with fallback |
| Batch order logic break during extraction | Keep `calculateBatchOrders` in OptionsPanel until all consumers are extracted |
| Real money at risk from order execution bugs | ALL order-placement code stays untouched — extraction is UI-only |

---

## Files Inventory (All Files Touched)

| Phase | File | Action |
|-------|------|--------|
| 1 | `App.js` | Add `group` to sections, update icons, add options badge |
| 1 | `Sidebar.js` | Add group rendering with dividers |
| 1 | `MobileNav` (in App.js) | Add group rendering |
| 2 | `OptionsPanel.js` | Reorganize header, make shortcuts a tooltip, make strategy collapsible |
| 3 | `OptionsPanel.js` | Move summary/Greeks above table as sticky strip |
| 4 | **NEW** `PendingOrdersPanel.js` | Extracted from OptionsPanel |
| 4 | **NEW** `BatchOrderPanel.js` | Extracted from OptionsPanel |
| 4 | **NEW** `AutoLoopController.js` | Extracted from OptionsPanel |
| 4 | **NEW** `ScalingStrategyPanel.js` | Extracted from OptionsPanel |
| 4 | **NEW** `AddPositionDialog.js` | Extracted from OptionsPanel |
| 4 | **NEW** `PortfolioSummaryStrip.js` | Extracted from OptionsPanel |
| 4 | `OptionsPanel.js` | Reduce from 6887 → ~3500 lines |
| 5 | **NEW** `hooks/usePersistedState.js` | New utility hook |
| 5 | **NEW** `hooks/useOptionsPositions.js` | Data fetching hook |
| 5 | **NEW** `hooks/useOptionsSettings.js` | Settings management hook |
| 5 | `utils/apiShim.ts` | Add resilience features |

**Total new files: 9**  
**Total modified files: 5**  
**Net line reduction in OptionsPanel.js: ~3,400 lines (6887 → ~3500)**

---

## Approval Checklist

- [x] Phase 1 plan reviewed — ✅ Implemented & deployed
- [x] Phase 2 plan reviewed — ✅ Implemented & deployed
- [x] Phase 3 plan reviewed — ✅ Implemented & deployed
- [ ] Phase 4 extraction order confirmed
- [ ] Phase 5 hook consolidation confirmed
- [ ] Deferred items acknowledged
- [ ] Testing strategy accepted

**Ready to proceed? Confirm which phase(s) to start with.**
