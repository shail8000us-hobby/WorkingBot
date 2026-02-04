/**
 * LoadingSpinner Component
 * 
 * Reusable loading spinner with size and color variants.
 * 
 * Per Implementation Plan: Section 2.3 - shared/LoadingSpinner.js
 * Created: February 3, 2026
 */

import React from 'react';

/**
 * Size configurations
 */
const SIZE_CONFIG = {
  xs: 'w-4 h-4 border-2',
  sm: 'w-6 h-6 border-2',
  md: 'w-8 h-8 border-2',
  lg: 'w-12 h-12 border-3',
  xl: 'w-16 h-16 border-4',
};

/**
 * Color configurations
 */
const COLOR_CONFIG = {
  primary: 'border-blue-500',
  secondary: 'border-gray-500',
  success: 'border-green-500',
  danger: 'border-red-500',
  warning: 'border-yellow-500',
  white: 'border-white',
};

/**
 * LoadingSpinner Component
 * 
 * @param {string} size - Spinner size: 'xs', 'sm', 'md', 'lg', 'xl'
 * @param {string} color - Spinner color: 'primary', 'secondary', 'success', 'danger', 'warning', 'white'
 * @param {string} label - Accessibility label
 * @param {string} className - Additional CSS classes
 */
const LoadingSpinner = ({
  size = 'md',
  color = 'primary',
  label = 'Loading',
  className = '',
}) => {
  const sizeClass = SIZE_CONFIG[size] || SIZE_CONFIG.md;
  const colorClass = COLOR_CONFIG[color] || COLOR_CONFIG.primary;

  return (
    <div
      className={`inline-block ${sizeClass} ${className}`}
      role="status"
      aria-label={label}
    >
      <div
        className={`
          w-full h-full rounded-full
          border-t-transparent
          ${colorClass}
          animate-spin
        `}
      />
      <span className="sr-only">{label}</span>
    </div>
  );
};

/**
 * Loading overlay for containers
 */
export const LoadingOverlay = ({
  loading = true,
  label = 'Loading...',
  size = 'lg',
  className = '',
  children,
}) => {
  if (!loading) return children || null;

  return (
    <div className={`relative ${className}`}>
      {children && (
        <div className="opacity-50 pointer-events-none">
          {children}
        </div>
      )}
      <div className="absolute inset-0 flex items-center justify-center bg-white bg-opacity-75">
        <div className="flex flex-col items-center gap-2">
          <LoadingSpinner size={size} />
          {label && (
            <span className="text-gray-600 text-sm">{label}</span>
          )}
        </div>
      </div>
    </div>
  );
};

/**
 * Skeleton loader for content placeholders
 */
export const SkeletonLoader = ({
  type = 'text',
  width,
  height,
  lines = 1,
  className = '',
}) => {
  const baseClass = 'bg-gray-200 animate-pulse rounded';

  if (type === 'text') {
    return (
      <div className={`space-y-2 ${className}`}>
        {Array.from({ length: lines }).map((_, i) => (
          <div
            key={i}
            className={`${baseClass} h-4`}
            style={{ width: i === lines - 1 && lines > 1 ? '75%' : width || '100%' }}
          />
        ))}
      </div>
    );
  }

  if (type === 'circle') {
    return (
      <div
        className={`${baseClass} rounded-full ${className}`}
        style={{ width: width || 40, height: height || 40 }}
      />
    );
  }

  if (type === 'card') {
    return (
      <div className={`${baseClass} ${className}`} style={{ width, height: height || 120 }}>
        <div className="p-4 space-y-3">
          <div className="bg-gray-300 h-4 rounded w-1/3" />
          <div className="bg-gray-300 h-8 rounded w-2/3" />
          <div className="bg-gray-300 h-3 rounded w-1/2" />
        </div>
      </div>
    );
  }

  // Default rectangle
  return (
    <div
      className={`${baseClass} ${className}`}
      style={{ width: width || '100%', height: height || 20 }}
    />
  );
};

/**
 * Button loading state
 */
export const ButtonSpinner = ({ color = 'white', className = '' }) => {
  return (
    <LoadingSpinner size="xs" color={color} className={`mr-2 ${className}`} />
  );
};

/**
 * Full page loading screen
 */
export const FullPageLoader = ({ message = 'Loading SSR Algo...', className = '' }) => {
  return (
    <div className={`fixed inset-0 flex items-center justify-center bg-gray-50 z-50 ${className}`}>
      <div className="flex flex-col items-center gap-4">
        <div className="relative">
          <LoadingSpinner size="xl" />
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xl font-bold text-blue-600">SSR</span>
          </div>
        </div>
        <p className="text-gray-600 text-lg">{message}</p>
      </div>
    </div>
  );
};

/**
 * Inline loader with text
 */
export const InlineLoader = ({
  loading = true,
  children,
  loadingText = 'Loading...',
  size = 'sm',
  className = '',
}) => {
  if (!loading) return children || null;

  return (
    <span className={`inline-flex items-center ${className}`}>
      <LoadingSpinner size={size} className="mr-2" />
      {loadingText}
    </span>
  );
};

export default LoadingSpinner;
