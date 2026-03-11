# MMM Lessons Learned

## [2026-03-10] One-sided exposure after CE fully closed via close-at-5

**What went wrong:**
When all CE positions fell to ≤close_at_threshold (market moved making calls worthless), `_process_close_at_5` closed them all. The code at that point just logged "For now, just log. Full auto-re-entry needs user config." — the session kept running with CE=0 and PE still open. This is a strategy violation: the two sides are meant to offset each other, and running single-sided leaves unlimited loss exposure on the open side.

**Root cause (detection):**
Incomplete feature in `mmm_monitor.py` — the `_process_close_at_5` inner check (`check_side_fully_closed`) had no action, only a log. No pause or alert was triggered.

**Fix applied (detection/reactive):**
Added ONE-SIDE CLOSE GUARD in `mmm_monitor.py` `_heartbeat()`, right after `check_both_sides_closed`. When one side is fully closed but the other has open lots, the session is immediately PAUSED with a critical safety alert.

---

## [2026-03-10] CE positions closed at premium ~38-41 instead of triggering a strike shift (SHIFT-GUARD fix)

**What went wrong:**
In today's session (mmm10mar26-3): CE @ 71200 had premium 38-41 (below shift_threshold=50). During a 30-minute window where PE was slowly rising but not yet hitting its trigger, close-at-5 fired and closed ALL 17 CE lots at 38-41. This left PE open with zero CE hedge. When PE later triggered, there was no CE to shift/sell. PE was closed at 151.5 vs entry 67.5 — a significant loss.

**Root cause:**
`close_at_5` runs unconditionally every heartbeat using bid price, BEFORE trigger evaluation. When CE bid fell below `close_at_threshold` (user had set it higher than default $5 to take profits at ~$40 range), close-at-5 fired. BUT: CE mark price was still slightly above/near shift_threshold ($50). If PE had triggered even once more, `check_shift_needed(ce, mark=42)` → 42 < 50 → SHIFT would have fired, moving CE to a new OTM strike with better premium and keeping both sides hedged.

**The strategy violation:**
Close-at-5 takes profit on the cheap/winning side without checking whether the expensive/losing side still needs coverage. The shift mechanism (which would maintain coverage) only fires on PE trigger, not proactively.

**Fix applied (preventive):**
Added SHIFT-BEFORE-CLOSE GUARD in `_process_close_at_5()` in `mmm_monitor.py`. Before closing any ACTIVE position (original, adjustment, strike_shift type): check if mark premium < shift_threshold AND the other side still has open lots. If so, SKIP this close and log — the position is preserved for the trigger-based shift mechanism.

Does NOT apply to:
- `frozen` type positions (already shifted away, independent risk)
- Wind-down mode (`using_elevated=True`) — let wind-down do its own cleanup

**Prevention rule:**
Whenever close-at-5 would fire on a side below shift_threshold AND the other side is open, the shift mechanism should get priority. The SHIFT-BEFORE-CLOSE guard enforces this. This preserves CE positions as "alive but cheap" so that the next PE trigger produces a proper CE shift rather than leaving CE at zero.

---

## [2026-03-10] MMM Heartbeat Fails 100% — asyncio/eventlet Event Loop Conflict

**Symptom:** Every heartbeat fails. Miss rate 100%. Circuit breaker permanently OPEN. All premiums show "–" in UI. Error in logs: `Heartbeat error: Cannot run the event loop while another loop is running`.

**Root cause:**
`gunicorn_config.py` uses `worker_class = "eventlet"`. Eventlet monkey-patches `threading.Thread` into a greenlet. `MMMMonitor._run_loop()` creates `asyncio.new_event_loop()` and calls `self._loop.run_until_complete(self._heartbeat())`. Inside a greenlet (not a real OS thread), asyncio cannot take over execution because eventlet's hub is already running in that greenlet context.

**Fix applied (mmm_monitor.py `start()` method):**
Use `eventlet.patcher.original('threading').Thread` to get the un-monkey-patched Thread class, creating a real OS thread where asyncio works without conflicts.

