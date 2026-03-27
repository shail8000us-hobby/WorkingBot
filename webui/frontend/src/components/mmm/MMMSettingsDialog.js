/**
 * MMMSettingsDialog — Money Mind & Method
 *
 * Parameter editor with hot-reload support.
 * Allows editing strategy parameters while session is running.
 * Non-hot parameters (expiry, initial lots, etc.) require restart.
 *
 * Maps to MONEY_POWER_CALCULATION_LOGIC.md §19 Parameters
 *
 * Created: February 16, 2026
 */

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Grid,
  Typography,
  Box,
  Chip,
  Alert,
  FormControlLabel,
  Switch,
  Divider,
  Tooltip,
  CircularProgress,
  Select,
  MenuItem,
  InputLabel,
  FormControl,
  IconButton,
} from '@mui/material';
import {
  Settings as SettingsIcon,
  Bolt as HotIcon,
  Lock as LockIcon,
  Warning as WarningIcon,
  HelpOutline as HelpIcon,
  Star as StarIcon,
  StarBorder as StarBorderIcon,
} from '@mui/icons-material';
import mmmService from './mmmService';
import { HELP } from './MMMEducation';

// =============================================================================
// Parameter Groups for UI Organization
// =============================================================================

// Sealed params — logic is contract-tested and protected. Badge shown in UI.
const SEALED_PARAMS = new Set(['max_loss_amount', 'initial_lots', 'adjustment_interval']);

const PARAM_GROUPS = {
  core: {
    title: 'Core Parameters',
    color: '#2196f3',
    blurb: 'Fundamental settings that define position size, check frequency, and hard stop.',
    params: ['initial_lots', 'adjustment_interval', 'max_loss_amount'],
  },
  triggers: {
    title: 'Trigger & Adjustment',
    color: '#4caf50',
    blurb: 'Controls when the algo adjusts and how it shifts strikes. Lower trigger = more sensitive.',
    params: ['min_trigger_move', 'min_trigger_dollar', 'min_frozen_trigger_dollar', 'shift_threshold', 'shift_threshold_pct', 'shift_target_premium', 'pre_sell_shift_enabled', 'shift_match_opposite_lots', 'max_adjustments', 'cooldown_on_reversal'],
  },
  safety: {
    title: 'Safety Limits',
    color: '#ff9800',
    blurb: 'Guard rails to prevent runaway exposure. Adjust carefully.',
    params: ['whipsaw_window_mins', 'whipsaw_spot_move_pct', 'whipsaw_caution_score', 'whipsaw_restrict_score', 'whipsaw_cooldown_score', 'max_lots_per_side', 'max_total_exposure', 'trailing_stop_pct', 'premium_buffer_pct', 'close_at_atm', 'itm_guard_enabled'],
  },
  expiry: {
    title: 'Close-at-Expiry',
    color: '#f44336',
    blurb: 'End-of-life behavior: when to stop adjusting, auto-close, and profit-lock thresholds.',
    params: ['auto_close_mins', 'stop_adjustment_mins', 'close_at_threshold', 'theta_acceleration_window'],
  },
  adaptive: {
    title: 'Adaptive Interval',
    color: '#00bcd4',
    blurb: 'Automatically shortens heartbeat interval as expiry nears. More checks when theta accelerates.',
    params: ['adaptive_interval_enabled'],
  },
  windDown: {
    title: 'Wind-Down Mode',
    color: '#9c27b0',
    blurb: 'Near-expiry risk reduction: buys back positions (LIFO) instead of adding new naked lots.',
    params: ['session_window_hours', 'wind_down_on_atm', 'wind_down_enabled', 'wind_down_hours_before_expiry', 'wind_down_buyback_pct', 'wind_down_close_threshold', 'wind_down_min_lots_to_keep', 'wind_down_floor_action'],
  },
  marginGuardian: {
    title: '🛡️ Margin Guardian',
    color: '#e91e63',
    blurb: 'Real-time margin monitoring — auto-defends when margin utilization crosses thresholds: blocks new sells (Yellow), forces buybacks (Orange), emergency closes (Red), survival shutdown (Critical).',
    params: ['margin_monitor_enabled', 'margin_green_pct', 'margin_yellow_pct', 'margin_orange_pct', 'margin_red_pct', 'margin_critical_pct', 'margin_target_pct'],
  },
  regimeControls: {
    title: 'Regime Controls',
    color: '#ff5722',
    blurb: 'Pre-adjustment intelligence: detects dangerous market conditions (vol spikes, gamma explosion, strong trends) and blocks exposure-increasing trades. Risk-reducing trades always proceed.',
    params: [
      'regime_enabled',
      'vol_regime_enabled', 'vol_iv_spike_pct', 'vol_rv_threshold',
      'vol_lookback_beats', 'vol_rv_window', 'vol_regime_action',
      'vol_regime_cooldown_beats',
      'gamma_cap_enabled', 'gamma_soft_limit', 'gamma_hard_limit',
      'gamma_emergency_limit', 'gamma_near_expiry_multiplier',
      'trend_enabled', 'trend_tier1_pct', 'trend_tier2_pct',
      'trend_tier3_pct', 'trend_tier4_pct', 'trend_tier1_lot_reduction',
      'trend_retrace_pct', 'trend_ema_period', 'trend_ema_slope_threshold',
      'trend_action', 'trend_reset_beats',
      'trend_plateau_reset_beats', 'trend_t4_timeout_beats',
      'trend_acceleration_window_s', 'trend_acceleration_pct',
      'trend_boost_enabled', 'trend_boost_tier1_mult',
      'trend_boost_tier2_mult', 'trend_boost_tier3_mult',
    ],
  },
  perpHedge: {
    title: '⚡ Perp Delta Hedge',
    color: '#00bcd4',
    blurb: 'Perpetual futures delta hedging: trades BTCUSD perp to neutralize portfolio delta (CE + PE combined). "Full" hedges every heartbeat. "ATM Only" activates perp ONLY when the ORIGINAL entry strike approaches ATM — lets OTM theta profits run undisturbed.',
    params: [
      'perp_hedge_enabled',
      'perp_hedge_mode',
      'perp_hedge_atm_threshold_pct',
      'perp_hedge_delta_threshold',
      'perp_hedge_ratio',
      'perp_hedge_rebalance_band',
      'perp_hedge_max_lots',
      'perp_hedge_cooldown_sec',
      'perp_hedge_max_flips_per_hour',
    ],
  },
  positionLifecycle: {
    title: '🌾 Position Lifecycle',
    color: '#4caf50',
    blurb: 'M1 Profit Harvesting, M2 Lot Recycling, and Split Ledger Shift-Time Recycle: proactively close profitable frozen positions, restructure when capped, and optionally clean up cheap frozen lots at every strike shift.',
    params: [
      'harvest_enabled',
      'harvest_profit_pct', 'harvest_min_age_mins',
      'harvest_pressure_threshold', 'harvest_max_per_beat',
      'recycle_enabled',
      'recycle_premium_ceiling', 'recycle_min_premium_ratio',
      'recycle_max_pct', 'recycle_free_lot_buffer',
      'recycle_min_lot_gain', 'recycle_cooldown_sec',
      'recycle_protect_original',
      'shift_recycle_enabled',
      'shift_recycle_premium_floor', 'shift_recycle_floor_ratio',
      'shift_recycle_max_pct',
      'shift_recycle_pressure_threshold',
    ],
  },
  balanceControl: {
    title: '⚖️ Balance Control',
    color: '#ff9800',
    blurb: 'M3 Asymmetry Rebalancing: automatically relaxes harvest thresholds on the dominant side when CE/PE lot counts are severely skewed, preventing the one-sided accumulation death spiral.',
    params: [
      'rebalance_enabled',
      'rebalance_asymmetry_threshold',
      'rebalance_pressure_threshold',
    ],
  },
  favorableScaleUp: {
    title: '\uD83D\uDCC8 Favorable Scale-Up',
    color: '#8bc34a',
    blurb: 'When both CE and PE premiums are decaying (market is flat), automatically open new OTM option positions to capture additional theta. Positions become standard MMM positions with full protection.',
    params: [
      'scale_enabled',
      'scale_min_decay_pct', 'scale_lots_pct',
      'scale_max_events', 'scale_cooldown_mins',
      'scale_target_premium', 'scale_min_premium',
    ],
  },
  autoReplenish: {
    title: '\uD83D\uDD04 Auto-Replenish Leg',
    color: '#26a69a',
    blurb: 'When one side (CE or PE) reaches 0 positions while the other still has open lots, automatically sell a new leg on the empty side instead of pausing. Keeps the straddle/strangle hedged at all times.',
    params: [
      'replenish_enabled',
      'replenish_lot_mode',
      'replenish_max_per_session',
      'replenish_cooldown_sec',
      'replenish_min_premium',
    ],
  },
  atmShield: {
    title: '\uD83D\uDEE1\uFE0F ATM Shield \u2014 Close & Retreat',
    color: '#e91e63',
    blurb: 'Pre-emptively closes endangered positions approaching ATM and repositions at a safer OTM strike. Full position shift (original lots) + loss recovery. Overrides Trend Guard at T1/T2 when active.',
    params: [
      'atm_shield_enabled',
      'atm_shield_proximity_pct', 'atm_shield_target_otm_pct',
      'atm_shield_loss_split_aggressor',
      'atm_shield_max_per_session', 'atm_shield_cooldown_mins',
      'atm_shield_partial_pct', 'atm_shield_defer_resell_beats',
    ],
  },
  adaptiveTuning: {
    title: '\u2699\uFE0F Adaptive Tuning',
    color: '#00bcd4',
    blurb: 'Automatic parameter optimization per market regime. Manual: you control every param. Preset: loads recommended values for your strategy type in one click. Adaptive: auto-tunes ATM Shield proximity, cooldown, and hedge buffer based on live volatility, trend, and whipsaw signals.',
    sections: [
      {
        header: 'Mode',
        params: ['adaptive_mode', 'adaptive_preset', 'adaptive_dry_run'],
      },
    ],
  },
  lotVelocity: {
    title: '🚦 Lot Velocity Limiter',
    color: '#ff9800',
    blurb: 'Caps how many lots can be sold within a rolling time window. Prevents runaway accumulation during fast markets. When the limit is hit, all adjustments are blocked until the window rolls forward.',
    params: [
      'lot_velocity_enabled',
      'lot_velocity_limit',
      'lot_velocity_window_mins',
    ],
  },
  consecutiveDir: {
    title: '↕️ Consecutive Direction Limiter',
    color: '#ef5350',
    blurb: 'Prevents runaway selling in one direction. After N consecutive same-direction adjustments the algo caps lot size; after M it blocks entirely. The block auto-clears after a configurable timeout — no manual force-heartbeat needed.',
    params: [
      'consecutive_dir_limit',
      'consecutive_dir_lot_cap_pct',
      'consecutive_dir_block_after',
      'consecutive_dir_auto_resume_mins',
    ],
  },
  closeAt5Watcher: {
    title: '⚡ Close-at-5 Watcher',
    color: '#4caf50',
    blurb: 'Proactive scanner that polls bid prices and forces a heartbeat when any position hits the close-at-5 threshold. Default: activates only in the last 3 hours before expiry to save API resources. Force-enable it anytime via the toggle.',
    params: [
      'close_at_watcher_force_enabled',
      'close_at_watch_hours_before_expiry',
      'close_at_watch_near_expiry_interval',
      'close_at_watch_interval',
      'close_at_max_per_beat',
    ],
  },
  breakevenEngine: {
    title: '🎯 Breakeven Engine',
    color: '#1565c0',
    blurb: 'Real-time portfolio breakeven awareness. Calculates the BTC spot prices where your total portfolio becomes unprofitable and boosts hedge lot counts as spot approaches those boundaries. Uses intrinsic-only P&L (no live premium fetches) for fast, reliable calculation.',
    sections: [
      {
        header: null, // No header for the enable toggle
        params: ['breakeven_control_enabled'],
      },
      {
        header: 'Zone Thresholds (% distance from spot to nearest breakeven)',
        params: ['breakeven_warning_pct', 'breakeven_danger_pct', 'breakeven_critical_pct'],
      },
      {
        header: 'Aggression',
        params: ['breakeven_aggression_max', 'max_combined_lot_multiplier'],
      },
      {
        header: 'Diagnostics',
        params: ['breakeven_narrow_band_threshold'],
      },
      {
        header: 'Advanced',
        params: ['breakeven_scan_range_pct'],
      },
      {
        header: 'DTE-Aware Threshold Scaling',
        params: ['breakeven_dte_threshold_mult'],
      },
      {
        header: 'DTE Aggression Controls',
        params: ['breakeven_dte_aggression_damp', 'breakeven_dte_vol_regime_damp', 'breakeven_high_risk_mode'],
      },
      {
        header: 'DTE Safety Limits',
        params: ['breakeven_dte_pnl_clamp_pct', 'breakeven_critical_lot_ceiling'],
      },
    ],
  },
  gammaDetector: {
    title: '📐 Gamma Detector',
    color: '#6a1b9a',
    blurb: 'P&L curvature scanner. Detects kinks in the portfolio P&L curve at option strikes — these kinks are gamma boundaries where hedging urgency spikes. Warns before spot reaches a breakeven boundary. Observation-only by default; Phase 9 enables lot multiplier modulation.',
    sections: [
      {
        header: null,
        params: ['gamma_detector_enabled'],
      },
      {
        header: 'Scan Parameters',
        params: ['gamma_step_pct', 'gamma_scan_steps'],
      },
      {
        header: 'Zone Thresholds (% distance from spot to nearest gamma boundary)',
        params: ['gamma_warning_distance_pct', 'gamma_danger_distance_pct'],
      },
      {
        header: 'Detection Sensitivity',
        params: ['gamma_detect_epsilon'],
      },
      {
        header: 'Advanced — Phase 9 Gate (requires session restart)',
        params: ['gamma_severity_multiplier_enabled'],
      },
    ],
  },
  reverseMode: {
    title: '🔄 Controlled Reverse Mode',
    color: '#e91e63',
    blurb: 'WARNING: Reverse mode suspends normal MMM hedge-sell logic. Instead, it sells the same aggressor side (directional premium harvesting). Strict CE→PE→CE alternating enforced. All safety infrastructure (max_loss, trailing stop, margin guardian, wind-down) continues running. Only activate when you understand the unhedged delta exposure.',
    sections: [
      {
        header: 'Master Switch',
        params: ['reverse_enabled'],
      },
      {
        header: 'Capacity',
        params: ['reverse_capacity_pct', 'reverse_num_slots', 'reverse_slot_size_override'],
      },
      {
        header: 'Execution Control',
        params: ['reverse_max_adjustments', 'reverse_mode_type', 'reverse_cooldown_mins'],
      },
      {
        header: 'Time Window',
        params: ['reverse_time_start', 'reverse_time_end', 'reverse_duration_mins'],
      },
      {
        header: 'Safety Limits',
        params: ['reverse_max_loss', 'reverse_close_at_threshold', 'reverse_unhedged_emergency_loss'],
      },
    ],
  },
};

