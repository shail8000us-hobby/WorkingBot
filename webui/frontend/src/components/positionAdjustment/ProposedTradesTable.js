/**
 * Proposed Trades Table
 * =====================
 * Displays the list of user-selected trades to be executed.
 * 
 * Features:
 * - Strike, Type, Side, Qty, Premium display
 * - Inline quantity editing
 * - Delete button per row
 * - Net premium calculation (credit/debit)
 * 
 * Created: January 31, 2026
 */

import React, { useMemo } from 'react';
import {
  Box,
  Paper,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  TextField,
  Chip,
  Tooltip,
  Button,
} from '@mui/material';
import {
  Delete as DeleteIcon,
  Add as AddIcon,
  Remove as RemoveIcon,
  Clear as ClearIcon,
} from '@mui/icons-material';
import { getContractMultiplier } from '../../utils/constants';

// Styling
const styles = {
  buyChip: {
    backgroundColor: '#2e7d32',
    color: '#fff',
    fontWeight: 'bold',
    fontSize: '0.7rem',
    height: 22,
  },
  sellChip: {
    backgroundColor: '#c62828',
    color: '#fff',
    fontWeight: 'bold',
    fontSize: '0.7rem',
    height: 22,
  },
  callChip: {
    backgroundColor: 'rgba(76, 175, 80, 0.2)',
    color: '#4caf50',
    fontWeight: 'bold',
    fontSize: '0.7rem',
    height: 22,
  },
  putChip: {
    backgroundColor: 'rgba(244, 67, 54, 0.2)',
    color: '#f44336',
    fontWeight: 'bold',
    fontSize: '0.7rem',
    height: 22,
  },
  qtyInput: {
    width: '70px',
    '& input': {
      padding: '4px 8px',
      textAlign: 'center',
      fontSize: '0.875rem',
    },
  },
  premiumCredit: {
    color: '#4caf50',
    fontWeight: 'bold',
  },
  premiumDebit: {
    color: '#f44336',
    fontWeight: 'bold',
  },
};

/**
 * ProposedTradesTable Component
 */
