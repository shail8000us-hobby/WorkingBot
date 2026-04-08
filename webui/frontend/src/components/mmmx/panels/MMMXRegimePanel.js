/**
 * MMMXRegimePanel — Whipsaw state machine + ATM shield event trail.
 *
 * Whipsaw: derives level from session._whipsaw_score (flat int) using params thresholds.
 * ATM shield: reads session.shield_event_history (list) and session.shield_fire_count (int).
 */

import React from 'react';
import { Box, Paper, Typography, Chip, Alert, LinearProgress } from '@mui/material';
import { useMMMX } from '../MMMXContext';
import { WHIPSAW_COLOR } from '../utils/mmmxConstants';
import { deriveWhipsawLevel } from '../utils/mmmxFormatters';

const WHIPSAW_LEVEL_DESC = {
  NORMAL:   { color: '#4caf50', desc: 'Normal trading conditions — all tranches eligible.' },
  CAUTION:  { color: '#ff9800', desc: 'Elevated noise — deployment pacing reduced.' },
  RESTRICT: { color: '#f44336', desc: 'High volatility — only protection actions allowed.' },
  COOLDOWN: { color: '#d32f2f', desc: 'Cooldown active — all deployments blocked until score decays.' },
};

export default function MMMXRegimePanel() {
  const { session } = useMMMX();

  if (!session) return <Typography color="text.secondary">No session loaded.</Typography>;

  const wsScore = session._whipsaw_score ?? 0;
  const params  = session.params ?? {};
  const wsLevel = deriveWhipsawLevel(wsScore, params);
  const wsDesc  = WHIPSAW_LEVEL_DESC[wsLevel] || WHIPSAW_LEVEL_DESC.NORMAL;

  const shieldHistory = session.shield_event_history ?? [];
  const shieldFires   = session.shield_fire_count ?? 0;
  const skipUntil     = session._whipsaw_skip_until;

  const cooldownScore  = params.whipsaw_cooldown_score ?? 4;
  const scorePct       = Math.min(100, (wsScore / cooldownScore) * 100);

  return (
    <Box>
      {/* ── Whipsaw state ── */}
      <Paper variant="outlined" sx={{ p: 1.8, mb: 2, borderRadius: 1.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.2 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>Whipsaw State Machine</Typography>
          <Chip label={wsLevel} color={WHIPSAW_COLOR[wsLevel] || 'default'} size="small" />
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
          <Typography variant="h3" sx={{ fontWeight: 800, color: wsDesc.color, lineHeight: 1 }}>
            {wsScore}
          </Typography>
          <Box sx={{ flex: 1 }}>
            <LinearProgress variant="determinate" value={scorePct}
              color={wsLevel === 'NORMAL' ? 'success' : wsLevel === 'CAUTION' ? 'warning' : 'error'}
              sx={{ height: 10, borderRadius: 1, mb: 0.5 }} />
            <Typography variant="caption" color="text.secondary">
              {wsScore} / {cooldownScore} (cooldown threshold)
            </Typography>
          </Box>
        </Box>

        <Typography variant="body2" sx={{ color: wsDesc.color, mb: 1.2 }}>
          {wsDesc.desc}
        </Typography>

        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1 }}>
          {[
            ['Caution at',  params.whipsaw_caution_score  ?? 2],
            ['Restrict at', params.whipsaw_restrict_score ?? 3],
            ['Cooldown at', params.whipsaw_cooldown_score ?? 4],
          ].map(([label, val]) => (
            <Box key={label} sx={{ textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', fontSize: '0.68rem' }}>{label}</Typography>
              <Typography variant="body2" sx={{ fontWeight: 700 }}>{val}</Typography>
            </Box>
          ))}
        </Box>

        {skipUntil && (
          <Alert severity="warning" sx={{ mt: 1.2 }}>
            Deployment blocked until {new Date(skipUntil).toLocaleTimeString()} (cooldown active)
          </Alert>
        )}
      </Paper>

      {/* ── ATM shield trail ── */}
      <Paper variant="outlined" sx={{ p: 1.8, borderRadius: 1.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.2 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>ATM Shield Events</Typography>
          <Chip size="small" label={`${shieldFires} total fires`}
            color={shieldFires > 3 ? 'error' : shieldFires > 0 ? 'warning' : 'success'} />
        </Box>

        {!shieldHistory.length ? (
          <Typography variant="caption" color="text.secondary">
            No shield events recorded for this session.
          </Typography>
        ) : (
          <Box sx={{ maxHeight: 280, overflow: 'auto' }}>
            {[...shieldHistory].reverse().slice(0, 20).map((ev, i) => (
              <Paper key={i} variant="outlined" sx={{ p: 1, mb: 0.6, borderRadius: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8, flexWrap: 'wrap' }}>
                  <Chip size="small" label={ev.event_type || 'shield'} color="warning" />
                  {ev.spot && (
                    <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                      spot=${Number(ev.spot).toFixed(0)}
                    </Typography>
                  )}
                  {ev.shift_count != null && (
                    <Chip size="small" variant="outlined" label={`shift #${ev.shift_count}`} />
                  )}
                  <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto', fontFamily: 'monospace' }}>
                    {ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : '—'}
                  </Typography>
                </Box>
                {ev.note && (
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.3 }}>
                    {ev.note}
                  </Typography>
                )}
              </Paper>
            ))}
          </Box>
        )}
      </Paper>
    </Box>
  );
}
