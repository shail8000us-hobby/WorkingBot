# File Audit Report — `mmm_close_at_5.py` (chunk 01)

## Metadata

- Phase: `01 — Foundations`
- File: `webui/backend/routes/mmm/mmm_close_at_5.py`
- Chunk: `1` (`lines 1–450`)
- Date: `2026-04-20`
- Auditor: `GitHub Copilot`

## Scope covered

- Line range: `1–450`
- Functions/methods in range:
  - `_D`
  - `_check_stale_being_closed`
  - `scan_closeable_positions`
  - `close_position` (entry + guard + market branch segment)

## Function-level results

| Function | Lines | Read keys | Write keys | Side effects | Tests | Status |
|---|---:|---|---|---|---|---|
| `_D` | 21–23 | numeric input | Decimal value | none | Indirect via close P&L arithmetic | PASS |
| `_check_stale_being_closed` | 32–49 | `_being_closed`, `_being_closed_at` | clears stale in-flight flags | log warning on stale auto-clear | `test_sealed_mmm_close_at_5.py` | PASS |
| `scan_closeable_positions` | 52–215 | side ledgers, fills, frozen positions, threshold config | closeable candidate list | log debug/info | `test_mmm_close_at_5.py`, `test_sealed_mmm_close_at_5.py` | RISK |
| `close_position` (partial, incl. market no-ID branch) | 218–450 | session/position payload, guardian+observer checks | in-flight flags, pending verification, state reduction/removal | exchange order placement, logs | same + pure-roll contracts | RISK |

## Findings

| ID | Severity | Function | Evidence (line range) | Risk | Proposed fix |
|---|---|---|---|---|---|
| F01-P2-018 | P2 | `scan_closeable_positions` + `close_position` legacy original flow | `mmm_close_at_5.py:85–117` can emit original close payload with `_pos_id=None`; `mmm_close_at_5.py:333–360` fallback in-flight guard only covers adjustment/frozen views (no original scalar fallback). | In legacy/scalar-only states, duplicate-close suppression is incomplete for original-lot closes if ID linkage is missing. | Add explicit no-ID original guard/marker path (or hard-fail with deterministic repair path) before order placement. |
| F01-P3-019 | P3 | `close_position` market branch contracts | Market path around `mmm_close_at_5.py:410–450` has nuanced semantics (partial fill handling, no-ID failure cleanup, pending-close verification). | Coverage gap risk: subtle regression potential in emergency/hard-stop market flows without direct branch-focused contract tests. | Add dedicated sealed tests for market branch permutations (success/partial/no-ID failure/verification registry). |

## Wiring impact

- Called from monitor close-at-threshold path and from mechanisms that reuse close helper (`harvest`, `recycler`, `wind_down`, emergency exits).
- Guardian/observer integration in this chunk is safety-critical for continuity/velocity gating before buyback execution.

## Validation notes

- Executed:
  - `test_mmm_close_at_5.py`
  - `test_sealed_mmm_close_at_5.py`
- Combined targeted run (with DTE suites) result: `104 passed`.

## Chunk verdict

- **RISK**
- Next chunk dependency notes:
  - Continue `close_position` completion path and helper mutators (`_partial_close_position`, `_remove_closed_position`) in chunk 02.
