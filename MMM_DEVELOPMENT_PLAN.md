# MMM — Money Mind & Method
## Phase-Wise Development Plan

> **Algorithm:** BTC 0DTE options premium selling with automatic adjustment, strike shifting, and close-at-5.
> **Logic Reference:** `MONEY_POWER_CALCULATION_LOGIC.md` (21 sections, sealed)
> **Navigation Position:** MV Straddle → **MMM** → SSR ALGO
> **Isolation Rule:** Entirely separate codebase. Zero impact on existing WebUI or trading logic.

---

## Architecture Overview

```
webui/
├── backend/
│   └── routes/
│       └── mmm/                          ← NEW (isolated backend module)
│           ├── __init__.py               ← Blueprint registration, init_mmm()
│           ├── mmm_api.py                ← REST API endpoints
│           ├── mmm_engine.py             ← Core adjustment engine (Sections 4-6)
│           ├── mmm_state.py              ← State management (Section 2)
│           ├── mmm_trigger.py            ← Trigger system (Section 7)
│           ├── mmm_strike_shift.py       ← Strike shifting logic (Section 10)
│           ├── mmm_close_at_5.py         ← Close-at-5 rule (Section 11)
│           ├── mmm_safety.py             ← Safety mechanisms (Sections 13-14)
│           ├── mmm_reversal.py           ← Reversal detection & first-reversal P&L (Section 9)
│           ├── mmm_initializer.py        ← Auto-find strikes & import existing (Section 3)
│           ├── mmm_monitor.py            ← Background heartbeat loop (Section 4)
│           ├── mmm_storage.py            ← Session persistence (JSON/SQLite)
│           ├── mmm_websocket.py          ← WebSocket events for real-time UI updates
│           └── mmm_config.py             ← Default parameters, hot-reload support (Section 19)
│
├── frontend/
│   └── src/
│       └── components/
│           └── mmm/                      ← NEW (isolated frontend module)
│               ├── index.js              ← Barrel exports
│               ├── MMMDashboard.js       ← Main dashboard container
│               ├── MMMConfigPanel.js     ← Entry configuration form
│               ├── MMMSessionCard.js     ← Active/historical session cards
│               ├── MMMPositionsTable.js  ← Live positions view (active + frozen)
│               ├── MMMTriggerGauge.js    ← Visual trigger/safe-zone gauge
│               ├── MMMAdjustmentLog.js   ← Adjustment history timeline
│               ├── MMMPnLChart.js        ← Real-time P&L graph
│               ├── MMMSafetyPanel.js     ← Safety status indicators
│               ├── MMMStrikeMap.js       ← Strike shift visualization
│               ├── MMMBothSidesAlert.js  ← Both-sides-up user decision modal
│               ├── MMMStatusBanner.js    ← Top status bar (running/paused/stopped)
│               ├── MMMErrorBoundary.js   ← Error boundary wrapper
│               ├── mmmService.js         ← API service (axios calls)
│               ├── MMMContext.js          ← React context for shared state
│               ├── hooks/
│               │   ├── useMMMSession.js  ← Session management hook
│               │   ├── useMMMWebSocket.js← WebSocket subscription hook
│               │   └── useMMMParams.js   ← Hot-reload parameter hook
│               └── utils/
│                   ├── mmmCalculations.js← Client-side P&L preview math
│                   └── mmmFormatters.js  ← Number, time, strike formatters
```

---

## Integration Points (Minimal, Non-Invasive)

Only **3 existing files** will be touched — all with additive-only changes:

| File | Change | Risk |
|------|--------|------|
| `webui/backend/app.py` | Add `register_blueprint(mmm_bp)` block (same as SSR ALGO pattern) | None — isolated try/except |
| `webui/frontend/src/App.js` | Add `mmm` tab to `navigationTabs` array + lazy import + `sectionContent` entry | None — additive only |
| `webui/frontend/src/components/mmm/index.js` | New file (barrel export) | None — new file |

All other files are **NEW** — no existing file is modified.

---

## Phase Plan

---

### PHASE 1: Foundation — State, Storage & API Skeleton
**Duration:** 2-3 days
**Logic Sections:** 2, 19
**Goal:** Build the data layer and empty API endpoints that the UI can connect to immediately.

#### Backend Tasks

