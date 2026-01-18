import React from 'react';
import clsx from 'clsx';
import '../../styles/animations.css';

/**
 * LoadingSkeleton Component
 * Animated placeholder for loading states
 * 
 * Created: January 18, 2026 (Migrated to TypeScript)
 * Safe: Pure UI component, no functional changes
 */

type SkeletonVariant = 'text' | 'title' | 'subtitle' | 'card' | 'button' | 'avatar' | 'badge' | 'metric' | 'chart';

interface LoadingSkeletonProps {
  variant?: SkeletonVariant;
  width?: string | number;
  height?: string | number;
  className?: string;
  count?: number;
  circle?: boolean;
  borderRadius?: string | number;
}

const LoadingSkeleton: React.FC<LoadingSkeletonProps> = ({
  variant = 'text',
  width,
  height,
  className,
  count = 1,
  circle = false,
  borderRadius
}) => {
  const baseClasses = 'loading-shimmer rounded';
  
  const variantStyles: Record<SkeletonVariant, string> = {
    text: 'h-4 w-full mb-2',
    title: 'h-6 w-3/4 mb-3',
    subtitle: 'h-4 w-1/2 mb-2',
    card: 'h-32 w-full',
    button: 'h-10 w-24',
    avatar: 'h-10 w-10 rounded-full',
    badge: 'h-6 w-16 rounded-full',
    metric: 'h-16 w-full',
    chart: 'h-64 w-full'
  };
  
  const variantClass = variantStyles[variant] || variantStyles.text;
  
  const style: React.CSSProperties = {
    width: width || undefined,
    height: height || undefined,
    borderRadius: circle ? '50%' : borderRadius || undefined
  };
  
  return (
    <>
      {Array.from({ length: count }).map((_, index) => (
        <div
          key={index}
          className={clsx(baseClasses, variantClass, className)}
          style={style}
          aria-label="Loading..."
        />
      ))}
    </>
  );
};

// Preset skeleton layouts
export const CardSkeleton: React.FC = () => (
  <div className="glass-card p-5 space-y-4">
    <LoadingSkeleton variant="title" />
    <LoadingSkeleton variant="subtitle" />
    <div className="space-y-2">
      <LoadingSkeleton variant="text" count={3} />
    </div>
    <div className="flex gap-2">
      <LoadingSkeleton variant="button" />
      <LoadingSkeleton variant="button" />
    </div>
  </div>
);

export const MetricSkeleton: React.FC = () => (
  <div className="glass-card p-4 space-y-2">
    <LoadingSkeleton variant="badge" width="60%" />
    <LoadingSkeleton variant="metric" />
    <LoadingSkeleton variant="text" width="40%" />
  </div>
);

interface TableRowSkeletonProps {
  columns?: number;
}

export const TableRowSkeleton: React.FC<TableRowSkeletonProps> = ({ columns = 4 }) => (
  <div className="flex gap-4 py-3 border-b border-slate-700/30">
    {Array.from({ length: columns }).map((_, i) => (
      <LoadingSkeleton key={i} variant="text" width={`${100 / columns}%`} />
    ))}
  </div>
);

export const ChartSkeleton: React.FC = () => (
  <div className="glass-card p-5 space-y-4">
    <div className="flex justify-between items-center">
      <LoadingSkeleton variant="title" width="30%" />
      <div className="flex gap-2">
        <LoadingSkeleton variant="badge" />
        <LoadingSkeleton variant="badge" />
      </div>
    </div>
    <LoadingSkeleton variant="chart" />
  </div>
);

export default LoadingSkeleton;
