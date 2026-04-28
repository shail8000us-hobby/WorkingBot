# Phase 1 — Task 1: MMM Decision Map (Gate Inventory)

**Status**: Complete
**Date**: 2026-04-27
**Auditor**: Claude
**Scope**: Document every gate, blocker, and multiplier in the MMM heartbeat in execution order. For each: reads / writes / blocks / bypassed-by / missing-inputs.

This is the foundation document for the Phase 3 arbiter. Each gap surfaced here becomes a candidate for arbiter coordination.

---

## Heartbeat structure (high-level)

The heartbeat is `_heartbeat_inner()` in [mmm_monitor.py:1472](../../../webui/backend/routes/mmm/mmm_monitor.py#L1472), called from `_heartbeat()` ([1460](../../../webui/backend/routes/mmm/mmm_monitor.py#L1460)) which is called from `_run_loop()` ([1084](../../../webui/backend/routes/mmm/mmm_monitor.py#L1084)).

Runs every `adjustment_interval` seconds (default 300s).

```
RUN LOOP — sealed primary guard (stale monitor protection, CLAUDE.md §4)
  ↓
HEARTBEAT INNER
  ├─ Pre-flight: graceful exit gate
  ├─ Step 0    : Position reconcile / fill sync
  ├─ Step 0.5  : Margin Guardian
  ├─ Step 0.75 : Auto-promote ATM strike
  ├─ Step 1    : Fetch premiums (circuit breaker)
  ├─ Step 2    : Close-at-5 scan
  ├─ Step 2.1  : Profit Harvesting (M1)
  ├─ Lifecycle close detection
  ├─ One-side close guard + auto-replenish
  ├─ Step 3    : Safety checks (run_all_checks)
  │            ├─ Phase 6 inner: Smart whipsaw early evaluation
  │            └─ Phase 6 outer: Smart whipsaw block gate
  ├─ Step 3.5  : Regime controls (delta/gamma/vol/trend)
  ├─ Step 4    : Paused / both-sides-up handling
  ├─ Step 5    : Cooldown check
  ├─ Step 5.3  : Adaptive tuning engine
  ├─ Step 5.4  : Strategy dispatch
  ├─ Step 5.5  : ATM Shield
  ├─ Step 5.6  : Proactive Shift Scanner
  ├─ Step 5.7  : Breakeven Engine
  ├─ Step 5.8  : Gamma Detector
  ├─ Step 5.5b : Delta Neutral Engine
  ├─ God Layer : strategic drift correction
  ├─ skip-to-PNL gate (if any prior block fired)
  ├─ Step 6    : Evaluate triggers (with whipsaw widening)
  ├─ Step 7    : Process outcome (adjustment/reverse intercept)
  ├─ Step 7.5  : Perp delta hedge
  ├─ Step 8    : Update P&L
  ├─ Step 9    : Portfolio delta
  ├─ POST-UPDATE max loss check (Tier 0)
  ├─ Step 9    : Walkthrough generation
  └─ Auto-reconcile drift check
```

---

## Notation key

For each gate entry below:

- **Type**: `BLOCK` (binary), `MULTIPLIER` (scales lot/trigger), `ROUTE` (changes path), `STATE` (writes session), `T0` (Tier 0 absolute)
- **Reads**: signals consumed (session keys, params)
- **Writes**: session state produced
- **Blocks**: downstream operations stopped/altered
- **Bypassed by**: signals/strategies that override
- **Gaps**: signals missing — coordination defects

---

## SECTION A — Tier 0 Sealed Gates

These run outside or above the heartbeat and never bypass.

### A1. Hard Stop Guard (sealed in `__init__`)
- **File**: [mmm_monitor.py:165](../../../webui/backend/routes/mmm/mmm_monitor.py#L165)
- **Type**: T0
- **Trigger**: `_hard_stop_fired` event. Set by either (a) max_loss breach (line 4085) or (b) margin emergency or (c) external signal.
- **Reads**: `_hard_stop_fired` event flag.
- **Writes**: triggers `_auto_close_all(emergency=True)`.
- **Blocks**: everything — terminates all open positions via market orders.
- **Bypassed by**: nothing. Sealed.
- **Gaps**: none.

### A2. Stale Monitor Generation Guard (CLAUDE.md §4)
- **File**: `_run_loop` primary guard ([mmm_monitor.py:1084](../../../webui/backend/routes/mmm/mmm_monitor.py#L1084)) + Guardian G5 in `_heartbeat`
- **Type**: T0
- **Trigger**: `stored_gen > self._my_generation` (a newer monitor instance exists).
- **Reads**: session generation field, `self._my_generation`.
- **Writes**: `_running = False`, fires Telegram + `emit_safety()`, breaks loop.
- **Blocks**: all activity from stale monitor instance.
- **Bypassed by**: nothing. Sealed (CLAUDE.md §4 — three-layer fix from 2026-03-24 incident).
- **Gaps**: none.

### A3. Time-Based Hard Stop Near Expiry
- **File**: configured per-strategy; checked via safety events
- **Type**: T0
- **Trigger**: minutes_to_expiry ≤ `auto_close_minutes_before_expiry` (default 15).
- **Reads**: `_minutes_to_expiry`, `params['auto_close_minutes_before_expiry']`.
- **Writes**: triggers `_auto_close_all`.
- **Blocks**: all new trades; closes everything.
- **Bypassed by**: nothing per Phase 2 / A3.
- **Gaps**: none.

### A4. POST-UPDATE Max Loss Check
- **File**: [mmm_monitor.py:4057-4099](../../../webui/backend/routes/mmm/mmm_monitor.py#L4057-L4099)
- **Type**: T0
- **Trigger**: `current_total_pnl <= -max_loss_amount` (after P&L update each beat).
- **Reads**: `pnl['net_pnl']`, `_reverse.net_pnl`, `params['max_loss_amount']`.
- **Writes**: `_hard_stop_fired.set()`, `_auto_close_all(emergency=True)`.
- **Blocks**: terminates all positions immediately, market-order exit.
- **Bypassed by**: nothing.
- **Gaps**: none. This is the critical Tier 0 enforcer. Every Phase 3 arbiter decision must respect this — but since it runs AFTER all module decisions, this is naturally enforced.

---

## SECTION B — Pre-trigger Gates (Steps 0–3)

### B1. Global Graceful Exit Gate
- **File**: [mmm_monitor.py:1541-1553](../../../webui/backend/routes/mmm/mmm_monitor.py#L1541-L1553)
- **Type**: BLOCK
- **Trigger**: `_should_stop()` or session status not running.
- **Reads**: `self._stopping`, session status.
- **Writes**: returns from heartbeat.
- **Blocks**: entire heartbeat.
- **Bypassed by**: nothing.
- **Gaps**: none — pure plumbing.

### B2. Margin Guardian (Step 0.5)
- **File**: [mmm_monitor.py:1638-1689](../../../webui/backend/routes/mmm/mmm_monitor.py#L1638-L1689)
- **Type**: BLOCK / STATE / T0 (in CRITICAL escalation)
- **Trigger**: margin tier check via `_check_margin_guardian()`.
- **Reads**: exchange margin, `params['margin_*']`.
- **Writes**:
  - `_last_margin_snapshot` (tier + utilization)
  - `_margin_wind_down = True` if ORANGE
  - `_margin_block_sells = True` if YELLOW
  - On RED/CRITICAL: triggers emergency close
  - On consecutive CRITICAL: forces session stop
- **Blocks**:
  - YELLOW → blocks new sells
  - ORANGE → flags wind_down (used by other modules)
  - RED/CRITICAL → emergency close, return from heartbeat
- **Bypassed by**: NONE (margin is physical capital limit).
- **Gaps**: NONE — margin check is correctly placed at top of heartbeat.

### B3. Premium Fetch Circuit Breaker (Step 1)
- **File**: [mmm_monitor.py:1698-1880](../../../webui/backend/routes/mmm/mmm_monitor.py#L1698-L1880)
- **Type**: BLOCK
- **Trigger**: premium fetch fails N times → circuit opens.
- **Reads**: chain data via initializer.
- **Writes**: `_circuit_breaker` state.
- **Blocks**: trigger evaluation if circuit open (no fresh prices).
- **Bypassed by**: fallback prices may be used if available.
- **Gaps**: NONE for Phase 3 — circuit breaker is data-availability gate, not coordination gate.

### B4. One-Side Close Guard + Auto-Replenish
- **File**: [mmm_monitor.py:2270-2503](../../../webui/backend/routes/mmm/mmm_monitor.py#L2270-L2503)
- **Type**: BLOCK / ROUTE
- **Trigger**: one side fully closed while other has positions, OR partial replenish pending.
- **Reads**: `total_lots` per side, `_replenish_ocs_active`, `_replenish_lots_remaining_*`.
- **Writes**: `_replenish_ocs_active`, replenish lots, possibly pauses session.
- **Blocks**: triggers + adjustments if pause path taken.
- **Bypassed by**: monitor stopping (line 2316).
- **Gaps**:
  - Does not coordinate with breakeven zone — if breakeven CRITICAL, replenish should arguably be more aggressive.
  - Documented in CLAUDE.md §2026-04-02 hedge_break incident. **Coordination gap acknowledged**.

### B5. Safety Checks (Step 3 — `run_all_checks`)
- **File**: [mmm_monitor.py:2576](../../../webui/backend/routes/mmm/mmm_monitor.py#L2576) → `mmm_safety.py`
- **Type**: BLOCK / STATE
- **Trigger**: per-beat checks (whipsaw, lot_velocity, position_cap, trailing_stop, ITM guard, max_loss, etc.)
- **Reads**: many session keys; per-check.
- **Writes**: `safety_events[]` list with `action in {'stop_adjustments','auto_close','stop','pause','warn','resume'}`.
- **Blocks**:
  - `auto_close` → close all (Tier 0)
  - `stop` → terminate session
  - `stop_adjustments` → set `_skip_to_pnl=True`, skip triggers
  - `pause` → pause session
- **Bypassed by**:
  - `dangerous_mode` — bypasses all `stop_adjustments` (line 2706)
  - `STRADDLE_WITH_ADJUSTMENT` — bypasses all `stop_adjustments` (line 2715)
- **Gaps**:
  - No bypass for `_breakeven_zone == 'CRITICAL'`. **TODAY'S BUG.**
  - No bypass for `_breakeven_zone == 'DANGER'`.
  - These two gaps are exactly what Phase 2 / Rule 2 (Tier 1 acts) is designed to fix.

### B6. Smart Whipsaw — Early Evaluation (Phase 6 inner)
- **File**: [mmm_monitor.py:2560-2574](../../../webui/backend/routes/mmm/mmm_monitor.py#L2560-L2574)
- **Type**: STATE (caches decision for later use)
- **Trigger**: every beat (cached for reuse at Step 6 widening + Step 7 lot reduction).
- **Reads**: `ce_now`, `pe_now`, `_regime_spot_price` (from PRIOR beat — see Gap), session state for detector inputs.
- **Writes**: `self._beat_whipsaw_decision`, `_smart_ws_*` keys, `_whipsaw_dispatcher_ran=True`.
- **Blocks**: nothing here — produces decision; gating happens at B7.
- **Bypassed by**: STRADDLE_WITH_ADJUSTMENT (incorrectly — see Task 3 audit).
- **Gaps**:
  - Reads `_regime_spot_price` set in PRIOR beat (set at Step 3.5, line 2811, AFTER this point in current beat). 1-beat lag on spot.
  - Does NOT read `_breakeven_zone` (stale by 1 beat anyway, but available). **TODAY'S BUG ROOT CAUSE.**
  - Does NOT read `_gamma_zone_prev` or `_gamma_result`.

### B7. Smart Whipsaw — Block Gate (Phase 6 outer)
- **File**: [mmm_monitor.py:2769-2796](../../../webui/backend/routes/mmm/mmm_monitor.py#L2769-L2796)
- **Type**: BLOCK
- **Trigger**: `self._beat_whipsaw_decision.block_adjustment is True`.
- **Reads**: cached decision from B6.
- **Writes**: `_skip_to_pnl=True`, emit safety event.
- **Blocks**: all triggers + adjustments this beat.
- **Bypassed by**:
  - `dangerous_mode` (line 2776)
  - `_is_straddle_adj` (line 2777) — but Phase 2 user wants this bypass removed (smart whipsaw should block over-adjustment in straddle).
- **Gaps** (CRITICAL):
  - **No `_breakeven_zone` bypass** — this is today's bug.
  - **No `_margin_tier='RED'` bypass** — though margin RED has its own emergency close path, the coordination is implicit, not explicit.
  - **No Tier 1 hierarchy awareness** at all. Will be added by Phase 3 arbiter (Rule 2).

---

## SECTION C — Strategic Gates (Steps 3.5 – 5.8)

### C1. Regime Controls (Step 3.5)
- **File**: [mmm_monitor.py:2798-3018](../../../webui/backend/routes/mmm/mmm_monitor.py#L2798-L3018) → `mmm_regime.py`
- **Type**: BLOCK / STATE
- **Trigger**: portfolio delta + gamma + vol + trend computed → regime action determined.
- **Reads**: `portfolio_delta`, `_last_gamma_data`, vol regime, trend, `_regime_spot_price`.
- **Writes**:
  - `_regime_action` ∈ `{ACTION_NORMAL, ACTION_BLOCK_CE_SELLS, ACTION_BLOCK_PE_SELLS, ACTION_BLOCK_ALL_SELLS, ACTION_FORCE_REDUCE, ACTION_PAUSE}`
  - `_regime_state`, `_vol_regime`, `_trend_state`
- **Blocks**: per `_regime_action`. Used downstream at adjustment processing.
- **Bypassed by**:
  - `dangerous_mode`
  - `STRADDLE_WITH_ADJUSTMENT` (`_strategy_handler.bypass_gamma_guards`)
  - God Layer can bypass `BLOCK_SELLS`
- **Gaps**:
  - **No `_breakeven_zone` consideration** — regime can BLOCK_PE_SELLS even when breakeven CRITICAL on PE (this is the CLAUDE.md §2026-04-02 hedge_break incident).
  - **No interaction with smart whipsaw decision** — both are independent block sources.
  - 2026-04-27 rev5/rev6 fixes addressed VOL_HIGH+TREND directional logic, but Tier 1 coordination still missing.

### C2. Cooldown Check (Step 5)
- **File**: [mmm_monitor.py:3172-3206](../../../webui/backend/routes/mmm/mmm_monitor.py#L3172-L3206)
- **Type**: BLOCK
- **Trigger**: `is_cooldown_active(session)` returns True (post-reversal cooldown).
- **Reads**: `cooldown_active`, `cooldown_until`.
- **Writes**: `_skip_to_pnl=True`.
- **Blocks**: trigger evaluation + adjustments.
- **Bypassed by**: `dangerous_mode`, `STRADDLE_WITH_ADJUSTMENT` (correctly per straddle doctrine).
- **Gaps**:
  - **No `_breakeven_zone` bypass** — cooldown blocks even when breakeven CRITICAL.
  - **No `_margin_tier='RED'` bypass**.

### C3. Adaptive Tuning Engine (Step 5.3)
- **File**: [mmm_monitor.py:3210-3213](../../../webui/backend/routes/mmm/mmm_monitor.py#L3210-L3213) → `mmm_adaptive.py`
- **Type**: STATE (modifies params via tuning)
- **Trigger**: `adaptive_mode == 'adaptive'`.
- **Reads**: market regime signals.
- **Writes**: tunes params dynamically.
- **Blocks**: nothing.
- **Bypassed by**: `adaptive_mode != 'adaptive'`.
- **Gaps**:
  - Adaptive engine could in principle tune params during Tier 1 — needs coordination so adaptive tuning doesn't fight arbiter decisions.

### C4. Strategy Dispatch (Step 5.4)
- **File**: [mmm_monitor.py:3215-3231](../../../webui/backend/routes/mmm/mmm_monitor.py#L3215-L3231)
- **Type**: ROUTE (selects per-strategy handler)
- **Trigger**: every beat.
- **Reads**: `params['strategy_type']`.
- **Writes**: `_strategy_handler` reference.
- **Blocks**: handler may abort heartbeat for its strategy (e.g., STRADDLE_ROLL).
- **Bypassed by**: nothing.
- **Gaps**: handler-specific decisions are isolated; arbiter must call into handlers respectfully.

### C5. ATM Shield (Step 5.5)
- **File**: [mmm_monitor.py:3243-3251](../../../webui/backend/routes/mmm/mmm_monitor.py#L3243-L3251) → `mmm_atm_shield.py`
- **Type**: T0 (when enabled) / ROUTE
- **Trigger**: `params['atm_shield_enabled']` AND not paused AND `_strategy_handler.should_run_atm_shield`.
- **Reads**: spot, strikes, `params['atm_shield_*']`.
- **Writes**: `_atm_shield_fired = True` if buyback executed.
- **Blocks**: trigger evaluation skipped if shield fired (line 3517).
- **Bypassed by**: STRADDLE strategies (handler flag) — correct per Phase 2 / D6.
- **Gaps**: ATM shield's internal `vol_gamma_blocked` guard already considers gamma+vol; OK as-is. Tier 0 is correctly absolute.

### C6. Proactive Shift Scanner (Step 5.6)
- **File**: [mmm_monitor.py:3253-3280](../../../webui/backend/routes/mmm/mmm_monitor.py#L3253-L3280)
- **Type**: STATE (pre-scans candidates)
- **Trigger**: not skipping to PNL, proactive_shift_enabled, not pure-straddle (or asymmetric straddle).
- **Reads**: spot, chain.
- **Writes**: `_proactive_shifted_ce`, `_proactive_shifted_pe`, candidate cache.
- **Blocks**: nothing.
- **Bypassed by**: `_skip_to_pnl`, pure straddle.
- **Gaps**:
  - **Does NOT prioritize shift when `_breakeven_zone='CRITICAL'`** — runs at same priority as normal beats. Phase 3 arbiter Tier 1 will force a shift at CRITICAL.

### C7. Breakeven Engine (Step 5.7)
- **File**: [mmm_monitor.py:3282-3346](../../../webui/backend/routes/mmm/mmm_monitor.py#L3282-L3346) → `mmm_breakeven_engine.py`
- **Type**: STATE / MULTIPLIER
- **Trigger**: `breakeven_control_enabled`.
- **Reads**: spot, positions, `_breakeven_zone_prev`, params.
- **Writes**:
  - `_breakeven_result` (full dict)
  - `_breakeven_multiplier` (1.0–3.0)
  - `_breakeven_zone` ∈ `{'SAFE','WARNING','DANGER','CRITICAL'}`
  - `_breakeven_zone_prev` (for transition logging)
- **Blocks**: nothing directly. Multiplier is consumed by `calculate_lots_to_sell()`.
- **Bypassed by**: `breakeven_control_enabled = False`.
- **Gaps**:
  - **CRITICAL: zone is consumed only by `calculate_lots_to_sell()` for multiplier; no other gate reads it.** This is the gap that causes today's bug — whipsaw, regime, cooldown, smart whipsaw all ignore breakeven zone.
  - **No timestamp** on `_breakeven_zone` — Rule 6 (stale = danger) needs this.

### C8. Gamma Detector (Step 5.8)
- **File**: [mmm_monitor.py:3349-3390](../../../webui/backend/routes/mmm/mmm_monitor.py#L3349-L3390) → `mmm_gamma_detector.py`
- **Type**: STATE / MULTIPLIER
- **Trigger**: `gamma_detector_enabled`.
- **Reads**: positions, spot, breakeven engine.
- **Writes**:
  - `_gamma_result` (full dict)
  - `_gamma_zone_prev`
- **Blocks**: nothing directly (observation-only, comment line 3351).
- **Bypassed by**: `gamma_detector_enabled = False`.
- **Gaps**:
  - **Comment says "observation-only, does NOT influence lot sizing"** but `calculate_lots_to_sell` reads `_gamma_result.gamma_zone` for severity multiplier (mmm_engine.py:475-480). Comment is outdated — gamma severity multiplier IS active when `gamma_severity_multiplier_enabled=True`.
  - **No timestamp on `_gamma_result`** — needed for Rule 6.
  - **User dissatisfaction documented in Phase 2 / B3** — DTE-awareness and lot-size-awareness need verification (Task 2 audit, next).

### C9. Delta Neutral Engine (Step 5.5b)
- **File**: [mmm_monitor.py:3442-3506](../../../webui/backend/routes/mmm/mmm_monitor.py#L3442-L3506)
- **Type**: STATE / ROUTE
- **Trigger**: enabled when params['delta_neutral_enabled'].
- **Reads**: portfolio delta.
- **Writes**: hedge calc.
- **Blocks**: may trigger perp hedge.
- **Bypassed by**: not enabled by default.
- **Gaps**: independent module; doesn't read breakeven/gamma. Consider in Phase 3 if user enables.

### C10. God Layer (Strategic Drift Correction)
- **File**: [mmm_monitor.py:3392-3440](../../../webui/backend/routes/mmm/mmm_monitor.py#L3392-L3440)
- **Type**: ROUTE (overrides soft guards)
- **Trigger**: 25-min clock, `god_enabled=True`.
- **Reads**: drift signals.
- **Writes**: may force adjustments.
- **Blocks**: bypasses `lot_velocity`, `regime BLOCK_SELLS`, `margin YELLOW`, asymmetry.
- **Bypassed by**: hard stops (PAUSE, STOPPED, margin wind_down, FORCE_REDUCE).
- **Gaps**:
  - **God Layer is essentially a Tier-1-like override mechanism but separate from arbiter.** Phase 3 arbiter should subsume God Layer's bypass logic OR explicitly coordinate with it. **Architecturally redundant once arbiter ships.**
  - God doesn't read breakeven zone either.

---

## SECTION D — Trigger and Process Gates (Steps 6–9)

### D1. Skip-to-PNL Gate (consolidator)
- **File**: [mmm_monitor.py:3508-3522](../../../webui/backend/routes/mmm/mmm_monitor.py#L3508-L3522)
- **Type**: BLOCK
- **Trigger**: any prior gate set `_skip_to_pnl=True`.
- **Reads**: `_skip_to_pnl`, `_atm_shield_fired`.
- **Writes**: skips Step 6/7.
- **Blocks**: trigger evaluation + adjustment processing.
- **Bypassed by**: nothing — this is the consolidator that respects all upstream blocks.
- **Gaps**: this is the BIG choke point for arbiter. Phase 3 arbiter Tier 1 will *unset* `_skip_to_pnl` when Tier 1 conditions are met, after evaluating which upstream block set it.

### D2. Whipsaw Trigger Widening (within Step 6)
- **File**: [mmm_monitor.py:3543-3557](../../../webui/backend/routes/mmm/mmm_monitor.py#L3543-L3557)
- **Type**: MULTIPLIER (widens trigger threshold)
- **Trigger**: `_wsd.trigger_widen_factor > 1.0` AND not straddle.
- **Reads**: cached whipsaw decision, `_effective_min_trigger_move`.
- **Writes**: `_effective_min_trigger_move`, `_whipsaw_trigger_widened=True`.
- **Blocks**: makes triggers fire less often.
- **Bypassed by**: STRADDLE_WITH_ADJUSTMENT (correct per Task 3 audit — under-adjusting hurts straddle).
- **Gaps**:
  - **No bypass when `_breakeven_zone='CRITICAL'`** — wider triggers delay defense exactly when defense is needed.
  - **No bypass when `_margin_tier='RED'`** but in this case RED's emergency close handles it.

### D3. Trigger Evaluation (Step 6)
- **File**: [mmm_monitor.py:3559](../../../webui/backend/routes/mmm/mmm_monitor.py#L3559) → `mmm_trigger.py`
- **Type**: STATE / ROUTE
- **Trigger**: every beat where not skipping.
- **Reads**: premiums, `_effective_min_trigger_move`.
- **Writes**: trigger result, outcome (NONE/CE/PE/BOTH).
- **Blocks**: outcome=NONE → no adjustment.
- **Bypassed by**: nothing (this is the trigger itself).
- **Gaps**: trigger logic is single-aggressor; doesn't know about breakeven priority.

### D4. Both-Sides-Up Detection (Step 7)
- **File**: [mmm_monitor.py:3609-3672](../../../webui/backend/routes/mmm/mmm_monitor.py#L3609-L3672)
- **Type**: ROUTE / BLOCK (pause)
- **Trigger**: outcome=BOTH (both sides triggered same beat).
- **Reads**: trigger outcome, history.
- **Writes**: pauses session, alerts user.
- **Blocks**: adjustment processing.
- **Bypassed by**: nothing — both-sides-up is a structural anomaly.
- **Gaps**: arbiter Tier 1 should consider pre-empting both-sides-up if breakeven CRITICAL.

### D5. Tier D Delta Rescue (within Step 7)
- **File**: [mmm_monitor.py:3674-3709](../../../webui/backend/routes/mmm/mmm_monitor.py#L3674-L3709)
- **Type**: ROUTE
- **Trigger**: portfolio delta exceeds rescue threshold.
- **Reads**: `portfolio_delta`, params.
- **Writes**: forces hedge.
- **Blocks**: replaces normal adjustment path.
- **Bypassed by**: nothing.
- **Gaps**: delta rescue runs independently of breakeven.

### D6. Reverse Mode Intercept (within Step 7)
- **File**: [mmm_monitor.py:3783-3848](../../../webui/backend/routes/mmm/mmm_monitor.py#L3783-L3848) → `mmm_reverse.py`
- **Type**: ROUTE
- **Trigger**: `reverse_enabled` AND `_reverse.active`.
- **Reads**: `_reverse` state.
- **Writes**: routes to `process_reverse_entry` instead of `_process_adjustment`.
- **Blocks**: hard mutual exclusion with normal adjustment (CLAUDE.md §5).
- **Bypassed by**: nothing — strict isolation.
- **Gaps**: per Phase 2 / D4, reverse remains isolated from arbiter (correct).

### D7. Pending Order Guard (within `_process_adjustment`)
- **File**: [mmm_monitor.py:4744-4790](../../../webui/backend/routes/mmm/mmm_monitor.py#L4744-L4790)
- **Type**: BLOCK
- **Trigger**: pending order outstanding for this side.
- **Reads**: `_pending_orders`.
- **Writes**: skips adjustment.
- **Blocks**: prevents double-orders.
- **Bypassed by**: nothing.
- **Gaps**: none — this is operational hygiene, not coordination.

### D8. Reversal Check (within `_process_adjustment`, §9)
- **File**: [mmm_monitor.py:4800](../../../webui/backend/routes/mmm/mmm_monitor.py#L4800) → `mmm_reversal.py`
- **Type**: ROUTE / BLOCK
- **Trigger**: aggressor flip detected.
- **Reads**: aggressor history.
- **Writes**: cooldown activation, reversal record.
- **Blocks**: may skip adjustment.
- **Bypassed by**: nothing.
- **Gaps**: reversal logic doesn't read breakeven zone. Phase 3 arbiter Tier 1 should override reversal block when breakeven CRITICAL.

### D9. Lot Reduction at RESTRICT (within `_process_adjustment`)
- **File**: [mmm_monitor.py:5128-5144](../../../webui/backend/routes/mmm/mmm_monitor.py#L5128-L5144)
- **Type**: MULTIPLIER (halves lots)
- **Trigger**: `_ws_lot_scalar < 1.0` AND lots > 1 AND not straddle.
- **Reads**: cached whipsaw decision.
- **Writes**: reduces `lots`, appends constraint message.
- **Blocks**: not absolute — just smaller adjustment.
- **Bypassed by**: STRADDLE_WITH_ADJUSTMENT (correct per Task 3 audit).
- **Gaps**: same as D2 — no bypass for breakeven CRITICAL.

### D10. Guardian G1 (Hedge Integrity Gate)
- **File**: [mmm_monitor.py:4351-4365](../../../webui/backend/routes/mmm/mmm_monitor.py#L4351-L4365)
- **Type**: BLOCK
- **Trigger**: hedge structure invariant violated.
- **Reads**: position structure.
- **Writes**: blocks adjustment.
- **Blocks**: prevents structural breach.
- **Bypassed by**: nothing.
- **Gaps**: structural integrity — sacred. No arbiter override needed.

---

## SECTION E — Multipliers (lot/trigger scaling, not blocks)

These do not block adjustments but modify their size or threshold. Composition order matters.

### E1. Whipsaw Trigger Widen Factor
- **From**: B6 / D2
- **Range**: 1.0 (NORMAL/DEFENSIVE) → 1.5 (DEFENSIVE) → 2.0 (RESTRICT/OBSERVE) → 3.0 (LOCKDOWN)
- **Applied to**: `_effective_min_trigger_move`
- **Composes with**: `theta_acceleration` widening — taken as `max()` not multiplied (line 3556).
- **Bypassed by**: STRADDLE_WITH_ADJUSTMENT.

### E2. Whipsaw Lot Scalar
- **From**: B6 / D9
- **Range**: 1.0 (normal) → 0.5 (RESTRICT) → 0.25 (OBSERVE) → 0.0 (LOCKDOWN — blocks)
- **Applied to**: `lots` after `calculate_lots_to_sell`.
- **Composes with**: nothing — overwrites lot count.
- **Bypassed by**: STRADDLE_WITH_ADJUSTMENT (currently bypasses fully — Task 3 says scalar bypass is correct).

### E3. T3-2 Gamma-Aware Multiplier
- **File**: [mmm_engine.py:419-446](../../../webui/backend/routes/mmm/mmm_engine.py#L419-L446)
- **Range**: 1.0 → 1.1 → 1.2 → 1.3 (capped at `gamma_aware_max_multiplier`)
- **Applied to**: lots before breakeven multiplier.
- **Composes with**: breakeven multiplier (multiplicative, line 455).
- **Bypassed by**: `gamma_aware_enabled = False`.

### E4. Breakeven Aggression Multiplier
- **File**: [mmm_engine.py:448-461](../../../webui/backend/routes/mmm/mmm_engine.py#L448-L461)
- **Range**: 1.0 (SAFE) → 1.0–1.3 (WARNING) → 1.3–2.0 (DANGER) → 2.0–3.0 (CRITICAL)
- **Applied to**: lots after T3-2.
- **Composes with**: T3-2 (multiplicative).
- **Bypassed by**: `breakeven_control_enabled = False`.

### E5. Gamma Severity Multiplier
- **File**: [mmm_engine.py:463-end](../../../webui/backend/routes/mmm/mmm_engine.py#L463)
- **Range**: 1.0 (SAFE) → 1.1 (WARNING) → 1.1–1.5 (DANGER, proportional)
- **Applied to**: lots after breakeven multiplier.
- **Composes with**: previous multipliers (multiplicative).
- **Bypassed by**: `gamma_severity_multiplier_enabled = False`.

### E6. Position Cap (`max_lots_per_side`)
- **File**: `mmm_engine.py` `calculate_lots_to_sell`
- **Range**: hard cap.
- **Applied to**: final `lots`.
- **Composes**: takes precedence — caps everything else.
- **Bypassed by**: nothing — physical limit.

**Composition order in `calculate_lots_to_sell`**:
```
raw_lots = loss_to_cover / (premium * LOT_SIZE_BTC) * (1 + premium_buffer_pct)
       ↓
apply T3-2 gamma-aware multiplier (1.0–1.3)
       ↓
apply breakeven multiplier (1.0–3.0)
       ↓
apply gamma severity multiplier (1.0–1.5)
       ↓
clamp to max_lots_per_side
       ↓
[after return] whipsaw lot scalar (×0.5 for RESTRICT, etc.) — BYPASSED by Tier 1 in arbiter
```

Worst case multiplier stack: 1.05 × 1.3 × 3.0 × 1.5 = **6.14×** raw. Position cap (max 100) saves the day. But during STRADDLE_WITH_ADJUSTMENT (where breakeven and gamma may both bypass differently), this composition is currently the source of cheap-policy pile-up.

---

## SECTION F — Coordination Gaps Surfaced

These are the structural defects this map reveals. Each becomes a Phase 3 arbiter responsibility.

### Gap #1 — `_breakeven_zone` is read by ZERO blocking gates
**Severity**: CRITICAL (today's bug)
**Modules that should read it**: B5 (safety), B6/B7 (whipsaw), C1 (regime), C2 (cooldown), D2 (trigger widen), D8 (reversal), D9 (lot reduction).
**Modules that DO read it**: only `calculate_lots_to_sell` (E4 multiplier).
**Fix**: Phase 3 arbiter at Tier 1 forces all the above gates to bypass when `_breakeven_zone in ('DANGER','CRITICAL')`.

### Gap #2 — `_gamma_zone` similarly siloed
**Severity**: HIGH
**Reads**: only E5 multiplier.
**Fix**: arbiter consumes for Tier 1 escalation (also: gamma engine itself needs DTE/lot-size audit — Task 2).

### Gap #3 — No timestamps on signal writes
**Severity**: HIGH (Rule 6 dependency)
**Affected**: `_breakeven_zone`, `_gamma_result`, `_regime_action`, `_margin_tier`, `_smart_ws_loss_velocity`.
**Fix**: Task 5 (stale-detection feasibility) will plan this. Each signal needs `_signal_last_updated_ts` field.

### Gap #4 — God Layer redundant with arbiter
**Severity**: MEDIUM (architectural)
**Description**: God Layer already implements Tier-1-like bypass mechanism (skips lot_velocity, regime BLOCK_SELLS, margin YELLOW, asymmetry). Phase 3 arbiter implements the same pattern more comprehensively.
**Fix**: Phase 3 arbiter subsumes God Layer logic OR explicitly coordinates. Decide during Phase 3 design.

### Gap #5 — Smart whipsaw and regime are independent block sources
**Severity**: HIGH
**Description**: B7 (smart whipsaw block) and C1 (regime block) each set blocks independently. They do not coordinate or share signals. Together they can over-block in extreme conditions.
**Fix**: arbiter merges them at Tier 1 hierarchy.

### Gap #6 — STRADDLE_WITH_ADJUSTMENT bypass is over-applied (Task 3)
**Severity**: HIGH (Phase 3 fix already designed)
**Description**: smart whipsaw `block` and `token budget` incorrectly bypassed for straddle.
**Fix**: surgical fix per Task 3 audit. Apply during Phase 3.

### Gap #7 — Replenish (B4) ignores breakeven zone
**Severity**: MEDIUM
**Description**: one-side close replenish proceeds at normal pace even if breakeven CRITICAL.
**Fix**: arbiter Tier 1 should accelerate replenish OR replenish should consume `_breakeven_zone` directly.

### Gap #8 — Cooldown (C2) ignores breakeven zone
**Severity**: HIGH
**Description**: post-reversal cooldown blocks adjustment even when breakeven CRITICAL.
**Fix**: arbiter Tier 1 bypasses cooldown.

### Gap #9 — Reversal (D8) ignores breakeven zone
**Severity**: HIGH
**Description**: aggressor flip → reversal logic blocks adjustment with no awareness of breakeven priority.
**Fix**: arbiter Tier 1 overrides reversal block.

### Gap #10 — Adaptive Engine could fight arbiter
**Severity**: LOW
**Description**: adaptive tuning runs in Step 5.3, before arbiter would activate. Tuning during Tier 1 events could distort arbiter's decisions.
**Fix**: arbiter Tier 1 freezes adaptive tuning for the beat.

---

## SECTION G — Heartbeat Order Implications for Arbiter Placement

The arbiter must run after ALL signals are computed but BEFORE the final block consolidator (D1) and trigger evaluation (D3). The natural insertion point is:

```
… Step 5.7 Breakeven   ← writes _breakeven_zone
   Step 5.8 Gamma      ← writes _gamma_zone
   God Layer
↓
[NEW] ARBITER          ← reads everything, decides Tier 0/1/2
↓
   Skip-to-PNL gate (D1) — modified to respect arbiter
   Step 6 Triggers
   Step 7 Process
```

Issue: Smart whipsaw decision was made WAY EARLIER at Phase 6 inner (B6, line 2564) — before breakeven/gamma signals are fresh. This is why today's bug exists.

**Phase 3 design implication**: smart whipsaw evaluation can stay at Phase 6 inner (it's just a decision computation). What changes is which signals it consumes for `_check_pressure_override` AND whether the arbiter (running later, with fresh breakeven/gamma) can override the cached whipsaw decision.

Two equivalent designs:

- **Design A**: Move arbiter check before B7 (whipsaw block gate). Arbiter activates → forces `_beat_whipsaw_decision.block_adjustment = False` (or similar override flag). Whipsaw block gate respects override.
- **Design B**: Keep whipsaw block gate as-is. Arbiter runs LATER (after breakeven/gamma) and explicitly unsets `_skip_to_pnl` if Tier 1 fires, plus bypasses any other `skip_to_pnl` setters.

Design B is cleaner because arbiter has full information when it acts. Design A requires whipsaw decision to be partially deferred.

**Recommendation**: Design B. Phase 3 arbiter runs after Step 5.8 / God Layer (around line 3441), reads all freshly-computed state (`_breakeven_zone`, `_gamma_zone`, `_margin_tier`, `_smart_ws_loss_velocity`), and either confirms `_skip_to_pnl` or unsets it with a defensive shift action injected.

---

## SECTION H — Phase 3 Candidate List (cumulative)

From Tasks 1, 3, 4 combined:

- **C1**: Surgical fix to `mmm_whipsaw_smart.py:697-711` (Task 3) — remove `block = False` + token budget skip; preserve scalar bypasses
- **C2**: Add sealed test `test_smart_whipsaw_straddle_block_active` (Task 3)
- **C3**: Update `mmm_whipsaw_implementation.md §0 rule 6` (Task 3)
- **C4**: Update memory `feedback_straddle_gamma_bypass.md` (Task 3)
- **C5**: Implement `arbiter_tier1_action()` orchestrator — premium-aware shift, ~40 lines (Task 4)
- **C6**: Implement `arbiter_margin_recovery_action()` for Tier 1 ∩ margin RED (Task 4)
- **C7**: Wire arbiter into heartbeat between Step 5.8 and D1 (this Task)
- **C8**: Add sealed test `test_arbiter_tier1_premium_aware_shift` (Task 4)
- **C9**: Add sealed test `test_arbiter_respects_atm_shield` (Task 4)
- **C10**: Add `_signal_last_updated_ts` writes to all signal-producing modules (Task 5 will detail)
- **C11**: Decide God Layer disposition — subsume into arbiter or coordinate explicitly (this Task)
- **C12**: Add sealed test `test_arbiter_overrides_cooldown_on_breakeven_critical` (Gap #8)
- **C13**: Add sealed test `test_arbiter_overrides_reversal_block_on_breakeven_critical` (Gap #9)
- **C14**: Audit/fix outdated comment in C8 (gamma detector "observation-only" is wrong — gamma severity multiplier IS active)

---

## Verdict

The MMM heartbeat has approximately **24 distinct gates** (T0/BLOCK/MULTIPLIER/ROUTE/STATE) plus **6 multiplier composers**. Of the 24 gates, only 2 (B7 whipsaw and the multiplier in E4) are aware of breakeven zone — and B7 is unaware (today's bug). Of the 6 multiplier composers, only E4 reads breakeven zone.

**The coordination gap is structural and pervasive.** A single arbiter — running once per beat after all signals are computed, mutating exactly the `_skip_to_pnl` flag and a Tier 1 action queue — fixes 9 of the 10 surfaced gaps with one piece of code. Gap #6 (straddle whipsaw bypass) is a separate one-line fix.

The arbiter is the right structural answer. Phase 3 implementation is now well-scoped.
