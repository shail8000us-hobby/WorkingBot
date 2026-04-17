# BREAKEVEN CONTEXT

This file is a consolidated combination of multiple documentation and planning files to preserve context for the AI.

## SOURCE FILE: tasks/BREAKEVEN_ENGINE_REVIEW.md

# Breakeven Engine — Technical Review Analysis

> **Purpose:** Evaluate 8 external review suggestions against the original breakeven engine plan
> **Date:** March 15, 2026
> **Approach:** Each suggestion evaluated against the actual MMM codebase, not theoretical assumptions

---

## PART 1: Evaluation of Review Suggestions

---

### Suggestion 1: Use intrinsic-only or live premiums, not time value approximation

**Claim:** The `sqrt(DTE_fraction) * extrinsic` time value model will produce large errors when spot moves far from the strike. Should use intrinsic only or live premiums instead.

**Verdict: PARTIALLY CORRECT**

**What the reviewer gets right:**
The time value approximation `current_extrinsic * sqrt(remaining_DTE_fraction)` was designed for the *current* spot price. When the breakeven scanner evaluates hypothetical spot prices $3,000–$7,000 away from current spot, the extrinsic value profile changes dramatically. An OTM option with $80 of extrinsic at current spot might be deep ITM at `spot + 5000`, where its extrinsic collapses to near zero. The approximation would overstate the option's value at that hypothetical spot (because it carries the current extrinsic forward), which makes the portfolio P&L look *worse* than it is — the breakeven band appears *narrower* than reality.

This error direction (conservative — tighter band than real) is actually acceptable for a risk tool, but it's still an error and the magnitude grows with distance from current spot.

**What the reviewer gets wrong:**
"Use live premiums" is not feasible. The entire point of the breakeven scan is to evaluate PnL at *hypothetical* spot prices. There is no way to fetch live premiums for prices that don't exist yet. Live premiums only exist for the *current* spot price.

**What the reviewer misses — the fundamental insight:**
The existing `compute_unrealized_pnl()` in `mmm_engine.py` uses `(entry_premium - current_premium) * lots * LOT_SIZE_BTC`. This works because `current_premium` is fetched live. But for breakeven scanning, we need `PnL(spot_h)` where `spot_h` varies. We cannot fetch live premiums at hypothetical spots.

**The correct approach: intrinsic-only with a conservative bias.**

For breakeven scanning specifically:
- **Intrinsic-only underestimates the option's value** (ignores remaining time value), which means it *overestimates the seller's loss* at any given spot_h. This produces a **narrower breakeven band** than reality — i.e., the engine thinks the portfolio breaks even *closer to spot* than it actually does.
- This is the **conservative direction** — the engine fires zone warnings earlier than strictly necessary, which is correct for a risk tool.
- For 0DTE sessions with < 2 hours remaining, intrinsic-only is essentially exact.
- For multi-DTE sessions, the conservatism is acceptable (breakeven warnings arrive early rather than late).

**However:** There is one scenario where intrinsic-only produces a *wrong* result. At current spot, the portfolio has substantial extrinsic value on OTM options (where intrinsic = 0). Using intrinsic-only would compute `PnL_at_current_spot` as if all OTM options are worth $0, which is wrong — they have real premium. This would show the portfolio as MORE profitable than it is at current spot, potentially pushing breakevens *further out*.

**Resolution:** Use a **hybrid approach** — at the current spot evaluation point, use the known live premiums (already fetched in Step 1 of the heartbeat). For all other scan points, use intrinsic-only. This anchors the PnL curve to the true value at spot, then uses the conservative intrinsic model for the scan.

**Design change:** Remove the `breakeven_use_time_value` parameter. Replace the time value approximation with intrinsic-only scanning anchored to a live-premium reference point at current spot.

---

### Suggestion 2: Dynamic scan range based on furthest strike distance

**Claim:** The fixed ±8% scan range may miss breakevens if frozen positions exist at distant strikes from prior shifts.

**Verdict: CORRECT**

**Analysis:**

After multiple strike shifts, the session can accumulate frozen positions at strikes far from the current active strikes. Example scenario at BTC $87,000:

- Session starts: CE @ 89,000, PE @ 85,000
- Shift 1: CE shifts to 91,000 (frozen CE @ 89,000)
- Shift 2: CE shifts to 93,000 (frozen CE @ 89,000, 91,000)
- BTC rallies to 92,000: now frozen CE @ 89,000 is $3,000 ITM

The upper breakeven depends on losses from the 89,000 call going deep ITM. At 8% range from $92,000 spot, the scan covers [$84,640, $99,360]. This catches the 89,000 strike, so in this specific case 8% would suffice.

But consider a more extreme scenario with multi-DTE sessions:
- Frozen puts at 75,000 from an early shift
- BTC at 87,000
- Lower scan limit at 8%: 87,000 × 0.92 = $80,040
- The 75,000 put doesn't go ITM until spot drops below 75,000 — well outside the 8% range
- If those puts are large enough, the lower breakeven could be near $75,000

**The fix:** Compute the scan range dynamically:

```python
all_strikes = [pos['strike'] for pos in open_positions]
furthest_strike_distance = max(abs(spot - k) for k in all_strikes) if all_strikes else 0
min_range = furthest_strike_distance * 1.2  # 20% beyond the furthest strike
scan_range = max(spot * (scan_range_pct / 100), min_range)
```

This ensures the scan always covers at least 20% beyond the furthest open strike, while still respecting the configurable `scan_range_pct` as a minimum floor.

**Design change:** Replace fixed `breakeven_scan_range_pct` with a dynamic range that auto-expands based on position spread. Keep the parameter as a minimum floor (not removed — useful for ensuring some minimum scan width even when all strikes are close to spot).

---

### Suggestion 3: Directional aggression logic is incorrect — should only boost the already-decided hedge side

**Claim:** The breakeven engine should not determine which side to hedge. It should only increase the lot count of whatever the core MMM adjustment logic already decided.

**Verdict: CORRECT — and the original plan contains a logic error**

**The bug in the original plan:**

Section 3.3 states:
```
if nearest_side == 'lower' and hedge_side == 'pe':
    apply_multiplier = True   # selling PE pushes lower breakeven further down
```

This is wrong. When spot approaches the **lower** breakeven (spot falling), put premiums rise, PE is the aggressor, and the core MMM logic hedges by **selling CE** (the opposite side). The original plan says the multiplier should apply when `hedge_side == 'pe'`, but the hedge side would be CE in this scenario.

Even if the mapping were corrected, the directional logic is still over-engineering:

**Why the core adjustment logic already handles direction:**
- The trigger system fires when one side's premium rises above the snapshot → that side is the aggressor → the algo sells the *opposite* side
- If spot approaches the lower breakeven, puts go ITM, PE triggers, and the algo sells CE as hedge
- If spot approaches the upper breakeven, calls go ITM, CE triggers, and the algo sells PE as hedge
- The trigger system naturally aligns the hedge with the correct directional response

**The only scenario where direction misaligns** is a reversal — but reversals have their own detection and cooldown logic (`mmm_reversal.py`). Adding a second layer of directional filtering in the breakeven engine creates confusion about which module controls direction.

**The correct design:** The breakeven multiplier should be **non-directional**. When the spot is in a Warning/Danger/Critical zone, ANY triggered adjustment gets the multiplier boost. The core trigger system already ensures the adjustment is on the correct side.

**Additional benefit of non-directional:** Simpler code, fewer edge cases, easier to test. The multiplier becomes a pure function of `(zone, distance)` → `float`, with no dependency on hedge_side.

**Design change:** Remove all directional logic from `get_aggression_multiplier()`. The method signature simplifies from `(result, hedge_side) → float` to `(result) → float`. The multiplier applies to every adjustment uniformly.

---

### Suggestion 4: Multiplier stacking risk — need a combined multiplier cap

**Claim:** Adding a breakeven multiplier to the existing gamma-aware and trend multipliers could create combined multipliers of 4x+, requiring a global cap.

**Verdict: CORRECT**

**Actual multiplier chain analysis** (verified from codebase, `mmm_engine.py` lines 302–505 and `mmm_monitor.py` lines 3072–3103):

Amplifying multipliers applied in sequence:

| Order | Multiplier | Max Value | Default |
|-------|-----------|-----------|---------|
| 0 | Premium buffer | 1.05x | Always on |
| 1 | Gamma-aware (T3-2) | 1.3x | On by default |
| 2 | **Breakeven (proposed)** | **3.0x** | Off by default |
| 3 | Trend boost (IMP-2, safe side) | 2.0x | Off by default |

Worst-case combined amplification: `1.05 × 1.3 × 3.0 × 2.0 = 8.19x`

Even with the trend boost off (its default), `1.05 × 1.3 × 3.0 = 4.10x` is still high. The `max_lots_per_side` cap would clamp this downstream, but if there's headroom (e.g., 60 active lots with cap at 100), 4x of a 10-lot calculation = 40 lots, which fits and would be placed.

**Real risk:** A session in CRITICAL breakeven zone with high gamma excess could sell 4x the "natural" hedge amount. While each individual multiplier has justification, their compound effect may overshoot the premium-collection intent and instead invite unnecessary concentrated risk.

**The solution: Add a combined multiplier ceiling.**

```python
# After all multiplicative modifiers, before the position cap clamps:
combined_mult = gamma_mult * breakeven_mult * trend_mult
max_combined = params.get('max_combined_lot_multiplier', 3.0)
if combined_mult > max_combined:
    # Scale back proportionally
    scale_factor = max_combined / combined_mult
    lots_to_sell = max(math.ceil(lots_to_sell * scale_factor), 1)
```

This is cleaner than reducing each individual multiplier's max — it allows each module to express its full intent while capping the combined effect.

**Design change:** Add `max_combined_lot_multiplier` parameter (default 3.0, range 1.5–5.0, hot-reloadable). Apply in `calculate_lots_to_sell()` after all multiplicative modifiers but before the position cap clamps.

---

### Suggestion 5: Recompute breakeven only when positions change, not every heartbeat

**Claim:** The full scan+bisection is wasted if positions haven't changed. Only recompute when adjustments, shifts, harvests, recycles, or perp changes occur.

**Verdict: PARTIALLY CORRECT**

**What changes between heartbeats:**

| Component | Changes every heartbeat? | Affects breakeven? |
|-----------|------------------------|-------------------|
| Open positions (lots, strikes) | No (only on adjustment/shift/close) | Yes — determines P&L curve shape |
| Realized P&L | No (only on close events) | Yes — vertical shift of PnL curve |
| BTC spot price | Yes | Yes — determines distance to breakeven, NOT breakeven location |
| Perp unrealized P&L | Yes (mark-to-market) | Yes — shifts PnL curve based on spot |

**The split optimization:**

The breakeven PRICES (lower/upper) depend on:
- Position layout (strikes, lots, entry premiums) — **changes rarely**
- Realized PnL — **changes rarely**
- Premium-to-spot relationship — for intrinsic-only model, this is deterministic given strikes

For an **intrinsic-only model**, the PnL(spot_h) function depends ONLY on strikes, lots, entry_premiums, realized_pnl, and perp_state. The breakeven prices are deterministic from this data and only change when positions change.

The DISTANCE from spot to breakeven changes every heartbeat because spot moves, but this is a trivial subtraction, not a scan.

**Correct optimization:**

```
On position change (adjust/shift/close/harvest/recycle/perp fill):
  → Run full scan+bisection → cache breakeven prices
  → Set _breakeven_dirty = False

Every heartbeat:
  → If _breakeven_dirty: run full scan
  → Else: reuse cached breakeven prices
  → Always: recompute distance, zone, multiplier from cached breakevens + current spot
```

**What about the perp hedge?** The perp's unrealized P&L changes every heartbeat because `(mark_price - avg_entry) * lots * LOT_SIZE_BTC` depends on current spot. However, in the intrinsic-only breakeven model, the perp term is `(spot_h - avg_entry) * lots * LOT_SIZE_BTC` — this is a linear function of spot_h, and its effect on breakeven location can be computed algebraically once (it shifts both breakevens by the same amount). So the perp P&L does NOT require a rescan.

**Conclusion:** Full scan ~2–3 times per session (on adjustments/shifts). Distance/zone computation every heartbeat (trivial arithmetic). This is a ~50-100x reduction in scan frequency.

**Design change:** Add position-change dirty flag. Cache breakeven prices. Recompute distances every heartbeat from cache. Mark dirty on: adjustment fill, strike shift, close-at-5, harvest, recycle, perp fill, operator inject, adopt.

---

### Suggestion 6: The "use time value" toggle is unnecessary complexity

**Claim:** The parameter complicates the operator interface for marginal benefit.

**Verdict: CORRECT**

This follows directly from the resolution of Suggestion 1. If we adopt intrinsic-only scanning (with live-premium anchoring at current spot), there is no time-value model to toggle. The parameter becomes meaningless.

Even if we had kept two modes, forcing the operator to choose between "intrinsic" and "time value model" is a pricing engine decision that operators should never be exposed to. The engine should auto-select the appropriate model internally based on DTE, not expose it as a knob.

**Design change:** Remove `breakeven_use_time_value` parameter entirely. Parameter count drops from 7 to 6. Add `max_combined_lot_multiplier` to bring count back to 7.

---

### Suggestion 7: The <5ms performance estimate is optimistic

**Claim:** The number of position evaluations during the scan may exceed what can be done in 5ms.

**Verdict: INCORRECT**

**Actual computation cost analysis:**

The coarse scan evaluates ~80 sample points. At each point, for each open position, the computation is:

```python
# Per call position:
intrinsic = max(spot_h - strike, 0)
pnl = (entry_premium - intrinsic) * lots * LOT_SIZE_BTC

# Per put position:
intrinsic = max(strike - spot_h, 0)
pnl = (entry_premium - intrinsic) * lots * LOT_SIZE_BTC
```

This is 3 float operations per position per sample point.

With 20 positions (a session with several shifts and adjustments), that's:
- Coarse scan: 80 × 20 × 3 = 4,800 float ops
- Binary search (2 searches × 20 iterations): 40 × 20 × 3 = 2,400 float ops
- Total: ~7,200 float ops

CPython executes simple float arithmetic at approximately 5–10 million operations per second. 7,200 operations = **~1ms**.

