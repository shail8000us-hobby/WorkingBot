/**
 * Idle Detection Hook
 *
 * Detects user inactivity and pauses API calls/polling to save CPU.
 * Resumes on mouse movement, keyboard input, or scroll.
 *
 * Features:
 * - Configurable idle timeout (default: 60 seconds)
 * - Multiple activity detection (mouse, keyboard, scroll, touch)
 * - Automatic pause/resume of polling
 * - Visual indicator when paused
 * - Tab visibility detection
 *
 * Usage:
 * const { isIdle, isActive } = useIdleDetection({ timeout: 60000 });
 */

import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * Hook for detecting user idle state
 * @param {Object} options - Configuration options
 * @param {number} options.timeout - Idle timeout in milliseconds (default: 60000 = 60s)
 * @param {boolean} options.enabled - Enable/disable idle detection (default: true)
 * @param {Function} options.onIdle - Callback when user becomes idle
 * @param {Function} options.onActive - Callback when user becomes active
 * @returns {Object} - { isIdle, isActive, lastActivityTime, timeSinceActivity }
 */
export function useIdleDetection(options = {}) {
  const {
    timeout = 60000, // 60 seconds default
    enabled = true,
    onIdle,
    onActive,
  } = options;

  const [isIdle, setIsIdle] = useState(false);
  const [lastActivityTime, setLastActivityTime] = useState(Date.now());
  const [timeSinceActivity, setTimeSinceActivity] = useState(0);
  const [isTabVisible, setIsTabVisible] = useState(true);

  const idleTimerRef = useRef(null);
  const onIdleRef = useRef(onIdle);
  const onActiveRef = useRef(onActive);

  // Update refs when callbacks change
  useEffect(() => {
    onIdleRef.current = onIdle;
    onActiveRef.current = onActive;
  }, [onIdle, onActive]);

  // Handle activity
  const handleActivity = useCallback(() => {
    const now = Date.now();
    setLastActivityTime(now);
    setTimeSinceActivity(0);

    // If was idle, trigger onActive callback
    if (isIdle && onActiveRef.current) {
      console.log('👤 User is back - resuming activity');
      onActiveRef.current();
    }

    setIsIdle(false);

    // Clear existing timer
    if (idleTimerRef.current) {
      clearTimeout(idleTimerRef.current);
    }

    // Set new idle timer
    idleTimerRef.current = setTimeout(() => {
      console.log('😴 User is idle - pausing activity to save CPU');
      setIsIdle(true);
      if (onIdleRef.current) {
        onIdleRef.current();
      }
    }, timeout);
  }, [isIdle, timeout]);

  // Tab visibility detection
  useEffect(() => {
    const handleVisibilityChange = () => {
      const visible = !document.hidden;
      setIsTabVisible(visible);

      if (visible) {
        console.log('👁️ Tab is visible - resuming');
        handleActivity();
      } else {
        console.log('👁️ Tab is hidden - pausing');
        setIsIdle(true);
        if (onIdleRef.current) {
          onIdleRef.current();
        }
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [handleActivity]);

  // Activity event listeners
  useEffect(() => {
    if (!enabled) return;

    const events = ['mousedown', 'mousemove', 'keydown', 'scroll', 'touchstart', 'click'];

    // Throttle activity handler to avoid excessive calls
    let throttleTimeout = null;
    const throttledActivity = () => {
      if (!throttleTimeout) {
        handleActivity();
        throttleTimeout = setTimeout(() => {
          throttleTimeout = null;
        }, 1000); // Throttle to once per second
      }
    };

    events.forEach((event) => {
      document.addEventListener(event, throttledActivity, { passive: true });
    });

    // Initial activity
    handleActivity();

    return () => {
      events.forEach((event) => {
        document.removeEventListener(event, throttledActivity);
      });
      if (idleTimerRef.current) {
        clearTimeout(idleTimerRef.current);
      }
      if (throttleTimeout) {
        clearTimeout(throttleTimeout);
      }
    };
  }, [enabled, handleActivity]);

  // Update time since activity
  useEffect(() => {
    const interval = setInterval(() => {
      const elapsed = Date.now() - lastActivityTime;
      setTimeSinceActivity(elapsed);
    }, 1000);

    return () => clearInterval(interval);
  }, [lastActivityTime]);

  return {
    isIdle,
    isActive: !isIdle && isTabVisible,
    lastActivityTime,
    timeSinceActivity,
    isTabVisible,
  };
}

/**
 * Hook for smart polling that pauses when idle
 * @param {Function} callback - Function to call on interval
 * @param {number} interval - Interval in milliseconds
 * @param {Object} options - Idle detection options
 */
export function useSmartPolling(callback, interval = 30000, options = {}) {
  const { isActive } = useIdleDetection(options);
  const callbackRef = useRef(callback);

  // Update callback ref
  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  useEffect(() => {
    if (!isActive) {
      console.log('⏸️ Polling paused (user idle)');
      return;
    }

    // Initial call
    callbackRef.current();

    // Set up interval
    const timer = setInterval(() => {
      callbackRef.current();
    }, interval);

    return () => clearInterval(timer);
  }, [interval, isActive]);

  return { isActive };
}

export default useIdleDetection;
