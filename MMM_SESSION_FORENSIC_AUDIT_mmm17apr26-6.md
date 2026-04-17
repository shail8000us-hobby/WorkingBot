# MMM Session Forensic Audit Report

**Session audited:** `mmm17apr26-6`  
**Strategy:** `STRADDLE_WITH_ADJUSTMENT`  
**Status at end:** `STOPPED`  
**Evidence cut date:** 2026-04-17

---

## 1. Executive Summary

Session `mmm17apr26-6` is a **micro-duration monitor/stop session** with **no executed trades** and multiple control-plane inconsistencies.

- **Session window:** 2026-04-17T03:16:09.697305+00:00 → 2026-04-17T03:17:30.477960+00:00 (`80.78s`, `1.3 min`)
- **Order lifecycle:** `0 intents`, `0 confirms`, `0 audits`
- **Final total P&L:** `+3.411067` (unrealized)
- **Final realized P&L:** `0.000000`
- **Final unrealized P&L:** `+3.411067`
- **Fees from fill ledger:** `0.000000`
- **Terminal regime:** `_regime_action=FORCE_REDUCE`, `_gamma_regime=EMERGENCY`
- **Portfolio dollar gamma:** `13875.33`

### High-confidence headline findings

1. **No trading occurred**, yet session entered emergency-risk posture immediately and then stopped. **[Confidence: High]**
2. **State integrity mismatch** exists between walkthrough ENTRY narrative and terminal inventory state. **[Confidence: High]**
3. **Validation error was present in-state** (`CE strike 75000 != PE strike 74400`) while session still proceeded. **[Confidence: High]**
4. **Performance semantics conflict with state** (`exit_quality=CLEAN`, `exit_pct_closed=100` but open lots still `CE 323 / PE 142`). **[Confidence: High]**

---

## 2. Chronological Timeline

| # | Time (UTC) | Event | Evidence | Impact |
|---:|---|---|---|---|
| 1 | 03:16:15.995 | Regime transition | `NORMAL → FORCE_REDUCE`, gamma `EMERGENCY` | Immediate stress posture |
| 2 | 03:16:48.463 | Hot reload | `max_lots_per_side 5 → 500` | Hard cap widened during emergency window |
| 3 | 03:17:32.219 | Session stopped | details: `{"reason":"","new_status":"STOPPED"}` | Stop reason persisted blank |

### Event totals

- `session_event_log` rows: **3** (`transition=1`, `hot_reload=1`, `stopped=1`)
- `position_audit_log` rows: **0**
- `adjustment_history`: **0**
- `_fill_ledger`: **0**

---

## 3. State Consistency Forensics

## 3.1 Terminal inventory snapshot

From `mmm_sessions.data_json`:

- CE active: `300 @ 75000`, CE total: `323`
- CE frozen positions: 1 record (`23 @ 74400`, entry premium 367.5)
- PE active: `142 @ 74400`, PE total: `142`

## 3.2 Walkthrough ENTRY mismatch

First `_walkthrough_log` entry says:

- `Sell 23 CE @ 74400 + Sell 23 PE @ 74400`
- State in entry record also shows `ce_active_lots=23`, `pe_active_lots=23`

This conflicts with terminal session state (`CE active 300 + frozen 23`, `PE active 142`).

**Interpretation:** walkthrough narrative likely reflects a stale/default template or partial adoption snapshot, not full inherited inventory.

## 3.3 Validation error present but not blocking

State field `_strategy_validation_errors` contains:

> `Straddle strategy requires equal CE/PE active strikes; got CE=75000, PE=74400.`

Despite this, session advanced into monitoring and emergency regime transitions.

---

## 4. Trigger / Safety Behavior

Walkthrough (`3` records):

- Types: `entry=1`, `none=2`
- Parsed safety prefixes in details:
  - `position_cap`: `4`
  - `total_exposure`: `4`
  - `margin_warning`: `2`

No trigger execution path occurred (consistent with 0 order intents/confirms).

---

## 5. Performance Row Consistency Check

From `performance_sessions`:

- `exit_quality = CLEAN`
- `exit_pct_closed = 100.0`
- `stop_open_lots_ce = 323`, `stop_open_lots_pe = 142`
- `stop_reason = ''` (blank)
- `stop_gamma_regime = EMERGENCY`

### Contradiction

`CLEAN/100% closed` is incompatible with open lots recorded at stop (`465 combined`).

**Likely issue class:** scorecard semantic bug or stale-metric write ordering. **[Confidence: High]**

---

## 6. Mistakes, Classification, Confidence

| Issue | Evidence | Avoidable? | Confidence | Impact |
|---|---|---|---|---|
| Session proceeded with structural strike mismatch | `_strategy_validation_errors` non-empty, CE/PE strikes differ | **Yes** | **High** | Compromised strategy invariants |
| Walkthrough ENTRY not aligned with actual inherited inventory | ENTRY shows 23/23; state shows CE323/PE142 | **Yes** | **High** | Operator observability risk |
| Stop reason blank | `stopped` event + performance row reason empty | **Yes** | **High** | Weak post-mortem accountability |
| Performance semantics inconsistent | `CLEAN/100%` vs open lots non-zero | **Yes** | **High** | Misleading control dashboard |
| Immediate emergency posture with no action path | FORCE_REDUCE with 0 execution rows | **Partly** | **Medium** | Potentially deliberate protective halt, but under-instrumented |

---

## 7. What Was Avoidable vs Unavoidable

### Avoidable

1. Allowing monitor start when strategy validation errors are present.
2. Logging contradictory session narratives (ENTRY vs actual inventory).
3. Emitting contradictory scorecard outcomes at stop.
4. Blank stop reason in stop lifecycle path.

### Likely unavoidable / context-driven

1. High gamma posture inherited from carried inventory context.
2. Need to halt quickly when adoption state is structurally inconsistent.

---

## 8. Immediate Fix Priorities

1. **Hard preflight gate:** block monitor start when `_strategy_validation_errors` is non-empty.
2. **Single-source state serialization:** walkthrough ENTRY must be generated from post-adoption canonical state.
3. **Scorecard invariant checks:** if `open_lots > 0`, forbid `exit_pct_closed=100` and `exit_quality=CLEAN`.
4. **Mandatory stop reason enum** (`manual_stop`, `validation_failed`, `unrecoverable_exception`, etc.).
5. **FORCE_REDUCE action fallback:** if no trade path available, explicitly log reason code and residual inventory handling.

---

## 9. Session Scorecard

| Dimension | Score (/10) | Why |
|---|---:|---|
| Execution quality | 2.0 | No execution attempts; no fills |
| Risk-control signaling | 4.5 | Emergency posture detected quickly |
| Data integrity | 1.5 | Multiple state/reporting contradictions |
| Control-plane reliability | 2.5 | Stop occurred, but reason/semantics weak |
| Forensic traceability | 3.0 | Core rows exist, but key fields conflict |

**Overall grade: `D`**

---

## 10. Final Verdict

`mmm17apr26-6` is not a trading-performance session; it is a **control-path integrity incident**.

Main value of this run is diagnostic:

- it exposed preflight gating gaps,
- serialization inconsistencies,
- and scorecard correctness defects under emergency stop conditions.

**Desk verdict:** _“Treat as telemetry/control defect session, not as tradable-strategy evidence.”_
