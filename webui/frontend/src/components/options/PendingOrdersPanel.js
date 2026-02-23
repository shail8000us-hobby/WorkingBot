/**
 * PendingOrdersPanel — Extracted from OptionsPanel.js (Phase 4.1)
 * 
 * Shows pending/open orders from Delta Exchange with cancel capability.
 * Collapsible section with "Live" badge when orders are present.
 */
import React, { useState, useCallback } from 'react';
import {
  Box,
  Typography,
  Chip,
  IconButton,
  Tooltip,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Collapse,
} from '@mui/material';
import {
  Close as CloseIcon,
  Timer as TimerIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
} from '@mui/icons-material';

const PendingOrdersPanel = React.memo(function PendingOrdersPanel({
  pendingOrders = [],
  pendingOrdersError,
  onCancelOrder,
}) {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      const saved = localStorage.getItem('options_pending_orders_collapsed');
      return saved ? JSON.parse(saved) : false;
    } catch {
      return false;
    }
  });

  const toggleCollapsed = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem('options_pending_orders_collapsed', JSON.stringify(next));
      return next;
    });
  }, []);

  if (pendingOrdersError) return null;

  return (
    <Box
      sx={{
        mb: 2,
        p: 2,
        borderRadius: 1,
        border: '1px solid',
        borderColor: pendingOrders.length > 0 ? 'warning.main' : 'divider',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
        <TimerIcon sx={{ color: pendingOrders.length > 0 ? 'warning.main' : 'text.secondary' }} />
        <Typography variant="subtitle1" sx={{ fontWeight: 'bold', color: 'text.primary' }}>
          ⏳ Pending Orders ({pendingOrders.length})
        </Typography>
        {pendingOrders.length > 0 && (
          <Chip
            label="Live"
            size="small"
            color="error"
            sx={{ animation: 'pulse 1.5s infinite' }}
          />
        )}
        <IconButton
          size="small"
          onClick={toggleCollapsed}
          sx={{ ml: 'auto', color: 'text.secondary' }}
        >
          {collapsed ? <ExpandMoreIcon /> : <ExpandLessIcon />}
        </IconButton>
      </Box>
      <Collapse in={!collapsed}>
        {pendingOrders.length > 0 ? (
          <TableContainer
            component={Paper}
            sx={{ maxHeight: 200, bgcolor: 'background.paper' }}
          >
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell>Symbol</TableCell>
                  <TableCell align="center">Side</TableCell>
                  <TableCell align="right">Size</TableCell>
                  <TableCell align="right">Price</TableCell>
                  <TableCell align="center">Type</TableCell>
                  <TableCell align="center">Status</TableCell>
                  <TableCell align="right">Date & Time</TableCell>
                  <TableCell align="center">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {pendingOrders.map((order) => (
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
                        ${parseFloat(order.price || 0).toFixed(2)}
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
                        label={order.state || 'open'}
                        size="small"
                        color="warning"
                        sx={{ fontWeight: 'bold' }}
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
                          onClick={() => onCancelOrder(order)}
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
        ) : (
          <Paper sx={{ p: 2, textAlign: 'center', bgcolor: 'action.hover' }}>
            <Typography variant="body2" color="text.secondary">
              No pending orders
            </Typography>
          </Paper>
        )}
      </Collapse>
    </Box>
  );
});

export default PendingOrdersPanel;
