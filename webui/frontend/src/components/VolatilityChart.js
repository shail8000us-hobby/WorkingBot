/**
 * Professional IV vs RV Volatility Chart Component
 *
 * Features:
 * - Dual-line chart (IV in red, RV in green)
 * - Timeframe selector (Daily/Weekly/Monthly)
 * - Real-time updates via WebSocket
 * - Dark theme matching Delta Exchange
 * - Professional tooltips and legend
 * - Auto-refresh every 30 seconds
 *
 * PERFORMANCE OPTIMIZED: Phase 6 (Jan 18, 2026)
 * - React.memo for component memoization
 * - useMemo for expensive computations
 * - useCallback for stable function references
 */

import React, { useState, useEffect, useCallback, useRef, useMemo, memo } from 'react';
import {
  Box,
  Paper,
  Typography,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  CircularProgress,
  Alert,
  Chip,
  Grid,
} from '@mui/material';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { format } from 'date-fns';
import { useRenderPerformance } from '../hooks/usePerformance';

const VolatilityChart = memo(({ socketio }) => {
  // Track render performance in development
  useRenderPerformance('VolatilityChart');
  const [timeframe, setTimeframe] = useState('daily');
  const [chartData, setChartData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [latestValues, setLatestValues] = useState({ iv: null, rv: {} });
  const [stats, setStats] = useState(null);
  const refreshTimerRef = useRef(null);

  /**
   * Fetch historical data from backend
   */
  const fetchHistoricalData = useCallback(async (selectedTimeframe) => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(
        `/api/risk/volatility/historical?timeframe=${selectedTimeframe}&limit=100`
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();

      if (!result.success) {
        throw new Error(result.error || 'Failed to fetch data');
      }

      // Merge IV and RV data by timestamp
      const mergedData = mergeDataByTimestamp(result.data.iv, result.data.rv);
      setChartData(mergedData);
    } catch (err) {
      console.error('Failed to fetch volatility data:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Fetch latest values
   */
  const fetchLatestValues = useCallback(async () => {
    try {
      const response = await fetch('/api/risk/volatility/latest');
      if (!response.ok) return;

      const result = await response.json();
      if (result.success) {
        setLatestValues(result.data);
      }
    } catch (err) {
      console.error('Failed to fetch latest values:', err);
    }
  }, []);

  /**
   * Fetch volatility statistics
   */
  const fetchStats = useCallback(async () => {
    try {
      const response = await fetch('/api/risk/volatility/stats');
      if (!response.ok) return;

      const result = await response.json();
      if (result.success) {
        setStats(result.data);
      }
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  }, []);

  /**
   * Merge IV and RV arrays by timestamp
   */
  const mergeDataByTimestamp = (ivData, rvData) => {
    const dataMap = new Map();

    // Add IV data
    ivData.forEach((point) => {
      dataMap.set(point.timestamp, {
        timestamp: point.timestamp,
        iv: point.value,
      });
    });

    // Add RV data
    rvData.forEach((point) => {
      const existing = dataMap.get(point.timestamp);
      if (existing) {
        existing.rv = point.value;
      } else {
        dataMap.set(point.timestamp, {
          timestamp: point.timestamp,
          rv: point.value,
        });
      }
    });

    // Convert to array and sort by timestamp
    return Array.from(dataMap.values()).sort((a, b) => a.timestamp - b.timestamp);
  };

  /**
   * Handle timeframe change
   */
  const handleTimeframeChange = (event) => {
    const newTimeframe = event.target.value;
    setTimeframe(newTimeframe);
    fetchHistoricalData(newTimeframe);
  };

  /**
   * Setup WebSocket subscription for real-time updates
   */
  useEffect(() => {
    if (!socketio) return;

    // Subscribe to volatility updates
    socketio.emit('subscribe_volatility');

    // Handle real-time updates
    const handleVolatilityUpdate = (data) => {
      if (data.success && data.data) {
        setLatestValues(data.data);
      }
    };

    socketio.on('volatility_update', handleVolatilityUpdate);

    // Cleanup
    return () => {
      socketio.emit('unsubscribe_volatility');
      socketio.off('volatility_update', handleVolatilityUpdate);
    };
  }, [socketio]);

  /**
   * Initial data fetch and auto-refresh setup
   */
  useEffect(() => {
    // Initial fetch
    fetchHistoricalData(timeframe);
    fetchLatestValues();
    fetchStats();

    // Auto-refresh every 30 seconds
    refreshTimerRef.current = setInterval(() => {
      fetchHistoricalData(timeframe);
      fetchLatestValues();
      fetchStats();
    }, 30000);

    // Cleanup
    return () => {
      if (refreshTimerRef.current) {
        clearInterval(refreshTimerRef.current);
      }
    };
  }, [timeframe, fetchHistoricalData, fetchLatestValues, fetchStats]);

  /**
   * Custom tooltip for chart
   */
  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload || !payload.length) return null;

    const data = payload[0].payload;
    const date = new Date(data.timestamp);

    return (
      <Paper
        elevation={3}
        sx={{
          p: 2,
          backgroundColor: 'rgba(18, 18, 18, 0.95)',
          border: '1px solid rgba(255, 255, 255, 0.12)',
        }}
      >
        <Typography variant="body2" sx={{ color: '#aaa', mb: 1 }}>
          {format(date, 'MMM dd, yyyy HH:mm')}
        </Typography>
        {data.iv !== undefined && (
          <Typography variant="body2" sx={{ color: '#ef5350', mb: 0.5 }}>
            IV: {data.iv.toFixed(2)}%
          </Typography>
        )}
        {data.rv !== undefined && (
          <Typography variant="body2" sx={{ color: '#66bb6a' }}>
            RV: {data.rv.toFixed(2)}%
          </Typography>
        )}
        {data.iv !== undefined && data.rv !== undefined && (
          <Typography variant="body2" sx={{ color: '#ffb74d', mt: 0.5 }}>
            Spread: {(data.iv - data.rv).toFixed(2)}%
          </Typography>
        )}
      </Paper>
    );
  };

  /**
   * Format X-axis timestamp
   */
  const formatXAxis = (timestamp) => {
    const date = new Date(timestamp);
    if (timeframe === 'daily') {
      return format(date, 'HH:mm');
    } else if (timeframe === 'weekly') {
      return format(date, 'MMM dd');
    } else {
      return format(date, 'MMM dd');
    }
  };

  /**
   * Get current RV value based on timeframe
   */
  const getCurrentRV = () => {
    const rvMap = { daily: '1d', weekly: '7d', monthly: '30d' };
    const rvKey = rvMap[timeframe];
    return latestValues.rv?.[rvKey]?.value;
  };

  return (
    <Paper
      elevation={2}
      sx={{
        p: 3,
        backgroundColor: 'rgba(18, 18, 18, 0.8)',
        border: '1px solid rgba(255, 255, 255, 0.12)',
        borderRadius: 2,
      }}
    >
      {/* Header */}
      <Grid container spacing={2} alignItems="center" sx={{ mb: 3 }}>
        <Grid item xs={12} md={6}>
          <Typography variant="h6" sx={{ fontWeight: 600, color: '#fff' }}>
            📊 IV vs RV Volatility Chart
          </Typography>
          <Typography variant="body2" sx={{ color: '#aaa', mt: 0.5 }}>
            Implied Volatility vs Realized Volatility
          </Typography>
        </Grid>
        <Grid item xs={12} md={6} sx={{ textAlign: { xs: 'left', md: 'right' } }}>
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel id="timeframe-label" sx={{ color: '#aaa' }}>
              Timeframe
            </InputLabel>
            <Select
              labelId="timeframe-label"
              value={timeframe}
              onChange={handleTimeframeChange}
              label="Timeframe"
              sx={{
                color: '#fff',
                '.MuiOutlinedInput-notchedOutline': {
                  borderColor: 'rgba(255, 255, 255, 0.23)',
                },
                '&:hover .MuiOutlinedInput-notchedOutline': {
                  borderColor: 'rgba(255, 255, 255, 0.4)',
                },
                '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                  borderColor: '#1976d2',
                },
              }}
            >
              <MenuItem value="daily">Daily (1D)</MenuItem>
              <MenuItem value="weekly">Weekly (7D)</MenuItem>
              <MenuItem value="monthly">Monthly (30D)</MenuItem>
            </Select>
          </FormControl>
        </Grid>
      </Grid>

      {/* Current Values */}
      {latestValues.iv && (
        <Box sx={{ mb: 2, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <Chip
            label={`IV: ${latestValues.iv.value.toFixed(2)}%`}
            sx={{
              backgroundColor: 'rgba(239, 83, 80, 0.2)',
              color: '#ef5350',
              fontWeight: 600,
              border: '1px solid rgba(239, 83, 80, 0.5)',
            }}
          />
          {getCurrentRV() && (
            <Chip
              label={`RV: ${getCurrentRV().toFixed(2)}%`}
              sx={{
                backgroundColor: 'rgba(102, 187, 106, 0.2)',
                color: '#66bb6a',
                fontWeight: 600,
                border: '1px solid rgba(102, 187, 106, 0.5)',
              }}
            />
          )}
          {stats?.safety && !stats.safety.is_safe && (
            <Chip
              label={stats.safety.violation_reason || 'Volatility Alert'}
              color="error"
              sx={{ fontWeight: 600 }}
            />
          )}
        </Box>
      )}

      {/* Error Display */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* Loading State */}
      {loading && chartData.length === 0 ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
          <CircularProgress />
        </Box>
      ) : (
        /* Chart */
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.1)" />
            <XAxis
              dataKey="timestamp"
              tickFormatter={formatXAxis}
              stroke="#aaa"
              style={{ fontSize: '12px' }}
            />
            <YAxis
              stroke="#aaa"
              style={{ fontSize: '12px' }}
              label={{
                value: 'Volatility (%)',
                angle: -90,
                position: 'insideLeft',
                style: { fill: '#aaa' },
              }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ paddingTop: '20px' }} iconType="line" />
            <Line
              type="monotone"
              dataKey="iv"
              stroke="#ef5350"
              strokeWidth={2}
              dot={false}
              name="Implied Volatility (IV)"
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="rv"
              stroke="#66bb6a"
              strokeWidth={2}
              dot={false}
              name="Realized Volatility (RV)"
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}

      {/* Footer */}
      <Box sx={{ mt: 2, textAlign: 'center' }}>
        <Typography variant="caption" sx={{ color: '#777' }}>
          Data updates every 30 seconds • Source: Delta Exchange India
        </Typography>
      </Box>
    </Paper>
  );
});

VolatilityChart.displayName = 'VolatilityChart';

export default VolatilityChart;
