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
    # NOTE: initial_lots is display-only — stored for analytics/reporting but
    # the runtime entry lot count is set by the API request body, not this param.
    'initial_lots':            {'type': int,   'min': 1,    'max': 1000,  'hot': False},
    'expiry':                  {'type': str,   'min': None, 'max': None,  'hot': False},
    'adjustment_interval':     {'type': int,   'min': 10,   'max': 3600,  'hot': True},
    'min_trigger_move':        {'type': float, 'min': 0.1,  'max': 100,   'hot': True},
    'shift_threshold':         {'type': float, 'min': 1,    'max': 5000,  'hot': True},
    'shift_target_premium':    {'type': float, 'min': 10,   'max': 5000,  'hot': True},
    'close_at_threshold':      {'type': float, 'min': 0,    'max': 100,   'hot': True},
    'premium_buffer_pct':      {'type': float, 'min': 0,    'max': 0.5,   'hot': True},
    'max_lots_per_side':       {'type': int,   'min': 1,    'max': 10000, 'hot': True},
    # Split Ledger Phase 1
    'max_total_exposure':      {'type': int,   'min': 0,    'max': 20000, 'hot': True},
    # Split Ledger Phase 2 — Shift-Time Recycle
    'shift_recycle_enabled':         {'type': bool,  'min': None, 'max': None,  'hot': True},
    'shift_recycle_premium_floor':   {'type': float, 'min': 0,    'max': 500,   'hot': True},
    'shift_recycle_max_pct':         {'type': float, 'min': 0.0,  'max': 1.0,   'hot': True},
    'shift_recycle_floor_ratio':     {'type': float, 'min': 0.0,  'max': 1.0,   'hot': True},
    'max_adjustments':         {'type': int,   'min': 1,    'max': 1000,  'hot': True},
    # M-6 fix: min raised from 0 to 1 — setting to 0 triggers auto_close on
    # any negative P&L including normal spread fluctuation (extremely dangerous).
    'max_loss_amount':         {'type': float, 'min': 1,    'max': 1e9,   'hot': True},
    'stop_adjustment_mins':    {'type': int,   'min': 0,    'max': 1440,  'hot': True},
    'auto_close_mins':         {'type': int,   'min': 0,    'max': 1440,  'hot': True},
    'cooldown_on_reversal':    {'type': bool,  'min': None, 'max': None,  'hot': True},
    'whipsaw_limit':           {'type': int,   'min': 2,    'max': 100,   'hot': True},
    'trailing_stop_pct':       {'type': float, 'min': 0,    'max': 1.0,   'hot': True},
    'theta_acceleration_window': {'type': int, 'min': 0,    'max': 1440,  'hot': True},
    'close_at_atm':              {'type': bool,  'min': None, 'max': None,  'hot': True},
    'itm_guard_enabled':         {'type': bool,  'min': None, 'max': None,  'hot': True},
    'shift_threshold_pct':       {'type': float, 'min': 0,    'max': 1.0,   'hot': True},
    'shift_match_opposite_lots': {'type': bool,  'min': None, 'max': None,  'hot': True},
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
    # Regime Controls — Trend Detection Guard (Tiered — IMP-2)
    'trend_enabled':             {'type': bool,  'min': None, 'max': None,  'hot': True},
    'trend_tier1_pct':           {'type': float, 'min': 0.1,  'max': 5.0,   'hot': True},
    'trend_tier2_pct':           {'type': float, 'min': 0.2,  'max': 8.0,   'hot': True},
    'trend_tier3_pct':           {'type': float, 'min': 0.5,  'max': 10.0,  'hot': True},
    'trend_tier4_pct':           {'type': float, 'min': 0.5,  'max': 15.0,  'hot': True},
    'trend_tier1_lot_reduction': {'type': float, 'min': 0.05, 'max': 0.90,  'hot': True},
    'trend_move_pct':            {'type': float, 'min': 0.5,  'max': 10,    'hot': True},
    'trend_retrace_pct':         {'type': int,   'min': 10,   'max': 80,    'hot': True},
    'trend_ema_period':          {'type': int,   'min': 5,    'max': 50,    'hot': True},
    'trend_ema_slope_threshold': {'type': int,   'min': 5,    'max': 100,   'hot': True},
    'trend_action':              {'type': str,   'min': None, 'max': None,  'hot': True},
    'trend_reset_beats':         {'type': int,   'min': 2,    'max': 30,    'hot': True},
    'trend_acceleration_window_s': {'type': int, 'min': 60,   'max': 3600,  'hot': True},
    'trend_acceleration_pct':    {'type': float, 'min': 0.1,  'max': 5.0,   'hot': True},
    # Perpetual Futures Delta Hedge (Fix #26)
    'perp_hedge_enabled':        {'type': bool,  'min': None, 'max': None,  'hot': True},
    # Fix #26.2: Perp hedge mode — 'full' hedges entire portfolio delta every heartbeat,
    # 'atm_only' activates perp ONLY when any strike is within atm_threshold_pct of spot,
    # letting OTM positions benefit from theta decay undisturbed.
    'perp_hedge_mode':           {'type': str,   'min': None, 'max': None,  'hot': True},
    'perp_hedge_atm_threshold_pct': {'type': float, 'min': 0.5, 'max': 5.0, 'hot': True},
    'perp_hedge_delta_threshold': {'type': float, 'min': 0.005, 'max': 0.10, 'hot': True},
    'perp_hedge_ratio':          {'type': float, 'min': 0.1,  'max': 1.0,  'hot': True},
    'perp_hedge_rebalance_band': {'type': float, 'min': 0.001, 'max': 0.02, 'hot': True},
    'perp_hedge_max_lots':       {'type': int,   'min': 5,    'max': 200,   'hot': True},
    'perp_hedge_cooldown_sec':   {'type': int,   'min': 10,   'max': 300,   'hot': True},
    # M-8 fix: rate-limit perp hedge direction flips to avoid spread drag in choppy markets
    'perp_hedge_max_flips_per_hour': {'type': int, 'min': 2,  'max': 30,   'hot': True},
    # M-5 fix: configurable circuit breaker failure threshold
    'circuit_breaker_threshold': {'type': int,   'min': 3,    'max': 20,   'hot': True},
    # L-1 fix: configurable expiry time (non-hot — set at session creation only)
    'expiry_hour_utc':           {'type': int,   'min': 0,    'max': 23,   'hot': False},
    'expiry_minute_utc':         {'type': int,   'min': 0,    'max': 59,   'hot': False},
    # L-3 fix: configurable max reprice attempts
    'max_reprice_attempts':      {'type': int,   'min': 1,    'max': 10,   'hot': True},
    # L-4 fix: configurable P&L reconciliation threshold
    'pnl_reconciliation_threshold': {'type': float, 'min': 1.0, 'max': 1000.0, 'hot': True},
    # M1: Profit Harvesting
    'harvest_enabled':              {'type': bool,  'min': None, 'max': None,  'hot': True},
    'harvest_profit_pct':           {'type': float, 'min': 20,   'max': 80,    'hot': True},
    'harvest_min_age_mins':         {'type': int,   'min': 10,   'max': 120,   'hot': True},
    'harvest_pressure_threshold':   {'type': float, 'min': 0.4,  'max': 0.9,   'hot': True},
    'harvest_max_per_beat':         {'type': int,   'min': 1,    'max': 10,    'hot': True},
    # M2: Lot Recycling
    'recycle_enabled':              {'type': bool,  'min': None, 'max': None,  'hot': True},
    'recycle_premium_ceiling':      {'type': float, 'min': 10,   'max': 200,   'hot': True},
    'recycle_min_premium_ratio':    {'type': float, 'min': 1.5,  'max': 10,    'hot': True},
    'recycle_max_pct':              {'type': float, 'min': 0.2,  'max': 0.8,   'hot': True},
    'recycle_free_lot_buffer':      {'type': int,   'min': 0,    'max': 50,    'hot': True},
    'recycle_min_lot_gain':         {'type': int,   'min': 1,    'max': 20,    'hot': True},
    'recycle_cooldown_sec':         {'type': int,   'min': 60,   'max': 600,   'hot': True},
    'recycle_protect_original':     {'type': bool,  'min': None, 'max': None,  'hot': True},
    # M3: Asymmetry Rebalancing
    'rebalance_enabled':            {'type': bool,  'min': None, 'max': None,  'hot': True},
    'rebalance_asymmetry_threshold': {'type': float, 'min': 2,  'max': 20,    'hot': True},
    'rebalance_pressure_threshold': {'type': float, 'min': 0.5,  'max': 1.0,   'hot': True},
    # T2-4: Lot Velocity Limiter
    'lot_velocity_enabled':         {'type': bool,  'min': None, 'max': None,  'hot': True},
    'lot_velocity_limit':           {'type': int,   'min': 1,    'max': 500,   'hot': True},
    'lot_velocity_window_mins':     {'type': int,   'min': 5,    'max': 120,   'hot': True},
    # FSU: Favorable Scale-Up
    'scale_enabled':          {'type': bool,  'min': None, 'max': None,   'hot': True},
    'scale_min_decay_pct':    {'type': float, 'min': 10,   'max': 90,     'hot': True},
    'scale_lots_pct':         {'type': float, 'min': 10,   'max': 100,    'hot': True},
    'scale_max_events':       {'type': int,   'min': 1,    'max': 20,     'hot': True},
    'scale_cooldown_mins':    {'type': int,   'min': 5,    'max': 240,    'hot': True},
    'scale_target_premium':   {'type': float, 'min': 10,   'max': 5000,   'hot': True},
    'scale_min_premium':      {'type': float, 'min': 5,    'max': 1000,   'hot': True},
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

    # ── Fix #15: Cross-parameter interdependency validation ──
    # These rules catch invalid combinations that pass individual range checks.
    _interdependency_checks(validated, errors)

    return validated, errors


