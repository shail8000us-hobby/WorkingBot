/**
 * MMMPerpHedgePanel — Perpetual Futures Delta Hedge Dashboard
 *
 * Displays the perp hedge state from heartbeat data:
 *   - Position status (enabled/disabled, lots, direction, avg entry)
 *   - P&L breakdown (realized, unrealized, total)
 *   - Delta info (portfolio delta, target lots)
 *   - Hedge activity (count, last hedge time)
 *   - Controls (toggle enable, manual close)
 *
 * Maps to MMM_robustv2.md §26 — Perpetual Futures Delta Hedge Module
 *
 * Created: February 26, 2026
 */

import React, { useState, useCallback, useMemo } from 'react';
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
  LinearProgress,
} from '@mui/material';
import {
  CheckCircle as CheckIcon,
  Warning as WarnIcon,
  Error as ErrorIcon,
  SwapVert as SwapIcon,
  TrendingUp as LongIcon,
  TrendingDown as ShortIcon,
  Block as BlockIcon,
  PowerSettingsNew as PowerIcon,
  Close as CloseIcon,
} from '@mui/icons-material';
import mmmService from './mmmService';


// =============================================================================
// Constants
// =============================================================================

const DIRECTION_LABELS = {
  long: { label: 'LONG', color: '#4caf50', icon: <LongIcon sx={{ fontSize: 16 }} /> },
  short: { label: 'SHORT', color: '#f44336', icon: <ShortIcon sx={{ fontSize: 16 }} /> },
  flat: { label: 'FLAT', color: '#9e9e9e', icon: <SwapIcon sx={{ fontSize: 16 }} /> },
};


// =============================================================================
// Sub-Components
// =============================================================================

function StatusBanner({ enabled, lots }) {
  if (!enabled) {
    return (
      <Alert
        severity="info"
        icon={<BlockIcon />}
        sx={{
          mb: 2,
          backgroundColor: 'rgba(158,158,158,0.1)',
          border: '1px solid rgba(158,158,158,0.3)',
        }}
      >
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          Perp Hedge: DISABLED
        </Typography>
        <Typography variant="body2" sx={{ opacity: 0.85 }}>
          Enable via Settings → Perp Hedge or use the toggle button below.
        </Typography>
      </Alert>
    );
  }

  const direction = lots > 0 ? 'long' : lots < 0 ? 'short' : 'flat';
  const dirInfo = DIRECTION_LABELS[direction];
  const severity = direction === 'flat' ? 'warning' : 'success';

  return (
    <Alert
      severity={severity}
      icon={dirInfo.icon}
      sx={{
        mb: 2,
        backgroundColor: `${dirInfo.color}12`,
        border: `1px solid ${dirInfo.color}40`,
        '& .MuiAlert-icon': { color: dirInfo.color },
      }}
    >
      <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
        Perp Hedge: ACTIVE — {dirInfo.label} {Math.abs(lots)} lots
      </Typography>
      <Typography variant="body2" sx={{ opacity: 0.85 }}>
        {direction === 'flat'
          ? 'No open perp position. Waiting for delta threshold breach.'
          : `BTCUSD perpetual ${direction} position open to neutralize portfolio delta.`}
      </Typography>
    </Alert>
  );
}


