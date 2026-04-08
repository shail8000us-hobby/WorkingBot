# MMMX WebUI Robustness Plan (Verified Against Backend)
**Date:** 2026-04-07 — updated after full backend audit  
**Branch:** SSR  
**Scope:** Frontend only — zero changes to MMM algo, MMM backend, or MMM frontend  
**Reference:** `mmmx_webUI.md` (spec), `MMMXDashboard.js` (current implementation)  
**Audit source:** `/webui/backend/routes/mmmx/*.py` — field-level verified

---

## Backend Audit Findings (Critical — Plan Corrections)

The original plan contained several assumptions about session fields that do not match the
actual backend schema. These are corrected throughout.

| Assumption in original plan | Reality (from source) | Impact |
|-----------------------------|-----------------------|--------|
| `session._whipsaw.score` | Field is `session._whipsaw_score` (flat int) | Bug in existing `MMMXContext.js` line 117 |
| `session._whipsaw.level` | Derived from `_whipsaw_score` via `get_level()` in `mmmx_engine.py` | Must derive in UI too |
| `session._atm_shield_active` | Does not exist — use `session.shield_event_history` (list) | Phase 3.4 redesign |
| `session._atm_shield_shifts` | Does not exist — use `session.shield_fire_count` (int) | Phase 3.4 redesign |
| `margin_tier`, `margin_used_pct`, `margin_available` | **None of these exist** in backend session schema | Phase 3.3 full redesign |
| Tranche has gamma, theta, vega | Only `entry_delta` + `current_delta` per leg — no other Greeks | Phase 3.5 redesign |
| Heartbeat emits `beat_at` | Heartbeat only emits `timestamp` — `beat_at` does not exist | Phase 3.6 minor fix |
| `session._whipsaw.score` in `SET_SESSION` | Should be `session._whipsaw_score` | Existing bug in `MMMXContext.js` |

### Confirmed Available (No Changes Needed)
- `ce_reserve_remaining`, `pe_reserve_remaining` ✅
- `total_premium_collected`, `profit_booked_total`, `total_hedge_cost_paid`, `tranches_deployed` ✅
- `ce_lot_balance.imbalance_pct` (for portfolio balance) ✅
- `portfolio_pnl`, `portfolio_delta` (on session + in heartbeat) ✅
- `shield_event_history` (list), `shield_fire_count` (int) ✅
- `fees_tracking.total_fees_paid`, `fees_tracking.fee_rate_maker`, `fees_tracking.fee_rate_taker` ✅
- `entry_delta`, `current_delta` per tranche leg ✅
- Heartbeat: `beat_number`, `portfolio_pnl`, `portfolio_delta`, `hard_stop_usd`, `whipsaw_score`, `timestamp` ✅
- `/session/<id>/audit` endpoint ✅
- `/session/<id>/activity` endpoint (returns `{type, label, message, level, timestamp, data}`) ✅
- `/api/mmmx/health` endpoint ✅
- Trigger ladder: `priority`, `trigger_name`, `severity`, `status`, `threshold`, `value`, `excluded_by`, `would_status` ✅

---

## Existing Bug — Fix in Phase 0

**File:** `webui/frontend/src/components/mmmx/MMMXContext.js` line 117  
**Bug:** `whipsaw_score: s?._whipsaw?.score ?? 0`  
**Fix:** `whipsaw_score: s?._whipsaw_score ?? 0`

**Impact:** After a REST `GET /session/<id>`, the whipsaw score in the UI is always 0 until the
next `mmmx_whipsaw` WebSocket event fires. This means the RiskTab whipsaw display is wrong
immediately after session load or page refresh.

---

## Gap Analysis Summary (Corrected)

