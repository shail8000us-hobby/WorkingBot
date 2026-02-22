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
} from '@mui/material';
import {
  Settings as SettingsIcon,
  Bolt as HotIcon,
  Lock as LockIcon,
  Warning as WarningIcon,
  HelpOutline as HelpIcon,
} from '@mui/icons-material';
import mmmService from './mmmService';
import { HELP } from './MMMEducation';

// =============================================================================
// Parameter Groups for UI Organization
// =============================================================================

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
    params: ['min_trigger_move', 'shift_threshold', 'shift_threshold_pct', 'shift_target_premium', 'max_adjustments', 'cooldown_on_reversal'],
  },
  safety: {
    title: 'Safety Limits',
    color: '#ff9800',
    blurb: 'Guard rails to prevent runaway exposure. Adjust carefully.',
    params: ['whipsaw_limit', 'max_lots_per_side', 'trailing_stop_pct', 'premium_buffer_pct', 'close_at_atm', 'itm_guard_enabled'],
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
    params: ['wind_down_on_atm', 'wind_down_enabled', 'wind_down_hours_before_expiry', 'wind_down_buyback_pct', 'wind_down_close_threshold', 'wind_down_min_lots_to_keep', 'wind_down_floor_action'],
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
      'trend_enabled', 'trend_move_pct', 'trend_retrace_pct',
      'trend_ema_period', 'trend_ema_slope_threshold', 'trend_action',
      'trend_reset_beats',
    ],
  },
  perpHedge: {
    title: '⚡ Perp Delta Hedge',
    color: '#00bcd4',
    blurb: 'Perpetual futures delta hedging: trades BTCUSD perp to neutralize portfolio delta exposure each heartbeat. Threshold + rebalance band prevent over-trading.',
    params: [
      'perp_hedge_enabled',
      'perp_hedge_delta_threshold',
      'perp_hedge_ratio',
      'perp_hedge_rebalance_band',
      'perp_hedge_max_lots',
      'perp_hedge_cooldown_sec',
    ],
  },
};

