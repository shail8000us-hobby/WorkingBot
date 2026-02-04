/**
 * StatusBadge Component
 * 
 * Displays session/position status with appropriate styling.
 * 
 * Per Implementation Plan: Section 2.3 - shared/StatusBadge.js
 * Created: February 3, 2026
 */

import React from 'react';

/**
 * Status configurations with colors and icons
 */
const STATUS_CONFIG = {
  active: {
    bg: 'bg-green-100',
    text: 'text-green-800',
    border: 'border-green-200',
    dot: 'bg-green-500',
    icon: '●',
    pulse: true,
  },
  running: {
    bg: 'bg-green-100',
    text: 'text-green-800',
    border: 'border-green-200',
    dot: 'bg-green-500',
    icon: '●',
    pulse: true,
  },
  paused: {
    bg: 'bg-yellow-100',
    text: 'text-yellow-800',
    border: 'border-yellow-200',
    dot: 'bg-yellow-500',
    icon: '⏸',
    pulse: false,
  },
  stopped: {
    bg: 'bg-gray-100',
    text: 'text-gray-600',
    border: 'border-gray-200',
    dot: 'bg-gray-400',
    icon: '■',
    pulse: false,
  },
  completed: {
    bg: 'bg-blue-100',
    text: 'text-blue-800',
    border: 'border-blue-200',
    dot: 'bg-blue-500',
    icon: '✓',
    pulse: false,
  },
  error: {
    bg: 'bg-red-100',
    text: 'text-red-800',
    border: 'border-red-200',
    dot: 'bg-red-500',
    icon: '✕',
    pulse: false,
  },
  warning: {
    bg: 'bg-orange-100',
    text: 'text-orange-800',
    border: 'border-orange-200',
    dot: 'bg-orange-500',
    icon: '⚠',
    pulse: true,
  },
  danger: {
    bg: 'bg-red-100',
    text: 'text-red-800',
    border: 'border-red-200',
    dot: 'bg-red-500',
    icon: '⚠',
    pulse: true,
  },
  safe: {
    bg: 'bg-green-100',
    text: 'text-green-800',
    border: 'border-green-200',
    dot: 'bg-green-500',
    icon: '✓',
    pulse: false,
  },
  pending: {
    bg: 'bg-purple-100',
    text: 'text-purple-800',
    border: 'border-purple-200',
    dot: 'bg-purple-500',
    icon: '○',
    pulse: true,
  },
  triggered: {
    bg: 'bg-red-100',
    text: 'text-red-800',
    border: 'border-red-200',
    dot: 'bg-red-500',
    icon: '⚡',
    pulse: true,
  },
  default: {
    bg: 'bg-gray-100',
    text: 'text-gray-600',
    border: 'border-gray-200',
    dot: 'bg-gray-400',
    icon: '○',
    pulse: false,
  },
};

/**
 * Size configurations
 */
const SIZE_CONFIG = {
  xs: 'px-1.5 py-0.5 text-xs',
  sm: 'px-2 py-0.5 text-sm',
  md: 'px-2.5 py-1 text-sm',
  lg: 'px-3 py-1.5 text-base',
};

/**
 * StatusBadge Component
 * 
 * @param {string} status - Status key
 * @param {string} label - Optional custom label (uses status if not provided)
 * @param {string} size - Badge size: 'xs', 'sm', 'md', 'lg'
 * @param {boolean} showDot - Show status dot indicator
 * @param {boolean} showIcon - Show status icon
 * @param {string} className - Additional CSS classes
 */
const StatusBadge = ({
  status = 'default',
  label,
  size = 'sm',
  showDot = true,
  showIcon = false,
  className = '',
}) => {
  const config = STATUS_CONFIG[status.toLowerCase()] || STATUS_CONFIG.default;
  const sizeClass = SIZE_CONFIG[size] || SIZE_CONFIG.sm;
  
  const displayLabel = label || status.charAt(0).toUpperCase() + status.slice(1);

  return (
    <span
      className={`
        inline-flex items-center gap-1.5 rounded-full font-medium
        ${config.bg} ${config.text} border ${config.border}
        ${sizeClass}
        ${className}
      `}
    >
      {showDot && (
        <span
          className={`
            w-2 h-2 rounded-full
            ${config.dot}
            ${config.pulse ? 'animate-pulse' : ''}
          `}
        />
      )}
      {showIcon && (
        <span className="text-xs">{config.icon}</span>
      )}
      {displayLabel}
    </span>
  );
};

/**
 * Zone status badge with specific styling
 */
export const ZoneBadge = ({ zone, distance, className = '' }) => {
  const zoneConfig = {
    safe: { label: 'Safe Zone', status: 'safe' },
    profit: { label: 'Profit Zone', status: 'safe' },
    warning: { label: 'Warning Zone', status: 'warning' },
    danger: { label: 'Max Loss Zone', status: 'danger' },
    breached: { label: 'BREACHED', status: 'triggered' },
    upper: { label: 'Upper Max Loss', status: 'danger' },
    lower: { label: 'Lower Max Loss', status: 'danger' },
  };

  const config = zoneConfig[zone] || { label: zone, status: 'default' };

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <StatusBadge status={config.status} label={config.label} size="md" />
      {distance !== undefined && distance !== null && (
        <span className="text-sm text-gray-500">
          {distance > 0 ? '+' : ''}{distance.toFixed(0)} pts away
        </span>
      )}
    </div>
  );
};

/**
 * Session status badge with context
 */
export const SessionStatusBadge = ({ session, className = '' }) => {
  if (!session) {
    return <StatusBadge status="stopped" label="No Session" className={className} />;
  }

  const status = session.status || session.session_status || 'unknown';
  const triggers = session.trigger_count || 0;

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <StatusBadge status={status} showDot />
      {triggers > 0 && (
        <span className="text-xs text-gray-500">
          ({triggers} trigger{triggers !== 1 ? 's' : ''})
        </span>
      )}
    </div>
  );
};

export default StatusBadge;
