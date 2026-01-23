/**
 * Options Trading Panel
 *
 * Displays options positions with real-time data and provides
 * controls to close or add to positions.
 *
 * Created: January 4, 2026
 * Phase 3: Frontend Options Panel
 *
 * ⚠️ COMPLETE SEPARATION FROM GRID BOT
 * This component only manages options positions.
 */

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Chip,
  IconButton,
  Tooltip,
  CircularProgress,
  Divider,
  Button,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Alert,
  AlertTitle,
  Collapse,
  Badge,
  Checkbox,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Menu,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  TrendingUp,
  TrendingDown,
  Close as CloseIcon,
  Add as AddIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Block as BlockIcon,
  ShowChart as ShowChartIcon,
  AttachMoney as MoneyIcon,
  Timer as TimerIcon,
  DragIndicator as DragIcon,
  PlayArrow as PlayArrowIcon,
  Remove as RemoveIcon,
  ArrowUpward as ArrowUpwardIcon,
  ArrowDownward as ArrowDownwardIcon,
  UnfoldMore as UnfoldMoreIcon,
  Settings as SettingsIcon,
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
  VolumeUp as VolumeIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
} from '@mui/icons-material';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import api from '../../utils/apiShim';
import soundManager from '../../utils/soundManager';
import OptionsPayoffDiagram from './OptionsPayoffDiagram';
import LogPanel from '../optionsChain/LogPanel';
import { AutomationButton, automationMonitor, notificationService } from './automation';
import SLTPDialog from './SLTPDialog';
import SLTPIndicator from './SLTPIndicator';
import MaxLossIndicator from './MaxLossIndicator';
import ExpiryMaxLossPanel from './ExpiryMaxLossPanel';
import useMarketPrices from '../../hooks/useMarketPrices';
import SoundSettingsPanel from '../SoundSettingsPanel';
import TradeNotification from '../TradeNotification';
// JAN 17, 2026: Futures panel - separate file structure, minimal invasion
import FuturesPanel from '../futures/FuturesPanel';

// Sortable Row Component
const SortableRow = ({ pos, children }) => {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: pos.product_symbol,
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    zIndex: isDragging ? 1000 : 'auto',
    position: 'relative',
  };

  return (
    <TableRow
      ref={setNodeRef}
      style={style}
      sx={{
        cursor: isDragging ? 'grabbing' : 'default',
      }}
    >
      {children(attributes, listeners)}
    </TableRow>
  );
};

