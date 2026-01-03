/**
 * Loading Skeletons
 * 
 * Skeleton components for different UI sections
 * to show during data loading.
 */

'use client';

import { cn } from '@/lib/utils';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent, CardHeader } from '@/components/ui/card';

/**
 * Generic skeleton wrapper with animation
 */
export function SkeletonCard({ className }: { className?: string }) {
  return (
    <Card className={cn('overflow-hidden', className)}>
      <CardHeader className="pb-2">
        <Skeleton className="h-5 w-1/3" />
      </CardHeader>
      <CardContent className="space-y-3">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-4 w-4/5" />
      </CardContent>
    </Card>
  );
}

/**
 * Skeleton for metric cards (like in dashboard)
 */
export function SkeletonMetricCard({ className }: { className?: string }) {
  return (
    <Card className={cn('overflow-hidden', className)}>
      <CardContent className="p-4">
        <div className="flex justify-between items-start">
          <div className="space-y-2 flex-1">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-7 w-24" />
          </div>
          <Skeleton className="h-8 w-8 rounded-md" />
        </div>
        <Skeleton className="h-3 w-16 mt-2" />
      </CardContent>
    </Card>
  );
}

/**
 * Skeleton for order rows
 */
export function SkeletonOrderRow({ className }: { className?: string }) {
  return (
    <div className={cn('flex items-center gap-4 p-3 border-b', className)}>
      <Skeleton className="h-6 w-14 rounded-full" />
      <div className="flex-1 space-y-1">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-3 w-16" />
      </div>
      <Skeleton className="h-4 w-20" />
      <Skeleton className="h-4 w-16" />
      <Skeleton className="h-8 w-8 rounded" />
    </div>
  );
}

/**
 * Skeleton for position cards
 */
export function SkeletonPositionCard({ className }: { className?: string }) {
  return (
    <Card className={cn('overflow-hidden', className)}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Skeleton className="h-6 w-16 rounded-full" />
            <Skeleton className="h-5 w-24" />
          </div>
          <Skeleton className="h-6 w-20" />
        </div>
        <div className="grid grid-cols-3 gap-2">
          <div className="space-y-1">
            <Skeleton className="h-3 w-12" />
            <Skeleton className="h-4 w-16" />
          </div>
          <div className="space-y-1">
            <Skeleton className="h-3 w-12" />
            <Skeleton className="h-4 w-16" />
          </div>
          <div className="space-y-1">
            <Skeleton className="h-3 w-12" />
            <Skeleton className="h-4 w-16" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * Skeleton for grid visualization
 */
export function SkeletonGrid({ className }: { className?: string }) {
  return (
    <Card className={cn('overflow-hidden', className)}>
      <CardHeader className="pb-2">
        <div className="flex justify-between items-center">
          <Skeleton className="h-5 w-28" />
          <Skeleton className="h-8 w-24" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="flex items-center gap-2">
              <Skeleton className="h-6 w-16" />
              <Skeleton className="h-4 flex-1" />
              <Skeleton className="h-5 w-12 rounded-full" />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * Skeleton for chart
 */
export function SkeletonChart({ className }: { className?: string }) {
  return (
    <Card className={cn('overflow-hidden', className)}>
      <CardHeader className="pb-2">
        <Skeleton className="h-5 w-32" />
      </CardHeader>
      <CardContent>
        <div className="h-[200px] flex items-end justify-between gap-1">
          {Array.from({ length: 12 }).map((_, i) => (
            <Skeleton 
              key={i} 
              className="flex-1" 
              style={{ height: `${20 + Math.random() * 60}%` }}
            />
          ))}
        </div>
        <div className="flex justify-between mt-2">
          <Skeleton className="h-3 w-8" />
          <Skeleton className="h-3 w-8" />
          <Skeleton className="h-3 w-8" />
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * Skeleton for table
 */
interface SkeletonTableProps {
  rows?: number;
  columns?: number;
  className?: string;
}

export function SkeletonTable({ rows = 5, columns = 4, className }: SkeletonTableProps) {
  return (
    <div className={cn('space-y-2', className)}>
      {/* Header */}
      <div className="flex gap-4 p-3 border-b">
        {Array.from({ length: columns }).map((_, i) => (
          <Skeleton key={i} className="h-4 flex-1" />
        ))}
      </div>
      {/* Rows */}
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4 p-3 border-b">
          {Array.from({ length: columns }).map((_, j) => (
            <Skeleton key={j} className="h-4 flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}

/**
 * Skeleton for dashboard grid
 */
export function SkeletonDashboard() {
  return (
    <div className="space-y-4">
      {/* Metrics row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <SkeletonMetricCard />
        <SkeletonMetricCard />
        <SkeletonMetricCard />
        <SkeletonMetricCard />
      </div>
      
      {/* Main content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <SkeletonChart />
        <SkeletonGrid />
      </div>
      
      {/* Orders */}
      <div className="space-y-2">
        <SkeletonOrderRow />
        <SkeletonOrderRow />
        <SkeletonOrderRow />
      </div>
    </div>
  );
}

export default {
  SkeletonCard,
  SkeletonMetricCard,
  SkeletonOrderRow,
  SkeletonPositionCard,
  SkeletonGrid,
  SkeletonChart,
  SkeletonTable,
  SkeletonDashboard,
};
