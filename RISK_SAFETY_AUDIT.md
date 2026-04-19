# MMM Risk & Safety Audit

**Date:** 2026-04-18
**Mode:** Read-only forensic audit (no code changes)
**Scope:** `webui/backend/routes/mmm/*` runtime controls, lifecycle APIs, persistence, and sealed contracts

---

## Executive Verdict

The MMM stack has **strong layered safety controls** and is materially safer than a single-guard design:

- independent hard-stop thread,
- monitor-generation stale-thread protection,
- kill-switch market-order exit path,
- watchdog supervision with restart/backoff,
- strict fill ownership reconciliation,
- transactional persistence + checksum integrity checks.

**Overall assessment:** **Production-capable with targeted residual risks** (mainly lifecycle-state edge cases and emergency control semantics under degraded runtime states).

---

## What Was Verified (Evidence-Backed)

### 1) Independent max-loss hard stop (not heartbeat-bound)

- `mmm_monitor.py` sealed block defines `HARD_STOP_INTERVAL = 10` and dedicated guard thread (`_start_hard_stop_guard`, `_run_hard_stop_guard`).
- Guard path uses canonical P&L (`compute_current_total_pnl`), then performs:
  1. alert,
  2. emergency close,
  3. stop.
- `_hard_stop_fired` prevents double-fire with heartbeat path.

**Risk effect:** prevents delayed max-loss response when heartbeat cadence degrades.

### 2) Kill switch + exit-all emergency semantics

- API endpoint `POST /session/<id>/kill_switch` is idempotent and transitions to `EXITING` with `_kill_switch_triggered=True`.
- `mmm_exit_all.py` routes kill-switch sessions to market-order close rounds (`use_market_orders=True`) and cancels pending adjustments first.
- `_close_one_side(..., emergency=True)` routes to `place_market_order_immediate` (`order_type="market_order"`).

**Risk effect:** prioritizes deterministic flattening speed in emergency mode.

### 3) Stale monitor prevention (phantom-order defense)

- Generation counter `_monitor_generation` is incremented on start.
- Heartbeat path and `_save_session(..., my_generation)` reject stale monitor saves.
- Guardian G5 (`mmm_guardian.py`) detects stale monitor and forces STOP semantics (not PAUSE).
- Monitor replacement waits for old thread (`join(timeout=15)`) before new monitor start.

**Risk effect:** reduces dual-monitor race/phantom-order class.

### 4) Watchdog supervision + EXITING stuck handling

- `mmm_watchdog.py` supervises both `RUNNING` and `EXITING` sessions.
- Detects dead thread and beat timeout.
- Uses deferred restarts + exponential backoff + max restart cap.
- For stuck `EXITING`, marks partial exit and persists fail-safe state.

**Risk effect:** prevents silent dead sessions and improves failure visibility.

### 5) Pending-order dedupe guard

- `mmm_pending_orders.py` tracks in-flight per `session_id` and side.
- Dual TTL model:
  - sentinel `order_id='pending'`: 90s,
  - real order IDs: 900s.
- Conservative behavior on verification failure returns `error` (treated as open).

**Risk effect:** mitigates duplicate adjustment accumulation under exchange ambiguity.

### 6) Fill sync strict ownership + sub-fill safety

- `mmm_fill_sync.py` matches fills strictly by `fill.order_id == position.close_order_id`.
- Non-owned fills are skipped (debug logged).
- Sub-fill-aware logic tracks cumulative closed lots before marking position fully closed.

**Risk effect:** avoids cross-order attribution and premature full-close booking.

### 7) Persistence integrity and write serialization

- `mmm_storage.py` validates raw checksum before post-load mutation (`_validate_checksum_raw`).
- `save_session` and `update_session` both use `BEGIN IMMEDIATE` transactions.
- checksum warning flag (`_checksum_warning`) is surfaced for operator visibility.

**Risk effect:** lowers lost-update and silent corruption risk.

### 8) Canonical total P&L formula consistency

