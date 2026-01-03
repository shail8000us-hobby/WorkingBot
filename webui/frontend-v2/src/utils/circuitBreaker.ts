/**
 * Circuit Breaker Pattern
 * 
 * Prevents cascading failures by stopping requests to failing services
 * States: CLOSED (normal) -> OPEN (blocking) -> HALF_OPEN (testing)
 * 
 * Features:
 * - Automatic failure detection
 * - Exponential backoff retry
 * - Success rate monitoring
 * - Automatic recovery testing
 */

enum CircuitState {
  CLOSED = 'CLOSED',       // Normal operation
  OPEN = 'OPEN',           // Blocking all requests
  HALF_OPEN = 'HALF_OPEN'  // Testing recovery
}

interface CircuitBreakerConfig {
  failureThreshold: number;    // Failures before opening
  successThreshold: number;    // Successes to close from half-open
  timeout: number;             // Time before attempting recovery (ms)
  monitoringPeriod: number;    // Window for failure counting (ms)
}

interface CircuitStats {
  totalRequests: number;
  successCount: number;
  failureCount: number;
  consecutiveFailures: number;
  consecutiveSuccesses: number;
  lastFailureTime: number | null;
  lastSuccessTime: number | null;
  state: CircuitState;
}

export class CircuitBreaker {
  private state: CircuitState = CircuitState.CLOSED;
  private stats: CircuitStats = {
    totalRequests: 0,
    successCount: 0,
    failureCount: 0,
    consecutiveFailures: 0,
    consecutiveSuccesses: 0,
    lastFailureTime: null,
    lastSuccessTime: null,
    state: CircuitState.CLOSED
  };
  
  private nextAttemptTime: number = 0;
  private config: CircuitBreakerConfig;
  private serviceName: string;

  constructor(serviceName: string, config: Partial<CircuitBreakerConfig> = {}) {
    this.serviceName = serviceName;
    this.config = {
      failureThreshold: config.failureThreshold || 5,
      successThreshold: config.successThreshold || 2,
      timeout: config.timeout || 60000, // 1 minute
      monitoringPeriod: config.monitoringPeriod || 120000 // 2 minutes
    };
  }

  /**
   * Execute function with circuit breaker protection
   */
  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.state === CircuitState.OPEN) {
      if (Date.now() < this.nextAttemptTime) {
        const error = new Error(`Circuit breaker is OPEN for ${this.serviceName}`);
        error.name = 'CircuitBreakerError';
        throw error;
      }
      
      // Timeout elapsed, try half-open
      this.state = CircuitState.HALF_OPEN;
      console.log(`[CircuitBreaker:${this.serviceName}] Entering HALF_OPEN state`);
    }

    try {
      const result = await fn();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }

  private onSuccess(): void {
    this.stats.totalRequests++;
    this.stats.successCount++;
    this.stats.consecutiveSuccesses++;
    this.stats.consecutiveFailures = 0;
    this.stats.lastSuccessTime = Date.now();

    if (this.state === CircuitState.HALF_OPEN) {
      if (this.stats.consecutiveSuccesses >= this.config.successThreshold) {
        this.close();
      }
    }

    this.cleanOldStats();
  }

  private onFailure(): void {
    this.stats.totalRequests++;
    this.stats.failureCount++;
    this.stats.consecutiveFailures++;
    this.stats.consecutiveSuccesses = 0;
    this.stats.lastFailureTime = Date.now();

    if (this.state === CircuitState.HALF_OPEN) {
      // Single failure in half-open -> back to open
      this.open();
    } else if (this.state === CircuitState.CLOSED) {
      if (this.stats.consecutiveFailures >= this.config.failureThreshold) {
        this.open();
      }
    }

    this.cleanOldStats();
  }

  private open(): void {
    this.state = CircuitState.OPEN;
    this.nextAttemptTime = Date.now() + this.config.timeout;
    this.stats.state = CircuitState.OPEN;
    
    console.warn(
      `[CircuitBreaker:${this.serviceName}] OPEN - Blocking requests for ${this.config.timeout}ms`,
      { stats: this.getStats() }
    );
  }

  private close(): void {
    this.state = CircuitState.CLOSED;
    this.stats.consecutiveFailures = 0;
    this.stats.consecutiveSuccesses = 0;
    this.stats.state = CircuitState.CLOSED;
    
    console.log(
      `[CircuitBreaker:${this.serviceName}] CLOSED - Resuming normal operation`,
      { stats: this.getStats() }
    );
  }

  private cleanOldStats(): void {
    const now = Date.now();
    const cutoff = now - this.config.monitoringPeriod;

    // Reset old stats (simplified - in production use sliding window)
    if (this.stats.lastFailureTime && this.stats.lastFailureTime < cutoff) {
      this.stats.failureCount = 0;
    }
    if (this.stats.lastSuccessTime && this.stats.lastSuccessTime < cutoff) {
      this.stats.successCount = 0;
    }
  }

  /**
   * Get current circuit breaker statistics
   */
  getStats(): CircuitStats {
    return {
      ...this.stats,
      state: this.state
    };
  }

  /**
   * Get current state
   */
  getState(): CircuitState {
    return this.state;
  }

  /**
   * Check if circuit is allowing requests
   */
  isAvailable(): boolean {
    return this.state !== CircuitState.OPEN || Date.now() >= this.nextAttemptTime;
  }

  /**
   * Manually reset circuit breaker
   */
  reset(): void {
    this.state = CircuitState.CLOSED;
    this.stats = {
      totalRequests: 0,
      successCount: 0,
      failureCount: 0,
      consecutiveFailures: 0,
      consecutiveSuccesses: 0,
      lastFailureTime: null,
      lastSuccessTime: null,
      state: CircuitState.CLOSED
    };
    console.log(`[CircuitBreaker:${this.serviceName}] Manually reset`);
  }
}

/**
 * Circuit Breaker Manager
 * Manages multiple circuit breakers for different services
 */
export class CircuitBreakerManager {
  private breakers = new Map<string, CircuitBreaker>();

  /**
   * Get or create circuit breaker for service
   */
  getBreaker(serviceName: string, config?: Partial<CircuitBreakerConfig>): CircuitBreaker {
    if (!this.breakers.has(serviceName)) {
      this.breakers.set(serviceName, new CircuitBreaker(serviceName, config));
    }
    return this.breakers.get(serviceName)!;
  }

  /**
   * Execute function with circuit breaker protection
   */
  async execute<T>(
    serviceName: string, 
    fn: () => Promise<T>,
    config?: Partial<CircuitBreakerConfig>
  ): Promise<T> {
    const breaker = this.getBreaker(serviceName, config);
    return breaker.execute(fn);
  }

  /**
   * Get all circuit breaker stats
   */
  getAllStats(): Record<string, CircuitStats> {
    const stats: Record<string, CircuitStats> = {};
    this.breakers.forEach((breaker, name) => {
      stats[name] = breaker.getStats();
    });
    return stats;
  }

  /**
   * Reset all circuit breakers
   */
  resetAll(): void {
    this.breakers.forEach(breaker => breaker.reset());
  }

  /**
   * Reset specific circuit breaker
   */
  reset(serviceName: string): void {
    const breaker = this.breakers.get(serviceName);
    if (breaker) {
      breaker.reset();
    }
  }
}

// Global circuit breaker manager instance
export const circuitBreakerManager = new CircuitBreakerManager();
