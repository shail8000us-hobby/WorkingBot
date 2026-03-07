# MMM Algorithm Audit — Bug Report
**Date:** 2026-02-23
**Branch:** SSR
**Audited Files:** mmm_monitor.py, mmm_api.py, mmm_regime.py, mmm_adopter.py, mmm_activity.py, mmm_state.py, MMMConfigPanel.js, MMMDashboard.js
**Total Bugs:** 76 (CRITICAL: 9 | HIGH: 16 | MEDIUM: 35 | LOW: 11 | Not Counting: 5 false alarms)

---

## Quick Stats

| Severity | Count | Files Affected |
|----------|-------|----------------|
| CRITICAL | 9 | monitor, state, adopter, activity, dashboard |
| HIGH | 16 | monitor, api, regime, state, adopter, activity, dashboard |
| MEDIUM | 35 | all files |
| LOW | 11 | all files |

---

## CRITICAL Bugs

---

### C-1 · `mmm_monitor.py:668` — Margin RED/CRITICAL early return skips all cleanup

**Severity:** CRITICAL
**File:** `webui/backend/routes/mmm/mmm_monitor.py`
**Line:** 668

**What's Wrong:**
```python
if margin_result['tier'] in (TIER_RED, TIER_CRITICAL):
    await self._auto_close_all(...)
    return  # ← BARE RETURN — skips everything below
```

**Why It Matters:**
- `update_peak_pnl()` never called → trailing stop permanently locked
- `_save_my_session()` never called → session state lost if monitor crashes after return
- `_emit_heartbeat_data()` never called → UI never sees the emergency event
- `self._health.record_beat()` never called → telemetry gap

**How to Fix:**
```python
if margin_result['tier'] in (TIER_RED, TIER_CRITICAL):
    await self._auto_close_all(...)
    self._emit_heartbeat_data(ce_now, pe_now)
    update_peak_pnl(session, current_total_pnl)
    self._save_my_session(session)
    self._health.record_beat('ok', latency_ms=elapsed_ms)
    return
```

**Verification:** Trigger a margin RED scenario in staging; confirm `peak_pnl` field in session JSON is updated and a WebSocket event fires.

---

### C-2 · `mmm_monitor.py:925` — ATM auto-close early return skips cleanup

**Severity:** CRITICAL
**File:** `webui/backend/routes/mmm/mmm_monitor.py`
**Line:** 925

**What's Wrong:**
```python
await self._auto_close_all(
    f'ATM auto-close: Spot ${spot_price:.0f} ...',
    emergency=True,
)
return  # ← BARE RETURN — same pattern as C-1
```

**Why It Matters:** Same as C-1 — peak P&L decay skipped, no save, no emit, no health beat.

**How to Fix:** Same cleanup block as C-1 before the `return`.

**Verification:** Simulate ATM breach; check session JSON and WebSocket log for post-close data.

---

### C-3 · `mmm_monitor.py:1581` — Max loss breach early return skips cleanup

**Severity:** CRITICAL
**File:** `webui/backend/routes/mmm/mmm_monitor.py`
**Line:** 1581

**What's Wrong:**
```python
await self._auto_close_all(
    f'Max loss breached: P&L ${current_total_pnl:.2f} <= -${max_loss_amount:.2f}',
    emergency=True,
)
return  # ← BARE RETURN — same pattern as C-1
```

**Why It Matters:** Same as C-1.

**How to Fix:** Same cleanup block as C-1.

> **Root Cause Note for C-1/C-2/C-3:** Every emergency path that calls `_auto_close_all()` then immediately `return` bypasses the entire heartbeat tail. The proper fix is either: (a) inline a `_run_emergency_cleanup()` helper before each return, or (b) refactor emergency exits to set `_skip_to_pnl = True` + `break` so the existing cleanup tail runs naturally.

---

### C-4 · `mmm_state.py:429–473` — `create_session()` allows empty expiry; session persists without it

**Severity:** CRITICAL
**File:** `webui/backend/routes/mmm/mmm_state.py`
**Lines:** 429–473

**What's Wrong:**
Sessions can be created with `params['expiry'] = ''`. If a crash occurs between `create_session()` and the caller assigning the expiry, the session persists in storage forever with an empty expiry string.

**Why It Matters:**
- `minutes_to_expiry` returns `None` for the entire session lifetime
- Gamma near-expiry multiplier never activates
- Wind-down, auto-close timing, and theta acceleration all fail silently
- Session becomes a zombie that cannot be fixed without manual database surgery

**How to Fix:**
```python
def create_session(session_id: str = None, mode: str = 'fresh', params: Dict = None) -> Dict:
    merged_params = {**DEFAULT_PARAMS}
    if params:
        merged_params.update(params)

    # ENFORCE expiry before anything else
    if not merged_params.get('expiry'):
        raise ValueError("params['expiry'] is required to create a session")
    ...
```

**Verification:** Call `create_session()` without expiry; confirm `ValueError` is raised and no session file is written.

---

### C-5 · `mmm_state.py:512–515` — `expiry_time` is never populated in `create_session()`

**Severity:** CRITICAL
**File:** `webui/backend/routes/mmm/mmm_state.py`
**Line:** 512

