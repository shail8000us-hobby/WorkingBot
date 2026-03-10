/**
 * usePayoffCalculation Hook
 * =========================
 * React hook for managing payoff calculations in the adjustment system.
 * 
 * Provides:
 * - Real-time payoff calculation on position/trade changes
 * - Black-Scholes pre-expiry curves, theta fan, probability overlay
 * - Delta profile, stress matrix, net debit/credit
 * - Debounced updates for performance
 * - Memoized chart data and metrics
 * 
 * Created: January 31, 2026
 * Enhanced: March 6, 2026 — BS engine integration
 */

import { useMemo } from 'react';
import { calculateCombinedPayoff, formatCurrency, formatPercentage, formatProposedAsPositions } from '../utils/adjustmentPayoffEngine';
import {
  calculateThetaFanCurves,
  calculateProbabilityOverlay,
  calculateDeltaProfile,
  calculateStressMatrix,
  calculateNetDebitCredit,
  calculatePreExpiryPayoff,
  getWeightedIV,
  generateDynamicPriceRange,
} from '../utils/adjustmentBSEngine';
import { getTimeToExpiry, parsePositionSymbol } from '../utils/adjustmentPayoffEngine';

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
    thetaFanEnabled = false,
    deltaProfileEnabled = false,
    daysToTarget = 0,
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
      // Build combined position list for dynamic range
      const proposed = formatProposedAsPositions(proposedTrades || []);
      const allPositions = [...(currentPositions || []), ...proposed];

      // Dynamic price range: auto-expands to cover all strikes ±5%
      const dynamicRange = generateDynamicPriceRange(spotPrice, allPositions, rangePercent);

      const result = calculateCombinedPayoff(
        currentPositions || [],
        proposedTrades || [],
        spotPrice,
        rangePercent,
        dynamicRange
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

  // ============================================================================
  // BS ENGINE — Enhanced calculations
  // ============================================================================

  // Resolve combined positions for BS calculations
  const combinedPositions = useMemo(() => {
    const proposed = formatProposedAsPositions(proposedTrades || []);
    return [...(currentPositions || []), ...proposed];
  }, [currentPositions, proposedTrades]);

  // Today's BS pre-expiry P&L curve (daysToTarget = 0 → current moment)
  // This is the "On Target Date" blue line — shows what P&L looks like today
  // before time decay finishes. Updates when daysToTarget changes via slider.
  const todayBsPayoff = useMemo(() => {
    if (!enabled || !spotPrice || !payoffResult.isValid || !payoffResult.priceRange?.length) return null;
    if (combinedPositions.length === 0) return null;
    try {
      return calculatePreExpiryPayoff(
        combinedPositions,
        spotPrice,
        payoffResult.priceRange,
        daysToTarget,
      );
    } catch (e) {
      console.error('[usePayoffCalculation] todayBs error:', e);
      return null;
    }
  }, [enabled, spotPrice, payoffResult.isValid, payoffResult.priceRange, combinedPositions, daysToTarget]);

  // Merge todayBs into chartData rows
  const enhancedChartData = useMemo(() => {
    if (!payoffResult.chartData?.length) return payoffResult.chartData || [];
    if (!todayBsPayoff) return payoffResult.chartData;
    return payoffResult.chartData.map((d, i) => ({
      ...d,
      todayBs: todayBsPayoff[i] != null ? Math.round(todayBsPayoff[i].pnl * 100) / 100 : null,
    }));
  }, [payoffResult.chartData, todayBsPayoff]);

  // Resolve average IV and days to expiry
  const ivAndExpiry = useMemo(() => {
    const allPositions = combinedPositions.length > 0 ? combinedPositions : (currentPositions || []);
    const iv = getWeightedIV(allPositions, spotPrice);

    // Find the nearest expiry
    let minDays = 30;
    allPositions.forEach(pos => {
      const parsed = parsePositionSymbol(pos.product_symbol);
      if (parsed?.expiry) {
        const T = getTimeToExpiry(parsed.expiry);
        const days = T * 365.25;
        if (days > 0.5) {
          minDays = Math.min(minDays, days);
        }
      }
    });

    return { iv, daysToExpiry: minDays };
  }, [combinedPositions, currentPositions, spotPrice]);

  // Net debit/credit for proposed trades
  const netDebitCredit = useMemo(() => {
    return calculateNetDebitCredit(proposedTrades);
  }, [proposedTrades]);

  // Theta fan curves (only when enabled for performance)
  const thetaFanData = useMemo(() => {
    if (!thetaFanEnabled || !enabled || !spotPrice || !payoffResult.isValid) {
      return null;
    }

    try {
      const priceRange = payoffResult.priceRange || payoffResult.chartData?.map(d => d.price) || [];
      if (priceRange.length === 0) return null;

      return calculateThetaFanCurves(
        combinedPositions,
        spotPrice,
        priceRange,
        ivAndExpiry.daysToExpiry
      );
    } catch (error) {
      console.error('[usePayoffCalculation] Theta fan error:', error);
      return null;
    }
  }, [thetaFanEnabled, enabled, spotPrice, payoffResult.isValid, payoffResult.priceRange, payoffResult.chartData, combinedPositions, ivAndExpiry.daysToExpiry]);

  // Probability distribution overlay
  const probabilityData = useMemo(() => {
    if (!enabled || !spotPrice || !payoffResult.isValid) {
      return null;
    }

    try {
      const priceRange = payoffResult.priceRange || payoffResult.chartData?.map(d => d.price) || [];
      if (priceRange.length === 0) return null;

      return calculateProbabilityOverlay(
        spotPrice,
        ivAndExpiry.iv,
        ivAndExpiry.daysToExpiry / 365.25,
        priceRange
      );
    } catch (error) {
      console.error('[usePayoffCalculation] Probability overlay error:', error);
      return null;
    }
  }, [enabled, spotPrice, payoffResult.isValid, payoffResult.priceRange, payoffResult.chartData, ivAndExpiry]);

  // Delta profile (only when enabled)
  const deltaProfileData = useMemo(() => {
    if (!deltaProfileEnabled || !enabled || !spotPrice || !payoffResult.isValid) {
      return null;
    }

    try {
      const priceRange = payoffResult.priceRange || payoffResult.chartData?.map(d => d.price) || [];
      if (priceRange.length === 0) return null;

      return calculateDeltaProfile(
        combinedPositions,
        spotPrice,
        priceRange,
        0 // Current date
      );
    } catch (error) {
      console.error('[usePayoffCalculation] Delta profile error:', error);
      return null;
    }
  }, [deltaProfileEnabled, enabled, spotPrice, payoffResult.isValid, payoffResult.priceRange, payoffResult.chartData, combinedPositions]);

  // Stress test matrix
  const stressTestData = useMemo(() => {
    if (!enabled || !spotPrice) return null;

    try {
      const currentStress = calculateStressMatrix(currentPositions || [], spotPrice, 0);
      const combinedStress = calculateStressMatrix(combinedPositions, spotPrice, 0);
      return { current: currentStress, combined: combinedStress };
    } catch (error) {
      console.error('[usePayoffCalculation] Stress test error:', error);
      return null;
    }
  }, [enabled, spotPrice, currentPositions, combinedPositions]);

  // ============================================================================
  // FORMATTED METRICS (unchanged from original + net debit/credit)
  // ============================================================================

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
    if (!enhancedChartData || enhancedChartData.length === 0) {
      return null;
    }

    const allPnls = enhancedChartData.flatMap(d => [d.current, d.combined, d.todayBs].filter(v => v != null));
    const minPnl = Math.min(...allPnls);
    const maxPnl = Math.max(...allPnls);
    const padding = Math.abs(maxPnl - minPnl) * 0.1 || 100;

    return {
      yDomain: [minPnl - padding, maxPnl + padding],
      xDomain: [
        enhancedChartData[0]?.price,
        enhancedChartData[enhancedChartData.length - 1]?.price,
      ],
      zeroLine: 0,
      spotLine: spotPrice,
    };
  }, [enhancedChartData, spotPrice]);

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
    // Raw calculation results (chartData overridden with todayBs merged in)
    ...payoffResult,
    chartData: enhancedChartData,

    // Formatted for display
    formattedMetrics,

    // Chart helpers
    chartConfig,

    // Quick summary
    summary,

    // BS engine results
    thetaFanData,
    probabilityData,
    deltaProfileData,
    stressTestData,
    netDebitCredit,
    ivAndExpiry,
  };
}

export default usePayoffCalculation;
