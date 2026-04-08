# MMMX WebUI — Mission-Critical Control Terminal Specification

**Date:** 2026-04-07  
**Purpose:** Define the MMMX WebUI as the **primary operator control layer** for real-money operations.  
**Scope:** UI/UX architecture, control governance, event/state model, failure escalation, and operator runbooks.  
**Out of Scope:** Strategy math, exchange execution internals, backend code implementation.

---

## 1) Control-Layer Mission

The MMMX WebUI must function as an institutional-grade control terminal where:

- Operators can understand risk state immediately (no hidden criticals).
- Every high-impact action is deliberate, auditable, and reversible when safe.
- Protection-first logic remains visible and enforceable at all times.
- Stale state, silent failures, and ambiguous action outcomes are prevented by design.

**Design principle:** In uncertainty, the interface must degrade toward safety, not convenience.

---

## 2) Non-Negotiable Safety Invariants

The UI must enforce and communicate these invariants continuously:

1. **Hard stop is non-overridable once session is RUNNING.**
2. **Trigger priority is authoritative** (protection triggers always outrank deployment).
3. **Restart lands in PAUSED** and requires reconcile before resume.
4. **Listener-protection visibility remains live in PAUSED** (monitor paused does not mean blind).
5. **Recovery tranches are first-class citizens** in monitoring, audit, and controls.
6. **Reserve accounting is per-side (CE/PE)** and must be shown independently.
7. **Partial-fill residuals must remain explicitly tracked** until fully resolved.
8. **Orphan/displaced hedge states are explicit** and never hidden from operator view.

---

## 3) Terminal Layout (Institutional Multi-Panel)

## 3.1 Persistent Top Command Strip

Always visible, regardless of tab:

- Session status chip and generation/heartbeat age
- WebSocket health, listener health, watchdog health
- Portfolio P&L vs hard-stop usage bar
- Circuit breaker state and whipsaw level
- CE/PE reserve remaining
- Global incident counter (severity colored)

## 3.2 Left Rail — Session & Incident Control

- Session list with fast filters: All / Active / Draft / Done
- Per-session quick controls (context-safe): deploy, pause, resume, stop, force heartbeat
- **Incident Queue** ordered by severity and time-to-escalation

## 3.3 Center Pane — Execution Core

Primary tabs (in operator action order):

1. Status & Control Deck
2. Tranches (deployment + recovery lineage)
3. Trigger Engine (active winner + blocked reasons)
4. Execution Pipeline (intent/ack/partial/fill)
5. Profit Booking
6. Reconcile Workbench

## 3.4 Right Pane — Risk & Protection Stack

Persistent risk widgets:

- Hard stop status
- Portfolio delta + CE/PE lot imbalance
- ATM shield tracker and shift chain
- Reserve burn-down (CE and PE separate)
- Hedge book (active/displaced/orphaned)
- Margin guardian tier + utilization
- Whipsaw score + cooldown/decay timers

---

## 4) State Model & Control Gating

## 4.1 Session Lifecycle Surface

`DRAFT → GATES_PASSED → RUNNING ↔ PAUSED → COMPLETE/ERROR`

UI behavior by state:

- **DRAFT:** configuration and tranche-1 deploy preparation only.
- **GATES_PASSED:** deploy/start controls enabled.
- **RUNNING:** live controls + risk controls + full incident monitoring.
- **PAUSED:** no new offensive actions; protective visibility remains active.
- **COMPLETE/ERROR:** no new strategy actions; reconcile/forensics/export available.

## 4.2 Control Locking Rules

- Resume is blocked if reconcile-required flag is active.
- Deployment controls are blocked when protection-priority incidents are unresolved.
- Duplicate command submission is blocked while same command scope is pending.
- Any action that conflicts with active hard-stop closure is disabled.

---

## 5) Live Event & Data Model (WebSocket-First)

## 5.1 Principles

- WebSocket is the source of truth for live state.
- REST is command/request path and historical fetch path.
- Every mutating command uses correlation ID for causality tracking.

## 5.2 Required Event Domains

- **Lifecycle:** heartbeat, status change, monitor/listener/watchdog health
- **Risk:** pnl update, delta/imbalance, margin tier, whipsaw
- **Protection:** hard-stop fired, ATM shield events, reserve depletion, near-ITM emergency
- **Execution:** order intent, ack, partial fill, residual retry, fill complete
- **Reconcile:** divergence found/resolved
- **Config:** params changed (applied/rejected)

## 5.3 Command Outcome Contract

Each command should surface:

- Submitted (pending)
- Accepted/rejected (immediate)
- Completed/failed (event-confirmed)
- Operator-visible reason on rejection/failure

No control action should remain in ambiguous “clicked but unknown” state.

---

