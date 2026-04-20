# MMM Full-Stack Phasewise Audit Plan (Context-Window Safe)

**Date:** 2026-04-20  
**Repository:** `WorkingBot`  
**Scope:** MMM algo backend + API + frontend MMM UI + tests + wiring contracts

---

## Why this exists

This plan is designed for your exact problem: no single AI context window can hold the whole MMM codebase safely, but you still need a **complete file-by-file, function-by-function, wiring-complete audit**.

This document gives a deterministic sequence, artifact protocol, and handoff format so multiple AI sessions can audit **100% of MMM scope** without losing history.

---

## Measured baseline (from current repo scan)

- Backend MMM modules (`webui/backend/routes/mmm`): **57 files**
- Backend MMM tests (`webui/backend/routes/mmm/tests`): **75 files**
- Frontend MMM modules (`webui/frontend/src/components/mmm`): **38 files**
- MMM backend routes in `mmm_api.py`: **93 endpoints**
- Frontend `mmmService` mapped paths: **59 paths**
- Known direct frontend bypass (not via `mmmService`):
  - `MMMWhipsawCompareTab.js` uses `fetch(`/api/mmm/whipsaw/metrics/${sessionId}`)`

High-context files requiring chunked audit:
- `mmm_monitor.py` ~11,755 lines (~27 chunks @ 450 lines)
- `mmm_api.py` ~8,750 lines (~20 chunks @ 450 lines)
- `MMMDashboard.js` ~5,312 lines (~16 chunks @ 350 lines)
- `MMMSettingsDialog.js` ~2,211 lines (~7 chunks @ 350 lines)

---

## Non-negotiable guardrails (must be loaded in every audit session)

1. `CLAUDE.md` MMM safety rules and stale-monitor invariants are binding.
2. Reverse mode invariants are binding (`_reverse` isolation, hard if/else path, close order reverse→perp→core).
3. Any finding that can place/cancel wrong real orders is **P0**.
4. No assumption-based conclusions: every finding must cite code evidence (file + function + line range).
5. Every phase produces a report `.md` with explicit pass/fail status.

---

## Context-window operating model

### Session budget

- **Backend code review unit:** max 1 file chunk (<= 450 lines) + 2 dependency snippets.
- **Frontend code review unit:** max 1 file chunk (<= 350 lines) + 2 dependency snippets.
- **No session audits > 1,500 lines raw code**.

### Continuity model

Each session must load only:
1. `00_MASTER_INDEX.md`
2. Previous session handoff (`HANDOFF_LAST.md`)
3. Current phase brief (`phase_xx_plan.md`)
4. Current file chunk(s)

### Output model

Every session writes exactly:
- 1 `FILE_AUDIT_*.md`
- 1 `WIRE_CHECK_*.md` (if wiring touched)
- updates `00_MASTER_INDEX.md`
- updates `HANDOFF_LAST.md`

---

## Audit artifact structure

Create and maintain this structure:

- `audit/mmm/00_MASTER_INDEX.md`
- `audit/mmm/HANDOFF_LAST.md`
- `audit/mmm/phases/phase_00_setup.md` … `phase_12_final.md`
- `audit/mmm/file_reports/backend/*.md`
- `audit/mmm/file_reports/frontend/*.md`
- `audit/mmm/wiring_reports/*.md`
- `audit/mmm/test_reports/*.md`
- `audit/mmm/final/MMM_AUDIT_FINAL_REPORT.md`

> If you prefer root-level docs, keep names identical and preserve ordering prefixes (`00_`, `phase_01_`, etc.).

---

## Phase map (sequential, dependency-safe)

## Phase 00 — Setup + manifests (mandatory first)

**Goal:** Build auditable inventory so nothing is skipped.

**Actions**
- Build backend file manifest (all `mmm_*.py`, line counts, chunk counts).
- Build function manifest (function/method signature list per file).
- Build endpoint manifest from `mmm_api.py`.
- Build frontend component/service/hook manifest.
- Build websocket event manifest (`emit` vs `on`/`off`).

**Deliverables**
- `phase_00_setup.md`
- `MANIFEST_BACKEND_FILES.md`
- `MANIFEST_BACKEND_FUNCTIONS.md`
- `MANIFEST_FRONTEND_FILES.md`
- `MANIFEST_API_ENDPOINTS.md`
- `MANIFEST_WS_EVENTS.md`

---

## Phase 01 — Foundations (constants/config/base infra)

