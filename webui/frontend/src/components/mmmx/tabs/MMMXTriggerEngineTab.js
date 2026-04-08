import React from 'react';
import { Box, Paper, Typography, Chip, Alert } from '@mui/material';
import { useMMMX } from '../MMMXContext';

export default function MMMXTriggerEngineTab() {
  const { risk } = useMMMX();
  const triggerWinner = risk.trigger_winner;
  const triggerRows = Array.isArray(risk.trigger_ladder) ? risk.trigger_ladder : [];

  return (
    <Box>
      {triggerWinner ? (
        <Alert
          severity={triggerWinner.severity === 'critical' ? 'error' : 'warning'}
          sx={{ mb: 1.5 }}
        >
          <strong>Winner: {triggerWinner.trigger_name}</strong>
          {triggerWinner.reason ? ` — ${triggerWinner.reason}` : ''}
        </Alert>
      ) : (
        <Alert severity="info" sx={{ mb: 1.5 }}>No trigger winner on latest beat.</Alert>
      )}

      <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 1.5 }}>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>Priority Ladder Explanation</Typography>
        {!triggerRows.length ? (
          <Typography variant="caption" color="text.secondary">
            Trigger ladder payload missing for this beat. Explanation confidence is reduced.
          </Typography>
        ) : (
          <Box sx={{ maxHeight: 360, overflow: 'auto' }}>
            {triggerRows.map((row, idx) => {
              const status = String(row?.status || 'UNKNOWN').toUpperCase();
              const color = status === 'FIRED' ? 'success'
                : status === 'NOT_MET' ? 'default'
                : status.includes('BLOCK') ? 'warning'
                : 'default';

              return (
                <Paper key={`${row.trigger_name || 'row'}-${idx}`} variant="outlined" sx={{ p: 1, mb: 0.8, borderRadius: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8, flexWrap: 'wrap' }}>
                    <Chip size="small" variant="outlined" label={`P${row.priority ?? idx + 1}`} />
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 700 }}>
                      {row.trigger_name || 'UNKNOWN_TRIGGER'}
                    </Typography>
                    <Chip size="small" color={color} label={status} />
                    {row.excluded_by && (
                      <Chip size="small" variant="outlined" color="warning" label={`Excluded by ${row.excluded_by}`} />
                    )}
                    <Typography variant="caption" sx={{ ml: 'auto', color: 'text.secondary' }}>
                      threshold={row.threshold ?? '—'} value={row.value ?? '—'}
                    </Typography>
                  </Box>
                  {(row.reason || row.note) && (
                    <Typography variant="caption" sx={{ display: 'block', mt: 0.4, color: 'text.secondary' }}>
                      {row.reason || row.note}
                    </Typography>
                  )}
                  {row?.data?.would_status && (
                    <Typography variant="caption" sx={{ display: 'block', mt: 0.2, color: 'warning.main' }}>
                      would_status={row.data.would_status}
                    </Typography>
                  )}
                </Paper>
              );
            })}
          </Box>
        )}
      </Paper>
    </Box>
  );
}
