"""
MMM Configuration — Money Mind & Method

Default parameters, hot-reload support, and parameter validation.
Maps to MONEY_POWER_CALCULATION_LOGIC.md Section 19: User Parameters.

Created: February 15, 2026
"""

import logging
from typing import Dict, Any, Tuple, Set

log = logging.getLogger('mmm_config')


# Parameter type and range validation rules
PARAM_RULES = {
    'desired_ce_premium':      {'type': float, 'min': 1,    'max': 10000, 'hot': False},
    'desired_pe_premium':      {'type': float, 'min': 1,    'max': 10000, 'hot': False},
    'initial_lots':            {'type': int,   'min': 1,    'max': 1000,  'hot': False},
    'expiry':                  {'type': str,   'min': None, 'max': None,  'hot': False},
    'adjustment_interval':     {'type': int,   'min': 10,   'max': 3600,  'hot': True},
    'min_trigger_move':        {'type': float, 'min': 0.1,  'max': 100,   'hot': True},
    'shift_threshold':         {'type': float, 'min': 1,    'max': 5000,  'hot': True},
    'shift_target_premium':    {'type': float, 'min': 10,   'max': 5000,  'hot': True},
    'close_at_threshold':      {'type': float, 'min': 0,    'max': 100,   'hot': True},
    'premium_buffer_pct':      {'type': float, 'min': 0,    'max': 0.5,   'hot': True},
    'max_lots_per_side':       {'type': int,   'min': 1,    'max': 10000, 'hot': True},
    'max_adjustments':         {'type': int,   'min': 1,    'max': 1000,  'hot': True},
    'max_loss_amount':         {'type': float, 'min': 0,    'max': 1e9,   'hot': True},
    'stop_adjustment_mins':    {'type': int,   'min': 0,    'max': 1440,  'hot': True},
    'auto_close_mins':         {'type': int,   'min': 0,    'max': 1440,  'hot': True},
    'cooldown_on_reversal':    {'type': bool,  'min': None, 'max': None,  'hot': True},
    'whipsaw_limit':           {'type': int,   'min': 2,    'max': 100,   'hot': True},
    'trailing_stop_pct':       {'type': float, 'min': 0,    'max': 1.0,   'hot': True},
    'theta_acceleration_window': {'type': int, 'min': 0,    'max': 1440,  'hot': True},
    'close_at_atm':              {'type': bool,  'min': None, 'max': None,  'hot': True},
    'itm_guard_enabled':         {'type': bool,  'min': None, 'max': None,  'hot': True},
    'shift_threshold_pct':       {'type': float, 'min': 0,    'max': 1.0,   'hot': True},
    # Adaptive interval
    'adaptive_interval_enabled': {'type': bool,  'min': None, 'max': None,  'hot': True},
    # Wind-down mode
    'wind_down_enabled':         {'type': bool,  'min': None, 'max': None,  'hot': True},
    'wind_down_hours_before_expiry': {'type': float, 'min': 0, 'max': 72,   'hot': True},
    'wind_down_buyback_pct':     {'type': float, 'min': 0.05, 'max': 1.0,  'hot': True},
    'wind_down_close_threshold': {'type': float, 'min': 1,    'max': 500,  'hot': True},
    'wind_down_min_lots_to_keep': {'type': int,  'min': 0,    'max': 10000, 'hot': True},
    'wind_down_floor_action':    {'type': str,   'min': None, 'max': None,  'hot': True},
    'wind_down_on_atm':          {'type': bool,  'min': None, 'max': None,  'hot': True},
    # Margin Guardian
    'margin_monitor_enabled':    {'type': bool,  'min': None, 'max': None,  'hot': True},
    'margin_green_pct':          {'type': float, 'min': 10,   'max': 100,   'hot': True},
    'margin_yellow_pct':         {'type': float, 'min': 20,   'max': 100,   'hot': True},
    'margin_orange_pct':         {'type': float, 'min': 30,   'max': 100,   'hot': True},
    'margin_red_pct':            {'type': float, 'min': 40,   'max': 100,   'hot': True},
    'margin_critical_pct':       {'type': float, 'min': 50,   'max': 100,   'hot': True},
    'margin_target_pct':         {'type': float, 'min': 10,   'max': 100,   'hot': True},
    # Regime Controls — Volatility Regime Filter
    'regime_enabled':             {'type': bool,  'min': None, 'max': None,  'hot': True},
    'vol_regime_enabled':        {'type': bool,  'min': None, 'max': None,  'hot': True},
    'vol_iv_spike_pct':          {'type': int,   'min': 5,    'max': 200,   'hot': True},
    'vol_rv_threshold':          {'type': int,   'min': 20,   'max': 300,   'hot': True},
    'vol_lookback_beats':        {'type': int,   'min': 2,    'max': 30,    'hot': True},
    'vol_rv_window':             {'type': int,   'min': 5,    'max': 60,    'hot': True},
    'vol_regime_action':         {'type': str,   'min': None, 'max': None,  'hot': True},
    'vol_regime_cooldown_beats': {'type': int,   'min': 3,    'max': 60,    'hot': True},
    # Regime Controls — Portfolio Gamma Cap
    'gamma_cap_enabled':         {'type': bool,  'min': None, 'max': None,  'hot': True},
    'gamma_soft_limit':          {'type': float, 'min': 1,    'max': 50000, 'hot': True},
    'gamma_hard_limit':          {'type': float, 'min': 1,    'max': 50000, 'hot': True},
    'gamma_emergency_limit':     {'type': float, 'min': 1,    'max': 50000, 'hot': True},
    'gamma_near_expiry_multiplier': {'type': float, 'min': 0.1, 'max': 1.0, 'hot': True},
    # Regime Controls — Trend Detection Guard
    'trend_enabled':             {'type': bool,  'min': None, 'max': None,  'hot': True},
    'trend_move_pct':            {'type': float, 'min': 0.5,  'max': 10,    'hot': True},
    'trend_retrace_pct':         {'type': int,   'min': 10,   'max': 80,    'hot': True},
    'trend_ema_period':          {'type': int,   'min': 5,    'max': 50,    'hot': True},
    'trend_ema_slope_threshold': {'type': int,   'min': 5,    'max': 100,   'hot': True},
    'trend_action':              {'type': str,   'min': None, 'max': None,  'hot': True},
    'trend_reset_beats':         {'type': int,   'min': 2,    'max': 30,    'hot': True},
}


