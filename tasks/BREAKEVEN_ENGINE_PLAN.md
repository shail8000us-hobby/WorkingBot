# Breakeven Engine — Implementation Plan (Reviewed & Final)

> **Feature:** Real-time portfolio breakeven awareness + defensive aggression near breakeven boundaries
> **Author:** AI Plan — March 15, 2026
> **Status:** ✅ IMPLEMENTED — March 15, 2026
> **Review History:**
> - Initial Plan: March 15, 2026
> - First Review: 8 external suggestions analyzed (5 adopted, 1 rejected, 2 partial)
> - Final Validation: 3 additional critiques evaluated (1 rejected, 1 partial, 1 confirmed correct)
> - Implementation: March 15, 2026 — all 4 phases complete, 436 sealed tests pass
>
> **Implementation Notes:**
> - Backend takes effect after next restart (disabled by default — `breakeven_control_enabled: false`)
> - Two live sessions (mmm15mar26-3, mmm16mar26-1) were running during implementation; backend not restarted
> - `gamma_mult` scope fix required: initialized to `1.0` before T3-2 block so combined ceiling can read it
> - Breakeven data embedded in `mmm_heartbeat` payload (`heartbeat.breakeven`) and emitted as standalone `mmm_breakeven` event
> - **Audit (March 15, 2026):** Found and fixed 5 missing `invalidate_cache()` calls (close-at-5, harvest, recycle, shift-time-recycle, inject) and missing param descriptions in `mmm_config.py`
> - **Documentation:** See `MMM_USERGUIDE.md` Section 12.5 and `AI_MMM_CONTEXT.md` Section 2.21 for complete feature documentation

---

## EXECUTIVE SUMMARY

**What changed from the original plan across all reviews:**

**First Review (8 suggestions):**
- **P&L model:** Time-value approximation replaced with intrinsic-only (simpler, faster, conservative)
- **Scan range:** Fixed ±8% replaced with dynamic range based on furthest strike (catches distant frozen positions)
- **Multiplier logic:** Directional filtering removed (was buggy and redundant with core trigger system)
- **Stacking protection:** Added combined multiplier ceiling (prevents gamma × breakeven × trend → 8x runaway)
- **Performance:** Position-change caching added (breakeven prices recomputed only when positions change, ~50-100x reduction)
- **Parameters:** `breakeven_use_time_value` removed, `max_combined_lot_multiplier` added

**Final Validation (3 critiques):**
- **Distance velocity:** Rejected — redundant with existing trend detection system
- **Band width aggression:** Partially adopted — added as diagnostic warning (not automatic control)
- **Perp cache invalidation:** Confirmed correct — already explicitly covered in design
- **Parameters:** Added `breakeven_narrow_band_threshold` (8 total parameters)

**Net result:** Simpler, safer, faster, better coverage. Same integration points, same 4-phase plan. One diagnostic enhancement added.

---

## PART 1: TECHNICAL REVIEW ANALYSIS

### Review Process

8 external technical suggestions were evaluated against the actual MMM codebase (not theoretical assumptions). Each was classified as Correct, Partially Correct, or Incorrect based on:
1. Actual MMM engine behavior (`mmm_engine.py`, `mmm_monitor.py` analysis)
2. Interaction with existing safety systems
3. Real-world session scenarios (multi-shift, frozen positions, multi-DTE)

---

### Suggestion 1: Use intrinsic-only or live premiums, not time value approximation

**Claim:** The `sqrt(DTE_fraction) * extrinsic` time value model will produce large errors when spot moves far from the strike.

**Verdict: PARTIALLY CORRECT**

**What's right:** The approximation was designed for *current* spot. At hypothetical spots $3,000–$7,000 away, an OTM option's extrinsic profile changes dramatically. The model would carry the current extrinsic forward, overstating the option's value at distant spots → portfolio P&L looks worse than reality → breakeven band appears narrower. This is conservative (early warnings) but still an error.

**What's wrong:** "Use live premiums" is impossible — the scan evaluates *hypothetical* spots. Live premiums only exist for current spot.

**What's missing:** The existing `compute_unrealized_pnl()` uses `(entry_premium - current_premium)` with live fetches. For breakeven scanning at hypothetical spots, we can't fetch live premiums.

**Resolution:** Use **intrinsic-only** scanning. This underestimates option value (ignores remaining extrinsic) → overestimates seller's loss → narrower breakeven band than reality → conservative for a risk tool. For 0DTE < 2 hours, intrinsic-only is essentially exact. For multi-DTE, the conservatism is acceptable.

**Design change:** Remove time value approximation entirely. Intrinsic-only model. Remove `breakeven_use_time_value` parameter.

---

### Suggestion 2: Dynamic scan range based on furthest strike distance

**Claim:** The fixed ±8% scan range may miss breakevens if frozen positions exist at distant strikes from prior shifts.

**Verdict: CORRECT**

**Analysis:** After multiple shifts, frozen positions can be far from current active strikes. Example:
- Frozen puts at $75,000 from an early shift
- BTC at $87,000
- Lower scan limit at 8%: $80,040
- The $75,000 put doesn't go ITM until spot < $75,000 (outside range)
- If those puts are large enough, the lower breakeven could be near $75,000 (missed)

**The fix:**
```python
all_strikes = [pos['strike'] for pos in open_positions]
furthest_strike_distance = max(abs(spot - k) for k in all_strikes)
min_range = furthest_strike_distance * 1.2  # 20% beyond furthest strike
scan_range = max(spot * (scan_range_pct / 100), min_range)
```

**Design change:** Dynamic scan range that auto-expands based on position spread. Keep `breakeven_scan_range_pct` as a minimum floor.

---

### Suggestion 3: Directional aggression logic is incorrect

**Claim:** The breakeven engine should not determine which side to hedge. It should only boost the lot count of whatever the core MMM adjustment logic already decided.

**Verdict: CORRECT — and the original plan contains a logic bug**

**The bug in the original plan:**
```python
if nearest_side == 'lower' and hedge_side == 'pe':
    apply_multiplier = True   # selling PE pushes lower breakeven further down
```

This is wrong. When spot approaches the **lower** breakeven (spot falling), put premiums rise, PE is the aggressor, and the core MMM logic hedges by **selling CE** (the opposite side). The original plan says the multiplier should apply when `hedge_side == 'pe'`, but the hedge side would be CE.

**Why the core adjustment logic already handles direction:**
- The trigger system fires when one side's premium rises → that side is aggressor → algo sells opposite side
- If spot approaches lower breakeven, puts go ITM, PE triggers, algo sells CE as hedge
- If spot approaches upper breakeven, calls go ITM, CE triggers, algo sells PE as hedge
- The trigger system naturally aligns the hedge

**The correct design:** Non-directional multiplier. When spot is in Warning/Danger/Critical zone, ANY triggered adjustment gets the boost.

**Design change:** Remove all directional logic. `get_aggression_multiplier()` signature simplifies from `(result, hedge_side) → float` to `(result) → float`.

---

### Suggestion 4: Multiplier stacking risk — need a combined multiplier cap

**Claim:** Adding a breakeven multiplier to existing gamma-aware and trend multipliers could create combined multipliers of 4x+, requiring a global cap.

**Verdict: CORRECT**

**Actual multiplier chain** (verified from `mmm_engine.py` lines 302–505):

| Order | Multiplier | Max Value | Default |
|-------|-----------|-----------|---------|
| 0 | Premium buffer | 1.05x | Always on |
| 1 | Gamma-aware (T3-2) | 1.3x | On by default |
| 2 | **Breakeven (proposed)** | **3.0x** | Off by default |
| 3 | Trend boost (IMP-2, safe side) | 2.0x | Off by default |

