import React, { useMemo } from 'react';
import { Box, Chip, LinearProgress, Paper, Typography } from '@mui/material';
import { useMMMX } from '../MMMXContext';
import { WHIPSAW_COLOR, WHIPSAW_LABEL } from '../utils/mmmxConstants';

const SEC_TITLE_SX = {
  textTransform: 'uppercase',
  letterSpacing: 0.5,
  color: 'text.secondary',
  fontSize: '0.65rem',
};

function mapPoints(series, width, height, pad = 6) {
  if (!Array.isArray(series) || series.length < 2) return [];
  const values = series.map((v) => Number(v ?? 0));
  const minV = Math.min(...values);
  const maxV = Math.max(...values);
  const range = maxV - minV || 1;
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;

  return values.map((value, idx) => ({
    x: pad + (idx / Math.max(values.length - 1, 1)) * innerW,
    y: pad + (1 - (value - minV) / range) * innerH,
  }));
}

function Sparkline({ points, color }) {
  if (!points.length) return null;
  const d = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(2)},${p.y.toFixed(2)}`)
    .join(' ');

  return (
    <path
      d={d}
      stroke={color}
      strokeWidth={1.5}
      fill="none"
      strokeLinejoin="round"
      strokeLinecap="round"
    />
  );
}

function deltaColor(absDelta) {
  if (absDelta < 0.15) return '#4caf50';
  if (absDelta < 0.3) return '#ff9800';
  return '#f44336';
}

function reserveColor(lots) {
  if (lots < 5) return '#f44336';
  if (lots < 10) return '#ff9800';
  return 'inherit';
}

export default function MMMXRiskRail() {
  const { session, risk, pnlHistory, reserveHistory } = useMMMX();

  const portfolioDelta = Number(risk?.portfolio_delta ?? 0);
  const deltaAbs = Math.abs(portfolioDelta);
  const deltaTone = deltaColor(deltaAbs);
  const deltaProgress = Math.min(100, deltaAbs * 200);

  const whipsawScore = Number(risk?.whipsaw_score ?? 0);
  const whipsawLevel = WHIPSAW_LABEL[whipsawScore] ?? 'NORMAL';

  const cbState = risk?.circuit_breaker_state ?? 'CLOSED';
  const cbColor = cbState === 'CLOSED' ? 'success' : cbState === 'OPEN' ? 'warning' : 'error';

  const hardStop = Number(session?.hard_stop_usd ?? 0);
  const hardStopPct = hardStop > 0
    ? (Math.abs(Number(risk?.portfolio_pnl ?? 0)) / hardStop) * 100
    : 0;
  const hardStopColor = hardStopPct > 70 ? '#f44336' : hardStopPct > 40 ? '#ff9800' : '#4caf50';

  const ceReserve = Number(session?.ce_reserve_remaining ?? 30);
  const peReserve = Number(session?.pe_reserve_remaining ?? 30);

  const pnlSeries = useMemo(
    () => (pnlHistory || []).slice(0, 20).reverse().map((p) => Number(p?.pnl ?? 0)),
    [pnlHistory],
  );
  const pnlPoints = useMemo(() => mapPoints(pnlSeries, 200, 50, 6), [pnlSeries]);

  const reserveWindow = useMemo(() => (reserveHistory || []).slice(0, 20).reverse(), [reserveHistory]);
  const ceSeries = useMemo(() => reserveWindow.map((p) => Number(p?.ce ?? 0)), [reserveWindow]);
  const peSeries = useMemo(() => reserveWindow.map((p) => Number(p?.pe ?? 0)), [reserveWindow]);
  const cePoints = useMemo(() => mapPoints(ceSeries, 200, 40, 6), [ceSeries]);
  const pePoints = useMemo(() => mapPoints(peSeries, 200, 40, 6), [peSeries]);

  if (!session) {
    return (
      <Box sx={{ minHeight: 140, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Typography color="text.secondary" variant="caption">No session</Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Paper variant="outlined" sx={{ p: 1.2, mb: 1, borderRadius: 1.2 }}>
        <Typography variant="caption" sx={SEC_TITLE_SX}>Portfolio Delta</Typography>
        <Typography
          sx={{
            mt: 0.4,
            mb: 0.7,
            fontFamily: 'monospace',
            fontWeight: 800,
            fontSize: '1.05rem',
            color: deltaTone,
          }}
        >
          {portfolioDelta >= 0 ? '+' : ''}
          {portfolioDelta.toFixed(4)}
        </Typography>
        <LinearProgress
          variant="determinate"
          value={deltaProgress}
          sx={{
            height: 7,
            borderRadius: 4,
            bgcolor: 'rgba(255,255,255,0.08)',
            '& .MuiLinearProgress-bar': { backgroundColor: deltaTone },
          }}
        />
      </Paper>

      <Paper variant="outlined" sx={{ p: 1.2, mb: 1, borderRadius: 1.2 }}>
        <Typography variant="caption" sx={SEC_TITLE_SX}>Whipsaw</Typography>
        <Box sx={{ mt: 0.6, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
          <Typography sx={{ fontFamily: 'monospace', fontWeight: 700 }}>Score {Math.round(whipsawScore)}</Typography>
          <Chip
            label={whipsawLevel}
            color={WHIPSAW_COLOR[whipsawLevel] || 'default'}
            size="small"
            sx={{ height: 18, fontSize: '0.62rem', fontWeight: 700 }}
          />
        </Box>
      </Paper>

      <Paper variant="outlined" sx={{ p: 1.2, mb: 1, borderRadius: 1.2 }}>
        <Typography variant="caption" sx={SEC_TITLE_SX}>Circuit Breaker</Typography>
        <Box sx={{ mt: 0.6 }}>
          <Chip
            label={cbState}
            color={cbColor}
            size="small"
            sx={{ height: 18, fontSize: '0.62rem', fontWeight: 700 }}
          />
        </Box>
      </Paper>

      {hardStop > 0 && (
        <Paper variant="outlined" sx={{ p: 1.2, mb: 1, borderRadius: 1.2 }}>
          <Typography variant="caption" sx={SEC_TITLE_SX}>Hard Stop Utilisation</Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.45, mb: 0.7 }}>
            {hardStopPct.toFixed(1)}% of ${hardStop.toFixed(0)}
          </Typography>
          <LinearProgress
            variant="determinate"
            value={Math.min(100, hardStopPct)}
            sx={{
              height: 7,
              borderRadius: 4,
              bgcolor: 'rgba(255,255,255,0.08)',
              '& .MuiLinearProgress-bar': { backgroundColor: hardStopColor },
            }}
          />
        </Paper>
      )}

      <Paper variant="outlined" sx={{ p: 1.2, mb: 1, borderRadius: 1.2 }}>
        <Typography variant="caption" sx={SEC_TITLE_SX}>CE / PE Reserves</Typography>
        <Box sx={{ mt: 0.65, display: 'flex', gap: 1 }}>
          <Box sx={{ flex: 1 }}>
            <Typography variant="caption" color="text.secondary">CE Reserve</Typography>
            <Typography sx={{ fontWeight: 700, color: reserveColor(ceReserve) }}>{ceReserve} lots</Typography>
          </Box>
          <Box sx={{ flex: 1 }}>
            <Typography variant="caption" color="text.secondary">PE Reserve</Typography>
            <Typography sx={{ fontWeight: 700, color: reserveColor(peReserve) }}>{peReserve} lots</Typography>
          </Box>
        </Box>
      </Paper>

      <Paper variant="outlined" sx={{ p: 1.2, mb: 1, borderRadius: 1.2 }}>
        <Typography variant="caption" sx={SEC_TITLE_SX}>Mini P&amp;L</Typography>
        {pnlSeries.length >= 3 ? (
          <Box sx={{ mt: 0.55 }}>
            <svg viewBox="0 0 200 50" width="100%" height="50">
              <Sparkline points={pnlPoints} color="#42a5f5" />
            </svg>
          </Box>
        ) : (
          <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
            No history yet
          </Typography>
        )}
      </Paper>

      <Paper variant="outlined" sx={{ p: 1.2, mb: 1, borderRadius: 1.2 }}>
        <Typography variant="caption" sx={SEC_TITLE_SX}>Reserve History</Typography>

        {reserveWindow.length >= 3 ? (
          <Box sx={{ mt: 0.55 }}>
            <Typography variant="caption" color="text.secondary">CE reserve</Typography>
            <svg viewBox="0 0 200 40" width="100%" height="40">
              <Sparkline points={cePoints} color="#4caf50" />
            </svg>

            <Typography variant="caption" color="text.secondary">PE reserve</Typography>
            <svg viewBox="0 0 200 40" width="100%" height="40">
              <Sparkline points={pePoints} color="#f44336" />
            </svg>
          </Box>
        ) : (
          <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
            No history yet
          </Typography>
        )}
      </Paper>
    </Box>
  );
}