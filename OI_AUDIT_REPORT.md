# OI Aggregator — Audit Report + Expiry Filter Design

**Auditor:** Staff Engineer Review
**Date:** 2026-03-27
**Files Read:** oi_api.py, oi_fetchers.py, oi_store.py, OIPanel.js, OIBarChart.js, OIChangeChart.js, OITable.js, OISpikeLog.js, OIPage.js, App.js (OI sections), navigationSections.js, app.py (OI registration block)
**Status:** NOT PRODUCTION READY — 3 Critical bugs must be fixed before live use.

---

## PHASE 1 — AUDIT REPORT

---

### SECTION A — Isolation Verification

| Check | Result |
|---|---|
| Zero imports from MMM / IC / SSDH | ✅ PASS — all 3 backend files import only stdlib, requests, flask |
| No shared state with MMM | ✅ PASS — module globals are OI-only (`_store`, `_fetchers`, `_socketio`) |
| SocketIO namespace `/oi` isolated from `/` | ✅ PASS — every `emit` and `on` uses `namespace='/oi'` |
| Blueprint registered in try/catch | ✅ PASS — `app.py:611` wraps in try/except, logs warning on failure |
| Route prefix isolated (`/api/oi/`) | ✅ PASS — Blueprint url_prefix is `/api/oi` |
| Dedicated logger (not root) | ✅ PASS — `logging.getLogger('oi_aggregator')` |
| Background thread is daemon | ✅ PASS — `daemon=True` set |
| Real OS thread (eventlet-safe) | ✅ PASS — `eventlet.patcher.original('threading').Thread` with fallback |

**Isolation verdict: CLEAN.** This module cannot touch, break, or interfere with MMM trading logic. The three-layer separation (different logger, different blueprint, different namespace) is solid.

---

### SECTION B — Thread Safety

#### B1. CRITICAL — `_ensure_initialized()` Has No Lock

**File:** `oi_api.py:51–62`

```python
def _ensure_initialized():
    global _store, _fetchers
    if _store is None:
        _store = OIStore()        # ← no lock around this
    if _fetchers is None:
        _fetchers = create_fetchers()  # ← no lock around this
```

This function is called from:
1. The SocketIO `connect` handler (line 295) — can fire for multiple simultaneous clients
2. The background thread at startup (line 74)
3. Every REST endpoint via decorator pattern

**Race condition:** Two clients connect simultaneously:
- Client A: checks `_store is None` → True
- Client B: checks `_store is None` → True (before A finishes creating)
- Client A: creates `OIStore()` (opens SQLite connection, creates tables)
- Client B: creates `OIStore()` (opens same SQLite file again)
- Client A: assigns `_store = OIStore_A`
- Client B: assigns `_store = OIStore_B` → **overwrites A's instance**

Result: `OIStore_A` is garbage-collected with its thread-local SQLite connection leaked. The background thread (which was already initialized against `OIStore_A`) is now writing to a different object than the Flask handlers are reading. Data is split across two stores.

**Additionally:** The background thread's startup call at line 74 (`_oi_refresh_loop → _ensure_initialized`) races with the connect handler's call at line 295. The thread starts inside the lock (line 291) but calls `_ensure_initialized` outside it.

**Severity:** CRITICAL. Fix: add a dedicated `_init_lock = threading.Lock()` and wrap the `if _store is None` block inside `_ensure_initialized`.

---

#### B2. Thread-started guard is correct

The `thread_started` flag check+set is inside a single `with _state_lock` block (lines 288–292). This is atomic. Only one thread will ever start. ✅

---

#### B3. `_refresh_interval` global read/write without lock

**File:** `oi_api.py:258`

```python
_refresh_interval = max(30, min(300, int(data['refresh_interval_sec'])))
```

Written by Flask request handler, read by background thread. In CPython, integer assignment is GIL-protected so this won't corrupt. But it is technically a data race. Low severity in practice.

