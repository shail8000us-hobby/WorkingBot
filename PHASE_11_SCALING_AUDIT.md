# PHASE 11 — Scaling Readiness Audit
**Lead Agent:** Scaling Readiness Agent
**Status:** COMPLETE
**Date:** 2026-04-26
**Prior Phases Read:** Phase 01–10

---

## Executive Summary

The MMM algo is architecturally sound for current capital levels (~100 lots per side per session). Three P1/P2 blockers exist before capital scaling to 3× or higher:

1. **Gamma limits are fixed-dollar, not lot-proportional** — at 300+ lots the default `gamma_hard_limit=5000` fires at session start, blocking all adjustments.
2. **No API rate-limit budget tracking** — no proactive throttle; the circuit breaker reacts to 429 errors but cannot prevent them at high heartbeat frequency + large lot counts.
3. **SQLite contention under concurrent multi-session writes** — WAL mode handles N readers, but high-frequency saves from multiple concurrent sessions contend for the single write slot with 5s busy_timeout.

**Scaling Readiness Grade: C+** — current scale operates cleanly; blockers are specific and fixable before scaling.

---

## 1. Lot Cap Configuration

### 1.1 Default Parameter Values

| Parameter | Default | Notes |
|---|---|---|
| `initial_lots` | 10 | Typical entry lot count per side |
| `max_lots_per_side` | 100 | Hard cap per CE or PE |
| `max_total_exposure` | 200 | (= 2 × max_lots_per_side default) |
| `gamma_soft_limit` | 2500 | Dollar gamma soft cap |
| `gamma_hard_limit` | 5000 | Dollar gamma hard cap — blocks sells |
| `gamma_emergency_limit` | 10000 | Force reduce |
| `lot_velocity_limit` | 30 | Max lots added per 30-min window |

### 1.2 Gamma Limit Scaling Gap (A6-11 Confirmed)

**Finding A11-01 (P1):** Dollar gamma formula: `$Γ = |Γ_portfolio| × S² × 0.01`

For BTC options at $94,000 spot, gamma per lot ≈ 0.00002:

| Lots (per side × 2) | Dollar Gamma | Regime |
|---|---|---|
| 100 lots total | $94,000² × 0.00002 × 100 × 0.01 = $1,768 | NORMAL |
| 200 lots total | $3,536 | SOFT |
| 267 lots total | $5,000 | **HARD (blocks sells)** |
| 300 lots total | $5,643 | **HARD from session start** |
| 534 lots total | $10,000 | EMERGENCY (force reduce) |

At 3× capital (300 total lots), the gamma hard limit fires immediately on session start, blocking all adjustments. The bot becomes unable to hedge.

**Remediation:** Gamma limits must scale with `initial_lots` × a per-lot multiplier, OR express limits as `gamma_per_lot × initial_lots` rather than fixed dollar amounts. Specifically: `gamma_hard_limit = initial_lots × 2 × 0.00002 × S² × 0.01 × scaling_factor` where `scaling_factor` is operator-configurable.

---

## 2. API Rate Limits

### 2.1 Current API Call Budget Per Heartbeat

At `adjustment_interval=30s`, one heartbeat makes approximately:
- 1× L2 orderbook fetch (price feed, for trigger evaluation)
- 1× `/v2/fills` REST poll (fill_sync) + up to 3 paginated pages
- 0–2× order placements (smart_execute) — each blocks up to 4 min (60s × 4 attempts)
- Per order: 1× placement + up to 20 fill-status polls (every 3s) + up to 4× reprice + 4× amend

For a busy heartbeat (trigger fires + 2 orders placed): ~30 REST calls.

### 2.2 No Proactive Rate-Limit Tracking

**Finding A11-02 (P2):** Delta Exchange imposes API rate limits (exact values not exposed in codebase). The `mmm_circuit_breaker.py` handles 429 errors reactively (classifies as `err_type='rate_limit'`, applies backoff). There is no proactive rate-limit budget tracker that:
- Counts API calls per session per minute
- Throttles order placement if budget is near limit
- Coordinates across concurrent sessions sharing the same API key

At 3× sessions (3 monitors running simultaneously), the aggregate API call rate triples. A triggered beat on all sessions simultaneously could hit the rate limit, with the circuit breaker applying backoff — potentially leaving sessions unhedged for 30+ seconds during a rapid price move.

**Remediation:** Implement a shared rate-limit token bucket (per API key) that all sessions draw from. Heartbeat API calls draw tokens; if exhausted, non-critical calls (price feed) are deferred and critical calls (order placement) are prioritized.

---

## 3. Storage Performance Under Multi-Session

### 3.1 SQLite Architecture

- Single DB file: `mmm_sessions.db`
- WAL mode: N concurrent readers, 1 writer at a time
- `busy_timeout=5000ms` per connection (5s wait before error)
- Session saves: called after every heartbeat (every `adjustment_interval`, min 10s)

### 3.2 Write Contention

**Finding A11-03 (P2):** At N concurrent sessions, N monitor threads call `save_session()` simultaneously at heartbeat end. In WAL mode, only one write proceeds at a time; others wait up to `busy_timeout=5000ms`. For N=5 concurrent sessions, worst-case: 4 sessions each wait up to 5s for the write slot. If a session's heartbeat takes 5s+ in a retry (fill waiting), its save blocks other sessions' saves for those 5s.

For the current typical case (1–3 sessions, heartbeat every 30s), write contention is low. At 10 concurrent sessions with 10s heartbeat intervals and active fills, contention could cause save backlogs and `OperationalError: database is locked` exceptions.

Current behavior on lock error: `save_session()` returns `False`, `_save_my_session()` sets `_stale_abort_gen=True` and aborts the monitor — same path as the H-4 stale generation guard. This is safe (avoids writes to wrong session) but loses the heartbeat result.

