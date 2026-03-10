/**
 * Adjustment Payoff Engine
 * ========================
 * Core calculation engine for position adjustment payoff analysis.
 * 
 * Features:
 * - Calculate payoff for current positions
 * - Calculate payoff for proposed combined positions
 * - Metrics calculation (max profit, max loss, breakevens, PoP)
 * - Greeks aggregation
 * 
 * Created: January 31, 2026
 */

import { getContractMultiplier, RISK_FREE_RATE } from '../../../utils/constants';
import { calculatePoP, normalCDF } from '../../../utils/probabilityCalc';

// ============================================================================
// PRICE RANGE GENERATION
// ============================================================================

/**
 * Generate array of price points for payoff calculation
 * @param {number} spotPrice - Current spot price
 * @param {number} rangePercent - Range as percentage (e.g., 15 for ±15%)
 * @param {number} points - Number of data points (default: 100)
 * @returns {number[]} Array of price points
 */
export function generatePriceRange(spotPrice, rangePercent = 15, points = 100) {
  const minPrice = spotPrice * (1 - rangePercent / 100);
  const maxPrice = spotPrice * (1 + rangePercent / 100);
  const step = (maxPrice - minPrice) / (points - 1);
  
  const prices = [];
  for (let i = 0; i < points; i++) {
    prices.push(Math.round(minPrice + i * step));
  }
  return prices;
}

// ============================================================================
// POSITION PARSING
// ============================================================================

/**
 * Parse position symbol to extract option details
 * @param {string} symbol - Option symbol (e.g., "C-BTC-82000-010226")
 * @returns {Object} Parsed details { type, underlying, strike, expiry }
 */
export function parsePositionSymbol(symbol) {
  if (!symbol) return null;
  
  const parts = symbol.split('-');
  if (parts.length < 4) return null;
  
  return {
    type: parts[0] === 'C' ? 'call' : 'put',
    underlying: parts[1], // BTC, ETH
    strike: parseFloat(parts[2]),
    expiry: parts[3], // DDMMYY
    symbol,
  };
}

/**
 * Format proposed trade as position object
 * @param {Object} trade - Proposed trade
 * @returns {Object} Position-like object for calculation
 */
export function formatProposedAsPosition(trade) {
  // Handle symbol format - might be C-BTC-82000-010226 or just need to build it
  let symbol = trade.symbol;
  
  // If no symbol, build it from trade properties
  if (!symbol && trade.strike && trade.type) {
    const typePrefix = trade.type === 'call' ? 'C' : 'P';
    const underlying = trade.underlying || 'BTC';
    const expiry = trade.expiry || '';
    symbol = `${typePrefix}-${underlying}-${trade.strike}-${expiry}`;
  }
  
  // Quantity handling - support both quantity and size fields
  const qty = Math.abs(trade.quantity || trade.size || 1);
  const size = trade.side === 'buy' ? qty : -qty;
  
  // Premium handling - support multiple field names
  const premium = trade.premium || trade.ltp || trade.price || trade.entry_price || 0;
  
  return {
    product_symbol: symbol,
    size: size,
    entry_price: Math.abs(premium),
    mark_price: Math.abs(premium),
    greeks: {
      delta: trade.delta || 0,
      gamma: trade.gamma || 0,
      theta: trade.theta || 0,
      vega: trade.vega || 0,
      spot: trade.spotPrice || 0,
    },
    // Include original trade type info
    _tradeType: trade.type,
    _tradeSide: trade.side,
    // Parsed details
    ...parsePositionSymbol(symbol),
  };
}

/**
 * Format array of proposed trades as positions
 * @param {Array} trades - Proposed trades
 * @returns {Array} Position-like objects
 */
export function formatProposedAsPositions(trades) {
  return trades.map(formatProposedAsPosition);
}

// ============================================================================
// SINGLE POSITION PAYOFF
// ============================================================================

/**
 * Calculate single position P&L at a given price (at expiry)
 * @param {Object} position - Position object with size, entry_price, etc.
 * @param {number} priceAtExpiry - Underlying price at expiry
 * @returns {number} P&L in USD
 */
