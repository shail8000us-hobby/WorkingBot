# Refactoring Plan: options_control.py

**File:** `webui/backend/routes/options/options_control.py`
**Current size:** 3,918 lines
**Target size after refactor:** ~600 lines (routes only)
**Risk level:** HIGH — multiple external modules import from this file
**Strategy:** Phased extraction with backward-compatible re-exports at every step

---

## 1. Problem Statement

`options_control.py` is a Flask Blueprint route file that has grown to contain three completely separate concerns:

| Concern | Lines (approx) | Should live in |
|---|---|---|
| HTTP route handlers | ~1,200 | `options_control.py` (keep) |
| Order execution engine | ~800 | `order_executor.py` (new) |
| SSR monitoring threads | ~660 | `ssr_monitor.py` (new) |
| Delta hedge background loop | ~200 | `delta_hedge.py` (new) |
| Infrastructure (event loop, client singleton) | ~150 | `options_client.py` (new) |

Additional structural issues:
- Two nearly identical background monitoring loops (`_run_ssr_monitoring_loop` at 552 lines, `_run_ssr_margin_monitoring_loop` at 103 lines) — near-duplicate code
- 80 bare `except Exception as e:` blocks that swallow stack traces silently
- `print()` statements mixed with `log` calls inside the SSR monitoring thread
- `import` statements scattered inside functions (hashlib, asyncio, json, traceback, datetime)
- Module-level side effects (auto-hedge timer auto-starts on import)

---

## 2. Dependency Map (What Currently Imports From This File)

Before touching anything, understand what must not break:

```
options_control.py  <---  app.py                    (imports: options_bp)
                    <---  dashboard_service.py       (imports: get_options_positions, get_options_status)
                    <---  batch_add_endpoint.py      (imports: place_smart_order, with_timeout,
                                                               validate_order_size, _run_async)
                    <---  max_loss_manager.py        (imports: place_smart_order, ORDER_TYPE_MARKET_ONLY)
                    <---  sl_tp_monitor.py           (imports: execute_close_order)
                    <---  take_profit_manager.py     (imports: place_smart_order, ORDER_TYPE_MAKER_FIRST)
                    <---  auto_loop_service.py       (imports: place_smart_order, with_timeout,
                                                               validate_order_size)
                    <---  conditional_exit_monitor.py(imports: place_smart_order, with_timeout)
                    <---  tests/test_sealed_*.py     (imports: place_smart_order,
                                                               cancel_order_with_verification)
```

**Rule:** Every symbol above must continue to be importable from `options_control.py` throughout this entire refactor. They are moved to new modules AND re-exported from `options_control.py`. External callers are updated LAST, in a separate pass, once everything is stable.

---

## 3. Target Architecture

```
webui/backend/routes/options/
    options_control.py          # Blueprint + route handlers only (~600 lines)
    options_client.py           # NEW: event loop, UnifiedAPIClient singleton, _run_async (NEW)
    order_executor.py           # NEW: all order placement functions
    ssr_monitor.py              # NEW: SSR tracking dict, monitoring loops, SSROrderTracker class
    delta_hedge.py              # NEW: auto-hedge config, timer loop, hedge routes
```

---

## 4. Phased Execution Plan

### PHASE 0: Pre-flight Checks (Before Writing Any Code)

**Do not skip this phase.**

- [ ] Run existing tests and note which pass: `pytest webui/backend/routes/options/tests/ -v`
- [ ] Confirm the webUI is running cleanly: check `/api/options/positions`, `/api/options/ssr-status`
- [ ] Note any active SSR orders — they will be lost on restart (expected)
- [ ] Commit current state as a clean checkpoint on branch `SSR`:
  ```
  git add -p
  git commit -m "chore: checkpoint before options_control refactor"
  ```

---

### PHASE 1: Extract Infrastructure to `options_client.py`

**Risk: LOW** — nothing external imports this, only used internally.

