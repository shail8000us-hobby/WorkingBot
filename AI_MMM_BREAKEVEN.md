# AI_MMM_BREAKEVEN — Breakeven Engine Reference

> Companion to `AI_MMM_CONTEXT.md`. Read this for breakeven-specific work.
> All code lives in `webui/backend/routes/mmm/mmm_breakeven_engine.py`.

---

## What the Breakeven Engine Does

Computes two BTC spot prices (lower/upper) where total portfolio P&L = 0 using an **intrinsic-only model** (no live premium fetches, no time value). Classifies current spot into a risk zone and returns a lot-aggression multiplier used by `mmm_engine.py`.

**Design principle:** Intrinsic-only is deliberately conservative — it ignores remaining time value. This is correct and intentional. At 5DTE, this makes the model pessimistic (real market breakeven is further away than the model shows). The DTE-aware upgrade addresses this via threshold scaling, not model changes.

---

## Architecture

```
compute_breakeven(session, spot_price)
├── _collect_open_positions()         # CE + PE + optional perp hedge
├── _hash_positions()                 # cache key: strikes + lots + premium + realized + perp
├── cache hit?
│   ├── YES → reuse lower/upper prices (~0.01ms)
│   └── NO  → _find_breakeven() bisection scan (~1ms), update cache
└── _build_result()                   # ALWAYS fresh, even on cache hit
    ├── _compute_dte_scale()          # √T threshold scaling
    ├── vol_regime_damp → aggression_damp
    ├── high_risk_mode override → dte_scale=1.0, aggression_damp=0
    ├── pnl_clamp guard
    ├── _classify_zone()              # SAFE / WARNING / DANGER / CRITICAL
    └── _compute_multiplier()         # 1.0→max_mult ramp, CRITICAL fully exempt from damp
```

**Cache stores:** `{lower_breakeven, upper_breakeven, positions_hash, band_width_pct}` only.
**Zone/multiplier/dte_scale are NEVER cached** — always recomputed from fresh session state.

---

## DTE-Aware Threshold Scaling

### Formula
```python
t_ratio = hours_remaining / total_dte_hours  # 1.0 at start, 0.0 at expiry
dte_scale = 1.0 + (breakeven_dte_threshold_mult - 1.0) * sqrt(t_ratio)
```

### Vol Regime Damping (inside `_compute_dte_scale`)
```python
if vol_regime == 'HIGH':     damp = breakeven_dte_vol_regime_damp       # full damp
elif vol_regime == 'ELEVATED': damp = breakeven_dte_vol_regime_damp * 0.5  # half damp
# dte_scale = 1.0 + (dte_scale - 1.0) * (1.0 - damp)
```

### High-Risk Mode (in `_build_result`)
When `breakeven_high_risk_mode=True`:
- Forces `dte_scale = 1.0` (0DTE-equivalent threshold sensitivity)
- Forces `aggression_damp = 0` (max lot aggression)
- Auto-expires after 4h via `session['_high_risk_mode_expires_at']`

### PnL Clamp (in `_build_result`)
```python
if (dte_scale > 1.0
        and total_lots >= 5                            # lot-count floor
        and pnl_at_spot < 0                           # only when losing
        and abs(pnl_at_spot) / total_premium_collected > clamp_pct):
    dte_scale = 1.0
```
Uses `session['total_premium_collected']` (full session accumulated), NOT current positions' premium.

### Example: 5DTE session, mult=1.5
| Hours left | t_ratio | dte_scale | Warning | Danger | Critical |
|-----------|---------|-----------|---------|--------|----------|
| 120h (start) | 1.00 | 1.50 | 3.0% | 1.5% | 0.75% |
| 72h (3DTE)   | 0.60 | 1.39 | 2.8% | 1.4% | 0.69% |
| 24h (1DTE)   | 0.20 | 1.22 | 2.5% | 1.2% | 0.61% |
| 0h (expiry)  | 0.00 | 1.00 | 2.0% | 1.0% | 0.50% |

