/**
 * RiskValidator - Pre-trade risk checks
 * 
 * Phase 3: Validates orders against risk limits before execution
 * 
 * Features:
 * - Position size validation
 * - Daily loss limit checks
 * - Portfolio exposure checks
 * - Trading hours validation
 * - Order rate limiting
 * - Balance sufficiency checks
 */

import deltaExchangeAPI from '../api/DeltaExchangeAPI';

class RiskValidator {
  constructor() {
    this.dailyStats = {
      trades: 0,
      pnl: 0,
      orders: 0,
      lastReset: this._getTodayStart(),
    };
    this.orderHistory = []; // Track recent orders for rate limiting
    this.activeAutomations = new Set();
  }

  /**
   * Validate order before execution
   * @param {Object} orderParams - Order parameters
   * @param {Object} riskRules - Risk control rules
   * @param {Object} accountData - Current account data
   * @returns {Object} { isValid: boolean, reason: string, violations: array }
   */
  async validateOrder(orderParams, riskRules, accountData) {
    const violations = [];

    // Reset daily stats if new day
    this._checkDailyReset();

    // 1. Check if live trading is enabled
    if (riskRules.alertOnlyMode) {
      return {
        isValid: false,
        reason: 'Alert-only mode enabled. Disable to place real orders.',
        violations: ['ALERT_ONLY_MODE'],
      };
    }

    // 2. Check position size limits
    if (orderParams.quantity > riskRules.maxPositionSize) {
      violations.push({
        type: 'MAX_POSITION_SIZE',
        message: `Order size ${orderParams.quantity} exceeds max ${riskRules.maxPositionSize}`,
      });
    }

    // 3. Check max open positions
    if (this.activeAutomations.size >= (riskRules.maxOpenPositions || 5)) {
      violations.push({
        type: 'MAX_OPEN_POSITIONS',
        message: `Already at max open positions: ${riskRules.maxOpenPositions}`,
      });
    }

    // 4. Check daily loss limit
    if (riskRules.dailyLossLimit && this.dailyStats.pnl < -riskRules.dailyLossLimit) {
      violations.push({
        type: 'DAILY_LOSS_LIMIT',
        message: `Daily loss limit exceeded: ₹${Math.abs(this.dailyStats.pnl).toFixed(2)} / ₹${riskRules.dailyLossLimit}`,
      });
    }

    // 5. Check trading hours
    if (riskRules.tradingHoursRestriction?.enabled) {
      const inTradingHours = this._checkTradingHours(riskRules.tradingHoursRestriction);
      if (!inTradingHours) {
        violations.push({
          type: 'TRADING_HOURS',
          message: `Outside trading hours: ${riskRules.tradingHoursRestriction.startTime} - ${riskRules.tradingHoursRestriction.endTime}`,
        });
      }
    }

    // 6. Check order rate limiting
    const rateLimitOk = this._checkRateLimit(riskRules.maxOrdersPerMinute || 10);
    if (!rateLimitOk) {
      violations.push({
        type: 'RATE_LIMIT',
        message: `Order rate limit exceeded: ${riskRules.maxOrdersPerMinute} orders/minute`,
      });
    }

    // 7. Check account balance (if accountData provided)
    if (accountData && accountData.availableBalance !== undefined) {
      const estimatedMargin = this._estimateRequiredMargin(orderParams);
      if (estimatedMargin > accountData.availableBalance) {
        violations.push({
          type: 'INSUFFICIENT_BALANCE',
          message: `Insufficient balance: Required ${estimatedMargin.toFixed(4)} BTC, Available ${accountData.availableBalance.toFixed(4)} BTC`,
        });
      }
    }

    // 8. Check portfolio exposure
    if (accountData && riskRules.portfolioExposure) {
      const currentExposure = this._calculateCurrentExposure(accountData);
      if (currentExposure >= riskRules.portfolioExposure) {
        violations.push({
          type: 'PORTFOLIO_EXPOSURE',
          message: `Portfolio exposure limit reached: ${currentExposure.toFixed(1)}% / ${riskRules.portfolioExposure}%`,
        });
      }
    }

    // Compile result
    const isValid = violations.length === 0;
    const reason = isValid 
      ? 'All risk checks passed' 
      : violations.map(v => v.message).join('; ');

    return {
      isValid,
      reason,
      violations,
    };
  }

