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
  ZoomIn as ZoomInIcon,
  CenterFocusStrong as ResetZoomIcon,
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
  Brush,
  ReferenceArea,
} from 'recharts';
import { getContractMultiplier } from '../../utils/constants';
import SlidingOptionsChainPanel from './SlidingOptionsChainPanel';
import AdjustmentReviewDialog from './AdjustmentReviewDialog';
import EnhancedPayoffChart from './EnhancedPayoffChart';
import NetDebitCreditBar from './NetDebitCreditBar';
import MarginImpactRow from './MarginImpactRow';
import StressTestMatrix from './StressTestMatrix';
import ScenarioManager from './ScenarioManager';
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
 * Payoff Chart Component - Enhanced with colored profit/loss zones and zoom functionality
 */
const PayoffChart = ({ chartData, spotPrice, hasProposedTrades, breakevens = [], zoomDomain, onZoomChange }) => {
  const [refAreaLeft, setRefAreaLeft] = useState(null);
  const [refAreaRight, setRefAreaRight] = useState(null);
  const [isSelecting, setIsSelecting] = useState(false);

  if (!chartData || chartData.length === 0) {
    return (
      <Box sx={{
        height: 320,
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

  // Filter data to zoom domain if set
  const filteredData = zoomDomain
    ? chartData.filter(d => d.price >= zoomDomain[0] && d.price <= zoomDomain[1])
    : chartData;

  // Find min/max for Y axis - include combined values when we have proposed trades
  const allValues = filteredData.flatMap(d => [d.current, d.combined].filter(v => v != null));
  const minY = Math.min(...allValues);
  const maxY = Math.max(...allValues);
  const padding = Math.abs(maxY - minY) * 0.2 || 100;

  // Use combined payoff when there are proposed trades, otherwise current
  // This shows the expected P&L after executing proposed trades
  const enhancedData = filteredData.map(d => {
    const displayPnl = hasProposedTrades ? (d.combined ?? d.current) : d.current;
    return {
      ...d,
      profit: displayPnl > 0 ? displayPnl : 0,
      loss: displayPnl < 0 ? displayPnl : 0,
      // Add combined profit/loss zones for visual comparison
      combinedProfit: hasProposedTrades && d.combined > 0 ? d.combined : 0,
      combinedLoss: hasProposedTrades && d.combined < 0 ? d.combined : 0,
    };
  });

  // Find ATM strike (closest to spot)
  const atmPrice = spotPrice;

  // Find projected profit at current spot - use combined if proposed trades exist
  const spotDataPoint = chartData.find(d => Math.abs(d.price - spotPrice) < (spotPrice * 0.005));
  const projectedProfit = hasProposedTrades
    ? (spotDataPoint?.combined ?? spotDataPoint?.current ?? 0)
    : (spotDataPoint?.current ?? 0);

  // Zoom handlers
  const handleMouseDown = (e) => {
    if (e && e.activeLabel) {
      setRefAreaLeft(e.activeLabel);
      setIsSelecting(true);
    }
  };

  const handleMouseMove = (e) => {
    if (isSelecting && e && e.activeLabel) {
      setRefAreaRight(e.activeLabel);
    }
  };

  const handleMouseUp = () => {
    if (refAreaLeft && refAreaRight && refAreaLeft !== refAreaRight) {
      const left = Math.min(refAreaLeft, refAreaRight);
      const right = Math.max(refAreaLeft, refAreaRight);
      onZoomChange?.([left, right]);
    }
    setRefAreaLeft(null);
    setRefAreaRight(null);
    setIsSelecting(false);
  };

  return (
    <Box sx={{ height: 320, position: 'relative', cursor: isSelecting ? 'crosshair' : 'default' }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart
          data={enhancedData}
          margin={{ top: 20, right: 30, left: 10, bottom: 10 }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          <defs>
            {/* Profit area gradient */}
            <linearGradient id="profitAreaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity={0.4} />
              <stop offset="100%" stopColor="#10b981" stopOpacity={0.05} />
            </linearGradient>
            {/* Loss area gradient */}
            <linearGradient id="lossAreaGrad" x1="0" y1="1" x2="0" y2="0">
              <stop offset="0%" stopColor="#ef4444" stopOpacity={0.4} />
              <stop offset="100%" stopColor="#ef4444" stopOpacity={0.05} />
            </linearGradient>
          </defs>

          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" vertical={false} />

          <XAxis
            dataKey="price"
            tickFormatter={(v) => v >= 1000 ? `${(v / 1000).toFixed(0)}K` : v.toFixed(0)}
            stroke="rgba(148, 163, 184, 0.6)"
            tick={{ fontSize: 11, fill: '#94a3b8' }}
            axisLine={{ stroke: 'rgba(148, 163, 184, 0.3)' }}
            allowDataOverflow
          />

          <YAxis
            domain={[minY - padding, maxY + padding]}
            tickFormatter={(v) => {
              if (Math.abs(v) >= 1000) return `$${(v / 1000).toFixed(1)}K`;
              return `$${v.toFixed(0)}`;
            }}
            stroke="rgba(148, 163, 184, 0.6)"
            tick={{ fontSize: 11, fill: '#94a3b8' }}
            axisLine={{ stroke: 'rgba(148, 163, 184, 0.3)' }}
            label={{
              value: 'Profit / Loss',
              angle: -90,
              position: 'insideLeft',
              style: { fill: '#94a3b8', fontSize: 11 }
            }}
          />

          <ChartTooltip
            contentStyle={{
              backgroundColor: 'rgba(30, 41, 59, 0.95)',
              border: '1px solid rgba(71, 85, 105, 0.5)',
              borderRadius: 8,
              boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
            }}
            labelStyle={{ color: '#e2e8f0', fontWeight: 'bold' }}
            formatter={(value, name) => {
              const color = value >= 0 ? '#10b981' : '#ef4444';
              const label = name === 'current' ? 'On Expiry' : name === 'combined' ? 'On Target' : name;
              return [<span style={{ color }}>${value?.toFixed(2)}</span>, label];
            }}
            labelFormatter={(label) => `Price: $${label?.toLocaleString()}`}
          />

          {/* Zero reference line */}
          <ReferenceLine
            y={0}
            stroke="rgba(255,255,255,0.4)"
            strokeWidth={1.5}
          />

          {/* ATM/Current spot line */}
          {spotPrice && (
            <ReferenceLine
              x={spotPrice}
              stroke="#fbbf24"
              strokeWidth={2}
              strokeDasharray="8 4"
              label={{
                value: 'ATM',
                position: 'top',
                fill: '#fbbf24',
                fontSize: 12,
                fontWeight: 'bold',
              }}
            />
          )}

          {/* Breakeven lines */}
          {breakevens?.map((be, idx) => (
            <ReferenceLine
              key={idx}
              x={be}
              stroke="#8b5cf6"
              strokeWidth={1}
              strokeDasharray="4 4"
            />
          ))}

          {/* Profit area fill */}
          <Area
            type="monotone"
            dataKey="profit"
            stroke="none"
            fill="url(#profitAreaGrad)"
            baseLine={0}
          />

          {/* Loss area fill */}
          <Area
            type="monotone"
            dataKey="loss"
            stroke="none"
            fill="url(#lossAreaGrad)"
            baseLine={0}
          />

          {/* Main expiry line - colored by P&L */}
          <Line
            type="monotone"
            dataKey="current"
            name="On Expiry"
            stroke="#10b981"
            strokeWidth={2.5}
            dot={false}
            activeDot={{ r: 4, fill: '#10b981' }}
          />

          {/* Combined/Target line (if proposed trades exist) */}
          {hasProposedTrades && (
            <Line
              type="monotone"
              dataKey="combined"
              name="On Target"
              stroke="#3b82f6"
              strokeWidth={2}
              strokeDasharray="6 3"
              dot={false}
              activeDot={{ r: 4, fill: '#3b82f6' }}
            />
          )}

          {/* Zoom selection area */}
          {refAreaLeft && refAreaRight && (
            <ReferenceArea
              x1={refAreaLeft}
              x2={refAreaRight}
              strokeOpacity={0.3}
              fill="#3b82f6"
              fillOpacity={0.3}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>

      {/* Legend */}
      <Box sx={{
        display: 'flex',
        justifyContent: 'center',
        gap: 4,
        mt: 1.5,
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box sx={{
            width: 20,
            height: 3,
            background: 'linear-gradient(90deg, #ef4444 0%, #ef4444 50%, #10b981 50%, #10b981 100%)',
            borderRadius: 1
          }} />
          <Typography variant="caption" sx={{ color: '#94a3b8' }}>On Expiry</Typography>
        </Box>
        {hasProposedTrades && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box sx={{
              width: 20,
              height: 3,
              bgcolor: '#3b82f6',
              borderRadius: 1,
            }} />
            <Typography variant="caption" sx={{ color: '#94a3b8' }}>On Target Date</Typography>
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
  const [targetDays, setTargetDays] = useState(0); // 0 = today; increases toward expiry

  // Enhanced chart toggle state
  const [thetaFanEnabled, setThetaFanEnabled] = useState(false);
  const [deltaProfileEnabled, setDeltaProfileEnabled] = useState(false);

  // Zoom state for payoff chart
  const [zoomDomain, setZoomDomain] = useState(null);

  // Multiplier state - like Sensibull
  const [multiplier, setMultiplier] = useState(1);
  const [multiplierMode, setMultiplierMode] = useState('normal'); // 'normal' or 'gcd'

  // Helper: Calculate GCD (Greatest Common Divisor) for ratio calculation
  const calculateGCD = (a, b) => {
    a = Math.abs(a);
    b = Math.abs(b);
    while (b !== 0) {
      const temp = b;
      b = a % b;
      a = temp;
    }
    return a;
  };

  // Calculate GCD of all proposed trades quantities
  const getTradesGCD = useCallback((trades) => {
    if (trades.length === 0) return 1;
    if (trades.length === 1) return Math.abs(trades[0].quantity || 1);

    let gcd = Math.abs(trades[0].quantity || 1);
    for (let i = 1; i < trades.length; i++) {
      gcd = calculateGCD(gcd, Math.abs(trades[i].quantity || 1));
    }
    return gcd === 0 ? 1 : gcd;
  }, []);

  // Get the GCD of current proposed trades
  const tradesGCD = useMemo(() => {
    return getTradesGCD(proposedTrades);
  }, [proposedTrades, getTradesGCD]);

  // Calculate multiplied trades for execution
  const getMultipliedTrades = useCallback(() => {
    return proposedTrades.map(trade => {
      const baseQty = trade.quantity || 1;
      let finalQty;

      if (multiplierMode === 'gcd') {
        // GCD mode: Scale based on ratio (qty / GCD * multiplier)
        finalQty = (baseQty / tradesGCD) * multiplier;
      } else {
        // Normal mode: Simple multiplication
        finalQty = baseQty * multiplier;
      }

      return {
        ...trade,
        quantity: Math.round(finalQty),
        originalQuantity: baseQty,
      };
    });
  }, [proposedTrades, multiplier, multiplierMode, tradesGCD]);

  // Get total order count for display
  const totalOrderCount = useMemo(() => {
    const multipliedTrades = getMultipliedTrades();
    return multipliedTrades.reduce((sum, t) => sum + (t.quantity || 1), 0);
  }, [getMultipliedTrades]);

  // Get ratio display for GCD mode
  const ratioDisplay = useMemo(() => {
    if (proposedTrades.length === 0) return '';
    const ratios = proposedTrades.map(t => (t.quantity || 1) / tradesGCD);
    return ratios.join(':');
  }, [proposedTrades, tradesGCD]);

  // Memoized multiplied trades for payoff calculation
  const multipliedTradesForPayoff = useMemo(() => {
    return proposedTrades.map(trade => {
      const baseQty = trade.quantity || 1;
      let finalQty;

      if (multiplierMode === 'gcd') {
        // GCD mode: Scale based on ratio (qty / GCD * multiplier)
        finalQty = Math.round((baseQty / tradesGCD) * multiplier);
      } else {
        // Normal mode: Simple multiplication
        finalQty = baseQty * multiplier;
      }

      return {
        ...trade,
        quantity: finalQty,
        originalQuantity: baseQty,
      };
    });
  }, [proposedTrades, multiplier, multiplierMode, tradesGCD]);

  // Calculate payoff - now uses multiplied trades + BS engine options
  const payoffData = usePayoffCalculation(
    currentPositions,
    multipliedTradesForPayoff,
    spotPrice,
    {
      enabled: open,
      thetaFanEnabled,
      deltaProfileEnabled,
      daysToTarget: targetDays,
    }
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

  // Get available expiries from positions
  const availableExpiries = useMemo(() => {
    const expiries = new Set();
    currentPositions.forEach(pos => {
      const parsed = parseSymbol(pos.product_symbol);
      if (parsed.expiry) {
        expiries.add(parsed.expiry);
      }
    });
    return Array.from(expiries).sort();
  }, [currentPositions]);

  // Auto-select first expiry if none selected
  React.useEffect(() => {
    if (availableExpiries.length > 0 && !selectedExpiry) {
      setSelectedExpiry(availableExpiries[0]);
    }
  }, [availableExpiries, selectedExpiry]);

  // Filter positions by selected expiry
  const filteredPositions = useMemo(() => {
    if (!selectedExpiry) return currentPositions;
    return currentPositions.filter(pos => {
      const parsed = parseSymbol(pos.product_symbol);
      return parsed.expiry === selectedExpiry;
    });
  }, [currentPositions, selectedExpiry]);

  // Calculate totals for filtered positions only
  const filteredTotals = useMemo(() => {
    let booked = 0;
    let unbooked = 0;

    filteredPositions.forEach(pos => {
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
  }, [filteredPositions]);

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

  // Handle update trade strike (for +/- buttons)
  const handleUpdateTradeStrike = useCallback((oldStrike, type, side, newStrike) => {
    setProposedTrades(prev =>
      prev.map(t => {
        if (t.strike === oldStrike && t.type === type && t.side === side) {
          // Update symbol with new strike
          const typePrefix = t.type === 'call' ? 'C' : 'P';
          const underlying = derivedUnderlying || 'BTC';
          const expiry = t.expiry || selectedExpiry;
          const expiryShort = expiry?.length === 8
            ? expiry.slice(0, 4) + expiry.slice(6, 8)
            : expiry;
          const newSymbol = `${typePrefix}-${underlying}-${newStrike}-${expiryShort}`;

          return {
            ...t,
            strike: newStrike,
            symbol: newSymbol,
          };
        }
        return t;
      })
    );
  }, [derivedUnderlying, selectedExpiry]);

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
      {/* Header Bar - Like Sensibull with Asset + Tabs + Metrics */}
      <Box sx={{
        display: 'flex',
        alignItems: 'center',
        px: 2,
        py: 0.75,
        bgcolor: 'rgba(15, 23, 42, 0.98)',
        borderBottom: `1px solid ${COLORS.border}`,
        gap: 2,
      }}>
        {/* Left: Asset Info */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <ChartIcon sx={{ color: COLORS.primary, fontSize: 18 }} />
          <Typography variant="body2" sx={{ color: COLORS.text, fontWeight: 600 }}>
            Position Adjustment
          </Typography>
          <Chip
            label={derivedUnderlying}
            size="small"
            sx={{ bgcolor: 'rgba(59, 130, 246, 0.2)', color: COLORS.primary, height: 20, fontSize: '0.7rem' }}
          />
        </Box>

        {/* Price + Change */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="body2" sx={{ color: COLORS.text, fontWeight: 600 }}>
            {derivedUnderlying} ${spotPrice?.toLocaleString() || '-'}
          </Typography>
          <Chip
            label="0.14%"
            size="small"
            sx={{
              bgcolor: 'rgba(34, 197, 94, 0.15)',
              color: COLORS.profit,
              height: 18,
              fontSize: '0.65rem',
            }}
          />
        </Box>

        {/* Info & Settings buttons */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Button size="small" variant="outlined" sx={{
            borderColor: COLORS.border,
            color: COLORS.textSecondary,
            minWidth: 40,
            fontSize: '0.7rem',
            py: 0.25,
          }}>
            Info
          </Button>
          <IconButton size="small" sx={{ color: COLORS.textSecondary }}>
            <SettingsIcon sx={{ fontSize: 16 }} />
          </IconButton>
          <IconButton size="small" onClick={onClose} sx={{ color: COLORS.textSecondary }}>
            <CloseIcon sx={{ fontSize: 16 }} />
          </IconButton>
        </Box>

        {/* Spacer */}
        <Box sx={{ flex: 1 }} />

        {/* Key Metrics - Right Side */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="caption" sx={{ color: COLORS.textSecondary, fontSize: '0.6rem', display: 'block' }}>Profit left</Typography>
            <Typography variant="body2" sx={{ color: COLORS.profit, fontWeight: 600, fontSize: '0.8rem' }}>
              {payoffData.formattedMetrics?.current?.maxProfit || '$0'}
            </Typography>
          </Box>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="caption" sx={{ color: COLORS.textSecondary, fontSize: '0.6rem', display: 'block' }}>Loss left</Typography>
            <Typography variant="body2" sx={{ color: COLORS.loss, fontWeight: 600, fontSize: '0.8rem' }}>
              {payoffData.formattedMetrics?.current?.maxLoss || '$0'}
            </Typography>
          </Box>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="caption" sx={{ color: COLORS.textSecondary, fontSize: '0.6rem', display: 'block' }}>Reward/Risk</Typography>
            <Typography variant="body2" sx={{ color: COLORS.text, fontWeight: 600, fontSize: '0.8rem' }}>
              {payoffData.formattedMetrics?.current?.riskReward || '0'}
            </Typography>
          </Box>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="caption" sx={{ color: COLORS.textSecondary, fontSize: '0.6rem', display: 'block' }}>POP</Typography>
            <Typography variant="body2" sx={{ color: COLORS.text, fontWeight: 600, fontSize: '0.8rem' }}>
              {payoffData.formattedMetrics?.current?.pop || '0%'}
            </Typography>
          </Box>
        </Box>
      </Box>

      {/* Main Content - 3 column layout like Sensibull */}
      <Box sx={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* LEFT PANEL - Options Chain (when open) OR Positions */}
        {showChainPanel ? (
          <Box sx={{
            width: '33%',
            minWidth: 450,
            maxWidth: 550,
            flexShrink: 0,
            display: 'flex',
            flexDirection: 'column',
            borderRight: `1px solid ${COLORS.border}`,
            bgcolor: COLORS.background,
          }}>
            <SlidingOptionsChainPanel
              open={true}
              onClose={() => setShowChainPanel(false)}
              underlying={derivedUnderlying}
              spotPrice={spotPrice}
              proposedTrades={proposedTrades}
              onAddTrade={handleAddTrade}
              onRemoveTrade={handleRemoveTrade}
              selectedExpiry={selectedExpiry}
              onExpiryChange={setSelectedExpiry}
              inline={true}
            />
          </Box>
        ) : (
          /* Positions Panel - Wider like Sensibull */
          <Box sx={{
            width: 380,
            flexShrink: 0,
            display: 'flex',
            flexDirection: 'column',
            borderRight: `1px solid ${COLORS.border}`,
            bgcolor: 'rgba(15, 23, 42, 0.6)',
          }}>
            {/* Header */}
            <Box sx={{
              px: 1.5,
              py: 1,
              borderBottom: `1px solid ${COLORS.border}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}>
              <Typography variant="body2" sx={{ color: COLORS.text, fontWeight: 600 }}>
                {derivedUnderlying} Positions
              </Typography>
              <Typography
                variant="caption"
                sx={{ color: COLORS.primary, cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
              >
                Clear Positions
              </Typography>
            </Box>

            {/* Action Buttons Row */}
            <Box sx={{ display: 'flex', gap: 1, p: 1, borderBottom: `1px solid ${COLORS.border}` }}>
              <Button
                variant="outlined"
                size="small"
                disabled={selectedPositions.length === 0}
                sx={{
                  borderColor: COLORS.loss,
                  color: COLORS.loss,
                  fontSize: '0.75rem',
                  px: 2,
                  '&:hover': { borderColor: COLORS.loss, bgcolor: 'rgba(239, 68, 68, 0.1)' },
                }}
              >
                Exit Positions ({selectedPositions.length})
              </Button>
              <Button
                variant="contained"
                size="small"
                onClick={() => setShowChainPanel(true)}
                sx={{
                  bgcolor: COLORS.primary,
                  color: '#fff',
                  fontSize: '0.75rem',
                  px: 2,
                  '&:hover': { bgcolor: '#2563eb' },
                }}
              >
                Add New Trade
              </Button>
            </Box>

            {/* Filter Pills - Expiry Selector */}
            <Box sx={{ display: 'flex', gap: 0.5, p: 1, borderBottom: `1px solid ${COLORS.border}`, flexWrap: 'wrap' }}>
              {availableExpiries.map((expiry) => (
                <Chip
                  key={expiry}
                  label={formatExpiryShort(expiry)}
                  size="small"
                  onClick={() => setSelectedExpiry(expiry)}
                  sx={{
                    bgcolor: selectedExpiry === expiry ? 'rgba(59, 130, 246, 0.2)' : 'transparent',
                    color: selectedExpiry === expiry ? COLORS.primary : COLORS.textSecondary,
                    border: `1px solid ${selectedExpiry === expiry ? COLORS.primary : COLORS.border}`,
                    height: 24,
                    fontSize: '0.7rem',
                    cursor: 'pointer',
                    '&:hover': { bgcolor: 'rgba(59, 130, 246, 0.1)' },
                  }}
                />
              ))}
              {availableExpiries.length === 0 && (
                <Typography variant="caption" sx={{ color: COLORS.textSecondary }}>No expiries</Typography>
              )}
            </Box>

            {/* P&L Summary Row */}
            <Box sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 2,
              px: 1.5,
              py: 1,
              borderBottom: `1px solid ${COLORS.border}`,
              bgcolor: 'rgba(0,0,0,0.2)',
            }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Typography variant="caption" sx={{ color: COLORS.textSecondary }}>Booked</Typography>
                <Typography variant="caption" sx={{ color: filteredTotals.booked >= 0 ? COLORS.profit : COLORS.loss, fontWeight: 600 }}>
                  {filteredTotals.booked >= 0 ? '+' : ''}{filteredTotals.booked.toFixed(0)}
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Typography variant="caption" sx={{ color: COLORS.textSecondary }}>Unbooked</Typography>
                <Typography variant="caption" sx={{ color: filteredTotals.unbooked >= 0 ? COLORS.profit : COLORS.loss, fontWeight: 600 }}>
                  {filteredTotals.unbooked >= 0 ? '+' : ''}{filteredTotals.unbooked.toFixed(0)}
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Typography variant="caption" sx={{ color: COLORS.textSecondary }}>Total P&L</Typography>
                <Typography variant="caption" sx={{ color: filteredTotals.total >= 0 ? COLORS.profit : COLORS.loss, fontWeight: 600 }}>
                  {filteredTotals.total >= 0 ? '+' : ''}{filteredTotals.total.toFixed(0)}
                </Typography>
              </Box>
            </Box>

            {/* Column Headers */}
            <Box sx={{
              display: 'flex',
              alignItems: 'center',
              px: 1,
              py: 0.5,
              borderBottom: `1px solid ${COLORS.border}`,
              bgcolor: 'rgba(0,0,0,0.15)',
            }}>
              <Checkbox
                size="small"
                checked={selectedPositions.length === filteredPositions.length && filteredPositions.length > 0}
                indeterminate={selectedPositions.length > 0 && selectedPositions.length < filteredPositions.length}
                onChange={(e) => {
                  if (e.target.checked) {
                    setSelectedPositions([...filteredPositions]);
                  } else {
                    setSelectedPositions([]);
                  }
                }}
                sx={{ color: COLORS.textSecondary, p: 0.25 }}
              />
              <Typography variant="caption" sx={{ color: COLORS.textSecondary, flex: 1, fontSize: '0.7rem', ml: 0.5 }}>
                Instrument
              </Typography>
              <Typography variant="caption" sx={{ color: COLORS.textSecondary, width: 45, textAlign: 'center', fontSize: '0.7rem' }}>
                Qty
              </Typography>
              <Typography variant="caption" sx={{ color: COLORS.textSecondary, width: 60, textAlign: 'right', fontSize: '0.7rem' }}>
                Avg
              </Typography>
              <Typography variant="caption" sx={{ color: COLORS.textSecondary, width: 60, textAlign: 'right', fontSize: '0.7rem' }}>
                LTP
              </Typography>
            </Box>

            {/* Positions List */}
            <Box sx={{ flex: 1, overflow: 'auto' }}>
              {filteredPositions.map((pos, idx) => {
                const parsed = parseSymbol(pos.product_symbol);
                const isSelected = selectedPositions.some(p => p.product_symbol === pos.product_symbol);
                const size = pos.size || 0;
                const isBuy = size > 0;
                const entryPrice = Math.abs(pos.entry_price || 0);
                const markPrice = pos.mark_price || entryPrice;

                return (
                  <Box
                    key={pos.product_symbol || idx}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      px: 1,
                      py: 0.75,
                      borderBottom: `1px solid ${COLORS.border}`,
                      '&:hover': { bgcolor: 'rgba(255,255,255,0.03)' },
                    }}
                  >
                    <Checkbox
                      size="small"
                      checked={isSelected}
                      onChange={(e) => handleSelectPosition(pos, e.target.checked)}
                      sx={{ color: COLORS.textSecondary, p: 0.25 }}
                    />
                    <Box sx={{ flex: 1, ml: 0.5, display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <Chip
                        label={isBuy ? 'B' : 'S'}
                        size="small"
                        sx={{
                          bgcolor: isBuy ? 'rgba(34, 197, 94, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                          color: isBuy ? COLORS.buy : COLORS.sell,
                          fontWeight: 'bold',
                          fontSize: '0.6rem',
                          height: 18,
                          minWidth: 20,
                        }}
                      />
                      <Chip
                        label="NRML"
                        size="small"
                        sx={{
                          bgcolor: 'rgba(100, 116, 139, 0.3)',
                          color: COLORS.textSecondary,
                          fontSize: '0.55rem',
                          height: 16,
                        }}
                      />
                      <Typography variant="caption" sx={{ color: COLORS.text, fontSize: '0.75rem' }}>
                        {formatExpiryShort(parsed.expiry)} {parsed.strike.toLocaleString()} {parsed.type}
                      </Typography>
                    </Box>
                    <Typography variant="caption" sx={{ width: 45, textAlign: 'center', color: COLORS.text, fontWeight: 500, fontSize: '0.75rem' }}>
                      {Math.abs(size)}
                    </Typography>
                    <Typography variant="caption" sx={{ width: 60, textAlign: 'right', color: COLORS.textSecondary, fontSize: '0.75rem' }}>
                      {entryPrice.toFixed(2)}
                    </Typography>
                    <Typography variant="caption" sx={{ width: 60, textAlign: 'right', color: COLORS.text, fontSize: '0.75rem' }}>
                      {markPrice.toFixed(2)}
                    </Typography>
                  </Box>
                );
              })}

              {filteredPositions.length === 0 && (
                <Box sx={{ p: 3, textAlign: 'center' }}>
                  <Typography variant="body2" sx={{ color: COLORS.textSecondary }}>
                    No positions for selected expiry
                  </Typography>
                </Box>
              )}
            </Box>
          </Box>
        )}

        {/* RIGHT PANEL - Chart & Metrics */}
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Tabs Row - Single instance */}
          <Box sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            px: 2,
            py: 0.5,
            borderBottom: `1px solid ${COLORS.border}`,
            bgcolor: 'rgba(15, 23, 42, 0.4)',
          }}>
            <Tabs
              value={activeTab}
              onChange={(e, v) => setActiveTab(v)}
              sx={{
                minHeight: 32,
                '& .MuiTab-root': {
                  color: COLORS.textSecondary,
                  textTransform: 'none',
                  minWidth: 90,
                  minHeight: 32,
                  fontSize: '0.8rem',
                  py: 0.25,
                },
                '& .Mui-selected': { color: COLORS.primary },
                '& .MuiTabs-indicator': { bgcolor: COLORS.primary, height: 2 },
              }}
            >
              <Tab label="Payoff Graph" />
              <Tab label="P&L Table" />
              <Tab label="Greeks" />
              <Tab label="Stress Test" />
              <Tab label="Strategy Chart" />
            </Tabs>
          </Box>

          {/* Chart Area */}
          <Box sx={{ flex: 1, p: 1.5, overflow: 'auto' }}>

            {/* Payoff Graph Tab */}
            {activeTab === 0 && (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {/* Chart Section - Full width now */}
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
                    {zoomDomain && (
                      <>
                        <Button
                          size="small"
                          startIcon={<ZoomOutIcon />}
                          onClick={() => {
                            // Zoom out by 25%
                            const range = zoomDomain[1] - zoomDomain[0];
                            const center = (zoomDomain[0] + zoomDomain[1]) / 2;
                            const newRange = range * 1.5;
                            setZoomDomain([center - newRange / 2, center + newRange / 2]);
                          }}
                          sx={{ color: COLORS.textSecondary }}
                        >
                          Zoom Out
                        </Button>
                        <Button
                          size="small"
                          startIcon={<ResetZoomIcon />}
                          onClick={() => setZoomDomain(null)}
                          sx={{ color: COLORS.primary }}
                        >
                          Reset Zoom
                        </Button>
                      </>
                    )}
                    {!zoomDomain && (
                      <Typography variant="caption" sx={{ color: COLORS.textSecondary, fontStyle: 'italic' }}>
                        Drag on chart to zoom
                      </Typography>
                    )}
                  </Box>

                  <EnhancedPayoffChart
                    chartData={payoffData.chartData}
                    thetaFanData={payoffData.thetaFanData}
                    deltaProfileData={payoffData.deltaProfileData}
                    probabilityData={payoffData.probabilityData}
                    spotPrice={spotPrice}
                    hasProposedTrades={proposedTrades.length > 0}
                    breakevens={proposedTrades.length > 0
                      ? payoffData.combinedMetrics?.breakevens
                      : payoffData.currentMetrics?.breakevens}
                    zoomDomain={zoomDomain}
                    onZoomChange={setZoomDomain}
                    thetaFanEnabled={thetaFanEnabled}
                    onThetaFanToggle={setThetaFanEnabled}
                    deltaProfileEnabled={deltaProfileEnabled}
                    onDeltaProfileToggle={setDeltaProfileEnabled}
                  />

                  {/* Projected P&L at current spot — uses todayBs for real mark-to-market value */}
                  {(() => {
                    // Find the todayBs P&L at the current spot price
                    const spotPoint = payoffData.chartData?.find(
                      d => Math.abs(d.price - (spotPrice || 0)) < (spotPrice || 1) * 0.01
                    );
                    const projectedPnl = spotPoint?.todayBs ?? spotPoint?.combined ?? spotPoint?.current ?? null;
                    const isLoss = projectedPnl != null && projectedPnl < 0;
                    return (
                      <Box sx={{
                        mt: 2,
                        p: 1.5,
                        bgcolor: isLoss ? 'rgba(239, 68, 68, 0.12)' : 'rgba(34, 197, 94, 0.1)',
                        borderRadius: 1,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: 1,
                      }}>
                        <Typography variant="body2" sx={{ color: isLoss ? COLORS.loss : COLORS.profit }}>
                          {targetDays === 0 ? 'Current P&L at spot' : `P&L at spot in ${targetDays}D`}:{' '}
                          <strong>
                            {projectedPnl != null
                              ? `${projectedPnl >= 0 ? '+' : ''}$${projectedPnl.toFixed(2)}`
                              : '-'}
                          </strong>
                          {isLoss && ' ⚠'}
                        </Typography>
                        <Typography variant="caption" sx={{ color: COLORS.textSecondary }}>
                          Max profit at expiry: {payoffData.formattedMetrics?.combined?.maxProfit
                            || payoffData.formattedMetrics?.current?.maxProfit || '-'}
                        </Typography>
                      </Box>
                    );
                  })()}
                </Paper>

                {/* Bottom Section: Target Price, then Metrics + Proposed Trades below */}
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                  {/* Target Price + Date Row */}
                  <Paper sx={{
                    p: 1.5,
                    bgcolor: COLORS.cardBg,
                    border: `1px solid ${COLORS.border}`,
                    borderRadius: 2,
                  }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
                      <Typography variant="body2" sx={{ color: COLORS.text }}>
                        {derivedUnderlying} Target
                      </Typography>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Chip
                          label={`${targetPrice && spotPrice ? ((targetPrice / spotPrice - 1) * 100).toFixed(1) : '0.0'}%`}
                          size="small"
                          sx={{ bgcolor: 'rgba(255,255,255,0.1)', color: COLORS.text }}
                        />
                        <IconButton size="small" sx={{ color: COLORS.textSecondary }} onClick={() => setTargetPrice(p => p - (derivedUnderlying === 'ETH' ? 100 : 500))}><RemoveIcon fontSize="small" /></IconButton>
                        <TextField
                          size="small"
                          value={targetPrice || spotPrice || ''}
                          onChange={(e) => setTargetPrice(parseFloat(e.target.value) || 0)}
                          sx={{
                            width: 100,
                            '& input': { color: COLORS.text, textAlign: 'center', py: 0.5 },
                            '& .MuiOutlinedInput-root': {
                              '& fieldset': { borderColor: COLORS.border },
                            },
                          }}
                        />
                        <IconButton size="small" sx={{ color: COLORS.textSecondary }} onClick={() => setTargetPrice(p => p + (derivedUnderlying === 'ETH' ? 100 : 500))}><AddIcon fontSize="small" /></IconButton>
                      </Box>
                      <Button size="small" sx={{ color: COLORS.primary }} onClick={() => setTargetPrice(spotPrice || 0)}>Reset</Button>

                      {/* Date slider — controls the "On Target Date" blue line */}
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, ml: 'auto' }}>
                        <Typography variant="caption" sx={{ color: COLORS.textSecondary, whiteSpace: 'nowrap' }}>
                          Date:
                        </Typography>
                        <input
                          type="range"
                          min={0}
                          max={Math.max(1, Math.floor(payoffData.ivAndExpiry?.daysToExpiry || 30) - 1)}
                          value={targetDays}
                          onChange={(e) => setTargetDays(Number(e.target.value))}
                          style={{ width: 100, accentColor: '#3b82f6', cursor: 'pointer' }}
                        />
                        <Typography variant="caption" sx={{ color: '#3b82f6', fontWeight: 600, minWidth: 70 }}>
                          {targetDays === 0 ? 'Today' : `${targetDays}D from now`}
                        </Typography>
                        {targetDays > 0 && (
                          <Button size="small" sx={{ color: COLORS.textSecondary, fontSize: '0.65rem', py: 0.25, minWidth: 0 }} onClick={() => setTargetDays(0)}>
                            Reset
                          </Button>
                        )}
                      </Box>
                    </Box>
                    <MarginImpactRow
                      netDebitCredit={payoffData.netDebitCredit}
                      spotPrice={spotPrice}
                    />
                  </Paper>

                  {/* Metrics + Proposed Trades Row */}
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                    {/* Position Metrics - Compact horizontal layout */}
                    <Paper sx={{
                      p: 1.5,
                      bgcolor: COLORS.cardBg,
                      border: `1px solid ${COLORS.border}`,
                      borderRadius: 2,
                    }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                        <Typography variant="caption" sx={{ color: COLORS.textSecondary, fontWeight: 600 }}>
                          Position Metrics {proposedTrades.length > 0 && '(After Adjustment)'}
                        </Typography>
                        {proposedTrades.length > 0 && (
                          <Chip
                            label="Combined"
                            size="small"
                            sx={{ bgcolor: 'rgba(59, 130, 246, 0.2)', color: COLORS.primary, height: 18, fontSize: '0.65rem' }}
                          />
                        )}
                      </Box>
                      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                        <Box>
                          <Typography variant="caption" sx={{ color: COLORS.textSecondary, fontSize: '0.65rem' }}>Max Profit</Typography>
                          <Typography variant="body2" sx={{ color: COLORS.profit, fontWeight: 600, fontSize: '0.8rem' }}>
                            {proposedTrades.length > 0
                              ? payoffData.formattedMetrics?.combined?.maxProfit
                              : payoffData.formattedMetrics?.current?.maxProfit || '-'}
                          </Typography>
                        </Box>
                        <Box>
                          <Typography variant="caption" sx={{ color: COLORS.textSecondary, fontSize: '0.65rem' }}>Max Loss</Typography>
                          <Typography variant="body2" sx={{ color: COLORS.loss, fontWeight: 600, fontSize: '0.8rem' }}>
                            {proposedTrades.length > 0
                              ? payoffData.formattedMetrics?.combined?.maxLoss
                              : payoffData.formattedMetrics?.current?.maxLoss || '-'}
                          </Typography>
                        </Box>
                        <Box>
                          <Typography variant="caption" sx={{ color: COLORS.textSecondary, fontSize: '0.65rem' }}>Risk/Reward</Typography>
                          <Typography variant="body2" sx={{ color: COLORS.text, fontWeight: 600, fontSize: '0.8rem' }}>
                            {proposedTrades.length > 0
                              ? payoffData.formattedMetrics?.combined?.riskReward
                              : payoffData.formattedMetrics?.current?.riskReward || '-'}
                          </Typography>
                        </Box>
                        <Box>
                          <Typography variant="caption" sx={{ color: COLORS.textSecondary, fontSize: '0.65rem' }}>PoP</Typography>
                          <Typography variant="body2" sx={{ color: COLORS.text, fontWeight: 600, fontSize: '0.8rem' }}>
                            {proposedTrades.length > 0
                              ? payoffData.formattedMetrics?.combined?.pop
                              : payoffData.formattedMetrics?.current?.pop || '-'}
                          </Typography>
                        </Box>
                        <Box>
                          <Typography variant="caption" sx={{ color: COLORS.textSecondary, fontSize: '0.65rem' }}>Breakeven</Typography>
                          <Typography variant="body2" sx={{ color: COLORS.primary, fontWeight: 600, fontSize: '0.8rem' }}>
                            {proposedTrades.length > 0
                              ? (payoffData.formattedMetrics?.combined?.breakevens?.[0] || '-')
                              : (payoffData.formattedMetrics?.current?.breakevens?.[0] || '-')}
                          </Typography>
                        </Box>
                      </Box>
                      {/* Greeks Row */}
                      <Box sx={{ display: 'flex', gap: 2, mt: 1, pt: 1, borderTop: `1px solid ${COLORS.border}` }}>
                        <Box>
                          <Typography variant="caption" sx={{ color: COLORS.textSecondary, fontSize: '0.65rem' }}>Net Delta</Typography>
                          <Typography variant="body2" sx={{ color: COLORS.text, fontSize: '0.75rem' }}>
                            {proposedTrades.length > 0
                              ? payoffData.formattedMetrics?.combined?.netDelta
                              : payoffData.formattedMetrics?.current?.netDelta || '-'}
                          </Typography>
                        </Box>
                        <Box>
                          <Typography variant="caption" sx={{ color: COLORS.textSecondary, fontSize: '0.65rem' }}>Net Theta</Typography>
                          <Typography variant="body2" sx={{ color: COLORS.text, fontSize: '0.75rem' }}>
                            {proposedTrades.length > 0
                              ? payoffData.formattedMetrics?.combined?.netTheta
                              : payoffData.formattedMetrics?.current?.netTheta || '-'}
                          </Typography>
                        </Box>
                        <Box>
                          <Typography variant="caption" sx={{ color: COLORS.textSecondary, fontSize: '0.65rem' }}>Net Vega</Typography>
                          <Typography variant="body2" sx={{ color: COLORS.text, fontSize: '0.75rem' }}>
                            {proposedTrades.length > 0
                              ? payoffData.formattedMetrics?.combined?.netVega
                              : payoffData.formattedMetrics?.current?.netVega || '-'}
                          </Typography>
                        </Box>
                        <Box>
                          <Typography variant="caption" sx={{ color: COLORS.textSecondary, fontSize: '0.65rem' }}>Net Premium</Typography>
                          <Typography variant="body2" sx={{ color: COLORS.text, fontSize: '0.75rem' }}>
                            {proposedTrades.length > 0
                              ? payoffData.formattedMetrics?.combined?.netPremium
                              : payoffData.formattedMetrics?.current?.netPremium || '-'}
                          </Typography>
                        </Box>
                      </Box>
                    </Paper>

                    {/* Proposed Trades Panel - Sensibull Style with Multiplier */}
                    {proposedTrades.length > 0 && (
                      <Paper sx={{
                        p: 2,
                        bgcolor: COLORS.cardBg,
                        border: `1px solid ${COLORS.border}`,
                        borderRadius: 2,
                      }}>
                        {/* Header Row */}
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                            <Typography variant="subtitle2" sx={{ color: COLORS.text, fontWeight: 600 }}>
                              New Strategy
                            </Typography>
                            <Chip
                              label={`${proposedTrades.length} selected`}
                              size="small"
                              sx={{ bgcolor: 'rgba(59, 130, 246, 0.2)', color: COLORS.primary, height: 22 }}
                            />
                          </Box>
                          <Box sx={{ display: 'flex', gap: 1 }}>
                            <Button
                              size="small"
                              color="error"
                              onClick={handleClearAll}
                              sx={{ fontSize: '0.75rem' }}
                            >
                              Clear New Trades
                            </Button>
                            <ScenarioManager
                              proposedTrades={proposedTrades}
                              metrics={payoffData.formattedMetrics}
                              onRestoreScenario={(legs) => {
                                // Clear existing trades first
                                handleClearAll();
                                // Restore saved legs
                                legs.forEach(leg => {
                                  handleAddTrade(leg);
                                });
                              }}
                            />
                          </Box>
                        </Box>

                        {/* Trades Table - Sensibull Style */}
                        <NetDebitCreditBar netDebitCredit={payoffData.netDebitCredit} />
                        <TableContainer sx={{ mb: 2, maxHeight: 180, overflow: 'auto' }}>
                          <Table size="small">
                            <TableHead>
                              <TableRow>
                                <TableCell sx={{ color: COLORS.textSecondary, fontWeight: 600, fontSize: '0.75rem', py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>B/S</TableCell>
                                <TableCell sx={{ color: COLORS.textSecondary, fontWeight: 600, fontSize: '0.75rem', py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>Expiry</TableCell>
                                <TableCell sx={{ color: COLORS.textSecondary, fontWeight: 600, fontSize: '0.75rem', py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>Strike</TableCell>
                                <TableCell sx={{ color: COLORS.textSecondary, fontWeight: 600, fontSize: '0.75rem', py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>Type</TableCell>
                                <TableCell align="center" sx={{ color: COLORS.textSecondary, fontWeight: 600, fontSize: '0.75rem', py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>Qty</TableCell>
                                <TableCell align="right" sx={{ color: COLORS.textSecondary, fontWeight: 600, fontSize: '0.75rem', py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>Price</TableCell>
                              </TableRow>
                            </TableHead>
                            <TableBody>
                              {proposedTrades.map((trade, idx) => {
                                // Calculate final quantity based on multiplier mode
                                const baseQty = trade.quantity || 1;
                                const finalQty = multiplierMode === 'gcd'
                                  ? Math.round((baseQty / tradesGCD) * multiplier)
                                  : baseQty * multiplier;

                                return (
                                  <TableRow key={idx} hover>
                                    <TableCell sx={{ py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
                                      <Chip
                                        label={trade.side === 'buy' ? 'B' : 'S'}
                                        size="small"
                                        sx={{
                                          bgcolor: trade.side === 'buy' ? 'rgba(34, 197, 94, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                                          color: trade.side === 'buy' ? COLORS.buy : COLORS.sell,
                                          fontWeight: 'bold',
                                          fontSize: '0.7rem',
                                          height: 22,
                                          minWidth: 28,
                                        }}
                                      />
                                    </TableCell>
                                    <TableCell sx={{ py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
                                      <Typography variant="caption" sx={{ color: COLORS.text, fontSize: '0.8rem' }}>
                                        {formatExpiryShort(trade.expiry || selectedExpiry)}
                                      </Typography>
                                    </TableCell>
                                    <TableCell sx={{ py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
                                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                        <IconButton
                                          size="small"
                                          sx={{ p: 0.25, color: COLORS.textSecondary }}
                                          onClick={() => {
                                            // Decrease strike by 100 (or appropriate step)
                                            const step = derivedUnderlying === 'ETH' ? 25 : 100;
                                            const newStrike = trade.strike - step;
                                            handleUpdateTradeStrike(trade.strike, trade.type, trade.side, newStrike);
                                          }}
                                        >
                                          <RemoveIcon sx={{ fontSize: 14 }} />
                                        </IconButton>
                                        <Typography variant="body2" sx={{ color: COLORS.text, fontWeight: 500, minWidth: 50, textAlign: 'center' }}>
                                          {trade.strike?.toLocaleString()}
                                        </Typography>
                                        <IconButton
                                          size="small"
                                          sx={{ p: 0.25, color: COLORS.textSecondary }}
                                          onClick={() => {
                                            // Increase strike by 100 (or appropriate step)
                                            const step = derivedUnderlying === 'ETH' ? 25 : 100;
                                            const newStrike = trade.strike + step;
                                            handleUpdateTradeStrike(trade.strike, trade.type, trade.side, newStrike);
                                          }}
                                        >
                                          <AddIcon sx={{ fontSize: 14 }} />
                                        </IconButton>
                                      </Box>
                                    </TableCell>
                                    <TableCell sx={{ py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
                                      <Chip
                                        label={trade.type === 'call' ? 'CE' : 'PE'}
                                        size="small"
                                        sx={{
                                          bgcolor: trade.type === 'call' ? 'rgba(59, 130, 246, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                                          color: trade.type === 'call' ? '#60a5fa' : '#f87171',
                                          fontSize: '0.7rem',
                                          height: 22,
                                        }}
                                      />
                                    </TableCell>
                                    <TableCell align="center" sx={{ py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
                                      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
                                        <IconButton
                                          size="small"
                                          sx={{ p: 0.25, color: COLORS.textSecondary }}
                                          onClick={() => handleUpdateTradeQty(trade.strike, trade.type, trade.side, Math.max(1, (trade.quantity || 1) - 1))}
                                        >
                                          <RemoveIcon sx={{ fontSize: 14 }} />
                                        </IconButton>
                                        <Box sx={{ textAlign: 'center' }}>
                                          <Typography variant="body2" sx={{ color: COLORS.text, fontWeight: 600, minWidth: 24 }}>
                                            {finalQty}
                                          </Typography>
                                          {multiplier > 1 && (
                                            <Typography variant="caption" sx={{ color: COLORS.textSecondary, fontSize: '0.6rem' }}>
                                              {baseQty}×{multiplier}
                                            </Typography>
                                          )}
                                        </Box>
                                        <IconButton
                                          size="small"
                                          sx={{ p: 0.25, color: COLORS.textSecondary }}
                                          onClick={() => handleUpdateTradeQty(trade.strike, trade.type, trade.side, (trade.quantity || 1) + 1)}
                                        >
                                          <AddIcon sx={{ fontSize: 14 }} />
                                        </IconButton>
                                      </Box>
                                    </TableCell>
                                    <TableCell align="right" sx={{ py: 0.75, borderBottom: `1px solid ${COLORS.border}` }}>
                                      <Typography variant="body2" sx={{ color: COLORS.text }}>
                                        {(trade.premium || trade.ltp || 0).toFixed(1)}
                                      </Typography>
                                    </TableCell>
                                  </TableRow>
                                );
                              })}
                            </TableBody>
                          </Table>
                        </TableContainer>

                        {/* Multiplier Controls - Sensibull Style */}
                        <Box sx={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          pt: 2,
                          borderTop: `1px solid ${COLORS.border}`,
                        }}>
                          {/* Left: Multiplier Mode Toggle + Value */}
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                            <Typography variant="body2" sx={{ color: COLORS.textSecondary }}>
                              Multiplier
                            </Typography>

                            {/* Mode Toggle */}
                            <Box sx={{ display: 'flex', borderRadius: 1, overflow: 'hidden', border: `1px solid ${COLORS.border}` }}>
                              <Button
                                size="small"
                                onClick={() => setMultiplierMode('normal')}
                                sx={{
                                  px: 1.5,
                                  py: 0.5,
                                  minWidth: 70,
                                  borderRadius: 0,
                                  bgcolor: multiplierMode === 'normal' ? 'rgba(59, 130, 246, 0.2)' : 'transparent',
                                  color: multiplierMode === 'normal' ? COLORS.primary : COLORS.textSecondary,
                                  fontSize: '0.75rem',
                                  '&:hover': { bgcolor: 'rgba(59, 130, 246, 0.1)' },
                                }}
                              >
                                Normal
                              </Button>
                              <Button
                                size="small"
                                onClick={() => setMultiplierMode('gcd')}
                                sx={{
                                  px: 1.5,
                                  py: 0.5,
                                  minWidth: 70,
                                  borderRadius: 0,
                                  borderLeft: `1px solid ${COLORS.border}`,
                                  bgcolor: multiplierMode === 'gcd' ? 'rgba(139, 92, 246, 0.2)' : 'transparent',
                                  color: multiplierMode === 'gcd' ? '#a78bfa' : COLORS.textSecondary,
                                  fontSize: '0.75rem',
                                  '&:hover': { bgcolor: 'rgba(139, 92, 246, 0.1)' },
                                }}
                              >
                                GCD Ratio
                              </Button>
                            </Box>

                            {/* Multiplier Value */}
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                              <IconButton
                                size="small"
                                onClick={() => setMultiplier(m => Math.max(1, m - 1))}
                                sx={{
                                  color: COLORS.textSecondary,
                                  bgcolor: 'rgba(255,255,255,0.05)',
                                  '&:hover': { bgcolor: 'rgba(255,255,255,0.1)' },
                                }}
                              >
                                <RemoveIcon fontSize="small" />
                              </IconButton>
                              <TextField
                                size="small"
                                type="number"
                                value={multiplier}
                                onChange={(e) => setMultiplier(Math.max(1, parseInt(e.target.value) || 1))}
                                inputProps={{ min: 1, max: 100 }}
                                sx={{
                                  width: 60,
                                  '& input': { color: COLORS.text, textAlign: 'center', py: 0.5, fontWeight: 600 },
                                  '& .MuiOutlinedInput-root': {
                                    '& fieldset': { borderColor: COLORS.border },
                                  },
                                }}
                              />
                              <IconButton
                                size="small"
                                onClick={() => setMultiplier(m => Math.min(100, m + 1))}
                                sx={{
                                  color: COLORS.textSecondary,
                                  bgcolor: 'rgba(255,255,255,0.05)',
                                  '&:hover': { bgcolor: 'rgba(255,255,255,0.1)' },
                                }}
                              >
                                <AddIcon fontSize="small" />
                              </IconButton>
                            </Box>

                            {/* GCD Ratio Display */}
                            {multiplierMode === 'gcd' && tradesGCD > 1 && (
                              <Chip
                                label={`Ratio ${ratioDisplay}`}
                                size="small"
                                sx={{
                                  bgcolor: 'rgba(139, 92, 246, 0.15)',
                                  color: '#a78bfa',
                                  fontSize: '0.7rem',
                                }}
                              />
                            )}
                          </Box>

                          {/* Right: Total Orders + Execute Button */}
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                            <Box sx={{ textAlign: 'right' }}>
                              <Typography variant="caption" sx={{ color: COLORS.textSecondary, fontSize: '0.65rem', display: 'block' }}>
                                Total Orders
                              </Typography>
                              <Typography variant="body2" sx={{ color: COLORS.text, fontWeight: 600 }}>
                                {totalOrderCount} lots
                              </Typography>
                            </Box>

                            <Button
                              variant="contained"
                              color="primary"
                              size="medium"
                              sx={{
                                px: 4,
                                py: 1,
                                fontSize: '0.9rem',
                                fontWeight: 600,
                                borderRadius: 2,
                              }}
                              onClick={() => setReviewDialogOpen(true)}
                            >
                              Review & Execute
                            </Button>
                          </Box>
                        </Box>
                      </Paper>
                    )}
                  </Box>
                </Box>
              </Box>
            )}

            {/* Other tabs placeholder */}
            {activeTab === 3 && (
              <StressTestMatrix
                stressTestData={payoffData.stressTestData}
                spotPrice={spotPrice}
                hasProposedTrades={proposedTrades.length > 0}
              />
            )}
            {activeTab !== 0 && activeTab !== 3 && (
              <Box sx={{ p: 4, textAlign: 'center' }}>
                <Typography variant="body1" sx={{ color: COLORS.textSecondary }}>
                  {['Payoff Graph', 'P&L Table', 'Greeks', 'Stress Test', 'Strategy Chart'][activeTab]} - Coming soon
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

      {/* Review Dialog */}
      <AdjustmentReviewDialog
        open={reviewDialogOpen}
        onClose={() => setReviewDialogOpen(false)}
        trades={getMultipliedTrades()}
        formattedMetrics={payoffData.formattedMetrics}
        multiplierInfo={{
          mode: multiplierMode,
          value: multiplier,
          gcd: tradesGCD,
          ratio: ratioDisplay,
        }}
        onExecute={(params) => {
          setReviewDialogOpen(false);
          onExecuteComplete?.();
          onClose?.();
        }}
      />
    </Box>
  );
}