| # | Task | File | Logic Section |
|---|------|------|---------------|
| 1.1 | Define `MMMSession` dataclass with per-side state, global state, and all parameters from Section 19 | `mmm_state.py` | §2, §19 |
| 1.2 | Create `MMMStorage` class — save/load sessions to `mmm_sessions.json` with file locking | `mmm_storage.py` | — |
| 1.3 | Create `MMMConfig` class — default values for all 19 parameters, hot-reload support via WebSocket | `mmm_config.py` | §19 |
| 1.4 | Create Flask blueprint with `url_prefix='/api/mmm'` | `mmm_api.py` | — |
| 1.5 | Implement CRUD endpoints: `POST /session`, `GET /sessions`, `GET /session/<id>`, `DELETE /session/<id>` | `mmm_api.py` | — |
| 1.6 | Implement control endpoints: `POST /session/<id>/start`, `/pause`, `/resume`, `/stop` | `mmm_api.py` | — |
| 1.7 | Implement parameter update: `PATCH /session/<id>/params` with hot-reload | `mmm_api.py` | §19 |
| 1.8 | Create `__init__.py` with `init_mmm()` for startup restoration | `__init__.py` | — |
| 1.9 | Register blueprint in `app.py` (isolated try/except block) | `app.py` | — |

#### Frontend Tasks

| # | Task | File |
|---|------|------|
| 1.10 | Create `mmmService.js` — API client matching all backend endpoints | `mmmService.js` |
| 1.11 | Create `MMMContext.js` — React context provider for session state | `MMMContext.js` |
| 1.12 | Create empty `MMMDashboard.js` shell with tabs: Config / Active / History | `MMMDashboard.js` |
| 1.13 | Create `MMMErrorBoundary.js` (copy SSR ALGO pattern) | `MMMErrorBoundary.js` |
| 1.14 | Create `index.js` barrel export | `index.js` |
| 1.15 | Add MMM tab to `App.js` navigation — positioned between MV Straddle and SSR ALGO | `App.js` |

#### Deliverable
- Backend starts without errors, blueprint registered
- MMM tab appears in WebUI navigation at correct position
- Empty dashboard renders with tabs
- API endpoints return proper responses (empty sessions list, create/delete works)

---

### PHASE 2: Initialization Engine — Auto-Find Strikes & Import
**Duration:** 2-3 days
**Logic Sections:** 3, 15
**Goal:** User can enter desired premiums → algo finds strikes → user confirms → session created with full state.

#### Backend Tasks

| # | Task | File | Logic Section |
|---|------|------|---------------|
| 2.1 | Create `MMMInitializer` class with `auto_find_strikes(desired_ce_prem, desired_pe_prem, expiry)` | `mmm_initializer.py` | §3 Mode A |
| 2.2 | Implement options chain fetching via existing Deribit/Delta API client | `mmm_initializer.py` | §15.3 |
| 2.3 | Strike selection: scan OTM calls/puts, find closest to desired premium, prefer further OTM on tie | `mmm_initializer.py` | §3 Mode A |
| 2.4 | Add `POST /api/mmm/preview-strikes` — returns found strikes without executing | `mmm_api.py` | §3 |
| 2.5 | Add `POST /api/mmm/session/start-fresh` — auto-find + execute + initialize state | `mmm_api.py` | §3 Mode A |
| 2.6 | Add `POST /api/mmm/session/import` — import existing positions, skip execution | `mmm_api.py` | §3 Mode B |
| 2.7 | Implement order execution (sell N lots CE + PE) using existing order execution infrastructure | `mmm_initializer.py` | §3 |
| 2.8 | Implement fill verification and state initialization from actual fills | `mmm_initializer.py` | §3 |
| 2.9 | Fetch available BTC expiries from exchange for expiry dropdown | `mmm_initializer.py` | §15.2 |

#### Frontend Tasks

| # | Task | File |
|---|------|------|
| 2.10 | Build `MMMConfigPanel.js` — "Fresh Entry" form: desired CE/PE premium, lots, expiry dropdown | `MMMConfigPanel.js` |
| 2.11 | Add "Import Existing" tab: CE strike/premium/lots, PE strike/premium/lots, expiry | `MMMConfigPanel.js` |
| 2.12 | "Preview Strikes" button — calls preview API, shows found strikes with premiums | `MMMConfigPanel.js` |
| 2.13 | Confirmation dialog: "Found CE@100000 (prem 98.5), PE@96000 (prem 101.2) — Confirm?" with 5-sec countdown | `MMMConfigPanel.js` |
| 2.14 | Display real-time BTC spot price on the config panel | `MMMConfigPanel.js` |
| 2.15 | Parameter controls: all 19 params from Section 19 with tooltips explaining each | `MMMConfigPanel.js` |

#### Deliverable
- User types desired premium → sees found strikes → confirms → positions sold → session running
- Import mode creates session from existing positions without placing orders
- All parameters configurable before entry

---

### PHASE 3: Core Engine — Heartbeat, Triggers & Adjustments
**Duration:** 4-5 days
**Logic Sections:** 4, 5, 6, 7
**Goal:** The core adjustment loop runs in background, monitors premiums, calculates losses, sells opposite side.

#### Backend Tasks

