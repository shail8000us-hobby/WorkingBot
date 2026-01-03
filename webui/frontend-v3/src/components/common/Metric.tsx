/**
 * Metric Component
 * 
 * Displays a key metric with label, value, and optional trend.
 * Used throughout the dashboard for KPIs.
 */

'use client';

import { cn } from '@/lib/utils';
import { memo, useMemo } from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { PriceDisplay } from './PriceDisplay';

export interface MetricProps {
  /** Label for the metric */
  label: string;
  /** The metric value */
  value: number | string;
  /** Previous value for trend calculation */
  previousValue?: number;
  /** Format as currency */
  currency?: 'USD' | 'INR' | 'BTC';
  /** Format as percentage */
  percentage?: boolean;
  /** Show value with color coding */
  colorCode?: boolean;
  /** Optional icon */
  icon?: React.ReactNode;
  /** Size variant */
  size?: 'sm' | 'md' | 'lg';
  /** Show as card */
  asCard?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Subtitle text */
  subtitle?: string;
  /** Loading state */
  loading?: boolean;
}

const SIZE_CONFIG = {
  sm: {
    label: 'text-xs',
    value: 'text-lg',
    icon: 'h-4 w-4',
    card: 'p-3',
  },
  md: {
    label: 'text-sm',
    value: 'text-2xl',
    icon: 'h-5 w-5',
    card: 'p-4',
  },
  lg: {
    label: 'text-base',
    value: 'text-3xl',
    icon: 'h-6 w-6',
    card: 'p-6',
  },
};

export const Metric = memo(function Metric({
  label,
  value,
  previousValue,
  currency,
  percentage,
  colorCode = false,
  icon,
  size = 'md',
  asCard = false,
  className,
  subtitle,
  loading = false,
}: MetricProps) {
  const config = SIZE_CONFIG[size];
  
  const trend = useMemo(() => {
    if (typeof value !== 'number' || previousValue === undefined) {
      return null;
    }
    const change = value - previousValue;
    const percentChange = previousValue !== 0 
      ? (change / Math.abs(previousValue)) * 100 
      : 0;
    return {
      direction: change > 0 ? 'up' : change < 0 ? 'down' : 'neutral',
      change,
      percentChange,
    };
  }, [value, previousValue]);
  
  const formattedValue = useMemo(() => {
    if (loading) {
      return <span className="animate-pulse">---</span>;
    }
    
    if (typeof value === 'string') {
      return value;
    }
    
    if (currency) {
      return (
        <PriceDisplay 
          value={value} 
          currency={currency} 
          colorCode={colorCode}
          size={size === 'sm' ? 'md' : size === 'md' ? 'lg' : 'xl'}
          showPlusSign={colorCode}
        />
      );
    }
    
    if (percentage) {
      const sign = value > 0 ? '+' : '';
      return (
        <span className={cn(
          colorCode && value > 0 && 'text-green-500',
          colorCode && value < 0 && 'text-red-500',
        )}>
          {sign}{value.toFixed(2)}%
        </span>
      );
    }
    
    return value.toLocaleString();
  }, [value, currency, percentage, colorCode, size, loading]);
  
  const TrendIcon = trend?.direction === 'up' 
    ? TrendingUp 
    : trend?.direction === 'down' 
      ? TrendingDown 
      : Minus;
  
  const trendColor = trend?.direction === 'up'
    ? 'text-green-500'
    : trend?.direction === 'down'
      ? 'text-red-500'
      : 'text-muted-foreground';
  
  const content = (
    <div className={cn('space-y-1', className)}>
      {/* Label Row */}
      <div className="flex items-center gap-2">
        {icon && (
          <span className={cn('text-muted-foreground', config.icon)}>
            {icon}
          </span>
        )}
        <span className={cn('text-muted-foreground font-medium', config.label)}>
          {label}
        </span>
      </div>
      
      {/* Value Row */}
      <div className="flex items-baseline gap-2">
        <span className={cn('font-bold', config.value)}>
          {formattedValue}
        </span>
        
        {/* Trend Indicator */}
        {trend && (
          <div className={cn('flex items-center gap-1', trendColor)}>
            <TrendIcon className="h-4 w-4" />
            <span className="text-sm">
              {Math.abs(trend.percentChange).toFixed(1)}%
            </span>
          </div>
        )}
      </div>
      
      {/* Subtitle */}
      {subtitle && (
        <p className="text-xs text-muted-foreground">{subtitle}</p>
      )}
    </div>
  );
  
  if (asCard) {
    return (
      <Card className={className}>
        <CardContent className={config.card}>
          {content}
        </CardContent>
      </Card>
    );
  }
  
  return content;
});

/**
 * MetricGrid Component
 * 
 * Responsive grid layout for multiple metrics.
 */
export interface MetricGridProps {
  children: React.ReactNode;
  columns?: 2 | 3 | 4 | 5;
  className?: string;
}

export const MetricGrid = memo(function MetricGrid({
  children,
  columns = 4,
  className,
}: MetricGridProps) {
  const gridClass = {
    2: 'grid-cols-1 sm:grid-cols-2',
    3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
    4: 'grid-cols-2 lg:grid-cols-4',
    5: 'grid-cols-2 lg:grid-cols-5',
  };
  
  return (
    <div className={cn('grid gap-4', gridClass[columns], className)}>
      {children}
    </div>
  );
});

export default Metric;
