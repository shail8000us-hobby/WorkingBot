# MMM Cross-Session Comparative Forensic Review

**Sessions reviewed:** `mmm17apr26-4`, `mmm17apr26-5`, `mmm17apr26-6`  
**Review objective:** Prop-desk-grade comparison of execution quality, control integrity, risk posture, and process reliability.

---

## 1. Executive Comparative Verdict

Across this 3-session sequence, profitability remained positive, but **process integrity deteriorated**:

- `mmm17apr26-4`: profitable with known control defects (audit row miss + dead-zone behavior).
- `mmm17apr26-5`: profitable on paper but ended in **unrecoverable NameError** crash path.
- `mmm17apr26-6`: no trades; exposed **state/telemetry correctness failures** under emergency stop.

### Portfolio-level takeaway

This is not a market-edge failure. It is primarily a **control-plane robustness and observability correctness** issue.

---

## 2. Side-by-Side Metrics

| Metric | mmm17apr26-4 | mmm17apr26-5 | mmm17apr26-6 |
|---|---:|---:|---:|
| Duration (minutes) | 498.3 | 498.3 | 1.3 |
| Final total P&L | 45.8757 | 11.9713 | 3.4111 |
| Final realized P&L | 33.3425 | 0.0 | 0.0 |
| Max drawdown | 7.4078 | 5.1581 | 1.0447 |
| Session score (`performance_sessions`) | 6.0 | 4.0 | 5.0 |
| Exit quality | MESSY | MESSY | CLEAN *(contradictory)* |
| Exit % closed | 0.0 | 0.0 | 100.0 *(contradictory)* |
| Intents / confirms / audits | 9 / 9 / 8 | 3 / 3 / 3 | 0 / 0 / 0 |
| Total adjustments | 5 | 3 | 0 |
| Lots traded (combined) | 185 | 73 | 0 |
| Total close-at-threshold events | 3 | 0 | 0 |
| Terminal regime action | FORCE_REDUCE | BLOCK_PE_SELLS | FORCE_REDUCE |
| Terminal gamma regime | EMERGENCY | HARD | EMERGENCY |

---

## 3. Execution Quality Comparison

### 3.1 Intent → confirm latency

- **Session 4:** avg `41.59s`, p50 `53.03s`, max `69.82s` (slow in 0DTE context)
- **Session 5:** avg `11.78s`, p50 `10.38s`, max `17.81s` (better)
- **Session 6:** no orders

### 3.2 Signed slippage vs intent mid

- **Session 4:** `-0.120 USD`
- **Session 5:** `+2.025 USD`
- **Session 6:** `0` (no fills)

### 3.3 Fill lifecycle integrity

- **Session 4:** 1 confirmed replenish fill missing in `position_audit_log` (`order_id=1277579424`)  
- **Session 5:** lifecycle parity clean (`3/3/3`) with ~1ms confirm→audit lag  
- **Session 6:** no execution lifecycle

**Comparative interpretation:** trade execution micro-quality is not the primary systemic weakness; control/data integrity is.

---

## 4. Risk Posture & Decision Logic Comparison

### Session 4 (baseline)

- Reached high inventory stress (`max_combined_lots=600`)
- Trigger YES but no action: `51` beats (from prior session-4 forensic)
- Late-session replenish added risk near stop window

### Session 5

- Trigger dead-zone intensified: PE YES repeatedly, with `147` trigger-YES-but-none outcomes in walkthrough parsing
- Safety-block pressure persistent (`position_cap`, `asymmetry`, `lot_velocity` markers)
- No close harvest; P&L remained unrealized

### Session 6

- Immediate emergency posture without execution
- Structural invariant breach present (`CE strike != PE strike`) while session ran
- Acts as control-path anomaly session, not a strategy-performance sample

---

## 5. Cross-Session Inventory Lineage Signals

From analytics/state snapshots:

- Session 4 final lots: `CE 300`, `PE 300`
- Session 5 final lots: `CE 23`, `PE 142`
- Session 6 initial lots: `CE 323`, `PE 142`

### High-confidence inference

- Session 6 CE initial (`323`) exactly matches `300 + 23` from sessions 4+5 CE residue.
- Session 6 PE initial (`142`) matches session 5 PE residue.

This strongly indicates **cross-session carry/adoption chaining**, with selective residual transfer behavior.

---

## 6. Control-Plane Defect Matrix (Avoidable vs Unavoidable)

| Finding | Sessions | Avoidable? | Confidence | Severity |
|---|---|---|---|---|
| Missing audit row for confirmed fill | 4 | Yes | High | P0 |
| Runtime NameError crash-stop | 5 | Yes | High | P0 |
| Trigger dead-zone under cap/asymmetry blocks | 4,5 | Yes | High | P0 |
| Validation error not hard-blocking start | 6 | Yes | High | P0 |
| Walkthrough/state mismatch | 6 | Yes | High | P1 |
| Scorecard contradiction (`CLEAN/100%` with open lots) | 6 | Yes | High | P1 |
| Blank stop reason / weak stop metadata | 4,6 (and stop-path ambiguity in 5) | Yes | High | P1 |
| Regime volatility / market movement | 4,5,6 | No | High | Contextual |

---

## 7. Prioritized Fix Roadmap

## P0 (must fix before scaling)

1. **Lifecycle invariant:** every `ORDER_CONFIRMED` must produce exactly one audit row.
2. **Exception hardening:** prevent NameError-class failures in monitor critical paths (lint/static + runtime sentinels).
3. **Blocked-trigger fallback:** if trigger YES and cap blocks sell, force a risk-reducing alternative path.
4. **Validation gate:** block strategy start when structural invariants fail (e.g., CE/PE strike mismatch).

## P1 (stabilize observability and operator trust)

1. Make stop reason mandatory and typed.
2. Enforce scorecard consistency rules (`open_lots > 0` cannot be `100% closed`).
3. Make walkthrough ENTRY/summary generated from canonical post-adoption state only.
4. Add direct analytics counters for suppressed triggers by reason code.

## P2 (optimization)

1. Time-to-expiry policy switch to prevent late risky replenishment.
2. Cap model split: risk-adding vs risk-reducing cap semantics.
3. Automated post-session consistency checker that flags contradictory records immediately.

---

## 8. Desk-Level Verdict

### What improved

- Session 5 execution latency/slippage quality improved meaningfully over session 4.

### What regressed

- Reliability and data integrity regressed from session 4 → 5 → 6:
  - audit parity defect (4),
  - unrecoverable runtime crash (5),
  - state/scorecard inconsistency under emergency stop (6).

### Final call

**Do not scale risk based on these three sessions.**  
Fix control-plane invariants first; then re-run with a short canary cohort and strict forensic acceptance gates.
