import React from 'react';
import { Box, Typography, Chip, Table, TableHead, TableBody, TableRow, TableCell } from '@mui/material';
import { useMMMX } from '../MMMXContext';
import { HEDGE_COLOR } from '../utils/mmmxConstants';
import { fmt, pnlColor } from '../utils/mmmxFormatters';

export default function MMMXHedgesTab() {
  const { hedges } = useMMMX();
  if (!hedges.length)
    return <Typography color="text.secondary" sx={{ mt: 1 }}>No hedges executed yet.</Typography>;

  return (
    <Box sx={{ overflow: 'auto' }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Hedge ID</TableCell><TableCell>Parent</TableCell><TableCell>Status</TableCell>
            <TableCell>Premium Paid</TableCell><TableCell>CE P&amp;L</TableCell><TableCell>PE P&amp;L</TableCell>
            <TableCell>Executed At</TableCell><TableCell>Displaced</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {hedges.map(h => (
            <TableRow key={h.hedge_id} hover>
              <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{h.hedge_id}</TableCell>
              <TableCell>{h.parent_tranche_id}</TableCell>
              <TableCell><Chip label={h.status} size="small" color={HEDGE_COLOR[h.status] || 'default'} /></TableCell>
              <TableCell>${fmt(h.hedge_premium_paid)}</TableCell>
              <TableCell sx={{ color: pnlColor(h.ce?.unrealized_pnl) }}>${fmt(h.ce?.unrealized_pnl)}</TableCell>
              <TableCell sx={{ color: pnlColor(h.pe?.unrealized_pnl) }}>${fmt(h.pe?.unrealized_pnl)}</TableCell>
              <TableCell>
                <Typography variant="caption">
                  {h.hedge_executed_at ? new Date(h.hedge_executed_at).toLocaleTimeString() : '—'}
                </Typography>
              </TableCell>
              <TableCell>
                <Typography variant="caption" color={h.displaced_from_parent_at ? 'warning.main' : 'text.disabled'}>
                  {h.displaced_from_parent_at ? new Date(h.displaced_from_parent_at).toLocaleTimeString() : '—'}
                </Typography>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Box>
  );
}