def validate_params(params: Dict[str, Any], hot_only: bool = False) -> Tuple[Dict[str, Any], list]:
    """
    Validate and coerce parameter values.

    Args:
        params: Dictionary of parameter name → value
        hot_only: If True, reject non-hot-reloadable parameters

    Returns:
        Tuple of (validated_params, errors)
        validated_params has coerced types
        errors is a list of error strings (empty if valid)
    """
    validated = {}
    errors = []

    for key, value in params.items():
        if key not in PARAM_RULES:
            errors.append(f"Unknown parameter: {key}")
            continue

        rule = PARAM_RULES[key]

        # Check hot-reload restriction
        if hot_only and not rule['hot']:
            errors.append(f"Parameter '{key}' cannot be changed while running (not hot-reloadable)")
            continue

        # Type coercion
        try:
            if rule['type'] == bool:
                if isinstance(value, str):
                    validated[key] = value.lower() in ('true', '1', 'yes', 'on')
                else:
                    validated[key] = bool(value)
            elif rule['type'] == int:
                validated[key] = int(value)
            elif rule['type'] == float:
                validated[key] = float(value)
            elif rule['type'] == str:
                validated[key] = str(value)
        except (ValueError, TypeError):
            errors.append(f"Parameter '{key}': invalid type. Expected {rule['type'].__name__}, got {type(value).__name__}")
            continue

        # Range validation
        if rule['min'] is not None and validated[key] < rule['min']:
            errors.append(f"Parameter '{key}': {validated[key]} below minimum {rule['min']}")
            continue
        if rule['max'] is not None and validated[key] > rule['max']:
            errors.append(f"Parameter '{key}': {validated[key]} above maximum {rule['max']}")
            continue

    return validated, errors


def get_hot_reload_params() -> Set[str]:
    """Return set of parameter names that support hot-reload."""
    return {k for k, v in PARAM_RULES.items() if v.get('hot', False)}


