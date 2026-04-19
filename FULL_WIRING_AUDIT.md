# FULL_WIRING_AUDIT — MMM Backend/Frontend Forensic Wiring Report

**Generated:** 2026-04-18  
**Audit mode:** Read-only forensic inspection (no code changes)  
**Scope:** `webui/backend/routes/mmm/*` + `webui/frontend/src/components/mmm/*` + supporting API shim/runtime wiring

---

## 1) Scope, Constraints, and Method

This audit was performed under strict **inspection-only** constraints:

- No refactors
- No runtime behavior changes
- No generated production code

Method used:

1. Route-by-route backend contract review in `mmm_api.py` (session lifecycle, params, emergency, reverse, analytics, audit).
2. Frontend service + callsite review (`mmmService.js`, `MMMContext.js`, `MMMDashboard.js`, hooks/panels).
3. WebSocket producer/consumer mapping (`mmm_websocket.py` + frontend listeners).
4. Persistence-integrity review (`mmm_storage.py`, analytics/audit stores).
5. Static diff scripts for route/service parity and method usage.

---

## 2) End-to-End Wiring Inventory (Current State)

### Backend surface

- **~90** MMM REST routes discovered.
- Core control routes (`start/pause/resume/stop/exit_all/kill_switch`) are present and reachable via frontend service.
- Advanced/admin surfaces exist for emergency controls, audit export/trail, exchange introspection, reconcile, reverse status, and diagnostics.

### Frontend surface

- `mmmService.js` exposes **74** methods.
- Primary orchestration is split across:
  - `MMMContext.js` (session list + health + WS orchestration)
  - `MMMDashboard.js` (controls + high-level UX flow)
  - `useMMMWebSocket.js` (session-scoped real-time stream)
  - specialized panels (analytics, risk, reverse, margin, audit).

### Real-time surface

- Backend emits high-frequency and lifecycle events via `mmm_websocket.py` plus some direct emits from monitor/other modules.
- Frontend consumes events via both direct `socket.on(...)` and wrapper listener registration in hooks/context.

---

## 3) REST Contract Verification Results

### Route ↔ service parity (normalized path/method check)

Verified from static extraction:

- `ROUTES = 90`
- `SERVICE_CALLS = 73`
- `SERVICE_MISSING_BACKEND = 0`
- `METHOD_MISMATCH = 0`

✅ **Conclusion:** No hard route/method breakage between `mmmService.js` and backend routes.

### Response-shape consistency

Most endpoints follow `{ success, ... }` envelope; however, some audit endpoints return raw collections:

- `mmm_api.py:8283` → `{'rows': ...}`
- `mmm_api.py:8382`, `mmm_api.py:8397` → `{'events': ...}`

This is not currently breaking UI (panels consume these shapes directly), but it is an envelope inconsistency compared to the rest of MMM API.

---

## 4) WebSocket Wiring Review

### Confirmed wired core channels

Core operational events are wired end-to-end (heartbeat, adjustments, status changes, safety, params changes, session create/delete, exit progress/completion channels, options ticker updates).

### Event-surface drift / partially unused channels

From emitter/listener mapping (including wrapped listeners), the following channels from `mmm_websocket.py` currently have no frontend listener references:

- `mmm_atm_shield`
- `mmm_breakeven` (panel docs mention it, but no listener bound)
- `mmm_gamma`
- `mmm_manual_injection`
- `mmm_reverse_entry`
- `mmm_reverse_closed`
- `mmm_reverse_disabled`
- `mmm_reverse_status`
- `mmm_scale_up`

This is mostly **observability drift** (low to medium risk depending on operator dependence on these events).

---

## 5) State Flow and Persistence Integrity

### Healthy patterns observed

- Session control routes generally enforce state gating and explicit errors.
- Stop flow includes final P&L persistence pass and lifecycle/audit writes.
- Storage layer includes status column + JSON persistence + summary query optimization.
- Adoption flow includes payload congruence/validation hardening.

### State-path concern found

Active-only session queries in storage filter to:

- `RUNNING`, `PAUSED`, `BOTH_SIDES_UP`, `EXITING` only  
  (`mmm_storage.py:789`, `mmm_storage.py:967`)

Frontend active refresh logic treats additional states as active:

- `STARTING`, `PARTIAL_ENTRY` are in `ACTIVE_SESSION_STATUSES`  
  (`MMMContext.js:60`)
- Active refresh calls `getSessions(true, true)` (`MMMContext.js:268`) and merge logic can drop these non-returned statuses (`MMMContext.js:252`).

This creates a real state-visibility gap (detailed in Findings).

---

## 6) Dead / Stale / Bypassed Surface Inventory

### Backend routes unused by frontend service (17)

Not represented in `mmmService.js` route calls:

- `GET /analytics/history`
- `GET /audit/export`
- `GET /audit/trail`
- `GET /emergency/health-check`
- `GET /exchange/orders`
- `GET /exchange/positions`
- `GET /metrics/aggregate`
- `GET /parameter_suggestions`
- `GET /session/<session_id>/breakeven`
- `GET /session/<session_id>/gamma`
- `GET /session/<session_id>/pnl-curve` *(called directly by fetch in chart, bypassing service)*
- `GET /session/<session_id>/reverse`
- `POST /emergency/pause-all`
- `POST /emergency/reset-circuit/<session_id>`
- `POST /emergency/stop-all`
- `POST /session/<session_id>/clear-backoff`
- `POST /session/<session_id>/reconcile`

### Unused frontend service methods (16)

Detected as defined-but-not-called in MMM component tree:

- `checkLiquidity`
- `emergencyCloseAllPositions`
- `emergencyKillAllBots`
- `getActivityStats`
- `getAggregatedAnalytics`
- `getAllMonitors`
- `getCriticalActivities`
- `getMonitorStatus`
- `getPerformanceSummary`
- `getPerpHedgeStatus`
- `getPnLTimeline`
- `getPositions`
- `getSafetyStatus`
- `getSessionHistory`
- `getSessionState`
- `getTriggerData`

### Direct API bypass

- `MMMRiskProfileChart.js:88` calls raw `fetch(...)` to `/api/mmm/session/${sessionId}/pnl-curve`.
- This bypasses shared retry/circuit logic in `apiShim.ts` (`apiShim.ts:3`, `apiShim.ts:16`, `apiShim.ts:111`).

---

## 7) Prioritized Findings (Critical → Low)

### 🔴 F1 — Critical: Active session polling can hide `STARTING` / `PARTIAL_ENTRY` sessions

**Evidence**

- Backend active filters exclude `STARTING` + `PARTIAL_ENTRY` (`mmm_storage.py:789`, `mmm_storage.py:967`).
- Frontend considers them active (`MMMContext.js:60`) and uses active-only polling (`MMMContext.js:268`).
- Merge logic drops active-status sessions not returned by active query (`MMMContext.js:252`).

**Impact**

- Session cards can disappear during entry startup or partial-entry/orphan states.
- Operator may lose visibility of exactly the states requiring urgent intervention.

---

### 🔴 F2 — High: UI blocks emergency exit controls in `PARTIAL_ENTRY` despite backend support

**Evidence**

- Backend `exit_all` explicitly allows `PARTIAL_ENTRY` (`mmm_api.py:1766`).
- Backend `kill_switch` also handles non-terminal active states (`mmm_api.py:1910`, `mmm_api.py:1918`).
- Frontend only shows Exit/Kill for `RUNNING|PAUSED|BOTH_SIDES_UP` (`MMMDashboard.js:749`, `MMMDashboard.js:763`).

**Impact**

- In orphan-leg scenarios, operator cannot trigger fastest emergency flatten path from primary UI.
- Increases manual API dependence during high-stress incidents.

---

### 🔴 F3 — High: Emergency admin endpoints have monitor/storage state divergence risk

**Evidence**

- `emergency_stop_all` calls `monitor.stop(reason)` then writes `session['strategy_status']='PAUSED'` (`mmm_api.py:7475-7476`).
- `emergency_pause_all` writes DB status `PAUSED` directly (`mmm_api.py:7638`) without monitor pause call.
- Standard pause path uses `pause_session_monitor(...)` (`mmm_api.py:1539`), indicating monitor-state mutation is expected for correctness.

**Impact**

- Emergency commands can create conflicting state semantics (DB says paused while monitor behavior differs).
- Dangerous in crisis workflows where operator trusts status labels.

---

### 🟠 F4 — Medium: `force_start` recovery path is documented backend behavior but unavailable in UI/service

**Evidence**

- Backend start route accepts `force_start` and tells operator to pass it on invariant/cap violations (`mmm_api.py:725-729`, `mmm_api.py:744`, `mmm_api.py:802`).
- `mmmService.startSession` posts with no request body (`mmmService.js:84-85`).

**Impact**

- Recovery flow advertised by API cannot be executed from current WebUI controls.

---

### 🟠 F5 — Medium: Risk chart bypasses shared API resilience and uses hardcoded fallback base URL

**Evidence**

- Raw fetch call in `MMMRiskProfileChart.js:88`.
- Shared API wrapper provides retries + circuit breaker (`apiShim.ts:3`, `apiShim.ts:16`, `apiShim.ts:111`).

**Impact**

- Inconsistent error handling/retry behavior vs rest of MMM panel.
- Environment-dependent base URL drift risk (`localhost:5555` fallback).

---

### 🟡 F6 — Low/Medium: WebSocket channel sprawl with unconsumed emissions

**Impact**

- Increases maintenance overhead and mental load during incident debugging.
- Some strategy-specific telemetry exists but is not visibly wired to operator UI.

---

### 🟡 F7 — Low: 17 backend-only endpoints and 16 unused service methods indicate surface drift

**Impact**

- Higher long-term drift probability and weaker confidence in “what is actually used.”

---

## 8) Prioritized Remediation Backlog (Execution Order)

1. **Fix active-session status parity first (F1)**  
	Align backend active filters with frontend active-state model (or change polling strategy) so `STARTING`/`PARTIAL_ENTRY` never disappear.

2. **Expose emergency flatten controls for `PARTIAL_ENTRY` (F2)**  
	Ensure Exit/Kill are available whenever backend supports them.

3. **Harden emergency admin semantics (F3)**  
	Make `pause-all` and `stop-all` use the same monitor-aware pathways as normal control routes.

4. **Add optional `force_start` plumbing in service/UI (F4)**  
	Keep guarded UX, but make the override reachable for authorized recovery actions.

5. **Route risk chart through shared API abstraction (F5)**  
	Remove direct fetch bypass and standardize retry/circuit behavior.

6. **Prune or wire currently unused WS/service surfaces (F6/F7)**  
	Either connect them to visible UI workflows or formally deprecate.

---

## Final Verdict

- **Core wiring correctness is strong** (0 route/method mismatches for service-called paths).
- **Primary production risk is not missing endpoints; it is state-visibility and emergency-path coherence** under stressed states (`STARTING`, `PARTIAL_ENTRY`, emergency controls).
- **Most impactful improvements are small wiring changes**, not algorithm changes.

