/**
 * AutomationMonitor - Background polling service
 *
 * Features:
 * - Polls market data every X seconds
 * - Checks all active automation rules
 * - Triggers notifications when conditions are met
 * - Executes orders when conditions are met (Phase 2+)
 */

import conditionEvaluator from '../core/ConditionEvaluator';
import notificationService from './NotificationService';
import automationStorage from '../storage/AutomationStorage';
import orderExecutor from '../core/OrderExecutor';
import { AUTOMATION_STATUS, NOTIFICATION_TYPES, POLLING_INTERVALS } from '../types/constants';

class AutomationMonitor {
  constructor() {
    this.pollingInterval = POLLING_INTERVALS.NORMAL; // 5 seconds default
    this.intervalId = null;
    this.isRunning = false;
    this.isChecking = false; // Prevent overlapping checks
    this.activeAutomations = new Map(); // automationId -> automation data
    this.marketDataProvider = null; // Will be set by UI component
  }

  /**
   * Set market data provider (function that returns current market data)
   * @param {Function} provider - Function that returns {positions, spotPrices}
   */
  setMarketDataProvider(provider) {
    this.marketDataProvider = provider;
  }

  /**
   * Start monitoring
   */
  start() {
    if (this.isRunning) {
      console.warn('AutomationMonitor already running');
      return;
    }

    console.log('AutomationMonitor starting...');
    this.isRunning = true;
    this._loadActiveAutomations();
    this._startPolling();
  }

  /**
   * Stop monitoring
   */
  stop() {
    if (!this.isRunning) return;

    console.log('AutomationMonitor stopping...');
    this.isRunning = false;
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }

  /**
   * Register a new automation
   * @param {string} automationId - Unique ID
   * @param {Object} automation - Automation data
   */
  register(automationId, automation) {
    this.activeAutomations.set(automationId, {
      ...automation,
      status: AUTOMATION_STATUS.WAITING,
      lastChecked: null,
      triggeredCount: 0,
    });

    // Save to storage
    automationStorage.updateStatus(automationId, AUTOMATION_STATUS.WAITING);

    console.log(`Registered automation: ${automationId}`);

    // Start monitoring if not already running
    if (!this.isRunning) {
      this.start();
    }
  }

  /**
   * Unregister automation
   * @param {string} automationId - Unique ID
   */
  unregister(automationId) {
    this.activeAutomations.delete(automationId);
    automationStorage.updateStatus(automationId, AUTOMATION_STATUS.INACTIVE);
    console.log(`Unregistered automation: ${automationId}`);

    // Stop monitoring if no active automations
    if (this.activeAutomations.size === 0) {
      this.stop();
    }
  }

  /**
   * Set polling interval
   * @param {number} intervalMs - Interval in milliseconds
   */
  setPollingInterval(intervalMs) {
    this.pollingInterval = intervalMs;

    // Restart polling if currently running
    if (this.isRunning) {
      this.stop();
      this.start();
    }
  }

  /**
   * Load active automations from storage on startup
   */
  _loadActiveAutomations() {
    const stored = automationStorage.getActive();
    stored.forEach((automation) => {
      if (automation.id) {
        this.activeAutomations.set(automation.id, automation);
      }
    });
    console.log(`Loaded ${stored.length} active automations from storage`);
  }

  /**
   * Start polling loop
   */
  _startPolling() {
    // Initial check
    this._checkAllAutomations();

    // Set up interval
    this.intervalId = setInterval(() => {
      this._checkAllAutomations();
    }, this.pollingInterval);
  }

