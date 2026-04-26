# File Audit Report — `mmm_executor.py` (chunk 01)

## Metadata

- Phase: `03 — Execution primitives`
- File: `webui/backend/routes/mmm/mmm_executor.py`
- Chunk: `1` (`lines 1–450`, partial)
- Date: `2026-04-21`
- Auditor: `GitHub Copilot`

## Scope covered

- Line range: `1–450`
- Functions/methods in range:
  - `_log_activity`
  - `_parse_fill_price`
  - `MMMExecutor.__init__`
  - `MMMExecutor.client`
  - `MMMExecutor._create_rest_client`
  - `MMMExecutor.smart_execute` *(partial: entry/placement/intent + early wait loop)*

## Function-level results

| Function | Lines | Read keys | Write keys | Side effects | Tests | Status |
|---|---:|---|---|---|---|---|
| `_log_activity` | 57–64 | `session_id`, message fields | none | emits activity rows via logger path | `test_sealed_smart_execute.py` | PASS |
| `_parse_fill_price` | 81–104 | `raw_price` | none | strict validation (`None`, NaN/inf, <=0, >1,000,000 rejected) | `test_sealed_execution_risk_remediation.py` (H-2 path uses same parse contract downstream) | PASS |
| `MMMExecutor.__init__` | 124–125 | none | `_client=None` | none | smoke via executor fixtures | PASS |
| `MMMExecutor.client` | 130–148 | `_client`, event loop state | `_client` lazy init/reset | creates async REST client bound to active loop | covered indirectly by executor suites | PASS |
| `MMMExecutor._create_rest_client` | 150–171 | env-derived credentials via `create_delta_rest_client` | none | returns fresh per-call async client | covered indirectly by mocked executor suites | PASS |
| `MMMExecutor.smart_execute` *(partial)* | 177–450 | quotes (`best_bid/ask/tick_size`), `client_order_id`, placement/error payloads | `ORDER_INTENT/ORDER_FAILED` event-log writes, local order state | exchange placement/retry, duplicate coid recovery attempt, pre-fill intent logging | `test_sealed_smart_execute.py` | PASS *(with gaps; see findings)* |

## Findings

| ID | Severity | Function/Area | Evidence (line range) | Risk | Proposed fix |
|---|---|---|---|---|---|
| F03-P2-054 | P2 | `smart_execute` duplicate-order recovery (`duplicate_client_order_id`) | Recovery path only queries `get_open_orders_by_symbol` and matches by `client_order_id` (`319–343`). If no open match, flow continues toward placement failure terminal event (`370+`). | If first order was actually accepted and then filled/cancelled before lookup, open-order-only recovery can miss it and return `ORDER_FAILED`, causing false failure semantics and potential fill attribution drift/untracked exposure handling at caller layer. | Extend duplicate recovery to include terminal/non-open lookup (recent orders/fills by `client_order_id` or order history endpoint), and on recovery write consistent execution-intent events (`ORDER_INTENT`/`ORDER_CONFIRMED` or equivalent terminal linkage). |
| F03-P3-055 | P3 | Sealed coverage gap for duplicate coid recovery branch | No tests found for `duplicate_client_order_id` recovery/open-order lookup branch in MMM test suite (`webui/backend/routes/mmm/tests/**` search: no `duplicate_client_order_id` or `get_open_orders_by_symbol` assertions). | High-value branch in a real exchange race condition is currently unsealed; regressions can ship while primary smart-execute tests still pass. | Add sealed contracts for: (1) duplicate coid + open-order recovery success, (2) duplicate coid + no-open-order fallback behavior, (3) duplicate coid + recovered already-filled order handling semantics. |

## Wiring impact

- `MMMExecutor.smart_execute` remains a central dependency for monitor adjustment, close, and recovery pathways; pre-fill `ORDER_INTENT` durability is present in chunk-01.
- Duplicate coid recovery semantics in this chunk directly influence downstream orphan detection and operator observability in `mmm_audit_log` execution-intent flows.

## Validation notes

- Executed tests:
  - `python3 -m pytest webui/backend/routes/mmm/tests/test_sealed_smart_execute.py -q`
    - Result: `9 passed`.
  - `python3 -m pytest webui/backend/routes/mmm/tests/test_sealed_execution_risk_remediation.py -q`
    - Result: `14 passed`.
- Additional static checks:
  - Function inventory for chunk-01 extracted (`6` symbols start in lines `1–450`; file total functions `22`).
  - Test search performed for duplicate coid branch coverage (`duplicate_client_order_id`, `get_open_orders_by_symbol`) — no direct assertions found.

## Chunk verdict

- **RISK** (runtime branch robustness + sealed coverage gap; no code changes applied in this audit step).
- Next dependency for Phase 03:
  - Continue `mmm_executor.py` chunk 02 (`lines 451–900`) to complete `smart_execute` remainder (repricing/cancel-replace/terminal handling) before moving to subsequent executor symbols.
