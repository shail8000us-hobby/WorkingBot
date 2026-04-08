# MMMX WebUI — Executable Phase-Wise Implementation Plan

**Date:** 2026-04-07  
**Input Authority:**
1. `MMMX_COMPLETE.md`
2. `MMMX_IMPLEMENTATION_PLAN.md`
3. `mmmx_webUI.md` (Sections 1–19)

**Planning Mode:** Conversion-only. No redesign. No requirement removal.  
**Rule:** If a needed contract is absent, it is flagged exactly as `NOT DEFINED IN SPEC`.

---

## 0) Full Parsing Output (Requirement Inventory)

This is the complete extracted implementation inventory from `mmmx_webUI.md`.

### 0.1 Panels / UI Surfaces (must exist)

1. Persistent Top Command Strip
2. Left Rail: Session List + Incident Queue
3. Center Pane Tabs:
   - Status & Control Deck
   - Tranches
   - Trigger Engine
   - Execution Pipeline
   - Profit Booking
   - Reconcile Workbench
4. Right Risk Stack:
   - Hard stop status
   - Delta + lot imbalance
   - ATM shield tracker
   - CE/PE reserve burn-down
   - Hedge book
   - Margin guardian
   - Whipsaw status
5. Hot-Reload Governance Panel (domain grouped)
6. Critical Mode UI (stress mode)

### 0.2 Mandatory Components (Section 16, must be fully implemented)

1. Global Kill Switch System
2. State Integrity Monitor
3. Order Lifecycle Timeline
4. Critical Mode UI
5. Operator Error Prevention Layer
6. System Health Score Engine
7. Delta/Change Tracking Panel
8. Action Recommendation Engine
9. Trigger Explanation Panel
10. Incident Auto-Focus System

### 0.3 Controls (must be safety-gated)

- Create Session
- Check Gates
- Deploy Tranche 1
- Pause
- Resume
- Stop
- Reconcile
- Confirm Reconcile action (`accept_db`, `accept_exchange`, `manual_close`)
- Profit Book (queue close)
- Hot Reload Apply Changes
- Force Heartbeat (specified in UI spec as quick control)
- Kill Switch (session/global)
- Incident Acknowledge
- Incident Snooze (policy-governed)
- Integrity Check Now
- Critical Mode toggle

### 0.4 Invariants (must remain enforceable in UI)

- Hard stop non-overridable while RUNNING.
- Trigger priority authoritative.
- Restart lands PAUSED and requires reconcile before resume.
- Listener-protection visibility remains live in PAUSED.
- Recovery tranches are first-class.
- CE/PE reserve accounting independent.
- Partial-fill residuals explicit until cleared.
- Orphan/displaced hedges explicit.

### 0.5 Event Dependencies (from spec + implementation)

Required domains:
- Lifecycle
- Risk
- Protection
- Execution
- Reconcile
- Config

Observed implemented backend websocket events:
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

---

## 1) Complete Phase-Wise Implementation Plan

All phases are intentionally micro-scoped, independently testable, and do not depend on future phases.

---

### Phase 0 — Contract Baseline Freeze

**Objective**  
Create a strict source-of-truth contract map for controls, events, payload fields, and UI state gates.

**Components to Build**
- Contract registry (events, payload keys, control IDs)
- Validation harness for event payload shape
- UI state gate enum definitions (`SYNCED/DRIFT/STALE/UNKNOWN`, severity levels, control lock reasons)

**Data Contracts Required**
- Existing event payloads from backend emitters
- Existing REST response payloads from `mmmx_api.py`

**WebSocket Events Used**
- All currently emitted events (enumerated in section 0.5)

**UI States Covered**
- Connected
- Disconnected
- Unknown contract
- Degraded contract

**Failure States Covered**
- API failure: contract checks move to websocket-only mode
- WebSocket disconnect: contract checks move to API-only mode
- Partial data: field-level contract violation reports
- Stale state: mark `UNKNOWN`, lock Tier B/C actions