**Order**
1. `mmm_constants.py`
2. `mmm_config.py`
3. `mmm_dte_presets.py`
4. `mmm_telegram.py`
5. `mmm_websocket.py`
6. `mmm_activity.py`
7. `mmm_audit_log.py`
8. `mmm_audit_remark.py`
9. `mmm_analytics_storage.py`
10. `mmm_analytics_aggregator.py`
11. `mmm_performance.py`
12. `mmm_walkthrough.py`

**Checks**
- Config defaults vs runtime usage.
- Dead knobs / phantom controls.
- Event schema stability (`emit_*` payload consistency).

---

## Phase 02 — Persistence + P&L kernel

**Order**
1. `mmm_state.py`
2. `mmm_storage.py`
3. `mmm_pnl_core.py`
4. `mmm_observer.py`

**Checks**
- Session schema invariants.
- Generation save/reload correctness.
- Canonical total P&L formula (must include reverse where required).

---

## Phase 03 — Execution primitives

**Order**
1. `mmm_initializer.py`
2. `mmm_executor.py`
3. `mmm_pending_orders.py`
4. `mmm_trigger.py`
5. `mmm_fill_sync.py`
6. `mmm_adaptive.py`
7. `mmm_scaler.py`

**Checks**
- Order lifecycle correctness.
- Fill sync correctness under partial/failed fills.
- Trigger snapshots and reset conditions.

---

## Phase 04 — Safety, guardians, and fail-safe controls

**Order**
1. `mmm_margin_guardian.py`
2. `mmm_circuit_breaker.py`
3. `mmm_guardian.py`
4. `mmm_safety.py`
5. `mmm_heartbeat_health.py`
6. `mmm_watchdog.py`

**Checks**
- Stale monitor 3-layer invariants preserved.
- STOP vs PAUSE semantics correctness.
- Safety actions idempotence and precedence.

---

## Phase 05 — Position lifecycle mechanics

**Order**
1. `mmm_close_at_5.py`
2. `mmm_strike_shift.py`
3. `mmm_harvester.py`
4. `mmm_recycler.py`
5. `mmm_wind_down.py`
6. `mmm_replenish.py`
7. `mmm_reversal.py`
8. `mmm_exit_all.py`

**Checks**
- Lot accounting conservation (`active + frozen + closed`).
- Partial-fill and rollback integrity.
- Close-order sequencing and emergency pathways.

---

## Phase 06 — Strategy overlays and advanced controls

**Order**
1. `mmm_reverse.py`
2. `mmm_perp_hedge.py`
3. `mmm_gamma.py`
4. `mmm_gamma_detector.py`
5. `mmm_breakeven_engine.py`
6. `mmm_regime.py`
7. `mmm_atm_shield.py`
8. `mmm_god_layer.py`
9. `mmm_adopter.py`

**Checks**
- `_reverse` isolation from core CE/PE ledgers.
- Hedge interactions with total P&L + risk gates.
- Mode transition correctness and no silent bypass.

---

## Phase 07 — Strategy dispatch + whipsaw subsystem

**Order**
1. `mmm_straddle_adjustment.py`
2. `mmm_straddle_roll_pure.py`
3. `mmm_strategy_dispatch.py`
4. `mmm_whipsaw_spot_log.py`
5. `mmm_whipsaw_smart.py`
6. `mmm_whipsaw.py`
7. `mmm_whipsaw_replay.py`

**Checks**
- Engine selection semantics truth (`whipsaw_engine` vs any secondary gates).
- Exposed parameter usage (no dead controls).
- Replay path dependence correctness (no per-beat state reset bias).

---

## Phase 08 — Core orchestrators (highest risk)

**Order**
1. `mmm_engine.py`
2. `mmm_monitor.py` (chunked sub-phases: 27 chunks)

**Checks**
- Heartbeat order contract and early-return safety cleanup consistency.
- Generation guards, stale abort flags, save-path return checks.
- Any path capable of placing real orders must pass all gating invariants.

---

## Phase 09 — API surface + backend wiring contracts

**Order**
1. `mmm_api.py` (chunked sub-phases: 20 chunks)
2. `webui/backend/routes/mmm/__init__.py`
3. `webui/backend/app.py` MMM registration block

**Checks**
- Endpoint semantics truth (docs/UI/status vs backend behavior).
- Route-to-function correctness and status transition legality.
- Emergency routes: behavior when monitor object missing or stale.

---

## Phase 10 — Frontend data layer + socket lifecycle

