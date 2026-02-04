/**
 * SSR Algo Payoff Chart
 * 
 * Displays the payoff curve for an SSR Algo session with
 * max loss zone markers and current price indicator.
 * 
 * Created: February 2, 2026
 */

import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import {
  Box,
  Typography,
  Paper,
  CircularProgress,
} from '@mui/material';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Area,
  ComposedChart,
} from 'recharts';

/**
 * Custom tooltip for payoff chart
 */
const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload || !payload.length) return null;

  const pnl = payload[0]?.value;
  const isProfit = pnl >= 0;

  return (
    <Paper sx={{ 
      p: 1.5, 
      bgcolor: 'rgba(15, 23, 42, 0.95)',
      border: '1px solid rgba(56, 189, 248, 0.3)',
      borderRadius: 2,
      boxShadow: '0 4px 12px rgba(0, 0, 0, 0.4)'
    }}>
      <Typography variant="body2" sx={{ color: 'rgba(148, 163, 184, 0.9)', mb: 0.5 }}>
        Price: <strong style={{ color: '#fff' }}>${label?.toLocaleString()}</strong>
      </Typography>
      <Typography 
        variant="body2" 
        sx={{ 
          color: isProfit ? '#4ade80' : '#f87171',
          fontWeight: 700,
          fontSize: '1rem'
        }}
      >
        P&L: ${pnl?.toFixed(2)}
      </Typography>
    </Paper>
  );
};

/**
 * Payoff chart component
 */
