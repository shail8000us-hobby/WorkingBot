/**
 * Sensibull-Style Position Adjustment Page
 * =========================================
 * Full-page position adjustment interface inspired by Sensibull's design.
 * 
 * Layout:
 * - Left: Current positions list with P&L, Exit/Add Trade buttons
 * - Right: Payoff graph, P&L Table, Greeks, Strategy Chart tabs
 *          Position Metrics panel
 * 
 * Created: February 1, 2026
 */

import React, { useState, useCallback, useMemo } from 'react';
import {
  Box,
  Paper,
  Typography,
  IconButton,
  Button,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Checkbox,
  Tabs,
  Tab,
  Collapse,
  Divider,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  TextField,
  CircularProgress,
  Alert,
  Tooltip,
  useTheme,
} from '@mui/material';
import {
  Close as CloseIcon,
  Refresh as RefreshIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  Add as AddIcon,
  Remove as RemoveIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  ShowChart as ChartIcon,
  TableChart as TableChartIcon,
  Settings as SettingsIcon,
  ZoomOut as ZoomOutIcon,
} from '@mui/icons-material';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as ChartTooltip,
  ReferenceLine,
  Area,
  AreaChart,
  Bar,
  BarChart,
  Legend,
} from 'recharts';
import { getContractMultiplier } from '../../utils/constants';
import SlidingOptionsChainPanel from './SlidingOptionsChainPanel';
import AdjustmentReviewDialog from './AdjustmentReviewDialog';
import { usePayoffCalculation } from './hooks/usePayoffCalculation';
import api from '../../utils/apiShim';

// Colors
const COLORS = {
  profit: '#22c55e',
  loss: '#ef4444',
  neutral: '#94a3b8',
  primary: '#3b82f6',
  background: '#0f172a',
  cardBg: 'rgba(30, 41, 59, 0.8)',
  border: 'rgba(71, 85, 105, 0.4)',
  text: '#e2e8f0',
  textSecondary: '#94a3b8',
  buy: '#22c55e',
  sell: '#ef4444',
  atm: '#fbbf24',
};

/**
 * Parse position symbol
 */
const parseSymbol = (symbol) => {
  if (!symbol) return { type: 'P', underlying: 'BTC', strike: 0, expiry: '' };
  const parts = symbol.split('-');
  return {
    type: parts[0] === 'C' ? 'CE' : 'PE',
    underlying: parts[1] || 'BTC',
    strike: parseFloat(parts[2]) || 0,
    expiry: parts[3] || '',
  };
};

/**
 * Format expiry for display (DDMMYY -> "DD Mon")
 */
