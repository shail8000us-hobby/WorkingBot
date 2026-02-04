/**
 * Max Loss Calculator Utility
 * 
 * Client-side utilities for calculating max loss points and payoff metrics.
 * Used for visualization and real-time calculations.
 * 
 * Per Implementation Plan: Section 2.3 - utils/maxLossCalculator.js
 * Created: February 3, 2026
 */

/**
 * Calculate payoff at a specific price point for a single leg
 * @param {Object} leg - Position leg data
 * @param {number} price - Expiry price
 * @returns {number} P&L for this leg
 */
const calculateLegPayoff = (leg, price) => {
  if (!leg || !leg.symbol) return 0;

  const isCall = leg.symbol.startsWith('C-');
  const isPut = leg.symbol.startsWith('P-');
  const strikeMatch = leg.symbol.match(/-(\d+)-/);
  const strike = strikeMatch ? parseInt(strikeMatch[1], 10) : 0;
  const size = leg.size || 0;
  const entryPremium = leg.entry_premium || leg.selected_premium || 0;

  if (!strike) return 0;

  // Calculate intrinsic value at expiry
  let intrinsicValue = 0;
  if (isCall) {
    intrinsicValue = Math.max(0, price - strike);
  } else if (isPut) {
    intrinsicValue = Math.max(0, strike - price);
  }

  // P&L = (Entry Premium - Expiry Value) * Size
  // For SELL (size < 0): Profit when option expires worthless
  // For BUY (size > 0): Profit when option has value
  const pnl = (entryPremium - intrinsicValue) * size;
  
  return pnl;
};

/**
 * Calculate total payoff for all positions at a specific price
 * @param {Array} positions - Array of position groups
 * @param {number} price - Expiry price
 * @param {number} lotSize - Contract lot size (default 1)
 * @returns {number} Total P&L
 */
export const calculateTotalPayoff = (positions, price, lotSize = 1) => {
  if (!positions || !Array.isArray(positions) || positions.length === 0) {
    return 0;
  }

  let totalPnL = 0;

  positions.forEach(posGroup => {
    const legs = [
      posGroup.atm_ce,
      posGroup.atm_pe,
      posGroup.otm_ce_buy,
      posGroup.otm_pe_buy,
      posGroup.far_otm_ce,
      posGroup.far_otm_pe,
    ].filter(Boolean);

    legs.forEach(leg => {
      totalPnL += calculateLegPayoff(leg, price) * lotSize;
    });
  });

  // Add closed position P&L
  if (positions[0]?.closed_positions) {
    positions[0].closed_positions.forEach(cp => {
      totalPnL += cp.realized_pnl || 0;
    });
  }

  return totalPnL;
};

/**
 * Find max loss points (where payoff curve reaches minimum)
 * @param {Array} positions - Array of position groups
 * @param {number} spotPrice - Current spot price
 * @param {number} range - Price range percentage (default 30%)
 * @param {number} step - Price step size (default 100)
 * @returns {Object} Max loss points { upper, lower, maxLossValue }
 */
export const findMaxLossPoints = (positions, spotPrice, range = 0.30, step = 100) => {
  if (!positions || positions.length === 0 || !spotPrice) {
    return { upper: null, lower: null, maxLossValue: 0 };
  }

  const minPrice = spotPrice * (1 - range);
  const maxPrice = spotPrice * (1 + range);
  
  let maxLossUpper = null;
  let maxLossLower = null;
  let maxLossValue = Infinity;
  
  // Find ATM strike to determine search direction
  const atmStrike = positions[0]?.atm_strike || spotPrice;

  // Search above ATM for upper max loss
  let currentPrice = atmStrike;
  let prevPayoff = calculateTotalPayoff(positions, currentPrice);
  
  while (currentPrice < maxPrice) {
    currentPrice += step;
    const payoff = calculateTotalPayoff(positions, currentPrice);
    
    // Found local minimum (payoff starts increasing)
    if (payoff > prevPayoff && prevPayoff < maxLossValue) {
      maxLossUpper = currentPrice - step;
      maxLossValue = prevPayoff;
    }
    prevPayoff = payoff;
  }

  // Search below ATM for lower max loss
  currentPrice = atmStrike;
  prevPayoff = calculateTotalPayoff(positions, currentPrice);
  
  while (currentPrice > minPrice) {
    currentPrice -= step;
    const payoff = calculateTotalPayoff(positions, currentPrice);
    
    // Found local minimum (payoff starts increasing)
    if (payoff > prevPayoff && prevPayoff < maxLossValue) {
      maxLossLower = currentPrice + step;
      if (prevPayoff < maxLossValue) {
        maxLossValue = prevPayoff;
      }
    }
    prevPayoff = payoff;
  }

  return {
    upper: maxLossUpper ? Math.round(maxLossUpper) : null,
    lower: maxLossLower ? Math.round(maxLossLower) : null,
    maxLossValue: Math.round(maxLossValue * 100) / 100,
  };
};

