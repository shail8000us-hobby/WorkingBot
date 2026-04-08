/**
 * MMMXFeesCapitalPanel — fees_tracking stats and budget utilisation.
 * All data sourced from session.fees_tracking.* and session.params.*
 */

import React from 'react';
import { Box, Paper, Typography, LinearProgress, Alert } from '@mui/material';
import { useMMMX } from '../MMMXContext';
import { fmt } from '../utils/mmmxFormatters';

function StatBox({ label, value, sub, color }) {
  return (
    <Paper variant="outlined" sx={{ p: 1.2, borderRadius: 1.5, textAlign: 'center' }}>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.68rem', mb: 0.3 }}>
        {label}
      </Typography>
      <Typography variant="body1" sx={{ fontWeight: 700, color: color || 'text.primary' }}>
        {value}
      </Typography>
      {sub && (
        <Typography variant="caption" color="text.disabled" sx={{ display: 'block', fontSize: '0.65rem' }}>
          {sub}
        </Typography>
      )}
    </Paper>
  );
}

export default function MMMXFeesCapitalPanel() {
  const { session } = useMMMX();

  if (!session) return <Typography color="text.secondary">No session loaded.</Typography>;

  const ft = session.fees_tracking ?? {};
  const params = session.params ?? {};

  const totalFees   = ft.total_fees_paid ?? 0;
  const makerFees   = ft.total_maker_fees ?? 0;
  const takerFees   = ft.total_taker_fees ?? 0;
  const feeRateMkr  = ft.fee_rate_maker ?? 0;
  const feeRateTkr  = ft.fee_rate_taker ?? 0;
  const lastFee     = ft.last_fee_charge;

  const premium = session.total_premium_collected ?? 0;
  const pnl     = session.portfolio_pnl ?? 0;
  const hardStop = session.hard_stop_usd ?? 0;

  const budgetLots = params.total_budget_lots ?? 0;
  const deployedLots = (session.tranches_deployed ?? 0) * (params.lots_per_tranche ?? 0);
  const budgetUtilPct = budgetLots > 0 ? Math.min(100, (deployedLots / budgetLots) * 100) : 0;

  const feeToPremiaPct = premium > 0 ? (totalFees / premium) * 100 : 0;
  const netPnl = pnl - totalFees;

  return (
    <Box>
      {!Object.keys(ft).length && (
        <Alert severity="info" sx={{ mb: 2 }}>
          No fees data yet. Fees are tracked after the first order execution.
        </Alert>
      )}

      <Typography variant="caption" sx={{ display: 'block', mb: 1.5, fontWeight: 700, textTransform: 'uppercase',
        letterSpacing: 0.5, color: 'text.secondary', fontSize: '0.68rem' }}>
        Fees Summary
      </Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1.2, mb: 2 }}>
        <StatBox label="Total Fees Paid" value={`$${fmt(totalFees)}`} color={totalFees > 0 ? '#f44336' : undefined} />
        <StatBox label="Maker Fees" value={`$${fmt(makerFees)}`}
          sub={`rate: ${(feeRateMkr * 100).toFixed(3)}%`} />
        <StatBox label="Taker Fees" value={`$${fmt(takerFees)}`}
          sub={`rate: ${(feeRateTkr * 100).toFixed(3)}%`} />
        <StatBox label="Premium Collected" value={`$${fmt(premium)}`} color="#4caf50" />
        <StatBox label="Fees / Premium" value={`${feeToPremiaPct.toFixed(1)}%`}
          color={feeToPremiaPct > 10 ? '#f44336' : feeToPremiaPct > 5 ? '#ff9800' : '#4caf50'} />
        <StatBox label="Net P&L (after fees)" value={`$${fmt(netPnl)}`}
          color={netPnl >= 0 ? '#4caf50' : '#f44336'} />
      </Box>

      {lastFee && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2, fontFamily: 'monospace' }}>
          Last fee charge: {new Date(lastFee).toLocaleString()}
        </Typography>
      )}

      <Typography variant="caption" sx={{ display: 'block', mb: 1.5, fontWeight: 700, textTransform: 'uppercase',
        letterSpacing: 0.5, color: 'text.secondary', fontSize: '0.68rem' }}>
        Capital Utilisation
      </Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 1.2, mb: 2 }}>
        <StatBox label="Hard Stop USD" value={`$${fmt(hardStop, 0)}`} />
        <StatBox label="Portfolio P&L" value={`$${fmt(pnl)}`}
          color={pnl >= 0 ? '#4caf50' : '#f44336'} />
        <StatBox label="CE Reserve" value={`${session.ce_reserve_remaining ?? 30} lots`} />
        <StatBox label="PE Reserve" value={`${session.pe_reserve_remaining ?? 30} lots`} />
      </Box>

      {budgetLots > 0 && (
        <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 1.5 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
            <Typography variant="body2">Budget Utilisation</Typography>
            <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
              {budgetUtilPct.toFixed(0)}% · {session.tranches_deployed ?? 0} / 10 tranches
            </Typography>
          </Box>
          <LinearProgress variant="determinate" value={budgetUtilPct}
            color={budgetUtilPct > 80 ? 'warning' : 'primary'}
            sx={{ height: 6, borderRadius: 1 }} />
        </Paper>
      )}
    </Box>
  );
}
