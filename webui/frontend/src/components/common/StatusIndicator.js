import React from 'react';
import clsx from 'clsx';
import '../../styles/animations.css';

/**
 * StatusIndicator Component
 * Animated status dots with pulsing effect
 * 
 * Created: January 18, 2026
 * Safe: Pure UI component, no functional changes
 */

const StatusIndicator = ({
  status = 'idle',
  size = 'md',
  label,
  showLabel = true,
  className
}) => {
  const statusConfig = {
    running: {
      color: 'bg-green-500',
      glow: 'shadow-[0_0_12px_rgba(34,197,94,0.6)]',
      ring: 'ring-green-500/30',
      label: 'Running',
      animate: true
    },
    stopped: {
      color: 'bg-red-500',
      glow: 'shadow-[0_0_12px_rgba(239,68,68,0.6)]',
      ring: 'ring-red-500/30',
      label: 'Stopped',
      animate: false
    },
    idle: {
      color: 'bg-yellow-500',
      glow: 'shadow-[0_0_12px_rgba(234,179,8,0.6)]',
      ring: 'ring-yellow-500/30',
      label: 'Idle',
      animate: true
    },
    loading: {
      color: 'bg-blue-500',
      glow: 'shadow-[0_0_12px_rgba(59,130,246,0.6)]',
      ring: 'ring-blue-500/30',
      label: 'Loading',
      animate: true
    },
    connected: {
      color: 'bg-emerald-500',
      glow: 'shadow-[0_0_12px_rgba(16,185,129,0.6)]',
      ring: 'ring-emerald-500/30',
      label: 'Connected',
      animate: true
    },
    disconnected: {
      color: 'bg-slate-500',
      glow: '',
      ring: 'ring-slate-500/30',
      label: 'Disconnected',
      animate: false
    },
    warning: {
      color: 'bg-orange-500',
      glow: 'shadow-[0_0_12px_rgba(249,115,22,0.6)]',
      ring: 'ring-orange-500/30',
      label: 'Warning',
      animate: true
    },
    error: {
      color: 'bg-rose-500',
      glow: 'shadow-[0_0_12px_rgba(244,63,94,0.6)]',
      ring: 'ring-rose-500/30',
      label: 'Error',
      animate: true
    }
  };
  
  const sizeConfig = {
    xs: 'h-1.5 w-1.5',
    sm: 'h-2 w-2',
    md: 'h-2.5 w-2.5',
    lg: 'h-3 w-3',
    xl: 'h-4 w-4'
  };
  
  const config = statusConfig[status] || statusConfig.idle;
  const sizeClass = sizeConfig[size] || sizeConfig.md;
  
  return (
    <div className={clsx('inline-flex items-center gap-2', className)}>
      <div className="relative inline-flex">
        {/* Pulsing ring */}
        {config.animate && (
          <span
            className={clsx(
              'absolute inline-flex h-full w-full rounded-full opacity-75',
              config.color,
              'animate-pulse'
            )}
          />
        )}
        
        {/* Main dot */}
        <span
          className={clsx(
            'relative inline-flex rounded-full',
            config.color,
            config.glow,
            sizeClass
          )}
        />
      </div>
      
      {showLabel && (
        <span className="text-sm font-medium text-slate-300">
          {label || config.label}
        </span>
      )}
    </div>
  );
};

// Preset status indicators for common states
export const BotStatusIndicator = ({ isRunning, isIdle }) => {
  let status = 'stopped';
  if (isRunning && !isIdle) status = 'running';
  else if (isIdle) status = 'idle';
  
  return <StatusIndicator status={status} size="md" />;
};

export const ConnectionStatusIndicator = ({ connected, quality }) => {
  let status = 'disconnected';
  if (connected) {
    if (quality === 'excellent' || quality === 'good') status = 'connected';
    else if (quality === 'poor') status = 'warning';
  }
  
  return <StatusIndicator status={status} size="sm" />;
};

export const OrderStatusIndicator = ({ status: orderStatus }) => {
  const statusMap = {
    pending: 'loading',
    filled: 'connected',
    cancelled: 'stopped',
    rejected: 'error',
    expired: 'idle'
  };
  
  return <StatusIndicator status={statusMap[orderStatus] || 'idle'} size="sm" />;
};

export default StatusIndicator;
