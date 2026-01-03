/**
 * LoadingState Component
 * 
 * Consistent loading indicators throughout the app.
 */

'use client';

import { cn } from '@/lib/utils';
import { memo } from 'react';
import { Loader2 } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';

export interface LoadingSpinnerProps {
  /** Size variant */
  size?: 'sm' | 'md' | 'lg';
  /** Optional label */
  label?: string;
  /** Additional CSS classes */
  className?: string;
}

const SIZE_CLASSES = {
  sm: 'h-4 w-4',
  md: 'h-6 w-6',
  lg: 'h-8 w-8',
};

export const LoadingSpinner = memo(function LoadingSpinner({
  size = 'md',
  label,
  className,
}: LoadingSpinnerProps) {
  return (
    <div className={cn('flex items-center gap-2', className)}>
      <Loader2 className={cn('animate-spin text-muted-foreground', SIZE_CLASSES[size])} />
      {label && <span className="text-muted-foreground">{label}</span>}
    </div>
  );
});

/**
 * LoadingCard Component
 * 
 * Skeleton loading state for cards.
 */
export interface LoadingCardProps {
  /** Number of lines to show */
  lines?: number;
  /** Show header skeleton */
  showHeader?: boolean;
  /** Additional CSS classes */
  className?: string;
}

export const LoadingCard = memo(function LoadingCard({
  lines = 3,
  showHeader = true,
  className,
}: LoadingCardProps) {
  return (
    <div className={cn('space-y-3 p-4', className)}>
      {showHeader && (
        <Skeleton className="h-5 w-1/3" />
      )}
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton 
          key={i} 
          className="h-4" 
          style={{ width: `${85 - i * 15}%` }} 
        />
      ))}
    </div>
  );
});

/**
 * LoadingTable Component
 * 
 * Skeleton loading state for tables.
 */
export interface LoadingTableProps {
  /** Number of rows */
  rows?: number;
  /** Number of columns */
  columns?: number;
  /** Additional CSS classes */
  className?: string;
}

export const LoadingTable = memo(function LoadingTable({
  rows = 5,
  columns = 4,
  className,
}: LoadingTableProps) {
  return (
    <div className={cn('space-y-2', className)}>
      {/* Header */}
      <div className="flex gap-4 pb-2 border-b">
        {Array.from({ length: columns }).map((_, i) => (
          <Skeleton key={i} className="h-4 flex-1" />
        ))}
      </div>
      
      {/* Rows */}
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={rowIndex} className="flex gap-4 py-2">
          {Array.from({ length: columns }).map((_, colIndex) => (
            <Skeleton key={colIndex} className="h-4 flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
});

/**
 * FullPageLoading Component
 * 
 * Full page loading overlay.
 */
export interface FullPageLoadingProps {
  /** Loading message */
  message?: string;
}

export const FullPageLoading = memo(function FullPageLoading({
  message = 'Loading...',
}: FullPageLoadingProps) {
  return (
    <div className="fixed inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="flex flex-col items-center gap-4">
        <Loader2 className="h-12 w-12 animate-spin text-primary" />
        <p className="text-lg text-muted-foreground">{message}</p>
      </div>
    </div>
  );
});

export default LoadingSpinner;