Worst-case combined: `1.05 × 1.3 × 3.0 × 2.0 = 8.19x`

Even with trend boost off (default): `1.05 × 1.3 × 3.0 = 4.10x`

**The solution: Add a combined multiplier ceiling**

```python
# After all multiplicative modifiers, before position cap clamps:
combined_mult = gamma_mult * breakeven_mult * trend_mult
max_combined = params.get('max_combined_lot_multiplier', 3.0)
if combined_mult > max_combined:
    scale_factor = max_combined / combined_mult
    lots_to_sell = max(math.ceil(lots_to_sell * scale_factor), 1)
```

**Design change:** Add `max_combined_lot_multiplier` parameter (default 3.0, range 1.5–5.0, hot-reloadable).

---

### Suggestion 5: Recompute breakeven only when positions change, not every heartbeat

**Claim:** The full scan+bisection is wasted if positions haven't changed. Only recompute when adjustments, shifts, harvests, recycles, or perp changes occur.

**Verdict: PARTIALLY CORRECT**

**What changes between heartbeats:**

| Component | Changes every heartbeat? | Affects breakeven? |
|-----------|------------------------|-------------------|
| Open positions (lots, strikes) | No (only on adjust/shift/close) | Yes — determines P&L curve |
| Realized P&L | No (only on close) | Yes — vertical shift |
| BTC spot price | Yes | Yes — determines distance, NOT location |
| Perp unrealized P&L | Yes (mark-to-market) | Yes — but linear in spot |

**The split optimization:** For an intrinsic-only model, the breakeven PRICES depend only on position layout (strikes, lots, entry_premiums) and realized P&L — both change rarely. The DISTANCE from spot to breakeven changes every heartbeat (spot moves), but that's trivial subtraction.

```
On position change:
  → Run full scan+bisection → cache breakeven prices

Every heartbeat:
  → Reuse cached breakeven prices
  → Recompute distance, zone, multiplier (trivial arithmetic)
```

**Design change:** Add position-change dirty flag. Cache breakeven prices. Recompute distances every heartbeat from cache. ~50-100x frequency reduction.

---

### Suggestion 6: The "use time value" toggle is unnecessary complexity

**Claim:** The parameter complicates the operator interface for marginal benefit.

**Verdict: CORRECT**

Follows from Suggestion 1. If we adopt intrinsic-only scanning, there's no time-value model to toggle. Even if we had two modes, forcing the operator to choose is a pricing engine decision operators shouldn't be exposed to.

**Design change:** Remove `breakeven_use_time_value` parameter. Parameter count remains 7 by adding `max_combined_lot_multiplier`.

---

### Suggestion 7: The <5ms performance estimate is optimistic

**Claim:** The number of position evaluations during the scan may exceed 5ms.

**Verdict: INCORRECT**

**Actual computation cost:**
- Coarse scan: 80 sample points × 20 positions × 3 float ops = 4,800 ops
- Binary search: 40 iterations × 20 positions × 3 float ops = 2,400 ops
- Total: ~7,200 float ops

CPython executes simple float arithmetic at ~5–10 million ops/sec. 7,200 operations = **~1ms**.

With position-change caching (Suggestion 5), per-heartbeat cost drops to **< 0.01ms**.

**The 5ms estimate is actually conservative, not optimistic.**

**Design change:** None. Keep <5ms target.

---

### Suggestion 8: Missing detection of rapidly shrinking breakeven bands

**Claim:** If the breakeven band width contracts quickly, it signals accelerating risk and the algorithm should reduce aggression.

**Verdict: PARTIALLY CORRECT — observation valid, action wrong**

**The observation is valid:** A rapidly contracting band means losing money faster than gaining. Can happen when aggressive adjustments stack lots, frozen positions go deep ITM, or perp hedge direction flipped.

**The prescribed action is wrong:** Reducing aggression when band contracts means selling *fewer* hedge lots precisely when the portfolio needs *more* protection. The entire thesis of the breakeven engine is to hedge MORE aggressively as breakeven approaches.

**What existing safety systems already do:**

| Cause | Existing Response |
|-------|------------------|
| Lot stacking | Asymmetry 5:1 reduction (IMP-3) |
| Trend move | Trend guard escalates tiers → blocks sells |
| Margin pressure | Margin guardian → blocks sells |
| Whipsaw | Whipsaw guard → cooldown |
| P&L deterioration | Max-loss stop, trailing-stop |

**What IS valuable:** Adding `band_width_pct` and `band_width_velocity` as diagnostic data. Log activity when band contracts >30%.

**Design change:** Add `band_width_velocity` to BreakevenResult. Emit `breakeven_band_contracting` activity log. No automated aggression reduction.

---

### Review Summary Table

| # | Suggestion | Verdict | Action |
|---|-----------|---------|--------|
| 1 | Use intrinsic-only, not time value | Partially Correct | **Adopt** intrinsic-only |
| 2 | Dynamic scan range | Correct | **Adopt** |
| 3 | Non-directional multiplier | Correct | **Adopt** (original had bug) |
| 4 | Combined multiplier cap | Correct | **Adopt** |
| 5 | Cache breakeven prices | Partially Correct | **Adopt** split approach |
| 6 | Remove time value toggle | Correct | **Adopt** |
| 7 | <5ms is optimistic | Incorrect | **Reject** (1ms actual) |
| 8 | Detect band contraction | Partially Correct | **Adopt** detection, reject response |

**Net result:** 5 full adoptions, 2 partial adoptions, 1 rejection. Original plan was structurally sound; these corrections eliminate bugs and improve robustness.

---

## PART 2: REVISED BREAKEVEN ENGINE DESIGN

---

## 1. WHAT THIS FEATURE DOES

The breakeven engine gives the algorithm **spot-price awareness**. Today the algorithm only reacts to premium-based triggers ("CE premium rose above snapshot → sell PE"). It has no idea what BTC spot price would actually make the entire portfolio unprofitable.

This module adds:

1. **Breakeven band calculation** — the lower and upper BTC spot prices where total portfolio P&L = 0
2. **Distance tracking** — how far the current spot is from each breakeven boundary
3. **Risk zone classification** — Safe / Warning / Danger / Critical
4. **Aggression multiplier** — sells more hedge lots as spot approaches breakeven (non-directional)
5. **Dashboard visualization** — operator sees breakeven band, spot position, and zone in real time

---

## 2. CORE MATH — HOW BREAKEVEN IS CALCULATED

### 2.1 Portfolio P&L as a Function of Spot Price (Intrinsic-Only Model)

For any hypothetical `spot_h`, the portfolio P&L is:

```
PnL(spot_h) = Σ position_pnl(pos, spot_h) + realized_pnl + perp_pnl(spot_h)
```

**For a SHORT CALL position** at strike K with entry_premium P_entry, lots N:
```
intrinsic_at_spot_h = max(spot_h - K, 0)
position_pnl = (P_entry - intrinsic_at_spot_h) * N × LOT_SIZE_BTC
```

**For a SHORT PUT position** at strike K with entry_premium P_entry, lots N:
```
intrinsic_at_spot_h = max(K - spot_h, 0)
position_pnl = (P_entry - intrinsic_at_spot_h) * N × LOT_SIZE_BTC
```

**For PERP HEDGE** with lots L_perp at avg_entry E_perp:
```
perp_pnl = (spot_h - E_perp) × L_perp × LOT_SIZE_BTC  [positive = long, negative = short]
```

**Why intrinsic-only?**
- **Conservative bias:** Ignores remaining extrinsic value → makes options appear more expensive to buy back → narrows the breakeven band → the engine thinks the portfolio breaks even *closer* to spot than reality → early warnings rather than late warnings
- **Simplicity:** No IV assumptions, no complex time-decay models, pure arithmetic on strikes and spot
- **Accuracy near expiry:** For 0DTE < 2 hours, time value is negligible — intrinsic-only is essentially exact
- **Acceptable for multi-DTE:** The conservative error (early warnings) is the right direction for a risk tool

