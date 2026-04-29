# Combined Behavior: Profit Ratchet · Coordination Arbiter · God Layer · Smart Whipsaw

**Created**: 2026-04-28  
**Status**: Single source of truth for cross-system coordination

---

## 1. What Each System Does (One Line Each)

| System | Role | Default | Gate |
|---|---|---|---|
| **Smart Whipsaw** | Blocks adjustments when market is choppy (7 detectors, 4-mode state machine, token budget) | ON (`whipsaw_engine=SMART`) | `_skip_to_pnl=True` via block gate |
| **Coordination Arbiter** | Fires Tier 1 defensive action (shift/close/buyback) when breakeven=CRITICAL, gamma=EMERGENCY, or margin=RED | ON (`arbiter_enabled=True`) | Clears `_skip_to_pnl` on Tier 1 |
| **God Layer** | Corrects 25-min strategic drift when PNL dropped $40+ AND algo was silent 20+ min | OFF (`god_enabled=False`) | Own 45-min cooldown; respects only hard stops |
| **Profit Ratchet** | Re-anchors trigger snapshots at each P&L milestone, keeping triggers sensitive as profit accumulates | OFF (`profit_ratchet_enabled=False`) | HWM guard; skips when `_arbiter_decision_active=True` |

---

## 2. Heartbeat Execution Order (Complete)

Every `_heartbeat_inner()` runs these in this fixed order. Understanding the order is the key to understanding all cross-system behavior.

```
STEP  LINE    SYSTEM              ACTION
─────────────────────────────────────────────────────────────────────────
1     2560    Loss velocity       Writes _smart_ws_loss_velocity (feeds Smart pressure override)
2     2572    Smart Whipsaw       Evaluates early → caches self._beat_whipsaw_decision
3     2584    Safety checks       run_all_checks() → safety_events list
4     2684    _skip_to_pnl init   _skip_to_pnl = False
5     2684    Safety gate         auto_close/stop → return early; stop_adjustments → _skip_to_pnl=True
6     2780    Smart WS block gate If block_adj=True AND not dangerous_mode AND not straddle:
                                    → _skip_to_pnl=True
7     2806    Regime controls     ACTION_PAUSE / ACTION_BLOCK_ALL_SELLS → _skip_to_pnl=True
                                  GAMMA_EMERGENCY + arbiter_enabled → hands off to arbiter (no pause)
8     3063    Paused gate         If paused → _skip_to_pnl=True
9     3090    Replenish/hedge     NOT gated on _skip_to_pnl (closes, not sells)
10    3212    Cooldown gate       is_cooldown_active() → _skip_to_pnl=True
11    3256    ATM shield          Runs regardless of _skip_to_pnl (buybacks, not new sells)
12    3316    Proactive shift     Gated on NOT _skip_to_pnl
13    3322    Breakeven engine    Runs regardless. Writes _breakeven_zone, _breakeven_result.
                                  Timestamps _breakeven_zone_last_updated_at (Rule 6 stale feed)
14    3390    Gamma detector      Runs regardless. Writes _gamma_result, _gamma_regime.
                                  Timestamps _gamma_regime_last_updated_at (Rule 6 stale feed)
15    3438    Coordination        Reset _arbiter_decision_active=False
            Arbiter              evaluate(session) reads: _breakeven_zone, _gamma_regime, _margin_tier
                                  If Tier 1: set _arbiter_decision_active=True
                                             CLEAR _skip_to_pnl=False  ← Rule 2 override
                                             await _execute_arbiter_decision()
                                  If Tier 2/3: noop
16    3507    God Layer           if NOT paused AND god_enabled:
                                    check() → 25-min window + PNL drift + inactivity + evaluate_triggers()
                                    If fires: _process_adjustment() + record_correction()
17    3557    Delta Engine        Only if NOT _skip_to_pnl.
                                  If fires → sets _delta_engine_fired=True → _skip_to_pnl=True
18    3623    Profit Ratchet      Runs regardless of _skip_to_pnl.
                                  Skips if _arbiter_decision_active=True.
                                  If milestone crossed: update_trigger_snapshots() +
                                    session.pop('_smart_ws_cooldown_until', None)
19    3665    Skip-to-PNL         if _skip_to_pnl: emit heartbeat data, fall to Step 8
20    3669    ATM shield fired    if _atm_shield_fired: _skip_to_pnl=True
21    3676    Trigger eval        NOT _skip_to_pnl: evaluate_triggers() → _process_adjustment()
22    (end)   PNL update          update_peak_pnl(), _save_my_session(), record_beat()
```

