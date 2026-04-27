# PHASE 06 — Mathematical Model Audit
**Lead Agent:** Mathematical Model Agent
**Status:** COMPLETE
**Date:** 2026-04-26
**Prior Phases Read:** Phase 01 Architecture, Phase 02 Accounting, Phase 03 P&L, Phase 04 Risk Controls, Phase 05 Strategy Logic

---

## Executive Summary

The core quantitative formulas in the MMM system are mathematically sound. The lot sizing formula correctly converts USD loss-to-cover into lots via premium × LOT_SIZE_BTC, the trigger system's percentage-from-snapshot approach produces symmetric sensitivity across premium levels, the breakeven engine uses a correct intrinsic-only model with appropriate conservative bias, and the gamma dollar-gamma formula is mathematically verified. The primary structural issue is the **multiplier chain in `calculate_lots_to_sell()`** — seven multipliers are applied in strict sequence with a combined-ceiling cap, but the IMP-2 floor ceiling is computed from `raw_lots` while later multipliers operate on the post-IMP2 value, creating asymmetric interactions. A second structural concern is the **M2 recycling trigger relying on string-matching** the error message from `calculate_lots_to_sell()`. No P0 issues found.

**Mathematical Model Grade: A-** — formulas are correct; multiplier ordering has documented interactions worth monitoring at scale.

---

## 1. Core Constants Verification

| Constant | Value | Verified | Notes |
|---|---|---|---|
| `LOT_SIZE_BTC` | 0.001 | ✓ | 1 BTC = 1000 lots on Delta Exchange |
| USD per lot at price P | `P × 0.001` | ✓ | `premium × LOT_SIZE_BTC` |
| `TRIGGER_PCT_FLOOR` | 1.0 | ✓ | Prevents div-by-zero in trigger pct calculation |
| `strike_key()` | `str(int(round(float(s))))` | ✓ | Canonical key — prevents float-string mismatch |

**Lot size chain verified:** 1 lot = 0.001 BTC. At spot=$85,000: 1 lot = $85 notional. 100 lots = $8,500 notional. This is consistent across engine, pnl_core, breakeven_engine, and gamma.

---

## 2. Trigger Formula — Verified

### 2.1 Percentage-Based Trigger

```
triggered = ((premium_now - trigger_snapshot) / trigger_snapshot × 100) > min_trigger_move
```

With `TRIGGER_PCT_FLOOR = 1.0` as divisor floor.

**Derivation check:**
- If `trigger_snapshot = 100`, `min_trigger_move = 15` → fires at `premium_now > 115` ✓
- `ce_excess_pct = ((ce_now - ce_trigger) / max(ce_trigger, 1.0)) × 100`
- For `ce_trigger=80, ce_now=94`: `excess_pct = (14/80)×100 = 17.5%` → fires at 15% threshold ✓
- Symmetric sensitivity: a 15% threshold on CE@$200 requires $30 move, on PE@$80 requires $12 — both equally meaningful as proportional moves ✓

**Trigger snapshot ratcheting:** After each adjustment, `update_trigger_snapshots()` ratchets the snapshot to the current premium. Next trigger fires at `current × (1 + threshold/100)`. This is a compounding threshold — correct for momentum hedging.

### 2.2 Dollar Floor Trigger (Optional)

```
ce_dollar_excess = max(ce_excess, 0) × active_lots × LOT_SIZE_BTC
triggered |= ce_dollar_excess > min_trigger_dollar
```

**Derivation check:** `ce_excess × active_lots × LOT_SIZE_BTC` = absolute USD loss on active CE position from trigger snapshot. Correct sign: only positive excess counts (negative = premium declining, not a trigger). Uses active_lots only (frozen positions excluded from this calculation — handled by separate `check_frozen_pnl_trigger()`). ✓

**Finding A6-01 (P2):** `min_trigger_dollar` is OR-combined with the percentage trigger. A very small `min_trigger_dollar` (e.g., $5) on a large position would fire almost every heartbeat when any price movement occurs — the dollar floor would dominate the percentage threshold. There is no enforcement that `min_trigger_dollar > 0` means "only meaningful dollar moves". Since default is 0 (disabled), this is a misconfiguration risk, not a code bug.