| # | Task | File | Logic Section |
|---|------|------|---------------|
| 3.1 | Create `MMMMonitor` class with background thread running every `interval` seconds | `mmm_monitor.py` | §4 |
| 3.2 | Implement premium fetching (mark price for monitoring, bid for selling, ask for buying back) | `mmm_monitor.py` | §15.5 |
| 3.3 | Implement trigger evaluation: `ce_excess`, `pe_excess`, `min_trigger_move` filter | `mmm_trigger.py` | §7 |
| 3.4 | Implement `MMMEngine.calculate_adjustment()` — standard loss formula | `mmm_engine.py` | §5 Case A |
| 3.5 | Implement lots calculation with ceiling, buffer, and constraints (cap, max_lots) | `mmm_engine.py` | §5.4 |
| 3.6 | Implement order execution for adjustments (sell opposite side lots) | `mmm_engine.py` | §5.5 |
| 3.7 | Implement state update — record fill, update BOTH triggers, update tracking | `mmm_engine.py` | §6 |
| 3.8 | Implement the 4 heartbeat outcomes: neither/CE/PE/both triggered | `mmm_monitor.py` | §4.7 |
| 3.9 | Add margin check before every sell order | `mmm_engine.py` | §13.7 |
| 3.10 | Implement `start_session_monitor()` and `stop_session_monitor()` | `mmm_monitor.py` | — |
| 3.11 | Implement monitor pause/resume with state preservation | `mmm_monitor.py` | — |

#### Frontend Tasks

| # | Task | File |
|---|------|------|
| 3.12 | Build `MMMPositionsTable.js` — live table: side, strike, lots (orig + adj), entry prem, current prem, P&L per row | `MMMPositionsTable.js` |
| 3.13 | Build `MMMTriggerGauge.js` — visual gauge showing current premium vs trigger per side, safe zone band | `MMMTriggerGauge.js` |
| 3.14 | Build `MMMAdjustmentLog.js` — timeline of all adjustments: time, side, lots, premium, loss covered | `MMMAdjustmentLog.js` |
| 3.15 | Build `MMMStatusBanner.js` — shows RUNNING/PAUSED/STOPPED, elapsed time, interval countdown, adjustment count | `MMMStatusBanner.js` |
| 3.16 | Implement `useMMMWebSocket.js` — subscribe to `mmm_update`, `mmm_adjustment`, `mmm_alert` events | `useMMMWebSocket.js` |
| 3.17 | Build `MMMSessionCard.js` — card view of each session with summary stats | `MMMSessionCard.js` |

#### Deliverable
- Background heartbeat loop running
- Adjustments fire when premium exceeds trigger + min_move
- Positions table updates in real-time via WebSocket
- Trigger gauge shows safe zone visually
- Adjustment log shows each action

---

### PHASE 4: Reversal Detection & Multi-Reversal Cycles
**Duration:** 2-3 days
**Logic Sections:** 5 (Case B), 9, 12
**Goal:** Properly handle direction changes — first reversal uses adjustment P&L, subsequent use standard formula.

#### Backend Tasks

| # | Task | File | Logic Section |
|---|------|------|---------------|
| 4.1 | Implement `MMMReversal.detect_reversal()` — checks `last_aggressor` vs current aggressor | `mmm_reversal.py` | §9 |
| 4.2 | Implement first-reversal P&L calculation — per-fill, per-strike across active + frozen | `mmm_reversal.py` | §5 Case B, §9 |
| 4.3 | Implement "adjustments still profitable → DO NOTHING" logic | `mmm_reversal.py` | §9 |
| 4.4 | Implement cooldown on reversal — optional skip of 1 interval | `mmm_reversal.py` | §14.3 |
| 4.5 | Integrate reversal checks into the heartbeat loop (Step 5.1 decision) | `mmm_monitor.py` | §4, §5.1 |
| 4.6 | Ensure multi-reversal cycles track adjustment fills per side cumulatively | `mmm_state.py` | §12 |

#### Frontend Tasks

| # | Task | File |
|---|------|------|
| 4.7 | Add reversal indicator to `MMMStatusBanner.js` — "REVERSAL DETECTED" label with cooldown countdown | `MMMStatusBanner.js` |
| 4.8 | Color-code adjustment log entries: green (standard), orange (reversal), gray (skipped/cooldown) | `MMMAdjustmentLog.js` |
| 4.9 | Show adjustment P&L breakdown in reversal entries — per-fill P&L detail tooltip | `MMMAdjustmentLog.js` |

#### Deliverable
- First reversal correctly computes adjustment P&L and only hedges if underwater
- Cooldown skips one interval on reversal
- Multi-reversal cycles work across 3+ direction changes
- UI clearly shows reversal events

---

### PHASE 5: Strike Shifting & Close-at-5
**Duration:** 3-4 days
**Logic Sections:** 10, 11
**Goal:** When premium too low, shift to closer strike. Close positions at ≤5 to lock profit.

#### Backend Tasks