  /**
   * Check all active automations
   */
  async _checkAllAutomations() {
    // Prevent overlapping checks (if previous check is still running)
    if (this.isChecking) {
      console.log('[AutomationMonitor] Skipping check - previous check still running');
      return;
    }

    if (!this.marketDataProvider) {
      console.warn('No market data provider set for AutomationMonitor');
      return;
    }

    // Debug: Show active automations count
    if (this.activeAutomations.size > 0) {
      console.log(
        `[AutomationMonitor] Checking ${this.activeAutomations.size} active automation(s)`
      );
    }

    this.isChecking = true;

    try {
      // Get current market data
      const marketData = this.marketDataProvider();
      if (!marketData || !marketData.positions) {
        return;
      }

      const { positions, spotPrices } = marketData;
      const currentTime = new Date();

      // Check each automation
      for (const [automationId, automation] of this.activeAutomations.entries()) {
        try {
          await this._checkAutomation(automationId, automation, positions, spotPrices, currentTime);
        } catch (error) {
          console.error(`Error checking automation ${automationId}:`, error);
          notificationService.notify(
            NOTIFICATION_TYPES.ERROR,
            `Error checking automation ${automation.position?.symbol}: ${error.message}`
          );
        }
      }
    } catch (error) {
      console.error('Error in AutomationMonitor polling loop:', error);
    } finally {
      this.isChecking = false;
    }
  }

  /**
   * Check single automation
   * @param {string} automationId - Automation ID
   * @param {Object} automation - Automation data
   * @param {Array} positions - Current positions
   * @param {Object} spotPrices - Current spot prices (BTC, ETH)
   * @param {Date} currentTime - Current time
   */
  async _checkAutomation(automationId, automation, positions, spotPrices, currentTime) {
    console.log(
      `[AutomationMonitor] Checking automation ${automationId} for ${automation.position?.symbol}`
    );

    // Find the position this automation is for
    const position = positions.find((p) => p.product_symbol === automation.position?.symbol);
    if (!position) {
      // Position not found - likely closed or expired

      // Track consecutive misses
      if (!automation.missingPositionCount) {
        automation.missingPositionCount = 0;
      }
      automation.missingPositionCount++;

      // If position missing for 3+ consecutive checks (15+ seconds), auto-stop automation
      if (automation.missingPositionCount >= 3) {
        console.warn(
          `[AutomationMonitor] Position ${automation.position?.symbol} not found for ${automation.missingPositionCount} checks. Auto-stopping automation.`
        );

        automation.status = AUTOMATION_STATUS.COMPLETED;
        automation.completionReason = 'Position closed or expired';
        this.activeAutomations.set(automationId, automation);
        automationStorage.updateStatus(automationId, AUTOMATION_STATUS.COMPLETED);

        notificationService.notify({
          type: NOTIFICATION_TYPES.INFO,
          title: 'Automation Auto-Stopped',
          message: `${automation.position?.symbol} position not found. Automation stopped.`,
          automation,
        });

        // Unregister from active monitoring
        this.unregister(automationId);
      } else {
        console.warn(
          `[AutomationMonitor] Position not found for ${automation.position?.symbol} (${automation.missingPositionCount}/3 checks)`
        );
      }
      return;
    }

    // Reset missing count if position found
    automation.missingPositionCount = 0;

    console.log(`[AutomationMonitor] Found position:`, {
      symbol: position.product_symbol,
      strike: position.strike,
      type: position.type,
      mark_price: position.mark_price,
      iv: position.greeks?.iv,
    });

    // Get spot price for this asset
    const underlying = automation.position?.underlying || 'BTC';
    const spotPrice = spotPrices[underlying] || 90000;

    // Prepare current data for evaluation
    const currentData = {
      position,
      spotPrice,
      currentTime,
    };

    // Evaluate entry conditions
    const result = conditionEvaluator.evaluateEntry(currentData, automation.rules.entry);

    console.log(`[AutomationMonitor] Evaluation result for ${automation.position?.symbol}:`, {
      shouldEnter: result.shouldEnter,
      reason: result.reason,
      checksPassedCount: `${result.checks.filter((c) => c.passed).length}/${result.checks.length}`,
      allChecks: result.checks,
      entryRules: automation.rules.entry,
    });

    // Update last checked time
    automation.lastChecked = currentTime.toISOString();

    if (result.shouldEnter) {
      // Conditions met! Trigger notification
      automation.triggeredCount = (automation.triggeredCount || 0) + 1;
      automation.status = AUTOMATION_STATUS.TRIGGERED;

      this.activeAutomations.set(automationId, automation);
      automationStorage.updateStatus(automationId, AUTOMATION_STATUS.TRIGGERED);

      // Send notification
      const message =
        `🔥 Automation triggered for ${position.product_symbol}!\n` +
        `Action: ${automation.rules.entry.action.toUpperCase()} ${automation.rules.entry.quantity} lots\n` +
        `Reason: ${result.reason}\n` +
        `✅ ${result.checks.filter((c) => c.passed).length}/${result.checks.length} conditions met`;

      notificationService.notify(NOTIFICATION_TYPES.ENTRY_TRIGGERED, message, {
        browserNotification: true,
      });

      console.log(`🔥 Automation triggered: ${automationId}`, result);

      // Execute order (respects alertOnlyMode in risk settings)
      try {
        await this._executeEntryOrder(automation, position, spotPrice);
      } catch (error) {
        console.error(`[AutomationMonitor] Failed to execute entry order:`, error);
        automation.status = AUTOMATION_STATUS.ERROR;
        this.activeAutomations.set(automationId, automation);
        automationStorage.updateStatus(automationId, AUTOMATION_STATUS.ERROR);

        notificationService.notify({
          type: NOTIFICATION_TYPES.ERROR,
          title: 'Order Execution Failed',
          message: error.message,
          automation,
        });
      }
    } else {
      // Conditions not yet met
      if (automation.status !== AUTOMATION_STATUS.WAITING) {
        automation.status = AUTOMATION_STATUS.WAITING;
        automationStorage.updateStatus(automationId, AUTOMATION_STATUS.WAITING);
      }
    }
  }

