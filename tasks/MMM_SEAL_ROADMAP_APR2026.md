# MMM Sealing Roadmap — April 2026

> Created: 2026-04-17 after forensic sealing audit (see `mmm_workdone_march.md` line 4682)
> Protocol reference: `AI_SEAL.md` (Type-1 + Type-2 rules)
> Current sealed count: **77** (baseline test count: **1400 passed** as of 2026-04-17)

---

## Current State

| Metric | Value |
|---|---|
| Total backend MMM functions | 768 |
| Decorator-sealed (backend) | 43 |
| Unsealed | 725 |
| Total sealed entries (including frontend/JS) | 77 |
| Test baseline | 1400 passed, 1 pre-existing fail (unrelated) |

**Highest unsealed concentration:**

| File | Unsealed count | Recent churn (commits since Mar 20) |
|---|---|---|
| `mmm_api.py` | 98 | 15 |
| `mmm_monitor.py` | 79 | 25 — **HOLD** (see below) |
| `mmm_websocket.py` | 35 | low |
| `mmm_storage.py` | 29 | 6 |
| `mmm_executor.py` | 22 | 6 |
| `mmm_state.py` | high | 16 |
| `mmm_safety.py` | — | 7 |

---

## HOLD — Do Not Seal Yet

### `mmm_monitor.py` — core adjustment path

**Reason:** 14+ new bypass paths added 2026-04-17 for `STRADDLE_WITH_ADJUSTMENT`. None validated in a live session yet.

Changes that need at least 1 live session to settle:
- ITM guard disabled at 2 sites (`_process_adjustment`, `_process_shift_fallback`)
- Regime bypass at 5 sites (FORCE_REDUCE, PAUSE, BLOCK_ALL_SELLS, `should_block_sell`, auto-resume)
- 7 additional bypasses (stop_adjustments, reversal cooldown, reversal skip, whipsaw lot reduction, consecutive direction limit, proactive shift, whipsaw trigger widening)

**Gate to lift HOLD:** Run 1 complete live STRADDLE_WITH_ADJUSTMENT session, confirm no regressions, then seal.

---

## Seal Session Roadmap

Sessions are ordered: leaf/stable first, high-churn last. Each session = 1 function (or 1 tightly grouped cluster per AI_SEAL.md Rule 1).

> **Session baseline after S-1–S-4 (2026-04-17): 1459 passed, 0 failed**

---

### ~~Session S-1 — `mmm_storage.py`: `save_session` + `load_session`~~ ✅ DONE (#78, 13 contracts)

**File:** `webui/backend/routes/mmm/mmm_storage.py`
**Type:** Type-1 + Type-2 (infrastructure — silent skip possible if Redis/DB is down)
**What it does:** Persists and loads the full session dict to/from storage backend.
**Why now:** Pure data layer, no recent churn, highest dependency — everything in the stack calls these.
**Can be silently skipped?** YES — `save_session` catches exceptions internally; caller may not know save failed.
**Type-2 contracts needed:**
- Storage backend down → must not silently return True
- Partial write (exception mid-save) → session must not be partially corrupted on reload
- Stale/missing session key → `load_session` returns None, not raises

---

### ~~Session S-2 — `mmm_executor.py`: `smart_execute`~~ ✅ DONE (#79, 9 contracts)

**File:** `webui/backend/routes/mmm/mmm_executor.py`
**Type:** Type-1 + Type-2
**What it does:** Places exchange order with retry, repricing, and fill timeout. All order placement goes through this.
**Why now:** FIX-1.2 (terminal event for cancelled/failed orders) was just merged — seal locks the new contract.
**Can be silently skipped?** YES — if placement retries exhausted, order silently fails; no exception raised to caller.
**Type-2 contracts needed:**
- All retries exhausted → `ORDER_FAILED` event written to `session_event_log` (FIX-1.2 contract)
- Order goes dead (cancelled by exchange) → `ORDER_CANCELLED` event written
- `fill_timeout` DTE scaling: EMERGENCY gamma → cap 20s, DTE < 1h → cap 30s (FIX-2.1 contract)

