# WebUI Speed — Detailed Implementation Plan

**Date:** March 2026
**Goal:** Measurably reduce dashboard load time and Delta Exchange API call frequency
**Approach:** Targeted surgical fixes, no architecture rewrites

---

## The Problem in One Diagram

```
Every 5 seconds (one browser tab open):

FRONTEND
  └─ polls GET /api/options/dashboard
        └─ dashboard.py: _fetch_dashboard_fresh()  [SEQUENTIAL]
              │
              ├─ fetch_options_positions_data()  →  Delta Exchange  ~400ms
              ├─ fetch_pending_orders_data()     →  Delta Exchange  ~300ms
              ├─ fetch_futures_positions_data()  →  Delta Exchange  ~300ms
              ├─ fetch_options_status_data()     →  file read       ~5ms
              └─ fetch_margin_data()             →  Delta Exchange  ~250ms
                                                    TOTAL: ~1,250ms (serial)

SIMULTANEOUSLY (background threads):

  MaxLossMonitor (every 5s)
    └─ requests.get("http://localhost:5555/api/options/positions")
          └─ Flask thread → _run_async → Delta Exchange  ~400ms
              (HTTP loopback through own server = extra 50ms overhead)

  SL/TP Monitor (every 5s)
    └─ loop.run_until_complete(api_client.get_all_positions())  ~400ms

  TakeProfit Monitor (every 3s)
    └─ loop.run_until_complete(api_client.get_all_positions())  ~400ms

TOTAL Delta Exchange calls per 5 seconds: ~7-8 calls, all fetching same positions
```

**Root causes, ranked by impact:**

| # | Root Cause | Calls wasted | Fix complexity |
|---|---|---|---|
| 1 | Dashboard fetches 4 API calls **sequentially** | 0 extra calls, but adds ~800ms latency | Low |
| 2 | MaxLossMonitor fetches via HTTP loopback to self | 1 redundant positions call per 5s | Low |
| 3 | SL/TP + TakeProfit each fetch positions independently | 2 redundant positions calls per ~4s | Medium |
| 4 | Dashboard cache SWR not using HTTP ETag | 0 extra calls but wastes compute on unchanged data | Low |
| 5 | Frontend polls at 5s even when nothing changes | 1 dashboard fetch per 5s minimum | Low |

---

## Fix 1 — Parallelize Dashboard Fetches

**File:** `webui/backend/routes/options/dashboard.py`
**Lines:** 195–199 (the 5 sequential service calls in `_fetch_dashboard_fresh`)
**Effort:** 2 hours
**Expected gain:** Dashboard response time drops from ~1,250ms to ~400ms (fastest of the 4 calls)

### Current code (lines 195–199):
```python
positions_data = fetch_options_positions_data()
pending_data   = fetch_pending_orders_data()
futures_data   = fetch_futures_positions_data()
status_data    = fetch_options_status_data()
margin_data    = fetch_margin_data()
```

These 5 functions are completely independent. They wait for each other for no reason.

### What to add at top of `dashboard.py`:
```python
from concurrent.futures import ThreadPoolExecutor, as_completed
```

### What to replace lines 195–199 with:
```python
# Fetch all data sources concurrently — each submits work to the shared
# async event loop independently, so they run in parallel.
with ThreadPoolExecutor(max_workers=5, thread_name_prefix='dashboard-fetch') as pool:
    f_positions = pool.submit(fetch_options_positions_data)
    f_pending   = pool.submit(fetch_pending_orders_data)
    f_futures   = pool.submit(fetch_futures_positions_data)
    f_status    = pool.submit(fetch_options_status_data)
    f_margin    = pool.submit(fetch_margin_data)

    positions_data = f_positions.result(timeout=20)
    pending_data   = f_pending.result(timeout=20)
    futures_data   = f_futures.result(timeout=20)
    status_data    = f_status.result(timeout=20)
    margin_data    = f_margin.result(timeout=20)
```