**Exit Criteria (STRICT)**
- Contract registry generated for every current control/event.
- Every event has required/optional field list.
- All mismatches are categorized as `EVENT MISSING`, `EVENT MISMATCH`, or `EVENT INSUFFICIENT`.
- No UI feature build begins without this registry.

---

### Phase 1 — Terminal Shell + Session Surfaces

**Objective**  
Implement structural shell from spec Section 3 without advanced decision logic.

**Components to Build**
- Persistent Top Command Strip (baseline fields)
- Left Session Rail (All/Active/Draft/Done)
- Session card controls scaffold
- Center tab container (Status/Tranches/Trigger/Execution/Profit/Reconcile)
- Right risk stack container (widget placeholders + loaded baseline data)

**Data Contracts Required**
- Session list summary
- Session detail payload
- Health snapshot (`/api/mmmx/health`)

**WebSocket Events Used**
- `mmmx_status_change`
- `mmmx_heartbeat`
- `mmmx_session_created`
- `mmmx_session_stopped`

**UI States Covered**
- No session selected
- DRAFT/GATES_PASSED/RUNNING/PAUSED/COMPLETE/ERROR

**Failure States Covered**
- API failure: show cached list + explicit stale banner
- WebSocket disconnect: shell stays usable, status marked stale
- Partial data: placeholders with explicit unknown markers
- Stale state: command strip confidence downgraded

**Exit Criteria (STRICT)**
- Shell and tab routing match Section 3 exactly.
- Session/status view works for all lifecycle states.
- No hidden critical data fields in baseline strip.

---

### Phase 2 — Operator Error Prevention Layer + Control Safety Base

**Objective**  
Implement control interlocks, confirmation tiers, and command-state discipline.

**Components to Build**
- Operator Error Prevention Layer (global action wrapper)
- Tier A/B/C confirmation flows
- Command submission state machine (submitted/accepted/completed/failed)
- Control lock reason panel

**Data Contracts Required**
- Command result payload model
- Control lock reason model

**WebSocket Events Used**
- `mmmx_status_change`
- `mmmx_safety`
- `mmmx_heartbeat`

**UI States Covered**
- Control enabled
- Control disabled
- Pending command
- Blocked by lock

**Failure States Covered**
- API failure: pending transitions to retry-required
- WebSocket disconnect: Tier B/C blocked by stale-context rule
- Partial data: default deny for Tier B/C
- Stale state: explicit lock + reconcile hint

**Exit Criteria (STRICT)**
- Every control has deterministic enable/disable rule.
- Every Tier B/C action has required confirmation.
- Duplicate submissions are blocked by command scope.

---

### Phase 3 — Global Kill Switch System

**Objective**  
Implement session/global risk-off controls with deterministic progress visibility.

**Components to Build**
- Kill Switch control (`SAFE→ARMED→EXECUTING`)
- Kill progress rail
- Kill command lockout on offensive controls

**Data Contracts Required**
- Kill command ack payload
- Kill progress event payloads

**WebSocket Events Used**
- `mmmx_safety`
- `mmmx_status_change`
- `mmmx_tranche_closed`
- `mmmx_heartbeat`
- `mmmx_pnl_update`

**UI States Covered**
- Idle
- Armed
- Executing
- Degraded execution
- Execution uncertain

**Failure States Covered**
- API failure: `KILL_DEGRADED` + retry sequence
- WebSocket disconnect: freeze progress + reconcile-required lock
- Partial data: unknown progress nodes explicit
- Stale state: escalate to L4 incident banner

**Exit Criteria (STRICT)**
- Kill actions cannot be triggered accidentally.
- Progress cannot appear complete without completion evidence.
- Risk-on controls stay locked until terminal certainty.

**Dependency Validation**
- Dependency: kill command/event contract.  
- Status: `BLOCKED` until command ack/progress schema is defined.  
- Marker: `NOT DEFINED IN SPEC`.

