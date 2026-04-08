import React, { useMemo } from 'react';
import { Box, Paper, Typography } from '@mui/material';
import { useMMMX } from '../MMMXContext';
import { heartbeatAgeSec } from '../utils/mmmxFormatters';

const SIZE = 200;
const CENTER = 100;
const MAX_RADIUS = 75;

function pointFor(i, radius) {
  const angle = ((i * 60 - 90) * Math.PI) / 180;
  return {
    x: CENTER + radius * Math.cos(angle),
    y: CENTER + radius * Math.sin(angle),
  };
}

function polygonPoints(values, radiusFn) {
  return values
    .map((_, i) => {
      const p = pointFor(i, radiusFn(values[i], i));
      return `${p.x.toFixed(2)},${p.y.toFixed(2)}`;
    })
    .join(' ');
}

export default function MMMXHealthRadar() {
  const { session, risk, isConnected } = useMMMX();

  const model = useMemo(() => {
    const hbAgeSec = heartbeatAgeSec(session?._last_beat_at || session?.last_beat_at);
    const deltaAbs = Math.abs(Number(risk?.portfolio_delta ?? 0));
    const whipsawScore = Number(risk?.whipsaw_score ?? 0);
    const minReserve = Math.min(
      Number(session?.ce_reserve_remaining ?? 30),
      Number(session?.pe_reserve_remaining ?? 30),
    );
    const pnl = Number(risk?.portfolio_pnl ?? 0);
    const hardStop = Number(session?.hard_stop_usd ?? 0);

    const scores = [
      isConnected ? 100 : 0,
      hbAgeSec < 30 ? 100 : hbAgeSec < 60 ? 70 : hbAgeSec < 120 ? 40 : 0,
      deltaAbs < 0.1 ? 100 : deltaAbs < 0.2 ? 80 : deltaAbs < 0.3 ? 50 : 20,
      [100, 100, 70, 40, 20][whipsawScore] ?? 20,
      minReserve >= 20 ? 100 : minReserve >= 10 ? 70 : minReserve >= 5 ? 40 : 10,
      hardStop > 0 ? Math.max(0, 100 - (Math.abs(pnl) / hardStop) * 100) : pnl >= 0 ? 100 : 50,
    ];

    const labels = ['Connectivity', 'Heartbeat', 'Delta Balance', 'Whipsaw', 'Reserve', 'P&L Health'];
    const overall = Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length);

    return { scores, labels, overall };
  }, [session, risk, isConnected]);

  const overallColor = model.overall >= 80 ? '#4caf50' : model.overall >= 60 ? '#ff9800' : '#f44336';
  const scorePolyPoints = polygonPoints(model.scores, (score) => (Math.max(0, Math.min(100, score)) / 100) * MAX_RADIUS);

  const rings = [0.33, 0.66, 1.0].map((factor) =>
    polygonPoints(model.scores, () => MAX_RADIUS * factor),
  );

  return (
    <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 1.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', mb: 1 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>System Health</Typography>
        <Typography sx={{ fontWeight: 800, fontFamily: 'monospace', color: overallColor }}>
          {model.overall}
        </Typography>
      </Box>

      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} width="100%" height="220">
        {rings.map((pts, idx) => (
          <polygon
            key={`ring-${idx}`}
            points={pts}
            fill="none"
            stroke="#ffffff15"
            strokeWidth="1"
          />
        ))}

        {model.scores.map((_, i) => {
          const axis = pointFor(i, MAX_RADIUS);
          return (
            <line
              key={`axis-${i}`}
              x1={CENTER}
              y1={CENTER}
              x2={axis.x}
              y2={axis.y}
              stroke="#ffffff20"
              strokeWidth="1"
            />
          );
        })}

        <polygon
          points={scorePolyPoints}
          fill="rgba(33,150,243,0.2)"
          stroke="#2196f3"
          strokeWidth="1.5"
        />

        {model.scores.map((score, i) => {
          const vertex = pointFor(i, (Math.max(0, Math.min(100, score)) / 100) * MAX_RADIUS);
          return <circle key={`dot-${i}`} cx={vertex.x} cy={vertex.y} r="3" fill="#2196f3" />;
        })}

        {model.labels.map((label, i) => {
          const lp = pointFor(i, MAX_RADIUS * 1.1);
          return (
            <text
              key={`label-${label}`}
              x={lp.x}
              y={lp.y}
              fill="#aaa"
              fontSize="8"
              textAnchor="middle"
              dominantBaseline="middle"
            >
              {label}
            </text>
          );
        })}
      </svg>
    </Paper>
  );
}