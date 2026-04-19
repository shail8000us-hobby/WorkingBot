# AUDIT_OBSERVABILITY

**Date:** 2026-04-18  
**Scope:** Monitoring + Logs observability audit (operator truth, alert quality, forensic readiness)

## 1. Executive Summary

Current observability is **partially implemented but not operator-truth-grade**.

The system has strong pieces (heartbeat writers, monitoring snapshots, multiple dashboards), but they are fragmented and inconsistent at integration boundaries. The biggest risk is **false confidence**: several endpoints and dashboards can look “healthy” while data is stale, synthetic, or silently dropped.

Top concerns:
- Monitoring snapshot schema drift causes silent fallback behavior (hidden failure mode).
- No first-class heartbeat proof metric/dashboard path for operators.
- Options dashboard metric names do not match exported metric definitions.
- Notification and risk fallbacks can report success/allow states during degraded conditions.
- Logs UI and backend retrieval are optimized for convenience, not forensic depth.

---

## 2. Files Audited

### Backend routes / APIs
- `webui/backend/routes/monitor.py`
- `webui/backend/routes/monitoring.py`
- `webui/backend/routes/metrics.py`
- `webui/backend/routes/health.py`
- `webui/backend/routes/logs.py`
- `webui/backend/routes/websocket_api.py`
- `webui/backend/routes/alerts/alert_routes.py`
- `webui/backend/routes/production_monitoring.py`
- `webui/backend/app.py`

### Backend services / utils
- `webui/backend/services/price_alert_monitor.py`
- `webui/backend/services/notifications.py`
- `webui/backend/utils/lightweight_health.py`
- `webui/backend/utils/health_monitor.py`
- `webui/backend/utils/metrics_logger.py`
- `webui/backend/utils/file_helpers.py`
- `webui/backend/log_parser.py`

### Bot monitoring internals
- `bot/heartbeat/monitor.py`
- `bot/strategy/modules/health_monitor.py`
- `bot/monitoring/health_check.py`

### Observability stack
- `observability/metrics/definitions.py`
- `observability/metrics/collectors.py`
- `observability/metrics/enhanced_collector.py`
- `observability/metrics/exporters.py`
- `observability/server/metrics_server.py`
- `observability/dashboards/system_health.json`
- `observability/dashboards/risk_management.json`
- `observability/dashboards/trading_performance.json`
- `observability/dashboards/options_analytics.json`

### Runtime artifacts sampled
- `data/monitoring_snapshot_BTCUSD_LONG.json`
- `data/monitoring_snapshot_ETHUSD_LONG.json`
- `webui/backend/webui_backend_fixed.log`

---

## 3. Findings

