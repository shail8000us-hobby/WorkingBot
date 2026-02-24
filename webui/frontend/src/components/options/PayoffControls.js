/**
 * PayoffControls — Target price slider + Date/time slider controls
 *
 * Extracted from OptionsPayoffDiagram.js (D5) to separate
 * interactive controls from chart rendering.
 *
 * @version 1.0.0
 */

import React from 'react';
import {
  Box, Typography, Chip, Slider, IconButton,
} from '@mui/material';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { formatDate } from './payoffCalculator';

/**
 * @param {Object} props
 * @param {number} props.targetPricePercent - Target price offset from spot (%)
 * @param {Function} props.setTargetPricePercent - Setter for target price percent
 * @param {number} props.targetPrice - Computed target price ($)
 * @param {number} props.targetDaysFromNow - Days from now for target date
 * @param {Function} props.setTargetDaysFromNow - Setter for target days
 * @param {Date} props.targetDate - Computed target date
 * @param {number} props.daysToExpiryFromTarget - Days remaining from target to expiry
 * @param {number} props.minDaysToExpiry - Max value for date slider
 * @param {Date} props.nearestExpiry - Nearest expiry date
 */
const PayoffControls = React.memo(({
  targetPricePercent,
  setTargetPricePercent,
  targetPrice,
  targetDaysFromNow,
  setTargetDaysFromNow,
  targetDate,
  daysToExpiryFromTarget,
  minDaysToExpiry,
  nearestExpiry,
}) => {
  const dateMarks = [
    { value: 0, label: 'Now' },
    {
      value: minDaysToExpiry,
      label: minDaysToExpiry < 1
        ? `${Math.round(minDaysToExpiry * 24)}h`
        : `${Math.ceil(minDaysToExpiry)}d`,
    },
  ];

  return (
    <>
      {/* BTC Target Price Slider */}
      <Box sx={{ mt: 2, px: 2, py: 1.5, bgcolor: 'rgba(0,0,0,0.3)', borderRadius: 1 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="body2" fontWeight="bold">
              BTC Target
            </Typography>
            <Chip
              label={targetPricePercent === 0 ? 'ATM' : 'Custom'}
              size="small"
              sx={{
                height: 18, fontSize: 10,
                bgcolor: targetPricePercent === 0 ? 'rgba(251, 191, 36, 0.2)' : 'rgba(59, 130, 246, 0.2)',
                color: targetPricePercent === 0 ? '#fbbf24' : '#3b82f6',
              }}
            />
            <Typography
              variant="caption"
              onClick={() => setTargetPricePercent(0)}
              sx={{ color: '#3b82f6', cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
            >
              Reset to ATM
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="body2" color="text.secondary">
              {targetPricePercent >= 0 ? '+' : ''}{targetPricePercent.toFixed(1)}%
            </Typography>
            <IconButton size="small" onClick={() => setTargetPricePercent((p) => Math.max(-30, p - 1))}>
              <Typography sx={{ fontWeight: 'bold', fontSize: 16 }}>−</Typography>
            </IconButton>
            <Typography variant="body2" fontWeight="bold" sx={{ minWidth: 80, textAlign: 'center' }}>
              ${targetPrice.toLocaleString()}
            </Typography>
            <IconButton size="small" onClick={() => setTargetPricePercent((p) => Math.min(30, p + 1))}>
              <Typography sx={{ fontWeight: 'bold', fontSize: 16 }}>+</Typography>
            </IconButton>
          </Box>
        </Box>
        <Slider
          value={targetPricePercent}
          onChange={(e, v) => setTargetPricePercent(v)}
          min={-30} max={30} step={0.5}
          sx={{
            color: '#3b82f6', mt: 0.5,
            '& .MuiSlider-thumb': { width: 14, height: 14 },
            '& .MuiSlider-track': { height: 3 },
            '& .MuiSlider-rail': { height: 3, bgcolor: 'rgba(255,255,255,0.1)' },
          }}
        />
      </Box>

      {/* Date/Time Slider Section */}
      <Box sx={{ mt: 2, px: 2, py: 2, bgcolor: 'rgba(0,0,0,0.2)', borderRadius: 1 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Box>
            <Typography variant="caption" color="text.secondary">
              Time to expiry: {Math.floor(daysToExpiryFromTarget)}D{' '}
              {Math.round((daysToExpiryFromTarget % 1) * 24)}H
              {daysToExpiryFromTarget < 1 && ' (0 DTE)'}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <IconButton size="small" onClick={() => setTargetDaysFromNow((d) => Math.max(0, d - 1 / 24))} title="-1 hour">
              <ChevronLeftIcon fontSize="small" />
            </IconButton>
            <Typography variant="body2" sx={{ minWidth: 180, textAlign: 'center' }}>
              {formatDate(targetDate)}
            </Typography>
            <IconButton size="small" onClick={() => setTargetDaysFromNow((d) => Math.min(minDaysToExpiry, d + 1 / 24))} title="+1 hour">
              <ChevronRightIcon fontSize="small" />
            </IconButton>
          </Box>
        </Box>
        <Box sx={{ px: 1 }}>
          <Slider
            value={targetDaysFromNow}
            onChange={(e, v) => setTargetDaysFromNow(v)}
            min={0} max={minDaysToExpiry} step={1 / 24}
            marks={dateMarks}
            sx={{
              color: '#3b82f6',
              '& .MuiSlider-thumb': { width: 16, height: 16 },
              '& .MuiSlider-track': { height: 4 },
              '& .MuiSlider-rail': { height: 4, bgcolor: 'rgba(255,255,255,0.1)' },
            }}
          />
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: -1 }}>
            <Typography variant="caption" color="text.secondary">Now</Typography>
            <Typography variant="caption" color="text.secondary">
              {minDaysToExpiry < 1
                ? `${nearestExpiry.toLocaleDateString('en-US', { day: '2-digit', month: 'short' })} 5:30 PM IST`
                : nearestExpiry.toLocaleDateString('en-US', { day: '2-digit', month: 'short' })}
            </Typography>
          </Box>
        </Box>
      </Box>
    </>
  );
});

PayoffControls.displayName = 'PayoffControls';

export default PayoffControls;
