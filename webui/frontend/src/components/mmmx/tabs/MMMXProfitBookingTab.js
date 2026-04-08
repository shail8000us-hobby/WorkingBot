import React, { useState } from 'react';
import {
  Box, Typography, Chip, Button, Alert, CircularProgress,
  Table, TableHead, TableBody, TableRow, TableCell,
  FormControl, Select, MenuItem,
} from '@mui/material';
import { useMMMX } from '../MMMXContext';
import { mmmxService } from '../mmmxService';
import { fmt, pnlColor } from '../utils/mmmxFormatters';

export default function MMMXProfitBookingTab({ queueConfirmedAction }) {
  const { tranches, session } = useMMMX();
  const [targets, setTargets] = useState({});
  const [msgs, setMsgs] = useState({});
  const [pendingBook, setPendingBook] = useState({});
  const active = tranches.filter(t => t.status === 'ACTIVE');

  const handleBook = (trancheId) => {
    const pct = Number(targets[trancheId] || 20);
    const tranche = tranches.find(t => t.tranche_id === trancheId);
    const apply = async () => {
      setPendingBook(p => ({ ...p, [trancheId]: true }));
      try {
        const res = await mmmxService.profitBook(session.session_id, trancheId, pct);
        setMsgs(m => ({ ...m, [trancheId]: res.ok ? '✓ Queued' : (res.error ?? 'Failed') }));
      } catch (e) {
        setMsgs(m => ({ ...m, [trancheId]: String(e) }));
      } finally {
        setPendingBook(p => ({ ...p, [trancheId]: false }));
      }
    };
    if (queueConfirmedAction) {
      queueConfirmedAction({
        tier: 'B',
        title: `Book profit — Tranche ${trancheId}`,
        description: `Book ${pct}% profit target for tranche ${trancheId}. Premium: $${fmt(tranche?.premium_collected)}, Unrealized: $${fmt(tranche?.unrealized_pnl)}.`,
        run: apply,
      });
    } else {
      apply();
    }
  };

  if (!active.length)
    return (
      <Alert severity="info" sx={{ mt: 1 }}>
        No active tranches available for profit booking.
        Deploy tranches and wait for them to become ACTIVE.
      </Alert>
    );

  return (
    <Table size="small">
      <TableHead>
        <TableRow>
          <TableCell>Tranche</TableCell><TableCell>Type</TableCell>
          <TableCell>Premium</TableCell><TableCell>Unrealized</TableCell>
          <TableCell>Target %</TableCell><TableCell>Action</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {active.map(t => (
          <TableRow key={t.tranche_id}>
            <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{t.tranche_id}</TableCell>
            <TableCell><Chip label={t.type || 'deploy'} size="small" variant="outlined" /></TableCell>
            <TableCell>${fmt(t.premium_collected)}</TableCell>
            <TableCell sx={{ color: pnlColor(t.unrealized_pnl) }}>${fmt(t.unrealized_pnl)}</TableCell>
            <TableCell>
              <FormControl size="small" sx={{ minWidth: 80 }}>
                <Select value={targets[t.tranche_id] || 20}
                  onChange={e => setTargets(p => ({ ...p, [t.tranche_id]: e.target.value }))}>
                  {[10, 20, 30, 50].map(v => <MenuItem key={v} value={v}>{v}%</MenuItem>)}
                </Select>
              </FormControl>
            </TableCell>
            <TableCell>
              <Button size="small" variant="contained"
                disabled={!!pendingBook[t.tranche_id]}
                onClick={() => handleBook(t.tranche_id)}>
                {pendingBook[t.tranche_id] ? <CircularProgress size={14} color="inherit" /> : 'Book Now'}
              </Button>
              {msgs[t.tranche_id] && (
                <Typography variant="caption" sx={{ ml: 1,
                  color: msgs[t.tranche_id].startsWith('✓') ? 'success.main' : 'error.main' }}>
                  {msgs[t.tranche_id]}
                </Typography>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
