/**
 * ConditionEvaluator - Check if automation conditions are met
 * 
 * Features:
 * - Evaluate entry conditions (IV, moneyness, premium, time, price)
 * - Evaluate exit conditions (profit/loss targets, trailing stops, etc.)
 * - Support for complex logic (AND/OR operators)
 */

import { MONEYNESS, MONEYNESS_THRESHOLDS, OPERATORS } from '../types/constants';

class ConditionEvaluator {
  /**
   * Evaluate entry conditions
   * @param {Object} currentData - Current market data (position, prices, greeks)
   * @param {Object} rules - Entry rules
   * @returns {Object} { shouldEnter: boolean, reason: string, details: object }
   */
  evaluateEntry(currentData, rules) {
    const { position, spotPrice, currentTime } = currentData;
    const checks = [];

    // 1. Check IV filter
    if (rules.ivFilter?.enabled) {
      const iv = position.greeks?.iv || position.iv || 0;
      const ivPercent = iv * 100;
      const threshold = rules.ivFilter.value;
      const operator = rules.ivFilter.operator;
      
      const ivCheck = this._compareValues(ivPercent, operator, threshold);
      checks.push({
        name: 'IV Filter',
        passed: ivCheck,
        detail: `IV ${ivPercent.toFixed(1)}% ${operator} ${threshold}%`,
      });
      
      if (!ivCheck) {
        return {
          shouldEnter: false,
          reason: `IV condition not met: ${ivPercent.toFixed(1)}% ${operator} ${threshold}%`,
          checks,
        };
      }
    }

    // 2. Check moneyness
    if (rules.moneyness) {
      const moneyness = this._calculateMoneyness(position.strike, spotPrice);
      const moneynessCheck = moneyness === rules.moneyness;
      
      checks.push({
        name: 'Moneyness',
        passed: moneynessCheck,
        detail: `Expected ${rules.moneyness.toUpperCase()}, got ${moneyness.toUpperCase()}`,
      });
      
      if (!moneynessCheck) {
        return {
          shouldEnter: false,
          reason: `Moneyness condition not met: Expected ${rules.moneyness.toUpperCase()}, got ${moneyness.toUpperCase()}`,
          checks,
        };
      }
    }

    // 3. Check premium range
    if (rules.premiumRange?.enabled) {
      const premium = position.mark_price || position.mid_price || position.entry_price || 0;
      const inRange = premium >= rules.premiumRange.min && premium <= rules.premiumRange.max;
      
      checks.push({
        name: 'Premium Range',
        passed: inRange,
        detail: `Premium $${premium} in range [$${rules.premiumRange.min}, $${rules.premiumRange.max}]`,
      });
      
      if (!inRange) {
        return {
          shouldEnter: false,
          reason: `Premium $${premium} outside range [$${rules.premiumRange.min}, $${rules.premiumRange.max}]`,
          checks,
        };
      }
    }

    // 4. Check time filter
    if (rules.timeFilter?.enabled) {
      const now = currentTime || new Date();
      const currentHour = now.getHours();
      const currentMinute = now.getMinutes();
      const currentTimeStr = `${String(currentHour).padStart(2, '0')}:${String(currentMinute).padStart(2, '0')}`;
      
      const inTimeWindow = this._isInTimeWindow(
        currentTimeStr,
        rules.timeFilter.startTime,
        rules.timeFilter.endTime
      );
      
      checks.push({
        name: 'Time Window',
        passed: inTimeWindow,
        detail: `Current time ${currentTimeStr} in window [${rules.timeFilter.startTime}, ${rules.timeFilter.endTime}]`,
      });
      
      if (!inTimeWindow) {
        return {
          shouldEnter: false,
          reason: `Outside time window: Current ${currentTimeStr}, Window [${rules.timeFilter.startTime}, ${rules.timeFilter.endTime}]`,
          checks,
        };
      }
    }

    // 5. Check underlying price range
    if (rules.underlyingPrice?.enabled) {
      const inRange = spotPrice >= rules.underlyingPrice.min && spotPrice <= rules.underlyingPrice.max;
      
      checks.push({
        name: 'Underlying Price',
        passed: inRange,
        detail: `Spot $${spotPrice} in range [$${rules.underlyingPrice.min}, $${rules.underlyingPrice.max}]`,
      });
      
      if (!inRange) {
        return {
          shouldEnter: false,
          reason: `Spot price $${spotPrice} outside range [$${rules.underlyingPrice.min}, $${rules.underlyingPrice.max}]`,
          checks,
        };
      }
    }

    // All conditions passed
    return {
      shouldEnter: true,
      reason: 'All entry conditions met',
      checks,
    };
  }

