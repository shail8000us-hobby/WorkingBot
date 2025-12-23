/**
 * Rate Limiting & Debouncing Utilities
 * Prevents excessive API calls and button clicks
 */

/**
 * Debounce function - delays execution until after delay
 * @param {Function} func - Function to debounce
 * @param {number} delay - Delay in milliseconds
 * @returns {Function} Debounced function
 */
export const debounce = (func, delay = 300) => {
  let timeoutId;
  
  const debounced = function(...args) {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func.apply(this, args), delay);
  };

  debounced.cancel = () => {
    clearTimeout(timeoutId);
  };

  return debounced;
};

/**
 * Throttle function - limits execution to once per interval
 * @param {Function} func - Function to throttle
 * @param {number} interval - Interval in milliseconds
 * @returns {Function} Throttled function
 */
export const throttle = (func, interval = 1000) => {
  let lastCall = 0;
  let timeoutId;

  return function(...args) {
    const now = Date.now();
    const timeSinceLastCall = now - lastCall;

    if (timeSinceLastCall >= interval) {
      lastCall = now;
      func.apply(this, args);
    } else {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        lastCall = Date.now();
        func.apply(this, args);
      }, interval - timeSinceLastCall);
    }
  };
};

/**
 * Rate Limiter Class
 * Manages rate limiting for multiple operations
 */
export class RateLimiter {
  constructor(maxCalls = 10, timeWindow = 1000) {
    this.maxCalls = maxCalls;
    this.timeWindow = timeWindow;
    this.calls = [];
  }

  canCall() {
    const now = Date.now();
    // Remove old calls outside the time window
    this.calls = this.calls.filter(timestamp => now - timestamp < this.timeWindow);
    return this.calls.length < this.maxCalls;
  }

  call(func) {
    if (this.canCall()) {
      this.calls.push(Date.now());
      return func();
    } else {
      console.warn('Rate limit exceeded');
      return Promise.reject(new Error('Rate limit exceeded'));
    }
  }

  getCallsRemaining() {
    const now = Date.now();
    this.calls = this.calls.filter(timestamp => now - timestamp < this.timeWindow);
    return this.maxCalls - this.calls.length;
  }

  reset() {
    this.calls = [];
  }
}

/**
 * React Hook for Debouncing
 * @param {any} value - Value to debounce
 * @param {number} delay - Delay in milliseconds
 * @returns {any} Debounced value
 */
export const useDebouncedValue = (value, delay = 300) => {
  const [debouncedValue, setDebouncedValue] = React.useState(value);

  React.useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
};

/**
 * React Hook for Rate Limited Function
 * @param {Function} func - Function to rate limit
 * @param {number} minInterval - Minimum interval between calls in milliseconds
 * @returns {Function} Rate limited function
 */
export const useRateLimited = (func, minInterval = 1000) => {
  const lastCallRef = React.useRef(0);

  return React.useCallback((...args) => {
    const now = Date.now();
    const timeSinceLastCall = now - lastCallRef.current;

    if (timeSinceLastCall >= minInterval) {
      lastCallRef.current = now;
      return func(...args);
    } else {
      const remaining = minInterval - timeSinceLastCall;
      console.log(`Rate limited: Please wait ${remaining}ms`);
      return Promise.reject(new Error(`Please wait ${remaining}ms before trying again`));
    }
  }, [func, minInterval]);
};

/**
 * Button Click Rate Limiter
 * Prevents rapid button clicking
 */
export class ButtonRateLimiter {
  constructor(minInterval = 1000) {
    this.minInterval = minInterval;
    this.lastClicks = new Map();
  }

  canClick(buttonId) {
    const lastClick = this.lastClicks.get(buttonId) || 0;
    const now = Date.now();
    return now - lastClick >= this.minInterval;
  }

  click(buttonId, callback) {
    if (this.canClick(buttonId)) {
      this.lastClicks.set(buttonId, Date.now());
      return callback();
    } else {
      const lastClick = this.lastClicks.get(buttonId);
      const remaining = this.minInterval - (Date.now() - lastClick);
      console.log(`Button "${buttonId}" rate limited: ${remaining}ms remaining`);
      return null;
    }
  }

  getTimeRemaining(buttonId) {
    const lastClick = this.lastClicks.get(buttonId);
    if (!lastClick) return 0;
    const elapsed = Date.now() - lastClick;
    return Math.max(0, this.minInterval - elapsed);
  }
}

// Singleton instance for global button rate limiting
export const globalButtonLimiter = new ButtonRateLimiter(1000);

/**
 * Request Queue Manager
 * Queues requests when rate limited
 */
export class RequestQueue {
  constructor(maxConcurrent = 5, minInterval = 100) {
    this.maxConcurrent = maxConcurrent;
    this.minInterval = minInterval;
    this.queue = [];
    this.active = 0;
    this.lastRequest = 0;
  }

  async add(requestFn) {
    return new Promise((resolve, reject) => {
      this.queue.push({ requestFn, resolve, reject });
      this.process();
    });
  }

  async process() {
    if (this.active >= this.maxConcurrent || this.queue.length === 0) {
      return;
    }

    const now = Date.now();
    const timeSinceLastRequest = now - this.lastRequest;
    
    if (timeSinceLastRequest < this.minInterval) {
      setTimeout(() => this.process(), this.minInterval - timeSinceLastRequest);
      return;
    }

    const { requestFn, resolve, reject } = this.queue.shift();
    this.active++;
    this.lastRequest = Date.now();

    try {
      const result = await requestFn();
      resolve(result);
    } catch (error) {
      reject(error);
    } finally {
      this.active--;
      this.process();
    }
  }

  clear() {
    this.queue = [];
  }

  getQueueLength() {
    return this.queue.length;
  }
}

// Global request queue
export const globalRequestQueue = new RequestQueue(5, 100);

/**
 * Adaptive Rate Limiter
 * Adjusts rate limit based on success/failure
 */
export class AdaptiveRateLimiter {
  constructor(initialInterval = 1000) {
    this.interval = initialInterval;
    this.minInterval = 100;
    this.maxInterval = 10000;
    this.lastCall = 0;
    this.successCount = 0;
    this.failureCount = 0;
  }

  async call(func) {
    const now = Date.now();
    const timeSinceLastCall = now - this.lastCall;

    if (timeSinceLastCall < this.interval) {
      await new Promise(resolve => 
        setTimeout(resolve, this.interval - timeSinceLastCall)
      );
    }

    this.lastCall = Date.now();

    try {
      const result = await func();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }

  onSuccess() {
    this.successCount++;
    this.failureCount = 0;

    // Gradually decrease interval on consecutive successes
    if (this.successCount >= 5) {
      this.interval = Math.max(this.minInterval, this.interval * 0.8);
      this.successCount = 0;
      console.log(`📉 Adaptive rate limit decreased to ${this.interval}ms`);
    }
  }

  onFailure() {
    this.failureCount++;
    this.successCount = 0;

    // Increase interval on failure
    this.interval = Math.min(this.maxInterval, this.interval * 1.5);
    console.log(`📈 Adaptive rate limit increased to ${this.interval}ms`);
  }

  reset() {
    this.interval = 1000;
    this.successCount = 0;
    this.failureCount = 0;
  }
}

// For use in React components
const React = require('react');

export default {
  debounce,
  throttle,
  RateLimiter,
  ButtonRateLimiter,
  RequestQueue,
  AdaptiveRateLimiter,
  globalButtonLimiter,
  globalRequestQueue,
};

