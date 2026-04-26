# File Audit Report — `mmm_executor.py` (chunk 05)

## Metadata

- Phase: `03 — Execution primitives`
- File: `webui/backend/routes/mmm/mmm_executor.py`
- Chunk: `5` (`lines 1801–EOF`, file tail)
- Date: `2026-04-21`
- Auditor: `GitHub Copilot`

## Scope covered

- Line range: `1801–2004`
- Functions/methods in range:
  - `MMMExecutor._place_limit_order` *(tail only; continuation from chunk 04)*
  - `MMMExecutor.place_market_order_immediate` *(full, `1787–1837`)*
  - `MMMExecutor._amend_order` *(full, `1839–1862`)*
  - `MMMExecutor._cancel_order` *(full, `1864–1880`)*
  - `MMMExecutor._get_order_status` *(full, `1882–1899`)*
  - `MMMExecutor._is_filled` *(full, `1901–1907`)*
  - `MMMExecutor._wait_for_fill` *(full, `1913–1963`)*
  - `MMMExecutor._failure` *(full, `1969–1986`)*
  - `get_executor` *(module-level singleton accessor, `1997–2004`)*

## Function-level results

| Function | Lines | Read keys | Write keys | Side effects | Tests | Status |
|---|---:|---|---|---|---|---|
| `_place_limit_order` *(tail)* | 1801+ (tail continuation only) | post-only rejection text; `best_bid/ask` | retry `current_price` | exchange limit placement retries | No direct internal branch tests | RISK |
| `place_market_order_immediate` | 1787–1837 | exchange raw result (`id`, `average_fill_price`, `filled_size`) | return payload passthrough | true market order placement | Indirect via `test_sealed_kill_switch_and_hard_stop.py` / `test_sealed_straddle_roll_pure.py` | PASS |
| `_amend_order` | 1839–1862 | `order_id`, `product_id`, exchange edit result | bool success/failure | order amend endpoint call | No direct helper-contract tests found | PASS |
| `_cancel_order` | 1864–1880 | `product_id`, cancel response/error text | bool success/failure | order cancel endpoint call | No direct helper-contract tests found | RISK |
| `_get_order_status` | 1882–1899 | order ID | order dict passthrough | single-order exchange read | Only mocked in sealed suites; no direct integration assertions | PASS |
| `_is_filled` | 1901–1907 | `state/status` | bool | none | Indirect only | PASS |
| `_wait_for_fill` | 1913–1963 | periodic order status (`state`, `unfilled_size`) | tuple `(filled, status)` | polling + timeout loop | Usually mocked in smart_execute sealed tests | RISK |
| `_failure` | 1969–1986 | inputs | standardized failure dict | none | Indirect only | PASS |
| `get_executor` | 1997–2004 | singleton global | singleton instance | lock-protected lazy init | No dedicated concurrency contract test found | PASS |

## Findings

| ID | Severity | Function/Area | Evidence (line range) | Risk | Proposed fix |
|---|---|---|---|---|---|
| F03-P1-066 | P1 | Cancel/failure reconciliation gap on tail cancel path | `_cancel_order` treats HTTP `400` as "likely already filled/cancelled" and returns `False` (`1864–1880`); `smart_execute` attempts-exhausted path cancels once (`~865`) and immediately returns failure without a final status reconciliation. | In race windows where cancel returns 400 because order just filled, caller can receive failure while exchange has live fill, creating duplicate-retry / phantom-position risk. | On attempts-exhausted path, if cancel fails (especially `400`), re-fetch final order status and return confirmed fill/partial outcome before emitting terminal failure. |
| F03-P3-067 | P3 | Chunk-05 helper coverage gap | Sealed suites assert routing/caller behavior (`place_market_order_immediate`) and mostly mock `_wait_for_fill` / `_get_order_status`; no direct contracts found for `_cancel_order` (400/no-product-id semantics), `_wait_for_fill` timeout/dead-state transitions, or `get_executor` singleton semantics. | Regressions in helper edge behavior can pass green sealed suites because core internals are stubbed at caller level. | Add sealed contracts for helper internals: `_cancel_order` 400 reconciliation flow, `_wait_for_fill` dead/timeout transitions, and singleton accessor idempotence under repeated calls. |

## Wiring impact

- `place_market_order_immediate` is safety-critical in hard-stop pathways (`mmm_monitor._close_one_side`, `mmm_close_at_5` market path) and remains correctly isolated from `emergency_execute` IOC semantics in sealed contracts.
- `_cancel_order` / `_get_order_status` are also used by kill-switch pending-order cleanup (`mmm_exit_all._cancel_pending_for_kill_switch`), so cancellation semantics directly affect EXITING safety behavior.
- `get_executor` remains the shared executor entry point used by monitor/engine/API paths.

## Validation notes

- Executed tests:
  - `python3 -m pytest webui/backend/routes/mmm/tests/test_sealed_execution_risk_remediation.py webui/backend/routes/mmm/tests/test_sealed_smart_execute.py webui/backend/routes/mmm/tests/test_sealed_kill_switch_and_hard_stop.py -m sealed -v`
  - Result: `43 passed, 5 warnings`.
- Static coverage scan highlights:
  - `place_market_order_immediate` call-routing contracts are covered in sealed hard-stop tests.
  - `_wait_for_fill`, `_cancel_order`, and singleton helper behavior lack direct sealed branch assertions.

## Chunk verdict

- **RISK** (P1 cancellation-reconciliation edge + helper coverage gaps).
- `mmm_executor.py` execution-primitives file audit is now **chunk-complete** (`01–05`).
- Next dependency for Phase 03 progression:
  - Continue with `webui/backend/routes/mmm/mmm_initializer.py` chunk 01 (`lines 1–450`).