def _interdependency_checks(validated: Dict[str, Any], errors: list):
    """
    Validate cross-parameter relationships.
    Fix #15 from MMM_robustv2 audit: prevent degenerate parameter combinations
    that cause infinite loops, dead triggers, or inconsistent safety tiers.
    """
    # wind_down_close_threshold must be >= close_at_threshold
    wd_close = validated.get('wind_down_close_threshold')
    close_at = validated.get('close_at_threshold')
    if wd_close is not None and close_at is not None and wd_close < close_at:
        errors.append(
            f"wind_down_close_threshold ({wd_close}) must be >= close_at_threshold ({close_at}): "
            "wind-down should be more aggressive than normal close"
        )

    # Margin tier ordering: green < yellow < orange < red < critical
    margin_keys = ['margin_green_pct', 'margin_yellow_pct', 'margin_orange_pct',
                   'margin_red_pct', 'margin_critical_pct']
    margin_vals = [(k, validated.get(k)) for k in margin_keys]
    margin_vals = [(k, v) for k, v in margin_vals if v is not None]
    for i in range(len(margin_vals) - 1):
        k1, v1 = margin_vals[i]
        k2, v2 = margin_vals[i + 1]
        if v1 >= v2:
            errors.append(
                f"Margin tier ordering violated: {k1} ({v1}) must be < {k2} ({v2})"
            )

    # max_adjustments should be >= whipsaw_limit for whipsaw detection to be meaningful
    max_adj = validated.get('max_adjustments')
    whipsaw = validated.get('whipsaw_limit')
    if max_adj is not None and whipsaw is not None and max_adj < whipsaw:
        errors.append(
            f"max_adjustments ({max_adj}) < whipsaw_limit ({whipsaw}): "
            "max-adjustments will be reached before whipsaw can detect alternation"
        )

    # auto_close_mins should be <= stop_adjustment_mins (stop adjusting before closing)
    auto_close = validated.get('auto_close_mins')
    stop_adj = validated.get('stop_adjustment_mins')
    if auto_close is not None and stop_adj is not None:
        if auto_close > 0 and stop_adj > 0 and auto_close > stop_adj:
            errors.append(
                f"auto_close_mins ({auto_close}) > stop_adjustment_mins ({stop_adj}): "
                "session would close before adjustment stop takes effect"
            )

    # gamma limits: soft < hard < emergency
    gamma_soft = validated.get('gamma_soft_limit')
    gamma_hard = validated.get('gamma_hard_limit')
    gamma_emrg = validated.get('gamma_emergency_limit')
    if gamma_soft is not None and gamma_hard is not None and gamma_soft >= gamma_hard:
        errors.append(
            f"gamma_soft_limit ({gamma_soft}) must be < gamma_hard_limit ({gamma_hard})"
        )
    if gamma_hard is not None and gamma_emrg is not None and gamma_hard >= gamma_emrg:
        errors.append(
            f"gamma_hard_limit ({gamma_hard}) must be < gamma_emergency_limit ({gamma_emrg})"
        )

    # perp hedge: delta_threshold must be > rebalance_band (otherwise every
    # heartbeat would immediately trigger a rebalance on a brand-new position)
    perp_threshold = validated.get('perp_hedge_delta_threshold')
    perp_band = validated.get('perp_hedge_rebalance_band')
    if perp_threshold is not None and perp_band is not None and perp_threshold <= perp_band:
        errors.append(
            f"perp_hedge_delta_threshold ({perp_threshold}) must be > "
            f"perp_hedge_rebalance_band ({perp_band}): "
            "threshold must exceed band to avoid immediate rebalance on entry"
        )

    # M-6 fix: warn if max_loss_amount is set dangerously low
    max_loss = validated.get('max_loss_amount')
    if max_loss is not None and max_loss < 10:
        errors.append(
            f"max_loss_amount below $10 is dangerous — session may auto-close "
            "on normal spread fluctuation. Minimum recommended value is $100."
        )

    # IMP-2: Trend tier ordering: tier1 < tier2 < tier3 < tier4
    tier_keys = ['trend_tier1_pct', 'trend_tier2_pct', 'trend_tier3_pct', 'trend_tier4_pct']
    tier_vals = [(k, validated.get(k)) for k in tier_keys]
    tier_vals = [(k, v) for k, v in tier_vals if v is not None]
    for i in range(len(tier_vals) - 1):
        k1, v1 = tier_vals[i]
        k2, v2 = tier_vals[i + 1]
        if v1 >= v2:
            errors.append(
                f"Trend tier ordering violated: {k1} ({v1}) must be < {k2} ({v2}). "
                "Each tier threshold must be strictly higher than the previous."
            )

    # M-5 fix: circuit breaker threshold sanity check
    cb_threshold = validated.get('circuit_breaker_threshold')
    if cb_threshold is not None and cb_threshold < 3:
        errors.append(
            f"circuit_breaker_threshold ({cb_threshold}) below 3 is too aggressive — "
            "normal exchange latency spikes will constantly trip the breaker"
        )


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
        'initial_lots': 'Starting lots per side at entry (display/analytics only — actual entry lots set via API)',
        'expiry': 'Target expiry date/time',
        'adjustment_interval': 'Seconds between heartbeat checks',
        'min_trigger_move': 'Minimum % premium move above trigger to fire adjustment (e.g. 15 = 15%)',
        'shift_threshold': 'Minimum premium at hedge strike to avoid shift',
        'shift_target_premium': 'Target premium for new strike when shifting (picks strike closest to this premium)',
        'close_at_threshold': 'Close positions at this premium or below',
        'premium_buffer_pct': 'Extra lots percentage for slippage protection',
        'max_lots_per_side': 'Maximum total lots allowed per side (CE or PE)',
        # Split Ledger
        'max_total_exposure': 'Absolute ceiling on active+frozen lots per side. 0 = auto (2× max_lots_per_side). Prevents runaway accumulation when frozen lots do not block the active cap.',
        'shift_recycle_enabled': 'Split Ledger Phase 2: At each strike shift, close cheap frozen positions to free capacity. Returns buyback cost is folded into the new sell calculation. Disabled by default — enable after observing Phase 1 behavior.',
        'shift_recycle_premium_floor': 'Shift-Time Recycle: only close frozen positions with live premium BELOW this value. 0 = dynamic mode (uses shift_recycle_floor_ratio × new_strike_premium). Default 60.',
        'shift_recycle_max_pct': 'Shift-Time Recycle: maximum fraction of total frozen lots to close per shift. 1.0 = all eligible. 0.5 = at most half. Prevents closing too many at once.',
        'shift_recycle_floor_ratio': 'Shift-Time Recycle dynamic floor: when shift_recycle_premium_floor=0, close frozen if premium < this fraction × new_strike_premium. 0.4 = close if frozen < 40% of new premium.',
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
        # Regime Controls — Trend Detection Guard (Tiered — IMP-2)
        'trend_enabled': 'Master switch for the tiered trend detection guard. Detects strong directional BTC moves and responds with graduated actions: lot reduction → directional block → full block → wind-down.',
        'trend_tier1_pct': 'Tier 1 (ALERT): % move from session anchor to start reducing hedge lots. At this level, the algo logs a warning and reduces new hedge lot sizes by trend_tier1_lot_reduction %. Recommended: 0.5% (~$500 at BTC $100K). This is the earliest "soft" response.',
        'trend_tier2_pct': 'Tier 2 (GUARD): % move from session anchor to block sells on the aggressor side. In a rally, CE sells are blocked (no more short calls into a rising market). PE adjustments still allowed. Recommended: 1.0% (~$1,000 at BTC $100K).',
        'trend_tier3_pct': 'Tier 3 (BLOCK): % move from session anchor to block ALL new option sells (both CE and PE). Existing positions are protected — no new risk added. This is a full freeze on the book. Recommended: 1.5% (~$1,500 at BTC $100K).',
        'trend_tier4_pct': 'Tier 4 (WIND-DOWN): % move from session anchor to automatically activate wind-down mode without operator confirmation. The algo starts buying back the most exposed side. Recommended: 2.0% (~$2,000 at BTC $100K).',
        'trend_tier1_lot_reduction': 'At Tier 1, reduce calculated hedge lot size by this fraction. 0.30 = reduce lots by 30% (sell 70% of what the formula calculates). Higher = more conservative at early trend stages.',
        'trend_move_pct': 'DEPRECATED — Legacy single-threshold trend trigger. Kept for backward compatibility. The tiered system (tier1–tier4) supersedes this. If tier params are not set, this is used as fallback for Tier 2.',
        'trend_retrace_pct': 'Spot must retrace this percentage of the move before the trend guard resets to Tier 0. 30% means if BTC moved $2K up, it needs to pull back $600 before the guard clears. Prevents premature reset.',
        'trend_ema_period': 'EMA period in heartbeats for slope calculation. Used for Tier 1 confirmation only — confirms sustained directional drift vs a one-time spike. Tiers 2-4 fire on absolute % move alone (no EMA needed).',
        'trend_ema_slope_threshold': 'EMA slope threshold for Tier 1 confirmation only. Higher = less sensitive. Tiers 2-4 do not require EMA confirmation — large moves speak for themselves.',
        'trend_action': 'Action when trend triggers: block_sells (block dangerous-side sells), pause, wind_down (also activate wind-down). At Tier 4, wind-down is auto-triggered regardless of this setting.',
        'trend_reset_beats': 'Must stay calm (retrace + low EMA slope) for this many beats before resetting to Tier 0 (NORMAL). Simple binary reset — goes from any tier straight to 0.',
        'trend_acceleration_window_s': 'Rate-of-change window in seconds. If BTC moves trend_acceleration_pct within this window, bypasses EMA confirmation for Tier 1. Catches sharp spikes that EMA would lag behind. Default: 600s (10 min).',
        'trend_acceleration_pct': 'Fast-move threshold: if BTC moves this % within the acceleration window, bypass EMA and enter Tier 1+. Catches sudden spikes vs slow drift. Default: 0.5% (~$500 at BTC $100K in 10 min).',
        # Perpetual Futures Delta Hedge
        'perp_hedge_enabled': 'Enable BTCUSD perpetual futures delta hedge — neutralizes portfolio delta from short options positions using a linear instrument (zero gamma impact)',
        'perp_hedge_mode': 'Hedge mode: "full" = hedge entire portfolio delta every heartbeat, "atm_only" = activate perp ONLY when a strike is near ATM (lets OTM theta profit run undisturbed)',
        'perp_hedge_atm_threshold_pct': 'ATM proximity threshold (%). In "atm_only" mode, perp activates only when any strike is within this % of spot price. E.g., 1.5 = strike must be within 1.5% of spot. Only used when mode is "atm_only".',
        'perp_hedge_max_flips_per_hour': 'M-8: Maximum perp hedge direction flips per hour to prevent spread drag in choppy markets (default 6)',
        # Circuit breaker
        'circuit_breaker_threshold': 'M-5: Consecutive failures to trip circuit breaker (default 5; raise to 10+ during volatile API periods)',
        # Expiry time
        'expiry_hour_utc': 'L-1: UTC hour of options expiry (default 12 = 5:30 PM IST for Delta Exchange BTC)',
        'expiry_minute_utc': 'L-1: UTC minute of options expiry (default 0)',
        # Reprice & reconciliation
        'max_reprice_attempts': 'L-3: Max reprice attempts per order (default 4 = 4-min worst-case block; 10 = original 10-min)',
        'pnl_reconciliation_threshold': 'L-4: Dollar threshold for P&L reconciliation warnings (default $10; raise for large accounts)',
        'perp_hedge_delta_threshold': 'Minimum |portfolio delta| (in BTC) to open an initial perp hedge. Below this threshold, delta is too small to justify a hedge trade (e.g. 0.02 = 2% of 1 BTC)',
        'perp_hedge_ratio': 'Fraction of portfolio delta to neutralize with perp (1.0 = full hedge, 0.5 = half hedge). Lower values leave residual directional exposure intentionally',
        'perp_hedge_rebalance_band': 'Minimum |effective delta| (options + perp combined) to trigger a rebalance of an existing perp position. Prevents over-trading on tiny delta drift',
        'perp_hedge_max_lots': 'Maximum perp position size in lots (hard cap on long or short). Prevents runaway hedging in extreme delta scenarios',
        'perp_hedge_cooldown_sec': 'Minimum seconds between consecutive perp hedge executions. Prevents rapid flip-flop trading when delta oscillates near the threshold',
        # M1: Profit Harvesting
        'harvest_enabled': 'M1: Enable proactive profit harvesting of frozen positions',
        'harvest_profit_pct': 'M1: Minimum profit % (entry vs current) to harvest a frozen position (default 40%)',
        'harvest_min_age_mins': 'M1: Minimum position age in minutes before it is eligible for harvesting',
        'harvest_pressure_threshold': 'M1: Minimum capacity pressure (total_lots/max_lots) to start harvesting',
        'harvest_max_per_beat': 'M1: Maximum frozen positions to close per heartbeat',
        # M2: Lot Recycling
        'recycle_enabled': 'M2: Enable emergency lot recycling when max lots blocks an adjustment',
        'recycle_premium_ceiling': 'M2: Maximum current premium for a position to be considered recyclable',
        'recycle_min_premium_ratio': 'M2: Minimum new_strike_premium / avg_recycle_premium ratio required to proceed',
        'recycle_max_pct': 'M2: Maximum fraction of side lots to recycle in a single operation',
        'recycle_free_lot_buffer': 'M2: Extra lots to free beyond the immediate need (buffer for next adjustment)',
        'recycle_min_lot_gain': 'M2: Minimum net lots freed (recycled - new_sold) to proceed with recycling',
        'recycle_cooldown_sec': 'M2: Cooldown in seconds between consecutive recycle operations',
        'recycle_protect_original': 'M2: Never recycle the original entry position',
        # M3: Asymmetry Rebalancing
        'rebalance_enabled': 'M3: Enable asymmetry-aware harvest threshold relaxation on the dominant side',
        'rebalance_asymmetry_threshold': 'M3: CE/PE lot ratio that triggers relaxed harvest thresholds on the dominant side',
        'rebalance_pressure_threshold': 'M3: Minimum capacity pressure on dominant side required for threshold relaxation',
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
