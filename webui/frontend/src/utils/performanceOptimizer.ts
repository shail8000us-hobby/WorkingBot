/**
 * Performance Optimizer Utilities
 * Migrated to TypeScript: January 18, 2026
 */

import { useRef, useEffect, useCallback, useState } from 'react';

export function debounce<T extends (...args: any[]) => any>(func: T, delay: number = 300) {
  let timeoutId: ReturnType<typeof setTimeout>;
  return function debounced(this: any, ...args: Parameters<T>) {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func.apply(this, args), delay);
  };
}

export function throttle<T extends (...args: any[]) => any>(func: T, limit: number = 1000) {
  let inThrottle: boolean;
  return function throttled(this: any, ...args: Parameters<T>) {
    if (!inThrottle) {
      func.apply(this, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}

export function useDebounced<T>(value: T, delay: number = 300): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}

export function useThrottledCallback<T extends (...args: any[]) => any>(
  callback: T,
  limit: number = 1000
): (...args: Parameters<T>) => void {
  const throttledFn = useRef<ReturnType<typeof throttle<T>>>();
  
  useEffect(() => {
    throttledFn.current = throttle(callback, limit);
  }, [callback, limit]);
  
  return useCallback((...args: Parameters<T>) => {
    if (throttledFn.current) {
      throttledFn.current(...args);
    }
  }, []);
}

export function useSmartPolling(
  callback: () => void,
  interval: number = 30000,
  isVisible: boolean = true
): void {
  useEffect(() => {
    if (!isVisible) return;
    
    callback();
    
    const timer = setInterval(callback, interval);
    return () => clearInterval(timer);
  }, [callback, interval, isVisible]);
}

export default { debounce, throttle, useDebounced, useThrottledCallback, useSmartPolling };