| # | Task | File | Logic Section |
|---|------|------|---------------|
| 5.1 | Implement `MMMStrikeShift.check_shift_needed()` — premium < `shift_threshold` | `mmm_strike_shift.py` | §10 |
| 5.2 | Implement `MMMStrikeShift.find_new_strike()` — scan chain, filter ≥ threshold, closest to target premium, liquidity check | `mmm_strike_shift.py` | §10 |
| 5.3 | Implement freeze logic — move active positions to `frozen_positions`, set new `active_strike` | `mmm_strike_shift.py` | §10 |
| 5.4 | Handle "no available strike" edge case — alert user (Section 20.3) | `mmm_strike_shift.py` | §20.3 |
| 5.5 | Implement `MMMCloseAt5.scan_and_close()` — check ALL positions every interval | `mmm_close_at_5.py` | §11 |
| 5.6 | Implement profit locking — buy back at market/ask, record realized P&L | `mmm_close_at_5.py` | §11 |
| 5.7 | Handle "side fully closed" → auto-find new strike for that side (Section 11 consequence) | `mmm_close_at_5.py` | §11 |
| 5.8 | Handle "both sides fully closed" → strategy complete, best outcome | `mmm_close_at_5.py` | §11 |
| 5.9 | Integrate strike shift check into adjustment flow (between Step 5.3 and 5.4) | `mmm_engine.py` | §5.3 |
| 5.10 | Integrate close-at-5 into heartbeat loop (Step 3 of heartbeat) | `mmm_monitor.py` | §4 |

#### Frontend Tasks

| # | Task | File |
|---|------|------|
| 5.11 | Build `MMMStrikeMap.js` — visual map of all strikes with positions (active = bright, frozen = dimmed) | `MMMStrikeMap.js` |
| 5.12 | Show strike shift events in adjustment log with before/after strike info | `MMMAdjustmentLog.js` |
| 5.13 | Show frozen positions in positions table with "FROZEN" badge and current premium | `MMMPositionsTable.js` |
| 5.14 | Close-at-5 events in log with green "PROFIT LOCKED" badge and realized amount | `MMMAdjustmentLog.js` |
| 5.15 | Realized vs unrealized P&L split in P&L chart | `MMMPnLChart.js` |

#### Deliverable
- Strike shift fires when opposing premium < threshold
- Old positions frozen, new strike activated
- Positions auto-close at ≤5, profit locked
- Side fully closed → auto-finds new strike
- Both sides closed → strategy complete
- Strike map shows all strikes visually

---

### PHASE 6: Both-Sides-Up Alert & Safety Mechanisms
**Duration:** 3-4 days
**Logic Sections:** 8, 13, 14
**Goal:** User decision panel for both-sides-up. All 7 safety mechanisms + 7 strength improvements operational.

#### Backend Tasks

| # | Task | File | Logic Section |
|---|------|------|---------------|
| 6.1 | Implement both-sides-up detection (outcome D of heartbeat) | `mmm_monitor.py` | §8 |
| 6.2 | Emit `mmm_both_sides_alert` WebSocket event with CE/PE details and 4 options | `mmm_websocket.py` | §8 |
| 6.3 | Implement handler for user's choice: ADD / REDUCE / RESUME / STOP | `mmm_api.py` | §8 |
| 6.4 | Implement `MMMSafety` class with all 7 safety checks | `mmm_safety.py` | §13 |
| 6.5 | Position cap with per-side tracking | `mmm_safety.py` | §13.1 |
| 6.6 | Max adjustments counter with WebUI override | `mmm_safety.py` | §13.2 |
| 6.7 | Max loss hard stop — compute unrealized + realized every interval | `mmm_safety.py` | §13.3 |
| 6.8 | Whipsaw detection (3 alternating adjustments) → auto-pause | `mmm_safety.py` | §13.4 |
| 6.9 | Position asymmetry warning/alert at ratio 3/5 | `mmm_safety.py` | §13.5 |
| 6.10 | Near-expiry behavior — stop adjustments at N mins, auto-close at M mins | `mmm_safety.py` | §13.6 |
| 6.11 | Premium buffer calculation (5% default) | `mmm_safety.py` | §14.1 |
| 6.12 | Net P&L guardrail (warning/pause/hard-stop tiers) | `mmm_safety.py` | §14.4 |
| 6.13 | Periodic P&L reconciliation every 5 adjustments | `mmm_safety.py` | §14.5 |
| 6.14 | Trailing profit protection (high-water mark) | `mmm_safety.py` | §14.6 |
| 6.15 | Theta acceleration — widen triggers & intervals near expiry | `mmm_safety.py` | §14.7 |

#### Frontend Tasks

