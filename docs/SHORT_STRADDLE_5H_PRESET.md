# SHORT_STRADDLE_5H — Preset Design Document

> **Purpose:** Production-ready MMM preset for a **pure ATM short straddle** on BTC Delta Exchange India. **Dynamic** — auto-computes all time-proportional parameters from actual hours-to-expiry at session start (Delta Exchange daily expiry: 5:30 PM IST).
>
> **Date:** March 19, 2026 · **Rev 4.1** (final)

---

## 1. Research Summary

### Codebase Findings

- **~120 configurable parameters** in `mmm_state.py` `DEFAULT_PARAMS`
- Three existing DTE presets in `mmm_dte_presets.py`: `PRESET_0DTE`, `PRESET_SHORT_WINDOW`, `PRESET_5DTE`
- `apply_preset()` (L148-171) merges a **static dict**. Dynamic preset needs a **function-based** approach.
- `mmm_state.py` L755-764 already auto-computes `total_dte_hours` from expiry at session creation
- `mmm_initializer.py` L42-46: Delta Exchange expiry = 5:30 PM IST (12:00 UTC)
- `dte_category='0DTE'` safe for sessions ≤ 36h (`mmm_safety.py` L73, `mmm_monitor.py` L720/L741)

### Online Research Findings

- Theta decay follows convex hockey-stick curve; final 2-3h = 60-70% extrinsic evaporation
- ATM = highest theta; conservative sizing essential (2-5% capital)
- Exit 5-10 min before expiry to avoid pin risk

---

## 2. Dynamic Scaling Design

### Architecture

The existing `apply_preset()` returns a static dict. The dynamic short straddle preset replaces this with a **factory function**:

```python
def build_short_straddle_preset(hours_to_expiry: float) -> Dict:
    """Compute time-scaled parameters for short straddle preset."""
```

**Integration point:** `mmm_state.py` L744-753 would call this function instead of looking up a static dict when `dte_category == 'SHORT_STRADDLE'`. The `hours_to_expiry` is computed from expiry date (already available at L756-764).

### Supported Range

| Duration | Classification | Notes |
|:--|:--|:--|
| < 2h | **Reject** | Too little theta; gamma risk dominates |
| 2–6h | **Sprint** | Core sweet spot — max theta acceleration |
| 6–12h | **Extended** | Works but wider regime tiers needed |
| > 12h | **Reject** | Use `PRESET_SHORT_WINDOW` or `PRESET_5DTE` instead |

### Parameter Classification

Every parameter falls into one of 3 categories:

#### 🔒 Fixed Parameters (same for all durations)

These are strategy-intrinsic — they don't depend on session length.

```python
# ── Always fixed ──
'dte_category': '0DTE',
'initial_lots': 1,
'max_lots_per_side': 5,
'max_total_exposure': 10,
'adjustment_interval': 120,
'adaptive_interval_enabled': True,
'min_trigger_move': 8.0,
'premium_buffer_pct': 0.08,
'shift_threshold': 30,
'shift_target_premium': 100,
'close_at_threshold': 5,
'stop_adjustment_mins': 30,
'auto_close_mins': 10,
'max_loss_amount': 3.0,
'trailing_stop_pct': 0.25,
'cooldown_on_reversal': True,
'reversal_cooldown_seconds': 120,
'whipsaw_spot_move_pct': 0.4,
'whipsaw_caution_score': 2,
'whipsaw_restrict_score': 3,
'whipsaw_cooldown_score': 4,
'asymmetry_7to1_hard_block': True,
'asymmetry_5to1_lot_reduction': 0.5,
'atm_shield_enabled': True,
'atm_shield_proximity_pct': 0.3,
'atm_shield_target_otm_pct': 0.8,
'atm_shield_cooldown_mins': 10,
'atm_shield_partial_pct': 1.0,
'breakeven_control_enabled': True,
'breakeven_warning_pct': 1.5,
'breakeven_danger_pct': 0.8,
'breakeven_critical_pct': 0.3,
'breakeven_aggression_max': 2.5,
'perp_hedge_enabled': True,
'perp_hedge_mode': 'full',
'perp_hedge_delta_threshold': 0.015,
'perp_hedge_max_lots': 10,
'perp_hedge_cooldown_sec': 20,
'harvest_enabled': True,
'harvest_profit_pct': 30.0,
'harvest_max_per_beat': 3,
'harvest_pressure_threshold': 0.3,
'recycle_enabled': False,
'proactive_shift_enabled': False,
'scale_enabled': False,
'adaptive_mode': 'preset',
'adaptive_preset': 'straddle',
'wind_down_enabled': True,
'wind_down_close_threshold': 30.0,
'wind_down_floor_action': 'close_all',
'wind_down_on_atm': False,
'regime_enabled': True,
```

