/**
 * MMMXPerformancePanel — analytics summary derived from session fields.
 * Shows key performance metrics: premium efficiency, fee ratio, beat stats.
 */

import React, { useMemo } from 'react';
import { Box, Paper, Typography, Chip, LinearProgress, Alert } from '@mui/material';
import { useMMMX } from '../MMMXContext';
import { fmt } from '../utils/mmmxFormatters';

function MetricRow({ label, value, sub, color, bar, barPct, barColor }) {
  return (
    <Box sx={{ mb: 1.2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', mb: 0.3 }}>
        <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.72rem' }}>
          {label}
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.6 }}>
          <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: 'monospace', color: color || 'text.primary' }}>
            {value}
          </Typography>
          {sub && (
            <Typography variant="caption" color="text.disabled" sx={{ fontSize: '0.65rem' }}>
              {sub}
            </Typography>
          )}
        </Box>
      </Box>
      {bar && (
        <LinearProgress variant="determinate" value={Math.min(100, barPct || 0)}
          color={barColor || 'primary'} sx={{ height: 4, borderRadius: 1 }} />
      )}
    </Box>
  );
}

export default function MMMXPerformancePanel() {
  const { session, pnlHistory, risk } = useMMMX();

  const stats = useMemo(() => {
    if (!session) return null;

    const premium       = session.total_premium_collected ?? 0;
    const pnl           = session.portfolio_pnl ?? 0;
    const hardStop      = session.hard_stop_usd ?? 0;
    const hedgeCost     = session.total_hedge_cost_paid ?? 0;
    const profitBooked  = session.profit_booked_total ?? 0;
    const beats         = session.beat_number ?? session.beat_count ?? 0;
    const tranches      = session.tranches_deployed ?? 0;
    const ft            = session.fees_tracking ?? {};
    const totalFees     = ft.total_fees_paid ?? 0;

    const netPnl        = pnl - totalFees;
    const premiumUtilPct = hardStop > 0 ? Math.min(100, (Math.abs(pnl) / hardStop) * 100) : 0;
    const feePct        = premium > 0 ? (totalFees / premium) * 100 : 0;
    const hedgePct      = premium > 0 ? (hedgeCost / premium) * 100 : 0;
    const bookingPct    = premium > 0 ? (profitBooked / premium) * 100 : 0;
    const pnlPct        = premium > 0 ? (pnl / premium) * 100 : 0;

    // PnL volatility from history
    let pnlStdDev = null;
    if (pnlHistory.length >= 5) {
      const vals = pnlHistory.map(h => h.pnl);
      const mean = vals.reduce((s, v) => s + v, 0) / vals.length;
      const variance = vals.reduce((s, v) => s + (v - mean) ** 2, 0) / vals.length;
      pnlStdDev = Math.sqrt(variance);
    }

    return {
      premium, pnl, netPnl, hardStop, hedgeCost, profitBooked,
      beats, tranches, totalFees, premiumUtilPct, feePct, hedgePct, bookingPct, pnlPct, pnlStdDev,
    };
  }, [session, pnlHistory]);

  if (!session) return <Typography color="text.secondary">No session loaded.</Typography>;
  if (!stats)   return null;

  const liveStatuses = ['RUNNING', 'PAUSED', 'GATES_PASSED'];

  return (
    <Box>
      {/* Session health overview */}
      <Paper variant="outlined" sx={{ p: 1.8, mb: 2, borderRadius: 1.5 }}>
        <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 700 }}>Session P&amp;L Analytics</Typography>

        <MetricRow label="Premium Collected"    value={`$${fmt(stats.premium)}`} color="#4caf50" />
        <MetricRow label="Portfolio P&L"
          value={`$${fmt(stats.pnl)}`}
          sub={`(${stats.pnlPct.toFixed(1)}% of premium)`}
          color={stats.pnl >= 0 ? '#4caf50' : '#f44336'}
          bar barPct={Math.abs(stats.pnlPct)} barColor={stats.pnl >= 0 ? 'success' : 'error'} />
        <MetricRow label="Net P&L (after fees)" value={`$${fmt(stats.netPnl)}`}
          color={stats.netPnl >= 0 ? '#4caf50' : '#f44336'} />
        <MetricRow label="Profit Booked"        value={`$${fmt(stats.profitBooked)}`}
          sub={`(${stats.bookingPct.toFixed(1)}% of premium)`}
          bar barPct={stats.bookingPct} barColor="info" />
        <MetricRow label="Hedge Cost"           value={`$${fmt(stats.hedgeCost)}`}
          sub={`(${stats.hedgePct.toFixed(1)}% of premium)`}
          color={stats.hedgePct > 20 ? '#ff9800' : undefined}
          bar barPct={stats.hedgePct} barColor="warning" />
        <MetricRow label="Total Fees"           value={`$${fmt(stats.totalFees)}`}
          sub={`(${stats.feePct.toFixed(1)}% of premium)`}
          color={stats.feePct > 10 ? '#f44336' : undefined} />

        {stats.hardStop > 0 && (
          <MetricRow label="Hard Stop Utilisation"
            value={`${stats.premiumUtilPct.toFixed(1)}%`}
            sub={`of $${fmt(stats.hardStop, 0)}`}
            color={stats.premiumUtilPct > 70 ? '#f44336' : stats.premiumUtilPct > 40 ? '#ff9800' : undefined}
            bar barPct={stats.premiumUtilPct}
            barColor={stats.premiumUtilPct > 70 ? 'error' : stats.premiumUtilPct > 40 ? 'warning' : 'success'} />
        )}
      </Paper>

      {/* Operational metrics */}
      <Paper variant="outlined" sx={{ p: 1.8, mb: 2, borderRadius: 1.5 }}>
        <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 700 }}>Operational Metrics</Typography>
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1.2 }}>
          {[
            ['Tranches', `${stats.tranches} / 10`],
            ['Beats',    stats.beats],
            ['WS',       risk.last_beat_at ? new Date(risk.last_beat_at).toLocaleTimeString() : '—'],
            ['Whipsaw',  risk.whipsaw_score ?? 0],
            ['CE Resv',  `${session.ce_reserve_remaining ?? 30} lots`],
            ['PE Resv',  `${session.pe_reserve_remaining ?? 30} lots`],
          ].map(([label, val]) => (
            <Box key={label} sx={{ textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.65rem' }}>{label}</Typography>
              <Typography variant="body2" sx={{ fontWeight: 700, fontFamily: 'monospace' }}>{val}</Typography>
            </Box>
          ))}
        </Box>
      </Paper>

      {/* PnL volatility */}
      {stats.pnlStdDev != null && (
        <Paper variant="outlined" sx={{ p: 1.8, borderRadius: 1.5 }}>
          <Typography variant="subtitle2" sx={{ mb: 0.8, fontWeight: 700 }}>P&amp;L Stability</Typography>
          <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center' }}>
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
              Std dev (last {pnlHistory.length} beats):
            </Typography>
            <Chip size="small" label={`$${fmt(stats.pnlStdDev)}`}
              color={stats.pnlStdDev > Math.abs(stats.pnl) * 0.3 ? 'warning' : 'success'} />
          </Box>
        </Paper>
      )}

      {!liveStatuses.includes(session.status) && (
        <Alert severity="info" sx={{ mt: 2 }}>
          Session is {session.status}. Metrics are final for this session's lifecycle.
        </Alert>
      )}
    </Box>
  );
}