**No live premium fetches needed:** Unlike the real P&L computation (`compute_unrealized_pnl()` which calls `fetch_premium_fn` for every position), the breakeven scan uses only strikes, entry_premiums, and hypothetical spot prices — all in-memory data.

### 2.2 Finding Breakeven Points

Use a two-pass numerical method:

**Pass 1 — Coarse scan:**
- Range: **Dynamic** — see §2.2.1 below
- Step: `spot × 0.002` (~$174 steps at $87k BTC, giving ~80 sample points)
- Walk from center outward in both directions
- Detect sign change in PnL (positive → negative)

**Pass 2 — Binary search refinement:**
- For each sign change found, binary search between the two bracketing prices
- Converge to within $10 precision (sufficient for risk zones)
- Max 20 iterations (guaranteed convergence: $7,000 / 2^20 = $0.007)

### 2.2.1 Dynamic Scan Range (Corrected from Original)

**Problem with fixed ±8%:** After multiple strike shifts, frozen positions can be far from the current active strikes. Example:
- Frozen puts at $75,000 from an early shift
- BTC at $87,000
- 8% scan: [$80,040, $93,960] — misses the $75,000 strike entirely
- Lower breakeven near $75,000 would be invisible

**Solution:**
```python
def _compute_scan_range(self, spot, positions, params):
    all_strikes = [p['strike'] for p in positions]
    if not all_strikes:
        return spot * (params['breakeven_scan_range_pct'] / 100)

    furthest = max(abs(spot - k) for k in all_strikes)
    min_range_from_strikes = furthest * 1.2  # 20% beyond furthest strike
    min_range_from_param = spot * (params['breakeven_scan_range_pct'] / 100)

    return max(min_range_from_strikes, min_range_from_param)
```

This ensures the scan always covers at least 20% beyond the furthest open strike, while `breakeven_scan_range_pct` acts as a minimum floor.

**Edge cases:**
- **No breakeven found on one side:** Portfolio is profitable everywhere in that direction → distance = `inf` → Safe zone
- **Portfolio already underwater at spot:** Both breakevens may be very close → Critical zone immediately
- **Only puts / only calls remain:** Only one breakeven exists → the other side is unbounded
- **All positions closed:** No breakevens → skip computation entirely

### 2.3 Distance Calculation

```python
distance_lower_pct = (spot - lower_breakeven) / spot × 100
distance_upper_pct = (upper_breakeven - spot) / spot × 100
nearest_distance_pct = min(distance_lower_pct, distance_upper_pct)
nearest_side = 'lower' if distance_lower_pct < distance_upper_pct else 'upper'
```

### 2.4 Position-Change Caching (New)

Since breakeven prices depend only on position layout (which changes rarely), cache the results:

```python
class BreakevenEngine:
    def __init__(self):
        self._cache = {}  # session_id → {lower, upper, positions_hash, band_width, computed_at}

    def compute_breakeven(self, session, spot_price):
        session_id = session['session_id']
        positions = self._collect_open_positions(session)
        pos_hash = self._hash_positions(positions, session)

        cached = self._cache.get(session_id)
        if cached and cached['positions_hash'] == pos_hash:
            # Positions unchanged — reuse cached breakeven prices
            lower = cached['lower_breakeven']
            upper = cached['upper_breakeven']
        else:
            # Positions changed — full scan + bisection (~1ms)
            lower = self._find_breakeven(positions, spot_price, session, 'lower')
            upper = self._find_breakeven(positions, spot_price, session, 'upper')
            band_width = ...
            self._cache[session_id] = {
                'lower_breakeven': lower,
                'upper_breakeven': upper,
                'positions_hash': pos_hash,
                'band_width_at_compute': band_width,
                'computed_at': now,
            }

        # Always recompute: distance, zone, multiplier (~0.01ms trivial arithmetic)
        return self._build_result(lower, upper, spot_price, session)

    def _hash_positions(self, positions, session):
        """Hash of all factors that affect breakeven location."""
        # Strikes, lots, entry_premiums, realized_pnl, perp avg_entry, perp lots
        ...

    def invalidate_cache(self, session_id):
        """Called by monitor after position-changing events."""
        self._cache.pop(session_id, None)
```

**Dirty events** that call `invalidate_cache()`: adjustment fill, strike shift, close-at-5, M1 harvest, M2 recycle, operator inject, adopt, perp fill.

**Performance impact:** ~50-100x reduction in scan frequency. Full scan only runs 2-3 times per session (on adjustments/shifts). Per-heartbeat cost drops from ~1ms to ~0.01ms.

---

## 3. RISK ZONE CLASSIFICATION

### 3.1 Zone Thresholds

| Zone | Condition | Default Threshold | Meaning |
|------|-----------|-------------------|---------|
| **SAFE** | `nearest_distance_pct > warning_pct` | > 2.0% | ~$1,740 buffer at $87k — comfortable |
| **WARNING** | `danger_pct < nearest_distance_pct ≤ warning_pct` | 1.0% – 2.0% | ~$870–$1,740 — drifting toward breakeven |
| **DANGER** | `critical_pct < nearest_distance_pct ≤ danger_pct` | 0.5% – 1.0% | ~$435–$870 — actively threatened |
| **CRITICAL** | `nearest_distance_pct ≤ critical_pct` | ≤ 0.5% | < $435 — imminent breach |

All thresholds are hot-reloadable.

### 3.2 Aggression Multiplier (Non-Directional — Corrected)

**Original plan had a bug:** It tried to apply the multiplier only when the hedge_side matched the at-risk breakeven boundary. This was both logically incorrect (the mapping was backwards) and conceptually redundant (the core trigger system already determines the correct hedge side).

**Corrected design:** The multiplier is a pure function of `(zone, nearest_distance_pct)` with NO directional filtering. When spot is in Warning/Danger/Critical zone, ANY triggered adjustment gets the boost. The core trigger system ensures the adjustment is already on the correct side.

**Linear interpolation within zones:**

```python
def _compute_multiplier(self, zone, nearest_distance_pct, params):
    warning_pct = params['breakeven_warning_pct']
    danger_pct = params['breakeven_danger_pct']
    critical_pct = params['breakeven_critical_pct']
    max_mult = params['breakeven_aggression_max']

    if zone == 'SAFE':
        return 1.0

    elif zone == 'WARNING':
        # Linear ramp from 1.0 to 1.3 as distance shrinks
        progress = (warning_pct - nearest_distance_pct) / (warning_pct - danger_pct)
        return 1.0 + progress * 0.3

    elif zone == 'DANGER':
        # Linear ramp from 1.3 to 2.0
        progress = (danger_pct - nearest_distance_pct) / (danger_pct - critical_pct)
        return 1.3 + progress * 0.7

    elif zone == 'CRITICAL':
        # Ramp from 2.0 to max_mult as distance approaches 0
        progress = min(1.0, (critical_pct - nearest_distance_pct) / critical_pct)
        return 2.0 + progress * (max_mult - 2.0)
```

**Why linear interpolation instead of step function:** Step functions cause lot jumps at zone boundaries. If spot oscillates around `danger_pct`, the lot count would flip-flop. Linear gives smooth scaling.

**Simplified method signature:**
```python
def get_aggression_multiplier(self, breakeven_result) -> float:
    """Returns multiplier >= 1.0. Applied to ALL adjustments."""
    if not breakeven_result or breakeven_result['zone'] == 'SAFE':
        return 1.0
    return breakeven_result['multiplier']
```

