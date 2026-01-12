import notificationService from '../monitoring/NotificationService';
import deltaExchangeAPI from '../api/DeltaExchangeAPI';
import riskValidator from './RiskValidator';
import { NOTIFICATION_TYPES, ACTION_TYPES, ORDER_TYPES, EXECUTION_TIMING } from '../types/constants';

/**
 * OrderExecutor - Order execution service (dry run and real orders)
 * 
 * Phase 2: Dry run only - logs orders to console
 * Phase 3: Real order execution via Delta Exchange API
 * 
 * Features:
 * - Order validation
 * - Dry run simulation
 * - Real order execution with risk checks
 * - Order tracking and lifecycle management
 * - PnL calculation
 */
class OrderExecutor {
  constructor() {
    this.orders = new Map(); // orderId -> order object
    this.positions = new Map(); // positionKey -> simulated/real position
    this.nextOrderId = 1;
  }

  /**
   * Set mode (dry run or live)
   * @param {boolean} isDryRun - True for dry run, false for live trading
   */
  setMode(isDryRun) {
    this.isDryRun = isDryRun;
    console.log(`[OrderExecutor] Mode set to: ${isDryRun ? 'DRY RUN' : 'LIVE TRADING'}`);
  }

  /**
   * Execute an entry order based on automation rules
   * @param {Object} automation - The automation configuration
   * @param {Object} position - The current option position
   * @param {Object} marketData - Current market data (spotPrice, etc.)
   * @returns {Promise<Object>} Order result
   */
  async executeEntry(automation, position, marketData) {
    try {
      const { entry, execution, risk } = automation.rules;
      const isDryRun = risk.alertOnlyMode;

      // Validate entry conditions
      if (!this._validateEntry(automation, position)) {
        throw new Error('Entry validation failed');
      }

      // Calculate order parameters
      const orderParams = this._calculateOrderParams(automation, position, marketData);

      // Perform risk validation for real orders
      if (!isDryRun) {
        let accountData = { availableBalance: 0 };
        try {
          accountData = await deltaExchangeAPI.getAccountBalance();
        } catch (balanceError) {
          console.warn('[OrderExecutor] Failed to get account balance:', balanceError);
          // Continue with empty account data - risk validator will handle appropriately
        }
        
        const validation = await riskValidator.validateOrder(orderParams, risk, accountData);
        
        if (!validation.isValid) {
          throw new Error(`Risk validation failed: ${validation.reason}`);
        }
      }

      // Handle staggered entry
      if (execution.staging.enabled) {
        return await this._executeStaggeredEntry(orderParams, execution.staging, isDryRun);
      }

      // Execute single order
      return await this._executeSingleOrder(orderParams, isDryRun);
    } catch (error) {
      console.error('[OrderExecutor] Entry execution failed:', error);
      notificationService.notify({
        type: NOTIFICATION_TYPES.ERROR,
        title: 'Order Failed',
        message: error.message,
        automation
      });
      throw error;
    }
  }

  /**
   * Execute an exit order for a position
   * @param {Object} automation - The automation configuration
   * @param {Object} position - The position to exit
   * @param {string} exitReason - Reason for exit (TP/SL/Trailing/Time/Manual)
   * @returns {Promise<Object>} Order result
   */
  async executeExit(automation, position, exitReason) {
    try {
      const orderParams = {
        orderId: this._generateOrderId(),
        symbol: position.symbol,
        action: position.size > 0 ? ACTION_TYPES.SELL : ACTION_TYPES.BUY,
        quantity: Math.abs(position.size),
        orderType: ORDER_TYPES.MARKET, // Always market for exits
        reason: exitReason,
        timestamp: Date.now()
      };

      const result = await this._executeSingleOrder(orderParams);

      // Calculate PnL
      const pnl = this._calculatePnL(position, result.executionPrice);
      result.pnl = pnl;

      notificationService.notify({
        type: pnl >= 0 ? NOTIFICATION_TYPES.SUCCESS : NOTIFICATION_TYPES.WARNING,
        title: `Position Closed: ${exitReason}`,
        message: `${position.symbol} closed at ${result.executionPrice.toFixed(4)} | PnL: ${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}%`,
        automation
      });

      return result;
    } catch (error) {
      console.error('[OrderExecutor] Exit execution failed:', error);
      throw error;
    }
  }

