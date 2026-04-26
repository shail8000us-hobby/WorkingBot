# File Audit Report — `mmm_executor.py` (chunk 04)

## Metadata

- Phase: `03 — Execution primitives`
- File: `webui/backend/routes/mmm/mmm_executor.py`
- Chunk: `4` (`lines 1351–1800`, partial)
- Date: `2026-04-21`
- Auditor: `GitHub Copilot`

## Scope covered

- Line range: `1351–1800`
- Functions/methods in range:
  - `MMMExecutor.execute_entry` *(tail: rollback completion + return contract)*
  - `MMMExecutor.execute_adjustment` *(full)*
  - `MMMExecutor._h2_exchange_fill_lookup` *(full)*
  - `MMMExecutor._fetch_quotes` *(full)*
  - `MMMExecutor._calculate_mid_price` *(full)*
  - `MMMExecutor.get_mid_price` *(full)*
  - `MMMExecutor._place_limit_order` *(full)*
  - `MMMExecutor.place_market_order_immediate` *(partial start only)*

## Function-level results

| Function | Lines | Read keys | Write keys | Side effects | Tests | Status |
|---|---:|---|---|---|---|---|
| `MMMExecutor.execute_entry` *(tail)* | 1351–1430 | leg `success/error`, rollback responses | aggregate payload (`success`, `rollback_ok`, `error`) | rollback smart+emergency buyback attempts | No direct sealed branch tests found | RISK |
| `MMMExecutor.execute_adjustment` | 1437–1566 | close/open execution results (`success`, `fill_price`, `filled_size`) | return payload (`success`, `open_leg_recovered`, `net_cost`) | sequential close/open + emergency recovery sell | No direct caller-contract tests found | RISK |
| `MMMExecutor._h2_exchange_fill_lookup` | 1572–1613 | order status `average_fill_price` | fallback fill price return value | one extra exchange status lookup | `test_sealed_execution_risk_remediation.py` (H-2) | PASS |
| `MMMExecutor._fetch_quotes` | 1616–1669 | L2 orderbook, ticker quotes | quote dict (`best_bid`, `best_ask`, `tick_size`, source) | async exchange reads (orderbook/ticker) | Indirect via smart_execute tests | PASS |
| `MMMExecutor._calculate_mid_price` / `get_mid_price` | 1672–1692 | quote fields (`best_bid`, `best_ask`, `tick_size`) | computed mid | none | Indirect | PASS |
| `MMMExecutor._place_limit_order` | 1698–1785 | post-only rejection text, fresh quotes | retry price + error/success payload | order placement retries, re-quote loop | No direct sealed branch tests found | RISK |

## Findings

| ID | Severity | Function/Area | Evidence (line range) | Risk | Proposed fix |
|---|---|---|---|---|---|
| F03-P1-063 | P1 | `_place_limit_order` buy-side post-only retry pricing | On post-only reject (`1750+`), buy retry branch sets `current_price = round(ask, 2)` (`1766–1768`) while keeping `post_only=True` (`1723`). | A buy-at-ask post-only retry is self-contradictory (crosses the book), so retries can repeatedly reject and exhaust (`1785`) during critical close/rollback paths. | For buy post-only retries, re-anchor to `best_bid` (or `best_bid - tick`) to guarantee passive placement. Keep emergency/taker path separate for urgency. |
| F03-P2-064 | P2 | `execute_adjustment` lot normalization in recovery path | Close leg admits any boolean success (`1476`), open leg always submits requested `open_lots` (`1487`), and recovery re-sell uses requested `close_lots` (`1511–1512`) while cost accounting already uses actual `filled_size` (`1549`). | If close leg is partial and open fails, recovery can re-sell more than actually closed, creating over-restoration/lot drift. *(No in-repo runtime caller currently targets this helper, but risk is latent if re-used.)* | Normalize recovery/order sizing to `close_result.get('filled_size', close_lots)` and make partial-close semantics explicit in the return contract. |
| F03-P3-065 | P3 | Chunk-04 execution branch coverage gap | Sealed remediation covers `_h2_exchange_fill_lookup` only; `test_sealed_smart_execute.py` heavily mocks `_place_limit_order` callsites and does not exercise its internal buy-retry branch; no direct tests found for `MMMExecutor.execute_adjustment`. | High-risk retry/recovery branches can regress while sealed suites remain green. | Add sealed tests for: (1) post-only buy retry repricing logic, (2) `execute_adjustment` partial-close + open-fail recovery sizing, (3) return-contract invariants for `open_leg_recovered` and `net_cost`. |

## Wiring impact

- `_place_limit_order` is on the core `smart_execute` path used across entry, close, and rollback operations.
- `execute_adjustment` appears as a legacy/dormant helper in current repo call graph (no direct runtime callsites found), but remains part of executor surface and can be reactivated by future flows.
- `_h2_exchange_fill_lookup` remains safety-critical for emergency fill-price fidelity when exchange payloads lag.

## Validation notes

- Executed tests:
  - `python3 -m pytest webui/backend/routes/mmm/tests/test_sealed_execution_risk_remediation.py webui/backend/routes/mmm/tests/test_sealed_smart_execute.py webui/backend/routes/mmm/tests/test_sealed_kill_switch_and_hard_stop.py -m sealed -v`
    - Result: `43 passed, 5 warnings`.
- Static coverage scan highlights:
  - `_h2_exchange_fill_lookup` has direct sealed assertions.
  - No direct sealed contracts found for `_place_limit_order` internal buy retry branch or `MMMExecutor.execute_adjustment`.

## Chunk verdict

- **RISK** (P1 retry-pricing contradiction in `_place_limit_order`; latent lot-normalization drift in `execute_adjustment`; coverage gaps).
- Next dependency for Phase 03:
  - Continue `mmm_executor.py` chunk 05 (`lines 1801–EOF`) to finish order-operation internals + monitor/wait/failure helpers.
