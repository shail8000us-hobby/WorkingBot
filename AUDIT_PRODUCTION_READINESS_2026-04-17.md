# AUDIT_PRODUCTION_READINESS — 2026-04-17

Audit mode: **read-only** (no code changes, no trading actions).

## 1. Executive Summary

This system has **strong core trading safety controls** in MMM (including stale-monitor defenses, hard-stop guard architecture, and robust sealed test coverage), but it is **not yet production-ready for prop-desk deployment** due to operational and platform-level risks.

### What is strong right now
- Critical MMM safety controls are present in current code:
  - hard-stop guard thread + anti-double-fire event,
  - generation/stale-monitor controls,
  - pending-order fail-safe behavior in replenish path,
  - corrected reconciliation safety emission signature,
  - reverse/perp close ordering safeguards in core close flows.
- Fresh test evidence is good:
  - `python3 -m pytest webui/backend/routes/mmm/tests -m sealed -q`
  - **1051 passed, 405 deselected, 0 failed** (39.76s).

### Why this is not prop-desk ready yet
- Production serving/runtime architecture and deployment discipline are below institutional standards.
- Data truth consistency and operator-forensics consistency are still weak.
- Performance/reactivity profile remains slow for stress conditions.

---

## 2. Files Audited

### Core MMM safety/runtime
- `MMM_LAST_3_SESSIONS.md`
- `webui/backend/routes/mmm/mmm_monitor.py`
- `webui/backend/routes/mmm/mmm_exit_all.py`
- `webui/backend/routes/mmm/mmm_websocket.py`
- `webui/backend/routes/mmm/mmm_api.py`
- `webui/backend/routes/mmm/mmm_activity.py`

### MMM frontend/operator visibility
- `webui/frontend/src/components/mmm/MMMActivityFeed.js`
- `webui/frontend/src/components/mmm/MMMContext.js`
- `webui/frontend/src/components/mmm/hooks/useMMMWebSocket.js`
- `webui/frontend/src/utils/connectionManager.js`
- `webui/frontend/src/utils/RobustConnectionManager.js`

### Existing audits/reports
- `AUDIT_RISK_ENGINE.md`
- `AUDIT_EXECUTION_SPEED.md`
- `AUDIT_DATABASE_INTEGRITY.md`
- `MMM_PHASE2_OBSERVABILITY_HYGIENE_AUDIT_2026-04-13.md`
- `MMM_SAFETY_AUDIT_MAR31_2026.md`
- `KILL_SWITCH_TEST_RESULTS.md`

### Deployment/operations/quality gates
- `webui/backend/app.py`
- `ecosystem.config.js`
- `run_gunicorn.sh`
- `start_webui.sh`
- `scripts/restart_webui.sh`
- `Dockerfile`
- `.github/workflows/refactor-ci.yml`
- `webui/backend/routes/mmm/tests/pytest.ini`
- `pyproject.toml`
- `webui/frontend/tsconfig.json` (editor diagnostics)

---

## 3. Findings

### F-01 — Production serving stack is not institutional-grade
- **Severity:** P1
- **Evidence:**
  - `webui/backend/app.py` runs Flask-SocketIO with `async_mode=threading` and `allow_unsafe_werkzeug=True`.
  - `ecosystem.config.js` starts backend via `python3 webui/backend/app.py` directly.
  - `run_gunicorn.sh` is misnamed and still launches `socketio.run(...)`, not a real Gunicorn worker model.
- **Why it matters:** Built-in/unsafe serving patterns are fragile under high concurrency/failure bursts.
- **Suggested fix:** Move to a true production WSGI/ASGI topology with explicit worker strategy, graceful restarts, and hardened health/readiness checks.

### F-02 — Data integrity/canonical-truth drift remains high
- **Severity:** P1
- **Evidence:** `AUDIT_DATABASE_INTEGRITY.md` reports lifecycle contradictions, 69 blank stop reasons in STOPPED records, and significant cross-copy DB/log divergence.
- **Why it matters:** In real-money incidents, inconsistent truth breaks risk accountability, P&L forensics, and operator confidence.
- **Suggested fix:** Define one canonical writer/reader per dataset; enforce lifecycle invariants and non-empty terminal stop reasons; run deterministic repair/backfill scripts with provenance tags.

### F-03 — Emergency close-all endpoint still reflects legacy position schema assumptions
- **Severity:** P1
- **Evidence:** In `mmm_api.py` (`emergency_close_all_positions`), dry-run/result reporting loops legacy keys (`entry`, `adj1`, `adj2`, `adj3`) while MMM now relies on unified `positions[]` ledger patterns.
- **Why it matters:** In emergency conditions, operator output can be incomplete/misleading even if underlying close logic executes.
- **Suggested fix:** Refactor endpoint reporting to derive from `positions[]` and exchange-confirmed state only.

### F-04 — CI gate is not explicitly enforcing MMM deployment-critical suites
- **Severity:** P1
- **Evidence:** Only `.github/workflows/refactor-ci.yml` is present; no explicit MMM sealed gate is visible in workflow definitions.
- **Why it matters:** Safety-critical regressions can pass through non-specific CI, especially with broad code churn.
- **Suggested fix:** Add mandatory MMM sealed suite gate + minimum smoke/integration matrix before merge/release.