  /**
   * Calculate order parameters from automation rules
   */
  _calculateOrderParams(automation, position, marketData) {
    const { entry, execution } = automation.rules;
    const spotPrice = marketData.spotPrice || position.mark_price;

    // Determine quantity
    let quantity = execution.quantity || 1;
    if (execution.positionSizing === 'PERCENTAGE') {
      // Would calculate based on account balance in Phase 3
      quantity = Math.max(1, Math.floor(execution.capitalPercentage / 100 * 10)); // Placeholder
    } else if (execution.positionSizing === 'DYNAMIC') {
      // Adjust based on IV in Phase 3
      quantity = execution.minQuantity || 1;
    }

    // Determine order type and price
    let orderType = execution.orderType;
    let limitPrice = null;

    if (orderType === ORDER_TYPES.LIMIT) {
      const offset = execution.limitPriceOffset || 0;
      const direction = entry.action === ACTION_TYPES.BUY ? -1 : 1;
      limitPrice = spotPrice * (1 + (direction * offset / 100));
    }

    return {
      orderId: this._generateOrderId(),
      symbol: position.symbol,
      action: entry.action,
      quantity,
      orderType,
      limitPrice,
      timeout: execution.orderTimeout || 60,
      timestamp: Date.now()
    };
  }

  /**
   * Execute a single order
   * @param {Object} orderParams - Order parameters
   * @param {boolean} isDryRun - Dry run mode flag
   */
  async _executeSingleOrder(orderParams, isDryRun = true) {
    if (isDryRun) {
      return await this._executeDryRunOrder(orderParams);
    } else {
      return await this._executeRealOrder(orderParams);
    }
  }

  /**
   * Execute dry run (simulated) order
   */
  async _executeDryRunOrder(orderParams) {
    console.log('[OrderExecutor] DRY RUN - Simulating order:', orderParams);

    // Simulate network delay
    await this._simulateDelay(100, 500);

    // Simulate execution
    const executionPrice = orderParams.limitPrice || (Math.random() * 0.01 + 0.005); // Mock price
    const order = {
      ...orderParams,
      status: 'FILLED',
      executionPrice,
      executionTime: Date.now(),
      fees: executionPrice * orderParams.quantity * 0.0005, // 0.05% fee
      isDryRun: true
    };

    this.orders.set(order.orderId, order);

    // Update simulated position
    this._updateSimulatedPosition(order);

    console.log('[OrderExecutor] DRY RUN - Order filled:', {
      orderId: order.orderId,
      symbol: order.symbol,
      action: order.action,
      quantity: order.quantity,
      price: executionPrice.toFixed(4),
      fees: order.fees.toFixed(4)
    });

    return order;
  }

  /**
   * Execute real order via Delta Exchange API
   */
  async _executeRealOrder(orderParams) {
    console.log('[OrderExecutor] LIVE - Placing real order:', orderParams);

    try {
      const result = await deltaExchangeAPI.placeOrder({
        symbol: orderParams.symbol,
        side: orderParams.action, // 'buy' or 'sell'
        orderType: orderParams.orderType === ORDER_TYPES.MARKET ? 'market_order' : 'limit_order',
        quantity: orderParams.quantity,
        limitPrice: orderParams.limitPrice,
        timeInForce: 'gtc',
      });

      if (!result.success) {
        throw new Error(result.error || 'Order placement failed');
      }

      const order = {
        ...orderParams,
        orderId: result.orderId,
        status: result.status,
        executionPrice: result.fillPrice || orderParams.limitPrice,
        executionTime: result.timestamp,
        fees: result.fillPrice * orderParams.quantity * 0.0005, // Estimate 0.05% fee
        isDryRun: false,
        raw: result.raw,
      };

      this.orders.set(order.orderId, order);

      // Record order for risk tracking
      riskValidator.recordOrder(order);

      console.log('[OrderExecutor] LIVE - Order executed:', {
        orderId: order.orderId,
        symbol: order.symbol,
        action: order.action,
        quantity: order.quantity,
        price: order.executionPrice?.toFixed(4),
        status: order.status,
      });

      // Send success notification
      notificationService.notify({
        type: NOTIFICATION_TYPES.SUCCESS,
        title: 'Order Filled',
        message: `${order.action.toUpperCase()} ${order.quantity} ${order.symbol} @ ${order.executionPrice?.toFixed(4)}`,
      });

      return order;
    } catch (error) {
      console.error('[OrderExecutor] LIVE - Order failed:', error);
      
      notificationService.notify({
        type: NOTIFICATION_TYPES.ERROR,
        title: 'Order Failed',
        message: error.message,
      });

      throw error;
    }
  }