export function calculateSinglePositionPayoff(position, priceAtExpiry) {
  const parsed = parsePositionSymbol(position.product_symbol);
  if (!parsed) return 0;
  
  const { type, strike, underlying } = parsed;
  const size = position.size || 0;
  const entryPrice = Math.abs(position.entry_price || 0);
  const contractMultiplier = getContractMultiplier(position.product_symbol);
  
  // Intrinsic value at expiry
  let intrinsic = 0;
  if (type === 'call') {
    intrinsic = Math.max(0, priceAtExpiry - strike);
  } else {
    intrinsic = Math.max(0, strike - priceAtExpiry);
  }
  
  // P&L calculation
  // Long (size > 0): Paid premium, profit from intrinsic
  // Short (size < 0): Received premium, loss from intrinsic
  const isLong = size > 0;
  const direction = isLong ? 1 : -1;
  
  // PnL = (Intrinsic - Premium) * |size| * direction * contractMultiplier
  // For long: profit when intrinsic > premium
  // For short: profit when intrinsic < premium (premium received)
  const pnl = (intrinsic - entryPrice) * direction * Math.abs(size) * contractMultiplier;
  
  return pnl;
}

// ============================================================================
// MULTI-POSITION PAYOFF
// ============================================================================

/**
 * Calculate total payoff for multiple positions at a given price
 * @param {Array} positions - Array of position objects
 * @param {number} priceAtExpiry - Underlying price at expiry
 * @returns {number} Total P&L in USD
 */
export function calculatePositionsPayoff(positions, priceAtExpiry) {
  if (!positions || positions.length === 0) return 0;
  
  return positions.reduce((total, pos) => {
    return total + calculateSinglePositionPayoff(pos, priceAtExpiry);
  }, 0);
}

/**
 * Calculate payoff data points for chart
 * @param {Array} positions - Position objects
 * @param {number[]} priceRange - Array of price points
 * @returns {Array} Array of { price, pnl } objects
 */
export function calculatePayoffCurve(positions, priceRange) {
  return priceRange.map(price => ({
    price,
    pnl: calculatePositionsPayoff(positions, price),
  }));
}

// ============================================================================
// BREAKEVEN CALCULATION
// ============================================================================

/**
 * Find breakeven points from payoff data
 * @param {Array} payoffData - Array of { price, pnl } objects
 * @returns {number[]} Array of breakeven prices
 */
export function findBreakevens(payoffData) {
  if (!payoffData || payoffData.length < 2) return [];
  
  const breakevens = [];
  
  for (let i = 1; i < payoffData.length; i++) {
    const prev = payoffData[i - 1];
    const curr = payoffData[i];
    
    // Check for zero crossing
    if ((prev.pnl <= 0 && curr.pnl >= 0) || (prev.pnl >= 0 && curr.pnl <= 0)) {
      // Linear interpolation for precise breakeven
      const pnlDiff = Math.abs(curr.pnl - prev.pnl);
      if (pnlDiff > 0) {
        const ratio = Math.abs(prev.pnl) / pnlDiff;
        const breakeven = prev.price + ratio * (curr.price - prev.price);
        breakevens.push(Math.round(breakeven * 100) / 100);
      }
    }
  }
  
  return breakevens;
}

// ============================================================================
// GREEKS AGGREGATION
// ============================================================================

/**
 * Calculate net Greek value for positions
 * @param {Array} positions - Position objects with greeks
 * @param {string} greekName - 'delta', 'gamma', 'theta', 'vega'
 * @returns {number} Net Greek value
 */
export function calculateNetGreek(positions, greekName) {
  if (!positions || positions.length === 0) return 0;
  
  return positions.reduce((total, pos) => {
    const greekValue = pos.greeks?.[greekName] || 0;
    const size = pos.size || 0;
    
    // Most Greeks scale with position size
    // Delta, Theta, Vega: multiply by size
    // Gamma: multiply by |size| (always positive for gamma exposure)
    if (greekName === 'gamma') {
      return total + greekValue * Math.abs(size);
    }
    
    // For theta and vega from Delta Exchange (divide by 1000 for USD)
    if (greekName === 'theta' || greekName === 'vega') {
      return total + (greekValue / 1000) * size;
    }
    
    return total + greekValue * size;
  }, 0);
}

/**
 * Calculate all aggregated Greeks for positions
 * @param {Array} positions - Position objects
 * @returns {Object} { delta, gamma, theta, vega }
 */
