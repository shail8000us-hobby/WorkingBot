/**
 * useSSRAlgoPayoff Hook
 * 
 * Custom hook for calculating and managing payoff data for SSR Algo sessions.
 * Provides payoff chart data, breakeven points, and P&L calculations.
 * 
 * Per Implementation Plan: Section 3.2
 * Created: February 3, 2026
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import ssrAlgoService from '../ssrAlgoService';

/**
 * Calculate payoff at a specific price point
 * @param {Array} positions - Array of position objects
 * @param {number} price - Price to calculate payoff at
 * @param {number} lotSize - Contract lot size
 * @returns {number} Total P&L at this price
 */
const calculatePayoffAtPrice = (positions, price, lotSize = 1) => {
  if (!positions || !Array.isArray(positions) || positions.length === 0) {
    return 0;
  }

  let totalPnL = 0;

  positions.forEach(posGroup => {
    // Handle grouped positions by trigger_id
    const legs = [
      posGroup.atm_ce,
      posGroup.atm_pe,
      posGroup.otm_ce_buy,
      posGroup.otm_pe_buy,
      posGroup.far_otm_ce,
      posGroup.far_otm_pe,
    ].filter(Boolean);

    legs.forEach(leg => {
      if (!leg || !leg.symbol) return;

      const isCall = leg.symbol.startsWith('C-');
      const isPut = leg.symbol.startsWith('P-');
      const strikeMatch = leg.symbol.match(/-(\d+)-/);
      const strike = strikeMatch ? parseInt(strikeMatch[1], 10) : 0;
      const size = leg.size || 0;
      const entryPremium = leg.entry_premium || leg.selected_premium || 0;

      if (!strike) return;

      let intrinsicValue = 0;
      if (isCall) {
        intrinsicValue = Math.max(0, price - strike);
      } else if (isPut) {
        intrinsicValue = Math.max(0, strike - price);
      }

      // P&L = (Current Value - Entry Premium) * Size * Lot Size
      // For sold positions (size < 0), profit when option expires worthless
      const currentValue = intrinsicValue;
      const pnl = (entryPremium - currentValue) * size * lotSize;
      
      totalPnL += pnl;
    });
  });

  return totalPnL;
};

/**
 * Generate payoff chart data points
 * @param {Object} session - Session data with positions
 * @param {number} currentPrice - Current underlying price
 * @param {number} range - Price range percentage (default 20%)
 * @param {number} points - Number of data points (default 100)
 * @returns {Array} Array of {price, pnl} data points
 */
const generatePayoffPoints = (session, currentPrice, range = 0.20, points = 100) => {
  if (!session?.positions || !currentPrice) {
    return [];
  }

  const minPrice = currentPrice * (1 - range);
  const maxPrice = currentPrice * (1 + range);
  const step = (maxPrice - minPrice) / points;
  
  const dataPoints = [];
  for (let i = 0; i <= points; i++) {
    const price = minPrice + (step * i);
    const pnl = calculatePayoffAtPrice(session.positions, price);
    dataPoints.push({
      price: Math.round(price),
      pnl: Math.round(pnl * 100) / 100,
    });
  }

  return dataPoints;
};

/**
 * Find breakeven points where P&L crosses zero
 * @param {Array} payoffPoints - Array of {price, pnl} points
 * @returns {Array} Array of breakeven prices
 */
const findBreakevenPoints = (payoffPoints) => {
  if (!payoffPoints || payoffPoints.length < 2) {
    return [];
  }

  const breakevens = [];
  
  for (let i = 1; i < payoffPoints.length; i++) {
    const prev = payoffPoints[i - 1];
    const curr = payoffPoints[i];
    
    // Check if P&L crossed zero
    if ((prev.pnl < 0 && curr.pnl >= 0) || (prev.pnl >= 0 && curr.pnl < 0)) {
      // Linear interpolation to find exact crossing point
      const ratio = Math.abs(prev.pnl) / (Math.abs(prev.pnl) + Math.abs(curr.pnl));
      const breakevenPrice = prev.price + (curr.price - prev.price) * ratio;
      breakevens.push(Math.round(breakevenPrice));
    }
  }

  return breakevens;
};

/**
 * Calculate max profit and max loss from payoff data
 * @param {Array} payoffPoints - Array of {price, pnl} points
 * @returns {Object} {maxProfit, maxLoss, maxProfitPrice, maxLossPrice}
 */
const calculateExtremes = (payoffPoints) => {
  if (!payoffPoints || payoffPoints.length === 0) {
    return { maxProfit: 0, maxLoss: 0, maxProfitPrice: 0, maxLossPrice: 0 };
  }

  let maxProfit = -Infinity;
  let maxLoss = Infinity;
  let maxProfitPrice = 0;
  let maxLossPrice = 0;

  payoffPoints.forEach(point => {
    if (point.pnl > maxProfit) {
      maxProfit = point.pnl;
      maxProfitPrice = point.price;
    }
    if (point.pnl < maxLoss) {
      maxLoss = point.pnl;
      maxLossPrice = point.price;
    }
  });

  return {
    maxProfit: Math.round(maxProfit * 100) / 100,
    maxLoss: Math.round(maxLoss * 100) / 100,
    maxProfitPrice,
    maxLossPrice,
  };
};

