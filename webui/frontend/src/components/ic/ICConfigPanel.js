/**
 * ICConfigPanel — Parameter management with hot-reload
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Box, Typography, TextField, Button, Alert, Grid, Divider, Switch, FormControlLabel } from '@mui/material';
import icService from './icService';

const PARAM_GROUPS = [
  {
    label: 'General',
    params: [
      { key: 'lots', label: 'Lots per leg', type: 'number' },
      { key: 'expiry_dte', label: 'Target DTE at entry', type: 'number' },
      { key: 'wing_width_usd', label: 'Wing width (USD)', type: 'number' },
    ],
  },
  {
    label: 'Strike Selection',
    params: [
      { key: 'short_put_delta_target', label: 'Short put delta', type: 'number', step: 0.01 },
      { key: 'short_call_delta_target', label: 'Short call delta', type: 'number', step: 0.01 },
      { key: 'strike_interval', label: 'Strike grid interval', type: 'number' },
    ],
  },
  {
    label: 'Heartbeat',
    params: [
      { key: 'heartbeat_interval', label: 'Normal interval (s)', type: 'number' },
      { key: 'rapid_heartbeat_interval', label: 'Rapid interval (s)', type: 'number' },
    ],
  },
  {
    label: 'Exit Rules',
    params: [
      { key: 'profit_target_pct', label: 'Profit target (%)', type: 'number' },
      { key: 'close_at_dte', label: 'Close at DTE (days)', type: 'number' },
      { key: 'max_loss_pct', label: 'Max loss (%)', type: 'number' },
    ],
  },
  {
    label: 'Adjustment',
    params: [
      { key: 'breach_threshold_pct', label: 'Breach threshold (%)', type: 'number', step: 0.1 },
      { key: 'max_adjustments_per_cycle', label: 'Max adj/cycle', type: 'number' },
      { key: 'adjustment_cooldown_secs', label: 'Adj cooldown (s)', type: 'number' },
    ],
  },
  {
    label: 'Auto-Cycle',
    params: [
      { key: 'auto_cycle', label: 'Auto-cycle', type: 'bool' },
      { key: 'cycle_delay_secs', label: 'Cycle delay (s)', type: 'number' },
    ],
  },
  {
    label: 'Safety',
    params: [
      { key: 'max_daily_loss_usd', label: 'Max daily loss (USD)', type: 'number' },
      { key: 'margin_safety_pct', label: 'Margin safety (%)', type: 'number' },
      { key: 'simulate', label: 'Simulate mode', type: 'bool' },
    ],
  },
];

const ICConfigPanel = ({ session, onSaved }) => {
  const [params, setParams] = useState({});
  const [dirty, setDirty] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  // Load initial params
  useEffect(() => {
    if (session?.params) {
      setParams({ ...session.params });
      setDirty({});
    }
  }, [session?.session_id, session?.params]);

  const handleChange = useCallback((key, value) => {
    setParams((prev) => ({ ...prev, [key]: value }));
    setDirty((prev) => ({ ...prev, [key]: true }));
    setSuccess(false);
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      const changedParams = {};
      Object.keys(dirty).forEach((key) => {
        changedParams[key] = params[key];
      });

      const result = await icService.updateParams(session.session_id, changedParams);
      if (result.success) {
        setDirty({});
        setSuccess(true);
        onSaved?.();
      } else {
        setError(result.error || 'Failed to save parameters');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    try {
      const result = await icService.getDefaults();
      if (result.success) {
        setParams({ ...result.defaults });
        // Mark all as dirty
        const allDirty = {};
        Object.keys(result.defaults).forEach((k) => { allDirty[k] = true; });
        setDirty(allDirty);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const hasDirty = Object.keys(dirty).length > 0;

  return (
    <Box sx={{ p: 1 }}>
      <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 700 }}>
        Settings — {session?.name || session?.session_id}
      </Typography>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }}>Parameters saved successfully</Alert>}

      {PARAM_GROUPS.map((group) => (
        <Box key={group.label} sx={{ mb: 2 }}>
          <Divider sx={{ mb: 1.5 }}>
            <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary' }}>
              {group.label}
            </Typography>
          </Divider>

          <Grid container spacing={1.5}>
            {group.params.map((p) => (
              <Grid item xs={12} sm={6} md={4} key={p.key}>
                {p.type === 'bool' ? (
                  <FormControlLabel
                    control={
                      <Switch
                        checked={!!params[p.key]}
                        onChange={(e) => handleChange(p.key, e.target.checked)}
                        size="small"
                      />
                    }
                    label={<Typography variant="caption">{p.label}</Typography>}
                  />
                ) : (
                  <TextField
                    label={p.label}
                    type="number"
                    size="small"
                    fullWidth
                    value={params[p.key] ?? ''}
                    onChange={(e) => handleChange(p.key, parseFloat(e.target.value) || 0)}
                    inputProps={{ step: p.step || 1 }}
                    sx={{
                      '& .MuiInputBase-input': { fontFamily: 'monospace', fontSize: '0.85rem' },
                      ...(dirty[p.key] ? { '& .MuiOutlinedInput-root': { borderColor: '#ff9800' } } : {}),
                    }}
                  />
                )}
              </Grid>
            ))}
          </Grid>
        </Box>
      ))}

      <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
        <Button
          variant="contained" onClick={handleSave}
          disabled={!hasDirty || saving}
          sx={{ textTransform: 'none' }}
        >
          {saving ? 'Saving...' : 'Save Changes'}
        </Button>
        <Button
          variant="outlined" onClick={handleReset}
          sx={{ textTransform: 'none' }}
        >
          Reset to Defaults
        </Button>
      </Box>

      {session?.status === 'RUNNING' && (
        <Alert severity="info" sx={{ mt: 1.5 }}>
          Changes to highlighted fields take effect immediately — no restart needed
        </Alert>
      )}
    </Box>
  );
};

export default ICConfigPanel;
