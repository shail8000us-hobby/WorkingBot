/**
 * MMMHealthRadar — 5-Axis Portfolio Health Spider Chart
 *
 * Shows a compact radar/spider chart with 5 dimensions of portfolio health:
 * 1. BE Buffer    — distance from spot to nearest breakeven boundary
 * 2. γ Buffer     — distance from spot to nearest gamma boundary
 * 3. Margin Safety — 100% minus exchange margin utilization
 * 4. Regime Calm  — how "normal" the regime controls are (NORMAL=max, BLOCK_ALL=min)
 * 5. Trend Safety — inverted trend tier (Tier 0=max, Tier 4=min)
 *
 * All axes are normalized to 0-100. Green = healthy, Amber = elevated, Red = alarm.
 *
 * Props:
 *   breakeven: BreakevenResult dict
 *   gamma:     GammaResult dict (optional)
 *   margin:    margin snapshot {utilization_pct, tier} (from heartbeat.margin)
 *   regime:    regime snapshot {regime_action, trend_tier} (from heartbeat.regime)
 */

import React from 'react';
import { Box, Typography, Chip, Tooltip } from '@mui/material';
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
} from 'recharts';

// Regime action → health score
const REGIME_SCORES = {
  NORMAL:           95,
  BLOCK_CE_SELLS:   65,
  BLOCK_PE_SELLS:   65,
  BLOCK_ALL_SELLS:  35,
  PAUSE:            15,
  FORCE_REDUCE:      5,
};

// Trend tier → health score
const TREND_TIER_SCORES = { 0: 95, 1: 70, 2: 45, 3: 20, 4: 5 };

function computeRadarData({ breakeven, gamma, margin, regime }) {
  // 1. BE Buffer — clamp distance to [0%…5%] → [0…100] score
  let beScore = 100;
  if (breakeven?.enabled && breakeven.nearest_distance_pct != null) {
    beScore = Math.min(100, (breakeven.nearest_distance_pct / 5.0) * 100);
  }

  // 2. γ Buffer — clamp distance to [0%…6%] → [0…100] score
  let gammaScore = 100;
  if (gamma?.enabled && gamma.nearest_distance_pct != null) {
    gammaScore = Math.min(100, (gamma.nearest_distance_pct / 6.0) * 100);
  }

  // 3. Margin Safety
  let marginScore = 85; // default if no data
  if (margin?.utilization_pct != null) {
    marginScore = Math.max(0, 100 - margin.utilization_pct);
  }

  // 4. Regime Calm
  const regimeAction = regime?.regime_action || regime?.action || 'NORMAL';
  const regimeScore = REGIME_SCORES[regimeAction] ?? 95;

  // 5. Trend Safety — use numeric trend_tier if present, else derive from trend_regime string
  const TREND_REGIME_TO_TIER = { NORMAL: 0, TIER_NONE: 0, ALERT: 1, GUARD: 2, BLOCK: 3, WIND_DOWN: 4, TIER1: 1, TIER2: 2, TIER3: 3, TIER4: 4 };
  const trendTier = regime?.trend_tier ?? TREND_REGIME_TO_TIER[regime?.trend_regime] ?? 0;
  const trendScore = TREND_TIER_SCORES[trendTier] ?? 95;

  return [
    { subject: 'BE Buffer',     value: Math.round(beScore),     detail: breakeven?.nearest_distance_pct != null ? `${breakeven.nearest_distance_pct.toFixed(1)}% dist` : 'No boundary' },
    { subject: 'γ Buffer',      value: Math.round(gammaScore),  detail: gamma?.nearest_distance_pct != null ? `${gamma.nearest_distance_pct.toFixed(1)}% dist` : 'No boundary' },
    { subject: 'Margin',        value: Math.round(marginScore), detail: margin?.utilization_pct != null ? `${margin.utilization_pct.toFixed(0)}% used` : 'No data' },
    { subject: 'Regime',        value: regimeScore,             detail: regimeAction },
    { subject: 'Trend',         value: trendScore,              detail: `Tier ${trendTier}` },
  ];
}

// Color based on worst score
function getHealthColor(data) {
  const worst = Math.min(...data.map(d => d.value));
  if (worst < 30) return '#f44336';
  if (worst < 60) return '#ff9800';
  return '#4caf50';
}