**Order**
1. `mmmService.js`
2. `MMMContext.js`
3. `hooks/useMMMWebSocket.js`
4. `index.js`

**Checks**
- API parity (all used paths exist, method parity).
- Socket event parity (`emit` backend vs `on` frontend).
- No bypass of shared API shim (retry/circuit features).

---

## Phase 11 — Frontend panel audit (UI truthfulness)

**Start with central files**
1. `MMMDashboard.js` (16 chunks)
2. `MMMSettingsDialog.js` (7 chunks)
3. `MMMConfigPanel.js` (4 chunks)
4. `MMMWhipsawCompareTab.js`
5. `MMMSafetyPanel.js`

**Then all remaining MMM components in descending LOC order.**

**Checks**
- Control semantics match backend reality.
- Labels/tooltips do not encode deprecated logic.
- Compare/metrics panels do not show biased or placeholder values as authoritative.

---

## Phase 12 — Test matrix, replay probes, and final synthesis

**Actions**
- Audit all 75 backend MMM tests for coverage and stale assumptions.
- Audit frontend MMM tests (`__tests__`) for contract relevance.
- Build uncovered-function list from function manifest.
- Run replay/probe checks for critical semantics (engine select, dead knobs, replay dependence).

**Final deliverables**
- `COVERAGE_GAPS_FUNCTION_LEVEL.md`
- `CRITICAL_FINDINGS_REGISTER.md`
- `MMM_AUDIT_FINAL_REPORT.md`

---

## Function-level audit loop (applies to every function/method)

For each function `f` in each file:

1. Record signature and line range.
2. Record direct callees and direct callers.
3. Record read keys (`session[...]`, params, globals).
4. Record write keys.
5. Record side effects (order place/cancel, websocket emit, DB save, file I/O).
6. Record guards expected before action.
7. Validate error handling path (exception-safe? partial-state risk?).
8. Validate idempotence / re-entry behavior.
9. Validate test coverage presence and quality.
10. Mark status: `PASS`, `FAIL`, `RISK`, `NOT-APPLICABLE`.

---

## Wiring contract audit loop (backend ↔ frontend)

For each endpoint and socket event:

1. Backend producer: route or emitter function.
2. Backend state dependency.
3. Frontend consumer (service/context/component).
4. UI label/control that presents it.
5. Compare intended semantics vs runtime semantics.
6. Flag drift as:
   - `C-TRUTH` (operator truth mismatch)
   - `C-DEAD-KNOB` (exposed control no runtime effect)
   - `C-BIAS` (telemetry/replay distortion)

---

## Severity model

- **P0 Critical:** Can cause wrong real-order behavior, hidden exposure, or operator mis-action during live incidents.
- **P1 High:** Major control-plane or accounting risk; can become P0 under stress.
- **P2 Medium:** Logic drift, replay bias, or observability misalignment.
- **P3 Low:** Naming/comment/tooling debt.

---

## Completion criteria (strict)

The audit is complete only when all are true:

1. Every MMM file is marked `AUDITED` in `00_MASTER_INDEX.md`.
2. Every function in function manifest has an audit status.
3. Every backend endpoint has frontend parity status.
4. Every websocket event has producer/consumer parity status.
5. Uncovered critical functions have tests proposed or added.
6. Final report includes open-risk register with explicit production impact.

---

## Session handoff format (copy/paste standard)

Each session ends with a handoff block containing:

- Phase + file + chunk completed
- Functions audited this session
- Findings (IDs + severities)
- Files/wiring dependencies to load next session
- Exact next step (single actionable line)

This handoff must be appended to `HANDOFF_LAST.md` and summarized in `00_MASTER_INDEX.md`.

---

## Suggested first 3 execution sessions

1. **Session A:** Phase 00 manifests + index/handoff scaffolding.
2. **Session B:** Phase 01 files 1–6 (constants/config/websocket/activity baseline).
3. **Session C:** Phase 01 files 7–12 + start Phase 02 (`mmm_state.py` chunk 1).

After Session C, continue strictly phase-by-phase without skipping.

---

## Notes from recent audits to keep front-of-mind

- Watch for stale-monitor regressions and save-path guard bypasses.
- Whipsaw control semantics need special scrutiny (engine selection truth, dead controls, replay fidelity).
- Maintain separation between runtime truth and operator-facing UI semantics.

---

**Bottom line:** This plan is optimized for multi-session, multi-AI execution under context constraints while preserving institutional memory and full coverage of MMM backend, API wiring, frontend controls, and tests.
