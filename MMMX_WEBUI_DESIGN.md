# MMMX WebUI — Robust Dashboard Design

> **Goal:** A WebUI for MMMX with the same depth and operational robustness as the existing MMM dashboard (37 components, ~4k-line dashboard, ~110 REST endpoints, 16 WebSocket event types).
>
> **Status:** Design only. No production code yet. Backend endpoints and events defined here map 1:1 to Phase 8 of [MMMX_IMPLEMENTATION_PLAN.md](MMMX_IMPLEMENTATION_PLAN.md), and several also extend Phases 1–7. Anything referenced here that is not yet built is flagged as a dependency.
>
> **Guiding principle:** MMMX is a slower, longer-horizon strategy than MMM (weeks, not hours), but the operator still needs the same level of visibility during volatile periods. UI must surface every safety layer (Hard Stop → ATM Shield → Hedging → Whipsaw) with one-glance status and deep-dive drill-down.
>
> **Isolation:** The MMMX frontend lives in a sibling folder (`webui/frontend/src/components/mmmx/`) and never imports from `components/mmm/`. Shared primitives (buttons, layout) come from the repo's shared component library only. No `mmm_*` API or WebSocket events are consumed.

---

## SECTION 1 — PARITY MATRIX (MMM → MMMX)

For every MMM dashboard concept, this table specifies the MMMX equivalent. Anything marked **NEW** is MMMX-specific with no MMM analogue.

| # | MMM Component / Feature | MMMX Equivalent | Strategy difference |
|---|---|---|---|
| 1 | `MMMSessionCard` — session list row | `MMMXSessionCard` | Adds budget-used bar, tranches deployed x/10, active hedges count |
| 2 | `MMMDashboard` — main container | `MMMXDashboard` | Tabs: Overview, Tranches, Hedges, Protection, Risk, Deployment, Activity, Parameters, Admin |
| 3 | `MMMStatusBanner` — top-of-page status | `MMMXStatusBanner` | Extra indicators: Hard Stop headroom %, Whipsaw level (NORMAL/CAUTION/RESTRICT/COOLDOWN), Reserve remaining |
| 4 | `MMMPositionsTable` — open CE/PE positions | `MMMXTranchesTable` | One row per tranche (deployment + recovery siblings 2A/2B/2C). Grouped by parent. Expandable for CE/PE detail |
| 5 | `MMMConsolidatedPositions` | `MMMXConsolidatedView` | Sum across all tranches + hedges; shows CE/PE lot imbalance widget |
| 6 | `MMMStrikeSelector` — manual strike picker | `MMMXStrikeScanner` | Used only for Tr1 manual deploy. Scans live chain, shows OTM distance, premium, delta, bid depth |
| 7 | `MMMStrikeMap` — visual strike ladder | `MMMXStrikeMap` | Shows all active tranche strikes, hedge strikes, current spot, 5% ATM shield threshold ring |
| 8 | `MMMPnLChart` — real-time P&L line | `MMMXPnLChart` | Overlays: portfolio P&L, hard stop floor, gross premium, fees paid, hedge cost |
| 9 | `MMMGreeksPanel` — delta/gamma/theta/vega | `MMMXGreeksPanel` | Per-tranche + portfolio aggregate; flags threatened-side delta |
| 10 | `MMMGammaPanel` — gamma exposure | `MMMXGammaPanel` | Less critical for monthly but still shown; highlights gamma ramp at DTE ≤ 15 |
| 11 | `MMMBreakevenPanel` | `MMMXBreakevenPanel` | Shows per-tranche CE/PE breakevens; portfolio break-even band |
| 12 | `MMMAdjustmentLog` | `MMMXAdjustmentLog` | Richer event types: DEPLOY, SHIELD_FIRE, HEDGE_BUY, PROFIT_BOOK, WHIPSAW_LEVEL_CHANGE, QUEUE_POPULATE, QUEUE_CLEAR, RESERVE_DEPLETED, NAKED_DETECTED |
| 13 | `MMMActivityFeed` | `MMMXActivityFeed` | Streaming from `mmmx_activity` ring buffer |
| 14 | `MMMTradeAuditPanel` | `MMMXAuditPanel` | JSONL audit log viewer with filters by tranche, order type, status |
| 15 | `MMMConfigPanel` / `MMMSettingsDialog` | `MMMXSettingsDialog` | Hot-reload editor with allowlist from Plan §5.1 |
| 16 | `MMMSafetyPanel` | `MMMXSafetyPanel` | Shows status of every safety layer with traffic-light indicators |
| 17 | `MMMRegimePanel` | ❌ Not in v1 | Regime controls deferred (MMMX_COMPLETE "Known Limitations") |
| 18 | `MMMReverseModePanel` | ❌ Not in MMMX | Reverse mode is MMM-only |
| 19 | `MMMPerpHedgePanel` | ❌ Not in v1 | Perp futures hedge deferred |
| 20 | `MMMMarginGuardianPanel` | `MMMXMarginPanel` | Shows current utilization, 80% deploy threshold, 85/95% execution thresholds (G40) |
| 21 | `MMMHealthRadar` — monitor/listener/WS health | `MMMXHealthRadar` | Same: monitor alive, listener alive, WS lag, last beat, last tick, generation |
| 22 | `MMMTriggerGauge` — which trigger is closest to firing | `MMMXTriggerGauge` | 10 triggers from Plan §3.7, shows distance-to-fire for each |
| 23 | `MMMEducation` — in-app explainer | `MMMXEducation` | Strategy philosophy + safety layers explanation |
| 24 | `MMMAnalyticsPanel` / `Summary` / `Table` | `MMMXAnalyticsPanel` | Per-tranche ROI, theta capture rate, shield fire count, hedge utilization |
| 25 | `MMMPerformancePanel` | `MMMXPerformancePanel` | Historical sessions summary |
| 26 | `MMMAlgoCalculations` | `MMMXFormulaPanel` | Side-panel showing live formula values (hard stop calc, whipsaw score math, OTM distance per position) |
| 27 | `MMMDistanceHistoryChart` | `MMMXDistanceHistory` | Historical OTM buffer per tranche over time |
| 28 | `MMMRiskProfileChart` | `MMMXRiskProfileChart` | Payoff curve at expiry across all tranches + hedges |
| 29 | `MMMExecutionLogPanel` | `MMMXExecutionLog` | Every smart_execute attempt with reprice history |
| 30 | `MMMBothSidesAlert` | `MMMXNakedAlert` | Full-screen red alert on `_naked_positions` with retry + manual close buttons |
| 31 | `MMMAdoptPanel` — import positions | `MMMXReconcilePanel` | On restart, shows DB vs exchange diff, requires operator confirm to Resume |
| 32 | `MMMCombinedZoneWidget` | `MMMXZoneWidget` | Shows ATM shield 5% ring, threatened zone per position |
| 33 | `MMMErrorBoundary` | `MMMXErrorBoundary` | Same pattern |
| 34 | `useMMMWebSocket` | `useMMMXWebSocket` | Subscribes to `mmmx_*` events (Section 5 below) |
| 35 | `useMMMParams` | `useMMMXParams` | Hot-reload param editor state |
| 36 | `mmmService.js` | `mmmxService.js` | Axios client for `/api/mmmx/*` |
| 37 | `mmmFormatters.js` / `mmmCalculations.js` | `mmmxFormatters.js` / `mmmxCalculations.js` | USD, %, DTE, delta formatters + client-side derived values |
| **NEW** | — | `MMMXDeploymentQueuePanel` | Shows `deployment_eligible_tranches` queue, retracement distance, trigger spot |
| **NEW** | — | `MMMXHedgeLedger` | Full hedge table with H-Tr5…H-Tr10, parent link, displacement status, max loss if spreads hit |
| **NEW** | — | `MMMXWhipsawPanel` | Live score, level badge, decay countdown, cooldown timer, shield event history |
| **NEW** | — | `MMMXProfitBookingPanel` | Per-tranche target picker (10/20/30/50), queued closes list |
| **NEW** | — | `MMMXReserveBar` | Reserve lots used vs available, with cascade warning if < 10 |
| **NEW** | — | `MMMXHardStopMeter` | Large gauge: current P&L vs -hard_stop_usd with color bands |
| **NEW** | — | `MMMXLotImbalancePanel` | CE vs PE lot totals with imbalance_pct, warning at 40%, critical at 60% |