  /**
   * Execute staggered entry (multiple orders)
   */
  async _executeStaggeredEntry(orderParams, staging, isDryRun = true) {
    const results = [];
    const quantityPerStage = Math.ceil(orderParams.quantity / staging.stages);

    console.log(`[OrderExecutor] ${isDryRun ? 'DRY RUN' : 'LIVE'} - Executing ${staging.stages} staged orders`);

    for (let i = 0; i < staging.stages; i++) {
      const stageParams = {
        ...orderParams,
        orderId: this._generateOrderId(),
        quantity: Math.min(quantityPerStage, orderParams.quantity - (i * quantityPerStage)),
        stage: i + 1,
        totalStages: staging.stages
      };

      const result = await this._executeSingleOrder(stageParams, isDryRun);
      results.push(result);

      // Wait between stages (except last)
      if (i < staging.stages - 1) {
        console.log(`[OrderExecutor] Waiting ${staging.intervalSeconds}s before next stage...`);
        await this._simulateDelay(staging.intervalSeconds * 1000);
      }
    }

    return {
      type: 'STAGED_ORDER',
      stages: results,
      totalQuantity: results.reduce((sum, r) => sum + r.quantity, 0),
      avgPrice: results.reduce((sum, r) => sum + r.executionPrice * r.quantity, 0) / 
                results.reduce((sum, r) => sum + r.quantity, 0)
    };
  }

  /**
   * Update simulated position tracking
   */
  _updateSimulatedPosition(order) {
    const key = order.symbol;
    let position = this.positions.get(key);

    if (!position) {
      position = {
        symbol: order.symbol,
        size: 0,
        avgEntryPrice: 0,
        realizedPnL: 0,
        trades: []
      };
    }

    const oldSize = position.size;
    const newSize = order.action === ACTION_TYPES.BUY ? 
      oldSize + order.quantity : 
      oldSize - order.quantity;

    // Update average entry price
    if (Math.sign(newSize) === Math.sign(oldSize) || oldSize === 0) {
      // Adding to position
      position.avgEntryPrice = 
        (position.avgEntryPrice * Math.abs(oldSize) + order.executionPrice * order.quantity) /
        (Math.abs(oldSize) + order.quantity);
    } else {
      // Reducing position - realize PnL
      const closedQuantity = Math.min(order.quantity, Math.abs(oldSize));
      const pnl = (order.executionPrice - position.avgEntryPrice) * closedQuantity *
        (oldSize > 0 ? 1 : -1);
      position.realizedPnL += pnl;
    }

    position.size = newSize;
    position.trades.push({
      orderId: order.orderId,
      action: order.action,
      quantity: order.quantity,
      price: order.executionPrice,
      timestamp: order.executionTime
    });

    this.positions.set(key, position);
  }

  /**
   * Calculate PnL for a position
   */
  _calculatePnL(position, exitPrice) {
    const entryPrice = position.mark_price; // Use current mark as mock entry
    const priceChange = ((exitPrice - entryPrice) / entryPrice) * 100;
    
    // BUY position (size > 0): profit when price rises
    // SELL position (size < 0): profit when price falls (inverse)
    return position.size > 0 ? priceChange : -priceChange;
  }

  /**
   * Validate entry conditions before order
   */
  _validateEntry(automation, position) {
    // Check if position exists
    if (!position) {
      console.error('[OrderExecutor] Position not found');
      return false;
    }

    // Check if automation is active
    if (automation.status !== 'ACTIVE') {
      console.error('[OrderExecutor] Automation not active');
      return false;
    }

    // Additional validation in Phase 3:
    // - Account balance check
    // - Risk limit checks
    // - Position limit checks
    // - Market hours check

    return true;
  }

  /**
   * Simulate network delay
   */
  _simulateDelay(minMs = 100, maxMs = 500) {
    const delay = Math.random() * (maxMs - minMs) + minMs;
    return new Promise(resolve => setTimeout(resolve, delay));
  }

  /**
   * Generate unique order ID
   */
  _generateOrderId() {
    return `DRY_${Date.now()}_${this.nextOrderId++}`;
  }

  /**
   * Get order by ID
   */
  getOrder(orderId) {
    return this.orders.get(orderId);
  }

  /**
   * Get all orders for a symbol
   */
  getOrdersBySymbol(symbol) {
    return Array.from(this.orders.values())
      .filter(order => order.symbol === symbol);
  }

  /**
   * Get simulated position
   */
  getPosition(symbol) {
    return this.positions.get(symbol);
  }

  /**
   * Get all simulated positions
   */
  getAllPositions() {
    return Array.from(this.positions.values());
  }

  /**
   * Clear all simulated data (useful for testing)
   */
  clear() {
    this.orders.clear();
    this.positions.clear();
    this.nextOrderId = 1;
    console.log('[OrderExecutor] Cleared all simulated data');
  }

  /**
   * Get execution statistics
   */
  getStats() {
    const orders = Array.from(this.orders.values());
    return {
      totalOrders: orders.length,
      filledOrders: orders.filter(o => o.status === 'FILLED').length,
      totalFees: orders.reduce((sum, o) => sum + (o.fees || 0), 0),
      totalVolume: orders.reduce((sum, o) => sum + (o.executionPrice * o.quantity), 0)
    };
  }
}

// Singleton instance
const orderExecutor = new OrderExecutor();

export default orderExecutor;
export { OrderExecutor };
