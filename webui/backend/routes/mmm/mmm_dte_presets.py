"""
MMM DTE Presets — Multi-Expiry Parameter Profiles

Provides pre-configured parameter sets for different DTE categories.
Operators select a preset when creating a session, and all parameters auto-fill.

Phase 0: Aggregate PnL safety + liquidity gate
Phase 1: DTE presets (0DTE + 5DTE)

Created: March 12, 2026
"""

import logging
import math
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timezone

log = logging.getLogger('mmm_dte_presets')


# =============================================================================
# DTE Preset Profiles
# =============================================================================

PRESET_0DTE = {
    'dte_category': '0DTE',
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
    'reversal_cooldown_seconds': 0,
    'lot_velocity_limit': 30,
    'lot_velocity_window_mins': 30,
}

PRESET_SHORT_WINDOW = {
    'dte_category': 'SHORT_WINDOW',
    'session_window_hours': 5.0,
    'adjustment_interval': 120,
    'adaptive_max_interval': 300,
    'min_trigger_move': 15.0,
    'shift_threshold': 25,
    'shift_target_premium': 150,
    'close_at_threshold': 5,
    'max_loss_amount': 5000,
    'max_lots_per_side': 30,
    'max_total_exposure': 50,
    'max_adjustments': 12,
    'trailing_stop_pct': 0.4,
    'wind_down_enabled': True,
    'wind_down_hours_before_expiry': 1.0,
    'wind_down_close_threshold': 40.0,
    'wind_down_floor_action': 'close_all',
    'stop_adjustment_mins': 30,
    'auto_close_mins': 10,
    'whipsaw_cooldown_score': 3,
    'reversal_cooldown_seconds': 0,
    'lot_velocity_limit': 8,
    'lot_velocity_window_mins': 20,
    'harvest_profit_pct': 30.0,
    'harvest_min_age_mins': 20,
    'harvest_max_per_beat': 5,
    'harvest_pressure_threshold': 0.3,
    'recycle_enabled': False,
    'proactive_shift_enabled': False,
    'atm_shield_enabled': True,
    'atm_shield_proximity_pct': 0.8,
    'atm_shield_max_per_session': 2,
    'atm_shield_cooldown_mins': 15,
    'perp_hedge_enabled': True,
    'perp_hedge_delta_threshold': 0.03,
    'perp_hedge_max_lots': 20,
    'breakeven_warning_pct': 2.5,
    'breakeven_danger_pct': 1.5,
    'breakeven_critical_pct': 0.8,
    'breakeven_aggression_max': 2.5,
}

PRESET_5DTE = {
    'dte_category': '5DTE',
    'adjustment_interval': 900,         # 15 min
    'min_trigger_move': 20.0,           # Less sensitive
    'shift_threshold': 35,              # Lower shift point
    'shift_target_premium': 150,        # Higher premium available
    'close_at_threshold': 3,            # More patience
    'max_loss_amount': 15000,           # Scaled to premium
    'max_lots_per_side': 50,            # Conservative (corrected from 75)
    'whipsaw_cooldown_score': 5,        # More tolerance
    'wind_down_hours_before_expiry': 12, # Last half-day
    'stop_adjustment_mins': 30,         # Wider window
    'auto_close_mins': 10,             # Wider close window
    'reversal_cooldown_seconds': 1800,  # 30 min cooldown
    'lot_velocity_limit': 8,            # Slower accumulation (corrected from 15)
    'lot_velocity_window_mins': 60,     # 1-hour window
    'trailing_stop_pct': 0.6,           # Protect 60% of peak
    # Regime: slightly wider thresholds
    'trend_tier1_pct': 1.0,
    'trend_tier2_pct': 2.0,
    'trend_tier3_pct': 3.0,
    'trend_tier4_pct': 5.0,
    # Breakeven DTE-aware controls
    'breakeven_dte_threshold_mult': 1.5,     # widen thresholds 50% at session start
    'breakeven_dte_aggression_damp': 0.1,    # 10% lot boost reduction in WARNING/DANGER
    'breakeven_dte_vol_regime_damp': 0.2,    # auto-damp 20% on HIGH vol (10% on ELEVATED)
    'breakeven_dte_pnl_clamp_pct': 1.5,      # disable widening if loss > 1.5× total premium collected
    'breakeven_tv_credit_factor': 0.0,       # reserved
    'breakeven_high_risk_mode': False,        # operator-triggered max aggression (0DTE-equivalent)
    'breakeven_critical_lot_ceiling': 4.0,   # CRITICAL ceiling (vs combined cap for lower zones)
}

# Registry of all presets
DTE_PRESETS = {
    '0DTE': PRESET_0DTE,
    'SHORT_WINDOW': PRESET_SHORT_WINDOW,
    '5DTE': PRESET_5DTE,
}

# Dynamic preset identifier — not in DTE_PRESETS because it's a factory function
SHORT_STRADDLE_CATEGORY = 'SHORT_STRADDLE'


