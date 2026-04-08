import sys

content = r"""# MMMX WebUI — Mission-Critical Control Terminal Specification

**Date:** 2026-04-07  
**Purpose:** Define the MMMX WebUI as the **primary operator control layer** for real-money operations.  
**Scope:** UI/UX architecture, control governance, event/state model, failure escalation, and operator runbooks.  
**Out of Scope:** Strategy math, exchange execution internals, backend code implementation.

---

## 1. MMM UI ANALYSIS (EXISTING STATE)

### What Exists
- Flat parameter table displaying un-grouped configuration variables.
- Simple single-panel display for Pnl and delta.
- Basic start/stop buttons for monitor thread control.
- Rudimentary log tailing panel.

### What Works Well
- Immediate Websocket-driven log visibility.
- Lightweight control surface without over-engineered animations.

### What is Dangerous / Missing
- **No Hierarchical Tranche View:** Legacy UI does not distinguish parent deployments from their DTE-shifted recovery children (e.g. 2A, 2B).
- **No Explicit Protection Priority:** When a hard stop or shield is blocked, the UI does not visually escalate the blocked state or the "winning" trigger.
- **Hidden Invariants:** Stale monitors / "Phantom positions" can occur if the user double-clicks deploy or pause/resumes aggressively without Reconcile gates.
- **Blind during 'Paused':** If the session pauses, operator loses sight of the listener's Near-ITM alerts or flash-crash indicators.
- **No Margin/Reserve Visuals:** 30-lot reserve and 80% margin utilization are implicit; the operator cannot see exhaustion approaching until it fails.
- **Lack of Confirmation Risk Previews:** Closing all positions currently lacks a snapshot of the exact loss/rollback impact before firing.

### What Must Be Improved for MMMX
- Shift from a flat dashboard to a **State-Driven Multi-Panel Terminal**.
- Introduce explicit **Risk Radar** isolating danger (CE/PE delta imbalance, reserve lot burn-down).
- Introduce **Reconciliation Gates** requiring explicit manual diff-checks after any API disconnect or restart.

---

## 2. MMMX UI REQUIREMENT EXTRACTION

### A. Control Actions
- **Session Lifecycle:** Create Draft, Validate Gates (DTE, IV), Scan Strikes, Deploy Tranche 1 (manual), Pause (stops monitor, keeps listener), Resume (gated by reconcile), Stop.
- **Execution Overrides:** Manual deploy (Tranches 2-10), Emergency close, Profit Booking manual targets.
- **Maintenance:** Force heartbeat, Reconcile exchange diffs.
- **Parameter Hot Reload:** Governed updates for risk parameters during live operations.

### B. Monitoring
- **Core Metrics:** Portfolio PnL, Total Realized/Unrealized, Portfolio Delta, IV State, Margin % Utilization.
- **Tranches:** Deployment queue (Tr 1-10) and Recovery lineage (2A, 2B, etc.).
- **Hedge positions:** Active, Displaced, or Orphaned states, parental linkage.
- **Safety Reserves:** CE Reserve Usage (X/30), PE Reserve Usage (X/30).
- **System States:** Hard Stop distance, Whipsaw Score (1-4) & level (Normal/Caution/Restrict/Cooldown), Circuit Breaker connection state (CLOSED/HALF_OPEN/OPEN).
- **Process Health:** Listener websocket status, Watchdog thread health.

### C. Risk Visibility (CRITICAL)
- **Imminent Danger Indicator:** Which side (CE or PE) is closest to ATM and how far away.
- **Exposure:** Delta per discrete position and Worst-Performing Tranche.
- **Reserve Exhaustion Risk:** Alerts when reserve drops below 10 lots.
- **Execution Risks:** Naked position alerts (delay in hedge), Pending partial fills/residuals.

---

## 3. FULL UI LAYOUT DESIGN (INSTITUTIONAL LEVEL)

*The interface is designed as an institutional multi-panel trading terminal. No scrolling required for critical metrics.*

### 3.1 TOP BAR (Global Control)
- **Session Status:** Color-coded chip (`DRAFT` [grey], `GATES_PASSED` [blue], `RUNNING` [green], `PAUSED` [amber], `COMPLETE/ERROR` [red]).
- **Connection Health:** 3 discrete pings (API REST, Exchange WS, Internal Watchdog).
- **Kill Switch:** High-contrast `CLOSE ALL` button (Requires double type-to-confirm).
- **Hard Stop Level:** Progress bar (e.g., -$450 / -$1200 MAX) turning red at 80%.
- **Heartbeat & Time:** UTC Clock, Next Heartbeat countdown timer.
- **Quick Controls:** Pause/Resume Session.

### 3.2 LEFT PANEL — CONTROL CENTER
- **Session Setup:** Strike Scanner (live bid/ask spread, IV rank), DTE Validation.
- **Deploy Command:** `Deploy Tranche 1` button (enabled only in `GATES_PASSED`).
- **Parameter Hot Reload:** Grouped accordion [Deployment], [Protection], [Hedging].
- **Profit Booking Panel:** Select Tranche -> Slider for target limit / percentage -> Submit.
- **Reconciliation Panel:** Opens diff-viewer overlay showing Local DB vs Exchange API.

### 3.3 MAIN PANEL — LIVE TRADING VIEW
**A. Portfolio Overview (Top slice):**
- Total PnL (Realized + Unrealized) vs Capital deployed.
- Portfolio Delta & Margin Utilization dial.
- Live Spot Price vs Rolling IV State.

**B. Tranche Table (Center slice):**
*Row per tranche with hierarchical indent for recovery:*
- **ID / Type:** `1` (Deploy) -> `1A` (Recovery).
- **CE/PE Strikes:** `67500 / 62000`.
- **Premium:** Collected vs Current Value.
- **Live PnL:** Green/Red.
- **Delta:** Position-specific exposure.
- **Status:** `ACTIVE`, `SHIELD_PENDING`, `CLOSED`.
- **Shift Count:** Integer (how many times rolled).
- **Actions:** `Book Profit`, `Force Close`.

**C. Hedge Table (Bottom slice):**
- **Parent Tranche:** Linked e.g. `H-Tr3`.
- **Cost / PnL:** Entry price vs current mark.
- **Status Tag:** `ACTIVE`, `DISPLACED` (parent moved), `ORPHANED` (parent closed).

### 3.4 RIGHT PANEL — RISK RADAR (CRITICAL)
- **CE vs PE Imbalance:** Visual scale comparing weighted deltas.
- **Closest to ATM Gauge:** Live tracking of the nearest strike to spot price.
- **Reserve Depletion Bars:** Two separate tracks: CE Recovery Lots (0-30), PE Recovery Lots (0-30).
- **Whipsaw Tracker:** Current Score (0-4), Level Tag (e.g. `RESTRICT [3]`), and Time-to-Decay countdown.
- **Circuit Breaker Status:** `CLOSED` (Healthy), `HALF_OPEN` (Retrying), `OPEN` (API Down).
- **Alert Queue:** Flashing cards for `NAKED POSITION`, `PARTIAL FILL STUCK`. 

### 3.5 BOTTOM PANEL — EVENT LOG
- **Chronological Stream:** Websocket-driven (`mmmx_*` events).
- **Severity Tagging:** L0 (Info), L1 (Warning), L2 (Actionable), L3 (Critical), L4 (Fatal).
- **Message Content:** Timestamp (UTC), Correlation ID, Deduped textual explanation.

---

## 4. COMPONENT ARCHITECTURE & STATE

**React / TypeScript Structure:**
- **State Management:** Strict `Context API` + `useReducer` mirroring backend session dictionary. 
- **WebSocket Hooks:** `useMMMXLiveState()` consuming `mmmx_status_tick` to rehydrate state globally.
- **API Service Layer:** Axios REST wrappers for Commands (`deploy`, `pause`, `update_params`), returning immediate causality tracking IDs.

**Key Components:**
- `<TerminalLayout>`: Strict flexbox grid, preventing overflow/scroll on main panels.
- `<TrancheGrid>`: Recursive tree-table rendering `<ParentRow>` and `<RecoveryRow>`.
- `<RiskRadar>`: Aggregates `session.delta`, `session.atm_distance`, `session._reverse` metrics.
- `<ActionConfirmModal>`: Reusable Tier-B/Tier-C risk preview dialog.

---

## 5. LIVE UPDATE SYSTEM (WebSocket-First)

**Rule:** UI does not poll. It reacts to the backend heartbeat and listener pulses.
- **`mmmx_status_tick`:** Fired every 1s by listener or 1h by monitor. Contains full PnL, margin, delta, and spot updates.
- **`mmmx_activity_log`:** Rings buffer events for Bottom Panel.
- **`mmmx_safety_gate`:** Emitted when a protection check modifies deployment availability.

**State Sync Strategy:**
1. Upon initial load or WS reconnect -> trigger REST `GET /api/mmmx/session/{id}` for authoritative `_schema_version=1` state.
2. Listen to WS updates to mutate local reducer.
3. If sequence generation ID skips, force full REST sync to prevent split-brain.

---

## 6. FAILURE VISIBILITY & ESCALATION (CRITICAL)

The UI must immediately flag when the system cannot defend itself:

1. **API Failure (CB OPEN):**
   - **Trigger:** Exchange times out.
   - **UI Change:** Top Strip turns solid Red. Deploy button locks.
   - **Action:** Shows "API Down - Waiting for 5s Retry Loop".
2. **Listener Stale / Watchdog Dead:**
   - **Trigger:** Health ping > 3 seconds old.
   - **UI Change:** Center Panel greyed out with "STALE STATE" overlay. 
   - **Action:** Manual "Force Reconnect / Ping" button appears.
3. **Naked Positions:**
   - **Trigger:** CE/PE leg mismatch detected in `session_state`.
   - **UI Change:** L3 Critical Alert Card pops in Risk Radar with audible/pulsing border.
   - **Action:** "Hedge Now (Market)" or "Emergency Close Unbalanced Leg".
4. **Partial Fills Stuck:**
   - **Trigger:** Order `filled_size < target_size` resting beyond timeout.
   - **UI Change:** Right panel queue shows "Residual: 5 lots CE @ 67000".
   - **Action:** "Retry Residual" or "Abandon Residual & Re-calc".
5. **Reconciliation Required:**
   - **Trigger:** Backend restarts or divergent state found.
   - **UI Change:** Resume button deeply disabled. Modal overlay interrupts screen.
   - **Action:** Opens Reconcile Workbench -> user must "Accept Exchange State" or "Accept Local State".

---

## 7. SAFETY CONTROLS (GATING & DIALOGS)

**Disabled Controls:**
- `Deploy Tranche` is visually disabled if: Session is Paused, Session is Reconciling, Circuit Breaker is OPEN, Whipsaw Score == 4, or Margin > 80%.

**Confirmation Tiers:**
- **Tier A (No Confirm):** Change visible chart scale, acknowledge L0 log.
- **Tier B (Double Click/Confirm):** Pause session, Resume session, Submit Hot Reload params.
- **Tier C (Type-to-Confirm + Risk Preview):** `CLOSE ALL` (Kill Switch), `Force Stop Session`.
  *(Risk Preview shows: "This will incur immediate -$450 realized loss at market wide spreads. Type 'CLOSE' to confirm.")*

---

## 8. HOT RELOAD PANEL DESIGN

Parameters must not be a flat list. Grouped by Operational Intent:

1. **Deployment Offense:** `tranche_deploy_move_pct` (2%), `tranche_deploy_iv_delta` (10).
2. **Protection Gates:** `otm_distance_pct`, `hard_stop_multiplier`.
3. **Hedging Policy:** `hedge_distance_pct`, `delay_seconds`.
4. **Whipsaw Control:** `score_thresholds`, `cooldown_minutes`.

**Component Interaction:**
- Input fields show `Current: 2.0%` -> `New: [ 2.5 ] %`.
- Hitting `Apply` triggers backend validation. 
- UI waits for `mmmx_param_ack` WS event before flashing green and updating `Current`.

---

## 9. EDGE CASE UI DESIGN

- **Recovery Tranches (2A, 2B, 2C):** Visualized as nested children under Tranche 2. Indentation + subset summation of PnL so the operator can see the performance of the full "Tranche 2 lineage".
- **Multiple Shields:** If BTC flashes 10%, Tranches 1, 2, 3 might shield simultaneously. The Risk Radar queues 3 pending `SHIELD_FIRE` events, locking the UI from manual interference until the execution pipeline resolves them sequentially.
- **Zero Reserve State:** Reserve Depletion Bar hits 0/30. Color: Black/Red. System Alert: `DEGRADED RECOVERY`. Next shield will forcefully cannibalize parent size (shrink to survive).
- **Orphan Hedges:** Tranche closes cleanly but hedge limit-sell fails. Hedge row remains in Main Panel flagged `ORPHANED` with an explicit "Close Orphan" button.

---

## 10. OPERATOR TEST SCENARIOS (WORKFLOW VALIDATION)

1. **Normal Deployment Flow:**
   *Expectation:* Operator sets DTE, clicks "Scan", sees green checkmarks on margin/liquidity. Clicks "Deploy Tranche 1". TopNav updates status to `RUNNING`.
2. **6% Crash -> Shield Fires:**
   *Expectation:* Risk radar `Closest to ATM` drops to 0%. Screen flashes warning. Bottom log streams: `Shield evaluating` -> `Executing Market Buyback` -> `Executing Limit Sell`. Tranche grid splits Tr1 into 1A. Reserve drops from 30 -> 20.
3. **API Down (Exchange Maintenance):**
   *Expectation:* Top bar Connection dot turns red. Circuit Breaker shows `OPEN`. Tranche grid greyed out. Deploy button disabled. Log prints `API Unreachable - Queuing actions`.
4. **Partial Fill on Deployment:**
   *Expectation:* Tranche row shows `Partial (4/10)`. Risk radar loads "Pending Residuals: 6 lots". After timeout, Reconcile panel highlights the mismatch.
5. **Hard Stop Hit:**
   *Expectation:* Portfolio PnL crosses red threshold. System auto-halts all processes. UI freezes offensive controls. Log streams mass close events. Top status turns `COMPLETE`.
6. **Restart + Reconcile:**
   *Expectation:* Post-crash recovery. UI loads into `PAUSED`. Resume button is grey. Modal "Reconcile Required" forces operator to map live exchange IDs against DB state before unlocking.

---

## 11. MISSING / UNDEFINED AREAS

The following definitions must be resolved by product owners prior to deployment:
1. **NOT DEFINED IN SPEC:** Multi-operator concurrency and event arbitration (what happens if Operator A and Operator B hit pause at exactly the same time?).
2. **NOT DEFINED IN SPEC:** Explicit UI Audio/Modality policy (Do hard-stop warnings mandate audible browser alarms?).
3. **NOT DEFINED IN SPEC:** Historical UI Session Retrospectives (Can the operator cleanly load and scrub through previous "COMPLETE" sessions visually?).
4. **NOT DEFINED IN SPEC:** Role-Based Access Controls (RBAC) separating "Viewer", "Operator", and "Admin" abilities in the frontend.
"""

with open("mmmx_webUI.md", "w") as f:
    f.write(content)