---

### SECTION C — Backend Safety

#### C1. CRITICAL — `oi_config_set` has no input validation

**File:** `oi_api.py:258`

```python
_refresh_interval = max(30, min(300, int(data['refresh_interval_sec'])))
```

If someone sends `{"refresh_interval_sec": "not-a-number"}`, `int("not-a-number")` throws `ValueError`. Flask will return a 500 error with a traceback. The other fields passed to `update_config` (threshold_pct, min_oi_usd, etc.) have **no validation at all** — a caller can set `threshold_pct = -999` which makes the spike detector fire on every single row every cycle, flooding SocketIO and SQLite.

**Fix:** Add type-check + bounds validation for all config fields before calling `update_config`.

---

#### C2. `/change` endpoint is missing

The plan (and `oi_api.py`'s own docstring implied) a separate `/change` endpoint. It was never implemented. The `/snapshot` response does include `oi_change` per row, so the frontend has the data. But the plan's REST contract is partially undelivered. This is a gap, not a crash.

---

#### C3. `get_aggregated` ignores window_min — OI change window is non-deterministic

**File:** `oi_store.py:224–227`

```python
if len(dq) >= 2:
    oldest = dq[0]
    change = latest.get('oi', 0) - oldest.get('oi', 0)
```

`deque[0]` is whatever the oldest of the last 20 entries is. After 1 cycle: no change. After 5 cycles: change vs 5 minutes ago. After 20 cycles: change vs 20 minutes ago. After 21 cycles: change vs still 20 minutes ago (maxlen). The "OI change" window is non-deterministic (it varies from 1 minute to 20 minutes depending on how long the system has been running). This will confuse users who see the UI title say "OI Change" but don't know what timeframe it represents.

**The `window_minutes` parameter exists in the spike detector config but is never used by `get_aggregated`.** They are disconnected.

**Fix:** Accept `window_minutes` in `get_aggregated`, compute cutoff timestamp, find the deque entry closest to `now - window_minutes`, use that as baseline.

---

#### C4. Delta Global OI USD fallback produces garbage data that passes validation

**File:** `oi_fetchers.py:408`

```python
oi_usd = oi * spot_price if spot_price > 0 else oi
```

If `spot_price` is 0 (e.g., the field is missing from the API response), `oi_usd = oi` — treating each contract as $1. For BTC options, `oi` is typically in contracts (e.g., 50 contracts). So `oi_usd = 50` — fifty dollars. This row passes `_validate_row` (`oi_usd >= 0` passes) and enters the spike detector. The `min_oi_usd = 500_000` threshold will filter this out from spike detection, but it will pollute the aggregated OI table with wrong USD notional. The correct fallback is `oi_usd = 0.0`.

---

#### C5. `_prune_stale_keys` called 3 times per cycle

**File:** `oi_store.py:176`

`merge_snapshot` calls `self._prune_stale_keys()` at the end. Since merge_snapshot is called once per exchange (3 exchanges), pruning runs 3 times per cycle, each time acquiring the lock and iterating the full snapshot dict. This is unnecessary churn. Should run once per cycle in `_run_single_cycle`.

---

#### C6. Aggregate spike detector holds lock while calling spike_detector.check

**File:** `oi_store.py:342–370`

```python
with self._lock:           # OIStore lock
    for ...:
        spike = self.spike_detector.check(...)  # spike_detector acquires its OWN lock
```

`OISpikeDetector.check()` acquires `self._lock` (line 470) — but this is the **detector's lock**, not the store's lock. Two different objects, two different locks. No deadlock is possible. ✅ This is fine. Flagging it only because nested lock patterns need explicit confirmation.

---

#### C7. SQLite `get_spike_log` called from Flask request threads is correct

Per-thread connections via `_get_conn()` with WAL mode means concurrent readers are safe. The Flask request thread gets its own connection. ✅

---

### SECTION D — Frontend Stability

#### D1. CRITICAL — Missing `EnhancedErrorBoundary` in `OIPage.js`

**File:** `OIPage.js:13–15`

```jsx
export default function OIPage() {
  return <OIPanel />;
}
```

Every other page in this codebase wraps its panel in `EnhancedErrorBoundary`. This page does not. If `OIPanel` throws a runtime error (e.g., Recharts receives malformed data from the WebSocket), the error will propagate up through the React tree to the nearest Suspense/ErrorBoundary in `App.js` — which is the global Suspense for all routes. Result: the user sees a blank page for the `/oi` route until they navigate away. The error is not contained.

**Severity:** CRITICAL for a production UI. In normal flow this may not fire, but Recharts with null/NaN in `data` props is a known source of runtime throws.

---

#### D2. CRITICAL — SocketIO `oi_update` overwrites rows regardless of selected expiry

**File:** `OIPanel.js:153`

```javascript
socket.on('oi_update', (data) => {
    if (data?.rows) setRows(data.rows);  // ← always overwrites
```

The server always emits rows for the **nearest expiry** (`get_snapshot_for_emit` hardcodes `nearest`). If the user selects a non-nearest expiry and the data loads via `fetchSnapshot`, the display is correct. But the next SocketIO `oi_update` event (60 seconds later) will overwrite `rows` with nearest-expiry data. The chart then shows the wrong expiry. If `selectedExpiry` is different from the nearest, `filteredRows` will be empty (line 198–200 filters by `selectedExpiry`), and all charts show "No data available".

**User experience:** User selects April 7 expiry → charts show April 7 data → 60 seconds later → SocketIO fires → charts go blank.

**Severity:** CRITICAL UX bug. Will confuse and frustrate users.

---

#### D3. `atmStrike` is hardcoded `null` in all chart and table calls

**File:** `OIPanel.js:376–383`

```jsx
<OIChangeChart data={filteredRows} atmStrike={null} />
<OIBarChart    data={filteredRows} atmStrike={null} />
<OITable       data={filteredRows} atmStrike={null} />
```

The ATM reference line (a key feature from the plan, visible in the screenshots) is never rendered. The charts will never show the "ATM" dotted vertical line or highlighted row. The underlying price is available from the exchange data but was never threaded through to the frontend. The `summary` state contains no underlying price field.

**Fix:** Backend `/snapshot` response must include `underlying_price`. Frontend computes nearest strike to that price and passes as `atmStrike`.

---

#### D4. No spike toast notifications implemented

**File:** `OIPanel.js:164–167`

```javascript
socket.on('oi_spike', (spike) => {
    console.log('[OI] Spike detected:', spike);  // ← just a log
    setSpikes(prev => [spike, ...prev].slice(0, 200));
});
```

The plan specified MUI Snackbar toast on spike. The plan exists in the design doc. The implementation does not have it. Users sitting on the "OI Change" tab will have no indication a spike just fired on the "Spike Log" tab. The tab badge (shows count) only updates if they're already on the page.

---

#### D5. Strike count in summary strip is wrong for asymmetric data

**File:** `OIPanel.js:306`

```javascript
{ label: 'Strikes', value: filteredRows.length / 2, ... }
```

`filteredRows.length / 2` assumes exactly one call + one put for every strike. If any strike has only calls (or only puts), this produces a non-integer. For BTC OI this is common near the edges of the strike range. Should be `new Set(filteredRows.map(r => r.strike)).size`.

---

#### D6. OIChangeChart shows misleading empty state

**File:** `OIChangeChart.js:88–96`

The "No OI change data — needs at least 2 fetch cycles" message is shown only when `chartData.length === 0`. But after the first cycle, `chartData` will have entries (correct) with `putChange: 0` and `callChange: 0` for every strike. The chart renders all zero-height bars, which looks broken. Users will think data isn't loading. The chart should show "waiting for baseline" state when all changes are zero, not when data is completely absent.

---

#### D7. Recharts `<Bar>` radius is visually wrong for negative values

**File:** `OIChangeChart.js:148–158`

```javascript
<Bar
  dataKey="putChange"
  radius={[2, 2, 0, 0]}   // top-left, top-right, bottom-right, bottom-left
  ...
/>
```

For negative bars, the bar renders downward. The rounded corners are on the top (the start) rather than the bottom (the tip). Result: negative bars have rounded corners at zero-line and flat tips at the bottom. Visually inconsistent with positive bars. Recharts does not natively flip the radius for negative bars.

---

#### D8. Spike log key is unstable on prepend

**File:** `OISpikeLog.js:104`

```jsx
<tr key={spike.id || `spike-${idx}`}>
```

SocketIO spikes don't have an `id` field (the backend SpikeEvent dict doesn't include `id` from SQLite). So for live spikes, key = `spike-0`, `spike-1`, etc. When a new spike is prepended (newest first), all existing indices shift by 1. React unmounts and remounts every row. Use `spike.ts + spike.strike + spike.exchange` as a stable composite key.