/**
 * Generate payoff curve data points
 * @param {Array} positions - Array of position groups
 * @param {number} spotPrice - Current spot price
 * @param {Object} options - Generation options
 * @returns {Array} Array of { price, pnl } points
 */
export const generatePayoffCurve = (positions, spotPrice, options = {}) => {
  const {
    range = 0.25,
    points = 100,
    lotSize = 1,
  } = options;

  if (!positions || positions.length === 0 || !spotPrice) {
    return [];
  }

  const minPrice = spotPrice * (1 - range);
  const maxPrice = spotPrice * (1 + range);
  const stepSize = (maxPrice - minPrice) / points;
  
  const dataPoints = [];
  
  for (let i = 0; i <= points; i++) {
    const price = minPrice + (stepSize * i);
    const pnl = calculateTotalPayoff(positions, price, lotSize);
    
    dataPoints.push({
      price: Math.round(price),
      pnl: Math.round(pnl * 100) / 100,
    });
  }

  return dataPoints;
};

/**
 * Calculate key payoff metrics
 * @param {Array} payoffPoints - Array of { price, pnl } points
 * @param {number} currentPrice - Current spot price
 * @returns {Object} Payoff metrics
 */
export const calculatePayoffMetrics = (payoffPoints, currentPrice) => {
  if (!payoffPoints || payoffPoints.length === 0) {
    return {
      maxProfit: 0,
      maxLoss: 0,
      maxProfitPrice: null,
      maxLossPrice: null,
      currentPnL: 0,
      breakevens: [],
    };
  }

  let maxProfit = -Infinity;
  let maxLoss = Infinity;
  let maxProfitPrice = null;
  let maxLossPrice = null;
  const breakevens = [];

  // Find extremes and breakevens
  for (let i = 0; i < payoffPoints.length; i++) {
    const point = payoffPoints[i];
    
    if (point.pnl > maxProfit) {
      maxProfit = point.pnl;
      maxProfitPrice = point.price;
    }
    
    if (point.pnl < maxLoss) {
      maxLoss = point.pnl;
      maxLossPrice = point.price;
    }

    // Find breakeven crossings
    if (i > 0) {
      const prev = payoffPoints[i - 1];
      if ((prev.pnl < 0 && point.pnl >= 0) || (prev.pnl >= 0 && point.pnl < 0)) {
        // Linear interpolation
        const ratio = Math.abs(prev.pnl) / (Math.abs(prev.pnl) + Math.abs(point.pnl));
        const breakevenPrice = prev.price + (point.price - prev.price) * ratio;
        breakevens.push(Math.round(breakevenPrice));
      }
    }
  }

  // Find current P&L
  const currentPoint = payoffPoints.find(p => p.price === Math.round(currentPrice));
  const currentPnL = currentPoint?.pnl || calculateTotalPayoff([], currentPrice);

  return {
    maxProfit: Math.round(maxProfit * 100) / 100,
    maxLoss: Math.round(maxLoss * 100) / 100,
    maxProfitPrice,
    maxLossPrice,
    currentPnL: Math.round(currentPnL * 100) / 100,
    breakevens,
  };
};

/**
 * Determine zone status based on price and max loss points
 * @param {number} currentPrice - Current price
 * @param {number} maxLossUpper - Upper max loss point
 * @param {number} maxLossLower - Lower max loss point
 * @param {number} tolerance - Price tolerance (default 100)
 * @returns {Object} Zone status
 */
export const getZoneStatus = (currentPrice, maxLossUpper, maxLossLower, tolerance = 100) => {
  if (!currentPrice || !maxLossUpper || !maxLossLower) {
    return {
      zone: 'unknown',
      status: 'unknown',
      inDanger: false,
      distance: null,
    };
  }

  const distanceToUpper = maxLossUpper - currentPrice;
  const distanceToLower = currentPrice - maxLossLower;

  // In upper danger zone
  if (currentPrice >= maxLossUpper - tolerance) {
    return {
      zone: 'upper',
      status: currentPrice >= maxLossUpper ? 'breached' : 'warning',
      inDanger: true,
      distance: -distanceToUpper,
      percentDistance: (Math.abs(distanceToUpper) / currentPrice) * 100,
    };
  }

  // In lower danger zone
  if (currentPrice <= maxLossLower + tolerance) {
    return {
      zone: 'lower',
      status: currentPrice <= maxLossLower ? 'breached' : 'warning',
      inDanger: true,
      distance: -distanceToLower,
      percentDistance: (Math.abs(distanceToLower) / currentPrice) * 100,
    };
  }

  // In safe/profit zone
  return {
    zone: 'profit',
    status: 'safe',
    inDanger: false,
    distanceToUpper,
    distanceToLower,
    nearestBoundary: distanceToUpper < distanceToLower ? 'upper' : 'lower',
    nearestDistance: Math.min(distanceToUpper, distanceToLower),
    percentToNearest: (Math.min(distanceToUpper, distanceToLower) / currentPrice) * 100,
  };
};