export function calculateAggregatedGreeks(positions) {
  return {
    delta: calculateNetGreek(positions, 'delta'),
    gamma: calculateNetGreek(positions, 'gamma'),
    theta: calculateNetGreek(positions, 'theta'),
    vega: calculateNetGreek(positions, 'vega'),
  };
}

// ============================================================================
// PREMIUM CALCULATION
// ============================================================================

/**
 * Calculate net premium for positions (positive = credit, negative = debit)
 * @param {Array} positions - Position objects
 * @returns {number} Net premium in USD
 */
export function calculateNetPremium(positions) {
  if (!positions || positions.length === 0) return 0;
  
  return positions.reduce((total, pos) => {
    const premium = Math.abs(pos.entry_price || 0);
    const size = Math.abs(pos.size || 0);
    const contractMultiplier = getContractMultiplier(pos.product_symbol);
    const isLong = (pos.size || 0) > 0;
    
    // Long = paid premium (debit, negative)
    // Short = received premium (credit, positive)
    const direction = isLong ? -1 : 1;
    
    return total + premium * size * contractMultiplier * direction;
  }, 0);
}

// ============================================================================
// PROBABILITY OF PROFIT
// ============================================================================

/**
 * Calculate strategy PoP based on positions and spot price
 * Uses simplified approach: % of payoff curve points that are profitable
 * 
 * @param {Array} payoffData - Payoff curve data
 * @returns {number} PoP as decimal (0-1)
 */
export function calculateStrategyPoP(payoffData) {
  if (!payoffData || payoffData.length === 0) return 0;
  
  const profitablePoints = payoffData.filter(d => d.pnl > 0).length;
  return profitablePoints / payoffData.length;
}

/**
 * Calculate more accurate PoP using Black-Scholes probability
 * For breakeven-based calculation
 * 
 * @param {number} spotPrice - Current spot price
 * @param {number[]} breakevens - Array of breakeven prices
 * @param {number} volatility - Annualized volatility
 * @param {number} timeToExpiry - Time to expiry in years
 * @param {boolean} isProfitAboveBreakeven - True if profit is above breakeven(s)
 * @returns {number} PoP as decimal (0-1)
 */
export function calculateBlackScholesPoP(spotPrice, breakevens, volatility, timeToExpiry, isProfitAboveBreakeven = true) {
  if (!breakevens || breakevens.length === 0 || !spotPrice || !volatility || timeToExpiry <= 0) {
    return 0.5; // Default to 50% if insufficient data
  }
  
  // For single breakeven, calculate probability
  if (breakevens.length === 1) {
    const breakeven = breakevens[0];
    const d2 = (Math.log(spotPrice / breakeven) + (-0.5 * volatility * volatility) * timeToExpiry) 
              / (volatility * Math.sqrt(timeToExpiry));
    
    const probBelowBreakeven = normalCDF(d2);
    return isProfitAboveBreakeven ? 1 - probBelowBreakeven : probBelowBreakeven;
  }
  
  // For multiple breakevens (spreads), calculate probability of being in profit zone
  // This is a simplification - for complex strategies, use payoff curve method
  const sortedBEs = [...breakevens].sort((a, b) => a - b);
  
  // Assume profit between breakevens (typical for iron condor, straddle, etc.)
  if (sortedBEs.length === 2) {
    const lowerBE = sortedBEs[0];
    const upperBE = sortedBEs[1];
    
    const d2Lower = (Math.log(spotPrice / lowerBE) + (-0.5 * volatility * volatility) * timeToExpiry) 
                   / (volatility * Math.sqrt(timeToExpiry));
    const d2Upper = (Math.log(spotPrice / upperBE) + (-0.5 * volatility * volatility) * timeToExpiry) 
                   / (volatility * Math.sqrt(timeToExpiry));
    
    const probBelowLower = normalCDF(d2Lower);
    const probBelowUpper = normalCDF(d2Upper);
    
    // Probability of being between breakevens
    return probBelowUpper - probBelowLower;
  }
  
  // Fallback to simple method for complex strategies
  return 0.5;
}

// ============================================================================
// METRICS CALCULATION
// ============================================================================

/**
 * Calculate PoP using lognormal probability distribution (risk-neutral measure).
 * Integrates PDF × (payoff > 0) across the price range.
 * Falls back to simple uniform-range count if insufficient data.
 */