**Total MMMX frontend components: 40+** (37 direct parity + 7 MMMX-specific panels).

---

## SECTION 2 — DASHBOARD INFORMATION ARCHITECTURE

### 2.1 Top-Level Layout

```
┌───────────────────────────────────────────────────────────────────────┐
│ GLOBAL HEADER  MMMX | Session dropdown | Status badge | Last beat | ⚙ │
├───────────────────────────────────────────────────────────────────────┤
│ STATUS BANNER (MMMXStatusBanner)                                      │
│  ● RUNNING  |  Tr 4/10  |  Reserve 22/30  |  Whipsaw: NORMAL          │
│  P&L +$340  |  HS headroom 82%  |  Hedges 0 (capacity 40/50 lots)     │
├───────────────────────────────────────────────────────────────────────┤
│ TABS: Overview | Tranches | Hedges | Protection | Risk |              │
│       Deployment | Activity | Parameters | Admin                      │
├───────────────────────────────────────────────────────────────────────┤
│ ACTIVE TAB CONTENT (see 2.2)                                          │
└───────────────────────────────────────────────────────────────────────┘
│ BOTTOM DOCK: Mini Activity Feed (last 5 events, scrolling)            │
└───────────────────────────────────────────────────────────────────────┘

Full-screen overlay (on critical state):
  ┌─────────────────────────────────┐
  │  🚨 MMMXNakedAlert              │
  │  / MMMXReconcilePanel           │
  │  / MMMXHardStopFiredScreen      │
  └─────────────────────────────────┘
```

### 2.2 Tab Contents

**Overview**
- `MMMXHardStopMeter` (primary, large)
- `MMMXPnLChart` (1h / 24h / session toggle)
- `MMMXHealthRadar`
- `MMMXTriggerGauge`
- `MMMXReserveBar` + `MMMXLotImbalancePanel` (side-by-side)
- `MMMXFormulaPanel` collapsed

**Tranches**
- `MMMXTranchesTable` (grouped by parent; recovery tranches nested)
- Row expander shows CE + PE detail, shield history, unrealized/realized P&L split
- Row actions: "Book profit at…" (10/20/30/50), "Force close" (operator override, logged)
- `MMMXStrikeMap` below table with all strikes plotted

