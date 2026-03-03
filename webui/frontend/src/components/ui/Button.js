/**
 * Button Component - Standardized button styles
 * Part of Design System consolidation
 */

import React from 'react';
import clsx from 'clsx';

const buttonVariants = {
  primary: 'bg-sky-500 text-white hover:bg-sky-600 border-sky-500',
  secondary: 'bg-slate-700 text-slate-100 hover:bg-slate-600 border-slate-700',
  danger: 'bg-rose-500 text-white hover:bg-rose-600 border-rose-500',
  success: 'bg-emerald-500 text-white hover:bg-emerald-600 border-emerald-500',
  ghost: 'bg-transparent text-slate-300 hover:bg-slate-800 border-slate-700',
  outline: 'bg-transparent text-sky-400 hover:bg-sky-500/10 border-sky-500',
};

const buttonSizes = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-base',
  lg: 'px-6 py-3 text-lg',
};

const Button = React.memo(function Button({
  children,
  variant = 'primary',
  size = 'md',
  disabled = false,
  loading = false,
  icon,
  fullWidth = false,
  className = '',
  onClick,
  type = 'button',
  ...props
}) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      onClick={onClick}
      className={clsx(
        'inline-flex items-center justify-center gap-2 rounded-lg border font-semibold transition-all duration-150',
        'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:ring-offset-slate-900',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        !disabled && !loading && 'hover:scale-[1.02] active:scale-[0.98]',
        buttonVariants[variant],
        buttonSizes[size],
        fullWidth && 'w-full',
        className
      )}
      {...props}
    >
      {loading ? (
        <>
          <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24">
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
              fill="none"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          <span>Loading...</span>
        </>
      ) : (
        <>
          {icon && <span className="flex-shrink-0">{icon}</span>}
          {children}
        </>
      )}
    </button>
  );
});

export default Button;
