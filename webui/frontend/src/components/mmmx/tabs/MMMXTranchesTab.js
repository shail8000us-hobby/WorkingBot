import React from 'react';
import { Box, Typography, Chip, Alert, Table, TableHead, TableBody, TableRow, TableCell } from '@mui/material';
import { useMMMX } from '../MMMXContext';
import { fmt, pnlColor } from '../utils/mmmxFormatters';

export default function MMMXTranchesTab() {
  const { tranches } = useMMMX();
  if (!tranches.length)
    return (
      <Alert severity="info" sx={{ mt: 1 }}>
        No tranches deployed yet. Use the <strong>Deploy Tranche 1</strong> button on the Status tab to start.
      </Alert>
    );

  return (
    <Box sx={{ overflow: 'auto' }}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>ID</TableCell><TableCell>Type</TableCell>
            <TableCell>CE Symbol</TableCell><TableCell>CE Strike</TableCell><TableCell>CE Lots</TableCell><TableCell>CE Δ</TableCell>
            <TableCell>PE Symbol</TableCell><TableCell>PE Strike</TableCell><TableCell>PE Lots</TableCell><TableCell>PE Δ</TableCell>
            <TableCell>Premium</TableCell><TableCell>Unrealized</TableCell><TableCell>Status</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {tranches.map(t => (
            <TableRow key={t.tranche_id} hover>
              <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{t.tranche_id}</TableCell>
              <TableCell><Chip label={t.type || 'deploy'} size="small" variant="outlined" /></TableCell>
              <TableCell><Typography variant="caption" sx={{ fontFamily: 'monospace' }}>{t.ce?.symbol ?? '—'}</Typography></TableCell>
              <TableCell>{fmt(t.ce?.strike, 0)}</TableCell>
              <TableCell>{t.ce?.lots ?? '—'}</TableCell>
              <TableCell>{fmt(t.ce?.entry_delta, 3)}</TableCell>
              <TableCell><Typography variant="caption" sx={{ fontFamily: 'monospace' }}>{t.pe?.symbol ?? '—'}</Typography></TableCell>
              <TableCell>{fmt(t.pe?.strike, 0)}</TableCell>
              <TableCell>{t.pe?.lots ?? '—'}</TableCell>
              <TableCell>{fmt(t.pe?.entry_delta, 3)}</TableCell>
              <TableCell sx={{ color: '#4caf50' }}>${fmt(t.premium_collected)}</TableCell>
              <TableCell sx={{ color: pnlColor(t.unrealized_pnl) }}>${fmt(t.unrealized_pnl)}</TableCell>
              <TableCell>
                <Chip label={t.status} size="small"
                  color={t.status === 'ACTIVE' ? 'success' : t.status === 'BEING_CLOSED' ? 'warning' : 'default'} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Box>
  );
}
