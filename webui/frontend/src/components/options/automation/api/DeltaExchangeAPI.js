/**
 * DeltaExchangeAPI - Real order execution service
 *
 * Phase 3: Integrates with Delta Exchange API to place real orders
 *
 * Features:
 * - Place market/limit orders
 * - Cancel orders
 * - Get order status
 * - Get account balance
 * - Position management
 * - Error handling and retries
 */

import axios from 'axios';

class DeltaExchangeAPI {
  constructor() {
    this.baseURL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:5000';
    this.apiKey = null;
    this.apiSecret = null;
    this.isInitialized = false;

    // Auto-initialize from environment or localStorage
    this._autoInitialize();
  }

  /**
   * Auto-initialize from available sources
   * Priority: 1. Environment vars, 2. localStorage, 3. Backend will use its own keys
   */
  _autoInitialize() {
    // Try environment variables first
    const envApiKey = process.env.REACT_APP_DELTA_API_KEY;
    const envApiSecret = process.env.REACT_APP_DELTA_API_SECRET;

    if (envApiKey && envApiSecret) {
      this.initialize(envApiKey, envApiSecret);
      return;
    }

    // Try localStorage (saved from settings)
    try {
      const savedKey = localStorage.getItem('delta_api_key');
      const savedSecret = localStorage.getItem('delta_api_secret');
      if (savedKey && savedSecret) {
        this.initialize(savedKey, savedSecret);
        return;
      }
    } catch (e) {
      // localStorage not available
    }

    // Backend-proxy mode: no client-side keys needed
    // Backend will use its own credentials
    this.isInitialized = true;
    this.useBackendProxy = true;
    console.log('[DeltaExchangeAPI] Using backend proxy mode (no client-side keys)');
  }

  /**
   * Initialize API with credentials
   * @param {string} apiKey - Delta Exchange API key
   * @param {string} apiSecret - Delta Exchange API secret
   */
  initialize(apiKey, apiSecret) {
    this.apiKey = apiKey;
    this.apiSecret = apiSecret;
    this.isInitialized = true;
    this.useBackendProxy = false;
    console.log('[DeltaExchangeAPI] Initialized with credentials');
  }

  /**
   * Check if API is initialized (now always returns - backend proxy is fallback)
   */
  checkInitialized() {
    // With backend proxy mode, we're always "initialized"
    // The backend handles authentication
    if (!this.isInitialized) {
      console.warn('[DeltaExchangeAPI] Not explicitly initialized, using backend proxy mode');
      this.isInitialized = true;
      this.useBackendProxy = true;
    }
  }