function calculateLognormalPoP(payoffData, spotPrice, volatility, timeToExpiry) {
  if (!payoffData || payoffData.length < 2 || !spotPrice || !(volatility > 0) || !(timeToExpiry > 0)) {
    return calculateStrategyPoP(payoffData);
  }
  const sigma = Math.max(0.05, Math.min(5.0, volatility));
  const mu = Math.log(spotPrice) + (-0.5 * sigma * sigma) * timeToExpiry;
  const sigmaT = sigma * Math.sqrt(timeToExpiry);
  let profitProb = 0;
  let totalProb = 0;
  for (let i = 1; i < payoffData.length; i++) {
    const p = payoffData[i];
    const prevP = payoffData[i - 1];
    if (p.price <= 0) continue;
    const z = (Math.log(p.price) - mu) / sigmaT;
    const pdf = Math.exp(-0.5 * z * z) / (p.price * sigmaT * Math.sqrt(2 * Math.PI));
    const dp = p.price - prevP.price;
    const prob = pdf * dp;
    totalProb += prob;
    if (p.pnl > 0) profitProb += prob;
  }
  return totalProb > 0 ? profitProb / totalProb : calculateStrategyPoP(payoffData);
}

/**
 * Calculate comprehensive metrics for a set of positions
 * @param {Array} payoffData - Payoff curve data
 * @param {Array} positions - Position objects
 * @param {number} spotPrice - Current spot price
 * @param {number} volatility - Average IV (optional)
 * @param {number} timeToExpiry - Time to expiry in years (optional)
 * @returns {Object} Complete metrics
 */
export function calculateMetrics(payoffData, positions, spotPrice, volatility = 0.8, timeToExpiry = 0.1) {
  if (!payoffData || payoffData.length === 0) {
    return {
      maxProfit: 0,
      maxLoss: 0,
      breakevens: [],
      pop: 0,
      netDelta: 0,
      netGamma: 0,
      netTheta: 0,
      netVega: 0,
      netPremium: 0,
      riskReward: 0,
    };
  }
  
  const pnls = payoffData.map(d => d.pnl);
  const maxProfit = Math.max(...pnls);
  const maxLoss = Math.min(...pnls);
  const breakevens = findBreakevens(payoffData);
  
  // Calculate PoP using lognormal probability distribution (risk-neutral)
  const pop = calculateLognormalPoP(payoffData, spotPrice, volatility, timeToExpiry);
  
  // Greeks
  const greeks = calculateAggregatedGreeks(positions);
  
  // Net premium
  const netPremium = calculateNetPremium(positions);
  
  // Risk/Reward ratio
  const riskReward = maxLoss !== 0 ? Math.abs(maxProfit / maxLoss) : Infinity;
  
  return {
    maxProfit: Math.round(maxProfit * 100) / 100,
    maxLoss: Math.round(maxLoss * 100) / 100,
    breakevens,
    pop,
    netDelta: Math.round(greeks.delta * 1000) / 1000,
    netGamma: Math.round(greeks.gamma * 10000) / 10000,
    netTheta: Math.round(greeks.theta * 100) / 100,
    netVega: Math.round(greeks.vega * 100) / 100,
    netPremium: Math.round(netPremium * 100) / 100,
    riskReward: riskReward === Infinity ? 'Unlimited' : Math.round(riskReward * 100) / 100,
  };
}

// ============================================================================
// MAIN CALCULATION FUNCTION
// ============================================================================

/**
 * Calculate combined payoff for current + proposed positions
 * Main entry point for the adjustment system
 * 
 * @param {Array} currentPositions - Existing positions from API
 * @param {Array} proposedTrades - User-selected new trades
 * @param {number} spotPrice - Current underlying price
 * @param {number} rangePercent - Price range for chart (±%)
 * @returns {Object} { chartData, currentMetrics, combinedMetrics }
 */
