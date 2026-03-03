import React, { useMemo } from 'react';
import { Paper, Box, Typography, Chip } from '@mui/material';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Area,
  AreaChart
} from 'recharts';

const BreakevenChart = ({ data }) => {
  // Sample every nth point to keep chart readable
  const chartData = useMemo(() => {
    if (!data || !data.prices || !data.pnl) return [];
    const sampleRate = Math.max(1, Math.floor(data.prices.length / 50));
    return data.prices
      .filter((_, i) => i % sampleRate === 0)
      .map((price, i) => ({
        price: `$${Math.round(price).toLocaleString()}`,
        pnl: data.pnl.filter((_, j) => j % sampleRate === 0)[i],
      }));
  }, [data]);

  if (!data || !data.prices || !data.pnl) {
    return (
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>P&L at Expiry</Typography>
        <Typography variant="body2" color="text.secondary">
          No data available
        </Typography>
      </Paper>
    );
  }

  const customTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div style={{
          background: 'rgba(30, 41, 59, 0.95)',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 6,
          padding: '8px 12px',
        }}>
          <p style={{ margin: 0, color: '#94a3b8', fontSize: 12 }}>{label}</p>
          <p style={{ margin: 0, color: payload[0].value >= 0 ? '#4ade80' : '#f87171', fontWeight: 600 }}>
            P&L: ${payload[0].value?.toFixed(2)}
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <Paper sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">P&L at Expiry</Typography>
        {data.breakeven_points && data.breakeven_points.length > 0 && (
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Chip 
              label={`Lower BE: $${Math.round(data.breakeven_points[0]).toLocaleString()}`}
              size="small"
              color="info"
            />
            {data.breakeven_points[1] && (
              <Chip 
                label={`Upper BE: $${Math.round(data.breakeven_points[1]).toLocaleString()}`}
                size="small"
                color="info"
              />
            )}
          </Box>
        )}
      </Box>

      <Box sx={{ height: 300 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
            <defs>
              <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="rgb(75, 192, 192)" stopOpacity={0.4} />
                <stop offset="50%" stopColor="rgb(255, 255, 255)" stopOpacity={0.1} />
                <stop offset="100%" stopColor="rgb(255, 99, 132)" stopOpacity={0.4} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.05)" />
            <XAxis
              dataKey="price"
              stroke="rgba(255, 255, 255, 0.3)"
              tick={{ fontSize: 11, fill: 'rgba(255,255,255,0.6)' }}
              interval={Math.max(0, Math.floor(chartData.length / 8) - 1)}
            />
            <YAxis
              stroke="rgba(255, 255, 255, 0.3)"
              tick={{ fontSize: 11, fill: 'rgba(255,255,255,0.6)' }}
              tickFormatter={(v) => `$${v.toFixed(0)}`}
            />
            <Tooltip content={customTooltip} />
            <Legend />
            <ReferenceLine y={0} stroke="rgba(255, 255, 255, 0.5)" strokeDasharray="5 5" label="" />
            <Area
              type="monotone"
              dataKey="pnl"
              name="P&L at Expiry"
              stroke="rgb(75, 192, 192)"
              fill="url(#pnlGradient)"
              strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>
      </Box>

      {/* Summary Stats */}
      {data.strike && (
        <Box sx={{ mt: 2, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <Box>
            <Typography variant="caption" color="text.secondary">Strike</Typography>
            <Typography variant="body2" fontWeight="bold">
              ${data.strike.toLocaleString()}
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">Total Premium</Typography>
            <Typography variant="body2" fontWeight="bold">
              ${data.total_premium?.toFixed(2)}
            </Typography>
          </Box>
          {data.breakeven_points && data.breakeven_points.length >= 2 && (
            <Box>
              <Typography variant="caption" color="text.secondary">Profit Range</Typography>
              <Typography variant="body2" fontWeight="bold">
                ${Math.round(data.breakeven_points[1] - data.breakeven_points[0]).toLocaleString()}
              </Typography>
            </Box>
          )}
        </Box>
      )}
    </Paper>
  );
};

export default BreakevenChart;
