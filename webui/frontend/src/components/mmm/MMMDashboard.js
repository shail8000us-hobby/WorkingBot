/**
 * MMM Dashboard — Money Mind & Method
 *
 * Main dashboard for the BTC 0DTE Options Selling Algorithm.
 * Phase 1: Foundation layout with session management, status display,
 * and parameter configuration panel.
 * Phase 3-7: Full live monitoring with positions, triggers, adjustments,
 * safety indicators, P&L chart, and strike map.
 *
 * Sections from MONEY_POWER_CALCULATION_LOGIC.md:
 *   §2 State, §3 Init, §4 Heartbeat, §5 Adjustment, §7 Triggers,
 *   §8 Both-Sides-Up, §9 Reversal, §10 Strike Shift, §11 Close-at-5,
 *   §13 Safety, §14 Strength, §19 Parameters
 *
 * Created: February 15, 2026
 * Updated: Phase 3-7 integration
 */

import React, { useState, useCallback, useMemo, useEffect } from 'react';
import {
  Box,
  Typography,
  Grid,
  Paper,
  Tabs,
  Tab,
  Button,
  Chip,
  Alert,
  CircularProgress,
  Divider,
  IconButton,
  Tooltip,
  Card,
  CardContent,
  TextField,
  Select,
  MenuItem,
  InputLabel,
  FormControl,
  Snackbar,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  ToggleButtonGroup,
  ToggleButton,
  Switch,
  FormControlLabel,
  Slider,
  Autocomplete,
} from '@mui/material';
import ContentCutIcon from '@mui/icons-material/ContentCut';
import {
  Refresh as RefreshIcon,
  PlayArrow as PlayIcon,
  Pause as PauseIcon,
  Stop as StopIcon,
  Add as AddIcon,
  Remove as RemoveIcon,
  Delete as DeleteIcon,
  Settings as SettingsIcon,
  TrendingUp as TrendingUpIcon,
  CheckCircle as HealthyIcon,
  Error as ErrorIcon,
  Circle as CircleIcon,
  Bolt as BoltIcon,
  LocalFireDepartment as DangerIcon,
} from '@mui/icons-material';
import { useMMM } from './MMMContext';
import mmmService from './mmmService';
import MMMConfigPanel from './MMMConfigPanel';
import useMMMWebSocket from './hooks/useMMMWebSocket';
import MMMStatusBanner from './MMMStatusBanner';
import MMMPositionsTable, { buildPositionRows, LOT_SIZE_BTC } from './MMMPositionsTable';
import MMMTriggerGauge from './MMMTriggerGauge';
import MMMAdjustmentLog from './MMMAdjustmentLog';
import MMMStrikeMap from './MMMStrikeMap';
import MMMAlgoCalculations from './MMMAlgoCalculations';
import MMMPnLChart from './MMMPnLChart';
import MMMBothSidesAlert from './MMMBothSidesAlert';
import MMMBreakevenPanel from './MMMBreakevenPanel';
import MMMGammaPanel from './MMMGammaPanel';
import MMMRiskProfileChart from './MMMRiskProfileChart';
import MMMCombinedZoneWidget from './MMMCombinedZoneWidget';
import MMMHealthRadar from './MMMHealthRadar';
import MMMDistanceHistoryChart from './MMMDistanceHistoryChart';
import MMMSafetyPanel from './MMMSafetyPanel';
import MMMMarginGuardianPanel from './MMMMarginGuardianPanel';
import MMMRegimePanel from './MMMRegimePanel';
import MMMPerpHedgePanel from './MMMPerpHedgePanel';
import MMMPerformancePanel from './MMMPerformancePanel';
import MMMTradeAuditPanel from './MMMTradeAuditPanel';
import MMMActivityFeed from './MMMActivityFeed';
import MMMExecutionLogPanel from './MMMExecutionLogPanel';
import MMMReverseModePanel from './MMMReverseModePanel';
import MMMSettingsDialog from './MMMSettingsDialog';
import MMMConsolidatedPositions from './MMMConsolidatedPositions';
import MMMGreeksPanel from './MMMGreeksPanel';
import MMMAnalyticsSummary from './MMMAnalyticsSummary';
import MMMInstitutionalAnalytics from '../MMMInstitutionalAnalytics';
import { HelpTooltip, SectionBlurb, StrategyExplainer } from './MMMEducation';
import useVisibilityAwarePolling from '../../hooks/useVisibilityAwarePolling';
import {
  ResponsiveContainer, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, Tooltip as RechartsTooltip, ReferenceLine,
} from 'recharts';

// =============================================================================
// Aggregate PnL Widget — shows combined P&L across all active sessions
// =============================================================================

const AGGREGATE_LEVEL_CONFIG = {
  ok: { color: '#4caf50', bg: 'rgba(76,175,80,0.1)', icon: '🟢', label: 'OK' },
  warning: { color: '#ff9800', bg: 'rgba(255,152,0,0.12)', icon: '🟡', label: 'WARNING' },
  danger: { color: '#f44336', bg: 'rgba(244,67,54,0.12)', icon: '🔴', label: 'DANGER' },
  blocked: { color: '#9c27b0', bg: 'rgba(156,39,176,0.12)', icon: '⛔', label: 'BLOCKED' },
};

