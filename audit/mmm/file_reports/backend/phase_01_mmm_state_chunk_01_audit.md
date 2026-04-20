# File Audit Report — `mmm_state.py` (chunk 01)

## Metadata

- Phase: `01 — Foundations`
- File: `webui/backend/routes/mmm/mmm_state.py`
- Chunk: `1` (`lines 1–450`)
- Date: `2026-04-20`
- Auditor: `GitHub Copilot`

## Scope covered

- Line range: `1–450`
- Functions/methods in range:
  - `_migrate_side_to_positions`
  - `create_side_state`
  - `recompute_side_lots`
  - `_normalize_strategy_type`
  - `derive_strategy_type`
- Constants/structures in range:
  - `VALID_STRATEGY_TYPES`
  - `STRATEGY_TYPE_ALIASES`
  - `DEFAULT_PARAMS` (partial block through line 450)

## Function-level results

| Function | Lines | Read keys | Write keys | Side effects | Tests | Status |
|---|---:|---|---|---|---|---|
| `_migrate_side_to_positions` | ~27–132 | legacy side fields (`original_lots`, `adjustment_fills`, `frozen_positions`) | `positions`, `_pos_counter`, `_positions_migrated` | Logs migration + duplicate-ID recovery path | `test_mmm_state.py` migration tests | PASS |
| `create_side_state` | ~136–200 | input args | full side state dict with `positions` + derived views | None | `test_sealed_mmm_state.py`, `test_mmm_integration.py` | PASS |
| `recompute_side_lots` | ~203–336 | `positions`, `active_strike` | derived views (`adjustment_fills`, `frozen_positions`, scalar lot counters) | Auto-shifts off-strike active positions + logs | `test_mmm_state.py`, `test_mmm_integration.py`, strike-shift/close-at tests (indirect) | PASS |
| `_normalize_strategy_type` | ~356–364 | strategy identity candidate | normalized strategy token | None | Indirect via create/session-summary identity tests | PASS |
| `derive_strategy_type` | ~367–387 | `params` markers (`strategy_type`, `_preset_source`, `dte_category`) | derived canonical strategy string | None | `test_mmm_strategy_type_identity.py` (integration path), `test_sealed_mmm_state.py` (session creation path) | RISK |

## Findings

| ID | Severity | Function | Evidence (line range) | Risk | Proposed fix |
|---|---|---|---|---|---|
| F01-P3-008 | P3 | `derive_strategy_type` (cross-module identity normalization) | `mmm_state.py:356–387` vs `mmm_config.py:486–493` | Strategy identity normalization logic is duplicated across modules (`mmm_state` and `mmm_config`) with separate alias maps/default handling. Future alias additions can drift and create subtle namespace/validation mismatches. | Centralize normalization in one shared helper module (or export from `mmm_state` and consume in `mmm_config`) and add a contract test asserting both code paths normalize legacy aliases identically. |

## Wiring impact

- Upstream callers:
  - `mmm_api.create_session_endpoint` relies on `create_session` + `derive_strategy_type`
  - `mmm_storage` summary paths consume session fields populated here
  - Runtime modules mutate side state then depend on `recompute_side_lots` invariants
- Downstream callees:
  - `create_session` calls `create_side_state` and later runtime calls into `recompute_side_lots`
- API/UI/socket contract impact:
  - Session summary and strategy identity labels originate from this layer; identity normalization drift here can propagate to API filters and strategy namespace checks.

## Validation notes

- Existing tests relevant:
  - `webui/backend/routes/mmm/tests/test_sealed_mmm_state.py`
  - `webui/backend/routes/mmm/tests/test_mmm_state.py`
  - `webui/backend/routes/mmm/tests/test_mmm_strategy_type_identity.py`
  - `webui/backend/routes/mmm/tests/test_mmm_integration.py` (state model smoke)
- New tests needed:
  - Add a parity test: `mmm_state.derive_strategy_type` and `mmm_config._normalize_strategy_namespace_key` must produce consistent canonical strategy for shared legacy aliases.

## Chunk verdict

- **RISK** (low-severity maintainability drift risk; no P0/P1 issues found in this chunk)
- Next chunk dependency notes:
  - Continue `mmm_state.py` chunk 02 (line `451` onward) to audit full `DEFAULT_PARAMS`/`HOT_RELOAD_PARAMS` contract and session-construction/state-summary paths.