### F-05 — Test hygiene warning noise (marker config split)
- **Severity:** P2
- **Evidence:** Fresh sealed run emitted **663 `PytestUnknownMarkWarning`** for `@pytest.mark.sealed`; `webui/backend/routes/mmm/tests/pytest.ini` lacks marker registration while root `pyproject.toml` defines it.
- **Why it matters:** Signal-to-noise drops, and marker/filter confidence degrades in audit workflows.
- **Suggested fix:** Consolidate pytest marker registration so all entry points recognize `sealed` consistently.

### F-06 — Responsiveness remains slow for stress regimes
- **Severity:** P2
- **Evidence:** `AUDIT_EXECUTION_SPEED.md` (current repo audit) shows long execution envelopes, interval-driven reaction limits, and hot-path persistence overhead.
- **Why it matters:** Fast adverse moves can outrun reaction layers despite good safety design.
- **Suggested fix:** Tighten operational intervals/profiles, separate status-call retries from transactional retries, and reduce hot-path write amplification.

### F-07 — MMM events are globally emitted; isolation depends on client filtering
- **Severity:** P2
- **Evidence:** `mmm_websocket.py` `_emit` broadcasts to namespace `/`; session-scoping is mainly client-side.
- **Why it matters:** Any frontend filter drift can reintroduce cross-session noise/leakage.
- **Suggested fix:** Add optional server-side room/session scoping for session-specific events.

### F-08 — Maintainability debt remains material
- **Severity:** P2
- **Evidence:** `webui/backend/app.py` remains very large and side-effect heavy; broad exception handling patterns persist; `webui/frontend/tsconfig.json` has deprecation diagnostics.
- **Why it matters:** High change-risk in a real-money platform increases regression probability and slows incident remediation.
- **Suggested fix:** Incremental modularization of startup/runtime responsibilities + strict lint/type and diagnostics budget.

### F-09 — Containerization/deployment baseline is weak for scale
- **Severity:** P3
- **Evidence:** `Dockerfile` couples bot+backend startup in one shell, sources secrets from files, lacks orchestration-grade health strategy.
- **Why it matters:** Limits portability, reproducibility, and fault-domain isolation.
- **Suggested fix:** Split services, add health probes and runtime contracts, and move secret handling to managed runtime mechanisms.

---

## 4. Severity (P0/P1/P2/P3)

- **P0:** 0
- **P1:** 4 (`F-01`, `F-02`, `F-03`, `F-04`)
- **P2:** 4 (`F-05`, `F-06`, `F-07`, `F-08`)
- **P3:** 1 (`F-09`)

---

## 5. Why It Matters

MMM can place real-money orders. In that context, correctness is not enough; **operational truth, deterministic emergency behavior, and institutional-grade runtime guarantees** are mandatory.

Current state: strong algorithmic safety internals, but platform/ops gaps can still create unacceptable risk during live incidents (especially when decisions rely on stale/partial operator context).

---

## 6. Suggested Fix

### 0–48h (must-fix before real capital scaling)
1. Harden production serving model (replace unsafe runtime pattern).
2. Fix emergency endpoint reporting to `positions[]` + exchange truth.
3. Add explicit CI gate for MMM sealed tests and critical regression suites.
4. Enforce lifecycle/stop-reason invariants in canonical data store.

### 2–7 days
1. Remove pytest marker ambiguity and warning noise.
2. Reduce latency bottlenecks in heartbeat/execution hot paths.
3. Add server-side session scoping for WebSocket events.

### 1–3 weeks
1. Modularize backend startup/registration surfaces.
2. Upgrade container/deployment topology to scale-safe patterns.
3. Build incident replay pack (stale monitor, max-loss breach, partial entry, kill-switch).

---

## 7. Safe Implementation Notes for Claude

When implementing fixes, these are non-negotiable safety rules:

1. **Do not weaken stale-monitor protections** in MMM.
2. **Do not alter hard-stop guard invariants** (independent guard behavior, anti-double-fire, emergency close chain).
3. **Preserve reverse-mode invariants**:
   - hard reverse/normal branch separation,
   - `_auto_close_all()` order: reverse → perp → core,
   - no contamination of `_reverse` into CE/PE core ledgers.
4. **Treat exchange truth as authority** for emergency and reconciliation reporting.
5. **No silent fail paths** in safety-alert or emergency workflows; errors must be visible and auditable.
6. **Before touching MMM logic**, follow repository safeguards in `CLAUDE.md` (line/function-level change declaration, before/after behavior clarity, no guessing).
7. **Never restart/operate trading services without explicit human confirmation** in live environments.

---

## 8. Final Score /10

### Category scores
- **safety:** 7.8/10
- **reliability:** 7.2/10
- **speed:** 4.5/10
- **observability:** 6.8/10
- **maintainability:** 5.9/10
- **operator usability:** 6.6/10
- **recovery after crash:** 7.4/10
- **scale readiness:** 4.8/10

### Overall
- **Final Score: 6.4 / 10**
- **Production-ready for prop desk?** **No (not yet).**

A prop desk could consider a **limited pilot** only after all P1 items are closed and re-validated with sealed tests + incident replay drills.