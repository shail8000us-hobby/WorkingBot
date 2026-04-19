# AUDIT_REAL_MONEY_SAFETY.md

**Date:** 2026-04-17  
**Scope:** Real-money safety audit (read-only, no code changes) for MMM runtime + control plane.

## Executive Summary

The **runtime trading core** is materially stronger than average for a real-money bot: there are layered stale-monitor controls, independent hard-stop guarding, duplicate-order protections, partial-beat safety behavior, and exchange reconciliation/fill-sync paths.

However, the **API control plane** has critical gaps that can still create real-money loss scenarios even when core logic is solid. The top issues are:

1. **No auth/authorization on money-moving MMM endpoints** (P0)
2. **Exit/Kill-Switch can report success without guaranteed execution if monitor is missing** (P0)
3. **Emergency pause/stop-all flows can desynchronize runtime vs persisted state** (P0)

Bottom line: core engine safety is good, but operational/control-plane safety is not yet production-safe for unattended real-money exposure.

## Files Audited

- `MMM_LAST_3_SESSIONS.md`
- `webui/backend/routes/mmm/mmm_monitor.py`
- `webui/backend/routes/mmm/mmm_watchdog.py`
- `webui/backend/routes/mmm/mmm_pending_orders.py`
- `webui/backend/routes/mmm/mmm_executor.py`
- `webui/backend/routes/mmm/mmm_engine.py`
- `webui/backend/routes/mmm/mmm_safety.py`
- `webui/backend/routes/mmm/mmm_close_at_5.py`
- `webui/backend/routes/mmm/mmm_exit_all.py`
- `webui/backend/routes/mmm/mmm_recycler.py`
- `webui/backend/routes/mmm/mmm_api.py`
- `webui/backend/app.py`

## Findings

### F1 — Unauthenticated money-control surface (P0)

**Severity:** P0  
**Why It Matters:** High-risk endpoints (start/stop/pause/resume/kill-switch/exit-all/manual reduce/manual inject/emergency actions) are callable without explicit route-level auth controls. Combined with broad network exposure (`0.0.0.0`) and permissive CORS configuration, this is a direct real-money misuse vector.

**Evidence:**
- MMM endpoints in `mmm_api.py` do not enforce per-route auth decorators or token checks.
- `app.py` has no global auth middleware for `/api/mmm/*`.
- CORS configuration is permissive and backend binds broadly.

**Suggested Fix:**
1. Enforce mandatory authN+authZ on all `/api/mmm/*` mutating routes.
2. Add role-based guardrails for destructive actions (`kill_switch`, `exit_all`, emergency routes).
3. Require anti-CSRF for browser-originated mutating actions.
4. Restrict CORS/ingress to trusted origins/networks only.

**Safe Implementation Notes for Claude:**
- Implement auth at blueprint boundary first; do **not** alter trading math/execution modules.
- Add an explicit allowlist for internal service tokens used by backend automation.
- Roll out in observe mode first (`log-only`) before hard-enforce.

---

### F2 — `exit_all` / `kill_switch` can be non-executing success when monitor missing (P0)

**Severity:** P0  
**Why It Matters:** In crash/dead-monitor scenarios, API can return accepted/initiated while no heartbeat is running to actually execute close logic. This is a missed-exit failure mode under stress.

**Evidence:**
- `mmm_api.py` routes set `strategy_status='EXITING'` and only trigger `force_heartbeat()` **if** monitor exists.
- No guaranteed fallback worker path when monitor is absent.

**Suggested Fix:**
1. If monitor is absent, start a dedicated EXITING worker immediately (or start monitor in EXITING mode) before returning success.
2. Return explicit execution state: `queued`, `worker_started`, `monitor_missing`, `verified_closed`.
3. Add hard postcondition check against exchange positions before marking completion.

**Safe Implementation Notes for Claude:**
- Reuse `mmm_exit_all.run_exit_all()`; do not fork duplicate close logic.
- Preserve close ordering invariant: reverse → perp → core options.
- Preserve stale-generation protections in monitor lifecycle.

---

### F3 — Emergency pause/stop-all state desynchronization risk (P0)

**Severity:** P0  
**Why It Matters:** Control-plane operations can leave DB/session status inconsistent with actual monitor runtime (e.g., DB says PAUSED while monitor is still running or has been stopped). This can hide live risk and break operator mental model.

**Evidence:**
- `emergency_pause_all`: updates persisted status to `PAUSED` without calling `monitor.pause()`.
- `emergency_stop_all`: calls `monitor.stop(...)` then writes session object with `strategy_status='PAUSED'`.

**Suggested Fix:**
1. `pause-all`: call runtime pause on active monitors, verify `_paused=True`, then persist.
2. `stop-all`: do not overwrite STOPPED state with stale object writes.
3. Add reconciliation endpoint: runtime state vs persisted state mismatch detector.

**Safe Implementation Notes for Claude:**
- Never write stale session snapshots after invoking `monitor.stop()`.
- Use monitor-owned state transitions where monitor exists; persist via minimal field updates only.

---

### F4 — Max-loss can be effectively disabled by config (`max_loss_amount <= 0`) (P1)

**Severity:** P1  
**Why It Matters:** Current behavior warns but continues. A misconfig (or bad patch) can silently remove hard-stop protection in real money.

**Evidence:**
- `mmm_safety.check_max_loss()` emits critical config event but action is warn-only when threshold <= 0.

**Suggested Fix:**
1. Block session start when `max_loss_amount <= 0` unless explicit privileged override.
2. Reject hot-reload PATCH that sets non-positive max loss on running session.
3. Add UI hard guard + confirmation for dangerous override mode.

