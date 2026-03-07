# Options WebUI — 9 Features Implementation Plan

**Created:** 2026-03-05
**Branch:** SSR
**Status:** ✅ ALL 9 FEATURES IMPLEMENTED (2026-03-05)

| # | Feature | Status | Key Files Added/Modified |
|---|---------|--------|--------------------------|
| F1 | Fix Activity Log | ✅ Done | `max_loss_manager.py`, `activity_log_db.py`, `options_control.py`, `OptionsActivityPanel.js` |
| F2 | IV Rank/Percentile | ✅ Done | `iv_history_db.py`, `options_control.py`, `useIVStats.js`, `OptionsPanel.js`, `PositionRow.js` |
| F3 | Per-Position Greeks | ✅ Done | `position_greeks.py`, `options_control.py`, `usePositionGreeks.js`, `OptionsPanel.js`, `PositionRow.js` |
| F4 | PnL Attribution | ✅ Done | `pnl_attribution.py`, `app.py`, `PnLAttributionPanel.js`, `OptionsPanel.js` |
| F5 | Conditional Alerts | ✅ Done | `alerts_db.py` (migration+greek_alerts), `alert_routes.py`, `price_alert_monitor.py`, `greek_alerts.py`, `PayoffAlertDialog.js`, `AlertsPanel.js` |
| F6 | Payoff Graph Fixes | ✅ Done | `OptionsPayoffDiagram.js` (maxDaysToExpiry, compare sliders, breakevens), `PayoffControls.js` |
| F7 | IV Term Structure | ✅ Done | `VolTermStructurePanel.js`, `OptionsPanel.js` |
| F8 | Vol Skew/Smile | ✅ Done | `VolSmilePanel.js`, `OptionsPanel.js` |
| F9 | Roll Management | ✅ Done | `roll_manager.py`, `app.py`, `RollManagerModal.js`, `PositionRow.js`, `OptionsPanel.js` |

---

## Table of Contents