// Custom tooltip
function RadarCustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  return (
    <Box sx={{
      backgroundColor: 'rgba(18,18,18,0.95)',
      border: '1px solid rgba(255,255,255,0.15)',
      borderRadius: 1, p: 0.75,
      fontSize: '0.72rem',
    }}>
      <Typography variant="caption" sx={{ fontWeight: 700, display: 'block' }}>{d.subject}</Typography>
      <Typography variant="caption" sx={{ color: '#4caf50' }}>Score: {d.value}/100</Typography>
      {d.detail && (
        <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary' }}>{d.detail}</Typography>
      )}
    </Box>
  );
}

export default function MMMHealthRadar({ breakeven, gamma, margin, regime }) {
  // If no data at all, show a waiting placeholder so the card always occupies its column
  const hasAnyData = breakeven?.enabled || gamma?.enabled || margin?.utilization_pct != null || regime?.regime_action != null;
  if (!hasAnyData) {
    return (
      <Box sx={{
        p: 1.5, borderRadius: 1.5,
        border: '1px solid rgba(255,255,255,0.08)',
        backgroundColor: 'rgba(255,255,255,0.02)',
        mb: 2,
      }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 0.5 }}>🕸 Portfolio Health</Typography>
        <Typography variant="caption" color="text.secondary">
          Waiting for session heartbeat — health scores not yet available.
        </Typography>
      </Box>
    );
  }

  const radarData = computeRadarData({ breakeven, gamma, margin, regime });
  const healthColor = getHealthColor(radarData);
  const worstScore = Math.min(...radarData.map(d => d.value));
  const overallLabel = worstScore >= 70 ? 'Healthy' : worstScore >= 40 ? 'Elevated' : 'Alert';

  return (
    <Box sx={{
      p: 1.5,
      borderRadius: 1.5,
      border: `1px solid ${healthColor}40`,
      backgroundColor: `${healthColor}08`,
      mb: 2,
    }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'text.primary' }}>
          🕸 Portfolio Health
        </Typography>
        <Chip
          label={overallLabel}
          size="small"
          sx={{
            fontWeight: 700, fontSize: '0.7rem',
            color: healthColor,
            border: `1px solid ${healthColor}`,
            backgroundColor: 'transparent',
          }}
        />
      </Box>

      {/* Radar chart */}
      <ResponsiveContainer width="100%" height={200}>
        <RadarChart cx="50%" cy="50%" outerRadius={72} data={radarData}>
          <PolarGrid stroke="rgba(255,255,255,0.08)" />
          <PolarAngleAxis
            dataKey="subject"
            tick={{ fill: '#888', fontSize: 10, fontWeight: 500 }}
          />
          <PolarRadiusAxis
            angle={72}
            domain={[0, 100]}
            tick={false}
            axisLine={false}
            tickCount={3}
          />
          <Radar
            name="Health"
            dataKey="value"
            stroke={healthColor}
            strokeWidth={2}
            fill={healthColor}
            fillOpacity={0.18}
            dot={{ fill: healthColor, r: 3, strokeWidth: 0 }}
          />
          <ChartTooltip content={<RadarCustomTooltip />} />
        </RadarChart>
      </ResponsiveContainer>

      {/* Score row */}
      <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mt: 0.5 }}>
        {radarData.map(d => {
          const c = d.value >= 70 ? '#4caf50' : d.value >= 40 ? '#ff9800' : '#f44336';
          return (
            <Tooltip key={d.subject} title={d.detail} placement="top">
              <Box sx={{
                display: 'flex', flexDirection: 'column', alignItems: 'center',
                minWidth: 40, cursor: 'help',
              }}>
                <Typography variant="caption" sx={{ fontSize: '0.6rem', color: 'text.disabled' }}>
                  {d.subject.split(' ')[0]}
                </Typography>
                <Typography variant="caption" sx={{ fontSize: '0.68rem', color: c, fontFamily: 'monospace', fontWeight: 700 }}>
                  {d.value}
                </Typography>
              </Box>
            </Tooltip>
          );
        })}
      </Box>
    </Box>
  );
}