**Hedges**
- `MMMXHedgeLedger` (H-Tr5 … H-Tr10)
- Columns: hedge id, parent, status (ACTIVE/DISPLACED/ORPHANED), spread width, current P&L, displacement timestamp
- Below: total hedge cost paid, active hedges count, max loss if all spreads hit

**Protection**
- `MMMXSafetyPanel` — 4 rows, one per layer:
  1. Hard Stop: multiplier, threshold, headroom, last recalc
  2. ATM Shield: threshold, shifts used per tranche, reserve remaining
  3. Hedging: capacity met?, active hedges, total cost
  4. Whipsaw: score, level, decay/cooldown countdowns
- `MMMXZoneWidget` showing 5% ATM rings around current spot per position
- `MMMXGreeksPanel` with threatened-side highlighting

**Risk**
- `MMMXRiskProfileChart` (payoff at expiry curve)
- `MMMXGreeksPanel` detailed
- `MMMXMarginPanel` with live utilization gauge (80% deploy cap, 85/95% execution thresholds)
- `MMMXDistanceHistoryChart`

**Deployment**
- `MMMXStrikeScanner` — live chain preview for manual Tr1 or "what would next tranche deploy into"
- `MMMXDeploymentQueuePanel` — current queue, trigger spot, retracement, next-deploy eligibility
- Deployment gates status list: entry gates (if DRAFT), fairness gate, frequency gate (deployments_last_24h), whipsaw skip_until
- Manual "Deploy Tr1" button (only when `status == GATES_PASSED`)
- Recent deployments log

**Activity**
- `MMMXActivityFeed` full-height
- `MMMXAdjustmentLog` filterable (DEPLOY / SHIELD_FIRE / HEDGE_BUY / PROFIT_BOOK / WHIPSAW_LEVEL_CHANGE / …)
- `MMMXExecutionLog` with per-order reprice sequences
- `MMMXAuditPanel` — raw JSONL viewer with filters

**Parameters**
- `MMMXSettingsDialog` inline
- Grouped sections: Deployment, Gates, Hedging, Whipsaw, Exit, Shield, Delta Gates, IV
- Diff preview before save; rejected changes show reason inline
- Change history (last 50 hot-reloads with who/when/what)

**Admin**
- `MMMXReconcilePanel` (visible only when status == PAUSED after restart)
- Pause / Resume / Stop buttons with confirm modals
- Telegram test button, WebSocket reconnect, manual health check
- Generation counter, monitor thread uptime, listener uptime
- Raw session JSON viewer (collapsed)

### 2.3 Navigation & Routing

- Route: `/mmmx` (lazy-loaded in `App.js`, mirrors how MMM is lazy-loaded)
- Nav entry in `navigationSections.js` with icon
- Query param `?session=<id>` selects active session; default = most recent RUNNING, else most recent
- Deep-linkable tabs: `/mmmx?session=<id>&tab=hedges`

### 2.4 Responsive Behavior

- **Desktop (≥1280px)**: 2-column grid on Overview; side panels docked
- **Tablet (768–1279)**: single column, tabs collapse to dropdown if > 6
- **Mobile (<768)**: status banner + single active panel; actions button promotes to bottom bar
- Matches MMM's responsive pattern in `MobileNav.js`

---

## SECTION 3 — REST API SURFACE (`/api/mmmx/*`)

Mirrors MMM's ~110 endpoints at a comparable level of granularity. Grouped by concern. All endpoints return JSON, emit typed errors `{error, code, message}`, and log mutations to `mmmx_param_audit.jsonl` or `mmmx_audit_log.jsonl` as appropriate.

### 3.1 Session lifecycle

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/mmmx/sessions` | List all sessions with summary fields |
| POST | `/api/mmmx/session` | Create session (DRAFT) |
| GET | `/api/mmmx/session/<id>` | Full session state |
| DELETE | `/api/mmmx/session/<id>` | Delete DRAFT or COMPLETE session |
| POST | `/api/mmmx/session/<id>/check_entry_gates` | Run entry gate checks (returns verdict) |
| POST | `/api/mmmx/session/<id>/scan_strikes` | Live chain scan for Tr1 (body: `otm_distance_pct`) |
| POST | `/api/mmmx/session/<id>/validate_selection` | Validate operator's chosen CE/PE strikes |
| POST | `/api/mmmx/session/<id>/deploy_tranche1` | Execute manual Tr1 |
| POST | `/api/mmmx/session/<id>/pause` | Status → PAUSED |
| POST | `/api/mmmx/session/<id>/resume` | Status → RUNNING (runs full beat immediately) |
| POST | `/api/mmmx/session/<id>/stop` | Graceful stop (close_all + COMPLETE) |
| POST | `/api/mmmx/session/<id>/force_close_all` | Operator emergency close (audit-logged) |

### 3.2 Params / hot-reload

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/mmmx/session/<id>/params` | Current params |
| PATCH | `/api/mmmx/session/<id>/params` | Hot-reload allowlisted params (Plan §5.1) |
| GET | `/api/mmmx/session/<id>/params/history` | Last N param change audit entries |
| GET | `/api/mmmx/params/info` | Per-param metadata (min, max, type, description, hot-reloadable y/n) |
| GET | `/api/mmmx/params/allowlist` | Hot-reload allowlist |

