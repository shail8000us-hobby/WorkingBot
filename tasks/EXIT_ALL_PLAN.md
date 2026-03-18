# GLOBAL GRACEFUL EXIT — Implementation Plan

**Feature:** `EXIT ALL` — Single control to close all MMM positions and stop the session
**Status:** Implemented
**Files changed:** 8 backend files + 1 frontend component + 1 new module

---

## Design Principles

- **Core engine is untouched.** `close_position()`, `_heartbeat_inner()`, the guardian invariants, and all existing session lifecycle methods are preserved exactly as-is.
- **Additive only.** All new behavior lives behind the `EXITING` status gate. The `RUNNING` heartbeat path is 100% unchanged.
- **Reuse, don't duplicate.** `close_position()` is called with `mechanism='exit_all'` — no new closing logic is written.
- **Always reaches STOPPED.** Whether exit succeeds fully, partially, or throws an exception, the session terminates cleanly.

---

## 1. High-Level Flow

```
[1] User clicks "Exit Strategy" button in UI
      ↓
[2] Frontend shows confirmation modal with live position counts
      ↓
[3] POST /api/mmm/session/<id>/exit_all
      ↓
[4] Backend validates (not EXITING/STOPPED), then:
    - Set session['_exit_all_requested'] = True
    - Set session['strategy_status'] = 'EXITING'
    - Enqueue audit event: EXIT_ALL_INITIATED
    - Call monitor.force_heartbeat()
    - Return HTTP 202 Accepted
      ↓
[5] Next heartbeat detects EXITING at the top of _heartbeat_inner()
    - Skips ALL normal trading logic
    - Calls await self._run_exit_all()
      ↓
[6] _run_exit_all() — round-based closing:
    - Enumerates ALL open positions (both sides, all types)
    - Sorts by risk priority (ATM proximity → lots → type)
    - Closes in rounds (both_sides_closing=True, mechanism='exit_all')
    - Emits WebSocket progress after each round
    - Recomputes lots after each round
      ↓
[7a] All positions closed →
    - Enqueue audit event: EXIT_ALL_COMPLETED
    - Call self.stop('Exit All — all positions closed')
      ↓
[7b] Max rounds exceeded with residual positions →
    - Set _exit_all_partial = True
    - Persist failed position IDs
    - Enqueue audit event: EXIT_ALL_PARTIAL
    - Call self.stop('Exit All partial — manual close required')
    - Emit mmm_exit_partial WebSocket event
      ↓
[8] stop() runs normally — perp hedge close, deregister, WebSocket STOPPED
```

---

## 2. State Machine Changes

### New Status: `EXITING`

```
RUNNING       ──────────────┐
PAUSED        ──────────────┼──► EXITING ──► STOPPED
BOTH_SIDES_UP ──────────────┘         └──► STOPPED  (on partial/exception, with alert)
```

`EXITING` is a one-way transient gate. It never reverts to RUNNING.

### New Session Fields (added to DEFAULT_PARAMS)

| Field | Type | Default | Purpose |
|---|---|---|---|
| `_exit_all_requested` | bool | False | Intent flag — set before status change |
| `_exit_all_initiated_at` | str | None | ISO UTC timestamp of initiation |
| `_exit_all_reason` | str | None | e.g. "user_requested" |
| `_exit_all_completed_at` | str | None | ISO UTC timestamp of completion |
| `_exit_all_rounds_attempted` | int | 0 | Count of closing rounds run |
| `_exit_all_failed_positions` | list | [] | Position IDs that failed all retries |
| `_exit_all_partial` | bool | False | True if stopped with residual open positions |

---

## 3. Execution Sequence Design

### Position Collection

Both CE and PE sides — all three categories:
1. Active original positions (`positions[]` where `status='active'`, `type='original'`)
2. Active adjustment positions (`positions[]` where `status='active'`, `type='adjustment'`)
3. Frozen/shifted positions (`positions[]` where `status='shifted'`)

Filter out: `status='closed'`, `lots <= 0`, `_being_closed=True` (unless stale > 180s)

### Risk-Priority Sort Order

```
Priority 1 (HIGHEST): |spot_price - strike| ascending  ← closest ATM = highest delta/gamma
Priority 2:            lots descending                  ← larger exposure within same band
Priority 3 (LOWEST):   type: original > adjustment > shifted
```

Frozen positions are last — they shifted because premium decayed and are far OTM.

### Round Structure

```
Round N:
  1. Collect all unclosed positions (CE + PE) into two sorted lists
  2. Interleave: CE[0] → PE[0] → CE[1] → PE[1] → ...
     (prevents one-sided wipeout detection during multi-position exit)
  3. For each position:
       close_position(
           executor, initializer, session, position,
           mechanism='exit_all',
           hedge_guard=False,         ← bypasses G1/G2 in guardian
           both_sides_closing=True    ← signals coordinated both-side exit
       )
  4. recompute_side_lots() for both sides
  5. Check remaining lots

Max rounds: 3 (hardcoded constant MAX_EXIT_ROUNDS)
Inter-round delay: 2 seconds
```

