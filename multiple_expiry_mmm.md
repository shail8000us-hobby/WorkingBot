# Expanding MMM to Multi-Expiry: 5 / 10 / 20 DTE

> **Date:** March 12, 2026
> **Context:** MMM was built for 0DTE (same-day expiry) BTC options on Delta Exchange India. This document proposes how to expand it to 5, 10, and 20 DTE options while reusing the existing architecture.
> **Audience:** Developer implementing the changes + trader understanding the behavioral differences

---

## Why Multi-Expiry?

### 0DTE Limitations

| Problem | Impact |
|---|---|
| Limited time for premium decay | Must be aggressive with lot sizing |
| High gamma near expiry | Small spot moves cause large P&L swings |
| Forced auto-close at 21:30 IST | No flexibility to hold overnight |
| No room for recovery | A big move early kills the session |
| Theta acceleration is brief | Premium decays mostly in last 2 hours |

### What 5/10/20 DTE Brings

| DTE | Advantage | Trade-off |
|---|---|---|
| 5 DTE | More time to recover from whipsaw, theta still meaningful | Lower daily theta, need bigger positions for same premium |
| 10 DTE | Can ride through 1-2 day ranges, meaningful theta in last 3 days | Much lower gamma = less responsive hedge |
| 20 DTE | True swing strategy, can hold through weekends | Very slow theta, needs fundamentally different trigger logic |

---

## What Changes Are Needed

### Category 1: Parameter Tuning Only (No Code Changes)

These features already work for multi-DTE — just change the parameter values.

#### Adjustment Interval

| DTE | Suggested `adjustment_interval` | Reasoning |
|---|---|---|
| 0 DTE | 300s (5 min) | Premiums change fast, need quick reaction |
| 5 DTE | 900s (15 min) | Premiums change slower, less noise |
| 10 DTE | 1800s (30 min) | Significant premium changes take time |
| 20 DTE | 3600s (1 hour) | Theta is negligible per hour |

#### Trigger Sensitivity

| DTE | Suggested `min_trigger_move` | Reasoning |
|---|---|---|
| 0 DTE | 10% | Premiums can double in minutes |
| 5 DTE | 15–20% | Need bigger move to justify adjustment |
| 10 DTE | 20–30% | Avoid adjusting on intraday noise |
| 20 DTE | 30–50% | Only adjust on multi-day trend |

#### Shift Threshold

| DTE | Suggested `shift_threshold` | Reasoning |
|---|---|---|
| 0 DTE | 50 USD | Quick premium decay → shift often |
| 5 DTE | 30–40 USD | Slower decay → shift less |
| 10 DTE | 20–30 USD | Much slower decay |
| 20 DTE | 15–20 USD | Shift only when strike is truly dead |

#### Close-at Threshold

| DTE | Suggested `close_at_threshold` | Reasoning |
|---|---|---|
| 0 DTE | 5 USD | Close near-worthless quickly |
| 5 DTE | 3–5 USD | Same logic, slightly lower |
| 10 DTE | 2–3 USD | More patience, let it decay fully |
| 20 DTE | 1–2 USD | Positions take days to reach here |

#### Max Loss

Scale with expected premium collected:

| DTE | Entry Premium | Suggested `max_loss_amount` |
|---|---|---|
| 0 DTE | ~$100/side × 10 lots = $2 total | $5,000 (2.5× collected) |
| 5 DTE | ~$300/side × 10 lots = $6 total | $15,000 (2.5× collected) |
| 10 DTE | ~$500/side × 10 lots = $10 total | $25,000 (2.5× collected) |
| 20 DTE | ~$800/side × 10 lots = $16 total | $40,000 (2.5× collected) |

---

### Category 2: Code Changes Required (Medium Effort)

These features need modification to work properly with multi-DTE.

#### 2.1 Adaptive Interval Scaling (Must Change)

**Current behavior:** `compute_adaptive_interval()` in `mmm_trigger.py` scales interval based on hours-to-expiry. The tiers are hardcoded for 0DTE:
- > 8 hours: 1.5× (longer)
- 4-8 hours: 1.0× (normal)
- 2-4 hours: 0.7× (faster)
- 1-2 hours: 0.5×
- < 1 hour: 0.3× (rapid)

**Problem for multi-DTE:** A 20 DTE session starts at 480 hours. It would spend its entire life in the "> 8 hours" tier, always at 1.5× — never accelerating.