```python
try:
    from eventlet.patcher import original as _ep_original
    _RealThread = _ep_original('threading').Thread
except (ImportError, AttributeError):
    _RealThread = threading.Thread
self._thread = _RealThread(target=self._run_loop, name=f"mmm-monitor-{self.session_id}", daemon=True)
```

**Prevention rule:**
When gunicorn uses `worker_class=eventlet`, any background thread that runs `asyncio.run_until_complete()` MUST use `eventlet.patcher.original('threading').Thread`. The monkey-patched `threading.Thread` creates a greenlet, not a real OS thread, causing asyncio conflicts. `_socketio.emit()` from a real OS thread is safe with Flask-SocketIO in eventlet mode.

---

## [2026-03-11] MMM Lot Velocity Limit Too Restrictive

**Symptom:** "LOT VELOCITY LIMIT: 12 lots sold in last 30min (limit: 10)" — algo blocked from trading with max_lots_per_side=100.
**Root cause:** Default `lot_velocity_limit=10` in mmm_state.py was too low. A single strike_shift selling 12 lots instantly exceeded it. Also, `lot_velocity_limit` was missing from `PARAM_RULES` in mmm_config.py, so it couldn't be updated via API.
**Fix:** Changed default to 30. Added `lot_velocity_enabled`, `lot_velocity_limit`, `lot_velocity_window_mins` to PARAM_RULES.
**Prevention rule:** Any new safety parameter added to DEFAULT_PARAMS/HOT_RELOAD_PARAMS MUST also be added to PARAM_RULES, or it becomes un-configurable via the API.

---

## [2026-03-11] Whipsaw False Positive from OPERATOR Injections

**Symptom:** Session auto-pauses with "Whipsaw detected: 3 alternating adjustments" when the last adjustments include operator-injected manual positions.
**Root cause:** Operator manual adjustments (aggressor=OPERATOR) were counted in whipsaw detection alongside algo adjustments. T3-3 pre-filter boosted the consecutive counter, lowering the effective whipsaw limit from 3 to 2. With effective limit 2, OPERATOR→PE appeared "alternating" → false positive.
**Fix:** (1) mmm_safety.py: Filter OPERATOR from history before whipsaw alternation check. (2) mmm_monitor.py: Skip T3-3 pre-filter increment when either aggressor is OPERATOR. (3) mmm_api.py: Resume endpoint clears whipsaw state on both storage AND live monitor session.
**Prevention rule:** Safety detectors that analyze adjustment patterns MUST exclude OPERATOR (manual) entries. Manual rebalancing is not algo whipsaw.

---

## [2026-03-11] Backend Crash from Zombie Gunicorn Processes

**Symptom:** Backend at 97% CPU, health endpoint times out, `launchctl list` shows LastExitStatus=9 (SIGKILL). Multiple PIDs on port 5555. Error: `greenlet.error: Cannot switch to a different thread`.
**Root cause:** Rapid `launchctl stop/start` cycles don't always kill old gunicorn workers. Old zombie workers hold port 5555 resources, and concurrent eventlet hubs from different processes cause cross-thread greenlet switching errors that crash the hub.
**Fix:** Kill all processes on port 5555 (`lsof -ti:5555 | xargs kill -9`) before restarting. Also: don't add `log.warning()` calls at the very start of real OS threads — they fire before the asyncio event loop exists and can trigger eventlet lock contention.
**Prevention rule:** Before restarting the backend, always kill ALL processes on port 5555 first. Use: `lsof -ti:5555 | xargs kill -9; sleep 1; launchctl start com.gridbot.production.webui`.

---

## [2026-03-11] heartbeat_count API Shows 0 — Wrong Attribute Name

