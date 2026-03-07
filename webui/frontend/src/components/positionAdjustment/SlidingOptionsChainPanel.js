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
 * Chain Row Component - Sensibull Style with per-row quantity selector
 */
const ChainRow = ({
  strikeData,
  isAtm,
  spotPrice,
  proposedTrades,
  onTradeClick,
  showOi,
  showGreeks,
  tradeQuantities,
  onQuantityChange,
}) => {
  const strike = parseFloat(strikeData.strike);
  const callData = strikeData.call || {};
  const putData = strikeData.put || {};

  // No max restriction on quantity — free-text input

  // Get current quantities for this strike
  const callQty = tradeQuantities?.[`${strike}-call`] || 1;
  const putQty = tradeQuantities?.[`${strike}-put`] || 1;

  // Check if trades are selected
  const isCallBuySelected = proposedTrades.some(t => t.strike === strike && t.type === 'call' && t.side === 'buy');
  const isCallSellSelected = proposedTrades.some(t => t.strike === strike && t.type === 'call' && t.side === 'sell');
  const isPutBuySelected = proposedTrades.some(t => t.strike === strike && t.type === 'put' && t.side === 'buy');
  const isPutSellSelected = proposedTrades.some(t => t.strike === strike && t.type === 'put' && t.side === 'sell');

  const isCallSelected = isCallBuySelected || isCallSellSelected;
  const isPutSelected = isPutBuySelected || isPutSellSelected;

  return (
    <>
      <TableRow
        sx={{
          bgcolor: isAtm ? COLORS.atmBg : 'transparent',
          '&:hover': { bgcolor: 'rgba(255,255,255,0.03)' },
        }}
      >
        {/* Delta (Call) */}
        {showGreeks && (
          <TableCell align="center" sx={{ color: COLORS.textSecondary, fontSize: '0.8rem', py: 0.75, px: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
            {callData.delta ? callData.delta.toFixed(2) : '-'}
          </TableCell>
        )}

        {/* Call LTP */}
        <TableCell align="right" sx={{ color: COLORS.text, fontSize: '0.85rem', py: 0.75, px: 1, borderBottom: `1px solid ${COLORS.border}` }}>
          {(callData.mark_price || callData.ltp)?.toFixed(2) || '-'}
        </TableCell>

        {/* Call OI bar */}
        {showOi && (
          <TableCell align="center" sx={{ py: 0.75, px: 0.75, width: 60, borderBottom: `1px solid ${COLORS.border}` }}>
            <Box sx={{
              height: 6,
              bgcolor: COLORS.callOi,
              borderRadius: 0.5,
              width: `${Math.min((callData.oi || 0) / 1000, 100)}%`,
              minWidth: callData.oi ? 4 : 0,
              ml: 'auto',
            }} />
          </TableCell>
        )}

        {/* Call B/S Buttons */}
        <TableCell align="center" sx={{ py: 0.75, px: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
          <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'center' }}>
            <Box
              onClick={() => onTradeClick(strike, 'call', 'buy', callData, callQty)}
              sx={{
                width: 26,
                height: 26,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.75rem',
                fontWeight: 'bold',
                borderRadius: 0.5,
                cursor: 'pointer',
                bgcolor: isCallBuySelected ? COLORS.buy : 'transparent',
                color: isCallBuySelected ? '#fff' : COLORS.buy,
                border: `1px solid ${COLORS.buy}`,
                '&:hover': { bgcolor: COLORS.buy, color: '#fff' },
              }}
            >
              B
            </Box>
            <Box
              onClick={() => onTradeClick(strike, 'call', 'sell', callData, callQty)}
              sx={{
                width: 26,
                height: 26,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.75rem',
                fontWeight: 'bold',
                borderRadius: 0.5,
                cursor: 'pointer',
                bgcolor: isCallSellSelected ? COLORS.sell : 'transparent',
                color: isCallSellSelected ? '#fff' : COLORS.sell,
                border: `1px solid ${COLORS.sell}`,
                '&:hover': { bgcolor: COLORS.sell, color: '#fff' },
              }}
            >
              S
            </Box>
          </Box>
        </TableCell>

        {/* Strike */}
        <TableCell
          align="center"
          sx={{
            fontWeight: 600,
            fontSize: '0.9rem',
            color: isAtm ? COLORS.atm : COLORS.text,
            bgcolor: 'rgba(255,255,255,0.03)',
            borderLeft: `1px solid ${COLORS.border}`,
            borderRight: `1px solid ${COLORS.border}`,
            borderBottom: `1px solid ${COLORS.border}`,
            py: 0.75,
            px: 1.5,
            position: 'relative',
          }}
        >
          {strike.toLocaleString()}
          {isAtm && (
            <Box
              component="span"
              sx={{
                ml: 0.5,
                fontSize: '0.6rem',
                color: COLORS.atm,
                verticalAlign: 'super',
              }}
            >
              ATM
            </Box>
          )}
        </TableCell>

        {/* IV */}
        <TableCell align="center" sx={{ color: COLORS.textSecondary, fontSize: '0.8rem', py: 0.75, px: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
          {putData.iv ? `${(putData.iv * 100).toFixed(1)}` : callData.iv ? `${(callData.iv * 100).toFixed(1)}` : '-'}
        </TableCell>

        {/* Put OI bar */}
        {showOi && (
          <TableCell align="center" sx={{ py: 0.75, px: 0.75, width: 60, borderBottom: `1px solid ${COLORS.border}` }}>
            <Box sx={{
              height: 6,
              bgcolor: COLORS.putOi,
              borderRadius: 0.5,
              width: `${Math.min((putData.oi || 0) / 1000, 100)}%`,
              minWidth: putData.oi ? 4 : 0,
            }} />
          </TableCell>
        )}

        {/* Put B/S Buttons */}
        <TableCell align="center" sx={{ py: 0.75, px: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
          <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'center' }}>
            <Box
              onClick={() => onTradeClick(strike, 'put', 'buy', putData, putQty)}
              sx={{
                width: 26,
                height: 26,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.75rem',
                fontWeight: 'bold',
                borderRadius: 0.5,
                cursor: 'pointer',
                bgcolor: isPutBuySelected ? COLORS.buy : 'transparent',
                color: isPutBuySelected ? '#fff' : COLORS.buy,
                border: `1px solid ${COLORS.buy}`,
                '&:hover': { bgcolor: COLORS.buy, color: '#fff' },
              }}
            >
              B
            </Box>
            <Box
              onClick={() => onTradeClick(strike, 'put', 'sell', putData, putQty)}
              sx={{
                width: 26,
                height: 26,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.75rem',
                fontWeight: 'bold',
                borderRadius: 0.5,
                cursor: 'pointer',
                bgcolor: isPutSellSelected ? COLORS.sell : 'transparent',
                color: isPutSellSelected ? '#fff' : COLORS.sell,
                border: `1px solid ${COLORS.sell}`,
                '&:hover': { bgcolor: COLORS.sell, color: '#fff' },
              }}
            >
              S
            </Box>
          </Box>
        </TableCell>

        {/* Put LTP */}
        <TableCell align="left" sx={{ color: COLORS.text, fontSize: '0.85rem', py: 0.75, px: 1, borderBottom: `1px solid ${COLORS.border}` }}>
          {(putData.mark_price || putData.ltp)?.toFixed(2) || '-'}
        </TableCell>

        {/* Delta (Put) */}
        {showGreeks && (
          <TableCell align="center" sx={{ color: COLORS.textSecondary, fontSize: '0.8rem', py: 0.75, px: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
            {putData.delta ? putData.delta.toFixed(2) : '-'}
          </TableCell>
        )}
      </TableRow>

      {/* Quantity selector row - appears when call or put is selected */}
      {(isCallSelected || isPutSelected) && (
        <TableRow sx={{ bgcolor: 'rgba(255,255,255,0.02)' }}>
          <TableCell
            colSpan={showGreeks ? (showOi ? 10 : 8) : (showOi ? 8 : 6)}
            sx={{ py: 0.5, px: 1, borderBottom: `1px solid ${COLORS.border}` }}
          >
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              {/* Call Quantity Selector */}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flex: 1, justifyContent: 'flex-end', pr: 2 }}>
                {isCallSelected && (
                  <>
                    <Typography sx={{ fontSize: '0.7rem', color: COLORS.textSecondary }}>Qty</Typography>
                    <input
                      type="number"
                      value={callQty}
                      min="1"
                      onChange={(e) => {
                        e.stopPropagation();
                        const val = parseInt(e.target.value) || 1;
                        onQuantityChange(strike, 'call', Math.max(1, val));
                      }}
                      onClick={(e) => e.stopPropagation()}
                      style={{
                        height: 24,
                        width: 60,
                        fontSize: '0.75rem',
                        color: COLORS.text,
                        backgroundColor: COLORS.cardBg,
                        border: `1px solid ${COLORS.border}`,
                        borderRadius: 4,
                        padding: '2px 6px',
                        textAlign: 'center',
                        outline: 'none',
                      }}
                    />
                  </>
                )}
              </Box>

              {/* Strike spacer */}
              <Box sx={{ width: 70 }} />

              {/* Put Quantity Selector */}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flex: 1, pl: 2 }}>
                {isPutSelected && (
                  <>
                    <input
                      type="number"
                      value={putQty}
                      min="1"
                      onChange={(e) => {
                        e.stopPropagation();
                        const val = parseInt(e.target.value) || 1;
                        onQuantityChange(strike, 'put', Math.max(1, val));
                      }}
                      onClick={(e) => e.stopPropagation()}
                      style={{
                        height: 24,
                        width: 60,
                        fontSize: '0.75rem',
                        color: COLORS.text,
                        backgroundColor: COLORS.cardBg,
                        border: `1px solid ${COLORS.border}`,
                        borderRadius: 4,
                        padding: '2px 6px',
                        textAlign: 'center',
                        outline: 'none',
                      }}
                    />
                    <Typography sx={{ fontSize: '0.7rem', color: COLORS.textSecondary }}>Qty</Typography>
                  </>
                )}
              </Box>
            </Box>
          </TableCell>
        </TableRow>
      )}
    </>
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
  inline = false,  // NEW: Render inline without Drawer wrapper
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
  const [tradeQuantities, setTradeQuantities] = useState({}); // Per-strike quantities: { "78200-call": 30, "78200-put": 10 }

  // Convert expiry from DDMMYY to DDMMYYYY for API
  const convertExpiryToAPI = useCallback((expiry) => {
    if (!expiry) return expiry;
    // If already 8 digits, it's DDMMYYYY format
    if (expiry.length === 8) return expiry;
    // If 6 digits (DDMMYY), convert to DDMMYYYY
    if (expiry.length === 6) {
      const year = expiry.slice(4, 6);
      const fullYear = parseInt(year) > 50 ? `19${year}` : `20${year}`;
      return expiry.slice(0, 4) + fullYear;
    }
    return expiry;
  }, []);

  // Fetch expirations when panel opens
  useEffect(() => {
    if (!open) return;

    const fetchExpirations = async () => {
      try {
        setLoading(true);
        setError(null);
        const result = await optionsChainAPI.getExpirations(underlying);
        setExpirations(result || []);

        // Auto-select first expiry if none selected
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
        // Convert expiry format for API (DDMMYY -> DDMMYYYY)
        const apiExpiry = convertExpiryToAPI(selectedExpiry);
        const result = await optionsChainAPI.getChainData(underlying, apiExpiry);
        setChainData(result);
      } catch (err) {
        console.error('[SlidingOptionsChainPanel] fetchChain error:', err);
        setError('Failed to load options chain');
        setChainData(null);
      } finally {
        setLoading(false);
      }
    };

    fetchChain();
  }, [open, underlying, selectedExpiry, convertExpiryToAPI]);

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

  // Handle quantity change for a specific strike/type
  const handleQuantityChange = useCallback((strike, type, quantity) => {
    const key = `${strike}-${type}`;
    setTradeQuantities(prev => ({ ...prev, [key]: quantity }));

    // Update existing trade if it exists
    const existingTrade = proposedTrades.find(t => t.strike === strike && t.type === type);
    if (existingTrade) {
      // Remove old trade and add with new quantity
      onRemoveTrade?.(existingTrade);
      onAddTrade?.({
        ...existingTrade,
        quantity,
      });
    }
  }, [proposedTrades, onAddTrade, onRemoveTrade]);

  // Handle trade click - now accepts quantity from row
  const handleTradeClick = useCallback((strike, type, side, optionData, quantity = 1) => {
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

      // Use the converted expiry format for API
      const apiExpiry = convertExpiryToAPI(selectedExpiry);

      // Convert expiry format (DDMMYYYY -> DDMMYY for symbol)
      const expiryShort = apiExpiry?.length === 8
        ? apiExpiry.slice(0, 4) + apiExpiry.slice(6, 8)
        : selectedExpiry;

      const symbol = `${type === 'call' ? 'C' : 'P'}-${underlying}-${strike}-${expiryShort}`;
      const price = optionData?.mark_price || optionData?.ltp || 0;

      // Get quantity from tradeQuantities or use passed quantity
      const key = `${strike}-${type}`;
      const tradeQty = tradeQuantities[key] || quantity;

      onAddTrade?.({
        symbol,
        strike,
        type,
        side,
        quantity: tradeQty,
        ltp: price,
        premium: price,
        iv: optionData?.iv || 0,
        delta: optionData?.delta || 0,
        theta: optionData?.theta || 0,
        vega: optionData?.vega || 0,
        expiry: apiExpiry,
        spotPrice: chainData?.spot_price || spotPrice,
      });
    }
  }, [proposedTrades, underlying, selectedExpiry, spotPrice, chainData, tradeQuantities, onAddTrade, onRemoveTrade, convertExpiryToAPI]);

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

  // Inner content to be rendered in both modes
  const panelContent = (
    <Box sx={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      bgcolor: COLORS.background,
    }}>
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

      {/* Expiry Selector, Quantity Selector and Display Mode */}
      <Box sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        p: 1,
        borderBottom: `1px solid ${COLORS.border}`,
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <FormControl size="small" sx={{ minWidth: 80 }}>
            <Select
              value={selectedExpiry || ''}
              onChange={(e) => onExpiryChange?.(e.target.value)}
              displayEmpty
              sx={{
                color: COLORS.text,
                bgcolor: COLORS.primary,
                borderRadius: 1,
                '& .MuiSelect-icon': { color: COLORS.text },
                '& fieldset': { border: 'none' },
                fontSize: '0.8rem',
                height: 28,
              }}
            >
              {expirations.map((exp) => (
                <MenuItem key={exp} value={exp} sx={{ fontSize: '0.8rem' }}>
                  {formatExpiry(exp)}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>

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
                    <TableCell align="center" sx={{ bgcolor: COLORS.cardBg, color: COLORS.textSecondary, fontSize: '0.8rem', py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
                      Delta
                    </TableCell>
                  )}
                  <TableCell align="right" sx={{ bgcolor: COLORS.cardBg, color: COLORS.buy, fontSize: '0.8rem', py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
                    Call LTP
                  </TableCell>
                  {showOi && (
                    <TableCell align="center" sx={{ bgcolor: COLORS.cardBg, color: COLORS.callOi, fontSize: '0.8rem', py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
                      Call OI
                    </TableCell>
                  )}
                  <TableCell align="center" sx={{ bgcolor: COLORS.cardBg, color: COLORS.buy, fontSize: '0.8rem', py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
                    Call
                  </TableCell>
                  <TableCell align="center" sx={{ bgcolor: COLORS.cardBg, color: COLORS.text, fontSize: '0.85rem', fontWeight: 'bold', py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
                    Strike
                  </TableCell>
                  <TableCell align="center" sx={{ bgcolor: COLORS.cardBg, color: COLORS.textSecondary, fontSize: '0.8rem', py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
                    IV
                  </TableCell>
                  {showOi && (
                    <TableCell align="center" sx={{ bgcolor: COLORS.cardBg, color: COLORS.putOi, fontSize: '0.8rem', py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
                      Put OI
                    </TableCell>
                  )}
                  <TableCell align="center" sx={{ bgcolor: COLORS.cardBg, color: COLORS.sell, fontSize: '0.8rem', py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
                    Put
                  </TableCell>
                  <TableCell align="left" sx={{ bgcolor: COLORS.cardBg, color: COLORS.sell, fontSize: '0.8rem', py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
                    Put LTP
                  </TableCell>
                  {showGreeks && (
                    <TableCell align="center" sx={{ bgcolor: COLORS.cardBg, color: COLORS.textSecondary, fontSize: '0.8rem', py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
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
                      tradeQuantities={tradeQuantities}
                      onQuantityChange={handleQuantityChange}
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
    </Box>
  );

  // If inline mode, render without Drawer wrapper
  if (inline) {
    return panelContent;
  }

  // Standard Drawer mode
  return (
    <Drawer
      anchor="left"
      open={open}
      onClose={onClose}
      variant="persistent"
      hideBackdrop={true}
      PaperProps={{
        sx: {
          width: PANEL_WIDTH,
          bgcolor: COLORS.background,
          borderRight: `1px solid ${COLORS.border}`,
          boxShadow: '4px 0 12px rgba(0, 0, 0, 0.5)',
          position: 'fixed',
          zIndex: 1300,
          height: '100%',
        },
      }}
      ModalProps={{
        keepMounted: false,
        disablePortal: false,
        hideBackdrop: true,
        style: { position: 'absolute' },
      }}
      SlideProps={{
        timeout: 300,
      }}
    >
      {panelContent}

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
