/**
 * MMMReverseModePanel — Controlled Reverse Mode Dashboard
 *
 * Displays live reverse mode state from heartbeat data:
 *   - Active/disabled status with enable/disable controls
 *   - Slots used / remaining
 *   - P&L breakdown (realized, unrealized, net)
 *   - Delta exposure from open positions
 *   - Position table (side, strike, lots, premium, P&L)
 *   - Window time remaining
 *   - History of closed reverse positions
 *
 * Maps to MMM_REVERSE_MODE_DESIGN.md — Controlled Reverse Mode overlay.
 *
 * Created: 2026-03-26
 */

import React, { useState, useCallback } from 'react';
import {
  Box,
  Typography,
  Grid,
  Paper,
  Chip,
  Button,
  Alert,
  Divider,
  Tooltip,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material';
import {
  CheckCircle as CheckIcon,
  Warning as WarnIcon,
  Block as BlockIcon,
  PowerSettingsNew as PowerIcon,
  Close as CloseIcon,
  SwapHoriz as ReverseIcon,
} from '@mui/icons-material';
import mmmService from './mmmService';


// =============================================================================
// Helpers
// =============================================================================

function fmt(v, decimals = 2) {
  if (v == null || v === '') return '—';
  const n = parseFloat(v);
  if (isNaN(n)) return '—';
  return n.toFixed(decimals);
}

const REVERSE_SUPPORTED_STRATEGIES = new Set(['0DTE', '5DTE', 'SHORT_WINDOW']);

function resolveStrategyType(session) {
  const raw = String(
    session?.strategy_type ||
    session?.params?.strategy_type ||
    session?.params?._preset_source ||
    session?.params?.dte_category ||
    '0DTE'
  ).toUpperCase();
  return raw === 'SHORT_STRADDLE' ? 'STRADDLE_WITH_ADJUSTMENT' : raw;
}

function fmtPnl(v) {
  if (v == null) return '—';
  const n = parseFloat(v);
  if (isNaN(n)) return '—';
  const prefix = n >= 0 ? '+' : '';
  return `${prefix}$${Math.abs(n).toFixed(2)}`;
}

function pnlColor(v) {
  if (v == null) return '#9e9e9e';
  const n = parseFloat(v);
  if (isNaN(n)) return '#9e9e9e';
  if (n > 0) return '#4caf50';
  if (n < 0) return '#f44336';
  return '#9e9e9e';
}

function StatBox({ label, value, color, sub }) {
  return (
    <Paper sx={{ p: 1.5, background: '#161b22', border: '1px solid #30363d', borderRadius: 1, textAlign: 'center' }}>
      <Typography variant="caption" sx={{ color: '#8b949e', display: 'block' }}>{label}</Typography>
      <Typography variant="h6" sx={{ fontWeight: 700, color: color || '#e6edf3', fontFamily: 'monospace' }}>
        {value}
      </Typography>
      {sub && <Typography variant="caption" sx={{ color: '#8b949e' }}>{sub}</Typography>}
    </Paper>
  );
}


// =============================================================================
// Sub-Components
// =============================================================================

function StatusBanner({ enabled, active, disableReason }) {
  if (!enabled) {
    return (
      <Alert
        severity="info"
        icon={<BlockIcon />}
        sx={{ mb: 2, backgroundColor: 'rgba(158,158,158,0.1)', border: '1px solid rgba(158,158,158,0.3)' }}
      >
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>Reverse Mode: DISABLED</Typography>
        <Typography variant="body2" sx={{ opacity: 0.85 }}>
          Enable via Settings → Reverse Mode or the button below.
        </Typography>
      </Alert>
    );
  }
  if (!active) {
    return (
      <Alert
        severity="warning"
        icon={<WarnIcon />}
        sx={{ mb: 2, backgroundColor: 'rgba(255,152,0,0.1)', border: '1px solid rgba(255,152,0,0.3)' }}
      >
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>Reverse Mode: ENABLED (not yet active)</Typography>
        <Typography variant="body2" sx={{ opacity: 0.85 }}>
          {disableReason ? `Last disabled: ${disableReason}` : 'Waiting for next trigger to activate.'}
        </Typography>
      </Alert>
    );
  }
  return (
    <Alert
      severity="error"
      icon={<ReverseIcon />}
      sx={{ mb: 2, backgroundColor: 'rgba(233,30,99,0.1)', border: '1px solid rgba(233,30,99,0.5)' }}
    >
      <Typography variant="subtitle2" sx={{ fontWeight: 700, color: '#e91e63' }}>
        REVERSE MODE ACTIVE — Normal hedge-sell logic suspended
      </Typography>
      <Typography variant="body2" sx={{ opacity: 0.85 }}>
        Selling same-side premium (directional harvesting). CE→PE→CE alternating enforced. Max-loss and trailing stop continue running.
      </Typography>
    </Alert>
  );
}


function PositionsTable({ positions }) {
  if (!positions || positions.length === 0) {
    return (
      <Typography variant="body2" sx={{ color: '#8b949e', fontStyle: 'italic', mt: 1 }}>
        No open reverse positions.
      </Typography>
    );
  }
  return (
    <TableContainer component={Paper} sx={{ background: '#161b22', border: '1px solid #30363d', mt: 1 }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell sx={{ color: '#8b949e', fontWeight: 700 }}>Side</TableCell>
            <TableCell sx={{ color: '#8b949e', fontWeight: 700 }}>Strike</TableCell>
            <TableCell sx={{ color: '#8b949e', fontWeight: 700 }}>Lots</TableCell>
            <TableCell sx={{ color: '#8b949e', fontWeight: 700 }}>Entry $</TableCell>
            <TableCell sx={{ color: '#8b949e', fontWeight: 700 }}>Current $</TableCell>
            <TableCell sx={{ color: '#8b949e', fontWeight: 700 }}>Unreal P&L</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {positions.map((pos, i) => {
            const unrealPnl = pos.unrealized_pnl != null ? parseFloat(pos.unrealized_pnl) : null;
            return (
              <TableRow key={i}>
                <TableCell>
                  <Chip
                    label={String(pos.option_type || '').toUpperCase()}
                    size="small"
                    sx={{
                      fontWeight: 700, fontSize: 11,
                      backgroundColor: pos.option_type === 'ce' ? 'rgba(33,150,243,0.15)' : 'rgba(244,67,54,0.15)',
                      color: pos.option_type === 'ce' ? '#2196f3' : '#f44336',
                    }}
                  />
                </TableCell>
                <TableCell sx={{ color: '#e6edf3', fontFamily: 'monospace' }}>
                  {pos.strike ? Number(pos.strike).toLocaleString() : '—'}
                </TableCell>
                <TableCell sx={{ color: '#e6edf3', fontFamily: 'monospace' }}>{pos.lots ?? '—'}</TableCell>
                <TableCell sx={{ color: '#e6edf3', fontFamily: 'monospace' }}>${fmt(pos.entry_premium)}</TableCell>
                <TableCell sx={{ color: '#e6edf3', fontFamily: 'monospace' }}>${fmt(pos.current_premium)}</TableCell>
                <TableCell sx={{ color: pnlColor(unrealPnl), fontFamily: 'monospace', fontWeight: 700 }}>
                  {fmtPnl(unrealPnl)}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </TableContainer>
  );
}


// =============================================================================
// Main Panel
// =============================================================================

export default function MMMReverseModePanel({ session, heartbeat }) {
  const sessionId = session?.session_id;
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState(null);
  const strategyType = resolveStrategyType(session);
  const reverseSupportedByStrategy = REVERSE_SUPPORTED_STRATEGIES.has(strategyType);

  if (!reverseSupportedByStrategy) {
    return (
      <Alert severity="info" sx={{ mt: 1 }}>
        Reverse Mode is not available for <strong>{strategyType}</strong> sessions.
      </Alert>
    );
  }

  // Pull reverse state from heartbeat (live) with storage fallback
  const params = session?.params || {};
  const reverseEnabled = params.reverse_enabled || false;
  const reverseState = heartbeat?._reverse || session?._reverse || {};
  const active = reverseState.active || false;

  const slotsUsed = reverseState.slots_used ?? 0;
  const slotsRemaining = reverseState.slots_remaining ?? (params.reverse_num_slots || 5);
  const totalSlots = slotsUsed + slotsRemaining;
  const lastSide = reverseState.last_reverse_side;
  const adjustmentCount = reverseState.adjustment_count ?? 0;
  const totalLots = reverseState.total_lots ?? 0;
  const totalPremiumCollected = reverseState.total_premium_collected ?? 0;
  const realizedPnl = reverseState.realized_pnl ?? 0;
  const unrealizedPnl = reverseState.unrealized_pnl ?? 0;
  const netPnl = reverseState.net_pnl ?? 0;
  const deltaExposure = reverseState.delta_exposure ?? 0;
  const positions = reverseState.positions || [];
  const disableReason = reverseState.disable_reason;
  const enabledAt = reverseState.enabled_at;
  const disabledAt = reverseState.disabled_at;

  const handleEnable = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    setMsg(null);
    try {
      await mmmService.enableReverseMode(sessionId);
      setMsg({ type: 'success', text: 'Reverse mode enabled.' });
    } catch (e) {
      setMsg({ type: 'error', text: e?.message || 'Failed to enable.' });
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  const handleDisable = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    setMsg(null);
    try {
      await mmmService.disableReverseMode(sessionId);
      setMsg({ type: 'success', text: 'Reverse mode disabled.' });
    } catch (e) {
      setMsg({ type: 'error', text: e?.message || 'Failed to disable.' });
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  const handleCloseAll = useCallback(async () => {
    if (!sessionId) return;
    if (!window.confirm('Close ALL open reverse positions? This will send real orders.')) return;
    setLoading(true);
    setMsg(null);
    try {
      await mmmService.closeAllReversePositions(sessionId);
      setMsg({ type: 'success', text: 'Reverse positions closed.' });
    } catch (e) {
      setMsg({ type: 'error', text: e?.message || 'Failed to close.' });
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  return (
    <Box sx={{ p: 1 }}>
      <Typography variant="h6" sx={{ fontWeight: 700, mb: 1, color: '#e91e63', display: 'flex', alignItems: 'center', gap: 1 }}>
        <ReverseIcon /> Controlled Reverse Mode
      </Typography>

      <StatusBanner enabled={reverseEnabled} active={active} disableReason={disableReason} />

      {msg && (
        <Alert severity={msg.type} sx={{ mb: 1 }} onClose={() => setMsg(null)}>
          {msg.text}
        </Alert>
      )}

      {/* Controls */}
      <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
        {!reverseEnabled ? (
          <Tooltip title="Enable reverse mode. Normal hedge-sell logic will be suspended when active.">
            <span>
              <Button
                variant="contained"
                size="small"
                startIcon={loading ? <CircularProgress size={14} /> : <PowerIcon />}
                onClick={handleEnable}
                disabled={loading || !sessionId}
                sx={{ backgroundColor: '#e91e63', '&:hover': { backgroundColor: '#c2185b' } }}
              >
                Enable Reverse Mode
              </Button>
            </span>
          </Tooltip>
        ) : (
          <Tooltip title="Disable reverse mode. Does NOT close open positions.">
            <span>
              <Button
                variant="outlined"
                size="small"
                startIcon={loading ? <CircularProgress size={14} /> : <BlockIcon />}
                onClick={handleDisable}
                disabled={loading || !sessionId}
                sx={{ borderColor: '#9e9e9e', color: '#9e9e9e' }}
              >
                Disable
              </Button>
            </span>
          </Tooltip>
        )}
        {positions.length > 0 && (
          <Tooltip title="Close ALL open reverse positions (real orders).">
            <span>
              <Button
                variant="outlined"
                size="small"
                startIcon={loading ? <CircularProgress size={14} /> : <CloseIcon />}
                onClick={handleCloseAll}
                disabled={loading || !sessionId}
                sx={{ borderColor: '#f44336', color: '#f44336' }}
              >
                Close All Reverse Positions
              </Button>
            </span>
          </Tooltip>
        )}
      </Box>

      <Divider sx={{ borderColor: '#21262d', mb: 2 }} />

      {/* Stats Row */}
      <Grid container spacing={1} sx={{ mb: 2 }}>
        <Grid item xs={6} sm={4} md={2}>
          <StatBox
            label="Slots Used"
            value={`${slotsUsed} / ${totalSlots}`}
            color={slotsUsed >= totalSlots ? '#f44336' : '#e6edf3'}
          />
        </Grid>
        <Grid item xs={6} sm={4} md={2}>
          <StatBox
            label="Slots Left"
            value={slotsRemaining}
            color={slotsRemaining === 0 ? '#f44336' : '#4caf50'}
          />
        </Grid>
        <Grid item xs={6} sm={4} md={2}>
          <StatBox
            label="Last Side"
            value={lastSide ? lastSide.toUpperCase() : '—'}
            color={lastSide === 'ce' ? '#2196f3' : lastSide === 'pe' ? '#f44336' : '#9e9e9e'}
          />
        </Grid>
        <Grid item xs={6} sm={4} md={2}>
          <StatBox label="Adjustments" value={adjustmentCount} />
        </Grid>
        <Grid item xs={6} sm={4} md={2}>
          <StatBox label="Total Lots" value={totalLots} />
        </Grid>
        <Grid item xs={6} sm={4} md={2}>
          <StatBox
            label="Delta Exposure"
            value={fmt(deltaExposure, 4)}
            color={Math.abs(parseFloat(deltaExposure) || 0) > 0.05 ? '#ff9800' : '#9e9e9e'}
            sub="BTC"
          />
        </Grid>
      </Grid>

      {/* P&L Row */}
      <Grid container spacing={1} sx={{ mb: 2 }}>
        <Grid item xs={6} sm={3}>
          <StatBox label="Total Premium Collected" value={`$${fmt(totalPremiumCollected)}`} color="#4caf50" />
        </Grid>
        <Grid item xs={6} sm={3}>
          <StatBox label="Realized P&L" value={fmtPnl(realizedPnl)} color={pnlColor(realizedPnl)} />
        </Grid>
        <Grid item xs={6} sm={3}>
          <StatBox label="Unrealized P&L" value={fmtPnl(unrealizedPnl)} color={pnlColor(unrealizedPnl)} />
        </Grid>
        <Grid item xs={6} sm={3}>
          <StatBox label="Net P&L" value={fmtPnl(netPnl)} color={pnlColor(netPnl)} />
        </Grid>
      </Grid>

      {/* Meta info */}
      {(enabledAt || disabledAt) && (
        <Box sx={{ mb: 2, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          {enabledAt && (
            <Typography variant="caption" sx={{ color: '#8b949e' }}>
              Enabled at: {new Date(enabledAt).toLocaleTimeString()}
            </Typography>
          )}
          {disabledAt && (
            <Typography variant="caption" sx={{ color: '#8b949e' }}>
              Disabled at: {new Date(disabledAt).toLocaleTimeString()}
              {disableReason && ` (${disableReason})`}
            </Typography>
          )}
        </Box>
      )}

      <Divider sx={{ borderColor: '#21262d', mb: 1 }} />

      {/* Open Positions */}
      <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5, color: '#e6edf3' }}>
        Open Reverse Positions ({positions.filter(p => p.status === 'open').length})
      </Typography>
      <PositionsTable positions={positions.filter(p => p.status === 'open')} />

      {/* Config summary */}
      <Divider sx={{ borderColor: '#21262d', mt: 2, mb: 1 }} />
      <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5, color: '#8b949e' }}>
        Config (read-only — edit in Settings)
      </Typography>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        {[
          { label: 'Capacity', value: `${params.reverse_capacity_pct ?? 10}%` },
          { label: 'Max Loss', value: `$${params.reverse_max_loss ?? 100}` },
          { label: 'Close At', value: `$${params.reverse_close_at_threshold ?? 8}` },
          { label: 'Cooldown', value: `${params.reverse_cooldown_mins ?? 5}m` },
          { label: 'Max Adj', value: params.reverse_max_adjustments ?? 3 },
          { label: 'Mode', value: params.reverse_mode_type || 'strict_alternating' },
        ].map(({ label, value }) => (
          <Chip
            key={label}
            label={`${label}: ${value}`}
            size="small"
            sx={{ backgroundColor: '#161b22', border: '1px solid #30363d', color: '#8b949e', fontSize: 11 }}
          />
        ))}
      </Box>
    </Box>
  );
}
