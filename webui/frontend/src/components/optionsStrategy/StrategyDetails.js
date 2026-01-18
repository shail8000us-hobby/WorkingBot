/**
 * Strategy Details
 * ================
 * Display detailed view of a strategy with legs and actions.
 *
 * Created: January 5, 2026
 */

import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Chip,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Divider,
  Alert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Stack,
} from '@mui/material';
import {
  PlayArrow as ExecuteIcon,
  Close as CloseIcon,
  Delete as DeleteIcon,
  CallMade as BuyIcon,
  CallReceived as SellIcon,
} from '@mui/icons-material';

// Status colors
const STATUS_COLORS = {
  pending: 'default',
  configured: 'info',
  submitted: 'warning',
  filled: 'success',
  failed: 'error',
  active: 'success',
  closed: 'default',
};

// Format currency
const formatCurrency = (value, digits = 2) => {
  if (value === null || value === undefined) return '-';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
};

function LegRow({ leg, index }) {
  const isBuy = leg.side === 'buy';
  const statusColor = STATUS_COLORS[leg.status] || 'default';

  return (
    <TableRow>
      <TableCell>
        <Chip label={`Leg ${index + 1}`} size="small" variant="outlined" />
      </TableCell>
      <TableCell>
        <Stack direction="row" alignItems="center" spacing={0.5}>
          {isBuy ? (
            <BuyIcon fontSize="small" color="success" />
          ) : (
            <SellIcon fontSize="small" color="error" />
          )}
          <Typography variant="body2" fontWeight="medium">
            {leg.side.toUpperCase()}
          </Typography>
        </Stack>
      </TableCell>
      <TableCell>
        <Chip
          label={leg.option_type.toUpperCase()}
          size="small"
          color={leg.option_type === 'call' ? 'success' : 'error'}
          variant="outlined"
        />
      </TableCell>
      <TableCell align="right">{formatCurrency(leg.strike, 0)}</TableCell>
      <TableCell align="center">{leg.quantity}</TableCell>
      <TableCell>
        <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
          {leg.symbol}
        </Typography>
      </TableCell>
      <TableCell>
        <Chip label={leg.status} size="small" color={statusColor} />
      </TableCell>
      <TableCell align="right">
        {leg.avg_fill_price > 0 ? formatCurrency(leg.avg_fill_price) : '-'}
      </TableCell>
    </TableRow>
  );
}