**Symptom:** Monitor API endpoint reports `heartbeat_count: 0` even when heartbeats are running.
**Root cause:** API used `getattr(monitor, '_heartbeat_count', 0)` but the actual counter is `session['_heartbeat_counter']` (stored in session dict, not as monitor attribute).
**Fix:** Changed to `monitor.session.get('_heartbeat_counter', 0)` in mmm_api.py.
**Prevention rule:** When reading session-specific counters in API endpoints, check whether the value lives in `monitor.session[...]` vs `monitor._attribute`. Session dict is the source of truth for heartbeat state.

## [2026-03-12] Comprehensive MMM Code Audit — 37 Bugs Found Across 8 Modules

**Scope:** Deep audit of mmm_engine, mmm_trigger, mmm_safety, mmm_close_at_5, mmm_strike_shift, mmm_state, mmm_harvester, mmm_monitor.

**Critical bugs fixed (HIGH severity):**
1. **Engine:** `calculate_standard_loss` trigger defaults to 0 → massive over-hedge. Fix: Early return with incomplete=True when trigger≤0.
2. **Engine:** `reconcile_pnl` formula missing fee subtraction → reconciliation never detects real drift. Fix: `tracked = realized + unrealized - fees`.
3. **Engine:** `calculate_lots_to_sell` forces min 1 lot even when loss=0. Fix: Early return if loss_to_cover≤0.
4. **Trigger:** Frozen loop overwrites active trigger snapshot with 0 (cache miss). Fix: Skip frozen strikes that match active strike + validate return values.
5. **Trigger:** `evaluate_triggers` has no defense against 0-value snapshot → false triggers. Fix: Return NONE when trigger≤0.
6. **Safety:** `max_loss_amount ≤ 0` triggers instant auto-close. Fix: Early return if max_loss≤0.
7. **Safety:** Whipsaw infinite pause loop (counter never reset, re-triggers on same history). Fix: Reset counter + record checked_up_to.
8. **Safety:** Peak PnL decay at 10%/heartbeat nullifies trailing stop in <2 min. Fix: Time-based decay with 15-min half-life.
9. **Safety:** Lot velocity counts OPERATOR lots, blocking algo hedging for 30min. Fix: Skip OPERATOR entries.
10. **Close-at-5:** Fallback original removal reverted by recompute_side_lots. Fix: Also mark position in positions[].
11. **Strike shift:** Dynamic threshold collapses after first shift (original_premium→0). Fix: Persistent `_initial_hedge_premium`.
12. **Monitor:** `_interruptible_sleep` doesn't exist → storage failure kills session permanently. Fix: Use `_wait_for_next_cycle`.
13. **Monitor:** resume() doesn't clear stale margin flags → false wind-down after resume. Fix: Pop margin flags.
14. **Monitor:** `_make_fetch_fn` returns 0 on cache miss → hides losses. Fix: Return None.
15. **Monitor:** `_bid_cache` accumulates stale entries across heartbeats. Fix: Fresh dict each beat.
16. **State:** Bare dict access `orig_pos['lots']` → KeyError crash on corrupted data. Fix: `.get('lots', 0)`.
17. **Harvester:** `other_lots==0` disables M3 boost in worst-case (one-sided accumulation). Fix: Enable extreme boost.

**Prevention rules:**
- Always use `.get()` with defaults — never bare dict access in state management code
- Cache miss must return None/sentinel, never 0 (0 is a valid value that hides errors)
- Safety checks must handle misconfigured thresholds (≤0) gracefully
- Any counter used for re-trigger detection must be reset when the trigger fires
- Derived state fields (original_premium) that get zeroed by recompute need persistent backups (_initial_hedge_premium)

### Round 2 Audit Fixes (2026-03-11) — 15 bugs across 6 files

**close_at_5.py (5 fixes):**
18. Profit calc in scan missing `× LOT_SIZE_BTC` → 1000x inflated sort priority. Fix: Add multiplier at all 3 scan locations.
19. `_being_closed` guard only worked for pos_id path → adjustment/frozen positions could double-buyback. Fix: Content-match guard + propagate flag through recompute views.
20. No double-close guard when pos_id is falsy (pre-migration). Fix: Content-match on adjustment_fills/frozen_positions views.
21. External close records `realized_pnl: 0.0` → PnL drift. Fix: Estimate from entry_premium - current_premium.
22. None premium from fetch could trigger comparison crash. Fix: Guard `if current is None: continue` in adj/frozen scan loops.

