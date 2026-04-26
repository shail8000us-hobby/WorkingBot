# File Audit Report — `mmm_close_at_5.py` (chunk 02)

## Metadata

- Phase: `01 — Foundations`
- File: `webui/backend/routes/mmm/mmm_close_at_5.py`
- Chunk: `2` (`lines 451–EOF`)
- Date: `2026-04-20`
- Auditor: `GitHub Copilot`

## Scope covered

- Line range: `451–EOF`
- Functions/methods in range:
  - `close_position` (remainder)
  - `_partial_close_position`
  - `_remove_closed_position`
  - `check_side_fully_closed`
  - `check_both_sides_closed`

## Function-level results

| Function | Lines | Read keys | Write keys | Side effects | Tests | Status |
|---|---:|---|---|---|---|---|
| `close_position` (remainder) | 451–744 | order execution result, side ledger, observer/guardian state | close bookkeeping, pending verification, activity/audit trail | exchange close orchestration + logs + event enqueue | `test_mmm_close_at_5.py`, `test_sealed_mmm_close_at_5.py` | RISK |
| `_partial_close_position` | 747–833 | target position + filled lots | remaining lots + close IDs + status markers | log on ID-miss | same | RISK |
| `_remove_closed_position` | 836–943 | target position payload | closes/removes lots and clears trigger snapshot | warning logs on content/ID mismatches | same | PASS |
| `check_side_fully_closed` / `check_both_sides_closed` | 946–968 | side total_lots | boolean return only | none | `test_sealed_check_side_fully_closed.py` | PASS |

## Findings

| ID | Severity | Function | Evidence (line range) | Risk | Proposed fix |
|---|---|---|---|---|---|
| F01-P1-020 | P1 | `_partial_close_position` (ID-mismatch path) | `mmm_close_at_5.py:772–791` logs `Partial close ID-miss` when `_pos_id` is not found in `positions[]` and does not apply deterministic fallback mutation for remaining lots. | Partial fill can desynchronize local state from exchange exposure under ID-link corruption/migration edge cases; downstream risk controls can under-estimate live lots. | Add explicit fallback reconciliation path (content-match + scalar parity + forced mismatch flag) when `_pos_id` lookup fails in partial-close flow. |
| F01-P2-021 | P2 | `close_position` failure cleanup consistency | Cleanup semantics differ across failure paths (`mmm_close_at_5.py:418–426` vs `472–480`): `_being_closed_at` is not consistently cleared when aborting failed closes. | Marker/timestamp cleanup inconsistency can create noisy stale-flag telemetry and make post-failure diagnostics less deterministic. | Normalize all failure cleanup branches to clear both `_being_closed` and `_being_closed_at` (ID and content-match paths), then assert via sealed contracts. |

## Wiring impact

- `_partial_close_position` and `_remove_closed_position` are the state-authority mutators used by all close mechanisms routed through `close_position`.
- `pending_close_verification` registration in this chunk directly affects reconciliation behavior in subsequent beats.

## Validation notes

- Executed:
  - `test_mmm_close_at_5.py`
  - `test_sealed_mmm_close_at_5.py`
- Combined targeted run (with DTE suites) result: `104 passed`.

## Chunk verdict

- **RISK**
- File status:
  - `mmm_close_at_5.py` audit is complete (chunks 01 + 02).
