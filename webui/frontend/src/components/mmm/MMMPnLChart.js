/**
 * MMMPnLChart — Money Mind & Method
 *
 * Real-time P&L chart using Recharts:
 * - Total P&L line (bold)
 * - Realized P&L area (green fill)
 * - Unrealized P&L line (dashed)
 * - Adjustment markers
 * - Peak line overlay for trailing profit tracking
 * - Cumulative premium overlay
 *
 * Maps to MONEY_POWER_CALCULATION_LOGIC.md §14.6 (Trailing), §6.4 (Updates)
 *
 * Created: February 15, 2026
 */

import React, { useMemo } from 'react';
import {
  Box,
  Typography,
  Paper,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';

// Conditional Recharts import — may not be available in all environments
let LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer,
  ReferenceLine, Area, ComposedChart, Legend, Tooltip;

try {
  const recharts = require('recharts');
  LineChart = recharts.LineChart;
  Line = recharts.Line;
  XAxis = recharts.XAxis;
  YAxis = recharts.YAxis;
  CartesianGrid = recharts.CartesianGrid;
  ResponsiveContainer = recharts.ResponsiveContainer;
  ReferenceLine = recharts.ReferenceLine;
  Area = recharts.Area;
  ComposedChart = recharts.ComposedChart;
  Legend = recharts.Legend;
  Tooltip = recharts.Tooltip;
} catch {
  // Recharts not available
}

function formatTime(timestamp) {
  if (!timestamp) return '';
  try {
    const d = new Date(timestamp);
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  } catch { return ''; }
}

function formatPnl(value) {
  if (value == null) return '--';
  return `$${Number(value).toFixed(0)}`;
}

export default function MMMPnLChart({ session, pnlData }) {
  const [view, setView] = React.useState('all');

  const chartData = useMemo(() => {
    const history = session?.pnl_history || [];
    return history.map((h) => ({
      time: formatTime(h.timestamp),
      total: h.total_pnl || 0,
      realized: h.realized || 0,
      unrealized: h.unrealized || 0,
      ceP: h.ce_premium || 0,
      peP: h.pe_premium || 0,
    }));
  }, [session]);

  const peakPnl = session?.peak_pnl || 0;
  const trailingPct = session?.params?.trailing_stop_pct || 0.5;
  const trailingFloor = peakPnl * trailingPct;

  // If Recharts not available, show text fallback
  if (!ComposedChart) {
    const latest = pnlData || {};
    return (
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
          P&L Summary
        </Typography>
        <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary', lineHeight: 1.5, mb: 1, fontStyle: 'italic', fontSize: '0.7rem', opacity: 0.75 }}>
          💡 Total P&L = Realized (locked profits from closed positions) + Unrealized (paper P&L of open positions) − Fees. The chart plots this over time once heartbeat data accumulates.
        </Typography>
        <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
          <Box>
            <Typography variant="caption" color="text.secondary">Total (net)</Typography>
            <Typography variant="h6" sx={{
              fontFamily: 'monospace',
              color: (latest.total_pnl || 0) >= 0 ? '#4caf50' : '#f44336',
            }}>
              {formatPnl(latest.total_pnl)}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">Realized (locked)</Typography>
            <Typography variant="h6" sx={{ fontFamily: 'monospace' }}>
              {formatPnl(latest.realized)}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">Unrealized (paper)</Typography>
            <Typography variant="h6" sx={{ fontFamily: 'monospace' }}>
              {formatPnl(latest.unrealized)}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">Fees</Typography>
            <Typography variant="h6" sx={{ fontFamily: 'monospace' }}>
              {formatPnl(latest.fees)}
            </Typography>
          </Box>
        </Box>
      </Paper>
    );
  }

  if (chartData.length < 2) {
    return (
      <Paper variant="outlined" sx={{ p: 3, borderRadius: 2, textAlign: 'center' }}>
        <Typography color="text.secondary">
          P&L chart will appear after multiple heartbeats. Each heartbeat (every {session?.params?.adjustment_interval || 300}s) records a snapshot of your positions' value.
        </Typography>
      </Paper>
    );
  }

  return (
    <Paper variant="outlined" sx={{ borderRadius: 2 }}>
      <Box sx={{ px: 2, py: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          P&L Chart
        </Typography>
        <ToggleButtonGroup
          value={view}
          exclusive
          onChange={(_, v) => v && setView(v)}
          size="small"
        >
          <ToggleButton value="all" sx={{ fontSize: '0.78rem', py: 0.25 }}>All</ToggleButton>
          <ToggleButton value="pnl" sx={{ fontSize: '0.78rem', py: 0.25 }}>P&L</ToggleButton>
          <ToggleButton value="premiums" sx={{ fontSize: '0.78rem', py: 0.25 }}>Premiums</ToggleButton>
        </ToggleButtonGroup>
      </Box>

      <Box sx={{ width: '100%', height: 250, px: 1, pb: 1 }}>
        <ResponsiveContainer>
          <ComposedChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
            <XAxis dataKey="time" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `$${v}`} />
            <Tooltip
              contentStyle={{
                background: '#1a1a2e',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: 8,
                fontSize: '0.75rem',
              }}
              formatter={(value, name) => [`$${Number(value).toFixed(2)}`, name]}
            />
            <Legend wrapperStyle={{ fontSize: '0.7rem' }} />

            {/* Zero line */}
            <ReferenceLine y={0} stroke="rgba(255,255,255,0.3)" strokeDasharray="3 3" />

            {/* Peak line for trailing stop */}
            {peakPnl > 0 && (
              <>
                <ReferenceLine
                  y={peakPnl}
                  stroke="#FFD600"
                  strokeDasharray="5 5"
                  label={{ value: `Peak: $${peakPnl.toFixed(0)}`, fontSize: 10, fill: '#FFD600' }}
                />
                <ReferenceLine
                  y={trailingFloor}
                  stroke="#ff9800"
                  strokeDasharray="3 3"
                  label={{ value: `Floor: $${trailingFloor.toFixed(0)}`, fontSize: 10, fill: '#ff9800' }}
                />
              </>
            )}

            {(view === 'all' || view === 'pnl') && (
              <>
                {/* Realized area fill */}
                <Area
                  type="monotone"
                  dataKey="realized"
                  name="Realized"
                  fill="rgba(76,175,80,0.15)"
                  stroke="#4caf50"
                  strokeWidth={1}
                />
                {/* Total P&L line */}
                <Line
                  type="monotone"
                  dataKey="total"
                  name="Total P&L"
                  stroke="#00C853"
                  strokeWidth={2}
                  dot={false}
                />
                {/* Unrealized dashed */}
                <Line
                  type="monotone"
                  dataKey="unrealized"
                  name="Unrealized"
                  stroke="#ff9800"
                  strokeWidth={1}
                  strokeDasharray="4 4"
                  dot={false}
                />
              </>
            )}

            {(view === 'all' || view === 'premiums') && (
              <>
                <Line
                  type="monotone"
                  dataKey="ceP"
                  name="CE Premium"
                  stroke="#2196f3"
                  strokeWidth={1}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="peP"
                  name="PE Premium"
                  stroke="#9c27b0"
                  strokeWidth={1}
                  dot={false}
                />
              </>
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </Box>
    </Paper>
  );
}
