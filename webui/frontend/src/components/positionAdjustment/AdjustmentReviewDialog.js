/**
 * Adjustment Review Dialog
 * ========================
 * Final confirmation dialog before executing trades.
 * 
 * Features:
 * - Summary of all proposed trades
 * - Before/After metrics comparison
 * - Order execution settings (order type, rounds)
 * - Execute button with confirmation
 * 
 * Created: January 31, 2026
 */

import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Box,
  Typography,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Alert,
  Divider,
  CircularProgress,
  IconButton,
} from '@mui/material';
import {
  Close as CloseIcon,
  PlayArrow as ExecuteIcon,
  Warning as WarningIcon,
  CheckCircle as CheckIcon,
} from '@mui/icons-material';
import { getContractMultiplier } from '../../utils/constants';

// Styling
const styles = {
  buyChip: {
    backgroundColor: '#2e7d32',
    color: '#fff',
    fontWeight: 'bold',
    fontSize: '0.7rem',
  },
  sellChip: {
    backgroundColor: '#c62828',
    color: '#fff',
    fontWeight: 'bold',
    fontSize: '0.7rem',
  },
  callChip: {
    backgroundColor: 'rgba(76, 175, 80, 0.2)',
    color: '#4caf50',
  },
  putChip: {
    backgroundColor: 'rgba(244, 67, 54, 0.2)',
    color: '#f44336',
  },
};

/**
 * AdjustmentReviewDialog Component
 */