---

#### D9. `fetchSnapshot` depends on `selectedExpiry` in closure

**File:** `OIPanel.js:97–109`

```javascript
const fetchSnapshot = useCallback(async (expiry) => {
    ...
    if (data.expiry && !selectedExpiry) setSelectedExpiry(data.expiry);
}, [selectedExpiry]);   // ← stale closure risk
```

`fetchSnapshot` is recreated every time `selectedExpiry` changes. Any in-flight call from a previous render still holds the old closure. For rapid expiry switching, the state update `setSelectedExpiry` may fire from a stale call and reset the selection. This is a classic stale closure / race condition in React async callbacks. Should use a `useRef` for the intent or `AbortController` to cancel in-flight requests.

---

### SECTION E — Performance Risks

#### E1. No row limit on `/snapshot` when no expiry is specified

**File:** `oi_api.py:190–194`

```python
if not expiry:
    expiries = _store.get_expiries(underlying)
    expiry = expiries[0] if expiries else None
```

This defaults to nearest expiry — which is correct and limits the response. But if `expiry` is explicitly passed as an empty string (not `None`), the condition is False and `get_aggregated(expiry='', ...)` will return rows matching `exp == ''` — which is nothing but is a confusion point. An explicit empty string vs `None` should be normalized.

#### E2. Binance fetch blocks for 3+ seconds per cycle

