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
    'min_trigger_dollar':          {'type': float, 'min': 0, 'max': 100000, 'hot': True},
    'min_frozen_trigger_dollar':   {'type': float, 'min': 0, 'max': 100000, 'hot': True},
    'shift_threshold':         {'type': float, 'min': 1,    'max': 5000,  'hot': True},
    'shift_target_premium':    {'type': float, 'min': 10,   'max': 5000,  'hot': True},
    'shift_premium_tolerance': {'type': float, 'min': 0,    'max': 500,   'hot': True},
    'close_at_threshold':      {'type': float, 'min': 0,    'max': 100,   'hot': True},
    'close_at_watch_interval': {'type': int,   'min': 0,    'max': 300,   'hot': True},
    'close_at_max_per_beat':   {'type': int,   'min': 1,    'max': 50,    'hot': True},
    'close_at_watcher_force_enabled':         {'type': bool,  'min': None, 'max': None, 'hot': True},
    'close_at_watch_hours_before_expiry':     {'type': float, 'min': 0,    'max': 24,   'hot': True},
    'close_at_watch_near_expiry_interval':    {'type': int,   'min': 5,    'max': 300,  'hot': True},
    'premium_buffer_pct':      {'type': float, 'min': 0,    'max': 0.5,   'hot': True},
    'max_lots_per_side':       {'type': int,   'min': 1,    'max': 10000, 'hot': True},
    # Split Ledger Phase 1
    'max_total_exposure':      {'type': int,   'min': 0,    'max': 20000, 'hot': True},
    # Split Ledger Phase 2 — Shift-Time Recycle
    'shift_recycle_enabled':              {'type': bool,  'min': None, 'max': None,  'hot': True},
    'shift_recycle_premium_floor':        {'type': float, 'min': 0,    'max': 500,   'hot': True},
    'shift_recycle_max_pct':              {'type': float, 'min': 0.0,  'max': 1.0,   'hot': True},
    'shift_recycle_floor_ratio':          {'type': float, 'min': 0.0,  'max': 1.0,   'hot': True},
    'shift_recycle_pressure_threshold':   {'type': float, 'min': 0.0,  'max': 1.0,   'hot': True},
    'max_adjustments':         {'type': int,   'min': 1,    'max': 1000,  'hot': True},
    # M-6 fix: min raised from 0 to 1 — setting to 0 triggers auto_close on
    # any negative P&L including normal spread fluctuation (extremely dangerous).
    'max_loss_amount':         {'type': float, 'min': 1,    'max': 1e9,   'hot': True},
    'stop_adjustment_mins':    {'type': int,   'min': 0,    'max': 1440,  'hot': True},
    'auto_close_mins':         {'type': int,   'min': 0,    'max': 1440,  'hot': True},
    'cooldown_on_reversal':    {'type': bool,  'min': None, 'max': None,  'hot': True},
    'whipsaw_limit':           {'type': int,   'min': 2,    'max': 100,   'hot': True},
    # Adaptive Whipsaw Guard
    'whipsaw_window_mins':     {'type': int,   'min': 5,    'max': 120,   'hot': True},
    'whipsaw_spot_move_pct':   {'type': float, 'min': 0.05, 'max': 5.0,   'hot': True},
    'whipsaw_caution_score':   {'type': int,   'min': 1,    'max': 10,    'hot': True},
    'whipsaw_restrict_score':  {'type': int,   'min': 2,    'max': 15,    'hot': True},
    'whipsaw_cooldown_score':  {'type': int,   'min': 3,    'max': 20,    'hot': True},
    'trailing_stop_pct':       {'type': float, 'min': 0,    'max': 1.0,   'hot': True},
    'theta_acceleration_window': {'type': int, 'min': 0,    'max': 1440,  'hot': True},
    'close_at_atm':              {'type': bool,  'min': None, 'max': None,  'hot': True},
    'itm_guard_enabled':         {'type': bool,  'min': None, 'max': None,  'hot': True},
    'shift_threshold_pct':       {'type': float, 'min': 0,    'max': 1.0,   'hot': True},
    'shift_match_opposite_lots': {'type': bool,  'min': None, 'max': None,  'hot': True},
    'pre_sell_shift_enabled':    {'type': bool,  'min': None, 'max': None,  'hot': True},
    'shift_fallback_enabled':    {'type': bool,  'min': None, 'max': None,  'hot': True},
    'shift_fallback_min_premium': {'type': float, 'min': 0,   'max': 500,   'hot': True},
    'proactive_shift_enabled':   {'type': bool,  'min': None, 'max': None,  'hot': True},
    'dangerous_mode':            {'type': bool,  'min': None, 'max': None,  'hot': True},
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
    # Tier B: per-side gamma imbalance — directional block when one side dominates
    'gamma_side_imbalance_ratio':   {'type': float, 'min': 1.1, 'max': 10.0, 'hot': True},
    # Tier C: DTE-aware hedge limit relaxation
    'gamma_dte_relax_hours':        {'type': float, 'min': 0,    'max': 6.0, 'hot': True},
    'gamma_dte_hedge_multiplier':   {'type': float, 'min': 1.0,  'max': 5.0, 'hot': True},
    # Tier D: delta rescue — override regime block for forced hedge sell near expiry
    'gamma_rescue_window_minutes':  {'type': float, 'min': 0,    'max': 480, 'hot': True},
    # Incremental gamma budget: when current gamma already exceeds hard_limit,
    # allow a trade if it adds ≤ this many dollars of additional gamma.
    # 0 = disabled (default, preserves old block-all behavior).
    'gamma_incremental_limit':      {'type': float, 'min': 0,    'max': 5000, 'hot': True},
    # Directional dead-band: minimum % move from anchor to trust direction for gamma block
    'gamma_directional_min_pct':    {'type': float, 'min': 0.0,  'max': 2.0, 'hot': True},
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
    'trend_plateau_reset_beats': {'type': int,   'min': 2,    'max': 50,    'hot': True},
    'trend_t4_timeout_beats':    {'type': int,   'min': 5,    'max': 100,   'hot': True},
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
    # Trend Boost — aggressive safe-side selling
    'trend_boost_enabled':          {'type': bool,  'min': None, 'max': None,  'hot': True},
    'trend_boost_tier1_mult':       {'type': float, 'min': 1.0,  'max': 3.0,   'hot': True},
    'trend_boost_tier2_mult':       {'type': float, 'min': 1.0,  'max': 3.0,   'hot': True},
    'trend_boost_tier3_mult':       {'type': float, 'min': 1.0,  'max': 3.0,   'hot': True},
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
    # Auto-Replenish Leg
    'replenish_enabled':          {'type': bool,  'min': None, 'max': None,  'hot': True},
    'replenish_lot_mode':         {'type': str,   'min': None, 'max': None,  'hot': True},
    'replenish_max_per_session':  {'type': int,   'min': 1,    'max': 20,    'hot': True},
    'replenish_cooldown_sec':     {'type': int,   'min': 30,   'max': 3600,  'hot': True},
    'replenish_min_premium':      {'type': float, 'min': 1,    'max': 500,   'hot': True},
    # ATM Shield — Close & Retreat
    'atm_shield_enabled':              {'type': bool,  'min': None, 'max': None,  'hot': True},
    'atm_shield_proximity_pct':        {'type': float, 'min': 0.1,  'max': 5.0,   'hot': True},
    'atm_shield_target_otm_pct':       {'type': float, 'min': 0.1,  'max': 10.0,  'hot': True},
    'atm_shield_loss_split_aggressor': {'type': float, 'min': 0.0,  'max': 1.0,   'hot': True},
    'atm_shield_max_per_session':      {'type': int,   'min': 1,    'max': 10,    'hot': True},
    'atm_shield_cooldown_mins':        {'type': int,   'min': 0,    'max': 60,    'hot': True},

    # Multi-Expiry DTE Presets
    'dte_category':                    {'type': str,   'min': None, 'max': None,  'hot': True},
    'total_dte_hours':                 {'type': float, 'min': 0,    'max': 10000, 'hot': True},
    'session_window_hours':            {'type': float, 'min': 0,    'max': 24,    'hot': True},
    'global_max_loss':                 {'type': float, 'min': 100,  'max': 1e9,   'hot': True},
    # Guardian params
    'guardian_enabled':                {'type': bool,  'min': None, 'max': None,  'hot': True},
    'guardian_max_close_per_beat':     {'type': int,   'min': 5,    'max': 500,   'hot': True},
    'guardian_max_beat_sec':           {'type': int,   'min': 30,   'max': 600,   'hot': True},
    'guardian_side_wipeout_floor':     {'type': int,   'min': 1,    'max': 100,   'hot': True},
    'shift_recycle_max_per_beat':      {'type': int,   'min': 1,    'max': 100,   'hot': True},
    'shift_match_max_inflate_mult':    {'type': float, 'min': 1.0,  'max': 10.0,  'hot': True},
    # Breakeven Engine
    'breakeven_control_enabled':        {'type': bool,  'min': None, 'max': None,  'hot': True},
    'breakeven_warning_pct':            {'type': float, 'min': 0.5,  'max': 10.0,  'hot': True},
    'breakeven_danger_pct':             {'type': float, 'min': 0.2,  'max': 5.0,   'hot': True},
    'breakeven_critical_pct':           {'type': float, 'min': 0.1,  'max': 2.0,   'hot': True},
    'breakeven_aggression_max':         {'type': float, 'min': 1.5,  'max': 5.0,   'hot': True},
    'breakeven_scan_range_pct':         {'type': float, 'min': 2.0,  'max': 15.0,  'hot': True},
    'max_combined_lot_multiplier':      {'type': float, 'min': 1.5,  'max': 5.0,   'hot': True},
    'breakeven_narrow_band_threshold':  {'type': float, 'min': 1.0,  'max': 10.0,  'hot': True},
    # Breakeven DTE-aware controls
    'breakeven_dte_threshold_mult':     {'type': float, 'min': 1.0,  'max': 5.0,   'hot': True},
    'breakeven_dte_aggression_damp':    {'type': float, 'min': 0.0,  'max': 0.4,   'hot': True},
    'breakeven_dte_vol_regime_damp':    {'type': float, 'min': 0.0,  'max': 1.0,   'hot': True},
    'breakeven_dte_pnl_clamp_pct':      {'type': float, 'min': 0.5,  'max': 3.0,   'hot': True},
    'breakeven_tv_credit_factor':       {'type': float, 'min': 0.0,  'max': 0.5,   'hot': True},
    'breakeven_high_risk_mode':         {'type': bool,  'min': None, 'max': None,  'hot': True},
    'breakeven_critical_lot_ceiling':   {'type': float, 'min': 2.0,  'max': 6.0,   'hot': True},
    # Gamma Detector Engine
    'gamma_detector_enabled':           {'type': bool,  'min': None, 'max': None,  'hot': True},
    'gamma_step_pct':                   {'type': float, 'min': 0.1,  'max': 5.0,   'hot': True},
    'gamma_scan_steps':                 {'type': int,   'min': 10,   'max': 200,   'hot': True},
    'gamma_warning_distance_pct':       {'type': float, 'min': 0.1,  'max': 20.0,  'hot': True},
    'gamma_danger_distance_pct':        {'type': float, 'min': 0.1,  'max': 10.0,  'hot': True},
    'gamma_detect_epsilon':             {'type': float, 'min': 0.01, 'max': 50.0,  'hot': True},
    'gamma_severity_multiplier_enabled':  {'type': bool,  'min': None, 'max': None,  'hot': False},
    'gamma_severity_max_multiplier':      {'type': float, 'min': 1.0,  'max': 3.0,   'hot': True},
    'gamma_severity_proportional':        {'type': bool,  'min': None, 'max': None,  'hot': True},   # F6
    'gamma_severity_warning_mult':        {'type': float, 'min': 1.0,  'max': 2.0,   'hot': True},   # F6
    'gamma_severity_shift_distance_mult': {'type': float, 'min': 1.0,  'max': 3.0,   'hot': True},   # F6
    # Feature 9: Data Confidence Gate
    'data_confidence_enabled':            {'type': bool,  'min': None, 'max': None,  'hot': True},
    'confidence_stale_penalty':           {'type': float, 'min': 0.0,  'max': 0.5,   'hot': True},
    'confidence_ws_failure_penalty':      {'type': float, 'min': 0.0,  'max': 0.1,   'hot': True},
    'confidence_min_floor':               {'type': float, 'min': 0.0,  'max': 0.5,   'hot': True},
    # Adaptive Tuning Engine
    'adaptive_mode':                     {'type': str,   'min': None, 'max': None,  'hot': True},
    'adaptive_preset':                   {'type': str,   'min': None, 'max': None,  'hot': True},
    'adaptive_dry_run':                  {'type': bool,  'min': None, 'max': None,  'hot': True},
    'atm_shield_partial_pct':            {'type': float, 'min': 0.1,  'max': 1.0,   'hot': True},
    'atm_shield_defer_resell_beats':     {'type': int,   'min': 0,    'max': 5,     'hot': True},
    # ── Reverse Mode ──
    'reverse_enabled':                   {'type': bool,  'min': None, 'max': None,  'hot': True},
    'reverse_capacity_pct':              {'type': float, 'min': 0,    'max': 100,   'hot': True},
    'reverse_num_slots':                 {'type': int,   'min': 1,    'max': 20,    'hot': True},
    'reverse_slot_size_override':        {'type': int,   'min': 0,    'max': 1000,  'hot': True},
    'reverse_max_adjustments':           {'type': int,   'min': 1,    'max': 20,    'hot': True},
    'reverse_time_start':                {'type': str,   'min': None, 'max': None,  'hot': True},
    'reverse_time_end':                  {'type': str,   'min': None, 'max': None,  'hot': True},
    'reverse_duration_mins':             {'type': int,   'min': 0,    'max': 1440,  'hot': True},
    'reverse_mode_type':                 {'type': str,   'min': None, 'max': None,  'hot': True},
    'reverse_cooldown_mins':             {'type': int,   'min': 0,    'max': 60,    'hot': True},
    'reverse_max_loss':                  {'type': float, 'min': 0,    'max': 1e9,   'hot': True},
    'reverse_close_at_threshold':        {'type': float, 'min': 0,    'max': 1000,  'hot': True},
    'reverse_unhedged_emergency_loss':   {'type': float, 'min': 0,    'max': 1e9,   'hot': True},
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
            # Skip silently — DEFAULT_PARAMS contains internal/non-editable params
            # (e.g. close_at_use_bid, shift_cooldown_sec) that don't need UI validation.
            # Old sessions merge new defaults on dialog open, causing unknown keys to appear.
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

    # max_adjustments should be >= whipsaw_cooldown_score
    max_adj = validated.get('max_adjustments')
    whipsaw = validated.get('whipsaw_limit')
    if max_adj is not None and whipsaw is not None and max_adj < whipsaw:
        errors.append(
            f"max_adjustments ({max_adj}) < whipsaw_limit ({whipsaw}): "
            "max-adjustments will be reached before whipsaw can detect alternation"
        )

    # Whipsaw score ordering: caution < restrict < cooldown
    ws_caution = validated.get('whipsaw_caution_score')
    ws_restrict = validated.get('whipsaw_restrict_score')
    ws_cooldown = validated.get('whipsaw_cooldown_score')
    if ws_caution is not None and ws_restrict is not None and ws_caution >= ws_restrict:
        errors.append(
            f"whipsaw_caution_score ({ws_caution}) must be < whipsaw_restrict_score ({ws_restrict})"
        )
    if ws_restrict is not None and ws_cooldown is not None and ws_restrict >= ws_cooldown:
        errors.append(
            f"whipsaw_restrict_score ({ws_restrict}) must be < whipsaw_cooldown_score ({ws_cooldown})"
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

    # M-6 note: max_loss_amount floor is enforced by PARAM_RULES min=1.
    # No additional check here — $3 is valid for conservative 1-lot presets (e.g. STRADDLE_WITH_ADJUSTMENT).

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

    # Breakeven zone threshold ordering: critical_pct < danger_pct < warning_pct
    if all(k in validated for k in ('breakeven_critical_pct', 'breakeven_danger_pct', 'breakeven_warning_pct')):
        c = validated['breakeven_critical_pct']
        d = validated['breakeven_danger_pct']
        w = validated['breakeven_warning_pct']
        if not (c < d < w):
            errors.append(
                f"Breakeven thresholds must satisfy critical < danger < warning "
                f"(got critical={c}, danger={d}, warning={w})"
            )

    # Trend Boost: multiplier ordering tier1 <= tier2 <= tier3
    boost_keys = ['trend_boost_tier1_mult', 'trend_boost_tier2_mult', 'trend_boost_tier3_mult']
    boost_vals = [(k, validated.get(k)) for k in boost_keys]
    boost_vals = [(k, v) for k, v in boost_vals if v is not None]
    for i in range(len(boost_vals) - 1):
        k1, v1 = boost_vals[i]
        k2, v2 = boost_vals[i + 1]
        if v1 > v2:
            errors.append(
                f"Trend boost multiplier ordering violated: {k1} ({v1}) must be <= {k2} ({v2}). "
                "Higher tiers should have equal or larger boost multipliers."
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
        'min_trigger_dollar': 'Dollar floor trigger: also fire if active-strike USD loss exceeds this amount regardless of % move (0 = disabled). Catches dead-zone losses below min_trigger_move threshold.',
        'min_frozen_trigger_dollar': 'Frozen position fallback trigger: fire if total frozen USD loss exceeds this amount when active trigger has not fired (0 = disabled). Covers blind-spot losses at old strikes.',
        'shift_threshold': 'Minimum premium at hedge strike to avoid shift',
        'shift_target_premium': 'Target premium for new strike when shifting (picks strike closest to this premium)',
        'shift_premium_tolerance': '±$ tolerance around shift_target_premium for live candidate validation. Before placing a shift order, the bot fetches the candidate strike\'s current premium — if it has drifted outside target±tolerance, the chain is rescanned for a better strike. Critical for 0DTE where premiums move fast. E.g. target=50, tolerance=10 → rescan if current premium is outside $40–$60. Set 0 to disable.',
        'close_at_threshold': 'Close positions at this premium or below',
        'close_at_watch_interval': 'Watcher polling interval (seconds) when force-enabled. 0 = disable force-enabled mode.',
        'close_at_max_per_beat': 'Max positions to close per heartbeat. Prevents heartbeat stall when many positions hit threshold near expiry.',
        'close_at_watcher_force_enabled': 'Force close-at-5 watcher ON regardless of expiry timing. Polls every close_at_watch_interval seconds.',
        'close_at_watch_hours_before_expiry': 'Watcher auto-activates within this many hours of expiry. Default 3h. Set 0 = always on.',
        'close_at_watch_near_expiry_interval': 'Watcher polling interval (seconds) inside the expiry window. Smaller = faster detection. Default 10s.',
        'premium_buffer_pct': 'Extra lots percentage for slippage protection',
        'max_lots_per_side': 'Maximum total lots allowed per side (CE or PE)',
        # Split Ledger
        'max_total_exposure': 'Absolute ceiling on active+frozen lots per side. 0 = auto (2× max_lots_per_side). Prevents runaway accumulation when frozen lots do not block the active cap.',
        'shift_recycle_enabled': 'Split Ledger Phase 2: At each strike shift, close cheap frozen positions to free capacity. Returns buyback cost is folded into the new sell calculation. Disabled by default — enable after observing Phase 1 behavior.',
        'shift_recycle_premium_floor': 'Shift-Time Recycle: only close frozen positions with live premium BELOW this value. 0 = dynamic mode (uses shift_recycle_floor_ratio × new_strike_premium). Default 20.',
        'shift_recycle_max_pct': 'Shift-Time Recycle: maximum fraction of total frozen lots to close per shift. 1.0 = all eligible. 0.5 = at most half. Prevents closing too many at once.',
        'shift_recycle_floor_ratio': 'Shift-Time Recycle dynamic floor: when shift_recycle_premium_floor=0, close frozen if premium < this fraction × new_strike_premium. 0.4 = close if frozen < 40% of new premium.',
        'shift_recycle_pressure_threshold': 'Shift-Time Recycle: minimum capacity pressure (total_lots/max_lots) required to run recycle. 0.7 = only recycle when 70%+ full. 0.0 = always run (not recommended — closes winning positions unnecessarily and wastes fees).',
        'max_adjustments': 'Maximum number of adjustment events',
        'max_loss_amount': 'Absolute dollar hard stop — close all if breached',
        'stop_adjustment_mins': 'Stop adjusting N minutes before expiry',
        'auto_close_mins': 'Auto-close all positions N minutes before expiry',
        'cooldown_on_reversal': 'Skip one interval on reversal detection',
        'whipsaw_limit': 'DEPRECATED — backward compat alias for whipsaw_cooldown_score',
        'whipsaw_window_mins': 'Rolling window (minutes): only count alternations within this window. Old alternations age out. Default 30.',
        'whipsaw_spot_move_pct': 'If BTC spot moved more than this % between two alternating adjustments, the alternation is considered justified (real hedge, not noise). Default 0.3%.',
        'whipsaw_caution_score': 'Whipsaw score to enter CAUTION: widen triggers by +50%. Score decays -1 per interval without new noise alternation.',
        'whipsaw_restrict_score': 'Whipsaw score to enter RESTRICT: widen triggers by +100% and halve lot sizes.',
        'whipsaw_cooldown_score': 'Whipsaw score to enter COOLDOWN: skip one interval, then score drops by 2. Never a full session PAUSE.',
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
        'gamma_side_imbalance_ratio': 'Tier B: one side must have ≥ this × the other side\'s dollar gamma to be blocked alone. Lower = more aggressive directional blocking; default 1.5 (50% imbalance needed)',
        'gamma_dte_relax_hours': 'Tier C: hours before expiry where the hedge sell limit is relaxed. Inside this window the hard limit is multiplied by gamma_dte_hedge_multiplier for hedge sells only. Set to 0 to disable Tier C entirely.',
        'gamma_dte_hedge_multiplier': 'Tier C: multiply hard gamma limit by this value for hedge sells inside the DTE relax window. Default 2.0 — hedge sells are allowed up to 2× the hard limit near expiry',
        'gamma_rescue_window_minutes': 'Tier D: minutes to expiry within which a forced hedge sell can override a gamma regime block. Set to 0 to disable. Default 120 (last 2 hours)',
        'gamma_incremental_limit': 'Incremental gamma budget: when portfolio gamma already exceeds hard_limit (e.g. near-ATM 0DTE positions), allow a trade if it adds ≤ this many dollars of additional gamma. Prevents permanent "once breached, always blocked" freeze. 0 = disabled (default, strict block-all). Recommended starting value: 500–1000.',
        'gamma_directional_min_pct': 'Minimum % move from the session anchor for directional gamma blocking to activate. When spot is within this dead-band of anchor (flat market), direction is ambiguous and per-side gamma imbalance is used instead. Prevents flip-flopping when spot oscillates near anchor. Default 0.10 (0.10% = ~$67 at $67K BTC)',
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
        'trend_plateau_reset_beats': 'When the market has moved to a new level (Tier 2–3) but never retraces AND raw tier has fallen below the locked tier (price stabilised below the lock threshold), this many flat-EMA beats will slide the anchor and reset. Does NOT apply at Tier 4 — use trend_t4_timeout_beats for that. Default: 5.',
        'trend_t4_timeout_beats': 'Emergency anchor unlock for Tier 4 plateau. After this many consecutive beats where EMA slope is flat (market stopped trending), the anchor slides to current price and the Tier 4 lock is cleared — re-enabling auto-replenish and new sells. The standard plateau reset cannot fire at T4 because the frozen anchor keeps abs_move above the T4 threshold indefinitely. Set higher for more patience before unlocking. Default: 20 (~20 min at 60s interval).',
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
        # Breakeven Engine
        'breakeven_control_enabled': 'Enable real-time portfolio breakeven awareness and defensive aggression',
        'breakeven_warning_pct': 'Distance % from spot to breakeven that triggers WARNING zone (multiplier ramps 1.0→1.3)',
        'breakeven_danger_pct': 'Distance % from spot to breakeven that triggers DANGER zone (multiplier ramps 1.3→2.0)',
        'breakeven_critical_pct': 'Distance % from spot to breakeven that triggers CRITICAL zone (multiplier ramps 2.0→max)',
        'breakeven_aggression_max': 'Maximum lot multiplier at deepest CRITICAL zone (caps the breakeven ramp)',
        'breakeven_scan_range_pct': 'Minimum scan width as % of spot for breakeven search (auto-expands to 120% beyond furthest strike)',
        'max_combined_lot_multiplier': 'Cap on combined gamma × breakeven × trend multiplier product (prevents compound runaway)',
        'breakeven_narrow_band_threshold': 'Warn operator when breakeven band width falls below this % of spot',
        # Breakeven DTE-aware controls
        'breakeven_dte_threshold_mult': 'DTE threshold widening multiplier. dte_scale = 1 + (mult-1)*sqrt(t_remaining/t_total). At 5DTE start with mult=1.5: thresholds 50% wider. Shrinks to 1.0 at expiry.',
        'breakeven_dte_aggression_damp': 'Reduce aggression in WARNING/DANGER zones by this fraction [0,0.4]. 0.1 = 10% reduction in lot boost. CRITICAL zone is always fully exempt.',
        'breakeven_dte_vol_regime_damp': 'Auto-damp applied when vol regime is ELEVATED (×0.5) or HIGH (×1.0). Overrides manual aggression_damp during vol spikes.',
        'breakeven_dte_pnl_clamp_pct': 'Disable dte_scale widening if |pnl_at_spot| / total_premium_collected > this ratio. Prevents false safety when position is already deeply in loss.',
        'breakeven_tv_credit_factor': 'Time value credit fraction [0,0.5]. Reserved — set to 0 (Tier 3 feature, not yet active).',
        'breakeven_high_risk_mode': 'Override all aggression damps to 0 AND force dte_scale=1.0 (0DTE-equivalent sensitivity + maximum lot aggression). Auto-expires after 4 hours via _high_risk_mode_expires_at session field.',
        'breakeven_critical_lot_ceiling': 'Max combined lot multiplier ceiling applied when zone=CRITICAL, overriding max_combined_lot_multiplier (which applies to WARNING/DANGER).',
        # Trigger & Adjustment — missing
        'shift_threshold_pct': 'Dynamic shift threshold as % of current entry premium. E.g. 0.30 = shift only when hedge premium drops below 30% of what you paid. Overrides the fixed shift_threshold when non-zero. 0 = use fixed shift_threshold instead.',
        'shift_match_opposite_lots': 'Delta-neutral balance: when shifting strikes, sell at least as many lots as the opposite side. E.g. PE has 11 lots → CE shift opens 11 lots (not just formula lots). Prevents directional bias. Trend-tier reductions still apply. Recommended: ON.',
        'pre_sell_shift_enabled': 'Experimental: shift to target premium BEFORE selling cheap hedge lots. In an up-move, CE rises but PE drops — algo would normally sell PE at 60-80 (below target 100), accumulating many cheap lots. With this ON: if PE < shift_target_premium, find a better OTM strike at ~100 first, then sell fewer lots there. Falls back to current behavior if no better strike exists. Default OFF.',
        'shift_fallback_enabled': 'When no new strike with premium >= shift_threshold is found, attempt to sell at the current (decayed) active strike if its premium >= shift_fallback_min_premium. Prevents the indefinite no-hedge loop. If premium is below the floor, the adjustment is skipped entirely. Default ON.',
        'shift_fallback_min_premium': 'Minimum premium floor for the shift fallback. If the decayed strike premium is below this value, the fallback is skipped entirely — selling near-worthless options adds delta risk with negligible credit (e.g. 70 lots @ $7.50 = $525 credit but full delta exposure). Default $25.',
        'dangerous_mode': '⚠️ DANGEROUS MODE: Bypasses ALL safety gates — cooldowns (reversal, whipsaw, consecutive-direction, shift), regime blocks (BLOCK_ALL_SELLS, BLOCK_CE, BLOCK_PE, FORCE_REDUCE, PAUSE), margin YELLOW block, and asymmetry 7:1 block. Only max_loss hard stop, ITM guard, and auto-close near expiry remain active. Intended for operator use during 0DTE expiry when fast algo response is required. REQUIRES typing CONFIRM in UI. Default OFF.',
        'proactive_shift_enabled': 'Master switch for proactive strike shifting. When ON, the algo detects when the active-strike premium decays below shift_threshold and proactively shifts to a better strike before being forced to. Disable to lock the algo to its current strikes until an adjustment naturally triggers a shift. Default ON.',
        # Trend Boost
        'trend_boost_enabled': 'Trend Boost: multiply hedge lots by tier multipliers when a trend is active. When CE is the aggressor in an uptrend, CE adjustment lots are scaled up to catch up faster. Each tier has its own multiplier.',
        'trend_boost_tier1_mult': 'Trend Boost Tier 1 (ALERT) lot multiplier. E.g. 1.5 = sell 50% more CE lots when Tier 1 trend is active on that side.',
        'trend_boost_tier2_mult': 'Trend Boost Tier 2 (GUARD) lot multiplier. Higher than Tier 1 — stronger trend warrants larger hedge. E.g. 2.0 = double the lots.',
        'trend_boost_tier3_mult': 'Trend Boost Tier 3 (BLOCK) lot multiplier — applies to the non-blocked side only. E.g. 2.5 = sell 2.5× PE lots when CE is fully blocked (uptrend Tier 3).',
        # Lot Velocity Limiter
        'lot_velocity_enabled': 'Enable lot velocity limiter — caps total lots sold within a rolling time window. Prevents runaway accumulation in fast-moving markets.',
        'lot_velocity_limit': 'Maximum lots that can be sold within the velocity window. When this limit is hit, all adjustments are blocked until the window rolls forward.',
        'lot_velocity_window_mins': 'Rolling window in minutes for the velocity cap. Lots sold within this window count toward the limit. Older sells age out automatically.',
        # Favorable Scale-Up
        'scale_enabled': 'Favorable Scale-Up: when BOTH CE and PE premiums are decaying (flat market), open new OTM positions to capture additional theta. These become standard MMM positions.',
        'scale_min_decay_pct': 'Minimum premium decay % required on BOTH sides before Scale-Up fires. E.g. 30 = both CE and PE must have decayed 30% from entry before scaling.',
        'scale_lots_pct': 'New position size as % of current total lots per side. E.g. 50 = new scaled position = 50% of current side lots.',
        'scale_max_events': 'Maximum scale-up events per session. Prevents unlimited position stacking in very flat markets.',
        'scale_cooldown_mins': 'Minimum minutes between consecutive scale-up events.',
        'scale_target_premium': 'Target premium (in $) when scanning for the new OTM strike to sell during scale-up. Picks the strike closest to this premium.',
        'scale_min_premium': 'Minimum premium ($) required for the scale-up strike to be sold. Prevents selling strikes with negligible theta.',
        # Auto-Replenish Leg
        'replenish_enabled': 'Auto-Replenish: when one side closes to 0 lots, automatically sell a new leg on the empty side instead of pausing.',
        'replenish_lot_mode': 'Lot sizing mode. match_active = match the open side active lots. initial = use initial_lots.',
        'replenish_max_per_session': 'Max replenishments per session. Prevents infinite re-entry loops.',
        'replenish_cooldown_sec': 'Min seconds between replenishments. Prevents rapid re-entry.',
        'replenish_min_premium': 'Min premium ($) for the replenish strike. Rejects illiquid strikes.',
        # ATM Shield
        'atm_shield_enabled': 'ATM Shield: pre-emptively closes endangered positions approaching ATM and repositions at a safer OTM strike. Overrides Trend Guard at T1/T2 when active.',
        'atm_shield_proximity_pct': 'ATM proximity threshold (% of spot). When any strike is within this % of spot, Shield fires. E.g. 1.5 = fire when strike is within 1.5% of BTC price.',
        'atm_shield_target_otm_pct': 'After closing the ATM-bound strike, re-sell at this % OTM from spot. E.g. 3.0 = new strike at spot ± 3%.',
        'atm_shield_loss_split_aggressor': 'Fraction of ATM Shield buyback loss to add to the new lot calculation for the aggressor side. 0.5 = split loss 50/50 between sides. 1.0 = all loss on the aggressor.',
        'atm_shield_max_per_session': 'Maximum ATM Shield activations per session. Prevents repeated close-reopen cycles in a trending market.',
        'atm_shield_cooldown_mins': 'Minimum minutes between consecutive ATM Shield activations.',
        # Gamma Detector
        'gamma_detector_enabled': 'Enable P&L curvature scanner — detects kinks in the portfolio P&L curve at option strikes (gamma boundaries). Warns before spot reaches a breakeven boundary.',
        'gamma_step_pct': 'Step size (% of spot) for gamma scan grid. Smaller = finer resolution but slower scan. Default 0.5%.',
        'gamma_scan_steps': 'Number of steps on each side of spot to scan for gamma kinks. E.g. 50 steps × 0.5% = ±25% of spot covered.',
        'gamma_warning_distance_pct': 'Distance (% of spot) from nearest gamma boundary to trigger WARNING zone. E.g. 5.0 = warn when boundary is within 5% of current spot.',
        'gamma_danger_distance_pct': 'Distance (% of spot) to trigger DANGER zone. Should be less than warning threshold. E.g. 2.0 = danger when boundary within 2% of spot.',
        'gamma_detect_epsilon': 'Minimum P&L slope change to count as a kink (gamma boundary). Lower = more sensitive, more false positives. Default 1.0.',
        'gamma_severity_multiplier_enabled': 'Phase 9 (RESTART REQUIRED): enable lot multiplier modulation based on gamma severity score. When ON, the gamma detector not only warns but actively scales hedge lots proportional to curvature magnitude.',
        'gamma_severity_max_multiplier': 'Maximum lot multiplier applied by gamma severity modulation (Phase 9). E.g. 2.0 = at maximum severity, double the hedge lots.',
        # Adaptive Tuning Engine
        'adaptive_mode': 'Parameter tuning mode. manual = you set everything; preset = loads recommended values for your strategy type; adaptive = auto-tunes ATM Shield and buffer params based on live market regime. Default: manual.',
        'adaptive_preset': 'Strategy profile for preset/adaptive mode. strangle = standard OTM; straddle = near-ATM; short_window = 3–5 hour sessions. Loads optimized base values for ATM Shield proximity, cooldown, and buffer.',
        'adaptive_dry_run': 'Shadow mode: compute what the adaptive engine would change but only log it — do not apply. Use to validate adaptive behavior before enabling live tuning.',
        'atm_shield_partial_pct': 'Fraction of active positions to close on shield fire. 1.0 = close all (default). 0.5 = close half. Partial mode useful in oscillating markets — avoids crystallizing full loss on a potential reversal while still reducing gamma exposure.',
        'atm_shield_defer_resell_beats': 'Beats to wait after closing before re-selling at new OTM strike. 0 = immediate re-sell (default). 1 = wait one heartbeat interval. Deferring lets the market settle and often catches a better premium, especially in high-volatility conditions.',
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