**What's Wrong:**
```python
'entry_time': None,
'last_heartbeat': None,
'next_heartbeat': None,
'expiry_time': None,   # ← Never computed from params['expiry']
```

`expiry_time` is initialized `None` and never calculated anywhere in `mmm_state.py`. All time-based logic depends on this field.

**Why It Matters:**
- `minutes_to_expiry` is always `None` → every time-gated check is disabled
- Wind-down, ATM auto-close timing, gamma multiplier: all dead

**How to Fix:**
```python
expiry_str = merged_params.get('expiry', '')
expiry_time = None
if expiry_str:
    try:
        d, m, y = int(expiry_str[0:2]), int(expiry_str[2:4]), int(expiry_str[4:8])
        expiry_time = datetime(y, m, d, 15, 30, 0, tzinfo=timezone.utc).isoformat()
    except (ValueError, IndexError):
        log.warning(f"Failed to parse expiry string: {expiry_str!r}")

# ... in session dict:
'expiry_time': expiry_time,
```

**Verification:** Create session with expiry "23022026"; check `session['expiry_time']` equals `"2026-02-23T15:30:00+00:00"`.

---

### C-6 · `mmm_state.py:429–450` — `create_session()` silently overwrites an existing session

**Severity:** CRITICAL
**File:** `webui/backend/routes/mmm/mmm_state.py`
**Lines:** 429–450

**What's Wrong:**
No guard prevents `create_session(session_id="mmm25feb26-1", params={...})` from re-initializing an existing running session. A concurrent retry or race condition can destroy positions and P&L history without any error.

**Why It Matters:**
- All position history, realized P&L, and adjustment records are wiped
- Session resumes from zero state — financial data lost
- No error raised, no log emitted

**How to Fix:**
```python
def create_session(session_id: str = None, mode: str = 'fresh', params: Dict = None) -> Dict:
    if session_id:
        existing = storage.get_session(session_id)
        if existing:
            raise RuntimeError(
                f"Session '{session_id}' already exists. "
                "Use resume, not create_session()."
            )
    ...
```

**Verification:** Call `create_session()` with an existing session ID; confirm `RuntimeError` and no data overwrite.

---

### C-7 · `mmm_adopter.py:472` — `side_state['positions'].append()` without guaranteeing key exists

**Severity:** CRITICAL
**File:** `webui/backend/routes/mmm/mmm_adopter.py`
**Line:** 472

**What's Wrong:**
```python
side_state['positions'].append({...})  # KeyError if 'positions' not in side_state
```

If `create_side_state()` fails to initialize `'positions'` (version mismatch, logic error), this raises `KeyError` or `AttributeError` mid-adoption, leaving a partially constructed session in storage.

**Why It Matters:** Partial adoption writes corrupt session to disk. Next heartbeat loads broken state.

**How to Fix:**
```python
if 'positions' not in side_state or side_state['positions'] is None:
    log.warning(f"[Adopter] 'positions' missing from {side_label} state — initializing empty")
    side_state['positions'] = []
side_state['positions'].append({...})
```

**Verification:** Mock `create_side_state()` to return dict without `'positions'`; confirm adoption handles it gracefully.

---

### C-8 · `mmm_activity.py:94–99` — `MMMActivityLog` claims "thread-safe" but has no lock

**Severity:** CRITICAL
**File:** `webui/backend/routes/mmm/mmm_activity.py`
**Lines:** 94–99

**What's Wrong:**
```python
class MMMActivityLog:
    """Thread-safe activity log for MMM background operations."""  # ← INCORRECT

    def __init__(self):
        self._activities: deque = deque(maxlen=MAX_ACTIVITIES)
        # ← NO threading.Lock() anywhere
```

Multiple heartbeat threads call `add()`, `get_recent()`, `clear()`, `resolve_progress()` concurrently. Python `deque.append` is GIL-atomic but iteration + modification (in `clear()`, `resolve_progress()`) is not.

**Why It Matters:**
- Activity log corruption in production
- `clear()` reconstructs deque while another thread iterates → non-deterministic data loss
- Frontend receives duplicate or missing activity events
- Violates the documented "thread-safe" contract

**How to Fix:**
```python
import threading

class MMMActivityLog:
    def __init__(self):
        self._lock = threading.RLock()
        self._activities: deque = deque(maxlen=MAX_ACTIVITIES)
        ...

    def add(self, ...):
        with self._lock:
            self._activities.append(activity)
            self._save_to_disk(activity)

    def get_recent(self, ...):
        with self._lock:
            items = list(self._activities)
        items.reverse()
        ...

    def clear(self, session_id: str = None):
        with self._lock:
            ...  # existing logic
```

**Verification:** Run two heartbeat threads simultaneously; confirm no log corruption under stress test.

---

### C-9 · `MMMDashboard.js:1147,1372,1454` — WebSocket data accessed without null guard

**Severity:** CRITICAL
**File:** `webui/frontend/src/components/mmm/MMMDashboard.js`
**Lines:** 1147, 1372–1376, 1454–1457