With 12 expiries × 0.25s sleep = 3s minimum sleep time + network latency (~0.5s × 12 = 6s) = ~9s total for Binance alone. Sequential in the background thread. Within a 60s cycle this is acceptable but it means the cycle regularly takes 10+ seconds. If Deribit and Delta also have latency, the cycle could exceed 20s. The overlap guard (`cycle_running` flag) prevents stacking but means late finishes silently skip the next tick.

#### E3. `_prune_stale_keys` acquires the lock on every exchange merge

Covered in C5. Three lock acquisitions + full dict iterations per 60s cycle = minor but unnecessary overhead.

---

### SECTION F — Complete Flow Trace

```
navigationSections.js:167 → id:'oi', label:'OI Dashboard', group:'Analytics'
    ↓
App.js:384 → Route path="/oi" → <OIPage />   (lazy, inside global Suspense)
    ↓
OIPage.js:14 → return <OIPanel />   ← NO ErrorBoundary ← D1 CRITICAL
    ↓
OIPanel.js useEffect[] →
    io('ws://localhost:5555/oi', ...)  ← correct namespace
    → server: app.py:613 → init_oi_websocket(socketio)
    → oi_api.py:280 → @socketio.on('connect', namespace='/oi')
        → _state['connected_clients'] += 1
        → if not thread_started: _start_background_thread()  ← correct
        → _ensure_initialized()  ← NO LOCK ← B1 CRITICAL
        → emit initial snapshot
    ↓
Background thread (real OS thread):
    _oi_refresh_loop() → _ensure_initialized() ← NO LOCK ← B1 again
    → while True:
        → DeribitOIFetcher.fetch('BTC')     ← sequential
        → BinanceOIFetcher.fetch('BTC')     ← sequential, 9s+
        → DeltaGlobalOIFetcher.fetch('BTC') ← sequential
        → OIStore.merge_snapshot(...)
            → lock → update _snapshots → unlock
            → _write_to_db() (SQLite, WAL, thread-local conn)
            → _check_aggregate_spikes()
            → _prune_stale_keys() ← called 3x per cycle ← C5
        → socketio.emit('oi_update', nearest_expiry_only, namespace='/oi')
                                            ← always nearest ← D2 CRITICAL
        → socketio.emit('oi_spike', ...) for each spike
    ↓
OIPanel.js socket.on('oi_update'):
    setRows(data.rows)  ← overwrites regardless of selectedExpiry ← D2
    setExpiries(data.expiries)
    setLastUpdated(...)
    ↓
filteredRows = rows.filter(r => r.expiry === selectedExpiry)
    ← if selectedExpiry ≠ nearest → empty ← D2 result
    ↓
<OIChangeChart atmStrike={null} />   ← ATM line never shows ← D3
<OIBarChart    atmStrike={null} />   ← ATM line never shows ← D3
<OITable       atmStrike={null} />   ← ATM highlight never shows ← D3
```