  /**
   * Evaluate exit conditions
   * @param {Object} currentData - Current market data
   * @param {Object} entryData - Data from when position was entered
   * @param {Object} rules - Exit rules
   * @returns {Object} { shouldExit: boolean, reason: string, details: object }
   */
  evaluateExit(currentData, entryData, rules) {
    const { position, spotPrice, currentTime } = currentData;
    const { entryPrice, entryTime, entryAction, peakPrice = entryPrice } = entryData;
    const checks = [];
    const currentPrice = position.mark_price || position.mid_price || 0;

    // Calculate PnL correctly based on position direction
    // BUY: profit when price rises (currentPrice > entryPrice)
    // SELL: profit when price falls (currentPrice < entryPrice)
    let pnl, pnlDollar;
    
    if (entryAction === 'sell' || position.size < 0) {
      // SELL position: profit when price drops
      pnl = ((entryPrice - currentPrice) / entryPrice) * 100;
      pnlDollar = (entryPrice - currentPrice) * Math.abs(position.size || 1);
    } else {
      // BUY position: profit when price rises
      pnl = ((currentPrice - entryPrice) / entryPrice) * 100;
      pnlDollar = (currentPrice - entryPrice) * Math.abs(position.size || 1);
    }

    // 1. Check Take Profit
    if (rules.takeProfit?.enabled) {
      const tpCheck = pnl >= rules.takeProfit.percentage ||
                     (rules.takeProfit.fixedValue > 0 && pnlDollar >= rules.takeProfit.fixedValue);
      
      checks.push({
        name: 'Take Profit',
        passed: tpCheck,
        detail: `PnL: ${pnl.toFixed(1)}% / Target: ${rules.takeProfit.percentage}%`,
      });

      if (tpCheck) {
        return {
          shouldExit: true,
          reason: `Take profit target reached: ${pnl.toFixed(1)}%`,
          exitType: 'TAKE_PROFIT',
          checks,
        };
      }
    }

    // 2. Check Stop Loss
    if (rules.stopLoss?.enabled) {
      const slCheck = pnl <= -rules.stopLoss.percentage ||
                     (rules.stopLoss.fixedValue > 0 && pnlDollar <= -rules.stopLoss.fixedValue);
      
      checks.push({
        name: 'Stop Loss',
        passed: !slCheck,
        detail: `PnL: ${pnl.toFixed(1)}% / Stop: -${rules.stopLoss.percentage}%`,
      });

      if (slCheck) {
        return {
          shouldExit: true,
          reason: `Stop loss triggered: ${pnl.toFixed(1)}%`,
          exitType: 'STOP_LOSS',
          checks,
        };
      }
    }

    // 3. Check Trailing Stop
    if (rules.trailingStop?.enabled) {
      const activationPnL = rules.trailingStop.activationProfit || 10;
      
      // Only activate trailing stop after reaching activation profit
      if (pnl >= activationPnL) {
        let trailingStopPrice;
        
        if (entryAction === 'sell' || position.size < 0) {
          // SELL position: trail from lowest price (best price for seller)
          const lowestPrice = peakPrice; // peakPrice tracks best price (lowest for sell)
          if (rules.trailingStop.type === 'percentage') {
            const trailDistance = rules.trailingStop.distance || 20;
            trailingStopPrice = lowestPrice * (1 + trailDistance / 100);
          } else {
            trailingStopPrice = lowestPrice + rules.trailingStop.distance;
          }
          const trailCheck = currentPrice >= trailingStopPrice;
          
          checks.push({
            name: 'Trailing Stop',
            passed: !trailCheck,
            detail: `Price: ${currentPrice.toFixed(4)} / Trail: ${trailingStopPrice.toFixed(4)} (SELL)`,
          });

          if (trailCheck) {
            return {
              shouldExit: true,
              reason: `Trailing stop hit: Price ${currentPrice.toFixed(4)} above ${trailingStopPrice.toFixed(4)}`,
              exitType: 'TRAILING_STOP',
              checks,
            };
          }
        } else {
          // BUY position: trail from highest price (best price for buyer)
          if (rules.trailingStop.type === 'percentage') {
            const trailDistance = rules.trailingStop.distance || 20;
            trailingStopPrice = peakPrice * (1 - trailDistance / 100);
          } else {
            trailingStopPrice = peakPrice - rules.trailingStop.distance;
          }
          const trailCheck = currentPrice <= trailingStopPrice;
          
          checks.push({
            name: 'Trailing Stop',
            passed: !trailCheck,
            detail: `Price: ${currentPrice.toFixed(4)} / Trail: ${trailingStopPrice.toFixed(4)} (BUY)`,
          });

          if (trailCheck) {
            return {
              shouldExit: true,
              reason: `Trailing stop hit: Price ${currentPrice.toFixed(4)} below ${trailingStopPrice.toFixed(4)}`,
              exitType: 'TRAILING_STOP',
              checks,
            };
          }
        }
      }
    }

    // 4. Check Time-Based Exit
    if (rules.timeBased?.enabled) {
      const now = new Date(currentTime || Date.now());
      
      // Check exit time
      if (rules.timeBased.exitTime) {
        const [hours, minutes] = rules.timeBased.exitTime.split(':').map(Number);
        const exitTime = new Date(now);
        exitTime.setHours(hours, minutes, 0, 0);
        
        if (now >= exitTime) {
          return {
            shouldExit: true,
            reason: `Time-based exit: ${rules.timeBased.exitTime}`,
            exitType: 'TIME_BASED',
            checks,
          };
        }
      }
      
      // Check duration
      if (rules.timeBased.duration > 0) {
        const durationMs = rules.timeBased.duration * 60 * 1000;
        const elapsed = now - entryTime;
        
        if (elapsed >= durationMs) {
          return {
            shouldExit: true,
            reason: `Duration limit reached: ${rules.timeBased.duration} minutes`,
            exitType: 'TIME_BASED',
            checks,
          };
        }
      }
      
      // Check before expiry
      if (rules.timeBased.closeBeforeExpiry && position.expiry_time) {
        const expiryTime = new Date(position.expiry_time * 1000);
        const closeTime = new Date(expiryTime.getTime() - 10 * 60 * 1000); // 10 min before
        
        if (now >= closeTime) {
          return {
            shouldExit: true,
            reason: 'Auto-close before expiry',
            exitType: 'TIME_BASED',
            checks,
          };
        }
      }
    }

    // 5. Check Underlying Price Exit
    if (rules.underlyingExit?.enabled) {
      if (rules.underlyingExit.abovePrice > 0 && spotPrice >= rules.underlyingExit.abovePrice) {
        return {
          shouldExit: true,
          reason: `Underlying price above target: $${spotPrice} >= $${rules.underlyingExit.abovePrice}`,
          exitType: 'UNDERLYING_PRICE',
          checks,
        };
      }
      
      if (rules.underlyingExit.belowPrice > 0 && spotPrice <= rules.underlyingExit.belowPrice) {
        return {
          shouldExit: true,
          reason: `Underlying price below target: $${spotPrice} <= $${rules.underlyingExit.belowPrice}`,
          exitType: 'UNDERLYING_PRICE',
          checks,
        };
      }
    }

    // No exit conditions met
    return {
      shouldExit: false,
      reason: 'No exit conditions met',
      checks,
    };
  }