No `hedge_side` parameter. No directional logic.

### 3.3 Band Width Velocity Tracking (New)

Track band width over time to detect rapid contraction (accelerating risk):

```python
# In BreakevenResult:
'band_width_pct': float,              # Current band width as % of spot
'band_width_prev_pct': float | None,  # Previous computation's band width
'band_contracting': bool,             # True if band shrunk >30% since last recompute
```

When `band_contracting` is True:
- Log an activity entry of type `breakeven_band_contracting`
- Display a warning indicator on the UI panel

**No automated response:** Existing safety systems (regime, margin guardian, whipsaw, asymmetry, max-loss) already handle the root causes of band contraction. Adding another control mechanism here risks conflicts. The velocity data is purely diagnostic/alerting.

---

## 4. SAFETY INTEGRATION — WHAT THE MULTIPLIER CANNOT DO

The aggression multiplier modifies `lots_to_sell` BEFORE the existing safety clamps:

| Safety System | How It Already Works | Breakeven Interaction |
|---------------|---------------------|----------------------|
| `max_lots_per_side` | Caps `active_lots` per side | Multiplied lots clamped by cap headroom |
| `max_total_exposure` | Caps `active + frozen` | Exposure ceiling still enforced |
| `max_combined_lot_multiplier` | **NEW** — caps gamma × breakeven × trend | Prevents compound runaway |
| Margin Guardian | Blocks sells at YELLOW+ | Multiplier irrelevant when sells blocked |
| Regime BLOCK_ALL_SELLS | Blocks all sell orders | Multiplier bypassed entirely |
| Whipsaw RESTRICT | Halves lots | Applied AFTER multiplier — acts as counterweight |
| Consecutive direction limiter (IMP-5) | Limits same-direction adjustments | Still enforced |
| Lot velocity limit | Caps lots per time window | Still enforced |
| Asymmetry 5:1 reduction (IMP-3) | Reduces lots on heavy side | Applied AFTER multiplier |

### 4.1 Combined Multiplier Ceiling (New)

**Problem:** Individual multipliers are reasonable, but their compound effect can be extreme:
- Gamma-aware: 1.3x (default on)
- Breakeven: 3.0x (when in Critical zone)
- Trend boost: 2.0x (when enabled)
- Combined worst-case: `1.05 × 1.3 × 3.0 × 2.0 = 8.19x`

**Solution:** Cap the combined multiplier after all multiplicative modifiers:

```python
# In calculate_lots_to_sell(), after all individual multipliers:
combined_multiplier = gamma_mult * breakeven_mult
if trend_boost_applied:
    combined_multiplier *= trend_boost_mult

max_combined = params.get('max_combined_lot_multiplier', 3.0)
if combined_multiplier > max_combined:
    overshoot = combined_multiplier / max_combined
    lots_to_sell = max(math.ceil(lots_to_sell / overshoot), 1)
```

This allows each module to express its full intent while bounding the compound effect.

### 4.2 Order of Operations in `calculate_lots_to_sell()` (Corrected)

```
 1. raw_lots = loss / (premium × LOT_SIZE_BTC) × (1 + buffer)
 2. lots = ceil(raw_lots)
 3. ×= gamma_aware_multiplier (T3-2)                [1.0 – 1.3x]
 4. ×= breakeven_aggression_multiplier              [1.0 – 3.0x]  ← NEW
 5. ×= trend_boost/trend_reduction (IMP-2)          [0.7 – 2.0x]
 5a. COMBINED CEILING CHECK                         ← NEW
     if (gamma × breakeven × trend) > max_combined_lot_multiplier:
       scale lots back proportionally
 6. lots = min(lots, cap_remaining)                 ← max_lots_per_side
 7. lots = min(lots, exposure_remaining)            ← max_total_exposure
 8. lots ×= asymmetry_reduction (IMP-3)             [0.0 – 1.0x]
 9. lots ×= otm_scaling (IMP-4)                     [0.0 – 1.0x]
```

**Key insight:** The ceiling sits after all multiplicative amplifiers but before all hard caps and reductive modifiers.

---

## 5. CONFIGURABLE PARAMETERS (Revised)

| Parameter | Default | Type | Range | Hot Reload | Status |
|-----------|---------|------|-------|------------|--------|
| `breakeven_control_enabled` | `false` | bool | — | Yes | Unchanged |
| `breakeven_warning_pct` | `2.0` | float | 0.5–10.0 | Yes | Unchanged |
| `breakeven_danger_pct` | `1.0` | float | 0.2–5.0 | Yes | Unchanged |
| `breakeven_critical_pct` | `0.5` | float | 0.1–2.0 | Yes | Unchanged |
| `breakeven_aggression_max` | `3.0` | float | 1.5–5.0 | Yes | Min raised to 1.5 |
| `breakeven_scan_range_pct` | `5.0` | float | 2.0–15.0 | Yes | Now minimum floor; default lowered |
| `max_combined_lot_multiplier` | `3.0` | float | 1.5–5.0 | Yes | **NEW** — caps combined multipliers |
| `breakeven_narrow_band_threshold` | `5.0` | float | 1.0–10.0 | Yes | **NEW** — warns when band < threshold |

**Removed:** `breakeven_use_time_value` (intrinsic-only model has no toggle)

**Total: 8 parameters** (was 7, added narrow band threshold and combined ceiling, removed time value toggle)

**Validation rule:** `critical_pct < danger_pct < warning_pct` (interdependency check in `mmm_config.py`).

---

## 6. FILE CHANGES — COMPLETE MAP

### 6.1 New File: `mmm_breakeven_engine.py`

**Location:** `webui/backend/routes/mmm/mmm_breakeven_engine.py`

**Estimated size:** ~400–450 lines (slightly larger due to caching logic)

**Class:** `BreakevenEngine`

**Public methods:**

| Method | Signature | Returns |
|--------|-----------|---------|
| `compute_breakeven` | `(session, spot_price) → BreakevenResult` | Full breakeven analysis |
| `get_aggression_multiplier` | `(result) → float` | Multiplier for lot calculation (**no hedge_side param**) |
| `invalidate_cache` | `(session_id) → None` | Invalidate cached breakeven prices |

**`BreakevenResult` structure (dict):**
```python
{
    'lower_breakeven': float | None,
    'upper_breakeven': float | None,
    'spot_price': float,
    'distance_lower_pct': float | None,
    'distance_upper_pct': float | None,
    'nearest_distance_pct': float | None,
    'nearest_side': str,                     # 'lower' | 'upper' | 'none'
    'zone': str,                             # 'SAFE' | 'WARNING' | 'DANGER' | 'CRITICAL'
    'multiplier': float,                     # Current aggression multiplier (non-directional)
    'pnl_at_spot': float,
    'band_width_pct': float | None,
    'band_width_prev_pct': float | None,     # NEW — for velocity tracking
    'band_contracting': bool,                # NEW — True if contracted >30%
    'is_narrow_band': bool,                  # NEW — True if width < narrow_band_threshold
    'computed_at': str,
    'positions_included': int,
    'perp_included': bool,
    'from_cache': bool,                      # NEW — True if breakeven prices reused from cache
}
```

**Internal methods:**

| Method | Purpose |
|--------|---------|
| `_collect_open_positions(session)` | Gathers all active + shifted positions |
| `_compute_pnl_at_spot(positions, spot_h, perp_state, realized_pnl)` | Portfolio P&L at hypothetical spot (intrinsic-only) |
| `_find_breakeven(positions, spot, perp, realized, direction)` | Coarse scan + binary search |
| `_compute_scan_range(spot, positions, params)` | **NEW** — dynamic range based on furthest strike |
| `_hash_positions(positions, session)` | **NEW** — hash of position layout for cache invalidation |
| `_classify_zone(nearest_distance_pct, params)` | Returns zone string |
| `_compute_multiplier(zone, nearest_distance_pct, params)` | Continuous aggression ramp |
| `_build_result(...)` | Assembles BreakevenResult dict |