| Dimension | MMM | MMMX | Gap Severity |
|-----------|-----|------|-------------|
| Code organization | 40+ separate component files | 1 monolith (3,500+ lines) | Critical |
| Error boundaries | `MMMErrorBoundary` per section | None | Critical |
| P&L chart | `MMMPnLChart` (visual area chart) | Number only | High |
| Delta exposure panel | `MMMGreeksPanel` (delta + drift) | No panel | High |
| Persistent right risk pane | N/A (spec §3.4) | Not implemented | High |
| Regime panel | `MMMRegimePanel` | Whipsaw chip only | Medium |
| Health radar | `MMMHealthRadar` (spider chart) | Score number only | Medium |
| Performance analytics | `MMMPerformancePanel` | None | Medium |
| Trade audit panel | `MMMTradeAuditPanel` | Activity log only | Medium |
| Dedicated safety panel | `MMMSafetyPanel` | Mixed in activity feed | Medium |
| Fees & capital panel | N/A | None | Medium |
| Snackbar/toast feedback | `<Snackbar>` on all actions | Silent on action results | Medium |
| Visibility-aware polling | `useVisibilityAwarePolling` | Raw intervals | Low |
| Safety / integrity features | None | Full suite (MMMX wins) | N/A |

**Removed from original plan** (no backend data):
- `MMMXMarginGuardianPanel` → replaced by `MMMXFeesCapitalPanel` (uses real fields)
- `MMMXGreeksPanel` (full Greeks) → replaced by `MMMXDeltaExposurePanel` (delta only, real fields)

---

## Phase 0 — Bug Fixes (Do First, Zero Risk)

**Prerequisite:** None. These are one-line fixes before any new work.

| # | File | Bug | Fix |
|---|------|-----|-----|
| 0.1 | `MMMXContext.js:117` | `s?._whipsaw?.score ?? 0` reads wrong field | Change to `s?._whipsaw_score ?? 0` |
| 0.2 | `MMMXContext.js:117` | `imbalance_pct` is read from `s?.ce_lot_balance?.imbalance_pct` | ✅ Already correct — no change needed |

**Acceptance:** After page refresh + session load, the whipsaw score in the Risk tab matches
the value shown in `_whipsaw_score` in the backend session JSON.

---

## Phase 1 — Code Architecture Refactoring

**Goal:** Break the 3,500-line `MMMXDashboard.js` monolith into separate files matching MMM's
structure.  
**Risk:** Zero — pure extraction, no behavior change.  
**Outcome:** `MMMXDashboard.js` becomes a ~300-line orchestration shell.

### 1.1 Utility files

| New file | Content to extract | Real fields used |
|----------|--------------------|-----------------|
| `utils/mmmxFormatters.js` | `fmt`, `pnlColor`, `parseIsoToMs`, `heartbeatAgeSec`, `formatEta`, `computeDTE` | Pure functions, no session fields |
| `utils/mmmxDerivations.js` | `deriveIntegrityState`, `deriveConfidence`, `deriveSystemHealth`, `buildIncidentQueue`, `deriveRecommendations`, `deriveExecutionIncidents` | `risk.*`, `session.status`, `session.reconcile_required`, `session.hedges[].status` |

### 1.2 Core UI component files

| New file | Extract from | Real fields / props |
|----------|-------------|---------------------|
| `MMMXErrorBoundary.js` | New (write fresh) | None — pure React class component |
| `MMMXSessionCard.js` | `MMMXDashboard.js` ~line 500–750 | `s.session_id`, `s.status`, `s._last_beat_at`, `s.portfolio_pnl`, `s.expiry_date`, `s.expiry_ddmmyy` |
| `MMMXTopCommandStrip.js` | `MMMXDashboard.js` | `session`, `isConnected`, `integrityState`, `confidence`, `health`, `incidents`, `risk.kill_switch_progress` |
| `MMMXIncidentQueuePanel.js` | `MMMXDashboard.js` | `incidents[]` with `level`, `title`, `escalates_in_sec` |
| `MMMXCriticalModePanel.js` | `MMMXDashboard.js` | `session`, `incidents`, `recommendations` |
| `MMMXCreateSessionDialog.js` | `MMMXDashboard.js` | `CreateSessionDialog` + `DeployTr1Dialog` |

### 1.3 Tab component files

Each tab receives its data via `useMMMX()` hook internally — no prop drilling.

