import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Chip,
  IconButton,
  Button,
  LinearProgress,
  Alert,
  Tooltip,
  Divider,
  Skeleton,
  Snackbar,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  ShowChart,
  PlayArrow,
  Pause,
  Add,
  Refresh,
  Visibility,
} from '@mui/icons-material';
import { motion } from 'framer-motion';
import { useInstanceSafe, parseInstanceName as parseInstance } from '../context/InstanceContext';
import SymbolBadge from './common/SymbolBadge';
import AddSymbolDialog from './AddSymbolDialog';
import { getSymbolColor } from '../utils/symbolColors.ts';

/**
 * SymbolPortfolio - Multi-Symbol Overview Dashboard (Phase 5)
 *
 * Shows all configured symbols at once with:
 * - Status (enabled/disabled)
 * - Current PnL
 * - Position count
 * - Grid configuration
 * - Quick actions (view, enable/disable)
 *
 * Modern UI Features:
 * - Skeleton loading states
 * - Smooth animations with framer-motion
 * - Real-time data refresh
 * - Visual status indicators
 */
const SymbolPortfolio = () => {
  const instanceContext = useInstanceSafe();
  const instances = instanceContext?.instances || [];
  const selectedInstance = instanceContext?.selectedInstance || null;
  const changeInstance = instanceContext?.changeInstance || (() => {});
  const loadInstances = instanceContext?.loadInstances || (() => {});
  const instancesLoading = instanceContext?.loading || false;

  // Backward compat: derive symbols from instances
  const symbols = instances
    .map((i) => {
      const parsed = parseInstance(i.name);
      return { name: parsed?.symbol, enabled: i.enabled };
    })
    .filter((v, i, a) => a.findIndex((t) => t.name === v.name) === i);
  const selectedSymbol = parseInstance(selectedInstance)?.symbol;
  const changeSymbol = (sym) => changeInstance(`${sym}_LONG`);
  const loadSymbols = loadInstances;
  const symbolsLoading = instancesLoading;

  const [portfolioData, setPortfolioData] = useState({});
  const [loading, setLoading] = useState(true);
  const [totalPnL, setTotalPnL] = useState(0);
  const [totalCapital, setTotalCapital] = useState(0);
  const [lastRefresh, setLastRefresh] = useState(null);

  // Add Symbol Dialog state
  const [addSymbolDialogOpen, setAddSymbolDialogOpen] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  // Fetch portfolio data for all symbols
  const fetchPortfolioData = useCallback(async () => {
    // Wait for instances to load
    if (instancesLoading) return;
    if (symbols.length === 0) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const data = {};
      let pnlSum = 0;
      let capitalSum = 0;

      // Fetch data for each symbol in parallel
      const promises = symbols.map(async (symbol) => {
        try {
          // Fetch positions
          const posResponse = await fetch(`/api/positions?symbol=${symbol.name}`);
          const posData = await posResponse.json();

          // Fetch config
          const configResponse = await fetch(`/api/config/flat?symbol=${symbol.name}`);
          const configData = await configResponse.json();

          const positions = posData?.positions || [];
          const unrealizedPnL = positions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0);

          data[symbol.name] = {
            symbol: symbol.name,
            enabled: symbol.enabled,
            positions: positions.length,
            pnl: unrealizedPnL,
            gridLower: configData?.grid_lower || 0,
            gridUpper: configData?.grid_upper || 0,
            gridLevels: configData?.grid_levels || 0,
            capital: configData?.total_capital || 0,
          };

          if (symbol.enabled) {
            pnlSum += unrealizedPnL;
            capitalSum += configData?.total_capital || 0;
          }
        } catch (err) {
          console.error(`Failed to fetch data for ${symbol.name}:`, err);
          data[symbol.name] = {
            symbol: symbol.name,
            enabled: symbol.enabled,
            error: true,
          };
        }
      });

      await Promise.all(promises);

      setPortfolioData(data);
      setTotalPnL(pnlSum);
      setTotalCapital(capitalSum);
    } catch (err) {
      console.error('Failed to fetch portfolio data:', err);
    } finally {
      setLoading(false);
      setLastRefresh(new Date());
    }
  }, [symbols]);

  useEffect(() => {
    if (symbols.length > 0) {
      fetchPortfolioData();
    }
  }, [symbols, fetchPortfolioData]);

  // Auto-refresh every 10 seconds
  useEffect(() => {
    if (symbols.length === 0) return;
    const interval = setInterval(fetchPortfolioData, 10000);
    return () => clearInterval(interval);
  }, [symbols, fetchPortfolioData]);

  const handleViewSymbol = (symbolName) => {
    changeSymbol(symbolName);
  };

  const formatCurrency = (value) => {
    const sign = value >= 0 ? '+' : '';
    return `${sign}$${value.toFixed(2)}`;
  };

  const getPnLColor = (pnl) => {
    if (pnl > 0) return '#10b981';
    if (pnl < 0) return '#ef4444';
    return '#94a3b8';
  };

  // Handle new symbol creation
  const handleAddSymbolSuccess = useCallback(
    (symbolName) => {
      setSnackbar({
        open: true,
        message: `Symbol ${symbolName} added successfully! Enable it to start trading.`,
        severity: 'success',
      });
      // Reload symbols to show new one
      loadSymbols();
      fetchPortfolioData();
    },
    [loadSymbols, fetchPortfolioData]
  );

  // Loading skeleton component
  const SkeletonCard = () => (
    <Card sx={{ bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider' }}>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
          <Skeleton variant="rounded" width={80} height={28} />
          <Skeleton variant="rounded" width={60} height={20} />
        </Box>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          <Skeleton variant="text" width="60%" />
          <Skeleton variant="text" width="80%" />
          <Skeleton variant="text" width="40%" />
        </Box>
        <Box sx={{ mt: 2 }}>
          <Skeleton variant="rounded" width="100%" height={36} />
        </Box>
      </CardContent>
    </Card>
  );

  // Show loading state when context is loading
  if (instancesLoading) {
    return (
      <Box sx={{ p: 3 }}>
        <Box sx={{ mb: 4 }}>
          <Skeleton variant="text" width={300} height={40} />
          <Skeleton variant="text" width={200} height={20} sx={{ mt: 0.5 }} />
        </Box>
        <Grid container spacing={3}>
          {[1, 2, 3].map((i) => (
            <Grid item xs={12} sm={6} lg={4} key={i}>
              <SkeletonCard />
            </Grid>
          ))}
        </Grid>
      </Box>
    );
  }

  // Show empty state when no instances configured
  if (!instancesLoading && symbols.length === 0) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <ShowChart sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
        <Typography variant="h5" color="text.secondary" gutterBottom>
          No Trading Instances Configured
        </Typography>
        <Typography variant="body2" color="text.disabled" sx={{ mb: 3 }}>
          Add instances in config/symbols.yaml to see your portfolio here
        </Typography>
        <Button variant="outlined" startIcon={<Refresh />} onClick={() => loadInstances()}>
          Refresh
        </Button>
      </Box>
    );
  }

  // Show loading state for data fetch
  if (loading && Object.keys(portfolioData).length === 0) {
    return (
      <Box sx={{ p: 3 }}>
        <Box sx={{ mb: 4 }}>
          <Skeleton variant="text" width={300} height={40} />
          <Skeleton variant="text" width={200} height={20} sx={{ mt: 0.5 }} />
        </Box>
        <Grid container spacing={3}>
          {[1, 2, 3].map((i) => (
            <Grid item xs={12} sm={6} lg={4} key={i}>
              <SkeletonCard />
            </Grid>
          ))}
        </Grid>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box
        sx={{
          mb: 4,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 2,
        }}
      >
        <Box>
          <Typography
            variant="h4"
            sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1 }}
          >
            <ShowChart sx={{ fontSize: 32 }} />
            Multi-Symbol Portfolio
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mt: 0.5 }}>
            <Typography variant="body2" color="text.secondary">
              Overview of all configured trading symbols
            </Typography>
            {lastRefresh && (
              <Typography variant="caption" color="text.disabled" sx={{ fontSize: '0.7rem' }}>
                • Last updated: {lastRefresh.toLocaleTimeString()}
              </Typography>
            )}
          </Box>
        </Box>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          {loading && (
            <Typography variant="caption" color="primary.main">
              Refreshing...
            </Typography>
          )}
          <Tooltip title="Refresh all symbol data">
            <IconButton
              onClick={() => {
                loadSymbols();
                fetchPortfolioData();
              }}
              sx={{
                bgcolor: 'primary.main',
                color: 'white',
                '&:hover': { bgcolor: 'primary.dark' },
              }}
            >
              <Refresh />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Portfolio Summary */}
      <Grid container spacing={2} sx={{ mb: 4 }}>
        <Grid item xs={12} md={4}>
          <Card sx={{ bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider' }}>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Total Portfolio PnL
              </Typography>
              <Typography
                variant="h4"
                sx={{
                  fontWeight: 'bold',
                  color: getPnLColor(totalPnL),
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1,
                }}
              >
                {totalPnL >= 0 ? <TrendingUp /> : <TrendingDown />}
                {formatCurrency(totalPnL)}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card sx={{ bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider' }}>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Total Capital Allocated
              </Typography>
              <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
                ${totalCapital.toLocaleString()}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card sx={{ bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider' }}>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Active Symbols
              </Typography>
              <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
                {symbols.filter((s) => s.enabled).length} / {symbols.length}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Symbol Cards */}
      <Grid container spacing={3}>
        {symbols.map((symbol, index) => {
          const data = portfolioData[symbol.name] || {};
          const color = getSymbolColor(symbol.name);
          const isSelected = selectedSymbol === symbol.name;

          return (
            <Grid item xs={12} sm={6} lg={4} key={symbol.name}>
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
              >
                <Card
                  sx={{
                    bgcolor: 'background.paper',
                    border: '2px solid',
                    borderColor: isSelected ? color : 'divider',
                    borderLeft: `6px solid ${color}`,
                    transition: 'all 0.3s',
                    '&:hover': {
                      transform: 'translateY(-4px)',
                      boxShadow: `0 8px 24px ${color}33`,
                      borderColor: color,
                    },
                  }}
                >
                  <CardContent>
                    {/* Header */}
                    <Box
                      sx={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        mb: 2,
                      }}
                    >
                      <SymbolBadge symbol={symbol.name} size="lg" variant="solid" />
                      <Chip
                        icon={symbol.enabled ? <PlayArrow /> : <Pause />}
                        label={symbol.enabled ? 'Active' : 'Paused'}
                        color={symbol.enabled ? 'success' : 'default'}
                        size="small"
                      />
                    </Box>

                    <Divider sx={{ my: 2 }} />

                    {/* Stats */}
                    {loading ? (
                      <LinearProgress />
                    ) : data.error ? (
                      <Alert severity="error" sx={{ py: 0 }}>
                        Failed to load data
                      </Alert>
                    ) : (
                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                        {/* PnL */}
                        <Box>
                          <Typography variant="caption" color="text.secondary">
                            Unrealized PnL
                          </Typography>
                          <Typography
                            variant="h6"
                            sx={{
                              fontWeight: 'bold',
                              color: getPnLColor(data.pnl || 0),
                              display: 'flex',
                              alignItems: 'center',
                              gap: 0.5,
                            }}
                          >
                            {data.pnl >= 0 ? (
                              <TrendingUp fontSize="small" />
                            ) : (
                              <TrendingDown fontSize="small" />
                            )}
                            {formatCurrency(data.pnl || 0)}
                          </Typography>
                        </Box>

                        {/* Positions */}
                        <Box>
                          <Typography variant="caption" color="text.secondary">
                            Open Positions
                          </Typography>
                          <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                            {data.positions || 0}
                          </Typography>
                        </Box>

                        {/* Grid Config */}
                        <Box>
                          <Typography variant="caption" color="text.secondary">
                            Grid Range
                          </Typography>
                          <Typography variant="body2" sx={{ fontWeight: 600 }}>
                            ${data.gridLower?.toLocaleString()} - $
                            {data.gridUpper?.toLocaleString()}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {data.gridLevels} levels
                          </Typography>
                        </Box>

                        {/* Capital */}
                        <Box>
                          <Typography variant="caption" color="text.secondary">
                            Allocated Capital
                          </Typography>
                          <Typography variant="body2" sx={{ fontWeight: 600 }}>
                            ${data.capital?.toLocaleString()}
                          </Typography>
                        </Box>
                      </Box>
                    )}

                    <Divider sx={{ my: 2 }} />

                    {/* Actions */}
                    <Box sx={{ display: 'flex', gap: 1 }}>
                      <Button
                        fullWidth
                        variant={isSelected ? 'contained' : 'outlined'}
                        startIcon={<Visibility />}
                        onClick={() => handleViewSymbol(symbol.name)}
                        disabled={isSelected}
                        sx={{
                          borderColor: color,
                          color: isSelected ? 'white' : color,
                          bgcolor: isSelected ? color : 'transparent',
                          '&:hover': {
                            borderColor: color,
                            bgcolor: isSelected ? color : `${color}15`,
                          },
                        }}
                      >
                        {isSelected ? 'Current' : 'View'}
                      </Button>
                    </Box>
                  </CardContent>
                </Card>
              </motion.div>
            </Grid>
          );
        })}

        {/* Add New Symbol Card */}
        <Grid item xs={12} sm={6} lg={4}>
          <Card
            onClick={() => setAddSymbolDialogOpen(true)}
            sx={{
              bgcolor: 'background.paper',
              border: '2px dashed',
              borderColor: 'divider',
              minHeight: '400px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              transition: 'all 0.3s',
              '&:hover': {
                borderColor: 'primary.main',
                bgcolor: 'rgba(99, 102, 241, 0.05)',
              },
            }}
          >
            <CardContent sx={{ textAlign: 'center' }}>
              <Add sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" color="text.secondary" gutterBottom>
                Add New Symbol
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Configure additional trading pairs
              </Typography>
              <Button
                variant="outlined"
                startIcon={<Add />}
                sx={{ mt: 2 }}
                onClick={(e) => {
                  e.stopPropagation();
                  setAddSymbolDialogOpen(true);
                }}
              >
                Add Symbol
              </Button>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Add Symbol Dialog */}
      <AddSymbolDialog
        open={addSymbolDialogOpen}
        onClose={() => setAddSymbolDialogOpen(false)}
        onSuccess={handleAddSymbolSuccess}
        existingSymbols={symbols.map((s) => s.name)}
      />

      {/* Success/Error Snackbar */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          severity={snackbar.severity}
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default SymbolPortfolio;
