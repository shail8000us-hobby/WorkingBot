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
} from '@mui/material';
import ContentCutIcon from '@mui/icons-material/ContentCut';
import {
  Refresh as RefreshIcon,
  PlayArrow as PlayIcon,
  Pause as PauseIcon,
  Stop as StopIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  Settings as SettingsIcon,
  TrendingUp as TrendingUpIcon,
  CheckCircle as HealthyIcon,
  Error as ErrorIcon,
  Circle as CircleIcon,
  Bolt as BoltIcon,
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
import MMMSafetyPanel from './MMMSafetyPanel';
import MMMMarginGuardianPanel from './MMMMarginGuardianPanel';
import MMMRegimePanel from './MMMRegimePanel';
import MMMPerpHedgePanel from './MMMPerpHedgePanel';
import MMMActivityFeed from './MMMActivityFeed';
import MMMSettingsDialog from './MMMSettingsDialog';
import MMMConsolidatedPositions from './MMMConsolidatedPositions';
import MMMGreeksPanel from './MMMGreeksPanel';
import MMMAnalyticsSummary from './MMMAnalyticsSummary';
import MMMInstitutionalAnalytics from '../MMMInstitutionalAnalytics';
import { HelpTooltip, SectionBlurb, StrategyExplainer } from './MMMEducation';
import useVisibilityAwarePolling from '../../hooks/useVisibilityAwarePolling';

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
 * Session card condensed view
 */
const SessionCard = ({ session, selected, onSelect, onControl }) => {
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
        transition: 'all 0.2s',
        '&:hover': { backgroundColor: cfg.bg },
      }}
    >
      <CardContent sx={{ py: 1.5, px: 2, '&:last-child': { pb: 1.5 } }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
          <Typography variant="subtitle2" sx={{ fontFamily: 'monospace' }}>
            {session.session_id}
          </Typography>
          <StatusChip status={status} />
        </Box>

        <Grid container spacing={1} sx={{ mt: 0.5 }}>
          <Grid item xs={6}>
            <Typography variant="caption" color="text.secondary">
              CE: {session.ce_active_lots || 0} lots @ {session.ce_strike || '—'}
            </Typography>
          </Grid>
          <Grid item xs={6}>
            <Typography variant="caption" color="text.secondary">
              PE: {session.pe_active_lots || 0} lots @ {session.pe_strike || '—'}
            </Typography>
          </Grid>
        </Grid>

        {session.net_pnl !== undefined && (
          <Typography
            variant="body2"
            sx={{
              mt: 0.5,
              fontWeight: 700,
              color: session.net_pnl >= 0 ? '#4caf50' : '#f44336',
              fontFamily: 'monospace',
            }}
          >
            P&L: ${session.net_pnl?.toFixed(2) || '0.00'}
          </Typography>
        )}

        {/* Time to Expiry (IST) */}
        {expiryInfo && (
          <Typography
            variant="caption"
            sx={{
              mt: 0.5,
              fontWeight: 600,
              color: expiryInfo.countdown === 'EXPIRED' ? '#f44336' : '#ff9800',
              fontFamily: 'monospace',
              display: 'block',
            }}
          >
            Expiry: {expiryInfo.expiryIST} IST &nbsp;|&nbsp; {expiryInfo.countdown}
          </Typography>
        )}

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
  const [params, setParams] = useState({
    desired_ce_premium: 100,
    desired_pe_premium: 100,
    initial_lots: 1,
    expiry: '',
    adjustment_interval: 300,
    close_at_threshold: 5,
    max_lots_per_side: 100,
    max_adjustments: 30,
    max_loss_amount: 50000,
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

  // Fetch expiries and spot price when dialog opens
  React.useEffect(() => {
    if (!open) return;
    let cancelled = false;

    const fetchData = async () => {
      setExpiryLoading(true);
      try {
        const [expResult, spotResult] = await Promise.all([
          mmmService.getExpiries().catch(() => ({ success: false })),
          mmmService.getSpotPrice().catch(() => ({ success: false })),
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
      const config = { mode: backendMode, params };
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

        {/* Mode selection */}
        <FormControl fullWidth sx={{ mb: 3, mt: 1 }}>
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

        {/* Core parameters */}
        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700 }}>Core Parameters</Typography>
        <Grid container spacing={2} sx={{ mb: 3 }}>
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
              inputProps={{ min: 100, step: 1000 }}
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

/**
 * Session detail panel — tabbed live dashboard view
 */
const SessionDetail = ({ session, wsData, onBothSidesAction, onPartialEntryAction }) => {
  const [detailTab, setDetailTab] = useState(0);
  const [reduceOpen, setReduceOpen] = useState(false);

  // M-30 fix: Reset tab when session changes (avoids showing empty P&L tab on fresh session)
  useEffect(() => {
    setDetailTab(0);
  }, [session?.session_id]);

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
  const realized = session.realized_pnl ?? 0;
  const unrealized = session.unrealized_pnl ?? 0;
  const fees = session.total_fees ?? 0;
  const netPnl = realized + unrealized - fees;
  const totalPremium = session.total_premium_collected ?? 0;
  const peakPnl = session.peak_pnl ?? 0;
  // L-11: Compute drawdown from peak for display
  const peakDrawdown = peakPnl - netPnl;

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
            </Box>
            <StatusChip status={status} />
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
                label: 'Total Premium',
                help: 'total_premium',
                value: `$${totalPremium.toFixed(2)}`,
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
                label: 'Duration',
                help: 'session_duration',
                value: sessionDuration || '—',
                color: '#78909c',
                bg: 'rgba(120,144,156,0.08)',
                border: 'rgba(120,144,156,0.3)',
              },
            ].map(({ label, help, value, sub, color, bg, border }) => (
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
                    <Typography variant="caption" sx={{ color: '#ef5350', display: 'block', mt: 0.25, fontSize: '0.7rem' }}>
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
                          const livePremium = key === 'CE' ? ceLivePremium : peLivePremium;
                          const sk = key.toLowerCase();
                          const avgEntry = sideMetrics[sk].avgEntry;
                          const hasLive = livePremium != null && livePremium > 0;
                          // For short sellers: profit when current < entry
                          const pctChange = hasLive && avgEntry > 0
                            ? ((livePremium - avgEntry) / avgEntry * 100)
                            : null;
                          // Green = current dropped (good for shorts), Red = current rose (bad)
                          const premColor = pctChange != null
                            ? (pctChange <= 0 ? '#4caf50' : '#f44336')
                            : 'text.primary';
                          return (
                            <>
                              <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.85rem' }}>Current Premium</Typography>
                              <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 0.5 }}>
                                <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: 'monospace', color: premColor }}>
                                  {hasLive ? `$${livePremium.toFixed(2)}` : '—'}
                                </Typography>
                                {pctChange != null && (
                                  <Typography variant="caption" sx={{ fontFamily: 'monospace', color: premColor, fontSize: '0.75rem' }}>
                                    {pctChange <= 0 ? '▼' : '▲'}{Math.abs(pctChange).toFixed(1)}%
                                  </Typography>
                                )}
                              </Box>
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
            <MMMTriggerGauge
              session={session}
              heartbeat={heartbeat}
              triggerData={heartbeat}
            />
          </Paper>

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
        </Box>
      )}

      {/* Tab 1: Positions */}
      {detailTab === 1 && (
        <Box>
          {/* Reduce Position button — only shown when session is active */}
          {['RUNNING', 'PAUSED', 'BOTH_SIDES_UP'].includes(status) && (
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1.5 }}>
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
            </Box>
          )}
          <MMMPositionsTable session={session} heartbeat={heartbeat} />
          <MMMReduceModal
            open={reduceOpen}
            session={session}
            onClose={() => setReduceOpen(false)}
          />
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

  // Clear full session when no session is selected
  useEffect(() => {
    if (!selectedSessionId) setFullSession(null);
  }, [selectedSessionId]);

  // Poll full session details — pauses when tab is hidden
  useVisibilityAwarePolling(fetchFullSession, 15000, 60000, !!selectedSessionId);

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
    () => sessions.filter((s) => ['RUNNING', 'PAUSED', 'BOTH_SIDES_UP', 'STARTING', 'PARTIAL_ENTRY'].includes(s.status)),
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
            label="BTC 0DTE"
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
                  initialMode={adoptModeForSession === selectedSessionId ? 'adopt' : undefined}
                  onInitialized={() => {
                    setSnackbar({ open: true, message: 'Session initialized!', severity: 'success' });
                    setAdoptModeForSession(null);
                    fetchSessions(false);
                  }}
                />
              )}
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
                    onBothSidesAction={handleBothSidesDecision}
                    onPartialEntryAction={(action) => handleControl(action, selectedSessionId)}
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
