/**
 * MMMXPnLChart — SVG sparkline of portfolio P&L over heartbeats.
 * Data source: pnlHistory from MMMXContext (accumulated in-memory per session load).
 * No external charting library — pure SVG.
 */

import React, { useMemo } from 'react';
import { Box, Paper, Typography, Chip } from '@mui/material';
import { useMMMX } from '../MMMXContext';
import { fmt } from '../utils/mmmxFormatters';

const W = 480;
const H = 100;
const PAD = 12;

function Sparkline({ points, color, strokeWidth = 1.5 }) {
  if (points.length < 2) return null;
  const d = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
  // Area fill
  const first = points[0];
  const last  = points[points.length - 1];
  const zeroY = points[0]?.zeroY ?? H - PAD;
  const area  = `M${first.x},${zeroY} ${d.slice(1)} L${last.x},${zeroY} Z`;
  return (
    <>
      <path d={area} fill={color} fillOpacity={0.12} />
      <path d={d} stroke={color} strokeWidth={strokeWidth} fill="none" strokeLinejoin="round" />
    </>
  );
}

function mapPoints(data, key, zeroY) {
  if (!data.length) return [];
  const values = data.map(d => d[key]);
  const minV = Math.min(...values, 0);
  const maxV = Math.max(...values, 0);
  const rangeV = maxV - minV || 1;
  const innerW = W - PAD * 2;
  const innerH = H - PAD * 2;
  return data.map((d, i) => ({
    x: PAD + (i / Math.max(data.length - 1, 1)) * innerW,
    y: PAD + (1 - (d[key] - minV) / rangeV) * innerH,
    zeroY: PAD + (1 - (0 - minV) / rangeV) * innerH,
    raw: d[key],
    at: d.at,
  }));
}

export default function MMMXPnLChart() {
  const { pnlHistory, risk, session } = useMMMX();

  // pnlHistory is newest-first; reverse for chronological display
  const chronological = useMemo(() => [...pnlHistory].reverse(), [pnlHistory]);

  const pnlPoints   = useMemo(() => mapPoints(chronological, 'pnl',   0), [chronological]);
  const deltaPoints = useMemo(() => mapPoints(chronological, 'delta', 0), [chronological]);

  const currentPnl   = risk.portfolio_pnl   ?? 0;
  const currentDelta = risk.portfolio_delta  ?? 0;
  const hardStop     = session?.hard_stop_usd ?? 0;

  if (!pnlHistory.length) {
    return (
      <Paper variant="outlined" sx={{ p: 1.8, borderRadius: 1.5 }}>
        <Typography variant="subtitle2" sx={{ mb: 0.5, fontWeight: 700 }}>P&amp;L Chart</Typography>
        <Typography variant="caption" color="text.secondary">
          Waiting for heartbeat data. Chart builds in real-time as the monitor sends beats.
        </Typography>
      </Paper>
    );
  }

  const pnlColor   = currentPnl >= 0 ? '#4caf50' : '#f44336';
  const deltaColor = Math.abs(currentDelta) > 0.2 ? '#f44336' : '#2196f3';

  return (
    <Box>
      <Paper variant="outlined" sx={{ p: 1.5, mb: 1.5, borderRadius: 1.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>Portfolio P&amp;L</Typography>
          <Chip size="small" label={`$${fmt(currentPnl)}`}
            sx={{ bgcolor: `${pnlColor}22`, color: pnlColor, fontWeight: 700, fontFamily: 'monospace' }} />
          {hardStop > 0 && (
            <Typography variant="caption" color="text.secondary">
              Hard stop: ${fmt(hardStop, 0)}
            </Typography>
          )}
          <Typography variant="caption" color="text.disabled" sx={{ ml: 'auto' }}>
            {pnlHistory.length} beats
          </Typography>
        </Box>
        <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: H, display: 'block' }}>
          {/* Zero line */}
          {pnlPoints.length > 0 && (
            <line
              x1={PAD} y1={pnlPoints[0].zeroY}
              x2={W - PAD} y2={pnlPoints[0].zeroY}
              stroke="#555" strokeWidth={0.5} strokeDasharray="3,3"
            />
          )}
          <Sparkline points={pnlPoints} color={pnlColor} />
          {/* Current value dot */}
          {pnlPoints.length > 0 && (() => {
            const last = pnlPoints[pnlPoints.length - 1];
            return <circle cx={last.x} cy={last.y} r={3} fill={pnlColor} />;
          })()}
        </svg>
      </Paper>

      <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 1.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>Portfolio Delta</Typography>
          <Chip size="small" label={`${currentDelta >= 0 ? '+' : ''}${currentDelta.toFixed(4)}`}
            sx={{ bgcolor: `${deltaColor}22`, color: deltaColor, fontWeight: 700, fontFamily: 'monospace' }} />
        </Box>
        <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: H, display: 'block' }}>
          {deltaPoints.length > 0 && (
            <line
              x1={PAD} y1={deltaPoints[0].zeroY}
              x2={W - PAD} y2={deltaPoints[0].zeroY}
              stroke="#555" strokeWidth={0.5} strokeDasharray="3,3"
            />
          )}
          <Sparkline points={deltaPoints} color={deltaColor} />
          {deltaPoints.length > 0 && (() => {
            const last = deltaPoints[deltaPoints.length - 1];
            return <circle cx={last.x} cy={last.y} r={3} fill={deltaColor} />;
          })()}
        </svg>
      </Paper>
    </Box>
  );
}
