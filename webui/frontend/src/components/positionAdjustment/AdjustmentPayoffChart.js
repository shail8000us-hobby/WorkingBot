/**
 * Adjustment Payoff Chart
 * =======================
 * Dual-line payoff comparison chart for position adjustment.
 * 
 * Features:
 * - Solid line: Current positions payoff at expiry
 * - Dashed line: Proposed combined payoff at expiry
 * - Vertical line at current spot price
 * - Breakeven markers
 * - Profit/Loss zone shading
 * - Interactive tooltips
 * 
 * Created: January 31, 2026
 */

import React, { useMemo } from 'react';
import {
  Box,
  Typography,
  Paper,
  Chip,
  useTheme,
} from '@mui/material';
import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts';

// Color scheme
const COLORS = {
  current: '#4caf50',       // Green for current position
  combined: '#2196f3',      // Blue for combined (proposed)
  profit: 'rgba(76, 175, 80, 0.15)',
  loss: 'rgba(244, 67, 54, 0.15)',
  spotLine: '#ffc107',      // Yellow for spot price
  breakeven: '#9c27b0',     // Purple for breakeven
  grid: 'rgba(255, 255, 255, 0.1)',
  text: 'rgba(255, 255, 255, 0.7)',
};

/**
 * Custom tooltip component
 */
const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload || payload.length === 0) return null;

  return (
    <Paper sx={{ 
      p: 1.5, 
      backgroundColor: 'rgba(30, 30, 46, 0.95)',
      border: '1px solid rgba(255, 255, 255, 0.1)',
      boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
    }}>
      <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 0.5 }}>
        Price: ${Number(label).toLocaleString()}
      </Typography>
      
      {payload.map((entry, index) => {
        const value = entry.value;
        const isProfit = value >= 0;
        const color = entry.dataKey === 'current' ? COLORS.current : COLORS.combined;
        const label = entry.dataKey === 'current' ? 'Current' : 'After Adjustment';
        
        return (
          <Box key={index} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box sx={{ 
              width: 12, 
              height: 12, 
              borderRadius: '50%', 
              backgroundColor: color,
            }} />
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
              {label}:
            </Typography>
            <Typography
              variant="body2"
              sx={{ 
                fontWeight: 'bold',
                color: isProfit ? '#4caf50' : '#f44336',
              }}
            >
              {isProfit ? '+' : ''}{value?.toFixed(2)} USD
            </Typography>
          </Box>
        );
      })}
      
      {/* Show difference if both values exist */}
      {payload.length === 2 && (
        <Box sx={{ mt: 1, pt: 1, borderTop: '1px solid rgba(255,255,255,0.1)' }}>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>
            Difference: {(payload[1].value - payload[0].value) >= 0 ? '+' : ''}
            {((payload[1].value || 0) - (payload[0].value || 0)).toFixed(2)} USD
          </Typography>
        </Box>
      )}
    </Paper>
  );
};

/**
 * Custom legend component
 */
const CustomLegend = ({ hasProposedTrades }) => (
  <Box sx={{ 
    display: 'flex', 
    justifyContent: 'center', 
    gap: 3, 
    mt: 1,
    pb: 1,
  }}>
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <Box sx={{ 
        width: 20, 
        height: 3, 
        backgroundColor: COLORS.current,
        borderRadius: 1,
      }} />
      <Typography variant="caption" sx={{ color: 'text.secondary' }}>
        Current Position
      </Typography>
    </Box>
    
    {hasProposedTrades && (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Box sx={{ 
          width: 20, 
          height: 3, 
          backgroundColor: COLORS.combined,
          borderRadius: 1,
          backgroundImage: 'repeating-linear-gradient(90deg, transparent, transparent 3px, #2196f3 3px, #2196f3 6px)',
        }} />
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
          After Adjustment
        </Typography>
      </Box>
    )}
  </Box>
);

/**
 * AdjustmentPayoffChart Component
 */
