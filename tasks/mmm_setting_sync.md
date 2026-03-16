# MMM Settings Sync — Unified Safety Parameter Architecture
> **Purpose:** Deep analysis of parameter conflicts, redundancies, and missing coordination across all MMM safety mechanisms. Proposes a coherent "Unified Risk Framework" so every parameter knows what the others are doing.
> **Author:** Claude (via deep codebase audit)
> **Date:** March 15, 2026
> **Action required:** Read, validate, then decide implementation approach.

---

## 1. The Core Problem — What Is Actually Broken

The MMM algo has been built incrementally: each safety feature was added when a specific pain point was felt. The result is **15+ independent safety modules**, each with its own parameters, thresholds, and action logic — all running in the same heartbeat loop with no shared awareness of each other.

The specific failures:

| Failure Type | What It Looks Like |
|---|---|
| **Same job, multiple owners** | Wind-down can be triggered by Trend Tier 4, Vol Regime HIGH, Margin Guardian ORANGE, `wind_down_on_atm`, and `close_at_atm` — 5 independent paths into the same action |
| **Amplifiers and blockers run in the wrong order** | Whipsaw RESTRICT halves lots, but Breakeven Engine then multiplies by 3.0× — net effect is 1.5× more lots than formula intended |
| **Defaults disconnected from position size** | `max_loss_amount` defaults to $5,000 regardless of whether you have 1 lot or 100 lots at $500 premium — these are completely different risk profiles |
| **Dead zones between thresholds** | `close_at_threshold=5`, `harvest_profit_pct=40%` (cuts at $60 for $100-entry), `shift_threshold=50` — positions between $5 and $50 accumulate in frozen state with no cleanup mechanism unless wind-down activates |
| **Parallel "block sells" with no authority chain** | 8+ mechanisms can independently block sells. When two fire at once, the logs contradict and UI is confused |
| **Parameters designed in isolation** | `whipsaw_window_mins=30` makes no sense without knowing `adjustment_interval`. At 60s heartbeats, 30 min = 30 intervals. At 300s heartbeats, 30 min = 6 intervals. Sensitivity is wildly different |
| **ATM Shield sells INTO margin stress** | ATM Shield is gated "not RED or CRITICAL" — meaning it fires at YELLOW and ORANGE, selling MORE lots when margin utilization is already above 60% |
| **Regime master switch hides critical subsystems** | `regime_enabled=False` (the default) silently disables vol filter, gamma cap, AND trend guard all together. Users enabling regime think they're turning on extra safety but are actually turning on all three simultaneously with no warmup |

---

## 2. Complete Safety Mechanism Inventory

Every module, what it does, what triggers it, what it outputs.

### 2A. Hard Loss Limits (Capital Protection)

| Mechanism | Key Params | Trigger | Action | Problem |
|---|---|---|---|---|
| **Max Loss Hard Stop** | `max_loss_amount=5000` | total P&L < -N | Close ALL positions, stop session | Default $5000 ignores position size |
| **Trailing Stop** | `trailing_stop_pct=0` (off) | P&L drawdown from peak > N% | Close ALL | Off by default; peak decay logic is subtle |
| **Global Max Loss** | `global_max_loss=50000` | Sum of ALL active session P&L < -N | Block new sessions | Separate from per-session max_loss |
| **P&L Guardrail** | Hard-coded tiers in mmm_safety.py | Session P&L at warning/pause/stop thresholds | Graduated: warn → pause → stop | Thresholds not user-configurable — buried in code |

### 2B. Position Size Controls

| Mechanism | Key Params | Trigger | Action | Problem |
|---|---|---|---|---|
| **Active Lot Cap** | `max_lots_per_side=100` | active_lots >= cap | Stop adjustments on that side; trigger M2 | Only applies to active lots (Split Ledger) |
| **Total Exposure Ceiling** | `max_total_exposure=0 (auto: 2×cap)` | active+frozen >= ceiling | Warn (NOT stop) | Does NOT trigger M2; only warns |
| **Lot Velocity Limiter** | `lot_velocity_limit=30`, `lot_velocity_window_mins=30` | lots added in window > limit | Block new lot additions | Window doesn't scale with `adjustment_interval` |
| **Asymmetry 3-tier** | `asymmetry_5to1_lot_reduction=0.5`, `asymmetry_7to1_hard_block=True` | CE:PE ratio exceeds N | 50% reduction at 5:1; hard block at 7:1 | Uses total_lots (including frozen) — correct |
| **Consecutive Direction Limiter** | `consecutive_dir_limit=3`, `consecutive_dir_lot_cap_pct=0.25`, `consecutive_dir_block_after=5` | N consecutive same-dir adjustments | Cap lots at 25% of initial; block at 5 | Independent from whipsaw; similar goal |
| **M2 Lot Recycling** | `recycle_min_premium_ratio=2.5`, `recycle_*` | Position cap reached | Buyback frozen + resell at better strike | Only triggers on "Position cap reached" string — fragile |

### 2C. Lot Sizing Multipliers (SELL MORE)

