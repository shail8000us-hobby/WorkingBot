/**
 * MMMDistanceHistoryChart — Zone Distance Timeline
 *
 * Shows a rolling time-series chart of how far spot has been from the
 * breakeven and gamma boundaries over the last N heartbeats.
 *
 * Data source: heartbeatHistory prop (rolling buffer maintained by MMMDashboard).
 * Each entry: { ts, beDistance, gammaDistance, beZone, gammaZone }
 *
 * Props:
 *   heartbeatHistory: array of history entries (max 200, newest last)
 *     Each entry: {
 *       ts: timestamp (ms or ISO string),
 *       beDistance: nearest_distance_pct from breakeven result,
 *       gammaDistance: nearest_distance_pct from gamma result,
 *       beZone: zone string,
 *       gammaZone: gamma_zone string,
 *     }
 */

import React, { useMemo } from 'react';
import { Box, Typography, Chip } from '@mui/material';
import {
  ComposedChart,
  Line,
  ReferenceLine,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as ChartTooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';

function fmtTime(ts) {
  if (!ts) return '';
  const d = typeof ts === 'string' ? new Date(ts) : new Date(ts);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function CustomTimelineTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <Box sx={{
      backgroundColor: 'rgba(18,18,18,0.95)',
      border: '1px solid rgba(255,255,255,0.15)',
      borderRadius: 1, p: 1, fontSize: '0.72rem',
    }}>
      <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 0.5 }}>
        {fmtTime(label)}
      </Typography>
      {payload.map(p => (
        <Typography key={p.name} variant="caption" sx={{ color: p.color, display: 'block' }}>
          {p.name}: {p.value != null ? `${p.value.toFixed(2)}%` : '—'}
        </Typography>
      ))}
    </Box>
  );
}

export default function MMMDistanceHistoryChart({ heartbeatHistory = [], beWarnPct = 2.0, gammaWarnPct = 3.0 }) {
  // Filter to entries that have at least one distance value
  const chartData = useMemo(() => {
    return heartbeatHistory
      .filter(e => e.beDistance != null || e.gammaDistance != null)
      .map(e => ({
        ts: e.ts,
        'BE Dist%': e.beDistance != null ? parseFloat(e.beDistance.toFixed(3)) : null,
        'γ Dist%':  e.gammaDistance != null ? parseFloat(e.gammaDistance.toFixed(3)) : null,
      }));
  }, [heartbeatHistory]);

  if (chartData.length < 2) {
    return (
      <Box sx={{
        p: 1.5, borderRadius: 1.5,
        border: '1px solid rgba(255,255,255,0.08)',
        backgroundColor: 'rgba(255,255,255,0.02)',
        mb: 2,
      }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>
          📊 Distance History
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Collecting history… (needs 2+ heartbeats with breakeven/gamma data)
        </Typography>
      </Box>
    );
  }

  // Determine if we have BE or gamma data
  const hasBE    = chartData.some(d => d['BE Dist%'] != null);
  const hasGamma = chartData.some(d => d['γ Dist%'] != null);

  return (
    <Box sx={{
      p: 1.5, borderRadius: 1.5,
      border: '1px solid rgba(255,255,255,0.08)',
      backgroundColor: 'rgba(255,255,255,0.02)',
      mb: 2,
    }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.75 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          📊 Distance History
        </Typography>
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Chip
            label={`${chartData.length} pts`}
            size="small"
            sx={{ fontSize: '0.62rem', opacity: 0.6 }}
          />
        </Box>
      </Box>

      <ResponsiveContainer width="100%" height={180}>
        <ComposedChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
          <XAxis
            dataKey="ts"
            tickFormatter={fmtTime}
            tick={{ fontSize: 9, fill: '#666' }}
            tickLine={false}
            axisLine={{ stroke: 'rgba(255,255,255,0.08)' }}
            interval="preserveStartEnd"
          />
          <YAxis
            tickFormatter={v => `${v}%`}
            tick={{ fontSize: 9, fill: '#666' }}
            tickLine={false}
            axisLine={false}
            width={36}
            domain={[0, 'auto']}
          />
          <ChartTooltip content={<CustomTimelineTooltip />} />

          {/* Warning zone reference lines */}
          <ReferenceLine
            y={beWarnPct}
            stroke="rgba(255,152,0,0.3)"
            strokeDasharray="3 3"
            label={{ value: 'BE Warn', position: 'right', fontSize: 8, fill: '#ff9800' }}
          />
          <ReferenceLine
            y={gammaWarnPct}
            stroke="rgba(171,71,188,0.3)"
            strokeDasharray="3 3"
            label={{ value: 'γ Warn', position: 'right', fontSize: 8, fill: '#ab47bc' }}
          />

          {/* Breakeven distance line */}
          {hasBE && (
            <Line
              type="monotone"
              dataKey="BE Dist%"
              stroke="#ff7043"
              strokeWidth={1.5}
              dot={false}
              connectNulls
              isAnimationActive={false}
              activeDot={{ r: 3 }}
            />
          )}

          {/* Gamma distance line */}
          {hasGamma && (
            <Line
              type="monotone"
              dataKey="γ Dist%"
              stroke="#ab47bc"
              strokeWidth={1.5}
              dot={false}
              connectNulls
              isAnimationActive={false}
              activeDot={{ r: 3 }}
            />
          )}

          {(hasBE || hasGamma) && (
            <Legend
              wrapperStyle={{ fontSize: '0.68rem', paddingTop: '4px' }}
              iconType="line"
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>

      <Typography variant="caption" sx={{ fontSize: '0.6rem', color: 'text.disabled', display: 'block', mt: 0.5 }}>
        Lower = spot closer to boundary. Dashed lines = warning thresholds.
      </Typography>
    </Box>
  );
}