/**
 * Custom hook for SSR Algo payoff calculations
 * @param {string} sessionId - Session ID
 * @param {Object} options - Hook options
 * @returns {Object} Payoff data and calculations
 */
export const useSSRAlgoPayoff = (sessionId, options = {}) => {
  const {
    autoRefresh = true,
    refreshInterval = 30000,
    priceRange = 0.20,
    dataPoints = 100,
  } = options;

  // State
  const [session, setSession] = useState(null);
  const [currentPrice, setCurrentPrice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [serverPayoff, setServerPayoff] = useState(null);

  // Fetch session and payoff data
  const fetchData = useCallback(async (showLoading = true) => {
    if (!sessionId) return;

    if (showLoading) setLoading(true);

    try {
      // Fetch session
      const sessionResult = await ssrAlgoService.getSession(sessionId);
      if (sessionResult.success) {
        setSession(sessionResult.session);
        
        // Get current price from monitor status
        if (sessionResult.session?.monitor_status?.current_price) {
          setCurrentPrice(sessionResult.session.monitor_status.current_price);
        }
      }

      // Fetch payoff from server
      const payoffResult = await ssrAlgoService.getSessionPayoff(sessionId);
      if (payoffResult.success) {
        setServerPayoff(payoffResult);
        if (payoffResult.current_price) {
          setCurrentPrice(payoffResult.current_price);
        }
      }

      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to fetch payoff data');
    } finally {
      if (showLoading) setLoading(false);
    }
  }, [sessionId]);

  // Initial fetch
  useEffect(() => {
    fetchData();
  }, [sessionId, fetchData]);

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh || !sessionId) return;

    const interval = setInterval(() => {
      fetchData(false);
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [autoRefresh, sessionId, refreshInterval, fetchData]);

  // Calculated payoff data
  const payoffData = useMemo(() => {
    if (!session || !currentPrice) {
      return {
        points: [],
        breakevens: [],
        maxProfit: 0,
        maxLoss: 0,
        currentPnL: 0,
      };
    }

    // Generate payoff curve points
    const points = generatePayoffPoints(session, currentPrice, priceRange, dataPoints);
    
    // Find breakeven points
    const breakevens = findBreakevenPoints(points);
    
    // Calculate extremes
    const extremes = calculateExtremes(points);
    
    // Current P&L at current price
    const currentPnL = calculatePayoffAtPrice(session.positions, currentPrice);

    return {
      points,
      breakevens,
      ...extremes,
      currentPnL: Math.round(currentPnL * 100) / 100,
      maxLossUpper: session.max_loss_upper,
      maxLossLower: session.max_loss_lower,
    };
  }, [session, currentPrice, priceRange, dataPoints]);

  // Chart configuration
  const chartConfig = useMemo(() => {
    if (!session || !currentPrice) {
      return null;
    }

    return {
      xAxis: {
        label: 'Underlying Price',
        min: currentPrice * (1 - priceRange),
        max: currentPrice * (1 + priceRange),
      },
      yAxis: {
        label: 'Profit/Loss ($)',
      },
      markers: [
        {
          type: 'vertical',
          value: session.max_loss_lower,
          color: '#ef4444',
          label: 'Max Loss Lower',
          dashed: true,
        },
        {
          type: 'vertical',
          value: session.max_loss_upper,
          color: '#ef4444',
          label: 'Max Loss Upper',
          dashed: true,
        },
        {
          type: 'dot',
          x: currentPrice,
          y: payoffData.currentPnL,
          color: '#3b82f6',
          label: 'Current',
          size: 8,
        },
        ...payoffData.breakevens.map(be => ({
          type: 'vertical',
          value: be,
          color: '#f59e0b',
          label: 'Breakeven',
          dashed: true,
        })),
      ],
      zones: [
        {
          x: [payoffData.points[0]?.price || 0, session.max_loss_lower],
          fill: 'rgba(239, 68, 68, 0.1)',
          label: 'Danger Zone',
        },
        {
          x: [session.max_loss_lower, session.max_loss_upper],
          fill: 'rgba(34, 197, 94, 0.1)',
          label: 'Profit Zone',
        },
        {
          x: [session.max_loss_upper, payoffData.points[payoffData.points.length - 1]?.price || 0],
          fill: 'rgba(239, 68, 68, 0.1)',
          label: 'Danger Zone',
        },
      ],
    };
  }, [session, currentPrice, priceRange, payoffData]);

  return {
    // Data
    session,
    currentPrice,
    serverPayoff,
    
    // Calculated data
    payoffPoints: payoffData.points,
    breakevens: payoffData.breakevens,
    maxProfit: payoffData.maxProfit,
    maxLoss: payoffData.maxLoss,
    maxProfitPrice: payoffData.maxProfitPrice,
    maxLossPrice: payoffData.maxLossPrice,
    currentPnL: payoffData.currentPnL,
    maxLossUpper: payoffData.maxLossUpper,
    maxLossLower: payoffData.maxLossLower,
    
    // Chart config
    chartConfig,
    
    // Status
    loading,
    error,
    
    // Actions
    refresh: () => fetchData(false),
    
    // Utilities
    calculateAtPrice: (price) => calculatePayoffAtPrice(session?.positions, price),
  };
};

export default useSSRAlgoPayoff;
