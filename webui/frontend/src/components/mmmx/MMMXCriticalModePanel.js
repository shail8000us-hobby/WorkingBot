import React from 'react';
import { Box, Paper, Typography, Chip, Button, Alert } from '@mui/material';
import { formatEta } from './utils/mmmxFormatters';

export default function MMMXCriticalModePanel({
  session,
  incidents = [],
  recommendations = [],
  onFocusIncident,
  onKillSession,
  onKillGlobal,
  onExit,
}) {
  const top = incidents[0];

  return (
    <Box sx={{ p: 2.2 }}>
      <Alert severity="error" sx={{ mb: 1.5 }}>
        <Typography variant="h6" sx={{ fontWeight: 800, mb: 0.4 }}>
          Critical Mode
        </Typography>
        <Typography variant="body2">
          Emergency-only layout is active. Keep actions protection-first until state certainty recovers.
        </Typography>
      </Alert>

      {top ? (
        <Paper variant="outlined" sx={{ p: 1.6, mb: 1.5, borderRadius: 1.5, borderColor: 'error.main' }}>
          <Typography variant="subtitle2" sx={{ mb: 0.6 }}>
            Top Incident · {top.level}
          </Typography>
          {top.escalates_in_sec != null && (
            <Chip size="small" color="warning" label={`Escalates in ${formatEta(top.escalates_in_sec)}`} sx={{ mb: 0.6 }} />
          )}
          <Typography variant="body1" sx={{ fontWeight: 700 }}>{top.title}</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>{top.detail}</Typography>
          {top.recommendedAction && (
            <Typography variant="body2" sx={{ color: 'warning.main' }}>
              Recommended now: {top.recommendedAction}
            </Typography>
          )}
        </Paper>
      ) : (
        <Alert severity="warning" sx={{ mb: 1.5 }}>No incident selected, but critical mode remains manually enabled.</Alert>
      )}

      <Paper variant="outlined" sx={{ p: 1.6, mb: 1.5, borderRadius: 1.5 }}>
        <Typography variant="subtitle2" sx={{ mb: 0.8 }}>Required Actions</Typography>
        {recommendations.length === 0 ? (
          <Typography variant="caption" color="text.secondary">No recommendations available.</Typography>
        ) : (
          recommendations.slice(0, 4).map((r, idx) => (
            <Alert
              key={`${r.priority}-${idx}`}
              severity={r.priority === 'REQUIRED' ? 'error' : 'warning'}
              sx={{ mb: 0.7 }}
            >
              <strong>{r.priority}:</strong> {r.text}
            </Alert>
          ))
        )}
      </Paper>

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
        <Button variant="outlined" color="warning" onClick={() => top && onFocusIncident?.(top)}>
          Focus Top Incident
        </Button>
        <Button variant="outlined" color="error" disabled={!session?.session_id} onClick={onKillSession}>
          Kill Session
        </Button>
        <Button variant="contained" color="error" onClick={onKillGlobal}>
          Global Kill
        </Button>
        <Button variant="text" onClick={onExit}>
          Exit Critical Mode
        </Button>
      </Box>
    </Box>
  );
}
