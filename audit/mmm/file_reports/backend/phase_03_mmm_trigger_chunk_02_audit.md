# File Audit Report — `mmm_trigger.py` (chunk 02)

## Metadata

- Phase: `03 — Execution primitives`
- File: `webui/backend/routes/mmm/mmm_trigger.py`
- Chunk: `2` (`lines 488–780`, file complete)
- Date: `2026-04-27`
- Auditor: `GitHub Copilot`

## Scope covered

- Line range: `488–780`
- Functions/methods in range:
  - `apply_theta_acceleration` (`488–567`)
  - `compute_adaptive_interval` (`571–644`)
  - `compute_adaptive_interval_v2` (`648–711`)
  - `apply_theta_acceleration_v2` (`714–780`)

## Function-level results

| Function | Lines | Read keys | Write keys | Side effects | Tests | Status |
|---|---:|---|---|---|---|---|
| `apply_theta_acceleration` | 488–567 | `params.theta_acceleration_window`, `min_trigger_move`, `adjustment_interval` | none | pure return calculation | `test_mmm_trigger.py`, `test_sealed_mmm_trigger.py` | PASS |
| `compute_adaptive_interval` | 571–644 | `base_interval`, `hours_to_expiry`, `enabled`, `ADAPTIVE_INTERVAL_TIERS`, floor constant | none | pure return calculation (sealed) | `test_mmm_trigger.py`, `test_sealed_compute_adaptive_interval.py` | PASS |
| `compute_adaptive_interval_v2` | 648–711 | `base_interval`, `hours_to_expiry`, `total_dte_hours`, v2 tier table | none | pure return calculation (sealed) | `test_sealed_compute_adaptive_interval.py` | PASS |
| `apply_theta_acceleration_v2` | 714–780 | `params.min_trigger_move`, `adjustment_interval`, `theta_acceleration_window`, `total_dte_mins` | none | pure return calculation | `test_sealed_mmm_trigger.py` | PASS |

## Findings

- No new chunk-02-specific findings.
- Carry-forward open findings from chunk 01 remain active:
  - `F03-P3-074`
  - `F03-P3-075`

## Wiring impact

- `mmm_monitor.py` consumes all chunk-02 functions in heartbeat interval/trigger shaping:
  - `compute_adaptive_interval_v2(...)` at `1184`
  - `compute_adaptive_interval(...)` at `1189`
  - `apply_theta_acceleration_v2(...)` at `1206`
  - `apply_theta_acceleration(...)` at `1210`
- This wiring establishes a two-stage cadence policy in monitor flow:
  - hours-scale adaptive interval first,
  - then near-expiry theta acceleration overlay.

## Validation notes

- Executed:
  - `python3 -m pytest webui/backend/routes/mmm/tests/test_sealed_compute_adaptive_interval.py webui/backend/routes/mmm/tests/test_mmm_trigger.py webui/backend/routes/mmm/tests/test_sealed_mmm_trigger.py -q` → `121 passed, 5 warnings`.
- Coverage posture for this chunk is strong:
  - dedicated sealed tier-boundary/floor tests for v1/v2 adaptive interval,
  - sealed + behavior tests for theta acceleration and cap behavior (`min(..., 80.0)`).

## Chunk verdict

- **PASS**
- File status:
  - `mmm_trigger.py` phase-03 audit complete (chunks 01 + 02).
- Next file dependency note:
  - Continue Phase 03 execution-primitives audit with `webui/backend/routes/mmm/mmm_fill_sync.py` chunk 01.