**Fix:**
```python
# Current: absolute hours
# Proposed: percentage of total DTE
def compute_adaptive_interval(base_interval, hours_to_expiry, total_dte_hours, enabled=True):
    if not enabled:
        return {'adaptive': False, ...}

    pct_remaining = hours_to_expiry / total_dte_hours

    if pct_remaining > 0.8:     # First 80% of life
        multiplier = 1.5        # Relaxed
    elif pct_remaining > 0.5:   # 50-80%
        multiplier = 1.0        # Normal
    elif pct_remaining > 0.2:   # 20-50%
        multiplier = 0.7        # Faster
    elif pct_remaining > 0.05:  # 5-20%
        multiplier = 0.5        # Rapid
    else:                       # Last 5%
        multiplier = 0.3        # Very rapid

    return {'adaptive': True, 'effective_interval': base_interval * multiplier, ...}
```

**Store `total_dte_hours` in session at creation time.** Add to `create_session()` in `mmm_state.py`.

#### 2.2 Theta Acceleration (Must Change)

**Current behavior:** `apply_theta_acceleration()` fires in the last 30 minutes, narrowing the trigger sensitivity and shortening intervals.

**Problem for multi-DTE:** For a 20 DTE option, the last 30 minutes is still relevant (gamma explodes ATM regardless of DTE). But the trigger widening makes no sense 20 days out — theta is negligible.

**Fix:**
- Keep the **interval acceleration** for the last 30 minutes (gamma protection) — this is universal.
- Make the **trigger widening** scale with DTE:
  ```python
  # Only widen triggers in last N% of total DTE
  theta_accel_window_pct = params.get('theta_accel_window_pct', 0.02)  # last 2%
  theta_accel_window_mins = total_dte_mins * theta_accel_window_pct
  # For 0DTE (24h): last 2% = 28 min (close to current 30 min)
  # For 5DTE (120h): last 2% = 144 min = 2.4 hours
  # For 20DTE (480h): last 2% = 576 min = 9.6 hours
  ```

#### 2.3 Wind-Down Timing (Must Change)

**Current behavior:** `wind_down_hours_before_expiry` defaults to a fixed value. Auto-close at `auto_close_mins` before expiry.

**Problem for multi-DTE:** A 20 DTE session shouldn't start winding down 1 hour before expiry — it should start 1-2 days before when theta decay accelerates.

**Fix:**
```python
# Suggest: wind-down as percentage of total DTE
'wind_down_pct_before_expiry': 0.10,  # last 10% of DTE
# 0DTE: last 10% = 2.4 hours (reasonable)
# 5DTE: last 10% = 12 hours (last half-day)
# 20DTE: last 10% = 48 hours (last 2 days)
```

Alternatively, add DTE-based presets:
```python
DTE_WIND_DOWN_HOURS = {
    0: 1,     # 1 hour before
    5: 12,    # 12 hours before
    10: 24,   # 1 day before
    20: 72,   # 3 days before
}
```

#### 2.4 Near-Expiry Safety Check (Must Change)

**Current behavior:** `check_near_expiry()` uses absolute minutes (`stop_adjustment_mins=15`, `auto_close_mins=5`).

**Problem for multi-DTE:** These are fine for 0DTE but meaningless for 20DTE. The relevant window scales with DTE.

**Fix:** Keep absolute minutes for the final safety (auto-close at 5 min is always correct — options expire regardless of DTE). But add a percentage-based "soft wind-down" that activates earlier for longer DTE:
```python
# New param
'near_expiry_warning_pct': 0.05,  # warn at last 5% of DTE
# 0DTE: last 5% = 72 min (current behavior roughly matches)
# 5DTE: last 5% = 6 hours
# 20DTE: last 5% = 24 hours
```

#### 2.5 Reversal Cooldown (Must Change)

**Current behavior:** Cooldown is `adjustment_interval × 2` (or `reversal_cooldown_seconds` once P1-B is implemented).

**Problem for multi-DTE:** With a 1-hour interval (20 DTE), the cooldown would be 2 hours. That's way too long — BTC can reverse and reverse again in 2 hours.

**Fix:** Use a separate `reversal_cooldown_seconds` parameter with DTE-appropriate defaults:
```python
DTE_REVERSAL_COOLDOWN = {
    0: 600,      # 10 min
    5: 1800,     # 30 min
    10: 3600,    # 1 hour
    20: 7200,    # 2 hours
}
```

---

### Category 3: New Features Needed (Major Effort)

These are features that don't exist today and are needed for multi-DTE to work properly.

#### 3.1 Roll-Over Between Expiries

**What:** When a 5 DTE session approaches expiry (e.g., 1 day left), automatically close positions and open new ones at the next week's expiry.

**Why needed:** 0DTE sessions die daily — the operator starts a new one each morning. For 5/10/20 DTE, the operator shouldn't have to manually close and re-open. The algo should offer automated rollover.