| New file | Content | Key `useMMMX()` fields used |
|----------|---------|----------------------------|
| `MMMXStatusTab.js` | StatusTab (lines ~1367–1895) | `session`, `risk`, `contract`, `activity`, `execution` |
| `MMMXTranchesTab.js` | TranchesTab | `session.tranches[]` — `tranche_id`, `type`, `status`, `ce_strike`, `pe_strike`, `ce_premium`, `pe_premium`, `lots`, `realized_pnl`, `opened_at` |
| `MMMXHedgesTab.js` | HedgesTab | `session.hedges[]` — `hedge_id`, `status`, `symbol`, `lots`, `entry_price`, `parent_tranche_id` |
| `MMMXTriggerEngineTab.js` | TriggerEngineTab | `risk.trigger_winner`, `risk.trigger_ladder[]` — `priority`, `trigger_name`, `status`, `threshold`, `value`, `excluded_by`, `would_status` |
| `MMMXRiskTab.js` | RiskTab | `risk.whipsaw_score`, `risk.circuit_breaker_state`, `risk.imbalance_pct`, `risk.portfolio_delta`, `risk.deployment_eligible_tranches` |
| `MMMXExecutionTab.js` | ExecutionTab | `execution.timeline[]` — `event_name`, `symbol`, `side`, `filled_size`, `residual_size`, `avg_price`, `timestamp` |
| `MMMXAdjustmentsTab.js` | AdjustmentsTab | `activity[]` — `type`, `label`, `message`, `level`, `timestamp`, `data` |
| `MMMXProfitBookingTab.js` | ProfitBookingTab | `session.tranches[]`, `session.profit_booked_total`, `session._profit_booking_queue[]` |
| `MMMXParametersTab.js` | ParametersTab | `session.params` (full dict), `session.session_id` |
| `MMMXReconcileTab.js` | ReconcileTab | `session.session_id`, `session.reconcile_required` |

### 1.4 Acceptance criteria
- All existing tabs render identically before and after extraction
- No new props, no new state — only import paths change
- Each extracted file uses `useMMMX()` to access context directly
- `MMMXDashboard.js` drops below 350 lines

---

## Phase 2 — UX Foundation Parity with MMM

**Goal:** Add structural UX robustness features that MMM has and MMMX is missing.  
**Risk:** Low — all additions.  
**Prerequisite:** Phase 1 complete.

### 2.1 Error Boundaries

Wrap every `<TabPanel>` and the right panel in `<MMMXErrorBoundary name="TabName">`:

```jsx
<TabPanel value={detailTab} index={0}>
  <MMMXErrorBoundary name="Status">
    <MMMXStatusTab ... />
  </MMMXErrorBoundary>
</TabPanel>
```

- Crash in one tab shows a red "Panel error — reload tab" card, not a blank dashboard
- Matches `MMMErrorBoundary` pattern used in MMM

### 2.2 Snackbar Feedback

Add `snackbar` state + `<Snackbar>` in `MMMXDashboard.js`. Surface `runControl` results:

```js
const [snackbar, setSnackbar] = useState(null);
// { message: string, severity: 'success'|'error'|'warning' }
```

Fire on: pause/resume success, deploy success/failure, force heartbeat result,
hot reload applied/rejected, kill switch accepted/failed. Currently all of these fail silently.

### 2.3 Visibility-Aware Polling

Replace raw `setInterval` in `MMMXDashboard.js` session-list refresh with the already-
available hook:

```js
import useVisibilityAwarePolling from '../../hooks/useVisibilityAwarePolling';
// Active: every 15s when tab visible; Background: every 60s when hidden
useVisibilityAwarePolling(fetchSessions, 15_000, 60_000, true);
```

Hook at: `src/hooks/useVisibilityAwarePolling.js` — already used by MMM, safe to reuse.

### 2.4 Acceptance criteria
- Any tab crash shows an isolated error card, not a blank dashboard
- Every mutating control action shows a success or error toast within 2 seconds
- Session list polling stops at full rate when window/tab is hidden

---

## Phase 3 — Missing Analytics Panels

**Goal:** Add the visual/analytics panels MMM has that MMMX lacks.  
**Risk:** Low — each panel is additive.  
**Prerequisite:** Phase 1 complete. Phase 0 (bug fix) must be done before 3.4.

All data sources are verified against actual backend schema.

---

### 3.1 MMMXSafetyPanel.js (P1 — zero new data)

Dedicated safety event stream split out from the generic activity log.

**Data source:**  
`activity[]` filtered to `type === 'safety'`  
Activity log returns: `{ type, label, message, level, timestamp, data }` per entry  
Severity mapping: `level` field values are `'info'`, `'warning'`, `'critical'`

