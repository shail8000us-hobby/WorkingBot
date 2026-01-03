import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Chip,
  IconButton,
  Tooltip,
  CircularProgress,
  Divider,
  Button,
  Paper,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  TrendingUp,
  TrendingDown,
  ShowChart as ShowChartIcon,
  Edit as EditIcon,
  Close as CloseIcon,
} from '@mui/icons-material';
import api from '../utils/apiShim';
import { useInstance, parseInstanceName } from '../context/InstanceContext';
import SymbolBadge from './common/SymbolBadge';

const PositionsPanel = () => {
  const { selectedInstance, withInstance } = useInstance();
  const instanceInfo = parseInstanceName(selectedInstance);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [positionsData, setPositionsData] = useState(null);

  // Fetch positions for current instance
  const fetchPositions = async () => {
    try {
      // v6.0: Use instance parameter for filtering
      const { data } = await api.get(withInstance('/api/positions'));
      
      // API returns positions directly without a 'success' wrapper
      if (data?.status === 'NO_DATA' || data?.status === 'UNKNOWN') {
        setPositionsData({ positions: [], status: data.status });
      } else if (data && data.positions) {
        setPositionsData(data);
      } else if (data.error) {
        console.error('Failed to fetch positions:', data.error);
      }
    } catch (error) {
      console.error('Error fetching positions:', error);
    }
  };

  // Initial load and refresh when instance changes
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await fetchPositions();
      setLoading(false);
    };
    loadData();
  }, [selectedInstance]);

  // Auto-refresh every 5 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      fetchPositions();
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  // Manual refresh
  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchPositions();
    setRefreshing(false);
  };

  const formatCurrency = (value) => {
    return `$${Math.abs(value).toFixed(2)}`;
  };

  const formatNumber = (value, decimals = 4) => {
    return value.toFixed(decimals);
  };

  // Get PnL color
  const getPnlColor = (pnl) => {
    if (pnl > 0) return '#10b981'; // Green
    if (pnl < 0) return '#ef4444'; // Red
    return '#94a3b8'; // Gray
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  const positions = positionsData?.positions || [];
  const summary = positionsData?.summary || {};

  if (positionsData?.status === 'NO_DATA' || positionsData?.status === 'UNKNOWN') {
    return (
      <Paper sx={{ p: 4, textAlign: 'center', bgcolor: '#111827', border: '1px dashed #334155' }}>
        <CircularProgress size={24} sx={{ color: '#3b82f6', mb: 2 }} />
        <Typography variant="h6" color="#cbd5e1">Waiting for market data…</Typography>
        <Typography variant="body2" color="#64748b" sx={{ mt: 1 }}>
          Exchange feeds have not returned any open positions yet. This screen refreshes automatically once data arrives.
        </Typography>
      </Paper>
    );
  }

  return (
    <Box>
      {/* Header with Title and Actions */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box display="flex" alignItems="center" gap={1}>
          <ShowChartIcon sx={{ fontSize: 28, color: '#3b82f6' }} />
          <Typography variant="h5" fontWeight={600}>
            Current Positions
          </Typography>
          <SymbolBadge symbol={instanceInfo?.symbol || 'BTCUSD'} size="md" variant="solid" />
        </Box>
        <Box display="flex" gap={1}>
          <Tooltip title="Refresh positions from exchange">
            <IconButton 
              onClick={handleRefresh}
              disabled={refreshing}
              sx={{ 
                bgcolor: '#3b82f6',
                color: 'white',
                '&:hover': { bgcolor: '#2563eb' }
              }}
            >
              <RefreshIcon className={refreshing ? 'fa-spin' : ''} />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      <Grid container spacing={3}>
        {/* Individual Position Cards */}
        <Grid item xs={12} lg={8}>
          <Box display="flex" flexDirection="column" gap={2}>
            {positions.length === 0 ? (
              <Card sx={{ bgcolor: '#1e293b', border: '1px solid #334155' }}>
                <CardContent>
                  <Box 
                    display="flex" 
                    flexDirection="column" 
                    alignItems="center" 
                    justifyContent="center"
                    minHeight="200px"
                  >
                    <ShowChartIcon sx={{ fontSize: 48, color: '#64748b', mb: 2 }} />
                    <Typography variant="h6" color="#94a3b8">
                      No active positions
                    </Typography>
                    <Typography variant="body2" color="#64748b">
                      Click "Refresh" to load positions from exchange
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            ) : (
              positions.map((position, index) => (
                <Card 
                  key={index}
                  sx={{ 
                    bgcolor: '#1e293b',
                    border: '1px solid #334155',
                    borderLeft: `4px solid ${position.unrealized_pnl >= 0 ? '#10b981' : '#ef4444'}`,
                    transition: 'all 0.3s',
                    '&:hover': {
                      transform: 'translateY(-2px)',
                      boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
                      borderColor: '#475569'
                    }
                  }}
                >
                  <CardContent>
                    {/* Position Header */}
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                      <Box>
                        <Typography variant="h6" fontWeight={600} color="#f8fafc">
                          {position.symbol}
                        </Typography>
                        <Chip 
                          label={position.type} 
                          size="small"
                          sx={{ 
                            mt: 0.5,
                            bgcolor: position.type === 'OPTION' ? '#8b5cf6' : '#3b82f6',
                            color: 'white',
                            fontWeight: 500
                          }}
                        />
                      </Box>
                      <Typography
                        component={motion.p}
                        initial={{ opacity: 0, y: -4 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.3 }}
                        variant="h5"
                        fontWeight={700}
                        sx={{ color: getPnlColor(position.unrealized_pnl) }}
                      >
                        {position.unrealized_pnl >= 0 ? '+' : ''}{formatCurrency(position.unrealized_pnl)}
                      </Typography>
                    </Box>

                    {/* Position Details Grid */}
                    <Grid container spacing={2}>
                      <Grid item xs={6} sm={3}>
                        <Typography variant="caption" color="#94a3b8">Size</Typography>
                        <Typography variant="body1" fontWeight={600} color="#cbd5e1">
                          {position.size} ({position.side})
                        </Typography>
                      </Grid>
                      <Grid item xs={6} sm={3}>
                        <Typography variant="caption" color="#94a3b8">Current</Typography>
                        <Typography variant="body1" fontWeight={600} color="#cbd5e1">
                          {formatCurrency(position.current_price)}
                        </Typography>
                      </Grid>
                      <Grid item xs={6} sm={3}>
                        <Typography variant="caption" color="#94a3b8">Entry</Typography>
                        <Typography variant="body1" fontWeight={600} color="#cbd5e1">
                          {formatCurrency(position.entry_price)}
                        </Typography>
                      </Grid>
                      <Grid item xs={6} sm={3}>
                        <Typography variant="caption" color="#94a3b8">Delta</Typography>
                        <Typography variant="body1" fontWeight={600} color="#cbd5e1">
                          {formatNumber(position.delta)}
                        </Typography>
                      </Grid>
                    </Grid>
                  </CardContent>
                </Card>
              ))
            )}
          </Box>
        </Grid>

        {/* Portfolio Summary Card */}
        <Grid item xs={12} lg={4}>
          <Card 
            sx={{ 
              bgcolor: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)',
              background: 'linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%)',
              border: '1px solid #7c3aed',
              height: '100%'
            }}
          >
            <CardContent>
              <Box display="flex" alignItems="center" gap={1} mb={3}>
                <ShowChartIcon sx={{ color: 'white' }} />
                <Typography variant="h6" fontWeight={600} color="white">
                  Portfolio Summary
                </Typography>
              </Box>

              <Divider sx={{ bgcolor: 'rgba(255,255,255,0.2)', mb: 3 }} />

              {/* Summary Metrics */}
              <Box display="flex" flexDirection="column" gap={2.5}>
                <Box>
                  <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                    Total Positions
                  </Typography>
                  <Typography variant="h4" fontWeight={700} color="white">
                    {summary.total_positions || 0}
                  </Typography>
                </Box>

                <Box>
                  <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                    Unrealized P&L
                  </Typography>
                  <Typography 
                    variant="h4" 
                    fontWeight={700}
                    sx={{ color: summary.total_pnl >= 0 ? '#10b981' : '#ef4444' }}
                  >
                    {summary.total_pnl >= 0 ? '+' : ''}{formatCurrency(summary.total_pnl || 0)}
                  </Typography>
                </Box>

                <Divider sx={{ bgcolor: 'rgba(255,255,255,0.2)' }} />

                <Grid container spacing={2}>
                  <Grid item xs={12}>
                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                      Portfolio Δ (Delta)
                    </Typography>
                    <Typography variant="h6" fontWeight={600} color="white">
                      {formatNumber(summary.portfolio_delta || 0)}
                    </Typography>
                  </Grid>

                  <Grid item xs={12}>
                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                      Portfolio ν (Vega)
                    </Typography>
                    <Typography variant="h6" fontWeight={600} color="white">
                      {formatNumber(summary.portfolio_vega || 0)}
                    </Typography>
                  </Grid>

                  <Grid item xs={12}>
                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                      Portfolio θ (Theta)
                    </Typography>
                    <Typography variant="h6" fontWeight={600} color="white">
                      {formatNumber(summary.portfolio_theta || 0)}
                    </Typography>
                  </Grid>
                </Grid>

                <Divider sx={{ bgcolor: 'rgba(255,255,255,0.2)' }} />

                <Box>
                  <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                    Data Source
                  </Typography>
                  <Typography variant="body2" fontWeight={600} sx={{ color: '#c084fc' }}>
                    {summary.data_source || 'delta_exchange'}
                  </Typography>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default PositionsPanel;