| Mechanism | Key Params | Trigger | Action | Problem |
|---|---|---|---|---|
| **Breakeven Engine** | `breakeven_aggression_max=3.0`, zone thresholds | Spot near portfolio breakeven | Multiply hedge lots by up to 3.0× | Combines with gamma-aware multiplier poorly |
| **Gamma-Aware Multiplier** | `gamma_aware_max_multiplier=1.3` | Premium has spiked aggressively (high gamma) | Multiply lots by up to 1.3× | Applied before or after breakeven? Order unclear |
| **Trend Boost** | `trend_boost_tier1_mult=1.3`, `tier2_mult=1.5`, `tier3_mult=2.0` | Trend tier active | Boost SAFE-side lots by multiplier | Off by default; independent of combined cap |
| **Combined Cap** | `max_combined_lot_multiplier=3.0` | All multipliers combined | Cap total multiplication at 3.0× | Does NOT include trend boost (a bug) |

### 2D. Lot Sizing Reducers (SELL LESS)

| Mechanism | Key Params | Trigger | Action | Problem |
|---|---|---|---|---|
| **Whipsaw RESTRICT** | `whipsaw_restrict_score=3` | Whipsaw score ≥ 3 | Halve lots + widen triggers +100% | RESTRICT fires but multipliers still apply after |
| **Trend Tier 1** | `trend_tier1_lot_reduction=0.30` | BTC moved 0.5% from anchor | Reduce lots by 30% | Only fires if `regime_enabled=True` (off by default) |
| **Asymmetry lot reduction** | `asymmetry_5to1_lot_reduction=0.5` | CE:PE ratio > 5:1 | Apply 50% lot multiplier | Independent from trend lot reduction |
| **ATM Shield lot scaling** | `strike_shift_otm_tier1/2/3` | Strike is shifting OTM | Reduce lots at closer OTM distances | Only when `strike_shift_use_lot_scaling=True` (off by default) |

### 2E. Sell Block Mechanisms

| Mechanism | Trigger | Blocks | Priority |
|---|---|---|---|
| Trend Tier 3 `BLOCK_ALL_SELLS` | BTC moved 1.5% from anchor | All new sells | Unknown |
| Trend Tier 2 `BLOCK_CE/PE_SELLS` | BTC moved 1.0% from anchor | Aggressor-side sells | Unknown |
| Margin Guardian YELLOW | Margin util ≥ 60% | New sells | Unknown |
| Vol Regime HIGH | IV spike + RV composite > 1.0 | New sells (`block_sells` action) | Unknown |
| Gamma Cap HARD | Dollar gamma ≥ `gamma_hard_limit` | New sells | Unknown |
| Whipsaw COOLDOWN | Whipsaw score ≥ 4 | Skip entire interval | Unknown |
| Position Cap | active_lots ≥ max_lots | Hedge-side sells | Known: triggers M2 |
| Asymmetry 7:1 hard block | CE:PE ratio > 7 | All sells | Unknown |
| Consecutive dir block | 5+ same-direction adjustments | All sells | Unknown |

**Critical finding:** None of these 9 block mechanisms communicate with each other. The monitor processes them sequentially. If 3 fire simultaneously, there are 3 different log entries and potentially contradictory UI state updates.

### 2F. Close/Buyback Mechanisms

| Mechanism | Threshold | Scope | Runs When |
|---|---|---|---|
| Close-at-5 | `close_at_threshold=5` | All positions | Every heartbeat (Step 3) |
| Close-at-5 Watcher | Same threshold, `close_at_watch_interval=30s` | All positions | Continuously between heartbeats |
| M1 Harvest | profit ≥ 40%, age ≥ 30min | Frozen positions only | Step 3a, after close-at-5 |
| ATM Shield | spot within 0.5% of strike | Active positions (endangered side) | Step 5.5, before trigger eval |
| Wind-Down Buyback | `wind_down_close_threshold=20` | LIFO order | When wind-down active |
| Margin Guardian ORANGE/RED | Exchange margin | Emergency reduce | Every beat if margin stressed |
| Max Loss Close-All | `max_loss_amount` | All positions | Safety check, every beat |
| M2 Recycle Phase A | `recycle_premium_ceiling=50` | Cheapest frozen | When cap hit |
| Shift-Time Recycle | `shift_recycle_premium_floor=60` | Frozen below floor | At each strike shift |

**Critical finding:** A single frozen position can be targeted by 6+ independent close mechanisms, with no coordination on which one "claims" it. The first to win owns the fill; others may try and fail silently.

### 2G. Wind-Down Trigger Paths

Five completely independent paths into the same wind-down behavior:

1. `wind_down_enabled=True` + `wind_down_hours_before_expiry=2.0` → time-based activation
2. `wind_down_on_atm=True` → when original strike goes ATM (spot within 0.5%)
3. Trend Tier 4 (`trend_tier4_pct=2.0%`) → `_trend_wind_down_triggered=True`
4. Vol Regime HIGH with `vol_regime_action='wind_down'` → `_vol_wind_down_triggered=True`
5. Margin Guardian ORANGE → aggressive buyback (functionally identical to wind-down)

None of these set a shared flag. Each uses its own session key. The monitor has to check all 5 independently every beat.

---

## 3. Specific Contradictions Found

### Contradiction 1: ATM Shield vs. Margin Guardian

**Scenario:** Margin utilization = 65% (YELLOW tier — "block new sells"). ATM Shield fires (spot within 0.5% of active CE strike).

**What happens today:** ATM Shield gate checks for "not RED or CRITICAL" → passes at YELLOW. ATM Shield closes CE positions AND re-sells MORE lots at new strike. This adds margin consumption **when margin is already stressed**.

