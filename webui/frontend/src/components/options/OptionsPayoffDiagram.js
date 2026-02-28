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
  Box, Typography, Paper, Chip, IconButton, Popover, Switch, FormControlLabel,
} from '@mui/material';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import ZoomOutIcon from '@mui/icons-material/ZoomOut';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
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
// CUSTOM TOOLTIP — defined outside the parent component so the function
// reference is stable across renders. Recharts remounts the tooltip whenever
// it detects a new component *type*, so inlining this inside OptionsPayoffDiagram
// (which recreates the function on every render) caused visible flickering.
// ============================================================================

const CustomTooltip = ({
  active, payload, label,
  displayData, targetDaysFromNow, targetDate, spotPrice, chartPositions, minDaysToExpiry,
}) => {
  if (!active || !payload || !payload.length) return null;

  const currentPrice = Number(label);

  // Read directly from the matching data point so we never miss null/hidden series
  const dataPoint = displayData?.find((d) => d.price === currentPrice)
    || displayData?.reduce((closest, d) =>
      Math.abs(d.price - currentPrice) < Math.abs(closest.price - currentPrice) ? d : closest,
      displayData[0]);

  const expiryVal = dataPoint
    ? (dataPoint.expiry ?? dataPoint.expiryGreen ?? dataPoint.expiryRed ?? 0)
    : (payload.find((p) => p.dataKey === 'expiryGreen')?.value ?? payload.find((p) => p.dataKey === 'expiryRed')?.value ?? 0);

  const targetVal = dataPoint?.target ?? payload.find((p) => p.dataKey === 'target')?.value ?? 0;
  const todayVal = dataPoint?.today ?? payload.find((p) => p.dataKey === 'today')?.value;
  const midVal = dataPoint?.mid ?? payload.find((p) => p.dataKey === 'mid')?.value;

  // When slider = 0 (today), target IS today — avoid showing the same number twice
  const isTargetToday = targetDaysFromNow < 0.02;

  // C2: Calculate portfolio Greeks at hovered price
  const delta = chartPositions ? calculatePortfolioDelta(currentPrice, chartPositions, targetDaysFromNow) : 0;
  const gamma = chartPositions ? calculatePortfolioGamma(currentPrice, chartPositions, targetDaysFromNow) : 0;
  const theta = chartPositions ? calculatePortfolioTheta(currentPrice, chartPositions, targetDaysFromNow) : 0;

  // Calculate price change from spot
  const priceChange = currentPrice - spotPrice;
  const priceChangePct = ((priceChange / spotPrice) * 100).toFixed(2);
  const priceChangeSign = priceChange >= 0 ? '+' : '';

  // Format target date label
  const targetDateFormatted = isTargetToday
    ? 'Today (now)'
    : (targetDate
      ? targetDate.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' })
      : 'Today');

  // Mid-expiry time label: show human-readable time distance instead of jargon
  const midDays = minDaysToExpiry != null ? minDaysToExpiry * 0.5 : null;
  const midLabel = midDays == null
    ? 'Mid-expiry'
    : midDays < 0.5
      ? `In ~${Math.round(midDays * 24)}h`
      : midDays < 1.5
        ? 'In ~1 day'
        : `In ~${Math.round(midDays)} days`;

  // Format a P&L value with dollar sign and sign prefix
  const fmtPnL = (v) => `${v >= 0 ? '+' : '-'}$${Math.abs(v).toFixed(2)}`;

  return (
    <Paper
      sx={{
        p: 0,
        bgcolor: 'rgba(17, 24, 39, 0.95)',
        border: '1px solid rgba(75, 85, 99, 0.5)',
        borderRadius: 2,
        minWidth: 190,
        backdropFilter: 'blur(8px)',
        boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
      }}
    >
      {/* Price header */}
      <Box sx={{ p: 1.25, borderBottom: '1px solid rgba(75, 85, 99, 0.3)' }}>
        <Typography variant="caption" sx={{ color: 'rgba(156, 163, 175, 0.8)', display: 'block', mb: 0.25 }}>
          If price is at
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1 }}>
          <Typography variant="h6" fontWeight="bold" sx={{ color: '#fff', lineHeight: 1 }}>
            ${currentPrice.toLocaleString()}
          </Typography>
          <Typography
            variant="caption"
            sx={{
              color: priceChange >= 0 ? '#10b981' : '#ef4444',
              fontWeight: 600
            }}
          >
            {priceChangeSign}{priceChangePct}% ({priceChangeSign}${Math.abs(priceChange).toLocaleString(undefined, { maximumFractionDigits: 0 })})
          </Typography>
        </Box>
      </Box>

      {/* P&L section — values are conditional on price staying at this level */}
      <Box sx={{ p: 1.25 }}>
        <Typography variant="caption" sx={{ color: 'rgba(156, 163, 175, 0.8)', display: 'block', mb: 0.75 }}>
          P&L at this price on
        </Typography>

        {/* Target date P&L */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.75 }}>
          <Typography variant="body2" sx={{ color: '#9ca3af' }}>
            {targetDateFormatted}
          </Typography>
          <Typography
            variant="body2"
            fontWeight="bold"
            sx={{ color: targetVal >= 0 ? '#10b981' : '#ef4444' }}
          >
            {fmtPnL(targetVal)}
          </Typography>
        </Box>

        {/* Today P&L (multi-date overlay) - hide if target is already today */}
        {!isTargetToday && todayVal !== undefined && (
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.75 }}>
            <Typography variant="body2" sx={{ color: '#06b6d4' }}>
              Today
            </Typography>
            <Typography
              variant="body2"
              fontWeight="bold"
              sx={{ color: todayVal >= 0 ? '#10b981' : '#ef4444' }}
            >
              {fmtPnL(todayVal)}
            </Typography>
          </Box>
        )}

        {/* Mid-expiry P&L (multi-date overlay) — labeled with actual time distance */}
        {midVal !== undefined && (
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.75 }}>
            <Typography variant="body2" sx={{ color: '#818cf8' }}>
              {midLabel}
            </Typography>
            <Typography
              variant="body2"
              fontWeight="bold"
              sx={{ color: midVal >= 0 ? '#10b981' : '#ef4444' }}
            >
              {fmtPnL(midVal)}
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
            sx={{ color: expiryVal >= 0 ? '#10b981' : '#ef4444' }}
          >
            {fmtPnL(expiryVal)}
          </Typography>
        </Box>
      </Box>

      {/* C2: Greeks at hovered price */}
      {chartPositions && chartPositions.length > 0 && (
        <Box sx={{ p: 1.25, borderTop: '1px solid rgba(75, 85, 99, 0.3)' }}>
          <Box sx={{ display: 'flex', gap: 1.5, justifyContent: 'space-between' }}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="caption" sx={{ color: 'rgba(156,163,175,0.6)', fontSize: '0.6rem', display: 'block' }}>Δ Net Delta</Typography>
              <Typography variant="caption" fontWeight="bold" sx={{ color: delta >= 0 ? '#10b981' : '#ef4444' }}>
                {delta >= 0 ? '+' : ''}{delta.toFixed(4)}
              </Typography>
            </Box>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="caption" sx={{ color: 'rgba(156,163,175,0.6)', fontSize: '0.6rem', display: 'block' }}>Γ Net Gamma</Typography>
              <Typography variant="caption" fontWeight="bold" sx={{ color: '#a78bfa' }}>
                {gamma.toFixed(6)}
              </Typography>
            </Box>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="caption" sx={{ color: 'rgba(156,163,175,0.6)', fontSize: '0.6rem', display: 'block' }}>Θ Net Theta</Typography>
              <Typography variant="caption" fontWeight="bold" sx={{ color: theta >= 0 ? '#10b981' : '#ef4444' }}>
                {theta >= 0 ? '+$' : '-$'}{Math.abs(theta).toFixed(2)}/day
              </Typography>
            </Box>
          </Box>
        </Box>
      )}
    </Paper>
  );
};

