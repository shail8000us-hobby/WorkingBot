/**
 * Options Payoff Diagram - Sensibull Style
 *
 * Features:
 * - Dual lines: "On Expiry" (green/red based on profit/loss) + "On Target Date" (blue)
 * - Interactive date slider to see P&L at any point between now and expiry
 * - Color-coded expiry area: Green fill above zero, Red fill below zero
 * - Projected profit display at current spot
 * - Real IV calculation from market prices
 *
 * @version 4.0.0 - Extracted math + alert dialog, fixed blue line
 */

import React, { useMemo, useState, useCallback, useEffect, useRef } from 'react';
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Area,
  ComposedChart,
  Line,
  ReferenceArea,
} from 'recharts';
import {
  Box, Typography, Paper, Chip, IconButton, Switch, FormControlLabel, Slider,
  TextField, Button, ClickAwayListener,
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import ZoomOutIcon from '@mui/icons-material/ZoomOut';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import MonetizationOnOutlinedIcon from '@mui/icons-material/MonetizationOnOutlined';
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded';
import TrackChangesRoundedIcon from '@mui/icons-material/TrackChangesRounded';
import CompareArrowsRoundedIcon from '@mui/icons-material/CompareArrowsRounded';
import CasinoRoundedIcon from '@mui/icons-material/CasinoRounded';
import EditNoteRoundedIcon from '@mui/icons-material/EditNoteRounded';
import AlertsPanel from './AlertsPanel';
import PayoffAlertDialog from './PayoffAlertDialog';
import PayoffControls from './PayoffControls';
import {
  calculatePortfolioDelta,
  calculatePortfolioTheta,
  calculatePortfolioGamma,
} from './payoffCalculator';
import { useParsedPositions, useChartData } from './usePayoffData';
import usePayoffAlerts from './usePayoffAlerts';

// ============================================================================
// MAIN COMPONENT
// ============================================================================

const OptionsPayoffDiagram = ({
  positions,
  selectedPositions = [],
  futuresPositions = [],
  indexPrices = { BTC: 0, ETH: 0 },
  manualPnL = 0,
  onManualPnLChange,
  batchOrderSection = null,
}) => {
  const [priceRangePercent, setPriceRangePercent] = useState(20);
  const [targetDaysFromNow, setTargetDaysFromNow] = useState(0); // Slider value in days (supports decimals for hours)
  const [targetPricePercent, setTargetPricePercent] = useState(0); // Target price offset from spot (-50% to +50%)

  // Zoom state
  const [isZoomed, setIsZoomed] = useState(false);
  const [zoomDomain, setZoomDomain] = useState({ left: null, right: null });

  // Selection state for drag-to-zoom
  const [selectionStart, setSelectionStart] = useState(null);
  const [selectionEnd, setSelectionEnd] = useState(null);
  const [isSelecting, setIsSelecting] = useState(false);

  // Alert creation state (from chart click)
  const [alertDialogOpen, setAlertDialogOpen] = useState(false);
  const [alertPrice, setAlertPrice] = useState(null);
  const [alertPnLExpiry, setAlertPnLExpiry] = useState(null);
  const [alertPnLTarget, setAlertPnLTarget] = useState(null);
  const [activeAlerts, setActiveAlerts] = useState([]);
  const [alertsRefreshTrigger, setAlertsRefreshTrigger] = useState(0);

  // Positions section visibility toggle
  const [showPositionsSection, setShowPositionsSection] = useState(true);

  // Phase E: Advanced feature toggles
  const [showMultiDate, setShowMultiDate] = useState(true);
  const [showProbDist, setShowProbDist] = useState(true);

  // E5: Scenario comparison — offset sliders + dashed comparison curve
  const [scenarioCompare, setScenarioCompare] = useState(false);
  const [compareSpotPct, setCompareSpotPct] = useState(0);   // ±% from current target
  const [compareTimeDays, setCompareTimeDays] = useState(0); // extra days forward
  const baselineRef = useRef(null); // kept for reset logic

  // Manual PnL offset control state (popover)
  const [manualPnLOpen, setManualPnLOpen] = useState(false);
  const [manualPnLInput, setManualPnLInput] = useState('');

  // ========================================================================
  // D2: Data computation via extracted hooks (usePayoffData.js)
  // ========================================================================
  const parsedPositions = useParsedPositions(positions, selectedPositions, futuresPositions, indexPrices);
  const chartData = useChartData(parsedPositions, {
    priceRangePercent, targetDaysFromNow, targetPricePercent,
    showMultiDate, showProbDist, futuresPositions,
  });

  // E5: Scenario comparison — second chart with offset params (unconditional hook call)
  const scenarioChartData = useChartData(parsedPositions, {
    priceRangePercent,
    targetDaysFromNow: targetDaysFromNow + compareTimeDays,
    targetPricePercent: targetPricePercent + compareSpotPct,
    showMultiDate: false,
    showProbDist: false,
    futuresPositions,
  });

  // F6: Compute furthest-expiry for time slider (fixes slider max = only nearest expiry bug)
  const { maxDaysToExpiry, furthestExpiry, allExpiryMarks } = useMemo(() => {
    const positions_ = parsedPositions?.positions;
    if (!positions_?.length) return { maxDaysToExpiry: null, furthestExpiry: null, allExpiryMarks: null };
    const now = new Date();
    // unique expiry dates, sorted ascending
    const seen = new Set();
    const expiries = [];
    positions_.filter(p => !p.isClosed).forEach(p => {
      const key = p.expiryDate.toISOString().split('T')[0];
      if (!seen.has(key)) { seen.add(key); expiries.push(p.expiryDate); }
    });
    expiries.sort((a, b) => a - b);
    if (!expiries.length) return { maxDaysToExpiry: null, furthestExpiry: null, allExpiryMarks: null };
    const maxD = (expiries[expiries.length - 1] - now) / 86400000;
    const marks = [
      { value: 0, label: 'Now' },
      ...expiries.map(d => {
        const days = (d - now) / 86400000;
        const lbl = days < 1 ? `${Math.round(days * 24)}h` : d.toLocaleDateString('en-US', { day: '2-digit', month: 'short' });
        return { value: days, label: lbl };
      }),
    ];
    return { maxDaysToExpiry: maxD, furthestExpiry: expiries[expiries.length - 1], allExpiryMarks: marks };
  }, [parsedPositions?.positions]);

  // E5: Reset offsets when compare mode is turned off
  useEffect(() => {
    if (!scenarioCompare) {
      setCompareSpotPct(0);
      setCompareTimeDays(0);
      baselineRef.current = null;
    }
  }, [scenarioCompare]);

  // Merge scenario chart data as dashed comparison overlay
  const enrichedData = useMemo(() => {
    if (!chartData?.data || !scenarioCompare || !scenarioChartData?.data) {
      return chartData?.data;
    }
    // Build a price→scenarioPnL lookup from scenarioChartData
    const scenarioMap = {};
    for (const pt of scenarioChartData.data) {
      scenarioMap[pt.price] = {
        expiry: (pt.expiryGreen ?? pt.expiryRed ?? 0),
        target: pt.target ?? 0,
      };
    }
    return chartData.data.map((pt) => {
      const sc = scenarioMap[pt.price];
      if (sc) return { ...pt, baselineExpiry: sc.expiry, baselineTarget: sc.target };
      return pt;
    });
  }, [chartData, scenarioCompare, scenarioChartData]);

  // D3: Alert management via extracted hook (usePayoffAlerts.js)
  // Note: We keep inline state for now to avoid breaking changes, but the hook is ready
  // for future use when alert functionality is further decoupled.
  const fetchAlerts = useCallback(async () => {
    try {
      const response = await fetch('/api/alerts');
      const data = await response.json();
      if (data.success) {
        setActiveAlerts(data.alerts || []);
      }
    } catch (err) {
      console.error('Failed to fetch alerts:', err);
    }
  }, []);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts, alertsRefreshTrigger]);

  const currentExpiryStr = useMemo(() =>
    chartData?.nearestExpiry ? new Date(chartData.nearestExpiry).toISOString().split('T')[0] : null
    , [chartData?.nearestExpiry]);

  const filteredAlerts = useMemo(() => {
    if (!currentExpiryStr) return activeAlerts.filter(a => a.status === 'active');
    return activeAlerts.filter(a =>
      a.status === 'active' && (a.expiry_date === currentExpiryStr || !a.expiry_date)
    );
  }, [activeAlerts, currentExpiryStr]);

  // ========================================================================
  // ZOOM HANDLERS
  // ========================================================================

  // Handle mouse down on chart (start selection)
  const handleMouseDown = useCallback((e) => {
    if (e && e.activeLabel) {
      setSelectionStart(e.activeLabel);
      setSelectionEnd(e.activeLabel);
      setIsSelecting(true);
    }
  }, []);

  // Handle mouse move on chart (update selection)
  const handleMouseMove = useCallback(
    (e) => {
      if (isSelecting && e && e.activeLabel) {
        setSelectionEnd(e.activeLabel);
      }
    },
    [isSelecting]
  );

  // Handle mouse up on chart (complete zoom or create alert on click)
  const handleMouseUp = useCallback((e) => {
    if (isSelecting && selectionStart !== null && selectionEnd !== null) {
      const left = Math.min(selectionStart, selectionEnd);
      const right = Math.max(selectionStart, selectionEnd);

      // Only zoom if selection is meaningful (at least 1% of range)
      const isDrag = right - left > (chartData?.maxPrice - chartData?.minPrice) * 0.01;

      if (isDrag) {
        setZoomDomain({ left, right });
        setIsZoomed(true);
      } else if (e && e.activePayload && e.activePayload[0]) {
        // Simple click (not a drag) - open alert dialog
        const payload = e.activePayload[0].payload;
        if (payload) {
          setAlertPrice(payload.price);
          setAlertPnLExpiry(payload.expiry || 0);
          setAlertPnLTarget(payload.target || 0);
          setAlertDialogOpen(true);
        }
      }
    }
    setSelectionStart(null);
    setSelectionEnd(null);
    setIsSelecting(false);
  }, [isSelecting, selectionStart, selectionEnd, chartData]);

  // Reset zoom
  const handleResetZoom = useCallback(() => {
    setZoomDomain({ left: null, right: null });
    setIsZoomed(false);
  }, []);

  // Zoom in (reduce range by 50%, centered on current view)
  const handleZoomIn = useCallback(() => {
    if (!chartData) return;

    const { minPrice, maxPrice, spotPrice } = chartData;
    const currentLeft = isZoomed && zoomDomain.left ? zoomDomain.left : minPrice;
    const currentRight = isZoomed && zoomDomain.right ? zoomDomain.right : maxPrice;
    const currentCenter = (currentLeft + currentRight) / 2;
    const currentRange = currentRight - currentLeft;
    const newRange = currentRange * 0.5; // Reduce by 50%

    // Ensure minimum zoom range (at least $2000 for BTC)
    if (newRange < 2000) return;

    const newLeft = Math.max(minPrice, currentCenter - newRange / 2);
    const newRight = Math.min(maxPrice, currentCenter + newRange / 2);

    setZoomDomain({ left: newLeft, right: newRight });
    setIsZoomed(true);
  }, [chartData, isZoomed, zoomDomain]);

  // Zoom out (increase range by 100%, centered on current view)
  const handleZoomOut = useCallback(() => {
    if (!chartData) return;

    const { minPrice, maxPrice } = chartData;

    if (!isZoomed) return; // Can't zoom out if not zoomed

    const currentLeft = zoomDomain.left || minPrice;
    const currentRight = zoomDomain.right || maxPrice;
    const currentCenter = (currentLeft + currentRight) / 2;
    const currentRange = currentRight - currentLeft;
    const newRange = currentRange * 2; // Double the range

    let newLeft = currentCenter - newRange / 2;
    let newRight = currentCenter + newRange / 2;

    // If we've zoomed out to full range, reset zoom
    if (newLeft <= minPrice && newRight >= maxPrice) {
      handleResetZoom();
      return;
    }

    // Clamp to bounds
    newLeft = Math.max(minPrice, newLeft);
    newRight = Math.min(maxPrice, newRight);

    setZoomDomain({ left: newLeft, right: newRight });
  }, [chartData, isZoomed, zoomDomain, handleResetZoom]);

  // Toggle zoom (zoom in to center 50% or zoom out)
  const handleToggleZoom = useCallback(() => {
    if (isZoomed) {
      handleResetZoom();
    } else if (chartData) {
      const { minPrice, maxPrice, spotPrice } = chartData;
      const range = maxPrice - minPrice;
      // Zoom to 50% range centered on spot
      const left = Math.max(minPrice, spotPrice - range * 0.25);
      const right = Math.min(maxPrice, spotPrice + range * 0.25);
      setZoomDomain({ left, right });
      setIsZoomed(true);
    }
  }, [isZoomed, chartData, handleResetZoom]);

  // Get filtered data based on zoom (uses enrichedData for scenario overlay)
  const displayData = useMemo(() => {
    const sourceData = enrichedData || chartData?.data;
    if (!sourceData) return [];
    if (!isZoomed || !zoomDomain.left || !zoomDomain.right) {
      return sourceData;
    }
    return sourceData.filter((d) => d.price >= zoomDomain.left && d.price <= zoomDomain.right);
  }, [enrichedData, chartData, isZoomed, zoomDomain]);

  // Apply manual PnL offset to all displayData points (display-only, no trading effect)
  const shiftedDisplayData = useMemo(() => {
    if (!displayData || manualPnL === 0) return displayData;
    return displayData.map(pt => {
      const rawExpiry = pt.expiry !== undefined ? pt.expiry + manualPnL : undefined;
      return {
        ...pt,
        ...(rawExpiry !== undefined ? {
          expiry: rawExpiry,
          expiryProfit: rawExpiry >= 0 ? rawExpiry : 0,
          expiryLoss: rawExpiry < 0 ? rawExpiry : 0,
          expiryGreen: rawExpiry >= 0 ? rawExpiry : null,
          expiryRed: rawExpiry <= 0 ? rawExpiry : null,
        } : {}),
        ...(pt.target !== undefined ? { target: pt.target + manualPnL } : {}),
        ...(pt.today !== undefined ? { today: pt.today + manualPnL } : {}),
        ...(pt.mid !== undefined ? { mid: pt.mid + manualPnL } : {}),
      };
    });
  }, [displayData, manualPnL]);

  // Compute breakevens from shifted data (where shifted expiry crosses zero)
  const displayBreakevens = useMemo(() => {
    if (manualPnL === 0) return null; // null = use original chartData.breakevens
    if (!shiftedDisplayData || shiftedDisplayData.length < 2) return [];
    const bps = [];
    for (let i = 1; i < shiftedDisplayData.length; i++) {
      const prev = shiftedDisplayData[i - 1];
      const curr = shiftedDisplayData[i];
      const prevVal = prev.expiry ?? 0;
      const currVal = curr.expiry ?? 0;
      if (prevVal !== currVal && prevVal * currVal < 0) {
        const t = Math.abs(prevVal) / (Math.abs(prevVal) + Math.abs(currVal));
        bps.push(Math.round(prev.price + t * (curr.price - prev.price)));
      }
    }
    return bps;
  }, [shiftedDisplayData, manualPnL]);

  // Calculate Y-axis domain for zoomed view (TRULY ADAPTIVE based on visible data)
  // This is critical - when user zooms to a small area, Y-axis MUST adapt
  const zoomedYDomain = useMemo(() => {
    if (!shiftedDisplayData || shiftedDisplayData.length === 0) {
      return [(chartData?.yMin || -10) + manualPnL, (chartData?.yMax || 10) + manualPnL];
    }

    let minY = Infinity,
      maxY = -Infinity;
    shiftedDisplayData.forEach((d) => {
      if (d.expiry < minY) minY = d.expiry;
      if (d.expiry > maxY) maxY = d.expiry;
      if (d.target < minY) minY = d.target;
      if (d.target > maxY) maxY = d.target;
      // Include multi-date overlay lines in zoom bounds
      if (d.today !== undefined) {
        if (d.today < minY) minY = d.today;
        if (d.today > maxY) maxY = d.today;
      }
      if (d.mid !== undefined) {
        if (d.mid < minY) minY = d.mid;
        if (d.mid > maxY) maxY = d.mid;
      }
    });

    // Handle edge case where min/max are the same or very close
    const dataRange = maxY - minY;
    if (dataRange < 0.5) {
      // If range is tiny (essentially a flat line), create symmetric range around it
      const center = (maxY + minY) / 2;
      const smallPadding = Math.max(Math.abs(center) * 0.2, 2); // 20% or at least $2
      return [center - smallPadding, center + smallPadding];
    }

    // Add PROPORTIONAL padding - more padding for smaller ranges to make them readable
    // Smaller ranges get larger relative padding
    const paddingPercent = dataRange < 5 ? 0.5 : dataRange < 20 ? 0.35 : 0.2;
    const padding = dataRange * paddingPercent;

    // Ensure zero is visible if data crosses zero
    let yMin = minY - padding;
    let yMax = maxY + padding;

    // If data is all positive but close to zero, show some negative
    if (minY >= 0 && minY < 5) yMin = Math.min(-2, yMin);
    // If data is all negative but close to zero, show some positive
    if (maxY <= 0 && maxY > -5) yMax = Math.max(2, yMax);

    // Adaptive: fit tightly around data, always include zero
    return [yMin, yMax];
  }, [shiftedDisplayData, chartData, manualPnL]);

  // ========================================================================
  // RENDER
  // ========================================================================

  if (!chartData) {
    return (
      <Paper sx={{ p: 3, textAlign: 'center', bgcolor: 'background.default' }}>
        <Typography color="text.secondary">
          Select positions using checkboxes to display payoff diagram
        </Typography>
      </Paper>
    );
  }

  const {
    spotPrice,
    targetPrice,
    maxProfit,
    maxLoss,
    breakevens,
    projectedProfit,
    profitPct,
    targetDate,
    daysToExpiryFromTarget,
    minDaysToExpiry,
    nearestExpiry,
    yMin,
    yMax,
    probabilityOfProfit,
    parsedPositions: chartPositions,
  } = chartData;

  // Manual PnL display stats — shifted values for UI only, zero trading effect
  const displayMaxProfit = isFinite(maxProfit) ? maxProfit + manualPnL : maxProfit;
  const displayMaxLoss = isFinite(maxLoss) ? maxLoss + manualPnL : maxLoss;
  const displayProjectedProfit = projectedProfit + manualPnL;
  const rawProfitPct = parseFloat(profitPct);
  const totalPremiumForPct = (rawProfitPct !== 0 && projectedProfit !== 0)
    ? (projectedProfit / rawProfitPct) * 100
    : null;
  const displayProfitPct = totalPremiumForPct
    ? ((displayProjectedProfit / totalPremiumForPct) * 100).toFixed(2)
    : profitPct;
  const displayBreakevensResolved = displayBreakevens !== null ? displayBreakevens : breakevens;

  const hasRewardRisk = isFinite(displayMaxProfit) && isFinite(displayMaxLoss) && displayMaxLoss !== 0;
  const rewardRiskRatio = hasRewardRisk ? Math.abs(displayMaxProfit / displayMaxLoss) : null;
  const rrIsFavorable = hasRewardRisk ? displayMaxProfit > Math.abs(displayMaxLoss) : false;
  const rrIsUnfavorable = hasRewardRisk ? displayMaxProfit < Math.abs(displayMaxLoss) : false;
  const rrStatusTone = rrIsFavorable ? 'success' : rrIsUnfavorable ? 'danger' : 'neutral';
  const rrStatusLabel = rrIsFavorable ? 'Fav' : rrIsUnfavorable ? 'Unfav' : 'Neutral';
  const popTone = probabilityOfProfit >= 50 ? 'success' : 'danger';
  const popStatusLabel = probabilityOfProfit >= 50 ? 'Fav' : 'Unfav';
  const profitCapLabel = isFinite(displayMaxProfit) && displayMaxProfit > 0 ? 'Capped' : 'Unlimited';
  const lossCapLabel = isFinite(displayMaxLoss) && displayMaxLoss < 0 ? 'Capped' : 'Unlimited';

  const tonePalette = {
    success: {
      border: alpha('#10b981', 0.45),
      bg: alpha('#10b981', 0.12),
      label: alpha('#cbd5e1', 0.92),
      value: '#34d399',
      chipBg: alpha('#10b981', 0.2),
      chipText: '#6ee7b7',
    },
    danger: {
      border: alpha('#ef4444', 0.45),
      bg: alpha('#ef4444', 0.12),
      label: alpha('#cbd5e1', 0.92),
      value: '#f87171',
      chipBg: alpha('#ef4444', 0.2),
      chipText: '#fca5a5',
    },
    warning: {
      border: alpha('#f59e0b', 0.45),
      bg: alpha('#f59e0b', 0.12),
      label: alpha('#cbd5e1', 0.92),
      value: '#fbbf24',
      chipBg: alpha('#f59e0b', 0.2),
      chipText: '#fcd34d',
    },
    info: {
      border: alpha('#3b82f6', 0.45),
      bg: alpha('#3b82f6', 0.12),
      label: alpha('#cbd5e1', 0.92),
      value: '#60a5fa',
      chipBg: alpha('#3b82f6', 0.2),
      chipText: '#93c5fd',
    },
    neutral: {
      border: alpha('#64748b', 0.5),
      bg: alpha('#475569', 0.14),
      label: alpha('#cbd5e1', 0.88),
      value: alpha('#cbd5e1', 0.95),
      chipBg: alpha('#64748b', 0.22),
      chipText: alpha('#cbd5e1', 0.9),
    },
    indigo: {
      border: alpha('#818cf8', 0.5),
      bg: alpha('#6366f1', 0.16),
      label: alpha('#cbd5e1', 0.92),
      value: '#a5b4fc',
      chipBg: alpha('#818cf8', 0.22),
      chipText: '#c7d2fe',
    },
  };

  const metricLabelSx = {
    fontSize: '0.68rem',
    fontWeight: 900,
    letterSpacing: '0.06em',
    textTransform: 'uppercase',
    lineHeight: 1,
    whiteSpace: 'nowrap',
  };

  const metricValueSx = (color) => ({
    color,
    fontSize: '1.03rem',
    fontWeight: 900,
    lineHeight: 1,
    fontVariantNumeric: 'tabular-nums',
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
    whiteSpace: 'nowrap',
  });

  const metricMetaSx = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 0.5,
    minWidth: 0,
  };

  const metricIconWrapSx = (tone = 'neutral') => ({
    width: 20,
    height: 20,
    borderRadius: '50%',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    bgcolor: tonePalette[tone]?.chipBg || tonePalette.neutral.chipBg,
    border: `1px solid ${tonePalette[tone]?.border || tonePalette.neutral.border}`,
    flexShrink: 0,
  });

  const metricIconSx = (tone = 'neutral') => ({
    fontSize: 13,
    color: tonePalette[tone]?.value || tonePalette.neutral.value,
  });

  const metricPillSx = (tone = 'neutral') => {
    const palette = tonePalette[tone] || tonePalette.neutral;
    return {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 0.9,
      px: 1.35,
      py: 0.85,
      minHeight: 44,
      borderRadius: 999,
      border: `1px solid ${palette.border}`,
      bgcolor: alpha('#020617', 0.42),
      backgroundImage: `linear-gradient(180deg, ${alpha(palette.value, 0.16)} 0%, ${alpha('#020617', 0.28)} 100%)`,
      boxShadow: `
        inset 0 1px 0 ${alpha('#e2e8f0', 0.1)},
        0 0 0 1px ${alpha(palette.value, 0.18)},
        0 0 16px ${alpha(palette.value, 0.22)}
      `,
      transition: 'border-color 160ms ease, background-color 160ms ease, transform 160ms ease, box-shadow 160ms ease',
      scrollSnapAlign: 'start',
      '&:hover': {
        transform: 'translateY(-2px)',
        borderColor: alpha(palette.border, 0.95),
        boxShadow: `
          inset 0 1px 0 ${alpha('#e2e8f0', 0.12)},
          0 0 0 1px ${alpha(palette.value, 0.3)},
          0 0 24px ${alpha(palette.value, 0.32)}
        `,
      },
    };
  };

  // Custom Tooltip - Sensibull Style
  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload || !payload.length) return null;

    const expiryGreen = payload.find((p) => p.dataKey === 'expiryGreen')?.value;
    const expiryRed = payload.find((p) => p.dataKey === 'expiryRed')?.value;
    const expiry = expiryGreen ?? expiryRed ?? 0;  // One will be non-null
    const target = payload.find((p) => p.dataKey === 'target')?.value ?? 0;
    const today = payload.find((p) => p.dataKey === 'today')?.value;
    const mid = payload.find((p) => p.dataKey === 'mid')?.value;
    const currentPrice = Number(label);

    // C2: Calculate portfolio Greeks at hovered price
    const delta = chartPositions ? calculatePortfolioDelta(currentPrice, chartPositions, targetDaysFromNow) : 0;
    const gamma = chartPositions ? calculatePortfolioGamma(currentPrice, chartPositions, targetDaysFromNow) : 0;
    const theta = chartPositions ? calculatePortfolioTheta(currentPrice, chartPositions, targetDaysFromNow) : 0;

    // Calculate price change from spot
    const priceChange = currentPrice - spotPrice;
    const priceChangePct = ((priceChange / spotPrice) * 100).toFixed(2);
    const priceChangeSign = priceChange >= 0 ? '+' : '';

    // ── Smart time-aware labelling ────────────────────────────────────────
    // For near-expiry options the labels must reflect real time remaining
    // rather than generic "Today / Mid-expiry / Expiry date" labels.
    const hoursToExpiry = minDaysToExpiry * 24;
    const isNearExpiry = hoursToExpiry < 24;   // < 1 day left

    // Target-date label: "Today (now)" when slider is at 0, formatted date otherwise
    const isTargetToday = targetDaysFromNow <= 0.001;
    const targetDateFormatted = isTargetToday
      ? (isNearExpiry
        ? `Now  (${hoursToExpiry >= 1
          ? `${hoursToExpiry.toFixed(0)}h to exp`
          : `${(hoursToExpiry * 60).toFixed(0)}m to exp`})`
        : 'Today (now)')
      : (targetDate
        ? targetDate.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' })
        : 'Today (now)');

    // "Today (now)" overlay label — shown when slider was moved off zero
    const todayLabel = isNearExpiry
      ? `Now (${hoursToExpiry >= 1
        ? `~${hoursToExpiry.toFixed(0)}h to exp`
        : `~${(hoursToExpiry * 60).toFixed(0)}m to exp`})`
      : 'Today (now)';

    // Mid-expiry label — show real time for near-expiry, else keep generic label
    const midHours = (minDaysToExpiry * 0.5) * 24;
    const midLabel = isNearExpiry
      ? (midHours >= 1
        ? `In ~${midHours.toFixed(0)}h`
        : `In ~${(midHours * 60).toFixed(0)}m`)
      : 'Mid-expiry';

    return (
      <Paper
        sx={{
          p: 0,
          bgcolor: 'rgba(17, 24, 39, 0.95)',
          border: '1px solid rgba(75, 85, 99, 0.5)',
          borderRadius: 2,
          minWidth: 180,
          backdropFilter: 'blur(8px)',
          boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
        }}
      >
        {/* Price header */}
        <Box sx={{ p: 1.25, borderBottom: '1px solid rgba(75, 85, 99, 0.3)' }}>
          <Typography variant="caption" sx={{ color: 'rgba(156, 163, 175, 0.8)', display: 'block', mb: 0.25 }}>
            When price is at
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1 }}>
            <Typography variant="h6" fontWeight="bold" sx={{ color: '#fff', lineHeight: 1 }}>
              {currentPrice.toLocaleString()}
            </Typography>
            <Typography
              variant="caption"
              sx={{
                color: priceChange >= 0 ? '#10b981' : '#ef4444',
                fontWeight: 600
              }}
            >
              {priceChangeSign}{priceChangePct}% ({priceChangeSign}{Math.abs(priceChange).toLocaleString(undefined, { maximumFractionDigits: 0 })})
            </Typography>
          </Box>
        </Box>

        {/* P&L section */}
        <Box sx={{ p: 1.25 }}>
          <Typography variant="caption" sx={{ color: 'rgba(156, 163, 175, 0.8)', display: 'block', mb: 0.75 }}>
            Expected P&L on
          </Typography>

          {/* Target date P&L */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.75 }}>
            <Typography variant="body2" sx={{ color: '#9ca3af' }}>
              {targetDateFormatted}
            </Typography>
            <Typography
              variant="body2"
              fontWeight="bold"
              sx={{ color: target >= 0 ? '#10b981' : '#ef4444' }}
            >
              {target >= 0 ? '+' : ''}{target.toFixed(2)}
            </Typography>
          </Box>

          {/* Today P&L (multi-date overlay) */}
          {today !== undefined && (
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.75 }}>
              <Typography variant="body2" sx={{ color: '#06b6d4' }}>
                {todayLabel}
              </Typography>
              <Typography
                variant="body2"
                fontWeight="bold"
                sx={{ color: today >= 0 ? '#10b981' : '#ef4444' }}
              >
                {today >= 0 ? '+' : ''}{today.toFixed(2)}
              </Typography>
            </Box>
          )}

          {/* Mid-expiry P&L (multi-date overlay) */}
          {mid !== undefined && (
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.75 }}>
              <Typography variant="body2" sx={{ color: '#818cf8' }}>
                {midLabel}
              </Typography>
              <Typography
                variant="body2"
                fontWeight="bold"
                sx={{ color: mid >= 0 ? '#10b981' : '#ef4444' }}
              >
                {mid >= 0 ? '+' : ''}{mid.toFixed(2)}
              </Typography>
            </Box>
          )}

          {/* Expiry P&L */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="body2" sx={{ color: '#9ca3af' }}>
              At expiry
            </Typography>
            <Typography
              variant="body2"
              fontWeight="bold"
              sx={{ color: expiry >= 0 ? '#10b981' : '#ef4444' }}
            >
              {expiry >= 0 ? '+' : ''}{expiry.toFixed(2)}
            </Typography>
          </Box>
        </Box>

        {/* C2: Greeks at hovered price */}
        {chartPositions && chartPositions.length > 0 && (
          <Box sx={{ p: 1.25, borderTop: '1px solid rgba(75, 85, 99, 0.3)' }}>
            <Box sx={{ display: 'flex', gap: 1.5, justifyContent: 'space-between' }}>
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="caption" sx={{ color: 'rgba(156,163,175,0.6)', fontSize: '0.6rem', display: 'block' }}>Δ Delta</Typography>
                <Typography variant="caption" fontWeight="bold" sx={{ color: delta >= 0 ? '#10b981' : '#ef4444' }}>
                  {delta >= 0 ? '+' : ''}{delta.toFixed(4)}
                </Typography>
              </Box>
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="caption" sx={{ color: 'rgba(156,163,175,0.6)', fontSize: '0.6rem', display: 'block' }}>Γ Gamma</Typography>
                <Typography variant="caption" fontWeight="bold" sx={{ color: '#a78bfa' }}>
                  {gamma.toFixed(6)}
                </Typography>
              </Box>
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="caption" sx={{ color: 'rgba(156,163,175,0.6)', fontSize: '0.6rem', display: 'block' }}>Θ Theta</Typography>
                <Typography variant="caption" fontWeight="bold" sx={{ color: theta >= 0 ? '#10b981' : '#ef4444' }}>
                  {/* Near-expiry theta blows up — clamp and flag with ~  */}
                  {isNearExpiry
                    ? (Math.abs(theta) > 999 ? `~${theta >= 0 ? '+' : '-'}∞/d` : `~${theta >= 0 ? '+' : ''}${theta.toFixed(2)}/d`)
                    : `${theta >= 0 ? '+' : ''}${theta.toFixed(4)}/d`
                  }
                </Typography>
              </Box>
            </Box>
          </Box>
        )}
      </Paper>
    );
  };



  return (
    <Paper sx={{ p: 2, bgcolor: 'background.paper', display: 'flex', flexDirection: 'column' }}>
      {/* Positions Used in Payoff - Show at top */}
      <Box sx={{ order: 2, mb: 1, p: 2, bgcolor: 'action.hover', borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: showPositionsSection ? 1.5 : 0 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="subtitle2" fontWeight="bold" sx={{ color: 'primary.main' }}>
              📊 Positions Used in This Payoff Graph
            </Typography>
            <Chip
              size="small"
              label="🔒 SEALED"
              sx={{
                height: 20,
                fontSize: '0.65rem',
                fontWeight: 700,
                bgcolor: 'rgba(16, 185, 129, 0.1)',
                color: '#10b981',
                border: '1px solid rgba(16, 185, 129, 0.3)',
              }}
            />
          </Box>
          <Chip
            size="small"
            label={showPositionsSection ? '▲ Hide' : '▼ Show'}
            onClick={() => setShowPositionsSection(v => !v)}
            sx={{
              height: 20,
              fontSize: '0.65rem',
              fontWeight: 600,
              cursor: 'pointer',
              bgcolor: 'transparent',
              color: 'text.secondary',
              border: '1px solid',
              borderColor: 'divider',
              '&:hover': { bgcolor: 'action.hover', color: 'text.primary' },
            }}
          />
        </Box>

        {showPositionsSection && parsedPositions?.positions && parsedPositions.positions.length > 0 && (() => {
          // C3: Detect multiple expiry dates for multi-expiry indicator
          const expiryDates = [...new Set(parsedPositions.positions.filter(p => !p.isClosed).map(p => p.expiryDate.toISOString().split('T')[0]))];
          const isMultiExpiry = expiryDates.length > 1;
          const nearestExpiryStr = parsedPositions.nearestExpiry?.toISOString().split('T')[0];

          return (
            <Box sx={{ mb: futuresPositions.length > 0 ? 1.5 : 0 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                  Options ({parsedPositions.positions.length}):
                </Typography>
                {isMultiExpiry && (
                  <Chip
                    size="small"
                    label={`${expiryDates.length} Expiries`}
                    sx={{
                      height: 18, fontSize: '0.6rem', fontWeight: 700,
                      bgcolor: 'rgba(251,191,36,0.15)', color: '#fbbf24',
                      border: '1px solid rgba(251,191,36,0.3)',
                    }}
                  />
                )}
              </Box>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
                {parsedPositions.positions.map((pos, idx) => {
                  const posExpiryStr = pos.expiryDate.toISOString().split('T')[0];
                  const isNearestExpiry = posExpiryStr === nearestExpiryStr;
                  const expiryLabel = pos.expiryDate.toLocaleDateString('en-US', { day: '2-digit', month: 'short' });
                  return (
                    <Chip
                      key={idx}
                      size="small"
                      sx={{
                        bgcolor: pos.type === 'call' ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)',
                        color: pos.type === 'call' ? '#10b981' : '#ef4444',
                        fontWeight: 500,
                        border: '1px solid',
                        borderColor: pos.type === 'call' ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)',
                      }}
                      label={
                        <span>
                          {pos.size > 0 ? '📈 Long' : '📉 Short'} {Math.abs(pos.size)} {pos.type.toUpperCase()} ${pos.strike.toLocaleString()}
                          {isMultiExpiry && (
                            <span style={{
                              marginLeft: 4, fontSize: '0.6rem', padding: '1px 4px',
                              borderRadius: 3, fontWeight: 700,
                              backgroundColor: isNearestExpiry ? 'rgba(239,68,68,0.25)' : 'rgba(59,130,246,0.25)',
                              color: isNearestExpiry ? '#fca5a5' : '#93c5fd',
                            }}>
                              {expiryLabel}{isNearestExpiry ? ' ⏰' : ''}
                            </span>
                          )}
                        </span>
                      }
                    />
                  );
                })}
              </Box>
            </Box>
          );
        })()}

        {showPositionsSection && futuresPositions.length > 0 && (
          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5, fontWeight: 600 }}>
              Futures ({futuresPositions.length}):
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
              {futuresPositions.map((pos, idx) => (
                <Chip
                  key={idx}
                  size="small"
                  sx={{
                    bgcolor: 'rgba(59,130,246,0.15)',
                    color: '#3b82f6',
                    fontWeight: 500,
                    border: '1px solid',
                    borderColor: 'rgba(59,130,246,0.3)',
                  }}
                  label={`${pos.size > 0 ? '📈 Long' : '📉 Short'} ${Math.abs(pos.size)} ${pos.product_symbol} @ $${parseFloat(pos.entry_price).toLocaleString()}`}
                />
              ))}
            </Box>
          </Box>
        )}

        {showPositionsSection && (!parsedPositions?.positions || parsedPositions.positions.length === 0) && futuresPositions.length === 0 && (
          <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>
            No positions selected. Check the boxes next to positions to include them in the payoff graph.
          </Typography>
        )}
      </Box>

      {/* Compact Metrics Strip - Unified component style */}
      <Box
        sx={{
          mb: 2,
          display: 'flex',
          alignItems: 'center',
          flexWrap: { xs: 'wrap', xl: 'nowrap' },
          gap: 1.1,
          p: 1.45,
          bgcolor: alpha('#020617', 0.86),
          backgroundImage: `
            radial-gradient(circle at 8% 0%, ${alpha('#38bdf8', 0.2)} 0%, transparent 38%),
            radial-gradient(circle at 92% 0%, ${alpha('#a78bfa', 0.2)} 0%, transparent 40%),
            linear-gradient(180deg, ${alpha('#0f172a', 0.9)} 0%, ${alpha('#020617', 0.95)} 100%)
          `,
          borderRadius: 2.3,
          border: `1px solid ${alpha('#60a5fa', 0.45)}`,
          boxShadow: `
            inset 0 1px 0 ${alpha('#e2e8f0', 0.12)},
            0 0 0 1px ${alpha('#60a5fa', 0.18)},
            0 14px 30px ${alpha('#000', 0.5)},
            0 0 24px ${alpha('#60a5fa', 0.16)}
          `,
          overflowX: 'auto',
          scrollSnapType: 'x proximity',
        }}
      >
        {/* Profit Potential */}
        <Box sx={metricPillSx('success')}>
          <Box sx={metricMetaSx}>
            <Box sx={metricIconWrapSx('success')}>
              <MonetizationOnOutlinedIcon sx={metricIconSx('success')} />
            </Box>
            <Typography variant="caption" sx={{ ...metricLabelSx, color: tonePalette.success.label }}>
              Max Profit
            </Typography>
          </Box>
          <Typography sx={metricValueSx(tonePalette.success.value)}>
            {isFinite(displayMaxProfit) && displayMaxProfit > 0
              ? `+$${displayMaxProfit.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
              : '∞'}
          </Typography>
          <Chip
            size="small"
            label={profitCapLabel}
            sx={{
              height: 20,
              fontSize: '0.65rem',
              fontWeight: 800,
              borderRadius: 999,
              bgcolor: tonePalette.success.chipBg,
              color: tonePalette.success.chipText,
              border: `1px solid ${alpha('#10b981', 0.42)}`,
            }}
          />
        </Box>

        {/* Risk Exposure */}
        <Box sx={metricPillSx('danger')}>
          <Box sx={metricMetaSx}>
            <Box sx={metricIconWrapSx('danger')}>
              <WarningAmberRoundedIcon sx={metricIconSx('danger')} />
            </Box>
            <Typography variant="caption" sx={{ ...metricLabelSx, color: tonePalette.danger.label }}>
              Max Loss
            </Typography>
          </Box>
          <Typography sx={metricValueSx(tonePalette.danger.value)}>
            {isFinite(displayMaxLoss) && displayMaxLoss < 0
              ? `$${displayMaxLoss.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
              : '∞'}
          </Typography>
          <Chip
            size="small"
            label={lossCapLabel}
            sx={{
              height: 20,
              fontSize: '0.65rem',
              fontWeight: 800,
              borderRadius: 999,
              bgcolor: tonePalette.danger.chipBg,
              color: tonePalette.danger.chipText,
              border: `1px solid ${alpha('#ef4444', 0.42)}`,
            }}
          />
        </Box>

        {/* Breakeven Points - Always expanded inline */}
        <Box
          sx={{
            ...metricPillSx('warning'),
            alignItems: 'center',
            flexWrap: 'wrap',
            rowGap: 0.45,
            maxWidth: '100%',
          }}
        >
          <Box sx={metricMetaSx}>
            <Box sx={metricIconWrapSx('warning')}>
              <TrackChangesRoundedIcon sx={metricIconSx('warning')} />
            </Box>
            <Typography variant="caption" sx={{ ...metricLabelSx, color: tonePalette.warning.label }}>
              Breakeven
            </Typography>
          </Box>
          {displayBreakevensResolved.length > 0 ? (
            <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center', flexWrap: 'wrap' }}>
              {displayBreakevensResolved.map((be, idx) => {
                const bePercent = ((be / spotPrice - 1) * 100).toFixed(1);
                const sign = bePercent >= 0 ? '+' : '';
                return (
                  <Chip
                    key={idx}
                    size="small"
                    label={`$${be.toLocaleString()} (${sign}${bePercent}%)`}
                    sx={{
                      height: 21,
                      fontSize: '0.69rem',
                      fontWeight: 800,
                      borderRadius: 999,
                      bgcolor: tonePalette.warning.chipBg,
                      color: tonePalette.warning.chipText,
                      border: `1px solid ${alpha('#f59e0b', 0.35)}`,
                    }}
                  />
                );
              })}
            </Box>
          ) : (
            <Typography sx={metricValueSx(alpha('#94a3b8', 0.92))}>N/A</Typography>
          )}
        </Box>

        {/* Reward/Risk Ratio */}
        <Box sx={metricPillSx('info')}>
          <Box sx={metricMetaSx}>
            <Box sx={metricIconWrapSx('info')}>
              <CompareArrowsRoundedIcon sx={metricIconSx('info')} />
            </Box>
            <Typography variant="caption" sx={{ ...metricLabelSx, color: tonePalette.info.label }}>
              R:R
            </Typography>
          </Box>
          {hasRewardRisk ? (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
              <Typography sx={metricValueSx(tonePalette.info.value)}>
                {rewardRiskRatio.toFixed(2)}:1
              </Typography>
              <Chip
                size="small"
                label={rrStatusLabel}
                sx={{
                  height: 20,
                  fontSize: '0.66rem',
                  fontWeight: 800,
                  borderRadius: 999,
                  bgcolor: tonePalette[rrStatusTone].chipBg,
                  color: tonePalette[rrStatusTone].chipText,
                  border: `1px solid ${tonePalette[rrStatusTone].border}`,
                }}
              />
            </Box>
          ) : (
            <Typography sx={metricValueSx(alpha('#94a3b8', 0.92))}>N/A</Typography>
          )}
        </Box>

        {/* B4: Probability of Profit (PoP) */}
        {probabilityOfProfit !== null && probabilityOfProfit !== undefined && (
          <Box sx={metricPillSx(popTone)}>
            <Box sx={metricMetaSx}>
              <Box sx={metricIconWrapSx(popTone)}>
                <CasinoRoundedIcon sx={metricIconSx(popTone)} />
              </Box>
              <Typography
                variant="caption"
                sx={{
                  ...metricLabelSx,
                  color: probabilityOfProfit >= 50 ? tonePalette.success.label : tonePalette.danger.label,
                }}
              >
                PoP
              </Typography>
            </Box>
            <Typography sx={metricValueSx(popTone === 'success' ? tonePalette.success.value : tonePalette.danger.value)}>
              {probabilityOfProfit.toFixed(1)}%
            </Typography>
            <Chip
              size="small"
              label={popStatusLabel}
              sx={{
                height: 20,
                fontSize: '0.66rem',
                fontWeight: 800,
                borderRadius: 999,
                bgcolor: tonePalette[popTone].chipBg,
                color: tonePalette[popTone].chipText,
                border: `1px solid ${tonePalette[popTone].border}`,
              }}
            />
          </Box>
        )}

        {/* Manual PnL offset control */}
        {onManualPnLChange && (
          <Box sx={{ position: 'relative', ml: { xs: 0, md: 'auto' } }}>
            <Box
              onClick={() => {
                setManualPnLInput(manualPnL === 0 ? '' : String(manualPnL));
                setManualPnLOpen(true);
              }}
              sx={{
                ...metricPillSx(manualPnL !== 0 ? 'indigo' : 'neutral'),
                cursor: 'pointer',
                '&:hover': {
                  ...metricPillSx(manualPnL !== 0 ? 'indigo' : 'neutral')['&:hover'],
                  bgcolor: manualPnL !== 0 ? alpha('#6366f1', 0.2) : alpha('#475569', 0.2),
                },
              }}
              role="button"
              tabIndex={0}
              aria-label="Open manual PnL offset editor"
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  setManualPnLInput(manualPnL === 0 ? '' : String(manualPnL));
                  setManualPnLOpen(true);
                }
              }}
            >
              <Box sx={metricMetaSx}>
                <Box sx={metricIconWrapSx(manualPnL !== 0 ? 'indigo' : 'neutral')}>
                  <EditNoteRoundedIcon sx={metricIconSx(manualPnL !== 0 ? 'indigo' : 'neutral')} />
                </Box>
                <Typography
                  variant="caption"
                  sx={{
                    ...metricLabelSx,
                    color: manualPnL !== 0 ? tonePalette.indigo.label : tonePalette.neutral.label,
                  }}
                >
                  Manual PnL
                </Typography>
              </Box>
              <Typography sx={metricValueSx(manualPnL !== 0 ? tonePalette.indigo.value : tonePalette.neutral.value)}>
                {manualPnL !== 0
                  ? `${manualPnL > 0 ? '+' : ''}$${manualPnL.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                  : 'Off'}
              </Typography>
              <Chip
                size="small"
                label={manualPnL !== 0 ? 'Active' : 'Off'}
                sx={{
                  height: 20,
                  fontSize: '0.65rem',
                  fontWeight: 800,
                  borderRadius: 999,
                  bgcolor: manualPnL !== 0 ? tonePalette.indigo.chipBg : tonePalette.neutral.chipBg,
                  color: manualPnL !== 0 ? tonePalette.indigo.chipText : tonePalette.neutral.chipText,
                  border: `1px solid ${manualPnL !== 0 ? alpha('#818cf8', 0.45) : alpha('#64748b', 0.42)}`,
                }}
              />
            </Box>
            {manualPnLOpen && (
              <ClickAwayListener onClickAway={() => setManualPnLOpen(false)}>
                <Paper elevation={8} sx={{
                  position: 'absolute', bottom: '110%', right: 0, zIndex: 1400,
                  p: 1.5, minWidth: 250, bgcolor: 'background.paper',
                  border: '1px solid', borderColor: 'divider', borderRadius: 1.5,
                }}>
                  <Typography variant="caption" sx={{ display: 'block', mb: 0.5, fontWeight: 600 }}>
                    Manual PnL Offset
                  </Typography>
                  <TextField
                    size="small" fullWidth type="number"
                    value={manualPnLInput}
                    onChange={(e) => setManualPnLInput(e.target.value)}
                    placeholder="e.g. +20.00"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        const v = parseFloat(manualPnLInput);
                        onManualPnLChange(isNaN(v) ? 0 : v);
                        setManualPnLOpen(false);
                      }
                      if (e.key === 'Escape') setManualPnLOpen(false);
                    }}
                    autoFocus
                    sx={{ mb: 0.75 }}
                  />
                  <Typography variant="caption" sx={{ display: 'block', mb: 1, color: 'text.secondary', fontSize: '0.7rem' }}>
                    Realized PnL from squared-off positions. Shifts payoff graph up/down without changing its shape.
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 1 }}>
                    <Button size="small" variant="contained" sx={{ flex: 1 }} onClick={() => {
                      const v = parseFloat(manualPnLInput);
                      onManualPnLChange(isNaN(v) ? 0 : v);
                      setManualPnLOpen(false);
                    }}>Apply</Button>
                    <Button size="small" variant="outlined" sx={{ flex: 1 }} onClick={() => {
                      onManualPnLChange(0);
                      setManualPnLOpen(false);
                    }}>Clear</Button>
                  </Box>
                </Paper>
              </ClickAwayListener>
            )}
          </Box>
        )}
      </Box>

      {/* Header with Legend */}
      <Box
        sx={{
          mb: 2,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 1,
        }}
      >
        <Typography variant="h6" fontWeight="bold">
          Payoff Graph
          {futuresPositions.length > 0 && (
            <Typography component="span" variant="caption" sx={{ ml: 1, color: '#3b82f6', fontWeight: 600 }}>
              (Options + Futures Combined)
            </Typography>
          )}
        </Typography>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
          {/* Legend */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Box
              sx={{
                width: 24,
                height: 3,
                background:
                  'linear-gradient(90deg, #ef4444 0%, #ef4444 50%, #10b981 50%, #10b981 100%)',
              }}
            />
            <Typography variant="caption" color="text.secondary">
              On Expiry
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Box sx={{ width: 24, height: 3, bgcolor: '#3b82f6' }} />
            <Typography variant="caption" color="text.secondary">
              {targetDaysFromNow <= 0.001 ? 'Today (now)' : 'On Target Date'}
            </Typography>
          </Box>
          {showMultiDate && (
            <>
              {targetDaysFromNow > 0.02 && (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Box sx={{ width: 24, height: 2, bgcolor: '#06b6d4' }} />
                  <Typography variant="caption" color="text.secondary">
                    {minDaysToExpiry * 24 < 24
                      ? `Now (~${(minDaysToExpiry * 24).toFixed(0)}h to exp)`
                      : 'Today (now)'}
                  </Typography>
                </Box>
              )}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Box sx={{ width: 24, height: 2, bgcolor: '#818cf8', opacity: 0.8 }} />
                <Typography variant="caption" color="text.secondary">
                  {minDaysToExpiry * 24 < 24
                    ? (minDaysToExpiry * 12 >= 1
                      ? `In ~${(minDaysToExpiry * 12).toFixed(0)}h`
                      : `In ~${(minDaysToExpiry * 12 * 60).toFixed(0)}m`)
                    : 'Mid-Expiry'}
                </Typography>
              </Box>
            </>
          )}
          {showProbDist && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <Box sx={{ width: 24, height: 8, bgcolor: '#a78bfa', opacity: 0.3, borderRadius: 0.5 }} />
              <Typography variant="caption" color="text.secondary">
                Prob. Zone
              </Typography>
            </Box>
          )}
          {scenarioCompare && scenarioChartData?.data && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <Box sx={{ width: 24, height: 2, bgcolor: '#9ca3af', borderStyle: 'dashed' }} />
              <Typography variant="caption" color="text.secondary">
                Baseline
              </Typography>
            </Box>
          )}

          {/* Feature toggles */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, ml: 1 }}>
            <FormControlLabel
              control={<Switch size="small" checked={showMultiDate} onChange={(e) => setShowMultiDate(e.target.checked)} sx={{ '& .MuiSwitch-track': { bgcolor: 'rgba(255,255,255,0.15)' } }} />}
              label={<Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>Time Decay</Typography>}
              sx={{ mx: 0, '& .MuiFormControlLabel-label': { ml: 0.25 } }}
            />
            <FormControlLabel
              control={<Switch size="small" checked={showProbDist} onChange={(e) => setShowProbDist(e.target.checked)} sx={{ '& .MuiSwitch-track': { bgcolor: 'rgba(255,255,255,0.15)' } }} />}
              label={<Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>Probability</Typography>}
              sx={{ mx: 0, '& .MuiFormControlLabel-label': { ml: 0.25 } }}
            />
            <FormControlLabel
              control={<Switch size="small" checked={scenarioCompare} onChange={(e) => setScenarioCompare(e.target.checked)} sx={{ '& .MuiSwitch-track': { bgcolor: 'rgba(255,255,255,0.15)' } }} />}
              label={<Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.7rem' }}>Compare</Typography>}
              sx={{ mx: 0, '& .MuiFormControlLabel-label': { ml: 0.25 } }}
            />
          </Box>

          {/* Zoom Controls - Improved */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, ml: 2 }}>
            <IconButton
              size="small"
              onClick={handleZoomIn}
              title="Zoom In (50%)"
              sx={{
                border: '1px solid rgba(255,255,255,0.1)',
                '&:hover': { bgcolor: 'rgba(255,255,255,0.1)' },
              }}
            >
              <ZoomInIcon fontSize="small" />
            </IconButton>
            <IconButton
              size="small"
              onClick={handleZoomOut}
              disabled={!isZoomed}
              title="Zoom Out (200%)"
              sx={{
                border: '1px solid rgba(255,255,255,0.1)',
                '&:hover': { bgcolor: 'rgba(255,255,255,0.1)' },
              }}
            >
              <ZoomOutIcon fontSize="small" />
            </IconButton>
            {isZoomed && (
              <IconButton
                size="small"
                onClick={handleResetZoom}
                title="Reset Zoom"
                sx={{
                  border: '1px solid rgba(255,255,255,0.1)',
                  '&:hover': { bgcolor: 'rgba(255,255,255,0.1)' },
                }}
              >
                <RestartAltIcon fontSize="small" />
              </IconButton>
            )}
          </Box>
        </Box>
      </Box>

      {/* E5: Scenario compare offset sliders — shown only when Compare is on */}
      {scenarioCompare && (
        <Box sx={{ mt: 1, px: 2, py: 1.5, bgcolor: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.25)', borderRadius: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <Typography variant="caption" sx={{ color: '#818cf8', fontWeight: 600 }}>
              📊 Compare Scenario
            </Typography>
            <Typography variant="caption" sx={{ color: '#64748b' }}>
              — dashed curves show payoff with these offsets applied
            </Typography>
            {(compareSpotPct !== 0 || compareTimeDays !== 0) && (
              <Typography
                variant="caption"
                onClick={() => { setCompareSpotPct(0); setCompareTimeDays(0); }}
                sx={{ color: '#6366f1', cursor: 'pointer', ml: 'auto', '&:hover': { textDecoration: 'underline' } }}
              >
                Reset
              </Typography>
            )}
          </Box>
          <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
            <Box sx={{ flex: 1, minWidth: 160 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="caption" color="text.secondary">BTC offset</Typography>
                <Typography variant="caption" sx={{ color: compareSpotPct === 0 ? '#64748b' : '#818cf8', fontWeight: 600 }}>
                  {compareSpotPct >= 0 ? '+' : ''}{compareSpotPct.toFixed(1)}%
                </Typography>
              </Box>
              <Slider
                size="small"
                value={compareSpotPct}
                onChange={(e, v) => setCompareSpotPct(v)}
                min={-20} max={20} step={0.5}
                sx={{ color: '#6366f1', '& .MuiSlider-thumb': { width: 12, height: 12 } }}
              />
            </Box>
            <Box sx={{ flex: 1, minWidth: 160 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="caption" color="text.secondary">Time forward</Typography>
                <Typography variant="caption" sx={{ color: compareTimeDays === 0 ? '#64748b' : '#818cf8', fontWeight: 600 }}>
                  +{compareTimeDays}d
                </Typography>
              </Box>
              <Slider
                size="small"
                value={compareTimeDays}
                onChange={(e, v) => setCompareTimeDays(v)}
                min={0} max={30} step={1}
                sx={{ color: '#6366f1', '& .MuiSlider-thumb': { width: 12, height: 12 } }}
              />
            </Box>
          </Box>
          {scenarioChartData?.projectedProfit != null && (
            <Box sx={{ display: 'flex', gap: 2, mt: 0.5 }}>
              <Typography variant="caption" sx={{ color: '#64748b' }}>
                Current P&L at spot:{' '}
                <span style={{ color: (chartData?.projectedProfit ?? 0) >= 0 ? '#10b981' : '#ef4444', fontWeight: 600 }}>
                  {(chartData?.projectedProfit ?? 0) >= 0 ? '+' : ''}${(chartData?.projectedProfit ?? 0).toFixed(0)}
                </span>
              </Typography>
              <Typography variant="caption" sx={{ color: '#64748b' }}>
                Scenario P&L:{' '}
                <span style={{ color: scenarioChartData.projectedProfit >= 0 ? '#10b981' : '#ef4444', fontWeight: 600 }}>
                  {scenarioChartData.projectedProfit >= 0 ? '+' : ''}${scenarioChartData.projectedProfit.toFixed(0)}
                </span>
              </Typography>
              <Typography variant="caption" sx={{ color: '#64748b' }}>
                Δ:{' '}
                <span style={{ color: (scenarioChartData.projectedProfit - (chartData?.projectedProfit ?? 0)) >= 0 ? '#10b981' : '#ef4444', fontWeight: 600 }}>
                  {(scenarioChartData.projectedProfit - (chartData?.projectedProfit ?? 0)) >= 0 ? '+' : ''}${(scenarioChartData.projectedProfit - (chartData?.projectedProfit ?? 0)).toFixed(0)}
                </span>
              </Typography>
            </Box>
          )}
        </Box>
      )}

      {/* Current Price Display */}
      <Box sx={{ mb: 1, display: 'flex', justifyContent: 'center', gap: 1 }}>
        <Chip
          label={`Current price: $${spotPrice.toLocaleString()}`}
          size="small"
          sx={{ bgcolor: 'rgba(59, 130, 246, 0.2)', color: '#3b82f6', fontWeight: 'bold' }}
        />
        {isZoomed && (
          <Chip
            label="Drag to select area • Click Zoom Out to reset"
            size="small"
            variant="outlined"
            sx={{ borderColor: 'rgba(255,255,255,0.2)' }}
          />
        )}
      </Box>

      {/* Drag instruction */}
      {!isZoomed && (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: 'block', textAlign: 'center', mb: 1 }}
        >
          💡 Drag on chart to select an area and zoom
        </Typography>
      )}

      {/* Chart */}
      <Box sx={{ position: 'relative' }}>
        {manualPnL !== 0 && (
          <Typography sx={{
            position: 'absolute', top: 24, left: 52, zIndex: 1,
            fontSize: '0.7rem', color: '#9ca3af', fontStyle: 'italic', pointerEvents: 'none',
          }}>
            ⚙ Manual offset: {manualPnL > 0 ? '+' : ''}${Math.abs(manualPnL).toFixed(2)}
          </Typography>
        )}
        <ResponsiveContainer width="100%" height={350}>
        <ComposedChart
          data={shiftedDisplayData}
          margin={{ top: 20, right: 30, left: 20, bottom: 10 }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          <defs>
            {/* Gradient for profit area */}
            <linearGradient id="profitGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity={0.15} />
              <stop offset="100%" stopColor="#10b981" stopOpacity={0.03} />
            </linearGradient>
            {/* Gradient for loss area */}
            <linearGradient id="lossGradient" x1="0" y1="1" x2="0" y2="0">
              <stop offset="0%" stopColor="#ef4444" stopOpacity={0.4} />
              <stop offset="100%" stopColor="#ef4444" stopOpacity={0.1} />
            </linearGradient>
            {/* Selection highlight */}
            <linearGradient id="selectionGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.1} />
            </linearGradient>
            {/* Probability distribution overlay (E3) — visible gradient */}
            <linearGradient id="probGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#a78bfa" stopOpacity={0.35} />
              <stop offset="100%" stopColor="#a78bfa" stopOpacity={0.08} />
            </linearGradient>
          </defs>

          <XAxis
            type="number"
            dataKey="price"
            tickFormatter={(v) => v.toLocaleString()}
            stroke="#666"
            tick={{ fontSize: 11 }}
            domain={
              isZoomed && zoomDomain.left ? [zoomDomain.left, zoomDomain.right] : ['auto', 'auto']
            }
            allowDataOverflow={true}
            scale="linear"
          />
          <YAxis
            tickFormatter={(v) => `$${v.toFixed(0)}`}
            stroke="#666"
            tick={{ fontSize: 11 }}
            domain={isZoomed ? zoomedYDomain : [yMin + manualPnL, yMax + manualPnL]}
            allowDataOverflow={true}
            label={{
              value: 'Profit / Loss',
              angle: -90,
              position: 'insideLeft',
              fill: '#888',
              fontSize: 12,
            }}
          />
          {/* Hidden secondary Y-axis for probability distribution — auto-scales independently */}
          {showProbDist && (
            <YAxis
              yAxisId="prob"
              orientation="right"
              hide={true}
              domain={[0, 'dataMax']}
            />
          )}

          <Tooltip content={<CustomTooltip />} />

          {/* Selection area highlight */}
          {isSelecting && selectionStart !== null && selectionEnd !== null && (
            <ReferenceArea
              x1={selectionStart}
              x2={selectionEnd}
              fill="url(#selectionGradient)"
              stroke="#3b82f6"
              strokeOpacity={0.5}
            />
          )}

          {/* Zero reference line */}
          <ReferenceLine y={0} stroke="#555" strokeWidth={1} />

          {/* Current spot price vertical line */}
          <ReferenceLine
            x={Math.round(spotPrice)}
            stroke="#3b82f6"
            strokeWidth={2}
            strokeDasharray="5 5"
          />

          {/* Profit area (above zero) - Green fill */}
          <Area
            type="monotone"
            dataKey="expiryProfit"
            stroke="none"
            fill="url(#profitGradient)"
            fillOpacity={1}
            isAnimationActive={false}
          />

          {/* Loss area (below zero) - Red fill */}
          <Area
            type="monotone"
            dataKey="expiryLoss"
            stroke="none"
            fill="url(#lossGradient)"
            fillOpacity={1}
            isAnimationActive={false}
          />

          {/* CartesianGrid rendered after Area fills so grid lines show through the fill */}
          <CartesianGrid strokeDasharray="3 3" stroke="#555" opacity={0.5} />

          {/* C5: On Expiry line — dual-color (green above zero, red below) */}
          <Line
            type="monotone"
            dataKey="expiryGreen"
            stroke="#10b981"
            strokeWidth={2.5}
            dot={false}
            name="On Expiry"
            isAnimationActive={false}
            connectNulls={false}
          />
          <Line
            type="monotone"
            dataKey="expiryRed"
            stroke="#ef4444"
            strokeWidth={2.5}
            dot={false}
            name="On Expiry (loss)"
            isAnimationActive={false}
            connectNulls={false}
            legendType="none"
          />

          {/* On Target Date line - Blue (natural curve for smoothness) */}
          <Line
            type="natural"
            dataKey="target"
            stroke="#3b82f6"
            strokeWidth={2.5}
            dot={false}
            name="On Target Date"
            isAnimationActive={false}
          />

          {/* ── Multi-date overlay (E1): Today + Mid-expiry reference lines ── */}
          {/* "Today" line — only when slider moved so it's not hidden behind Target */}
          {showMultiDate && targetDaysFromNow > 0.02 && (
            <Line
              type="natural"
              dataKey="today"
              stroke="#06b6d4"
              strokeWidth={2}
              strokeDasharray="6 3"
              dot={false}
              name="Today"
              isAnimationActive={false}
            />
          )}
          {/* Mid-expiry line — always distinct from both Target and Expiry */}
          {showMultiDate && (
            <Line
              type="natural"
              dataKey="mid"
              stroke="#818cf8"
              strokeWidth={2}
              strokeDasharray="4 4"
              dot={false}
              name="Mid-Expiry"
              isAnimationActive={false}
              opacity={0.8}
            />
          )}

          {/* ── E5: Scenario comparison baseline overlay ── */}
          {scenarioCompare && scenarioChartData?.data && (
            <>
              <Line
                type="natural"
                dataKey="baselineExpiry"
                stroke="#9ca3af"
                strokeWidth={2}
                strokeDasharray="8 4"
                dot={false}
                name="Baseline Expiry"
                isAnimationActive={false}
                opacity={0.6}
              />
              <Line
                type="natural"
                dataKey="baselineTarget"
                stroke="#6b7280"
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={false}
                name="Baseline Target"
                isAnimationActive={false}
                opacity={0.5}
              />
            </>
          )}

          {/* ── Probability distribution overlay (E3): bell curve (normalized 0-100) ── */}
          {showProbDist && (
            <Area
              yAxisId="prob"
              type="monotone"
              dataKey="probability"
              stroke="#a78bfa"
              strokeWidth={1.5}
              strokeOpacity={0.5}
              fill="url(#probGradient)"
              fillOpacity={1}
              isAnimationActive={false}
              name="Probability"
            />
          )}

          {/* Target price vertical line (dashed yellow) - Always visible at ATM/target */}
          <ReferenceLine
            x={Math.round(targetPrice)}
            stroke="#fbbf24"
            strokeWidth={2}
            strokeDasharray="5 5"
            label={{
              value: targetPricePercent === 0 ? 'ATM' : 'Target',
              position: 'top',
              fill: '#fbbf24',
              fontSize: 10,
            }}
          />


          {/* Active Alerts - Orange lines (Filtered by View Expiry) */}
          {/* Active Alerts - Orange lines (Filtered by View Expiry) */}
          {filteredAlerts.map((alert) => {
            // Ensure price is a valid number
            const price = parseFloat(alert.target_price);
            if (isNaN(price)) return null;

            return (
              <ReferenceLine
                key={alert.id}
                x={price}
                stroke="#f97316"
                strokeWidth={2}
                strokeDasharray="5 5"
                isFront={true}
                ifOverflow="extendDomain"
                label={({ viewBox }) => {
                  // Custom label renderer
                  const { x, y } = viewBox;
                  // If x is undefined or NaN, don't render
                  if (!x || isNaN(x)) return null;

                  return (
                    <g transform={`translate(${x}, 20)`}>
                      {/* C4: SVG bell icon instead of emoji for cross-platform rendering */}
                      <path
                        d="M12 2C11.172 2 10.5 2.672 10.5 3.5V4.19C7.91 4.86 6 7.2 6 10V15L4 17V18H20V17L18 15V10C18 7.2 16.09 4.86 13.5 4.19V3.5C13.5 2.672 12.828 2 12 2ZM10 19C10 20.1 10.9 21 12 21S14 20.1 14 19H10Z"
                        fill="#f97316"
                        transform="translate(-12, -12) scale(0.9)"
                      />
                      <text x={0} y={14} textAnchor="middle" fill="#f97316" fontSize="10" fontWeight="bold">
                        {price.toLocaleString()}
                      </text>
                    </g>
                  );
                }}
              />
            );
          })}
        </ComposedChart>
        </ResponsiveContainer>
      </Box>

      {/* Projected Profit Display */}
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: -1, mb: 2 }}>
        <Chip
          label={`Projected profit at ${targetPricePercent === 0 ? 'spot' : `$${targetPrice.toLocaleString()}`}: ${displayProjectedProfit >= 0 ? '+' : ''}$${displayProjectedProfit.toFixed(2)} (${displayProfitPct >= 0 ? '+' : ''}${displayProfitPct}%)`}
          sx={{
            bgcolor: displayProjectedProfit >= 0 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
            color: displayProjectedProfit >= 0 ? '#10b981' : '#ef4444',
            fontWeight: 'bold',
            px: 2,
          }}
        />
      </Box>

      {/* Target Price + Date/Time Sliders — extracted to PayoffControls */}
      <PayoffControls
        targetPricePercent={targetPricePercent}
        setTargetPricePercent={setTargetPricePercent}
        maxDaysToExpiry={maxDaysToExpiry}
        furthestExpiry={furthestExpiry}
        allExpiryMarks={allExpiryMarks}
        targetPrice={targetPrice}
        targetDaysFromNow={targetDaysFromNow}
        setTargetDaysFromNow={setTargetDaysFromNow}
        targetDate={targetDate}
        daysToExpiryFromTarget={daysToExpiryFromTarget}
        minDaysToExpiry={minDaysToExpiry}
        nearestExpiry={nearestExpiry}
      />

      {/* Batch Order section (injected from OptionsPanel) */}
      {batchOrderSection && (
        <Box sx={{ order: 1 }}>
          {batchOrderSection}
        </Box>
      )}

      {/* Alerts Panel - Manage Price Notifications */}
      <Box sx={{ order: 3 }}>
        <AlertsPanel
          spotPrice={chartData?.spotPrice}
          alerts={activeAlerts}
          onRefresh={fetchAlerts}
          expiryDate={chartData?.nearestExpiry ? new Date(chartData.nearestExpiry).toISOString().split('T')[0] : null}
          compactSpacing
        />
      </Box>

      {/* Alert Creation Dialog - Extracted Component */}
      <PayoffAlertDialog
        open={alertDialogOpen}
        onClose={() => setAlertDialogOpen(false)}
        alertPrice={alertPrice}
        setAlertPrice={setAlertPrice}
        alertPnLExpiry={alertPnLExpiry}
        alertPnLTarget={alertPnLTarget}
        expiryDate={chartData?.nearestExpiry ? new Date(chartData.nearestExpiry).toISOString().split('T')[0] : null}
        onAlertCreated={() => setAlertsRefreshTrigger((prev) => prev + 1)}
      />
    </Paper>
  );
};

export default OptionsPayoffDiagram;
