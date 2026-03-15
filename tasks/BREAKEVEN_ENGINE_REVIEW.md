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