### 6.2 Modified Files

| File | Change | Lines Affected | Reason |
|------|--------|---------------|--------|
| **`mmm_state.py`** | Add 7 params to `DEFAULT_PARAMS`, add to `HOT_RELOAD_PARAMS` (swap `breakeven_use_time_value` → `max_combined_lot_multiplier`) | ~15 lines | Params revised |
| **`mmm_config.py`** | Add 7 `PARAM_RULES` entries (revised set) + breakeven interdependency validation | ~35 lines | Params revised + combined mult |
| **`mmm_monitor.py`** | (1) Import BreakevenEngine singleton, (2) Call `compute_breakeven()` at Step 5.7 WITHOUT fetch_premium_fn, (3) Store `_breakeven_result` in session, (4) Pass multiplier to `calculate_lots_to_sell()` WITHOUT directional check, (5) Call `invalidate_cache()` after position-changing events | ~50 lines | Simplified: no fetch_fn, no directional logic, added cache invalidation hooks |
| **`mmm_engine.py`** | (1) Accept `breakeven_multiplier` param in `calculate_lots_to_sell()`, (2) Apply after gamma multiplier, (3) Add combined multiplier ceiling logic after step 5 | ~25 lines | Multiplier integration + stacking protection |
| **`mmm_websocket.py`** | Add `emit_breakeven()` function (embed in `mmm_heartbeat` payload or standalone event) | ~25 lines | Unchanged |
| **`mmm_api.py`** | Add `GET /api/mmm/session/<id>/breakeven` endpoint | ~30 lines | Unchanged |
| **`mmm_activity.py`** | Add `'breakeven_zone_change'`, `'breakeven_band_contracting'`, AND `'breakeven_narrow_band'` activity types | ~7 lines | Added band contraction and narrow band types |
| **`MMMSettingsDialog.js`** | Add "Breakeven Engine" settings section (8 params: remove time value toggle, add combined multiplier slider, add narrow band threshold) | ~80 lines | Params revised + narrow band |
| **`MMMDashboard.js`** | Import + render `MMMBreakevenPanel` component | ~5 lines | Unchanged |

### 6.3 New Frontend File: `MMMBreakevenPanel.js`

**Location:** `webui/frontend/src/components/mmm/MMMBreakevenPanel.js`

**Estimated size:** ~280–320 lines (added band contraction indicator)

---

## 7. IMPLEMENTATION PHASES

### Phase 1: Core Engine + Backend Integration (No UI)
**Goal:** Breakeven calculation runs every heartbeat (or cached), result stored in session state, available via API.

| Step | Task | Files | Additions from Review |
|------|------|-------|----------------------|
| 1.1 | Create `mmm_breakeven_engine.py` with intrinsic-only model, dynamic scan range, position-change caching | New file | Intrinsic-only, dynamic range, caching |
| 1.2 | Add 8 params (revised set) to `DEFAULT_PARAMS` + `HOT_RELOAD_PARAMS` | `mmm_state.py` | Added narrow band + combined mult |
| 1.3 | Add `PARAM_RULES` (revised) + interdependency validation | `mmm_config.py` | Combined mult + narrow band |
| 1.4 | Hook into heartbeat at Step 5.7, call `compute_breakeven(session, spot)` | `mmm_monitor.py` | No fetch_fn param |
| 1.5 | Store `_breakeven_result` in session state | `mmm_monitor.py` | Unchanged |
| 1.6 | Add cache invalidation hooks after adjust/shift/close/harvest/recycle/inject | `mmm_monitor.py` | **NEW** |
| 1.7 | Add `GET /session/<id>/breakeven` API endpoint | `mmm_api.py` | Unchanged |
| 1.8 | Add `breakeven_zone_change`, `breakeven_band_contracting`, and `breakeven_narrow_band` activity types | `mmm_activity.py` | Band contraction + narrow band |

**Test:** `curl http://localhost:5555/api/mmm/session/<id>/breakeven` returns valid result with `from_cache` flag.

### Phase 2: Aggression Multiplier Integration
**Goal:** Lot calculation is boosted when spot approaches breakeven.

| Step | Task | Files | Additions from Review |
|------|------|-------|----------------------|
| 2.1 | Add `breakeven_multiplier` parameter to `calculate_lots_to_sell()` | `mmm_engine.py` | Unchanged |
| 2.2 | Add combined multiplier ceiling logic after step 5 in `calculate_lots_to_sell()` | `mmm_engine.py` | **NEW** |
| 2.3 | In `_process_adjustment()`, pass multiplier WITHOUT directional check | `mmm_monitor.py` | Simplified (no direction check) |
| 2.4 | Add `emit_breakeven()` or embed in `mmm_heartbeat` | `mmm_websocket.py` | Unchanged |
| 2.5 | Emit breakeven data every heartbeat | `mmm_monitor.py` | Unchanged |
| 2.6 | Log zone transitions and band contractions | `mmm_monitor.py` | Band contraction log |

**Test:** Start session, manually shift spot → verify lot count increases in walkthrough, combined multiplier capped at 3.0.

### Phase 3: Frontend — Settings Dialog
**Goal:** Operator can enable/disable breakeven engine and tune all 7 parameters.

| Step | Task | Files | Additions from Review |
|------|------|-------|----------------------|
| 3.1 | Add "Breakeven Engine" settings group (8 params: remove time value toggle, add combined mult slider, add narrow band threshold) | `MMMSettingsDialog.js` | Revised param set |
| 3.2 | Add tooltips for all 8 parameters | `MMMSettingsDialog.js` | Updated tooltips |

### Phase 4: Frontend — Breakeven Panel
**Goal:** Live dashboard panel showing breakeven band, distances, zone, aggression multiplier, and band contraction warning.

| Step | Task | Files | Additions from Review |
|------|------|-------|----------------------|
| 4.1 | Create `MMMBreakevenPanel.js` component with band contraction indicator | New file | Contraction warning |
| 4.2 | Import and render in `MMMDashboard.js` | `MMMDashboard.js` | Unchanged |
| 4.3 | Subscribe to breakeven data (from `mmm_heartbeat` or dedicated event) | `MMMBreakevenPanel.js` | Unchanged |

---

## 8. HEARTBEAT INTEGRATION POINT

The breakeven computation slots into the heartbeat at Step 5.7 (unchanged from original plan):

```
Step 5    — Cooldown check
Step 5.5  — ATM Shield (close & retreat)
Step 5.6  — Proactive Shift Scanner
Step 5.7  — *** BREAKEVEN ENGINE *** ← HERE
            - compute_breakeven(session, spot_price)  [no fetch_premium_fn param]
            - If cached: ~0.01ms (distance/zone calculation only)
            - If recompute: ~1ms (full scan + bisection)
Step 6    — Evaluate triggers
Step 7    — Process adjustment (uses breakeven multiplier, non-directional)
Step 7.5  — Perp delta hedge
Step 8    — P&L + emit events
```

**Why here?**
- Fresh spot price available (from Step 1)
- P&L data available (from Step 3)
- ATM Shield acted already (Step 5.5) — breakeven reflects post-shield state
- Must compute BEFORE trigger evaluation — multiplier ready for Step 7

**Performance budget:** ~1ms on position changes (full scan), ~0.01ms per heartbeat (cached). No API calls.

---

## 9. WEB UI — SETTINGS DIALOG APPEARANCE

