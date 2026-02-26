/**
 * Max Loss Indicator Component
 *
 * Compact inline editor for setting max loss per strike.
 * Shows current max loss limit and allows quick editing.
 *
 * Created: January 16, 2026
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  TextField,
  IconButton,
  Tooltip,
  Typography,
  Chip,
  CircularProgress,
} from '@mui/material';
import { Warning, Check, Close, Edit, Shield, ShieldOutlined } from '@mui/icons-material';
// BUG-14 FIX: use shared apiShim (handles auth headers, base URL, interceptors)
import api from '../../utils/apiShim';

export default function MaxLossIndicator({
  symbol,
  currentPnl = 0,
  settings = null,
  onUpdate = () => {},
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null); // MISSING-4 FIX: show inline error
  const [localSettings, setLocalSettings] = useState(settings);

  // Update local settings when prop changes
  useEffect(() => {
    setLocalSettings(settings);
    if (settings?.max_loss) {
      setInputValue(settings.max_loss.toString());
    }
  }, [settings]);

  const hasMaxLoss = localSettings && localSettings.max_loss > 0 && localSettings.enabled;
  const maxLoss = localSettings?.max_loss || 0;
  const triggered = localSettings?.triggered || false;

  // Calculate how close we are to max loss (percentage)
  const lossAmount = currentPnl < 0 ? Math.abs(currentPnl) : 0;
  const lossPercentage = hasMaxLoss ? (lossAmount / maxLoss) * 100 : 0;
  const isNearLimit = lossPercentage >= 70;
  const isVeryNearLimit = lossPercentage >= 90;

  const handleSave = async () => {
    const value = parseFloat(inputValue);
    if (isNaN(value) || value <= 0) {
      setIsEditing(false);
      return;
    }

    setSaving(true);
    setSaveError(null);
    try {
      const { data } = await api.post('/api/options/max-loss/strike/set', {
        symbol,
        max_loss: value,
      });

      if (data.success) {
        setLocalSettings({
          symbol,
          max_loss: value,
          enabled: true,
          triggered: false,
        });
        onUpdate(symbol, { max_loss: value, enabled: true });
        setIsEditing(false);
      } else {
        // MISSING-4 FIX: show API-level error inline
        setSaveError(data.error || 'Save failed');
      }
    } catch (err) {
      console.error('Failed to save max loss:', err);
      setSaveError(err.message || 'Network error');
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const { data } = await api.delete(`/api/options/max-loss/strike/remove/${symbol}`);

      if (data.success) {
        setLocalSettings(null);
        setInputValue('');
        onUpdate(symbol, null);
        setIsEditing(false);
      } else {
        setSaveError(data.error || 'Remove failed');
      }
    } catch (err) {
      console.error('Failed to remove max loss:', err);
      setSaveError(err.message || 'Network error');
    } finally {
      setSaving(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSave();
    } else if (e.key === 'Escape') {
      setIsEditing(false);
      setInputValue(maxLoss > 0 ? maxLoss.toString() : '');
    }
  };

  // Loading state
  if (saving) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minWidth={60}>
        <CircularProgress size={16} />
      </Box>
    );
  }

  // Editing mode
  if (isEditing) {
    return (
      <Box display="flex" flexDirection="column" gap={0.25}>
      {saveError && (
        <Typography variant="caption" sx={{ color: 'error.main', fontSize: '0.65rem' }}>
          {saveError}
        </Typography>
      )}
      <Box display="flex" alignItems="center" gap={0.5}>
        <TextField
          size="small"
          type="number"
          placeholder="$"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyPress}
          autoFocus
          sx={{
            width: '60px',
            '& .MuiInputBase-input': {
              textAlign: 'center',
              fontSize: '0.75rem',
              padding: '4px 6px',
            },
          }}
        />
        <IconButton size="small" onClick={handleSave} sx={{ p: 0.25 }}>
          <Check sx={{ fontSize: 14, color: 'success.main' }} />
        </IconButton>
        <IconButton size="small" onClick={() => setIsEditing(false)} sx={{ p: 0.25 }}>
          <Close sx={{ fontSize: 14, color: 'error.main' }} />
        </IconButton>
        {hasMaxLoss && (
          <Tooltip title="Remove max loss limit">
            <IconButton size="small" onClick={handleRemove} sx={{ p: 0.25 }}>
              <Close sx={{ fontSize: 12, color: 'text.secondary' }} />
            </IconButton>
          </Tooltip>
        )}
      </Box>
      </Box>
    );
  }

  // Triggered state (max loss was hit)
  if (triggered) {
    return (
      <Tooltip title={`Max loss of $${maxLoss} was triggered - position closed`}>
        <Chip
          icon={<Warning sx={{ fontSize: 12 }} />}
          label={`$${maxLoss}`}
          size="small"
          color="error"
          variant="filled"
          onClick={() => setIsEditing(true)}
          sx={{
            height: 20,
            fontSize: 10,
            cursor: 'pointer',
            textDecoration: 'line-through',
          }}
        />
      </Tooltip>
    );
  }

  // Has max loss set
  if (hasMaxLoss) {
    const tooltipContent = (
      <Box>
        <Typography variant="caption" display="block">
          <strong>Max Loss Limit: ${maxLoss.toFixed(0)}</strong>
        </Typography>
        {lossAmount > 0 && (
          <>
            <Typography variant="caption" display="block">
              Current Loss: ${lossAmount.toFixed(2)} ({lossPercentage.toFixed(0)}%)
            </Typography>
            <Typography variant="caption" display="block">
              Remaining: ${(maxLoss - lossAmount).toFixed(2)}
            </Typography>
          </>
        )}
        <Typography variant="caption" display="block" sx={{ mt: 0.5, color: 'warning.light' }}>
          ⚡ Auto square-off when limit reached
        </Typography>
        <Typography variant="caption" display="block" sx={{ color: 'info.light' }}>
          Click to edit
        </Typography>
      </Box>
    );

    return (
      <Tooltip title={tooltipContent} arrow>
        <Chip
          icon={<Shield sx={{ fontSize: 12 }} />}
          label={`$${maxLoss.toFixed(0)}`}
          size="small"
          color={isVeryNearLimit ? 'error' : isNearLimit ? 'warning' : 'primary'}
          variant={isNearLimit ? 'filled' : 'outlined'}
          onClick={() => setIsEditing(true)}
          sx={{
            height: 20,
            fontSize: 10,
            cursor: 'pointer',
            '& .MuiChip-icon': { fontSize: 12 },
            animation: isVeryNearLimit ? 'pulse 1s infinite' : 'none',
            '@keyframes pulse': {
              '0%': { opacity: 1 },
              '50%': { opacity: 0.6 },
              '100%': { opacity: 1 },
            },
          }}
        />
      </Tooltip>
    );
  }

  // No max loss set - show edit button
  return (
    <Tooltip title="Set max loss limit for auto square-off">
      <IconButton
        size="small"
        onClick={() => setIsEditing(true)}
        sx={{ opacity: 0.4, '&:hover': { opacity: 1 } }}
      >
        <ShieldOutlined sx={{ fontSize: 16 }} />
      </IconButton>
    </Tooltip>
  );
}
