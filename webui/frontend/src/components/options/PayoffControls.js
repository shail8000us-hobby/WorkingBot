/**
 * PayoffControls — Target price slider + Date/time slider controls
 *
 * Extracted from OptionsPayoffDiagram.js (D5) to separate
 * interactive controls from chart rendering.
 *
 * @version 1.0.0
 */

import React, { useState } from 'react';
import {
  Box, Typography, Chip, Slider, IconButton,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import ExpandLessRoundedIcon from '@mui/icons-material/ExpandLessRounded';
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded';
import { formatDate } from './payoffCalculator';

const ACCENT_BLUE = '#60a5fa';
const ACCENT_CYAN = '#22d3ee';
const ACCENT_PURPLE = '#a855f7';
const ACCENT_GOLD = '#fbbf24';

const panelShellSx = (accentA = ACCENT_BLUE, accentB = ACCENT_PURPLE) => ({
  mt: 2,
  px: 2,
  py: 1.6,
  borderRadius: 2.2,
  border: `1px solid ${alpha(accentA, 0.42)}`,
  bgcolor: alpha('#020617', 0.88),
  backgroundImage: `
    radial-gradient(circle at 10% 0%, ${alpha(accentA, 0.18)} 0%, transparent 38%),
    radial-gradient(circle at 90% 0%, ${alpha(accentB, 0.14)} 0%, transparent 42%),
    linear-gradient(180deg, ${alpha('#0f172a', 0.9)} 0%, ${alpha('#020617', 0.95)} 100%)
  `,
  boxShadow: `
    inset 0 1px 0 ${alpha('#e2e8f0', 0.1)},
    0 0 0 1px ${alpha(accentA, 0.15)},
    0 12px 30px ${alpha('#000', 0.5)},
    0 0 22px ${alpha(accentA, 0.16)}
  `,
  backdropFilter: 'blur(10px)',
});

const iconControlSx = (accent = ACCENT_BLUE) => ({
  width: 28,
  height: 28,
  borderRadius: 999,
  bgcolor: alpha('#020617', 0.52),
  border: `1px solid ${alpha(accent, 0.5)}`,
  color: alpha('#e2e8f0', 0.95),
  '&:hover': {
    bgcolor: alpha(accent, 0.18),
    borderColor: alpha(accent, 0.75),
  },
});

const sliderSx = (accent = ACCENT_BLUE) => ({
  color: accent,
  mt: 0.6,
  '& .MuiSlider-thumb': {
    width: 14,
    height: 14,
    boxShadow: `0 0 0 3px ${alpha(accent, 0.25)}`,
    '&:hover, &.Mui-focusVisible': {
      boxShadow: `0 0 0 5px ${alpha(accent, 0.3)}`,
    },
  },
  '& .MuiSlider-track': { height: 4, border: 'none' },
  '& .MuiSlider-rail': { height: 4, bgcolor: alpha('#94a3b8', 0.2) },
  '& .MuiSlider-mark': {
    width: 4,
    height: 4,
    borderRadius: '50%',
    bgcolor: alpha('#cbd5e1', 0.55),
  },
  '& .MuiSlider-markLabel': {
    color: alpha('#94a3b8', 0.82),
    fontSize: '0.66rem',
    fontWeight: 700,
    letterSpacing: '0.02em',
  },
});

const statusChipSx = (accent = ACCENT_BLUE, active = false) => ({
  height: 20,
  borderRadius: 999,
  fontSize: '0.64rem',
  fontWeight: 800,
  letterSpacing: '0.04em',
  textTransform: 'uppercase',
  bgcolor: active ? alpha(accent, 0.22) : alpha('#64748b', 0.2),
  color: active ? accent : alpha('#cbd5e1', 0.82),
  border: `1px solid ${active ? alpha(accent, 0.5) : alpha('#64748b', 0.35)}`,
  '& .MuiChip-label': { px: 0.85 },
});

const sectionCardSx = (accent = ACCENT_BLUE) => ({
  px: 1.1,
  py: 0.95,
  borderRadius: 1.7,
  border: `1px solid ${alpha(accent, 0.36)}`,
  bgcolor: alpha('#020617', 0.45),
  boxShadow: `
    inset 0 1px 0 ${alpha('#e2e8f0', 0.06)},
    0 0 0 1px ${alpha(accent, 0.12)}
  `,
});

/**
 * @param {Object} props
 * @param {number} props.targetPricePercent - Target price offset from spot (%)
 * @param {Function} props.setTargetPricePercent - Setter for target price percent
 * @param {number} props.targetPrice - Computed target price ($)
 * @param {number} props.targetDaysFromNow - Days from now for target date
 * @param {Function} props.setTargetDaysFromNow - Setter for target days
 * @param {Date} props.targetDate - Computed target date
 * @param {number} props.daysToExpiryFromTarget - Days remaining from target to expiry
 * @param {number} props.minDaysToExpiry - Nearest expiry in days (used as fallback)
 * @param {number} [props.maxDaysToExpiry] - Furthest expiry in days (slider max)
 * @param {Date} props.nearestExpiry - Nearest expiry date
 * @param {Date} [props.furthestExpiry] - Furthest expiry date (right-end label)
 * @param {Array} [props.allExpiryMarks] - Per-expiry tick marks for the slider
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
  maxDaysToExpiry,
  nearestExpiry,
  furthestExpiry,
  allExpiryMarks,
}) => {
  const [controlsCollapsed, setControlsCollapsed] = useState(true);

  const sliderMax = maxDaysToExpiry ?? minDaysToExpiry;
  const normalizedDaysToExpiry = Math.max(0, daysToExpiryFromTarget);
  const expiryDays = Math.floor(normalizedDaysToExpiry);
  const expiryHours = Math.round((normalizedDaysToExpiry % 1) * 24);
  const isZeroDte = normalizedDaysToExpiry < 1;

  const dateMarks = allExpiryMarks ?? [
    { value: 0, label: 'Now' },
    {
      value: sliderMax,
      label: sliderMax < 1
        ? `${Math.round(sliderMax * 24)}h`
        : `${Math.ceil(sliderMax)}d`,
    },
  ];
  const rightExpiry = furthestExpiry ?? nearestExpiry;

  return (
    <Box sx={panelShellSx(ACCENT_BLUE, ACCENT_PURPLE)}>
      {/* Unified header + collapse toggle */}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 1,
          flexWrap: { xs: 'wrap', lg: 'nowrap' },
          mb: controlsCollapsed ? 0 : 1.1,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap' }}>
          <Typography
            variant="body2"
            sx={{
              color: alpha('#e2e8f0', 0.97),
              fontWeight: 900,
              letterSpacing: '0.04em',
              textTransform: 'none',
            }}
          >
            Target & Expiry Controls
          </Typography>
          <Chip
            label={`BTC ${targetPricePercent >= 0 ? '+' : ''}${targetPricePercent.toFixed(1)}%`}
            size="small"
            sx={statusChipSx(ACCENT_BLUE, true)}
          />
          <Chip
            label={`$${targetPrice.toLocaleString()}`}
            size="small"
            sx={statusChipSx(ACCENT_CYAN, true)}
          />
          <Chip
            label={`${expiryDays}D ${expiryHours}H${isZeroDte ? ' • 0 DTE' : ''}`}
            size="small"
            sx={statusChipSx(isZeroDte ? ACCENT_GOLD : ACCENT_PURPLE, true)}
          />
        </Box>

        <Chip
          icon={controlsCollapsed
            ? <ExpandMoreRoundedIcon sx={{ fontSize: 16 }} />
            : <ExpandLessRoundedIcon sx={{ fontSize: 16 }} />}
          label={controlsCollapsed ? 'Show Controls' : 'Hide Controls'}
          size="small"
          onClick={() => setControlsCollapsed((prev) => !prev)}
          sx={{
            ...statusChipSx(ACCENT_BLUE, true),
            cursor: 'pointer',
            '& .MuiChip-label': { px: 0.75, fontWeight: 900 },
            '& .MuiChip-icon': { ml: 0.55, mr: -0.2, color: ACCENT_BLUE },
          }}
        />
      </Box>

      {!controlsCollapsed && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.05 }}>
          {/* BTC Target Price Slider */}
          <Box sx={sectionCardSx(ACCENT_BLUE)}>
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: 1,
                flexWrap: { xs: 'wrap', sm: 'nowrap' },
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.85, flexWrap: 'wrap' }}>
                <Typography
                  variant="body2"
                  sx={{ color: alpha('#e2e8f0', 0.96), fontWeight: 900, letterSpacing: '0.04em' }}
                >
                  BTC Target
                </Typography>
                <Chip
                  label={targetPricePercent === 0 ? 'ATM' : 'Custom'}
                  size="small"
                  sx={statusChipSx(targetPricePercent === 0 ? ACCENT_GOLD : ACCENT_BLUE, true)}
                />
                <Chip
                  label="Reset to ATM"
                  size="small"
                  onClick={() => setTargetPricePercent(0)}
                  disabled={targetPricePercent === 0}
                  sx={{
                    ...statusChipSx(ACCENT_BLUE, targetPricePercent !== 0),
                    cursor: targetPricePercent === 0 ? 'default' : 'pointer',
                  }}
                />
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap' }}>
                <Typography variant="caption" sx={{ color: alpha('#93c5fd', 0.95), fontWeight: 800 }}>
                  {targetPricePercent >= 0 ? '+' : ''}{targetPricePercent.toFixed(1)}%
                </Typography>
                <IconButton
                  size="small"
                  onClick={() => setTargetPricePercent((p) => Math.max(-30, p - 1))}
                  sx={iconControlSx(ACCENT_BLUE)}
                >
                  <Typography sx={{ fontWeight: 'bold', fontSize: 16 }}>−</Typography>
                </IconButton>
                <Box
                  sx={{
                    px: 1.1,
                    py: 0.45,
                    borderRadius: 999,
                    border: `1px solid ${alpha(ACCENT_BLUE, 0.45)}`,
                    bgcolor: alpha('#020617', 0.54),
                    minWidth: 96,
                    textAlign: 'center',
                  }}
                >
                  <Typography variant="body2" fontWeight="bold" sx={{ color: '#dbeafe' }}>
                    ${targetPrice.toLocaleString()}
                  </Typography>
                </Box>
                <IconButton
                  size="small"
                  onClick={() => setTargetPricePercent((p) => Math.min(30, p + 1))}
                  sx={iconControlSx(ACCENT_BLUE)}
                >
                  <Typography sx={{ fontWeight: 'bold', fontSize: 16 }}>+</Typography>
                </IconButton>
              </Box>
            </Box>
            <Box sx={{ px: 0.45 }}>
              <Slider
                value={targetPricePercent}
                onChange={(e, v) => setTargetPricePercent(Array.isArray(v) ? v[0] : v)}
                min={-30} max={30} step={0.5}
                sx={sliderSx(ACCENT_BLUE)}
              />
            </Box>
          </Box>

          {/* Date/Time Slider Section */}
          <Box sx={sectionCardSx(ACCENT_CYAN)}>
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                mb: 1,
                gap: 1,
                flexWrap: { xs: 'wrap', sm: 'nowrap' },
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap' }}>
                <Typography variant="caption" sx={{ color: alpha('#cbd5e1', 0.92), fontWeight: 800, letterSpacing: '0.04em' }}>
                  Time to expiry
                </Typography>
                <Chip
                  label={`${expiryDays}D ${expiryHours}H`}
                  size="small"
                  sx={statusChipSx(isZeroDte ? ACCENT_GOLD : ACCENT_CYAN, true)}
                />
                {isZeroDte && (
                  <Chip
                    label="0 DTE"
                    size="small"
                    sx={statusChipSx(ACCENT_GOLD, true)}
                  />
                )}
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.6, flexWrap: 'wrap' }}>
                <IconButton
                  size="small"
                  onClick={() => setTargetDaysFromNow((d) => Math.max(0, d - 1 / 24))}
                  title="-1 hour"
                  sx={iconControlSx(ACCENT_CYAN)}
                >
                  <ChevronLeftIcon fontSize="small" />
                </IconButton>
                <Box
                  sx={{
                    px: 1.15,
                    py: 0.5,
                    borderRadius: 999,
                    border: `1px solid ${alpha(ACCENT_CYAN, 0.45)}`,
                    bgcolor: alpha('#020617', 0.54),
                    minWidth: 200,
                    textAlign: 'center',
                  }}
                >
                  <Typography variant="body2" sx={{ color: alpha('#e2e8f0', 0.94), fontWeight: 700 }}>
                    {formatDate(targetDate)}
                  </Typography>
                </Box>
                <IconButton
                  size="small"
                  onClick={() => setTargetDaysFromNow((d) => Math.min(sliderMax, d + 1 / 24))}
                  title="+1 hour"
                  sx={iconControlSx(ACCENT_CYAN)}
                >
                  <ChevronRightIcon fontSize="small" />
                </IconButton>
              </Box>
            </Box>

            <Box sx={{ px: 0.45 }}>
              <Slider
                value={targetDaysFromNow}
                onChange={(e, v) => setTargetDaysFromNow(Array.isArray(v) ? v[0] : v)}
                min={0} max={sliderMax} step={1 / 24}
                marks={dateMarks}
                sx={sliderSx(ACCENT_CYAN)}
              />

              <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: -0.4 }}>
                <Typography variant="caption" sx={{ color: alpha('#94a3b8', 0.9), fontWeight: 700 }}>
                  Now
                </Typography>
                <Typography variant="caption" sx={{ color: alpha('#94a3b8', 0.9), fontWeight: 700 }}>
                  {rightExpiry && (sliderMax < 1
                    ? `${rightExpiry.toLocaleDateString('en-US', { day: '2-digit', month: 'short' })} 5:30 PM IST`
                    : rightExpiry.toLocaleDateString('en-US', { day: '2-digit', month: 'short' }))}
                </Typography>
              </Box>
            </Box>
          </Box>
        </Box>
      )}
    </Box>
  );
});

PayoffControls.displayName = 'PayoffControls';

export default PayoffControls;
