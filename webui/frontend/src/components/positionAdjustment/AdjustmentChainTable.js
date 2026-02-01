/**
 * Adjustment Chain Table
 * ======================
 * Options chain display with quick Buy/Sell selection buttons.
 * Similar to Sensibull's strike selection interface.
 * 
 * Features:
 * - Strike prices centered
 * - Call side on left, Put side on right
 * - B (Buy) / S (Sell) buttons for each option
 * - LTP, IV, OI data displayed
 * - ATM row highlighted
 * - Qty input appears after selection
 * 
 * Created: January 31, 2026
 */

import React, { useState, useEffect, useMemo, useCallback } from 'react';
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
  Button,
  ButtonGroup,
  TextField,
  CircularProgress,
  Alert,
  Chip,
  Tooltip,
  IconButton,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from '@mui/material';
import {
  Add as AddIcon,
  Remove as RemoveIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { optionsChainAPI } from '../optionsChain/services/chainAPI';

// Styling constants
const styles = {
  buyButton: {
    backgroundColor: '#2e7d32',
    color: '#fff',
    minWidth: '32px',
    padding: '2px 6px',
    fontSize: '0.75rem',
    '&:hover': {
      backgroundColor: '#1b5e20',
    },
  },
  buyButtonActive: {
    backgroundColor: '#1b5e20',
    color: '#fff',
    minWidth: '32px',
    padding: '2px 6px',
    fontSize: '0.75rem',
    boxShadow: '0 0 8px rgba(46, 125, 50, 0.6)',
  },
  sellButton: {
    backgroundColor: '#c62828',
    color: '#fff',
    minWidth: '32px',
    padding: '2px 6px',
    fontSize: '0.75rem',
    '&:hover': {
      backgroundColor: '#b71c1c',
    },
  },
  sellButtonActive: {
    backgroundColor: '#b71c1c',
    color: '#fff',
    minWidth: '32px',
    padding: '2px 6px',
    fontSize: '0.75rem',
    boxShadow: '0 0 8px rgba(198, 40, 40, 0.6)',
  },
  atmRow: {
    backgroundColor: 'rgba(33, 150, 243, 0.1)',
    borderLeft: '3px solid #2196f3',
    borderRight: '3px solid #2196f3',
  },
  strikeCell: {
    fontWeight: 'bold',
    textAlign: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.02)',
    borderLeft: '1px solid rgba(255, 255, 255, 0.1)',
    borderRight: '1px solid rgba(255, 255, 255, 0.1)',
  },
  qtyInput: {
    width: '60px',
    '& input': {
      padding: '4px 8px',
      textAlign: 'center',
      fontSize: '0.875rem',
    },
  },
};

/**
 * Format expiry date for display
 * @param {string} expiry - DDMMYYYY format
 * @returns {string} Formatted date
 */
const formatExpiry = (expiry) => {
  if (!expiry || expiry.length !== 8) return expiry;
  const day = expiry.slice(0, 2);
  const month = expiry.slice(2, 4);
  const year = expiry.slice(4, 8);
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const monthName = months[parseInt(month) - 1] || month;
  return `${day} ${monthName} ${year}`;
};

/**
 * AdjustmentChainTable Component
 */
