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

import React, { useState, useEffect, useCallback, useMemo, useRef, lazy, Suspense } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { io } from 'socket.io-client';
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
  TuneRounded as AdjustIcon,
  HelpOutline as HelpOutlineIcon,
  KeyboardArrowDown as KeyboardArrowDownIcon,
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
import LogPanel from '../optionsChain/LogPanel';
import PendingOrdersPanel from './PendingOrdersPanel';
import ScalingStrategyPanel from './ScalingStrategyPanel';
import PortfolioSummaryStrip from './PortfolioSummaryStrip';
import AddPositionDialog from './AddPositionDialog';
import BatchOrderPanel from './BatchOrderPanel';
import { AutomationButton, automationMonitor, notificationService } from './automation';
import SLTPDialog from './SLTPDialog';
import SLTPIndicator from './SLTPIndicator';
import MaxLossIndicator from './MaxLossIndicator';
import TakeProfitIndicator from './TakeProfitIndicator';
import TakeProfitDialog from './TakeProfitDialog';
import ExpiryMaxLossPanel from './ExpiryMaxLossPanel';
import useMarketPrices from '../../hooks/useMarketPrices';
import SoundSettingsPanel from '../SoundSettingsPanel';
import TradeNotification from '../TradeNotification';
// JAN 17, 2026: Futures panel - separate file structure, minimal invasion
import FuturesPanel from '../futures/FuturesPanel';
// JAN 23, 2026: Day 1 & 2 utilities for PoP calculation
import { calculatePoP } from '../../utils/probabilityCalc';
import { RISK_FREE_RATE, getContractMultiplier } from '../../utils/constants';
// JAN 31, 2026: Position Adjustment Panel - Sensibull-like position adjustment system
// FEB 1, 2026: Updated to use SensibullStyleAdjustmentPage (full page layout)
import { SensibullStyleAdjustmentPage } from '../positionAdjustment';

// Phase 3: Lazy load heavy components
const OptionsPayoffDiagram = lazy(() => import('./OptionsPayoffDiagram'));
const OptionsActivityPanel = lazy(() => import('./OptionsActivityPanel'));

// Phase 5 Optimization: IV cache with 60s TTL to avoid 17+ external API calls per poll
const IV_CACHE_TTL_MS = 60000; // 60 seconds - IV doesn't change meaningfully every second
const _ivCache = { data: {}, timestamp: 0 };

// ============================================================================
// PHASE 1 OPTIMIZATION: React.memo for SortableRow
// Prevents unnecessary re-renders when position data hasn't changed
// ============================================================================

