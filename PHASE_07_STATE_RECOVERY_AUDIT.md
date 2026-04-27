# PHASE 07 — State & Recovery Audit
**Lead Agent:** State & Recovery Agent
**Status:** COMPLETE
**Date:** 2026-04-26
**Prior Phases Read:** Phase 01–06

---

## Executive Summary

The MMM state system is well-architected. SQLite WAL mode, dual params+data JSON columns, checksum v2 corruption detection, and the watchdog supervisor form a solid foundation. The three-layer stale monitor guard (H-4 generation, `_run_loop` primary, G5 guardian) was verified intact in Phase 4 and remains the architectural highlight of the recovery system. The primary structural gap is in watchdog restart reconciliation: it corrects scalar `total_lots`/`active_lots` from ledger DB truth, but the `positions[]` array is not rebuilt — and the very next heartbeat's `recompute_side_lots()` call reverts the corrected scalars back to the stale array sum, making the reconciliation ephemeral.

**State & Recovery Architecture Grade: B+** — foundation is solid; reconciliation fix has a structural reversion gap.

---

## 1. Storage Layer — `mmm_storage.py`

### 1.1 Schema

SQLite table `mmm_sessions` with:
- `session_id TEXT PRIMARY KEY`
- `params_json TEXT` — strategy parameters (separate column for index/query)
- `data_json TEXT` — all other session state
- `strategy_type TEXT DEFAULT '0DTE'` — denormalized column added by migration
- `created_at`, `updated_at` timestamps
- WAL mode enabled on startup

The params/data split prevents large param sets from bloating delta-diffing on saves.

### 1.2 Strategy Type Derivation on Load

`_derive_strategy_type_legacy_aware()` handles pre-migration sessions:
- If stored `strategy_type == '0DTE'` (the migration column default) but legacy params markers (`_preset_source`, `dte_category`) indicate another strategy → trusts legacy markers
- Correct for old sessions created before the `strategy_type` column existed
- `_derive_strategy_type_strict()` is used for all other cases

### 1.3 FillSync Double-Booking Retroactive Fix

`_apply_retroactive_fixes_on_startup()` runs on every backend start:
- Reads all sessions, applies FillSync correction (idempotent; sets `_fillsync_double_booking_corrected=True`)
- Recalculates checksums against corrected state
- Prevents `[CORRUPTION RISK]` false alarms that would otherwise fire on every load of un-patched sessions

**Finding A7-05 (P3):** Checksum recalculation in `_apply_retroactive_fixes_on_startup()` uses `session['params'] = json.loads(row['params_json'])`. If `params_json` is corrupted (empty or malformed), the checksum is calculated against `{}`. When the session is loaded normally (which merges params from the authoritative `params_json` column), the re-derived checksum won't match, producing [CORRUPTION RISK] warnings on every load. The corruption of params_json would cascade as a false-alarm flood rather than a clean failure.

### 1.4 Checksum System

Checksum v2 covers `realized_pnl`, `total_fees`, session_id, and strategy_type. Detects data corruption between saves.

---

## 2. Session State — `mmm_state.py`

### 2.1 Create Session Path

`create_session()` merges user `params` into `DEFAULT_PARAMS`, then:
1. Strips `strategy_type` from params (it is a top-level identity field, not a param)
2. Applies DTE preset if `dte_category` is set (via `mmm_dte_presets.apply_preset()`)
3. Derives `strategy_type` from the merged params
4. Initialises `ce`/`pe` side state via `create_side_state()`

### 2.2 DEFAULT_PARAMS Backfill on Restart

In `MMMMonitor.__init__()` (`mmm_monitor.py:346-351`):
```python
for _k, _v in _DP.items():
    session_params.setdefault(_k, _v)
```
New params added to `DEFAULT_PARAMS` after a session was created are silently backfilled with their defaults on every backend restart. Existing operator values are never overwritten (`setdefault`).

**Finding A7-03 (P2):** Params **removed** from `DEFAULT_PARAMS` remain in `session['params']` indefinitely — no eviction path. Over a session's lifetime, deleted params accumulate as ghosts. Any module doing `params.get('old_param')` would find the stale value rather than falling through to the default. Low risk now (no module reads deleted params intentionally) but becomes a maintenance hazard as the param surface grows.

### 2.3 Position Ledger — `recompute_side_lots()`