---

### SECTION G — Issue Summary

#### CRITICAL (must fix before production)

| # | File | Issue |
|---|---|---|
| C1 | `oi_api.py:51` | `_ensure_initialized()` not thread-safe — double-init race on concurrent connects |
| D2 | `OIPanel.js:153` | SocketIO `oi_update` overwrites rows ignoring selected expiry → charts blank on next update |
| D1 | `OIPage.js:14` | No `EnhancedErrorBoundary` — Recharts error crashes entire route |

#### WARNINGS (should fix before regular use)

| # | File | Issue |
|---|---|---|
| C2 | `oi_api.py` | `/change` endpoint missing — plan gap |
| C3 | `oi_store.py:224` | OI change window non-deterministic (oldest deque entry, not time-windowed) |
| C4 | `oi_api.py:258` | Config endpoint has no input validation — TypeError or unbounded thresholds |
| C5 | `oi_store.py:176` | `_prune_stale_keys` called 3× per cycle — should be once |
| C6 | `oi_fetchers.py:408` | Delta Global: `oi_usd = oi` when spot_price=0 → garbage data passes validation |
| D3 | `OIPanel.js:376` | `atmStrike=null` everywhere — reference line never renders |
| D4 | `OIPanel.js:164` | Spike toast not implemented — no proactive alert |
| D5 | `OIPanel.js:306` | Strike count `length/2` wrong for asymmetric strike data |
| D6 | `OIChangeChart.js:88` | Empty state shows for zero-change data, not truly empty data |
| D7 | `OIChangeChart.js:148` | Bar radius visually wrong for negative-value bars |
| D8 | `OISpikeLog.js:104` | Unstable key on prepend — unnecessary full-list remount |
| D9 | `OIPanel.js:97` | Stale closure in `fetchSnapshot` — race on rapid expiry switching |

#### NICE TO HAVE

| # | File | Issue |
|---|---|---|
| N1 | `OIPanel.js` | Expiry selector is `<select>` single-choice, not multi-checkbox (Phase 2 addresses) |
| N2 | `OIPanel.js:186` | `// eslint-disable-line react-hooks/exhaustive-deps` suppresses a legitimate warning |
| N3 | `oi_api.py:258` | `_refresh_interval` global written without lock (GIL-safe in CPython, bad practice) |
| N4 | `oi_store.py` | No VACUUM after retention delete (plan specified it, missing) |
| N5 | `oi_fetchers.py` | Deribit uses `now_ts = datetime.now()` instead of exchange's own `creation_timestamp` |

