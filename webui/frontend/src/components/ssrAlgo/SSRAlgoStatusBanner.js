/**
 * SSR Algo Status Banner
 * 
 * Status bar showing real-time monitoring information.
 * Displays current price, zone status, dwell progress, and trading status.
 * 
 * Per Architecture Doc: Section 8.2, 8.3
 * 
 * Created: February 2, 2026
 */

import React from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Paper,
  Typography,
  Chip,
  LinearProgress,
  Tooltip,
} from '@mui/material';
import {
  FiberManualRecord as DotIcon,
  TrendingUp as UpIcon,
  TrendingDown as DownIcon,
  Warning as WarningIcon,
  Pause as PauseIcon,
  PlayArrow as PlayIcon,
  CheckCircle as ActiveIcon,
  Error as ErrorIcon,
  Timer as TimerIcon,
} from '@mui/icons-material';

// Status configurations per architecture doc section 8.3
const STATUS_CONFIG = {
  IDLE: { 
    color: '#6b7280', 
    label: '⚪ Ready', 
    bgColor: 'rgba(107, 114, 128, 0.15)',
    borderColor: 'rgba(107, 114, 128, 0.3)'
  },
  SELECTING_STRIKES: { 
    color: '#3b82f6', 
    label: '🔵 Selecting Strikes...', 
    bgColor: 'rgba(59, 130, 246, 0.15)',
    borderColor: 'rgba(59, 130, 246, 0.3)',
    pulse: true
  },
  EXECUTING_AUTO_LOOP: { 
    color: '#f59e0b', 
    label: '🟡 Executing Rounds...', 
    bgColor: 'rgba(245, 158, 11, 0.15)',
    borderColor: 'rgba(245, 158, 11, 0.3)',
    pulse: true
  },
  MONITORING: { 
    color: '#22c55e', 
    label: '🟢 Monitoring', 
    bgColor: 'rgba(34, 197, 94, 0.15)',
    borderColor: 'rgba(34, 197, 94, 0.3)'
  },
  PAUSED: { 
    color: '#f97316', 
    label: '🟠 Paused', 
    bgColor: 'rgba(249, 115, 22, 0.15)',
    borderColor: 'rgba(249, 115, 22, 0.3)'
  },
  STOPPED: { 
    color: '#ef4444', 
    label: '🔴 Stopped', 
    bgColor: 'rgba(239, 68, 68, 0.15)',
    borderColor: 'rgba(239, 68, 68, 0.3)'
  },
  IN_MAX_LOSS_ZONE: { 
    color: '#ef4444', 
    label: '⚠️ MAX LOSS ZONE!', 
    bgColor: 'rgba(239, 68, 68, 0.25)',
    borderColor: 'rgba(239, 68, 68, 0.5)',
    flash: true
  },
};

/**
 * SSR Algo Status Banner Component
 */