**What should happen:** ATM Shield should check if margin guardian allows new sells. At YELLOW, the correct behavior is: close the endangered side (good, reduces margin), but do NOT re-sell new lots (bad, increases margin) until margin recovers to GREEN.

**The fix needed:** ATM Shield re-sell step must respect margin tier. At YELLOW: close only, no re-open. At GREEN: full close + reopen.

---

### Contradiction 2: Trend Boost vs. Whipsaw RESTRICT

**Scenario:** Market is choppy → Whipsaw RESTRICT fires (halve lots). Simultaneously, BTC has drifted 0.8% in one direction → Trend Tier 2 fires. If `trend_boost_enabled=True`, Tier 2 applies 1.5× boost to safe-side lots.

**What happens today:**
- Lots formula calculates N lots
- Whipsaw RESTRICT: N → N/2 (halve)
- Then Trend Boost Tier 2: N/2 × 1.5 = 0.75N
- Then `max_combined_lot_multiplier` check: only covers breakeven × gamma (not trend boost)
- Final result: 0.75N — slightly less than formula but not the intended "half"

**What should happen:** In a RESTRICT scenario, lot reduction should be the FINAL word. No multiplier should be able to undo a RESTRICT reduction. RESTRICT exists precisely because the market is dangerous.

---

### Contradiction 3: Breakeven Aggression vs. Lot Velocity Limiter

**Scenario:** Session has been running 25 minutes. Lot velocity used 25 of 30 allowed lots in the window. Spot approaches breakeven → Breakeven Engine fires 2.5× multiplier.

**What happens today:** Engine calculates 10 lots needed → 2.5× = 25 lots. Lot velocity limiter: 5 remaining in window → blocks to 5 lots.

**Result:** Breakeven engine told the user "we're defending hard" but actually only placed 5 lots. The UI shows aggressive multiplier but the execution was heavily throttled. No log entry says "breakeven aggression was velocity-limited."

**The fix needed:** Velocity limiter should report the constraint so breakeven engine knows its aggressive order was not filled. The user needs to see this in the UI.

---

### Contradiction 4: `harvest_pressure_threshold` with Split Ledger

**Scenario with Split Ledger:** `max_lots_per_side=100`. Active lots CE = 40, Frozen lots CE = 80.
- Capacity pressure = active_lots / max_lots = 40/100 = **40%** → Below harvest threshold (50%) → Harvest does NOT fire
- But total exposure = 120 lots → Frozen keep accumulating

**What should happen:** Harvest pressure should consider `total_lots / max_total_exposure` as well as `active_lots / max_lots_per_side`. With 120 lots against a 200-lot ceiling, total pressure = 60% — above the harvest threshold.

**Today:** The harvest sees low active pressure and lets frozen accumulate indefinitely despite high total exposure.

---

### Contradiction 5: `shift_threshold` vs. `recycle_premium_ceiling` vs. `close_at_threshold`

The three thresholds create a dead zone:

```
$0 ──────── $5 ──────── $50 ──────── $60 ──────── $100+
       close_at    shift_threshold  recycle_ceiling  shift_target
         ↑                                ↑
         Close                       Recycle (buyback to free lots)
```

