import React, { useState } from 'react';
import {
  Box, Typography, Button, Chip, Alert, CircularProgress, Tooltip,
  Table, TableHead, TableBody, TableRow, TableCell,
} from '@mui/material';
import { useMMMX } from '../MMMXContext';
import { mmmxService } from '../mmmxService';

export default function MMMXReconcileTab({ queueConfirmedAction }) {
  const { session } = useMMMX();
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  const runRecon = async () => {
    if (!session) return;
    setBusy(true); setMsg('');
    try {
      const res = await mmmxService.reconcile(session.session_id);
      if (res.ok) setReport(res.data); else setMsg(res.error || 'Failed');
    } catch (e) { setMsg(String(e)); }
    finally { setBusy(false); }
  };

  const applyAction = (divId, action, symbol) => {
    if (!session) return;
    const tier = action === 'accept_db' ? 'B' : 'C';
    const TIER_C_PHRASES = {
      accept_exchange: `ACCEPT EXCHANGE ${(symbol || '').slice(0, 8)}`,
      manual_close: `MANUAL CLOSE ${(symbol || '').slice(0, 8)}`,
    };
    const typedPhrase = tier === 'C' ? TIER_C_PHRASES[action] : '';
    const run = async () => {
      setBusy(true); setMsg('');
      try {
        const res = await mmmxService.confirmReconcile(session.session_id, divId, action);
        setMsg(res.ok ? `✓ Action "${action}" applied` : (res.error || 'Failed'));
        if (res.ok) setReport(null);
      } catch (e) { setMsg(String(e)); }
      finally { setBusy(false); }
    };
    if (queueConfirmedAction) {
      queueConfirmedAction({ tier, title: `Reconcile: ${action}`, description: `Apply "${action}" to divergence ${divId}`, typedPhrase, run });
    } else {
      run();
    }
  };

  if (!session) return <Typography color="text.secondary">No session loaded.</Typography>;

  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 1, mb: 2, alignItems: 'center' }}>
        <Button variant="contained" onClick={runRecon} disabled={busy}>
          {busy ? <CircularProgress size={16} /> : 'Run Reconciliation'}
        </Button>
        {msg && (
          <Typography variant="body2" sx={{ color: msg.startsWith('✓') ? 'success.main' : 'error.main' }}>
            {msg}
          </Typography>
        )}
      </Box>

      {report && (
        <Box>
          <Box sx={{ display: 'flex', gap: 1, mb: 1.5, alignItems: 'center' }}>
            <Chip label={report.ok ? '✓ Clean — no divergences' : `${report.divergences?.length ?? 0} divergence(s)`}
              color={report.ok ? 'success' : 'error'} />
            {report.checked_at && (
              <Typography variant="caption" color="text.secondary">
                {report.checked_at.slice(0, 19).replace('T', ' ')} UTC
              </Typography>
            )}
          </Box>
          {report.notes && <Typography variant="body2" sx={{ mb: 1 }}>{report.notes}</Typography>}
          {report.divergences?.length > 0 && (
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Type</TableCell><TableCell>Symbol</TableCell>
                  <TableCell>Tranche</TableCell><TableCell>Leg</TableCell><TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {report.divergences.map((d, i) => {
                  const divId = `${d.symbol}:${d.tranche_id}:${d.leg}`;
                  return (
                    <TableRow key={i} hover>
                      <TableCell>{d.type}</TableCell>
                      <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{d.symbol ?? '—'}</TableCell>
                      <TableCell>{d.tranche_id ?? '—'}</TableCell>
                      <TableCell>{d.leg ?? '—'}</TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', gap: 0.5 }}>
                          <Tooltip title="DB state is correct — keep it (Tier B confirm)">
                            <Button size="small" variant="outlined" disabled={busy}
                              onClick={() => applyAction(divId, 'accept_db', d.symbol)}>Accept DB</Button>
                          </Tooltip>
                          <Tooltip title="Force DB to match exchange — DESTRUCTIVE (Tier C)">
                            <Button size="small" variant="outlined" color="warning" disabled={busy}
                              onClick={() => applyAction(divId, 'accept_exchange', d.symbol)}>Accept Exchange</Button>
                          </Tooltip>
                          <Tooltip title="Mark for manual close on exchange — DESTRUCTIVE (Tier C)">
                            <Button size="small" variant="outlined" color="error" disabled={busy}
                              onClick={() => applyAction(divId, 'manual_close', d.symbol)}>Manual Close</Button>
                          </Tooltip>
                        </Box>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </Box>
      )}
    </Box>
  );
}
