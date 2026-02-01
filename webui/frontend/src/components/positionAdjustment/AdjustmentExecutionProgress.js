/**
 * Adjustment Execution Progress
 * =============================
 * Real-time display of order execution status.
 * 
 * Features:
 * - List of orders with status indicators
 * - ✓ Filled / ⏳ Pending / ❌ Failed status
 * - Fill price display
 * - Overall progress bar
 * - Cancel button to stop remaining orders
 * 
 * Created: January 31, 2026
 */

import React from 'react';
import {
  Box,
  Paper,
  Typography,
  LinearProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Button,
  Chip,
  Alert,
  CircularProgress,
} from '@mui/material';
import {
  CheckCircle as FilledIcon,
  HourglassEmpty as PendingIcon,
  Error as FailedIcon,
  Cancel as CancelIcon,
  PlayArrow as RunningIcon,
} from '@mui/icons-material';

// Status colors
const STATUS_COLORS = {
  filled: '#4caf50',
  pending: '#ff9800',
  failed: '#f44336',
  placing: '#2196f3',
};

/**
 * Get status icon
 */
const getStatusIcon = (status) => {
  switch (status) {
    case 'filled':
      return <FilledIcon sx={{ color: STATUS_COLORS.filled }} />;
    case 'pending':
      return <PendingIcon sx={{ color: STATUS_COLORS.pending }} />;
    case 'failed':
      return <FailedIcon sx={{ color: STATUS_COLORS.failed }} />;
    case 'placing':
      return <CircularProgress size={20} sx={{ color: STATUS_COLORS.placing }} />;
    default:
      return <PendingIcon sx={{ color: 'text.secondary' }} />;
  }
};

/**
 * Get status label
 */
const getStatusLabel = (status) => {
  switch (status) {
    case 'filled': return 'Filled';
    case 'pending': return 'Pending';
    case 'failed': return 'Failed';
    case 'placing': return 'Placing...';
    default: return 'Waiting';
  }
};

/**
 * AdjustmentExecutionProgress Component
 */
export default function AdjustmentExecutionProgress({
  orders = [],
  progress = {},
  currentRound = 0,
  totalRounds = 1,
  error = null,
  onCancel,
  isRunning = false,
  isComplete = false,
}) {
  // Calculate overall progress
  const filledCount = Object.values(progress).filter(p => p.filled).length;
  const totalOrders = orders.length;
  const progressPercent = totalOrders > 0 ? (filledCount / totalOrders) * 100 : 0;

  // Calculate round progress
  const roundProgress = totalRounds > 0 ? (currentRound / totalRounds) * 100 : 0;

  return (
    <Box>
      {/* Header */}
      <Box sx={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        mb: 2,
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {isRunning && (
            <CircularProgress size={20} />
          )}
          <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
            {isComplete ? 'Execution Complete' : isRunning ? 'Executing Orders...' : 'Execution Progress'}
          </Typography>
        </Box>

        {totalRounds > 1 && (
          <Chip
            label={`Round ${currentRound}/${totalRounds}`}
            size="small"
            color="primary"
            variant="outlined"
          />
        )}
      </Box>

      {/* Error display */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {/* Overall progress */}
      <Box sx={{ mb: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
          <Typography variant="caption" color="text.secondary">
            Orders: {filledCount} / {totalOrders} filled
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {Math.round(progressPercent)}%
          </Typography>
        </Box>
        <LinearProgress
          variant="determinate"
          value={progressPercent}
          sx={{
            height: 8,
            borderRadius: 4,
            backgroundColor: 'rgba(255,255,255,0.1)',
            '& .MuiLinearProgress-bar': {
              backgroundColor: isComplete ? '#4caf50' : '#2196f3',
              borderRadius: 4,
            },
          }}
        />
      </Box>

      {/* Round progress (if multiple rounds) */}
      {totalRounds > 1 && (
        <Box sx={{ mb: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
            <Typography variant="caption" color="text.secondary">
              Rounds Progress
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {Math.round(roundProgress)}%
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={roundProgress}
            sx={{
              height: 6,
              borderRadius: 3,
              backgroundColor: 'rgba(255,255,255,0.1)',
              '& .MuiLinearProgress-bar': {
                backgroundColor: '#9c27b0',
                borderRadius: 3,
              },
            }}
          />
        </Box>
      )}

      {/* Orders list */}
      <Paper sx={{ 
        backgroundColor: 'rgba(255,255,255,0.02)',
        maxHeight: 300,
        overflow: 'auto',
      }}>
        <List dense>
          {orders.map((order, index) => {
            const orderProgress = progress[order.symbol] || {};
            const status = orderProgress.status || 'waiting';
            const fillPrice = orderProgress.fillPrice;

            return (
              <ListItem
                key={`${order.symbol}-${index}`}
                sx={{
                  borderBottom: '1px solid rgba(255,255,255,0.05)',
                  '&:last-child': { borderBottom: 'none' },
                }}
              >
                <ListItemIcon sx={{ minWidth: 40 }}>
                  {getStatusIcon(status)}
                </ListItemIcon>
                
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
                        {order.symbol}
                      </Typography>
                      <Chip
                        label={order.side.toUpperCase()}
                        size="small"
                        sx={{
                          height: 18,
                          fontSize: '0.65rem',
                          backgroundColor: order.side === 'buy' 
                            ? 'rgba(76, 175, 80, 0.2)' 
                            : 'rgba(244, 67, 54, 0.2)',
                          color: order.side === 'buy' ? '#4caf50' : '#f44336',
                        }}
                      />
                      <Typography variant="caption" color="text.secondary">
                        × {order.size || order.quantity}
                      </Typography>
                    </Box>
                  }
                  secondary={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                      <Chip
                        label={getStatusLabel(status)}
                        size="small"
                        sx={{
                          height: 16,
                          fontSize: '0.6rem',
                          backgroundColor: `${STATUS_COLORS[status] || 'grey'}20`,
                          color: STATUS_COLORS[status] || 'grey',
                        }}
                      />
                      {fillPrice && (
                        <Typography variant="caption" color="text.secondary">
                          @ ${fillPrice.toFixed(2)}
                        </Typography>
                      )}
                      {orderProgress.error && (
                        <Typography variant="caption" color="error">
                          {orderProgress.error}
                        </Typography>
                      )}
                    </Box>
                  }
                />
              </ListItem>
            );
          })}
        </List>
      </Paper>

      {/* Cancel button */}
      {isRunning && onCancel && (
        <Box sx={{ mt: 2, textAlign: 'center' }}>
          <Button
            variant="outlined"
            color="error"
            startIcon={<CancelIcon />}
            onClick={onCancel}
          >
            Stop Execution
          </Button>
          <Typography variant="caption" display="block" sx={{ mt: 1, color: 'text.secondary' }}>
            Already placed orders will not be cancelled
          </Typography>
        </Box>
      )}

      {/* Success message */}
      {isComplete && !error && (
        <Alert severity="success" sx={{ mt: 2 }}>
          <Typography variant="body2">
            ✅ All {totalOrders} orders executed successfully!
            {totalRounds > 1 && ` (${totalRounds} rounds)`}
          </Typography>
        </Alert>
      )}
    </Box>
  );
}
