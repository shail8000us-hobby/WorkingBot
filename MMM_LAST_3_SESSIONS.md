# Last 3 Sessions — Auto-maintained. Full log: mmm_workdone_march.md

---

## 2026-04-27 (rev3) — A11-03: SQLite Concurrency Evaluation + Fix

Evaluated SQLite concurrency at 3–5 session scale. WAL mode + connection-per-call is sound. One gap found and fixed.

- **Gap**: `mmm_ledger._connect()` had no `busy_timeout` — concurrent fill recordings from multiple sessions would fail immediately with `OperationalError: database is locked`. `mmm_storage._get_conn()` already had `busy_timeout=5000`.
- **Fix**: Added `PRAGMA busy_timeout=5000` to `mmm_ledger._connect()`.
- **Verdict**: SQLite WAL mode fully acceptable for 3–5 concurrent sessions. No architectural changes needed.
- **Sealed (#84)**: `TestA1103SQLiteConcurrency` — 3 contracts: ledger has busy_timeout, storage has busy_timeout, 10-thread concurrent fill recording produces zero errors.

**Files:** `mmm_ledger.py`, `test_sealed_audit_fixes.py` | **Tests:** 1684 passed / 0 failed

---

## 2026-04-27 (rev2) — Score Improvement Plan: Remaining Work (Sprints 3–5 + Sealed Tests)

Completed all remaining fixes. 1674 sealed tests pass.

- **A5-05** (`test_sealed_straddle_roll_pure.py`): Added C-SR-1/2/3 — `execute_pure_straddle_roll()` entry-point contracts: expiry auto-close returns True, min_time suppression returns False, zero-spot returns False.
- **A11-02** (`mmm_api_budget.py` — new): `APIRateBudget` token-bucket singleton. `consume(priority='critical')` always True; `consume(priority='normal')` False when budget exhausted. 60 calls/min.
- **Sealed tests** (`test_sealed_audit_fixes.py`): Added `pytestmark = pytest.mark.sealed` + 14 new tests for A3-01, A6-11, A8-02, A7-01 fixes.

**Files:** `test_sealed_straddle_roll_pure.py`, `test_sealed_audit_fixes.py`, `mmm_api_budget.py` | **Tests:** 1674 passed / 0 failed

---

## 2026-04-27 — Score Improvement Plan: Sprints 1–5 (confidence 69 → 80+)

Implemented all Gate A fixes from `MMM_SCORE_IMPROVEMENT_PLAN.md`. 1657 sealed tests pass.

- **A3-01** (`mmm_monitor.py`): Track `_prem_fetch_failures`; after 3 consecutive premium fetch failures, zero `unrealized_pnl` and fire `emit_safety('stale_unrealized_zeroed')` — prevents stale max-loss reads.
- **A5-07** (`mmm_strategy_dispatch.py`, `mmm_monitor.py`): Added `bypass_gamma_guards`, `bypass_itm_guard`, `replenish_at_open_strike` flags to `StrategyHandler`. Replaced 7 inline `== STRADDLE_WITH_ADJUSTMENT_CATEGORY` string checks in monitor with dispatch flag lookups.
- **A6-11/A11-01** (`mmm_state.py`): Gamma limits and lot_velocity_limit now derived from `initial_lots` at session creation (`soft = lots × 250`, `hard = lots × 500`, `emergency = lots × 1000`). Unchanged at default 10 lots; correct at 100 lots.
- **A11-06** (`mmm_state.py`): `HOT_RELOAD_PARAMS` now derived from `PARAM_RULES[k]['hot']` at import time; static set is fallback only.
- **A7-01** (`mmm_ledger.py`, `mmm_watchdog.py`): Added `get_session_open_positions_by_side()` to ledger. Watchdog reconciliation now rebuilds `positions[]` from ledger DB when drift detected, then calls `recompute_side_lots()` — prevents first heartbeat from reverting the correction.
- **A7-04** (`mmm_watchdog.py`): `_build_failed_list()` wrapped in try/except; EXITING stuck Telegram alert always fires.
- **A8-01** (`mmm_executor.py`): Added 2-char random hex nonce to `client_order_id` — eliminates duplicate_coid on concurrent same-side orders.
- **A8-02** (`mmm_fill_sync.py`, `mmm_activity.py`): Guard changed `<= 0` → `< 0` for fill_price. Added `_close_worthless_expiry()` for zero-price settlement fills — books full entry premium as realized P&L and marks position closed.

**Files:** `mmm_monitor.py`, `mmm_strategy_dispatch.py`, `mmm_state.py`, `mmm_ledger.py`, `mmm_watchdog.py`, `mmm_executor.py`, `mmm_fill_sync.py`, `mmm_activity.py` | **Tests:** 1657 passed / 0 failed

