# File Audit Report — `mmm_config.py` (chunk 02)

## Metadata

- Phase: `01 — Foundations`
- File: `webui/backend/routes/mmm/mmm_config.py`
- Chunk: `2` (`lines 451–EOF`)
- Date: `2026-04-20`
- Auditor: `GitHub Copilot`

## Scope covered

- Line range: `451–EOF`
- Functions/methods in range:
  - `_normalize_strategy_namespace_key` (`486–493`)
  - `get_strategy_param_namespace` (`496–503`)
  - `get_forbidden_params_for_strategy` (`505–507`)
  - `validate_params` (`510–569`)
  - `_interdependency_checks` (`572–724`)
  - `get_hot_reload_params` (`728–730`)
  - `get_param_info` (`733–EOF`)
- Major structures reviewed:
  - `STRATEGY_PARAM_NAMESPACES` (`462–483`)

## Function-level results

| Function | Lines | Read keys | Write keys | Side effects | Tests | Status |
|---|---:|---|---|---|---|---|
| `_normalize_strategy_namespace_key` | 486–493 | `strategy_type` | None | None | Indirectly covered via strategy identity tests | PASS |
| `get_strategy_param_namespace` | 496–503 | `STRATEGY_PARAM_NAMESPACES` | None | None | `test_mmm_strategy_type_identity.py` (namespace behavior via API) | PASS |
| `get_forbidden_params_for_strategy` | 505–507 | `STRATEGY_PARAM_NAMESPACES` | None | None | `test_mmm_strategy_type_identity.py`, `test_sealed_mmm_adversarial_isolation.py` | PASS |
| `validate_params` | 510–569 | `params`, `PARAM_RULES` | `validated`, `errors` (local) | None | `test_sealed_mmm_config.py` | RISK |
| `_interdependency_checks` | 572–724 | validated subset | `errors` list | None | `test_sealed_mmm_config.py` | RISK |
| `get_hot_reload_params` | 728–730 | `PARAM_RULES` | None | None | `test_sealed_mmm_config.py` | PASS |
| `get_param_info` | 733–EOF | `PARAM_RULES`, description map | `info` (local) | None | `test_sealed_mmm_config.py`, API info endpoint consumers | PASS |

## Findings

| ID | Severity | Function | Evidence (line range) | Risk | Proposed fix |
|---|---|---|---|---|---|
| F01-P1-006 | P1 | `validate_params` + `_interdependency_checks` | `mmm_config.py:510–569, 572–724`; call path `mmm_api.py:2583` validates patch before merge | Cross-parameter invariants are validated only on submitted keys, not effective session params. Partial updates can produce invalid final configs (e.g., margin tier inversion) without rejection. | In `update_session_params`, validate against `merged_params = {**current_params, **validated_patch}` (or add `validate_effective_params(base, patch)` in config module). Keep hot-only enforcement on patch keys, but run interdependency checks on effective merged map. |
| F01-P2-007 | P2 | `validate_params` (unknown-key skip behavior in create flow) | `mmm_config.py:529–533` silently skips unknown keys; create path `mmm_api.py:345` accepts result without unknown-key rejection | Session creation succeeds even when payload contains typo/unknown keys; operator can believe risk params were applied while defaults are used. | Keep skip behavior for runtime/hot-patch compatibility, but in `create_session_endpoint` compute `unknown = payload_keys - PARAM_RULES` and hard-fail (or warn + require explicit confirm flag). |

## Wiring impact

- Upstream callers:
  - `webui/backend/routes/mmm/mmm_api.py:345` (`create_session_endpoint`)
  - `webui/backend/routes/mmm/mmm_api.py:2583` (`update_session_params`)
  - `webui/backend/routes/mmm/mmm_api.py:2110–2112` (`params/info` response)
- Downstream callees:
  - None external; this module is validation/metadata provider.
- API/UI/socket contract impact:
  - `/api/mmm/session/<id>/params` may accept patches that violate full-session cross-constraints when only one side of a pair is updated.
  - `/api/mmm/session/create` currently tolerates unknown keys; UI/backends that send mistyped keys will not receive a contract failure.

## Validation notes

- Existing tests relevant:
  - `webui/backend/routes/mmm/tests/test_sealed_mmm_config.py` (type/range + selected interdependency checks)
  - `webui/backend/routes/mmm/tests/test_mmm_strategy_type_identity.py` (strategy namespace integration)
  - `webui/backend/routes/mmm/tests/test_sealed_mmm_adversarial_isolation.py` (forbidden-set behavior)
- Runtime probe evidence captured during audit:
  - Partial patch check: `validate_params({'margin_green_pct': 90}, hot_only=True)` returns no error, while validating merged defaults+patch flags margin tier ordering violation.
  - Create path check: posting create payload with typo-only key (`max_lots_per_sied`) returns `201 success`; typo key is silently dropped and default `max_lots_per_side` remains.
- New tests needed:
  - Contract test: partial PATCH that would violate margin ordering after merge must fail.
  - Contract test: create-session unknown keys should be rejected (or explicitly surfaced) per chosen policy.

## Chunk verdict

- **RISK**
- Next chunk dependency notes:
  - `mmm_config.py` file-level audit is complete for Phase 01.
  - Continue Phase 01 with `webui/backend/routes/mmm/mmm_state.py` (chunk 01) to validate default/runtime param-state alignment against `PARAM_RULES` findings.