#### 📐 Scaled Parameters (proportional to session hours)

These use a **base value at 5h** with a scaling formula. `H` = `hours_to_expiry`.

```python
# ── Scaling formulas ──
'total_dte_hours':              H,
'session_window_hours':         H,
'adaptive_max_interval':        clamp(H * 60, min=180, max=600),     # 1 min/h, 3-10 min range
'theta_acceleration_window':    clamp(H * 36, min=60, max=360),      # 60% of session in mins
'wind_down_hours_before_expiry': clamp(H * 0.20, min=0.5, max=2.0), # 20% of session
'max_adjustments':              clamp(round(H * 4), min=10, max=50), # ~4 adjustments/hour
'whipsaw_window_mins':          clamp(round(H * 3), min=10, max=30), # ~3 min/h
'lot_velocity_window_mins':     clamp(round(H * 3), min=10, max=30), # match whipsaw
'lot_velocity_limit':           10,                                  # always 2× max_lots_per_side
'harvest_min_age_mins':         clamp(round(H * 3), min=10, max=30), # ~3 min/h
'atm_shield_max_per_session':   clamp(round(H * 0.4), min=1, max=4),# ~1 per 2.5h
```

#### 📏 Regime Tiers (widen for longer sessions)

Longer sessions = more chance of sustained moves. Tiers widen to avoid false blocks.

```python
# ── Tier formulas ──
'trend_tier1_pct': clamp(H * 0.06, min=0.2, max=0.5),   # 0.30 at 5h, 0.60 at 10h
'trend_tier2_pct': clamp(H * 0.12, min=0.4, max=1.0),   # 0.60 at 5h, 1.00 at 10h
'trend_tier3_pct': clamp(H * 0.20, min=0.7, max=1.5),   # 1.00 at 5h, 1.50 at 10h
'trend_tier4_pct': clamp(H * 0.30, min=1.0, max=2.5),   # 1.50 at 5h, 2.50 at 10h
```

### Example Outputs

| Param | 3h | 5h | 8h | 10h |
|:--|:--|:--|:--|:--|
| `session_window_hours` | 3.0 | 5.0 | 8.0 | 10.0 |
| `theta_acceleration_window` | 108 | 180 | 288 | 360 |
| `wind_down_hours_before_expiry` | 0.6 | 1.0 | 1.6 | 2.0 |
| `max_adjustments` | 12 | 20 | 32 | 40 |
| `whipsaw_window_mins` | 10 | 15 | 24 | 30 |
| `lot_velocity_window_mins` | 10 | 15 | 24 | 30 |
| `harvest_min_age_mins` | 10 | 15 | 24 | 30 |
| `adaptive_max_interval` | 180 | 300 | 480 | 600 |
| `atm_shield_max_per_session` | 1 | 2 | 3 | 4 |
| `trend_tier1_pct` | 0.20 | 0.30 | 0.48 | 0.50 |
| `trend_tier2_pct` | 0.40 | 0.60 | 0.96 | 1.00 |
| `trend_tier3_pct` | 0.70 | 1.00 | 1.50 | 1.50 |
| `trend_tier4_pct` | 1.00 | 1.50 | 2.40 | 2.50 |

---

## 3. Complete Factory Function (Python)