Even with Python overhead (function call dispatch, list iteration, dict lookups), this comfortably fits within 5ms. This is pure arithmetic on in-memory data — no I/O, no API calls, no Decimal conversion.

With Suggestion 5 adopted (cache breakevens, only rescan on position changes), the per-heartbeat cost drops to a handful of float subtractions — effectively **< 0.01ms**.

**The 5ms estimate is actually conservative, not optimistic.**

**Design change:** None. Keep the <5ms target. With caching, it's even faster than estimated.

---

### Suggestion 8: Missing detection of rapidly shrinking breakeven bands

**Claim:** If the breakeven band width contracts quickly, it signals accelerating risk and the algorithm should reduce aggression.

**Verdict: PARTIALLY CORRECT — the observation is valuable but the prescribed action is wrong**

**The observation is valid:**
A rapidly contracting breakeven band means the portfolio is losing money faster than it's gaining. This can happen when:
- Aggressive adjustments stack lots on one side (each adjustment adds a new position whose loss grows with further spot movement)
- A trend move makes multiple frozen positions go deep ITM simultaneously
- The perp hedge direction flipped and now amplifies losses instead of offsetting them

Tracking band width velocity is useful diagnostic data.

**The prescribed action is wrong:**
The reviewer says "reduce aggression" when the band contracts. This is backwards:

- A contracting band means spot is approaching a breakeven → the zone escalates → the multiplier *should* increase hedging
- Reducing aggression when the band contracts means selling *fewer* hedge lots precisely when the portfolio needs *more* protection
- The entire thesis of the breakeven engine is to hedge MORE aggressively as breakeven approaches — reducing aggression contradicts the feature's purpose

**What SHOULD happen on rapid band contraction:**
The existing safety systems already handle the underlying causes:

| Cause | Existing Response |
|-------|------------------|
| Lot stacking on one side | Asymmetry 5:1 reduction (IMP-3) kicks in |
| Trend move | Trend guard escalates tiers → blocks dangerous-side sells |
| Margin pressure | Margin guardian escalates → blocks all sells |
| Whipsaw (flip-flopping) | Whipsaw guard → widened triggers → halved lots → cooldown |
| P&L deterioration | Max-loss stop, trailing-stop protection |

Adding a band contraction detector as another control mechanism risks conflicting with these existing systems.

**What IS valuable:** Adding `band_width_pct` and `band_width_velocity` (change over last N heartbeats) as **diagnostic data** in the breakeven result. The UI can display this, and the operator can use it to manually tune parameters. Also worth logging as an activity when band contracts by more than 30% within a few heartbeats.

**Design change:** Add `band_width_velocity` to the BreakevenResult. Emit a `breakeven_band_contracting` activity log when band width shrinks by more than 30% since last recomputation. No automated aggression reduction — leave that to the existing safety stack.

---

## PART 2: Revised Breakeven Engine Design

Based on the analysis above, here is the corrected architecture:

### 2.1 P&L Model: Intrinsic-Only with Live Anchor

```
PnL(spot_h) = Σ position_pnl(pos, spot_h) + realized_pnl + perp_pnl(spot_h)

For SHORT CALL at strike K, entry_premium P, lots N:
  intrinsic(spot_h) = max(spot_h - K, 0)
  position_pnl = (P - intrinsic(spot_h)) * N * LOT_SIZE_BTC

For SHORT PUT at strike K, entry_premium P, lots N:
  intrinsic(spot_h) = max(K - spot_h, 0)
  position_pnl = (P - intrinsic(spot_h)) * N * LOT_SIZE_BTC

For PERP HEDGE with signed lots L at avg_entry E:
  perp_pnl(spot_h) = (spot_h - E) * L * LOT_SIZE_BTC
```

**Conservative bias:** Intrinsic-only ignores remaining extrinsic value, which makes options appear *more expensive* to buy back than they actually are. This narrows the breakeven band (the engine thinks the portfolio breaks even closer to spot than reality). For a risk-awareness tool, early warnings are better than late warnings.

### 2.2 Dynamic Scan Range

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

### 2.3 Non-Directional Aggression Multiplier

The multiplier is a pure function of `(zone, nearest_distance_pct, params)`:

```python
def get_aggression_multiplier(self, breakeven_result):
    """Returns multiplier ≥ 1.0. Applied to ALL adjustments regardless of side."""
    if not breakeven_result or breakeven_result['zone'] == 'SAFE':
        return 1.0
    return breakeven_result['multiplier']
```

The linear interpolation formula from the original plan remains unchanged. The `hedge_side` parameter is removed.

### 2.4 Combined Multiplier Ceiling

In `calculate_lots_to_sell()`, after all multiplicative modifiers:

```python
# Track all multipliers applied
combined_multiplier = gamma_mult * breakeven_mult
if trend_boost_applied:
    combined_multiplier *= trend_boost_mult

max_combined = params.get('max_combined_lot_multiplier', 3.0)
if combined_multiplier > max_combined:
    overshoot = combined_multiplier / max_combined
    lots_to_sell = max(math.ceil(lots_to_sell / overshoot), 1)
```

### 2.5 Position-Change Caching

```python
class BreakevenEngine:
    def __init__(self):
        self._cache = {}  # session_id → {lower, upper, positions_hash, computed_at}

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
            # Positions changed — full scan + bisection
            lower = self._find_breakeven(positions, spot_price, session, 'lower')
            upper = self._find_breakeven(positions, spot_price, session, 'upper')
            self._cache[session_id] = {
                'lower_breakeven': lower,
                'upper_breakeven': upper,
                'positions_hash': pos_hash,
                'band_width_at_compute': ...,  # for velocity tracking
                'computed_at': now,
            }

        # Always recompute: distance, zone, multiplier (trivial arithmetic)
        return self._build_result(lower, upper, spot_price, session)

    def _hash_positions(self, positions, session):
        """Hash of all factors that affect breakeven location."""
        # Strikes, lots, entry_premiums, realized_pnl, perp avg_entry, perp lots
        ...
```

Dirty events that invalidate cache: adjustment fill, strike shift, close-at-5, M1 harvest, M2 recycle, operator inject, adopt, perp fill.

### 2.6 Band Width Velocity Tracking

```python
# In BreakevenResult:
'band_width_pct': float,              # Current band width as % of spot
'band_width_prev_pct': float | None,  # Previous computation's band width
'band_contracting': bool,             # True if band shrunk >30% since last recompute
```

When `band_contracting` is True, log an activity entry of type `breakeven_band_contracting`. No automated response — existing safety systems handle the root causes.

### 2.7 Updated Parameter List

| Parameter | Default | Type | Range | Hot Reload | Change from Original |
|-----------|---------|------|-------|------------|---------------------|
| `breakeven_control_enabled` | `false` | bool | — | Yes | Unchanged |
| `breakeven_warning_pct` | `2.0` | float | 0.5–10.0 | Yes | Unchanged |
| `breakeven_danger_pct` | `1.0` | float | 0.2–5.0 | Yes | Unchanged |
| `breakeven_critical_pct` | `0.5` | float | 0.1–2.0 | Yes | Unchanged |
| `breakeven_aggression_max` | `3.0` | float | 1.5–5.0 | Yes | Min raised to 1.5 |
| `breakeven_scan_range_pct` | `5.0` | float | 2.0–15.0 | Yes | Now a minimum floor; default lowered since dynamic range handles expansion |
| `max_combined_lot_multiplier` | `3.0` | float | 1.5–5.0 | Yes | **NEW** — caps combined gamma × breakeven × trend |

**Removed:** `breakeven_use_time_value` (always intrinsic-only now)

**Total: 7 parameters** (same count, different composition)

### 2.8 Updated Method Signatures

```python
class BreakevenEngine:
    def compute_breakeven(self, session, spot_price) -> dict:
        """Full breakeven analysis. Uses cached breakeven prices if positions unchanged."""

    def get_aggression_multiplier(self, breakeven_result) -> float:
        """Returns multiplier >= 1.0. No directional filtering."""

    def invalidate_cache(self, session_id):
        """Called by monitor after position-changing events."""
```

`compute_breakeven` no longer needs `fetch_premium_fn` — intrinsic-only model uses only strike/spot arithmetic, no live premium fetches.

### 2.9 Updated Heartbeat Integration

```
Step 5.7 — BREAKEVEN ENGINE:
  1. Call compute_breakeven(session, spot_price)
     - If positions unchanged since last call: reuses cached breakevens, recomputes distance/zone (~0.01ms)
     - If positions changed: full scan + bisection (~1ms)
  2. Store _breakeven_result in session
  3. Check for zone transition → log activity if changed
  4. Check band_contracting → log activity if True

Step 7 — PROCESS ADJUSTMENT:
  1. Core trigger logic determines aggressor and hedge_side (unchanged)
  2. calculate_lots_to_sell() receives breakeven_multiplier from _breakeven_result
  3. Combined multiplier ceiling applied inside calculate_lots_to_sell()
```

### 2.10 Updated `calculate_lots_to_sell` Order of Operations

```
 1. raw_lots = loss / (premium × LOT_SIZE_BTC) × (1 + buffer)
 2. lots = ceil(raw_lots)
 3. ×= gamma_aware_multiplier (T3-2)               [1.0 – 1.3]
 4. ×= breakeven_aggression_multiplier              [1.0 – 3.0]  ← NEW
 5. ×= trend_boost (IMP-2, safe side only)          [1.3 – 2.0]  (or trend_reduction 0.1–1.0)
 5a. COMBINED CEILING CHECK                                       ← NEW
     if (gamma × breakeven × trend) > max_combined_lot_multiplier:
       scale lots back proportionally
 6. lots = min(lots, cap_remaining)                 ← max_lots_per_side
 7. lots = min(lots, exposure_remaining)            ← max_total_exposure
 8. lots ×= asymmetry_reduction (IMP-3)
 9. lots ×= otm_scaling (IMP-4)
```

Step 5a is the new combined ceiling. It sits after all multiplicative amplifiers but before all hard caps and reductive modifiers. This ensures:
- Individual modules compute their full intent
- The ceiling prevents combined runaway
- Downstream clamps (position cap, exposure, asymmetry) still apply normally

---

## PART 3: Changes Required to the Original Implementation Plan

### Backend Changes

| File | Original Plan Change | Revised Change | Reason |
|------|---------------------|----------------|--------|
| **`mmm_breakeven_engine.py`** (new) | Time value estimation, fixed 8% scan, directional multiplier | Intrinsic-only model, dynamic scan range, non-directional multiplier, position-change caching, band velocity tracking | Suggestions 1, 2, 3, 5, 8 |
| **`mmm_engine.py`** | Accept `breakeven_multiplier` param | Accept `breakeven_multiplier` param AND add combined multiplier ceiling logic after step 5 | Suggestion 4 |
| **`mmm_state.py`** | 7 params including `breakeven_use_time_value` | 7 params: swap `breakeven_use_time_value` → `max_combined_lot_multiplier` | Suggestions 4, 6 |
| **`mmm_config.py`** | 7 PARAM_RULES | 7 PARAM_RULES (different set: remove time_value, add combined_multiplier) | Suggestions 4, 6 |
| **`mmm_monitor.py`** | Call compute_breakeven with fetch_premium_fn, directional multiplier in _process_adjustment | Call compute_breakeven WITHOUT fetch_premium_fn, pass multiplier directly (no directional check), call invalidate_cache after position-changing events | Suggestions 1, 3, 5 |
| **`mmm_activity.py`** | `breakeven_zone_change` activity type | Add `breakeven_zone_change` AND `breakeven_band_contracting` activity types | Suggestion 8 |
| **`mmm_websocket.py`** | `emit_breakeven()` | Unchanged — add `band_contracting` field to payload |  |
| **`mmm_api.py`** | GET breakeven endpoint | Unchanged |  |

### Frontend Changes

| File | Original Plan Change | Revised Change | Reason |
|------|---------------------|----------------|--------|
| **`MMMSettingsDialog.js`** | 7 params including "Use Time Value" toggle | 7 params: remove time value toggle, add "Max Combined Multiplier" slider | Suggestions 4, 6 |
| **`MMMBreakevenPanel.js`** (new) | Band visualization with zone colors | Add band contraction indicator (pulsing "contracting" warning) | Suggestion 8 |
| **`MMMDashboard.js`** | Import + render panel | Unchanged |  |

### Testing Changes

| Original Test | Revised Test | Reason |
|---------------|-------------|--------|
| `test_multiplier_directional` | **Remove** — no longer applicable | Suggestion 3 |
| — | `test_combined_multiplier_ceiling` — verify gamma × breakeven × trend capped | Suggestion 4 |
| — | `test_dynamic_scan_range` — verify range expands with distant strikes | Suggestion 2 |
| — | `test_cache_invalidation` — verify breakeven recalculates after adjustment | Suggestion 5 |
| — | `test_cache_reuse` — verify same breakeven returned when positions unchanged | Suggestion 5 |
| — | `test_band_contraction_detection` — verify band_contracting flag | Suggestion 8 |
| `test_breakeven_straddle` | Update to use intrinsic-only math | Suggestion 1 |

---

## PART 4: Final Recommendation

**Proceed with revised architecture.** The original plan was structurally sound — the heartbeat integration point, zone classification, linear ramp multiplier, safety-clamp ordering, and module interaction design are all correct. But four suggestions identified real issues that must be fixed before implementation:

1. **Suggestion 1 (Partially Correct):** The time-value approximation was an unnecessary source of error. Intrinsic-only is simpler, faster, conservative (safe direction for risk tool), and removes a confusing operator-facing parameter. Adopt.

2. **Suggestion 2 (Correct):** Fixed scan range was a real gap. Dynamic expansion based on strike spread is a straightforward fix. Adopt.

3. **Suggestion 3 (Correct):** The directional aggression logic contained a mapping error and was conceptually redundant with the core trigger system. The non-directional approach is both simpler and more correct. Adopt.

4. **Suggestion 4 (Correct):** Combined multiplier stacking to 4x+ was a real risk. A combined ceiling parameter is the cleanest solution — it lets each module express intent while bounding the compound effect. Adopt.

Three suggestions were partially valuable:

5. **Suggestion 5 (Partially Correct):** Position-change caching is a valid optimization but the distance/zone calculation must still run every heartbeat. Adopt the split approach.

6. **Suggestion 6 (Correct):** Removing the time-value toggle follows from Suggestion 1. Adopt.