/**
 * Calculate price zone indicator bar percentages
 * @param {number} currentPrice - Current price
 * @param {number} maxLossUpper - Upper max loss point
 * @param {number} maxLossLower - Lower max loss point
 * @param {number} padding - Padding percentage (default 10%)
 * @returns {Object} Bar percentages for visualization
 */
export const calculateZoneBarPercentages = (currentPrice, maxLossUpper, maxLossLower, padding = 0.10) => {
  if (!currentPrice || !maxLossUpper || !maxLossLower) {
    return null;
  }

  const totalRange = (maxLossUpper - maxLossLower) * (1 + padding * 2);
  const paddedMin = maxLossLower - (maxLossUpper - maxLossLower) * padding;
  const paddedMax = maxLossUpper + (maxLossUpper - maxLossLower) * padding;

  // Calculate positions as percentages
  const lowerZoneEnd = ((maxLossLower - paddedMin) / totalRange) * 100;
  const upperZoneStart = ((maxLossUpper - paddedMin) / totalRange) * 100;
  const currentPosition = ((currentPrice - paddedMin) / totalRange) * 100;

  return {
    lowerZonePercent: lowerZoneEnd,
    profitZonePercent: upperZoneStart - lowerZoneEnd,
    upperZonePercent: 100 - upperZoneStart,
    currentPositionPercent: Math.max(0, Math.min(100, currentPosition)),
    minPrice: Math.round(paddedMin),
    maxPrice: Math.round(paddedMax),
    lowerBoundary: maxLossLower,
    upperBoundary: maxLossUpper,
  };
};

/**
 * Estimate Greeks impact (simplified)
 * @param {Array} positions - Position data
 * @param {number} currentPrice - Current spot price
 * @returns {Object} Estimated Greeks
 */
export const estimateGreeks = (positions, currentPrice) => {
  // Simplified Greeks estimation
  // In production, this would use Black-Scholes or similar
  
  let totalDelta = 0;
  let totalGamma = 0;
  let totalTheta = 0;
  let totalVega = 0;

  if (!positions || positions.length === 0) {
    return { delta: 0, gamma: 0, theta: 0, vega: 0 };
  }

  positions.forEach(posGroup => {
    const legs = [
      { ...posGroup.atm_ce, type: 'ce' },
      { ...posGroup.atm_pe, type: 'pe' },
      { ...posGroup.otm_ce_buy, type: 'ce' },
      { ...posGroup.otm_pe_buy, type: 'pe' },
      { ...posGroup.far_otm_ce, type: 'ce' },
      { ...posGroup.far_otm_pe, type: 'pe' },
    ].filter(l => l && l.symbol);

    legs.forEach(leg => {
      const size = leg.size || 0;
      const strikeMatch = leg.symbol?.match(/-(\d+)-/);
      const strike = strikeMatch ? parseInt(strikeMatch[1], 10) : currentPrice;
      
      // Simplified ATM delta approximation
      const moneyness = (currentPrice - strike) / strike;
      let delta = leg.type === 'ce' ? 0.5 + moneyness * 2 : -0.5 - moneyness * 2;
      delta = Math.max(-1, Math.min(1, delta));
      
      totalDelta += delta * size;
      totalGamma += 0.02 * Math.abs(size); // Simplified
      totalTheta -= 0.01 * Math.abs(size) * (leg.entry_premium || 0); // Simplified
      totalVega += 0.05 * Math.abs(size); // Simplified
    });
  });

  return {
    delta: Math.round(totalDelta * 100) / 100,
    gamma: Math.round(totalGamma * 100) / 100,
    theta: Math.round(totalTheta * 100) / 100,
    vega: Math.round(totalVega * 100) / 100,
  };
};

export default {
  calculateTotalPayoff,
  findMaxLossPoints,
  generatePayoffCurve,
  calculatePayoffMetrics,
  getZoneStatus,
  calculateZoneBarPercentages,
  estimateGreeks,
};
