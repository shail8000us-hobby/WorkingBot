# File Audit Report — `mmm_trigger.py` (chunk 01)

## Metadata

- Phase: `01 — Foundations`
- File: `webui/backend/routes/mmm/mmm_trigger.py`
- Chunk: `1` (`lines 1–450`)
- Date: `2026-04-20`
- Auditor: `GitHub Copilot`

## Scope covered

- Line range: `1–450`
- Functions/methods in range:
  - `evaluate_triggers` (`47–178`)
  - `check_frozen_pnl_trigger` (`181–307`, includes nested `_compute_frozen_loss`)
  - `update_trigger_snapshots` (`309–450` in this chunk; function continues to line ~470)

## Function-level results

| Function | Lines | Read keys | Write keys | Side effects | Tests | Status |
|---|---:|---|---|---|---|---|
| `evaluate_triggers` | 47–178 | `params.min_trigger_move`, `params.min_trigger_dollar`, active strikes, trigger snapshots, active lots | return dict only | warning log on missing/zero snapshot | `test_sealed_mmm_trigger.py`, `test_mmm_trigger.py`, `test_mmm_integration.py` | RISK |
| `check_frozen_pnl_trigger` | 181–307 | frozen positions, trigger snapshots, fetched premiums, `min_frozen_trigger_dollar` | return dict only | warning/info logs, no session mutation | `test_sealed_mmm_trigger.py`, `test_mmm_trigger.py` | PASS |
| `update_trigger_snapshots` (partial) | 309–450 | active strikes, trigger pins, frozen positions, fetched premiums | mutates `session['ce']['trigger_snapshot']`, `session['pe']['trigger_snapshot']` and pin metadata | logs on pin expiry/snapshot failures/pruning | `test_mmm_trigger.py` (partial coverage) | RISK |

## Findings

| ID | Severity | Function | Evidence (line range) | Risk | Proposed fix |
|---|---|---|---|---|---|
| F01-P1-013 | P1 | `update_trigger_snapshots` | `mmm_trigger.py:388,400` | Frozen snapshot update skip uses a cross-side active key set (`{ce_active, pe_active}`), so a CE frozen strike equal to **PE** active strike (or vice versa) is incorrectly skipped. Probe confirmed stale CE frozen snapshot remained unchanged (`before=100.0`, `after=100.0`) when fetch returned a newer value. This can prevent baseline ratcheting and distort incremental frozen-loss logic. | Use side-local active strike gating (`if f_strike_key == side_active_key`) rather than cross-side set membership. Add regression test where one side’s frozen strike equals the opposite side’s active strike. |
| F01-P2-014 | P2 | `evaluate_triggers` | `mmm_trigger.py:107` | Missing/zero snapshot on either side forces global `OUTCOME_NONE`, suppressing valid trigger detection on the other side. Probe confirmed PE-side +30% condition was ignored when CE snapshot was missing (`outcome=none`, `pe_triggered=False`). This is a deliberate safety guard but creates one-side blindness under partial-data conditions. | Preserve guard intent while evaluating sides independently: disable only the invalid side, evaluate valid side normally, and emit a data-quality flag/event to surface degraded state. |

## Wiring impact

- Upstream callers:
  - `mmm_monitor` uses `evaluate_triggers`, then fallback `check_frozen_pnl_trigger`, then `update_trigger_snapshots` after adjustments.
- Downstream behavior:
  - Trigger outcome directly controls aggressor selection, reversal/cooldown flow, and hedge placement cadence.
  - Snapshot ratcheting quality determines whether frozen-loss accounting is incremental vs re-counted.

## Validation notes

- Tests reviewed for this chunk:
  - `webui/backend/routes/mmm/tests/test_sealed_mmm_trigger.py`
  - `webui/backend/routes/mmm/tests/test_mmm_trigger.py`
  - `webui/backend/routes/mmm/tests/test_mmm_integration.py` (trigger smoke)
- Runtime probes executed:
  - One-side snapshot-missing probe: valid PE trigger was suppressed due global guard.
  - Cross-side active-key collision probe: CE frozen snapshot update skipped when frozen strike matched PE active strike.
- Coverage gap identified:
  - No test currently guards the cross-side active-key collision scenario in `update_trigger_snapshots`.

## Chunk verdict

- **RISK**
- Next chunk dependency notes:
  - Continue `mmm_trigger.py` chunk 02 (`line 451 onward`) to complete acceleration/adaptive interval v1/v2 audit and sealed contract verification.
