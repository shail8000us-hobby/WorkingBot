import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Switch,
  FormControlLabel,
  TextField,
  Button,
  Alert,
  Chip,
  LinearProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Tooltip,
  Divider,
} from '@mui/material';
import { 
  InfoOutlined, 
  PlayArrow, 
  Stop, 
  TrendingUp, 
  TrendingDown, 
  Refresh,
  ShowChart,
  AttachMoney,
} from '@mui/icons-material';
import api from '../utils/apiShim';

/**
 * Gamma Scalping Bot
 * 
 * Institutional-grade gamma scalping system from market makers
 * 
 * Strategy:
 * 1. Monitor portfolio gamma exposure
 * 2. When underlying moves by threshold (e.g., $500), delta changes
 * 3. Execute hedge to "lock in" gamma profit
 * 4. Repeat on each significant move
 * 
 * Example:
 * - Long straddle with +10 gamma
 * - BTC up $500 → delta increases by +5
 * - Sell 5 BTC to hedge → lock in $2,500 profit
 * - BTC down $500 → delta decreases back
 * - Buy 5 BTC to hedge → lock in another $2,500
 * - Net: Made $5,000 from volatility!
 * 
 * Key: You profit from MOVEMENT, not direction
 */
const GammaScalpingBot = () => {
  // State
  const [enabled, setEnabled] = useState(false);
  const [priceThreshold, setPriceThreshold] = useState(500); // USD move to trigger scalp
  const [greeks, setGreeks] = useState({
    delta: 0,
    gamma: 0,
    options_delta: 0,
    futures_delta: 0,
    btc_price: 0,
    lastUpdated: null,
  });
  const [scalpHistory, setScalpHistory] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('idle'); // idle, monitoring, scalping
  const [stats, setStats] = useState({
    totalScalps: 0,
    totalPnL: 0,
    avgScalpSize: 0,
    lastScalpTime: null,
  });
  const [lastScalpPrice, setLastScalpPrice] = useState(null);

  const intervalRef = useRef(null);

  // Fetch current portfolio Greeks
  const fetchGreeks = useCallback(async () => {
    try {
      const response = await api.get('/api/experimental/greeks');
      if (response.data.success) {
        const newGreeks = {
          ...response.data.greeks,
          lastUpdated: new Date().toLocaleTimeString(),
        };
        setGreeks(newGreeks);
        
        // Initialize last scalp price on first fetch
        if (!lastScalpPrice && newGreeks.btc_price > 0) {
          setLastScalpPrice(newGreeks.btc_price);
        }
        
        return newGreeks;
      }
    } catch (err) {
      console.error('Failed to fetch Greeks:', err);
      setError('Failed to fetch portfolio Greeks');
    }
    return null;
  }, [lastScalpPrice]);

  // Execute gamma scalp
  const executeScalp = useCallback(async (priceDiff, currentDelta, currentPrice) => {
    setStatus('scalping');
    try {
      const response = await api.post('/api/experimental/gamma-scalp', {
        price_diff: priceDiff,
        current_delta: currentDelta,
        current_price: currentPrice,
        threshold: priceThreshold,
      });
      
      if (response.data.success) {
        const scalp = response.data.scalp;
        setScalpHistory(prev => [scalp, ...prev].slice(0, 30)); // Keep last 30
        setStats(prev => ({
          totalScalps: prev.totalScalps + 1,
          totalPnL: prev.totalPnL + (scalp.estimated_pnl || 0),
          avgScalpSize: ((prev.avgScalpSize * prev.totalScalps) + Math.abs(scalp.size || 0)) / (prev.totalScalps + 1),
          lastScalpTime: new Date().toLocaleTimeString(),
        }));
        setLastScalpPrice(currentPrice);
        setError(null);
      } else {
        setError(response.data.error || 'Scalp execution failed');
      }
    } catch (err) {
      console.error('Scalp execution error:', err);
      setError('Failed to execute gamma scalp');
    }
    setStatus('monitoring');
  }, [priceThreshold]);

  // Check if scalp is needed
  const checkForScalp = useCallback(async () => {
    const currentGreeks = await fetchGreeks();
    if (!currentGreeks || !lastScalpPrice) return;
    
    const currentPrice = currentGreeks.btc_price;
    const priceDiff = currentPrice - lastScalpPrice;
    
    // Check if price moved enough to trigger scalp
    if (Math.abs(priceDiff) >= priceThreshold) {
      // Only scalp if we have gamma exposure (long gamma = positive gamma)
      if (Math.abs(currentGreeks.gamma) > 0.001) {
        console.log(`Gamma scalp triggered: price moved $${priceDiff.toFixed(2)}, gamma=${currentGreeks.gamma}`);
        await executeScalp(priceDiff, currentGreeks.options_delta, currentPrice);
      }
    }
  }, [fetchGreeks, lastScalpPrice, priceThreshold, executeScalp]);

  // Monitoring loop
  useEffect(() => {
    if (enabled) {
      setStatus('monitoring');
      // Check every 15 seconds when enabled
      intervalRef.current = setInterval(checkForScalp, 15000);
      // Initial check
      checkForScalp();
    } else {
      setStatus('idle');
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [enabled, checkForScalp]);

  // Initial Greeks fetch
  useEffect(() => {
    fetchGreeks();
    
    // Refresh every 15 seconds when disabled
    const refreshInterval = setInterval(() => {
      if (!enabled) {
        fetchGreeks();
      }
    }, 15000);
    
    return () => clearInterval(refreshInterval);
  }, [fetchGreeks, enabled]);

  // Toggle enable/disable
  const handleToggle = (event) => {
    const newEnabled = event.target.checked;
    setEnabled(newEnabled);
    if (newEnabled) {
      // Reset last scalp price when starting
      setLastScalpPrice(greeks.btc_price);
    }
  };

  // Manual scalp trigger
  const handleManualScalp = async () => {
    if (greeks.gamma !== 0 && greeks.btc_price > 0 && lastScalpPrice) {
      const priceDiff = greeks.btc_price - lastScalpPrice;
      await executeScalp(priceDiff, greeks.options_delta, greeks.btc_price);
    }
  };

  // Reset reference price
  const handleResetPrice = () => {
    setLastScalpPrice(greeks.btc_price);
  };

  // Manual refresh
  const handleRefresh = async () => {
    setLoading(true);
    await fetchGreeks();
    setLoading(false);
  };

  // Format number
  const formatNumber = (num, decimals = 4) => {
    if (num === null || num === undefined) return '-';
    return Number(num).toFixed(decimals);
  };

  // Format USD
  const formatUSD = (num) => {
    if (num === null || num === undefined) return '-';
    return `$${Number(num).toFixed(2)}`;
  };

  // Gamma color - green when long (positive), red when short
  const getGammaColor = () => {
    if (greeks.gamma > 0.01) return 'success';
    if (greeks.gamma < -0.01) return 'error';
    return 'default';
  };

  // Price diff from last scalp
  const currentPriceDiff = lastScalpPrice ? greeks.btc_price - lastScalpPrice : 0;
  const progressToScalp = lastScalpPrice ? Math.min(100, (Math.abs(currentPriceDiff) / priceThreshold) * 100) : 0;

  return (
    <Card sx={{ bgcolor: 'background.paper', borderRadius: 2 }}>
      <CardContent>
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Box>
            <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <ShowChart /> Gamma Scalping Bot
              <Tooltip title="Automatically scalps gamma profits by delta-hedging on price moves. Classic market maker strategy.">
                <InfoOutlined sx={{ fontSize: 18, color: 'text.secondary' }} />
              </Tooltip>
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Market maker strategy - profit from volatility, not direction
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Chip
              label={status.toUpperCase()}
              color={status === 'monitoring' ? 'success' : status === 'scalping' ? 'warning' : 'default'}
              size="small"
              icon={status === 'monitoring' ? <PlayArrow /> : status === 'scalping' ? <AttachMoney /> : <Stop />}
            />
            <FormControlLabel
              control={<Switch checked={enabled} onChange={handleToggle} color="primary" />}
              label={enabled ? 'ON' : 'OFF'}
            />
          </Box>
        </Box>

        {/* Error Alert */}
        {error && (
          <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {/* Gamma Exposure Warning */}
        {greeks.gamma < 0 && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            ⚠️ You are SHORT gamma ({formatNumber(greeks.gamma, 2)}). Gamma scalping works best when LONG gamma (owning options).
            Short gamma means you LOSE money on big moves.
          </Alert>
        )}

        {/* Info Banner */}
        {!enabled && greeks.gamma >= 0 && (
          <Alert severity="info" sx={{ mb: 2 }}>
            ℹ️ <strong>How it works:</strong> When BTC moves ${priceThreshold}, the bot hedges your delta change to lock in gamma profit.
            With {formatNumber(greeks.gamma, 2)} gamma, a ${priceThreshold} move generates ~{formatUSD(Math.abs(greeks.gamma * priceThreshold * priceThreshold / 2))} in gamma P&L.
          </Alert>
        )}

        {/* Loading bar */}
        {loading && <LinearProgress sx={{ mb: 2 }} />}

        {/* Configuration */}
        <Box sx={{ mb: 3, p: 2, bgcolor: 'rgba(0,0,0,0.2)', borderRadius: 1 }}>
          <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
            Configuration
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
            <TextField
              label="Price Threshold ($)"
              type="number"
              value={priceThreshold}
              onChange={(e) => setPriceThreshold(Number(e.target.value))}
              size="small"
              sx={{ width: 180 }}
              inputProps={{ min: 100, max: 5000, step: 100 }}
              disabled={enabled}
            />
            <Typography variant="caption" color="text.secondary">
              Scalp when BTC moves this much from last scalp
            </Typography>
          </Box>
        </Box>

        {/* Current Position */}
        <Box sx={{ mb: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
              Gamma Exposure & Position
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
              <Typography variant="caption" color="text.secondary">
                Last updated: {greeks.lastUpdated || '-'}
              </Typography>
              <Tooltip title="Refresh">
                <IconButton size="small" onClick={handleRefresh} disabled={loading}>
                  <Refresh sx={{ fontSize: 16 }} />
                </IconButton>
              </Tooltip>
            </Box>
          </Box>
          
          {/* Gamma Display */}
          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 2, mb: 2 }}>
            <Box sx={{ p: 2, bgcolor: getGammaColor() === 'success' ? 'success.dark' : getGammaColor() === 'error' ? 'error.dark' : 'rgba(0,0,0,0.2)', borderRadius: 1, textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary">Portfolio Gamma</Typography>
              <Typography variant="h5" fontWeight="bold">
                {formatNumber(greeks.gamma, 4)}
              </Typography>
              <Typography variant="caption" color={greeks.gamma >= 0 ? 'success.main' : 'error.main'}>
                {greeks.gamma >= 0 ? 'LONG GAMMA ✓' : 'SHORT GAMMA ✗'}
              </Typography>
            </Box>
            <Box sx={{ p: 2, bgcolor: 'rgba(0,0,0,0.2)', borderRadius: 1, textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary">BTC Price</Typography>
              <Typography variant="h5" fontWeight="bold">
                {formatUSD(greeks.btc_price)}
              </Typography>
            </Box>
            <Box sx={{ p: 2, bgcolor: 'rgba(0,0,0,0.2)', borderRadius: 1, textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary">Options Delta</Typography>
              <Typography variant="h5" fontWeight="bold" color={greeks.options_delta > 0 ? 'success.main' : greeks.options_delta < 0 ? 'error.main' : 'text.primary'}>
                {formatNumber(greeks.options_delta, 2)}
              </Typography>
            </Box>
          </Box>

          {/* Progress to next scalp */}
          <Box sx={{ mb: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
              <Typography variant="caption">Progress to Next Scalp</Typography>
              <Typography variant="caption">
                {formatUSD(currentPriceDiff)} / {formatUSD(priceThreshold)} ({progressToScalp.toFixed(0)}%)
              </Typography>
            </Box>
            <LinearProgress 
              variant="determinate" 
              value={progressToScalp} 
              color={currentPriceDiff > 0 ? 'success' : 'error'}
              sx={{ height: 8, borderRadius: 1 }}
            />
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
              <Typography variant="caption" color="text.secondary">
                Last scalp at: {lastScalpPrice ? formatUSD(lastScalpPrice) : 'N/A'}
              </Typography>
              <Button size="small" onClick={handleResetPrice} disabled={!greeks.btc_price}>
                Reset Reference
              </Button>
            </Box>
          </Box>
        </Box>

        {/* Manual Scalp Button */}
        {!enabled && (
          <Box sx={{ mb: 3, display: 'flex', gap: 2 }}>
            <Button
              variant="contained"
              color="primary"
              onClick={handleManualScalp}
              disabled={greeks.gamma === 0 || loading || !lastScalpPrice}
              fullWidth
            >
              Manual Scalp Now (Δ Price: {formatUSD(currentPriceDiff)})
            </Button>
          </Box>
        )}

        <Divider sx={{ my: 2 }} />

        {/* Stats */}
        <Box sx={{ mb: 3, p: 2, bgcolor: 'rgba(0,0,0,0.2)', borderRadius: 1 }}>
          <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
            Session Statistics
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 2, fontSize: '0.875rem' }}>
            <Box>
              <Typography variant="caption" color="text.secondary">Total Scalps</Typography>
              <Typography variant="body1" fontWeight="bold">{stats.totalScalps}</Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">Est. Total P&L</Typography>
              <Typography variant="body1" fontWeight="bold" color={stats.totalPnL >= 0 ? 'success.main' : 'error.main'}>
                {formatUSD(stats.totalPnL)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">Avg Scalp Size</Typography>
              <Typography variant="body1" fontWeight="bold">{formatNumber(stats.avgScalpSize, 2)} BTC</Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">Last Scalp</Typography>
              <Typography variant="body1" fontWeight="bold">{stats.lastScalpTime || '-'}</Typography>
            </Box>
          </Box>
        </Box>

        {/* Scalp History */}
        {scalpHistory.length > 0 && (
          <Box>
            <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
              Recent Scalps
            </Typography>
            <TableContainer component={Paper} sx={{ maxHeight: 250, bgcolor: 'rgba(0,0,0,0.2)' }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>Time</TableCell>
                    <TableCell>Direction</TableCell>
                    <TableCell align="right">Price Move</TableCell>
                    <TableCell align="right">Size</TableCell>
                    <TableCell align="right">Est. P&L</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {scalpHistory.map((scalp, idx) => (
                    <TableRow key={idx}>
                      <TableCell>{scalp.time}</TableCell>
                      <TableCell>
                        <Chip
                          label={scalp.direction}
                          size="small"
                          color={scalp.direction === 'SELL' ? 'error' : 'success'}
                          icon={scalp.direction === 'SELL' ? <TrendingDown /> : <TrendingUp />}
                        />
                      </TableCell>
                      <TableCell align="right">{formatUSD(scalp.price_diff)}</TableCell>
                      <TableCell align="right">{formatNumber(Math.abs(scalp.size), 3)} BTC</TableCell>
                      <TableCell align="right" sx={{ color: (scalp.estimated_pnl || 0) >= 0 ? 'success.main' : 'error.main' }}>
                        {formatUSD(scalp.estimated_pnl)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        )}

        {/* Educational Note */}
        <Box sx={{ mt: 2, p: 2, bgcolor: 'rgba(255,255,255,0.05)', borderRadius: 1 }}>
          <Typography variant="caption" color="text.secondary">
            <strong>💡 Gamma Scalping Math:</strong> Gamma profit = ½ × Γ × (ΔPrice)². 
            With Γ={formatNumber(greeks.gamma, 3)} and ${priceThreshold} move: 
            P&L ≈ {formatUSD(0.5 * Math.abs(greeks.gamma) * priceThreshold * priceThreshold)}.
            The key is to hedge (scalp) at each threshold to lock in this profit before price reverses.
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
};

export default GammaScalpingBot;