// Sortable Row Component - Simple memo without custom comparison
// Removed overly strict comparison that was blocking TP/SL settings updates
const SortableRow = React.memo(({ pos, children }) => {
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
});

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
  // Phase 2: Secondary toolbar visibility (persisted)
  const [secondaryToolbarOpen, setSecondaryToolbarOpen] = useState(() => {
    try {
      const saved = localStorage.getItem('options_secondary_toolbar_open');
      return saved ? JSON.parse(saved) : false;
    } catch {
      return false;
    }
  });
  // Phase 2: Scaling strategy section collapsed (persisted)
  const [scalingStrategyCollapsed, setScalingStrategyCollapsed] = useState(() => {
    try {
      const saved = localStorage.getItem('options_scaling_strategy_collapsed');
      return saved ? JSON.parse(saved) : true; // default: collapsed
    } catch {
      return true;
    }
  });
  // Phase 2: Expiry max loss section collapsed (persisted)
  const [expiryMaxLossCollapsed, setExpiryMaxLossCollapsed] = useState(() => {
    try {
      const saved = localStorage.getItem('options_expiry_maxloss_collapsed');
      return saved ? JSON.parse(saved) : true; // default: collapsed
    } catch {
      return true;
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
  // Selected positions for payoff diagram (whitelist approach - default: none selected)
  const [selectedPositionsForPayoff, setSelectedPositionsForPayoff] = useState(() => {
    try {
      const saved = localStorage.getItem('options_selected_positions_payoff');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  // Closed positions storage - keeps squared off positions visible with size=0 and their final PnL
  // Format: { symbol: { product_symbol, realized_pnl, closed_at, entry_price, close_price, original_size } }
  const [closedPositions, setClosedPositions] = useState(() => {
    try {
      const saved = localStorage.getItem('options_closed_positions');
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });

  // Day 1: Probability of Profit (PoP) data
  const [popData, setPopData] = useState({}); // Map of symbol -> PoP percentage

  // ============================================================================
  // PHASE 1 OPTIMIZATION: Debounced localStorage writes
  // Prevents UI blocking from synchronous localStorage operations
  // MUST BE DEFINED BEFORE useEffect hooks that reference it
  // ============================================================================
  
  // Debounced localStorage saver (500ms delay)
  const debouncedSave = useMemo(
    () => {
      const saveToStorage = (key, value) => {
        try {
          if (value === null || value === undefined) {
            localStorage.removeItem(key);
          } else if (typeof value === 'object') {
            localStorage.setItem(key, JSON.stringify(value));
          } else {
            localStorage.setItem(key, String(value));
          }
        } catch (err) {
          console.warn(`Failed to save ${key} to localStorage:`, err);
        }
      };
      
      // Create debounced function with 500ms delay
      let timeouts = {};
      return (key, value, immediate = false) => {
        if (immediate) {
          saveToStorage(key, value);
          return;
        }
        
        clearTimeout(timeouts[key]);
        timeouts[key] = setTimeout(() => {
          saveToStorage(key, value);
        }, 500);
      };
    },
    []
  );

  // Save hiddenPositions to localStorage whenever it changes (debounced)
  useEffect(() => {
    debouncedSave('options_hidden_positions', hiddenPositions);
  }, [hiddenPositions, debouncedSave]);
  
  // Save closedPositions to localStorage whenever it changes (debounced)
  useEffect(() => {
    debouncedSave('options_closed_positions', closedPositions);
  }, [closedPositions, debouncedSave]);
  // Polling interval (default 5s)
  const [pollInterval, setPollInterval] = useState(() => {
    try {
      const saved = localStorage.getItem('options_poll_interval');
      return saved ? parseInt(saved) : 5000;
    } catch {
      return 5000;
    }
  });

  // Phase 4: Turbo Mode for expiry day ultra-fast trading
  const [turboMode, setTurboMode] = useState(() => {
    try {
      const saved = localStorage.getItem('options_turbo_mode');
      return saved === 'true';
    } catch {
      return false;
    }
  });

  // Phase 4: Keyboard trading - selected row index (-1 = no selection until arrow keys used)
  const [selectedRowIndex, setSelectedRowIndex] = useState(-1);

  // Expiry filter (persisted) - now supports multiple selection
  const [selectedExpiries, setSelectedExpiries] = useState(() => {
    try {
      const saved = localStorage.getItem('options_selected_expiries');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  // Sort state
  const [symbolSort, setSymbolSort] = useState(null); // null = no sort, 'grouped' = CE/PE grouped
  const [strikeSort, setStrikeSort] = useState(null); // null = no sort, 'asc' = ascending, 'desc' = descending
  const [sizeSort, setSizeSort] = useState(null); // null = no sort, 'asc' = ascending, 'desc' = descending

  // SL/TP Dialog state
  const [slTpDialogOpen, setSlTpDialogOpen] = useState(false);
  const [selectedPositionForSLTP, setSelectedPositionForSLTP] = useState(null);
  const [slTpSettings, setSlTpSettings] = useState({}); // Map of symbol -> settings

  // Max Loss Settings state (per-strike and per-expiry)
  const [maxLossSettings, setMaxLossSettings] = useState({}); // Map of symbol -> settings
  const [expiryMaxLossSettings, setExpiryMaxLossSettings] = useState({}); // Map of expiry_code -> settings

  // Take Profit Dialog state
  const [tpDialogOpen, setTpDialogOpen] = useState(false);
  const [selectedPositionForTP, setSelectedPositionForTP] = useState(null);
  const [tpSettings, setTpSettings] = useState({}); // Map of symbol -> TP settings

  // Column visibility state (persisted)
  const [columnMenuAnchor, setColumnMenuAnchor] = useState(null);
  const [visibleColumns, setVisibleColumns] = useState(() => {
    try {
      const saved = localStorage.getItem('options_visible_columns');
      const parsed = saved ? JSON.parse(saved) : null;

      // Default columns with PoP
      const defaults = {
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
        takeProfit: true,
        iv: true,
        pop: true,  // Day 1 & 2: Always show PoP by default
        pnl: true,
        actions: true,
      };

      // Merge saved with defaults (ensures new columns appear for existing users)
      return parsed ? { ...defaults, ...parsed } : defaults;
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
        pop: true,
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
    { key: 'takeProfit', label: 'TP' },
    { key: 'iv', label: 'IV' },
    { key: 'pop', label: 'PoP' },
    { key: 'pnl', label: 'PnL' },
    { key: 'actions', label: 'Actions' },
  ];

  // Toggle column visibility - debounced save
  const toggleColumn = (columnKey) => {
    setVisibleColumns((prev) => {
      const updated = { ...prev, [columnKey]: !prev[columnKey] };
      debouncedSave('options_visible_columns', updated);
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
      const order = saved ? JSON.parse(saved) : [];
      if (order.length > 0) {
        console.log('[OptionsPanel] Loaded custom order from localStorage:', order);
      }
      return order;
    } catch (error) {
      console.error('[OptionsPanel] Failed to load custom order:', error);
      return [];
    }
  });

  // Batch order state - strike selection and order quantity
  const [selectedStrikes, setSelectedStrikes] = useState({}); // { symbol: true/false }
  const [orderQuantity, setOrderQuantity] = useState(1); // Simple multiplier based on current position lots
  const [multiplierMode, setMultiplierMode] = useState('normal'); // 'normal' or 'gcd' - Toggle between normal multiplier and GCD-based
  const [executionMode, setExecutionMode] = useState('smart'); // 'immediate' or 'smart'
  const [batchQuantities, setBatchQuantities] = useState({}); // { symbol: number } - Manual quantity input per strike
  const [batchOrderResults, setBatchOrderResults] = useState([]);

  // Auto-loop execution state - with localStorage persistence
  // Now supports per-expiry loops
  const [autoLoopEnabled, setAutoLoopEnabled] = useState(() => {
    try {
      const saved = localStorage.getItem('autoLoopEnabled');
      return saved ? JSON.parse(saved) : false;
    } catch { return false; }
  });
  const [autoLoopRounds, setAutoLoopRounds] = useState(() => {
    try {
      const saved = localStorage.getItem('autoLoopRounds');
      return saved ? parseInt(saved, 10) : 10;
    } catch { return 10; }
  });
  // Per-expiry loop state: { [expiryCode]: { running, currentRound, progress, error, stopRef } }
  // Persisted to localStorage for recovery across page refreshes
  const [expiryLoopState, setExpiryLoopState] = useState(() => {
    try {
      const saved = localStorage.getItem('expiryLoopState');
      if (saved) {
        const parsed = JSON.parse(saved);
        // On load, mark any "running" loops as interrupted (since they couldn't have survived the refresh)
        const restored = {};
        for (const [expiry, state] of Object.entries(parsed)) {
          if (state.running) {
            // Loop was running when page was refreshed - mark as interrupted
            restored[expiry] = {
              ...state,
              running: false,
              error: `⚠️ Loop interrupted at round ${state.currentRound}/${state.totalRounds}. Page was refreshed.`,
              interrupted: true,
              interruptedAt: Date.now(),
            };
          } else {
            // Preserve completed/errored states for user reference
            restored[expiry] = state;
          }
        }
        return restored;
      }
      return {};
    } catch { return {}; }
  });
  // Legacy single-loop state (kept for backward compatibility)
  const [autoLoopRunning, setAutoLoopRunning] = useState(false);
  const [autoLoopCurrentRound, setAutoLoopCurrentRound] = useState(0);
  const [autoLoopProgress, setAutoLoopProgress] = useState({}); // { symbol: { filled: bool, orderId: string } }
  const [autoLoopError, setAutoLoopError] = useState(null);
  const [autoLoopLastRun, setAutoLoopLastRun] = useState(() => {
    try {
      const saved = localStorage.getItem('autoLoopLastRun');
      return saved ? JSON.parse(saved) : null;
    } catch { return null; }
  }); // Stores last run info for recovery
  const autoLoopStopRef = useRef(false); // Flag to stop the loop
  // Per-expiry stop refs (managed as regular object, updated via expiryLoopState)
  const expiryStopRefs = useRef({});
  // Phase 2: Persistent WebSocket connection ref
  const socketRef = useRef(null);
  // Phase 3: Change detection - track last modified timestamp
  const lastModifiedRef = useRef(null);

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

  // Position Adjustment Panel state (JAN 31, 2026 - Sensibull-like adjustment workflow)
  const [adjustmentPanelOpen, setAdjustmentPanelOpen] = useState(false);

  // Trade notification state (JAN 19, 2026 - Visual feedback)
  const [tradeNotification, setTradeNotification] = useState(null);
  const [orderResult, setOrderResult] = useState(null);
  const [submittingOrder, setSubmittingOrder] = useState(false); // Prevent double submission

  // Quick size default (last used)
  const DEFAULT_SIZE = lastUsedSize;

  // SSR mode mapping for backend
  const SSR_MODE_MAP = {
    ssr_standard: 'standard',
    ssr_aggressive: 'aggressive',
    ssr_conservative: 'conservative',
  };

  // Helper function to check if an order execution type means the order was actually filled
  // This is critical: we only show trade confirmation visuals when orders are EXECUTED, not just PLACED
  const isOrderFilled = (executionType) => {
    const filledTypes = [
      'market',                    // Market order (immediately filled)
      'market_fallback_no_quotes', // Market order when no quotes (immediately filled)
      'market_fallback',           // Market order after limit order cancelled (filled)
      'market_fallback_error',     // Market order as error fallback (filled)
      'limit_filled',              // Limit order filled
      'limit_filled_late',         // Limit order filled during cancellation attempt
    ];
    return filledTypes.includes(executionType);
  };

  // Save skipConfirmStrikes to localStorage whenever it changes (debounced)
  useEffect(() => {
    debouncedSave('options_skip_confirm_strikes', skipConfirmStrikes);
  }, [skipConfirmStrikes, debouncedSave]);
  
  // Save selected positions to localStorage whenever it changes (debounced)
  useEffect(() => {
    debouncedSave('options_selected_positions_payoff', selectedPositionsForPayoff);
  }, [selectedPositionsForPayoff, debouncedSave]);
  
  // Save pollInterval to localStorage whenever it changes (debounced)
  useEffect(() => {
    debouncedSave('options_poll_interval', pollInterval);
  }, [pollInterval, debouncedSave]);

  // Phase 4: Save turbo mode to localStorage
  useEffect(() => {
    debouncedSave('options_turbo_mode', turboMode);
  }, [turboMode, debouncedSave]);
  
  // Save lastUsedSize to localStorage whenever it changes (debounced)
  useEffect(() => {
    debouncedSave('options_last_used_size', lastUsedSize);
  }, [lastUsedSize, debouncedSave]);

  // Save customOrder to localStorage whenever it changes (debounced)
  useEffect(() => {
    debouncedSave('options_custom_order', customOrder);
  }, [customOrder, debouncedSave]);

  // Save auto-loop settings to localStorage (debounced)
  useEffect(() => {
    debouncedSave('autoLoopEnabled', autoLoopEnabled);
  }, [autoLoopEnabled, debouncedSave]);
  
  useEffect(() => {
    debouncedSave('autoLoopRounds', autoLoopRounds);
  }, [autoLoopRounds, debouncedSave]);

  // Save per-expiry loop state to localStorage for recovery (debounced)
  useEffect(() => {
    if (Object.keys(expiryLoopState).length > 0) {
      debouncedSave('expiryLoopState', expiryLoopState);
    }
  }, [expiryLoopState, debouncedSave]);

  // Save auto-loop run state for recovery (immediate - critical for recovery)
  useEffect(() => {
    if (autoLoopLastRun) {
      debouncedSave('autoLoopLastRun', autoLoopLastRun, true); // immediate
    } else {
      debouncedSave('autoLoopLastRun', null, true); // immediate
    }
  }, [autoLoopLastRun, debouncedSave]);

  // Check for interrupted auto-loop on mount
  useEffect(() => {
    const savedLastRun = localStorage.getItem('autoLoopLastRun');
    if (savedLastRun) {
      try {
        const lastRun = JSON.parse(savedLastRun);
        // If the last run didn't complete (has currentRound but not completed)
        if (lastRun && lastRun.currentRound < lastRun.totalRounds && !lastRun.completed) {
          const timeSince = Date.now() - lastRun.startTime;
          const minsSince = Math.floor(timeSince / 60000);
          console.log(`[AUTO-LOOP] Found interrupted run from ${minsSince}m ago: Round ${lastRun.currentRound}/${lastRun.totalRounds}`);
          setAutoLoopError(`⚠️ Previous run interrupted at round ${lastRun.currentRound}/${lastRun.totalRounds} (${minsSince}m ago). Check your orders!`);
        }
      } catch (e) {
        console.warn('[AUTO-LOOP] Could not parse saved run state:', e);
      }
    }
  }, []);

  // Handle drag end - save the custom order to persist across page refreshes (immediate save for UX)
  const handleDragEnd = (event) => {
    const { active, over } = event;

    if (active.id !== over.id) {
      const oldIndex = sortedPositions.findIndex((p) => p.product_symbol === active.id);
      const newIndex = sortedPositions.findIndex((p) => p.product_symbol === over.id);

      const reordered = arrayMove(sortedPositions, oldIndex, newIndex);
      const newOrder = reordered.map((p) => p.product_symbol);
      
      // Update state and save immediately (drag operations need instant persistence)
      setCustomOrder(newOrder);
      debouncedSave('options_custom_order', newOrder, true); // immediate save
      
      // Log for debugging
      console.log('[OptionsPanel] Position order updated:', newOrder);
    }
  };

  // Reset custom order (immediate save)
  const resetOrder = () => {
    setCustomOrder([]);
    debouncedSave('options_custom_order', null, true); // immediate save
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

  // Toggle size sort (ascending/descending)
  const toggleSizeSort = () => {
    setSizeSort((prev) => {
      if (prev === null) return 'asc';
      if (prev === 'asc') return 'desc';
      return null;
    });
    // Clear custom order when applying automatic sort
    if (sizeSort === null) {
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

  // Toggle expiry selection (multi-select) - debounced save
  const toggleExpirySelection = (expiry) => {
    setSelectedExpiries((prev) => {
      const newSelection = prev.includes(expiry)
        ? prev.filter((e) => e !== expiry) // Remove if already selected
        : [...prev, expiry]; // Add if not selected
      debouncedSave('options_selected_expiries', newSelection);
      return newSelection;
    });
  };

  // Clear all expiry selections (show all) - debounced save
  const clearExpirySelection = () => {
    setSelectedExpiries([]);
    debouncedSave('options_selected_expiries', []);
  };

  // Sort positions by custom order or default (days to expiration)
  const sortedPositions = useMemo(() => {
    // Get symbols that exist in live positions
    const liveSymbols = new Set(positions.map(p => p.product_symbol));

    // Remove closed positions that now exist as live positions again (user added back)
    // This is done in a separate effect, but we filter here too for immediacy
    const closedToShow = Object.values(closedPositions).filter(
      cp => !liveSymbols.has(cp.product_symbol)
    );

    // Convert closed positions to position-like objects with size=0
    const closedAsPositions = closedToShow.map(cp => ({
      product_symbol: cp.product_symbol,
      size: 0,
      entry_price: cp.entry_price,
      unrealized_pnl: cp.realized_pnl, // Show realized PnL in the PnL column
      realized_pnl: cp.realized_pnl,
      close_price: cp.close_price,
      closed_at: cp.closed_at,
      original_size: cp.original_size,
      is_closed: true, // Flag to identify closed positions in UI
      greeks: cp.greeks || {},
      // Parse symbol for display
      best_bid: 0,
      best_ask: 0,
    }));

    // Merge live positions with closed positions
    const allPositions = [...positions, ...closedAsPositions];

    // First filter out hidden positions
    let filtered = allPositions.filter((p) => !hiddenPositions.includes(p.product_symbol));

    // Apply expiry filter if any expiries are selected
    if (selectedExpiries.length > 0) {
      filtered = filtered.filter((p) => selectedExpiries.includes(getExpiryCode(p.product_symbol)));
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

    // Apply size sort
    if (sizeSort) {
      sorted = sorted.sort((a, b) => {
        const sizeA = a.size || 0;
        const sizeB = b.size || 0;
        return sizeSort === 'asc' ? sizeA - sizeB : sizeB - sizeA;
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
  }, [positions, closedPositions, hiddenPositions, selectedPositionsForPayoff, customOrder, selectedExpiries, symbolSort, strikeSort, sizeSort]);

  // Live index prices state (fetched from WebSocket, not from positions)
  const { btcPrice, ethPrice } = useMarketPrices();
  const indexPrices = useMemo(
    () => ({
      BTC: btcPrice || 0,
      ETH: ethPrice || 0,
    }),
    [btcPrice, ethPrice]
  );

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

  // ============================================================================
  // PHASE 2 OPTIMIZATION: Unified Dashboard Data Fetching
  // Single API call instead of 4 separate calls
  // ============================================================================
  
  // Unified dashboard fetch (Phase 2 optimization)
  const fetchDashboard = useCallback(async () => {
    try {
      const { data } = await api.get('/api/options/dashboard');
      
      if (data?.success) {
        // Phase 5: Content-hash based change detection - skip ALL state updates if unchanged
        if (data.last_modified && data.last_modified === lastModifiedRef.current) {
          return true; // Data unchanged - skip re-render entirely
        }
        lastModifiedRef.current = data.last_modified;

        // Update all state from single response
        const dashPositions = data.positions || [];
        const dashStatus = data.status || {};
        const dashPendingOrders = data.pending_orders || [];
        const dashFuturesPositions = data.futures_positions || [];

        // Phase 5: IV enrichment now uses 60s cache - instant on cache hit
        const positionsWithIV = await enrichPositionsWithIV(dashPositions);

        setPositions(positionsWithIV);
        setStatus(dashStatus);
        setPendingOrders(dashPendingOrders);
        setFuturesPositions(dashFuturesPositions);

        hasPositionsRef.current = positionsWithIV.length > 0;
        setError(null);

        return true;
      } else {
        throw new Error(data?.error || 'Dashboard fetch failed');
      }
    } catch (err) {
      console.error('Unified dashboard fetch error:', err);
      // Keep existing data on error
      if (hasPositionsRef.current) {
        setError(`⚠️ Dashboard refresh failed: ${err.message}`);
      } else {
        setError(`Connection error: ${err.message}`);
      }
      return false;
    }
  }, []);
  
  // Legacy individual fetch functions (kept for fallback compatibility)
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
      // Fetch both options and MV straddle positions in parallel
      const [optionsResponse, mvStraddleResponse] = await Promise.all([
        api.get('/api/options/positions'),
        api.get('/api/mv-straddle/positions').catch(err => {
          console.warn('MV Straddle positions unavailable:', err.message);
          return { data: { success: false, positions: [] } };
        })
      ]);

      const optionsData = optionsResponse?.data;
      const mvData = mvStraddleResponse?.data;

      if (optionsData?.success) {
        const rawOptionsPositions = optionsData.positions || [];
        const rawMVPositions = mvData?.success ? mvData.positions || [] : [];

        // Merge options and MV straddle positions
        const combinedPositions = [...rawOptionsPositions, ...rawMVPositions];

        // Enrich positions with IV data from Delta Exchange
        const positionsWithIV = await enrichPositionsWithIV(combinedPositions);

        setPositions(positionsWithIV);
        hasPositionsRef.current = positionsWithIV.length > 0;

        // Only clear error if we got fresh (non-cached) data
        if (!optionsData.cached) {
          setError(null);
        } else if (optionsData.warning) {
          // Show warning for cached data
          setError(`⚠️ ${optionsData.warning}`);
        }

        // Log MV positions count if any
        if (rawMVPositions.length > 0) {
          console.log(`📊 Loaded ${rawMVPositions.length} MV Straddle position(s)`);
        }
      } else {
        // Keep existing positions on error, just show warning
        if (hasPositionsRef.current) {
          setError(`⚠️ Refresh failed: ${optionsData?.error || 'Unknown error'}`);
        } else {
          setError(optionsData?.error || 'Failed to fetch positions');
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

  // Clean up closed positions when they reappear as live positions
  // This happens when user adds back to a closed position
  useEffect(() => {
    if (positions.length === 0) return;

    const liveSymbols = new Set(positions.map(p => p.product_symbol));
    const closedSymbols = Object.keys(closedPositions);

    // Find closed positions that now exist as live positions
    const toRemove = closedSymbols.filter(symbol => liveSymbols.has(symbol));

    if (toRemove.length > 0) {
      console.log(`🔄 Removing ${toRemove.length} closed positions that are now live:`, toRemove);
      setClosedPositions(prev => {
        const updated = { ...prev };
        toRemove.forEach(symbol => delete updated[symbol]);
        return updated;
      });
    }
  }, [positions, closedPositions]);

  // **CRITICAL: Detect positions that disappear from API (expired, auto-closed, etc.)**
  // Save them to closedPositions before they vanish from the UI
  const prevPositionsRef = useRef([]);
  const closedPositionsRef = useRef(closedPositions);

  // Keep closedPositionsRef in sync
  useEffect(() => {
    closedPositionsRef.current = closedPositions;
  }, [closedPositions]);
  useEffect(() => {
    // Skip on first render or if no positions
    if (prevPositionsRef.current.length === 0 && positions.length > 0) {
      prevPositionsRef.current = positions;
      return;
    }

    // Skip if positions haven't actually changed (same array reference)
    if (prevPositionsRef.current === positions) {
      return;
    }

    // Find positions that existed before but are now gone
    const currentSymbols = new Set(positions.map(p => p.product_symbol));
    const previousSymbols = prevPositionsRef.current;

    if (process.env.NODE_ENV === 'development') {
      console.log(`🔍 Position change check: prev=${previousSymbols.length}, current=${positions.length}`);
    }

    const disappeared = previousSymbols.filter(
      prevPos => !currentSymbols.has(prevPos.product_symbol) && !closedPositionsRef.current[prevPos.product_symbol]
    );

    if (disappeared.length > 0) {
      console.log(`📦 Detected ${disappeared.length} positions that disappeared (likely expired or auto-closed)`);

      const newClosedPositions = {};
      disappeared.forEach(pos => {
        newClosedPositions[pos.product_symbol] = {
          product_symbol: pos.product_symbol,
          realized_pnl: pos.unrealized_pnl || 0, // Use last known PnL
          closed_at: new Date().toISOString(),
          entry_price: pos.entry_price || 0,
          close_price: pos.best_bid || pos.best_ask || 0,
          original_size: pos.size || 0,
          greeks: pos.greeks || {},
          underlying: pos.product_symbol.split('-')[1] || 'BTC',
          strike: parseInt(pos.product_symbol.split('-')[2]) || 0,
          expiry_code: pos.product_symbol.split('-')[3] || '',
          option_type: pos.product_symbol.startsWith('C-') ? 'Call' : 'Put',
        };
        console.log(`  → ${pos.product_symbol}: PnL $${(pos.unrealized_pnl || 0).toFixed(4)}`);
      });

      setClosedPositions(prev => ({ ...prev, ...newClosedPositions }));
    }

    // Update the ref for next comparison
    prevPositionsRef.current = positions;
  }, [positions]); // Only depend on positions, not closedPositions!

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

  // Track selected futures from localStorage (updates when FuturesPanel changes selection)
  const [selectedFuturesState, setSelectedFuturesState] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('futures_selected_positions_payoff') || '[]');
    } catch {
      return [];
    }
  });

  // Listen for localStorage changes (when FuturesPanel updates the selection)
  useEffect(() => {
    const handleStorageChange = () => {
      try {
        const selectedFutures = JSON.parse(localStorage.getItem('futures_selected_positions_payoff') || '[]');
        setSelectedFuturesState(selectedFutures);
      } catch {
        setSelectedFuturesState([]);
      }
    };

    // Listen for storage events (cross-tab) and custom events (same-tab)
    window.addEventListener('storage', handleStorageChange);
    window.addEventListener('futures_selected_changed', handleStorageChange);

    return () => {
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('futures_selected_changed', handleStorageChange);
    };
  }, []);

  // Filter futures positions to only selected ones
  const visibleFuturesPositions = useMemo(() => {
    return futuresPositions.filter((pos) => selectedFuturesState.includes(pos.product_symbol));
  }, [futuresPositions, selectedFuturesState]);

  // Enrich positions with IV data from Delta Exchange
  // Phase 5 Optimization: Uses module-level cache with 60s TTL
  const enrichPositionsWithIV = async (positions) => {
    try {
      const symbols = positions.map(pos => pos.product_symbol).filter(Boolean);
      if (symbols.length === 0) return positions;

      const now = Date.now();
      const cacheAge = now - _ivCache.timestamp;

      // Check if cache is still fresh
      if (cacheAge < IV_CACHE_TTL_MS && Object.keys(_ivCache.data).length > 0) {
        // Use cached IV data - only fetch for symbols not in cache
        const uncachedSymbols = symbols.filter(s => _ivCache.data[s] === undefined);

        if (uncachedSymbols.length === 0) {
          // All symbols cached - instant return
          return positions.map(pos => ({
            ...pos,
            iv: _ivCache.data[pos.product_symbol] ?? pos.iv ?? null
          }));
        }

        // Only fetch uncached symbols
        const newIvData = await fetchIVForSymbols(uncachedSymbols);
        Object.assign(_ivCache.data, newIvData);

        return positions.map(pos => ({
          ...pos,
          iv: _ivCache.data[pos.product_symbol] ?? pos.iv ?? null
        }));
      }

      // Cache expired - refresh all
      const ivMap = await fetchIVForSymbols(symbols);
      _ivCache.data = ivMap;
      _ivCache.timestamp = now;

      return positions.map(pos => ({
        ...pos,
        iv: ivMap[pos.product_symbol] ?? null
      }));
    } catch (err) {
      console.error('Failed to enrich positions with IV:', err);
      return positions;
    }
  };

  // Fetch IV for specific symbols from Delta Exchange
  const fetchIVForSymbols = async (symbols) => {
    const tickerPromises = symbols.map(async (symbol) => {
      try {
        const response = await fetch(`https://api.india.delta.exchange/v2/tickers/${symbol}`);
        const result = await response.json();
        if (result?.success && result?.result) {
          const quotes = result.result.quotes || {};
          const bidIV = parseFloat(quotes.bid_iv) || 0;
          const askIV = parseFloat(quotes.ask_iv) || 0;
          return { symbol, iv: bidIV && askIV ? (bidIV + askIV) / 2 : (bidIV || askIV) };
        }
        return { symbol, iv: null };
      } catch {
        return { symbol, iv: null };
      }
    });
    const ivData = await Promise.all(tickerPromises);
    return Object.fromEntries(ivData.map(d => [d.symbol, d.iv]));
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

  // Load Take Profit settings for all positions
  const loadTakeProfitSettings = useCallback(async () => {
    try {
      const { data } = await api.get('/api/options/take-profit/strike/all');
      if (data?.success && data.settings) {
        const settingsMap = {};
        data.settings.forEach((s) => {
          settingsMap[s.symbol] = s;
        });
        setTpSettings(settingsMap);
      }
    } catch (err) {
      console.error('Failed to load take profit settings:', err);
    }
  }, []);

  // Handle take profit setting update from child component
  const handleTakeProfitUpdate = useCallback((symbol, settings) => {
    setTpSettings((prev) => {
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

  // ============================================================================
  // PHASE 2 OPTIMIZATION: Use unified dashboard endpoint for initial load and polling
  // ============================================================================
  
  // Initial load - use unified endpoint (Phase 2)
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      
      // Try unified endpoint first (Phase 2 optimization)
      const dashSuccess = await fetchDashboard();
      
      // Load auxiliary data not in unified endpoint
      await Promise.all([
        loadSLTPSettings(),
        loadMaxLossSettings(),
        loadTakeProfitSettings(),
      ]);
      
      setLoading(false);
      
      // Fallback to individual calls if unified fails
      if (!dashSuccess) {
        console.warn('⚠️ Unified dashboard endpoint failed, using legacy individual calls');
        await Promise.all([
          fetchStatus(),
          fetchPositions(),
          fetchPendingOrders(),
          fetchFuturesPositions(),
        ]);
      }
    };
    loadData();
  }, [fetchDashboard, loadSLTPSettings, loadMaxLossSettings, loadTakeProfitSettings, fetchStatus, fetchPositions, fetchPendingOrders, fetchFuturesPositions]);

  // Auto-refresh every pollInterval ms - use unified endpoint (Phase 2)
  // Phase 5 Optimization: Removed SL/TP/MaxLoss/TP settings from poll loop
  // Those are user-configured and only change when user explicitly modifies them
  useEffect(() => {
    const interval = setInterval(async () => {
      await fetchDashboard();
    }, pollInterval);
    return () => clearInterval(interval);
  }, [fetchDashboard, pollInterval]);

  // ============================================================================
  // PHASE 2 OPTIMIZATION: Persistent WebSocket Connection
  // Single connection reused across component lifecycle, smart subscription updates
  // ============================================================================
  
  // Initialize persistent WebSocket connection once
  useEffect(() => {
    if (!socketRef.current) {
      socketRef.current = io({
        path: '/socket.io',
        transports: ['polling'],
        upgrade: false,
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionAttempts: 10,
      });
      
      socketRef.current.on('connect', () => {
        console.log('[OptionsPanel] ⚡ Phase 2: Persistent WebSocket connected');
      });
      
      socketRef.current.on('options_ticker_update', (data) => {
        const { symbol, best_bid, best_ask, mark_price, timestamp } = data;
        
        // Update positions with new bid/ask data
        setPositions(prevPositions => 
          prevPositions.map(pos => {
            if (pos.product_symbol === symbol) {
              return {
                ...pos,
                best_bid,
                best_ask,
                mark_price,
                ws_updated: timestamp
              };
            }
            return pos;
          })
        );
      });
      
      socketRef.current.on('disconnect', () => {
        console.log('[OptionsPanel] WebSocket disconnected (will auto-reconnect)');
      });
      
      socketRef.current.on('connect_error', (error) => {
        console.error('[OptionsPanel] WebSocket connection error:', error);
      });
    }
    
    // Cleanup only on unmount (not on every positions change)
    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
        socketRef.current = null;
      }
    };
  }, []); // Empty deps - run once on mount
  
  // Update subscriptions when positions change (without reconnecting)
  useEffect(() => {
    if (!socketRef.current || positions.length === 0) return;
    
    const symbols = positions.map(p => p.product_symbol);
    
    // Update subscriptions without reconnecting
    if (socketRef.current.connected) {
      socketRef.current.emit('subscribe_options_tickers', { symbols });
      console.log(`[OptionsPanel] ⚡ Updated ${symbols.length} subscriptions (Phase 2: no reconnect)`);
    } else {
      // If not connected yet, subscribe on next connect event
      const onConnect = () => {
        socketRef.current.emit('subscribe_options_tickers', { symbols });
        socketRef.current.off('connect', onConnect);
      };
      socketRef.current.on('connect', onConnect);
    }
  }, [positions.map(p => p.product_symbol).join(',')]); // Re-subscribe when positions change

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

  // Phase 4: Keyboard shortcuts for ultra-fast trading
  useEffect(() => {
    if (!turboMode) return;

    const handleKeyPress = (e) => {
      // Don't interfere with inputs or dialogs
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (closeDialog.open || addDialog.open) return;

      const key = e.key.toLowerCase();

      // Navigate positions with arrow keys
      if (key === 'arrowdown') {
        e.preventDefault();
        setSelectedRowIndex(prev => {
          // First arrow press activates selection at index 0
          if (prev === -1) return 0;
          return Math.min(prev + 1, sortedPositions.length - 1);
        });
      } else if (key === 'arrowup') {
        e.preventDefault();
        setSelectedRowIndex(prev => {
          // First arrow press activates selection at index 0
          if (prev === -1) return 0;
          return Math.max(prev - 1, 0);
        });
      }

      // Quick actions on selected position
      if (sortedPositions.length === 0 || selectedRowIndex === -1) return;
      const selectedPos = sortedPositions[selectedRowIndex];
      if (!selectedPos) return;

      // C = Close position
      if (key === 'c') {
        e.preventDefault();
        setCloseDialog({
          open: true,
          position: selectedPos,
        });
      }

      // B = Buy more (add to position if long, or reduce if short)
      if (key === 'b') {
        e.preventDefault();
        setAddDialog({
          open: true,
          position: selectedPos,
          side: 'buy',
          defaultSize: lastUsedSize,
        });
      }

      // S = Sell (add to position if short, or reduce if long)
      if (key === 's') {
        e.preventDefault();
        setAddDialog({
          open: true,
          position: selectedPos,
          side: 'sell',
          defaultSize: lastUsedSize,
        });
      }

      // ESC = Cancel any operation
      if (key === 'escape') {
        e.preventDefault();
        setCloseDialog({ open: false, position: null });
        setAddDialog({ open: false, position: null, side: null });
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [turboMode, sortedPositions, selectedRowIndex, lastUsedSize, closeDialog.open, addDialog.open]);

  // Day 1: Calculate Probability of Profit (PoP) for each position
  // Phase 5 Optimization: Throttled to recalculate every 30s or when position count changes
  const popLastCalcRef = useRef(0);
  const popLastCountRef = useRef(0);
  useEffect(() => {
    if (!sortedPositions || sortedPositions.length === 0) {
      if (Object.keys(popData).length > 0) setPopData({});
      return;
    }

    // Only recalculate if: position count changed OR 30 seconds elapsed
    const now = Date.now();
    const positionSymbols = sortedPositions.map(p => p.product_symbol).sort().join(',');
    const posCountChanged = positionSymbols !== popLastCountRef.current;
    const timeElapsed = now - popLastCalcRef.current > 30000;

    if (!posCountChanged && !timeElapsed) return;

    popLastCalcRef.current = now;
    popLastCountRef.current = positionSymbols;

    const newPopData = {};

    sortedPositions.forEach((pos) => {
      const symbolParts = (pos.product_symbol || '').split('-');
      if (symbolParts.length < 4) return;

      const optionTypeChar = symbolParts[0];
      const underlying = symbolParts[1];
      const strikePrice = parseFloat(symbolParts[2]);
      const expiryStr = symbolParts[3];

      const optionType = optionTypeChar === 'C' ? 'call' : optionTypeChar === 'P' ? 'put' : null;
      if (!optionType) return;

      let spotPrice = pos.greeks?.spot || indexPrices[underlying] || 0;
      if (!spotPrice || spotPrice <= 0) return;
      if (!strikePrice || strikePrice <= 0) return;
      if (!expiryStr || expiryStr.length !== 6) return;

      try {
        const day = parseInt(expiryStr.slice(0, 2));
        const month = parseInt(expiryStr.slice(2, 4)) - 1;
        const year = 2000 + parseInt(expiryStr.slice(4, 6));
        const expiryDate = new Date(year, month, day, 8, 0, 0);
        const timeToExpiry = (expiryDate - new Date()) / (1000 * 60 * 60 * 24 * 365);

        if (timeToExpiry <= 0) return;

        let volatility = pos.iv || 0.8;

        const pop = calculatePoP({
          spotPrice,
          strike: strikePrice,
          entryPrice: Math.abs(pos.entry_price) || 0,
          timeToExpiry,
          volatility,
          optionType,
          side: pos.size > 0 ? 'buy' : 'sell',
        });

        newPopData[pos.product_symbol] = pop * 100;
      } catch {
        // Skip failed calculations silently
      }
    });

    setPopData(newPopData);
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

  // ============================================================================
  // PHASE 1 OPTIMIZATION: Performance monitoring
  // Track render times and warn about slow operations
  // ============================================================================
  useEffect(() => {
    const renderStart = performance.now();
    return () => {
      const renderTime = performance.now() - renderStart;
      if (renderTime > 50) {
        console.warn(
          `⚠️ Slow render detected: ${renderTime.toFixed(2)}ms (target: <50ms)`,
          { positionCount: positions.length, visibleCount: sortedPositions.length }
        );
      }
    };
  });

  // Manual refresh - Phase 2: Use unified dashboard endpoint ⚡
  const handleRefresh = async () => {
    const refreshStart = performance.now();
    setRefreshing(true);
    
    // Phase 2: Single unified API call
    const success = await fetchDashboard();
    
    // Fallback to individual calls if needed
    if (!success) {
      await Promise.all([
        fetchStatus(),
        fetchPositions(),
        fetchPendingOrders(),
        fetchFuturesPositions()
      ]);
    }
    
    setRefreshing(false);
    const refreshTime = performance.now() - refreshStart;
    
    if (refreshTime > 200) {
      console.warn(`⚠️ Slow refresh: ${refreshTime.toFixed(2)}ms (target: <200ms)`);
    } else {
      console.log(`⚡ Fast refresh: ${refreshTime.toFixed(2)}ms (Phase 2 unified endpoint)`);
    }
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
        // Save the closed position to closedPositions for continued visibility
        // This keeps the position visible with size=0 and its realized PnL
        const closedPosData = {
          product_symbol: position.product_symbol,
          realized_pnl: position.unrealized_pnl || 0, // Current unrealized becomes realized
          closed_at: new Date().toISOString(),
          entry_price: position.entry_price || 0,
          close_price: data.fill_price || position.best_bid || position.best_ask || 0,
          original_size: position.size || 0,
          greeks: position.greeks || {},
          // Keep original position data for reference
          underlying: position.product_symbol.split('-')[1] || 'BTC',
          strike: parseInt(position.product_symbol.split('-')[2]) || 0,
          expiry_code: position.product_symbol.split('-')[3] || '',
          option_type: position.product_symbol.startsWith('C-') ? 'Call' : 'Put',
        };

        setClosedPositions(prev => ({
          ...prev,
          [position.product_symbol]: closedPosData
        }));

        console.log(`📦 Saved closed position: ${position.product_symbol} with realized PnL: $${closedPosData.realized_pnl.toFixed(4)}`);

        // Check if order was actually filled (not just placed)
        const execType = data.execution_type || 'market'; // Close orders default to market
        const wasFilled = isOrderFilled(execType);

        // Only play sound and show notification when order is EXECUTED (filled)
        if (wasFilled) {
          soundManager.playTradeFilled();
          // Show visual notification only for filled orders
          setTradeNotification({
            symbol: position.product_symbol,
            side: 'close',
            size: Math.abs(position.size),
            price: data.fill_price,
          });
        }
        setOrderResult({ type: 'success', message: `Closed ${position.product_symbol}` });
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
        const execTypeRaw = data.execution_type || 'unknown';
        const execType = execTypeRaw.toLowerCase();
        const fillPrice = data.fill_price ? `@ $${parseFloat(data.fill_price).toFixed(2)}` : '';
        const wasFilled = isOrderFilled(execType);

        // Only play sound and show notification when order is EXECUTED (filled)
        if (wasFilled) {
          soundManager.playTradeFilled();
          // Show visual notification only for filled orders
          setTradeNotification({
            symbol: symbol,
            side: side,
            size: size,
            price: data.fill_price,
            execType: execType,
          });
        }

        // Show clearer feedback for pending limit orders vs filled orders
        setOrderResult({
          type: wasFilled ? 'success' : 'info',
          message: wasFilled
            ? `⚡ ${side.toUpperCase()} ${size} ${symbol} ${fillPrice} (${execType})`
            : `⏳ Order Placed: ${side.toUpperCase()} ${size} ${symbol} (Pending: ${execType})`,
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
      // Check if this is an SSR order type
      const isSSROrder = orderType?.startsWith('ssr_');
      
      if (isSSROrder) {
        // Route SSR orders to dedicated endpoint
        const ssrMode = SSR_MODE_MAP[orderType] || 'standard';
        const ssrRequestData = {
          symbol: position.product_symbol,
          side: side,
          quantity: parseFloat(size),
          ssrMode: ssrMode,
        };
        
        console.log(`🏎️ Placing SSR order: ${ssrMode}`, ssrRequestData);
        
        const { data } = await api.post('/api/options/ssr-order', ssrRequestData);
        
        if (data?.success) {
          soundManager.play('orderPlaced');
          setOrderResult({
            type: 'info',
            message: `🏎️ SSR ${ssrMode.toUpperCase()}: ${side.toUpperCase()} ${size} ${position.product_symbol} - monitoring started`,
          });
          fetchPositions();
        } else {
          setOrderResult({ type: 'error', message: data?.error || 'Failed to place SSR order' });
        }
      } else {
        // Regular order types
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
          const execTypeRaw = data.execution_type || 'unknown';
          const execType = execTypeRaw.toLowerCase();
          const fillPrice = data.fill_price ? `@ $${parseFloat(data.fill_price).toFixed(2)}` : '';
          const wasFilled = isOrderFilled(execType);

          // Only play sound and show notification when order is EXECUTED (filled)
          if (wasFilled) {
            soundManager.playTradeFilled();
            // Show visual notification only for filled orders
            setTradeNotification({
              symbol: position.product_symbol,
              side: side,
              size: size,
              price: data.fill_price,
              execType: execType,
            });
          }

          // Show clearer feedback for pending limit orders vs filled orders
          setOrderResult({
            type: wasFilled ? 'success' : 'info',
            message: wasFilled
              ? `⚡ ${side.toUpperCase()} ${size} ${position.product_symbol} ${fillPrice} (${execType})`
              : `⏳ Order Placed: ${side.toUpperCase()} ${size} ${position.product_symbol} (Pending: ${execType})`,
          });
          fetchPositions();
        } else {
          setOrderResult({ type: 'error', message: data?.error || 'Failed to add to position' });
        }
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

  // Helper function to calculate GCD (Greatest Common Divisor)
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

  // Helper function to calculate GCD of all selected positions
  const getPositionsGCD = (positions) => {
    if (positions.length === 0) return 1;
    if (positions.length === 1) return Math.abs(positions[0].size);

    let gcd = Math.abs(positions[0].size);
    for (let i = 1; i < positions.length; i++) {
      gcd = calculateGCD(gcd, Math.abs(positions[i].size));
    }
    return gcd === 0 ? 1 : gcd; // Prevent division by zero
  };

  // Batch order quantity multiplier logic: multiply each position's size by the orderQuantity
  // This creates scaled orders based on current position sizes
  // Example: Position has 1 lot bought → Multiplier 1 = 1 lot new buy
  // Example: Position has 2 lots sold → Multiplier 1 = 2 lots new sell
  // GCD Mode: Uses greatest common divisor of all positions for proportional scaling
  const calculateBatchOrders = (filterExpiry = null) => {
    // Get selected positions, optionally filtered by expiry
    let selectedPos = getSelectedPositions();
    if (filterExpiry) {
      selectedPos = selectedPos.filter(pos => getExpiryCode(pos.product_symbol) === filterExpiry);
    }
    const orders = [];

    // Calculate GCD if in GCD mode
    const gcd = multiplierMode === 'gcd' ? getPositionsGCD(selectedPos) : 1;

    selectedPos.forEach((pos) => {
      const currentSize = pos.size;
      const absCurrentSize = Math.abs(currentSize);
      const multiplier = Math.abs(orderQuantity);

      const midPrice = ((pos.best_bid || 0) + (pos.best_ask || 0)) / 2;

      // If position is long (size > 0), create BUY orders
      // If position is short (size < 0), create SELL orders
      // In normal mode: Order size = abs(position size) * multiplier
      // In GCD mode: Order size = (abs(position size) / GCD) * multiplier

      const isLong = currentSize > 0;
      const orderSize = multiplierMode === 'gcd'
        ? (absCurrentSize / gcd) * multiplier
        : absCurrentSize * multiplier;
      const side = isLong ? 'buy' : 'sell';

      orders.push({
        symbol: pos.product_symbol,
        size: orderSize,
        side: side,
        midPrice,
        originalSize: pos.size,
        optionType: pos.product_symbol.startsWith('C-') ? 'Call' : 'Put',
        expiry: getExpiryCode(pos.product_symbol),
      });
    });

    return orders;
  };

  // Track batch execution to prevent duplicates
  const [batchExecuting, setBatchExecuting] = useState(false);
  const [pendingBatchOrders, setPendingBatchOrders] = useState(null); // CRITICAL FIX: Store orders to prevent recalculation

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

    // CRITICAL FIX: Store orders BEFORE showing dialog to prevent recalculation
    setPendingBatchOrders(orders);

    // Show warning for large batches
    if (orders.length > 10) {
      setBatchConfirmDialog({
        open: true,
        orderCount: orders.length,
        estimatedTime: Math.ceil(orders.length * 1.5),
      });
      return; // Will be called when user confirms - uses pendingBatchOrders
    }

    // Execute batch (this is called after confirmation or if < 10 orders)
    executeBatch(orders);
  };

  // Actual batch execution logic (split from executeBatchOrders for confirmation flow)
  const executeBatch = async (orders) => {
    // Lock execution immediately
    console.log(`[BATCH EXECUTE] Starting batch execution with ${orders.length} orders`, orders);

    setBatchExecuting(true);
    setBatchOrderResults([]);

    // Check if this is an SSR execution mode
    const isSSRMode = executionMode?.startsWith('ssr_');
    
    // Determine order preference based on execution mode
    let orderPreference = 'maker_first'; // default
    let executionLabel = 'SMART';
    
    if (executionMode === 'immediate') {
      orderPreference = 'market_only';
      executionLabel = 'MARKET';
    } else if (executionMode === 'smart') {
      orderPreference = 'maker_first';
      executionLabel = 'SMART';
    } else if (isSSRMode) {
      orderPreference = executionMode; // pass the SSR mode directly
      executionLabel = executionMode === 'ssr_standard' ? 'SSR' : 
                       executionMode === 'ssr_aggressive' ? 'SSR AGGRO' : 'SSR SAFE';
    }

    console.log(`[BATCH EXECUTE] Execution mode: ${executionMode}, Preference: ${orderPreference}, Label: ${executionLabel}`);

    try {
      // Handle SSR batch orders differently - need to place sequentially for monitoring
      if (isSSRMode) {
        console.log(`[BATCH-SSR] Placing ${orders.length} SSR orders (mode: ${executionMode})`);
        const ssrMode = SSR_MODE_MAP[executionMode] || 'standard';
        const uiResults = [];
        
        for (const order of orders) {
          try {
            const { data } = await api.post('/api/options/ssr-order', {
              symbol: order.symbol,
              side: order.side,
              quantity: order.size,
              ssrMode: ssrMode,
            });
            
            if (data?.success) {
              uiResults.push({
                symbol: order.symbol,
                size: order.size,
                side: order.side,
                success: true,
                filled: false,
                message: `🏎️ SSR ${ssrMode.toUpperCase()}: Monitoring started`,
              });
            } else {
              uiResults.push({
                symbol: order.symbol,
                size: order.size,
                side: order.side,
                success: false,
                filled: false,
                message: `❌ ${data?.error || 'SSR order failed'}`,
              });
            }
          } catch (err) {
            uiResults.push({
              symbol: order.symbol,
              size: order.size,
              side: order.side,
              success: false,
              filled: false,
              message: `❌ ${err.message}`,
            });
          }
        }
        
        setBatchOrderResults(uiResults);
        soundManager.play('orderPlaced');
        setOrderResult({
          type: 'info',
          message: `🏎️ ${executionLabel}: ${uiResults.filter(r => r.success).length}/${orders.length} orders monitoring`,
        });
        fetchPositions();
        return;
      }

      // Regular batch execution (market/smart)
      console.log(`[BATCH-API] Calling /api/options/batch_add with ${orders.length} orders`);

      const { data } = await api.post('/api/options/batch_add', {
        orders: orders.map(order => ({
          symbol: order.symbol,
          size: order.size,
          side: order.side
        })),
        order_preference: orderPreference,
        confirm: true
      });

      console.log(`[BATCH-API] Response received:`, data);

      if (data?.success) {
        const results = data.results || [];
        const successful = data.successful || 0;
        const failed = data.failed || 0;
        const executionTime = data.execution_time || '0s';

        // Convert API results to UI format
        const uiResults = results.map((result, index) => {
          if (result.success) {
            const fillPrice = result.fill_price;
            return {
              symbol: result.symbol,
              size: result.size,
              side: result.side,
              success: true,
              filled: executionMode === 'immediate' || result.execution_type?.includes('filled'),
              message: `✅ ${result.side.toUpperCase()} ${result.size} ${result.execution_type === 'market' ? 'FILLED' : result.execution_type} ${fillPrice ? '@ $' + parseFloat(fillPrice).toFixed(2) : ''}`,
            };
          } else {
            return {
              symbol: result.symbol,
              size: result.size,
              side: result.side,
              success: false,
              filled: false,
              message: `❌ ${result.error || 'Failed'}`,
            };
          }
        });

        setBatchOrderResults(uiResults);

        // Play sound and show notification only for filled orders
        // Find first order that was actually EXECUTED (filled), not just placed
        const firstFilled = results.find(r => r.success && isOrderFilled(r.execution_type));
        if (firstFilled) {
          soundManager.playTradeFilled();
          setTradeNotification({
            symbol: firstFilled.symbol,
            side: firstFilled.side,
            size: firstFilled.size,
            price: firstFilled.fill_price,
          });
        }

        // Show summary
        setOrderResult({
          type: failed === 0 ? 'success' : 'warning',
          message: `✅ Batch complete: ${successful} success, ${failed} failed in ${executionTime}`,
        });
        setTimeout(() => setOrderResult(null), 5000);

        console.log(`[BATCH-COMPLETE] ${successful} success, ${failed} failed in ${executionTime}`);

      } else {
        // API returned error
        const errorMsg = data?.error || 'Batch execution failed';
        console.error(`[BATCH-ERROR] ${errorMsg}`);

        setBatchOrderResults([{
          symbol: 'BATCH',
          success: false,
          filled: false,
          message: `❌ ${errorMsg}`,
        }]);

        setOrderResult({
          type: 'error',
          message: `❌ Batch failed: ${errorMsg}`,
        });
        setTimeout(() => setOrderResult(null), 5000);
      }

    } catch (err) {
      // Network or other error
      const errorMsg = err.response?.data?.error || err.message || 'Unknown error';
      console.error(`[BATCH-EXCEPTION]`, err);

      setBatchOrderResults([{
        symbol: 'BATCH',
        success: false,
        filled: false,
        message: `❌ ${errorMsg}`,
      }]);

      setOrderResult({
        type: 'error',
        message: `❌ Batch error: ${errorMsg}`,
      });
      setTimeout(() => setOrderResult(null), 5000);
    }

    // Always reset executing state
    setBatchExecuting(false);
    setPendingBatchOrders(null);
  };

  // Auto-loop execution: Execute batch orders multiple times with fill polling
  const executeAutoLoop = async (startFromRound = 1) => {
    console.log('[AUTO-LOOP] executeAutoLoop called with startFromRound:', startFromRound);
    
    if (autoLoopRunning) {
      console.log('⚠️ Auto-loop already running');
      return;
    }

    const orders = calculateBatchOrders();
    console.log('[AUTO-LOOP] Calculated orders:', orders.length, orders);
    
    if (orders.length === 0) {
      console.log('[AUTO-LOOP] ERROR: No orders calculated');
      console.log('[AUTO-LOOP] selectedStrikes:', selectedStrikes);
      console.log('[AUTO-LOOP] sortedPositions:', sortedPositions?.length);
      console.log('[AUTO-LOOP] orderQuantity:', orderQuantity);
      setAutoLoopError('No orders to execute. Select positions and set quantities.');
      return;
    }

    if (!autoLoopRounds || autoLoopRounds < 1) {
      setAutoLoopError('Please set number of rounds (must be >= 1)');
      return;
    }

    console.log(`[AUTO-LOOP] Starting execution: ${autoLoopRounds} rounds, ${orders.length} orders per round`);

    // Reset state
    setAutoLoopRunning(true);
    setAutoLoopCurrentRound(startFromRound > 1 ? startFromRound - 1 : 0);
    setAutoLoopError(null);
    setAutoLoopProgress({});
    autoLoopStopRef.current = false;

    // Save run state for recovery
    const runState = {
      startTime: Date.now(),
      totalRounds: autoLoopRounds,
      currentRound: 0,
      orderSymbols: orders.map(o => o.symbol),
      completed: false,
    };
    setAutoLoopLastRun(runState);

    console.log(`[AUTO-LOOP] Starting ${autoLoopRounds} rounds with ${orders.length} orders per round (from round ${startFromRound})`);

    const orderPreference = executionMode === 'immediate' ? 'market_only' : 'maker_first';

    try {
      for (let round = startFromRound; round <= autoLoopRounds; round++) {
        // Check if user stopped the loop
        if (autoLoopStopRef.current) {
          console.log('[AUTO-LOOP] Stopped by user');
          setAutoLoopError(`Stopped by user at round ${round - 1}/${autoLoopRounds}`);
          // Clear last run on intentional stop
          setAutoLoopLastRun(null);
          break;
        }

        setAutoLoopCurrentRound(round);
        
        // Update recovery state
        setAutoLoopLastRun(prev => ({ ...prev, currentRound: round }));
        console.log(`[AUTO-LOOP] Starting round ${round}/${autoLoopRounds}`);

        // Reset progress for this round
        const roundProgress = {};
        orders.forEach(order => {
          roundProgress[order.symbol] = { filled: false, orderId: null, size: order.size, status: 'placing' };
        });
        setAutoLoopProgress(roundProgress);

        // Step 1: Place all orders in this round
        console.log(`[AUTO-LOOP] Placing ${orders.length} orders...`);
        const response = await api.post('/api/options/batch_add', {
          orders: orders.map(o => ({
            symbol: o.symbol,
            side: o.side,
            size: o.size,
          })),
          order_preference: orderPreference,
          confirm: true,
        });

        if (!response.data.success) {
          throw new Error(response.data.error || 'Batch order placement failed');
        }

        const placedOrders = response.data.results || [];
        console.log(`[AUTO-LOOP] Placed ${placedOrders.length} orders:`, placedOrders);

        // Check if any orders failed to place
        const failedPlacements = placedOrders.filter(r => !r.success);
        if (failedPlacements.length > 0) {
          const errorMsg = `Round ${round}: Failed to place ${failedPlacements.length} order(s): ${failedPlacements.map(f => `${f.symbol} - ${f.error || f.message}`).join(', ')}`;
          throw new Error(errorMsg);
        }

        // Check which orders were filled immediately vs pending
        // Orders filled via 'market' or 'limit_filled' execution types are already done
        const filledImmediately = [];
        const pendingOrders = [];
        
        placedOrders.forEach(result => {
          if (result.success) {
            const executionType = result.execution_type || '';
            const isFilledType = ['market', 'market_fallback', 'market_fallback_no_quotes', 
                                   'market_fallback_error', 'limit_filled', 'limit_filled_late'].includes(executionType);
            
            if (isFilledType || !result.order_id) {
              // Order was filled immediately
              filledImmediately.push(result);
            } else {
              // Order is pending (limit order placed, waiting for fill)
              pendingOrders.push(result);
            }
          }
        });

        console.log(`[AUTO-LOOP] Round ${round}: ${filledImmediately.length} filled immediately, ${pendingOrders.length} pending`);

        // Update progress with filled orders
        const updatedProgress = { ...roundProgress };
        filledImmediately.forEach(result => {
          updatedProgress[result.symbol] = {
            filled: true,
            orderId: result.order_id,
            size: result.size,
            fillPrice: result.fill_price,
            status: 'filled',
          };
        });
        pendingOrders.forEach(result => {
          updatedProgress[result.symbol] = {
            filled: false,
            orderId: result.order_id,
            size: result.size,
            status: 'pending',
          };
        });
        setAutoLoopProgress(updatedProgress);

        // Step 2: Poll for pending orders if any
        if (pendingOrders.length > 0) {
          console.log(`[AUTO-LOOP] Waiting for ${pendingOrders.length} pending orders to fill...`);
          
          const orderIds = pendingOrders.map(r => r.order_id).filter(id => id);
          let allFilled = false;
          let pollCount = 0;

          while (!allFilled && !autoLoopStopRef.current) {
            pollCount++;
            await new Promise(resolve => setTimeout(resolve, 2000)); // Poll every 2 seconds

            // Fetch order status
            try {
              const statusResponse = await api.post('/api/options/batch_order_status', {
                order_ids: orderIds,
              });

              if (!statusResponse.data.success) {
                console.warn('[AUTO-LOOP] Failed to fetch order status, retrying...', statusResponse.data.error);
                continue;
              }

              const orderStatuses = statusResponse.data.orders || [];
              
              // Update progress
              const progressUpdate = { ...updatedProgress };
              orderStatuses.forEach(status => {
                const matchingOrder = pendingOrders.find(o => o.order_id === status.order_id);
                if (matchingOrder) {
                  // Delta Exchange uses 'closed' for filled orders, not 'filled'
                  const isFilled = status.state === 'filled' || status.state === 'closed';
                  const isCancelled = status.state === 'cancelled';
                  const isRejected = status.state === 'rejected';
                  
                  if (isCancelled || isRejected) {
                    throw new Error(`Order ${matchingOrder.symbol} was ${status.state}`);
                  }
                  
                  progressUpdate[matchingOrder.symbol] = {
                    filled: isFilled,
                    orderId: status.order_id,
                    size: status.size,
                    fillPrice: status.fill_price,
                    status: isFilled ? 'filled' : 'pending',
                  };
                }
              });
              setAutoLoopProgress(progressUpdate);

              // Check if all orders are filled
              const filledCount = Object.values(progressUpdate).filter(p => p.filled).length;
              allFilled = filledCount === orders.length;

              console.log(`[AUTO-LOOP] Round ${round} - Poll ${pollCount}: ${filledCount}/${orders.length} filled`);

            } catch (pollError) {
              console.error('[AUTO-LOOP] Poll error:', pollError);
              if (pollError.message.includes('cancelled') || pollError.message.includes('rejected')) {
                throw pollError;
              }
              // Continue polling on other errors
            }
          }
        } else {
          console.log(`[AUTO-LOOP] Round ${round} - All ${filledImmediately.length} orders filled immediately`);
        }

        // Check if stopped during polling
        if (autoLoopStopRef.current) {
          console.log('[AUTO-LOOP] Stopped during polling');
          setAutoLoopError(`Stopped by user at round ${round}/${autoLoopRounds}`);
          // Clear last run on intentional stop
          setAutoLoopLastRun(null);
          break;
        }

        // All orders in this round are filled
        console.log(`[AUTO-LOOP] Round ${round} complete - all orders filled`);
        
        // Play sound for round completion
        soundManager.playTradeFilled();
        
        // Update progress to show all filled
        const finalProgress = {};
        orders.forEach(order => {
          finalProgress[order.symbol] = { filled: true, status: 'filled', size: order.size };
        });
        setAutoLoopProgress(finalProgress);
        
        // Small delay before next round
        if (round < autoLoopRounds) {
          console.log(`[AUTO-LOOP] Waiting 1s before next round...`);
          await new Promise(resolve => setTimeout(resolve, 1000));
        }
      }

      // All rounds completed successfully
      if (!autoLoopStopRef.current) {
        console.log('[AUTO-LOOP] All rounds completed successfully');
        // Mark as completed in recovery state
        setAutoLoopLastRun(prev => prev ? { ...prev, completed: true, endTime: Date.now() } : null);
        setOrderResult({
          type: 'success',
          message: `✅ Auto-loop completed: ${autoLoopRounds} rounds executed successfully`,
        });
        setTimeout(() => setOrderResult(null), 5000);
      }

    } catch (error) {
      const errorMsg = error.message || 'Auto-loop execution failed';
      console.error('[AUTO-LOOP] Error:', error);
      // Keep the lastRun state so user can see what was interrupted
      setAutoLoopError(`${errorMsg} (Round ${autoLoopCurrentRound}/${autoLoopRounds})`);
      setOrderResult({
        type: 'error',
        message: `❌ Auto-loop error at round ${autoLoopCurrentRound}: ${errorMsg}`,
      });
      setTimeout(() => setOrderResult(null), 8000);
    } finally {
      setAutoLoopRunning(false);
      autoLoopStopRef.current = false;
    }
  };

  // Stop auto-loop
  const stopAutoLoop = () => {
    autoLoopStopRef.current = true;
    console.log('[AUTO-LOOP] Stop requested');
  };

  // Clear auto-loop error/warning and persisted state
  const clearAutoLoopError = () => {
    setAutoLoopError(null);
    setAutoLoopLastRun(null);
    localStorage.removeItem('autoLoopLastRun');
  };

  // ==================== PER-EXPIRY AUTO-LOOP ====================
  
  // Get unique expiries from selected positions
  const selectedExpiriesForLoop = useMemo(() => {
    const selected = getSelectedPositions();
    const expiries = new Set();
    selected.forEach(pos => {
      const exp = getExpiryCode(pos.product_symbol);
      if (exp) expiries.add(exp);
    });
    return Array.from(expiries).sort((a, b) => {
      // Sort by date
      const dayA = parseInt(a.substring(0, 2));
      const monthA = parseInt(a.substring(2, 4));
      const yearA = parseInt(a.substring(4, 6));
      const dayB = parseInt(b.substring(0, 2));
      const monthB = parseInt(b.substring(2, 4));
      const yearB = parseInt(b.substring(4, 6));
      if (yearA !== yearB) return yearA - yearB;
      if (monthA !== monthB) return monthA - monthB;
      return dayA - dayB;
    });
  }, [selectedStrikes, positions]);

  // Check if any expiry loop is running
  const anyExpiryLoopRunning = useMemo(() => {
    return Object.values(expiryLoopState).some(state => state.running);
  }, [expiryLoopState]);

  // Execute auto-loop for a specific expiry
  const executeExpiryAutoLoop = async (expiryCode) => {
    // Check if already running for this expiry
    if (expiryLoopState[expiryCode]?.running) {
      console.log(`⚠️ Auto-loop already running for ${expiryCode}`);
      return;
    }

    const orders = calculateBatchOrders(expiryCode);
    if (orders.length === 0) {
      setExpiryLoopState(prev => ({
        ...prev,
        [expiryCode]: { ...prev[expiryCode], error: 'No orders to execute for this expiry' }
      }));
      return;
    }

    if (!autoLoopRounds || autoLoopRounds < 1) {
      setExpiryLoopState(prev => ({
        ...prev,
        [expiryCode]: { ...prev[expiryCode], error: 'Please set number of rounds (must be >= 1)' }
      }));
      return;
    }

    // Initialize state for this expiry
    expiryStopRefs.current[expiryCode] = false;
    setExpiryLoopState(prev => ({
      ...prev,
      [expiryCode]: {
        running: true,
        currentRound: 0,
        totalRounds: autoLoopRounds,
        progress: {},
        error: null,
        startTime: Date.now(),
      }
    }));

    console.log(`[AUTO-LOOP:${expiryCode}] Starting ${autoLoopRounds} rounds with ${orders.length} orders`);
    const orderPreference = executionMode === 'immediate' ? 'market_only' : 'maker_first';

    try {
      for (let round = 1; round <= autoLoopRounds; round++) {
        // Check if stopped
        if (expiryStopRefs.current[expiryCode]) {
          console.log(`[AUTO-LOOP:${expiryCode}] Stopped by user at round ${round - 1}`);
          setExpiryLoopState(prev => ({
            ...prev,
            [expiryCode]: { ...prev[expiryCode], running: false, error: `Stopped at round ${round - 1}/${autoLoopRounds}` }
          }));
          break;
        }

        // Update round counter
        setExpiryLoopState(prev => ({
          ...prev,
          [expiryCode]: { ...prev[expiryCode], currentRound: round }
        }));

        console.log(`[AUTO-LOOP:${expiryCode}] Round ${round}/${autoLoopRounds}`);

        // Reset progress for this round
        const roundProgress = {};
        orders.forEach(order => {
          roundProgress[order.symbol] = { filled: false, orderId: null, size: order.size, status: 'placing' };
        });
        setExpiryLoopState(prev => ({
          ...prev,
          [expiryCode]: { ...prev[expiryCode], progress: roundProgress }
        }));

        // Place orders
        const response = await api.post('/api/options/batch_add', {
          orders: orders.map(o => ({ symbol: o.symbol, side: o.side, size: o.size })),
          order_preference: orderPreference,
          confirm: true,
        });

        if (!response.data.success) {
          throw new Error(response.data.error || 'Batch order placement failed');
        }

        const placedOrders = response.data.results || [];
        const failedPlacements = placedOrders.filter(r => !r.success);
        if (failedPlacements.length > 0) {
          throw new Error(`Failed to place ${failedPlacements.length} order(s)`);
        }

        // Separate filled vs pending
        const filledImmediately = [];
        const pendingOrders = [];
        placedOrders.forEach(result => {
          if (result.success) {
            const executionType = result.execution_type || '';
            const isFilledType = ['market', 'market_fallback', 'limit_filled', 'limit_filled_late'].includes(executionType);
            if (isFilledType || !result.order_id) {
              filledImmediately.push(result);
            } else {
              pendingOrders.push(result);
            }
          }
        });

        // Update progress
        const updatedProgress = { ...roundProgress };
        filledImmediately.forEach(result => {
          updatedProgress[result.symbol] = { filled: true, orderId: result.order_id, size: result.size, status: 'filled' };
        });
        pendingOrders.forEach(result => {
          updatedProgress[result.symbol] = { filled: false, orderId: result.order_id, size: result.size, status: 'pending' };
        });
        setExpiryLoopState(prev => ({
          ...prev,
          [expiryCode]: { ...prev[expiryCode], progress: updatedProgress }
        }));

        // Poll for pending orders
        if (pendingOrders.length > 0) {
          const orderIds = pendingOrders.map(r => r.order_id).filter(id => id);
          let allFilled = false;
          let pollCount = 0;

          while (!allFilled && !expiryStopRefs.current[expiryCode]) {
            pollCount++;
            await new Promise(resolve => setTimeout(resolve, 2000));

            try {
              const statusResponse = await api.post('/api/options/batch_order_status', { order_ids: orderIds });
              if (!statusResponse.data.success) continue;

              const orderStatuses = statusResponse.data.orders || [];
              const progressUpdate = { ...updatedProgress };

              orderStatuses.forEach(status => {
                const matchingOrder = pendingOrders.find(o => o.order_id === status.order_id);
                if (matchingOrder) {
                  // Delta Exchange uses 'closed' for filled orders, not 'filled'
                  const isFilled = status.state === 'filled' || status.state === 'closed';
                  if (status.state === 'cancelled' || status.state === 'rejected') {
                    throw new Error(`Order ${matchingOrder.symbol} was ${status.state}`);
                  }
                  progressUpdate[matchingOrder.symbol] = {
                    filled: isFilled,
                    orderId: status.order_id,
                    size: status.size,
                    status: isFilled ? 'filled' : 'pending',
                  };
                }
              });

              setExpiryLoopState(prev => ({
                ...prev,
                [expiryCode]: { ...prev[expiryCode], progress: progressUpdate }
              }));

              const filledCount = Object.values(progressUpdate).filter(p => p.filled).length;
              allFilled = filledCount === orders.length;
              console.log(`[AUTO-LOOP:${expiryCode}] Poll ${pollCount}: ${filledCount}/${orders.length} filled`);

            } catch (pollError) {
              if (pollError.message.includes('cancelled') || pollError.message.includes('rejected')) {
                throw pollError;
              }
            }
          }
        }

        // Check if stopped during polling
        if (expiryStopRefs.current[expiryCode]) {
          setExpiryLoopState(prev => ({
            ...prev,
            [expiryCode]: { ...prev[expiryCode], running: false, error: `Stopped at round ${round}/${autoLoopRounds}` }
          }));
          break;
        }

        // Round complete
        console.log(`[AUTO-LOOP:${expiryCode}] Round ${round} complete`);
        soundManager.playTradeFilled();

        // Update to all filled
        const finalProgress = {};
        orders.forEach(order => {
          finalProgress[order.symbol] = { filled: true, status: 'filled', size: order.size };
        });
        setExpiryLoopState(prev => ({
          ...prev,
          [expiryCode]: { ...prev[expiryCode], progress: finalProgress }
        }));

        // Delay before next round
        if (round < autoLoopRounds) {
          await new Promise(resolve => setTimeout(resolve, 1000));
        }
      }

      // All rounds complete
      if (!expiryStopRefs.current[expiryCode]) {
        console.log(`[AUTO-LOOP:${expiryCode}] All rounds completed`);
        setExpiryLoopState(prev => ({
          ...prev,
          [expiryCode]: { ...prev[expiryCode], running: false, completed: true, endTime: Date.now() }
        }));
        setOrderResult({
          type: 'success',
          message: `✅ [${expiryCode}] Auto-loop completed: ${autoLoopRounds} rounds`,
        });
        setTimeout(() => setOrderResult(null), 5000);
      }

    } catch (error) {
      console.error(`[AUTO-LOOP:${expiryCode}] Error:`, error);
      setExpiryLoopState(prev => ({
        ...prev,
        [expiryCode]: {
          ...prev[expiryCode],
          running: false,
          error: `${error.message} (Round ${prev[expiryCode]?.currentRound || '?'}/${autoLoopRounds})`,
        }
      }));
    }
  };

  // Stop auto-loop for specific expiry
  const stopExpiryAutoLoop = (expiryCode) => {
    expiryStopRefs.current[expiryCode] = true;
    console.log(`[AUTO-LOOP:${expiryCode}] Stop requested`);
  };

  // Stop all expiry loops
  const stopAllExpiryLoops = () => {
    Object.keys(expiryLoopState).forEach(expiry => {
      if (expiryLoopState[expiry]?.running) {
        expiryStopRefs.current[expiry] = true;
      }
    });
    console.log('[AUTO-LOOP] Stop all requested');
  };

  // Start all expiry loops simultaneously
  const startAllExpiryLoops = () => {
    selectedExpiriesForLoop.forEach(expiry => {
      if (!expiryLoopState[expiry]?.running) {
        executeExpiryAutoLoop(expiry);
      }
    });
  };

  // Clear expiry loop error and interrupted state
  const clearExpiryLoopError = (expiryCode) => {
    setExpiryLoopState(prev => {
      const updated = { ...prev };
      if (updated[expiryCode]) {
        // Clear error and interrupted flags
        updated[expiryCode] = { 
          ...updated[expiryCode], 
          error: null, 
          interrupted: false,
          interruptedAt: null 
        };
        // If the loop is not running and has no useful state, remove it entirely
        if (!updated[expiryCode].running && !updated[expiryCode].completed) {
          delete updated[expiryCode];
        }
      }
      // Also update localStorage to reflect the cleared state
      if (Object.keys(updated).length > 0) {
        localStorage.setItem('expiryLoopState', JSON.stringify(updated));
      } else {
        localStorage.removeItem('expiryLoopState');
      }
      return updated;
    });
  };

  // Clear all persisted loop state (useful for cleanup)
  const clearAllLoopState = () => {
    setExpiryLoopState({});
    localStorage.removeItem('expiryLoopState');
    localStorage.removeItem('autoLoopLastRun');
    setAutoLoopError(null);
    setAutoLoopLastRun(null);
    console.log('[AUTO-LOOP] Cleared all persisted loop state');
  };

  // ==================== END PER-EXPIRY AUTO-LOOP ====================

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
    if (symbol.startsWith('MV-')) return { type: 'MV STRADDLE', color: '#00bcd4' }; // Cyan for MV Straddle
    return { type: 'UNKNOWN', color: '#6b7280' };
  };

  const parseOptionSymbol = (symbol) => {
    // Handle MV Straddle format: MV-BTC-89400-250126
    if (symbol.startsWith('MV-')) {
      const parts = symbol.split('-');
      if (parts.length >= 4) {
        const underlying = parts[1];
        const strike = parseInt(parts[2]);
        const expiry = parts[3];
        // Parse expiry DDMMYY to readable format
        const day = expiry.substring(0, 2);
        const month = expiry.substring(2, 4);
        const year = '20' + expiry.substring(4, 6);
        return {
          type: 'MV Straddle',
          underlying,
          strike,
          expiry: `${day}/${month}/${year}`,
        };
      }
    }

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

  // FEB 2, 2026: Filter positions for adjustment panel based on user selection
  // Respects selectedExpiries (expiry filter dropdown) and selectedStrikes (checkbox selection)
  const filteredPositionsForAdjustment = useMemo(() => {
    let filtered = [...positions];

    // Filter by selected expiries (if any)
    if (selectedExpiries && selectedExpiries.length > 0) {
      filtered = filtered.filter(pos => {
        const posExpiry = getExpiryCode(pos.product_symbol);
        return posExpiry && selectedExpiries.includes(posExpiry);
      });
    }

    // Filter by selected strikes (if any checkboxes checked)
    if (
      selectedStrikes &&
      typeof selectedStrikes === 'object' &&
      Object.values(selectedStrikes).some(val => val === true)
    ) {
      const selectedSymbols = Object.keys(selectedStrikes).filter(sym => selectedStrikes[sym] === true);
      filtered = filtered.filter(pos => selectedSymbols.includes(pos.product_symbol));
    }

    // Fallback: if filtering results in empty array, return original positions
    // This prevents showing blank payoff graph
    return filtered.length > 0 ? filtered : positions;
  }, [positions, selectedExpiries, selectedStrikes]);

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
      {/* Persistent Auto-Loop Status Banner - Always visible at top */}
      {/* Shows per-expiry loop status when any expiry loop is running */}
      {(autoLoopRunning || anyExpiryLoopRunning) && (
        <Box sx={{ 
          position: 'sticky',
          top: 0,
          zIndex: 1100,
          bgcolor: 'rgba(251, 191, 36, 0.95)',
          color: '#000',
          py: 1,
          px: 2,
          mb: 1,
          borderRadius: '8px',
          boxShadow: '0 4px 12px rgba(251, 191, 36, 0.4)',
          animation: 'pulse-banner 2s infinite',
          '@keyframes pulse-banner': {
            '0%, 100%': { boxShadow: '0 4px 12px rgba(251, 191, 36, 0.4)' },
            '50%': { boxShadow: '0 4px 20px rgba(251, 191, 36, 0.7)' },
          },
        }}>
          {/* Header row */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: anyExpiryLoopRunning ? 1 : 0 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <CircularProgress size={20} thickness={5} sx={{ color: '#000' }} />
              <Typography variant="body1" fontWeight="bold">
                🔁 AUTO-LOOP ACTIVE
              </Typography>
              {!anyExpiryLoopRunning && autoLoopRunning && (
                <Typography variant="body2" sx={{ opacity: 0.8 }}>
                  Round {autoLoopCurrentRound}/{autoLoopRounds} • {Object.values(autoLoopProgress).filter(p => p.status === 'filled').length}/{Object.keys(autoLoopProgress).length} filled
                </Typography>
              )}
            </Box>
            <Button
              variant="contained"
              size="small"
              color="error"
              onClick={anyExpiryLoopRunning ? stopAllExpiryLoops : stopAutoLoop}
              startIcon={<BlockIcon />}
              sx={{ fontWeight: 'bold', bgcolor: '#ef4444', '&:hover': { bgcolor: '#dc2626' } }}
            >
              STOP ALL
            </Button>
          </Box>
          
          {/* Per-expiry detailed status */}
          {anyExpiryLoopRunning && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              {Object.entries(expiryLoopState)
                .filter(([_, state]) => state.running)
                .map(([expiry, state]) => {
                  const filledCount = Object.values(state.progress || {}).filter(p => p.filled).length;
                  const totalCount = Object.keys(state.progress || {}).length;
                  const pendingCount = totalCount - filledCount;
                  return (
                    <Box key={expiry} sx={{ bgcolor: 'rgba(0,0,0,0.15)', p: 1, borderRadius: '6px' }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                          <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                            📅 {expiry}
                          </Typography>
                          <Chip
                            size="small"
                            label={`Round ${state.currentRound}/${state.totalRounds}`}
                            sx={{ bgcolor: 'rgba(0,0,0,0.2)', height: 20, fontSize: '0.7rem' }}
                          />
                          <Typography variant="caption" sx={{ color: 'rgba(0,0,0,0.7)' }}>
                            ✅ {filledCount} filled • ⏳ {pendingCount} pending
                          </Typography>
                        </Box>
                        <IconButton
                          size="small"
                          onClick={(e) => { e.stopPropagation(); stopExpiryAutoLoop(expiry); }}
                          sx={{ p: 0.5, color: '#ef4444', bgcolor: 'rgba(239,68,68,0.2)', '&:hover': { bgcolor: 'rgba(239,68,68,0.3)' } }}
                        >
                          <BlockIcon sx={{ fontSize: 16 }} />
                        </IconButton>
                      </Box>
                      {/* Per-symbol progress chips */}
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                        {Object.entries(state.progress || {}).map(([symbol, prog]) => {
                          const parts = symbol.split('-');
                          const optType = parts[0];
                          const strike = parts[2];
                          return (
                            <Chip
                              key={symbol}
                              size="small"
                              label={`${prog.filled ? '✅' : '⏳'} ${optType}${strike}`}
                              sx={{
                                bgcolor: prog.filled ? 'rgba(16,185,129,0.3)' : 'rgba(0,0,0,0.2)',
                                color: prog.filled ? '#065f46' : '#000',
                                fontSize: '0.65rem',
                                height: 18,
                              }}
                            />
                          );
                        })}
                      </Box>
                    </Box>
                  );
                })}
            </Box>
          )}
        </Box>
      )}
      

      
      <Card sx={{ bgcolor: 'background.paper', borderRadius: 2 }}>
        <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
          {/* ═══ Phase 2: Primary Header Bar ═══ */}
          <Box
            sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="subtitle1" fontWeight="600" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <ShowChartIcon fontSize="small" /> Options Positions
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

              {/* Turbo Mode Toggle — stays in primary bar for fast access */}
              <Tooltip title={turboMode ? "Exit Turbo Mode - Show all features" : "Turbo Mode - Ultra-fast expiry day trading (minimal UI, keyboard shortcuts)"}>
                <Button
                  size="small"
                  variant={turboMode ? 'contained' : 'outlined'}
                  color={turboMode ? 'error' : 'warning'}
                  onClick={() => setTurboMode(!turboMode)}
                  sx={{ fontWeight: 'bold' }}
                  startIcon={turboMode ? '⚡' : null}
                >
                  {turboMode ? '⚡ TURBO' : 'Turbo'}
                </Button>
              </Tooltip>
            </Box>

            <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
              {/* Keyboard Shortcuts — tooltip instead of permanent bar */}
              <Tooltip
                title={
                  <Box sx={{ p: 0.5 }}>
                    <Typography variant="caption" fontWeight="bold" sx={{ display: 'block', mb: 0.5 }}>⌨️ Keyboard Shortcuts</Typography>
                    <Typography variant="caption" component="div">B = Buy &nbsp;|&nbsp; S = Sell &nbsp;|&nbsp; C = Close</Typography>
                    <Typography variant="caption" component="div">R = Refresh &nbsp;|&nbsp; Esc = Cancel</Typography>
                    <Typography variant="caption" component="div">↑/↓ = Navigate rows</Typography>
                  </Box>
                }
                arrow
                placement="bottom-end"
              >
                <IconButton size="small" sx={{ color: 'text.secondary' }}>
                  <HelpOutlineIcon fontSize="small" />
                </IconButton>
              </Tooltip>

              <Tooltip title="Sound Settings">
                <IconButton
                  onClick={() => setSoundSettingsOpen(true)}
                  size="small"
                  color="primary"
                >
                  <VolumeIcon fontSize="small" />
                </IconButton>
              </Tooltip>

              <Tooltip title="Refresh">
                <IconButton onClick={handleRefresh} disabled={refreshing} size="small">
                  {refreshing ? <CircularProgress size={18} /> : <RefreshIcon fontSize="small" />}
                </IconButton>
              </Tooltip>

              {/* Toggle secondary toolbar */}
              <Tooltip title={secondaryToolbarOpen ? 'Hide toolbar' : 'More controls'}>
                <IconButton
                  size="small"
                  onClick={() => {
                    const next = !secondaryToolbarOpen;
                    setSecondaryToolbarOpen(next);
                    localStorage.setItem('options_secondary_toolbar_open', JSON.stringify(next));
                  }}
                  sx={{ color: secondaryToolbarOpen ? 'primary.main' : 'text.secondary' }}
                >
                  <KeyboardArrowDownIcon
                    fontSize="small"
                    sx={{
                      transition: 'transform 0.2s',
                      transform: secondaryToolbarOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                    }}
                  />
                </IconButton>
              </Tooltip>
            </Box>
          </Box>

          {/* ═══ Phase 2: Secondary Toolbar (collapsible) ═══ */}
          <Collapse in={secondaryToolbarOpen}>
            <Box
              sx={{
                display: 'flex',
                gap: 1,
                flexWrap: 'wrap',
                alignItems: 'center',
                mb: 1,
                py: 0.75,
                px: 1,
                bgcolor: 'action.hover',
                borderRadius: 1,
                border: '1px solid',
                borderColor: 'divider',
              }}
            >
              {/* Polling interval */}
              <Tooltip title="Change price polling interval">
                <Button
                  size="small"
                  variant={pollInterval === 1000 ? 'contained' : 'outlined'}
                  color={pollInterval === 1000 ? 'primary' : 'inherit'}
                  onClick={() => setPollInterval(pollInterval === 5000 ? 1000 : 5000)}
                  sx={{ fontSize: '0.7rem', py: 0.25 }}
                >
                  ⏱ Poll: {pollInterval / 1000}s
                </Button>
              </Tooltip>

              {/* Custom order indicator */}
              {customOrder.length > 0 && (
                <Chip 
                  icon={<DragIcon />}
                  label="Custom Order"
                  size="small"
                  color="primary"
                  variant="filled"
                  sx={{ fontWeight: 'bold' }}
                  onDelete={resetOrder}
                  deleteIcon={
                    <Tooltip title="Reset to default sort order">
                      <CloseIcon sx={{ fontSize: '0.9rem !important' }} />
                    </Tooltip>
                  }
                />
              )}

              {/* Show hidden positions */}
              {hiddenPositions.length > 0 && (
                <Chip
                  label={`👁 ${hiddenPositions.length} hidden`}
                  size="small"
                  color="warning"
                  variant="outlined"
                  onClick={() => setHiddenPositions([])}
                  onDelete={() => setHiddenPositions([])}
                />
              )}

              {/* Selected for payoff */}
              {selectedPositionsForPayoff.length > 0 && (
                <Chip
                  size="small"
                  label={`🎯 ${selectedPositionsForPayoff.length} for Payoff`}
                  color="primary"
                  variant="outlined"
                />
              )}

              {/* Position Adjustment Button */}
              {positions.length > 0 && !turboMode && (
                <Tooltip title="Adjust positions - Add/close with live payoff preview">
                  <Button
                    size="small"
                    variant="outlined"
                    color="secondary"
                    startIcon={<AdjustIcon />}
                    onClick={() => setAdjustmentPanelOpen(true)}
                    sx={{ fontSize: '0.7rem', py: 0.25 }}
                  >
                    Adjust
                  </Button>
                </Tooltip>
              )}
            </Box>
          </Collapse>

          {/* Expiry Filter Tabs - Multi-Select */}
          {uniqueExpiries.length > 1 && (
            <Box sx={{ mb: 1, display: 'flex', gap: 0.5, flexWrap: 'wrap', alignItems: 'center' }}>
              <Typography variant="caption" color="text.secondary" sx={{ mr: 0.5, fontSize: '0.7rem' }}>
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

          {/* Phase 4: Turbo Mode — compact inline alert */}
          {turboMode && (
            <Alert severity="warning" sx={{ mb: 1, py: 0.25 }} icon={false}>
              <Typography variant="caption" fontWeight="bold">
                ⚡ TURBO — <kbd>↑↓</kbd> Nav • <kbd>B</kbd> Buy • <kbd>S</kbd> Sell • <kbd>C</kbd> Close • <kbd>ESC</kbd> Cancel
              </Typography>
            </Alert>
          )}

          {/* Phase 2: Per-Expiry Max Loss Settings — collapsible */}
          {positions.length > 0 && uniqueExpiries.length > 0 && !turboMode && (
            <Box sx={{ mb: 1 }}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1,
                  cursor: 'pointer',
                  py: 0.5,
                  px: 1,
                  borderRadius: 1,
                  '&:hover': { bgcolor: 'action.hover' },
                }}
                onClick={() => {
                  const next = !expiryMaxLossCollapsed;
                  setExpiryMaxLossCollapsed(next);
                  localStorage.setItem('options_expiry_maxloss_collapsed', JSON.stringify(next));
                }}
              >
                {expiryMaxLossCollapsed ? <ExpandMoreIcon sx={{ fontSize: '1rem' }} /> : <ExpandLessIcon sx={{ fontSize: '1rem' }} />}
                <Typography variant="caption" fontWeight="600" sx={{ fontSize: '0.75rem' }}>
                  🛡️ Per-Expiry Max Loss
                </Typography>
                {expiryMaxLossCollapsed && Object.keys(expiryMaxLossSettings || {}).length > 0 && (
                  <Chip
                    label={`${Object.keys(expiryMaxLossSettings).length} expiries configured`}
                    size="small"
                    variant="outlined"
                    sx={{ height: 18, fontSize: '0.65rem' }}
                  />
                )}
              </Box>
              <Collapse in={!expiryMaxLossCollapsed}>
                <ExpiryMaxLossPanel
                  uniqueExpiries={uniqueExpiries}
                  expiryPnlMap={expiryPnlMap}
                  expiryMaxLossSettings={expiryMaxLossSettings}
                  onSettingsUpdate={handleExpiryMaxLossUpdate}
                />
              </Collapse>
            </Box>
          )}

          {/* Phase 2: Position Scaling Strategy — extracted component */}
          <ScalingStrategyPanel
            scalingStrategy={scalingStrategy}
            setScalingStrategy={setScalingStrategy}
            scalingParams={scalingParams}
            setScalingParams={setScalingParams}
            indexPrices={indexPrices}
            scalingStrategyCollapsed={scalingStrategyCollapsed}
            setScalingStrategyCollapsed={setScalingStrategyCollapsed}
          />

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

          {/* Pending Orders Panel — extracted component */}
          <PendingOrdersPanel
            pendingOrders={pendingOrders}
            pendingOrdersError={pendingOrdersError}
            onCancelOrder={handleCancelPendingOrder}
          />

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

          {/* Phase 3: Sticky Portfolio Summary Strip — extracted component */}
          <PortfolioSummaryStrip
            sortedPositions={sortedPositions}
            aggregatedGreeks={aggregatedGreeks}
            formatPnl={formatPnl}
            getPnlColor={getPnlColor}
          />

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
                    {/* Selection Checkbox - Batch Order Selection (Green/Red) */}
                    <TableCell width="40px" padding="checkbox">
                      <Tooltip title="Select/deselect all for batch orders">
                        <Checkbox
                          checked={
                            sortedPositions.length > 0 &&
                            sortedPositions.every((p) => selectedStrikes[p.product_symbol])
                          }
                          indeterminate={
                            sortedPositions.some((p) => selectedStrikes[p.product_symbol]) &&
                            !sortedPositions.every((p) => selectedStrikes[p.product_symbol])
                          }
                          onChange={(e) => {
                            if (e.target.checked) {
                              const newSelected = {};
                              sortedPositions.forEach((p) => {
                                newSelected[p.product_symbol] = true;
                              });
                              setSelectedStrikes(newSelected);
                            } else {
                              setSelectedStrikes({});
                            }
                          }}
                          sx={{
                            color: '#10b981',
                            '&.Mui-checked': { color: '#10b981' },
                            '&.MuiCheckbox-indeterminate': { color: '#f59e0b' },
                          }}
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
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                          <Tooltip title="Select/deselect all for payoff graph">
                            <Checkbox
                              size="small"
                              checked={
                                sortedPositions.length > 0 &&
                                selectedPositionsForPayoff.length === sortedPositions.length
                              }
                              indeterminate={
                                selectedPositionsForPayoff.length > 0 &&
                                selectedPositionsForPayoff.length < sortedPositions.length
                              }
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setSelectedPositionsForPayoff(sortedPositions.map((p) => p.product_symbol));
                                } else {
                                  setSelectedPositionsForPayoff([]);
                                }
                              }}
                              sx={{
                                color: '#3b82f6',
                                '&.Mui-checked': { color: '#3b82f6' },
                                '&.MuiCheckbox-indeterminate': { color: '#3b82f6' },
                                padding: 0,
                                mr: 0.5,
                              }}
                            />
                          </Tooltip>
                          <Box
                            sx={{ display: 'flex', alignItems: 'center', gap: 0.5, cursor: 'pointer' }}
                            onClick={toggleSymbolSort}
                          >
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
                        </Box>
                      </TableCell>
                    )}
                    {/* Hide/Show column header */}
                    <TableCell align="center" width="50px">
                      <Tooltip title="Show/Hide positions">
                        <Box>
                          <VisibilityIcon sx={{ fontSize: 18, opacity: 0.6 }} />
                        </Box>
                      </Tooltip>
                    </TableCell>
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
                    {visibleColumns.size && (
                      <TableCell
                        align="right"
                        sx={{ cursor: 'pointer', userSelect: 'none' }}
                        onClick={toggleSizeSort}
                      >
                        <Tooltip title="Click to sort by size">
                          <Box
                            sx={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'flex-end',
                              gap: 0.5,
                            }}
                          >
                            Size
                            {sizeSort === 'asc' ? (
                              <ArrowUpwardIcon sx={{ fontSize: 16 }} color="primary" />
                            ) : sizeSort === 'desc' ? (
                              <ArrowDownwardIcon sx={{ fontSize: 16 }} color="primary" />
                            ) : (
                              <UnfoldMoreIcon sx={{ fontSize: 16, opacity: 0.5 }} />
                            )}
                          </Box>
                        </Tooltip>
                      </TableCell>
                    )}
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
                    {visibleColumns.takeProfit && (
                      <TableCell align="center" sx={{ minWidth: 60 }}>
                        <Tooltip title="Take Profit - auto partial exit when profit target reached">
                          <Box>TP</Box>
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
                    {visibleColumns.pop && (
                      <TableCell align="center" sx={{ minWidth: 70 }}>
                        <Tooltip title="Probability of Profit at Expiry">
                          <Box>PoP</Box>
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

                        // Check if this is a closed position (squared off but retained for PnL tracking)
                        const isClosed = pos.is_closed === true || (pos.size === 0 && closedPositions[pos.product_symbol]);

                        // Use backend-calculated cashflow
                        const cashflow = pos.cashflow || 0;

                        const isCall = optionInfo.type === 'Call';
                        const isPut = optionInfo.type === 'Put';

                        // Closed positions use light white/gray background for easy identification
                        const rowBgColor = isClosed
                          ? 'rgba(255, 255, 255, 0.03)' // Light white tint - easily identifiable
                          : isCall
                            ? 'rgba(16, 185, 129, 0.03)'
                            : isPut
                              ? 'rgba(239, 68, 68, 0.03)'
                              : 'transparent';
                        const rowHoverColor = isClosed
                          ? 'rgba(255, 255, 255, 0.06)' // Slightly brighter on hover
                          : isCall
                            ? 'rgba(16, 185, 129, 0.06)'
                            : isPut
                              ? 'rgba(239, 68, 68, 0.06)'
                              : 'action.hover';

                        // Phase 4: Turbo mode selected row highlight (only if actively selected)
                        const isSelectedInTurbo = turboMode && selectedRowIndex >= 0 && index === selectedRowIndex;
                        const finalBgColor = isSelectedInTurbo ? 'rgba(255, 193, 7, 0.2)' : rowBgColor;
                        const finalHoverColor = isSelectedInTurbo ? 'rgba(255, 193, 7, 0.3)' : rowHoverColor;

                        // Common cell style
                        const cellSx = {
                          backgroundColor: `${finalBgColor} !important`,
                          '&:hover': { backgroundColor: `${finalHoverColor} !important` },
                          opacity: isClosed ? 0.7 : 1, // Reduce opacity for closed positions
                          borderLeft: isSelectedInTurbo ? '3px solid #ffc107' : undefined,
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
                                  </Box>
                                </TableCell>

                                {/* Drag Handle - with tooltip to explain persistence */}
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
                                  <Tooltip title="Drag to reorder positions. Your custom order will be saved and persist across page refreshes.">
                                    <DragIcon sx={{ color: 'text.secondary', fontSize: 20 }} />
                                  </Tooltip>
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
                                          selectedPositionsForPayoff.includes(pos.product_symbol)
                                            ? 'Selected for payoff graph'
                                            : 'Click to include in payoff graph'
                                        }
                                      >
                                        <Checkbox
                                          checked={selectedPositionsForPayoff.includes(pos.product_symbol)}
                                          onChange={() => {
                                            setSelectedPositionsForPayoff((prev) =>
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
                                    </Box>
                                  </TableCell>
                                )}

                                {/* Hide/Show Button - between Symbol and Strike */}
                                <TableCell align="center" sx={cellSx} width="50px">
                                  <Tooltip title="Hide from table and payoff graph">
                                    <IconButton
                                      size="small"
                                      onClick={() => {
                                        setHiddenPositions((prev) =>
                                          prev.includes(pos.product_symbol)
                                            ? prev.filter((s) => s !== pos.product_symbol)
                                            : [...prev, pos.product_symbol]
                                        );
                                      }}
                                      sx={{ opacity: 0.7, '&:hover': { opacity: 1 } }}
                                    >
                                      <VisibilityIcon sx={{ fontSize: 18 }} />
                                    </IconButton>
                                  </Tooltip>
                                </TableCell>

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
                                    {isClosed ? (
                                      <Chip
                                        label="CLOSED"
                                        size="small"
                                        sx={{
                                          bgcolor: 'rgba(100, 100, 100, 0.2)',
                                          color: '#888',
                                          fontWeight: 'bold',
                                          fontSize: '0.65rem',
                                        }}
                                      />
                                    ) : (
                                      <Chip
                                        icon={isLong ? <TrendingUp /> : <TrendingDown />}
                                        label={pos.size}
                                        size="small"
                                        sx={{
                                          bgcolor: isLong ? '#10b98120' : '#ef444420',
                                          color: isLong ? '#10b981' : '#ef4444',
                                        }}
                                      />
                                    )}
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

                                {/* Take Profit Indicator */}
                                {visibleColumns.takeProfit && (
                                  <TableCell align="center" sx={cellSx}>
                                    <TakeProfitIndicator
                                      symbol={pos.product_symbol}
                                      currentPnl={pos.unrealized_pnl || 0}
                                      currentSize={Math.abs(pos.size || 0)}
                                      settings={tpSettings[pos.product_symbol]}
                                      onEdit={() => {
                                        setSelectedPositionForTP(pos);
                                        setTpDialogOpen(true);
                                      }}
                                      onUpdate={handleTakeProfitUpdate}
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

                                {/* PoP (Probability of Profit) - Day 1 */}
                                {visibleColumns.pop && (
                                  <TableCell align="center" sx={cellSx}>
                                    {popData[pos.product_symbol] !== undefined ? (
                                      <Chip
                                        label={`${popData[pos.product_symbol].toFixed(1)}%`}
                                        size="small"
                                        sx={{
                                          bgcolor: popData[pos.product_symbol] > 50
                                            ? 'success.main'
                                            : 'warning.main',
                                          color: 'white',
                                          fontWeight: 'bold',
                                          fontSize: '0.75rem',
                                          height: 22,
                                        }}
                                      />
                                    ) : (
                                      <Typography variant="body2" color="text.secondary">
                                        -
                                      </Typography>
                                    )}
                                  </TableCell>
                                )}

                                {/* PnL */}
                                {visibleColumns.pnl && (
                                  <TableCell align="right" sx={cellSx}>
                                    <Box>
                                      <Typography fontWeight="bold" sx={{ color: pnlColor }}>
                                        {formatPnl(pos.unrealized_pnl || 0)}
                                      </Typography>
                                      {isClosed ? (
                                        <Typography variant="caption" sx={{ color: '#888', fontStyle: 'italic' }}>
                                          Realized
                                        </Typography>
                                      ) : (
                                        <Typography variant="caption" sx={{ color: pnlColor }}>
                                          {formatPnlPct(pos.pnl_percentage || 0)}
                                        </Typography>
                                      )}
                                    </Box>
                                  </TableCell>
                                )}

                                {/* Actions */}
                                {visibleColumns.actions && (
                                  <TableCell align="center" sx={cellSx}>
                                    <Box
                                      sx={{
                                        display: 'flex',
                                        gap: 0.5,
                                        justifyContent: 'center',
                                        alignItems: 'center',
                                        minWidth: 180,
                                        flexWrap: 'nowrap',
                                      }}
                                    >
                                      {/* Quick Execute Mode Indicator */}
                                      {isQuickMode && (
                                        <Tooltip
                                          title={`Quick mode: Click C+/P+ to instantly ${skipConfirmStrikes[pos.product_symbol]?.side || 'sell'} ${skipConfirmStrikes[pos.product_symbol]?.size || DEFAULT_SIZE} lots. Click ⚡ to disable.`}
                                        >
                                          <Chip
                                            label={`⚡${skipConfirmStrikes[pos.product_symbol]?.size || DEFAULT_SIZE}`}
                                            size="small"
                                            onClick={() => disableSkipConfirm(pos.product_symbol)}
                                            sx={{
                                              cursor: 'pointer',
                                              bgcolor: '#fbbf24',
                                              color: '#000',
                                              fontWeight: 'bold',
                                              minWidth: 32,
                                              maxHeight: 24,
                                              fontSize: '0.75rem',
                                              '&:hover': {
                                                bgcolor: '#f59e0b',
                                              }
                                            }}
                                          />
                                        </Tooltip>
                                      )}

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
                                          mx: 0.25,
                                        }}
                                      />

                                      {isClosed ? (
                                        /* For closed positions: Show Remove button to remove from tracking */
                                        <Tooltip title="🗑️ Remove from display - This removes the closed position from tracking">
                                          <IconButton
                                            size="medium"
                                            color="default"
                                            onClick={() => {
                                              // Remove from closedPositions
                                              setClosedPositions(prev => {
                                                const updated = { ...prev };
                                                delete updated[pos.product_symbol];
                                                return updated;
                                              });
                                              console.log(`🗑️ Removed closed position: ${pos.product_symbol}`);
                                            }}
                                            sx={{
                                              border: '2px solid',
                                              borderColor: 'text.secondary',
                                              color: 'text.secondary',
                                              '&:hover': {
                                                bgcolor: 'action.hover',
                                                borderColor: 'error.main',
                                                color: 'error.main',
                                              },
                                            }}
                                          >
                                            <CloseIcon fontSize="small" />
                                          </IconButton>
                                        </Tooltip>
                                      ) : (
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
                                      )}
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


          <BatchOrderPanel
            positions={positions}
            selectedStrikes={selectedStrikes}
            status={status}
            orderQuantity={orderQuantity}
            setOrderQuantity={setOrderQuantity}
            multiplierMode={multiplierMode}
            setMultiplierMode={setMultiplierMode}
            executionMode={executionMode}
            setExecutionMode={setExecutionMode}
            batchOrderResults={batchOrderResults}
            setBatchOrderResults={setBatchOrderResults}
            batchExecuting={batchExecuting}
            autoLoopEnabled={autoLoopEnabled}
            setAutoLoopEnabled={setAutoLoopEnabled}
            autoLoopRounds={autoLoopRounds}
            setAutoLoopRounds={setAutoLoopRounds}
            autoLoopRunning={autoLoopRunning}
            autoLoopCurrentRound={autoLoopCurrentRound}
            autoLoopProgress={autoLoopProgress}
            autoLoopError={autoLoopError}
            expiryLoopState={expiryLoopState}
            anyExpiryLoopRunning={anyExpiryLoopRunning}
            selectedExpiriesForLoop={selectedExpiriesForLoop}
            batchConfirmDialog={batchConfirmDialog}
            setBatchConfirmDialog={setBatchConfirmDialog}
            pendingBatchOrders={pendingBatchOrders}
            setPendingBatchOrders={setPendingBatchOrders}
            getSelectedPositions={getSelectedPositions}
            getPositionsGCD={getPositionsGCD}
            calculateBatchOrders={calculateBatchOrders}
            executeBatchOrders={executeBatchOrders}
            executeBatch={executeBatch}
            executeAutoLoop={executeAutoLoop}
            stopAutoLoop={stopAutoLoop}
            startAllExpiryLoops={startAllExpiryLoops}
            executeExpiryAutoLoop={executeExpiryAutoLoop}
            stopExpiryAutoLoop={stopExpiryAutoLoop}
            clearAutoLoopError={clearAutoLoopError}
            clearExpiryLoopError={clearExpiryLoopError}
          />

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

              {/* Greeks Summary - Only for visible positions - COMPACT */}
              {aggregatedGreeks.count > 0 && (
                <Box sx={{ mt: 1.5, p: 1.5, bgcolor: 'action.hover', borderRadius: 1 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                    <Typography variant="caption" color="text.secondary" fontWeight="bold">
                      Portfolio Greeks ({sortedPositions.length} visible positions)
                    </Typography>
                    {/* Delta Neutral / High Delta Badge - Inline */}
                    {Math.abs(aggregatedGreeks.delta) < 0.1 && (
                      <Chip
                        label="Delta Neutral ✅"
                        size="small"
                        color="info"
                        sx={{ height: 18, fontSize: '0.65rem' }}
                      />
                    )}
                    {Math.abs(aggregatedGreeks.delta) > 10 && (
                      <Chip
                        label="High Delta ⚠️"
                        size="small"
                        color="warning"
                        sx={{ height: 18, fontSize: '0.65rem' }}
                      />
                    )}
                  </Box>

                  {/* Futures Equivalent & Greeks in single row */}
                  <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
                    {/* Futures Equivalent - Compact */}
                    {(aggregatedGreeks.btcDelta !== 0 || aggregatedGreeks.ethDelta !== 0) && (
                      <>
                        <Typography variant="caption" color="text.secondary" sx={{ mr: -1 }}>
                          Futures Equiv:
                        </Typography>
                        {aggregatedGreeks.btcDelta !== 0 && (
                          <Tooltip
                            title={`Your BTC options have the same directional exposure as ${Math.abs(Number(aggregatedGreeks.btcDelta) || 0).toFixed(4)} BTC futures contracts`}
                          >
                            <Chip
                              size="small"
                              label={`${aggregatedGreeks.btcDelta >= 0 ? 'Long' : 'Short'} ${Math.abs(Number(aggregatedGreeks.btcDelta) || 0).toFixed(4)} BTC`}
                              icon={aggregatedGreeks.btcDelta >= 0 ? <TrendingUp sx={{ fontSize: 14 }} /> : <TrendingDown sx={{ fontSize: 14 }} />}
                              sx={{
                                height: 22,
                                bgcolor: aggregatedGreeks.btcDelta >= 0 ? '#10b98120' : '#ef444420',
                                color: aggregatedGreeks.btcDelta >= 0 ? '#10b981' : '#ef4444',
                                fontWeight: 'bold',
                                fontSize: '0.7rem'
                              }}
                            />
                          </Tooltip>
                        )}
                        {aggregatedGreeks.ethDelta !== 0 && (
                          <Tooltip
                            title={`Your ETH options have the same directional exposure as ${Math.abs(Number(aggregatedGreeks.ethDelta) || 0).toFixed(4)} ETH futures contracts`}
                          >
                            <Chip
                              size="small"
                              label={`${aggregatedGreeks.ethDelta >= 0 ? 'Long' : 'Short'} ${Math.abs(Number(aggregatedGreeks.ethDelta) || 0).toFixed(4)} ETH`}
                              icon={aggregatedGreeks.ethDelta >= 0 ? <TrendingUp sx={{ fontSize: 14 }} /> : <TrendingDown sx={{ fontSize: 14 }} />}
                              sx={{
                                height: 22,
                                bgcolor: aggregatedGreeks.ethDelta >= 0 ? '#10b98120' : '#ef444420',
                                color: aggregatedGreeks.ethDelta >= 0 ? '#10b981' : '#ef4444',
                                fontWeight: 'bold',
                                fontSize: '0.7rem'
                              }}
                            />
                          </Tooltip>
                        )}
                        <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />
                      </>
                    )}

                    {/* Greek Values - Compact */}
                    <Tooltip title="Portfolio delta - sensitivity to underlying price change">
                      <Box sx={{ display: 'inline-flex', alignItems: 'baseline', gap: 0.5 }}>
                        <Typography variant="caption" color="text.secondary">Delta:</Typography>
                        <Typography
                          variant="caption"
                          fontWeight="bold"
                          sx={{ color: (Number(aggregatedGreeks.delta) || 0) >= 0 ? '#10b981' : '#ef4444' }}
                        >
                          {(Number(aggregatedGreeks.delta) || 0) >= 0 ? '+' : ''}{(Number(aggregatedGreeks.delta) || 0).toFixed(4)}
                        </Typography>
                      </Box>
                    </Tooltip>
                    <Tooltip title="Portfolio gamma - rate of delta change">
                      <Box sx={{ display: 'inline-flex', alignItems: 'baseline', gap: 0.5 }}>
                        <Typography variant="caption" color="text.secondary">Gamma:</Typography>
                        <Typography variant="caption" fontWeight="bold">
                          {(Number(aggregatedGreeks.gamma) || 0).toFixed(6)}
                        </Typography>
                      </Box>
                    </Tooltip>
                    <Tooltip title="Portfolio theta - daily time decay (P&L change per day)">
                      <Box sx={{ display: 'inline-flex', alignItems: 'baseline', gap: 0.5 }}>
                        <Typography variant="caption" color="text.secondary">Theta:</Typography>
                        <Typography
                          variant="caption"
                          fontWeight="bold"
                          sx={{ color: (Number(aggregatedGreeks.theta) || 0) >= 0 ? '#10b981' : '#ef4444' }}
                        >
                          {(Number(aggregatedGreeks.theta) || 0) >= 0 ? '+' : ''}{(Number(aggregatedGreeks.theta) || 0).toFixed(2)}
                        </Typography>
                      </Box>
                    </Tooltip>
                    <Tooltip title="Portfolio vega - sensitivity to 1% IV change">
                      <Box sx={{ display: 'inline-flex', alignItems: 'baseline', gap: 0.5 }}>
                        <Typography variant="caption" color="text.secondary">Vega:</Typography>
                        <Typography variant="caption" fontWeight="bold">
                          {(Number(aggregatedGreeks.vega) || 0).toFixed(2)}
                        </Typography>
                      </Box>
                    </Tooltip>
                  </Box>
                </Box>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Payoff Diagram */}
      {positions.length > 0 && !turboMode && (
        <Box sx={{ mt: 2 }}>
          <Suspense fallback={<Box sx={{ p: 2, textAlign: 'center' }}>Loading payoff diagram...</Box>}>
            <OptionsPayoffDiagram
              positions={sortedPositions}
              selectedPositions={selectedPositionsForPayoff}
              futuresPositions={visibleFuturesPositions}
            />
          </Suspense>
        </Box>
      )}

      {/* Options Trading Activity Monitor */}
      {!turboMode && (
        <Box sx={{ mt: 2 }}>
          <Suspense fallback={<Box sx={{ p: 2, textAlign: 'center' }}>Loading activity panel...</Box>}>
            <OptionsActivityPanel refreshTrigger={0} />
          </Suspense>
        </Box>
      )}

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

      <AddPositionDialog
        addDialog={addDialog}
        setAddDialog={setAddDialog}
        onSubmit={confirmAddWithSkip}
        submittingOrder={submittingOrder}
        lastUsedSize={lastUsedSize}
        skipConfirmStrikes={skipConfirmStrikes}
      />


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

      {/* Take Profit Configuration Dialog */}
      <TakeProfitDialog
        open={tpDialogOpen}
        onClose={() => {
          setTpDialogOpen(false);
          setSelectedPositionForTP(null);
        }}
        position={selectedPositionForTP}
        settings={selectedPositionForTP ? tpSettings[selectedPositionForTP.product_symbol] : null}
        onUpdate={handleTakeProfitUpdate}
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

      {/* Position Adjustment Page (FEB 1, 2026 - Sensibull-like full page layout) */}
      {/* FEB 2, 2026: Now uses filteredPositionsForAdjustment based on expiry/strike selection */}
      <SensibullStyleAdjustmentPage
        open={adjustmentPanelOpen}
        onClose={() => setAdjustmentPanelOpen(false)}
        currentPositions={filteredPositionsForAdjustment}
        spotPrice={btcPrice || ethPrice}
        underlying={filteredPositionsForAdjustment[0]?.product_symbol?.split('-')[1] || positions[0]?.product_symbol?.split('-')[1] || 'BTC'}
        onExecuteComplete={() => {
          setAdjustmentPanelOpen(false);
          handleRefresh();
        }}
      />
    </motion.div>
  );
};

export default OptionsPanel;
