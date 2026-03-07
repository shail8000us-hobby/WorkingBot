# WebUI Performance Analysis

**Date:** March 2026
**Scope:** Backend + Frontend — what actually makes the WebUI slow and how to fix it

---

## Executive Summary

The WebUI is slow for one primary reason: **too many redundant Delta Exchange API calls happening
simultaneously from too many places**. The frontend polls every 5 seconds, triggering a dashboard
fetch that hits Delta Exchange 4–5 times per request — while three background monitors
are *also* independently fetching positions from Delta Exchange every 3–5 seconds each.

Under load with 1 browser tab open:
- ~1 dashboard fetch / 5s = ~4 Delta Exchange calls / 5s from frontend
- SL/TP monitor: 1 positions call / 5s
- Max Loss monitor: 1 positions call / 5s
- Take Profit monitor: 1 positions call / 3s

**Total: ~7–8 Delta Exchange API calls per 5 seconds, all fetching the same positions data.**

Delta Exchange rate-limits aggressively. When you hit the limit, API calls queue up or fail,
which makes the frontend stall waiting for responses that take 2–4s instead of 200ms.

---

## Bottleneck Map

```
Browser (5s poll)
  └─> GET /api/options/dashboard
        └─> dashboard_service.py
              ├─> get_options_positions()      → Delta Exchange REST (positions)
              │     └─> asyncio.gather(tickers for each position) → N Delta calls
              ├─> get_pending_orders()         → Delta Exchange REST (orders)
              ├─> get_futures_positions()      → Delta Exchange REST (futures)
              ├─> get_options_status()         → Guardian file read (fast)
              └─> fetch_margin_data()          → Delta Exchange REST (wallet)

(running in parallel background threads, independently):
  SL/TP Monitor (every 5s)     → positions API call → Delta Exchange
  Max Loss Monitor (every 5s)  → positions API call → Delta Exchange
  Take Profit Monitor (every 3s) → positions API call → Delta Exchange

(also running):
  SSR monitoring threads (per active order, every 2s) → orderbook + order status
  IV enrichment (browser, every 60s) → N direct Delta Exchange calls from browser
```

Every one of these calls is independent. They do not share data. They do not coordinate.

---

## Root Cause 1: No Shared Position Cache Between Monitors

**Impact: HIGH**

SL/TP monitor, Max Loss monitor, and Take Profit monitor each call `get_all_positions_with_options()`
independently. They sleep 3–5 seconds between checks. At any given moment, 2–3 of them
are fetching positions simultaneously. They will always return the same data since options
positions don't change without a fill event.

**Fix:** A single `PositionCache` with a 3-second TTL, shared by all three monitors.
All three call `cache.get_positions()` — only one triggers the actual API call per window.

**Estimated gain:** Reduces Delta Exchange position API calls from ~8/5s to ~2/5s (75% reduction).

---

## Root Cause 2: Dashboard Aggregation Is Sequential, Not Parallel

**Impact: HIGH**

`dashboard_service.py` calls these in sequence (effectively, via `_run_async` on a single
dedicated event loop):

```
get_options_positions()   ~300-600ms
get_pending_orders()      ~200-400ms
get_futures_positions()   ~200-400ms
fetch_margin_data()       ~200-400ms
```

Total: **~900ms–1800ms per dashboard request** just in API wait time.

These four calls are completely independent and can all run concurrently.

**Fix:** Run all four with `asyncio.gather()` on the same event loop call.

**Estimated gain:** Dashboard response time drops from ~1.5s to ~500ms (the slowest single call).

---

## Root Cause 3: Frontend Polls HTTP Even Though WebSocket Is Connected

**Impact: MEDIUM**

The WebSocket (`socket.io`) is already connected and used for `options_ticker_update`.
But position data (the main content of the dashboard) still comes via HTTP polling every 5 seconds.

Every 5 seconds, the browser sends an HTTP request, Flask allocates a thread, the backend
hits Delta Exchange, waits 300-600ms, serializes JSON, and sends it back — even when
nothing has changed.

The hook even has a `last_modified` check:
```js
if (data.last_modified && data.last_modified === lastModifiedRef.current) {
  return true; // Skip re-render
}
```
But the backend has *already done all the API work* before returning. The check only
prevents a React re-render, not the backend work.

**Fix (two parts):**

Part A — Backend `If-None-Match` / ETag response:
The dashboard cache tracks `last_modified`. Add an ETag header. If the browser sends
`If-None-Match` with the same ETag, return `304 Not Modified` immediately — zero API calls,
zero JSON serialization, tiny response. This is standard HTTP caching.