---

### Phase 4 — Incident Framework (Severity + Queue + Escalation Timers)

**Objective**  
Operationalize Section 6 incident model with queue, acknowledgment, and escalation timing.

**Components to Build**
- Incident Queue in left rail
- Severity badges L0–L4
- Incident card with escalation ETA
- Acknowledge action + audit write-through

**Data Contracts Required**
- Incident model (`id/type/severity/detected_at/escalation_at/blocking/recommendation/ack`)

**WebSocket Events Used**
- `mmmx_safety`
- `mmmx_naked_position`
- `mmmx_circuit_breaker`
- `mmmx_status_change`

**UI States Covered**
- No incidents
- Active incidents
- Acked incidents
- Escalated incidents

**Failure States Covered**
- API failure: allow local ack staging, mark unsynced
- WebSocket disconnect: queue frozen + stale warning
- Partial data: incomplete cards with unknown fields
- Stale state: auto-raise integrity incident

**Exit Criteria (STRICT)**
- All Section 6.3 incident types render as first-class cards.
- Escalation timer displayed per active incident.
- Blocking impact visible for each incident.

---

### Phase 5 — Reconcile Workbench + Resume Gate

**Objective**  
Finalize restart/reconcile operator flow and enforce resume gating.

**Components to Build**
- Reconcile report display and per-divergence actions
- Reconcile-required gate badge in command strip
- Resume blocker when divergence unresolved

**Data Contracts Required**
- Reconcile report payload
- Confirm reconcile action payload

**WebSocket Events Used**
- `mmmx_status_change`
- `mmmx_safety` (supporting)

**UI States Covered**
- Clean reconcile
- Divergence pending
- Divergence resolved

**Failure States Covered**
- API failure: report unavailable state + no resume unlock
- WebSocket disconnect: gating remains API-authoritative
- Partial data: unresolved divergence treated as blocking
- Stale state: enforce no-resume policy

**Exit Criteria (STRICT)**
- Resume unavailable while reconcile-required is true.
- Every divergence has explicit operator disposition.
- Reconcile actions are auditable.

---

### Phase 6 — Hot-Reload Governance Panel

**Objective**  
Implement Section 8 grouped hot-reload with applied/rejected visibility and risk impact.

**Components to Build**
- Domain-grouped parameter editor
- Change diff preview (`old→new`)
- Applied/rejected response display
- Audit reference display

**Data Contracts Required**
- Params schema + allowlist
- Hot reload response (`applied/rejected/audit_id`)

**WebSocket Events Used**
- `mmmx_params_changed`
- `mmmx_status_change`

**UI States Covered**
- No edits
- Pending edits
- Applied
- Partially rejected
- Fully rejected

**Failure States Covered**
- API failure: retain pending edit set and mark unsent
- WebSocket disconnect: changes still REST-confirmed
- Partial data: rejected reasons mandatory per key
- Stale state: block apply when integrity is unknown

**Exit Criteria (STRICT)**
- Parameter grouping matches Section 8 domains exactly.
- Applied vs rejected keys shown clearly.
- Audit reference visible for successful updates.

---

### Phase 7 — Execution Pipeline + Order Lifecycle Timeline

**Objective**  
Implement full execution visibility including residual aging and uncertain state.

**Components to Build**
- Execution Pipeline tab implementation
- Order Lifecycle Timeline lanes
- Residual aging chips and retry visibility
- Execution-uncertain incident integration

**Data Contracts Required**
- Order lifecycle event schema
- Residual model with retry attempt metadata

**WebSocket Events Used**
- Existing fallback: `mmmx_tranche_deployed`, `mmmx_tranche_closed`, `mmmx_safety`
- Required granular stream: order intent/ack/partial/retry/fill/fail

**UI States Covered**
- Pending
- Partial
- Retrying
- Filled
- Failed
- Uncertain