---

## 3. Cross-System State Map

The 4 systems share state through session keys. This table shows who writes and who reads each key.

| Session Key | Written by | Read by | Purpose |
|---|---|---|---|
| `_skip_to_pnl` | Safety / Smart WS gate / Regime / Cooldown / ATM shield / Delta engine | Trigger eval, Delta engine, Proactive shift | Block adjustments this beat |
| `_arbiter_decision_active` | Arbiter (True on Tier 1; False at start of beat) | Ratchet gate | Signal arbiter took action; Ratchet skips |
| `_smart_ws_cooldown_until` | Smart WS engine (set on gate-block) | Smart WS engine (checked next beat) | Time-based cooldown (separate from token budget) |
| `_smart_ws_tokens` | Smart WS engine | Smart WS engine | Per-session token budget; depleted each allowed adjustment |
| `_smart_ws_loss_velocity` | Monitor (Step 1, each beat) | Smart WS `_check_pressure_override()` | Pressure-release override: bypasses block if >$50/min |
| `_breakeven_zone` | Breakeven engine | Arbiter (stale-escalated) | Zone classification: SAFE/WARNING/DANGER/CRITICAL |
| `_breakeven_result` | Breakeven engine | Arbiter + Frontend | Full dict (nearest_distance_pct, zone, band_width_pct…) |
| `_gamma_regime` | Regime module | Arbiter (stale-escalated) | Gamma regime: NORMAL/SOFT/HARD/EMERGENCY |
| `_margin_tier` | Margin guardian | Arbiter (stale-escalated) | Margin tier: GREEN/YELLOW/ORANGE/RED/CRITICAL |
| `_god` | God Layer (initialize + check + record_correction) | God Layer only | Nested: snapshot_pnl, snapshot_time, cooldown_until, total_corrections |
| `_profit_ratchet_hwm` | Ratchet | Ratchet | Highest milestone crossed (HWM guard) |
| `_profit_ratchet_count` | Ratchet | Frontend summary | Count of ratchet fires this session |
| `_arbiter_shift_bypass_cooldown` | `_arbiter_execute_defensive_shift` | `check_shift_needed()` | Bypass cooldown guard during arbiter-initiated shift |
| `_minutes_to_expiry` | Monitor | Smart WS (expiry tightening), God (warmup), Arbiter (Rule 5 cooldown) | Session DTE |
| `adjustment_history` | `_process_adjustment` | Smart WS (flip/outcome detectors), God Layer (inactivity scan) | Full history of adjustments with aggressor field |

---

## 4. Confirmed Synchronization Issues

These are **real behavioral gaps** discovered during audit. None are P0 (no money at risk), but each should be understood and optionally patched.

---

### ISSUE-1: God Layer + Ratchet Both Fire Same Beat [SEVERITY: LOW]

**Scenario**: God's 25-min window elapsed + PNL drifted $45 (threshold $40) + inactivity ≥ 20min. ALSO, this beat crosses a ratchet milestone.

