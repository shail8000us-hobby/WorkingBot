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
} from '@mui/material';
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
} from '@mui/icons-material';
import { useMMM } from './MMMContext';
import mmmService from './mmmService';
import MMMConfigPanel from './MMMConfigPanel';
import useMMMWebSocket from './hooks/useMMMWebSocket';
import MMMStatusBanner from './MMMStatusBanner';
import MMMPositionsTable from './MMMPositionsTable';
import MMMTriggerGauge from './MMMTriggerGauge';
import MMMAdjustmentLog from './MMMAdjustmentLog';
import MMMStrikeMap from './MMMStrikeMap';
import MMMAlgoCalculations from './MMMAlgoCalculations';
import MMMPnLChart from './MMMPnLChart';
import MMMBothSidesAlert from './MMMBothSidesAlert';
import MMMSafetyPanel from './MMMSafetyPanel';
import MMMActivityFeed from './MMMActivityFeed';
import MMMSettingsDialog from './MMMSettingsDialog';
import { HelpTooltip, SectionBlurb, StrategyExplainer } from './MMMEducation';

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
    // expiry_time is naive UTC ISO string like '2026-02-17T12:00:00'
    const expMs = new Date(expiryTimeISO + 'Z').getTime();
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

    const totalMin = Math.floor(diffMs / 60000);
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
    setExpiryInfo(computeExpiryInfo(session.expiry_time));
    const timer = setInterval(() => setExpiryInfo(computeExpiryInfo(session.expiry_time)), 30000);
    return () => clearInterval(timer);
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
            <Typography variant="caption" color="error" sx={{ fontWeight: 700 }}>
              ⚠️ One leg filled, other failed! Check activities.
            </Typography>
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
    }

    setCreating(true);
    setError(null);

    try {
      const config = { mode, params };
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

/**
 * Session detail panel — tabbed live dashboard view
 */
const SessionDetail = ({ session, wsData, onBothSidesAction }) => {
  const [detailTab, setDetailTab] = useState(0);

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

  // P&L calculations
  const realized = session.realized_pnl || 0;
  const unrealized = session.unrealized_pnl || 0;
  const fees = session.total_fees || 0;
  const netPnl = realized + unrealized - fees;
  const totalPremium = session.total_premium_collected || 0;
  const peakPnl = session.peak_pnl || 0;

  return (
    <Box sx={{ p: 2 }}>
      {/* Status Banner — ALWAYS shown */}
      <Box sx={{ mb: 2 }}>
        <MMMStatusBanner session={session} heartbeat={wsData.heartbeat} onBothSidesAction={onBothSidesAction} />
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
      </Tabs>

      {/* Tab 0: Overview — Professional KPI Dashboard */}
      {detailTab === 0 && (
        <Box>
          {/* Expandable strategy explainer for new users */}
          <StrategyExplainer />

          {/* Session ID + Status Header */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
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
                color: '#ab47bc',
                bg: 'rgba(171,71,188,0.08)',
                border: 'rgba(171,71,188,0.3)',
              },
              {
                label: 'Fees',
                help: 'fees',
                value: `$${fees.toFixed(2)}`,
                color: '#ff9800',
                bg: 'rgba(255,152,0,0.08)',
                border: 'rgba(255,152,0,0.3)',
              },
            ].map(({ label, help, value, color, bg, border }) => (
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
                      sx={{ color: 'text.secondary', display: 'block', mb: 0.5, fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: 0.5 }}
                    >
                      {label}
                    </Typography>
                  </HelpTooltip>
                  <Typography
                    variant="body1"
                    sx={{ fontWeight: 700, fontFamily: 'monospace', color, fontSize: '1rem' }}
                  >
                    {value}
                  </Typography>
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
                        label={`${data.total_lots || 0} lots`}
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
                        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.78rem' }}>Strike</Typography>
                        <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: 'monospace' }}>
                          {data.active_strike ? data.active_strike.toLocaleString() : '—'}
                        </Typography>
                      </Box>
                    </Grid>
                    <Grid item xs={6}>
                      <Box sx={{ mb: 1 }}>
                        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.78rem' }}>Entry Premium</Typography>
                        <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: 'monospace' }}>
                          ${(data.entry_fill_price || data.original_premium)?.toFixed(2) || '—'}
                        </Typography>
                      </Box>
                    </Grid>
                    <Grid item xs={4}>
                      <Box>
                        <HelpTooltip topic="original_lots">
                          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.78rem' }}>Original</Typography>
                        </HelpTooltip>
                        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>{data.original_lots || 0}</Typography>
                      </Box>
                    </Grid>
                    <Grid item xs={4}>
                      <Box>
                        <HelpTooltip topic="adjustment_lots">
                          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.78rem' }}>Adj Lots</Typography>
                        </HelpTooltip>
                        <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>{data.adjustment_total_lots || 0}</Typography>
                      </Box>
                    </Grid>
                    <Grid item xs={4}>
                      <Box>
                        <HelpTooltip topic="frozen_lots">
                          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.78rem' }}>Frozen</Typography>
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
              heartbeat={wsData.heartbeat}
              triggerData={wsData.heartbeat}
            />
          </Paper>

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
                      <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.72rem', textTransform: 'uppercase' }}>
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
        <MMMPositionsTable session={session} heartbeat={wsData.heartbeat} />
      )}

      {/* Tab 2: Triggers */}
      {detailTab === 2 && (
        <MMMTriggerGauge
          session={session}
          heartbeat={wsData.heartbeat}
          triggerData={wsData.heartbeat}
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
          minutesToExpiry={wsData.heartbeat?.minutes_to_expiry}
        />
      )}

      {/* Tab 6: Strike Map */}
      {detailTab === 6 && (
        <MMMStrikeMap
          session={session}
          spotPrice={wsData.heartbeat?.spot_price}
        />
      )}

      {/* Tab 7: Algo Calculations */}
      {detailTab === 7 && (
        <MMMAlgoCalculations
          session={session}
          wsData={wsData}
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

  // Settings dialog state
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsSessionId, setSettingsSessionId] = useState(null);

  // Full session object for detail view
  const [fullSession, setFullSession] = useState(null);

  // When selectedSessionId changes, fetch full session
  const selectedSession = useMemo(
    () => sessions.find((s) => s.session_id === selectedSessionId),
    [sessions, selectedSessionId]
  );

  // Fetch full session details when selected
  React.useEffect(() => {
    if (!selectedSessionId) {
      setFullSession(null);
      return;
    }

    let cancelled = false;
    const fetchFull = async () => {
      try {
        const result = await mmmService.getSession(selectedSessionId);
        if (!cancelled && result.success) {
          setFullSession(result.session);
        }
      } catch (err) {
        // If 404, the session was deleted — clear selection & localStorage
        if (err.status === 404 || err?.details?.error?.includes('not found')) {
          if (!cancelled) {
            setFullSession(null);
            selectSession(null);
            localStorage.removeItem('mmm_selectedSessionId');
          }
          return;
        }
        console.error('Failed to fetch full session:', err);
      }
    };

    fetchFull();
    const interval = setInterval(fetchFull, 5000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [selectedSessionId, selectSession]);

  // Session control handler
  const handleControl = useCallback(async (action, sessionId) => {
    try {
      let result;
      switch (action) {
        case 'start':
          result = await mmmService.startSession(sessionId);
          break;
        case 'pause':
          result = await mmmService.pauseSession(sessionId);
          break;
        case 'resume':
          result = await mmmService.resumeSession(sessionId);
          break;
        case 'stop':
          result = await mmmService.stopSession(sessionId);
          break;
        case 'delete':
          result = await mmmService.deleteSession(sessionId);
          break;
        case 'settings':
          // Open settings dialog
          setSettingsSessionId(sessionId);
          setSettingsOpen(true);
          return;
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
      || wsData.bothSidesAlert?.session_id
      || selectedSessionId;  // Fallback: user may have opened page after the alert fired
    if (!alertSessionId) return;

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
                  onInitialized={() => {
                    setSnackbar({ open: true, message: 'Session initialized!', severity: 'success' });
                    fetchSessions(false);
                  }}
                />
              )}
              <Paper sx={{ overflow: 'auto' }}>
                <SessionDetail session={fullSession} wsData={wsData} onBothSidesAction={handleBothSidesDecision} />
              </Paper>

              {/* Background Activities Feed */}
              <Box sx={{ mt: 2 }}>
                <MMMActivityFeed sessionId={selectedSessionId} socket={wsData.socket} />
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
