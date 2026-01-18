/**
 * Chart Animations Wrapper
 * 
 * Phase 3: Enhanced chart animations and transitions
 */

'use client';

import { useEffect, useRef, ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface AnimatedChartProps {
  children: ReactNode;
  delay?: number;
  className?: string;
}

export function AnimatedChart({ children, delay = 0, className }: AnimatedChartProps) {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setTimeout(() => {
              entry.target.classList.add('animate-in');
            }, delay);
          }
        });
      },
      { threshold: 0.1 }
    );

    if (chartRef.current) {
      observer.observe(chartRef.current);
    }

    return () => observer.disconnect();
  }, [delay]);

  return (
    <div
      ref={chartRef}
      className={cn('opacity-0 transition-all duration-700', className)}
      style={{
        '--delay': `${delay}ms`,
      } as React.CSSProperties}
    >
      {children}
    </div>
  );
}

interface LineChartConfig {
  animate?: boolean;
  gradient?: boolean;
  glow?: boolean;
}

export function enhanceChartLine(config: LineChartConfig = {}) {
  const { animate = true, gradient = false, glow = false } = config;
  
  const classes = ['chart-line'];
  
  if (animate) classes.push('chart-line-animate');
  if (gradient) classes.push('chart-gradient-fill');
  if (glow) classes.push('chart-line-glow');
  
  return classes.join(' ');
}

interface MetricCardProps {
  label: string;
  value: number | string;
  change?: number;
  trend?: 'up' | 'down' | 'neutral';
  format?: 'number' | 'currency' | 'percentage';
  animated?: boolean;
  className?: string;
}

export function AnimatedMetricCard({
  label,
  value,
  change,
  trend = 'neutral',
  format = 'number',
  animated = true,
  className,
}: MetricCardProps) {
  const trendColors = {
    up: 'text-green-600 dark:text-green-400',
    down: 'text-red-600 dark:text-red-400',
    neutral: 'text-muted-foreground',
  };

  const formatValue = (val: number | string) => {
    if (typeof val === 'string') return val;
    
    switch (format) {
      case 'currency':
        return `$${val.toLocaleString()}`;
      case 'percentage':
        return `${val.toFixed(2)}%`;
      default:
        return val.toLocaleString();
    }
  };

  return (
    <div className={cn('p-4 rounded-lg bg-muted/50 scale-in', className)}>
      <p className="text-sm text-muted-foreground mb-1">{label}</p>
      <div className="flex items-baseline gap-2">
        <p className={cn(
          'text-2xl font-bold tabular-nums',
          animated && 'metric-counter'
        )}>
          {formatValue(value)}
        </p>
        {change !== undefined && (
          <span className={cn('text-sm font-medium', trendColors[trend])}>
            {change > 0 ? '+' : ''}{change.toFixed(2)}%
          </span>
        )}
      </div>
    </div>
  );
}

// SVG Filter Definitions for Charts
export function ChartFilters() {
  return (
    <svg width="0" height="0" style={{ position: 'absolute' }}>
      <defs>
        {/* Gradient for success */}
        <linearGradient id="gradient-success" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="rgb(16, 185, 129)" stopOpacity="0.8" />
          <stop offset="100%" stopColor="rgb(16, 185, 129)" stopOpacity="0.1" />
        </linearGradient>

        {/* Gradient for error */}
        <linearGradient id="gradient-error" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="rgb(239, 68, 68)" stopOpacity="0.8" />
          <stop offset="100%" stopColor="rgb(239, 68, 68)" stopOpacity="0.1" />
        </linearGradient>

        {/* Gradient for primary */}
        <linearGradient id="gradient-primary" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="rgb(99, 102, 241)" stopOpacity="0.8" />
          <stop offset="100%" stopColor="rgb(99, 102, 241)" stopOpacity="0.1" />
        </linearGradient>

        {/* Glow filter */}
        <filter id="glow">
          <feGaussianBlur stdDeviation="2" result="coloredBlur" />
          <feMerge>
            <feMergeNode in="coloredBlur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>

        {/* Drop shadow */}
        <filter id="drop-shadow">
          <feGaussianBlur in="SourceAlpha" stdDeviation="2" />
          <feOffset dx="0" dy="2" result="offsetblur" />
          <feComponentTransfer>
            <feFuncA type="linear" slope="0.3" />
          </feComponentTransfer>
          <feMerge>
            <feMergeNode />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
    </svg>
  );
}

export default AnimatedChart;
