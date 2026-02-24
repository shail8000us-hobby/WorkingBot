/**
 * Payoff Calculator — Pure Math Functions for Options Payoff Diagram
 *
 * Extracted from OptionsPayoffDiagram.js for testability and reuse.
 * Contains: Black-Scholes pricing, IV solver, Normal distribution, helpers.
 *
 * Standards (Delta Exchange / Crypto):
 * - Risk-free rate: 0% (crypto — no carry cost, no dividends)
 * - Contract multipliers: 0.001 (BTC), 0.01 (ETH)
 * - European options only
 *
 * @version 1.0.0
 */

// ============================================================================
// CONSTANTS
// ============================================================================

export const RISK_FREE_RATE = 0.0; // Crypto standard — 0% (matches Delta Exchange & backend)

export const CONTRACT_MULTIPLIERS = {
  BTC: 0.001,
  ETH: 0.01,
};

/**
 * Get contract multiplier from symbol string.
 * @param {string} symbol - e.g. "C-BTC-65000-240226" or "ETH-PERP"
 * @returns {number} 0.001 for BTC, 0.01 for ETH
 */
export const getContractMultiplier = (symbol) => {
  if (!symbol) return CONTRACT_MULTIPLIERS.BTC;
  const upper = symbol.toUpperCase();
  if (upper.includes('ETH')) return CONTRACT_MULTIPLIERS.ETH;
  return CONTRACT_MULTIPLIERS.BTC;
};

// ============================================================================
// STATISTICAL FUNCTIONS
// ============================================================================

/**
 * Cumulative distribution function for standard normal distribution.
 * Abramowitz & Stegun approximation (5-term, accuracy ~1e-7).
 */
