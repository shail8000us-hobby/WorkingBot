/**
 * PnLAttributionPanel  (Feature 4)
 * ==================================
 * Collapsible panel showing PnL breakdown by Greek source.
 * Fetches from GET /api/options/pnl-attribution every 30s.
 *
 * Segments: Delta (blue) | Gamma (purple) | Theta (green) | Vega (orange) | Residual (gray)
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box, Paper, Typography, IconButton, Chip, Tooltip,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import RefreshIcon from '@mui/icons-material/Refresh';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Cell,
  Tooltip as RechartTooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { alpha } from '@mui/material/styles';

const ACCENT = '#22d3ee';
const POSITIVE = '#34d399';
const NEGATIVE = '#f87171';
const NUMERIC_FONT = 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace';
const CARD_MIN_HEIGHT = 318;
const CHART_HEIGHT = 180;
const FOOTER_MIN_HEIGHT = 34;

const COLORS = {
  delta_pnl:   '#3b82f6',
  gamma_pnl:   '#a855f7',
  theta_pnl:   '#10b981',
  vega_pnl:    '#f59e0b',
  residual_pnl:'#64748b',
};

const LABELS = {
  delta_pnl:   'Delta',
  gamma_pnl:   'Gamma',
  theta_pnl:   'Theta',
  vega_pnl:    'Vega',
  residual_pnl:'Residual',
};

function buildChartData(attribution) {
  if (!attribution) return [];
  return Object.keys(LABELS).map(key => ({
    name: LABELS[key],
    value: attribution[key] || 0,
    key,
  }));
}

function fmtUsd(v) {
  const sign = v >= 0 ? '+' : '';
  return `${sign}$${Math.abs(v).toFixed(2)}`;
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  return (
    <Box
      sx={{
        bgcolor: alpha('#0f172a', 0.96),
        border: `1px solid ${alpha(ACCENT, 0.35)}`,
        borderRadius: 1.4,
        px: 1.1,
        py: 0.9,
        boxShadow: `0 10px 30px ${alpha('#000', 0.5)}`,
      }}
    >
      <Typography
        variant="caption"
        sx={{
          color: alpha('#e2e8f0', 0.9),
          fontWeight: 800,
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
          fontSize: '0.64rem',
        }}
      >
        {d.name}
      </Typography>
      <Typography
        variant="caption"
        sx={{
          color: d.value >= 0 ? POSITIVE : NEGATIVE,
          display: 'block',
          fontWeight: 800,
          fontFamily: NUMERIC_FONT,
          fontSize: '0.74rem',
          mt: 0.15,
        }}
      >
        {fmtUsd(d.value)}
      </Typography>
    </Box>
  );
};

export default function PnLAttributionPanel() {
  const [collapsed, setCollapsed] = useState(false);
  const [data, setData] = useState(null);
  const [, setLoading] = useState(false);
  const timerRef = useRef(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await window.fetch('/api/options/pnl-attribution');
      if (!res.ok) return;
      const json = await res.json();
      if (json.success) setData(json.attribution);
    } catch (_) {
    } finally {
      setLoading(false);
    }
  }, []);

  const resetBaseline = useCallback(async () => {
    try {
      await window.fetch('/api/options/pnl-attribution/reset', { method: 'POST' });
      await fetchData();
    } catch (_) {}
  }, [fetchData]);

  useEffect(() => {
    fetchData();
    timerRef.current = setInterval(fetchData, 30_000);
    return () => clearInterval(timerRef.current);
  }, [fetchData]);

  const chartData = buildChartData(data);

  const headerContent = (
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 0.7, minHeight: 30 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8, flexWrap: 'wrap', rowGap: 0.45 }}>
        <TrendingUpIcon sx={{ fontSize: '1rem', color: alpha(ACCENT, 0.92) }} />
        <Typography
          variant="subtitle2"
          sx={{
            color: '#e2e8f0',
            fontWeight: 800,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            fontSize: '0.74rem',
            lineHeight: 1,
          }}
        >
          PnL Attribution
        </Typography>
        {data && (
          <Chip
            label={`Total: ${fmtUsd(data.total_change)}`}
            size="small"
            sx={{
              bgcolor: data.total_change >= 0 ? alpha(POSITIVE, 0.18) : alpha(NEGATIVE, 0.16),
              color: data.total_change >= 0 ? POSITIVE : NEGATIVE,
              border: `1px solid ${data.total_change >= 0 ? alpha(POSITIVE, 0.45) : alpha(NEGATIVE, 0.45)}`,
              fontSize: '0.63rem',
              height: 21,
              fontWeight: 800,
              letterSpacing: '0.02em',
              '& .MuiChip-label': { px: 0.85, fontFamily: NUMERIC_FONT },
            }}
          />
        )}
        {data && (
          <Typography
            variant="caption"
            sx={{
              color: alpha('#94a3b8', 0.85),
              fontSize: '0.64rem',
              fontWeight: 700,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            vs {data.elapsed_hours?.toFixed(1)}h ago
          </Typography>
        )}
      </Box>
      <Box sx={{ display: 'flex', gap: 0.5 }}>
        <Tooltip title="Reset baseline to now">
          <IconButton size="small" onClick={resetBaseline} sx={{ color: alpha('#94a3b8', 0.78), p: 0.45 }}>
            <RefreshIcon sx={{ fontSize: '0.9rem' }} />
          </IconButton>
        </Tooltip>
        <IconButton size="small" onClick={() => setCollapsed(c => !c)} sx={{ color: '#94a3b8', p: 0.45 }}>
          {collapsed ? <ExpandMoreIcon /> : <ExpandLessIcon />}
        </IconButton>
      </Box>
    </Box>
  );

  return (
    <Paper
      sx={{
        p: 1.25,
        bgcolor: alpha('#0b1220', 0.92),
        border: `1px solid ${alpha(ACCENT, 0.28)}`,
        borderRadius: 2.2,
        mb: 1,
        height: '100%',
        minHeight: CARD_MIN_HEIGHT,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        backgroundImage: `
          radial-gradient(circle at 96% 0%, ${alpha(ACCENT, 0.12)} 0%, transparent 34%),
          linear-gradient(180deg, ${alpha('#0f172a', 0.82)} 0%, ${alpha('#0b1220', 0.94)} 100%)
        `,
        boxShadow: `0 12px 26px ${alpha('#000', 0.45)}`,
      }}
    >
      {headerContent}
      {!collapsed && (
        <Box sx={{ mt: 1, display: 'flex', flexDirection: 'column', gap: 0.85, flex: 1 }}>
          {!data ? (
            <Typography variant="caption" sx={{ color: alpha('#94a3b8', 0.8), fontSize: '0.7rem' }}>
              Loading attribution data...
            </Typography>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={CHART_HEIGHT}>
                <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 20, bottom: 0, left: 64 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" horizontal={false} />
                  <XAxis
                    type="number" tick={{ fill: '#94a3b8', fontSize: 10 }}
                    axisLine={{ stroke: '#334155' }} tickLine={false}
                    tickFormatter={v => `$${v.toFixed(0)}`}
                  />
                  <YAxis
                    type="category" dataKey="name"
                    tick={{ fill: '#94a3b8', fontSize: 11 }}
                    axisLine={false} tickLine={false} width={55}
                  />
                  <RechartTooltip content={<CustomTooltip />} />
                  <ReferenceLine x={0} stroke="rgba(255,255,255,0.2)" />
                  <Bar dataKey="value" radius={[0, 3, 3, 0]}>
                    {chartData.map(entry => (
                      <Cell key={entry.key} fill={COLORS[entry.key]} opacity={0.9} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>

              {/* Context row */}
              <Box
                sx={{
                  display: 'grid',
                  gridTemplateColumns: { xs: '1fr', sm: 'repeat(3, minmax(0, 1fr))' },
                  rowGap: 0.4,
                  columnGap: 1.1,
                  mt: 'auto',
                  pt: 0.65,
                  minHeight: FOOTER_MIN_HEIGHT,
                  alignItems: 'center',
                  borderTop: `1px dashed ${alpha('#475569', 0.45)}`,
                }}
              >
                <Typography
                  variant="caption"
                  sx={{
                    color: alpha('#94a3b8', 0.86),
                    fontSize: '0.65rem',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  <Box component="span" sx={{ color: alpha('#cbd5e1', 0.92), fontWeight: 700, mr: 0.45 }}>Spot</Box>
                  ${data.baseline_spot?.toLocaleString()} → {data.spot_change >= 0 ? '+' : ''}${data.spot_change?.toLocaleString()}
                </Typography>
                <Typography
                  variant="caption"
                  sx={{
                    color: alpha('#94a3b8', 0.86),
                    fontSize: '0.65rem',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  <Box component="span" sx={{ color: alpha('#cbd5e1', 0.92), fontWeight: 700, mr: 0.45 }}>IV Avg</Box>
                  {data.baseline_iv_avg_pct?.toFixed(1)}% → {data.iv_change_pts >= 0 ? '+' : ''}{data.iv_change_pts?.toFixed(2)} pts
                </Typography>
                <Typography
                  variant="caption"
                  sx={{
                    color: alpha('#94a3b8', 0.86),
                    fontSize: '0.65rem',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  <Box component="span" sx={{ color: alpha('#cbd5e1', 0.92), fontWeight: 700, mr: 0.45 }}>Elapsed</Box>
                  {data.elapsed_hours?.toFixed(2)}h
                </Typography>
              </Box>
            </>
          )}
        </Box>
      )}
    </Paper>
  );
}
