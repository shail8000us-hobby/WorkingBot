/**
 * MMMStatusBanner — Money Mind & Method
 *
 * Top status bar showing:
 * - RUNNING/PAUSED/STOPPED/BOTH_SIDES_UP status with colored indicator
 * - Contextual explanation of what the algo is doing and why
 * - Adjustment count + counters
 * - Elapsed time since entry
 * - Interval countdown timer
 * - Reversal indicator with cooldown
 * - Expiry countdown with color transitions
 *
 * Maps to MONEY_POWER_CALCULATION_LOGIC.md §4, §8
 *
 * Created: February 15, 2026
 * Updated: February 16, 2026 — Added contextual status explanations,
 *          Both Sides Up inline guidance with action buttons
 */

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Box,
  Typography,
  Chip,
  Tooltip,
  Button,
  LinearProgress,
} from '@mui/material';
import {
  Circle as CircleIcon,
  SwapHoriz as ReversalIcon,
  Timer as TimerIcon,
  TrendingUp as TrendingUpIcon,
  Warning as WarningIcon,
  PlayArrow as ResumeIcon,
  Stop as StopIcon,
  Pause as PauseIcon,
} from '@mui/icons-material';

const STATUS_COLORS = {
  RUNNING: '#4caf50',
  STARTING: '#2196f3',
  PAUSED: '#ff9800',
  BOTH_SIDES_UP: '#f44336',
  PARTIAL_ENTRY: '#ff5722',
  STOPPED: '#757575',
  IDLE: '#9e9e9e',
  ERROR: '#f44336',
};

/**
 * Contextual explanation of what the algo is doing based on its status.
 * This is the key missing piece — tell the user WHY and WHAT.
 */
const STATUS_CONTEXT = {
  RUNNING: {
    short: 'Monitoring',
    detail: 'Heartbeat loop active — checking premiums every interval. If one side exceeds its trigger, the opposite side will be sold to hedge.',
    icon: '🟢',
  },
  STARTING: {
    short: 'Placing Orders',
    detail: 'Placing CE + PE entry orders on the exchange. Waiting for fills...',
    icon: '🔵',
  },
  PAUSED: {
    short: 'Paused',
    detail: 'Heartbeat loop paused — positions remain open but no monitoring or adjustments. Resume to restart monitoring.',
    icon: '🟡',
  },
  BOTH_SIDES_UP: {
    short: '⚠️ Action Required',
    detail: 'Both CE and PE premiums exceeded their triggers simultaneously. The algo is PAUSED — it cannot auto-adjust because selling either side would increase risk. You must decide what to do.',
    icon: '🔴',
  },
  PARTIAL_ENTRY: {
    short: '⚠️ Intervention Required',
    detail: 'One entry leg filled but the other failed. Use "Retry Leg" to attempt re-execution, or "Both Filled" if you manually filled it on the exchange.',
    icon: '⚠️',
  },
  STOPPED: {
    short: 'Stopped',
    detail: 'Strategy stopped. Positions may still be open on the exchange — manage them manually or start a new session.',
    icon: '⏹',
  },
  IDLE: {
    short: 'Not Started',
    detail: 'Session configured but not started. Initialize with desired parameters and start to begin monitoring.',
    icon: '⚪',
  },
  ERROR: {
    short: 'Error',
    detail: 'An error occurred. Check the activity feed for details.',
    icon: '❌',
  },
};

/**
 * Ensure timestamp is parsed as UTC.
 * Handles both naive UTC strings and timezone-aware (+00:00 / Z) from Fix #14.
 */
function parseUTC(timestamp) {
  if (!timestamp) return null;
  try {
    // Already has timezone info (+00:00, Z)? Parse directly.
    if (timestamp.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(timestamp)) {
      const d = new Date(timestamp);
      return isNaN(d.getTime()) ? null : d;
    }
    // Naive UTC — append Z
    const d = new Date(timestamp + 'Z');
    return isNaN(d.getTime()) ? null : d;
  } catch {
    return null;
  }
}