`recompute_side_lots()` is `@sealed` and is the single source of truth for lot counts. It:
1. Sums `p.get('lots', 0)` across `side['positions']`
2. Normalises positions at non-active strikes (shifts them to the active strike's frozen pool)
3. Sets `total_lots`, `active_lots`, `frozen_total_lots`

Called every heartbeat at the start of `_heartbeat()`. All lot scalars derive from `positions[]`.

### 2.4 Fix #23 Migration

`_migrate_side_to_positions()` lazily migrates old 3-array format (`open_lots[]`, `close_lots[]`, `strike_lots[]`) to the canonical `positions[]` dict format. Runs at session load. Idempotent via `_positions_migrated` flag.

---

## 3. Watchdog — `mmm_watchdog.py`

### 3.1 Detection Criteria

For RUNNING sessions:
1. **Thread liveness**: `_running=True` but thread not alive → dead thread
2. **Beat timeout**: `seconds_since_last_beat > adjustment_interval × BEAT_TIMEOUT_MULTIPLIER (3×)`

For EXITING sessions: stuck exit_all detection (thread dead or beat timeout while status=EXITING).

### 3.2 Restart Flow

1. `stop()` old monitor → `join(15s)` — mirrors the H-4 fix in `start_session_monitor()`
2. F5 deferred restart: 30s settlement wait (non-blocking via `_pending_restart_at` dict) before executing restart
3. Load `fresh_session` from storage (authoritative DB state)
4. Increment `_monitor_generation` → any stale old-thread save is rejected by H-4 guard
5. Reconciliation: compare memory `total_lots` vs ledger DB `total_lots` per side
6. `start_session_monitor(sid, fresh_session, context='monitor_restore')` — warm restart
7. Exponential backoff: base=30s, multiplier=2×, max=600s

After MAX_RESTARTS_PER_SESSION (10), session is set to PAUSED (not STOPPED) — operator can resume via UI.

**Finding A7-06 (P2 — confirmed resolved):** `_watchdog_restarts` counter IS reset to 0 on manual PAUSED→RESUME via `mmm_api.py:1616`. An operator resuming after 10 failures gets a fresh set of 10 restart attempts. **Not a gap.**

### 3.3 Reconciliation — the P1 Gap

**Finding A7-01 (P1):** The watchdog reconciliation (`_restart_monitor()` lines 410–440) corrects `total_lots` and `active_lots` by comparing in-memory values against `get_session_lots_by_side(sid)` (ledger DB truth). It patches:
```python
fresh_session[side_key]['total_lots'] = db_total
fresh_session[side_key]['active_lots'] = max(db_total - frozen, 0)
```

However, `positions[]` — the canonical array that `recompute_side_lots()` reads — is **not updated**. On the first heartbeat after restart, `recompute_side_lots()` is called and re-derives `total_lots` from the unchanged `positions[]`, **reverting the reconciliation within seconds** of the new monitor starting.

**When this matters:** A fill was recorded in the ledger DB by fill_sync (or WS executions) between the last session save and the monitor crash. The persisted session's `positions[]` doesn't include that fill. After restart, reconciliation patches the scalar, but `positions[]` still lacks the entry → first `recompute_side_lots()` call undoes the patch.

**Consequence:** Ghost positions (exposure on exchange not tracked by bot) survive the watchdog restart. Max loss, lot limits, and P&L tracking remain blind to those lots — the exact failure mode of the 2026-03-24 incident, via a different pathway.

The correct fix requires rebuilding `positions[]` from the ledger DB after reconciliation, not just patching scalar fields.

### 3.4 EXITING Session Handling

When `status == 'EXITING'` and the monitor is stuck, the watchdog:
1. Sets `_exit_all_partial = True`
2. Calls `_build_failed_list(session)` to enumerate affected positions
3. Saves STOPPED state to DB
4. Fires critical Telegram + WebSocket alert

**Finding A7-04 (P2):** `_build_failed_list()` is called via a late import inside the `if not session.get('_exit_all_failed_positions')` block. If the import or the function throws, the exception propagates to the outer `_check_monitor()` try/except (line 162), which logs `log.error()` and returns — without setting `_exit_all_partial` or calling `self._emit_alert()`. The operator receives no alert and no partial-exit flag. While `_build_failed_list` is unlikely to fail, the error handling is fragile for the highest-stakes code path.

---

## 4. Session Startup Path — `mmm_monitor.py` `__init__`

On every `MMMMonitor.__init__()` (fresh start or watchdog restart):

1. **Half-roll detection**: checks for `HALF_ROLL_PENDING_PHASE_B` / `HALF_ROLL_PENDING_PHASE_A` states. If detected: sets `strategy_status = 'STOPPED'`, pauses trading, fires Telegram alert, returns early without launching thread. (C-3 FIX — prevents trading in partial-roll state)

2. **DEFAULT_PARAMS backfill**: adds new params with `setdefault` — operator values never overwritten

3. **Reverse state guard**: `if '_reverse' not in self.session: initialize_reverse_state(session)` — safe on restore, never overwrites live reverse state

4. **God Layer init**: `self._god.initialize(self.session)` — idempotent, adds `_god` block if absent

5. **H-4 generation increment**: `session['_monitor_generation'] += 1` — seals this instance as the authoritative one; all stale saves from prior generation will be rejected

6. **Straddle credit computation**: computes `_straddle_initial_credit` from current positions if absent or zero-valued (without `_straddle_credit_v2` flag)

**Finding A7-02 (P2):** `_straddle_initial_credit` is conditionally re-computed on startup if the value is 0 **and** `_straddle_credit_v2` is absent. For a session that has undergone partial rolls (some positions closed, new ones opened), the current `positions[]` reflects post-roll state. Re-computing from post-roll `positions[]` yields a lower initial credit than was actually received at entry. Gate 10 in `_check_pure_roll_gates()` checks `net_pnl >= -straddle_roll_min_credit_pct × initial_credit` — a lower baseline makes Gate 10 more permissive, allowing additional rolls even when net loss already exceeds the safety threshold. The `_straddle_credit_v2` flag prevents this for sessions already correctly computed (v2 flag set after first correct computation), but old sessions or sessions where the initial entry was zero-premium are unprotected.

---

## 5. Architecture Issues — Phase 7

| ID | Problem | Risk | Priority |
|---|---|---|---|
| A7-01 | Watchdog reconciliation patches `total_lots`/`active_lots` from ledger DB but does NOT rebuild `positions[]`; first heartbeat's `recompute_side_lots()` reverts the correction | Ghost positions survive watchdog restart (same exposure as 2026-03-24 incident via different path) | P1 |
| A7-02 | `_straddle_initial_credit` re-computed from post-roll `positions[]` if `_straddle_credit_v2` flag absent; lower basis → Gate 10 more permissive | Roll loss-abort fires too late on sessions lacking v2 flag | P2 |
| A7-03 | Params removed from `DEFAULT_PARAMS` persist forever in `session['params']`; no eviction | Ghost param values may shadow new logic reading those key names | P2 |
| A7-04 | EXITING stuck-detection: if `_build_failed_list()` throws, exception silently escapes, `_exit_all_partial` not set, no alert fired | Operator has no position list on stuck-exit; no visible alert | P2 |
| A7-05 | `_apply_retroactive_fixes_on_startup()` recalculates checksums against `params_json`; corrupted `params_json` → cascading [CORRUPTION RISK] false alarms masking real corruption | False alarms desensitize operator to real checksum failures | P3 |

---

## 6. Positive Findings

1. **Three-layer stale monitor guard** — H-4 generation, `_run_loop` primary, G5 guardian all intact (verified Phase 4)
2. **`_watchdog_restarts` reset on resume** — `mmm_api.py:1616` resets counter to 0 on PAUSED→RESUME; operator gets fresh 10 attempts after manual intervention
3. **F5 deferred restart** — 30s non-blocking settlement wait prevents watchdog restart racing with in-flight orders
4. **C-3 FIX: Half-roll detection at startup** — trading blocked if roll partially completed; also fires on watchdog restart since `__init__` re-runs
5. **DEFAULT_PARAMS backfill uses `setdefault`** — new param defaults backfilled without ever overwriting operator-configured values
6. **`initialize_reverse_state()` guard** — `if '_reverse' not in self.session` — never overwrites live reverse positions
7. **`_straddle_credit_v2` flag** — prevents re-computation for sessions that have already been correctly computed
8. **EXITING session watchdog detection** — stuck `exit_all` is now visible and alerted (previously invisible; positions could remain open on exchange without any alarm)
9. **SQLite WAL mode** — concurrent reads don't block write path; safe for high-frequency heartbeats
10. **Strategy type migration** — `_derive_strategy_type_legacy_aware()` correctly handles pre-migration sessions without misidentifying genuine 0DTE sessions

---

## 7. Pass Criteria Checklist

- [x] Storage schema reviewed (SQLite WAL, dual params+data columns, checksum v2)
- [x] Session creation and DEFAULT_PARAMS backfill path verified
- [x] `recompute_side_lots()` as single source of truth confirmed (@sealed)
- [x] Watchdog lifecycle: detection, deferred restart, reconciliation, EXITING handling
- [x] Startup path: half-roll detection, reverse state guard, generation increment
- [x] Reconciliation structural gap documented (A7-01)
- [x] Architecture Issue Register updated (Section 5)

**Phase 7 Status: PASSED. One P1 gap (reconciliation reversion) requires a positions[] rebuild fix before capital scaling.**