  /**
   * Get status of all automations
   * @returns {Array} Array of automation statuses
   */
  getStatus() {
    return Array.from(this.activeAutomations.entries()).map(([id, automation]) => ({
      id,
      symbol: automation.position?.symbol,
      status: automation.status,
      lastChecked: automation.lastChecked,
      triggeredCount: automation.triggeredCount || 0,
    }));
  }

  /**
   * Get specific automation status
   * @param {string} automationId - Automation ID
   * @returns {Object|null} Automation status or null
   */
  getAutomationStatus(automationId) {
    const automation = this.activeAutomations.get(automationId);
    return automation
      ? {
          id: automationId,
          symbol: automation.position?.symbol,
          status: automation.status,
          lastChecked: automation.lastChecked,
          triggeredCount: automation.triggeredCount || 0,
        }
      : null;
  }

  /**
   * Execute entry order
   * @param {Object} automation - Automation configuration
   * @param {Object} position - Position data
   * @param {number} spotPrice - Current spot price
   */
  async _executeEntryOrder(automation, position, spotPrice) {
    console.log(`[AutomationMonitor] Executing entry order for ${position.product_symbol}`);

    const marketData = {
      spotPrice,
      timestamp: Date.now(),
    };

    try {
      // Call OrderExecutor to place the order
      const orderResult = await orderExecutor.executeEntry(automation, position, marketData);

      console.log('[AutomationMonitor] Order executed successfully:', orderResult);

      // Update automation status to ACTIVE (position opened, now monitoring exit)
      automation.status = AUTOMATION_STATUS.ACTIVE;
      automation.entryOrder = orderResult;
      automation.entryTime = Date.now();
      automation.entryPrice = orderResult.executionPrice;

      this.activeAutomations.set(automation.id, automation);
      automationStorage.save(automation.id, automation);

      // Send success notification
      notificationService.notify({
        type: NOTIFICATION_TYPES.ORDER_FILLED,
        title: 'Entry Order Filled',
        message: `${orderResult.action.toUpperCase()} ${orderResult.quantity} ${orderResult.symbol} @ ${orderResult.executionPrice?.toFixed(4)}`,
        automation,
      });
    } catch (error) {
      console.error('[AutomationMonitor] Entry order failed:', error);
      throw error;
    }
  }
}

// Singleton instance
const automationMonitor = new AutomationMonitor();
export default automationMonitor;