// Rich tooltip text for each parameter (maps param name → detailed help)
const PARAM_TOOLTIPS = {
  initial_lots: 'Starting lots per side at entry. CE and PE each get this many lots. These "original" lots naturally hedge each other — when one side loses, the other gains. This is the safe foundation of the strategy.',
  adjustment_interval: HELP.heartbeat_interval || 'Seconds between heartbeat checks. Shorter = more responsive (catches fast moves) but more API calls and potential fees. Default 300 = 5 minutes.',
  max_loss_amount: HELP.max_loss || 'Absolute dollar hard stop. If your total P&L drops below this negative amount, ALL positions are immediately closed. Your last line of defense.',
  min_trigger_move: HELP.min_trigger_move || 'Minimum % premium must exceed trigger to fire adjustment.',
  min_trigger_dollar: 'Dollar floor trigger for active strike. Fires an adjustment if the active-strike USD loss (premium_excess × lots × 0.001 BTC) exceeds this amount — regardless of the % threshold. Catches dead-zone losses that accumulate below min_trigger_move at high lot counts. 0 = disabled (default). Example: 0.50 at 10 lots fires when premium rises ~$50.',
  min_frozen_trigger_dollar: 'Frozen position fallback trigger. Fires a hedge if the total USD loss across all frozen (old-strike) positions exceeds this amount when the active-strike trigger has NOT fired. Covers the blind spot where stranded positions bleed without triggering. 0 = disabled (default). Only runs after active trigger returns no action.',
  shift_threshold: HELP.shift_threshold || 'Minimum premium at the hedge strike to avoid a strike shift.',
  shift_threshold_pct: HELP.shift_threshold_pct || 'Dynamic shift threshold as % of entry premium.',
  shift_target_premium: 'Target premium when looking for a new strike after a shift. The algo picks the strike closest to this premium value. Higher = deeper OTM (safer but less premium). Lower = closer to ATM (more premium but riskier).',
  pre_sell_shift_enabled: 'Experimental: Before selling hedge lots at a cheap premium, shift to a better strike first. In an up-move, CE rises but PE drops — without this, the algo keeps selling PE at 60-80 when target is 100, causing lot imbalance. With this ON: if PE < shift_target_premium, find a closer-to-ATM PE strike at ~100 first, THEN sell fewer lots there. Falls back to current behavior if no better strike exists in the chain. Default OFF — enable to test.',
  shift_match_opposite_lots: 'Delta-neutral balance: when a strike shift opens a new position, sell AT LEAST as many lots as the opposite side has active. Example: PE has 11 lots, CE shifts → CE opens 11 lots too (not just 4). Prevents directional bias from lot asymmetry. Trend-tier lot reduction is applied proportionally so risk controls are respected. Recommended: ON.',
  max_adjustments: HELP.max_adjustments || 'Maximum number of adjustments before the algo stops and alerts you.',
  cooldown_on_reversal: HELP.cooldown || 'After a reversal is detected, skip one heartbeat interval before adjusting. Filters out false reversals from short price spikes.',
  whipsaw_window_mins: 'Rolling window (minutes) for counting alternating adjustments. Only alternations within this window contribute to the whipsaw score. Default 30.',
  whipsaw_spot_move_pct: 'If BTC spot moved more than this % between two alternating adjustments, treat it as justified (not whipsaw noise). Default 0.3%.',
  whipsaw_caution_score: 'Whipsaw score threshold for CAUTION level: triggers widened +50%. Default 2.',
  whipsaw_restrict_score: 'Whipsaw score threshold for RESTRICT level: triggers widened +100%, lots halved. Default 3.',
  whipsaw_cooldown_score: 'Whipsaw score threshold for COOLDOWN: skip one interval, then score drops by 2. Default 4.',
  max_lots_per_side: HELP.position_cap || 'Maximum total lots allowed per side (CE or PE). With Split Ledger, only ACTIVE lots count against this cap — frozen (shifted) lots do not. Prevents runaway accumulation of productive adjustments.',
  max_total_exposure: 'Split Ledger: Absolute ceiling on active + frozen lots per side. 0 = auto (2× max_lots_per_side). A safety net for the safety net — prevents runaway total exposure even if frozen lots don\'t block the active cap. Fires "Total exposure ceiling" error which does NOT trigger M2 recycling.',
  trailing_stop_pct: HELP.trailing_profit || 'Once P&L hits a peak, if it drops more than this % from that peak, the algo alerts you. Protects profits from giving back too much.',
  premium_buffer_pct: 'Extra lots percentage for slippage protection. When calculating how many lots to sell, add this % extra to account for price movement between quote and fill. 0.05 = 5% buffer.',
  close_at_atm: 'Auto-close ALL positions if the original strike becomes at-the-money (spot price ≈ strike price). This is dangerous territory — ATM options have maximum gamma and can move violently.',
  itm_guard_enabled: 'When ON (default): blocks selling ITM options for adjustment — safe, prevents selling worthless contracts. When OFF: allows the algo to sell ITM options. Useful in the last 2-3 hours before expiry when strikes may briefly go ITM but you still want the algo to adjust. ⚠️ Turn OFF only when you understand the risk.',
  auto_close_mins: 'Auto-close ALL positions N minutes before expiry. This is the absolute final safety net. Default 5 = close everything 5 minutes before expiry, regardless of P&L.',
  stop_adjustment_mins: HELP.near_expiry || 'Stop making new adjustments N minutes before expiry. Let theta decay do the final work instead of adding risky late adjustments.',
  close_at_threshold: HELP.close_at_5 || 'Close any position whose premium drops to this level or below. Default 5 = when an option is worth $5 or less, buy it back to lock in ~95% profit.',
  close_at_watcher_force_enabled: 'Force the close-at-5 watcher ON regardless of expiry timing. Useful when you want fast close detection early in the session. The watcher polls every close_at_watch_interval seconds when force-enabled.',
  close_at_watch_hours_before_expiry: 'Watcher auto-activates when this many hours remain until expiry. Default 3 = watcher turns on in last 3 hours automatically. Set to 0 to always run (old behavior — wastes API calls).',
  close_at_watch_near_expiry_interval: 'Polling interval (seconds) when the watcher is auto-activated by the expiry window. Use a smaller value for 0DTE — faster detection in the last few hours. Default 10s. Must be ≥ 5.',
  close_at_watch_interval: 'Polling interval (seconds) when watcher is force-enabled. Default 30s. Set to 0 to disable force-enabled mode entirely.',
  close_at_max_per_beat: 'Maximum positions to close per heartbeat. Prevents the heartbeat from stalling when many positions hit threshold simultaneously (near expiry). Default 3. Increase to 10 near expiry if needed.',
  close_at_use_bid: 'Use bid price (not mark price) to detect when a position is eligible for close-at-5. Bid is more accurate for illiquid options — mark price can be much higher than what you actually get. Always leave ON.',
  theta_acceleration_window: 'Minutes before expiry to activate theta acceleration. Within this window, the algo widens trigger thresholds (allows more premium move before adjusting) because time decay is rapidly working in your favor.',
  adaptive_interval_enabled: HELP.adaptive_interval_enabled || 'Auto-scale heartbeat frequency based on time-to-expiry.',
  session_window_hours: 'Short Window: session auto-exits after N hours from start. 0 = disabled (runs until expiry). When set, wind-down and stop-adjustment timers count down from the session deadline, not the chain expiry. Ideal for evening sessions where you want to exit before India close (5:30 PM IST).',
  wind_down_on_atm: 'Auto-trigger wind-down mode if any original strike becomes ATM (spot ≈ strike). Instead of closing all positions immediately (like close_at_atm), this switches the algo into gradual LIFO buyback mode. The original strike is the entry strike — real danger territory. Activates once and stays active for the rest of the session.',
  wind_down_enabled: HELP.wind_down_enabled || 'Enable wind-down mode near expiry.',
  wind_down_hours_before_expiry: HELP.wind_down_hours_before_expiry || 'Hours before expiry to activate wind-down.',
  wind_down_buyback_pct: HELP.wind_down_buyback_pct || 'Fraction of lots to buy back per trigger during wind-down.',
  wind_down_close_threshold: HELP.wind_down_close_threshold || 'Elevated close threshold during wind-down.',
  wind_down_min_lots_to_keep: HELP.wind_down_min_lots_to_keep || 'Minimum lots to keep per side during wind-down.',
  wind_down_floor_action: HELP.wind_down_floor_action || 'Action when at minimum lots during wind-down.',
  // Margin Guardian tooltips
  margin_monitor_enabled: 'Master switch for real-time margin monitoring. When ON, the heartbeat checks your exchange margin utilization and auto-defends when thresholds are crossed. When OFF, no margin checks are made.',
  margin_green_pct: 'Below this % = GREEN tier — completely normal operation, no intervention. This is the safe zone. Default: 50%.',
  margin_yellow_pct: 'At this % = YELLOW tier — caution mode. The algo blocks new sell orders but keeps existing positions. Think of it as a soft defense. Default: 60%.',
  margin_orange_pct: 'At this % = ORANGE tier — aggressive buyback mode. Forces position reduction (wind-down) regardless of time-to-expiry. Sells are also blocked. Default: 75%.',
  margin_red_pct: 'At this % = RED tier — emergency mode. Closes ALL positions using taker (IOC) orders for fastest fills. This is the fire alarm. Default: 85%.',
  margin_critical_pct: 'At this % = CRITICAL tier — survival mode. Closes ALL positions AND stops the session completely. Only manual restart possible. Default: 90%.',
  margin_target_pct: 'Target margin utilization to wind down to during ORANGE/RED reductions. The algo estimates how many lots to close to reach this level. Default: 50%.',
  // Regime Controls — Volatility Regime Filter
  regime_enabled: 'MASTER SWITCH for ALL regime controls (Vol Filter, Gamma Cap, Trend Guard). When OFF, regime data is still collected for observation but NO trades are blocked or forced. Turn ON only after validating regime data for a few days.',
  vol_regime_enabled: 'Master switch for the volatility regime filter. When enabled, monitors IV change rate and realized volatility to detect dangerous vol environments. Blocks new sells during spikes.',
  vol_iv_spike_pct: 'IV change % threshold. If implied volatility rises this much from the lookback point (e.g., 30%), the vol regime triggers. Higher = less sensitive. For BTC 0DTE, 30% is a good starting point.',
  vol_rv_threshold: 'Annualized realized volatility threshold. If RV exceeds this (e.g., 80%), it indicates a high-vol environment. Computed from spot prices already being fetched.',
  vol_lookback_beats: 'How many heartbeats to look back for the IV rate-of-change calculation. At 60s adaptive interval, 5 beats = 5-minute lookback.',
  vol_rv_window: 'Number of heartbeats for the realized volatility calculation window. More beats = smoother but slower to react. 20 beats at 60s = ~20 minute window.',
  vol_regime_action: 'What to do when vol regime triggers: "block_sells" (block new sell orders), "pause" (pause entire session), "wind_down" (activate wind-down to reduce positions).',
  vol_regime_cooldown_beats: 'After regime goes HIGH, it must stay below threshold for this many consecutive beats before returning to NORMAL. Prevents premature reset from brief IV dips.',
  // Regime Controls — Portfolio Gamma Cap
  gamma_cap_enabled: 'Master switch for portfolio gamma cap. Monitors total dollar gamma exposure and enforces soft/hard/emergency limits.',
  gamma_soft_limit: 'Dollar gamma soft limit (warning). When your portfolio $gamma exceeds this, you get a warning log but adjustments still proceed. Suggested: max_loss × 0.01.',
  gamma_hard_limit: 'Dollar gamma hard limit. ALL new sell orders are blocked when exceeded. Adjustments blocked but risk-reducing trades continue. Suggested: max_loss × 0.02.',
  gamma_emergency_limit: 'Dollar gamma emergency limit. Forces wind-down buybacks to reduce gamma below the hard limit. This is the "gamma knife" defense for 0DTE. Suggested: max_loss × 0.04.',
  gamma_near_expiry_multiplier: 'In the last 30 minutes before expiry, multiply all gamma limits by this factor (e.g., 0.5 = limits cut in half). Gamma explodes near ATM at expiry — tighter control needed.',
  // Regime Controls — Tiered Trend Detection Guard (4 tiers: Alert → Guard → Block → Wind-Down)
  trend_enabled: 'Master switch for the tiered trend detection guard. Detects directional BTC moves from session anchor and activates graduated defences across 4 tiers. Tier 1 (Alert) reduces lot size, Tier 2 (Guard) blocks dangerous-side sells, Tier 3 (Block) blocks ALL sells, Tier 4 (Wind-Down) auto-triggers wind-down. The most impactful regime control.',
  trend_tier1_pct: 'Tier 1 — ALERT threshold (% move from anchor). When BTC moves this % from session anchor AND EMA confirms drift (or acceleration detected), lot sizes are reduced by the lot-reduction factor. At BTC $100K, 0.5% ≈ $500. Requires EMA confirmation or fast-move bypass. Recommended: 0.3–0.7.',
  trend_tier2_pct: 'Tier 2 — GUARD threshold (% move from anchor). Blocks sells on the dangerous side only (CE sells blocked in up-trend, PE sells blocked in down-trend). Does NOT require EMA — fires on absolute move alone. At BTC $100K, 1.0% ≈ $1,000. Must be > Tier 1. Recommended: 0.8–1.2.',
  trend_tier3_pct: 'Tier 3 — BLOCK threshold (% move from anchor). Blocks ALL new sell orders on both sides. Serious defensive posture — only risk-reducing trades allowed. At BTC $100K, 1.5% ≈ $1,500. Must be > Tier 2. Recommended: 1.2–1.8.',
  trend_tier4_pct: 'Tier 4 — WIND-DOWN threshold (% move from anchor). Automatically triggers wind-down without operator confirmation. This is the emergency brake — the algo will actively buy back positions. At BTC $100K, 2.0% ≈ $2,000. Must be > Tier 3. Recommended: 1.8–2.5.',
  trend_tier1_lot_reduction: 'Lot reduction factor at Tier 1 (Alert). When trend hits Tier 1, new sell lots are reduced by this fraction. E.g., 0.30 = 30% reduction (sell 70% of normal lots). Helps you slow down exposure growth before blocking. Range: 0.10–0.90. Recommended: 0.25–0.40.',
  trend_retrace_pct: 'Retracement required for tier reset (fraction, not %). Spot must retrace this fraction of the trend move before the guard can reset. E.g., 0.30 = 30% of move. If BTC moved $2,000 up, needs $600 pullback. Also requires calm beats. Crossing the anchor always resets immediately. Recommended: 0.25–0.40.',
  trend_ema_period: 'EMA (Exponential Moving Average) period in heartbeats for slope calculation. Used ONLY for Tier 1 entry confirmation — Tiers 2–4 fire on absolute % move alone. Confirms sustained drift vs. a one-time spike. Higher = smoother/slower. Recommended: 12–25.',
  trend_ema_slope_threshold: 'EMA slope threshold for Tier 1 confirmation. Higher = less sensitive. Only needed for Tier 1 entry — Tiers 2+ ignore EMA. A slope of 25 means ~0.25% per beat average drift — strong sustained move. Set higher to avoid false alerts. Recommended: 15–40.',
  trend_action: 'What to do at Tier 2 (Guard): "block_sells" = block dangerous-side sells only (smart directional blocking), "pause" = pause entire session, "wind_down" = activate wind-down on dangerous side. Note: Tier 3 always blocks all sells, Tier 4 always auto-triggers wind-down regardless of this setting.',
  trend_reset_beats: 'After retracement and EMA slope calm down, must stay calm for this many consecutive heartbeats before resetting ALL tiers back to Tier 0 (Normal). Prevents whipsaw on/off. Binary reset — all tiers clear at once. Recommended: 3–8.',
  trend_plateau_reset_beats: 'At Tier 2–3: if the market plateaued at the new level (no retracement) but the raw tier has fallen below the locked tier AND EMA is flat, reset after this many calm beats. Prevents stale T2/T3 locks when price stabilises mid-range. Does NOT apply at Tier 4 — use trend_t4_timeout_beats for that. Default: 5.',
  trend_t4_timeout_beats: 'At Tier 4 (Wind-Down): after this many consecutive beats of flat EMA slope, the anchor slides to the current price and the T4 lock is cleared. The standard plateau path cannot fire at T4 because the frozen anchor keeps the price distance above the T4 threshold forever. This is the dedicated unlock. Applies only when the market has genuinely stopped moving (EMA must be flat the entire time). Default: 20 (~20 min at 60s interval).',
  trend_acceleration_window_s: 'Acceleration detection window in seconds. Looks at BTC spot price history within this window to detect fast moves. If price moved more than acceleration_pct within this window, Tier 1 can fire WITHOUT EMA confirmation (fast-move bypass). Recommended: 300–900.',
  trend_acceleration_pct: 'Acceleration threshold (% move within window). If BTC moves this % within the acceleration window, it triggers a "fast move" bypass — Tier 1 activates without waiting for EMA confirmation. Catches sudden spikes that EMA is too slow to detect. At BTC $100K, 0.5% ≈ $500. Recommended: 0.3–0.7.',
  trend_boost_enabled: 'Trend Boost: When a directional trend is confirmed, BOOST lot size on the safe/hedge side instead of blocking it. In an uptrend, PE is far OTM and safe to sell aggressively — collect more premium while the trend confirms your safety. In a downtrend, CE is safe. At Tier 3 (BLOCK), instead of blocking ALL sells, only the dangerous side is blocked while the safe side gets boosted lots. Existing safety guards (position cap, margin guardian, asymmetry) still apply.',
  trend_boost_tier1_mult: 'Safe-side lot multiplier at Tier 1 (Alert). E.g., 1.3 = sell 30% MORE lots on the safe side. In an uptrend, PE is the safe side. In a downtrend, CE is the safe side. Recommended: 1.2–1.5.',
  trend_boost_tier2_mult: 'Safe-side lot multiplier at Tier 2 (Guard). E.g., 1.5 = sell 50% MORE lots on the safe side. The stronger the trend, the further OTM the safe side is — more aggressive selling is justified. Recommended: 1.3–2.0.',
  trend_boost_tier3_mult: 'Safe-side lot multiplier at Tier 3 (Block). E.g., 2.0 = DOUBLE the lots on the safe side. At this tier, the dangerous side is fully blocked, so all premium collection depends on the safe side. This is the biggest win — collecting rich IV premium while the trend confirms your safety. Recommended: 1.5–2.5.',
  // Perp Delta Hedge tooltips
  perp_hedge_enabled: 'Master switch for perpetual futures delta hedging. When enabled, the algo trades BTCUSD perpetual each heartbeat to neutralize portfolio delta. When disabled, no perp trades are made but existing positions remain.',
  perp_hedge_mode: 'Hedge activation mode. "Full" = hedge entire portfolio delta (CE + PE combined) every heartbeat to make you delta-neutral. "ATM Only" = perp activates ONLY when an ORIGINAL entry strike is within the ATM threshold % of spot — OTM positions keep profiting from theta decay undisturbed. Recommended: ATM Only for 0DTE.',
  perp_hedge_atm_threshold_pct: 'ATM proximity threshold (%). In ATM Only mode, the perp hedge activates only when the ORIGINAL entry strike (the strike at session start, not shifted strikes) is within this % of spot. E.g., 1.5% at BTC $63,000 means perp activates if original strike is between $62,055 and $63,945. Lower = more selective.',
  perp_hedge_delta_threshold: 'Minimum absolute portfolio delta before hedging triggers. E.g., 0.02 = don\'t hedge until delta exceeds 2%. Prevents micro-adjustments on balanced portfolios.',
  perp_hedge_ratio: 'Fraction of portfolio delta to hedge. 1.0 = full neutralization (target delta zero). 0.5 = hedge only half the delta. Use < 1.0 if you want partial directional exposure.',
  perp_hedge_rebalance_band: 'Dead zone around target position. If current lots are within this band of target, skip the trade. Prevents tiny round-trip adjustments. E.g., 0.005 = 0.5% band.',
  perp_hedge_max_lots: 'Maximum perp position size in lots (1 lot = 0.001 BTC). Caps total hedge exposure. E.g., 50 lots = 0.05 BTC max perp position.',
  perp_hedge_cooldown_sec: 'Minimum seconds between consecutive hedge executions. Prevents rapid-fire trading during volatile periods. Default: 30 seconds.',
  perp_hedge_max_flips_per_hour: 'Maximum perp direction flips (long→short or short→long) per hour. Prevents spread drag from rapid flip-flopping in choppy markets. Default: 6.',
  // M1: Profit Harvesting
  harvest_enabled: 'M1: Enable proactive profit harvesting. Each heartbeat, frozen positions that have decayed by at least harvest_profit_pct are automatically bought back, freeing lot capacity for future adjustments.',
  harvest_profit_pct: 'M1: Minimum profit percentage to harvest a frozen position. E.g., 40 means the option must be worth ≤ 60% of entry price (40%+ profit locked). Higher = more selective, fewer buybacks.',
  harvest_min_age_mins: 'M1: Minimum age in minutes before a position can be harvested. Prevents harvesting freshly-frozen positions that may still be within normal bid-ask spread movement.',
  harvest_pressure_threshold: 'M1: Minimum capacity pressure (total_lots / max_lots) to start harvesting. 0.6 = only harvest when above 60% capacity. Prevents unnecessary buybacks when lots are plentiful.',
  harvest_max_per_beat: 'M1: Maximum frozen positions to close per heartbeat. Limits API calls and potential slippage in a single pass. Eligible positions beyond this limit are deferred to the next heartbeat.',
  // M2: Lot Recycling
  recycle_enabled: 'M2: Enable emergency lot recycling when max lots blocks an adjustment. Phase A buys back cheap frozen positions; Phase B sells fewer lots at an ATM-closer strike to cover both costs.',
  recycle_premium_ceiling: 'M2: Maximum current premium (USD) for a position to be considered recyclable. Only deeply decayed options worth ≤ this amount are eligible for buyback during recycling.',
  recycle_min_premium_ratio: 'M2: Minimum ratio of new_strike_premium ÷ avg_recycle_premium. Ensures Phase B collects at least 2.5× the buyback cost. Below this ratio, recycling is not economical — algo stays blocked.',
  recycle_max_pct: 'M2: Maximum fraction of side lots to recycle in a single operation. 0.5 = never recycle more than 50% of side positions in one pass. Prevents over-restructuring.',
  recycle_free_lot_buffer: 'M2: Extra lots to free beyond the immediate adjustment need. Frees headroom so the next heartbeat can adjust normally without triggering another recycle immediately.',
  recycle_min_lot_gain: 'M2: Minimum net lots freed (recycled − new lots sold) for recycling to proceed. Ensures each operation meaningfully improves capacity, not just a break-even shuffle.',
  recycle_cooldown_sec: 'M2: Cooldown in seconds between consecutive recycle operations. Prevents rapid repeated restructuring in choppy markets where every heartbeat hits the cap.',
  recycle_protect_original: 'M2: Never recycle the original entry position. The original lots are your core anchor — recycling them would fundamentally change the strategy setup.',
  // Split Ledger Phase 2 — Shift-Time Recycle
  shift_recycle_enabled: 'Split Ledger Phase 2: At each strike shift, the algo closes cheap frozen positions BEFORE selling the new strike lots. Buyback cost is folded into the new sell calculation so net coverage is the same. Disabled by default — enable after observing Phase 1 for 1 week.',
  shift_recycle_premium_floor: 'Shift-Time Recycle: Only close frozen positions with live premium BELOW this amount. 0 = use dynamic floor (shift_recycle_floor_ratio × new_strike_premium). Default 60 = close frozen positions worth $60 or less. Higher = more aggressive cleanup.',
  shift_recycle_floor_ratio: 'Shift-Time Recycle dynamic floor: when shift_recycle_premium_floor is 0, compute floor as this fraction × new_strike_premium. 0.40 = close frozen if it costs less than 40% of the new strike. Auto-adapts to current market premium levels.',
  shift_recycle_max_pct: 'Shift-Time Recycle: max fraction of total frozen lots to close per shift. 1.0 = all eligible lots. 0.5 = at most 50% of frozen lots per shift. Prevents liquidating too many positions at once.',
  shift_recycle_pressure_threshold: 'Shift-Time Recycle: minimum capacity pressure (total_lots / max_lots_per_side) required before recycle runs. 0.7 = only recycle when 70%+ full. 0.0 = always run (not recommended — closes winning positions unnecessarily and wastes fees).',
  // M3: Asymmetry Rebalancing
  rebalance_enabled: 'M3: Enable asymmetry-aware harvest threshold relaxation. When one side accumulates many more lots than the other, the harvest thresholds on the dominant side are automatically relaxed to free capacity faster.',
  rebalance_asymmetry_threshold: 'M3: CE/PE lot ratio that triggers relaxed harvesting on the dominant side. Default 5.0 = relax when one side has 5× more lots than the other. Lower = more aggressive rebalancing.',
  rebalance_pressure_threshold: 'M3: Minimum capacity pressure on the dominant side (combined with asymmetry ratio) to activate M3. Prevents threshold relaxation when lots are still plentiful on the dominant side.',
  // Auto-Replenish Leg
  replenish_enabled: 'Master switch for Auto-Replenish. When one side closes to 0 lots while the other still has positions, automatically sell a new leg on the empty side instead of pausing the session. OFF by default \u2014 turn on when ready.',
  replenish_lot_mode: 'How many lots to sell on the empty side. match_active = match the open side\'s active lot count. initial = use the session\'s initial_lots parameter. Default: match_active.',
  replenish_max_per_session: 'Maximum number of replenishments per session. Prevents infinite re-entry loops if positions keep getting closed. Default: 3.',
  replenish_cooldown_sec: 'Minimum seconds between replenishments. Prevents rapid re-entry if the replenished position gets closed again quickly. Default: 300 (5 minutes).',
  replenish_min_premium: 'Minimum premium ($) for the replenish strike. Strikes below this are rejected \u2014 too little theta to justify entering. Default: $30.',
  // FSU: Favorable Scale-Up
  scale_enabled: 'Master switch for Favorable Scale-Up (FSU). When enabled and both premiums have decayed significantly, the algo opens new positions at fresh OTM strikes. Positions become standard MMM positions \u2014 included in adjustments, loss calculations, close-at-5, etc. Disabled by default.',
  scale_min_decay_pct: 'Both CE and PE premiums must have decayed by at least this percentage from the trigger snapshot before a scale-up event fires. Higher = more conservative. Default 35% means premiums must have dropped by a third.',
  scale_lots_pct: 'Lots per side as a percentage of initial_lots. With initial_lots=10 and scale_lots_pct=50, each scale-up sells 5 lots CE + 5 lots PE. Lower = more conservative. Default 50%.',
  scale_max_events: 'Maximum number of scale-up events per session. After this many, no more scale-ups occur. Default 3.',
  scale_cooldown_mins: 'Minimum minutes between consecutive scale-up events. Prevents rapid stacking even when conditions remain favorable. Default 30 minutes.',
  scale_target_premium: 'Target premium when scanning for new OTM strikes. The algo picks the OTM strike with premium closest to this value. Higher = further OTM (safer, less theta). Default $100.',
  scale_min_premium: 'Minimum premium threshold for scale-up strikes. Strikes below this premium are rejected \u2014 too little theta to justify the risk. Default $30.',
  // Adaptive Tuning
  adaptive_mode: 'Parameter tuning mode. Manual: you set every param — current behavior, nothing changes. Preset: pick a strategy profile (Strangle/Straddle/Short Window) and all adaptive params load with optimized values in one click — you can still override any value after. Adaptive: starts from preset values then auto-tunes ATM Shield proximity, cooldown, and hedge buffer every heartbeat based on live vol/trend/whipsaw signals.',
  adaptive_preset: 'Strategy profile loaded in Preset or Adaptive mode. Strangle = standard OTM positions (wider proximity, longer cooldown). Straddle = near-ATM (tight proximity, full-close always). Short Window = 3–5 hour sessions (faster cooldown, farther retreat).',
  adaptive_dry_run: 'Shadow mode: the adaptive engine computes what it would change but only logs — does not write to params. Use to validate adaptive behavior over 2–3 live sessions before enabling live tuning. Watch the activity log for param_adapted entries.',
  atm_shield_partial_pct: 'Fraction of active positions to close when shield fires. 1.0 = close all (default). 0.5 = close only half the positions (closest to ATM first). Partial mode is useful in oscillating/ranging markets — avoids crystallizing the full loss if price reverses. Has no effect when there is only 1 active position per side.',
  atm_shield_defer_resell_beats: 'Beats to wait after the close before re-selling at the new OTM strike. 0 = re-sell immediately in the same beat (default). 1 = wait one heartbeat interval before opening the new position. Deferring lets volatility settle and often captures a better premium. The close is always immediate regardless of this setting.',
  // ATM Shield
  atm_shield_enabled: 'Master switch for ATM Shield. When enabled, the algo pre-emptively closes positions approaching ATM and repositions at a safer OTM strike. Original lots are fully shifted + additional lots for loss recovery. Overrides Trend Guard T1/T2 lot reduction. Recommended ON.',
  atm_shield_proximity_pct: 'Base % proximity from active strike that triggers the shield. Scaled by time-to-expiry (wider near expiry). At 6hr+: fires when spot is within 0.5% of strike. At 1hr: fires at 1.5%. Default 0.5%.',
  atm_shield_target_otm_pct: 'Base target % OTM for the retreat strike. Scaled by time-to-expiry and progressive widening (each successive fire retreats 50% farther). At 6hr+: first retreat to 1% OTM. Default 1.0%.',
  atm_shield_loss_split_aggressor: 'Fraction of buyback loss recovered from endangered-side re-sell. Remaining fraction from safe-side. 0.3 = 30% from CE (if CE retreated), 70% from PE. Default 0.3.',
  atm_shield_max_per_session: 'Maximum shield fires per side per session. After exhaustion, Trend Guard reverts to original behavior and close_at_ATM resumes. Default 3.',
  atm_shield_cooldown_mins: 'Minimum minutes between shield fires on the same side. Prevents rapid-fire whipsaw. Default 10 minutes.',
  // Lot Velocity Limiter
  lot_velocity_enabled: 'Master switch for the lot velocity limiter. When ON, the algo counts how many lots have been sold in the rolling window and blocks further adjustments once the limit is reached. When OFF, no velocity check is performed — the algo can sell unlimited lots in any time period.',
  lot_velocity_limit: 'Maximum lots that can be sold across both CE and PE sides within the rolling window. When this count is reached, adjustments are blocked until enough time passes that older sales fall outside the window. OPERATOR (manual) injections are excluded from the count. Default 30.',
  lot_velocity_window_mins: 'Rolling window in minutes for the velocity count. Lots sold more than this many minutes ago no longer count towards the limit. Smaller window = more responsive but allows short bursts. Default 30 minutes.',
  // Consecutive Direction Limiter
  consecutive_dir_limit: 'After this many consecutive same-direction adjustments (e.g. CE aggressor 3 times in a row), lot size is capped at consecutive_dir_lot_cap_pct × initial_lots. Prevents explosive accumulation during sustained trends. Default 3.',
  consecutive_dir_lot_cap_pct: 'Lot cap fraction applied once consecutive_dir_limit is reached. 0.25 = cap at 25% of initial_lots. Example: initial_lots=10 → max 2 lots per adjustment while the streak continues. Default 0.25.',
  consecutive_dir_block_after: 'After this many consecutive same-direction adjustments, all further adjustments in that direction are blocked until the auto-resume timeout elapses (or a manual force-heartbeat). The counter resets automatically when the direction changes. Default 5.',
  consecutive_dir_auto_resume_mins: 'Minutes before the consecutive-direction block auto-clears. After this timeout the counter resets and the algo resumes normally — no manual force-heartbeat needed. Set to 0 to require manual intervention (original behavior). Default 10.',
  // Breakeven Engine
  breakeven_control_enabled: 'Enable real-time breakeven band tracking and defensive aggression. When enabled, the algo calculates where spot would make the portfolio unprofitable and boosts hedging as spot approaches that boundary. Non-directional — applies to any triggered adjustment. Safe to enable: defaults to 1x (no change) until spot enters Warning zone.',
  breakeven_warning_pct: 'Distance from nearest breakeven (as % of spot) that triggers Warning zone. At 2% with BTC at $87k, Warning fires when spot is within ~$1,740 of breakeven. Multiplier ramps from 1.0× to 1.3×. Must be greater than Danger threshold.',
  breakeven_danger_pct: 'Distance from nearest breakeven that triggers Danger zone. Multiplier ramps from 1.3× to 2.0×. At $87k, 1% ≈ $870 buffer. Must be less than Warning and greater than Critical threshold.',
  breakeven_critical_pct: 'Distance from nearest breakeven that triggers Critical zone. Multiplier ramps from 2.0× to Max Multiplier. At $87k, 0.5% ≈ $435 — imminent breach. Must be less than Danger threshold.',
  breakeven_aggression_max: 'Maximum lot multiplier applied at the Critical zone boundary (distance ≤ critical_pct). A value of 3.0 means up to 3× normal hedge lots. Still capped by max_lots_per_side, max_total_exposure, and combined multiplier ceiling. Min 1.5.',
  max_combined_lot_multiplier: 'Caps the combined effect of ALL lot multipliers (gamma-aware × breakeven × trend boost). Prevents compound runaway. A value of 3.0 means the total multiplier never exceeds 3×, even if individual systems each want more. Applied after all individual multipliers, before position caps.',
  breakeven_narrow_band_threshold: 'Diagnostic threshold for narrow band warning. When the breakeven band width (upper − lower, as % of spot) falls below this, the UI displays an amber warning and an activity log is emitted. Does not trigger automatic responses — operator decides corrective action. Default 5% warns when both breakevens are within ~2.5% of spot.',
  breakeven_scan_range_pct: 'Minimum scan width from spot (% of spot). The engine auto-expands the range to cover all open strikes (120% of furthest strike distance). This parameter acts as a floor. Default 5% is sufficient for most sessions.',
  // Breakeven DTE-aware controls
  breakeven_dte_threshold_mult: 'DTE threshold widening multiplier. Uses √T scaling: dte_scale = 1 + (mult−1)×√(hours_remaining/total_hours). With mult=1.5, thresholds start 50% wider at session creation and decay back to standard at expiry. Default 1.0 = disabled (backward-compatible).',
  breakeven_dte_aggression_damp: 'Reduce lot boost amplitude in WARNING and DANGER zones by this fraction. 0.1 = 10% reduction (e.g. max WARNING goes from 1.3× to 1.27×). CRITICAL zone is always fully exempt — damp never applies there. Default 0.0 = no reduction.',
  breakeven_dte_vol_regime_damp: 'Auto-damp fraction applied during volatile regimes. ELEVATED vol: this×0.5. HIGH vol: this×1.0. Overrides the manual aggression_damp setting. With 0.2: ELEVATED = 10% damp, HIGH = 20% damp. Does not affect CRITICAL zone.',
  breakeven_high_risk_mode: 'Emergency override: set all aggression damps to 0 (maximum breakeven response). Intended for sessions where you manually determine that maximum lot boost is warranted. Auto-expires after 4 hours — set _high_risk_mode_expires_at in session to control duration.',
  breakeven_dte_pnl_clamp_pct: 'Safety clamp: if |pnl_at_spot| / total_premium_collected exceeds this ratio, dte_scale reverts to 1.0. Prevents dte_scale from keeping thresholds artificially wide when the position is already deeply in trouble. Requires ≥5 lots total to trigger (avoids false clamp on tiny positions). Default 1.5.',
  breakeven_critical_lot_ceiling: 'Combined multiplier ceiling specifically for CRITICAL zone. Replaces max_combined_lot_multiplier when zone=CRITICAL, allowing a higher ceiling during genuine emergencies. Default 4.0 (vs typical 3.0 combined cap). Still bounded by max_lots_per_side.',
  // Gamma Detector Engine
  gamma_detector_enabled: 'Enable real-time portfolio gamma boundary scanning. The detector computes the P&L curve from your open positions and finds BTC price levels where the curve kinks sharply — these are gamma boundaries where hedging urgency spikes. Observation-only by default (no lot changes) until gamma_severity_multiplier_enabled is turned on. Safe to enable: no trades are affected.',
  gamma_step_pct: 'Step size as % of BTC spot for the P&L curve scan. Smaller = finer resolution but more computation. 0.5% at BTC $87k ≈ $435 per step. Range: 0.1–5.0. Default 0.5%.',
  gamma_scan_steps: 'Steps to scan outward from spot in each direction. Total scan range = ±(gamma_step_pct × gamma_scan_steps). With defaults (0.5% × 40), range = ±20% of spot. More steps = wider view but slower. Range: 10–200. Default 40.',
  gamma_warning_distance_pct: 'Distance (% of spot) from nearest gamma boundary that triggers Warning zone. At 3% with BTC at $87k, Warning fires when spot is within ~$2,610 of a kink. Must be greater than Danger threshold. Default 3.0%.',
  gamma_danger_distance_pct: 'Distance (% of spot) from nearest gamma boundary that triggers Danger zone. At 1.5% with BTC at $87k, Danger fires when spot is within ~$1,305 of a kink. Must be less than Warning threshold. Default 1.5%.',
  gamma_detect_epsilon: 'Minimum absolute P&L second-difference (USD) to classify a point as a gamma boundary. Too low = noise triggers false kinks. Too high = misses real boundaries. At 0.3, a kink must cause a $0.30+ curvature change per step. Range: 0.01–50.0. Default 0.3.',
  gamma_severity_multiplier_enabled: 'Phase 9 gate — enables lot multiplier modulation from gamma severity scores. When ON, gamma boundary proximity boosts hedge lots directionally (toward the threatened side). The combined multiplier ceiling (max_combined_lot_multiplier) still applies. REQUIRES SESSION RESTART when toggled. Off by default until Phase 9 validation is complete.',
};