**Failure States Covered**
- API failure: retry/failed path visible
- WebSocket disconnect: timeline freezes with stale banner
- Partial data: unknown nodes shown explicitly
- Stale state: affected orders marked uncertain

**Exit Criteria (STRICT)**
- No order can appear complete without completion evidence.
- Residuals include age and retry history.
- Uncertain lifecycle states generate incidents.

**Dependency Validation**
- Dependency: granular order lifecycle events.  
- Status: `BLOCKED`.  
- Marker: `EVENT MISSING` + `NOT DEFINED IN SPEC` (event contract not defined).

---

### Phase 8 — Trigger Engine + Trigger Explanation Panel

**Objective**  
Show full trigger priority ladder with winner and non-winner rationale.

**Components to Build**
- Trigger Engine detail panel
- Trigger Explanation ladder (`FIRED/BLOCKED/NOT_MET/SKIPPED_AFTER_WINNER`)

**Data Contracts Required**
- Trigger evaluation snapshot payload (all rows + thresholds + values)

**WebSocket Events Used**
- `mmmx_heartbeat` (winner baseline)
- Required: trigger evaluation payload event

**UI States Covered**
- Complete explanation
- Partial explanation
- Explanation unavailable

**Failure States Covered**
- API failure: last complete explanation read-only
- WebSocket disconnect: stale explanation warning
- Partial data: winner-only with unknown rows
- Stale state: recommendation engine confidence downgrade

**Exit Criteria (STRICT)**
- Trigger winner always explainable in priority context.
- Non-winning rows clearly marked with reason.

**Dependency Validation**
- Dependency: full trigger evaluation payload.  
- Status: `BLOCKED`.  
- Marker: `EVENT MISSING` (`mmmx_trigger_evaluation` not defined).

---

### Phase 9 — Delta/Change Tracking Panel

**Objective**  
Provide beat-to-beat change visibility for operator decision support.

**Components to Build**
- Change-since-last-beat panel
- Beat comparison timeline scrubber
- Structural change list (tranche/hedge/reserve/incidents)

**Data Contracts Required**
- Beat snapshot persistence model (current + prior)

**WebSocket Events Used**
- `mmmx_heartbeat`
- `mmmx_pnl_update`
- `mmmx_tranche_deployed`
- `mmmx_tranche_closed`
- `mmmx_hedge_executed`
- `mmmx_deployment_queue`

**UI States Covered**
- Normal beat progression
- Beat gap detected
- Partial diff

**Failure States Covered**
- API failure: freeze baseline
- WebSocket disconnect: paused diff stream
- Partial data: unknown fields explicit
- Stale state: raise integrity incident

**Exit Criteria (STRICT)**
- Operator can inspect exact changes between any two recent beats.
- Beat discontinuities are explicit and never hidden.

---

### Phase 10 — State Integrity Monitor

**Objective**  
Detect and expose UI/backend drift and stale confidence, with lock integration.

**Components to Build**
- Integrity badge (`SYNCED/DRIFT/STALE/UNKNOWN`)
- Integrity detail drawer with mismatch fields
- Integrity-triggered control lock integration

**Data Contracts Required**
- Snapshot consistency payload (`version/checksum/sequence`) or equivalent

**WebSocket Events Used**
- `mmmx_heartbeat`
- `mmmx_status_change`
- `mmmx_params_changed`
- `mmmx_deployment_queue`
- `mmmx_safety`

**UI States Covered**
- Synced
- Drift
- Stale
- Unknown

**Failure States Covered**
- API failure: integrity unknown
- WebSocket disconnect: stale transition timer
- Partial data: mismatch at field granularity
- Stale state: enforce reconcile-required lock

**Exit Criteria (STRICT)**
- Drift detection visible within configured SLA.
- Tier B/C controls auto-lock on `DRIFT/UNKNOWN`.

**Dependency Validation**
- Dependency: snapshot checksum/version contract.  
- Status: `BLOCKED`.  
- Marker: `EVENT/CONTRACT INSUFFICIENT` + `NOT DEFINED IN SPEC`.

