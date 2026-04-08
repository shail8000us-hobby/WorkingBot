/**
 * MMMXDeltaExposurePanel — per-tranche and portfolio delta exposure.
 * Source: tranches[].ce.entry_delta / pe.entry_delta / ce.current_delta / pe.current_delta
 */

import React from 'react';
import { Box, Paper, Typography, LinearProgress, Alert } from '@mui/material';
import { useMMMX } from '../MMMXContext';
import { fmt } from '../utils/mmmxFormatters';

export default function MMMXDeltaExposurePanel() {
  const { tranches, risk } = useMMMX();
  const activeTranches = tranches.filter(t => t.status === 'ACTIVE' || t.status === 'BEING_CLOSED');

  if (!activeTranches.length) {
    return (
      <Alert severity="info" sx={{ mt: 1 }}>
        No active tranches. Deploy tranches to see delta exposure.
      </Alert>
    );
  }

  // Portfolio delta from risk payload is most authoritative
  const portfolioDelta = risk.portfolio_delta ?? 0;
  const deltaAbs = Math.abs(portfolioDelta);
  const deltaBarPct = Math.min(100, deltaAbs * 200); // scale: 0.5 delta = 100%

  return (
    <Box>
      {/* Portfolio delta summary */}
      <Paper variant="outlined" sx={{ p: 1.8, mb: 2, borderRadius: 1.5 }}>
        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700 }}>Portfolio Delta</Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Typography variant="h3" sx={{
            fontWeight: 800,
            color: Math.abs(portfolioDelta) > 0.3 ? '#f44336'
              : Math.abs(portfolioDelta) > 0.15 ? '#ff9800'
              : '#4caf50',
            lineHeight: 1,
          }}>
            {portfolioDelta >= 0 ? '+' : ''}{portfolioDelta.toFixed(4)}
          </Typography>
          <Box sx={{ flex: 1 }}>
            <LinearProgress variant="determinate" value={deltaBarPct}
              color={deltaAbs > 0.3 ? 'error' : deltaAbs > 0.15 ? 'warning' : 'success'}
              sx={{ height: 8, borderRadius: 1 }} />
          </Box>
        </Box>
        <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
          Target: net-zero delta. Positive = net long, Negative = net short.
        </Typography>
      </Paper>

      {/* Per-tranche breakdown */}
      <Typography variant="caption" sx={{ display: 'block', mb: 1.2, fontWeight: 700, textTransform: 'uppercase',
        letterSpacing: 0.5, color: 'text.secondary', fontSize: '0.68rem' }}>
        Tranche Breakdown
      </Typography>
      {activeTranches.map(t => {
        const ceEntryDelta  = t.ce?.entry_delta ?? null;
        const peEntryDelta  = t.pe?.entry_delta ?? null;
        const ceCurrDelta   = t.ce?.current_delta ?? ceEntryDelta;
        const peCurrDelta   = t.pe?.current_delta ?? peEntryDelta;
        const ceLots = t.ce?.lots ?? 0;
        const peLots = t.pe?.lots ?? 0;
        const netDelta = ((ceCurrDelta ?? 0) * ceLots + (peCurrDelta ?? 0) * peLots);

        return (
          <Paper key={t.tranche_id} variant="outlined" sx={{ p: 1.2, mb: 0.8, borderRadius: 1.2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.8 }}>
              <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
                {t.tranche_id}
              </Typography>
              <Typography variant="body2" sx={{
                fontFamily: 'monospace', fontWeight: 700,
                color: Math.abs(netDelta) > 0.3 ? '#f44336' : Math.abs(netDelta) > 0.1 ? '#ff9800' : '#4caf50',
              }}>
                Net Δ {netDelta >= 0 ? '+' : ''}{netDelta.toFixed(3)}
              </Typography>
            </Box>
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1 }}>
              {/* CE */}
              <Box sx={{ p: 0.8, borderRadius: 1, border: '1px solid', borderColor: '#4caf5044', bgcolor: 'rgba(76,175,80,0.04)' }}>
                <Typography variant="caption" sx={{ color: '#4caf50', fontWeight: 700, display: 'block', mb: 0.3 }}>
                  CE · {ceLots} lots
                </Typography>
                <Typography variant="caption" sx={{ fontFamily: 'monospace', display: 'block' }}>
                  Entry: {ceEntryDelta != null ? fmt(ceEntryDelta, 4) : '—'}
                </Typography>
                {ceCurrDelta !== ceEntryDelta && ceCurrDelta != null && (
                  <Typography variant="caption" sx={{ fontFamily: 'monospace', display: 'block', color: '#ff9800' }}>
                    Current: {fmt(ceCurrDelta, 4)}
                  </Typography>
                )}
              </Box>
              {/* PE */}
              <Box sx={{ p: 0.8, borderRadius: 1, border: '1px solid', borderColor: '#f4433644', bgcolor: 'rgba(244,67,54,0.04)' }}>
                <Typography variant="caption" sx={{ color: '#f44336', fontWeight: 700, display: 'block', mb: 0.3 }}>
                  PE · {peLots} lots
                </Typography>
                <Typography variant="caption" sx={{ fontFamily: 'monospace', display: 'block' }}>
                  Entry: {peEntryDelta != null ? fmt(peEntryDelta, 4) : '—'}
                </Typography>
                {peCurrDelta !== peEntryDelta && peCurrDelta != null && (
                  <Typography variant="caption" sx={{ fontFamily: 'monospace', display: 'block', color: '#ff9800' }}>
                    Current: {fmt(peCurrDelta, 4)}
                  </Typography>
                )}
              </Box>
            </Box>
          </Paper>
        );
      })}
    </Box>
  );
}
