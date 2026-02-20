/**
 * MMMMarginGuardianPanel — Money Mind & Method
 *
 * ALWAYS-LIVE exchange margin utilization dashboard.
 * Fetches margin data directly from Delta Exchange India — covers ALL
 * positions: all algos, manual trades, every product. The exchange is
 * the single source of truth for margin.
 *
 * Features:
 * - Live margin utilization gauge (always visible, auto-refreshes every 10s)
 * - Wallet balance breakdown (position margin, order margin, equity)
 * - All open positions from exchange (sorted by margin usage)
 * - Guardian defense tier ladder (separate from margin display)
 * - Quick-toggle for Guardian defense system
 *
 * Created: February 20, 2026
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box,
  Typography,
  Paper,
  Grid,
  LinearProgress,
  Chip,
  Switch,
  FormControlLabel,
  Button,
  CircularProgress,
  Tooltip,
  Alert,
  Divider,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Collapse,
} from '@mui/material';
import {
  Shield as ShieldIcon,
  Warning as WarnIcon,
  Error as ErrorIcon,
  CheckCircle as OKIcon,
  Refresh as RefreshIcon,
  TrendingUp as TrendingIcon,
  AccountBalance as WalletIcon,
  ExpandMore as ExpandIcon,
  ExpandLess as CollapseIcon,
  Speed as SpeedIcon,
  Visibility as VisibilityIcon,
} from '@mui/icons-material';
import mmmService from './mmmService';

// Tier configuration
const TIER_CONFIG = {
  GREEN:    { color: '#4caf50', bg: 'rgba(76,175,80,0.08)',   icon: OKIcon,    label: 'Normal',    emoji: '🟢' },
  YELLOW:   { color: '#ffc107', bg: 'rgba(255,193,7,0.08)',   icon: WarnIcon,  label: 'Caution',   emoji: '🟡' },
  ORANGE:   { color: '#ff9800', bg: 'rgba(255,152,0,0.08)',   icon: WarnIcon,  label: 'Wind Down', emoji: '🟠' },
  RED:      { color: '#f44336', bg: 'rgba(244,67,54,0.08)',   icon: ErrorIcon, label: 'Emergency', emoji: '🔴' },
  CRITICAL: { color: '#b71c1c', bg: 'rgba(183,28,28,0.12)',   icon: ErrorIcon, label: 'Survival',  emoji: '🚨' },
};

const TIER_ORDER = ['GREEN', 'YELLOW', 'ORANGE', 'RED', 'CRITICAL'];

function TierBadge({ tier }) {
  const config = TIER_CONFIG[tier] || TIER_CONFIG.GREEN;
  const Icon = config.icon;
  return (
    <Chip
      icon={<Icon sx={{ fontSize: 14 }} />}
      label={`${config.emoji} ${config.label}`}
      size="small"
      sx={{
        bgcolor: config.bg,
        color: config.color,
        fontWeight: 700,
        border: `1px solid ${config.color}40`,
        fontSize: '0.75rem',
      }}
    />
  );
}

// Determine visual tier from utilization (independent of Guardian thresholds)
function getUtilizationColor(util) {
  if (util >= 90) return '#b71c1c';
  if (util >= 80) return '#f44336';
  if (util >= 70) return '#ff9800';
  if (util >= 55) return '#ffc107';
  return '#4caf50';
}

function UtilizationGauge({ utilization, tier, thresholds }) {
  const barColor = getUtilizationColor(utilization);
  const clampedUtil = Math.min(utilization, 100);

  return (
    <Paper
      variant="outlined"
      sx={{ p: 2, borderRadius: 2, borderColor: `${barColor}40` }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <SpeedIcon sx={{ fontSize: 18, color: barColor }} />
          <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'text.primary' }}>
            Exchange Margin Utilization
          </Typography>
        </Box>
        <Typography variant="h6" sx={{ fontWeight: 800, color: barColor, fontFamily: 'monospace' }}>
          {utilization.toFixed(1)}%
        </Typography>
      </Box>

      {/* Main gauge */}
      <Box sx={{ position: 'relative', mb: 1 }}>
        <LinearProgress
          variant="determinate"
          value={clampedUtil}
          sx={{
            height: 20,
            borderRadius: 10,
            bgcolor: 'action.hover',
            '& .MuiLinearProgress-bar': {
              bgcolor: barColor,
              borderRadius: 10,
              transition: 'transform 0.8s ease',
            },
          }}
        />
        <Typography
          variant="caption"
          sx={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            fontWeight: 700,
            color: clampedUtil > 40 ? '#fff' : 'text.primary',
            fontSize: '0.75rem',
            textShadow: clampedUtil > 40 ? '0 1px 2px rgba(0,0,0,0.5)' : 'none',
          }}
        >
          {utilization.toFixed(1)}%
        </Typography>
      </Box>

      {/* Threshold markers */}
      {thresholds && (
        <Box sx={{ position: 'relative', height: 22, mt: 0.5 }}>
          {Object.entries(thresholds).map(([name, pct]) => {
            if (name === 'target') return null;
            const tierName = name.toUpperCase();
            const tc = TIER_CONFIG[tierName];
            if (!tc || pct == null) return null;
            return (
              <Tooltip key={name} title={`${tierName} threshold: ${pct}%`} placement="bottom">
                <Box
                  sx={{
                    position: 'absolute',
                    left: `${Math.min(pct, 100)}%`,
                    transform: 'translateX(-50%)',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                  }}
                >
                  <Box sx={{ width: 2, height: 10, bgcolor: tc.color, opacity: 0.7 }} />
                  <Typography
                    variant="caption"
                    sx={{ fontSize: '0.55rem', color: tc.color, fontWeight: 600, lineHeight: 1 }}
                  >
                    {pct}
                  </Typography>
                </Box>
              </Tooltip>
            );
          })}
        </Box>
      )}
    </Paper>
  );
}