## 6) Incident Visibility & Escalation Ladder

## 6.1 Severity Model

- **L0 Info**
- **L1 Warning**
- **L2 Action Required**
- **L3 Critical**
- **L4 Terminal/Circuit-break**

## 6.2 Incident Card Requirements

Each incident card must include:

- Detection timestamp (UTC)
- Current severity
- Time-to-next escalation
- Current blocking impact (what controls are disabled)
- Recommended actions
- Acknowledgement record (who/when)

## 6.3 Must-Be-First-Class Incident Types

1. Naked position lifecycle
2. Partial-fill residual aging
3. WebSocket/listener stale condition
4. Reconcile divergence after restart
5. Reserve exhaustion/degraded recovery
6. Orphan hedge accumulation
7. API unavailable / circuit breaker OPEN

---

## 7) Safety Confirmation Design

## 7.1 Action Confirmation Tiers

- **Tier A (single confirm):** low-impact controls
- **Tier B (double confirm):** pause/resume/deploy actions
- **Tier C (typed confirmation + risk preview):** stop, forced close, reconcile mutation paths

## 7.2 Risk Preview Before Critical Action

Before Tier C action, show:

- current state snapshot
- expected immediate effects
- protections impacted
- rollback availability

No critical action should execute from a single accidental click.

---

## 8) Hot-Reload Governance Panel (Risk-Domain Grouping)

Avoid flat key-value editing. Group live params by operational intent:

1. **Deployment offense** (move%, IV delta, fairness, max/day)
2. **Protection gates** (delta thresholds, ATM protect, max shifts)
3. **Hedging policy** (enabled, distance, delay, threshold)
4. **Whipsaw control** (window, score thresholds, cooldown)
5. **Exit discipline** (`close_at_dte`, profit-booking controls)

For each change, the UI must display:

- previous value → new value
- expected risk impact
- backend result: applied vs rejected with reason
- audit reference

---

## 9) Edge-Case Operational Runbooks

## 9.1 Recovery Tranche Chain

- Parent and sibling chain (`2A`, `2B`, `2C`) shown as linked lineage.
- Each sibling shows independent status, P&L, and actionability.

## 9.2 Partial Fill Residual Handling

- Residual quantity, retry count, and next retry ETA must remain visible.
- Escalate if residual ages beyond threshold.

## 9.3 Reserve Depletion

- CE and PE reserves shown separately.
- Partial allocation events clearly logged.
- “Reposition without recovery” must be highlighted as degraded mode.

## 9.4 Orphan/Displaced Hedges

- Hedge state labels: ACTIVE / DISPLACED / ORPHANED / CLOSED
- Parent linkage retained even after orphaning.
- Orphaned hedges remain visible until explicit lifecycle end.

## 9.5 Restart + Reconcile

- Post-restart state is explicit: `PAUSED_RECONCILE_REQUIRED`
- Reconcile results require operator disposition per divergence.
- Resume control is enabled only when reconcile gate clears.

---

## 10) Operator Workflow Standard

## 10.1 Pre-Live Flow

1. Create session
2. Set expiry and validate gates
3. Scan strikes and review liquidity
4. Deploy tranche 1
5. Confirm transition to running state

## 10.2 Live Management Flow

1. Monitor command strip + incident queue
2. Confirm trigger engine winner and blocked reasons
3. Execute required controls (if needed)
4. Verify command completion through correlated events
5. Record intervention rationale in audit notes

## 10.3 Failure Handling Flow

1. Acknowledge incident
2. Run prescribed mitigation action
3. Confirm backend outcome via event stream
4. Reconcile if divergence exists
5. Return to protected steady state

---

## 11) Acceptance Test Matrix (UI Readiness)

The WebUI is ready only when all are demonstrably true:

- Hard-stop event cannot be manually bypassed.
- Pause/resume honors listener-live behavior.
- Trigger-priority winner is visible and explainable.
- Partial-fill residuals are visible until resolved.
- Reserve depletion and degraded recovery are explicit.
- Reconcile gate blocks resume when required.
- Command outcomes are never ambiguous.
- Incident escalation timeline is visible and auditable.
- Hedge displacement/orphaning is visible and linked.
- WebSocket disconnect/reconnect preserves consistent operator state.

---

## 12) Items Not Fully Defined in Spec

These require explicit operator/product decisions before production lock:

1. **NOT DEFINED IN SPEC:** Multi-operator concurrency policy and command arbitration.
2. **NOT DEFINED IN SPEC:** Role-based permissions model (viewer/operator/admin).
3. **NOT DEFINED IN SPEC:** Mandatory acknowledgement SLA per incident severity.
4. **NOT DEFINED IN SPEC:** Event replay retention depth after reconnect.
5. **NOT DEFINED IN SPEC:** Alert modality policy (visual-only vs audible/push requirements).
6. **NOT DEFINED IN SPEC:** Export retention and forensic data retention windows.

