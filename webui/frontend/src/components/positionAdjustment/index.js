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
 * Updated: February 1, 2026 - Added SensibullStyleAdjustmentPage
 * Updated: May 7, 2026 - Added InlineAdjustmentWrapper for payoff graph inline adjustment
 */

export { default as PositionAdjustmentPanel } from './PositionAdjustmentPanel';
export { default as SensibullStyleAdjustmentPage } from './SensibullStyleAdjustmentPage';
export { default as AdjustmentChainTable } from './AdjustmentChainTable';
export { default as AdjustmentPayoffChart } from './AdjustmentPayoffChart';
export { default as AdjustmentMetricsPanel } from './AdjustmentMetricsPanel';
export { default as ProposedTradesTable } from './ProposedTradesTable';
export { default as AdjustmentReviewDialog } from './AdjustmentReviewDialog';
export { default as AdjustmentExecutionProgress } from './AdjustmentExecutionProgress';
export { default as InlineAdjustmentWrapper } from './InlineAdjustmentWrapper';
export { usePayoffCalculation } from './hooks/usePayoffCalculation';
export * from './utils/adjustmentPayoffEngine';
