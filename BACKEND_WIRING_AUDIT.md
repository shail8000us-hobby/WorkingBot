# MMM Backend Internal Wiring Audit

**Date:** 2026-04-18  
**Scope:** Backend wiring only (no source edits), with explicit trace `route -> service -> executor -> state -> storage -> response` and defect hunt across requested categories.

---

## What was audited

Primary flow files:
- `webui/backend/routes/mmm/mmm_api.py`
- `webui/backend/routes/mmm/mmm_monitor.py`
- `webui/backend/routes/mmm/mmm_executor.py`
- `webui/backend/routes/mmm/mmm_state.py`
- `webui/backend/routes/mmm/mmm_storage.py`

Additional wiring-critical files:
- `webui/backend/routes/mmm/mmm_strategy_dispatch.py`
- `webui/backend/routes/mmm/mmm_straddle_roll_pure.py`
- `webui/backend/routes/mmm/mmm_exit_all.py`
- `webui/backend/routes/mmm/mmm_watchdog.py`
- `webui/backend/routes/mmm/mmm_guardian.py`
- `webui/backend/routes/mmm/mmm_close_at_5.py`
- `webui/backend/routes/mmm/mmm_straddle_adjustment.py`

Static wiring checks run:
- Route registry scan in `mmm_api.py`: **90 route decorators**, **0 duplicate path+method registrations**.
- Import graph scan over MMM modules: **53 modules**, **215 internal import edges**, **3 strongly connected cycles**.
- Broad swallow scan on core files (`mmm_api.py`, `mmm_monitor.py`, `mmm_executor.py`, `mmm_storage.py`, `mmm_state.py`): **100** `except Exception: pass` matches.

---

## Route → Service → Executor → State → Storage → Response trace

### Flow A — Session create

1. **Route**: `POST /api/mmm/session/create` in `mmm_api.py:290-291` (`create_session_endpoint`).
2. **Service/state construction**: calls `create_session(mode=..., params=...)` in `mmm_state.py:888+`.
3. **State shaping**: `create_session` builds CE/PE side objects and session defaults (`mmm_state.py:1044+`), strategy identity, params, lifecycle fields.
4. **Storage write**: `storage.save_session(session)` in `mmm_api.py:529`, implemented by `MMMStorage.save_session()` in `mmm_storage.py:612+`.
5. **Response/event**: emits `emit_session_created(...)` at `mmm_api.py:533`, returns `201` with session payload.

### Flow B — Session start (fresh entry path)

1. **Route**: `POST /api/mmm/session/<id>/start` in `mmm_api.py:602+` (`start_session`).
2. **Storage status pre-write**: sets `strategy_status='STARTING'` (`mmm_api.py:691+`).
3. **Background service**: starts thread target `_execute_entry_background` (`mmm_api.py:704`, def at `918+`).
4. **Executor**: `_execute_entry_background` invokes `executor.execute_entry(...)` (`mmm_api.py:934`), implemented in `mmm_executor.py:1209+`, which runs concurrent `smart_execute(...)` legs.
5. **State mutation**: on success, writes CE/PE fill prices, trigger snapshots, premiums, `strategy_status='RUNNING'` in `_execute_entry_background` (`mmm_api.py:1050+`).
6. **Monitor/service handoff**: starts monitor via `start_session_monitor(...)` (`mmm_api.py:1174`).
7. **Monitor runtime loop**: `MMMMonitor._run_loop()` (`mmm_monitor.py:1051+`) reloads state from storage (`1088`), runs heartbeat (`1233`).
8. **Storage persistence loop**: monitor save path `MMMMonitor._save_my_session()` -> module `_save_session(...)` (`mmm_monitor.py:11461+`) -> `storage.save_session(session)` (`11578`).
9. **Response**: initial route returns immediately with `STARTING` (`mmm_api.py:712+`) while execution is async.

### Flow C — Params hot reload

