import React from 'react';
import { Box, Paper, Typography, Chip, Alert, LinearProgress } from '@mui/material';
import { useMMMX } from '../MMMXContext';
import { WHIPSAW_LABEL, WHIPSAW_COLOR } from '../utils/mmmxConstants';
import { fmt } from '../utils/mmmxFormatters';

export default function MMMXRiskTab() {
  const { risk } = useMMMX();
  const wsScore = risk.whipsaw_score ?? 0;
  const wsLevel = WHIPSAW_LABEL[Math.min(wsScore, 4)] ?? 'COOLDOWN';

  return (
    <Box>
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 2 }}>
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 1.5 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>Portfolio Delta</Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <LinearProgress variant="determinate"
              value={50 + Math.min(50, Math.max(-50, (risk.portfolio_delta ?? 0) * 50))}
              sx={{ flex: 1, height: 10, borderRadius: 1 }}
              color={Math.abs(risk.portfolio_delta ?? 0) > 0.5 ? 'error' : 'primary'} />
            <Typography variant="body2" sx={{ fontFamily: 'monospace', minWidth: 55 }}>
              {fmt(risk.portfolio_delta, 3)}
            </Typography>
          </Box>
        </Paper>

        <Paper variant="outlined" sx={{ p: 2, borderRadius: 1.5 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>Whipsaw Score</Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="h4" sx={{ fontWeight: 700 }}>{wsScore}</Typography>
            <Chip label={wsLevel} color={WHIPSAW_COLOR[wsLevel] || 'default'} size="small" />
          </Box>
        </Paper>
      </Box>

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
        <Chip label={`CB: ${risk.circuit_breaker_state || 'CLOSED'}`}
          color={risk.circuit_breaker_state !== 'CLOSED' ? 'warning' : 'success'} size="small" />
        <Chip label={`Imbalance: ${fmt(risk.imbalance_pct, 1)}%`}
          color={(risk.imbalance_pct ?? 0) > 20 ? 'warning' : 'default'} size="small" />
        {risk.deployment_eligible_tranches?.length > 0 && (
          <Chip label={`Deploy Queue: ${risk.deployment_eligible_tranches.length}`}
            color="info" size="small" />
        )}
      </Box>

      {risk.naked_positions?.length > 0 && (
        <Alert severity="error" sx={{ mb: 2 }}>Naked positions: {risk.naked_positions.join(', ')}</Alert>
      )}

      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1 }}>
        <Paper variant="outlined" sx={{ p: 1, borderRadius: 1.5 }}>
          <Typography variant="caption" color="text.secondary">Last Beat</Typography>
          <Typography variant="body2">
            {risk.last_beat_at ? new Date(risk.last_beat_at).toLocaleTimeString() : '—'}
          </Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 1, borderRadius: 1.5 }}>
          <Typography variant="caption" color="text.secondary">Last Price Update</Typography>
          <Typography variant="body2">
            {risk.last_price_update_at ? new Date(risk.last_price_update_at).toLocaleTimeString() : '—'}
          </Typography>
        </Paper>
      </Box>
    </Box>
  );
}
