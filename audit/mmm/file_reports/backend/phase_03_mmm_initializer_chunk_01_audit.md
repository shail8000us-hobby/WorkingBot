# File Audit Report — `mmm_initializer.py` (chunk 01)

## Metadata

- Phase: `03 — Execution primitives`
- File: `webui/backend/routes/mmm/mmm_initializer.py`
- Chunk: `1` (`lines 1–450`)
- Date: `2026-04-22`
- Auditor: `GitHub Copilot`

## Scope covered

- Line range: `1–450`
- Functions/methods in range:
  - `expiry_to_utc_datetime` *(full, `49–85`)*
  - `normalize_expiry` *(full, `88–114`)*
  - `expiry_to_symbol_suffix` *(full, `117–123`)*
  - `MMMInitializer.__init__` *(full, `131–141`)*
  - `MMMInitializer.get_available_expiries` *(full, `145–158`)*
  - `MMMInitializer.get_spot_price` *(full, `162–166`)*
  - `MMMInitializer.get_full_chain` *(full, `169–239`)*
  - `MMMInitializer.preview_strikes` *(full, `245–328`)*
  - `MMMInitializer.preview_atm_straddle` *(full, `330–419`)*
  - `MMMInitializer.validate_manual_selection` *(partial start only, `425–450`; implementation continues in chunk 02)*

## Function-level results

| Function | Lines | Read keys | Write keys | Side effects | Tests | Status |
|---|---:|---|---|---|---|---|
| `expiry_to_utc_datetime` | 49–85 | `expiry_hour_utc`, `expiry_minute_utc` from params | returns UTC `datetime` | none | No direct unit contract | PASS |
| `normalize_expiry` | 88–114 | raw expiry string | normalized `DDMMYYYY` string | none | No direct unit contract | PASS |
| `expiry_to_symbol_suffix` | 117–123 | normalized-expiry expectation | `DDMMYY` suffix | none | No direct unit contract | PASS |
| `MMMInitializer.__init__` | 131–141 | options chain service singleton | service handles on instance | singleton/service wiring | Indirect only | PASS |
| `get_available_expiries` | 145–158 | underlying, chain-service expiries | list passthrough | API/service call | Indirect only | PASS |
| `get_spot_price` | 162–166 | underlying | float passthrough | API/service call | Indirect only | PASS |
| `get_full_chain` | 169–239 | chain payload (`nested_format`, `spot_price`) | formatted chain rows with moneyness labels | API/service call | Indirect via strike workflows | PASS |
| `preview_strikes` | 245–328 | desired premiums, chain snapshot | CE/PE picks + alternatives | chain fetch + selection heuristics | No direct sealed contracts found | PASS |
| `preview_atm_straddle` | 330–419 | chain snapshot + spot | ATM strike payload (`ce`/`pe`) | chain fetch + symbol synthesis | Consumed indirectly by straddle adjustment flows (often mocked) | PASS |
| `validate_manual_selection` *(partial start)* | 425–450 (start) | CE/PE symbols, lots, expiry, underlying contract inputs | N/A in this chunk (body continues) | boundary symbol for manual-entry safety path | No direct sealed contract for full method | RISK |

## Findings

| ID | Severity | Function/Area | Evidence (line range) | Risk | Proposed fix |
|---|---|---|---|---|---|
| F03-P1-068 | P1 | Manual-selection expiry/underlying contract blind spot *(boundary-spanning from partial symbol in this chunk)* | `validate_manual_selection` accepts `expiry` + `underlying` contract inputs (`425–432`), then its continuation normalizes expiry (`453`) and validates ticker/liquidity only (`459–535`) without asserting CE/PE symbols match requested expiry/underlying. API init paths persist user symbols directly (`mmm_api.py` `3280–3281`) while separately persisting session expiry, so symbol-date drift can be stored. | A mixed-expiry or wrong-underlying symbol pair can pass validation and be persisted, creating wrong-contract entry/close divergence when later flows build symbols from session expiry. | In `validate_manual_selection`, parse CE/PE symbols and enforce both `underlying` and expiry-suffix equality against normalized request expiry before returning valid=true; reject mixed-expiry/underlying pairs. |
| F03-P3-069 | P3 | Initializer core contract coverage gap | Workspace tests include nearby consumers, but no dedicated sealed initializer contracts were found for `normalize_expiry`, `preview_strikes`, `preview_atm_straddle`, or full manual-selection validation branches; current targeted suites pass via consumer-level behavior/mocking. | Regressions in initializer parsing/selection contracts can pass green suites because core initializer branches are not asserted directly. | Add sealed tests for: expiry normalization matrix; symbol suffix parsing/validation; premium-selection tie cases in `preview_strikes`; ATM selection contract in `preview_atm_straddle`; manual-selection symbol/expiry/underlying mismatch rejection. |

## Wiring impact

- `mmm_api` routes directly depend on this chunk’s surfaces:
  - `/preview-strikes` → `MMMInitializer.preview_strikes`
  - `/preview_atm_straddle` → `MMMInitializer.preview_atm_straddle`
  - `/chain` → `MMMInitializer.get_full_chain`
  - `/validate-selection` → `MMMInitializer.validate_manual_selection`
- Strike/symbol construction primitives from this file are transitively used across monitor/engine/close/reverse paths via initializer symbol builders.

## Validation notes

- Executed targeted suites:
  - `python3 -m pytest webui/backend/routes/mmm/tests/test_sealed_mmm_strike_shift.py webui/backend/routes/mmm/tests/test_sealed_straddle_adjustment.py -m sealed -v`
  - Result: `58 passed, 6 warnings`.
- Evidence interpretation:
  - These suites validate adjacent strategy contracts that consume initializer outputs.
  - They do not provide direct branch-level contract coverage for initializer core parsing/selection logic.

## Chunk verdict

- **RISK** (P1 manual-selection contract blind spot + P3 direct-coverage gap).
- `mmm_initializer.py` remains **in progress**; chunk 01 completed.
- Next step: continue with `webui/backend/routes/mmm/mmm_initializer.py` chunk 02 (`lines 451–900`).