---

## 3. Loss-to-Cover Formula — Verified

### 3.1 Standard Loss (`calculate_standard_loss`)

```
active_loss = (premium_now - trigger_snapshot) × active_lots × LOT_SIZE_BTC
shifted_loss = Σ max((current_premium_i - baseline_i) × lots_i × LOT_SIZE_BTC, 0)
total_loss = max(active_loss + shifted_loss, 0)
```

Where baseline = `trigger_snapshot[strike]` if available, else `entry_premium`.

**Derivation check:**
- Short option seller's loss when premium rises: `(current - entry) × lots × size_per_lot` ✓
- `active_loss` can be negative when premium_now < trigger (option decaying) — clamped to zero at total_loss ✓
- Shifted positions: only positive losses added (profitable frozen positions do NOT reduce hedge requirement) — intentionally conservative ✓
- Uses Decimal arithmetic internally via `_D()` ✓

**Finding A6-02 (P2):** The shifted loss calculation uses `trigger_snapshot` as baseline to avoid double-counting already-hedged losses. But `update_trigger_snapshots()` only ratchets snapshots for the active strike and for adjustment fills. If a frozen position at an old strike was last hedged 5 heartbeats ago and its snapshot hasn't been updated since, the incremental loss since that hedge is correctly measured. However, if `trigger_snapshots` is missing for a frozen strike (e.g., session restored without snapshot state), `entry_premium` is used as fallback — this could overcount losses already covered by prior hedges. The risk is low (sessions are rarely restored mid-hedge), but it is a known edge case.

### 3.2 Reversal Loss (`calculate_reversal_loss`)

```
adjustment_pnl = Σ (entry_premium_i - current_i) × lots_i × LOT_SIZE_BTC
active_strike_pnl = same formula but only for active-strike fills
loss_to_cover = |active_strike_pnl| if active < 0, else |adjustment_pnl| if total < 0, else 0
```

**FM2 fix:** Uses `active_strike_pnl` as primary gate — a profitable frozen position at an old strike cannot mask a genuine loss at the current active strike. The distinction between active_strike_pnl and total adjustment_pnl is correct.

**Sign check:** `(entry_premium - current) × lots × LOT_SIZE_BTC`
- Entry premium > current (option decayed): positive P&L ✓
- Entry premium < current (option expanded, loss): negative P&L ✓

**Verified: Reversal formula correctly computes short-option P&L.**

---

## 4. Lot Sizing Formula — Verified

### 4.1 Base Formula

```
raw_lots = loss_to_cover / (hedge_premium × LOT_SIZE_BTC) × (1 + buffer_pct)
lots_to_sell = max(ceil(raw_lots), 1)
```

**Derivation check:**
- We need `lots_to_sell × hedge_premium × LOT_SIZE_BTC >= loss_to_cover`
- So `lots_to_sell >= loss_to_cover / (hedge_premium × LOT_SIZE_BTC)`
- Buffer adds `buffer_pct` (default 5%) to ensure rounding never undershoots ✓
- `ceil()` ensures integer lots ✓
- Floor at 1: always sell at least 1 lot (ensures response even for tiny losses) ✓

**Example verification:**
- loss_to_cover = $50, hedge_premium = $100, buffer_pct = 0.05
- `raw_lots = 50 / (100 × 0.001) × 1.05 = 50 / 0.1 × 1.05 = 525`
- `lots_to_sell = 525` — these 525 lots collect `525 × $100 × 0.001 = $52.50` (covers $50 loss + $2.50 buffer) ✓

### 4.2 Multiplier Chain

Seven multipliers are applied in sequence to `lots_to_sell`. Understanding the ordering is critical:

