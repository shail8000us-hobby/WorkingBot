# File Audit Report — `mmm_trigger.py` (chunk 01)

## Metadata

- Phase: `03 — Execution primitives`
- File: `webui/backend/routes/mmm/mmm_trigger.py`
- Chunk: `1` (`lines 1–487`)
- Date: `2026-04-27`
- Auditor: `GitHub Copilot`

## Scope covered

- Line range: `1–487`
- Functions/methods in range:
  - `evaluate_triggers` (`47–193`)
  - `check_frozen_pnl_trigger` (`196–321`)
  - `update_trigger_snapshots` (`324–486`)

## Function-level results

| Function | Lines | Read keys | Write keys | Side effects | Tests | Status |
|---|---:|---|---|---|---|---|
| `evaluate_triggers` | 47–193 | `params.min_trigger_move`, `_effective_min_trigger_move`, `min_trigger_dollar`, active strikes/snapshots/lots | none | trigger outcome computation + warning logs on missing snapshots | `test_mmm_trigger.py`, `test_sealed_mmm_trigger.py`, `test_mmm_integration.py` | PASS |
| `check_frozen_pnl_trigger` | 196–321 | `params.min_frozen_trigger_dollar`, frozen positions, trigger snapshots, fetched premiums | none | frozen-loss fallback computation + info logs when triggered | `test_mmm_trigger.py`, `test_sealed_mmm_trigger.py` | RISK |
| `update_trigger_snapshots` | 324–486 | active strikes, frozen positions, optional fetched premiums, pin flags (`_trigger_pinned`, `_pin_adj_count`) | mutates side `trigger_snapshot` maps; can clear pin flags | logs trigger/pin/prune actions | `test_mmm_trigger.py` | RISK |

## Findings

| ID | Severity | Function | Evidence (line range) | Risk | Proposed fix |
|---|---|---|---|---|---|
| F03-P3-074 | P3 | `check_frozen_pnl_trigger` return-contract semantic drift | Base return path sets `frozen_triggered=False` (`239`), but enabled path always returns `frozen_triggered=True` (`317`) regardless of `outcome`. Runtime probe confirms `{'outcome':'none','frozen_triggered':True}` when `min_frozen_trigger_dollar>0` and losses are zero. | Current monitor flow is mostly insulated (it only adopts frozen result when `outcome != OUTCOME_NONE`), but the field name becomes misleading for any future callsite/telemetry consumer and can cause incorrect operator interpretation. | Set `frozen_triggered` to `outcome != OUTCOME_NONE` (or `ce_triggered or pe_triggered`) in the enabled return path; add a contract test for enabled+none outcome semantics. |
| F03-P3-075 | P3 | Missing sealed coverage for pin-expiry + stale-prune branches in `update_trigger_snapshots` | Stateful pin/expiry logic exists (`_MAX_PIN_ADJ=3`, pin counters/auto-expiry at `368–394`) and stale snapshot pruning logic exists (`439–474`), but no direct assertions found in `test_mmm_trigger.py` or `test_sealed_mmm_trigger.py` for `_trigger_pinned`, `_pin_adj_count`, `_pinned_trigger_value`, or prune behavior. | Regressions in trigger-pin safety and stale baseline cleanup can ship while trigger suites remain green; these are low-frequency branches but high-debug-cost when they fail in live sessions. | Add dedicated tests for: (1) pin hold across <3 adjustments, (2) auto-expiry on 3rd adjustment with ratchet resume, (3) stale snapshot key pruning keeps active/open strikes and removes orphan keys. |

## Wiring impact

- `mmm_monitor.py` consumes this chunk’s APIs in the heartbeat core:
  - `evaluate_triggers(...)` at `3557` and re-check path at `3803`.
  - `check_frozen_pnl_trigger(...)` fallback at `3568` (only when active outcome is `none`).
  - `update_trigger_snapshots(...)` after adjustments/shift/replenish/scale flows (e.g., `4584`, `5347`, `6239`, `7011`, `7643`).
- `mmm_reversal.py` calls `update_trigger_snapshots(...)` in `handle_reversal_skip_transition` (`287`) to reset post-skip baselines.
- `mmm_api.py` calls `update_trigger_snapshots(...)` in manual operator flows (reduce/inject/set-active-strike), so pin/prune semantics affect both automated and manual control-plane paths.

## Validation notes

- Executed:
  - `python3 -m pytest webui/backend/routes/mmm/tests/test_mmm_trigger.py webui/backend/routes/mmm/tests/test_sealed_mmm_trigger.py -q` → `95 passed, 5 warnings`.
- Additional runtime probe:
  - `check_frozen_pnl_trigger(...)` with `min_frozen_trigger_dollar>0` and no losses returned `outcome='none'` with `frozen_triggered=True` (used as evidence for `F03-P3-074`).

## Chunk verdict

- **RISK**
- File status:
  - `mmm_trigger.py` chunk 01 complete.
- Next file dependency note:
  - Continue with `webui/backend/routes/mmm/mmm_trigger.py` chunk 02 (`lines 488–EOF`).
