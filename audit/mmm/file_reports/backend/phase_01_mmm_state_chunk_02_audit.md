# File Audit Report — `mmm_state.py` (chunk 02)

## Metadata

- Phase: `01 — Foundations`
- File: `webui/backend/routes/mmm/mmm_state.py`
- Chunk: `2` (`lines 451–1436`)
- Date: `2026-04-20`
- Auditor: `GitHub Copilot`

## Scope covered

- Line range: `451–1436`
- Functions/methods in range:
  - `create_session` (`~916–1249`)
  - `initialize_side_from_entry` (`~1252–1291`)
  - `_backfill_side_premiums` (`~1294–1321`)
  - `get_session_summary` (`~1324–1436`)
- Major structures reviewed:
  - `DEFAULT_PARAMS` tail (`451–761`)
  - `HOT_RELOAD_PARAMS` (`764–913`)

## Function-level results

| Function | Lines | Read keys | Write keys | Side effects | Tests | Status |
|---|---:|---|---|---|---|---|
| `create_session` | ~916–1249 | `DEFAULT_PARAMS`, caller `params`, DTE preset helpers, storage lookup | full session state object (`params`, `ce`/`pe`, runtime namespaces) | Reads storage for ID collision checks; logs warnings on parse/collision fallback | `test_sealed_mmm_state.py`, `test_mmm_state.py`, `test_mmm_integration.py` | RISK |
| `initialize_side_from_entry` | ~1252–1291 | side payload args | mutates selected side state + trigger snapshot | Warn-and-skip on re-init safety check | `test_sealed_mmm_state.py`, `test_mmm_integration.py` | PASS |
| `_backfill_side_premiums` | ~1294–1321 | legacy session fields (`entry_fill_price`, `adjustment_history`) | computed return tuple only | None | `test_sealed_mmm_state.py` (summary path) | PASS |
| `get_session_summary` | ~1324–1436 | session scalar + side fields, canonical pnl helper | summary dict | Imports canonical pnl helper; no persistence side effects | `test_sealed_mmm_state.py` | PASS |

## Findings

| ID | Severity | Function | Evidence (line range) | Risk | Proposed fix |
|---|---|---|---|---|---|
| F01-P1-009 | P1 | `HOT_RELOAD_PARAMS` + `create_session`/PATCH config contract | `mmm_state.py:764–913` vs `mmm_config.py:17–340,728+` and PATCH path `mmm_api.py:2583+` | Hot-reload contract is split-brain: multiple keys marked hot in `mmm_state.HOT_RELOAD_PARAMS` are not declared in `mmm_config.PARAM_RULES` (20-key drift in probe). Validation silently drops such keys (`validate_params(..., hot_only=True) -> validated_keys=[]`), so PATCH calls can fail with “No valid parameters” despite state marking them hot. Operator-control reliability degrades. | Establish one source of truth for editable/hot params (prefer `mmm_config.PARAM_RULES`). Either derive `HOT_RELOAD_PARAMS` from config or add a sealed parity test that enforces exact key parity both directions and blocks drift in CI. |

## Wiring impact

- Upstream callers:
  - `mmm_api.create_session_endpoint` invokes `create_session`.
  - Runtime workflows call `initialize_side_from_entry` and `get_session_summary` through API/storage paths.
- Downstream dependencies:
  - `create_session` composes preset builders from `mmm_dte_presets` and storage collision checks from `mmm_storage`.
  - `get_session_summary` depends on `mmm_pnl_core.compute_current_total_pnl` for canonical net P&L.
- API/UI/socket contract impact:
  - Parameter metadata/hot-reload behavior exposed by API is governed by `mmm_config`, while this file maintains its own hot set. Divergence here creates operational confusion and patch-time surprises.

## Validation notes

- Existing tests relevant:
  - `webui/backend/routes/mmm/tests/test_sealed_mmm_state.py`
  - `webui/backend/routes/mmm/tests/test_mmm_state.py`
  - `webui/backend/routes/mmm/tests/test_mmm_integration.py`
  - `webui/backend/routes/mmm/tests/test_mmm_lot_lifecycle_integration.py` (includes hot-flag consistency checks for a subset)
- Runtime probe evidence used in this chunk:
  - `state_hot_missing_rules_count = 20`
  - `rule_hot_missing_state_count = 15`
  - Example mismatches dropped by validation: `close_at_use_bid`, `shift_cooldown_sec`, `consecutive_dir_limit` (`validated_keys=[]`, no explicit error).
- New tests needed:
  - Full parity contract test covering **all** `DEFAULT_PARAMS`/`HOT_RELOAD_PARAMS` vs `PARAM_RULES` to prevent future silent drift.

## Chunk verdict

- **RISK**
- Next chunk dependency notes:
  - `mmm_state.py` file audit is complete (chunks 01 + 02).
  - Continue Phase 01 with `webui/backend/routes/mmm/mmm_storage.py` chunk 01, since persistence layer directly consumes state shape and summary contracts audited here.
