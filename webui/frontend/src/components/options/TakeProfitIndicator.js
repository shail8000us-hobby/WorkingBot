/**
 * Take Profit Indicator Component
 *
 * Compact inline button for setting take profit per strike.
 * Opens a dialog to configure target profit and exit quantity.
 *
 * Created: February 3, 2026
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  IconButton,
  Tooltip,
  Typography,
  Chip,
  CircularProgress,
} from '@mui/material';
import { TrendingUp, CheckCircle, Close } from '@mui/icons-material';
import axios from 'axios';

const api = axios.create({ baseURL: '' });

export default function TakeProfitIndicator({
  symbol,
  currentPnl = 0,
  currentSize = 0,
  settings = null,
  onEdit = () => {},
  onUpdate = () => {},
}) {
  const [saving, setSaving] = useState(false);
  const [localSettings, setLocalSettings] = useState(settings);

  // Update local settings when prop changes
  useEffect(() => {
    setLocalSettings(settings);
  }, [settings]);

  const hasTP = localSettings && localSettings.target_profit !== 0 && localSettings.target_profit !== undefined && localSettings.enabled;
  const targetProfit = localSettings?.target_profit || 0;
  const exitQuantity = localSettings?.exit_quantity || 0;
  const triggered = localSettings?.triggered || false;

  // Determine if it's a profit target or loss limit
  const isLossLimit = targetProfit < 0;
  
  // Calculate progress towards target (works for both profit and loss)
  const currentValue = currentPnl;
  let progressPercentage = 0;
  if (hasTP && targetProfit !== 0) {
    if (isLossLimit) {
      // For loss limits: flip the calculation to show meaningful progress
      // Example: target = -$50, current = -$100 → (-50/-100) * 100 = 50% (halfway to target)
      // Example: target = -$50, current = -$50 → (-50/-50) * 100 = 100% (at target)
      // Example: target = -$50, current = -$25 → (-50/-25) * 100 = 200% (past target)
      if (currentValue !== 0) {
        progressPercentage = (targetProfit / currentValue) * 100;
      }
    } else {
      // For profit targets: show how close we are to the positive target
      // Example: target = $50, current = $25 → (25/50) * 100 = 50%
      progressPercentage = (currentValue / targetProfit) * 100;
    }
  }
  const isNearTarget = progressPercentage >= 70;
  const isVeryNearTarget = progressPercentage >= 90;

  const handleRemove = async () => {
    setSaving(true);
    try {
      const { data } = await api.post('/api/options/take-profit/strike/remove', {
        symbol,
      });

      if (data.success) {
        setLocalSettings(null);
        onUpdate(symbol, null);
      }
    } catch (err) {
      console.error('Failed to remove take profit:', err);
    } finally {
      setSaving(false);
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

  // Triggered state (take profit was hit)
  if (triggered) {
    return (
      <Tooltip title={`Take profit of $${targetProfit} was triggered - ${exitQuantity} lots exited`}>
        <Chip
          icon={<CheckCircle sx={{ fontSize: 12 }} />}
          label={`$${targetProfit}`}
          size="small"
          color="success"
          variant="filled"
          onClick={onEdit}
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

  // Has take profit set
  if (hasTP) {
    const targetType = isLossLimit ? 'Loss Limit' : 'Profit Target';
    const tooltipContent = (
      <Box>
        <Typography variant="caption" display="block">
          <strong>{targetType}: ${targetProfit.toFixed(0)}</strong>
        </Typography>
        <Typography variant="caption" display="block">
          Exit Quantity: {exitQuantity} lots
        </Typography>
        {triggered ? (
          <Typography variant="caption" display="block" sx={{ mt: 0.5, color: 'success.main', fontWeight: 'bold' }}>
            ✅ Order Placed Successfully!
          </Typography>
        ) : (
          <>
            {currentValue !== 0 && (
              <>
                <Typography variant="caption" display="block">
                  Current P&L: ${currentValue.toFixed(2)} ({Math.abs(progressPercentage).toFixed(0)}%)
                </Typography>
                <Typography variant="caption" display="block">
                  Remaining: ${(targetProfit - currentValue).toFixed(2)}
                </Typography>
              </>
            )}
            <Typography variant="caption" display="block" sx={{ mt: 0.5, color: isLossLimit ? 'error.light' : 'success.light' }}>
              🎯 Auto partial exit when target reached
            </Typography>
          </>
        )}
        <Typography variant="caption" display="block" sx={{ fontSize: '0.65rem', color: 'text.secondary' }}>
          {triggered ? 'Target executed' : 'Click to edit • Right-click to remove'}
        </Typography>
      </Box>
    );

    return (
      <Box display="flex" alignItems="center" gap={0.5}>
        <Tooltip title={tooltipContent} arrow>
          <Chip
            icon={triggered ? <CheckCircle sx={{ fontSize: 12 }} /> : <TrendingUp sx={{ fontSize: 12 }} />}
            label={triggered ? `✓ $${targetProfit}` : `$${targetProfit} / ${exitQuantity}L`}
            size="small"
            color={triggered ? 'success' : isLossLimit ? 'error' : isVeryNearTarget ? 'success' : isNearTarget ? 'warning' : 'default'}
            variant={triggered ? 'filled' : Math.abs(progressPercentage) > 0 ? 'filled' : 'outlined'}
            onClick={triggered ? undefined : onEdit}
            onContextMenu={triggered ? undefined : (e) => {
              e.preventDefault();
              handleRemove();
            }}
            sx={{
              height: 20,
              fontSize: 10,
              cursor: triggered ? 'default' : 'pointer',
              fontWeight: triggered || isNearTarget ? 'bold' : 'normal',
              animation: triggered ? 'none' : isVeryNearTarget ? 'pulse 1s infinite' : 'none',
              '@keyframes pulse': {
                '0%, 100%': { opacity: 1 },
                '50%': { opacity: 0.6 },
              },
            }}
          />
        </Tooltip>
        {!triggered && Math.abs(progressPercentage) > 0 && (
          <Typography
            variant="caption"
            sx={{
              fontSize: '0.65rem',
              color: isNearTarget ? (isLossLimit ? 'error.main' : 'success.main') : 'text.secondary',
              fontWeight: isNearTarget ? 'bold' : 'normal',
            }}
          >
            {Math.abs(progressPercentage).toFixed(0)}%
          </Typography>
        )}
      </Box>
    );
  }

  // No take profit set - show add button
  return (
    <Tooltip title="Click to set target (profit or loss limit)">
      <IconButton size="small" onClick={onEdit} sx={{ opacity: 0.6, '&:hover': { opacity: 1 } }}>
        <TrendingUp sx={{ fontSize: 16, color: 'success.main' }} />
      </IconButton>
    </Tooltip>
  );
}