---

### ~~Session S-3 — `mmm_pending_orders.py`: pending order guard~~ ✅ DONE (#80, 16 contracts)

**File:** `webui/backend/routes/mmm/mmm_pending_orders.py`
**Type:** Type-1 + Type-2
**What it does:** Checks if there are open pending orders before allowing a new adjustment.
**Why now:** Audit confirmed this is a Type-2 hotspot — its 4 guard branches (`filled/open/error/stale`) gate `_process_adjustment()`.
**Can be silently skipped?** YES — stale order not detected → adjustment fires on top of existing open order.
**Type-2 contracts needed:**
- Stale order (age > threshold) → treated as cleared, not blocking
- Dead order (error/cancelled state) → treated as cleared
- Open order → blocks adjustment
- Filled order → clears pending state, does not block

---

### ~~Session S-4 — `mmm_fill_sync.py`: fill deduplication~~ ✅ DONE (#81, 11 contracts)

**File:** `webui/backend/routes/mmm/mmm_fill_sync.py`
**Type:** Type-1 only (pure logic, no silent-skip risk)
**What it does:** Deduplicates fills arriving from WS and REST polling, preventing double-counting.
**Why now:** Stable, pure logic, leaf function — no external dependencies.
**Can be silently skipped?** NO
**Type-1 contracts needed:**
- Same fill_id from WS and REST → counted once
- Fill for unknown session → discarded
- Fill arriving out of order (REST before WS) → handled correctly

---

### Session S-5 — `mmm_api.py`: emergency control routes

**File:** `webui/backend/routes/mmm/mmm_api.py`
**Type:** Type-1 + Type-2 (most critical — these are the last-resort controls)
**Target functions:** `stop_all_sessions`, `pause_all_sessions`, `close_all_positions_route`, `reset_circuit_breaker`, `reconcile_route`
**Why now:** These are the emergency control plane. Highest stakes if they silently fail. No recent churn.
**Can be silently skipped?** YES — Flask routes can swallow exceptions; a failed `stop_all` with 200 OK is dangerous.
**Type-2 contracts needed:**
- `stop_all_sessions`: every RUNNING session transitions to STOPPED (not just the first)
- `pause_all_sessions`: every RUNNING session transitions to PAUSED
- `close_all_positions_route`: returns error if any position close fails (not silent 200)
- `reset_circuit_breaker`: clears the correct state keys, verified by subsequent heartbeat behavior
- `reconcile_route`: triggers actual reconciliation, not just a log entry

---

### Session S-6 — `mmm_watchdog.py`: watchdog health check

**File:** `webui/backend/routes/mmm/mmm_watchdog.py`
**Type:** Type-1 + Type-2
**What it does:** Supervisory loop — detects stale heartbeats, dead monitors, and fires alerts.
**Can be silently skipped?** YES — if the watchdog's own check loop stalls, it stops alerting without notice.
**Type-2 contracts needed:**
- Monitor heartbeat stale > threshold → fires alert within 1 check cycle
- Watchdog itself must emit a verifiable liveness signal
- Multiple stale monitors → alerts for each, not just the first

---

### Session S-7 — `mmm_guardian.py`: generation integrity check

**File:** `webui/backend/routes/mmm/mmm_guardian.py`
**Target function:** `check_generation_integrity` (Guardian G5 — innermost fallback, stale monitor layer 3)
**Type:** Type-1 + Type-2
**Why this matters:** This is the innermost of the 3-layer stale monitor fix (CLAUDE.md §4). If this seal breaks, P0 incident of 2026-03-24 (560 phantom SELL lots) can recur.
**Can be silently skipped?** YES — `_heartbeat()` swallows exceptions; if G5 raises, stale monitor continues unchecked.
**Type-2 contracts needed:**
- Stale gen detected → calls `handle_stale_monitor()` with STOP (not pause)
- Exception in G5 → does NOT silently continue heartbeat

---

### Session S-8 — `mmm_websocket.py`: WS emission health

