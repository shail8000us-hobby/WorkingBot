/**
 * Futures Positions Panel
 *
 * Displays futures (perpetual) positions from Delta Exchange.
 * Designed to be embedded within the Options Panel above Pending Orders.
 *
 * Created: January 17, 2026
 * Purpose: Show futures positions with real-time data
 *
 * ⚠️ COMPLETE SEPARATION FROM OPTIONS TRADING
 * This component only displays futures positions, never touches options logic.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Chip,
  IconButton,
  Tooltip,
  CircularProgress,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Collapse,
  Alert,
  Button,
  TextField,
  InputAdornment,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  TrendingUp,
  TrendingDown,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  ShowChart as FuturesIcon,
  ShoppingCart as BuyIcon,
  Sell as SellIcon,
  Close as CloseIcon,
  Warning as WarningIcon,
  DeleteSweep as CloseAllIcon,
} from '@mui/icons-material';
import api from '../../utils/apiShim';
import FuturesTradeDialog from './FuturesTradeDialog';
import FuturesPayoffGraph from './FuturesPayoffGraph';

const FuturesPanel = ({ pollInterval = 5000 }) => {
  // State
  const [positions, setPositions] = useState([]);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(true);
  const [summary, setSummary] = useState({
    total_positions: 0,
    total_unrealized_pnl: 0,
    total_realized_pnl: 0,
  });

  // Trade dialog state
  const [tradeDialog, setTradeDialog] = useState({ open: false, position: null, side: null });

  // Max loss state (per position, stored in localStorage)
  const [maxLossSettings, setMaxLossSettings] = useState({});
  const [maxLossInput, setMaxLossInput] = useState({});

  // Close all confirmation dialog
  const [closeAllDialog, setCloseAllDialog] = useState(false);
  const [closingAll, setClosingAll] = useState(false);

  // Fetch futures positions
  const fetchPositions = useCallback(async () => {
    try {
      const { data } = await api.get('/api/futures/positions');
      if (data?.success) {
        setPositions(data.positions || []);
        setSummary(data.summary || {});
        setError(null);
      } else {
        setError(data?.error || 'Failed to fetch positions');
      }
    } catch (err) {
      console.error('Failed to fetch futures positions:', err);
      setError(err.message);
    }
  }, []);

  // Fetch futures orders
  const fetchOrders = useCallback(async () => {
    try {
      const { data } = await api.get('/api/futures/orders');
      if (data?.success) {
        setOrders(data.orders || []);
      }
    } catch (err) {
      console.error('Failed to fetch futures orders:', err);
    }
  }, []);

  // Cancel futures order
  const handleCancelFuturesOrder = useCallback(async (order) => {
    if (!window.confirm('Cancel this order?')) {
      return;
    }
    
    try {
      const { data } = await api.delete(`/api/options-chain/order/${order.id}/${order.product_id}`);
      if (data?.success) {
        // Refresh orders list
        await fetchOrders();
      } else {
        console.error('Failed to cancel order:', data?.error);
        alert(`Failed to cancel order: ${data?.error || 'Unknown error'}`);
      }
    } catch (err) {
      console.error('Failed to cancel order:', err);
      alert(`Failed to cancel order: ${err.message || 'Unknown error'}`);
    }
  }, [fetchOrders]);

  // Initial load
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([fetchPositions(), fetchOrders()]);
      setLoading(false);
    };
    loadData();
  }, [fetchPositions, fetchOrders]);

  // Auto-refresh
  useEffect(() => {
    const interval = setInterval(() => {
      fetchPositions();
      fetchOrders();
    }, pollInterval);
    return () => clearInterval(interval);
  }, [fetchPositions, fetchOrders, pollInterval]);

  // Load max loss settings from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem('futures_max_loss_settings');
      if (saved) {
        const parsed = JSON.parse(saved);
        setMaxLossSettings(parsed);

        // Initialize max loss monitor for active settings
        Object.entries(parsed).forEach(([productId, setting]) => {
          if (setting.enabled && setting.max_loss > 0) {
            activateMaxLoss(parseInt(productId), setting.max_loss);
          }
        });
      }
    } catch (err) {
      console.error('Failed to load max loss settings:', err);
    }
  }, []);

  // Save max loss settings to localStorage
  const saveMaxLossSettings = (settings) => {
    try {
      localStorage.setItem('futures_max_loss_settings', JSON.stringify(settings));
      setMaxLossSettings(settings);
    } catch (err) {
      console.error('Failed to save max loss settings:', err);
    }
  };

  // Manual refresh
  const handleRefresh = async () => {
    setRefreshing(true);
    await Promise.all([fetchPositions(), fetchOrders()]);
    setRefreshing(false);
  };

  // Open trade dialog
  const handleOpenTrade = (position, side) => {
    setTradeDialog({ open: true, position, side });
  };

  // Close trade dialog
  const handleCloseTrade = (success) => {
    setTradeDialog({ open: false, position: null, side: null });
    if (success) {
      // Refresh positions after successful trade
      setTimeout(() => {
        fetchPositions();
        fetchOrders();
      }, 1000);
    }
  };

  // Close single position
  const handleClosePosition = async (position) => {
    if (!window.confirm(`Close position ${position.symbol}?`)) {
      return;
    }

    try {
      const { data } = await api.post(`/api/futures/trade/close/${position.product_id}`);

      if (data?.success) {
        // Refresh positions
        await fetchPositions();

        // Remove max loss setting for this position
        const newSettings = { ...maxLossSettings };
        delete newSettings[position.product_id];
        saveMaxLossSettings(newSettings);
      } else {
        alert(`Failed to close position: ${data?.error || 'Unknown error'}`);
      }
    } catch (err) {
      console.error('Failed to close position:', err);
      alert(`Error: ${err.message}`);
    }
  };

  // Handle max loss input change
  const handleMaxLossChange = (productId, value) => {
    setMaxLossInput({
      ...maxLossInput,
      [productId]: value,
    });
  };

  // Activate max loss monitoring
  const activateMaxLoss = async (productId, maxLoss) => {
    try {
      const position = positions.find((p) => p.product_id === productId);
      if (!position) return;

      const { data } = await api.post('/api/futures/max-loss/set', {
        product_id: productId,
        symbol: position.symbol,
        max_loss: parseFloat(maxLoss),
        enabled: true,
      });

      if (data?.success) {
        const newSettings = {
          ...maxLossSettings,
          [productId]: {
            max_loss: parseFloat(maxLoss),
            enabled: true,
            symbol: position.symbol,
          },
        };
        saveMaxLossSettings(newSettings);

        // Clear input
        setMaxLossInput({
          ...maxLossInput,
          [productId]: '',
        });
      } else {
        alert(`Failed to set max loss: ${data?.error || 'Unknown error'}`);
      }
    } catch (err) {
      console.error('Failed to activate max loss:', err);
      alert(`Error: ${err.message}`);
    }
  };

  // Disable max loss monitoring
  const disableMaxLoss = async (productId) => {
    try {
      const { data } = await api.post(`/api/futures/max-loss/disable/${productId}`);

      if (data?.success) {
        const newSettings = { ...maxLossSettings };
        delete newSettings[productId];
        saveMaxLossSettings(newSettings);
      }
    } catch (err) {
      console.error('Failed to disable max loss:', err);
    }
  };

  // Close all positions
  const handleCloseAll = async () => {
    setClosingAll(true);
    setCloseAllDialog(false);

    try {
      const { data } = await api.post('/api/futures/trade/close-all');

      if (data?.success) {
        alert(`Closed ${data.closed_count}/${data.total_count} positions`);

        // Clear all max loss settings
        saveMaxLossSettings({});

        // Refresh positions
        await fetchPositions();
      } else {
        alert(`Failed to close all positions: ${data?.error || 'Unknown error'}`);
      }
    } catch (err) {
      console.error('Failed to close all positions:', err);
      alert(`Error: ${err.message}`);
    } finally {
      setClosingAll(false);
    }
  };

  // Format price
  const formatPrice = (price) => {
    if (!price || isNaN(price)) return '$0.00';
    return `$${parseFloat(price).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  // Format PnL with color
  const formatPnL = (pnl) => {
    if (!pnl || isNaN(pnl)) return { text: '$0.00', color: 'text.secondary' };
    const value = parseFloat(pnl);
    const color = value > 0 ? '#10b981' : value < 0 ? '#ef4444' : 'text.secondary';
    const prefix = value > 0 ? '+' : '';
    return {
      text: `${prefix}$${Math.abs(value).toFixed(4)}`,
      color,
    };
  };

  // If no positions and no orders, don't render
  if (!loading && positions.length === 0 && orders.length === 0) {
    return null;
  }

  return (
    <Box sx={{ mb: 2 }}>
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          p: 1.5,
          borderRadius: 1,
          bgcolor: 'rgba(14, 165, 233, 0.1)',
          border: '1px solid rgba(14, 165, 233, 0.3)',
          cursor: 'pointer',
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <FuturesIcon sx={{ color: 'primary.main' }} />
          <Typography variant="subtitle1" sx={{ fontWeight: 'bold', color: 'text.primary' }}>
            Futures Positions ({positions.length})
          </Typography>
          {positions.length > 0 && (
            <Chip
              label="Live"
              size="small"
              color="info"
              sx={{ animation: 'pulse 1.5s infinite' }}
            />
          )}
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {/* Close All Button */}
          {positions.length > 0 && (
            <Tooltip title="Close All Positions">
              <Button
                size="small"
                variant="outlined"
                color="error"
                startIcon={<CloseAllIcon />}
                onClick={(e) => {
                  e.stopPropagation();
                  setCloseAllDialog(true);
                }}
                disabled={closingAll}
              >
                Close All
              </Button>
            </Tooltip>
          )}

          {/* Summary PnL */}
          {positions.length > 0 && (
            <Chip
              icon={summary.total_unrealized_pnl >= 0 ? <TrendingUp /> : <TrendingDown />}
              label={formatPnL(summary.total_unrealized_pnl).text}
              size="small"
              sx={{
                bgcolor:
                  summary.total_unrealized_pnl >= 0
                    ? 'rgba(16, 185, 129, 0.2)'
                    : 'rgba(239, 68, 68, 0.2)',
                color: summary.total_unrealized_pnl >= 0 ? '#10b981' : '#ef4444',
                fontWeight: 'bold',
              }}
            />
          )}
          <Tooltip title="Refresh">
            <IconButton
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                handleRefresh();
              }}
              disabled={refreshing}
            >
              {refreshing ? <CircularProgress size={16} /> : <RefreshIcon fontSize="small" />}
            </IconButton>
          </Tooltip>
          {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        </Box>
      </Box>

      {/* Content */}
      <Collapse in={expanded}>
        <Box sx={{ mt: 1 }}>
          {/* Loading */}
          {loading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
              <CircularProgress size={24} />
            </Box>
          )}

          {/* Error */}
          {error && !loading && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          {/* Positions Table */}
          {!loading && positions.length > 0 && (
            <>
              <TableContainer
                component={Paper}
                sx={{ bgcolor: 'background.paper', borderRadius: 1 }}
              >
                <Table size="small">
                  <TableHead>
                    <TableRow sx={{ bgcolor: 'rgba(14, 165, 233, 0.1)' }}>
                      <TableCell sx={{ fontWeight: 'bold' }}>Symbol</TableCell>
                      <TableCell align="center" sx={{ fontWeight: 'bold' }}>
                        Side
                      </TableCell>
                      <TableCell align="right" sx={{ fontWeight: 'bold' }}>
                        Size
                      </TableCell>
                      <TableCell align="right" sx={{ fontWeight: 'bold' }}>
                        Entry
                      </TableCell>
                      <TableCell align="right" sx={{ fontWeight: 'bold' }}>
                        Mark
                      </TableCell>
                      <TableCell align="right" sx={{ fontWeight: 'bold' }}>
                        Liq. Price
                      </TableCell>
                      <TableCell align="right" sx={{ fontWeight: 'bold' }}>
                        Unrealized PnL
                      </TableCell>
                      <TableCell align="right" sx={{ fontWeight: 'bold' }}>
                        Margin
                      </TableCell>
                      <TableCell align="center" sx={{ fontWeight: 'bold' }}>
                        Max Loss
                      </TableCell>
                      <TableCell align="center" sx={{ fontWeight: 'bold' }}>
                        Actions
                      </TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {positions.map((pos) => {
                      const pnl = formatPnL(pos.unrealized_pnl);
                      const productId = pos.product_id;
                      const hasMaxLoss = maxLossSettings[productId]?.enabled;
                      const maxLossValue = maxLossSettings[productId]?.max_loss || '';

                      return (
                        <TableRow
                          key={`${pos.symbol}-${pos.product_id}`}
                          sx={{ '&:hover': { bgcolor: 'action.hover' } }}
                        >
                          <TableCell>
                            <Typography
                              variant="body2"
                              sx={{ fontFamily: 'monospace', fontWeight: 600 }}
                            >
                              {pos.symbol}
                            </Typography>
                          </TableCell>
                          <TableCell align="center">
                            <Chip
                              label={pos.side?.toUpperCase()}
                              size="small"
                              color={pos.side === 'long' ? 'success' : 'error'}
                              sx={{ fontWeight: 'bold', minWidth: 55 }}
                            />
                          </TableCell>
                          <TableCell align="right">
                            <Typography variant="body2" sx={{ fontWeight: 500 }}>
                              {Math.abs(pos.size)}
                            </Typography>
                          </TableCell>
                          <TableCell align="right">
                            <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                              {formatPrice(pos.entry_price)}
                            </Typography>
                          </TableCell>
                          <TableCell align="right">
                            <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                              {formatPrice(pos.mark_price)}
                            </Typography>
                          </TableCell>
                          <TableCell align="right">
                            <Typography
                              variant="body2"
                              sx={{
                                fontFamily: 'monospace',
                                color: 'warning.main',
                              }}
                            >
                              {formatPrice(pos.liquidation_price)}
                            </Typography>
                          </TableCell>
                          <TableCell align="right">
                            <Typography
                              variant="body2"
                              sx={{
                                fontWeight: 'bold',
                                color: pnl.color,
                                fontFamily: 'monospace',
                              }}
                            >
                              {pnl.text}
                            </Typography>
                          </TableCell>
                          <TableCell align="right">
                            <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                              ${pos.margin?.toFixed(4)}
                            </Typography>
                          </TableCell>
                          <TableCell align="center">
                            {hasMaxLoss ? (
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                <Chip
                                  icon={<WarningIcon />}
                                  label={`$${maxLossValue}`}
                                  size="small"
                                  color="warning"
                                  onDelete={() => disableMaxLoss(productId)}
                                />
                              </Box>
                            ) : (
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                <TextField
                                  size="small"
                                  type="number"
                                  placeholder="Max Loss"
                                  value={maxLossInput[productId] || ''}
                                  onChange={(e) => handleMaxLossChange(productId, e.target.value)}
                                  sx={{ width: 90 }}
                                  InputProps={{
                                    startAdornment: (
                                      <InputAdornment position="start">$</InputAdornment>
                                    ),
                                  }}
                                  inputProps={{ min: 0, step: 1 }}
                                />
                                <Tooltip title="Activate Max Loss">
                                  <IconButton
                                    size="small"
                                    color="warning"
                                    onClick={() => {
                                      const value = maxLossInput[productId];
                                      if (value && parseFloat(value) > 0) {
                                        activateMaxLoss(productId, value);
                                      }
                                    }}
                                    disabled={
                                      !maxLossInput[productId] ||
                                      parseFloat(maxLossInput[productId]) <= 0
                                    }
                                  >
                                    <WarningIcon fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                              </Box>
                            )}
                          </TableCell>
                          <TableCell align="center">
                            <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'center' }}>
                              <Tooltip title="Buy">
                                <IconButton
                                  size="small"
                                  color="success"
                                  onClick={() => handleOpenTrade(pos, 'buy')}
                                >
                                  <BuyIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                              <Tooltip title="Sell">
                                <IconButton
                                  size="small"
                                  color="error"
                                  onClick={() => handleOpenTrade(pos, 'sell')}
                                >
                                  <SellIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                              <Tooltip title="Close Position">
                                <IconButton size="small" onClick={() => handleClosePosition(pos)}>
                                  <CloseIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            </Box>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>

              {/* Payoff Graph */}
              <Box sx={{ mt: 2 }}>
                <FuturesPayoffGraph positions={positions} />
              </Box>
            </>
          )}

          {/* Pending Orders */}
          {!loading && orders.length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" sx={{ mb: 1, color: 'warning.main' }}>
                Pending Futures Orders ({orders.length})
              </Typography>
              <TableContainer
                component={Paper}
                sx={{ bgcolor: 'background.paper', borderRadius: 1 }}
              >
                <Table size="small">
                  <TableHead>
                    <TableRow sx={{ bgcolor: 'rgba(245, 158, 11, 0.1)' }}>
                      <TableCell sx={{ fontWeight: 'bold' }}>Symbol</TableCell>
                      <TableCell align="center" sx={{ fontWeight: 'bold' }}>
                        Side
                      </TableCell>
                      <TableCell align="right" sx={{ fontWeight: 'bold' }}>
                        Size
                      </TableCell>
                      <TableCell align="right" sx={{ fontWeight: 'bold' }}>
                        Price
                      </TableCell>
                      <TableCell align="center" sx={{ fontWeight: 'bold' }}>
                        Type
                      </TableCell>
                      <TableCell align="center" sx={{ fontWeight: 'bold' }}>
                        Status
                      </TableCell>
                      <TableCell align="right" sx={{ fontWeight: 'bold' }}>
                        Date & Time
                      </TableCell>
                      <TableCell align="center" sx={{ fontWeight: 'bold' }}>
                        Actions
                      </TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {orders.map((order) => (
                      <TableRow key={order.id} sx={{ '&:hover': { bgcolor: 'action.hover' } }}>
                        <TableCell>
                          <Typography
                            variant="body2"
                            sx={{ fontFamily: 'monospace', fontWeight: 500 }}
                          >
                            {order.symbol}
                          </Typography>
                        </TableCell>
                        <TableCell align="center">
                          <Chip
                            label={order.side?.toUpperCase()}
                            size="small"
                            color={order.side === 'buy' ? 'success' : 'error'}
                            sx={{ fontWeight: 'bold', minWidth: 50 }}
                          />
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2" sx={{ fontWeight: 500 }}>
                            {order.unfilled_size || order.size}
                          </Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                            {formatPrice(order.price)}
                          </Typography>
                        </TableCell>
                        <TableCell align="center">
                          <Chip
                            label={order.order_type?.replace('_', ' ') || 'limit'}
                            size="small"
                            variant="outlined"
                            sx={{ fontSize: '0.7rem' }}
                          />
                        </TableCell>
                        <TableCell align="center">
                          <Chip
                            label={order.state}
                            size="small"
                            color={order.state === 'open' ? 'warning' : 'default'}
                            sx={{ fontSize: '0.7rem' }}
                          />
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="caption" color="text.secondary">
                            {order.created_at
                              ? new Date(order.created_at).toLocaleString()
                              : '-'}
                          </Typography>
                        </TableCell>
                        <TableCell align="center">
                          <Tooltip title="Cancel Order">
                            <IconButton
                              size="small"
                              color="error"
                              onClick={() => handleCancelFuturesOrder(order)}
                            >
                              <CloseIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>
          )}

          {/* No data message */}
          {!loading && positions.length === 0 && orders.length === 0 && (
            <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 2 }}>
              No futures positions or orders
            </Typography>
          )}
        </Box>
      </Collapse>

      {/* Trade Dialog */}
      <FuturesTradeDialog
        open={tradeDialog.open}
        onClose={handleCloseTrade}
        position={tradeDialog.position}
        side={tradeDialog.side}
      />

      {/* Close All Confirmation Dialog */}
      <Dialog open={closeAllDialog} onClose={() => setCloseAllDialog(false)}>
        <DialogTitle>Close All Futures Positions?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            This will close all {positions.length} futures position(s) at market price. This action
            cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCloseAllDialog(false)}>Cancel</Button>
          <Button onClick={handleCloseAll} color="error" variant="contained">
            Close All Positions
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default FuturesPanel;