---

## 13) Implementation Guidance (Non-Code)

This document should be used as the UI contract for:

- product acceptance criteria
- operator runbook alignment
- QA/UAT scenario design
- backend-event contract validation

No strategy behavior should be changed to satisfy UI convenience.
The UI must adapt to safety invariants, not the other way around.

---

## 14) Final Objective

A trader/operator should be able to answer these questions within seconds, at any moment:

- What state is the session in, and why?
- What is the top risk right now?
- Which trigger/protection logic is currently winning?
- Which controls are safe, blocked, or required?
- What happened after the last action?

If any answer is unclear, the interface is not production-safe yet.

---

## 15) Critical Gap Analysis (Completion Delta — No Redesign)

This section adds only missing/weak areas not fully defined in Sections 1–14.

### 15.1 Identified Gaps

| Gap ID | Category | Gap | Severity | Current State |
|---|---|---|---|---|
| A1 | Control Safety | No explicit **Global Kill Switch** architecture (scope, arming, execution telemetry). | P0 | Missing |
| A2 | Control Safety | Action confirmation tiers exist, but no deterministic **pre-flight action validation/interlock** contract. | P1 | Weak |
| A3 | Control Safety | No operator error firewall for conflicting commands under load (double-submit, stale-context submit). | P1 | Weak |
| B1 | State Integrity | No continuous **UI vs backend integrity monitor** (sequence/hash/drift detection). | P0 | Missing |
| B2 | State Integrity | Reconcile workflow exists, but no persistent divergence watch badge outside Reconcile tab. | P1 | Weak |
| B3 | State Integrity | No explicit stale-state confidence state to auto-lock high-risk controls. | P0 | Missing |
| B4 | State Integrity | Event contract drift risk detected: backend emits `mmmx_whipsaw`; frontend subscribes `mmmx_whipsaw_update`. | P0 | Mismatch |
| C1 | Execution Visibility | No per-order **lifecycle timeline** (intent→ack→partial→retry→fill/failed). | P0 | Missing |
| C2 | Execution Visibility | Residual retry visibility exists implicitly, but no residual aging SLA timeline in UI. | P1 | Weak |
| C3 | Execution Visibility | No explicit “execution uncertain” state when event chain is incomplete. | P0 | Missing |
| D1 | Decision Support | No ranked **Action Recommendation Engine** with confidence and rationale. | P1 | Missing |
| D2 | Decision Support | Trigger winner is visible, but no full loser/exclusion explanation ladder. | P1 | Missing |
| D3 | Decision Support | No **delta/change-since-last-beat** operator panel. | P1 | Missing |
| E1 | Stress Mode | No dedicated **Critical Mode UI** (compressed, high-contrast, incident-first). | P0 | Missing |
| E2 | Stress Mode | No **Incident Auto-Focus** behavior to bring operator to highest-risk pane. | P1 | Missing |
| E3 | Stress Mode | No explicit time-pressure indicators (breach ETA, escalation ETA, stale ETA). | P1 | Missing |
| F1 | System Health | No composite **System Health Score + confidence** model. | P1 | Missing |
| F2 | System Health | No degradation state machine (Normal/Degraded/Critical/Unknown) tied to control locks. | P0 | Missing |

### 15.2 Immediate Safety Consequence

Without Sections 16–18 below, the WebUI remains vulnerable to:

- high-impact operator mistakes during stress,
- hidden state divergence between backend and frontend,
- ambiguous execution state during partial fills/retries,
- delayed recognition of terminal-risk incidents.

---

## 16) Missing Components — Detailed Designs Only

> Mandatory components 1–10 are defined below. Existing panels are extended/integrated, not redesigned.

### 16.1 Global Kill Switch System

**Purpose**  
Provide deterministic, immediate risk-off controls with full execution visibility.

**UI Location**  
Top command strip (persistent) + emergency floating control in Critical Mode.

**Data Required**

- `session.status`, `portfolio_pnl`, `hard_stop_usd`
- open active legs count (short/long)
- pending command queue size
- circuit breaker state
- latest reconcile flag

**Visual Design**

- Red two-state control: `SAFE` → `ARMED` → `EXECUTING`
- Progress rail with steps: signal accepted, close dispatched, fills confirmed, terminal state reached
- Distinct badges: `SESSION_KILL`, `GLOBAL_KILL`

**Operator Interaction**

- Tier C confirmation (typed phrase + risk preview)
- Choose scope (session/global)
- Post-fire panel locks offensive controls until completion certainty is reached

**Failure Behavior**