const formatExpiryShort = (expiry) => {
  if (!expiry || expiry.length < 6) return expiry;
  const day = expiry.slice(0, 2);
  const month = parseInt(expiry.slice(2, 4));
  const months = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${parseInt(day)} ${months[month] || ''}`;
};

/**
 * Position Row Component
 */
const PositionRow = ({ position, isSelected, onSelect, spotPrice }) => {
  const parsed = parseSymbol(position.product_symbol);
  const size = position.size || 0;
  const entryPrice = Math.abs(position.entry_price || 0);
  const markPrice = position.mark_price || entryPrice;
  const contractMultiplier = getContractMultiplier(position.product_symbol);
  
  // Calculate P&L
  const unrealizedPnl = ((markPrice - entryPrice) * size * contractMultiplier);
  const isLong = size > 0;
  const displayQty = Math.abs(size);
  
  return (
    <TableRow 
      hover 
      sx={{ 
        '&:hover': { bgcolor: 'rgba(59, 130, 246, 0.05)' },
        borderBottom: '1px solid rgba(71, 85, 105, 0.3)',
      }}
    >
      <TableCell padding="checkbox" sx={{ borderBottom: 'none' }}>
        <Checkbox 
          checked={isSelected} 
          onChange={(e) => onSelect(position, e.target.checked)}
          size="small"
          sx={{ color: COLORS.textSecondary }}
        />
      </TableCell>
      <TableCell sx={{ borderBottom: 'none', py: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Chip 
            label={isLong ? 'B' : 'S'} 
            size="small" 
            sx={{ 
              bgcolor: isLong ? 'rgba(34, 197, 94, 0.2)' : 'rgba(239, 68, 68, 0.2)',
              color: isLong ? COLORS.buy : COLORS.sell,
              fontWeight: 'bold',
              fontSize: '0.65rem',
              height: 20,
              minWidth: 24,
            }} 
          />
          <Typography variant="body2" sx={{ fontWeight: 500, color: COLORS.text }}>
            {formatExpiryShort(parsed.expiry)} {parsed.strike.toLocaleString()} {parsed.type}
          </Typography>
        </Box>
      </TableCell>
      <TableCell align="center" sx={{ borderBottom: 'none', py: 1 }}>
        <Typography variant="body2" sx={{ color: COLORS.text }}>
          {displayQty}
        </Typography>
      </TableCell>
      <TableCell align="right" sx={{ borderBottom: 'none', py: 1 }}>
        <Typography variant="body2" sx={{ color: COLORS.text }}>
          {entryPrice.toFixed(2)}
        </Typography>
      </TableCell>
      <TableCell align="right" sx={{ borderBottom: 'none', py: 1 }}>
        <Typography variant="body2" sx={{ color: COLORS.text }}>
          {markPrice.toFixed(2)}
        </Typography>
      </TableCell>
      <TableCell align="right" sx={{ borderBottom: 'none', py: 1 }}>
        <Typography 
          variant="body2" 
          sx={{ 
            color: unrealizedPnl >= 0 ? COLORS.profit : COLORS.loss,
            fontWeight: 600,
          }}
        >
          {unrealizedPnl >= 0 ? '+' : ''}{unrealizedPnl.toFixed(2)}
        </Typography>
      </TableCell>
    </TableRow>
  );
};

/**
 * Position Metrics Card
 */
const PositionMetricsCard = ({ metrics, hasProposedTrades }) => {
  if (!metrics) return null;
  
  const { current, combined } = metrics;
  const displayMetrics = hasProposedTrades ? combined : current;
  const raw = metrics.raw || {};
  
  return (
    <Paper sx={{ 
      p: 2, 
      bgcolor: COLORS.cardBg, 
      border: `1px solid ${COLORS.border}`,
      borderRadius: 2,
    }}>
      <Typography variant="subtitle2" sx={{ color: COLORS.textSecondary, mb: 1.5, fontWeight: 600 }}>
        Position Metrics
      </Typography>
      
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 1.5 }}>
        {/* Max Profit */}
        <Typography variant="body2" sx={{ color: COLORS.textSecondary }}>Max Profit</Typography>
        <Typography variant="body2" sx={{ color: COLORS.profit, fontWeight: 600, textAlign: 'right' }}>
          {displayMetrics?.maxProfit || '-'}
        </Typography>
        
        {/* Max Loss */}
        <Typography variant="body2" sx={{ color: COLORS.textSecondary }}>Max Loss</Typography>
        <Typography variant="body2" sx={{ color: COLORS.loss, fontWeight: 600, textAlign: 'right' }}>
          {displayMetrics?.maxLoss || '-'}
        </Typography>
        
        {/* Risk/Reward */}
        <Typography variant="body2" sx={{ color: COLORS.textSecondary }}>Risk/Reward</Typography>
        <Typography variant="body2" sx={{ color: COLORS.text, fontWeight: 600, textAlign: 'right' }}>
          {displayMetrics?.riskReward || '-'}
        </Typography>
        
        {/* PoP */}
        <Typography variant="body2" sx={{ color: COLORS.textSecondary }}>PoP</Typography>
        <Typography variant="body2" sx={{ color: COLORS.text, fontWeight: 600, textAlign: 'right' }}>
          {displayMetrics?.pop || '-'}
        </Typography>
        
        {/* Breakeven */}
        <Typography variant="body2" sx={{ color: COLORS.textSecondary }}>Breakeven</Typography>
        <Typography variant="body2" sx={{ color: COLORS.primary, fontWeight: 600, textAlign: 'right' }}>
          ${displayMetrics?.breakevens?.[0] || '-'}
        </Typography>
      </Box>
      
      <Divider sx={{ my: 1.5, borderColor: COLORS.border }} />
      
      {/* Greeks */}
      <Typography variant="caption" sx={{ color: COLORS.textSecondary, fontWeight: 600 }}>
        Greeks
      </Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 1, mt: 1 }}>
        <Box>
          <Typography variant="caption" sx={{ color: COLORS.textSecondary }}>Net Delta</Typography>
          <Typography variant="body2" sx={{ color: COLORS.text, fontWeight: 600 }}>
            {displayMetrics?.netDelta || '-'}
          </Typography>
        </Box>
        <Box>
          <Typography variant="caption" sx={{ color: COLORS.textSecondary }}>Net Theta</Typography>
          <Typography variant="body2" sx={{ color: COLORS.text, fontWeight: 600 }}>
            {displayMetrics?.netTheta || '-'}
          </Typography>
        </Box>
        <Box>
          <Typography variant="caption" sx={{ color: COLORS.textSecondary }}>Net Vega</Typography>
          <Typography variant="body2" sx={{ color: COLORS.text, fontWeight: 600 }}>
            {displayMetrics?.netVega || '-'}
          </Typography>
        </Box>
        <Box>
          <Typography variant="caption" sx={{ color: COLORS.textSecondary }}>Net Premium</Typography>
          <Typography 
            variant="body2" 
            sx={{ 
              color: (raw.current?.netPremium || 0) >= 0 ? COLORS.profit : COLORS.loss, 
              fontWeight: 600 
            }}
          >
            {displayMetrics?.netPremium || '-'}
          </Typography>
        </Box>
      </Box>
    </Paper>
  );
};

/**
 * Payoff Chart Component
 */
const PayoffChart = ({ chartData, spotPrice, hasProposedTrades, breakevens = [] }) => {
  if (!chartData || chartData.length === 0) {
    return (
      <Box sx={{ 
        height: 280, 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'center',
        bgcolor: 'rgba(0,0,0,0.2)',
        borderRadius: 1,
      }}>
        <Typography color="text.secondary">No payoff data</Typography>
      </Box>
    );
  }
  
  // Find min/max for Y axis
  const allValues = chartData.flatMap(d => [d.current, d.combined].filter(v => v != null));
  const minY = Math.min(...allValues);
  const maxY = Math.max(...allValues);
  const padding = Math.abs(maxY - minY) * 0.15 || 100;
  
  return (
    <Box sx={{ height: 280, position: 'relative' }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData} margin={{ top: 10, right: 30, left: 10, bottom: 5 }}>
          <defs>
            <linearGradient id="profitGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={COLORS.profit} stopOpacity={0.3} />
              <stop offset="100%" stopColor={COLORS.profit} stopOpacity={0} />
            </linearGradient>
            <linearGradient id="lossGrad" x1="0" y1="1" x2="0" y2="0">
              <stop offset="0%" stopColor={COLORS.loss} stopOpacity={0.3} />
              <stop offset="100%" stopColor={COLORS.loss} stopOpacity={0} />
            </linearGradient>
          </defs>
          
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" vertical={false} />
          
          <XAxis 
            dataKey="price" 
            tickFormatter={(v) => v >= 1000 ? `${(v/1000).toFixed(0)}K` : v}
            stroke={COLORS.textSecondary}
            tick={{ fontSize: 11, fill: COLORS.textSecondary }}
          />
          
          <YAxis 
            domain={[minY - padding, maxY + padding]}
            tickFormatter={(v) => v >= 1000 || v <= -1000 ? `${(v/1000).toFixed(1)}K` : v}
            stroke={COLORS.textSecondary}
            tick={{ fontSize: 11, fill: COLORS.textSecondary }}
          />
          
          <ChartTooltip 
            contentStyle={{ 
              backgroundColor: COLORS.cardBg, 
              border: `1px solid ${COLORS.border}`,
              borderRadius: 8,
            }}
            labelStyle={{ color: COLORS.text }}
          />
          
          {/* Zero line */}
          <ReferenceLine y={0} stroke="rgba(255,255,255,0.3)" strokeWidth={1} />
          
          {/* Current spot line */}
          {spotPrice && (
            <ReferenceLine 
              x={spotPrice} 
              stroke={COLORS.atm} 
              strokeWidth={2}
              strokeDasharray="5 5"
              label={{ 
                value: 'Current Position', 
                position: 'top', 
                fill: COLORS.atm, 
                fontSize: 10 
              }}
            />
          )}
          
          {/* Current position line */}
          <Line 
            type="monotone" 
            dataKey="current" 
            name="On Expiry"
            stroke={COLORS.profit}
            strokeWidth={2}
            dot={false}
          />
          
          {/* Combined line (if proposed trades exist) */}
          {hasProposedTrades && (
            <Line 
              type="monotone" 
              dataKey="combined" 
              name="On Target Date"
              stroke={COLORS.primary}
              strokeWidth={2}
              strokeDasharray="6 3"
              dot={false}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
      
      {/* Legend */}
      <Box sx={{ 
        display: 'flex', 
        justifyContent: 'center', 
        gap: 3, 
        mt: 1,
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={{ width: 16, height: 3, bgcolor: COLORS.profit, borderRadius: 1 }} />
          <Typography variant="caption" sx={{ color: COLORS.textSecondary }}>On Expiry</Typography>
        </Box>
        {hasProposedTrades && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box sx={{ 
              width: 16, 
              height: 3, 
              bgcolor: COLORS.primary, 
              borderRadius: 1,
              background: `repeating-linear-gradient(90deg, transparent, transparent 2px, ${COLORS.primary} 2px, ${COLORS.primary} 4px)`,
            }} />
            <Typography variant="caption" sx={{ color: COLORS.textSecondary }}>On Target Date</Typography>
          </Box>
        )}
      </Box>
    </Box>
  );
};

/**
 * Main Sensibull-Style Adjustment Page
 */
export default function SensibullStyleAdjustmentPage({
  open,
  onClose,
  currentPositions = [],
  spotPrice,
  underlying = 'BTC',
  onExecuteComplete,
}) {
  const theme = useTheme();
  
  // State
  const [selectedPositions, setSelectedPositions] = useState([]);
  const [proposedTrades, setProposedTrades] = useState([]);
  const [showClosedPositions, setShowClosedPositions] = useState(false);
  const [activeTab, setActiveTab] = useState(0); // Payoff Graph, P&L Table, Greeks, Strategy Chart
  const [reviewDialogOpen, setReviewDialogOpen] = useState(false);
  const [showChainPanel, setShowChainPanel] = useState(false);
  const [selectedExpiry, setSelectedExpiry] = useState('');
  const [targetPrice, setTargetPrice] = useState(spotPrice || 0);
  
  // Calculate payoff
  const payoffData = usePayoffCalculation(
    currentPositions,
    proposedTrades,
    spotPrice,
    { enabled: open }
  );
  
  // Derive underlying
  const derivedUnderlying = useMemo(() => {
    if (currentPositions?.length > 0) {
      const parts = currentPositions[0]?.product_symbol?.split('-');
      return parts?.[1] || underlying;
    }
    return underlying;
  }, [currentPositions, underlying]);
  
  // Calculate totals
  const totals = useMemo(() => {
    let booked = 0;
    let unbooked = 0;
    
    currentPositions.forEach(pos => {
      const size = pos.size || 0;
      const entryPrice = Math.abs(pos.entry_price || 0);
      const markPrice = pos.mark_price || entryPrice;
      const multiplier = getContractMultiplier(pos.product_symbol);
      const pnl = (markPrice - entryPrice) * size * multiplier;
      unbooked += pnl;
    });
    
    return {
      booked,
      unbooked,
      total: booked + unbooked,
    };
  }, [currentPositions]);
  
  // Handle position selection
  const handleSelectPosition = useCallback((position, selected) => {
    if (selected) {
      setSelectedPositions(prev => [...prev, position]);
    } else {
      setSelectedPositions(prev => prev.filter(p => p.product_symbol !== position.product_symbol));
    }
  }, []);
  
  // Handle add trade
  const handleAddTrade = useCallback((trade) => {
    setProposedTrades(prev => [...prev, trade]);
  }, []);
  
  // Handle remove trade
  const handleRemoveTrade = useCallback((trade) => {
    setProposedTrades(prev => 
      prev.filter(t => !(t.strike === trade.strike && t.type === trade.type && t.side === trade.side))
    );
  }, []);
  
  // Handle update trade qty
  const handleUpdateTradeQty = useCallback((strike, type, side, newQty) => {
    setProposedTrades(prev =>
      prev.map(t => {
        if (t.strike === strike && t.type === type && t.side === side) {
          return { ...t, quantity: newQty };
        }
        return t;
      })
    );
  }, []);
  
  // Handle clear all
  const handleClearAll = useCallback(() => {
    setProposedTrades([]);
    setSelectedPositions([]);
  }, []);
  
  if (!open) return null;
  
  return (
    <Box sx={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      bgcolor: COLORS.background,
      zIndex: 1300,
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <Box sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        px: 3,
        py: 1.5,
        bgcolor: 'rgba(15, 23, 42, 0.95)',
        borderBottom: `1px solid ${COLORS.border}`,
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <ChartIcon sx={{ color: COLORS.primary }} />
          <Typography variant="h6" sx={{ color: COLORS.text, fontWeight: 600 }}>
            Position Adjustment
          </Typography>
          <Chip 
            label={derivedUnderlying} 
            size="small" 
            sx={{ bgcolor: 'rgba(59, 130, 246, 0.2)', color: COLORS.primary }}
          />
        </Box>
        
        <IconButton onClick={onClose} sx={{ color: COLORS.textSecondary }}>
          <CloseIcon />
        </IconButton>
      </Box>
      
      {/* Main Content */}
      <Box sx={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Left Panel - Positions */}
        <Box sx={{ 
          width: 420, 
          flexShrink: 0, 
          display: 'flex', 
          flexDirection: 'column',
          borderRight: `1px solid ${COLORS.border}`,
          bgcolor: 'rgba(15, 23, 42, 0.5)',
        }}>
          {/* Positions Header */}
          <Box sx={{ p: 2, borderBottom: `1px solid ${COLORS.border}` }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5 }}>
              <Typography variant="subtitle1" sx={{ color: COLORS.text, fontWeight: 600 }}>
                {derivedUnderlying} Positions
              </Typography>
              <Button 
                size="small" 
                sx={{ color: COLORS.textSecondary }}
              >
                Clear Positions
              </Button>
            </Box>
            
            {/* Action Buttons */}
            <Box sx={{ display: 'flex', gap: 1, mb: 1.5 }}>
              <Button 
                variant="outlined" 
                size="small"
                disabled={selectedPositions.length === 0}
                sx={{ 
                  borderColor: COLORS.loss, 
                  color: COLORS.loss,
                  '&:hover': { borderColor: COLORS.loss, bgcolor: 'rgba(239, 68, 68, 0.1)' },
                }}
              >
                Exit Positions ({selectedPositions.length})
              </Button>
              <Button 
                variant="outlined" 
                size="small"
                onClick={() => setShowChainPanel(!showChainPanel)}
                sx={{ 
                  borderColor: COLORS.primary, 
                  color: COLORS.primary,
                  '&:hover': { borderColor: COLORS.primary, bgcolor: 'rgba(59, 130, 246, 0.1)' },
                }}
              >
                Add New Trade
              </Button>
            </Box>
            
            {/* P&L Summary */}
            <Box sx={{ display: 'flex', gap: 3 }}>
              <Box>
                <Typography variant="caption" sx={{ color: COLORS.textSecondary }}>Booked</Typography>
                <Typography variant="body2" sx={{ color: totals.booked >= 0 ? COLORS.profit : COLORS.loss, fontWeight: 600 }}>
                  {totals.booked >= 0 ? '+' : ''}{totals.booked.toFixed(0)}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: COLORS.textSecondary }}>Unbooked</Typography>
                <Typography variant="body2" sx={{ color: totals.unbooked >= 0 ? COLORS.profit : COLORS.loss, fontWeight: 600 }}>
                  {totals.unbooked >= 0 ? '+' : ''}{totals.unbooked.toFixed(0)}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: COLORS.textSecondary }}>Total P&L</Typography>
                <Typography variant="body2" sx={{ color: totals.total >= 0 ? COLORS.profit : COLORS.loss, fontWeight: 600 }}>
                  {totals.total >= 0 ? '+' : ''}{totals.total.toFixed(0)}
                </Typography>
              </Box>
            </Box>
          </Box>
          
          {/* Positions Table */}
          <Box sx={{ flex: 1, overflow: 'auto' }}>
            {/* Open Positions */}
            <Box sx={{ p: 1.5, borderBottom: `1px solid ${COLORS.border}` }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <Checkbox 
                  size="small"
                  checked={selectedPositions.length === currentPositions.length}
                  indeterminate={selectedPositions.length > 0 && selectedPositions.length < currentPositions.length}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSelectedPositions([...currentPositions]);
                    } else {
                      setSelectedPositions([]);
                    }
                  }}
                  sx={{ color: COLORS.textSecondary }}
                />
                <Typography variant="caption" sx={{ color: COLORS.textSecondary }}>
                  Instrument
                </Typography>
              </Box>
              
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell padding="checkbox" sx={{ color: COLORS.textSecondary, borderBottom: 'none' }}></TableCell>
                      <TableCell sx={{ color: COLORS.textSecondary, borderBottom: 'none', fontSize: '0.75rem' }}>Instrument</TableCell>
                      <TableCell align="center" sx={{ color: COLORS.textSecondary, borderBottom: 'none', fontSize: '0.75rem' }}>Qty</TableCell>
                      <TableCell align="right" sx={{ color: COLORS.textSecondary, borderBottom: 'none', fontSize: '0.75rem' }}>Avg</TableCell>
                      <TableCell align="right" sx={{ color: COLORS.textSecondary, borderBottom: 'none', fontSize: '0.75rem' }}>LTP</TableCell>
                      <TableCell align="right" sx={{ color: COLORS.textSecondary, borderBottom: 'none', fontSize: '0.75rem' }}>P&L</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {currentPositions.map((pos, idx) => (
                      <PositionRow 
                        key={pos.product_symbol || idx}
                        position={pos}
                        isSelected={selectedPositions.some(p => p.product_symbol === pos.product_symbol)}
                        onSelect={handleSelectPosition}
                        spotPrice={spotPrice}
                      />
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
              
              {currentPositions.length === 0 && (
                <Box sx={{ p: 3, textAlign: 'center' }}>
                  <Typography variant="body2" sx={{ color: COLORS.textSecondary }}>
                    No open positions
                  </Typography>
                </Box>
              )}
            </Box>
            
            {/* Closed Positions (Collapsible) */}
            <Box>
              <Box 
                sx={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'space-between',
                  p: 1.5,
                  cursor: 'pointer',
                  '&:hover': { bgcolor: 'rgba(255,255,255,0.02)' },
                }}
                onClick={() => setShowClosedPositions(!showClosedPositions)}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Checkbox size="small" sx={{ color: COLORS.textSecondary }} disabled />
                  <Typography variant="body2" sx={{ color: COLORS.textSecondary }}>
                    Closed Positions (0)
                  </Typography>
                </Box>
                {showClosedPositions ? <ExpandLessIcon sx={{ color: COLORS.textSecondary }} /> : <ExpandMoreIcon sx={{ color: COLORS.textSecondary }} />}
              </Box>
              <Collapse in={showClosedPositions}>
                <Box sx={{ p: 2, textAlign: 'center' }}>
                  <Typography variant="caption" sx={{ color: COLORS.textSecondary }}>
                    No closed positions
                  </Typography>
                </Box>
              </Collapse>
            </Box>
          </Box>
        </Box>
        
        {/* Right Panel - Chart & Metrics */}
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Top Metrics Bar */}
          <Box sx={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between',
            px: 3, 
            py: 1.5,
            borderBottom: `1px solid ${COLORS.border}`,
            bgcolor: 'rgba(15, 23, 42, 0.3)',
          }}>
            <Box sx={{ display: 'flex', gap: 4 }}>
              <Box>
                <Typography variant="caption" sx={{ color: COLORS.textSecondary }}>Profit left</Typography>
                <Typography variant="body2" sx={{ color: COLORS.profit, fontWeight: 600 }}>
                  {payoffData.formattedMetrics?.current?.maxProfit || '-'}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: COLORS.textSecondary }}>Loss left</Typography>
                <Typography variant="body2" sx={{ color: COLORS.loss, fontWeight: 600 }}>
                  {payoffData.formattedMetrics?.current?.maxLoss === 'Unlimited' ? 'Unlimited' : payoffData.formattedMetrics?.current?.maxLoss || '-'}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: COLORS.textSecondary }}>Reward / Risk</Typography>
                <Typography variant="body2" sx={{ color: COLORS.text, fontWeight: 600 }}>
                  {payoffData.formattedMetrics?.current?.riskReward || '-'}
                </Typography>
              </Box>
              <Box>
                <Typography variant="caption" sx={{ color: COLORS.textSecondary }}>POP</Typography>
                <Typography variant="body2" sx={{ color: COLORS.text, fontWeight: 600 }}>
                  {payoffData.formattedMetrics?.current?.pop || '-'}
                </Typography>
              </Box>
            </Box>
            
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <IconButton size="small" sx={{ color: COLORS.textSecondary }}>
                <SettingsIcon fontSize="small" />
              </IconButton>
            </Box>
          </Box>
          
          {/* Chart Area */}
          <Box sx={{ flex: 1, p: 2, overflow: 'auto' }}>
            {/* Tabs */}
            <Box sx={{ mb: 2 }}>
              <Tabs 
                value={activeTab} 
                onChange={(e, v) => setActiveTab(v)}
                sx={{
                  '& .MuiTab-root': { 
                    color: COLORS.textSecondary, 
                    textTransform: 'none',
                    minWidth: 100,
                  },
                  '& .Mui-selected': { color: COLORS.primary },
                  '& .MuiTabs-indicator': { bgcolor: COLORS.primary },
                }}
              >
                <Tab label="Payoff Graph" />
                <Tab label="P&L Table" />
                <Tab label="Greeks" />
                <Tab label="Strategy Chart" />
              </Tabs>
            </Box>
            
            {/* Payoff Graph Tab */}
            {activeTab === 0 && (
              <Box sx={{ display: 'flex', gap: 2 }}>
                {/* Chart */}
                <Box sx={{ flex: 1 }}>
                  <Paper sx={{ 
                    p: 2, 
                    bgcolor: COLORS.cardBg, 
                    border: `1px solid ${COLORS.border}`,
                    borderRadius: 2,
                  }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                      <Box sx={{ display: 'flex', gap: 1 }}>
                        <Chip label="Payoff Graph" size="small" sx={{ bgcolor: 'rgba(59, 130, 246, 0.2)', color: COLORS.primary }} />
                        <Chip label="Payoff Table" size="small" variant="outlined" sx={{ borderColor: COLORS.border, color: COLORS.textSecondary }} />
                      </Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Chip label="SD Dynamic" size="small" variant="outlined" sx={{ borderColor: COLORS.border, color: COLORS.textSecondary }} />
                        <Chip label="Open Interest" size="small" variant="outlined" sx={{ borderColor: COLORS.border, color: COLORS.textSecondary }} />
                      </Box>
                    </Box>
                    
                    {/* Current price indicator */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                      <Typography variant="caption" sx={{ color: COLORS.textSecondary }}>
                        Current price: ${spotPrice?.toLocaleString() || '-'}
                      </Typography>
                      <Button size="small" startIcon={<ZoomOutIcon />} sx={{ color: COLORS.textSecondary }}>
                        Zoom Out
                      </Button>
                    </Box>
                    
                    <PayoffChart 
                      chartData={payoffData.chartData}
                      spotPrice={spotPrice}
                      hasProposedTrades={proposedTrades.length > 0}
                      breakevens={payoffData.currentMetrics?.breakevens}
                    />
                    
                    {/* Projected profit */}
                    <Box sx={{ 
                      mt: 2, 
                      p: 1.5, 
                      bgcolor: 'rgba(34, 197, 94, 0.1)', 
                      borderRadius: 1,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 1,
                    }}>
                      <Typography variant="body2" sx={{ color: COLORS.profit }}>
                        Projected profit: {payoffData.formattedMetrics?.current?.maxProfit || '-'}
                      </Typography>
                    </Box>
                  </Paper>
                  
                  {/* Target Price Selector */}
                  <Paper sx={{ 
                    mt: 2, 
                    p: 2, 
                    bgcolor: COLORS.cardBg, 
                    border: `1px solid ${COLORS.border}`,
                    borderRadius: 2,
                  }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                      <Typography variant="body2" sx={{ color: COLORS.text }}>
                        {derivedUnderlying} Target
                      </Typography>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Chip label="0.0%" size="small" sx={{ bgcolor: 'rgba(255,255,255,0.1)', color: COLORS.text }} />
                        <IconButton size="small" sx={{ color: COLORS.textSecondary }}><RemoveIcon fontSize="small" /></IconButton>
                        <TextField
                          size="small"
                          value={targetPrice || spotPrice || ''}
                          onChange={(e) => setTargetPrice(parseFloat(e.target.value) || 0)}
                          sx={{ 
                            width: 120,
                            '& input': { color: COLORS.text, textAlign: 'center' },
                            '& .MuiOutlinedInput-root': { 
                              '& fieldset': { borderColor: COLORS.border },
                            },
                          }}
                        />
                        <IconButton size="small" sx={{ color: COLORS.textSecondary }}><AddIcon fontSize="small" /></IconButton>
                      </Box>
                      <Button size="small" sx={{ color: COLORS.primary }}>Reset</Button>
                    </Box>
                  </Paper>
                </Box>
                
                {/* Metrics Sidebar */}
                <Box sx={{ width: 280, flexShrink: 0 }}>
                  <PositionMetricsCard 
                    metrics={payoffData.formattedMetrics}
                    hasProposedTrades={proposedTrades.length > 0}
                  />
                  
                  {/* Proposed Trades */}
                  {proposedTrades.length > 0 && (
                    <Paper sx={{ 
                      mt: 2, 
                      p: 2, 
                      bgcolor: COLORS.cardBg, 
                      border: `1px solid ${COLORS.border}`,
                      borderRadius: 2,
                    }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                        <Typography variant="subtitle2" sx={{ color: COLORS.textSecondary, fontWeight: 600 }}>
                          Proposed Trades ({proposedTrades.length})
                        </Typography>
                        <Button size="small" color="error" onClick={handleClearAll}>
                          Clear
                        </Button>
                      </Box>
                      
                      {proposedTrades.map((trade, idx) => (
                        <Box key={idx} sx={{ 
                          display: 'flex', 
                          alignItems: 'center', 
                          justifyContent: 'space-between',
                          py: 0.5,
                          borderBottom: idx < proposedTrades.length - 1 ? `1px solid ${COLORS.border}` : 'none',
                        }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Chip 
                              label={trade.side === 'buy' ? 'B' : 'S'} 
                              size="small" 
                              sx={{ 
                                bgcolor: trade.side === 'buy' ? 'rgba(34, 197, 94, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                                color: trade.side === 'buy' ? COLORS.buy : COLORS.sell,
                                fontSize: '0.6rem',
                                height: 18,
                              }} 
                            />
                            <Typography variant="caption" sx={{ color: COLORS.text }}>
                              {trade.strike} {trade.type === 'call' ? 'C' : 'P'}
                            </Typography>
                          </Box>
                          <Typography variant="caption" sx={{ color: COLORS.textSecondary }}>
                            x{trade.quantity}
                          </Typography>
                        </Box>
                      ))}
                      
                      <Button 
                        fullWidth 
                        variant="contained" 
                        color="primary"
                        sx={{ mt: 2 }}
                        onClick={() => setReviewDialogOpen(true)}
                      >
                        Review & Execute
                      </Button>
                    </Paper>
                  )}
                </Box>
              </Box>
            )}
            
            {/* Other tabs placeholder */}
            {activeTab !== 0 && (
              <Box sx={{ p: 4, textAlign: 'center' }}>
                <Typography variant="body1" sx={{ color: COLORS.textSecondary }}>
                  {['Payoff Graph', 'P&L Table', 'Greeks', 'Strategy Chart'][activeTab]} - Coming soon
                </Typography>
              </Box>
            )}
          </Box>
          
          {/* Footer */}
          <Box sx={{ 
            px: 3, 
            py: 1, 
            borderTop: `1px solid ${COLORS.border}`,
            bgcolor: 'rgba(15, 23, 42, 0.3)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <Typography variant="caption" sx={{ color: COLORS.textSecondary }}>
              Current Positions: {currentPositions.length} | Spot: ${spotPrice?.toLocaleString() || '-'}
            </Typography>
            <Typography variant="caption" sx={{ color: COLORS.textSecondary }}>
              Powered by Autoloop Execution
            </Typography>
          </Box>
        </Box>
      </Box>
      
      {/* Sliding Options Chain Panel (from left side like Sensibull) */}
      <SlidingOptionsChainPanel
        open={showChainPanel}
        onClose={() => setShowChainPanel(false)}
        underlying={derivedUnderlying}
        spotPrice={spotPrice}
        proposedTrades={proposedTrades}
        onAddTrade={handleAddTrade}
        onRemoveTrade={handleRemoveTrade}
        selectedExpiry={selectedExpiry}
        onExpiryChange={setSelectedExpiry}
      />
      
      {/* Review Dialog */}
      <AdjustmentReviewDialog
        open={reviewDialogOpen}
        onClose={() => setReviewDialogOpen(false)}
        trades={proposedTrades}
        formattedMetrics={payoffData.formattedMetrics}
        onExecute={(params) => {
          setReviewDialogOpen(false);
          onExecuteComplete?.();
          onClose?.();
        }}
      />
    </Box>
  );
}