// Rich tooltip text for each parameter (maps param name → detailed help)
const PARAM_TOOLTIPS = {
  initial_lots: 'Starting lots per side at entry. CE and PE each get this many lots. These "original" lots naturally hedge each other — when one side loses, the other gains. This is the safe foundation of the strategy.',
  adjustment_interval: HELP.heartbeat_interval || 'Seconds between heartbeat checks. Shorter = more responsive (catches fast moves) but more API calls and potential fees. Default 300 = 5 minutes.',
  max_loss_amount: HELP.max_loss || 'Absolute dollar hard stop. If your total P&L drops below this negative amount, ALL positions are immediately closed. Your last line of defense.',
  min_trigger_move: HELP.min_trigger_move || 'Minimum % premium must exceed trigger to fire adjustment.',
  shift_threshold: HELP.shift_threshold || 'Minimum premium at the hedge strike to avoid a strike shift.',
  shift_threshold_pct: HELP.shift_threshold_pct || 'Dynamic shift threshold as % of entry premium.',
  shift_target_premium: 'Target premium when looking for a new strike after a shift. The algo picks the strike closest to this premium value. Higher = deeper OTM (safer but less premium). Lower = closer to ATM (more premium but riskier).',
  max_adjustments: HELP.max_adjustments || 'Maximum number of adjustments before the algo stops and alerts you.',
  cooldown_on_reversal: HELP.cooldown || 'After a reversal is detected, skip one heartbeat interval before adjusting. Filters out false reversals from short price spikes.',
  whipsaw_limit: HELP.whipsaw || 'If the last N adjustments alternate between CE and PE, the market is whipsawing. The algo pauses.',
  max_lots_per_side: HELP.position_cap || 'Maximum total lots allowed per side (CE or PE). Prevents runaway lot accumulation from repeated adjustments.',
  trailing_stop_pct: HELP.trailing_profit || 'Once P&L hits a peak, if it drops more than this % from that peak, the algo alerts you. Protects profits from giving back too much.',
  premium_buffer_pct: 'Extra lots percentage for slippage protection. When calculating how many lots to sell, add this % extra to account for price movement between quote and fill. 0.05 = 5% buffer.',
  close_at_atm: 'Auto-close ALL positions if the original strike becomes at-the-money (spot price ≈ strike price). This is dangerous territory — ATM options have maximum gamma and can move violently.',
  itm_guard_enabled: 'When ON (default): blocks selling ITM options for adjustment — safe, prevents selling worthless contracts. When OFF: allows the algo to sell ITM options. Useful in the last 2-3 hours before expiry when strikes may briefly go ITM but you still want the algo to adjust. ⚠️ Turn OFF only when you understand the risk.',
  auto_close_mins: 'Auto-close ALL positions N minutes before expiry. This is the absolute final safety net. Default 5 = close everything 5 minutes before expiry, regardless of P&L.',
  stop_adjustment_mins: HELP.near_expiry || 'Stop making new adjustments N minutes before expiry. Let theta decay do the final work instead of adding risky late adjustments.',
  close_at_threshold: HELP.close_at_5 || 'Close any position whose premium drops to this level or below. Default 5 = when an option is worth $5 or less, buy it back to lock in ~95% profit.',
  theta_acceleration_window: 'Minutes before expiry to activate theta acceleration. Within this window, the algo widens trigger thresholds (allows more premium move before adjusting) because time decay is rapidly working in your favor.',
  adaptive_interval_enabled: HELP.adaptive_interval_enabled || 'Auto-scale heartbeat frequency based on time-to-expiry.',
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
  // Regime Controls — Trend Detection Guard
  trend_enabled: 'Master switch for the trend detection guard. Detects strong directional moves and blocks exposure-increasing sells on the dangerous side. The most impactful regime control.',
  trend_move_pct: 'Percentage move from session anchor that triggers the trend guard. For BTC at $100K, 1.5% = ~$1,500 — roughly a 1-sigma move for an 8-hour session.',
  trend_retrace_pct: 'Spot must retrace this percentage of the move before the trend guard resets. 30% means if BTC moved $2K, it needs to pull back $600 before the guard clears.',
  trend_ema_period: 'EMA (Exponential Moving Average) period in heartbeats for slope calculation. Confirms sustained directional drift vs. a one-time spike.',
  trend_ema_slope_threshold: 'EMA slope threshold for trend confirmation. Higher = less sensitive. A slope of 25 means ~0.25% per beat average drift — strong sustained move.',
  trend_action: 'What to do when trend triggers: "block_sells" (block dangerous-side sells only — smart directional blocking), "pause" (pause session), "wind_down" (also activate wind-down on dangerous side).',
  trend_reset_beats: 'After retracement and EMA slope calm down, must stay calm for this many consecutive beats before resetting to NORMAL. Prevents whipsaw on/off of trend guard.',
  // Perp Delta Hedge tooltips
  perp_hedge_enabled: 'Master switch for perpetual futures delta hedging. When enabled, the algo trades BTCUSD perpetual each heartbeat to neutralize portfolio delta. When disabled, no perp trades are made but existing positions remain.',
  perp_hedge_delta_threshold: 'Minimum absolute portfolio delta before hedging triggers. E.g., 0.02 = don\'t hedge until delta exceeds 2%. Prevents micro-adjustments on balanced portfolios.',
  perp_hedge_ratio: 'Fraction of portfolio delta to hedge. 1.0 = full neutralization (target delta zero). 0.5 = hedge only half the delta. Use < 1.0 if you want partial directional exposure.',
  perp_hedge_rebalance_band: 'Dead zone around target position. If current lots are within this band of target, skip the trade. Prevents tiny round-trip adjustments. E.g., 0.005 = 0.5% band.',
  perp_hedge_max_lots: 'Maximum perp position size in lots (1 lot = 0.001 BTC). Caps total hedge exposure. E.g., 50 lots = 0.05 BTC max perp position.',
  perp_hedge_cooldown_sec: 'Minimum seconds between consecutive hedge executions. Prevents rapid-fire trading during volatile periods. Default: 30 seconds.',
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

export default function MMMSettingsDialog({ open, onClose, sessionId, paramsInfo = {} }) {
  const [formValues, setFormValues] = useState({});
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);
  const [serverError, setServerError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [sessionData, setSessionData] = useState(null);

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

      // Filter out unchanged and non-hot params if session is running
      const changedParams = {};
      const nonHotChanges = [];
      const params = paramsInfo?.params || {};

      for (const [key, value] of Object.entries(formValues)) {
        if (value !== currentParams[key]) {
          changedParams[key] = value;
          const info = params[key] || {};
          if (isRunning && !info.hot_reload) {
            nonHotChanges.push(key);
          }
        }
      }

      if (Object.keys(changedParams).length === 0) {
        setServerError('No changes detected');
        setSaving(false);
        return;
      }

      if (nonHotChanges.length > 0) {
        setServerError(
          `Cannot change non-hot parameters (${nonHotChanges.join(', ')}) while session is ${sessionStatus}. ` +
          'Stop the session first, then update.'
        );
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

  // Render parameter input
  const renderParam = (paramName) => {
    const params = paramsInfo?.params || {};
    const info = params[paramName] || {};
    const type = info.type || 'str';
    const value = formatValue(formValues[paramName], type);
    const error = errors[paramName];
    const isHot = info.hot_reload;

    // String select params (e.g. wind_down_floor_action)
    const STRING_SELECT_OPTIONS = {
      wind_down_floor_action: [
        { value: 'skip', label: 'Skip — let theta work' },
        { value: 'normal', label: 'Normal — allow adjustments' },
        { value: 'pause', label: 'Pause — require decision' },
      ],
    };

    if (type === 'str' && STRING_SELECT_OPTIONS[paramName]) {
      const options = STRING_SELECT_OPTIONS[paramName];
      return (
        <Grid item xs={12} sm={6} key={paramName}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <FormControl fullWidth size="small">
              <InputLabel>{info.description || paramName}</InputLabel>
              <Select
                value={value || ''}
                label={info.description || paramName}
                onChange={(e) => handleChange(paramName, e.target.value, type)}
              >
                {options.map((opt) => (
                  <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
                ))}
              </Select>
            </FormControl>
            {renderHelpIcon(paramName)}
          </Box>
        </Grid>
      );
    }

    if (type === 'bool') {
      return (
        <Grid item xs={12} key={paramName}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={Boolean(value)}
                  onChange={(e) => handleChange(paramName, e.target.checked, type)}
                  size="small"
                />
              }
              label={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Typography variant="body2">{info.description || paramName}</Typography>
                  {!isHot && (
                    <Tooltip title="Requires session restart">
                      <LockIcon sx={{ fontSize: 14, color: 'text.disabled' }} />
                    </Tooltip>
                  )}
                  {isHot && (
                    <Tooltip title="Hot-reloadable">
                      <HotIcon sx={{ fontSize: 14, color: '#ff9800' }} />
                    </Tooltip>
                  )}
                  {renderHelpIcon(paramName)}
                </Box>
              }
            />
          </Box>
        </Grid>
      );
    }

    return (
      <Grid item xs={12} sm={6} key={paramName}>
        <TextField
          label={
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              {info.description || paramName}
              {!isHot && (
                <Tooltip title="Requires session restart">
                  <LockIcon sx={{ fontSize: 12, color: 'text.disabled', ml: 0.5 }} />
                </Tooltip>
              )}
              {isHot && (
                <Tooltip title="Hot-reloadable">
                  <HotIcon sx={{ fontSize: 12, color: '#ff9800', ml: 0.5 }} />
                </Tooltip>
              )}
              {renderHelpIcon(paramName)}
            </Box>
          }
          type="number"
          value={value}
          onChange={(e) => handleChange(paramName, e.target.value, type)}
          fullWidth
          size="small"
          error={Boolean(error)}
          helperText={
            error ||
            (info.min !== undefined && info.min !== null && info.max !== undefined && info.max !== null
              ? `Range: ${info.min} - ${info.max}`
              : '')
          }
          inputProps={{
            min: info.min,
            max: info.max,
            step: type === 'int' ? 1 : type === 'float' ? 0.01 : undefined,
          }}
        />
      </Grid>
    );
  };

  return (
    <Dialog open={open} onClose={() => !saving && onClose()} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <SettingsIcon color="primary" />
          <span>Strategy Settings</span>
          <Chip
            label={`Session: ${sessionId}`}
            size="small"
            variant="outlined"
            sx={{ ml: 'auto', fontFamily: 'monospace', fontSize: 11 }}
          />
        </Box>
      </DialogTitle>

      <DialogContent sx={{ maxHeight: '75vh', overflowY: 'auto' }}>
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
            <Alert severity="info" sx={{ mb: 3 }} icon={<HotIcon />}>
              <strong>Hot Reload:</strong> Changes take effect immediately on the next heartbeat.
              Parameters with <LockIcon sx={{ fontSize: 12, verticalAlign: 'middle' }} /> require
              session restart.
            </Alert>

            {/* Render parameter groups */}
            {Object.entries(PARAM_GROUPS).map(([groupKey, group], idx) => (
              <Box key={groupKey} sx={{ mb: 3 }}>
                {idx > 0 && <Divider sx={{ my: 3 }} />}

                <Box sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Box
                    sx={{
                      width: 4,
                      height: 20,
                      backgroundColor: group.color,
                      borderRadius: 1,
                    }}
                  />
                  <Typography variant="subtitle2" sx={{ fontWeight: 700, color: group.color }}>
                    {group.title}
                  </Typography>

                  {groupKey === 'safety' && (
                    <Chip
                      label="CRITICAL"
                      size="small"
                      color="warning"
                      icon={<WarningIcon />}
                      sx={{ ml: 'auto', fontWeight: 700 }}
                    />
                  )}
                </Box>
                {group.blurb && (
                  <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary', mb: 1.5, fontStyle: 'italic', fontSize: '0.72rem', opacity: 0.8 }}>
                    💡 {group.blurb}
                  </Typography>
                )}

                <Grid container spacing={2}>
                  {group.params.map((paramName) => renderParam(paramName))}
                </Grid>
              </Box>
            ))}
          </>
        )}
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={() => onClose()} disabled={saving}>
          Cancel
        </Button>
        <Button
          variant="contained"
          onClick={handleSave}
          disabled={saving || success}
          startIcon={saving ? <CircularProgress size={16} /> : undefined}
        >
          {saving ? 'Saving...' : success ? 'Saved!' : 'Save Changes'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