**Visual:**
- Severity-color list: critical (red) → warning (amber) → info (grey)
- Each row: severity chip | timestamp | `data.safety_type` badge | message text
- "Critical" entries pinned to top regardless of time
- Empty state: "No safety events in this session"

**Integration:** Add as a collapsible card in the lower half of **Status tab**,
below the recommendations section.  
**File:** `webui/frontend/src/components/mmmx/MMMXSafetyPanel.js`

---

### 3.2 MMMXTradeAuditPanel.js (P1 — uses existing `/audit` endpoint)

Full trade audit trail with filtering.

**Data source:**  
`mmmxService.getAuditLog(sessionId, 200)` — confirmed endpoint: `GET /session/<id>/audit?limit=200`  
Returns `{ ok, data: [events], count }`  
Event structure: `{ type, event_type, client_order_id, symbol, side, qty, price, fees, timestamp, data }`  
Event categories include: TRADE (fills), EVENT:TRIGGER, EVENT:SAFETY, EVENT:SHIELD, EVENT:DEPLOY, etc.

**Visual:**
- Table: timestamp | category | side | symbol | qty | price | result
- Filter row: category dropdown, side (CE/PE/ALL), symbol text search
- Expandable row: full payload JSON (via `<Accordion>`)
- "TRADE" rows colored by side (CE = blue, PE = orange)

**Integration:** Replace the current thin `AdjustmentsTab` with this panel.
Rename tab label from "Adjustments" to "Audit".  
**File:** `webui/frontend/src/components/mmmx/MMMXTradeAuditPanel.js`

---

### 3.3 MMMXFeesCapitalPanel.js (P2 — replaces original Margin Guardian plan)

> ⚠ **Original plan had `MMMXMarginGuardianPanel` using `margin_tier`, `margin_used_pct`, etc.
> None of these fields exist in the backend. Redesigned as Fees & Capital Panel using real fields.**

Capital allocation + fees tracking panel.

**Data source (all verified in backend schema):**

| Field | Source |
|-------|--------|
| `fees_tracking.total_fees_paid` | `session.fees_tracking.total_fees_paid` |
| `fees_tracking.fee_rate_maker` | `session.fees_tracking.fee_rate_maker` (default 0.0002) |
| `fees_tracking.fee_rate_taker` | `session.fees_tracking.fee_rate_taker` |
| `fees_tracking.last_fee_charge` | `session.fees_tracking.last_fee_charge` (timestamp) |
| `total_budget_lots` | `session.total_budget_lots` |
| `total_deployed_lots` | `session.total_deployed_lots` |
| `tranches_remaining` | `session.tranches_remaining` |
| `deployments_last_24h` | `session.deployments_last_24h` |

**Visual:**
- Row 1 — Capital: Budget lots | Deployed lots | Remaining tranches | Deployments last 24h
- Row 2 — Fees: Total fees paid (USD) | Maker rate | Taker rate | Last fee timestamp
- Fee-to-premium ratio: `fees_tracking.total_fees_paid / total_premium_collected`

**Integration:** Add as a section at the bottom of the **Risk tab**.  
**File:** `webui/frontend/src/components/mmmx/MMMXFeesCapitalPanel.js`

---

### 3.4 MMMXRegimePanel.js (P2 — field references corrected)

> ⚠ **Original plan referenced `session._whipsaw.score`, `session._atm_shield_active`,
> `session._atm_shield_shifts` — none exist. Corrected below.**

ATM shield + whipsaw regime state machine with event trail.

**Data source (corrected field names):**

| UI need | Correct backend field | Notes |
|---------|-----------------------|-------|
| Whipsaw score | `session._whipsaw_score` (int) | After Phase 0 bug fix, also in `risk.whipsaw_score` |
| Whipsaw level | Derive from score (same logic as `mmmx_engine.get_level`) | NORMAL: 0–1, CAUTION: 2, RESTRICT: 3, COOLDOWN: 4+ |
| Cooldown skip-until | `session._whipsaw_skip_until` (ISO timestamp or null) | Present when score ≥ cooldown threshold |
| Last noise event | `session._whipsaw_last_noise_at` (ISO timestamp or null) | |
| ATM shield active | `session.shield_event_history.length > 0` AND last event is recent | No boolean flag — derive from history |
| Shield fire count | `session.shield_fire_count` (int, default 0) | |
| Shield event trail | `session.shield_event_history` (list, last N events) | Each has timestamp + event data |

