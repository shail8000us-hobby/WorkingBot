# MMM MASTER AUDIT PLAN
### Institutional-Grade System Confidence Review — Pre-Capital-Scaling Edition
**Created:** 2026-04-26
**Status:** PLAN ONLY — No code changes until phases execute
**Working Branch:** SSR

---

## PREAMBLE

The MMM Algo is a live trading system handling real BTC options on Delta Exchange. It has been built incrementally over many sessions, with fixes applied under time pressure, strategies added on top of shared infrastructure, and invariants established post-incident. The system is approximately 90% built but has never undergone a structured, adversarial, institution-grade confidence audit.

This plan defines that audit.

**Primary goal:** Increase confidence in correctness, safety, and scalability before deploying larger capital.

**Secondary goal:** Detect and document structural debt, architecture anti-patterns, and hidden failure modes before they produce live incidents.

---

## 1. EXECUTIVE OBJECTIVE

### What "Confidence" Means Before Scaling Capital

Confidence is not a feeling. It is a measurable state where:

1. **Accounting is provably correct** — every lot placed, every premium collected, every fee paid is tracked without gaps or double-counting.
2. **P&L formulas agree with reality** — the number shown on the dashboard is the number a manual ledger review would produce.
3. **Risk controls are not bypassable** — max loss, lot cap, kill switch, hard stop cannot be silently skipped by any code path.
4. **State survives restarts without corruption** — session restore produces the exact same risk posture as before the restart.
5. **Strategies are isolated** — a bug in one strategy cannot bleed into another through shared module side-effects.
6. **All UI controls have verified backend effect** — no phantom parameters that look active but change nothing.
7. **Edge cases are not unexplored** — expiry chaos, API outage, fast crash, and whipsaw do not produce untracked positions.
8. **Scaling does not break assumptions** — formulas, limits, and API calls hold at 5x and 10x current capital.

**Confidence Score of 80+ (out of 100) is required before next capital increase.**
The score framework is defined in Section 14.

---

## 2. FULL REPO MAPPING PHASE

Before any audit phase executes, a complete map of the system must be verified.

### 2.1 Backend Python Modules (routes/mmm/)

| Category | Files |
|---|---|
| **Orchestrator** | `mmm_monitor.py` |
| **Core Math** | `mmm_engine.py`, `mmm_pnl_core.py`, `mmm_constants.py` |
| **State** | `mmm_state.py`, `mmm_initializer.py`, `mmm_storage.py` |
| **Execution** | `mmm_executor.py`, `mmm_fill_sync.py`, `mmm_pending_orders.py`, `mmm_ledger.py`, `mmm_ws_executions.py` |
| **Risk Controls** | `mmm_safety.py`, `mmm_guardian.py`, `mmm_god_layer.py`, `mmm_circuit_breaker.py`, `mmm_margin_guardian.py`, `mmm_exit_all.py` |
| **Strategy Routing** | `mmm_strategy_dispatch.py`, `mmm_config.py`, `mmm_dte_presets.py` |
| **Strategies** | `mmm_straddle_adjustment.py`, `mmm_straddle_roll_pure.py`, `mmm_reverse.py`, `mmm_reversal.py` |
| **Adjustments** | `mmm_trigger.py`, `mmm_strike_shift.py`, `mmm_replenish.py`, `mmm_close_at_5.py`, `mmm_wind_down.py` |
| **Greeks / Regime** | `mmm_gamma.py`, `mmm_gamma_detector.py`, `mmm_atm_shield.py`, `mmm_regime.py`, `mmm_breakeven_engine.py` |
| **Position Mgmt** | `mmm_harvester.py`, `mmm_recycler.py`, `mmm_scaler.py`, `mmm_perp_hedge.py`, `mmm_adopter.py` |
| **Whipsaw** | `mmm_whipsaw.py`, `mmm_whipsaw_smart.py`, `mmm_whipsaw_replay.py`, `mmm_whipsaw_spot_log.py` |
| **Monitoring** | `mmm_adaptive.py`, `mmm_observer.py`, `mmm_heartbeat_health.py`, `mmm_watchdog.py`, `mmm_performance.py` |
| **Comms** | `mmm_websocket.py`, `mmm_telegram.py`, `mmm_activity.py` |
| **Audit/Analytics** | `mmm_audit_log.py`, `mmm_audit_remark.py`, `mmm_audit_reconciler.py`, `mmm_analytics_aggregator.py`, `mmm_analytics_storage.py` |
| **API** | `mmm_api.py` |
| **Misc** | `mmm_walkthrough.py` |