1. [Feature 1 — Fix Activity Log](#feature-1--fix-activity-log-bug-fix)
2. [Feature 2 — IV Rank / IV Percentile](#feature-2--iv-rank--iv-percentile)
3. [Feature 3 — Per-Position Greeks](#feature-3--per-position-greeks)
4. [Feature 4 — PnL Attribution](#feature-4--pnl-attribution-by-greek-source)
5. [Feature 5 — Conditional Execution on Alerts](#feature-5--conditional-execution-on-price-alerts)
6. [Feature 6 — Payoff Graph Fixes](#feature-6--payoff-graph-fixes)
7. [Feature 7 — IV Term Structure Chart](#feature-7--iv-term-structure-chart)
8. [Feature 8 — Volatility Skew / Smile Chart](#feature-8--volatility-skew--smile-chart)
9. [Feature 9 — Roll Management Tool](#feature-9--roll-management-tool)
10. [Dependency Graph & Execution Order](#dependency-graph--execution-order)

---

## Codebase Architecture Summary

| Layer | Key Files | Notes |
|-------|-----------|-------|
| **Frontend — Page** | `webui/frontend/src/pages/OptionsPage.js` | Wrapper with collapsible cards |
| **Frontend — Main Panel** | `webui/frontend/src/components/options/OptionsPanel.js` (192KB) | Position table, column settings (lines 603-652), drag-and-drop |
| **Frontend — Position Row** | `webui/frontend/src/components/options/PositionRow.js` (36KB) | Per-row rendering, memoized |
| **Frontend — Payoff** | `webui/frontend/src/components/options/OptionsPayoffDiagram.js` (55KB) | Recharts-based, time slider, compare, breakevens |
| **Frontend — Activity** | `webui/frontend/src/components/options/OptionsActivityPanel.js` (17KB) | Polls `/api/options/monitoring-activity` |
| **Frontend — Greeks Summary** | `webui/frontend/src/components/options/PortfolioGreeksSummary.js` (13KB) | Aggregate delta/gamma/theta/vega bar |
| **Frontend — Hooks** | `webui/frontend/src/hooks/useOptionsPositions.js` (16KB) | Fetches `/api/options/dashboard`, WS updates |
| **Frontend — Calculator** | `webui/frontend/src/components/options/payoffCalculator.js` (14KB, SEALED) | BS pricing, Greeks, PoP — `RISK_FREE_RATE=0.0` |
| **Backend — Routes** | `webui/backend/routes/options/options_control.py` (97KB) | All option endpoints under `/api/options` |
| **Backend — Dashboard** | `webui/backend/routes/options/dashboard.py` + `dashboard_service.py` | Unified position+greeks+margin endpoint |
| **Backend — Max Loss Monitor** | `webui/backend/options_strategy/max_loss_manager.py` | In-memory ring buffer (200 events), monitor loop |
| **Backend — Alerts DB** | `webui/backend/db/alerts_db.py` | SQLite `alerts.db`, no action-on-trigger field |
| **Backend — Delta Hedge** | `webui/backend/routes/options/delta_hedge.py` | Auto-hedge config, order placement |
| **Backend — Order Executor** | `webui/backend/routes/options/order_executor.py` | `place_smart_order()`, `place_options_order()` |
| **Backend — Options Chain** | `webui/backend/options_chain/chain_service.py` + `chain_routes.py` | Expirations, chain data, ticker quotes |
| **Charting** | Recharts v2.9.0 | ComposedChart, Area, Line, ReferenceLine |
| **State Persistence** | `usePersistedState` hook → localStorage | Column visibility, settings |
| **Databases** | `options_groups.db`, `options_sl_tp.db`, `options_max_loss.db`, `alerts.db` | All SQLite, WAL mode |

---

## Feature 1 — Fix Activity Log (Bug Fix)

**Priority:** HIGHEST — blocks visibility of all other feature events
**Estimated complexity:** Medium
**Files to modify:** 4 backend + 1 frontend

### Root Cause Analysis

The bug is in `webui/backend/options_strategy/max_loss_manager.py`:
- **Line ~782:** `_monitor_loop()` calls `add_activity_event("idle", "No active max loss limits configured", ...)` every iteration when no limits exist
- The iteration guard `iteration % 12 == 1` means it fires every ~60s (12 iterations * 5s = 60s), but that still fills the 200-event buffer in ~3.3 hours
- **`_check_count`** (line 622) only increments inside `check_now()` and when active checks run — it stays 0 when there are no limits because the code early-returns before incrementing

### Implementation Plan

#### Backend Changes

**File: `webui/backend/options_strategy/max_loss_manager.py`**

1. **Add state tracking flag** near line 46:
   ```
   _last_limit_state = None  # Track "no_limits" / "has_limits" to log state changes only
   ```

2. **Fix `_monitor_loop()`** around line 778-785:
   - Replace the unconditional `add_activity_event("idle", ...)` with state-change detection:
     - If `_last_limit_state != "no_limits"`: log once, set `_last_limit_state = "no_limits"`
     - If `_last_limit_state == "no_limits"`: skip logging entirely
     - When limits are detected: set `_last_limit_state = "has_limits"`
   - Always increment `_check_count` at the top of each loop iteration (even when no limits exist) — this represents the monitoring heartbeat, not "found something to check"

3. **Add `type` field enforcement** in `add_activity_event()` (line 51):
   - Validate `event_type` against allowed set: `{"trade", "hedge", "alert", "error", "system", "roll", "monitor_start", "check_start", "position_check", "warning", "breach", "closing", "idle"}`
   - Map legacy types: `monitor_start` → `system`, `check_start`/`position_check` → `system`, `breach`/`closing` → `trade`, `idle` → `system`
   - Add a `category` field derived from type for frontend filtering

4. **Increase buffer** from 200 to 500:
   - Change `_MAX_ACTIVITY_LOG_SIZE = 500`

5. **Add SQLite persistence** — new file: `webui/backend/db/activity_log_db.py`
   - Table schema:
     ```sql
     CREATE TABLE activity_log (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       timestamp TEXT NOT NULL,
       type TEXT NOT NULL,
       category TEXT NOT NULL,
       message TEXT NOT NULL,
       details TEXT,  -- JSON blob
       created_at REAL DEFAULT (strftime('%s','now'))
     );
     CREATE INDEX idx_activity_timestamp ON activity_log(timestamp);
     CREATE INDEX idx_activity_category ON activity_log(category);
     ```
   - Auto-prune entries older than 24 hours on each write (or via periodic cleanup)
   - `add_activity_event()` writes to both in-memory buffer AND SQLite
   - New function: `get_persisted_log(hours=24, category=None, limit=500)` for retrieval

6. **Add CSV export endpoint** in `options_control.py`:
   - `GET /api/options/monitoring-activity/export` → returns CSV with headers: `timestamp,type,category,message,details`
   - Content-Disposition: `attachment; filename=activity_log_YYYYMMDD.csv`

#### Frontend Changes

**File: `webui/frontend/src/components/options/OptionsActivityPanel.js`**

1. **Add filter buttons** above the event list (after monitor status bar):
   - Buttons: `[All] [Trades] [Hedges] [Alerts] [Errors] [System]`
   - State: `activeFilter` (default: "All")
   - Filter events client-side using the `category` field from backend
   - Style: pill-shaped toggle buttons using existing MUI ButtonGroup

2. **Add "Export CSV" button** next to the filter bar:
   - onClick: `window.open('/api/options/monitoring-activity/export')`
   - Small download icon button

3. **Fix Checks counter display** — no frontend change needed (backend fix makes the counter increment properly)

### Testing Checklist
- [ ] Start with 0 max loss limits → verify only 1 "idle" event logged, not repeated
- [ ] Add a limit → verify "has_limits" state change logged
- [ ] Remove limit → verify "no_limits" logged once
- [ ] Checks counter increments every cycle
- [ ] Filter buttons correctly filter events by category
- [ ] CSV export downloads valid file
- [ ] 500-event buffer works correctly
- [ ] SQLite persists across backend restarts

---

## Feature 2 — IV Rank / IV Percentile

**Priority:** High
**Estimated complexity:** Medium-High
**Files to modify:** 2 backend + 3 frontend
**Dependency:** None (independent)

### Current State

- Each position has `iv` field (raw IV%, e.g., 0.534 for 53.4%)
- IV is enriched from Delta Exchange API with 60s cache in `useOptionsPositions.js`
- No historical IV storage exists anywhere in the codebase
- `payoffCalculator.js` is SEALED — should not be modified

### Implementation Plan

#### Backend Changes

**New file: `webui/backend/db/iv_history_db.py`**

1. **SQLite table** in `webui/backend/data/iv_history.db`:
   ```sql
   CREATE TABLE iv_history (
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     symbol TEXT NOT NULL,          -- e.g., "C-BTC-72000-260313"
     strike REAL NOT NULL,
     expiry TEXT NOT NULL,          -- "2026-03-13"
     option_type TEXT NOT NULL,     -- "call" or "put"
     iv REAL NOT NULL,              -- raw IV as decimal
     spot_price REAL,               -- BTC spot at time of recording
     timestamp REAL NOT NULL,       -- Unix timestamp
     UNIQUE(symbol, timestamp)      -- Prevent duplicates
   );
   CREATE INDEX idx_iv_symbol_time ON iv_history(symbol, timestamp);
   ```

2. **Recording function:** `record_iv_snapshot(positions_list)` — called from the dashboard cache refresh cycle (every 5s, but only write to DB every 5 minutes to avoid bloat)
   - Extract `{symbol, strike, expiry, option_type, iv, spot}` from each position
   - INSERT OR IGNORE into `iv_history`

3. **Computation functions:**
   ```python
   def get_iv_rank(symbol, current_iv, lookback_days=365):
       """IVR = (current - 52w_low) / (52w_high - 52w_low) * 100"""
       # Query min/max IV for this symbol over lookback period
       # Return IVR as 0-100 integer

   def get_iv_percentile(symbol, current_iv, lookback_days=365):
       """IVP = % of days where IV was lower than current"""
       # Count days where IV < current_iv / total days
       # Return IVP as 0-100 integer

   def get_iv_stats(symbol, lookback_days=365):
       """Return {ivr, ivp, high_52w, low_52w}"""
   ```

4. **Batch endpoint** in `options_control.py`:
   - `GET /api/options/iv-stats` → returns `{symbol: {ivr, ivp, high_52w, low_52w}}` for all current positions
   - Called by frontend on load and every 60s

**Caveat:** For newly listed options (< 365 days of data), use whatever history is available. If < 5 data points exist, show "N/A" instead of a misleading IVR.

#### Frontend Changes

**File: `webui/frontend/src/components/options/OptionsPanel.js`**

1. **Add to `DEFAULT_VISIBLE_COLUMNS`** (line ~608):
   ```javascript
   ivr: false,  // Hidden by default
   ```
2. **Add to `columnDefs`** (line ~629):
   ```javascript
   { key: 'ivr', label: 'IVR' },
   ```

**File: `webui/frontend/src/components/options/PositionRow.js`**

1. **Add IVR cell** rendering:
   - Fetch IVR data from a new context or prop passed down from OptionsPanel
   - Badge rendering:
     - 0-30: green chip, text "Low"
     - 31-60: yellow chip, text "Mid"
     - 61-100: red chip, text "Rich"
   - Tooltip on hover: `"IVP: {ivp} | 52W: {low_52w}% - {high_52w}%"`
   - Use MUI Chip + Tooltip components (already in use)

**File: `webui/frontend/src/components/options/PortfolioGreeksSummary.js`**

1. **Add per-expiry average IVR** to the summary bar:
   - Calculate weighted average IVR per expiry group
   - Display as: `IVR: Mar13 42 | Mar20 38 | Mar27 55`
   - Only show if IVR data is available

**New hook: `webui/frontend/src/hooks/useIVStats.js`**
- Polls `GET /api/options/iv-stats` every 60s
- Returns `{ivStats, loading}` — map of symbol → {ivr, ivp, high_52w, low_52w}

### Data Growth Concern
- 40 positions * 1 write every 5 minutes = 480 rows/hour = ~11,500 rows/day
- 365 days = ~4.2M rows — manageable for SQLite but should add periodic pruning
- Add a cleanup job: on startup, delete rows older than 400 days

---

## Feature 3 — Per-Position Greeks

**Priority:** High
**Estimated complexity:** Medium
**Files to modify:** 2 backend + 3 frontend
**Dependency:** None (independent, but enhances Feature 4)

### Current State

- `dashboard_service.py` has `calculate_portfolio_greeks(positions)` (SEALED) that returns aggregate Greeks
- `payoffCalculator.js` (SEALED) has `blackScholesPrice()`, `normalCDF()`, `normalPDF()` — full BS implementation but only for payoff curves
- The `/api/options/dashboard` response already includes a `greeks` object at the portfolio level: `{delta, gamma, theta, vega}`
- Individual positions have `iv` but NOT individual greeks in the API response
- `RISK_FREE_RATE = 0.0` (crypto standard) in `payoffCalculator.js`

### Implementation Plan

#### Backend Changes

**File: `webui/backend/routes/options/dashboard_service.py`**

1. **New function: `calculate_per_position_greeks(positions, spot_price)`**
   - For each position, compute:
     ```python
     d1 = (ln(S/K) + (r + sigma^2/2)*T) / (sigma * sqrt(T))
     d2 = d1 - sigma * sqrt(T)

     # Per-contract Greeks:
     delta_call = N(d1)          delta_put = N(d1) - 1
     gamma = n(d1) / (S * sigma * sqrt(T))
     theta_call = -(S*n(d1)*sigma)/(2*sqrt(T)) - r*K*exp(-rT)*N(d2)   (per year, convert to per day /365)
     theta_put  = -(S*n(d1)*sigma)/(2*sqrt(T)) + r*K*exp(-rT)*N(-d2)
     vega = S * n(d1) * sqrt(T) / 100   (per 1 vol point)

     # Scale by position size and CONTRACT_MULTIPLIER (0.001 for BTC):
     pos_delta = delta * abs(size) * multiplier * sign(size)
     pos_theta = theta * abs(size) * multiplier * sign(size)
     pos_gamma = gamma * abs(size) * multiplier
     pos_vega  = vega * abs(size) * multiplier * sign(size)
     ```
   - Input: `S` (spot), `K` (strike), `T` (DTE/365), `sigma` (IV), `r` (0.0), option type, size
   - Handle edge cases: T <= 0 → intrinsic value only, sigma <= 0 → skip

2. **Modify `fetch_options_positions_data()`** to attach per-position greeks:
   - After fetching positions, call `calculate_per_position_greeks()`
   - Attach `pos_greeks: {delta, gamma, theta, vega, dte}` to each position dict

3. **Add DTE computation:**
   - Parse expiry date string from position symbol (e.g., "260313" → 2026-03-13)
   - `dte = max(0, (expiry_date - today).days)`

#### Frontend Changes

**File: `webui/frontend/src/components/options/OptionsPanel.js`**

1. **Add to `DEFAULT_VISIBLE_COLUMNS`:**
   ```javascript
   dte: false,
   posDelta: false,
   posTheta: false,
   posGamma: false,
   posVega: false,
   ```
2. **Add to `columnDefs`:**
   ```javascript
   { key: 'dte', label: 'DTE' },
   { key: 'posDelta', label: 'Delta' },
   { key: 'posTheta', label: 'Theta' },
   { key: 'posGamma', label: 'Gamma' },
   { key: 'posVega', label: 'Vega' },
   ```

3. **Add per-expiry sub-total rows:**
   - After grouping positions by expiry (already done for expiry headers), insert a summary row
   - Summary row data: sum of delta/theta/gamma/vega for that expiry group
   - Style: darker background (`rgba(255,255,255,0.05)`), bold text, no action buttons
   - Render as a special `<TableRow>` variant (not a PositionRow)

**File: `webui/frontend/src/components/options/PositionRow.js`**

1. **Add Greek cells** (conditionally rendered based on `visibleColumns`):
   - Delta: format to 4 decimal places, color green if positive, red if negative
   - Theta: format to 2 decimal places + "$" sign (it's $/day)
   - Gamma: format to 6 decimal places
   - Vega: format to 2 decimal places + "$" sign
   - DTE: integer, bold if < 7 (approaching expiry)

### Performance Note
- BS Greeks calculation is O(1) per position — 40 positions is negligible
- Runs server-side as part of dashboard refresh (every 5s) — no extra API calls
- Frontend receives pre-computed Greeks, no client-side BS calculation needed

---

## Feature 4 — PnL Attribution by Greek Source

**Priority:** Medium-High
**Estimated complexity:** Medium
**Files to modify:** 1 backend + 2 frontend
**Dependency:** Feature 3 (needs per-position Greeks for accuracy, but can use aggregate Greeks)

### Current State

- Portfolio PnL: -$359.49 (total, no breakdown)
- Aggregate Greeks available: Delta +59.41, Theta +78.14, Gamma 0.117482, Vega 142.23
- BTC spot available in real-time
- No session snapshot mechanism exists

### Implementation Plan

#### Backend Changes

**File: `webui/backend/routes/options/dashboard_service.py`** (or new helper)

1. **Session snapshot storage:**
   - On first `/api/options/dashboard` call (or explicit `/api/options/pnl-attribution/reset`), capture:
     ```python
     _pnl_baseline = {
       "spot": btc_spot,
       "iv_avg": weighted_avg_iv,
       "delta": portfolio_delta,
       "gamma": portfolio_gamma,
       "theta": portfolio_theta,
       "vega": portfolio_vega,
       "total_pnl": total_unrealized_pnl,
       "timestamp": time.time()
     }
     ```
   - Store in module-level variable (resets on backend restart)
   - Add `POST /api/options/pnl-attribution/reset` to manually reset baseline

2. **Attribution computation** — add to dashboard response or new endpoint `GET /api/options/pnl-attribution`:
   ```python
   dS = current_spot - baseline_spot
   dIV = current_iv_avg - baseline_iv_avg
   dt_hours = (time.time() - baseline_timestamp) / 3600

   delta_pnl = baseline_delta * dS
   gamma_pnl = 0.5 * baseline_gamma * dS * dS
   theta_pnl = baseline_theta * (dt_hours / 24)
   vega_pnl  = baseline_vega * dIV
   residual  = (current_total_pnl - baseline_total_pnl) - (delta_pnl + gamma_pnl + theta_pnl + vega_pnl)

   return {
     "delta_pnl": round(delta_pnl, 2),
     "gamma_pnl": round(gamma_pnl, 2),
     "theta_pnl": round(theta_pnl, 2),
     "vega_pnl": round(vega_pnl, 2),
     "residual_pnl": round(residual, 2),
     "total_change": round(current_total_pnl - baseline_total_pnl, 2),
     "spot_change": round(dS, 2),
     "iv_change": round(dIV, 4),
     "elapsed_hours": round(dt_hours, 2),
     "baseline_timestamp": baseline_timestamp
   }
   ```

#### Frontend Changes

**New component: `webui/frontend/src/components/options/PnLAttributionPanel.js`**

1. **Collapsible panel** below PortfolioGreeksSummary:
   - Collapsed by default, toggle with "PnL Attribution" header + chevron
   - Uses existing Collapse/Accordion MUI component pattern

2. **Horizontal stacked bar chart** (Recharts BarChart):
   - 5 segments: Delta (blue), Gamma (purple), Theta (green), Vega (orange), Residual (gray)
   - Each segment labeled with $ value
   - Total change shown at the right end

3. **Stats row below chart:**
   - `"Spot: $70,975 (dS: -$1,938) | IV avg: 57.2% (dIV: +1.3pts) | Elapsed: 6.2h"`
   - "Reset Baseline" button → calls `POST /api/options/pnl-attribution/reset`

4. **Data fetching:** Include in the existing dashboard poll (add `pnl_attribution` to dashboard response) OR poll separately every 30s

**File: `webui/frontend/src/pages/OptionsPage.js`**

1. **Insert PnLAttributionPanel** between PortfolioGreeksSummary and the position table

### Design Decision: Baseline Strategy
- **Option A:** Auto-reset at midnight UTC (daily attribution) — simpler
- **Option B:** Reset at "session start" (first page load) — more intuitive for intraday
- **Recommendation:** Use Option B (session start) with manual reset button. The baseline timestamp is shown so the user knows the reference point.

---

## Feature 5 — Conditional Execution on Price Alerts

**Priority:** Medium-High
**Estimated complexity:** High
**Files to modify:** 2 backend + 2 frontend
**Dependency:** Feature 1 (activity log must support "alert" event type)

### Current State

- `alerts_db.py` schema has 17 columns — NO action field
- Alert trigger logic in `trigger_alert()` (lines 186-225) only updates status and records history
- Price alert monitoring runs in `webui/backend/services/price_alert_monitor.py`
- Frontend alert creation form exists but has no action dropdown
- Existing API: `POST /api/options/alerts` for creation

### Implementation Plan

#### Backend Changes

**File: `webui/backend/db/alerts_db.py`**

1. **Schema migration** — add columns to `price_alerts`:
   ```sql
   ALTER TABLE price_alerts ADD COLUMN action_type TEXT DEFAULT 'none';
   -- Values: 'none', 'close_positions', 'execute_hedge', 'send_webhook'
   ALTER TABLE price_alerts ADD COLUMN action_config TEXT DEFAULT '{}';
   -- JSON blob with action-specific params:
   -- close_positions: {"expiry": "2026-03-13" or "all"}
   -- execute_hedge: {"size_btc": 2.0, "order_type": "market"}
   -- send_webhook: {"url": "https://..."}
   ```

2. **Add Greek-based alert table:**
   ```sql
   CREATE TABLE greek_alerts (
     id TEXT PRIMARY KEY,
     metric TEXT NOT NULL,          -- 'delta', 'vega', 'margin_pct'
     condition TEXT NOT NULL,       -- 'gt', 'lt'
     threshold REAL NOT NULL,
     action_type TEXT DEFAULT 'none',
     action_config TEXT DEFAULT '{}',
     status TEXT DEFAULT 'active',
     note TEXT,
     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
     triggered_at TIMESTAMP,
     cooldown_minutes INTEGER DEFAULT 60,
     last_triggered_at TIMESTAMP
   );
   ```

3. **New CRUD methods:**
   - `create_greek_alert(metric, condition, threshold, action_type, action_config, note)`
   - `get_active_greek_alerts()`
   - `trigger_greek_alert(alert_id, current_value)`

**File: `webui/backend/services/price_alert_monitor.py`**

1. **Add action execution** after trigger:
   ```python
   def _execute_alert_action(alert):
       action_type = alert.get('action_type', 'none')
       config = json.loads(alert.get('action_config', '{}'))

       if action_type == 'close_positions':
           expiry = config.get('expiry', 'all')
           # Call batch close API internally
           _close_positions_for_expiry(expiry)

       elif action_type == 'execute_hedge':
           size = config['size_btc']
           order_type = config.get('order_type', 'market')
           # Call delta hedge placement
           _place_hedge_order(size, 'sell', order_type)

       elif action_type == 'send_webhook':
           url = config['url']
           payload = _build_webhook_payload(alert)
           requests.post(url, json=payload, timeout=10)

       # Log to activity log
       add_activity_event("alert", f"Alert triggered: {alert['direction']} ${alert['target_price']}", {
           "alert_id": alert['id'],
           "action": action_type,
           "price": current_price
       })
   ```

2. **Add Greek alert monitoring** to the monitor loop:
   - Every check cycle, fetch current portfolio Greeks from dashboard cache
   - Compare against active Greek alerts
   - Trigger + execute action if condition met (with cooldown respect)

3. **New endpoints** in `options_control.py`:
   - `POST /api/options/greek-alerts` — create Greek alert
   - `GET /api/options/greek-alerts` — list all
   - `DELETE /api/options/greek-alerts/<id>` — delete

#### Frontend Changes

**Modify alert creation form** (in OptionsPanel.js or dedicated alert component):

1. **Add "Action" dropdown** after the existing form fields:
   - Options: `None | Close Positions | Execute Hedge | Send Webhook`
   - Conditional sub-fields based on selection:
     - Close Positions → Expiry selector (Mar 13 / Mar 20 / Mar 27 / All)
     - Execute Hedge → BTC amount input + Order Type (Market/Smart)
     - Send Webhook → URL text input

2. **Add "Action" column** to the alerts table:
   - Shows action type as a chip/badge, or "—" for none

3. **Add "Greek Alert" tab/section** in the New Alert form:
   - Toggle: "Price Alert" / "Greek Alert"
   - Greek Alert fields: Metric dropdown (Delta/Vega/Margin%), Condition (>/< ), Threshold input
   - Same Action dropdown as price alerts

4. **Display Greek alerts** in a separate table section below price alerts

### Security Considerations
- Webhook URLs should be validated (https only, no localhost/internal IPs)
- Rate-limit webhook calls (max 1 per alert per cooldown period)
- Log all action executions for audit trail

---

## Feature 6 — Payoff Graph Fixes

**Priority:** Medium
**Estimated complexity:** Medium
**Files to modify:** 1 frontend (OptionsPayoffDiagram.js)
**Dependency:** None

### Current State

- Time slider: `targetDaysFromNow` state, passed to `useChartData()` — max is calculated from nearest expiry only
- Compare: `scenarioCompare` boolean + `baselineRef` — captures baseline but no scenario controls rendered
- Breakevens: Shows first 2 inline + popover for rest

### Implementation Plan

#### Fix 1: Time Slider Range

**File: `webui/frontend/src/components/options/OptionsPayoffDiagram.js`**

1. **Compute max from furthest expiry:**
   - Find `Math.max(...positions.map(p => p.dte))` → use as slider max
   - Currently uses nearest expiry — change to use `maxDTE`

2. **Add expiry marker ticks on slider:**
   - Compute unique DTE values from positions (8, 15, 22)
   - Render MUI Slider with `marks` prop:
     ```javascript
     marks={[
       { value: 8, label: 'Mar 13' },
       { value: 15, label: 'Mar 20' },
       { value: 22, label: 'Mar 27' },
     ]}
     ```

3. **Filter expired positions in payoff calc:**
   - When slider is at day X, filter positions where `dte < X` out of the payoff calculation
   - This means at day 15, Mar 13 positions are excluded (already expired)
   - The `useChartData()` hook needs to accept `targetDate` and filter accordingly

#### Fix 2: Compare Scenario Controls

1. **When `scenarioCompare` is checked**, render a control panel below the chart:
   ```
   [Compare Scenario]
   BTC Offset: [slider -30% to +30%]    IV Offset: [slider -20 to +20 pts]    Time: [slider 0 to maxDTE days]
   ```

2. **Render second payoff curve:**
   - Apply offsets to spot/IV/time
   - Recalculate payoff with modified parameters
   - Plot as dashed line in orange (current is solid blue)

3. **Show comparison stats box:**
   ```
   Current PnL at target: -$359 | Scenario PnL: +$512 | Diff: +$871
   ```

#### Fix 3: Always Show All Breakevens

1. **Remove the popover/collapse logic** (lines ~773-836)
2. **Render all breakevens inline:**
   ```javascript
   breakevens.map(be => <Chip label={`$${be.price} (${be.pct}%)`} />)
   ```
3. If more than 4 breakevens, wrap to a second line using `flexWrap: 'wrap'`

### Risk
- `payoffCalculator.js` is marked SEALED — the time filtering and scenario offset logic must be implemented in `usePayoffData.js` or `OptionsPayoffDiagram.js`, NOT in the calculator itself
- The `useChartData()` hook may need modification to accept additional parameters

---

## Feature 7 — IV Term Structure Chart

**Priority:** Medium
**Estimated complexity:** Low
**Files to modify:** 1 new frontend component + 1 page integration
**Dependency:** None (uses existing position IV data)

### Implementation Plan

**New file: `webui/frontend/src/components/options/VolTermStructurePanel.js`**

1. **Data computation** (no backend needed — use positions from `useOptionsPositions`):
   ```javascript
   function computeTermStructure(positions, spotPrice) {
     const expiryGroups = groupBy(positions, 'expiry');
     return Object.entries(expiryGroups).map(([expiry, positions]) => {
       const atmPositions = positions.filter(p =>
         Math.abs(p.strike - spotPrice) / spotPrice <= 0.05  // within 5%
       );
       const callATM = avgIV(atmPositions.filter(isCall));
       const putATM = avgIV(atmPositions.filter(isPut));
       const combinedATM = avgIV(atmPositions);
       return { expiry, dte, atmIV: combinedATM, callIV: callATM, putIV: putATM };
     }).sort((a, b) => a.dte - b.dte);
   }
   ```

2. **Recharts LineChart:**
   - X-axis: DTE (8, 15, 22)
   - Y-axis: ATM IV%
   - 3 lines: Combined (white/bold), Call-weighted (blue), Put-weighted (red)
   - Dot markers at each data point with labels

3. **Term structure label:**
   - If short-term IV > long-term IV: red badge "Vol Backwardation"
   - If short-term IV < long-term IV: green badge "Vol Contango"
   - Show: `"Term spread: Mar13-Mar27 = +5.5 vol pts"`

4. **Panel wrapper:** Collapsible card with "Vol Structure" header, collapsed by default

**File: `webui/frontend/src/pages/OptionsPage.js`** (or OptionsPanel.js)

1. Insert `<VolTermStructurePanel>` below PortfolioGreeksSummary (and below PnL Attribution if implemented)

---

## Feature 8 — Volatility Skew / Smile Chart

**Priority:** Medium
**Estimated complexity:** Low
**Files to modify:** 1 new frontend component + 1 page integration
**Dependency:** None (uses existing position IV data)

### Implementation Plan

**New file: `webui/frontend/src/components/options/VolSmilePanel.js`**

1. **Expiry tab selector:**
   - MUI Tabs: `[Mar 13] [Mar 20] [Mar 27]`
   - Default to the expiry with most positions (Mar 20)

2. **Recharts ScatterChart + fitted curve:**
   - X-axis: Strike price ($54K to $79K)
   - Y-axis: IV%
   - Two scatter series: Calls (blue dots), Puts (red dots)
   - Reference line at current spot price ($70,975) — vertical dashed line
   - Optional: polynomial curve fit through points (degree 2-3) using least squares
     - Simple approach: use Recharts `Line` through sorted data points (connect-the-dots is sufficient for 6-10 points per expiry)

3. **Put Skew metric:**
   - Approximate 25-delta strikes from the position data
   - `Put Skew = IV(OTM Put near 25-delta) - IV(OTM Call near 25-delta)`
   - Display as badge: `"Put Skew: +8.2 pts"` with warning if > 5

4. **Real-time updates:** Since it reads from the positions array (already in React state), it auto-updates when IV refreshes

5. **Panel wrapper:** Collapsible, collapsed by default, placed below Vol Structure panel

**Data source:** Pure frontend computation from `positions` array — no backend endpoint needed.

### Limitation
- With only 6 positions in Mar 13, the smile curve will be sparse
- Mar 20 has 30 positions — best data for a meaningful smile
- Should show a note: "N positions used" on each tab

---

## Feature 9 — Roll Management Tool

**Priority:** Medium
**Estimated complexity:** High
**Files to modify:** 2 backend + 2 new frontend
**Dependency:** Uses order_executor.py, chain_service.py

### Current State

- No roll mechanism exists
- Order placement via `place_smart_order()` in `order_executor.py`
- Options chain quotes available via `GET /api/options-chain/ticker/<symbol>`
- Batch close exists in options_control.py
- Position symbol format: `C-BTC-72000-260313` (Type-Asset-Strike-YYMMDD)

### Implementation Plan

#### Backend Changes

**File: `webui/backend/routes/options/options_control.py`** (or new `roll_manager.py`)

1. **Quote fetch for target expiry:**
   ```python
   @options_bp.route('/api/options/roll/quotes', methods=['POST'])
   def get_roll_quotes():
       """Fetch bid/ask for target expiry options"""
       positions = request.json['positions']  # [{symbol, strike, type, size, target_expiry, target_strike}]
       quotes = []
       for pos in positions:
           target_symbol = build_symbol(pos['type'], 'BTC', pos['target_strike'], pos['target_expiry'])
           ticker = chain_service.get_ticker(target_symbol)
           quotes.append({
               'current_symbol': pos['symbol'],
               'target_symbol': target_symbol,
               'target_bid': ticker['best_bid'],
               'target_ask': ticker['best_ask'],
           })
       return jsonify({'success': True, 'quotes': quotes})
   ```

2. **Roll execution endpoint:**
   ```python
   @options_bp.route('/api/options/roll/execute', methods=['POST'])
   def execute_roll():
       """Execute roll: close current + open target for each selected position"""
       rolls = request.json['rolls']
       # For each roll:
       #   1. Close current position (buy back if short, sell if long) via Smart order
       #   2. Open target position (sell if was short, buy if was long) via Smart order
       #   3. Log each leg to activity log with type "roll"
       results = []
       for roll in rolls:
           close_result = place_smart_order(close_params)
           open_result = place_smart_order(open_params)
           results.append({...})
           add_activity_event("roll", f"Rolled {roll['symbol']} to {roll['target']}", {...})
       return jsonify({'success': True, 'results': results})
   ```

#### Frontend Changes

**New file: `webui/frontend/src/components/options/RollManagerModal.js`**

1. **Modal dialog** (MUI Dialog, fullWidth, maxWidth="lg"):
   - Header: "Roll Expiry — Mar 13, 2026 (6 positions)"
   - Table columns:
     | Select | Symbol | Strike | Side | Size | Current Bid/Ask | Roll To Expiry | Target Strike | Target Bid/Ask | Est. Debit/Credit |
   - Roll-to Expiry: dropdown (Mar 20 / Mar 27)
   - Target Strike: editable input (defaults to same strike)
   - Estimated Debit/Credit: calculated from current close price vs target open price

2. **Net Roll Cost calculation:**
   ```
   For each selected position:
     If LONG: close at bid (selling), open at ask (buying) → cost = target_ask - current_bid
     If SHORT: close at ask (buying back), open at bid (selling) → credit = target_bid - current_ask
   Net = sum of all position costs/credits * size * CONTRACT_MULTIPLIER
   ```
   - Display prominently at bottom: `"Net Roll Cost: -$234.50 (debit)"` or `"+$150.00 (credit)"`

3. **Warning banner** if roll cost > 20% of original premium:
   - Red alert: "Roll cost exceeds 20% of original premium collected. Consider alternative strategies."

4. **Execute button:**
   - Calls `POST /api/options/roll/execute` with selected positions
   - Shows progress spinner during execution
   - On success: close modal, refresh positions, show success toast

5. **Quote refresh:** "Refresh Quotes" button to re-fetch target expiry bid/ask

**File: `webui/frontend/src/components/options/OptionsPanel.js`**

1. **Add "Roll" button** next to each expiry group header (where "13/03/2026 (6)" is shown)
   - Only show for expiries within 14 DTE (approaching expiry)
   - Opens RollManagerModal with that expiry's positions pre-loaded

### Execution Risk
- Rolls are NOT atomic — close and open are separate orders that can partially fill
- Should warn user: "Roll executes as 2 separate orders per position. Market conditions may change between legs."
- Consider: execute close first, wait for fill confirmation, then place open — sequential, not parallel

---

## Dependency Graph & Execution Order

```
Feature 1 (Activity Log Fix)
    ↓ [must be first — all other features log to activity]
Feature 3 (Per-Position Greeks)
    ↓ [Feature 4 needs per-position Greeks]
Feature 4 (PnL Attribution)
    ↓ [independent after F3]
Feature 2 (IV Rank/Percentile) — independent, can parallel with F3/F4
Feature 5 (Conditional Alerts) — depends on F1 for activity logging
Feature 6 (Payoff Graph Fixes) — independent
Feature 7 (Vol Term Structure) — independent, pure frontend
Feature 8 (Vol Smile) — independent, pure frontend
Feature 9 (Roll Manager) — independent, highest code complexity
```

### Recommended Execution Order

| Phase | Features | Reason |
|-------|----------|--------|
| **Phase 1** | F1 (Activity Log) | Unblocks all event logging |
| **Phase 2** | F3 (Per-Position Greeks) + F7 (Vol Term Structure) + F8 (Vol Smile) | F3 is prerequisite for F4; F7/F8 are pure frontend, parallelizable |
| **Phase 3** | F4 (PnL Attribution) + F2 (IV Rank) + F6 (Payoff Fixes) | F4 needs F3 done; F2/F6 independent |
| **Phase 4** | F5 (Conditional Alerts) + F9 (Roll Manager) | Most complex features, do last |

### Estimated File Changes Summary

| Feature | Backend Files | Frontend Files | New Files | DB Changes |
|---------|--------------|----------------|-----------|------------|
| F1 | 2 modified | 1 modified | 1 new (activity_log_db.py) | New SQLite table |
| F2 | 2 modified | 3 modified | 2 new (iv_history_db.py, useIVStats.js) | New SQLite table |
| F3 | 1 modified | 2 modified | 0 | None |
| F4 | 1 modified | 1 modified | 1 new (PnLAttributionPanel.js) | None |
| F5 | 2 modified | 2 modified | 0 | 2 new columns + 1 new table |
| F6 | 0 | 1 modified | 0 | None |
| F7 | 0 | 1 modified | 1 new (VolTermStructurePanel.js) | None |
| F8 | 0 | 1 modified | 1 new (VolSmilePanel.js) | None |
| F9 | 1 modified | 1 modified | 2 new (roll endpoint + RollManagerModal.js) | None |
| **Total** | **~9** | **~13** | **~8 new** | **2 new tables + 2 new columns** |