// ============================================================================
// MAIN COMPONENT
// ============================================================================

const OptionsPayoffDiagram = ({
  positions,
  selectedPositions = [],
  futuresPositions = []
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
  const [breakevenAnchor, setBreakevenAnchor] = useState(null); // For expandable breakeven popover

  // Alert creation state (from chart click)
  const [alertDialogOpen, setAlertDialogOpen] = useState(false);
  const [alertPrice, setAlertPrice] = useState(null);
  const [alertPnLExpiry, setAlertPnLExpiry] = useState(null);
  const [alertPnLTarget, setAlertPnLTarget] = useState(null);
  const [activeAlerts, setActiveAlerts] = useState([]);
  const [alertsRefreshTrigger, setAlertsRefreshTrigger] = useState(0);

  // Phase E: Advanced feature toggles
  const [showMultiDate, setShowMultiDate] = useState(true);
  const [showProbDist, setShowProbDist] = useState(true);

  // E5: Scenario comparison — snapshot baseline, overlay on future changes
  const [scenarioCompare, setScenarioCompare] = useState(false);
  const baselineRef = useRef(null);

  // ========================================================================
  // D2: Data computation via extracted hooks (usePayoffData.js)
  // ========================================================================
  const parsedPositions = useParsedPositions(positions, selectedPositions, futuresPositions);
  const chartData = useChartData(parsedPositions, {
    priceRangePercent, targetDaysFromNow, targetPricePercent,
    showMultiDate, showProbDist, futuresPositions,
  });

  // E5: Capture baseline snapshot when compare mode is toggled on
  useEffect(() => {
    if (scenarioCompare && chartData?.data?.length > 0 && !baselineRef.current) {
      // Take a snapshot: map price → { expiry, target }
      const snap = {};
      for (const pt of chartData.data) {
        snap[pt.price] = {
          expiry: (pt.expiryGreen ?? pt.expiryRed ?? 0),
          target: pt.target ?? 0,
        };
      }
      baselineRef.current = snap;
    }
    if (!scenarioCompare) {
      baselineRef.current = null;
    }
  }, [scenarioCompare, chartData]);

  // Merge baseline into chart data
  const enrichedData = useMemo(() => {
    if (!chartData?.data || !scenarioCompare || !baselineRef.current) {
      return chartData?.data;
    }
    const snap = baselineRef.current;
    return chartData.data.map((pt) => {
      const base = snap[pt.price];
      if (base) {
        return { ...pt, baselineExpiry: base.expiry, baselineTarget: base.target };
      }
      return pt;
    });
  }, [chartData, scenarioCompare]);

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

  // Calculate Y-axis domain for zoomed view (TRULY ADAPTIVE based on visible data)
  // This is critical - when user zooms to a small area, Y-axis MUST adapt
  const zoomedYDomain = useMemo(() => {
    if (!displayData || displayData.length === 0) {
      return [chartData?.yMin || -10, chartData?.yMax || 10];
    }

    let minY = Infinity,
      maxY = -Infinity;
    displayData.forEach((d) => {
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

    // Zero-centred Y domain: keep zero in the middle so the profit region
    // always gets meaningful screen space even when losses are much larger.
    const profitMax = Math.max(maxY, 0);
    const lossMin = Math.min(minY, 0);

    const profitPaddingPercent = profitMax < 5 ? 0.5 : profitMax < 20 ? 0.35 : 0.2;
    const profitPadding = Math.max(profitMax * profitPaddingPercent, 2);
    const rawYMax = profitMax + profitPadding;

    // Mirror upper bound below zero (symmetric), then allow extension for deeper losses
    // but cap at 3× profit extent so extreme losses don't dominate the scale
    const actualLoss = Math.abs(lossMin);
    const cappedLoss = Math.min(actualLoss, rawYMax * 3);
    const rawYMin = -Math.max(cappedLoss, rawYMax); // at least symmetric

    return [Math.min(rawYMin, -2), Math.max(rawYMax, 2)];
  }, [displayData, chartData]);

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
    data,
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

  return (
    <Paper sx={{ p: 2, bgcolor: 'background.paper' }}>
      {/* Positions Used in Payoff - Show at top */}
      <Box sx={{ mb: 2, p: 2, bgcolor: 'action.hover', borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
        <Typography variant="subtitle2" fontWeight="bold" sx={{ mb: 1.5, color: 'primary.main' }}>
          📊 Positions Used in This Payoff Graph
        </Typography>

        {parsedPositions?.positions && parsedPositions.positions.length > 0 && (() => {
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
        )}

        {futuresPositions.length > 0 && (
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

        {(!parsedPositions?.positions || parsedPositions.positions.length === 0) && futuresPositions.length === 0 && (
          <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>
            No positions selected. Check the boxes next to positions to include them in the payoff graph.
          </Typography>
        )}
      </Box>

      {/* Compact Metrics Strip - Sensibull Style */}
      <Box
        sx={{
          mb: 2,
          display: 'flex',
          flexWrap: 'wrap',
          gap: 1.5,
          p: 1.5,
          bgcolor: 'rgba(17, 24, 39, 0.6)',
          borderRadius: 2,
          border: '1px solid rgba(75, 85, 99, 0.3)',
        }}
      >
        {/* Profit Potential */}
        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          px: 1.5,
          py: 0.75,
          borderRadius: 1.5,
          bgcolor: 'rgba(16,185,129,0.1)',
          border: '1px solid rgba(16,185,129,0.3)',
          minWidth: 'fit-content',
        }}>
          <Typography variant="caption" sx={{ color: 'rgba(156,163,175,0.9)', fontWeight: 500 }}>
            💰 Max Profit
          </Typography>
          <Typography variant="body2" fontWeight="bold" sx={{ color: '#10b981' }}>
            {isFinite(maxProfit) && maxProfit > 0 ? `+$${maxProfit.toFixed(2)}` : '♾️'}
          </Typography>
        </Box>

        {/* Risk Exposure */}
        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          px: 1.5,
          py: 0.75,
          borderRadius: 1.5,
          bgcolor: 'rgba(239,68,68,0.1)',
          border: '1px solid rgba(239,68,68,0.3)',
          minWidth: 'fit-content',
        }}>
          <Typography variant="caption" sx={{ color: 'rgba(156,163,175,0.9)', fontWeight: 500 }}>
            ⚠️ Max Loss
          </Typography>
          <Typography variant="body2" fontWeight="bold" sx={{ color: '#ef4444' }}>
            {isFinite(maxLoss) && maxLoss < 0 ? `$${maxLoss.toFixed(2)}` : '♾️'}
          </Typography>
        </Box>

        {/* Breakeven Points - Clickable with Popover */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            px: 1.5,
            py: 0.75,
            borderRadius: 1.5,
            bgcolor: 'rgba(251,191,36,0.1)',
            border: '1px solid rgba(251,191,36,0.3)',
            minWidth: 'fit-content',
            cursor: breakevens.length > 2 ? 'pointer' : 'default',
            transition: 'all 0.2s ease',
            '&:hover': breakevens.length > 2 ? {
              borderColor: 'rgba(251,191,36,0.6)',
              bgcolor: 'rgba(251,191,36,0.15)',
            } : {},
          }}
          onClick={(e) => breakevens.length > 2 && setBreakevenAnchor(e.currentTarget)}
        >
          <Typography variant="caption" sx={{ color: 'rgba(156,163,175,0.9)', fontWeight: 500 }}>
            🎯 Breakeven
          </Typography>
          {breakevens.length > 0 ? (
            <Box sx={{ display: 'flex', gap: 0.75, alignItems: 'center' }}>
              {breakevens.slice(0, 2).map((be, idx) => {
                const bePercent = ((be / spotPrice - 1) * 100).toFixed(1);
                const sign = bePercent >= 0 ? '+' : '';
                return (
                  <Typography key={idx} variant="body2" fontWeight="bold" sx={{ color: '#fbbf24' }}>
                    ${be.toLocaleString()}
                    <Typography component="span" variant="caption" sx={{ color: 'rgba(251,191,36,0.7)', ml: 0.25 }}>
                      ({sign}{bePercent}%)
                    </Typography>
                  </Typography>
                );
              })}
              {breakevens.length > 2 && (
                <Box
                  sx={{
                    px: 0.75,
                    py: 0.25,
                    borderRadius: 1,
                    bgcolor: 'rgba(251,191,36,0.25)',
                    '&:hover': { bgcolor: 'rgba(251,191,36,0.4)' },
                  }}
                >
                  <Typography variant="caption" fontWeight="600" sx={{ color: '#fbbf24' }}>
                    +{breakevens.length - 2} more ▼
                  </Typography>
                </Box>
              )}
            </Box>
          ) : (
            <Typography variant="body2" sx={{ color: '#9ca3af' }}>N/A</Typography>
          )}
        </Box>

        {/* Breakeven Popover - Shows all when clicked */}
        <Popover
          open={Boolean(breakevenAnchor)}
          anchorEl={breakevenAnchor}
          onClose={() => setBreakevenAnchor(null)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
          transformOrigin={{ vertical: 'top', horizontal: 'left' }}
          PaperProps={{
            sx: {
              mt: 0.5,
              p: 1.5,
              bgcolor: 'rgba(17, 24, 39, 0.98)',
              border: '1px solid rgba(251,191,36,0.3)',
              borderRadius: 2,
              backdropFilter: 'blur(8px)',
              minWidth: 200,
            }
          }}
        >
          <Typography variant="caption" sx={{ color: 'rgba(156,163,175,0.9)', display: 'block', mb: 1, fontWeight: 600 }}>
            🎯 All Breakeven Points ({breakevens.length})
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
            {breakevens.map((be, idx) => {
              const bePercent = ((be / spotPrice - 1) * 100).toFixed(1);
              const sign = bePercent >= 0 ? '+' : '';
              return (
                <Box key={idx} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="body2" fontWeight="bold" sx={{ color: '#fbbf24' }}>
                    ${be.toLocaleString()}
                  </Typography>
                  <Typography variant="caption" sx={{ color: 'rgba(251,191,36,0.7)' }}>
                    {sign}{bePercent}% from spot
                  </Typography>
                </Box>
              );
            })}
          </Box>
        </Popover>

        {/* Reward/Risk Ratio */}
        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          px: 1.5,
          py: 0.75,
          borderRadius: 1.5,
          bgcolor: 'rgba(59,130,246,0.1)',
          border: '1px solid rgba(59,130,246,0.3)',
          minWidth: 'fit-content',
        }}>
          <Typography variant="caption" sx={{ color: 'rgba(156,163,175,0.9)', fontWeight: 500 }}>
            ⚖️ R:R
          </Typography>
          {isFinite(maxProfit) && isFinite(maxLoss) && maxLoss !== 0 ? (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
              <Typography variant="body2" fontWeight="bold" sx={{ color: '#3b82f6' }}>
                {Math.abs(maxProfit / maxLoss).toFixed(2)}:1
              </Typography>
              <Box sx={{
                px: 0.75,
                py: 0.25,
                borderRadius: 0.5,
                bgcolor: maxProfit > Math.abs(maxLoss) ? 'rgba(16,185,129,0.2)' : maxProfit < Math.abs(maxLoss) ? 'rgba(239,68,68,0.2)' : 'rgba(156,163,175,0.2)'
              }}>
                <Typography variant="caption" fontWeight="600" sx={{
                  color: maxProfit > Math.abs(maxLoss) ? '#10b981' : maxProfit < Math.abs(maxLoss) ? '#ef4444' : '#9ca3af',
                  fontSize: '0.65rem'
                }}>
                  {maxProfit > Math.abs(maxLoss) ? '✓ Fav' : maxProfit < Math.abs(maxLoss) ? '⚠ Unfav' : '○'}
                </Typography>
              </Box>
            </Box>
          ) : (
            <Typography variant="body2" sx={{ color: '#9ca3af' }}>N/A</Typography>
          )}
        </Box>

        {/* B4: Probability of Profit (PoP) */}
        {probabilityOfProfit !== null && probabilityOfProfit !== undefined && (
          <Box sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            px: 1.5,
            py: 0.75,
            borderRadius: 1.5,
            bgcolor: probabilityOfProfit >= 50 ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
            border: `1px solid ${probabilityOfProfit >= 50 ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
            minWidth: 'fit-content',
          }}>
            <Typography variant="caption" sx={{ color: 'rgba(156,163,175,0.9)', fontWeight: 500 }}>
              🎲 PoP
            </Typography>
            <Typography variant="body2" fontWeight="bold" sx={{
              color: probabilityOfProfit >= 50 ? '#10b981' : '#ef4444',
            }}>
              {probabilityOfProfit.toFixed(1)}%
            </Typography>
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
              On Target Date
            </Typography>
          </Box>
          {showMultiDate && (
            <>
              {targetDaysFromNow > 0.02 && (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Box sx={{ width: 24, height: 2, bgcolor: '#06b6d4' }} />
                  <Typography variant="caption" color="text.secondary">
                    Today
                  </Typography>
                </Box>
              )}
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Box sx={{ width: 24, height: 2, bgcolor: '#818cf8', opacity: 0.8 }} />
                <Typography variant="caption" color="text.secondary">
                  Mid-Expiry
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
          {scenarioCompare && baselineRef.current && (
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
      <ResponsiveContainer width="100%" height={350}>
        <ComposedChart
          data={displayData}
          margin={{ top: 20, right: 30, left: 20, bottom: 10 }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          <defs>
            {/* Gradient for profit area */}
            <linearGradient id="profitGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity={0.4} />
              <stop offset="100%" stopColor="#10b981" stopOpacity={0.1} />
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

          <CartesianGrid strokeDasharray="3 3" stroke="#333" opacity={0.3} />

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
            domain={isZoomed ? zoomedYDomain : [yMin, yMax]}
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

          <Tooltip
            content={
              <CustomTooltip
                displayData={displayData}
                targetDaysFromNow={targetDaysFromNow}
                targetDate={targetDate}
                spotPrice={spotPrice}
                chartPositions={chartPositions}
                minDaysToExpiry={minDaysToExpiry}
              />
            }
          />

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
          {scenarioCompare && baselineRef.current && (
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

      {/* Projected Profit Display */}
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: -1, mb: 2 }}>
        <Chip
          label={`Projected profit at ${targetPricePercent === 0 ? 'spot' : `$${targetPrice.toLocaleString()}`}: ${projectedProfit >= 0 ? '+' : ''}$${projectedProfit.toFixed(2)} (${profitPct >= 0 ? '+' : ''}${profitPct}%)`}
          sx={{
            bgcolor: projectedProfit >= 0 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
            color: projectedProfit >= 0 ? '#10b981' : '#ef4444',
            fontWeight: 'bold',
            px: 2,
          }}
        />
      </Box>

      {/* Target Price + Date/Time Sliders — extracted to PayoffControls */}
      <PayoffControls
        targetPricePercent={targetPricePercent}
        setTargetPricePercent={setTargetPricePercent}
        targetPrice={targetPrice}
        targetDaysFromNow={targetDaysFromNow}
        setTargetDaysFromNow={setTargetDaysFromNow}
        targetDate={targetDate}
        daysToExpiryFromTarget={daysToExpiryFromTarget}
        minDaysToExpiry={minDaysToExpiry}
        nearestExpiry={nearestExpiry}
      />

      {/* Alerts Panel - Manage Price Notifications */}
      <AlertsPanel
        spotPrice={chartData?.spotPrice}
        alerts={activeAlerts}
        onRefresh={fetchAlerts}
        expiryDate={chartData?.nearestExpiry ? new Date(chartData.nearestExpiry).toISOString().split('T')[0] : null}
      />

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