8. **Suggestion 8 (Partially Correct):** Band contraction detection is valuable as diagnostics/alerting, but the prescribed response (reduce aggression) is counterproductive. Adopt the detection, reject the response.

One suggestion was wrong:

7. **Suggestion 7 (Incorrect):** The 5ms estimate is actually conservative. Pure float arithmetic on in-memory data with 20 positions across 80 scan points is ~1ms in Python. With caching, the per-heartbeat cost drops to microseconds.

**Net impact of revisions:**
- Simpler code (removed directional logic, removed time-value model)
- Safer arithmetic (combined multiplier ceiling prevents runaway stacking)
- Better coverage (dynamic scan range catches distant strikes)
- Better performance (position-change caching eliminates redundant scans)
- Same parameter count (7 — composition changed, not quantity)
- Same file count and integration points
- Same 4-phase implementation plan

The revised design is strictly superior to the original. Proceed with implementation using the corrected architecture.


---

## SOURCE FILE: tasks/BREAKEVEN_ENGINE_PLAN.md

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


---

## SOURCE FILE: tasks/BREAKEVEN_DTE_AWARE_PLAN.md

# Breakeven Engine — DTE-Aware Upgrade Plan

> **Feature:** Make breakeven zone thresholds and aggression multipliers dynamic with respect to time remaining to expiry (DTE)
> **Author:** AI Plan — March 16, 2026
> **Status:** IMPLEMENTED + BUG-FIXED — March 16, 2026 (4 post-implementation bugs fixed via code review)
> **Prerequisite:** `tasks/BREAKEVEN_ENGINE_PLAN.md` (already implemented, 436 sealed tests pass)

---

## 1. PROBLEM STATEMENT

The current `mmm_breakeven_engine.py` uses **static** zone thresholds regardless of how many hours remain until expiry:

```
warning=2%, danger=1%, critical=0.5%   # same at 0DTE, same at 5DTE
```

**This is wrong.** A 1% distance from the intrinsic breakeven at 5DTE is fundamentally different from 1% at 0DTE:

| DTE | Remaining time value (ATM BTC, σ≈80%) | Meaning of "1% from intrinsic breakeven" |
|-----|---------------------------------------|------------------------------------------|
| 5DTE (120h) | ~3.0% of spot (~$2,400 on $80k BTC) | Option still has ~$2,400 extrinsic. Real market breakeven is ~3% further out. This trigger is a **false alarm**. |
| 1DTE (24h) | ~1.3% of spot (~$1,040) | Moderate. Real breakeven shifted ~1.3% out. Should alert but not panic. |
| 4h | ~0.3% of spot (~$240) | Option nearly pure intrinsic. This is a **real alarm**. |
| 0DTE | ~0% | Intrinsic model is exact. Full aggression appropriate. |

