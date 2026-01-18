/**
 * StatusBadge Component
 * 
 * Visual indicator for various system states.
 * Supports pulse animation for active states.
 */

'use client';

import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { memo } from 'react';

export type StatusType = 
  | 'running' 
  | 'stopped' 
  | 'warning' 
  | 'error' 
  | 'success' 
  | 'pending'
  | 'connected'
  | 'disconnected'
  | 'reconnecting'
  | 'healthy'
  | 'degraded'
  | 'unhealthy'
  | 'long'
  | 'short';

export interface StatusBadgeProps {
  /** The status to display */
  status: StatusType;
  /** Custom label (defaults to status name) */
  label?: string;
  /** Show pulse animation for active states */
  pulse?: boolean;
  /** Size variant */
  size?: 'sm' | 'md' | 'lg';
  /** Additional CSS classes */
  className?: string;
}

const STATUS_CONFIG: Record<StatusType, { 
  color: string; 
  bg: string; 
  border: string;
  glow: string;
  label: string;
  pulse?: boolean;
}> = {
  running: { 
    color: 'text-green-700 dark:text-green-400', 
    bg: 'bg-green-100 dark:bg-green-900/40',
    border: 'border-green-400/70',
    glow: 'shadow-lg shadow-green-500/20',
    label: 'Running',
    pulse: true,
  },
  stopped: { 
    color: 'text-gray-700 dark:text-gray-400', 
    bg: 'bg-gray-100 dark:bg-gray-800',
    border: 'border-gray-400/50',
    glow: '',
    label: 'Stopped',
  },
  warning: { 
    color: 'text-yellow-700 dark:text-yellow-400', 
    bg: 'bg-yellow-100 dark:bg-yellow-900/40',
    border: 'border-yellow-400/70',
    glow: 'shadow-lg shadow-yellow-500/20',
    label: 'Warning',
  },
  error: { 
    color: 'text-red-700 dark:text-red-400', 
    bg: 'bg-red-100 dark:bg-red-900/40',
    border: 'border-red-400/70',
    glow: 'shadow-lg shadow-red-500/20',
    label: 'Error',
  },
  success: { 
    color: 'text-green-700 dark:text-green-400', 
    bg: 'bg-green-100 dark:bg-green-900/40',
    border: 'border-green-400/70',
    glow: 'shadow-lg shadow-green-500/20',
    label: 'Success',
  },
  pending: { 
    color: 'text-blue-700 dark:text-blue-400', 
    bg: 'bg-blue-100 dark:bg-blue-900/40',
    border: 'border-blue-400/70',
    glow: 'shadow-lg shadow-blue-500/20',
    label: 'Pending',
    pulse: true,
  },
  connected: { 
    color: 'text-green-700 dark:text-green-400', 
    bg: 'bg-green-100 dark:bg-green-900/40',
    border: 'border-green-400/70',
    glow: 'shadow-lg shadow-green-500/20',
    label: 'Connected',
  },
  disconnected: { 
    color: 'text-gray-700 dark:text-gray-400', 
    bg: 'bg-gray-100 dark:bg-gray-800',
    border: 'border-gray-400/50',
    glow: '',
    label: 'Disconnected',
  },
  reconnecting: { 
    color: 'text-yellow-700 dark:text-yellow-400', 
    bg: 'bg-yellow-100 dark:bg-yellow-900/40',
    border: 'border-yellow-400/70',
    glow: 'shadow-lg shadow-yellow-500/20',
    label: 'Reconnecting',
    pulse: true,
  },
  healthy: { 
    color: 'text-green-700 dark:text-green-400', 
    bg: 'bg-green-100 dark:bg-green-900/40',
    border: 'border-green-400/70',
    glow: 'shadow-lg shadow-green-500/20',
    label: 'Healthy',
  },
  degraded: { 
    color: 'text-yellow-700 dark:text-yellow-400', 
    bg: 'bg-yellow-100 dark:bg-yellow-900/40',
    border: 'border-yellow-400/70',
    glow: 'shadow-lg shadow-yellow-500/20',
    label: 'Degraded',
  },
  unhealthy: { 
    color: 'text-red-700 dark:text-red-400', 
    bg: 'bg-red-100 dark:bg-red-900/40',
    border: 'border-red-400/70',
    glow: 'shadow-lg shadow-red-500/20',
    label: 'Unhealthy',
  },
  long: { 
    color: 'text-green-700 dark:text-green-400', 
    bg: 'bg-green-100 dark:bg-green-900/40',
    border: 'border-green-400/70',
    glow: 'shadow-lg shadow-green-500/20',
    label: 'LONG',
  },
  short: { 
    color: 'text-red-700 dark:text-red-400', 
    bg: 'bg-red-100 dark:bg-red-900/40',
    border: 'border-red-400/70',
    glow: 'shadow-lg shadow-red-500/20',
    label: 'SHORT',
  },
};

const SIZE_CLASSES = {
  sm: 'text-xs px-1.5 py-0.5',
  md: 'text-sm px-2 py-0.5',
  lg: 'text-base px-2.5 py-1',
};

export const StatusBadge = memo(function StatusBadge({
  status,
  label,
  pulse,
  size = 'md',
  className,
}: StatusBadgeProps) {
  const config = STATUS_CONFIG[status];
  const showPulse = pulse ?? config.pulse;
  
  return (
    <Badge
      variant="outline"
      className={cn(
        config.color,
        config.bg,
        config.border,
        config.glow,
        SIZE_CLASSES[size],
        'font-medium transition-all',
        className
      )}
    >
      {showPulse && (
        <span className="relative mr-1.5 flex h-2 w-2">
          <span className={cn(
            'absolute inline-flex h-full w-full animate-ping rounded-full opacity-75',
            status === 'running' || status === 'connected' || status === 'healthy' 
              ? 'bg-green-400' 
              : status === 'pending' || status === 'reconnecting'
                ? 'bg-yellow-400'
                : 'bg-gray-400'
          )} />
          <span className={cn(
            'relative inline-flex h-2 w-2 rounded-full',
            status === 'running' || status === 'connected' || status === 'healthy'
              ? 'bg-green-500'
              : status === 'pending' || status === 'reconnecting'
                ? 'bg-yellow-500'
                : 'bg-gray-500'
          )} />
        </span>
      )}
      {label ?? config.label}
    </Badge>
  );
});

export default StatusBadge;
