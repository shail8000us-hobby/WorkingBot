# AUDIT_EXECUTION_SPEED — MMM Execution Latency Audit (Audit-Only)

Date: 2026-04-17  
Scope: **Audit only** (no code changes, no patches to MMM logic)

---

## Executive finding

MMM feels slow primarily because the system is intentionally built around long control-loop cadence plus long order wait/reprice windows.

The biggest latency contributors are:

1. **Order execution wait loops** (`smart_execute`) that can block for minutes.
2. **Heartbeat cadence defaults** (`adjustment_interval`) that are high by design (300s default; active sessions observed at 900s and 3600s).
3. **Sequential heartbeat orchestration** that includes multiple network-heavy stages before decision/output.

This is not one bug; it is a stack of latency contributors that compound.

---

## Evidence snapshot (from code + live DB telemetry)

### Runtime telemetry (active sessions)

- Running sessions currently observed with `adjustment_interval` of **300s, 900s, and 3600s**.
- Persisted heartbeat health (`_health_summary`) for running sessions shows:
  - p50 latency roughly **2.0s–7.6s**
  - p95 latency roughly **23.6s–24.9s**

### Session payload size (storage impact)

- `mmm_sessions.db` contains session `data_json` payloads averaging about **353 KB** overall.
- Running sessions average about **285 KB**; max running observed about **397 KB**.
- Largest stored rows exceed **550 KB**.

### File persistence overhead (activity log)

- `mmm_activity_log.json` is ~**273 KB** and is rewritten (temp file + fsync + backup copy + replace) on frequent activity events.

---

## End-to-end latency map

## 1) Intent → order placement

- `ORDER_INTENT` is written after successful placement.
- Placement has retry logic (`INITIAL_PLACEMENT_RETRIES=3`, `POST_ONLY_RETRY_DELAY=1.5s`).

## 2) Confirm latency (placement → `ORDER_CONFIRMED`)

- Confirm is emitted only after fill confirmation.
- `smart_execute` defaults:
  - `FILL_CHECK_INTERVAL=3s`
  - `FILL_TIMEOUT=60s`
  - `MAX_REPRICE_ATTEMPTS=4`
- Worst-case per call (normal path) is approximately:

$$
T_{smart} \approx 4 \times 60\text{s} = 240\text{s}
$$

- Entry uses `ENTRY_REPRICE_ATTEMPTS=8` (per-leg, concurrent legs), so one leg can wait up to:

$$
T_{entry\ leg} \approx 8 \times 60\text{s} = 480\text{s}
$$

## 3) API retry inflation inside each step

- Shared async REST client (`_request_with_retry`) defaults to `max_retries=3`, per-attempt timeout 10s, exponential waits 1s then 2s.
- In degradation, a single call can stretch to roughly:

$$
T_{api\ call\ worst} \approx 3\times10\text{s} + (1+2)\text{s} = 33\text{s}
$$

- This can multiply inside fill checks, quote fetches, fill sync, reconciliation, and close flows.

## 4) Fill sync delay

- Fill sync runs in heartbeat step 0.1.
- If heartbeat interval is 300s+, fill-sync visibility can lag by up to one cycle.
- Fill sync also paginates (`_PAGE_SIZE=100`, `_MAX_PAGES=3`) using retrying REST calls.

## 5) Polling delay

- Main wait loop is interval-driven (`adjustment_interval`) with force polling every 0.5s.
- Proactive close watcher defaults:
  - 30s normal
  - 10s near-expiry
- Reconciliation runs every 5th heartbeat.

## 6) Persistence + UI emission

- Heartbeat invokes many `_save_my_session()` call sites across branches.
- Save path serializes full session JSON + SQLite write under `BEGIN IMMEDIATE`.
- Activity logging emits websocket + disk persistence frequently.

---

## Top causes of slow execution (ranked)

## P0 — Long smart-execution wait/reprice envelope

**Why it matters:** This is the largest direct latency block in trading-critical paths. One action can consume 4–8 minutes.

**Suggested fix:**
- **Fastest win (config):** lower `reprice_base_timeout_s` and/or `max_reprice_attempts` for non-entry flows.
- Keep longer patience only where fill quality materially justifies it.

**Safe implementation notes for Claude:**
- Do not weaken stale monitor protections (join + generation guards + G5).
- Do not bypass max-loss/hard-stop invariants.

---

## P0 — Heartbeat cadence itself is slow in active sessions

**Why it matters:** Even perfect internal code cannot react faster than the heartbeat schedule for many actions.

