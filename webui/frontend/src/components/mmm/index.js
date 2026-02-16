/**
 * MMM Components — Money Mind & Method
 *
 * Barrel exports for all MMM components.
 *
 * Created: February 15, 2026
 * Updated: Phase 3-7 components added
 */

// Main Dashboard
export { default as MMMDashboard } from './MMMDashboard';

// Phase 2: Config Panel & Strike Selector
export { default as MMMConfigPanel } from './MMMConfigPanel';
export { default as MMMStrikeSelector } from './MMMStrikeSelector';

// Phase 3-7: Live Dashboard Components
export { default as MMMStatusBanner } from './MMMStatusBanner';
export { default as MMMPositionsTable } from './MMMPositionsTable';
export { default as MMMTriggerGauge } from './MMMTriggerGauge';
export { default as MMMAdjustmentLog } from './MMMAdjustmentLog';
export { default as MMMSessionCard } from './MMMSessionCard';
export { default as MMMStrikeMap } from './MMMStrikeMap';
export { default as MMMPnLChart } from './MMMPnLChart';
export { default as MMMBothSidesAlert } from './MMMBothSidesAlert';
export { default as MMMSafetyPanel } from './MMMSafetyPanel';
export { default as MMMActivityFeed } from './MMMActivityFeed';

// Error Boundary
export { default as MMMErrorBoundary } from './MMMErrorBoundary';

// Context & Service
export { MMMProvider, useMMM } from './MMMContext';
export { default as mmmService } from './mmmService';

// Hooks
export { default as useMMMParams } from './hooks/useMMMParams';
export { default as useMMMWebSocket } from './hooks/useMMMWebSocket';

// Utilities
export * from './utils/mmmFormatters';
export * from './utils/mmmCalculations';