- `mmm_pnl_core.py::compute_current_total_pnl` includes realized + unrealized − fees + perp + reverse.
- Safety and hard-stop paths reference the same formula.

**Risk effect:** avoids safety/UI divergence on true drawdown.

### 9) Margin guardian tiering and escalation

- `mmm_margin_guardian.py` enforces GREEN→CRITICAL transitions and lots-to-close estimation.
- Consecutive CRITICAL beats can escalate to `force_stop_session` action.
- `mmm_monitor.py::_check_margin_guardian` maps RED/CRITICAL to emergency close behavior.

**Risk effect:** adds dedicated margin-pressure response layer before liquidation territory.

### 10) Observability endpoints

- `GET /session/<id>/beat-health` returns health summary + circuit + watchdog status.
- `GET /metrics/aggregate` computes system health over sessions.
- `GET /emergency/health-check` covers storage/watchdog/websocket/memory/thread health.

**Risk effect:** improves operator diagnosis speed during stress.

---

## Contract Coverage Confirmed

Reviewed sealed tests (representative):

- `test_sealed_kill_switch_and_hard_stop.py`
- `test_kill_switch_endpoint.py`
- `test_sealed_mmm_pending_orders.py`
- `test_sealed_mmm_fill_sync.py`
- `test_sealed_mmm_circuit_breaker.py`
- `test_sealed_smart_execute.py`
- `test_sealed_mmm_storage.py`
- `test_sealed_mmm_adversarial_isolation.py`
- `test_sealed_margin_guardian.py`
- `test_sealed_mmm_margin_guardian_async.py`

These tests strongly anchor emergency-route behavior, dedupe guarantees, fill ownership, breaker transitions, execution terminal events, and storage integrity paths.

---

## Residual Risks & Gaps (Prioritized)

| ID | Severity | Finding | Evidence | Impact | Recommendation |
|---|---|---|---|---|---|
| R1 | **High** | `get_active_session_ids()` excludes `STARTING` and `PARTIAL_ENTRY` while broader active filters include them elsewhere. | `mmm_storage.py::get_active_session_ids`; `__init__.py::init_mmm` restore loop | Restart recovery can miss certain in-flight states. | Align active-state set across storage helpers and restore callers. |
| R2 | **Medium** | `emergency_stop_all` only stops sessions that have a live monitor object; `RUNNING` rows with missing/dead monitors are not explicitly marked failed/stopped in-loop. | `mmm_api.py::emergency_stop_all` | “Stop all” may under-deliver in degraded control-plane states. | Add explicit else-path: mark as failure + persist safe status or include in failed list. |
| R3 | **Medium** | Margin guardian monitor path is fail-open on internal exceptions (`return None`). | `mmm_monitor.py::_check_margin_guardian` exception path | During margin-check telemetry outages, this layer is bypassed until recovery. | Keep fail-open but add rate-limited critical alert/escalation if failures persist N beats. |
| R4 | **Low** | `force_heartbeat()` clears cooldown and consecutive-direction blocks as operator override. | `mmm_monitor.py::force_heartbeat` | Strong operator power can bypass throttles if misused. | Require privileged audit marker / role gate at API boundary (if not already enforced upstream). |

---

## Safety Posture Summary

### What is robust

- Emergency flatten path (kill switch + market orders) is explicit and contract-tested.
- Stale-thread/phantom-order defenses are layered (generation checks + guardian + save gate).
- Watchdog + circuit breaker provide graceful degradation rather than brittle hard-fail behavior.
- Fill reconciliation and persistence integrity are materially hardened.

### What remains most important to harden next

1. **Active-state consistency across storage helpers** (`STARTING` / `PARTIAL_ENTRY` handling).
2. **Emergency stop-all degraded-mode semantics** (monitor-missing cases).
3. **Persistent margin-check failure escalation policy** (while preserving fail-open intent).

---

## Audit Notes

- This audit was source-and-contract based; no live exchange execution was performed.
- No code, config, or schema changes were made in this pass.
- Findings are constrained to the inspected MMM backend/runtime scope.