**Suggested fix:**
- **Fastest win (config):** reduce `adjustment_interval` on latency-sensitive sessions (e.g., 60–120s baseline, not 300–3600s).
- Keep longer intervals only for explicitly low-touch modes.

**Safe implementation notes for Claude:**
- If reducing interval, monitor API/rate-limit pressure and margin guardian behavior.

---

## P1 — Sequential heartbeat does too much synchronous work per cycle

**Why it matters:** A single beat includes reconciliation, fill sync, premium fetch, close scans, safety/regime, triggers, adjustment, delta hedge, P&L, saves, and emits.

**Suggested fix:**
- Split non-critical tasks (some telemetry/reconciliation/reporting) off the hot path.
- Preserve critical order: safety + close logic must remain deterministic.

**Safe implementation notes for Claude:**
- Keep hard-stop guard independent thread behavior intact.
- Keep reverse-mode hard `if/else` split untouched.

---

## P1 — Retry policy can inflate single API calls to ~33s

**Why it matters:** Under exchange/network stress, “3-second poll” loops are no longer 3 seconds in practice.

**Suggested fix:**
- Use stricter retry/timeouts for heartbeat polling/status calls than for placement endpoints.
- Distinguish “must-be-fast status check” vs “must-succeed transactional call.”

**Safe implementation notes for Claude:**
- Never remove retries on critical order placement/cancel paths without compensating safety.

---

## P1 — Storage and activity persistence in hot paths

**Why it matters:** Frequent full-session saves (hundreds of KB each) plus activity-log disk writes increase loop latency and contention.

**Suggested fix:**
- Coalesce saves (dirty-flag + end-of-beat flush for non-critical fields).
- Move activity disk persistence to buffered/background batching.

**Safe implementation notes for Claude:**
- Any save-throttling must preserve generation-guard stale-monitor protections.
- Do not skip critical state writes on stop/auto-close/hard-stop paths.

---

## P2 — Fill-sync and reconciliation cadence delay state convergence

**Why it matters:** Realized state can be correct on exchange but appear late in session/UI.

**Suggested fix:**
- Trigger targeted immediate fill-sync after close-heavy actions (already partially done in shutdown path; extend carefully).
- Consider adaptive reconciliation frequency under mismatch signals.

**Safe implementation notes for Claude:**
- Fill sync must remain additive and idempotent; never double-book.

---

## P2 — Queue overflow / drop behavior under stress

**Why it matters:** `audit_log` and `event_log` are bounded (`_MAX_QUEUE=2000`) and can drop entries when backpressured.

**Suggested fix:**
- Add backpressure metrics/alerts and drop counters to heartbeat summary.
- Harden event writer DB-error handling to avoid retry storms/backlog growth.

**Safe implementation notes for Claude:**
- Keep write path non-blocking for trading thread.

---

## P3 — Websocket emission is synchronous and high-chatter

**Why it matters:** Under heavy event volume, UI emission can contribute latency/jitter.

**Suggested fix:**
- Coalesce low-priority events and reduce duplicate chatter.
- Keep heartbeat summary as the primary UI channel.

**Safe implementation notes for Claude:**
- Never suppress critical safety/stop emissions.

---

## Fastest wins (prioritized)

## 1) No-code configuration wins (fastest)

1. Lower `adjustment_interval` for latency-critical sessions.
2. Lower `reprice_base_timeout_s` (and optionally `max_reprice_attempts`) for non-entry paths.
3. Use aggressive close watcher settings near expiry where needed.

## 2) Low-risk code wins

1. Introduce save coalescing for non-critical state fields.
2. Move activity file writes off hot path to buffered writer.
3. Separate retry policy profiles by call type (status vs transactional).

## 3) Higher-impact architecture wins

1. Decouple long order-wait loops from the primary heartbeat thread.
2. Promote event-driven fill confirmation path (websocket/order updates) as primary, polling as fallback.

---

## Safety constraints that must remain intact during any speed work

- Stale monitor 3-layer protections must remain intact.
- Hard-stop guard invariants must remain intact.
- Reverse mode invariants must remain intact:
  - hard `if reverse_enabled && _reverse.active` branch separation
  - `_auto_close_all()` order: reverse → perp → core
  - no contamination of `_reverse` into CE/PE core ledgers

---

## Final score

**Current execution speed score: 4.5 / 10**

Rationale:
- Strong safety architecture, but responsiveness is materially limited by cadence and long blocking execution loops.
- Good reliability bias, but high-latency defaults and synchronous hot-path I/O make the system feel slow during live operations.