export default function AdjustmentReviewDialog({
  open,
  onClose,
  trades = [],
  formattedMetrics,
  onExecute,
  executing = false,
}) {
  // State for execution options
  const [orderType, setOrderType] = useState('maker_first');
  const [loopRounds, setLoopRounds] = useState(1);
  const [confirmed, setConfirmed] = useState(false);

  // Calculate totals
  const calculateTotals = () => {
    let totalPremium = 0;
    let buyCount = 0;
    let sellCount = 0;

    trades.forEach((trade) => {
      const premium = Math.abs(trade.premium || trade.ltp || 0);
      const qty = trade.quantity || 1;
      const multiplier = getContractMultiplier(trade.symbol);
      const isLong = trade.side === 'buy';

      if (isLong) {
        buyCount++;
        totalPremium -= premium * qty * multiplier;
      } else {
        sellCount++;
        totalPremium += premium * qty * multiplier;
      }
    });

    return {
      totalPremium,
      buyCount,
      sellCount,
      isCredit: totalPremium >= 0,
    };
  };

  const totals = calculateTotals();

  // Handle execute
  const handleExecute = () => {
    if (!confirmed) {
      setConfirmed(true);
      return;
    }

    onExecute?.({
      trades,
      orderType,
      loopRounds,
    });
  };

  // Reset on close
  const handleClose = () => {
    setConfirmed(false);
    onClose?.();
  };

  return (
    <Dialog 
      open={open} 
      onClose={executing ? undefined : handleClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          backgroundColor: '#1a1a2e',
          borderRadius: 2,
        },
      }}
    >
      <DialogTitle sx={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        borderBottom: '1px solid rgba(255,255,255,0.1)',
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="h6">
            Review & Execute
          </Typography>
          <Chip 
            label={`${trades.length} trade${trades.length !== 1 ? 's' : ''}`}
            size="small"
            color="primary"
          />
        </Box>
        
        {!executing && (
          <IconButton onClick={handleClose} size="small">
            <CloseIcon />
          </IconButton>
        )}
      </DialogTitle>

      <DialogContent sx={{ py: 3 }}>
        {/* Warning for high-risk adjustments */}
        {formattedMetrics?.raw?.change?.popChange < -0.1 && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            <Typography variant="body2">
              This adjustment significantly decreases your Probability of Profit. Review carefully.
            </Typography>
          </Alert>
        )}

        {/* Trades Table */}
        <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>
          Trades to Execute
        </Typography>
        
        <TableContainer 
          component={Paper} 
          sx={{ 
            mb: 3,
            backgroundColor: 'rgba(255,255,255,0.02)',
            maxHeight: 250,
          }}
        >
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 'bold' }}>Symbol</TableCell>
                <TableCell align="center" sx={{ fontWeight: 'bold' }}>Type</TableCell>
                <TableCell align="center" sx={{ fontWeight: 'bold' }}>Side</TableCell>
                <TableCell align="center" sx={{ fontWeight: 'bold' }}>Qty</TableCell>
                <TableCell align="right" sx={{ fontWeight: 'bold' }}>Premium</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {trades.map((trade, index) => {
                const premium = Math.abs(trade.premium || trade.ltp || 0);
                const qty = trade.quantity || 1;
                const totalPremium = premium * qty * getContractMultiplier(trade.symbol);
                const isCredit = trade.side === 'sell';

                return (
                  <TableRow key={index} hover>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
                        {trade.symbol}
                      </Typography>
                    </TableCell>
                    <TableCell align="center">
                      <Chip
                        label={trade.type === 'call' ? 'CALL' : 'PUT'}
                        size="small"
                        sx={trade.type === 'call' ? styles.callChip : styles.putChip}
                      />
                    </TableCell>
                    <TableCell align="center">
                      <Chip
                        label={trade.side === 'buy' ? 'BUY' : 'SELL'}
                        size="small"
                        sx={trade.side === 'buy' ? styles.buyChip : styles.sellChip}
                      />
                    </TableCell>
                    <TableCell align="center">
                      <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                        {qty}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Typography
                        variant="body2"
                        sx={{ 
                          fontWeight: 'bold',
                          color: isCredit ? '#4caf50' : '#f44336',
                        }}
                      >
                        {isCredit ? '+' : '-'}${totalPremium.toFixed(2)}
                      </Typography>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>

        {/* Net Premium Summary */}
        <Box sx={{ 
          p: 2, 
          mb: 3,
          backgroundColor: totals.isCredit 
            ? 'rgba(76, 175, 80, 0.1)' 
            : 'rgba(244, 67, 54, 0.1)',
          borderRadius: 1,
          borderLeft: `3px solid ${totals.isCredit ? '#4caf50' : '#f44336'}`,
        }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="body2">
              Net Premium ({totals.buyCount} buy, {totals.sellCount} sell):
            </Typography>
            <Typography
              variant="h6"
              sx={{ 
                fontWeight: 'bold',
                color: totals.isCredit ? '#4caf50' : '#f44336',
              }}
            >
              {totals.isCredit ? '+' : ''}{totals.totalPremium.toFixed(2)} USD
              <Typography component="span" variant="body2" sx={{ ml: 1, color: 'text.secondary' }}>
                ({totals.isCredit ? 'Credit' : 'Debit'})
              </Typography>
            </Typography>
          </Box>
        </Box>

        <Divider sx={{ my: 2 }} />

        {/* Execution Options */}
        <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 2 }}>
          Execution Options
        </Typography>
        
        <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel>Order Type</InputLabel>
            <Select
              value={orderType}
              onChange={(e) => setOrderType(e.target.value)}
              label="Order Type"
              disabled={executing}
            >
              <MenuItem value="maker_first">
                Smart Limit (Recommended)
              </MenuItem>
              <MenuItem value="ssr">
                SSR Order (Best Price)
              </MenuItem>
              <MenuItem value="market_only">
                Market (Instant Fill)
              </MenuItem>
              <MenuItem value="maker_only">
                Limit Only (May Not Fill)
              </MenuItem>
            </Select>
          </FormControl>

          <TextField
            size="small"
            type="number"
            label="Loop Rounds"
            value={loopRounds}
            onChange={(e) => setLoopRounds(Math.max(1, parseInt(e.target.value) || 1))}
            inputProps={{ min: 1, max: 100 }}
            sx={{ width: 120 }}
            disabled={executing}
            helperText="Orders per round"
          />
        </Box>

        {/* Info about autoloop */}
        <Alert severity="info" sx={{ mb: 2 }}>
          <Typography variant="body2">
            Using <strong>autoloop</strong>: Orders execute one at a time to avoid slippage in low liquidity.
            {loopRounds > 1 && ` Will run ${loopRounds} round(s) for each order.`}
          </Typography>
        </Alert>

        {/* Metrics Summary (compact) */}
        {formattedMetrics && (
          <Box sx={{ 
            p: 2, 
            backgroundColor: 'rgba(255,255,255,0.03)',
            borderRadius: 1,
          }}>
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              After Execution
            </Typography>
            <Box sx={{ display: 'flex', gap: 3, mt: 1 }}>
              <Box>
                <Typography variant="caption" color="text.secondary">Max Profit</Typography>
                <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                  {formattedMetrics.combined?.maxProfit}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">Max Loss</Typography>
                <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                  {formattedMetrics.combined?.maxLoss}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">PoP</Typography>
                <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                  {formattedMetrics.combined?.pop}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" color="text.secondary">Breakeven</Typography>
                <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                  {formattedMetrics.combined?.breakevens?.join(', ') || '-'}
                </Typography>
              </Box>
            </Box>
          </Box>
        )}
      </DialogContent>

      <DialogActions sx={{ 
        px: 3, 
        py: 2,
        borderTop: '1px solid rgba(255,255,255,0.1)',
        justifyContent: 'space-between',
      }}>
        <Button
          onClick={handleClose}
          disabled={executing}
          color="inherit"
        >
          Cancel
        </Button>

        <Box sx={{ display: 'flex', gap: 1 }}>
          {!confirmed ? (
            <Button
              variant="contained"
              color="primary"
              onClick={handleExecute}
              disabled={executing || trades.length === 0}
              startIcon={<CheckIcon />}
            >
              Confirm Execution
            </Button>
          ) : (
            <Button
              variant="contained"
              color="success"
              onClick={handleExecute}
              disabled={executing || trades.length === 0}
              startIcon={executing ? <CircularProgress size={20} color="inherit" /> : <ExecuteIcon />}
              sx={{ minWidth: 150 }}
            >
              {executing ? 'Executing...' : 'Execute Now'}
            </Button>
          )}
        </Box>
      </DialogActions>
    </Dialog>
  );
}