def get_param_info() -> Dict[str, Dict]:
    """
    Return parameter metadata for WebUI display.
    Includes type, range, hot-reload status, and description.
    """
    descriptions = {
        'desired_ce_premium': 'Target CE premium for auto strike selection',
        'desired_pe_premium': 'Target PE premium for auto strike selection',
        'initial_lots': 'Starting lots per side at entry',
        'expiry': 'Target expiry date/time',
        'adjustment_interval': 'Seconds between heartbeat checks',
        'min_trigger_move': 'Minimum % premium move above trigger to fire adjustment (e.g. 15 = 15%)',
        'shift_threshold': 'Minimum premium at hedge strike to avoid shift',
        'shift_target_premium': 'Target premium for new strike when shifting (picks strike closest to this premium)',
        'close_at_threshold': 'Close positions at this premium or below',
        'premium_buffer_pct': 'Extra lots percentage for slippage protection',
        'max_lots_per_side': 'Maximum total lots allowed per side (CE or PE)',
        'max_adjustments': 'Maximum number of adjustment events',
        'max_loss_amount': 'Absolute dollar hard stop — close all if breached',
        'stop_adjustment_mins': 'Stop adjusting N minutes before expiry',
        'auto_close_mins': 'Auto-close all positions N minutes before expiry',
        'cooldown_on_reversal': 'Skip one interval on reversal detection',
        'whipsaw_limit': 'Max alternating adjustments before auto-pause',
        'trailing_stop_pct': 'Protect profit at this percentage of peak P&L',
        'theta_acceleration_window': 'Minutes before expiry to widen triggers',
        'close_at_atm': 'Auto-close all if original strike becomes ATM (spot ≈ strike)',
        'itm_guard_enabled': 'Block selling ITM options for adjustment (ON = safe, OFF = allow ITM selling near expiry)',
        'adaptive_interval_enabled': 'Auto-scale heartbeat frequency based on time-to-expiry (faster checks as expiry nears)',
        'wind_down_enabled': 'Wind-down mode: reduce positions instead of adding when triggered near expiry',
        'wind_down_hours_before_expiry': 'Activate wind-down N hours before expiry (0 = disabled)',
        'wind_down_buyback_pct': 'Fraction of aggressor lots to buy back per trigger during wind-down (e.g. 0.25 = 25%)',
        'wind_down_close_threshold': 'Close any position with premium below this during wind-down (elevated close-at-5)',
        'wind_down_min_lots_to_keep': 'Never reduce below this many lots per side during wind-down (0 = allow full unwind)',
        'wind_down_floor_action': 'When at min lots during wind-down: skip (let theta work), normal (fall back to hedge), or pause (ask user)',
        'wind_down_on_atm': 'Auto-trigger wind-down mode if any original strike becomes ATM (spot ≈ strike). Instead of closing all, switches to gradual position reduction.',
        # Margin Guardian
        'margin_monitor_enabled': 'Enable real-time margin monitoring — auto-defends when margin utilization gets too high',
        'margin_green_pct': 'Below this % = normal operation (no intervention)',
        'margin_yellow_pct': 'At this % = caution — blocks new sell orders',
        'margin_orange_pct': 'At this % = force wind-down — aggressive buyback regardless of time-to-expiry',
        'margin_red_pct': 'At this % = emergency — close all positions using taker orders',
        'margin_critical_pct': 'At this % = survival — close all + stop session immediately',
        'margin_target_pct': 'Target margin utilization to wind down to during ORANGE/RED tiers',
        # Regime Controls — Volatility Regime Filter
        'regime_enabled': 'MASTER SWITCH for ALL regime controls (Volatility Filter, Gamma Cap, Trend Guard). When OFF, no regime checks run and adjustments proceed freely. Turn ON only after validating the data for a few days.',
        'vol_regime_enabled': 'Enable volatility regime filter — detects IV spikes and high RV to block sells in dangerous vol environments',
        'vol_iv_spike_pct': 'IV change % threshold — if IV rises this much from lookback point, trigger ELEVATED/HIGH regime',
        'vol_rv_threshold': 'Annualized realized volatility % threshold — high RV indicates dangerous market',
        'vol_lookback_beats': 'Number of heartbeats to look back for IV rate-of-change calculation',
        'vol_rv_window': 'Number of heartbeats for realized volatility computation window',
        'vol_regime_action': 'Action when vol regime triggers: block_sells (block new sells), pause (pause session), wind_down (activate wind-down)',
        'vol_regime_cooldown_beats': 'Must stay below threshold for this many beats before returning to NORMAL (prevents premature reset)',
        # Regime Controls — Portfolio Gamma Cap
        'gamma_cap_enabled': 'Enable portfolio gamma cap — monitors total dollar gamma exposure and blocks/reduces when limits exceeded',
        'gamma_soft_limit': 'Dollar gamma soft limit — warning level. Log alert but allow adjustments',
        'gamma_hard_limit': 'Dollar gamma hard limit — block all new sell orders when exceeded',
        'gamma_emergency_limit': 'Dollar gamma emergency — force wind-down buybacks to reduce gamma below hard limit',
        'gamma_near_expiry_multiplier': 'Tighten gamma limits by this factor in last 30 minutes (gamma explodes near expiry for ATM strikes)',
        # Regime Controls — Trend Detection Guard
        'trend_enabled': 'Enable trend detection guard — blocks exposure-increasing sells into strong directional moves',
        'trend_move_pct': 'Percentage move from session anchor to trigger trend guard (1.5% = ~$1,500 at BTC $100K)',
        'trend_retrace_pct': 'Spot must retrace this % of the move before trend guard resets (30 = need 30% retracement)',
        'trend_ema_period': 'EMA period in beats for slope calculation — confirms sustained directional drift',
        'trend_ema_slope_threshold': 'EMA slope threshold for trend confirmation — higher = less sensitive',
        'trend_action': 'Action when trend triggers: block_sells (block dangerous-side sells), pause, wind_down (also activate wind-down)',
        'trend_reset_beats': 'Must stay calm (retrace + low EMA slope) for this many beats before resetting to NORMAL',
    }

    info = {}
    for key, rule in PARAM_RULES.items():
        info[key] = {
            'type': rule['type'].__name__,
            'min': rule['min'],
            'max': rule['max'],
            'hot_reload': rule['hot'],
            'description': descriptions.get(key, ''),
        }

    return info
