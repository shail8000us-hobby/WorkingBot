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
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  TrendingUp,
  TrendingDown,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  ShowChart as FuturesIcon,
} from '@mui/icons-material';
import api from '../../utils/apiShim';

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

  // Manual refresh
  const handleRefresh = async () => {
    setRefreshing(true);
    await Promise.all([fetchPositions(), fetchOrders()]);
    setRefreshing(false);
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
          {/* Summary PnL */}
          {positions.length > 0 && (
            <Chip
              icon={summary.total_unrealized_pnl >= 0 ? <TrendingUp /> : <TrendingDown />}
              label={formatPnL(summary.total_unrealized_pnl).text}
              size="small"
              sx={{
                bgcolor: summary.total_unrealized_pnl >= 0 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
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
            <TableContainer component={Paper} sx={{ bgcolor: 'background.paper', borderRadius: 1 }}>
              <Table size="small">
                <TableHead>
                  <TableRow sx={{ bgcolor: 'rgba(14, 165, 233, 0.1)' }}>
                    <TableCell sx={{ fontWeight: 'bold' }}>Symbol</TableCell>
                    <TableCell align="center" sx={{ fontWeight: 'bold' }}>Side</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 'bold' }}>Size</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 'bold' }}>Entry</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 'bold' }}>Mark</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 'bold' }}>Liq. Price</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 'bold' }}>Unrealized PnL</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 'bold' }}>Margin</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {positions.map((pos) => {
                    const pnl = formatPnL(pos.unrealized_pnl);
                    return (
                      <TableRow
                        key={`${pos.symbol}-${pos.product_id}`}
                        sx={{ '&:hover': { bgcolor: 'action.hover' } }}
                      >
                        <TableCell>
                          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 600 }}>
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
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}

          {/* Pending Orders */}
          {!loading && orders.length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" sx={{ mb: 1, color: 'warning.main' }}>
                Pending Futures Orders ({orders.length})
              </Typography>
              <TableContainer component={Paper} sx={{ bgcolor: 'background.paper', borderRadius: 1 }}>
                <Table size="small">
                  <TableHead>
                    <TableRow sx={{ bgcolor: 'rgba(245, 158, 11, 0.1)' }}>
                      <TableCell sx={{ fontWeight: 'bold' }}>Symbol</TableCell>
                      <TableCell align="center" sx={{ fontWeight: 'bold' }}>Side</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 'bold' }}>Size</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 'bold' }}>Price</TableCell>
                      <TableCell align="center" sx={{ fontWeight: 'bold' }}>Type</TableCell>
                      <TableCell align="center" sx={{ fontWeight: 'bold' }}>Status</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {orders.map((order) => (
                      <TableRow
                        key={order.id}
                        sx={{ '&:hover': { bgcolor: 'action.hover' } }}
                      >
                        <TableCell>
                          <Typography variant="body2" sx={{ fontFamily: 'monospace', fontWeight: 500 }}>
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
    </Box>
  );
};

export default FuturesPanel;
