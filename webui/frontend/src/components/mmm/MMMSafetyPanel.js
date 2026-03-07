/**
 * MMMSafetyPanel — Money Mind & Method
 *
 * Dashboard showing all safety mechanism statuses:
 * - Position cap per side (progress bar)
 * - Adjustments count vs max
 * - Max loss proximity
 * - Asymmetry ratio
 * - Whipsaw status
 * - Expiry countdown with color transitions
 * - Margin availability
 * - Trailing profit vs peak
 *
 * Maps to MONEY_POWER_CALCULATION_LOGIC.md §13, §14
 *
 * Created: February 15, 2026
 */

import React, { useMemo } from 'react';
import {
  Box,
  Typography,
  Grid,
  Paper,
  LinearProgress,
  Chip,
  Tooltip,
} from '@mui/material';
import {
  CheckCircle as OKIcon,
  Warning as WarnIcon,
  Error as AlertIcon,
} from '@mui/icons-material';

function getStatusIcon(level) {
  if (level === 'ok') return <OKIcon sx={{ fontSize: 16, color: '#4caf50' }} />;
  if (level === 'warning') return <WarnIcon sx={{ fontSize: 16, color: '#ff9800' }} />;
  return <AlertIcon sx={{ fontSize: 16, color: '#f44336' }} />;
}

function getBarColor(ratio) {
  if (ratio >= 0.8) return '#f44336';
  if (ratio >= 0.5) return '#ff9800';
  return '#4caf50';
}

function getDeltaLevel(absDelta) {
  if (absDelta >= 0.5) return 'alert';
  if (absDelta >= 0.3) return 'warning';
  return 'ok';
}

function getDeltaColor(absDelta) {
  if (absDelta >= 0.5) return '#f44336';
  if (absDelta >= 0.3) return '#ff9800';
  return '#4caf50';
}

function SafetyIndicator({
  label,
  value,
  maxValue,
  displayText,
  level = 'ok',
  showBar = true,
  tooltip = '',
}) {
  const ratio = maxValue > 0 ? Math.min(value / maxValue, 1) : 0;
  const barColor = getBarColor(ratio);

  return (
    <Tooltip title={tooltip} placement="top">
      <Paper
        variant="outlined"
        sx={{
          p: 1.5,
          borderRadius: 2,
          borderColor: level === 'ok' ? 'divider' : level === 'warning' ? '#ff980040' : '#f4433640',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5 }}>
          <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.secondary' }}>
            {label}
          </Typography>
          {getStatusIcon(level)}
        </Box>

        {showBar && maxValue > 0 && (
          <LinearProgress
            variant="determinate"
            value={ratio * 100}
            sx={{
              height: 6,
              borderRadius: 3,
              mb: 0.5,
              bgcolor: 'action.hover',
              '& .MuiLinearProgress-bar': { bgcolor: barColor, borderRadius: 3 },
            }}
          />
        )}

        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600, fontSize: '0.88rem' }}>
          {displayText}
        </Typography>
      </Paper>
    </Tooltip>
  );
}

function getExpiryColor(minutes) {
  if (minutes <= 5) return '#f44336';
  if (minutes <= 15) return '#ff9800';
  if (minutes <= 60) return '#ffc107';
  return '#4caf50';
}

function getExpiryLevel(minutes) {
  if (minutes <= 5) return 'alert';
  if (minutes <= 15) return 'warning';
  return 'ok';
}

function formatExpiry(minutes) {
  if (minutes == null) return '--';
  if (minutes < 1) return '< 1m';
  if (minutes < 60) return `${Math.floor(minutes)}m`;
  const hrs = Math.floor(minutes / 60);
  const mins = Math.floor(minutes % 60);
  return `${hrs}h ${mins}m`;
}

