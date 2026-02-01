/**
 * Sliding Options Chain Panel
 * ===========================
 * A sliding panel that appears from the left side when "Add New Trade" is clicked.
 * Matches Sensibull's options chain popup design.
 * 
 * Features:
 * - Slides in from left side
 * - Tabs: Straddles, Strangles, Strikes, Futures
 * - Filter toggles: LTP, OI, Greeks
 * - Full options chain with Delta, LTP, OI, Strike, IV columns
 * - B/S buttons for quick trade selection
 * - Clear All / Done buttons at bottom
 * 
 * Created: February 1, 2026
 */

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  IconButton,
  Button,
  ButtonGroup,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  Tab,
  Select,
  MenuItem,
  FormControl,
  TextField,
  CircularProgress,
  Slide,
  Drawer,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
} from '@mui/material';
import {
  Close as CloseIcon,
  Settings as SettingsIcon,
  ChevronRight as ChevronRightIcon,
} from '@mui/icons-material';
import { optionsChainAPI } from '../optionsChain/services/chainAPI';
import { getContractMultiplier } from '../../utils/constants';

// Colors
const COLORS = {
  background: '#1a1f2e',
  cardBg: '#242938',
  border: 'rgba(71, 85, 105, 0.4)',
  text: '#e2e8f0',
  textSecondary: '#94a3b8',
  buy: '#22c55e',
  buyBg: 'rgba(34, 197, 94, 0.15)',
  sell: '#ef4444',
  sellBg: 'rgba(239, 68, 68, 0.15)',
  primary: '#3b82f6',
  atm: '#fbbf24',
  atmBg: 'rgba(251, 191, 36, 0.1)',
  callOi: '#3b82f6',
  putOi: '#a855f7',
};

// Panel width
const PANEL_WIDTH = 480;

/**
 * Format expiry for selector
 */
