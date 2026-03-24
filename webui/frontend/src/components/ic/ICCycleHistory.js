/**
 * ICCycleHistory — Table of all completed and current cycles
 */
import React, { useState, useCallback, useEffect } from 'react';
import { Box, Typography, Chip } from '@mui/material';
import icService from './icService';

const ICCycleHistory = ({ session }) => {
  const [cycleData, setCycleData] = useState(null);

  const fetchHistory = useCallback(async () => {
    if (!session?.session_id) return;
    try {
      const result = await icService.getCycleHistory(session.session_id);
      if (result.success) setCycleData(result);
    } catch (err) {
      console.error('IC cycle history error:', err);
    }
  }, [session?.session_id]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const history = cycleData?.cycle_history || session?.cycle_history || [];
  const current = cycleData?.current_cycle || session?.current_cycle;
  const totalRealized = cycleData?.total_realized_pnl || session?.total_realized_pnl || 0;

  const allCycles = [];
  if (current) {
    allCycles.push({ ...current, isCurrent: true });
  }
  history.forEach((c) => allCycles.push({ ...c, isCurrent: false }));

  if (allCycles.length === 0) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography color="text.secondary">No cycles yet</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 1 }}>
      <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 700 }}>
        Cycle History
      </Typography>

      {/* Table header */}
      <Box sx={{
        display: 'grid', gridTemplateColumns: '50px 120px 120px 120px 90px 40px',
        gap: 1, px: 1, py: 0.5, borderBottom: '1px solid rgba(255,255,255,0.15)',
        '& > *': { fontSize: '0.7rem', fontWeight: 700, color: 'text.secondary' },
      }}>
        <Typography variant="caption">Cycle</Typography>
        <Typography variant="caption">Opened</Typography>
        <Typography variant="caption">Closed</Typography>
        <Typography variant="caption">Exit Reason</Typography>
        <Typography variant="caption">P&L</Typography>
        <Typography variant="caption">Adj</Typography>
      </Box>

      {/* Rows */}
      {allCycles.map((c, i) => {
        const pnl = c.isCurrent ? (c.unrealized_pnl || 0) : (c.realized_pnl || 0);
        return (
          <Box key={i} sx={{
            display: 'grid', gridTemplateColumns: '50px 120px 120px 120px 90px 40px',
            gap: 1, px: 1, py: 0.75, alignItems: 'center',
            borderBottom: '1px solid rgba(255,255,255,0.06)',
            backgroundColor: c.isCurrent ? 'rgba(33,150,243,0.05)' : 'transparent',
            '&:hover': { backgroundColor: 'rgba(255,255,255,0.03)' },
          }}>
            <Typography variant="caption" sx={{ fontWeight: 700, fontFamily: 'monospace' }}>
              {c.cycle_number || i + 1}
            </Typography>
            <Typography variant="caption" sx={{ fontFamily: 'monospace', fontSize: '0.65rem' }}>
              {c.opened_at ? new Date(c.opened_at).toLocaleDateString() : 'Running...'}
            </Typography>
            <Typography variant="caption" sx={{ fontFamily: 'monospace', fontSize: '0.65rem' }}>
              {c.isCurrent ? '—' : (c.closed_at ? new Date(c.closed_at).toLocaleDateString() : '—')}
            </Typography>
            <Box>
              {c.isCurrent ? (
                <Chip label="Running" size="small" color="success" variant="outlined" sx={{ height: 18, fontSize: '0.6rem' }} />
              ) : (
                <Typography variant="caption" sx={{ fontFamily: 'monospace', fontSize: '0.65rem' }}>
                  {c.exit_reason || '—'}
                </Typography>
              )}
            </Box>
            <Typography variant="caption" sx={{
              fontFamily: 'monospace', fontWeight: 700,
              color: pnl >= 0 ? '#4caf50' : '#f44336',
            }}>
              {pnl >= 0 ? '+' : ''}${pnl.toFixed(4)}{c.isCurrent ? '*' : ''}
            </Typography>
            <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
              {c.adjustment_count || c.roll_events?.length || 0}
            </Typography>
          </Box>
        );
      })}

      {/* Total */}
      <Box sx={{ px: 1, py: 1.5, mt: 1, borderTop: '2px solid rgba(255,255,255,0.15)' }}>
        <Typography variant="caption" sx={{
          fontFamily: 'monospace', fontWeight: 700,
          color: totalRealized >= 0 ? '#4caf50' : '#f44336',
        }}>
          Total realized P&L: {totalRealized >= 0 ? '+' : ''}${totalRealized.toFixed(4)}
          <Typography component="span" variant="caption" color="text.secondary"> (*unrealized)</Typography>
        </Typography>
      </Box>
    </Box>
  );
};

export default ICCycleHistory;
