/**
 * Strategy Builder Panel
 * ======================
 * Floating panel for building custom strategies from Options Chain.
 * Like Sensibull's strategy builder - shows selected legs, payoff preview, and execute button.
 *
 * Features:
 * - Shows all selected legs with B/S indicator
 * - Adjustable quantity per leg
 * - Real-time premium calculation
 * - Simple payoff graph preview
 * - One-click execute
 *
 * Created: January 12, 2026
 */

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  IconButton,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Select,
  MenuItem,
  TextField,
  Chip,
  Divider,
  Alert,
  CircularProgress,
  Collapse,
  Tooltip,
  Card,
  CardContent,
} from '@mui/material';
import {
  Delete as DeleteIcon,
  PlayArrow as ExecuteIcon,
  Clear as ClearIcon,
  ExpandMore as ExpandIcon,
  ExpandLess as CollapseIcon,
  TrendingUp as CallIcon,
  TrendingDown as PutIcon,
  Calculate as CalcIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  ReferenceLine,
  ResponsiveContainer,
  Area,
  ComposedChart,
} from 'recharts';

const API_BASE = '/api/options-strategy';

// Generate payoff data points
const generatePayoffData = (legs, spotPrice, range = 0.15) => {
  if (!legs || legs.length === 0 || !spotPrice) return [];

  const minPrice = spotPrice * (1 - range);
  const maxPrice = spotPrice * (1 + range);
  const step = (maxPrice - minPrice) / 50;

  const data = [];

  for (let price = minPrice; price <= maxPrice; price += step) {
    let totalPnL = 0;

    legs.forEach((leg) => {
      const strike = leg.strike;
      const premium = leg.premium || leg.ltp || 0;
      const qty = leg.quantity || 1;
      const isCall = leg.type === 'call';
      const isBuy = leg.side === 'buy';

      // Intrinsic value at expiry
      let intrinsic = 0;
      if (isCall) {
        intrinsic = Math.max(0, price - strike);
      } else {
        intrinsic = Math.max(0, strike - price);
      }

      // P&L = (Intrinsic - Premium) * quantity * direction
      const direction = isBuy ? 1 : -1;
      const pnl = (intrinsic - premium) * qty * direction;
      totalPnL += pnl;
    });

    data.push({
      price: Math.round(price),
      pnl: Math.round(totalPnL * 100) / 100,
    });
  }

  return data;
};

// Calculate max profit, max loss, breakeven
const calculateStrategyMetrics = (payoffData) => {
  if (!payoffData || payoffData.length === 0) {
    return { maxProfit: 0, maxLoss: 0, breakevens: [] };
  }

  const pnls = payoffData.map((d) => d.pnl);
  const maxProfit = Math.max(...pnls);
  const maxLoss = Math.min(...pnls);

  // Find breakeven points (where PnL crosses zero)
  const breakevens = [];
  for (let i = 1; i < payoffData.length; i++) {
    const prev = payoffData[i - 1].pnl;
    const curr = payoffData[i].pnl;
    if ((prev <= 0 && curr >= 0) || (prev >= 0 && curr <= 0)) {
      breakevens.push(payoffData[i].price);
    }
  }

  return { maxProfit, maxLoss, breakevens };
};