| Step | Multiplier | Formula | Default | Effect |
|---|---|---|---|---|
| 1 | Base | `raw_lots × (1 + buffer)` | buffer=5% | Upward amplifier |
| 2 | Gamma-aware | 1.0–1.3x based on aggressor_excess_pct | off | Amplifier |
| 3 | Breakeven | 1.0–max_mult based on zone | off | Amplifier |
| 4 | Gamma severity | 1.0–1.5x based on DANGER zone | off | Amplifier |
| 5 | Trend boost (up) | 1.3–2.0x on safe side | off | Amplifier |
| 5 | IMP-2 trend reduction | 0.7x on dangerous side | off | Reducer w/ ceiling |
| 6 | Combined ceiling | cap combined_mult at max_combined=3.0 | 3.0 | Cap |
| 7 | Data confidence | `floor(lots × confidence)` | 1.0 | Reducer |
| 8 | Position cap | `max_lots_per_side - current_total` | — | Hard cap |
| 9 | Total exposure cap | `max_total_exposure - current_total` | 2× max_lots | Hard cap |
| 10 | OTM scaling | multiplier < 1.0 after strike shift | off | Reducer |

**Finding A6-03 (P1):** The IMP-2 trend reduction at step 5 applies a `max(ceil(raw_lots × multiplier), 1)` ceiling where the ceiling is computed from `raw_lots` — the pre-multiplier value. This means if breakeven (step 3) inflated lots to 150 and IMP-2 then reduces to 70%:

1. Before IMP-2: `lots_to_sell = 150` (after breakeven 1.5x applied to raw=100)
2. IMP-2 ceiling: `imp2_ceiling = ceil(raw_lots × 0.7) = ceil(100 × 0.7) = 70`
3. IMP-2 result: `lots_to_sell = min(150×0.7, 70) = min(105, 70) = 70`

Result: The breakeven aggression boost is completely cancelled by IMP-2. The C5 FIX comment acknowledges this: "enforce a hard ceiling: result must not exceed `ceil(raw_lots × multiplier)` — the value IMP-2 would have produced from a clean baseline." This is the intended behavior: IMP-2 (trend safety reduction) must dominate breakeven aggressiveness when a trend is detected.

**Risk:** At 5x capital, with breakeven zone=DANGER (1.5x) + gamma_severity (1.3x) + trend_reduction (0.7x), the combined ceiling (step 6) fires but only sees `combined = 1.5 × 1.3 × 1.0 = 1.95`. IMP-2 is not included in `combined` (because `_trend_boost_active=False` when IMP-2 reduction ran). So the combined ceiling doesn't cap IMP-2's side. The result may be fewer lots than expected, but that's safe (underhedge rather than overhedge for a trending market). Correct.

**Finding A6-04 (P1):** The M2 recycling trigger in `mmm_monitor.py` (~line 2615) detects position cap by string-matching the error message from `calculate_lots_to_sell()`. The position cap path returns:

```python
return 0, f"Position cap reached: {hedge_side.upper()} has {current_total}/{max_lots_per_side} lots (active+frozen)", True
```

And the total exposure cap path explicitly comments: "IMPORTANT: error message must NOT contain 'Position cap reached'". This is **fragile string-based IPC**: the monitor activates M2 recycling based on whether the constraint message contains the literal string "Position cap reached". If a developer changes the position cap message wording, M2 recycling silently breaks. The `is_position_cap_hit` boolean (3rd return value) was added in Fix F1.6 specifically to replace this pattern, but the monitor may still check the string for backward compatibility. This needs Phase 8 verification that the monitor uses `is_position_cap_hit` rather than string matching.

---

## 5. Gamma Formula — Verified

### 5.1 Portfolio Gamma Accumulation

```python
position_gamma = greek_gamma × lots × LOT_SIZE_BTC
portfolio_gamma = Σ position_gamma_i  # (from exchange greeks)
```

**Verified:** `greek_gamma` is per BTC per $ (standard Delta Exchange format). Multiplying by lots × LOT_SIZE_BTC converts to total BTC exposure. ✓

### 5.2 Dollar Gamma Formula

```
$Γ = |Γ_portfolio| × S² × 0.01
```

