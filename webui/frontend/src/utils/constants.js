/**
 * Trading Constants for Delta Exchange India
 * 
 * Contract specifications:
 * - BTC: 1 contract = 0.001 BTC
 * - ETH: 1 contract = 0.001 ETH
 * 
 * Reference: https://docs.delta.exchange/docs/trading-guide/
 */

// Contract multipliers (notional value per contract)
export const CONTRACT_MULTIPLIERS = {
  BTC: 0.001,
  ETH: 0.001,
  SOL: 0.001,  // Verify from API
  MATIC: 0.001,  // Verify from API
};

// Default multiplier for unknown assets
export const DEFAULT_CONTRACT_MULTIPLIER = 0.001;

/**
 * Get contract multiplier for a symbol
 * @param {string} symbol - Trading symbol (e.g., "BTCUSD", "C-BTC-95000-310125")
 * @returns {number} - Contract multiplier
 */
export function getContractMultiplier(symbol) {
  // Extract underlying asset from symbol
  // Examples: "BTCUSD" -> "BTC", "C-BTC-95000-310125" -> "BTC", "P-ETH-3000-280225" -> "ETH"
  
  if (!symbol) return DEFAULT_CONTRACT_MULTIPLIER;
  
  // For options: C-BTC-95000-310125 or P-BTC-95000-310125
  if (symbol.includes('-')) {
    const parts = symbol.split('-');
    if (parts.length >= 2) {
      const asset = parts[1]; // BTC, ETH, etc.
      return CONTRACT_MULTIPLIERS[asset] || DEFAULT_CONTRACT_MULTIPLIER;
    }
  }
  
  // For futures/perpetuals: BTCUSD, ETHUSD
  for (const asset of Object.keys(CONTRACT_MULTIPLIERS)) {
    if (symbol.startsWith(asset)) {
      return CONTRACT_MULTIPLIERS[asset];
    }
  }
  
  return DEFAULT_CONTRACT_MULTIPLIER;
}

// Risk-free rate for crypto (typically 0%)
export const RISK_FREE_RATE = 0.0;

// Dividend yield (crypto assets don't pay dividends)
export const DIVIDEND_YIELD = 0.0;

// Minimum volatility floor (prevent division by zero)
export const MIN_VOLATILITY = 0.05;  // 5%

// Maximum volatility cap (prevent extreme calculations)
export const MAX_VOLATILITY = 5.0;  // 500%

// Minimum time to expiry (in years) to prevent issues at expiry
export const MIN_TIME_TO_EXPIRY = 1 / (365 * 24);  // 1 hour

// Number of points for payoff calculation
export const DEFAULT_PAYOFF_POINTS = 200;

// Price range percentage for payoff chart (% around current price)
export const DEFAULT_PRICE_RANGE_PCT = 25;  // ±25%

// API endpoints
export const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:5555';
export const DELTA_EXCHANGE_API = 'https://api.india.delta.exchange';
export const DELTA_EXCHANGE_WS = 'wss://socket.india.delta.exchange';

// Color scheme for P&L
export const PNL_COLORS = {
  PROFIT: '#4caf50',      // Green
  LOSS: '#f44336',        // Red
  NEUTRAL: '#9e9e9e',     // Gray
  WARNING: '#ff9800',     // Orange
};

// Leverage risk levels
export const LEVERAGE_LEVELS = {
  SAFE: { max: 3, color: '#4caf50', label: 'Safe' },
  MEDIUM: { max: 5, color: '#ff9800', label: 'Medium Risk' },
  HIGH: { max: Infinity, color: '#f44336', label: 'High Risk' },
};

// Moneyness thresholds (% difference from spot)
export const MONEYNESS_THRESHOLD = 0.02;  // 2% = ATM

// Greeks update throttle (milliseconds)
export const GREEKS_UPDATE_THROTTLE = 1000;  // 1 second

// Max positions to display without virtualization
export const VIRTUAL_SCROLL_THRESHOLD = 50;

export default {
  CONTRACT_MULTIPLIERS,
  DEFAULT_CONTRACT_MULTIPLIER,
  getContractMultiplier,
  RISK_FREE_RATE,
  DIVIDEND_YIELD,
  MIN_VOLATILITY,
  MAX_VOLATILITY,
  MIN_TIME_TO_EXPIRY,
  DEFAULT_PAYOFF_POINTS,
  DEFAULT_PRICE_RANGE_PCT,
  API_BASE_URL,
  DELTA_EXCHANGE_API,
  DELTA_EXCHANGE_WS,
  PNL_COLORS,
  LEVERAGE_LEVELS,
  MONEYNESS_THRESHOLD,
  GREEKS_UPDATE_THROTTLE,
  VIRTUAL_SCROLL_THRESHOLD,
};
