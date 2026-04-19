# Whipsaw Audit — 2026-04-19

## Scope

This audit verifies whether the previously flagged Smart Whipsaw integration issues are fixed.

Validation method:
- Static code inspection of backend/frontend whipsaw wiring.
- Targeted runtime probes.
- Focused whipsaw test suite execution.

Files reviewed (primary):
- `webui/backend/routes/mmm/mmm_safety.py`
- `webui/backend/routes/mmm/mmm_monitor.py`
- `webui/backend/routes/mmm/mmm_whipsaw.py`
- `webui/backend/routes/mmm/mmm_whipsaw_smart.py`
- `webui/backend/routes/mmm/mmm_api.py`
- `webui/frontend/src/components/mmm/MMMWhipsawCompareTab.js`
- `webui/frontend/src/components/mmm/MMMStatusBanner.js`

---

## Verification Matrix (Issue Status)

| ID | Previously Flagged Issue | Current Status | Evidence | Risk |
|---|---|---|---|---|
| W-01 | `whipsaw_engine=OFF` still blocked by legacy safety path | **STILL EXISTS** | `mmm_safety.py::run_all_checks()` still calls `check_whipsaw()` unless `_whipsaw_dispatcher_ran` is set. No setter exists in codebase. Runtime probe with `whipsaw_engine=OFF` produced `whipsaw_guard` + `stop_adjustments` and `_whipsaw_score=5`. | **Critical** |
| W-02 | Smart engine receives incomplete runtime context in monitor | **STILL EXISTS** | `mmm_monitor.py` calls `_WhipsawCtx(...)` with only `ce_now`, `pe_now`, `spot` (both Step 3 and fallback). Missing `iv`, `aggressor`, `premium_trigger_fired` => Smart gating/detectors operate with default/empty values. | **Critical** |
| W-03 | Smart tuning params exposed but not actually consumed | **STILL EXISTS** | `mmm_config.py`/`mmm_state.py` expose `smart_ws_gate_count_normal`, `smart_ws_gate_count_defensive`, `smart_ws_size_scalar_defensive`, `smart_ws_size_scalar_observe`; `mmm_whipsaw_smart.py` still hard-codes required gates (`3/4`) and scalars (`1.0/0.5/0.25`) in `multi_gate_decide()`. | **High** |
| W-04 | Smart-primary compare telemetry key mismatch | **STILL EXISTS** | `mmm_whipsaw.py` writes `_ws_legacy_shadow_last` when Smart is primary, but compare surfaces (`mmm_api.py::whipsaw_shadow_diff`, `MMMWhipsawCompareTab.js`) read `_smart_ws_shadow_last`. Runtime probe confirmed Smart-primary session had `_ws_legacy_shadow_last=True`, `_smart_ws_shadow_last=False`. | **High** |
| W-05 | Status badge derives mode from legacy score while Smart may be primary | **STILL EXISTS** | `MMMStatusBanner.js` computes badge mode from `_whipsaw_score` thresholds even when `whipsaw_engine='SMART'`. | **Medium** |

---

## Runtime Probe Results

### Probe A — OFF engine behavior in safety path

Result:
- `whipsaw_engine = OFF`
- `whipsaw_events = 1`
- event: `whipsaw_guard | action=stop_adjustments | level=alert`
- `session _whipsaw_score = 5`

Interpretation:
- OFF is not globally OFF in current safety flow.

### Probe B — Smart-primary shadow key path

Result:
- `has _smart_ws_shadow_last: False`
- `has _ws_legacy_shadow_last: True`
- summary: `primary_engine=SMART, shadow_engine=LEGACY`

Interpretation:
- Compare API/UI paths still miss primary Smart-vs-legacy shadow data unless they also read `_ws_legacy_shadow_last`.

---

## Test Run Summary

Command executed:
- `python3 -m pytest webui/backend/routes/mmm/tests/test_*whipsaw* -q`

Result:
- **106 passed**, **5 warnings**, **3.12s**

Note:
- Passing tests do not currently guarantee elimination of the integration issues listed above.

---

## Overall Verdict

The previously reported high-risk integration issues are **not fully fixed**.

Current state is **not yet safe for trustable SMART-primary unattended behavior** without further wiring corrections for:
1. OFF-mode enforcement in safety path,
2. full Smart context injection from monitor,
3. binding of exposed Smart tuning params,
4. compare telemetry key alignment for Smart-primary mode.

---

## Audit Integrity Note

- This audit session made **no source-code changes** to MMM logic.
- Findings are based on direct code inspection + reproducible runtime probes + test execution.