export default function MMMSafetyPanel({ session, safetyEvents = [], minutesToExpiry = null }) {
  if (!session) return null;

  const params = session.params || {};
  const maxLots = params.max_lots_per_side || 100;
  const maxAdj = params.max_adjustments || 30;
  const maxLoss = params.max_loss_amount || 5000;
  const trailingPct = params.trailing_stop_pct || 0.5;

  // Split Ledger: show active vs total
  const ceLots = session.ce?.active_lots ?? session.ce?.total_lots ?? 0;
  const peLots = session.pe?.active_lots ?? session.pe?.total_lots ?? 0;
  const ceTotalLots = session.ce?.total_lots || 0;
  const peTotalLots = session.pe?.total_lots || 0;
  const ceFrozenLots = session.ce?.frozen_total_lots || 0;
  const peFrozenLots = session.pe?.frozen_total_lots || 0;
  const maxTotalExposure = params.max_total_exposure > 0 ? params.max_total_exposure : maxLots * 2;
  const adjCount = session.adjustment_count || 0;
  const realized = session.realized_pnl || 0;
  const unrealized = session.unrealized_pnl || 0;
  const totalPnl = realized + unrealized;
  const peakPnl = session.peak_pnl || 0;

  // Portfolio Delta (monitoring only)
  const portfolioDelta = session.portfolio_delta || 0;
  const absDelta = Math.abs(portfolioDelta);

  // Asymmetry — use total_lots (matches backend check_asymmetry which tracks full exposure)
  const maxSideLots = Math.max(ceTotalLots, peTotalLots);
  const minSideLots = Math.max(Math.min(ceTotalLots, peTotalLots), 1);
  const asymmetryRatio = maxSideLots / minSideLots;

  // M3: Rebalancing active flag
  const rebalancingActive = (params.rebalance_enabled !== false)
    && asymmetryRatio > (params.rebalance_asymmetry_threshold || 5.0)
    && (maxSideLots / Math.max(maxLots, 1)) > (params.rebalance_pressure_threshold || 0.8);

  // Loss ratio
  const lossRatio = totalPnl < 0 ? Math.abs(totalPnl) / maxLoss : 0;

  // Trailing
  const trailingFloor = peakPnl * trailingPct;
  const trailingStatus = peakPnl > 0 && totalPnl < trailingFloor ? 'warning' : 'ok';

  // Active safety alerts
  const criticalEvents = safetyEvents.filter((e) => e.level === 'critical');
  const warningEvents = safetyEvents.filter((e) => e.level === 'warning' || e.level === 'alert');

  return (
    <Box>
      {/* Section explainer */}
      <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary', lineHeight: 1.5, mb: 1.5, fontStyle: 'italic', fontSize: '0.78rem', opacity: 0.75 }}>
        💡 Safety mechanisms protect your positions from extreme scenarios. Each indicator shows how close you are to a limit — green is safe, yellow is approaching, red means the limit has been reached and the algo will pause or alert you. Hover over any indicator for details.
      </Typography>

      {/* Critical alerts */}
      {criticalEvents.length > 0 && (
        <Box sx={{ mb: 2 }}>
          {criticalEvents.map((e, i) => (
            <Paper
              key={i}
              sx={{
                p: 1.5,
                mb: 1,
                bgcolor: 'rgba(244,67,54,0.1)',
                border: '1px solid #f44336',
                borderRadius: 2,
              }}
            >
              <Typography variant="body2" sx={{ color: '#f44336', fontWeight: 600 }}>
                ⚠️ {e.message}
              </Typography>
            </Paper>
          ))}
        </Box>
      )}

      <Grid container spacing={1.5}>
        {/* Position Cap CE — Split Ledger: active vs cap, total shown in tooltip */}
        <Grid item xs={6} sm={4} md={3}>
          <SafetyIndicator
            label="CE Active"
            value={ceLots}
            maxValue={maxLots}
            displayText={ceFrozenLots > 0
              ? `${ceLots} / ${maxLots} (+${ceFrozenLots} frozen)`
              : `${ceLots} / ${maxLots}`}
            level={ceLots >= maxLots ? 'alert' : ceLots >= maxLots * 0.8 ? 'warning' : 'ok'}
            tooltip={`CE active lots vs cap (${maxLots}). Active lots count against the position cap — frozen (shifted) lots do not. ${ceFrozenLots > 0 ? `${ceFrozenLots} frozen lots are being tracked separately; total exposure is ${ceTotalLots}/${maxTotalExposure}.` : 'No frozen lots currently.'}`}
          />
        </Grid>

        {/* Position Cap PE — Split Ledger: active vs cap */}
        <Grid item xs={6} sm={4} md={3}>
          <SafetyIndicator
            label="PE Active"
            value={peLots}
            maxValue={maxLots}
            displayText={peFrozenLots > 0
              ? `${peLots} / ${maxLots} (+${peFrozenLots} frozen)`
              : `${peLots} / ${maxLots}`}
            level={peLots >= maxLots ? 'alert' : peLots >= maxLots * 0.8 ? 'warning' : 'ok'}
            tooltip={`PE active lots vs cap (${maxLots}). Active lots count against the position cap — frozen (shifted) lots do not. ${peFrozenLots > 0 ? `${peFrozenLots} frozen lots are being tracked separately; total exposure is ${peTotalLots}/${maxTotalExposure}.` : 'No frozen lots currently.'}`}
          />
        </Grid>

        {/* Adjustments */}
        <Grid item xs={6} sm={4} md={3}>
          <SafetyIndicator
            label="Adjustments"
            value={adjCount}
            maxValue={maxAdj}
            displayText={`${adjCount} / ${maxAdj}`}
            level={adjCount >= maxAdj ? 'alert' : adjCount >= maxAdj * 0.8 ? 'warning' : 'ok'}
            tooltip="How many times the algo has sold opposite-side lots to cover losses. If this hits the max, the algo stops adjusting — it may mean the market is too volatile for this strategy."
          />
        </Grid>

        {/* Max Loss */}
        <Grid item xs={6} sm={4} md={3}>
          <SafetyIndicator
            label="Max Loss"
            value={totalPnl < 0 ? Math.abs(totalPnl) : 0}
            maxValue={maxLoss}
            displayText={`$${Math.abs(totalPnl).toFixed(0)} / $${maxLoss}`}
            level={lossRatio >= 1 ? 'alert' : lossRatio >= 0.8 ? 'warning' : 'ok'}
            tooltip="If your total P&L drops below the max loss amount, ALL positions are immediately closed. This is your last line of defense against extreme moves like flash crashes."
          />
        </Grid>

        {/* Asymmetry */}
        <Grid item xs={6} sm={4} md={3}>
          <SafetyIndicator
            label="Asymmetry"
            value={asymmetryRatio}
            maxValue={5}
            displayText={`${asymmetryRatio.toFixed(1)}:1${rebalancingActive ? ' ⚖ M3' : ''}`}
            level={asymmetryRatio >= 5 ? 'alert' : asymmetryRatio >= 3 ? 'warning' : 'ok'}
            tooltip={`CE has ${ceTotalLots} lots (${ceLots} active + ${ceFrozenLots} frozen), PE has ${peTotalLots} lots (${peLots} active + ${peFrozenLots} frozen). Ratio: ${asymmetryRatio.toFixed(1)}:1. Above 3:1 is concerning, above 5:1 is dangerous.${rebalancingActive ? ' ⚖ M3 rebalancing active — harvest thresholds relaxed on dominant side.' : ''}`}
          />
        </Grid>

        {/* Whipsaw */}
        <Grid item xs={6} sm={4} md={3}>
          <SafetyIndicator
            label="Whipsaw"
            value={0}
            maxValue={params.whipsaw_limit || 3}
            displayText={`0 / ${params.whipsaw_limit || 3}`}
            level="ok"
            tooltip="Whipsaw = market oscillating rapidly, causing alternating adjustments (CE→PE→CE). If 3 alternating adjustments happen in a row, the algo detects the choppy market and pauses. This prevents burning premium on trading fees in sideways conditions."
          />
        </Grid>

        {/* Expiry */}
        <Grid item xs={6} sm={4} md={3}>
          <SafetyIndicator
            label="Expiry"
            value={minutesToExpiry != null ? Math.max(0, 480 - minutesToExpiry) : 0}
            maxValue={480}
            displayText={formatExpiry(minutesToExpiry)}
            level={getExpiryLevel(minutesToExpiry || 999)}
            tooltip="Time remaining until the options expire. The algo stops adjustments 15 min before expiry (let theta do the work) and auto-closes everything 5 min before. Both thresholds are configurable in Settings."
          />
        </Grid>

        {/* Trailing Profit */}
        <Grid item xs={6} sm={4} md={3}>
          <SafetyIndicator
            label="Trailing"
            value={peakPnl > 0 ? peakPnl - totalPnl : 0}
            maxValue={peakPnl > 0 ? peakPnl - trailingFloor : 1}
            displayText={peakPnl > 0
              ? `Peak $${peakPnl.toFixed(0)} | ${((totalPnl / peakPnl) * 100).toFixed(0)}%`
              : 'No peak'
            }
            level={trailingStatus}
            tooltip={peakPnl > 0
              ? `Peak reached $${peakPnl.toFixed(0)}. Current P&L: $${totalPnl.toFixed(0)}. Floor: $${trailingFloor.toFixed(0)}. If P&L drops below the floor (${(trailingPct * 100).toFixed(0)}% of peak), the algo alerts you to protect profits.`
              : 'Once you become profitable, the algo tracks your highest P&L. If P&L drops below 50% of that peak, it alerts you — protecting profits from giving back too much.'
            }
          />
        </Grid>

        {/* Portfolio Delta */}
        <Grid item xs={6} sm={4} md={3}>
          <SafetyIndicator
            label="Portfolio Δ"
            value={absDelta}
            maxValue={0.5}
            displayText={portfolioDelta >= 0 
              ? `+${portfolioDelta.toFixed(3)} (Long)` 
              : `${portfolioDelta.toFixed(3)} (Short)`
            }
            level={getDeltaLevel(absDelta)}
            tooltip={`Portfolio delta measures your directional exposure to BTC price movement. Positive = net long (profit when BTC rises), negative = net short (profit when BTC falls). Green: |Δ| < 0.3 (well-balanced), Yellow: 0.3-0.5 (moderate exposure), Red: > 0.5 (high directional risk). This is for monitoring only — no auto-adjustments are made.`}
          />
        </Grid>
      </Grid>
    </Box>
  );
}
