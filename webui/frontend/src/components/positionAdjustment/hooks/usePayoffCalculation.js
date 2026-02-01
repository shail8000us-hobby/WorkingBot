/**
 * usePayoffCalculation Hook
 * =========================
 * React hook for managing payoff calculations in the adjustment system.
 * 
 * Provides:
 * - Real-time payoff calculation on position/trade changes
 * - Debounced updates for performance
 * - Memoized chart data and metrics
 * 
 * Created: January 31, 2026
 */

import { useMemo, useCallback, useState, useEffect } from 'react';
import { calculateCombinedPayoff, formatCurrency, formatPercentage } from '../utils/adjustmentPayoffEngine';

/**
 * Hook for calculating and managing payoff data
 * 
 * @param {Array} currentPositions - Existing positions from OptionsPanel
 * @param {Array} proposedTrades - User-selected new trades
 * @param {number} spotPrice - Current underlying spot price
 * @param {Object} options - Optional configuration
 * @returns {Object} Calculated payoff data and metrics
 */
export function usePayoffCalculation(currentPositions, proposedTrades, spotPrice, options = {}) {
  const {
    rangePercent = 15,
    enabled = true,
  } = options;

  // Calculate payoff data when inputs change
  const payoffResult = useMemo(() => {
    if (!enabled || !spotPrice || spotPrice <= 0) {
      return {
        chartData: [],
        currentMetrics: null,
        combinedMetrics: null,
        metricsChange: null,
        hasProposedTrades: false,
        isValid: false,
      };
    }

    try {
      const result = calculateCombinedPayoff(
        currentPositions || [],
        proposedTrades || [],
        spotPrice,
        rangePercent
      );

      return {
        ...result,
        hasProposedTrades: proposedTrades && proposedTrades.length > 0,
        isValid: true,
      };
    } catch (error) {
      console.error('[usePayoffCalculation] Error:', error);
      return {
        chartData: [],
        currentMetrics: null,
        combinedMetrics: null,
        metricsChange: null,
        hasProposedTrades: false,
        isValid: false,
        error: error.message,
      };
    }
  }, [currentPositions, proposedTrades, spotPrice, rangePercent, enabled]);

  // Formatted metrics for display
  const formattedMetrics = useMemo(() => {
    if (!payoffResult.currentMetrics && !payoffResult.combinedMetrics) {
      return null;
    }

    const current = payoffResult.currentMetrics || {};
    const combined = payoffResult.combinedMetrics || {};
    const change = payoffResult.metricsChange || {};

    return {
      current: {
        maxProfit: formatCurrency(current.maxProfit),
        maxLoss: formatCurrency(current.maxLoss),
        breakevens: current.breakevens?.map(b => formatCurrency(b).replace('$', '')) || [],
        pop: formatPercentage(current.pop),
        netDelta: current.netDelta?.toFixed(3) || '0',
        netTheta: formatCurrency(current.netTheta),
        netVega: formatCurrency(current.netVega),
        netPremium: formatCurrency(current.netPremium),
        riskReward: current.riskReward === 'Unlimited' ? '∞' : current.riskReward?.toFixed(2),
      },
      combined: {
        maxProfit: formatCurrency(combined.maxProfit),
        maxLoss: formatCurrency(combined.maxLoss),
        breakevens: combined.breakevens?.map(b => formatCurrency(b).replace('$', '')) || [],
        pop: formatPercentage(combined.pop),
        netDelta: combined.netDelta?.toFixed(3) || '0',
        netTheta: formatCurrency(combined.netTheta),
        netVega: formatCurrency(combined.netVega),
        netPremium: formatCurrency(combined.netPremium),
        riskReward: combined.riskReward === 'Unlimited' ? '∞' : combined.riskReward?.toFixed(2),
      },
      change: {
        maxProfit: formatCurrency(change.maxProfitChange, true),
        maxLoss: formatCurrency(change.maxLossChange, true),
        pop: formatPercentage(change.popChange, true),
        netDelta: change.deltaChange?.toFixed(3) || '0',
        netTheta: formatCurrency(change.thetaChange, true),
        netVega: formatCurrency(change.vegaChange, true),
      },
      raw: {
        current: payoffResult.currentMetrics,
        combined: payoffResult.combinedMetrics,
        change: payoffResult.metricsChange,
      },
    };
  }, [payoffResult]);

  // Chart configuration helpers
  const chartConfig = useMemo(() => {
    if (!payoffResult.chartData || payoffResult.chartData.length === 0) {
      return null;
    }

    const allPnls = payoffResult.chartData.flatMap(d => [d.current, d.combined].filter(v => v != null));
    const minPnl = Math.min(...allPnls);
    const maxPnl = Math.max(...allPnls);
    const padding = Math.abs(maxPnl - minPnl) * 0.1 || 100;

    return {
      yDomain: [minPnl - padding, maxPnl + padding],
      xDomain: [
        payoffResult.chartData[0]?.price,
        payoffResult.chartData[payoffResult.chartData.length - 1]?.price,
      ],
      zeroLine: 0,
      spotLine: spotPrice,
    };
  }, [payoffResult.chartData, spotPrice]);

  // Summary for quick display
  const summary = useMemo(() => {
    if (!payoffResult.isValid) {
      return {
        hasPositions: false,
        hasProposedTrades: false,
        netChange: null,
        recommendation: null,
      };
    }

    const hasPositions = currentPositions && currentPositions.length > 0;
    const hasProposedTrades = proposedTrades && proposedTrades.length > 0;

    let recommendation = null;
    if (hasProposedTrades && payoffResult.metricsChange) {
      const { popChange, maxLossChange } = payoffResult.metricsChange;
      
      if (popChange > 0.05 && maxLossChange > 0) {
        recommendation = { type: 'positive', message: 'Improves PoP and reduces max loss' };
      } else if (popChange > 0.05) {
        recommendation = { type: 'neutral', message: 'Improves PoP but increases max loss' };
      } else if (maxLossChange > 0) {
        recommendation = { type: 'neutral', message: 'Reduces max loss but lowers PoP' };
      } else if (popChange < -0.1 || maxLossChange < -500) {
        recommendation = { type: 'warning', message: 'Significantly increases risk profile' };
      }
    }

    return {
      hasPositions,
      hasProposedTrades,
      tradeCount: proposedTrades?.length || 0,
      positionCount: currentPositions?.length || 0,
      netPremium: payoffResult.combinedMetrics?.netPremium,
      recommendation,
    };
  }, [payoffResult, currentPositions, proposedTrades]);

  return {
    // Raw calculation results
    ...payoffResult,
    
    // Formatted for display
    formattedMetrics,
    
    // Chart helpers
    chartConfig,
    
    // Quick summary
    summary,
  };
}

export default usePayoffCalculation;