**Safe Implementation Notes for Claude:**
- Validate at API boundary (`create` + `PATCH`) rather than patching monitor internals.
- Keep canonical P&L formula untouched (`compute_current_total_pnl`).

---

### F5 — `emergency_close_all_positions` executes monitor internals from foreign loop (P1)

**Severity:** P1  
**Why It Matters:** Invoking monitor internals directly from a separate event loop risks race conditions with the monitor heartbeat and inconsistent close behavior during emergency actions.

**Evidence:**
- Route creates new event loop and directly awaits `monitor._auto_close_all(...)` across monitors.
- Dry-run logic references legacy per-position keys and may misreport exposure.

**Suggested Fix:**
1. Dispatch close work onto each monitor’s own loop (`run_coroutine_threadsafe`) or route through EXITING flow.
2. Normalize dry-run/introspection to unified `positions[]` ledger only.
3. Add strict post-close exchange verification step before success.

**Safe Implementation Notes for Claude:**
- Avoid calling private monitor coroutines from foreign loops.
- Keep emergency path deterministic and single-thread ownership per session.

---

### F6 — Duplicate-order prevention not fully restart-persistent (P2)

**Severity:** P2  
**Why It Matters:** In-memory pending registry is strong intra-process, but restart windows can still lose pending context while exchange orders remain open.

**Evidence:**
- `mmm_pending_orders` is process-local memory.
- Startup clears stale in-memory entries by design.

**Suggested Fix:**
1. Persist pending intent metadata (order_id/client_order_id/side/strike) in session state.
2. Before new side order, query exchange open orders by `client_order_id`/symbol+side and short-circuit if already pending.

**Safe Implementation Notes for Claude:**
- Keep current conservative “skip on uncertainty” behavior.
- Do not weaken existing exchange-state checks in pending resolver.

---

### F7 — Manual control endpoints can race monitor in-memory snapshot (P2)

**Severity:** P2  
**Why It Matters:** Manual mutate endpoints write storage snapshots while monitor owns in-memory runtime state. Usually self-heals next beat, but there is a risk window for one-beat incorrect decisions.

**Evidence:**
- Multiple endpoints in `mmm_api.py` load from storage, mutate, save directly while monitor may already be running.

**Suggested Fix:**
1. If monitor exists, route mutation through monitor-owned state path (under monitor lock) and persist afterward.
2. If monitor absent, reject or queue mutation until runtime owner is available.

**Safe Implementation Notes for Claude:**
- Prefer single-writer model (monitor owns live session mutations).
- Preserve current heartbeat reload model; avoid dual-writer behavior.

## Severity (P0/P1/P2/P3)

- **P0 (Critical / immediate real-money danger):** 3
- **P1 (High / can cause material loss in realistic scenarios):** 2
- **P2 (Medium / bounded but meaningful risk):** 2
- **P3 (Low / hygiene/observability):** 0

## Why It Matters

Even with a robust trading engine, real-money safety fails if control-plane operations are unauthenticated, non-atomic, or can report success without guaranteed execution. Most catastrophic losses in automated systems happen during stress transitions (crash/restart/emergency), not in normal heartbeats.

## Suggested Fix (Priority Order)

1. **Lock down auth on MMM mutating routes** (P0)  
2. **Guarantee exit execution when monitor is absent** (P0)  
3. **Fix emergency pause/stop-all runtime-vs-storage desync** (P0)  
4. **Harden max-loss config validation** (P1)  
5. **Unify emergency close execution ownership to monitor loop** (P1)  
6. **Persist pending-order intent across restarts** (P2)

## Safe Implementation Notes for Claude

- Do **not** change core P&L formulas or stale-monitor 3-layer protections while implementing control-plane fixes.
- Preserve these invariants:
  - stale monitor stop behavior in `_run_loop` + guardian G5
  - generation-guarded `_save_session()` behavior
  - `emit_safety()` sync call semantics
  - reverse close order (reverse → perp → core)
- Implement high-risk fixes at API/route and monitor-lifecycle boundaries first; keep engine/executor math unchanged.
- Add post-action verification checks (exchange truth) to emergency endpoints before reporting success.

## Risk-Class Coverage (Requested)

| Risk Class | Current State | Primary Evidence | Residual Severity |
|---|---|---|---|
| Runaway lots | Strongly mitigated (caps, velocity, confidence gates) | `mmm_engine.py`, `mmm_safety.py` | P2 |
| Stale feed trades | Mitigated (partial-beat + cache + confidence) | `mmm_monitor.py` | P2 |
| Duplicate orders | Mitigated intra-process; weaker across restart | `mmm_pending_orders.py` | P2 |
| Missed exits | **Critical residual** in monitor-missing exit paths | `mmm_api.py` + `mmm_exit_all.py` | **P0** |
| API failure handling | Generally strong (retry/reprice/fallback) | `mmm_executor.py`, `mmm_monitor.py` | P2 |
| Reconnect chaos | Mostly mitigated by watchdog; emergency endpoints still risky | `mmm_watchdog.py`, `mmm_api.py` | P1 |
| Stop-loss bypass | Core strong; config disable path remains | `mmm_safety.py` | P1 |
| State corruption | Control-plane emergency routes can desync state | `mmm_api.py` | **P0** |
| Ghost positions | Strong reconciliation/fill-sync stack | `mmm_monitor.py` | P2 |
| Mobile misuse risk | **Critical** (unauthenticated mutating API) | `app.py` + `mmm_api.py` | **P0** |

## Final Score /10

**6.1 / 10**

- **+** Strong runtime safeguards in monitor/watchdog/executor/reconciliation layers.
- **−** Control-plane P0 gaps (auth + guaranteed emergency execution + state desync) materially reduce real-money safety.

**Production verdict:** **Not safe enough for unattended real-money operation until all P0 items are fixed.**
