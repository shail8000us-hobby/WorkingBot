/**
 * MetricCard Component
 * 
 * Displays key metrics with label, value, and optional trend indicator.
 * 
 * Per Implementation Plan: Section 2.3 - shared/MetricCard.js
 * Created: February 3, 2026
 */

import React from 'react';

/**
 * Trend indicator component
 */
const TrendIndicator = ({ trend, value }) => {
  if (!trend || trend === 'neutral') return null;

  const isUp = trend === 'up' || value > 0;
  const isDown = trend === 'down' || value < 0;

  return (
    <span
      className={`
        inline-flex items-center text-xs font-medium
        ${isUp ? 'text-green-600' : ''}
        ${isDown ? 'text-red-600' : ''}
        ${!isUp && !isDown ? 'text-gray-500' : ''}
      `}
    >
      {isUp && '↑'}
      {isDown && '↓'}
      {value !== undefined && (
        <span className="ml-0.5">
          {Math.abs(value).toFixed(1)}%
        </span>
      )}
    </span>
  );
};

/**
 * Size configurations
 */
const SIZE_CONFIG = {
  sm: {
    container: 'p-3',
    label: 'text-xs',
    value: 'text-lg',
    subtitle: 'text-xs',
  },
  md: {
    container: 'p-4',
    label: 'text-sm',
    value: 'text-xl',
    subtitle: 'text-xs',
  },
  lg: {
    container: 'p-5',
    label: 'text-sm',
    value: 'text-2xl',
    subtitle: 'text-sm',
  },
};

/**
 * MetricCard Component
 * 
 * @param {string} label - Metric label
 * @param {string|number} value - Main value to display
 * @param {string} unit - Unit suffix (e.g., 'pts', '%', '₹')
 * @param {string} prefix - Value prefix (e.g., '₹', '+', '-')
 * @param {string} subtitle - Additional context below value
 * @param {string} trend - Trend direction: 'up', 'down', 'neutral'
 * @param {number} trendValue - Trend percentage value
 * @param {string} size - Card size: 'sm', 'md', 'lg'
 * @param {string} variant - Card variant: 'default', 'positive', 'negative', 'warning'
 * @param {React.Node} icon - Optional icon element
 * @param {string} className - Additional CSS classes
 * @param {function} onClick - Optional click handler
 */
const MetricCard = ({
  label,
  value,
  unit,
  prefix,
  subtitle,
  trend,
  trendValue,
  size = 'md',
  variant = 'default',
  icon,
  className = '',
  onClick,
}) => {
  const sizeConfig = SIZE_CONFIG[size] || SIZE_CONFIG.md;

  const variantStyles = {
    default: 'bg-white border-gray-200',
    positive: 'bg-green-50 border-green-200',
    negative: 'bg-red-50 border-red-200',
    warning: 'bg-yellow-50 border-yellow-200',
    info: 'bg-blue-50 border-blue-200',
  };

  const valueStyles = {
    default: 'text-gray-900',
    positive: 'text-green-700',
    negative: 'text-red-700',
    warning: 'text-yellow-700',
    info: 'text-blue-700',
  };

  // Format value
  const formatValue = (val) => {
    if (val === null || val === undefined) return '-';
    if (typeof val === 'number') {
      if (Math.abs(val) >= 1000000) {
        return (val / 1000000).toFixed(2) + 'M';
      }
      if (Math.abs(val) >= 1000) {
        return (val / 1000).toFixed(1) + 'K';
      }
      return val.toLocaleString(undefined, { maximumFractionDigits: 2 });
    }
    return val;
  };

  return (
    <div
      className={`
        rounded-lg border shadow-sm
        ${variantStyles[variant] || variantStyles.default}
        ${sizeConfig.container}
        ${onClick ? 'cursor-pointer hover:shadow-md transition-shadow' : ''}
        ${className}
      `}
      onClick={onClick}
    >
      {/* Header with label and icon */}
      <div className="flex items-center justify-between mb-1">
        <span className={`font-medium text-gray-500 ${sizeConfig.label}`}>
          {label}
        </span>
        {icon && <span className="text-gray-400">{icon}</span>}
      </div>

      {/* Value row */}
      <div className="flex items-baseline gap-2">
        <span
          className={`
            font-bold
            ${sizeConfig.value}
            ${valueStyles[variant] || valueStyles.default}
          `}
        >
          {prefix}
          {formatValue(value)}
          {unit && <span className="text-sm font-normal ml-0.5">{unit}</span>}
        </span>
        
        <TrendIndicator trend={trend} value={trendValue} />
      </div>

      {/* Subtitle */}
      {subtitle && (
        <p className={`mt-1 text-gray-500 ${sizeConfig.subtitle}`}>
          {subtitle}
        </p>
      )}
    </div>
  );
};

/**
 * Metric card for P&L display
 */
export const PnLCard = ({ pnl, unrealizedPnl, className = '' }) => {
  const total = (pnl || 0) + (unrealizedPnl || 0);
  const variant = total >= 0 ? 'positive' : 'negative';

  return (
    <MetricCard
      label="Total P&L"
      value={total}
      prefix={total >= 0 ? '+₹' : '-₹'}
      variant={variant}
      subtitle={unrealizedPnl ? `Unrealized: ₹${unrealizedPnl.toFixed(2)}` : undefined}
      className={className}
    />
  );
};

/**
 * Metric card for price distance
 */
export const DistanceCard = ({ 
  label = 'Distance to Max Loss', 
  distance, 
  percent, 
  direction,
  className = '' 
}) => {
  const variant = distance < 100 ? 'negative' : distance < 300 ? 'warning' : 'default';
  
  return (
    <MetricCard
      label={label}
      value={Math.abs(distance)}
      unit="pts"
      prefix={direction === 'above' ? '↑' : direction === 'below' ? '↓' : ''}
      variant={variant}
      subtitle={percent ? `${percent.toFixed(2)}% away` : undefined}
      className={className}
    />
  );
};

/**
 * Metric card grid for multiple metrics
 */
export const MetricCardGrid = ({ children, cols = 4, className = '' }) => {
  return (
    <div
      className={`
        grid gap-4
        grid-cols-2
        sm:grid-cols-${Math.min(cols, 3)}
        lg:grid-cols-${cols}
        ${className}
      `}
    >
      {children}
    </div>
  );
};

export default MetricCard;