The Breakeven Engine settings section appears in `MMMSettingsDialog.js` positioned AFTER "ATM Shield". Color theme: **deep blue**.

### Settings Layout (Revised):

```
┌─ Breakeven Engine ──────────────────────────────────────────────────┐
│                                                                     │
│  [Toggle] Enable Breakeven Control                                  │
│  ─────────────────────────────────────────────────────────────────── │
│                                                                     │
│  Zone Thresholds (% distance from spot to nearest breakeven)        │
│                                                                     │
│  Warning Zone (%)      [  2.0  ]   ℹ️ Spot within this distance     │
│  Danger Zone (%)       [  1.0  ]      triggers Warning zone         │
│  Critical Zone (%)     [  0.5  ]                                    │
│                                                                     │
│  ─────────────────────────────────────────────────────────────────── │
│                                                                     │
│  Aggression                                                         │
│                                                                     │
│  Max Multiplier        [  3.0  ]   ℹ️ Maximum lot multiplier at     │
│                                       Critical zone boundary        │
│                                                                     │
│  Combined Mult Cap     [  3.0  ]   ℹ️ Caps combined gamma ×        │
│                                       breakeven × trend             │
│                                                                     │
│  ─────────────────────────────────────────────────────────────────── │
│                                                                     │
│  Diagnostics                                                        │
│                                                                     │
│  Narrow Band Threshold [  5.0  ]   ℹ️ Warn when band width falls   │
│                                       below this % of spot          │
│                                                                     │
│  ─────────────────────────────────────────────────────────────────── │
│                                                                     │
│  Advanced                                                           │
│                                                                     │
│  Min Scan Range (%)    [  5.0  ]   ℹ️ Minimum scan width; auto-    │
│                                       expands to cover all strikes  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Tooltip text (revised):**

| Parameter | Tooltip |
|-----------|---------|
| `breakeven_control_enabled` | "Enable real-time breakeven band tracking and defensive aggression. When enabled, the algo calculates where spot would make the portfolio unprofitable and boosts hedging as spot approaches that boundary." |
| `breakeven_warning_pct` | "Distance from nearest breakeven (as % of spot) that triggers Warning zone. At 2% with BTC at $87k, Warning fires when spot is within ~$1,740 of breakeven. Multiplier ramps from 1.0 to 1.3." |
| `breakeven_danger_pct` | "Distance from nearest breakeven that triggers Danger zone. Multiplier ramps from 1.3 to 2.0. Should be less than Warning threshold." |
| `breakeven_critical_pct` | "Distance from nearest breakeven that triggers Critical zone. Multiplier ramps from 2.0 to Max Multiplier. Should be less than Danger threshold." |
| `breakeven_aggression_max` | "Maximum lot multiplier applied in Critical zone. A value of 3.0 means up to 3x normal hedge lots. Still capped by max_lots_per_side, max_total_exposure, and combined multiplier ceiling." |
| `max_combined_lot_multiplier` | "**NEW** — Caps the combined effect of all lot multipliers (gamma-aware × breakeven × trend boost). Prevents compound runaway. A value of 3.0 means the total multiplier never exceeds 3x, even if individual systems want more." |
| `breakeven_scan_range_pct` | "Minimum scan width from spot (% of spot). The engine auto-expands the range to cover all open strikes (120% of furthest strike distance). This parameter acts as a floor. Default 5% is sufficient for most sessions." |
| `breakeven_narrow_band_threshold` | "**NEW** — Diagnostic threshold for narrow band warning. When the breakeven band width falls below this percentage, the UI displays an amber warning chip and an activity log is emitted. Does not trigger automatic responses — the operator decides corrective action. Default 5% warns when both breakevens are within 2.5% of spot (fragile portfolio structure)." |

---

## 10. WEB UI — BREAKEVEN PANEL APPEARANCE

The panel appears on the **main Overview tab** after the Trigger Gauges section.

### Compact View (always visible when session is RUNNING):

```
┌─ Breakeven Band ────────────────────────────────────────────────────┐
│                                                                     │
│  ◀── $82,450 ──────────── $87,150 ──────────── $91,800 ──▶         │
│      Lower BE              SPOT                 Upper BE            │
│                                                                     │
│  ▼ Lower: 5.4% ($4,700)     ▼ Upper: 5.3% ($4,650)                │
│                                                                     │
│  Zone: 🟢 SAFE              Multiplier: 1.0x                       │
│  🟠 Band contracting        (-32% since last shift)                │
│  ⚠️ Narrow Band (4.2%)     Consider reducing exposure  ← NEW       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

The "Band contracting" indicator appears when `band_contracting: true`.
The "Narrow Band" warning appears when `is_narrow_band: true` (width < narrow_band_threshold).

### Zone Color Coding:

| Zone | Color | Accent |
|------|-------|--------|
| SAFE | Green `#4caf50` | Subtle green background |
| WARNING | Amber `#ff9800` | Amber border pulse |
| DANGER | Orange-Red `#f44336` | Red border, slight animation |
| CRITICAL | Deep Red `#d32f2f` | Red background pulse, bold text |

### Expanded View (click to toggle):

