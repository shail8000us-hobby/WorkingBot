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
 * @version 3.0.0 - Sensibull Style
 */

import React, { useMemo, useState, useCallback, useRef } from 'react';
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  Area,
  ComposedChart,
  Line,
  ReferenceArea,
  Brush,
} from 'recharts';
import { Box, Typography, Paper, Chip, Slider, Stack, Divider, IconButton } from '@mui/material';
import ZoomInIcon from '@mui/icons-material/ZoomIn';
import ZoomOutIcon from '@mui/icons-material/ZoomOut';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import RestartAltIcon from '@mui/icons-material/RestartAlt';

// ============================================================================
// BLACK-SCHOLES MODEL
// ============================================================================

const normalCDF = (x) => {
  if (x === 0) return 0.5;
  const a1 = 0.254829592,
    a2 = -0.284496736,
    a3 = 1.421413741;
  const a4 = -1.453152027,
    a5 = 1.061405429,
    p = 0.3275911;
  const sign = x < 0 ? -1 : 1;
  const absX = Math.abs(x);
  const t = 1.0 / (1.0 + p * absX);
  const y = 1.0 - ((((a5 * t + a4) * t + a3) * t + a2) * t + a1) * t * Math.exp((-absX * absX) / 2);
  return 0.5 * (1.0 + sign * y);
};

const normalPDF = (x) => Math.exp(-0.5 * x * x) / Math.sqrt(2 * Math.PI);

const blackScholesPrice = (S, K, T, r, sigma, type) => {
  if (T <= 0) return type === 'call' ? Math.max(0, S - K) : Math.max(0, K - S);
  if (sigma <= 0 || S <= 0 || K <= 0)
    return type === 'call' ? Math.max(0, S - K) : Math.max(0, K - S);

  const sqrtT = Math.sqrt(T);
  const d1 = (Math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrtT);
  const d2 = d1 - sigma * sqrtT;

  return type === 'call'
    ? S * normalCDF(d1) - K * Math.exp(-r * T) * normalCDF(d2)
    : K * Math.exp(-r * T) * normalCDF(-d2) - S * normalCDF(-d1);
};

const calculateImpliedVolatility = (marketPrice, S, K, T, r, type) => {
  if (T <= 0 || marketPrice <= 0) return 0.8;

  let sigma = Math.sqrt((2 * Math.PI) / T) * (marketPrice / S);
  sigma = Math.max(0.1, Math.min(3.0, sigma));

  for (let i = 0; i < 50; i++) {
    const price = blackScholesPrice(S, K, T, r, sigma, type);
    const sqrtT = Math.sqrt(T);
    const d1 = (Math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrtT);
    const vega = S * sqrtT * normalPDF(d1);
    if (Math.abs(vega) < 1e-10) break;
    const diff = marketPrice - price;
    if (Math.abs(diff) < 0.0001) return sigma;
    sigma = Math.max(0.01, Math.min(5.0, sigma + diff / vega));
  }

  let low = 0.01,
    high = 3.0;
  for (let i = 0; i < 100; i++) {
    const mid = (low + high) / 2;
    const price = blackScholesPrice(S, K, T, r, mid, type);
    if (Math.abs(price - marketPrice) < 0.0001) return mid;
    if (price < marketPrice) low = mid;
    else high = mid;
  }
  return (low + high) / 2;
};