---

## Zone Classification

| Zone | Distance from breakeven | Multiplier range |
|------|------------------------|-----------------|
| SAFE | > warning_pct (×dte_scale) | 1.0× |
| WARNING | danger_pct – warning_pct | 1.0 – 1.3× (damped) |
| DANGER | critical_pct – danger_pct | 1.3 – 2.0× (damped) |
| CRITICAL | < critical_pct | 2.0 – max_mult× (**NEVER damped**) |

- `dte_aggression_damp` reduces WARNING/DANGER amplitude. CRITICAL always gets full aggression.
- `_breakeven_zone` is stored in `session` each heartbeat for use by `mmm_engine.py`.

---

## Combined Ceiling Override

In `mmm_engine.py` `calculate_lots_to_sell()`:
```python
if session.get('_breakeven_zone') == 'CRITICAL':
    max_combined = params.get('breakeven_critical_lot_ceiling', 4.0)  # higher ceiling
else:
    max_combined = params.get('max_combined_lot_multiplier', 3.0)     # normal ceiling
```
Allows CRITICAL zone to bypass the global combined multiplier cap.

---

## Config Parameters (8 new, all hot-reloadable)

| Param | Default | PRESET_5DTE | Range | Purpose |
|-------|---------|-------------|-------|---------|
| `breakeven_dte_threshold_mult` | 1.0 | 1.5 | 1.0–5.0 | Widening factor at session start |
| `breakeven_dte_aggression_damp` | 0.0 | 0.1 | 0.0–0.4 | Lot boost reduction in WARNING/DANGER |
| `breakeven_dte_vol_regime_damp` | 0.2 | 0.2 | 0.0–1.0 | dte_scale reduction at HIGH/ELEVATED vol |
| `breakeven_dte_pnl_clamp_pct` | 1.5 | 1.5 | 0.5–3.0 | Loss ratio to disable dte_scale (needs ≥5 lots) |
| `breakeven_tv_credit_factor` | 0.0 | 0.0 | 0.0–0.5 | Reserved (Tier 3, not active) |
| `breakeven_high_risk_mode` | False | False | bool | FOMC/CPI override: dte_scale=1.0, damp=0 |
| `breakeven_critical_lot_ceiling` | 4.0 | 4.0 | 2.0–6.0 | Combined mult ceiling in CRITICAL zone |

Base breakeven params (existed before DTE upgrade):
`breakeven_control_enabled`, `breakeven_warning_pct` (2.0%), `breakeven_danger_pct` (1.0%), `breakeven_critical_pct` (0.5%), `breakeven_aggression_max` (3.0), `breakeven_scan_range_pct`, `breakeven_narrow_band_threshold`

---

## Result Dict Fields

```python
{
  'enabled': bool,
  'lower_breakeven': float | None,
  'upper_breakeven': float | None,
  'spot_price': float,
  'distance_lower_pct': float | None,
  'distance_upper_pct': float | None,
  'nearest_distance_pct': float | None,
  'nearest_side': 'lower' | 'upper' | 'none',
  'zone': 'SAFE' | 'WARNING' | 'DANGER' | 'CRITICAL',
  'multiplier': float,               # 1.0 → breakeven_aggression_max
  'pnl_at_spot': float,              # intrinsic-only P&L at current spot
  'dte_scale': float,                # active scale factor (after all overrides)
  'effective_warning_pct': float,    # breakeven_warning_pct × dte_scale
  'effective_danger_pct': float,
  'effective_critical_pct': float,
  'band_width_pct': float | None,
  'band_contracting': bool,
  'is_narrow_band': bool,
  'from_cache': bool,
  'positions_included': int,
  'perp_included': bool,
  'computed_at': str,                # UTC ISO
}
```

---

## Session Fields Written by Engine