### Why this works:
Each service function calls `_run_async(coro)` which submits a coroutine to the shared
dedicated event loop via `run_coroutine_threadsafe`. The event loop can interleave all
5 coroutines cooperatively. The 5 ThreadPoolExecutor threads all unblock as soon as their
coroutine completes. Net wall-clock time = longest single call, not sum of all calls.

### How to verify it worked:
The dashboard response already includes `response_time_ms` in the JSON. Before fix it
should read ~1200–1800ms. After fix it should read ~350–600ms. Check it in browser DevTools
→ Network → `/api/options/dashboard` → Response → `response_time_ms`.

### Risk:
Low. `fetch_pending_orders_data` is SEALED — it is not modified, only called from a thread
instead of directly. The SEALED decorator is on the function definition, not the call site.

---

## Fix 2 — Kill the HTTP Loopback in MaxLossMonitor

**File:** `webui/backend/options_strategy/max_loss_manager.py`
**Lines:** 832–869 (the `if positions is None:` block in `_check_max_loss`)
**Effort:** 1 hour
**Expected gain:** Removes 1 full HTTP round-trip per 5s cycle, frees a Flask worker thread

### Current code (lines 838–845):
```python
response = requests.get(
    "http://localhost:5555/api/options/positions",
    timeout=10
)
```

This is a background thread making an HTTP request to its own Flask server. This:
- Opens a TCP connection to itself
- Consumes a Flask worker thread for the duration
- That Flask thread then calls `_run_async` → Delta Exchange

The `MaxLossMonitor` already has its own internal cache (`self._positions_cache`, TTL-based).
The cache is working — when it hits, positions are fast. The problem is only the cache-miss path.

### The MaxLossMonitor already has `self.api_client` injected
Looking at `__init__` (line ~604): `self.api_client` is available. It's the same
`UnifiedAPIClient` used elsewhere. The HTTP loopback was added to avoid asyncio event loop
issues — but `take_profit_manager.py` solves this correctly with `loop.run_until_complete`.

### What to replace the HTTP loopback with:
```python
# Use api_client directly (same pattern as take_profit_manager.py)
try:
    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

positions_data = loop.run_until_complete(
    self.api_client.get_all_positions_with_options()
)
```

Then update the cache:
```python
with self._cache_lock:
    if isinstance(positions_data, dict):
        self._positions_cache = positions_data.get('options', [])
    self._cache_time = time.time()
positions = self._positions_cache
```

### Also fix the close order loopback (lines 1223–1224 and 1304–1305):
Same pattern — `requests.post("http://localhost:5555/api/options/close", ...)`.
These should call `place_smart_order` directly (it is already importable).

```python
# Replace:
response = requests.post("http://localhost:5555/api/options/close", ...)

# With (already imported at top of file):
from webui.backend.routes.options.options_control import place_smart_order, ORDER_TYPE_MARKET_ONLY
from webui.backend.routes.options.options_control import _run_async
result = _run_async(place_smart_order(
    client=self.api_client,
    symbol=symbol,
    size=size,
    side=side,
    order_preference=ORDER_TYPE_MARKET_ONLY,
    reduce_only=True
))
```

### How to verify:
Check logs — before fix you'll see `MaxLossMonitor: requests.get(...)` TCP connections
in netstat. After fix, no HTTP loopback connections from that monitor.

### Risk:
Medium. The HTTP loopback was deliberately chosen to avoid asyncio issues. Follow the
`take_profit_manager.py` pattern exactly since it already works. Test with a simulated
max loss trigger before deploying.

---

## Fix 3 — Shared Position Cache (Eliminates 3 Redundant Position Fetches)

**New file:** `webui/backend/services/position_cache.py`
**Modified files:** `sl_tp_monitor.py`, `take_profit_manager.py`, `max_loss_manager.py`
**Effort:** 1 day
**Expected gain:** Reduces position API calls from ~5/5s to ~1/5s (80% reduction)

### Create `webui/backend/services/position_cache.py`:

This module provides a process-wide singleton position cache. All three monitors
read from it instead of fetching independently.

