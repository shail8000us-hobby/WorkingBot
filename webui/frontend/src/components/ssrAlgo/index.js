/**
 * SSR Algo Components
 * 
 * Exports all SSR Algo components for easy importing.
 * Per Architecture Doc: Section 6
 * Per Implementation Plan: Section 2.3
 * 
 * Created: February 2, 2026
 * Updated: February 3, 2026 - Added hooks, utils, and shared components
 * Updated: February 3, 2026 - Added V2 Dashboard with professional Tailwind design
 */

// Main Dashboard Components
export { default as SSRAlgoDashboard } from './SSRAlgoDashboard';
export { default as SSRAlgoConfigPanel } from './SSRAlgoConfigPanel';

// V2 Dashboard (Professional Trading UI with Tailwind)
export { 
  SSRAlgoDashboardV2,
  MaxLossAlertBanner,
  SSRAlgoConfigV2,
  PositionLegsTableV2,
  PayoffDiagramV2,
  OrderHistoryTabs
} from './v2';
export { default as SSRAlgoSessionCard } from './SSRAlgoSessionCard';
export { default as SSRAlgoPayoffChart } from './SSRAlgoPayoffChart';
export { default as SSRAlgoPositionsTable } from './SSRAlgoPositionsTable';
export { default as SSRAlgoStatusBanner } from './SSRAlgoStatusBanner';
export { default as SSRAlgoTriggerHistory } from './SSRAlgoTriggerHistory';
export { default as SSRAlgoErrorBoundary } from './SSRAlgoErrorBoundary';
export { default as SSRAlgoLogPanel } from './SSRAlgoLogPanel';

// Service and Context
export { default as ssrAlgoService } from './ssrAlgoService';
export { SSRAlgoProvider, useSSRAlgo } from './SSRAlgoContext';

// Custom Hooks
export { 
  useSSRAlgoSession, 
  useSSRAlgoPayoff, 
  useSSRAlgoMonitor 
} from './hooks';

// Utility Functions
export * from './utils';

// Shared UI Components
export * from './shared';
