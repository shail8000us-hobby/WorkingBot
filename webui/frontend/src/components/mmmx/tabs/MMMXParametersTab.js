import React, { useState, useEffect } from 'react';
import {
  Box, Typography, Button, Alert, CircularProgress, Tooltip, Paper,
  Table, TableHead, TableBody, TableRow, TableCell, TextField,
  Accordion, AccordionSummary, AccordionDetails,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useMMMX } from '../MMMXContext';
import { mmmxService } from '../mmmxService';
import { HOT_RELOAD_ALLOWLIST } from '../utils/mmmxConstants';

function ParamHistory({ sessionId }) {
  const [history, setHistory] = useState([]);
  useEffect(() => {
    mmmxService.getParamHistory(sessionId, 20).then(r => { if (r.ok) setHistory(r.data ?? []); }).catch(() => {});
  }, [sessionId]);

  if (!history.length)
    return <Typography variant="caption" color="text.secondary" sx={{ p: 1, display: 'block' }}>No history.</Typography>;

  return (
    <Box sx={{ p: 1 }}>
      {history.map((h, i) => (
        <Paper key={i} variant="outlined" sx={{ p: 1, mb: 0.5, borderRadius: 1 }}>
          <Typography variant="caption" color="text.secondary">{h.changed_at}</Typography>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
            {JSON.stringify(h.diff)}
          </Typography>
        </Paper>
      ))}
    </Box>
  );
}

export default function MMMXParametersTab({ queueConfirmedAction, runControl }) {
  const { session } = useMMMX();
  const [edits, setEdits] = useState({});
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const params = session?.params ?? {};

  const handleSubmit = () => {
    if (!Object.keys(edits).length) return;
    const patch = {};
    for (const [k, v] of Object.entries(edits)) {
      patch[k] = typeof params[k] === 'number' ? Number(v) : v;
    }
    const apply = async () => {
      setBusy(true);
      try {
        const controlKey = `hot_reload_apply:${session.session_id}`;
        const run = runControl
          ? () => runControl(controlKey, () => mmmxService.hotReloadParams(session.session_id, patch))
          : () => mmmxService.hotReloadParams(session.session_id, patch);
        const res = await run();
        setResult(res);
        if (res?.ok) setEdits({});
      } catch (e) {
        setResult({ ok: false, error: String(e) });
      } finally {
        setBusy(false);
      }
    };
    if (queueConfirmedAction) {
      queueConfirmedAction({
        tier: 'B',
        title: 'Apply hot-reload parameter changes',
        description: `Patching ${Object.keys(patch).length} param(s): ${Object.keys(patch).join(', ')}`,
        run: apply,
      });
    } else {
      apply();
    }
  };

  return (
    <Box>
      <Box sx={{ overflow: 'auto', maxHeight: 400 }}>
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell>Parameter</TableCell><TableCell>Current Value</TableCell><TableCell>Edit</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {Object.entries(params).map(([key, val]) => {
              const editable = HOT_RELOAD_ALLOWLIST.has(key);
              return (
                <TableRow key={key} hover>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      {!editable && (
                        <Tooltip title="Not hot-reloadable — requires session restart">
                          <Typography component="span" sx={{ opacity: 0.4, fontSize: '0.75rem' }}>🔒</Typography>
                        </Tooltip>
                      )}
                      <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>{key}</Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.78rem' }}>
                      {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    {editable && typeof val !== 'boolean' && !Array.isArray(val) && (
                      <TextField size="small" variant="outlined" sx={{ width: 110 }}
                        value={edits[key] ?? ''} placeholder={String(val)}
                        onChange={e => setEdits(p => {
                          const n = { ...p };
                          if (e.target.value === '') delete n[key]; else n[key] = e.target.value;
                          return n;
                        })} />
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Box>

      {Object.keys(edits).length > 0 && (
        <Paper variant="outlined" sx={{ p: 1, mt: 1, borderRadius: 1.5 }}>
          <Typography variant="caption" color="text.secondary">Pending changes:</Typography>
          {Object.entries(edits).map(([k, v]) => (
            <Typography key={k} variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>
              {k}: {String(params[k])} → <b>{String(v)}</b>
            </Typography>
          ))}
        </Paper>
      )}

      <Box sx={{ mt: 1.5, display: 'flex', gap: 1, alignItems: 'center' }}>
        <Button variant="contained" disabled={!Object.keys(edits).length || busy} onClick={handleSubmit}>
          {busy ? <CircularProgress size={16} /> : 'Apply Changes'}
        </Button>
        {Object.keys(edits).length > 0 && (
          <Button variant="text" onClick={() => setEdits({})}>Clear</Button>
        )}
      </Box>

      {result && (
        <Box sx={{ mt: 1 }}>
          {result.ok ? (
            <Alert severity="success">
              Applied: {Object.keys(result.applied ?? {}).join(', ') || 'none'}.
              {Object.keys(result.rejected ?? {}).length > 0 && ` Rejected: ${Object.keys(result.rejected).join(', ')}`}
            </Alert>
          ) : (
            <Alert severity="error">{result.error ?? JSON.stringify(result.rejected)}</Alert>
          )}
        </Box>
      )}

      {session && (
        <Accordion sx={{ mt: 2 }} disableGutters>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="body2">Param Change History</Typography>
          </AccordionSummary>
          <AccordionDetails sx={{ p: 0 }}>
            <ParamHistory sessionId={session.session_id} />
          </AccordionDetails>
        </Accordion>
      )}
    </Box>
  );
}