---

---

## PHASE 2 — EXPIRY FILTER FEATURE DESIGN

---

### Overview

Replace the single `<select>` expiry dropdown with a Sensibull-style checkbox list that supports multi-select, human-readable labels, weekly expiry markers, and drives the API request.

---

### Frontend Design

#### 2.1 New Component: `ExpiryFilter.js`

**Location:** `webui/frontend/src/components/oi/ExpiryFilter.js`

**Props:**
```
expiries:         string[]     — ISO dates from /api/oi/expiries
selectedExpiries: string[]     — controlled from OIPanel state
onChange:         (string[]) → void
today:            Date         — for day-count calculation
maxSelections:    number       — default 5
```

**Rendering per expiry row:**
```
[ ✓ ] 30 Mar  (3 days)
[ ✓ ] 07 Apr  (11 days) [W]
[   ] 25 Apr  (29 days) [M]
[   ] 27 Jun  (92 days)
```

**Label rules:**
- Date display: `dd MMM` (e.g., "30 Mar")
- Day count: `(N days)` computed as `ceil((expiry - today) / 86400000)`
- Weekly marker `[W]`: expiry falls on a Thursday (Indian markets) or Friday (crypto)
- Monthly marker `[M]`: expiry is the last Friday/Thursday of the month
- Default selection on first load: nearest expiry only (index 0)
- `maxSelections = 5` — if user tries to add a 6th, show inline warning "Max 5 expiries"

**Selected count display:**
```
Selected: 2 of 8 expiries  [Clear all]
```

**Layout:** Horizontal flex-wrap row of pill-style checkboxes (not a vertical list) to save vertical space. Each pill = `[expiry date] (N days)`. Active = filled blue background. On mobile, wraps to 2-per-row.

**Pill style:**
```
Active:   bg:#1e3a5f, border:#3b82f6, text:#e2e8f0
Inactive: bg:transparent, border:#334155, text:#64748b
Weekly:   + small 'W' badge top-right in amber
```

---

#### 2.2 OIPanel State Changes

**Replace:**
```javascript
const [selectedExpiry, setSelectedExpiry] = useState('');   // single
```

**With:**
```javascript
const [selectedExpiries, setSelectedExpiries] = useState([]);  // multi
```

**handleExpiryChange → handleExpiryFilter:**
```
Arguments: newSelectedExpiries (string[])
Behavior:
  - Update selectedExpiries state
  - If empty: do nothing (show empty state with message "Select at least one expiry")
  - If 1-5: fetch snapshot for all, merge results
```

**filteredRows update:**
```javascript
const filteredRows = selectedExpiries.length > 0
  ? rows.filter(r => selectedExpiries.includes(r.expiry))
  : [];
```

---

#### 2.3 Default Selection Logic

```
On first oi_update from SocketIO:
  if selectedExpiries is empty:
    setSelectedExpiries([data.expiries[0]])   // nearest expiry only

On explicit user click:
  Toggle expiry in/out of selectedExpiries
  Enforce maxSelections = 5
```

---

### Backend Design

#### 2.4 `/snapshot` Endpoint — Add Multi-Expiry Support

**Current:** `?expiry=2026-03-30` (single, optional)

**New:** `?expiries=2026-03-30,2026-04-07` (comma-separated list, optional)

**Backward compatibility:** If `expiries` is absent but `expiry` is present, treat as single-expiry (existing behavior preserved). If both absent, default to nearest.

**Parsing:**
```python
expiries_param = request.args.get('expiries', '')
if expiries_param:
    expiry_list = [e.strip() for e in expiries_param.split(',') if e.strip()]
    expiry_list = expiry_list[:5]  # hard cap at 5
else:
    single = request.args.get('expiry', None)
    expiry_list = [single] if single else []
    if not expiry_list:
        all_exp = _store.get_expiries(underlying)
        expiry_list = [all_exp[0]] if all_exp else []
```