**What's Wrong:**
```javascript
// wsData.heartbeat accessed directly — crashes if wsData is empty or WS not connected
const spot = wsData.heartbeat.spot_price;  // TypeError if heartbeat is undefined
```

On initial load, reconnect, or slow WebSocket delivery, `wsData.heartbeat` is `undefined`. The component crashes with a blank dashboard.

**Why It Matters:** User loses visibility into live positions at the worst possible time (reconnect during a move).

**How to Fix:**
```javascript
// At the top of SessionDetail render:
if (!wsData?.heartbeat) {
    return <Box sx={{ p: 3 }}><CircularProgress /><Typography>Waiting for live data...</Typography></Box>;
}
```
Add similar guards for `wsData.positions`, `wsData.regime`, `wsData.safety` before use.

**Verification:** Open dashboard with WebSocket disconnected; confirm loading state shown instead of crash.

---

## HIGH Bugs

---

### H-1 · `mmm_api.py:2247` — Premium calculation missing `LOT_SIZE_BTC` (1000× overstatement)

**Severity:** HIGH
**File:** `webui/backend/routes/mmm/mmm_api.py`
**Line:** 2247

**What's Wrong:**
```python
# Current (WRONG):
actual_premium = (ce_fill * lots) + (pe_fill * lots)

# Should match line 1593 pattern:
actual_premium = (ce_fill + pe_fill) * lots * LOT_SIZE_BTC  # LOT_SIZE_BTC = 0.001
```

With `ce_fill=100`, `pe_fill=50`, `lots=10`: current gives `1500`, correct gives `1.5`.

**Why It Matters:** All downstream P&L calculations are ~1000× off. Net P&L, realized P&L, and peak_pnl tracking are corrupted.

**How to Fix:** Replace line 2247 with: `actual_premium = (ce_fill + pe_fill) * lots * LOT_SIZE_BTC`

**Verification:** Unit test with known fill prices; assert `actual_premium` is within expected USD range (dollars, not thousands).

---

### H-2 · `mmm_monitor.py:943` — Both-sides-closed early return skips final cleanup

**Severity:** HIGH
**File:** `webui/backend/routes/mmm/mmm_monitor.py`
**Line:** 943

**What's Wrong:**
```python
self.stop('Both sides fully closed — strategy complete!')
return  # ← No final emit, no peak update, stop() saves once but skips tail
```

**Why It Matters:** Final P&L, peak decay, and WebSocket completion event are skipped. UI doesn't know the session completed cleanly.

**How to Fix:** Before `return`, emit final heartbeat data and update peak P&L.

---

### H-3 · `mmm_monitor.py:980` — P&L-incomplete return skips `update_peak_pnl()`

**Severity:** HIGH
**File:** `webui/backend/routes/mmm/mmm_monitor.py`
**Line:** 980

**What's Wrong:**
```python
self.pause('P&L calculation incomplete — data unreliable')
self._emit_heartbeat_data(ce_now, pe_now)
self._save_my_session(session)
return  # ← save and emit ARE called, but update_peak_pnl() is NOT
```

**Why It Matters:** During extended exchange outages, the trailing stop permanently locks because peak P&L never decays.

**How to Fix:** Add before the return:
```python
update_peak_pnl(session, last_known_pnl)  # Use cached value if fresh unavailable
```

---

### H-4 · `mmm_monitor.py:759` — Miss/partial beat paths skip peak P&L update

**Severity:** HIGH
**File:** `webui/backend/routes/mmm/mmm_monitor.py`
**Line:** 759

**What's Wrong:** Miss beat and partial beat early-return paths do not call `update_peak_pnl()`. Same consequence as H-3 during exchange outages.

**How to Fix:** Same — add `update_peak_pnl(session, cached_pnl)` before all miss/partial beat returns.

---

### H-5 · `mmm_monitor.py:1015,1018` — Safety "auto_close" and "stop" exits skip cleanup

**Severity:** HIGH
**File:** `webui/backend/routes/mmm/mmm_monitor.py`
**Lines:** 1015, 1018

**What's Wrong:**
```python
if action_type == 'auto_close':
    await self._auto_close_all(reason, emergency=True)
    return  # ← No peak update, save, or emit

elif action_type == 'stop':
    self.stop(reason)
    return  # ← No final emit or health record
```

**How to Fix:** Add cleanup block before each return (same pattern as C-1 fix).

---

### H-6 · `mmm_api.py:351–356` — `start()` endpoint rejects PAUSED sessions

**Severity:** HIGH
**File:** `webui/backend/routes/mmm/mmm_api.py`
**Lines:** 351–356

**What's Wrong:**
```python
if status not in ('IDLE',):  # Only IDLE allowed
    return jsonify({'error': 'Must be IDLE'}), 400
```

A PAUSED session cannot be re-started via the start endpoint. Users must manually transition state to IDLE first, which requires backend knowledge they shouldn't need.

**How to Fix:**
```python
if status not in ('IDLE', 'PAUSED'):
    return jsonify({'error': f'Cannot start from {status}. Must be IDLE or PAUSED.'}), 400
```

---

### H-7 · `mmm_api.py:389,514,533,579,1609` — WS emit fires after `save_session()` (race on fast reads)