---

### Phase 11 — System Health Score Engine

**Objective**  
Implement composite health + confidence scoring and degradation state machine.

**Components to Build**
- Health score widget (0–100)
- Confidence badge (`HIGH/MEDIUM/LOW/UNKNOWN`)
- Subsystem decomposition panel
- Degradation state machine (`NORMAL/DEGRADED/CRITICAL/UNKNOWN`)

**Data Contracts Required**
- Health inputs from `/api/mmmx/health`
- Incident severity distribution
- Queue depth/residual aging

**WebSocket Events Used**
- `mmmx_heartbeat`
- `mmmx_safety`
- `mmmx_circuit_breaker`
- `mmmx_status_change`

**UI States Covered**
- Normal
- Degraded
- Critical
- Unknown

**Failure States Covered**
- API failure: confidence drops before score
- WebSocket disconnect: stream-quality penalty
- Partial data: unknown subscore
- Stale state: high-risk control lock

**Exit Criteria (STRICT)**
- Health confidence directly affects control gating.
- Degradation transitions are deterministic and visible.

**Dependency Validation**
- Dependency: canonical weighting thresholds.  
- Status: `BLOCKED FOR FINALIZATION` (prototype possible, production lock blocked).  
- Marker: `NOT DEFINED IN SPEC`.

---

### Phase 12 — Action Recommendation Engine

**Objective**  
Provide ranked, confidence-scored, safety-aware recommendations.

**Components to Build**
- Recommendation stack (`REQUIRED/RECOMMENDED/OPTIONAL/BLOCKED`)
- Rationale + delayed-impact explanation
- Dismiss with reason (audited)

**Data Contracts Required**
- Trigger explanation output
- Incident queue state
- Health confidence state
- Control lock state

**WebSocket Events Used**
- `mmmx_safety`
- `mmmx_heartbeat`
- `mmmx_status_change`
- `mmmx_deployment_queue`
- `mmmx_circuit_breaker`

**UI States Covered**
- Normal recommendations
- Safe-only recommendations
- No safe recommendation

**Failure States Covered**
- API failure: offline-safe recommendations only
- WebSocket disconnect: confidence downgrade
- Partial data: hide low-confidence recs
- Stale state: recommendation shortcuts disabled

**Exit Criteria (STRICT)**
- Every recommendation has explicit rationale and confidence.
- No recommendation can bypass control safety tiers.

**Dependency Validation**
- Dependency: trigger explanation + integrity + health completed.  
- Status: `BLOCKED` until Phases 8/10/11 are production-ready.

---

### Phase 13 — Critical Mode UI + Incident Auto-Focus System

**Objective**  
Implement stress-mode and automatic operator focus routing for L3/L4 incidents.

**Components to Build**
- Critical Mode overlay
- Incident Auto-Focus controller
- Focus ribbon with acknowledge/snooze controls

**Data Contracts Required**
- Incident-to-panel routing map
- Auto-focus policy controls

**WebSocket Events Used**
- `mmmx_safety`
- `mmmx_naked_position`
- `mmmx_status_change`
- `mmmx_circuit_breaker`
- `mmmx_heartbeat`

**UI States Covered**
- Normal mode
- Manual critical mode
- Auto-critical mode
- Advisory focus
- Forced focus

**Failure States Covered**
- API failure: non-dismissible critical ribbon
- WebSocket disconnect: freeze focus transitions
- Partial data: fallback to incident queue focus
- Stale state: auto-focus integrity/reconcile path

**Exit Criteria (STRICT)**
- L3/L4 incidents auto-surface without tab hunting.
- Focus behavior is deterministic and auditable.

**Dependency Validation**
- Dependency: snooze/override policy under L4.  
- Status: `BLOCKED FOR POLICY FINALIZATION`.  
- Marker: `NOT DEFINED IN SPEC`.

---