- If API unavailable: enters `KILL_DEGRADED`, auto-retries and raises L3 incident
- If command ack missing: marks `EXECUTION_UNCERTAIN`, forces reconcile gate

**Event Wiring**

- Listens: `mmmx_safety`, `mmmx_status_change`, `mmmx_tranche_closed`, `mmmx_heartbeat`, `mmmx_pnl_update`, `mmmx_circuit_breaker`
- Also reads: command response stream and pending command store
- Delay/missing rule: if no close progress events within timeout, escalate to L4 banner + auto-focus
- Implemented command progress stream: `mmmx_kill_switch_progress` (`accepted → session_result → completed` with `correlation_id`)
- **NOT DEFINED IN SPEC:** Unified command-ack websocket schema for non-kill mutating controls

**Failure Testing (expected UI behavior)**

| Scenario | Expected Behavior |
|---|---|
| API failure | Show `KILL_DEGRADED`, keep retry countdown visible, lock risk-on controls |
| WebSocket disconnect | Freeze progress at last confirmed step, show `STATE UNCERTAIN`, require reconcile before unlock |
| Partial data | Render partial progress with unknown nodes explicit (never green-wash) |
| Stale state | Auto-escalate severity and force Incident Auto-Focus to Reconcile/Status |

**Integration Points**

- Extends Section 3.1 command strip
- Uses Section 7 Tier C confirmation contract
- Enforces Section 4.2 locking rules

---

### 16.2 State Integrity Monitor

**Purpose**  
Continuously detect frontend/backend drift, stale feeds, and event-order integrity breaks.

**UI Location**  
Top strip integrity badge + detailed card in right risk stack.

**Data Required**

- heartbeat number monotonicity
- last websocket event timestamp
- last REST snapshot timestamp
- generation values (monitor/listener/session)
- reconcile divergence count

**Visual Design**

- Badge states: `SYNCED`, `DRIFT`, `STALE`, `UNKNOWN`
- Diff inspector drawer: field-level mismatch list

**Operator Interaction**

- “Run integrity check now” action
- “Open divergence diff” deep-link to Reconcile tab

**Failure Behavior**

- On `DRIFT/STALE`: block Tier B/C offensive actions
- On `UNKNOWN`: enforce reconcile-required lock

**Event Wiring**

- Listens: `mmmx_heartbeat`, `mmmx_status_change`, `mmmx_params_changed`, `mmmx_deployment_queue`, `mmmx_safety`
- Pulls periodic consistency snapshot via existing `GET /session/<id>`
- Delay/missing rule: if heartbeat/event sequence stalls > threshold, downgrade confidence and raise L2 incident
- **NOT DEFINED IN SPEC:** Backend snapshot checksum/version field for O(1) integrity validation

**Failure Testing (expected UI behavior)**

| Scenario | Expected Behavior |
|---|---|
| API failure | Freeze last verified snapshot, mark integrity `UNKNOWN`, lock risky controls |
| WebSocket disconnect | Transition `SYNCED→STALE` with timer; show last verified beat |
| Partial data | Show field-level “unknown” markers; never infer missing values |
| Stale state | Force reconcile prompt and persistent warning badge |

**Integration Points**

- Extends Section 4 control locking
- Feeds Section 6 incident queue
- Feeds Section 11 acceptance checks

---

### 16.3 Order Lifecycle Timeline

**Purpose**  
Expose full execution lifecycle per order to remove ambiguity in partial/retry states.

**UI Location**  
Center pane, Execution Pipeline tab (new sub-panel).

**Data Required**

- `order_id`, `client_order_id`, `tranche_id`, side, symbol
- requested/fill/residual quantity
- attempt number and mode (limit/market/emergency)
- reason codes (timeout, margin, duplicate, reject)
- timestamps for each transition

**Visual Design**

- Horizontal timeline per order lane
- Color semantics: queued/active/partial/retry/filled/failed
- Residual aging timer chip

**Operator Interaction**

- Filter by tranche, status, side, symbol
- Expand row for payload details and linked incidents

**Failure Behavior**

- If lifecycle chain breaks, mark order state `UNCERTAIN` and create incident

**Event Wiring**

- Listens existing: `mmmx_tranche_deployed`, `mmmx_tranche_closed`, `mmmx_safety` (fallback)
- Implemented granular lifecycle events: `mmmx_order_intent`, `mmmx_order_ack`, `mmmx_order_partial`, `mmmx_order_retry`, `mmmx_order_filled`, `mmmx_order_failed`
- Delay/missing rule: if no transition event after SLA window, auto-mark uncertain and escalate

**Failure Testing (expected UI behavior)**

| Scenario | Expected Behavior |
|---|---|
| API failure | Show retry/failed nodes with explicit reason path |
| WebSocket disconnect | Freeze timeline and display “live updates paused” strip |
| Partial data | Render unknown nodes instead of collapsing lifecycle |
| Stale state | Mark affected lanes uncertain and deep-link to Reconcile |