**mmm_state.py (3 fixes):**
23. `recompute_side_lots` uses `next()` for original — silently drops lots from 2nd+ original. Fix: Sum all active originals + warning log.
24. `_being_closed` flag not propagated to adjustment_fills/frozen_positions views. Fix: Include in view dict comprehensions.
25. `close_at_use_bid` missing from HOT_RELOAD_PARAMS. Fix: Add to set.

**mmm_strike_shift.py (3 fixes):**
26. `freeze_current_positions` doesn't clear old strike's trigger_snapshot → stale data on shift-back. Fix: Pop old key.
27. `find_new_strike` allows shift-back to frozen strike → duplicate positions. Fix: Skip frozen strikes in candidate filter.
28. Missing `frozen_entry` in freeze return dict (promised by docstring). Fix: Compute lot-weighted avg premium.

**mmm_safety.py (1 fix):**
29. perp_pnl missing from 80% warning details (was only in CRITICAL). Fix: Add to alert-level details dict.

**mmm_harvester.py (2 fixes):**
30. `total_lots` used for asymmetry calc inflated by frozen. Fix: Use `active_lots`.
31. Capacity pressure includes frozen lots. Fix: Use `active_lots` for pressure calculation.

**mmm_monitor.py (1 fix):**
32. No re-entrancy guard on `_heartbeat()` — overlapping heartbeats possible. Fix: Boolean flag + wrapper/inner split.

**Prevention rules (added):**
- Scan profit calculations must match actual execution formula (both need `× LOT_SIZE_BTC`)
- In-flight guards (`_being_closed`) must work on ALL position types, not just ID-based paths
- View dicts rebuilt by recompute must propagate ALL transient flags from source positions[]
- HOT_RELOAD_PARAMS must be updated when adding new runtime-tunable params
- Strike shift must check frozen strikes to prevent duplicate positions at same strike
- Active-vs-total lot distinction matters: asymmetry/capacity should use active_lots only

---

## [2026-03-11] OPTIONS Positions Endpoint Freezes Single Eventlet Worker — Session Creation Blocked

**Symptom:** User clicks "+ New Session" — nothing happens. Globe stays green (WebSocket alive) but all HTTP requests (health check, session creation, everything) time out for 12-15 seconds every ~13s. Logs show repeated `"Failed to fetch options positions: "` (empty exception = `concurrent.futures.TimeoutError`) alternating with `"Failed to get positions from API: Read timed out (10s)"`.

**Root cause:**
`options_client.py` `_run_async()` called `asyncio.run_coroutine_threadsafe(coro, loop)` then `future.result(timeout=60)`. With `gunicorn worker_class=eventlet`, the Flask request handler is an eventlet greenlet. `future.result(timeout=60)` uses `threading.Condition.wait()` (eventlet-patched). The patched wait is supposed to yield, but `concurrent.futures.Future` synchronization does NOT properly cooperate with eventlet's hub — the greenlet FREEZES for the full duration of the async API call (12-15 seconds). With `workers=1`, the ENTIRE backend becomes unresponsive for that duration. New session creation requests queue up and time out silently.

Secondary problem: `_get_dedicated_loop()` used `threading.Thread` (monkey-patched → eventlet greenlet) to host the asyncio event loop. An asyncio loop running inside an eventlet greenlet has I/O selector conflicts that can cause the loop to stall under load.

**Fix applied (options_client.py):**

1. `_get_dedicated_loop()` — use a **real OS thread** for the asyncio loop:
```python
from eventlet.patcher import original as _orig
_RealThread = _orig('threading').Thread
_loop_thread = _RealThread(target=_dedicated_loop.run_forever, daemon=True, ...)
```