**Severity:** HIGH
**File:** `webui/backend/routes/mmm/mmm_api.py`
**Lines:** 389, 514, 533, 579, 1609

**What's Wrong:**
Status is saved to storage, then the WebSocket event fires. If a client queries the REST API immediately on receiving the WS event, storage may not have fully flushed (on some filesystems/OS caches), returning the old status.

**Why It Matters:** Frontend shows correct status from WS but REST API returns stale status — inconsistent state for 1–2 seconds.

**How to Fix:** Either (a) ensure `save_session()` uses `fsync` before emit, or (b) include the new status directly in the WS payload so clients don't need to re-query.

---

### H-8 · `mmm_adopter.py:245` — Frozen position detection uses object identity (`is not`) not value equality

**Severity:** HIGH
**File:** `webui/backend/routes/mmm/mmm_adopter.py`
**Line:** 245

**What's Wrong:**
```python
frozen = [p for p in positions if p is not active]
```

`is not` checks memory address, not value. If `positions` is rebuilt or copied before this line (common after JSON round-trip), all positions incorrectly classify as frozen — including the active one.

**How to Fix:**
```python
# Option A: value equality
frozen = [p for p in positions if p != active]

# Option B: index tracking (most explicit)
active_idx = positions.index(active)
frozen = [p for i, p in enumerate(positions) if i != active_idx]
```

---

### H-9 · `mmm_monitor.py:651` — Position reconciliation runs while PAUSED

**Severity:** HIGH
**File:** `webui/backend/routes/mmm/mmm_monitor.py`
**Line:** 651 (reconciliation call before pause check)

**What's Wrong:**
`_reconcile_exchange_positions()` is called at the top of `_heartbeat()`, before the PAUSED state check. Phantom positions are auto-corrected while the user believes the session is frozen.

**Why It Matters:** User pauses to investigate a position mismatch; reconciliation silently auto-fixes (or misclassifies) positions before they can investigate.

**How to Fix:**
```python
# Reconcile only when not paused
if not self._paused:
    await self._reconcile_exchange_positions()
else:
    # Ensure force_recon fires on resume
    session.setdefault('_force_recon', True)
```

---

### H-10 · `mmm_state.py:518/mmm_storage.py` — `params` and session stored in separate columns; can desynchronize

**Severity:** HIGH
**File:** `webui/backend/routes/mmm/mmm_state.py` / `mmm_storage.py`

**What's Wrong:**
A hot-reload writes `params_json` independently of the full session save. The in-memory monitor session may have old params for up to one full heartbeat interval (90s) after a hot-reload completes.

**Why It Matters:** Critical safety params (`max_loss_amount`, `gamma_cap_enabled`, `vol_regime_enabled`) can be stale, leading to missed risk controls during a 90-second window.

**How to Fix (immediate mitigation):**
```python
# At start of _heartbeat(), reload params from storage
fresh_params = storage.get_session_params(self.session_id)
if fresh_params:
    session['params'].update(fresh_params)
```

---

### H-11 · `mmm_regime.py:613–746` — Regime engine public API has no try/except; crashes fall back to NORMAL

**Severity:** HIGH
**File:** `webui/backend/routes/mmm/mmm_regime.py`
**Lines:** 613–746

**What's Wrong:**
If `_update_vol_regime()` throws any exception, the caller's broad except block silently sets `_regime_action = ACTION_NORMAL`, treating a calculation crash as a safe market. A dangerous IV spike could be masked as "no action needed."

**How to Fix:**
```python
def update_vol_regime(self, session, iv_data, spot_price) -> str:
    try:
        return _update_vol_regime(session, iv_data, spot_price)
    except Exception as e:
        log.error(f"[RegimeEngine] vol_regime calculation failed: {e}", exc_info=True)
        # Return CURRENT regime, not NORMAL — don't downgrade safety
        return session.get('_vol_regime', VOL_NORMAL)
```

---

### H-12 · `mmm_activity.py:152–166` — Concurrent `os.rename()` calls overwrite each other

**Severity:** HIGH
**File:** `webui/backend/routes/mmm/mmm_activity.py`
**Lines:** 152–166

**What's Wrong:**
`tempfile.mkstemp()` creates unique temp files (correct), but two threads can both complete their write and call `os.rename()` near-simultaneously. The second rename silently discards the first thread's data.

**Why It Matters:** One heartbeat's activity entries are permanently lost with no error logged.

**How to Fix:**
```python
_activity_write_lock = threading.Lock()  # module-level

def _save_to_disk(self, activity=None):
    ...
    with _activity_write_lock:
        fd, tmp_file = tempfile.mkstemp(...)
        ...
        os.rename(tmp_file, ACTIVITY_FILE)
```

---

### H-13 · `MMMDashboard.js:1926` — `fullSession` passed to `<SessionDetail>` without null guard

**Severity:** HIGH
**File:** `webui/frontend/src/components/mmm/MMMDashboard.js`
**Line:** 1926

**What's Wrong:**
```javascript
<SessionDetail session={fullSession} wsData={wsData} />
// fullSession can be null (fetch failed / 404)
// SessionDetail accesses session.ce, session.pe without null check
```