// ============================================================================
// HELPER: Format date for display
// ============================================================================
const formatDate = (date) => {
  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
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
  return `${days[date.getDay()]}, ${date.getDate()} ${months[date.getMonth()]} ${date.getHours()}:${String(date.getMinutes()).padStart(2, '0')} PM`;
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

  // ========================================================================
  // PARSE POSITIONS
  // ========================================================================

  const parsedPositions = useMemo(() => {
    if (!positions || positions.length === 0) return null;

    // Filter to only selected positions (whitelist approach)
    const visiblePositions = positions.filter((p) => selectedPositions.includes(p.product_symbol));

    // Get spot price from first position, or from futures, or default
    let spotPrice = 90000;
    if (visiblePositions.length > 0 && visiblePositions[0]?.greeks?.spot) {
      spotPrice = parseFloat(visiblePositions[0].greeks.spot);
    } else if (futuresPositions.length > 0 && futuresPositions[0]?.mark_price) {
      spotPrice = parseFloat(futuresPositions[0].mark_price);
    }

    // If no selected options AND no visible futures, return null
    if (visiblePositions.length === 0 && futuresPositions.length === 0) {
      return null;
    }

    // If no selected options but have futures, return minimal data structure
    if (visiblePositions.length === 0) {
      return {
        positions: [],
        spotPrice,
        minDaysToExpiry: 0.001,
        riskFreeRate: 0.05,
        nearestExpiry: new Date(Date.now() + 24 * 60 * 60 * 1000), // 1 day from now
      };
    }

    const riskFreeRate = 0.05;

    const parsed = visiblePositions.map((pos) => {
      const parts = pos.product_symbol.split('-');
      const optionType = parts[0] === 'C' ? 'call' : 'put';
      const strike = parseFloat(parts[2]);

      const expiryStr = parts[3];
      const day = parseInt(expiryStr.substring(0, 2));
      const month = parseInt(expiryStr.substring(2, 4)) - 1;
      const year = 2000 + parseInt(expiryStr.substring(4, 6));
      // BTC/ETH options on Delta Exchange expire at 5:30 PM IST (12:00 UTC)
      // IST = UTC + 5:30, so 5:30 PM IST = 12:00 PM UTC
      // Create date in UTC then convert - using local time equivalent of 5:30 PM IST
      const expiryDate = new Date(Date.UTC(year, month, day, 12, 0, 0)); // 12:00 UTC = 5:30 PM IST

      const now = new Date();
      const msToExpiry = expiryDate - now;
      const daysToExpiry = Math.max(0, msToExpiry / (1000 * 60 * 60 * 24));
      const yearsToExpiry = daysToExpiry / 365.25;

      const size = parseFloat(pos.size || 0);
      const entryPrice = parseFloat(pos.entry_price || 0);

      // Use mid_price (bid+ask)/2 for accurate current value, fallback to mark_price
      // This matches how PnL is calculated in the backend
      const bestBid = parseFloat(pos.best_bid || 0);
      const bestAsk = parseFloat(pos.best_ask || 0);
      const midPrice = bestBid > 0 && bestAsk > 0 ? (bestBid + bestAsk) / 2 : 0;
      const markPrice =
        midPrice > 0 ? midPrice : parseFloat(pos.mid_price || pos.mark_price || entryPrice);

      let iv = 0.8;
      if (markPrice > 0 && yearsToExpiry > 0.001) {
        const calculatedIV = calculateImpliedVolatility(
          markPrice,
          spotPrice,
          strike,
          yearsToExpiry,
          riskFreeRate,
          optionType
        );
        if (calculatedIV > 0.05 && calculatedIV < 4.0) iv = calculatedIV;
      }

      return {
        symbol: pos.product_symbol,
        type: optionType,
        strike,
        expiryDate,
        daysToExpiry,
        yearsToExpiry,
        size,
        entryPrice,
        markPrice,
        iv,
      };
    });

    // Calculate actual time to nearest expiry (can be fractional days)
    const nearestExpiry = parsed.reduce(
      (min, p) => (p.expiryDate < min ? p.expiryDate : min),
      parsed[0].expiryDate
    );
    const now = new Date();
    const actualDaysToExpiry = Math.max(0, (nearestExpiry - now) / (1000 * 60 * 60 * 24));
    // Use actual time to expiry (not ceiling) so slider can't go beyond 5:30 PM IST on expiry day
    const minDaysToExpiry = Math.max(0.001, actualDaysToExpiry);

    return { positions: parsed, spotPrice, minDaysToExpiry, riskFreeRate, nearestExpiry };
  }, [positions, selectedPositions, futuresPositions]);

  // ========================================================================
  // CALCULATE PAYOFF DATA WITH BOTH LINES
  // ========================================================================

  const chartData = useMemo(() => {
    if (!parsedPositions) return null;

    const {
      positions: parsedPos,
      spotPrice,
      minDaysToExpiry,
      riskFreeRate,
      nearestExpiry,
    } = parsedPositions;

    // Calculate X-axis range: ±6000 from ATM by default (user requested)
    // For zooming out, allow up to ±30000 range
    const DEFAULT_RANGE = 6000; // ±6000 from ATM
    const MAX_ZOOM_RANGE = 30000; // Maximum range for zooming out

    // Default: ±6000 from spot price
    let optimalMinPrice = spotPrice - DEFAULT_RANGE;
    let optimalMaxPrice = spotPrice + DEFAULT_RANGE;

    // If positions have strikes outside this range, extend to include them
    if (parsedPos.length > 0) {
      const strikes = parsedPos.map(p => p.strike);
      const minStrike = Math.min(...strikes);
      const maxStrike = Math.max(...strikes);

      // Extend range if needed to include all strikes + 2000 buffer
      const strikeBuffer = 2000;
      if (minStrike - strikeBuffer < optimalMinPrice) {
        optimalMinPrice = minStrike - strikeBuffer;
      }
      if (maxStrike + strikeBuffer > optimalMaxPrice) {
        optimalMaxPrice = maxStrike + strikeBuffer;
      }

      // Make symmetric around spot
      const spotToMin = spotPrice - optimalMinPrice;
      const spotToMax = optimalMaxPrice - spotPrice;
      const maxOffset = Math.max(spotToMin, spotToMax);
      optimalMinPrice = spotPrice - maxOffset;
      optimalMaxPrice = spotPrice + maxOffset;
    }

    // Apply user zoom override if priceRangePercent was manually changed (non-default)
    // Allow up to MAX_ZOOM_RANGE for zooming out
    const isDefaultRange = priceRangePercent === 20;
    let minPrice, maxPrice;
    if (isDefaultRange) {
      minPrice = optimalMinPrice;
      maxPrice = optimalMaxPrice;
    } else {
      // User changed the range - use their setting but cap at MAX_ZOOM_RANGE
      const userRange = Math.min(spotPrice * (priceRangePercent / 100), MAX_ZOOM_RANGE);
      minPrice = spotPrice - userRange;
      maxPrice = spotPrice + userRange;
    }

    const numPoints = 200; // More points for smoother curves
    const priceStep = (maxPrice - minPrice) / numPoints;

    // Calculate target date based on slider (supports fractional days for hourly precision)
    const now = new Date();
    const targetDate = new Date(now.getTime() + targetDaysFromNow * 24 * 60 * 60 * 1000);

    // Target price for projection (user-adjustable)
    const targetPrice = spotPrice * (1 + targetPricePercent / 100);
    const daysToExpiryFromTarget = Math.max(
      0,
      (nearestExpiry - targetDate) / (1000 * 60 * 60 * 24)
    );

    const data = [];

    for (let i = 0; i <= numPoints; i++) {
      const price = minPrice + i * priceStep;
      const point = { price: Math.round(price) };

      // Calculate "On Expiry" payoff for OPTIONS
      // For SHORT positions (size < 0): You SOLD the option, received premium
      //   P&L = (entryPrice - intrinsicAtExpiry) * |size| * multiplier
      //   If OTM at expiry (intrinsic=0): P&L = entryPrice * |size| * 0.001 (keep full premium)
      // For LONG positions (size > 0): You BOUGHT the option, paid premium
      //   P&L = (intrinsicAtExpiry - entryPrice) * size * multiplier
      let expiryPayoff = 0;
      parsedPos.forEach((pos) => {
        const intrinsic =
          pos.type === 'call' ? Math.max(0, price - pos.strike) : Math.max(0, pos.strike - price);

        const absSize = Math.abs(pos.size);
        const isShort = pos.size < 0;

        if (isShort) {
          // SHORT: profit = (premium received - intrinsic value owed) * size * multiplier
          const pnl = (pos.entryPrice - intrinsic) * absSize * 0.001;
          expiryPayoff += pnl;
        } else {
          // LONG: profit = (intrinsic value - premium paid) * size * multiplier
          const pnl = (intrinsic - pos.entryPrice) * absSize * 0.001;
          expiryPayoff += pnl;
        }
      });

      // Add FUTURES payoff at expiry (linear P&L)
      futuresPositions.forEach((futPos) => {
        const size = futPos.size;
        const entryPrice = futPos.entry_price;
        const CONTRACT_MULTIPLIER = 0.001; // Standard for Delta Exchange

        // P&L = (current_price - entry_price) * size * multiplier
        const pnl = (price - entryPrice) * size * CONTRACT_MULTIPLIER;
        expiryPayoff += pnl;
      });

      // Split into profit/loss for colored areas
      point.expiryProfit = expiryPayoff >= 0 ? expiryPayoff : 0;
      point.expiryLoss = expiryPayoff < 0 ? expiryPayoff : 0;
      point.expiry = expiryPayoff;

      // Calculate "On Target Date" payoff
      // ANCHORED to actual current unrealized P&L, then project change using Black-Scholes
      let targetPayoff = 0;
      parsedPos.forEach((pos) => {
        const absSize = Math.abs(pos.size);
        const isShort = pos.size < 0;

        // Current unrealized P&L (from actual market data)
        // SHORT: profit when mark < entry (option decayed)
        // LONG: profit when mark > entry (option gained value)
        let currentUnrealizedPnL;
        if (isShort) {
          currentUnrealizedPnL = (pos.entryPrice - pos.markPrice) * absSize * 0.001;
        } else {
          currentUnrealizedPnL = (pos.markPrice - pos.entryPrice) * absSize * 0.001;
        }

        const remainingYears = Math.max(0.0001, (pos.daysToExpiry - targetDaysFromNow) / 365.25);

        // Calculate theoretical prices at current spot and at this price point
        const theoAtCurrentSpot = blackScholesPrice(
          spotPrice,
          pos.strike,
          remainingYears,
          riskFreeRate,
          pos.iv,
          pos.type
        );
        const theoAtThisPrice = blackScholesPrice(
          price,
          pos.strike,
          remainingYears,
          riskFreeRate,
          pos.iv,
          pos.type
        );

        // Projected change from current spot to this price point
        // SHORT: loses money when option price goes up
        // LONG: gains money when option price goes up
        let projectedChange;
        if (isShort) {
          projectedChange = (theoAtCurrentSpot - theoAtThisPrice) * absSize * 0.001;
        } else {
          projectedChange = (theoAtThisPrice - theoAtCurrentSpot) * absSize * 0.001;
        }

        // Total P&L = current actual P&L + projected change
        targetPayoff += currentUnrealizedPnL + projectedChange;
      });

      // Add FUTURES payoff for target date (same as expiry, linear)
      futuresPositions.forEach((futPos) => {
        const size = futPos.size;
        const entryPrice = futPos.entry_price;
        const CONTRACT_MULTIPLIER = 0.001;

        const pnl = (price - entryPrice) * size * CONTRACT_MULTIPLIER;
        targetPayoff += pnl;
      });

      point.target = targetPayoff;

      data.push(point);
    }

    // Statistics
    let maxProfit = -Infinity,
      maxLoss = Infinity;
    let maxTargetProfit = -Infinity,
      maxTargetLoss = Infinity;
    const breakevens = [];

    data.forEach((point, idx) => {
      if (point.expiry > maxProfit) maxProfit = point.expiry;
      if (point.expiry < maxLoss) maxLoss = point.expiry;
      if (point.target > maxTargetProfit) maxTargetProfit = point.target;
      if (point.target < maxTargetLoss) maxTargetLoss = point.target;

      if (idx > 0) {
        const prev = data[idx - 1].expiry;
        const curr = point.expiry;
        if ((prev < 0 && curr >= 0) || (prev > 0 && curr <= 0)) {
          breakevens.push(point.price);
        }
      }
    });

    // Calculate Y-axis domain with ADAPTIVE bounds based on actual data
    // Goal: Use the full graph area for actual data, not fixed arbitrary bounds
    const overallMax = Math.max(maxProfit, maxTargetProfit);
    const overallMin = Math.min(maxLoss, maxTargetLoss);

    // Calculate adaptive padding based on the data range
    // Small ranges get more relative padding to make them readable
    const dataRange = Math.max(Math.abs(overallMax), Math.abs(overallMin));
    const paddingPercent = dataRange < 50 ? 0.4 : dataRange < 200 ? 0.25 : 0.15;

    // Calculate padded min/max with symmetric padding around zero if appropriate
    let rawYMin = overallMin - (Math.abs(overallMin) * paddingPercent);
    let rawYMax = overallMax + (Math.abs(overallMax) * paddingPercent);

    // Ensure zero line is always visible (important for reference)
    if (rawYMin > 0) rawYMin = -(rawYMax * 0.1);
    if (rawYMax < 0) rawYMax = -(rawYMin * 0.1);

    // Final bounds with min/max safeguards
    const yMin = Math.min(rawYMin, -5); // Always show at least a little below zero
    const yMax = Math.max(rawYMax, 5);  // Always show at least a little above zero

    // Find projected profit at target price (at current spot when targetPricePercent = 0)
    const targetPricePoint = data.find((d) => Math.abs(d.price - targetPrice) < priceStep * 1.5);
    const projectedProfit = targetPricePoint?.target ?? 0;

    // Calculate total premium collected (for short positions, this is what we received)
    // For longs, it's what we paid (negative)
    const totalPremiumCollected = parsedPos.reduce((sum, p) => {
      // For shorts (size < 0): entry * |size| * 0.001 = premium received
      // For longs (size > 0): -entry * size * 0.001 = premium paid (negative)
      return sum + p.entryPrice * Math.abs(p.size) * 0.001;
    }, 0);

    const profitPct =
      totalPremiumCollected > 0 ? ((projectedProfit / totalPremiumCollected) * 100).toFixed(2) : 0;

    return {
      data,
      spotPrice,
      targetPrice,
      maxProfit: isFinite(maxProfit) ? maxProfit : 0,
      maxLoss: isFinite(maxLoss) ? maxLoss : 0,
      breakevens,
      projectedProfit,
      profitPct,
      targetDate,
      daysToExpiryFromTarget,
      minDaysToExpiry,
      nearestExpiry,
      minPrice,
      maxPrice,
      yMin: isFinite(yMin) ? yMin : -10,
      yMax: isFinite(yMax) ? yMax : 10,
    };
  }, [parsedPositions, priceRangePercent, targetDaysFromNow, targetPricePercent, futuresPositions]);

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

  // Handle mouse up on chart (complete zoom)
  const handleMouseUp = useCallback(() => {
    if (isSelecting && selectionStart !== null && selectionEnd !== null) {
      const left = Math.min(selectionStart, selectionEnd);
      const right = Math.max(selectionStart, selectionEnd);

      // Only zoom if selection is meaningful (at least 1% of range)
      if (right - left > (chartData?.maxPrice - chartData?.minPrice) * 0.01) {
        setZoomDomain({ left, right });
        setIsZoomed(true);
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

  // Get filtered data based on zoom
  const displayData = useMemo(() => {
    if (!chartData) return [];
    if (!isZoomed || !zoomDomain.left || !zoomDomain.right) {
      return chartData.data;
    }
    return chartData.data.filter((d) => d.price >= zoomDomain.left && d.price <= zoomDomain.right);
  }, [chartData, isZoomed, zoomDomain]);

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

    // NO FIXED CAPS - let Y-axis be fully adaptive to actual data
    return [yMin, yMax];
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
  } = chartData;

  // Custom Tooltip - Sensibull Style
  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload || !payload.length) return null;

    const expiry = payload.find((p) => p.dataKey === 'expiry')?.value ?? 0;
    const target = payload.find((p) => p.dataKey === 'target')?.value ?? 0;
    const currentPrice = Number(label);

    // Calculate price change from spot
    const priceChange = currentPrice - spotPrice;
    const priceChangePct = ((priceChange / spotPrice) * 100).toFixed(2);
    const priceChangeSign = priceChange >= 0 ? '+' : '';

    // Format target date
    const targetDateFormatted = targetDate ?
      targetDate.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' }) :
      'Today';

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

          {/* Expiry P&L */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="body2" sx={{ color: '#9ca3af' }}>
              Expiry date
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
      </Paper>
    );
  };

  // Date slider marks - show hours for 0 DTE, days otherwise
  const dateMarks = [
    { value: 0, label: 'Now' },
    {
      value: minDaysToExpiry,
      label:
        minDaysToExpiry < 1
          ? `${Math.round(minDaysToExpiry * 24)}h`
          : `${Math.ceil(minDaysToExpiry)}d`,
    },
  ];

  return (
    <Paper sx={{ p: 2, bgcolor: 'background.paper' }}>
      {/* Positions Used in Payoff - Show at top */}
      <Box sx={{ mb: 2, p: 2, bgcolor: 'action.hover', borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
        <Typography variant="subtitle2" fontWeight="bold" sx={{ mb: 1.5, color: 'primary.main' }}>
          📊 Positions Used in This Payoff Graph
        </Typography>

        {parsedPositions?.positions && parsedPositions.positions.length > 0 && (
          <Box sx={{ mb: futuresPositions.length > 0 ? 1.5 : 0 }}>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5, fontWeight: 600 }}>
              Options ({parsedPositions.positions.length}):
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
              {parsedPositions.positions.map((pos, idx) => (
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
                  label={`${pos.size > 0 ? '📈 Long' : '📉 Short'} ${Math.abs(pos.size)} ${pos.type.toUpperCase()} $${pos.strike.toLocaleString()}`}
                />
              ))}
            </Box>
          </Box>
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

        {/* Breakeven Points */}
        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          px: 1.5,
          py: 0.75,
          borderRadius: 1.5,
          bgcolor: 'rgba(251,191,36,0.1)',
          border: '1px solid rgba(251,191,36,0.3)',
          minWidth: 'fit-content',
        }}>
          <Typography variant="caption" sx={{ color: 'rgba(156,163,175,0.9)', fontWeight: 500 }}>
            🎯 Breakeven
          </Typography>
          {breakevens.length > 0 ? (
            <Box sx={{ display: 'flex', gap: 0.75 }}>
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
                <Typography variant="caption" sx={{ color: 'rgba(251,191,36,0.7)' }}>
                  +{breakevens.length - 2} more
                </Typography>
              )}
            </Box>
          ) : (
            <Typography variant="body2" sx={{ color: '#9ca3af' }}>N/A</Typography>
          )}
        </Box>

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
        </Typography>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
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
          </defs>

          <CartesianGrid strokeDasharray="3 3" stroke="#333" opacity={0.3} />

          <XAxis
            dataKey="price"
            tickFormatter={(v) => v.toLocaleString()}
            stroke="#666"
            tick={{ fontSize: 11 }}
            domain={
              isZoomed && zoomDomain.left ? [zoomDomain.left, zoomDomain.right] : ['auto', 'auto']
            }
            allowDataOverflow={true}
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

          {/* On Expiry line - with gradient color (rendered as two separate paths) */}
          <Line
            type="monotone"
            dataKey="expiry"
            stroke="#10b981"
            strokeWidth={2.5}
            dot={false}
            name="On Expiry"
            isAnimationActive={false}
            // Custom stroke to show red below 0, green above - handled via CSS
            style={{ filter: 'none' }}
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

      {/* BTC Target Price Slider - Sensibull Style (Default: ATM/Index Price) */}
      <Box sx={{ mt: 2, px: 2, py: 1.5, bgcolor: 'rgba(0,0,0,0.3)', borderRadius: 1 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="body2" fontWeight="bold">
              BTC Target
            </Typography>
            <Chip
              label={targetPricePercent === 0 ? 'ATM' : 'Custom'}
              size="small"
              sx={{
                height: 18,
                fontSize: 10,
                bgcolor:
                  targetPricePercent === 0 ? 'rgba(251, 191, 36, 0.2)' : 'rgba(59, 130, 246, 0.2)',
                color: targetPricePercent === 0 ? '#fbbf24' : '#3b82f6',
              }}
            />
            <Typography
              variant="caption"
              onClick={() => setTargetPricePercent(0)}
              sx={{
                color: '#3b82f6',
                cursor: 'pointer',
                '&:hover': { textDecoration: 'underline' },
              }}
            >
              Reset to ATM
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="body2" color="text.secondary">
              {targetPricePercent >= 0 ? '+' : ''}
              {targetPricePercent.toFixed(1)}%
            </Typography>
            <IconButton
              size="small"
              onClick={() => setTargetPricePercent((p) => Math.max(-30, p - 1))}
            >
              <Typography sx={{ fontWeight: 'bold', fontSize: 16 }}>−</Typography>
            </IconButton>
            <Typography
              variant="body2"
              fontWeight="bold"
              sx={{ minWidth: 80, textAlign: 'center' }}
            >
              ${targetPrice.toLocaleString()}
            </Typography>
            <IconButton
              size="small"
              onClick={() => setTargetPricePercent((p) => Math.min(30, p + 1))}
            >
              <Typography sx={{ fontWeight: 'bold', fontSize: 16 }}>+</Typography>
            </IconButton>
          </Box>
        </Box>
        <Slider
          value={targetPricePercent}
          onChange={(e, v) => setTargetPricePercent(v)}
          min={-30}
          max={30}
          step={0.5}
          sx={{
            color: '#3b82f6',
            mt: 0.5,
            '& .MuiSlider-thumb': { width: 14, height: 14 },
            '& .MuiSlider-track': { height: 3 },
            '& .MuiSlider-rail': { height: 3, bgcolor: 'rgba(255,255,255,0.1)' },
          }}
        />
      </Box>

      {/* Date/Time Slider Section - Hourly for 24/7 BTC (Expiry: 5:30 PM IST) */}
      <Box sx={{ mt: 2, px: 2, py: 2, bgcolor: 'rgba(0,0,0,0.2)', borderRadius: 1 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Box>
            <Typography variant="caption" color="text.secondary">
              Time to expiry: {Math.floor(daysToExpiryFromTarget)}D{' '}
              {Math.round((daysToExpiryFromTarget % 1) * 24)}H
              {daysToExpiryFromTarget < 1 && ' (0 DTE)'}
            </Typography>
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            {/* Hourly back */}
            <IconButton
              size="small"
              onClick={() => setTargetDaysFromNow((d) => Math.max(0, d - 1 / 24))}
              title="-1 hour"
            >
              <ChevronLeftIcon fontSize="small" />
            </IconButton>
            <Typography variant="body2" sx={{ minWidth: 180, textAlign: 'center' }}>
              {formatDate(targetDate)}
            </Typography>
            {/* Hourly forward */}
            <IconButton
              size="small"
              onClick={() => setTargetDaysFromNow((d) => Math.min(minDaysToExpiry, d + 1 / 24))}
              title="+1 hour"
            >
              <ChevronRightIcon fontSize="small" />
            </IconButton>
          </Box>
        </Box>

        <Box sx={{ px: 1 }}>
          <Slider
            value={targetDaysFromNow}
            onChange={(e, v) => setTargetDaysFromNow(v)}
            min={0}
            max={minDaysToExpiry}
            step={1 / 24} // Hourly step for 24/7 market
            marks={dateMarks}
            sx={{
              color: '#3b82f6',
              '& .MuiSlider-thumb': {
                width: 16,
                height: 16,
              },
              '& .MuiSlider-track': {
                height: 4,
              },
              '& .MuiSlider-rail': {
                height: 4,
                bgcolor: 'rgba(255,255,255,0.1)',
              },
            }}
          />
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: -1 }}>
            <Typography variant="caption" color="text.secondary">
              Now
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {minDaysToExpiry < 1
                ? `${nearestExpiry.toLocaleDateString('en-US', { day: '2-digit', month: 'short' })} 5:30 PM IST`
                : nearestExpiry.toLocaleDateString('en-US', { day: '2-digit', month: 'short' })}
            </Typography>
          </Box>
        </Box>
      </Box>

      {/* Stats Row */}
      <Stack direction="row" spacing={1} sx={{ mt: 2, flexWrap: 'wrap', gap: 1 }}>
        <Chip
          label={`Spot: $${spotPrice.toLocaleString()}`}
          size="small"
          variant="outlined"
          sx={{ borderColor: '#3b82f6', color: '#3b82f6' }}
        />
        <Chip
          label={`Max Profit: $${maxProfit.toFixed(2)}`}
          size="small"
          sx={{ bgcolor: 'rgba(16,185,129,0.15)', color: '#10b981' }}
        />
        <Chip
          label={`Max Loss: $${maxLoss.toFixed(2)}`}
          size="small"
          sx={{ bgcolor: 'rgba(239,68,68,0.15)', color: '#ef4444' }}
        />
        {breakevens.length > 0 && (
          <Chip
            label={`Break-even: ${breakevens.map((b) => `$${b.toLocaleString()}`).join(', ')}`}
            size="small"
            variant="outlined"
          />
        )}
      </Stack>

      {/* Position Details */}
      {parsedPositions?.positions && (
        <Box sx={{ mt: 2, p: 1.5, bgcolor: 'action.hover', borderRadius: 1 }}>
          <Typography variant="caption" color="text.secondary" component="div" sx={{ mb: 1 }}>
            <strong>Options Positions ({parsedPositions.positions.length}):</strong>
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {parsedPositions.positions.map((pos, idx) => (
              <Chip
                key={idx}
                size="small"
                variant="outlined"
                sx={{
                  borderColor: pos.type === 'call' ? '#10b981' : '#ef4444',
                  color: pos.type === 'call' ? '#10b981' : '#ef4444',
                }}
                label={`${pos.size > 0 ? 'Long' : 'Short'} ${Math.abs(pos.size)} ${pos.type.toUpperCase()} $${pos.strike.toLocaleString()} • IV ${Math.round(pos.iv * 100)}%`}
              />
            ))}
          </Box>
        </Box>
      )}

      {/* Futures Position Details */}
      {futuresPositions.length > 0 && (
        <Box sx={{ mt: 2, p: 1.5, bgcolor: 'action.hover', borderRadius: 1 }}>
          <Typography variant="caption" color="text.secondary" component="div" sx={{ mb: 1 }}>
            <strong>Futures Positions ({futuresPositions.length}):</strong>
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {futuresPositions.map((pos, idx) => (
              <Chip
                key={idx}
                size="small"
                variant="outlined"
                sx={{
                  borderColor: '#3b82f6',
                  color: '#3b82f6',
                }}
                label={`${pos.size > 0 ? 'Long' : 'Short'} ${Math.abs(pos.size)} ${pos.product_symbol} @ $${parseFloat(pos.entry_price).toLocaleString()}`}
              />
            ))}
          </Box>
        </Box>
      )}
    </Paper>
  );
};

export default OptionsPayoffDiagram;