function PositionCard({ data }) {
  const lots = data?.lots || 0;
  const direction = lots > 0 ? 'long' : lots < 0 ? 'short' : 'flat';
  const dirInfo = DIRECTION_LABELS[direction];
  const avgEntry = data?.avg_entry || 0;
  const maxLots = data?.config?.perp_hedge_max_lots || 50;
  const utilization = maxLots > 0 ? (Math.abs(lots) / maxLots) * 100 : 0;

  return (
    <Paper sx={{ p: 2, border: `1px solid ${dirInfo.color}40`, backgroundColor: `${dirInfo.color}08` }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          Position
        </Typography>
        <Chip
          label={`${dirInfo.label} ${Math.abs(lots)}`}
          size="small"
          sx={{
            fontWeight: 700,
            fontFamily: 'monospace',
            backgroundColor: `${dirInfo.color}20`,
            color: dirInfo.color,
            border: `1px solid ${dirInfo.color}40`,
          }}
        />
      </Box>

      <Grid container spacing={1}>
        <Grid item xs={4}>
          <Typography variant="caption" sx={{ opacity: 0.6 }}>Lots (signed)</Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600, color: dirInfo.color }}>
            {lots >= 0 ? '+' : ''}{lots}
          </Typography>
        </Grid>
        <Grid item xs={4}>
          <Typography variant="caption" sx={{ opacity: 0.6 }}>BTC Size</Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
            {(Math.abs(lots) * 0.001).toFixed(4)}
          </Typography>
        </Grid>
        <Grid item xs={4}>
          <Typography variant="caption" sx={{ opacity: 0.6 }}>Avg Entry</Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
            {avgEntry > 0 ? `$${avgEntry.toFixed(0)}` : '—'}
          </Typography>
        </Grid>
      </Grid>

      {/* Utilization bar */}
      <Box sx={{ mt: 1.5 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
          <Typography variant="caption" sx={{ opacity: 0.5, fontSize: '0.7rem' }}>
            Lot utilization
          </Typography>
          <Typography variant="caption" sx={{ opacity: 0.5, fontSize: '0.7rem' }}>
            {Math.abs(lots)} / {maxLots}
          </Typography>
        </Box>
        <LinearProgress
          variant="determinate"
          value={Math.min(utilization, 100)}
          sx={{
            height: 6,
            borderRadius: 3,
            backgroundColor: 'rgba(255,255,255,0.1)',
            '& .MuiLinearProgress-bar': {
              backgroundColor: utilization > 80 ? '#f44336' : utilization > 50 ? '#ff9800' : '#4caf50',
              borderRadius: 3,
            },
          }}
        />
      </Box>
    </Paper>
  );
}


function PnLCard({ data }) {
  const realized = data?.realized_pnl || 0;
  const unrealized = data?.unrealized_pnl || 0;
  const total = data?.total_pnl || 0;

  const totalColor = total >= 0 ? '#4caf50' : '#f44336';

  return (
    <Paper sx={{ p: 2, border: `1px solid ${totalColor}40`, backgroundColor: `${totalColor}08` }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          P&L
        </Typography>
        <Chip
          label={`$${total >= 0 ? '+' : ''}${total.toFixed(2)}`}
          size="small"
          sx={{
            fontWeight: 700,
            fontFamily: 'monospace',
            backgroundColor: `${totalColor}20`,
            color: totalColor,
            border: `1px solid ${totalColor}40`,
          }}
        />
      </Box>

      <Grid container spacing={1}>
        <Grid item xs={4}>
          <Typography variant="caption" sx={{ opacity: 0.6 }}>Realized</Typography>
          <Typography variant="body2" sx={{
            fontFamily: 'monospace', fontWeight: 600,
            color: realized >= 0 ? '#4caf50' : '#f44336',
          }}>
            ${realized >= 0 ? '+' : ''}{realized.toFixed(2)}
          </Typography>
        </Grid>
        <Grid item xs={4}>
          <Typography variant="caption" sx={{ opacity: 0.6 }}>Unrealized</Typography>
          <Typography variant="body2" sx={{
            fontFamily: 'monospace', fontWeight: 600,
            color: unrealized >= 0 ? '#4caf50' : '#f44336',
          }}>
            ${unrealized >= 0 ? '+' : ''}{unrealized.toFixed(2)}
          </Typography>
        </Grid>
        <Grid item xs={4}>
          <Typography variant="caption" sx={{ opacity: 0.6 }}>Total</Typography>
          <Typography variant="body2" sx={{
            fontFamily: 'monospace', fontWeight: 700, fontSize: '0.95rem',
            color: totalColor,
          }}>
            ${total >= 0 ? '+' : ''}{total.toFixed(2)}
          </Typography>
        </Grid>
      </Grid>
    </Paper>
  );
}


function DeltaCard({ data }) {
  const lastDelta = data?.last_delta || 0;
  const targetLots = data?.target_lots || 0;
  const currentLots = data?.lots || 0;
  const threshold = data?.config?.perp_hedge_delta_threshold || 0.02;
  const ratio = data?.config?.perp_hedge_ratio || 1.0;

  const deltaColor = Math.abs(lastDelta) > threshold ? '#ff9800' : '#4caf50';
  const balanced = currentLots === targetLots;

  return (
    <Paper sx={{ p: 2, border: `1px solid ${deltaColor}40`, backgroundColor: `${deltaColor}08` }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          Delta & Target
        </Typography>
        <Chip
          label={balanced ? 'BALANCED' : 'IMBALANCED'}
          size="small"
          sx={{
            fontWeight: 700,
            fontFamily: 'monospace',
            backgroundColor: balanced ? '#4caf5020' : '#ff980020',
            color: balanced ? '#4caf50' : '#ff9800',
            border: `1px solid ${balanced ? '#4caf5040' : '#ff980040'}`,
          }}
        />
      </Box>

      <Grid container spacing={1}>
        <Grid item xs={3}>
          <Typography variant="caption" sx={{ opacity: 0.6 }}>Portfolio Δ</Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600, color: deltaColor }}>
            {lastDelta >= 0 ? '+' : ''}{lastDelta.toFixed(4)}
          </Typography>
        </Grid>
        <Grid item xs={3}>
          <Typography variant="caption" sx={{ opacity: 0.6 }}>Target Lots</Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
            {targetLots >= 0 ? '+' : ''}{targetLots}
          </Typography>
        </Grid>
        <Grid item xs={3}>
          <Typography variant="caption" sx={{ opacity: 0.6 }}>Threshold</Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
            {(threshold * 100).toFixed(1)}%
          </Typography>
        </Grid>
        <Grid item xs={3}>
          <Typography variant="caption" sx={{ opacity: 0.6 }}>Hedge Ratio</Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
            {(ratio * 100).toFixed(0)}%
          </Typography>
        </Grid>
      </Grid>
    </Paper>
  );
}


function ActivityCard({ data }) {
  const hedgeCount = data?.total_hedge_count || 0;
  const lastTime = data?.last_hedge_time;
  const symbol = data?.symbol || 'BTCUSD';
  const cooldown = data?.config?.perp_hedge_cooldown_sec || 30;

  const formatTime = (iso) => {
    if (!iso) return '—';
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return iso;
    }
  };

  return (
    <Paper sx={{ p: 2, border: '1px solid rgba(255,255,255,0.1)' }}>
      <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.5 }}>
        Activity
      </Typography>

      <Grid container spacing={1}>
        <Grid item xs={3}>
          <Typography variant="caption" sx={{ opacity: 0.6 }}>Symbol</Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
            {symbol}
          </Typography>
        </Grid>
        <Grid item xs={3}>
          <Typography variant="caption" sx={{ opacity: 0.6 }}>Total Hedges</Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600, color: '#2196f3' }}>
            {hedgeCount}
          </Typography>
        </Grid>
        <Grid item xs={3}>
          <Typography variant="caption" sx={{ opacity: 0.6 }}>Last Hedge</Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
            {formatTime(lastTime)}
          </Typography>
        </Grid>
        <Grid item xs={3}>
          <Typography variant="caption" sx={{ opacity: 0.6 }}>Cooldown</Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
            {cooldown}s
          </Typography>
        </Grid>
      </Grid>
    </Paper>
  );
}


