/**
 * MMMDeltaEnginePanel — live status of the Delta Neutral Engine for the MMM algo.
 * Data source: mmm_delta_engine socket event, passed in as `deltaEngine` prop.
 */

import React from 'react';
import { Box, Paper, Typography, Chip, Grid, Divider, LinearProgress, Alert } from '@mui/material';

function StatBox({ label, value, mono = false, color }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary" display="block">{label}</Typography>
      <Typography variant="body2" sx={{ fontWeight: 600, fontFamily: mono ? 'monospace' : 'inherit', color: color || 'inherit' }}>
        {value}
      </Typography>
    </Box>
  );
}

export default function MMMDeltaEnginePanel({ session, deltaEngine }) {
  // Prefer live deltaEngine event; fall back to session params for config display
  const params = session?.params ?? {};

  const enabled     = deltaEngine?.enabled       ?? params.delta_engine_enabled     ?? false;
  const instrument  = deltaEngine?.instrument    ?? params.delta_engine_instrument  ?? 'options';
  const threshold   = deltaEngine?.threshold     ?? params.delta_drift_threshold    ?? '—';
  const hardThresh  = deltaEngine?.hard_threshold ?? params.delta_drift_hard_threshold ?? '—';
  const totalHedges = deltaEngine?.total_hedges  ?? 0;
  const cooldownLeft = deltaEngine?.cooldown_remaining_sec ?? 0;
  const portfolioDelta = deltaEngine?.portfolio_delta ?? null;
  const lastHedgeAt  = deltaEngine?.last_hedge_at ?? null;
  const autoActivated = deltaEngine?.auto_activated ?? false;
  const perpMode    = instrument === 'perp';

  const deltaAbs = portfolioDelta != null ? Math.abs(portfolioDelta) : null;
  const deltaBarPct = deltaAbs != null ? Math.min(100, deltaAbs * 200) : 0;
  const deltaColor = deltaAbs == null ? 'text.primary'
    : deltaAbs > 0.3 ? '#f44336'
    : deltaAbs > 0.15 ? '#ff9800'
    : '#4caf50';

  if (!enabled && !deltaEngine) {
    return (
      <Alert severity="info" sx={{ mt: 1 }}>
        Delta Neutral Engine is disabled. Enable <code>delta_engine_enabled</code> in session settings to activate.
      </Alert>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Paper variant="outlined" sx={{ p: 2, mb: 2, borderRadius: 1.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>Delta Neutral Engine</Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            {autoActivated && (
              <Chip label="Auto-Activated" size="small" color="warning" variant="outlined" />
            )}
            <Chip
              label={enabled ? 'Active' : 'Disabled'}
              size="small"
              color={enabled ? 'success' : 'default'}
              sx={{ fontWeight: 700 }}
            />
          </Box>
        </Box>

        <Grid container spacing={2}>
          <Grid item xs={6} sm={3}>
            <StatBox label="Instrument" value={perpMode ? 'Perpetual Futures' : 'Near-ATM Options'} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <StatBox label="Soft Threshold" value={`±${threshold} Δ`} mono />
          </Grid>
          <Grid item xs={6} sm={3}>
            <StatBox label="Hard Threshold" value={`±${hardThresh} Δ`} mono />
          </Grid>
          <Grid item xs={6} sm={3}>
            <StatBox
              label="Cooldown"
              value={cooldownLeft > 0 ? `${Math.ceil(cooldownLeft)}s remaining` : 'Ready'}
              color={cooldownLeft > 0 ? '#ff9800' : '#4caf50'}
              mono
            />
          </Grid>
        </Grid>

        <Divider sx={{ my: 1.5 }} />

        <Grid container spacing={2}>
          <Grid item xs={6} sm={3}>
            <StatBox label="Total Hedges" value={totalHedges} mono />
          </Grid>
          <Grid item xs={6} sm={3}>
            <StatBox
              label="Last Hedge"
              value={lastHedgeAt ? new Date(lastHedgeAt).toLocaleTimeString() : '—'}
              mono
            />
          </Grid>
          {portfolioDelta != null && (
            <Grid item xs={12} sm={6}>
              <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.5 }}>
                Current Portfolio Delta
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <Typography variant="h5" sx={{ fontWeight: 800, color: deltaColor, lineHeight: 1 }}>
                  {portfolioDelta >= 0 ? '+' : ''}{portfolioDelta.toFixed(4)}
                </Typography>
                <Box sx={{ flex: 1 }}>
                  <LinearProgress
                    variant="determinate"
                    value={deltaBarPct}
                    color={deltaAbs > 0.3 ? 'error' : deltaAbs > 0.15 ? 'warning' : 'success'}
                    sx={{ height: 8, borderRadius: 1 }}
                  />
                </Box>
              </Box>
              <Typography variant="caption" color="text.secondary">
                Target: net-zero · Positive = net long · Negative = net short
              </Typography>
            </Grid>
          )}
        </Grid>
      </Paper>

      {/* Recent hedge executions */}
      {deltaEngine?.recent_hedges?.length > 0 && (
        <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 1.5 }}>
          <Typography variant="caption" sx={{
            fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5,
            fontSize: '0.68rem', color: 'text.secondary', display: 'block', mb: 1,
          }}>
            Recent Hedge Executions
          </Typography>
          {deltaEngine.recent_hedges.map((h, i) => (
            <Box key={i} sx={{
              display: 'flex', gap: 2, alignItems: 'center',
              py: 0.5, borderBottom: '1px solid', borderColor: 'divider',
              '&:last-child': { borderBottom: 0 },
            }}>
              <Typography variant="caption" color="text.secondary" sx={{ width: 70, flexShrink: 0 }}>
                {h.at ? new Date(h.at).toLocaleTimeString() : '—'}
              </Typography>
              <Chip label={h.mode ?? instrument} size="small" variant="outlined"
                color={h.mode === 'perp' ? 'primary' : 'success'}
                sx={{ height: 18, fontSize: '0.65rem' }} />
              <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                {h.lots ?? '?'} lots · δ {h.delta_before != null ? h.delta_before.toFixed(3) : '?'} → {h.delta_after != null ? h.delta_after.toFixed(3) : '?'}
              </Typography>
            </Box>
          ))}
        </Paper>
      )}
    </Box>
  );
}