  /**
   * Place an order via backend proxy
   * @param {Object} orderParams - Order parameters
   * @returns {Promise<Object>} Order result
   */
  async placeOrder(orderParams) {
    this.checkInitialized();

    try {
      console.log('[DeltaExchangeAPI] Placing order:', orderParams);

      const response = await axios.post(
        `${this.baseURL}/api/orders`,
        {
          symbol: orderParams.symbol,
          side: orderParams.side, // 'buy' or 'sell'
          order_type: orderParams.orderType, // 'market_order' or 'limit_order'
          size: orderParams.quantity,
          limit_price: orderParams.limitPrice,
          time_in_force: orderParams.timeInForce || 'gtc',
          // MAKER-ONLY: For limit orders, default to post_only=true to ensure order adds liquidity
          post_only: orderParams.postOnly !== undefined ? orderParams.postOnly : (orderParams.orderType === 'limit_order'),
        },
        {
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${this.apiKey}`,
          },
          timeout: 10000, // 10 second timeout
        }
      );

      if (response.data && response.data.success) {
        console.log('[DeltaExchangeAPI] Order placed successfully:', response.data.result);
        return {
          success: true,
          orderId: response.data.result.id,
          status: response.data.result.state,
          fillPrice: response.data.result.average_fill_price,
          filledQuantity: response.data.result.filled_size,
          timestamp: Date.now(),
          raw: response.data.result,
        };
      } else {
        throw new Error(response.data?.error || 'Order placement failed');
      }
    } catch (error) {
      console.error('[DeltaExchangeAPI] Order placement error:', error);

      return {
        success: false,
        error: error.response?.data?.error || error.message,
        code: error.response?.status,
        timestamp: Date.now(),
      };
    }
  }

  /**
   * Cancel an order
   * @param {string} orderId - Order ID to cancel
   * @param {string} symbol - Product symbol
   * @returns {Promise<Object>} Cancel result
   */
  async cancelOrder(orderId, symbol) {
    this.checkInitialized();

    try {
      console.log('[DeltaExchangeAPI] Cancelling order:', orderId);

      const response = await axios.delete(`${this.baseURL}/api/orders/${orderId}`, {
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
        },
        params: {
          product_id: symbol,
        },
        timeout: 10000,
      });

      if (response.data && response.data.success) {
        console.log('[DeltaExchangeAPI] Order cancelled successfully');
        return {
          success: true,
          orderId,
          timestamp: Date.now(),
        };
      } else {
        throw new Error(response.data?.error || 'Order cancellation failed');
      }
    } catch (error) {
      console.error('[DeltaExchangeAPI] Order cancellation error:', error);

      return {
        success: false,
        error: error.response?.data?.error || error.message,
        timestamp: Date.now(),
      };
    }
  }

  /**
   * Get order status
   * @param {string} orderId - Order ID
   * @returns {Promise<Object>} Order status
   */
  async getOrderStatus(orderId) {
    this.checkInitialized();

    try {
      const response = await axios.get(`${this.baseURL}/api/orders/${orderId}`, {
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
        },
        timeout: 5000,
      });

      if (response.data && response.data.success) {
        const order = response.data.result;
        return {
          success: true,
          orderId: order.id,
          status: order.state,
          fillPrice: order.average_fill_price,
          filledQuantity: order.filled_size,
          remainingQuantity: order.unfilled_size,
          timestamp: Date.now(),
        };
      } else {
        throw new Error('Failed to get order status');
      }
    } catch (error) {
      console.error('[DeltaExchangeAPI] Get order status error:', error);
      return {
        success: false,
        error: error.message,
      };
    }
  }

  /**
   * Get account balance
   * @returns {Promise<Object>} Account balance
   */
  async getAccountBalance() {
    this.checkInitialized();

    try {
      const response = await axios.get(`${this.baseURL}/api/wallet/balances`, {
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
        },
        timeout: 5000,
      });

      if (response.data && response.data.success) {
        const balances = response.data.result;

        // Find BTC balance (Delta Exchange uses BTC as margin)
        const btcBalance = balances.find((b) => b.asset_symbol === 'BTC');

        return {
          success: true,
          availableBalance: btcBalance?.available_balance || 0,
          marginBalance: btcBalance?.balance || 0,
          currency: 'BTC',
          timestamp: Date.now(),
        };
      } else {
        throw new Error('Failed to get account balance');
      }
    } catch (error) {
      console.error('[DeltaExchangeAPI] Get balance error:', error);
      return {
        success: false,
        error: error.message,
        availableBalance: 0,
      };
    }
  }

  /**
   * Get current positions
   * @returns {Promise<Array>} Array of positions
   */
  async getPositions() {
    this.checkInitialized();

    try {
      const response = await axios.get(`${this.baseURL}/api/positions`, {
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
        },
        timeout: 5000,
      });

      if (response.data && response.data.success) {
        return {
          success: true,
          positions: response.data.result || [],
          timestamp: Date.now(),
        };
      } else {
        throw new Error('Failed to get positions');
      }
    } catch (error) {
      console.error('[DeltaExchangeAPI] Get positions error:', error);
      return {
        success: false,
        error: error.message,
        positions: [],
      };
    }
  }

  /**
   * Close a position (market order opposite direction)
   * @param {string} symbol - Product symbol
   * @param {number} size - Position size to close
   * @param {string} side - Position side ('buy' or 'sell')
   * @returns {Promise<Object>} Close order result
   */
  async closePosition(symbol, size, side) {
    // Reverse the side to close
    const closeSide = side === 'buy' ? 'sell' : 'buy';

    return await this.placeOrder({
      symbol,
      side: closeSide,
      orderType: 'market_order',
      quantity: Math.abs(size),
    });
  }

  /**
   * Batch close multiple positions
   * @param {Array} positions - Array of position objects
   * @returns {Promise<Array>} Array of close results
   */
  async closeAllPositions(positions) {
    const results = [];

    for (const position of positions) {
      try {
        const result = await this.closePosition(
          position.product_symbol,
          position.size,
          position.size > 0 ? 'buy' : 'sell'
        );
        results.push({ position: position.product_symbol, ...result });

        // Small delay between closes to avoid rate limits
        await new Promise((resolve) => setTimeout(resolve, 200));
      } catch (error) {
        results.push({
          position: position.product_symbol,
          success: false,
          error: error.message,
        });
      }
    }

    return results;
  }

  /**
   * Get product specifications
   * @param {string} symbol - Product symbol
   * @returns {Promise<Object>} Product specs
   */
  async getProductSpecs(symbol) {
    try {
      const response = await axios.get(`${this.baseURL}/api/products`, {
        timeout: 5000,
      });

      if (response.data && response.data.success) {
        const products = response.data.result;
        const product = products.find((p) => p.symbol === symbol);

        if (product) {
          return {
            success: true,
            symbol: product.symbol,
            contractValue: product.contract_value,
            tickSize: product.tick_size,
            minSize: product.min_size,
            maxSize: product.max_size,
            settlementTime: product.settlement_time,
          };
        }
      }

      throw new Error(`Product ${symbol} not found`);
    } catch (error) {
      console.error('[DeltaExchangeAPI] Get product specs error:', error);
      return {
        success: false,
        error: error.message,
      };
    }
  }

  /**
   * Health check - verify API connection
   * @returns {Promise<boolean>} True if connection is healthy
   */
  async healthCheck() {
    try {
      const response = await axios.get(`${this.baseURL}/api/products`, { timeout: 5000 });

      return response.status === 200;
    } catch (error) {
      console.error('[DeltaExchangeAPI] Health check failed:', error);
      return false;
    }
  }
}

// Singleton instance
const deltaExchangeAPI = new DeltaExchangeAPI();

export default deltaExchangeAPI;
export { DeltaExchangeAPI };
