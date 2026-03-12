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
