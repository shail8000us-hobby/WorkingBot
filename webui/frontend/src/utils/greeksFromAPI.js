/**
 * Greeks Fetcher from Delta Exchange API
 * 
 * Fetches real-time Greeks from Delta Exchange ticker API instead of calculating.
 * Falls back to frontend Black-Scholes calculation if API fails.
 * 
 * Reference: https://docs.delta.exchange/reference/get-ticker-for-a-product-by-symbol
 */

import { API_BASE_URL } from './constants';

// Cache for Greeks data to avoid excessive API calls
const greeksCache = new Map();
const CACHE_TTL = 5000; // 5 seconds

/**
 * Fetch Greeks from Delta Exchange API for a single symbol
 * @param {string} symbol - Option symbol (e.g., "C-BTC-95000-310125")
 * @returns {Promise<Object|null>} - Greeks object or null if failed
 */
export async function getGreeksFromAPI(symbol) {
  if (!symbol) {
    console.warn('getGreeksFromAPI: No symbol provided');
    return null;
  }

  // Check cache first
  const cached = greeksCache.get(symbol);
  if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
    return cached.data;
  }

  try {
    // Fetch from our backend proxy (which calls Delta Exchange)
    const response = await fetch(`${API_BASE_URL}/api/ticker/${symbol}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`API request failed: ${response.status}`);
    }

    const data = await response.json();

    // Delta Exchange ticker response includes Greeks for options
    if (data.greeks) {
      const greeks = {
        delta: parseFloat(data.greeks.delta) || 0,
        gamma: parseFloat(data.greeks.gamma) || 0,
        theta: parseFloat(data.greeks.theta) || 0,
        vega: parseFloat(data.greeks.vega) || 0,
        rho: parseFloat(data.greeks.rho) || 0,
        timestamp: Date.now(),
      };

      // Cache the result
      greeksCache.set(symbol, { data: greeks, timestamp: Date.now() });

      return greeks;
    }

    console.warn(`getGreeksFromAPI: No Greeks data for ${symbol}`);
    return null;
  } catch (error) {
    console.error(`Failed to fetch Greeks from API for ${symbol}:`, error);
    return null;
  }
}

/**
 * Fetch Greeks for multiple symbols in parallel
 * @param {string[]} symbols - Array of option symbols
 * @returns {Promise<Object>} - Map of symbol -> Greeks
 */
export async function getBatchGreeksFromAPI(symbols) {
  if (!symbols || symbols.length === 0) {
    return {};
  }

  const promises = symbols.map(async (symbol) => {
    const greeks = await getGreeksFromAPI(symbol);
    return { symbol, greeks };
  });

  const results = await Promise.allSettled(promises);

  const greeksMap = {};
  results.forEach((result) => {
    if (result.status === 'fulfilled' && result.value.greeks) {
      greeksMap[result.value.symbol] = result.value.greeks;
    }
  });

  return greeksMap;
}

/**
 * Clear Greeks cache (useful for testing or manual refresh)
 */
export function clearGreeksCache() {
  greeksCache.clear();
}

/**
 * Get Greeks from API with fallback to Black-Scholes calculation
 * @param {string} symbol - Option symbol
 * @param {Object} optionParams - Parameters for fallback calculation
 *   @param {number} optionParams.spotPrice
 *   @param {number} optionParams.strike
 *   @param {number} optionParams.timeToExpiry - In years
 *   @param {number} optionParams.volatility - Implied volatility
 *   @param {string} optionParams.optionType - 'call' or 'put'
 * @param {Function} calculateGreeksFallback - Fallback function for Greeks calculation
 * @returns {Promise<Object>} - Greeks object (always returns something)
 */
export async function getGreeksWithFallback(symbol, optionParams, calculateGreeksFallback) {
  // Try API first
  const apiGreeks = await getGreeksFromAPI(symbol);
  
  if (apiGreeks) {
    return {
      ...apiGreeks,
      source: 'api',
    };
  }

  // Fallback to calculation
  if (calculateGreeksFallback && optionParams) {
    try {
      const calculatedGreeks = calculateGreeksFallback(optionParams);
      return {
        ...calculatedGreeks,
        source: 'calculated',
        timestamp: Date.now(),
      };
    } catch (error) {
      console.error('Fallback Greeks calculation failed:', error);
    }
  }

  // Return zeros as last resort
  return {
    delta: 0,
    gamma: 0,
    theta: 0,
    vega: 0,
    rho: 0,
    source: 'fallback',
    timestamp: Date.now(),
  };
}

export default {
  getGreeksFromAPI,
  getBatchGreeksFromAPI,
  getGreeksWithFallback,
  clearGreeksCache,
};