```python
"""
Shared position cache — process-wide singleton.

Prevents redundant Delta Exchange position API calls from multiple monitors
(SL/TP, MaxLoss, TakeProfit) that all need the same data.

Cache TTL: 5 seconds (monitors check every 3–5s, so usually 1 real API call per cycle).
"""

import time
import asyncio
import threading
import logging
from typing import Optional, List, Dict

log = logging.getLogger(__name__)

_cache_lock = threading.Lock()
_positions: Optional[List[Dict]] = None
_cache_time: float = 0.0
_CACHE_TTL = 5.0   # seconds — monitors sleep 3–5s so this covers most checks


def get_options_positions(force_refresh: bool = False) -> List[Dict]:
    """
    Return cached options positions. Fetches from Delta Exchange only on cache miss.

    Thread-safe. All three monitors call this instead of fetching independently.

    Args:
        force_refresh: If True, bypass cache and fetch fresh (use sparingly).

    Returns:
        List of position dicts (same format as api_client.get_all_positions_with_options()['options'])
    """
    global _positions, _cache_time

    now = time.time()

    with _cache_lock:
        if not force_refresh and _positions is not None and (now - _cache_time) < _CACHE_TTL:
            log.debug(f"[PositionCache] HIT — {len(_positions)} positions, age={now - _cache_time:.1f}s")
            return list(_positions)

    # Cache miss — fetch fresh
    log.debug("[PositionCache] MISS — fetching from Delta Exchange")
    positions = _fetch_fresh()

    with _cache_lock:
        _positions = positions
        _cache_time = time.time()

    return list(positions)


def invalidate():
    """Force cache expiry on next call. Call this after placing/closing an order."""
    global _cache_time
    with _cache_lock:
        _cache_time = 0.0
    log.debug("[PositionCache] Invalidated")


def _fetch_fresh() -> List[Dict]:
    """Fetch positions from Delta Exchange. Creates event loop if needed."""
    try:
        from webui.backend.routes.options.options_client import get_unified_client, _run_async

        client = get_unified_client()
        result = _run_async(client.get_all_positions_with_options())

        if isinstance(result, dict):
            return result.get('options', [])
        return []

    except Exception:
        log.exception("[PositionCache] Failed to fetch positions")
        return []
```

### Modify `sl_tp_monitor.py` — replace `_get_positions()`:
**Lines 145–171** (`_get_positions` method) — replace entire method body:
```python
def _get_positions(self) -> List[Dict]:
    """Get current options positions from shared cache."""
    from webui.backend.services.position_cache import get_options_positions
    return get_options_positions()
```

### Modify `take_profit_manager.py` — replace position fetch block:
**Lines 540–584** (the cache-miss block inside `_check_take_profit`) — replace with:
```python
from webui.backend.services.position_cache import get_options_positions
positions_data_list = get_options_positions()
```

### Modify `max_loss_manager.py` — after completing Fix 2:
The internal `_positions_cache` in MaxLossMonitor can remain as-is OR be replaced with:
```python
from webui.backend.services.position_cache import get_options_positions
positions = get_options_positions()
```
If replaced, remove `self._positions_cache`, `self._cache_lock`, `self._cache_time` instance vars.

### Invalidate cache after order execution:
In `options_control.py`, after any order that closes/opens a position, add:
```python
from webui.backend.services.position_cache import invalidate as invalidate_position_cache
invalidate_position_cache()
```
This ensures monitors see fresh data immediately after a trade rather than waiting 5s.

### How to verify:
Add a counter to `position_cache.py`: increment on MISS, log every 60s.
Before fix: should see ~12 misses/60s (3 monitors × every 5s).
After fix: should see ~12 misses/60s → ~12 hits + ~1 miss/5s = ~1 miss/5s total.