| # | Task | File |
|---|------|------|
| 6.16 | Build `MMMBothSidesAlert.js` — modal dialog with CE/PE details and 4 action buttons | `MMMBothSidesAlert.js` |
| 6.17 | ADD action: inline inputs for lots + side selection | `MMMBothSidesAlert.js` |
| 6.18 | REDUCE action: lot selection per side | `MMMBothSidesAlert.js` |
| 6.19 | Build `MMMSafetyPanel.js` — dashboard showing all safety statuses | `MMMSafetyPanel.js` |
| 6.20 | Visual indicators: position cap %, max adj count, max loss proximity, asymmetry ratio | `MMMSafetyPanel.js` |
| 6.21 | Whipsaw warning banner with suggestion to increase interval | `MMMSafetyPanel.js` |
| 6.22 | Expiry countdown timer with color transitions (green→yellow→red) | `MMMStatusBanner.js` |
| 6.23 | Trailing profit chart overlay showing peak vs current P&L | `MMMPnLChart.js` |
| 6.24 | Audio alert + browser notification for both-sides-up and safety events | `MMMDashboard.js` |

#### Deliverable
- Both-sides-up pauses algo and shows decision modal
- All safety mechanisms fire correctly
- User gets clear visual/audio feedback on every safety event
- Near-expiry auto-close works

---

### PHASE 7: Real-Time P&L, WebSocket & Dashboard Polish
**Duration:** 3-4 days
**Logic Sections:** 6.4, 15, 18
**Goal:** Production-grade real-time dashboard with complete P&L tracking, BTC-specific features, and polished UI.

#### Backend Tasks

| # | Task | File | Logic Section |
|---|------|------|---------------|
| 7.1 | Implement `MMMWebSocket` — structured events for all state changes | `mmm_websocket.py` | §6.4 |
| 7.2 | Events: `mmm_heartbeat`, `mmm_adjustment`, `mmm_close_at_5`, `mmm_shift`, `mmm_reversal`, `mmm_safety`, `mmm_both_sides`, `mmm_pnl_update`, `mmm_params_changed` | `mmm_websocket.py` | — |
| 7.3 | Fee tracking: accumulate fees per trade, include in net P&L | `mmm_engine.py` | §15.8 |
| 7.4 | USD equivalent display: convert BTC-denominated premiums to USD | `mmm_api.py` | §15.4 |
| 7.5 | Liquidity check before every sell order | `mmm_engine.py` | §15.6 |
| 7.6 | API downtime handling: retry with backoff, pause on prolonged failure | `mmm_monitor.py` | §20.5 |
| 7.7 | Session restore on backend restart — pick up running sessions | `mmm_monitor.py` | — |
| 7.8 | Comprehensive logging with structured log format | All files | — |

#### Frontend Tasks

| # | Task | File |
|---|------|------|
| 7.9 | Build `MMMPnLChart.js` — real-time line chart: total P&L, realized, unrealized, fees | `MMMPnLChart.js` |
| 7.10 | Cumulative premium chart overlay | `MMMPnLChart.js` |
| 7.11 | Position heatmap colored by P&L (green=profit, red=loss) | `MMMPositionsTable.js` |
| 7.12 | Adjustment log with expandable rows — full fill details, slippage, overcoverage | `MMMAdjustmentLog.js` |
| 7.13 | Summary stats cards: total premium, net P&L, total fees, adjustments, reversals, shifts, close-at-5 count | `MMMDashboard.js` |
| 7.14 | Hot-reload parameter panel — edit params while running, instant effect | `MMMConfigPanel.js` |
| 7.15 | Mobile-responsive layout | All components |
| 7.16 | Dark theme consistency with existing WebUI theme | All components |

#### Deliverable
- Full real-time dashboard with WebSocket updates
- P&L chart with all overlays
- Hot-reload params work while algo runs
- Session survives backend restart
- Mobile-friendly

---

### PHASE 8: Testing, Edge Cases & Hardening
**Duration:** 3-4 days
**Logic Sections:** 16, 20, 21
**Goal:** Validate all edge cases, simulate walk-through, stress test, and harden for production.

#### Backend Tasks

| # | Task | File |
|---|------|------|
| 8.1 | Unit tests: `test_mmm_engine.py` — standard adjustment math, lots calculation, ceiling, buffer | tests |
| 8.2 | Unit tests: `test_mmm_reversal.py` — first reversal P&L, multi-strike, multi-cycle | tests |
| 8.3 | Unit tests: `test_mmm_strike_shift.py` — shift detection, freeze, new strike selection | tests |
| 8.4 | Unit tests: `test_mmm_close_at_5.py` — close logic, profit locking, side fully closed | tests |
| 8.5 | Unit tests: `test_mmm_safety.py` — all 7 safety mechanisms + 7 strength improvements | tests |
| 8.6 | Integration test: full walk-through from Section 16 (7 intervals, replayed programmatically) | tests |
| 8.7 | Edge case: unequal premiums at entry (§20.1) | tests |
| 8.8 | Edge case: multiple shifts on same side (§20.2) | tests |
| 8.9 | Edge case: no available strike for shift (§20.3) | tests |
| 8.10 | Edge case: user manual adjustment mid-strategy (§20.4) | tests |
| 8.11 | Edge case: API downtime with retry/pause (§20.5) | tests |
| 8.12 | Edge case: extreme move / flash crash (§20.6) | tests |
| 8.13 | Simulation mode: run the full engine against historical BTC data without real orders | `mmm_engine.py` |