### 3.3 Tranches & positions

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/mmmx/session/<id>/tranches` | All tranches (deployment + recovery) |
| GET | `/api/mmmx/session/<id>/tranche/<tranche_id>` | Single tranche detail + shield history |
| GET | `/api/mmmx/session/<id>/positions` | Flattened CE/PE positions |
| GET | `/api/mmmx/session/<id>/consolidated` | Aggregate exposure (sum across tranches) |
| GET | `/api/mmmx/session/<id>/lot_balance` | `ce_lot_balance` snapshot |

### 3.4 Hedging

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/mmmx/session/<id>/hedges` | All hedge entries |
| GET | `/api/mmmx/session/<id>/hedge/<hedge_id>` | Single hedge detail |
| POST | `/api/mmmx/session/<id>/hedge/<hedge_id>/manual_close` | Operator-triggered hedge close (rare) |

### 3.5 Deployment queue & triggers

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/mmmx/session/<id>/deployment_queue` | Queue state + trigger spot + retracement distance |
| GET | `/api/mmmx/session/<id>/triggers` | Last beat's trigger evaluation (all 10 with distance-to-fire) |
| GET | `/api/mmmx/session/<id>/deploy_conditions` | Current deploy-condition check (move %, IV delta, frequency gate, fairness gate) |
| POST | `/api/mmmx/session/<id>/preview_next_deploy` | Dry-run next tranche: strikes, premium, lots (applies whipsaw adjustments) |

### 3.6 ATM Shield

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/mmmx/session/<id>/shield/status` | Reserve remaining, shield candidates next beat |
| GET | `/api/mmmx/session/<id>/shield/history` | Full shield event history |
| GET | `/api/mmmx/session/<id>/shield/candidates` | Current positions near threshold with distance-to-fire |

### 3.7 Whipsaw

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/mmmx/session/<id>/whipsaw` | Score, level, decay/cooldown timers, shield_event_history |

### 3.8 Profit booking

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/mmmx/session/<id>/profit_book` | Body `{tranche_id, target_pct, mode: 'at_target' \| 'now'}` |
| GET | `/api/mmmx/session/<id>/profit_book/queue` | Pending profit-booking requests |
| DELETE | `/api/mmmx/session/<id>/profit_book/<request_id>` | Cancel a pending request |

### 3.9 Risk / P&L / Greeks

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/mmmx/session/<id>/pnl` | Portfolio P&L (realized + unrealized + fees) |
| GET | `/api/mmmx/session/<id>/pnl/history` | P&L time series for charts |
| GET | `/api/mmmx/session/<id>/greeks` | Per-tranche + portfolio greeks |
| GET | `/api/mmmx/session/<id>/risk_profile` | Payoff at expiry (array of {spot, pnl}) |
| GET | `/api/mmmx/session/<id>/breakeven` | Per-tranche + portfolio breakevens |
| GET | `/api/mmmx/session/<id>/distance_history` | OTM buffer per tranche over time |
| GET | `/api/mmmx/aggregate_pnl` | Sum across all MMMX sessions (matches MMM's dashboard aggregate) |

### 3.10 Margin

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/mmmx/session/<id>/margin` | Utilization, available, thresholds |
| GET | `/api/mmmx/exchange/margin` | Live exchange margin snapshot |

### 3.11 Activity / audit / history

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/mmmx/session/<id>/activities` | Ring buffer feed (paginated) |
| GET | `/api/mmmx/session/<id>/adjustments` | Adjustment log with filters |
| GET | `/api/mmmx/session/<id>/execution_log` | Per-order execution history |
| GET | `/api/mmmx/session/<id>/audit` | Raw JSONL audit rows (filters: tranche, side, order_type, status, since) |
| GET | `/api/mmmx/session/<id>/history` | Full beat history |
| GET | `/api/mmmx/session/<id>/state` | Raw session dict |

### 3.12 Chain / market data

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/mmmx/expiries` | Available BTC monthly expiries 20–45 DTE |
| GET | `/api/mmmx/spot_price` | Current BTC spot |
| GET | `/api/mmmx/chain` | Full chain for selected expiry |
| POST | `/api/mmmx/preview_strikes` | For given spot + OTM %, preview CE/PE strikes on live chain |
| POST | `/api/mmmx/check_liquidity` | For given symbol, return bid/ask/depth/spread |

### 3.13 Reconciliation / adoption

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/mmmx/session/<id>/reconcile` | Run DB-vs-exchange diff |
| POST | `/api/mmmx/session/<id>/reconcile/confirm` | Operator confirms diff; session → RUNNING |
| GET | `/api/mmmx/exchange/positions` | All BTC options positions on exchange |
| POST | `/api/mmmx/session/<id>/retry_partial_leg` | Retry a residual fill (matches MMM pattern) |

### 3.14 Health / diagnostics

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/mmmx/health` | Blueprint health check |
| GET | `/api/mmmx/session/<id>/health` | Monitor + listener + WS + generation |
| GET | `/api/mmmx/session/<id>/formula_values` | Live computed formula outputs for `MMMXFormulaPanel` |

