/**
 * Common Components - Barrel Export
 * 
 * Re-exports all common components for easy importing.
 */

export { PriceDisplay, type PriceDisplayProps } from './PriceDisplay';
export { StatusBadge, type StatusBadgeProps, type StatusType } from './StatusBadge';
export { TimeAgo, type TimeAgoProps } from './TimeAgo';
export { 
  SafetyCheck, 
  SafetyGate,
  type SafetyCheckProps, 
  type SafetyCheckItem,
  type SafetyGateProps,
} from './SafetyCheck';
export { 
  Metric, 
  MetricGrid,
  type MetricProps,
  type MetricGridProps,
} from './Metric';
export {
  LoadingSpinner,
  LoadingCard,
  LoadingTable,
  FullPageLoading,
  type LoadingSpinnerProps,
  type LoadingCardProps,
  type LoadingTableProps,
  type FullPageLoadingProps,
} from './LoadingState';
export { ShortcutsHelp } from './ShortcutsHelp';
export { CommandPalette, type CommandItem } from './CommandPalette';
export { FocusModeToggle } from './FocusModeToggle';

// Error & Edge Case Components
export { ErrorBoundary, ErrorAlert } from './ErrorBoundary';
export { BackendDownHandler } from './BackendDownHandler';
export { StaleDataIndicator, useStaleData } from './StaleDataIndicator';
export { DisconnectBanner, ConnectionIndicator } from './DisconnectBanner';
export {
  SkeletonCard,
  SkeletonMetricCard,
  SkeletonOrderRow,
  SkeletonPositionCard,
  SkeletonGrid,
  SkeletonChart,
  SkeletonTable,
  SkeletonDashboard,
} from './LoadingSkeletons';
export {
  EmptyState,
  EmptyOrders,
  EmptyPositions,
  EmptyGrid,
  EmptyInstances,
  EmptyData,
  EmptySearch,
  EmptyFailed,
} from './EmptyStates';

// Mobile Components
export { SwipeableMetrics } from './SwipeableMetrics';
export { TouchButton, TouchIconButton, FloatingActionButton } from './TouchButton';