**Design:**
```
ROLL-OVER FLOW:
1. Session has `roll_over_hours_before_expiry` (e.g., 24h for 5DTE)
2. At that time, algo enters ROLLOVER mode:
   a. Find strikes on NEXT expiry with similar premium to current position
   b. Place sell orders at next expiry strikes
   c. If fills succeed: close current expiry positions via close-at-5
   d. If fills fail: stay in current expiry (fallback to normal wind-down)
3. Create new session for next expiry with same parameters
4. Transfer running P&L as base for new session's accounting
```

**Implementation considerations:**
- Need to handle both expiries simultaneously during transition
- Delta Exchange must support the next expiry's options chain
- Risk of gap between close and re-open (unhedged window)
- Consider doing the rollover in the last 4 hours of a trading day to have liquidity

#### 3.2 Multi-Session Correlation

**What:** When running multiple sessions (e.g., 0DTE + 5DTE + 20DTE simultaneously), they should be aware of each other's positions for aggregate risk management.

**Why needed:** Each session independently manages its own margin and delta. But the exchange sees them as one portfolio. Session A might be YELLOW on margin, while Session B happily adds more positions — causing a margin call.

**Design:**
```
SHARED STATE:
- Global margin utilization (one MarginGuardian per account, not per session)
- Aggregate portfolio delta (sum across all sessions)
- Combined max_loss tracking

PER-SESSION:
- Everything else stays session-local
- Each session has its own heartbeat, triggers, positions
```

**Implementation:**
- Create `MMMPortfolioManager` singleton that all sessions register with
- Each session reports: active_lots, frozen_lots, delta, unrealized_pnl
- Portfolio manager provides: aggregate_margin_tier, aggregate_delta, total_pnl
- Each session checks portfolio manager before adding new positions

#### 3.3 Overnight Risk Management

**What:** BTC trades 24/7 but options on Delta Exchange have settlement times. Multi-DTE positions are held overnight and over weekends.

**Why needed:** 0DTE has no overnight risk — it expires every day. But 5/20 DTE positions carry overnight gap risk. BTC can move 5-10% overnight.

**Design:**
```
OVERNIGHT MODE (activated during low-liquidity hours):
1. Widen trigger sensitivity by 2-3x (avoid adjusting on thin liquidity)
2. Reduce max_lots_per_adjustment (smaller bite sizes)
3. Set wider bid-ask acceptance in executor (more slippage tolerance)
4. Optional: close all positions before configurable "overnight window"
   (e.g., 22:00-06:00 IST) and re-open in the morning

WEEKEND MODE (activated Friday evening):
1. Close or reduce positions before weekend
2. Or: hold with widened stops (max_loss_amount *= 1.5 for weekend)
3. Re-tighten on Monday morning
```

#### 3.4 DTE-Aware Strike Selection

**What:** The initializer's strike selection should account for DTE when choosing OTM distance.

**Why needed:** For 0DTE, a strike 2% OTM is safe — it has a few hours to expire worthless. For 20DTE, a strike 2% OTM is dangerous — BTC can move 2% in a day easily.

**Design:**
```python
# Scale OTM distance with DTE
min_otm_distance_pct = base_otm_pct × sqrt(dte_days / 1)
# base_otm_pct = 2% (for 0DTE)
# 0DTE: 2% × sqrt(1/1) = 2%
# 5DTE: 2% × sqrt(5) = 4.5%
# 10DTE: 2% × sqrt(10) = 6.3%
# 20DTE: 2% × sqrt(20) = 8.9%

# This follows the sqrt(T) scaling of standard deviation
```

Also adjust `shift_target_premium` to account for higher premiums available at longer DTE.

#### 3.5 Theta Curve Awareness

**What:** Theta decay is not linear. For 0DTE it's steep and constant. For 20DTE, most theta decay happens in the last 5 days. The algo should adjust its behavior based on where it is on the theta curve.

**Why needed:** A 20DTE session at day 1 has almost zero theta. Selling more lots doesn't earn meaningful theta — it just adds risk. The algo should be more conservative early and more aggressive near expiry.

**Design:**
```
THETA CURVE PHASES:

Phase 1: ACCUMULATION (80% → 100% DTE remaining)
  - Conservative lot sizing (0.5× base lots)
  - Wide trigger sensitivity (avoid noise)
  - Focus on collecting premium at good strikes
  - No recycling or harvesting (let positions mature)

Phase 2: NORMAL (20% → 80% DTE remaining)
  - Standard lot sizing
  - Normal trigger sensitivity
  - M1/M2/M3 all active

Phase 3: ACCELERATION (5% → 20% DTE remaining)
  - Aggressive lot sizing (1.2× base lots)
  - Tight trigger sensitivity (capture fast decay)
  - Proactive harvesting (M1 threshold lowered)
  - More frequent heartbeats

Phase 4: EXPIRY (0% → 5% DTE remaining)
  - Wind-down mode active
  - LIFO buyback
  - Auto-close at absolute time
```

