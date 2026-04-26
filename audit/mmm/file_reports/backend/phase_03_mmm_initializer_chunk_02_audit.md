# File Audit Report — `mmm_initializer.py` (chunk 02)

## Metadata

- Phase: `03 — Execution primitives`
- File: `webui/backend/routes/mmm/mmm_initializer.py`
- Chunk: `2` (`lines 451–EOF`)
- Date: `2026-04-23`
- Auditor: `GitHub Copilot`

## Scope covered

- Line range: `451–870`
- Functions/methods in range:
  - `MMMInitializer.validate_manual_selection` *(tail completion, `451–535`; start audited in chunk 01)*
  - `MMMInitializer.build_symbol` *(full, `541–551`)*
  - `MMMInitializer._rank_strikes` *(full, `557–670`)*
  - `MMMInitializer._enrich_option` *(full, `676–706`)*
  - `MMMInitializer._get_moneyness` *(full, `708–716`)*
  - `MMMInitializer._extract_ticker_data` *(full, `718–761`)*
  - `MMMInitializer.check_liquidity` *(full, `767–806`)*
  - `MMMInitializer.calculate_total_premium` *(full, `808–824`)*
  - `MMMInitializer.calculate_lots_with_buffer` *(full, `826–846`)*
  - `get_initializer` *(module singleton accessor, `858–870`)*

## Function-level results

| Function | Lines | Read keys | Write keys | Side effects | Tests | Status |
|---|---:|---|---|---|---|---|
| `validate_manual_selection` *(tail)* | 451–535 | ticker quotes/greeks, CE/PE symbol data | return payload fields (`valid`, `warnings`, `errors`) | ticker fetch calls via chain service | No direct initializer-only contracts | PASS |
| `build_symbol` | 541–551 | `option_type`, `underlying`, `strike`, `expiry` | symbol string | none | Indirect only (consumer-level) | PASS |
| `_rank_strikes` | 557–670 | chain rows (`bid`, `ask`, `mark_price`, `bid_size`) | ranked candidates + selected best | none | Indirect via consumers (`preview_strikes`, replenish scan) | RISK |
| `_enrich_option` | 676–706 | option quote fields | enriched quote payload | none | Indirect only | PASS |
| `_get_moneyness` | 708–716 | strike/spot relation | classification string | none | Indirect only | PASS |
| `_extract_ticker_data` | 718–761 | raw ticker/quotes/greeks shape | normalized ticker payload | none | Indirect only | PASS |
| `check_liquidity` | 767–806 | ticker `bid_size` | sufficiency payload | chain-service ticker fetch | No dedicated endpoint/helper contracts found | PASS |
| `calculate_total_premium` | 808–824 | CE/PE premium + lots, `LOT_SIZE_BTC` | aggregate totals | none | No direct tests found | PASS |
| `calculate_lots_with_buffer` | 826–846 | base lots, buffer % | buffered lot count | emits `DeprecationWarning` | No direct tests found | PASS |
| `get_initializer` | 858–870 | singleton globals/lock | singleton instance | lock-protected lazy init | No dedicated concurrency contract found | PASS |

## Findings

| ID | Severity | Function/Area | Evidence (line range) | Risk | Proposed fix |
|---|---|---|---|---|---|
| F03-P2-070 | P2 | Auto-mode sellability gate bypass (`_rank_strikes` + preview/init wiring) | `_rank_strikes` keeps zero-bid candidates as selectable via score penalty (`557–670`, especially zero-bid penalty branch), not hard rejection. Auto flow in UI calls `previewStrikes` then can directly call `initSessionFresh` (`MMMConfigPanel.js` `335`, `419`, `570`) without manual `validateSelection`. Manual path explicitly rejects zero-bid legs via `validate_manual_selection` (`502–504`). | Auto setup can initialize/start with unsellable legs (by the system’s own manual-validation rules), causing avoidable entry failures/retries and stale entry-baseline assumptions for operators. | Add a hard sellability gate for preview-selected legs (`bid > 0`, optional min bid_size) before returning `success=True` from preview flow; otherwise return `success=False` with a clear “no sellable OTM strikes” error. |
| F03-P3-071 | P3 | Chunk-02 helper contract coverage gap | Search across MMM tests found only indirect patch usage of `get_initializer` in strike-shift tests; no direct contracts for `build_symbol`, `_extract_ticker_data`, `check_liquidity`, `calculate_total_premium`, `calculate_lots_with_buffer`. | Helper regressions can pass green suites because consumer-level tests mock or bypass these contracts. | Add sealed helper tests for symbol format matrix, ticker-shape normalization branches, liquidity decision payload contract, and deprecation helper behavior. |

## Wiring impact

- `build_symbol` and `get_initializer` are high-fanout primitives used across API, monitor, close, reverse, and fill-sync paths.
- `_rank_strikes` is not just startup preview logic; it is also used by monitor replenish-side strike selection flows.
- `check_liquidity` is exposed via `/check-liquidity` route but currently appears under-used by frontend flows.

## Validation notes

- Executed targeted suites:
  - `python3 -m pytest webui/backend/routes/mmm/tests/test_sealed_mmm_strike_shift.py webui/backend/routes/mmm/tests/test_sealed_straddle_adjustment.py -m sealed -v`
  - Result: `58 passed, 6 warnings`.
- Coverage interpretation:
  - Strong consumer-path validation exists around strike-shift and straddle-adjustment surfaces.
  - Direct contracts for chunk-02 initializer helpers remain sparse.

## Chunk verdict

- **RISK** (P2 auto-mode sellability gate bypass + P3 helper coverage gap).
- `mmm_initializer.py` is now **chunk-complete** (`01–02`; file complete).
- Next Phase 03 target:
  - `webui/backend/routes/mmm/mmm_pending_orders.py` chunk 01 (`lines 1–250`; file complete in one chunk).