**Whipsaw level derivation (match backend `mmmx_engine.get_level`):**
```js
function deriveWhipsawLevel(score, params) {
  const cooldown = params?.whipsaw_cooldown_score ?? 4;
  const restrict = params?.whipsaw_restrict_score ?? 3;
  const caution  = params?.whipsaw_caution_score  ?? 2;
  if (score >= cooldown) return 'COOLDOWN';
  if (score >= restrict) return 'RESTRICT';
  if (score >= caution)  return 'CAUTION';
  return 'NORMAL';
}
```

**Visual:**
- State chip row: NORMAL → CAUTION → RESTRICT → COOLDOWN (current highlighted)
- Cooldown countdown: if `_whipsaw_skip_until` is in future, show time remaining
- Shield section: fire count badge + last 5 events from `shield_event_history`
- Each shield event: timestamp + any available event data

**Integration:** Replace the basic whipsaw `<Chip>` in `MMMXRiskTab.js` with this full panel.  
**File:** `webui/frontend/src/components/mmmx/MMMXRegimePanel.js`

---

### 3.5 MMMXDeltaExposurePanel.js (P2 — redesigned from Greeks panel)

> ⚠ **Original plan was `MMMXGreeksPanel` with gamma, theta, vega — none exist in backend.
> Redesigned as Delta Exposure Panel using the two delta fields that DO exist.**

Per-tranche delta exposure and drift tracking.

**Data source (verified):**

Each tranche leg (accessible via `session.tranches[]`) has:
- `entry_delta` — delta at time of deployment (float)
- `current_delta` — live delta from listener updates (float, may be null if listener not yet set)

Tranche-level fields available:
- `tranche_id`, `type` (deploy/recovery/shield), `status`, `ce_strike`, `pe_strike`, `lots`

**Visual:**
- Table: Tranche | Type | Lots | CE Δ entry | CE Δ now | CE Δ drift | PE Δ entry | PE Δ now | PE Δ drift
- Δ drift = `abs(current_delta - entry_delta)` — colored amber if > 50% of `delta_drift_threshold` param
- Portfolio totals row: sum of CE deltas, sum of PE deltas, net delta
- "No data" gracefully shown when `current_delta` is null (listener not yet updating)
- Closed tranches greyed out

**Note:** Gamma, theta, vega are NOT available from the backend. If needed in future, they
require backend listener work (see §Backend Work Required section).

**Integration:** Add as a card below the tranche table in the **Tranches tab**.  
**File:** `webui/frontend/src/components/mmmx/MMMXDeltaExposurePanel.js`

---

### 3.6 MMMXPnLChart.js (P3 — requires one context addition)

Portfolio P&L history chart over beats. Matching `MMMPnLChart` visual pattern.

**Context change required in `MMMXContext.js`:**

```js
// Add to INIT:
pnlHistory: [],  // [{ beat_number, portfolio_pnl, timestamp }]

// Add reducer case:
case 'PUSH_PNL_HISTORY': {
  const next = [action.payload, ...state.pnlHistory].slice(0, 300);
  return { ...state, pnlHistory: next };
}
```

In `onHeartbeat` handler, add dispatch:
```js
dispatch({ type: 'PUSH_PNL_HISTORY', payload: {
  beat_number: data.beat_number,           // confirmed in heartbeat payload
  portfolio_pnl: data.portfolio_pnl ?? 0,  // confirmed in heartbeat payload
  timestamp: data.timestamp ?? new Date().toISOString(), // 'beat_at' does NOT exist — use 'timestamp'
}});
```

**Visual:**
- Recharts `AreaChart` matching `MMMPnLChart` style
- X-axis: `beat_number` (integer)
- Y-axis: P&L in USD
- Zero-line `ReferenceLine` (fill above = green area, fill below = red area)
- Hard-stop threshold line: dashed red at `-(session.hard_stop_usd)`
- Hover tooltip: beat number, P&L value, timestamp

**Integration:** First card in new **"Analytics"** tab (index 10).  
**File:** `webui/frontend/src/components/mmmx/MMMXPnLChart.js`

---

