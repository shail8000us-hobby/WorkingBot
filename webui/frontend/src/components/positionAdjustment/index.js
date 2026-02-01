/**
 * Position Adjustment System
 * ==========================
 * Exports for the position adjustment module.
 * 
 * This module provides Sensibull-like position adjustment functionality:
 * - View current positions payoff
 * - Add proposed trades with live payoff preview
 * - Execute via autoloop for Delta Exchange low liquidity
 * 
 * Created: January 31, 2026
 */

export { default as PositionAdjustmentPanel } from './PositionAdjustmentPanel';
export { default as AdjustmentChainTable } from './AdjustmentChainTable';
export { default as AdjustmentPayoffChart } from './AdjustmentPayoffChart';
export { default as AdjustmentMetricsPanel } from './AdjustmentMetricsPanel';
export { default as ProposedTradesTable } from './ProposedTradesTable';
export { default as AdjustmentReviewDialog } from './AdjustmentReviewDialog';
export { default as AdjustmentExecutionProgress } from './AdjustmentExecutionProgress';
export { usePayoffCalculation } from './hooks/usePayoffCalculation';
export * from './utils/adjustmentPayoffEngine';
