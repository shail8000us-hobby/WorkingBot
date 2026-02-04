/**
 * CircuitBreakerAlert Component
 * 
 * Alert component for circuit breaker warnings and triggers.
 * Displays countdown timer when in warning zone.
 * 
 * Per Implementation Plan: Section 2.3 - shared/CircuitBreakerAlert.js
 * Created: February 3, 2026
 */

import React, { useState, useEffect, useCallback } from 'react';

/**
 * Alert severity configurations
 */
const SEVERITY_CONFIG = {
  info: {
    bg: 'bg-blue-50',
    border: 'border-blue-300',
    text: 'text-blue-800',
    icon: 'ℹ️',
    iconBg: 'bg-blue-100',
  },
  warning: {
    bg: 'bg-yellow-50',
    border: 'border-yellow-300',
    text: 'text-yellow-800',
    icon: '⚠️',
    iconBg: 'bg-yellow-100',
  },
  danger: {
    bg: 'bg-red-50',
    border: 'border-red-300',
    text: 'text-red-800',
    icon: '🚨',
    iconBg: 'bg-red-100',
  },
  triggered: {
    bg: 'bg-red-100',
    border: 'border-red-500',
    text: 'text-red-900',
    icon: '⚡',
    iconBg: 'bg-red-200',
  },
  success: {
    bg: 'bg-green-50',
    border: 'border-green-300',
    text: 'text-green-800',
    icon: '✅',
    iconBg: 'bg-green-100',
  },
};

/**
 * Countdown timer hook
 */
const useCountdown = (endTime, onComplete) => {
  const [timeLeft, setTimeLeft] = useState(0);

  useEffect(() => {
    if (!endTime) {
      setTimeLeft(0);
      return;
    }

    const updateTimer = () => {
      const now = Date.now();
      const end = typeof endTime === 'number' ? endTime : new Date(endTime).getTime();
      const remaining = Math.max(0, end - now);
      
      setTimeLeft(remaining);
      
      if (remaining === 0 && onComplete) {
        onComplete();
      }
    };

    updateTimer();
    const interval = setInterval(updateTimer, 100);

    return () => clearInterval(interval);
  }, [endTime, onComplete]);

  return timeLeft;
};

/**
 * Format milliseconds to MM:SS.ms display
 */