### 3.7 MMMXPerformancePanel.js (P3 — all fields verified)

Session performance analytics summary.

**Data source (all verified):**

| Metric | Field | Verified |
|--------|-------|---------|
| Premium collected | `session.total_premium_collected` | ✅ |
| Profit booked | `session.profit_booked_total` | ✅ |
| Hedge cost paid | `session.total_hedge_cost_paid` | ✅ |
| Tranches deployed | `session.tranches_deployed` | ✅ |
| Open tranches | `session.tranches.filter(t => t.status === 'ACTIVE').length` | ✅ |
| Closed tranches | `session.tranches.filter(t => t.status === 'CLOSED').length` | ✅ |
| CE reserve used | `session.ce_reserve_total_lots - session.ce_reserve_remaining` | ✅ |
| PE reserve used | `session.pe_reserve_total_lots - session.pe_reserve_remaining` | ✅ |
| Total fees | `session.fees_tracking.total_fees_paid` | ✅ |
| Net P&L | `session.portfolio_pnl` | ✅ |

**Visual:**
- Stat card row: Premium Collected | Profit Booked | Hedge Cost | Total Fees
- Tranche breakdown: Total Deployed | Open | Closed | Recovery
- Derived ratio: Profit Booking Efficiency = `profit_booked_total / total_premium_collected`
- Reserve usage: CE used/total bar, PE used/total bar

**Integration:** Second card in **"Analytics"** tab (index 10), below `MMMXPnLChart`.  
**File:** `webui/frontend/src/components/mmmx/MMMXPerformancePanel.js`

### 3.8 Acceptance criteria
- Safety panel shows only `type === 'safety'` events, none from other activity types
- Trade audit renders entries from `/audit` endpoint and is filterable
- Fees & Capital panel shows $0.00 fees when `fees_tracking` is missing (graceful default)
- Regime panel whipsaw level matches backend `get_level(score)` logic exactly
- Delta exposure shows "—" when `current_delta` is null — never shows NaN
- P&L chart accumulates up to 300 beats and updates in real-time on heartbeat
- All panels show a friendly empty state when data is absent (no blank or crash)

---

## Phase 4 — Persistent Right Risk Pane (Spec §3.4)

**Goal:** Implement the persistent right rail from `mmmx_webUI.md §3.4` — always visible
regardless of active tab.  
**Risk:** Medium — layout change.  
**Prerequisite:** Phase 1, Phase 3.3 (MMMXFeesCapitalPanel) and Phase 3.4 (MMMXRegimePanel)
complete.

### 4.1 Layout change

Current:
```
[Left 300px: session list] | [Right flex: top strip + tabs]
```

New:
```
[Left 300px: session list] | [Center flex: top strip + tabs] | [Right 220px: risk rail]
```

- Right rail: always visible when a session is selected
- Collapsible via icon toggle — collapses to 24px icon strip
- Independent scroll — does not scroll with tab content
- Auto-hides below 900px viewport width

### 4.2 Right rail widgets — verified data sources

| Widget | Data source | Verified |
|--------|-------------|---------|
| Hard stop status bar | `session.portfolio_pnl`, `session.hard_stop_usd` | ✅ |
| Portfolio delta | `risk.portfolio_delta` (from heartbeat `PATCH_RISK`) | ✅ |
| CE/PE lot imbalance | `risk.imbalance_pct` (mapped from `session.ce_lot_balance.imbalance_pct`) | ✅ |
| ATM shield status | `session.shield_fire_count`, `session.shield_event_history` last entry | ✅ |
| CE reserve | `session.ce_reserve_remaining` | ✅ |
| PE reserve | `session.pe_reserve_remaining` | ✅ |
| Hedge book | `session.hedges[]` — count by `h.status` (ACTIVE/DISPLACED/ORPHANED/CLOSED) | ✅ |
| Whipsaw level | `risk.whipsaw_score` + derive level (same logic as Phase 3.4) | ✅ |
| Cooldown timer | `session._whipsaw_skip_until` (ISO string or null) | ✅ |

**Removed from original plan:** Margin tier widget — no backend field exists.

### 4.3 Acceptance criteria
- Right rail is visible on all 10 tabs simultaneously
- Collapsing the rail does not affect tab content or layout
- All widgets update in real-time on heartbeat without requiring a tab switch
- Auto-hides on viewports narrower than 900px

