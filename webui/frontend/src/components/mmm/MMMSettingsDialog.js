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
} from '@mui/icons-material';
import mmmService from './mmmService';

// =============================================================================
// Parameter Groups for UI Organization
// =============================================================================

const PARAM_GROUPS = {
  core: {
    title: 'Core Parameters',
    color: '#2196f3',
    params: ['initial_lots', 'adjustment_interval', 'max_loss_amount'],
  },
  triggers: {
    title: 'Trigger & Adjustment',
    color: '#4caf50',
    params: ['min_trigger_move', 'shift_threshold', 'shift_threshold_pct', 'shift_target_premium', 'max_adjustments', 'cooldown_on_reversal'],
  },
  safety: {
    title: 'Safety Limits',
    color: '#ff9800',
    params: ['whipsaw_limit', 'max_lots_per_side', 'trailing_stop_pct', 'premium_buffer_pct', 'close_at_atm'],
  },
  expiry: {
    title: 'Close-at-Expiry',
    color: '#f44336',
    params: ['auto_close_mins', 'stop_adjustment_mins', 'close_at_threshold', 'theta_acceleration_window'],
  },
  adaptive: {
    title: 'Adaptive Interval',
    color: '#00bcd4',
    params: ['adaptive_interval_enabled'],
  },
  windDown: {
    title: 'Wind-Down Mode',
    color: '#9c27b0',
    params: ['wind_down_enabled', 'wind_down_hours_before_expiry', 'wind_down_buyback_pct', 'wind_down_close_threshold', 'wind_down_min_lots_to_keep', 'wind_down_floor_action'],
  },
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
        { value: 'skip', label: 'Skip — do nothing, let expire' },
        { value: 'normal', label: 'Normal — allow standard adjustments' },
        { value: 'pause', label: 'Pause — stop bot, require manual decision' },
      ],
    };

    if (type === 'str' && STRING_SELECT_OPTIONS[paramName]) {
      const options = STRING_SELECT_OPTIONS[paramName];
      return (
        <Grid item xs={12} sm={6} key={paramName}>
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

      <DialogContent>
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
            
            <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
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