**File:** `webui/backend/routes/mmm/mmm_websocket.py`
**Type:** Type-1 + Type-2
**What it does:** Emits session state to connected frontend clients. Health counters track emission failures.
**Can be silently skipped?** YES — `emit()` catches SocketIO errors internally; frontend goes stale without knowing.
**Type-2 contracts needed:**
- SocketIO error during emit → health counter incremented, not swallowed silently
- Health counter threshold exceeded → logged at WARNING or above
- `emit_safety()` is sync (not async) — must never be wrapped in `run_until_complete()`

---

### Session S-9 — `mmm_state.py`: `initialize_session_defaults` + `initialize_reverse_state`

**File:** `webui/backend/routes/mmm/mmm_state.py`
**Type:** Type-1 only
**What it does:** Sets default keys on a new or restored session dict.
**Why now:** Session restore compatibility invariant (CLAUDE.md §5) — `initialize_reverse_state` must be called when `'_reverse' not in session`. Seal locks this contract.
**Can be silently skipped?** NO — called at session creation, not conditional.
**Type-1 contracts needed:**
- New session → all expected default keys present with correct types
- Restored session missing `_reverse` → `initialize_reverse_state` adds it correctly
- Calling twice (idempotent) → no mutation on second call

---

### Session S-10 — `mmm_monitor.py`: `_heartbeat_inner` (AFTER HOLD LIFTED)

**File:** `webui/backend/routes/mmm/mmm_monitor.py`
**Type:** Type-1 + Type-2 (mandatory — this is the heartbeat orchestrator)
**Gate:** Only seal AFTER STRADDLE_WITH_ADJUSTMENT live session validates the 2026-04-17 bypasses.
**What it does:** Inner heartbeat body — fetches premiums, checks safety, triggers adjustments.
**Can be silently skipped?** YES — multiple early returns and degraded paths.
**Type-2 contracts needed:**
- `_fetch_premiums_with_fallback()` returns None → heartbeat must not silently skip safety checks
- Degraded path (partial premium fetch) → emits at WARNING level
- Stale generation detected → calls stale monitor handler, does NOT continue loop

---

## Type-2 Infrastructure Hotspots Summary

These require Type-2 tests regardless of which session seals them:

| Hotspot | File | Risk if not sealed |
|---|---|---|
| `_heartbeat_inner` degraded paths | `mmm_monitor.py` | Safety checks silently skipped on bad network |
| `_fetch_premiums_with_fallback` | `mmm_monitor.py` | None return silently bypasses position checks |
| Pending order guard branches | `mmm_pending_orders.py` | Double-adjustment on stale pending order |
| `smart_execute` retry exhaustion | `mmm_executor.py` | No audit trail when order silently fails |
| `stop_all` / `close_all` emergency routes | `mmm_api.py` | Silent failure on emergency commands |
| `check_generation_integrity` (G5) | `mmm_guardian.py` | Stale monitor survives if G5 raises |
| Watchdog health check | `mmm_watchdog.py` | Dead monitor not detected |

---

## Promotion Gate Reminder

From CLAUDE.md — MMM Canary → Live requires:

- [ ] All Tier 1 + Tier 2 MMM functions sealed
- [ ] Zero sealed test failures for 7 days
- [ ] 3+ complete canary sessions without manual intervention
- [ ] All safety checks verified against real session data
- [ ] Reconciliation verified after at least 1 planned restart

Sealing sessions S-1 through S-9 above cover the Tier 2 safety + infrastructure layer. That gets us significantly closer to promotion criteria.

---

## How to Use This File

1. Pick the next session from the list above (S-1, S-2, etc.)
2. Fill in `AI_SEAL.md` Section A using the details in this file
3. Say "Seal this" — AI executes the protocol
4. After tests pass, cross off the session here and update `AI_ALREADY_SEALED.md`
5. Repeat

> Run sealed tests before and after every session:
> ```bash
> python3 -m pytest webui/ bot/ -m sealed -v
> ```
> Baseline must stay at or above 1400 passed.