#### Frontend Tasks

| # | Task | File |
|---|------|------|
| 8.14 | Error boundary testing — API failures, WebSocket disconnects, malformed data | `MMMErrorBoundary.js` |
| 8.15 | Loading states for all async operations | All components |
| 8.16 | Confirmation dialogs before destructive actions (stop, close all) | `MMMDashboard.js` |

#### Deliverable
- All unit tests pass
- Full Section 16 walk-through validated
- All 6 edge cases from Section 20 handled
- Simulation mode available for dry-run testing

---

## WebUI Design Specification

### Navigation Integration

```javascript
// App.js — navigationTabs array (insert between mv_straddle and ssr_algo)
{
  id: 'mmm',
  label: '💰 MMM',
  icon: TrendingUp,
  description: 'Money Mind & Method — BTC 0DTE premium selling with auto-adjustment',
}
```

**Tab order:** ... → MV Straddle → **MMM** → SSR ALGO → ...

### Dashboard Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  MMM Status Banner [RUNNING ●] [Adj: 5] [Elapsed: 2h 15m] [⏱ 3:42]│
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │
│  │ Total Prem   │  │  Net P&L     │  │  Realized    │  │  Fees    │ │
│  │  $3,690      │  │  +$1,480     │  │  +$1,300     │  │  -$45    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────┘ │
│                                                                      │
│  TABS: [Dashboard] [Positions] [Adjustments] [Safety] [Config]       │
│                                                                      │
│  ┌─ Dashboard Tab ─────────────────────────────────────────────────┐ │
│  │                                                                  │ │
│  │  ┌─ Trigger Gauges ──────────────────────────┐                  │ │
│  │  │                                            │                  │ │
│  │  │  CE Side                 PE Side           │                  │ │
│  │  │  ▓▓▓▓▓▓▓▓░░░░          ▓▓▓▓▓░░░░░░░      │                  │ │
│  │  │  130/190 (safe)          160/190 (safe)    │                  │ │
│  │  │  Strike: 100,000         Strike: 98,000    │                  │ │
│  │  │  Active: 14 lots         Active: 7 lots    │                  │ │
│  │  │  Frozen: 0               Frozen: 0         │                  │ │
│  │  └────────────────────────────────────────────┘                  │ │
│  │                                                                  │ │
│  │  ┌─ P&L Chart ───────────────────────────────┐                  │ │
│  │  │     ╱‾‾‾‾╲           ╱‾‾‾‾‾‾‾‾            │                  │ │
│  │  │    ╱      ╲   ╱‾‾‾‾╱                      │                  │ │
│  │  │───╱────────╲─╱──────────────────── time    │                  │ │
│  │  │  ── total   ── realized   ── unrealized    │                  │ │
│  │  └────────────────────────────────────────────┘                  │ │
│  │                                                                  │ │
│  │  ┌─ Strike Map ──────────────────────────────┐                  │ │
│  │  │  96,000 ○ PE frozen(15) — closed at 5     │                  │ │
│  │  │  98,000 ● PE active(7)  ← current         │                  │ │
│  │  │  ─────── BTC: 99,200 ────────             │                  │ │
│  │  │ 100,000 ● CE active(14) ← current         │                  │ │
│  │  └────────────────────────────────────────────┘                  │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌─ Positions Tab ─────────────────────────────────────────────────┐ │
│  │ Side │ Strike  │ Type     │ Lots │ Entry │ Current │ P&L       │ │
│  │ CE   │ 100,000 │ Original │ 10   │ 100   │ 130     │ -300      │ │
│  │ CE   │ 100,000 │ Adj #3   │ 2    │ 140   │ 130     │ +20       │ │
│  │ CE   │ 100,000 │ Adj #4   │ 2    │ 110   │ 130     │ -40       │ │
│  │ PE   │ 98,000  │ Adj #2   │ 6    │ 110   │ 170     │ -360      │ │
│  │ PE   │ 98,000  │ Adj #5   │ 1    │ 170   │ 170     │ 0         │ │
│  │ PE   │ 96,000  │ FROZEN   │ 15   │ varies│ 4       │ +1,300 ✓  │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌─ Adjustments Tab ──────────────────────────────────────────────┐  │
│  │ #5 │ 14:30 │ Sell 1 PE @98k │ 170 │ Reversal │ Loss: 20     │  │
│  │ #4 │ 14:25 │ Sell 2 CE @100k│ 110 │ Standard │ Loss: 180    │  │
│  │ #3 │ 14:20 │ Sell 2 CE @100k│ 140 │ Reversal │ Loss: 190    │  │
│  │ #2 │ 14:10 │ SHIFT PE 96→98k│ 110 │ Shift    │ Loss: 600    │  │
│  │ #1 │ 14:05 │ Sell 5 PE @96k │ 72  │ Standard │ Loss: 300    │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌─ Safety Tab ───────────────────────────────────────────────────┐  │
│  │ Position Cap:    CE 14/100 ▓░░░  PE 7/100 ▓░░░               │  │
│  │ Adjustments:     5/30     ▓░░░░                               │  │
│  │ Max Loss:        -$520 / -$5000  ▓░░░░░░░░░                   │  │
│  │ Asymmetry:       2.0x            ✅ OK                        │  │
│  │ Whipsaw:         0/3             ✅ OK                        │  │
│  │ Expiry:          5h 30m          🟢 Far                       │  │
│  │ Margin:          $12,400 avail   ✅ OK                        │  │
│  │ Trailing:        Peak $1,800     Current $1,480   ✅ 82%      │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌─ Config Tab ───────────────────────────────────────────────────┐  │
│  │ Interval:         [300] sec   🔥 Hot                          │  │
│  │ Min Trigger Move: [3]         🔥 Hot                          │  │
│  │ Shift Threshold:  [50]        🔥 Hot                          │  │
│  │ Close-at-5:       [5]         🔥 Hot                          │  │
│  │ Buffer:           [5] %       🔥 Hot                          │  │
│  │ Max Lots/Side:    [100]       🔥 Hot                          │  │
│  │ Max Adjustments:  [30]        🔥 Hot                          │  │
│  │ Max Loss:         [$5000]     🔥 Hot                          │  │
│  │ Cooldown:         [✓ On]      🔥 Hot                          │  │
│  │ Trailing Stop:    [50] %      🔥 Hot                          │  │
│  │                                                                │  │
│  │             [Apply Changes ✓]  [Reset Defaults ↺]             │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  [⏸ Pause]  [⏹ Stop]  [🗑 Close All & Stop]                        │
└──────────────────────────────────────────────────────────────────────┘
```

### UI Component Details

#### Trigger Gauge (`MMMTriggerGauge.js`)
- Horizontal progress bar per side
- Fill = current premium / trigger level
- Color: green (< 80% of trigger), yellow (80-100%), red (exceeded)
- Show current premium, trigger level, active strike, lots count
- Animated pulse when approaching trigger

#### P&L Chart (`MMMPnLChart.js`)
- Line chart with 3 lines: total, realized, unrealized
- X-axis: time (from entry to now)
- Y-axis: USD value
- Area fill under realized line (green)
- Marker dots on adjustment events
- Peak line overlay for trailing profit tracking
- Using recharts (already in project dependencies)

#### Strike Map (`MMMStrikeMap.js`)
- Vertical axis: strikes ordered by value
- BTC spot price shown as horizontal divider
- Active strikes: bright circle with lot count
- Frozen strikes: dimmed circle with lot count, "(frozen)" label
- Closed strikes: crossed out with realized profit shown
- Strike shift shown as arrow from old to new

#### Both-Sides Alert Modal (`MMMBothSidesAlert.js`)
- Full-screen overlay with backdrop blur
- Shows CE and PE current premiums vs triggers with excess
- 4 large action buttons: ADD / REDUCE / RESUME / STOP
- ADD option shows inline lot input + side selection
- REDUCE shows per-side lot input
- Audio chime + browser push notification
- Stays until user acts — algo paused

#### Safety Panel (`MMMSafetyPanel.js`)
- Grid of safety indicators
- Each indicator: label, value, threshold, progress bar, status icon
- Color coding: green (ok), yellow (approaching), red (breached)
- Click to expand shows details + threshold adjustment

### Design System

| Element | Value |
|---------|-------|
| **Primary Color** | `#00C853` (green — money/profit theme) |
| **Accent Color** | `#FFD600` (gold — premium/wealth) |
| **Danger Color** | `#FF1744` (red — loss/alert) |
| **Card Background** | Follows existing theme (dark: `#1a1a2e`, light: `#fff`) |
| **Font** | Existing WebUI font system |
| **Border Radius** | 12px (cards), 8px (inputs), 20px (badges) |
| **Animations** | Framer Motion for transitions, CSS pulse for alerts |
| **Icons** | Lucide React (consistent with existing WebUI) |
| **Charts** | Recharts (consistent with existing WebUI) |