const AggregatePnLWidget = () => {
  const [data, setData] = useState(null);

  const fetchAgg = useCallback(async () => {
    try {
      const result = await mmmService.getAggregatePnL();
      if (result.success && result.aggregate) setData(result.aggregate);
    } catch (_) { /* non-critical */ }
  }, []);

  useEffect(() => { fetchAgg(); }, [fetchAgg]);
  useVisibilityAwarePolling(fetchAgg, 30000, 120000, true);

  if (!data || data.session_count === 0) return null;

  const cfg = AGGREGATE_LEVEL_CONFIG[data.level] || AGGREGATE_LEVEL_CONFIG.ok;
  const pnl = data.combined_pnl ?? 0;
  const pctUsed = data.pct_used ?? 0;

  return (
    <Box sx={{ mb: 1.5, p: 1, borderRadius: 1, border: `1px solid ${cfg.color}44`, backgroundColor: cfg.bg }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="caption" sx={{ fontWeight: 700, color: cfg.color, fontSize: '0.75rem' }}>
          {cfg.icon} Combined P&amp;L
        </Typography>
        <Typography variant="caption" sx={{ fontWeight: 700, fontFamily: 'monospace', color: pnl >= 0 ? '#4caf50' : '#f44336', fontSize: '0.8rem' }}>
          ${pnl.toFixed(2)}
        </Typography>
      </Box>
      {pctUsed > 30 && (
        <Box sx={{ mt: 0.5 }}>
          <Box sx={{ height: 3, borderRadius: 2, backgroundColor: 'rgba(255,255,255,0.1)', overflow: 'hidden' }}>
            <Box sx={{ height: '100%', width: `${Math.min(pctUsed, 100)}%`, backgroundColor: cfg.color, borderRadius: 2, transition: 'width 0.5s ease' }} />
          </Box>
          <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.65rem' }}>
            {pctUsed.toFixed(0)}% of max loss used ({data.active_sessions} session{data.active_sessions > 1 ? 's' : ''})
          </Typography>
        </Box>
      )}
    </Box>
  );
};

// =============================================================================
// Status color + label mapping
// =============================================================================

const STATUS_CONFIG = {
  IDLE: { color: '#9e9e9e', bg: 'rgba(158,158,158,0.12)', label: 'Idle' },
  STARTING: { color: '#2196f3', bg: 'rgba(33,150,243,0.12)', label: 'Starting...' },
  RUNNING: { color: '#4caf50', bg: 'rgba(76,175,80,0.12)', label: 'Running' },
  PAUSED: { color: '#ff9800', bg: 'rgba(255,152,0,0.12)', label: 'Paused' },
  BOTH_SIDES_UP: { color: '#f44336', bg: 'rgba(244,67,54,0.12)', label: 'Both Sides Up!' },
  PARTIAL_ENTRY: { color: '#ff5722', bg: 'rgba(255,87,34,0.12)', label: 'Partial Entry!' },
  ERROR: { color: '#f44336', bg: 'rgba(244,67,54,0.12)', label: 'Error' },
  STOPPED: { color: '#757575', bg: 'rgba(117,117,117,0.12)', label: 'Stopped' },
  EXITING: { color: '#ff6f00', bg: 'rgba(255,111,0,0.12)', label: 'Exiting...' },
};

const getStatusConfig = (status) =>
  STATUS_CONFIG[status] || STATUS_CONFIG.IDLE;

// =============================================================================
// Sub-Components
// =============================================================================

/**
 * Status chip for a session
 */
const StatusChip = ({ status }) => {
  const cfg = getStatusConfig(status);
  return (
    <Chip
      label={cfg.label}
      size="small"
      icon={<CircleIcon sx={{ fontSize: 10 }} />}
      sx={{
        backgroundColor: cfg.bg,
        color: cfg.color,
        fontWeight: 600,
        '& .MuiChip-icon': { color: cfg.color },
      }}
    />
  );
};

/**
 * Compute expiry info from an ISO UTC expiry_time.
 * Returns { countdown: "0d:2h:46m", expiryIST: "5:30 PM IST" } or null.
 * Delta Exchange India expires daily at 5:30 PM IST.
 */
const computeExpiryInfo = (expiryTimeISO) => {
  if (!expiryTimeISO) return null;
  try {
    // expiry_time may be naive UTC or timezone-aware (Fix #14)
    const expStr = expiryTimeISO.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(expiryTimeISO)
      ? expiryTimeISO : expiryTimeISO + 'Z';
    const expMs = new Date(expStr).getTime();
    const nowMs = Date.now();
    const diffMs = expMs - nowMs;

    // Format expiry in IST (UTC+5:30)
    const expDate = new Date(expMs);
    const expiryIST = expDate.toLocaleString('en-IN', {
      timeZone: 'Asia/Kolkata',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
      day: 'numeric',
      month: 'short',
    });

    if (diffMs <= 0) return { countdown: 'EXPIRED', expiryIST };

    // L-10 fix: clamp to non-negative
    const totalMin = Math.floor(Math.max(diffMs, 0) / 60000);
    const d = Math.floor(totalMin / 1440);
    const h = Math.floor((totalMin % 1440) / 60);
    const m = totalMin % 60;
    return { countdown: `${d}d:${h}h:${m}m`, expiryIST };
  } catch {
    return null;
  }
};

/**
 * Compute DTE countdown color based on time remaining.
 * Green (>4h) → Yellow (1-4h) → Orange (<1h) → Red (expired)
 */
const getCountdownColor = (expiryInfo) => {
  if (!expiryInfo) return '#ff9800';
  if (expiryInfo.countdown === 'EXPIRED') return '#f44336';
  // Parse days:hours:minutes from "Xd:Yh:Zm" format
  const match = expiryInfo.countdown.match(/(\d+)d:(\d+)h:(\d+)m/);
  if (!match) return '#ff9800';
  const totalMins = parseInt(match[1], 10) * 1440 + parseInt(match[2], 10) * 60 + parseInt(match[3], 10);
  if (totalMins > 240) return '#4caf50';  // > 4 hours: green
  if (totalMins > 60) return '#ff9800';   // 1-4 hours: yellow/amber
  return '#f44336';                       // < 1 hour: red
};

// ── Radar background — SVG data-URI injected as Card backgroundImage ─────────
const _RADAR_REGIME_SCORES = {
  NORMAL: 95, BLOCK_CE_SELLS: 65, BLOCK_PE_SELLS: 65,
  BLOCK_ALL_SELLS: 35, PAUSE: 15, FORCE_REDUCE: 5,
};
const _RADAR_TREND_SCORES = { 0: 95, 1: 70, 2: 45, 3: 20, 4: 5 };

function _radarBgImage(session, heartbeat) {
  const deg = (d) => (d * Math.PI) / 180;
  const CX = 50, CY = 50, R = 38;
  const hb = heartbeat || {};

  // Prefer live heartbeat data, fall back to stored session summary fields
  const beDist = hb.breakeven?.nearest_distance_pct ?? session._be_nearest_pct;
  const beEnabled = hb.breakeven?.enabled ?? session._be_enabled;
  const beScore = beEnabled && beDist != null ? Math.min(100, (beDist / 5.0) * 100) : 100;

  const gDist = hb.gamma?.nearest_distance_pct ?? session._gamma_nearest_pct;
  const gEnabled = hb.gamma?.enabled ?? session._gamma_enabled;
  const gammaScore = gEnabled && gDist != null ? Math.min(100, (gDist / 6.0) * 100) : 100;

  const marginUtil = hb.margin?.utilization_pct;
  const marginScore = marginUtil != null ? Math.max(0, 100 - marginUtil) : 85;

  const regimeAction = hb.regime?.action || hb.regime?.regime_action || session._regime_action || 'NORMAL';
  const regimeScore  = _RADAR_REGIME_SCORES[regimeAction] ?? 95;

  const trendTier = hb.regime?.trend_tier ?? session._trend_tier ?? 0;
  const trendScore = _RADAR_TREND_SCORES[trendTier] ?? 95;

  const scores = [beScore, gammaScore, marginScore, regimeScore, trendScore];
  const worst  = Math.min(...scores);
  const color  = worst < 30 ? '#f44336' : worst < 60 ? '#ff9800' : '#4caf50';

  const pt = (s, i) => {
    const a = deg(-90 + i * 72);
    const r = (s / 100) * R;
    return `${(CX + r * Math.cos(a)).toFixed(1)},${(CY + r * Math.sin(a)).toFixed(1)}`;
  };
  const scorePts = scores.map((s, i) => pt(s, i)).join(' ');

  const ringPts = (f) => Array.from({ length: 5 }, (_, i) => {
    const a = deg(-90 + i * 72);
    const r = f * R;
    return `${(CX + r * Math.cos(a)).toFixed(1)},${(CY + r * Math.sin(a)).toFixed(1)}`;
  }).join(' ');

  const dots = scores.map((s, i) => {
    const a = deg(-90 + i * 72);
    const r = (s / 100) * R;
    return `<circle cx='${(CX + r * Math.cos(a)).toFixed(1)}' cy='${(CY + r * Math.sin(a)).toFixed(1)}' r='1.5' fill='${color}' opacity='0.5'/>`;
  }).join('');

  const svg = [
    `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>`,
    `<polygon points='${ringPts(0.33)}' fill='none' stroke='white' stroke-width='0.4' opacity='0.12'/>`,
    `<polygon points='${ringPts(0.67)}' fill='none' stroke='white' stroke-width='0.4' opacity='0.12'/>`,
    `<polygon points='${ringPts(1)}'    fill='none' stroke='white' stroke-width='0.4' opacity='0.12'/>`,
    `<polygon points='${scorePts}' fill='${color}' fill-opacity='0.12' stroke='${color}' stroke-width='1.2' opacity='0.45'/>`,
    dots,
    `</svg>`,
  ].join('');

  return `url("data:image/svg+xml,${encodeURIComponent(svg)}")`;
}

/**
 * Session card condensed view
 */
// 🔒 SEALED #74 — test: test_sealed_mmm_session_card.test.js
export const SessionCard = ({ session, selected, onSelect, onControl, heartbeat }) => {
  const status = session.status || 'IDLE';
  const cfg = getStatusConfig(status);

  // Live countdown — ticks every 30s so it stays fresh between polls
  const [expiryInfo, setExpiryInfo] = useState(() => computeExpiryInfo(session.expiry_time));
  useEffect(() => {
    let isMounted = true;  // M-31 fix: guard against post-unmount setState
    setExpiryInfo(computeExpiryInfo(session.expiry_time));
    const timer = setInterval(() => {
      if (isMounted) setExpiryInfo(computeExpiryInfo(session.expiry_time));
    }, 30000);
    return () => { isMounted = false; clearInterval(timer); };
  }, [session.expiry_time]);

  return (
    <Card
      variant="outlined"
      onClick={() => onSelect(session.session_id)}
      sx={{
        cursor: 'pointer',
        mb: 1,
        border: selected
          ? `2px solid ${cfg.color}`
          : '1px solid rgba(255,255,255,0.12)',
        backgroundColor: selected ? cfg.bg : 'transparent',
        backgroundImage: _radarBgImage(session, heartbeat),
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'right 8px bottom 8px',
        backgroundSize: '42% 75%',
        transition: 'all 0.2s',
        '&:hover': { backgroundColor: cfg.bg },
      }}
    >
      <CardContent sx={{ py: 1.5, px: 2, '&:last-child': { pb: 1.5 } }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Typography variant="subtitle2" sx={{ fontFamily: 'monospace' }}>
              {session.session_id}
            </Typography>
            {/* Preset badge — shown for all presets */}
            {(session.params?._preset_source === 'STRADDLE_WITH_ADJUSTMENT' ||
              session.params?._preset_source === 'SHORT_STRADDLE') ? (
              <Chip
                label="Straddle+Adj"
                size="small"
                color="secondary"
                variant="outlined"
                sx={{ height: 18, fontSize: '0.6rem', fontWeight: 700 }}
              />
            ) : session.dte_category === 'SHORT_WINDOW' ? (
              <Chip
                label={`${session.session_window_hours || 5}h`}
                size="small"
                color="warning"
                variant="outlined"
                sx={{ height: 18, fontSize: '0.6rem', fontWeight: 700 }}
              />
            ) : session.dte_category && session.dte_category !== '0DTE' ? (
              <Chip
                label={session.dte_category}
                size="small"
                color="info"
                variant="outlined"
                sx={{ height: 18, fontSize: '0.6rem', fontWeight: 700 }}
              />
            ) : null}
            {/* Health Grade Badge */}
            {session._health_grade && (
              <Tooltip title={`Health: ${session._health_grade}`}>
                <Box sx={{
                  width: 18, height: 18, borderRadius: '50%', display: 'flex',
                  alignItems: 'center', justifyContent: 'center', fontSize: '0.6rem', fontWeight: 800,
                  backgroundColor: ({ A: '#4caf50', B: '#8bc34a', C: '#ff9800', D: '#f44336' })[session._health_grade] || '#9e9e9e',
                  color: '#fff',
                }}>
                  {session._health_grade}
                </Box>
              </Tooltip>
            )}
            {/* Gamma regime indicator */}
            {session._gamma_regime && session._gamma_regime !== 'NORMAL' && (
              <Tooltip title={`Gamma: ${session._gamma_regime}`}>
                <Typography component="span" sx={{ fontSize: '0.7rem', fontWeight: 700, color: '#f44336' }}>
                  ⚡{session._gamma_regime}
                </Typography>
              </Tooltip>
            )}
            {/* F9: Data Quality badge — live from heartbeat, fallback to session field */}
            {(() => {
              const conf = heartbeat?.data_confidence ?? session._data_confidence;
              if (conf == null) return null;
              const pct = Math.round(conf * 100);
              const color = conf >= 0.8 ? '#4caf50' : conf >= 0.5 ? '#ff9800' : '#f44336';
              const bg = conf >= 0.8 ? 'rgba(76,175,80,0.15)' : conf >= 0.5 ? 'rgba(255,152,0,0.15)' : 'rgba(244,67,54,0.15)';
              return (
                <Tooltip title={`Data confidence: ${pct}%`}>
                  <Chip size="small" label={`${pct}%`}
                    sx={{ height: 16, fontSize: '0.6rem', fontWeight: 700, bgcolor: bg, color, '& .MuiChip-label': { px: 0.75 } }} />
                </Tooltip>
              );
            })()}
            {/* F6: Gamma Zone badge — hidden in SAFE, shown for WARNING/DANGER/CRITICAL */}
            {(() => {
              const zone = heartbeat?.gamma?.gamma_zone ?? session._gamma_zone;
              if (!zone || zone === 'SAFE') return null;
              const dist = heartbeat?.gamma?.nearest_distance_pct ?? session._gamma_nearest_pct;
              const color = zone === 'WARNING' ? '#ff9800' : '#f44336';
              const bg = zone === 'WARNING' ? 'rgba(255,152,0,0.15)' : 'rgba(244,67,54,0.15)';
              const label = `γ${zone[0]}${dist != null ? ` ${dist.toFixed(1)}%` : ''}`;
              return (
                <Tooltip title={`Gamma zone: ${zone}${dist != null ? ` (${dist.toFixed(2)}% from boundary)` : ''}`}>
                  <Chip size="small" label={label}
                    sx={{ height: 16, fontSize: '0.6rem', fontWeight: 700, bgcolor: bg, color, '& .MuiChip-label': { px: 0.75 } }} />
                </Tooltip>
              );
            })()}
          </Box>
          <StatusChip status={status} />
        </Box>

        <Grid container spacing={1} sx={{ mt: 0.5 }}>
          <Grid item xs={6}>
            <Typography variant="caption" color="text.secondary">
              CE: {session.ce_active_lots || 0} lots @ {session.ce_strike || '—'}
              {session.ce_frozen_lots > 0 && (
                <span style={{ color: '#ff9800', fontWeight: 600 }}> (+{session.ce_frozen_lots}F)</span>
              )}
            </Typography>
          </Grid>
          <Grid item xs={6}>
            <Typography variant="caption" color="text.secondary">
              PE: {session.pe_active_lots || 0} lots @ {session.pe_strike || '—'}
              {session.pe_frozen_lots > 0 && (
                <span style={{ color: '#ff9800', fontWeight: 600 }}> (+{session.pe_frozen_lots}F)</span>
              )}
            </Typography>
          </Grid>
        </Grid>

        {session.net_pnl !== undefined && (
          <Box sx={{ mt: 0.5 }}>
            <Typography
              variant="body2"
              sx={{
                fontWeight: 700,
                color: session.net_pnl >= 0 ? '#4caf50' : '#f44336',
                fontFamily: 'monospace',
              }}
            >
              P&L: ${session.net_pnl?.toFixed(2) || '0.00'}
            </Typography>
            {(session.realized_pnl !== 0 || session.net_pnl !== 0) && (
              <Typography variant="caption" sx={{ fontFamily: 'monospace', color: 'text.secondary', fontSize: '0.65rem' }}>
                R: ${(session.realized_pnl || 0).toFixed(2)} &nbsp; U: ${(session.unrealized_pnl || 0).toFixed(2)} &nbsp; F: -${(session.total_fees || 0).toFixed(2)}
              </Typography>
            )}
          </Box>
        )}

        {/* Activity counters */}
        {(session.adjustment_count > 0 || session.shift_count > 0 || session.close_at_5_count > 0) && (
          <Typography variant="caption" sx={{ mt: 0.25, display: 'block', color: 'text.secondary', fontSize: '0.65rem', fontFamily: 'monospace' }}>
            {session.adjustment_count > 0 && `⚙${session.adjustment_count} adj`}
            {session.adjustment_count > 0 && (session.shift_count > 0 || session.close_at_5_count > 0) && ' · '}
            {session.shift_count > 0 && `↗${session.shift_count} shift`}
            {session.shift_count > 0 && session.close_at_5_count > 0 && ' · '}
            {session.close_at_5_count > 0 && `🎯${session.close_at_5_count} close`}
          </Typography>
        )}

        {/* Time to Expiry (IST) */}
        {expiryInfo && (
          <Typography
            variant="caption"
            sx={{
              mt: 0.5,
              fontWeight: 600,
              color: getCountdownColor(expiryInfo),
              fontFamily: 'monospace',
              display: 'block',
            }}
          >
            Expiry: {expiryInfo.expiryIST} IST &nbsp;|&nbsp; {expiryInfo.countdown}
          </Typography>
        )}

        {/* Why Paused — show reason when session is paused */}
        {status === 'PAUSED' && session._paused_reason && (
          <Typography
            variant="caption"
            sx={{
              mt: 0.5, display: 'block', fontStyle: 'italic',
              color: '#ff9800', fontSize: '0.7rem',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}
          >
            ⚠️ {session._paused_reason}
          </Typography>
        )}

        {/* Last heartbeat alive indicator */}
        {session.last_heartbeat && ['RUNNING', 'PAUSED', 'BOTH_SIDES_UP'].includes(status) && (() => {
          const ts = session.last_heartbeat;
          const beatMs = new Date(ts.includes('+') || ts.endsWith('Z') ? ts : ts + 'Z').getTime();
          const beatAge = Math.floor((Date.now() - beatMs) / 1000);
          if (isNaN(beatAge)) return null;
          const beatColor = beatAge < 60 ? '#4caf50' : beatAge < 300 ? '#ff9800' : '#f44336';
          const beatLabel = beatAge < 60 ? `${beatAge}s ago` : beatAge < 3600 ? `${Math.floor(beatAge / 60)}m ago` : `${Math.floor(beatAge / 3600)}h ago`;
          return (
            <Typography variant="caption" sx={{ mt: 0.25, display: 'block', fontSize: '0.6rem', color: beatColor, fontFamily: 'monospace' }}>
              ♥ {beatLabel}{session.adjustment_interval ? ` · interval ${Math.floor(session.adjustment_interval / 60)}m` : ''}
            </Typography>
          );
        })()}

        {/* Control buttons */}
        <Box sx={{ display: 'flex', gap: 0.5, mt: 1, alignItems: 'center' }}>
          {status === 'STARTING' && (
            <Typography variant="caption" color="primary" sx={{ fontStyle: 'italic', animation: 'pulse 1.5s infinite' }}>
              ⏳ Placing entry orders...
            </Typography>
          )}
          {status === 'PARTIAL_ENTRY' && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, width: '100%' }}>
              <Typography variant="caption" color="error" sx={{ fontWeight: 700 }}>
                ⚠️ One leg filled, other failed!
              </Typography>
              <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                <Tooltip title="Auto-retry the failed leg with smart order execution">
                  <Button
                    size="small"
                    variant="outlined"
                    color="warning"
                    sx={{ fontSize: '0.65rem', py: 0.2, px: 0.8, minWidth: 0 }}
                    onClick={(e) => { e.stopPropagation(); onControl('retry_leg', session.session_id); }}
                  >
                    🔄 Retry Leg
                  </Button>
                </Tooltip>
                <Tooltip title="Both legs are already filled on the exchange — enter fill prices to start monitoring">
                  <Button
                    size="small"
                    variant="outlined"
                    color="success"
                    sx={{ fontSize: '0.65rem', py: 0.2, px: 0.8, minWidth: 0 }}
                    onClick={(e) => { e.stopPropagation(); onControl('resolve_partial', session.session_id); }}
                  >
                    ✅ Both Filled
                  </Button>
                </Tooltip>
              </Box>
            </Box>
          )}
          {status === 'IDLE' && (session.ce_original_lots > 0 || session.ce_active_lots > 0) && (
            <Tooltip title="Start">
              <IconButton
                size="small"
                color="success"
                onClick={(e) => { e.stopPropagation(); onControl('start', session.session_id); }}
              >
                <PlayIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          {status === 'IDLE' && !(session.ce_original_lots > 0 || session.ce_active_lots > 0) && (
            <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>Click to initialize →</Typography>
          )}
          {status === 'RUNNING' && (
            <Tooltip title="Pause">
              <IconButton
                size="small"
                color="warning"
                onClick={(e) => { e.stopPropagation(); onControl('pause', session.session_id); }}
              >
                <PauseIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          {status === 'RUNNING' && (
            <Tooltip title="⚡ Force Heartbeat — run next check immediately">
              <IconButton
                size="small"
                sx={{
                  color: '#ffab00',
                  '&:hover': { color: '#ffd600', backgroundColor: 'rgba(255,171,0,0.12)' },
                }}
                onClick={(e) => { e.stopPropagation(); onControl('force_heartbeat', session.session_id); }}
              >
                <BoltIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          {status === 'PAUSED' && (
            <Tooltip title="Resume">
              <IconButton
                size="small"
                color="success"
                onClick={(e) => { e.stopPropagation(); onControl('resume', session.session_id); }}
              >
                <PlayIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          {['RUNNING', 'PAUSED', 'BOTH_SIDES_UP', 'STARTING', 'PARTIAL_ENTRY'].includes(status) && (
            <Tooltip title="Stop">
              <IconButton
                size="small"
                color="error"
                onClick={(e) => { e.stopPropagation(); onControl('stop', session.session_id); }}
              >
                <StopIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          {['RUNNING', 'PAUSED', 'BOTH_SIDES_UP'].includes(status) && (
            <Tooltip title="Exit Strategy — close all positions and stop">
              <IconButton
                size="small"
                sx={{
                  color: '#ff6f00',
                  '&:hover': { color: '#ff8f00', backgroundColor: 'rgba(255,111,0,0.12)' },
                }}
                onClick={(e) => { e.stopPropagation(); onControl('exit_all', session.session_id); }}
              >
                <ContentCutIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          {status === 'EXITING' && (
            <Tooltip title="Exit in progress...">
              <CircularProgress size={16} sx={{ color: '#ff6f00', ml: 0.5 }} />
            </Tooltip>
          )}
          {['IDLE', 'STOPPED'].includes(status) && (
            <Tooltip title="Delete">
              <IconButton
                size="small"
                color="default"
                onClick={(e) => { e.stopPropagation(); onControl('delete', session.session_id); }}
              >
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
          {/* Settings button for all sessions except STARTING */}
          {status !== 'STARTING' && (
            <Tooltip title="Settings">
              <IconButton
                size="small"
                color="primary"
                onClick={(e) => { e.stopPropagation(); onControl('settings', session.session_id); }}
              >
                <SettingsIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      </CardContent>
    </Card>
  );
};

/**
 * Both-Sides-Up decision dialog (Section 8)
 * Now delegates to MMMBothSidesAlert component.
 */

/**
 * Format expiry from DDMMYYYY → human-readable "DD MMM YYYY"
 */
const formatExpiry = (ddmmyyyy) => {
  if (!ddmmyyyy || ddmmyyyy.length !== 8) return ddmmyyyy;
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const dd = ddmmyyyy.slice(0, 2);
  const mm = parseInt(ddmmyyyy.slice(2, 4), 10) - 1;
  const yyyy = ddmmyyyy.slice(4, 8);
  return `${dd} ${months[mm] || '???'} ${yyyy}`;
};

/**
 * Create Session dialog — with proper expiry dropdown and import fields
 */
const CreateSessionDialog = ({ open, onClose, onCreated, paramsInfo }) => {
  const [mode, setMode] = useState('fresh');
  const [dtePreset, setDtePreset] = useState('');  // '' = Custom (no preset)
  const [dtePresets, setDtePresets] = useState({});  // preset_details from API
  const [params, setParams] = useState({
    desired_ce_premium: 100,
    desired_pe_premium: 100,
    initial_lots: 1,
    straddle_roll_max_per_session: 3,
    expiry: '',
    adjustment_interval: 300,
    close_at_threshold: 5,
    max_lots_per_side: 100,
    max_adjustments: 30,
    max_loss_amount: 50000,
    session_window_hours: 0,
  });
  const [importData, setImportData] = useState({
    ce: { strike: '', premium: '', lots: '' },
    pe: { strike: '', premium: '', lots: '' },
  });
  const [expiries, setExpiries] = useState([]);
  const [expiryLoading, setExpiryLoading] = useState(false);
  const [spotPrice, setSpotPrice] = useState(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState(null);

  // Apply DTE preset when selection changes
  const handlePresetChange = (presetName) => {
    setDtePreset(presetName);
    if (presetName && dtePresets[presetName]) {
      const preset = dtePresets[presetName];
      setParams(prev => ({
        ...prev,
        adjustment_interval: preset.adjustment_interval ?? prev.adjustment_interval,
        close_at_threshold: preset.close_at_threshold ?? prev.close_at_threshold,
        max_lots_per_side: preset.max_lots_per_side ?? prev.max_lots_per_side,
        max_loss_amount: preset.max_loss_amount ?? prev.max_loss_amount,
        min_trigger_move: preset.min_trigger_move ?? prev.min_trigger_move,
        session_window_hours: preset.session_window_hours ?? 0,
      }));
    }
  };

  // Fetch expiries, spot price, and DTE presets when dialog opens
  React.useEffect(() => {
    if (!open) return;
    let cancelled = false;

    const fetchData = async () => {
      setExpiryLoading(true);
      try {
        const [expResult, spotResult, presetResult] = await Promise.all([
          mmmService.getExpiries().catch(() => ({ success: false })),
          mmmService.getSpotPrice().catch(() => ({ success: false })),
          mmmService.getDTEPresets().catch(() => ({ success: false })),
        ]);

        if (cancelled) return;

        if (expResult.success && expResult.expiries?.length > 0) {
          setExpiries(expResult.expiries);
          // Auto-select first (today's 0DTE) if no expiry set
          if (!params.expiry) {
            setParams(prev => ({ ...prev, expiry: expResult.expiries[0] }));
          }
        }
        if (spotResult.success) {
          setSpotPrice(spotResult.spot_price);
        }
        if (presetResult.success && presetResult.preset_details) {
          setDtePresets(presetResult.preset_details);
        }
      } catch (err) {
        console.error('Failed to fetch expiries/spot:', err);
      } finally {
        if (!cancelled) setExpiryLoading(false);
      }
    };

    fetchData();
    return () => { cancelled = true; };
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleParamChange = (key, value) => {
    setParams((prev) => ({ ...prev, [key]: value }));
  };

  const handleImportChange = (side, field, value) => {
    setImportData((prev) => ({
      ...prev,
      [side]: { ...prev[side], [field]: value },
    }));
  };

  const handleCreate = async () => {
    // Guard: prevent double-submit (button disabled state can lag one render)
    if (creating) return;

    // Validate expiry
    if (!params.expiry) {
      setError('Please select an expiry date');
      return;
    }

    // Validate import data
    if (mode === 'import') {
      const { ce, pe } = importData;
      if (!ce.strike || !ce.premium || !ce.lots) {
        setError('All CE side fields (Strike, Fill Price, Lots) are required');
        return;
      }
      if (!pe.strike || !pe.premium || !pe.lots) {
        setError('All PE side fields (Strike, Fill Price, Lots) are required');
        return;
      }
      // M-34 fix: Validate numeric fields before sending to backend
      if (isNaN(parseFloat(ce.strike)) || isNaN(parseFloat(ce.premium)) || isNaN(parseInt(ce.lots, 10)) ||
        isNaN(parseFloat(pe.strike)) || isNaN(parseFloat(pe.premium)) || isNaN(parseInt(pe.lots, 10))) {
        setError('Strike, Premium, and Lots must be valid numbers');
        return;
      }
    }

    setCreating(true);
    setError(null);

    try {
      // For adopt mode, create as 'fresh' on backend — adoption happens in ConfigPanel
      const backendMode = mode === 'adopt' ? 'fresh' : mode;
      let sessionParams;
      if (dtePreset === 'STRADDLE_WITH_ADJUSTMENT') {
        // STRADDLE_WITH_ADJUSTMENT: backend builds all params from the preset server-side.
        // Only send what the user explicitly controls — preset-driven values
        // (max_loss_amount, adjustment_interval, etc.) must not be sent so they
        // don't trip backend validation guards calibrated for other presets.
        sessionParams = {
          expiry: params.expiry,
          dte_category: 'STRADDLE_WITH_ADJUSTMENT',
          initial_lots: params.initial_lots,
          straddle_roll_max_per_session: params.straddle_roll_max_per_session,
          desired_ce_premium: params.desired_ce_premium,
          desired_pe_premium: params.desired_pe_premium,
        };
      } else {
        sessionParams = { ...params };
        if (dtePreset) {
          sessionParams.dte_category = dtePreset;
        }
      }
      const config = { mode: backendMode, params: sessionParams };
      if (mode === 'import') {
        config.import_data = {
          ce: {
            strike: parseFloat(importData.ce.strike),
            premium: parseFloat(importData.ce.premium),
            lots: parseInt(importData.ce.lots, 10),
          },
          pe: {
            strike: parseFloat(importData.pe.strike),
            premium: parseFloat(importData.pe.premium),
            lots: parseInt(importData.pe.lots, 10),
          },
        };
      }
      const result = await mmmService.createSession(config);
      if (result.success) {
        // Signal adopt mode to parent so ConfigPanel opens in adopt tab
        if (mode === 'adopt') {
          result.session._adoptMode = true;
        }
        onCreated(result.session);
        onClose();
        // Reset form
        setMode('fresh');
        setError(null);
        setImportData({
          ce: { strike: '', premium: '', lots: '' },
          pe: { strike: '', premium: '', lots: '' },
        });
      } else {
        setError(result.error || 'Failed to create session');
      }
    } catch (err) {
      setError(err.details?.error || err.message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <TrendingUpIcon color="primary" />
          <span>Create MMM Session</span>
          {spotPrice && (
            <Chip
              label={`BTC $${spotPrice.toLocaleString('en-US', { maximumFractionDigits: 0 })}`}
              size="small"
              variant="outlined"
              color="primary"
              sx={{ ml: 'auto' }}
            />
          )}
        </Box>
      </DialogTitle>
      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2, mt: 1 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {/* DTE Preset + Mode selection */}
        <Grid container spacing={2} sx={{ mb: 3, mt: 1 }}>
          <Grid item xs={6}>
            <FormControl fullWidth size="small">
              <InputLabel>DTE Preset</InputLabel>
              <Select
                value={dtePreset}
                label="DTE Preset"
                onChange={(e) => handlePresetChange(e.target.value)}
              >
                <MenuItem value="">Custom (no preset)</MenuItem>
                {Object.keys(dtePresets).map((name) => (
                  <MenuItem key={name} value={name}>
                    {name === 'SHORT_WINDOW'
                      ? `Short Window (${dtePresets[name].session_window_hours ?? 5}h)`
                      : name === 'STRADDLE_WITH_ADJUSTMENT'
                      ? 'Short Straddle — with Adjustment'
                      : name}
                    {dtePresets[name]?.max_loss_amount && (
                      <Typography
                        component="span"
                        variant="caption"
                        sx={{ ml: 1, color: 'text.secondary' }}
                      >
                        — Max Loss ${dtePresets[name].max_loss_amount.toLocaleString()}
                      </Typography>
                    )}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={6}>
            <FormControl fullWidth size="small">
              <InputLabel>Mode</InputLabel>
              <Select value={mode} label="Mode" onChange={(e) => setMode(e.target.value)}>
                <MenuItem value="fresh">Fresh — Auto-find strikes</MenuItem>
                <MenuItem value="import">Import — Use existing positions</MenuItem>
                <MenuItem value="adopt">
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    Adopt — Scan exchange for open positions
                    <Chip label="NEW" size="small" color="secondary" sx={{ height: 18, fontSize: '0.65rem' }} />
                  </Box>
                </MenuItem>
              </Select>
            </FormControl>
          </Grid>
        </Grid>

        {/* DTE preset info */}
        {dtePreset && dtePresets[dtePreset] && (
          <Alert severity="info" sx={{ mb: 2 }} icon={false}>
            {dtePreset === 'SHORT_WINDOW' ? (
              <>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                  Short Window Preset — Evening Theta Harvest
                </Typography>
                <Typography variant="body2" sx={{ mb: 1 }}>
                  Optimized for 1–8h evening sessions. Wind-down starts 1h before deadline.
                  Auto-closes all positions at session end.
                </Typography>
                <Box sx={{ px: 1 }}>
                  <Typography variant="caption" sx={{ fontWeight: 600 }}>
                    Session window: {params.session_window_hours}h
                  </Typography>
                  <Slider
                    value={params.session_window_hours || 5}
                    min={1}
                    max={8}
                    step={0.5}
                    marks={[
                      { value: 1, label: '1h' },
                      { value: 3, label: '3h' },
                      { value: 5, label: '5h' },
                      { value: 8, label: '8h' },
                    ]}
                    valueLabelDisplay="auto"
                    onChange={(_, v) => handleParamChange('session_window_hours', v)}
                    sx={{ mt: 0.5 }}
                  />
                </Box>
                <Typography variant="caption" color="text.secondary">
                  Interval: {dtePresets[dtePreset].adjustment_interval}s
                  {' • '}Trigger: {dtePresets[dtePreset].min_trigger_move}%
                  {' • '}Max Lots: {dtePresets[dtePreset].max_lots_per_side}/side
                  {' • '}Max Loss: ${dtePresets[dtePreset].max_loss_amount?.toLocaleString()}
                </Typography>
              </>
            ) : dtePreset === 'STRADDLE_WITH_ADJUSTMENT' ? (
              <>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                  🎯 Short Straddle — with Adjustment
                </Typography>
                <Typography variant="body2" sx={{ mb: 1 }}>
                  Pure ATM straddle optimized for daily BTC options. All 52 parameters
                  auto-scale based on hours remaining to 5:30 PM IST expiry (1–24h range).
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Max Lots: {dtePresets[dtePreset].max_lots_per_side}/side
                  {' • '}Max Loss: ${dtePresets[dtePreset].max_loss_amount?.toLocaleString()}
                  {' • '}Trailing Stop: {(dtePresets[dtePreset].trailing_stop_pct * 100) || 25}%
                  {' • '}Adjustments: auto-scaled
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                  🔄 Straddle Roll: auto-repositions at ATM when spot moves ≥ CE+PE entry premium pts
                  {' • '}Max rolls/session set by operator (required)
                  {' • '}Cooldown {dtePresets[dtePreset].straddle_roll_cooldown_mins || 15}min
                  {' • '}⚡ Price Guard: 5s real-time spot monitor
                </Typography>
                <Typography variant="caption" color="warning.main" sx={{ display: 'block', mt: 0.5 }}>
                  ⏱ Params computed at session creation from time-to-expiry. Select today's expiry above.
                </Typography>
              </>
            ) : (
              <>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
                  {dtePreset} Preset Applied
                </Typography>
                <Typography variant="body2">
                  Interval: {dtePresets[dtePreset].adjustment_interval}s
                  {' • '}Trigger: {dtePresets[dtePreset].min_trigger_move}%
                  {' • '}Max Lots: {dtePresets[dtePreset].max_lots_per_side}/side
                  {' • '}Max Loss: ${dtePresets[dtePreset].max_loss_amount?.toLocaleString()}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  You can override any parameter below. The preset provides defaults.
                </Typography>
              </>
            )}
          </Alert>
        )}

        {/* Core parameters */}
        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700 }}>Core Parameters</Typography>
        <Grid container spacing={2} sx={{ mb: 3 }}>
          {dtePreset === 'STRADDLE_WITH_ADJUSTMENT' ? (
            /* STRADDLE_WITH_ADJUSTMENT: ATM strike is auto-selected — premium fields are not applicable */
            <Grid item xs={8}>
              <Box sx={{
                p: 1.5,
                borderRadius: 1,
                border: '1px solid rgba(255,255,255,0.12)',
                backgroundColor: 'rgba(255,255,255,0.04)',
              }}>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                  Strike Selection
                </Typography>
                <Typography variant="body2" sx={{ fontWeight: 500 }}>
                  ATM — auto-selected at session creation
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  CE and PE sold simultaneously at the same ATM strike. No manual premium target needed.
                </Typography>
              </Box>
            </Grid>
          ) : (
            <>
              <Grid item xs={4}>
                <TextField
                  label="Desired CE Premium"
                  type="number"
                  value={params.desired_ce_premium}
                  onChange={(e) => handleParamChange('desired_ce_premium', parseFloat(e.target.value) || 0)}
                  fullWidth
                  size="small"
                  inputProps={{ min: 1, step: 10 }}
                />
              </Grid>
              <Grid item xs={4}>
                <TextField
                  label="Desired PE Premium"
                  type="number"
                  value={params.desired_pe_premium}
                  onChange={(e) => handleParamChange('desired_pe_premium', parseFloat(e.target.value) || 0)}
                  fullWidth
                  size="small"
                  inputProps={{ min: 1, step: 10 }}
                />
              </Grid>
            </>
          )}
          <Grid item xs={4}>
            <TextField
              label="Initial Lots"
              type="number"
              value={params.initial_lots}
              onChange={(e) => handleParamChange('initial_lots', parseInt(e.target.value, 10) || 1)}
              fullWidth
              size="small"
              inputProps={{ min: 1 }}
            />
          </Grid>
          {dtePreset === 'STRADDLE_WITH_ADJUSTMENT' && (
            <Grid item xs={4}>
              <TextField
                label="Max Rolls / Session"
                type="number"
                value={params.straddle_roll_max_per_session}
                onChange={(e) => handleParamChange('straddle_roll_max_per_session', parseInt(e.target.value, 10) || 1)}
                fullWidth
                size="small"
                inputProps={{ min: 1, max: 20 }}
                helperText="Required — no default"
              />
            </Grid>
          )}
          <Grid item xs={4}>
            <FormControl fullWidth size="small">
              <InputLabel>Expiry</InputLabel>
              <Select
                value={params.expiry}
                label="Expiry"
                onChange={(e) => handleParamChange('expiry', e.target.value)}
                disabled={expiryLoading}
              >
                {expiryLoading && (
                  <MenuItem value="" disabled>Loading expiries...</MenuItem>
                )}
                {expiries.map((exp) => (
                  <MenuItem key={exp} value={exp}>
                    {formatExpiry(exp)}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={4}>
            <TextField
              label="Adj. Interval (sec)"
              type="number"
              value={params.adjustment_interval}
              onChange={(e) => handleParamChange('adjustment_interval', parseInt(e.target.value, 10) || 60)}
              fullWidth
              size="small"
              inputProps={{ min: 10, step: 30 }}
              disabled={dtePreset === 'STRADDLE_WITH_ADJUSTMENT'}
            />
          </Grid>
          <Grid item xs={4}>
            <TextField
              label="Max Loss ($)"
              type="number"
              value={params.max_loss_amount}
              onChange={(e) => handleParamChange('max_loss_amount', parseFloat(e.target.value) || 0)}
              fullWidth
              size="small"
              inputProps={{ min: dtePreset === 'STRADDLE_WITH_ADJUSTMENT' ? 1 : 100, step: dtePreset === 'STRADDLE_WITH_ADJUSTMENT' ? 1 : 1000 }}
            />
          </Grid>
        </Grid>

        {/* Import data (only for import mode) */}
        {mode === 'import' && (
          <>
            <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle2" sx={{ mb: 2, fontWeight: 700 }}>
              Import Existing Positions
            </Typography>
            {[
              { side: 'ce', label: 'CE Side (Call)', color: '#4caf50' },
              { side: 'pe', label: 'PE Side (Put)', color: '#f44336' },
            ].map(({ side, label, color }) => (
              <Box
                key={side}
                sx={{
                  mb: 2,
                  p: 2,
                  borderRadius: 1,
                  border: `1px solid ${color}33`,
                  backgroundColor: `${color}08`,
                }}
              >
                <Typography
                  variant="subtitle2"
                  sx={{ mb: 1.5, fontWeight: 600, color, textTransform: 'uppercase' }}
                >
                  {label}
                </Typography>
                <Grid container spacing={2}>
                  <Grid item xs={4}>
                    <TextField
                      label="Strike Price"
                      type="number"
                      value={importData[side].strike}
                      onChange={(e) => handleImportChange(side, 'strike', e.target.value)}
                      fullWidth
                      size="small"
                      variant="outlined"
                      placeholder={side === 'ce' ? 'e.g. 101000' : 'e.g. 97000'}
                      inputProps={{ min: 0, step: 500 }}
                      InputLabelProps={{ shrink: true }}
                    />
                  </Grid>
                  <Grid item xs={4}>
                    <TextField
                      label="Fill Price ($)"
                      type="number"
                      value={importData[side].premium}
                      onChange={(e) => handleImportChange(side, 'premium', e.target.value)}
                      fullWidth
                      size="small"
                      variant="outlined"
                      placeholder="e.g. 120.50"
                      inputProps={{ min: 0, step: 5 }}
                      InputLabelProps={{ shrink: true }}
                    />
                  </Grid>
                  <Grid item xs={4}>
                    <TextField
                      label="Lots"
                      type="number"
                      value={importData[side].lots}
                      onChange={(e) => handleImportChange(side, 'lots', e.target.value)}
                      fullWidth
                      size="small"
                      variant="outlined"
                      placeholder="e.g. 1"
                      inputProps={{ min: 1, step: 1 }}
                      InputLabelProps={{ shrink: true }}
                    />
                  </Grid>
                </Grid>
              </Box>
            ))}
          </>
        )}

        {/* Fresh mode hint */}
        {mode === 'fresh' && (
          <Alert severity="info" sx={{ mt: 1 }}>
            After creating the session, use the <strong>Config Panel</strong> to auto-find strikes
            and preview before confirming entry.
          </Alert>
        )}

        {/* Adopt mode hint */}
        {mode === 'adopt' && (
          <Alert severity="info" sx={{ mt: 1 }} icon={false}>
            <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
              🔍 Adopt from Exchange
            </Typography>
            <Typography variant="body2">
              Creates a session, then opens the <strong>Adopt Panel</strong> where you can
              scan Delta Exchange for your open short BTC options, select positions,
              assign active/frozen roles, and start the algorithm.
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
              Only the <strong>Expiry</strong> and <strong>Max Loss</strong> fields above are needed.
              Other params (desired premium, lots) will be auto-filled from your positions.
            </Typography>
          </Alert>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={creating}>
          Cancel
        </Button>
        <Button
          variant="contained"
          onClick={handleCreate}
          disabled={creating || !params.expiry}
          startIcon={creating ? <CircularProgress size={16} /> : <AddIcon />}
        >
          {creating ? 'Creating...' : 'Create Session'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

// =============================================================================
// HeartbeatHealthPanel — institutional beat telemetry widget
// =============================================================================

const GRADE_COLORS = { A: '#4caf50', B: '#8bc34a', C: '#ff9800', D: '#f44336', F: '#9c27b0' };

const HeartbeatHealthPanel = ({ sessionId, status }) => {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(false);
  const [lastRefresh, setLastRefresh] = useState(null);

  const fetchHealth = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const data = await mmmService.getBeatHealth(sessionId);
      if (data && data.success) {
        setHealth(data);
        setLastRefresh(new Date());
      }
    } catch (_e) {
      // silently ignore — health panel is non-critical
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  // Always fetch once on mount; only poll continuously when RUNNING
  useEffect(() => { fetchHealth(); }, [fetchHealth]);
  useVisibilityAwarePolling(fetchHealth, 30000, 120000, status === 'RUNNING');

  if (!health) return null;

  // M-33 fix: Show staleness indicator when session not running
  const isStale = status !== 'RUNNING' && health !== null;

  const bh = health.beat_health || {};
  const circ = health.circuit || {};
  const grade = bh.grade || '?';
  const gradeColor = GRADE_COLORS[grade] || '#9e9e9e';
  const circuitColor = circ.state === 'CLOSED' ? '#4caf50' : circ.state === 'HALF_OPEN' ? '#ff9800' : '#f44336';

  const outcomeDot = (o) => {
    if (o === 'ok') return '🟢';
    if (o === 'partial') return '🟡';
    if (o === 'miss') return '🔴';
    if (o === 'error') return '❌';
    return '⬜';
  };

  return (
    <Paper elevation={0} sx={{ p: 2, mb: 2, borderRadius: 2, border: '1px solid rgba(255,255,255,0.12)' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          💓 Heartbeat Health {isStale && <Chip label="paused" size="small" color="warning" variant="outlined" sx={{ ml: 1 }} />}
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {lastRefresh && (
            <Typography variant="caption" color="text.secondary">
              {lastRefresh.toLocaleTimeString()}
            </Typography>
          )}
          <Tooltip title="Refresh health stats">
            <IconButton size="small" onClick={fetchHealth} disabled={loading}>
              <RefreshIcon fontSize="inherit" />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      <Grid container spacing={1.5} alignItems="stretch">
        <Grid item xs={4} sm={2}>
          <Box sx={{ textAlign: 'center', p: 1, borderRadius: 1, backgroundColor: 'rgba(255,255,255,0.04)' }}>
            <Typography variant="caption" color="text.secondary" display="block">Grade</Typography>
            <Typography variant="h5" sx={{ fontWeight: 900, color: gradeColor, fontFamily: 'monospace' }}>
              {grade}
            </Typography>
          </Box>
        </Grid>
        <Grid item xs={4} sm={2}>
          <Box sx={{ textAlign: 'center', p: 1, borderRadius: 1, backgroundColor: 'rgba(255,255,255,0.04)' }}>
            <Typography variant="caption" color="text.secondary" display="block">p50 Latency</Typography>
            <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: 'monospace' }}>
              {bh.latency_p50_ms != null ? `${bh.latency_p50_ms}ms` : '—'}
            </Typography>
          </Box>
        </Grid>
        <Grid item xs={4} sm={2}>
          <Box sx={{ textAlign: 'center', p: 1, borderRadius: 1, backgroundColor: 'rgba(255,255,255,0.04)' }}>
            <Typography variant="caption" color="text.secondary" display="block">p95 Latency</Typography>
            <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: 'monospace' }}>
              {bh.latency_p95_ms != null ? `${bh.latency_p95_ms}ms` : '—'}
            </Typography>
          </Box>
        </Grid>
        <Grid item xs={4} sm={2}>
          <Box sx={{ textAlign: 'center', p: 1, borderRadius: 1, backgroundColor: 'rgba(255,255,255,0.04)' }}>
            <Typography variant="caption" color="text.secondary" display="block">Miss Rate</Typography>
            <Typography variant="body2" sx={{
              fontWeight: 700, fontFamily: 'monospace',
              color: (bh.miss_rate_pct || 0) > 10 ? '#f44336' : (bh.miss_rate_pct || 0) > 2 ? '#ff9800' : 'inherit'
            }}>
              {bh.miss_rate_pct != null ? `${bh.miss_rate_pct}%` : '—'}
            </Typography>
          </Box>
        </Grid>
        <Grid item xs={4} sm={2}>
          <Tooltip title={circ.last_error ? `Last error: ${circ.last_error}` : 'Exchange API circuit breaker'}>
            <Box sx={{ textAlign: 'center', p: 1, borderRadius: 1, backgroundColor: 'rgba(255,255,255,0.04)', cursor: 'help' }}>
              <Typography variant="caption" color="text.secondary" display="block">Circuit</Typography>
              <Typography variant="body2" sx={{ fontWeight: 700, color: circuitColor, fontFamily: 'monospace' }}>
                {circ.state || '—'}
              </Typography>
              {circ.open_depth > 0 && (
                <Typography variant="caption" sx={{ color: '#ff9800' }}>depth {circ.open_depth}</Typography>
              )}
            </Box>
          </Tooltip>
        </Grid>
        <Grid item xs={4} sm={2}>
          <Box sx={{ textAlign: 'center', p: 1, borderRadius: 1, backgroundColor: 'rgba(255,255,255,0.04)' }}>
            <Typography variant="caption" color="text.secondary" display="block">Beats</Typography>
            <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: 'monospace', fontSize: '0.75rem' }}>
              ✅{bh.ok_beats || 0} 🟡{bh.partial_beats || 0} ❌{bh.error_beats || 0}
            </Typography>
          </Box>
        </Grid>
      </Grid>

      {bh.recent_outcomes && bh.recent_outcomes.length > 0 && (
        <Box sx={{ mt: 1.5, display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
          <Typography variant="caption" color="text.secondary" sx={{ mr: 0.5 }}>Last 20:</Typography>
          {bh.recent_outcomes.map((o, i) => (
            <span key={i} style={{ fontSize: '10px', lineHeight: 1 }}>{outcomeDot(o)}</span>
          ))}
        </Box>
      )}

      {(bh.stale_ce || bh.stale_pe) && (
        <Alert severity="warning" sx={{ mt: 1, py: 0.5 }}>
          ⚠️ Stale price detected: {[bh.stale_ce && 'CE', bh.stale_pe && 'PE'].filter(Boolean).join(' & ')} mark price
          unchanged for 3+ consecutive beats — exchange may be serving cached data.
        </Alert>
      )}

      {circ.state && circ.state !== 'CLOSED' && (
        <Alert severity={circ.state === 'OPEN' ? 'error' : 'warning'} sx={{ mt: 1, py: 0.5 }}>
          🔴 Circuit breaker {circ.state} — using cached prices for safety checks.
          {circ.seconds_until_probe != null && ` Next probe in ${Math.ceil(circ.seconds_until_probe)}s.`}
        </Alert>
      )}
    </Paper>
  );
};

// =============================================================================
// Manual Reduce Modal
// =============================================================================

/**
 * Modal dialog for manually buying back lots while the algo keeps running.
 * Side selector, lots stepper, optional specific strike.
 *
 * Props:
 *   open    — boolean
 *   session — session object (for max lots, strikes list)
 *   onClose — callback
 */
const MMMReduceModal = ({ open, session, onClose }) => {
  const [side, setSide] = useState('ce');
  const [lots, setLots] = useState(1);
  const [strikeMode, setStrikeMode] = useState('lifo');  // 'lifo' | 'specific'
  const [specificStrike, setSpecificStrike] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);   // last API result
  const [error, setError] = useState('');

  if (!session) return null;

  // Collect unique strikes per side for the dropdown
  const getStrikes = (sideKey) => {
    const s = session[sideKey] || {};
    const strikes = new Set();
    if (s.active_strike) strikes.add(s.active_strike);
    if (s.original_strike) strikes.add(s.original_strike);
    (s.adjustment_fills || []).forEach(f => { if (f.strike) strikes.add(f.strike); });
    (s.frozen_positions || []).forEach(f => { if (f.strike) strikes.add(f.strike); });
    return Array.from(strikes).sort((a, b) => a - b);
  };

  const maxLots = side === 'both'
    ? Math.min(session.ce?.active_lots || 0, session.pe?.active_lots || 0)
    : (session[side]?.active_lots || 0);

  const ceStrikes = getStrikes('ce');
  const peStrikes = getStrikes('pe');
  const availableStrikes = side === 'both'
    ? [...new Set([...ceStrikes, ...peStrikes])].sort((a, b) => a - b)
    : (side === 'ce' ? ceStrikes : peStrikes);

  const handleClose = () => {
    if (loading) return;
    setResult(null);
    setError('');
    setLots(1);
    setSide('ce');
    setStrikeMode('lifo');
    setSpecificStrike('');
    onClose();
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const strike = strikeMode === 'specific' && specificStrike ? Number(specificStrike) : null;
      const res = await mmmService.reducePosition(session.session_id, side, lots, strike);
      setResult(res);
      if (!res.success && !res.results?.length) {
        setError(res.error || (res.errors || []).join('; ') || 'Reduction failed');
      }
    } catch (e) {
      setError(e?.response?.data?.error || e.message || 'Network error');
    } finally {
      setLoading(false);
    }
  };

  const isDone = result != null;

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ fontWeight: 700 }}>
        ✂️ Reduce Position
      </DialogTitle>

      <DialogContent sx={{ pt: 2 }}>
        {isDone ? (
          /* ---- Result view ---- */
          <Box>
            {result.results?.length > 0 ? (
              <Alert severity="success" sx={{ mb: 1.5 }}>
                Reduced successfully. Realized P&L: <strong>${(result.total_realized_pnl || 0).toFixed(2)}</strong>
              </Alert>
            ) : (
              <Alert severity="error" sx={{ mb: 1.5 }}>
                {error || 'No lots were reduced.'}
              </Alert>
            )}
            {result.results?.map((r, i) => (
              <Box key={i} sx={{ mb: 0.5, fontFamily: 'monospace', fontSize: '0.85rem' }}>
                {r.side} @ {Number(r.strike).toLocaleString()}: {r.lots} lots
                — fill ${r.fill_price?.toFixed(2)}, P&L ${r.realized_pnl?.toFixed(2)}
              </Box>
            ))}
            {result.errors?.length > 0 && (
              <Alert severity="warning" sx={{ mt: 1 }}>
                {result.errors.join('; ')}
              </Alert>
            )}
          </Box>
        ) : (
          /* ---- Input view ---- */
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 0.5 }}>
            <Typography variant="body2" color="text.secondary">
              Buy back lots while the algo keeps running. Does not count as an adjustment.
            </Typography>

            {/* Side toggle */}
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
                Side to reduce
              </Typography>
              <ToggleButtonGroup
                value={side}
                exclusive
                onChange={(_, v) => { if (v) { setSide(v); setLots(1); setSpecificStrike(''); } }}
                size="small"
                sx={{ width: '100%' }}
              >
                <ToggleButton value="ce" sx={{ flex: 1, fontWeight: 700 }}>
                  📈 CE  {session.ce?.active_lots != null && `(${session.ce.active_lots} lots)`}
                </ToggleButton>
                <ToggleButton value="pe" sx={{ flex: 1, fontWeight: 700 }}>
                  📉 PE  {session.pe?.active_lots != null && `(${session.pe.active_lots} lots)`}
                </ToggleButton>
                <ToggleButton value="both" sx={{ flex: 1, fontWeight: 700 }}>
                  ⚖️ Both
                </ToggleButton>
              </ToggleButtonGroup>
            </Box>

            {/* Lots input */}
            <TextField
              label={`Lots to buy back ${maxLots > 0 ? `(max ${maxLots})` : ''}`}
              type="number"
              value={lots}
              onChange={e => setLots(Math.max(1, Math.min(maxLots, parseInt(e.target.value) || 1)))}
              inputProps={{ min: 1, max: maxLots }}
              size="small"
              fullWidth
              error={lots > maxLots}
              helperText={lots > maxLots ? `Max available: ${maxLots}` : ''}
            />

            {/* Strike mode */}
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
                Strike selection
              </Typography>
              <ToggleButtonGroup
                value={strikeMode}
                exclusive
                onChange={(_, v) => { if (v) setStrikeMode(v); }}
                size="small"
                sx={{ width: '100%' }}
              >
                <ToggleButton value="lifo" sx={{ flex: 1 }}>
                  Auto (LIFO)
                </ToggleButton>
                <ToggleButton value="specific" sx={{ flex: 1 }}>
                  Specific Strike
                </ToggleButton>
              </ToggleButtonGroup>
            </Box>

            {strikeMode === 'specific' && (
              <FormControl size="small" fullWidth>
                <InputLabel>Strike</InputLabel>
                <Select
                  value={specificStrike}
                  label="Strike"
                  onChange={e => setSpecificStrike(e.target.value)}
                >
                  {availableStrikes.map(s => (
                    <MenuItem key={s} value={s}>{Number(s).toLocaleString()}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}

            {error && <Alert severity="error">{error}</Alert>}
          </Box>
        )}
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={handleClose} disabled={loading}>
          {isDone ? 'Close' : 'Cancel'}
        </Button>
        {!isDone && (
          <Button
            variant="contained"
            color="warning"
            onClick={handleSubmit}
            disabled={loading || lots < 1 || lots > maxLots || maxLots === 0 || (strikeMode === 'specific' && !specificStrike)}
            startIcon={loading ? <CircularProgress size={16} color="inherit" /> : <ContentCutIcon />}
          >
            {loading ? 'Executing...' : `Buy Back ${lots} Lot${lots !== 1 ? 's' : ''}`}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};

// =============================================================================
// Operator Inject Modal
// =============================================================================

/**
 * Modal for manually injecting a new short option position into a running
 * algo session. The algo will register and manage it going forward.
 *
 * Props:
 *   open    — boolean
 *   session — session object (for lots cap info)
 *   onClose — callback
 */
const MMMInjectModal = ({ open, session, onClose }) => {
  const [side, setSide] = useState('ce');
  const [lots, setLots] = useState(1);
  // 'active' = use algo's current active strike; 'custom' = operator picks from chain
  const [strikeMode, setStrikeMode] = useState('active');
  const [customStrike, setCustomStrike] = useState('');
  const [adopt, setAdopt] = useState(false);
  const [adoptFillPrice, setAdoptFillPrice] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  // Strike chain for picker
  const [chain, setChain] = useState({ ce: [], pe: [], spot_price: 0 });
  const [chainLoading, setChainLoading] = useState(false);
  const [chainError, setChainError] = useState('');

  if (!session) return null;

  // Fetch option chain whenever custom mode is activated or side changes
  const fetchChain = async () => {
    setChainLoading(true);
    setChainError('');
    try {
      const data = await mmmService.getOptionChain(session.session_id);
      if (data.success) setChain(data);
      else setChainError(data.error || 'Failed to load strikes');
    } catch (e) {
      setChainError('Could not load strikes from exchange');
    } finally {
      setChainLoading(false);
    }
  };

  const activeStrike = session[side]?.active_strike || 0;
  const effectiveStrike = strikeMode === 'active' ? activeStrike : Number(customStrike);
  const maxLots = Math.max(0, (session.params?.max_lots_per_side || 100) - (session[side]?.active_lots || 0));

  const resetForm = () => {
    setResult(null); setError(''); setLots(1); setSide('ce');
    setStrikeMode('active'); setCustomStrike(''); setConfirmed(false);
    setAdopt(false); setAdoptFillPrice('');
    setChain({ ce: [], pe: [], spot_price: 0 }); setChainError('');
  };

  const handleClose = () => { if (loading) return; resetForm(); onClose(); };

  const handleSideChange = (_, v) => {
    if (v) {
      setSide(v); setLots(1); setStrikeMode('active'); setCustomStrike('');
      // Re-fetch not needed — chain has both sides already
    }
  };

  const handleStrikeModeChange = (_, v) => {
    if (!v) return;
    setStrikeMode(v);
    setCustomStrike('');
    if (v === 'custom' && chain.ce.length === 0) fetchChain();
  };

  const handleSubmit = async () => {
    if (!confirmed || !isValid) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const res = await mmmService.injectPosition(
        session.session_id, side, lots, effectiveStrike,
        adopt, adopt ? Number(adoptFillPrice) : null
      );
      setResult(res);
      if (!res.success) setError(res.error || 'Injection failed');
    } catch (e) {
      const msg = e?.response?.data?.error || e?.message || 'Network error';
      setError(
        msg === 'Failed to fetch' || msg.includes('ERR_CONNECTION_REFUSED')
          ? 'Backend unreachable — server may be restarting. Please try again.'
          : msg
      );
    } finally {
      setLoading(false);
    }
  };

  const isDone = result != null;
  const adoptFillValid = !adopt || (Number(adoptFillPrice) > 0);
  const isValid = effectiveStrike >= 1000 && lots >= 1 && (adopt || maxLots > 0) && (adopt || lots <= maxLots) && adoptFillValid;

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ fontWeight: 700, color: '#ff9800' }}>
        {adopt ? '📌 Adopt Existing Position' : '💉 Inject Position'}
      </DialogTitle>

      <DialogContent sx={{ pt: 2 }}>
        {isDone ? (
          /* ---- Result view ---- */
          <Box>
            {result.success ? (
              <Alert severity="success" sx={{ mb: 1.5 }}>
                {result.adopted ? 'Adopted successfully.' : 'Injected successfully.'} Fill: <strong>${result.fill_price?.toFixed(2)}</strong>
              </Alert>
            ) : (
              <Alert severity="error" sx={{ mb: 1.5 }}>{error || 'Injection failed.'}</Alert>
            )}
            {result.success && (
              <Box sx={{ fontFamily: 'monospace', fontSize: '0.85rem', mt: 1 }}>
                <Box>{result.side} @ {Number(result.strike).toLocaleString()}: {result.lots} lots</Box>
                <Box>Fill price: ${result.fill_price?.toFixed(2)}</Box>
                <Box>New active lots ({result.side}): {result.new_active_lots}</Box>
                {result.order_id && <Box sx={{ mt: 0.5, color: 'text.secondary' }}>Order: {result.order_id}</Box>}
              </Box>
            )}
          </Box>
        ) : (
          /* ---- Input view ---- */
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 0.5 }}>

            {/* Adopt / New order toggle */}
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              border: '1px solid', borderColor: adopt ? 'info.main' : 'divider',
              borderRadius: 1, px: 1.5, py: 0.75,
              backgroundColor: adopt ? 'rgba(33,150,243,0.07)' : 'transparent' }}>
              <Box>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {adopt ? '📌 Adopt mode' : '💉 New sell order'}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {adopt
                    ? 'Register an existing exchange position — no order placed'
                    : 'Place a real SELL order and register it'}
                </Typography>
              </Box>
              <Switch checked={adopt} onChange={e => { setAdopt(e.target.checked); setConfirmed(false); setAdoptFillPrice(''); }} color="info" size="small" />
            </Box>

            {adopt ? (
              <Alert severity="info" sx={{ fontSize: '0.8rem' }}>
                Registers an <strong>already-open position on the exchange</strong> with the algo.
                No order is placed. Use this when you sold manually or the session lost track.
              </Alert>
            ) : (
              <Alert severity="warning" sx={{ fontSize: '0.8rem' }}>
                This places a <strong>real SELL order</strong> on the exchange and registers
                the position with the algo. The algo will manage it (adjustments, shifts,
                close-at-5) from this point forward.
              </Alert>
            )}

            {/* Side selector */}
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>Side</Typography>
              <ToggleButtonGroup value={side} exclusive onChange={handleSideChange} size="small" sx={{ width: '100%' }}>
                <ToggleButton value="ce" sx={{ flex: 1, fontWeight: 700 }}>
                  📈 CE {session.ce?.active_lots != null && `(${session.ce.active_lots} active)`}
                </ToggleButton>
                <ToggleButton value="pe" sx={{ flex: 1, fontWeight: 700 }}>
                  📉 PE {session.pe?.active_lots != null && `(${session.pe.active_lots} active)`}
                </ToggleButton>
              </ToggleButtonGroup>
            </Box>

            {/* Strike mode selector */}
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>Strike</Typography>
              <ToggleButtonGroup
                value={strikeMode}
                exclusive
                onChange={handleStrikeModeChange}
                size="small"
                sx={{ width: '100%', mb: 1 }}
              >
                <ToggleButton value="active" sx={{ flex: 1 }}>
                  Active&nbsp;
                  {activeStrike > 0
                    ? <Typography component="span" sx={{ fontWeight: 700, fontFamily: 'monospace', fontSize: '0.85rem', color: 'primary.main' }}>
                        {activeStrike.toLocaleString()}
                      </Typography>
                    : <Typography component="span" sx={{ color: 'text.disabled', fontSize: '0.8rem' }}>—</Typography>
                  }
                </ToggleButton>
                <ToggleButton value="custom" sx={{ flex: 1 }}>Pick Strike</ToggleButton>
              </ToggleButtonGroup>

              {strikeMode === 'active' ? (
                /* Visual confirmation of which strike will be used */
                <Box sx={{
                  display: 'flex', alignItems: 'center', gap: 1, px: 1.5, py: 1,
                  borderRadius: 1, backgroundColor: 'rgba(33,150,243,0.08)',
                  border: '1px solid rgba(33,150,243,0.3)',
                }}>
                  <Typography variant="body2" color="text.secondary">Will sell at:</Typography>
                  {activeStrike > 0
                    ? <Typography variant="body1" sx={{ fontWeight: 700, fontFamily: 'monospace', color: 'primary.main' }}>
                        {activeStrike.toLocaleString()}
                      </Typography>
                    : <Typography variant="body2" color="error">No active strike on this side</Typography>
                  }
                  <Typography variant="caption" color="text.disabled" sx={{ ml: 'auto' }}>
                    algo's current {side.toUpperCase()} strike
                  </Typography>
                </Box>
              ) : (
                /* Strike picker — loads live option chain from exchange */
                <Box>
                  {chainLoading && (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 1 }}>
                      <CircularProgress size={14} />
                      <Typography variant="caption" color="text.secondary">Loading strikes from exchange…</Typography>
                    </Box>
                  )}
                  {chainError && (
                    <Alert severity="warning" sx={{ mb: 1, fontSize: '0.78rem' }}>
                      {chainError} —{' '}
                      <Box component="span" sx={{ cursor: 'pointer', textDecoration: 'underline' }} onClick={fetchChain}>retry</Box>
                    </Alert>
                  )}
                  {!chainLoading && (chain[side] || []).length > 0 && (
                    <>
                      {chain.spot_price > 0 && (
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                          BTC Spot: <strong>${Number(chain.spot_price).toLocaleString()}</strong>
                        </Typography>
                      )}
                      <Autocomplete
                        options={chain[side] || []}
                        getOptionLabel={opt => `${Number(opt.strike).toLocaleString()}  —  $${opt.premium.toFixed(2)}`}
                        value={(chain[side] || []).find(o => o.strike === Number(customStrike)) || null}
                        onChange={(_, opt) => setCustomStrike(opt ? String(opt.strike) : '')}
                        size="small"
                        autoHighlight
                        renderOption={(props, opt) => (
                          <Box component="li" {...props} sx={{ fontFamily: 'monospace', fontSize: '0.82rem' }}>
                            <Box sx={{ display: 'flex', width: '100%', justifyContent: 'space-between', gap: 2 }}>
                              <Typography sx={{ fontWeight: 700, fontFamily: 'monospace', fontSize: '0.85rem' }}>
                                {Number(opt.strike).toLocaleString()}
                              </Typography>
                              <Box sx={{ display: 'flex', gap: 1.5, color: 'text.secondary', fontSize: '0.78rem' }}>
                                <span>Mark <strong style={{ color: '#4caf50' }}>${opt.mark_price > 0 ? opt.mark_price.toFixed(1) : opt.premium.toFixed(1)}</strong></span>
                                <span>Bid <strong>${opt.bid.toFixed(1)}</strong></span>
                                <span>Ask <strong>${opt.ask.toFixed(1)}</strong></span>
                                {opt.delta !== 0 && <span>Δ {opt.delta.toFixed(2)}</span>}
                              </Box>
                            </Box>
                          </Box>
                        )}
                        renderInput={params => (
                          <TextField
                            {...params}
                            label="Select strike"
                            placeholder="Search by strike…"
                            size="small"
                            autoFocus
                          />
                        )}
                      />
                      {customStrike && (chain[side] || []).find(o => o.strike === Number(customStrike)) && (() => {
                        const sel = (chain[side] || []).find(o => o.strike === Number(customStrike));
                        return (
                          <Box sx={{ mt: 0.75, px: 1, py: 0.5, borderRadius: 1, backgroundColor: 'rgba(255,152,0,0.08)', border: '1px solid rgba(255,152,0,0.3)', fontFamily: 'monospace', fontSize: '0.8rem' }}>
                            <Typography variant="caption">
                              Strike <strong>{Number(sel.strike).toLocaleString()}</strong> · Mark <strong>${(sel.mark_price || sel.premium).toFixed(2)}</strong> · Bid <strong>${sel.bid.toFixed(2)}</strong> / Ask <strong>${sel.ask.toFixed(2)}</strong>
                              {sel.delta !== 0 && <> · Δ <strong>{sel.delta.toFixed(3)}</strong></>}
                            </Typography>
                          </Box>
                        );
                      })()}
                    </>
                  )}
                </Box>
              )}
            </Box>

            {/* Lots input */}
            <TextField
              label={adopt ? 'Lots to adopt' : `Lots to sell ${maxLots > 0 ? `(max ${maxLots})` : '(cap reached)'}`}
              type="number"
              value={lots}
              onChange={e => setLots(Math.max(1, parseInt(e.target.value) || 1))}
              inputProps={{ min: 1, ...(adopt ? {} : { max: maxLots }) }}
              size="small"
              fullWidth
              error={!adopt && (lots > maxLots || maxLots <= 0)}
              helperText={!adopt && (maxLots <= 0 ? 'max_lots_per_side cap reached' : lots > maxLots ? `Max available: ${maxLots}` : '')}
            />

            {/* Fill price (adopt mode only) */}
            {adopt && (
              <TextField
                label="Your fill price (entry premium $)"
                type="number"
                value={adoptFillPrice}
                onChange={e => setAdoptFillPrice(e.target.value)}
                size="small"
                fullWidth
                autoFocus
                placeholder="e.g. 73.02"
                inputProps={{ min: 0.01, step: 0.01 }}
                error={adoptFillPrice !== '' && Number(adoptFillPrice) <= 0}
                helperText="The premium you received when you sold. Used for P&L tracking."
              />
            )}

            {/* Confirmation toggle */}
            <Box sx={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              border: '1px solid', borderColor: confirmed ? (adopt ? 'info.main' : 'warning.main') : 'divider',
              borderRadius: 1, px: 1.5, py: 0.5,
              backgroundColor: confirmed ? (adopt ? 'rgba(33,150,243,0.08)' : 'rgba(255,152,0,0.08)') : 'transparent',
              transition: 'all 0.2s',
            }}>
              <Typography variant="body2" sx={{ fontWeight: confirmed ? 700 : 400, color: confirmed ? (adopt ? 'info.main' : 'warning.main') : 'text.secondary' }}>
                {adopt ? 'I confirm this registers an existing exchange position' : 'I confirm this places a real SELL order'}
              </Typography>
              <Switch checked={confirmed} onChange={e => setConfirmed(e.target.checked)} color={adopt ? 'info' : 'warning'} size="small" />
            </Box>

            {error && <Alert severity="error">{error}</Alert>}
          </Box>
        )}
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={handleClose} disabled={loading}>
          {isDone ? 'Close' : 'Cancel'}
        </Button>
        {!isDone && (
          <Button
            variant="contained"
            color={adopt ? 'info' : 'warning'}
            onClick={handleSubmit}
            disabled={loading || !isValid || !confirmed}
            startIcon={loading ? <CircularProgress size={16} color="inherit" /> : null}
          >
            {loading
              ? (adopt ? 'Adopting...' : 'Placing order...')
              : adopt
                ? `Adopt ${lots} Lot${lots !== 1 ? 's' : ''} @ ${effectiveStrike >= 1000 ? effectiveStrike.toLocaleString() : '—'}`
                : `Sell ${lots} Lot${lots !== 1 ? 's' : ''} @ ${effectiveStrike >= 1000 ? effectiveStrike.toLocaleString() : '—'}`
            }
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};

/**
 * Session detail panel — tabbed live dashboard view
 */
const SessionDetail = ({ session, wsData, socket, onBothSidesAction, onPartialEntryAction, onStrikePromoted }) => {
  const [detailTab, setDetailTab] = useState(0);
  const [reduceOpen, setReduceOpen] = useState(false);
  const [injectOpen, setInjectOpen] = useState(false);
  // Close-strike confirmation dialog state
  const [closeStrikeDlg, setCloseStrikeDlg] = useState({
    open: false, side: '', strike: 0, lots: 0, currentPremium: null, loading: false, error: '',
  });
  // Adjust-lots dialog state (+ or - lots on CE/PE side)
  const [adjustLotsDlg, setAdjustLotsDlg] = useState({
    open: false, side: '', direction: 'add', activeLots: 0, activeStrike: 0,
    qty: 1, loading: false, error: '',
  });

  // Dangerous Mode dialog state
  const [dangerDlg, setDangerDlg] = useState({ open: false, confirmText: '', loading: false });
  const isDangerousMode = session?.params?.dangerous_mode === true;

  const handleDangerousModeToggle = async () => {
    if (isDangerousMode) {
      // Turn OFF — no confirmation needed
      try {
        await mmmService.updateSessionParams(session.session_id, { dangerous_mode: false });
      } catch (e) {
        console.error('Failed to disable dangerous mode', e);
      }
    } else {
      setDangerDlg({ open: true, confirmText: '', loading: false });
    }
  };

  const handleDangerConfirm = async () => {
    if (dangerDlg.confirmText !== 'CONFIRM') return;
    setDangerDlg(d => ({ ...d, loading: true }));
    try {
      await mmmService.updateSessionParams(session.session_id, { dangerous_mode: true });
      setDangerDlg({ open: false, confirmText: '', loading: false });
    } catch (e) {
      console.error('Failed to enable dangerous mode', e);
      setDangerDlg(d => ({ ...d, loading: false }));
    }
  };

  // M-30 fix: Reset tab when session changes (avoids showing empty P&L tab on fresh session)
  useEffect(() => {
    setDetailTab(0);
  }, [session?.session_id]);

  // P&L curve data — shared between RiskProfileChart (fetches it) and CombinedZoneWidget (consumes computed_breakeven)
  const [pnlCurveData, setPnlCurveData] = useState(null);
  // Keep a ref so heartbeat effect always sees latest curve data (avoids stale closure)
  const pnlCurveDataRef = React.useRef(null);
  React.useEffect(() => { pnlCurveDataRef.current = pnlCurveData; }, [pnlCurveData]);

  // Helper: compute BE distance from curve when engine is disabled
  const computeBeDistanceFromCurve = (curveData, spotOverride) => {
    if (!curveData?.computed_breakeven) return null;
    const sp = spotOverride || curveData.spot_price;
    if (!sp || sp <= 0) return null;
    const cb = curveData.computed_breakeven;
    const distances = [cb.lower_breakeven, cb.upper_breakeven]
      .filter(v => v != null)
      .map(v => Math.abs(v - sp) / sp * 100);
    return distances.length > 0 ? Math.min(...distances) : null;
  };

  // Rolling heartbeat history for distance timeline chart (max 200 entries)
  const [heartbeatHistory, setHeartbeatHistory] = React.useState([]);

  // Seed history when curve first loads (so chart has data immediately, not waiting for next heartbeat)
  React.useEffect(() => {
    if (!pnlCurveData?.computed_breakeven) return;
    const beDistance = computeBeDistanceFromCurve(pnlCurveData);
    if (beDistance == null) return;
    const entry = { ts: new Date().toISOString(), beDistance, gammaDistance: null, beZone: 'SAFE', gammaZone: 'SAFE' };
    setHeartbeatHistory(prev => {
      // Only seed if empty or last entry has no beDistance (avoid duplicate on re-renders)
      if (prev.length > 0 && prev[prev.length - 1].beDistance != null) return prev;
      return [...prev, entry];
    });
  }, [pnlCurveData]); // eslint-disable-line react-hooks/exhaustive-deps

  React.useEffect(() => {
    const beResult = wsData?.heartbeat?.breakeven;
    const gammaResult = wsData?.heartbeat?.gamma;
    // Use engine result if available, else compute from curve (ref is always fresh)
    let beDistance = beResult?.nearest_distance_pct ?? null;
    let beZone = beResult?.zone || null;
    if (beDistance == null) {
      beDistance = computeBeDistanceFromCurve(pnlCurveDataRef.current);
    }
    if (!beDistance && !gammaResult) return;
    const entry = {
      ts: new Date().toISOString(),
      beDistance,
      gammaDistance: gammaResult?.nearest_distance_pct ?? null,
      beZone: beZone || 'SAFE',
      gammaZone: gammaResult?.gamma_zone || 'SAFE',
    };
    setHeartbeatHistory(prev => {
      const updated = [...prev, entry];
      return updated.length > 200 ? updated.slice(-200) : updated;
    });
  }, [wsData?.heartbeat]); // eslint-disable-line react-hooks/exhaustive-deps

  // Session duration calculation — must be before early return (hooks rule)
  const sessionCreatedAt = session?.created_at || session?.entry_time;
  const [sessionDuration, setSessionDuration] = React.useState('');
  React.useEffect(() => {
    if (!sessionCreatedAt) { setSessionDuration('—'); return; }
    const calcDuration = () => {
      try {
        const ts = sessionCreatedAt.endsWith('Z') ? sessionCreatedAt : sessionCreatedAt + 'Z';
        const start = new Date(ts);
        if (isNaN(start.getTime())) { setSessionDuration('—'); return; }
        const diff = Math.max(0, Math.floor((Date.now() - start.getTime()) / 1000));
        const h = Math.floor(diff / 3600);
        const m = Math.floor((diff % 3600) / 60);
        const s = diff % 60;
        if (h > 0) setSessionDuration(`${h}h ${m}m`);
        else if (m > 0) setSessionDuration(`${m}m ${s}s`);
        else setSessionDuration(`${s}s`);
      } catch { setSessionDuration('—'); }
    };
    calcDuration();
    const iv = setInterval(calcDuration, 10000);
    return () => clearInterval(iv);
  }, [sessionCreatedAt]);

  // Expiry countdown for detail header — must be before early return
  const [expiryCountdown, setExpiryCountdown] = React.useState('');
  React.useEffect(() => {
    const calc = () => {
      const et = session?.expiry_time;
      if (!et) { setExpiryCountdown(''); return; }
      try {
        const ts = et.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(et) ? et : et + 'Z';
        const diff = new Date(ts).getTime() - Date.now();
        if (diff <= 0) { setExpiryCountdown('EXPIRED'); return; }
        const totalMin = Math.floor(diff / 60000);
        const h = Math.floor(totalMin / 60);
        const m = totalMin % 60;
        setExpiryCountdown(h > 0 ? `${h}h ${m}m left` : `${m}m left`);
      } catch { setExpiryCountdown(''); }
    };
    calc();
    const iv = setInterval(calc, 30000);
    return () => clearInterval(iv);
  }, [session?.expiry_time]);

  // C-9 fix: safe reference to heartbeat data (may be undefined on initial load/reconnect)
  // Moved ABOVE early return so useMemo below can reference it (React hooks rule).
  const heartbeat = wsData?.heartbeat || null;

  const [activeStrikeSnack, setActiveStrikeSnack] = useState({ open: false, message: '', severity: 'success' });

  // --- Set Active Strike ---
  const handleSetActiveStrike = async (sideKey, strike) => {
    try {
      const res = await mmmService.setActiveStrike(session.session_id, sideKey, strike);
      if (!res.success) {
        setActiveStrikeSnack({ open: true, message: res.error || 'Cannot set active strike', severity: 'warning' });
      } else {
        setActiveStrikeSnack({ open: true, message: `Active strike set to ${Number(strike).toLocaleString()} ${sideKey.toUpperCase()}`, severity: 'success' });
        if (onStrikePromoted) onStrikePromoted();
      }
    } catch (e) {
      const msg = e.response?.data?.error || e.message || 'Request failed';
      setActiveStrikeSnack({ open: true, message: msg, severity: 'error' });
    }
  };

  // --- Close Strike (open confirmation dialog) ---
  const handleCloseStrikeRequest = (sideKey, strike, lots, currentPremium) => {
    setCloseStrikeDlg({ open: true, side: sideKey, strike, lots, currentPremium, loading: false, error: '' });
  };

  const handleCloseStrikeConfirm = async () => {
    setCloseStrikeDlg(d => ({ ...d, loading: true, error: '' }));
    try {
      const res = await mmmService.closeStrike(session.session_id, closeStrikeDlg.side, closeStrikeDlg.strike);
      if (res.success) {
        setCloseStrikeDlg(d => ({ ...d, open: false, loading: false }));
      } else {
        setCloseStrikeDlg(d => ({ ...d, loading: false, error: res.error || 'Close failed' }));
      }
    } catch (e) {
      const msg = e?.response?.data?.error || e.message;
      setCloseStrikeDlg(d => ({
        ...d, loading: false,
        error: msg.includes('fetch') || msg.includes('Network')
          ? 'Backend unreachable — server may be restarting. Please try again.'
          : msg,
      }));
    }
  };

  // --- Adjust Active Lots (+/-) ---
  const handleAdjustLotsRequest = (sideKey, direction, activeLots, activeStrike) => {
    setAdjustLotsDlg({
      open: true, side: sideKey, direction, activeLots, activeStrike,
      qty: 1, loading: false, error: '',
    });
  };

  const handleAdjustLotsConfirm = async () => {
    const { side, direction, qty } = adjustLotsDlg;
    const delta = direction === 'add' ? qty : -qty;
    setAdjustLotsDlg(d => ({ ...d, loading: true, error: '' }));
    try {
      const res = await mmmService.adjustActiveLots(session.session_id, side, delta);
      if (res.success) {
        setAdjustLotsDlg(d => ({ ...d, open: false, loading: false }));
      } else {
        setAdjustLotsDlg(d => ({ ...d, loading: false, error: res.error || 'Adjust failed' }));
      }
    } catch (e) {
      const msg = e?.response?.data?.error || e.message;
      setAdjustLotsDlg(d => ({
        ...d, loading: false,
        error: msg.includes('fetch') || msg.includes('Network')
          ? 'Backend unreachable — server may be restarting. Please try again.'
          : msg,
      }));
    }
  };

  // BUG FIX: Compute proper per-side P&L from individual position rows.
  // The old formula used (entry_fill_price - activePremium) × totalLots which is wrong
  // because it applies one entry premium and one live premium to ALL lots including
  // frozen lots at different strikes with different premiums.
  // Must be before early return (React hooks rule — hooks must always be called).
  const sideMetrics = useMemo(() => {
    if (!session) return { ce: { pnl: 0, hasPnl: false, totalLots: 0, avgEntry: 0, totalEntryWeighted: 0 },
                           pe: { pnl: 0, hasPnl: false, totalLots: 0, avgEntry: 0, totalEntryWeighted: 0 } };
    const rows = buildPositionRows(session, heartbeat);
    const metrics = { ce: { pnl: 0, hasPnl: false, totalLots: 0, totalEntryWeighted: 0 },
                      pe: { pnl: 0, hasPnl: false, totalLots: 0, totalEntryWeighted: 0 } };
    for (const row of rows) {
      const sk = row.side === 'CE' ? 'ce' : 'pe';
      metrics[sk].totalLots += row.lots;
      metrics[sk].totalEntryWeighted += row.lots * (row.entryPremium || 0);
      if (row.pnl != null) {
        metrics[sk].pnl += row.pnl;
        metrics[sk].hasPnl = true;
      }
    }
    // Compute weighted average entry premium per side
    for (const sk of ['ce', 'pe']) {
      metrics[sk].avgEntry = metrics[sk].totalLots > 0
        ? metrics[sk].totalEntryWeighted / metrics[sk].totalLots : 0;
    }
    return metrics;
  }, [session, heartbeat]);

  if (!session) {
    return (
      <Box sx={{ p: 4, textAlign: 'center' }}>
        <Typography variant="body1" color="text.secondary">
          Select a session to view details
        </Typography>
      </Box>
    );
  }

  const ce = session.ce || {};
  const pe = session.pe || {};
  const status = session.strategy_status || session.status || 'IDLE';
  const isLive = ['RUNNING', 'PAUSED', 'BOTH_SIDES_UP'].includes(status);

  // P&L calculations — H-14 fix: use ?? 0 to prevent NaN when backend returns null
  // Prefer session.net_pnl (kept fresh by mmm_pnl_update event) over locally-recomputed value.
  // Use session.unrealized_pnl directly — _overlay_live_pnl sets all 4 values atomically so
  // they are always from the same snapshot. Deriving unrealized = net - realized incorrectly
  // merged fees into the unrealized display (net - R = U - F, not U).
  const realized = session.realized_pnl ?? 0;
  const fees = session.total_fees ?? 0;
  const netPnl = session.net_pnl ?? ((session.realized_pnl ?? 0) + (session.unrealized_pnl ?? 0) - fees);
  const unrealized = session.unrealized_pnl ?? 0;
  // net_premium_collected = gross sells minus buyback costs (decreases on close)
  // Falls back to gross total_premium_collected for old sessions without ledger data
  const totalPremium = session.net_premium_collected ?? session.total_premium_collected ?? 0;
  const cePremiumCollected = session.ce_net_premium ?? session.ce_premium_collected ?? 0;
  const pePremiumCollected = session.pe_net_premium ?? session.pe_premium_collected ?? 0;
  const peakPnl = session.peak_pnl ?? 0;
  // L-11: Compute drawdown from peak for display
  const peakDrawdown = peakPnl - netPnl;

  // Warnings card — aggregate active recon discrepancies + checksum flag
  const _reconDiscs = session?._last_auto_recon_discrepancies || [];
  const _warnTotal = _reconDiscs.length + (session?._checksum_warning ? 1 : 0);
  const _warnValue = _warnTotal === 0 ? '✓ Clear' : `⚠ ${_warnTotal} active`;
  const _warnSub = _warnTotal === 0 ? null
    : session?._checksum_warning ? 'Checksum mismatch'
    : (_reconDiscs[0]?.type || '').replace(/_/g, ' ').toLowerCase();
  const _warnColor = _warnTotal === 0 ? '#66bb6a' : '#ff9800';
  const _warnBg    = _warnTotal === 0 ? 'rgba(102,187,106,0.08)' : 'rgba(255,152,0,0.08)';
  const _warnBorder= _warnTotal === 0 ? 'rgba(102,187,106,0.3)'  : 'rgba(255,152,0,0.3)';

  // Current premium from heartbeat for CE/PE cards.
  // Fallback to session._premium_map (persisted by backend on every heartbeat) when
  // the WebSocket event hasn't fired yet (e.g. PAUSED/STOPPED sessions).
  const sessionPremiumMap = session?._premium_map || {};
  const _cePremiumFromMap = (() => {
    const strike = ce?.active_strike;
    if (!strike) return null;
    const key = `${Math.round(strike)}:call`;
    const v = sessionPremiumMap[key];
    return (v != null && v > 0) ? v : null;
  })();
  const _pePremiumFromMap = (() => {
    const strike = pe?.active_strike;
    if (!strike) return null;
    const key = `${Math.round(strike)}:put`;
    const v = sessionPremiumMap[key];
    return (v != null && v > 0) ? v : null;
  })();
  const ceLivePremium = heartbeat?.ce_premium ?? _cePremiumFromMap ?? null;
  const peLivePremium = heartbeat?.pe_premium ?? _pePremiumFromMap ?? null;

  // Live bid/ask from options_ticker_update (sub-second, same pipeline as options panel)
  const expiry = session.params?.expiry;
  const ceSymbol = ce.active_strike && expiry ? `C-BTC-${Math.round(ce.active_strike)}-${expiry}` : null;
  const peSymbol = pe.active_strike && expiry ? `P-BTC-${Math.round(pe.active_strike)}-${expiry}` : null;
  const livePrices = wsData?.livePrices || {};
  const ceLive = ceSymbol ? livePrices[ceSymbol] : null;
  const peLive = peSymbol ? livePrices[peSymbol] : null;
  // isLiveRecent: true if last WS update was within 10s
  const _now = Date.now() / 1000;
  const ceLiveRecent = ceLive && (_now - ceLive.ts) < 10;
  const peLiveRecent = peLive && (_now - peLive.ts) < 10;

  return (
    <Box sx={{ p: 2 }}>
      {/* Status Banner — ALWAYS shown */}
      <Box sx={{ mb: 2 }}>
        <MMMStatusBanner session={session} heartbeat={heartbeat} onBothSidesAction={onBothSidesAction} onPartialEntryAction={onPartialEntryAction} />
      </Box>

      {/* Detail Tabs */}
      <Tabs
        value={detailTab}
        onChange={(e, v) => setDetailTab(v)}
        variant="scrollable"
        scrollButtons="auto"
        sx={{ mb: 2, borderBottom: 1, borderColor: 'divider' }}
      >
        <Tab label="Overview" />
        <Tab label="Positions" />
        <Tab label="Triggers" />
        <Tab label="Adjustments" />
        <Tab label="P&L" />
        <Tab label="Safety" />
        <Tab label="Strike Map" />
        <Tab label="Algo Calculations" />
        <Tab label="Consolidated" />
        <Tab label="Greeks & IV" />
        <Tab label="Analytics" />
        <Tab label="Margin" />
        <Tab label="Regime" />
        <Tab label="Perp Hedge" />
        <Tab label="Risk" />
        <Tab label="Performance" />
        <Tab label="Audit" />
        <Tab label="Exec Log" />
        <Tab label="Reverse Mode" />
      </Tabs>

      {/* Tab 0: Overview — Professional KPI Dashboard */}
      {detailTab === 0 && (
        <Box>
          {/* Expandable strategy explainer for new users */}
          <StrategyExplainer />

          {/* Session ID + Status Header */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
              <Typography variant="h6" sx={{ fontFamily: 'monospace', fontWeight: 700 }}>
                {session.session_id}
              </Typography>
              {session.params?.expiry && (
                <Chip
                  label={`Expiry: ${formatExpiry(session.params.expiry)}`}
                  size="small"
                  variant="outlined"
                  sx={{ fontFamily: 'monospace' }}
                />
              )}
              {expiryCountdown && (
                <Chip
                  label={`⏱ ${expiryCountdown}`}
                  size="small"
                  sx={{
                    fontFamily: 'monospace',
                    fontWeight: 600,
                    bgcolor: expiryCountdown === 'EXPIRED' ? 'rgba(244,67,54,0.15)' : 'rgba(255,152,0,0.12)',
                    color: expiryCountdown === 'EXPIRED' ? '#f44336' : '#ff9800',
                  }}
                />
              )}
              {sessionDuration && sessionDuration !== '—' && (
                <Chip
                  label={`Running: ${sessionDuration}`}
                  size="small"
                  variant="outlined"
                  sx={{ fontFamily: 'monospace', fontSize: '0.78rem', color: 'text.secondary' }}
                />
              )}
              {/* Straddle Roll badge — only for STRADDLE_WITH_ADJUSTMENT sessions */}
              {(session.params?._preset_source === 'STRADDLE_WITH_ADJUSTMENT' || session.params?.dte_category === 'STRADDLE_WITH_ADJUSTMENT') &&
                session._straddle_roll_count != null && (
                <Tooltip title={
                  <span>
                    {session._straddle_last_roll_at
                      ? `Last roll: ${new Date(session._straddle_last_roll_at).toLocaleTimeString()}`
                      : 'No rolls yet'}
                    {session._straddle_roll_trigger_pts > 0
                      ? ` | Next trigger: ±${Math.round(session._straddle_roll_trigger_pts)} pts`
                      : ''}
                    {' • Hot-reloadable: change max_per_session in settings to add more rolls'}
                  </span>
                }>
                  <Chip
                    label={`🔄 Rolls: ${session._straddle_roll_count}/${session.params?.straddle_roll_max_per_session ?? '?'}`}
                    size="small"
                    sx={{
                      fontFamily: 'monospace',
                      fontWeight: 600,
                      bgcolor: session._straddle_roll_count > 0 ? 'rgba(33,150,243,0.15)' : 'rgba(255,255,255,0.06)',
                      color: session._straddle_roll_count > 0 ? '#42a5f5' : 'text.secondary',
                    }}
                  />
                </Tooltip>
              )}
              {/* Price Guard indicator — shows when real-time 5s spot monitor is active */}
              {(session.params?._preset_source === 'STRADDLE_WITH_ADJUSTMENT' || session.params?.dte_category === 'STRADDLE_WITH_ADJUSTMENT') &&
                session.params?.price_guard_enabled !== false &&
                status === 'RUNNING' && (
                <Tooltip title="⚡ Price Guard active — spot monitored every 5s, heartbeat forced when approaching roll trigger">
                  <Chip
                    label="⚡ Guard"
                    size="small"
                    sx={{
                      fontSize: '0.65rem',
                      fontFamily: 'monospace',
                      bgcolor: 'rgba(76,175,80,0.15)',
                      color: '#66bb6a',
                    }}
                  />
                </Tooltip>
              )}
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {['RUNNING', 'PAUSED'].includes(status) && (
                <Tooltip title={isDangerousMode
                  ? 'DANGEROUS MODE ON — click to disable and restore all safety gates'
                  : '⚠️ Dangerous Mode — bypass all safety gates except max loss & ITM guard. Use during 0DTE expiry only.'
                }>
                  <Button
                    size="small"
                    variant={isDangerousMode ? 'contained' : 'outlined'}
                    startIcon={<DangerIcon fontSize="small" />}
                    onClick={handleDangerousModeToggle}
                    sx={{
                      fontSize: '0.7rem',
                      py: 0.3,
                      px: 1,
                      fontWeight: 700,
                      minWidth: 0,
                      borderColor: '#b71c1c',
                      color: isDangerousMode ? '#fff' : '#ef9a9a',
                      backgroundColor: isDangerousMode ? '#c62828' : 'transparent',
                      animation: isDangerousMode ? 'pulse-danger 1.5s ease-in-out infinite' : 'none',
                      '@keyframes pulse-danger': {
                        '0%, 100%': { boxShadow: '0 0 0 0 rgba(244,67,54,0.5)' },
                        '50%': { boxShadow: '0 0 0 6px rgba(244,67,54,0)' },
                      },
                      '&:hover': {
                        backgroundColor: isDangerousMode ? '#b71c1c' : 'rgba(183,28,28,0.15)',
                        borderColor: '#f44336',
                      },
                    }}
                  >
                    {isDangerousMode ? '🔥 DANGEROUS MODE: ON' : 'Dangerous Mode'}
                  </Button>
                </Tooltip>
              )}
              <StatusChip status={status} />
            </Box>
          </Box>

          {/* KPI Cards Row */}
          <Grid container spacing={1.5} sx={{ mb: 2 }}>
            {[
              {
                label: 'Net P&L',
                help: 'net_pnl',
                value: `$${netPnl.toFixed(2)}`,
                color: netPnl >= 0 ? '#4caf50' : '#f44336',
                bg: netPnl >= 0 ? 'rgba(76,175,80,0.08)' : 'rgba(244,67,54,0.08)',
                border: netPnl >= 0 ? 'rgba(76,175,80,0.3)' : 'rgba(244,67,54,0.3)',
              },
              {
                label: 'Net Premium',
                help: 'total_premium',
                value: `$${totalPremium.toFixed(2)}`,
                sub: `CE $${cePremiumCollected.toFixed(2)} | PE $${pePremiumCollected.toFixed(2)}`,
                subColor: 'text.secondary',
                color: '#2196f3',
                bg: 'rgba(33,150,243,0.08)',
                border: 'rgba(33,150,243,0.3)',
              },
              {
                label: 'Realized',
                help: 'realized_pnl',
                value: `$${realized.toFixed(2)}`,
                color: realized >= 0 ? '#66bb6a' : '#ef5350',
                bg: 'rgba(255,255,255,0.04)',
                border: 'rgba(255,255,255,0.12)',
              },
              {
                label: 'Unrealized',
                help: 'unrealized_pnl',
                value: `$${unrealized.toFixed(2)}`,
                color: unrealized >= 0 ? '#66bb6a' : '#ef5350',
                bg: 'rgba(255,255,255,0.04)',
                border: 'rgba(255,255,255,0.12)',
              },
              {
                label: 'Peak P&L',
                help: 'peak_pnl',
                value: `$${peakPnl.toFixed(2)}`,
                // L-11 fix: Show drawdown delta from peak
                sub: peakDrawdown > 0.01 ? `↓ $${peakDrawdown.toFixed(2)} from peak` : null,
                color: '#ab47bc',
                bg: 'rgba(171,71,188,0.08)',
                border: 'rgba(171,71,188,0.3)',
              },
              {
                label: 'Warnings',
                help: 'session_warnings',
                value: _warnValue,
                sub: _warnSub,
                subColor: '#ff9800',
                color: _warnColor,
                bg: _warnBg,
                border: _warnBorder,
              },
            ].map(({ label, help, value, sub, subColor, color, bg, border }) => (
              <Grid item xs={4} sm={2} key={label}>
                <Paper
                  elevation={0}
                  sx={{
                    p: 1.5,
                    textAlign: 'center',
                    backgroundColor: bg,
                    border: `1px solid ${border}`,
                    borderRadius: 2,
                  }}
                >
                  <HelpTooltip topic={help}>
                    <Typography
                      variant="caption"
                      sx={{ color: 'text.secondary', display: 'block', mb: 0.5, fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: 0.5 }}
                    >
                      {label}
                    </Typography>
                  </HelpTooltip>
                  <Typography
                    variant="body1"
                    sx={{ fontWeight: 700, fontFamily: 'monospace', color, fontSize: '1.1rem' }}
                  >
                    {value}
                  </Typography>
                  {/* L-11: Show sub-label (e.g., drawdown from peak) */}
                  {sub && (
                    <Typography variant="caption" sx={{ color: subColor || '#ef5350', display: 'block', mt: 0.25, fontSize: '0.7rem' }}>
                      {sub}
                    </Typography>
                  )}
                </Paper>
              </Grid>
            ))}
          </Grid>

          {/* CE / PE Side-by-side — Enriched Cards */}
          <Grid container spacing={2} sx={{ mb: 2 }}>
            {[
              { key: 'CE', helpKey: 'ce_side', data: ce, color: '#4caf50', gradStart: 'rgba(76,175,80,0.15)', gradEnd: 'rgba(76,175,80,0.02)' },
              { key: 'PE', helpKey: 'pe_side', data: pe, color: '#f44336', gradStart: 'rgba(244,67,54,0.15)', gradEnd: 'rgba(244,67,54,0.02)' },
            ].map(({ key, helpKey, data, color, gradStart, gradEnd }) => (
              <Grid item xs={6} key={key}>
                <Paper
                  elevation={0}
                  sx={{
                    p: 2,
                    borderRadius: 2,
                    border: `1px solid ${color}33`,
                    background: `linear-gradient(135deg, ${gradStart} 0%, ${gradEnd} 100%)`,
                  }}
                >
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
                    <HelpTooltip topic={helpKey}>
                      <Typography variant="subtitle1" sx={{ fontWeight: 700, color }}>
                        {key === 'CE' ? '📈' : '📉'} {key} Side
                      </Typography>
                    </HelpTooltip>
                    <HelpTooltip topic="total_lots">
                      <Chip
                        label={`${data.active_lots ?? data.total_lots ?? 0} active${data.frozen_total_lots ? ` (+${data.frozen_total_lots} frozen)` : ''}`}
                        size="small"
                        sx={{
                          backgroundColor: `${color}22`,
                          color,
                          fontWeight: 700,
                          fontFamily: 'monospace',
                        }}
                      />
                    </HelpTooltip>
                  </Box>

                  {/* Key metrics in a compact grid */}
                  <Grid container spacing={0.5}>
                    <Grid item xs={6}>
                      <Box sx={{ mb: 1 }}>
                        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.85rem' }}>Strike</Typography>
                        <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: 'monospace' }}>
                          {data.active_strike ? data.active_strike.toLocaleString() : '—'}
                        </Typography>
                      </Box>
                    </Grid>
                    <Grid item xs={6}>
                      <Box sx={{ mb: 1 }}>
                        {/* BUG FIX: Show weighted avg entry across ALL positions, not just original fill */}
                        {(() => {
                          const sk = key.toLowerCase();
                          const avgEntry = sideMetrics[sk].avgEntry;
                          const origEntry = data.entry_fill_price || data.original_premium || 0;
                          const showWeighted = avgEntry > 0 && Math.abs(avgEntry - origEntry) > 0.5;
                          return (
                            <>
                              <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.85rem' }}>
                                {showWeighted ? 'Avg Entry' : 'Entry Premium'}
                              </Typography>
                              <Tooltip title={showWeighted ? `Weighted avg across ${sideMetrics[sk].totalLots} lots. Original fill: $${origEntry.toFixed(2)}` : ''} arrow>
                                <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: 'monospace' }}>
                                  ${avgEntry > 0 ? avgEntry.toFixed(2) : (origEntry?.toFixed(2) || '—')}
                                </Typography>
                              </Tooltip>
                            </>
                          );
                        })()}
                      </Box>
                    </Grid>
                    <Grid item xs={6}>
                      <Box sx={{ mb: 1 }}>
                        {(() => {
                          const liveWs = key === 'CE' ? ceLive : peLive;
                          const liveRecent = key === 'CE' ? ceLiveRecent : peLiveRecent;
                          const livePremium = key === 'CE' ? ceLivePremium : peLivePremium;
                          const sk = key.toLowerCase();
                          const avgEntry = sideMetrics[sk].avgEntry;
                          // Prefer WS mid price; fallback to heartbeat premium
                          const displayPremium = (liveWs?.mid > 0) ? liveWs.mid : livePremium;
                          const hasLive = displayPremium != null && displayPremium > 0;
                          const pctChange = hasLive && avgEntry > 0
                            ? ((displayPremium - avgEntry) / avgEntry * 100)
                            : null;
                          const premColor = pctChange != null
                            ? (pctChange <= 0 ? '#4caf50' : '#f44336')
                            : 'text.primary';
                          return (
                            <>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.85rem' }}>
                                  Current Premium
                                </Typography>
                                {liveRecent && (
                                  <Box component="span" sx={{
                                    width: 6, height: 6, borderRadius: '50%', bgcolor: '#4caf50',
                                    display: 'inline-block', flexShrink: 0,
                                    animation: 'pulse 1.5s ease-in-out infinite',
                                    '@keyframes pulse': {
                                      '0%': { opacity: 1 }, '50%': { opacity: 0.3 }, '100%': { opacity: 1 },
                                    },
                                  }} />
                                )}
                              </Box>
                              <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 0.5 }}>
                                <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: 'monospace', color: premColor }}>
                                  {hasLive ? `$${displayPremium.toFixed(2)}` : '—'}
                                </Typography>
                                {pctChange != null && (
                                  <Typography variant="caption" sx={{ fontFamily: 'monospace', color: premColor, fontSize: '0.75rem' }}>
                                    {pctChange <= 0 ? '▼' : '▲'}{Math.abs(pctChange).toFixed(1)}%
                                  </Typography>
                                )}
                              </Box>
                              {liveWs?.bid > 0 && liveWs?.ask > 0 && (
                                <Typography variant="caption" sx={{ fontFamily: 'monospace', color: 'text.secondary', fontSize: '0.72rem', display: 'block' }}>
                                  B:{liveWs.bid.toFixed(1)} / A:{liveWs.ask.toFixed(1)}
                                </Typography>
                              )}
                            </>
                          );
                        })()}
                      </Box>
                    </Grid>
                    <Grid item xs={6}>
                      <Box sx={{ mb: 1 }}>
                        {/* BUG FIX: Use proper per-position P&L from buildPositionRows
                            instead of (entryFill - activePremium) × totalLots which
                            applies one premium to all lots including frozen at different strikes */}
                        {(() => {
                          const sk = key.toLowerCase();
                          const m = sideMetrics[sk];
                          const sidePnl = m.hasPnl ? m.pnl : null;
                          return (
                            <>
                              <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.85rem' }}>Side P&L</Typography>
                              <Typography variant="body2" sx={{
                                fontWeight: 700,
                                fontFamily: 'monospace',
                                color: sidePnl != null ? (sidePnl >= 0 ? '#4caf50' : '#f44336') : 'text.secondary',
                              }}>
                                {sidePnl != null ? `${sidePnl >= 0 ? '+' : ''}$${sidePnl.toFixed(4)}` : '—'}
                              </Typography>
                            </>
                          );
                        })()}
                      </Box>
                    </Grid>
                    <Grid item xs={4}>
                      <Box>
                        <HelpTooltip topic="original_lots">
                          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.85rem' }}>Original</Typography>
                        </HelpTooltip>
                        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>{data.original_lots || 0}</Typography>
                      </Box>
                    </Grid>
                    <Grid item xs={4}>
                      <Box>
                        <HelpTooltip topic="adjustment_lots">
                          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.85rem' }}>Adj Lots</Typography>
                        </HelpTooltip>
                        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>{data.adjustment_total_lots || 0}</Typography>
                      </Box>
                    </Grid>
                    <Grid item xs={4}>
                      <Box>
                        <HelpTooltip topic="frozen_lots">
                          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.85rem' }}>Frozen</Typography>
                        </HelpTooltip>
                        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>{data.frozen_total_lots || 0}</Typography>
                      </Box>
                    </Grid>
                  </Grid>

                  {/* Manual lot adjustment — only when session is live */}
                  {isLive && (
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 0.5, mt: 1, pt: 1, borderTop: `1px solid ${color}22` }}>
                      <Tooltip
                        title={
                          (data.active_lots ?? data.total_lots ?? 0) === 0
                            ? `No active ${key} lots to remove`
                            : `Remove lots from ${key} @ ${Number(data.active_strike || 0).toLocaleString()} — currently ${data.active_lots ?? data.total_lots ?? 0} active`
                        }
                        arrow
                      >
                        <span>
                          <IconButton
                            size="small"
                            onClick={() => handleAdjustLotsRequest(
                              key.toLowerCase(), 'remove',
                              data.active_lots ?? data.total_lots ?? 0,
                              data.active_strike,
                            )}
                            disabled={(data.active_lots ?? data.total_lots ?? 0) === 0}
                            sx={{
                              color: '#f44336',
                              border: '1px solid rgba(244,67,54,0.35)',
                              borderRadius: 1,
                              p: 0.4,
                              '&:hover': { backgroundColor: 'rgba(244,67,54,0.12)' },
                            }}
                          >
                            <RemoveIcon sx={{ fontSize: 16 }} />
                          </IconButton>
                        </span>
                      </Tooltip>
                      <Tooltip
                        title={`Add lots to ${key} @ ${Number(data.active_strike || 0).toLocaleString()} — currently ${data.active_lots ?? data.total_lots ?? 0} active`}
                        arrow
                      >
                        <IconButton
                          size="small"
                          onClick={() => handleAdjustLotsRequest(
                            key.toLowerCase(), 'add',
                            data.active_lots ?? data.total_lots ?? 0,
                            data.active_strike,
                          )}
                          sx={{
                            color,
                            border: `1px solid ${color}55`,
                            borderRadius: 1,
                            p: 0.4,
                            '&:hover': { backgroundColor: `${color}18` },
                          }}
                        >
                          <AddIcon sx={{ fontSize: 16 }} />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  )}
                </Paper>
              </Grid>
            ))}
          </Grid>

          {/* Inline Trigger Gauges (visible on Overview, not hidden in tab) */}
          <Paper elevation={0} sx={{ p: 2, mb: 2, borderRadius: 2, border: '1px solid rgba(255,255,255,0.12)' }}>
            <HelpTooltip topic="trigger_system">
              <Typography variant="subtitle2" sx={{ mb: 0.5, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 1 }}>
                🎯 Trigger Gauges
              </Typography>
            </HelpTooltip>
            <SectionBlurb topic="trigger_system" />
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5, lineHeight: 1.5 }}>
              🖱️ <strong>Drag the white marker right</strong> to lock a higher trigger threshold — the algo won't fire an adjustment until premium crosses your chosen level. The cyan marker and 🔒 label appear when locked. Click the cyan marker to unlock. Locks auto-release after 3 adjustments.
            </Typography>
            <MMMTriggerGauge
              session={session}
              heartbeat={heartbeat}
              triggerData={heartbeat}
            />
          </Paper>

          {/* Breakeven Band Panel */}
          {isLive && (session.params?.breakeven_control_enabled || heartbeat?.breakeven?.enabled) && (
            <MMMBreakevenPanel
              breakeven={heartbeat?.breakeven || session._breakeven_result}
              gamma={heartbeat?.gamma || session._gamma_result}
            />
          )}

          {/* Gamma Detector Panel */}
          {isLive && (session.params?.gamma_detector_enabled || heartbeat?.gamma?.enabled) && (
            <MMMGammaPanel
              gamma={heartbeat?.gamma || session._gamma_result}
            />
          )}

          {/* Dangerous Mode banner — shown whenever dangerous_mode is ON */}
          {isDangerousMode && (
            <Alert
              severity="error"
              icon={<DangerIcon />}
              sx={{
                mb: 2,
                backgroundColor: 'rgba(180,0,0,0.18)',
                border: '2px solid #f44336',
                fontWeight: 700,
              }}
              action={
                <Button
                  color="inherit"
                  size="small"
                  variant="outlined"
                  sx={{ borderColor: '#f44336', color: '#f44336', fontWeight: 700 }}
                  onClick={handleDangerousModeToggle}
                >
                  DISABLE
                </Button>
              }
            >
              <Typography variant="subtitle2" sx={{ fontWeight: 800, color: '#f44336' }}>
                ⚠️ DANGEROUS MODE ACTIVE
              </Typography>
              <Typography variant="body2" sx={{ color: '#ffcdd2' }}>
                All safety gates are OFF. Only max loss hard stop, ITM guard, and auto-close near expiry remain active.
                Operator is fully responsible for risk management.
              </Typography>
            </Alert>
          )}

          {/* Why Paused — prominent banner in detail view */}
          {status === 'PAUSED' && session._paused_reason && (
            <Alert severity="warning" sx={{ mb: 2 }} icon={false}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.25 }}>
                ⏸️ Session Paused
              </Typography>
              <Typography variant="body2">
                {session._paused_reason}
              </Typography>
              {session._paused_at && (
                <Typography variant="caption" color="text.secondary">
                  Since {new Date(session._paused_at.endsWith('Z') ? session._paused_at : session._paused_at + 'Z').toLocaleTimeString()}
                </Typography>
              )}
            </Alert>
          )}

          {/* Live Safety & System Status Summary */}
          {isLive && heartbeat && (
            <Paper elevation={0} sx={{ p: 2, mb: 2, borderRadius: 2, border: '1px solid rgba(255,255,255,0.12)' }}>
              <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700 }}>
                🛡️ System Status
              </Typography>
              <Grid container spacing={1}>
                {/* Margin Tier */}
                <Grid item xs={6} sm={3}>
                  <Box sx={{ textAlign: 'center', p: 1, borderRadius: 1, backgroundColor: 'rgba(255,255,255,0.03)' }}>
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ fontSize: '0.75rem' }}>Margin</Typography>
                    <Typography variant="body2" sx={{
                      fontWeight: 700, fontFamily: 'monospace',
                      color: ({ GREEN: '#4caf50', YELLOW: '#ff9800', ORANGE: '#ff5722', RED: '#f44336', CRITICAL: '#9c27b0' })[heartbeat.margin?.tier] || '#9e9e9e',
                    }}>
                      {heartbeat.margin?.tier || 'N/A'}
                    </Typography>
                    {heartbeat.margin?.utilization_pct != null && (
                      <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.65rem' }}>
                        {heartbeat.margin.utilization_pct.toFixed(0)}% used
                      </Typography>
                    )}
                  </Box>
                </Grid>
                {/* Regime Action */}
                <Grid item xs={6} sm={3}>
                  <Box sx={{ textAlign: 'center', p: 1, borderRadius: 1, backgroundColor: 'rgba(255,255,255,0.03)' }}>
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ fontSize: '0.75rem' }}>Regime</Typography>
                    <Typography variant="body2" sx={{
                      fontWeight: 700, fontFamily: 'monospace',
                      color: (() => {
                        const action = heartbeat.regime?.action || 'NORMAL';
                        if (action === 'NORMAL') return '#4caf50';
                        if (action.startsWith('BLOCK')) return '#f44336';
                        return '#ff9800';
                      })(),
                    }}>
                      {heartbeat.regime?.action || 'NORMAL'}
                    </Typography>
                  </Box>
                </Grid>
                {/* Wind-Down */}
                <Grid item xs={6} sm={3}>
                  <Box sx={{ textAlign: 'center', p: 1, borderRadius: 1, backgroundColor: 'rgba(255,255,255,0.03)' }}>
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ fontSize: '0.75rem' }}>Wind-Down</Typography>
                    <Typography variant="body2" sx={{
                      fontWeight: 700, fontFamily: 'monospace',
                      color: heartbeat.wind_down_active ? '#ff9800' : '#4caf50',
                    }}>
                      {heartbeat.wind_down_active ? 'ACTIVE' : 'Off'}
                    </Typography>
                  </Box>
                </Grid>
                {/* Adaptive Tier */}
                <Grid item xs={6} sm={3}>
                  <Box sx={{ textAlign: 'center', p: 1, borderRadius: 1, backgroundColor: 'rgba(255,255,255,0.03)' }}>
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ fontSize: '0.75rem' }}>Interval</Typography>
                    <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: 'monospace', color: '#78909c' }}>
                      {heartbeat.adaptive_tier || 'normal'}
                    </Typography>
                  </Box>
                </Grid>
              </Grid>
            </Paper>
          )}

          {/* Heartbeat Health Panel */}
          <HeartbeatHealthPanel sessionId={session.session_id} status={status} />

          {/* Global State + Activity Counters */}
          <Paper elevation={0} sx={{ p: 2, borderRadius: 2, border: '1px solid rgba(255,255,255,0.12)' }}>
            <Typography variant="subtitle2" sx={{ mb: 0.5, fontWeight: 700 }}>
              📊 Algorithm State
            </Typography>
            <SectionBlurb topic="heartbeat" />
            <Grid container spacing={1}>
              {[
                { label: 'Adjustments', help: 'adjustment', value: session.adjustment_count || 0, icon: '⚙️' },
                { label: 'Reversals', help: 'reversal', value: session.reversal_count || 0, icon: '🔄' },
                { label: 'Shifts', help: 'strike_shift', value: session.shift_count || 0, icon: '↔️' },
                { label: 'Close-at-5', help: 'close_at_5', value: session.close_at_5_count || 0, icon: '🎯' },
                { label: 'Last Aggressor', help: 'aggressor', value: session.last_aggressor || 'NONE', icon: '🏷️' },
                { label: 'Cooldown', help: 'cooldown', value: session.cooldown_active ? '🟡 Active' : '🟢 No', icon: '' },
              ].map(({ label, help, value, icon }) => (
                <Grid item xs={4} sm={2} key={label}>
                  <Box sx={{ textAlign: 'center', p: 1, borderRadius: 1, backgroundColor: 'rgba(255,255,255,0.03)' }}>
                    <HelpTooltip topic={help}>
                      <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.8rem', textTransform: 'uppercase' }}>
                        {icon} {label}
                      </Typography>
                    </HelpTooltip>
                    <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: 'monospace' }}>
                      {value}
                    </Typography>
                  </Box>
                </Grid>
              ))}
            </Grid>
          </Paper>

          {/* P&L Attribution — breakdown by source */}
          {(session.pnl_initial || session.pnl_adjustment || session.pnl_harvest || session.pnl_recycle || session.pnl_perp) ? (
            <Paper elevation={0} sx={{ p: 2, mt: 2, borderRadius: 2, border: '1px solid rgba(255,255,255,0.12)' }}>
              <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700 }}>
                💰 P&L Attribution
              </Typography>
              <Grid container spacing={1}>
                {[
                  { label: 'Initial', value: session.pnl_initial || 0, color: '#2196f3' },
                  { label: 'Adjustments', value: session.pnl_adjustment || 0, color: '#ff9800' },
                  { label: 'Harvest', value: session.pnl_harvest || 0, color: '#4caf50' },
                  { label: 'Recycle', value: session.pnl_recycle || 0, color: '#ab47bc' },
                  { label: 'Perp Hedge', value: session.pnl_perp || 0, color: '#00bcd4' },
                ].filter(({ value }) => value !== 0).map(({ label, value, color }) => (
                  <Grid item xs={4} sm={2} key={label}>
                    <Box sx={{ textAlign: 'center', p: 1, borderRadius: 1, backgroundColor: 'rgba(255,255,255,0.03)' }}>
                      <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                        {label}
                      </Typography>
                      <Typography variant="body2" sx={{
                        fontWeight: 700, fontFamily: 'monospace',
                        color: value >= 0 ? color : '#f44336',
                      }}>
                        ${value.toFixed(2)}
                      </Typography>
                    </Box>
                  </Grid>
                ))}
              </Grid>
            </Paper>
          ) : null}

          {/* P&L Trend Mini-Chart */}
          {(() => {
            const history = session?.pnl_history || [];
            if (history.length < 3) return null;
            const chartData = history.map(h => ({
              t: new Date(h.timestamp.includes('+') || h.timestamp.endsWith('Z') ? h.timestamp : h.timestamp + 'Z')
                .toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              pnl: h.total_pnl,
              r: h.realized,
              u: h.unrealized,
            }));
            const lastPnl = chartData[chartData.length - 1]?.pnl || 0;
            const gradColor = lastPnl >= 0 ? '#4caf50' : '#f44336';
            return (
              <Paper elevation={0} sx={{ p: 2, mt: 2, borderRadius: 2, border: '1px solid rgba(255,255,255,0.12)' }}>
                <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700 }}>
                  📈 P&L Trend
                </Typography>
                <ResponsiveContainer width="100%" height={120}>
                  <AreaChart data={chartData}>
                    <defs>
                      <linearGradient id="pnlMiniGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={gradColor} stopOpacity={0.3} />
                        <stop offset="95%" stopColor={gradColor} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="t" tick={{ fontSize: 9 }} interval="preserveStartEnd" />
                    <YAxis tick={{ fontSize: 9 }} width={45} tickFormatter={v => `$${v.toFixed(1)}`} />
                    <RechartsTooltip
                      contentStyle={{ backgroundColor: '#1e1e1e', border: '1px solid #333', fontSize: 11 }}
                      formatter={(v, name) => [`$${Number(v).toFixed(3)}`, name === 'pnl' ? 'Net' : name === 'r' ? 'Realized' : 'Unrealized']}
                    />
                    <ReferenceLine y={0} stroke="#666" strokeDasharray="3 3" />
                    <Area type="monotone" dataKey="pnl" stroke={gradColor} fill="url(#pnlMiniGrad)" strokeWidth={1.5} dot={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </Paper>
            );
          })()}

          {/* Position Strike Map — lot distribution across strikes */}
          {(() => {
            const ce = session?.ce || {};
            const pe = session?.pe || {};
            const strikeMap = new Map();
            const addStrike = (strike, field, lots) => {
              if (!strike || !lots) return;
              const k = String(strike);
              const row = strikeMap.get(k) || { strike, ceActive: 0, ceFrozen: 0, peActive: 0, peFrozen: 0 };
              row[field] += lots;
              strikeMap.set(k, row);
            };
            addStrike(ce.active_strike, 'ceActive', ce.active_lots);
            addStrike(pe.active_strike, 'peActive', pe.active_lots);
            (ce.frozen_positions || []).forEach(fp => addStrike(fp.strike, 'ceFrozen', fp.lots));
            (pe.frozen_positions || []).forEach(fp => addStrike(fp.strike, 'peFrozen', fp.lots));
            const mapData = Array.from(strikeMap.values()).sort((a, b) => a.strike - b.strike);
            if (mapData.length === 0) return null;
            return (
              <Paper elevation={0} sx={{ p: 2, mt: 2, borderRadius: 2, border: '1px solid rgba(255,255,255,0.12)' }}>
                <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700 }}>
                  🗺️ Position Strike Map
                </Typography>
                <ResponsiveContainer width="100%" height={Math.max(80, mapData.length * 36 + 30)}>
                  <BarChart data={mapData} layout="vertical" barGap={0} barCategoryGap={6}>
                    <XAxis type="number" tick={{ fontSize: 10 }} />
                    <YAxis dataKey="strike" type="category" width={60} tick={{ fontSize: 10 }} tickFormatter={v => Number(v).toLocaleString()} />
                    <RechartsTooltip
                      contentStyle={{ backgroundColor: '#1e1e1e', border: '1px solid #333', fontSize: 11 }}
                      formatter={(v, name) => [v, name]}
                    />
                    <Bar dataKey="ceActive" name="CE Active" fill="#4caf50" stackId="ce" />
                    <Bar dataKey="ceFrozen" name="CE Frozen" fill="rgba(76,175,80,0.35)" stackId="ce" />
                    <Bar dataKey="peActive" name="PE Active" fill="#f44336" stackId="pe" />
                    <Bar dataKey="peFrozen" name="PE Frozen" fill="rgba(244,67,54,0.35)" stackId="pe" />
                  </BarChart>
                </ResponsiveContainer>
              </Paper>
            );
          })()}
        </Box>
      )}

      {/* Tab 1: Positions */}
      {detailTab === 1 && (
        <Box>
          {/* Reduce / Inject buttons — only shown when session is active */}
          {['RUNNING', 'PAUSED', 'BOTH_SIDES_UP'].includes(status) && (
            <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end', mb: 1.5 }}>
              <Button
                variant="outlined"
                color="warning"
                size="small"
                startIcon={<ContentCutIcon />}
                onClick={() => setReduceOpen(true)}
                sx={{ fontWeight: 700, borderRadius: 2 }}
              >
                Reduce Position
              </Button>
              {['RUNNING', 'PAUSED'].includes(status) && (
                <Button
                  variant="outlined"
                  color="info"
                  size="small"
                  startIcon={<AddIcon />}
                  onClick={() => setInjectOpen(true)}
                  sx={{ fontWeight: 700, borderRadius: 2 }}
                >
                  Inject Position
                </Button>
              )}
            </Box>
          )}
          <MMMPositionsTable
            session={session}
            heartbeat={heartbeat}
            onSetActiveStrike={handleSetActiveStrike}
            onCloseStrike={handleCloseStrikeRequest}
          />
          <MMMReduceModal
            open={reduceOpen}
            session={session}
            onClose={() => setReduceOpen(false)}
          />
          <MMMInjectModal
            open={injectOpen}
            session={session}
            onClose={() => setInjectOpen(false)}
          />

          {/* Close-Strike Confirmation Dialog */}
          <Dialog
            open={closeStrikeDlg.open}
            onClose={() => !closeStrikeDlg.loading && setCloseStrikeDlg(d => ({ ...d, open: false }))}
            maxWidth="xs"
            fullWidth
          >
            <DialogTitle sx={{ fontWeight: 700, color: '#ef5350' }}>
              🔴 Close Strike — Place Buyback Order
            </DialogTitle>
            <DialogContent>
              <Box sx={{ pt: 1 }}>
                <Typography sx={{ mb: 2 }}>
                  Buy back <strong>{closeStrikeDlg.lots} lot{closeStrikeDlg.lots !== 1 ? 's' : ''}</strong> of{' '}
                  <strong>{closeStrikeDlg.side?.toUpperCase()}</strong> @{' '}
                  <strong>{Number(closeStrikeDlg.strike).toLocaleString()}</strong>
                </Typography>
                {closeStrikeDlg.currentPremium != null && closeStrikeDlg.currentPremium > 0 && (
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                    Current premium: ~${Number(closeStrikeDlg.currentPremium).toFixed(2)}
                    {' '}· Est. cost: ~${(closeStrikeDlg.currentPremium * closeStrikeDlg.lots * 0.001).toFixed(4)} BTC
                  </Typography>
                )}
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1, fontStyle: 'italic' }}>
                  This places a live buyback order on the exchange. The position will be removed
                  from the algo ledger after fill. You can then inject a new position at a safer strike.
                </Typography>
                {closeStrikeDlg.error && (
                  <Typography color="error" variant="body2" sx={{ mt: 1 }}>
                    {closeStrikeDlg.error}
                  </Typography>
                )}
              </Box>
            </DialogContent>
            <DialogActions sx={{ px: 3, pb: 2 }}>
              <Button
                onClick={() => setCloseStrikeDlg(d => ({ ...d, open: false }))}
                disabled={closeStrikeDlg.loading}
              >
                Cancel
              </Button>
              <Button
                variant="contained"
                color="error"
                onClick={handleCloseStrikeConfirm}
                disabled={closeStrikeDlg.loading}
                startIcon={closeStrikeDlg.loading ? <CircularProgress size={16} color="inherit" /> : null}
              >
                {closeStrikeDlg.loading
                  ? 'Placing order...'
                  : `Close ${closeStrikeDlg.lots} lot${closeStrikeDlg.lots !== 1 ? 's' : ''} @ ${Number(closeStrikeDlg.strike).toLocaleString()}`
                }
              </Button>
            </DialogActions>
          </Dialog>
        </Box>
      )}

      {/* Tab 2: Triggers */}
      {detailTab === 2 && (
        <MMMTriggerGauge
          session={session}
          heartbeat={heartbeat}
          triggerData={heartbeat}
        />
      )}

      {/* Tab 3: Adjustments */}
      {detailTab === 3 && (
        <MMMAdjustmentLog
          adjustments={wsData.adjustments}
          reversals={wsData.reversals}
          shifts={wsData.shifts}
          closeEvents={wsData.closeEvents}
          session={session}
        />
      )}

      {/* Tab 4: P&L Chart */}
      {detailTab === 4 && (
        <MMMPnLChart session={session} pnlData={wsData.pnl} />
      )}

      {/* Tab 5: Safety */}
      {detailTab === 5 && (
        <MMMSafetyPanel
          session={session}
          safetyEvents={wsData.safetyEvents}
          minutesToExpiry={heartbeat?.minutes_to_expiry}
        />
      )}

      {/* Tab 6: Strike Map */}
      {detailTab === 6 && (
        <MMMStrikeMap
          session={session}
          spotPrice={heartbeat?.spot_price}
        />
      )}

      {/* Tab 7: Algo Calculations */}
      {detailTab === 7 && (
        <MMMAlgoCalculations
          session={session}
          wsData={wsData}
        />
      )}

      {/* Tab 8: Consolidated Positions */}
      {detailTab === 8 && (
        <MMMConsolidatedPositions session={session} heartbeat={heartbeat} />
      )}

      {/* Tab 9: Greeks & IV */}
      {detailTab === 9 && (
        <MMMGreeksPanel session={session} />
      )}

      {/* Tab 10: Institutional Analytics */}
      {detailTab === 10 && (
        <MMMInstitutionalAnalytics />
      )}

      {/* Tab 11: Margin — Exchange-level margin & risk dashboard */}
      {detailTab === 11 && (
        <MMMMarginGuardianPanel
          session={session}
          sessionId={session?.session_id || session?.id}
        />
      )}

      {/* Tab 12: Regime — Pre-adjustment risk controls */}
      {detailTab === 12 && (
        <MMMRegimePanel
          session={session}
          regimeData={wsData.regimeData}
          heartbeat={heartbeat}
        />
      )}

      {/* Tab 13: Perp Hedge — Perpetual futures delta hedge */}
      {detailTab === 13 && (
        <MMMPerpHedgePanel
          session={session}
          heartbeat={heartbeat}
          perpHedgeEvents={wsData.perpHedgeEvents || []}
          perpHedgeFlip={wsData.perpHedgeFlip}
        />
      )}

      {/* Tab 14: Risk — Breakeven + Gamma visual landscape */}
      {detailTab === 14 && (
        <Box>
          {/* Row 1: 2-column — Combined Zone (spatial WHERE) + Health Radar (dimensional HOW HEALTHY) */}
          <Grid container spacing={2} sx={{ mb: 2 }}>
            <Grid item xs={12} md={6}>
              <MMMCombinedZoneWidget
                breakeven={heartbeat?.breakeven || session._breakeven_result}
                gamma={heartbeat?.gamma || session._gamma_result}
                computedBreakeven={pnlCurveData?.computed_breakeven}
                spotPrice={pnlCurveData?.spot_price}
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <MMMHealthRadar
                breakeven={heartbeat?.breakeven || session._breakeven_result}
                gamma={heartbeat?.gamma || session._gamma_result}
                margin={heartbeat?.margin || session._last_margin_snapshot}
                regime={heartbeat?.regime || (session._regime_action != null ? {
                  regime_action: session._regime_action,
                  vol_regime: session._vol_regime || 'NORMAL',
                  gamma_regime: session._gamma_regime || 'NORMAL',
                  trend_regime: session._trend_regime || 'NORMAL',
                  trend_tier: session._trend_tier || 0,
                } : null)}
              />
            </Grid>
          </Grid>

          {/* Row 2: P&L Landscape Chart — on-demand fetch */}
          <Paper elevation={0} sx={{ p: 1.5, mb: 2, borderRadius: 1.5, border: '1px solid rgba(255,255,255,0.1)' }}>
            <MMMRiskProfileChart
              sessionId={session.session_id}
              isActive={detailTab === 14}
              breakeven={heartbeat?.breakeven || session._breakeven_result}
              onCurveLoaded={setPnlCurveData}
            />
          </Paper>

          {/* Row 3: Distance History Timeline */}
          <MMMDistanceHistoryChart
            heartbeatHistory={heartbeatHistory}
            beWarnPct={session.params?.breakeven_warning_pct}
            gammaWarnPct={session.params?.gamma_warning_distance_pct}
          />

          {/* Row 4: Detailed compact panels (always-visible summary) */}
          <MMMBreakevenPanel
            breakeven={heartbeat?.breakeven || session._breakeven_result}
            gamma={heartbeat?.gamma || session._gamma_result}
          />
          <MMMGammaPanel
            gamma={heartbeat?.gamma || session._gamma_result}
          />
        </Box>
      )}

      {/* Tab 15: Performance Intelligence */}
      {detailTab === 15 && (
        <Box>
          <MMMPerformancePanel sessionId={session?.session_id} />
        </Box>
      )}

      {/* Tab 16: Trade Audit */}
      {detailTab === 16 && (
        <Box>
          <MMMTradeAuditPanel sessionId={session?.session_id} />
        </Box>
      )}

      {/* Tab 17: Execution Event Log */}
      {detailTab === 17 && (
        <Box>
          <MMMExecutionLogPanel sessionId={session?.session_id} />
        </Box>
      )}

      {/* Tab 18: Reverse Mode — Controlled premium harvesting overlay */}
      {detailTab === 18 && (
        <Box>
          <MMMReverseModePanel session={session} heartbeat={heartbeat} />
        </Box>
      )}

      {/* Adjust-Lots Dialog — mounted outside all tab blocks so it works from any tab */}
      <Dialog
        open={adjustLotsDlg.open}
        onClose={() => !adjustLotsDlg.loading && setAdjustLotsDlg(d => ({ ...d, open: false }))}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 700, color: adjustLotsDlg.direction === 'add' ? '#4caf50' : '#ef5350' }}>
          {adjustLotsDlg.direction === 'add' ? '➕' : '➖'}{' '}
          {adjustLotsDlg.direction === 'add' ? 'Add' : 'Remove'} Lots —{' '}
          {adjustLotsDlg.side?.toUpperCase()} Side
        </DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Active strike: <strong>{Number(adjustLotsDlg.activeStrike || 0).toLocaleString()}</strong>
              {' · '}Current active: <strong>{adjustLotsDlg.activeLots} lot{adjustLotsDlg.activeLots !== 1 ? 's' : ''}</strong>
            </Typography>
            <Typography variant="body2" sx={{ mb: 2 }}>
              {adjustLotsDlg.direction === 'add'
                ? 'A SELL order will be placed at the active strike and registered in the ledger.'
                : 'A BUY order will be placed at the active strike to partially close the position.'}
            </Typography>
            <TextField
              label="Lots"
              type="number"
              size="small"
              fullWidth
              value={adjustLotsDlg.qty}
              onChange={e => {
                const v = Math.max(1, parseInt(e.target.value, 10) || 1);
                const max = adjustLotsDlg.direction === 'remove' ? adjustLotsDlg.activeLots : 999;
                setAdjustLotsDlg(d => ({ ...d, qty: Math.min(v, max) }));
              }}
              inputProps={{ min: 1, max: adjustLotsDlg.direction === 'remove' ? adjustLotsDlg.activeLots : 999 }}
              sx={{ mb: 1 }}
            />
            {adjustLotsDlg.error && (
              <Typography color="error" variant="body2" sx={{ mt: 1 }}>
                {adjustLotsDlg.error}
              </Typography>
            )}
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button
            onClick={() => setAdjustLotsDlg(d => ({ ...d, open: false }))}
            disabled={adjustLotsDlg.loading}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            color={adjustLotsDlg.direction === 'add' ? 'success' : 'error'}
            onClick={handleAdjustLotsConfirm}
            disabled={adjustLotsDlg.loading || adjustLotsDlg.qty < 1}
            startIcon={adjustLotsDlg.loading ? <CircularProgress size={16} color="inherit" /> : null}
          >
            {adjustLotsDlg.loading
              ? 'Placing order...'
              : `${adjustLotsDlg.direction === 'add' ? 'Add' : 'Remove'} ${adjustLotsDlg.qty} lot${adjustLotsDlg.qty !== 1 ? 's' : ''}`
            }
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={activeStrikeSnack.open}
        autoHideDuration={4000}
        onClose={() => setActiveStrikeSnack(s => ({ ...s, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity={activeStrikeSnack.severity} onClose={() => setActiveStrikeSnack(s => ({ ...s, open: false }))}>
          {activeStrikeSnack.message}
        </Alert>
      </Snackbar>

      {/* ── Dangerous Mode CONFIRM dialog ── */}
      <Dialog
        open={dangerDlg.open}
        onClose={() => !dangerDlg.loading && setDangerDlg(d => ({ ...d, open: false, confirmText: '' }))}
        maxWidth="sm"
        fullWidth
        PaperProps={{ sx: { border: '2px solid #f44336', backgroundColor: '#1a0000' } }}
      >
        <DialogTitle sx={{ fontWeight: 800, color: '#f44336', display: 'flex', alignItems: 'center', gap: 1 }}>
          <DangerIcon sx={{ color: '#f44336' }} />
          ⚠️ Enable Dangerous Mode
        </DialogTitle>
        <DialogContent>
          <Alert severity="error" icon={false} sx={{ mb: 2, backgroundColor: 'rgba(183,28,28,0.25)', border: '1px solid #f44336' }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
              ALL SAFETY GATES WILL BE DISABLED
            </Typography>
            <Typography variant="body2" sx={{ mb: 0.5 }}>
              The following protections will be bypassed:
            </Typography>
            <Box component="ul" sx={{ m: 0, pl: 2 }}>
              {[
                'Reversal cooldown',
                'Whipsaw protection',
                'Consecutive direction block',
                'Strike shift cooldown',
                'Regime blocks (BLOCK_ALL, FORCE_REDUCE, PAUSE)',
                'Margin YELLOW sell-block',
                'Asymmetry 7:1 block',
                'FM1 reversal circuit breaker',
              ].map(item => (
                <Typography key={item} component="li" variant="body2" sx={{ color: '#ef9a9a', mb: 0.25 }}>
                  {item}
                </Typography>
              ))}
            </Box>
          </Alert>
          <Alert severity="info" icon={false} sx={{ mb: 2, backgroundColor: 'rgba(0,50,80,0.4)' }}>
            <Typography variant="body2">
              <strong>Still active:</strong> Max loss hard stop · ITM guard · Auto-close near expiry · Margin ORANGE wind-down
            </Typography>
          </Alert>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            This mode is intended for use during <strong>0DTE expiry</strong> when the operator is actively monitoring
            and fast algo response is required. You are fully responsible for risk management while this is ON.
          </Typography>
          <Typography variant="body2" sx={{ mb: 1, fontWeight: 600 }}>
            Type <strong style={{ color: '#f44336' }}>CONFIRM</strong> to enable:
          </Typography>
          <TextField
            fullWidth
            size="small"
            placeholder="Type CONFIRM"
            value={dangerDlg.confirmText}
            onChange={e => setDangerDlg(d => ({ ...d, confirmText: e.target.value }))}
            onKeyDown={e => e.key === 'Enter' && dangerDlg.confirmText === 'CONFIRM' && handleDangerConfirm()}
            disabled={dangerDlg.loading}
            sx={{
              '& .MuiOutlinedInput-root': {
                borderColor: dangerDlg.confirmText === 'CONFIRM' ? '#f44336' : undefined,
              },
            }}
            autoFocus
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button
            onClick={() => setDangerDlg(d => ({ ...d, open: false, confirmText: '' }))}
            disabled={dangerDlg.loading}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={handleDangerConfirm}
            disabled={dangerDlg.confirmText !== 'CONFIRM' || dangerDlg.loading}
            startIcon={dangerDlg.loading ? <CircularProgress size={16} color="inherit" /> : <DangerIcon />}
            sx={{ fontWeight: 700 }}
          >
            {dangerDlg.loading ? 'Enabling...' : 'Enable Dangerous Mode'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

/**
 * Small label-value row
 */
const DetailRow = ({ label, value, valueColor }) => (
  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
    <Typography variant="caption" color="text.secondary">
      {label}
    </Typography>
    <Typography
      variant="caption"
      sx={{ fontWeight: 600, fontFamily: 'monospace', color: valueColor || 'text.primary' }}
    >
      {value}
    </Typography>
  </Box>
);

// =============================================================================
// Main Dashboard
// =============================================================================

const MMMDashboard = () => {
  const {
    sessions,
    selectedSessionId,
    loading,
    error,
    healthStatus,
    connectionStatus,
    lastUpdate,
    paramsInfo,
    bothSidesAlert,
    fetchSessions,
    selectSession,
    clearError,
    clearBothSidesAlert,
    socket,
  } = useMMM();

  // WebSocket hook for live data — uses shared socket (no duplicate connection)
  const wsData = useMMMWebSocket(selectedSessionId, socket);

  const [tabValue, setTabValue] = useState(0);
  const [createOpen, setCreateOpen] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const [adoptModeForSession, setAdoptModeForSession] = useState(null);  // session_id that needs adopt mode

  // Settings dialog state
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsSessionId, setSettingsSessionId] = useState(null);

  // Full session object for detail view
  const [fullSession, setFullSession] = useState(null);
  const [fetchError, setFetchError] = useState(null);  // H-15 fix

  // Live price subscription: subscribe CE/PE active strikes to options_ticker_update.
  // Must be declared AFTER fullSession useState — deps array is evaluated immediately.
  useEffect(() => {
    if (!socket || !fullSession) return;
    const ce = fullSession.ce || {};
    const pe = fullSession.pe || {};
    const expiry = fullSession.params?.expiry;
    const ceStrike = ce.active_strike;
    const peStrike = pe.active_strike;
    if (!expiry || (!ceStrike && !peStrike)) return;

    const symbols = [];
    if (ceStrike) symbols.push(`C-BTC-${Math.round(ceStrike)}-${expiry}`);
    if (peStrike) symbols.push(`P-BTC-${Math.round(peStrike)}-${expiry}`);

    if (socket.connected) {
      socket.emit('subscribe_options_tickers', { symbols });
    }
    const onConnect = () => socket.emit('subscribe_options_tickers', { symbols });
    socket.on('connect', onConnect);

    return () => {
      socket.off('connect', onConnect);
      if (socket.connected) {
        socket.emit('unsubscribe_options_tickers', { symbols });
      }
    };
  }, [socket, fullSession?.session_id, fullSession?.ce?.active_strike, fullSession?.pe?.active_strike, fullSession?.params?.expiry]); // eslint-disable-line react-hooks/exhaustive-deps

  // When selectedSessionId changes, fetch full session
  const selectedSession = useMemo(
    () => sessions.find((s) => s.session_id === selectedSessionId),
    [sessions, selectedSessionId]
  );

  // Fetch full session details when selected
  const fetchFullSession = useCallback(async () => {
    if (!selectedSessionId) return;
    try {
      const result = await mmmService.getSession(selectedSessionId);
      if (result.success) {
        setFullSession(result.session);
        setFetchError(null);  // H-15: clear error on success
      }
    } catch (err) {
      // If 404, the session was deleted — clear selection & localStorage
      if (err.status === 404 || err?.details?.error?.includes('not found')) {
        setFullSession(null);
        setFetchError(null);
        selectSession(null);
        localStorage.removeItem('mmm_selectedSessionId');
        return;
      }
      // H-15 fix: Surface non-404 errors to user
      setFetchError(err.message || 'Failed to fetch session data');
      console.error('Failed to fetch full session:', err);
    }
  }, [selectedSessionId, selectSession]);

  // On session switch: clear stale data immediately, then fetch new session
  useEffect(() => {
    setFullSession(null);
    if (selectedSessionId) fetchFullSession();
  }, [selectedSessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Poll full session details — pauses when tab is hidden
  useVisibilityAwarePolling(fetchFullSession, 15000, 60000, !!selectedSessionId);

  // Refresh full session immediately when backend promotes active strike
  // (auto-promotion at Step 0.75 or manual set-active-strike via API)
  useEffect(() => {
    if (!socket || !selectedSessionId) return;
    const handler = (data) => {
      if (data?.session_id === selectedSessionId) fetchFullSession();
    };
    socket.on('mmm_active_strike_changed', handler);
    return () => socket.off('mmm_active_strike_changed', handler);
  }, [socket, selectedSessionId, fetchFullSession]);

  // Exit All WebSocket events — refresh sessions + show alerts
  useEffect(() => {
    if (!socket) return;
    const onProgress = (data) => {
      if (data?.session_id === selectedSessionId) {
        fetchFullSession();
      }
    };
    const onCompleted = (data) => {
      fetchSessions(false);
      if (data?.session_id === selectedSessionId) {
        fetchFullSession();
        setSnackbar({ open: true, message: 'Exit All complete — all positions closed.', severity: 'success' });
      }
    };
    const onPartial = (data) => {
      fetchSessions(false);
      if (data?.session_id === selectedSessionId) {
        fetchFullSession();
        const failed = data?.failed_positions || [];
        setSnackbar({
          open: true,
          message: `Exit partial: ${failed.length} position(s) may still be open — close manually on exchange.`,
          severity: 'warning',
        });
      }
    };
    socket.on('mmm_exit_progress', onProgress);
    socket.on('mmm_exit_completed', onCompleted);
    socket.on('mmm_exit_partial', onPartial);
    return () => {
      socket.off('mmm_exit_progress', onProgress);
      socket.off('mmm_exit_completed', onCompleted);
      socket.off('mmm_exit_partial', onPartial);
    };
  }, [socket, selectedSessionId, fetchFullSession, fetchSessions]);

  // Session control handler
  const handleControl = useCallback(async (action, sessionId) => {
    try {
      let result;
      switch (action) {
        case 'start': {
          // Guard: prevent starting a session that is not IDLE
          const sess = sessions.find(s => s.session_id === sessionId);
          const currentStatus = sess?.status || sess?.strategy_status;
          if (currentStatus && currentStatus !== 'IDLE') {
            setSnackbar({ open: true, message: `Session is already ${currentStatus}`, severity: 'info' });
            return;
          }
          result = await mmmService.startSession(sessionId);
          break;
        }
        case 'pause':
          result = await mmmService.pauseSession(sessionId);
          break;
        case 'resume':
          result = await mmmService.resumeSession(sessionId);
          break;
        case 'stop':
          result = await mmmService.stopSession(sessionId);
          break;
        case 'force_heartbeat':
          result = await mmmService.forceHeartbeat(sessionId);
          break;
        case 'exit_all': {
          // Build position summary for confirmation dialog
          const sess = sessions.find(s => s.session_id === sessionId);
          const ceLots = (sess?.ce_active_lots || 0) + (sess?.ce_frozen_lots || 0);
          const peLots = (sess?.pe_active_lots || 0) + (sess?.pe_frozen_lots || 0);
          const confirmed = window.confirm(
            `Exit Strategy — Close ALL Positions\n\n` +
            `This will close ALL open options positions:\n` +
            `  CE: ${ceLots} lots\n` +
            `  PE: ${peLots} lots\n\n` +
            `The session will stop after all positions are closed.\n\n` +
            `This cannot be undone. Confirm?`
          );
          if (!confirmed) return;
          result = await mmmService.exitAllSession(sessionId);
          break;
        }
        case 'delete':
          result = await mmmService.deleteSession(sessionId);
          if (result.success && sessionId === selectedSessionId) {
            // Auto-select first remaining active session, or clear selection
            const remaining = sessions.filter(s => s.session_id !== sessionId);
            const nextActive = remaining.find(s => ['RUNNING', 'PAUSED', 'BOTH_SIDES_UP'].includes(s.status || s.strategy_status));
            selectSession(nextActive ? nextActive.session_id : (remaining[0]?.session_id || null));
          }
          break;
        case 'settings':
          // Open settings dialog
          setSettingsSessionId(sessionId);
          setSettingsOpen(true);
          return;
        case 'retry_leg':
          result = await mmmService.retryPartialLeg(sessionId);
          break;
        case 'resolve_partial': {
          // Prompt user for both fill prices
          const ceFillStr = window.prompt('Enter CE fill price (actual fill from exchange):');
          if (!ceFillStr) return;
          const peFillStr = window.prompt('Enter PE fill price (actual fill from exchange):');
          if (!peFillStr) return;
          const ceFill = parseFloat(ceFillStr);
          const peFill = parseFloat(peFillStr);
          if (isNaN(ceFill) || isNaN(peFill) || ceFill <= 0 || peFill <= 0) {
            setSnackbar({ open: true, message: 'Invalid fill prices — must be positive numbers', severity: 'error' });
            return;
          }
          result = await mmmService.resolvePartialEntry(sessionId, ceFill, peFill);
          break;
        }
        default:
          return;

      }

      if (result.success) {
        setSnackbar({
          open: true,
          message: result.message || `Session ${action}ed successfully`,
          severity: 'success',
        });
        fetchSessions(false);
      } else {
        setSnackbar({
          open: true,
          message: result.error || `Failed to ${action} session`,
          severity: 'error',
        });
      }
    } catch (err) {
      setSnackbar({
        open: true,
        message: err.details?.error || err.message,
        severity: 'error',
      });
    }
  }, [fetchSessions]);

  // Both-sides decision handler — works from both the popup dialog AND the inline status banner
  const handleBothSidesDecision = useCallback(async (decision, params = {}) => {
    const alertSessionId = bothSidesAlert?.session_id
      || wsData.bothSidesAlert?.session_id;
    // M-32 fix: Don't fall back to selectedSessionId — could be wrong session
    if (!alertSessionId) {
      setSnackbar({ open: true, message: 'No active alert to respond to', severity: 'error' });
      return;
    }

    try {
      const result = await mmmService.submitBothSidesDecision(alertSessionId, decision, params);
      if (result.success) {
        const labels = {
          adjust_ce: 'Hedging CE → selling PE',
          adjust_pe: 'Hedging PE → selling CE',
          skip: 'Resumed with updated triggers',
        };
        setSnackbar({ open: true, message: labels[decision] || `Decision: ${decision}`, severity: 'success' });
        clearBothSidesAlert();
        wsData.clearBothSidesAlert?.();
        fetchSessions(false);
      } else if (result.stale) {
        // Session already transitioned — dismiss the stale alert silently
        clearBothSidesAlert();
        wsData.clearBothSidesAlert?.();
        fetchSessions(false);
      }
    } catch (err) {
      setSnackbar({ open: true, message: err.details?.error || err.message, severity: 'error' });
    }
  }, [bothSidesAlert, wsData, clearBothSidesAlert, fetchSessions, selectedSessionId]);

  // Session created handler
  const handleSessionCreated = useCallback((session) => {
    setSnackbar({ open: true, message: `Session ${session.session_id} created`, severity: 'success' });
    fetchSessions(false);
    selectSession(session.session_id);
    // If created in adopt mode, tell ConfigPanel
    if (session._adoptMode) {
      setAdoptModeForSession(session.session_id);
    }
  }, [fetchSessions, selectSession]);

  // Categorize sessions
  const activeSessions = useMemo(
    () => sessions.filter((s) => ['RUNNING', 'PAUSED', 'BOTH_SIDES_UP', 'STARTING', 'PARTIAL_ENTRY', 'EXITING'].includes(s.status)),
    [sessions]
  );
  const idleSessions = useMemo(
    () => sessions.filter((s) => s.status === 'IDLE'),
    [sessions]
  );
  const stoppedSessions = useMemo(
    () => sessions.filter((s) => s.status === 'STOPPED'),
    [sessions]
  );

  // =========================================================================
  // Render
  // =========================================================================

  return (
    <Box sx={{ p: 2, height: '100%' }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="h5" sx={{ fontWeight: 700 }}>
            💰 MMM — Money Mind &amp; Method
          </Typography>
          <Chip
            label="BTC Options"
            size="small"
            variant="outlined"
            color="primary"
          />
          {healthStatus && (
            <Tooltip title={`Backend: ${healthStatus}`}>
              {healthStatus === 'healthy' ? (
                <HealthyIcon sx={{ color: '#4caf50', fontSize: 20 }} />
              ) : (
                <ErrorIcon sx={{ color: '#f44336', fontSize: 20 }} />
              )}
            </Tooltip>
          )}
          {connectionStatus !== 'connected' && (
            <Chip
              label={connectionStatus === 'reconnecting' ? 'Reconnecting...' : 'Disconnected'}
              size="small"
              color={connectionStatus === 'reconnecting' ? 'warning' : 'error'}
            />
          )}
        </Box>

        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="contained"
            size="small"
            startIcon={<AddIcon />}
            onClick={() => setCreateOpen(true)}
          >
            New Session
          </Button>
          <Tooltip title="Refresh">
            <IconButton onClick={() => fetchSessions(false)} size="small">
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Error banner */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={clearError}>
          {error}
        </Alert>
      )}

      {/* M-35 fix: Prominent WebSocket disconnected warning */}
      {connectionStatus !== 'connected' && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          WebSocket disconnected — position data may be stale.
          {connectionStatus === 'reconnecting' ? ' Reconnecting...' : ''}
        </Alert>
      )}

      {/* Loading state */}
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', py: 8 }}>
          <CircularProgress />
          <Typography sx={{ ml: 2 }}>Loading MMM sessions...</Typography>
        </Box>
      ) : (
        <Grid container spacing={2} sx={{ height: 'calc(100% - 80px)' }}>
          {/* Left panel: session list */}
          <Grid item xs={12} md={4} lg={3}>
            <Paper sx={{ p: 1.5, height: '100%', overflow: 'auto' }}>
              {/* Aggregate PnL across all sessions */}
              <AggregatePnLWidget />

              {/* Multi-session comparison — shows when 2+ active sessions */}
              {activeSessions.length >= 2 && (
                <Paper elevation={0} sx={{ p: 1, mb: 1, borderRadius: 1, border: '1px solid rgba(255,255,255,0.08)', backgroundColor: 'rgba(255,255,255,0.02)' }}>
                  <Typography variant="caption" sx={{ fontWeight: 700, display: 'block', mb: 0.5, color: 'text.secondary', fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                    📊 Session Comparison
                  </Typography>
                  <Box sx={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.65rem', fontFamily: 'monospace' }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.12)' }}>
                          <th style={{ textAlign: 'left', padding: '2px 4px', color: '#999', fontWeight: 600 }}>Session</th>
                          <th style={{ textAlign: 'right', padding: '2px 4px', color: '#999', fontWeight: 600 }}>CE/PE</th>
                          <th style={{ textAlign: 'right', padding: '2px 4px', color: '#999', fontWeight: 600 }}>P&L</th>
                          <th style={{ textAlign: 'right', padding: '2px 4px', color: '#999', fontWeight: 600 }}>Adj</th>
                        </tr>
                      </thead>
                      <tbody>
                        {activeSessions.map(s => (
                          <tr key={s.session_id}
                            style={{
                              borderBottom: '1px solid rgba(255,255,255,0.05)',
                              backgroundColor: s.session_id === selectedSessionId ? 'rgba(33,150,243,0.08)' : 'transparent',
                              cursor: 'pointer',
                            }}
                            onClick={() => selectSession(s.session_id)}
                          >
                            <td style={{ padding: '3px 4px', whiteSpace: 'nowrap', maxWidth: 70, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                              {s.session_id.length > 10 ? s.session_id.slice(-8) : s.session_id}
                            </td>
                            <td style={{ textAlign: 'right', padding: '3px 4px', color: '#90caf9' }}>
                              {s.ce_active_lots || 0}/{s.pe_active_lots || 0}
                            </td>
                            <td style={{
                              textAlign: 'right', padding: '3px 4px',
                              color: (s.net_pnl || 0) >= 0 ? '#4caf50' : '#f44336',
                              fontWeight: 600,
                            }}>
                              ${(s.net_pnl || 0).toFixed(2)}
                            </td>
                            <td style={{ textAlign: 'right', padding: '3px 4px', color: '#b0bec5' }}>{s.adjustment_count || 0}</td>
                          </tr>
                        ))}
                        {/* Totals row */}
                        <tr style={{ borderTop: '1px solid rgba(255,255,255,0.15)' }}>
                          <td style={{ padding: '3px 4px', fontWeight: 700, color: '#fff' }}>Total</td>
                          <td style={{ textAlign: 'right', padding: '3px 4px', fontWeight: 700, color: '#90caf9' }}>
                            {activeSessions.reduce((s, x) => s + (x.ce_active_lots || 0), 0)}/{activeSessions.reduce((s, x) => s + (x.pe_active_lots || 0), 0)}
                          </td>
                          <td style={{
                            textAlign: 'right', padding: '3px 4px', fontWeight: 700,
                            color: activeSessions.reduce((s, x) => s + (x.net_pnl || 0), 0) >= 0 ? '#4caf50' : '#f44336',
                          }}>
                            ${activeSessions.reduce((s, x) => s + (x.net_pnl || 0), 0).toFixed(2)}
                          </td>
                          <td style={{ textAlign: 'right', padding: '3px 4px', fontWeight: 700, color: '#b0bec5' }}>
                            {activeSessions.reduce((s, x) => s + (x.adjustment_count || 0), 0)}
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </Box>
                </Paper>
              )}

              <Tabs
                value={tabValue}
                onChange={(e, v) => setTabValue(v)}
                variant="fullWidth"
                sx={{ mb: 1, minHeight: 36 }}
              >
                <Tab
                  label={`Active (${activeSessions.length})`}
                  sx={{ minHeight: 36, py: 0 }}
                />
                <Tab
                  label={`Idle (${idleSessions.length})`}
                  sx={{ minHeight: 36, py: 0 }}
                />
                <Tab
                  label={`History (${stoppedSessions.length})`}
                  sx={{ minHeight: 36, py: 0 }}
                />
              </Tabs>

              {tabValue === 0 && activeSessions.map((s) => (
                <SessionCard
                  key={s.session_id}
                  session={s}
                  selected={s.session_id === selectedSessionId}
                  onSelect={selectSession}
                  onControl={handleControl}
                  heartbeat={s.session_id === selectedSessionId ? wsData?.heartbeat : null}
                />
              ))}
              {tabValue === 0 && activeSessions.length === 0 && (
                <Typography variant="body2" color="text.secondary" sx={{ p: 2, textAlign: 'center' }}>
                  No active sessions
                </Typography>
              )}

              {tabValue === 1 && idleSessions.map((s) => (
                <SessionCard
                  key={s.session_id}
                  session={s}
                  selected={s.session_id === selectedSessionId}
                  onSelect={selectSession}
                  onControl={handleControl}
                />
              ))}
              {tabValue === 1 && idleSessions.length === 0 && (
                <Typography variant="body2" color="text.secondary" sx={{ p: 2, textAlign: 'center' }}>
                  No idle sessions
                </Typography>
              )}

              {tabValue === 2 && stoppedSessions.map((s) => (
                <SessionCard
                  key={s.session_id}
                  session={s}
                  selected={s.session_id === selectedSessionId}
                  onSelect={selectSession}
                  onControl={handleControl}
                />
              ))}
              {tabValue === 2 && stoppedSessions.length === 0 && (
                <Typography variant="body2" color="text.secondary" sx={{ p: 2, textAlign: 'center' }}>
                  No stopped sessions
                </Typography>
              )}

              {/* Last update */}
              {lastUpdate && (
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: 'block', textAlign: 'center', mt: 1 }}
                >
                  Updated: {new Date(lastUpdate).toLocaleTimeString()}
                </Typography>
              )}
            </Paper>
          </Grid>

          {/* Right panel: session detail + config */}
          <Grid item xs={12} md={8} lg={9}>
            <Box sx={{ height: '100%', overflow: 'auto' }}>
              {/* Phase 2: Config panel for IDLE/STOPPED sessions */}
              {fullSession && ['IDLE', 'STOPPED'].includes((fullSession.strategy_status || fullSession.status || '').toUpperCase()) && (
                <MMMConfigPanel
                  sessionId={selectedSessionId}
                  sessionStatus={fullSession.strategy_status || fullSession.status}
                  sessionExpiry={fullSession.params?.expiry || ''}
                  isStraddle={
                    fullSession.params?._preset_source === 'STRADDLE_WITH_ADJUSTMENT' ||
                    fullSession.params?.dte_category === 'STRADDLE_WITH_ADJUSTMENT'
                  }
                  initialMode={adoptModeForSession === selectedSessionId ? 'adopt' : undefined}
                  onInitialized={() => {
                    setSnackbar({ open: true, message: 'Session initialized!', severity: 'success' });
                    setAdoptModeForSession(null);
                    fetchSessions(false);
                  }}
                />
              )}
              {/* AWAITING_USER_ACTION banner — one leg wiped during active hours */}
              {(() => {
                const _aua = wsData?.heartbeat?.awaiting_user_action || fullSession?._awaiting_user_action;
                const _aud = wsData?.heartbeat?.awaiting_user_action_details || fullSession?._awaiting_user_action_details;
                if (!_aua || !_aud) return null;
                const closedSide = (_aud.closed_side || '').toUpperCase();
                const openSide   = (_aud.open_side   || '').toUpperCase();
                const pnl        = _aud.current_pnl || 0;
                const pnlColor   = pnl >= 0 ? '#a5d6a7' : '#ef9a9a';
                return (
                  <Alert
                    severity="error"
                    variant="filled"
                    icon={false}
                    sx={{ mx: 0, mb: 1, borderRadius: 0, borderBottom: '2px solid #b71c1c' }}
                  >
                    <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                      <Typography sx={{ fontSize: '1.3rem', lineHeight: 1, mt: 0.2 }}>🚨</Typography>
                      <Box sx={{ flex: 1 }}>
                        <Typography sx={{ fontWeight: 700, fontSize: '0.93rem', mb: 0.3 }}>
                          HUMAN ACTION REQUIRED — Session Paused (Active Hours)
                        </Typography>
                        <Typography sx={{ fontSize: '0.82rem', lineHeight: 1.6 }}>
                          <strong>{closedSide}</strong> fully closed (0 lots).{' '}
                          <strong>{openSide}</strong> has{' '}
                          <strong>{_aud.open_lots} lot{_aud.open_lots !== 1 ? 's' : ''}</strong> open — unhedged.
                          {_aud.open_strike ? ` Strike: ${_aud.open_strike}.` : ''}
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 3, mt: 0.4, flexWrap: 'wrap', alignItems: 'center' }}>
                          <Typography sx={{ fontSize: '0.78rem', color: 'rgba(255,255,255,0.85)' }}>
                            P&L:{' '}
                            <strong style={{ color: pnlColor }}>
                              ${pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}
                            </strong>
                          </Typography>
                          {_aud.detected_at_ist && (
                            <Typography sx={{ fontSize: '0.78rem', color: 'rgba(255,255,255,0.75)' }}>
                              Detected: {_aud.detected_at_ist}
                            </Typography>
                          )}
                        </Box>
                        <Typography sx={{ fontSize: '0.78rem', mt: 0.4, color: 'rgba(255,255,255,0.85)' }}>
                          Action: Close <strong>{openSide}</strong> manually, or re-enter{' '}
                          <strong>{closedSide}</strong> at a new strike to restore hedge.
                        </Typography>
                      </Box>
                    </Box>
                  </Alert>
                );
              })()}

              <Paper sx={{ overflow: 'auto' }}>
                {/* H-15 fix: Show fetch error alert when non-404 error occurs */}
                {fetchError && (
                  <Alert severity="warning" sx={{ m: 1 }}>
                    Data may be stale: {fetchError}
                  </Alert>
                )}
                {/* H-13 fix: guard against null fullSession */}
                {fullSession ? (
                  <SessionDetail
                    session={fullSession}
                    wsData={wsData}
                    socket={socket}
                    onBothSidesAction={handleBothSidesDecision}
                    onPartialEntryAction={(action) => handleControl(action, selectedSessionId)}
                    onStrikePromoted={fetchFullSession}
                  />
                ) : (
                  <Box sx={{ p: 4, textAlign: 'center' }}>
                    <Typography variant="body1" color="text.secondary">
                      Select a session to view details
                    </Typography>
                  </Box>
                )}
              </Paper>

              {/* Background Activities Feed */}
              <Box sx={{ mt: 2 }}>
                <MMMActivityFeed sessionId={selectedSessionId} socket={wsData.socket} />
              </Box>

              {/* Session Analytics Summary */}
              <Box sx={{ mt: 2 }}>
                <MMMAnalyticsSummary sessionId={selectedSessionId} />
              </Box>
            </Box>
          </Grid>
        </Grid>
      )}

      {/* Dialogs */}
      <CreateSessionDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={handleSessionCreated}
        paramsInfo={paramsInfo}
      />

      <MMMBothSidesAlert
        open={!!(bothSidesAlert || wsData.bothSidesAlert)}
        alertData={bothSidesAlert || wsData.bothSidesAlert}
        sessionId={bothSidesAlert?.session_id || wsData.bothSidesAlert?.session_id}
        onAction={handleBothSidesDecision}
        onClose={() => { clearBothSidesAlert(); wsData.clearBothSidesAlert?.(); }}
      />

      {/* Settings Dialog */}
      <MMMSettingsDialog
        open={settingsOpen}
        sessionId={settingsSessionId}
        paramsInfo={paramsInfo}
        onClose={(success) => {
          setSettingsOpen(false);
          setSettingsSessionId(null);
          if (success) {
            setSnackbar({ open: true, message: 'Settings updated successfully', severity: 'success' });
            fetchSessions(false);
          }
        }}
      />

      {/* Snackbar */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar((prev) => ({ ...prev, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert
          severity={snackbar.severity}
          onClose={() => setSnackbar((prev) => ({ ...prev, open: false }))}
          variant="filled"
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default MMMDashboard;