const SSRAlgoPayoffChart = ({
  payoffCurve = [],
  maxLossPoints = {},
  adjustmentTriggers = {},
  breakevens = [],
  spotPrice = 0,
  currentPrice = 0,
  height = 300,
  loading = false,
}) => {
  // Process data for chart
  const chartData = useMemo(() => {
    if (!payoffCurve || payoffCurve.length === 0) return [];
    
    return payoffCurve.map(point => ({
      price: point.price,
      pnl: point.pnl,
      // Add profit/loss areas
      profit: point.pnl >= 0 ? point.pnl : null,
      loss: point.pnl < 0 ? point.pnl : null,
    }));
  }, [payoffCurve]);

  // Calculate Y-axis domain
  const yDomain = useMemo(() => {
    if (chartData.length === 0) return [-100, 100];
    
    const pnls = chartData.map(d => d.pnl);
    const min = Math.min(...pnls);
    const max = Math.max(...pnls);
    const padding = (max - min) * 0.1;
    
    return [Math.floor(min - padding), Math.ceil(max + padding)];
  }, [chartData]);

  // Calculate X-axis domain
  const xDomain = useMemo(() => {
    if (chartData.length === 0) return [0, 100000];
    
    const prices = chartData.map(d => d.price);
    return [Math.min(...prices), Math.max(...prices)];
  }, [chartData]);

  if (loading) {
    return (
      <Box sx={{ 
        display: 'flex', 
        flexDirection: 'column',
        justifyContent: 'center', 
        alignItems: 'center', 
        height,
        background: 'rgba(0, 0, 0, 0.1)',
        borderRadius: 2
      }}>
        <CircularProgress size={40} sx={{ color: '#38bdf8' }} />
        <Typography sx={{ mt: 2, color: 'rgba(148, 163, 184, 0.7)' }}>
          Loading payoff data...
        </Typography>
      </Box>
    );
  }

  if (chartData.length === 0) {
    return (
      <Box sx={{ 
        display: 'flex', 
        flexDirection: 'column',
        justifyContent: 'center', 
        alignItems: 'center', 
        height, 
        color: 'text.secondary',
        background: 'rgba(0, 0, 0, 0.1)',
        borderRadius: 2
      }}>
        <Typography sx={{ fontSize: '3rem', mb: 1 }}>📈</Typography>
        <Typography sx={{ color: 'rgba(148, 163, 184, 0.7)' }}>No payoff data available</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ width: '100%', height }}>
      <ResponsiveContainer>
        <ComposedChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <defs>
            {/* Gradient for profit area */}
            <linearGradient id="profitGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#4ade80" stopOpacity={0.4}/>
              <stop offset="95%" stopColor="#4ade80" stopOpacity={0}/>
            </linearGradient>
            {/* Gradient for loss area */}
            <linearGradient id="lossGradient" x1="0" y1="1" x2="0" y2="0">
              <stop offset="5%" stopColor="#f87171" stopOpacity={0.4}/>
              <stop offset="95%" stopColor="#f87171" stopOpacity={0}/>
            </linearGradient>
          </defs>
          
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.2)" />
          
          <XAxis 
            dataKey="price" 
            domain={xDomain}
            tickFormatter={(value) => `${(value / 1000).toFixed(0)}k`}
            tick={{ fontSize: 11, fill: 'rgba(148, 163, 184, 0.8)' }}
            stroke="rgba(148, 163, 184, 0.3)"
          />
          
          <YAxis 
            domain={yDomain}
            tickFormatter={(value) => {
              // Format based on value magnitude
              if (Math.abs(value) >= 1000) return `$${(value / 1000).toFixed(1)}k`;
              if (Math.abs(value) >= 1) return `$${value.toFixed(0)}`;
              return `$${value.toFixed(2)}`;
            }}
            tick={{ fontSize: 11, fill: 'rgba(148, 163, 184, 0.8)' }}
            stroke="rgba(148, 163, 184, 0.3)"
            width={60}
          />
          
          <Tooltip content={<CustomTooltip />} />

          {/* Zero line */}
          <ReferenceLine y={0} stroke="rgba(148, 163, 184, 0.5)" strokeWidth={1} />

          {/* ADJUSTMENT TRIGGER ZONES - Key visual indicator */}
          {adjustmentTriggers.lower_trigger && (
            <ReferenceLine 
              x={adjustmentTriggers.lower_trigger} 
              stroke="#ef4444" 
              strokeWidth={3}
              label={{ 
                value: `⚠️ Adjust @ ${(adjustmentTriggers.lower_trigger/1000).toFixed(1)}k`, 
                position: 'insideBottomLeft', 
                fill: '#ef4444',
                fontSize: 11,
                fontWeight: 700
              }}
            />
          )}
          {adjustmentTriggers.upper_trigger && (
            <ReferenceLine 
              x={adjustmentTriggers.upper_trigger} 
              stroke="#ef4444" 
              strokeWidth={3}
              label={{ 
                value: `⚠️ Adjust @ ${(adjustmentTriggers.upper_trigger/1000).toFixed(1)}k`, 
                position: 'insideBottomRight', 
                fill: '#ef4444',
                fontSize: 11,
                fontWeight: 700
              }}
            />
          )}

          {/* Max loss zone markers (for reference) */}
          {maxLossPoints.max_loss_lower && (
            <ReferenceLine 
              x={maxLossPoints.max_loss_lower} 
              stroke="#f87171" 
              strokeDasharray="5 5"
              strokeWidth={2}
              label={{ 
                value: 'Max Loss Lower', 
                position: 'top', 
                fill: '#f87171',
                fontSize: 10
              }}
            />
          )}
          {maxLossPoints.max_loss_upper && (
            <ReferenceLine 
              x={maxLossPoints.max_loss_upper} 
              stroke="#f87171" 
              strokeDasharray="5 5"
              strokeWidth={2}
              label={{ 
                value: 'Max Loss Upper', 
                position: 'top', 
                fill: '#f87171',
                fontSize: 10
              }}
            />
          )}

          {/* Breakeven lines */}
          {breakevens.map((be, idx) => (
            <ReferenceLine 
              key={idx}
              x={be} 
              stroke="#fbbf24" 
              strokeDasharray="3 3"
              strokeWidth={1}
            />
          ))}

          {/* Current price marker */}
          {currentPrice > 0 && (
            <ReferenceLine 
              x={currentPrice} 
              stroke="#38bdf8" 
              strokeWidth={2}
              label={{ 
                value: `$${currentPrice.toLocaleString()}`, 
                position: 'top', 
                fill: '#38bdf8',
                fontSize: 11
              }}
            />
          )}

          {/* ATM/Spot price marker */}
          {spotPrice > 0 && spotPrice !== currentPrice && (
            <ReferenceLine 
              x={spotPrice} 
              stroke="#a78bfa" 
              strokeDasharray="2 2"
              strokeWidth={1}
            />
          )}

          {/* Profit area */}
          <Area
            type="monotone"
            dataKey="profit"
            stroke="none"
            fill="url(#profitGradient)"
          />

          {/* Loss area */}
          <Area
            type="monotone"
            dataKey="loss"
            stroke="none"
            fill="url(#lossGradient)"
          />

          {/* Main payoff line */}
          <Line 
            type="monotone" 
            dataKey="pnl" 
            stroke="#38bdf8" 
            strokeWidth={2.5}
            dot={false}
            activeDot={{ r: 6, fill: '#38bdf8', stroke: '#fff', strokeWidth: 2 }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </Box>
  );
};

// PropTypes
SSRAlgoPayoffChart.propTypes = {
  /** Array of payoff data points [{price, pnl}, ...] */
  payoffData: PropTypes.arrayOf(
    PropTypes.shape({
      price: PropTypes.number,
      pnl: PropTypes.number,
    })
  ),
  /** Max loss detection results */
  maxLossPoints: PropTypes.shape({
    max_loss_upper: PropTypes.number,
    max_loss_lower: PropTypes.number,
    max_profit_price: PropTypes.number,
    max_profit_value: PropTypes.number,
  }),
  /** Array of breakeven prices */
  breakevens: PropTypes.arrayOf(PropTypes.number),
  /** Current underlying price */
  currentPrice: PropTypes.number,
  /** Initial spot price at session creation */
  spotPrice: PropTypes.number,
  /** Chart height in pixels */
  height: PropTypes.number,
};

SSRAlgoPayoffChart.defaultProps = {
  payoffData: [],
  maxLossPoints: {},
  breakevens: [],
  currentPrice: 0,
  spotPrice: 0,
  height: 300,
};

export default SSRAlgoPayoffChart;