const SSRAlgoStatusBanner = ({ 
  session, 
  monitorStatus, 
  payoffData,
  currentPrice = null 
}) => {
  const status = session?.status || 'IDLE';
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.IDLE;
  
  // Check if in max loss zone (use !! to avoid undefined !== null being true)
  const dwellStatus = monitorStatus?.dwell_status || {};
  const inMaxLossZone = !!dwellStatus.current_zone;
  const displayConfig = inMaxLossZone ? STATUS_CONFIG.IN_MAX_LOSS_ZONE : config;
  
  // Calculate dwell progress
  const dwellProgress = dwellStatus.dwell_threshold_minutes 
    ? (dwellStatus.time_in_zone_minutes / dwellStatus.dwell_threshold_minutes) * 100
    : 0;

  // Determine price direction
  const price = currentPrice || monitorStatus?.last_price;
  const atmStrike = payoffData?.atm_strike || session?.positions?.[0]?.atm_strike;
  const priceDirection = price && atmStrike 
    ? (price > atmStrike ? 'up' : price < atmStrike ? 'down' : 'neutral')
    : 'neutral';

  // Format active time
  const getActiveTime = () => {
    if (!session?.started_at) return null;
    const start = new Date(session.started_at);
    const now = new Date();
    const mins = Math.floor((now - start) / 60000);
    if (mins < 60) return `${mins}m`;
    return `${Math.floor(mins / 60)}h ${mins % 60}m`;
  };

  return (
    <Paper
      sx={{
        p: 1,
        mb: 0,
        bgcolor: displayConfig.bgColor,
        border: `1px solid ${displayConfig.borderColor}`,
        borderRadius: 2,
        animation: displayConfig.flash ? 'flash 1s infinite' : 
                   displayConfig.pulse ? 'pulse 2s infinite' : 'none',
        '@keyframes flash': {
          '0%, 50%, 100%': { opacity: 1 },
          '25%, 75%': { opacity: 0.6 },
        },
        '@keyframes pulse': {
          '0%, 100%': { opacity: 1 },
          '50%': { opacity: 0.7 },
        },
      }}
    >
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
        
        {/* Status Label */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography 
            variant="h6" 
            sx={{ 
              fontWeight: 700, 
              color: displayConfig.color,
              letterSpacing: inMaxLossZone ? '1px' : 'normal',
            }}
          >
            {displayConfig.label}
          </Typography>
          {session?.underlying && (
            <Chip 
              size="small" 
              label={session.underlying}
              sx={{ 
                fontWeight: 600,
                bgcolor: 'rgba(255,255,255,0.1)',
                color: '#e2e8f0'
              }}
            />
          )}
        </Box>

        {/* Current Price */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="caption" color="text.secondary">Current Price</Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              {priceDirection === 'up' && <UpIcon sx={{ color: '#4ade80', fontSize: 18 }} />}
              {priceDirection === 'down' && <DownIcon sx={{ color: '#f87171', fontSize: 18 }} />}
              <Typography 
                variant="h6" 
                sx={{ 
                  fontWeight: 700, 
                  fontFamily: 'monospace',
                  color: priceDirection === 'up' ? '#4ade80' : 
                         priceDirection === 'down' ? '#f87171' : '#f1f5f9'
                }}
              >
                {price ? `$${price.toLocaleString()}` : '—'}
              </Typography>
            </Box>
          </Box>

          {/* ATM Reference */}
          {atmStrike && (
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary">ATM Strike</Typography>
              <Typography variant="body1" sx={{ fontWeight: 600, fontFamily: 'monospace' }}>
                ${atmStrike.toLocaleString()}
              </Typography>
            </Box>
          )}

          {/* Max Loss Zones */}
          {payoffData?.adjustment_triggers?.lower_trigger && payoffData?.adjustment_triggers?.upper_trigger && (
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary">Next Trigger</Typography>
              <Box sx={{ display: 'flex', gap: 1, flexDirection: 'column', alignItems: 'center' }}>
                {price && (() => {
                  const lowerTrigger = payoffData.adjustment_triggers.lower_trigger;
                  const upperTrigger = payoffData.adjustment_triggers.upper_trigger;
                  const distanceToLower = Math.abs(price - lowerTrigger);
                  const distanceToUpper = Math.abs(price - upperTrigger);
                  const nearestTrigger = distanceToLower < distanceToUpper ? lowerTrigger : upperTrigger;
                  const distance = Math.min(distanceToLower, distanceToUpper);
                  const isLower = nearestTrigger === lowerTrigger;
                  const percentage = ((distance / price) * 100).toFixed(1);
                  
                  return (
                    <>
                      <Tooltip title={`${isLower ? 'Lower' : 'Upper'} trigger at $${nearestTrigger.toLocaleString()}`}>
                        <Chip 
                          size="small"
                          icon={isLower ? <DownIcon sx={{ fontSize: '14px !important' }} /> : <UpIcon sx={{ fontSize: '14px !important' }} />}
                          label={`$${(nearestTrigger / 1000).toFixed(1)}k ${isLower ? '↓' : '↑'}${(distance / 1000).toFixed(1)}k (${percentage}%)`}
                          sx={{ 
                            bgcolor: percentage < 5 ? 'rgba(239, 68, 68, 0.3)' : 'rgba(239, 68, 68, 0.2)',
                            color: percentage < 5 ? '#fca5a5' : '#f87171',
                            fontWeight: percentage < 5 ? 700 : 600,
                            fontSize: '0.7rem',
                            border: percentage < 5 ? '1px solid rgba(239, 68, 68, 0.5)' : 'none',
                          }}
                        />
                      </Tooltip>
                    </>
                  );
                })()}
              </Box>
            </Box>
          )}

          {/* Triggers Count / Rounds */}
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="caption" color="text.secondary">Rounds</Typography>
            <Typography variant="h6" sx={{ fontWeight: 700, color: '#818cf8' }}>
              {session?.rounds_completed || 0} / {session?.auto_loop_rounds || 2}
            </Typography>
          </Box>

          {/* Open Positions */}
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="caption" color="text.secondary">Open Legs</Typography>
            <Typography variant="body1" sx={{ fontWeight: 600 }}>
              {(session?.rounds_completed || 0) * 6}
            </Typography>
          </Box>

          {/* Expiry */}
          {session?.expiry && (
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary">Expiry</Typography>
              <Typography variant="body1" sx={{ fontWeight: 600, fontFamily: 'monospace', color: '#fbbf24' }}>
                {session.expiry}
              </Typography>
            </Box>
          )}

          {/* Time Window */}
          {session?.start_time && session?.end_time && (
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary">Time Window</Typography>
              <Typography variant="body2" sx={{ fontWeight: 600, fontFamily: 'monospace' }}>
                {session.start_time} - {session.end_time}
              </Typography>
            </Box>
          )}

          {/* Adjustments Count */}
          {(session?.trigger_count || 0) > 0 && (
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary">Adjustments</Typography>
              <Typography variant="body1" sx={{ fontWeight: 600, color: '#f59e0b' }}>
                {session.trigger_count}
              </Typography>
            </Box>
          )}

          {/* Active Time */}
          {getActiveTime() && (
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary">Active</Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <TimerIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
                <Typography variant="body1" sx={{ fontWeight: 600 }}>
                  {getActiveTime()}
                </Typography>
              </Box>
            </Box>
          )}
        </Box>
      </Box>

      {/* Dwell Progress Bar (when in max loss zone) */}
      {inMaxLossZone && (
        <Box sx={{ mt: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
            <Typography variant="caption" sx={{ color: '#f87171', fontWeight: 600 }}>
              ⚠️ In {dwellStatus.current_zone?.toUpperCase() || 'MAX LOSS'} zone for {(dwellStatus.time_in_zone_minutes || 0).toFixed(1)} min
            </Typography>
            <Typography variant="caption" sx={{ color: '#f87171' }}>
              Trigger at {dwellStatus.dwell_threshold_minutes} min
            </Typography>
          </Box>
          <LinearProgress 
            variant="determinate" 
            value={Math.min(100, dwellProgress)}
            sx={{
              height: 8,
              borderRadius: 4,
              bgcolor: 'rgba(239, 68, 68, 0.2)',
              '& .MuiLinearProgress-bar': {
                bgcolor: dwellProgress > 80 ? '#ef4444' : '#f59e0b',
                borderRadius: 4,
              }
            }}
          />
        </Box>
      )}
    </Paper>
  );
};

SSRAlgoStatusBanner.propTypes = {
  session: PropTypes.object,
  monitorStatus: PropTypes.object,
  payoffData: PropTypes.object,
  currentPrice: PropTypes.number,
};

export default SSRAlgoStatusBanner;
