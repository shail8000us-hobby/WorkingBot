/**
 * Probability Analysis Panel
 * 
 * Shows probability distributions and risk metrics:
 * - Probability of Profit (PoP)
 * - Expected Value
 * - Value-at-Risk (VaR)
 * - Monte Carlo simulation results
 * 
 * Created: January 23, 2026
 * Part of: PAYOFF_GRAPH_ENHANCEMENT_PLAN.md Phase 3
 */

import React, { useState, useEffect, useMemo } from 'react';
import {
  Paper,
  Box,
  Typography,
  Grid,
  Chip,
  Button,
  CircularProgress,
  Alert,
  Stack,
} from '@mui/material';
import {
  TrendingUp as ProfitIcon,
  TrendingDown as LossIcon,
  ShowChart as ExpectedValueIcon,
  Warning as RiskIcon,
} from '@mui/icons-material';
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ReferenceLine,
  Area,
} from 'recharts';
import api from '../../utils/apiShim';

const ProbabilityAnalysisPanel = ({ positions, spotPrice, volatility, timeToExpiry }) => {
  const [loading, setLoading] = useState(false);
  const [probabilityData, setProbabilityData] = useState(null);
  const [monteCarloData, setMonteCarloData] = useState(null);
  const [error, setError] = useState(null);

  // Calculate probability metrics
  useEffect(() => {
    if (!positions || positions.length === 0 || !spotPrice || !volatility || timeToExpiry === undefined) {
      return;
    }

    calculateProbability();
  }, [positions, spotPrice, volatility, timeToExpiry]);

  const calculateProbability = async () => {
    setLoading(true);
    setError(null);

    try {
      // Calculate PoP
      const popResponse = await api.post('/api/enhanced-options/probability/pop', {
        positions: positions.map(p => ({
          strike: p.strike,
          option_type: p.option_type || (p.product_symbol?.includes('-C-') ? 'call' : 'put'),
          side: p.side || (p.size > 0 ? 'buy' : 'sell'),
          quantity: Math.abs(p.size),
          entry_price: p.entry_price,
        })),
        spot_price: spotPrice,
        volatility: volatility,
        time_to_expiry: timeToExpiry,
        risk_free_rate: 0.0,
      });

      setProbabilityData(popResponse.data);

      // Run Monte Carlo simulation
      const mcResponse = await api.post('/api/enhanced-options/probability/monte-carlo', {
        positions: positions.map(p => ({
          strike: p.strike,
          option_type: p.option_type || (p.product_symbol?.includes('-C-') ? 'call' : 'put'),
          side: p.side || (p.size > 0 ? 'buy' : 'sell'),
          quantity: Math.abs(p.size),
          entry_price: p.entry_price,
        })),
        spot_price: spotPrice,
        volatility: volatility,
        time_to_expiry: timeToExpiry,
        risk_free_rate: 0.0,
        num_simulations: 10000,
      });

      setMonteCarloData(mcResponse.data);
    } catch (err) {
      setError(err.message || 'Failed to calculate probability metrics');
      console.error('Probability calculation error:', err);
    } finally {
      setLoading(false);
    }
  };

  // Format histogram data for chart
  const histogramData = useMemo(() => {
    if (!monteCarloData || !monteCarloData.histogram) return [];

    const { bins, frequencies } = monteCarloData.histogram;
    const data = [];

    for (let i = 0; i < frequencies.length; i++) {
      const binStart = bins[i];
      const binEnd = bins[i + 1];
      const binMid = (binStart + binEnd) / 2;

      data.push({
        pnl: Math.round(binMid),
        frequency: frequencies[i],
        isProfit: binMid > 0,
      });
    }

    return data;
  }, [monteCarloData]);

  if (loading) {
    return (
      <Paper sx={{ p: 3, textAlign: 'center' }}>
        <CircularProgress />
        <Typography variant="body2" sx={{ mt: 2 }}>
          Running Monte Carlo simulation (10,000 iterations)...
        </Typography>
      </Paper>
    );
  }

  if (error) {
    return (
      <Paper sx={{ p: 3 }}>
        <Alert severity="error">
          <Typography variant="body2">{error}</Typography>
          <Button onClick={calculateProbability} sx={{ mt: 1 }}>Retry</Button>
        </Alert>
      </Paper>
    );
  }

  if (!probabilityData || !monteCarloData) {
    return (
      <Paper sx={{ p: 3, textAlign: 'center' }}>
        <Typography variant="body2" color="text.secondary">
          Select positions to see probability analysis
        </Typography>
      </Paper>
    );
  }

  const pop = probabilityData.pop * 100; // Convert to percentage
  const popColor = pop >= 50 ? '#10b981' : '#ef4444';

  return (
    <Paper sx={{ p: 3, bgcolor: 'background.paper', borderRadius: 2 }}>
      <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        🎲 Probability Analysis
      </Typography>

      {/* Key Metrics */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        {/* Probability of Profit */}
        <Grid item xs={12} sm={6} md={3}>
          <Box sx={{ p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <ProfitIcon sx={{ color: popColor }} />
              <Typography variant="caption" color="text.secondary">Probability of Profit</Typography>
            </Box>
            <Typography variant="h4" sx={{ fontFamily: 'monospace', color: popColor }}>
              {pop.toFixed(1)}%
            </Typography>
            <Chip 
              label={pop >= 50 ? 'FAVORABLE' : 'UNFAVORABLE'} 
              size="small" 
              sx={{ 
                bgcolor: popColor, 
                color: 'white', 
                fontSize: '0.65rem',
                height: 20,
                mt: 0.5
              }} 
            />
          </Box>
        </Grid>

        {/* Expected Value */}
        <Grid item xs={12} sm={6} md={3}>
          <Box sx={{ p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <ExpectedValueIcon sx={{ color: '#3b82f6' }} />
              <Typography variant="caption" color="text.secondary">Expected Value</Typography>
            </Box>
            <Typography 
              variant="h5" 
              sx={{ 
                fontFamily: 'monospace',
                color: probabilityData.expected_value >= 0 ? '#10b981' : '#ef4444'
              }}
            >
              ${probabilityData.expected_value.toFixed(2)}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Mean P&L at expiry
            </Typography>
          </Box>
        </Grid>

        {/* Value at Risk (95%) */}
        <Grid item xs={12} sm={6} md={3}>
          <Box sx={{ p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <RiskIcon sx={{ color: '#f59e0b' }} />
              <Typography variant="caption" color="text.secondary">Value at Risk (95%)</Typography>
            </Box>
            <Typography variant="h5" sx={{ fontFamily: 'monospace', color: '#ef4444' }}>
              ${Math.abs(probabilityData.value_at_risk_95).toFixed(2)}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Max loss (5% probability)
            </Typography>
          </Box>
        </Grid>

        {/* Conditional VaR */}
        <Grid item xs={12} sm={6} md={3}>
          <Box sx={{ p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <LossIcon sx={{ color: '#ef4444' }} />
              <Typography variant="caption" color="text.secondary">Conditional VaR</Typography>
            </Box>
            <Typography variant="h5" sx={{ fontFamily: 'monospace', color: '#dc2626' }}>
              ${Math.abs(probabilityData.conditional_var_95).toFixed(2)}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Avg loss when VaR exceeded
            </Typography>
          </Box>
        </Grid>
      </Grid>

      {/* Monte Carlo Histogram */}
      <Box sx={{ mt: 3 }}>
        <Typography variant="subtitle2" gutterBottom>
          Profit/Loss Distribution (10,000 simulations)
        </Typography>
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={histogramData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis 
              dataKey="pnl" 
              stroke="#888"
              tickFormatter={(value) => `$${value}`}
            />
            <YAxis stroke="#888" label={{ value: 'Frequency', angle: -90, position: 'insideLeft' }} />
            <RechartsTooltip 
              contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155' }}
              formatter={(value, name) => {
                if (name === 'frequency') return [value, 'Occurrences'];
                return [value, name];
              }}
            />
            <ReferenceLine x={0} stroke="#fff" strokeDasharray="3 3" label="Breakeven" />
            <Bar 
              dataKey="frequency" 
              fill="#3b82f6"
              fillOpacity={0.6}
              name="Frequency"
            >
              {histogramData.map((entry, index) => (
                <Bar 
                  key={index} 
                  fill={entry.isProfit ? '#10b981' : '#ef4444'}
                  fillOpacity={0.6}
                />
              ))}
            </Bar>
          </ComposedChart>
        </ResponsiveContainer>
      </Box>

      {/* Percentiles */}
      <Box sx={{ mt: 2, p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
        <Typography variant="subtitle2" gutterBottom>
          Simulated Outcome Percentiles
        </Typography>
        <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
          <Chip 
            label={`P5: $${monteCarloData.percentiles.p5.toFixed(2)}`} 
            size="small"
            sx={{ fontFamily: 'monospace', bgcolor: '#dc2626', color: 'white' }}
          />
          <Chip 
            label={`P25: $${monteCarloData.percentiles.p25.toFixed(2)}`} 
            size="small"
            sx={{ fontFamily: 'monospace', bgcolor: '#f59e0b', color: 'white' }}
          />
          <Chip 
            label={`P50 (Median): $${monteCarloData.percentiles.p50.toFixed(2)}`} 
            size="small"
            sx={{ fontFamily: 'monospace', bgcolor: '#3b82f6', color: 'white' }}
          />
          <Chip 
            label={`P75: $${monteCarloData.percentiles.p75.toFixed(2)}`} 
            size="small"
            sx={{ fontFamily: 'monospace', bgcolor: '#10b981', color: 'white' }}
          />
          <Chip 
            label={`P95: $${monteCarloData.percentiles.p95.toFixed(2)}`} 
            size="small"
            sx={{ fontFamily: 'monospace', bgcolor: '#059669', color: 'white' }}
          />
        </Stack>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
          P5 = 95% of outcomes are better than this | P95 = 95% of outcomes are worse than this
        </Typography>
      </Box>

      {/* Refresh Button */}
      <Box sx={{ mt: 2, textAlign: 'center' }}>
        <Button 
          variant="outlined" 
          size="small" 
          onClick={calculateProbability}
          disabled={loading}
        >
          Recalculate (New Monte Carlo)
        </Button>
      </Box>
    </Paper>
  );
};

export default ProbabilityAnalysisPanel;
