# MMM Algo — Module Audit Plan

**Purpose:** Systematic, context-window-safe audit of all 51 MMM modules.
**Method:** One module per session. Each session audits a single file by loading the module + its direct callers + the state fields it touches — keeping total context manageable.
**Goal:** Find hidden bugs, broken invariants, race conditions, and cross-module interaction issues. Make the algo robust, correct, and fast.

---

## How To Run an Audit Session

1. Upload this file to Claude Code.
2. Say: **"Audit module M-XX"** (use the ID from the registry below).
3. Claude will load the file, its callers, its state fields, and run the checklist.
4. After the session, update the `Status` column in the registry below to `DONE` and note key findings.

> **Never audit across multiple modules in one session.** Keep it focused.

---

## Audit Checklist (applies to every module)

When auditing a module, check ALL of the following:

### A — Correctness
- [ ] Does each function do what its name and docstring claim?
- [ ] Are all edge cases handled (empty list, None, zero, negative)?
- [ ] Are there off-by-one errors in lot counts, index access, or range checks?
- [ ] Are float comparisons using `==` where they should use a threshold?
- [ ] Are there silent failures (bare `except`, `pass`, swallowed exceptions)?

### B — State Integrity
- [ ] What session keys does this module READ? Are they always guaranteed to exist?
- [ ] What session keys does this module WRITE? Can they be written in a partial/corrupt state?
- [ ] Is there any direct mutation of a shared dict that could race with the heartbeat loop?
- [ ] Are defaults used consistently (`session.get('key', default)` everywhere, or mixed)?
- [ ] Does any function leave the session in an inconsistent state if it raises mid-way?

### C — Concurrency / Async
- [ ] Is any `async def` called with `await` everywhere it's used? (no fire-and-forget)
- [ ] Is any sync function accidentally called with `await`?
- [ ] Is `asyncio.run()` or `run_until_complete()` called inside an already-running event loop?
- [ ] Are there any shared mutable objects (lists, dicts) accessed from both the monitor thread and an API route without a lock?

### D — Cross-Module Invariants
- [ ] Does this module assume another module has already run? (ordering dependency)
- [ ] Does this module write a field that another module reads — and are the names consistent?
- [ ] Does this module bypass any gate/guard that other modules respect? (e.g., regime check, lot velocity, generation guard)
- [ ] Does this module touch `session['ce']` or `session['pe']` directly in a way that could corrupt lot accounting?

### E — Safety / Known Bad Patterns
- [ ] Does any order placement happen without checking: max_loss, lot_velocity, regime gate, generation guard?
- [ ] Does any SELL order get placed without verifying the position actually exists?
- [ ] Is `_being_closed` set before or after the order is placed? (must be before)
- [ ] Does any loop break condition allow a stale monitor to continue trading?
- [ ] Is there a code path that could place orders during wind-down or STOP state?

### F — Performance
- [ ] Are there any O(N²) scans over position lists? (N can reach 50+ lots)
- [ ] Is any heavy computation done inside the heartbeat loop that could be cached?
- [ ] Are there repeated `session.get()` calls for the same key that should be extracted once?
- [ ] Are there redundant DB/file reads inside a tight loop?

### G — Test Coverage
- [ ] Does a sealed test exist for this module?
- [ ] Do existing tests cover the edge cases found in checklist A?
- [ ] Are there critical paths with zero test coverage?
- [ ] Do tests mock state correctly — or do they test against stale assumptions?

---

## Module Registry

> **Tiers:** P0 = live trading + safety (audit first) | P1 = order execution | P2 = logic/P&L | P3 = supporting/infra

