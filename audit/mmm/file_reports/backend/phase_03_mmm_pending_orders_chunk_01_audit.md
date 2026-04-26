# File Audit Report — `mmm_pending_orders.py` (chunk 01)

## Metadata

- Phase: `03 — Execution primitives`
- File: `webui/backend/routes/mmm/mmm_pending_orders.py`
- Chunk: `1` (`lines 1–249`, file complete)
- Date: `2026-04-23`
- Auditor: `GitHub Copilot`

## Scope covered

- Line range: `1–249`
- Functions/methods in range:
  - `register_pending` (`61–85`)
  - `clear_pending` (`88–96`)
  - `get_pending` (`99–103`)
  - `clear_all` (`106–110`)
  - `check_and_resolve_pending` (`117–249`)

## Function-level results

| Function | Lines | Read keys | Write keys | Side effects | Tests | Status |
|---|---:|---|---|---|---|---|
| `register_pending` | 61–85 | session_id, side, order metadata | `_registry[session_id][side]` | logs registration | `test_sealed_mmm_pending_orders.py` | PASS |
| `clear_pending` | 88–96 | session_id, side | `_registry[session_id][side] = None` | logs clear | `test_sealed_mmm_pending_orders.py` | PASS |
| `get_pending` | 99–103 | session_id, side | none | none | `test_sealed_mmm_pending_orders.py` | PASS |
| `clear_all` | 106–110 | session_id | `_registry.pop(session_id, None)` | logs full clear | `test_sealed_mmm_pending_orders.py` | PASS |
| `check_and_resolve_pending` | 117–249 | pending entry, order state, average_fill_price, unfilled_size | may clear registry, may call `record_fill_fn`, may mutate session via callback | exchange verification + pending-order recovery | `test_sealed_mmm_pending_orders.py` | RISK |

## Findings

| ID | Severity | Function | Evidence (line range) | Risk | Proposed fix |
|---|---|---|---|---|---|
| F03-P2-072 | P2 | Partial-fill recovery gap in `check_and_resolve_pending` | The guard only resolves all-or-nothing states: `state in _STATES_FILLED` records a fill only when `average_fill_price` is present (`~192–212`), while `state in _STATES_DEAD` clears the registry without inspecting `filled_size` / `unfilled_size` (`~214–221`). The function logs `unfilled_size` for open states but never uses it (`~223–242`). By contrast, `mmm_executor.py` and `mmm_monitor.py` explicitly use `unfilled_size`/`filled_size` to compute partial fills and preserve correct lot accounting (`mmm_executor.py:482–526`, `806–835`; `mmm_api.py:6387`). | A partially filled order that later becomes `cancelled`/`expired` can be cleared as “dead” without recording the executed lots, undercounting exposure and creating duplicate-order risk on the next heartbeat. | Teach the guard to inspect `filled_size`/`unfilled_size` before clearing a dead/open order. If any positive fill exists, invoke `record_fill_fn` for the filled portion (or defer clearing until fill quantity is recoverable), rather than treating the order as all-or-nothing. |
| F03-P3-073 | P3 | Missing direct contract coverage for mixed partial states | The sealed suite covers only the happy path plus all-or-nothing recovery states: no pending, stale sentinel, real-id TTL, filled with price, filled without price, cancelled, open, and exception. It does not exercise `cancelled`/`expired` orders that still report a nonzero filled quantity, nor callback-failure idempotence after a partial recovery attempt. | Regression in the partial-fill recovery path can ship while the current sealed suite stays green; a one-line status handling change could silently reintroduce duplicate-adjustment or undercount bugs. | Add sealed tests for: (1) `cancelled`/`expired` order with positive `filled_size` or `unfilled_size` and valid fill price, (2) `check_and_resolve_pending` callback failure after fill recording, (3) repeated recovery calls proving the guard is idempotent. |

## Wiring impact

- `mmm_monitor.py` uses `check_and_resolve_pending()` before both adjustment and replenish execution, so any recovery gap directly affects duplicate-order suppression and whether recovered fills are restored to session state.
- `mmm_engine.py` and `mmm_monitor.py` both pre-register `pending` before `smart_execute()` and then update the registry with the real order id, so this module is the gatekeeper for duplicate-hedge prevention during timeouts/restarts.
- The exchange-order API surfaces `unfilled_size`, and executor code already interprets it for partial-fill math; this module should stay aligned with that contract.

## Validation notes

- Executed:
  - `python3 -m pytest webui/backend/routes/mmm/tests/test_sealed_mmm_pending_orders.py -q` → `16 passed, 5 warnings`
- Review notes:
  - Existing sealed coverage is solid for all-or-nothing states.
  - No direct partial-fill recovery test currently exercises the state-mixed edge case called out above.

## Chunk verdict

- **RISK**
- File status:
  - `mmm_pending_orders.py` audit complete (single chunk).
- Next file dependency note:
  - Continue Phase 03 execution-primitives audit with `webui/backend/routes/mmm/mmm_trigger.py` chunk 01.
