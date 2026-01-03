/**
 * PriceDisplay Component
 * 
 * Displays price with proper formatting, color coding, and optional change indicator.
 * Handles USD and INR formatting with appropriate precision.
 */

'use client';

import { cn } from '@/lib/utils';
import { memo, useMemo } from 'react';

export interface PriceDisplayProps {
  /** The price value to display */
  value: number;
  /** Currency for formatting (affects symbol and precision) */
  currency?: 'USD' | 'INR' | 'BTC';
  /** Show positive/negative color coding */
  colorCode?: boolean;
  /** Size variant */
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  /** Previous value for change calculation */
  previousValue?: number;
  /** Show change arrow */
  showChange?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Show + sign for positive values */
  showPlusSign?: boolean;
}

const SIZE_CLASSES = {
  xs: 'text-xs',
  sm: 'text-sm',
  md: 'text-base',
  lg: 'text-lg',
  xl: 'text-2xl font-semibold',
};

const CURRENCY_CONFIG = {
  USD: { symbol: '$', precision: 2, locale: 'en-US' },
  INR: { symbol: '₹', precision: 2, locale: 'en-IN' },
  BTC: { symbol: '₿', precision: 8, locale: 'en-US' },
};

export const PriceDisplay = memo(function PriceDisplay({
  value,
  currency = 'USD',
  colorCode = false,
  size = 'md',
  previousValue,
  showChange = false,
  className,
  showPlusSign = false,
}: PriceDisplayProps) {
  const config = CURRENCY_CONFIG[currency];
  
  const formattedValue = useMemo(() => {
    const absValue = Math.abs(value);
    
    // Format with locale
    const formatted = absValue.toLocaleString(config.locale, {
      minimumFractionDigits: currency === 'BTC' ? 2 : config.precision,
      maximumFractionDigits: config.precision,
    });
    
    // Add sign
    const sign = value < 0 ? '-' : (showPlusSign && value > 0 ? '+' : '');
    
    return `${sign}${config.symbol}${formatted}`;
  }, [value, currency, config, showPlusSign]);
  
  const change = useMemo(() => {
    if (!showChange || previousValue === undefined || previousValue === 0) {
      return null;
    }
    return value - previousValue;
  }, [value, previousValue, showChange]);
  
  const colorClass = useMemo(() => {
    if (!colorCode) return '';
    if (value > 0) return 'text-green-500 dark:text-green-400';
    if (value < 0) return 'text-red-500 dark:text-red-400';
    return 'text-muted-foreground';
  }, [value, colorCode]);
  
  return (
    <span className={cn(SIZE_CLASSES[size], colorClass, 'font-mono tabular-nums', className)}>
      {formattedValue}
      {change !== null && (
        <span className={cn(
          'ml-1 text-xs',
          change > 0 ? 'text-green-500' : change < 0 ? 'text-red-500' : 'text-muted-foreground'
        )}>
          {change > 0 ? '↑' : change < 0 ? '↓' : '→'}
        </span>
      )}
    </span>
  );
});

export default PriceDisplay;
