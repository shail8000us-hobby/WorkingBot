/**
 * SL/TP Indicator Component
 *
 * Compact visual indicator showing SL/TP status in the positions table.
 * Shows colored chips for active stop-loss and take-profit levels.
 *
 * Created: January 14, 2026
 */

import React from 'react';
import { Box, Chip, Tooltip, Typography, IconButton } from '@mui/material';
import { TrendingDown, TrendingUp, ShowChart, Edit } from '@mui/icons-material';

export default function SLTPIndicator({ settings, position, onEdit }) {
  if (!settings) {
    return (
      <Tooltip title="Set SL/TP">
        <IconButton size="small" onClick={onEdit} sx={{ opacity: 0.5 }}>
          <ShowChart fontSize="small" />
        </IconButton>
      </Tooltip>
    );
  }

  const hasStopLoss = settings.stop_loss_price || settings.stop_loss_pct;
  const hasTakeProfit = settings.take_profit_price || settings.take_profit_pct;
  const hasTrailingStop = settings.trailing_stop_enabled;

  const currentPrice = position?.mid_price || position?.mark_price || 0;
  const entryPrice = position?.entry_price || 0;

  // Calculate stop-loss display
  const getStopLossDisplay = () => {
    if (settings.stop_loss_price) {
      return `$${settings.stop_loss_price.toFixed(0)}`;
    } else if (settings.stop_loss_pct) {
      return `${Math.abs(settings.stop_loss_pct).toFixed(0)}%`;
    }
    return null;
  };

  // Calculate take-profit display
  const getTakeProfitDisplay = () => {
    if (settings.take_profit_price) {
      return `$${settings.take_profit_price.toFixed(0)}`;
    } else if (settings.take_profit_pct) {
      return `+${settings.take_profit_pct.toFixed(0)}%`;
    }
    return null;
  };

  // Calculate distance to SL/TP
  const getStopLossDistance = () => {
    if (!currentPrice || !entryPrice) return null;

    if (settings.stop_loss_price) {
      const distance = ((currentPrice - settings.stop_loss_price) / currentPrice) * 100;
      return distance.toFixed(1);
    } else if (settings.stop_loss_pct) {
      const pnlPct = ((currentPrice - entryPrice) / entryPrice) * 100;
      const distance = pnlPct - settings.stop_loss_pct;
      return distance.toFixed(1);
    }
    return null;
  };

  const getTakeProfitDistance = () => {
    if (!currentPrice || !entryPrice) return null;

    if (settings.take_profit_price) {
      const distance = ((settings.take_profit_price - currentPrice) / currentPrice) * 100;
      return distance.toFixed(1);
    } else if (settings.take_profit_pct) {
      const pnlPct = ((currentPrice - entryPrice) / entryPrice) * 100;
      const distance = settings.take_profit_pct - pnlPct;
      return distance.toFixed(1);
    }
    return null;
  };

  const slDisplay = getStopLossDisplay();
  const tpDisplay = getTakeProfitDisplay();
  const slDistance = getStopLossDistance();
  const tpDistance = getTakeProfitDistance();

  // Check if close to trigger
  const isCloseToSL = slDistance !== null && parseFloat(slDistance) < 5;
  const isCloseToTP = tpDistance !== null && parseFloat(tpDistance) < 5;

  return (
    <Box
      display="flex"
      gap={0.5}
      alignItems="center"
      onClick={onEdit}
      sx={{ cursor: 'pointer', '&:hover': { opacity: 0.8 } }}
    >
      {hasStopLoss && (
        <Tooltip
          title={
            <Box>
              <Typography variant="caption" display="block">
                <strong>Stop-Loss</strong>
              </Typography>
              {settings.stop_loss_price && (
                <Typography variant="caption" display="block">
                  Price: ${settings.stop_loss_price.toFixed(2)}
                </Typography>
              )}
              {settings.stop_loss_pct && (
                <Typography variant="caption" display="block">
                  Loss: {Math.abs(settings.stop_loss_pct).toFixed(1)}%
                </Typography>
              )}
              {slDistance && (
                <Typography variant="caption" display="block">
                  Distance: {slDistance}% away
                </Typography>
              )}
              <Typography
                variant="caption"
                display="block"
                sx={{ mt: 0.5, color: 'warning.light' }}
              >
                {settings.auto_execute ? '⚡ Auto-execute' : '🔔 Alert only'}
              </Typography>
            </Box>
          }
          arrow
        >
          <Chip
            icon={<TrendingDown sx={{ fontSize: 14 }} />}
            label={slDisplay}
            size="small"
            color="error"
            variant={isCloseToSL ? 'filled' : 'outlined'}
            sx={{
              height: 20,
              fontSize: 10,
              '& .MuiChip-icon': { fontSize: 12 },
              animation: isCloseToSL ? 'pulse 1s infinite' : 'none',
              '@keyframes pulse': {
                '0%': { opacity: 1 },
                '50%': { opacity: 0.6 },
                '100%': { opacity: 1 },
              },
            }}
          />
        </Tooltip>
      )}

      {hasTakeProfit && (
        <Tooltip
          title={
            <Box>
              <Typography variant="caption" display="block">
                <strong>Take-Profit Target</strong>
              </Typography>
              {settings.take_profit_price && (
                <Typography variant="caption" display="block">
                  Price: ${settings.take_profit_price.toFixed(2)}
                </Typography>
              )}
              {settings.take_profit_pct && (
                <Typography variant="caption" display="block">
                  Profit: {settings.take_profit_pct.toFixed(1)}%
                </Typography>
              )}
              {tpDistance && (
                <Typography variant="caption" display="block">
                  Distance: {tpDistance}% away
                </Typography>
              )}
              <Typography
                variant="caption"
                display="block"
                sx={{ mt: 0.5, color: 'warning.light' }}
              >
                {settings.auto_execute ? '⚡ Auto-execute' : '🔔 Alert only'}
              </Typography>
            </Box>
          }
          arrow
        >
          <Chip
            icon={<TrendingUp sx={{ fontSize: 14 }} />}
            label={tpDisplay}
            size="small"
            color="success"
            variant={isCloseToTP ? 'filled' : 'outlined'}
            sx={{
              height: 20,
              fontSize: 10,
              '& .MuiChip-icon': { fontSize: 12 },
              animation: isCloseToTP ? 'pulse 1s infinite' : 'none',
            }}
          />
        </Tooltip>
      )}

      {hasTrailingStop && (
        <Tooltip title={`Trailing Stop: ${settings.trailing_stop_pct}%`}>
          <Chip
            label="T"
            size="small"
            color="warning"
            variant="outlined"
            sx={{
              height: 20,
              fontSize: 10,
              minWidth: 20,
            }}
          />
        </Tooltip>
      )}

      {/* Edit button */}
      <Tooltip title="Edit SL/TP">
        <IconButton size="small" sx={{ p: 0.25, ml: 0.25 }}>
          <Edit sx={{ fontSize: 12 }} />
        </IconButton>
      </Tooltip>
    </Box>
  );
}