### Phase 14 — Final Hardening + Acceptance Completion

**Objective**  
Execute full safety completion gate (Section 19) and UAT closure.

**Components to Build**
- End-to-end validation suite
- Contract drift monitors
- Production readiness report

**Data Contracts Required**
- All prior phase contracts finalized

**WebSocket Events Used**
- Full event set

**UI States Covered**
- All lifecycle and degraded states

**Failure States Covered**
- API failure, WS disconnect, partial data, stale state across all controls

**Exit Criteria (STRICT)**
- Section 19 safety completion gate fully passed.
- No unresolved `EVENT MISSING/MISMATCH/INSUFFICIENT` in critical paths.
- No Tier B/C control with ambiguous command outcome.

---

## 2) Cross-Phase Wiring (N → N+1)

| From | To | What Connects | Must Persist | Required Existing Events |
|---|---|---|---|---|
| P0 | P1 | Contract registry into UI shell adapters | event/field map, state enums | all baseline events |
| P1 | P2 | Control surfaces into safety wrappers | control IDs + lock contexts | `mmmx_status_change`, `mmmx_heartbeat` |
| P2 | P3 | Safety engine into kill workflow | command states, lock reasons | `mmmx_safety`, `mmmx_tranche_closed` |
| P3 | P4 | Incident model into queue/escalation | incident IDs, ack status | `mmmx_safety`, `mmmx_naked_position` |
| P4 | P5 | Reconcile-required incidents into resume gate | divergence state | reconcile API responses |
| P5 | P6 | Domain controls into parameter governance | edit diffs, audit refs | `mmmx_params_changed` |
| P6 | P7 | Command/event certainty into execution timeline | order correlation context | execution events |
| P7 | P8 | Execution context into trigger explanation | beat-index mapping | trigger evaluation payload |
| P8 | P9 | Beat snapshots into diff panel | prior/current beat snapshots | `mmmx_heartbeat` + change events |
| P9 | P10 | Diff+sequence signals into integrity monitor | sequence markers | heartbeat + snapshot contract |
| P10 | P11 | Integrity confidence into health engine | confidence state | health + incident + stream stats |
| P11 | P12 | Health confidence + trigger rationale into recommendations | recommendation history | safety/risk events |
| P12 | P13 | Priority recommendations + incidents into critical mode | focus policy state | incident + safety events |
| P13 | P14 | All systems into final acceptance harness | all persisted stores | full event set |

---

## 3) Dependency Graph (Phase-Level)

```text
P0
 └─> P1
      └─> P2
           └─> P3
                └─> P4
                     ├─> P5
                     └─> P6
                           └─> P7 (BLOCKED: execution events)
                                └─> P8 (BLOCKED: trigger evaluation payload)
                                     └─> P9
                                          └─> P10 (BLOCKED: checksum/version contract)
                                               └─> P11 (BLOCKED: health weighting policy)
                                                    └─> P12
                                                         └─> P13 (BLOCKED: L4 snooze policy)
                                                              └─> P14
```

---

## 4) Phase Dependency Validation (Blocked/Ready)

| Phase | Dependencies | Status |
|---|---|---|
| P0 | Access to current frontend/backend contracts | READY |
| P1 | P0 complete | READY |
| P2 | P1 complete | READY |
| P3 | P2 complete + kill command contract | BLOCKED (`NOT DEFINED IN SPEC`) |
| P4 | P2 complete + safety events | READY |
| P5 | P4 complete + reconcile APIs | READY |
| P6 | P2 complete + params APIs | READY |
| P7 | P2 + order lifecycle event stream | BLOCKED (`EVENT MISSING`) |
| P8 | P1 + trigger evaluation payload | BLOCKED (`EVENT MISSING`) |
| P9 | P1 + baseline event stream | READY (partial mode) |
| P10 | P1 + snapshot checksum/version | BLOCKED (`EVENT INSUFFICIENT`) |
| P11 | P10 + scoring weights/thresholds | BLOCKED FOR FINAL POLICY (`NOT DEFINED IN SPEC`) |
| P12 | P8 + P10 + P11 | BLOCKED UNTIL UPSTREAM CLEARS |
| P13 | P4 + focus override policy | BLOCKED FOR POLICY (`NOT DEFINED IN SPEC`) |
| P14 | All critical blocks resolved | BLOCKED UNTIL RESOLUTION |