**Total MMMX endpoints: ~70** (vs MMM's ~110, which includes many legacy/regime/perp routes MMMX does not need).

---

## SECTION 4 — WEBSOCKET EVENT CONTRACT (`mmmx_*`)

All events prefixed `mmmx_` and never overlap MMM. The frontend hook `useMMMXWebSocket.js` subscribes to the full list.

| Event | Payload (abbreviated) | Triggered by | Consumed by |
|---|---|---|---|
| `mmmx_heartbeat` | `{session_id, beat_number, ts, pnl, hard_stop_usd}` | Every beat end | Status banner, P&L chart, health radar |
| `mmmx_price_tick` | `{session_id, symbol, bid, ask, last, delta, ts}` | Premium listener | Strike map, positions table |
| `mmmx_status_change` | `{session_id, from, to, reason}` | Monitor state transitions | Status banner, full dashboard |
| `mmmx_session_created` | `{session_id, params}` | Create endpoint | Session list |
| `mmmx_pnl_update` | `{session_id, realized, unrealized, fees, total, per_tranche}` | Each beat | P&L chart, hard stop meter |
| `mmmx_deployment` | `{session_id, tranche_id, type, ce_strike, pe_strike, premium, spot}` | `initializer.execute_tranche_deploy` | Tranches table, activity feed |
| `mmmx_deployment_queue` | `{session_id, queue, trigger_spot, triggered_at}` | Queue populate/clear | Deployment queue panel |
| `mmmx_shield_fire` | `{session_id, tranche_id, side, old_strike, new_strike, loss, recovery_tranche_id}` | `atm_shield.execute_shield` | Adjustment log, shield history, strike map |
| `mmmx_shield_abort` | `{session_id, tranche_id, reason}` | Shield buyback or sell failure | Safety panel, naked alert |
| `mmmx_reserve_update` | `{session_id, reserve_remaining, last_decrement}` | Any recovery allocation | Reserve bar |
| `mmmx_hedge_scheduled` | `{session_id, hedge_id, parent_tranche_id, execute_at}` | Hedger schedule | Hedge ledger |
| `mmmx_hedge_executed` | `{session_id, hedge_id, ce_strike, pe_strike, cost}` | Hedger tick | Hedge ledger, activity feed |
| `mmmx_hedge_displaced` | `{session_id, hedge_id, parent_tranche_id}` | Shield repositions parent | Hedge ledger |
| `mmmx_whipsaw_level` | `{session_id, score, level, skip_until}` | Whipsaw score crosses threshold | Whipsaw panel, status banner |
| `mmmx_profit_booked` | `{session_id, tranche_id, target_pct, realized}` | Profit booking completes | Tranches table, P&L chart |
| `mmmx_params_updated` | `{session_id, diff, operator}` | Hot-reload PATCH | Parameters panel, activity feed |
| `mmmx_trigger_fired` | `{session_id, trigger_name, action, context}` | Trigger evaluator first-match | Trigger gauge, activity feed |
| `mmmx_cb_tier0` | `{session_id, breaker, value, threshold}` | Premium listener CB fires | Activity feed, safety panel |
| `mmmx_naked_detected` | `{session_id, tranche_id, side, since}` | Shield sell failure | Full-screen naked alert |
| `mmmx_naked_resolved` | `{session_id, tranche_id, side, how}` | Retry success or manual close | Naked alert dismissal |
| `mmmx_reconcile_needed` | `{session_id, diffs}` | Startup or explicit reconcile | Reconcile panel overlay |
| `mmmx_margin_warning` | `{session_id, utilization, threshold}` | Executor margin recheck | Margin panel, activity feed |
| `mmmx_api_failure` | `{session_id, endpoint, error}` | Circuit breaker OPEN | Safety panel |
| `mmmx_api_recovered` | `{session_id}` | Circuit breaker CLOSED | Safety panel |
| `mmmx_watchdog_restart` | `{session_id, thread, generation}` | Watchdog restart | Health radar, admin tab |
| `mmmx_activity` | `{session_id, type, message, ts}` | Any activity log append | Activity feed (streaming) |

**Total MMMX WebSocket events: 27** (vs MMM's 16 — MMMX is richer because it has more safety layers to surface).

---

## SECTION 5 — COMPONENT SPECIFICATIONS (Key Panels)

Only the highest-value MMMX-specific panels are specified here in detail. The 1:1 parity panels (Section 1 rows 1–33) follow MMM's implementation patterns.

### 5.1 `MMMXHardStopMeter`

**Purpose:** Primary headline gauge. Operator should see at a glance how close the session is to hard stop.

**Data sources:** `mmmx_pnl_update` (live), `GET /session/<id>/pnl` on mount.

**Visual:**
- Large radial gauge, 0 at bottom-left (full loss), hard_stop_usd at top-right mirror, 0 at center
- Current P&L as a needle
- Color bands: green (>0), yellow (0 to -50%), orange (-50 to -80%), red (-80 to -100%)
- Beyond the red band: a crosshatched "slippage zone" (G36 — acknowledges overshoot is possible)
- Secondary readouts: Hard stop threshold, Headroom %, Gross premium, Fees paid, Hedge cost (separate)

**Interactions:**
- Hover any band → tooltip with P&L value at that band edge
- Click → opens `MMMXFormulaPanel` showing `hard_stop_usd = multiplier × total_premium_collected`

### 5.2 `MMMXTranchesTable`

**Purpose:** The table the operator lives in during a session.

**Rows:**
- One per tranche, parent-grouped. Recovery tranches (`2A`, `2B`, `2C`) are indented children of their parent.
- Columns: ID, Type (deployment/recovery), Status, Entry spot, Entry DTE, CE strike/lots/current/δ, PE strike/lots/current/δ, Premium collected, Unrealized P&L, Realized P&L, OTM% CE, OTM% PE, Shift count, Action menu

**Row highlighting:**
- Yellow border if any side OTM% < 7% (warning proximity)
- Red border if any side OTM% < 5% (shield will fire next beat)
- Red background if `_being_closed` is set (in-flight)
- Strikethrough if status == CLOSED

**Actions (per row):**
- "Book profit at…" dropdown → POST `/profit_book` with tranche id
- "View shield history" → side drawer with `shield_history` array
- "Force close" → confirm modal, audit-logged, POST `/force_close_tranche`

**Update cadence:** every beat + every `mmmx_price_tick` (for current_premium / delta) + on `mmmx_shield_fire` and `mmmx_profit_booked`.

### 5.3 `MMMXDeploymentQueuePanel`

**Purpose:** Make the deployment eligibility queue (Plan §1.3 + spec §2) visible.

**Data:** `mmmx_deployment_queue` + `GET /deployment_queue`.

**Layout:**
```
Deployment Queue
  Triggered at: 11:00 UTC, spot $70,500
  Queue: [Tr3, Tr4]                (chips)
  Retracement from trigger spot: 1.4% (threshold 0.5%)
  Next deploy eligible: Beat +1 (12:00 UTC)

Current deploy conditions
  ✓ Spot move: 2.1% ≥ 2.0%
  ✗ IV delta:  +4 ranks < 10 required
  ✓ Margin:   62% < 80%
  ✓ Frequency: 1/2 deploys in last 24h
  ✓ Fairness:  mid within 3.2% of BS (≤10%)
  ● Whipsaw:  NORMAL
  Verdict: DEPLOY eligible — next beat will place Tr3
```

### 5.4 `MMMXHedgeLedger`

**Data:** `GET /hedges`, updated by `mmmx_hedge_*` events.

**Columns:** hedge_id, parent_tranche_id, executed_at, CE strike, CE lots, CE premium paid, CE current, PE strike, PE lots, PE premium paid, PE current, total cost, spread width, max loss if hit, status (ACTIVE/DISPLACED/ORPHANED), actions

**Filters:** status, parent_tranche_id, executed_after

**Footer totals:** total_hedge_cost_paid, active_hedges count, sum of max_loss_if_spreads_hit, margin consumed (estimated)

### 5.5 `MMMXWhipsawPanel`

**Data:** `GET /whipsaw` + `mmmx_whipsaw_level` events.

**Content:**
- Large level badge (NORMAL / CAUTION / RESTRICT / COOLDOWN) in color
- Score gauge (0–5) with decay rate
- Countdown: "Next decay in 23 min" or "Cooldown ends in 41 min"
- Table of recent `shield_event_history` entries (beat, side, spot, tranche_id, contributed to score?)
- Explanation of current adjustments: "Deployment triggers widened to 3.0% (CAUTION). Tranche size: 10 lots."

### 5.6 `MMMXSafetyPanel`

**Purpose:** Single page showing all four safety layers with traffic-light status.

**Layout:** 4 large cards, one per layer:

```
┌────────────────────────────────────────────────────────┐
│ 1. HARD STOP                                🟢 HEALTHY │
│    Multiplier: 2.0  |  Threshold: -$680               │
│    Current: -$120 (headroom 82%)                       │
│    Last recalc: after Tr4 deploy, 10:04 UTC           │
└────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────┐
│ 2. ATM SHIELD                               🟡 ACTIVE  │
│    Threshold: 5.0% OTM                                 │
│    Positions < 8% OTM: 1 (Tr2 PE at 6.2%)             │
│    Reserve: 22/30 lots  |  Shifts used: Tr2=1, rest=0 │
│    Last fire: Tr1 CE 10:30 UTC → Tr1A created          │
└────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────┐
│ 3. HEDGING                                  ⚪ PENDING │
│    Capacity: 40/50 lots (Tr1-Tr4 deployed)            │
│    Active hedges: 0  |  Total cost: $0                 │
│    Next eligible: Tr5 deploy triggers H-Tr5            │
└────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────┐
│ 4. WHIPSAW                                  🟢 NORMAL  │
│    Score: 0  |  Last noise: —                          │
│    Deployment triggers: 2.0% (base)                    │
│    Cooldown: not active                                │
└────────────────────────────────────────────────────────┘
```

### 5.7 `MMMXNakedAlert` (full-screen overlay)

**Trigger:** `mmmx_naked_detected` fires.

**Content:**
- Red full-screen overlay, cannot be dismissed without action
- Shows: tranche_id, side, minutes naked, retry count
- Buttons:
  - "Retry emergency sell now" → POST `/session/<id>/naked/retry`
  - "Mark as manually closed" (operator closed on exchange) → POST `/session/<id>/naked/resolve`
  - "Open exchange" → external link to Delta
- Countdown to 30-min and 2-hour escalation thresholds
- Live premium / delta of naked position

### 5.8 `MMMXReconcilePanel` (full-screen overlay on restart)

**Trigger:** Any startup where sessions exist in PAUSED state, or explicit reconcile via Admin tab.

**Content:**
- Diff table: DB positions vs exchange positions
  - Rows flagged `DB_ONLY`, `EXCHANGE_ONLY`, `MATCH`, `MISMATCH_LOTS`, `MISMATCH_STRIKE`
- For each mismatch, operator must choose: Adopt exchange truth, Mark DB row as closed, Manual investigation (leaves in PAUSED)
- "Confirm reconciliation" button disabled until every mismatch has a decision
- After confirmation → `mmmx_status_change` to RUNNING, next beat runs immediately

### 5.9 `MMMXSettingsDialog`

**Purpose:** Hot-reload editor.

**Features:**
- Grouped by section matching Plan §5.1
- Per-field: label, help text, current value, proposed value, min/max, type
- Client-side validation mirrors server allowlist (from `GET /params/info`)
- Diff preview before save
- Save button disabled if no diff or if any field invalid
- Rejected changes show inline server reason (e.g., "close_at_dte must be >= 7 (gamma risk)")
- Change history drawer showing last 50 hot-reloads with timestamp, operator, diff

### 5.10 `MMMXStrikeMap`

**Visual:** Horizontal price axis centered on current spot, extending to ±30%.

**Markers:**
- Vertical line at current spot
- Per active tranche: two diamonds (CE strike above, PE strike below), colored by parent, labeled with tranche_id
- Per hedge: two triangles (wider OTM), colored gray, labeled H-Tr5
- Two translucent bands at ±5% ATM shield threshold
- Strike ladder ticks from live chain

**Interactions:**
- Hover strike → tooltip with lots, premium, delta, OTM%
- Click tranche → scrolls to its row in `MMMXTranchesTable`
- Scroll wheel zooms the price axis

---

## SECTION 6 — FILE STRUCTURE

```
webui/frontend/src/components/mmmx/
├── MMMXDashboard.js                   — main container, tab router
├── MMMXContext.js                     — React context provider
├── MMMXErrorBoundary.js
├── MMMXStatusBanner.js
├── MMMXSessionCard.js
│
├── overview/
│   ├── MMMXHardStopMeter.js
│   ├── MMMXHealthRadar.js
│   ├── MMMXTriggerGauge.js
│   ├── MMMXReserveBar.js
│   └── MMMXLotImbalancePanel.js
│
├── tranches/
│   ├── MMMXTranchesTable.js
│   ├── MMMXConsolidatedView.js
│   └── MMMXStrikeMap.js
│
├── hedges/
│   └── MMMXHedgeLedger.js
│
├── protection/
│   ├── MMMXSafetyPanel.js
│   ├── MMMXWhipsawPanel.js
│   ├── MMMXZoneWidget.js
│   └── MMMXShieldHistoryDrawer.js
│
├── risk/
│   ├── MMMXRiskProfileChart.js
│   ├── MMMXGreeksPanel.js
│   ├── MMMXGammaPanel.js
│   ├── MMMXBreakevenPanel.js
│   ├── MMMXDistanceHistory.js
│   ├── MMMXPnLChart.js
│   └── MMMXMarginPanel.js
│
├── deployment/
│   ├── MMMXStrikeScanner.js
│   ├── MMMXDeploymentQueuePanel.js
│   └── MMMXDeployConditionsPanel.js
│
├── activity/
│   ├── MMMXActivityFeed.js
│   ├── MMMXAdjustmentLog.js
│   ├── MMMXExecutionLog.js
│   └── MMMXAuditPanel.js
│
├── parameters/
│   ├── MMMXSettingsDialog.js
│   ├── MMMXParamHistoryDrawer.js
│   └── MMMXFormulaPanel.js
│
├── admin/
│   ├── MMMXReconcilePanel.js
│   ├── MMMXAdminControls.js
│   └── MMMXRawStateViewer.js
│
├── overlays/
│   ├── MMMXNakedAlert.js
│   └── MMMXHardStopFiredScreen.js
│
├── profit/
│   └── MMMXProfitBookingPanel.js
│
├── analytics/
│   ├── MMMXAnalyticsPanel.js
│   ├── MMMXAnalyticsTable.js
│   └── MMMXPerformancePanel.js
│
├── education/
│   └── MMMXEducation.js
│
├── hooks/
│   ├── useMMMXWebSocket.js
│   ├── useMMMXParams.js
│   ├── useMMMXSession.js
│   └── useMMMXFormulaValues.js
│
├── utils/
│   ├── mmmxFormatters.js
│   └── mmmxCalculations.js
│
├── mmmxService.js                     — axios client
├── __tests__/                         — component tests
└── index.js                           — exports
```

---

## SECTION 7 — STATE MANAGEMENT

### 7.1 React Context (`MMMXContext`)

```js
{
  activeSessionId,
  sessions,              // list summary
  session,               // full session (refreshed on each mmmx_heartbeat)
  params,                // session.params
  pnl,                   // realized/unrealized/fees/total
  tranches,              // flattened with parent grouping
  hedges,
  deploymentQueue,
  whipsaw,
  reserve,
  triggers,              // last beat evaluation
  safety,                // 4-layer status
  health,                // monitor/listener/ws/gen
  naked,                 // [] or non-empty overlay
  reconcileNeeded,       // bool
  wsConnected,
  lastBeatAt,
  loading,
  error,
}
```

### 7.2 Data Flow

```
REST (initial load)  ──┐
                       ▼
                  MMMXContext state  ─────► components (hooks/useContext)
                       ▲
                       │
WebSocket events  ─────┘  (partial updates, reducers)
```

- Initial load fetches everything once per session switch.
- WebSocket events drive incremental updates; no polling.
- If WebSocket disconnects > 10s → banner warning + fall back to 5s REST polling until reconnect (matches MMM pattern).

### 7.3 Cache & Refresh Strategy

- Session list: cached, invalidated on `mmmx_session_created`, `mmmx_status_change`.
- Chain data: cached 30s client-side for strike scanner.
- Audit log / history: paginated, cursor-based, never fully loaded.
- Charts: rolling buffer (last 500 points) in memory + on-demand history fetch.

---

## SECTION 8 — INTEGRATION WITH IMPLEMENTATION PLAN

This design plugs into the phased build in [MMMX_IMPLEMENTATION_PLAN.md](MMMX_IMPLEMENTATION_PLAN.md) as follows:

| Phase | What the UI needs from the backend |
|---|---|
| **Phase 1** (Skeleton) | Sessions list, create, DRAFT state, param validation, `mmmx_session_created`, `mmmx_heartbeat`, `mmmx_status_change` → **minimal Overview tab + Sessions list + Parameters viewer (read-only)** can ship on top of Phase 1. |
| **Phase 2** (Executor) | None directly visible; enables manual exchange probes (liquidity check, margin check endpoints). |
| **Phase 3** (Monitor + triggers) | `mmmx_trigger_fired`, `mmmx_pnl_update` → Trigger Gauge, P&L Chart, Hard Stop Meter become live. |
| **Phase 4** (Hard stop) | `mmmx_trigger_fired` with HARD_STOP → `MMMXHardStopFiredScreen` overlay. Safety panel Layer 1 goes live. |
| **Phase 5** (ATM Shield) | `mmmx_shield_fire`, `mmmx_shield_abort`, `mmmx_reserve_update`, `mmmx_naked_detected` → Protection tab, Reserve Bar, Shield History, Naked Alert overlay. |
| **Phase 6** (Deployment + whipsaw + profit booking) | `mmmx_deployment`, `mmmx_deployment_queue`, `mmmx_whipsaw_level`, `mmmx_profit_booked` → Deployment tab, Whipsaw panel, Profit Booking panel, Tr1 manual deploy flow. |
| **Phase 7** (Listener + hedger) | `mmmx_price_tick`, `mmmx_cb_tier0`, `mmmx_hedge_*` → Live tick updates in Tranches table, Hedge Ledger, Hedging safety card. |
| **Phase 8** (UI + hot reload) | **This is the dedicated UI phase.** All endpoints in Section 3 and events in Section 4 MUST exist before this phase ships. The React code-up happens here end-to-end using this design as the blueprint. |
| **Phase 9** (Fault tolerance) | `mmmx_reconcile_needed`, `mmmx_watchdog_restart` → `MMMXReconcilePanel` overlay, Admin tab health indicators. |

**Recommendation:** Build the UI incrementally alongside the backend phases, not in one big Phase 8 drop. The full Phase 8 milestone becomes a **UI-complete audit** where every Section 5 panel is verified against its final backend contract.

---

## SECTION 9 — DEPENDENCIES & ASSUMPTIONS

1. Shared components (buttons, modals, toast, theme, MUI) are consumed from the existing repo shared library — not copied from MMM folders.
2. `useMMMXWebSocket` connects to the same Socket.IO namespace as MMM but only listens for `mmmx_*` events. Backend must emit MMMX events via the existing SocketIO instance.
3. Authentication / session-cookie handling inherits from the existing WebUI. No new auth layer.
4. No chart library beyond what MMM already uses (to avoid bundle bloat).
5. Design explicitly does NOT include: regime controls, reverse mode, perp hedge, event calendar, IV-RV spread, concentration risk, TWAP slicing (these are post-MVP per MMMX_COMPLETE §11).
6. Mobile responsiveness reuses MMM's `MobileNav` component via the shared library layer (if exposed) or is re-implemented in `mmmx/` without importing from `mmm/`.
7. Every destructive action (stop, force_close, resume) requires an explicit confirm modal with a 3-second arming delay, matching MMM's pattern.

---

## SECTION 10 — OPEN DESIGN QUESTIONS (decisions needed before Phase 8)

| # | Question | Recommendation |
|---|---|---|
| U1 | Should MMMX share MMM's Socket.IO namespace or open a new one? | Share existing namespace. Event prefix ensures isolation. Saves a second WS connection. |
| U2 | Is the Admin tab behind a role gate? | Yes — mirror MMM's pattern. Operator-only actions (force close, reconcile confirm) require the same auth as MMM. |
| U3 | Should `MMMXHardStopFiredScreen` auto-dismiss or require acknowledgement? | Require operator acknowledgement (click "I understand"). Audit-logged. |
| U4 | Charts library: reuse MMM's (likely Recharts) or migrate to lightweight-charts for options payoff? | Reuse MMM's for parity; revisit post-MVP. |
| U5 | Do we expose the raw session JSON viewer to all operators or only admin? | Admin tab only (same as MMM). |
| U6 | Should the `MMMXReconcilePanel` block all other UI until resolved? | Yes — full-screen overlay, no other interaction possible. Matches severity of the condition. |
| U7 | For `MMMXEducation`, reuse MMM's copy or write MMMX-specific? | Write MMMX-specific copy. The philosophy section is fundamentally different. |
| U8 | Should profit booking support scheduled/conditional orders or only immediate? | Phase 8 ships "at target" + "now" only. Conditional orders deferred to v2. |
| U9 | How is "aggregate P&L across all MMMX sessions" surfaced? | `GET /api/mmmx/aggregate_pnl` powers a small widget on the sessions list page. |
| U10 | Do we support operator-added notes/tags per tranche? | Deferred to v2; out of MVP. |

---

**End of design.** This document is the source of truth for the MMMX WebUI build. Any deviation during Phase 8 implementation must be reflected here first.