---

## Suggested DTE Preset Profiles

These are ready-to-use parameter sets for each DTE. The operator selects a preset when creating a session, and all parameters auto-fill.

### 0DTE Preset (Current Default)

```python
PRESET_0DTE = {
    'adjustment_interval': 300,
    'min_trigger_move': 10.0,
    'shift_threshold': 50,
    'shift_target_premium': 100,
    'close_at_threshold': 5,
    'max_loss_amount': 5000,
    'max_lots_per_side': 100,
    'whipsaw_cooldown_score': 4,
    'wind_down_hours_before_expiry': 1,
    'stop_adjustment_mins': 15,
    'auto_close_mins': 5,
}
```

### 5DTE Preset

```python
PRESET_5DTE = {
    'adjustment_interval': 900,        # 15 min
    'min_trigger_move': 20.0,          # 20% (less sensitive)
    'shift_threshold': 35,             # lower shift point
    'shift_target_premium': 150,       # higher premium available
    'close_at_threshold': 3,           # more patience
    'max_loss_amount': 15000,          # scaled to premium
    'max_lots_per_side': 75,           # fewer lots needed
    'whipsaw_cooldown_score': 5,       # more tolerance
    'wind_down_hours_before_expiry': 12,  # last half-day
    'stop_adjustment_mins': 30,        # wider window
    'auto_close_mins': 10,             # wider close window
    'reversal_cooldown_seconds': 1800, # 30 min cooldown
    'lot_velocity_limit': 15,          # slightly higher
    'lot_velocity_window_mins': 60,    # 1-hour window
    'trailing_stop_pct': 0.6,          # protect 60% of peak
}
```

### 10DTE Preset

```python
PRESET_10DTE = {
    'adjustment_interval': 1800,       # 30 min
    'min_trigger_move': 25.0,          # 25%
    'shift_threshold': 25,
    'shift_target_premium': 200,       # higher premium
    'close_at_threshold': 2,
    'max_loss_amount': 25000,
    'max_lots_per_side': 50,           # conservative sizing
    'whipsaw_cooldown_score': 6,       # very tolerant
    'wind_down_hours_before_expiry': 24,  # last day
    'stop_adjustment_mins': 60,
    'auto_close_mins': 15,
    'reversal_cooldown_seconds': 3600, # 1 hour
    'lot_velocity_limit': 10,
    'lot_velocity_window_mins': 120,   # 2-hour window
    'trailing_stop_pct': 0.5,
    'regime_enabled': True,            # regime matters more for multi-day
    'trend_tier1_pct': 2.0,            # wider trend thresholds
    'trend_tier2_pct': 4.0,
    'trend_tier3_pct': 6.0,
    'trend_tier4_pct': 10.0,
}
```

### 20DTE Preset

```python
PRESET_20DTE = {
    'adjustment_interval': 3600,       # 1 hour
    'min_trigger_move': 40.0,          # 40% (very conservative)
    'shift_threshold': 15,
    'shift_target_premium': 300,       # high premium
    'close_at_threshold': 1,           # very patient
    'max_loss_amount': 40000,
    'max_lots_per_side': 30,           # small position
    'whipsaw_cooldown_score': 8,       # very tolerant
    'wind_down_hours_before_expiry': 72,  # last 3 days
    'stop_adjustment_mins': 120,
    'auto_close_mins': 30,
    'reversal_cooldown_seconds': 7200, # 2 hours
    'lot_velocity_limit': 5,           # very slow accumulation
    'lot_velocity_window_mins': 240,   # 4-hour window
    'trailing_stop_pct': 0.4,
    'regime_enabled': True,
    'trend_tier1_pct': 3.0,
    'trend_tier2_pct': 5.0,
    'trend_tier3_pct': 8.0,
    'trend_tier4_pct': 15.0,
    'perp_hedge_enabled': True,        # delta hedge essential for multi-day
}
```

---

## Implementation Roadmap

### Phase 1: Parameter Presets (1-2 days, No Code Changes)

1. Add `DTE_PRESETS` dictionary to `mmm_config.py`
2. Add `dte_preset` selection to session creation API (`mmm_api.py`)
3. Frontend: dropdown in "New Session" dialog to pick preset
4. Store `dte_category` in session for UI display

**This alone enables multi-DTE usage** — operators manually adjust any parameters that don't feel right.

### Phase 2: Adaptive Scaling (3-5 days)

1. Store `total_dte_hours` in session at creation
2. Modify `compute_adaptive_interval()` to use percentage-based tiers
3. Modify `apply_theta_acceleration()` to scale window with DTE
4. Modify `check_near_expiry()` to use DTE-aware thresholds
5. Add `reversal_cooldown_seconds` parameter (P1-B fix)
6. Test with 5DTE mock sessions