**Dead zone $5–$50:** A frozen position with current premium between $5 and $50:
- NOT closed by close-at-5 (premium > $5)
- NOT eligible for M2 recycle buyback (premium > $50)
- NOT harvested by M1 if profit < 40% (e.g., entry at $100, current $70 = only 30% profit)
- NOT shifted (frozen positions don't shift)
- NOT wind-down-closed (unless wind-down threshold configured above $50)

These positions just sit there consuming exposure capacity forever until they naturally decay below $5 or wind-down activates.

---

### Contradiction 6: `min_trigger_move` interpretation inconsistency

**In code** (`mmm_monitor.py`): `ce_threshold = trigger_snapshot × (min_trigger_move / 100)` → treated as a **percentage** (e.g., 20 = 20% of trigger snapshot premium).

**In DEFAULT_PARAMS**: `'min_trigger_move': 10.0` — which in % terms means "don't trigger unless premium has risen 10% above snapshot."

**In UI Settings dialog** (screenshot): Shows label "Minimum % premium move above trigger to fire adjustment" with value 20 and "Range: 0.1 - 100."

**The problem:** If a user has `trigger_snapshot = $50` (a low-premium position), then 20% threshold = $10 move required. For a `trigger_snapshot = $500` (high-premium), 20% = $100 move required. The parameter is percentage-relative, which is good. But its interaction with `adjustment_interval` (how often you check) and `adaptive_interval` (which shortens check interval when close to trigger) is not coherent: at high proximity, the adaptive interval fires every 60s. You'd trigger frequently. At low proximity with 1200s interval, you might miss the trigger entirely if premium spikes and recovers in one beat.

---

### Contradiction 7: Vol Regime vs. Gamma Cap — both measure "dangerous volatility" differently

**Vol Regime:** Measures IV change rate + realized volatility. Fires when IV spikes 30% OR RV > 80% annualized. Uses ring buffer of historical beats.

**Gamma Cap:** Measures dollar-gamma of current portfolio. Fires when `|Γ_portfolio| × S² × 0.01 > soft_limit`. More lots → higher gamma → more likely to fire.

**The gap:** A portfolio can have HIGH gamma (lots of ATM exposure) with LOW vol (market is calm). Both measures can be simultaneously:
- Vol: NORMAL (IV hasn't spiked)
- Gamma: HARD (you have too many lots near ATM)

In this case, gamma cap blocks sells but vol regime does not. Gamma cap doesn't trigger wind-down. Vol regime, if in HIGH state, could trigger wind-down. But they're completely unaware of each other.

**A coherent system** would say: "If vol is HIGH AND gamma is HARD simultaneously, the risk is multiplicative — we need EMERGENCY action, not just the sum of independent actions."

---

### Contradiction 8: Trend Tier Plateau Reset vs. Retracement Reset — conflicting defaults

From `lessons.md`: The trend engine got stuck at Tier 3 for 3 days because:
- Retracement required: 30% (`trend_retrace_pct=30`)
- Reset beats required: 5 (`trend_reset_beats=5`)
- Plateau reset: 20 beats (`trend_plateau_reset_beats=20`) — added as a fix

**The interaction:** At 300s interval, 20 beats = 100 minutes. At 60s adaptive interval (triggered by proximity), 20 beats = 20 minutes. The plateau reset duration is beat-counted but beats vary in length. The same 20-beat requirement means very different real time depending on market conditions.

---

### Contradiction 9: `recycle_min_premium_ratio` vs. `shift_target_premium` — no connection

**Recycle** requires: `new_premium / avg_recycle_premium >= 2.5`. This measures "how much better is the new strike vs. the frozen positions."

**Shift target premium**: `shift_target_premium=100`. This is the ideal premium for a new strike after shift.

If current market has low premiums (BTC quiet, options cheap), a shift might find a new strike at only $40. Recycle ratio = 40 / 25 (average frozen at $25) = 1.6× → below 2.5 → recycle fails. System is stuck: can't recycle because premium ratio too low, can't add lots because at cap.

But `shift_target_premium=100` vs. actual market $40 means the shift engine is also struggling. These two parameters should be AWARE of each other: when market premiums are compressed, both the recycle threshold and shift target should adjust, or at least warn that they're in conflict.

---

## 4. The Missing Concepts

Beyond specific contradictions, the system is missing three fundamental concepts that a professional risk system would have:

### Missing Concept 1: A Unified Session Risk Score

Every safety module computes its own severity internally. There is no single "session risk level" shared across modules. This leads to:
- Module A doesn't know Module B has already escalated
- Multiple modules fire the same log messages
- The UI shows 5 different risk indicators with no relationship to each other

**What's needed:** A single `session['_risk_level']` enum: `LOW / MODERATE / ELEVATED / HIGH / CRITICAL`. All modules READ this before deciding their own action. All modules WRITE to it (escalate only, never de-escalate without consensus).

### Missing Concept 2: Position-Size-Relative Parameters

Almost every threshold is expressed in absolute numbers, but position size and premium level determine what's "dangerous." Examples:

| Parameter | Default | Should Be |
|---|---|---|
| `max_loss_amount` | $5,000 flat | ~50% of total premium collected at entry |
| `max_lots_per_side` | 100 absolute | ~10× `initial_lots` |
| `max_total_exposure` | 200 absolute | ~15× `initial_lots` |
| `lot_velocity_limit` | 30 lots/30min | ~3× `initial_lots` per 30min |
| `recycle_min_lot_gain` | 5 lots absolute | ~50% of initial_lots |

When `initial_lots=1`, these defaults are comically large (you'd never hit 100 lot cap). When `initial_lots=50`, they may be too loose. The parameters need to be **referenced to initial_lots and premium at entry.**

### Missing Concept 3: A Parameter Coherence Check at Session Start

Currently, `_interdependency_checks()` in `mmm_config.py` validates a few obvious relationships on hot-reload. But it doesn't check:
- Whether the selected parameters are coherent AS A SYSTEM for the current market conditions
- Whether enabled features have conflicting behaviors
- Whether disabled features leave gaps in protection

**What's needed:** At session start AND on every hot-reload, run a "coherence audit" that outputs a `_param_health` score and specific warnings like: "ATM Shield is enabled but Margin Guardian is disabled — ATM Shield may sell into margin stress unsafely."

---

## 5. Proposed Architecture: The Unified Risk Framework

This section proposes HOW to fix the coordination failures. The approach is additive — no existing code is changed, just new coordination layers are added.

### 5.1 The Session Risk Level (SRL)

A single session field `session['_srl']` with values: `0=LOW`, `1=MODERATE`, `2=ELEVATED`, `3=HIGH`, `4=CRITICAL`.

**How it's computed:**

```
Each module contributes a "vote":
  Margin Guardian:  GREEN=0, YELLOW=1, ORANGE=2, RED=3, CRITICAL=4
  Vol Regime:       NORMAL=0, ELEVATED=1, HIGH=3
  Gamma Cap:        NORMAL=0, SOFT=1, HARD=2, EMERGENCY=4
  Trend Guard:      Tier 0=0, Tier 1=1, Tier 2=2, Tier 3=3, Tier 4=4
  Whipsaw:          NORMAL=0, CAUTION=1, RESTRICT=2, COOLDOWN=3
  Drawdown:         <50% max_loss=0, <80%=1, <100%=2, >100%=4

SRL = max(all votes)   [not sum — we don't want additive panic]
```

**What each SRL level means to ALL modules:**

| SRL | Regime | Lot Sizing | Multipliers | Buyback Aggressiveness |
|---|---|---|---|---|
| 0 LOW | Normal | Full formula | All multipliers permitted | Normal close-at-5 |
| 1 MODERATE | Monitor | Full formula | Capped at 1.5× combined | Close-at-5 + harvest active |
| 2 ELEVATED | Alert | -20% lots | Capped at 1.0× (no amplification) | Wind-down thresholds lower |
| 3 HIGH | Warning | -50% lots | 0.5× (actually hedge LESS, preserve capital) | Aggressive harvest + recycle |
| 4 CRITICAL | Block all sells | 0 new lots | N/A | Emergency reduce |

### 5.2 Parameter Sync Groups

Group parameters by the relationship they should maintain:

**Group A: The Premium Ladder** (close → harvest → recycle → shift → target)
```
Rule: close_at_threshold < harvest_entry_threshold < recycle_premium_ceiling < shift_threshold < shift_target_premium

Current defaults: 5 < [40% of entry → variable] < 50 < 50 < 100
Problem: recycle_ceiling ≤ shift_threshold creates a conflict (recycle tries to buy back positions that are still above shift threshold → it won't buy them, but shift won't take them either)

Proposed fixed relationship:
  close_at_threshold = C (user sets: 5)
  harvest_threshold = C × 10 (= 50 at default → positions at 50 or above, if 40% profit, harvest)
  recycle_premium_ceiling = shift_threshold × 0.8 (= 40 if shift_threshold=50)
  shift_threshold = [user sets: 50]
  shift_target_premium = shift_threshold × 2 (= 100 → natural)

With this: a frozen position at $45 is below recycle_ceiling ($40) only if shift is at $50. That's still a problem. Let me reconsider:

Better: recycle_premium_ceiling should be LESS than shift_threshold, so frozen positions eligible for recycle are those that are truly cheap (decayed well below the minimum we'd sell at a new strike).
  recycle_premium_ceiling = shift_threshold × 0.6 (= 30 if shift=50)

Then the dead zone becomes:
  $5 → close-at-5
  $5-$30 → dead zone (could add a "cheap position accumulation harvest" here)
  $30-$50 → M1 harvest eligible (if profit ≥ 40%)
  $50+ → too expensive to harvest, just carry to expiry or wait for close-at-5
```

**Group B: The Time Ladder** (close → stop adjustments → wind-down → expiry)
```
Rule: auto_close_mins < stop_adjustment_mins < wind_down_hours_before_expiry × 60

Current defaults: 5 < 15 < 120 → correctly ordered
Already validated in _interdependency_checks()

Missing validation:
  close_at_watch_hours_before_expiry > wind_down_hours_before_expiry?
  → close-at-5 watcher should become MORE active during wind-down, not less

  If close_at_watch_hours_before_expiry < wind_down_hours_before_expiry, the watcher activates AFTER wind-down ends → gap

Proposed rule: close_at_watch_hours_before_expiry >= wind_down_hours_before_expiry
  AND close_at_watch_near_expiry_interval < close_at_watch_interval
```

**Group C: The Margin Tier Ladder** (already validated, but missing one rule)
```
Existing: green < yellow < orange < red < critical (validated ✓)
Missing: margin_target_pct < margin_green_pct
  → You can't target recovery to a level that's already "good"

Current: target=50%, green=50% → exactly equal. If utilization is 49.9%, you've hit target but are still at "green boundary."
Proposed: margin_target_pct < margin_green_pct × 0.9 (90% of green threshold)
```

**Group D: The Trend Tier Ladder** (validated ✓, but gaps)
```
Existing: tier1 < tier2 < tier3 < tier4 (validated ✓)
Missing:
  trend_tier4_pct should NOT exceed the ATM Shield proximity converted to same units
  → If ATM Shield fires at 0.5% proximity of strike, and trend Tier 4 fires at 2.0% anchor move,
    these are measuring different things. No sync needed.

  BUT: If wind_down_on_atm fires when spot is within 0.5% of original strike, and trend Tier 4
  fires when spot has moved 2.0% from anchor, they could fire SIMULTANEOUSLY on the same event.
  Need: "if wind-down is already active via any path, skip trend Tier 4 wind-down trigger"
```

**Group E: The Lot Multiplier Stack** (critical gap)
```
Current multiplier application order (inferred from code):
  1. Base lots = formula
  2. Trend Tier 1 reduction (if enabled)
  3. Whipsaw RESTRICT halving (if active)
  4. Asymmetry reduction (if active)
  5. Consecutive direction cap (if active)
  6. Gamma-aware multiplier (if enabled)
  7. Breakeven multiplier (if enabled)
  8. Combined cap check (max_combined_lot_multiplier)
  9. Lot velocity limiter
  10. Position cap check

Problem: Steps 2-5 REDUCE lots. Steps 6-8 AMPLIFY. The amplifiers can undo the reducers.

Proposed rule: REDUCERS WIN.
  After all reductions (steps 2-5), compute a "reduced_lots_ceiling."
  Amplifiers (steps 6-8) can ONLY operate up to reduced_lots_ceiling.

  In other words: if whipsaw RESTRICT halved lots to N/2, no multiplier can push above N/2.
  The intent of RESTRICT is: "the market is dangerous — don't add more than N/2."
  A 3× breakeven multiplier saying "add 3× because you're near breakeven" directly contradicts
  the RESTRICT signal.

Implementation note: Add a session field `_lot_ceiling_from_reducers` set by any reduction mechanism.
  Multipliers read this ceiling and cap at it.
```

**Group F: The Whipsaw-Interval Coupling**
```
Current: whipsaw_window_mins=30 is independent of adjustment_interval=300s.

Proposed: whipsaw_window_beats = whipsaw_window_mins × 60 / adjustment_interval
  At 300s interval: 30min = 6 beats
  At 60s interval: 30min = 30 beats

The score decay of -1 per interval without noise is already correct — it scales naturally.
The problem is the DETECTION: alternations within `whipsaw_window_mins` are counted.
At 60s adaptive intervals, you can have 30 alternations in 30 minutes. At 300s base, only 6.

The whipsaw_cooldown_score (4) hits much faster at 60s intervals.

Proposed fix: Scale whipsaw score thresholds by heartbeat frequency:
  effective_caution = whipsaw_caution_score × max(1, adjustment_interval / 300)

  At 300s: caution=2 (unchanged)
  At 60s: caution=2 × (300/60) = 10 (much harder to hit)

  Or alternatively: make the window beat-based, not minute-based.
```

**Group G: Wind-Down Trigger Deduplication**
```
Five paths into wind-down. None know about each other.

Proposed: A single `session['_wind_down_active']` boolean, set by ANY trigger path.
  is_wind_down_active() in mmm_wind_down.py should be THE source of truth.
  It already checks all the path flags (_atm_wind_down_triggered, etc.).

What's missing: When wind-down is active via one path, the other paths should stop
trying to activate it again (wasted compute and confusing logs).

Proposed: When `_wind_down_active=True`, all 5 trigger checks skip their own activation
logic and just confirm wind-down is active.
```

### 5.3 Parameter Coherence Check (Session Start)

Run at session start AND on hot-reload. Returns a `_param_health` dict.

**Proposed checks to add:**

```
1. ATM Shield enabled + Margin Guardian disabled?
   → WARN: "ATM Shield may sell into margin stress. Enable margin_monitor for protection."

2. regime_enabled=True (first time enabling)?
   → INFO: "Regime controls activated. All 3 subsystems (vol/gamma/trend) are now live.
     Trend anchor initialized to current spot. Expect trend tiers to be evaluated immediately."

3. breakeven_control_enabled=True + max_combined_lot_multiplier < breakeven_aggression_max?
   → ERROR: "max_combined_lot_multiplier (N) < breakeven_aggression_max (M).
     Breakeven engine will never reach its maximum. Set max_combined >= breakeven_aggression_max."

4. wind_down_enabled=True + wind_down_close_threshold < harvest_profit_pct_threshold?
   → WARN: "Wind-down threshold may be below harvest trigger for some positions.
     Some frozen positions may be harvested before wind-down can close them."

5. trend_boost_enabled=True?
   → WARN: "Trend Boost is not covered by max_combined_lot_multiplier.
     Effective maximum lots per adjustment can exceed the combined cap."

6. lot_velocity_limit <= initial_lots × 3?
   → OK (reasonable)
   lot_velocity_limit <= initial_lots?
   → WARN: "Lot velocity limit is below initial_lots — normal adjustment may be blocked immediately."

7. max_loss_amount < (initial_lots × avg_entry_premium × LOT_SIZE_BTC × 0.3)?
   → WARN: "max_loss_amount covers less than 30% of one side's initial premium.
     Consider: max_loss_amount ≥ $X" (show computed value)

8. recycle_premium_ceiling >= shift_threshold?
   → WARN: "Recycle ceiling (N) is at or above shift_threshold (M).
     Recycle will try to buy back positions that haven't shifted yet.
     Recommended: recycle_premium_ceiling ≤ shift_threshold × 0.7"

9. harvest_pressure_threshold applied to active_lots only (Split Ledger):
   → If total_lots >> active_lots: "Harvest pressure calculation uses active_lots / max_lots_per_side.
     Your session has N frozen lots not counting toward pressure.
     Consider lowering harvest_pressure_threshold."

10. ATM Shield fires + Trend Tier GUARD or BLOCK active simultaneously:
    → "ATM Shield exempts endangered side from trend restrictions.
      This overrides BLOCK_CE_SELLS even when trend Tier 2/3 is active."
    (This is existing behavior — just needs to be documented clearly)
```

---

## 6. Default Value Recommendations

Current defaults were set in isolation. Here is a proposed **coherent default set** — all values chosen with knowledge of how they interact.

### 6A. The Core Problem: Defaults for "0 lots" vs. "real session"

Most defaults assume a generic user. But MMM is real-money, and the defaults should be CONSERVATIVE — the user should have to explicitly relax them, not accidentally have a dangerously loose config.

### 6B. Recommended Default Changes

**Capital Protection (too loose by default):**

| Parameter | Current Default | Recommended Default | Reason |
|---|---|---|---|
| `trailing_stop_pct` | 0.0 (off) | 0.50 (50%) | Should be ON by default — protect profits |
| `max_adjustments` | 500 | 30 | 500 is unrealistically high; 30 is already the UI display default |
| `max_loss_amount` | 5000 | — | Dynamic: should be set based on initial premium collected |
| `regime_enabled` | False | False | Keep off — enabling all 3 subsystems at once needs deliberate choice |
| `margin_monitor_enabled` | False | True | Should be ON — it's reading your real exchange margin |

**Position Management (wrong shape):**

| Parameter | Current Default | Recommended Default | Reason |
|---|---|---|---|
| `harvest_pressure_threshold` | 0.5 | 0.4 | Start harvesting earlier (40% active pressure) |
| `recycle_premium_ceiling` | 50.0 | 35.0 | Should be below shift_threshold default (50) |
| `wind_down_enabled` | False | True | Wind-down should be on by default — 0DTE positions need graceful exit |
| `wind_down_close_threshold` | 20.0 | 15.0 | 20 is too aggressive — closes at 85% of max possible theta; 15% is gentler |
| `close_at_watch_hours_before_expiry` | 3.0 | 4.0 | Watcher should activate before wind-down (wind_down_hours_before_expiry=2.0) |

**Lot Multiplier Stack (needs a reducer-wins rule):**

| Parameter | Current Default | Recommended Change | Reason |
|---|---|---|---|
| `max_combined_lot_multiplier` | 3.0 | 3.0 | OK, but should include trend_boost in its scope |
| `gamma_aware_max_multiplier` | 1.3 | 1.2 | Slightly lower — gamma-aware is additive with breakeven |
| `breakeven_aggression_max` | 3.0 | 2.5 | 3× is very aggressive; combined cap of 3.0 makes breakeven alone hit the ceiling |

**Whipsaw (needs interval awareness):**

| Parameter | Current Default | Recommended Change | Reason |
|---|---|---|---|
| `whipsaw_window_mins` | 30 | 30 | OK but needs beat-scaling |
| `whipsaw_cooldown_score` | 4 | 5 | At adaptive 60s intervals, 4 is too easy to hit |

---

## 7. The "Ideal Parameter Set" for a Conservative Session

A master trader starting a new session should use these settings. These are COHERENT — each parameter is chosen knowing what the others are doing.

```
Initial Position:
  initial_lots: 5               ← start small
  desired_ce_premium: 100       ← comfortable OTM
  desired_pe_premium: 100       ← symmetric

Core Dynamics:
  adjustment_interval: 300      ← 5-min heartbeat
  min_trigger_move: 15          ← 15% above snapshot to trigger
  shift_threshold: 60           ← shift if hedge premium < 60
  shift_target_premium: 120     ← target 2× shift threshold
  close_at_threshold: 5         ← close at $5 (5% of entry $100)

Position Limits (scaled to initial_lots=5):
  max_lots_per_side: 50         ← 10× initial_lots
  max_total_exposure: 75        ← 15× initial_lots
  lot_velocity_limit: 15        ← 3× initial_lots per window

Capital Protection (scaled to premium collected):
  max_loss_amount: 300          ← ~60% of one-side initial premium: 5 × $100 × 0.001 BTC × $60k = $30/side
                                   More practically: 300 = enough to cover 3 full adjustments
  trailing_stop_pct: 0.50       ← protect 50% of peak profit

Position Lifecycle (coherent ladder):
  close_at_threshold: 5         ← bottom rung
  recycle_premium_ceiling: 40   ← below shift_threshold (60) × 0.67
  harvest_profit_pct: 35        ← harvest frozen positions at 35% profit
  harvest_pressure_threshold: 0.4  ← activate at 40% capacity pressure
  shift_threshold: 60           ← shift threshold
  shift_target_premium: 120     ← shift target (2× shift_threshold)

Time-Based (coherent ladder):
  close_at_watch_hours_before_expiry: 4.0   ← watcher before wind-down
  wind_down_enabled: true
  wind_down_hours_before_expiry: 2.0        ← 2-hour wind-down
  wind_down_close_threshold: 15.0           ← elevated close during wind-down
  stop_adjustment_mins: 20                  ← stop adjustments 20min before expiry
  auto_close_mins: 5                        ← close all 5min before expiry

Whipsaw (scale-aware):
  whipsaw_window_mins: 30
  whipsaw_spot_move_pct: 0.4    ← slightly higher threshold for "justified" move
  whipsaw_caution_score: 2
  whipsaw_restrict_score: 3
  whipsaw_cooldown_score: 4

Margin Guardian (ON by default):
  margin_monitor_enabled: true
  margin_green_pct: 45          ← tighter than default (50)
  margin_yellow_pct: 60
  margin_orange_pct: 70         ← tighter than default (75)
  margin_red_pct: 80
  margin_critical_pct: 88
  margin_target_pct: 40         ← target recovery to 40% (below green)
```

---

## 8. The "Sync Engine" — What to Build

Based on all of the above, the plan for a Sync Engine is:

### Phase 1: Coherence Checks (No Code Risk)

Add to `mmm_config.py _interdependency_checks()`:
- The 10 proposed coherence checks in Section 5.3
- `_param_health` field in session for UI display
- No behavioral change — warnings only

**Effort:** Low. **Risk:** Zero (warning-only). **Value:** Immediate — shows users when their params are in conflict.

### Phase 2: Reducer-Wins Rule (Medium Risk)

In `mmm_engine.py` lot calculation:
- After all reduction steps, compute `reduced_lots_ceiling`
- Multipliers cap at `reduced_lots_ceiling`
- Add log entry when multiplier is ceiling-capped

**Effort:** Medium. **Risk:** Low (only affects lot sizing when both reducers AND amplifiers are active simultaneously). **Value:** High — prevents "RESTRICT but still over-hedging" scenario.

### Phase 3: Wind-Down Deduplication (Low Risk)

- Ensure `is_wind_down_active()` is the single truth
- When `_wind_down_active`, skip redundant trigger checks from other paths
- Add `_wind_down_trigger_source` to session for diagnostic logging

**Effort:** Low. **Risk:** Low. **Value:** Cleaner logs, easier debugging.

### Phase 4: ATM Shield Margin Awareness (Medium Risk)

- Add margin tier check to ATM Shield re-sell step (not gate check)
- If YELLOW: close endangered side, skip re-open, emit `atm_shield_close_only` event
- If GREEN: full close + re-open behavior

**Effort:** Medium. **Risk:** Medium (changes ATM Shield behavior). **Value:** High — eliminates the sell-into-margin-stress contradiction.

### Phase 5: Harvest Pressure Fix for Split Ledger (Medium Risk)

- `check_pressure()` in `mmm_harvester.py`: also compute `total_lots / max_total_exposure`
- Fire harvest if EITHER pressure measure >= threshold
- Log which measure triggered harvest

**Effort:** Low. **Risk:** Low (can only increase harvest frequency, never decrease safety). **Value:** High — prevents frozen lot accumulation with Split Ledger.

### Phase 6: Session Risk Level (SRL) (High Effort, High Value)

- Add `session['_srl']` computation in monitor heartbeat
- Each module writes its severity vote to `session['_srl_votes']`
- Monitor computes max → `session['_srl']`
- UI reads SRL and shows a single "session health" indicator

**Effort:** High (touches many modules). **Risk:** Medium (new field, additive). **Value:** Very high — enables future modules to instantly know the system's current risk posture.

---

## 9. Priority Matrix

| Phase | Safety Impact | Effort | Risk | Recommendation |
|---|---|---|---|---|
| Phase 1: Coherence Checks | HIGH (users stop making bad configs) | LOW | ZERO | **Do first** |
| Phase 2: Reducer-Wins | MEDIUM (prevents over-hedging when restricted) | MEDIUM | LOW | **Do second** |
| Phase 3: Wind-Down Dedup | LOW (logging/clarity) | LOW | LOW | **Do with Phase 2** |
| Phase 4: ATM Shield Margin | HIGH (real contradiction) | MEDIUM | MEDIUM | **Do after testing** |
| Phase 5: Harvest Pressure | MEDIUM (prevents lot accumulation) | LOW | LOW | **Do with Phase 4** |
| Phase 6: SRL | VERY HIGH (architectural) | HIGH | MEDIUM | **Plan carefully, implement last** |

---

## 10. What This Document Is NOT Saying

1. **Not saying the existing safety mechanisms are wrong.** Each one is correct in isolation. The problem is coordination, not correctness.

2. **Not saying "add more parameters."** The plan is to LINK existing parameters, not add new ones. Phase 1-5 add zero new parameters. Phase 6 adds one field (`_srl`).

3. **Not saying all features should be enabled by default.** Conservative defaults with more features off (ATM Shield, regime, perp hedge, breakeven engine) is correct. The sync engine is about ensuring that when you DO enable them, they work coherently.

4. **Not saying the user should set all these manually.** The long-term vision is: user sets `initial_lots`, `desired_premium`, and `risk_appetite=conservative/moderate/aggressive`. The Sync Engine computes sensible values for all derived parameters automatically. But that's Phase 7 (not in scope here).

---

## 11. Questions for the Trader Before Implementation

1. **Should the "Reducer-Wins" rule be absolute, or should it only apply when the SRL is ELEVATED+?**
   At LOW risk, maybe letting multipliers override reducers is fine (the reducer is a precaution, not a hard limit). At ELEVATED+, reducers should be absolute.

2. **Should ATM Shield be permanently gated at YELLOW+ (close-only, no re-sell), or just at ORANGE+?**
   YELLOW is fairly common (60% margin util). If ATM Shield can only close at YELLOW, it loses its "re-establish at safer strike" benefit frequently.

3. **For the harvest pressure fix: should it use OR logic (fire if EITHER measure hits threshold) or should total exposure pressure have a HIGHER threshold than active pressure?**
   E.g., harvest if active_pressure >= 0.4 OR total_pressure >= 0.7. This way, the active pressure threshold is stricter (fires earlier) and total pressure is a safety net.

4. **Is `regime_enabled` the right architecture for a master switch?**
   Currently, disabling regime disables vol, gamma, AND trend simultaneously. A user might want trend protection without gamma cap (or vice versa). Splitting the master switch into per-subsystem switches (which already exist: `vol_regime_enabled`, `gamma_cap_enabled`, `trend_enabled`) would allow more surgical control. The `regime_enabled` master could become a "monitoring/dashboard only" switch, with the subsystems controlled independently.

5. **On the dead zone between close_at ($5) and recycle_ceiling ($50): do you want to add a "gradual decay harvester" that closes positions with premium below $X regardless of profit percentage?**
   Currently M1 requires both profit% AND age. A simpler rule: "if premium is below $20 and position has been frozen for 60+ minutes, close it regardless of profit%" would eliminate the dead zone.

---

*End of Plan. Awaiting trader review before any implementation begins.*