**How to Fix:** `{fullSession && <SessionDetail session={fullSession} wsData={wsData} />}`

---

### H-14 · `MMMDashboard.js:1135–1141` — P&L display shows `$NaN` when backend returns `null`

**Severity:** HIGH
**File:** `webui/frontend/src/components/mmm/MMMDashboard.js`
**Lines:** 1135–1141

**What's Wrong:**
```javascript
const netPnl = realized + unrealized - fees;  // null + null - null = NaN
// ...
`$${netPnl.toFixed(2)}`  // → "$NaN"
```

**How to Fix:**
```javascript
const realized = session.realized_pnl ?? 0;
const unrealized = session.unrealized_pnl ?? 0;
const fees = session.total_fees ?? 0;
```

---

### H-15 · `MMMDashboard.js:1606–1624` — Non-404 errors in `fetchFull()` leave stale data silently

**Severity:** HIGH
**File:** `webui/frontend/src/components/mmm/MMMDashboard.js`
**Lines:** 1606–1624

**What's Wrong:**
Only 404 responses are handled. A 500 or network timeout logs to console but shows no UI error. `fullSession` remains stale while user reads outdated positions.

**How to Fix:**
```javascript
const [fetchError, setFetchError] = useState(null);
// In catch:
if (err.status !== 404) setFetchError(err.message);
// In render:
{fetchError && <Alert severity="warning">Data may be stale: {fetchError}</Alert>}
```

---

### H-16 · `mmm_monitor.py:513–549` — Exception handler in `_run_loop` skips peak P&L and session save

**Severity:** HIGH
**File:** `webui/backend/routes/mmm/mmm_monitor.py`
**Lines:** 513–549

**What's Wrong:**
When a heartbeat throws an unhandled exception, the except block logs and records a circuit-breaker failure but does not call `update_peak_pnl()` or `_save_my_session()`. The next heartbeat inherits the inconsistent pre-crash state.

**How to Fix:**
```python
except Exception as e:
    log.exception(f"Heartbeat error for {self.session_id}: {e}")
    self.session['last_error'] = str(e)
    self._circuit.record_failure(str(e))

    # Best-effort state preservation
    try:
        update_peak_pnl(self.session, self.session.get('unrealized_pnl', 0))
        self._save_my_session(self.session)
    except Exception as save_err:
        log.error(f"Failed to save state after heartbeat crash: {save_err}")
```

---

## MEDIUM Bugs

---

### mmm_monitor.py

#### M-1 · Line 1263 — Emergency exits bypass `_skip_to_pnl` tail (walkthrough, analytics, final save)

Emergency exits that set `_skip_to_pnl = True` correctly flow through the cleanup tail. But `auto_close` and `stop` action types use bare `return` instead, bypassing walkthrough generation (lines 1590–1618), analytics (1503–1527), and the final save (line 1621).

**Fix:** Change `auto_close` and `stop` action handlers to set `_skip_to_pnl = True` + `break` out of the adjustment loop rather than using `return`.

---

#### M-2 · Lines 594–1659 — `_session_lock` not held during heartbeat field updates

`_session_lock` is used in `pause()`, `resume()`, and `get_session_snapshot()` but NOT in `_heartbeat()` while modifying `self.session`. API threads calling `get_session_snapshot()` (which does acquire the lock) can see torn state mid-update.

**Fix:** Either document this as a known accepted race (API reads may lag one heartbeat), or wrap critical multi-field updates in `with self._session_lock:`.

---

#### M-3 · Line 213–215 — `start()` always emits `'IDLE' → 'RUNNING'` even when restoring PAUSED

```python
emit_status_change(self.session_id, 'IDLE', 'RUNNING', 'Monitor started')
# Emitted even if session is restored in PAUSED state
```

**Fix:**
```python
restored_status = 'PAUSED' if self._paused else 'RUNNING'
emit_status_change(self.session_id, 'IDLE', restored_status, f'Monitor started (restored: {restored_status})')
```

---

#### M-4 · Lines 195–204 — `session.get('ce', {})` not type-validated; crashes if `ce` is `None`

```python
analytics['initial_ce_lots'] = self.session.get('ce', {}).get('original_lots', 0)
# Crashes if session['ce'] is None (AttributeError: 'NoneType' has no attribute 'get')
```

**Fix:**
```python
ce_state = self.session.get('ce') or {}
analytics['initial_ce_lots'] = ce_state.get('original_lots', 0) if isinstance(ce_state, dict) else 0
```

---

### mmm_api.py

#### M-5 · Lines 1931–1932 — Bare `except: pass` during spot price fetch in adoption

```python
except Exception:
    pass  # spot_price stays 0.0 — wrong classification silently
```

**Fix:** `except Exception as e: log.warning(f"[{session_id}] spot price fetch failed during adoption: {e}")`

---

#### M-6 · Lines 2585–2586 — Bare `except: pass` on WS emit during manual reduce

Frontend goes stale — user sees success response but no live update fires.

**Fix:** `except Exception as e: log.warning(f"[{session_id}] WS emit failed on manual_reduce: {e}")`

---

