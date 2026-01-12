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
  ToggleButtonGroup,
  ToggleButton,
  FormControlLabel,
  Switch,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  TrendingUp,
  TrendingDown,
  ShowChart as ShowChartIcon,
  Edit as EditIcon,
  Close as CloseIcon,
  FilterList,
} from '@mui/icons-material';
import api from '../utils/apiShim';
import { useInstance, parseInstanceName } from '../context/InstanceContext';
import SymbolBadge from './common/SymbolBadge';

const PositionsPanel = () => {
  const { selectedInstance, withInstance, instances } = useInstance();
  const instanceInfo = parseInstanceName(selectedInstance);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [positionsData, setPositionsData] = useState(null);
  const [filterMode, setFilterMode] = useState('all'); // 'all', 'futures', 'options', 'btcusd', 'ethusd'
  const [showBotOnly, setShowBotOnly] = useState(false);

  // Available symbols from instances
  const availableSymbols = [...new Set(instances.map(i => parseInstanceName(i.name)?.symbol).filter(Boolean))];

  // Fetch ALL positions (futures, options, manual, bot-driven)
  const fetchPositions = async () => {
    try {
      // Fetch ALL positions without instance filter to get everything
      const { data } = await api.get('/api/positions?all=true');
      
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

  // Initial load
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await fetchPositions();
      setLoading(false);
    };
    loadData();
  }, []);

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

  const getPnlColor = (pnl) => {
    if (pnl > 0) return '#10b981';
    if (pnl < 0) return '#ef4444';
    return '#94a3b8';
  };

  // Get symbol color
  const getSymbolColor = (symbol) => {
    const colors = {
      'BTCUSD': { bg: '#f7931a20', text: '#f7931a' },
      'ETHUSD': { bg: '#627eea20', text: '#627eea' },
    };
    return colors[symbol] || { bg: '#64748b20', text: '#64748b' };
  };

  // Filter positions based on selected filter
  const filterPositions = (positions) => {
    if (!positions) return [];
    
    let filtered = positions;
    
    // Filter by type
    if (filterMode === 'futures') {
      filtered = filtered.filter(p => p.type !== 'OPTION');
    } else if (filterMode === 'options') {
      filtered = filtered.filter(p => p.type === 'OPTION');
    } else if (filterMode === 'btcusd') {
      filtered = filtered.filter(p => p.symbol?.includes('BTC'));
    } else if (filterMode === 'ethusd') {
      filtered = filtered.filter(p => p.symbol?.includes('ETH'));
    }
    
    // Filter bot-only positions
    if (showBotOnly) {
      filtered = filtered.filter(p => p.source === 'bot' || p.tags?.includes('DBOT_'));
    }
    
    return filtered;
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  const allPositions = positionsData?.positions || [];
  const positions = filterPositions(allPositions);
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
      {/* Header with Title and Filter Controls */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3} flexWrap="wrap" gap={2}>
        <Box display="flex" alignItems="center" gap={1}>
          <ShowChartIcon sx={{ fontSize: 28, color: '#3b82f6' }} />
          <Typography variant="h5" fontWeight={600}>
            All Positions
          </Typography>
          <Chip 
            label={`${positions.length} of ${allPositions.length}`} 
            size="small" 
            color="primary"
            variant="outlined"
          />
        </Box>
        
        {/* Filter Controls */}
        <Box display="flex" alignItems="center" gap={2} flexWrap="wrap">
          <ToggleButtonGroup
            value={filterMode}
            exclusive
            onChange={(e, val) => val && setFilterMode(val)}
            size="small"
          >
            <ToggleButton value="all">All</ToggleButton>
            <ToggleButton value="futures">Futures</ToggleButton>
            <ToggleButton value="options">Options</ToggleButton>
            {availableSymbols.includes('BTCUSD') && (
              <ToggleButton value="btcusd" sx={{ color: filterMode === 'btcusd' ? '#f7931a' : 'inherit' }}>
                BTCUSD
              </ToggleButton>
            )}
            {availableSymbols.includes('ETHUSD') && (
              <ToggleButton value="ethusd" sx={{ color: filterMode === 'ethusd' ? '#627eea' : 'inherit' }}>
                ETHUSD
              </ToggleButton>
            )}
          </ToggleButtonGroup>
          
          <FormControlLabel
            control={
              <Switch
                size="small"
                checked={showBotOnly}
                onChange={(e) => setShowBotOnly(e.target.checked)}
              />
            }
            label="Bot Only"
            sx={{ color: '#94a3b8' }}
          />
          
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
              positions.map((position, index) => {
                // Extract base symbol (BTCUSD, ETHUSD) from position symbol
                const baseSymbol = position.symbol?.includes('BTC') ? 'BTCUSD' : 
                                   position.symbol?.includes('ETH') ? 'ETHUSD' : null;
                const symbolColors = baseSymbol ? getSymbolColor(baseSymbol) : { bg: '#64748b20', text: '#64748b' };
                
                return (
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
                      <Box display="flex" alignItems="center" gap={1}>
                        <Box>
                          <Typography variant="h6" fontWeight={600} color="#f8fafc">
                            {position.symbol}
                          </Typography>
                          <Box display="flex" alignItems="center" gap={1} mt={0.5}>
                            <Chip 
                              label={position.type} 
                              size="small"
                              sx={{ 
                                bgcolor: position.type === 'OPTION' ? '#8b5cf6' : '#3b82f6',
                                color: 'white',
                                fontWeight: 500
                              }}
                            />
                            {baseSymbol && (
                              <Chip 
                                label={baseSymbol} 
                                size="small"
                                sx={{ 
                                  bgcolor: symbolColors.bg,
                                  color: symbolColors.text,
                                  fontWeight: 600
                                }}
                              />
                            )}
                            {position.source === 'bot' && (
                              <Chip 
                                label="BOT" 
                                size="small"
                                sx={{ bgcolor: '#10b98120', color: '#10b981' }}
                              />
                            )}
                          </Box>
                        </Box>
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
              );
              })
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