export default function AdjustmentPayoffChart({
  chartData = [],
  spotPrice,
  currentBreakevens = [],
  combinedBreakevens = [],
  hasProposedTrades = false,
  height = 300,
}) {
  const theme = useTheme();

  // Calculate Y-axis domain with padding
  const yDomain = useMemo(() => {
    if (!chartData || chartData.length === 0) return [-100, 100];
    
    const allValues = chartData.flatMap(d => [
      d.current,
      hasProposedTrades ? d.combined : null,
    ].filter(v => v != null));
    
    if (allValues.length === 0) return [-100, 100];
    
    const min = Math.min(...allValues);
    const max = Math.max(...allValues);
    const padding = Math.abs(max - min) * 0.15 || 50;
    
    return [
      Math.floor((min - padding) / 10) * 10,
      Math.ceil((max + padding) / 10) * 10,
    ];
  }, [chartData, hasProposedTrades]);

  // Format Y-axis tick
  const formatYAxis = (value) => {
    if (Math.abs(value) >= 1000) {
      return `$${(value / 1000).toFixed(1)}K`;
    }
    return `$${value}`;
  };

  // Format X-axis tick
  const formatXAxis = (value) => {
    if (value >= 1000) {
      return `${(value / 1000).toFixed(0)}K`;
    }
    return value;
  };

  // Empty state
  if (!chartData || chartData.length === 0) {
    return (
      <Box sx={{ 
        height, 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        border: '1px dashed rgba(255,255,255,0.2)',
        borderRadius: 2,
        backgroundColor: 'rgba(255,255,255,0.02)',
      }}>
        <Typography variant="body2" color="text.secondary">
          No payoff data available
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ width: '100%', height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart
          data={chartData}
          margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
        >
          <defs>
            {/* Gradient for profit zone */}
            <linearGradient id="profitGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#4caf50" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#4caf50" stopOpacity={0} />
            </linearGradient>
            
            {/* Gradient for loss zone */}
            <linearGradient id="lossGradient" x1="0" y1="1" x2="0" y2="0">
              <stop offset="0%" stopColor="#f44336" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#f44336" stopOpacity={0} />
            </linearGradient>
          </defs>

          <CartesianGrid 
            strokeDasharray="3 3" 
            stroke={COLORS.grid}
            vertical={false}
          />

          <XAxis
            dataKey="price"
            tickFormatter={formatXAxis}
            stroke={COLORS.text}
            tick={{ fill: COLORS.text, fontSize: 11 }}
            axisLine={{ stroke: COLORS.grid }}
            tickLine={{ stroke: COLORS.grid }}
          />

          <YAxis
            domain={yDomain}
            tickFormatter={formatYAxis}
            stroke={COLORS.text}
            tick={{ fill: COLORS.text, fontSize: 11 }}
            axisLine={{ stroke: COLORS.grid }}
            tickLine={{ stroke: COLORS.grid }}
          />

          <Tooltip content={<CustomTooltip />} />

          {/* Zero line (profit/loss boundary) */}
          <ReferenceLine
            y={0}
            stroke="rgba(255, 255, 255, 0.3)"
            strokeWidth={1}
          />

          {/* Current spot price line */}
          {spotPrice && (
            <ReferenceLine
              x={spotPrice}
              stroke={COLORS.spotLine}
              strokeWidth={2}
              strokeDasharray="5 5"
              label={{
                value: `Spot: $${spotPrice.toLocaleString()}`,
                position: 'top',
                fill: COLORS.spotLine,
                fontSize: 11,
              }}
            />
          )}

          {/* Current breakeven lines */}
          {currentBreakevens.map((be, idx) => (
            <ReferenceLine
              key={`current-be-${idx}`}
              x={be}
              stroke={COLORS.current}
              strokeWidth={1}
              strokeDasharray="2 2"
            />
          ))}

          {/* Combined breakeven lines */}
          {hasProposedTrades && combinedBreakevens.map((be, idx) => (
            <ReferenceLine
              key={`combined-be-${idx}`}
              x={be}
              stroke={COLORS.combined}
              strokeWidth={1}
              strokeDasharray="4 2"
            />
          ))}

          {/* Current position payoff line */}
          <Line
            type="monotone"
            dataKey="current"
            name="Current"
            stroke={COLORS.current}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: COLORS.current }}
          />

          {/* Combined position payoff line (dashed) */}
          {hasProposedTrades && (
            <Line
              type="monotone"
              dataKey="combined"
              name="After Adjustment"
              stroke={COLORS.combined}
              strokeWidth={2}
              strokeDasharray="6 3"
              dot={false}
              activeDot={{ r: 4, fill: COLORS.combined }}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>

      {/* Custom Legend */}
      <CustomLegend hasProposedTrades={hasProposedTrades} />

      {/* Breakeven labels */}
      {(currentBreakevens.length > 0 || combinedBreakevens.length > 0) && (
        <Box sx={{ 
          display: 'flex', 
          justifyContent: 'center', 
          gap: 2, 
          flexWrap: 'wrap',
          mt: 1,
        }}>
          {currentBreakevens.length > 0 && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                Current BE:
              </Typography>
              {currentBreakevens.map((be, idx) => (
                <Chip
                  key={idx}
                  label={`$${be.toLocaleString()}`}
                  size="small"
                  sx={{
                    backgroundColor: 'rgba(76, 175, 80, 0.2)',
                    color: COLORS.current,
                    fontSize: '0.7rem',
                    height: 20,
                  }}
                />
              ))}
            </Box>
          )}
          
          {hasProposedTrades && combinedBreakevens.length > 0 && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                New BE:
              </Typography>
              {combinedBreakevens.map((be, idx) => (
                <Chip
                  key={idx}
                  label={`$${be.toLocaleString()}`}
                  size="small"
                  sx={{
                    backgroundColor: 'rgba(33, 150, 243, 0.2)',
                    color: COLORS.combined,
                    fontSize: '0.7rem',
                    height: 20,
                  }}
                />
              ))}
            </Box>
          )}
        </Box>
      )}
    </Box>
  );
}
