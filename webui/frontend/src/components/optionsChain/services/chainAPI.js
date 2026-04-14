/**
 * Options Chain API Service
 * ==========================
 * Isolated API client for options chain data.
 * Does NOT share state with options trading module.
 *
 * Created: January 5, 2026
 */

const API_BASE = '/api/options-chain';

/**
 * Options Chain API client
 */
class OptionsChainAPI {
  constructor() {
    this.expirationCache = new Map();
    this.chainCache = new Map();
    this.expirationTtlMs = 60 * 1000;
    this.chainTtlMs = 20 * 1000;
  }

  getCached(cache, key, ttlMs) {
    const cached = cache.get(key);
    if (!cached) return null;

    if ((Date.now() - cached.ts) > ttlMs) {
      cache.delete(key);
      return null;
    }

    return cached.value;
  }

  setCached(cache, key, value) {
    cache.set(key, {
      ts: Date.now(),
      value,
    });
  }

  /**
   * Preload lightweight Options Chain data ahead of first navigation.
   * Keeps first open of the Options Chain tab snappy.
   */
  async warmup(underlying = 'BTC') {
    await this.getExpirations(underlying);
  }

  /**
   * Get available expiry dates for underlying
   * @param {string} underlying - BTC or ETH
   * @returns {Promise<string[]>} Array of expiry dates (DDMMYYYY format)
   */
  async getExpirations(underlying = 'BTC') {
    const cacheKey = String(underlying || 'BTC').toUpperCase();
    const cached = this.getCached(this.expirationCache, cacheKey, this.expirationTtlMs);
    if (cached) {
      return cached;
    }

    try {
      const response = await fetch(`${API_BASE}/expirations?underlying=${underlying}`);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      const expirations = data.expirations || [];
      this.setCached(this.expirationCache, cacheKey, expirations);
      return expirations;
    } catch (error) {
      console.error('[OptionsChainAPI] getExpirations error:', error);
      throw error;
    }
  }

  /**
   * Get full options chain data for underlying and expiry
   * @param {string} underlying - BTC or ETH
   * @param {string} expiry - Expiry date in DDMMYYYY format
   * @returns {Promise<Object>} Chain data with spot, ATM, and all strikes
   */
  async getChainData(underlying = 'BTC', expiry) {
    const cacheKey = `${String(underlying || 'BTC').toUpperCase()}:${expiry}`;
    const cached = this.getCached(this.chainCache, cacheKey, this.chainTtlMs);
    if (cached) {
      return cached;
    }

    try {
      if (!expiry) {
        throw new Error('Expiry date is required');
      }

      const response = await fetch(`${API_BASE}/data?underlying=${underlying}&expiry=${expiry}`);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      this.setCached(this.chainCache, cacheKey, data);
      return data;
    } catch (error) {
      console.error('[OptionsChainAPI] getChainData error:', error);
      throw error;
    }
  }

  /**
   * Force refresh chain data (invalidate cache)
   * @param {string} underlying - BTC or ETH
   * @param {string} expiry - Optional expiry date
   */
  async refresh(underlying = 'BTC', expiry = null) {
    try {
      let url = `${API_BASE}/refresh?underlying=${underlying}`;
      if (expiry) {
        url += `&expiry=${expiry}`;
      }

      const response = await fetch(url, { method: 'POST' });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const normalizedUnderlying = String(underlying || 'BTC').toUpperCase();
      this.expirationCache.delete(normalizedUnderlying);
      if (expiry) {
        this.chainCache.delete(`${normalizedUnderlying}:${expiry}`);
      } else {
        [...this.chainCache.keys()]
          .filter((k) => k.startsWith(`${normalizedUnderlying}:`))
          .forEach((k) => this.chainCache.delete(k));
      }

      return await response.json();
    } catch (error) {
      console.error('[OptionsChainAPI] refresh error:', error);
      throw error;
    }
  }

  /**
   * Health check
   * @returns {Promise<boolean>}
   */
  async healthCheck() {
    try {
      const response = await fetch(`${API_BASE}/health`);
      const data = await response.json();
      return data.status === 'ok';
    } catch {
      return false;
    }
  }