export function calculateCombinedPayoff(currentPositions, proposedTrades, spotPrice, rangePercent = 15, customPriceRange = null) {
  if (!spotPrice || spotPrice <= 0) {
    return {
      chartData: [],
      currentMetrics: null,
      combinedMetrics: null,
      error: 'Invalid spot price',
    };
  }

  // Use custom price range if provided (dynamic, covers all strikes), else generate default
  const priceRange = customPriceRange || generatePriceRange(spotPrice, rangePercent);
  
  // Current positions payoff
  const currentPayoff = calculatePayoffCurve(currentPositions || [], priceRange);
  
  // Format proposed trades as positions
  const proposedPositions = formatProposedAsPositions(proposedTrades || []);
  
  // Combined positions (current + proposed)
  const combinedPositions = [...(currentPositions || []), ...proposedPositions];
  const combinedPayoff = calculatePayoffCurve(combinedPositions, priceRange);
  
  // Build chart data with both curves
  const chartData = priceRange.map((price, i) => ({
    price,
    current: Math.round(currentPayoff[i].pnl * 100) / 100,
    combined: Math.round(combinedPayoff[i].pnl * 100) / 100,
  }));
  
  // Calculate metrics for both scenarios
  const currentMetrics = calculateMetrics(currentPayoff, currentPositions || [], spotPrice);
  const combinedMetrics = calculateMetrics(combinedPayoff, combinedPositions, spotPrice);
  
  // Calculate the difference/change
  const metricsChange = {
    maxProfitChange: combinedMetrics.maxProfit - currentMetrics.maxProfit,
    maxLossChange: combinedMetrics.maxLoss - currentMetrics.maxLoss,
    popChange: combinedMetrics.pop - currentMetrics.pop,
    deltaChange: combinedMetrics.netDelta - currentMetrics.netDelta,
    thetaChange: combinedMetrics.netTheta - currentMetrics.netTheta,
    vegaChange: combinedMetrics.netVega - currentMetrics.netVega,
  };
  
  return {
    chartData,
    priceRange,
    currentPayoff,
    combinedPayoff,
    currentMetrics,
    combinedMetrics,
    metricsChange,
    proposedPositions,
    spotPrice,
  };
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Get time to expiry in years from expiry code
 * @param {string} expiryCode - DDMMYY format
 * @returns {number} Time to expiry in years
 */
export function getTimeToExpiry(expiryCode) {
  if (!expiryCode || expiryCode.length !== 6) return 0.1; // Default to ~36 days
  
  try {
    const day = parseInt(expiryCode.slice(0, 2));
    const month = parseInt(expiryCode.slice(2, 4)) - 1;
    const year = 2000 + parseInt(expiryCode.slice(4, 6));
    
    const expiryDate = new Date(year, month, day, 8, 0, 0); // 8am UTC
    const now = new Date();
    
    const diffMs = expiryDate - now;
    const diffYears = diffMs / (1000 * 60 * 60 * 24 * 365);
    
    return Math.max(diffYears, 0.001); // Minimum 1 hour
  } catch (e) {
    return 0.1;
  }
}

/**
 * Format currency value for display
 * @param {number} value - Value in USD
 * @param {boolean} showSign - Whether to show +/- sign
 * @returns {string} Formatted string
 */
export function formatCurrency(value, showSign = false) {
  if (value === null || value === undefined || isNaN(value)) return '-';
  
  const formatted = Math.abs(value).toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  
  if (showSign && value !== 0) {
    return value > 0 ? `+${formatted}` : `-${formatted.slice(1)}`;
  }
  
  return value < 0 ? `-${formatted.slice(1)}` : formatted;
}

/**
 * Format percentage for display
 * @param {number} value - Decimal value (0-1)
 * @param {boolean} showSign - Whether to show +/- sign
 * @returns {string} Formatted percentage string
 */
export function formatPercentage(value, showSign = false) {
  if (value === null || value === undefined || isNaN(value)) return '-';
  
  const pct = (value * 100).toFixed(1);
  
  if (showSign && value !== 0) {
    return value > 0 ? `+${pct}%` : `${pct}%`;
  }
  
  return `${pct}%`;
}

export default {
  calculateCombinedPayoff,
  calculateSinglePositionPayoff,
  calculatePositionsPayoff,
  calculatePayoffCurve,
  calculateMetrics,
  findBreakevens,
  calculateNetGreek,
  calculateAggregatedGreeks,
  calculateNetPremium,
  calculateStrategyPoP,
  generatePriceRange,
  parsePositionSymbol,
  formatProposedAsPosition,
  formatProposedAsPositions,
  getTimeToExpiry,
  formatCurrency,
  formatPercentage,
};
