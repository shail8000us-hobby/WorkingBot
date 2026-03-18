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
    return result


def apply_preset(params: Dict, dte_category: str) -> Dict:
    """
    Apply a DTE preset to session params.
    Preset values are applied as defaults — explicit user params override.

    Args:
        params: User-provided params (may be partial)
        dte_category: e.g. '0DTE', '5DTE'

    Returns:
        Merged params with preset values as base layer
    """
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
