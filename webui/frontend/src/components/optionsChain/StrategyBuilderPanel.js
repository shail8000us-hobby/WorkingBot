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

import React, { useState, useMemo, useCallback } from 'react';
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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  ListItemButton,
  Badge,
} from '@mui/material';
import {
  Delete as DeleteIcon,
  PlayArrow as ExecuteIcon,
  Clear as ClearIcon,
  ExpandMore as ExpandIcon,
  ExpandLess as CollapseIcon,
  Calculate as CalcIcon,
  BookmarkAdd as SaveTemplateIcon,
  FolderOpen as LoadTemplateIcon,
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
import { calculatePoP, calculateStrategyPoP } from '../../utils/probabilityCalc';
import { getContractMultiplier } from '../../utils/constants';

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

// Calculate max profit, max loss, breakeven, and PoP
const calculateStrategyMetrics = (payoffData, legs, spotPrice, expiry) => {
  if (!payoffData || payoffData.length === 0) {
    return { maxProfit: 0, maxLoss: 0, breakevens: [], pop: null };
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

  // Calculate Probability of Profit
  let pop = null;
  if (legs && legs.length > 0 && spotPrice && expiry) {
    try {
      // Calculate time to expiry (rough estimate)
      const now = new Date();
      const expiryDate = parseExpiry(expiry);
      const timeToExpiry = expiryDate ? (expiryDate - now) / (1000 * 60 * 60 * 24 * 365) : 0.1;

      // Get average IV from legs
      const avgIV = legs.reduce((sum, leg) => sum + (leg.iv || 0.8), 0) / legs.length;

      // For multi-leg strategies, use weighted PoP based on each leg's contribution
      if (legs.length === 1) {
        const leg = legs[0];
        pop = calculatePoP({
          spotPrice,
          strike: leg.strike,
          entryPrice: leg.premium || leg.ltp || 0,
          timeToExpiry,
          volatility: leg.iv || avgIV,
          optionType: leg.type,
          side: leg.side,
        });
      } else {
        // For multi-leg, calculate PoP based on probability of final PnL > 0
        // This is a simplified approximation
        const profitCount = pnls.filter(pnl => pnl > 0).length;
        pop = profitCount / pnls.length;
      }
    } catch (error) {
      console.error('Failed to calculate PoP:', error);
    }
  }

  return { maxProfit, maxLoss, breakevens, pop };
};

// Parse expiry string (DDMMYYYY or YYMMDD) to Date
const parseExpiry = (expiry) => {
  if (!expiry) return null;
  const expStr = String(expiry).trim();
  
  let day, month, year;
  if (expStr.length === 8) {
    // DDMMYYYY format
    day = parseInt(expStr.slice(0, 2));
    month = parseInt(expStr.slice(2, 4)) - 1; // Month is 0-indexed
    year = parseInt(expStr.slice(4, 8));
  } else if (expStr.length === 6) {
    // YYMMDD format
    year = 2000 + parseInt(expStr.slice(0, 2));
    month = parseInt(expStr.slice(2, 4)) - 1;
    day = parseInt(expStr.slice(4, 6));
  } else {
    return null;
  }
  
  return new Date(year, month, day, 17, 30); // 5:30 PM IST expiry
};

// ==================== Template Storage (localStorage) ====================

const TEMPLATE_STORAGE_KEY = 'strategy_builder_templates';

const loadTemplatesFromStorage = () => {
  try {
    const raw = localStorage.getItem(TEMPLATE_STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
};

const saveTemplatesToStorage = (templates) => {
  try {
    localStorage.setItem(TEMPLATE_STORAGE_KEY, JSON.stringify(templates));
  } catch (e) {
    console.error('Failed to save templates:', e);
  }
};

// Build product_symbol from components (e.g. "C-BTC-90000-270226")
// expiry must be DDMMYYYY; converts to DDMMYY for the symbol tail
const buildSymbol = (type, underlying, strike, expiryDDMMYYYY) => {
  if (!type || !underlying || !strike || strike <= 0) return null;
  const prefix = type === 'call' ? 'C' : 'P';
  const exp = String(expiryDDMMYYYY || '');
  if (exp.length !== 8 || !/^\d{8}$/.test(exp)) return null;
  const dd = exp.slice(0, 2);
  const mm = exp.slice(2, 4);
  const yy = exp.slice(6, 8);
  return `${prefix}-${underlying}-${strike}-${dd}${mm}${yy}`;
};

// Snap strike to the nearest standard increment for the underlying.
// Returns null if result is non-positive (prevents garbage symbols).
const snapStrike = (strike, underlying) => {
  const increment = underlying === 'BTC' ? 1000 : underlying === 'ETH' ? 100 : 50;
  const snapped = Math.round(strike / increment) * increment;
  return snapped > 0 ? snapped : null;
};

export default function StrategyBuilderPanel({
  legs = [],
  spotPrice,
  expiry,
  underlying = 'BTC',
  onUpdateLeg,
  onRemoveLeg,
  onClearAll,
  onSetLegs,
  onExecute,
  loading = false,
  expanded: initialExpanded = true,
}) {
  const [expanded, setExpanded] = useState(initialExpanded);
  const [executing, setExecuting] = useState(false);
  const [strategyName, setStrategyName] = useState('My Custom Strategy');
  const [error, setError] = useState(null);

  // ---- Template state ----
  const [templates, setTemplates] = useState(() => loadTemplatesFromStorage());
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [showLoadDialog, setShowLoadDialog] = useState(false);
  const [templateName, setTemplateName] = useState('');
  const [templateSearch, setTemplateSearch] = useState('');
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [templateLoadWarning, setTemplateLoadWarning] = useState(null);
  const [confirmDialog, setConfirmDialog] = useState({ deleteId: null, deleteAll: false });

  // Load templates from backend on mount, with localStorage migration
  React.useEffect(() => {
    const fetchTemplates = async () => {
      try {
        const response = await fetch('/api/options-strategy/user-templates');
        if (response.ok) {
          const data = await response.json();
          const backendTemplates = data.templates || [];
          setTemplates(backendTemplates);
          saveTemplatesToStorage(backendTemplates);

          // Migration: if backend is empty but localStorage has templates, sync them up
          if (backendTemplates.length === 0) {
            const localTemplates = loadTemplatesFromStorage();
            if (localTemplates.length > 0) {
              console.log(`Migrating ${localTemplates.length} templates from localStorage to backend...`);
              // Batch sync all localStorage templates to backend
              for (const tmpl of localTemplates) {
                try {
                  await fetch('/api/options-strategy/user-templates', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(tmpl),
                  });
                } catch (e) {
                  console.warn(`Failed to migrate template ${tmpl.id}:`, e);
                }
              }
              setTemplates(localTemplates);
            }
          }
        }
      } catch (e) {
        console.warn('Failed to load templates from backend, using localStorage:', e);
      }
    };
    fetchTemplates();
  }, []);

  // ---- Template handlers ----

  const handleSaveTemplate = useCallback(async () => {
    if (!legs.length) return;
    const name = (templateName || strategyName || 'My Strategy').trim();
    if (!name) return;
    const atmRef = spotPrice || 0;
    const newTemplate = {
      id: Date.now().toString(),
      name,
      underlying,
      saved_spot: atmRef,
      created_at: new Date().toISOString(),
      legs: legs.map((leg) => ({
        type: leg.type,
        side: leg.side,
        quantity: leg.quantity || 1,
        strike: leg.strike,
        atm_offset: atmRef > 0 ? leg.strike - atmRef : 0,
      })),
    };

    // Save to backend first
    try {
      const response = await fetch('/api/options-strategy/user-templates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newTemplate),
      });
      if (!response.ok) {
        console.error('Failed to save template to backend');
        return;
      }
    } catch (e) {
      console.error('Error saving template to backend:', e);
      return;
    }

    const updated = [newTemplate, ...templates];
    setTemplates(updated);
    saveTemplatesToStorage(updated);
    setShowSaveDialog(false);
    setTemplateName('');
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 3000);
  }, [legs, templates, templateName, strategyName, underlying, spotPrice]);

  const handleLoadTemplate = useCallback((template) => {
    if (!onSetLegs) return;
    const currentExpiry = expiry;
    const currentSpot = spotPrice || template.saved_spot || 0;

    const newLegs = template.legs.map((tLeg) => {
      // Recompute strike from ATM offset if we have a live spot price
      let strike = tLeg.strike;
      if (currentSpot > 0 && tLeg.atm_offset !== undefined && tLeg.atm_offset !== null) {
        const rawStrike = currentSpot + tLeg.atm_offset;
        strike = snapStrike(rawStrike, template.underlying || underlying);
      }
      // Guard: strike must be positive
      if (!strike || strike <= 0) strike = tLeg.strike;

      const symbol = currentExpiry
        ? buildSymbol(tLeg.type, template.underlying || underlying, strike, currentExpiry)
        : null;
      return {
        type: tLeg.type,
        side: tLeg.side,
        quantity: tLeg.quantity || 1,
        strike,
        symbol,
        expiry: currentExpiry,
        // Market data is not available for template legs — will be blank until
        // user clicks the same row in the chain (which updates via onUpdateLeg)
        _fromTemplate: true,  // marker so Price column can show a hint
        premium: null,
        ltp: null,
        bid: null,
        ask: null,
        iv: null,
        delta: null,
      };
    });

    onSetLegs(newLegs);
    setStrategyName(template.name);
    setShowLoadDialog(false);

    // Warn if no expiry — legs loaded but symbols are null, execute will fail
    if (!currentExpiry) {
      setTemplateLoadWarning('Template loaded — select an expiry from the chain above to populate symbols before executing.');
    } else {
      setTemplateLoadWarning('Template loaded. Prices shown are estimates — click chain rows to refresh live bid/ask.');
    }
  }, [expiry, spotPrice, underlying, onSetLegs]);

  const handleDeleteTemplate = useCallback(async (id) => {
    try {
      const response = await fetch(`/api/options-strategy/user-templates/${id}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        console.error('Failed to delete template from backend');
        return;
      }
    } catch (e) {
      console.error('Error deleting template from backend:', e);
      return;
    }

    const updated = templates.filter((t) => t.id !== id);
    setTemplates(updated);
    saveTemplatesToStorage(updated);
    setConfirmDialog({ deleteId: null, deleteAll: false });
  }, [templates]);

  const filteredTemplates = useMemo(() => {
    if (!templateSearch.trim()) return templates;
    const q = templateSearch.toLowerCase();
    return templates.filter((t) => t.name.toLowerCase().includes(q));
  }, [templates, templateSearch]);

  // Detect if any legs are template-loaded (no live market data)
  const hasTemplateLegs = useMemo(
    () => legs.some((l) => l._fromTemplate && l.bid == null),
    [legs]
  );

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
    return calculateStrategyMetrics(payoffData, legs, spotPrice, expiry);
  }, [payoffData, legs, spotPrice, expiry]);

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
      const legsWithNoSymbol = legs.filter((l) => !l.symbol);
      if (legsWithNoSymbol.length > 0) {
        if (!expiry) {
          throw new Error('Template loaded but no expiry selected — pick an expiry from the chain dropdown first, then try again.');
        }
        throw new Error(`${legsWithNoSymbol.length} leg(s) are missing a product symbol. Click their row in the chain to link them before executing.`);
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
    <>
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
        }}
      >
        {/* Left: title + leg count — clicking expands */}
        <Box
          sx={{ display: 'flex', alignItems: 'center', gap: 1, flex: 1, cursor: 'pointer' }}
          onClick={() => setExpanded(!expanded)}
        >
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

        {/* Right: template buttons + collapse */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Tooltip title={legs.length > 0 ? 'Save as Template' : 'Add legs first to save template'}>
            <span>
              <IconButton
                size="small"
                onClick={(e) => { e.stopPropagation(); setTemplateName(strategyName); setShowSaveDialog(true); }}
                disabled={legs.length === 0}
                color="primary"
              >
                <SaveTemplateIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title={`Load Template (${templates.length} saved)`}>
            <span>
              <IconButton
                size="small"
                onClick={(e) => { e.stopPropagation(); setTemplateSearch(''); setShowLoadDialog(true); }}
                color={templates.length > 0 ? 'warning' : 'default'}
              >
                <Badge badgeContent={templates.length || null} color="warning" max={9}>
                  <LoadTemplateIcon fontSize="small" />
                </Badge>
              </IconButton>
            </span>
          </Tooltip>
          <IconButton size="small" onClick={() => setExpanded(!expanded)}>
            {expanded ? <CollapseIcon /> : <ExpandIcon />}
          </IconButton>
        </Box>
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
                          const bid = leg.bid != null ? leg.bid : (leg.best_bid_price != null ? leg.best_bid_price : null);
                          const ask = leg.ask != null ? leg.ask : (leg.best_ask_price != null ? leg.best_ask_price : null);
                          const hasLiveData = bid != null && ask != null;
                          const midPrice = hasLiveData
                            ? (bid + ask) / 2
                            : (leg.premium != null ? leg.premium : (leg.ltp != null ? leg.ltp : null));

                          if (midPrice == null) {
                            return (
                              <Tooltip title="No live price — click this row in the chain to refresh">
                                <span style={{ color: '#888', fontStyle: 'italic', fontSize: '0.7rem' }}>
                                  —
                                </span>
                              </Tooltip>
                            );
                          }
                          const bidStr = bid != null ? bid.toFixed(1) : '—';
                          const askStr = ask != null ? ask.toFixed(1) : '—';
                          return (
                            <Tooltip title={`Bid: ${bidStr} | Ask: ${askStr} | Mid: ${midPrice.toFixed(1)}`}>
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
              {metrics.pop !== null && (
                <Tooltip title="Probability of Profit at Expiry">
                  <Chip
                    label={`PoP: ${(metrics.pop * 100).toFixed(1)}%`}
                    size="small"
                    color={metrics.pop > 0.5 ? 'success' : 'warning'}
                    variant="outlined"
                    sx={{ fontSize: '0.65rem', fontWeight: 'bold' }}
                  />
                </Tooltip>
              )}
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
            {/* Save success banner */}
            {saveSuccess && (
              <Alert severity="success" onClose={() => setSaveSuccess(false)} sx={{ mb: 1.5, py: 0.5 }}>
                Template saved — survives page refresh &amp; backend restarts.
              </Alert>
            )}
            {/* Template load warning */}
            {templateLoadWarning && (
              <Alert severity="info" onClose={() => setTemplateLoadWarning(null)} sx={{ mb: 1.5, py: 0.5 }}>
                {templateLoadWarning}
              </Alert>
            )}
            {/* No live price warning */}
            {hasTemplateLegs && !templateLoadWarning && (
              <Alert severity="warning" sx={{ mb: 1.5, py: 0.5 }}>
                Some legs have no live price. Click their rows in the chain to refresh bid/ask before executing.
              </Alert>
            )}
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

    {/* ==================== Save Template Dialog ==================== */}
    <Dialog
      open={showSaveDialog}
      onClose={() => setShowSaveDialog(false)}
      maxWidth="xs"
      fullWidth
    >
      <DialogTitle sx={{ pb: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <SaveTemplateIcon color="primary" />
          Save Strategy as Template
        </Box>
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Saves the current {legs.length}-leg structure. On reload you can pick a different expiry
          and strikes will auto-adjust relative to the spot price.
        </Typography>
        <TextField
          fullWidth
          size="small"
          label="Template Name"
          value={templateName}
          onChange={(e) => setTemplateName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSaveTemplate()}
          autoFocus
          placeholder="e.g. Iron Condor BTC"
        />

        {/* Preview legs */}
        <Box sx={{ mt: 2 }}>
          <Typography variant="caption" color="text.secondary" gutterBottom>
            Legs to save ({legs.length}):
          </Typography>
          {legs.map((leg, i) => (
            <Box key={i} sx={{ display: 'flex', gap: 1, alignItems: 'center', mt: 0.5 }}>
              <Chip
                label={leg.side === 'buy' ? 'B' : 'S'}
                size="small"
                color={leg.side === 'buy' ? 'primary' : 'error'}
                sx={{ minWidth: 28, height: 20, '& .MuiChip-label': { px: 0.5, fontSize: '0.65rem' } }}
              />
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
              <Typography variant="caption">
                {leg.strike?.toLocaleString()}
                {spotPrice > 0 && (
                  <span style={{ color: '#888', marginLeft: 4 }}>
                    ({leg.strike - spotPrice > 0 ? '+' : ''}{Math.round(leg.strike - spotPrice).toLocaleString()} from ATM)
                  </span>
                )}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                × {leg.quantity || 1}
              </Typography>
            </Box>
          ))}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={() => setShowSaveDialog(false)} size="small">Cancel</Button>
        <Button
          onClick={handleSaveTemplate}
          variant="contained"
          size="small"
          disabled={!templateName.trim()}
          startIcon={<SaveTemplateIcon />}
        >
          Save Template
        </Button>
      </DialogActions>
    </Dialog>

    {/* ==================== Load Template Dialog ==================== */}
    <Dialog
      open={showLoadDialog}
      onClose={() => setShowLoadDialog(false)}
      maxWidth="sm"
      fullWidth
    >
      <DialogTitle sx={{ pb: 0 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <LoadTemplateIcon color="warning" />
          Load Strategy Template
        </Box>
      </DialogTitle>
      <DialogContent sx={{ p: 0 }}>
        {/* No-expiry warning — prominent Alert, not just footer text */}
        {!expiry && (
          <Alert severity="warning" sx={{ mx: 2, mt: 1.5, mb: 0.5 }}>
            No expiry selected. Template will load but symbols will be missing — select an expiry
            from the chain dropdown after loading, then try executing.
          </Alert>
        )}
        {expiry && spotPrice > 0 && (
          <Alert severity="info" sx={{ mx: 2, mt: 1.5, mb: 0.5 }} icon={false}>
            Strikes will auto-adjust relative to current spot ({spotPrice?.toLocaleString()}).
            Saved spot is shown for reference.
          </Alert>
        )}

        {/* Search */}
        {templates.length > 3 && (
          <Box sx={{ px: 2, pt: 1 }}>
            <TextField
              fullWidth
              size="small"
              placeholder="Search templates..."
              value={templateSearch}
              onChange={(e) => setTemplateSearch(e.target.value)}
              autoFocus={templates.length > 3}
            />
          </Box>
        )}

        {filteredTemplates.length === 0 ? (
          <Box sx={{ p: 3, textAlign: 'center' }}>
            <Typography color="text.secondary" variant="body2">
              {templates.length === 0
                ? 'No saved templates yet. Build a strategy and click the 📑 icon to save one.'
                : 'No templates match your search.'}
            </Typography>
          </Box>
        ) : (
          <List dense sx={{ pt: 0.5 }}>
            {filteredTemplates.map((tmpl, idx) => (
              <React.Fragment key={tmpl.id}>
                {idx > 0 && <Divider />}
                {/* Use ListItem with secondaryAction (MUI v5 pattern, avoids z-index issues) */}
                <ListItem
                  disablePadding
                  secondaryAction={
                    <Tooltip title="Delete template">
                      <IconButton
                        edge="end"
                        size="small"
                        onClick={() => setConfirmDialog({ deleteId: tmpl.id, deleteAll: false })}
                        sx={{ opacity: 0.4, mr: 0.5, '&:hover': { opacity: 1, color: 'error.main' } }}
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  }
                >
                  <ListItemButton
                    onClick={() => handleLoadTemplate(tmpl)}
                    sx={{ py: 1, px: 2, pr: 6 }}
                  >
                    <ListItemText
                      primary={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Typography variant="body2" fontWeight="bold">{tmpl.name}</Typography>
                          <Chip
                            label={`${tmpl.legs?.length || 0} legs`}
                            size="small"
                            sx={{ height: 18, '& .MuiChip-label': { px: 0.5, fontSize: '0.6rem' } }}
                          />
                          <Typography variant="caption" color="text.disabled">
                            {tmpl.underlying}
                          </Typography>
                        </Box>
                      }
                      secondary={
                        <Box component="span" sx={{ display: 'block', mt: 0.5 }}>
                          {/* Leg summary chips */}
                          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mb: 0.5 }}>
                            {(tmpl.legs || []).map((leg, li) => {
                              const offsetStr = leg.atm_offset > 0
                                ? `+${Math.round(leg.atm_offset / 1000)}k`
                                : leg.atm_offset < 0
                                  ? `${Math.round(leg.atm_offset / 1000)}k`
                                  : 'ATM';
                              return (
                                <Chip
                                  key={li}
                                  label={`${leg.side === 'buy' ? 'B' : 'S'} ${leg.type === 'call' ? 'CE' : 'PE'} ${offsetStr}`}
                                  size="small"
                                  color={leg.side === 'buy' ? 'primary' : 'error'}
                                  variant="outlined"
                                  sx={{ height: 18, '& .MuiChip-label': { px: 0.5, fontSize: '0.6rem' } }}
                                />
                              );
                            })}
                          </Box>
                          <Typography variant="caption" color="text.disabled" component="span">
                            Saved {new Date(tmpl.created_at).toLocaleDateString()} · ref spot: {tmpl.saved_spot?.toLocaleString() || '—'}
                          </Typography>
                        </Box>
                      }
                    />
                  </ListItemButton>
                </ListItem>
              </React.Fragment>
            ))}
          </List>
        )}
      </DialogContent>
      <DialogActions sx={{ justifyContent: 'space-between' }}>
        <Button
          onClick={() => setConfirmDialog({ deleteId: null, deleteAll: true })}
          size="small"
          color="error"
          disabled={templates.length === 0}
        >
          Clear All Templates
        </Button>
        <Button onClick={() => setShowLoadDialog(false)} size="small">Close</Button>
      </DialogActions>
    </Dialog>

    {/* Delete Single Template Confirmation */}
    <Dialog
      open={confirmDialog.deleteId !== null}
      onClose={() => setConfirmDialog({ deleteId: null, deleteAll: false })}
      maxWidth="xs"
    >
      <DialogTitle>Delete Template?</DialogTitle>
      <DialogContent>
        <Typography>
          Are you sure you want to delete this template? This action cannot be undone.
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={() => setConfirmDialog({ deleteId: null, deleteAll: false })} size="small">Cancel</Button>
        <Button
          onClick={() => handleDeleteTemplate(confirmDialog.deleteId)}
          variant="contained"
          color="error"
          size="small"
        >
          Delete
        </Button>
      </DialogActions>
    </Dialog>

    {/* Delete All Templates Confirmation */}
    <Dialog
      open={confirmDialog.deleteAll}
      onClose={() => setConfirmDialog({ deleteId: null, deleteAll: false })}
      maxWidth="xs"
    >
      <DialogTitle>Delete All Templates?</DialogTitle>
      <DialogContent>
        <Typography color="error" sx={{ fontWeight: 'bold', mb: 1 }}>
          ⚠️ This will permanently delete all {templates.length} templates.
        </Typography>
        <Typography>
          This action cannot be undone. Make sure you have exported any important templates before proceeding.
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={() => setConfirmDialog({ deleteId: null, deleteAll: false })} size="small">Cancel</Button>
        <Button
          onClick={async () => {
            try {
              const response = await fetch('/api/options-strategy/user-templates/batch-delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids: templates.map(t => t.id) }),
              });
              if (response.ok) {
                setTemplates([]);
                saveTemplatesToStorage([]);
                setConfirmDialog({ deleteId: null, deleteAll: false });
                setShowLoadDialog(false);
              }
            } catch (e) {
              console.error('Error batch deleting templates:', e);
            }
          }}
          variant="contained"
          color="error"
          size="small"
        >
          Delete All
        </Button>
      </DialogActions>
    </Dialog>
    </>
  );
}