### Phase 3: DTE-Aware Intelligence (1-2 weeks)

1. Implement theta curve phases (ACCUMULATION → NORMAL → ACCELERATION → EXPIRY)
2. DTE-aware strike selection in `mmm_initializer.py`
3. DTE-aware lot sizing in `mmm_engine.py` (scale with sqrt(DTE))
4. Overnight mode: widen triggers during 22:00-06:00 IST
5. Test with 10DTE and 20DTE mock sessions

### Phase 4: Multi-Session & Rollover (2-4 weeks)

1. `MMMPortfolioManager` for cross-session risk aggregation
2. Shared `MarginGuardian` per account
3. Roll-over automation between expiries
4. Weekend mode (close/hold/reduce)
5. Integration testing with multiple simultaneous sessions

---

## Key Risks for Multi-DTE

### Risk 1: Liquidity

0DTE options on Delta Exchange have decent liquidity near ATM. 20DTE far-OTM options may have zero liquidity.

**Mitigation:**
- Check bid-ask spread before placing orders (already done in `smart_execute()`)
- Add a `max_spread_pct` parameter: reject orders where `(ask-bid)/mid > max_spread_pct`
- For 20DTE: accept wider spreads (5-10%) vs 0DTE (1-3%)

### Risk 2: Gap Risk

BTC can move 5-10% overnight. A 20DTE position entered on Monday can be deep ITM by Tuesday.

**Mitigation:**
- Wider `min_trigger_move` prevents adjusting on noise
- `max_loss_amount` scaled to DTE provides adequate stop
- Perp hedge essential for 10/20 DTE (delta neutralization)
- Consider: mandatory perp hedge for DTE > 5

### Risk 3: Theta Drag

For 20DTE, theta is negligible in the first 15 days. Selling premium with no theta decay means you're essentially betting on range-bound markets with no edge.

**Mitigation:**
- Enter closer to expiry (e.g., at 10 remaining DTE for "20DTE" preset)
- Use ACCUMULATION phase to limit lot additions early
- Focus on premium level, not DTE: sell when premium is high regardless of DTE

### Risk 4: Regime Controls Are 0DTE-Calibrated

The vol regime's IV spike threshold (30%), trend tiers (1-5%), and gamma limits ($2,500-$10,000) are calibrated for 0DTE where premiums are $50-$200 and gamma is high.

For 20DTE: gamma is naturally low, premiums are $200-$800, and a "normal" daily range is 2-3%.

**Mitigation:**
- Include regime parameter adjustments in DTE presets (done above)
- Gamma limits should scale with `sqrt(DTE)` or be configurable per preset
- Trend tiers should widen with DTE (done above)

---

## Summary: What Exists Today vs. What's Needed

| Feature | 0DTE (Works Today) | 5DTE (Needs) | 10DTE (Needs) | 20DTE (Needs) |
|---|---|---|---|---|
| Core adjustment engine | Yes | Param tune | Param tune | Param tune |
| Trigger evaluation | Yes | Param tune | Param tune | Param tune |
| Strike shift | Yes | Param tune | Param tune | Param tune |
| Close-at-5 | Yes | Param tune | Param tune | Param tune |
| Safety checks | Yes | Near-expiry fix | Near-expiry fix | Near-expiry fix |
| Adaptive interval | Yes | % scaling | % scaling | % scaling |
| Theta acceleration | Yes | DTE window | DTE window | DTE window |
| Wind-down | Yes | DTE timing | DTE timing | DTE timing |
| Regime controls | Yes | Param tune | Param tune | Param tune |
| Margin Guardian | Yes | Works as-is | Works as-is | Works as-is |
| Perp hedge | Yes | Recommended | Essential | Essential |
| ATM Shield | Yes | Works as-is | Works as-is | Works as-is |
| M1/M2/M3 lifecycle | Yes | Works as-is | Works as-is | Works as-is |
| DTE presets | No | Phase 1 | Phase 1 | Phase 1 |
| Theta curve phases | No | Not needed | Phase 3 | Phase 3 |
| DTE-aware strikes | No | Not needed | Phase 3 | Phase 3 |
| Overnight mode | No | Nice to have | Phase 3 | Phase 3 |
| Roll-over | No | Not needed | Nice to have | Phase 4 |
| Multi-session risk | No | Phase 4 | Phase 4 | Phase 4 |
| Weekend mode | No | Not needed | Phase 4 | Phase 4 |

**Bottom line:** 5DTE works TODAY with just parameter tuning. 10DTE needs adaptive scaling fixes (Phase 2). 20DTE needs the full Phase 3 implementation. Start with Phase 1 presets — they enable all DTEs immediately with acceptable (not optimal) behavior.