**Remediation:** Consider per-session DB files (sharding by session_id) or a dedicated async write queue that serializes saves without blocking monitor threads.

### 3.3 Activity Log Contention

The activity log is a JSON file (`mmm_activity_log.json`), append-written on every activity event. At high frequency (sub-second activity during a rapid trigger sequence), file lock contention could occur. The activity log has a throttle for non-critical events (M-7 fix) — critical events always persist. This is acceptable for current scale.

---

## 4. Execution Throughput at Large Lot Counts

### 4.1 Multi-Fill Sub-Lot Handling

`smart_execute()` handles partial fills via `_cumulative_filled`/`_cumulative_fill_value`. For a 1000-lot sell order:
- Exchange may split into 50–200 individual sub-fills
- Each sub-fill arrives as a separate exchange fill event
- FillSync processes up to 300 fills per sync cycle (3 pages × 100)
- If a single entry produces >300 fills in one heartbeat interval, fills are truncated

**Finding A11-04 (P2):** FillSync truncation warning fires when 300 fills per cycle is exceeded, but the cursor advances to the newest fill across ALL 300 processed, potentially leaving unprocessed fills in a gap. The truncation message recommends "reducing heartbeat interval" but does not provide a mechanism to process the backlog in subsequent beats. At extreme scale (1000 lots, highly fragmented book), fills from one entry order could span multiple sync cycles with possible gaps.

### 4.2 Connection Overhead Per Order

`smart_execute()` creates a fresh `AsyncDeltaClient` per call. At concurrent CE+PE entry (via `asyncio.gather()`): 2 TCP connections opened simultaneously. At N concurrent sessions each placing simultaneous orders: 2N connections. This is acceptable for N≤5 but at N=20 could approach OS socket limits.

**Finding A11-05 (P3):** No connection pooling across concurrent `smart_execute` calls. Each call opens and closes an HTTP connection independently. At scale, a shared `httpx.AsyncClient` with connection pooling (one per event loop) would reduce overhead.

---

## 5. Position Limits and Lot Velocity

### 5.1 Lot Velocity Limiter

`lot_velocity_limit=30` per 30-minute window (default) caps lot accumulation rate. At 10× lots:
- Initial entry: 100 lots — exceeds 30-lot velocity limit immediately
- All subsequent adjustments in the first 30 min: blocked until window resets

**Finding A11-06 (P2):** `lot_velocity_limit` default (30 lots/30 min) is incompatible with `initial_lots` values above 30. At initial_lots=50, the first adjustment (which tries to hedge 50 new lots) fires `lot_velocity_limit` immediately. The parameter needs to scale with `initial_lots` (e.g., `lot_velocity_limit = initial_lots × 2`) rather than being set as an absolute count.

---

## 6. Architecture Issues — Phase 11

| ID | Problem | Risk | Priority |
|---|---|---|---|
| A11-01 | Fixed-dollar gamma limits block sells at ~267 lots (3× current scale) | Bot unable to hedge at 3× capital | P1 |
| A11-02 | No proactive API rate-limit tracking; circuit breaker is reactive only | 429 errors cause backoff during price moves at multi-session scale | P2 |
| A11-03 | SQLite WAL single-writer contention at N>5 concurrent sessions | Save backlog → lost heartbeats → stale session state | P2 |
| A11-04 | FillSync truncated at 300 fills; no backlog processing mechanism | Fills missed on large-lot entries with fragmented book | P2 |
| A11-05 | No connection pooling for concurrent smart_execute calls | Connection overhead at N=20+ concurrent sessions | P3 |
| A11-06 | lot_velocity_limit default (30) incompatible with initial_lots > 30 | First adjustment blocked on any session with initial_lots > lot_velocity_limit | P2 |

---

## 7. Scaling Readiness Checklist

| Threshold | Blocker | Status |
|---|---|---|
| 1× current capital (~100 lots) | None | **READY** |
| 2× (~200 lots) | A11-01 (gamma hard fires at 267 lots), A11-06 (velocity limit) | **NOT READY** — must raise gamma limits and velocity limit |
| 3× (~300 lots) | A11-01 critical, A11-02, A11-03 | **NOT READY** |
| 5× (~500 lots) | All P1/P2 blockers | **NOT READY** |
| 10× (~1000 lots) | All blockers + 10× scenario (Phase 10 S12) | **NOT READY** |

---

## 8. Positive Findings

1. **WAL mode** — SQLite WAL handles N concurrent readers without blocking; 1-writer contention is manageable at current scale
2. **lot_velocity_limit exists** — runaway lot accumulation has a per-window cap
3. **Circuit breaker** — reactive 429 handling prevents infinite retry storms
4. **Partial fill recovery in smart_execute** — correctly handles fragmented book fills
5. **`max_total_exposure` cap** — dual ceiling (per-side + total) prevents runaway exposure
6. **Margin Guardian available** — `margin_monitor_enabled=False` by default; can be enabled at scale to auto-reduce on margin approach
7. **FillSync truncation warning** — operator is notified when pagination limit is approached

---

## 9. Pass Criteria Checklist

- [x] Default parameter calibration reviewed against lot-scale targets
- [x] Gamma limit scaling gap confirmed (A11-01 = A6-11 from Phase 6)
- [x] API rate-limit budget analysis produced
- [x] SQLite contention analysis for multi-session writes
- [x] FillSync pagination limit at scale analyzed
- [x] Scaling readiness threshold table produced
- [x] Architecture Issue Register updated (Section 6)

**Phase 11 Status: PASSED. Bot is READY at current 1× scale. Clear blockers documented for 2×/3×/10× scaling. Must resolve A11-01 (gamma limits) and A11-06 (velocity limit) before first capital increase.**