---

## API Endpoints Reference

### Session Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mmm/health` | Health check |
| `GET` | `/api/mmm/sessions` | List all sessions |
| `GET` | `/api/mmm/session/<id>` | Get session details |
| `POST` | `/api/mmm/session` | Create session (import mode) |
| `DELETE` | `/api/mmm/session/<id>` | Delete session |

### Initialization
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mmm/expiries` | Get available BTC expiries |
| `POST` | `/api/mmm/preview-strikes` | Preview strikes for desired premiums |
| `POST` | `/api/mmm/start-fresh` | Auto-find + execute + start |
| `POST` | `/api/mmm/import` | Import existing positions + start |

### Session Control
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/mmm/session/<id>/start` | Start monitoring |
| `POST` | `/api/mmm/session/<id>/pause` | Pause monitoring |
| `POST` | `/api/mmm/session/<id>/resume` | Resume monitoring |
| `POST` | `/api/mmm/session/<id>/stop` | Stop and optionally close positions |

### Real-Time Data
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mmm/session/<id>/status` | Full status snapshot |
| `GET` | `/api/mmm/session/<id>/positions` | All positions (active + frozen) |
| `GET` | `/api/mmm/session/<id>/adjustments` | Adjustment history |
| `GET` | `/api/mmm/session/<id>/pnl` | P&L breakdown |
| `GET` | `/api/mmm/session/<id>/triggers` | Current trigger values |

### Parameters
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/mmm/session/<id>/params` | Get current parameters |
| `PATCH` | `/api/mmm/session/<id>/params` | Update hot-reload params |

