# AUDIT_RISK_ENGINE — MMM Runtime Risk Audit

Date: 2026-04-17  
Mode: Read-only static audit (no runtime mutation, no order actions)  
Primary scope: `webui/backend/routes/mmm/*` (+ supporting service path for emergency monitor)

---

## Executive summary

This audit focused on three risk classes:

1. **Silent failure** (system continues but critical signal/action is dropped)
2. **Late action** (safety action occurs after meaningful delay)
3. **Rule conflict** (two controls interact in a way that defeats intended safety)

### Overall assessment

- **Risk status:** **ELEVATED** until top findings are remediated.
- **Estimated safety score (static-audit estimate):** **71 / 100**.
- **Confidence:** Medium-high (broad source coverage, but no live replay in this pass).

### Highest-priority issues

1. **Silent reconciliation alert drop due wrong `emit_safety` call signature**
2. **Replenish path pending-order guard can proceed on unverifiable order state (`'error'`)**
3. **`exit_all` reverse close block references undefined variable `reason`**
4. **Circuit-breaker auto-pause/partial-beat capabilities are implemented but not wired into monitor flow**

### Strong controls verified

- 3-layer stale-monitor defense remains present (`thread.join(15s)` + run-loop generation guard + save-time stale abort path)
- Independent hard-stop guard thread with anti-double-fire event
- API preflight gates for invariant violations and cap/adoption violations
- Emergency close order in `_auto_close_all`: reverse → perp → options

---

## Findings by severity

## 🔴 Critical / High

### F-01 — Silent safety alert failure in reconciliation path

- **Type:** Silent failure
- **Severity:** **Critical**
- **Evidence:**
  - `webui/backend/routes/mmm/mmm_monitor.py:8750` calls:
    - `emit_safety(self.session_id, 'POSITION_MISSING_FROM_EXCHANGE', {...})`
  - `webui/backend/routes/mmm/mmm_websocket.py:247` signature is:
    - `emit_safety(session_id, safety_type, level, message, details=None)`
- **Why this is risky:**
  - The call at `mmm_monitor.py:8750` is missing required `level` and `message` args.
  - It will raise a runtime exception, but that exception is swallowed by `except Exception: pass`.
  - Result: reconciliation can remove phantom lots from session state without emitting the intended operator safety event.
- **Recommended fix:**
  - Replace with full signature call, e.g. pass explicit `level`, `message`, `details`.
  - Replace bare `except` with logged exception so alert-channel failures are visible.
- **Suggested test:**
  - Unit test asserting reconciliation path emits `mmm_safety` event with expected payload on missing-exchange-position condition.

---

### F-02 — Replenish pending-order guard does not treat `'error'` as blocking

- **Type:** Silent failure / duplicate-order risk
- **Severity:** **High**
- **Evidence:**
  - Adjustment path (safe behavior):
    - `webui/backend/routes/mmm/mmm_monitor.py:4486` blocks on `guard_result in ('open', 'error')`
  - Replenish path (inconsistent behavior):
    - `webui/backend/routes/mmm/mmm_monitor.py:6786` only handles `'filled'`
    - `webui/backend/routes/mmm/mmm_monitor.py:6790` only handles `'open'`
    - exceptions in guard path log and **proceed**
  - Guard contract:
    - `webui/backend/routes/mmm/mmm_pending_orders.py:192,226,250` returns `'error'` with explicit “treating as open (conservative)” intent.
- **Why this is risky:**
  - Under exchange/API uncertainty, replenish can place a new sell while prior order status is unverifiable.
  - This undermines the anti-duplication posture used in standard adjustment flow.
- **Recommended fix:**
  - Align replenish to adjustment behavior: treat `'error'` as blocking/skip.
  - Consider making guard-exception path fail-safe (`return False`) instead of proceed.
- **Suggested test:**
  - Sealed test: replenish with guard_result `'error'` must skip new order.

---

### F-03 — `exit_all` reverse disable uses undefined variable

- **Type:** Rule conflict / latent runtime exception
- **Severity:** **High**
- **Evidence:**
  - `webui/backend/routes/mmm/mmm_exit_all.py:116`:
    - `disable_reverse_mode(session, f'exit_all: {reason}')`
  - `reason` is not defined in this scope at that point.
- **Why this is risky:**
  - Causes exception in reverse-close try block during `run_exit_all`.
  - Although caught, it can skip intended reverse-state disable semantics and produce noisy/partial behavior in emergency unwinds.
- **Recommended fix:**
  - Define `reason` before use (or use a literal/available variable in that scope).
  - Add regression test that executes reverse-close branch in `run_exit_all`.

---

### F-04 — Circuit breaker remediation hooks are unintegrated in monitor runtime

- **Type:** Rule conflict / delayed action
- **Severity:** **High**
- **Evidence:**
  - Capability exists:
    - `webui/backend/routes/mmm/mmm_circuit_breaker.py:232` `should_auto_pause`
    - `webui/backend/routes/mmm/mmm_circuit_breaker.py:247` `partial_beat_allowed`
  - Tests expect behavior:
    - `webui/backend/routes/mmm/tests/test_sealed_execution_risk_remediation.py:89+`
  - No runtime usage found in monitor:
    - `grep` for `should_auto_pause|partial_beat_allowed` in `mmm_monitor.py` returns no matches.
