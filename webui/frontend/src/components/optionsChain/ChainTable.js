/**
 * Chain Table Component
 * =====================
 * Displays options chain data in a professional table format.
 * Shows calls on left, strikes in center, puts on right.
 * Includes buy/sell buttons for trading.
 * 
 * Created: January 5, 2026
 * Updated: January 5, 2026 - Added trading functionality
 */

import React, { useState, useMemo } from 'react';
import {
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  Tooltip,
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  ButtonGroup,
  Button,
} from '@mui/material';

// Formatting helpers
const formatPrice = (price) => {
  if (price === null || price === undefined || price === 0) return '-';
  return `$${Number(price).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
};

const formatIV = (iv) => {
  if (iv === null || iv === undefined || iv === 0) return '-';
  return `${(Number(iv) * 100).toFixed(1)}%`;
};

const formatOI = (oi) => {
  if (oi === null || oi === undefined || oi === 0) return '-';
  if (oi >= 1000000) return `${(oi / 1000000).toFixed(1)}M`;
  if (oi >= 1000) return `${(oi / 1000).toFixed(1)}K`;
  return oi.toString();
};

const formatDelta = (delta) => {
  if (delta === null || delta === undefined) return '-';
  return Number(delta).toFixed(2);
};

// Determine if strike is ITM, ATM, or OTM
const getMoneyness = (strike, spotPrice, optionType) => {
  const diff = Math.abs(strike - spotPrice);
  const pct = diff / spotPrice;
  
  if (pct < 0.01) return 'ATM';
  
  if (optionType === 'call') {
    return strike < spotPrice ? 'ITM' : 'OTM';
  } else {
    return strike > spotPrice ? 'ITM' : 'OTM';
  }
};

// Get background color based on moneyness
const getMoneynessColor = (moneyness) => {
  switch (moneyness) {
    case 'ITM':
      return 'rgba(76, 175, 80, 0.15)';
    case 'ATM':
      return 'rgba(255, 193, 7, 0.25)';
    case 'OTM':
    default:
      return 'transparent';
  }
};

// Trade button component
const TradeButtons = ({ onBuy, onSell, disabled, selected }) => (
  <ButtonGroup size="small" variant={selected ? "contained" : "outlined"}>
    <Button 
      color="success" 
      onClick={(e) => { e.stopPropagation(); onBuy(); }}
      disabled={disabled}
      sx={{ 
        minWidth: 28, 
        px: 0.5,
        fontSize: '0.65rem',
        '&:hover': { bgcolor: 'success.dark', color: 'white' }
      }}
    >
      B
    </Button>
    <Button 
      color="error" 
      onClick={(e) => { e.stopPropagation(); onSell(); }}
      disabled={disabled}
      sx={{ 
        minWidth: 28, 
        px: 0.5,
        fontSize: '0.65rem',
        '&:hover': { bgcolor: 'error.dark', color: 'white' }
      }}
    >
      S
    </Button>
  </ButtonGroup>
);

const ChainTable = ({ chainData, spotPrice, atmStrike, onTrade, strategyMode, strategyContext, selectedLegs, builderMode }) => {
  const [moneynessFilter, setMoneynessFilter] = useState('atm10');
  
  // Get suggested strikes from strategy context
  const suggestedStrikes = useMemo(() => {
    if (!strategyContext?.suggestedStrikes) return [];
    return Object.values(strategyContext.suggestedStrikes);
  }, [strategyContext]);
  
  // Check if a strike is suggested
  const isStrikeSuggested = (strike) => {
    return suggestedStrikes.some(s => Math.abs(s - strike) < strike * 0.01);
  };
  
  // Check if an option is already selected (for strategy mode or builder mode)
  const isLegSelected = (symbol, side) => {
    if (!selectedLegs) return false;
    return selectedLegs.some(leg => leg.symbol === symbol && leg.side === side);
  };
  
  // Check if option is selected in any way (for highlighting)
  const isOptionSelected = (symbol) => {
    if (!selectedLegs) return false;
    return selectedLegs.some(leg => leg.symbol === symbol);
  };
  
  // Filter strikes based on moneyness
  const filteredChain = useMemo(() => {
    if (!chainData?.chain) return [];
    
    let chain = chainData.chain;
    
    if (moneynessFilter === 'atm5') {
      const lower = spotPrice * 0.95;
      const upper = spotPrice * 1.05;
      chain = chain.filter(s => s.strike >= lower && s.strike <= upper);
    } else if (moneynessFilter === 'atm10') {
      const lower = spotPrice * 0.90;
      const upper = spotPrice * 1.10;
      chain = chain.filter(s => s.strike >= lower && s.strike <= upper);
    }
    
    return chain;
  }, [chainData, spotPrice, moneynessFilter]);
  
  // Handle trade button click
  const handleTrade = (optionData, type, side) => {
    if (!onTrade) return;
    
    onTrade({
      symbol: optionData.symbol,
      strike: optionData.strike_price,
      type: type,
      side: side,
      bid: optionData.bid,
      ask: optionData.ask,
      ltp: optionData.ltp || optionData.mark_price || ((optionData.bid + optionData.ask) / 2),
      iv: optionData.iv,
      delta: optionData.delta
    });
  };
  
  if (!chainData?.chain || chainData.chain.length === 0) {
    return (
      <Box sx={{ p: 4, textAlign: 'center' }}>
        <Typography color="text.secondary">
          No chain data available
        </Typography>
      </Box>
    );
  }
  
  return (
    <Box>
      {/* Filter Controls */}
      <Box sx={{ mb: 2, display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <InputLabel>Strike Range</InputLabel>
          <Select
            value={moneynessFilter}
            onChange={(e) => setMoneynessFilter(e.target.value)}
            label="Strike Range"
          >
            <MenuItem value="all">All Strikes ({chainData.chain.length})</MenuItem>
            <MenuItem value="atm5">ATM ±5%</MenuItem>
            <MenuItem value="atm10">ATM ±10%</MenuItem>
          </Select>
        </FormControl>
        
        <Chip 
          label={`${filteredChain.length} strikes`} 
          size="small" 
          variant="outlined" 
        />
        
        <Box sx={{ ml: 'auto', display: 'flex', gap: 2 }}>
          <Chip 
            label={`Calls OI: ${formatOI(chainData.summary?.call_oi)}`}
            size="small"
            color="success"
            variant="outlined"
          />
          <Chip 
            label={`Puts OI: ${formatOI(chainData.summary?.put_oi)}`}
            size="small"
            color="error"
            variant="outlined"
          />
        </Box>
      </Box>
      
      {/* Trading hint */}
      <Box sx={{ mb: 1, px: 1 }}>
        <Typography variant="caption" color="text.secondary">
          💡 Click <strong>B</strong> to Buy or <strong>S</strong> to Sell. You can also click on Bid/Ask prices directly.
        </Typography>
      </Box>
      
      {/* Chain Table */}
      <TableContainer sx={{ maxHeight: 520, overflowX: 'auto' }}>
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell 
                colSpan={7} 
                align="center" 
                sx={{ 
                  bgcolor: 'success.dark', 
                  color: 'white',
                  fontWeight: 'bold',
                  borderRight: '2px solid #666'
                }}
              >
                📈 CALLS (Bullish)
              </TableCell>
              
              <TableCell 
                align="center" 
                sx={{ 
                  bgcolor: 'grey.800', 
                  color: 'white',
                  fontWeight: 'bold',
                  borderRight: '2px solid #666'
                }}
              >
                STRIKE
              </TableCell>
              
              <TableCell 
                colSpan={7} 
                align="center" 
                sx={{ 
                  bgcolor: 'error.dark', 
                  color: 'white',
                  fontWeight: 'bold'
                }}
              >
                📉 PUTS (Bearish)
              </TableCell>
            </TableRow>
            
            <TableRow>
              <TableCell sx={{ borderRight: '1px solid #333', minWidth: 55, fontSize: '0.7rem' }}>Trade</TableCell>
              <TableCell sx={{ borderRight: '1px solid #333', fontSize: '0.7rem' }}>OI</TableCell>
              <TableCell sx={{ borderRight: '1px solid #333', fontSize: '0.7rem' }}>IV</TableCell>
              <TableCell sx={{ borderRight: '1px solid #333', fontSize: '0.7rem' }}>Δ</TableCell>
              <TableCell sx={{ borderRight: '1px solid #333', color: 'success.main', fontSize: '0.7rem' }}>Bid</TableCell>
              <TableCell sx={{ borderRight: '1px solid #333', color: 'error.main', fontSize: '0.7rem' }}>Ask</TableCell>
              <TableCell sx={{ borderRight: '2px solid #666', fontSize: '0.7rem' }}>Sprd</TableCell>
              
              <TableCell align="center" sx={{ borderRight: '2px solid #666', fontWeight: 'bold', fontSize: '0.75rem' }}>
                Strike
              </TableCell>
              
              <TableCell sx={{ borderRight: '1px solid #333', fontSize: '0.7rem' }}>Sprd</TableCell>
              <TableCell sx={{ borderRight: '1px solid #333', color: 'success.main', fontSize: '0.7rem' }}>Bid</TableCell>
              <TableCell sx={{ borderRight: '1px solid #333', color: 'error.main', fontSize: '0.7rem' }}>Ask</TableCell>
              <TableCell sx={{ borderRight: '1px solid #333', fontSize: '0.7rem' }}>Δ</TableCell>
              <TableCell sx={{ borderRight: '1px solid #333', fontSize: '0.7rem' }}>IV</TableCell>
              <TableCell sx={{ borderRight: '1px solid #333', fontSize: '0.7rem' }}>OI</TableCell>
              <TableCell sx={{ minWidth: 55, fontSize: '0.7rem' }}>Trade</TableCell>
            </TableRow>
          </TableHead>
          
          <TableBody>
            {filteredChain.map((row) => {
              const isATM = row.strike === atmStrike;
              const callMoneyness = getMoneyness(row.strike, spotPrice, 'call');
              const putMoneyness = getMoneyness(row.strike, spotPrice, 'put');
              
              const call = row.call || {};
              const put = row.put || {};
              
              const hasCall = call.symbol;
              const hasPut = put.symbol;
              
              // Strategy mode or Builder mode: check if suggested or selected
              const isInSelectionMode = strategyMode || builderMode;
              const isSuggested = strategyMode && !builderMode && isStrikeSuggested(row.strike);
              const isCallSelectedBuy = isInSelectionMode && isLegSelected(call.symbol, 'buy');
              const isCallSelectedSell = isInSelectionMode && isLegSelected(call.symbol, 'sell');
              const isPutSelectedBuy = isInSelectionMode && isLegSelected(put.symbol, 'buy');
              const isPutSelectedSell = isInSelectionMode && isLegSelected(put.symbol, 'sell');
              
              // Calculate spread percentage
              const callSpread = call.bid && call.ask 
                ? (((call.ask - call.bid) / ((call.ask + call.bid) / 2)) * 100).toFixed(1) + '%'
                : '-';
              const putSpread = put.bid && put.ask 
                ? (((put.ask - put.bid) / ((put.ask + put.bid) / 2)) * 100).toFixed(1) + '%'
                : '-';
              
              return (
                <TableRow 
                  key={row.strike}
                  sx={{
                    '&:hover': { bgcolor: 'action.hover' },
                    bgcolor: isATM ? 'rgba(255, 193, 7, 0.2)' : 
                             isSuggested && strategyMode && !builderMode ? 'rgba(33, 150, 243, 0.15)' : 'inherit',
                    borderTop: isATM ? '2px solid #ffc107' : 
                               isSuggested && strategyMode && !builderMode ? '1px solid #2196f3' : 'none',
                    borderBottom: isATM ? '2px solid #ffc107' : 
                                  isSuggested && strategyMode && !builderMode ? '1px solid #2196f3' : 'none',
                    animation: isSuggested && strategyMode && !builderMode ? 'suggestedPulse 2s infinite' : 'none'
                  }}
                >
                  {/* CALL Trade */}
                  <TableCell 
                    sx={{ 
                      bgcolor: isCallSelectedBuy || isCallSelectedSell 
                        ? 'rgba(76, 175, 80, 0.3)' 
                        : getMoneynessColor(callMoneyness), 
                      borderRight: '1px solid #333', 
                      p: 0.5,
                      position: 'relative'
                    }}
                  >
                    {(isCallSelectedBuy || isCallSelectedSell) && (
                      <Chip 
                        label={isCallSelectedBuy ? 'BUY' : 'SELL'} 
                        size="small" 
                        color={isCallSelectedBuy ? 'success' : 'error'}
                        sx={{ 
                          position: 'absolute', 
                          top: 2, 
                          right: 2, 
                          height: 14, 
                          fontSize: 8,
                          '& .MuiChip-label': { px: 0.5 }
                        }} 
                      />
                    )}
                    {hasCall && (
                      <TradeButtons 
                        onBuy={() => handleTrade(call, 'call', 'buy')}
                        onSell={() => handleTrade(call, 'call', 'sell')}
                        disabled={!onTrade || (!builderMode && (isCallSelectedBuy || isCallSelectedSell))}
                        selected={isCallSelectedBuy || isCallSelectedSell}
                      />
                    )}
                  </TableCell>
                  
                  {/* CALL OI */}
                  <TableCell sx={{ bgcolor: getMoneynessColor(callMoneyness), borderRight: '1px solid #333', fontSize: '0.75rem' }}>
                    {formatOI(call.oi)}
                  </TableCell>
                  
                  {/* CALL IV */}
                  <TableCell sx={{ bgcolor: getMoneynessColor(callMoneyness), borderRight: '1px solid #333', fontSize: '0.75rem' }}>
                    <Typography 
                      variant="body2" 
                      sx={{ fontSize: '0.75rem' }}
                      color={call.iv > 0.5 ? 'warning.main' : 'text.primary'}
                    >
                      {formatIV(call.iv)}
                    </Typography>
                  </TableCell>
                  
                  {/* CALL Delta */}
                  <TableCell sx={{ bgcolor: getMoneynessColor(callMoneyness), borderRight: '1px solid #333', fontSize: '0.75rem' }}>
                    <Typography 
                      variant="body2" 
                      sx={{ fontSize: '0.75rem' }}
                      color={call.delta > 0.5 ? 'success.main' : 'text.secondary'}
                    >
                      {formatDelta(call.delta)}
                    </Typography>
                  </TableCell>
                  
                  {/* CALL Bid - clickable for sell */}
                  <TableCell 
                    sx={{ 
                      bgcolor: getMoneynessColor(callMoneyness), 
                      borderRight: '1px solid #333',
                      color: 'success.main',
                      cursor: hasCall ? 'pointer' : 'default',
                      fontSize: '0.75rem',
                      '&:hover': hasCall ? { bgcolor: 'success.dark', color: 'white' } : {}
                    }}
                    onClick={() => hasCall && handleTrade(call, 'call', 'sell')}
                  >
                    {formatPrice(call.bid)}
                  </TableCell>
                  
                  {/* CALL Ask - clickable for buy */}
                  <TableCell 
                    sx={{ 
                      bgcolor: getMoneynessColor(callMoneyness), 
                      borderRight: '1px solid #333',
                      color: 'error.main',
                      cursor: hasCall ? 'pointer' : 'default',
                      fontSize: '0.75rem',
                      '&:hover': hasCall ? { bgcolor: 'error.dark', color: 'white' } : {}
                    }}
                    onClick={() => hasCall && handleTrade(call, 'call', 'buy')}
                  >
                    {formatPrice(call.ask)}
                  </TableCell>
                  
                  {/* CALL Spread */}
                  <TableCell sx={{ bgcolor: getMoneynessColor(callMoneyness), borderRight: '2px solid #666', fontSize: '0.7rem', color: 'text.secondary' }}>
                    {callSpread}
                  </TableCell>
                  
                  {/* STRIKE Column */}
                  <TableCell 
                    align="center" 
                    sx={{ 
                      fontWeight: 'bold',
                      bgcolor: isATM ? 'warning.dark' : 'grey.900',
                      color: isATM ? 'white' : 'inherit',
                      borderRight: '2px solid #666',
                      fontSize: '0.85rem'
                    }}
                  >
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
                      ${row.strike.toLocaleString()}
                      {isATM && (
                        <Chip label="ATM" size="small" color="warning" sx={{ height: 16, fontSize: 9 }} />
                      )}
                    </Box>
                  </TableCell>
                  
                  {/* PUT Spread */}
                  <TableCell sx={{ bgcolor: getMoneynessColor(putMoneyness), borderRight: '1px solid #333', fontSize: '0.7rem', color: 'text.secondary' }}>
                    {putSpread}
                  </TableCell>
                  
                  {/* PUT Bid - clickable for sell */}
                  <TableCell 
                    sx={{ 
                      bgcolor: getMoneynessColor(putMoneyness), 
                      borderRight: '1px solid #333',
                      color: 'success.main',
                      cursor: hasPut ? 'pointer' : 'default',
                      fontSize: '0.75rem',
                      '&:hover': hasPut ? { bgcolor: 'success.dark', color: 'white' } : {}
                    }}
                    onClick={() => hasPut && handleTrade(put, 'put', 'sell')}
                  >
                    {formatPrice(put.bid)}
                  </TableCell>
                  
                  {/* PUT Ask - clickable for buy */}
                  <TableCell 
                    sx={{ 
                      bgcolor: getMoneynessColor(putMoneyness), 
                      borderRight: '1px solid #333',
                      color: 'error.main',
                      cursor: hasPut ? 'pointer' : 'default',
                      fontSize: '0.75rem',
                      '&:hover': hasPut ? { bgcolor: 'error.dark', color: 'white' } : {}
                    }}
                    onClick={() => hasPut && handleTrade(put, 'put', 'buy')}
                  >
                    {formatPrice(put.ask)}
                  </TableCell>
                  
                  {/* PUT Delta */}
                  <TableCell sx={{ bgcolor: getMoneynessColor(putMoneyness), borderRight: '1px solid #333', fontSize: '0.75rem' }}>
                    <Typography 
                      variant="body2" 
                      sx={{ fontSize: '0.75rem' }}
                      color={Math.abs(put.delta) > 0.5 ? 'error.main' : 'text.secondary'}
                    >
                      {formatDelta(put.delta)}
                    </Typography>
                  </TableCell>
                  
                  {/* PUT IV */}
                  <TableCell sx={{ bgcolor: getMoneynessColor(putMoneyness), borderRight: '1px solid #333', fontSize: '0.75rem' }}>
                    <Typography 
                      variant="body2" 
                      sx={{ fontSize: '0.75rem' }}
                      color={put.iv > 0.5 ? 'warning.main' : 'text.primary'}
                    >
                      {formatIV(put.iv)}
                    </Typography>
                  </TableCell>
                  
                  {/* PUT OI */}
                  <TableCell sx={{ bgcolor: getMoneynessColor(putMoneyness), borderRight: '1px solid #333', fontSize: '0.75rem' }}>
                    {formatOI(put.oi)}
                  </TableCell>
                  
                  {/* PUT Trade */}
                  <TableCell 
                    sx={{ 
                      bgcolor: isPutSelectedBuy || isPutSelectedSell 
                        ? 'rgba(244, 67, 54, 0.3)' 
                        : getMoneynessColor(putMoneyness), 
                      p: 0.5,
                      position: 'relative'
                    }}
                  >
                    {(isPutSelectedBuy || isPutSelectedSell) && (
                      <Chip 
                        label={isPutSelectedBuy ? 'BUY' : 'SELL'} 
                        size="small" 
                        color={isPutSelectedBuy ? 'success' : 'error'}
                        sx={{ 
                          position: 'absolute', 
                          top: 2, 
                          right: 2, 
                          height: 14, 
                          fontSize: 8,
                          '& .MuiChip-label': { px: 0.5 }
                        }} 
                      />
                    )}
                    {hasPut && (
                      <TradeButtons 
                        onBuy={() => handleTrade(put, 'put', 'buy')}
                        onSell={() => handleTrade(put, 'put', 'sell')}
                        disabled={!onTrade || (!builderMode && (isPutSelectedBuy || isPutSelectedSell))}
                        selected={isPutSelectedBuy || isPutSelectedSell}
                      />
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
      
      {/* Legend */}
      <Box sx={{ mt: 2, display: 'flex', gap: 3, justifyContent: 'center', flexWrap: 'wrap' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={{ width: 14, height: 14, bgcolor: 'rgba(76, 175, 80, 0.15)', border: '1px solid #4caf50' }} />
          <Typography variant="caption">ITM</Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={{ width: 14, height: 14, bgcolor: 'rgba(255, 193, 7, 0.25)', border: '1px solid #ffc107' }} />
          <Typography variant="caption">ATM</Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={{ width: 14, height: 14, bgcolor: 'transparent', border: '1px solid #666' }} />
          <Typography variant="caption">OTM</Typography>
        </Box>
        {strategyMode && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box sx={{ width: 14, height: 14, bgcolor: 'rgba(33, 150, 243, 0.15)', border: '1px solid #2196f3' }} />
            <Typography variant="caption">Suggested</Typography>
          </Box>
        )}
        <Typography variant="caption" color="text.secondary">
          | {strategyMode ? 'Click B/S to add leg' : 'Click Bid = Sell • Click Ask = Buy'}
        </Typography>
      </Box>
      
      {/* CSS Animations */}
      <style>{`
        @keyframes suggestedPulse {
          0%, 100% { background-color: rgba(33, 150, 243, 0.15); }
          50% { background-color: rgba(33, 150, 243, 0.25); }
        }
      `}</style>
    </Box>
  );
};

export default ChainTable;