export default function StrategyBuilderPanel({
  legs = [],
  spotPrice,
  expiry,
  underlying = 'BTC',
  onUpdateLeg,
  onRemoveLeg,
  onClearAll,
  onExecute,
  loading = false,
  expanded: initialExpanded = true,
}) {
  const [expanded, setExpanded] = useState(initialExpanded);
  const [executing, setExecuting] = useState(false);
  const [strategyName, setStrategyName] = useState('My Custom Strategy');
  const [error, setError] = useState(null);

  // Calculate totals
  const totals = useMemo(() => {
    let netPremium = 0;
    let netDelta = 0;

    legs.forEach((leg) => {
      const premium = (leg.premium || leg.ltp || 0) * (leg.quantity || 1);
      const delta = (leg.delta || 0) * (leg.quantity || 1);

      if (leg.side === 'buy') {
        netPremium -= premium; // Paying premium (debit)
        netDelta += delta;
      } else {
        netPremium += premium; // Receiving premium (credit)
        netDelta -= delta;
      }
    });

    return {
      netPremium,
      netDelta,
      isCredit: netPremium > 0,
      legCount: legs.length,
    };
  }, [legs]);

  // Generate payoff chart data
  const payoffData = useMemo(() => {
    return generatePayoffData(legs, spotPrice);
  }, [legs, spotPrice]);

  // Calculate strategy metrics
  const metrics = useMemo(() => {
    return calculateStrategyMetrics(payoffData);
  }, [payoffData]);

  // Convert DDMMYYYY to YYMMDD format for API
  const convertExpiryFormat = (exp) => {
    // Validate input
    if (!exp) {
      console.error('Expiry is null or undefined');
      return null;
    }
    
    // Convert to string if needed
    const expStr = String(exp).trim();
    
    console.log('Converting expiry:', expStr);
    
    if (expStr.length !== 8) {
      console.error(`Invalid expiry length: ${expStr} (expected 8 characters, got ${expStr.length})`);
      return null;
    }
    
    // Validate it's all digits
    if (!/^\d{8}$/.test(expStr)) {
      console.error(`Expiry contains non-numeric characters: ${expStr}`);
      return null;
    }
    
    // DDMMYYYY -> YYMMDD
    const day = expStr.slice(0, 2);
    const month = expStr.slice(2, 4);
    const year = expStr.slice(6, 8); // Last 2 digits of year
    
    const result = `${year}${month}${day}`;
    
    console.log(`Converted ${expStr} (DDMMYYYY) -> ${result} (YYMMDD)`);
    
    // Validate result
    if (result.length !== 6 || isNaN(result)) {
      console.error(`Invalid expiry conversion result: ${result}`);
      return null;
    }
    
    return result;
  };

  // Calculate mid-price (average of bid and ask) for smart limit orders
  const calculateMidPrice = (leg) => {
    const bid = leg.bid || leg.best_bid_price || 0;
    const ask = leg.ask || leg.best_ask_price || 0;
    
    console.log(`  Calculating mid-price - Bid: ${bid}, Ask: ${ask}`);
    
    // If both bid and ask are available, use mid-price
    if (bid > 0 && ask > 0) {
      const mid = (bid + ask) / 2;
      console.log(`  Mid-price: ${mid}`);
      return mid;
    }
    
    // Fallback to mark price or LTP
    const fallback = leg.mark_price || leg.ltp || leg.premium || 0;
    console.log(`  Using fallback price: ${fallback}`);
    return fallback;
  };

  // Handle execute
  const handleExecute = async () => {
    if (legs.length === 0) return;

    setExecuting(true);
    setError(null); // Clear previous errors
    
    try {
      console.log('=== Starting Strategy Execution ===');
      console.log('Legs:', JSON.stringify(legs, null, 2));
      
      // Validate we have legs
      if (!legs || legs.length === 0) {
        throw new Error('No legs selected. Please add at least one leg.');
      }
      
      // Validate each leg has a symbol (format: C-BTC-90000-270226)
      for (let i = 0; i < legs.length; i++) {
        if (!legs[i].symbol) {
          throw new Error(`Leg ${i + 1} is missing a symbol. Please ensure all legs are properly selected from the options chain.`);
        }
      }
      
      // Extract expiry from first leg's symbol for backend validation
      // Symbol format: C-BTC-90000-270226 (last 6 digits are DDMMYY)
      let backendExpiry = expiry; // Use dropdown value if available
      
      if (!backendExpiry && legs[0]?.symbol) {
        // Extract from symbol: C-BTC-90000-270226 -> 270226
        const symbolParts = legs[0].symbol.split('-');
        const ddmmyy = symbolParts[symbolParts.length - 1]; // Last part is date
        
        if (ddmmyy && ddmmyy.length === 6) {
          // Convert DDMMYY to DDMMYYYY for backend
          const dd = ddmmyy.slice(0, 2);
          const mm = ddmmyy.slice(2, 4);
          const yy = ddmmyy.slice(4, 6);
          const yyyy = '20' + yy; // Assume 20xx century
          backendExpiry = dd + mm + yyyy; // DDMMYYYY
          console.log(`Extracted expiry from symbol: ${ddmmyy} -> ${backendExpiry}`);
        }
      }
      
      if (!backendExpiry) {
        throw new Error('Cannot determine expiry date. Please ensure legs are properly selected.');
      }

      // Format legs for API with limit orders at mid-price
      // Backend needs option_type/strike for tracking, Delta Exchange uses product_symbol
      const formattedLegs = legs.map((leg, index) => {
        console.log(`\n=== Processing leg ${index + 1} ===`);
        console.log(`  Full leg object:`, leg);
        console.log(`  Quantity value: leg.quantity = ${leg.quantity}`);
        console.log(`  Will send size = ${leg.quantity || 1}`);
        
        // Validate symbol exists (format: C-BTC-90000-270226)
        if (!leg.symbol) {
          const errorMsg = `Missing symbol for leg ${index + 1}`;
          console.error(errorMsg);
          throw new Error(errorMsg);
        }
        
        // Calculate mid-price for smart limit order
        const midPrice = calculateMidPrice(leg);
        
        // Round to 1 decimal place (standard for options on Delta Exchange)
        const limitPrice = Math.round(midPrice * 10) / 10;
        
        console.log(`  Pricing details:`, {
          symbol: leg.symbol,
          bid: leg.bid || leg.best_bid_price || 0,
          ask: leg.ask || leg.best_ask_price || 0,
          midPrice: midPrice,
          limitPrice: limitPrice,
        });
        
        // Backend expects: option_type, strike for tracking
        // Delta Exchange uses: product_symbol for orders
        const formattedLeg = {
          // Backend tracking fields
          option_type: leg.type,       // "call" or "put"
          strike: leg.strike,          // e.g., 90000
          // Delta Exchange order fields
          product_symbol: leg.symbol,  // e.g., "C-BTC-90000-270226"
          size: leg.quantity || 1,     // Use "size" not "quantity"
          side: leg.side,              // "buy" or "sell"
          order_type: 'limit_order',
          limit_price: limitPrice.toString(),
        };
        
        console.log(`  Final formatted leg:`, formattedLeg);
        return formattedLeg;
      });
      
      // Delta Exchange India: Send expiry for backend validation
      // Backend converts it internally, but actual orders use symbol format
      const payload = {
        name: strategyName,
        underlying,
        expiry: backendExpiry, // DDMMYYYY format for backend
        legs: formattedLegs,
      };
      
      console.log('Final payload:', JSON.stringify(payload, null, 2));

      // Call parent handler or API directly
      if (onExecute) {
        await onExecute(payload);
      }
    } catch (err) {
      console.error('Execution failed:', err);
      setError(err.message || 'Failed to execute strategy');
      // Also show alert for immediate feedback
      alert(err.message || 'Failed to execute strategy');
    } finally {
      setExecuting(false);
    }
  };

  // Format expiry for display
  const formatExpiry = (exp) => {
    if (!exp || exp.length !== 8) return exp;
    const day = exp.slice(0, 2);
    const month = exp.slice(2, 4);
    const months = [
      'Jan',
      'Feb',
      'Mar',
      'Apr',
      'May',
      'Jun',
      'Jul',
      'Aug',
      'Sep',
      'Oct',
      'Nov',
      'Dec',
    ];
    return `${day} ${months[parseInt(month) - 1]}`;
  };

  return (
    <Paper
      elevation={4}
      sx={{
        position: 'sticky',
        top: 16,
        maxHeight: 'calc(100vh - 32px)',
        overflow: 'auto',
        borderRadius: 2,
        border: '1px solid',
        borderColor: legs.length > 0 ? 'primary.main' : 'divider',
      }}
    >
      {/* Header */}
      <Box
        sx={{
          p: 2,
          bgcolor: 'background.paper',
          borderBottom: '1px solid',
          borderColor: 'divider',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: 'pointer',
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <CalcIcon color="primary" />
          <Typography variant="subtitle1" fontWeight="bold">
            New Strategy
          </Typography>
          {legs.length > 0 && (
            <Chip
              label={`${legs.length} leg${legs.length > 1 ? 's' : ''}`}
              size="small"
              color="primary"
            />
          )}
        </Box>
        <IconButton size="small">{expanded ? <CollapseIcon /> : <ExpandIcon />}</IconButton>
      </Box>

      <Collapse in={expanded}>
        {legs.length === 0 ? (
          /* Empty State */
          <Box sx={{ p: 3, textAlign: 'center' }}>
            <Box
              sx={{
                width: 60,
                height: 60,
                mx: 'auto',
                mb: 2,
                borderRadius: 2,
                bgcolor: 'action.hover',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Typography variant="h6">📋</Typography>
            </Box>
            <Typography color="text.secondary" gutterBottom>
              No Trades Added
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Click <strong>B</strong> (Buy) or <strong>S</strong> (Sell) on any strike to add legs
            </Typography>
          </Box>
        ) : (
          /* Legs Table */
          <Box sx={{ px: 1 }}>
            <TableContainer sx={{ maxHeight: 200 }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontSize: '0.7rem', py: 0.5 }}>B/S</TableCell>
                    <TableCell sx={{ fontSize: '0.7rem', py: 0.5 }}>Expiry</TableCell>
                    <TableCell sx={{ fontSize: '0.7rem', py: 0.5 }}>Strike</TableCell>
                    <TableCell sx={{ fontSize: '0.7rem', py: 0.5 }}>Type</TableCell>
                    <TableCell sx={{ fontSize: '0.7rem', py: 0.5 }}>Qty</TableCell>
                    <TableCell sx={{ fontSize: '0.7rem', py: 0.5 }}>Price</TableCell>
                    <TableCell sx={{ fontSize: '0.7rem', py: 0.5, width: 30 }}></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {legs.map((leg, idx) => (
                    <TableRow key={`${leg.symbol}-${leg.side}-${idx}`}>
                      {/* Buy/Sell */}
                      <TableCell sx={{ py: 0.5 }}>
                        <Chip
                          label={leg.side === 'buy' ? 'B' : 'S'}
                          size="small"
                          color={leg.side === 'buy' ? 'primary' : 'error'}
                          sx={{
                            minWidth: 24,
                            height: 20,
                            '& .MuiChip-label': { px: 0.5, fontSize: '0.65rem' },
                          }}
                        />
                      </TableCell>

                      {/* Expiry */}
                      <TableCell sx={{ py: 0.5, fontSize: '0.75rem' }}>
                        {formatExpiry(leg.expiry || expiry)}
                      </TableCell>

                      {/* Strike */}
                      <TableCell sx={{ py: 0.5, fontSize: '0.75rem', fontWeight: 'bold' }}>
                        {leg.strike?.toLocaleString()}
                      </TableCell>

                      {/* Type */}
                      <TableCell sx={{ py: 0.5 }}>
                        <Chip
                          label={leg.type === 'call' ? 'CE' : 'PE'}
                          size="small"
                          sx={{
                            height: 18,
                            bgcolor: leg.type === 'call' ? 'success.dark' : 'error.dark',
                            color: 'white',
                            '& .MuiChip-label': { px: 0.5, fontSize: '0.6rem' },
                          }}
                        />
                      </TableCell>

                      {/* Quantity */}
                      <TableCell sx={{ py: 0.5, px: 0.5 }}>
                        <Select
                          value={leg.quantity || 1}
                          onChange={(e) =>
                            onUpdateLeg && onUpdateLeg(idx, 'quantity', e.target.value)
                          }
                          size="small"
                          sx={{
                            minWidth: 50,
                            '& .MuiSelect-select': { py: 0.25, fontSize: '0.75rem' },
                          }}
                        >
                          {[1, 2, 3, 4, 5, 10, 20, 50].map((q) => (
                            <MenuItem key={q} value={q}>
                              {q}
                            </MenuItem>
                          ))}
                        </Select>
                      </TableCell>

                      {/* Price */}
                      <TableCell sx={{ py: 0.5, fontSize: '0.75rem' }}>
                        {(() => {
                          const bid = leg.bid || leg.best_bid_price || 0;
                          const ask = leg.ask || leg.best_ask_price || 0;
                          const midPrice = bid > 0 && ask > 0 ? (bid + ask) / 2 : (leg.premium || leg.ltp || 0);
                          return (
                            <Tooltip title={`Bid: ${bid.toFixed(1)} | Ask: ${ask.toFixed(1)} | Mid: ${midPrice.toFixed(1)}`}>
                              <span style={{ cursor: 'help', borderBottom: '1px dotted #666' }}>
                                {midPrice.toFixed(1)}
                              </span>
                            </Tooltip>
                          );
                        })()}
                      </TableCell>

                      {/* Delete */}
                      <TableCell sx={{ py: 0.5, px: 0 }}>
                        <IconButton
                          size="small"
                          onClick={() => onRemoveLeg && onRemoveLeg(idx)}
                          sx={{ p: 0.25 }}
                        >
                          <DeleteIcon sx={{ fontSize: 16 }} />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>

            {/* Clear All */}
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', py: 0.5, px: 1 }}>
              <Button
                size="small"
                color="inherit"
                onClick={onClearAll}
                startIcon={<ClearIcon sx={{ fontSize: 14 }} />}
                sx={{ fontSize: '0.7rem' }}
              >
                Clear All
              </Button>
            </Box>
          </Box>
        )}

        {/* Payoff Chart */}
        {legs.length > 0 && payoffData.length > 0 && (
          <Box sx={{ px: 2, py: 1 }}>
            <Divider sx={{ mb: 1 }} />
            <Typography variant="caption" color="text.secondary" gutterBottom>
              Payoff at Expiry
            </Typography>
            <Box sx={{ height: 120 }}>
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={payoffData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                  <XAxis
                    dataKey="price"
                    tick={{ fontSize: 9 }}
                    tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
                  />
                  <YAxis
                    tick={{ fontSize: 9 }}
                    tickFormatter={(v) => (v >= 0 ? `+${v}` : v)}
                    width={35}
                  />
                  <ReferenceLine y={0} stroke="#666" strokeDasharray="3 3" />
                  {spotPrice && (
                    <ReferenceLine
                      x={Math.round(spotPrice)}
                      stroke="#2196f3"
                      strokeDasharray="3 3"
                      label={{ value: 'Spot', fontSize: 8, fill: '#2196f3' }}
                    />
                  )}
                  <Area type="monotone" dataKey="pnl" fill="url(#colorPnl)" stroke="none" />
                  <Line
                    type="monotone"
                    dataKey="pnl"
                    stroke="#4caf50"
                    strokeWidth={2}
                    dot={false}
                  />
                  <defs>
                    <linearGradient id="colorPnl" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#4caf50" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#f44336" stopOpacity={0.3} />
                    </linearGradient>
                  </defs>
                </ComposedChart>
              </ResponsiveContainer>
            </Box>

            {/* Metrics */}
            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', mt: 1 }}>
              <Tooltip title="Maximum Profit">
                <Chip
                  label={`Max: +${metrics.maxProfit.toFixed(0)}`}
                  size="small"
                  color="success"
                  variant="outlined"
                  sx={{ fontSize: '0.65rem' }}
                />
              </Tooltip>
              <Tooltip title="Maximum Loss">
                <Chip
                  label={`Loss: ${metrics.maxLoss.toFixed(0)}`}
                  size="small"
                  color="error"
                  variant="outlined"
                  sx={{ fontSize: '0.65rem' }}
                />
              </Tooltip>
            </Box>
          </Box>
        )}

        {/* Summary */}
        {legs.length > 0 && (
          <Box sx={{ px: 2, py: 1, bgcolor: 'action.hover' }}>
            <Box
              sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}
            >
              <Typography variant="caption" color="text.secondary">
                Net Premium
              </Typography>
              <Typography
                variant="subtitle2"
                fontWeight="bold"
                color={totals.isCredit ? 'success.main' : 'error.main'}
              >
                {totals.isCredit ? '+' : ''}
                {totals.netPremium.toFixed(2)} USD
                <Typography variant="caption" component="span" sx={{ ml: 0.5 }}>
                  ({totals.isCredit ? 'Credit' : 'Debit'})
                </Typography>
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Typography variant="caption" color="text.secondary">
                Net Delta
              </Typography>
              <Typography variant="subtitle2">{totals.netDelta.toFixed(3)}</Typography>
            </Box>
          </Box>
        )}

        {/* Strategy Name & Execute */}
        {legs.length > 0 && (
          <Box sx={{ p: 2 }}>
            {/* Error Alert */}
            {error && (
              <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}
            
            <TextField
              fullWidth
              size="small"
              label="Strategy Name"
              value={strategyName}
              onChange={(e) => setStrategyName(e.target.value)}
              sx={{ mb: 2 }}
            />

            <Button
              fullWidth
              variant="contained"
              color="success"
              size="large"
              startIcon={
                executing ? <CircularProgress size={20} color="inherit" /> : <ExecuteIcon />
              }
              onClick={handleExecute}
              disabled={executing || loading || legs.length === 0}
            >
              {executing ? 'Executing...' : 'Trade All'}
            </Button>
          </Box>
        )}
      </Collapse>
    </Paper>
  );
}
