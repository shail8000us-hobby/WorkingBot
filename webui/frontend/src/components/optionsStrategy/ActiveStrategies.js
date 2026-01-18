/**
 * Active Strategies List
 * ======================
 * Display and manage active/pending strategies.
 *
 * Created: January 5, 2026
 */

import React from 'react';
import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  Chip,
  IconButton,
  Button,
  Tooltip,
  Stack,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Visibility as ViewIcon,
  PlayArrow as ExecuteIcon,
  Close as CloseIcon,
  Delete as DeleteIcon,
  TrendingUp as ProfitIcon,
  TrendingDown as LossIcon,
} from '@mui/icons-material';

// Status chip colors
const STATUS_CONFIG = {
  pending: { color: 'default', label: 'Pending' },
  configured: { color: 'info', label: 'Configured' },
  executing: { color: 'warning', label: 'Executing' },
  active: { color: 'success', label: 'Active' },
  partial: { color: 'warning', label: 'Partial' },
  closing: { color: 'warning', label: 'Closing' },
  closed: { color: 'default', label: 'Closed' },
  failed: { color: 'error', label: 'Failed' },
};

// Strategy type icons
const TYPE_ICONS = {
  straddle: '🎯',
  strangle: '🔀',
  iron_condor: '🦅',
  iron_butterfly: '🦋',
  call_spread: '📈',
  put_spread: '📉',
  custom: '⚙️',
};

// Format currency
const formatCurrency = (value) => {
  if (value === null || value === undefined || value === 0) return '-';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(value);
};

// Format date
const formatDate = (isoString) => {
  if (!isoString) return '-';
  return new Date(isoString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

export default function ActiveStrategies({
  strategies,
  onRefresh,
  onClose,
  onDelete,
  onView,
  onExecute,
  loading,
}) {
  if (!strategies || strategies.length === 0) {
    return (
      <Paper sx={{ p: 4, textAlign: 'center' }}>
        <Typography variant="h6" color="text.secondary" gutterBottom>
          No Active Strategies
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Create a new strategy using the Build Strategy tab
        </Typography>
        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={onRefresh}
          disabled={loading}
        >
          Refresh
        </Button>
      </Paper>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">{strategies.length} Strategies</Typography>
        <Button
          variant="outlined"
          size="small"
          startIcon={<RefreshIcon />}
          onClick={onRefresh}
          disabled={loading}
        >
          Refresh
        </Button>
      </Box>

      {/* Table */}
      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Strategy</TableCell>
              <TableCell>Underlying</TableCell>
              <TableCell>Expiry</TableCell>
              <TableCell align="center">Legs</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Cost</TableCell>
              <TableCell align="right">P&L</TableCell>
              <TableCell align="center">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {strategies.map((strategy) => {
              const statusConfig = STATUS_CONFIG[strategy.status] || STATUS_CONFIG.pending;
              const typeIcon = TYPE_ICONS[strategy.strategy_type] || '📊';
              const pnl = strategy.current_pnl || 0;
              const isActive = strategy.status === 'active' || strategy.status === 'partial';
              const canExecute = strategy.status === 'pending' || strategy.status === 'configured';
              const canDelete = strategy.status === 'pending' || strategy.status === 'configured';

              return (
                <TableRow key={strategy.id} hover sx={{ '&:hover': { bgcolor: 'action.hover' } }}>
                  {/* Strategy Name */}
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography variant="body1">{typeIcon}</Typography>
                      <Box>
                        <Typography variant="body2" fontWeight="medium">
                          {strategy.name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {strategy.strategy_type.replace('_', ' ')}
                        </Typography>
                      </Box>
                    </Box>
                  </TableCell>

                  {/* Underlying */}
                  <TableCell>
                    <Chip
                      label={strategy.underlying}
                      size="small"
                      color={strategy.underlying === 'BTC' ? 'warning' : 'primary'}
                      variant="outlined"
                    />
                  </TableCell>

                  {/* Expiry */}
                  <TableCell>
                    <Typography variant="body2">{strategy.expiry}</Typography>
                  </TableCell>

                  {/* Legs */}
                  <TableCell align="center">
                    <Typography variant="body2">{strategy.legs?.length || 0}</Typography>
                  </TableCell>

                  {/* Status */}
                  <TableCell>
                    <Chip label={statusConfig.label} color={statusConfig.color} size="small" />
                  </TableCell>

                  {/* Cost */}
                  <TableCell align="right">
                    <Typography variant="body2">{formatCurrency(strategy.total_cost)}</Typography>
                  </TableCell>

                  {/* P&L */}
                  <TableCell align="right">
                    <Stack
                      direction="row"
                      alignItems="center"
                      justifyContent="flex-end"
                      spacing={0.5}
                    >
                      {pnl !== 0 &&
                        (pnl > 0 ? (
                          <ProfitIcon fontSize="small" color="success" />
                        ) : (
                          <LossIcon fontSize="small" color="error" />
                        ))}
                      <Typography
                        variant="body2"
                        fontWeight="medium"
                        color={pnl > 0 ? 'success.main' : pnl < 0 ? 'error.main' : 'text.secondary'}
                      >
                        {formatCurrency(pnl)}
                      </Typography>
                    </Stack>
                  </TableCell>

                  {/* Actions */}
                  <TableCell align="center">
                    <Stack direction="row" spacing={0.5} justifyContent="center">
                      <Tooltip title="View Details">
                        <IconButton size="small" onClick={() => onView(strategy)}>
                          <ViewIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>

                      {canExecute && onExecute && (
                        <Tooltip title="Execute">
                          <IconButton
                            size="small"
                            color="primary"
                            onClick={() => onExecute(strategy.id)}
                          >
                            <ExecuteIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      )}

                      {isActive && (
                        <Tooltip title="Close Strategy">
                          <IconButton
                            size="small"
                            color="warning"
                            onClick={() => onClose(strategy.id)}
                          >
                            <CloseIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      )}

                      {canDelete && (
                        <Tooltip title="Delete">
                          <IconButton
                            size="small"
                            color="error"
                            onClick={() => onDelete(strategy.id)}
                          >
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      )}
                    </Stack>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}