  /**
   * Record order execution
   * @param {Object} order - Executed order details
   */
  recordOrder(order) {
    this.dailyStats.orders++;
    this.orderHistory.push({
      orderId: order.orderId,
      timestamp: Date.now(),
    });

    // Keep only last hour of orders for rate limiting
    const oneHourAgo = Date.now() - 60 * 60 * 1000;
    this.orderHistory = this.orderHistory.filter(o => o.timestamp > oneHourAgo);

    console.log('[RiskValidator] Order recorded. Daily stats:', this.dailyStats);
  }

  /**
   * Record trade P&L
   * @param {number} pnl - Profit/loss amount
   */
  recordTrade(pnl) {
    this.dailyStats.trades++;
    this.dailyStats.pnl += pnl;

    console.log('[RiskValidator] Trade recorded. Daily P&L:', this.dailyStats.pnl.toFixed(2));
  }

  /**
   * Register active automation
   * @param {string} automationId - Automation ID
   */
  registerAutomation(automationId) {
    this.activeAutomations.add(automationId);
  }

  /**
   * Unregister automation
   * @param {string} automationId - Automation ID
   */
  unregisterAutomation(automationId) {
    this.activeAutomations.delete(automationId);
  }

  /**
   * Get daily statistics
   */
  getDailyStats() {
    this._checkDailyReset();
    return { ...this.dailyStats };
  }

  /**
   * Reset daily statistics manually
   */
  resetDailyStats() {
    this.dailyStats = {
      trades: 0,
      pnl: 0,
      orders: 0,
      lastReset: Date.now(),
    };
    console.log('[RiskValidator] Daily stats reset');
  }

  /**
   * Check and reset daily stats if new day
   */
  _checkDailyReset() {
    const todayStart = this._getTodayStart();
    if (this.dailyStats.lastReset < todayStart) {
      this.resetDailyStats();
    }
  }

  /**
   * Get today's start timestamp
   */
  _getTodayStart() {
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    return now.getTime();
  }

  /**
   * Check if current time is within trading hours
   */
  _checkTradingHours(restriction) {
    const now = new Date();
    const currentTime = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
    
    const toMinutes = (timeStr) => {
      const [hours, minutes] = timeStr.split(':').map(Number);
      return hours * 60 + minutes;
    };
    
    const current = toMinutes(currentTime);
    const start = toMinutes(restriction.startTime);
    const end = toMinutes(restriction.endTime);
    
    // Handle overnight windows
    if (end < start) {
      return current >= start || current <= end;
    }
    
    return current >= start && current <= end;
  }

  /**
   * Check order rate limit
   */
  _checkRateLimit(maxOrdersPerMinute) {
    const oneMinuteAgo = Date.now() - 60 * 1000;
    const recentOrders = this.orderHistory.filter(o => o.timestamp > oneMinuteAgo);
    
    return recentOrders.length < maxOrdersPerMinute;
  }

  /**
   * Estimate required margin for order
   * @param {Object} orderParams - Order parameters
   * @returns {number} Estimated margin in BTC
   */
  _estimateRequiredMargin(orderParams) {
    // Simplified estimation: 
    // For options, margin = quantity * contract_value * mark_price * leverage_factor
    // Delta Exchange contract_value = 0.001 BTC
    // Assume average option price of 0.005 BTC
    // Leverage factor ~10x, so margin ~10% of notional
    
    const contractValue = 0.001; // BTC per contract
    const estimatedPrice = orderParams.limitPrice || 0.005; // Default to 0.005 if market order
    const leverageFactor = 0.1; // 10x leverage = 10% margin
    
    return orderParams.quantity * contractValue * estimatedPrice * leverageFactor;
  }

  /**
   * Calculate current portfolio exposure
   * @param {Object} accountData - Account data with positions
   * @returns {number} Exposure percentage
   */
  _calculateCurrentExposure(accountData) {
    // Simplified: exposure = (used_margin / total_balance) * 100
    // In real implementation, would calculate actual position values
    
    if (!accountData.marginBalance || accountData.marginBalance === 0) {
      return 0;
    }
    
    const usedMargin = accountData.marginBalance - accountData.availableBalance;
    return (usedMargin / accountData.marginBalance) * 100;
  }

  /**
   * Get current risk metrics
   */
  async getRiskMetrics() {
    const accountBalance = await deltaExchangeAPI.getAccountBalance();
    
    return {
      dailyStats: this.getDailyStats(),
      activeAutomations: this.activeAutomations.size,
      accountBalance: accountBalance.availableBalance || 0,
      recentOrdersCount: this.orderHistory.filter(o => o.timestamp > Date.now() - 60000).length,
    };
  }
}

// Singleton instance
const riskValidator = new RiskValidator();

export default riskValidator;
export { RiskValidator };
