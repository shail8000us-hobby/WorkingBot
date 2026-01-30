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
} from '@mui/material';
import { InfoOutlined, PlayArrow, Stop, Settings, TrendingUp, TrendingDown } from '@mui/icons-material';
import api from '../utils/apiShim';

/**
 * Auto-Delta Hedger
 * 
 * Institutional-grade automatic delta hedging system from quantconnect-lean-study
 * 
 * Features:
 * - Continuous portfolio Greeks monitoring
 * - Automatic BTC perp hedging when delta exceeds threshold
 * - Real-time Greeks display (Delta, Gamma, Vega, Theta)
 * - Hedge history log
 * - Configurable delta threshold
 * 
 * Strategy:
 * 1. Calculate total portfolio Delta every 10 seconds
 * 2. If |Delta| > threshold (default: 5 BTC), execute hedge
 * 3. Hedge by placing opposite position in BTC perpetual
 * 4. Log all hedges for analysis
 */
const AutoDeltaHedger = () => {
  // State
  const [enabled, setEnabled] = useState(false);
  const [deltaThreshold, setDeltaThreshold] = useState(5); // BTC units
  const [greeks, setGreeks] = useState({
    delta: 0,
    gamma: 0,
    vega: 0,
    theta: 0,
    lastUpdated: null,
  });
  const [hedgeHistory, setHedgeHistory] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('idle'); // idle, monitoring, hedging
  const [stats, setStats] = useState({
    totalHedges: 0,
    avgDeltaBeforeHedge: 0,
    lastHedgeTime: null,
  });

  const intervalRef = useRef(null);

  // Fetch current portfolio Greeks
  const fetchGreeks = useCallback(async () => {
    try {
      const response = await api.get('/api/experimental/greeks');
      if (response.data.success) {
        setGreeks({
          ...response.data.greeks,
          lastUpdated: new Date().toLocaleTimeString(),
        });
      }
    } catch (err) {
      console.error('Failed to fetch Greeks:', err);
      setError('Failed to fetch portfolio Greeks');
    }
  }, []);

  // Execute hedge
  const executeHedge = useCallback(async (currentDelta) => {
    setStatus('hedging');
    try {
      const response = await api.post('/api/experimental/hedge', {
        delta: currentDelta,
        threshold: deltaThreshold,
      });
      
      if (response.data.success) {
        const hedge = response.data.hedge;
        setHedgeHistory(prev => [hedge, ...prev].slice(0, 20)); // Keep last 20
        setStats(prev => ({
          totalHedges: prev.totalHedges + 1,
          avgDeltaBeforeHedge: (prev.avgDeltaBeforeHedge * prev.totalHedges + Math.abs(currentDelta)) / (prev.totalHedges + 1),
          lastHedgeTime: new Date().toLocaleTimeString(),
        }));
        setError(null);
      } else {
        setError(response.data.error || 'Hedge execution failed');
      }
    } catch (err) {
      console.error('Hedge execution error:', err);
      setError(`Hedge failed: ${err.message}`);
    } finally {
      setStatus('monitoring');
    }
  }, [deltaThreshold]);

  // Monitoring loop
  const monitoringLoop = useCallback(async () => {
    await fetchGreeks();
    
    // Check if hedge needed
    const currentDelta = greeks.delta;
    if (Math.abs(currentDelta) > deltaThreshold) {
      console.log(`[AUTO-HEDGE] Delta ${currentDelta.toFixed(4)} exceeds threshold ${deltaThreshold}, executing hedge...`);
      await executeHedge(currentDelta);
    }
  }, [fetchGreeks, greeks.delta, deltaThreshold, executeHedge]);

  // Start/Stop monitoring
  useEffect(() => {
    if (enabled) {
      setStatus('monitoring');
      setError(null);
      // Immediate fetch
      fetchGreeks();
      // Set up interval
      intervalRef.current = setInterval(monitoringLoop, 10000); // Every 10 seconds
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
  }, [enabled, monitoringLoop, fetchGreeks]);

  // Toggle enable/disable
  const handleToggle = (event) => {
    setEnabled(event.target.checked);
  };

  // Manual hedge trigger
  const handleManualHedge = async () => {
    if (greeks.delta !== 0) {
      await executeHedge(greeks.delta);
    }
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

  // Delta color
  const getDeltaColor = (delta) => {
    const absDelta = Math.abs(delta);
    if (absDelta > deltaThreshold * 1.5) return 'error';
    if (absDelta > deltaThreshold) return 'warning';
    return 'success';
  };

  return (
    <Card sx={{ bgcolor: 'background.paper', borderRadius: 2 }}>
      <CardContent>
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Box>
            <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <TrendingUp /> Auto-Delta Hedger
              <Tooltip title="Automatically hedges portfolio delta using BTC perpetual when threshold is exceeded">
                <InfoOutlined sx={{ fontSize: 18, color: 'text.secondary' }} />
              </Tooltip>
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Institutional-grade delta-neutral portfolio management
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Chip
              label={status.toUpperCase()}
              color={status === 'monitoring' ? 'success' : status === 'hedging' ? 'warning' : 'default'}
              size="small"
              icon={status === 'monitoring' ? <PlayArrow /> : status === 'hedging' ? <Settings /> : <Stop />}
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

        {/* Info Banner */}
        {!enabled && (
          <Alert severity="info" sx={{ mb: 2 }}>
            ℹ️ Enable auto-hedging to continuously monitor portfolio delta and automatically hedge when threshold is exceeded.
          </Alert>
        )}

        {/* Loading bar */}
        {loading && <LinearProgress sx={{ mb: 2 }} />}

        {/* Configuration */}
        <Box sx={{ mb: 3, p: 2, bgcolor: 'rgba(0,0,0,0.2)', borderRadius: 1 }}>
          <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
            Configuration
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
            <TextField
              label="Delta Threshold (BTC)"
              type="number"
              value={deltaThreshold}
              onChange={(e) => setDeltaThreshold(Number(e.target.value))}
              size="small"
              sx={{ width: 200 }}
              inputProps={{ min: 0.1, max: 100, step: 0.5 }}
              disabled={enabled}
            />
            <Typography variant="caption" color="text.secondary">
              Hedge when |Delta| exceeds this value
            </Typography>
          </Box>
        </Box>

        {/* Greeks Display */}
        <Box sx={{ mb: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
              Portfolio Greeks
            </Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Typography variant="caption" color="text.secondary">
                Last updated: {greeks.lastUpdated || '-'}
              </Typography>
              <IconButton size="small" onClick={handleRefresh} disabled={loading}>
                <Settings sx={{ fontSize: 16 }} />
              </IconButton>
            </Box>
          </Box>
          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 2 }}>
            <Box sx={{ p: 2, bgcolor: 'rgba(0,0,0,0.2)', borderRadius: 1, textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary">Delta</Typography>
              <Typography variant="h6" color={getDeltaColor(greeks.delta)}>
                {formatNumber(greeks.delta, 2)}
              </Typography>
            </Box>
            <Box sx={{ p: 2, bgcolor: 'rgba(0,0,0,0.2)', borderRadius: 1, textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary">Gamma</Typography>
              <Typography variant="h6">{formatNumber(greeks.gamma, 2)}</Typography>
            </Box>
            <Box sx={{ p: 2, bgcolor: 'rgba(0,0,0,0.2)', borderRadius: 1, textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary">Vega</Typography>
              <Typography variant="h6">{formatNumber(greeks.vega, 2)}</Typography>
            </Box>
            <Box sx={{ p: 2, bgcolor: 'rgba(0,0,0,0.2)', borderRadius: 1, textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary">Theta</Typography>
              <Typography variant="h6">{formatNumber(greeks.theta, 2)}</Typography>
            </Box>
          </Box>
        </Box>

        {/* Manual Hedge Button */}
        {!enabled && (
          <Box sx={{ mb: 3 }}>
            <Button
              variant="contained"
              color="primary"
              onClick={handleManualHedge}
              disabled={greeks.delta === 0 || loading}
              fullWidth
            >
              Manual Hedge Now
            </Button>
          </Box>
        )}

        {/* Stats */}
        <Box sx={{ mb: 3, p: 2, bgcolor: 'rgba(0,0,0,0.2)', borderRadius: 1 }}>
          <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
            Statistics
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 2, fontSize: '0.875rem' }}>
            <Box>
              <Typography variant="caption" color="text.secondary">Total Hedges</Typography>
              <Typography variant="body2" fontWeight="bold">{stats.totalHedges}</Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">Avg Delta (pre-hedge)</Typography>
              <Typography variant="body2" fontWeight="bold">{formatNumber(stats.avgDeltaBeforeHedge, 2)}</Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">Last Hedge</Typography>
              <Typography variant="body2" fontWeight="bold">{stats.lastHedgeTime || '-'}</Typography>
            </Box>
          </Box>
        </Box>

        {/* Hedge History */}
        {hedgeHistory.length > 0 && (
          <Box>
            <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
              Hedge History (Last 20)
            </Typography>
            <TableContainer component={Paper} sx={{ maxHeight: 300 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>Time</TableCell>
                    <TableCell align="right">Delta Before</TableCell>
                    <TableCell align="right">Hedge Size</TableCell>
                    <TableCell align="right">Price</TableCell>
                    <TableCell>Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {hedgeHistory.map((hedge, idx) => (
                    <TableRow key={idx}>
                      <TableCell>{new Date(hedge.timestamp).toLocaleTimeString()}</TableCell>
                      <TableCell align="right">
                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 0.5 }}>
                          {hedge.deltaBefore > 0 ? <TrendingUp fontSize="small" color="success" /> : <TrendingDown fontSize="small" color="error" />}
                          {formatNumber(hedge.deltaBefore, 2)}
                        </Box>
                      </TableCell>
                      <TableCell align="right">{formatNumber(hedge.hedgeSize, 4)} BTC</TableCell>
                      <TableCell align="right">${formatNumber(hedge.price, 2)}</TableCell>
                      <TableCell>
                        <Chip
                          label={hedge.status}
                          size="small"
                          color={hedge.status === 'success' ? 'success' : 'error'}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default AutoDeltaHedger;
