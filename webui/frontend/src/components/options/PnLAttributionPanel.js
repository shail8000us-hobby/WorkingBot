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
    <Box sx={{ bgcolor: '#1e293b', border: '1px solid #334155', borderRadius: 1, p: 1 }}>
      <Typography variant="caption" sx={{ color: '#e2e8f0', fontWeight: 600 }}>{d.name}</Typography>
      <Typography variant="caption" sx={{ color: d.value >= 0 ? '#10b981' : '#ef4444', display: 'block' }}>
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
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <TrendingUpIcon sx={{ fontSize: '1rem', color: '#94a3b8' }} />
        <Typography variant="subtitle2" sx={{ color: '#e2e8f0', fontWeight: 600 }}>
          PnL Attribution
        </Typography>
        {data && (
          <Chip
            label={`Total: ${fmtUsd(data.total_change)}`}
            size="small"
            sx={{
              bgcolor: data.total_change >= 0 ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)',
              color: data.total_change >= 0 ? '#10b981' : '#ef4444',
              fontSize: '0.65rem', height: 18,
            }}
          />
        )}
        {data && (
          <Typography variant="caption" sx={{ color: '#64748b' }}>
            vs {data.elapsed_hours?.toFixed(1)}h ago
          </Typography>
        )}
      </Box>
      <Box sx={{ display: 'flex', gap: 0.5 }}>
        <Tooltip title="Reset baseline to now">
          <IconButton size="small" onClick={resetBaseline} sx={{ color: '#64748b', p: 0.5 }}>
            <RefreshIcon sx={{ fontSize: '0.9rem' }} />
          </IconButton>
        </Tooltip>
        <IconButton size="small" onClick={() => setCollapsed(c => !c)} sx={{ color: '#94a3b8' }}>
          {collapsed ? <ExpandMoreIcon /> : <ExpandLessIcon />}
        </IconButton>
      </Box>
    </Box>
  );

  return (
    <Paper sx={{ p: 1.5, bgcolor: 'rgba(15, 23, 42, 0.8)', border: '1px solid rgba(71, 85, 105, 0.3)', mb: 1 }}>
      {headerContent}
      {!collapsed && (
        <Box sx={{ mt: 1.5 }}>
          {!data ? (
            <Typography variant="caption" sx={{ color: '#64748b' }}>
              Loading attribution data...
            </Typography>
          ) : (
            <>
              <ResponsiveContainer width="100%" height={120}>
                <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 20, bottom: 0, left: 60 }}>
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
                      <Cell key={entry.key} fill={COLORS[entry.key]} opacity={0.85} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>

              {/* Context row */}
              <Box sx={{ display: 'flex', gap: 2, mt: 1, flexWrap: 'wrap' }}>
                <Typography variant="caption" sx={{ color: '#64748b' }}>
                  Spot: ${data.baseline_spot?.toLocaleString()} → {data.spot_change >= 0 ? '+' : ''}${data.spot_change?.toLocaleString()}
                </Typography>
                <Typography variant="caption" sx={{ color: '#64748b' }}>
                  IV avg: {data.baseline_iv_avg_pct?.toFixed(1)}% → {data.iv_change_pts >= 0 ? '+' : ''}{data.iv_change_pts?.toFixed(2)} pts
                </Typography>
                <Typography variant="caption" sx={{ color: '#64748b' }}>
                  Time: {data.elapsed_hours?.toFixed(2)}h elapsed
                </Typography>
              </Box>
            </>
          )}
        </Box>
      )}
    </Paper>
  );
}
