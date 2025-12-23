/**
 * Performance Optimizer Utilities
 * 
 * Helps prevent shaky UI behavior by:
 * - Debouncing rapid updates
 * - Throttling frequent function calls
 * - Smart polling intervals
 * - Re-render optimization
 */

import { useRef, useEffect, useCallback, useState } from 'react';

/**
 * Debounce function - prevents excessive calls
 * @param {Function} func - Function to debounce
 * @param {number} delay - Delay in milliseconds
 * @returns {Function} Debounced function
 */
export function debounce(func, delay = 300) {
  let timeoutId;
  return function debounced(...args) {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func.apply(this, args), delay);
  };
}

/**
 * Throttle function - limits call frequency
 * @param {Function} func - Function to throttle
 * @param {number} limit - Minimum time between calls (ms)
 * @returns {Function} Throttled function
 */
export function throttle(func, limit = 1000) {
  let inThrottle;
  return function throttled(...args) {
    if (!inThrottle) {
      func.apply(this, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}

/**
 * useDebounced - React hook for debounced values
 * @param {any} value - Value to debounce
 * @param {number} delay - Debounce delay in ms
 * @returns {any} Debounced value
 */
export function useDebounced(value, delay = 300) {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}

/**
 * useThrottledCallback - React hook for throttled callbacks
 * @param {Function} callback - Callback to throttle
 * @param {number} limit - Throttle limit in ms
 * @returns {Function} Throttled callback
 */
export function useThrottledCallback(callback, limit = 1000) {
  const throttledFn = useRef();
  
  useEffect(() => {
    throttledFn.current = throttle(callback, limit);
  }, [callback, limit]);
  
  return useCallback((...args) => {
    if (throttledFn.current) {
      throttledFn.current(...args);
    }
  }, []);
}

/**
 * Smart polling intervals based on panel visibility
 * @param {Function} callback - Function to call on interval
 * @param {number} interval - Interval in ms
 * @param {boolean} isVisible - Whether panel is visible
 */
export function useSmartPolling(callback, interval = 30000, isVisible = true) {
  useEffect(() => {
    if (!isVisible) return; // Don't poll if panel hidden
    
    callback(); // Initial call
    
    const timer = setInterval(callback, interval);
    return () => clearInterval(timer);
  }, [callback, interval, isVisible]);
}

/**
 * Batch state updates to reduce re-renders
 * @param {Object} initialState - Initial state object
 * @returns {[Object, Function]} State and batch update function
 */
export function useBatchedState(initialState = {}) {
  const [state, setState] = useState(initialState);
  const pendingUpdates = useRef({});
  const flushTimer = useRef(null);
  
  const batchUpdate = useCallback((updates) => {
    // Collect updates
    pendingUpdates.current = {
      ...pendingUpdates.current,
      ...updates
    };
    
    // Clear existing timer
    if (flushTimer.current) {
      clearTimeout(flushTimer.current);
    }
    
    // Flush after 100ms of no new updates
    flushTimer.current = setTimeout(() => {
      setState(prev => ({
        ...prev,
        ...pendingUpdates.current
      }));
      pendingUpdates.current = {};
    }, 100);
  }, []);
  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (flushTimer.current) {
        clearTimeout(flushTimer.current);
      }
    };
  }, []);
  
  return [state, batchUpdate];
}

/**
 * Check if value actually changed (deep comparison for objects)
 * @param {any} value - Value to compare
 * @returns {any} Value (only triggers re-render if actually changed)
 */
export function useDeepMemo(value) {
  const ref = useRef();
  
  if (JSON.stringify(ref.current) !== JSON.stringify(value)) {
    ref.current = value;
  }
  
  return ref.current;
}

/**
 * Recommended polling intervals
 */
export const POLLING_INTERVALS = {
  CRITICAL: 5000,     // 5s - Only for critical real-time data
  NORMAL: 30000,      // 30s - Standard updates
  SLOW: 60000,        // 60s - Low priority data
  VERY_SLOW: 300000   // 5min - Rarely changing data
};

/**
 * Performance monitoring helper
 */
export class PanelPerformanceMonitor {
  constructor(panelName) {
    this.panelName = panelName;
    this.renderCount = 0;
    this.lastRenderTime = Date.now();
  }
  
  logRender() {
    this.renderCount++;
    const now = Date.now();
    const timeSinceLastRender = now - this.lastRenderTime;
    
    if (timeSinceLastRender < 100) {
      console.warn(
        `⚠️ ${this.panelName}: Frequent re-renders detected (${timeSinceLastRender}ms since last render)`
      );
    }
    
    this.lastRenderTime = now;
  }
  
  getStats() {
    return {
      panel: this.panelName,
      totalRenders: this.renderCount,
      avgRenderInterval: this.renderCount > 1 
        ? (Date.now() - this.lastRenderTime) / this.renderCount 
        : 0
    };
  }
}

export default {
  debounce,
  throttle,
  useDebounced,
  useThrottledCallback,
  useSmartPolling,
  useBatchedState,
  useDeepMemo,
  POLLING_INTERVALS,
  PanelPerformanceMonitor
};