| ID | File | Tier | Purpose (one line) | Sealed Test? | Status | Key Findings |
|----|------|------|--------------------|--------------|--------|--------------|
| M-01 | `mmm_monitor.py` | P0 | Central heartbeat orchestration loop — drives all phases | ✗ | DONE | BUG-1: `_save_session` returned `None` on exception (breaks stale guard Layer 2). BUG-2: 7 early-return paths used inline P&L formula (missing perp+reverse). BUG-3: `asyncio.gather(return_exceptions=False)` in emergency close. BUG-4: dead `_gamma_emergency_wind_down` flag. BUG-5: dead `_process_proactive_wind_down` method. BUG-6: stale log hardcoded `{3}`. BUG-7/8: deferred (velocity helper refactor, test coverage). All 6 fixed 2026-04-04. |
| M-02 | `mmm_engine.py` | P0 | Core P&L formulas, adjustment sizing, lot math | ✗ | DONE | BUG-1: `reconcile_pnl` compared options-only `tracked` vs perp+reverse-inclusive `net_pnl` → phantom discrepancies every heartbeat. BUG-2: `calculate_reversal_loss` had no explicit None check (unlike `calculate_standard_loss`). BUG-3: commission `or` chain falsy-unsafe for `paid_commission=0.0`. BUG-4: no sealed tests for 4 core functions (deferred). All 3 fixed 2026-04-04. |
| M-03 | `mmm_guardian.py` | P0 | Multi-layer safety guardian — generation guard, G5 heartbeat check | ✗ | TODO | |
| M-04 | `mmm_safety.py` | P0 | Max loss check, lot velocity, gate enforcement | `test_sealed_mmm_safety.py` | TODO | |
| M-05 | `mmm_executor.py` | P0 | Places real orders on exchange — BUY/SELL/CANCEL | ✗ | TODO | |
| M-06 | `mmm_margin_guardian.py` | P0 | Real-time margin check, emergency close trigger | `test_sealed_mmm_margin_guardian_async.py` | TODO | |
| M-07 | `mmm_circuit_breaker.py` | P0 | Halts trading on repeated failures or anomalies | `test_sealed_mmm_circuit_breaker.py` | TODO | |
| M-08 | `mmm_fill_sync.py` | P0 | Syncs exchange fills back into session state | ✗ | TODO | |
| M-09 | `mmm_perp_hedge.py` | P1 | Manages perpetual hedge positions | `test_sealed_mmm_perp_hedge.py` | TODO | |
| M-10 | `mmm_replenish.py` | P1 | Auto-replenishes closed side using ranked strikes | `test_sealed_mmm_replenish.py` | TODO | |
| M-11 | `mmm_close_at_5.py` | P1 | Closes positions at 5pm / expiry boundary | `test_sealed_mmm_close_at_5.py` | TODO | |
| M-12 | `mmm_strike_shift.py` | P1 | Shifts strikes when price moves out of range | `test_sealed_mmm_strike_shift.py` | TODO | |
| M-13 | `mmm_harvester.py` | P1 | Harvests profitable legs — sells winners | `test_sealed_mmm_harvester.py` | TODO | |
| M-14 | `mmm_recycler.py` | P1 | Recycles closed lots by rolling to new strikes | `test_sealed_mmm_recycler.py` | TODO | |
| M-15 | `mmm_wind_down.py` | P1 | Orderly wind-down — closes all positions gracefully | `test_sealed_mmm_wind_down.py` | TODO | |
| M-16 | `mmm_exit_all.py` | P1 | Emergency exit — closes everything immediately | ✗ | TODO | |
| M-17 | `mmm_reverse.py` | P1 | Controlled Reverse Mode overlay (isolated from core) | ✗ | TODO | |
| M-18 | `mmm_pnl_core.py` | P2 | Session P&L computation — realized, unrealized, total | `test_sealed_mmm_pnl_core.py` | TODO | |
| M-19 | `mmm_regime.py` | P2 | Market regime detection — gates sells/buys by regime | `test_sealed_mmm_regime.py` | TODO | |
| M-20 | `mmm_state.py` | P2 | Session state management — load, save, validate | `test_sealed_mmm_state.py` | TODO | |
| M-21 | `mmm_storage.py` | P2 | Persistence layer — file I/O for session JSON | `test_sealed_mmm_storage.py` | TODO | |
| M-22 | `mmm_gamma.py` | P2 | Gamma exposure tracking and position gamma | `test_sealed_mmm_gamma.py` | TODO | |
| M-23 | `mmm_gamma_detector.py` | P2 | Detects gamma spikes, triggers protective actions | `test_sealed_mmm_gamma_detector.py` | TODO | |
| M-24 | `mmm_breakeven_engine.py` | P2 | Computes breakeven levels per side | `test_sealed_mmm_breakeven_engine.py` | TODO | |
| M-25 | `mmm_scaler.py` | P2 | Scales lot sizes based on account size / risk params | ✗ | TODO | |
| M-26 | `mmm_adaptive.py` | P2 | Adaptive heartbeat interval — speeds up/slows down loop | `test_sealed_compute_adaptive_interval.py` | TODO | |
| M-27 | `mmm_atm_shield.py` | P2 | ATM protection shield — blocks trades near ATM | `test_sealed_mmm_atm_shield.py` | TODO | |
| M-28 | `mmm_reversal.py` | P2 | Detects and handles trend reversals | `test_sealed_mmm_reversal.py` | TODO | |
| M-29 | `mmm_pending_orders.py` | P2 | Tracks and times out pending (unfilled) orders | `test_sealed_mmm_pending_orders.py` | TODO | |
| M-30 | `mmm_adopter.py` | P2 | Adopts orphaned/existing positions into session | `test_sealed_mmm_adopter.py` | TODO | |
| M-31 | `mmm_trigger.py` | P2 | External triggers — manual actions from UI/API | `test_sealed_mmm_trigger.py` | TODO | |
| M-32 | `mmm_initializer.py` | P2 | Session initialization — creates fresh session state | ✗ | TODO | |
| M-33 | `mmm_straddle_roll.py` | P2 | Rolls straddle positions to new strikes/expiries | ✗ | TODO | |
| M-34 | `mmm_observer.py` | P3 | Observes and logs algo state — read-only monitoring | ✗ | TODO | |
| M-35 | `mmm_activity.py` | P3 | Activity log — records what the algo did and why | ✗ | TODO | |
| M-36 | `mmm_audit_log.py` | P3 | Audit trail — immutable record of all order events | ✗ | TODO | |
| M-37 | `mmm_audit_reconciler.py` | P3 | Reconciles audit log vs exchange fills | ✗ | TODO | |
| M-38 | `mmm_audit_remark.py` | P3 | Attaches human remarks to audit entries | ✗ | TODO | |
| M-39 | `mmm_analytics_storage.py` | P3 | Stores analytics snapshots to disk | ✗ | TODO | |
| M-40 | `mmm_analytics_aggregator.py` | P3 | Aggregates analytics data for UI display | ✗ | TODO | |
| M-41 | `mmm_performance.py` | P3 | Performance metrics — win rate, drawdown, Sharpe | ✗ | TODO | |
| M-42 | `mmm_watchdog.py` | P3 | Watchdog — detects stuck/frozen monitor, auto-restarts | ✗ | TODO | |
| M-43 | `mmm_heartbeat_health.py` | P3 | Tracks heartbeat health — latency, missed beats | ✗ | TODO | |
| M-44 | `mmm_websocket.py` | P3 | WebSocket push to frontend — real-time UI updates | ✗ | TODO | |
| M-45 | `mmm_telegram.py` | P3 | Telegram alerts — sends trade/safety notifications | ✗ | TODO | |
| M-46 | `mmm_api.py` | P3 | REST API routes — UI → backend commands | ✗ | TODO | |
| M-47 | `mmm_config.py` | P3 | Config loader and validator | `test_sealed_mmm_config.py` | TODO | |
| M-48 | `mmm_constants.py` | P3 | All constants — LOT_SIZE_BTC, thresholds, limits | ✗ | TODO | |
| M-49 | `mmm_dte_presets.py` | P3 | DTE-based strike presets | `test_sealed_mmm_dte_presets.py` | TODO | |
| M-50 | `mmm_walkthrough.py` | P3 | Step-by-step walkthrough mode for debugging | ✗ | TODO | |
| M-51 | `mmm_gamma_detector.py` | P2 | *(check: may overlap with M-23 — verify on first read)* | `test_sealed_mmm_gamma_detector.py` | TODO | |

