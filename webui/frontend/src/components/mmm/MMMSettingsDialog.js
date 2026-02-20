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