**Integration Points**

- Extends Section 3.3 Execution Pipeline
- Drives Section 9.2 residual runbook visibility

---

### 16.4 Critical Mode UI (Stress Mode)

**Purpose**  
Reduce cognitive load during L3/L4 incidents by collapsing UI to only decisive controls.

**UI Location**  
Full-screen overlay mode switch + optional auto-entry on L4.

**Data Required**

- highest incident severity
- hard-stop usage and trend
- stale/unknown integrity flag
- top-3 recommended actions with confidence

**Visual Design**

- High-contrast, large typography, red/amber focus
- Single-column “What’s happening / What to do now / What is blocked”

**Operator Interaction**

- Manual toggle + auto-enter on terminal incidents
- One-step navigation to relevant panel

**Failure Behavior**

- If data confidence low, display “STATE UNCERTAIN — SAFE ACTIONS ONLY”

**Event Wiring**

- Listens: `mmmx_safety`, `mmmx_naked_position`, `mmmx_status_change`, `mmmx_circuit_breaker`, `mmmx_heartbeat`
- Delay/missing rule: fallback to static emergency command cards when stream quality degrades

**Failure Testing (expected UI behavior)**

| Scenario | Expected Behavior |
|---|---|
| API failure | Keep emergency-safe controls visible, hide non-executable actions |
| WebSocket disconnect | Enter degraded critical mode with explicit uncertainty banner |
| Partial data | Show known/unknown split; prevent optimistic inference |
| Stale state | Auto-focus to integrity + reconcile actions |

**Integration Points**

- Extends Section 6 escalation ladder
- Uses Section 7 confirmation tiers

---

### 16.5 Operator Error Prevention Layer

**Purpose**  
Prevent operator-induced losses from context drift, conflicting commands, and accidental activation.

**UI Location**  
Cross-cutting wrapper on every mutating action.

**Data Required**

- current session status
- command conflict matrix
- pending command states
- integrity confidence state

**Visual Design**

- Pre-flight checklist modal
- Hard blocks shown as explicit failed checks

**Operator Interaction**

- Required pre-flight acknowledgement for Tier B/C
- Explain why action is blocked and what clears the block

**Failure Behavior**

- Default deny on missing pre-flight data

**Event Wiring**

- Listens: `mmmx_status_change`, `mmmx_safety`, `mmmx_heartbeat`, `mmmx_deployment_queue`
- Reads pending command store and integrity monitor state
- **NOT DEFINED IN SPEC:** Centralized backend command-conflict metadata endpoint

**Failure Testing (expected UI behavior)**

| Scenario | Expected Behavior |
|---|---|
| API failure | Disable submit, preserve intent draft, show retry option |
| WebSocket disconnect | Block high-risk submits with “state not current” reason |
| Partial data | Deny action with exact missing prerequisites listed |
| Stale state | Require refresh + integrity check before action is enabled |

**Integration Points**

- Implements Section 7 confirmation policy at runtime
- Enforces Section 4.2 lock rules consistently

---

### 16.6 System Health Score Engine

**Purpose**  
Provide one composite health/confidence signal for operator trust calibration.

**UI Location**  
Top strip score + right pane decomposition panel.

**Data Required**

- websocket health (`get_ws_health`)
- heartbeat age and beat continuity
- circuit breaker state
- incident volume/severity
- reconcile divergence count
- residual partial count/age

**Visual Design**

- Score 0–100 + confidence badge (`HIGH/MEDIUM/LOW/UNKNOWN`)
- Decomposition bars by subsystem

**Operator Interaction**

- Click score to view root-cause contributors

**Failure Behavior**

- If confidence `LOW/UNKNOWN`, enforce conservative control locks

**Event Wiring**

- Listens: `mmmx_heartbeat`, `mmmx_safety`, `mmmx_circuit_breaker`, `mmmx_status_change`
- Pulls periodic `GET /health` for watchdog/ws health
- Delay/missing rule: downgrade confidence before downgrading score
- **NOT DEFINED IN SPEC:** canonical weighting formula and thresholds

**Failure Testing (expected UI behavior)**

| Scenario | Expected Behavior |
|---|---|
| API failure | Score enters degraded mode; confidence drops first |
| WebSocket disconnect | Health shows stream-failure contribution explicitly |
| Partial data | Subscores with missing data flagged, no fake aggregate precision |
| Stale state | Health status turns amber/red and blocks risky actions |

**Integration Points**

- Extends existing Status/Health carding
- Feeds Incident Auto-Focus priorities

---

### 16.7 Delta/Change Tracking Panel (Since Last Beat)

