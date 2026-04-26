# File Audit Report — `mmm_harvester.py` (chunk 01)

## Metadata

- Phase: `01 — Foundations`
- File: `webui/backend/routes/mmm/mmm_harvester.py`
- Chunk: `1` (`lines 1–EOF`)
- Date: `2026-04-20`
- Auditor: `GitHub Copilot`

## Scope covered

- Line range: `1–EOF`
- Functions/methods in range:
  - `get_effective_harvest_params`
  - `scan_harvestable_positions`

## Function-level results

| Function | Lines | Read keys | Write keys | Side effects | Tests | Status |
|---|---:|---|---|---|---|---|
| `get_effective_harvest_params` | 30–101 | `params.rebalance_*`, `params.harvest_profit_pct`, side `active_lots` | none (returns override dict) | none | `test_sealed_mmm_harvester.py` (G1–G10), `test_mmm_harvester.py` (`TestGetEffectiveHarvestParams`) | RISK |
| `scan_harvestable_positions` | 107–264 | `params.harvest_*`, side `active_lots`, `frozen_positions`, in-flight markers, premium fetcher | none (returns close payload list) | logger diagnostics | `test_sealed_mmm_harvester.py` (H1–H13), `test_mmm_harvester.py` (`TestScanHarvestablePositions`) | RISK |

## Findings

| ID | Severity | Function | Evidence (line range) | Risk | Proposed fix |
|---|---|---|---|---|---|
| F01-P2-022 | P2 | `get_effective_harvest_params` ↔ monitor integration | `mmm_harvester.py:70–72, 84–86, 93–95` returns M3 override `harvest_max_per_beat`; `mmm_harvester.py:150–156` applies only profit/pressure overrides; `mmm_monitor.py:6512, 6526–6527` enforces static `params['harvest_max_per_beat']`. Probe `probe-m3-cap`: override reported `5`, scanner found `6` eligible, runtime cap remained `3`. | M3 “aggressive capacity relief” can be throughput-limited to base cap even under extreme asymmetry, delaying dominant-side lot drainage. | Either (A) plumb an effective per-beat cap from scanner/side metadata into `_process_harvest`, or (B) remove `harvest_max_per_beat` from M3 override contract/docs/tests to avoid false operator expectation. Add sealed integration test for M3 throughput behavior. |
| F01-P2-023 | P2 | `scan_harvestable_positions` | `mmm_harvester.py:178–180` builds in-flight set by `positions[].id`; skip gate `mmm_harvester.py:190` requires truthy `_pos_id`. For no-ID entries, guard is bypassed. Probe `probe-noid-guard`: with `positions=[{'id': None, '_being_closed': True}]` and frozen `_pos_id=None`, scanner still returned eligible entry (`count=1`). | Legacy/no-ID states can bypass in-flight protection and requeue duplicate harvest closes across beats/mechanisms. | Add a no-ID fallback guard (content-match or explicit block when `_being_closed` exists on no-ID rows) so scanner respects in-flight markers even without `_pos_id`. Add sealed regression for no-ID in-flight suppression. |
| F01-P3-024 | P3 | Default + contract consistency (`get_effective_harvest_params`, `scan_harvestable_positions`) | Canonical defaults/docs: `mmm_state.py:545` has `harvest_pressure_threshold=0.5`, `mmm_state.py:559` has `rebalance_pressure_threshold=0.7`, `mmm_config.py:875` documents pressure as `(total_lots/max_lots)`. Scanner/runtime fallbacks: `mmm_harvester.py:59` uses `rebalance_pressure_threshold` default `0.8`; `mmm_harvester.py:156` uses `harvest_pressure_threshold` default `0.6`; implementation pressure source is `active_lots` (`mmm_harvester.py:145`). | Legacy/missing-key sessions can behave differently from canonical defaults, and docs/comments can mislead operators about `total_lots` vs `active_lots` semantics. | Align fallback constants with canonical defaults and update comments/help text to explicitly match `active_lots` semantics (or intentionally standardize on `total_lots` if strategy changes). |

## Wiring impact

- Upstream callers:
  - `mmm_monitor._process_harvest` imports and executes `scan_harvestable_positions` each heartbeat.
- Downstream effects:
  - Returned payloads are consumed by `mmm_close_at_5.close_position(..., mechanism='harvest')`.
  - Successful harvests emit websocket activity via `emit_harvest(...)` and increment session harvest metrics.

## Validation notes

- Tests reviewed for this chunk:
  - `webui/backend/routes/mmm/tests/test_sealed_mmm_harvester.py`
  - `webui/backend/routes/mmm/tests/test_mmm_harvester.py`
- Test execution performed:
  - `python3 -m pytest webui/backend/routes/mmm/tests/test_sealed_mmm_harvester.py webui/backend/routes/mmm/tests/test_mmm_harvester.py -q` → `47 passed`.
- Runtime probes executed:
  - `probe-m3-cap`: confirmed M3 override advertises `harvest_max_per_beat=5` while baseline runtime cap remains session param (`3`).
  - `probe-noid-guard`: confirmed no-ID `_being_closed` marker does not suppress scanner eligibility.

## Chunk verdict

- **RISK**
- File status:
  - `mmm_harvester.py` audit is complete (chunk 01/01).
- Next file dependency notes:
  - Continue with `webui/backend/routes/mmm/mmm_recycler.py` chunk 01.