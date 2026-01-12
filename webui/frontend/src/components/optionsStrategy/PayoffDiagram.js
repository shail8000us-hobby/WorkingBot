/**
 * Payoff Diagram
 * ==============
 * Visualize strategy payoff at expiration.
 * 
 * Created: January 5, 2026
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  CircularProgress,
  Alert,
  Chip,
  Stack
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
  ComposedChart
} from 'recharts';

const API_BASE = '/api/options-strategy';

// Format currency
const formatCurrency = (value) => {
  if (value === null || value === undefined) return '-';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0
  }).format(value);
};

// Custom tooltip
const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const value = payload[0].value;
    return (
      <Box
        sx={{
          bgcolor: 'background.paper',
          border: 1,
          borderColor: 'divider',
          borderRadius: 1,
          p: 1,
          boxShadow: 2
        }}
      >
        <Typography variant="caption" display="block">
          Price: {formatCurrency(label)}
        </Typography>
        <Typography
          variant="body2"
          fontWeight="bold"
          color={value >= 0 ? 'success.main' : 'error.main'}
        >
          P&L: {formatCurrency(value)}
        </Typography>
      </Box>
    );
  }
  return null;
};

export default function PayoffDiagram({ strategyId, data: directData, height = 300 }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    // If direct data is provided, use it
    if (directData) {
      // Calculate payoff from legs if needed
      if (directData.legs && !directData.price_points) {
        const calculated = calculatePayoffFromLegs(directData);
        setData(calculated);
      } else {
        setData(directData);
      }
      return;
    }
    
    if (strategyId) {
      fetchPayoffData();
    }
  }, [strategyId, directData]);
  
  // Calculate payoff locally from legs data
  const calculatePayoffFromLegs = (legData) => {
    const { legs, spot_price } = legData;
    if (!legs || legs.length === 0 || !spot_price) return null;
    
    // Generate price range (±25% from spot)
    const minPrice = spot_price * 0.75;
    const maxPrice = spot_price * 1.25;
    const numPoints = 100;
    const step = (maxPrice - minPrice) / numPoints;
    
    const pricePoints = [];
    const payoffValues = [];
    
    for (let i = 0; i <= numPoints; i++) {
      const price = minPrice + (i * step);
      pricePoints.push(price);
      
      let totalPayoff = 0;
      
      legs.forEach(leg => {
        const { option_type, side, strike, premium = 0, quantity = 1 } = leg;
        const sign = side === 'buy' ? 1 : -1;
        
        let intrinsicValue = 0;
        if (option_type === 'call') {
          intrinsicValue = Math.max(0, price - strike);
        } else {
          intrinsicValue = Math.max(0, strike - price);
        }
        
        // Payoff = (Intrinsic Value - Premium) * sign * quantity
        const legPayoff = ((intrinsicValue * sign) - (premium * sign)) * quantity;
        totalPayoff += legPayoff;
      });
      
      payoffValues.push(totalPayoff);
    }
    
    // Find max profit/loss and breakeven points
    const maxProfit = Math.max(...payoffValues);
    const maxLoss = Math.min(...payoffValues);
    
    // Find breakeven points (where payoff crosses zero)
    const breakevenPoints = [];
    for (let i = 1; i < payoffValues.length; i++) {
      if ((payoffValues[i-1] <= 0 && payoffValues[i] >= 0) ||
          (payoffValues[i-1] >= 0 && payoffValues[i] <= 0)) {
        breakevenPoints.push(pricePoints[i]);
      }
    }
    
    return {
      price_points: pricePoints,
      payoff_values: payoffValues,
      max_profit: maxProfit > 1000000 ? null : maxProfit,
      max_loss: maxLoss < -1000000 ? null : maxLoss,
      breakeven_points: breakevenPoints,
      current_price: spot_price
    };
  };

  const fetchPayoffData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const res = await fetch(
        `${API_BASE}/payoff/${strategyId}?price_range_pct=25&num_points=100`
      );
      const result = await res.json();
      
      if (result.error) {
        setError(result.error);
      } else {
        setData(result);
      }
    } catch (err) {
      setError(`Failed to load payoff data: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="warning" sx={{ m: 2 }}>
        {error}
      </Alert>
    );
  }

  if (!data || !data.price_points) {
    return (
      <Box sx={{ p: 2, textAlign: 'center' }}>
        <Typography color="text.secondary">
          No payoff data available
        </Typography>
      </Box>
    );
  }

  // Transform data for chart
  const chartData = data.price_points.map((price, i) => ({
    price,
    payoff: data.payoff_values[i]
  }));

  // Find zero crossing (breakeven) points
  const breakevenPoints = data.breakeven_points || [];

  return (
    <Box>
      {/* Stats */}
      <Stack direction="row" spacing={1} sx={{ mb: 2 }} flexWrap="wrap">
        <Chip
          label={`Max Profit: ${data.max_profit !== null ? formatCurrency(data.max_profit) : 'Unlimited'}`}
          color="success"
          size="small"
          variant="outlined"
        />
        <Chip
          label={`Max Loss: ${data.max_loss !== null ? formatCurrency(data.max_loss) : 'Unlimited'}`}
          color="error"
          size="small"
          variant="outlined"
        />
        {breakevenPoints.map((bp, i) => (
          <Chip
            key={i}
            label={`BE: ${formatCurrency(bp)}`}
            size="small"
            variant="outlined"
          />
        ))}
      </Stack>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
          <defs>
            <linearGradient id="profitGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#4caf50" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#4caf50" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="lossGradient" x1="0" y1="1" x2="0" y2="0">
              <stop offset="0%" stopColor="#f44336" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#f44336" stopOpacity={0} />
            </linearGradient>
          </defs>
          
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
          
          <XAxis
            dataKey="price"
            tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
            tick={{ fontSize: 11 }}
          />
          
          <YAxis
            tickFormatter={(v) => `$${v}`}
            tick={{ fontSize: 11 }}
            domain={['auto', 'auto']}
          />
          
          <Tooltip content={<CustomTooltip />} />
          
          {/* Zero line */}
          <ReferenceLine y={0} stroke="#666" strokeDasharray="3 3" />
          
          {/* Breakeven lines */}
          {breakevenPoints.map((bp, i) => (
            <ReferenceLine
              key={i}
              x={bp}
              stroke="#ff9800"
              strokeDasharray="5 5"
              label={{
                value: 'BE',
                position: 'top',
                fontSize: 10,
                fill: '#ff9800'
              }}
            />
          ))}
          
          {/* Area fill for profit/loss zones */}
          <Area
            type="monotone"
            dataKey="payoff"
            fill="url(#profitGradient)"
            stroke="none"
            fillOpacity={1}
            isAnimationActive={false}
            baseValue={0}
          />
          
          {/* Payoff line */}
          <Line
            type="monotone"
            dataKey="payoff"
            stroke="#1976d2"
            strokeWidth={2}
            dot={false}
            isAnimationActive={true}
            animationDuration={500}
          />
        </ComposedChart>
      </ResponsiveContainer>

      {/* Legend */}
      <Box sx={{ mt: 1, display: 'flex', justifyContent: 'center', gap: 2 }}>
        <Typography variant="caption" color="text.secondary">
          X-axis: Underlying Price at Expiration
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Y-axis: Profit/Loss ($)
        </Typography>
      </Box>
    </Box>
  );
}