---

## 5) Control Safety Validation Matrix (Per Control)

| Control | Enabled When | Disabled When | Blocks | Confirmation |
|---|---|---|---|---|
| Create Session | Shell loaded, API reachable | API unavailable hard fail | none | Tier A |
| Check Gates | Session=DRAFT | non-DRAFT | missing expiry input | Tier B |
| Deploy Tranche 1 | Session in DRAFT/GATES_PASSED/RUNNING and no tranche1 deployed | reconcile-required, integrity UNKNOWN, pending conflicting command | active L3/L4 protection incident | Tier B |
| Pause | Session=RUNNING | COMPLETE/ERROR/DRAFT | pending stop/kill | Tier B |
| Resume | Session=PAUSED and reconcile-clear | reconcile-required, integrity DRIFT/UNKNOWN | unresolved divergence | Tier B |
| Stop | Session in RUNNING/PAUSED/GATES_PASSED | COMPLETE/ERROR/DRAFT | kill in progress | Tier C |
| Reconcile | Session exists | command conflict lock | none | Tier B |
| Confirm Reconcile Action | divergence selected | no divergence | stale reconcile report | Tier C |
| Profit Book | Session=RUNNING + tranche ACTIVE | non-running or no active tranche | conflicting close command | Tier B |
| Hot Reload Apply | editable params present + integrity not UNKNOWN | no changes / integrity UNKNOWN | unresolved L4 incident | Tier B |
| Force Heartbeat | Session RUNNING/PAUSED | no session / command conflict | API unavailable | Tier B |
| Session Kill Switch | Session active + command channel healthy | COMPLETE/ERROR | kill already executing | Tier C |
| Global Kill Switch | Operator scope allows + global context healthy | no authorization / command channel unknown | unresolved identity policy | Tier C |
| Incident Acknowledge | incident active | incident resolved | none | Tier A |
| Incident Snooze | incident active + snooze policy allows | L4 non-snoozable | policy violation | Tier B |
| Integrity Check Now | session selected | none | none | Tier A |
| Critical Mode Toggle | any active session | none | none | Tier A |

**Note:** Role/authorization gates are `NOT DEFINED IN SPEC` and must be policy-defined before production.

---

## 6) Event Contract Validation Report

### 6.1 Existing Event → Consumer Validation

| Event | Backend Emitter | Frontend Consumer | Result | Issue Type |
|---|---|---|---|---|
| `mmmx_heartbeat` | yes | yes | FAIL (payload mismatch on `beat_at`) | EVENT INSUFFICIENT |
| `mmmx_pnl_update` | yes | yes | PASS (partial consumption) | — |
| `mmmx_tranche_deployed` | yes | yes | FAIL (`tranches` array expected by consumer) | EVENT INSUFFICIENT |
| `mmmx_tranche_closed` | yes | yes | FAIL (`tranches` array expected by consumer) | EVENT INSUFFICIENT |
| `mmmx_hedge_executed` | yes | yes | FAIL (`hedges` array expected by consumer) | EVENT INSUFFICIENT |
| `mmmx_whipsaw` | yes | no (`mmmx_whipsaw_update` subscribed) | FAIL | EVENT MISMATCH |
| `mmmx_circuit_breaker` | yes (`old_state/new_state`) | yes (`state` expected) | FAIL | EVENT INSUFFICIENT |
| `mmmx_atm_shield` | yes | yes | PARTIAL (payload detail level not standardized) | EVENT INSUFFICIENT |
| `mmmx_params_changed` | yes | yes | PASS | — |
| `mmmx_status_change` | yes | yes | PASS | — |
| `mmmx_deployment_queue` | yes | yes | PASS (assumes `queue` key) | — |
| `mmmx_safety` | yes | yes | PASS | — |
| `mmmx_naked_position` | yes | no | FAIL | EVENT MISSING (consumer) |
| `mmmx_session_created` | yes | no | FAIL | EVENT MISSING (consumer) |
| `mmmx_session_stopped` | yes | no | FAIL | EVENT MISSING (consumer) |