Part B — Push on fill events:
Positions only meaningfully change when a fill occurs (order executed). The backend already
knows when fills happen (fill processor, SL/TP triggers). Emit a `positions_updated`
SocketIO event on fill → frontend re-fetches immediately. Between fills, extend the poll
interval to 30s (positions won't have changed).

**Estimated gain:** With ETag: 80% of polls return 304 in <5ms instead of 1.5s.
With push: poll interval can safely be raised to 30s.

---

## Root Cause 4: `async_mode='threading'` Blocks Flask Workers on Every API Call

**Impact: MEDIUM**

Flask is configured with `async_mode='threading'`. Every call to `_run_async(...)` in a
route handler blocks the Flask thread for the full duration of the async operation
(up to 60s by the timeout). With multiple browser tabs or concurrent requests, threads
pile up waiting for Delta Exchange.

Each `asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=60)` call is a
blocking wait. If Delta Exchange is slow (250ms), that Flask thread sits idle for 250ms
doing nothing, unable to serve other requests.

**Fix options (pick one):**

Option A — More Gunicorn workers (easiest):
```
gunicorn --workers 4 --threads 2 --worker-class gthread app:app
```
4 workers × 2 threads = 8 concurrent blocking requests. Costs ~200MB extra RAM.

Option B — Upgrade to async Flask (bigger change):
Migrate from Flask + Flask-SocketIO threading mode to Quart + python-socketio async mode.
All `_run_async()` calls become native `await`. Zero thread blocking.
This is a significant migration but eliminates the fundamental concurrency limit.

**Estimated gain (Option A):** 4× concurrent request capacity with no code changes.

---

## Root Cause 5: SSR Monitoring Creates a New Event Loop Per Thread

**Impact: LOW-MEDIUM** (only when SSR orders are active)

Each SSR order spawns a thread that creates `asyncio.new_event_loop()` and a fresh
`AsyncDeltaClient` with its own `httpx.AsyncClient` connection pool. With 3 active
SSR orders, that is 3 separate connection pools each maintaining persistent connections
to Delta Exchange. Each pool opens 2–5 TCP connections.

At 6–15 open connections just for SSR monitoring, plus the dedicated options event loop
connection pool, plus the SL/TP/MaxLoss monitors — the backend can exhaust the OS
file descriptor limit under load (the code comments about `[Errno 24] Too many open files`
exist for exactly this reason).

**Fix:** Reuse the existing dedicated event loop (`_get_dedicated_loop()`) for SSR
monitoring instead of creating per-thread loops. SSR monitoring coroutines can be
submitted via `run_coroutine_threadsafe` to the shared loop.

**Estimated gain:** Reduces open connections from O(N active SSR orders) to O(1).

---

## Root Cause 6: Multiple Slow Routes Block the Activity Log

**Impact: LOW-MEDIUM**

`GET /api/options/activity-log` fetches: SSR order snapshot + positions (or cache) +
P&L calculation + filesystem log read — all inline in the route handler. If the frontend
calls this separately from the dashboard, it adds another set of API calls on top of
the polling already happening.

Check if `OptionsPanel` calls both `/api/options/dashboard` AND `/api/options/activity-log`
on the same polling interval. If so, that doubles the backend load.

**Fix:** Consolidate. Everything in `activity-log` that overlaps with `dashboard` (positions,
SSR orders) should come from the shared cache, not fresh API calls.

---

## Priority Order for Implementation

These are ordered by **impact vs effort**:

| # | Fix | Effort | Impact | Risk |
|---|---|---|---|---|
| 1 | Shared `PositionCache` for 3 monitors | 1 day | HIGH | Low |
| 2 | Parallelize dashboard with `asyncio.gather` | 2 hours | HIGH | Low |
| 3 | HTTP ETag / 304 for dashboard | 3 hours | HIGH | Low |
| 4 | Gunicorn multi-worker deployment | 1 hour | MEDIUM | Low |
| 5 | Push `positions_updated` on fill events | 2 days | MEDIUM | Medium |
| 6 | SSR shared event loop | 3 hours | MEDIUM | Medium |
| 7 | Raise poll interval to 30s (after push) | 30 min | MEDIUM | Low |
| 8 | Quart/async Flask migration | 2 weeks | HIGH | HIGH |

**Items 1–4 together will have the most visible effect and take less than a day total.**

---

## What Will NOT Help (Common Misconceptions)

| Idea | Why it won't help |
|---|---|
| Refactoring options_control.py into smaller files | Zero runtime effect. Same code, different files. |
| Increasing `POSITIONS_CACHE_SECONDS` from 10s to 30s | Helps slightly but doesn't fix monitors bypassing cache |
| Adding more `try/except` around API calls | Makes failures silent, does not speed up success paths |
| Reducing IV enrichment frequency (already at 60s) | IV enrichment is already well-optimized, not a bottleneck |
| Caching at the route level (already done for dashboard) | Cache is working; the problem is monitors bypassing it |

---

## Quick Win: Measure First

Before implementing anything, add timing to the dashboard endpoint to know exactly
where the time goes. Log how long each of the 4 sub-fetches takes:

```
[dashboard] positions: 412ms
[dashboard] pending_orders: 198ms
[dashboard] futures: 231ms
[dashboard] margin: 187ms
[dashboard] total: 1028ms  (serial)
vs parallel: 412ms (max of above)
```

This will confirm or refute the Root Cause 2 diagnosis and give a baseline to measure
improvements against. Add this logging first, run for 1 hour, then decide which fixes
to implement.

---

## Recommended Implementation Order

### Step 1 (today): Add timing logs to dashboard endpoint
Wrap each sub-fetch in `time.time()` before/after. Log to `log.info`. Gives you real numbers.

### Step 2 (same day): Parallelize the 4 dashboard sub-fetches
Change `dashboard_service.py` to run all 4 with `asyncio.gather`. No structural changes,
just wrap in gather. Expected: dashboard latency drops from ~1.5s to ~500ms.

### Step 3 (next day): Shared PositionCache
Create `webui/backend/services/position_cache.py` with a `PositionCache` singleton
(TTL=5s). All three monitors call `position_cache.get()` instead of independently
fetching. Expected: 75% reduction in position API calls.

### Step 4 (1 hour): Gunicorn multi-worker
Add `gunicorn.conf.py` with 3–4 workers. This alone prevents thread starvation under
concurrent requests.

### Step 5 (next week): ETag on dashboard + raise poll interval
After Steps 1–4 are running, measure again. Then add ETag so unchanged responses
return 304 in <5ms.
