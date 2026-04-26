# File Audit Report — `mmm_wind_down.py` (chunk 01)

## Metadata

- Phase: `01 — Foundations`
- File: `webui/backend/routes/mmm/mmm_wind_down.py`
- Chunk: `1` (`lines 1–EOF`)
- Date: `2026-04-20`
- Auditor: `GitHub Copilot`

## Scope covered

- Line range: `1–EOF`
- Functions/methods in range:
  - `is_wind_down_active`
  - `get_wind_down_status`
  - `compute_wind_down_action`
  - `get_lifo_close_fills`
  - `apply_lifo_removals`
  - `get_wind_down_close_threshold`

## Function-level results

| Function | Lines | Read keys | Write keys | Side effects | Tests | Status |
|---|---:|---|---|---|---|---|
| `is_wind_down_active` | 31–114 | `params.*`, `_vol_wind_down_triggered`, `_trend_wind_down_triggered`, `_atm_wind_down_triggered`, `session_deadline_utc` | none | expiry parser call, time gating | `test_sealed_mmm_wind_down.py`, `test_mmm_wind_down.py` | OK |
| `get_wind_down_status` | 117–183 | `params.*`, `session_deadline_utc` | none | expiry parser call, status dict composition | none (direct) | RISK |
| `compute_wind_down_action` | 186–269 | `params.wind_down_*`, `<side>.active_lots` | none | buyback/floor decision only | `test_sealed_mmm_wind_down.py`, `test_mmm_wind_down.py` | OK |
| `get_lifo_close_fills` | 272–341 | `<side>.positions[]` | side migration on missing `positions` | selects close records in LIFO with `_pos_id` | `test_sealed_mmm_wind_down.py`, `test_mmm_wind_down.py` | OK |
| `apply_lifo_removals` | 344–414 | `<side>.positions[]`, close records | mutates `positions[]`, recomputes side lots | rollback-on-exception, weighted-entry return | `test_sealed_mmm_wind_down.py`, `test_mmm_wind_down.py` | RISK |
| `get_wind_down_close_threshold` | 417–426 | `params.wind_down_close_threshold`, `params.close_at_threshold` | none | delegates to `is_wind_down_active` | `test_sealed_mmm_wind_down.py`, `test_mmm_wind_down.py` | OK |

## Findings

| ID | Severity | Function | Evidence (line range) | Risk | Proposed fix |
|---|---|---|---|---|---|
| F01-P1-030 | P1 | `apply_lifo_removals` wiring in wind-down execution path | `apply_lifo_removals` removes lots exactly as requested by records (`mmm_wind_down.py:344–414`), while caller in monitor logs/uses partial fills via `actual_filled` (`mmm_monitor.py:4322–4336`) but still passes full `group_records` into removals (`mmm_monitor.py:4332`). Runtime probe (`partial-fill mismatch`) showed requested 4 lots removed from state even if exchange fill is only 2 lots. | On partial fills, session can over-remove positions vs exchange reality (under-reporting exposure), breaking lot safety and P&L integrity. | In monitor wind-down path, trim `group_records` to `actual_filled` before calling `apply_lifo_removals`, or extend helper to accept `filled_lots` and enforce ID-scoped partial reduction exactly to exchange-filled size. Add regression test for partial-fill state parity. |
| F01-P2-031 | P2 | `get_wind_down_status` | Activation function allows regime-triggered bypass (`_vol_wind_down_triggered` / `_trend_wind_down_triggered`) at `mmm_wind_down.py:58–66`, but status function starts with `enabled = params.wind_down_enabled` and returns inactive when disabled (`mmm_wind_down.py:128–132`). Probe: `is_wind_down_active=True` while `get_wind_down_status.active=False` for trend-triggered session. | Status payload can contradict live activation behavior, creating operator/UI observability drift during regime-triggered wind-down. | Make `get_wind_down_status` derive `active` from `is_wind_down_active(session)` and include trigger source fields (`trend_triggered`, `vol_triggered`, `atm_triggered`, `time_gate`) so status and runtime behavior stay consistent. |
| F01-P3-032 | P3 | wind-down coverage | No direct tests for `get_wind_down_status` and no wind-down partial-fill reconciliation test exercising `actual_filled < requested` with state-lot parity after LIFO application. Existing suites focus on pure helper contracts and activation/action basics. | Drift between status and activation logic, and partial-fill reconciliation regressions can slip through CI undetected. | Add tests: (1) `get_wind_down_status` regime-trigger parity with `is_wind_down_active`; (2) monitor wind-down partial-fill case asserting state lot reduction equals `filled_size`, not requested size. |

## Wiring impact

- Upstream/downstream callers:
  - `mmm_monitor._process_wind_down_buyback` consumes `compute_wind_down_action`, `get_lifo_close_fills`, `apply_lifo_removals` and applies exchange fill metadata (`filled_size`) in the same flow.
  - `mmm_monitor` heartbeat summary uses `is_wind_down_active` directly; status helper is currently imported but not used in heartbeat payload.
- Risk propagation:
  - Partial-fill mismatch can propagate into session lot tracking, safety gates, and reported P&L if state is reduced beyond exchange-confirmed fills.

## Validation notes

- Tests reviewed:
  - `webui/backend/routes/mmm/tests/test_sealed_mmm_wind_down.py`
  - `webui/backend/routes/mmm/tests/test_mmm_wind_down.py`
- Test execution:
  - `python3 -m pytest webui/backend/routes/mmm/tests/test_sealed_mmm_wind_down.py webui/backend/routes/mmm/tests/test_mmm_wind_down.py -q` → `55 passed`.
- Runtime probes executed:
  - Regime-trigger status parity probe: `is_wind_down_active=True` while `get_wind_down_status.active=False` under `_trend_wind_down_triggered=True` + `wind_down_enabled=False`.
  - Partial-fill mismatch probe: helper removed requested lots from state, demonstrating over-removal risk if caller does not trim close records to actual fill size.

## Chunk verdict

- **RISK**
- File status:
  - `mmm_wind_down.py` audit complete (single chunk).
- Next file dependency note:
  - Proceed to `webui/backend/routes/mmm/mmm_dte_presets.py` chunk 01 for continued Phase 01 foundations coverage.