1. **Route**: `PATCH /api/mmm/session/<id>/params` in `mmm_api.py:2463+`.
2. **Validation/service**: validates and merges params (`validate_params`, hot-reload policy).
3. **Storage write**: `storage.update_session(session_id, session_updates)` (`mmm_api.py:2698`) via `mmm_storage.py:831+`.
4. **Response/event**: emits `emit_params_changed(...)`, returns changed keys.
5. **Runtime consumption**: monitor picks params on next cycle via `fresh_session = storage.get_session(...)` (`mmm_monitor.py:1088`) before heartbeat.

### Flow D — Stop session

1. **Route**: `POST /api/mmm/session/<id>/stop` in `mmm_api.py:1650+`.
2. **Storage pre-write**: sets `STOPPED` and stop metadata via `update_session` (`mmm_api.py:1685+`).
3. **Service stop**: `stop_session_monitor(...)` (`mmm_api.py:1697`) -> `MMMMonitor.stop(...)` (`mmm_monitor.py:549+`).
4. **State persistence**: monitor `stop()` writes final in-memory state via `_save_my_session()` (`mmm_monitor.py:662`) then sets `_save_disabled`.
5. **Storage finalization**: route recomputes ledger net pnl and calls `update_session(..., {'net_pnl': ...})` (`mmm_api.py:1711+`).
6. **Response**: JSON success + reason.

### Flow E — Exit all / Kill switch

1. **Routes**:
   - `POST /session/<id>/exit_all` (`mmm_api.py:1757+`)
   - `POST /session/<id>/kill_switch` (`mmm_api.py:1883+`)
2. **Storage status transition**: both write `strategy_status='EXITING'` and exit markers (`mmm_api.py:1818`, `1954`).
3. **Service trigger**: if monitor exists, `monitor.force_heartbeat()` (`mmm_api.py:1829`, `1970`).
4. **Monitor gate**: `_heartbeat_inner()` branches early when status is `EXITING` to `run_exit_all(self)` (`mmm_monitor.py` near EXITING gate).
5. **Exit service**: `run_exit_all` in `mmm_exit_all.py:59+` closes reverse/perp/options, then always `monitor.stop(...)` (`mmm_exit_all.py:201`).
6. **Persistence**: stop path + post-stop safety update (`mmm_exit_all.py:214+`).
7. **Response**: route returns `202` async accepted.

---

## Findings by required defect category

## 1) Unreachable functions

### F-UNR-1 (LOW): dead reconciliation helpers in monitor

- `MMMMonitor._auto_correct_lot_mismatch` defined at `mmm_monitor.py:8855`.
- `MMMMonitor._auto_correct_frozen_mismatch` defined at `mmm_monitor.py:8914`.
- Workspace usage scan found no call sites beyond their own definitions.

**Impact:** dead code surface increases maintenance ambiguity and can mislead responders during incidents.

---

## 2) Duplicate handlers

### F-DUP-0 (INFO): no duplicate route+method handlers in `mmm_api.py`

- Route scan result: **0 duplicates** across **90** decorators.

**Impact:** none detected in this category.

---

## 3) Wrong imports

### F-IMP-1 (CRITICAL): invalid `_auto_close_all` import in STRADDLE_ROLL emergency/expiry paths

Evidence:
- `mmm_straddle_roll_pure.py:887` and `:922` import `from .mmm_monitor import _auto_close_all`.
- Calls at `:888` and `:923` invoke `_auto_close_all(monitor, session, sid, reason=...)`.
- In `mmm_monitor.py`, `_auto_close_all` is an **instance method**: `async def _auto_close_all(self, ...)` at `:8103`; there is no matching module-level symbol with that signature.

Failure behavior:
- Import/call wrapped in broad `except Exception` fallback (`mmm_straddle_roll_pure.py:889-891`, `:924-925`) and flow continues to `session['strategy_status'] = 'STOPPED'` (`:893`, `:926`).

**Impact:** close-all in these STRADDLE_ROLL fallback branches can silently fail while session transitions to STOPPED.

### F-IMP-2 (MEDIUM): fallback import target ambiguity in API cache import

Evidence:
- Preferred import: `from webui.backend.cache import cache, CACHE_TIMEOUTS` (`mmm_api.py:27`).
- Fallback: `from cache import cache, CACHE_TIMEOUTS` (`mmm_api.py:29`).