const formatCountdown = (ms) => {
  if (ms <= 0) return '00:00.0';
  
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  const tenths = Math.floor((ms % 1000) / 100);
  
  return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}.${tenths}`;
};

/**
 * CircuitBreakerAlert Component
 * 
 * @param {string} severity - Alert severity: 'info', 'warning', 'danger', 'triggered', 'success'
 * @param {string} title - Alert title
 * @param {string} message - Alert message
 * @param {number|string} countdownEndTime - End time for countdown (ms timestamp or ISO string)
 * @param {function} onCountdownComplete - Callback when countdown reaches zero
 * @param {string} zone - Zone name ('upper' or 'lower')
 * @param {number} distance - Distance to max loss point
 * @param {boolean} dismissible - Can alert be dismissed
 * @param {function} onDismiss - Callback when dismissed
 * @param {Array} actions - Action buttons [{label, onClick, variant}]
 * @param {string} className - Additional CSS classes
 */
const CircuitBreakerAlert = ({
  severity = 'warning',
  title,
  message,
  countdownEndTime,
  onCountdownComplete,
  zone,
  distance,
  dismissible = false,
  onDismiss,
  actions = [],
  className = '',
}) => {
  const config = SEVERITY_CONFIG[severity] || SEVERITY_CONFIG.warning;
  const timeLeft = useCountdown(countdownEndTime, onCountdownComplete);
  const [dismissed, setDismissed] = useState(false);

  const handleDismiss = useCallback(() => {
    setDismissed(true);
    if (onDismiss) onDismiss();
  }, [onDismiss]);

  if (dismissed) return null;

  // Determine urgency level based on time left
  const isUrgent = timeLeft > 0 && timeLeft < 3000; // Less than 3 seconds
  const isCritical = timeLeft > 0 && timeLeft < 1000; // Less than 1 second

  return (
    <div
      className={`
        relative rounded-lg border-l-4 p-4
        ${config.bg} ${config.border}
        ${isUrgent ? 'animate-pulse' : ''}
        ${className}
      `}
      role="alert"
    >
      <div className="flex items-start">
        {/* Icon */}
        <div
          className={`
            flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center
            ${config.iconBg} ${isCritical ? 'animate-bounce' : ''}
          `}
        >
          <span className="text-xl">{config.icon}</span>
        </div>

        {/* Content */}
        <div className="ml-3 flex-1">
          {/* Title and countdown */}
          <div className="flex items-center justify-between">
            <h3 className={`text-lg font-semibold ${config.text}`}>
              {title || getDefaultTitle(severity, zone)}
            </h3>
            
            {countdownEndTime && timeLeft > 0 && (
              <div
                className={`
                  px-3 py-1 rounded-full font-mono font-bold text-lg
                  ${isCritical ? 'bg-red-600 text-white' : isUrgent ? 'bg-yellow-500 text-white' : 'bg-gray-200 text-gray-800'}
                `}
              >
                {formatCountdown(timeLeft)}
              </div>
            )}
          </div>

          {/* Message */}
          <p className={`mt-1 ${config.text} opacity-90`}>
            {message || getDefaultMessage(severity, zone, distance)}
          </p>

          {/* Zone and distance info */}
          {zone && (
            <div className="mt-2 flex items-center gap-4 text-sm">
              <span className={`font-medium ${config.text}`}>
                Zone: {zone.charAt(0).toUpperCase() + zone.slice(1)}
              </span>
              {distance !== undefined && (
                <span className={config.text}>
                  Distance: {Math.abs(distance).toFixed(0)} pts
                </span>
              )}
            </div>
          )}

          {/* Actions */}
          {actions.length > 0 && (
            <div className="mt-3 flex gap-2">
              {actions.map((action, index) => (
                <button
                  key={index}
                  onClick={action.onClick}
                  className={`
                    px-4 py-2 rounded-md text-sm font-medium transition-colors
                    ${action.variant === 'primary' 
                      ? 'bg-blue-600 text-white hover:bg-blue-700' 
                      : action.variant === 'danger'
                      ? 'bg-red-600 text-white hover:bg-red-700'
                      : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'
                    }
                  `}
                >
                  {action.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Dismiss button */}
        {dismissible && (
          <button
            onClick={handleDismiss}
            className={`
              ml-2 flex-shrink-0 p-1 rounded-full
              hover:bg-gray-200 transition-colors
              ${config.text}
            `}
            aria-label="Dismiss"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        )}
      </div>

      {/* Progress bar for countdown */}
      {countdownEndTime && timeLeft > 0 && (
        <div className="absolute bottom-0 left-0 right-0 h-1 bg-gray-200 rounded-b-lg overflow-hidden">
          <div
            className={`
              h-full transition-all duration-100
              ${isCritical ? 'bg-red-600' : isUrgent ? 'bg-yellow-500' : 'bg-blue-500'}
            `}
            style={{
              width: `${Math.min(100, (timeLeft / 5000) * 100)}%`, // 5 second max display
            }}
          />
        </div>
      )}
    </div>
  );
};

/**
 * Get default title based on severity
 */
const getDefaultTitle = (severity, zone) => {
  switch (severity) {
    case 'danger':
      return `Max Loss Zone Alert - ${zone?.toUpperCase() || 'DANGER'}`;
    case 'triggered':
      return 'Circuit Breaker TRIGGERED';
    case 'warning':
      return 'Approaching Max Loss Zone';
    case 'success':
      return 'Back to Safe Zone';
    default:
      return 'Price Alert';
  }
};

/**
 * Get default message based on severity
 */
const getDefaultMessage = (severity, zone, distance) => {
  const distanceText = distance !== undefined ? ` (${Math.abs(distance).toFixed(0)} pts)` : '';
  
  switch (severity) {
    case 'danger':
      return `Price has entered the ${zone || 'max loss'} zone${distanceText}. Protective trigger imminent.`;
    case 'triggered':
      return 'Protective positions have been executed to limit losses.';
    case 'warning':
      return `Price is approaching the ${zone || 'max loss'} boundary${distanceText}. Monitor closely.`;
    case 'success':
      return 'Price has returned to the profit zone. No action needed.';
    default:
      return 'Price movement detected.';
  }
};

/**
 * Compact alert for dashboard headers
 */
export const CompactCircuitBreakerAlert = ({
  severity = 'warning',
  zone,
  distance,
  countdownEndTime,
  className = '',
}) => {
  const config = SEVERITY_CONFIG[severity] || SEVERITY_CONFIG.warning;
  const timeLeft = useCountdown(countdownEndTime);

  return (
    <div
      className={`
        inline-flex items-center gap-2 px-3 py-1.5 rounded-full
        ${config.bg} border ${config.border}
        ${className}
      `}
    >
      <span>{config.icon}</span>
      <span className={`font-medium ${config.text}`}>
        {zone && `${zone.charAt(0).toUpperCase() + zone.slice(1)} Zone`}
        {distance !== undefined && ` • ${Math.abs(distance).toFixed(0)} pts`}
      </span>
      {timeLeft > 0 && (
        <span className="font-mono font-bold">
          {formatCountdown(timeLeft)}
        </span>
      )}
    </div>
  );
};

export default CircuitBreakerAlert;
