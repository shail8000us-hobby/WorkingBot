# MMM Codebase — Remaining Work Plan

> **Status:** P0 + P1 + partial P2 complete as of commit `313d6aa33` (Feb 27, 2026)  
> **Author:** Senior Developer Audit → Phased Execution Plan  
> **Branch:** SSR

---

## ✅ Already Done (Do Not Repeat)

| Priority | # | Fix | Commit |
|----------|---|-----|--------|
| P0 | 1 | `get_session_snapshot()` → `deepcopy()` to prevent torn reads | `efafcc17e` |
| P0 | 2 | `_migrate_side_to_positions()` two-phase flag (crash-safety) | `efafcc17e` |
| P0 | 3 | Checksum mismatch → `_checksum_warning` flag + WebSocket safety alert | `efafcc17e` |
| P0 | 4 | `apply_lifo_removals()` deep-copy + atomic rollback | `efafcc17e` |
| P0 | 5 | `_being_closed` in-flight guard on positions in `mmm_close_at_5` | `efafcc17e` |
| P0 | 6 | `_parse_fill_price()` helper — fill-price deduplication | `efafcc17e` |
| P1 | 7 | `mmm_activity.py` monotonic activity ID counter | `efafcc17e` |
| P1 | 8 | `mmm_reversal.py` suppress detection during wind-down | `efafcc17e` |
| P1 | 9 | `mmm_reversal.py` cap `reversal_history[]` at 50 entries | `efafcc17e` |
| P2 | 15a | `test_mmm_trigger.py` — 31 new tests | `313d6aa33` |
| P2 | 15b | `test_mmm_wind_down.py` — 23 new tests | `313d6aa33` |
| P2 | 15c | `test_mmm_state.py` — 21 new tests | `313d6aa33` |
| P2 | 16 | `sys.path.insert()` made idempotent (guarded) | `313d6aa33` |
| P2 | 18 | `OUTCOME_BOTH` documented (confirmed not dead) | `313d6aa33` |
| P2 | 19 | `reversal_history[]` cap (same as P1 #9 above) | `efafcc17e` |
| P2 | 20 | `calculate_lots_with_buffer()` deprecated + `get_initializer()` lock | `313d6aa33` |

---

## 🔴 Remaining P1 — Do First (Stability)

These were identified in the audit as P1 but not yet implemented.

---

### P1-A · Safety Checks Fire 2-3× Per Degraded Heartbeat

**File:** `mmm_monitor.py`  
**Lines:** ~841–851, ~1092–1096  
**Risk:** False safety events (spurious auto-pauses, incorrect alerts) in degraded network conditions.

**Problem:**  
`self._safety.run_all_checks()` is called up to **three times** per heartbeat in the miss/partial-beat paths:
1. In the "partial beat" path
2. In the "miss beat" path
3. In the normal full-beat path

Auto-resume logic is also duplicated across all three locations.

**Plan:**
1. Extract a `_run_safety_phase(session, ce_now, pe_now)` private method in `mmm_monitor.py`.
2. Replace all 3 inline safety-check blocks with a single call.
3. Add a `_safety_ran_this_beat` boolean flag on `self` at the start of each beat, set to `True` after first safety run, guard the remaining paths with `if not self._safety_ran_this_beat`.
4. Unit test: mock `_safety.run_all_checks` and assert it's called exactly once per partial/miss beat.

**Estimated effort:** 2–3 hours  
**Risk:** Low — pure deduplication, no logic change.

---

### P1-B · Cooldown Duration Hardcoded to `adjustment_interval × 2`

**File:** `mmm_reversal.py`  
**Risk:** A session with `adjustment_interval=3600s` (1h) gets a **2-hour** blanket reversal cooldown that can't be tuned without changing the interval itself.

**Plan:**
1. Add `reversal_cooldown_seconds` to `DEFAULT_PARAMS` in `mmm_state.py`:
   ```python
   'reversal_cooldown_seconds': 0,   # 0 = use adjustment_interval * 2 (legacy behaviour)
   ```
2. In `mmm_reversal.activate_cooldown()`:
   ```python
   configured = params.get('reversal_cooldown_seconds', 0)
   cooldown_secs = configured if configured > 0 else params.get('adjustment_interval', 300) * 2
   ```
3. Expose `reversal_cooldown_seconds` in the WebUI session-params panel.
4. Add a test for both `cooldown_seconds=0` (legacy) and `cooldown_seconds=120` (explicit).

**Estimated effort:** 2 hours  
**Risk:** Very low — additive param with backward-compatible default.

---

### P1-C · `_atm_wind_down_triggered` Never Cleared

**File:** `mmm_monitor.py`  
**Risk:** After a full wind-down cycle (all positions closed and a new session round starts), the `_atm_wind_down_triggered=True` flag persists. ATM wind-down can never re-arm because the flag is already set.

**Plan:**
1. In `mmm_monitor.py`, find where `total_lots == 0` / both-sides-closed is detected.
2. Add: `session.pop('_atm_wind_down_triggered', None)` at that point.
3. Similarly, clear it when a new initialization is triggered (`session['strategy_status'] == 'INITIALIZED'`).
4. Add a regression test in `test_mmm_integration.py` asserting the flag is cleared after close.

**Estimated effort:** 1 hour  
**Risk:** Very low — targeted flag reset.

---

### P1-D · Partial Fill Not Propagated to Position Ledger

**File:** `mmm_executor.py` → `mmm_engine.py` (callers)  
**Risk:** If `smart_execute()` returns `filled_size < size` (partial fill), callers assume `size` lots were filled and update the position ledger with the wrong lot count — exchange reality diverges from internal state.

**Plan:**
1. **Audit all callers** of `smart_execute()` in `mmm_engine.py`, `mmm_wind_down.py`, `mmm_close_at_5.py`.
2. For each caller, check whether `result['filled_size']` is used or `result` is trusted as full fill.
3. Add a guard in each caller:
   ```python
   if result['filled_size'] < size:
       log.warning(f"Partial fill: requested {size}, got {result['filled_size']}")
       # Use result['filled_size'] for position update, not size
       actual_lots = result['filled_size']
   ```
4. In `mmm_executor.py`'s `smart_execute()`, ensure `filled_size` is always set in the returned dict even for the "timeout" path.
5. Add a test: mock executor to return `filled_size=3` when `size=5` was requested; assert position ledger shows 3.

**Estimated effort:** 3–4 hours  
**Risk:** Medium — touches order execution paths. Test thoroughly before deploying.

---

## 🟡 Remaining P2 — Quality Sprint

These improve code quality and maintainability without touching trading logic.

---

### P2-A · `mmm_monitor.py` God Object — Phase 1 Extraction

**File:** `mmm_monitor.py` (5,023 lines)  
**Risk to skip:** Every future feature adds to an already unmaintainable file.

**Plan — Safe Incremental Extraction (3 phases):**

#### Phase 1 — Extract `_finalize_heartbeat()` (Low risk, 1–2h)
The "cleanup before return" pattern appears 5+ times. Extract it:
```python
def _finalize_heartbeat(self, session, ce_now, pe_now, beat_start_mono, outcome_label):
    self._update_peak_pnl(session)
    self._save_session_async(session)
    self._record_beat(session, beat_start_mono)
    self._emit_heartbeat(session, ce_now, pe_now, outcome_label)
```
Replace all 5+ inline blocks with a call to this method.

#### Phase 2 — Extract Price Fetching (Low risk, 2–3h)
Move `_fetch_spot_price()`, `_fetch_ce_pe_premiums()`, and `_fetch_fresh_orderbook_quotes()` into a new file `mmm_price_fetcher.py`. Import them back into `mmm_monitor.py`.

#### Phase 3 — Extract P&L Calculation (Medium risk, 3–4h)
Move `_calculate_session_pnl()`, `_calculate_portfolio_delta()` into a new `mmm_pnl.py`. These are pure calculations with no side effects — safe to extract.

> **Do NOT attempt to extract the full heartbeat loop yet.** That requires a deeper architectural review and is Phase 4+ work.

---

### P2-B · Socket.IO Room Isolation

**Files:** `mmm_websocket.py` (backend) + `MMMContext.js` (frontend)  
**Risk:** All clients receive all session events. With 5+ sessions active, every client processes 5× the heartbeat traffic.

**Plan:**
1. **Backend** — in `mmm_websocket.py`, emit to a room:
   ```python
   socketio.emit('mmm_heartbeat', payload, room=f'session_{session_id}', namespace='/')
   ```
2. **Backend** — add a `join_session_room` Socket.IO event:
   ```python
   @socketio.on('join_session')
   def on_join_session(data):
       join_room(f"session_{data['session_id']}")
   ```
3. **Frontend** — in `MMMContext.js`, after connecting, emit `join_session` for the active session.
4. Test: open two browser tabs for two different sessions; verify each only receives its own heartbeats.

**Estimated effort:** 3–4 hours  
**Risk:** Medium — requires coordinated frontend + backend change. Deploy both atomically.

---

### P2-C · Missing Test Coverage

Still need tests for:

| Module | What to test | Priority |
|--------|-------------|---------|
| `mmm_initializer.py` | Strike ranking/scoring formula, `normalize_expiry()` edge cases, `validate_manual_selection()` zero-bid path | High |
| `mmm_executor.py` | `_parse_fill_price()` with NaN/Inf/empty inputs, partial fill propagation | High |
| `mmm_storage.py` | SQLite migration from JSON, checksum mismatch, `sort_keys` serialization | Medium |
| `mmm_watchdog.py` | Thread liveness check, restart backoff, max-restarts → PAUSED | Medium |
| `mmm_safety.py` | Each of the 7 safety check functions in isolation | Medium |

**To run existing + new tests:**
```bash
cd webui/backend/routes/mmm/tests
PYTHONPATH=/path/to/WorkingBot python3 -m pytest --import-mode=importlib --rootdir=. -v
```

---

### P2-D · `mmm_storage.py` — `sort_keys` Checksum Stability

**File:** `mmm_storage.py`  
**Risk:** Checksum could differ between Python runtimes if dict serialization order varies.

```python
# Current (fragile):
json.dumps(data, default=str)

# Fix:
json.dumps(data, sort_keys=True, default=str)
```

**Estimated effort:** 15 minutes  
**Risk:** None — purely additive.

---

### P2-E · Dead Code Cleanup

| Item | File | Action |
|------|------|--------|
| Tombstone comment `# NOTE: Proactive wind-down ... was removed` | `mmm_monitor.py` ~line 1052 | Delete — git history preserves the why |
| `_force_event = threading.Event()` — set but never `.set()` called | `mmm_monitor.py` `__init__` | Remove or implement the force-heartbeat feature |
| `# D: Both → user decides` original comment replaced | `mmm_trigger.py` | Done already |
| `close_5_enabled` vs new unified close-at-5 logic | `mmm_state.py` | Audit whether this param is still read anywhere |
| `enable_reversal` flag — if always active, remove | `mmm_state.py` | Search all callers; if nil, deprecate |
| `perp_hedge_*` params in non-perp sessions | `mmm_state.py` | Move to feature-flag block |

---

## 🟢 P3 Backlog — Do When Time Permits

These are improvements, not fixes. None block trading.

| # | What | File | Notes |
|---|------|------|-------|
| P3-1 | **Structured JSON logging** | All modules | Add `python-json-logger`; emit `session_id`, `event_type`, amounts as separate JSON fields. Invaluable for post-crash analysis. |
| P3-2 | **Dry-run / paper-trading mode** | `mmm_executor.py` | `USE_PAPER_FILLS=True` env flag → logs order without placing. Critical for CI testing and new session verification. |
| P3-3 | **`validate_session()` integrity check** | `mmm_state.py` | Call after migrations + saves. Assert: lots ≥ 0, positions sum matches `total_lots`, no duplicate position IDs. |
| P3-4 | **`clear_stale_snapshots()`** | `mmm_trigger.py` | Remove trigger snapshot entries for strikes no longer in `positions[]`. Call after any position reduction or strike shift. |
| P3-5 | **Watchdog → Telegram on restart** | `mmm_watchdog.py` | Use existing `mmm_telegram.py`. Send alert when watchdog triggers restart. Operators currently have no out-of-band notification. |
| P3-6 | **Frontend session map: `Map<id, session>`** | `MMMContext.js` | Replace flat `sessions[]` array with a `Map` keyed by `session_id`. O(1) lookup instead of O(n) scan per heartbeat. |
| P3-7 | **`HeartbeatPayload` dataclass** | `mmm_websocket.py` | `emit_heartbeat()` has 10+ positional args. A dataclass would make callers self-documenting and prevent arg ordering bugs. |
| P3-8 | **SQLite connection pooling** | `mmm_storage.py` | Keep one connection per thread via `threading.local()` instead of `sqlite3.connect()` per call. |
| P3-9 | **`_wind_down_active` cached per heartbeat** | `mmm_monitor.py` | `is_wind_down_active()` is called multiple times per beat with identical results. Cache the result at beat start in `self._hb_wind_down_active`. |
| P3-10 | **React Error Boundary** | `MMMContext.js` | Wrap `MMMProvider` consumers in an Error Boundary. A malformed heartbeat payload currently unmounts the entire MMM UI. |
| P3-11 | **`compact_old_sessions()`** | `mmm_storage.py` | Prune sessions older than N days from SQLite. DB grows unbounded otherwise. |
| P3-12 | **Watchdog dynamic check interval** | `mmm_watchdog.py` | `_check_interval = min(30, beat_timeout / 2)` — faster detection for rapid-mode sessions (5s intervals). |
| P3-13 | **Restart count persistence** | `mmm_watchdog.py` | Save `_restart_count` to session storage so max-restart protection survives backend restarts. |
| P3-14 | **`get_activity_by_id()`** | `mmm_activity.py` | Frontend currently scans the full list for ID lookup. An indexed O(1) function eliminates this. |
| P3-15 | **Adaptive dedup interval per activity type** | `mmm_activity.py` | `regime_control` events are very noisy; they need a longer dedup window (e.g. 60s) than the global `_DEDUP_INTERVAL_SECS=30`. |

---

## 📋 Recommended Execution Order

```
Week 1 — Stability (P1)
  └── P1-C  _atm_wind_down_triggered never cleared    (1h, very low risk)
  └── P1-B  Cooldown duration configurable            (2h, very low risk)
  └── P1-A  Safety checks fire 2-3× per beat          (3h, low risk)
  └── P1-D  Partial fill not propagated               (4h, medium risk — test thoroughly)

Week 2 — Quality (P2)
  └── P2-D  sort_keys checksum fix                    (15 min, zero risk)
  └── P2-E  Dead code cleanup                         (2h, zero risk)
  └── P2-A  Monitor: extract _finalize_heartbeat()    (2h, low risk)
  └── P2-A  Monitor: extract price fetching           (3h, low risk)
  └── P2-C  Test coverage: initializer + executor     (4h, additive)

Week 3 — Architecture (P2 continued)
  └── P2-B  Socket.IO rooms (backend + frontend)      (4h, medium risk)
  └── P2-A  Monitor: extract P&L calculation          (4h, medium risk)
  └── P2-C  Test coverage: storage + watchdog         (3h, additive)

Ongoing Backlog (P3)
  └── P3-2  Dry-run mode in executor                  (high value for CI)
  └── P3-5  Watchdog Telegram alerts                  (high operator value)
  └── P3-1  Structured JSON logging                   (high for debugging)
  └── Others as time permits
```

---

## 🛑 Things to NEVER Change Without Extensive Testing

The following code paths are critical and have caused production issues before. Any change here must be reviewed extremely carefully:

1. **`mmm_engine.py`** — `calculate_standard_loss()` and `calculate_reversal_loss()` — These drive all adjustment decisions. A one-line change here can cause over- or under-hedging.

2. **`mmm_trigger.py`** — `evaluate_triggers()` — This is THE core decision gate. The percentage threshold math and `TRIGGER_PCT_FLOOR` must not be touched without a full test suite run.

3. **`mmm_state.py`** — `recompute_side_lots()` — This rebuilds all derived state from `positions[]`. Any bug here corrupts the entire session view.

4. **`mmm_executor.py`** — `smart_execute()` — This places real exchange orders. The 60s fill timeout, reprice logic, and cancel paths must be tested with mocks before any change.

5. **`mmm_monitor.py`** — The heartbeat loop — Any refactor of the main beat loop must be validated against: normal beat, miss beat, partial beat, ATM close, both-sides-closed, safety-triggered-pause scenarios.

---

## 🔧 How to Run Tests

```bash
# Run all MMM unit tests (from project root):
cd /path/to/WorkingBot/webui/backend/routes/mmm/tests
PYTHONPATH=/path/to/WorkingBot \
  python3 -m pytest --import-mode=importlib --rootdir=. -v

# Run a specific test file:
PYTHONPATH=/path/to/WorkingBot \
  python3 -m pytest test_mmm_trigger.py -v --tb=short --import-mode=importlib --rootdir=.

# Run the full project test suite (requires Flask app available):
cd /path/to/WorkingBot
python3 -m pytest tests/ -v
```

---

> **Last updated:** Feb 27, 2026  
> **Commits referenced:** `efafcc17e` (P0/P1), `313d6aa33` (P2)  
> **Total tests added:** 95 (trigger: 31, wind-down: 23, state: 21, previously existing: 20+)
