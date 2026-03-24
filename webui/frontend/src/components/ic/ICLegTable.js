/**
 * ICLegTable — 4-leg position table for Iron Condor
 * Shows LP, SP, SC, LC with entry/mark/P&L per leg
 */
import React from 'react';
import { Box, Typography, Chip } from '@mui/material';

const LEG_META = {
  lp: { label: 'LP', side: 'Put', action: 'Buy', color: '#2196f3' },
  sp: { label: 'SP ★', side: 'Put', action: 'Sell', color: '#f44336' },
  sc: { label: 'SC ★', side: 'Call', action: 'Sell', color: '#f44336' },
  lc: { label: 'LC', side: 'Call', action: 'Buy', color: '#2196f3' },
};

const ICLegTable = ({ cycle, params }) => {
  if (!cycle || !cycle.legs) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography color="text.secondary">No active cycle. Start the session to open a cycle.</Typography>
      </Box>
    );
  }

  const legs = cycle.legs;
  const netCredit = cycle.net_credit || 0;
  const lots = params?.lots || cycle.lots || 0;

  return (
    <Box>
      <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 700 }}>
        Cycle #{cycle.cycle_number} — Leg Positions
      </Typography>

      {/* Table header */}
      <Box sx={{
        display: 'grid', gridTemplateColumns: '60px 60px 50px 90px 80px 80px 90px',
        gap: 1, px: 1, py: 0.5, borderBottom: '1px solid rgba(255,255,255,0.15)',
        '& > *': { fontSize: '0.7rem', fontWeight: 700, color: 'text.secondary' },
      }}>
        <Typography variant="caption">Leg</Typography>
        <Typography variant="caption">Side</Typography>
        <Typography variant="caption">Act</Typography>
        <Typography variant="caption">Strike</Typography>
        <Typography variant="caption">Entry</Typography>
        <Typography variant="caption">Mark</Typography>
        <Typography variant="caption">Leg P&L</Typography>
      </Box>

      {/* Rows */}
      {['lp', 'sp', 'sc', 'lc'].map((legId) => {
        const leg = legs[legId] || {};
        const meta = LEG_META[legId];
        const legPnl = leg.unrealized_pnl || 0;

        return (
          <Box key={legId} sx={{
            display: 'grid', gridTemplateColumns: '60px 60px 50px 90px 80px 80px 90px',
            gap: 1, px: 1, py: 0.75, alignItems: 'center',
            borderBottom: '1px solid rgba(255,255,255,0.06)',
            '&:hover': { backgroundColor: 'rgba(255,255,255,0.03)' },
          }}>
            <Chip label={meta.label} size="small" sx={{
              fontSize: '0.7rem', fontWeight: 700, height: 22,
              backgroundColor: meta.color + '22', color: meta.color,
            }} />
            <Typography variant="caption">{meta.side}</Typography>
            <Typography variant="caption" sx={{ color: meta.action === 'Sell' ? '#f44336' : '#4caf50' }}>
              {meta.action}
            </Typography>
            <Typography variant="caption" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
              ${(leg.strike || 0).toLocaleString()}
            </Typography>
            <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
              ${(leg.entry_price || 0).toFixed(2)}
            </Typography>
            <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
              ${(leg.mark_price || leg.entry_price || 0).toFixed(2)}
            </Typography>
            <Typography variant="caption" sx={{
              fontFamily: 'monospace', fontWeight: 700,
              color: legPnl >= 0 ? '#4caf50' : '#f44336',
            }}>
              {legPnl >= 0 ? '+' : ''}${legPnl.toFixed(4)}
            </Typography>
          </Box>
        );
      })}

      {/* Summary row */}
      <Box sx={{
        display: 'grid', gridTemplateColumns: '1fr 90px',
        px: 1, py: 1, mt: 0.5, borderTop: '2px solid rgba(255,255,255,0.15)',
      }}>
        <Typography variant="caption" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
          Net credit at entry: ${netCredit.toFixed(2)}/BTC × {lots} lots
        </Typography>
        <Typography variant="caption" sx={{
          fontFamily: 'monospace', fontWeight: 700, textAlign: 'right',
          color: (cycle.unrealized_pnl || 0) >= 0 ? '#4caf50' : '#f44336',
        }}>
          {(cycle.unrealized_pnl || 0) >= 0 ? '+' : ''}${(cycle.unrealized_pnl || 0).toFixed(4)}
        </Typography>
      </Box>

      <Typography variant="caption" color="text.secondary" sx={{ ml: 1, mt: 0.5, display: 'block' }}>
        ★ = short leg (risk leg)
      </Typography>
    </Box>
  );
};

export default ICLegTable;