| Field | Set by | Purpose |
|-------|--------|---------|
| `_breakeven_zone` | `mmm_monitor.py` (from result) | Used by mmm_engine combined ceiling |
| `_breakeven_result` | `mmm_monitor.py` | Full result dict, exposed in heartbeat |
| `_high_risk_mode_expires_at` | `mmm_api.py` params update endpoint | Auto-expiry for high_risk_mode (4h TTL) |

`_high_risk_mode_expires_at` is set when `breakeven_high_risk_mode` is toggled True via `/session/<id>/params` PATCH. Cleared when toggled False. UTC-aware ISO string.

---

## Key Bugs Fixed (March 2026, post-implementation audit)

| Bug | Symptom | Fix |
|-----|---------|-----|
| pnl_clamp wrong denominator | Used current positions' premium sum instead of `total_premium_collected`. After harvesting, denominator shrank → clamp fired prematurely | Changed to `session.get('total_premium_collected')` |
| pnl_clamp fired on profitable positions | `abs(pnl_at_spot)` without `pnl < 0` guard | Added `pnl_at_spot < 0` check |
| high_risk_mode didn't tighten thresholds | Only zeroed aggression_damp; dte_scale stayed wide. FOMC override was half-broken | Added `dte_scale = 1.0` when high_risk_active |
| vol_regime_damp only affected aggression, not dte_scale | Elevated vol didn't tighten the threshold band at all | Added vol_regime damping inside `_compute_dte_scale()` |
| `_high_risk_mode_expires_at` never written | Engine read it but API never set it → mode stayed on forever, no auto-expiry | Added setter in `update_session_params` (mmm_api.py) |

---

## Files Modified for DTE Upgrade

| File | Changes |
|------|---------|
| `mmm_breakeven_engine.py` | `_compute_dte_scale()`, updated `_classify_zone()` + `_compute_multiplier()` signatures, DTE block in `_build_result()`, `_empty_result()` |
| `mmm_config.py` | 7 new PARAM_RULES entries + descriptions |
| `mmm_state.py` | 7 defaults in DEFAULT_PARAMS + HOT_RELOAD_PARAMS |
| `mmm_dte_presets.py` | PRESET_5DTE: mult=1.5, damp=0.1, vol_regime_damp=0.2, pnl_clamp=1.5 |
| `mmm_engine.py` | CRITICAL zone ceiling override using `breakeven_critical_lot_ceiling` |
| `MMMBreakevenPanel.js` | DTE scale chip, effective thresholds row |
| `MMMSettingsDialog.js` | 3 DTE sections with 7 params |
| `mmm_api.py` | `_high_risk_mode_expires_at` setter in `update_session_params` |

**Files NOT modified:** `mmm_monitor.py`, `mmm_regime.py`, `mmm_gamma_detector.py`, `mmm_harvester.py`, `mmm_recycler.py`, `mmm_close_at_5.py`

---

## Testing Checklist

```bash
# 1. Sealed tests must not drop below 436
python3 -m pytest webui/ bot/ -m sealed -v

# 2. Backend health
curl http://localhost:5555/api/health

# 3. Verify dte_scale in live heartbeat
curl http://localhost:5555/api/mmm/sessions | python3 -c "
import json,sys; s=json.load(sys.stdin)
for x in s: print(x.get('session_id','?'), x.get('_breakeven_result',{}).get('dte_scale','N/A'))
"
```

Key manual verifications:
- 5DTE session at start: `dte_scale ≈ 1.5` (mult=1.5, t_ratio=1.0)
- 5DTE session at expiry: `dte_scale = 1.0`
- HIGH vol: `dte_scale` reduced ~20% vs NORMAL
- `breakeven_high_risk_mode=True`: `dte_scale = 1.0` and `multiplier` at max in zones
- pnl_clamp: only fires when `total_lots ≥ 5` AND `pnl < 0` AND `loss/total_premium > 1.5`

---

*Created: March 16, 2026. Covers DTE-aware upgrade (Tier 1+2) + post-implementation bug fixes.*