function WalletBreakdown({ marginData }) {
  if (!marginData || Object.keys(marginData).length === 0) return null;

  const items = [
    { label: 'Net Equity', value: marginData.net_equity, color: '#2196f3', isBase: true },
    { label: 'Available Balance', value: marginData.available_balance, color: '#4caf50' },
    { label: 'Position Margin', value: marginData.position_margin, color: '#ff9800' },
    { label: 'Order Margin', value: marginData.order_margin, color: '#9c27b0' },
    { label: 'Blocked Margin', value: marginData.blocked_margin, color: '#607d8b' },
  ];

  const equity = marginData.net_equity || 1;

  return (
    <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
        <WalletIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          Wallet Breakdown
        </Typography>
      </Box>

      {items.map((item) => {
        const val = item.value || 0;
        const pct = equity > 0 ? (Math.abs(val) / equity) * 100 : 0;
        return (
          <Box key={item.label} sx={{ mb: 1.2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.25 }}>
              <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.72rem' }}>
                {item.label}
              </Typography>
              <Typography
                variant="caption"
                sx={{ fontFamily: 'monospace', fontWeight: 600, fontSize: '0.75rem' }}
              >
                ${val.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                {!item.isBase && (
                  <span style={{ opacity: 0.5, marginLeft: 4 }}>
                    ({pct.toFixed(1)}%)
                  </span>
                )}
              </Typography>
            </Box>
            {!item.isBase && (
              <LinearProgress
                variant="determinate"
                value={Math.min(pct, 100)}
                sx={{
                  height: 4,
                  borderRadius: 2,
                  bgcolor: 'action.hover',
                  '& .MuiLinearProgress-bar': { bgcolor: item.color, borderRadius: 2 },
                }}
              />
            )}
          </Box>
        );
      })}
    </Paper>
  );
}

function PositionsTable({ positions }) {
  const [expanded, setExpanded] = useState(true);

  if (!positions || positions.length === 0) {
    return (
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>
          No open positions on exchange
        </Typography>
      </Paper>
    );
  }

  return (
    <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
      <Box
        sx={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          px: 2, py: 1, cursor: 'pointer', bgcolor: 'action.hover',
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <VisibilityIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
          <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
            All Open Positions
          </Typography>
          <Chip
            label={positions.length}
            size="small"
            sx={{ height: 18, fontSize: '0.65rem', fontWeight: 700 }}
          />
        </Box>
        <IconButton size="small">
          {expanded ? <CollapseIcon sx={{ fontSize: 18 }} /> : <ExpandIcon sx={{ fontSize: 18 }} />}
        </IconButton>
      </Box>

      <Collapse in={expanded}>
        <TableContainer sx={{ maxHeight: 300 }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontSize: '0.68rem', fontWeight: 700, py: 0.5 }}>Symbol</TableCell>
                <TableCell sx={{ fontSize: '0.68rem', fontWeight: 700, py: 0.5 }} align="right">Size</TableCell>
                <TableCell sx={{ fontSize: '0.68rem', fontWeight: 700, py: 0.5 }} align="right">Entry</TableCell>
                <TableCell sx={{ fontSize: '0.68rem', fontWeight: 700, py: 0.5 }} align="right">Mark</TableCell>
                <TableCell sx={{ fontSize: '0.68rem', fontWeight: 700, py: 0.5 }} align="right">Margin</TableCell>
                <TableCell sx={{ fontSize: '0.68rem', fontWeight: 700, py: 0.5 }} align="right">Unrlzd P&L</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {positions.map((pos, idx) => {
                const isShort = pos.side === 'short';
                const pnlColor = (pos.unrealized_pnl || 0) >= 0 ? '#4caf50' : '#f44336';
                return (
                  <TableRow key={`${pos.symbol}-${idx}`} hover>
                    <TableCell sx={{ fontSize: '0.7rem', py: 0.5, fontFamily: 'monospace' }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        {pos.symbol}
                        <Chip
                          label={isShort ? 'S' : 'L'}
                          size="small"
                          sx={{
                            height: 16, fontSize: '0.55rem', fontWeight: 700,
                            bgcolor: isShort ? 'rgba(244,67,54,0.12)' : 'rgba(76,175,80,0.12)',
                            color: isShort ? '#f44336' : '#4caf50',
                          }}
                        />
                      </Box>
                    </TableCell>
                    <TableCell align="right" sx={{ fontSize: '0.7rem', py: 0.5, fontFamily: 'monospace' }}>
                      {Math.abs(pos.size)}
                    </TableCell>
                    <TableCell align="right" sx={{ fontSize: '0.7rem', py: 0.5, fontFamily: 'monospace' }}>
                      ${pos.entry_price?.toFixed(2) || '—'}
                    </TableCell>
                    <TableCell align="right" sx={{ fontSize: '0.7rem', py: 0.5, fontFamily: 'monospace' }}>
                      ${pos.mark_price?.toFixed(2) || '—'}
                    </TableCell>
                    <TableCell align="right" sx={{ fontSize: '0.7rem', py: 0.5, fontFamily: 'monospace', fontWeight: 600 }}>
                      ${pos.margin?.toFixed(2) || '0.00'}
                    </TableCell>
                    <TableCell
                      align="right"
                      sx={{ fontSize: '0.7rem', py: 0.5, fontFamily: 'monospace', fontWeight: 600, color: pnlColor }}
                    >
                      ${(pos.unrealized_pnl || 0) >= 0 ? '+' : ''}{(pos.unrealized_pnl || 0).toFixed(2)}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      </Collapse>
    </Paper>
  );
}

function TierLadder({ currentTier, thresholds, utilization }) {
  return (
    <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
        <ShieldIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          Guardian Defense Tiers
        </Typography>
      </Box>

      {TIER_ORDER.map((tier) => {
        const tc = TIER_CONFIG[tier];
        const thresholdKey = tier.toLowerCase();
        const threshold = thresholds?.[thresholdKey];
        const isCurrent = tier === currentTier;
        const actions = {
          GREEN: 'Normal operation',
          YELLOW: 'Block new sells',
          ORANGE: 'Force buyback + block sells',
          RED: 'Emergency close all (taker orders)',
          CRITICAL: 'Close all + stop session',
        };

        return (
          <Box
            key={tier}
            sx={{
              display: 'flex', alignItems: 'center', gap: 1,
              py: 0.75, px: 1, mb: 0.5, borderRadius: 1,
              bgcolor: isCurrent ? tc.bg : 'transparent',
              border: isCurrent ? `1px solid ${tc.color}40` : '1px solid transparent',
              transition: 'all 0.3s ease',
            }}
          >
            <Typography sx={{ fontSize: '0.85rem', width: 20 }}>{tc.emoji}</Typography>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography
                variant="caption"
                sx={{
                  fontWeight: isCurrent ? 700 : 500,
                  color: isCurrent ? tc.color : 'text.secondary',
                  fontSize: '0.72rem',
                }}
              >
                {tier} {threshold != null ? `(≥${threshold}%)` : ''}
              </Typography>
              <Typography
                variant="caption"
                sx={{ display: 'block', fontSize: '0.62rem', color: 'text.disabled', lineHeight: 1.2 }}
              >
                {actions[tier]}
              </Typography>
            </Box>
            {isCurrent && (
              <Chip
                label="NOW"
                size="small"
                sx={{ height: 18, fontSize: '0.6rem', fontWeight: 700, bgcolor: tc.color, color: '#fff' }}
              />
            )}
          </Box>
        );
      })}
    </Paper>
  );
}

export default function MMMMarginGuardianPanel({ session, sessionId }) {
  const [exchangeMargin, setExchangeMargin] = useState(null);
  const [guardianStatus, setGuardianStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(10); // seconds
  const lastFetchRef = useRef(null);

  const params = session?.params || {};
  const guardianEnabled = params.margin_monitor_enabled || false;

  // Fetch exchange-level margin (always — not gated behind Guardian)
  const fetchExchangeMargin = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await mmmService.getExchangeMargin();
      if (result.success) {
        setExchangeMargin(result);
        lastFetchRef.current = new Date();
      } else {
        setError(result.error || 'Failed to fetch exchange margin');
      }
    } catch (err) {
      setError(err.message || 'Network error');
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch Guardian tier status (session-specific)
  const fetchGuardianStatus = useCallback(async () => {
    if (!sessionId) return;
    try {
      const result = await mmmService.getMarginStatus(sessionId);
      if (result.success) {
        setGuardianStatus(result);
      }
    } catch (err) {
      // Non-critical — Guardian status is supplementary
    }
  }, [sessionId]);

  // Combined fetch
  const fetchAll = useCallback(async () => {
    await Promise.all([fetchExchangeMargin(), fetchGuardianStatus()]);
  }, [fetchExchangeMargin, fetchGuardianStatus]);

  // Auto-refresh
  useEffect(() => {
    fetchAll();
    if (!autoRefresh) return;
    const interval = setInterval(fetchAll, refreshInterval * 1000);
    return () => clearInterval(interval);
  }, [fetchAll, autoRefresh, refreshInterval]);

  // Toggle guardian defense
  const handleToggleGuardian = async (enabled) => {
    try {
      await mmmService.updateSessionParams(sessionId, {
        margin_monitor_enabled: enabled,
      });
      setTimeout(fetchGuardianStatus, 1000);
    } catch (err) {
      setError(`Failed to ${enabled ? 'enable' : 'disable'} Guardian: ${err.message}`);
    }
  };

  if (!session) return null;

  const utilization = exchangeMargin?.utilization_pct || 0;
  const barColor = getUtilizationColor(utilization);

  return (
    <Box>
      {/* ═══════════════════════════════════════════ */}
      {/* Section 1: Exchange Margin (ALWAYS LIVE)   */}
      {/* ═══════════════════════════════════════════ */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <SpeedIcon sx={{ fontSize: 20, color: barColor }} />
          <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
            Exchange Margin
          </Typography>
          <Chip
            label="LIVE"
            size="small"
            sx={{
              height: 20, fontSize: '0.6rem', fontWeight: 700,
              bgcolor: 'rgba(76,175,80,0.12)', color: '#4caf50',
              animation: loading ? 'pulse 1s infinite' : 'none',
              '@keyframes pulse': {
                '0%, 100%': { opacity: 1 },
                '50%': { opacity: 0.5 },
              },
            }}
          />
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {lastFetchRef.current && (
            <Typography variant="caption" sx={{ fontSize: '0.62rem', color: 'text.disabled' }}>
              {lastFetchRef.current.toLocaleTimeString()}
            </Typography>
          )}
          <Tooltip title="Refresh now">
            <span>
              <Button
                size="small"
                onClick={fetchAll}
                disabled={loading}
                sx={{ minWidth: 32, p: 0.5 }}
              >
                {loading ? <CircularProgress size={16} /> : <RefreshIcon sx={{ fontSize: 16 }} />}
              </Button>
            </span>
          </Tooltip>
        </Box>
      </Box>

      <Typography
        variant="caption"
        sx={{
          display: 'block', color: 'text.secondary', lineHeight: 1.5, mb: 2,
          fontSize: '0.72rem', opacity: 0.75,
        }}
      >
        Real-time margin data from Delta Exchange India — covers ALL positions
        across all algos and manual trades. The exchange is the single source of truth.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {exchangeMargin && (
        <Grid container spacing={2}>
          {/* Utilization gauge */}
          <Grid item xs={12}>
            <UtilizationGauge
              utilization={utilization}
              tier={guardianStatus?.tier || 'GREEN'}
              thresholds={guardianStatus?.thresholds}
            />
          </Grid>

          {/* Wallet breakdown */}
          <Grid item xs={12} md={6}>
            <WalletBreakdown marginData={exchangeMargin.margin_data} />
          </Grid>

          {/* Quick stats */}
          <Grid item xs={12} md={6}>
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, height: '100%' }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.5 }}>
                Quick Stats
              </Typography>
              {[
                {
                  label: 'Margin Used',
                  value: `$${(exchangeMargin.margin_data?.total_margin_used || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
                  sub: `of $${(exchangeMargin.margin_data?.net_equity || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} equity`,
                },
                {
                  label: 'Available',
                  value: `$${(exchangeMargin.margin_data?.available_balance || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
                  sub: `${exchangeMargin.margin_data?.net_equity ? ((exchangeMargin.margin_data.available_balance / exchangeMargin.margin_data.net_equity) * 100).toFixed(1) : 0}% of equity`,
                  color: '#4caf50',
                },
                {
                  label: 'Open Positions',
                  value: exchangeMargin.position_count || 0,
                  sub: 'across all products',
                },
                {
                  label: 'Utilization',
                  value: `${utilization.toFixed(1)}%`,
                  sub: utilization < 50 ? 'Healthy' : utilization < 75 ? 'Moderate' : 'Elevated',
                  color: barColor,
                },
              ].map((stat) => (
                <Box key={stat.label} sx={{ mb: 1.5 }}>
                  <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.68rem' }}>
                    {stat.label}
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={{
                      fontWeight: 700, fontFamily: 'monospace',
                      color: stat.color || 'text.primary',
                    }}
                  >
                    {stat.value}
                  </Typography>
                  <Typography variant="caption" sx={{ fontSize: '0.6rem', color: 'text.disabled' }}>
                    {stat.sub}
                  </Typography>
                </Box>
              ))}
            </Paper>
          </Grid>

          {/* All open positions from exchange */}
          <Grid item xs={12}>
            <PositionsTable positions={exchangeMargin.positions} />
          </Grid>
        </Grid>
      )}

      {!exchangeMargin && loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress size={28} />
        </Box>
      )}

      {/* ═══════════════════════════════════════════════ */}
      {/* Section 2: Guardian Defense (Toggleable)       */}
      {/* ═══════════════════════════════════════════════ */}
      <Divider sx={{ my: 3 }} />

      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <ShieldIcon sx={{ fontSize: 20, color: guardianEnabled ? '#4caf50' : 'text.disabled' }} />
          <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
            Margin Guardian Defense
          </Typography>
          {guardianEnabled ? (
            <Chip label="ACTIVE" size="small" color="success" sx={{ fontWeight: 700, fontSize: '0.65rem', height: 20 }} />
          ) : (
            <Chip label="OFF" size="small" sx={{ fontWeight: 600, fontSize: '0.65rem', height: 20 }} />
          )}
        </Box>

        <FormControlLabel
          control={
            <Switch
              checked={guardianEnabled}
              onChange={(e) => handleToggleGuardian(e.target.checked)}
              size="small"
              color="success"
            />
          }
          label={
            <Typography variant="caption" sx={{ fontSize: '0.7rem' }}>
              {guardianEnabled ? 'Defense Active' : 'Defense Off'}
            </Typography>
          }
          sx={{ mr: 0 }}
        />
      </Box>

      <Typography
        variant="caption"
        sx={{
          display: 'block', color: 'text.secondary', lineHeight: 1.5, mb: 2,
          fontSize: '0.7rem', opacity: 0.75,
        }}
      >
        When enabled, the Guardian automatically defends your positions based on margin
        utilization tiers. Margin data comes from the exchange (same as above).
        Configure thresholds in Settings → Margin Guardian.
      </Typography>

      {!guardianEnabled && (
        <Alert severity="info" sx={{ mb: 2, fontSize: '0.75rem' }}>
          Guardian defense is <strong>off</strong>. Margin is still monitored above,
          but no automatic defensive actions will be taken.
          Enable to activate tier-based protection.
        </Alert>
      )}

      {guardianEnabled && guardianStatus && (
        <Grid container spacing={2}>
          {/* Current tier + headroom */}
          <Grid item xs={12}>
            <Paper
              variant="outlined"
              sx={{
                p: 1.5, borderRadius: 2, display: 'flex', alignItems: 'center',
                gap: 2, flexWrap: 'wrap',
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Typography variant="caption" sx={{ fontWeight: 600, fontSize: '0.72rem' }}>
                  Current Tier:
                </Typography>
                <TierBadge tier={guardianStatus.tier || 'GREEN'} />
              </Box>

              {guardianStatus.headroom_pct != null && guardianStatus.next_threshold != null && (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <TrendingIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
                  <Typography variant="caption" sx={{ fontSize: '0.72rem' }}>
                    <strong>{guardianStatus.headroom_pct.toFixed(1)}%</strong> headroom
                    → next tier at {guardianStatus.next_threshold}%
                  </Typography>
                </Box>
              )}

              {guardianStatus.actions && guardianStatus.actions.length > 0 && (
                <Box sx={{ display: 'flex', gap: 0.5 }}>
                  {guardianStatus.actions.map((action) => (
                    <Chip
                      key={action}
                      label={action.replace(/_/g, ' ')}
                      size="small"
                      variant="outlined"
                      sx={{ fontSize: '0.6rem', height: 18 }}
                    />
                  ))}
                </Box>
              )}
            </Paper>
          </Grid>

          {/* Tier ladder */}
          <Grid item xs={12}>
            <TierLadder
              currentTier={guardianStatus.tier || 'GREEN'}
              thresholds={guardianStatus.thresholds}
              utilization={utilization}
            />
          </Grid>
        </Grid>
      )}

      {/* ═══════════════════════════════════════════════ */}
      {/* Auto-refresh controls                         */}
      {/* ═══════════════════════════════════════════════ */}
      <Divider sx={{ my: 2 }} />
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <FormControlLabel
          control={
            <Switch
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              size="small"
            />
          }
          label={
            <Typography variant="caption" sx={{ fontSize: '0.68rem', color: 'text.secondary' }}>
              Auto-refresh
            </Typography>
          }
        />
        {autoRefresh && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            {[5, 10, 15, 30].map((sec) => (
              <Chip
                key={sec}
                label={`${sec}s`}
                size="small"
                variant={refreshInterval === sec ? 'filled' : 'outlined'}
                color={refreshInterval === sec ? 'primary' : 'default'}
                onClick={() => setRefreshInterval(sec)}
                sx={{ fontSize: '0.6rem', height: 20, cursor: 'pointer' }}
              />
            ))}
          </Box>
        )}
      </Box>
    </Box>
  );
}