**What happens**:
1. God Layer fires → calls `_process_adjustment()` → internally calls `update_trigger_snapshots()` with the hedge fill price.
2. Ratchet runs next → checks `_arbiter_decision_active` (False; God doesn't set it) → milestone condition true → calls `update_trigger_snapshots(session, ce_now, pe_now)` with current market premiums.
3. Ratchet's call **overwrites** God's fill-price snapshot.

**Impact**: Trigger snapshot anchored to market premium (`ce_now`, `pe_now`) instead of fill price. In practice these are nearly identical (fill happens at market price). Very minor numerical difference.

**Fix if desired**: In ratchet block, add `and not _god_result.get('should_correct', False)` guard. Requires threading `_god_result` out of the try/except block above it. Not worth doing unless you observe divergent fill prices.

---

### ISSUE-2: God Layer Does Not Check `_arbiter_decision_active` [SEVERITY: MEDIUM]

**Scenario**: On the same beat, Arbiter fires Tier 1 (defensive shift on CE) AND God's 25-min window has elapsed with sufficient PNL drift + inactivity.

**What happens**:
1. Arbiter fires → sets `_arbiter_decision_active=True` → executes CE defensive shift (places orders).
2. God Layer runs → does NOT check `_arbiter_decision_active` → `check()` fires → calls `_process_adjustment()` for a hedge adjustment.
3. **Two adjustments execute in the same heartbeat**: one from Arbiter, one from God.

**Risk**: Double-hedging one side. If Arbiter already shifted CE to a safer strike AND God also hedges PE with a normal adjustment, the net position may be over-hedged on one side. 

**This is not prevented anywhere in the current code.**

**Recommended fix**:
```python
# In _heartbeat_inner, before God Layer check (line ~3512):
if not self._paused and self._god and not session.get('_arbiter_decision_active', False):
    ...  # God Layer block
```

---

### ISSUE-3: Ratchet Clears Smart WS Cooldown But NOT Token Budget [SEVERITY: MEDIUM]

**Scenario**: Smart Whipsaw has been gate-blocking for 3 beats (tokens spent down to 0.5) and has set `_smart_ws_cooldown_until`. Then a profit milestone is crossed (ratchet fires).

**What Ratchet does**:
- `update_trigger_snapshots()` → snapshots re-anchored ✓
- `session.pop('_smart_ws_cooldown_until', None)` → time-based cooldown lifted ✓
- `session['_smart_ws_tokens']` → **NOT touched; remains depleted** ✗

**What happens next beat**:
- Smart WS has no time-cooldown → evaluates composite score
- Token budget check: `budget.spend(token_cost)` fails (e.g., 0.5 remaining, need 1.5)
- `block = True` → `_skip_to_pnl = True`
- Trigger evaluation skipped → the re-anchored snapshot is wasted

**Intent gap**: Ratchet's logic "profit milestone proves the move is real, not whipsaw" justifies clearing the TIME cooldown. The same logic arguably justifies restoring a partial token credit. The token budget (`_smart_ws_tokens`) is meant to cap per-session over-adjustment, but a confirmed profit milestone is evidence the algo should be allowed to trade again.

**Recommended fix** (if you want Ratchet to also free up tokens):
```python
# In ratchet block, after session.pop('_smart_ws_cooldown_until', None):
# Restore a partial token credit on milestone — market moved favorably, not a whipsaw
_ws_tokens = session.get('_smart_ws_tokens', 0.0)
_ws_max = params.get('smart_ws_tokens_per_session', 10.0)
session['_smart_ws_tokens'] = min(_ws_max, _ws_tokens + 2.0)  # partial restore
```
This is optional; the current behavior is conservative (tokens are a hard budget).

---

### ISSUE-4: God Layer's `evaluate_triggers()` Is Suppressed by Arbiter's Snapshot Reset [SEVERITY: LOW-MEDIUM]

**Scenario**: On the same beat, Arbiter fires Tier 1 (defensive shift). Arbiter's shift calls `update_trigger_snapshots()` with fill price (excess reset to 0). God Layer then evaluates.

**What happens**:
1. Arbiter executes → `update_trigger_snapshots()` → excess = 0 on both sides.
2. God Layer `check()` runs → PNL drift signal = True, inactivity signal = True.
3. God calls `evaluate_triggers(session, ce_now, pe_now)` → excess = 0 (snapshots just reset) → `OUTCOME_NONE`.
4. God concludes "no trigger firing" → takes fresh snapshot → returns NO_ACTION.

**Impact**: God Layer's correction is silently skipped on the same beat as an Arbiter action, even though PNL drifted and the algo was inactive. 

**Is it harmful?** Usually not — Arbiter already took defensive action. God's correction on the same beat would be redundant and likely over-hedge. The silent skip is actually correct behavior in this scenario.

**What's missing**: A log entry explaining why God returned NO_ACTION (snapshots just reset by Arbiter). Currently the log just shows "no trigger active, taking fresh snapshot." In debugging, this can be confusing.

**Recommended documentation fix**: No code change needed, but note in logs: if you see God "taking fresh snapshot" on the same beat as an Arbiter log, this is the cause.

---

### ISSUE-5: Normal Trigger Evaluation Runs After Arbiter Tier 1 Clears `_skip_to_pnl` [SEVERITY: MEDIUM]

**Scenario**: Arbiter fires Tier 1 (e.g., gamma emergency close on CE). Arbiter clears `_skip_to_pnl=False` per Rule 2 ("act, don't block"). After Arbiter and God both complete, the heartbeat reaches trigger evaluation (Step 6), which is gated on `not _skip_to_pnl`.

**What happens**: Since `_skip_to_pnl=False`, trigger evaluation also runs. If a trigger fires (e.g., CE premium up 12%), `_process_adjustment()` executes a normal hedge sell on CE — the same side the Arbiter just partially closed (gamma emergency close).

**Result**: On a Tier 1 beat, you can get two adjustment operations:
1. Arbiter: `gamma_emergency_close` (close 25% of CE lots)
2. Trigger: `_process_adjustment()` on CE (sell more CE lots)

These are **opposite directions**: close lots vs. sell lots. Net effect could be near-zero (close 25%, sell some back). But the exchange sees two order operations in one heartbeat.

**`_arbiter_decision_active=True` does NOT gate `_process_adjustment()`** — it only gates the Ratchet (line 3632). The flag is meant as an informational signal for downstream gates, but `evaluate_triggers()` and `_process_adjustment()` don't check it.

**Recommended fix** (if you want to prevent dual-adjustments on Tier 1 beats):
```python
# In trigger evaluation block (line ~3676):
if not _skip_to_pnl and not session.get('_arbiter_decision_active', False):
    trigger_result = evaluate_triggers(session, ce_now, pe_now)
    ...
```
However, this may be intentional design — Arbiter Rule 2 says "act, don't block." The Arbiter action and the trigger adjustment could be on different sides and complementary. **Discuss with operator before patching.**

---

## 5. What Works Correctly (Validated)

### 5.1 Ratchet ↔ Arbiter: Gate Is Correct
`not session.get('_arbiter_decision_active', False)` prevents the Ratchet from overwriting trigger snapshots when Arbiter already reset them with the fill price. Works as designed.

### 5.2 Arbiter ↔ Smart Whipsaw: Rule 2 Override Works
Smart WS LOCKDOWN sets `_skip_to_pnl=True` at line 2804. Arbiter at line 3485 clears it with `_skip_to_pnl=False`. This is the documented Rule 2 behavior: Tier 1 overrides all upstream blocks. Trigger evaluation then runs normally.

### 5.3 Smart Whipsaw ↔ Pressure Override: Works
When `_margin_tier=ORANGE/RED` or `_smart_ws_loss_velocity > 50`, `_check_pressure_override()` returns True → Smart WS forces mode=NORMAL regardless of composite score. This prevents Smart WS from blocking adjustments during margin emergencies (which would make them worse).

### 5.4 God Layer ↔ Hard Stops: Works
God respects: PAUSED, regime=ACTION_FORCE_REDUCE, regime=ACTION_PAUSE, `_margin_wind_down`, `_stale_abort_gen`, `_straddle_roll_in_progress`. God's `_hard_stops_active()` covers all real financial emergencies where adding sells makes things worse.

### 5.5 God Layer Self-Protection: Works
God skips `GOD_CORRECTION`-tagged entries in `_minutes_since_last_adjustment()` — so its own corrections don't reset the inactivity clock. After firing, 45-min cooldown prevents re-entry regardless of PNL drift.

### 5.6 Arbiter Rule 5 (Last 30 Min): Works
Arbiter returns noop if `_minutes_to_expiry <= 30`. This prevents forced defensive actions near expiry when gamma-driven repositioning looks dangerous but isn't.

### 5.7 Ratchet ↔ Smart Whipsaw Cooldown: Partial (see Issue-3)
Ratchet clears `_smart_ws_cooldown_until` (time-based cooldown). Token budget is not restored. Time cooldown lift is correct; token non-restore is debatable.

### 5.8 STRADDLE_WITH_ADJUSTMENT: Bypass Rules Work
Smart WS: `trigger_widen_factor=1.0` and `lot_scalar=1.0` bypassed; `block` and token budget remain active (Phase 3 refinement).  
Arbiter: gamma emergency returns noop for this strategy (ATM gamma is structural, not dangerous).  
God Layer: runs normally (no strategy exemption needed — God only fires when algo was inactive).

### 5.9 Arbiter Stale Escalation: Works
When `_breakeven_zone` is older than 1.5× beat interval, arbiter escalates it one tier (DANGER → CRITICAL). This prevents missed Tier 1 actions when the breakeven engine had a slow beat. The timestamps (`_breakeven_zone_last_updated_at`, `_gamma_regime_last_updated_at`, `_margin_tier_last_updated_at`) are written by the monitor at steps 13–14 above.

---

## 6. Param Interaction Table

The four systems expose configurable params. These are the ones that interact across systems:

| Param | System | Cross-System Impact |
|---|---|---|
| `profit_ratchet_enabled` | Ratchet | Also clears `_smart_ws_cooldown_until` when milestone fires |
| `profit_ratchet_step_usd` | Ratchet | Larger step = fewer ratchet fires = less Smart WS cooldown clearing |
| `arbiter_enabled` | Arbiter | When False: Ratchet gate never triggers (`_arbiter_decision_active` always False); God has no competition |
| `smart_ws_score_lockdown` | Smart WS | Higher = harder to lock; reduces frequency of Arbiter override needing to clear `_skip_to_pnl` |
| `smart_ws_tokens_per_session` | Smart WS | More tokens = Smart WS blocks less = Arbiter override less needed; Ratchet token gap (Issue-3) matters more with low token count |
| `smart_ws_cooldown_base_beats` | Smart WS | Determines how long after a gate-block before Ratchet can re-enable the next beat |
| `god_enabled` | God Layer | When True: potential double-adjustment on Arbiter Tier 1 beats (Issue-2) |
| `god_pnl_threshold` | God Layer | Higher = God fires less = less double-adjustment risk with Arbiter |
| `god_cooldown_min` | God Layer | 45 min default; ensures God doesn't compound with back-to-back Arbiter actions |
| `adjustment_interval` | All | Beat period drives Smart WS gate cooldown, Arbiter stale-age tolerance (1.5×), God's 25-min window |

---

## 7. Decision Matrix: What Fires When

| Market Condition | Smart WS | Arbiter | God | Ratchet |
|---|---|---|---|---|
| Quiet session, P&L growing | NORMAL mode, no block | Tier 3 noop | Snapshot only (no drift) | Fires at milestones |
| Choppy market, P&L flat | DEFENSIVE/OBSERVE/LOCKDOWN → blocks | Tier 2 noop (modules work) | No drift signal | No milestone → no fire |
| Breakeven CRITICAL | May block (if choppy) | Tier 1 → defensive shift → CLEARS block | Snapshot, may not fire (see Issue-4) | Skips (arbiter active) |
| Gamma EMERGENCY (non-straddle) | May block | Tier 1 → gamma close → CLEARS block | Usually suppressed (see Issue-4) | Skips (arbiter active) |
| Margin RED | Pressure override → NORMAL mode | Tier 1 → margin recovery | No P&L drift signal typically | Skips (arbiter active) |
| 25-min drift + algo inactive | May block | Tier 2/3 noop | Fires → _process_adjustment | Independently fires if milestone |
| 25-min drift + Arbiter fires | May block | Tier 1 → clears block | Also fires (Issue-2: double adj) | Skips (arbiter active) |
| Last 30 min before expiry | Tightened thresholds | Tier 1 disabled (Rule 5) | No cooldown restriction | Fires if milestone |

---

## 8. Debugging Guide

### Ratchet Fires But Smart Whipsaw Immediately Blocks Next Beat

**Cause**: Token budget (`_smart_ws_tokens`) was depleted before the milestone. Ratchet cleared time-cooldown but not tokens. See Issue-3.

**Check**: Look for `_smart_ws_tokens` in session state. If ≤ token_cost threshold, tokens are the block.

**Resolution**: Wait for token refresh (`smart_ws_token_refresh_per_hour` param drips tokens back). Or reduce `smart_ws_score_lockdown` to avoid hitting LOCKDOWN/OBSERVE modes that spend tokens faster.

---

### Arbiter Fires But No Orders Appear

**Cause A**: `arbiter_enabled=True` but `arbiter_live_execution` flag: arbiter is always live (no shadow mode per user directive 2026-04-28). If no orders, check `_execute_arbiter_decision` logs.

**Cause B**: `_arbiter_execute_defensive_shift` could not find a valid strike at target premium ± tolerance. Check `shift_target_premium` and `shift_premium_tolerance` params.

**Cause C**: Rule 5 active: `_minutes_to_expiry <= 30` → Arbiter returns noop. Check the `arbiter_last_decision.trigger` field for `'last_30_min_cooldown'`.

**Cause D**: Warmup: `adjustment_count=0` and breakeven_zone timestamp missing → arbiter returns noop. Normal on session start; resolves after first beat.

---

### God Layer Never Fires Even With Large P&L Drop

**Check order**: (1) `god_enabled=True` in params? Default is False. (2) Session paused? God skips when paused. (3) 25-min window elapsed? Check `session._god.snapshot_time`. (4) PNL drifted enough? `current_pnl - snapshot_pnl < -god_pnl_threshold`. (5) Algo inactive? `adjustment_history` — last non-GOD entry must be ≥ `god_min_silence_min` minutes ago. (6) Trigger actually firing? God calls `evaluate_triggers()` itself — if snapshots were recently reset (by Arbiter or Ratchet), excess=0, God returns NO_ACTION (Issue-4).

---

### Two Adjustments on Same Beat (Unexpected Lot Count)

**Cause**: Arbiter Tier 1 cleared `_skip_to_pnl`, then trigger evaluation also fired. Check activity log for same beat with both `arbiter_tier1` and `adjustments_stopped`-cleared events. See Issue-5.

**Resolution**: No automatic fix. If you want to prevent it, add `_arbiter_decision_active` gate on trigger evaluation (Issue-5 recommended fix).

---

### Smart Whipsaw LOCKDOWN But Arbiter Still Firing

**This is correct**: Arbiter Rule 2 explicitly overrides `_skip_to_pnl`. Smart WS LOCKDOWN + Arbiter Tier 1 can coexist. The Arbiter's defensive action has higher priority than the whipsaw block.

---

## 9. Session State Fields (All Four Systems)

```
Profit Ratchet:
  _profit_ratchet_hwm          float   Highest milestone crossed (0.0 if never fired)
  _profit_ratchet_count        int     Times ratchet fired this session
  _profit_ratchet_last_pnl     float   PNL at last milestone

Coordination Arbiter:
  _arbiter_decision_active     bool    True only during the beat Arbiter Tier 1 fired
  _arbiter_active_action       str     e.g. 'defensive_shift', 'gamma_emergency_close'
  _arbiter_active_side         str     'ce' or 'pe'
  _arbiter_last_decision       dict    Full audit dict of last evaluate() result
  _arbiter_shift_bypass_cooldown bool  Set during defensive shift exec; gates cooldown check

God Layer:
  _god.snapshot_pnl            float   PNL at last 25-min snapshot
  _god.snapshot_time           str     ISO timestamp of last snapshot
  _god.last_fired              str     ISO timestamp of last correction
  _god.cooldown_until          str     ISO timestamp of cooldown expiry
  _god.total_corrections       int     Total corrections this session
  _god.last_correction_detail  dict    Audit detail of last correction

Smart Whipsaw:
  _smart_ws_score              float   Composite score (0=calm, 1=extreme chop)
  _smart_ws_mode               str     NORMAL / DEFENSIVE / OBSERVE / LOCKDOWN
  _smart_ws_tokens             float   Remaining token budget (depletes per adjustment)
  _smart_ws_cooldown_until     str     ISO timestamp of time-based cooldown expiry
  _smart_ws_loss_velocity      float   $ loss/min computed by monitor each beat
  _smart_ws_pnl_prev           float   PNL from previous beat (for velocity)
  _smart_ws_flip_count_30m     int     Approximate flip count in 30-min window
  _smart_ws_late_session       bool    True if in last-3hr window (weights adjusted)
  _smart_ws_last_decision      dict    Full decision dict from last evaluate()
```

---

## 10. File Map

| File | Role |
|---|---|
| `mmm_monitor.py` | Heartbeat orchestrator. Executes all 4 systems in the fixed order above. |
| `mmm_whipsaw_smart.py` | `SmartWhipsawEngine.evaluate()` — 7 detectors, composite, 4-mode, 5-gate, token budget |
| `mmm_arbiter.py` | `CoordinationArbiter.evaluate()` — stale-aware signal reader, 3 Tier 1 action types |
| `mmm_god_layer.py` | `StrategicIntegrityMonitor.check()` — 25-min drift correction engine |
| `mmm_monitor.py` (line 3623) | Profit Ratchet inline block — no separate module |
| `mmm_trigger.py` | `evaluate_triggers()`, `update_trigger_snapshots()` — used by Ratchet and God Layer |

---

## 11. Invariants That Must Never Break

1. **Ratchet never places orders** — `update_trigger_snapshots()` is pure in-memory. Safe to run outside `_skip_to_pnl` gate.

2. **Ratchet gate respects `_arbiter_decision_active`** — must remain at line 3632 to prevent snapshot overwrite during arbiter execution.

3. **Arbiter Rule 5 (last 30 min)** — must remain. Near-expiry defensive shifts are dangerous; gamma-driven repositioning looks like CRITICAL but is structural.

4. **God Layer hard stops** — `_hard_stops_active()` must always return True for: margin wind_down, FORCE_REDUCE, ACTION_PAUSE, stale monitor, straddle roll. God must never add sells during these states.

5. **Smart Whipsaw STRADDLE bypass** — `trigger_widen_factor=1.0`, `lot_scalar=1.0` forced for STRADDLE_WITH_ADJUSTMENT. LOCKDOWN/OBSERVE block still applies. Never revert to full bypass (the user directive is documented in mmm_whipsaw_smart.py:697).

6. **Arbiter is a no-op at Tier 2/3** — operational modules run as designed. Arbiter must never inject any state modification when its evaluation returns Tier 2 or Tier 3.

7. **`_skip_to_pnl` cleared by Arbiter Tier 1 only** — no other system should clear it. God Layer bypasses it entirely (doesn't read it). Ratchet ignores it. Only Arbiter uses the clear as Rule 2 override.

---

## 12. Known Gap Summary (Rapid Reference)

| Gap | Severity | Risk | Auto-fix? |
|---|---|---|---|
| ISSUE-1: God + Ratchet overwrite snapshots same beat | LOW | Minor snapshot numerical delta | No; not worth fixing |
| ISSUE-2: God doesn't check `_arbiter_decision_active` | MEDIUM | Double-adjustment on rare beats | Recommended: add gate before God block |
| ISSUE-3: Ratchet clears time-cooldown but not tokens | MEDIUM | Re-anchor useless if tokens exhausted | Optional: partial token restore on milestone |
| ISSUE-4: God's trigger eval suppressed by Arbiter snapshot reset | LOW-MEDIUM | God correction silently skipped (acceptable on Arbiter beats) | No; add log note only |
| ISSUE-5: Trigger eval runs after Arbiter Tier 1 | MEDIUM | Potential double adjustment (arbiter action + trigger) | Optional: gate trigger eval on `not _arbiter_decision_active` |
