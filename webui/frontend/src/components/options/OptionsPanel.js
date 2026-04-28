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
import useVisibilityAwarePolling from '../../hooks/useVisibilityAwarePolling';
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
  ClickAwayListener,
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
  EditNote as EditNoteIcon,
  StickyNote2 as StickyNote2Icon,
} from '@mui/icons-material';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  useDroppable,
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
import OptionsPositionsPropDeskHeader from './OptionsPositionsPropDeskHeader';
import AddPositionDialog from './AddPositionDialog';
import BatchOrderPanel from './BatchOrderPanel';
import ConditionalExitPanel from './ConditionalExitPanel';
import { AutomationButton, automationMonitor, notificationService } from './automation';
import SLTPDialog from './SLTPDialog';
import SLTPIndicator from './SLTPIndicator';
import MaxLossIndicator from './MaxLossIndicator';
import TakeProfitIndicator from './TakeProfitIndicator';
import TakeProfitDialog from './TakeProfitDialog';
import ExpiryMaxLossPanel from './ExpiryMaxLossPanel';
import useMarketPrices from '../../hooks/useMarketPrices';
import usePersistedState from '../../hooks/usePersistedState';
import useGroupsAPI from '../../hooks/useGroupsAPI';
import useOptionsPositions from '../../hooks/useOptionsPositions';
import useOptionsSettings from '../../hooks/useOptionsSettings';
import usePositionGreeks from '../../hooks/usePositionGreeks';
import useIVStats from '../../hooks/useIVStats';
import SoundSettingsPanel from '../SoundSettingsPanel';
// JAN 17, 2026: Futures panel - separate file structure, minimal invasion
import FuturesPanel from '../futures/FuturesPanel';
// JAN 23, 2026: Day 1 & 2 utilities for PoP calculation
import { calculatePoP } from '../../utils/probabilityCalc';
import { RISK_FREE_RATE, getContractMultiplier } from '../../utils/constants';
// JAN 31, 2026: Position Adjustment Panel - Sensibull-like position adjustment system
// FEB 1, 2026: Updated to use SensibullStyleAdjustmentPage (full page layout)
import { SensibullStyleAdjustmentPage } from '../positionAdjustment';
import PayoffErrorBoundary from './PayoffErrorBoundary';
// ARCH-2: Extracted sub-components to reduce monolith size and enable per-component React.memo
import PositionRow from './PositionRow';
import PortfolioGreeksSummary from './PortfolioGreeksSummary';
import HedgeDeltaModal from './HedgeDeltaModal';
import PnLAttributionPanel from './PnLAttributionPanel';
import VolTermStructurePanel from './VolTermStructurePanel';
import VolSmilePanel from './VolSmilePanel';
import RollManagerModal from './RollManagerModal';
import AutoLoopBanner from './AutoLoopBanner';
import ClosePositionDialog from './ClosePositionDialog';

// Phase 3: Lazy load heavy components
const OptionsPayoffDiagram = lazy(() => import('./OptionsPayoffDiagram'));
const OptionsActivityPanel = lazy(() => import('./OptionsActivityPanel'));

// ============================================================================
// DEV-ONLY LOGGER — silenced in production for performance
// ============================================================================
const isDev = process.env.NODE_ENV !== 'production';
const devLog = isDev ? console.log.bind(console) : () => { };
const devWarn = isDev ? console.warn.bind(console) : () => { };

// ============================================================================
// PHASE 1 OPTIMIZATION: React.memo for SortableRow
// Prevents unnecessary re-renders when position data hasn't changed
// ============================================================================

// ============================================================================
// PURE UTILITY FUNCTIONS (hoisted outside component for stable references)
// ============================================================================

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

const formatUsd = (value) => {
  const num = Number(value) || 0;
  if (num >= 1000 || num <= -1000) {
    return '$' + num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  return '$' + num.toFixed(2);
};

const getPnlColor = (pnl) => {
  if (pnl > 0) return '#10b981';
  if (pnl < 0) return '#ef4444';
  return '#94a3b8';
};

const getPositionType = (symbol) => {
  if (symbol.startsWith('C-')) return { type: 'CALL', color: '#3b82f6' };
  if (symbol.startsWith('P-')) return { type: 'PUT', color: '#a855f7' };
  if (symbol.startsWith('MV-')) return { type: 'MV STRADDLE', color: '#00bcd4' };
  return { type: 'UNKNOWN', color: '#6b7280' };
};

const parseOptionSymbol = (symbol) => {
  if (symbol.startsWith('MV-')) {
    const parts = symbol.split('-');
    if (parts.length >= 4) {
      const underlying = parts[1];
      const strike = parseInt(parts[2]);
      const expiry = parts[3];
      const day = expiry.substring(0, 2);
      const month = expiry.substring(2, 4);
      const year = '20' + expiry.substring(4, 6);
      return { type: 'MV Straddle', underlying, strike, expiry: `${day}/${month}/${year}` };
    }
  }
  const parts = symbol.split('-');
  if (parts.length >= 4) {
    const optionType = parts[0];
    const rawUnderlying = parts[1];
    // Display BTC for Call options, BTP for Put options (C = Call, P = Put)
    // This avoids confusion where "C" in BTC could be misread as "Call"
    const underlying = rawUnderlying === 'BTC'
      ? (optionType === 'C' ? 'BTC' : 'BTP')
      : rawUnderlying;
    const strike = parseInt(parts[2]);
    const expiry = parts[3];
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

// Prefix for group-header dnd IDs — distinguishes them from position symbol IDs
const GROUP_DROP_PREFIX = '__GROUP__';
const UNGROUPED_DROP_ID = `${GROUP_DROP_PREFIX}UNGROUPED`;

// SortableGroupHeader — full drag+drop for named groups.
// The group header itself is sortable (grab the ⠿ grip to reorder groups).
// It is also a drop target so individual positions can be dropped onto it.
const SortableGroupHeader = React.memo(({ groupId, color, children }) => {
  const id = `${GROUP_DROP_PREFIX}${groupId}`;
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
    isOver,
  } = useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    zIndex: isDragging ? 1001 : 'auto',
  };

  return (
    <TableRow
      ref={setNodeRef}
      style={style}
      sx={{
        outline: isOver && !isDragging ? `2px dashed ${color || '#888'}` : 'none',
        outlineOffset: -2,
        transition: 'outline 0.1s, background 0.1s',
        bgcolor: isOver && !isDragging ? `${color || '#888'}22` : undefined,
      }}
    >
      {/* children receives the drag handle attrs/listeners so the grip icon
          inside the header can initiate group-level drag */}
      {children(attributes, listeners)}
    </TableRow>
  );
});

// DroppableGroupHeader — only used for the "Ungrouped" section footer
// (cannot be reordered, only acts as a drop zone to remove a position from its group)
const DroppableGroupHeader = React.memo(({ groupId, color, children }) => {
  const id = groupId ? `${GROUP_DROP_PREFIX}${groupId}` : UNGROUPED_DROP_ID;
  const { setNodeRef, isOver } = useDroppable({ id });
  return (
    <TableRow
      ref={setNodeRef}
      sx={{
        outline: isOver ? `2px dashed ${color || '#888'}` : 'none',
        outlineOffset: -2,
        transition: 'outline 0.1s',
        bgcolor: isOver ? `${color || '#888'}1A` : undefined,
      }}
    >
      {children}
    </TableRow>
  );
});

// ============================================================================
// MANUAL PNL BADGE — Display-only PnL offset for payoff graph
// ============================================================================
function ManualPnLBadge({ value, onChange }) {
  const [open, setOpen] = useState(false);
  const [inputVal, setInputVal] = useState('');

  const handleOpen = () => {
    setInputVal(value === 0 ? '' : String(value));
    setOpen(true);
  };

  const handleApply = () => {
    const parsed = parseFloat(inputVal);
    onChange(isNaN(parsed) ? 0 : parsed);
    setOpen(false);
  };

  const handleClear = () => {
    onChange(0);
    setOpen(false);
  };

  const color = value > 0 ? '#10b981' : value < 0 ? '#ef4444' : '#94a3b8';
  const label = value === 0
    ? '✏️ Manual PnL'
    : `✏️ ${value > 0 ? '+' : ''}$${Math.abs(value).toFixed(2)}`;

  return (
    <Box sx={{ position: 'relative', display: 'inline-flex' }}>
      <Chip
        label={label}
        size="small"
        onClick={handleOpen}
        sx={{
          fontWeight: 'bold',
          bgcolor: `${color}20`,
          color,
          cursor: 'pointer',
          border: `1px solid ${color}40`,
          '&:hover': { bgcolor: `${color}35` },
        }}
      />
      {open && (
        <ClickAwayListener onClickAway={() => setOpen(false)}>
          <Paper
            elevation={8}
            sx={{
              position: 'absolute',
              top: '110%',
              left: 0,
              zIndex: 1300,
              p: 1.5,
              minWidth: 240,
              bgcolor: 'background.paper',
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 1.5,
            }}
          >
            <Typography variant="caption" sx={{ display: 'block', mb: 0.5, fontWeight: 600 }}>
              Manual PnL Offset
            </Typography>
            <TextField
              size="small"
              fullWidth
              type="number"
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              placeholder="e.g. +20.00"
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleApply();
                if (e.key === 'Escape') setOpen(false);
              }}
              autoFocus
              sx={{ mb: 0.75 }}
            />
            <Typography variant="caption" sx={{ display: 'block', mb: 1, color: 'text.secondary', fontSize: '0.7rem' }}>
              Realized PnL from squared-off positions. Shifts payoff graph up/down without changing its shape.
            </Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button size="small" variant="contained" onClick={handleApply} sx={{ flex: 1 }}>Apply</Button>
              <Button size="small" variant="outlined" onClick={handleClear} sx={{ flex: 1 }}>Clear</Button>
            </Box>
          </Paper>
        </ClickAwayListener>
      )}
    </Box>
  );
}