---

## Phase 5 — Visual Enhancements

**Goal:** Add the remaining visual depth matching MMM's UI richness.  
**Risk:** Low — all additive.  
**Prerequisite:** Phases 1–4 complete.

### 5.1 MMMXHealthRadar.js (verified axes only)

Radar/spider chart matching `MMMHealthRadar`. Only axes with verified data sources.

**Axes (6 — all data verified):**

| Axis | Source | Max = 100 when |
|------|--------|---------------|
| WS health | `isConnected` | `true` |
| Heartbeat freshness | `hbAgeSec` (derived from `risk.last_beat_at`) | age < 30s |
| Integrity | `integrityState` (SYNCED/DRIFT/STALE/UNKNOWN) | SYNCED |
| Incident pressure | `incidentQueue.length` + severity weights | zero incidents |
| Circuit breaker | `risk.circuit_breaker_state` | `'CLOSED'` |
| Execution certainty | `execution.timeline` uncertain lanes | zero uncertain lanes |

**Visual:** Recharts `RadarChart` with filled polygon; color tied to `healthModel.state`
(NORMAL=green, DEGRADED=amber, CRITICAL=red, UNKNOWN=grey)  
**Integration:** Add as a card at the bottom of the **Status tab**.  
**File:** `webui/frontend/src/components/mmmx/MMMXHealthRadar.js`

---

### 5.2 Reserve Burn-Down History (in right rail)

Mini area sparklines for CE and PE reserve over beats.

**Context change (add to `MMMXContext.js`):**
```js
reserveHistory: [],  // [{ beat_number, ce_reserve, pe_reserve }]
```

Append on `mmmx_heartbeat` — but heartbeat does NOT currently emit reserve fields.  
**Alternative:** Append on `SET_SESSION` and `PATCH_SESSION` when reserve fields change.  
This means history builds on REST refreshes + session patch events, not every beat.

```js
case 'PUSH_RESERVE_HISTORY': {
  const next = [action.payload, ...state.reserveHistory].slice(0, 100);
  return { ...state, reserveHistory: next };
}
```

Dispatch after any `loadSession` call that returns new reserve values.

**Visual:** Two overlapping mini sparklines (CE=blue, PE=orange) shown in right rail
reserve section, below the reserve remaining numbers.

---

### 5.3 DTE Animation on Session Card

Enhance session card DTE chip with urgency coloring (logic already in `computeDTE`).

```
DTE > 14  → grey chip, no animation
DTE 7–14  → amber chip
DTE 3–7   → orange chip, subtle CSS pulse
DTE < 3   → red chip, faster pulse
DTE = 0   → red badge "EXPIRY TODAY" 
```

**Integration:** Modify `MMMXSessionCard.js` (extracted in Phase 1).  
No new data required — `computeDTE(session.expiry_date, session.expiry_ddmmyy)` already exists.

---

### 5.4 Acceptance criteria
- Health radar renders without error when any axis data is absent (axis defaults to 0)
- Reserve chart shows "No history yet" on first load before any data arrives
- DTE animation is CSS-only — no extra API calls or state

---

## Backend Work Required (Future — Not in This Plan)

These features from the original plan are **deferred** because they need new backend fields.
Document here so they can be added as backend tasks:

| Feature | Backend work needed | Effort |
|---------|--------------------|----|
| **Margin Guardian panel** | Add `margin_tier`, `margin_used_pct`, `margin_available` to session schema + emit in heartbeat | Medium |
| **Full Greeks panel** (gamma, theta, vega) | Add gamma/theta/vega to tranche leg schema + populate from live option quotes in premium listener | High |
| **Reserve in heartbeat** | Add `ce_reserve_remaining`, `pe_reserve_remaining` to `emit_heartbeat()` payload in `mmmx_websocket.py` | Low |

The reserve heartbeat addition is the lowest-effort and highest-value: adding two fields to
`emit_heartbeat()` in `mmmx_websocket.py` unlocks real-time reserve burn-down charting (Phase 5.2).

---

## File Map After All Phases

