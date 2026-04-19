# Kill Switch Implementation — 2026-04-17

## Overview
Per-session Emergency Kill Switch added to all MMM/MMMX active session cards.
One click → confirmation dialog → market-order square-off of all session positions.

---

## Files Changed

### Backend
| File | Change |
|------|--------|
| `webui/backend/routes/mmm/mmm_api.py` | Added `POST /api/mmm/session/<id>/kill_switch` endpoint (~line 1857) |
| `webui/backend/routes/mmm/mmm_activity.py` | Registered `kill_switch_triggered` in ACTIVITY_TYPES, ACTIVITY_CATEGORIES.system, and _ALWAYS_PERSIST_TYPES |

### Frontend
| File | Change |
|------|--------|
| `webui/frontend/src/components/mmm/mmmService.js` | Added `killSwitch(sessionId, reason)` method |
| `webui/frontend/src/components/mmm/MMMDashboard.js` | Kill switch button + dialog in `SessionCard`; `kill_switch` case in `handleControl`; `PowerOffIcon` import |
| `webui/frontend/src/components/mmm/MMMSessionCard.js` | Kill switch button + dialog + `onKillSwitch` prop; `PowerOffIcon`, `Dialog`, `Button`, `CircularProgress` imports |
| `webui/frontend/src/components/mmmx/MMMXSessionCard.js` | Kill switch button + dialog + `onKillSwitch` prop; `PowerOffIcon`, Dialog imports |
| `webui/frontend/src/components/mmmx/MMMXDashboard.js` | Wired `onKillSwitch` prop on `MMMXSessionCard` → `mmmxService.killSwitch` |

---

## Endpoint Added

```
POST /api/mmm/session/<session_id>/kill_switch
```

**Request body** (optional):
```json
{ "reason": "string" }
```

**Behavior:**
1. Validates session exists → 404 if not found
2. STOPPED/IDLE → 200 (graceful, nothing to close)
3. EXITING → 200 idempotent (already in flight)
4. RUNNING/PAUSED/BOTH_SIDES_UP → 202 Accepted:
   - Writes `_kill_switch_triggered=True`, `_kill_switch_at`, `_kill_switch_reason`
   - Sets `strategy_status=EXITING` + all `_exit_all_*` fields
   - Mirrors to live monitor's in-memory session
   - Calls `monitor.force_heartbeat()` — close orders go immediately
   - Logs to activity log (category: system, severity: critical)
   - Logs to structured event log (SESSION_LIFECYCLE / CRITICAL)

**Response (202):**
```json
{
  "success": true,
  "message": "Kill switch activated for session ...",
  "session_id": "...",
  "initiated_at": "...",
  "prior_status": "RUNNING",
  "positions_to_close": { "ce": {...}, "pe": {...} }
}
```

---

## Flow Summary

```
User clicks Kill Switch button
  → Confirmation dialog (MUI Dialog)
  → User clicks "Confirm Exit All"
  → onControl('kill_switch', sessionId) called
  → mmmService.killSwitch(sessionId)
  → POST /api/mmm/session/<id>/kill_switch
  → Backend: sets EXITING + _kill_switch_triggered + forces heartbeat
  → Monitor detects EXITING on next heartbeat (immediate via force)
  → Monitor closes all positions via existing exit_all flow
  → Session → STOPPED
  → UI refreshes (fetchSessions called on success)
```

---

## Safety Rules Enforced
- **Scope**: Only the specified session. No other sessions touched.
- **Idempotent**: Multiple clicks safe. EXITING/STOPPED/IDLE all return 200.
- **No double-submit**: Button disabled while submitting (`killSubmitting` state).
- **No trading logic changed**: Delegates entirely to existing `exit_all` flow.
- **Audit trail**: `_kill_switch_triggered`, `_kill_switch_at`, `_kill_switch_reason` written to DB.
- **Activity + event log**: Both log entries created (always-persist category).

---

## MMMX Note
MMMX already had a kill switch accessible via `MMMXTopCommandStrip` (requires typed phrase "KILL {id}").
The card kill switch is a **second, simpler path** for the same session-scoped stop, without the typed confirmation. Uses the existing `mmmxService.killSwitch({ scope: 'session', ... })`.
