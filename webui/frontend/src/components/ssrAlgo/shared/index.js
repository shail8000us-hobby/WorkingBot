/**
 * SSR Algo Shared Components
 * 
 * Exports all reusable UI components for SSR Algo.
 * 
 * Per Implementation Plan: Section 2.3
 * Created: February 3, 2026
 */

// Status and badge components
export { default as StatusBadge, ZoneBadge, SessionStatusBadge } from './StatusBadge';

// Metric display components
export { default as MetricCard, PnLCard, DistanceCard, MetricCardGrid } from './MetricCard';

// Zone visualization components
export { 
  default as PriceZoneBar, 
  CompactZoneIndicator, 
  VerticalZoneIndicator 
} from './PriceZoneBar';

// Alert components
export { 
  default as CircuitBreakerAlert, 
  CompactCircuitBreakerAlert 
} from './CircuitBreakerAlert';

// Loading components
export { 
  default as LoadingSpinner, 
  LoadingOverlay, 
  SkeletonLoader, 
  ButtonSpinner,
  FullPageLoader,
  InlineLoader
} from './LoadingSpinner';

// Error handling components
export { 
  default as ErrorBoundary, 
  CompactError, 
  APIError, 
  InlineError,
  SSRAlgoErrorBoundary
} from './ErrorBoundary';

// Dialog components
export { 
  default as ConfirmDialog, 
  StopSessionDialog, 
  EmergencyCloseDialog,
  ManualTriggerDialog,
  ResetConfigDialog
} from './ConfirmDialog';

// Strike preview components
export { 
  default as StrikePreviewRow, 
  StrikePreviewTable 
} from './StrikePreviewRow';