export default function AdjustmentChainTable({
  underlying = 'BTC',
  selectedExpiry,
  onExpiryChange,
  proposedTrades = [],
  onAddTrade,
  onRemoveTrade,
  onUpdateTradeQty,
  spotPrice,
  loading: externalLoading = false,
  isOpen = false,
}) {
  // State
  const [expirations, setExpirations] = useState([]);
  const [chainData, setChainData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Reset state when panel opens
  useEffect(() => {
    if (isOpen) {
      console.log('[AdjustmentChainTable] Panel opened, resetting state');
      setError(null);
    }
  }, [isOpen]);

  // Fetch available expirations
  useEffect(() => {
    // Only fetch when panel is open
    if (!isOpen) return;

    const fetchExpirations = async () => {
      try {
        setLoading(true);
        setError(null);
        const result = await optionsChainAPI.getExpirations(underlying);
        console.log('[AdjustmentChainTable] Fetched expirations:', result);
        setExpirations(result || []);
        
        // Auto-select first expiry if none selected
        if (!selectedExpiry && result && result.length > 0) {
          console.log('[AdjustmentChainTable] Auto-selecting first expiry:', result[0]);
          onExpiryChange?.(result[0]);
        }
      } catch (err) {
        console.error('[AdjustmentChainTable] Failed to fetch expirations:', err);
        setError('Failed to load expiry dates');
      } finally {
        setLoading(false);
      }
    };

    fetchExpirations();
  }, [underlying, isOpen]);

  // Fetch chain data when expiry changes
  useEffect(() => {
    const fetchChainData = async () => {
      if (!selectedExpiry || !isOpen) {
        console.log('[AdjustmentChainTable] Skipping chain fetch:', { selectedExpiry, isOpen });
        return;
      }

      try {
        setLoading(true);
        setError(null);
        console.log('[AdjustmentChainTable] Fetching chain data:', { underlying, selectedExpiry });
        const result = await optionsChainAPI.getChainData(underlying, selectedExpiry);
        console.log('[AdjustmentChainTable] Chain data received:', result);
        setChainData(result);
      } catch (err) {
        console.error('[AdjustmentChainTable] Failed to fetch chain data:', err);
        setError('Failed to load options chain: ' + err.message);
        setChainData(null);
      } finally {
        setLoading(false);
      }
    };

    fetchChainData();
  }, [underlying, selectedExpiry, isOpen]);

  // Find ATM strike - prefer API's atm_strike if available
  const atmStrike = useMemo(() => {
    // Use API's atm_strike if available
    if (chainData?.atm_strike) return chainData.atm_strike;
    
    // Use spot price from API if available
    const effectiveSpot = chainData?.spot_price || spotPrice;
    if (!effectiveSpot || !chainData?.chain) return null;
    
    const strikes = chainData.chain.map(s => parseFloat(s.strike));
    if (strikes.length === 0) return null;

    // Find closest strike to spot
    return strikes.reduce((closest, strike) => {
      return Math.abs(strike - effectiveSpot) < Math.abs(closest - effectiveSpot) ? strike : closest;
    });
  }, [spotPrice, chainData]);

  // Check if a trade is selected
  const isTradeSelected = useCallback((strike, type, side) => {
    return proposedTrades.some(t => 
      t.strike === strike && 
      t.type === type && 
      t.side === side
    );
  }, [proposedTrades]);

  // Get trade quantity for a selected trade
  const getTradeQty = useCallback((strike, type, side) => {
    const trade = proposedTrades.find(t => 
      t.strike === strike && 
      t.type === type && 
      t.side === side
    );
    return trade?.quantity || 0;
  }, [proposedTrades]);

  // Handle Buy/Sell button click
  const handleTradeClick = useCallback((strike, type, side, optionData) => {
    const existingTrade = proposedTrades.find(t => 
      t.strike === strike && 
      t.type === type && 
      t.side === side
    );

    if (existingTrade) {
      // Remove if already selected
      onRemoveTrade?.(existingTrade);
    } else {
      // Check if opposite side is selected - remove it first
      const oppositeSide = side === 'buy' ? 'sell' : 'buy';
      const oppositeTrade = proposedTrades.find(t => 
        t.strike === strike && 
        t.type === type && 
        t.side === oppositeSide
      );
      if (oppositeTrade) {
        onRemoveTrade?.(oppositeTrade);
      }

      // Add new trade
      const symbol = `${type === 'call' ? 'C' : 'P'}-${underlying}-${strike}-${convertExpiryFormat(selectedExpiry)}`;
      
      // Use mark_price from API, fallback to ltp for backwards compatibility
      const price = optionData?.mark_price || optionData?.ltp || 0;
      
      onAddTrade?.({
        symbol,
        strike,
        type,
        side,
        quantity: 1, // Default quantity
        ltp: price,
        premium: price,
        iv: optionData?.iv || 0,
        delta: optionData?.delta || 0,
        gamma: optionData?.gamma || 0,
        theta: optionData?.theta || 0,
        vega: optionData?.vega || 0,
        expiry: selectedExpiry,
        spotPrice: chainData?.spot_price || spotPrice,
      });
    }
  }, [proposedTrades, underlying, selectedExpiry, spotPrice, chainData, onAddTrade, onRemoveTrade]);

  // Handle quantity change
  const handleQtyChange = useCallback((strike, type, side, newQty) => {
    const qty = Math.max(1, parseInt(newQty) || 1);
    onUpdateTradeQty?.(strike, type, side, qty);
  }, [onUpdateTradeQty]);

  // Convert DDMMYYYY to DDMMYY format for symbol
  const convertExpiryFormat = (expiry) => {
    if (!expiry || expiry.length !== 8) return expiry;
    const day = expiry.slice(0, 2);
    const month = expiry.slice(2, 4);
    const year = expiry.slice(6, 8); // Last 2 digits
    return `${day}${month}${year}`;
  };

  // Refresh chain data
  const handleRefresh = async () => {
    if (!selectedExpiry) return;
    
    try {
      setLoading(true);
      await optionsChainAPI.refresh(underlying, selectedExpiry);
      const result = await optionsChainAPI.getChainData(underlying, selectedExpiry);
      setChainData(result);
      setError(null);
    } catch (err) {
      console.error('[AdjustmentChainTable] Refresh failed:', err);
      setError('Failed to refresh chain data');
    } finally {
      setLoading(false);
    }
  };

  // Render loading state
  if (loading || externalLoading) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <CircularProgress size={40} />
        <Typography sx={{ mt: 2, color: 'text.secondary' }}>
          Loading options chain...
        </Typography>
        <Typography variant="caption" sx={{ mt: 1, display: 'block', color: 'text.secondary' }}>
          {underlying} - {selectedExpiry || 'Selecting expiry...'}
        </Typography>
      </Box>
    );
  }

  // Render error state
  if (error) {
    return (
      <Box sx={{ p: 2 }}>
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
        <Typography variant="caption" sx={{ mb: 2, display: 'block', color: 'text.secondary' }}>
          Underlying: {underlying} | Expiry: {selectedExpiry || 'None selected'}
        </Typography>
        <Button onClick={handleRefresh} startIcon={<RefreshIcon />}>
          Retry
        </Button>
      </Box>
    );
  }

  // If no expiry selected, show prompt
  if (!selectedExpiry) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography sx={{ color: 'text.secondary', mb: 2 }}>
          Select an expiry date to view options chain
        </Typography>
        {expirations.length > 0 && (
          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel>Expiry</InputLabel>
            <Select
              value=""
              onChange={(e) => onExpiryChange?.(e.target.value)}
              label="Expiry"
            >
              {expirations.map((exp) => (
                <MenuItem key={exp} value={exp}>
                  {formatExpiry(exp)}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        )}
      </Box>
    );
  }

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header with expiry selector */}
      <Box sx={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: 2, 
        mb: 2, 
        px: 1,
        flexWrap: 'wrap',
      }}>
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <InputLabel>Expiry</InputLabel>
          <Select
            value={selectedExpiry || ''}
            onChange={(e) => onExpiryChange?.(e.target.value)}
            label="Expiry"
          >
            {expirations.map((exp) => (
              <MenuItem key={exp} value={exp}>
                {formatExpiry(exp)}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <Chip 
          label={`Spot: $${(chainData?.spot_price || spotPrice)?.toLocaleString() || '-'}`}
          variant="outlined"
          size="small"
          sx={{ fontWeight: 'bold' }}
        />

        {atmStrike && (
          <Chip 
            label={`ATM: $${atmStrike.toLocaleString()}`}
            color="primary"
            size="small"
          />
        )}

        <IconButton size="small" onClick={handleRefresh} disabled={loading}>
          <RefreshIcon />
        </IconButton>

        <Typography variant="caption" sx={{ color: 'text.secondary', ml: 'auto' }}>
          Click B to Buy, S to Sell
        </Typography>
      </Box>

      {/* Chain table */}
      <TableContainer 
        component={Paper} 
        sx={{ 
          flex: 1, 
          overflow: 'auto',
          backgroundColor: 'transparent',
          '& .MuiTable-root': {
            minWidth: 600,
          },
        }}
      >
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              {/* Call side */}
              <TableCell align="center" sx={{ fontWeight: 'bold', color: '#4caf50' }}>
                LTP
              </TableCell>
              <TableCell align="center" sx={{ fontWeight: 'bold', color: '#4caf50' }}>
                IV
              </TableCell>
              <TableCell align="center" sx={{ fontWeight: 'bold', color: '#4caf50' }}>
                Call
              </TableCell>
              
              {/* Strike */}
              <TableCell align="center" sx={{ fontWeight: 'bold', backgroundColor: 'rgba(255,255,255,0.05)' }}>
                Strike
              </TableCell>
              
              {/* Put side */}
              <TableCell align="center" sx={{ fontWeight: 'bold', color: '#f44336' }}>
                Put
              </TableCell>
              <TableCell align="center" sx={{ fontWeight: 'bold', color: '#f44336' }}>
                IV
              </TableCell>
              <TableCell align="center" sx={{ fontWeight: 'bold', color: '#f44336' }}>
                LTP
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {chainData?.chain?.map((strikeData) => {
              const strike = parseFloat(strikeData.strike);
              const isAtm = strike === atmStrike;
              const callData = strikeData.call || {};
              const putData = strikeData.put || {};

              return (
                <TableRow 
                  key={strike}
                  sx={isAtm ? styles.atmRow : {}}
                  hover
                >
                  {/* Call LTP (using mark_price from API) */}
                  <TableCell align="right" sx={{ color: '#4caf50' }}>
                    ${(callData.mark_price || callData.ltp)?.toFixed(2) || '-'}
                  </TableCell>

                  {/* Call IV */}
                  <TableCell align="center" sx={{ color: 'text.secondary', fontSize: '0.75rem' }}>
                    {callData.iv ? `${(callData.iv * 100).toFixed(0)}%` : '-'}
                  </TableCell>

                  {/* Call B/S buttons + Qty */}
                  <TableCell align="center">
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
                      <ButtonGroup size="small">
                        <Button
                          sx={isTradeSelected(strike, 'call', 'buy') ? styles.buyButtonActive : styles.buyButton}
                          onClick={() => handleTradeClick(strike, 'call', 'buy', callData)}
                        >
                          B
                        </Button>
                        <Button
                          sx={isTradeSelected(strike, 'call', 'sell') ? styles.sellButtonActive : styles.sellButton}
                          onClick={() => handleTradeClick(strike, 'call', 'sell', callData)}
                        >
                          S
                        </Button>
                      </ButtonGroup>
                      
                      {/* Qty input if selected */}
                      {(isTradeSelected(strike, 'call', 'buy') || isTradeSelected(strike, 'call', 'sell')) && (
                        <TextField
                          size="small"
                          type="number"
                          value={getTradeQty(strike, 'call', isTradeSelected(strike, 'call', 'buy') ? 'buy' : 'sell')}
                          onChange={(e) => handleQtyChange(
                            strike, 
                            'call', 
                            isTradeSelected(strike, 'call', 'buy') ? 'buy' : 'sell',
                            e.target.value
                          )}
                          sx={styles.qtyInput}
                          inputProps={{ min: 1, max: 1000 }}
                        />
                      )}
                    </Box>
                  </TableCell>

                  {/* Strike price */}
                  <TableCell sx={styles.strikeCell}>
                    <Typography 
                      variant="body2" 
                      sx={{ 
                        fontWeight: isAtm ? 'bold' : 'normal',
                        color: isAtm ? '#2196f3' : 'inherit',
                      }}
                    >
                      ${strike.toLocaleString()}
                    </Typography>
                    {isAtm && (
                      <Chip label="ATM" size="small" color="primary" sx={{ fontSize: '0.6rem', height: 16, mt: 0.5 }} />
                    )}
                  </TableCell>

                  {/* Put B/S buttons + Qty */}
                  <TableCell align="center">
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
                      {/* Qty input if selected */}
                      {(isTradeSelected(strike, 'put', 'buy') || isTradeSelected(strike, 'put', 'sell')) && (
                        <TextField
                          size="small"
                          type="number"
                          value={getTradeQty(strike, 'put', isTradeSelected(strike, 'put', 'buy') ? 'buy' : 'sell')}
                          onChange={(e) => handleQtyChange(
                            strike, 
                            'put', 
                            isTradeSelected(strike, 'put', 'buy') ? 'buy' : 'sell',
                            e.target.value
                          )}
                          sx={styles.qtyInput}
                          inputProps={{ min: 1, max: 1000 }}
                        />
                      )}
                      
                      <ButtonGroup size="small">
                        <Button
                          sx={isTradeSelected(strike, 'put', 'buy') ? styles.buyButtonActive : styles.buyButton}
                          onClick={() => handleTradeClick(strike, 'put', 'buy', putData)}
                        >
                          B
                        </Button>
                        <Button
                          sx={isTradeSelected(strike, 'put', 'sell') ? styles.sellButtonActive : styles.sellButton}
                          onClick={() => handleTradeClick(strike, 'put', 'sell', putData)}
                        >
                          S
                        </Button>
                      </ButtonGroup>
                    </Box>
                  </TableCell>

                  {/* Put IV */}
                  <TableCell align="center" sx={{ color: 'text.secondary', fontSize: '0.75rem' }}>
                    {putData.iv ? `${(putData.iv * 100).toFixed(0)}%` : '-'}
                  </TableCell>

                  {/* Put LTP */}
                  <TableCell align="left" sx={{ color: '#f44336' }}>
                    ${(putData.mark_price || putData.ltp)?.toFixed(2) || '-'}
                  </TableCell>
                </TableRow>
              );
            })}

            {(!chainData?.chain || chainData.chain.length === 0) && (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 4 }}>
                  <Typography color="text.secondary">
                    {selectedExpiry ? 'No options data available' : 'Select an expiry date'}
                  </Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}