#### M-7 · Lines 148–271 — Expiry not validated at session CREATE time

Invalid or missing expiry is only caught at `init-fresh` (400 mismatch), after the session already exists in storage. User wastes time filling init form before the error appears.

**Fix:** Validate expiry format (DDMMYYYY, parseable date) in `create_session_endpoint()` before `create_session()` is called.

---

#### M-8 · Lines 1150–1167 — `current_params` mutated in-place from a dict reference before `update_session()`

```python
current_params = session.get('params', {})  # Reference, not copy
current_params[key] = value  # Mutates session dict in place
storage.update_session(session_id, {'params': current_params})
```

If `update_session()` fails, mutations are lost but the in-memory session already has them.

**Fix:** `current_params = dict(session.get('params', {}))` — make a shallow copy first.

---

#### M-9 · Line 2511 — `apply_lifo_removals()` can return `None`; no null check before arithmetic

```python
avg_entry = apply_lifo_removals(side_state, group['records'])
group_realized = (avg_entry - fill_price) * group_lots * LOT_SIZE_BTC
# TypeError if avg_entry is None
```

**Fix:**
```python
avg_entry = apply_lifo_removals(side_state, group['records'])
if avg_entry is None:
    log.warning(f"[{session_id}] avg_entry is None for {side_key} — defaulting to 0")
    avg_entry = 0.0
```

---

#### M-10 · Lines 673–678 — `resume()` allows `RUNNING` status; error message says "Must be PAUSED"

`status not in ('PAUSED', 'RUNNING')` — but the error message only mentions PAUSED. Resuming a RUNNING session is a no-op but could trigger duplicate heartbeat registrations.

**Fix:** Restrict to PAUSED only, or update error message to match the allowed set.

---

#### M-11 · Line 3638 — `monitor.session['params']` mutated directly; creates split-brain with storage

```python
monitor.session.get('params', {})['perp_hedge_enabled'] = bool(new_value)
```

The monitor's in-memory session is updated directly AND storage is updated separately. They can diverge if either write fails.

**Fix:** Update storage only; let the monitor reload params from storage at next heartbeat.

---

### mmm_regime.py

#### M-12 · Line 129 — Off-by-one fragility in IV history indexing

`len(iv_history) > lookback` is the guard, then `iv_history[-lookback - 1][1]` accesses the item. This is correct for current logic but fragile — changing `lookback` or the deque maxlen without updating the guard could produce wrong historical IV comparisons.

**Fix:** Use explicit index calculation with `assert idx >= 0` guard.

---

#### M-13 · Line 160 — `avg_dt = 0` possible path → `math.sqrt(31_536_000 / 0)` ZeroDivisionError

`time_diffs` could theoretically contain all-zero values (two consecutive heartbeats with same timestamp due to clock issue).

**Fix:** `avg_dt = max(sum(time_diffs) / len(time_diffs) if time_diffs else 60, 1)`

---

#### M-14 · Lines 118–120 — Spot history stays empty if early spot prices are ≤ 0

```python
if spot_price > 0:
    spot_history.append(...)
# If first N beats have bad price → rv_window never reached → RV never computed
```

**Fix:** Track last valid spot price and use it as fallback:
```python
last_valid = session.get('_vol_last_valid_spot', 0)
effective_spot = spot_price if spot_price > 0 else last_valid
if effective_spot > 0:
    spot_history.append((now, effective_spot))
    session['_vol_last_valid_spot'] = effective_spot
```

---

### mmm_state.py

#### M-15 · Lines 226–237 — Direct dict access `p['lots']`, `p['strike']` in `recompute_side_lots()`

```python
'lots': p['lots'],    # KeyError on corrupted position record
'strike': p['strike'],
```

**Fix:** `'lots': p.get('lots', 0), 'strike': p.get('strike', 0)`

---

#### M-16 · Lines 250–260 — Same direct dict access in frozen positions block

`p['strike']`, `p['lots']`, `p['id']` — KeyError on corrupted position.

**Fix:** Replace with `.get()` and defaults.

---

#### M-17 · Lines 512–514 — `last_heartbeat`/`next_heartbeat` initialized `None`; callers can crash

```python
elapsed = (datetime.fromisoformat(session['last_heartbeat']) - now).total_seconds()
# TypeError if last_heartbeat is None
```

**Fix:** Either initialize to `datetime.now(timezone.utc).isoformat()` in `create_session()`, or add `if session.get('last_heartbeat'):` guards at every callsite.

---

#### M-18 · Line 216 — `positions` not type-validated after migration

```python
positions = side_state['positions']
for p in positions ...  # TypeError if positions is None or a string
```

**Fix:**
```python
positions = side_state.get('positions', [])
if not isinstance(positions, list):
    log.error(f"Invalid positions type {type(positions)} — resetting")
    positions = []
    side_state['positions'] = []
```

---

### mmm_adopter.py

#### M-19 · Lines 474–476 — Direct dict access in frozen position ledger append

```python
'strike': fp['strike'],     # KeyError if key missing
'lots': fp['lots'],
'entry_premium': fp['entry_price'],
```

