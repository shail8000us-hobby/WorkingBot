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