// =============================================================================
// Main Component
// =============================================================================

export default function MMMPerpHedgePanel({ session, heartbeat, perpHedgeEvents = [], perpHedgeFlip }) {
  const [toggling, setToggling] = useState(false);
  const [closing, setClosing] = useState(false);
  const [actionResult, setActionResult] = useState(null);

  const sessionId = session?.session_id || session?.id;

  // Merge perp_hedge data from session (heartbeat auto-merges into session)
  const perpData = useMemo(() => {
    const hb = heartbeat?.perp_hedge || {};
    const sess = session?.perp_hedge || {};
    // Heartbeat is fresher, prefer it; fall back to session
    const merged = { ...sess, ...hb };
    // Attach config params for display
    const params = session?.params || heartbeat?.params || {};
    merged.config = {
      perp_hedge_enabled: params.perp_hedge_enabled ?? false,
      perp_hedge_delta_threshold: params.perp_hedge_delta_threshold ?? 0.02,
      perp_hedge_ratio: params.perp_hedge_ratio ?? 1.0,
      perp_hedge_rebalance_band: params.perp_hedge_rebalance_band ?? 0.005,
      perp_hedge_max_lots: params.perp_hedge_max_lots ?? 50,
      perp_hedge_cooldown_sec: params.perp_hedge_cooldown_sec ?? 30,
    };
    return merged;
  }, [session, heartbeat]);

  const enabled = perpData?.enabled ?? perpData?.config?.perp_hedge_enabled ?? false;
  const lots = perpData?.lots || 0;

  // Toggle perp hedge on/off
  const handleToggle = useCallback(async () => {
    if (!sessionId) return;
    try {
      setToggling(true);
      setActionResult(null);
      const result = await mmmService.togglePerpHedge(sessionId);
      setActionResult({
        type: 'success',
        message: result.message || `Perp hedge ${result.new_state ? 'enabled' : 'disabled'}`,
      });
    } catch (err) {
      setActionResult({
        type: 'error',
        message: err?.response?.data?.error || err.message || 'Toggle failed',
      });
    } finally {
      setToggling(false);
    }
  }, [sessionId]);

  // Manual close perp position
  const handleClose = useCallback(async () => {
    if (!sessionId) return;
    try {
      setClosing(true);
      setActionResult(null);
      const result = await mmmService.closePerpHedge(sessionId);
      setActionResult({
        type: 'success',
        message: result.message || 'Perp position closed',
      });
    } catch (err) {
      setActionResult({
        type: 'error',
        message: err?.response?.data?.error || err.message || 'Close failed',
      });
    } finally {
      setClosing(false);
    }
  }, [sessionId]);

  // No session selected
  if (!session) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography variant="body2" sx={{ opacity: 0.5 }}>
          Select a session to view perp hedge status.
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      {/* Status Banner */}
      <StatusBanner enabled={enabled} lots={lots} />

      {/* Action Result */}
      {actionResult && (
        <Alert
          severity={actionResult.type}
          onClose={() => setActionResult(null)}
          sx={{ mb: 2 }}
        >
          {actionResult.message}
        </Alert>
      )}

      {/* Controls */}
      <Box sx={{ display: 'flex', gap: 1.5, mb: 2 }}>
        <Button
          variant="outlined"
          size="small"
          startIcon={toggling ? <CircularProgress size={14} /> : <PowerIcon />}
          disabled={toggling || closing}
          onClick={handleToggle}
          sx={{
            borderColor: enabled ? '#f4433660' : '#4caf5060',
            color: enabled ? '#f44336' : '#4caf50',
            '&:hover': {
              borderColor: enabled ? '#f44336' : '#4caf50',
              backgroundColor: enabled ? 'rgba(244,67,54,0.08)' : 'rgba(76,175,80,0.08)',
            },
          }}
        >
          {enabled ? 'Disable Hedge' : 'Enable Hedge'}
        </Button>

        {lots !== 0 && (
          <Button
            variant="outlined"
            size="small"
            startIcon={closing ? <CircularProgress size={14} /> : <CloseIcon />}
            disabled={toggling || closing}
            onClick={handleClose}
            sx={{
              borderColor: '#ff980060',
              color: '#ff9800',
              '&:hover': {
                borderColor: '#ff9800',
                backgroundColor: 'rgba(255,152,0,0.08)',
              },
            }}
          >
            Close Perp Position
          </Button>
        )}
      </Box>

      {/* Cards Grid */}
      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <PositionCard data={perpData} />
        </Grid>
        <Grid item xs={12} md={6}>
          <PnLCard data={perpData} />
        </Grid>
        <Grid item xs={12} md={6}>
          <DeltaCard data={perpData} />
        </Grid>
        <Grid item xs={12} md={6}>
          <ActivityCard data={perpData} />
        </Grid>
      </Grid>

      {/* Recent Flip Alert */}
      {perpHedgeFlip && (
        <Alert
          severity="warning"
          icon={<SwapIcon />}
          sx={{
            mt: 2,
            backgroundColor: 'rgba(255,152,0,0.1)',
            border: '1px solid rgba(255,152,0,0.3)',
          }}
        >
          <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
            Position Flip: {perpHedgeFlip.old_direction?.toUpperCase()} → {perpHedgeFlip.new_direction?.toUpperCase()}
          </Typography>
          <Typography variant="body2" sx={{ opacity: 0.85 }}>
            Closed {perpHedgeFlip.lots_closed} lots, new position: {perpHedgeFlip.new_lots} lots @
            ${perpHedgeFlip.fill_price?.toFixed(0)}. Realized P&L: ${perpHedgeFlip.realized_pnl?.toFixed(2)}
          </Typography>
        </Alert>
      )}

      {/* Recent Executions Log */}
      {perpHedgeEvents.length > 0 && (
        <Box sx={{ mt: 2 }}>
          <Divider sx={{ mb: 1.5 }} />
          <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
            Recent Hedge Executions
          </Typography>
          <Box sx={{ maxHeight: 200, overflow: 'auto' }}>
            {perpHedgeEvents.slice(-10).reverse().map((evt, idx) => (
              <Box
                key={idx}
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  py: 0.5,
                  px: 1,
                  borderBottom: '1px solid rgba(255,255,255,0.05)',
                  '&:hover': { backgroundColor: 'rgba(255,255,255,0.03)' },
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Chip
                    label={evt.action}
                    size="small"
                    sx={{
                      fontFamily: 'monospace',
                      fontSize: '0.7rem',
                      height: 20,
                      backgroundColor: evt.action === 'BUY' ? '#4caf5020' : '#f4433620',
                      color: evt.action === 'BUY' ? '#4caf50' : '#f44336',
                    }}
                  />
                  <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                    {evt.lots} lots @ ${evt.fill_price?.toFixed(0)}
                  </Typography>
                </Box>
                <Typography variant="caption" sx={{ opacity: 0.5, fontFamily: 'monospace' }}>
                  Δ={evt.effective_delta?.toFixed(4)}
                </Typography>
              </Box>
            ))}
          </Box>
        </Box>
      )}

      {/* How It Works */}
      <Box sx={{ mt: 2 }}>
        <Divider sx={{ mb: 1.5 }} />
        <Typography variant="caption" sx={{ opacity: 0.5, display: 'block', mb: 0.5 }}>
          The perp hedge module runs each heartbeat after safety checks. It computes portfolio delta
          from all option positions and trades BTCUSD perpetual futures to neutralize exposure.
        </Typography>
        <Grid container spacing={1}>
          <Grid item xs={4}>
            <Typography variant="caption" sx={{ opacity: 0.4, fontSize: '0.65rem' }}>
              <strong>Threshold:</strong> Only hedges when |delta| exceeds the configured threshold.
              Rebalance band prevents small adjustments.
            </Typography>
          </Grid>
          <Grid item xs={4}>
            <Typography variant="caption" sx={{ opacity: 0.4, fontSize: '0.65rem' }}>
              <strong>Lot Sizing:</strong> 1 lot = 0.001 BTC. Hedge ratio controls what fraction
              of delta to offset (100% = full neutralization).
            </Typography>
          </Grid>
          <Grid item xs={4}>
            <Typography variant="caption" sx={{ opacity: 0.4, fontSize: '0.65rem' }}>
              <strong>Safety:</strong> Max lot cap prevents outsized positions. Cooldown prevents
              rapid-fire hedging. Auto-close on session stop.
            </Typography>
          </Grid>
        </Grid>
      </Box>
    </Box>
  );
}
