# File Audit Report — `mmm_reversal.py` (chunk 01)

## Metadata

- Phase: `01 — Foundations`
- File: `webui/backend/routes/mmm/mmm_reversal.py`
- Chunk: `1` (`lines 1–EOF`)
- Date: `2026-04-20`
- Auditor: `GitHub Copilot`

## Scope covered

- Line range: `1–EOF`
- Functions/methods in range:
  - `detect_reversal`
  - `is_cooldown_active`
  - `activate_cooldown`
  - `should_skip_reversal_adjustment`
  - `record_reversal`
  - `handle_reversal_skip_transition`

## Function-level results

| Function | Lines | Read keys | Write keys | Side effects | Tests | Status |
|---|---:|---|---|---|---|---|
| `detect_reversal` | ~24–68 | `last_aggressor`, wind-down state | none | info/debug logging | `test_sealed_mmm_reversal.py`, `test_mmm_reversal.py` | PASS |
| `is_cooldown_active` | ~71–109 | `cooldown_active`, `cooldown_until` | may clear cooldown fields on expiry/parse error | info logging | `test_sealed_mmm_reversal.py`, `test_mmm_reversal.py` | RISK |
| `activate_cooldown` | ~112–140 | cooldown flags + params | `cooldown_active`, `cooldown_until` | info/debug logging | `test_sealed_mmm_reversal.py`, `test_mmm_reversal.py` | RISK |
| `should_skip_reversal_adjustment` | ~143–169 | active + total adjustment P&L | return tuple only | none | `test_sealed_mmm_reversal.py`, `test_mmm_reversal.py` | PASS |
| `record_reversal` | ~172–206 | reversal history + adjustment count | `reversal_count`, `reversal_history` | history capping + logging | `test_sealed_mmm_reversal.py`, `test_mmm_reversal.py` | PASS |
| `handle_reversal_skip_transition` | ~209–EOF | aggressor state, trigger snapshots, adjustment history | last aggressor, history, skip counter, trigger baseline preservation | calls `update_trigger_snapshots`, logging | `test_sealed_mmm_reversal.py`, `test_mmm_reversal.py` | PASS |

## Findings

| ID | Severity | Function | Evidence (line range) | Risk | Proposed fix |
|---|---|---|---|---|---|
| F01-P2-015 | P2 | `is_cooldown_active` + `activate_cooldown` | `mmm_reversal.py:85` and `mmm_reversal.py:122` | If `cooldown_active=True` but `cooldown_until=None`, `is_cooldown_active()` returns `False` **without clearing** the active flag, while `activate_cooldown()` refuses to re-activate because it sees `cooldown_active=True`. Probe confirmed this state persists unchanged after both calls. This creates a sticky invalid cooldown state where future cooldowns are silently skipped. | In `is_cooldown_active()`, when `cooldown_until is None`, clear `cooldown_active`/`_cooldown_block_logged` (same cleanup style as parse-error/expired branches) before returning `False`. Add a sealed test asserting re-activation works after this malformed state. |

## Wiring impact

- Upstream callers:
  - `mmm_monitor` invokes reversal detection, cooldown checks, skip gating, and skip-transition handling in live heartbeat flow.
- Downstream effects:
  - Cooldown state governs whether immediate post-reversal hedges are delayed.
  - Skip-transition updates affect trigger baselines and whipsaw/circuit-breaker observability.

## Validation notes

- Tests reviewed for this chunk:
  - `webui/backend/routes/mmm/tests/test_sealed_mmm_reversal.py`
  - `webui/backend/routes/mmm/tests/test_mmm_reversal.py`
- Runtime probe executed:
  - Constructed malformed state (`cooldown_active=True`, `cooldown_until=None`):
    - `is_cooldown_active()` returned `False` but left state unchanged.
    - `activate_cooldown()` then no-op’d, leaving cooldown permanently non-reactivable.
- Contract note:
  - Sealed test prose says I2 should clear cooldown on missing `cooldown_until`, but current assertion set does not enforce cleanup.

## Chunk verdict

- **RISK**
- Next file dependency notes:
  - `mmm_reversal.py` file audit is complete.
  - Continue Phase 01 with `webui/backend/routes/mmm/mmm_strike_shift.py` chunk 01.