**Fix:** `'strike': fp.get('strike', 0), 'lots': fp.get('lots', 0), 'entry_premium': fp.get('entry_price', 0)`

---

#### M-20 · Lines 520–526 — Expiry validation silently skips when `creation_expiry = ''`

```python
if creation_expiry and creation_expiry != expiry:
    raise ValueError(...)
# If creation_expiry is '' (falsy), check is skipped entirely
```

Wrong-expiry adoption proceeds silently when session was created without an expiry.

**Fix:**
```python
if expiry:
    if creation_expiry and creation_expiry != expiry:
        raise ValueError(f"Expiry mismatch: session={creation_expiry} adopt={expiry}")
    elif not creation_expiry:
        log.warning(f"[Adopter] Session has no creation_expiry; adopting with {expiry}")
```

---

### mmm_activity.py

#### M-21 · Line 151 — Directory created inside `_save_to_disk()`, not in `__init__()`

If the app crashes between `_activities.append()` and `os.makedirs()`, the activity is in memory but the directory doesn't exist — data cannot be persisted on next call.

**Fix:** Move `os.makedirs(os.path.dirname(ACTIVITY_FILE), exist_ok=True)` into `__init__()`.

---

#### M-22 · Lines 273–276 — `clear()` rebuilds deque via generator; loses ring-buffer continuity

```python
self._activities = deque(
    (a for a in self._activities if a.get('session_id') != session_id),
    maxlen=MAX_ACTIVITIES,
)
```

Reconstruction is not atomic. A concurrent `add()` between iteration and assignment can lose an entry.

**Fix:**
```python
with self._lock:
    to_keep = [a for a in self._activities if a.get('session_id') != session_id]
    self._activities.clear()
    for a in to_keep:
        self._activities.append(a)
```

---

#### M-23 · Lines 235–239 — Bare `except: pass` on WebSocket emit in `add()`

```python
except Exception:
    pass  # Silences ImportError, RuntimeError, TypeError — all real bugs
```

**Fix:**
```python
except ImportError:
    pass  # WS module not installed — acceptable
except Exception as e:
    log.warning(f"Activity WS emit failed: {e}")
```

---

#### M-24 · Lines 294–297 — `resolve_progress()` has same deque-reconstruction race as M-22

**Fix:** Same pattern — use `clear()` + re-append under lock.

---

### MMMConfigPanel.js

#### M-25 · Lines 261–266, 274 — `fetchExpiries()` dep on `selectedExpiry` overrides `sessionExpiry` prop

`useEffect` has `selectedExpiry` in its dependency array. Auto-select logic at lines 261–266 runs whenever `selectedExpiry` changes, potentially overwriting the `sessionExpiry` prop value.

**Fix:** Change dependency from `[selectedExpiry]` to `[sessionExpiry]`. Guard auto-select: `if (!selectedExpiry) { /* auto-select logic */ }`.

---

#### M-26 · Lines 319–320 — `setSelectedCe(result.ce)` without null check

If backend returns `success: true` but `ce`/`pe` is null, component stores null and downstream `selectedCe.premium` crashes.

**Fix:** `if (result.ce && result.pe) { setSelectedCe(result.ce); setSelectedPe(result.pe); } else { setError('Preview data incomplete'); }`

---

#### M-27 · Lines 602–624 — Symbol generation reads stale `selectedExpiry` on rapid expiry+strike change

React state batching means the symbol is generated against the old expiry if the user changes expiry and strike in rapid succession.

**Fix:** Regenerate symbols in a `useEffect` triggered by both `selectedExpiry` and the import strike fields, rather than inline in the onChange handler.

---

#### M-28 · Lines 434–439 — No client-side numeric validation on import fields

`parseFloat('abc')` returns `NaN`, which is sent to the backend. Backend may not strictly validate, causing silent import failures.

**Fix:** Before line 429: `if (isNaN(parseFloat(ce_strike)) || isNaN(parseFloat(ce_fill_price))) { setError('All fields must be valid numbers'); return; }`

---

#### M-29 · Lines 376–389 — Auto-start after init doesn't confirm persistence

`startSession()` is called immediately after `mmmService.initSessionFresh()` resolves. On a slow disk, the session file may not have been fully flushed before the monitor's first heartbeat tries to load it.

**Fix:** Add a 500ms delay or have the init endpoint confirm persistence before responding 200.

---

### MMMDashboard.js

#### M-30 · Lines 1117–1118 — `detailTab` not reset when `selectedSessionId` changes

Switching from a session on Tab 4 (P&L history) to a freshly started session shows the P&L tab, which is empty and confusing.

**Fix:** `useEffect(() => { setDetailTab(0); }, [selectedSessionId]);`

---

#### M-31 · Lines 176–181 — `SessionCard` countdown timer can fire after unmount

The interval depends on `session.expiry_time` in deps but not the `session` reference. Ref change without expiry change skips timer reset.

**Fix:** Add cleanup guard: `let mounted = true; return () => { mounted = false; clearInterval(id); };` and check `if (!mounted) return;` inside callback.

---

#### M-32 · Lines 1705–1709 — Both-sides alert handler falls back to `selectedSessionId`