---

## Audit Prompt Template

> Copy this prompt verbatim when starting a module audit session.
> Replace `[MODULE_ID]` and `[FILENAME]` with the actual values.

```
I am auditing the MMM algo module by module for correctness, safety, and robustness.

Today: Audit [MODULE_ID] — [FILENAME]

Please do the following:
1. Read [FILENAME] in full.
2. Read mmm_constants.py for any constants this module uses.
3. Identify which other modules call into this one (search for its function names).
4. Identify which session state keys this module reads and writes.
5. Run through the full audit checklist (sections A through G) from mmm_audit_plan.md.
6. List every bug, hidden issue, broken invariant, or risky pattern you find.
7. For each issue: state the function name, line number, what the bug is, and the fix.
8. Flag any issue that could cause real-money trading loss as CRITICAL.
9. After listing all issues, ask me to confirm before applying any fix.

Do NOT make any code changes until I confirm.
Do NOT restart the backend.
Do NOT audit any other module in this session.

Known invariants to check against (from CLAUDE.md):
- Stale monitor: three-layer guard must remain intact (join 15s / _run_loop primary / G5 heartbeat)
- emit_safety() is sync — never wrap in run_until_complete()
- handle_stale_monitor() must use STOP not pause
- Reverse mode: hard if/else in mmm_monitor.py — normal path unchanged when reverse_enabled=False
- _auto_close_all() close order: reverse → perp → core
- _reverse state never touches session['ce'] or session['pe']
- compute_current_total_pnl() must include reverse_pnl
```

---

## Progress Tracker

| Phase | Modules | Done | Remaining |
|-------|---------|------|-----------|
| P0 — Safety Critical | M-01 to M-08 | 2 | 6 |
| P1 — Order Execution | M-09 to M-17 | 0 | 9 |
| P2 — Logic / P&L | M-18 to M-33 | 0 | 16 |
| P3 — Supporting / Infra | M-34 to M-51 | 0 | 18 |
| **Total** | **51** | **2** | **49** |

---

## Deferred Bug Backlog

> Bugs found during audit sessions that were NOT fixed immediately — either because they require multi-file coordination, are large standalone efforts, or need a dedicated session. Process these before promoting MMM to live.