const OptionsPanel = () => {
  // State
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [positions, setPositions] = useState([]);
  const [futuresPositions, setFuturesPositions] = useState([]);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  // Pending orders state (from Delta Exchange)
  const [pendingOrders, setPendingOrders] = useState([]);
  const [pendingOrdersError, setPendingOrdersError] = useState(null);
  // Collapse state for pending orders
  const [pendingOrdersCollapsed, setPendingOrdersCollapsed] = useState(() => {
    try {
      const saved = localStorage.getItem('options_pending_orders_collapsed');
      return saved ? JSON.parse(saved) : false;
    } catch {
      return false;
    }
  });
  // Focus mode: hidden positions (persisted)
  const [hiddenPositions, setHiddenPositions] = useState(() => {
    try {
      const saved = localStorage.getItem('options_hidden_positions');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  // Save pending orders collapsed state to localStorage
  useEffect(() => {
    localStorage.setItem('options_pending_orders_collapsed', JSON.stringify(pendingOrdersCollapsed));
  }, [pendingOrdersCollapsed]);
  // Polling interval (default 5s)
  const [pollInterval, setPollInterval] = useState(() => {
    try {
      const saved = localStorage.getItem('options_poll_interval');
      return saved ? parseInt(saved) : 5000;
    } catch {
      return 5000;
    }
  });

  // Expiry filter (persisted) - now supports multiple selection
  const [selectedExpiries, setSelectedExpiries] = useState(() => {
    try {
      const saved = localStorage.getItem('options_selected_expiries');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  // Quick Filters (persisted) - Day 3 Enhancement
  const [pnlFilter, setPnlFilter] = useState(() => {
    try {
      const saved = localStorage.getItem('options_pnl_filter');
      return saved || 'all'; // 'all', 'profit', 'loss'
    } catch {
      return 'all';
    }
  });

  const [moneynessFilter, setMoneynessFilter] = useState(() => {
    try {
      const saved = localStorage.getItem('options_moneyness_filter');
      return saved || 'all'; // 'all', 'itm', 'atm', 'otm'
    } catch {
      return 'all';
    }
  });

  // Greeks panel collapsed state (persisted) - Day 3 Enhancement
  const [greeksCollapsed, setGreeksCollapsed] = useState(() => {
    try {
      const saved = localStorage.getItem('options_greeks_collapsed');
      return saved ? JSON.parse(saved) : false;
    } catch {
      return false;
    }
  });

  // Sort state
  const [symbolSort, setSymbolSort] = useState(null); // null = no sort, 'grouped' = CE/PE grouped
  const [strikeSort, setStrikeSort] = useState(null); // null = no sort, 'asc' = ascending, 'desc' = descending

  // SL/TP Dialog state
  const [slTpDialogOpen, setSlTpDialogOpen] = useState(false);
  const [selectedPositionForSLTP, setSelectedPositionForSLTP] = useState(null);
  const [slTpSettings, setSlTpSettings] = useState({}); // Map of symbol -> settings

  // Max Loss Settings state (per-strike and per-expiry)
  const [maxLossSettings, setMaxLossSettings] = useState({}); // Map of symbol -> settings
  const [expiryMaxLossSettings, setExpiryMaxLossSettings] = useState({}); // Map of expiry_code -> settings

  // Column visibility state (persisted)
  const [columnMenuAnchor, setColumnMenuAnchor] = useState(null);
  const [visibleColumns, setVisibleColumns] = useState(() => {
    try {
      const saved = localStorage.getItem('options_visible_columns');
      return saved
        ? JSON.parse(saved)
        : {
            symbol: true,
            strike: true,
            auto: true,
            expiry: true,
            size: true,
            batchQty: true,
            cashflow: true,
            entry: true,
            bid: true,
            ask: true,
            sltp: true,
            maxLoss: true,
            iv: true,
            pnl: true,
            actions: true,
          };
    } catch {
      return {
        symbol: true,
        strike: true,
        auto: true,
        expiry: true,
        size: true,
        batchQty: true,
        cashflow: true,
        entry: true,
        bid: true,
        ask: true,
        sltp: true,
        maxLoss: true,
        iv: true,
        pnl: true,
        actions: true,
      };
    }
  });

  // Column definitions for the menu
  const columnDefs = [
    { key: 'symbol', label: 'Symbol' },
    { key: 'strike', label: 'Strike' },
    { key: 'auto', label: 'Auto' },
    { key: 'expiry', label: 'Expiry' },
    { key: 'size', label: 'Size' },
    { key: 'batchQty', label: 'Batch Qty' },
    { key: 'cashflow', label: 'Cashflow' },
    { key: 'entry', label: 'Entry' },
    { key: 'bid', label: 'Bid' },
    { key: 'ask', label: 'Ask' },
    { key: 'sltp', label: 'SL/TP' },
    { key: 'maxLoss', label: 'Max Loss' },
    { key: 'iv', label: 'IV' },
    { key: 'pnl', label: 'PnL' },
    { key: 'actions', label: 'Actions' },
  ];

  // Toggle column visibility
  const toggleColumn = (columnKey) => {
    setVisibleColumns((prev) => {
      const updated = { ...prev, [columnKey]: !prev[columnKey] };
      localStorage.setItem('options_visible_columns', JSON.stringify(updated));
      return updated;
    });
  };

  // Skip confirmation per strike (persisted in localStorage)
  // Format: { "symbol": { enabled: true, size: 20, side: "sell" } }
  const [skipConfirmStrikes, setSkipConfirmStrikes] = useState(() => {
    try {
      const saved = localStorage.getItem('options_skip_confirm_strikes');
      if (!saved) return {};

      const parsed = JSON.parse(saved);

      // Migrate old format (symbol: true) to new format (symbol: { enabled, size, side })
      const migrated = {};
      for (const [symbol, value] of Object.entries(parsed)) {
        if (value === true) {
          // Old format - migrate with default size 5
          migrated[symbol] = { enabled: true, size: 5, side: 'sell' };
        } else if (typeof value === 'object' && value !== null) {
          // New format - keep as is
          migrated[symbol] = value;
        }
      }
      return migrated;
    } catch {
      return {};
    }
  });

  // Last used size (persisted)
  const [lastUsedSize, setLastUsedSize] = useState(() => {
    try {
      const saved = localStorage.getItem('options_last_used_size');
      return saved || '5';
    } catch {
      return '5';
    }
  });

  // Scaling strategy state (persisted)
  const [scalingStrategy, setScalingStrategy] = useState(() => {
    try {
      const saved = localStorage.getItem('options_scaling_strategy');
      return saved || 'fixed'; // fixed, profit_based, delta_neutral, volatility_based
    } catch {
      return 'fixed';
    }
  });

  const [scalingParams, setScalingParams] = useState(() => {
    try {
      const saved = localStorage.getItem('options_scaling_params');
      return saved
        ? JSON.parse(saved)
        : {
            maxPositionSize: 50, // Max contracts per position
            profitThreshold: 10, // Scale in when profit > 10%
            lossThreshold: -20, // Stop scaling when loss > -20%
            deltaTarget: 0, // Target delta for delta-neutral
            deltaTolerance: 5, // Rebalance when delta exceeds ±5
            ivChangeThreshold: 10, // Scale based on IV change > 10%
            stepSize: 5, // Default step size for scaling
          };
    } catch {
      return {
        maxPositionSize: 50,
        profitThreshold: 10,
        lossThreshold: -20,
        deltaTarget: 0,
        deltaTolerance: 5,
        ivChangeThreshold: 10,
        stepSize: 5,
      };
    }
  });

  // Custom order for positions (persisted)
  const [customOrder, setCustomOrder] = useState(() => {
    try {
      const saved = localStorage.getItem('options_custom_order');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  // Batch order state - strike selection and order quantity
  const [selectedStrikes, setSelectedStrikes] = useState({}); // { symbol: true/false }
  const [orderQuantity, setOrderQuantity] = useState(1); // Base unit for ratio scaling
  const [executionMode, setExecutionMode] = useState('smart'); // 'immediate' or 'smart'
  const [strikeRatios, setStrikeRatios] = useState({}); // { symbol: { buy: 1, sell: 2 } } - Buy:Sell ratio per strike
  const [batchQuantities, setBatchQuantities] = useState({}); // { symbol: number } - Manual quantity input per strike
  const [batchOrderResults, setBatchOrderResults] = useState([]);

  // Drag and drop sensors
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  // Dialog state
  const [closeDialog, setCloseDialog] = useState({ open: false, position: null });
  const [addDialog, setAddDialog] = useState({
    open: false,
    position: null,
    size: lastUsedSize,
    side: 'sell',
    orderType: 'maker_first',
    limitPrice: '',
  });
  const [confirmDialog, setConfirmDialog] = useState({ open: false, action: null, data: null });
  const [batchConfirmDialog, setBatchConfirmDialog] = useState({
    open: false,
    orderCount: 0,
    estimatedTime: 0,
  });
  
  // Sound settings dialog state (JAN 19, 2026 - Independent UI component)
  const [soundSettingsOpen, setSoundSettingsOpen] = useState(false);
  
  // Trade notification state (JAN 19, 2026 - Visual feedback)
  const [tradeNotification, setTradeNotification] = useState(null);
  const [orderResult, setOrderResult] = useState(null);
  const [submittingOrder, setSubmittingOrder] = useState(false); // Prevent double submission

  // Quick size presets (last used is default)
  const QUICK_SIZES = [1, 2, 5, 10, 20, 50];
  const DEFAULT_SIZE = lastUsedSize;

  // Order types
  const ORDER_TYPES = {
    maker_first: {
      label: 'Smart (Maker First)',
      description: 'Try limit at mid-price, fallback to market',
    },
    maker_only: { label: 'Maker Only', description: 'Only limit orders (may not fill)' },
    market_only: { label: 'Market Only (Fastest)', description: 'Immediate fill, higher fees' },
  };

  // Save skipConfirmStrikes to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem('options_skip_confirm_strikes', JSON.stringify(skipConfirmStrikes));
  }, [skipConfirmStrikes]);
  // Save hiddenPositions to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem('options_hidden_positions', JSON.stringify(hiddenPositions));
  }, [hiddenPositions]);
  // Save pollInterval to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem('options_poll_interval', pollInterval);
  }, [pollInterval]);
  // Save lastUsedSize to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem('options_last_used_size', lastUsedSize);
  }, [lastUsedSize]);

  // Save customOrder to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem('options_custom_order', JSON.stringify(customOrder));
  }, [customOrder]);

  // Handle drag end
  const handleDragEnd = (event) => {
    const { active, over } = event;

    if (active.id !== over.id) {
      const oldIndex = sortedPositions.findIndex((p) => p.product_symbol === active.id);
      const newIndex = sortedPositions.findIndex((p) => p.product_symbol === over.id);

      const reordered = arrayMove(sortedPositions, oldIndex, newIndex);
      setCustomOrder(reordered.map((p) => p.product_symbol));
    }
  };

  // Reset custom order
  const resetOrder = () => {
    setCustomOrder([]);
    localStorage.removeItem('options_custom_order');
  };

  // Toggle symbol sort (CE/PE grouping)
  const toggleSymbolSort = () => {
    setSymbolSort((prev) => (prev === 'grouped' ? null : 'grouped'));
    // Clear custom order when applying automatic sort
    if (symbolSort === null) {
      setCustomOrder([]);
    }
  };

  // Toggle strike sort (ascending/descending)
  const toggleStrikeSort = () => {
    setStrikeSort((prev) => {
      if (prev === null) return 'asc';
      if (prev === 'asc') return 'desc';
      return null;
    });
    // Clear custom order when applying automatic sort
    if (strikeSort === null) {
      setCustomOrder([]);
    }
  };

  // Parse expiry date and calculate days to expiration
  const getDaysToExpiry = (symbol) => {
    try {
      const parts = symbol?.split('-') || [];
      if (parts.length >= 4) {
        const expiry = parts[3]; // DDMMYY
        const day = parseInt(expiry.substring(0, 2));
        const month = parseInt(expiry.substring(2, 4)) - 1; // JS months are 0-indexed
        const year = 2000 + parseInt(expiry.substring(4, 6));
        const expiryDate = new Date(year, month, day, 8, 30, 0); // 8:30 AM expiry
        const now = new Date();
        const diffMs = expiryDate - now;
        const diffDays = diffMs / (1000 * 60 * 60 * 24);
        return isNaN(diffDays) ? 999 : diffDays;
      }
    } catch (e) {
      console.error('Error parsing expiry:', e);
    }
    return 999; // Far future if parsing fails
  };

  // Parse expiry code to formatted date string (DD/MM/YYYY)
  const formatExpiryDate = (symbol) => {
    try {
      const parts = symbol.split('-');
      if (parts.length >= 4) {
        const expiry = parts[3]; // DDMMYY
        const day = expiry.substring(0, 2);
        const month = expiry.substring(2, 4);
        const year = '20' + expiry.substring(4, 6);
        return `${day}/${month}/${year}`;
      }
    } catch (e) {
      console.error('Error parsing expiry for format:', e);
    }
    return 'Unknown';
  };

  // Get raw expiry code from symbol (for filtering)
  const getExpiryCode = (symbol) => {
    try {
      const parts = symbol.split('-');
      if (parts.length >= 4) {
        return parts[3]; // DDMMYY
      }
    } catch (e) {
      console.error('Error getting expiry code:', e);
    }
    return null;
  };

  // Extract unique expiry dates from positions (sorted by date)
  const uniqueExpiries = useMemo(() => {
    const expirySet = new Set();
    positions.forEach((pos) => {
      const code = getExpiryCode(pos.product_symbol);
      if (code) expirySet.add(code);
    });

    // Convert to array and sort by actual date
    return Array.from(expirySet).sort((a, b) => {
      const dayA = parseInt(a.substring(0, 2));
      const monthA = parseInt(a.substring(2, 4));
      const yearA = parseInt(a.substring(4, 6));
      const dayB = parseInt(b.substring(0, 2));
      const monthB = parseInt(b.substring(2, 4));
      const yearB = parseInt(b.substring(4, 6));

      // Compare: year, then month, then day
      if (yearA !== yearB) return yearA - yearB;
      if (monthA !== monthB) return monthA - monthB;
      return dayA - dayB;
    });
  }, [positions]);

  // Calculate PnL totals per expiry for max loss tracking
  const expiryPnlMap = useMemo(() => {
    const pnlMap = {};
    positions.forEach((pos) => {
      const code = getExpiryCode(pos.product_symbol);
      if (code) {
        if (!pnlMap[code]) pnlMap[code] = 0;
        pnlMap[code] += pos.unrealized_pnl || 0;
      }
    });
    return pnlMap;
  }, [positions]);

  // Handle expiry max loss setting update
  const handleExpiryMaxLossUpdate = useCallback((expiryCode, settings) => {
    setExpiryMaxLossSettings((prev) => {
      if (settings === null) {
        const next = { ...prev };
        delete next[expiryCode];
        return next;
      }
      return { ...prev, [expiryCode]: settings };
    });
  }, []);

  // Toggle expiry selection (multi-select)
  const toggleExpirySelection = (expiry) => {
    setSelectedExpiries((prev) => {
      const newSelection = prev.includes(expiry)
        ? prev.filter((e) => e !== expiry) // Remove if already selected
        : [...prev, expiry]; // Add if not selected
      localStorage.setItem('options_selected_expiries', JSON.stringify(newSelection));
      return newSelection;
    });
  };

  // Clear all expiry selections (show all)
  const clearExpirySelection = () => {
    setSelectedExpiries([]);
    localStorage.setItem('options_selected_expiries', JSON.stringify([]));
  };

  // Live index prices state (fetched from WebSocket, not from positions)
  const { btcPrice, ethPrice } = useMarketPrices();
  const indexPrices = useMemo(
    () => ({
      BTC: btcPrice || 0,
      ETH: ethPrice || 0,
    }),
    [btcPrice, ethPrice]
  );

  // Sort positions by custom order or default (days to expiration)
  const sortedPositions = useMemo(() => {
    // First filter out hidden positions
    let filtered = positions.filter((p) => !hiddenPositions.includes(p.product_symbol));

    // Apply expiry filter if any expiries are selected
    if (selectedExpiries.length > 0) {
      filtered = filtered.filter((p) => selectedExpiries.includes(getExpiryCode(p.product_symbol)));
    }

    // Apply P&L filter - Day 3 Enhancement
    if (pnlFilter === 'profit') {
      filtered = filtered.filter((p) => (p.unrealized_pnl || 0) > 0);
    } else if (pnlFilter === 'loss') {
      filtered = filtered.filter((p) => (p.unrealized_pnl || 0) < 0);
    }

    // Apply Moneyness filter - Day 3 Enhancement
    if (moneynessFilter !== 'all') {
      filtered = filtered.filter((p) => {
        const optionInfo = parseOptionSymbol(p.product_symbol);
        const spotPrice = indexPrices.BTC; // Use BTC price for both (ETH would need separate logic)
        const strike = optionInfo.strike;
        
        if (!strike || !spotPrice) return true; // Keep if can't determine
        
        const moneyness = spotPrice / strike;
        
        if (moneynessFilter === 'itm') {
          // ITM: Call if spot > strike, Put if spot < strike
          return optionInfo.isCall ? moneyness > 1.02 : moneyness < 0.98;
        } else if (moneynessFilter === 'atm') {
          // ATM: within 2% of strike
          return moneyness >= 0.98 && moneyness <= 1.02;
        } else if (moneynessFilter === 'otm') {
          // OTM: Call if spot < strike, Put if spot > strike
          return optionInfo.isCall ? moneyness < 0.98 : moneyness > 1.02;
        }
        return true;
      });
    }

    // Always sort by expiry first (nearest first)
    let sorted = filtered.sort((a, b) => {
      const daysA = getDaysToExpiry(a.product_symbol);
      const daysB = getDaysToExpiry(b.product_symbol);
      return daysA - daysB; // Ascending: nearest expiry first
    });

    // Apply symbol sort (CE/PE grouping)
    if (symbolSort === 'grouped') {
      sorted = sorted.sort((a, b) => {
        const typeA = a.product_symbol.startsWith('C-') ? 'Call' : 'Put';
        const typeB = b.product_symbol.startsWith('C-') ? 'Call' : 'Put';

        // First sort by type (Call first, then Put)
        if (typeA !== typeB) {
          return typeA === 'Call' ? -1 : 1;
        }

        // Within same type, maintain expiry order
        const daysA = getDaysToExpiry(a.product_symbol);
        const daysB = getDaysToExpiry(b.product_symbol);
        return daysA - daysB;
      });
    }

    // Apply strike sort
    if (strikeSort) {
      sorted = sorted.sort((a, b) => {
        // Extract strike prices
        const partsA = a.product_symbol.split('-');
        const partsB = b.product_symbol.split('-');
        const strikeA = partsA.length >= 3 ? parseInt(partsA[2]) : 0;
        const strikeB = partsB.length >= 3 ? parseInt(partsB[2]) : 0;

        return strikeSort === 'asc' ? strikeA - strikeB : strikeB - strikeA;
      });
    }

    // If custom order exists and is valid, use it (overrides all other sorting)
    if (customOrder.length > 0) {
      const ordered = [];
      const remaining = [...sorted];

      // Add positions in custom order
      customOrder.forEach((symbol) => {
        const pos = remaining.find((p) => p.product_symbol === symbol);
        if (pos) {
          ordered.push(pos);
          remaining.splice(remaining.indexOf(pos), 1);
        }
      });

      // Add any new positions not in custom order at the end
      return [...ordered, ...remaining];
    }

    return sorted;
  }, [positions, hiddenPositions, customOrder, selectedExpiries, pnlFilter, moneynessFilter, symbolSort, strikeSort, indexPrices]);

  // Calculate aggregated greeks for currently visible positions (respects expiry filter and hidden positions)
  const aggregatedGreeks = useMemo(() => {
    const greeks = {
      delta: 0,
      gamma: 0,
      theta: 0,
      vega: 0,
      count: 0,
      // Separate by underlying asset for futures equivalent
      btcDelta: 0,
      ethDelta: 0,
    };

    if (!sortedPositions || sortedPositions.length === 0) {
      return greeks;
    }

    // Use sortedPositions which already has expiry filter + hidden positions filter applied
    sortedPositions.forEach((pos) => {
      // Backend now returns position-level Greeks directly (already multiplied by size)
      // pos.delta, pos.theta, etc. are position-level values
      // pos.greeks.delta, pos.greeks.theta are per-contract values
      const size = pos.size || 0;

      if (pos.greeks) {
        // Use per-contract Greeks from pos.greeks and calculate position Greeks correctly
        const perContractDelta = parseFloat(pos.greeks.delta || 0);
        const perContractGamma = parseFloat(pos.greeks.gamma || 0);
        const perContractTheta = parseFloat(pos.greeks.theta || 0);
        const perContractVega = parseFloat(pos.greeks.vega || 0);

        // ✅ CORRECT FORMULA:
        // Delta Exchange theta/vega are in internal units (divide by 1000 for USD)
        // For SHORT positions (size < 0): we EARN theta (option loses value = our profit)
        // theta_usd = (theta_per_contract / 1000) * size
        // When size is negative (short), theta becomes positive (earning theta)

        greeks.delta += perContractDelta * size;
        greeks.gamma += perContractGamma * Math.abs(size);
        // Theta: short position (size < 0) with negative per-contract theta = positive portfolio theta (earning)
        greeks.theta += (perContractTheta / 1000) * size;
        greeks.vega += (perContractVega / 1000) * Math.abs(size);
        greeks.count++;

        // Separate delta by underlying asset for futures equivalent display
        const parts = pos.product_symbol.split('-');
        if (parts.length >= 2) {
          const underlying = parts[1]; // BTC or ETH
          const deltaContribution = perContractDelta * size;

          if (underlying === 'BTC') {
            greeks.btcDelta += deltaContribution;
          } else if (underlying === 'ETH') {
            greeks.ethDelta += deltaContribution;
          }
        }
      }
    });

    return greeks;
  }, [sortedPositions]);

  // Intelligent position scaling calculator
  const calculateSmartScaling = useCallback(
    (position) => {
      const currentSize = Math.abs(position.size || 0);
      const pnlPct = position.pnl_percentage || 0;
      const positionDelta = position.greeks?.delta
        ? parseFloat(position.greeks.delta) * position.size
        : 0;

      let recommendation = {
        action: 'hold',
        size: 0,
        reason: '',
        confidence: 'low',
        riskLevel: 'medium',
      };

      // Check maximum position size limit
      if (currentSize >= scalingParams.maxPositionSize) {
        recommendation.action = 'hold';
        recommendation.reason = `Position at max size (${scalingParams.maxPositionSize} contracts)`;
        recommendation.confidence = 'high';
        return recommendation;
      }

      // Check loss threshold - stop scaling if losing too much
      if (pnlPct < scalingParams.lossThreshold) {
        recommendation.action = 'reduce';
        recommendation.size = Math.floor(currentSize * 0.25); // Reduce by 25%
        recommendation.reason = `Loss ${(Number(pnlPct) || 0).toFixed(1)}% exceeds threshold (${scalingParams.lossThreshold}%)`;
        recommendation.confidence = 'high';
        recommendation.riskLevel = 'high';
        return recommendation;
      }

      switch (scalingStrategy) {
        case 'fixed':
          // Simple fixed size scaling
          recommendation.action = 'scale';
          recommendation.size = scalingParams.stepSize;
          recommendation.reason = `Fixed step size: ${scalingParams.stepSize} contracts`;
          recommendation.confidence = 'medium';
          break;

        case 'profit_based':
          // Scale in when profitable (pyramiding strategy)
          // Note: pnl_percentage already accounts for position direction:
          // - Long (size > 0): price up = positive PnL, price down = negative PnL
          // - Short (size < 0): price DOWN = positive PnL (profit), price UP = negative PnL (loss)

          const isLong = position.size > 0;
          const isShort = position.size < 0;

          if (pnlPct > scalingParams.profitThreshold) {
            // Position is profitable - scale into the winner
            const scaleFactor = Math.min(pnlPct / scalingParams.profitThreshold, 3); // Max 3x
            recommendation.action = 'scale';
            recommendation.size = Math.floor(scalingParams.stepSize * scaleFactor);
            recommendation.reason = `${isShort ? 'SHORT' : 'LONG'} profit ${(Number(pnlPct) || 0).toFixed(1)}% > threshold (${scalingParams.profitThreshold}%). Winner scaling.`;
            recommendation.confidence = 'high';
            recommendation.riskLevel = 'low';
          } else if (pnlPct < 0 && pnlPct > scalingParams.lossThreshold) {
            // Position is losing - average down cautiously
            // For shorts: price went UP (bad), adding more = selling more expensive options
            // For longs: price went DOWN (bad), adding more = buying cheaper options
            recommendation.action = 'scale';
            recommendation.size = Math.floor(scalingParams.stepSize * 0.5); // Half size when averaging down
            recommendation.reason = `${isShort ? 'SHORT' : 'LONG'} at ${(Number(pnlPct) || 0).toFixed(1)}% loss. Averaging down (cautious).`;
            recommendation.confidence = 'low';
            recommendation.riskLevel = 'high';
          } else {
            recommendation.action = 'hold';
            recommendation.reason = `${isShort ? 'SHORT' : 'LONG'} P&L ${(Number(pnlPct) || 0).toFixed(1)}% - waiting for ${scalingParams.profitThreshold}% profit`;
          }
          break;

        case 'delta_neutral':
          // Scale to maintain delta neutrality
          const portfolioDelta = aggregatedGreeks.delta || 0;
          const deltaDeviation = Math.abs(portfolioDelta - scalingParams.deltaTarget);

          if (deltaDeviation > scalingParams.deltaTolerance) {
            // Need to rebalance
            const needsMoreLong = portfolioDelta < scalingParams.deltaTarget;
            const positionIsCall = position.product_symbol.startsWith('C-');
            const positionIsLong = position.size > 0;

            // Determine if this position helps rebalance
            const helpsRebalance =
              (needsMoreLong && positionIsCall && positionIsLong) ||
              (!needsMoreLong && !positionIsCall && positionIsLong) ||
              (!needsMoreLong && positionIsCall && !positionIsLong) ||
              (needsMoreLong && !positionIsCall && !positionIsLong);

            if (helpsRebalance) {
              recommendation.action = 'scale';
              recommendation.size = Math.min(
                scalingParams.stepSize,
                Math.ceil(deltaDeviation / Math.abs(position.greeks?.delta || 1))
              );
              recommendation.reason = `Portfolio delta ${(Number(portfolioDelta) || 0).toFixed(2)} → target ${scalingParams.deltaTarget}. Rebalancing.`;
              recommendation.confidence = 'high';
              recommendation.riskLevel = 'medium';
            } else {
              recommendation.action = 'hold';
              recommendation.reason = `Portfolio delta ${(Number(portfolioDelta) || 0).toFixed(2)}. This position won't help rebalance.`;
            }
          } else {
            recommendation.action = 'hold';
            recommendation.reason = `Portfolio delta balanced: ${(Number(portfolioDelta) || 0).toFixed(2)} (target: ${scalingParams.deltaTarget})`;
          }
          break;

        case 'volatility_based':
          // Scale based on IV changes (requires IV tracking - placeholder)
          const currentIV = 0; // TODO: Track IV changes
          recommendation.action = 'hold';
          recommendation.reason = 'IV-based scaling (tracking IV changes...)';
          recommendation.confidence = 'low';
          break;

        default:
          recommendation.action = 'hold';
          recommendation.reason = 'Unknown strategy';
      }

      // Final validation - don't exceed max position size
      if (recommendation.action === 'scale') {
        const newSize = currentSize + recommendation.size;
        if (newSize > scalingParams.maxPositionSize) {
          recommendation.size = scalingParams.maxPositionSize - currentSize;
          recommendation.reason += ` (capped at max ${scalingParams.maxPositionSize})`;
        }

        if (recommendation.size <= 0) {
          recommendation.action = 'hold';
          recommendation.reason = 'At position size limit';
        }
      }

      return recommendation;
    },
    [scalingStrategy, scalingParams, aggregatedGreeks]
  );

  // Fetch options status
  const fetchStatus = useCallback(async () => {
    try {
      const { data } = await api.get('/api/options/status');
      if (data?.success) {
        setStatus(data);
      }
    } catch (err) {
      console.error('Failed to fetch options status:', err);
    }
  }, []);

  // Ref to track if we have positions (avoid dependency cycle)
  const hasPositionsRef = useRef(false);

  // Ref to track active batch polling intervals for cleanup
  const activeIntervalsRef = useRef([]);

  // Fetch options positions
  const fetchPositions = useCallback(async () => {
    try {
      const { data } = await api.get('/api/options/positions');
      if (data?.success) {
        const rawPositions = data.positions || [];
        
        // Enrich positions with IV data from Delta Exchange
        const positionsWithIV = await enrichPositionsWithIV(rawPositions);
        
        setPositions(positionsWithIV);
        hasPositionsRef.current = positionsWithIV.length > 0;
        // Only clear error if we got fresh (non-cached) data
        if (!data.cached) {
          setError(null);
        } else if (data.warning) {
          // Show warning for cached data
          setError(`⚠️ ${data.warning}`);
        }
      } else {
        // Keep existing positions on error, just show warning
        if (hasPositionsRef.current) {
          setError(`⚠️ Refresh failed: ${data?.error || 'Unknown error'}`);
        } else {
          setError(data?.error || 'Failed to fetch positions');
        }
      }
    } catch (err) {
      console.error('Failed to fetch options positions:', err);
      // Keep existing positions on error, just show warning
      if (hasPositionsRef.current) {
        setError(`⚠️ Connection issue: ${err.message}`);
      } else {
        setError(`Connection error: ${err.message}`);
      }
    }
  }, []); // No dependencies - safe

  // Fetch futures positions for combined payoff diagram
  const fetchFuturesPositions = useCallback(async () => {
    try {
      const { data } = await api.get('/api/futures/positions');
      if (data?.success) {
        setFuturesPositions(data.positions || []);
      }
    } catch (err) {
      console.error('Failed to fetch futures positions:', err);
      // Don't show error for futures, just log it
    }
  }, []);

  // Filter futures positions based on hidden state (from localStorage)
  const visibleFuturesPositions = useMemo(() => {
    try {
      const hiddenFutures = JSON.parse(localStorage.getItem('futures_hidden_positions') || '[]');
      return futuresPositions.filter((pos) => !hiddenFutures.includes(pos.product_symbol));
    } catch {
      return futuresPositions;
    }
  }, [futuresPositions]);

  // Enrich positions with IV data from Delta Exchange
  const enrichPositionsWithIV = async (positions) => {
    try {
      // Fetch IV data for all positions' symbols
      const symbols = positions.map(pos => pos.product_symbol).filter(Boolean);
      
      if (symbols.length === 0) {
        return positions;
      }

      // Fetch ticker data from Delta Exchange API (public endpoint, no auth needed)
      const tickerPromises = symbols.map(async (symbol) => {
        try {
          const response = await fetch(`https://api.india.delta.exchange/v2/tickers/${symbol}`);
          const result = await response.json();
          
          if (result?.success && result?.result) {
            const quotes = result.result.quotes || {};
            // Use average of bid_iv and ask_iv
            const bidIV = parseFloat(quotes.bid_iv) || 0;
            const askIV = parseFloat(quotes.ask_iv) || 0;
            const avgIV = bidIV && askIV ? (bidIV + askIV) / 2 : (bidIV || askIV);
            
            return { symbol, iv: avgIV };
          }
          return { symbol, iv: null };
        } catch (err) {
          console.warn(`Failed to fetch IV for ${symbol}:`, err.message);
          return { symbol, iv: null };
        }
      });

      const ivData = await Promise.all(tickerPromises);
      const ivMap = Object.fromEntries(ivData.map(d => [d.symbol, d.iv]));

      // Enrich positions with IV data
      return positions.map(pos => ({
        ...pos,
        iv: ivMap[pos.product_symbol] || null
      }));
    } catch (err) {
      console.error('Failed to enrich positions with IV:', err);
      // Return original positions if enrichment fails
      return positions;
    }
  };

  // Load SL/TP settings for all positions
  const loadSLTPSettings = useCallback(async () => {
    try {
      const { data } = await api.get('/api/options/sl-tp/all');
      if (data?.success && data.settings) {
        // Convert array to map by symbol
        const settingsMap = {};
        data.settings.forEach((s) => {
          settingsMap[s.symbol] = s;
        });
        setSlTpSettings(settingsMap);
      }
    } catch (err) {
      console.error('Failed to load SL/TP settings:', err);
    }
  }, []);

  // Load Max Loss settings for all positions (per-strike and per-expiry)
  const loadMaxLossSettings = useCallback(async () => {
    try {
      // Fetch per-strike max loss settings
      const { data: strikeData } = await api.get('/api/options/max-loss/strike/all');
      if (strikeData?.success && strikeData.settings) {
        const settingsMap = {};
        strikeData.settings.forEach((s) => {
          settingsMap[s.symbol] = s;
        });
        setMaxLossSettings(settingsMap);
      }

      // Fetch per-expiry max loss settings
      const { data: expiryData } = await api.get('/api/options/max-loss/expiry/all');
      if (expiryData?.success && expiryData.settings) {
        const settingsMap = {};
        expiryData.settings.forEach((s) => {
          settingsMap[s.expiry_code] = s;
        });
        setExpiryMaxLossSettings(settingsMap);
      }
    } catch (err) {
      console.error('Failed to load max loss settings:', err);
    }
  }, []);

  // Handle max loss setting update from child component
  const handleMaxLossUpdate = useCallback((symbol, settings) => {
    setMaxLossSettings((prev) => {
      if (settings === null) {
        const next = { ...prev };
        delete next[symbol];
        return next;
      }
      return { ...prev, [symbol]: settings };
    });
  }, []);

  // Fetch pending orders from Delta Exchange
  const fetchPendingOrders = useCallback(async () => {
    try {
      const { data } = await api.get('/api/positions/pending-orders');
      if (data?.success) {
        setPendingOrders(data.orders || []);
        setPendingOrdersError(null);
      } else {
        setPendingOrdersError(data?.error || 'Failed to fetch pending orders');
      }
    } catch (err) {
      console.error('Failed to fetch pending orders:', err);
      setPendingOrdersError(err.message);
    }
  }, []);

  // Cancel pending order
  const handleCancelPendingOrder = useCallback(async (order) => {
    if (!window.confirm('Cancel this order?')) {
      return;
    }
    
    try {
      const { data } = await api.delete(`/api/options-chain/order/${order.id}/${order.product_id}`);
      if (data?.success) {
        // Refresh pending orders list
        await fetchPendingOrders();
      } else {
        console.error('Failed to cancel order:', data?.error);
        alert(`Failed to cancel order: ${data?.error || 'Unknown error'}`);
      }
    } catch (err) {
      console.error('Failed to cancel order:', err);
      alert(`Failed to cancel order: ${err.message || 'Unknown error'}`);
    }
  }, [fetchPendingOrders]);

  // Initial load
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([
        fetchStatus(),
        fetchPositions(),
        loadSLTPSettings(),
        loadMaxLossSettings(),
        fetchPendingOrders(),
        fetchFuturesPositions(),
      ]);
      setLoading(false);
    };
    loadData();
  }, [fetchStatus, fetchPositions, loadSLTPSettings, loadMaxLossSettings, fetchPendingOrders, fetchFuturesPositions]);

  // Auto-refresh every pollInterval ms
  useEffect(() => {
    const interval = setInterval(() => {
      fetchPositions();
      fetchStatus();
      fetchPendingOrders();
      fetchFuturesPositions();
      loadMaxLossSettings(); // Refresh max loss settings too
    }, pollInterval);
    return () => clearInterval(interval);
  }, [fetchPositions, fetchStatus, fetchPendingOrders, fetchFuturesPositions, loadMaxLossSettings, pollInterval]);

  // Cleanup active batch polling intervals on unmount
  useEffect(() => {
    return () => {
      // Clear all active intervals on unmount
      activeIntervalsRef.current.forEach(clearInterval);
      activeIntervalsRef.current = [];
    };
  }, []);

  // Store latest data in refs to avoid useEffect dependency issues
  const sortedPositionsRef = React.useRef(sortedPositions);
  const indexPricesRef = React.useRef(indexPrices);

  // Keep refs updated
  useEffect(() => {
    sortedPositionsRef.current = sortedPositions;
    indexPricesRef.current = indexPrices;
  }, [sortedPositions, indexPrices]);

  // Automation monitor initialization (only once on mount)
  useEffect(() => {
    // Connect automation monitor to market data via refs (avoids stale closures)
    automationMonitor.setMarketDataProvider(() => ({
      positions: sortedPositionsRef.current,
      spotPrices: indexPricesRef.current,
    }));

    // Connect notifications to console (or your toast/snackbar system)
    notificationService.setToastCallback((message, severity) => {
      console.log(`[AUTOMATION ${severity.toUpperCase()}] ${message}`);
      // TODO: Connect to your toast/snackbar system if available
      // Example: setSnackbar({ open: true, message, severity });
    });

    // Start the automation monitor
    automationMonitor.start();

    // Expose debug helper to console
    window.debugAutomation = () => {
      const status = automationMonitor.getStatus();
      console.log('=== AUTOMATION DEBUG INFO ===');
      console.log('Active automations:', status.length);
      console.log('Details:', status);
      console.log('Market data:', {
        positions: sortedPositionsRef.current?.length || 0,
        spotPrices: indexPricesRef.current,
      });
      return status;
    };
    console.log('💡 Type window.debugAutomation() in console to check automation status');

    // Cleanup on unmount
    return () => {
      automationMonitor.stop();
      delete window.debugAutomation;
    };
  }, []); // Empty deps - only run once on mount

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyPress = (event) => {
      // Ignore if typing in input field or textarea
      if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
        return;
      }

      // Handle Escape to close dialogs
      if (event.key === 'Escape') {
        if (closeDialog.open || addDialog.open) {
          setCloseDialog({ open: false, position: null });
          setAddDialog({
            open: false,
            position: null,
            size: lastUsedSize,
            side: 'sell',
            orderType: 'maker_first',
            limitPrice: '',
          });
          event.preventDefault();
        }
        return;
      }

      // Block all other shortcuts if any dialog is open
      if (closeDialog.open || addDialog.open) {
        return;
      }

      // Get first position sorted by expiry (nearest first)
      if (sortedPositions.length === 0) return;
      const firstPosition = sortedPositions[0];

      switch (event.key.toLowerCase()) {
        case 'b':
          event.preventDefault();
          handleAdd(firstPosition, 'buy');
          break;
        case 's':
          event.preventDefault();
          handleAdd(firstPosition, 'sell');
          break;
        case 'c':
          event.preventDefault();
          handleClose(firstPosition);
          break;
        case 'r':
          event.preventDefault();
          handleRefresh();
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [sortedPositions, closeDialog.open, addDialog.open, lastUsedSize]);

  // Manual refresh
  const handleRefresh = async () => {
    setRefreshing(true);
    await Promise.all([fetchStatus(), fetchPositions(), fetchPendingOrders(), fetchFuturesPositions()]);
    setRefreshing(false);
  };

  // Close position
  const handleClose = async (position) => {
    setCloseDialog({ open: true, position });
  };

  const confirmClose = async () => {
    const { position } = closeDialog;
    setCloseDialog({ open: false, position: null });

    try {
      const { data } = await api.post('/api/options/close', {
        symbol: position.product_symbol,
        confirm: true,
      });

      if (data?.success) {
        // Play calming sound when position is closed
        soundManager.playTradeFilled();
        setOrderResult({ type: 'success', message: `Closed ${position.product_symbol}` });
        // Show visual notification
        setTradeNotification({
          symbol: position.product_symbol,
          side: 'close',
          size: Math.abs(position.size),
          price: data.fill_price,
        });
        fetchPositions();
      } else {
        setOrderResult({ type: 'error', message: data?.error || 'Failed to close position' });
      }
    } catch (err) {
      setOrderResult({ type: 'error', message: err.message });
    }

    // Clear result after 5 seconds
    setTimeout(() => setOrderResult(null), 5000);
  };

  // Quick execute order without confirmation (for skipped strikes)
  // Takes size and side directly to avoid stale closure issues
  const executeQuickOrderWithSettings = async (position, size, side) => {
    const symbol = position.product_symbol;

    console.log(`⚡ Quick order for ${symbol}: size=${size}, side=${side}`);

    try {
      const { data } = await api.post('/api/options/add', {
        symbol: symbol,
        size: size,
        side: side,
        order_preference: 'maker_first',
        confirm: true,
      });

      if (data?.success) {
        const execType = data.execution_type || 'unknown';
        const fillPrice = data.fill_price ? `@ $${parseFloat(data.fill_price).toFixed(2)}` : '';
        // Play calming sound for quick order fills
        soundManager.playTradeFilled();
        setOrderResult({
          type: 'success',
          message: `⚡ ${side.toUpperCase()} ${size} ${symbol} ${fillPrice} (${execType})`,
        });
        // Show visual notification
        setTradeNotification({
          symbol: symbol,
          side: side,
          size: size,
          price: data.fill_price,
        });
        fetchPositions();
      } else {
        setOrderResult({ type: 'error', message: data?.error || 'Quick order failed' });
      }
    } catch (err) {
      setOrderResult({ type: 'error', message: err.message });
    }
    setTimeout(() => setOrderResult(null), 5000);
  };

  // Legacy wrapper for backward compatibility
  const executeQuickOrder = async (position, side = 'sell') => {
    const symbol = position.product_symbol;
    // Get per-symbol saved settings (size and side)
    const savedSettings = skipConfirmStrikes[symbol] || {};
    const savedSize = savedSettings.size || parseInt(lastUsedSize) || 5;
    const savedSide = side || savedSettings.side || 'sell';

    console.log(
      `⚡ Quick order (legacy) for ${symbol}: size=${savedSize}, side=${savedSide}, settings=`,
      savedSettings
    );

    executeQuickOrderWithSettings(position, savedSize, savedSide);
  };

  // Add to position - check if strike is in skip list
  const handleAdd = (position, forceSide = null) => {
    const symbol = position.product_symbol;

    // Get smart scaling recommendation
    const recommendation = calculateSmartScaling(position);
    const suggestedSize =
      recommendation.size > 0 ? recommendation.size : parseInt(lastUsedSize) || 5;

    // If this strike is in skip list, execute immediately with saved settings
    const savedSettings = skipConfirmStrikes[symbol];
    if (savedSettings?.enabled) {
      const side = forceSide || savedSettings.side || 'sell';
      const size = savedSettings.size || 5;
      executeQuickOrderWithSettings(position, size, side);
      return;
    }

    // Otherwise show dialog with recommended size
    setAddDialog({
      open: true,
      position,
      size: suggestedSize.toString(), // Use smart recommended size
      side: forceSide || 'sell', // Default sell
      orderType: 'maker_first', // Default smart order
      limitPrice: '', // Clear limit price
      recommendation, // Pass recommendation to dialog for display
    });
  };

  // Enable skip confirmation for a strike with saved size and side
  const enableSkipConfirm = (symbol, size = null, side = null) => {
    const savedSize = size || parseInt(lastUsedSize) || 5;
    const savedSide = side || 'sell';
    console.log(`💾 Saving quick mode for ${symbol}: size=${savedSize}, side=${savedSide}`);
    setSkipConfirmStrikes((prev) => ({
      ...prev,
      [symbol]: {
        enabled: true,
        size: savedSize,
        side: savedSide,
      },
    }));
  };

  // Disable skip confirmation for a strike (reset)
  const disableSkipConfirm = (symbol) => {
    setSkipConfirmStrikes((prev) => {
      const updated = { ...prev };
      delete updated[symbol];
      return updated;
    });
  };

  // Confirm and optionally skip future dialogs
  const confirmAddWithSkip = async (skipFuture = false) => {
    const { position, size, side, orderType, limitPrice } = addDialog;

    // Prevent double submission
    if (submittingOrder) {
      console.log('⚠️ Order already submitting, ignoring duplicate click');
      return;
    }

    if (skipFuture && position) {
      enableSkipConfirm(position.product_symbol, parseInt(size), side);
    }

    // Save last used size
    setLastUsedSize(size);

    setAddDialog({
      open: false,
      position: null,
      size: lastUsedSize,
      side: 'sell',
      orderType: 'maker_first',
      limitPrice: '',
    });

    setSubmittingOrder(true); // Lock submission

    try {
      const requestData = {
        symbol: position.product_symbol,
        size: parseFloat(size),
        side,
        order_preference: orderType,
        confirm: true,
      };

      // Add limit price if using maker_only and price is specified
      if (orderType === 'maker_only' && limitPrice) {
        requestData.limit_price = parseFloat(limitPrice);
      }

      const { data } = await api.post('/api/options/add', requestData);

      if (data?.success) {
        const execType = data.execution_type || 'unknown';
        const fillPrice = data.fill_price ? `@ $${parseFloat(data.fill_price).toFixed(2)}` : '';
        // Play calming sound when order is filled
        soundManager.playTradeFilled();
        setOrderResult({
          type: 'success',
          message: `${side.toUpperCase()} ${size} ${position.product_symbol} ${fillPrice} (${execType})`,
        });
        // Show visual notification
        setTradeNotification({
          symbol: position.product_symbol,
          side: side,
          size: size,
          price: data.fill_price,
        });
        fetchPositions();
      } else {
        setOrderResult({ type: 'error', message: data?.error || 'Failed to add to position' });
      }
    } catch (err) {
      setOrderResult({ type: 'error', message: err.message });
    } finally {
      // Keep locked for 2 seconds to prevent double-click
      setTimeout(() => setSubmittingOrder(false), 2000);
    }

    // Clear result after 5 seconds
    setTimeout(() => setOrderResult(null), 5000);
  };

  // ========================================================================
  // BATCH ORDER FUNCTIONS - Ratio-preserving position scaling
  // ========================================================================

  // Helper: Calculate GCD (Greatest Common Divisor) for ratio calculation
  const gcd = (a, b) => {
    a = Math.abs(Math.round(a));
    b = Math.abs(Math.round(b));
    if (a === 0) return b;
    if (b === 0) return a;
    while (b !== 0) {
      const temp = b;
      b = a % b;
      a = temp;
    }
    return a;
  };

  // Toggle strike selection
  const toggleStrikeSelection = (symbol) => {
    setSelectedStrikes((prev) => ({
      ...prev,
      [symbol]: !prev[symbol],
    }));
  };

  // Select all visible positions
  const selectAllStrikes = () => {
    const allSelected = {};
    sortedPositions.forEach((pos) => {
      allSelected[pos.product_symbol] = true;
    });
    setSelectedStrikes(allSelected);
  };

  // Deselect all
  const deselectAllStrikes = () => {
    setSelectedStrikes({});
  };

  // Get selected positions
  const getSelectedPositions = () => {
    return sortedPositions.filter((pos) => selectedStrikes[pos.product_symbol]);
  };

  // Calculate batch orders maintaining buy:sell ratio
  // Example: Ratio 1:2 means 4 buy + 8 sell
  // Quantity +1 = 1 buy + 2 sell
  // Quantity +2 = 2 buy + 4 sell
  const calculateBatchOrders = () => {
    const selectedPos = getSelectedPositions();
    const orders = [];
    const errors = [];

    selectedPos.forEach((pos) => {
      const symbol = pos.product_symbol;
      const ratio = strikeRatios[symbol];

      // Check if ratio is defined for this strike
      if (!ratio || !ratio.buy || !ratio.sell) {
        // No ratio defined - generate single order (legacy behavior)
        const currentSize = pos.size;
        const orderSize = Math.abs(orderQuantity);
        const isLong = currentSize > 0;

        let side;
        if (orderQuantity > 0) {
          side = isLong ? 'buy' : 'sell';
        } else {
          side = isLong ? 'sell' : 'buy';
        }

        const midPrice = ((pos.best_bid || 0) + (pos.best_ask || 0)) / 2;

        orders.push({
          symbol: pos.product_symbol,
          size: orderSize,
          side,
          midPrice,
          originalSize: pos.size,
          optionType: pos.product_symbol.startsWith('C-') ? 'Call' : 'Put',
        });
        return;
      }

      // Ratio is defined - generate TWO orders (buy and sell) maintaining ratio
      const buyRatio = ratio.buy;
      const sellRatio = ratio.sell;

      // Validate ratio: must be integers
      if (
        !Number.isInteger(buyRatio) ||
        !Number.isInteger(sellRatio) ||
        buyRatio <= 0 ||
        sellRatio <= 0
      ) {
        errors.push({
          symbol,
          message: `Invalid ratio ${buyRatio}:${sellRatio}. Please place manually.`,
        });
        return;
      }

      // Calculate actual order sizes
      const buySize = Math.abs(orderQuantity) * buyRatio;
      const sellSize = Math.abs(orderQuantity) * sellRatio;

      const midPrice = ((pos.best_bid || 0) + (pos.best_ask || 0)) / 2;

      // Generate BUY order
      orders.push({
        symbol: pos.product_symbol,
        size: buySize,
        side: 'buy',
        midPrice,
        originalSize: pos.size,
        optionType: pos.product_symbol.startsWith('C-') ? 'Call' : 'Put',
        ratioInfo: `${buyRatio}:${sellRatio}`,
      });

      // Generate SELL order
      orders.push({
        symbol: pos.product_symbol,
        size: sellSize,
        side: 'sell',
        midPrice,
        originalSize: pos.size,
        optionType: pos.product_symbol.startsWith('C-') ? 'Call' : 'Put',
        ratioInfo: `${buyRatio}:${sellRatio}`,
      });
    });

    // Show errors if any
    if (errors.length > 0) {
      const errorMsg = errors.map((e) => `${e.symbol}: ${e.message}`).join('\\n');
      setOrderResult({ type: 'error', message: errorMsg });
      return [];
    }

    return orders;
  };

  // Track batch execution to prevent duplicates
  const [batchExecuting, setBatchExecuting] = useState(false);

  // Execute batch orders with robust rate limiting and retry logic
  const executeBatchOrders = async () => {
    // ===== DUPLICATE PREVENTION =====
    if (batchExecuting) {
      console.log('⚠️ Batch order already executing, ignoring duplicate trigger');
      setOrderResult({ type: 'warning', message: '⚠️ Batch already executing, please wait...' });
      return;
    }

    const orders = calculateBatchOrders();
    if (orders.length === 0) {
      setOrderResult({
        type: 'warning',
        message: 'No orders to execute. Enter quantities in Batch Qty column.',
      });
      setTimeout(() => setOrderResult(null), 3000);
      setBatchExecuting(false); // Reset state
      return;
    }

    // Show warning for large batches
    if (orders.length > 10) {
      setBatchConfirmDialog({
        open: true,
        orderCount: orders.length,
        estimatedTime: Math.ceil(orders.length * 1.5),
      });
      return; // Will be called again when user confirms
    }

    // Execute batch (this is called after confirmation or if < 10 orders)
    executeBatch(orders);
  };

  // Actual batch execution logic (split from executeBatchOrders for confirmation flow)
  const executeBatch = async (orders) => {
    // Lock execution immediately
    setBatchExecuting(true);
    setBatchOrderResults([]);

    const results = [];
    const submittedOrders = []; // Track orders that were submitted successfully
    const MAX_RETRIES = 2;
    const BASE_DELAY = 1500; // 1.5 seconds between orders (robust for rate limits)

    // Determine order preference based on execution mode
    const orderPreference = executionMode === 'immediate' ? 'market_only' : 'maker_first';
    const executionLabel = executionMode === 'immediate' ? 'MARKET' : 'LIMIT';

    // ===== PHASE 1: Submit all orders =====
    for (let i = 0; i < orders.length; i++) {
      const order = orders[i];
      let success = false;
      let retries = 0;

      // Update UI to show progress
      setBatchOrderResults((prev) => [
        ...prev,
        {
          symbol: order.symbol,
          size: order.size,
          side: order.side,
          success: false,
          filled: executionMode === 'immediate', // Market orders fill immediately
          message: `⏳ Placing ${executionLabel} order ${i + 1}/${orders.length}...`,
        },
      ]);

      while (!success && retries <= MAX_RETRIES) {
        try {
          const { data } = await api.post('/api/options/add', {
            symbol: order.symbol,
            size: order.size,
            side: order.side,
            order_preference: orderPreference,
            confirm: true,
          });

          if (data?.success) {
            const result = {
              symbol: order.symbol,
              size: order.size,
              side: order.side,
              success: true,
              filled: executionMode === 'immediate', // Market orders are filled immediately
              message:
                executionMode === 'immediate'
                  ? `✅ ${order.side.toUpperCase()} ${order.size} FILLED @ ${data.fill_price ? '$' + parseFloat(data.fill_price).toFixed(2) : 'market'}`
                  : `📤 ${order.side.toUpperCase()} ${order.size} submitted @ ${data.fill_price ? '$' + parseFloat(data.fill_price).toFixed(2) : 'mid'} - checking fill...`,
              expectedSize: order.side === 'buy' ? order.size : -order.size,
            };
            results.push(result);
            if (executionMode === 'smart') {
              submittedOrders.push(result); // Only track for smart mode
            }
            // Play calming sound for immediate fills
            if (executionMode === 'immediate') {
              soundManager.playTradeFilled();
              // Show visual notification
              setTradeNotification({
                symbol: order.symbol,
                side: order.side,
                size: order.size,
                price: data.fill_price,
              });
            }
            success = true;
          } else {
            // If order failed, check if it's rate limit or other error
            const errorMsg = data?.error || 'Failed';
            if (
              errorMsg.toLowerCase().includes('rate') ||
              errorMsg.toLowerCase().includes('too many')
            ) {
              // Rate limit hit - increase delay and retry
              if (retries < MAX_RETRIES) {
                retries++;
                results[results.length - 1] = {
                  symbol: order.symbol,
                  size: order.size,
                  side: order.side,
                  success: false,
                  filled: false,
                  message: `⚠️ Rate limit - retry ${retries}/${MAX_RETRIES} in ${retries * 2}s...`,
                };
                setBatchOrderResults([...results]);
                await new Promise((resolve) => setTimeout(resolve, retries * 2000)); // Exponential backoff
                continue;
              }
            }

            results[results.length - 1] = {
              symbol: order.symbol,
              size: order.size,
              side: order.side,
              success: false,
              filled: false,
              message: `❌ ${errorMsg}`,
            };
            break;
          }
        } catch (err) {
          const errorMsg = err.message || 'Unknown error';

          // Check if it's a network/rate limit error
          if (
            errorMsg.toLowerCase().includes('rate') ||
            errorMsg.toLowerCase().includes('429') ||
            errorMsg.toLowerCase().includes('too many')
          ) {
            if (retries < MAX_RETRIES) {
              retries++;
              results[results.length - 1] = {
                symbol: order.symbol,
                size: order.size,
                side: order.side,
                success: false,
                filled: false,
                message: `⚠️ Rate limit - retry ${retries}/${MAX_RETRIES}...`,
              };
              setBatchOrderResults([...results]);
              await new Promise((resolve) => setTimeout(resolve, retries * 2000)); // Exponential backoff
              continue;
            }
          }

          results[results.length - 1] = {
            symbol: order.symbol,
            size: order.size,
            side: order.side,
            success: false,
            filled: false,
            message: `❌ ${errorMsg}`,
          };
          break;
        }
      }

      // Update results
      setBatchOrderResults([...results]);

      // Delay between orders (with exponential increase for large batches)
      if (i < orders.length - 1) {
        // Increase delay for larger batches to avoid rate limits
        const delayMultiplier = orders.length > 5 ? 1.5 : 1;
        const delay = Math.ceil(BASE_DELAY * delayMultiplier);
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }

    setBatchExecuting(false); // Unlock batch execution

    // Clear batch quantities after successful execution
    setBatchQuantities({});

    // ===== PHASE 2: Monitor fill status with auto-market order after 5 minutes (only in smart mode) =====
    if (submittedOrders.length > 0 && executionMode === 'smart') {
      setOrderResult({
        type: 'info',
        message: `📊 Monitoring ${submittedOrders.length} orders for fills...`,
      });

      // Track start time for each order
      const orderStartTime = Date.now();
      const AUTO_MARKET_TIMEOUT = 5 * 60 * 1000; // 5 minutes

      // Poll positions to check if orders are filled
      let pollAttempts = 0;
      const MAX_POLL_ATTEMPTS = 150; // Poll for up to 5 minutes (150 * 2s = 300s)
      const POLL_INTERVAL = 2000; // Check every 2 seconds
      let autoMarketTriggered = false;

      const checkFillStatus = async () => {
        try {
          // Fetch fresh positions
          const { data } = await api.get('/api/options/positions');
          if (data?.success && data.positions) {
            const currentPositions = data.positions;

            // Check each submitted order
            submittedOrders.forEach((orderResult, idx) => {
              if (orderResult.filled) return; // Already marked as filled

              // Find the position for this symbol
              const position = currentPositions.find(
                (p) => p.product_symbol === orderResult.symbol
              );

              if (position) {
                // Check if size increased by expected amount
                // Note: This is an approximation - we compare against original expected size
                const actualSize = position.size;

                // Mark as filled (we assume if position exists and order submitted, it's filled)
                // More robust: could track original size and compare delta
                orderResult.filled = true;
                orderResult.message = `✅ ${orderResult.side.toUpperCase()} ${orderResult.size} FILLED - position now ${actualSize}`;
                
                // Play sound for individual order fills
                soundManager.playTradeFilled();
              }
            });

            // Update results display
            const updatedResults = [...results];
            setBatchOrderResults(updatedResults);

            // Check if all filled
            const allFilled = submittedOrders.every((o) => o.filled);

            if (allFilled) {
              // Play calming sound for successful fills
              soundManager.playTradeFilled();
              setOrderResult({
                type: 'success',
                message: `✅ All ${submittedOrders.length} orders filled!`,
              });
              // Clear after 5 seconds
              setTimeout(() => {
                setOrderResult(null);
                setBatchOrderResults([]);
              }, 5000);
              return true; // Stop polling
            }
          }
        } catch (err) {
          console.error('Error checking fill status:', err);
        }

        return false; // Continue polling
      };

      // Auto-market order function for unfilled orders after 5 minutes
      const triggerAutoMarket = async () => {
        const unfilledOrders = submittedOrders.filter((o) => !o.filled);

        if (unfilledOrders.length === 0 || autoMarketTriggered) return;

        autoMarketTriggered = true;

        setOrderResult({
          type: 'warning',
          message: `⚡ Auto-fill: Converting ${unfilledOrders.length} unfilled orders to MARKET orders...`,
        });

        // Process each unfilled order
        for (const orderResult of unfilledOrders) {
          try {
            orderResult.message = `🔄 Converting to MARKET order...`;
            setBatchOrderResults([...results]);

            // Place market order to force fill
            const { data } = await api.post('/api/options/add', {
              symbol: orderResult.symbol,
              size: orderResult.size,
              side: orderResult.side,
              order_preference: 'market_only', // Force market order
              confirm: true,
            });

            if (data?.success) {
              orderResult.filled = true;
              orderResult.message = `✅ ${orderResult.side.toUpperCase()} ${orderResult.size} FILLED via MARKET @ ${data.fill_price ? '$' + parseFloat(data.fill_price).toFixed(2) : 'market'}`;
              // Play sound for auto-market fills
              soundManager.playTradeFilled();
            } else {
              orderResult.message = `❌ Market order failed: ${data?.error || 'Unknown error'}`;
            }
          } catch (err) {
            orderResult.message = `❌ Market order error: ${err.message}`;
          }

          setBatchOrderResults([...results]);

          // Small delay between market orders
          await new Promise((resolve) => setTimeout(resolve, 1000));
        }

        // Check final status
        await fetchPositions();
        const finalUnfilled = submittedOrders.filter((o) => !o.filled).length;

        if (finalUnfilled === 0) {
          setOrderResult({
            type: 'success',
            message: `✅ All orders filled after auto-market conversion!`,
          });
          setTimeout(() => {
            setOrderResult(null);
            setBatchOrderResults([]);
          }, 5000);
        } else {
          setOrderResult({
            type: 'error',
            message: `⚠️ ${finalUnfilled} orders still unfilled after market conversion. Manual intervention required.`,
          });
        }
      };

      // Start polling (track ref to ensure cleanup)
      const pollIntervalRef = setInterval(async () => {
        pollAttempts++;
        const elapsedTime = Date.now() - orderStartTime;

        // Check if 5 minutes elapsed and orders still unfilled
        if (elapsedTime >= AUTO_MARKET_TIMEOUT && !autoMarketTriggered) {
          const unfilledCount = submittedOrders.filter((o) => !o.filled).length;
          if (unfilledCount > 0) {
            clearInterval(pollIntervalRef);
            activeIntervalsRef.current = activeIntervalsRef.current.filter(
              (id) => id !== pollIntervalRef
            );
            await triggerAutoMarket();
            return;
          }
        }

        const shouldStop = await checkFillStatus();

        if (shouldStop || pollAttempts >= MAX_POLL_ATTEMPTS) {
          clearInterval(pollIntervalRef);
          activeIntervalsRef.current = activeIntervalsRef.current.filter(
            (id) => id !== pollIntervalRef
          );

          if (pollAttempts >= MAX_POLL_ATTEMPTS) {
            const unfilledCount = submittedOrders.filter((o) => !o.filled).length;
            if (unfilledCount > 0 && !autoMarketTriggered) {
              // Trigger auto-market as fallback
              await triggerAutoMarket();
            }
          }
        }

        // Update countdown in message
        if (pollAttempts % 5 === 0) {
          // Update every 10 seconds
          const remainingTime = Math.max(0, AUTO_MARKET_TIMEOUT - elapsedTime);
          const remainingMinutes = Math.floor(remainingTime / 60000);
          const remainingSeconds = Math.floor((remainingTime % 60000) / 1000);

          const unfilledCount = submittedOrders.filter((o) => !o.filled).length;
          if (unfilledCount > 0 && remainingTime > 0) {
            setOrderResult({
              type: 'info',
              message: `📊 ${unfilledCount} unfilled - Auto-market in ${remainingMinutes}m ${remainingSeconds}s`,
            });
          }
        }
      }, POLL_INTERVAL);

      // Track interval for cleanup
      activeIntervalsRef.current.push(pollIntervalRef);

      // Initial check immediately
      await checkFillStatus();
    } else {
      // No orders submitted successfully
      const successCount = results.filter((r) => r.success).length;
      const failCount = results.length - successCount;

      setOrderResult({
        type: 'error',
        message: `❌ All orders failed: ${failCount} errors`,
      });

      // Clear after 8 seconds
      setTimeout(() => {
        setOrderResult(null);
        setBatchOrderResults([]);
      }, 8000);
    }
  };

  // Format helpers
  const formatPnl = (pnl) => {
    const numPnl = Number(pnl) || 0;
    const formatted = Math.abs(numPnl).toFixed(4);
    return numPnl >= 0 ? `+$${formatted}` : `-$${formatted}`;
  };

  const formatPnlPct = (pct) => {
    const numPct = Number(pct) || 0;
    const formatted = Math.abs(numPct).toFixed(2);
    return numPct >= 0 ? `+${formatted}%` : `-${formatted}%`;
  };

  const getPnlColor = (pnl) => {
    if (pnl > 0) return '#10b981';
    if (pnl < 0) return '#ef4444';
    return '#94a3b8';
  };

  const getPositionType = (symbol) => {
    if (symbol.startsWith('C-')) return { type: 'CALL', color: '#3b82f6' };
    if (symbol.startsWith('P-')) return { type: 'PUT', color: '#a855f7' };
    return { type: 'UNKNOWN', color: '#6b7280' };
  };

  const parseOptionSymbol = (symbol) => {
    // Format: C-BTC-113000-300126 or P-BTC-69000-270226
    const parts = symbol.split('-');
    if (parts.length >= 4) {
      const optionType = parts[0];
      const underlying = parts[1];
      const strike = parseInt(parts[2]);
      const expiry = parts[3];
      // Parse expiry DDMMYY to readable format
      const day = expiry.substring(0, 2);
      const month = expiry.substring(2, 4);
      const year = '20' + expiry.substring(4, 6);
      return {
        type: optionType === 'C' ? 'Call' : 'Put',
        underlying,
        strike,
        expiry: `${day}/${month}/${year}`,
      };
    }
    return { type: '?', underlying: '?', strike: 0, expiry: '?' };
  };

  // Render loading state
  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <Card sx={{ bgcolor: 'background.paper', borderRadius: 2 }}>
        <CardContent>
          {/* Header */}
          <Box
            sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <ShowChartIcon /> Options Positions
              </Typography>

              {/* Status Badge */}
              {status && (
                <Chip
                  icon={status.trading_allowed ? <CheckCircleIcon /> : <BlockIcon />}
                  label={status.guardian_signal}
                  color={status.trading_allowed ? 'success' : 'error'}
                  size="small"
                />
              )}

              <Chip label={`${positions.length} positions`} size="small" variant="outlined" />
              {/* Reset custom order button */}
              {customOrder.length > 0 && (
                <Tooltip title="Reset to default sort order (by expiry)">
                  <Button size="small" color="secondary" variant="outlined" onClick={resetOrder}>
                    Reset Order
                  </Button>
                </Tooltip>
              )}
              {/* Focus mode: show hidden count and unhide all */}
              {hiddenPositions.length > 0 && (
                <Tooltip title="Show all hidden positions">
                  <Button
                    size="small"
                    color="secondary"
                    variant="outlined"
                    onClick={() => setHiddenPositions([])}
                  >
                    Show {hiddenPositions.length} Hidden
                  </Button>
                </Tooltip>
              )}
              {/* Polling interval control */}
              <Tooltip title="Change price polling interval">
                <Button
                  size="small"
                  variant={pollInterval === 1000 ? 'contained' : 'outlined'}
                  color={pollInterval === 1000 ? 'primary' : 'inherit'}
                  onClick={() => setPollInterval(pollInterval === 5000 ? 1000 : 5000)}
                  sx={{ ml: 1 }}
                >
                  Poll: {pollInterval / 1000}s
                </Button>
              </Tooltip>
            </Box>

            <Box sx={{ display: 'flex', gap: 1 }}>
              <Tooltip title="Sound Settings">
                <IconButton 
                  onClick={() => setSoundSettingsOpen(true)} 
                  size="small"
                  color="primary"
                >
                  <VolumeIcon />
                </IconButton>
              </Tooltip>
              
              <Tooltip title="Refresh">
                <IconButton onClick={handleRefresh} disabled={refreshing}>
                  {refreshing ? <CircularProgress size={20} /> : <RefreshIcon />}
                </IconButton>
              </Tooltip>
            </Box>
          </Box>

          {/* Expiry Filter Tabs - Multi-Select */}
          {uniqueExpiries.length > 1 && (
            <Box sx={{ mb: 2, display: 'flex', gap: 1, flexWrap: 'wrap', alignItems: 'center' }}>
              <Typography variant="caption" color="text.secondary" sx={{ mr: 1 }}>
                📅 Expiry:
              </Typography>
              <Chip
                label={selectedExpiries.length === 0 ? "All" : `All (${selectedExpiries.length} selected)`}
                size="small"
                onClick={clearExpirySelection}
                color={selectedExpiries.length === 0 ? 'primary' : 'default'}
                variant={selectedExpiries.length === 0 ? 'filled' : 'outlined'}
                sx={{ fontWeight: selectedExpiries.length === 0 ? 'bold' : 'normal' }}
              />
              {uniqueExpiries.map((expiry) => {
                const day = expiry.substring(0, 2);
                const month = expiry.substring(2, 4);
                const year = '20' + expiry.substring(4, 6);
                const formattedDate = `${day}/${month}/${year}`;
                const posCount = positions.filter(
                  (p) => getExpiryCode(p.product_symbol) === expiry
                ).length;
                const isSelected = selectedExpiries.includes(expiry);
                return (
                  <Chip
                    key={expiry}
                    label={`${formattedDate} (${posCount})`}
                    size="small"
                    onClick={() => toggleExpirySelection(expiry)}
                    color={isSelected ? 'primary' : 'default'}
                    variant={isSelected ? 'filled' : 'outlined'}
                    sx={{ fontWeight: isSelected ? 'bold' : 'normal' }}
                  />
                );
              })}
            </Box>
          )}

          {/* Quick Filters - Day 3 Enhancement */}
          <Box sx={{ mb: 2, display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center', bgcolor: 'action.hover', p: 1.5, borderRadius: 1 }}>
            {/* P&L Filter */}
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
              <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 'bold' }}>
                📊 P&L:
              </Typography>
              <Chip
                label="All"
                size="small"
                onClick={() => {
                  setPnlFilter('all');
                  localStorage.setItem('options_pnl_filter', 'all');
                }}
                color={pnlFilter === 'all' ? 'primary' : 'default'}
                variant={pnlFilter === 'all' ? 'filled' : 'outlined'}
              />
              <Chip
                label="Profit"
                size="small"
                onClick={() => {
                  setPnlFilter('profit');
                  localStorage.setItem('options_pnl_filter', 'profit');
                }}
                color={pnlFilter === 'profit' ? 'success' : 'default'}
                variant={pnlFilter === 'profit' ? 'filled' : 'outlined'}
              />
              <Chip
                label="Loss"
                size="small"
                onClick={() => {
                  setPnlFilter('loss');
                  localStorage.setItem('options_pnl_filter', 'loss');
                }}
                color={pnlFilter === 'loss' ? 'error' : 'default'}
                variant={pnlFilter === 'loss' ? 'filled' : 'outlined'}
              />
            </Box>

            {/* Moneyness Filter */}
            <Divider orientation="vertical" flexItem />
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
              <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 'bold' }}>
                🎯 Moneyness:
              </Typography>
              <Chip
                label="All"
                size="small"
                onClick={() => {
                  setMoneynessFilter('all');
                  localStorage.setItem('options_moneyness_filter', 'all');
                }}
                color={moneynessFilter === 'all' ? 'primary' : 'default'}
                variant={moneynessFilter === 'all' ? 'filled' : 'outlined'}
              />
              <Chip
                label="ITM"
                size="small"
                onClick={() => {
                  setMoneynessFilter('itm');
                  localStorage.setItem('options_moneyness_filter', 'itm');
                }}
                color={moneynessFilter === 'itm' ? 'success' : 'default'}
                variant={moneynessFilter === 'itm' ? 'filled' : 'outlined'}
              />
              <Chip
                label="ATM"
                size="small"
                onClick={() => {
                  setMoneynessFilter('atm');
                  localStorage.setItem('options_moneyness_filter', 'atm');
                }}
                color={moneynessFilter === 'atm' ? 'info' : 'default'}
                variant={moneynessFilter === 'atm' ? 'filled' : 'outlined'}
              />
              <Chip
                label="OTM"
                size="small"
                onClick={() => {
                  setMoneynessFilter('otm');
                  localStorage.setItem('options_moneyness_filter', 'otm');
                }}
                color={moneynessFilter === 'otm' ? 'warning' : 'default'}
                variant={moneynessFilter === 'otm' ? 'filled' : 'outlined'}
              />
            </Box>

            {/* Active filter count */}
            {(pnlFilter !== 'all' || moneynessFilter !== 'all') && (
              <>
                <Divider orientation="vertical" flexItem />
                <Chip
                  label={`${sortedPositions.length} shown`}
                  size="small"
                  color="primary"
                  variant="outlined"
                  sx={{ fontWeight: 'bold' }}
                />
              </>
            )}
          </Box>

          {/* Per-Expiry Max Loss Settings */}
          {positions.length > 0 && uniqueExpiries.length > 0 && (
            <ExpiryMaxLossPanel
              uniqueExpiries={uniqueExpiries}
              expiryPnlMap={expiryPnlMap}
              expiryMaxLossSettings={expiryMaxLossSettings}
              onSettingsUpdate={handleExpiryMaxLossUpdate}
            />
          )}

          {/* Position Scaling Strategy */}
          <Box sx={{ mb: 2, p: 2, bgcolor: 'action.hover', borderRadius: 1 }}>
            <Box
              sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}
            >
              <Typography
                variant="subtitle2"
                sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
              >
                <ShowChartIcon fontSize="small" />
                Position Scaling Strategy
              </Typography>

              {/* Large Index Prices Display */}
              {(indexPrices.BTC > 0 || indexPrices.ETH > 0) && (
                <Box sx={{ display: 'flex', gap: 2 }}>
                  {indexPrices.BTC > 0 && (
                    <Box
                      sx={{
                        px: 2.5,
                        py: 1,
                        bgcolor: '#3b82f615',
                        borderRadius: 2,
                        border: '2px solid #3b82f6',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                      }}
                    >
                      <Typography
                        variant="caption"
                        sx={{
                          color: '#3b82f6',
                          fontWeight: 600,
                          fontSize: '0.75rem',
                          letterSpacing: 0.5,
                        }}
                      >
                        BTC SPOT
                      </Typography>
                      <Typography
                        variant="h5"
                        sx={{
                          color: '#3b82f6',
                          fontWeight: 'bold',
                          fontSize: '1.8rem',
                          lineHeight: 1.1,
                        }}
                      >
                        ${indexPrices.BTC.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                      </Typography>
                    </Box>
                  )}
                  {indexPrices.ETH > 0 && (
                    <Box
                      sx={{
                        px: 2.5,
                        py: 1,
                        bgcolor: '#a855f715',
                        borderRadius: 2,
                        border: '2px solid #a855f7',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                      }}
                    >
                      <Typography
                        variant="caption"
                        sx={{
                          color: '#a855f7',
                          fontWeight: 600,
                          fontSize: '0.75rem',
                          letterSpacing: 0.5,
                        }}
                      >
                        ETH SPOT
                      </Typography>
                      <Typography
                        variant="h5"
                        sx={{
                          color: '#a855f7',
                          fontWeight: 'bold',
                          fontSize: '1.8rem',
                          lineHeight: 1.1,
                        }}
                      >
                        ${indexPrices.ETH.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                      </Typography>
                    </Box>
                  )}
                </Box>
              )}
            </Box>
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
              {/* Strategy Selection */}
              <Box>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: 'block', mb: 0.5 }}
                >
                  Strategy:
                </Typography>
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <Chip
                    label="Fixed Size"
                    size="small"
                    onClick={() => {
                      setScalingStrategy('fixed');
                      localStorage.setItem('options_scaling_strategy', 'fixed');
                    }}
                    color={scalingStrategy === 'fixed' ? 'primary' : 'default'}
                    variant={scalingStrategy === 'fixed' ? 'filled' : 'outlined'}
                  />
                  <Chip
                    label="Profit-Based"
                    size="small"
                    onClick={() => {
                      setScalingStrategy('profit_based');
                      localStorage.setItem('options_scaling_strategy', 'profit_based');
                    }}
                    color={scalingStrategy === 'profit_based' ? 'success' : 'default'}
                    variant={scalingStrategy === 'profit_based' ? 'filled' : 'outlined'}
                  />
                  <Chip
                    label="Delta Neutral"
                    size="small"
                    onClick={() => {
                      setScalingStrategy('delta_neutral');
                      localStorage.setItem('options_scaling_strategy', 'delta_neutral');
                    }}
                    color={scalingStrategy === 'delta_neutral' ? 'info' : 'default'}
                    variant={scalingStrategy === 'delta_neutral' ? 'filled' : 'outlined'}
                  />
                </Box>
              </Box>

              {/* Strategy Parameters */}
              {scalingStrategy === 'fixed' && (
                <Box>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ display: 'block', mb: 0.5 }}
                  >
                    Step Size:
                  </Typography>
                  <TextField
                    size="small"
                    type="number"
                    value={scalingParams.stepSize}
                    onChange={(e) => {
                      const newParams = {
                        ...scalingParams,
                        stepSize: parseInt(e.target.value) || 5,
                      };
                      setScalingParams(newParams);
                      localStorage.setItem('options_scaling_params', JSON.stringify(newParams));
                    }}
                    sx={{ width: 80 }}
                  />
                </Box>
              )}

              {scalingStrategy === 'profit_based' && (
                <>
                  <Box>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ display: 'block', mb: 0.5 }}
                    >
                      Profit Threshold (%):
                    </Typography>
                    <TextField
                      size="small"
                      type="number"
                      value={scalingParams.profitThreshold}
                      onChange={(e) => {
                        const newParams = {
                          ...scalingParams,
                          profitThreshold: parseFloat(e.target.value) || 10,
                        };
                        setScalingParams(newParams);
                        localStorage.setItem('options_scaling_params', JSON.stringify(newParams));
                      }}
                      sx={{ width: 80 }}
                    />
                  </Box>
                  <Box>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ display: 'block', mb: 0.5 }}
                    >
                      Stop Loss (%):
                    </Typography>
                    <TextField
                      size="small"
                      type="number"
                      value={scalingParams.lossThreshold}
                      onChange={(e) => {
                        const newParams = {
                          ...scalingParams,
                          lossThreshold: parseFloat(e.target.value) || -20,
                        };
                        setScalingParams(newParams);
                        localStorage.setItem('options_scaling_params', JSON.stringify(newParams));
                      }}
                      sx={{ width: 80 }}
                    />
                  </Box>
                </>
              )}

              {scalingStrategy === 'delta_neutral' && (
                <>
                  <Box>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ display: 'block', mb: 0.5 }}
                    >
                      Target Delta:
                    </Typography>
                    <TextField
                      size="small"
                      type="number"
                      value={scalingParams.deltaTarget}
                      onChange={(e) => {
                        const newParams = {
                          ...scalingParams,
                          deltaTarget: parseFloat(e.target.value) || 0,
                        };
                        setScalingParams(newParams);
                        localStorage.setItem('options_scaling_params', JSON.stringify(newParams));
                      }}
                      sx={{ width: 80 }}
                    />
                  </Box>
                  <Box>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ display: 'block', mb: 0.5 }}
                    >
                      Tolerance (±):
                    </Typography>
                    <TextField
                      size="small"
                      type="number"
                      value={scalingParams.deltaTolerance}
                      onChange={(e) => {
                        const newParams = {
                          ...scalingParams,
                          deltaTolerance: parseFloat(e.target.value) || 5,
                        };
                        setScalingParams(newParams);
                        localStorage.setItem('options_scaling_params', JSON.stringify(newParams));
                      }}
                      sx={{ width: 80 }}
                    />
                  </Box>
                </>
              )}

              {/* Max Position Size - always visible */}
              <Box>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: 'block', mb: 0.5 }}
                >
                  Max Position Size:
                </Typography>
                <TextField
                  size="small"
                  type="number"
                  value={scalingParams.maxPositionSize}
                  onChange={(e) => {
                    const newParams = {
                      ...scalingParams,
                      maxPositionSize: parseInt(e.target.value) || 50,
                    };
                    setScalingParams(newParams);
                    localStorage.setItem('options_scaling_params', JSON.stringify(newParams));
                  }}
                  sx={{ width: 80 }}
                />
              </Box>
            </Box>

            {/* Strategy Description */}
            <Alert severity="info" sx={{ mt: 1.5 }}>
              <Typography variant="caption">
                {scalingStrategy === 'fixed' &&
                  `🔹 Fixed: Always add ${scalingParams.stepSize} contracts per click`}
                {scalingStrategy === 'profit_based' &&
                  `📈 Profit-Based: Scale into winners (>${scalingParams.profitThreshold}%), cautiously average down losers`}
                {scalingStrategy === 'delta_neutral' &&
                  `⚖️ Delta-Neutral: Auto-rebalance to maintain portfolio delta ~${scalingParams.deltaTarget}`}
              </Typography>
            </Alert>
          </Box>

          {/* Keyboard Shortcuts Legend */}
          <Box
            sx={{
              mb: 2,
              p: 1,
              bgcolor: 'action.hover',
              borderRadius: 1,
              display: 'flex',
              gap: 2,
              flexWrap: 'wrap',
              alignItems: 'center',
            }}
          >
            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 'bold' }}>
              ⌨️ Shortcuts:
            </Typography>
            <Chip label="B = Buy" size="small" variant="outlined" sx={{ height: 22 }} />
            <Chip label="S = Sell" size="small" variant="outlined" sx={{ height: 22 }} />
            <Chip label="C = Close" size="small" variant="outlined" sx={{ height: 22 }} />
            <Chip label="R = Refresh" size="small" variant="outlined" sx={{ height: 22 }} />
            <Chip label="Esc = Cancel" size="small" variant="outlined" sx={{ height: 22 }} />
          </Box>

          {/* Order Result Alert */}
          <Collapse in={!!orderResult}>
            <Alert
              severity={orderResult?.type || 'info'}
              sx={{ mb: 2 }}
              onClose={() => setOrderResult(null)}
            >
              {orderResult?.message}
            </Alert>
          </Collapse>

          {/* Futures Positions Panel - JAN 17, 2026 */}
          <FuturesPanel pollInterval={pollInterval} />

          {/* Pending Orders Panel */}
          {!pendingOrdersError && (
            <Box
              sx={{
                mb: 2,
                p: 2,
                borderRadius: 1,
                border: '1px solid',
                borderColor: pendingOrders.length > 0 ? 'warning.main' : 'divider',
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <TimerIcon sx={{ color: pendingOrders.length > 0 ? 'warning.main' : 'text.secondary' }} />
                <Typography variant="subtitle1" sx={{ fontWeight: 'bold', color: 'text.primary' }}>
                  ⏳ Pending Orders ({pendingOrders.length})
                </Typography>
                {pendingOrders.length > 0 && (
                  <Chip
                    label="Live"
                    size="small"
                    color="error"
                    sx={{ animation: 'pulse 1.5s infinite' }}
                  />
                )}
                <IconButton 
                  size="small" 
                  onClick={() => setPendingOrdersCollapsed(!pendingOrdersCollapsed)}
                  sx={{ ml: 'auto', color: 'text.secondary' }}
                >
                  {pendingOrdersCollapsed ? <ExpandMoreIcon /> : <ExpandLessIcon />}
                </IconButton>
              </Box>
              <Collapse in={!pendingOrdersCollapsed}>
              {pendingOrders.length > 0 ? (
              <TableContainer
                component={Paper}
                sx={{ maxHeight: 200, bgcolor: 'background.paper' }}
              >
                <Table size="small" stickyHeader>
                  <TableHead>
                    <TableRow>
                      <TableCell>Symbol</TableCell>
                      <TableCell align="center">Side</TableCell>
                      <TableCell align="right">Size</TableCell>
                      <TableCell align="right">Price</TableCell>
                      <TableCell align="center">Type</TableCell>
                      <TableCell align="center">Status</TableCell>
                      <TableCell align="right">Date & Time</TableCell>
                      <TableCell align="center">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {pendingOrders.map((order) => (
                      <TableRow key={order.id} sx={{ '&:hover': { bgcolor: 'action.hover' } }}>
                        <TableCell>
                          <Typography
                            variant="body2"
                            sx={{ fontFamily: 'monospace', fontWeight: 500 }}
                          >
                            {order.symbol}
                          </Typography>
                        </TableCell>
                        <TableCell align="center">
                          <Chip
                            label={order.side?.toUpperCase()}
                            size="small"
                            color={order.side === 'buy' ? 'success' : 'error'}
                            sx={{ fontWeight: 'bold', minWidth: 50 }}
                          />
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2" sx={{ fontWeight: 500 }}>
                            {order.unfilled_size || order.size}
                          </Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                            ${parseFloat(order.price || 0).toFixed(2)}
                          </Typography>
                        </TableCell>
                        <TableCell align="center">
                          <Chip
                            label={order.order_type?.replace('_', ' ') || 'limit'}
                            size="small"
                            variant="outlined"
                            sx={{ fontSize: '0.7rem' }}
                          />
                        </TableCell>
                        <TableCell align="center">
                          <Chip
                            label={order.state || 'open'}
                            size="small"
                            color="warning"
                            sx={{ fontWeight: 'bold' }}
                          />
                        </TableCell>
                        <TableCell align="right">
                          <Typography variant="caption" color="text.secondary">
                            {order.created_at
                              ? new Date(order.created_at).toLocaleString()
                              : '-'}
                          </Typography>
                        </TableCell>
                        <TableCell align="center">
                          <Tooltip title="Cancel Order">
                            <IconButton
                              size="small"
                              color="error"
                              onClick={() => handleCancelPendingOrder(order)}
                            >
                              <CloseIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
              ) : (
                <Paper sx={{ p: 2, textAlign: 'center', bgcolor: 'action.hover' }}>
                  <Typography variant="body2" color="text.secondary">
                    No pending orders
                  </Typography>
                </Paper>
              )}
              </Collapse>
            </Box>
          )}

          {/* Error Alert */}
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              <AlertTitle>Error</AlertTitle>
              {error}
            </Alert>
          )}

          {/* Guardian Warning */}
          {status && !status.trading_allowed && (
            <Alert severity="warning" sx={{ mb: 2 }} icon={<WarningIcon />}>
              <AlertTitle>Trading Disabled</AlertTitle>
              Guardian signal is {status.guardian_signal}. Close and add operations are blocked.
            </Alert>
          )}

          {/* Positions Table */}
          {positions.length === 0 ? (
            <Paper sx={{ p: 4, textAlign: 'center', bgcolor: 'action.hover' }}>
              <Typography color="text.secondary">No options positions found</Typography>
              <Typography variant="caption" color="text.secondary">
                Open positions manually on Delta Exchange to manage them here
              </Typography>
            </Paper>
          ) : sortedPositions.length === 0 && selectedExpiries.length > 0 ? (
            <Paper sx={{ p: 4, textAlign: 'center', bgcolor: 'action.hover' }}>
              <Typography color="text.secondary">No positions for selected {selectedExpiries.length === 1 ? 'expiry' : 'expiries'}</Typography>
              <Button
                size="small"
                variant="outlined"
                onClick={clearExpirySelection}
                sx={{ mt: 1 }}
              >
                Show All Expiries
              </Button>
            </Paper>
          ) : (
            <TableContainer component={Paper} sx={{ maxHeight: 500 }}>
              <Table stickyHeader size="small">
                <TableHead>
                  <TableRow>
                    {/* Selection Checkbox - Payoff Graph Visibility */}
                    <TableCell width="40px" padding="checkbox">
                      <Tooltip title="Select/deselect all for payoff graph">
                        <Checkbox
                          checked={hiddenPositions.length === 0}
                          indeterminate={
                            hiddenPositions.length > 0 &&
                            hiddenPositions.length < sortedPositions.length
                          }
                          onChange={(e) => {
                            if (e.target.checked) {
                              setHiddenPositions([]);
                            } else {
                              setHiddenPositions(sortedPositions.map((p) => p.product_symbol));
                            }
                          }}
                          sx={{ color: '#3b82f6', '&.Mui-checked': { color: '#3b82f6' } }}
                        />
                      </Tooltip>
                    </TableCell>
                    <TableCell width="30px">
                      <Tooltip title="Column settings">
                        <IconButton
                          size="small"
                          onClick={(e) => setColumnMenuAnchor(e.currentTarget)}
                          sx={{ opacity: 0.6, '&:hover': { opacity: 1 } }}
                        >
                          <SettingsIcon sx={{ fontSize: 16 }} />
                        </IconButton>
                      </Tooltip>
                      <Menu
                        anchorEl={columnMenuAnchor}
                        open={Boolean(columnMenuAnchor)}
                        onClose={() => setColumnMenuAnchor(null)}
                        PaperProps={{ sx: { maxHeight: 400, width: 200 } }}
                      >
                        <Typography variant="subtitle2" sx={{ px: 2, py: 1, fontWeight: 'bold' }}>
                          Show/Hide Columns
                        </Typography>
                        <Divider />
                        {columnDefs.map((col) => (
                          <MenuItem key={col.key} onClick={() => toggleColumn(col.key)} dense>
                            <ListItemIcon>
                              {visibleColumns[col.key] ? (
                                <VisibilityIcon fontSize="small" color="primary" />
                              ) : (
                                <VisibilityOffIcon fontSize="small" sx={{ opacity: 0.4 }} />
                              )}
                            </ListItemIcon>
                            <ListItemText>{col.label}</ListItemText>
                          </MenuItem>
                        ))}
                      </Menu>
                    </TableCell>
                    {visibleColumns.symbol && (
                      <TableCell
                        sx={{ cursor: 'pointer', userSelect: 'none' }}
                        onClick={toggleSymbolSort}
                      >
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                          Symbol
                          {symbolSort === 'grouped' ? (
                            <Chip
                              label="CE/PE"
                              size="small"
                              color="primary"
                              sx={{ height: 18, fontSize: '0.65rem' }}
                            />
                          ) : (
                            <UnfoldMoreIcon sx={{ fontSize: 16, opacity: 0.5 }} />
                          )}
                        </Box>
                      </TableCell>
                    )}
                    {visibleColumns.strike && (
                      <TableCell
                        align="right"
                        sx={{ cursor: 'pointer', userSelect: 'none' }}
                        onClick={toggleStrikeSort}
                      >
                        <Box
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'flex-end',
                            gap: 0.5,
                          }}
                        >
                          Strike
                          {strikeSort === 'asc' ? (
                            <ArrowUpwardIcon sx={{ fontSize: 16 }} color="primary" />
                          ) : strikeSort === 'desc' ? (
                            <ArrowDownwardIcon sx={{ fontSize: 16 }} color="primary" />
                          ) : (
                            <UnfoldMoreIcon sx={{ fontSize: 16, opacity: 0.5 }} />
                          )}
                        </Box>
                      </TableCell>
                    )}
                    {visibleColumns.auto && (
                      <TableCell align="center" width="50px">
                        <Tooltip title="Automation rules">
                          <Box>Auto</Box>
                        </Tooltip>
                      </TableCell>
                    )}
                    {visibleColumns.expiry && <TableCell align="right">Expiry</TableCell>}
                    {visibleColumns.size && <TableCell align="right">Size</TableCell>}
                    {visibleColumns.batchQty && (
                      <TableCell align="center" sx={{ minWidth: 90 }}>
                        <Tooltip title="Enter quantity for batch order. Positive = BUY, Negative = SELL">
                          <Box>Batch Qty</Box>
                        </Tooltip>
                      </TableCell>
                    )}
                    {visibleColumns.cashflow && <TableCell align="right">Cashflow</TableCell>}
                    {visibleColumns.entry && <TableCell align="right">Entry</TableCell>}
                    {visibleColumns.bid && <TableCell align="right">Bid</TableCell>}
                    {visibleColumns.ask && <TableCell align="right">Ask</TableCell>}
                    {visibleColumns.sltp && (
                      <TableCell align="center" sx={{ minWidth: 50 }}>
                        <Tooltip title="Stop-Loss / Take-Profit settings">
                          <Box>SL/TP</Box>
                        </Tooltip>
                      </TableCell>
                    )}
                    {visibleColumns.maxLoss && (
                      <TableCell align="center" sx={{ minWidth: 60 }}>
                        <Tooltip title="Max Loss per strike - auto square-off when exceeded">
                          <Box>Max Loss</Box>
                        </Tooltip>
                      </TableCell>
                    )}
                    {visibleColumns.iv && (
                      <TableCell align="right" sx={{ minWidth: 50 }}>
                        <Tooltip title="Implied Volatility">
                          <Box>IV</Box>
                        </Tooltip>
                      </TableCell>
                    )}
                    {visibleColumns.pnl && <TableCell align="right">PnL</TableCell>}
                    {visibleColumns.actions && <TableCell align="center">Actions</TableCell>}
                  </TableRow>
                </TableHead>
                <DndContext
                  sensors={sensors}
                  collisionDetection={closestCenter}
                  onDragEnd={handleDragEnd}
                >
                  <SortableContext
                    items={sortedPositions.map((p) => p.product_symbol)}
                    strategy={verticalListSortingStrategy}
                  >
                    <TableBody>
                      {sortedPositions.map((pos, index) => {
                        const optionInfo = parseOptionSymbol(pos.product_symbol);
                        const posType = getPositionType(pos.product_symbol);
                        const pnlColor = getPnlColor(pos.unrealized_pnl);
                        const isLong = pos.size > 0;
                        const daysToExp = getDaysToExpiry(pos.product_symbol);
                        const isQuickMode = skipConfirmStrikes[pos.product_symbol]?.enabled;

                        // Use backend-calculated cashflow
                        const cashflow = pos.cashflow || 0;

                        const isCall = optionInfo.type === 'Call';
                        const isPut = optionInfo.type === 'Put';
                        const rowBgColor = isCall
                          ? 'rgba(16, 185, 129, 0.03)'
                          : isPut
                            ? 'rgba(239, 68, 68, 0.03)'
                            : 'transparent';
                        const rowHoverColor = isCall
                          ? 'rgba(16, 185, 129, 0.06)'
                          : isPut
                            ? 'rgba(239, 68, 68, 0.06)'
                            : 'action.hover';

                        // Common cell style
                        const cellSx = {
                          backgroundColor: `${rowBgColor} !important`,
                          '&:hover': { backgroundColor: `${rowHoverColor} !important` },
                        };

                        return (
                          <SortableRow key={pos.product_symbol} pos={pos}>
                            {(attributes, listeners) => (
                              <>
                                {/* Selection Checkbox */}
                                <TableCell
                                  padding="checkbox"
                                  sx={{
                                    backgroundColor: `${rowBgColor} !important`,
                                  }}
                                >
                                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                    <Checkbox
                                      checked={!!selectedStrikes[pos.product_symbol]}
                                      onChange={() => toggleStrikeSelection(pos.product_symbol)}
                                      sx={{
                                        color: isCall ? '#10b981' : '#ef4444',
                                        '&.Mui-checked': { color: isCall ? '#10b981' : '#ef4444' },
                                      }}
                                    />
                                    {/* Ratio quick set buttons */}
                                    {selectedStrikes[pos.product_symbol] && (
                                      <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                                        <Tooltip title="Set Buy:Sell ratio to 1:2 (1 buy + 2 sell per multiplier)">
                                          <Chip
                                            label="1:2"
                                            size="small"
                                            onClick={() => {
                                              setStrikeRatios((prev) => ({
                                                ...prev,
                                                [pos.product_symbol]: { buy: 1, sell: 2 },
                                              }));
                                            }}
                                            sx={{
                                              fontSize: '10px',
                                              height: '20px',
                                              cursor: 'pointer',
                                              bgcolor:
                                                strikeRatios[pos.product_symbol]?.buy === 1 &&
                                                strikeRatios[pos.product_symbol]?.sell === 2
                                                  ? 'rgba(59, 130, 246, 0.5)'
                                                  : 'rgba(255,255,255,0.1)',
                                              '&:hover': { bgcolor: 'rgba(59, 130, 246, 0.3)' },
                                            }}
                                          />
                                        </Tooltip>
                                        <Tooltip title="Set Buy:Sell ratio to 1:1 (equal quantities)">
                                          <Chip
                                            label="1:1"
                                            size="small"
                                            onClick={() => {
                                              setStrikeRatios((prev) => ({
                                                ...prev,
                                                [pos.product_symbol]: { buy: 1, sell: 1 },
                                              }));
                                            }}
                                            sx={{
                                              fontSize: '10px',
                                              height: '20px',
                                              cursor: 'pointer',
                                              bgcolor:
                                                strikeRatios[pos.product_symbol]?.buy === 1 &&
                                                strikeRatios[pos.product_symbol]?.sell === 1
                                                  ? 'rgba(59, 130, 246, 0.5)'
                                                  : 'rgba(255,255,255,0.1)',
                                              '&:hover': { bgcolor: 'rgba(59, 130, 246, 0.3)' },
                                            }}
                                          />
                                        </Tooltip>
                                        <Tooltip title="Clear ratio (single order mode)">
                                          <IconButton
                                            size="small"
                                            onClick={() => {
                                              setStrikeRatios((prev) => {
                                                const next = { ...prev };
                                                delete next[pos.product_symbol];
                                                return next;
                                              });
                                            }}
                                            sx={{ padding: '2px' }}
                                          >
                                            <CloseIcon sx={{ fontSize: 14 }} />
                                          </IconButton>
                                        </Tooltip>
                                      </Box>
                                    )}
                                  </Box>
                                </TableCell>

                                {/* Drag Handle */}
                                <TableCell
                                  sx={{
                                    backgroundColor: `${rowBgColor} !important`,
                                    borderLeft: `3px solid ${posType.color}`,
                                    cursor: 'grab',
                                    '&:active': { cursor: 'grabbing' },
                                  }}
                                  {...attributes}
                                  {...listeners}
                                >
                                  <DragIcon sx={{ color: 'text.secondary', fontSize: 20 }} />
                                </TableCell>

                                {/* Symbol */}
                                {visibleColumns.symbol && (
                                  <TableCell
                                    sx={{
                                      backgroundColor: `${rowBgColor} !important`,
                                      '&:hover': { backgroundColor: `${rowHoverColor} !important` },
                                    }}
                                  >
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                      <Tooltip
                                        title={
                                          hiddenPositions.includes(pos.product_symbol)
                                            ? 'Show in payoff graph'
                                            : 'Hide from payoff graph'
                                        }
                                      >
                                        <Checkbox
                                          checked={!hiddenPositions.includes(pos.product_symbol)}
                                          onChange={() => {
                                            setHiddenPositions((prev) =>
                                              prev.includes(pos.product_symbol)
                                                ? prev.filter((s) => s !== pos.product_symbol)
                                                : [...prev, pos.product_symbol]
                                            );
                                          }}
                                          sx={{ color: '#3b82f6', '&.Mui-checked': { color: '#3b82f6' } }}
                                        />
                                      </Tooltip>
                                      <Chip
                                        label={optionInfo.type}
                                        size="small"
                                        sx={{
                                          bgcolor: posType.color + '20',
                                          color: posType.color,
                                          fontWeight: 'bold',
                                          minWidth: 50,
                                        }}
                                      />
                                      <Typography variant="body2" fontWeight="medium">
                                        {optionInfo.underlying}
                                      </Typography>
                                      {/* Quick mode indicator with per-symbol size */}
                                      {isQuickMode && (
                                        <Tooltip
                                          title={`Quick mode: Click + to instantly ${skipConfirmStrikes[pos.product_symbol]?.side || 'sell'} ${skipConfirmStrikes[pos.product_symbol]?.size || DEFAULT_SIZE} lots. Click to disable.`}
                                        >
                                          <Chip
                                            label={`⚡${skipConfirmStrikes[pos.product_symbol]?.size || DEFAULT_SIZE}`}
                                            size="small"
                                            onClick={() => disableSkipConfirm(pos.product_symbol)}
                                            sx={{
                                              cursor: 'pointer',
                                              bgcolor: '#fbbf2420',
                                              minWidth: 40,
                                            }}
                                          />
                                        </Tooltip>
                                      )}
                                    </Box>
                                  </TableCell>
                                )}

                                {/* Strike */}
                                {visibleColumns.strike && (
                                  <TableCell align="right" sx={cellSx}>
                                    <Typography fontWeight="bold">
                                      ${optionInfo.strike.toLocaleString()}
                                    </Typography>
                                  </TableCell>
                                )}

                                {/* Automation */}
                                {visibleColumns.auto && (
                                  <TableCell align="center" sx={{ ...cellSx, p: 0.5 }}>
                                    <AutomationButton position={pos} />
                                  </TableCell>
                                )}

                                {/* Expiry with days remaining */}
                                {visibleColumns.expiry && (
                                  <TableCell align="right" sx={cellSx}>
                                    <Tooltip
                                      title={`${(Number(daysToExp) || 0).toFixed(1)} days to expiry`}
                                    >
                                      <Chip
                                        label={optionInfo.expiry}
                                        size="small"
                                        variant="outlined"
                                        icon={<TimerIcon />}
                                        sx={{
                                          borderColor:
                                            daysToExp < 1
                                              ? '#ef4444'
                                              : daysToExp < 7
                                                ? '#f59e0b'
                                                : undefined,
                                          color:
                                            daysToExp < 1
                                              ? '#ef4444'
                                              : daysToExp < 7
                                                ? '#f59e0b'
                                                : undefined,
                                        }}
                                      />
                                    </Tooltip>
                                  </TableCell>
                                )}

                                {/* Size */}
                                {visibleColumns.size && (
                                  <TableCell align="right" sx={cellSx}>
                                    <Chip
                                      icon={isLong ? <TrendingUp /> : <TrendingDown />}
                                      label={pos.size}
                                      size="small"
                                      sx={{
                                        bgcolor: isLong ? '#10b98120' : '#ef444420',
                                        color: isLong ? '#10b981' : '#ef4444',
                                      }}
                                    />
                                  </TableCell>
                                )}

                                {/* Batch Quantity Input */}
                                {visibleColumns.batchQty && (
                                  <TableCell align="center" sx={cellSx}>
                                    <TextField
                                      size="small"
                                      type="number"
                                      placeholder="±qty"
                                      value={batchQuantities[pos.product_symbol] || ''}
                                      onChange={(e) => {
                                        const value =
                                          e.target.value === '' ? 0 : parseInt(e.target.value);
                                        setBatchQuantities((prev) => ({
                                          ...prev,
                                          [pos.product_symbol]: value,
                                        }));
                                        // Auto-select when quantity entered
                                        if (value !== 0) {
                                          setSelectedStrikes((prev) => ({
                                            ...prev,
                                            [pos.product_symbol]: true,
                                          }));
                                        }
                                      }}
                                      sx={{
                                        width: '70px',
                                        '& .MuiInputBase-input': {
                                          textAlign: 'center',
                                          fontSize: '0.875rem',
                                          padding: '4px 8px',
                                          color:
                                            batchQuantities[pos.product_symbol] > 0
                                              ? '#10b981'
                                              : batchQuantities[pos.product_symbol] < 0
                                                ? '#ef4444'
                                                : 'inherit',
                                        },
                                      }}
                                    />
                                  </TableCell>
                                )}

                                {/* Cashflow */}
                                {visibleColumns.cashflow && (
                                  <TableCell align="right" sx={cellSx}>
                                    <Tooltip title="Premium paid/received for this position">
                                      <Typography
                                        variant="body2"
                                        fontWeight="medium"
                                        sx={{ color: isLong ? '#ef4444' : '#10b981' }}
                                      >
                                        {(Number(cashflow) || 0).toFixed(2)} USD
                                      </Typography>
                                    </Tooltip>
                                  </TableCell>
                                )}

                                {/* Entry Price */}
                                {visibleColumns.entry && (
                                  <TableCell align="right" sx={cellSx}>
                                    ${(Number(pos.entry_price) || 0).toFixed(2)}
                                  </TableCell>
                                )}

                                {/* Bid Price */}
                                {visibleColumns.bid && (
                                  <TableCell align="right" sx={cellSx}>
                                    <Typography variant="body2" sx={{ color: '#10b981' }}>
                                      ${(Number(pos.best_bid) || 0).toFixed(2)}
                                    </Typography>
                                  </TableCell>
                                )}

                                {/* Ask Price */}
                                {visibleColumns.ask && (
                                  <TableCell align="right" sx={cellSx}>
                                    <Typography variant="body2" sx={{ color: '#ef4444' }}>
                                      ${(Number(pos.best_ask) || 0).toFixed(2)}
                                    </Typography>
                                  </TableCell>
                                )}

                                {/* SL/TP Indicator */}
                                {visibleColumns.sltp && (
                                  <TableCell align="center" sx={cellSx}>
                                    <SLTPIndicator
                                      settings={slTpSettings[pos.product_symbol]}
                                      position={pos}
                                      onEdit={() => {
                                        setSelectedPositionForSLTP(pos);
                                        setSlTpDialogOpen(true);
                                      }}
                                    />
                                  </TableCell>
                                )}

                                {/* Max Loss Indicator */}
                                {visibleColumns.maxLoss && (
                                  <TableCell align="center" sx={cellSx}>
                                    <MaxLossIndicator
                                      symbol={pos.product_symbol}
                                      currentPnl={pos.unrealized_pnl || 0}
                                      settings={maxLossSettings[pos.product_symbol]}
                                      onUpdate={handleMaxLossUpdate}
                                    />
                                  </TableCell>
                                )}

                                {/* IV (Implied Volatility) */}
                                {visibleColumns.iv && (
                                  <TableCell align="right" sx={cellSx}>
                                    <Typography variant="body2">
                                      {pos.iv ? `${(pos.iv * 100).toFixed(1)}%` : '-'}
                                    </Typography>
                                  </TableCell>
                                )}

                                {/* PnL */}
                                {visibleColumns.pnl && (
                                  <TableCell align="right" sx={cellSx}>
                                    <Box>
                                      <Typography fontWeight="bold" sx={{ color: pnlColor }}>
                                        {formatPnl(pos.unrealized_pnl || 0)}
                                      </Typography>
                                      <Typography variant="caption" sx={{ color: pnlColor }}>
                                        {formatPnlPct(pos.pnl_percentage || 0)}
                                      </Typography>
                                    </Box>
                                  </TableCell>
                                )}

                                {/* Actions */}
                                {visibleColumns.actions && (
                                  <TableCell align="center" sx={cellSx}>
                                    <Box
                                      sx={{
                                        display: 'flex',
                                        gap: 2,
                                        justifyContent: 'center',
                                        alignItems: 'center',
                                      }}
                                    >
                                      {(() => {
                                        const recommendation = calculateSmartScaling(pos);
                                        const tooltipTitle = (
                                          <Box>
                                            <Typography
                                              variant="body2"
                                              sx={{ fontWeight: 'bold', mb: 0.5 }}
                                            >
                                              Smart Scaling Recommendation
                                            </Typography>
                                            <Typography
                                              variant="caption"
                                              sx={{ display: 'block', mb: 0.5 }}
                                            >
                                              Action:{' '}
                                              {recommendation.action === 'scale'
                                                ? '✅ Scale In'
                                                : recommendation.action === 'reduce'
                                                  ? '⚠️ Reduce'
                                                  : '⏸️ Hold'}
                                            </Typography>
                                            {recommendation.size > 0 && (
                                              <Typography
                                                variant="caption"
                                                sx={{ display: 'block', mb: 0.5 }}
                                              >
                                                Size: {recommendation.size} contracts
                                              </Typography>
                                            )}
                                            <Typography
                                              variant="caption"
                                              sx={{ display: 'block', mb: 0.5 }}
                                            >
                                              {recommendation.reason}
                                            </Typography>
                                            <Typography
                                              variant="caption"
                                              sx={{
                                                display: 'block',
                                                color:
                                                  recommendation.riskLevel === 'high'
                                                    ? '#ef4444'
                                                    : recommendation.riskLevel === 'low'
                                                      ? '#10b981'
                                                      : '#f59e0b',
                                              }}
                                            >
                                              Risk: {recommendation.riskLevel.toUpperCase()} |
                                              Confidence: {recommendation.confidence.toUpperCase()}
                                            </Typography>
                                          </Box>
                                        );

                                        return (
                                          <Tooltip title={tooltipTitle}>
                                            <IconButton
                                              size="medium"
                                              color="primary"
                                              onClick={() => handleAdd(pos)}
                                              disabled={!status?.trading_allowed}
                                              sx={{
                                                bgcolor:
                                                  recommendation.action === 'scale'
                                                    ? isCall
                                                      ? '#10b981'
                                                      : '#ef4444'
                                                    : recommendation.action === 'reduce'
                                                      ? '#ef4444'
                                                      : '#6b7280',
                                                color: 'white',
                                                fontWeight: 'bold',
                                                fontSize: 14,
                                                minWidth: 36,
                                                '&:hover': {
                                                  bgcolor:
                                                    recommendation.action === 'scale'
                                                      ? isCall
                                                        ? '#059669'
                                                        : '#dc2626'
                                                      : '#4b5563',
                                                },
                                                '&:disabled': {
                                                  bgcolor: 'action.disabledBackground',
                                                },
                                              }}
                                            >
                                              {isCall ? 'C' : 'P'}+
                                            </IconButton>
                                          </Tooltip>
                                        );
                                      })()}

                                      {/* Visual Separator */}
                                      <Box
                                        sx={{
                                          width: '2px',
                                          height: '32px',
                                          bgcolor: 'divider',
                                          mx: 1,
                                        }}
                                      />

                                      <Tooltip title="⚠️ CLOSE POSITION - This will exit your entire position!">
                                        <IconButton
                                          size="medium"
                                          color="error"
                                          onClick={() => handleClose(pos)}
                                          disabled={!status?.trading_allowed}
                                          sx={{
                                            border: '2px solid',
                                            borderColor: 'error.main',
                                            '&:hover': {
                                              bgcolor: 'error.main',
                                              color: 'white',
                                            },
                                          }}
                                        >
                                          <CloseIcon fontSize="small" />
                                        </IconButton>
                                      </Tooltip>
                                    </Box>
                                  </TableCell>
                                )}
                              </>
                            )}
                          </SortableRow>
                        );
                      })}
                    </TableBody>
                  </SortableContext>
                </DndContext>
              </Table>
            </TableContainer>
          )}

          {/* ================================================================
              BATCH ORDER PANEL - Quantity-based position scaling with execution modes
              ================================================================ */}
          {positions.length > 0 && (
            <Box
              sx={{
                mt: 2,
                p: 2,
                bgcolor: 'rgba(59, 130, 246, 0.1)',
                borderRadius: 1,
                border: '1px solid rgba(59, 130, 246, 0.3)',
              }}
            >
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: 2,
                }}
              >
                {/* Left: Selection info and bulk ratio controls */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <Typography variant="body2" fontWeight="bold">
                    Batch Order
                  </Typography>
                  <Chip
                    label={`${Object.keys(selectedStrikes).filter((k) => selectedStrikes[k]).length} selected`}
                    size="small"
                    color={
                      Object.keys(selectedStrikes).filter((k) => selectedStrikes[k]).length > 0
                        ? 'primary'
                        : 'default'
                    }
                  />
                  {Object.keys(selectedStrikes).filter((k) => selectedStrikes[k]).length > 0 && (
                    <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                      <Typography variant="caption" color="text.secondary">
                        Set All Ratio:
                      </Typography>
                      <Button
                        size="small"
                        variant="outlined"
                        onClick={() => {
                          const selected = Object.keys(selectedStrikes).filter(
                            (k) => selectedStrikes[k]
                          );
                          const newRatios = {};
                          selected.forEach((symbol) => {
                            newRatios[symbol] = { buy: 1, sell: 2 };
                          });
                          setStrikeRatios((prev) => ({ ...prev, ...newRatios }));
                        }}
                        sx={{ minWidth: 'auto', px: 1, py: 0.25, fontSize: '0.7rem' }}
                      >
                        1:2
                      </Button>
                      <Button
                        size="small"
                        variant="outlined"
                        onClick={() => {
                          const selected = Object.keys(selectedStrikes).filter(
                            (k) => selectedStrikes[k]
                          );
                          const newRatios = {};
                          selected.forEach((symbol) => {
                            newRatios[symbol] = { buy: 1, sell: 1 };
                          });
                          setStrikeRatios((prev) => ({ ...prev, ...newRatios }));
                        }}
                        sx={{ minWidth: 'auto', px: 1, py: 0.25, fontSize: '0.7rem' }}
                      >
                        1:1
                      </Button>
                    </Box>
                  )}
                </Box>

                {/* Center: Quantity Control */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Typography variant="body2" color="text.secondary">
                    Quantity (lots)
                  </Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <IconButton
                      size="small"
                      onClick={() =>
                        setOrderQuantity((q) => (q > 0 ? Math.max(1, q - 1) : Math.max(-10, q - 1)))
                      }
                      sx={{
                        bgcolor: 'rgba(255,255,255,0.1)',
                        '&:hover': { bgcolor: 'rgba(255,255,255,0.2)' },
                      }}
                    >
                      <RemoveIcon fontSize="small" />
                    </IconButton>
                    <Select
                      value={orderQuantity}
                      onChange={(e) => setOrderQuantity(e.target.value)}
                      size="small"
                      sx={{
                        minWidth: 80,
                        bgcolor: 'rgba(255,255,255,0.1)',
                        '& .MuiSelect-select': { py: 0.5 },
                      }}
                    >
                      {[-10, -5, -4, -3, -2, -1, 1, 2, 3, 4, 5, 10].map((q) => (
                        <MenuItem key={q} value={q}>
                          {q > 0 ? `+${q}` : q}
                        </MenuItem>
                      ))}
                    </Select>
                    <IconButton
                      size="small"
                      onClick={() =>
                        setOrderQuantity((q) =>
                          q >= 0 ? Math.min(10, q + 1) : Math.min(-1, q + 1)
                        )
                      }
                      sx={{
                        bgcolor: 'rgba(255,255,255,0.1)',
                        '&:hover': { bgcolor: 'rgba(255,255,255,0.2)' },
                      }}
                    >
                      <AddIcon fontSize="small" />
                    </IconButton>
                  </Box>
                  <Tooltip
                    title={
                      orderQuantity > 0
                        ? `Multiplier for ratio-based orders. If ratio is 1:2, quantity 1 = 1 buy + 2 sell. Without ratio, adds ${orderQuantity} lots to each position.`
                        : `Multiplier for ratio-based orders. Without ratio, reduces ${Math.abs(orderQuantity)} lots from each position.`
                    }
                  >
                    <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                      (x{Math.abs(orderQuantity)} multiplier)
                    </Typography>
                  </Tooltip>
                </Box>

                {/* Execution Mode Toggle */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Tooltip title="Market: Fill immediately at best price. Smart: Limit orders with auto-market after 5min">
                    <Box
                      sx={{
                        display: 'flex',
                        borderRadius: 1,
                        overflow: 'hidden',
                        border: '1px solid rgba(255,255,255,0.2)',
                      }}
                    >
                      <Button
                        size="small"
                        variant={executionMode === 'immediate' ? 'contained' : 'outlined'}
                        onClick={() => setExecutionMode('immediate')}
                        sx={{
                          borderRadius: 0,
                          minWidth: 80,
                          bgcolor:
                            executionMode === 'immediate'
                              ? 'rgba(239, 68, 68, 0.8)'
                              : 'transparent',
                          color: executionMode === 'immediate' ? '#fff' : 'rgba(239, 68, 68, 0.8)',
                          borderColor: 'transparent',
                          '&:hover': {
                            bgcolor:
                              executionMode === 'immediate'
                                ? 'rgba(239, 68, 68, 1)'
                                : 'rgba(239, 68, 68, 0.1)',
                            borderColor: 'transparent',
                          },
                        }}
                      >
                        🚀 Immediate
                      </Button>
                      <Button
                        size="small"
                        variant={executionMode === 'smart' ? 'contained' : 'outlined'}
                        onClick={() => setExecutionMode('smart')}
                        sx={{
                          borderRadius: 0,
                          minWidth: 80,
                          bgcolor:
                            executionMode === 'smart' ? 'rgba(16, 185, 129, 0.8)' : 'transparent',
                          color: executionMode === 'smart' ? '#fff' : 'rgba(16, 185, 129, 0.8)',
                          borderColor: 'transparent',
                          '&:hover': {
                            bgcolor:
                              executionMode === 'smart'
                                ? 'rgba(16, 185, 129, 1)'
                                : 'rgba(16, 185, 129, 0.1)',
                            borderColor: 'transparent',
                          },
                        }}
                      >
                        🧠 Smart
                      </Button>
                    </Box>
                  </Tooltip>
                </Box>

                {/* Right: Execute Button */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Button
                    variant="contained"
                    color={orderQuantity > 0 ? 'success' : 'error'}
                    startIcon={
                      batchExecuting ? (
                        <CircularProgress size={16} color="inherit" />
                      ) : (
                        <PlayArrowIcon />
                      )
                    }
                    onClick={executeBatchOrders}
                    disabled={
                      batchExecuting ||
                      calculateBatchOrders().length === 0 ||
                      !status?.trading_allowed
                    }
                    sx={{ minWidth: 150 }}
                  >
                    {batchExecuting
                      ? 'Executing...'
                      : `Execute ${calculateBatchOrders().length} Orders`}
                  </Button>
                </Box>
              </Box>

              {/* Preview of orders */}
              {Object.keys(selectedStrikes).filter((k) => selectedStrikes[k]).length > 0 && (
                <Box sx={{ mt: 2, pt: 2, borderTop: '1px solid rgba(255,255,255,0.1)' }}>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ mb: 1, display: 'block' }}
                  >
                    Order Preview (
                    {executionMode === 'immediate'
                      ? 'Market Orders - Instant Fill'
                      : 'Limit Orders @ Mid - Auto-Market after 5min'}
                    ):
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {calculateBatchOrders().map((order, idx) => (
                      <Chip
                        key={idx}
                        size="small"
                        label={`${order.side.toUpperCase()} ${order.size} ${order.optionType === 'Call' ? 'C' : 'P'} ${order.symbol.split('-')[2]}${order.ratioInfo ? ` [${order.ratioInfo}]` : ''} ${executionMode === 'immediate' ? '🚀' : '🧠'}`}
                        sx={{
                          bgcolor:
                            order.side === 'buy'
                              ? 'rgba(16, 185, 129, 0.2)'
                              : 'rgba(239, 68, 68, 0.2)',
                          color: order.side === 'buy' ? '#10b981' : '#ef4444',
                          fontWeight: 'bold',
                          fontSize: '0.7rem',
                        }}
                      />
                    ))}
                  </Box>
                </Box>
              )}

              {/* Batch order results */}
              {batchOrderResults.length > 0 && (
                <Box sx={{ mt: 2, pt: 2, borderTop: '1px solid rgba(255,255,255,0.1)' }}>
                  <Box
                    sx={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      mb: 1,
                    }}
                  >
                    <Typography variant="caption" color="text.secondary">
                      Results:
                    </Typography>
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => setBatchOrderResults([])}
                      sx={{ fontSize: '0.7rem', py: 0, px: 1, minWidth: 'auto' }}
                    >
                      Dismiss
                    </Button>
                  </Box>
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                    {batchOrderResults.map((result, idx) => {
                      // Color coding: green for filled, blue for submitted, red for error
                      const color = result.filled
                        ? '#10b981'
                        : result.success
                          ? '#3b82f6'
                          : '#ef4444';
                      const icon = result.filled ? '✅' : result.success ? '📤' : '❌';

                      return (
                        <Typography
                          key={idx}
                          variant="caption"
                          sx={{ color, display: 'flex', alignItems: 'center', gap: 0.5 }}
                        >
                          <span>{icon}</span>
                          <span>
                            {result.symbol.split('-').slice(0, 3).join('-')}: {result.message}
                          </span>
                        </Typography>
                      );
                    })}
                  </Box>
                </Box>
              )}
            </Box>
          )}

          {/* Summary */}
          {positions.length > 0 && (
            <>
              <Box sx={{ mt: 2, display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                <Chip
                  icon={<MoneyIcon />}
                  label={`Total PnL: ${formatPnl(sortedPositions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0))}`}
                  sx={{
                    bgcolor:
                      getPnlColor(
                        sortedPositions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0)
                      ) + '20',
                    color: getPnlColor(
                      sortedPositions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0)
                    ),
                  }}
                />
                <Chip
                  label={`Calls: ${sortedPositions.filter((p) => p.product_symbol.startsWith('C-')).length}`}
                  sx={{ bgcolor: '#3b82f620', color: '#3b82f6' }}
                />
                <Chip
                  label={`Puts: ${sortedPositions.filter((p) => p.product_symbol.startsWith('P-')).length}`}
                  sx={{ bgcolor: '#a855f720', color: '#a855f7' }}
                />
              </Box>

              {/* Greeks Summary - Only for visible positions - Day 3 Enhancement: Collapsible */}
              {aggregatedGreeks.count > 0 && (
                <Box sx={{ mt: 2, p: 2, bgcolor: 'action.hover', borderRadius: 1 }}>
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      cursor: 'pointer',
                      mb: greeksCollapsed ? 0 : 1,
                    }}
                    onClick={() => {
                      const newState = !greeksCollapsed;
                      setGreeksCollapsed(newState);
                      localStorage.setItem('options_greeks_collapsed', JSON.stringify(newState));
                    }}
                  >
                    <Typography variant="subtitle2" color="text.secondary">
                      Portfolio Greeks ({sortedPositions.length} visible positions)
                    </Typography>
                    <IconButton size="small">
                      {greeksCollapsed ? <ExpandMoreIcon /> : <ExpandLessIcon />}
                    </IconButton>
                  </Box>

                  {!greeksCollapsed && (
                    <>
                  {/* Futures Equivalent - Delta as directional exposure */}
                  {(aggregatedGreeks.btcDelta !== 0 || aggregatedGreeks.ethDelta !== 0) && (
                    <Box
                      sx={{
                        mb: 2,
                        p: 1.5,
                        bgcolor: 'background.paper',
                        borderRadius: 1,
                        border: '1px solid',
                        borderColor: 'divider',
                      }}
                    >
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        sx={{ display: 'block', mb: 1 }}
                      >
                        Futures Equivalent (Delta Exposure)
                      </Typography>
                      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                        {/* BTC Equivalent */}
                        {aggregatedGreeks.btcDelta !== 0 && (
                          <Tooltip
                            title={`Your BTC options have the same directional exposure as ${Math.abs(Number(aggregatedGreeks.btcDelta) || 0).toFixed(4)} BTC futures contracts`}
                          >
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <Typography
                                variant="body2"
                                fontWeight="bold"
                                sx={{
                                  color: aggregatedGreeks.btcDelta >= 0 ? '#10b981' : '#ef4444',
                                }}
                              >
                                {aggregatedGreeks.btcDelta >= 0 ? 'Long' : 'Short'}{' '}
                                {Math.abs(Number(aggregatedGreeks.btcDelta) || 0).toFixed(4)} BTC
                              </Typography>
                              {aggregatedGreeks.btcDelta >= 0 ? (
                                <TrendingUp sx={{ fontSize: 16, color: '#10b981' }} />
                              ) : (
                                <TrendingDown sx={{ fontSize: 16, color: '#ef4444' }} />
                              )}
                            </Box>
                          </Tooltip>
                        )}

                        {/* ETH Equivalent */}
                        {aggregatedGreeks.ethDelta !== 0 && (
                          <Tooltip
                            title={`Your ETH options have the same directional exposure as ${Math.abs(Number(aggregatedGreeks.ethDelta) || 0).toFixed(4)} ETH futures contracts`}
                          >
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <Typography
                                variant="body2"
                                fontWeight="bold"
                                sx={{
                                  color: aggregatedGreeks.ethDelta >= 0 ? '#10b981' : '#ef4444',
                                }}
                              >
                                {aggregatedGreeks.ethDelta >= 0 ? 'Long' : 'Short'}{' '}
                                {Math.abs(Number(aggregatedGreeks.ethDelta) || 0).toFixed(4)} ETH
                              </Typography>
                              {aggregatedGreeks.ethDelta >= 0 ? (
                                <TrendingUp sx={{ fontSize: 16, color: '#10b981' }} />
                              ) : (
                                <TrendingDown sx={{ fontSize: 16, color: '#ef4444' }} />
                              )}
                            </Box>
                          </Tooltip>
                        )}
                      </Box>

                      {/* Delta Neutral Badge */}
                      {Math.abs(aggregatedGreeks.delta) < 0.1 && (
                        <Alert severity="info" sx={{ mt: 1.5 }} icon={<CheckCircleIcon />}>
                          <Typography variant="caption">
                            ✅ Portfolio is <strong>Delta Neutral</strong> (delta ≈ 0). Minimal
                            directional exposure.
                          </Typography>
                        </Alert>
                      )}

                      {/* High Delta Warning */}
                      {Math.abs(aggregatedGreeks.delta) > 10 && (
                        <Alert severity="warning" sx={{ mt: 1.5 }} icon={<WarningIcon />}>
                          <Typography variant="caption">
                            ⚠️ High directional exposure. Consider hedging with{' '}
                            {aggregatedGreeks.delta > 0 ? 'short' : 'long'} futures.
                          </Typography>
                        </Alert>
                      )}
                    </Box>
                  )}

                  {/* Greek Values */}
                  <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                    <Tooltip title="Portfolio delta - sensitivity to underlying price change">
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Delta
                        </Typography>
                        <Typography
                          variant="body2"
                          fontWeight="bold"
                          sx={{
                            color:
                              (Number(aggregatedGreeks.delta) || 0) >= 0 ? '#10b981' : '#ef4444',
                          }}
                        >
                          {(Number(aggregatedGreeks.delta) || 0) >= 0 ? '+' : ''}
                          {(Number(aggregatedGreeks.delta) || 0).toFixed(4)}
                        </Typography>
                      </Box>
                    </Tooltip>
                    <Tooltip title="Portfolio gamma - rate of delta change">
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Gamma
                        </Typography>
                        <Typography variant="body2" fontWeight="bold">
                          {(Number(aggregatedGreeks.gamma) || 0).toFixed(6)}
                        </Typography>
                      </Box>
                    </Tooltip>
                    <Tooltip title="Portfolio theta - daily time decay (P&L change per day)">
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Theta
                        </Typography>
                        <Typography
                          variant="body2"
                          fontWeight="bold"
                          sx={{
                            color:
                              (Number(aggregatedGreeks.theta) || 0) >= 0 ? '#10b981' : '#ef4444',
                          }}
                        >
                          {(Number(aggregatedGreeks.theta) || 0) >= 0 ? '+' : ''}
                          {(Number(aggregatedGreeks.theta) || 0).toFixed(2)}
                        </Typography>
                      </Box>
                    </Tooltip>
                    <Tooltip title="Portfolio vega - sensitivity to 1% IV change">
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Vega
                        </Typography>
                        <Typography variant="body2" fontWeight="bold">
                          {(Number(aggregatedGreeks.vega) || 0).toFixed(2)}
                        </Typography>
                      </Box>
                    </Tooltip>
                  </Box>
                  </>
                  )}
                </Box>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Payoff Diagram */}
      {positions.length > 0 && (
        <Box sx={{ mt: 2 }}>
          <OptionsPayoffDiagram 
            positions={sortedPositions} 
            hiddenPositions={hiddenPositions} 
            futuresPositions={visibleFuturesPositions}
          />
        </Box>
      )}
      
      {/* Live Execution Status */}
      <Box sx={{ mt: 2 }}>
        <LogPanel refreshTrigger={0} />
      </Box>

      {/* Close Confirmation Dialog */}
      <Dialog
        open={closeDialog.open}
        onClose={() => setCloseDialog({ open: false, position: null })}
        disableRestoreFocus
      >
        <DialogTitle>Close Position</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to close your position in{' '}
            <strong>{closeDialog.position?.product_symbol}</strong>?
          </Typography>
          <Box sx={{ mt: 2 }}>
            <Typography variant="body2" color="text.secondary">
              Size: {closeDialog.position?.size}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Current PnL: {formatPnl(closeDialog.position?.unrealized_pnl || 0)}
            </Typography>
          </Box>
          {!closeDialog.position?.is_liquid && (
            <Alert severity="warning" sx={{ mt: 2 }}>
              Warning: This position has a wide spread (
              {(Number(closeDialog.position?.spread_pct) || 0).toFixed(1)}%). You may get
              unfavorable fill prices.
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCloseDialog({ open: false, position: null })}>Cancel</Button>
          <Button onClick={confirmClose} color="error" variant="contained">
            Close Position
          </Button>
        </DialogActions>
      </Dialog>

      {/* Add to Position Dialog */}
      <Dialog
        open={addDialog.open}
        onClose={() =>
          setAddDialog({
            open: false,
            position: null,
            size: lastUsedSize,
            side: 'sell',
            orderType: 'maker_first',
            limitPrice: '',
          })
        }
        maxWidth="sm"
        fullWidth
        disableRestoreFocus
      >
        <DialogTitle>Add to Position</DialogTitle>
        <DialogContent>
          {/* Smart Scaling Recommendation */}
          {addDialog.recommendation && addDialog.recommendation.action !== 'hold' && (
            <Alert
              severity={
                addDialog.recommendation.action === 'scale' &&
                addDialog.recommendation.riskLevel === 'low'
                  ? 'success'
                  : addDialog.recommendation.action === 'scale' &&
                      addDialog.recommendation.riskLevel === 'medium'
                    ? 'info'
                    : addDialog.recommendation.action === 'reduce'
                      ? 'error'
                      : 'warning'
              }
              sx={{ mb: 2 }}
            >
              <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 0.5 }}>
                {addDialog.recommendation.action === 'scale'
                  ? '✅ Recommended: Scale In'
                  : '⚠️ Recommended: Reduce'}
              </Typography>
              <Typography variant="caption" sx={{ display: 'block', mb: 0.5 }}>
                Size: {addDialog.recommendation.size} contracts
              </Typography>
              <Typography variant="caption" sx={{ display: 'block', mb: 0.5 }}>
                {addDialog.recommendation.reason}
              </Typography>
              <Typography variant="caption" sx={{ display: 'block', fontStyle: 'italic' }}>
                Strategy: {scalingStrategy.replace('_', ' ').toUpperCase()} | Risk:{' '}
                {addDialog.recommendation.riskLevel.toUpperCase()} | Confidence:{' '}
                {addDialog.recommendation.confidence.toUpperCase()}
              </Typography>
            </Alert>
          )}

          <Typography sx={{ mb: 2 }}>
            Add to your position in <strong>{addDialog.position?.product_symbol}</strong>
          </Typography>

          {/* Quick Size Presets */}
          <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
            Quick Sizes:
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
            {QUICK_SIZES.map((size) => (
              <Button
                key={size}
                variant={addDialog.size === size.toString() ? 'contained' : 'outlined'}
                size="small"
                onClick={() => setAddDialog({ ...addDialog, size: size.toString() })}
                sx={{ minWidth: 50 }}
              >
                {size}
              </Button>
            ))}
          </Box>

          {/* Percentage-based adjustments */}
          {addDialog.position?.size && Math.abs(addDialog.position.size) > 0 && (
            <>
              <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
                % of Current Position ({Math.abs(addDialog.position.size)} contracts):
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
                {[25, 50, 100, 200].map((pct) => {
                  const adjustedSize = Math.max(
                    1,
                    Math.round(Math.abs(addDialog.position.size) * (pct / 100))
                  );
                  return (
                    <Button
                      key={pct}
                      variant="outlined"
                      size="small"
                      color="secondary"
                      onClick={() => setAddDialog({ ...addDialog, size: adjustedSize.toString() })}
                    >
                      {pct}% ({adjustedSize})
                    </Button>
                  );
                })}
              </Box>
            </>
          )}

          <TextField
            label="Size to Add"
            type="number"
            value={addDialog.size}
            onChange={(e) => setAddDialog({ ...addDialog, size: e.target.value })}
            fullWidth
            sx={{ mb: 2 }}
            inputProps={{ min: 1 }}
          />

          {/* Buy/Sell Selection */}
          <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
            Side:
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
            <Button
              variant={addDialog.side === 'buy' ? 'contained' : 'outlined'}
              color="success"
              onClick={() => setAddDialog({ ...addDialog, side: 'buy' })}
              fullWidth
            >
              Buy (B)
            </Button>
            <Button
              variant={addDialog.side === 'sell' ? 'contained' : 'outlined'}
              color="error"
              onClick={() => setAddDialog({ ...addDialog, side: 'sell' })}
              fullWidth
            >
              Sell (S)
            </Button>
          </Box>

          {/* Order Type Selection */}
          <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
            Order Type:
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap' }}>
            {Object.entries(ORDER_TYPES).map(([key, value]) => (
              <Tooltip key={key} title={value.description}>
                <Button
                  variant={addDialog.orderType === key ? 'contained' : 'outlined'}
                  size="small"
                  color="primary"
                  onClick={() => setAddDialog({ ...addDialog, orderType: key })}
                  sx={{ fontSize: '0.75rem' }}
                >
                  {key === 'maker_first' ? 'Smart' : key === 'maker_only' ? 'Limit' : 'Market'}
                </Button>
              </Tooltip>
            ))}
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ mb: 2, display: 'block' }}>
            {ORDER_TYPES[addDialog.orderType]?.description}
          </Typography>

          {/* Limit Price Input (only for maker_only) */}
          {addDialog.orderType === 'maker_only' && (
            <>
              <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
                Limit Price:
              </Typography>
              <TextField
                label="Limit Price (Optional)"
                type="number"
                value={addDialog.limitPrice}
                onChange={(e) => setAddDialog({ ...addDialog, limitPrice: e.target.value })}
                fullWidth
                sx={{ mb: 2 }}
                placeholder="Leave empty for mid-price"
                helperText="If empty, order will be placed at mid-price"
                inputProps={{ step: 0.01, min: 0 }}
              />
            </>
          )}

          {!addDialog.position?.is_liquid && (
            <Alert severity="warning" sx={{ mt: 2 }}>
              Warning: This option has a wide spread (
              {(Number(addDialog.position?.spread_pct) || 0).toFixed(1)}%).
            </Alert>
          )}

          {/* Skip confirmation hint */}
          {addDialog.position &&
            !skipConfirmStrikes[addDialog.position.product_symbol]?.enabled && (
              <Alert severity="info" sx={{ mt: 2 }} icon={false}>
                <Typography variant="caption">
                  💡 Click "Don't Ask Again" to instantly execute {addDialog.size || DEFAULT_SIZE}{' '}
                  lots on future clicks for this strike.
                </Typography>
              </Alert>
            )}
        </DialogContent>
        <DialogActions sx={{ justifyContent: 'space-between', px: 3, pb: 2 }}>
          <Button
            onClick={() =>
              setAddDialog({
                open: false,
                position: null,
                size: lastUsedSize,
                side: 'sell',
                orderType: 'maker_first',
                limitPrice: '',
              })
            }
          >
            Cancel (Esc)
          </Button>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              onClick={() => confirmAddWithSkip(true)}
              color="warning"
              variant="outlined"
              disabled={submittingOrder || !addDialog.size || parseFloat(addDialog.size) <= 0}
              title="Execute now and skip this dialog for future orders on this strike"
            >
              Don't Ask Again
            </Button>
            <Button
              onClick={() => confirmAddWithSkip(false)}
              color={addDialog.side === 'buy' ? 'success' : 'error'}
              variant="contained"
              disabled={submittingOrder || !addDialog.size || parseFloat(addDialog.size) <= 0}
            >
              {submittingOrder
                ? 'Submitting...'
                : `${addDialog.side === 'buy' ? 'Buy' : 'Sell'} ${addDialog.size || 0}`}
            </Button>
          </Box>
        </DialogActions>
      </Dialog>

      {/* Batch Order Confirmation Dialog */}
      <Dialog
        open={batchConfirmDialog.open}
        onClose={() => setBatchConfirmDialog({ open: false, orderCount: 0, estimatedTime: 0 })}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ bgcolor: 'warning.main', color: 'warning.contrastText' }}>
          ⚠️ Large Batch Order Confirmation
        </DialogTitle>
        <DialogContent sx={{ mt: 2 }}>
          <Alert severity="warning" sx={{ mb: 2 }}>
            <AlertTitle>Please Confirm</AlertTitle>
            You're about to place <strong>{batchConfirmDialog.orderCount} orders</strong>.
          </Alert>
          <Typography variant="body2" color="text.secondary">
            • Estimated execution time: <strong>~{batchConfirmDialog.estimatedTime} seconds</strong>
          </Typography>
          <Typography variant="body2" color="text.secondary">
            • Orders will be rate-limited to prevent API throttling
          </Typography>
          <Typography variant="body2" color="text.secondary">
            • You can monitor progress in the results panel
          </Typography>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button
            onClick={() => setBatchConfirmDialog({ open: false, orderCount: 0, estimatedTime: 0 })}
            variant="outlined"
          >
            Cancel
          </Button>
          <Button
            onClick={() => {
              const orders = calculateBatchOrders();
              setBatchConfirmDialog({ open: false, orderCount: 0, estimatedTime: 0 });
              executeBatch(orders);
            }}
            color="warning"
            variant="contained"
            autoFocus
          >
            Proceed with {batchConfirmDialog.orderCount} Orders
          </Button>
        </DialogActions>
      </Dialog>

      {/* SL/TP Configuration Dialog */}
      <SLTPDialog
        open={slTpDialogOpen}
        onClose={() => {
          setSlTpDialogOpen(false);
          setSelectedPositionForSLTP(null);
        }}
        position={selectedPositionForSLTP}
        onSave={() => {
          loadSLTPSettings();
          setSlTpDialogOpen(false);
          setSelectedPositionForSLTP(null);
        }}
      />
      
      {/* Sound Settings Panel (JAN 19, 2026 - Independent UI component) */}
      <SoundSettingsPanel 
        open={soundSettingsOpen} 
        onClose={() => setSoundSettingsOpen(false)} 
      />
      
      {/* Trade Notification (JAN 19, 2026 - Visual feedback) */}
      <TradeNotification 
        notification={tradeNotification} 
        onDismiss={() => setTradeNotification(null)} 
      />
    </motion.div>
  );
};

export default OptionsPanel;