```javascript
const alertSessionId = bothSidesAlert?.session_id
    || wsData.bothSidesAlert?.session_id
    || selectedSessionId;  // Fallback could be wrong session
```

**Fix:** Remove the `selectedSessionId` fallback. If no alert session_id is available, reject with an error: `setSnackbar({ message: 'No active alert to respond to', severity: 'error' })`.

---

#### M-33 · Lines 756–778 — `HeartbeatHealthPanel` shows stale data when session is paused

Health data stops polling when status !== 'RUNNING' but old data remains displayed with no staleness indicator.

**Fix:** Add `const isStale = status !== 'RUNNING' && health !== null;` and show a "(paused)" label on the health panel.

---

#### M-34 · Lines 471–480 — `CreateSessionDialog` import mode: no numeric validation

Same as M-28 — `parseFloat` on non-numeric import field sends NaN to backend.

**Fix:** Validate all import fields are numeric before calling the API.

---

#### M-35 · Lines 1786–1792 — WebSocket "Disconnected" shown as chip only; data tables show stale values

User can miss the connection chip and make trading decisions on stale data.

**Fix:**
```javascript
{connectionStatus !== 'connected' && (
  <Alert severity="warning" sx={{ mb: 2 }}>
    ⚠️ WebSocket disconnected — position data may be stale
  </Alert>
)}
```

---

## LOW Bugs

| # | File | Line | Severity | Issue | Fix |
|---|------|------|----------|-------|-----|
| L-1 | mmm_monitor.py | 218–223 | LOW | Watchdog registration failure is silent (non-fatal, but session may not auto-restart) | Add `log.error()` on failure |
| L-2 | mmm_monitor.py | 3167–3169 | LOW | Margin check exception returns `None`; heartbeat continues normally (correct but undocumented) | Add comment explaining fail-open design |
| L-3 | mmm_api.py | Throughout | LOW | Atomicity of `save_session()` not verified — depends on `mmm_storage.py` using temp+rename | Audit `mmm_storage.py` save path |
| L-4 | mmm_regime.py | 102–120 | LOW | Deque sometimes stored as deque in session, sometimes as list; inconsistent type | Always write `list(iv_history)` back, never store deque |
| L-5 | mmm_regime.py | 78,123,200 | LOW | `params.get('vol_lookback_beats', 5)` not type-checked; `None` from corrupt params causes TypeError | `lookback = int(params.get(...) or 5)` |
| L-6 | mmm_state.py | 656–661 | LOW | `initialize_side_from_entry()` silently overwrites existing side state on duplicate call | Add guard: if `original_lots > 0` already set, skip |
| L-7 | mmm_activity.py | 170–174 | LOW | Inner `except: pass` during temp file cleanup hides disk/permission errors | `except Exception as e: log.error(f"Temp cleanup failed: {e}")` |
| L-8 | MMMConfigPanel.js | 714–725 | LOW | Expiry dropdown allows change after `sessionExpiry` prop is set; mismatch only caught at submit | Disable dropdown when `sessionExpiry` is set |
| L-9 | MMMConfigPanel.js | 293–333 | LOW | Re-clicking "Find" while alternative strikes are selected silently discards manual selection | Show confirmation before re-previewing |
| L-10 | MMMDashboard.js | 135–166 | LOW | Expiry countdown goes negative if browser system clock adjusts | Clamp `diffMs = Math.max(diffMs, 0)` |
| L-11 | MMMDashboard.js | 1234–1240 | LOW | Peak P&L card shows no delta vs current P&L — user may not notice drawdown | Add sub-label: "Current: $X (↓ $Y from peak)" |

---

## Recommended Fix Order

### Phase 1 — Before Next Live Session
1. **C-1/C-2/C-3** — All 3 bare-return heartbeat emergency exits → add cleanup block
2. **C-4/C-5** — Enforce expiry in `create_session()` + parse `expiry_time`
3. **H-1** — Fix premium calculation missing `LOT_SIZE_BTC` in `mmm_api.py:2247`
4. **C-8** — Add `threading.RLock()` to `MMMActivityLog`
5. **C-9** — Add WebSocket null guards in MMMDashboard

### Phase 2 — High Priority Sprint
6. **C-6** — Guard `create_session()` against overwriting existing sessions
7. **H-6** — Allow PAUSED in `start()` endpoint
8. **H-9** — Skip reconciliation while paused
9. **H-11** — Wrap regime engine public API in try/except with explicit error logging
10. **H-12** — Add lock around activity log `os.rename()` critical section
11. **M-15/M-16** — Replace direct dict access with `.get()` in `recompute_side_lots()`
12. **H-16** — Add best-effort state save in heartbeat exception handler

### Phase 3 — Medium Priority
13. **H-10** — Implement params reload strategy before critical safety decisions
14. **M-2** — Document or fix session lock race between heartbeat and API reads
15. **M-20** — Strengthen expiry validation in adopter for empty `creation_expiry`
16. **M-5/M-6/M-23** — Replace all bare `except: pass` with logged warnings
17. Remaining M-class frontend null checks and validation gaps
18. L-class cleanup in follow-up

---

*Generated by automated code audit · 2026-02-23*
