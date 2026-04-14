# MMM Strategy Isolation Forensic Report

**Date:** 2026-04-13  
**Updated:** 2026-04-14 (forensic addendum)  
**Scope:** Read-only forensic audit of strategy isolation and reverse-mode integration parity, focused on `STRADDLE_ROLL` vs `STRADDLE_WITH_ADJUSTMENT`  
**Repository:** `WorkingBot`

---

## Executive Summary

The audit confirms that **runtime trading-path isolation is strong** between `STRADDLE_ROLL` and `STRADDLE_WITH_ADJUSTMENT`.

- `STRADDLE_ROLL` is routed through a pure-roll path and explicitly skips normal adjustment flow.
- Strategy identity is canonical (`strategy_type`) and protected against mutation.
- Strategy namespace guardrails are present server-side.
- Reverse backend routes and monitor hooks are present and wired.

Updated caveat (2026-04-14): while trade-path isolation remains intact, **reverse UI integration has a high-risk control-path mismatch** (`MMMReverseModePanel` calls `mmmService.post(...)` but no generic `post()` exists on `mmmService`). This is an operational/UI integration defect, not a cross-strategy execution leak.

---

## Audit Objectives

1. Verify pure-roll sessions cannot fall through into adjustment-engine behavior.
2. Verify strategy identity and parameter namespace integrity across API/state/storage.
3. Verify reverse-mode branch invariants and API/runtime parity.
4. Verify realtime/event surfaces for possible cross-session leakage.
5. Cross-check implementation intent against strategy plan history.

---

## Method

Read-only source audit of backend + frontend + strategy plan artifacts. No runtime code changes made during this investigation.

Primary areas reviewed:

- Strategy dispatch and monitor runtime flow
- API identity/params enforcement
- Reverse API + panel/service integration parity
- Activity and websocket emission model
- Frontend websocket/activity filtering behavior
- Strategy plan alignment documents

---

## Findings (A→N)

### A) Canonical identity is in place

`strategy_type` is derived and persisted as a top-level identity and exposed in summaries.

### B) Dispatch contract enforces separation

`STRADDLE_ROLL` handler is configured with:

- `should_run_adjustment = False`
- Step 5.4 pure-roll handler returning skip intent for downstream adjustment path.

### C) Monitor honors dispatch contract

In monitor Step 5.4, `_skip_to_pnl` is set when handler requests skip or adjustment is disabled for strategy.

### D) Pure-roll module does not run monitor adjustment engine

Pure-roll flow executes its own roll/hard-stop logic; it does not invoke monitor `_process_adjustment()` as part of normal routing.

### E) Hybrid strategy remains distinct and intentional

`STRADDLE_WITH_ADJUSTMENT` preserves adjustment-enabled semantics and is separate from pure-roll routing.

### F) Namespace controls exist

Server-side forbidden-parameter sets are strategy-aware; patch paths enforce/strip forbidden keys.

### G) Persistence supports identity stability

Storage schema and fallback/backfill logic include strategy identity handling to reduce drift.

### H) Reverse-mode hard branch invariant remains intact

No evidence of reverse-mode fallthrough into normal adjustment path when reverse is active.

### I) Websocket scoping is payload-level, not room-level

Emits are global namespace; session scoping is carried in payload.

### J) Residual feed leakage edge exists

Activity logging accepts `session_id=None`; frontend activity filtering rejects mismatched present IDs but can pass null-session events.

### K) Plan-to-code alignment holds

Plan history confirms the strategic split: shipped hybrid retained as `STRADDLE_WITH_ADJUSTMENT`; pure roll tracked separately.

### L) Reverse backend route and monitor parity is present

Reverse endpoints exist (`/reverse`, `/reverse/enable`, `/reverse/disable`, `/reverse/close`) and monitor reverse intercept hooks are in place.

### M) Reverse control panel call-surface mismatch (frontend)

`MMMReverseModePanel.js` invokes `mmmService.post(...)`, but `mmmService.js` does not expose a generic `post()` method. This can break reverse enable/disable/close actions from UI despite healthy backend routes.

### N) Reverse state/render parity drift risk

Two UI parity risks remain:
- reverse position rendering expects fields that may not match backend reverse position shape,
- settings-level `reverse_enabled` can drift from runtime `_reverse.active` activation semantics if operators use params save alone.

---

## Risk Assessment

- **Trading-path cross-strategy leakage:** **LOW**
- **Identity/namespace mutation risk:** **LOW**
- **Reverse control-path integration mismatch (UI → service):** **HIGH**
- **Reverse state/render parity drift (UI mapping + activation semantics):** **MEDIUM**
- **Observability cross-session leakage (activity feed):** **MEDIUM-LOW**

---

## Recommendations

1. Fix reverse panel service wiring first: replace `mmmService.post(...)` calls with explicit typed service methods (or add a supported generic method).
2. Normalize reverse position DTO mapping in the panel to backend `_reverse` schema fields.
3. Eliminate activation drift: ensure settings-driven reverse toggles and `/reverse/enable|disable` runtime state stay consistent.
4. Require `session_id` for activity writes where feasible.
5. In session-scoped feed mode, drop events with null/missing `session_id`.
6. Optionally move to room-based websocket emission for stronger transport-level isolation.

---

## Evidence Map (key files reviewed)

- `webui/backend/routes/mmm/mmm_strategy_dispatch.py`
- `webui/backend/routes/mmm/mmm_monitor.py`
- `webui/backend/routes/mmm/mmm_api.py`
- `webui/backend/routes/mmm/mmm_config.py`
- `webui/backend/routes/mmm/mmm_state.py`
- `webui/backend/routes/mmm/mmm_storage.py`
- `webui/backend/routes/mmm/mmm_activity.py`
- `webui/backend/routes/mmm/mmm_websocket.py`
- `webui/backend/routes/mmm/mmm_reverse.py`
- `webui/backend/routes/mmm/mmm_pnl_core.py`
- `webui/frontend/src/components/mmm/MMMActivityFeed.js`
- `webui/frontend/src/components/mmm/hooks/useMMMWebSocket.js`
- `webui/frontend/src/components/mmm/MMMContext.js`
- `webui/frontend/src/components/mmm/MMMReverseModePanel.js`
- `webui/frontend/src/components/mmm/mmmService.js`
- `tasks/STRADDLE_ROLL_FIX_PLAN.md`

---

## Final Verdict

The `STRADDLE_ROLL` and `STRADDLE_WITH_ADJUSTMENT` runtime paths remain **architecturally isolated** in current implementation.

Current top risks are concentrated in:
- **reverse UI/service integration parity** (operational control-path reliability), and
- **event observability hygiene** (session-scoping of activity feed data),

rather than trade-execution crossover between strategies.