**Total: ~57 Python modules in routes/mmm/**

### 2.2 Backend Services (MMM-related)

| File | Role |
|---|---|
| `services/_ws_executions_worker.py` | Subprocess worker: exchange execution WS feed |
| `services/_ws_subprocess_worker.py` | Subprocess WS base worker |
| `services/_ws_private_worker.py` | Private WS channel worker |
| `services/delta_private_websocket.py` | Delta Exchange private WS manager |
| `services/delta_price_websocket.py` | Delta Exchange price/orderbook WS |
| `services/notifications.py` | Telegram/alert notification dispatch |
| `services/auto_loop_service.py` | Auto-loop orchestration |

### 2.3 Frontend React Components (components/mmm/)

41 components including: `MMMDashboard`, `MMMContext`, `MMMConfigPanel`, `MMMSettingsDialog`, `MMMSafetyPanel`, `MMMPositionsTable`, `MMMConsolidatedPositions`, `MMMPnLChart`, `MMMBreakevenPanel`, `MMMGammaPanel`, `MMMMarginGuardianPanel`, `MMMPerpHedgePanel`, `MMMReverseModePanel`, `MMMRegimePanel`, `MMMWhipsawCompareTab`, `MMMActivityFeed`, `MMMExecutionLogPanel`, `MMMTradeAuditPanel`, and others.

### 2.4 Tests

| Category | Files |
|---|---|
| **Sealed (regression-locked)** | ~60 files in `tests/test_sealed_*.py` |
| **Integration** | `test_mmm_integration.py`, `test_mmm_lot_lifecycle_integration.py` |
| **Unit** | ~40 additional `test_*.py` files |
| **Frontend sealed** | `__tests__/test_sealed_*.test.js` |
| **Baseline** | 1641 passed as of 2026-04-26 |

### 2.5 Known Shared Infrastructure

- `webui/backend/sealed.py` — sealing decorator
- `webui/backend/routes/mmm/tests/conftest.py` — test fixtures
- Database layer (SQLite or equivalent) accessed via `mmm_storage.py`
- WebSocket broadcast via `mmm_websocket.py` → frontend `MMMContext.js`

---

## 3. AGENT DESIGN SECTION

Twelve specialist agents are defined. Each owns one domain exclusively. They operate independently in Stage A, share findings in Stage B, and are synthesized by the Chief Agent in Stage C.

---

### Agent 1 — Architecture Truth Agent

**Mission:** Map the complete call graph, identify coupling, discover duplicated logic, and expose structural anti-patterns.

**Scope boundaries:** File organization, module dependencies, import chains, ownership of state, God objects, circular imports.

**Inputs:** All Python files in routes/mmm/ and services/. `__init__.py` imports. Function signatures.

**Files to inspect:** Every `.py` in routes/mmm/ (import sections), `mmm_monitor.py` (master orchestrator), `mmm_god_layer.py`, `mmm_strategy_dispatch.py`, `mmm_guardian.py`.

**Outputs:**
- Full module dependency graph (textual)
- List of God objects (modules doing too much)
- Duplicated logic register
- Architecture Issue Register entries

**Report file:** `PHASE_01_ARCHITECTURE_AUDIT.md`

**Escalate to Chief:** Circular imports, modules with 10+ callers, state owned by multiple modules simultaneously, logic that exists in 3+ places.

---

### Agent 2 — Accounting Truth Agent

**Mission:** Prove that every lot placed, every premium received, every fee paid, and every close is tracked without gaps, double-counting, or orphaning.

**Scope boundaries:** Fill ledger, position arrays, lot counters, replenish/recycle loops, adjustment count, close detection.

**Inputs:** `mmm_ledger.py`, `mmm_fill_sync.py`, `mmm_state.py`, `mmm_engine.py`, `mmm_replenish.py`, `mmm_recycler.py`, `mmm_harvester.py`, `mmm_close_at_5.py`, `mmm_exit_all.py`.

**Outputs:**
- Lot lifecycle diagram (open → fill → close → reconcile)
- List of paths where fills may not be recorded
- Orphan-position risk register
- Replenish / recycle consistency check

**Report file:** `PHASE_02_ACCOUNTING_AUDIT.md`

**Escalate to Chief:** Any path where a fill can succeed but not be recorded in session state. Any position that can be on the exchange but not in `session['ce']['positions']` or `session['pe']['positions']`.

---

### Agent 3 — P&L Truth Agent

**Mission:** Verify that every formula in the P&L system produces numbers that agree with a manual ledger trace.

**Scope boundaries:** `mmm_pnl_core.py`, realized/unrealized split, fees, net premium, max loss calculation, session total, reverse P&L contamination.

**Inputs:** `mmm_pnl_core.py`, `mmm_engine.py`, `mmm_monitor.py` (P&L update paths), `mmm_websocket.py` (emit fields), `mmm_api.py` (overlay functions), `MMMContext.js` (frontend mapping), `mmm_storage.py` (persistence).

**Outputs:**
- Formula verification table (formula → manual trace → match/mismatch)
- Fee calculation verification
- Net vs gross premium distinction check
- Reverse P&L isolation check
- Frontend display accuracy check

**Report file:** `PHASE_03_PNL_AUDIT.md`

**Escalate to Chief:** Any formula where live display diverges from database truth. Any path where realized P&L is not updated after a close. Net premium gross/net confusion.

---

### Agent 4 — Risk Control Agent

**Mission:** Verify that every risk control (max loss, lot cap, kill switch, hard stop, margin guardian, generation guard) cannot be bypassed by any code path under any condition.

**Scope boundaries:** `mmm_safety.py`, `mmm_guardian.py`, `mmm_god_layer.py`, `mmm_circuit_breaker.py`, `mmm_margin_guardian.py`, `mmm_exit_all.py`, hard stop logic in `mmm_monitor.py`.

**Inputs:** All files above plus `mmm_monitor.py` (hard stop check locations), `mmm_strategy_dispatch.py` (strategy-specific bypasses).

**Outputs:**
- Risk control bypass matrix (control × strategy × bypass risk)
- Stale monitor guard verification (all 3 layers)
- Kill switch endpoint test trace
- Hard stop trigger-to-action trace
- Margin guardian async race condition check

**Report file:** `PHASE_04_RISK_CONTROLS_AUDIT.md`

**Escalate to Chief:** Any code path where max loss check is skipped. Any scenario where kill switch does not halt execution. Any generation guard that can be bypassed.

---

### Agent 5 — Strategy Logic Agent

**Mission:** Audit each strategy's core logic, decision trees, assumptions, and edge cases in isolation.

**Scope boundaries:** The four strategies (0DTE Strangle, 5DTE Strangle, Straddle With Adjustment, Pure Straddle Roll) plus Reverse Mode overlay. Strategy dispatch routing correctness.

**Inputs:**
- `mmm_strategy_dispatch.py`
- `mmm_straddle_adjustment.py`
- `mmm_straddle_roll_pure.py`
- `mmm_reverse.py`
- `mmm_monitor.py` (strategy-specific branches)
- `mmm_config.py` (per-strategy params)
- `mmm_dte_presets.py`

**Outputs:**
- Per-strategy decision tree verification
- Strategy isolation matrix (does Strategy A ever touch Strategy B state?)
- Edge case register per strategy
- Reverse mode isolation proof

**Report file:** `PHASE_05_STRATEGY_LOGIC_AUDIT.md`

**Escalate to Chief:** Any shared module that behaves differently based on strategy type via inline if/else (should use dispatch flags). Any reverse mode state leaking into core session fields.

---

### Agent 6 — Mathematical Model Agent

**Mission:** Verify every quantitative formula in the system is correct, consistent, and does not accumulate errors at scale.

**Scope boundaries:** Lot sizing, premium triggers, breakeven math, adjustment thresholds, gamma calculations, decay logic, expiry math, margin estimates, Decimal precision.

**Inputs:**
- `mmm_engine.py` (adjustment formula, loss-to-cover, lot calculation)
- `mmm_pnl_core.py` (P&L formulas)
- `mmm_constants.py` (LOT_SIZE_BTC)
- `mmm_breakeven_engine.py`
- `mmm_gamma.py`, `mmm_gamma_detector.py`
- `mmm_trigger.py` (threshold math)
- `mmm_scaler.py`
- `mmm_margin_guardian.py` (margin estimate formulas)

**Outputs:**
- Formula derivation table with manual checks
- Decimal vs float usage consistency check
- Rounding edge case register
- Gamma formula correctness check
- Lot size precision chain (1 lot = 0.001 BTC = $X at price Y)
- Premium trigger threshold sensitivity analysis

**Report file:** `PHASE_06_MATH_MODEL_AUDIT.md`

**Escalate to Chief:** Any formula using raw `float` for money arithmetic (not Decimal). Any threshold that fires too early or too late at 5x capital. Any formula that diverges from the referenced `MONEY_POWER_CALCULATION_LOGIC.md` document.

---

### Agent 7 — State & Recovery Agent

**Mission:** Verify that session state is consistent, survives restarts, and cannot corrupt after unexpected shutdowns.

**Scope boundaries:** Session dict structure, DB persistence, session restore path, watchdog restart, generation counter, stale state fields, `_reverse` isolation.

**Inputs:**
- `mmm_storage.py`
- `mmm_initializer.py`
- `mmm_watchdog.py`
- `mmm_guardian.py`
- `mmm_monitor.py` (restore path)
- `mmm_state.py`
- `mmm_reverse.py` (`initialize_reverse_state`)

**Outputs:**
- Session field inventory (all keys, types, initialization paths)
- Restore correctness checklist
- Generation counter integrity proof
- `_reverse` state isolation verification
- Missing-key vulnerability register (fields that silently default to wrong values)

**Report file:** `PHASE_07_STATE_RECOVERY_AUDIT.md`

**Escalate to Chief:** Any session field that can have wrong default on restore. Any path where `initialize_reverse_state` is not called on old sessions. Generation counter roll-over scenarios.

---

### Agent 8 — Execution & API Agent

**Mission:** Verify the order execution layer is correct, idempotent, handles partial fills, race conditions, and API outages without producing duplicate or orphan orders.

**Scope boundaries:** `mmm_executor.py`, `mmm_fill_sync.py`, `mmm_ws_executions.py`, `mmm_pending_orders.py`, `mmm_ledger.py`, exchange API calls.

**Inputs:** All files above plus `mmm_monitor.py` (execution call sites), `mmm_engine.py` (execute call), `mmm_replenish.py`, `mmm_close_at_5.py`.

**Outputs:**
- Execution flow diagram (order placed → fill confirmed → state updated)
- Duplicate order risk register
- Partial fill handling verification
- Race condition map (concurrent heartbeat vs fill sync)
- Retry logic audit
- Stale quote detection check

**Report file:** `PHASE_08_EXECUTION_AUDIT.md`

**Escalate to Chief:** Any path where an order can be placed twice for the same trigger. Any fill that can succeed without updating session lots. API timeout behavior during position-close.

---

### Agent 9 — WebUI / Parameter Truth Agent

**Mission:** Verify that every UI control in `MMMConfigPanel`, `MMMSettingsDialog`, `MMMSafetyPanel`, and other panels actually changes runtime behavior — no phantom parameters.

**Scope boundaries:** Frontend param → API endpoint → backend config → monitor runtime behavior chain for every configurable field.

**Inputs:**
- `MMMConfigPanel.js`, `MMMSettingsDialog.js`, `MMMSafetyPanel.js`, `MMMReverseModePanel.js`
- `mmm_api.py` (param update endpoints)
- `mmm_config.py` (param storage and hot-reload)
- `mmm_monitor.py` (param consumption sites)
- `MMMContext.js` (state propagation)
- `mmmService.js` (API calls)

**Outputs:**
- Parameter truth table (UI field → API field → config key → runtime variable → effect)
- Phantom parameter list (UI fields that save but do nothing)
- Hot-reload verification (param change takes effect without restart)
- Frontend display accuracy for live values

**Report file:** `PHASE_09_WEBUI_PARAM_AUDIT.md`

**Escalate to Chief:** Any UI parameter that is stored but never read at runtime. Any param change that requires a restart to take effect when hot-reload is claimed. Frontend showing stale values for live session fields.

---

### Agent 10 — Replay & Stress Test Agent

**Mission:** Design and document stress test scenarios that expose failure modes not visible in normal operation.

**Scope boundaries:** Scenario design, not execution (execution is a separate task). Identifies which code paths are triggered by each scenario.

**Scenarios:**
1. Trend day — spot moves 8% in 4 hours, one side keeps accumulating
2. Whipsaw day — spot crosses trigger 15 times in 2 hours
3. Fast crash — -20% in 30 minutes
4. API outage — exchange returns 503 for 10 minutes
5. Expiry chaos — DTE=0, both sides ITM, close_at_5 and exit_all race
6. Restart mid-adjustment — backend restarts while executor is placing an order
7. Margin breach — account equity drops below maintenance margin
8. Dual monitor ghost — watchdog restarts monitor while old one is still active
9. Pure straddle roll at expiry — roll trigger fires at same time as auto-close
10. Reverse mode activation during live adjustment

**Outputs:**
- Scenario × failure mode matrix
- Code paths activated per scenario
- Missing safeguard register per scenario

**Report file:** `PHASE_10_REPLAY_STRESS_AUDIT.md`

**Escalate to Chief:** Any scenario that produces untracked positions or incorrect P&L. Any scenario where two competing processes modify session state without a lock.

---

### Agent 11 — Scaling Readiness Agent

**Mission:** Identify what breaks, slows down, or produces incorrect results when capital is 5x or 10x current deployment.

**Scope boundaries:** Lot caps, API rate limits, DB query performance, WebSocket message volume, margin formula accuracy at scale, Telegram flood, memory growth.

**Inputs:** `mmm_constants.py`, `mmm_engine.py` (lot calc), `mmm_margin_guardian.py`, `mmm_storage.py` (query patterns), `mmm_websocket.py` (broadcast frequency), `mmm_telegram.py` (notification volume), `mmm_scaler.py`.

**Outputs:**
- Scaling risk register (assumption × current capital × 5x capital × 10x capital)
- API rate limit headroom analysis
- DB performance at session scale
- Hardcoded limits register

**Report file:** `PHASE_11_SCALING_AUDIT.md`

**Escalate to Chief:** Any hardcoded limit that blocks scaling. Any formula that becomes inaccurate at large lot counts. Any API call pattern that would hit rate limits at 3x volume.

---

### Agent 12 — Chief / God Agent (Final Integrator)

**Mission:** Read all 11 specialist reports, merge findings, eliminate duplicates, expose shared root causes, rank severity, and produce the final verdict.

**Inputs:** `PHASE_01` through `PHASE_11` audit reports (all of them — in full).

**Process:**
1. Collect all findings tagged P0/P1/P2/P3
2. Group duplicate symptoms pointing to same root cause
3. Identify architecture patterns that generate multiple bugs
4. Cross-check: does Phase 4 risk finding match Phase 8 execution finding?
5. Resolve contradictions between agents (document where agents disagree)
6. Produce ranked top-20 issues
7. Assign permanent fix priority vs patch priority
8. Score confidence (0–100) using Section 14 framework
9. Define safe capital scaling gating criteria

**Output file:** `MASTER_AUDIT_VERDICT.md`

---

## 4. AUDIT PHASES — SEQUENTIAL

Each phase must be completed before the next begins. Each phase reads all previous phase reports.

---

### Phase 1 — Architecture Truth Audit

**Objective:** Understand the complete structure, identify God objects, map module ownership, detect duplicated logic and dangerous coupling.

**Lead Agent:** Architecture Truth Agent (Agent 1)
**Supporting Agents:** Strategy Logic Agent (cross-check dispatch), State Agent (cross-check state ownership)

**Files to Read:**
- All `__init__.py` and top-level imports in `routes/mmm/`
- `mmm_monitor.py` (full file — primary orchestrator)
- `mmm_god_layer.py`
- `mmm_strategy_dispatch.py`
- `mmm_guardian.py`
- `mmm_watchdog.py`
- `mmm_config.py`

**Functions to Inspect:**
- `start_session_monitor()` — who calls it, what state it touches
- `_run_loop()` — full loop body, all side-effect call sites
- `_heartbeat()` — all subsystems invoked
- `strategy_dispatch()` — routing table, fall-through risk
- Every function in `mmm_god_layer.py`

**What to Verify:**
- Does a single module own session state, or is it shared across 3+?
- Are there modules that import each other (circular dependency)?
- Is `mmm_monitor.py` a true God object (1000+ lines handling everything)?
- Are strategy-specific behaviors cleanly separated or mixed into shared modules via inline `if strategy_type == X`?
- Is there a consistent pattern for async vs sync boundary management?

**Hidden Bugs to Search For:**
- Circular import that only triggers under certain execution orders
- Module-level singleton state that is shared across sessions
- Strategy type checked inline in 5+ shared modules (coupling)
- `mmm_monitor.py` calling functions from 40+ modules with no clear abstraction layer
- Watchdog and monitor both modifying the same session dict key simultaneously

**Architecture Issues to Search For:**
- `mmm_monitor.py` too large — single orchestrator doing session management, risk checks, execution, P&L, WebSocket emit, Telegram, strategy dispatch
- Strategy-specific logic in shared modules instead of strategy modules
- No clear ownership boundary between "session persistence" and "session runtime state"
- Mix of async/sync calls creating asyncio boundary violations
- `mmm_god_layer.py` duplicating logic from `mmm_guardian.py` and `mmm_safety.py`

**Output Report File:** `PHASE_01_ARCHITECTURE_AUDIT.md`

**Severity Levels:**
P0 = circular import that breaks live system | P1 = shared state without locking | P2 = duplication risk | P3 = cosmetic coupling

**Pass Criteria:** Complete module dependency graph produced. All God objects identified. Architecture Issue Register started with at least the structural issues known from prior incidents.

---

### Phase 2 — Accounting Truth Audit

**Objective:** Prove that every lot, every premium, and every fill is tracked end-to-end without gaps, duplicates, or silent losses.

**Lead Agent:** Accounting Truth Agent (Agent 2)
**Supporting Agents:** Execution Agent (fill path), P&L Agent (premium accounting)

**Files to Read:**
- `mmm_ledger.py` (fill ledger structure)
- `mmm_fill_sync.py` (exchange fill → session update)
- `mmm_state.py` (`recompute_side_lots`, position arrays)
- `mmm_engine.py` (post-adjustment state update)
- `mmm_replenish.py`
- `mmm_recycler.py`
- `mmm_harvester.py`
- `mmm_close_at_5.py`
- `mmm_exit_all.py`
- `mmm_adopter.py`

**Functions to Inspect:**
- `recompute_side_lots()` — is this the single source of truth for lot counts?
- Fill recording path: exchange fill → `mmm_ledger` → session state update
- `mmm_replenish.py` replenish trigger conditions and lot delta calculation
- `mmm_recycler.py` close-and-reopen accounting
- `mmm_harvester.py` profit harvest — does it correctly reduce `active_lots`?
- `mmm_close_at_5.py` — when it closes, does it reconcile position array immediately?
- Position adoption path in `mmm_adopter.py`

**What to Verify:**
- Is `recompute_side_lots()` called after every state-changing operation?
- Can a fill succeed (exchange confirms) but session lot count not update?
- Is the fill ledger append-only or can it be rewritten?
- Are adopted positions correctly bootstrapped into the same accounting structures as positions opened by the bot?
- Does recycler correctly account for buy-back cost before opening new position?
- Is adjustment count updated atomically with lot count?

**Hidden Bugs to Search For:**
- Close operation succeeds, premium collected decreases, but `active_lots` not decremented
- Replenish opens new lots before confirming previous close fill
- Harvester removes lots from session but does not record the close in the ledger
- Race: `fill_sync` updates lots at same time as `_heartbeat` reads them — torn read
- Adopter creates positions with incomplete field set (missing `entry_premium` etc.)
- Two adjustments in the same heartbeat cycle — second adjustment calculates on stale lot count

**Architecture Issues to Search For:**
- No single authoritative lot count — `active_lots`, `adjustment_count`, `len(positions)` may drift
- Fill ledger is a separate structure from position array — reconciliation is manual and error-prone
- Multiple modules modify `session['ce']['positions']` directly without going through a central state manager
- Replenish, recycler, harvester all have independent "should I act?" logic with no coordination

**Output Report File:** `PHASE_02_ACCOUNTING_AUDIT.md`

**Pass Criteria:** Complete lot lifecycle diagram produced. Every code path that modifies lot count identified. At least 3 potential orphan scenarios investigated.

---

### Phase 3 — P&L Truth Audit

**Objective:** Verify that every P&L number shown on the dashboard and stored in the database is the correct number a manual ledger review would produce.

**Lead Agent:** P&L Truth Agent (Agent 3)
**Supporting Agents:** Accounting Agent (fill basis), WebUI Agent (display accuracy)

**Files to Read:**
- `mmm_pnl_core.py` (all formulas)
- `mmm_engine.py` (realized P&L update logic)
- `mmm_monitor.py` (heartbeat P&L update, emit_pnl_update call)
- `mmm_websocket.py` (emit fields)
- `mmm_api.py` (`_overlay_live_pnl`, `list_session_summaries`)
- `mmm_storage.py` (how P&L is persisted)
- `MMMContext.js` (`handlePnlUpdate` mapping)
- `mmm_reverse.py` (`net_pnl` calculation)

**Functions to Inspect:**
- `compute_current_total_pnl()` — formula, reverse P&L inclusion
- `compute_net_premium()` — gross vs net distinction, ledger dependency
- `emit_pnl_update()` — which fields emitted, which fields received by frontend
- `_overlay_live_pnl()` — stopped session path vs live session path
- `list_session_summaries()` — does it load enough state to compute accurate P&L?
- Hard stop max loss check — exact formula, exact comparison

**What to Verify:**
- Does `total_pnl = realized + unrealized` always hold?
- Is fee computation correct: `fee = lots × LOT_SIZE_BTC × price × taker_rate`?
- Does net premium correctly subtract buyback costs from gross collected?
- Does `compute_current_total_pnl()` include reverse P&L in all paths?
- Is there a path where `_net_premium_collected` is stale at session end?
- Does the dashboard P&L match the database P&L for stopped sessions?

**Hidden Bugs to Search For:**
- Gross premium shown when net premium is the correct metric (fixed in rev9 — verify fully closed)
- Unrealized P&L calculated from stale mark prices (WebSocket disconnection scenario)
- Fee double-counted for adjustments that are later cancelled
- Session P&L reset to 0 on monitor restart (generation guard blocks saves but P&L in memory continues)
- Reverse mode `net_pnl` included in total correctly but also counted in `realized_pnl` (double-count)
- Hard stop triggers at -$X but actual loss is -$X - fees (fees not included in comparison)

**Architecture Issues to Search For:**
- P&L split across `pnl_core.py`, `engine.py`, `monitor.py`, and `api.py` with no single canonical formula location
- Live path and stopped-session path use different formulas (divergence risk)
- Frontend mapping of WebSocket P&L fields maintained manually — drift risk over time
- `compute_net_premium()` depends on fill ledger being fully loaded — fragile for large sessions

**Output Report File:** `PHASE_03_PNL_AUDIT.md`

**Pass Criteria:** Complete formula verification table produced. Live P&L and DB P&L shown to agree (or discrepancy documented). Gross/net premium distinction confirmed in all display paths.

---

### Phase 4 — Risk Controls Audit

**Objective:** Prove that every risk control is unbypassable under all code paths and all strategy types.

**Lead Agent:** Risk Control Agent (Agent 4)
**Supporting Agents:** Execution Agent (order placement path), Architecture Agent (God layer ownership)

**Files to Read:**
- `mmm_safety.py`
- `mmm_guardian.py`
- `mmm_god_layer.py`
- `mmm_circuit_breaker.py`
- `mmm_margin_guardian.py`
- `mmm_exit_all.py`
- `mmm_monitor.py` (max loss check, hard stop path, stale monitor guards)
- `mmm_strategy_dispatch.py` (strategy-specific bypasses)

**Functions to Inspect:**
- Max loss check location in `_run_loop()` — is it before or after execution?
- `handle_stale_monitor()` — STOP not PAUSE verification
- `emit_safety()` — sync vs async verification (must not use `run_until_complete`)
- Kill switch endpoint → `mmm_safety.py` → monitor halt chain
- Hard stop trigger → `mmm_exit_all.py` invocation chain
- Circuit breaker trip conditions and reset conditions
- Margin guardian async pattern (race condition risk)
- Generation guard G5 in `_heartbeat()` — innermost fallback check

**What to Verify:**
- Three-layer stale monitor fix is intact:
  1. `start_session_monitor()` `thread.join(15s)`
  2. `_run_loop` primary generation guard
  3. `_heartbeat()` G5 guardian check
- Kill switch sets `_running = False` (STOP) not just a pause flag
- Max loss check runs on every heartbeat cycle, not conditionally
- Margin guardian cannot be bypassed by strategy type
- Circuit breaker trip correctly halts execution (not just logs)
- Hard stop fires Telegram notification before halting

**Hidden Bugs to Search For:**
- Max loss check runs AFTER execution in one strategy path but BEFORE in another
- Generation guard disabled for a specific strategy (someone added an exception)
- Kill switch API endpoint sets flag but monitor reads a cached copy
- Circuit breaker resets too quickly (trip → reset within one heartbeat cycle)
- Margin guardian runs async but session write happens sync — tear possible
- `_stale_abort_gen` flag set but monitor loop continues for one more iteration

**Architecture Issues to Search For:**
- Risk controls spread across 6+ modules with no single risk gate function
- Some risk checks run inside strategy dispatch (hidden from shared audit path)
- Circuit breaker and max loss check are independent — no combined "all risk gates" function
- Hard stop and kill switch have different code paths (inconsistent halt behavior)
- Margin guardian can be disabled via config — no enforcement that it cannot be disabled at scale

**Output Report File:** `PHASE_04_RISK_CONTROLS_AUDIT.md`

**Pass Criteria:** Three-layer stale monitor fix verified in code. Risk bypass matrix produced for all six controls × all four strategies. No P0 bypass path found, or if found: documented and escalated immediately.

---

### Phase 5 — Strategy Logic Audit

**Objective:** Verify each strategy's logic is correct, complete, isolated, and handles its edge cases without leaking into other strategies.

**Lead Agent:** Strategy Logic Agent (Agent 5)
**Supporting Agents:** Math Agent (formulas), Architecture Agent (isolation)

**Reads Phase 1 + Phase 2 findings first.**

**Files to Read:**
- `mmm_strategy_dispatch.py`
- `mmm_straddle_adjustment.py`
- `mmm_straddle_roll_pure.py`
- `mmm_reverse.py`
- `mmm_reversal.py`
- `mmm_config.py`
- `mmm_dte_presets.py`
- `mmm_monitor.py` (strategy-specific branches ~line 2781 reverse hard if/else)
- `mmm_watchdog.py` (strategy-aware restart)
- `mmm_close_at_5.py` (strategy-aware close logic)

**Strategies to Audit Individually:**

**Strategy A: Short Strangle 0DTE**
- Entry logic, adjustment trigger threshold, close-at-5 behavior, DTE expiry handling
- Does it share any state with 5DTE strangle during same session?

**Strategy B: Short Strangle 5DTE**
- DTE counting correctness, roll logic, multi-day session persistence
- What happens when backend restarts mid-DTE?

**Strategy C: Short Straddle With Adjustment**
- Equal strikes entry invariant (at start only — not after adjustment)
- ATM gamma bypass rule (gamma must never block adjustment/shift)
- Strike shift after adjustment creates strangle — validation must allow this
- Adjustment reversal logic

**Strategy D: Pure Straddle Roll**
- Equal strikes invariant (must hold throughout — unlike Strategy C)
- Roll trigger vs adjustment trigger distinction
- Roll timing at DTE threshold

**Reverse Mode Overlay (all strategies):**
- `reverse_enabled=False` → 100% unchanged normal path
- `reverse_enabled=True, active=True` → hard if/else, no fallthrough
- `_reverse` state never contaminating `session['ce']` or `session['pe']`
- `initialize_reverse_state()` called on all session loads

**What to Verify:**
- Each strategy has a unique identity that is preserved through watchdog restarts
- `mmm_strategy_dispatch.py` routes to correct handler for each strategy
- No shared module makes a decision based on strategy type via inline if/else
- `_validate_straddle_with_adjustment_session` no longer calls `_validate_true_straddle_shape()` (fixed rev7)
- Watchdog restarts now use `context='monitor_restore'` (fixed rev7)

**Hidden Bugs to Search For:**
- 0DTE and 5DTE strategies diverge in behavior only via DTE preset — shared code paths may behave wrong for one
- Straddle adjustment triggers adjustment when in gamma protection mode (bypass rule not applied)
- Pure straddle roll allows unequal strikes to persist (invariant broken silently)
- Reverse mode `active=True` but `reverse_enabled=False` — which branch wins?
- Strategy type identity not preserved through `mmm_storage.py` serialize/deserialize round-trip

**Architecture Issues to Search For:**
- Strategy-specific behavior implemented via `if strategy_type == X` in `mmm_monitor.py` (should be dispatch)
- `mmm_straddle_adjustment.py` and `mmm_straddle_roll_pure.py` likely duplicate each other for 80% of the logic
- No strategy interface/contract definition — any module can claim to be a strategy handler
- Reverse mode is the only strategy with explicit isolation guarantees — others have none documented

**Output Report File:** `PHASE_05_STRATEGY_LOGIC_AUDIT.md`

**Pass Criteria:** Per-strategy decision tree produced. Reverse mode isolation verified. Strategy identity round-trip proven. ATM gamma bypass rule verified for STRADDLE_WITH_ADJUSTMENT.

---

### Phase 6 — Mathematical Model Audit

**Objective:** Verify every quantitative formula is mathematically correct, consistent across modules, and does not produce wrong results at edge values.

**Lead Agent:** Mathematical Model Agent (Agent 6)
**Supporting Agents:** P&L Agent (formula cross-check), Accounting Agent (lot size chain)

**Reads Phase 3 + Phase 5 findings first.**

**Files to Read:**
- `mmm_engine.py` (adjustment formula — Case A and Case B)
- `mmm_pnl_core.py` (all P&L formulas)
- `mmm_constants.py` (LOT_SIZE_BTC)
- `mmm_breakeven_engine.py`
- `mmm_gamma.py`
- `mmm_gamma_detector.py`
- `mmm_trigger.py` (threshold calculations)
- `mmm_scaler.py`
- `mmm_margin_guardian.py` (margin estimate formulas)
- `MONEY_POWER_CALCULATION_LOGIC.md` (reference document — if accessible)

**Functions to Inspect:**
- `calculate_lots_to_sell()` — loss-to-cover / premium-per-lot formula
- `compute_current_total_pnl()` — realized + unrealized + reverse
- Breakeven band width formula
- Gamma proportional scaling formula
- Trigger threshold formula (distance from strike as % of premium)
- Margin estimate formula (how many $ of margin per lot)
- Scaler lot multiplication logic

**What to Verify:**
- `LOT_SIZE_BTC = 0.001` — is this used consistently everywhere or are some paths using 0.1 or 1.0 by mistake?
- Decimal arithmetic used for all money calculations (no raw float accumulation)
- Case A (standard) and Case B (reversal) adjustment formulas are mathematically consistent
- Breakeven band formula accounts for both CE and PE premiums correctly
- Gamma formula uses correct options theory (delta-adjusted lot count)
- `calculate_lots_to_sell` result always rounded correctly (ceiling vs floor vs round — which is correct for covering loss?)
- Trigger threshold: does 1% move at $50,000 BTC mean same risk as 1% move at $100,000 BTC?

**Hidden Bugs to Search For:**
- LOT_SIZE_BTC used as 0.001 in one module but accessed as raw float in another (float imprecision)
- Breakeven formula uses mid-price when it should use ask (underestimates close cost)
- Gamma scaling multiplies lots by gamma value — if gamma > 1.0, can produce over-sized orders
- Margin estimate too conservative (over-blocking) or too loose (under-protecting)
- Premium trigger threshold not adjusted for volatility regime (flat threshold in high-vol = too early / low-vol = too late)
- `calculate_lots_to_sell` returns 0 when loss is very small — monitor skips adjustment but accumulates loss

**Architecture Issues to Search For:**
- `_D()` helper defined independently in `mmm_engine.py` AND `mmm_constants.py` (duplication)
- Formulas referenced in `MONEY_POWER_CALCULATION_LOGIC.md` but implemented differently in code (drift)
- No formula registry or documentation inside the codebase — only in external doc
- Mathematical constants hardcoded in calling code rather than in `mmm_constants.py`

**Output Report File:** `PHASE_06_MATH_MODEL_AUDIT.md`

**Pass Criteria:** LOT_SIZE_BTC consistency verified across all modules. Decimal arithmetic confirmed for all money operations. Case A / Case B formulas verified against reference doc.

---

### Phase 7 — State & Session Audit

**Objective:** Verify session state is complete, correct on restore, free from stale fields, and immune to corruption across restart cycles.

**Lead Agent:** State & Recovery Agent (Agent 7)
**Supporting Agents:** Accounting Agent (lot state), Risk Agent (generation guard state)

**Reads Phase 1 + Phase 2 findings first.**

**Files to Read:**
- `mmm_storage.py` (full — serialize/deserialize, query patterns)
- `mmm_initializer.py`
- `mmm_watchdog.py`
- `mmm_guardian.py`
- `mmm_monitor.py` (session load and restore path)
- `mmm_state.py`
- `mmm_reverse.py` (`initialize_reverse_state`)

**Functions to Inspect:**
- `save_session()` / `load_session()` round-trip — field preservation
- `start_session_monitor()` — session context passed to new monitor instance
- `initialize_reverse_state()` — default values, called on all load paths?
- `_save_my_session()` — return value check for blocked save
- `recompute_side_lots()` — idempotent? Can it be called twice without doubling counts?
- Watchdog session reload — does it reload from DB or use in-memory version?

**What to Verify:**
- Every field in the session dict has a known type, default value, and initialization path
- `_reverse` key is always present after load (no KeyError on old sessions)
- Generation counter increments correctly and is persisted to DB
- `_stale_abort_gen` flag is ephemeral (not persisted) — correct?
- Watchdog restart: new monitor generation = old generation + 1
- All strategy-specific fields are initialized by the correct strategy's init path

**Hidden Bugs to Search For:**
- Old session loaded without `initialize_reverse_state()` — `_reverse` KeyError in live code
- Generation counter read from DB but written to memory — divergence after crash
- Session dict mutated in-place by multiple concurrent coroutines (no copy/lock)
- `recompute_side_lots()` called on stale position array after partially-applied update
- Stopped session loaded for analytics — missing `_fill_ledger` causes incomplete P&L (known: rev9)
- Session fields added in recent sessions not backward-compatible with old format

**Architecture Issues to Search For:**
- Session is a raw dict — no schema validation, no migration system
- No versioning on the session dict format — old sessions may silently fail to load fields
- `mmm_storage.py` mixes session CRUD with analytics queries (two separate concerns)
- State recovery is a manual "hope all defaults are right" pattern, not a validated restore contract

**Output Report File:** `PHASE_07_STATE_RECOVERY_AUDIT.md`

**Pass Criteria:** Complete session field inventory produced. All fields shown to have correct defaults on restore. `initialize_reverse_state` call verified in all load paths.

---

### Phase 8 — Execution Layer Audit

**Objective:** Verify the order execution layer is correct, idempotent, handles all failure modes, and cannot produce duplicate or phantom orders.

**Lead Agent:** Execution & API Agent (Agent 8)
**Supporting Agents:** Accounting Agent (fill recording), State Agent (execution state in session)

**Reads Phase 2 + Phase 7 findings first.**

**Files to Read:**
- `mmm_executor.py` (full)
- `mmm_fill_sync.py` (full)
- `mmm_ws_executions.py`
- `mmm_pending_orders.py`
- `mmm_ledger.py`
- `services/_ws_executions_worker.py`
- `services/delta_private_websocket.py`

**Functions to Inspect:**
- Order placement function — idempotency check (client_order_id generation)
- Fill confirmation path — WS feed → `fill_sync` → session state
- Pending order tracking — how long before a pending order is considered timed out?
- Retry logic — on API error, does it retry once or infinitely?
- Duplicate order prevention — how is it guaranteed that the same trigger does not place two orders?
- Partial fill handling — if 50/100 lots fill, what happens to the other 50?

**What to Verify:**
- `client_order_id` is unique per trigger (not per session or per bot)
- A fill received via WS is not also processed via REST poll (double-accounting risk)
- A cancelled order that partially filled is correctly accounted (the filled portion)
- If WS disconnects during order placement, the fill is recovered on reconnect
- `BLOCK_ALL_SELLS` correctly blocks replenish but does not affect close operations
- Execution during `close_at_5` and independent close do not race (P1 incident 2026-04-02)

**Hidden Bugs to Search For:**
- `client_order_id` reused when bot restarts — exchange may reject as duplicate or accept as new
- WS fill event arrives before REST order confirmation — state updated twice
- Partial fill state left in pending orders indefinitely (memory leak)
- Retry on timeout places second order before cancelling first
- `BLOCK_ALL_SELLS` check missing in one replenish code path (the P1 incident path)
- Execution WS and fill sync both updating `active_lots` without a lock

**Architecture Issues to Search For:**
- Two systems for tracking fills (WS events + REST polling) with no clear primary/secondary designation
- `mmm_pending_orders.py` maintains its own order state separate from `mmm_ledger.py` — two sources of truth
- No dead-letter queue for failed fills — if recording fails, fill is lost silently
- Exchange error codes not systematically mapped to bot behavior (each module handles errors ad hoc)

**Output Report File:** `PHASE_08_EXECUTION_AUDIT.md`

**Pass Criteria:** Full execution flow diagram produced. Duplicate order prevention mechanism verified. P1 incident (2026-04-02) remediation confirmed in code.

---

### Phase 9 — WebUI / Parameter Truth Audit

**Objective:** Verify every UI control changes runtime behavior — no phantom parameters, no stale displays, no hot-reload gaps.

**Lead Agent:** WebUI / Parameter Truth Agent (Agent 9)
**Supporting Agents:** Architecture Agent (API wiring), Strategy Agent (per-strategy param scope)

**Reads Phase 5 + Phase 7 findings first.**

**Files to Read:**
- `MMMConfigPanel.js`
- `MMMSettingsDialog.js`
- `MMMSafetyPanel.js`
- `MMMReverseModePanel.js`
- `MMMContext.js`
- `mmmService.js`
- `mmm_api.py` (all PATCH/POST param endpoints)
- `mmm_config.py`
- `mmm_monitor.py` (param consumption — where params are read from session)

**What to Verify:**
- Every slider/input in the UI has a corresponding API endpoint
- Every API endpoint stores to the correct session key
- Every session key is read by the monitor at runtime (not just stored)
- Hot-reload: param changes take effect within the next heartbeat cycle
- Frontend displays live WebSocket values (not just last REST load)
- Null-guard before `.toFixed()` for all financial display values
- `!= null` checks used (not `|| 0`) for financial values per feedback rule

**Hidden Bugs to Search For:**
- Config param saved to `session['params']` but monitor reads from `session['config']` (key mismatch)
- DTE preset applies to UI only — underlying session DTE not actually changed
- Reverse mode toggle saves to params but does not `initialize_reverse_state()` when first enabled
- Max loss UI slider has different scale than backend constant (e.g., UI shows $500, backend stores 500.0 as 0.5)
- Breakeven threshold param exists in UI but is never read in `mmm_breakeven_engine.py`
- Gamma bypass for STRADDLE_WITH_ADJUSTMENT not reflected in any UI status indicator

**Architecture Issues to Search For:**
- Frontend uses hardcoded field names that drift from backend field names over time
- No contract between frontend and backend for WebSocket message schema
- `MMMContext.js` mixes API calls, WS subscriptions, and local state in one large context — hard to audit
- Configuration has multiple storage locations (session dict, config file, UI state) that can disagree

**Output Report File:** `PHASE_09_WEBUI_PARAM_AUDIT.md`

**Pass Criteria:** Parameter truth table produced for top 20 most critical params. At least 3 phantom parameter candidates investigated. Hot-reload behavior verified for kill switch and max loss params.

---

### Phase 10 — Replay & Stress Test Audit

**Objective:** Document the code paths activated by each stress scenario and identify missing safeguards.

**Lead Agent:** Replay & Stress Test Agent (Agent 10)
**Supporting Agents:** Risk Agent (safeguard gaps), Execution Agent (API failure paths)

**Reads all previous phase findings first.**

**Scenarios and Target Code Paths:**

| Scenario | Primary Files Activated |
|---|---|
| Trend day (+8% in 4h) | `mmm_trigger.py`, `mmm_engine.py`, `mmm_scaler.py`, `mmm_safety.py` (lot cap) |
| Whipsaw day (15 crosses) | `mmm_whipsaw_smart.py`, `mmm_circuit_breaker.py`, `mmm_trigger.py` |
| Fast crash (-20% in 30m) | `mmm_safety.py`, `mmm_exit_all.py`, `mmm_margin_guardian.py`, `mmm_regime.py` |
| API outage (503 for 10m) | `mmm_executor.py` (retry), `mmm_pending_orders.py`, `mmm_fill_sync.py` |
| Expiry chaos (DTE=0, both ITM) | `mmm_close_at_5.py`, `mmm_exit_all.py`, `mmm_wind_down.py` |
| Restart mid-adjustment | `mmm_watchdog.py`, `mmm_guardian.py`, `mmm_pending_orders.py` |
| Margin breach | `mmm_margin_guardian.py`, `mmm_safety.py`, `mmm_exit_all.py` |
| Dual monitor ghost | `mmm_guardian.py` (G5), `mmm_monitor.py` (gen guard), `start_session_monitor()` |
| Pure straddle roll at expiry | `mmm_straddle_roll_pure.py`, `mmm_close_at_5.py`, `mmm_wind_down.py` |
| Reverse mode during adjustment | `mmm_reverse.py`, `mmm_monitor.py` (hard if/else ~line 2781) |

**What to Verify per Scenario:**
- Does the scenario have a test in the sealed test suite?
- If not: what is the test coverage gap?
- Is there a safeguard that covers this scenario, or is it handled ad hoc?
- Can this scenario produce untracked positions or incorrect P&L?

**Output Report File:** `PHASE_10_REPLAY_STRESS_AUDIT.md`

**Pass Criteria:** All 10 scenarios mapped to code paths. Missing sealed tests documented. At least 5 new test scenarios proposed for sealing.

---

### Phase 11 — Scaling Readiness Audit

**Objective:** Identify what breaks, slows, or becomes incorrect at 5x and 10x current capital deployment.

**Lead Agent:** Scaling Readiness Agent (Agent 11)
**Supporting Agents:** Math Agent (formula scale limits), Execution Agent (API rate limits)

**Reads Phase 6 + Phase 8 findings first.**

**Files to Read:**
- `mmm_constants.py` (hardcoded limits)
- `mmm_engine.py` (`calculate_lots_to_sell` — lot size at scale)
- `mmm_margin_guardian.py` (margin formula at large lot counts)
- `mmm_storage.py` (DB query patterns — scale with session history)
- `mmm_websocket.py` (emit frequency, message size at scale)
- `mmm_telegram.py` (notification volume)
- `mmm_scaler.py` (scaling multiplier caps)

**What to Verify:**
- Is there a hardcoded max lot cap that would prevent scaling beyond current level?
- Does `calculate_lots_to_sell` produce correct results at 500-lot adjustments?
- Does the margin formula remain accurate at 1000+ total lots?
- Does the DB query pattern for session history remain fast with 6 months of data?
- Does Telegram notification rate stay within API limits at high-frequency trading?
- Does the WebSocket broadcast remain real-time at high message volume?
- Are there any `int` fields that would overflow at large lot counts?

**Hidden Bugs to Search For:**
- Hardcoded `max_lots = 100` that silently caps scaling
- Margin formula using a percentage that becomes dangerously inaccurate at large positions
- DB loading entire session history for each heartbeat (O(n) with session age)
- Telegram sending one message per lot (rate limit breach at 500 lots)
- Decimal precision insufficient for very large premium values ($1M+ session)

**Architecture Issues to Search For:**
- No explicit scaling configuration — current deployment level is implicit
- Performance profiling never done — bottlenecks unknown
- No circuit breaker on DB query time — slow DB blocks heartbeat
- Memory footprint of long-running sessions never measured

**Output Report File:** `PHASE_11_SCALING_AUDIT.md`

**Pass Criteria:** Scaling risk register produced with current limit, 5x limit, 10x limit per item. Hardcoded caps inventory completed.

---

### Phase 12 — Master Refactor Blueprint

**Objective:** Combine all Architecture Issue Register entries from all phases into a permanent redesign roadmap.

**Lead Agent:** Chief Agent (with Architecture Agent support)
**Supporting Agents:** All agents contribute architecture issues

**Reads all Phase 1–11 Architecture Issue Register entries.**

**This phase produces:**
- Consolidated Architecture Issue Register (all issues, deduplicated, ranked)
- Permanent redesign suggestions for each P0/P1 architecture issue
- Migration path risk assessment (what can be refactored without stopping the bot?)
- Sequencing recommendation (what must be fixed first?)

**Output Report File:** `PHASE_12_REFACTOR_BLUEPRINT.md`

**Pass Criteria:** All architecture issues categorized as: (A) Must fix before scaling, (B) Fix in next 30 days, (C) Long-term tech debt, (D) Acceptable trade-off.

---

### Phase 13 — Final Master Verdict

**Objective:** Synthesize all findings into a single confidence assessment and scaling decision.

**Lead Agent:** Chief / God Agent (Agent 12)

**Reads all Phase 1–12 reports in full.**

**Output:** `MASTER_AUDIT_VERDICT.md`

**Required Contents:**
1. Top 20 issues across all phases (merged, deduplicated)
2. Root cause clusters (issues sharing same root cause)
3. Architecture debt summary
4. Symptom-only fixes identified (patches that masked root cause)
5. Permanent redesign priorities
6. Safe scaling checklist (what must be true before increasing capital)
7. Confidence score (0–100) using Section 14 framework
8. Capital scaling recommendation with conditions

---

## 5. ARCHITECTURE ISSUE REGISTER — SEED ENTRIES

These known issues are pre-seeded from prior incident analysis. Each phase must append to this register.

| ID | Problem | Why It Exists | Risk | Modules Affected | Workaround | Redesign | Priority |
|---|---|---|---|---|---|---|---|
| A-001 | `mmm_monitor.py` is a God object (~3000+ lines) | Organic growth, no refactor | All bugs concentrate here | `mmm_monitor.py` | None | Split into MonitorOrchestrator, HeartbeatRunner, RiskGate, EmitLayer | P1 |
| A-002 | Session state is a raw unversioned dict | Speed of development | Silent breakage on old sessions | `mmm_storage.py`, all modules | `initialize_reverse_state()` per-field patch | Typed session schema with version migration | P1 |
| A-003 | `_D()` Decimal helper defined in two modules | Copy-paste | Divergence if one is updated | `mmm_engine.py`, `mmm_constants.py` | Ignored | Single definition in `mmm_constants.py` | P2 |
| A-004 | P&L formula split across 4 modules | Feature additions | Formula drift, different answers from same data | `pnl_core`, `engine`, `monitor`, `api` | Manual sync | Single `compute_pnl(session)` in one canonical module | P1 |
| A-005 | Two fill tracking systems (WS + REST poll) | Redundancy design | Double-counting risk | `fill_sync`, `ws_executions`, `pending_orders` | Deduplication by order ID | Designate WS as primary, REST as reconciliation only | P1 |
| A-006 | Stale monitor incident fixed with 3 patches | Incident response under pressure | Patches may not cover all paths | `monitor`, `guardian`, `safety` | Three-layer guard | Unified generation check at execution gate | P1 |
| A-007 | Strategy-specific behavior in shared modules | No dispatch abstraction | Strategy A bug fixes Strategy B | `monitor`, `close_at_5`, `replenish` | STRATEGY_DISPATCH flags | True strategy handler protocol with interface | P2 |
| A-008 | No fill ledger audit trail integrity check | Not designed yet | Fill manipulation undetectable | `mmm_ledger.py` | None | Append-only ledger with hash chain | P2 |
| A-009 | Reverse mode isolation guaranteed by naming convention only | Manual discipline | Future developer adds reverse field to wrong dict | `mmm_reverse.py`, `monitor` | CLAUDE.md rules | Typed reverse state container | P2 |
| A-010 | Frontend WebSocket field mapping maintained manually | No contract | Frontend shows stale/wrong fields silently | `mmm_websocket.py`, `MMMContext.js` | Manual sync | Auto-generated TypeScript types from backend schema | P2 |

---

## 6. PHASE DEPENDENCIES AND READING ORDER

```
Phase 1 (Architecture)
    ↓
Phase 2 (Accounting) ←— reads Phase 1
    ↓
Phase 3 (P&L) ←————————— reads Phase 1+2
Phase 4 (Risk) ←————————— reads Phase 1
    ↓
Phase 5 (Strategy) ←——————— reads Phase 1+2+4
    ↓
Phase 6 (Math) ←———————————— reads Phase 3+5
Phase 7 (State) ←——————————— reads Phase 1+2
    ↓
Phase 8 (Execution) ←——————— reads Phase 2+7
    ↓
Phase 9 (WebUI) ←——————————— reads Phase 5+7
Phase 10 (Stress) ←————————— reads ALL
Phase 11 (Scaling) ←————————— reads Phase 6+8
    ↓
Phase 12 (Refactor Blueprint) ←—— reads ALL arch registers
    ↓
Phase 13 (Final Verdict) ←————— reads EVERYTHING
```

---

## 7. AGENT COLLABORATION MODEL

### Stage A — Independent Specialist Reviews

Each agent audits its domain independently. No cross-communication during this stage. This prevents anchoring bias (Agent 2 should not know Agent 1's conclusions while reading fills).

### Stage B — Shared Memory Review

Before writing its report, each agent from Phase 3 onward must read all prior phase reports. Findings must be cross-referenced. If Agent 6 (Math) finds a formula bug that contradicts Agent 3's (P&L) finding, both are noted and the discrepancy is documented — not resolved silently.

### Stage C — Chief Integration

The Chief Agent reads all reports simultaneously. The Chief Agent:
- May **reclassify** a finding (e.g., a P1 from Phase 4 becomes P0 when combined with Phase 8 evidence)
- May **merge** findings that share a root cause into a single finding
- May **demote** findings that Phase 2+ evidence shows are not actually present
- Must **note contradictions** between agents and explain which agent's evidence is stronger
- Must produce a **confidence score** using Section 14

---

## 8. PERMANENT FIX THINKING FRAMEWORK

For every serious finding, the following questions must be answered before a fix is recommended:

1. **Is this a symptom or root cause?**
   Example: "net premium shows gross value" is a symptom. "P&L formula split across 4 modules" is a root cause.

2. **Is the root cause architectural?**
   If yes: a local fix will recur. Document in Architecture Issue Register. Recommend permanent redesign.

3. **If fixed locally, can it return elsewhere?**
   Example: fixing gross/net in `mmm_api.py` does not fix it in `mmm_storage.py`. Both need fixing.

4. **What permanent redesign removes the whole class of bug?**
   Example: single `compute_pnl(session)` canonical function eliminates the entire class of P&L formula drift.

5. **What is the safest migration path?**
   Example: new canonical function can shadow the old ones first (both run, results compared) before old ones are removed.

---

## 9. IMPORTANT AUDIT RULES

1. **Never assume old fixes are correct.** Re-read the code. Prior session notes can be wrong.
2. **Re-check symptom fixes for root cause.** Every fix in `mmm_workdone_march.md` is a potential symptom.
3. **If two modules disagree, report both.** Do not pick the "more likely correct" one silently.
4. **If a parameter exists but does nothing, report it.** Phantom params erode operator trust.
5. **If math is weak, explain with examples.** "Formula might be wrong" is insufficient. Show the specific inputs and outputs.
6. **If logic depends on hidden assumptions, expose them.** Example: "This assumes BTC price < $200,000" must be documented.
7. **If tests are missing, note them.** A sealed test for every P0 risk path is mandatory before scaling.
8. **Capital-first mindset.** Every finding is evaluated by: can this cause a real financial loss?
9. **Prefer permanent solutions.** Patch stacking on a live trading system creates compounding risk.
10. **Keep Architecture Issue Register current.** Every phase appends to it.
11. **Chief Agent decisions must be evidence-based.** No "gut feeling" in the verdict. Reference specific file:line or test output.

---

## 10. SEVERITY LEVELS

| Level | Meaning | Action |
|---|---|---|
| **P0** | Can cause real financial loss right now. Live risk. | Stop. Fix before resuming. |
| **P1** | Serious logic error or bypass risk. Will cause problems under certain conditions. | Fix before capital increase. |
| **P2** | Improvement. Incorrect result possible but unlikely. Architecture debt. | Fix within 30 days. |
| **P3** | Cosmetic. Naming inconsistency. Minor display error. | Nice to fix. |

---

## 11. PASS CRITERIA FOR EACH PHASE

A phase is **PASSED** when:
- Its output report file is written
- All functions listed in "Functions to Inspect" have been read and documented
- All "What to Verify" items have a Yes/No/Partial answer with evidence
- All P0/P1 issues found are documented with file:line reference
- Architecture Issue Register updated with any new entries
- Supporting agents have reviewed findings (or explicitly noted they found no contradictions)

A phase is **FAILED** when:
- A P0 is found and escalation to Chief is not immediate
- A "What to Verify" item cannot be answered (file not found, function not understood)
- Phase was executed without reading prior phase reports

---

## 12. FINAL DELIVERABLES

The following files will be produced, in order:

| File | Phase | Agent |
|---|---|---|
| `PHASE_01_ARCHITECTURE_AUDIT.md` | 1 | Architecture Agent |
| `PHASE_02_ACCOUNTING_AUDIT.md` | 2 | Accounting Agent |
| `PHASE_03_PNL_AUDIT.md` | 3 | P&L Agent |
| `PHASE_04_RISK_CONTROLS_AUDIT.md` | 4 | Risk Agent |
| `PHASE_05_STRATEGY_LOGIC_AUDIT.md` | 5 | Strategy Agent |
| `PHASE_06_MATH_MODEL_AUDIT.md` | 6 | Math Agent |
| `PHASE_07_STATE_RECOVERY_AUDIT.md` | 7 | State Agent |
| `PHASE_08_EXECUTION_AUDIT.md` | 8 | Execution Agent |
| `PHASE_09_WEBUI_PARAM_AUDIT.md` | 9 | WebUI Agent |
| `PHASE_10_REPLAY_STRESS_AUDIT.md` | 10 | Stress Agent |
| `PHASE_11_SCALING_AUDIT.md` | 11 | Scaling Agent |
| `PHASE_12_REFACTOR_BLUEPRINT.md` | 12 | Chief + Arch Agent |
| `MASTER_AUDIT_VERDICT.md` | 13 | Chief Agent |

---

## 13. ESTIMATED AUDIT ORDER — FASTEST PATH TO HIGHER CONFIDENCE

The following 5 audits produce the highest safety ROI and should be executed first:

### Priority 1: Phase 4 — Risk Controls
**Why:** If max loss, hard stop, or generation guard has a bypass path, no amount of P&L accuracy matters. This is the existential risk check.

### Priority 2: Phase 3 — P&L Truth
**Why:** The number shown on the dashboard must match reality. Before scaling capital, P&L must be provably correct. Net premium bug (rev9) is a recent example of how subtle these errors are.

### Priority 3: Phase 2 — Accounting Truth
**Why:** Lot counting and fill recording are the foundation of everything else. Orphan positions and missing lots produce compounding P&L errors.

### Priority 4: Phase 8 — Execution Layer
**Why:** The execution layer is where real money moves. Duplicate orders, partial fill mishandling, and API outage behavior must be verified before capital scales.

### Priority 5: Phase 7 — State & Session Recovery
**Why:** The stale monitor incident (2026-03-24) was fundamentally a state recovery issue. Session restore correctness under restart scenarios must be bulletproof.

---

## 14. CONFIDENCE SCORE FRAMEWORK

The confidence score (0–100) is computed after the Chief Agent review.

### Score Components

| Component | Weight | How Measured |
|---|---|---|
| Zero P0 issues found | 25 pts | All P0 candidates investigated and cleared |
| P&L formula verified correct | 15 pts | Manual ledger trace matches live display |
| Risk controls unbypassable | 20 pts | Bypass matrix shows no gaps |
| State survives restarts | 10 pts | Restore test passes for all session types |
| Accounting complete | 10 pts | No orphan position paths found |
| Stress scenarios handled | 10 pts | All 10 scenarios have safeguards identified |
| Parameter truth verified | 5 pts | No phantom params in top-20 list |
| Scaling headroom confirmed | 5 pts | 5x capital has no P0 scaling risk |

### Score Bands

| Score | Meaning |
|---|---|
| 90–100 | High confidence. Scale to next level. |
| 80–89 | Good confidence. Scale with monitoring. |
| 70–79 | Moderate. Fix P1s before scaling. |
| 60–69 | Low. Fix P1s and at least 2 P2s. |
| Below 60 | Do not scale. Significant risks unresolved. |

---

## 15. ARCHITECTURE DEBT MOST LIKELY IN THIS CODEBASE

Based on the incremental build history, the following types of structural debt are most probable:

1. **God object accumulation** — `mmm_monitor.py` likely does too much. Functions were added over time without refactoring the orchestrator.

2. **Patch chain buildup** — The stale monitor incident produced 3 patches. The hedge break incident produced 5 fixes (F1–F5). Each patch is layered on the last. Root causes may remain.

3. **Duplicated state management** — Lots are tracked in position arrays, in `active_lots` counters, in the fill ledger, and in `recompute_side_lots()`. These can drift.

4. **Strategy logic bleeding into shared modules** — Early in the project, strategy-specific behavior was handled inline. As strategies multiplied, this created coupling.

5. **No schema contract** — Session dict, WebSocket message, and API response all evolved without explicit schema documentation. Field names can drift between sender and receiver.

6. **Async/sync boundary violations** — A live trading system with both asyncio loops and threading can accumulate subtle boundary errors that only manifest under high concurrency.

7. **Test coverage asymmetry** — Sealed tests cover specific functions. Integration tests are sparse. Stress scenario coverage is minimal. The gap between unit coverage and system-level confidence is wide.

---

## 16. MASTER_AUDIT_VERDICT.md — REQUIRED STRUCTURE

When the Chief Agent writes the final verdict, it must contain exactly:

```markdown
# MASTER AUDIT VERDICT

## Executive Summary
## Confidence Score: XX/100
## Capital Scaling Recommendation

## Top 20 Issues (Merged and Ranked)
## Root Cause Clusters
## Architecture Debt Summary
## Symptoms vs Root Causes
## Permanent Redesign Priorities
## Safe Scaling Checklist
## What Must Be Fixed Before Next Capital Step
## What Can Wait
## Contradictions Between Agent Findings
## Appendix: Architecture Issue Register (Final)
```

---

## 17. SCOPE BOUNDARIES — WHAT THIS AUDIT DOES NOT COVER

The following are explicitly out of scope for this audit plan:

- **GridBot system** — separate codebase, separate audit if needed
- **Options Panel** — covered by separate options panel audit if needed
- **Exchange API correctness** — we audit our usage of the API, not the exchange itself
- **Infrastructure** — server hosting, launchd config, network reliability
- **Tax and regulatory compliance** — out of scope

---

*End of MMM Master Audit Plan*
*Next command: Execute Phase 1, or designate which phase to begin.*