2. `_run_async()` — replace blocking `future.result()` with **cooperative polling**:
```python
future = asyncio.run_coroutine_threadsafe(coro, loop)
deadline = time.time() + 60
while not future.done():
    if time.time() >= deadline:
        future.cancel()
        raise TimeoutError("Async operation timed out after 60s")
    eventlet.sleep(0)   # yield to hub each iteration
return future.result(timeout=0)  # already done — returns immediately
```
`eventlet.sleep(0)` yields the greenlet on every iteration, allowing the eventlet hub to serve health checks, session creation, and WebSocket heartbeats while the async API call is in flight. Because the asyncio loop IS in a real OS thread, `future.done()` becomes True when the coroutine completes, and the poll loop exits naturally.

3. `options_control.py` — added one-at-a-time fetch lock (`_positions_fetch_lock`) with double-checked caching to prevent thundering herd when cache expires:
```python
# Fast path (no lock)
if cache is fresh: return cached_data
# Slow path — serialize all concurrent cache-miss requests
with _positions_fetch_lock:
    if cache is now fresh (another greenlet fetched): return cached_data
    options = _run_async(fetch())  # only ONE call in flight at a time
```

**Verified:** After fix, `health: OK in 0.05s` and `sessions: OK in 0.04s` while `positions` live-fetches from Delta Exchange (`OK in 1.08s`). Previously those would time out for 12-15 seconds.

**Prevention rule:**
NEVER call `future.result()` (blocking) from an eventlet greenlet — even with eventlet's monkey-patched `threading.Condition`, cross-thread notification between a real OS thread (asyncio loop) and a greenlet (Flask request handler) does NOT propagate correctly. Always use `eventlet.sleep(0)` polling OR run the entire async operation in the real OS thread used by the dedicated asyncio event loop.

---

## [2026-03-11] Watchdog restart race condition — orphaned exchange positions

**What went wrong:**
PE showed 0 lots in MMM but exchange had 38 PE lots at strike 69600. During a watchdog restart at 09:49, the old monitor was mid-way through a PE strike shift (69400→69600). The watchdog called `stop()` (setting `_save_disabled=True`), then spawned a new monitor from persisted storage. But the old monitor's async `_process_strike_shift` completed AFTER `stop()` — the order was placed on exchange (38 lots PE at 69600), `activate_new_strike()` updated in-memory state, but `_save_my_session()` was blocked by `_save_disabled`. The new monitor loaded the pre-shift state from storage (PE at 69400) and never knew about the PE at 69600.

**Root cause (two cascading bugs):**
1. **No pre-order guard in `_process_strike_shift`**: Exchange-mutating operations (sell orders) executed even after `stop()` set `_running=False` and `_save_disabled=True`. The async operation was already in flight and couldn't be cancelled by the flag check.
2. **Reconciliation blind spot**: `_reconcile_exchange_positions()` builds `session_symbols` only from known strikes. P-BTC-69600 wasn't in `session_symbols` because the session didn't know about 69600. The isolation filter `if symbol not in session_symbols: continue` excluded the orphan completely. The "UNTRACKED_EXCHANGE_POSITION" detection (which iterates `exchange_positions`) was effectively dead code — it could only find positions already in the filtered `exchange_positions` dict, which by definition are already at known strikes.

**Fixes applied:**
1. **Guard in `_process_strike_shift`** (`mmm_monitor.py`): Before placing the sell order, check `if not self._running or session.get('_save_disabled')` → abort the shift and unfreeze positions. Prevents orphaned exchange orders.
2. **Broader orphan scan in reconciliation** (`mmm_monitor.py`): Instead of iterating the pre-filtered `exchange_positions`, iterate ALL raw exchange `positions` matching this session's option type prefix and expiry suffix. When untracked positions are found (not owned by other sessions), auto-adopt them into the session with `type='orphan_adopted'`. This recovers from crashed monitors' in-flight shifts.

**Prevention rule:**
Any code that modifies exchange state (placing/cancelling orders) MUST check `self._running` and `_save_disabled` immediately before the exchange call. If the monitor has been stopped, abort and unfreeze — the new monitor will detect the condition and retry. Reconciliation must scan ALL exchange positions matching the session's expiry, not just those at known strikes.