export default function ProposedTradesTable({
  trades = [],
  onRemoveTrade,
  onUpdateTradeQty,
  onClearAll,
  compact = false,
}) {
  // Calculate net premium
  const netPremium = useMemo(() => {
    return trades.reduce((total, trade) => {
      const premium = Math.abs(trade.premium || trade.ltp || 0);
      const qty = trade.quantity || 1;
      const contractMultiplier = getContractMultiplier(trade.symbol);
      const isLong = trade.side === 'buy';
      
      // Long = pay premium (negative), Short = receive premium (positive)
      const direction = isLong ? -1 : 1;
      return total + premium * qty * contractMultiplier * direction;
    }, 0);
  }, [trades]);

  // Handle quantity increment/decrement
  const handleQtyAdjust = (trade, delta) => {
    const newQty = Math.max(1, (trade.quantity || 1) + delta);
    onUpdateTradeQty?.(trade.strike, trade.type, trade.side, newQty);
  };

  // Handle quantity direct change
  const handleQtyChange = (trade, newQty) => {
    const qty = Math.max(1, parseInt(newQty) || 1);
    onUpdateTradeQty?.(trade.strike, trade.type, trade.side, qty);
  };

  // Empty state
  if (trades.length === 0) {
    return (
      <Box sx={{ 
        p: 3, 
        textAlign: 'center', 
        border: '1px dashed rgba(255,255,255,0.2)',
        borderRadius: 2,
        backgroundColor: 'rgba(255,255,255,0.02)',
      }}>
        <Typography variant="body2" color="text.secondary">
          No trades selected. Click B/S buttons in the chain to add trades.
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box sx={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between',
        mb: 1,
      }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
          Proposed Trades ({trades.length})
        </Typography>
        
        {trades.length > 0 && (
          <Button
            size="small"
            color="error"
            startIcon={<ClearIcon />}
            onClick={onClearAll}
            sx={{ textTransform: 'none' }}
          >
            Clear All
          </Button>
        )}
      </Box>

      {/* Table */}
      <TableContainer 
        component={Paper} 
        sx={{ 
          backgroundColor: 'rgba(255,255,255,0.02)',
          maxHeight: compact ? 200 : 300,
        }}
      >
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell sx={{ fontWeight: 'bold' }}>Strike</TableCell>
              <TableCell align="center" sx={{ fontWeight: 'bold' }}>Type</TableCell>
              <TableCell align="center" sx={{ fontWeight: 'bold' }}>Side</TableCell>
              <TableCell align="center" sx={{ fontWeight: 'bold' }}>Qty</TableCell>
              <TableCell align="right" sx={{ fontWeight: 'bold' }}>Premium</TableCell>
              <TableCell align="center" sx={{ fontWeight: 'bold', width: 50 }}></TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {trades.map((trade, index) => {
              const premium = Math.abs(trade.premium || trade.ltp || 0);
              const qty = trade.quantity || 1;
              const totalPremium = premium * qty * getContractMultiplier(trade.symbol);
              const isCredit = trade.side === 'sell';

              return (
                <TableRow key={`${trade.symbol}-${trade.side}-${index}`} hover>
                  {/* Strike */}
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                      ${trade.strike?.toLocaleString()}
                    </Typography>
                  </TableCell>

                  {/* Type (Call/Put) */}
                  <TableCell align="center">
                    <Chip
                      label={trade.type === 'call' ? 'C' : 'P'}
                      size="small"
                      sx={trade.type === 'call' ? styles.callChip : styles.putChip}
                    />
                  </TableCell>

                  {/* Side (Buy/Sell) */}
                  <TableCell align="center">
                    <Chip
                      label={trade.side === 'buy' ? 'BUY' : 'SELL'}
                      size="small"
                      sx={trade.side === 'buy' ? styles.buyChip : styles.sellChip}
                    />
                  </TableCell>

                  {/* Quantity with +/- buttons */}
                  <TableCell align="center">
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
                      <IconButton 
                        size="small" 
                        onClick={() => handleQtyAdjust(trade, -1)}
                        disabled={qty <= 1}
                        sx={{ p: 0.25 }}
                      >
                        <RemoveIcon fontSize="small" />
                      </IconButton>
                      
                      <TextField
                        size="small"
                        type="number"
                        value={qty}
                        onChange={(e) => handleQtyChange(trade, e.target.value)}
                        sx={styles.qtyInput}
                        inputProps={{ min: 1, max: 1000 }}
                      />
                      
                      <IconButton 
                        size="small" 
                        onClick={() => handleQtyAdjust(trade, 1)}
                        sx={{ p: 0.25 }}
                      >
                        <AddIcon fontSize="small" />
                      </IconButton>
                    </Box>
                  </TableCell>

                  {/* Premium */}
                  <TableCell align="right">
                    <Typography
                      variant="body2"
                      sx={isCredit ? styles.premiumCredit : styles.premiumDebit}
                    >
                      {isCredit ? '+' : '-'}${totalPremium.toFixed(2)}
                    </Typography>
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                      ${premium.toFixed(2)} × {qty}
                    </Typography>
                  </TableCell>

                  {/* Delete */}
                  <TableCell align="center">
                    <Tooltip title="Remove trade">
                      <IconButton
                        size="small"
                        color="error"
                        onClick={() => onRemoveTrade?.(trade)}
                        sx={{ p: 0.25 }}
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Net Premium Summary */}
      <Box sx={{
        mt: 1,
        p: 1.5,
        backgroundColor: 'rgba(255,255,255,0.03)',
        borderRadius: 1,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
          Net Premium:
        </Typography>
        <Typography
          variant="h6"
          sx={netPremium >= 0 ? styles.premiumCredit : styles.premiumDebit}
        >
          {netPremium >= 0 ? '+' : ''}{netPremium.toFixed(2)} USD
          <Typography component="span" variant="body2" sx={{ ml: 1, color: 'text.secondary' }}>
            ({netPremium >= 0 ? 'Credit' : 'Debit'})
          </Typography>
        </Typography>
      </Box>
    </Box>
  );
}