export default function StrategyDetails({
  strategy,
  open,
  onClose,
  onExecute,
  onCloseStrategy,
  onDelete,
  isDialog = false,
  loading,
}) {
  const [showExecuteDialog, setShowExecuteDialog] = useState(false);
  const [executionMode, setExecutionMode] = useState('sequential');
  const [orderType, setOrderType] = useState('limit');

  if (!strategy) return null;

  const canExecute = strategy.status === 'pending' || strategy.status === 'configured';
  const isActive = strategy.status === 'active' || strategy.status === 'partial';
  const canDelete = strategy.status === 'pending' || strategy.status === 'configured';

  const handleExecute = () => {
    if (onExecute) {
      onExecute(strategy.id, { execution_mode: executionMode, order_type: orderType });
    }
    setShowExecuteDialog(false);
  };

  const content = (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          {strategy.name}
        </Typography>
        <Stack direction="row" spacing={1} flexWrap="wrap">
          <Chip label={strategy.strategy_type.replace('_', ' ')} color="primary" size="small" />
          <Chip
            label={strategy.underlying}
            color={strategy.underlying === 'BTC' ? 'warning' : 'secondary'}
            size="small"
            variant="outlined"
          />
          <Chip label={`Exp: ${strategy.expiry}`} size="small" variant="outlined" />
          <Chip
            label={strategy.status}
            color={STATUS_COLORS[strategy.status] || 'default'}
            size="small"
          />
        </Stack>
      </Box>

      {/* Stats Grid */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={6} sm={3}>
          <Paper sx={{ p: 1.5, textAlign: 'center' }} variant="outlined">
            <Typography variant="caption" color="text.secondary">
              Total Cost
            </Typography>
            <Typography variant="h6">{formatCurrency(strategy.total_cost)}</Typography>
          </Paper>
        </Grid>
        <Grid item xs={6} sm={3}>
          <Paper sx={{ p: 1.5, textAlign: 'center' }} variant="outlined">
            <Typography variant="caption" color="text.secondary">
              Current P&L
            </Typography>
            <Typography
              variant="h6"
              color={
                strategy.current_pnl > 0
                  ? 'success.main'
                  : strategy.current_pnl < 0
                    ? 'error.main'
                    : 'text.primary'
              }
            >
              {formatCurrency(strategy.current_pnl)}
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={6} sm={3}>
          <Paper sx={{ p: 1.5, textAlign: 'center' }} variant="outlined">
            <Typography variant="caption" color="text.secondary">
              Max Profit
            </Typography>
            <Typography variant="h6" color="success.main">
              {strategy.max_profit !== null ? formatCurrency(strategy.max_profit) : '∞'}
            </Typography>
          </Paper>
        </Grid>
        <Grid item xs={6} sm={3}>
          <Paper sx={{ p: 1.5, textAlign: 'center' }} variant="outlined">
            <Typography variant="caption" color="text.secondary">
              Max Loss
            </Typography>
            <Typography variant="h6" color="error.main">
              {strategy.max_loss !== null ? formatCurrency(strategy.max_loss) : '∞'}
            </Typography>
          </Paper>
        </Grid>
      </Grid>

      {/* Legs Table */}
      <Typography variant="subtitle2" gutterBottom>
        Strategy Legs ({strategy.legs?.length || 0})
      </Typography>
      <TableContainer component={Paper} variant="outlined" sx={{ mb: 3 }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Leg</TableCell>
              <TableCell>Side</TableCell>
              <TableCell>Type</TableCell>
              <TableCell align="right">Strike</TableCell>
              <TableCell align="center">Qty</TableCell>
              <TableCell>Symbol</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Fill Price</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {strategy.legs?.map((leg, i) => (
              <LegRow key={leg.leg_id || i} leg={leg} index={i} />
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Exit Conditions */}
      {strategy.exit_conditions && Object.keys(strategy.exit_conditions).length > 0 && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" gutterBottom>
            Exit Conditions
          </Typography>
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Grid container spacing={2}>
              {strategy.exit_conditions.profit_target_pct && (
                <Grid item xs={4}>
                  <Typography variant="caption" color="text.secondary">
                    Profit Target
                  </Typography>
                  <Typography variant="body2" color="success.main">
                    +{strategy.exit_conditions.profit_target_pct}%
                  </Typography>
                </Grid>
              )}
              {strategy.exit_conditions.stop_loss_pct && (
                <Grid item xs={4}>
                  <Typography variant="caption" color="text.secondary">
                    Stop Loss
                  </Typography>
                  <Typography variant="body2" color="error.main">
                    {strategy.exit_conditions.stop_loss_pct}%
                  </Typography>
                </Grid>
              )}
              {strategy.exit_conditions.dte_exit && (
                <Grid item xs={4}>
                  <Typography variant="caption" color="text.secondary">
                    DTE Exit
                  </Typography>
                  <Typography variant="body2">{strategy.exit_conditions.dte_exit} days</Typography>
                </Grid>
              )}
            </Grid>
          </Paper>
        </Box>
      )}

      {/* Actions */}
      {!isDialog && (
        <Stack direction="row" spacing={2}>
          {canExecute && (
            <Button
              variant="contained"
              color="primary"
              startIcon={<ExecuteIcon />}
              onClick={() => setShowExecuteDialog(true)}
              disabled={loading}
            >
              Execute Strategy
            </Button>
          )}
          {isActive && (
            <Button
              variant="contained"
              color="warning"
              startIcon={<CloseIcon />}
              onClick={() => onCloseStrategy && onCloseStrategy(strategy.id)}
              disabled={loading}
            >
              Close Strategy
            </Button>
          )}
          {canDelete && (
            <Button
              variant="outlined"
              color="error"
              startIcon={<DeleteIcon />}
              onClick={() => onDelete && onDelete(strategy.id)}
              disabled={loading}
            >
              Delete
            </Button>
          )}
        </Stack>
      )}

      {/* Execute Dialog */}
      <Dialog open={showExecuteDialog} onClose={() => setShowExecuteDialog(false)}>
        <DialogTitle>Execute Strategy</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            This will place real orders on the exchange!
          </Alert>

          <Grid container spacing={2} sx={{ mt: 1 }}>
            <Grid item xs={6}>
              <FormControl fullWidth size="small">
                <InputLabel>Execution Mode</InputLabel>
                <Select
                  value={executionMode}
                  label="Execution Mode"
                  onChange={(e) => setExecutionMode(e.target.value)}
                >
                  <MenuItem value="sequential">Sequential (Safer)</MenuItem>
                  <MenuItem value="parallel">Parallel (Faster)</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={6}>
              <FormControl fullWidth size="small">
                <InputLabel>Order Type</InputLabel>
                <Select
                  value={orderType}
                  label="Order Type"
                  onChange={(e) => setOrderType(e.target.value)}
                >
                  <MenuItem value="limit">Limit</MenuItem>
                  <MenuItem value="market">Market</MenuItem>
                </Select>
              </FormControl>
            </Grid>
          </Grid>

          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            <strong>Sequential:</strong> Executes legs one at a time. If any leg fails, previous
            legs are rolled back.
            <br />
            <strong>Parallel:</strong> Executes all legs simultaneously. Faster but may result in
            partial fills.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowExecuteDialog(false)}>Cancel</Button>
          <Button
            variant="contained"
            color="primary"
            onClick={handleExecute}
            startIcon={<ExecuteIcon />}
          >
            Execute
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );

  // Render as dialog or inline
  if (isDialog) {
    return (
      <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
        <DialogTitle>Strategy Details</DialogTitle>
        <DialogContent>{content}</DialogContent>
        <DialogActions>
          {canExecute && onExecute && (
            <Button
              color="primary"
              startIcon={<ExecuteIcon />}
              onClick={() => setShowExecuteDialog(true)}
            >
              Execute
            </Button>
          )}
          {isActive && onCloseStrategy && (
            <Button
              color="warning"
              startIcon={<CloseIcon />}
              onClick={() => onCloseStrategy(strategy.id)}
            >
              Close Strategy
            </Button>
          )}
          {canDelete && onDelete && (
            <Button color="error" startIcon={<DeleteIcon />} onClick={() => onDelete(strategy.id)}>
              Delete
            </Button>
          )}
          <Button onClick={onClose}>Close</Button>
        </DialogActions>
      </Dialog>
    );
  }

  return content;
}