**Filtering must happen in `get_aggregated`** (not post-aggregation). Pass `expiry_list` to the store query. The store already filters by single expiry in its loop — extend to filter by `expiry in expiry_list`.

#### 2.5 `get_aggregated` Signature Change

**Current:**
```python
def get_aggregated(self, expiry: str = None, underlying: str = 'BTC') -> list:
    if expiry and exp != expiry:
        continue
```

**New:**
```python
def get_aggregated(self, expiries: list = None, underlying: str = 'BTC') -> list:
    if expiries and exp not in expiries:
        continue
```

This keeps the filtering inside the `with self._lock` block, before any aggregation computation. Correct per the performance rule.

#### 2.6 `/snapshot` Response Enhancement

Add to the JSON response:
```json
{
  "expiries_requested": ["2026-03-30", "2026-04-07"],
  "expiries_available": ["2026-03-30", "2026-04-07", "2026-04-25"],
  "underlying_price": 83000.0,   ← NEW (needed for ATM strike computation)
  "rows": [...],
  "summary": {
    "total_call_oi": ...,
    "total_put_oi": ...,
    "pcr": ...,
    "by_expiry": {                ← NEW (PCR per expiry when multi-select)
      "2026-03-30": { "call_oi": ..., "put_oi": ..., "pcr": ... },
      "2026-04-07": { "call_oi": ..., "put_oi": ..., "pcr": ... }
    }
  }
}
```

**Note:** `underlying_price` should come from the most recent Deribit row (most reliable price source). Store it in `OIStore._underlying_price` during `merge_snapshot`.

#### 2.7 SocketIO `oi_update` — Fix the D2 Critical Bug

Along with the expiry filter feature, this must be fixed:

**Current (broken):** Server always emits nearest-expiry data, overwrites frontend state.

**Fix:** Frontend sends its `selectedExpiries` to the server on connection, and the server uses that list when emitting.

Two options:

**Option A (recommended — simpler):** Remove rows from `oi_update` entirely. `oi_update` only sends metadata (expiries list, health, underlying price). Frontend always fetches rows via REST when it needs them.

**Option B:** Frontend emits `set_expiry_preference` event to server after connecting; server stores per-client preference and uses it in `oi_update`. Complex — requires per-client state in server.

**Recommendation: Option A.** `oi_update` becomes a lightweight "data is fresh" signal. Frontend auto-calls `fetchSnapshot(selectedExpiries)` on each `oi_update` event. The REST call is cheap (sub-10ms local, <100ms remote) and correct.

---

### Edge Case Handling

| Edge Case | Behavior |
|---|---|
| No expiry selected | Show empty charts with "Select at least one expiry" message. Do not call API. |
| Expiry not available (expired, not fetched yet) | Ignored silently by backend (`exp not in expiry_list` filter). Frontend shows only data that arrives. |
| More than 5 selected | Enforced client-side (pill becomes non-clickable at 5). Backend hard-caps at 5 via `expiry_list[:5]`. |
| Single expiry selected | Behaves identically to original behavior. Full backward compat. |
| SocketIO reconnect | `selectedExpiries` state is preserved in React (not cleared). On reconnect → `oi_update` fires → frontend re-fetches with existing `selectedExpiries`. |
| Weekly expiry detection | Server adds `is_weekly: bool` field to `/expiries` response. Frontend uses it for `[W]` marker. |

---

### Multi-Expiry Chart Behavior

When multiple expiries are selected, bar charts show **aggregated** data (all expiries summed per strike). This is intentional — lets the user see the total OI picture across near + far expiries.