```
┌─ Breakeven Band (Expanded) ─────────────────────────────────────────┐
│                                                                     │
│  [Visual bar as above, larger]                                      │
│                                                                     │
│  ┌─────────────┬────────────────┬────────────────┐                  │
│  │             │   Lower        │   Upper         │                  │
│  ├─────────────┼────────────────┼────────────────┤                  │
│  │ Breakeven   │  $82,450       │  $91,800        │                  │
│  │ Distance    │  5.4% ($4,700) │  5.3% ($4,650)  │                  │
│  │ Nearest     │  ← this side   │                 │                  │
│  └─────────────┴────────────────┴────────────────┘                  │
│                                                                     │
│  Zone: SAFE        Band Width: 10.7% ($9,350)                      │
│  Aggression: 1.0x  Positions: 6 (4 active + 2 frozen)              │
│  Perp Hedge: Included (long 5 lots)                                │
│                                                                     │
│  P&L at Spot: +$12.40          Realized: +$8.20                    │
│  Cached: Yes (computed 3 beats ago)   ← NEW                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Heartbeat WebSocket Event:

Embed in `mmm_heartbeat` payload:

```python
'breakeven': {
    'enabled': True,
    'lower': 82450.0,
    'upper': 91800.0,
    'distance_lower_pct': 5.4,
    'distance_upper_pct': 5.3,
    'nearest_side': 'upper',
    'zone': 'SAFE',
    'multiplier': 1.0,
    'band_width_pct': 10.7,
    'band_contracting': False,         # NEW — Review 1
    'is_narrow_band': False,           # NEW — Final Review
    'pnl_at_spot': 12.40,
    'from_cache': True,                # NEW — Review 1
}
```

---

## 11. EDGE CASES AND ROBUSTNESS

### 11.1 Handled Scenarios

| Scenario | Behavior |
|----------|----------|
| No positions | Skip computation, return `zone='SAFE'`, `multiplier=1.0` |
| Only one side has positions | One breakeven exists, other is `None` → Safe on that side |
| All positions frozen (after shift) | Still compute — frozen positions have real risk |
| Spot already past breakeven | `distance = 0`, `zone = CRITICAL`, `multiplier = max` |
| Rapid spot movement | Distance/zone recalculated every heartbeat — no stale data |
| Very wide band | `zone = SAFE`, `multiplier = 1.0` — no overhead |
| Perp hedge active | Perp P&L offsets directional losses, shifts breakeven band |
| Distant frozen strikes | Dynamic scan range expands to cover (120% beyond furthest) |
| Position-changing events | Cache invalidated, full scan on next heartbeat (~1ms) |
| Position unchanged | Cached breakeven prices reused (~0.01ms per heartbeat) |
| 0DTE near expiry | Intrinsic-only model is essentially exact |
| Multi-DTE far from expiry | Intrinsic-only is conservative (early warnings) |

### 11.2 Performance Guarantees

| Metric | Target | Actual |
|--------|--------|--------|
| CPU time on position change | < 5ms | ~1ms (full scan) |
| CPU time per heartbeat (cached) | < 0.1ms | ~0.01ms (distance calc) |
| Memory allocation | Minimal | Reuses position list, no large arrays |
| API calls | Zero | All data from in-memory session state |
| GC pressure | Low | Uses floats, no Decimal in hot path |

**Why no Decimal:** The breakeven engine is a risk-awareness heuristic. IEEE 754 float precision ($0.01 error on $87,000) is perfectly acceptable.

### 11.3 Circuit Breaker Interaction

The breakeven engine does NOT rely on live premium fetches (intrinsic-only model). If the circuit breaker is OPEN:
- The engine still computes breakevens (uses only strikes, spot, entry_premiums — all in-memory)
- No stale data warning needed
- The multiplier continues to apply normally

This is an improvement over the original plan, which would have needed live premium data and suffered degraded accuracy during API outages.

---

## 12. TESTING STRATEGY (Revised)

### 12.1 Unit Tests (sealed)

| Test | What it verifies | Status |
|------|-----------------|--------|
| `test_pnl_at_spot_short_call` | PnL formula for short call at various spots (intrinsic-only) | Updated |
| `test_pnl_at_spot_short_put` | PnL formula for short put at various spots (intrinsic-only) | Updated |
| `test_breakeven_straddle` | Classic straddle: breakevens = strike ± total_premium | Updated for intrinsic |
| `test_breakeven_with_frozen` | Frozen positions shift the breakeven band | Unchanged |
| `test_breakeven_with_perp` | Perp hedge asymmetrically shifts breakevens | Unchanged |
| `test_zone_classification` | Zone thresholds correctly classify distances | Unchanged |
| `test_multiplier_continuity` | Multiplier is continuous across zone boundaries | Unchanged |
| `test_no_positions` | Empty portfolio returns SAFE with multiplier 1.0 | Unchanged |
| `test_edge_spot_past_breakeven` | Spot outside band → CRITICAL | Unchanged |
| `test_binary_search_convergence` | Convergence within $10 in ≤ 20 iterations | Unchanged |
| `test_dynamic_scan_range` | **NEW** — Range expands to cover distant strikes | New |
| `test_cache_invalidation` | **NEW** — Breakeven recalculates after adjustment | New |
| `test_cache_reuse` | **NEW** — Same breakeven returned when positions unchanged | New |
| `test_combined_multiplier_ceiling` | **NEW** — gamma × breakeven × trend capped at max_combined | New |
| `test_band_contraction_detection` | **NEW** — `band_contracting` flag when band shrinks >30% | New |

**Removed:** `test_multiplier_directional` — no longer applicable (non-directional design)

### 12.2 Integration Tests

| Test | What it verifies | Status |
|------|-----------------|--------|
| `test_heartbeat_includes_breakeven` | Breakeven result present in session after heartbeat | Unchanged |
| `test_lot_boost_in_danger_zone` | `calculate_lots_to_sell` returns more lots with multiplier > 1 | Unchanged |
| `test_safety_caps_override_multiplier` | Multiplied lots still clamped by `max_lots_per_side` | Unchanged |
| `test_disabled_returns_1x` | When `breakeven_control_enabled=false`, multiplier = 1.0 | Unchanged |
| `test_combined_mult_prevents_runaway` | **NEW** — With gamma=1.3, breakeven=3.0, trend=2.0, combined capped at 3.0 | New |

---

## 13. INTERACTION WITH EXISTING MODULES

| Module | Interaction | Direction | Notes |
|--------|------------|-----------|-------|
| **ATM Shield** | Shield fires first (Step 5.5), then breakeven recalculates next beat with post-shield positions | Shield → Breakeven | Cache invalidated after shield fire |
| **Regime** | Regime blocks override multiplier (sells blocked = multiplier irrelevant) | Regime > Breakeven | Unchanged |
| **Margin Guardian** | YELLOW+ blocks sells entirely — multiplier has no effect | Margin > Breakeven | Unchanged |
| **Whipsaw Guard** | RESTRICT halves lots AFTER multiplier — counterweight | Whipsaw dampens Breakeven | Unchanged |
| **Perp Hedge** | Perp position included in P&L curve — shifts breakeven band | Perp feeds Breakeven | Cache invalidated after perp fill |
| **Strike Shift** | New strike changes position landscape — breakeven recalculates next beat | Shift → Breakeven | Cache invalidated |
| **Close-at-5** | Closed positions removed — breakeven band widens (positive) | Close → Breakeven | Cache invalidated |
| **M1 Harvest** | Harvested frozen positions removed — breakeven band widens | Harvest → Breakeven | Cache invalidated |
| **M2 Recycle** | Recycled positions change strikes — breakeven band shifts | Recycle → Breakeven | Cache invalidated |
| **Split Ledger** | Frozen positions still included in breakeven PnL curve (real risk) | Split Ledger consistent | Unchanged |
| **Wind-down** | Breakeven still computes during wind-down, aggression less useful (positions being closed anyway) | Coexist | Unchanged |
| **Trend Guard** | Trend BLOCK_ALL_SELLS makes multiplier moot; Tier 1 lot reduction applied AFTER breakeven multiplier | Trend dampens Breakeven | Combined mult ceiling prevents stacking |
| **Gamma-Aware** | Gamma multiplier applied BEFORE breakeven multiplier | Both amplify | Combined mult ceiling prevents stacking |

---

## 14. SUMMARY

| Aspect | Original Plan | Revised Plan | Change Reason |
|--------|--------------|--------------|---------------|
| **P&L model** | Time value approximation | Intrinsic-only | Simpler, faster, conservative, no live fetches |
| **Scan range** | Fixed ±8% | Dynamic (120% beyond furthest strike) | Catches distant frozen positions |
| **Multiplier logic** | Directional (hedge_side check) | Non-directional | Simpler, correct (original had mapping bug) |
| **Stacking protection** | None | Combined multiplier ceiling (3.0x default) | Prevents gamma × breakeven × trend runaway |
| **Caching** | None | Position-change caching | ~50-100x performance improvement |
| **Parameters** | 7 (incl. time value toggle) | 8 (removed toggle, added combined mult + narrow band) | Cleaner set, added diagnostics |
| **New files** | 2 (engine + panel) | 2 (engine + panel) | Unchanged |
| **Modified backend files** | 7 | 7 | Unchanged |
| **Modified frontend files** | 2 | 2 | Unchanged |
| **Performance cost** | < 5ms per heartbeat | ~1ms on position change, ~0.01ms cached | Better than original estimate |
| **Safety impact** | Zero (only boosts intent) | Zero (only boosts intent, capped by combined ceiling) | Improved safety |
| **Phases** | 4 | 4 | Unchanged |

**Recommendation:** Proceed with implementation using the revised architecture. The corrections address real issues (directional logic bug, multiplier stacking risk, missed distant strikes) while maintaining the original plan's structurally sound foundation. The revised design is strictly superior — simpler, safer, faster, better coverage.

---

## 15. FINAL VALIDATION REVIEW

After completing the first review incorporating 8 suggestions, a final validation pass evaluated 3 additional critiques to ensure the design meets production standards.

### 15.1 Final Critique Summary

| # | Critique | Verdict | Outcome |
|---|----------|---------|---------|
| **1** | Distance velocity | **INCORRECT** | Rejected — redundant with trend detection system (already tracks spot velocity + acceleration). Would add 3-4 parameters for marginal benefit. MMM already monitors faster (60s intervals) when premiums approach triggers. System gets 3-4 heartbeat cycles in WARNING zone even at rapid $500/min velocity. |
| **2** | Band width aggression | **PARTIALLY CORRECT** | Observation valid (narrow bands = fragile), but automatic multiplier scaling would create positive feedback loop. **Adopted as diagnostic warning** — added `is_narrow_band` flag, amber warning chip, activity log, `breakeven_narrow_band_threshold` param. Operator sees warning and decides corrective action (pause, reduce exposure, close positions). |
| **3** | Perp cache invalidation | **ALREADY CORRECT** | Design already includes "perp fill" in cache invalidation list. All perp state changes (open/close/rebalance/flip) go through fills → trigger `invalidate_cache()`. Validation check confirmed completeness. |

### 15.2 Why Distance Velocity Was Rejected

**The MMM system already has two velocity-responsive mechanisms:**

| System | Velocity Response | How It Works |
|--------|------------------|--------------|
| **Adaptive Interval** | Premium velocity detection | When premiums rise rapidly (approaching triggers), heartbeat interval drops from 300s → 120s → 60s. Monitors more frequently when action is imminent. |
| **Trend Detection** | Spot velocity + acceleration | Tracks spot price EMA and raw velocity. Escalates through 4 tiers (0.5% → 1.0% → 1.5% → 2.0% moves). Tier 2+ blocks dangerous-side sells. Tier 1 reduces lots by 30%. |

For the intrinsic-only cached model: `distance_velocity = spot_velocity - breakeven_velocity`. Since `breakeven_velocity = 0` between position changes, `distance_velocity ≈ spot_velocity` (already tracked by trend detection).

**Timing analysis showed "reacting too late" concern is unfounded:**
- WARNING zone = 2.0% distance (~$1,740 buffer at $87k)
- DANGER zone = 1.0% distance (~$870 buffer)
- At rapid $500/min velocity: 3.5 minutes to traverse WARNING → DANGER
- Heartbeat interval in high-activity: 60 seconds
- Result: **3-4 heartbeat cycles in WARNING zone** — adequate response time

Adding velocity would be redundant, noisy (spot price short-term volatility is high), and complex (requires history tracking, smoothing, tuning).

### 15.3 Why Band Width Multiplier Was Rejected But Warning Was Adopted

**The positive feedback loop problem:**
```
Session starts: wide band (30%) → band-width multiplier = 0.67x (reduced)
Session over-adjusts: band narrows to 10% → band-width multiplier = 2.0x (amplified)
Amplified adjustments: more positions added → band narrows to 5% → multiplier = 4.0x
...
```

This creates runaway amplification — the system detects trouble and digs deeper, making the situation worse.

**Narrow bands are a symptom, not a separate risk factor:**

A portfolio with a 4% breakeven band (both boundaries within 2% of spot) shouldn't exist if safeties are working:
- Asymmetry 5:1 reduction (IMP-3) should limit stacking
- Max total exposure cap should block further sells
- Margin guardian YELLOW+ should block sells
- Max-loss / trailing stop should stop the session

If a narrow band exists, the session is already in trouble. The correct response is STOP adjusting and reassess, not AMPLIFY adjustments.

**Diagnostic value is real:** Narrow bands signal fragility. The operator should see this and manually decide corrective action. The enhancement adopted:
- `is_narrow_band` flag in BreakevenResult (true when `band_width_pct < breakeven_narrow_band_threshold`)
- Activity log of type `breakeven_narrow_band` (warning level)
- Amber warning chip on UI: "⚠️ Narrow Band (4.2%) — Consider reducing exposure"
- New parameter: `breakeven_narrow_band_threshold` = 5.0% (hot-reloadable)

### 15.4 Perp Cache Invalidation Validation

The critique asked whether perp hedge changes invalidate the breakeven cache. Verification:

**Design already correct:**
- "perp fill" explicitly listed in dirty events (line 396 of the plan)
- All perp state changes go through `smart_execute()` → fill → `update_perp_state_after_fill()`

| Perp Event | How It Occurs | Covered? |
|-----------|--------------|----------|
| Hedge opened | `smart_execute()` → fill | ✅ Yes |
| Hedge closed | `smart_execute()` → fill | ✅ Yes |
| Lot size changed | `smart_execute()` → fill | ✅ Yes |
| Avg_entry changed | Only changes on fill | ✅ Yes |
| Position flipped | Close + open = 2 fills | ✅ Yes |

The perp's effect on breakeven:
```python
perp_pnl(spot_h) = (spot_h - avg_entry) × lots × LOT_SIZE_BTC
```

Since `avg_entry` and `lots` are static between fills, cached breakeven prices remain valid between fills. The critique validated existing design completeness.

### 15.5 Changes Made From Final Review

**One enhancement adopted:**

**Backend:**
- Added `'breakeven_narrow_band': 'Narrow Breakeven Band'` to `ACTIVITY_TYPES` in `mmm_activity.py`
- Added `is_narrow_band` detection in `_build_result()` in `mmm_breakeven_engine.py`
- Added narrow band warning log in heartbeat loop in `mmm_monitor.py`
- Added `breakeven_narrow_band_threshold` = 5.0 to `DEFAULT_PARAMS` in `mmm_state.py` (hot-reloadable)

**Frontend:**
- Added amber warning chip in `MMMBreakevenPanel.js` when `is_narrow_band` is true
- Added "Narrow Band Threshold (%)" slider in `MMMSettingsDialog.js`

**Testing:**
- Added `test_narrow_band_detection` — verify `is_narrow_band` flag when width < threshold

**Parameter count:** 7 → **8 total** (added `breakeven_narrow_band_threshold`)

**Documentation:**
- Added detailed docstring in `invalidate_cache()` method clarifying perp fill coverage

### 15.6 Architectural Integrity Assessment

**Strengths validated:**
1. ✅ **Intrinsic-only model** — no reliance on live premium fetches, conservative error direction
2. ✅ **Dynamic scan range** — auto-expands to cover distant frozen strikes
3. ✅ **Non-directional multiplier** — correct integration with core trigger system
4. ✅ **Combined multiplier ceiling** — prevents compound stacking
5. ✅ **Position-change caching** — efficient recomputation strategy
6. ✅ **Perp integration** — correctly invalidates cache on perp fills

**No fundamental flaws identified.** Three final critiques either:
- Suggested features already covered by existing MMM systems (velocity → trend detection)
- Suggested automatic controls that would introduce instability (band width multiplier → positive feedback)
- Validated that the design is already correct (perp invalidation)

**The one enhancement adopted** (narrow band warning) adds diagnostic value without introducing control complexity or feedback loops.

### 15.7 Implementation Readiness

✅ **FINAL STATUS: READY FOR IMPLEMENTATION**

The revised architecture, with the narrow band warning enhancement, is complete and internally consistent. All architectural decisions validated against:
- Actual MMM codebase behavior (multiplier chain, trigger system, existing safeties)
- Real-world session scenarios (multi-shift, frozen positions, perp hedge interaction)
- Control system stability principles (negative vs. positive feedback)
- Performance requirements (<5ms budget, caching optimization)

**Final configuration:**
- **New files:** 2 (backend engine + frontend panel)
- **Modified backend files:** 7 (state, config, monitor, engine, websocket, api, activity)
- **Modified frontend files:** 2 (settings dialog, dashboard)
- **Parameters:** 8 (all hot-reloadable)
- **Activity types:** 3 (zone_change, band_contracting, narrow_band)
- **Performance:** ~1ms on position changes, ~0.01ms per heartbeat (cached)
- **Phases:** 4 (engine → multiplier → settings → panel)

**Proceed with implementation.**