**Derivation verification:**
- `Γ_portfolio` has units: BTC/$ (change in BTC delta per $1 spot move)
- Dollar delta = `delta_BTC × S` (in USD)
- Change in dollar-delta for $dS move: `Γ × dS × S`
- For a 1% move: `dS = 0.01S`
- Dollar delta change = `Γ × 0.01S × S = Γ × S² × 0.01` ✓

The code comment says "NOT gamma P&L (which would be ½ × Γ × (0.01S)² = Γ × S² × 0.00005)". This is correct — the formula computes **dollar delta sensitivity**, not the gamma P&L (second-order). The limits are calibrated to this formula and are labeled in the code.

### 5.3 Near-Expiry Multiplier

```python
if minutes_to_expiry <= 30:
    multiplier = params.get('gamma_near_expiry_multiplier', 0.5)
    soft_limit *= multiplier  # halved by default
    hard_limit *= multiplier
    emergency_limit *= multiplier
```

**Finding A6-05 (P2):** Near-expiry gamma multiplier **lowers** the limits (multiplier=0.5 → halved), making the regime MORE sensitive near expiry. This is correct — gamma spikes near expiry, so the cap tightens. However, the multiplier is 0.5 (default), meaning inside 30 minutes the system is twice as likely to hit HARD or EMERGENCY gamma. For a 0DTE strangle, the window inside 30 minutes is typically the `auto_close_mins` zone where all positions should already be closed. If close_at_5 is working correctly, gamma exposure near expiry should be approaching zero. But if positions remain (e.g., hard to close due to liquidity), the halved limits create aggressive blocking right when position closure is most urgent.

### 5.4 Projected Gamma (Pre-Trade Check)

```python
projected_dollar_gamma = (|current_gamma| + |new_position_gamma|) × S² × 0.01
```

**Finding A6-06 (P3):** Projected gamma adds absolute values: `abs(current_gamma) + abs(new_gamma)`. For a portfolio that is long gamma on CE and short gamma on PE (e.g., after a rebalancing), this would overstate the projected gamma since CE and PE gamma contributions partially cancel. However, for a short-only strangle (the primary use case), all positions are short-gamma and the signs add correctly. ✓ for the strangle case.

---

## 6. Breakeven Engine Formula — Verified

### 6.1 Portfolio P&L at Hypothetical Spot

For short call at strike K, lots N, entry P:
```
intrinsic = max(spot_h - K, 0)
pnl = (P - intrinsic) × N × LOT_SIZE_BTC
```

For short put at strike K, lots N, entry P:
```
intrinsic = max(K - spot_h, 0)
pnl = (P - intrinsic) × N × LOT_SIZE_BTC
```

**Sign verification:**

| Case | Position | Math | Result |
|---|---|---|---|
| Short call, OTM (spot < K) | intrinsic=0 | (P - 0) × N × 0.001 > 0 | Profit ✓ |
| Short call, ATM/ITM (spot = K + P) | intrinsic=P | (P - P) × N × 0.001 = 0 | Breakeven ✓ |
| Short call, deep ITM | intrinsic >> P | (P - intrinsic) < 0 | Loss ✓ |
| Short put, OTM (spot > K) | intrinsic=0 | (P - 0) > 0 | Profit ✓ |
| Short put, ITM (spot = K - P) | intrinsic=P | = 0 | Breakeven ✓ |

Upper breakeven: spot = K_CE + entry_premium_CE (when call loss = premium collected) ✓
Lower breakeven: spot = K_PE - entry_premium_PE (when put loss = premium collected) ✓

### 6.2 Perp Hedge P&L (BUG-C5 Fix Verified)

```python
perp_pnl = (spot_h - avg_entry) × perp_lots × LOT_SIZE_BTC
```

`perp_lots` is signed (positive=long, negative=short). For a long perp at avg_entry=85000:
- If spot_h rises to 86000: pnl = (86000 - 85000) × lots × 0.001 > 0 ✓
- Breakeven line shifts the portfolio P&L curve linearly — correct for perp delta hedging ✓