| ID | Area | Finding | Severity | Evidence (line-level) |
|---|---|---|---|---|
| F1 | Hidden failures / Missing metrics | **Monitoring snapshot schema drift**: API expects ISO timestamp + `layers`, while real snapshots use epoch float + `monitoring`. This can silently invalidate snapshot reads. | P1 | `webui/backend/routes/monitoring.py:145` (`datetime.fromisoformat(data['timestamp'])`), `monitoring.py:227-231` (`snapshot['layers']...`), vs `data/monitoring_snapshot_BTCUSD_LONG.json:2,96-97` (epoch timestamp + `monitoring`) |
| F2 | No heartbeat proof | Operator-facing monitor endpoint exposes only running boolean, no heartbeat age/proof chain. | P1 | `webui/backend/routes/monitor.py:156` (`'running': is_monitor_running()`) |
| F3 | Missing metrics / Weak dashboards | **No heartbeat metrics defined** in Prometheus metric definitions; dashboards cannot show heartbeat freshness/timeout proof. | P1 | Search result: no `heartbeat` in `observability/metrics/definitions.py`; no `heartbeat|stale|watchdog` in `observability/dashboards/*.json` |
| F4 | Weak dashboards | WebSocket “health” endpoint returns mostly static capability payload and note, not real runtime connection telemetry. | P1 | `webui/backend/routes/websocket_api.py:73` (comment: would read shared state in production), `:78`, `:95` |
| F5 | Hidden failures | Notification success can be overstated because `in_app` is always `True`; alert history may mark success despite external channel failures. | P1 | `webui/backend/services/notifications.py:231-234` (`'in_app': True`), `price_alert_monitor.py:222` (`update_alert_history(... success ...)`) |
| F6 | Noisy alerts | `cross` direction alert condition is hardcoded true (“simplified”), which can trigger noisy/repeated alerts not tied to actual crossing logic. | P2 | `webui/backend/services/price_alert_monitor.py:135-137` |
| F7 | Hidden failures | Heartbeat monitor treats read/parsing failures as healthy (`return True`), potentially masking monitor blindness. | P2 | `bot/heartbeat/monitor.py:194` (`return True  # Don't take action on read errors`) |
| F8 | Hidden failures / Safety posture | Risk API defaults to allow trading when risk manager is unavailable or errors occur. | P1 | `webui/backend/routes/production_monitoring.py:240`, `:268` |
| F9 | Missing metrics | Request metrics middleware skips core high-frequency endpoints (`/api/positions`, `/api/orders`, etc.), creating blind spots in operational latency/error telemetry. | P2 | `webui/backend/app.py:733-734` |
| F10 | Hidden failures | Metrics logging failures are debug-only and non-actionable; operator cannot see metric pipeline degradation quickly. | P2 | `webui/backend/app.py:762` |
| F11 | Weak dashboards | `/api/health` payload contract mismatch: frontend expects bot/guardian/telegram fields, backend basic health route returns only status+timestamp. | P1 | Backend: `webui/backend/routes/health.py:161-163`; Frontend expectations: `HealthCheckDashboard.js:118,157-162` |
| F12 | Weak dashboards / Missing alerts | Grafana JSON dashboards contain no explicit alert-rule blocks, so there is no embedded threshold alerting strategy. | P2 | Search result: no `"alert"`, `"alertRuleTags"`, `"noDataState"` in `observability/dashboards/*.json` |
| F13 | Weak dashboards | Options dashboard queries metric names that do not exist in current definitions (contract mismatch => empty/misleading panels). | P1 | Dashboard queries: `options_analytics.json:50,94,142,260,421`; definitions export different names in `definitions.py:485,499,506,513,520` |
| F14 | Hidden failures / Missing metrics | Enhanced collector uses label sets inconsistent with definitions and direct `._value` writes; likely to throw or silently skew counters/gauges. | P1 | `enhanced_collector.py:61-76`, `:212-236` |
| F15 | Useless logs / Poor forensic trail | Logs UI and retrieval are heavily truncated by default (30 lines, per-line ellipsis clipping), reducing incident reconstruction quality. | P2 | Frontend: `LogsPanel.js:80,114,148,180,480-483`; backend default: `routes/logs.py:57,145`; helper error strings as log lines: `file_helpers.py:55,62` |
| F16 | Noisy logs / Useless logs | Periodic state broadcast prints every 5s and emits largely placeholder state (`bot_status: {}`, `positions: {}`), adding volume with low incident value. | P3 | `webui/backend/app.py:1700-1708`; initial snapshot placeholders also in `app.py:969-973` |

---

## 4. Severity (P0/P1/P2/P3)

### Severity rubric used
- **P0**: Immediate capital/safety risk requiring emergency action.
- **P1**: Critical observability blind spot or false-green condition that can hide real failures.
- **P2**: Significant gap degrading detection, triage speed, or trust.
- **P3**: Hygiene/usability issue; non-blocking but worth fixing.

### Count summary
- **P0:** 0
- **P1:** 8 (`F1, F2, F3, F4, F5, F8, F11, F13, F14`)
- **P2:** 6 (`F6, F7, F9, F10, F12, F15`)
- **P3:** 1 (`F16`)

> Note: No direct P0 trading-logic defect was audited here; this report focuses observability truthfulness and operator control signal quality.

---

## 5. Why It Matters