The intrinsic-only P&L model (deliberate design choice — it's correct and conservative) computes breakeven using only intrinsic value. This is *intentionally pessimistic*, but at 5DTE that pessimism is so large that:

1. **False alarms**: WARNING/CRITICAL triggered hours before real risk exists → bot over-adjusts
2. **Over-accumulation at 5DTE**: Aggressive lot additions at 5DTE when market hasn't truly threatened breakeven
3. **Asymmetric behavior**: 0DTE session behaves correctly; 5DTE session is too twitchy at the start

---

## 2. PROFESSIONAL DESK PRACTICES (RESEARCH FINDINGS)

### 2.1 Black-Scholes √T Foundation

The canonical insight from BSM: for an ATM option, time value scales with **√T**:

```
ATM Time Value ≈ S × σ × √T / √(2π)
```

where T is time to expiry in years, σ is annualised volatility.

For BTC (σ ≈ 80%, S = $80,000):
- T = 5 days: TV ≈ $80,000 × 0.8 × √(5/365) / √(2π) ≈ **$2,368** (~2.96% of spot)
- T = 1 day: TV ≈ **$1,063** (~1.33% of spot)
- T = 4 hours: TV ≈ **$488** (~0.61% of spot)
- T = 0.5 hours: TV ≈ **$173** (~0.22% of spot)

This is the extrinsic value that the intrinsic-only model ignores. **The breakeven band must be wider early in the session by exactly this much.**

### 2.2 Tastytrade / Retail-Pro Frameworks

- **45 DTE → 21 DTE rule**: Enter short premium at 45 DTE, close at 21 DTE. The reason: at 21 DTE, gamma starts accelerating relative to theta — risk/reward ratio deteriorates.
- **50% profit close**: Take profits at 50% premium captured. This is DTE-independent but implies the same philosophy: close before gamma risk dominates.
- **2× standard deviation as adjustment trigger**: Professional desks often set stop-loss/adjustment at the short strike (at the money) going 2σ OTM at entry, then adjusting when the position approaches 1σ.

### 2.3 Gamma Explosion Near Expiry

Gamma for ATM options scales as:

```
Γ_ATM ≈ 1 / (S × σ × √T × √(2π))
```

- Gamma is inversely proportional to √T
- At 0DTE, gamma is ~5× higher than at 1DTE
- At 0DTE, a 1% move in spot produces ~5× more delta change than at 1DTE

This confirms: near-expiry options are inherently more dangerous for the same intrinsic distance. So the **correct behavior is the opposite of false-alarms at 5DTE** — at 5DTE, widen the safe zone; at 0DTE, keep it tight.

### 2.4 The √T Scaling Rule

Industry standard for scaling time-based risk bands:

```
effective_threshold = base_threshold × (1 + (max_mult - 1) × √(t_ratio))
```

where `t_ratio = hours_remaining / total_dte_hours` (1.0 at session start, 0.0 at expiry).

This is the **same family of formulas** that professional vol desks use to scale VaR windows and options desk Greeks across time horizons.

### 2.3 BTC-Specific Context (Research Finding — Critical)

> **At 80-100% IV (typical for BTC), daily σ ≈ 5%. A 5-day expected move is ~11%. Your current 0.5-2% static thresholds are dramatically too tight for high-DTE BTC options and only appropriate for 0-1DTE scenarios.**
> — Research finding, confirmed by BS ATM straddle formula

| BTC IV | Daily σ | 5-day expected move | Current "danger" threshold (1%) | Danger as % of expected move |
|--------|---------|--------------------|---------------------------------|------------------------------|
| 80% | 5.04% | 11.3% | 1% | **8.8% of expected move** → almost never triggers |
| 80% | 5.04% | 11.3% | 1% × 2.0 DTE-scaled = 2% | **17.7%** — more reasonable |
| 40% | 2.52% | 5.6% | 1% | 17.9% → still tight |

This reinforces that for 5DTE BTC options at typical IV, the base thresholds of 1-2% are extremely conservative. The IV-based scaling (Tier 4 below) is the most accurate long-term fix.

### 2.4 The Tastytrade 21 DTE Inflection — Confirmed

Gamma at ATM scales as 1/√T. Relative to a 21 DTE baseline:

| DTE | Relative Gamma | Implication |
|-----|---------------|-------------|
| 21 | 1.0× | management window opens |
| 7 | 1.73× | act faster |
| 3 | 2.65× | aggressive intervention |
| 1 | 4.58× | near-binary behavior |
| 0DTE | explosive | maximum urgency |

Inside 21 DTE, gamma risk dominates over theta benefit — this is the professional close/hedge window. Our 5DTE sessions are already inside this window. 0DTE sessions are in the extreme zone.

### 2.5 Cumulative Theta Decay by DTE

```
Fraction of premium captured from DTE_start to DTE_end = 1 - √(DTE_end / DTE_start)
```

| Hold from | To | Premium Captured |
|-----------|----|-----------------|
| 5DTE | 0DTE | 100% |
| 5DTE | 1DTE | 55% captured, 45% remains as buffer |
| 5DTE | 3DTE | 22% captured, 78% remains |

At 3DTE of a 5DTE session, 78% of the remaining extrinsic is still working as a buffer. The intrinsic-only model ignores this entirely.

---

## 3. AUDIT OF CURRENT CODE

### 3.1 What is currently in `mmm_breakeven_engine.py`

| Component | Current Behavior | Problem |
|-----------|-----------------|---------|
| `_classify_zone()` | Static thresholds from `params` | Ignores DTE entirely |
| `_compute_multiplier()` | Static ramp from static thresholds | Ignores DTE entirely |
| `compute_breakeven()` | Passes `session` dict into zone/multiplier | Session has `expiry_time` and `total_dte_hours` — available but unused |
| `_compute_pnl_at_spot()` | Intrinsic-only | Correct design, but conservative → wide underestimate at 5DTE |
| `_hash_positions()` | Hashes positions+realized+perp | Does NOT include time → breakeven won't recompute as time changes |

### 3.2 What already exists in session state

From `mmm_state.py` and `mmm_monitor.py`:
- `session['expiry_time']` — datetime in UTC (set at session creation)
- `session['params']['total_dte_hours']` — total hours from creation to expiry
- `session['params']['dte_category']` — `'0DTE'` or `'5DTE'`
- `monitor._get_minutes_to_expiry()` — already computed every heartbeat

All required data is already present. **This upgrade requires only changes to `mmm_breakeven_engine.py`, `mmm_config.py`, `mmm_state.py`, and `mmm_dte_presets.py`.**

### 3.3 Cache invalidation gap

The current cache invalidates on **position change** only. Time passing is not a cache miss trigger.

For threshold scaling, time-based recompute is not required at every beat — the `_build_result()` call runs every beat and recomputes `dte_scale` from `hours_remaining` inline. But the **cached breakeven prices** (lower/upper) are computed from position data only. Since the P&L model is intrinsic-only, the breakeven prices don't change with time (only with positions). This is still correct — only the **zone classification** changes with time.

**Fix**: compute `dte_scale` inside `_build_result()` (not `_classify_zone()`), using fresh `hours_remaining` on every call, even from cache. The breakeven prices are cached; the zone derived from them is NOT separately cached — it's recomputed from the prices every time.

This means: **no cache invalidation change needed for DTE scaling.** Zone and multiplier are already recomputed every heartbeat.

### 3.4 Code quality issues found during audit

1. `_classify_zone()` and `_compute_multiplier()` are called without `session` — they receive only `params` and `nearest_distance_pct`. The DTE scale needs to come from `session`, so these methods need `dte_scale` as a parameter or `session` needs to be threaded through.

2. `_build_result()` already has access to `session` — the correct place to compute `dte_scale` and pass it into `_classify_zone()` / `_compute_multiplier()`.

3. There is no `breakeven_dte_threshold_mult` parameter defined in `DEFAULT_PARAMS` or `mmm_config.py` — needs to be added.

4. `PRESET_0DTE` and `PRESET_5DTE` in `mmm_dte_presets.py` do not set any breakeven parameters — they override the base breakeven thresholds implicitly through defaults. Adding DTE-specific breakeven params to the presets would auto-configure correctly at session creation.

---

## 4. PROPOSED SOLUTION: THREE-TIER UPGRADE

### Tier 1 — DTE-Scaled Zone Thresholds (HIGH PRIORITY, CORE FIX)

**Formula:**
```python
t_ratio = min(hours_remaining / total_dte_hours, 1.0)  # 1.0 at start, 0.0 at expiry
dte_scale = 1.0 + (breakeven_dte_threshold_mult - 1.0) * math.sqrt(t_ratio)

effective_warning_pct  = breakeven_warning_pct  * dte_scale
effective_danger_pct   = breakeven_danger_pct   * dte_scale
effective_critical_pct = breakeven_critical_pct * dte_scale
```

**Behavior for a 5DTE session (120h), `dte_threshold_mult=2.0`, base thresholds 2%/1%/0.5%:**

| Hours remaining | t_ratio | dte_scale | warning | danger | critical |
|----------------|---------|-----------|---------|--------|----------|
| 120h (start) | 1.00 | 2.00 | 4.0% | 2.0% | 1.0% |
| 96h | 0.80 | 1.89 | 3.8% | 1.9% | 0.95% |
| 72h (3DTE) | 0.60 | 1.77 | 3.5% | 1.77% | 0.89% |
| 48h (2DTE) | 0.40 | 1.63 | 3.3% | 1.63% | 0.82% |
| 24h (1DTE) | 0.20 | 1.45 | 2.9% | 1.45% | 0.72% |
| 6h | 0.05 | 1.22 | 2.4% | 1.22% | 0.61% |
| 2h | 0.017 | 1.13 | 2.3% | 1.13% | 0.57% |
| 0h (expiry) | 0.00 | 1.00 | 2.0% | 1.0% | 0.5% |

**For a 0DTE session with `dte_threshold_mult=1.0`:**
- dte_scale is always 1.0 → exact same behavior as today

**New config param:** `breakeven_dte_threshold_mult`
- Type: float, 1.0–5.0, hot-reloadable
- Default: 1.0 (backward-compatible, no change to existing sessions)
- PRESET_5DTE: 2.0
- PRESET_0DTE: 1.0 (explicit no-op)

### Tier 2 — DTE-Scaled Aggression Ceiling (MEDIUM PRIORITY)

At early DTE, even when thresholds are crossed, the bot should be slightly less aggressive because:
- More time for market to reverse
- Higher premium remaining means partial close is available
- Gamma risk is lower

**Formula:**
```python
dte_aggression_damp = 1.0 - (breakeven_dte_aggression_damp * math.sqrt(t_ratio))
# damp is between 0.0-0.4 (e.g., 0.2 = 20% reduction in max_mult at session start)
effective_max_mult = max(breakeven_aggression_max * dte_aggression_damp, 1.5)
```

For `damp=0.2`, `max_mult=3.0`:
- At 5DTE start: effective max = 3.0 × 0.8 = 2.4
- At 1DTE: effective max = 3.0 × 0.91 = 2.73
- At 0DTE: effective max = 3.0 × 1.0 = 3.0 (full)

**New config param:** `breakeven_dte_aggression_damp`
- Type: float, 0.0–0.4, hot-reloadable
- Default: 0.0 (backward-compatible)
- PRESET_5DTE: 0.2

### Tier 3 — Time-Value Credit in P&L Model (LOW PRIORITY, OPTIONAL)

This is the most accurate improvement but the most complex. It shifts the computed breakeven prices (lower/upper) outward to account for remaining time value, rather than relying on threshold scaling alone.

**Concept:**
```python
# For each position, add a time-value credit to the entry_premium
# credit = entry_premium × tv_credit_factor × sqrt(t_ratio)
effective_entry_prem = entry_prem * (1 + tv_credit_factor * sqrt(t_ratio))
```

**Why keep it optional:**
- Introduces estimation error (we don't know what fraction of entry premium was time value vs intrinsic at entry)
- Deep ITM positions have low time value regardless of DTE
- The Tier 1 threshold scaling already achieves the same practical effect with less model risk
- Recommended: implement only after Tier 1 is validated in live sessions

**New config param:** `breakeven_tv_credit_factor`
- Type: float, 0.0–0.5, hot-reloadable
- Default: 0.0 (disabled)
- PRESET_5DTE: 0.0 (disabled by default, operator opt-in)

---

### Tier 4 — IV-Based Scaling (ADVANCED / OPTIONAL)

Research finding: pure DTE scaling doesn't account for the volatility regime. At BTC 80% IV, 5DTE has an expected move of 11.3%. At 40% IV, the same 5DTE has a 5.6% expected move. The "danger" threshold should reflect this.

**Formula:**
```python
# Zone thresholds expressed as fractions of σ (sigma), scaled to current DTE
daily_vol = iv_annual / sqrt(252)
period_vol = daily_vol * sqrt(max(hours_remaining / 24.0, 0.5))
warning_pct  = period_vol * warning_sigma   # e.g. 1.0σ
danger_pct   = period_vol * danger_sigma    # e.g. 0.67σ
critical_pct = period_vol * critical_sigma  # e.g. 0.33σ
```

This makes thresholds automatically wider during high IV and narrower during low IV — correct behavior since a 1% move in a 5% daily-vol environment is much less alarming than in a 1% daily-vol environment.

**Requires:** current IV from session or vol collector. The session's `_regime_spot_price` data and vol data are already in the heartbeat context. IV is available via `mmm_regime.py` volatility checks.

**Recommend:** implement after Tier 1+2 are validated. Tier 4 is the most accurate long-term architecture.

**New config params:** `breakeven_warning_sigma`, `breakeven_danger_sigma`, `breakeven_critical_sigma`
(enable IV mode), defaulting to 0 (disabled, uses pct-based Tier 1).

---

## 5. IMPLEMENTATION PLAN

### Phase A — Core Engine Changes (`mmm_breakeven_engine.py`)

**A-1: Add `_compute_dte_scale()` method** (with vol regime damp and high-risk override)
```python
def _compute_dte_scale(self, session: Dict) -> float:
    """
    Returns DTE-based threshold scale factor.
    1.0 at expiry (0DTE behavior), dte_threshold_mult at session start.
    Uses sqrt(t_ratio) — same decay rate as BSM time-value.

    Modulated by:
    - breakeven_high_risk_mode: returns 1.0 immediately (operator override)
    - breakeven_dte_vol_regime_damp: reduces scale when vol regime is ELEVATED/HIGH
    """
    params = session.get('params', {})

    # High-risk mode override: disable DTE scaling entirely
    if params.get('breakeven_high_risk_mode', False):
        return 1.0

    dte_mult = params.get('breakeven_dte_threshold_mult', 1.0)
    if dte_mult <= 1.0:
        return 1.0  # Fast path: no scaling configured

    total_dte_hours = params.get('total_dte_hours', 0.0)
    if total_dte_hours <= 0:
        return 1.0

    expiry_time = session.get('expiry_time')
    if not expiry_time:
        return 1.0

    if isinstance(expiry_time, str):
        exp_dt = datetime.fromisoformat(expiry_time)
    else:
        exp_dt = expiry_time

    now = datetime.now(timezone.utc)
    hours_remaining = max((exp_dt - now).total_seconds() / 3600.0, 0.0)
    t_ratio = min(hours_remaining / total_dte_hours, 1.0)

    raw_scale = 1.0 + (dte_mult - 1.0) * math.sqrt(t_ratio)

    # Vol regime damp: reduce DTE widening when vol is elevated/high
    vol_regime_damp = params.get('breakeven_dte_vol_regime_damp', 0.4)
    if vol_regime_damp > 0:
        vol_regime = session.get('_vol_regime', 'NORMAL')
        if vol_regime == 'HIGH':
            damp = vol_regime_damp          # e.g. 0.4 = 40% reduction of excess
        elif vol_regime == 'ELEVATED':
            damp = vol_regime_damp * 0.5    # e.g. 0.2 = 20% reduction of excess
        else:
            damp = 0.0
        if damp > 0:
            raw_scale = 1.0 + (raw_scale - 1.0) * (1.0 - damp)

    return max(1.0, raw_scale)
```

**NOTE on cache architecture (per R4 review):** `_compute_dte_scale()` is called inside `_build_result()`, which is called on EVERY `compute_breakeven()` invocation regardless of cache state. Only the breakeven prices (lower/upper) are cached — zone, multiplier, and dte_scale are always freshly computed. No cache staleness risk.

**A-2: Update `_classify_zone()` signature**
```python
def _classify_zone(
    self,
    nearest_distance_pct: Optional[float],
    params: Dict,
    dte_scale: float = 1.0,   # NEW
) -> str:
    # Scale thresholds
    warning_pct  = params.get('breakeven_warning_pct', 2.0)  * dte_scale
    danger_pct   = params.get('breakeven_danger_pct', 1.0)   * dte_scale
    critical_pct = params.get('breakeven_critical_pct', 0.5) * dte_scale
    # ... rest unchanged
```

**A-3: Update `_compute_multiplier()` signature** (with CRITICAL-exempt damp)
```python
def _compute_multiplier(
    self,
    zone: str,
    nearest_distance_pct: Optional[float],
    params: Dict,
    dte_scale: float = 1.0,            # NEW
    dte_aggression_damp: float = 0.0,  # NEW
) -> float:
    # Scale thresholds identically to _classify_zone (same dte_scale)
    warning_pct  = params.get('breakeven_warning_pct', 2.0)  * dte_scale
    danger_pct   = params.get('breakeven_danger_pct', 1.0)   * dte_scale
    critical_pct = params.get('breakeven_critical_pct', 0.5) * dte_scale

    # Scale max_mult (Tier 2) — CRITICAL zone ALWAYS gets full max_mult
    max_mult_base = params.get('breakeven_aggression_max', 3.0)
    if dte_aggression_damp > 0 and zone != 'CRITICAL':
        # Compute sqrt(t_ratio) from dte_scale (inverse of the scale formula)
        raw_dte_mult = params.get('breakeven_dte_threshold_mult', 1.0)
        denom = max(raw_dte_mult - 1.0, 0.001)
        sqrt_t_ratio = (dte_scale - 1.0) / denom  # 0 at expiry, 1.0 at session start
        damp_factor = 1.0 - (dte_aggression_damp * sqrt_t_ratio)
        max_mult = max(max_mult_base * damp_factor, 1.5)  # floor at 1.5
    else:
        max_mult = max_mult_base  # CRITICAL: no dampening, or damp disabled
    # ... rest of ramp unchanged but uses scaled thresholds and effective max_mult
```

**A-4: Update `_build_result()` to compute dte_scale, pnl_clamp, and pass to zone/mult**
```python
dte_scale = self._compute_dte_scale(session)

# Pnl clamp: if portfolio is losing badly (suggests deep-ITM positions),
# disable DTE widening — intrinsic model is accurate when options are ITM
pnl_at_spot = self._compute_pnl_at_spot(positions, spot_price, session)
total_premium = session.get('total_premium_collected', 0)
if total_premium > 0 and pnl_at_spot < 0 and dte_scale > 1.0:
    clamp_pct = params.get('breakeven_dte_pnl_clamp_pct', 0.5)
    loss_ratio = abs(pnl_at_spot) / total_premium
    if loss_ratio > clamp_pct:
        dte_scale = 1.0  # Deep-ITM: full base aggression regardless of DTE

# CRITICAL zone exemption for aggression damp (applied in _compute_multiplier)
dte_aggression_damp = params.get('breakeven_dte_aggression_damp', 0.0)

zone = self._classify_zone(nearest_distance_pct, params, dte_scale)
multiplier = self._compute_multiplier(zone, nearest_distance_pct, params, dte_scale, dte_aggression_damp)
```

**A-5: Add `dte_scale` to the result dict**
```python
return {
    ...
    'dte_scale': round(dte_scale, 4),   # NEW — visible in heartbeat/UI
    ...
}
```

**A-6: Update `_empty_result()` to include `dte_scale: 1.0`**

### Phase B — Config and State Changes

**B-1: `mmm_config.py` — add 8 new parameters**
```python
'breakeven_dte_threshold_mult':    {'type': float, 'min': 1.0, 'max': 5.0,  'hot': True},
'breakeven_dte_aggression_damp':   {'type': float, 'min': 0.0, 'max': 0.4,  'hot': True},
'breakeven_dte_vol_regime_damp':   {'type': float, 'min': 0.0, 'max': 1.0,  'hot': True},
'breakeven_dte_pnl_clamp_pct':     {'type': float, 'min': 0.1, 'max': 2.0,  'hot': True},
'breakeven_tv_credit_factor':      {'type': float, 'min': 0.0, 'max': 0.5,  'hot': True},
'breakeven_high_risk_mode':        {'type': bool,  'min': None,'max': None,  'hot': True},
'breakeven_critical_lot_ceiling':  {'type': float, 'min': 2.0, 'max': 6.0,  'hot': True},
```

Add descriptions to the param_descriptions dict:
```python
'breakeven_dte_threshold_mult':   'DTE threshold scale at session start: 1.0=no scaling, 1.5=50% wider at session start, shrinks via sqrt(t) to 1.0 at expiry',
'breakeven_dte_aggression_damp':  'Reduce max lot aggression at early DTE (0=off, 0.1=10% reduction). Always 0 in CRITICAL zone.',
'breakeven_dte_vol_regime_damp':  'Reduce DTE widening when vol regime is ELEVATED/HIGH (0=off, 0.4=40% reduction at HIGH)',
'breakeven_dte_pnl_clamp_pct':    'Disable DTE scaling when portfolio loss > X× of collected premium (0.5=50%). Guards deep-ITM edge case.',
'breakeven_tv_credit_factor':     'Tier 3: time-value credit in P&L model (0=off, 0.15=15% of entry premium). Leave 0 until Tier 1 validated.',
'breakeven_high_risk_mode':       'Override: force dte_scale=1.0 (0DTE-equivalent) for FOMC/CPI/known event windows. Operator toggle.',
'breakeven_critical_lot_ceiling': 'Combined multiplier ceiling override in CRITICAL zone (default 4.0 vs global 3.0 cap)',
```

**B-2: `mmm_state.py` — add to DEFAULT_PARAMS**
```python
'breakeven_dte_threshold_mult':   1.0,   # backward compat default = no scaling
'breakeven_dte_aggression_damp':  0.0,   # no dampening
'breakeven_dte_vol_regime_damp':  0.4,   # moderate regime damping
'breakeven_dte_pnl_clamp_pct':    0.5,   # clamp at 50% of collected premium loss
'breakeven_tv_credit_factor':     0.0,   # Tier 3 disabled
'breakeven_high_risk_mode':       False, # operator override off
'breakeven_critical_lot_ceiling': 4.0,   # CRITICAL allows 4× combined
```

Add all 7 to `HOT_RELOAD_PARAMS`.

**B-3: `mmm_dte_presets.py` — update PRESET_5DTE** (conservative first-deployment)
```python
PRESET_5DTE = {
    ...existing fields...,
    'breakeven_dte_threshold_mult':   1.5,   # conservative first deployment (upgrade to 2.0 after validation)
    'breakeven_dte_aggression_damp':  0.1,   # mild dampening (was 0.2 in draft; reduced per review)
    'breakeven_dte_vol_regime_damp':  0.4,   # inherit from default
    'breakeven_dte_pnl_clamp_pct':    0.5,   # inherit from default
    'breakeven_critical_lot_ceiling': 4.0,   # inherit from default
}
```

Keep `PRESET_0DTE` unchanged (all DTE params at defaults = 0DTE-equivalent behavior).

### Phase C — Tests

**C-1: Sealed tests for `_compute_dte_scale()`**
- Returns 1.0 when `dte_threshold_mult=1.0`
- Returns 1.0 when `total_dte_hours=0`
- Returns 1.0 when `expiry_time=None`
- Returns `dte_mult` when `hours_remaining == total_dte_hours` (session start, no vol damp)
- Returns 1.0 when `hours_remaining == 0` (at expiry)
- Returns `1 + (dte_mult-1)*sqrt(0.25)` when at 25% of total time (t_ratio=0.25)
- Returns 1.0 when `breakeven_high_risk_mode=True` (override fires immediately)
- Vol regime ELEVATED with damp=0.4: scale reduced by 20% of excess (`damp × 0.5`)
- Vol regime HIGH with damp=0.4: scale reduced by 40% of excess
- Vol regime NORMAL: no damp regardless of damp param value
- `pnl_clamp`: if pnl_at_spot < 0 and abs(pnl_at_spot)/total_premium_collected > clamp_pct → dte_scale clamped to 1.0

**C-2: Updated sealed tests for `_classify_zone()`**
- All existing tests pass unchanged (dte_scale defaults to 1.0)
- New test: `dte_scale=2.0`, `nearest=3.5%` → zone=WARNING (would be SAFE at scale=1.0 since 3.5% > 2%)
- New test: `dte_scale=2.0`, `nearest=0.8%` → zone=DANGER (scaled danger threshold = 2.0%)

**C-3: Updated sealed tests for `_compute_multiplier()`**
- All existing tests pass with dte_scale=1.0, dte_aggression_damp=0.0
- New test: dte_aggression_damp=0.2 with high dte_scale → lower max_mult

**C-4: Integration test: full `compute_breakeven()` with 5DTE session**
- Mock session with expiry_time = now + 120h, total_dte_hours=120
- Verify `dte_scale ≈ 2.0` in result
- Verify zone is SAFE when spot is 3.5% from intrinsic breakeven (would trigger at scale=1.0)

### Phase D — Frontend

Changes to `MMMBreakevenPanel.js`:
- Add "DTE adj: 1.77×" indicator next to zone badge (tooltip: "Thresholds widened ×1.77 based on 72h remaining to expiry")
- When `breakeven_high_risk_mode=True`: show red "HIGH RISK" chip replacing the DTE adj indicator
- When `_vol_regime` is ELEVATED/HIGH and damp is active: show reduced scale with footnote "vol-damped"
- **Dollar buffer estimate row** (from §R13): compute and display `Market BE Est. (BSM)` = intrinsic_breakeven ± TV_buffer
  - `TV_buffer ≈ spot × 0.8 × √(hours_remaining / 8760) / √(2π)` (client-side, BSM ATM at σ=80%)
  - If session has live IV from MMMGreeksPanel context: use actual avg IV
  - Display: "Lower: $77,340 (model) → $76,140 (est. market)" — gives dollar intuition for the "false alarm" gap
  - Tooltip: "Estimated real market breakeven includes remaining time value (BSM ATM approximation at 80% IV). True value depends on actual IV and moneyness."

Add `breakeven_high_risk_mode` toggle to MMMSettingsDialog in the Breakeven Engine section with a prominent warning note: "Enable before FOMC/CPI/known event. Disables DTE threshold widening for the session."

---

## 6. BACKWARD COMPATIBILITY ANALYSIS

| Concern | Impact | Mitigation |
|---------|--------|------------|
| Existing live sessions | `breakeven_dte_threshold_mult` defaults to 1.0 → no behavior change | Default = 1.0 (explicit backward compat) |
| Existing sealed tests | `_classify_zone()` has new optional param with default=1.0 | All callers work unchanged |
| Sessions without expiry_time | `_compute_dte_scale()` returns 1.0 | Early return on `not expiry_time` |
| Sessions where expiry_time already passed | `hours_remaining=0` → `t_ratio=0` → `dte_scale=1.0` | Naturally 0DTE behavior after expiry |
| Cache invalidation | Not needed — dte_scale computed fresh in `_build_result()` every heartbeat | No cache changes |

---

## 7. WHAT THIS DOES NOT DO (INTENTIONAL SCOPE LIMITS)

- **Does not add live IV fetches** — intrinsic-only model is kept (deliberate design, no latency risk)
- **Does not add per-strike IV lookup** — too complex, too many API calls
- **Does not auto-detect DTE** at heartbeat level — `total_dte_hours` is set once at session creation and is sufficient
- **Does not change the breakeven P&L scan/bisection algorithm** — only the zone classification changes
- **Does not add Tier 3 (TV credit)** to the immediate implementation — recommend validating Tier 1+2 first

---

## 8. RECOMMENDED DEFAULTS PER PRESET

| Param | PRESET_0DTE | PRESET_5DTE | DEFAULT (no preset) |
|-------|-------------|-------------|---------------------|
| `breakeven_dte_threshold_mult` | 1.0 | 2.0 | 1.0 |
| `breakeven_dte_aggression_damp` | 0.0 | 0.2 | 0.0 |
| `breakeven_warning_pct` | 2.0 (base) | 2.0 (base, scaled to 4.0% at start) | 2.0 |
| `breakeven_danger_pct` | 1.0 (base) | 1.0 (base, scaled to 2.0% at start) | 1.0 |
| `breakeven_critical_pct` | 0.5 (base) | 0.5 (base, scaled to 1.0% at start) | 0.5 |

---

## 9. FILES TO MODIFY *(superseded by §13 — see post-review update)*

| File | Change |
|------|--------|
| `webui/backend/routes/mmm/mmm_breakeven_engine.py` | Add `_compute_dte_scale()` (with vol_regime_damp + high_risk_mode + pnl_clamp); update `_classify_zone()`, `_compute_multiplier()` (CRITICAL exempt), `_build_result()`, `_empty_result()` |
| `webui/backend/routes/mmm/mmm_config.py` | Add 7 new params + descriptions |
| `webui/backend/routes/mmm/mmm_state.py` | Add 7 defaults to DEFAULT_PARAMS + HOT_RELOAD_PARAMS |
| `webui/backend/routes/mmm/mmm_dte_presets.py` | Update PRESET_5DTE: mult=1.5, damp=0.1 + 3 inherited params |
| `webui/backend/routes/mmm/mmm_engine.py` | Add `breakeven_critical_lot_ceiling` override in combined ceiling block |
| `webui/frontend/src/components/mmm/MMMBreakevenPanel.js` | dte_scale indicator, high_risk chip, vol-damped note, market BE dollar estimate |
| `webui/frontend/src/components/mmm/MMMSettingsDialog.js` | 5 new param inputs with `breakeven_high_risk_mode` prominently placed |

**Files NOT modified:** `mmm_monitor.py`, `mmm_api.py`, `mmm_regime.py`, `mmm_gamma_detector.py`, `mmm_close_at_5.py`, `mmm_harvester.py`, `mmm_recycler.py`

---

## 10. CRITICAL REVIEW — INTEGRATED ANALYSIS

> A thorough external critique was applied to this plan (March 16, 2026). Each of the 10 problems and missing-feature concerns is evaluated below. Items marked ✅ are incorporated; ✗ are rejected with reasoning; ⚠ are noted with caveats.

---

### R1 — √T Formula Assumes Constant IV: BTC Front-End Is Often Elevated ✅ Incorporated

**Critique:** BTC front-end IV (0–5DTE) frequently trades at a premium to longer-dated IV due to jump risk (FOMC, CPI, exchange events). The √T formula blindly widens thresholds at session start — but if front-end IV is elevated (a common BTC condition), the option premium already includes elevated jump risk, and the extrinsic "buffer" argument weakens.

**Assessment: Valid.** The existing `mmm_regime.py` already tracks `_vol_regime` (NORMAL/ELEVATED/HIGH) and `_vol_rv_annualized`, `_vol_iv_change_pct`. When the vol regime is ELEVATED or HIGH, it signals compressed VRP or jump-risk premium, and the DTE threshold widening should be moderated.

**Fix:** Add a `breakeven_dte_vol_regime_damp` param. When vol_regime is ELEVATED, reduce dte_threshold_mult by 30% of its excess over 1.0. When HIGH, reduce by 60%. This auto-tightens thresholds when the regime signals elevated front-end risk.

```
effective_mult = 1.0 + (raw_mult - 1.0) × (1 - vol_regime_damp_factor)
vol_HIGH:     damp_factor = breakeven_dte_vol_regime_damp (default 0.6)
vol_ELEVATED: damp_factor = breakeven_dte_vol_regime_damp × 0.5
vol_NORMAL:   damp_factor = 0 (no damping, full widening)
```

**New param:** `breakeven_dte_vol_regime_damp` (float, 0.0–1.0, hot, default 0.4)
- At 0.4: vol HIGH → effective_mult reduced 40% of excess. For mult=2.0 at session start: 1 + (2-1)×0.6 = 1.6 (vs 2.0 raw).
- At 0.4: vol ELEVATED → reduced 20%: 1 + (2-1)×0.8 = 1.8 (vs 2.0 raw).

Data source: `session.get('_vol_regime', 'NORMAL')` — already in session state, no new API calls.

---

### R2 — Formula Gets One Case Wrong: Deep-ITM Moneyness Override ✅ Incorporated (simplified)

**Critique:** When an option is deep ITM (e.g., CE sold at $100, now at $400), the intrinsic-only model is accurate — minimal extrinsic remains. The √T formula would still widen thresholds, which is wrong. DTE scale should be 1.0 when the option is deep ITM regardless of time remaining.

**Assessment: Partially valid — but simpler than described.** The engine doesn't have access to current market premiums (those are `ce_now`/`pe_now` in the monitor, not stored in session). However, when an option goes deep ITM:
1. The intrinsic-only P&L at current spot becomes strongly negative
2. `nearest_distance_pct` → 0 (already at or past breakeven)
3. Even with dte_scale=2.0, the zone is CRITICAL — the widening doesn't create false-SAFE

The **real edge case** is: large `realized_pnl` banked from previous harvests/adjustments can mask a deteriorating live position (P&L vertical shift keeps pnl_at_spot positive even when live positions are deep ITM). In this case, dte_scale widening could keep zone SAFE while individual options are rapidly losing value.

**Fix:** Add an ITM clamp guard inside `_compute_dte_scale()`. If the session's live positions are on average significantly above entry (proxied by comparing total unrealized_pnl against the realized buffer), reduce dte_scale toward 1.0. Practically: add `breakeven_dte_pnl_clamp_pct` — if `pnl_at_spot` is negative by more than this % of `total_premium_collected`, clamp dte_scale to 1.0.

```python
# In _build_result(), after computing pnl_at_spot:
total_premium = session.get('total_premium_collected', 0)
if total_premium > 0 and pnl_at_spot < 0:
    loss_as_pct_of_collected = abs(pnl_at_spot) / total_premium
    clamp_threshold = params.get('breakeven_dte_pnl_clamp_pct', 0.5)  # 50% of collected
    if loss_as_pct_of_collected > clamp_threshold:
        dte_scale = 1.0  # Full base aggression — losing badly, DTE doesn't matter
```

**New param:** `breakeven_dte_pnl_clamp_pct` (float, 0.1–2.0, hot, default 0.5)
- At 0.5: if current portfolio loss (from intrinsic model) exceeds 50% of all premium collected, DTE scaling is disabled.
- Prevents false-SAFE when cumulative P&L looks fine but current position is deep ITM.

---

### R3 — Aggression Damp at Early DTE: Vega + M2 Interaction ⚠ Noted, Tier 2 Kept with Reduced Default

**Critique:** At 5DTE session start, IV is high (vega risk is high), and an IV spike could trigger adjustments needing full aggression. Dampening max_mult at this time could cause under-hedging. Also, the M2 recycler viability checks are not analyzed.

**Assessment: Partially valid.** The damp affects only max_mult (ceiling), not the base lot calculation. A 20% damp reduces the ceiling from 3.0× to 2.4× — still a significant multiplier. However:
- The Tier 2 damp fires when we ARE in a breakeven zone (thresholds already crossed after the Tier 1 widening) — the position is under genuine stress
- If vol regime is ELEVATED (R1 fix reduces dte_scale), the breakeven thresholds are tighter, making it less likely to be in a zone at all early in the session
- M2 recycler interaction: if damp causes fewer lots sold and M2 doesn't fire (viability checks fail), no fallback adjustment occurs. This is a real gap.

**Fix:** Reduce default `breakeven_dte_aggression_damp` from 0.2 → 0.1 in PRESET_5DTE. More conservative initial deployment. Additionally: the damp should be disabled when in CRITICAL zone regardless of DTE — add a zone override:

```python
# In _compute_multiplier(): only apply damp for WARNING/DANGER, never CRITICAL
if zone == 'CRITICAL':
    dte_aggression_damp = 0.0  # full aggression in CRITICAL regardless of DTE
```

PRESET_5DTE updated: `breakeven_dte_aggression_damp: 0.1` (was 0.2)

---

### R4 — Cache Staleness Bug: ✗ REJECTED — Not a Bug

**Critique:** "The returned multiplier from cache will be stale" when positions haven't changed.

**Assessment: Incorrect.** The code confirms (lines 78–109) that:
- The cache stores ONLY `{lower_breakeven, upper_breakeven, positions_hash, band_width_pct}` — NOT zone, multiplier, or dte_scale
- `_build_result()` is called on **every** `compute_breakeven()` invocation regardless of cache hit
- The proposed `_compute_dte_scale()` is added inside `_build_result()` — so it executes fresh every heartbeat

The cache optimizes the expensive bisection scan (~1ms), not the zone classification (~0.01ms). Zone, multiplier, and dte_scale are always freshly computed from current `session` state and `spot_price`.

**No change needed.** Plan clarification added to Phase A implementation notes.

---

### R5 — Combined Ceiling Throttles Breakeven When Trend Also Active ✅ Incorporated

**Critique:** When breakeven CRITICAL fires simultaneously with an active trend tier (not unusual — a large price move triggers both), the existing `max_combined_lot_multiplier=3.0` cap throttles the breakeven multiplier to near-1.0×.

Example: gamma(1.2) × breakeven(2.5) × trend(2.0) = 6.0× → capped to 3.0× (breakeven contribution nullified).

**Assessment: Valid.** However, INCREASING the ceiling globally risks runaway at other times. A targeted fix: when breakeven zone is CRITICAL, allow a higher ceiling.

**Fix:** Add `breakeven_critical_lot_ceiling` param that overrides `max_combined_lot_multiplier` specifically when zone=CRITICAL:

```python
# In mmm_engine.py calculate_lots_to_sell(), combined ceiling block:
breakeven_zone = session.get('_breakeven_zone', 'SAFE')
if breakeven_zone == 'CRITICAL':
    effective_ceiling = params.get('breakeven_critical_lot_ceiling',
                                   params.get('max_combined_lot_multiplier', 3.0))
else:
    effective_ceiling = params.get('max_combined_lot_multiplier', 3.0)
```

**New param:** `breakeven_critical_lot_ceiling` (float, 2.0–6.0, hot, default 4.0)
- Default 4.0: CRITICAL zone allows up to 4× combined multiplier instead of 3×
- Explicit override — operator can tune without touching the global ceiling
- Not hot-reloaded during live session changes (recommended, to avoid mid-session lot surprises)

---

### R6 — VRP Not a Separate Feature: Already Covered by R1 ✅ Covered

**Critique:** BTC's variance risk premium (VRP = IV/RV ratio) should modulate threshold width. High VRP → more cushion (wider). Low VRP → less cushion (tighter).

**Assessment: Substantially covered by R1 (vol regime damp).** The regime engine already computes `_vol_rv_annualized` and `_vol_iv_change_pct`. A pure VRP ratio isn't directly tracked, but:
- Vol ELEVATED state approximates "IV rising faster than RV" → compressed VRP → R1 damp fires
- Vol HIGH state approximates "IV spike / jump risk" → R1 damp at full 60%

For a future Tier 4 IV-based implementation, IV/RV ratio can be surfaced as `iv_rv_ratio = iv / max(rv, 0.1)` and used directly. For now, the regime-state proxy in R1 is sufficient and uses existing data.

---

### R7 — ATM Formula Used for OTM Options: mult=2.0 May Be Too High ✅ Adjusted

**Critique:** The plan's TV buffer estimates (~3% of spot at 5DTE) use the ATM straddle formula. The bot sells OTM options, which have less time value than ATM. For a 1% OTM option at 5DTE, actual TV is significantly less than 3%.

**Assessment: Valid.** BSM OTM option TV decays with moneyness. A 1% OTM call at BTC 80% IV, 5DTE has approximately 60–70% of ATM time value (not 100%). So the "3% extrinsic buffer" estimate in §2.2 is overstated for the actual positions.

**Fix:** Revise first-deployment recommendation to mult=1.5 (not 2.0). This is more defensible for OTM options and reduces first-deployment risk. After one full 5DTE session with telemetry, tune to 2.0 or higher if the session shows too-frequent early warnings.

**Updated §8 (Recommended Defaults):**

| Param | PRESET_5DTE (First Deployment) | PRESET_5DTE (After Validation) |
|-------|-------------------------------|-------------------------------|
| `breakeven_dte_threshold_mult` | **1.5** (conservative) | 2.0 (confirmed safe) |
| `breakeven_dte_aggression_damp` | **0.1** (conservative) | 0.1–0.2 (per session data) |

---

### R8 — BTC Jump Risk: High-Risk Window Override ✅ Incorporated

**Critique:** FOMC/CPI/exchange events within a 5DTE session window can cause 20–40% IV spikes. The DTE scaling has no way to temporarily tighten thresholds during known high-risk periods.

**Assessment: Valid.** Simple fix: boolean operator override.

**New param:** `breakeven_high_risk_mode` (bool, hot, default False)
- When True: `dte_scale = 1.0` regardless of time remaining (full 0DTE-equivalent aggression)
- Operator can toggle in MMMSettingsDialog before a known event
- Auto-resets to False on session stop (not persisted across restarts)
- Description: "Force DTE threshold scaling OFF — use base (0DTE-equivalent) thresholds for known high-volatility windows (FOMC, CPI, exchange halts)"

This is a single line in `_compute_dte_scale()`:
```python
if params.get('breakeven_high_risk_mode', False):
    return 1.0
```

---

### R9 — Tier Sequencing: Tier 3 (TV Credit) Should Be Earlier ⚠ Noted, Sequencing Maintained

**Critique:** Tier 3 fixes the root cause (inaccurate P&L model), while Tier 1 is a patch (inflated thresholds). Sequencing them backwards may leave operators with inaccurate P&L displays.

**Assessment: Partially valid.** The behavioral outcomes of Tier 1 and Tier 3 are similar — both widen the effective "safe zone" at high DTE. But Tier 3 would correct the **displayed `pnl_at_spot`** in MMMBreakevenPanel from being too pessimistic, giving operators more accurate dollar P&L estimates.

**Resolution:**
- Sequencing maintained (Tier 1 first) — lower implementation risk, faster path to live validation
- Add Tier 3 `breakeven_tv_credit_factor` as a parallel config param (can be non-zero even at Tier 1 deployment if operator chooses)
- Clarify in MMMBreakevenPanel tooltip: "P&L shown uses intrinsic-only model (conservative). Actual P&L is higher at high DTE due to remaining time value."
- Tier 3 is the upgrade path for display accuracy, not just behavioral accuracy

---

### R10 — Degradation Testing: Rapid Whipsaw Threshold Inconsistency ✅ Noted

**Critique:** In a rapid whipsaw where two adjustments fire 30 minutes apart, dte_scale changes slightly between them (it does, via continuous time decay), creating slightly different effective thresholds for each trigger. This is not a bug per se, but worth acknowledging.

**Assessment: This is acceptable behavior.** dte_scale changes at rate ~0.5% per hour for a 5DTE session (slope of √t function at t=0.5). In a 30-minute window, the scale changes by ~0.25%. This is negligible compared to the precision of lot calculations (integer ceiling). Not worth adding complexity to prevent.

**However:** Confirm the following edge cases are handled (they are, by existing early returns in `_compute_dte_scale()`):
- `expiry_time` missing → returns 1.0 ✓
- `total_dte_hours = 0` → returns 1.0 ✓
- `hours_remaining > total_dte_hours` (session started early) → `t_ratio` clamped to 1.0 ✓
- All times UTC-aware (robustv2 fix #14) ✓

---

### R11 — Asymmetric CE/PE Scaling for BTC Put Skew ⚠ Noted, Not in This PR

**Critique:** BTC has persistent negative put skew — PE options are priced at higher IV than CE at the same OTM distance. A PE position has more extrinsic cushion than CE. DTE threshold widening should be asymmetric: wider for PE, tighter for CE.

**Assessment: Valid but complex.** This requires knowing the IV skew (CE IV vs PE IV) per session, which requires the vol chain data available in `mmm_initializer.py` but not currently cached in session state. The gain would be meaningful (~10–15% asymmetry in effective thresholds for typical BTC skew conditions).

**Resolution:** Not in this PR. Add to Tier 4 scope when IV-based scaling is implemented. Tier 4 naturally handles this by computing thresholds based on per-side IV rather than a symmetric √T scale.

---

### R12 — Hedge-Side Lot Sizing Already DTE-Aware ✗ REJECTED — Already Handled

**Critique:** "Lot sizing for the hedge side doesn't account for DTE — you over-hedge at early DTE because the formula doesn't differentiate."

**Assessment: Incorrect.** The lot formula is `N_sell = ceil(L / P_hedge × (1 + buffer))`. At 5DTE session start, `P_hedge` (current premium of the hedge option) is naturally high because the option has more time value. Dividing by a larger `P_hedge` naturally produces **fewer** hedge lots needed for the same loss. The formula is inherently DTE-aware through the market price. No change needed.

---

### R13 — Dollar-Denominated Buffer Display ✅ Incorporated in Frontend Section

**Critique:** Showing "DTE adj: 1.77×" is abstract. More useful: show estimated market breakeven vs intrinsic breakeven in dollar terms.

**Assessment: Valid UX improvement.** Add to MMMBreakevenPanel:

**Proposed display addition:**
- Row: "Market BE Est." = intrinsic_breakeven ± TV_buffer
- Where `TV_buffer ≈ S × σ × √(hours_remaining / 8760) / √(2π)` (BSM ATM approximation, client-side calculation using avg_iv if available from MMMGreeksPanel)
- If IV not available: show `"~$X estimated (BSM ATM at σ=80%)"` using hardcoded 80% fallback
- Tooltip: "Estimated real market breakeven including time value (approximate, ATM BSM formula). True market price may differ from intrinsic model."

This gives operators a dollar intuition: "The model shows breakeven at $78,500, but with ~$1,200 of estimated time value remaining, the real market breakeven is around $77,300." This directly communicates the "false alarm" risk when dte_scale is widening thresholds.

---

## SUMMARY OF CHANGES FROM CRITICAL REVIEW

| Review Item | Status | Change |
|-------------|--------|--------|
| R1: IV regime damp on dte_scale | ✅ Added | New param `breakeven_dte_vol_regime_damp` |
| R2: Deep-ITM/moneyness override | ✅ Simplified | New param `breakeven_dte_pnl_clamp_pct` |
| R3: Aggression damp + M2 interaction | ✅ Adjusted | CRITICAL zone bypasses damp; default reduced 0.2→0.1 |
| R4: Cache staleness bug | ✗ Rejected | Not a bug — _build_result() always fresh |
| R5: Combined ceiling in CRITICAL zone | ✅ Added | New param `breakeven_critical_lot_ceiling` (default 4.0) |
| R6: VRP separate concern | ✅ Covered by R1 | Regime-state proxy sufficient |
| R7: OTM TV overestimate / mult=2.0 | ✅ Adjusted | First-deployment recommendation: mult=1.5 |
| R8: Jump risk / FOMC override | ✅ Added | New param `breakeven_high_risk_mode` (bool) |
| R9: Tier 3 sequencing | ⚠ Noted | Sequencing maintained; display note added |
| R10: Whipsaw threshold inconsistency | ✅ Analyzed | Negligible; edge cases confirmed handled |
| R11: Asymmetric CE/PE scaling | ⚠ Noted | Defer to Tier 4 / IV-based scaling |
| R12: Hedge-side lot sizing | ✗ Rejected | Already handled by formula |
| R13: Dollar buffer display | ✅ Added | Frontend enhancement in MMMBreakevenPanel |

---

## RESEARCH SUMMARY TABLE

| Source | Key Finding | Applied In |
|--------|------------|-----------|
| Black-Scholes | ATM time value ∝ √T. Zone widths must scale with √DTE | Tier 1 formula |
| Tastytrade studies | 21 DTE is gamma inflection. Close/manage inside 21 DTE for better Sharpe | Confirms 5DTE is already in active management window |
| Euan Sinclair "Volatility Trading" | Aggressively delta-hedge inside 1 week; remaining theta doesn't compensate unhedged gamma | Confirms higher aggression at lower DTE (Tier 2) |
| Natenberg | ATM straddle ≈ 0.8 × S × σ × √T | BTC TV estimates in section 2.2 |
| Tastytrade research | Short strangles at 45DTE closed at 21DTE: 84% win rate; better Sharpe vs hold-to-expiry | Validates conservative early exits |
| Institutional vol desks | Real breakeven = intrinsic + remaining extrinsic as buffer | Tier 3 (TV credit) |
| Research synthesis | BTC 80% IV: 5-day expected move = 11.3%. Static 1-2% thresholds are ~10% of expected move → barely trigger at 5DTE | Motivates Tier 4 IV-based scaling |

---

## 15. SECOND-PASS CRITIQUE — HONEST EVALUATION

*Instruction: "analyse this and update the plan only if they are relevant with our MMM algo dont be yes man be honest for profitability of mmm algo"*

---

### S1 — Verify `_vol_regime` Session Key Name ✓ Already Confirmed, No Change

**Critique:** `session.get('_vol_regime', 'NORMAL')` — verify this key name is correct.

**Assessment:** Already verified. `mmm_regime.py` lines 192 and 233 write `session['_vol_regime']` directly. The key name is correct. No change to implementation. Adding a test case note to §11 Validation Plan (new step: assert `_vol_regime` is readable from session after regime evaluation).

---

### S2 — pnl_clamp False Trigger at Early Session ✅ ACCEPTED, Fix Required

**Critique:** Default `breakeven_dte_pnl_clamp_pct=0.5` fires when loss > 50% of `total_premium_collected`. At session start with 1–2 lots and tiny accumulated premium (e.g., ₹200 total), any adverse 1% move easily exceeds 50% loss on ₹200. This disables DTE scaling exactly when it's most needed — early in a 5DTE session.

**Assessment: Valid and important.** The clamp was designed to catch deep ITM / runaway loss scenarios. But `total_premium_collected` starts near-zero and grows as lots are added. A 50% clamp on ₹200 = ₹100 — which triggers on a normal small market fluctuation. This inverts the intent.

**Fix — two guards:**
1. **Raise default to `1.5`**: Loss must exceed 150% of collected premium before the clamp fires. At 5DTE with typical premium collection, this gives meaningful runway before disabling DTE scaling.
2. **Add lot-count floor (NOT a currency floor)**: Clamp only activates when `total_lots_sold >= 5`. When session is too new to have meaningful positions, don't clamp at all — DTE scaling is most important in this window.

> Note: an earlier version of this plan used `MIN_PREMIUM_FLOOR = 1000` (INR hardcoded). That was wrong — the breakeven engine operates in USD (premiums in USD/BTC, LOT_SIZE_BTC=0.001). ₹1,000 ≈ $12 USD — functionally zero. Replaced with a lot-count floor which is currency-agnostic and semantically clearer.

```python
# In _build_result() before pnl_clamp check:
ce_lots = sum(p.get('lots', 0) for p in positions if p.get('side') == 'CE')
pe_lots = sum(p.get('lots', 0) for p in positions if p.get('side') == 'PE')
total_lots = ce_lots + pe_lots
MIN_LOTS_FOR_CLAMP = 5  # don't clamp until meaningful position exists

if total_lots >= MIN_LOTS_FOR_CLAMP and pnl_at_spot < 0 and dte_scale > 1.0:
    total_premium = session.get('total_premium_collected', 0)
    if total_premium > 0:
        clamp_pct = params.get('breakeven_dte_pnl_clamp_pct', 1.5)
        loss_ratio = abs(pnl_at_spot) / total_premium
        if loss_ratio > clamp_pct:
            dte_scale = 1.0  # Deep-ITM: full base aggression regardless of DTE
```

**Updated defaults:**

| Param | Old Default | New Default |
|-------|-------------|-------------|
| `breakeven_dte_pnl_clamp_pct` | 0.5 | **1.5** |

---

### S3 — CRITICAL Zone Full Exemption = Over-Accumulation at 5DTE ↩ REVISED AFTER THIRD-PASS

**Critique:** Current plan: CRITICAL zone is completely exempt from `aggression_damp`. At 5DTE session start with dte_scale=1.5 and mult=1.5 in threshold: the spot could be 0.75% from intrinsic breakeven (market breakeven actually ~3% away). Zone fires CRITICAL, gets full aggression multiplier. Bot aggressively accumulates lots when there's no real risk.

**Second-pass assessment:** Valid — partial damp (50%) was proposed.

**Third-pass re-evaluation: Partial damp reverted.** At typical params (damp=0.1), the difference between CRITICAL-with-50%-damp (effective_damp=0.05) and CRITICAL-fully-exempt (effective_damp=0.0) is:
- max_mult = 3.0 × (1 - 0.05×1.0) = 2.85 vs 3.0
- Difference: **0.15×** — negligible at integer ceiling, never changes actual lot count in practice

The partial damp adds code complexity (damp_factor conflated between config param value and halved value) for zero measurable behavioral effect at current defaults. It also creates a confusing code path where `damp_factor` means the raw param in some places and 50% of it in others.

**Final resolution: KEEP CRITICAL fully exempt.** The correct protection against over-accumulation in CRITICAL at 5DTE is the DTE threshold scaling itself (dte_scale=1.5 prevents CRITICAL from triggering falsely in the first place). If CRITICAL does trigger with dte_scale=1.5 active, that means spot is genuinely 0.75% from intrinsic breakeven, which is a real event deserving full defense.

```python
# In _compute_multiplier() — clean, unambiguous:
if zone == 'CRITICAL':
    damp_factor = 0.0  # CRITICAL: full aggression regardless of DTE
    # Rationale: if CRITICAL fires despite dte_scale widening, it's a genuine emergency
else:
    damp_factor = params.get('breakeven_dte_aggression_damp', 0.0)
```

At 0DTE: dte_scale=1.0 so damp has no effect for any zone. Behavior unchanged.
At 5DTE: SAFE/WARNING/DANGER are mildly damped; CRITICAL gets full aggression. This is the correct asymmetry.

---

### S4 — high_risk_mode Needs Auto-Expiry ✅ ACCEPTED

**Critique:** A 5DTE session runs for 5 days. If the operator enables `high_risk_mode` before FOMC and forgets, the bot trades with 0DTE-equivalent aggression for the remaining 4.5 days — defeating the entire DTE feature.

**Assessment: Valid operational safety concern.** Unlike most params that make sense to persist for a session's lifetime, `high_risk_mode` is event-specific. Forgetting to turn it off is plausible (operators are human; events happen at odd hours).

**Fix: Runtime auto-expiry via session key, not a config param.**

```python
# In toggle handler or engine startup:
# Must use datetime.now(timezone.utc) — NOT datetime.utcnow() (naive datetime)
# Codebase standard since robustv2 fix #14 — all datetimes are UTC-aware
session['_high_risk_mode_expires_at'] = (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()

# In _compute_dte_scale():
if params.get('breakeven_high_risk_mode', False):
    expires_at_str = session.get('_high_risk_mode_expires_at')
    if expires_at_str:
        expires_at = datetime.fromisoformat(expires_at_str)
        # Ensure tz-aware for comparison with datetime.now(timezone.utc)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires_at:
            # Auto-expired — treat as if False, log once
            log.info("breakeven_high_risk_mode auto-expired")
            return computed_dte_scale  # continue with normal DTE scaling
    return 1.0  # still within event window
```

- Default window: 4 hours from enable time
- Logged when auto-expires so operator can see it in activity log
- Not a config param — purely runtime state in session dict
- `_high_risk_mode_expires_at` is cleared on session stop (already implied by non-persisted session state)

**Does NOT add a new param.** The 4h window is hardcoded — operators who need longer just re-enable it.

---

### S5 — vol_regime_damp Default 0.4 → 0.2 ✅ ACCEPTED

**Critique:** Default `breakeven_dte_vol_regime_damp=0.4` means at VOL_ELEVATED/HIGH, the DTE threshold widening is reduced by 40%. With first-deployment mult=1.5, this cuts dte_scale at session start from 1.5 to 1.3. This is overly aggressive dampening for a first-deployment.

**Assessment: Valid.** The DTE effect (time value remains real regardless of vol regime) justifies only a modest reduction at elevated vol, not a 40% cut. At vol HIGH, you want tighter thresholds than at low vol — but you still want SOME DTE credit. The math:

| Vol Regime | damp=0.4 | damp=0.2 |
|------------|----------|----------|
| NORMAL | no damp | no damp |
| ELEVATED | scale = 1.0 + (1.5-1.0)×√1.0×0.6 = 1.3 | scale = 1.4 |
| HIGH | scale = 1.0 + (1.5-1.0)×√1.0×0.6 = 1.3 | scale = 1.4 |

At 0.2 damp, vol HIGH still reduces DTE widening by 20% — still tighter than NORMAL. This is a more calibrated first-deployment choice.

**Updated defaults:**

| Param | Old Default | New Default |
|-------|-------------|-------------|
| `breakeven_dte_vol_regime_damp` | 0.4 | **0.2** |

Note: PRESET_5DTE explicitly sets this, so default only affects future new presets.

---

### S6 — high_risk_mode Belongs in Dashboard, Not Just Settings ✅ ACCEPTED

**Critique:** `breakeven_high_risk_mode` is time-sensitive (toggle before FOMC announcement, which may be in 30 minutes). Burying it in MMMSettingsDialog means: open settings → scroll → find toggle → save. Too slow during a live event.

**Assessment: Valid.** This is a quick-action, not a configuration preference. UX matters when operators are stressed.

**Fix:** Add quick-action toggle to `MMMBreakevenPanel.js` — already in scope for modification. Place it in the breakeven status row:

```
Breakeven Status: [SAFE ▼]    DTE scale: 1.47×    [⚡ HIGH RISK MODE: OFF]
```

- One-click toggle visible at all times
- Also remains in MMMSettingsDialog for discovery / initial setup
- Frontend calls `PATCH /api/mmm/session/{id}/params` with `{breakeven_high_risk_mode: true}` (same as settings save)
- State visually distinct when ON (orange badge)

**Adds `MMMBreakevenPanel.js` change scope** (already in §13 file list — now explicitly includes the high_risk_mode quick-action).

---

### S7 — Dry-Run Shadow Mode for Validation ✅ ACCEPTED

**Critique:** The new DTE multiplier logic is untested on live data. Add `breakeven_dte_dry_run` (bool, hot, default True for first deployment). When enabled: compute dte_scale and new zone/multiplier normally, but pass `dte_scale=1.0` to the actual threshold classifiers — i.e., old behavior is used for trading, new behavior is only logged.

**Assessment: Highly valuable.** This is the responsible approach for a live financial system before trusting a new multiplier model. A dry-run mode lets the operator verify:
- Does dte_scale actually prevent false alarms that the old engine would have triggered?
- Do the computed multipliers look reasonable?
- Any edge cases in `_compute_dte_scale()` (expiry_time missing, regime not set, etc.)?

**Implementation:**

```python
# In compute_breakeven() / _build_result():
dry_run = params.get('breakeven_dte_dry_run', False)
effective_dte_scale = 1.0 if dry_run else dte_scale

result = self._build_result(..., dte_scale=effective_dte_scale)

# Always include shadow in result for logging:
result['dte_scale_computed'] = dte_scale          # what would have been used
result['dte_scale_effective'] = effective_dte_scale  # what was actually used
result['dte_dry_run'] = dry_run
```

Activity log emits `dte_scale_computed` even in dry-run so the operator can see "today's 5DTE session would have used scale=1.47 — here are the zones it would have produced."

**First-deployment default:** `PRESET_5DTE` sets `breakeven_dte_dry_run: True`. Operator explicitly disables after reviewing first session logs.

---

### S-MINOR-1 — Remove `breakeven_dte_aggression_min` Orphan Param ✅ ACCEPTED

**Critique:** `breakeven_dte_aggression_min` was added "for future IV asymmetry" with default 0.0 but has no implementation in any function. It adds dead config surface.

**Assessment: Correct. Remove it.** The future IV asymmetry feature belongs in Tier 4 and will have its own param design at that time. An orphan param with no implementation just confuses future readers and increases surface area. Removing it drops the count from 8 to 7 — but S7 adds `breakeven_dte_dry_run`, keeping count at 8.

---

### S-MINOR-2 — Reconcile Param Counts ✅ Fixed

**Issue:** Plan header says "now 9, up from 3" but table had 8 rows.

**Resolution after this review:**
- Remove: `breakeven_dte_aggression_min` (orphan, S-MINOR-1)
- Add: `breakeven_dte_dry_run` (S7)
- Net count: **8 new params** (up from 3 original)

---

## SECOND-PASS REVIEW SUMMARY

| Issue | Assessment | Action |
|-------|-----------|--------|
| S1: `_vol_regime` key | Already correct (confirmed from grep) | Add test case to validation plan |
| S2: pnl_clamp false trigger | Valid — small premium causes immediate trigger | Raise default 0.5→1.5, add ₹1k floor guard |
| S3: CRITICAL full exemption | Initially accepted → reverted after 3rd pass | Kept fully exempt — partial damp was <5% behavioral difference at typical params; adds code confusion |
| S4: high_risk_mode auto-expiry | Valid operational safety concern | Add `_high_risk_mode_expires_at` runtime key (4h) |
| S5: vol_regime_damp 0.4→0.2 | Valid — 0.4 is too aggressive a reduction | Lower default to 0.2 |
| S6: high_risk_mode in dashboard | Valid UX — time-sensitive toggle | Add quick-action to MMMBreakevenPanel |
| S7: dry_run shadow mode | Valid — responsible live deployment practice | Add `breakeven_dte_dry_run` param, default True in PRESET_5DTE |
| S-MINOR-1: orphan param | Valid — remove dead config surface | Remove `breakeven_dte_aggression_min` |
| S-MINOR-2: count inconsistency | Valid — fix to 8 params | Resolved: 8 params confirmed |

**All 7 issues accepted.** No rejections — critique was well-targeted at real operational risks.

---

## 11. REVISED PARAM LIST (POST SECOND REVIEW)

**New params from this plan: 8 (up from 3 original)**

| Param | Type | Default | PRESET_5DTE | Description |
|-------|------|---------|-------------|-------------|
| `breakeven_dte_threshold_mult` | float 1.0–5.0 | 1.0 | **1.5** | √T threshold scale at session start |
| `breakeven_dte_aggression_damp` | float 0.0–0.4 | 0.0 | **0.1** | Max-mult reduction at early DTE (CRITICAL always fully exempt) |
| `breakeven_dte_vol_regime_damp` | float 0.0–1.0 | **0.2** | **0.2** | Reduce DTE widening when vol regime is ELEVATED/HIGH |
| `breakeven_dte_pnl_clamp_pct` | float 0.5–3.0 | **1.5** | **1.5** | Disable DTE scaling if loss > X× collected premium (inactive until ≥5 lots sold) |
| `breakeven_tv_credit_factor` | float 0.0–0.5 | 0.0 | 0.0 | Tier 3: time-value P&L credit (0=disabled, defer) |
| `breakeven_high_risk_mode` | bool | False | False | Override: force dte_scale=1.0 for known event windows (auto-expires after 4h) |
| `breakeven_critical_lot_ceiling` | float 2.0–6.0 | 4.0 | 4.0 | Combined multiplier ceiling override when zone=CRITICAL |
| `breakeven_dte_dry_run` | bool | False | **True** | Shadow mode: compute DTE scale but use dte_scale=1.0 for actual decisions; logs computed vs effective |

> `breakeven_dte_aggression_min` removed — was orphan with no implementation. Will be designed in Tier 4 if needed.

---

## 13. UPDATED FILES TO MODIFY (FINAL)

| File | Change |
|------|--------|
| `mmm_breakeven_engine.py` | Add `_compute_dte_scale()` (vol_regime_damp @ 0.2, UTC-aware high_risk_mode auto-expiry); update `_classify_zone()`, `_compute_multiplier()` (CRITICAL fully exempt from damp); lot-count floor + pnl_clamp @ 1.5 in `_build_result()`; dry-run shadow (always emit both `dte_scale_computed` + `dte_scale_effective`); `_empty_result()` |
| `mmm_config.py` | Add 8 new params + descriptions |
| `mmm_state.py` | Add 8 defaults to DEFAULT_PARAMS + HOT_RELOAD_PARAMS |
| `mmm_dte_presets.py` | Update PRESET_5DTE: mult=1.5, damp=0.1, dry_run=True, vol_regime_damp=0.2, pnl_clamp_pct=1.5 |
| `mmm_engine.py` | Add `breakeven_critical_lot_ceiling` override in combined ceiling block |
| `MMMBreakevenPanel.js` | Add dte_scale indicator + dollar-denominated market BE estimate + high_risk_mode quick-action toggle |
| `MMMSettingsDialog.js` | Add 8 new param inputs in Breakeven Engine section |

**Critical implementation notes:**
- `mmm_state.py`: `breakeven_dte_dry_run` MUST be in `HOT_RELOAD_PARAMS` — operator needs to disable it mid-session after reviewing first canary logs
- `mmm_breakeven_engine.py`: `_empty_result()` must include `dte_scale_computed: 1.0`, `dte_scale_effective: 1.0`, `dte_dry_run: False` — always present, no null-checks in frontend
- `_high_risk_mode_expires_at`: write with `datetime.now(timezone.utc)` (NOT `datetime.utcnow()`) — must be UTC-aware for comparison
- Dry-run display: when `dte_dry_run=True`, show `dte_scale_computed` with "(observation)" label in MMMBreakevenPanel (not `dte_scale_effective=1.0`)

**Files NOT modified:** `mmm_monitor.py`, `mmm_api.py`, `mmm_regime.py`, `mmm_gamma_detector.py`, `mmm_close_at_5.py`, `mmm_harvester.py`, `mmm_recycler.py`

---

## 11. VALIDATION PLAN (AFTER IMPLEMENTATION)

1. **Run sealed tests** — count must not drop below 436
2. **Assert `_vol_regime` readable**: mock session after regime eval → `session.get('_vol_regime', 'NORMAL')` returns correct constant
3. **Test `_compute_dte_scale()` at t_ratio=1.0**, mult=1.5 → scale ≈ 1.5
4. **Test at t_ratio=0.25** → scale ≈ 1.25
5. **Test pnl_clamp lot-count floor**: 3 lots total, loss > 1.5× premium → clamp does NOT fire (below MIN_LOTS=5)
6. **Test pnl_clamp active**: 6 lots total, `pnl_at_spot = -$X`, `total_premium = $Y`, and `X/Y > 1.5` → dte_scale clamped to 1.0
7. **Test CRITICAL full exemption**: damp=0.1 in CRITICAL → effective_damp = 0.0 (full aggression unchanged)
8. **Test dry_run=True**: dte_scale computed but effective = 1.0; result always contains `dte_scale_computed`, `dte_scale_effective`, `dte_dry_run`
9. **Test dry_run=False**: result still contains all three fields; `dte_scale_computed == dte_scale_effective`
10. **Test high_risk_mode auto-expiry (UTC-aware)**: write `_high_risk_mode_expires_at` as past UTC ISO string → expiry check fires, DTE scaling resumes; verify no TypeError from naive/aware mismatch
11. **Verify backward compat**: session without any new params uses defaults → dte_scale = 1.0 always
12. **Live canary dry_run=True** — success/abort criteria:
    - **PASS**: At least one heartbeat where `dte_scale_computed > 1.2` AND `zone_computed` would have been WARNING/DANGER but static zone was SAFE → confirms feature prevents false alarm
    - **PASS**: Verify clamp fires when appropriate (`dte_scale_computed` drops to 1.0 when total_lots ≥ 5 and loss is deep)
    - **EXTEND canary** (don't disable dry_run): If BTC didn't move meaningfully toward strikes during the session and `dte_scale_computed` never exceeded 1.1 — no stress scenario observed, wait for another session
    - **ABORT feature**: If during canary the session hits max-loss or ATM shield fires twice — adversarial session, not a valid validation. Run another canary first.
    - After PASS: hot-reload `breakeven_dte_dry_run=False` (confirm it's in HOT_RELOAD_PARAMS), verify `dte_scale_effective` now equals `dte_scale_computed` in next heartbeat

---

## 14. DECISION REQUIRED FROM OPERATOR

1. **Approve Tier 1 + Tier 2** with all review integrations (first+second pass)
2. **First-deployment mult=1.5** confirmed (R7 + S7 dry_run provides validation path before tuning up to 2.0)
3. **PRESET_5DTE dry_run=True for first session** — review logs, then set False. Comfortable with this?
4. **CRITICAL zone: full exemption confirmed** (S3 partial damp reverted — 50% partial damp produced <5% behavioral difference at typical params, added code confusion for no gain)
5. **`breakeven_critical_lot_ceiling=4.0`** — keep at 4.0 or lower?
6. **Tier 3 (TV credit)** — defer until Tier 1 validated? (Recommended: defer)
7. **Tier 4 (IV-based + asymmetric CE/PE)** — design scope for next iteration?

---

---

## 16. THIRD-PASS CRITIQUE — HONEST EVALUATION

*6 issues flagged. 3 are genuine code bugs that must be fixed before implementation.*

---

### T1 — `datetime.utcnow()` in high_risk_mode Auto-Expiry ✅ FIXED (Code Bug)

**Critique:** S4 pseudocode used `datetime.utcnow()` (naive datetime) when writing `_high_risk_mode_expires_at`, and `datetime.utcnow()` in the comparison. The codebase-wide robustv2 fix #14 replaced ALL `datetime.utcnow()` with `datetime.now(timezone.utc)`. Mixing aware (`datetime.now(timezone.utc)`) and naive (`datetime.fromisoformat()` of a naively-written timestamp) datetimes raises `TypeError` at runtime when the auto-expiry comparison fires.

**Assessment: Correct. Genuine code bug in the plan's pseudocode.** Fixed: S4 code updated to use `datetime.now(timezone.utc)` everywhere, plus defensive `if expires_at.tzinfo is None: expires_at.replace(tzinfo=timezone.utc)` guard.

---

### T2 — pnl_clamp Floor ₹1,000 INR: Wrong Currency Unit ✅ FIXED (Code Bug)

**Critique:** S2 used `MIN_PREMIUM_FLOOR = 1000  # INR` but `mmm_breakeven_engine.py` operates in USD (premiums in USD/BTC, LOT_SIZE_BTC=0.001). ₹1,000 ≈ $12 USD — effectively zero. The clamp would still fire almost immediately after the first lot is sold.

**Assessment: Correct.** The INR appeared to be copied from the display layer (which converts to rupees for the frontend). The engine's `total_premium_collected` is USD. Fixed: replaced with `MIN_LOTS_FOR_CLAMP = 5` lot-count floor — currency-agnostic and semantically clearer (clamp only fires when meaningful position size exists).

---

### T3 — CRITICAL Partial Damp (S3) Adds <5% Behavioral Difference ✅ REVERTED

**Critique:** With damp=0.1 (the default), CRITICAL partial-damp produces 0.05 effective damp vs 0.0 for full-exempt. At integer lot ceilings this difference is invisible — CRITICAL-with-50%-damp and CRITICAL-fully-exempt will always produce the same lot count in practice. The partial damp adds code complexity (damp_factor meaning two different things in different branches) for zero measurable gain.

**Assessment: Correct.** Partial damp in CRITICAL was accepted too quickly in the second pass. The analytical math looked reasonable (S3) but the practical effect at actual defaults is negligible. Reverted to full exemption. The real protection against CRITICAL false alarms is the DTE threshold scaling itself. If CRITICAL fires with dte_scale=1.5 active, the position is genuinely at risk.

---

### T4 — `breakeven_dte_dry_run` Must Be in HOT_RELOAD_PARAMS ✅ CONFIRMED (Completeness)

**Critique:** §13 says "Add 8 defaults to DEFAULT_PARAMS + HOT_RELOAD_PARAMS" but doesn't call out `breakeven_dte_dry_run` explicitly. If this param is NOT hot-reloadable, the operator can't disable dry_run mid-session — they'd have to stop and recreate the session, defeating the validation workflow.

**Assessment: Valid completeness check.** Explicit note added to §13 critical implementation notes: `breakeven_dte_dry_run` MUST be in HOT_RELOAD_PARAMS.

---

### T5 — dry_run Result Fields Missing in Non-Dry-Run Mode ✅ FIXED

**Critique:** `dte_scale_computed` and `dte_scale_effective` were only added to result dict in dry-run mode. In non-dry-run mode these fields would be absent — frontend needs null-checks everywhere. Additionally: the plan didn't specify whether dry-run mode should display the computed or effective scale.

**Assessment: Valid.** Fixed:
- Always emit all three fields (`dte_scale_computed`, `dte_scale_effective`, `dte_dry_run`) regardless of dry-run state
- In non-dry-run: `dte_scale_computed == dte_scale_effective`
- `_empty_result()` includes all three with safe defaults
- Frontend display: when `dte_dry_run=True`, show `dte_scale_computed` with "(observation)" label so operator sees what the feature *would* use, not the actual 1.0

---

### T6 — Validation Step 11 Has No Pass/Fail Criteria ✅ FIXED

**Critique:** "Manually confirm no false alarms would have been prevented" is not a testable criterion. The operator will look at logs, feel uncertain, and either disable dry_run too early or leave it on indefinitely.

**Assessment: Correct.** Step 12 (renumbered) now has explicit criteria:
- **PASS**: At least one heartbeat where `dte_scale_computed > 1.2` AND `zone_computed` would have been WARNING/DANGER but static zone was SAFE
- **EXTEND**: If BTC didn't move toward strikes during the session and `dte_scale_computed` never exceeded 1.1 — no stress scenario observed, run another canary
- **ABORT**: If session hits max-loss or ATM shield fires twice — adversarial session, not valid validation

---

### THIRD-PASS SUMMARY

| Issue | Classification | Action |
|-------|---------------|--------|
| T1: `datetime.utcnow()` in auto-expiry | Code bug — TypeError at runtime | Fixed: use `datetime.now(timezone.utc)` |
| T2: INR floor in USD-denominated engine | Code bug — wrong unit | Fixed: lot-count floor MIN_LOTS=5 |
| T3: CRITICAL partial damp negligible | Logic flaw — adds complexity for 0 gain | Reverted: CRITICAL fully exempt |
| T4: `dry_run` not in HOT_RELOAD_PARAMS | Completeness gap — operator can't disable | Explicit note added to §13 |
| T5: dry_run fields missing in non-dry-run | Design gap — frontend null-checks required | Fixed: always emit all three fields |
| T6: canary step lacks pass/fail criteria | Operational gap — validation is theater | Fixed: concrete pass/extend/abort criteria |

**0 rejections.** All 6 issues were genuine. The third pass found the two most critical code bugs (T1, T2) that would have caused runtime failures on first deployment.

---

*Plan authored March 16, 2026. First-pass review integrated March 16, 2026. Second-pass review integrated March 16, 2026. Third-pass review integrated March 16, 2026. Implemented March 16, 2026. Post-implementation code review March 16, 2026 (4 bugs fixed — see §18).*

---

## §18 POST-IMPLEMENTATION BUG FIXES (Code Review, March 16, 2026)

A senior developer code review after implementation found 4 bugs not caught by the plan:

### BUG-1: pnl_clamp wrong denominator ✅ FIXED
**Found:** `_build_result()` used `sum(p['entry_premium'] * p['lots'] for p in positions)` as denominator.
**Problem:** After harvesting lots, this shrinks while `total_premium_collected` stays high. A normal $300 loss on $200 remaining positions = 1.5× ratio → clamp fires. Against full session $1000 = 0.3× → correct: clamp should NOT fire.
**Also:** `abs(pnl_at_spot)` without `< 0` guard fires clamp on profitable positions.
**Fix:** Use `session.get('total_premium_collected')` as denominator. Add `pnl_at_spot < 0` guard. Add `dte_scale > 1.0` guard (skip when scaling disabled).

### BUG-2: high_risk_mode didn't force dte_scale=1.0 ✅ FIXED
**Found:** Engine only set `aggression_damp = 0` in high_risk_active block. `dte_scale` remained at 1.5.
**Problem:** FOMC override worked for lot size (max aggression) but NOT for threshold sensitivity (still wide). Bot wouldn't react to breakeven zone until spot was 3% from intrinsic — not 2% as operator expected.
**Fix:** Add `dte_scale = 1.0` alongside `aggression_damp = 0.0` in the high_risk_active block.

### BUG-3: vol_regime_damp didn't reduce dte_scale ✅ FIXED
**Found:** `_compute_dte_scale()` had no vol_regime check — it computed pure √T formula.
`vol_regime_damp` only substituted for `aggression_damp` in `_build_result()`.
**Problem:** At HIGH vol, threshold widening was unchanged (still 1.5×). Only lot aggression changed. Plan intended dte_scale to be reduced at elevated vol to tighten thresholds automatically.
**Fix:** Added vol_regime damping inside `_compute_dte_scale()`: `dte_scale = 1.0 + (dte_scale - 1.0) * (1.0 - damp)`.

### BUG-4: `_high_risk_mode_expires_at` never written ✅ FIXED
**Found:** Engine reads `session.get('_high_risk_mode_expires_at')` for auto-expiry. No code in codebase wrote it.
**Problem:** Auto-expiry was dead code. Once operator enabled high_risk_mode, it stayed on for the entire 5-day session.
**Fix:** Added setter in `mmm_api.py` `update_session_params` endpoint. `breakeven_high_risk_mode` toggle True → sets `session['_high_risk_mode_expires_at'] = (now + 4h).isoformat()`. Toggle False → clears it. Uses `datetime.now(timezone.utc)` (not `utcnow()`).

### NOT IMPLEMENTED: dry_run shadow mode
Plan §S7 proposed `breakeven_dte_dry_run` observation mode. **Rejected by operator** — real money trading from day 1, no shadow mode needed. Removed from codebase. All implementation is live from first 5DTE session.

---

## §17 IMPLEMENTATION NOTES

### Files Changed (7)

| File | Change |
|------|--------|
| `mmm_breakeven_engine.py` | Added `_compute_dte_scale()`, updated `_classify_zone()` + `_compute_multiplier()` signatures, expanded `_build_result()` with DTE block, updated `_empty_result()` |
| `mmm_config.py` | Added 8 new PARAM_RULES entries + 8 descriptions |
| `mmm_state.py` | Added 8 defaults to DEFAULT_PARAMS, 8 entries in HOT_RELOAD_PARAMS |
| `mmm_dte_presets.py` | Added breakeven DTE params block to PRESET_5DTE (dry_run=True) |
| `mmm_engine.py` | CRITICAL zone ceiling override: uses `breakeven_critical_lot_ceiling` instead of `max_combined_lot_multiplier` when `_breakeven_zone == 'CRITICAL'` |
| `MMMBreakevenPanel.js` | Destructured new fields; added DTE scale chip (`DTE 1.47×`) in header; added Effective Thresholds row in expanded section |
| `MMMSettingsDialog.js` | Added 3 new sections under breakevenEngine group + 7 PARAM_TOOLTIPS |

### Key Implementation Decisions

1. **Backward compatibility confirmed**: `breakeven_dte_threshold_mult=1.0` (default) → `_compute_dte_scale()` returns `(1.0, 1.0, dry_run)` immediately. All existing sessions unaffected.

2. **pnl_clamp uses lot-count floor**: `MIN_LOTS_FOR_CLAMP = 5` (not an INR floor). Prevents false trigger on tiny canary/test sessions. All positions counted using `p['lots']`.

3. **Multiplier continuity maintained with damp**: WARNING ends at `1.0 + 0.3*damp_factor`; DANGER starts at same value (`1.0 + 0.3*damp_factor` at progress=0). No discontinuity at zone boundary regardless of damp value.

4. **High risk mode auto-expiry**: Reads `session['_high_risk_mode_expires_at']` (set externally by API when param toggled). Timezone guard: `.replace(tzinfo=timezone.utc)` if naive. Uses `datetime.now(timezone.utc)` throughout — no `utcnow()`.

5. **CRITICAL fully exempt from damp**: As planned. If CRITICAL fires despite dte_scale widening, it is a genuine emergency. Damp would be dangerous there.

6. **expiry_time source**: Uses `session['expiry_time']` (ISO UTC string set at session creation in `mmm_state.py` C-5 fix). Falls back to `total_dte_hours` if missing.

7. **Vol regime damp is an override**: When vol_regime is ELEVATED/HIGH, `breakeven_dte_vol_regime_damp` replaces `breakeven_dte_aggression_damp` entirely (not added). High risk mode then overrides all damp to 0.

### WebUI Visual Coverage

| Element | Where | What it shows |
|---------|-------|---------------|
| `DTE 1.47×` chip | Panel header | Scale factor is active; hidden when dte_scale ≤ 1.01 |
| Effective Thresholds row | Expanded section | `W 2.94% / D 1.47% / C 0.74%` — actual firing distances with DTE applied; hidden when dte_scale ≤ 1.01 |
| Aggression multiplier chip | Panel header | Current lot boost multiplier (unchanged) |
| Zone/distance bar | Panel body | Spot position relative to breakeven boundaries (unchanged) |
| DTE params sections | Settings Dialog | 3 sections: Scaling, Aggression Controls, Safety Limits |

Backend sends `effective_warning_pct`, `effective_danger_pct`, `effective_critical_pct` = `param × dte_scale` in every result dict. Frontend computes nothing — all threshold logic lives in the engine.

### Deployment Checklist

- [ ] PRESET_5DTE ships with `breakeven_dte_dry_run: True` — first session runs in observation mode
- [ ] Monitor `dte_scale_computed` in breakeven panel for one full 5DTE session
- [ ] If values look reasonable (1.3–1.5× at start, decaying to 1.0), hot-reload `breakeven_dte_dry_run=false`
- [ ] 0DTE sessions: `breakeven_dte_threshold_mult=1.0` (default) — no change in behavior


---