```python
def build_short_straddle_preset(hours_to_expiry: float) -> dict:
    """
    Dynamic short straddle preset — computes time-proportional parameters.

    Delta Exchange BTC options expire daily at 5:30 PM IST.
    Call this at session creation with actual hours remaining.

    Args:
        hours_to_expiry: Hours until expiry (e.g. 5.0, 3.5, 10.0)

    Returns:
        Complete parameter dict for the session

    Raises:
        ValueError: if hours_to_expiry < 2 or > 12
    """
    H = hours_to_expiry

    if H < 2:
        raise ValueError(
            f"Short straddle requires ≥2h to expiry (got {H:.1f}h). "
            f"Below 2h, gamma risk dominates and theta is insufficient."
        )
    if H > 12:
        raise ValueError(
            f"Short straddle preset supports ≤12h (got {H:.1f}h). "
            f"For longer sessions, use PRESET_SHORT_WINDOW or PRESET_5DTE."
        )

    def clamp(val, min_val, max_val):
        return max(min_val, min(max_val, val))

    return {
        # ── Identity / UI ──
        'preset_name': f'Short Straddle – {H:.0f}H Sprint',
        'description': (
            f'ATM short straddle, {H:.0f}h window. '
            f'Dynamic params auto-scaled from time-to-expiry. '
            f'Conservative lot sizing with full perp delta hedge.'
        ),

        # ── DTE / Session ──
        'dte_category': '0DTE',
        'total_dte_hours': H,
        'session_window_hours': H,

        # ── Lot Sizing (fixed) ──
        'initial_lots': 1,
        'max_lots_per_side': 5,
        'max_total_exposure': 10,
        'max_adjustments': clamp(round(H * 4), 10, 50),

        # ── Heartbeat ──
        'adjustment_interval': 120,
        'adaptive_interval_enabled': True,
        'adaptive_max_interval': clamp(round(H * 60), 180, 600),

        # ── Trigger Logic (fixed) ──
        'min_trigger_move': 8.0,
        'premium_buffer_pct': 0.08,
        'shift_threshold': 30,
        'shift_target_premium': 100,
        'close_at_threshold': 5,

        # ── Near-Expiry (fixed absolute thresholds) ──
        'stop_adjustment_mins': 30,
        'auto_close_mins': 10,
        'theta_acceleration_window': clamp(round(H * 36), 60, 360),

        # ── Wind-Down (scaled) ──
        'wind_down_enabled': True,
        'wind_down_hours_before_expiry': round(clamp(H * 0.20, 0.5, 2.0), 1),
        'wind_down_close_threshold': 30.0,
        'wind_down_floor_action': 'close_all',
        'wind_down_on_atm': False,

        # ── P&L Guardrails (fixed) ──
        'max_loss_amount': 3.0,
        'trailing_stop_pct': 0.25,

        # ── Reversal / Whipsaw (scaled window, fixed thresholds) ──
        'cooldown_on_reversal': True,
        'reversal_cooldown_seconds': 120,
        'whipsaw_window_mins': clamp(round(H * 3), 10, 30),
        'whipsaw_spot_move_pct': 0.4,
        'whipsaw_caution_score': 2,
        'whipsaw_restrict_score': 3,
        'whipsaw_cooldown_score': 4,

        # ── Lot Velocity (scaled window) ──
        'lot_velocity_enabled': True,
        'lot_velocity_window_mins': clamp(round(H * 3), 10, 30),
        'lot_velocity_limit': 10,

        # ── Asymmetry (fixed) ──
        'asymmetry_7to1_hard_block': True,
        'asymmetry_5to1_lot_reduction': 0.5,

        # ── Regime Tiers (scaled — widen for longer sessions) ──
        'regime_enabled': True,
        'trend_tier1_pct': round(clamp(H * 0.06, 0.2, 0.5), 2),
        'trend_tier2_pct': round(clamp(H * 0.12, 0.4, 1.0), 2),
        'trend_tier3_pct': round(clamp(H * 0.20, 0.7, 1.5), 2),
        'trend_tier4_pct': round(clamp(H * 0.30, 1.0, 2.5), 2),

        # ── ATM Shield (scaled budget) ──
        'atm_shield_enabled': True,
        'atm_shield_proximity_pct': 0.3,
        'atm_shield_target_otm_pct': 0.8,
        'atm_shield_max_per_session': clamp(round(H * 0.4), 1, 4),
        'atm_shield_cooldown_mins': 10,
        'atm_shield_partial_pct': 1.0,

        # ── Breakeven (fixed) ──
        'breakeven_control_enabled': True,
        'breakeven_warning_pct': 1.5,
        'breakeven_danger_pct': 0.8,
        'breakeven_critical_pct': 0.3,
        'breakeven_aggression_max': 2.5,

        # ── Perp Hedge (fixed) ──
        'perp_hedge_enabled': True,
        'perp_hedge_mode': 'full',
        'perp_hedge_delta_threshold': 0.015,
        'perp_hedge_max_lots': 10,
        'perp_hedge_cooldown_sec': 20,

        # ── Lot Lifecycle (scaled harvest age) ──
        'scale_enabled': False,
        'harvest_enabled': True,
        'harvest_profit_pct': 30.0,
        'harvest_min_age_mins': clamp(round(H * 3), 10, 30),
        'harvest_max_per_beat': 3,
        'harvest_pressure_threshold': 0.3,
        'recycle_enabled': False,
        'proactive_shift_enabled': False,

        # ── Adaptive (fixed) ──
        'adaptive_mode': 'preset',
        'adaptive_preset': 'straddle',
    }
```