---
---

# Strategic Analysis & Recommendations

> **Analyst:** Deep review of multi-expiry plan against current MMM architecture, Delta Exchange India market reality, and options trading economics
> **Date:** March 12, 2026
> **Verdict:** YES — but start with 5DTE only, with significant plan modifications

---

## 1. Is This a Good Idea?

**YES, with caveats.** Expanding to multi-DTE diversifies your risk profile and unlocks premium that 0DTE can't access. But the plan as written has gaps that must be addressed before implementation.

### Why YES:
- **0DTE is fragile.** One bad intraday move and the entire day's premium is gone. No time to recover.
- **5DTE is the sweet spot.** Meaningful theta (roughly 50-70% of 0DTE theta-per-strike), much lower gamma (positions don't blow up on a 2% move), and enough time to ride out whipsaws.
- **Premium stacking.** Running 0DTE + 5DTE simultaneously collects premium across different risk profiles. When 0DTE dies on a volatile day, 5DTE survives.
- **The current architecture already supports it.** Sessions have expiry dates, the chain service fetches all available expiries, and most features are parameter-driven.

### Why NOT yet for 10/20 DTE:
- **20DTE is a fundamentally different algo.** It's selling vega, not theta. Your trigger-adjustment model assumes theta decay drives premium changes. At 20DTE, premium moves are 80% vega (IV changes) and 20% theta. The entire decision engine needs rethinking for that.
- **10DTE is marginal.** Theta becomes meaningful only in the last 3-4 days, meaning you hold risk for 6-7 days with no edge.
- **Liquidity kills you.** Delta Exchange India is a small exchange. 0DTE near-ATM options have decent volume. 10-20 DTE OTM options may literally have zero bids. Your `smart_execute()` will fail or suffer catastrophic slippage.

---

## 2. Impact on Current Working 0DTE System

### Phase 1 (Presets): ZERO IMPACT
Adding a `DTE_PRESETS` dictionary and a dropdown is purely additive. No existing code changes. Safe.

### Phase 2 (Adaptive Scaling): MEDIUM RISK
This is where it gets dangerous:
- **`compute_adaptive_interval()`** — The current function uses absolute hours (>30h, 20-30h, etc.). The plan proposes percentage-based tiers. **If you change the function signature (add `total_dte_hours` parameter), every caller must be updated.** Missing one caller = runtime crash in production.
- **`apply_theta_acceleration()`** — Currently hardcoded for last 120 minutes. Changing this affects 0DTE behavior if not carefully branched.

**Recommendation:** Do NOT modify existing functions. Create NEW functions:
```
compute_adaptive_interval_v2(base_interval, hours_to_expiry, total_dte_hours)
apply_theta_acceleration_v2(session, minutes_to_expiry, total_dte_mins)
```
Have 0DTE continue using the originals. Only new multi-DTE sessions use the v2 functions. Switch 0DTE to v2 only after thorough regression testing.

### Phase 3 (DTE Intelligence): HIGH RISK
Theta curve phases, DTE-aware strikes, overnight mode — these touch `mmm_engine.py`, `mmm_initializer.py`, `mmm_monitor.py`. Each is a core production module.

**Recommendation:** Implement Phase 3 features behind a `dte_intelligence_enabled` flag. Default to `False` for 0DTE sessions. Only activate for explicitly configured multi-DTE sessions.

### Phase 4 (Multi-Session): CRITICAL SAFETY
Running multiple sessions without shared margin awareness is the single most dangerous thing in this plan. **One session can blow up the account while another keeps adding positions.**

**This must be moved to Phase 1 or at minimum before you run two sessions simultaneously.**

---

## 3. Critical Gaps in the Plan

### GAP-1: Liquidity Validation Is Not Addressed Seriously

The plan mentions liquidity under "Key Risks" but only as a mitigation ("check bid-ask spread"). This is the #1 showstopper.

**What to do:**
- Before starting ANY multi-DTE session, run a liquidity scan: fetch the full chain for that expiry, check how many strikes have `bid > 0` and `bid_size >= lots`. If fewer than 4 strikes (2 CE + 2 PE) have liquidity, refuse to start.
- Add `min_liquidity_lots` parameter (default: 5). Only consider strikes where `bid_size >= min_liquidity_lots`.
- Log liquidity snapshots — this data will tell you whether 10/20 DTE is even feasible on Delta Exchange India.

### GAP-2: Multi-Session Risk Must Be Phase 1

The plan puts `MMMPortfolioManager` in Phase 4. This is backwards. You CANNOT safely run two sessions without:
- **Shared margin monitoring** — the exchange sees one account. Two sessions independently checking "am I at 60% margin?" will both say "yes" even when combined they're at 90%.
- **Aggregate max_loss** — if 0DTE session hits -$4000 and 5DTE hits -$3000, total loss is -$7000. Each session thinks it's under its individual $5000 cap.

**Minimum viable safety: Before Phase 2, implement a simple `aggregate_session_pnl()` function that all running sessions check. If combined loss exceeds a global cap (`global_max_loss`), pause all sessions.**

### GAP-3: No Profitability Edge Analysis

The plan assumes "more DTE = more premium = more profit." This is wrong. Premium collected scales with DTE, but so does risk. The actual edge in options selling comes from the theta/gamma ratio, and this ratio behaves differently across DTEs:

| DTE | Theta/day | Gamma | Theta/Gamma Ratio | Edge |
|---|---|---|---|---|
| 0 DTE | Very high | Very high | Medium | Fast decay but fragile |
| 3-5 DTE | High | Moderate | **HIGHEST** | **Sweet spot** |
| 10 DTE | Medium | Low | Medium | Decent but slow |
| 20 DTE | Low | Very low | Low | No theta edge for 15 days |

**The plan should target 3-7 DTE, not 5/10/20 as proposed.** The theta/gamma ratio peaks in this range.

### GAP-4: No P&L Targets Per DTE

Without targets, you can't measure success. Add:
- 0DTE: Target $500-1000/day
- 5DTE: Target $2000-3000/week
- 10DTE: Target $3000-5000/biweek

If a DTE category consistently misses its target over 4 weeks, it's not profitable and should be dropped.

### GAP-5: No Backtest Plan

The preset parameter values (adjustment_interval=900 for 5DTE, min_trigger_move=20%, etc.) are educated guesses. Before going live, you need:
1. Historical premium data for Delta Exchange BTC options at each DTE
2. A simulator that replays the MMM algo with different parameters
3. At minimum 30 days of simulated results before risking real money

---

## 4. Profitability Strategies

### Strategy A: The Barbell (Recommended First)

Run 0DTE aggressively + 5DTE conservatively:
- **0DTE session:** Standard parameters, 10 lots/side, $5000 max loss. High theta, accepts gamma risk.
- **5DTE session:** Conservative parameters, 5 lots/side, $7500 max loss. Low theta but survives the intraday whipsaws that kill 0DTE.

**Why this works:** On quiet days, 0DTE harvests theta fast. On volatile days, 0DTE hits max loss but 5DTE barely moves (low gamma). Over a week, the 5DTE premium covers 1-2 bad 0DTE days.

### Strategy B: Premium Targeting (Advanced)

Don't choose a DTE — choose a premium range. Whatever DTE gives you $100-200 premium at a safe OTM distance, use it.

Low IV day → 0DTE premiums are thin → use 5DTE for better premium
High IV day → 0DTE premiums are fat → use 0DTE for fast decay

This requires `mmm_initializer.py` to scan across all expiries and recommend the best DTE/strike combination. Add as Phase 3 feature.

### Strategy C: RV-Based DTE Selection (Advanced)

Your volatility collector tracks realized volatility (RV). Use it:
- **RV < 30%:** Market is calm. Use 5-7 DTE, larger positions, wider strikes. Theta grinds steadily.
- **RV 30-50%:** Market is normal. Use 0DTE. Fast theta compensates for moderate gamma.
- **RV > 50%:** Market is wild. Use 0DTE only with small positions, or don't trade. Multi-DTE gets whipsawed.

### Strategy D: Theta Harvesting with Trailing Stops

For 5DTE sessions, implement time-based trailing stops:
- At entry, set `trailing_stop_pct = 0.5` (protect 50% of peak PnL)
- After 3 days (>50% of DTE elapsed), tighten to `trailing_stop_pct = 0.7`
- After 4 days (>80% elapsed), tighten to `trailing_stop_pct = 0.85`

This captures accelerating theta while protecting accumulated gains.

---

## 5. Plan Improvements

### 5.1 Revised Phase Roadmap

| Phase | Scope | Effort | Prerequisite |
|---|---|---|---|
| **Phase 0** | Liquidity audit + aggregate PnL safety | 1-2 days | None |
| **Phase 1** | DTE presets + session tagging | 1-2 days | Phase 0 |
| **Phase 1.5** | Paper-trade 5DTE with presets (2 weeks) | 0 code | Phase 1 |
| **Phase 2** | Adaptive scaling v2 (new functions, don't break old) | 3-5 days | Phase 1.5 results |
| **Phase 3** | DTE-aware intelligence (behind feature flag) | 1-2 weeks | Phase 2 |
| **Phase 4** | Full multi-session portfolio + rollover | 2-4 weeks | Phase 3 stable |

### 5.2 Drop 20DTE From Initial Scope

20DTE is a different algo. The trigger-based adjustment model doesn't suit it. The first 15 days you're just holding risk with no edge. If you want 20DTE, build a separate "swing options" module that:
- Enters based on IV percentile (sell when IV is high)
- Exits based on IV compression (buy back when IV drops)
- Uses fixed delta targets, not premium-based triggers

This is a separate project, not an MMM extension.

### 5.3 Simplify Theta Curve Phases

The plan proposes 4 phases (ACCUMULATION/NORMAL/ACCELERATION/EXPIRY). This is over-engineering. Use 2:

| Phase | DTE Remaining | Behavior |
|---|---|---|
| **HOLD** | > 40% of total DTE | Conservative lots (0.7x), wide triggers, no recycling. Let positions mature. |
| **HARVEST** | < 40% of total DTE | Normal lots, normal triggers, full M1/M2/M3. Theta is now meaningful. |

For 0DTE (24h), HOLD = first 14h, HARVEST = last 10h (roughly matches current behavior).
For 5DTE (120h), HOLD = first 72h (3 days), HARVEST = last 48h (2 days).

### 5.4 Add Liquidity Gate to Session Start

```
NEW SAFETY CHECK at session creation:
1. Fetch chain for target expiry
2. Count strikes with bid > 0 and bid_size >= min_liquidity_lots
3. If CE strikes < 2 OR PE strikes < 2: REFUSE to start
4. Log: "Insufficient liquidity for {expiry}: {n_ce} CE strikes, {n_pe} PE strikes"
```

### 5.5 Preset Values — Corrections

Some preset values in the plan need adjustment based on current code analysis:

**5DTE Preset corrections:**
- `max_lots_per_side: 75` → Change to `50`. With 5x longer DTE, you need fewer lots. 75 is too aggressive for a new DTE category.
- `lot_velocity_limit: 15` → Change to `8`. Slower accumulation is safer for multi-day.
- Add `dte_category: '5DTE'` for session tagging.

**10DTE Preset corrections:**
- `max_lots_per_side: 50` → Change to `30`. Conservative until proven profitable.
- `wind_down_hours_before_expiry: 24` → Change to `36`. Give more wind-down runway.
- `adjustment_interval: 1800` → Change to `1200` (20 min). 30 min is too slow — you miss opportunities.

### 5.6 Key Metrics to Track

Before declaring multi-DTE profitable, track these per DTE:
1. **Premium collected per day** (total premium / DTE days)
2. **Max drawdown** (worst unrealized loss during session)
3. **Theta efficiency** = (realized profit) / (theoretical theta collected). Should be > 0.5.
4. **Fill rate** = (orders filled) / (orders attempted). Below 80% means liquidity is too thin.
5. **Adjustment count per day** — if 5DTE adjusts more than 3x/day, triggers are too sensitive.

---

## 6. Risk Assessment Summary

| Risk | Severity | Mitigation | Status |
|---|---|---|---|
| Liquidity gap for longer DTE | **CRITICAL** | Pre-start liquidity gate | Not in plan — ADD |
| Multi-session margin collision | **CRITICAL** | Aggregate PnL tracking | In plan as Phase 4 — MOVE TO PHASE 0 |
| Phase 2 breaks 0DTE | **HIGH** | New v2 functions, don't modify originals | Not in plan — ADD |
| 20DTE has no theta edge | **HIGH** | Drop from scope | Not in plan — ADD |
| Preset values untested | **MEDIUM** | Paper-trade 2 weeks before live | Not in plan — ADD |
| Overnight gap risk (5DTE) | **MEDIUM** | Perp hedge + wider max_loss | Addressed |
| Code complexity increase | **MEDIUM** | Feature flags, DTE-aware branching | Partially addressed |

---

## 7. Final Recommendation

**Do this in order:**
1. **Phase 0:** Add aggregate PnL safety check across sessions + liquidity gate at session start. These are safety requirements, not features.
2. **Phase 1:** Add DTE presets with 0DTE and 5DTE profiles only. No 10DTE/20DTE yet.
3. **Paper-trade 5DTE for 2 weeks** using the 5DTE preset. Track the metrics in §5.6. Adjust presets based on real data.
4. **Phase 2:** If 5DTE paper-trade is profitable, implement adaptive scaling v2 (new functions, keep old ones for 0DTE).
5. **Consider 10DTE only after 5DTE has 30+ days of profitable live trading.**
6. **Never implement 20DTE as an MMM extension.** If you want it, build a separate IV-based swing module.

The MMM architecture is strong enough for 5DTE today. Don't over-build — prove profitability at each step before adding complexity.

---

*Analysis based on review of current MMM codebase (32 modules, ~32,900 lines), Delta Exchange India API capabilities, and options pricing theory.*