| ID | From Module | Severity | Bug Description | Blocker For | Owner Session |
|----|-------------|----------|-----------------|-------------|---------------|
| DEF-01 | M-01 `mmm_monitor.py` | P2 | Lot velocity window computation duplicated between `mmm_safety.py` and `mmm_monitor.py`. Two independent rolling-window computations that must stay in sync manually. Fix: extract shared helper into `mmm_safety.py` and call it from both locations. Requires coordinated change across two files. | M-04 audit | Dedicate a session after M-04 audit |
| DEF-02 | M-01 `mmm_monitor.py` | P2 | No sealed tests for `mmm_monitor.py` — the most critical P0 module has zero contract test coverage. `_save_session`, `_heartbeat_inner`, `_auto_close_all`, `_run_loop`, stale-monitor guard layers, and `start_session_monitor` all untested. Fix: write Type 1 + Type 2 sealed tests per AI_SEAL.md. Large effort — dedicated session required. | MMM live promotion | Dedicated seal session after P0 audits complete |
| DEF-03 | M-02 `mmm_engine.py` | P2 | No sealed tests for `calculate_standard_loss`, `calculate_reversal_loss`, `execute_adjustment`, `reconcile_pnl`. Only `calculate_lots_to_sell` sealed (entry #72). 9 non-sealed unit tests exist in `test_mmm_engine.py`. | MMM live promotion | Dedicated seal session after P0 audits complete |

---

## Cross-Module Dependency Map (to be filled as audits complete)

After each audit, add a row here if the module has a noteworthy cross-module dependency:

| Module | Reads From | Writes To | Critical Ordering |
|--------|-----------|-----------|-------------------|
| M-01 `mmm_monitor.py` | `mmm_pnl_core.compute_current_total_pnl` (P&L formula), `mmm_safety.update_peak_pnl` (trailing stop), `mmm_heartbeat_health.MAX_STALE_CONSECUTIVE` (stale threshold), `mmm_storage._save_session` return value | All modules that read session state (saved via `_save_session`) | `_save_session` must return `True`/`False` never `None` — callers use `is False` identity check. `compute_current_total_pnl` must be the ONLY formula for peak P&L tracking — never inline. |
| M-02 `mmm_engine.py` | `mmm_pnl_core.get_pnl()` (sub-totals: `realized`/`unrealized`/`fees`, NOT `net_pnl` for reconciliation), `mmm_pnl_core.compute_unrealized_pnl`, `mmm_pending_orders.register_pending/clear_pending`, `mmm_audit_log.enqueue_trade` | `session['ce'/'pe']` positions/lots, `adjustment_count`, `total_premium_collected`, `adjustment_history`, `_trend_boost_active/_trend_boost_mult` | `reconcile_pnl` must use `pnl['realized'/'unrealized'/'fees']` (options-only), never `pnl['net_pnl']` which includes perp+reverse. `calculate_lots_to_sell` is SEALED — never edit without UNSEAL. |

---

## Known Bad Patterns Checklist

Run these grep searches at the start of ANY session touching execution code:

```bash
# run_until_complete inside already-running loop
grep -rn "run_until_complete" webui/backend/routes/mmm/

# Bare except swallowing errors silently
grep -n "except:" webui/backend/routes/mmm/mmm_monitor.py

# Direct dict mutation without _being_closed guard
grep -n "_being_closed" webui/backend/routes/mmm/mmm_monitor.py

# Orders placed without regime check
grep -n "place_order\|create_order" webui/backend/routes/mmm/ -r

# Async functions called without await
grep -n "process_close_at_5\|_process_adjustment\|_replenish" webui/backend/routes/mmm/mmm_monitor.py
```

---

## Audit Log

*(Add an entry here after each completed audit session)*

| Date | Module | Auditor | Bugs Found | Fixed? | Notes |
|------|--------|---------|-----------|--------|-------|
| 2026-04-04 | M-01 `mmm_monitor.py` | Claude | 8 | 6 fixed, 2 deferred | BUG-1 CRITICAL (stale guard broken). BUG-2 P1 (7× wrong P&L formula). BUG-3 P1 (gather swallows one close). BUG-4/5 P2 (dead code). BUG-6 P2 (hardcoded constant). BUG-7 (velocity refactor deferred). BUG-8 (tests deferred). |
| 2026-04-04 | M-02 `mmm_engine.py` | Claude | 4 | 3 fixed, 1 deferred | BUG-1 P1 (`reconcile_pnl` phantom discrepancies — perp+reverse in actual but not tracked). BUG-2 P2 (no None check in `calculate_reversal_loss`). BUG-3 P3 (commission falsy-unsafe). BUG-4 (sealed tests for 4 core functions deferred). |
