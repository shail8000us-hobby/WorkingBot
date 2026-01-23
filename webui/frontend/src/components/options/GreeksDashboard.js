/**
 * Greeks Dashboard Component
 * 
 * Displays portfolio Greeks with:
 * - Real-time Greek values
 * - Greek sensitivity charts
 * - Risk visualization
 * 
 * Created: January 23, 2026
 * Part of: PAYOFF_GRAPH_ENHANCEMENT_PLAN.md Phase 3
 */

import React, { useMemo } from 'react';
import {
  Paper,
  Box,
  Typography,
  Grid,
  Chip,
  Tooltip,
  LinearProgress,
} from '@mui/material';
import {
  TrendingUp as DeltaIcon,
  ShowChart as GammaIcon,
  Schedule as ThetaIcon,
  BarChart as VegaIcon,
  AttachMoney as RhoIcon,
} from '@mui/icons-material';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ReferenceLine,
} from 'recharts';

const GreeksDashboard = ({ positions, spotPrice }) => {
  // Calculate portfolio Greeks
  const portfolioGreeks = useMemo(() => {
    if (!positions || positions.length === 0) {
      return {
        delta: 0,
        gamma: 0,
        theta: 0,
        vega: 0,
        rho: 0,
        dollar_delta: 0,
        dollar_gamma: 0,
        dollar_theta: 0,
        dollar_vega: 0,
      };
    }

    const greeks = {
      delta: 0,
      gamma: 0,
      theta: 0,
      vega: 0,
      rho: 0,
      dollar_delta: 0,
      dollar_gamma: 0,
      dollar_theta: 0,
      dollar_vega: 0,
    };

    positions.forEach((pos) => {
      if (pos.greeks) {
        const qty = pos.size || pos.quantity || 1;
        const multiplier = 0.001; // BTC/ETH multiplier

        greeks.delta += (pos.greeks.delta || 0) * qty;
        greeks.gamma += (pos.greeks.gamma || 0) * qty;
        greeks.theta += (pos.greeks.theta || 0) * qty;
        greeks.vega += (pos.greeks.vega || 0) * qty;
        greeks.rho += (pos.greeks.rho || 0) * qty;

        greeks.dollar_delta += (pos.greeks.delta || 0) * qty * spotPrice * multiplier;
        greeks.dollar_gamma += (pos.greeks.gamma || 0) * qty * spotPrice * spotPrice * multiplier / 100;
        greeks.dollar_theta += (pos.greeks.theta || 0) * qty * multiplier;
        greeks.dollar_vega += (pos.greeks.vega || 0) * qty * multiplier;
      }
    });

    return greeks;
  }, [positions, spotPrice]);

  // Calculate Greeks over price range for visualization
  const greeksOverPrice = useMemo(() => {
    if (!spotPrice) return [];

    const priceRange = [];
    const step = spotPrice * 0.02; // 2% steps

    for (let price = spotPrice * 0.8; price <= spotPrice * 1.2; price += step) {
      priceRange.push({
        price: Math.round(price),
        delta: portfolioGreeks.delta, // Simplified - would need recalculation for each price
        gamma: portfolioGreeks.gamma,
        theta: portfolioGreeks.theta,
      });
    }

    return priceRange;
  }, [spotPrice, portfolioGreeks]);

  // Get risk level based on Greeks
  const getRiskLevel = (greek, value) => {
    const absValue = Math.abs(value);
    
    switch (greek) {
      case 'gamma':
        if (absValue > 0.1) return { level: 'high', color: '#ef4444' };
        if (absValue > 0.05) return { level: 'medium', color: '#f59e0b' };
        return { level: 'low', color: '#10b981' };
      
      case 'theta':
        if (absValue > 100) return { level: 'high', color: '#ef4444' };
        if (absValue > 50) return { level: 'medium', color: '#f59e0b' };
        return { level: 'low', color: '#10b981' };
      
      default:
        return { level: 'low', color: '#10b981' };
    }
  };

  const gammaRisk = getRiskLevel('gamma', portfolioGreeks.gamma);
  const thetaRisk = getRiskLevel('theta', portfolioGreeks.theta);

  return (
    <Paper sx={{ p: 3, bgcolor: 'background.paper', borderRadius: 2 }}>
      <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        📊 Portfolio Greeks Dashboard
      </Typography>

      {/* Portfolio Greeks Summary */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        {/* Delta */}
        <Grid item xs={12} sm={6} md={2.4}>
          <Box sx={{ p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <DeltaIcon sx={{ color: '#3b82f6' }} />
              <Typography variant="caption" color="text.secondary">Delta (Δ)</Typography>
            </Box>
            <Tooltip title="Rate of change of option value with respect to underlying price">
              <Typography variant="h6" sx={{ fontFamily: 'monospace' }}>
                {portfolioGreeks.delta.toFixed(3)}
              </Typography>
            </Tooltip>
            <Typography variant="caption" color="text.secondary">
              ${portfolioGreeks.dollar_delta.toFixed(2)}
            </Typography>
          </Box>
        </Grid>

        {/* Gamma */}
        <Grid item xs={12} sm={6} md={2.4}>
          <Box sx={{ p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <GammaIcon sx={{ color: gammaRisk.color }} />
              <Typography variant="caption" color="text.secondary">Gamma (Γ)</Typography>
            </Box>
            <Tooltip title="Rate of change of delta with respect to underlying price">
              <Typography variant="h6" sx={{ fontFamily: 'monospace', color: gammaRisk.color }}>
                {portfolioGreeks.gamma.toFixed(4)}
              </Typography>
            </Tooltip>
            <Chip 
              label={`${gammaRisk.level.toUpperCase()} RISK`} 
              size="small" 
              sx={{ 
                bgcolor: gammaRisk.color, 
                color: 'white', 
                fontSize: '0.65rem',
                height: 20 
              }} 
            />
          </Box>
        </Grid>

        {/* Theta */}
        <Grid item xs={12} sm={6} md={2.4}>
          <Box sx={{ p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <ThetaIcon sx={{ color: thetaRisk.color }} />
              <Typography variant="caption" color="text.secondary">Theta (Θ)</Typography>
            </Box>
            <Tooltip title="Time decay per day">
              <Typography variant="h6" sx={{ fontFamily: 'monospace', color: thetaRisk.color }}>
                {portfolioGreeks.theta.toFixed(2)}
              </Typography>
            </Tooltip>
            <Typography variant="caption" color="text.secondary">
              ${portfolioGreeks.dollar_theta.toFixed(2)}/day
            </Typography>
          </Box>
        </Grid>

        {/* Vega */}
        <Grid item xs={12} sm={6} md={2.4}>
          <Box sx={{ p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <VegaIcon sx={{ color: '#8b5cf6' }} />
              <Typography variant="caption" color="text.secondary">Vega (ν)</Typography>
            </Box>
            <Tooltip title="Sensitivity to volatility changes">
              <Typography variant="h6" sx={{ fontFamily: 'monospace' }}>
                {portfolioGreeks.vega.toFixed(3)}
              </Typography>
            </Tooltip>
            <Typography variant="caption" color="text.secondary">
              ${portfolioGreeks.dollar_vega.toFixed(2)}/1% IV
            </Typography>
          </Box>
        </Grid>

        {/* Rho */}
        <Grid item xs={12} sm={6} md={2.4}>
          <Box sx={{ p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
              <RhoIcon sx={{ color: '#06b6d4' }} />
              <Typography variant="caption" color="text.secondary">Rho (ρ)</Typography>
            </Box>
            <Tooltip title="Sensitivity to interest rate changes">
              <Typography variant="h6" sx={{ fontFamily: 'monospace' }}>
                {portfolioGreeks.rho.toFixed(4)}
              </Typography>
            </Tooltip>
            <Typography variant="caption" color="text.secondary">
              per 1% rate change
            </Typography>
          </Box>
        </Grid>
      </Grid>

      {/* Greeks Sensitivity Chart */}
      <Box sx={{ mt: 3 }}>
        <Typography variant="subtitle2" gutterBottom>
          Greeks Sensitivity (Delta, Gamma, Theta over price)
        </Typography>
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={greeksOverPrice}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis 
              dataKey="price" 
              stroke="#888"
              tickFormatter={(value) => `$${value.toLocaleString()}`}
            />
            <YAxis stroke="#888" />
            <RechartsTooltip 
              contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155' }}
              formatter={(value, name) => [value.toFixed(4), name]}
            />
            <Legend />
            <ReferenceLine x={spotPrice} stroke="#3b82f6" strokeDasharray="3 3" label="Spot" />
            <Line 
              type="monotone" 
              dataKey="delta" 
              stroke="#3b82f6" 
              name="Delta"
              strokeWidth={2}
            />
            <Line 
              type="monotone" 
              dataKey="gamma" 
              stroke="#10b981" 
              name="Gamma"
              strokeWidth={2}
            />
            <Line 
              type="monotone" 
              dataKey="theta" 
              stroke="#f59e0b" 
              name="Theta"
              strokeWidth={2}
            />
          </LineChart>
        </ResponsiveContainer>
      </Box>

      {/* Risk Warnings */}
      {(gammaRisk.level === 'high' || thetaRisk.level === 'high') && (
        <Box sx={{ mt: 2, p: 2, bgcolor: '#fef3c7', borderRadius: 1, border: '1px solid #f59e0b' }}>
          <Typography variant="subtitle2" sx={{ color: '#92400e', mb: 1 }}>
            ⚠️ Risk Alerts
          </Typography>
          {gammaRisk.level === 'high' && (
            <Typography variant="body2" sx={{ color: '#78350f' }}>
              • High Gamma: Large delta changes with small price moves. Position is very sensitive.
            </Typography>
          )}
          {thetaRisk.level === 'high' && (
            <Typography variant="body2" sx={{ color: '#78350f' }}>
              • High Theta Decay: Losing ${Math.abs(portfolioGreeks.dollar_theta).toFixed(2)} per day to time decay.
            </Typography>
          )}
        </Box>
      )}
    </Paper>
  );
};

export default GreeksDashboard;