### 6.2 Required by Spec but Not Implemented

| Required Contract | Status |
|---|---|
| `mmmx_order_intent` | EVENT MISSING |
| `mmmx_order_ack` | EVENT MISSING |
| `mmmx_order_partial` | EVENT MISSING |
| `mmmx_order_retry` | EVENT MISSING |
| `mmmx_order_filled` | EVENT MISSING |
| `mmmx_order_failed` | EVENT MISSING |
| `mmmx_trigger_evaluation` (full ladder payload) | EVENT MISSING |
| Command correlation ack schema (`command_id` + terminal state) | EVENT MISSING |
| Snapshot checksum/version/sequence contract | EVENT INSUFFICIENT |

---

## 7) Missing Backend Requirements (Implementation-Blocking)

1. **Force heartbeat endpoint contract** for quick-control parity (`EVENT/API MISSING` for complete control path).
2. **Kill switch command endpoints and websocket progress events** (`NOT DEFINED IN SPEC`).
3. **Granular order lifecycle event stream** (intent/ack/partial/retry/fill/fail).
4. **Trigger evaluation payload event** (all trigger rows + thresholds + values).
5. **Command correlation contract** (`command_id`, accepted/rejected, completed/failed).
6. **Snapshot consistency contract** (`checksum/version/sequence`) for integrity monitor.
7. **Incident acknowledge/snooze backend audit contract** (`NOT DEFINED IN SPEC`).
8. **Role/permission contract** for dangerous controls (`NOT DEFINED IN SPEC`).
9. **Health score policy constants** (weights/thresholds) (`NOT DEFINED IN SPEC`).
10. **L4 snooze/override policy** for Incident Auto-Focus (`NOT DEFINED IN SPEC`).

---

## 8) Risk Points During Implementation

1. **Silent event failure risk:** backend emitters are wrapped with broad exception catches in places; UI may falsely appear healthy.
2. **Contract drift risk:** event names/payloads already diverge (`whipsaw`, `circuit_breaker`, tranche/hedge payloads).
3. **Ambiguous command outcome risk:** without command correlation, operator may repeat destructive actions.
4. **False-safe UI risk:** missing beat/event fields can render stale data as current.
5. **Control race risk:** pause/resume/stop/kill collisions without global command scope lock.
6. **Reconcile gating bypass risk:** if lock logic is split across components.
7. **Stress-mode overload risk:** if critical mode enters without deterministic focus routing.
8. **Recommendation misuse risk:** low-confidence suggestions presented as actionable.
9. **Integrity blind spot risk:** without checksum/version sequencing, drift detection becomes heuristic only.
10. **Capital-loss path risk:** if kill switch progress cannot prove closure certainty under API/WS degradation.

---

## 9) Implementation Start Order (Executable)

1. Execute P0–P2 first (contracts, shell, control safety).
2. Resolve blocked contracts for P3/P7/P8/P10 before coding those phases.
3. Execute P4–P6 in parallel where dependencies permit.
4. Unlock P11–P13 only after contract blockers are closed.
5. Run P14 acceptance only with zero unresolved critical contract blockers.

---

## 10) Final Safety Condition

This implementation plan is executable only if every `BLOCKED` dependency above is explicitly resolved or formally accepted by operator policy as `NOT DEFINED IN SPEC` with documented temporary mitigation.

If unresolved blockers remain in control, execution, or integrity paths, production go-live must be denied.