export const normalCDF = (x) => {
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

/**
 * Probability density function for standard normal distribution.
 */
export const normalPDF = (x) => Math.exp(-0.5 * x * x) / Math.sqrt(2 * Math.PI);

// ============================================================================
// BLACK-SCHOLES MODEL
// ============================================================================

/**
 * Calculate Black-Scholes option price.
 *
 * @param {number} S - Spot price
 * @param {number} K - Strike price
 * @param {number} T - Time to expiry in years
 * @param {number} r - Risk-free rate (0.0 for crypto)
 * @param {number} sigma - Implied volatility (e.g. 0.8 for 80%)
 * @param {string} type - 'call' or 'put'
 * @returns {number} Theoretical option price
 */
export const blackScholesPrice = (S, K, T, r, sigma, type) => {
  if (T <= 0) return type === 'call' ? Math.max(0, S - K) : Math.max(0, K - S);
  if (sigma <= 0 || S <= 0 || K <= 0)
    return type === 'call' ? Math.max(0, S - K) : Math.max(0, K - S);

  const sqrtT = Math.sqrt(T);
  const d1 = (Math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrtT);
  const d2 = d1 - sigma * sqrtT;

  const price =
    type === 'call'
      ? S * normalCDF(d1) - K * Math.exp(-r * T) * normalCDF(d2)
      : K * Math.exp(-r * T) * normalCDF(-d2) - S * normalCDF(-d1);

  return isFinite(price) ? Math.max(0, price) : 0;
};

// ============================================================================
// IMPLIED VOLATILITY SOLVER
// ============================================================================

/**
 * Calculate implied volatility using Newton-Raphson with bisection fallback.
 *
 * @param {number} marketPrice - Observed option market price
 * @param {number} S - Spot price
 * @param {number} K - Strike price
 * @param {number} T - Time to expiry in years
 * @param {number} r - Risk-free rate
 * @param {string} type - 'call' or 'put'
 * @returns {number} Implied volatility (e.g. 0.8 for 80%)
 */
export const calculateImpliedVolatility = (marketPrice, S, K, T, r, type) => {
  if (T <= 0 || marketPrice <= 0) return 0.8;

  // Initial guess using Brenner-Subrahmanyam approximation
  let sigma = Math.sqrt((2 * Math.PI) / T) * (marketPrice / S);
  sigma = Math.max(0.1, Math.min(3.0, sigma));

  // Newton-Raphson (50 iterations max)
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

  // Bisection fallback (100 iterations)
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
// GREEKS (Optional — for tooltip enhancement)
// ============================================================================

/**
 * Calculate portfolio delta at a given spot price.
 *
 * @param {number} S - Spot price
 * @param {Array} positions - Parsed positions array
 * @param {number} targetDaysFromNow - Days from now for target date
 * @param {number} r - Risk-free rate
 * @returns {number} Portfolio delta
 */
export const calculatePortfolioDelta = (S, positions, targetDaysFromNow = 0, r = RISK_FREE_RATE) => {
  let totalDelta = 0;
  positions.forEach((pos) => {
    if (pos.isClosed) return;
    const remainingYears = Math.max(0.0001, (pos.daysToExpiry - targetDaysFromNow) / 365.25);
    if (pos.iv <= 0 || S <= 0 || pos.strike <= 0) return;

    const sqrtT = Math.sqrt(remainingYears);
    const d1 = (Math.log(S / pos.strike) + (r + 0.5 * pos.iv * pos.iv) * remainingYears) / (pos.iv * sqrtT);
    const multiplier = getContractMultiplier(pos.symbol);

    let delta;
    if (pos.type === 'call') {
      delta = normalCDF(d1);
    } else {
      delta = normalCDF(d1) - 1;
    }
    totalDelta += delta * pos.size * multiplier;
  });
  return totalDelta;
};

// ============================================================================
// PROBABILITY DISTRIBUTION (Phase E3)
// ============================================================================

/**
 * Create a lognormal price distribution function for a given time horizon.
 * Returns a function price → raw probability density.
 * Caller should normalize values (e.g. 0-100) for chart overlay.
 *
 * @param {number} spot - Current spot price
 * @param {number} volatility - Annualized IV (e.g. 0.8 for 80%)
 * @param {number} T - Time horizon in years
 * @returns {Function} price → density (raw PDF value)
 */
export const createPriceDistribution = (spot, volatility, T) => {
  if (T <= 0 || volatility <= 0 || spot <= 0) return () => 0;

  const sigma = Math.max(0.05, Math.min(5.0, volatility));
  // Drift: μ = ln(S) + (r - ½σ²)T, with r=0 for crypto
  const mu = Math.log(spot) + (-0.5 * sigma * sigma) * T;
  const sigmaT = sigma * Math.sqrt(T);
  const coeff = 1 / (sigmaT * Math.sqrt(2 * Math.PI));

  return (price) => {
    if (price <= 0) return 0;
    const z = (Math.log(price) - mu) / sigmaT;
    return coeff * Math.exp(-0.5 * z * z) / price;
  };
};

/**
 * Calculate weighted average IV from portfolio positions.
 * Weights by notional value (|size| × strike × multiplier) so larger
 * positions have proportionally more influence on the distribution.
 *
 * @param {Array} positions - Parsed positions array
 * @returns {number} Weighted average IV (fallback 0.8)
 */
export const calculateWeightedIV = (positions) => {
  if (!positions || positions.length === 0) return 0.8;

  const nonClosed = positions.filter((p) => !p.isClosed && p.iv > 0);
  if (nonClosed.length === 0) return 0.8;

  let totalWeight = 0;
  let weightedSum = 0;

  nonClosed.forEach((pos) => {
    const multiplier = getContractMultiplier(pos.symbol);
    const weight = Math.abs(pos.size) * pos.strike * multiplier;
    weightedSum += pos.iv * weight;
    totalWeight += weight;
  });

  return totalWeight > 0 ? weightedSum / totalWeight : 0.8;
};

// ============================================================================
// HELPERS
// ============================================================================

/**
 * Format date for display in payoff diagram.
 */
export const formatDate = (date) => {
  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${days[date.getDay()]}, ${date.getDate()} ${months[date.getMonth()]} ${date.getHours()}:${String(date.getMinutes()).padStart(2, '0')} PM`;
};