**Purpose**  
Show exactly what changed at each beat so operators can reason under time pressure.

**UI Location**  
Center pane near Trigger Engine; optional compact strip in right pane.

**Data Required**

- beat number
- previous/current key metrics (pnl, delta, reserves, queue, incidents)
- structural changes (tranche added/closed, hedge status transitions)

**Visual Design**

- Diff cards with `+/-` semantics and severity color
- Beat-to-beat timeline scrubber

**Operator Interaction**

- Select beat pair to compare
- Jump to causative incident/event

**Failure Behavior**

- On beat discontinuity, mark gap explicitly (`BEAT_GAP_DETECTED`)

**Event Wiring**

- Listens: `mmmx_heartbeat`, `mmmx_pnl_update`, `mmmx_tranche_deployed`, `mmmx_tranche_closed`, `mmmx_hedge_executed`, `mmmx_deployment_queue`
- Delay/missing rule: if prior beat snapshot missing, show partial diff with unknown fields

**Failure Testing (expected UI behavior)**

| Scenario | Expected Behavior |
|---|---|
| API failure | Preserve last known diff baseline, stop advancing beat comparisons |
| WebSocket disconnect | Pause diff stream and mark view stale |
| Partial data | Render partial diff, unknown markers on missing fields |
| Stale state | Auto-raise integrity incident and freeze action recommendations |

**Integration Points**

- Complements Section 10.2 live management flow step-2 reasoning
- Supports Section 11 explainability acceptance criteria

---

### 16.8 Action Recommendation Engine

**Purpose**  
Rank next safe actions with rationale, blockers, and confidence.

**UI Location**  
Control Deck top card + incident card inline suggestions.

**Data Required**

- trigger winner and risk context
- incident queue
- control lock state
- health confidence score

**Visual Design**

- Ranked stack: `REQUIRED`, `RECOMMENDED`, `OPTIONAL`, `BLOCKED`
- Each recommendation includes “why now” and “what if delayed”

**Operator Interaction**

- One-click “prepare action” (does not auto-execute)
- Dismiss with reason (audited)

**Failure Behavior**

- If confidence low: show `NO SAFE RECOMMENDATION` rather than weak advice

**Event Wiring**

- Listens: `mmmx_safety`, `mmmx_heartbeat`, `mmmx_status_change`, `mmmx_deployment_queue`, `mmmx_circuit_breaker`
- Uses trigger explanation output (Section 16.9)
- **NOT DEFINED IN SPEC:** backend recommendation service contract; if absent, run deterministic UI ruleset

**Failure Testing (expected UI behavior)**

| Scenario | Expected Behavior |
|---|---|
| API failure | Recommendations shift to safe-only/offline guidance |
| WebSocket disconnect | Confidence drops; recommendations become conservative |
| Partial data | Hide low-confidence recommendations, show data gaps |
| Stale state | Suspend recommendation execution shortcuts |

**Integration Points**

- Extends Section 10 workflow step-3
- Integrates with Section 7 confirmation tiers

---

### 16.9 Trigger Explanation Panel

**Purpose**  
Explain why the winning trigger fired and why higher/lower priority candidates did not.

**UI Location**  
Trigger Engine tab side panel (expandable ladder).

**Data Required**

- full trigger evaluation snapshot for current beat
- threshold/value pairs for each trigger
- short-circuit point in priority order

**Visual Design**

- Priority ladder with per-row verdict: `FIRED`, `BLOCKED`, `NOT_MET`, `SKIPPED_AFTER_WINNER`
- Inline math/value chips

**Operator Interaction**

- Click row to inspect condition values and source fields

**Failure Behavior**

- If snapshot unavailable, show explicit `NOT DEFINED IN SPEC` marker and disable confidence-dependent recommendations

**Event Wiring**

- Listens existing: `mmmx_heartbeat` (winner only metadata)
- Implemented evaluation payload event: `mmmx_trigger_evaluation` containing winner + ladder context
- Delay/missing rule: if no evaluation payload for beat, mark explanation incomplete

**Failure Testing (expected UI behavior)**

| Scenario | Expected Behavior |
|---|---|
| API failure | Keep last complete ladder marked read-only |
| WebSocket disconnect | Show stale explanation warning |
| Partial data | Show winner row only + missing rows tagged unknown |
| Stale state | Force recommendation engine to low-confidence mode |

**Integration Points**

- Extends existing Trigger Engine panel (Section 3.3)
- Feeds Action Recommendation Engine (Section 16.8)

---

### 16.10 Incident Auto-Focus System

**Purpose**  
Automatically bring operator attention to the highest-severity incident context.

**UI Location**  
Global routing/controller layer with focus ribbon.

**Data Required**

- active incidents + severity
- escalation ETA
- mapped destination panel per incident type