### Why Sequential (Not asyncio.gather)

`_being_closed` flags and `recompute_side_lots()` are not coroutine-safe within the same session dict. Sequential execution matches existing heartbeat behavior and avoids state corruption.

---

## 4. Guardian Bypass

- **G1 (Hedge Integrity):** Bypassed via `both_sides_closing=True` — already accepted parameter in `check_close_allowed()`
- **G2 (Velocity Cap):** Bypassed by adding `'exit_all'` to the mechanism bypass list alongside `'emergency'`
- No guardian logic is modified — the bypass path already exists

---

## 5. Files Changed

| File | Change |
|---|---|
| `mmm_state.py` | Add 7 `_exit_all_*` fields to `DEFAULT_PARAMS` |
| `mmm_guardian.py` | Add `'exit_all'` to G1/G2 bypass mechanism list |
| `mmm_close_at_5.py` | Accept `mechanism='exit_all'` (no logic change needed if guardian handles it) |
| `mmm_exit_all.py` | **NEW FILE** — `_run_exit_all()` and `_collect_exit_positions()` |
| `mmm_monitor.py` | Add EXITING gate at top of `_heartbeat_inner()` + import |
| `mmm_websocket.py` | Add 3 new emitter functions |
| `mmm_activity.py` | Add 3 new ACTIVITY_TYPE constants |
| `webui/backend/app.py` | Add `POST /api/mmm/session/<id>/exit_all` endpoint |
| `MMMDashboard.js` | Add "Exit Strategy" button + confirmation modal + progress/result display |

---

## 6. API Specification

```
POST /api/mmm/session/<session_id>/exit_all

Request body (optional):
{ "reason": "user_requested" }

202 Accepted:
{
  "message": "Exit initiated",
  "session_id": "...",
  "initiated_at": "2026-03-18T10:00:00Z",
  "positions_to_close": {
    "ce": { "active_lots": 6, "frozen_lots": 2 },
    "pe": { "active_lots": 4, "frozen_lots": 0 }
  }
}

409 Conflict:  { "error": "Session already EXITING or STOPPED", "current_status": "..." }
404 Not Found: { "error": "Session not found" }
```

---

## 7. WebSocket Events

| Event | Payload |
|---|---|
| `mmm_exit_initiated` | `{session_id, initiated_at, total_ce_lots, total_pe_lots}` |
| `mmm_exit_progress` | `{session_id, round, closed_count, remaining_count, failed_count}` |
| `mmm_exit_completed` | `{session_id, completed_at, total_closed, duration_ms}` |
| `mmm_exit_partial` | `{session_id, failed_positions: [{side, strike, lots}], message}` |

---

## 8. Failure Handling

| Failure | Handling |
|---|---|
| Per-position API error | Log + add to `_exit_all_failed_positions` → continue other positions |
| Stale `_being_closed` (>180s) | Clear flag, retry in next round |
| Max rounds exceeded with residual | `_exit_all_partial=True` → stop() → alert user with position list |
| Exception in `_run_exit_all` | Catch all → stop() with error reason → emit partial alert |
| Already EXITING/STOPPED | API returns 409, no state change |
| No open positions | Skip rounds → EXIT_ALL_COMPLETED immediately → stop() |

---

## 9. UI Design

**Button:** "Exit Strategy" — amber/orange, near Pause/Stop controls
**Disabled when:** status is EXITING, STOPPED, IDLE
**During EXITING:** Shows spinner + "Closing positions… round N/3"

**Confirmation modal:**
```
Exit Strategy — Close All Positions

This will close ALL open positions across all strikes:
  CE: 6 active + 2 frozen = 8 lots (4 positions)
  PE: 4 active = 4 lots (2 positions)

The session will stop after all positions are closed.

[Cancel]  [Confirm Exit]
```

**On partial completion:** Persistent alert listing unclosed positions by side/strike/lots.

---

## 10. Test Checklist (SIM Mode, EXECUTE_ORDERS=false)

| Test | Expected |
|---|---|
| Happy path — active CE+PE | RUNNING → EXITING → STOPPED, all closed, audit complete |
| No open positions | Immediate STOPPED, COMPLETED audit |
| Already STOPPED | 409 response |
| Exit from PAUSED | PAUSED → EXITING → STOPPED |
| API failure simulation | Failed position in `_exit_all_failed_positions`, others closed |
| Max rounds exceeded | STOPPED + `_exit_all_partial=True` + UI alert |
| Double POST exit_all | Second returns 409 |
| Exception during exit | Caught → stop() → partial alert |
| Sealed tests still pass | `pytest -m sealed` count unchanged |

---

## 11. What Is NOT Changed

- `close_position()` internal logic
- `_heartbeat_inner()` RUNNING path
- Guardian G1/G2/G3/G4 invariant logic
- `stop()` / `pause()` / `resume()` methods
- `recompute_side_lots()`
- Any existing session fields or API endpoints
- All sealed tests remain valid