  /**
   * Calculate moneyness (ITM/ATM/OTM) based on strike vs spot
   * @param {number} strike - Strike price
   * @param {number} spotPrice - Current spot price
   * @returns {string} 'itm' | 'atm' | 'otm'
   */
  _calculateMoneyness(strike, spotPrice) {
    const percentDiff = ((strike - spotPrice) / spotPrice) * 100;
    
    if (percentDiff < MONEYNESS_THRESHOLDS.ATM_MIN) {
      return MONEYNESS.ITM; // Strike well below spot
    } else if (percentDiff > MONEYNESS_THRESHOLDS.ATM_MAX) {
      return MONEYNESS.OTM; // Strike well above spot
    } else {
      return MONEYNESS.ATM; // Strike near spot
    }
  }

  /**
   * Compare two values based on operator
   * @param {number} value - Current value
   * @param {string} operator - Comparison operator
   * @param {number} threshold - Threshold value
   * @returns {boolean} Comparison result
   */
  _compareValues(value, operator, threshold) {
    switch (operator) {
      case OPERATORS.GREATER_THAN:
        return value > threshold;
      case OPERATORS.LESS_THAN:
        return value < threshold;
      case OPERATORS.GREATER_EQUAL:
        return value >= threshold;
      case OPERATORS.LESS_EQUAL:
        return value <= threshold;
      case OPERATORS.EQUAL:
        return Math.abs(value - threshold) < 0.01; // Fuzzy equality
      default:
        return false;
    }
  }

  /**
   * Check if current time is within time window
   * @param {string} currentTime - Current time "HH:MM"
   * @param {string} startTime - Start time "HH:MM"
   * @param {string} endTime - End time "HH:MM"
   * @returns {boolean} True if in window
   */
  _isInTimeWindow(currentTime, startTime, endTime) {
    const toMinutes = (timeStr) => {
      const [hours, minutes] = timeStr.split(':').map(Number);
      return hours * 60 + minutes;
    };
    
    const current = toMinutes(currentTime);
    const start = toMinutes(startTime);
    const end = toMinutes(endTime);
    
    // Handle overnight windows (e.g., 23:00 to 01:00)
    if (end < start) {
      return current >= start || current <= end;
    }
    
    return current >= start && current <= end;
  }
}

// Singleton instance
const conditionEvaluator = new ConditionEvaluator();
export default conditionEvaluator;