const OptionsPanel = () => {
  // Polling interval (default 5s)
  const [pollInterval, setPollInterval] = usePersistedState('options_poll_interval', 5000, { parse: 'int' });

  // ---- Data layer (positions, status, fetchers, polling, WebSocket) ----
  const {
    positions, setPositions,
    futuresPositions, visibleFuturesPositions,
    status,
    loading, refreshing,
    error, setError,
    pendingOrders, pendingOrdersError,
    fetchDashboard, fetchStatus, fetchPositions, fetchFuturesPositions, fetchPendingOrders,
    handleCancelPendingOrder, handleRefresh,
    hasPositionsRef, activeIntervalsRef,
    marginData, lastDataUpdate,
    feesMap,
  } = useOptionsPositions({ pollInterval });

  // Phase 2: Secondary toolbar visibility (persisted)
  const [secondaryToolbarOpen, setSecondaryToolbarOpen] = usePersistedState('options_secondary_toolbar_open', false);
  // Phase 2: Scaling strategy section collapsed (persisted)
  const [scalingStrategyCollapsed, setScalingStrategyCollapsed] = usePersistedState('options_scaling_strategy_collapsed', true);
  // Phase 2: Expiry max loss section collapsed (persisted)
  const [expiryMaxLossCollapsed, setExpiryMaxLossCollapsed] = usePersistedState('options_expiry_maxloss_collapsed', true);
  // Focus mode: hidden positions (persisted)
  const [hiddenPositions, setHiddenPositions] = usePersistedState('options_hidden_positions', []);
  // Selected positions for payoff diagram (whitelist approach - default: none selected)
  const [selectedPositionsForPayoff, setSelectedPositionsForPayoff] = usePersistedState('options_selected_positions_payoff', []);

  // Closed positions storage - keeps squared off positions visible with size=0 and their final PnL
  // Format: { symbol: { product_symbol, realized_pnl, closed_at, entry_price, close_price, original_size } }
  const [closedPositions, setClosedPositions] = usePersistedState('options_closed_positions', {});

  // Positions the user explicitly dismissed via the X button.
  // Non-persisted: resets on page reload (positions are gone from API by then anyway).
  // Also checked in disappearance-detection to prevent re-adding dismissed symbols.
  const dismissedRef = useRef(new Set());
  const [dismissedSymbols, setDismissedSymbols] = useState(() => new Set());

  // Partial exit realized PnL tracking - accumulates PnL from partial position reductions
  // Format: { symbol: { realized_pnl: number, history: [{ size_reduced, pnl, price, timestamp }] } }
  // When you reduce a position (e.g., from -300 to -150), the PnL from the closed portion is locked in here.
  // This ensures partial exits don't "disappear" from PnL and payoff graph.
  const [partialRealizedPnl, setPartialRealizedPnl] = usePersistedState('options_partial_realized_pnl', {});

  // Manual PnL offset — display-only realized PnL from squared-off positions (persisted via localStorage)
  const [manualPnL, setManualPnL] = useState(() =>
    parseFloat(localStorage.getItem('ssrbot_manual_pnl') || '0')
  );
  useEffect(() => {
    localStorage.setItem('ssrbot_manual_pnl', String(manualPnL));
  }, [manualPnL]);

  // Day 1: Probability of Profit (PoP) data
  const [popData, setPopData] = useState({}); // Map of symbol -> PoP percentage

  // Phase 4: Turbo Mode for expiry day ultra-fast trading
  const [turboMode, setTurboMode] = usePersistedState('options_turbo_mode', false, { parse: 'bool-string' });

  // Phase 4: Keyboard trading - selected row index (-1 = no selection until arrow keys used)
  const [selectedRowIndex, setSelectedRowIndex] = useState(-1);

  // Expiry filter (persisted) - now supports multiple selection
  const [selectedExpiries, setSelectedExpiries] = usePersistedState('options_selected_expiries', []);

  // Sort state
  const [symbolSort, setSymbolSort] = useState(null); // null = no sort, 'grouped' = CE/PE grouped
  const [strikeSort, setStrikeSort] = useState(null); // null = no sort, 'asc' = ascending, 'desc' = descending
  const [sizeSort, setSizeSort] = useState(null); // null = no sort, 'asc' = ascending, 'desc' = descending

  // ── Position Groups (manual labelling) ───────────────────────────────────
  // Groups, collapsed state, and custom order are ALL scoped per expiry.
  // Master storage: { [expiryKey]: { groups: {}, collapsed: {}, order: [] } }
  // expiryKey = sorted expiry codes joined by '|', or 'ALL' when no filter.
  const GROUP_PALETTE = ['#7c3aed', '#0891b2', '#0d9488', '#d97706', '#dc2626', '#db2777', '#65a30d', '#ea580c'];

  // Color palettes for different group types
  const CALL_PALETTE = ['#16a34a', '#15803d', '#166534', '#4ade80', '#86efac'];
  const PUT_PALETTE = ['#dc2626', '#b91c1c', '#991b1b', '#f87171', '#fca5a5'];
  const MIXED_PALETTE = ['#7c3aed', '#0891b2', '#0d9488', '#d97706', '#db2777']; // neutral colors

  // Determine if a group is CALL-dominant, PUT-dominant, or MIXED based on its symbols
  const getGroupType = useCallback((symbols) => {
    if (!symbols || symbols.length === 0) return 'MIXED';

    let callCount = 0;
    let putCount = 0;

    symbols.forEach((symbol) => {
      if (symbol.startsWith('C-')) callCount++;
      else if (symbol.startsWith('P-')) putCount++;
    });

    // If all are calls, return 'CALL'
    if (putCount === 0 && callCount > 0) return 'CALL';
    // If all are puts, return 'PUT'
    if (callCount === 0 && putCount > 0) return 'PUT';
    // Otherwise it's mixed
    return 'MIXED';
  }, []);

  // Get the appropriate color for a group based on its type
  const getGroupColor = useCallback((groupType, typeCountInExpiry) => {
    const typeIndex = typeCountInExpiry || 0;

    if (groupType === 'CALL') {
      return CALL_PALETTE[typeIndex % CALL_PALETTE.length];
    } else if (groupType === 'PUT') {
      return PUT_PALETTE[typeIndex % PUT_PALETTE.length];
    } else {
      return MIXED_PALETTE[typeIndex % MIXED_PALETTE.length];
    }
  }, [CALL_PALETTE, PUT_PALETTE, MIXED_PALETTE]);

  // Single master persisted object for all expiry group data — SERVER-SIDE STORAGE
  // Groups are stored in SQLite on the backend and will NEVER disappear unless user deletes them.
  // On first load, any existing localStorage data is automatically migrated to the server.
  const {
    allExpiryGroupData, setAllExpiryGroupData,
    loaded: groupsLoaded,
    createGroupOnServer, deleteGroupOnServer,
    assignSymbolOnServer, updateGroupOnServer, updateMetaOnServer,
  } = useGroupsAPI();

  // The current expiry key (derived from selectedExpiries, or 'ALL' when no filter).
  const expiryGroupKey = useMemo(() => {
    if (!selectedExpiries || selectedExpiries.length === 0) return 'ALL';
    return [...selectedExpiries].sort().join('|');
  }, [selectedExpiries]);

  // Active slice for the current expiry.
  // When expiryGroupKey is 'ALL' (no filter applied) and there is no data stored directly under
  // 'ALL', build a merged view from individual per-expiry scopes whose groups contain symbols
  // that are currently visible. This keeps groups visible even when the expiry filter is cleared.
  const activeExpiryData = useMemo(() => {
    const direct = allExpiryGroupData[expiryGroupKey];
    if (direct) return direct;

    if (expiryGroupKey === 'ALL') {
      const visibleSymbols = new Set(positions.map((p) => p.product_symbol));
      const merged = { groups: {}, collapsed: {}, order: [], groupOrder: [] };
      let hadAny = false;
      Object.entries(allExpiryGroupData).forEach(([key, slice]) => {
        if (key.includes('|') || key === 'ALL') return; // skip composite/ALL keys
        const groups = slice.groups || {};
        const hasVisible = Object.values(groups).some((g) =>
          (g.symbols || []).some((s) => visibleSymbols.has(s))
        );
        if (hasVisible) {
          hadAny = true;
          Object.assign(merged.groups, groups);
          Object.assign(merged.collapsed, slice.collapsed || {});
          (slice.groupOrder || []).forEach((id) => {
            if (!merged.groupOrder.includes(id)) merged.groupOrder.push(id);
          });
        }
      });
      if (hadAny) return merged;
    }

    return { groups: {}, collapsed: {}, order: [], groupOrder: [] };
  }, [allExpiryGroupData, expiryGroupKey, positions]);

  // In 'ALL' merged mode, groups live under their original expiry keys, not under 'ALL'.
  // This helper finds the actual storage key for a group so write operations target the right key.
  const getGroupActualKey = useCallback((groupId) => {
    if (expiryGroupKey !== 'ALL') return expiryGroupKey;
    for (const [key, slice] of Object.entries(allExpiryGroupData)) {
      if (key.includes('|') || key === 'ALL') continue;
      if (slice.groups && slice.groups[groupId]) return key;
    }
    return 'ALL'; // new group created in ALL mode goes to ALL scope
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expiryGroupKey, allExpiryGroupData]);

  // Derived per-expiry state (read)
  const positionGroups = activeExpiryData.groups || {};
  const collapsedGroups = activeExpiryData.collapsed || {};
  const customOrder = activeExpiryData.order || [];
  // groupOrder: array of group IDs controlling the display order of groups
  const rawGroupOrder = activeExpiryData.groupOrder || [];
  const groupOrder = useMemo(() => {
    const allGroupIds = Object.keys(positionGroups);
    // Start with persisted order, append any new groups not yet in it
    const known = rawGroupOrder.filter((id) => positionGroups[id]);
    const unseen = allGroupIds.filter((id) => !known.includes(id));
    return [...known, ...unseen];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [positionGroups, rawGroupOrder]);

  // Setters that write into the correct expiry slice
  const setPositionGroups = useCallback((updater) => {
    setAllExpiryGroupData((prev) => {
      const key = expiryGroupKey;
      const slice = prev[key] || { groups: {}, collapsed: {}, order: [] };
      const nextGroups = typeof updater === 'function' ? updater(slice.groups || {}) : updater;
      return { ...prev, [key]: { ...slice, groups: nextGroups } };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expiryGroupKey]);

  const setCollapsedGroups = useCallback((updater) => {
    setAllExpiryGroupData((prev) => {
      const key = expiryGroupKey;
      const slice = prev[key] || { groups: {}, collapsed: {}, order: [] };
      const nextCollapsed = typeof updater === 'function' ? updater(slice.collapsed || {}) : updater;
      return { ...prev, [key]: { ...slice, collapsed: nextCollapsed } };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expiryGroupKey]);

  // customOrder needs setCustomOrder + saveCustomOrderNow (immediate-save variant)
  const setCustomOrder = useCallback((updater) => {
    setAllExpiryGroupData((prev) => {
      const key = expiryGroupKey;
      const slice = prev[key] || { groups: {}, collapsed: {}, order: [] };
      const nextOrder = typeof updater === 'function' ? updater(slice.order || []) : updater;
      return { ...prev, [key]: { ...slice, order: nextOrder } };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expiryGroupKey]);

  // saveCustomOrderNow: for the per-expiry approach the write is already synchronous
  // (usePersistedState debouncing is handled inside the hook). We expose a no-op-compatible
  // wrapper that accepts the new order and writes it immediately via setAllExpiryGroupData.
  const saveCustomOrderNow = useCallback((newOrder) => {
    // Persist position order to server
    updateMetaOnServer(expiryGroupKey, { order: newOrder });
    setAllExpiryGroupData((prev) => {
      const key = expiryGroupKey;
      const slice = prev[key] || { groups: {}, collapsed: {}, order: [] };
      return { ...prev, [key]: { ...slice, order: newOrder } };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expiryGroupKey, updateMetaOnServer]);

  // setGroupOrder — persists the group display order for the current expiry
  const setGroupOrder = useCallback((updater) => {
    setAllExpiryGroupData((prev) => {
      const key = expiryGroupKey;
      const slice = prev[key] || { groups: {}, collapsed: {}, order: [], groupOrder: [] };
      const nextGroupOrder = typeof updater === 'function' ? updater(slice.groupOrder || []) : updater;
      // Persist group order to server
      updateMetaOnServer(key, { group_order: nextGroupOrder });
      return { ...prev, [key]: { ...slice, groupOrder: nextGroupOrder } };
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expiryGroupKey, updateMetaOnServer]);

  const [newGroupName, setNewGroupName] = useState('');
  // Right-click / tag-button context menu
  const [groupMenuAnchor, setGroupMenuAnchor] = useState(null); // { mouseX, mouseY, symbol }

  // Create a new group — uses setAllExpiryGroupData directly to avoid stale closure on expiryGroupKey
  const handleCreateGroup = useCallback((name) => {
    if (!name.trim()) return;
    const id = Date.now().toString();
    const trimmedName = name.trim();
    setAllExpiryGroupData((prev) => {
      const slice = prev[expiryGroupKey] || { groups: {}, collapsed: {}, order: [], groupOrder: [] };
      // New groups start empty, so they're MIXED type. We use MIXED_PALETTE for new groups.
      // However, once positions are added, the color will be recalculated based on their type.
      const existingGroups = slice.groups || {};
      // Count existing MIXED groups to get the right index in the palette
      let mixedCount = 0;
      Object.values(existingGroups).forEach((g) => {
        const type = getGroupType(g.symbols);
        if (type === 'MIXED') mixedCount++;
      });
      const color = getGroupColor('MIXED', mixedCount);
      const existingOrder = slice.groupOrder || Object.keys(existingGroups);
      // Also persist to server via targeted API
      createGroupOnServer(expiryGroupKey, id, trimmedName, color);
      return {
        ...prev,
        [expiryGroupKey]: {
          ...slice,
          groups: { ...existingGroups, [id]: { name: trimmedName, color, symbols: [] } },
          groupOrder: [...existingOrder, id], // append new group at the end
        },
      };
    });
  }, [expiryGroupKey, createGroupOnServer, getGroupType, getGroupColor]); // eslint-disable-line react-hooks/exhaustive-deps

  // Delete a group (positions become ungrouped) — also removes from groupOrder
  const handleDeleteGroup = useCallback((groupId) => {
    const actualKey = getGroupActualKey(groupId);
    deleteGroupOnServer(actualKey, groupId);
    setAllExpiryGroupData((prev) => {
      const slice = prev[actualKey] || { groups: {}, collapsed: {}, order: [], groupOrder: [] };
      const nextGroups = { ...(slice.groups || {}) };
      delete nextGroups[groupId];
      const nextGroupOrder = (slice.groupOrder || []).filter((id) => id !== groupId);
      return { ...prev, [actualKey]: { ...slice, groups: nextGroups, groupOrder: nextGroupOrder } };
    });
  }, [getGroupActualKey, deleteGroupOnServer]); // eslint-disable-line react-hooks/exhaustive-deps

  // Assign a position symbol to a group (removes from any previous group first)
  const handleAssignToGroup = useCallback((symbol, groupId) => {
    // In merged-ALL mode, find the actual key for the target group (or source group if unassigning)
    const actualKey = groupId ? getGroupActualKey(groupId) : getGroupActualKey(
      Object.keys(positionGroups).find((id) => (positionGroups[id]?.symbols || []).includes(symbol)) || ''
    );
    const keyToUse = actualKey || expiryGroupKey;
    assignSymbolOnServer(keyToUse, symbol, groupId || null);
    setAllExpiryGroupData((prev) => {
      const slice = prev[keyToUse] || { groups: {}, collapsed: {}, order: [] };
      const prevGroups = slice.groups || {};

      // PASS 1: Update symbols in all groups
      const groupsWithUpdatedSymbols = {};
      for (const [id, g] of Object.entries(prevGroups)) {
        const newSymbols = g.symbols.filter((s) => s !== symbol);
        groupsWithUpdatedSymbols[id] = { ...g, symbols: newSymbols };
      }

      // Add symbol to target group if specified
      if (groupId && groupsWithUpdatedSymbols[groupId]) {
        const newSymbols = [...groupsWithUpdatedSymbols[groupId].symbols, symbol];
        groupsWithUpdatedSymbols[groupId] = { ...groupsWithUpdatedSymbols[groupId], symbols: newSymbols };
      }

      // PASS 2: Recalculate colors based on final symbol sets
      const next = {};
      for (const [id, g] of Object.entries(groupsWithUpdatedSymbols)) {
        const type = getGroupType(g.symbols);

        // Count how many groups of the same type exist (excluding current)
        let typeCount = 0;
        Object.entries(groupsWithUpdatedSymbols).forEach(([otherId, otherGroup]) => {
          if (otherId !== id) {
            const otherType = getGroupType(otherGroup.symbols);
            if (otherType === type) typeCount++;
          }
        });

        const color = getGroupColor(type, typeCount);
        next[id] = { ...g, color };
      }

      return { ...prev, [keyToUse]: { ...slice, groups: next } };
    });
  }, [expiryGroupKey, getGroupActualKey, positionGroups, assignSymbolOnServer, getGroupType, getGroupColor]); // eslint-disable-line react-hooks/exhaustive-deps

  // Get the groupId a symbol belongs to (or null)
  const getSymbolGroup = useCallback((symbol) => {
    for (const [id, g] of Object.entries(positionGroups)) {
      if (g.symbols.includes(symbol)) return id;
    }
    return null;
  }, [positionGroups]);

  // Toggle collapse for a group
  const toggleGroupCollapse = useCallback((groupId) => {
    const actualKey = getGroupActualKey(groupId);
    setAllExpiryGroupData((prev) => {
      const slice = prev[actualKey] || { groups: {}, collapsed: {}, order: [] };
      const prevCollapsed = slice.collapsed || {};
      const nextCollapsed = { ...prevCollapsed, [groupId]: !prevCollapsed[groupId] };
      updateMetaOnServer(actualKey, { collapsed: nextCollapsed });
      return {
        ...prev,
        [actualKey]: { ...slice, collapsed: nextCollapsed },
      };
    });
  }, [getGroupActualKey, updateMetaOnServer]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Group Notes ───────────────────────────────────────────────────────────
  // noteEditAnchor: { mouseX, mouseY, groupId } | null — controls popover visibility
  const [noteEditAnchor, setNoteEditAnchor] = useState(null);
  // Local textarea buffer (synced from group note when popover opens)
  const [noteEditValue, setNoteEditValue] = useState('');

  // Persist note text into the group object for the current expiry
  const handleSaveGroupNote = useCallback((groupId, text) => {
    const actualKey = getGroupActualKey(groupId);
    updateGroupOnServer(actualKey, groupId, { note: text });
    setAllExpiryGroupData((prev) => {
      const slice = prev[actualKey] || { groups: {}, collapsed: {}, order: [] };
      const prevGroups = slice.groups || {};
      if (!prevGroups[groupId]) return prev; // group was deleted mid-edit
      return {
        ...prev,
        [actualKey]: {
          ...slice,
          groups: {
            ...prevGroups,
            [groupId]: { ...prevGroups[groupId], note: text },
          },
        },
      };
    });
  }, [getGroupActualKey, updateGroupOnServer]); // eslint-disable-line react-hooks/exhaustive-deps

  // SL/TP Dialog state
  const [slTpDialogOpen, setSlTpDialogOpen] = useState(false);
  const [selectedPositionForSLTP, setSelectedPositionForSLTP] = useState(null);

  // Take Profit Dialog state
  const [tpDialogOpen, setTpDialogOpen] = useState(false);
  const [selectedPositionForTP, setSelectedPositionForTP] = useState(null);

  // ---- Settings layer (SL/TP, Max Loss, Take Profit) ----
  const {
    slTpSettings, setSlTpSettings,
    maxLossSettings, expiryMaxLossSettings, setExpiryMaxLossSettings,
    tpSettings,
    loadSLTPSettings, loadMaxLossSettings, loadTakeProfitSettings,
    handleMaxLossUpdate, handleTakeProfitUpdate,
  } = useOptionsSettings();

  // Column visibility state (persisted)
  const [columnMenuAnchor, setColumnMenuAnchor] = useState(null);
  const DEFAULT_VISIBLE_COLUMNS = useMemo(() => ({
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
    pop: true,
    pnl: true,
    actions: true,
    // F3: Per-position Greeks — hidden by default, toggleable via Column Settings
    dte: false,
    posDelta: false,
    posTheta: false,
    posGamma: false,
    posVega: false,
    // F2: IV Rank — hidden by default
    ivr: false,
    // Exchange fees paid — hidden by default
    fees: false,
  }), []);
  const [visibleColumns, setVisibleColumns] = usePersistedState('options_visible_columns', DEFAULT_VISIBLE_COLUMNS, {
    transform: (parsed) => ({ ...DEFAULT_VISIBLE_COLUMNS, ...parsed }),
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
    // F3: Per-position Greeks
    { key: 'dte', label: 'DTE' },
    { key: 'posDelta', label: 'Delta' },
    { key: 'posTheta', label: 'Theta ($/d)' },
    { key: 'posGamma', label: 'Gamma' },
    { key: 'posVega', label: 'Vega' },
    // F2: IV Rank
    { key: 'ivr', label: 'IVR' },
    // Exchange fees paid (cumulative, from /v2/fills)
    { key: 'fees', label: 'Fees Paid' },
  ];

  // Toggle column visibility (auto-saved by usePersistedState)
  const toggleColumn = (columnKey) => {
    setVisibleColumns((prev) => ({ ...prev, [columnKey]: !prev[columnKey] }));
  };

  // Skip confirmation per strike (persisted in localStorage)
  // Format: { "symbol": { enabled: true, size: 20, side: "sell" } }
  const [skipConfirmStrikes, setSkipConfirmStrikes] = usePersistedState('options_skip_confirm_strikes', {}, {
    transform: (parsed) => {
      // Migrate old format (symbol: true) to new format (symbol: { enabled, size, side })
      const migrated = {};
      for (const [symbol, value] of Object.entries(parsed)) {
        if (value === true) {
          migrated[symbol] = { enabled: true, size: 5, side: 'sell' };
        } else if (typeof value === 'object' && value !== null) {
          migrated[symbol] = value;
        }
      }
      return migrated;
    },
  });

  // Last used size (persisted)
  const [lastUsedSize, setLastUsedSize] = usePersistedState('options_last_used_size', '5', { parse: 'string' });

  // Scaling strategy state (persisted)
  const [scalingStrategy, setScalingStrategy] = usePersistedState('options_scaling_strategy', 'fixed', { parse: 'string' });

  const [scalingParams, setScalingParams] = usePersistedState('options_scaling_params', {
    maxPositionSize: 50,
    profitThreshold: 10,
    lossThreshold: -20,
    deltaTarget: 0,
    deltaTolerance: 5,
    ivChangeThreshold: 10,
    stepSize: 5,
  });

  // (customOrder is now defined above in the per-expiry group section)

  // Batch order state - strike selection and order quantity
  const [selectedStrikes, setSelectedStrikes] = useState({}); // { symbol: true/false }
  const [orderQuantity, setOrderQuantity] = useState(1); // Simple multiplier based on current position lots
  const [multiplierMode, setMultiplierMode] = useState(null); // null, 'normal', 'gcd', 'fixed', or 'batch' - No default, user must select
  const [executionMode, setExecutionMode] = useState('smart'); // 'immediate', 'smart', 'ssr_standard', 'ssr_aggressive', 'ssr_conservative'
  const [batchQuantities, setBatchQuantities] = useState({}); // { symbol: number } - Manual quantity input per strike
  const [batchOrderResults, setBatchOrderResults] = useState([]);
  // Saved batch quantities - persisted across sessions, keyed by strike (no expiry) e.g. 'P-BTP-56000'
  const [savedBatchQty, setSavedBatchQty] = usePersistedState('options_saved_batch_qty', {});
  // Track which symbols have already been auto-populated so we don't overwrite manual edits
  const initializedBatchQtyRef = useRef(new Set());
  // Auto-populate batch quantities from saved values when positions load or change
  useEffect(() => {
    if (!positions || positions.length === 0) return;
    const updates = {};
    positions.forEach((pos) => {
      const symbol = pos.product_symbol;
      if (!initializedBatchQtyRef.current.has(symbol)) {
        initializedBatchQtyRef.current.add(symbol);
        const key = symbol.split('-').slice(0, 3).join('-');
        if (savedBatchQty[key] !== undefined && savedBatchQty[key] !== 0) {
          updates[symbol] = savedBatchQty[key];
        }
      }
    });
    if (Object.keys(updates).length > 0) {
      setBatchQuantities((prev) => ({ ...prev, ...updates }));
    }
  }, [positions, savedBatchQty]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-loop execution state - with localStorage persistence
  // Now supports per-expiry loops
  const [autoLoopEnabled, setAutoLoopEnabled] = usePersistedState('autoLoopEnabled', false);
  const [autoLoopRounds, setAutoLoopRounds] = usePersistedState('autoLoopRounds', 10, { parse: 'int' });
  // Per-expiry loop state: { [expiryCode]: { running, currentRound, progress, error, stopRef } }
  // Persisted to localStorage for recovery across page refreshes
  // Since auto-loop now runs on backend, "running" loops survive refresh — keep them as running.
  // The polling effect will sync actual status from the backend.
  const [expiryLoopState, setExpiryLoopState] = usePersistedState('expiryLoopState', {});
  // Legacy single-loop state (kept for backward compatibility)
  const [autoLoopRunning, setAutoLoopRunning] = useState(false);
  const [autoLoopCurrentRound, setAutoLoopCurrentRound] = useState(0);
  const [autoLoopProgress, setAutoLoopProgress] = useState({}); // { symbol: { filled: bool, orderId: string } }
  const [autoLoopError, setAutoLoopError] = useState(null);
  const [autoLoopLastRun, setAutoLoopLastRun] = usePersistedState('autoLoopLastRun', null, { immediate: true }); // Stores last run info for recovery
  const autoLoopStopRef = useRef(false); // Flag to stop the loop
  // Per-expiry stop refs (managed as regular object, updated via expiryLoopState)
  const expiryStopRefs = useRef({});

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
  const [autoLoopConfirmDialog, setAutoLoopConfirmDialog] = useState({
    open: false,
    orders: [],
    totalRounds: 1,
    orderPreference: 'maker_first',
    executionMode: 'smart',
    multiplierMode: null, // 'normal' | 'gcd' | 'fixed' | 'batch' | null
  });

  // Sound settings dialog state (JAN 19, 2026 - Independent UI component)
  const [soundSettingsOpen, setSoundSettingsOpen] = useState(false);

  // Position Adjustment Panel state (JAN 31, 2026 - Sensibull-like adjustment workflow)
  const [adjustmentPanelOpen, setAdjustmentPanelOpen] = useState(false);

  // Delta Hedge Modal state
  const [hedgeModalOpen, setHedgeModalOpen] = useState(false);
  const [hedgeModalDelta, setHedgeModalDelta] = useState(0);

  // F9: Roll Manager Modal state
  const [rollModalOpen, setRollModalOpen] = useState(false);
  const [rollPosition, setRollPosition] = useState(null);

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

  // Auto-loop interrupted detection is now handled by backend polling.
  // On mount, the polling effects check for running backend loops and adopt them.

  // Handle drag end - save the custom order to persist across page refreshes (immediate save for UX)
  const handleDragEnd = (event) => {
    const { active, over } = event;
    if (!over) return; // dropped outside any valid target

    const overId = over.id;
    const activeId = active.id;

    // ── Case 0: GROUP-HEADER to GROUP-HEADER drag ─ reorder groups ────────
    // Both IDs start with GROUP_DROP_PREFIX but neither is UNGROUPED
    if (
      String(activeId).startsWith(GROUP_DROP_PREFIX) &&
      String(overId).startsWith(GROUP_DROP_PREFIX)
    ) {
      const activeGid = String(activeId).slice(GROUP_DROP_PREFIX.length);
      const overGid = String(overId).slice(GROUP_DROP_PREFIX.length);
      if (
        activeGid !== overGid &&
        activeGid !== 'UNGROUPED' &&
        overGid !== 'UNGROUPED'
      ) {
        setGroupOrder((prev) => {
          // Use the live groupOrder (from useMemo above) as base if prev is empty
          const base = prev.length > 0 ? prev : groupOrder;
          const oldIdx = base.indexOf(activeGid);
          const newIdx = base.indexOf(overGid);
          if (oldIdx === -1 || newIdx === -1) return base;
          return arrayMove([...base], oldIdx, newIdx);
        });
      }
      return;
    }

    // ── Case 1: dropped onto a group HEADER (DroppableGroupHeader / SortableGroupHeader position drop) ──
    // active is a POSITION, over is a group header
    if (String(overId).startsWith(GROUP_DROP_PREFIX)) {
      const rawId = String(overId).slice(GROUP_DROP_PREFIX.length);
      const targetGroupId = rawId === 'UNGROUPED' ? null : rawId;
      const currentGroupId = getSymbolGroup(activeId);
      if (currentGroupId !== targetGroupId) {
        handleAssignToGroup(activeId, targetGroupId);
        devLog('[OptionsPanel] Drag-to-header: assigned', activeId, '->', targetGroupId);
      }
      return; // no reorder needed — group membership change is enough
    }

    // ── Case 2: dropped onto a position ROW (SortableRow) ───────────────────
    if (activeId !== overId) {
      // BUG-17 FIX: use sortedPositionsRef (visual order, matches SortableContext items)
      const currentPositions = sortedPositionsRef.current;
      const oldIndex = currentPositions.findIndex((p) => p.product_symbol === activeId);
      const newIndex = currentPositions.findIndex((p) => p.product_symbol === overId);

      if (oldIndex === -1 || newIndex === -1) return; // safety guard

      // DRAG-TO-ASSIGN: if dropped onto a row in a different group, reassign
      const activeGroupId = getSymbolGroup(activeId);
      const overGroupId = getSymbolGroup(overId);
      if (activeGroupId !== overGroupId) {
        handleAssignToGroup(activeId, overGroupId || null);
      }

      const reordered = arrayMove(currentPositions, oldIndex, newIndex);
      const newOrder = reordered.map((p) => p.product_symbol);
      setCustomOrder(newOrder);
      saveCustomOrderNow(newOrder);
      devLog('[OptionsPanel] Order updated:', newOrder, '| group:', activeGroupId, '->', overGroupId);
    }
  };

  // Reset custom order (immediate save)
  const resetOrder = () => {
    setCustomOrder([]);
    saveCustomOrderNow([]);
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

  // BUG-10 FIX: Delta Exchange India options expire at 17:30 IST (UTC+5:30 = 12:00 UTC).
  // Always compute expiry relative to UTC so the countdown is correct regardless of browser timezone.
  const getDaysToExpiry = (symbol) => {
    try {
      const parts = symbol?.split('-') || [];
      if (parts.length >= 4) {
        const expiry = parts[3]; // DDMMYY
        const day = parseInt(expiry.substring(0, 2));
        const month = parseInt(expiry.substring(2, 4)) - 1; // JS months are 0-indexed
        const year = 2000 + parseInt(expiry.substring(4, 6));
        // 17:30 IST = 12:00 UTC (UTC+5:30 offset)
        const expiryUtcMs = Date.UTC(year, month, day, 12, 0, 0);
        const diffMs = expiryUtcMs - Date.now();
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

  // Toggle expiry selection (multi-select) - auto-saved by usePersistedState
  const toggleExpirySelection = (expiry) => {
    setSelectedExpiries((prev) => {
      return prev.includes(expiry)
        ? prev.filter((e) => e !== expiry)
        : [...prev, expiry];
    });
  };

  // Clear all expiry selections (show all)
  const clearExpirySelection = () => {
    setSelectedExpiries([]);
  };

  // Sort positions by custom order or default (days to expiration)
  const sortedPositions = useMemo(() => {
    // Get symbols that exist in live positions
    const liveSymbols = new Set(positions.map(p => p.product_symbol));

    // Remove closed positions that now exist as live positions again (user added back)
    // This is done in a separate effect, but we filter here too for immediacy.
    // Also exclude any symbols the user explicitly dismissed (immediate visual feedback).
    const closedToShow = Object.values(closedPositions).filter(
      cp => !liveSymbols.has(cp.product_symbol) && !dismissedSymbols.has(cp.product_symbol)
    );

    // Convert closed positions to position-like objects with size=0
    const closedAsPositions = closedToShow.map(cp => ({
      product_symbol: cp.product_symbol,
      size: 0,
      entry_price: cp.entry_price,
      unrealized_pnl: cp.realized_pnl, // Show realized PnL in the PnL column
      realized_pnl: cp.realized_pnl,
      // BUG-16 FIX: cp.realized_pnl already includes partial PnL at close time (see confirmClose).
      // Setting partial_realized_pnl to 0 here prevents double-count during the React batch race
      // where partialRealizedPnl hasn't been cleared yet after confirmClose.
      partial_realized_pnl: 0,
      close_price: cp.close_price,
      closed_at: cp.closed_at,
      original_size: cp.original_size,
      is_closed: true, // Flag to identify closed positions in UI
      greeks: cp.greeks || {},
      // Parse symbol for display
      best_bid: cp.last_bid || 0,
      best_ask: cp.last_ask || 0,
    }));

    // Inject partial_realized_pnl into live positions so PnL column and payoff graph include it.
    // Skip backend-provided closed phantoms (is_closed=true) — they already carry the correct
    // cumulative realized_pnl and overriding would cause a double-count with unrealized_pnl.
    // Also exclude user-dismissed symbols immediately (before the next API poll confirms they're gone).
    const enrichedPositions = positions
      .filter(p => !dismissedSymbols.has(p.product_symbol))
      .map(p => {
        if (p.is_closed) return p;
        const partialPnl = partialRealizedPnl[p.product_symbol]?.realized_pnl || 0;
        return partialPnl !== 0 ? { ...p, partial_realized_pnl: partialPnl } : p;
      });

    // Merge live positions with closed positions
    const allPositions = [...enrichedPositions, ...closedAsPositions];

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
    // BUG-15 FIX: removed selectedPositionsForPayoff — it is never read inside this memo,
    // so including it caused unnecessary recomputes on every payoff checkbox change
  }, [positions, closedPositions, partialRealizedPnl, hiddenPositions, customOrder, selectedExpiries, symbolSort, strikeSort, sizeSort, dismissedSymbols]);

  // Live index prices state (fetched from WebSocket, not from positions)
  const { btcPrice, ethPrice } = useMarketPrices();

  // F3: Per-position Greeks (polls /api/options/position-greeks every 30s)
  const { positionGreeks, expirySubtotals } = usePositionGreeks(btcPrice || 0);

  // F2: IV Rank/Percentile (polls /api/options/iv-stats every 60s)
  const { ivStats } = useIVStats();
  const indexPrices = useMemo(
    () => ({
      BTC: btcPrice || 0,
      ETH: ethPrice || 0,
    }),
    [btcPrice, ethPrice]
  );

  // Track the spot price at the last HTTP poll so we can apply gamma correction
  // when the spot moves between polls (MISSING-1 partial fix)
  const lastPollSpotRef = useRef({ BTC: 0, ETH: 0 });

  // Calculate aggregated greeks for currently visible positions (respects expiry filter and hidden positions)
  // MISSING-1 PARTIAL FIX: portfolio delta is adjusted in real-time using gamma approximation:
  //   adjusted_delta ≈ poll_delta + gamma * (live_spot - poll_spot)
  // This gives a live delta estimate without a full Black-Scholes recalculation.
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

        // Gamma correction for live delta: Δ_live ≈ Δ_poll + Γ * (S_live - S_poll)
        const parts = pos.product_symbol.split('-');
        const underlying = parts.length >= 2 ? parts[1] : 'BTC';
        const liveSpot = indexPrices[underlying] || 0;
        const pollSpot = lastPollSpotRef.current[underlying] || liveSpot;
        const spotMove = liveSpot > 0 && pollSpot > 0 ? liveSpot - pollSpot : 0;
        const adjustedDelta = perContractDelta + perContractGamma * spotMove;

        // 1 lot = 0.001 BTC — API greeks are per 1 BTC notional, multiply by 0.001.
        // Theta/vega already divide by 1000 (same as × 0.001) for USD conversion.
        const LOT_MULT = 0.001;
        greeks.delta += adjustedDelta * size * LOT_MULT;
        greeks.gamma += perContractGamma * Math.abs(size) * LOT_MULT;
        greeks.theta += (perContractTheta / 1000) * size;
        greeks.vega += (perContractVega / 1000) * Math.abs(size);
        greeks.count++;

        // Separate delta by underlying asset for futures equivalent display
        const deltaContribution = adjustedDelta * size * LOT_MULT;
        if (underlying === 'BTC') {
          greeks.btcDelta += deltaContribution;
        } else if (underlying === 'ETH') {
          greeks.ethDelta += deltaContribution;
        }
      }
    });

    return greeks;
  }, [sortedPositions, indexPrices]);

  // Header advisory (display-only): moved from Portfolio Greeks card to top header center
  const headerAdvisory = useMemo(() => {
    if (!sortedPositions || sortedPositions.length === 0) return null;

    const parseEpochMs = (value) => {
      if (!value) return 0;
      const asNumber = Number(value);
      if (Number.isFinite(asNumber) && asNumber > 0) return asNumber;
      const asDate = Date.parse(String(value));
      return Number.isFinite(asDate) ? asDate : 0;
    };

    const hasGreeks = (Number(aggregatedGreeks?.count) || 0) > 0;
    const delta = Number(aggregatedGreeks?.delta) || 0;
    const theta = Number(aggregatedGreeks?.theta) || 0;
    const gamma = Number(aggregatedGreeks?.gamma) || 0;
    const vega = Number(aggregatedGreeks?.vega) || 0;
    const btcDelta = Number(aggregatedGreeks?.btcDelta) || 0;
    const ethDelta = Number(aggregatedGreeks?.ethDelta) || 0;
    const btcSpot = indexPrices?.BTC || 0;
    const ethSpot = indexPrices?.ETH || 0;
    // Dollar-equivalent directional exposure — used for scale-invariant delta scoring.
    // Positive = long exposure (portfolio profits if price rises).
    const dollarDeltaExposure = Math.abs(btcDelta) * btcSpot + Math.abs(ethDelta) * ethSpot;

    const dataAgeSec = Math.floor((Date.now() - (lastDataUpdate || Date.now())) / 1000);
    const isStale = dataAgeSec > 30;
    const isWarning = dataAgeSec > 10 && dataAgeSec <= 30;

    const positionsWithGreeks = sortedPositions.filter((p) => {
      const g = p?.greeks;
      if (!g) return false;
      return ['delta', 'gamma', 'theta', 'vega'].some((k) => {
        const v = Number(g[k]);
        return Number.isFinite(v);
      });
    }).length;

    const positionsWithQuotes = sortedPositions.filter(
      (p) => (Number(p.best_bid) || 0) > 0 && (Number(p.best_ask) || 0) > 0
    ).length;

    const positionsWithRecentTicks = sortedPositions.filter((p) => {
      const ts = parseEpochMs(p.ws_updated);
      return ts > 0 && (Date.now() - ts) <= 20000;
    }).length;

    const greekCoveragePct = sortedPositions.length > 0
      ? (positionsWithGreeks / sortedPositions.length) * 100
      : 0;

    const quoteCoveragePct = sortedPositions.length > 0
      ? (positionsWithQuotes / sortedPositions.length) * 100
      : 0;

    const recentTickCoveragePct = sortedPositions.length > 0
      ? (positionsWithRecentTicks / sortedPositions.length) * 100
      : 0;

    const recomputedGreeks = sortedPositions.reduce((acc, p) => {
      const g = p?.greeks || {};
      const size = Number(p?.size) || 0;
      const perContractDelta = Number(g.delta) || 0;
      const perContractGamma = Number(g.gamma) || 0;
      const perContractTheta = Number(g.theta) || 0;
      const perContractVega = Number(g.vega) || 0;
      const LOT_MULT = 0.001;
      acc.delta += perContractDelta * size * LOT_MULT;
      acc.gamma += perContractGamma * Math.abs(size) * LOT_MULT;
      acc.theta += (perContractTheta / 1000) * size;
      acc.vega += (perContractVega / 1000) * Math.abs(size);
      return acc;
    }, { delta: 0, gamma: 0, theta: 0, vega: 0 });

    const greekDrift = {
      delta: Math.abs(delta - recomputedGreeks.delta),
      gamma: Math.abs(gamma - recomputedGreeks.gamma),
      theta: Math.abs(theta - recomputedGreeks.theta),
      vega: Math.abs(vega - recomputedGreeks.vega),
    };

    // Delta may differ slightly due live gamma correction in OptionsPanel,
    // so drift warning prioritizes theta/gamma/vega consistency.
    const driftFlag = greekDrift.theta > 0.5 || greekDrift.gamma > 0.00005 || greekDrift.vega > 0.5;

    const freshnessPct = isStale ? 0 : isWarning ? 60 : 100;
    const driftPenalty = driftFlag ? 15 : 0;
    const dataConfidencePct = Math.max(0, Math.min(
      100,
      (greekCoveragePct * 0.5)
      + (quoteCoveragePct * 0.3)
      + (freshnessPct * 0.2)
      - driftPenalty
    ));

    const hasMarginData = !!(marginData && marginData.wallet_balance_usd > 0);
    const blockedMargin = hasMarginData ? Number(marginData.blocked_margin_usd) || 0 : 0;
    const walletBalance = hasMarginData ? Number(marginData.wallet_balance_usd) || 1 : 1;
    const marginUtilPct = hasMarginData
      ? Math.min((blockedMargin / walletBalance) * 100, 100)
      : 0;

    // Dollar-weighted delta score: score = 1.0 at $5K exposure, caps at 2.0 ($10K+).
    // Falls back to BTC-unit comparison if spot price is unavailable.
    const deltaScore = btcSpot > 0
      ? Math.min(dollarDeltaExposure / 5000, 2)
      : Math.min(Math.abs(delta) / 0.25, 2);
    const gammaScore = Math.min(Math.abs(gamma) / 0.0012, 2);
    const marginScore = hasMarginData ? Math.min(marginUtilPct / 70, 2) : 0;
    const thetaCredit = theta > 0 ? Math.min(theta / 600, 1) : 0;
    const advisoryScore = (0.42 * deltaScore) + (0.28 * gammaScore) + (0.22 * marginScore) - (0.12 * thetaCredit);

    let signalState = 'GREEN';
    if (!hasGreeks || isStale || dataConfidencePct < 55) {
      signalState = 'HOLD';
    } else if (advisoryScore >= 1.0) {
      signalState = 'RED';
    } else if (advisoryScore >= 0.65) {
      signalState = 'YELLOW';
    }

    const signalMeta = {
      GREEN: {
        label: 'Monitor',
        color: '#4ade80',
        action: 'No immediate adjustment needed.',
      },
      YELLOW: {
        label: 'Prepare',
        color: '#f59e0b',
        action: 'Prepare a light hedge or rebalance if drift persists.',
      },
      RED: {
        label: 'Adjust',
        color: '#ef4444',
        action: 'Adjustment recommended: reduce directional or gamma risk.',
      },
      HOLD: {
        label: 'Hold',
        color: '#94a3b8',
        action: 'Signal paused until market data confidence recovers.',
      },
    };

    const signalReasons = [];
    if (Math.abs(delta) >= 0.01) {
      const deltaSign = delta >= 0 ? '+' : '';
      const dollarStr = dollarDeltaExposure >= 1000
        ? `≈$${(dollarDeltaExposure / 1000).toFixed(1)}K`
        : `≈$${dollarDeltaExposure.toFixed(0)}`;
      signalReasons.push(`Δ ${deltaSign}${delta.toFixed(4)} (${dollarStr})`);
    }
    if (Math.abs(gamma) >= 0.0010) signalReasons.push(`Γ ${Math.abs(gamma).toFixed(6)}`);
    if (hasMarginData && marginUtilPct >= 60) signalReasons.push(`Margin ${marginUtilPct.toFixed(0)}%`);
    if (isWarning || isStale) signalReasons.push(`Data age ${dataAgeSec}s`);
    if (driftFlag) signalReasons.push('Calc drift');
    if (signalReasons.length === 0) signalReasons.push('Balanced exposure');

    return {
      signalState,
      label: signalMeta[signalState].label,
      color: signalMeta[signalState].color,
      action: signalMeta[signalState].action,
      confidence: Math.round(dataConfidencePct),
      reasons: signalReasons.join(' • '),
    };
  }, [sortedPositions, aggregatedGreeks, marginData, lastDataUpdate, indexPrices]);

  // Intelligent position scaling calculator
  const calculateSmartScaling = useCallback(
    (position) => {
      const currentSize = Math.abs(position.size || 0);
      const pnlPct = position.pnl_percentage || 0;
      const positionDelta = position.greeks?.delta
        ? parseFloat(position.greeks.delta) * position.size * 0.001
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

  // Memoize scaling recommendations for all visible positions (avoid recalculating in render)
  const scalingRecommendations = useMemo(() => {
    const recs = {};
    sortedPositions.forEach((pos) => {
      recs[pos.product_symbol] = calculateSmartScaling(pos);
    });
    return recs;
  }, [sortedPositions, calculateSmartScaling]);

  // Clean up closed positions when they reappear as live positions (re-entry detected).
  // CRITICAL: Before deleting the closed record, carry its realized_pnl forward into
  // partialRealizedPnl so the re-entered position's PnL continues from where it left off
  // rather than restarting from zero. Without this, every re-entry looks like a fresh position.
  useEffect(() => {
    if (positions.length === 0) return;

    const liveSymbols = new Set(positions.map(p => p.product_symbol));
    const closedSymbols = Object.keys(closedPositions);

    // Find closed positions that now exist as live positions
    const toRemove = closedSymbols.filter(symbol => liveSymbols.has(symbol));

    if (toRemove.length > 0) {
      devLog(`🔄 Re-entry detected for ${toRemove.length} position(s) — carrying realized PnL forward`);

      // Step 1: Transfer realized PnL from closed record → partialRealizedPnl
      // This ensures the payoff graph baseline and PnL column both include history.
      const toTransfer = toRemove.filter(sym => closedPositions[sym]?.realized_pnl);
      if (toTransfer.length > 0) {
        setPartialRealizedPnl(prev => {
          const updated = { ...prev };
          toTransfer.forEach(symbol => {
            const closed = closedPositions[symbol];
            const existing = updated[symbol] || { realized_pnl: 0, history: [] };
            updated[symbol] = {
              realized_pnl: (existing.realized_pnl || 0) + closed.realized_pnl,
              history: [
                ...(existing.history || []),
                {
                  size_reduced: Math.abs(closed.original_size || 0),
                  pnl: closed.realized_pnl,
                  exit_price: closed.close_price || 0,
                  entry_price: closed.entry_price || 0,
                  timestamp: closed.closed_at || new Date().toISOString(),
                  event: 're-entry',
                },
              ],
            };
            devLog(`  → ${symbol}: carried forward $${closed.realized_pnl.toFixed(4)} realized PnL`);
          });
          return updated;
        });
      }

      // Step 2: Remove from closedPositions now that PnL is safely transferred
      setClosedPositions(prev => {
        const updated = { ...prev };
        toRemove.forEach(symbol => delete updated[symbol]);
        return updated;
      });
    }
  }, [positions, closedPositions]);

  // Fetch live bid/ask for closed positions so they display real-time market data
  // MISSING-7 FIX: route through backend proxy (/api/ticker/<symbol>) instead of calling
  // Delta Exchange public API directly from the frontend (avoids CORS issues in production)
  const closedSymbolsKey = Object.keys(closedPositions).join(',');
  const hasClosedSymbols = closedSymbolsKey.length > 0;

  const fetchClosedTickers = useCallback(async () => {
    const closedSymbols = Object.keys(closedPositions).filter(
      symbol => !positions.some(p => p.product_symbol === symbol)
    );
    if (closedSymbols.length === 0) return;

    const updates = {};
    await Promise.all(
      closedSymbols.map(async (symbol) => {
        try {
          const { data } = await api.get(`/api/options/ticker/${encodeURIComponent(symbol)}`, { skipCircuit: true });
          if (data?.success && data?.ticker?.quotes) {
            updates[symbol] = {
              last_bid: parseFloat(data.ticker.quotes.best_bid) || 0,
              last_ask: parseFloat(data.ticker.quotes.best_ask) || 0,
            };
          }
        } catch {
          // Silently fail - closed position ticker fetch is best-effort
        }
      })
    );

    if (Object.keys(updates).length > 0) {
      setClosedPositions(prev => {
        const updated = { ...prev };
        for (const [symbol, tickerData] of Object.entries(updates)) {
          if (updated[symbol]) {
            updated[symbol] = { ...updated[symbol], ...tickerData };
          }
        }
        return updated;
      });
    }
  }, [closedSymbolsKey, positions.length]);

  // Poll closed tickers — pauses when tab is hidden
  useVisibilityAwarePolling(fetchClosedTickers, pollInterval * 2, 60000, hasClosedSymbols);

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
      devLog(`🔍 Position change check: prev=${previousSymbols.length}, current=${positions.length}`);
    }

    const disappeared = previousSymbols.filter(
      prevPos => !currentSymbols.has(prevPos.product_symbol) &&
                 !closedPositionsRef.current[prevPos.product_symbol] &&
                 !dismissedRef.current.has(prevPos.product_symbol)
    );

    if (disappeared.length > 0) {
      devLog(`📦 Detected ${disappeared.length} positions that disappeared (likely expired or auto-closed)`);

      const newClosedPositions = {};
      disappeared.forEach(pos => {
        // Include accumulated partial realized PnL in the final realized PnL
        const accumulatedPartialPnl = partialRealizedPnl[pos.product_symbol]?.realized_pnl || 0;
        newClosedPositions[pos.product_symbol] = {
          product_symbol: pos.product_symbol,
          realized_pnl: (pos.unrealized_pnl || 0) + accumulatedPartialPnl, // Last known PnL + accumulated partial exits
          closed_at: new Date().toISOString(),
          entry_price: pos.entry_price || 0,
          close_price: pos.best_bid || pos.best_ask || 0,
          original_size: pos.size || 0,
          greeks: pos.greeks || {},
          // Save last known bid/ask so closed positions still display them
          last_bid: pos.best_bid || 0,
          last_ask: pos.best_ask || 0,
          underlying: pos.product_symbol.split('-')[1] || 'BTC',
          strike: parseInt(pos.product_symbol.split('-')[2]) || 0,
          expiry_code: pos.product_symbol.split('-')[3] || '',
          option_type: pos.product_symbol.startsWith('C-') ? 'Call' : 'Put',
        };
        devLog(`  → ${pos.product_symbol}: PnL $${(pos.unrealized_pnl || 0).toFixed(4)} + partial $${accumulatedPartialPnl.toFixed(4)}`);
      });

      setClosedPositions(prev => ({ ...prev, ...newClosedPositions }));

      // Clear partial realized PnL for disappeared positions (now included in closed position's realized_pnl)
      const partialToClean = disappeared.filter(pos => partialRealizedPnl[pos.product_symbol]);
      if (partialToClean.length > 0) {
        setPartialRealizedPnl(prev => {
          const updated = { ...prev };
          partialToClean.forEach(pos => delete updated[pos.product_symbol]);
          return updated;
        });
      }
    }

    // ========================================================================
    // PARTIAL EXIT PNL TRACKING
    // When a position's absolute size decreases (partial close), calculate the
    // realized PnL for the closed portion and accumulate it.
    // Formula: For the reduced contracts, PnL = (exit_price - entry_price) * reduced_size * 0.001
    // Exit price = mid of current bid/ask. Entry = entry_price at time of reduction.
    // ========================================================================
    const currentPositionMap = {};
    positions.forEach(p => { currentPositionMap[p.product_symbol] = p; });

    previousSymbols.forEach(prevPos => {
      const currPos = currentPositionMap[prevPos.product_symbol];
      if (!currPos) return; // Position disappeared entirely - handled above

      const prevSize = Math.abs(parseFloat(prevPos.size) || 0);
      const currSize = Math.abs(parseFloat(currPos.size) || 0);

      // Detect size reduction (partial exit)
      if (currSize < prevSize && currSize > 0) {
        const reducedContracts = prevSize - currSize; // Always positive
        const prevEntryPrice = parseFloat(prevPos.entry_price) || 0;
        // MISSING-8 FIX: use PREVIOUS position's bid/ask as the exit price approximation.
        // prevPos.best_bid/ask reflects the market AT THE TIME OF detection (before size changed),
        // which is closer to the actual fill than currPos prices (which are POST-fill market).
        // True exit price would come from order fill data, but we don't have it here.
        const prevBid = parseFloat(prevPos.best_bid) || 0;
        const prevAsk = parseFloat(prevPos.best_ask) || 0;
        // Fall back to currPos if prevPos had no quotes
        const fallbackBid = parseFloat(currPos.best_bid) || 0;
        const fallbackAsk = parseFloat(currPos.best_ask) || 0;
        const exitBid = prevBid || fallbackBid;
        const exitAsk = prevAsk || fallbackAsk;
        const exitPrice = (exitBid > 0 && exitAsk > 0)
          ? (exitBid + exitAsk) / 2
          : exitBid || exitAsk || prevEntryPrice;

        // Calculate realized PnL for the reduced portion
        // For SHORT (size < 0): profit = (entry - exit) * contracts * multiplier
        // For LONG (size > 0): profit = (exit - entry) * contracts * multiplier
        const isShort = parseFloat(prevPos.size) < 0;
        // BUG-3 FIX: use symbol-aware multiplier (getContractMultiplier imported at top)
        const contractMultiplier = getContractMultiplier(prevPos.product_symbol);
        const partialPnl = isShort
          ? (prevEntryPrice - exitPrice) * reducedContracts * contractMultiplier
          : (exitPrice - prevEntryPrice) * reducedContracts * contractMultiplier;

        devLog(`📊 Partial exit detected: ${prevPos.product_symbol}`);
        devLog(`   Size: ${prevPos.size} → ${currPos.size} (reduced ${reducedContracts} contracts)`);
        devLog(`   Entry: $${prevEntryPrice}, Exit mid: $${exitPrice.toFixed(2)}`);
        devLog(`   Partial realized PnL: $${partialPnl.toFixed(4)}`);

        setPartialRealizedPnl(prev => {
          const existing = prev[prevPos.product_symbol] || { realized_pnl: 0, history: [] };
          return {
            ...prev,
            [prevPos.product_symbol]: {
              realized_pnl: existing.realized_pnl + partialPnl,
              history: [
                ...existing.history,
                {
                  size_reduced: reducedContracts,
                  pnl: partialPnl,
                  exit_price: exitPrice,
                  entry_price: prevEntryPrice,
                  timestamp: new Date().toISOString(),
                  prev_size: prevPos.size,
                  new_size: currPos.size,
                },
              ],
            },
          };
        });
      }
    });

    // Update the ref for next comparison
    prevPositionsRef.current = positions;
  }, [positions]); // Only depend on positions, not closedPositions!

  // Store latest data in refs to avoid useEffect dependency issues
  const sortedPositionsRef = React.useRef(sortedPositions);
  const indexPricesRef = React.useRef(indexPrices);

  // ── Visual order of positions: MUST match exactly the DOM render order ──
  // Groups are rendered first (each group's positions in sortedPositions order),
  // then ungrouped positions. SortableContext items and sortedPositionsRef both
  // use this so dnd-kit indices always match the actual row positions in the DOM.
  const visualOrderedPositions = useMemo(() => {
    const assigned = new Set(
      Object.values(positionGroups).flatMap((g) => g.symbols)
    );
    const ordered = [];
    // 1. Each group's positions in groupOrder display order
    groupOrder.forEach((gid) => {
      const grp = positionGroups[gid];
      if (!grp) return;
      sortedPositions.forEach((p) => {
        if (grp.symbols.includes(p.product_symbol)) ordered.push(p);
      });
    });
    // 2. Ungrouped positions
    sortedPositions.forEach((p) => {
      if (!assigned.has(p.product_symbol)) ordered.push(p);
    });
    return ordered;
  }, [sortedPositions, positionGroups, groupOrder]);

  // Keep refs updated — use visual order so handleDragEnd indices match DOM
  useEffect(() => {
    sortedPositionsRef.current = visualOrderedPositions;
    indexPricesRef.current = indexPrices;
  }, [visualOrderedPositions, indexPrices]);

  // MISSING-1: Update lastPollSpotRef whenever positions are refreshed from HTTP
  // (indicated by lastDataUpdate changing). This sets the baseline for gamma correction.
  useEffect(() => {
    if (indexPrices.BTC > 0) lastPollSpotRef.current.BTC = indexPrices.BTC;
    if (indexPrices.ETH > 0) lastPollSpotRef.current.ETH = indexPrices.ETH;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastDataUpdate]); // Only on HTTP refresh, not on every WebSocket tick

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
  // BUG-11 FIX: recalculate when indexPrices change (spot moves affect PoP significantly).
  // Interval reduced to 15s for better freshness on 0DTE positions.
  const popLastCalcRef = useRef(0);
  const popLastCountRef = useRef(0);
  useEffect(() => {
    if (!sortedPositions || sortedPositions.length === 0) {
      if (Object.keys(popData).length > 0) setPopData({});
      return;
    }

    // Recalculate if: position set changed OR 15 seconds elapsed OR spot price changed
    const now = Date.now();
    const positionSymbols = sortedPositions.map(p => p.product_symbol).sort().join(',');
    const posCountChanged = positionSymbols !== popLastCountRef.current;
    const timeElapsed = now - popLastCalcRef.current > 15000;

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

      // BUG-25 FIX: pos.greeks has no 'spot' field in Delta Exchange API — use live index price directly
      let spotPrice = indexPrices[underlying] || 0;
      if (!spotPrice || spotPrice <= 0) return;
      if (!strikePrice || strikePrice <= 0) return;
      if (!expiryStr || expiryStr.length !== 6) return;

      try {
        const day = parseInt(expiryStr.slice(0, 2));
        const month = parseInt(expiryStr.slice(2, 4)) - 1;
        const year = 2000 + parseInt(expiryStr.slice(4, 6));
        // BUG-10 FIX: use UTC-based expiry (17:30 IST = 12:00 UTC) to match getDaysToExpiry
        const expiryUtcMs = Date.UTC(year, month, day, 12, 0, 0);
        const timeToExpiry = (expiryUtcMs - Date.now()) / (1000 * 60 * 60 * 24 * 365);

        if (timeToExpiry <= 0) {
          // Expired — determine PoP based on current moneyness
          const isShort = pos.size < 0;
          const itm = optionType === 'call' ? spotPrice > strikePrice : spotPrice < strikePrice;
          // Short ITM = losing, Short OTM = winning. Long ITM = winning, Long OTM = losing.
          newPopData[pos.product_symbol] = (isShort ? !itm : itm) ? 99.9 : 0.1;
          return;
        }

        // BUG-12 FIX: use 0.5 (50%) as fallback IV instead of 0.8 (80%),
        // which was too high for most BTC/ETH option expirations and skewed PoP calculations
        let volatility = pos.iv || 0.5;

        const pop = calculatePoP({
          spotPrice,
          strike: strikePrice,
          entryPrice: Math.abs(pos.entry_price) || 0,
          timeToExpiry,
          volatility,
          optionType,
          side: pos.size > 0 ? 'buy' : 'sell',
        });

        const popPct = pop * 100;
        // Clamp display to meaningful ranges instead of showing "0%" or "100%" flat
        if (popPct < 0.1) {
          newPopData[pos.product_symbol] = 0.1; // Show "< 1%" visually
        } else if (popPct > 99.9) {
          newPopData[pos.product_symbol] = 99.9;
        } else {
          newPopData[pos.product_symbol] = popPct;
        }
      } catch {
        // Fallback: show N/A indicator (use -1 as sentinel)
        newPopData[pos.product_symbol] = -1;
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
      devLog(`[AUTOMATION ${severity.toUpperCase()}] ${message}`);
      // TODO: Connect to your toast/snackbar system if available
      // Example: setSnackbar({ open: true, message, severity });
    });

    // Start the automation monitor
    automationMonitor.start();

    // Expose debug helper to console
    window.debugAutomation = () => {
      const status = automationMonitor.getStatus();
      devLog('=== AUTOMATION DEBUG INFO ===');
      devLog('Active automations:', status.length);
      devLog('Details:', status);
      devLog('Market data:', {
        positions: sortedPositionsRef.current?.length || 0,
        spotPrices: indexPricesRef.current,
      });
      return status;
    };
    devLog('💡 Type window.debugAutomation() in console to check automation status');

    // Cleanup on unmount
    return () => {
      automationMonitor.stop();
      delete window.debugAutomation;
    };
  }, []); // Empty deps - only run once on mount

  // Keyboard shortcuts (non-turbo mode — acts on first position by default)
  useEffect(() => {
    // Skip when turbo mode is active — turbo has its own handler with row selection
    if (turboMode) return;

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
  }, [turboMode, sortedPositions, closeDialog.open, addDialog.open, lastUsedSize]);

  // ============================================================================
  // PHASE 1 OPTIMIZATION: Performance monitoring
  // Track render times and warn about slow operations
  // ============================================================================
  useEffect(() => {
    const renderStart = performance.now();
    return () => {
      const renderTime = performance.now() - renderStart;
      if (renderTime > 50) {
        devWarn(
          `⚠️ Slow render detected: ${renderTime.toFixed(2)}ms (target: <50ms)`,
          { positionCount: positions.length, visibleCount: sortedPositions.length }
        );
      }
    };
  });

  // handleRefresh — now provided by useOptionsPositions hook

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
        // Include any accumulated partial realized PnL from prior partial exits
        const accumulatedPartialPnl = partialRealizedPnl[position.product_symbol]?.realized_pnl || 0;
        const closedPosData = {
          product_symbol: position.product_symbol,
          realized_pnl: (position.unrealized_pnl || 0) + accumulatedPartialPnl, // Unrealized + accumulated partial = total realized
          closed_at: new Date().toISOString(),
          entry_price: position.entry_price || 0,
          close_price: data.fill_price || position.best_bid || position.best_ask || 0,
          original_size: position.size || 0,
          greeks: position.greeks || {},
          // Save last known bid/ask so closed positions still display them
          last_bid: position.best_bid || 0,
          last_ask: position.best_ask || 0,
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

        // Clear partial realized PnL for this symbol since it's now fully closed and included in realized_pnl
        setPartialRealizedPnl(prev => {
          const updated = { ...prev };
          delete updated[position.product_symbol];
          return updated;
        });

        devLog(`📦 Saved closed position: ${position.product_symbol} with realized PnL: $${closedPosData.realized_pnl.toFixed(4)} (includes $${accumulatedPartialPnl.toFixed(4)} partial)`);

        // Check if order was actually filled (not just placed)
        // BUG-4 FIX: do not default to 'market' — that would trigger false fill sounds for pending limits
        const execType = data.execution_type || 'unknown';
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
        fetchDashboard(); // BUG-24 FIX: refresh all panel data (positions, pending orders, margin)
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

    devLog(`⚡ Quick order for ${symbol}: size=${size}, side=${side}`);

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
        fetchDashboard(); // BUG-29 FIX: refresh all panel data after order
        fetchPendingOrders(); // immediate pending orders refresh (bypasses dashboard cache)
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

    devLog(
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
    devLog(`💾 Saving quick mode for ${symbol}: size=${savedSize}, side=${savedSide}`);
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
      devLog('⚠️ Order already submitting, ignoring duplicate click');
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

        devLog(`🏎️ Placing SSR order: ${ssrMode}`, ssrRequestData);

        const { data } = await api.post('/api/options/ssr-order', ssrRequestData);

        if (data?.success) {
          soundManager.play('orderPlaced');
          setOrderResult({
            type: 'info',
            message: `🏎️ SSR ${ssrMode.toUpperCase()}: ${side.toUpperCase()} ${size} ${position.product_symbol} - monitoring started`,
          });
          fetchDashboard(); // BUG-29 FIX
          fetchPendingOrders(); // immediate pending orders refresh
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
          fetchDashboard(); // BUG-29 FIX
          fetchPendingOrders(); // immediate pending orders refresh
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

  // BUG-21 FIX: removed duplicate 'gcd' — using calculateGCD defined below for all GCD needs

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

  // Batch order quantity multiplier logic
  //
  // ORDER DIRECTION LOGIC (based on sign of orderQuantity):
  //   Positive (+1, +2, …) = ADD to position (same direction)
  //     • Long position  (size > 0) → BUY  more
  //     • Short position (size < 0) → SELL more
  //   Negative (-1, -2, …) = EXIT / REDUCE position (opposite direction)
  //     • Long position  (size > 0) → SELL to close
  //     • Short position (size < 0) → BUY  to close (buy back)
  //
  // MULTIPLIER MODES:
  //   Normal: Order size = abs(position size) * |qty|  (scales with position)
  //   GCD:    Order size = (abs(position size) / GCD) * |qty|  (proportional)
  //   Fixed:  Order size = |qty| lots per position (flat, ideal for gradual exit with auto-loop)
  //   Batch:  Order size = exact value from Batch Qty column per row (positive=BUY, negative=SELL)
  //           Completely ignores the global qty multiplier — use this when you want per-strike
  //           control without any ratio math.
  const calculateBatchOrders = (filterExpiry = null) => {
    // Must have a mode selected before calculating orders
    if (!multiplierMode) return [];

    // Get selected positions, optionally filtered by expiry
    let selectedPos = getSelectedPositions();
    if (filterExpiry) {
      selectedPos = selectedPos.filter(pos => getExpiryCode(pos.product_symbol) === filterExpiry);
    }
    const orders = [];

    // ── BATCH MODE ────────────────────────────────────────────────────────────
    // Uses the per-row Batch Qty column values directly.
    // Positive qty → BUY that many lots; Negative qty → SELL that many lots.
    // The global orderQuantity multiplier is NOT used in this mode.
    if (multiplierMode === 'batch') {
      selectedPos.forEach((pos) => {
        const rawQty = batchQuantities[pos.product_symbol];
        if (!rawQty || rawQty === 0) return; // skip rows with no qty entered

        const midPrice = ((pos.best_bid || 0) + (pos.best_ask || 0)) / 2;
        const orderSize = Math.abs(rawQty);
        const side = rawQty > 0 ? 'buy' : 'sell';

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
    }
    // ── END BATCH MODE ────────────────────────────────────────────────────────

    // Calculate GCD if in GCD mode
    const gcd = multiplierMode === 'gcd' ? getPositionsGCD(selectedPos) : 1;

    const isExiting = orderQuantity < 0; // negative = exit/reduce
    const multiplier = Math.abs(orderQuantity);

    selectedPos.forEach((pos) => {
      const currentSize = pos.size;
      const absCurrentSize = Math.abs(currentSize);

      const midPrice = ((pos.best_bid || 0) + (pos.best_ask || 0)) / 2;

      // Determine order side based on position direction and intent:
      //   isExiting  → opposite side to position (close/reduce)
      //   !isExiting → same side as position (add)
      const isLong = currentSize > 0;
      let side;
      if (isExiting) {
        side = isLong ? 'sell' : 'buy';
      } else {
        side = isLong ? 'buy' : 'sell';
      }

      // Calculate order size based on mode:
      //   Normal: abs(position size) * multiplier
      //   GCD:    (abs(position size) / GCD) * multiplier
      //   Fixed:  exactly `multiplier` lots (flat, capped at remaining position size when exiting)
      let orderSize;
      if (multiplierMode === 'fixed') {
        // Fixed: flat lot count, but cap at remaining position when exiting
        orderSize = isExiting ? Math.min(multiplier, absCurrentSize) : multiplier;
      } else if (multiplierMode === 'gcd') {
        orderSize = (absCurrentSize / gcd) * multiplier;
      } else {
        orderSize = absCurrentSize * multiplier;
      }

      // Skip positions that are already fully closed (0 remaining) when exiting
      if (isExiting && absCurrentSize === 0) return;

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
    // ===== MODE SELECTION CHECK =====
    if (!multiplierMode) {
      setOrderResult({ type: 'warning', message: '⚠️ Please select a mode first: Normal, GCD, Fixed, or Batch' });
      setTimeout(() => setOrderResult(null), 3000);
      return;
    }
    // ===== DUPLICATE PREVENTION =====
    if (batchExecuting) {
      devLog('⚠️ Batch order already executing, ignoring duplicate trigger');
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

    // MISSING-6 FIX: always show confirmation dialog for batch orders (was only for > 10)
    // Prevents accidental execution of wrong quantities on live positions
    setBatchConfirmDialog({
      open: true,
      orderCount: orders.length,
      estimatedTime: Math.ceil(orders.length * 1.5),
    });
    // executeBatch(orders) is called when user confirms — uses pendingBatchOrders
  };

  // Actual batch execution logic (split from executeBatchOrders for confirmation flow)
  const executeBatch = async (orders) => {
    // Lock execution immediately
    devLog(`[BATCH EXECUTE] Starting batch execution with ${orders.length} orders`, orders);

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

    devLog(`[BATCH EXECUTE] Execution mode: ${executionMode}, Preference: ${orderPreference}, Label: ${executionLabel}`);

    try {
      // Handle SSR batch orders differently - need to place sequentially for monitoring
      if (isSSRMode) {
        devLog(`[BATCH-SSR] Placing ${orders.length} SSR orders (mode: ${executionMode})`);
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
        fetchDashboard(); // BUG-29 FIX
        fetchPendingOrders(); // immediate pending orders refresh
        return;
      }

      // Regular batch execution (market/smart)
      devLog(`[BATCH-API] Calling /api/options/batch_add with ${orders.length} orders`);

      const { data } = await api.post('/api/options/batch_add', {
        orders: orders.map(order => ({
          symbol: order.symbol,
          size: order.size,
          side: order.side
        })),
        order_preference: orderPreference,
        confirm: true
      });

      devLog(`[BATCH-API] Response received:`, data);

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
        fetchPendingOrders(); // immediate pending orders refresh

        devLog(`[BATCH-COMPLETE] ${successful} success, ${failed} failed in ${executionTime}`);

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
    // BUG-22 FIX: clear batch quantity inputs after execution to prevent accidental re-runs
    setBatchQuantities({});
  };

  // Auto-loop execution: Execute batch orders multiple times with fill polling
  // NOW RUNS ON BACKEND — survives page refreshes
  const executeAutoLoop = async (startFromRound = 1) => {
    devLog('[AUTO-LOOP] executeAutoLoop called (backend mode)');

    if (autoLoopRunning) {
      devLog('⚠️ Auto-loop already running');
      return;
    }

    if (!multiplierMode) {
      setAutoLoopError('⚠️ Please select an order size mode first — choose Normal, GCD, Fixed, or Batch before starting Auto-Loop.');
      return;
    }

    const orders = calculateBatchOrders();
    devLog('[AUTO-LOOP] Calculated orders:', orders.length, orders);

    if (orders.length === 0) {
      setAutoLoopError('No orders to execute. Select positions and set quantities.');
      return;
    }

    if (!autoLoopRounds || autoLoopRounds < 1) {
      setAutoLoopError('Please set number of rounds (must be >= 1)');
      return;
    }

    // Map executionMode to order_preference for backend
    let orderPreference;
    if (executionMode === 'immediate') {
      orderPreference = 'market_only';
    } else if (executionMode === 'smart') {
      orderPreference = 'maker_first';
    } else if (executionMode?.startsWith('ssr_')) {
      orderPreference = executionMode; // pass 'ssr_standard', 'ssr_aggressive', 'ssr_conservative' directly
    } else {
      orderPreference = 'maker_first';
    }

    // Show confirmation dialog instead of executing immediately
    setAutoLoopConfirmDialog({
      open: true,
      orders,
      totalRounds: autoLoopRounds,
      orderPreference,
      executionMode,
      multiplierMode,
    });
  };

  const _doStartAutoLoop = async (orders, totalRounds, orderPreference) => {
    try {
      // Send to backend to run in a background thread
      let response;
      try {
        response = await api.post('/api/options/auto-loop/start', {
          loop_id: 'main',
          orders: orders.map(o => ({ symbol: o.symbol, side: o.side, size: o.size })),
          total_rounds: totalRounds,
          order_preference: orderPreference,
        });
      } catch (err) {
        // If 409 CONFLICT (running/stale loop), force-clear and retry once
        if (err.response?.status === 409) {
          devLog('[AUTO-LOOP] Got 409 CONFLICT — force-clearing loop and retrying...');
          await api.post('/api/options/auto-loop/clear', { force: true, loop_id: 'main' });
          response = await api.post('/api/options/auto-loop/start', {
            loop_id: 'main',
            orders: orders.map(o => ({ symbol: o.symbol, side: o.side, size: o.size })),
            total_rounds: totalRounds,
            order_preference: orderPreference,
          });
        } else {
          throw err;
        }
      }

      if (!response.data.success) {
        throw new Error(response.data.error || 'Failed to start auto-loop on backend');
      }

      devLog('[AUTO-LOOP] Backend loop started:', response.data.loop);

      // Set local UI state — polling effect will keep it updated
      setAutoLoopRunning(true);
      setAutoLoopCurrentRound(0);
      setAutoLoopError(null);
      setAutoLoopProgress({});
      autoLoopStopRef.current = false;

    } catch (error) {
      const errorMsg = error.response?.data?.error || error.message || 'Failed to start auto-loop';
      console.error('[AUTO-LOOP] Start error:', error);
      setAutoLoopError(errorMsg);
    }
  };

  // Stop auto-loop — tells backend to stop
  // ARCH-1 NOTE: Two auto-loop systems exist — legacy (autoLoopRunning) and per-expiry (expiryLoopState).
  // The "STOP ALL" banner button stops ALL running loops (both main and per-expiry).
  const stopAutoLoop = async () => {
    devLog('[AUTO-LOOP] Stop requested (backend mode)');
    // Optimistically update UI immediately so the banner responds right away
    setAutoLoopRunning(false);
    autoLoopStopRef.current = true;
    // Always stop the main loop
    try {
      await api.post('/api/options/auto-loop/stop', { loop_id: 'main' });
    } catch (err) {
      console.error('[AUTO-LOOP] Stop error (main):', err);
    }
    // Also stop any per-expiry loops that might be running concurrently
    if (anyExpiryLoopRunning) {
      await stopAllExpiryLoops();
    }
  };

  // Poll backend auto-loop status — drives autoLoopRunning / progress / error
  const autoLoopPollRef = useRef(null);
  const autoLoopPollInFlightRef = useRef(false);
  const autoLoopPollPendingRef = useRef(false);
  useEffect(() => {
    // Poll when autoLoopRunning OR on mount (to detect loops surviving refresh)
    const pollBackend = async () => {
      if (autoLoopPollInFlightRef.current) {
        autoLoopPollPendingRef.current = true;
        return;
      }

      autoLoopPollInFlightRef.current = true;
      try {
        const { data } = await api.get('/api/options/auto-loop/status?loop_id=main');
        if (!data.success) return;

        const loopState = data.loops?.main;
        // BUG-FIX: original condition "!loopState.exists === undefined" was always false
        // (boolean is never === undefined). Fixed to check exists properly.
        if (!loopState || loopState.exists === false || loopState.exists === undefined) {
          // No loop exists on backend — if we think one is running, stop
          if (autoLoopRunning) {
            setAutoLoopRunning(false);
          }
          return;
        }

        const { status, current_round, total_rounds, progress, error, rounds_completed } = loopState;

        // Map backend progress to frontend format
        if (progress && typeof progress === 'object') {
          setAutoLoopProgress(progress);
        }
        setAutoLoopCurrentRound(current_round || rounds_completed || 0);

        if (status === 'running') {
          if (!autoLoopRunning) setAutoLoopRunning(true);
          // Update rounds display (backend tracks total_rounds)
          if (total_rounds && total_rounds !== autoLoopRounds) {
            // Don't overwrite user's setting — just for display
          }
        } else if (status === 'completed') {
          setAutoLoopRunning(false);
          setOrderResult({
            type: 'success',
            message: `✅ Auto-loop completed: ${rounds_completed}/${total_rounds} rounds executed successfully`,
          });
          setTimeout(() => setOrderResult(null), 5000);
          // Clear backend finished state
          try { await api.post('/api/options/auto-loop/clear'); } catch (e) { /* ignore */ }
        } else if (status === 'stopped') {
          setAutoLoopRunning(false);
          setAutoLoopError(error || `Stopped after round ${rounds_completed}/${total_rounds}`);
          try { await api.post('/api/options/auto-loop/clear'); } catch (e) { /* ignore */ }
        } else if (status === 'error') {
          setAutoLoopRunning(false);
          setAutoLoopError(error || 'Auto-loop failed');
          setOrderResult({
            type: 'error',
            message: `❌ Auto-loop error: ${error}`,
          });
          setTimeout(() => setOrderResult(null), 8000);
          try { await api.post('/api/options/auto-loop/clear'); } catch (e) { /* ignore */ }
        } else if (status === 'stopping') {
          // Still running, waiting for current round to finish
          if (!autoLoopRunning) setAutoLoopRunning(true);
        }

      } catch (err) {
        // Silent fail for polling
      } finally {
        autoLoopPollInFlightRef.current = false;
        if (autoLoopPollPendingRef.current && !document.hidden) {
          autoLoopPollPendingRef.current = false;
          Promise.resolve().then(() => {
            pollBackend();
          });
        } else {
          autoLoopPollPendingRef.current = false;
        }
      }
    };

    // Check immediately on mount for any running backend loops
    pollBackend();

    // Adaptive poll: fast while running, slower while idle to reduce background load.
    const pollMs = autoLoopRunning ? 1500 : 6000;
    autoLoopPollRef.current = setInterval(() => {
      if (!document.hidden) pollBackend();
    }, pollMs);

    return () => {
      if (autoLoopPollRef.current) clearInterval(autoLoopPollRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoLoopRunning]);

  // Clear auto-loop error/warning
  const clearAutoLoopError = () => {
    setAutoLoopError(null);
    setAutoLoopLastRun(null);
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
    // BUG-28 FIX: sortedPositions depends on closedPositions and hiddenPositions too;
    // use sortedPositions directly so the memo stays in sync with what is actually visible
  }, [selectedStrikes, sortedPositions]);

  // Check if any expiry loop is running
  const anyExpiryLoopRunning = useMemo(() => {
    return Object.values(expiryLoopState).some(state => state.running);
  }, [expiryLoopState]);

  // Execute auto-loop for a specific expiry — NOW RUNS ON BACKEND
  const executeExpiryAutoLoop = async (expiryCode) => {
    // Check if already running for this expiry
    if (expiryLoopState[expiryCode]?.running) {
      devLog(`⚠️ Auto-loop already running for ${expiryCode}`);
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

    // Map executionMode to order_preference for backend
    let orderPreference;
    if (executionMode === 'immediate') {
      orderPreference = 'market_only';
    } else if (executionMode === 'smart') {
      orderPreference = 'maker_first';
    } else if (executionMode?.startsWith('ssr_')) {
      orderPreference = executionMode; // pass 'ssr_standard', 'ssr_aggressive', 'ssr_conservative' directly
    } else {
      orderPreference = 'maker_first';
    }

    try {
      // Send to backend — auto-clear stale loops on 409 CONFLICT
      let response;
      try {
        response = await api.post('/api/options/auto-loop/start', {
          loop_id: expiryCode,
          orders: orders.map(o => ({ symbol: o.symbol, side: o.side, size: o.size })),
          total_rounds: autoLoopRounds,
          order_preference: orderPreference,
        });
      } catch (err) {
        if (err.response?.status === 409) {
          devLog(`[AUTO-LOOP:${expiryCode}] Got 409 CONFLICT — force-clearing loop and retrying...`);
          await api.post('/api/options/auto-loop/clear', { force: true, loop_id: expiryCode });
          response = await api.post('/api/options/auto-loop/start', {
            loop_id: expiryCode,
            orders: orders.map(o => ({ symbol: o.symbol, side: o.side, size: o.size })),
            total_rounds: autoLoopRounds,
            order_preference: orderPreference,
          });
        } else {
          throw err;
        }
      }

      if (!response.data.success) {
        throw new Error(response.data.error || 'Failed to start auto-loop on backend');
      }

      devLog(`[AUTO-LOOP:${expiryCode}] Backend loop started`);

      // Set local state — polling effect will keep it updated
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

    } catch (error) {
      console.error(`[AUTO-LOOP:${expiryCode}] Start error:`, error);
      setExpiryLoopState(prev => ({
        ...prev,
        [expiryCode]: {
          ...prev[expiryCode],
          running: false,
          error: error.response?.data?.error || error.message || 'Failed to start',
        }
      }));
    }
  };

  // Stop auto-loop for specific expiry — calls backend
  const stopExpiryAutoLoop = async (expiryCode) => {
    devLog(`[AUTO-LOOP:${expiryCode}] Stop requested (backend mode)`);
    expiryStopRefs.current[expiryCode] = true;
    try {
      await api.post('/api/options/auto-loop/stop', { loop_id: expiryCode });
    } catch (err) {
      console.error(`[AUTO-LOOP:${expiryCode}] Stop error:`, err);
    }
  };

  // Stop all expiry loops AND the main loop — calls backend for each
  const stopAllExpiryLoops = async () => {
    const runningExpiries = Object.keys(expiryLoopState).filter(e => expiryLoopState[e]?.running);
    devLog('[AUTO-LOOP] Stop all requested for:', runningExpiries);

    // Optimistically clear all expiry loop running states immediately
    if (runningExpiries.length > 0) {
      setExpiryLoopState(prev => {
        const updated = { ...prev };
        runningExpiries.forEach(e => {
          if (updated[e]) updated[e] = { ...updated[e], running: false };
        });
        return updated;
      });
    }

    // Stop per-expiry loops on backend
    for (const expiry of runningExpiries) {
      expiryStopRefs.current[expiry] = true;
      try {
        await api.post('/api/options/auto-loop/stop', { loop_id: expiry });
      } catch (err) {
        console.error(`[AUTO-LOOP:${expiry}] Stop error:`, err);
      }
    }

    // Also stop the main loop in case it's running concurrently
    if (autoLoopRunning) {
      setAutoLoopRunning(false);
      autoLoopStopRef.current = true;
      try {
        await api.post('/api/options/auto-loop/stop', { loop_id: 'main' });
      } catch (err) {
        console.error('[AUTO-LOOP] Stop error (main from stopAllExpiryLoops):', err);
      }
    }
  };

  // Poll backend for per-expiry loop status
  const expiryPollRef = useRef(null);
  const expiryPollInFlightRef = useRef(false);
  const expiryPollPendingRef = useRef(false);
  useEffect(() => {
    const hasRunning = Object.values(expiryLoopState).some(s => s.running);

    const pollExpiryLoops = async () => {
      if (expiryPollInFlightRef.current) {
        expiryPollPendingRef.current = true;
        return;
      }

      expiryPollInFlightRef.current = true;
      try {
        const { data } = await api.get('/api/options/auto-loop/status');
        if (!data.success) return;

        const loops = data.loops || {};

        setExpiryLoopState(prev => {
          const updated = { ...prev };

          // Check each expiry that WE think is running
          for (const [expiryCode, localState] of Object.entries(updated)) {
            if (!localState.running) continue;

            const backendState = loops[expiryCode];
            if (!backendState || backendState.exists === false) {
              // Backend has no record — must have finished or never started
              updated[expiryCode] = { ...localState, running: false };
              continue;
            }

            const { status, current_round, total_rounds, progress, error, rounds_completed } = backendState;

            // Sync progress
            if (progress && typeof progress === 'object') {
              updated[expiryCode] = { ...updated[expiryCode], progress };
            }
            updated[expiryCode] = { ...updated[expiryCode], currentRound: current_round || rounds_completed || 0 };

            if (status === 'completed') {
              updated[expiryCode] = { ...updated[expiryCode], running: false, completed: true, endTime: Date.now() };
              // Clean up backend
              api.post('/api/options/auto-loop/clear').catch(() => { });
            } else if (status === 'stopped' || status === 'error') {
              updated[expiryCode] = {
                ...updated[expiryCode],
                running: false,
                error: error || `${status} at round ${rounds_completed}/${total_rounds}`,
              };
              api.post('/api/options/auto-loop/clear').catch(() => { });
            }
          }

          // Also detect NEW backend loops we don't know about (e.g. from before page refresh)
          for (const [loopId, backendState] of Object.entries(loops)) {
            if (loopId === 'main') continue; // handled by main auto-loop poller
            if (backendState.exists === false) continue;
            if (!updated[loopId]?.running && backendState.status === 'running') {
              // Backend has a running loop we don't know about — adopt it
              updated[loopId] = {
                running: true,
                currentRound: backendState.current_round || 0,
                totalRounds: backendState.total_rounds,
                progress: backendState.progress || {},
                error: null,
                startTime: backendState.started_at,
              };
            }
          }

          return updated;
        });
      } catch (err) {
        // Silent fail
      } finally {
        expiryPollInFlightRef.current = false;
        if (expiryPollPendingRef.current && !document.hidden) {
          expiryPollPendingRef.current = false;
          Promise.resolve().then(() => {
            pollExpiryLoops();
          });
        } else {
          expiryPollPendingRef.current = false;
        }
      }
    };

    if (hasRunning) {
      pollExpiryLoops();
      expiryPollRef.current = setInterval(() => {
        if (!document.hidden) pollExpiryLoops();
      }, 1500);
    } else {
      // Check once on mount for surviving backend loops
      pollExpiryLoops();
    }

    return () => {
      if (expiryPollRef.current) clearInterval(expiryPollRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [Object.values(expiryLoopState).some(s => s.running)]);

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
      return updated;
    });
  };

  // Clear all persisted loop state (useful for cleanup)
  const clearAllLoopState = () => {
    setExpiryLoopState({});
    setAutoLoopError(null);
    setAutoLoopLastRun(null);
    devLog('[AUTO-LOOP] Cleared all persisted loop state');
  };

  // ==================== END PER-EXPIRY AUTO-LOOP ====================

  // Format helpers — hoisted to module scope for stable references (see above)
  // formatPnl, formatPnlPct, formatUsd, getPnlColor, getPositionType, parseOptionSymbol
  // are defined OUTSIDE the component to avoid re-creation on every render.

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

  // UI LAYOUT: Options Positions toolbar/header moved to render just above the
  // PortfolioSummaryStrip (per annotated screenshot request).
  const optionsPositionsToolbar = (
    <>
      <OptionsPositionsPropDeskHeader
        status={status}
        positions={positions}
        positionsCount={positions.length}
        advisory={headerAdvisory}
        customOrderCount={customOrder.length}
        hiddenCount={hiddenPositions.length}
        payoffSelectedCount={selectedPositionsForPayoff.length}
        onResetOrder={resetOrder}
        onClearHidden={() => setHiddenPositions([])}
        turboMode={turboMode}
        onToggleTurbo={() => setTurboMode(!turboMode)}
        showAdjust={positions.length > 0 && !turboMode}
        onAdjust={() => setAdjustmentPanelOpen(true)}
        pollInterval={pollInterval}
        onTogglePollInterval={() => setPollInterval(pollInterval === 5000 ? 1000 : 5000)}
        uniqueExpiries={uniqueExpiries}
        selectedExpiries={selectedExpiries}
        onClearExpirySelection={clearExpirySelection}
        onToggleExpirySelection={toggleExpirySelection}
        getExpiryCode={getExpiryCode}
        indexPrices={indexPrices}
        scalingCollapsed={scalingStrategyCollapsed}
        onToggleScaling={() => {
          const next = !scalingStrategyCollapsed;
          setScalingStrategyCollapsed(next);
          localStorage.setItem('options_scaling_strategy_collapsed', JSON.stringify(next));
        }}
        maxLossCollapsed={expiryMaxLossCollapsed}
        onToggleMaxLoss={() => setExpiryMaxLossCollapsed((prev) => !prev)}
        onOpenSoundSettings={() => setSoundSettingsOpen(true)}
        onRefresh={handleRefresh}
        refreshing={refreshing}
      />

      {/* Per-Expiry Max Loss — toggled via Row 2 chip */}
      {positions.length > 0 && uniqueExpiries.length > 0 && !turboMode && (
        <Collapse in={!expiryMaxLossCollapsed}>
          <Box sx={{ mb: 1 }}>
            <ExpiryMaxLossPanel
              uniqueExpiries={uniqueExpiries}
              expiryPnlMap={expiryPnlMap}
              expiryMaxLossSettings={expiryMaxLossSettings}
              onSettingsUpdate={handleExpiryMaxLossUpdate}
            />
          </Box>
        </Collapse>
      )}

      {/* Position Scaling Strategy — toggled via Row 2 chip */}
      <ScalingStrategyPanel
        scalingStrategy={scalingStrategy}
        setScalingStrategy={setScalingStrategy}
        scalingParams={scalingParams}
        setScalingParams={setScalingParams}
        indexPrices={indexPrices}
        scalingStrategyCollapsed={scalingStrategyCollapsed}
        setScalingStrategyCollapsed={setScalingStrategyCollapsed}
        hideHeader
      />

      {/* Order Result Alert */}
      <Collapse in={!!orderResult}>
        <Alert severity={orderResult?.type || 'info'} sx={{ mb: 2 }} onClose={() => setOrderResult(null)}>
          {orderResult?.message}
        </Alert>
      </Collapse>
    </>
  );

  return (
    <div className="animate-fade-slide-up">
      {/* ARCH-2: Extracted AutoLoopBanner component */}
      <AutoLoopBanner
        autoLoopRunning={autoLoopRunning}
        anyExpiryLoopRunning={anyExpiryLoopRunning}
        autoLoopCurrentRound={autoLoopCurrentRound}
        autoLoopRounds={autoLoopRounds}
        autoLoopProgress={autoLoopProgress}
        expiryLoopState={expiryLoopState}
        stopAutoLoop={stopAutoLoop}
        stopAllExpiryLoops={stopAllExpiryLoops}
        stopExpiryAutoLoop={stopExpiryAutoLoop}
      />


      <Card sx={{ bgcolor: 'background.paper', borderRadius: 2, width: '100%' }}>
        <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
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

          {optionsPositionsToolbar}

          {/* Phase 3: Sticky Portfolio Summary Strip — extracted component */}
          <PortfolioSummaryStrip
            sortedPositions={sortedPositions}
            aggregatedGreeks={aggregatedGreeks}
            formatPnl={formatPnl}
            getPnlColor={getPnlColor}
            indexPrices={indexPrices}
            marginData={marginData}
            lastDataUpdate={lastDataUpdate}
            manualPnL={manualPnL}
            manualPnLBadge={<ManualPnLBadge value={manualPnL} onChange={setManualPnL} />}
          />

          {/* ── Group Manager Strip ──────────────────────────────────── */}
          {positions.length > 0 && !turboMode && (
            <Box sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
              <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, fontSize: '0.7rem' }}>
                🗂 Groups:
              </Typography>
              {/* Existing groups as chips */}
              {Object.entries(positionGroups).map(([gid, grp]) => (
                <Chip
                  key={gid}
                  label={`${grp.name} (${grp.symbols.filter(s => sortedPositions.some(p => p.product_symbol === s)).length})`}
                  size="small"
                  onDelete={() => handleDeleteGroup(gid)}
                  sx={{
                    bgcolor: `${grp.color}22`,
                    borderColor: grp.color,
                    border: '1px solid',
                    color: grp.color,
                    fontWeight: 600,
                    fontSize: '0.68rem',
                    '& .MuiChip-deleteIcon': { color: grp.color, fontSize: 14 },
                  }}
                />
              ))}
              {/* Create new group input */}
              <Box component="form" onSubmit={(e) => { e.preventDefault(); handleCreateGroup(newGroupName); setNewGroupName(''); }}
                sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                <TextField
                  size="small"
                  placeholder="New group name…"
                  value={newGroupName}
                  onChange={(e) => setNewGroupName(e.target.value)}
                  inputProps={{ maxLength: 30 }}
                  sx={{ width: 145, '& .MuiInputBase-input': { fontSize: '0.72rem', py: 0.5 } }}
                />
                <Button type="submit" size="small" variant="outlined" disabled={!newGroupName.trim()}
                  sx={{ fontSize: '0.68rem', py: 0.4, whiteSpace: 'nowrap' }}>
                  ＋ Group
                </Button>
              </Box>
            </Box>
          )}

          {/* ── Group assignment picker — transparent backdrop prevents ClickAway misfire ── */}
          {groupMenuAnchor && (
            <>
              {/* Transparent full-page backdrop — clicking outside closes picker */}
              <Box
                onClick={() => setGroupMenuAnchor(null)}
                sx={{
                  position: 'fixed', inset: 0,
                  zIndex: 99998,
                  background: 'transparent',
                }}
              />
              <Paper
                elevation={12}
                sx={{
                  position: 'fixed',
                  top: groupMenuAnchor.mouseY,
                  left: groupMenuAnchor.mouseX,
                  zIndex: 99999,
                  minWidth: 210,
                  py: 0.5,
                  borderRadius: 2,
                  border: '1px solid',
                  borderColor: 'divider',
                }}
              >
                <Typography variant="caption" sx={{ px: 2, py: 0.5, display: 'block', fontWeight: 'bold', color: 'text.secondary', letterSpacing: 0.5, textTransform: 'uppercase', fontSize: '0.6rem' }}>
                  Assign to Group
                </Typography>
                <Divider sx={{ mb: 0.5 }} />
                {Object.entries(positionGroups).map(([gid, grp]) => {
                  const isCurrent = getSymbolGroup(groupMenuAnchor.symbol) === gid;
                  return (
                    <Box
                      key={gid}
                      onClick={() => { handleAssignToGroup(groupMenuAnchor.symbol, isCurrent ? null : gid); setGroupMenuAnchor(null); }}
                      sx={{
                        display: 'flex', alignItems: 'center', gap: 1,
                        px: 2, py: 0.75, cursor: 'pointer',
                        bgcolor: isCurrent ? `${grp.color}15` : 'transparent',
                        '&:hover': { bgcolor: `${grp.color}22` },
                        borderLeft: isCurrent ? `3px solid ${grp.color}` : '3px solid transparent',
                      }}
                    >
                      <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: grp.color, flexShrink: 0 }} />
                      <Typography variant="body2" sx={{ flex: 1, fontSize: '0.8rem', color: isCurrent ? grp.color : 'text.primary', fontWeight: isCurrent ? 'bold' : 'normal' }}>
                        {grp.name}
                      </Typography>
                      {isCurrent && <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.65rem' }}>✓ assigned</Typography>}
                    </Box>
                  );
                })}
                {Object.keys(positionGroups).length === 0 && (
                  <Box sx={{ px: 2, py: 1 }}>
                    <Typography variant="caption" color="text.secondary" fontStyle="italic">No groups yet — create one above</Typography>
                  </Box>
                )}
                {getSymbolGroup(groupMenuAnchor.symbol) && (
                  <>
                    <Divider sx={{ my: 0.5 }} />
                    <Box
                      onClick={() => { handleAssignToGroup(groupMenuAnchor.symbol, null); setGroupMenuAnchor(null); }}
                      sx={{
                        display: 'flex', alignItems: 'center', gap: 1,
                        px: 2, py: 0.75, cursor: 'pointer',
                        color: 'error.main',
                        '&:hover': { bgcolor: 'error.main', color: 'white' },
                      }}
                    >
                      <CloseIcon sx={{ fontSize: 14 }} />
                      <Typography variant="body2" sx={{ fontSize: '0.8rem' }}>Remove from group</Typography>
                    </Box>
                  </>
                )}
              </Paper>
            </>
          )}

          {/* ── Group Note editor — centered modal with semi-transparent overlay ── */}
          {noteEditAnchor && (() => {
            const { groupId } = noteEditAnchor;
            const grp = positionGroups[groupId];
            if (!grp) return null;
            return (
              <>
                {/* Dark overlay */}
                <Box
                  onClick={() => {
                    handleSaveGroupNote(groupId, noteEditValue);
                    setNoteEditAnchor(null);
                  }}
                  sx={{
                    position: 'fixed', inset: 0, zIndex: 99998,
                    background: 'rgba(0,0,0,0.45)',
                    backdropFilter: 'blur(2px)',
                  }}
                />
                {/* Centered modal card */}
                <Paper
                  elevation={24}
                  onClick={(e) => e.stopPropagation()}
                  sx={{
                    position: 'fixed',
                    top: '50%', left: '50%',
                    transform: 'translate(-50%, -50%)',
                    zIndex: 99999,
                    width: 420,
                    borderRadius: 3,
                    border: `1.5px solid ${grp.color}60`,
                    overflow: 'hidden',
                  }}
                >
                  {/* Coloured title bar */}
                  <Box sx={{
                    px: 2, py: 1,
                    bgcolor: `${grp.color}22`,
                    borderBottom: `1px solid ${grp.color}33`,
                    display: 'flex', alignItems: 'center', gap: 1,
                  }}>
                    <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: grp.color, flexShrink: 0 }} />
                    <Typography sx={{ fontSize: '0.82rem', fontWeight: 700, color: grp.color, flex: 1 }}>
                      {grp.name}
                    </Typography>
                    <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', mr: 1 }}>Strategy Notes</Typography>
                    <Tooltip title="Save & close">
                      <IconButton
                        size="small" sx={{ p: 0.4, color: 'text.secondary' }}
                        onClick={() => { handleSaveGroupNote(groupId, noteEditValue); setNoteEditAnchor(null); }}
                      >
                        <CloseIcon sx={{ fontSize: 15 }} />
                      </IconButton>
                    </Tooltip>
                  </Box>
                  {/* Textarea body */}
                  <Box sx={{ p: 2 }}>
                    <TextField
                      autoFocus
                      multiline
                      minRows={5}
                      maxRows={14}
                      fullWidth
                      value={noteEditValue}
                      onChange={(e) => {
                        setNoteEditValue(e.target.value);
                        handleSaveGroupNote(groupId, e.target.value);
                      }}
                      placeholder={`Why did you create "${grp.name}"?\nWhat is the strategy logic?\nWhat are the expected scenarios?`}
                      variant="outlined"
                      size="small"
                      sx={{
                        '& .MuiOutlinedInput-root': {
                          fontSize: '0.82rem',
                          lineHeight: 1.7,
                          '& fieldset': { borderColor: `${grp.color}35` },
                          '&:hover fieldset': { borderColor: `${grp.color}70` },
                          '&.Mui-focused fieldset': { borderColor: grp.color },
                        },
                      }}
                    />
                    <Typography
                      variant="caption"
                      sx={{ mt: 0.75, display: 'block', color: 'text.disabled', fontSize: '0.62rem', textAlign: 'right' }}
                    >
                      Auto-saved · Press Esc or click outside to close
                    </Typography>
                  </Box>
                </Paper>
              </>
            );
          })()}

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
            <TableContainer component={Paper} sx={{ maxHeight: 500, width: '100%', overflowX: 'auto' }}>
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
                        <Tooltip title="Click to sort by size (contracts)">
                          <Box
                            sx={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'flex-end',
                              gap: 0.5,
                            }}
                          >
                            Size (cts)
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
                    {visibleColumns.ivr && (
                      <TableCell align="center" sx={{ minWidth: 50 }}>
                        <Tooltip title="IV Rank — percentile of current IV vs 52-week range">
                          <Box>IVR</Box>
                        </Tooltip>
                      </TableCell>
                    )}
                    {visibleColumns.dte && (
                      <TableCell align="center" sx={{ minWidth: 40 }}>
                        <Tooltip title="Days to Expiration">
                          <Box>DTE</Box>
                        </Tooltip>
                      </TableCell>
                    )}
                    {visibleColumns.posDelta && (
                      <TableCell align="right" sx={{ minWidth: 60 }}>
                        <Tooltip title="Position Delta — directional exposure">
                          <Box>Delta</Box>
                        </Tooltip>
                      </TableCell>
                    )}
                    {visibleColumns.posTheta && (
                      <TableCell align="right" sx={{ minWidth: 60 }}>
                        <Tooltip title="Position Theta — daily time decay ($)">
                          <Box>Theta</Box>
                        </Tooltip>
                      </TableCell>
                    )}
                    {visibleColumns.posGamma && (
                      <TableCell align="right" sx={{ minWidth: 60 }}>
                        <Tooltip title="Position Gamma — delta sensitivity">
                          <Box>Gamma</Box>
                        </Tooltip>
                      </TableCell>
                    )}
                    {visibleColumns.posVega && (
                      <TableCell align="right" sx={{ minWidth: 60 }}>
                        <Tooltip title="Position Vega — $ per 1 vol-point change">
                          <Box>Vega</Box>
                        </Tooltip>
                      </TableCell>
                    )}
                    {visibleColumns.fees && (
                      <TableCell align="right" sx={{ minWidth: 70 }}>
                        <Tooltip title="Cumulative exchange fees paid on this symbol (USD, last 30 days)">
                          <Box>Fees Paid</Box>
                        </Tooltip>
                      </TableCell>
                    )}
                    {visibleColumns.actions && <TableCell align="center">Actions</TableCell>}
                  </TableRow>
                </TableHead>
                <DndContext
                  sensors={sensors}
                  collisionDetection={closestCenter}
                  onDragEnd={handleDragEnd}
                >
                  <SortableContext
                    // Items include __GROUP__<id> for each named group header so group headers
                    // participate as sortable. Position symbols follow each group's header.
                    // BUG-6 FIX: deduplicate IDs
                    items={(() => {
                      const hasAnyGroups = Object.keys(positionGroups).length > 0;
                      if (!hasAnyGroups) {
                        return [...new Set(visualOrderedPositions.map((p) => p.product_symbol))];
                      }
                      const ids = [];
                      const gEntries = groupOrder
                        .filter((gid) => positionGroups[gid])
                        .map((gid) => [gid, positionGroups[gid]]);
                      gEntries.forEach(([gid, grp]) => {
                        ids.push(`${GROUP_DROP_PREFIX}${gid}`);
                        sortedPositions.forEach((p) => {
                          if (grp.symbols.includes(p.product_symbol)) ids.push(p.product_symbol);
                        });
                      });
                      const assignedSet = new Set(gEntries.flatMap(([, g]) => g.symbols));
                      sortedPositions.forEach((p) => {
                        if (!assignedSet.has(p.product_symbol)) ids.push(p.product_symbol);
                      });
                      return [...new Set(ids)];
                    })()}
                    strategy={verticalListSortingStrategy}
                  >
                    <TableBody>
                      {(() => {
                        // Build rendering order: named groups first (in groupOrder), then ungrouped
                        // groupOrder controls group display sequence; positions within each group
                        // follow sortedPositions order
                        const orderedGroupEntries = groupOrder
                          .filter((gid) => positionGroups[gid])
                          .map((gid) => [gid, positionGroups[gid]]);
                        const hasGroups = orderedGroupEntries.length > 0;
                        // Alias for backwards-compat with code below that references groupEntries
                        const groupEntries = orderedGroupEntries;

                        // Render one position row (shared helper)
                        const renderPositionRow = (pos, index, groupColor) => {
                          const optionInfo = parseOptionSymbol(pos.product_symbol);
                          const posType = getPositionType(pos.product_symbol);
                          const isLong = pos.size > 0;
                          const daysToExp = getDaysToExpiry(pos.product_symbol);
                          const isQuickMode = skipConfirmStrikes[pos.product_symbol]?.enabled;
                          const isClosed = pos.is_closed === true || (pos.size === 0 && closedPositions[pos.product_symbol]);
                          const cashflow = pos.cashflow || 0;
                          const effectiveSize = isClosed
                            ? (closedPositions[pos.product_symbol]?.original_size || pos.original_size || 0)
                            : pos.size;
                          const isCall = optionInfo.type === 'Call';
                          const isPut = optionInfo.type === 'Put';
                          const rowBgColor = groupColor
                            ? `${groupColor}0a`
                            : isClosed
                              ? 'rgba(255, 255, 255, 0.03)'
                              : isCall
                                ? 'rgba(16, 185, 129, 0.03)'
                                : isPut
                                  ? 'rgba(239, 68, 68, 0.03)'
                                  : 'transparent';
                          const rowHoverColor = groupColor
                            ? `${groupColor}18`
                            : isClosed
                              ? 'rgba(255, 255, 255, 0.06)'
                              : isCall
                                ? 'rgba(16, 185, 129, 0.06)'
                                : isPut
                                  ? 'rgba(239, 68, 68, 0.06)'
                                  : 'action.hover';
                          const isSelectedInTurbo = turboMode && selectedRowIndex >= 0 && index === selectedRowIndex;
                          const finalBgColor = isSelectedInTurbo ? 'rgba(255, 193, 7, 0.2)' : rowBgColor;
                          const finalHoverColor = isSelectedInTurbo ? 'rgba(255, 193, 7, 0.3)' : rowHoverColor;
                          const cellSx = {
                            backgroundColor: `${finalBgColor} !important`,
                            '&:hover': { backgroundColor: `${finalHoverColor} !important` },
                            opacity: isClosed ? 0.7 : 1,
                            borderLeft: groupColor
                              ? `3px solid ${groupColor}`
                              : isSelectedInTurbo
                                ? '3px solid #ffc107'
                                : undefined,
                          };

                          return (
                            <SortableRow
                              key={pos.product_symbol}
                              pos={pos}
                            >
                              {(attributes, listeners) => (
                                <PositionRow
                                  pos={pos}
                                  index={index}
                                  optionInfo={optionInfo}
                                  posType={posType}
                                  daysToExp={daysToExp}
                                  isClosed={isClosed}
                                  effectiveSize={effectiveSize}
                                  cashflow={cashflow}
                                  cellSx={cellSx}
                                  rowBgColor={rowBgColor}
                                  rowHoverColor={rowHoverColor}
                                  isCall={isCall}
                                  isPut={isPut}
                                  isLong={isLong}
                                  isQuickMode={isQuickMode}
                                  visibleColumns={visibleColumns}
                                  isSelected={selectedStrikes[pos.product_symbol]}
                                  isPayoffSelected={selectedPositionsForPayoff.includes(pos.product_symbol)}
                                  batchQty={batchQuantities[pos.product_symbol]}
                                  slTpSetting={slTpSettings[pos.product_symbol]}
                                  maxLossSetting={maxLossSettings[pos.product_symbol]}
                                  tpSetting={tpSettings[pos.product_symbol]}
                                  popValue={popData[pos.product_symbol]}
                                  posGreeks={positionGreeks[pos.product_symbol]}
                                  ivrData={ivStats[pos.product_symbol]}
                                  feesPaid={feesMap[pos.product_symbol] || 0}
                                  skipConfirmStrike={skipConfirmStrikes[pos.product_symbol]}
                                  scalingRecommendation={scalingRecommendations[pos.product_symbol]}
                                  onToggleStrikeSelection={toggleStrikeSelection}
                                  onTogglePayoffSelection={(symbol) => {
                                    setSelectedPositionsForPayoff((prev) =>
                                      prev.includes(symbol)
                                        ? prev.filter((s) => s !== symbol)
                                        : [...prev, symbol]
                                    );
                                  }}
                                  onToggleHidden={(symbol) => {
                                    setHiddenPositions((prev) =>
                                      prev.includes(symbol)
                                        ? prev.filter((s) => s !== symbol)
                                        : [...prev, symbol]
                                    );
                                  }}
                                  onBatchQtyChange={(symbol, value) => {
                                    setBatchQuantities((prev) => ({ ...prev, [symbol]: value }));
                                    if (value !== 0) {
                                      setSelectedStrikes((prev) => ({ ...prev, [symbol]: true }));
                                    }
                                  }}
                                  savedBatchQtyValue={savedBatchQty[pos.product_symbol.split('-').slice(0, 3).join('-')]}
                                  onSaveBatchQty={(symbol, qty) => {
                                    const key = symbol.split('-').slice(0, 3).join('-');
                                    setSavedBatchQty(prev => qty ? { ...prev, [key]: qty } : (({ [key]: _, ...rest }) => rest)(prev));
                                  }}
                                  onUnsaveBatchQty={(symbol) => {
                                    const key = symbol.split('-').slice(0, 3).join('-');
                                    setSavedBatchQty(prev => (({ [key]: _, ...rest }) => rest)(prev));
                                  }}
                                  onSetSLTP={(position) => {
                                    setSelectedPositionForSLTP(position);
                                    setSlTpDialogOpen(true);
                                  }}
                                  onSetTP={(position) => {
                                    setSelectedPositionForTP(position);
                                    setTpDialogOpen(true);
                                  }}
                                  onMaxLossUpdate={handleMaxLossUpdate}
                                  onTakeProfitUpdate={handleTakeProfitUpdate}
                                  onHandleAdd={handleAdd}
                                  onHandleClose={handleClose}
                                  onRoll={(p) => { setRollPosition(p); setRollModalOpen(true); }}
                                  onDisableSkipConfirm={disableSkipConfirm}
                                  onRemoveClosedPosition={(symbol) => {
                                    // 1. Immediately hide the row (works for both localStorage and
                                    //    backend-API phantom rows — instant visual feedback before
                                    //    the next poll confirms the server no longer returns it).
                                    dismissedRef.current = new Set([...dismissedRef.current, symbol]);
                                    setDismissedSymbols(new Set(dismissedRef.current));
                                    // 2. Remove from frontend localStorage
                                    setClosedPositions(prev => {
                                      const updated = { ...prev };
                                      delete updated[symbol];
                                      return updated;
                                    });
                                    setPartialRealizedPnl(prev => {
                                      const updated = { ...prev };
                                      delete updated[symbol];
                                      return updated;
                                    });
                                    // 3. Remove from backend store so it doesn't reappear on next poll
                                    api.delete(`/api/options/closed-positions/${encodeURIComponent(symbol)}`).catch(err => {
                                      devLog(`⚠️ Backend dismiss failed for ${symbol}:`, err);
                                    });
                                    devLog(`🗑️ Dismissed closed position: ${symbol}`);
                                  }}
                                  status={status}
                                  closedPositionData={closedPositions[pos.product_symbol]}
                                  DEFAULT_SIZE={DEFAULT_SIZE}
                                  attributes={attributes}
                                  listeners={listeners}
                                  onGroupClick={hasGroups ? (e) => {
                                    e.stopPropagation();
                                    const rect = e.currentTarget.getBoundingClientRect();
                                    setGroupMenuAnchor({
                                      mouseX: rect.right,
                                      mouseY: rect.bottom,
                                      symbol: pos.product_symbol,
                                    });
                                  } : undefined}
                                />
                              )}
                            </SortableRow>
                          );
                        };

                        // Compute column count for the header span
                        const colCount = Object.values(visibleColumns).filter(Boolean).length + 4; // checkboxes + drag

                        // Split positions into groups and ungrouped
                        const assignedSymbols = new Set(
                          groupEntries.flatMap(([, g]) => g.symbols)
                        );
                        const rows = [];
                        let globalIndex = 0;

                        // Render named groups
                        groupEntries.forEach(([gid, grp]) => {
                          const groupPositions = sortedPositions.filter(
                            (p) => grp.symbols.includes(p.product_symbol)
                          );
                          const isCollapsed = collapsedGroups[gid];
                          // Net PnL for the group
                          const groupNetPnl = groupPositions.reduce((sum, p) => {
                            return sum + (Number(p.unrealized_pnl) || 0) + (Number(p.partial_realized_pnl) || 0);
                          }, 0);

                          // Group header row — SortableGroupHeader makes it draggable.
                          // CLEAN HEADER: compact single-line, notes in a separate row below.
                          const groupNote = grp.note || '';
                          rows.push(
                            <SortableGroupHeader key={`grphdr-${gid}`} groupId={gid} color={grp.color}>
                              {(headerAttrs, headerListeners) => (
                                <TableCell
                                  colSpan={colCount}
                                  sx={{
                                    py: 0.4, px: 1,
                                    bgcolor: `${grp.color}18`,
                                    borderLeft: `3px solid ${grp.color}`,
                                    borderBottom: `1px solid ${grp.color}30`,
                                  }}
                                >
                                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    {/* Drag grip */}
                                    <Box
                                      {...headerAttrs} {...headerListeners}
                                      sx={{
                                        cursor: 'grab', color: `${grp.color}70`,
                                        fontSize: 15, lineHeight: 1, userSelect: 'none', flexShrink: 0,
                                        '&:active': { cursor: 'grabbing' },
                                      }}
                                      title="Drag to reorder group"
                                    >⋯</Box>
                                    {/* Color dot */}
                                    <Box sx={{ width: 9, height: 9, borderRadius: '50%', bgcolor: grp.color, flexShrink: 0 }} />
                                    {/* Group name */}
                                    <Typography sx={{ fontSize: '0.73rem', fontWeight: 700, color: grp.color, flex: 1, letterSpacing: 0.3 }}>
                                      {grp.name}
                                    </Typography>
                                    {/* Leg count chip */}
                                    <Chip
                                      label={`${groupPositions.length} leg${groupPositions.length !== 1 ? 's' : ''}`}
                                      size="small"
                                      sx={{ height: 15, fontSize: '0.58rem', bgcolor: `${grp.color}20`, color: grp.color, fontWeight: 600 }}
                                    />
                                    {/* Net PnL */}
                                    <Typography sx={{
                                      fontSize: '0.68rem', fontWeight: 700, minWidth: 65, textAlign: 'right',
                                      color: groupNetPnl >= 0 ? '#10b981' : '#ef4444',
                                    }}>
                                      {groupNetPnl >= 0 ? '+' : ''}{formatPnl(groupNetPnl)}
                                    </Typography>
                                    {/* Note icon — dimmed when empty, colored when note exists */}
                                    <Tooltip title={groupNote ? 'View / edit note' : 'Add strategy note'}>
                                      <IconButton
                                        size="small"
                                        sx={{
                                          p: 0.2,
                                          color: groupNote ? grp.color : `${grp.color}40`,
                                          '&:hover': { color: grp.color, bgcolor: `${grp.color}18` },
                                          transition: 'color 0.15s',
                                        }}
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          setNoteEditValue(groupNote);
                                          setNoteEditAnchor({ groupId: gid });
                                        }}
                                      >
                                        {groupNote
                                          ? <StickyNote2Icon sx={{ fontSize: 14 }} />
                                          : <EditNoteIcon sx={{ fontSize: 14 }} />}
                                      </IconButton>
                                    </Tooltip>
                                    {/* Collapse toggle */}
                                    <Tooltip title={isCollapsed ? 'Expand' : 'Collapse'}>
                                      <IconButton size="small" onClick={() => toggleGroupCollapse(gid)} sx={{ p: 0.2, color: `${grp.color}90` }}>
                                        {isCollapsed ? <ExpandMoreIcon sx={{ fontSize: 15 }} /> : <ExpandLessIcon sx={{ fontSize: 15 }} />}
                                      </IconButton>
                                    </Tooltip>
                                  </Box>
                                </TableCell>
                              )}
                            </SortableGroupHeader>
                          );

                          // Note preview row — separate clean row, shows only when note exists.
                          // Clicking it opens the note editor.
                          if (groupNote && !isCollapsed) {
                            rows.push(
                              <TableRow key={`grpnote-${gid}`} sx={{ bgcolor: `${grp.color}09` }}>
                                <TableCell
                                  colSpan={colCount}
                                  sx={{
                                    py: 0.4, px: 2,
                                    borderLeft: `3px solid ${grp.color}55`,
                                    borderBottom: `1px solid ${grp.color}20`,
                                    cursor: 'pointer',
                                    '&:hover': { bgcolor: `${grp.color}14` },
                                    transition: 'background 0.12s',
                                  }}
                                  onClick={() => {
                                    setNoteEditValue(groupNote);
                                    setNoteEditAnchor({ groupId: gid });
                                  }}
                                >
                                  <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 0.75 }}>
                                    <StickyNote2Icon sx={{ fontSize: 12, color: `${grp.color}70`, mt: '2px', flexShrink: 0 }} />
                                    <Typography sx={{
                                      fontSize: '0.68rem',
                                      color: 'text.secondary',
                                      fontStyle: 'italic',
                                      lineHeight: 1.5,
                                      whiteSpace: 'pre-wrap',
                                      wordBreak: 'break-word',
                                      display: '-webkit-box',
                                      WebkitLineClamp: 2,
                                      WebkitBoxOrient: 'vertical',
                                      overflow: 'hidden',
                                    }}>
                                      {groupNote}
                                    </Typography>
                                    <EditNoteIcon sx={{ fontSize: 12, color: 'text.disabled', ml: 'auto', flexShrink: 0, mt: '2px' }} />
                                  </Box>
                                </TableCell>
                              </TableRow>
                            );
                          }

                          // Group position rows (hidden when collapsed)
                          if (!isCollapsed) {
                            groupPositions.forEach((pos) => {
                              rows.push(renderPositionRow(pos, globalIndex++, grp.color));
                            });
                          } else {
                            globalIndex += groupPositions.length;
                          }
                        });

                        // Render ungrouped positions
                        const ungroupedPositions = hasGroups
                          ? sortedPositions.filter((p) => !assignedSymbols.has(p.product_symbol))
                          : sortedPositions;

                        if (hasGroups && ungroupedPositions.length > 0) {
                          // Ungrouped header — also a DroppableGroupHeader so dragging
                          // onto it removes the position from its current group
                          rows.push(
                            <DroppableGroupHeader key="grphdr-ungrouped" groupId={null} color="#888">
                              <TableCell
                                colSpan={colCount}
                                sx={{ py: 0.3, px: 1, bgcolor: 'action.hover', borderBottom: '1px solid', borderColor: 'divider' }}
                              >
                                <Typography sx={{ fontSize: '0.7rem', color: 'text.secondary', fontStyle: 'italic' }}>
                                  Ungrouped ({ungroupedPositions.length}) — drag here or click 🏷 to assign
                                </Typography>
                              </TableCell>
                            </DroppableGroupHeader>
                          );
                        }

                        ungroupedPositions.forEach((pos) => {
                          rows.push(renderPositionRow(pos, globalIndex++, null));
                        });

                        return rows;
                      })()}
                    </TableBody>
                  </SortableContext>
                </DndContext>
              </Table>
            </TableContainer>
          )}

          {/* F3: Expiry Greek Subtotals — shown when any Greek column is visible */}
          {(visibleColumns.posDelta || visibleColumns.posTheta || visibleColumns.posGamma || visibleColumns.posVega) &&
            Object.keys(expirySubtotals).length > 0 && (
            <Box sx={{
              mt: 0.5, mb: 1,
              display: 'flex', flexWrap: 'wrap', gap: 1,
              px: 1.5, py: 1,
              bgcolor: 'rgba(15, 23, 42, 0.7)',
              border: '1px solid rgba(71, 85, 105, 0.3)',
              borderRadius: 1,
            }}>
              <Typography variant="caption" sx={{ color: '#64748b', fontWeight: 600, mr: 0.5, lineHeight: 2 }}>
                Expiry Greeks:
              </Typography>
              {Object.entries(expirySubtotals).sort(([a], [b]) => a.localeCompare(b)).map(([expiry, st]) => {
                const label = expiry.slice(5).replace('-', '/'); // "2026-03-13" -> "03/13"
                return (
                  <Box key={expiry} sx={{
                    display: 'flex', alignItems: 'center', gap: 0.5,
                    px: 1, py: 0.3,
                    bgcolor: 'rgba(30, 41, 59, 0.8)',
                    border: '1px solid rgba(71, 85, 105, 0.4)',
                    borderRadius: 0.5,
                  }}>
                    <Typography variant="caption" sx={{ color: '#94a3b8', fontWeight: 700, mr: 0.5 }}>
                      {label}
                    </Typography>
                    {visibleColumns.posDelta && (
                      <Typography variant="caption" sx={{ color: st.delta >= 0 ? '#10b981' : '#ef4444' }}>
                        {'\u0394'}{st.delta > 0 ? '+' : ''}{st.delta.toFixed(3)}
                      </Typography>
                    )}
                    {visibleColumns.posTheta && (
                      <Typography variant="caption" sx={{ color: st.theta >= 0 ? '#10b981' : '#f59e0b', ml: 0.5 }}>
                        {'\u0398'}{st.theta > 0 ? '+' : ''}${st.theta.toFixed(2)}/d
                      </Typography>
                    )}
                    {visibleColumns.posGamma && (
                      <Typography variant="caption" sx={{ color: '#a855f7', ml: 0.5 }}>
                        {'\u0393'}{st.gamma.toFixed(5)}
                      </Typography>
                    )}
                    {visibleColumns.posVega && (
                      <Typography variant="caption" sx={{ color: '#f59e0b', ml: 0.5 }}>
                        {'\u03bd'}${st.vega.toFixed(2)}
                      </Typography>
                    )}
                    <Typography variant="caption" sx={{ color: '#475569', ml: 0.5 }}>
                      ({st.count})
                    </Typography>
                  </Box>
                );
              })}
            </Box>
          )}

          {/* Payoff Diagram — moved above Batch Order panel */}
          {positions.length > 0 && !turboMode && (
            <Box sx={{ mt: 2 }}>
              <PayoffErrorBoundary>
                <Suspense fallback={<Box sx={{ p: 2, textAlign: 'center' }}>Loading payoff diagram...</Box>}>
                  <OptionsPayoffDiagram
                    positions={sortedPositions}
                    selectedPositions={selectedPositionsForPayoff}
                    futuresPositions={visibleFuturesPositions}
                    indexPrices={indexPrices}
                    manualPnL={manualPnL}
                    onManualPnLChange={setManualPnL}
                    batchOrderSection={
                      <BatchOrderPanel
                        positions={positions}
                        selectedStrikes={selectedStrikes}
                        status={status}
                        compactSpacing
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
                        autoLoopConfirmDialog={autoLoopConfirmDialog}
                        setAutoLoopConfirmDialog={setAutoLoopConfirmDialog}
                        doStartAutoLoop={_doStartAutoLoop}
                        stopAutoLoop={stopAutoLoop}
                        startAllExpiryLoops={startAllExpiryLoops}
                        executeExpiryAutoLoop={executeExpiryAutoLoop}
                        stopExpiryAutoLoop={stopExpiryAutoLoop}
                        clearAutoLoopError={clearAutoLoopError}
                        clearExpiryLoopError={clearExpiryLoopError}
                        onBulkApplyBatchQty={(qty) => {
                          // Option 4: write qty into batchQuantities for every currently-selected row
                          const updates = {};
                          Object.keys(selectedStrikes).forEach((symbol) => {
                            if (selectedStrikes[symbol]) updates[symbol] = qty;
                          });
                          setBatchQuantities((prev) => ({ ...prev, ...updates }));
                        }}
                      />
                    }
                  />
                </Suspense>
              </PayoffErrorBoundary>
            </Box>
          )}

          <ConditionalExitPanel
            selectedStrikes={selectedStrikes}
            positions={positions}
            btcPrice={btcPrice}
          />

          {/* ARCH-2: Extracted PortfolioGreeksSummary component */}
          {
            positions.length > 0 && (
              <PortfolioGreeksSummary
                sortedPositions={sortedPositions}
                aggregatedGreeks={aggregatedGreeks}
                ivStats={ivStats}
                onHedgeClick={(delta) => {
                  setHedgeModalDelta(delta);
                  setHedgeModalOpen(true);
                }}
              />
            )
          }

          {/* Institutional analytics deck: equal 1/3 + 1/3 + 1/3 layout */}
          <Box
            sx={{
              mt: 0.5,
              mb: 1,
              display: 'grid',
              gap: 1.1,
              alignItems: 'stretch',
              gridTemplateColumns: {
                xs: '1fr',
                lg: 'repeat(3, minmax(0, 1fr))',
              },
            }}
          >
            <Box sx={{ minWidth: 0 }}>
              <PnLAttributionPanel />
            </Box>

            <Box sx={{ minWidth: 0 }}>
              {positions.length > 0 ? (
                <VolTermStructurePanel positions={positions} spotPrice={btcPrice || 0} />
              ) : (
                <Box sx={{ height: '100%' }} />
              )}
            </Box>

            <Box sx={{ minWidth: 0 }}>
              {positions.length > 0 ? (
                <VolSmilePanel positions={positions} spotPrice={btcPrice || 0} />
              ) : (
                <Box sx={{ height: '100%' }} />
              )}
            </Box>
          </Box>
        </CardContent >
      </Card >

      {/* F9: Roll Manager Modal */}
      <RollManagerModal
        open={rollModalOpen}
        position={rollPosition}
        onClose={() => { setRollModalOpen(false); setRollPosition(null); }}
        onRollComplete={() => { setRollModalOpen(false); setRollPosition(null); fetchPositions(); }}
      />

      {/* Delta Hedge Modal */}
      <HedgeDeltaModal
        open={hedgeModalOpen}
        delta={hedgeModalDelta}
        btcPrice={btcPrice}
        onClose={() => setHedgeModalOpen(false)}
        onSuccess={() => {
          setHedgeModalOpen(false);
          fetchPositions();
        }}
      />

      {/* Options Trading Activity Monitor */}
      {
        !turboMode && (
          <Box sx={{ mt: 2 }}>
            <Suspense fallback={<Box sx={{ p: 2, textAlign: 'center' }}>Loading activity panel...</Box>}>
              <OptionsActivityPanel refreshTrigger={0} />
            </Suspense>
          </Box>
        )
      }

      {/* ARCH-2: Extracted ClosePositionDialog component */}
      <ClosePositionDialog
        open={closeDialog.open}
        position={closeDialog.position}
        onClose={() => setCloseDialog({ open: false, position: null })}
        onConfirm={confirmClose}
      />

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

      {/* Sound Settings Panel */}
      <SoundSettingsPanel
        open={soundSettingsOpen}
        onClose={() => setSoundSettingsOpen(false)}
      />

      {/* Trade Notification — DISABLED (was too intrusive, mid-screen blocking popup) */}
      {/* <TradeNotification notification={tradeNotification} onDismiss={() => setTradeNotification(null)} /> */}

      {/* Position Adjustment Page */}
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
    </div >
  );
};

export default OptionsPanel;