**Visual Design**

- Focus ribbon: “Auto-focused: <incident>” with countdown and acknowledge controls

**Operator Interaction**

- Auto-navigate to relevant panel on L3/L4
- Allow temporary snooze with reason (audited)

**Failure Behavior**

- If routing target unavailable, fallback to Incident Queue + Status tab and raise configuration incident

**Event Wiring**

- Listens: `mmmx_safety`, `mmmx_naked_position`, `mmmx_status_change`, `mmmx_circuit_breaker`
- Uses integrity and health confidence to decide force-focus vs advisory-focus
- **NOT DEFINED IN SPEC:** policy for override/snooze limits under L4

**Failure Testing (expected UI behavior)**

| Scenario | Expected Behavior |
|---|---|
| API failure | Keep current focus, show non-dismissible critical ribbon |
| WebSocket disconnect | Freeze auto-focus transitions; keep highest known critical visible |
| Partial data | Focus incident queue with unknown-state warning |
| Stale state | Auto-focus to integrity/reconcile workflow |

**Integration Points**

- Uses Section 6 severity model
- Enforces stress workflow from Section 10.3

---

## 17) Event-Wiring Completion Notes (Cross-Component)

### 17.1 Existing Events Confirmed in Code

- `mmmx_heartbeat`
- `mmmx_safety`
- `mmmx_status_change`
- `mmmx_session_created`
- `mmmx_session_stopped`
- `mmmx_tranche_deployed`
- `mmmx_tranche_closed`
- `mmmx_atm_shield`
- `mmmx_hedge_executed`
- `mmmx_pnl_update`
- `mmmx_params_changed`
- `mmmx_deployment_queue`
- `mmmx_whipsaw`  
- `mmmx_circuit_breaker`
- `mmmx_naked_position`

### 17.2 Contract Drift / Missing Event Contracts

1. **Resolved drift:** frontend now listens both `mmmx_whipsaw` and compatibility `mmmx_whipsaw_update`; contract normalization active.

2. **Implemented:** per-order lifecycle events (`intent/ack/partial/retry/fill/fail`) are now part of the active event contract.

3. **Implemented:** full trigger-evaluation payload event (`mmmx_trigger_evaluation`) is now emitted and consumed.

4. **Remaining open:** unified command-ack correlation event schema for deterministic command-state UI beyond kill-switch progress.

---

## 18) Integration Plan with Existing UI (Additive Only)

- **Status tab**: add Kill Switch, State Integrity, System Health Score summary widgets.
- **Execution Pipeline tab**: add Order Lifecycle Timeline + Change Tracking panel.
- **Trigger Engine tab**: add Trigger Explanation panel (ladder format).
- **Incident queue (left rail)**: add Incident Auto-Focus hooks + escalation ETA chips.
- **Global shell**: add Critical Mode toggle/auto-entry and Operator Error Prevention wrappers.
- **Recommendation layer**: mount at Control Deck top, consuming existing risk + incident streams.

No existing panel is removed. Existing semantics remain authoritative.

---

## 19) Safety Completion Gate (Must Pass Before Production Control-Layer Signoff)

WebUI control layer is not considered complete until all are true:

1. Every L3/L4 incident is auto-visible without tab hunting.
2. Every mutating action has deterministic pre-flight validation and command-state feedback.
3. Execution uncertainty is explicit (never silently interpreted as success).
4. UI/backend state drift is detected and control-locked automatically.
5. Trigger winner reasoning is explainable in full priority context.
6. Stress mode keeps only safe, high-value actions visible.
7. Health/confidence degradation is visible and action-lock integrated.

If any of the above fails, the control interface remains unsafe for real-capital operations.

---

## 20) Progress Marking — 2026-04-07 Implementation Update

Status legend:

- **✅ Completed** — implemented and wired in active UI/backend paths
- **🟡 Partial** — implemented baseline; advanced/optional pieces still open
- **⬜ Pending** — not yet implemented

### 20.1 Gap Matrix Status