**Finding A6-07 (P2):** The breakeven engine uses the **intrinsic-only model** (ignores time value). This creates a conservative bias: the model's breakeven band is narrower than reality (actual breakeven is wider because time value provides additional buffer). At 5DTE start of session, options may have significant time value (e.g., $200 time value in a $300 premium). The intrinsic model treats the position as at breakeven at spot = K ± intrinsic, while the actual breakeven is spot = K ± $300 (full premium). This means the breakeven engine fires WARNING/DANGER earlier than actual risk warrants.

**Conservative direction is correct for a risk tool.** The over-aggressiveness of early warnings may inflate lot counts at 5DTE start — this should be monitored at scale.

### 6.3 Breakeven Binary Search Precision

Pass 2 converges to within `$10` (binary search, 20 iterations max).

**Precision check:** For a $85,000 spot, $10 precision = 0.012% of spot. The position size effect of a $10 shift in breakeven is negligible for lot calculations. ✓

### 6.4 Aggression Multiplier Ramp

Zone ranges:
- SAFE: 1.0x (no multiplier)
- WARNING: 1.0 → 1.3x (linear interpolation based on distance from boundary)
- DANGER: 1.3 → 2.0x
- CRITICAL: 2.0 → `breakeven_aggression_max` (default 2.5x)

**Finding A6-08 (P2):** The breakeven multiplier is non-directional — it applies to ANY triggered adjustment regardless of which side is the aggressor. If spot approaches the lower breakeven (PE side at risk), both CE and PE adjustments get the multiplier. A CE adjustment at lower breakeven adds more premium on the wrong side. The documentation says this is intentional ("non-directional: applies to ANY triggered adjustment"). The financial rationale: when spot approaches breakeven, you want more coverage on both sides because a reversal could swing the other way. This is defensible but directional traders may find it counter-intuitive.

---

## 7. Decimal Precision Analysis

### 7.1 _D() Function Consistency

Phase 3 identified 5 independent `_D()` definitions. Phase 6 confirms:
- `mmm_constants.py`: `def _D(x): return Decimal(str(x))`
- `mmm_engine.py`: `def _D(x): return Decimal(str(x))`
- `mmm_pnl_core.py`: `_D = Decimal` (type alias — used as `_D(str(x))`)
- `mmm_straddle_adjustment.py`: `def _D(x): isinstance check + Decimal(str(x))`
- `mmm_straddle_roll_pure.py`: `def _D(x): isinstance check + try/except + Decimal('0')`

All are functionally equivalent for normal inputs. The straddle modules have extra safety (isinstance check, exception handling). Only `mmm_pnl_core.py` is slightly different (`_D = Decimal` means callers do `_D(str(x))` rather than `_D(x)`).

**Finding A6-09 (P2):** Carries forward from Phase 3 A3-03 — 5 independent `_D()` definitions. Not a bug but technical debt. A precision fix requires 5 updates.

### 7.2 Where Decimal is Used vs Float

| Module | Internal Arithmetic | API Boundary |
|---|---|---|
| `mmm_engine.py` | Decimal (`_D`) | `float()` at return |
| `mmm_pnl_core.py` | Decimal | `round(float, 8)` at session write |
| `mmm_straddle_adjustment.py` | Decimal | `float()` at return |
| `mmm_straddle_roll_pure.py` | Decimal | `float()` at return |
| `mmm_breakeven_engine.py` | `float` throughout | N/A |
| `mmm_gamma.py` | `float` throughout | N/A |
| `mmm_trigger.py` | `float` throughout | N/A |

**Finding A6-10 (P3):** `mmm_breakeven_engine.py`, `mmm_gamma.py`, and `mmm_trigger.py` use Python `float` throughout with no Decimal. These are display/regime modules (not order-sizing), so IEEE 754 accumulation risk is lower. However, `mmm_trigger.py`'s `ce_dollar_excess = ce_excess × active_lots × LOT_SIZE_BTC` multiplies a float chain. At 1000 lots and $200 excess, the value is $200 × 1000 × 0.001 = $200.00 — no significant precision loss at current capital levels. At 10x capital (10,000 lots), the multiplication `0.001 × 10000 = 10.0` is exact in binary floating point. ✓