// =============================================================================
// Helper: Format parameter value for display
// =============================================================================

const formatValue = (value, type) => {
  if (value === null || value === undefined) return '';
  if (type === 'bool') return value;
  if (type === 'int') return Math.round(value);
  if (type === 'float') return parseFloat(value);
  return value;
};

// =============================================================================
// MMMSettingsDialog Component
// =============================================================================

// Parameters the adaptive engine can auto-tune (must match PARAM_LIMITS in mmm_adaptive.py)
const ADAPTIVE_ENGINE_PARAMS = new Set([
  'atm_shield_proximity_pct',
  'atm_shield_target_otm_pct',
  'atm_shield_cooldown_mins',
  'premium_buffer_pct',
]);

export default function MMMSettingsDialog({ open, onClose, sessionId, paramsInfo = {} }) {
  const [formValues, setFormValues] = useState({});
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);
  const [serverError, setServerError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [sessionData, setSessionData] = useState(null);
  const [search, setSearch] = useState('');

  // Adaptive tuning indicators — derived from live session state + form values
  const isAdaptiveActive = formValues.adaptive_mode === 'adaptive';
  const operatorLocked = new Set(sessionData?._adaptive_operator_overrides || []);

  // Pinned / Favorites — persisted to backend so they survive builds and cache clears
  const [pinned, setPinned] = useState(new Set());

  // Load pinned params from backend when dialog opens
  useEffect(() => {
    if (!open) return;
    fetch('/api/user/preferences')
      .then(r => r.json())
      .then(data => {
        const stored = data.pinned_params;
        if (Array.isArray(stored)) setPinned(new Set(stored));
      })
      .catch(() => {}); // silent — pinned is non-critical
  }, [open]);

  const togglePin = (paramName, e) => {
    e.stopPropagation();
    setPinned(prev => {
      const next = new Set(prev);
      if (next.has(paramName)) next.delete(paramName);
      else next.add(paramName);
      // Persist to backend (fire-and-forget)
      fetch('/api/user/preferences', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pinned_params: [...next] }),
      }).catch(() => {});
      return next;
    });
  };

  // Fetch session data when dialog opens
  useEffect(() => {
    if (!open || !sessionId) {
      setSessionData(null);
      setFormValues({});
      setErrors({});
      setSuccess(false);
      setServerError(null);
      return;
    }

    const fetchSessionData = async () => {
      setLoading(true);
      try {
        const result = await mmmService.getSession(sessionId);
        if (result.success && result.session) {
          setSessionData(result.session);
          // Merge backend defaults into session params so new params
          // (like shift_target_premium) show with default values
          // even for sessions created before the param existed
          const defaults = paramsInfo?.defaults || {};
          const sessionParams = result.session.params || {};
          setFormValues({ ...defaults, ...sessionParams });
        } else {
          setServerError('Failed to load session data');
        }
      } catch (error) {
        console.error('Failed to fetch session:', error);
        setServerError(error.message || 'Failed to load session');
      } finally {
        setLoading(false);
      }
    };

    fetchSessionData();
  }, [open, sessionId]);

  // Conflict rules: [condition, message]
  // Checked live as user edits — shown as warnings on conflicting params.
  const CONFLICTS = [
    {
      params: ['atm_shield_enabled', 'wind_down_on_atm'],
      check: (v) => v.atm_shield_enabled && v.wind_down_on_atm,
      message: 'ATM Shield and Wind-Down-on-ATM conflict. When ATM Shield is ON it handles all ATM approaches — Wind-Down-on-ATM will be automatically suppressed. Wind-down only activates as a last resort if no viable OTM strike is found. You do not need to enable both.',
      params_affected: ['wind_down_on_atm'],
    },
    {
      params: ['atm_shield_enabled', 'wind_down_enabled'],
      check: (v) => v.atm_shield_enabled && v.wind_down_enabled,
      message: 'ATM Shield and Wind-Down (manual) are both enabled. Wind-down will block ATM Shield re-sells, preventing position re-establishment. Disable Wind-Down while ATM Shield is active, or the shield will close positions but cannot re-open them.',
      params_affected: ['wind_down_enabled'],
    },
    {
      params: ['atm_shield_enabled', 'close_at_atm'],
      check: (v) => v.atm_shield_enabled && v.close_at_atm,
      message: 'ATM Shield and Close-at-ATM conflict. Both handle ATM approaches but differently: ATM Shield repositions (close + re-sell farther OTM), Close-at-ATM just closes. Enable only one. ATM Shield is preferred — it maintains premium collection capacity.',
      params_affected: ['close_at_atm'],
    },
    {
      params: ['pre_sell_shift_enabled', 'shift_match_opposite_lots'],
      check: (v) => v.pre_sell_shift_enabled && v.shift_match_opposite_lots,
      message: 'Pre-Sell Shift and Delta-Neutral Match conflict. Pre-Sell Shift aims to sell fewer lots at better premium. Delta-Neutral Match then inflates those lots to match the opposite side — cancelling the lot-reduction benefit. Disable shift_match_opposite_lots when using pre_sell_shift_enabled.',
      params_affected: ['shift_match_opposite_lots'],
    },
  ];

  const getConflictWarnings = (values) => {
    const warnings = {};
    for (const rule of CONFLICTS) {
      if (rule.check(values)) {
        for (const p of rule.params_affected) {
          warnings[p] = rule.message;
        }
      }
    }
    return warnings;
  };

  // Handle value change with validation
  const handleChange = (paramName, value, paramType) => {
    const params = paramsInfo?.params || {};
    const info = params[paramName] || {};

    // Type coercion
    let coercedValue = value;
    if (paramType === 'int') {
      coercedValue = value === '' ? '' : parseInt(value, 10);
    } else if (paramType === 'float') {
      coercedValue = value === '' ? '' : parseFloat(value);
    } else if (paramType === 'bool') {
      coercedValue = Boolean(value);
    }

    // Validation
    let error = null;
    if (coercedValue !== '' && !isNaN(coercedValue)) {
      if (info.min !== undefined && info.min !== null && coercedValue < info.min) {
        error = `Minimum: ${info.min}`;
      }
      if (info.max !== undefined && info.max !== null && coercedValue > info.max) {
        error = `Maximum: ${info.max}`;
      }
    }

    setFormValues((prev) => ({ ...prev, [paramName]: coercedValue }));
    setErrors((prev) => ({ ...prev, [paramName]: error }));
  };

  // Save changes
  const handleSave = async () => {
    // Check for validation errors
    const hasErrors = Object.values(errors).some((err) => err !== null);
    if (hasErrors) {
      setServerError('Please fix validation errors before saving');
      return;
    }

    // Check for setting conflicts
    const conflictWarnings = getConflictWarnings(formValues);
    if (Object.keys(conflictWarnings).length > 0) {
      setServerError('Conflicting settings detected (highlighted in yellow above). Please resolve conflicts before saving.');
      return;
    }

    if (!sessionData) {
      setServerError('Session data not loaded');
      return;
    }

    setSaving(true);
    setServerError(null);

    try {
      const currentParams = sessionData.params || {};
      const sessionStatus = (sessionData.strategy_status || sessionData.status || 'IDLE').toUpperCase();
      const isRunning = ['RUNNING', 'PAUSED', 'BOTH_SIDES_UP'].includes(sessionStatus);

      // Filter out unchanged params; when running, skip non-hot params to avoid 400
      // Also filter out internal params that aren't editable (not in paramsInfo.params)
      const changedParams = {};
      const hotParams = new Set(paramsInfo?.hot_reload_params || []);
      const editableParams = paramsInfo?.params || {};

      for (const [key, value] of Object.entries(formValues)) {
        // Skip internal params that aren't editable
        if (!editableParams[key]) {
          continue;
        }

        if (value !== currentParams[key]) {
          if (!isRunning || hotParams.has(key)) {
            changedParams[key] = value;
          }
        }
      }

      if (Object.keys(changedParams).length === 0) {
        setServerError('No changes detected');
        setSaving(false);
        return;
      }

      // Send update request
      await mmmService.updateSessionParams(sessionId, changedParams);

      setSuccess(true);
      setTimeout(() => {
        onClose(true); // true = params were updated
      }, 1000);

    } catch (error) {
      console.error('Failed to update params:', error);
      setServerError(error.response?.data?.error || error.message || 'Failed to update parameters');
    } finally {
      setSaving(false);
    }
  };

  // Render the (?) tooltip icon for a parameter
  const renderHelpIcon = (paramName) => {
    const tip = PARAM_TOOLTIPS[paramName];
    if (!tip) return null;
    return (
      <Tooltip
        title={
          <Typography variant="body2" sx={{ p: 0.5, lineHeight: 1.5, maxWidth: 360, fontSize: '0.78rem' }}>
            {tip}
          </Typography>
        }
        placement="top"
        arrow
      >
        <HelpIcon sx={{ fontSize: 14, color: 'text.disabled', opacity: 0.6, cursor: 'help', ml: 0.5, '&:hover': { opacity: 1, color: '#2196f3' } }} />
      </Tooltip>
    );
  };

  // Badge-style hot/lock + help icons
  const renderIcons = (isHot, paramName) => (
    <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center', flexShrink: 0 }}>
      <Tooltip title={pinned.has(paramName) ? 'Unpin from My Controls' : 'Pin to My Controls'} placement="top">
        <IconButton
          size="small"
          onClick={(e) => togglePin(paramName, e)}
          sx={{ p: '2px', color: pinned.has(paramName) ? '#ffd700' : '#4a5568', '&:hover': { color: '#ffd700', background: 'rgba(255,215,0,0.08)' }, transition: 'color 0.15s' }}
        >
          {pinned.has(paramName)
            ? <StarIcon sx={{ fontSize: 13 }} />
            : <StarBorderIcon sx={{ fontSize: 13 }} />}
        </IconButton>
      </Tooltip>
      <Box component="span" sx={{
        fontSize: '0.70rem', fontWeight: isHot ? 700 : 400, letterSpacing: '0.3px',
        background: isHot ? 'rgba(255,152,0,0.12)' : 'rgba(139,148,158,0.08)',
        border: '1px solid', borderColor: isHot ? 'rgba(255,152,0,0.3)' : 'rgba(139,148,158,0.18)',
        color: isHot ? '#ffa726' : '#6e7681',
        borderRadius: '4px', px: '4px', py: '1px', whiteSpace: 'nowrap',
      }}>
        {isHot ? '⚡ HOT' : '🔒'}
      </Box>
      {SEALED_PARAMS.has(paramName) && (
        <Box component="span" sx={{
          fontSize: '0.70rem', fontWeight: 700, letterSpacing: '0.3px',
          background: 'rgba(76,175,80,0.10)',
          border: '1px solid rgba(76,175,80,0.35)',
          color: '#66bb6a',
          borderRadius: '4px', px: '4px', py: '1px', whiteSpace: 'nowrap',
        }}>
          🔒 SEALED
        </Box>
      )}
      {renderHelpIcon(paramName)}
    </Box>
  );

  // Shared card and text styles (defined outside renderParam to avoid recreation)
  const cardSx = {
    background: '#1c2128',
    border: '1px solid #21262d',
    borderRadius: '8px',
    p: '10px 12px 8px',
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    gap: 1,
    transition: 'border-color 0.15s',
    '&:hover': { borderColor: 'rgba(56,139,253,0.25)' },
  };
  const descSx = { fontSize: '0.85rem', lineHeight: 1.45, color: '#eaf0f8' };
  const keySx  = { fontSize: '0.72rem', fontFamily: 'monospace', color: 'rgba(79,156,255,0.92)', display: 'block' };

  // Returns border/background override when adaptive engine is managing this param
  const getAdaptiveCardSx = (paramName) => {
    if (!isAdaptiveActive || !ADAPTIVE_ENGINE_PARAMS.has(paramName)) return {};
    if (operatorLocked.has(paramName)) {
      return { borderColor: 'rgba(255,152,0,0.5)', background: 'rgba(255,152,0,0.04)' };
    }
    return { borderColor: 'rgba(0,188,212,0.45)', background: 'rgba(0,188,212,0.04)' };
  };

  // Badge shown next to param description when adaptive is active
  const renderAdaptiveBadge = (paramName) => {
    if (!isAdaptiveActive || !ADAPTIVE_ENGINE_PARAMS.has(paramName)) return null;
    if (operatorLocked.has(paramName)) {
      return (
        <Tooltip title="You manually set this — adaptive engine won't change it this session" arrow>
          <Chip
            icon={<LockIcon sx={{ fontSize: '0.65rem !important' }} />}
            label="LOCKED"
            size="small"
            sx={{ height: 16, fontSize: '0.60rem', fontWeight: 700, color: '#ff9800',
                  background: 'rgba(255,152,0,0.12)', border: '1px solid rgba(255,152,0,0.3)',
                  '& .MuiChip-label': { px: '5px' }, flexShrink: 0 }}
          />
        </Tooltip>
      );
    }
    return (
      <Tooltip title="Adaptive engine is managing this parameter — changes automatically based on market regime" arrow>
        <Chip
          label="AUTO"
          size="small"
          sx={{ height: 16, fontSize: '0.60rem', fontWeight: 700, color: '#00bcd4',
                background: 'rgba(0,188,212,0.12)', border: '1px solid rgba(0,188,212,0.3)',
                '& .MuiChip-label': { px: '5px' }, flexShrink: 0 }}
        />
      </Tooltip>
    );
  };

  // Render parameter input
  const renderParam = (paramName, skipFilter = false) => {
    const params = paramsInfo?.params || {};
    const info = params[paramName] || {};
    const type = info.type || 'str';
    const value = formatValue(formValues[paramName], type);
    const error = errors[paramName];
    const isHot = info.hot_reload;
    const description = info.description || paramName;

    // Search filter — hide params that don't match (skipped in flat search mode)
    if (!skipFilter && search.trim()) {
      const q = search.toLowerCase();
      const pNorm = paramName.toLowerCase().replace(/_/g, ' ');
      const matches =
        pNorm.includes(q) ||
        paramName.toLowerCase().includes(q) ||
        description.toLowerCase().includes(q);
      if (!matches) return null;
    }

    const rangeText =
      info.min !== undefined && info.min !== null && info.max !== undefined && info.max !== null
        ? `${info.min}–${info.max}` : '';

    // String select params (e.g. wind_down_floor_action)
    const STRING_SELECT_OPTIONS = {
      adaptive_mode: [
        { value: 'manual',   label: 'Manual — you control every parameter' },
        { value: 'preset',   label: 'Preset — load recommended values for strategy type' },
        { value: 'adaptive', label: 'Adaptive — auto-tune based on live market regime' },
      ],
      adaptive_preset: [
        { value: 'strangle',     label: 'Short Strangle — standard OTM positions' },
        { value: 'straddle',     label: 'Short Straddle — near-ATM positions' },
        { value: 'short_window', label: 'Short Window — 3–5 hour sessions' },
      ],
      wind_down_floor_action: [
        { value: 'skip', label: 'Skip — let theta work' },
        { value: 'normal', label: 'Normal — allow adjustments' },
        { value: 'pause', label: 'Pause — require decision' },
      ],
      vol_regime_action: [
        { value: 'block_sells', label: 'Block Sells — block new sell orders' },
        { value: 'pause', label: 'Pause — pause entire session' },
        { value: 'wind_down', label: 'Wind Down — reduce positions' },
      ],
      trend_action: [
        { value: 'block_sells', label: 'Block Sells — block dangerous side only' },
        { value: 'pause', label: 'Pause — pause entire session' },
        { value: 'wind_down', label: 'Wind Down — buyback dangerous side' },
      ],
      perp_hedge_mode: [
        { value: 'full', label: 'Full — hedge every heartbeat' },
        { value: 'atm_only', label: 'ATM Only — hedge when strike near ATM' },
      ],
      replenish_lot_mode: [
        { value: 'match_active', label: 'Match Active — match open side lot count' },
        { value: 'initial', label: 'Initial — use session initial_lots' },
      ],
    };

    if (type === 'str' && STRING_SELECT_OPTIONS[paramName]) {
      const options = STRING_SELECT_OPTIONS[paramName];
      return (
        <Grid item xs={12} sm={6} key={paramName}>
          <Box sx={{ ...cardSx, ...getAdaptiveCardSx(paramName) }}>
            <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.75 }}>
              <Typography sx={{ ...descSx, flex: 1 }}>{description}</Typography>
              {renderAdaptiveBadge(paramName)}
              {renderIcons(isHot, paramName)}
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, mt: 'auto' }}>
              <Typography sx={keySx}>{paramName}</Typography>
              <FormControl size="small" sx={{ minWidth: 190 }}>
                <Select
                  value={value || ''}
                  onChange={(e) => handleChange(paramName, e.target.value, type)}
                  displayEmpty
                  sx={{
                    fontSize: '0.88rem',
                    '& .MuiInputBase-input': { py: '4px', px: '10px' },
                    '& .MuiOutlinedInput-root': { background: '#0d1117' },
                    '& fieldset': { borderColor: '#30363d' },
                    '&:hover fieldset': { borderColor: '#6e7681' },
                  }}
                >
                  {options.map((opt) => (
                    <MenuItem key={opt.value} value={opt.value} sx={{ fontSize: '0.88rem' }}>{opt.label}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>
          </Box>
        </Grid>
      );
    }

    if (type === 'bool') {
      const conflictWarnings = getConflictWarnings(formValues);
      const conflictMsg = conflictWarnings[paramName];
      const isOn = Boolean(value);
      const adaptiveBoolOverlay = getAdaptiveCardSx(paramName);
      // Runtime state warning: replenish is enabled but T4 wind-down is currently active.
      // Inform the user that it will be gated until the trend clears — don't block save.
      const trendT4Warning = (
        paramName === 'replenish_enabled' &&
        isOn &&
        (sessionData?._trend_tier >= 4 || sessionData?._trend_wind_down_triggered)
      ) ? 'Session is currently in Tier 4 Wind-Down (spot is far from the trend anchor). Auto-replenish will remain paused until the trend recovers or the anchor auto-resets via the T4 timeout.' : null;
      return (
        <Grid item xs={12} key={paramName}>
          <Box
            sx={{
              background: conflictMsg ? 'rgba(255,152,0,0.05)' : isOn ? 'rgba(56,139,253,0.07)' : (adaptiveBoolOverlay.background || '#1c2128'),
              border: '1px solid',
              borderColor: conflictMsg ? 'rgba(210,120,0,0.5)' : isOn ? 'rgba(56,139,253,0.4)' : (adaptiveBoolOverlay.borderColor || '#21262d'),
              borderRadius: '8px',
              px: '12px', py: '9px',
              cursor: 'pointer',
              transition: 'border-color 0.15s, background-color 0.15s',
              '&:hover': { borderColor: conflictMsg ? 'rgba(210,120,0,0.7)' : 'rgba(56,139,253,0.5)' },
            }}
            onClick={() => handleChange(paramName, !isOn, type)}
          >
            <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.25 }}>
              <Switch
                checked={isOn}
                onChange={(e) => { e.stopPropagation(); handleChange(paramName, e.target.checked, type); }}
                size="small"
                color={conflictMsg ? 'warning' : 'primary'}
                sx={{ mt: 0.15, flexShrink: 0 }}
              />
              <Box sx={{ flex: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.75 }}>
                  <Typography sx={{
                    ...descSx, flex: 1, userSelect: 'none',
                    color: isOn ? '#eaf0f8' : '#9ba8b5',
                    transition: 'color 0.15s',
                  }}>
                    {description}
                  </Typography>
                  {renderAdaptiveBadge(paramName)}
                  {renderIcons(isHot, paramName)}
                </Box>
                <Typography sx={{ ...keySx, mt: 0.4 }}>{paramName}</Typography>
              </Box>
            </Box>
            {conflictMsg && (
              <Alert severity="warning" sx={{ py: 0.5, fontSize: '0.7rem', mt: 0.75 }} icon={<WarningIcon fontSize="small" />}>
                <strong>Conflict:</strong> {conflictMsg}
              </Alert>
            )}
            {trendT4Warning && (
              <Alert severity="warning" sx={{ py: 0.5, fontSize: '0.7rem', mt: 0.75 }} icon={<WarningIcon fontSize="small" />}>
                ⚠️ <strong>Replenish Blocked:</strong> {trendT4Warning}
              </Alert>
            )}
          </Box>
        </Grid>
      );
    }

    // ── Numeric ──
    return (
      <Grid item xs={12} sm={6} key={paramName}>
        <Box sx={{ ...cardSx, ...getAdaptiveCardSx(paramName) }}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.75 }}>
            <Typography sx={{ ...descSx, flex: 1 }}>{description}</Typography>
            {renderAdaptiveBadge(paramName)}
            {renderIcons(isHot, paramName)}
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, mt: 'auto' }}>
            <Typography sx={keySx}>{paramName}</Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
              {rangeText && (
                <Typography sx={{ fontSize: '0.70rem', color: '#8b949e', whiteSpace: 'nowrap' }}>
                  {rangeText}
                </Typography>
              )}
              <TextField
                type="number"
                value={value}
                onChange={(e) => handleChange(paramName, e.target.value, type)}
                size="small"
                error={Boolean(error)}
                inputProps={{ min: info.min, max: info.max, step: (type === 'int' || Number.isInteger(Number(value))) ? 1 : 0.01 }}
                sx={{
                  width: 90,
                  '& .MuiOutlinedInput-root': {
                    background: '#0d1117',
                    '& fieldset': { borderColor: error ? 'error.main' : '#30363d' },
                    '&:hover fieldset': { borderColor: error ? 'error.main' : '#6e7681' },
                    '&.Mui-focused fieldset': { borderColor: '#388bfd' },
                  },
                  '& .MuiInputBase-input': {
                    py: '4px', px: '8px',
                    fontSize: '1.0rem', fontWeight: 600,
                    textAlign: 'right',
                    color: error ? 'error.main' : '#79c0ff',
                    fontFamily: '"SF Mono","Fira Code",monospace',
                  },
                }}
              />
            </Box>
          </Box>
          {error && (
            <Typography sx={{ fontSize: '0.72rem', color: 'error.main', mt: 0.25 }}>{error}</Typography>
          )}
        </Box>
      </Grid>
    );
  };

  return (
    <Dialog open={open} onClose={() => !saving && onClose()} maxWidth="lg" fullWidth>
      <DialogTitle sx={{ pb: 1, background: '#1c2128', borderBottom: '1px solid #21262d' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
          <SettingsIcon color="primary" />
          <span style={{ fontWeight: 600 }}>Strategy Settings</span>
          <Chip
            label={`Session: ${sessionId}`}
            size="small"
            variant="outlined"
            sx={{ ml: 'auto', fontFamily: 'monospace', fontSize: 11 }}
          />
        </Box>
        <TextField
          placeholder="Search parameters…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          size="small"
          fullWidth
          sx={{
            mb: 1.5,
            '& .MuiOutlinedInput-root': { background: '#0d1117' },
            '& fieldset': { borderColor: '#30363d' },
            '&:hover fieldset': { borderColor: '#6e7681' },
          }}
          inputProps={{ style: { fontSize: '0.82rem' } }}
        />
        <Box sx={{
          background: 'rgba(56,139,253,0.08)',
          border: '1px solid rgba(56,139,253,0.2)',
          borderRadius: '6px',
          px: 1.5, py: 0.75,
          fontSize: '0.82rem', color: '#79c0ff',
          display: 'flex', alignItems: 'center', gap: 0.75,
        }}>
          <HotIcon sx={{ fontSize: 14 }} />
          <span><strong>Hot Reload:</strong> changes apply on next heartbeat. <strong>🔒</strong> params require session restart.</span>
        </Box>
      </DialogTitle>

      <DialogContent sx={{ maxHeight: '72vh', overflowY: 'auto', background: '#161b22', p: '16px 20px' }}>
        {loading && (
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        )}

        {!loading && serverError && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setServerError(null)}>
            {serverError}
          </Alert>
        )}

        {!loading && success && (
          <Alert severity="success" sx={{ mb: 2 }}>
            ✅ Parameters updated successfully! Heartbeat will use new values on next cycle.
          </Alert>
        )}

        {!loading && sessionData && (
          <>
            {/* ⭐ My Controls — always visible when any params are pinned */}
            {pinned.size > 0 && (
              <Box sx={{ mb: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                  <Box sx={{ width: 3, height: 16, backgroundColor: '#ffd700', borderRadius: '2px', flexShrink: 0 }} />
                  <Typography sx={{ fontWeight: 700, fontSize: '0.93rem', color: '#ffd700' }}>
                    ⭐ My Controls
                  </Typography>
                  <Chip
                    label={`${pinned.size}`}
                    size="small"
                    sx={{ height: 16, fontSize: '0.65rem', background: 'rgba(255,215,0,0.12)', color: '#ffd700', border: '1px solid rgba(255,215,0,0.25)', '& .MuiChip-label': { px: '5px' } }}
                  />
                </Box>
                <Typography sx={{ display: 'block', color: '#9ba8b5', mb: 1.25, fontStyle: 'italic', fontSize: '0.80rem', pl: '11px' }}>
                  💡 Click ⭐ on any parameter to pin or unpin it here.
                </Typography>
                <Grid container spacing={1}>
                  {[...pinned].map(p => renderParam(p, true))}
                </Grid>
                <Divider sx={{ mt: 2, borderColor: '#21262d' }} />
              </Box>
            )}

            {search.trim() ? (
              /* Search mode: flat list, no group headers */
              (() => {
                const q = search.toLowerCase();
                const params = paramsInfo?.params || {};
                const matches = Object.keys(params).filter(p => {
                  const info = params[p] || {};
                  const desc = info.description || p;
                  const pNorm = p.toLowerCase().replace(/_/g, ' ');
                  return pNorm.includes(q) || p.toLowerCase().includes(q) || desc.toLowerCase().includes(q);
                });
                if (!matches.length) {
                  return (
                    <Typography sx={{ color: '#6e7681', fontSize: '0.82rem', textAlign: 'center', mt: 4 }}>
                      No parameters match "{search}"
                    </Typography>
                  );
                }
                return (
                  <Grid container spacing={1}>
                    {matches.map(p => renderParam(p, /* skipFilter */ true))}
                  </Grid>
                );
              })()
            ) : (
              /* Normal grouped layout */
              Object.entries(PARAM_GROUPS).map(([groupKey, group], idx) => (
                <Box key={groupKey} sx={{ mb: 2 }}>
                  {idx > 0 && <Divider sx={{ my: 2, borderColor: '#21262d' }} />}

                  {/* Group header */}
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                    <Box sx={{ width: 3, height: 16, backgroundColor: group.color, borderRadius: '2px', flexShrink: 0 }} />
                    <Typography sx={{ fontWeight: 700, fontSize: '0.93rem', color: group.color }}>
                      {group.title}
                    </Typography>
                    {groupKey === 'safety' && (
                      <Box component="span" sx={{
                        ml: 'auto', fontSize: '0.62rem', fontWeight: 700, letterSpacing: '0.5px',
                        background: 'rgba(210,120,0,0.15)', border: '1px solid rgba(210,120,0,0.4)',
                        color: '#f0883e', borderRadius: '4px', px: '6px', py: '1px', fontSize: '0.69rem',
                      }}>⚠ CRITICAL</Box>
                    )}
                  </Box>
                  {group.blurb && (
                    <Typography sx={{ display: 'block', color: '#9ba8b5', mb: 1.25, fontStyle: 'italic', fontSize: '0.80rem', pl: '11px' }}>
                      💡 {group.blurb}
                    </Typography>
                  )}

                  {group.sections ? (
                    group.sections.map((section, sectionIdx) => (
                      <Box key={sectionIdx}>
                        {sectionIdx > 0 && <Divider sx={{ my: 1.5, borderStyle: 'dashed', borderColor: '#21262d' }} />}
                        {section.header && (
                          <Typography sx={{
                            display: 'block', fontWeight: 600, color: group.color || '#6e7681',
                            mb: 1, mt: sectionIdx > 0 ? 0.5 : 0,
                            letterSpacing: '0.6px', textTransform: 'uppercase', fontSize: '0.75rem', opacity: 0.90,
                          }}>
                            {section.header}
                          </Typography>
                        )}
                        <Grid container spacing={1}>
                          {section.params.map((paramName) => renderParam(paramName))}
                        </Grid>
                      </Box>
                    ))
                  ) : (
                    <Grid container spacing={1}>
                      {group.params.map((paramName) => renderParam(paramName))}
                    </Grid>
                  )}
                </Box>
              ))
            )}
          </>
        )}
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2, background: '#1c2128', borderTop: '1px solid #21262d' }}>
        <Button onClick={() => onClose()} disabled={saving} sx={{ color: '#8b949e', borderColor: '#30363d', '&:hover': { borderColor: '#8b949e', color: '#e6edf3' } }} variant="outlined">
          Cancel
        </Button>
        <Button
          variant="contained"
          onClick={handleSave}
          disabled={saving || success}
          startIcon={saving ? <CircularProgress size={16} /> : undefined}
          sx={{ background: '#1f6feb', '&:hover': { background: '#388bfd' }, fontWeight: 600 }}
        >
          {saving ? 'Saving...' : success ? 'Saved!' : 'Save Changes'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