If the operator’s telemetry is stale, synthetic, or incomplete, then **safety controls can appear healthy while reality is degraded**. In a live-money environment this increases time-to-detection and time-to-containment.

Key operational impact:
- **Delayed incident detection:** Missing heartbeat freshness and missing alert rules reduce early warning.
- **False-green dashboards:** Static or mismatched metrics can show normal status during broken pipelines.
- **Alert fatigue / distrust:** Noisy or semantically weak alerts (e.g., cross=true simplification) desensitize operators.
- **Forensic weakness:** 30-line truncated logs and clipped rows hinder root-cause analysis under pressure.
- **Hidden failure propagation:** permissive defaults (“allow trading” / “success true”) conceal subsystem outages.

---

## 6. Suggested Fix

### Priority 1 (Immediate: P1 closures)
1. **Fix monitoring snapshot contract**
   - Make `monitoring.py` parser compatible with epoch timestamps and `monitoring` schema, or version schemas explicitly.
   - Fail loudly (operator-visible) on schema mismatch.
2. **Add heartbeat proof path**
   - Expose `last_heartbeat`, `heartbeat_age_seconds`, timeout threshold from bot monitor path to `/api/monitor/*`.
   - Export Prometheus heartbeat freshness metric(s) and dashboard panel(s).
3. **Replace synthetic WebSocket health with real telemetry**
   - Back endpoint by shared runtime state (connected, last message age, reconnect attempts, disconnect reason).
4. **Fix notification success semantics**
   - Report channel-specific success/failure; do not auto-pass via `in_app=True` for external delivery outcomes.
5. **Align dashboard metric names with definitions**
   - Either rename metric definitions or update dashboard queries; add CI check to validate panel query names.

### Priority 2 (Stability / quality)
6. **Stop permissive “allow on error” risk fallback** for production contexts; return explicit degraded/block state.
7. **Instrument skipped core endpoints** (`/api/positions`, `/api/orders`) with sampled metrics to avoid blind spots.
8. **Add dashboard alert rules** (heartbeat stale, API latency p95 spike, error burst, no data).

### Priority 3 (Forensics and operator UX)
9. **Improve log forensics path**
   - Increase default retrieval depth and expose time-window query mode.
   - Preserve full lines (optional wrapping) instead of forced ellipsis clipping.
10. **Reduce low-value log noise**
   - Rate-limit periodic “broadcasted snapshot” prints and remove placeholder payload emissions.

---

## 7. Safe Implementation Notes for Claude

Given live-money sensitivity, implement observability fixes with strict safety discipline:

1. **Observability-only blast radius first**
   - Do not change order placement/cancellation logic while fixing telemetry.
   - Keep fixes to routes, collectors, dashboards, and UI rendering.

2. **Respect repository guardrails (`CLAUDE.md`)**
   - If touching MMM files, follow mandatory pre-change self-check and session log rules exactly.
   - Preserve stale-monitor and reverse-mode invariants.

3. **Rollout in phases with fallback**
   - Add schema-version compatibility before schema migration.
   - Ship metric-name compatibility aliases temporarily to avoid dashboard blackouts.

4. **Fail loudly, not silently**
   - Replace hidden permissive fallbacks with explicit degraded states and operator-visible warnings.

5. **Verification gates before live rollout**
   - Validate endpoint contracts (backend + frontend).
   - Validate dashboard queries against live metric registry.
   - Dry-run alert channels and verify per-channel delivery outcomes.

6. **Operational safety controls**
   - No bot/backend/monitor restart without explicit operator confirmation.
   - No live-order side effects from observability changes.

---

## 8. Final Score /10

**4.2 / 10**

### Rationale
- **Strengths:** rich monitoring components exist; multiple APIs and dashboards already in place.
- **Weaknesses:** integration contract drift, missing heartbeat proof, synthetic health surfaces, and forensics truncation materially reduce operator truth.

With Priority 1 fixes completed and validated, this can realistically move into the **7.5–8.0/10** observability range.