### User Actions
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/mmm/session/<id>/both-sides-action` | Handle both-sides-up decision |
| `POST` | `/api/mmm/session/<id>/manual-adjust` | User manual position change |
| `POST` | `/api/mmm/session/<id>/close-all` | Close all positions immediately |

### WebSocket Events (Emitted)
| Event | Payload | When |
|-------|---------|------|
| `mmm_heartbeat` | `{session_id, ce_premium, pe_premium, triggers, status}` | Every interval |
| `mmm_adjustment` | `{session_id, side, lots, premium, strike, loss_covered, type}` | On adjustment |
| `mmm_reversal` | `{session_id, from_side, to_side, adj_pnl, action}` | On reversal |
| `mmm_shift` | `{session_id, side, old_strike, new_strike, frozen_lots}` | On strike shift |
| `mmm_close_at_5` | `{session_id, side, strike, lots, realized_pnl}` | On close-at-5 |
| `mmm_both_sides` | `{session_id, ce_details, pe_details}` | Both sides up |
| `mmm_safety` | `{session_id, type, level, message}` | Safety event |
| `mmm_pnl_update` | `{session_id, total, realized, unrealized, fees}` | Every interval |
| `mmm_params_changed` | `{session_id, changed_params}` | On hot-reload |

---

## File Count Summary

| Category | New Files | Existing Files Modified |
|----------|-----------|------------------------|
| Backend (routes/mmm/) | 14 files | 0 |
| Frontend (components/mmm/) | 18 files | 0 |
| Integration | 0 | 2 (app.py, App.js) |
| Tests | 6+ files | 0 |
| **Total** | **38+ files** | **2 files** |

---

## Phase Timeline

| Phase | Duration | Cumulative | What's Working After |
|-------|----------|------------|---------------------|
| **1: Foundation** | 2-3 days | 2-3 days | MMM tab visible, empty dashboard, API skeleton |
| **2: Initialization** | 2-3 days | 4-6 days | Auto-find strikes, start sessions, config panel |
| **3: Core Engine** | 4-5 days | 8-11 days | Heartbeat running, adjustments firing, live positions |
| **4: Reversals** | 2-3 days | 10-14 days | Direction changes handled, multi-reversal cycles |
| **5: Strike Shift + Close-at-5** | 3-4 days | 13-18 days | Full adjustment engine complete |
| **6: Safety + Both-Sides** | 3-4 days | 16-22 days | All safety mechanisms, user decision modal |
| **7: Dashboard Polish** | 3-4 days | 19-26 days | Production-grade UI, WebSocket real-time |
| **8: Testing** | 3-4 days | 22-30 days | Battle-tested, all edge cases covered |

**Total estimated:** 22-30 working days

---

## Development Rules

1. **Isolation first:** Every new file lives under `routes/mmm/` or `components/mmm/`. No imports from MMM into existing code. Only 2 files touched (additive).

2. **Follow existing patterns:** Blueprint registration matches SSR ALGO. Service file matches `ssrAlgoService.js`. Context matches existing patterns.

3. **Incremental delivery:** Each phase produces a working, testable state. No half-built features.

4. **Logic document drives code:** Every function maps to a section in `MONEY_POWER_CALCULATION_LOGIC.md`. Code comments reference section numbers.

5. **Hot reload tested:** Every `Hot Reload = Yes` parameter must be changeable while running and take effect on the next interval.

6. **WebSocket for everything:** No polling. All state changes push to frontend via WebSocket events.

7. **Error boundaries:** Frontend wraps MMM in `MMMErrorBoundary`. Backend endpoints use try/except. Failures in MMM never crash the main app.

---

*This plan implements the complete MMM algorithm as defined in `MONEY_POWER_CALCULATION_LOGIC.md`, delivers a production-grade WebUI, and maintains strict isolation from all existing code.*