The summary strip shows `by_expiry` breakdown as a secondary row:
```
[30 Mar] Call: 12.4K  Put: 18.2K  PCR: 1.47
[07 Apr] Call: 8.1K   Put: 6.3K   PCR: 0.78
```

---

### Performance Impact Assessment

**Adding multi-expiry support:**
- Backend `get_aggregated` with 5 expiries: same O(N) loop, just includes 5x keys. Negligible.
- Frontend: 5x more rows in `filteredRows`. Recharts handles 500 rows — slightly heavier render but acceptable.
- REST calls: one call with `expiries=...` vs one call per expiry. Better than before.
- No risk to MMM or other modules. Completely isolated.

**The D2 bug fix (Option A):** REST call for rows on every `oi_update` adds one HTTP call per 60s per client. Trivial.

---

## PHASE 3 — REQUIRED FILE CHANGES

### Files to modify (no code, only plan):

| File | Change |
|---|---|
| `oi_api.py` | 1. Add `_init_lock` to `_ensure_initialized`. 2. Validate config inputs in `oi_config_set`. 3. Parse `?expiries=` param in `/snapshot`. 4. Add `underlying_price` to snapshot response. 5. Change `oi_update` emit to metadata-only (Option A). |
| `oi_store.py` | 1. Change `get_aggregated(expiry)` → `get_aggregated(expiries: list)`. 2. Store `_underlying_price` during `merge_snapshot`. 3. Add `is_weekly` flag to `get_expiries` return. 4. Move `_prune_stale_keys` call out of `merge_snapshot` (call once per cycle in `oi_api.py`). 5. Fix Delta Global `oi_usd` fallback to `0.0`. |
| `OIPage.js` | Wrap `<OIPanel />` in `<EnhancedErrorBoundary componentName="OIPanel">`. |
| `OIPanel.js` | 1. Replace `selectedExpiry` state with `selectedExpiries[]`. 2. Add `ExpiryFilter` component. 3. Fix `oi_update` handler to not overwrite rows (fetch via REST instead). 4. Compute `atmStrike` from `underlying_price` and pass to charts. 5. Add spike toast (MUI Snackbar). 6. Fix strike count formula. |
| `OIBarChart.js` | No change needed. Already accepts `atmStrike` prop correctly. |
| `OIChangeChart.js` | Fix bar `radius` for negative values. Fix empty-state condition. |
| `OISpikeLog.js` | Fix `key` to use composite `ts+strike+exchange` instead of array index. |

### New files to create:

| File | Purpose |
|---|---|
| `webui/frontend/src/components/oi/ExpiryFilter.js` | Sensibull-style pill checkbox expiry selector |

---

## PHASE 3 — RISK ASSESSMENT

### Risk of Adding Expiry Filter

| Risk | Severity | Mitigation |
|---|---|---|
| Backend `get_aggregated` signature change breaks existing REST call | Medium | Old `?expiry=` param still works via backward-compat parsing |
| SocketIO `oi_update` payload change (Option A: rows removed) | Low | Frontend is the only consumer; both are changed together |
| Multi-expiry returns too many rows to frontend | Low | Backend cap at 5 expiries; typical BTC has ≤60 strikes per expiry = 300 rows max |
| D2 fix (REST call per `oi_update`) adds latency | Negligible | One HTTP call per 60s per connected client; sub-10ms local |
| MMM algo affected | None | Completely isolated. OI module shares nothing with MMM. |
| New ExpiryFilter component crash | Low | Wrap in ErrorBoundary at OIPanel level; chart tabs still render even if filter fails |

### Overall Risk: LOW

The module is read-only analytics. It cannot place orders, modify session state, or interact with the trading engine. The worst-case failure mode is a blank OI panel — which is contained behind the route-level ErrorBoundary (once D1 is fixed).

The 3 critical bugs (C1, D1, D2) must be fixed before production. All 3 have clear, contained fixes. None of the fixes touch MMM code.

---

**End of Audit Report.**