| Gap ID | Status | Progress Notes | Primary Implementation Touchpoints |
|---|---|---|---|
| A1 | ✅ Completed | Session/global kill-switch now includes lifecycle telemetry (`accepted → session_result → completed`) with correlation IDs and command-strip progress visibility. | `webui/backend/routes/mmmx/mmmx_api.py`, `webui/backend/routes/mmmx/mmmx_websocket.py`, `webui/frontend/src/components/mmmx/MMMXContext.js`, `webui/frontend/src/components/mmmx/MMMXDashboard.js` |
| A2 | ✅ Completed | Deterministic pre-flight layer implemented via confirmation tiers + control safety gating. | `webui/frontend/src/components/mmmx/MMMXDashboard.js`, `webui/frontend/src/components/mmmx/mmmxControlSafety.js` |
| A3 | ✅ Completed | Conflicting/pending command firewall enforced at control-key scope with stale-context deny behavior. | `webui/frontend/src/components/mmmx/MMMXDashboard.js`, `webui/frontend/src/components/mmmx/mmmxControlSafety.js` |
| B1 | ✅ Completed | Integrity signature contract (`state_version`, `state_checksum`) is now emitted in snapshots + heartbeats; UI compares stream/snapshot and raises mismatch incidents with lock integration. | `webui/backend/routes/mmmx/mmmx_integrity.py`, `webui/backend/routes/mmmx/mmmx_api.py`, `webui/backend/routes/mmmx/mmmx_monitor.py`, `webui/frontend/src/components/mmmx/MMMXContext.js`, `webui/frontend/src/components/mmmx/MMMXDashboard.js` |
| B2 | ✅ Completed | Divergence/reconcile visibility promoted to incident queue + top strip, no longer tab-isolated. | `webui/frontend/src/components/mmmx/MMMXDashboard.js` |
| B3 | ✅ Completed | Confidence + integrity state directly influence B/C control locks. | `webui/frontend/src/components/mmmx/MMMXDashboard.js`, `webui/frontend/src/components/mmmx/mmmxControlSafety.js` |
| B4 | ✅ Completed | Whipsaw event drift normalized by listening to both modern + legacy event names. | `webui/frontend/src/components/mmmx/MMMXContext.js` |
| C1 | ✅ Completed | Execution lifecycle timeline active with filters and stage chips. | `webui/frontend/src/components/mmmx/MMMXDashboard.js`, `webui/frontend/src/components/mmmx/MMMXContext.js`, `webui/backend/routes/mmmx/mmmx_websocket.py` |
| C2 | ✅ Completed | Residual aging surfaced as first-class incident type with escalation. | `webui/frontend/src/components/mmmx/MMMXDashboard.js` |
| C3 | ✅ Completed | Explicit execution-uncertain state implemented in incident engine + execution lane chips. | `webui/frontend/src/components/mmmx/MMMXDashboard.js` |
| D1 | ✅ Completed | Deterministic recommendation engine (required/recommended/optional) mounted in Status deck. | `webui/frontend/src/components/mmmx/MMMXDashboard.js` |
| D2 | ✅ Completed | Trigger explanation ladder now carries threshold/value/excluded_by/would_status metadata end-to-end and is rendered directly in the Trigger Engine panel. | `webui/backend/routes/mmmx/mmmx_trigger.py`, `webui/backend/routes/mmmx/tests/test_phase10.py`, `webui/frontend/src/components/mmmx/MMMXDashboard.js` |
| D3 | ✅ Completed | Beat-to-beat delta/change tracking panel implemented in Execution tab. | `webui/frontend/src/components/mmmx/MMMXDashboard.js` |
| E1 | ✅ Completed | Critical mode now switches into a dedicated emergency interaction layout with top-incident focus and constrained high-safety action set. | `webui/frontend/src/components/mmmx/MMMXDashboard.js` |
| E2 | ✅ Completed | Incident auto-focus routes operators to the highest-severity destination tab. | `webui/frontend/src/components/mmmx/MMMXDashboard.js` |
| E3 | ✅ Completed | Time-pressure indicators now include escalation ETA chips in incident queue + critical panel and live kill-switch progress timing context. | `webui/frontend/src/components/mmmx/MMMXDashboard.js` |
| F1 | ✅ Completed | Composite health score + confidence model implemented and displayed in persistent top strip. | `webui/frontend/src/components/mmmx/MMMXDashboard.js` |
| F2 | ✅ Completed | Degradation state machine (`NORMAL/DEGRADED/CRITICAL/UNKNOWN`) is active and integrated with control lock policy. | `webui/frontend/src/components/mmmx/MMMXDashboard.js`, `webui/frontend/src/components/mmmx/mmmxControlSafety.js` |

### 20.2 Safety Completion Gate Re-check (Section 19)

- 1) L3/L4 visibility without tab hunting — **✅ via incident queue + top strip + auto-focus**
- 2) Deterministic pre-flight + command-state feedback — **✅ baseline complete**
- 3) Execution uncertainty explicit — **✅ complete**
- 4) Drift detection + auto-lock — **✅ baseline complete (checksum-grade diff still optional)**
- 5) Full trigger reasoning context — **✅ complete (winner + ladder + exclusion metadata)**
- 6) Stress mode safe-action layout — **✅ complete (dedicated critical emergency panel + constrained action set)**
- 7) Health/confidence degradation lock integration — **✅ complete**

Overall control-layer readiness after this update: **Section 20 completion target reached for this scope; remaining items are optional UX polish, not safety-gate blockers.**