# File Audit Report — `mmm_executor.py` (chunk 02)

## Metadata

- Phase: `03 — Execution primitives`
- File: `webui/backend/routes/mmm/mmm_executor.py`
- Chunk: `2` (`lines 451–900`, partial)
- Date: `2026-04-21`
- Auditor: `GitHub Copilot`

## Scope covered

- Line range: `451–900`
- Functions/methods in range:
  - `MMMExecutor.smart_execute` *(partial: fill finalization + partial-fill continuation + reprice/amend/cancel-replace + attempts-exhausted path)*

## Function-level results

| Function | Lines | Read keys | Write keys | Side effects | Tests | Status |
|---|---:|---|---|---|---|---|
| `MMMExecutor.smart_execute` *(partial)* | 451–900 | `average_fill_price`, `unfilled_size`, quote snapshots, dead/open state, `_current_order_size`, `_cumulative_filled` | `ORDER_CONFIRMED`, `ORDER_CANCELLED` event writes on selected terminal paths; in-memory cumulative fill state | fill reconciliation, partial continuation order placement, aggressive repricing, cancel+replace fallback, final cancellation on attempts exhausted | `test_sealed_smart_execute.py`, `test_sealed_execution_risk_remediation.py` | PASS *(with risks/gaps below)* |

## Findings

| ID | Severity | Function/Area | Evidence (line range) | Risk | Proposed fix |
|---|---|---|---|---|---|
| F03-P1-056 | P1 | `smart_execute` continuation size accounting in cancel+replace branch | After partial continuation mode switches `_current_order_size` (`656–658`), cancel-path fill math and replacement placement still use original `size` (`810`, `849–850`). | In continuation scenarios, fallback replacement can re-place full original lots (instead of remaining lots), and cancel-path `filled_size` can be overstated. This can create overfill/exposure drift under exchange race conditions. | Use `_current_order_size` consistently for cancel-path fill computation/logging and replacement `_place_limit_order` size; preserve original `size` only for final target comparisons and user-facing totals. |
| F03-P2-057 | P2 | `smart_execute` execution-intent terminal closure parity | `ORDER_INTENT` is written on placement (`415–426`), and selected fail/dead branches write terminal events (`386–403`, `696–710`), but attempts-exhausted path (`862–905`) returns failure without an `EXECUTION_INTENT` terminal event. | `ORDER_INTENT` can remain dangling in audit stream when order times out/reprice exhausts, weakening orphan-intent observability and postmortem reconciliation quality. | On attempts-exhausted branch, enqueue explicit terminal event (`ORDER_CANCELLED`/`ORDER_FAILED`) with order_id, attempts, elapsed, and final cancel outcome. |
| F03-P3-058 | P3 | Sealed coverage gap for continuation + cancel/replace + exhaustion closure | No direct sealed assertions found for continuation sizing/cancel-path branch (`659–857`) or attempts-exhausted intent closure (`862–905`) in `test_sealed_smart_execute.py` / executor-focused suites. | High-risk edge branches can regress while primary success/dead/placement contracts stay green. | Add sealed contracts for: (1) partial continuation + amend-fail cancel-replace uses remaining size, (2) cancel-path filled-size uses in-flight order size, (3) attempts-exhausted emits execution-intent terminal event. |

## Wiring impact

- This chunk controls the highest-risk runtime transitions in `smart_execute`: partial continuation, cancel-race reconciliation, and reprice exhaustion finalization.
- Behavior here directly impacts downstream lot accounting and audit-log reliability used by restore/orphan handling and operator diagnostics.

## Validation notes

- Executed tests:
  - `python3 -m pytest webui/backend/routes/mmm/tests/test_sealed_smart_execute.py webui/backend/routes/mmm/tests/test_sealed_execution_risk_remediation.py -q`
    - Result: `23 passed`.
- Additional static checks:
  - Branch scan confirmed continuation-order path (`_current_order_size` updates) and cancel+replace path use different size variables (`size` vs `_current_order_size`).
  - Test-surface scan found no direct sealed branch assertions for continuation + cancel/replace sizing and attempts-exhausted intent closure.

## Chunk verdict

- **RISK** (P1 state/exposure accounting risk under partial-continuation cancel-replace races + intent closure parity gap).
- Next dependency for Phase 03:
  - Continue `mmm_executor.py` chunk 03 (`lines 901–1350`) to audit `emergency_execute` and the start of entry orchestration.