---

## 4. Integration Point

### Current flow (`mmm_state.py` L744-764):

```python
dte_category = merged_params.get('dte_category', '')
if dte_category:
    merged_params = apply_preset(merged_params, dte_category)
# Then total_dte_hours is computed from expiry...
```

### Required change:

```python
dte_category = merged_params.get('dte_category', '')
if dte_category == 'SHORT_STRADDLE':
    # Dynamic preset: compute hours_to_expiry FIRST, then build params
    from .mmm_dte_presets import compute_total_dte_hours
    hours = compute_total_dte_hours(merged_params.get('expiry', ''))
    preset_params = build_short_straddle_preset(hours)
    merged_params.update(preset_params)
    merged_params.update(user_params)  # user overrides still win
elif dte_category:
    merged_params = apply_preset(merged_params, dte_category)
```

> [!NOTE]
> User selects `dte_category = 'SHORT_STRADDLE'` in the WebUI. The system reads expiry, computes hours remaining to 5:30 PM IST, and auto-scales all parameters. No hardcoded hour value needed.

---

## 5. Known Limitations

> [!WARNING]
> **Trailing stop micro-peak (cannot fix without code change)**
>
> `check_trailing_stop` (L1035-1060) fires `action: 'stop_adjustments'` whenever `current_pnl < peak_pnl × 0.25` and `peak_pnl > 0`. Early-session $0.01 peak can cause false blocks. Session self-recovers once real P&L accumulates — existing positions continue decaying. Proper fix: minimum peak threshold in code.

> [!IMPORTANT]
> **`max_loss_amount: 3.0` does not scale with H**
>
> At H=2, ATM premium ≈ ~$60/BTC → 1 lot pair collects ~$0.12. The $3.00 stop is 25× initial premium (very wide). At H=12, premium is higher and the ratio is tighter. This is intentional — premium requires live market data at session start, so a fixed hard stop is pragmatic. For H < 3 sessions, operators should manually review this value.

> [!NOTE]
> **Asymmetry 7:1 uses `block_heavy_side_sells`, not `stop_adjustments`**
>
> `should_block_adjustment()` does NOT include `block_heavy_side_sells` in its blocking set. The monitor handles it via event details at L1679-1692, allowing the light side to still sell for rebalancing. This is actually better for a straddle — one side can recover without fully pausing.

> [!NOTE]
> **Margin warning at full capacity (cosmetic only)**
>
> At `max_lots_per_side=5`, margin warns when `total_lots > 7.5`. Full straddle (5+5=10) fires every heartbeat. Non-blocking.

---

## 6. Revision History

| Rev | Changes |
|:--|:--|
| **4.1** | Added `preset_name`/`description` to factory output. Documented `max_loss_amount` non-scaling and asymmetry nuance. |
| **4** | Dynamic scaling: factory function replaces static dict. All time-proportional params auto-computed from `hours_to_expiry`. Supported range: 2–12h. |
| **3** | `dte_category` → `'0DTE'`, `max_adjustments` 15→20, `scale_enabled: False` |
| **2** | `lot_velocity_limit` 5→10, `whipsaw_cooldown_score` 3→4, `trailing_stop_pct` 0.35→0.25, wind-down clarified |
| **1** | Initial design — 67 params, copy-paste static dict |
