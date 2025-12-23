import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Chip,
  Button,
  Card,
  CardContent,
  LinearProgress,
  IconButton,
  Collapse,
  Divider
} from '@mui/material';
import {
  SignalCellularAlt,
  TrendingUp,
  Speed,
  Shield,
  Refresh,
  ExpandMore,
  ExpandLess,
  Warning,
  CheckCircle,
  Error,
  Info
} from '@mui/icons-material';

const MarketSignalPanel = () => {
  const [signalData, setSignalData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);

  const fetchSignalData = async () => {
    try {
      setLoading(true);
      // Fetch both signal data and liquidation data in parallel
      const [signalResponse, liquidationResponse] = await Promise.all([
        fetch('/api/volatility/signal'),
        fetch('/api/liquidation/status')
      ]);
      
      const signalResult = await signalResponse.json();
      const liquidationResult = await liquidationResponse.json();
      
      if (signalResult.success) {
        const data = signalResult.data;
        
        // Merge liquidation data into position_risk if available
        if (liquidationResult.success && liquidationResult.distance && liquidationResult.margin) {
          data.position_risk = {
            ...data.position_risk,
            liquidation_distance: liquidationResult.distance.distance,
            margin_utilized: liquidationResult.margin.utilization,
            mtm: data.position_risk?.mtm || liquidationResult.mtm?.current_mtm_inr,
            num_positions: data.position_risk?.num_positions
          };
        }
        
        setSignalData(data);
        setLastUpdate(new Date());
      } else {
        console.error('API returned error:', signalResult.error);
      }
    } catch (error) {
      console.error('Failed to fetch market signal:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSignalData();
    
    // Auto-refresh every 30 seconds for real-time updates
    const interval = setInterval(fetchSignalData, 30000);
    return () => clearInterval(interval);
  }, []);

  const getColorFromValue = (color) => {
    const colorMap = {
      'green': '#4caf50',
      'yellow': '#ff9800',
      'orange': '#ff5722',
      'red': '#f44336',
      'gray': '#9e9e9e'
    };
    return colorMap[color] || '#9e9e9e';
  };

  const getIconFromRisk = (riskValue) => {
    if (riskValue.includes('EXTREME') || riskValue.includes('DANGER')) {
      return <Error sx={{ fontSize: 20 }} />;
    } else if (riskValue.includes('HIGH') || riskValue.includes('ELEVATED')) {
      return <Warning sx={{ fontSize: 20 }} />;
    } else if (riskValue.includes('MODERATE')) {
      return <Info sx={{ fontSize: 20 }} />;
    } else {
      return <CheckCircle sx={{ fontSize: 20 }} />;
    }
  };

  const formatLastUpdate = () => {
    if (!lastUpdate) return '';
    const seconds = Math.floor((new Date() - lastUpdate) / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ago`;
  };

  if (loading && !signalData) {
    return (
      <Paper sx={{ p: 3, mb: 2 }}>
        <Typography variant="h6" gutterBottom>Loading Market Signal...</Typography>
        <LinearProgress />
      </Paper>
    );
  }

  if (!signalData) {
    return (
      <Paper sx={{ p: 3, mb: 2 }}>
        <Typography variant="h6" color="error">Failed to load market signal</Typography>
        <Button onClick={fetchSignalData} variant="outlined" sx={{ mt: 2 }}>
          <Refresh /> Retry
        </Button>
      </Paper>
    );
  }

  if (!loading && (signalData.status === 'NO_DATA' || signalData.status === 'UNKNOWN')) {
    return (
      <Paper sx={{ p: 3, mb: 2, textAlign: 'center' }}>
        <Typography variant="h6" gutterBottom>Waiting for market data…</Typography>
        <Typography variant="body2" color="text.secondary">
          The bot is still syncing with the exchange. Market readiness metrics will appear automatically once feeds warm up.
        </Typography>
        <Box sx={{ mt: 3, display: 'flex', justifyContent: 'center' }}>
          <LinearProgress sx={{ width: '60%' }} />
        </Box>
      </Paper>
    );
  }

  const vol = signalData.volatility_signal || {};
  const regime = signalData.market_regime || {};
  const suitability = signalData.grid_suitability || {};
  const positionRisk = signalData.position_risk || {};
  const overallRisk = signalData.overall_risk_status || {};

  return (
    <Paper sx={{ p: 3, mb: 2 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <SignalCellularAlt sx={{ fontSize: 28, color: 'primary.main' }} />
          <Typography variant="h6" component="div">
            Market Signal & Risk Dashboard
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="body2" color="text.secondary">
            Last Update: {formatLastUpdate() || 'Never'}
          </Typography>
          <IconButton size="small" onClick={fetchSignalData} disabled={loading}>
            <Refresh />
          </IconButton>
        </Box>
      </Box>

      {/* 3 Signal Cards */}
      <Grid container spacing={2} sx={{ mb: 2 }}>
        {/* Volatility Signal */}
        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%', border: `2px solid ${getColorFromValue(vol.color)}` }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <TrendingUp sx={{ fontSize: 20 }} />
                <Typography variant="subtitle2" fontWeight="bold">VOLATILITY</Typography>
              </Box>
              <Chip
                label={vol.value || '—'}
                size="small"
                sx={{
                  bgcolor: getColorFromValue(vol.color),
                  color: 'white',
                  mb: 1,
                  fontWeight: 'bold'
                }}
                component={motion.div}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
              />
              {vol.iv && vol.rv && (
                <>
                  <Typography variant="body2" color="text.secondary" component={motion.p} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                    IV: {vol.iv.toFixed(1)}%
                  </Typography>
                  <Typography variant="body2" color="text.secondary" component={motion.p} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                    RV: {vol.rv.toFixed(1)}%
                  </Typography>
                  {vol.spread !== null && (
                    <Typography variant="body2" color="text.secondary" component={motion.p} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                      Spread: {vol.spread > 0 ? '+' : ''}{vol.spread.toFixed(1)}%
                    </Typography>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Market Regime */}
        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%', border: `2px solid ${getColorFromValue(regime.color)}` }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <Speed sx={{ fontSize: 20 }} />
                <Typography variant="subtitle2" fontWeight="bold">MARKET REGIME</Typography>
              </Box>
              <Chip
                label={regime.value || '—'}
                size="small"
                sx={{
                  bgcolor: getColorFromValue(regime.color),
                  color: 'white',
                  mb: 1,
                  fontWeight: 'bold'
                }}
                component={motion.div}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
              />
              <Typography variant="body2" color="text.secondary">
                RV: {regime.rv.toFixed(1)}%
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Risk: {regime.risk}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Grid Suitability */}
        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%', border: `2px solid ${getColorFromValue(suitability.color)}` }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <Shield sx={{ fontSize: 20 }} />
                <Typography variant="subtitle2" fontWeight="bold">GRID SUITABILITY</Typography>
              </Box>
              <Chip
                label={suitability.rating}
                size="small"
                sx={{
                  bgcolor: getColorFromValue(suitability.color),
                  color: 'white',
                  mb: 1,
                  fontWeight: 'bold'
                }}
              />
              <Typography variant="body2" color="text.secondary">
                Score: {suitability.score}/{suitability.score_max}
              </Typography>
              <Box sx={{ mt: 1 }}>
                <LinearProgress
                  variant="determinate"
                  value={(suitability.score / suitability.score_max) * 100}
                  sx={{
                    height: 8,
                    borderRadius: 4,
                    bgcolor: '#2a2d3e',
                    '& .MuiLinearProgress-bar': {
                      bgcolor: getColorFromValue(suitability.color)
                    }
                  }}
                />
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Position Risk Summary */}
      <Card sx={{ bgcolor: '#1a1d2e', border: `1px solid ${getColorFromValue(overallRisk.color)}` }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
            <Shield sx={{ fontSize: 20, color: getColorFromValue(overallRisk.color) }} />
            <Typography variant="subtitle1" fontWeight="bold">
              Position Risk Summary
            </Typography>
          </Box>
          
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={3}>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Liquidation Distance
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Chip
                    label={positionRisk.liquidation_distance ? `${positionRisk.liquidation_distance.toFixed(1)}%` : 'N/A'}
                    size="small"
                    sx={{ bgcolor: positionRisk.liquidation_distance ? getColorFromValue('green') : '#9e9e9e', color: 'white' }}
                  />
                  {positionRisk.liquidation_distance && (
                    <Typography variant="caption" color="text.secondary">
                      {positionRisk.liquidation_distance > 50 ? 'Safe' : positionRisk.liquidation_distance > 30 ? 'Moderate' : 'Caution'}
                    </Typography>
                  )}
                </Box>
              </Box>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Margin Utilized
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Chip
                    label={positionRisk.margin_utilized ? `${positionRisk.margin_utilized.toFixed(1)}%` : 'N/A'}
                    size="small"
                    sx={{ bgcolor: positionRisk.margin_utilized ? getColorFromValue('yellow') : '#9e9e9e', color: 'white' }}
                  />
                </Box>
              </Box>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  MTM (Mark-to-Market)
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Chip
                    label={positionRisk.mtm ? `₹${positionRisk.mtm.toLocaleString()}` : 'N/A'}
                    size="small"
                    sx={{ bgcolor: positionRisk.mtm > 5000 ? getColorFromValue('green') : positionRisk.mtm < -5000 ? getColorFromValue('red') : getColorFromValue('yellow'), color: 'white' }}
                  />
                </Box>
              </Box>
            </Grid>

            <Grid item xs={12} sm={6} md={3}>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Open Positions
                </Typography>
                <Chip
                  label={`${positionRisk.num_positions || 0} positions`}
                  size="small"
                  sx={{ bgcolor: '#2196f3', color: 'white' }}
                />
              </Box>
            </Grid>
          </Grid>

          <Divider sx={{ my: 2 }} />

          {/* Overall Risk Status */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {overallRisk?.value ? getIconFromRisk(overallRisk.value) : <Info sx={{ fontSize: 20 }} />}
              <Typography variant="body2" fontWeight="bold">
                Overall Risk Status:
              </Typography>
            </Box>
            <Chip
              label={overallRisk.value || 'Unknown'}
              sx={{
                bgcolor: getColorFromValue(overallRisk.color),
                color: 'white',
                fontWeight: 'bold'
              }}
            />
          </Box>
        </CardContent>
      </Card>

      {/* Expand/Collapse Button */}
      <Box sx={{ mt: 2, textAlign: 'center' }}>
        <Button
          onClick={() => setExpanded(!expanded)}
          endIcon={expanded ? <ExpandLess /> : <ExpandMore />}
          variant="text"
          size="small"
        >
          {expanded ? 'Hide Advanced Analysis' : 'Show Advanced Analysis'}
        </Button>
      </Box>

      {/* Advanced Analysis (Collapsible) */}
      <Collapse in={expanded}>
        <Paper sx={{ p: 2, mt: 2, bgcolor: '#1a1d2e' }}>
          <Typography variant="subtitle2" fontWeight="bold" gutterBottom>
            📈 Advanced Market Analysis
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            This analysis combines volatility metrics with your current position risk to provide
            comprehensive trading recommendations.
          </Typography>
          
          {/* Recommendations based on signals */}
          <Box sx={{ mt: 2 }}>
            <Typography variant="caption" fontWeight="bold" color="primary">
              SIGNAL INTERPRETATION:
            </Typography>
            <Typography variant="body2" component="div" sx={{ mt: 1 }}>
              {vol.value === 'NEUTRAL' && '• IV ≈ RV: Options are fairly priced'}
              {vol.value === 'IV_HIGH' && '• IV > RV: Options are expensive, consider reducing exposure'}
              {vol.value === 'IV_LOW' && '• IV < RV: Options are cheap, potential buying opportunity'}
              {vol.value === 'NO_DATA' && '• Insufficient volatility data'}
            </Typography>
          </Box>
        </Paper>
      </Collapse>
    </Paper>
  );
};

export default MarketSignalPanel;
