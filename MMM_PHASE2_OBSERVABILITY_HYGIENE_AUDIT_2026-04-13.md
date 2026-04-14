# MMM Phase 2 — Observability Hygiene Audit (No Trading Logic Changes)

Date: 2026-04-13  
Scope: Observability/event hygiene only (activity stream, WebSocket isolation, frontend filtering, stale/duplicate feed behavior, badge/session consistency)  
Constraint: **No trading logic modifications reviewed or proposed**

---

## Executive Summary

The strategy-isolation layer remains intact, but the observability path has a **session-scoping weakness**:

- Backend emits some valid system-level activity events with `session_id=None`
- MMM WebSocket broadcasts all MMM events globally (single namespace, no per-session room isolation)
- `MMMActivityFeed` session filter allows `session_id=None` events to pass into session-scoped views

This creates the exact symptom class requested for Phase 2:
- wrong-session/foreign logs appearing in a selected session feed
- warning/error/critical badge inflation unrelated to the selected session

Additional medium risks exist around stale response races on session switch and duplicate event rendering under replay/reconnect conditions.

---

## Severity-ranked Risk Register

### R1 — **HIGH** — `session_id=None` activity leakage into selected-session live feed (and badges)

**Evidence chain**

1. Backend intentionally logs global/system events with null session id:
   - `webui/backend/routes/mmm/mmm_api.py:7110` (`emergency stop-all` summary activity uses `None`)
   - `webui/backend/routes/mmm/mmm_api.py:7272` (`emergency pause-all` summary activity uses `None`)
   - `webui/backend/routes/mmm/mmm_api.py:7432` (`emergency close-all-positions` summary activity uses `None`)

2. Activity model permits and propagates null session ids:
   - `webui/backend/routes/mmm/mmm_activity.py:552` (`session_id: str = None` in `add()`)
   - `webui/backend/routes/mmm/mmm_activity.py:626` emits activity immediately via WS

3. WebSocket emission is global:
   - `webui/backend/routes/mmm/mmm_websocket.py:75` `_socketio.emit(event, data, namespace='/')`

4. Frontend filter in session view does not reject null `session_id`:
   - `webui/frontend/src/components/mmm/MMMActivityFeed.js:501`
   - `webui/frontend/src/components/mmm/MMMActivityFeed.js:507`
   - Current condition only rejects when `data.session_id` exists and mismatches; null passes through.

5. Badge counters are computed from full in-memory activity list:
   - `webui/frontend/src/components/mmm/MMMActivityFeed.js:565-567`

**Impact**
- Session-scoped feed can show unrelated system/global events
- Session-scoped warning/error/critical badges can be inflated by unrelated events
- Operator trust in real-time panel degrades during incidents

---

### R2 — **MEDIUM** — WebSocket isolation relies entirely on client-side filtering

**Evidence**
- `webui/backend/routes/mmm/mmm_websocket.py:75` broadcasts all MMM events to all clients (`namespace='/'`, no room targeting)
- Emission helper path consistently uses `_emit(...)` without per-session room routing

**Impact**
- One filtering bug in any frontend consumer can expose cross-session events immediately
- Higher fan-out/event noise under multi-session and multi-client usage

---

### R3 — **MEDIUM** — Stale event/state race after session switch (async fetch response ordering)

**Evidence**
- `webui/frontend/src/components/mmm/MMMActivityFeed.js:467-471` async fetch sets activities directly on completion
- `webui/frontend/src/components/mmm/MMMActivityFeed.js:482-487` session change clears state then starts new fetch
- No request token/abort guard before applying fetch result

**Impact**
- Late response from previous session request can overwrite newer session view transiently
- Appears as stale/foreign feed right after switching sessions

---

### R4 — **MEDIUM-LOW** — Duplicate feed events are not de-duplicated client-side

**Evidence**
- `webui/frontend/src/components/mmm/MMMActivityFeed.js:502` appends incoming WS activity directly (`[data, ...prev]`) with no id check
- Backend dedup is intentionally limited to selected types only:
  - `webui/backend/routes/mmm/mmm_activity.py:578` (`_DEDUP_TYPES` subset)
  - `webui/backend/routes/mmm/mmm_activity.py:582` conditionally applies dedup
- Activity IDs exist and are stable:
  - `webui/backend/routes/mmm/mmm_activity.py:605-608`

**Impact**
- Under replay/reconnect/multi-emission edge cases, same logical event can render multiple times
- Can distort perceived incident severity in live panel

---

### R5 — **LOW** — Global refresh signal can induce unnecessary cross-session refetch churn

**Evidence**
- Global refresh event has no `session_id`:
  - `webui/backend/routes/mmm/mmm_websocket.py:360` emits `mmm_activities_updated` with `{refresh: true}`
- Every feed instance responds with a fetch:
  - `webui/frontend/src/components/mmm/MMMActivityFeed.js:512`

**Impact**
- Extra API churn in multi-session/multi-client environments
- Increases chance of response-order races (R3), though not a direct data leak by itself

---

## Controls Already Present (Positive Findings)

- API activity query correctly enforces session equality when `session_id` is provided:
  - `webui/backend/routes/mmm/mmm_activity.py:692`
- Core live-data hook (`useMMMWebSocket`) uses strict equality checks (`data.session_id === sessionId`) and does not admit null for selected-session views:
  - `webui/frontend/src/components/mmm/hooks/useMMMWebSocket.js` (multiple handlers, e.g., line 127+)

These controls reduce blast radius but do not cover the `MMMActivityFeed` leak path.

---

## Recommended Fix Queue (Observability Only)

1. **R1 (High, first):** Tighten session filter in `MMMActivityFeed` to reject null session events when `sessionId` is set.
2. **R2 (Medium):** Add optional per-session WS room/channel emission for session-scoped events (or strict backend-side scoping for `mmm_activity` / `mmm_heartbeat_summary`).
3. **R3 (Medium):** Add request-sequencing/abort guard in `fetchActivities` to ignore stale responses after session changes.
4. **R4 (Med-Low):** Add client-side id-based dedup map in feed state updates.
5. **R5 (Low):** Add `session_id` to `mmm_activities_updated` where applicable and gate refetch by selected session.

---

## Final Verdict

Phase-2 observability audit confirms a **real, actionable session-hygiene gap** in live activity rendering (`session_id=None` passthrough), with clear evidence across backend emission and frontend filtering.  
No trading logic concerns were introduced in this audit, and all findings are isolated to observability/event handling paths.