**Impact:** in misconfigured PYTHONPATH contexts, fallback can bind wrong module name `cache` or fail unexpectedly.

---

## 4) Circular dependencies

### F-CYC-1 (MEDIUM): `mmm_storage <-> mmm_state`

- `mmm_storage.py:24` imports `derive_strategy_type` from `mmm_state`.
- `mmm_state.py:985` and `:1012` import `get_storage` from `mmm_storage` (function-level).

### F-CYC-2 (MEDIUM): `mmm_close_at_5 -> mmm_guardian -> mmm_straddle_adjustment -> mmm_close_at_5`

- `mmm_close_at_5.py:280` imports guardian.
- `mmm_guardian.py:305` imports `_cleanup_roll_lock` from `mmm_straddle_adjustment`.
- `mmm_straddle_adjustment.py:34` imports `close_position` from `mmm_close_at_5`.

### F-CYC-3 (MEDIUM): `mmm_monitor <-> mmm_watchdog`

- `mmm_monitor.py:588` / `:718` imports watchdog.
- `mmm_watchdog.py:378` imports `start_session_monitor` and monitor registry symbols.

**Impact:** currently mitigated via local/function-level imports, but raises fragility/risk during refactors and incident patches.

---

## 5) Silent exception swallowing

### F-SW-1 (HIGH): broad swallow in STRADDLE_ROLL close fallback

- `mmm_straddle_roll_pure.py:889-891` and `:924-925` swallow close-all failures after invalid import path.

**Impact:** safety-critical close path can fail without hard fail-up behavior.

### F-SW-2 (MEDIUM): pervasive broad swallows in core path modules

- `except Exception: pass` scan count = **100** across `mmm_api.py`, `mmm_monitor.py`, `mmm_executor.py`, `mmm_storage.py`, `mmm_state.py`.

Not all are critical (many telemetry/logging), but aggregate volume makes true failures easier to mask in live operations.

---

## 6) Wrong state transitions

### F-STATE-1 (HIGH): `RUNNING` persisted before monitor start is guaranteed

Representative evidence:
- Start route writes `RUNNING` first: `mmm_api.py:815+`, then calls `start_session_monitor(...)` (`:831`).
- `start_session_monitor` can raise validation `ValueError` (`mmm_monitor.py:11306+`).

Additional paths with same pattern:
- `resolve_partial_entry`: writes RUNNING then starts monitor (`mmm_api.py:1275` -> `1293`).
- `_retry_partial_leg_background`: writes RUNNING then starts monitor (`mmm_api.py:1478` -> `1498`) with no outer guard.
- `resume_session`: writes/saves RUNNING (`mmm_api.py:1607`) before fallback `start_session_monitor` (`:1629`).

**Impact:** persisted status can become RUNNING without an active monitor thread.

### F-STATE-2 (MEDIUM): STOPPED status may be set even when close-all fallback failed

- In STRADDLE_ROLL fallback branches, exceptions in close-all call are swallowed, yet `strategy_status='STOPPED'` is set (`mmm_straddle_roll_pure.py:893`, `:926`).

---

## 7) Missing validation

### F-VAL-1 (HIGH): storage update result is not validated in many routes

- `MMMStorage.update_session()` returns `Optional[Dict]`, returns `None` on failure (`mmm_storage.py:831+`, failure return `:936`).
- Numerous API call sites ignore return and continue success flow (examples):
  - `mmm_api.py:691`, `:815`, `:1534`, `:1685`, `:1711`, `:1818`, `:1954`, `:2698`, `:7208`, `:8461`, `:8505`, `:8553`.

**Impact:** API can report success while DB write failed.

### F-VAL-2 (MEDIUM): exit initiation does not validate monitor availability for async execution path

- `exit_all`/`kill_switch` write `EXITING` and return `202` even when `get_monitor(session_id)` is `None` (`mmm_api.py:1823+`, `:1964+` guard only for force_heartbeat).

**Impact:** async exit may never execute if no live monitor resumes the flow.

---