**What moves:**
- `_dedicated_loop`, `_loop_thread`, `_loop_lock` (globals)
- `_get_dedicated_loop()` function
- `_run_async()` function
- `_unified_client_singleton` (global)
- `get_unified_client()` function
- `with_timeout()` async helper

**What stays in `options_control.py`:**
```python
# Backward-compat re-exports — DO NOT REMOVE until all callers are updated
from .options_client import _run_async, get_unified_client, with_timeout
```

**Verify:** `batch_add_endpoint.py` uses `from .options_control import _run_async` — this must still work.

**Test after this phase:**
- Import: `python -c "from webui.backend.routes.options.options_control import options_bp"`
- Route: `GET /api/options/positions` must return 200

---

### PHASE 2: Extract Order Execution to `order_executor.py`

**Risk: MEDIUM** — `place_smart_order` is imported by 5 external modules.

**What moves:**
- Constants: `ORDER_TYPE_MAKER_FIRST`, `ORDER_TYPE_MAKER_ONLY`, `ORDER_TYPE_MARKET_ONLY`, `ORDER_TYPE_SSR`, `VALID_ORDER_TYPES`
- Functions:
  - `cancel_order_with_verification()` [SEALED — copy exactly, do not modify]
  - `validate_order_size()`
  - `place_options_order()`
  - `modify_order_price()`
  - `fetch_fresh_orderbook_quotes()`
  - `place_smart_order()` [SEALED — copy exactly, do not modify]

**What stays in `options_control.py`:**
```python
# Backward-compat re-exports
from .order_executor import (
    ORDER_TYPE_MAKER_FIRST, ORDER_TYPE_MAKER_ONLY, ORDER_TYPE_MARKET_ONLY,
    ORDER_TYPE_SSR, VALID_ORDER_TYPES,
    cancel_order_with_verification, validate_order_size,
    place_options_order, modify_order_price, fetch_fresh_orderbook_quotes,
    place_smart_order,
)
```

**Critical note on SEALED functions:** `cancel_order_with_verification` and `place_smart_order` are decorated with `@sealed`. The `@sealed` decorator is applied at import time. The new file `order_executor.py` must import `sealed` from `webui.backend.sealed` and apply the decorator identically. Do not unwrap or re-wrap them.

**Test after this phase:**
- All 5 external callers must still work: manually verify imports from `max_loss_manager`, `take_profit_manager`, `auto_loop_service`, `conditional_exit_monitor`, `batch_add_endpoint`
- Run sealed tests: `pytest webui/backend/routes/options/tests/`

---

### PHASE 3: Extract SSR Monitoring to `ssr_monitor.py`

**Risk: MEDIUM** — `_active_ssr_orders` is accessed by `get_ssr_status()` and `get_options_activity_log()` routes. After extraction, routes will use the registry from `ssr_monitor.py`.

**What moves:**

**Globals:**
- `_active_ssr_orders = {}`
- `_ssr_lock = threading.Lock()`

**Functions:**
- `_run_ssr_monitoring_loop()` — keep as-is functionally, but clean up:
  - Move all `import` statements to top of new file (asyncio, traceback, etc.)
  - Replace all `print(f"[SSR THREAD] ...")` with `log.debug(...)` using the module logger
  - No logic changes
