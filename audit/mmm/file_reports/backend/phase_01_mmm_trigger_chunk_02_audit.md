# File Audit Report — `mmm_trigger.py` (chunk 02)

## Metadata

- Phase: `01 — Foundations`
- File: `webui/backend/routes/mmm/mmm_trigger.py`
- Chunk: `2` (`lines 451–EOF`)
- Date: `2026-04-20`
- Auditor: `GitHub Copilot`

## Scope covered

- Line range: `451–EOF`
- Functions/methods in range:
  - `update_trigger_snapshots` (remainder + complete function coverage)
  - `apply_theta_acceleration`
  - `compute_adaptive_interval`
  - `compute_adaptive_interval_v2`
  - `apply_theta_acceleration_v2`

## Function-level results

| Function | Lines | Read keys | Write keys | Side effects | Tests | Status |
|---|---:|---|---|---|---|---|
| `update_trigger_snapshots` (remainder) | 451–470 | trigger snapshots + open-position strike sets | pruned snapshot entries + session side refs | logs pruning activity and trigger update summary | `test_mmm_trigger.py` | PASS |
| `apply_theta_acceleration` | 472–552 | `theta_acceleration_window`, `min_trigger_move`, `adjustment_interval`, `minutes_to_expiry` | return dict only | none | `test_sealed_mmm_trigger.py`, `test_mmm_trigger.py` | PASS |
| `compute_adaptive_interval` | 555–629 | base interval, hours-to-expiry, tier table | return dict only | none | `test_sealed_compute_adaptive_interval.py`, `test_mmm_trigger.py` | PASS |
| `compute_adaptive_interval_v2` | 632–695 | base interval, hours-to-expiry, total DTE hours, v2 tier table | return dict only | none | `test_sealed_compute_adaptive_interval.py` | PASS |
| `apply_theta_acceleration_v2` | 698–EOF | `minutes_to_expiry`, optional total DTE minutes, params fallback | return dict only | none | `test_sealed_mmm_trigger.py` | PASS |

## Findings

- No **new** chunk-02-only findings were identified.

## Carry-forward risk note

- `F01-P1-013` from chunk 01 remains open for the full `update_trigger_snapshots` function:
  - cross-side active-key skip can block frozen snapshot ratcheting when frozen strike equals opposite-side active strike.
- `F01-P2-014` from chunk 01 remains open for `evaluate_triggers` behavior under partial snapshot data.

## Wiring impact

- These functions define monitor cadence and near-expiry sensitivity:
  - `compute_adaptive_interval*` shapes baseline heartbeat pacing.
  - `apply_theta_acceleration*` applies near-expiry trigger widening and sub-30s cadence constraints.
- Effective values are consumed by monitor loop interval scheduling and ephemeral trigger thresholds.

## Validation notes

- Tests reviewed for this chunk:
  - `webui/backend/routes/mmm/tests/test_sealed_compute_adaptive_interval.py`
  - `webui/backend/routes/mmm/tests/test_sealed_mmm_trigger.py`
  - `webui/backend/routes/mmm/tests/test_mmm_trigger.py`
- Contracts confirmed:
  - Tier boundaries and floor behavior are explicitly sealed for v1 and v2 interval scaling.
  - Theta acceleration v1/v2 widening cap (`80.0`) is covered by sealed tests.

## Chunk verdict

- **PASS** (no new chunk-02 findings)
- Next file dependency notes:
  - `mmm_trigger.py` file audit is complete (chunks 01 + 02).
  - Continue Phase 01 with `webui/backend/routes/mmm/mmm_reversal.py` chunk 01.