### Risk:
Medium. Monitors previously had independent caches with independent TTLs.
Sharing means a slow Delta Exchange response blocks all three monitors simultaneously
(vs. previously one might succeed and one fail). Mitigate by keeping a 5s TTL
(short enough that stale data doesn't cause a missed trigger) and logging cache errors clearly.

---

## Fix 4 — HTTP ETag / 304 for Dashboard (Stop Wasting Compute on Unchanged Data)

**File:** `webui/backend/routes/options/dashboard.py`
**Lines:** `get_dashboard()` function and `_fetch_dashboard_fresh()` response
**Effort:** 1 hour
**Expected gain:** ~80% of frontend polls complete in <5ms when positions haven't changed

### Context:
The dashboard already computes `content_hash` (line 213) and returns it as `last_modified`.
The frontend hook (`useOptionsPositions.js`, lines 112–115) already skips re-rendering
if `last_modified` matches. But the backend still does all the work before returning.
ETag makes the backend skip the work entirely.

### Add to `get_dashboard()` — before the cache checks:
```python
from flask import request as flask_request

# ETag check — return 304 immediately if client has current version
client_etag = flask_request.headers.get('If-None-Match')
if client_etag and cached is not None:
    # Compare with the content_hash stored in cache
    server_etag = cached.get('last_modified')
    if server_etag and client_etag == f'"{server_etag}"':
        return '', 304  # Not Modified — zero compute, zero JSON

```

### Add ETag header to the response in `_fetch_dashboard_fresh()`:
```python
# After building the response dict:
response_obj = jsonify(response)
response_obj.headers['ETag'] = f'"{content_hash}"'
response_obj.headers['Cache-Control'] = 'no-cache'  # Must revalidate, but use ETag
return response_obj, 200
```

### Add ETag header to cached responses in `get_dashboard()`:
```python
# In the FRESH and STALE cache paths:
resp = jsonify(cached)
resp.headers['ETag'] = f'"{cached.get("last_modified", "")}"'
resp.headers['Cache-Control'] = 'no-cache'
return resp, 200
```

### Frontend side — add `If-None-Match` to fetch call:
In `useOptionsPositions.js`, the `fetchDashboard` function uses `api.get('/api/options/dashboard')`.
The browser's `fetch` API handles ETag/304 automatically when using standard HTTP caching.
But axios (which `api` wraps) may not. Add the header explicitly:

```js
// In fetchDashboard (useOptionsPositions.js, line 109):
const etag = lastModifiedRef.current;
const headers = etag ? { 'If-None-Match': `"${etag}"` } : {};
const { data, status } = await api.get('/api/options/dashboard', { headers });

if (status === 304) {
  return true; // Nothing changed, skip update
}
```

### How to verify:
Browser DevTools → Network → `/api/options/dashboard`.
- First request: `200 OK`, large response body
- Subsequent requests (unchanged data): `304 Not Modified`, 0 bytes body, <5ms
- After a position changes: next request `200 OK`

### Risk:
Low. ETag is additive — old clients (no `If-None-Match` header) still get `200 OK` as before.
304 is only returned when the client specifically asks for it.

---

## Fix 5 — Adaptive Poll Interval (Stop Polling Fast When Nothing Changes)

**File:** `webui/frontend/src/hooks/useOptionsPositions.js`
**File:** `webui/frontend/src/components/options/OptionsPanel.js`
**Effort:** 2 hours
**Expected gain:** Reduces backend load by 60–70% during quiet periods

### Current behaviour:
Frontend polls at fixed 5s interval (or 1s when manually set). Whether positions
changed or not, the timer fires every 5s.

### New behaviour — adaptive interval:
```
Active: positions changed in last 30s  →  poll every 5s (current)
Quiet:  no changes for 30s+           →  poll every 30s
Tab hidden: document.hidden == true   →  stop polling entirely (already implemented for some intervals)
```

### Changes to `useOptionsPositions.js`:
Add a `lastChangeRef` to track when data last changed:

```js
const lastChangeRef = useRef(Date.now());
const adaptiveIntervalRef = useRef(null);

// In fetchDashboard, when data actually changed (not 304):
if (status !== 304 && data?.success) {
  lastChangeRef.current = Date.now();
  // ... existing state updates
}

// Replace fixed polling useEffect with adaptive:
useEffect(() => {
  const scheduleNext = () => {
    const timeSinceChange = Date.now() - lastChangeRef.current;
    const interval = timeSinceChange > 30000 ? 30000 : pollInterval;
    adaptiveIntervalRef.current = setTimeout(async () => {
      if (!document.hidden) await fetchDashboard();
      scheduleNext();
    }, interval);
  };

  scheduleNext();
  return () => clearTimeout(adaptiveIntervalRef.current);
}, [fetchDashboard, pollInterval]);
```

### Handle position-change push (prerequisite for extending idle interval):
Before extending to 30s idle, you need the backend to push `positions_changed` when
a position actually changes. Otherwise the 30s poll may miss a fill for 30 seconds.

See Fix 6 below for the WebSocket push. Fix 5 should only extend idle interval
AFTER Fix 6 is in place.

**Without Fix 6:** Only extend to 15s idle (safe — won't miss a fill for more than 15s).
**With Fix 6:** Safely extend to 60s idle (WebSocket covers fill events).

---

## Fix 6 — Push Position Updates via WebSocket on Fill Events

**Files:** Multiple — where fills/closes are confirmed
**Effort:** 1 day
**Expected gain:** Frontend gets position updates immediately on fills, enabling idle polling reduction

### Context:
The WebSocket is already connected for `options_ticker_update` (bid/ask prices).
Positions only meaningfully change when:
1. An order is filled (new position opened or closed)
2. SL/TP/MaxLoss triggers and closes a position

Both these events are known to the backend. We just need to emit a SocketIO event.

### Step 6a — Create a helper in `options_client.py` (or `app.py`):
```python
# webui/backend/services/push_events.py

_socketio = None

def init_push_events(socketio_instance):
    global _socketio
    _socketio = socketio_instance

def push_positions_changed(reason: str = 'unknown'):
    """Notify all connected clients that options positions have changed."""
    if _socketio is None:
        return
    try:
        _socketio.emit('options_positions_changed', {
            'reason': reason,
            'timestamp': int(__import__('time').time() * 1000)
        })
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"push_positions_changed failed: {e}")
```

### Step 6b — Initialize in `app.py`:
```python
from webui.backend.services.push_events import init_push_events
init_push_events(socketio)
```

### Step 6c — Call `push_positions_changed()` in:
1. `options_control.py` — after any successful `close_options_position` or `add_to_options_position`
2. `max_loss_manager.py` — after a max loss order executes
3. `sl_tp_monitor.py` — after a SL/TP trigger executes
4. `take_profit_manager.py` — after a take profit trigger executes
5. `mmm_executor.py` — after MMM sells options positions

```python
# Example in options_control.py close route, after confirmed fill:
from webui.backend.services.push_events import push_positions_changed
push_positions_changed(reason='close_position')
```

### Step 6d — Frontend: listen and re-fetch on push:
In `useOptionsPositions.js`, add a socket listener:
```js
socketRef.current.on('options_positions_changed', (data) => {
  console.log('[useOptionsPositions] Position changed:', data.reason);
  fetchDashboard(); // Immediate re-fetch — no waiting for poll timer
  lastChangeRef.current = Date.now(); // Reset adaptive interval
});
```

### How to verify:
1. Open browser DevTools → Network
2. Close an options position manually
3. Within 1 second, a new `/api/options/dashboard` request should appear (triggered by push)
4. The positions list should update immediately (not wait 5s)

---

## Fix 7 — Reduce Monitor Check Frequency When Idle

**Files:** `max_loss_manager.py`, `sl_tp_monitor.py`, `take_profit_manager.py`
**Effort:** 2 hours
**Expected gain:** Reduces background API calls by 50–80% when no limits are configured

### MaxLossMonitor — already has idle detection (line 770):
```python
if active_strike or active_expiry:
    self._check_max_loss()
else:
    # Currently still sleeps 5s even when nothing to do
    pass
```

Change the sleep at line 789 to be adaptive:
```python
# Replace:
time.sleep(self.check_interval)

# With:
sleep_time = self.check_interval if (active_strike or active_expiry) else 30
time.sleep(sleep_time)
```

### SL/TP Monitor — check settings count first:
```python
# In _monitor_loop, before _check_all_positions:
settings = self.sl_tp_manager.get_all_active_sl_tp()
if not settings:
    time.sleep(30)  # No SL/TP configured — check infrequently
    continue
# ... else run normal check
time.sleep(self.check_interval)
```

### TakeProfit Monitor — same pattern:
```python
# In _monitor_loop, check settings first:
tp_settings = self.manager.get_all_strike_take_profit()
if not tp_settings:
    for _ in range(30):  # Sleep 30s if no TP configured
        if self.stop_event.is_set():
            break
        time.sleep(1)
    continue
```

### Risk:
Low. If a user adds a new limit while the monitor is in a 30s sleep, it will be
picked up at most 30s later (acceptable). Limits aren't added and triggered in <30s.

---

## Fix 8 — Remove Debug `print()` Statements from Hot Paths

**File:** `webui/backend/options_strategy/take_profit_manager.py`
**File:** `webui/backend/routes/options/options_control.py` (SSR monitoring loop)
**Effort:** 30 minutes
**Expected gain:** Minor — removes stdout I/O from hot loops which adds latency

### In `take_profit_manager.py` — lines 451, 455, 484, 493, 504:
```python
# Remove all lines like:
print("🎯 DEBUG: _monitor_loop() started!", flush=True)
print(f"🎯 DEBUG: Calling _check_take_profit()...", flush=True)
print(f"🎯 DEBUG: Exception in monitor loop: {e}", flush=True)
```
Replace with `log.debug(...)` or remove entirely. `flush=True` forces a write to
stdout on every call — in a loop that runs every 3 seconds, this adds unnecessary I/O.

### In `options_control.py` SSR monitoring loop (lines 755, 762, 768, 781, 790...):
```python
# Remove all:
print(f"[SSR THREAD] ...")
```
Replace with `log.debug(...)`.

`print()` with `flush=True` inside a monitoring loop that runs every 2 seconds generates
continuous stdout I/O on the same process that serves HTTP requests.

---

## Implementation Order and Timeline

Execute in this order — each fix is independent but builds on the previous:

```
Day 1 (morning) — Quick wins, no risk:
  Fix 8: Remove print() statements              (30 min)
  Fix 1: Parallelize dashboard fetches          (2 hours)
  Fix 4: ETag / 304 for dashboard               (1 hour)
  → Measure: dashboard response_time_ms should drop from ~1200ms to ~400ms

Day 1 (afternoon) — Kill HTTP loopback:
  Fix 2: MaxLossMonitor direct API              (1 hour)
  Fix 7: Adaptive monitor intervals             (2 hours)
  → Measure: Delta Exchange calls per minute should drop visibly in logs

Day 2 — Shared cache:
  Fix 3: Create position_cache.py               (2 hours)
  Fix 3: Wire sl_tp_monitor + take_profit_manager  (2 hours)
  Fix 3: Wire max_loss_manager                  (1 hour)
  → Measure: Position cache hit/miss ratio in logs

Day 3 — WebSocket push:
  Fix 6: push_events.py + backend emit points  (3 hours)
  Fix 6: Frontend socket listener               (1 hour)
  Fix 5: Adaptive poll interval                 (2 hours)
  → Measure: Position updates appear in <1s after a fill
```

---

## How to Measure Before and After

### Metric 1: Dashboard response time
Already in the response JSON as `response_time_ms`.
Log it to a file for 10 minutes before and after each fix:
```bash
watch -n 5 'curl -s http://localhost:5555/api/options/dashboard | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get(\"response_time_ms\", \"N/A\"), \"ms\")"'
```

### Metric 2: Delta Exchange API calls per minute
Add a counter in `async_delta_client.py` at `_request_with_retry`:
```python
_api_call_counter = 0
# At start of _request_with_retry:
_api_call_counter += 1
if _api_call_counter % 20 == 0:
    log.info(f"[API] Total calls so far: {_api_call_counter}")
```
Watch the log: `tail -f logs/backend.log | grep "\[API\] Total"`

### Metric 3: Position cache hit ratio (after Fix 3)
The `position_cache.py` logs HIT/MISS. Watch:
```bash
tail -f logs/backend.log | grep PositionCache
```
Target: >80% HIT rate.

### Metric 4: Frontend network tab
Browser DevTools → Network tab, filter by `/api/options/dashboard`:
- Response time: target <500ms (from ~1200ms)
- Status 304 frequency: target >80% of requests (after Fix 4+5)

---

## What NOT to Do

These are tempting but will not help or will make things worse:

| Idea | Why not |
|---|---|
| Increase `POSITIONS_CACHE_SECONDS` from 10s to 60s | Three monitors bypass this cache anyway |
| Switch to Gunicorn multi-worker | Flask-SocketIO requires Redis for multi-worker — adds infra complexity |
| Switch from `async_mode='threading'` to gevent | Requires changing all `threading.Thread` and `time.sleep` calls — high risk |
| Add Redis for cross-request caching | Adds infra dependency — the in-process fixes are sufficient |
| Increase polling to 1s | Makes everything worse — the opposite of what's needed |
| Rewrite in FastAPI/async | Months of work for the same result achievable in days |
| Pre-compute P&L on backend | Frontend already does this well; not a bottleneck |

---

## Files Changed — Summary

| File | Change | Fix # |
|---|---|---|
| `webui/backend/routes/options/dashboard.py` | Parallelize 5 service calls with ThreadPoolExecutor | 1 |
| `webui/backend/routes/options/dashboard.py` | Add ETag response header + 304 check | 4 |
| `webui/backend/options_strategy/max_loss_manager.py` | Replace HTTP loopback with direct API call | 2 |
| `webui/backend/options_strategy/max_loss_manager.py` | Adaptive sleep when no limits configured | 7 |
| `webui/backend/options_strategy/sl_tp_monitor.py` | Use shared position cache | 3 |
| `webui/backend/options_strategy/sl_tp_monitor.py` | Adaptive sleep when no settings | 7 |
| `webui/backend/options_strategy/take_profit_manager.py` | Use shared position cache | 3 |
| `webui/backend/options_strategy/take_profit_manager.py` | Remove print() debug statements | 8 |
| `webui/backend/options_strategy/take_profit_manager.py` | Adaptive sleep when no settings | 7 |
| `webui/backend/routes/options/options_control.py` | Remove print() from SSR loop | 8 |
| `webui/backend/services/position_cache.py` | **NEW FILE** — shared position cache | 3 |
| `webui/backend/services/push_events.py` | **NEW FILE** — SocketIO push helper | 6 |
| `webui/backend/app.py` | Call `init_push_events(socketio)` | 6 |
| `webui/frontend/src/hooks/useOptionsPositions.js` | Add If-None-Match header, 304 handling | 4 |
| `webui/frontend/src/hooks/useOptionsPositions.js` | Listen for `options_positions_changed` | 6 |
| `webui/frontend/src/hooks/useOptionsPositions.js` | Adaptive poll interval | 5 |

**Total: 2 new files, 13 modified files, ~3 days work**

---

## Expected Results After All Fixes

| Metric | Before | After |
|---|---|---|
| Dashboard response time | ~1,200ms | ~350ms |
| Delta Exchange positions calls/min | ~96 (every 3-5s × 3 monitors + frontend) | ~12 (every 5s, shared cache) |
| % of frontend polls returning 304 | 0% | ~75–85% |
| Dashboard 304 response time | N/A | <5ms |
| Position update latency after fill | 0–5s (depends on poll timing) | <1s (WebSocket push) |
| Time to first position display (cold load) | ~1.2s | ~0.35s |