```
webui/frontend/src/components/mmmx/
├── MMMXContext.js                   (modified — _whipsaw bug fix, pnlHistory, reserveHistory)
├── MMMXDashboard.js                 (modified — orchestration shell only, ~300 lines)
├── MMMXErrorBoundary.js             (new — Phase 1)
├── MMMXSessionCard.js               (new — Phase 1)
├── MMMXTopCommandStrip.js           (new — Phase 1)
├── MMMXIncidentQueuePanel.js        (new — Phase 1)
├── MMMXCriticalModePanel.js         (new — Phase 1)
├── MMMXCreateSessionDialog.js       (new — Phase 1)
├── MMMXStatusTab.js                 (new — Phase 1)
├── MMMXTranchesTab.js               (new — Phase 1)
├── MMMXHedgesTab.js                 (new — Phase 1)
├── MMMXTriggerEngineTab.js          (new — Phase 1)
├── MMMXRiskTab.js                   (new — Phase 1)
├── MMMXExecutionTab.js              (new — Phase 1)
├── MMMXProfitBookingTab.js          (new — Phase 1)
├── MMMXParametersTab.js             (new — Phase 1)
├── MMMXReconcileTab.js              (new — Phase 1)
├── MMMXSafetyPanel.js               (new — Phase 3.1)
├── MMMXTradeAuditPanel.js           (new — Phase 3.2, replaces AdjustmentsTab)
├── MMMXFeesCapitalPanel.js          (new — Phase 3.3)
├── MMMXRegimePanel.js               (new — Phase 3.4)
├── MMMXDeltaExposurePanel.js        (new — Phase 3.5)
├── MMMXPnLChart.js                  (new — Phase 3.6)
├── MMMXPerformancePanel.js          (new — Phase 3.7)
├── MMMXHealthRadar.js               (new — Phase 5.1)
├── mmmxControlSafety.js             (unchanged)
├── mmmxEventContracts.js            (unchanged)
├── mmmxService.js                   (unchanged)
├── useMMMXWebSocket.js              (unchanged)
└── utils/
    ├── mmmxFormatters.js            (new — Phase 1)
    └── mmmxDerivations.js           (new — Phase 1)
```

**Tab map after all phases:**

| Index | Label | Changes |
|-------|-------|---------|
| 0 | Status | Refactored + Safety panel + Health radar added |
| 1 | Tranches | Refactored + Delta Exposure panel added below |
| 2 | Trigger Engine | Refactored (unchanged behavior) |
| 3 | Hedges | Refactored (unchanged behavior) |
| 4 | Risk | Refactored + Regime panel + Fees & Capital panel |
| 5 | Execution | Refactored (unchanged behavior) |
| 6 | **Audit** | Was "Adjustments" — replaced by MMMXTradeAuditPanel |
| 7 | Profit | Refactored (unchanged behavior) |
| 8 | Parameters | Refactored (unchanged behavior) |
| 9 | Reconcile | Refactored (unchanged behavior) |
| 10 | **Analytics** | New tab — PnL chart + Performance panel |

---

## Implementation Order

```
Phase 0 — Bug fix (MMMXContext.js line 117)                 ← 5-minute fix, do first
Phase 1 — Architecture refactor (extract all files)          ← zero risk, enables all else
Phase 2 — UX foundation (error boundaries, snackbar, polling)
Phase 3 P1–P2 — Safety panel + Trade audit (no new data)
Phase 3 P2–P3 — Fees, Regime, Delta, PnL chart, Performance
Phase 4 — Right rail (layout change)
Phase 5 — Visual enhancements
[Future] Backend work for Margin Guardian + full Greeks
```

---

## Non-Goals (Explicitly Out of Scope)

- No changes to `webui/backend/routes/mmm/` or any MMM backend file
- No changes to `webui/frontend/src/components/mmm/` (MMM frontend)
- No new MMMX backend API endpoints within this plan scope
- No role-based permissions (listed as NOT DEFINED IN SPEC in mmmx_webUI.md §12)
- No re-design of existing control logic or safety invariants
- No changes to `mmmxControlSafety.js`, `mmmxEventContracts.js`, `mmmxService.js`

---

## Safety Rule (CLAUDE.md)

> Never restart the bot/backend/monitor without explicit user confirmation.  
> Always confirm before `git push` or any destructive operation.

All phases are frontend-only. No restarts required during development.
Each phase can be committed independently.
