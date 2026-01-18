/**
 * Badge Component - Status badges and indicators
 * Part of Design System consolidation
 */

import React from 'react';
import clsx from 'clsx';

const badgeVariants = {
  success: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  warning: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  error: 'bg-rose-500/20 text-rose-300 border-rose-500/30',
  info: 'bg-sky-500/20 text-sky-300 border-sky-500/30',
  neutral: 'bg-slate-700/50 text-slate-300 border-slate-600/50',
};

const badgeSizes = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-2.5 py-1 text-sm',
  lg: 'px-3 py-1.5 text-base',
};

const Badge = React.memo(function Badge({
  children,
  variant = 'neutral',
  size = 'sm',
  dot = false,
  className = '',
  ...props
}) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full border font-semibold',
        badgeVariants[variant],
        badgeSizes[size],
        className
      )}
      {...props}
    >
      {dot && (
        <span
          className={clsx(
            'h-1.5 w-1.5 rounded-full',
            variant === 'success' && 'bg-emerald-400',
            variant === 'warning' && 'bg-amber-400',
            variant === 'error' && 'bg-rose-400',
            variant === 'info' && 'bg-sky-400',
            variant === 'neutral' && 'bg-slate-400'
          )}
        />
      )}
      {children}
    </span>
  );
});

export default Badge;
