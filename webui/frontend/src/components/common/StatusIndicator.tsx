import React from 'react';
import clsx from 'clsx';

/**
 * StatusIndicator Component
 * Visual status dots with labels
 *
 * Created: January 18, 2026 (Migrated to TypeScript)
 * Safe: Pure UI component, no functional changes
 */

type StatusType =
  | 'running'
  | 'stopped'
  | 'idle'
  | 'loading'
  | 'connected'
  | 'disconnected'
  | 'warning'
  | 'error';
type SizeType = 'xs' | 'sm' | 'md' | 'lg' | 'xl';

interface StatusIndicatorProps {
  status?: StatusType;
  label?: string;
  size?: SizeType;
  showLabel?: boolean;
  className?: string;
}

const StatusIndicator: React.FC<StatusIndicatorProps> = ({
  status = 'idle',
  label,
  size = 'md',
  showLabel = true,
  className,
}) => {
  const statusConfig: Record<
    StatusType,
    { color: string; bgColor: string; label: string; pulse: boolean }
  > = {
    running: { color: 'text-green-400', bgColor: 'bg-green-500', label: 'Running', pulse: false },
    stopped: { color: 'text-red-400', bgColor: 'bg-red-500', label: 'Stopped', pulse: false },
    idle: { color: 'text-yellow-400', bgColor: 'bg-yellow-500', label: 'Idle', pulse: false },
    loading: { color: 'text-blue-400', bgColor: 'bg-blue-500', label: 'Loading', pulse: false },
    connected: {
      color: 'text-green-400',
      bgColor: 'bg-green-500',
      label: 'Connected',
      pulse: false,
    },
    disconnected: {
      color: 'text-gray-400',
      bgColor: 'bg-gray-500',
      label: 'Disconnected',
      pulse: false,
    },
    warning: { color: 'text-orange-400', bgColor: 'bg-orange-500', label: 'Warning', pulse: false },
    error: { color: 'text-red-400', bgColor: 'bg-red-500', label: 'Error', pulse: false },
  };

  const sizeClasses: Record<SizeType, { dot: string; text: string }> = {
    xs: { dot: 'w-1.5 h-1.5', text: 'text-xs' },
    sm: { dot: 'w-2 h-2', text: 'text-sm' },
    md: { dot: 'w-2.5 h-2.5', text: 'text-sm' },
    lg: { dot: 'w-3 h-3', text: 'text-base' },
    xl: { dot: 'w-4 h-4', text: 'text-lg' },
  };

  const config = statusConfig[status];
  const sizeClass = sizeClasses[size];
  const displayLabel = label || config.label;

  return (
    <div className={clsx('inline-flex items-center gap-2', className)}>
      <div className="relative inline-flex">
        {config.pulse && (
          <span
            className={clsx(
              'absolute inline-flex h-full w-full rounded-full opacity-75 animate-pulse',
              config.bgColor
            )}
          />
        )}
        <span
          className={clsx('relative inline-flex rounded-full', sizeClass.dot, config.bgColor)}
        />
      </div>
      {showLabel && (
        <span className={clsx('font-medium', config.color, sizeClass.text)}>{displayLabel}</span>
      )}
    </div>
  );
};

// Specialized status indicators
interface BotStatusIndicatorProps {
  isRunning: boolean;
  isIdle: boolean;
}

export const BotStatusIndicator: React.FC<BotStatusIndicatorProps> = ({ isRunning, isIdle }) => {
  const status: StatusType = isIdle ? 'idle' : isRunning ? 'running' : 'stopped';
  return <StatusIndicator status={status} size="sm" />;
};

interface ConnectionStatusIndicatorProps {
  connected: boolean;
  quality?: 'excellent' | 'good' | 'poor';
}

export const ConnectionStatusIndicator: React.FC<ConnectionStatusIndicatorProps> = ({
  connected,
  quality = 'excellent',
}) => {
  let status: StatusType;
  if (!connected) {
    status = 'disconnected';
  } else if (quality === 'poor') {
    status = 'warning';
  } else {
    status = 'connected';
  }
  return <StatusIndicator status={status} size="sm" />;
};

interface OrderStatusIndicatorProps {
  status: 'pending' | 'filled' | 'cancelled' | 'rejected' | 'expired';
}

export const OrderStatusIndicator: React.FC<OrderStatusIndicatorProps> = ({ status }) => {
  const statusMap: Record<string, StatusType> = {
    pending: 'loading',
    filled: 'connected',
    cancelled: 'stopped',
    rejected: 'error',
    expired: 'idle',
  };

  return <StatusIndicator status={statusMap[status]} size="sm" />;
};

export default StatusIndicator;
