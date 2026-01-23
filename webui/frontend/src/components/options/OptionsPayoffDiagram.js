/**
 * Options Payoff Diagram - Sensibull Style
 *
 * Features:
 * - Dual lines: "On Expiry" (green/red based on profit/loss) + "On Target Date" (blue)
 * - Interactive date slider to see P&L at any point between now and expiry
 * - Color-coded expiry area: Green fill above zero, Red fill below zero
 * - Projected profit display at current spot
 * - Real IV calculation from market prices
 * - Greeks from Delta Exchange API (with fallback to Black-Scholes)
 * - Probability of Profit (PoP) calculation
 *
 * @version 3.1.0 - API Integration + Probability Analysis
 */

import React, { useMemo, useState, useCallback, useRef, useEffect } from 'react';
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
import ApiIcon from '@mui/icons-material/Api';
import CalculateIcon from '@mui/icons-material/Calculate';

// Import new utilities
import { getContractMultiplier, RISK_FREE_RATE, DIVIDEND_YIELD } from '../../utils/constants';
import { getGreeksWithFallback, getBatchGreeksFromAPI } from '../../utils/greeksFromAPI';
import { calculatePoP, calculatePriceDistribution } from '../../utils/probabilityCalc';

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

const OptionsPayoffDiagram = ({ positions, hiddenPositions = [], futuresPositions = [] }) => {
  const [priceRangePercent, setPriceRangePercent] = useState(20);
  const [targetDaysFromNow, setTargetDaysFromNow] = useState(0); // Slider value in days (supports decimals for hours)
  const [targetPricePercent, setTargetPricePercent] = useState(0); // Target price offset from spot (-50% to +50%)

  // Greeks data source tracking
  const [greeksSource, setGreeksSource] = useState('calculating'); // 'api', 'calculated', 'calculating'
  const [popData, setPopData] = useState(null); // Probability of Profit data

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

    const visiblePositions = positions.filter((p) => !hiddenPositions.includes(p.product_symbol));
    if (visiblePositions.length === 0) return null;

    const spotPrice = visiblePositions[0]?.greeks?.spot
      ? parseFloat(visiblePositions[0].greeks.spot)
      : 90000;

    const riskFreeRate = RISK_FREE_RATE; // Using constant (0% for crypto)

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
  }, [positions, hiddenPositions]);

  // ========================================================================
  // CALCULATE PROBABILITY OF PROFIT
  // ========================================================================
  
  useEffect(() => {
    if (!parsedPositions || !parsedPositions.positions.length) {
      setPopData(null);
      return;
    }

    const { positions: parsedPos, spotPrice } = parsedPositions;

    // Calculate PoP for each position
    const positionsWithPoP = parsedPos.map((pos) => {
      try {
        const pop = calculatePoP({
          spotPrice,
          strike: pos.strike,
          entryPrice: pos.entryPrice,
          timeToExpiry: pos.yearsToExpiry,
          volatility: pos.iv,
          optionType: pos.type,
          side: pos.size > 0 ? 'buy' : 'sell',
        });

        return {
          symbol: pos.symbol,
          pop: pop * 100, // Convert to percentage
        };
      } catch (error) {
        console.error(`Failed to calculate PoP for ${pos.symbol}:`, error);
        return { symbol: pos.symbol, pop: 0 };
      }
    });

    // Calculate overall strategy PoP (weighted by position size)
    const totalSize = parsedPos.reduce((sum, pos) => sum + Math.abs(pos.size), 0);
    const weightedPoP = positionsWithPoP.reduce((sum, posPoP, i) => {
      const weight = Math.abs(parsedPos[i].size) / totalSize;
      return sum + posPoP.pop * weight;
    }, 0);

    setPopData({
      strategyPoP: weightedPoP,
      positions: positionsWithPoP,
    });
  }, [parsedPositions]);

  // ========================================================================
  // FETCH GREEKS FROM API
  // ========================================================================
  
  useEffect(() => {
    if (!parsedPositions || !parsedPositions.positions.length) {
      setGreeksSource('calculated');
      return;
    }

    const { positions: parsedPos } = parsedPositions;
    
    // Extract unique symbols to fetch
    const symbols = [...new Set(parsedPos.map(p => p.symbol))];
    
    // Set loading state
    setGreeksSource('calculating');

    // Attempt to fetch Greeks from API
    getBatchGreeksFromAPI(symbols)
      .then((results) => {
        // Check if we got any successful API results
        const hasApiData = Object.values(results).some(r => r !== null);
        
        if (hasApiData) {
          setGreeksSource('api');
          console.log('✅ Using API Greeks for', symbols.length, 'symbols');
        } else {
          setGreeksSource('calculated');
          console.log('⚠️ Using calculated Greeks (API unavailable)');
        }
      })
      .catch((error) => {
        console.error('Failed to fetch Greeks from API:', error);
        setGreeksSource('calculated');
      });
  }, [parsedPositions]);

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

    const minPrice = spotPrice * (1 - priceRangePercent / 100);
    const maxPrice = spotPrice * (1 + priceRangePercent / 100);
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
        const CONTRACT_MULTIPLIER = getContractMultiplier(parsedPos[0]?.symbol); // Dynamic multiplier
        
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

    // Calculate Y-axis domain with sensible bounds
    // User requested: lower bound around -500, upper bound around +200
    const overallMax = Math.max(maxProfit, maxTargetProfit);
    const overallMin = Math.min(maxLoss, maxTargetLoss);

    // Apply sensible bounds with some flexibility based on actual data
    // Lower bound: use actual min but cap at -500 (or extend if needed)
    // Upper bound: use actual max but ensure at least +200
    const rawYMin = Math.min(overallMin, -100); // Ensure we show at least some loss area
    const rawYMax = Math.max(overallMax, 50); // Ensure we show at least some profit area

    // Apply user-requested bounds: -500 to +200 with flexibility
    const yMin = Math.max(rawYMin * 1.1, -500); // Cap lower at -500, with 10% padding
    const yMax = Math.min(Math.max(rawYMax * 1.2, 200), 500); // At least +200, cap at +500

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

    // Calculate probability distribution for overlay
    let probabilityData = [];
    if (parsedPos.length > 0) {
      try {
        // Use average IV and time to expiry
        const avgIV = parsedPos.reduce((sum, p) => sum + (p.iv || 0), 0) / parsedPos.length;
        const avgTimeToExpiry = parsedPos.reduce((sum, p) => sum + p.yearsToExpiry, 0) / parsedPos.length;
        
        // Calculate price distribution
        probabilityData = calculatePriceDistribution(
          spotPrice,
          avgIV,
          avgTimeToExpiry,
          data.length // Match number of points
        );
      } catch (error) {
        console.error('Failed to calculate probability distribution:', error);
      }
    }

    // Merge probability data into chart data
    const dataWithProbability = data.map((point, i) => ({
      ...point,
      probability: probabilityData[i]?.probability || 0,
    }));

    return {
      data: dataWithProbability,
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
  }, [parsedPositions, priceRangePercent, targetDaysFromNow, targetPricePercent]);

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

  // Calculate Y-axis domain for zoomed view (recalculate based on visible data)
  const zoomedYDomain = useMemo(() => {
    if (!displayData || displayData.length === 0)
      return [chartData?.yMin || -500, chartData?.yMax || 200];

    let minY = Infinity,
      maxY = -Infinity;
    displayData.forEach((d) => {
      if (d.expiry < minY) minY = d.expiry;
      if (d.expiry > maxY) maxY = d.expiry;
      if (d.target < minY) minY = d.target;
      if (d.target > maxY) maxY = d.target;
    });

    // Add padding
    const range = maxY - minY;
    const padding = Math.max(range * 0.15, 20); // At least $20 padding

    return [
      Math.max(minY - padding, -500), // Cap at -500
      Math.min(maxY + padding, 500), // Cap at +500
    ];
  }, [displayData, chartData]);

  // ========================================================================
  // RENDER
  // ========================================================================

  if (!chartData) {
    return (
      <Paper sx={{ p: 3, textAlign: 'center', bgcolor: 'background.default' }}>
        <Typography color="text.secondary">
          No visible positions to display payoff diagram
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

  // Custom Tooltip
  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload || !payload.length) return null;

    const expiry = payload.find((p) => p.dataKey === 'expiry')?.value ?? 0;
    const target = payload.find((p) => p.dataKey === 'target')?.value ?? 0;
    const probability = payload.find((p) => p.dataKey === 'probability')?.value ?? 0;

    return (
      <Paper
        sx={{ p: 1.5, bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider' }}
      >
        <Typography variant="body2" fontWeight="bold">
          BTC: ${Number(label).toLocaleString()}
        </Typography>
        <Divider sx={{ my: 0.5 }} />
        <Typography variant="body2" sx={{ color: expiry >= 0 ? '#10b981' : '#ef4444' }}>
          On Expiry:{' '}
          <strong>
            {expiry >= 0 ? '+' : ''}${expiry.toFixed(2)}
          </strong>
        </Typography>
        <Typography variant="body2" sx={{ color: '#3b82f6' }}>
          On Target Date:{' '}
          <strong>
            {target >= 0 ? '+' : ''}${target.toFixed(2)}
          </strong>
        </Typography>
        {probability > 0 && (
          <Typography variant="body2" sx={{ color: '#10b981', mt: 0.5 }}>
            Probability:{' '}
            <strong>
              {probability.toFixed(1)}%
            </strong>
          </Typography>
        )}
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
          Payoff Graph {futuresPositions.length > 0 && `(Options + Futures)`}
        </Typography>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {/* Probability of Profit Badge */}
          {popData && (
            <Chip
              label={`PoP: ${popData.strategyPoP.toFixed(1)}%`}
              size="small"
              sx={{
                bgcolor: popData.strategyPoP > 50 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                color: popData.strategyPoP > 50 ? '#10b981' : '#ef4444',
                fontWeight: 'bold',
                fontSize: '0.75rem',
              }}
              title="Probability of Profit at expiry"
            />
          )}

          {/* Greeks Source Indicator */}
          <Chip
            icon={greeksSource === 'api' ? <ApiIcon /> : <CalculateIcon />}
            label={greeksSource === 'api' ? 'API Greeks' : greeksSource === 'calculated' ? 'Calc Greeks' : 'Loading...'}
            size="small"
            variant="outlined"
            sx={{
              borderColor: greeksSource === 'api' ? 'rgba(16, 185, 129, 0.5)' : 'rgba(255, 152, 0, 0.5)',
              color: greeksSource === 'api' ? '#10b981' : '#ff9800',
              fontSize: '0.7rem',
            }}
            title={greeksSource === 'api' ? 'Using real-time Greeks from Delta Exchange API' : 'Using calculated Greeks (fallback)'}
          />

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
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Box 
              sx={{ 
                width: 24, 
                height: 3, 
                bgcolor: '#10b981',
                opacity: 0.7,
                borderTop: '3px dashed #10b981',
                height: 0,
                marginTop: '1.5px',
              }} 
            />
            <Typography variant="caption" color="text.secondary">
              Probability
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
            yAxisId="left"
          />
          
          {/* Secondary Y-axis for Probability (0-100%) */}
          <YAxis
            yAxisId="right"
            orientation="right"
            tickFormatter={(v) => `${v.toFixed(0)}%`}
            stroke="#10b981"
            tick={{ fontSize: 11, fill: '#10b981' }}
            domain={[0, 100]}
            label={{
              value: 'Probability (%)',
              angle: 90,
              position: 'insideRight',
              fill: '#10b981',
              fontSize: 11,
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
            yAxisId="left"
          />

          {/* Loss area (below zero) - Red fill */}
          <Area
            type="monotone"
            dataKey="expiryLoss"
            stroke="none"
            fill="url(#lossGradient)"
            fillOpacity={1}
            isAnimationActive={false}
            yAxisId="left"
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
            yAxisId="left"
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
            yAxisId="left"
          />

          {/* Probability Distribution Overlay - Dotted Green Line */}
          <Line
            type="monotone"
            dataKey="probability"
            stroke="#10b981"
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={false}
            name="Probability (%)"
            isAnimationActive={false}
            yAxisId="right"
            opacity={0.7}
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