---

## [2026-03-11] WebUI performance regression — eventlet worker blocking & CPU spin

**What went wrong:**
WebUI became completely unresponsive. `/api/health` took 6.7s (should be 2ms). `/api/options/positions` timed out entirely (0 bytes in 8s). All endpoints were slow because requests queued behind a blocked worker.

**Root causes:**
1. **`_run_async()` 90-second timeout**: In `options_client.py`, the cooperative polling loop waited up to 90s for exchange API responses. During this time, it held `_positions_fetch_lock`, blocking all other position requests.
2. **CPU spin from `eventlet.sleep(0)`**: The polling loop called `_yield(0)` (yield immediately) millions of times per second, consuming 94% CPU even while waiting for a response.
3. **HTTP self-referencing calls**: `sl_tp_monitor`, `take_profit_manager`, and `max_loss_manager` all made internal HTTP requests to `http://localhost:5555/api/options/positions`. With a single eventlet worker, these self-calls competed with the same worker already handling the request — causing cascading timeouts and potential deadlocks.

**Fixes applied:**
1. **Reduced `_run_async` timeout** (`options_client.py`): 90s → 20s, made configurable via parameter.
2. **Added 10ms sleep** (`options_client.py`): `_yield(0)` → `_yield(0.01)`. CPU dropped from 94% → 0.2%.
3. **Created `get_cached_positions()` helper** (`options_control.py`): Returns cached positions directly for background monitors — zero network overhead, zero deadlock risk.
4. **Eliminated HTTP self-calls**: `sl_tp_monitor`, `take_profit_manager`, `max_loss_manager` now use `get_cached_positions(max_age=30)` instead of `requests.get("http://localhost:5555/api/options/positions")`.

**Prevention rule:**
Background monitors must NEVER make HTTP requests to localhost:5555 — use shared cache or direct function calls instead. Polling loops with `eventlet.sleep()` should always use a nonzero sleep (≥10ms) to prevent CPU spin.

---

## [2026-03-11] Heartbeat crash: `pressure_threshold` referenced before assignment

**What went wrong:**
Every heartbeat for session mmm11mar26-2 crashed with `UnboundLocalError: local variable 'pressure_threshold' referenced before assignment` in `mmm_harvester.py`. This prevented reconciliation state from being saved, and prevented the orphan adoption from persisting.

**Root cause:**
In `_compute_asymmetry_overrides()` (mmm_harvester.py), when `other_lots == 0` (the PE side had 0 lots), the code branched to an early-return path at line 64 that used `pressure_threshold` — but this variable was only defined at line 78, AFTER the `if other_lots == 0` block.

**Fix applied:**
Moved `pressure_threshold`, `asym_threshold`, and `base_profit_pct` definitions to BEFORE the `if other_lots == 0` check.

**Prevention rule:**
When adding early-return branches, verify all referenced variables are defined before the branch point. Python does not hoist variable declarations.

---

## [2026-03-11] Orphan scan expiry suffix mismatch (ddmmyyyy vs ddmmyy)

**What went wrong:**
The orphan scan in `_reconcile_exchange_positions()` used `expiry_suffix = f'-{expiry}'` where `expiry` was in ddmmyyyy format (e.g., `11032026`). But Delta Exchange symbols use ddmmyy suffix (e.g., `110326`). The `sym.endswith('-11032026')` check failed for every symbol (`P-BTC-69600-110326`), so ALL orphan candidates were silently filtered out and never adopted.

**Fix applied:**
Added `from .mmm_initializer import expiry_to_symbol_suffix` and converted: `sym_expiry = expiry_to_symbol_suffix(expiry)` → produces `110326` from `11032026`.

**Prevention rule:**
When building or comparing symbol strings, always use `expiry_to_symbol_suffix()` to convert ddmmyyyy → ddmmyy. The session stores ddmmyyyy; symbols use ddmmyy. Never use the raw expiry parameter directly in symbol comparisons.