def build_short_straddle_preset(hours_to_expiry: float) -> dict:
    """
    Dynamic short straddle preset — computes time-proportional parameters.

    Delta Exchange BTC options expire daily at 5:30 PM IST (12:00 UTC).
    Call this at session creation with actual hours remaining.

    Fixed params (37): strategy-intrinsic, same for all durations.
    Scaled params (11): proportional to H with clamp(min, max).
    Regime tiers (4): widen for longer sessions.

    See docs/SHORT_STRADDLE_5H_PRESET.md for full design rationale.

    Args:
        hours_to_expiry: Hours until expiry (2.0 to 12.0)

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

        # ── Wind-Down (scaled — consumed by mmm_wind_down.py) ──
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


def get_preset(dte_category: str) -> Optional[Dict]:
    """Get a preset by DTE category name. Returns None if not found."""
    return DTE_PRESETS.get(dte_category)


def list_presets() -> List[Dict]:
    """List all available DTE presets with metadata."""
    result = []
    for name, preset in DTE_PRESETS.items():
        entry = {
            'name': name,
            'adjustment_interval': preset.get('adjustment_interval'),
            'min_trigger_move': preset.get('min_trigger_move'),
            'max_loss_amount': preset.get('max_loss_amount'),
            'max_lots_per_side': preset.get('max_lots_per_side'),
        }
        if 'session_window_hours' in preset:
            entry['session_window_hours'] = preset['session_window_hours']
        result.append(entry)

    # Include dynamic preset with example values (5h)
    result.append({
        'name': SHORT_STRADDLE_CATEGORY,
        'dynamic': True,
        'description': 'ATM short straddle — params auto-scaled from time-to-expiry (2–12h)',
        'adjustment_interval': 120,
        'min_trigger_move': 8.0,
        'max_loss_amount': 3.0,
        'max_lots_per_side': 5,
    })

    return result


def apply_preset(params: Dict, dte_category: str) -> Dict:
    """
    Apply a DTE preset to session params.
    Preset values are applied as defaults — explicit user params override.

    For SHORT_STRADDLE: dynamically builds params from hours_to_expiry.
    For static presets: merges the static dict.

    Args:
        params: User-provided params (may be partial)
        dte_category: e.g. '0DTE', '5DTE', 'SHORT_STRADDLE'

    Returns:
        Merged params with preset values as base layer
    """
    if dte_category == SHORT_STRADDLE_CATEGORY:
        # Dynamic preset: compute hours from expiry, then build scaled params
        expiry_str = params.get('expiry', '')
        if not expiry_str:
            log.warning("SHORT_STRADDLE preset requires 'expiry' param")
            return params
        hours = compute_total_dte_hours(
            expiry_str,
            params.get('expiry_hour_utc', 12),
            params.get('expiry_minute_utc', 0),
        )
        try:
            preset = build_short_straddle_preset(hours)
        except ValueError as e:
            log.error(f"SHORT_STRADDLE preset rejected: {e}")
            return params

        merged = {}
        merged.update(preset)
        merged.update(params)
        # Restore computed dte_category (user sent 'SHORT_STRADDLE' but
        # routing needs '0DTE' from the preset)
        merged['dte_category'] = preset['dte_category']
        # Preserve the original preset selection for UI display
        merged['_preset_source'] = SHORT_STRADDLE_CATEGORY
        return merged

    preset = get_preset(dte_category)
    if not preset:
        log.warning(f"Unknown DTE preset: {dte_category}")
        return params

    # Preset acts as middle layer: DEFAULT_PARAMS < preset < user_params
    merged = {}
    merged.update(preset)
    merged.update(params)
    # Always store the category
    merged['dte_category'] = dte_category
    return merged


def compute_total_dte_hours(expiry_str: str, expiry_hour_utc: int = 12,
                            expiry_minute_utc: int = 0) -> float:
    """
    Compute total hours from now until expiry.

    Args:
        expiry_str: Expiry in DDMMYYYY format
        expiry_hour_utc: Hour of expiry in UTC (default 12 = 5:30 PM IST)
        expiry_minute_utc: Minute of expiry in UTC

    Returns:
        Total hours until expiry (can be negative if expired)
    """
    try:
        day = int(expiry_str[0:2])
        month = int(expiry_str[2:4])
        year = int(expiry_str[4:8])
        expiry_dt = datetime(year, month, day, expiry_hour_utc, expiry_minute_utc,
                             tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = expiry_dt - now
        return delta.total_seconds() / 3600.0
    except (ValueError, IndexError) as e:
        log.error(f"Failed to parse expiry '{expiry_str}': {e}")
        return 0.0


def infer_dte_category(total_dte_hours: float) -> str:
    """
    Infer a DTE category from total hours to expiry.

    Returns: '0DTE' or '5DTE' (only supported categories for now)
    """
    dte_days = total_dte_hours / 24.0
    if dte_days <= 1.5:
        return '0DTE'
    else:
        return '5DTE'


# =============================================================================
# Phase 0: Aggregate PnL Safety
# =============================================================================

# Global max loss across all active sessions (USD)
DEFAULT_GLOBAL_MAX_LOSS = 50000.0


def check_aggregate_pnl(
    active_sessions: List[Dict],
    global_max_loss: float = DEFAULT_GLOBAL_MAX_LOSS,
) -> Dict[str, Any]:
    """
    Check combined PnL across all active sessions.

    This is a SAFETY function called before allowing new position additions.
    If combined loss exceeds global_max_loss, ALL sessions should pause.

    Args:
        active_sessions: List of session dicts with realized_pnl and unrealized_pnl
        global_max_loss: Maximum allowed combined loss (positive number)

    Returns:
        {
            safe: bool,
            combined_pnl: float,
            combined_realized: float,
            combined_unrealized: float,
            session_count: int,
            pnl_pct_of_limit: float,  # 0-100+
            level: str,               # 'ok' | 'warning' | 'critical' | 'breach'
            message: str,
        }
    """
    combined_realized = 0.0
    combined_unrealized = 0.0

    for session in active_sessions:
        combined_realized += session.get('realized_pnl', 0.0)
        combined_unrealized += session.get('unrealized_pnl', 0.0)
        # Include manual reduction PnL
        combined_realized += session.get('manual_reduction_pnl', 0.0)

    combined_pnl = combined_realized + combined_unrealized
    pnl_pct = abs(min(combined_pnl, 0)) / global_max_loss * 100 if global_max_loss > 0 else 0

    if combined_pnl <= -global_max_loss:
        level = 'breach'
        safe = False
        message = (f"AGGREGATE MAX LOSS BREACHED: ${combined_pnl:.2f} "
                   f"across {len(active_sessions)} sessions "
                   f"(limit: ${global_max_loss:.2f})")
    elif pnl_pct >= 80:
        level = 'critical'
        safe = True  # Allow existing positions but warn strongly
        message = (f"Aggregate PnL critical: ${combined_pnl:.2f} "
                   f"({pnl_pct:.0f}% of ${global_max_loss:.2f} limit)")
    elif pnl_pct >= 50:
        level = 'warning'
        safe = True
        message = (f"Aggregate PnL warning: ${combined_pnl:.2f} "
                   f"({pnl_pct:.0f}% of ${global_max_loss:.2f} limit)")
    else:
        level = 'ok'
        safe = True
        message = f"Aggregate PnL OK: ${combined_pnl:.2f} across {len(active_sessions)} sessions"

    return {
        'safe': safe,
        'combined_pnl': round(combined_pnl, 2),
        'combined_realized': round(combined_realized, 2),
        'combined_unrealized': round(combined_unrealized, 2),
        'session_count': len(active_sessions),
        'pnl_pct_of_limit': round(pnl_pct, 1),
        'level': level,
        'message': message,
    }


# =============================================================================
# Phase 0: Liquidity Gate
# =============================================================================

MIN_LIQUID_STRIKES = 2  # Minimum strikes per side (CE/PE) with liquidity


def check_chain_liquidity(
    chain: List[Dict],
    min_liquidity_lots: int = 5,
    min_strikes_per_side: int = MIN_LIQUID_STRIKES,
) -> Dict[str, Any]:
    """
    Check if an options chain has sufficient liquidity to start a session.

    Called at session creation time to refuse starting on illiquid expiries.

    Accepts the nested chain format from MMMInitializer.get_full_chain():
        [{strike, call: {bid, bid_size, ...}, put: {bid, bid_size, ...}}, ...]

    Args:
        chain: List of strike entries from get_full_chain
        min_liquidity_lots: Minimum bid_size required per strike
        min_strikes_per_side: Minimum liquid strikes needed per side

    Returns:
        {
            liquid: bool,
            ce_liquid_strikes: int,
            pe_liquid_strikes: int,
            min_required: int,
            message: str,
        }
    """
    ce_liquid = 0
    pe_liquid = 0

    for entry in chain:
        # Nested format: {strike, call: {...}, put: {...}}
        call = entry.get('call') or {}
        put = entry.get('put') or {}

        call_bid = call.get('bid', 0) or 0
        call_bid_size = call.get('bid_size', 0) or 0
        if call_bid > 0 and call_bid_size >= min_liquidity_lots:
            ce_liquid += 1

        put_bid = put.get('bid', 0) or 0
        put_bid_size = put.get('bid_size', 0) or 0
        if put_bid > 0 and put_bid_size >= min_liquidity_lots:
            pe_liquid += 1

    is_liquid = ce_liquid >= min_strikes_per_side and pe_liquid >= min_strikes_per_side

    if is_liquid:
        message = (f"Liquidity OK: {ce_liquid} CE strikes, {pe_liquid} PE strikes "
                   f"(min {min_strikes_per_side} per side)")
    else:
        message = (f"Insufficient liquidity: {ce_liquid} CE strikes, {pe_liquid} PE strikes "
                   f"(need {min_strikes_per_side} per side with bid_size >= {min_liquidity_lots})")

    return {
        'liquid': is_liquid,
        'ce_liquid_strikes': ce_liquid,
        'pe_liquid_strikes': pe_liquid,
        'min_required': min_strikes_per_side,
        'message': message,
    }