---

## 8. Scaling Analysis (5x and 10x Capital)

| Formula | Current (100 lots) | 5x (500 lots) | 10x (1000 lots) | Risk |
|---|---|---|---|---|
| Lot sizing: `loss / (prem × 0.001)` | Works | Works | Works | None — linear |
| Trigger: `(prem_now - snap) / snap × 100` | Works | Works | Works | None — no lot dependency |
| Dollar gamma: `\|Γ\| × S² × 0.01` | ~$1000 at 100 lots | ~$5000 at 500 | ~$10000 at 1000 | **Gamma limits** |
| Breakeven scan: ~80 points × 1ms | 0.08ms | Same | Same | None — O(1) in lots |
| Combined multiplier ceiling | 3.0x cap | 3.0x cap | 3.0x cap | Holds |

**Finding A6-11 (P1):** At 10x capital (~1000 lots), default gamma hard_limit of $5000 would be hit almost immediately after entry for ATM options:
- 1000 lots × ~0.001 gamma/lot × $85,000² × 0.01 = ~$7,225 → exceeds hard_limit($5000) → GAMMA_HARD
- Default emergency_limit = $10,000 → 1000 lots at ATM would hit HARD but not EMERGENCY

At 5x (500 lots): `~$3,612` → approaches but may not reach HARD depending on actual gamma values. The gamma limits are calibrated for current 100-lot scale. **Before capital scaling, gamma limits MUST be reviewed and adjusted.** The params (`gamma_soft_limit`, `gamma_hard_limit`, `gamma_emergency_limit`) are in PARAM_RULES and hot-reloadable, but the defaults are not labeled as "calibrated for 100 lots" anywhere in the code.

**Finding A6-12 (P2):** Breakeven `_find_breakeven()` uses a fixed $10 convergence precision. At 10x capital, a $10 precision error in the breakeven price creates an error of `10 × 1000 × 0.001 = $10` in the P&L estimate used for zone classification. This is negligible relative to breakeven distance decisions (warning_pct=2.0% × $85,000 = $1,700). ✓ Precision holds at 10x.

---

## 9. Formula Verification Table

| Formula | Module | Manual Check | Match | Notes |
|---|---|---|---|---|
| `triggered = (prem_now - snap) / snap × 100 > threshold` | mmm_trigger | ✓ | MATCH | Percentage, not absolute |
| `loss = (prem_now - snap) × lots × 0.001` | mmm_engine | ✓ | MATCH | Active strike loss |
| `raw_lots = loss / (hedge_prem × 0.001) × (1+buffer)` | mmm_engine | ✓ | MATCH | Lot sizing |
| `$Γ = \|Γ_portfolio\| × S² × 0.01` | mmm_gamma | ✓ | MATCH | Dollar-delta sensitivity |
| `call_pnl = (entry - max(spot-K,0)) × lots × 0.001` | mmm_breakeven_engine | ✓ | MATCH | Intrinsic-only |
| `put_pnl = (entry - max(K-spot,0)) × lots × 0.001` | mmm_breakeven_engine | ✓ | MATCH | Intrinsic-only |
| `perp_pnl = (spot_h - avg_entry) × lots × 0.001` | mmm_breakeven_engine | ✓ | MATCH | Signed lots |
| Close P&L: `(entry - close) × lots × 0.001` | mmm_pnl_core | ✓ (Phase 3) | MATCH | Short seller's gain |
| Fee: `commission` from exchange fill | mmm_pnl_core | ✓ (Phase 3) | MATCH | No formula, raw value |

---

## 10. Architecture Issues — Phase 6 Entries