const formatExpiry = (expiry) => {
  if (!expiry || expiry.length !== 8) return expiry;
  const day = expiry.slice(0, 2);
  const month = parseInt(expiry.slice(2, 4));
  const months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${parseInt(day)} ${months[month] || ''}`;
};

/**
 * Chain Row Component
 */
const ChainRow = ({ 
  strikeData, 
  isAtm, 
  spotPrice,
  proposedTrades, 
  onTradeClick,
  showOi,
  showGreeks,
}) => {
  const strike = parseFloat(strikeData.strike);
  const callData = strikeData.call || {};
  const putData = strikeData.put || {};
  
  // Check if trades are selected
  const isCallBuySelected = proposedTrades.some(t => t.strike === strike && t.type === 'call' && t.side === 'buy');
  const isCallSellSelected = proposedTrades.some(t => t.strike === strike && t.type === 'call' && t.side === 'sell');
  const isPutBuySelected = proposedTrades.some(t => t.strike === strike && t.type === 'put' && t.side === 'buy');
  const isPutSellSelected = proposedTrades.some(t => t.strike === strike && t.type === 'put' && t.side === 'sell');
  
  // Calculate moneyness for visual indicator
  const isItm = spotPrice ? (strike < spotPrice ? 'call-itm' : strike > spotPrice ? 'put-itm' : 'atm') : '';
  
  return (
    <TableRow 
      sx={{ 
        bgcolor: isAtm ? COLORS.atmBg : 'transparent',
        borderLeft: isAtm ? `3px solid ${COLORS.atm}` : 'none',
        '&:hover': { bgcolor: 'rgba(255,255,255,0.02)' },
      }}
    >
      {/* Delta (Call) */}
      {showGreeks && (
        <TableCell align="center" sx={{ color: COLORS.textSecondary, fontSize: '0.75rem', py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
          {callData.delta ? callData.delta.toFixed(2) : '-'}
        </TableCell>
      )}
      
      {/* Call LTP */}
      <TableCell align="right" sx={{ color: COLORS.text, fontSize: '0.8rem', py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
        {(callData.mark_price || callData.ltp)?.toFixed(2) || '-'}
      </TableCell>
      
      {/* Call OI */}
      {showOi && (
        <TableCell align="center" sx={{ py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
          <Box sx={{ 
            height: 6, 
            bgcolor: COLORS.callOi, 
            borderRadius: 1,
            width: `${Math.min((callData.oi || 0) / 1000, 100)}%`,
            minWidth: callData.oi ? 4 : 0,
          }} />
        </TableCell>
      )}
      
      {/* B/S Buttons (Call) */}
      <TableCell align="center" sx={{ py: 0.5, borderBottom: `1px solid ${COLORS.border}` }}>
        <ButtonGroup size="small" sx={{ minWidth: 60 }}>
          <Button
            onClick={() => onTradeClick(strike, 'call', 'buy', callData)}
            sx={{
              minWidth: 28,
              px: 0.5,
              py: 0.25,
              fontSize: '0.7rem',
              fontWeight: 'bold',
              bgcolor: isCallBuySelected ? COLORS.buy : COLORS.buyBg,
              color: isCallBuySelected ? '#fff' : COLORS.buy,
              border: `1px solid ${COLORS.buy}`,
              '&:hover': { bgcolor: COLORS.buy, color: '#fff' },
            }}
          >
            B
          </Button>
          <Button
            onClick={() => onTradeClick(strike, 'call', 'sell', callData)}
            sx={{
              minWidth: 28,
              px: 0.5,
              py: 0.25,
              fontSize: '0.7rem',
              fontWeight: 'bold',
              bgcolor: isCallSellSelected ? COLORS.sell : COLORS.sellBg,
              color: isCallSellSelected ? '#fff' : COLORS.sell,
              border: `1px solid ${COLORS.sell}`,
              '&:hover': { bgcolor: COLORS.sell, color: '#fff' },
            }}
          >
            S
          </Button>
        </ButtonGroup>
      </TableCell>
      
      {/* Strike */}
      <TableCell 
        align="center" 
        sx={{ 
          fontWeight: 'bold',
          fontSize: '0.85rem',
          color: isAtm ? COLORS.atm : COLORS.text,
          bgcolor: 'rgba(255,255,255,0.02)',
          borderLeft: `1px solid ${COLORS.border}`,
          borderRight: `1px solid ${COLORS.border}`,
          borderBottom: `1px solid ${COLORS.border}`,
          py: 0.75,
        }}
      >
        {strike.toLocaleString()}
        {isAtm && (
          <Chip 
            label="ATM" 
            size="small" 
            sx={{ 
              ml: 0.5, 
              height: 16, 
              fontSize: '0.6rem',
              bgcolor: COLORS.atmBg,
              color: COLORS.atm,
            }} 
          />
        )}
      </TableCell>
      
      {/* IV */}
      <TableCell align="center" sx={{ color: COLORS.textSecondary, fontSize: '0.75rem', py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
        {putData.iv ? `${(putData.iv * 100).toFixed(1)}` : callData.iv ? `${(callData.iv * 100).toFixed(1)}` : '-'}
      </TableCell>
      
      {/* Put OI */}
      {showOi && (
        <TableCell align="center" sx={{ py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
          <Box sx={{ 
            height: 6, 
            bgcolor: COLORS.putOi, 
            borderRadius: 1,
            width: `${Math.min((putData.oi || 0) / 1000, 100)}%`,
            minWidth: putData.oi ? 4 : 0,
          }} />
        </TableCell>
      )}
      
      {/* B/S Buttons (Put) */}
      <TableCell align="center" sx={{ py: 0.5, borderBottom: `1px solid ${COLORS.border}` }}>
        <ButtonGroup size="small" sx={{ minWidth: 60 }}>
          <Button
            onClick={() => onTradeClick(strike, 'put', 'buy', putData)}
            sx={{
              minWidth: 28,
              px: 0.5,
              py: 0.25,
              fontSize: '0.7rem',
              fontWeight: 'bold',
              bgcolor: isPutBuySelected ? COLORS.buy : COLORS.buyBg,
              color: isPutBuySelected ? '#fff' : COLORS.buy,
              border: `1px solid ${COLORS.buy}`,
              '&:hover': { bgcolor: COLORS.buy, color: '#fff' },
            }}
          >
            B
          </Button>
          <Button
            onClick={() => onTradeClick(strike, 'put', 'sell', putData)}
            sx={{
              minWidth: 28,
              px: 0.5,
              py: 0.25,
              fontSize: '0.7rem',
              fontWeight: 'bold',
              bgcolor: isPutSellSelected ? COLORS.sell : COLORS.sellBg,
              color: isPutSellSelected ? '#fff' : COLORS.sell,
              border: `1px solid ${COLORS.sell}`,
              '&:hover': { bgcolor: COLORS.sell, color: '#fff' },
            }}
          >
            S
          </Button>
        </ButtonGroup>
      </TableCell>
      
      {/* Put LTP */}
      <TableCell align="left" sx={{ color: COLORS.text, fontSize: '0.8rem', py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
        {(putData.mark_price || putData.ltp)?.toFixed(2) || '-'}
      </TableCell>
      
      {/* Delta (Put) */}
      {showGreeks && (
        <TableCell align="center" sx={{ color: COLORS.textSecondary, fontSize: '0.75rem', py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
          {putData.delta ? putData.delta.toFixed(2) : '-'}
        </TableCell>
      )}
    </TableRow>
  );
};

/**
 * SlidingOptionsChainPanel Component
 */
export default function SlidingOptionsChainPanel({
  open,
  onClose,
  underlying = 'BTC',
  spotPrice,
  proposedTrades = [],
  onAddTrade,
  onRemoveTrade,
  selectedExpiry,
  onExpiryChange,
}) {
  // State
  const [expirations, setExpirations] = useState([]);
  const [chainData, setChainData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState(2); // 0=Straddles, 1=Strangles, 2=Strikes, 3=Futures
  const [showOi, setShowOi] = useState(false);
  const [showGreeks, setShowGreeks] = useState(false);
  const [displayMode, setDisplayMode] = useState('ltp'); // 'ltp', 'oi', 'greeks'
  
  // Fetch expirations when panel opens
  useEffect(() => {
    if (!open) return;
    
    const fetchExpirations = async () => {
      try {
        setLoading(true);
        setError(null);
        const result = await optionsChainAPI.getExpirations(underlying);
        setExpirations(result || []);
        
        // Auto-select first expiry if none
        if (!selectedExpiry && result?.length > 0) {
          onExpiryChange?.(result[0]);
        }
      } catch (err) {
        setError('Failed to load expiry dates');
      } finally {
        setLoading(false);
      }
    };
    
    fetchExpirations();
  }, [open, underlying]);
  
  // Fetch chain data when expiry changes
  useEffect(() => {
    if (!open || !selectedExpiry) return;
    
    const fetchChain = async () => {
      try {
        setLoading(true);
        setError(null);
        const result = await optionsChainAPI.getChainData(underlying, selectedExpiry);
        setChainData(result);
      } catch (err) {
        setError('Failed to load options chain');
        setChainData(null);
      } finally {
        setLoading(false);
      }
    };
    
    fetchChain();
  }, [open, underlying, selectedExpiry]);
  
  // Find ATM strike
  const atmStrike = useMemo(() => {
    if (chainData?.atm_strike) return chainData.atm_strike;
    const effectiveSpot = chainData?.spot_price || spotPrice;
    if (!effectiveSpot || !chainData?.chain) return null;
    
    const strikes = chainData.chain.map(s => parseFloat(s.strike));
    if (strikes.length === 0) return null;
    
    return strikes.reduce((closest, strike) => 
      Math.abs(strike - effectiveSpot) < Math.abs(closest - effectiveSpot) ? strike : closest
    );
  }, [spotPrice, chainData]);
  
  // Handle trade click
  const handleTradeClick = useCallback((strike, type, side, optionData) => {
    const existingTrade = proposedTrades.find(t => 
      t.strike === strike && t.type === type && t.side === side
    );
    
    if (existingTrade) {
      onRemoveTrade?.(existingTrade);
    } else {
      // Remove opposite side if selected
      const oppositeSide = side === 'buy' ? 'sell' : 'buy';
      const oppositeTrade = proposedTrades.find(t => 
        t.strike === strike && t.type === type && t.side === oppositeSide
      );
      if (oppositeTrade) {
        onRemoveTrade?.(oppositeTrade);
      }
      
      // Convert expiry format (DDMMYYYY -> DDMMYY)
      const expiryShort = selectedExpiry?.length === 8 
        ? selectedExpiry.slice(0, 4) + selectedExpiry.slice(6, 8)
        : selectedExpiry;
      
      const symbol = `${type === 'call' ? 'C' : 'P'}-${underlying}-${strike}-${expiryShort}`;
      const price = optionData?.mark_price || optionData?.ltp || 0;
      
      onAddTrade?.({
        symbol,
        strike,
        type,
        side,
        quantity: 1,
        ltp: price,
        premium: price,
        iv: optionData?.iv || 0,
        delta: optionData?.delta || 0,
        theta: optionData?.theta || 0,
        vega: optionData?.vega || 0,
        expiry: selectedExpiry,
        spotPrice: chainData?.spot_price || spotPrice,
      });
    }
  }, [proposedTrades, underlying, selectedExpiry, spotPrice, chainData, onAddTrade, onRemoveTrade]);
  
  // Clear all trades
  const handleClearAll = useCallback(() => {
    proposedTrades.forEach(t => onRemoveTrade?.(t));
  }, [proposedTrades, onRemoveTrade]);
  
  // Toggle display mode
  const handleDisplayModeChange = (mode) => {
    if (mode === 'oi') {
      setShowOi(!showOi);
    } else if (mode === 'greeks') {
      setShowGreeks(!showGreeks);
    }
    setDisplayMode(mode);
  };

  return (
    <Drawer
      anchor="left"
      open={open}
      onClose={onClose}
      PaperProps={{
        sx: {
          width: PANEL_WIDTH,
          bgcolor: COLORS.background,
          borderRight: `1px solid ${COLORS.border}`,
        },
      }}
      ModalProps={{
        BackdropProps: {
          sx: { bgcolor: 'rgba(0,0,0,0.3)' },
        },
      }}
    >
      {/* Header */}
      <Box sx={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between',
        p: 1.5,
        borderBottom: `1px solid ${COLORS.border}`,
        bgcolor: COLORS.cardBg,
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="subtitle1" sx={{ color: COLORS.text, fontWeight: 600 }}>
            {underlying} {spotPrice?.toLocaleString() || ''}
          </Typography>
          <Chip 
            label={`${((chainData?.spot_price || spotPrice) ? ((chainData?.spot_price - spotPrice) / spotPrice * 100).toFixed(2) : '0.00')}%`}
            size="small"
            sx={{ 
              bgcolor: 'rgba(239, 68, 68, 0.2)', 
              color: COLORS.sell,
              fontSize: '0.7rem',
              height: 20,
            }}
          />
        </Box>
        
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Chip label="Info" size="small" variant="outlined" sx={{ borderColor: COLORS.primary, color: COLORS.primary, height: 24 }} />
          <IconButton size="small" sx={{ color: COLORS.textSecondary }}>
            <SettingsIcon fontSize="small" />
          </IconButton>
          <IconButton size="small" onClick={onClose} sx={{ color: COLORS.textSecondary }}>
            <CloseIcon fontSize="small" />
          </IconButton>
        </Box>
      </Box>
      
      {/* Tabs */}
      <Box sx={{ borderBottom: `1px solid ${COLORS.border}`, bgcolor: COLORS.cardBg }}>
        <Tabs 
          value={activeTab} 
          onChange={(e, v) => setActiveTab(v)}
          variant="fullWidth"
          sx={{
            minHeight: 36,
            '& .MuiTab-root': { 
              color: COLORS.textSecondary, 
              textTransform: 'none',
              minHeight: 36,
              fontSize: '0.85rem',
            },
            '& .Mui-selected': { color: COLORS.text },
            '& .MuiTabs-indicator': { bgcolor: COLORS.primary },
          }}
        >
          <Tab label="Straddles" />
          <Tab label="Strangles" />
          <Tab label="Strikes" />
          <Tab label="Futures" />
        </Tabs>
      </Box>
      
      {/* Filters Row */}
      <Box sx={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between',
        p: 1,
        borderBottom: `1px solid ${COLORS.border}`,
      }}>
        {/* Expiry Selector */}
        <FormControl size="small" sx={{ minWidth: 80 }}>
          <Select
            value={selectedExpiry || ''}
            onChange={(e) => onExpiryChange?.(e.target.value)}
            sx={{ 
              color: COLORS.text,
              bgcolor: COLORS.primary,
              borderRadius: 1,
              '& .MuiSelect-select': { py: 0.5, px: 1.5, fontSize: '0.8rem' },
              '& .MuiOutlinedInput-notchedOutline': { border: 'none' },
            }}
          >
            {expirations.map(exp => (
              <MenuItem key={exp} value={exp}>{formatExpiry(exp)}</MenuItem>
            ))}
          </Select>
        </FormControl>
        
        {/* Display Mode Toggles */}
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Chip 
            label="LTP" 
            size="small"
            onClick={() => handleDisplayModeChange('ltp')}
            sx={{ 
              bgcolor: displayMode === 'ltp' ? COLORS.primary : 'transparent',
              color: displayMode === 'ltp' ? '#fff' : COLORS.textSecondary,
              border: `1px solid ${COLORS.border}`,
              fontSize: '0.7rem',
              height: 24,
              cursor: 'pointer',
            }}
          />
          <Chip 
            label="OI" 
            size="small"
            onClick={() => handleDisplayModeChange('oi')}
            sx={{ 
              bgcolor: showOi ? COLORS.primary : 'transparent',
              color: showOi ? '#fff' : COLORS.textSecondary,
              border: `1px solid ${COLORS.border}`,
              fontSize: '0.7rem',
              height: 24,
              cursor: 'pointer',
            }}
          />
          <Chip 
            label="Greeks" 
            size="small"
            onClick={() => handleDisplayModeChange('greeks')}
            sx={{ 
              bgcolor: showGreeks ? COLORS.primary : 'transparent',
              color: showGreeks ? '#fff' : COLORS.textSecondary,
              border: `1px solid ${COLORS.border}`,
              fontSize: '0.7rem',
              height: 24,
              cursor: 'pointer',
            }}
          />
        </Box>
      </Box>
      
      {/* Chain Table */}
      <Box sx={{ flex: 1, overflow: 'auto' }}>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 200 }}>
            <CircularProgress size={32} />
          </Box>
        ) : error ? (
          <Box sx={{ p: 2, textAlign: 'center' }}>
            <Typography color="error">{error}</Typography>
          </Box>
        ) : (
          <TableContainer>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  {showGreeks && (
                    <TableCell align="center" sx={{ bgcolor: COLORS.cardBg, color: COLORS.textSecondary, fontSize: '0.7rem', py: 0.5, borderBottom: `1px solid ${COLORS.border}` }}>
                      Delta
                    </TableCell>
                  )}
                  <TableCell align="right" sx={{ bgcolor: COLORS.cardBg, color: COLORS.buy, fontSize: '0.7rem', py: 0.5, borderBottom: `1px solid ${COLORS.border}` }}>
                    Call LTP
                  </TableCell>
                  {showOi && (
                    <TableCell align="center" sx={{ bgcolor: COLORS.cardBg, color: COLORS.callOi, fontSize: '0.7rem', py: 0.5, borderBottom: `1px solid ${COLORS.border}` }}>
                      Call OI
                    </TableCell>
                  )}
                  <TableCell align="center" sx={{ bgcolor: COLORS.cardBg, color: COLORS.buy, fontSize: '0.7rem', py: 0.5, borderBottom: `1px solid ${COLORS.border}` }}>
                    Call
                  </TableCell>
                  <TableCell align="center" sx={{ bgcolor: COLORS.cardBg, color: COLORS.text, fontSize: '0.75rem', fontWeight: 'bold', py: 0.5, borderBottom: `1px solid ${COLORS.border}` }}>
                    Strike
                  </TableCell>
                  <TableCell align="center" sx={{ bgcolor: COLORS.cardBg, color: COLORS.textSecondary, fontSize: '0.7rem', py: 0.5, borderBottom: `1px solid ${COLORS.border}` }}>
                    IV
                  </TableCell>
                  {showOi && (
                    <TableCell align="center" sx={{ bgcolor: COLORS.cardBg, color: COLORS.putOi, fontSize: '0.7rem', py: 0.5, borderBottom: `1px solid ${COLORS.border}` }}>
                      Put OI
                    </TableCell>
                  )}
                  <TableCell align="center" sx={{ bgcolor: COLORS.cardBg, color: COLORS.sell, fontSize: '0.7rem', py: 0.5, borderBottom: `1px solid ${COLORS.border}` }}>
                    Put
                  </TableCell>
                  <TableCell align="left" sx={{ bgcolor: COLORS.cardBg, color: COLORS.sell, fontSize: '0.7rem', py: 0.5, borderBottom: `1px solid ${COLORS.border}` }}>
                    Put LTP
                  </TableCell>
                  {showGreeks && (
                    <TableCell align="center" sx={{ bgcolor: COLORS.cardBg, color: COLORS.textSecondary, fontSize: '0.7rem', py: 0.5, borderBottom: `1px solid ${COLORS.border}` }}>
                      Delta
                    </TableCell>
                  )}
                </TableRow>
              </TableHead>
              <TableBody>
                {chainData?.chain?.map((strikeData) => {
                  const strike = parseFloat(strikeData.strike);
                  const isAtm = strike === atmStrike;
                  
                  return (
                    <ChainRow
                      key={strike}
                      strikeData={strikeData}
                      isAtm={isAtm}
                      spotPrice={chainData?.spot_price || spotPrice}
                      proposedTrades={proposedTrades}
                      onTradeClick={handleTradeClick}
                      showOi={showOi}
                      showGreeks={showGreeks}
                    />
                  );
                })}
                
                {(!chainData?.chain || chainData.chain.length === 0) && (
                  <TableRow>
                    <TableCell colSpan={showGreeks ? 10 : showOi ? 8 : 6} align="center" sx={{ py: 4, color: COLORS.textSecondary }}>
                      {selectedExpiry ? 'No options data available' : 'Select an expiry date'}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Box>
      
      {/* Footer */}
      <Box sx={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between',
        p: 1.5,
        borderTop: `1px solid ${COLORS.border}`,
        bgcolor: COLORS.cardBg,
      }}>
        <Button 
          variant="outlined"
          size="small"
          onClick={handleClearAll}
          disabled={proposedTrades.length === 0}
          sx={{ 
            color: COLORS.textSecondary, 
            borderColor: COLORS.border,
            '&:hover': { borderColor: COLORS.textSecondary },
          }}
        >
          Clear All
        </Button>
        
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {proposedTrades.length > 0 && (
            <Chip 
              label={`${proposedTrades.length} selected`}
              size="small"
              sx={{ bgcolor: COLORS.primary, color: '#fff' }}
            />
          )}
          <Button 
            variant="contained"
            size="small"
            onClick={onClose}
            sx={{ 
              bgcolor: COLORS.primary,
              '&:hover': { bgcolor: '#2563eb' },
            }}
          >
            Done
          </Button>
        </Box>
      </Box>
      
      {/* Collapse/Expand Handle */}
      <Box 
        sx={{ 
          position: 'absolute',
          top: '50%',
          right: -24,
          transform: 'translateY(-50%)',
          bgcolor: COLORS.cardBg,
          border: `1px solid ${COLORS.border}`,
          borderLeft: 'none',
          borderRadius: '0 4px 4px 0',
          px: 0.5,
          py: 2,
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          '&:hover': { bgcolor: 'rgba(255,255,255,0.05)' },
        }}
        onClick={onClose}
      >
        <Typography 
          sx={{ 
            writingMode: 'vertical-rl',
            textOrientation: 'mixed',
            fontSize: '0.7rem',
            color: COLORS.textSecondary,
          }}
        >
          Show Editor
        </Typography>
        <ChevronRightIcon sx={{ color: COLORS.textSecondary, fontSize: 16 }} />
      </Box>
    </Drawer>
  );
}