function formatElapsed(entryTime) {
  if (!entryTime) return '--';
  const start = parseUTC(entryTime);
  if (!start || isNaN(start.getTime())) return '--';
  const now = new Date();
  const diff = Math.max(0, Math.floor((now - start) / 1000));
  const hrs = Math.floor(diff / 3600);
  const mins = Math.floor((diff % 3600) / 60);
  const secs = diff % 60;
  if (hrs > 0) return `${hrs}h ${mins}m`;
  if (mins > 0) return `${mins}m ${secs}s`;
  return `${secs}s`;
}

function formatCountdown(nextHeartbeat) {
  if (!nextHeartbeat) return '--';
  const target = parseUTC(nextHeartbeat);
  if (!target || isNaN(target.getTime())) return '--';
  const now = new Date();
  const diff = Math.max(0, Math.floor((target - now) / 1000));
  const mins = Math.floor(diff / 60);
  const secs = diff % 60;
  return `${mins}:${String(secs).padStart(2, '0')}`;
}

export default function MMMStatusBanner({ session, heartbeat, onBothSidesAction, onPartialEntryAction }) {
  const [now, setNow] = useState(Date.now());

  // Update every second for live countdown
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const status = session?.strategy_status || 'IDLE';
  const baseCtx = STATUS_CONTEXT[status] || STATUS_CONTEXT.IDLE;

  // Dynamic context: override short/detail text with actual reason when available
  const ctx = useMemo(() => {
    if (!session) return baseCtx;
    if (status === 'PAUSED' && session._paused_reason) {
      return {
        ...baseCtx,
        short: session._paused_reason,
        detail: session._paused_resume_at
          ? `${session._paused_reason}. Will auto-resume at ${(parseUTC(session._paused_resume_at) || new Date()).toLocaleTimeString()}.`
          : baseCtx.detail,
      };
    }
    if (status === 'STOPPED' && session._stopped_reason) {
      return {
        ...baseCtx,
        short: session._stopped_reason,
        detail: session._stopped_reason,
      };
    }
    return baseCtx;
  }, [status, session, baseCtx]);

  if (!session) return null;

  const color = STATUS_COLORS[status] || STATUS_COLORS.IDLE;
  const adjCount = session.adjustment_count || 0;
  const reversalCount = session.reversal_count || 0;
  const shiftCount = session.shift_count || 0;
  const closeCount = session.close_at_5_count || 0;
  const elapsed = formatElapsed(session.entry_time);
  const countdown = formatCountdown(
    heartbeat?.next_heartbeat || session.next_heartbeat
  );

  const interval = heartbeat?.effective_interval || session.params?.adjustment_interval || 300;
  const isBothSidesUp = status === 'BOTH_SIDES_UP';
  const isPartialEntry = status === 'PARTIAL_ENTRY';
  const partialInfo = session?.partial_entry || {};

  return (
    <Box>
      {/* Main status bar */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          px: 2,
          py: 1,
          borderRadius: (isBothSidesUp || isPartialEntry) ? '8px 8px 0 0' : 2,
          bgcolor: 'rgba(0,0,0,0.04)',
          border: '1px solid',
          borderColor: `${color}40`,
          borderBottom: (isBothSidesUp || isPartialEntry) ? 'none' : undefined,
          flexWrap: 'wrap',
        }}
      >
        {/* Status */}
        <Tooltip title={ctx.detail} placement="bottom" arrow>
          <Chip
            icon={<CircleIcon sx={{ fontSize: 10, color }} />}
            label={status}
            size="small"
            sx={{
              fontWeight: 700,
              color,
              bgcolor: `${color}18`,
              letterSpacing: 0.5,
              cursor: 'help',
            }}
          />
        </Tooltip>

        {/* Contextual what's happening */}
        <Typography
          variant="caption"
          sx={{
            color: 'text.secondary',
            fontSize: '0.85rem',
            fontStyle: 'italic',
          }}
        >
          {ctx.short}
        </Typography>

        {/* Adjustment Count */}
        <Tooltip title={`Total adjustments made (§5). Each adjustment sells the opposite side to cover new losses.`}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <TrendingUpIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              Adj: {adjCount}
            </Typography>
          </Box>
        </Tooltip>

        {/* Reversal Count */}
        {reversalCount > 0 && (
          <Tooltip title={`${reversalCount} reversal(s) detected. A reversal means the market changed direction — the previously declining side started rising (§9).`}>
            <Chip
              icon={<ReversalIcon sx={{ fontSize: 14 }} />}
              label={`Rev: ${reversalCount}`}
              size="small"
              color="warning"
              variant="outlined"
              sx={{ cursor: 'help' }}
            />
          </Tooltip>
        )}

        {/* Shift Count */}
        {shiftCount > 0 && (
          <Tooltip title={`${shiftCount} strike shift(s). Shifted to a closer strike because opposing premium was too low for effective hedging (§10).`}>
            <Chip label={`Shifts: ${shiftCount}`} size="small" variant="outlined" sx={{ cursor: 'help' }} />
          </Tooltip>
        )}

        {/* Close-at-5 Count */}
        {closeCount > 0 && (
          <Tooltip title={`${closeCount} position(s) closed at ≤5 premium. Profit locked by buying back cheap options (§11).`}>
            <Chip
              label={`Closed: ${closeCount}`}
              size="small"
              color="success"
              variant="outlined"
              sx={{ cursor: 'help' }}
            />
          </Tooltip>
        )}

        {/* Adaptive Interval Tier */}
        {heartbeat?.adaptive_tier && (
          <Tooltip title={`Adaptive interval is active. Current tier: ${heartbeat.adaptive_tier}. Heartbeat interval automatically shortens as expiry approaches.`}>
            <Chip
              label={`⚡ ${heartbeat.adaptive_tier}`}
              size="small"
              variant="outlined"
              sx={{
                cursor: 'help',
                borderColor: '#00bcd4',
                color: '#00bcd4',
                fontWeight: 600,
                fontSize: '0.78rem',
              }}
            />
          </Tooltip>
        )}

        {/* Short Window deadline countdown */}
        {session?.session_deadline_utc && (() => {
          const deadlineMs = new Date(session.session_deadline_utc).getTime();
          const remainMs = Math.max(0, deadlineMs - now);
          const remainMin = Math.floor(remainMs / 60000);
          const remainH = Math.floor(remainMin / 60);
          const remMin = remainMin % 60;
          const label = remainH > 0 ? `⏱ ${remainH}h ${remMin}m left` : `⏱ ${remainMin}m left`;
          const urgent = remainMin < 30;
          return (
            <Tooltip title={`Short Window deadline: session will wind down and close all positions at ${new Date(session.session_deadline_utc).toLocaleTimeString()}`}>
              <Chip
                label={label}
                size="small"
                sx={{
                  cursor: 'help',
                  bgcolor: urgent ? 'rgba(211,47,47,0.12)' : 'rgba(237,108,2,0.12)',
                  color: urgent ? '#d32f2f' : '#ed6c02',
                  fontWeight: 700,
                  borderColor: urgent ? '#d32f2f' : '#ed6c02',
                  border: '1px solid',
                }}
              />
            </Tooltip>
          );
        })()}

        {/* Wind-Down Mode Active */}
        {heartbeat?.wind_down_active && (
          <Tooltip title="Wind-down mode is ACTIVE. The algo is reducing positions instead of adding new ones. Trigger events cause buybacks (LIFO) instead of adjustments.">
            <Chip
              label="🌙 Wind-Down"
              size="small"
              sx={{
                cursor: 'help',
                bgcolor: 'rgba(156,39,176,0.12)',
                color: '#9c27b0',
                fontWeight: 700,
                borderColor: '#9c27b0',
                border: '1px solid',
              }}
            />
          </Tooltip>
        )}

        {/* Spacer */}
        <Box sx={{ flexGrow: 1 }} />

        {/* Elapsed Time — only meaningful when strategy is active */}
        <Tooltip title={['RUNNING', 'PAUSED', 'BOTH_SIDES_UP', 'STARTING', 'PARTIAL_ENTRY'].includes(status) ? 'Time since entry' : 'Strategy not started yet'}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <TimerIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
            <Typography variant="body2" color="text.secondary">
              {['RUNNING', 'PAUSED', 'BOTH_SIDES_UP', 'STARTING', 'PARTIAL_ENTRY'].includes(status)
                ? elapsed
                : 'Not started'}
            </Typography>
          </Box>
        </Tooltip>

        {/* Countdown to next heartbeat */}
        {status === 'RUNNING' && (
          <Tooltip title={`Next heartbeat check in this time. Interval: ${interval}s. Each heartbeat fetches premiums, checks triggers, runs safety checks, and decides if an adjustment is needed (§4).`}>
            <Typography
              variant="body2"
              sx={{
                fontFamily: 'monospace',
                fontWeight: 600,
                color: 'text.secondary',
                bgcolor: 'action.hover',
                px: 1,
                py: 0.25,
                borderRadius: 1,
                cursor: 'help',
              }}
            >
              ⏱ {countdown}
            </Typography>
          </Tooltip>
        )}
      </Box>

      {/* Partial Entry — inline recovery panel */}
      {isPartialEntry && (
        <Box
          sx={{
            px: 2,
            py: 1.5,
            borderRadius: '0 0 8px 8px',
            bgcolor: 'rgba(255,87,34,0.06)',
            border: '1px solid',
            borderColor: 'rgba(255,87,34,0.3)',
            borderTop: 'none',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mb: 1 }}>
            <WarningIcon sx={{ color: '#ff5722', fontSize: 20, mt: 0.25 }} />
            <Box>
              <Typography variant="body2" sx={{ fontWeight: 600, color: '#ff5722', mb: 0.5 }}>
                Partial Entry — One leg failed
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', lineHeight: 1.5 }}>
                {partialInfo.ce_filled && !partialInfo.pe_filled
                  ? 'CE filled ✓ but PE failed ✗.'
                  : partialInfo.pe_filled && !partialInfo.ce_filled
                    ? 'PE filled ✓ but CE failed ✗.'
                    : 'One leg failed.'}
                {' '}Options: 1) Retry the failed leg automatically, or 2) if you already filled it manually on the exchange, click "Both Filled" and enter fill prices.
              </Typography>
            </Box>
          </Box>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <Tooltip title="Auto-retry the failed leg using smart order execution (mid-price limit order with repricing)">
              <Button
                size="small"
                variant="outlined"
                color="warning"
                onClick={() => onPartialEntryAction?.('retry_leg')}
                sx={{ fontSize: '0.88rem', py: 0.5 }}
              >
                🔄 Retry Failed Leg
              </Button>
            </Tooltip>
            <Tooltip title="Both legs are already filled on the exchange. Enter actual fill prices to start monitoring.">
              <Button
                size="small"
                variant="outlined"
                color="success"
                onClick={() => onPartialEntryAction?.('resolve_partial')}
                sx={{ fontSize: '0.88rem', py: 0.5 }}
              >
                ✅ Both Filled — Start
              </Button>
            </Tooltip>
          </Box>
        </Box>
      )}

      {/* Both Sides Up — inline decision panel */}
      {isBothSidesUp && (
        <Box
          sx={{
            px: 2,
            py: 1.5,
            borderRadius: '0 0 8px 8px',
            bgcolor: 'rgba(244,67,54,0.06)',
            border: '1px solid',
            borderColor: 'rgba(244,67,54,0.3)',
            borderTop: 'none',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, mb: 1 }}>
            <WarningIcon sx={{ color: '#f44336', fontSize: 20, mt: 0.25 }} />
            <Box>
              <Typography variant="body2" sx={{ fontWeight: 600, color: '#f44336', mb: 0.5 }}>
                Both CE and PE premiums exceeded triggers (§8)
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', lineHeight: 1.5 }}>
                The algo cannot auto-adjust because selling either side would double-down on risk.
                This may indicate an IV spike (premiums will decay — opportunity) or a whipsaw
                (sharp moves both ways — risk). Choose an action:
              </Typography>
            </Box>
          </Box>

          {/* CE / PE premium info if available from heartbeat */}
          {heartbeat && (
            <Box sx={{ display: 'flex', gap: 2, mb: 1.5, flexWrap: 'wrap' }}>
              <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                <Typography variant="caption" color="text.secondary">CE:</Typography>
                <Typography variant="caption" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                  ${Number(heartbeat.ce_premium || 0).toFixed(1)}
                </Typography>
                <Typography variant="caption" color="text.secondary">(trigger:</Typography>
                <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                  ${Number(heartbeat.ce_trigger || 0).toFixed(1)})
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                <Typography variant="caption" color="text.secondary">PE:</Typography>
                <Typography variant="caption" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                  ${Number(heartbeat.pe_premium || 0).toFixed(1)}
                </Typography>
                <Typography variant="caption" color="text.secondary">(trigger:</Typography>
                <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                  ${Number(heartbeat.pe_trigger || 0).toFixed(1)})
                </Typography>
              </Box>
            </Box>
          )}

          {/* Action buttons — §8 options */}
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <Tooltip title="Treat CE as the aggressor and sell more PE to cover CE's loss">
              <Button
                size="small"
                variant="outlined"
                color="primary"
                onClick={() => onBothSidesAction?.('adjust_ce')}
                sx={{ fontSize: '0.88rem', py: 0.5 }}
              >
                Hedge CE → Sell PE
              </Button>
            </Tooltip>
            <Tooltip title="Treat PE as the aggressor and sell more CE to cover PE's loss">
              <Button
                size="small"
                variant="outlined"
                color="primary"
                onClick={() => onBothSidesAction?.('adjust_pe')}
                sx={{ fontSize: '0.88rem', py: 0.5 }}
              >
                Hedge PE → Sell CE
              </Button>
            </Tooltip>
            <Tooltip title="Accept current premium levels as the new baseline. Update triggers to current values and resume monitoring — no adjustment.">
              <Button
                size="small"
                variant="outlined"
                color="success"
                startIcon={<ResumeIcon sx={{ fontSize: 14 }} />}
                onClick={() => onBothSidesAction?.('skip')}
                sx={{ fontSize: '0.88rem', py: 0.5 }}
              >
                Resume (Update Triggers)
              </Button>
            </Tooltip>
          </Box>
        </Box>
      )}

      {/* Paused explanation */}
      {status === 'PAUSED' && (
        <Box
          sx={{
            mt: 0.5,
            px: 2,
            py: 0.75,
            borderRadius: 1,
            bgcolor: 'rgba(255,152,0,0.06)',
            border: '1px dashed rgba(255,152,0,0.3)',
          }}
        >
          <Typography variant="caption" sx={{ color: '#ff9800' }}>
            ⏸ {session._paused_reason
              ? `Paused: ${session._paused_reason}`
              : 'Heartbeat monitoring is paused.'}{' '}
            {session._paused_resume_at
              ? (() => {
                const resumeAt = parseUTC(session._paused_resume_at) || new Date();
                const remaining = Math.max(0, Math.round((resumeAt - now) / 1000));
                return remaining > 0
                  ? `Auto-resume in ${remaining > 60 ? `${Math.floor(remaining / 60)}m ${remaining % 60}s` : `${remaining}s`}.`
                  : 'Auto-resuming shortly…';
              })()
              : 'Use "Resume" to restart monitoring, or "Stop" to end the strategy.'}
          </Typography>
        </Box>
      )}

      {/* T4 Trend Wind-Down — persistent warning strip */}
      {heartbeat?.wind_down_active && (heartbeat?.regime?.trend_tier ?? 0) >= 4 && (
        <Box
          sx={{
            mt: 0.5,
            px: 2,
            py: 0.75,
            borderRadius: 1,
            bgcolor: 'rgba(244,67,54,0.06)',
            border: '1px dashed rgba(244,67,54,0.3)',
            display: 'flex',
            alignItems: 'center',
            gap: 1,
          }}
        >
          <WarningIcon sx={{ color: '#f44336', fontSize: 18, flexShrink: 0 }} />
          <Typography variant="caption" sx={{ color: '#f44336', lineHeight: 1.5 }}>
            <strong>Wind-Down Active (Trend T4):</strong> New sells and auto-replenish are
            blocked. Spot is {Math.abs(session?._trend_move_pct || 0).toFixed(1)}% from
            anchor. Will auto-reset after ~{session?.params?.trend_t4_timeout_beats ?? 20} flat
            beats.
          </Typography>
        </Box>
      )}
    </Box>
  );
}