## 8) Dangerous fallback logic

### F-FB-1 (HIGH): premium fetch exception path treats stale data as fresh (`ok=True`)

- In `_fetch_premiums_with_fallback`, exception branch returns last-known-good with success flag true (`mmm_monitor.py:10045-10046`).

**Impact:** heartbeat may proceed with adjustment logic on stale prices as if live.

### F-FB-2 (HIGH): guardian check fail-open defaults to GO

- `_check_guardian_signal()` catches any exception and returns `'GO'` (`mmm_api.py:135-141`).

**Impact:** global trading gate can be bypassed by guardian subsystem failure.

### F-FB-3 (MEDIUM): margin guardian explicitly fail-open on check failure

- `_check_margin_guardian()` returns `None` on exception with “intentional fail-open design” (`mmm_monitor.py:8640-8644`).

**Impact:** margin safety layer can silently drop out during transient failures.

### F-FB-4 (MEDIUM): pure straddle dispatch masks execution failure

- `_run_step_5_4_straddle_roll` catches all errors and still `return True` (`mmm_strategy_dispatch.py:183-193`) to skip normal adjustment path.

**Impact:** if pure roll flow fails, fallback adjustment path is also suppressed in that beat.

---

## 9) Partial failure risks

### F-PART-1 (CRITICAL): auto-close partial fill can over-close internal ledger state

Evidence in `_close_one_side`:
- Detects partial active fill: `ac_filled = result.get('filled_size')...` (`mmm_monitor.py:8305`) and logs partial warning (`:8308`).
- Immediately marks **all active positions** closed in loop (`:8353+`) regardless of partial remainder.

Frozen path:
- Uses requested `frozen_lots` in accounting/log (`:8438`) without `filled_size` normalization.

**Impact:** session state can diverge from exchange residual lots after partial fills.

### F-PART-2 (HIGH): treating `no_position_for_reduce_only` as closed without state reconciliation

- Active branch: `no_position_for_reduce_only` treated as success (`mmm_monitor.py:8375+`) but no equivalent explicit position-state close path executed.
- Frozen branch similar handling at `:8457+`.

**Impact:** false-close semantics can leave internal/external mismatch unresolved.

### F-PART-3 (HIGH): stop-after-failure semantics can leave open exchange positions while session is STOPPED

- `_auto_close_all` logs failures, then finally always executes `self.stop(reason)` (`mmm_monitor.py:8164+`, `:8193+` context and final stop).
- `run_exit_all` similarly always terminates through `monitor.stop(...)` (`mmm_exit_all.py:63`, `:201`) with partial flag path.

**Impact:** strategy may be administratively stopped while manual cleanup is still required on exchange.

---

## End-to-end risk summary

- **Critical:** 2
- **High:** 8
- **Medium:** 8
- **Low/Info:** 3

Most severe wiring risks center on:
1. **Invalid import + swallowed exception in STRADDLE_ROLL close paths**.
2. **State transitions set to RUNNING/STOPPED before execution path is guaranteed**.
3. **Partial-fill bookkeeping in auto-close path** causing ledger/exchange divergence.
4. **Fail-open fallbacks** that can continue trading under degraded safety signals.

---

## Recommended remediation order (wiring-first)

1. Fix STRADDLE_ROLL close path import/call contract (`_auto_close_all` binding + signature).
2. Make status transitions transactional with monitor start outcome (start/resume/partial-entry flows).
3. Harden `_close_one_side` for partial fills (`filled_size`-aware state mutation on both active and frozen).
4. Change stale-price exception return in premium fetch to non-trading mode (`ok=False`) unless explicit policy override.
5. Fail-closed (or at least fail-visible) guardian signal handling; avoid blind `'GO'` fallback.
6. Enforce `update_session` result checks in routes before returning success.
7. Remove or wire dead reconciliation helpers to reduce ambiguity.
8. Reduce broad swallow usage in safety-critical branches to targeted exception classes.

---

## Audit constraints and notes

- This was a **read-only backend wiring audit**; no backend source changes were made.
- Findings are evidence-backed from inspected code paths and line references above.