- **Why this is risky:**
  - The monitor may continue in degraded fetch conditions without invoking intended automatic containment behavior.
  - Design intent and runtime behavior diverge.
- **Recommended fix:**
  - Wire `should_auto_pause` and `partial_beat_allowed` into heartbeat miss/partial-beat routing.
  - Add integration test at monitor layer (not only breaker unit tests).

---

## 🟠 Medium

### F-05 — Exit-all exchange verification can miss lingering positions if ledger marks closed early

- **Type:** Silent failure
- **Severity:** **Medium**
- **Evidence:**
  - `webui/backend/routes/mmm/mmm_exit_all.py:393` builds `tracked_strikes` only from non-closed local positions.
  - `webui/backend/routes/mmm/mmm_exit_all.py:417` only flags exchange positions if strike is in that set.
- **Why this is risky:**
  - If local state marks positions closed prematurely, verification may report success while exchange still has open options outside `tracked_strikes`.
- **Recommended fix:**
  - Track verification scope from all attempted close symbols/strikes (or persisted managed-strike set), not only currently non-closed positions.

---

### F-06 — Margin fetch failure is explicitly fail-open

- **Type:** Silent failure / delayed reaction under data outage
- **Severity:** **Medium**
- **Evidence:**
  - `webui/backend/routes/mmm/mmm_margin_guardian.py:427-430`:
    - On fetch failure: “keeping last tier …” and returns `require_action=False`.
- **Why this is risky:**
  - If margin API is down during rapid stress, enforcement remains at stale tier (possibly GREEN).
  - This is a deliberate policy choice, but should be treated as an explicit risk trade-off.
- **Recommended fix options:**
  - Configurable fail policy: `fail_open` vs `fail_safe_after_n_failures`.
  - Emit escalating alerts after consecutive margin-fetch failures.

---

## 🟡 Low / Design trade-offs (not immediate defects)

### F-07 — Hard-stop guard interval introduces bounded response latency

- **Type:** Late action (bounded by design)
- **Severity:** **Low**
- **Evidence:**
  - `webui/backend/routes/mmm/mmm_monitor.py:10061` `HARD_STOP_INTERVAL = 10`
  - `webui/backend/routes/mmm/mmm_monitor.py:10219` 1s-loop wait for next guard check.
- **Notes:**
  - Mitigated by heartbeat-side max-loss checks and 70% pre-breach force-heartbeat (`mmm_monitor.py:10196+`).
  - Keep as-is unless business requires tighter reaction and can absorb higher call pressure.

---

## Positive control validation (important)

1. **Stale monitor containment remains layered**
   - `start_session_monitor` old-thread join/backstop: `mmm_monitor.py:11123+`
   - save-time stale generation rejection with bool return path: `mmm_monitor.py:11369+`
   - caller abort flag on rejected save: `mmm_monitor.py:842`

2. **Hard-stop architecture remains independent and sealed**
   - guard thread and anti-double-fire event: `mmm_monitor.py:10032+`, `10134+`

3. **API lifecycle controls are strong**
   - preflight invariant/cap checks with `force_start` override: `mmm_api.py:724-787`
   - exit-all sets `EXITING` atomically and forces immediate heartbeat: `mmm_api.py:1785-1810`

4. **Emergency close sequencing remains correct**
   - reverse → perp → options in `_auto_close_all`: `mmm_monitor.py:8056+`

---

## Recommended remediation plan

### 0–24 hours (hotfix priority)

1. Fix F-01 (`emit_safety` call signature + logging)
2. Fix F-02 (treat replenish pending `'error'` as blocking)
3. Fix F-03 (undefined `reason` in `run_exit_all` reverse branch)

### 24–72 hours

4. Integrate F-04 circuit breaker monitor hooks (`should_auto_pause`, `partial_beat_allowed`)
5. Harden F-05 exit-all verification strike scope

### 3–7 days

6. Decide and implement explicit margin-failure policy (F-06)
7. Add integration tests for all remediated paths (especially monitor + exit_all + replenish)

---

## Final score and residual risk

### Current score (static estimate)

- **71 / 100 (ELEVATED)**

### After top-4 remediations (expected)

- **~84 / 100 (MODERATE/CONTROLLED)**

### Residual risks after remediation

- Inherent response-latency bounds (10s guard interval)
- External API outage policies (intentional fail-open/fail-safe trade-offs)
- Strategy-level operator overrides (`force_start`, force-heartbeat behavior) that require disciplined runbooks

---

## Audit notes

- This report is based on static code-path analysis and cross-module consistency checks.
- No live trading actions, order placement, or service restarts were performed.
- Recommended next step: apply top hotfixes behind sealed tests, then run full MMM test suite + targeted incident replay scenarios.
