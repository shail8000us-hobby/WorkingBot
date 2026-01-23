/**
 * Probability Calculations for Options
 * 
 * Calculates Probability of Profit (PoP) and other probability metrics
 * using Black-Scholes framework.
 */

import { RISK_FREE_RATE, DIVIDEND_YIELD, MIN_VOLATILITY, MIN_TIME_TO_EXPIRY } from './constants';

/**
 * Standard normal cumulative distribution function (CDF)
 * @param {number} x - Input value
 * @returns {number} - Probability
 */
export function normalCDF(x) {
  const t = 1 / (1 + 0.2316419 * Math.abs(x));
  const d = 0.3989423 * Math.exp(-x * x / 2);
  let prob = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));

  if (x > 0) {
    prob = 1 - prob;
  }

  return prob;
}

/**
 * Standard normal probability density function (PDF)
 * @param {number} x - Input value
 * @returns {number} - Density
 */
export function normalPDF(x) {
  return (1 / Math.sqrt(2 * Math.PI)) * Math.exp(-0.5 * x * x);
}

/**
 * Calculate d1 and d2 for Black-Scholes
 * @param {number} spotPrice - Current spot price
 * @param {number} strike - Strike price
 * @param {number} timeToExpiry - Time to expiry in years
 * @param {number} volatility - Implied volatility (annualized)
 * @param {number} riskFreeRate - Risk-free rate (default: 0 for crypto)
 * @param {number} dividendYield - Dividend yield (default: 0 for crypto)
 * @returns {Object} - {d1, d2}
 */
function calculateD1D2(spotPrice, strike, timeToExpiry, volatility, riskFreeRate = RISK_FREE_RATE, dividendYield = DIVIDEND_YIELD) {
  const T = Math.max(timeToExpiry, MIN_TIME_TO_EXPIRY);
  const vol = Math.max(volatility, MIN_VOLATILITY);
  
  const d1 = (Math.log(spotPrice / strike) + (riskFreeRate - dividendYield + 0.5 * vol * vol) * T) 
             / (vol * Math.sqrt(T));
  const d2 = d1 - vol * Math.sqrt(T);
  
  return { d1, d2 };
}

/**
 * Calculate Probability of Profit (PoP) for a single option position
 * 
 * PoP represents the probability that the option will be profitable at expiry.
 * For a long call: Probability that spot > breakeven
 * For a short call: Probability that spot < breakeven
 * 
 * @param {Object} params - Position parameters
 *   @param {number} params.spotPrice - Current spot price
 *   @param {number} params.strike - Strike price
 *   @param {number} params.entryPrice - Premium paid/received
 *   @param {number} params.timeToExpiry - Time to expiry in years
 *   @param {number} params.volatility - Implied volatility
 *   @param {string} params.optionType - 'call' or 'put'
 *   @param {string} params.side - 'buy' or 'sell'
 * @returns {number} - Probability of profit (0 to 1)
 */
export function calculatePoP({ spotPrice, strike, entryPrice, timeToExpiry, volatility, optionType, side }) {
  // Validate inputs
  if (!spotPrice || !strike || !volatility || spotPrice <= 0 || strike <= 0) {
    console.warn('calculatePoP: Invalid input parameters');
    return 0;
  }

  // Ensure positive time
  const T = Math.max(timeToExpiry, MIN_TIME_TO_EXPIRY);
  const vol = Math.max(volatility, MIN_VOLATILITY);

  // Calculate breakeven point
  let breakeven;
  if (optionType === 'call') {
    breakeven = side === 'buy' 
      ? strike + entryPrice  // Long call: need spot > strike + premium
      : strike + entryPrice; // Short call: profitable if spot < strike + premium
  } else { // put
    breakeven = side === 'buy'
      ? strike - entryPrice  // Long put: need spot < strike - premium
      : strike - entryPrice; // Short put: profitable if spot > strike - premium
  }

  // Calculate d2 for breakeven point (probability calculation)
  const { d2 } = calculateD1D2(spotPrice, breakeven, T, vol);

  // Calculate probability based on option type and side
  let pop;
  if (optionType === 'call') {
    if (side === 'buy') {
      // Long call: profit if spot > breakeven
      pop = normalCDF(d2);
    } else {
      // Short call: profit if spot < breakeven
      pop = 1 - normalCDF(d2);
    }
  } else { // put
    if (side === 'buy') {
      // Long put: profit if spot < breakeven
      pop = 1 - normalCDF(d2);
    } else {
      // Short put: profit if spot > breakeven
      pop = normalCDF(d2);
    }
  }

  return Math.max(0, Math.min(1, pop)); // Clamp to [0, 1]
}

/**
 * Calculate Probability of Profit for a multi-leg strategy
 * 
 * This is an approximation using Monte Carlo simulation.
 * For exact calculation, would need to integrate over all profitable price ranges.
 * 
 * @param {Array} positions - Array of position objects
 * @param {number} spotPrice - Current spot price
 * @param {number} volatility - Implied volatility for the underlying
 * @param {number} timeToExpiry - Time to expiry in years
 * @param {number} simulations - Number of Monte Carlo simulations (default: 10000)
 * @returns {Object} - {pop, expectedValue, profitPrices, lossPrices}
 */
