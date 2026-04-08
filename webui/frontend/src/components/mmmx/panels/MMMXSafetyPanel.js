/**
 * MMMXSafetyPanel — shows all safety-type activity events for the active session.
 * Source: activity array from MMMXContext (type === 'safety').
 */

import React from 'react';
import { Box, Typography, Chip, Paper, Alert } from '@mui/material';
import { useMMMX } from '../MMMXContext';

const LEVEL_SEV = { critical: 'error', warning: 'warning', info: 'info' };

export default function MMMXSafetyPanel() {
  const { activity } = useMMMX();
  const safetyEvents = activity.filter(e => e?.type === 'safety');

  if (!safetyEvents.length) {
    return (
      <Alert severity="success" sx={{ mt: 1 }}>
        No safety events recorded for this session.
      </Alert>
    );
  }

  return (
    <Box>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5, textTransform: 'uppercase', letterSpacing: 0.5, fontWeight: 600 }}>
        {safetyEvents.length} safety event{safetyEvents.length !== 1 ? 's' : ''} — latest first
      </Typography>
      {safetyEvents.map((e, i) => {
        const lvl = String(e.level || '').toLowerCase();
        const sev = LEVEL_SEV[lvl] || 'info';
        return (
          <Paper key={i} variant="outlined" sx={{ p: 1.2, mb: 0.8, borderRadius: 1.2,
            borderColor: sev === 'error' ? 'error.main' : sev === 'warning' ? 'warning.main' : 'divider' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8, mb: 0.4, flexWrap: 'wrap' }}>
              <Chip
                size="small"
                label={e.level || 'info'}
                color={sev === 'error' ? 'error' : sev === 'warning' ? 'warning' : 'info'}
              />
              {e.safety_type && (
                <Chip size="small" variant="outlined" label={e.safety_type} />
              )}
              <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto', fontFamily: 'monospace' }}>
                {e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : '—'}
              </Typography>
            </Box>
            <Typography variant="body2" sx={{ fontSize: '0.82rem' }}>{e.message ?? '—'}</Typography>
            {e.context && (
              <Typography variant="caption" sx={{ display: 'block', mt: 0.3, color: 'text.secondary', fontFamily: 'monospace' }}>
                {typeof e.context === 'string' ? e.context : JSON.stringify(e.context)}
              </Typography>
            )}
          </Paper>
        );
      })}
    </Box>
  );
}
