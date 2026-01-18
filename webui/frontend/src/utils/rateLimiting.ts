/**
 * Rate Limiting & Debouncing Utilities
 * Prevents excessive API calls and button clicks
 * 
 * Migrated to TypeScript: January 18, 2026
 */

type DebouncedFunction<T extends (...args: any[]) => any> = {
  (...args: Parameters<T>): void;
  cancel: () => void;
};

export const debounce = <T extends (...args: any[]) => any>(
  func: T,
  delay: number = 300
): DebouncedFunction<T> => {
  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  
  const debounced = function(this: any, ...args: Parameters<T>) {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func.apply(this, args), delay);
  };

  debounced.cancel = () => {
    clearTimeout(timeoutId);
  };

  return debounced;
};

export const throttle = <T extends (...args: any[]) => any>(
  func: T,
  interval: number = 1000
): ((...args: Parameters<T>) => void) => {
  let lastCall = 0;
  let timeoutId: ReturnType<typeof setTimeout> | undefined;

  return function(this: any, ...args: Parameters<T>) {
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

export class RateLimiter {
  private maxCalls: number;
  private timeWindow: number;
  private calls: number[] = [];

  constructor(maxCalls: number = 10, timeWindow: number = 1000) {
    this.maxCalls = maxCalls;
    this.timeWindow = timeWindow;
  }

  canCall(): boolean {
    const now = Date.now();
    this.calls = this.calls.filter(timestamp => now - timestamp < this.timeWindow);
    return this.calls.length < this.maxCalls;
  }

  call<T>(func: () => T): T | Promise<never> {
    if (this.canCall()) {
      this.calls.push(Date.now());
      return func();
    } else {
      console.warn('Rate limit exceeded');
      return Promise.reject(new Error('Rate limit exceeded'));
    }
  }

  reset(): void {
    this.calls = [];
  }

  getCalls(): number {
    const now = Date.now();
    this.calls = this.calls.filter(timestamp => now - timestamp < this.timeWindow);
    return this.calls.length;
  }
}

export default { debounce, throttle, RateLimiter };
