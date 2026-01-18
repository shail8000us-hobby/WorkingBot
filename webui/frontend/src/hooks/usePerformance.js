/**
 * Performance Optimization Hooks
 * React hooks for measuring and optimizing component performance
 *
 * Created: January 18, 2026 (Phase 6: Performance Optimization)
 * Safe: Pure React hooks for performance tracking
 */

import { useEffect, useRef, useCallback, useMemo, useState } from 'react';
import { perfMonitor } from '../utils/performanceMonitor';

/**
 * Hook to measure component render performance
 * Automatically tracks render count and duration
 *
 * @param {string} componentName - Name of the component
 */
export const useRenderPerformance = (componentName) => {
  const renderCount = useRef(0);

  useEffect(() => {
    renderCount.current++;
    const endMeasure = perfMonitor.measureRender(componentName);
    return endMeasure;
  });

  // Log excessive re-renders in development
  useEffect(() => {
    if (process.env.NODE_ENV === 'development' && renderCount.current > 50) {
      console.warn(
        `⚠️ ${componentName} has rendered ${renderCount.current} times. Consider optimization.`
      );
    }
  });
};

/**
 * Hook for stable callback references
 * Prevents unnecessary re-renders from callback prop changes
 *
 * @param {Function} callback - Callback function
 * @param {Array} deps - Dependencies
 * @returns {Function} Memoized callback
 */
export const useStableCallback = (callback, deps = []) => {
  // eslint-disable-next-line react-hooks/exhaustive-deps
  return useCallback(callback, deps);
};

/**
 * Hook for expensive computations
 * Memoizes results to prevent recalculation on every render
 *
 * @param {Function} factory - Computation function
 * @param {Array} deps - Dependencies
 * @returns {any} Memoized value
 */
export const useExpensiveComputation = (factory, deps) => {
  // eslint-disable-next-line react-hooks/exhaustive-deps
  return useMemo(() => {
    const start = performance.now();
    const result = factory();
    const duration = performance.now() - start;

    if (duration > 16) {
      // eslint-disable-next-line no-console
      console.warn(`🐌 Expensive computation took ${duration.toFixed(2)}ms`);
    }

    return result;
  }, deps);
};

/**
 * Hook to detect unnecessary re-renders
 * Logs when component re-renders without prop/state changes
 *
 * @param {string} componentName - Component name
 * @param {Object} props - Component props
 */
export const useWhyDidYouUpdate = (componentName, props) => {
  const previousProps = useRef();

  useEffect(() => {
    if (previousProps.current && process.env.NODE_ENV === 'development') {
      const allKeys = Object.keys({ ...previousProps.current, ...props });
      const changedProps = {};

      allKeys.forEach((key) => {
        if (previousProps.current[key] !== props[key]) {
          changedProps[key] = {
            from: previousProps.current[key],
            to: props[key],
          };
        }
      });

      if (Object.keys(changedProps).length > 0) {
        // eslint-disable-next-line no-console
        console.log(`🔄 ${componentName} re-rendered due to:`, changedProps);
      } else {
        // eslint-disable-next-line no-console
        console.warn(`⚠️ ${componentName} re-rendered but props didn't change!`);
      }
    }

    previousProps.current = props;
  });
};

/**
 * Hook for debounced values
 * Prevents expensive operations on rapid value changes
 *
 * @param {any} value - Value to debounce
 * @param {number} delay - Debounce delay in ms
 * @returns {any} Debounced value
 */
export const useDebouncedValue = (value, delay = 300) => {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => clearTimeout(handler);
  }, [value, delay]);

  return debouncedValue;
};

/**
 * Hook for throttled callbacks
 * Limits callback execution frequency
 *
 * @param {Function} callback - Callback to throttle
 * @param {number} limit - Throttle limit in ms
 * @returns {Function} Throttled callback
 */
export const useThrottledCallback = (callback, limit = 1000) => {
  const inThrottle = useRef(false);

  return useCallback(
    (...args) => {
      if (!inThrottle.current) {
        callback(...args);
        inThrottle.current = true;
        setTimeout(() => {
          inThrottle.current = false;
        }, limit);
      }
    },
    [callback, limit]
  );
};

/**
 * Hook to detect component mount/unmount
 * Useful for tracking component lifecycle performance
 *
 * @param {string} componentName - Component name
 */
export const useComponentLifecycle = (componentName) => {
  useEffect(() => {
    const mountTime = performance.now();
    // eslint-disable-next-line no-console
    console.log(`✅ ${componentName} mounted`);

    return () => {
      const lifetime = performance.now() - mountTime;
      // eslint-disable-next-line no-console
      console.log(`❌ ${componentName} unmounted (lifetime: ${lifetime.toFixed(2)}ms)`);
    };
  }, [componentName]);
};

export default {
  useRenderPerformance,
  useStableCallback,
  useExpensiveComputation,
  useWhyDidYouUpdate,
  useDebouncedValue,
  useThrottledCallback,
  useComponentLifecycle,
};
