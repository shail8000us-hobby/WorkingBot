# File Audit Report — `mmm_executor.py` (chunk 03)

## Metadata

- Phase: `03 — Execution primitives`
- File: `webui/backend/routes/mmm/mmm_executor.py`
- Chunk: `3` (`lines 901–1350`, partial)
- Date: `2026-04-21`
- Auditor: `GitHub Copilot`

## Scope covered

- Line range: `901–1350`
- Functions/methods in range:
  - `MMMExecutor.emergency_execute` *(full: emergency IOC/taker path)*
  - `MMMExecutor.execute_entry` *(partial: concurrent leg execution + success aggregation + CE rollback branch start)*

## Function-level results

| Function | Lines | Read keys | Write keys | Side effects | Tests | Status |
|---|---:|---|---|---|---|---|
| `MMMExecutor.emergency_execute` | 917–1224 | quotes (`best_bid`, `best_ask`, `tick_size`), order state, `average_fill_price`, `unfilled_size` | response payload (`success`, `fill_price`, `filled_size`, `execution_type`, `error`) | IOC taker placement, emergency slippage ratchet, fallback fill lookup (`_h2_exchange_fill_lookup`) | `test_sealed_kill_switch_and_hard_stop.py` *(indirect invariant only)* | PASS *(with risks/gaps below)* |
| `MMMExecutor.execute_entry` *(partial)* | 1225–1350 | leg `success`, `fill_price`, `filled_size`, exception paths | entry aggregate payload (`success`, `total_premium`, `rollback_ok`) | concurrent CE/PE sells (`asyncio.gather`), rollback buy on one-leg failure, emergency escalation trigger | No direct sealed coverage found for `execute_entry` branches | RISK |

## Findings

| ID | Severity | Function/Area | Evidence (line range) | Risk | Proposed fix |
|---|---|---|---|---|---|
| F03-P1-059 | P1 | `execute_entry` success contract accepts partial fills as full entry success | `total_premium` uses `filled_size` (`1287`, `1289`), but `all_success` gates only on boolean `success` (`1291`) | `smart_execute` can return `success=True` with `execution_type='partial_fill'`; entry can be marked successful even when one/both legs are under-filled, creating asymmetry/exposure drift at session start. | Define per-leg full success as `success and filled_size == lots`; require both legs full for `all_success=True`. Return explicit partial-entry state otherwise, with deterministic reconciliation path. |
| F03-P1-060 | P1 | `execute_entry` CE rollback size uses requested `lots`, not actual filled lots | One-leg-failed branch starts at `1316`; rollback buy submits `lots` (`1322–1323`) before emergency escalation (`1335–1340`) | If successful leg was partial, rollback can request oversized reduce-only quantity, causing rejection/escalation churn and increasing orphan/manual-intervention probability during entry failure handling. | Roll back `filled_size` from the successful leg (`ce_result.get('filled_size', 0)`) instead of requested `lots`; use same normalized lot size in smart and emergency rollback paths. |
| F03-P2-061 | P2 | `emergency_execute` optimistic full-fill assumption when `unfilled_size` is unusable | Filled-state branch parses `unfilled_size` (`1078+`); on parse failure sets `filled_size = size` (`1098`), and when missing assumes full fill (`1100–1101`) | Under exchange payload races/corruption, emergency close can be reported as fully filled without verified lot closure, reducing reliability of downstream position/P&L/state reconciliation. | Re-check order once (or short bounded retries) when `unfilled_size` is missing/unparseable; if still unknown, return non-success/indeterminate result requiring explicit reconciliation instead of assuming full fill. |
| F03-P3-062 | P3 | Sealed coverage + contract-doc drift for chunk-03 behaviors | Remediation file header claims H-1/H-3 coverage (`test_sealed_execution_risk_remediation.py:7–8`), but implemented tests are H-2 only (`class TestH2FillPriceFallback`, line `144+`, file ends at line `213`). Workspace grep found no direct `execute_entry(` tests and only anti-call invariants for `emergency_execute` (`test_sealed_kill_switch_and_hard_stop.py:358`, `498`). | Highest-risk emergency/entry branches can regress while sealed suites remain green. Header claims can create false confidence during incident response. | Add sealed contracts for: (1) entry partial-fill aggregation semantics, (2) rollback lot-size normalization by `filled_size`, (3) emergency `unfilled_size` missing/unparseable handling, and (4) header/body consistency checks for remediation suites. |

## Wiring impact

- This chunk governs emergency close behavior and entry atomicity semantics. Any drift here propagates into session exposure symmetry, rollback reliability, and operator trust in “closed” status under volatile conditions.
- `execute_entry` is a control-plane boundary: it translates two lower-level leg outcomes into a single “entry success” decision used by higher monitor/session logic.

## Validation notes

- Executed tests:
  - `python3 -m pytest webui/backend/routes/mmm/tests/test_sealed_execution_risk_remediation.py webui/backend/routes/mmm/tests/test_sealed_smart_execute.py webui/backend/routes/mmm/tests/test_sealed_kill_switch_and_hard_stop.py -m sealed -v`
    - Result: `43 passed, 5 warnings`.
- Additional static checks:
  - Verified remediation suite truncation/implementation scope: `test_sealed_execution_risk_remediation.py` line count is `213`, with H-2 tests only.
  - Verified test-surface absence for direct `execute_entry` coverage in sealed MMM tests.

## Chunk verdict

- **RISK** (P1 entry-success semantics + rollback lot normalization, plus emergency fill-quantity verification resilience and sealed coverage drift).
- Next dependency for Phase 03:
  - Continue `mmm_executor.py` chunk 04 (`lines 1351–1800`) to complete `execute_entry` tail + `execute_adjustment` transition paths.
