# File Audit Report — `mmm_config.py` (chunk 01)

## Metadata

- Phase: `01 — Foundations`
- File: `webui/backend/routes/mmm/mmm_config.py`
- Chunk: `1` (`lines 1–450`)
- Date: `2026-04-20`
- Auditor: `GitHub Copilot`

## Scope covered

- Line range: `1–450`
- Functions/methods in range:
  - None (module constants and strategy-namespace constant sets only)
- Major structures reviewed:
  - `PARAM_RULES` (`~17–340`)
  - `_STRADDLE_ROLL_PARAMS_SHARED` (`343–361`)
  - `_STRADDLE_ROLL_PURE_ONLY_PARAMS` (`363–369`)
  - `_ADJUSTMENT_ENGINE_ONLY_PARAMS` (`371–450`, partial; set continues in next chunk)

## Function-level results

| Function | Lines | Read keys | Write keys | Side effects | Tests | Status |
|---|---:|---|---|---|---|---|
| `PARAM_RULES` (constant map) | 17–340 | N/A (constant declaration) | N/A | None at declaration time | `tests/test_mmm_lot_lifecycle_integration.py` (PARAM_RULES coverage checks) | PASS |
| `_STRADDLE_ROLL_PARAMS_SHARED` | 343–361 | N/A | N/A | None | Covered indirectly by strategy-forbidden enforcement tests and API patch behavior | PASS |
| `_STRADDLE_ROLL_PURE_ONLY_PARAMS` | 363–369 | N/A | N/A | None | Covered indirectly via strategy namespace enforcement paths | PASS |
| `_ADJUSTMENT_ENGINE_ONLY_PARAMS` (partial in this chunk) | 371–450 | N/A | N/A | None | Cross-checked against runtime selector/tests (`whipsaw_*` subset) | RISK |

## Findings

| ID | Severity | Function | Evidence (line range) | Risk | Proposed fix |
|---|---|---|---|---|---|
| F01-P1-002 | P1 | `PARAM_RULES` + `_ADJUSTMENT_ENGINE_ONLY_PARAMS` (`whipsaw_smart_enabled`) | `mmm_config.py:62–64, 390–392`; runtime selector `mmm_whipsaw.py:173–185`; no-op usage signal `mmm_whipsaw.py:237`; guard-removed tests `tests/test_mmm_whipsaw_params.py:80–95`, `tests/test_smart_whipsaw_shadow_does_not_bind.py:57–60` | Control-plane truth drift: `whipsaw_smart_enabled` is exposed as hot config and namespace-controlled key but does not gate engine selection at runtime. Operator can toggle it expecting behavior change and get none. | Pick one source-of-truth behavior and align all layers: **(A)** remove/deprecate `whipsaw_smart_enabled` as a runtime control and update API/UI/docs/tests, or **(B)** reintroduce binding gate in dispatcher/selector and update tests accordingly. |
| F01-P2-004 | P2 | Cross-layer whipsaw semantics linked to config key | UI text says gate is binding: `MMMSettingsDialog.js:588–590`; compare tab says backend ignores gate: `MMMWhipsawCompareTab.js:125–126` (with `smartEnabled` read at line 87 but not used in status logic) | Operator guidance conflict inside frontend itself; increases rollback confusion under stress. | Unify frontend help/status language to backend truth; remove or clearly mark non-binding fields as deprecated/read-only until semantic alignment is complete. |
| F01-P3-005 | P3 | `_ADJUSTMENT_ENGINE_ONLY_PARAMS` maintenance model | `mmm_config.py:371–450` (manual static list, continues into next chunk) | Dual-maintenance drift risk vs `PARAM_RULES` over time (currently consistent, but fragile). | Add strategy/category tags to parameter metadata and derive forbidden sets programmatically; keep a test that asserts namespace sets are a strict subset of declared params. |

## Wiring impact

- Upstream callers:
  - `webui/backend/routes/mmm/mmm_api.py:59` imports config accessors.
  - `webui/backend/routes/mmm/mmm_api.py:345,2583` validates params using `validate_params`.
  - `webui/backend/routes/mmm/mmm_api.py:2110–2112` publishes parameter metadata and hot-reload set.
- Downstream callees:
  - Chunk-01 constants feed chunk-02 functions (`validate_params`, namespace accessors, metadata endpoint).
- API/UI/socket contract impact:
  - `/api/mmm/params/info` and settings UX expose `whipsaw_smart_enabled` as active control, but runtime selector is keyed by `whipsaw_engine` only.
  - Result: config contract and runtime behavior are currently not fully isomorphic.

## Validation notes

- Existing tests relevant:
  - `webui/backend/routes/mmm/tests/test_mmm_lot_lifecycle_integration.py` (PARAM_RULES/metadata coverage consistency)
  - `webui/backend/routes/mmm/tests/test_mmm_whipsaw_params.py` (explicitly asserts guard removal semantics)
  - `webui/backend/routes/mmm/tests/test_smart_whipsaw_shadow_does_not_bind.py` (engine=SMART behavior independent of smart_enabled)
- Additional audit checks run:
  - Parsed `PARAM_RULES` for duplicate keys: **none found** (`258 unique / 258 parsed`).
  - Verified `_ADJUSTMENT_ENGINE_ONLY_PARAMS` entries are present in `PARAM_RULES`: **no missing keys**.
- New tests needed:
  - Contract test tying param metadata semantics to dispatcher truth (prevent future UI/runtime drift on whipsaw control fields).

## Chunk verdict

- **RISK**
- Next chunk dependency notes:
  - Continue with `mmm_config.py` chunk 02 (starting line `451`) to audit completion of `_ADJUSTMENT_ENGINE_ONLY_PARAMS`, `STRATEGY_PARAM_NAMESPACES`, and function-layer enforcement (`validate_params`, interdependency checks, metadata descriptions).