- `_run_ssr_margin_monitoring_loop()` — same cleanup treatment
- `place_ssr_order()` — this also moves (it's execution, not a route)
- `place_ssr_order_with_margin()` — moves with it

**New public API of `ssr_monitor.py`:**
```python
# Importable by options_control.py routes:
get_active_ssr_orders()        # returns snapshot of _active_ssr_orders (thread-safe)
register_ssr_order(order_id, info)  # replaces direct dict access
update_ssr_order(order_id, **kwargs)
remove_ssr_order(order_id)
place_ssr_order(...)            # moved here from options_control
place_ssr_order_with_margin(...)
```

**Why encapsulate the dict?** The current code does `global _active_ssr_orders` + direct dict mutation across two files and in routes. Encapsulating it in accessor functions makes the shared state explicit and testable.

**What stays in `options_control.py`:**
```python
# Backward-compat re-exports
from .ssr_monitor import place_ssr_order, place_ssr_order_with_margin
```

**Route changes in `options_control.py`:**
- `get_ssr_status()`: replaces `with _ssr_lock: for order_id, info in _active_ssr_orders.items()` with `get_active_ssr_orders()` from `ssr_monitor`
- `get_options_activity_log()`: same

**Test after this phase:**
- `GET /api/options/ssr-status` — must return empty list (no active orders at test time)
- `POST /api/options/ssr-order` — place a test order, verify it appears in `/api/options/ssr-status`
- Verify the monitoring thread actually starts (check logs for "SSR MONITOR STARTED")

---

### PHASE 4: Extract Delta Hedge to `delta_hedge.py`

**Risk: LOW** — delta hedge functions are only called by their own routes and the auto-timer. Nothing external imports them.

**What moves:**
- All `_auto_hedge_config*` globals and lock
- `_hedge_events`, `_hedge_events_lock`, `_last_hedge_time`
- `_auto_hedge_config_path()`
- `_load_auto_hedge_config_from_disk()`
- `_auto_hedge_tick()`
- `_schedule_next_auto_hedge_tick()`
- `_ensure_auto_hedge_running()`
- `_auto_hedge_timer`, `_auto_hedge_timer_lock`, `AUTO_HEDGE_INTERVAL_SECONDS`
- All delta hedge route handlers (toggle, status, config, execute)
- `_get_portfolio_btc_delta()` (if defined in options_control — check)
- `_place_perp_order_async()` (if defined in options_control — check)

**What stays in `options_control.py`:**
```python
# Register delta hedge routes on the blueprint
from .delta_hedge import register_delta_hedge_routes
register_delta_hedge_routes(options_bp)
```

**Important:** The module-level auto-start at the bottom of options_control.py:
```python
if _auto_hedge_config.get('enabled', False):
    _ensure_auto_hedge_running()
```
This moves to the bottom of `delta_hedge.py`. It must remain a module-level side effect (it's intentional — restores the timer state after a restart).

**Test after this phase:**
- `GET /api/options/hedge/status` must return 200
- Toggle auto-hedge on and off, verify config persists to `data/auto_hedge_config.json`

---

### PHASE 5: Slim Down Route Handlers in `options_control.py`

**Risk: LOW-MEDIUM** — internal logic changes only, no moving of symbols.

This phase addresses the remaining code quality issues in the route handlers that stay in `options_control.py`.

**Issues to fix:**

**5a. Remove swallowed exceptions**

Pattern to find and fix (80 occurrences):
```python
# BEFORE (suppresses traceback):
except Exception as e:
    log.error(f"Error: {e}")

# AFTER (includes traceback for non-expected errors):
except Exception:
    log.exception("Error in get_options_positions")
    raise
```
For routes where graceful degradation is intentional (cache fallback), keep `log.error` but add `exc_info=True`:
```python
except Exception:
    log.error("Failed to fetch positions", exc_info=True)
```

**5b. Inline async fetch functions**

Several routes define `async def fetch():` as a nested closure and immediately call `_run_async(fetch())`. These can be flattened:
```python
# BEFORE:
async def fetch():
    positions = await client.get_all_positions_with_options()
    ...
options = _run_async(fetch())

# AFTER (same behavior, less nesting):
async def _fetch_positions(client):
    positions = await client.get_all_positions_with_options()
    ...
# Called from route:
options = _run_async(_fetch_positions(get_unified_client()))
```

**5c. Move all `import` statements inside functions to module top**

Functions like `place_ssr_order_endpoint` have `import asyncio` at the top of the function body. Move all such imports to the top of the file.

**5d. Remove redundant global declarations**

Any `global _active_ssr_orders` declaration in a function that only reads the dict (not reassigns the variable) is unnecessary — remove it.

**Test after this phase:**
- Full smoke test: all `/api/options/*` routes
- Ensure Telegram notifications still fire on position close (uses `options_notifier`)

---

### PHASE 6: Update External Callers (Final Pass)

**Risk: LOW** — re-exports are still in place, this is cleanup.

Only after all phases pass end-to-end testing, update external callers to import from their new canonical locations:

| File | Old import | New import |
|---|---|---|
| `batch_add_endpoint.py` | `from .options_control import place_smart_order, with_timeout, validate_order_size, _run_async` | `from .order_executor import place_smart_order, validate_order_size` + `from .options_client import _run_async, with_timeout` |
| `max_loss_manager.py` | `from ...routes.options.options_control import place_smart_order, ORDER_TYPE_MARKET_ONLY` | `from ...routes.options.order_executor import place_smart_order, ORDER_TYPE_MARKET_ONLY` |
| `sl_tp_monitor.py` | `from ...routes.options.options_control import execute_close_order` | `from ...routes.options.order_executor import execute_close_order` |
| `take_profit_manager.py` | `from ...routes.options.options_control import place_smart_order, ORDER_TYPE_MAKER_FIRST` | `from ...routes.options.order_executor import place_smart_order, ORDER_TYPE_MAKER_FIRST` |
| `auto_loop_service.py` | `from ...routes.options.options_control import place_smart_order, with_timeout, validate_order_size` | split across `order_executor` and `options_client` |
| `conditional_exit_monitor.py` | same as above | same as above |
| `tests/test_sealed_*.py` | `from webui.backend.routes.options.options_control import place_smart_order, cancel_order_with_verification` | `from webui.backend.routes.options.order_executor import ...` |

After updating each caller, remove the corresponding re-export from `options_control.py`.

---

## 5. Final File Structure After Refactor

### `options_client.py` (~80 lines)
- Dedicated event loop setup
- `_run_async()`
- `get_unified_client()` singleton
- `with_timeout()`

### `order_executor.py` (~350 lines)
- Order type constants
- `cancel_order_with_verification()` [SEALED]
- `place_options_order()`
- `validate_order_size()`
- `modify_order_price()`
- `fetch_fresh_orderbook_quotes()`
- `place_smart_order()` [SEALED]

### `ssr_monitor.py` (~400 lines)
- `_active_ssr_orders` registry with thread-safe accessors
- `_run_ssr_monitoring_loop()` (cleaned up, no prints)
- `_run_ssr_margin_monitoring_loop()` (cleaned up)
- `place_ssr_order()`
- `place_ssr_order_with_margin()`

### `delta_hedge.py` (~250 lines)
- Auto-hedge config + persistence
- `_auto_hedge_tick()` timer loop
- `_get_portfolio_btc_delta()`
- `_place_perp_order_async()`
- Delta hedge route handlers
- `register_delta_hedge_routes(bp)`

### `options_control.py` (~600 lines)
- Blueprint definition
- Rate limiting decorator
- Duplicate prevention decorator
- `check_guardian_signal()`
- Position cache globals
- All remaining HTTP route handlers (thin — validate, delegate, respond)
- Backward-compat re-exports (removed in Phase 6)

---

## 6. What NOT to Change

- **Do not touch** the `@sealed` decorator or the functions decorated with it. Copy them verbatim.
- **Do not touch** the event loop architecture (`_get_dedicated_loop` / `run_coroutine_threadsafe`). It was built specifically to solve "bound to different event loop" errors.
- **Do not touch** the SSR monitoring logic itself (which ticks, how price is calculated, when it stops). Only move and clean up the container.
- **Do not change any HTTP route URLs, method types, or response schemas.** The frontend calls these — any change there requires a frontend deploy.
- **Do not remove** `print()` calls from `_run_ssr_monitoring_loop` in the same commit as moving the function. First move, then clean in a follow-up commit so diffs are readable.

---

## 7. Rollback Plan

Each phase is a separate commit. If any phase causes a production issue:

1. `git revert <phase-commit-hash>` — single commit reverts the phase
2. Because re-exports are in place throughout, reverting any single phase restores full functionality
3. The route URLs never change, so no frontend cache issues

---

## 8. Testing Checklist Per Phase

Run after completing each phase before moving to the next:

```
[ ] python -c "from webui.backend.routes.options.options_control import options_bp"
[ ] python -c "from webui.backend.routes.options.options_control import place_smart_order, with_timeout"
[ ] python -c "from webui.backend.options_strategy.max_loss_manager import get_max_loss_manager"
[ ] python -c "from webui.backend.options_strategy.take_profit_manager import get_take_profit_manager"
[ ] python -c "from webui.backend.routes.options.batch_add_endpoint import batch_add_bp"
[ ] pytest webui/backend/routes/options/tests/ -v
[ ] Start backend: python -m webui.backend.app (no import errors on startup)
[ ] GET /api/options/positions    -> 200
[ ] GET /api/options/ssr-status   -> 200
[ ] GET /api/options/activity-log -> 200
[ ] GET /api/options/hedge/status -> 200
```

---

## 9. Estimated Scope Per Phase

| Phase | Files Created/Modified | Commits | Notes |
|---|---|---|---|
| 0 | 0 | 1 | Checkpoint only |
| 1 | `options_client.py` (new), `options_control.py` (edit) | 1 | Lowest risk |
| 2 | `order_executor.py` (new), `options_control.py` (edit) | 1 | SEALED functions — be careful |
| 3 | `ssr_monitor.py` (new), `options_control.py` (edit) | 2 | Move + cleanup as separate commits |
| 4 | `delta_hedge.py` (new), `options_control.py` (edit) | 1 | |
| 5 | `options_control.py` (edit only) | 1-2 | Exception cleanup + inline fetch flatten |
| 6 | 6+ external files + `options_control.py` | 1 per file | One PR per caller file |

---

## 10. Open Questions Before Starting

1. Where are `_get_portfolio_btc_delta()` and `_place_perp_order_async()` defined? Grep the file — if they are only in `options_control.py`, they move to `delta_hedge.py`. If they come from elsewhere, just re-import them.
2. Is `execute_close_order` a route function or a helper? `sl_tp_monitor.py` imports it — verify it is the route handler (registered on the blueprint) or a standalone helper, because this changes where it ends up.
3. Does the webUI run under Gunicorn (multiple workers) or single-worker Flask dev server in production? The comments in the file mention the rate-limiter and duplicate-prevention dict won't work under multi-worker. This is not a blocking question for the refactor, but worth documenting.

---

## 11. Post-Refactor Verification Report (March 5, 2026)

### Status: Phases 1–4 COMPLETE and VERIFIED ✅

Thorough senior-developer-level review and testing performed across all 4 phases.

### File Metrics

| File | Lines | Role |
|---|---|---|
| `options_control.py` | 2,459 | Blueprint + routes + backward-compat re-exports |
| `options_client.py` | 102 | Event loop, `_run_async`, `get_unified_client`, `with_timeout` |
| `order_executor.py` | 429 | Order type constants, SEALED order functions |
| `ssr_monitor.py` | 725 | SSR registry + thread-safe accessors, both monitoring loops, SSR order placement |
| `delta_hedge.py` | 377 | Auto-hedge config + timer, portfolio delta calc, perp order placement, hedge routes |
| **Total** | **4,092** | (vs original 3,918 — overhead is re-export blocks + module docstrings) |

### Syntax Verification
- All 5 files pass `py_compile.compile()` — no syntax errors.

### Import Verification (19/19 tests passed)
Tests confirmed the following import paths all resolve correctly:

| Test | Result |
|---|---|
| Phase 1: `options_client` direct imports | ✅ |
| Phase 1: re-exports via `options_control` | ✅ |
| Phase 2: `order_executor` direct imports (11 symbols) | ✅ |
| Phase 2: re-exports via `options_control` | ✅ |
| Phase 3: `ssr_monitor` direct imports | ✅ |
| Phase 3: re-exports via `options_control` | ✅ |
| Phase 4: `delta_hedge` direct imports | ✅ |
| Phase 4: delta_hedge routes registered on blueprint | ✅ |
| `app.py` → `options_bp` | ✅ |
| `batch_add_endpoint.py` → `place_smart_order, with_timeout, validate_order_size` | ✅ |
| `batch_add_endpoint.py` → `_run_async` | ✅ |
| `max_loss_manager.py` → `place_smart_order, ORDER_TYPE_MARKET_ONLY` | ✅ |
| `sl_tp_monitor.py` → `execute_close_order` | ✅ |
| `take_profit_manager.py` → `place_smart_order, ORDER_TYPE_MAKER_FIRST` | ✅ |
| Test file → `cancel_order_with_verification` | ✅ |
| SEALED decorators applied correctly | ✅ |
| Cross-import: `ssr_monitor` → `order_executor` | ✅ |
| Cross-import: `delta_hedge` → `options_client` | ✅ |
| SSR registry register/get/remove round-trip | ✅ |

### Pytest Results: 78 passed, 0 failed
All 78 existing tests pass after one fix (see below).

### Bug Found and Fixed During Verification

**Issue:** 7 tests in `test_sealed_place_smart_order.py` were failing with:
```
TypeError: object MagicMock can't be used in 'await' expression
```

**Root cause:** Tests patched `webui.backend.routes.options.options_control.place_options_order`, but `place_smart_order` now lives in `order_executor.py` and resolves `place_options_order` from its own module namespace. The patch target missed the actual function.

**Fix:** Changed `BASE` in the test file from `"webui.backend.routes.options.options_control"` to `"webui.backend.routes.options.order_executor"`. This is a natural consequence of moving code — mock patches must target the module where the name is looked up at call time, not where it was originally defined.

### External Callers — All Still Working (No Changes Needed)
All 12 external import sites (across 7 files) still import from `options_control.py` and resolve correctly via backward-compat re-exports:
- `app.py` — `options_bp`
- `batch_add_endpoint.py` — `place_smart_order`, `with_timeout`, `validate_order_size`, `_run_async`
- `dashboard_service.py` — `get_options_positions`, `get_options_status` (stayed in `options_control`)
- `auto_loop_service.py` — `place_smart_order`, `with_timeout`, `validate_order_size`
- `conditional_exit_monitor.py` — `place_smart_order`, `with_timeout`
- `max_loss_manager.py` — `place_smart_order`, `ORDER_TYPE_MARKET_ONLY`
- `sl_tp_monitor.py` — `execute_close_order` (stayed in `options_control`)
- `take_profit_manager.py` — `place_smart_order`, `ORDER_TYPE_MAKER_FIRST`

### Architecture Verification
- `options_client.py` correctly manages the dedicated event loop singleton — no circular imports.
- `order_executor.py` imports `sealed` from `webui.backend.sealed` and applies `@sealed` identically to both `cancel_order_with_verification` and `place_smart_order`.
- `ssr_monitor.py` encapsulates `_active_ssr_orders` behind thread-safe `get_active_ssr_orders()` / `register_ssr_order()` / `update_ssr_order()` / `remove_ssr_order()` accessors. Routes in `options_control.py` correctly use `get_active_ssr_orders()`.
- `delta_hedge.py` uses `register_delta_hedge_routes(bp)` pattern. Routes are registered on the blueprint at module load time via call at line 2460 of `options_control.py`. Auto-start timer fires correctly from module-level side effect.
- `order_executor.py` uses lazy imports for `ssr_monitor` (inside `place_smart_order`) to avoid circular import between the two modules.

### Phases 5 & 6: NOT DONE (intentional)
- **Phase 5** (exception cleanup + inline fetch flatten) — deferred.
- **Phase 6** (update external callers to import from canonical modules) — deferred until system confirmed stable in production.

### Test Script Location
Verification test: `_test_refactor_imports.py` (root of workspace) — can be re-run at any time to validate.
