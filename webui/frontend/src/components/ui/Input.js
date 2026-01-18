/**
 * Input Component - Standardized form inputs
 * Part of Design System consolidation
 */

import React from 'react';
import clsx from 'clsx';

const Input = React.memo(function Input({
  label,
  error,
  helperText,
  fullWidth = false,
  className = '',
  ...props
}) {
  const inputId = props.id || props.name || `input-${Math.random().toString(36).substr(2, 9)}`;

  return (
    <div className={clsx('flex flex-col gap-1.5', fullWidth && 'w-full')}>
      {label && (
        <label htmlFor={inputId} className="text-sm font-medium text-slate-200">
          {label}
          {props.required && <span className="ml-1 text-rose-400">*</span>}
        </label>
      )}

      <input
        id={inputId}
        className={clsx(
          'rounded-lg border bg-slate-800/50 px-4 py-2 text-slate-100 placeholder-slate-500',
          'transition-all focus:outline-none focus:ring-2',
          error
            ? 'border-rose-500/50 focus:border-rose-500 focus:ring-rose-500/20'
            : 'border-slate-700 focus:border-sky-500 focus:ring-sky-500/20',
          'disabled:cursor-not-allowed disabled:opacity-50',
          fullWidth && 'w-full',
          className
        )}
        {...props}
      />

      {(error || helperText) && (
        <p className={clsx('text-xs', error ? 'text-rose-400' : 'text-slate-400')}>
          {error || helperText}
        </p>
      )}
    </div>
  );
});

export default Input;