  /**
   * Place an order from the options chain
   * @param {Object} order - Order details
   * @param {string} order.symbol - Option symbol (e.g., C-BTC-95000-060126)
   * @param {string} order.side - 'buy' or 'sell'
   * @param {number} order.size - Number of contracts
   * @param {string} order.order_type - 'market' or 'limit'
   * @param {number} order.limit_price - Price for limit orders
   * @returns {Promise<Object>} Order result
   */
  async placeOrder({ symbol, side, size, order_type = 'market', limit_price = null }) {
    try {
      const body = {
        symbol,
        side,
        size: parseInt(size),
        order_type,
      };

      if (order_type === 'limit' && limit_price) {
        body.limit_price = parseFloat(limit_price);
      }

      const response = await fetch(`${API_BASE}/order`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || `HTTP ${response.status}`);
      }

      return data;
    } catch (error) {
      console.error('[OptionsChainAPI] placeOrder error:', error);
      throw error;
    }
  }

  /**
   * Cancel an open order
   * @param {string} orderId - Order ID to cancel
   * @returns {Promise<Object>} Cancellation result
   */
  async cancelOrder(orderId) {
    try {
      const response = await fetch(`${API_BASE}/order/${orderId}`, {
        method: 'DELETE',
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || `HTTP ${response.status}`);
      }

      return data;
    } catch (error) {
      console.error('[OptionsChainAPI] cancelOrder error:', error);
      throw error;
    }
  }

  /**
   * Get all open orders
   * @returns {Promise<Object>} Open orders list
   */
  async getOpenOrders() {
    try {
      const response = await fetch(`${API_BASE}/orders`);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error('[OptionsChainAPI] getOpenOrders error:', error);
      throw error;
    }
  }

  /**
   * Get ticker for specific option
   * @param {string} symbol - Option symbol
   * @returns {Promise<Object>} Ticker data
   */
  async getTicker(symbol) {
    try {
      const response = await fetch(`${API_BASE}/ticker/${encodeURIComponent(symbol)}`);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      return data.ticker;
    } catch (error) {
      console.error('[OptionsChainAPI] getTicker error:', error);
      throw error;
    }
  }

  /**
   * Get open options positions as a symbol lookup map
   * Returns: { [symbol]: { side: 'long'|'short', size, pnl } }
   *
   * @sealed v1.0.0 — Mar 5, 2026
   * CONTRACT:
   *   1. Always returns {} on any error — NEVER throws.
   *   2. Only includes options: C-/P- prefix OR product_type=call_options/put_options OR type=option.
   *   3. Map keys are always UPPERCASE.
   *   4. `side` is always lowercase ('long' or 'short').
   *   5. Long position (bought) → side='long' → green highlight in ChainTable.
   *   6. Short position (sold) → side='short' → red highlight in ChainTable.
   *   7. Symbol absent from map → no highlight (not in active trading).
   * DO NOT CHANGE without UNSEAL: getOpenPositions in AI_SEAL.md
   */
  // 🔒 SEALED #44 — test: test_sealed_getOpenPositions.test.js
  async getOpenPositions() {
    try {
      // Pass symbol= (empty) to bypass the default BTCUSD filter and get ALL positions
      // including options (C-BTC-... / P-BTC-... symbols)
      const response = await fetch('/api/positions?symbol=');
      if (!response.ok) return {};
      const data = await response.json();
      const positions = data.positions || [];

      console.log('[OpenPositions] Raw positions from API:', positions.length, positions);

      // Build lookup map: symbol -> position info (options only: C-/P- prefix or type='option')
      const map = {};
      for (const pos of positions) {
        if (!pos.symbol) continue;
        const sym = pos.symbol.toUpperCase();
        // Delta Exchange options symbols start with C- (call) or P- (put)
        const isOption =
          sym.startsWith('C-') ||
          sym.startsWith('P-') ||
          (pos.product_type || '').toLowerCase() === 'put_options' ||
          (pos.product_type || '').toLowerCase() === 'call_options' ||
          (pos.type || '').toLowerCase() === 'option';
        if (!isOption) continue;
        map[sym] = {
          side: (pos.side || '').toLowerCase(), // 'long' or 'short'
          size: pos.size,
          pnl: pos.unrealized_pnl,
        };
      }

      console.log('[OpenPositions] Options map keys:', Object.keys(map));
      return map;
    } catch (e) {
      console.warn('[OptionsChainAPI] getOpenPositions error:', e);
      return {};
    }
  }

  /**
   * Place an SSR (Stealth Sniper Repricing) order
   * @param {Object} order - SSR order details
   * @param {string} order.symbol - Option symbol (e.g., C-BTC-95000-060126)
   * @param {string} order.side - 'buy' or 'sell'
   * @param {number} order.quantity - Number of contracts
   * @param {string} order.ssrMode - 'standard', 'aggressive', or 'conservative'
   * @returns {Promise<Object>} Order result with SSR tracking info
   */
  async placeSSROrder({ symbol, side, quantity, ssrMode = 'standard' }) {
    try {
      const body = {
        symbol,
        side,
        quantity: parseInt(quantity),
        ssrMode,
      };

      console.log(`[OptionsChainAPI] Placing SSR order:`, body);

      // Route to the options SSR endpoint
      const response = await fetch('/api/options/ssr-order', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || `HTTP ${response.status}`);
      }

      return data;
    } catch (error) {
      console.error('[OptionsChainAPI] placeSSROrder error:', error);
      throw error;
    }
  }
}

// Export singleton instance
export const optionsChainAPI = new OptionsChainAPI();
export default optionsChainAPI;