export function calculateStrategyPoP(positions, spotPrice, volatility, timeToExpiry, simulations = 10000) {
  if (!positions || positions.length === 0) {
    return { pop: 0, expectedValue: 0, profitPrices: [], lossPrices: [] };
  }

  const T = Math.max(timeToExpiry, MIN_TIME_TO_EXPIRY);
  const vol = Math.max(volatility, MIN_VOLATILITY);

  let profitCount = 0;
  let totalPnL = 0;
  const profitPrices = [];
  const lossPrices = [];

  // Monte Carlo simulation
  for (let i = 0; i < simulations; i++) {
    // Generate random price at expiry using lognormal distribution
    const Z = normalInverse(Math.random());
    const finalPrice = spotPrice * Math.exp((RISK_FREE_RATE - 0.5 * vol * vol) * T + vol * Math.sqrt(T) * Z);

    // Calculate P&L at this price
    let pnl = 0;
    for (const pos of positions) {
      const intrinsic = calculateIntrinsicValue(finalPrice, pos.strike, pos.optionType);
      const positionPnL = (intrinsic - pos.entryPrice) * pos.size;
      pnl += pos.side === 'buy' ? positionPnL : -positionPnL;
    }

    // Track profit/loss
    if (pnl > 0) {
      profitCount++;
      profitPrices.push(finalPrice);
    } else {
      lossPrices.push(finalPrice);
    }
    totalPnL += pnl;
  }

  return {
    pop: profitCount / simulations,
    expectedValue: totalPnL / simulations,
    profitPrices: profitPrices.slice(0, 1000), // Limit array size
    lossPrices: lossPrices.slice(0, 1000),
  };
}

/**
 * Calculate intrinsic value of an option
 * @param {number} spotPrice - Current spot price
 * @param {number} strike - Strike price
 * @param {string} optionType - 'call' or 'put'
 * @returns {number} - Intrinsic value
 */
function calculateIntrinsicValue(spotPrice, strike, optionType) {
  if (optionType === 'call') {
    return Math.max(0, spotPrice - strike);
  } else {
    return Math.max(0, strike - spotPrice);
  }
}

/**
 * Inverse of standard normal CDF (approximate using Beasley-Springer-Moro algorithm)
 * @param {number} p - Probability (0 to 1)
 * @returns {number} - Z-score
 */
function normalInverse(p) {
  const a0 = 2.50662823884;
  const a1 = -18.61500062529;
  const a2 = 41.39119773534;
  const a3 = -25.44106049637;
  const b0 = -8.47351093090;
  const b1 = 23.08336743743;
  const b2 = -21.06224101826;
  const b3 = 3.13082909833;
  const c0 = 0.3374754822726147;
  const c1 = 0.9761690190917186;
  const c2 = 0.1607979714918209;
  const c3 = 0.0276438810333863;
  const c4 = 0.0038405729373609;
  const c5 = 0.0003951896511919;
  const c6 = 0.0000321767881768;
  const c7 = 0.0000002888167364;
  const c8 = 0.0000003960315187;

  if (p <= 0.0 || p >= 1.0) {
    return 0;
  }

  const y = p - 0.5;

  if (Math.abs(y) < 0.42) {
    const r = y * y;
    return y * (((a3 * r + a2) * r + a1) * r + a0) / ((((b3 * r + b2) * r + b1) * r + b0) * r + 1.0);
  }

  let r = p;
  if (y > 0.0) {
    r = 1.0 - p;
  }

  r = Math.log(-Math.log(r));
  const x = c0 + r * (c1 + r * (c2 + r * (c3 + r * (c4 + r * (c5 + r * (c6 + r * (c7 + r * c8)))))));

  if (y < 0.0) {
    return -x;
  }

  return x;
}

/**
 * Calculate probability distribution for plotting
 * @param {number} spotPrice - Current spot price
 * @param {number} volatility - Implied volatility
 * @param {number} timeToExpiry - Time to expiry in years
 * @param {number} numPoints - Number of points for distribution
 * @returns {Array} - Array of {price, probability} objects
 */
export function calculatePriceDistribution(spotPrice, volatility, timeToExpiry, numPoints = 100) {
  const T = Math.max(timeToExpiry, MIN_TIME_TO_EXPIRY);
  const vol = Math.max(volatility, MIN_VOLATILITY);

  const priceStdDev = spotPrice * vol * Math.sqrt(T);
  const minPrice = spotPrice - 3 * priceStdDev;
  const maxPrice = spotPrice + 3 * priceStdDev;
  const step = (maxPrice - minPrice) / numPoints;

  const distribution = [];
  for (let i = 0; i <= numPoints; i++) {
    const price = minPrice + i * step;
    
    // Lognormal PDF
    const logReturn = Math.log(price / spotPrice);
    const mean = (RISK_FREE_RATE - 0.5 * vol * vol) * T;
    const stdDev = vol * Math.sqrt(T);
    
    const z = (logReturn - mean) / stdDev;
    const prob = normalPDF(z) / (price * stdDev);

    distribution.push({ price, probability: prob });
  }

  return distribution;
}

export default {
  calculatePoP,
  calculateStrategyPoP,
  calculatePriceDistribution,
  normalCDF,
  normalPDF,
};