| ID | Problem | Risk | Priority |
|---|---|---|---|
| A6-01 | min_trigger_dollar=0 not validated; small value dominates pct trigger | Misconfiguration → near-continuous trigger firing | P2 |
| A6-02 | Frozen position trigger_snapshot missing on restore → entry_premium fallback overcounts previously hedged loss | Over-hedge after restart | P2 |
| A6-03 | IMP-2 ceiling computed from raw_lots, cancels breakeven amplifier under trend | Intended per C5 FIX; may surprise at scale | P1 |
| A6-04 | M2 recycling activated by string-match on "Position cap reached" message | Silent M2 break if message wording changes | P1 |
| A6-05 | Gamma near-expiry multiplier halves limits inside 30 min; may conflict with close_at_5 | Aggressive gamma blocking when trying to close | P2 |
| A6-06 | Projected gamma adds absolute values; cancellation from CE/PE offset not modeled | Overestimates projected gamma (conservative, safe) | P3 |
| A6-07 | Breakeven intrinsic-only model fires earlier than actual at 5DTE start | Inflated lot counts early in 5DTE session | P2 |
| A6-08 | Breakeven multiplier is non-directional (applies to both sides) | CE lots inflated when only PE is at risk | P2 |
| A6-09 | _D() defined 5 times (carries from Phase 3 A3-03) | Precision fix requires 5 updates | P2 |
| A6-10 | trigger.py, gamma.py, breakeven_engine.py use float throughout | No precision risk at current scale | P3 |
| A6-11 | Gamma limits (soft=$2500, hard=$5000) calibrated for ~100 lots; 10x capital hits hard immediately | Must raise before scaling; not labeled as lot-dependent | P1 |
| A6-12 | Breakeven $10 convergence precision adequate at 10x | No risk | P3 |

---

## 11. Positive Findings

1. **All core formulas mathematically verified** — lot sizing, loss calculation, trigger, gamma, breakeven all correct
2. **Decimal arithmetic in order-critical code** — `mmm_engine.py` uses Decimal internally, float at API boundary ✓
3. **Conservative bias in breakeven engine** — intrinsic-only model fires early warnings, appropriate for risk tool
4. **Combined multiplier ceiling prevents lot runaway** — cap at 3.0x across all amplifiers
5. **`strike_key()` prevents float/string dict mismatch** — trigger snapshots look up correctly ✓
6. **Calculation incomplete flag** — `calculate_standard_loss()` propagates fetch errors to caller, prevents silent under-hedge
7. **IMP-2 ceiling correctly prevents breakeven from cancelling safety reduction** — C5 FIX verified correct
8. **Gamma limits are hot-reloadable** — operator can raise before scaling without restart
9. **Breakeven binary search precision ($10) adequate at current and 10x capital**
10. **Perp hedge P&L correctly included in breakeven calculation** (BUG-C5 fix verified)

---

## 12. Pass Criteria Checklist

- [x] Formula derivation table with manual checks (Section 9)
- [x] Decimal vs float usage consistency check (Section 7)
- [x] Lot size precision chain verified: 1 lot = 0.001 BTC (Section 1)
- [x] Gamma formula correctness verified (Section 5)
- [x] Breakeven formula signs verified (Section 6.1)
- [x] Scaling analysis at 5x and 10x (Section 8)
- [x] Multiplier chain ordering documented and verified (Section 4.2)
- [x] Architecture Issue Register updated (Section 10)

**Phase 6 Status: PASSED. Two P1 issues require attention (A6-03 documented, A6-04 string-match risk, A6-11 gamma limits before scaling).**

---

## 13. Handoff Notes

**For Phase 7 (State):** The breakeven engine caches by `positions_hash`. Verify that the hash correctly invalidates when any position field changes (including frozen positions added after strike shifts). A stale cache would use incorrect breakeven prices for zone classification.

**For Phase 8 (Execution):** Verify `mmm_monitor.py` uses `is_position_cap_hit` (3rd return value from `calculate_lots_to_sell()`) rather than string-matching "Position cap reached" for M2 recycling trigger — Finding A6-04.

**For Phase 11 (Scaling):** The gamma dollar-gamma formula's default limits are the highest-priority scaling gate. At 500 lots, the portfolio would hit `gamma_hard_limit=5000` at ATM. These limits must be documented as lot-calibrated and raised proportionally before capital increase.
