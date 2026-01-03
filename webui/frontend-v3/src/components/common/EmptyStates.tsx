/**
 * Empty State Components
 * 
 * Display meaningful empty states when there's no data.
 * Each variant is tailored for specific data types.
 */

'use client';

import { 
  PackageOpen, 
  ShoppingCart, 
  TrendingUp, 
  Activity,
  Bot,
  RefreshCw,
  Plus,
  AlertCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  secondaryAction?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  secondaryAction,
  className,
  size = 'md',
}: EmptyStateProps) {
  const sizeClasses = {
    sm: 'py-6',
    md: 'py-12',
    lg: 'py-20',
  };

  const iconSizes = {
    sm: 'h-8 w-8',
    md: 'h-12 w-12',
    lg: 'h-16 w-16',
  };

  const titleSizes = {
    sm: 'text-sm',
    md: 'text-base',
    lg: 'text-lg',
  };

  return (
    <div className={cn(
      'flex flex-col items-center justify-center text-center',
      sizeClasses[size],
      className
    )}>
      {icon && (
        <div className={cn(
          'text-muted-foreground/50 mb-4',
          iconSizes[size]
        )}>
          {icon}
        </div>
      )}
      <h3 className={cn(
        'font-medium text-muted-foreground',
        titleSizes[size]
      )}>
        {title}
      </h3>
      {description && (
        <p className="text-sm text-muted-foreground/70 mt-1 max-w-sm">
          {description}
        </p>
      )}
      {(action || secondaryAction) && (
        <div className="flex gap-2 mt-4">
          {secondaryAction && (
            <Button
              variant="outline"
              size="sm"
              onClick={secondaryAction.onClick}
            >
              {secondaryAction.label}
            </Button>
          )}
          {action && (
            <Button
              size="sm"
              onClick={action.onClick}
            >
              {action.label}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Empty state for no orders
 */
interface EmptyOrdersProps {
  onRefresh?: () => void;
  className?: string;
}

export function EmptyOrders({ onRefresh, className }: EmptyOrdersProps) {
  return (
    <EmptyState
      icon={<ShoppingCart className="h-12 w-12" />}
      title="No Orders"
      description="There are no orders to display. New orders will appear here when the bot places trades."
      action={onRefresh ? { label: 'Refresh', onClick: onRefresh } : undefined}
      className={className}
    />
  );
}

/**
 * Empty state for no positions
 */
interface EmptyPositionsProps {
  onRefresh?: () => void;
  className?: string;
}

export function EmptyPositions({ onRefresh, className }: EmptyPositionsProps) {
  return (
    <EmptyState
      icon={<TrendingUp className="h-12 w-12" />}
      title="No Open Positions"
      description="You don't have any open positions. Positions will appear here when buy orders are filled."
      action={onRefresh ? { label: 'Refresh', onClick: onRefresh } : undefined}
      className={className}
    />
  );
}

/**
 * Empty state for no grid levels
 */
interface EmptyGridProps {
  onConfigure?: () => void;
  className?: string;
}

export function EmptyGrid({ onConfigure, className }: EmptyGridProps) {
  return (
    <EmptyState
      icon={<Activity className="h-12 w-12" />}
      title="No Grid Levels"
      description="The trading grid hasn't been configured yet. Set up your grid parameters to start trading."
      action={onConfigure ? { label: 'Configure Grid', onClick: onConfigure } : undefined}
      className={className}
    />
  );
}

/**
 * Empty state for no instances
 */
interface EmptyInstancesProps {
  onAdd?: () => void;
  className?: string;
}

export function EmptyInstances({ onAdd, className }: EmptyInstancesProps) {
  return (
    <EmptyState
      icon={<Bot className="h-12 w-12" />}
      title="No Bot Instances"
      description="No trading bot instances are running. Start a new instance to begin automated trading."
      action={onAdd ? { label: 'Add Instance', onClick: onAdd } : undefined}
      className={className}
    />
  );
}

/**
 * Empty state for no data (generic)
 */
interface EmptyDataProps {
  dataType?: string;
  onRefresh?: () => void;
  className?: string;
}

export function EmptyData({ dataType = 'data', onRefresh, className }: EmptyDataProps) {
  return (
    <EmptyState
      icon={<PackageOpen className="h-12 w-12" />}
      title={`No ${dataType}`}
      description={`There is no ${dataType.toLowerCase()} to display at this time.`}
      action={onRefresh ? { 
        label: 'Refresh', 
        onClick: onRefresh 
      } : undefined}
      className={className}
    />
  );
}

/**
 * Empty state for search results
 */
interface EmptySearchProps {
  query?: string;
  onClear?: () => void;
  className?: string;
}

export function EmptySearch({ query, onClear, className }: EmptySearchProps) {
  return (
    <EmptyState
      icon={<AlertCircle className="h-12 w-12" />}
      title="No Results Found"
      description={query 
        ? `No results match "${query}". Try adjusting your search terms.`
        : 'No results found. Try adjusting your filters.'
      }
      action={onClear ? { label: 'Clear Search', onClick: onClear } : undefined}
      className={className}
    />
  );
}

/**
 * Empty state for loading failed
 */
interface EmptyFailedProps {
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export function EmptyFailed({ message, onRetry, className }: EmptyFailedProps) {
  return (
    <EmptyState
      icon={<AlertCircle className="h-12 w-12 text-destructive" />}
      title="Failed to Load"
      description={message || 'Something went wrong while loading data.'}
      action={onRetry ? { label: 'Try Again', onClick: onRetry } : undefined}
      className={className}
    />
  );
}

export default {
  EmptyState,
  EmptyOrders,
  EmptyPositions,
  EmptyGrid,
  EmptyInstances,
  EmptyData,
  EmptySearch,
  EmptyFailed,
};
