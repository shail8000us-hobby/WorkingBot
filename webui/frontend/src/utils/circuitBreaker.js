/**
 * Frontend Circuit Breaker
 * 
 * Prevents hammering dead backend by failing fast after threshold failures.
 * Mirrors backend circuit breaker pattern for consistency.
 * 
 * States:
 * - CLOSED: Normal operation (requests go through)
 * - OPEN: Service failing (fail fast without calling backend)
 * - HALF_OPEN: Testing recovery (limited requests)
 * 
 * Usage:
 *   const result = await apiCircuit.call(async () => {
 *     return await fetch('/api/endpoint');
 *   });
 * 
 * Date: November 12, 2025
 * Part of: WebUI Robustness Plan Week 2
 */

const CircuitState = {
  CLOSED: 'CLOSED',      // Normal operation
  OPEN: 'OPEN',          // Failing, reject requests
  HALF_OPEN: 'HALF_OPEN' // Testing recovery
};

class CircuitBreaker {
  /**
   * Create a circuit breaker
   * 
   * @param {string} name - Identifier for logging
   * @param {number} threshold - Number of failures before opening (default: 3)
   * @param {number} timeout - Milliseconds to wait before attempting HALF_OPEN (default: 15000)
   */
  constructor(name, threshold = 3, timeout = 15000) {
    this.name = name;
    this.threshold = threshold;
    this.timeout = timeout;
    
    this.state = CircuitState.CLOSED;
    this.failureCount = 0;
    this.successCount = 0;
    this.lastFailureTime = null;
    this.nextAttemptTime = null;
  }
  
  /**
   * Execute function with circuit breaker protection
   * 
   * @param {Function} func - Async function to execute
   * @returns {Promise} Result of func or throws error
   */
  async call(func) {
    // Check if circuit is OPEN
    if (this.state === CircuitState.OPEN) {
      const now = Date.now();
      
      // Check if timeout expired, transition to HALF_OPEN
      if (now >= this.nextAttemptTime) {
        this.state = CircuitState.HALF_OPEN;
        this.successCount = 0;
        console.log(`🔄 Circuit ${this.name}: HALF_OPEN (testing recovery)`);
      } else {
        const waitTime = Math.ceil((this.nextAttemptTime - now) / 1000);
        throw new Error(
          `Circuit ${this.name} is OPEN (retry in ${waitTime}s)`
        );
      }
    }
    
    // Try to execute function
    try {
      const result = await func();
      this._onSuccess();
      return result;
    } catch (error) {
      this._onFailure();
      throw error;
    }
  }
  
  /**
   * Handle successful execution
   * @private
   */
  _onSuccess() {
    this.failureCount = 0;
    
    if (this.state === CircuitState.HALF_OPEN) {
      this.successCount++;
      
      // Need 2 successes to close circuit
      if (this.successCount >= 2) {
        this.state = CircuitState.CLOSED;
        this.successCount = 0;
        console.log(`✅ Circuit ${this.name}: CLOSED (service recovered)`);
      }
    }
  }
  
  /**
   * Handle failed execution
   * @private
   */
  _onFailure() {
    this.failureCount++;
    this.lastFailureTime = Date.now();
    
    if (this.state === CircuitState.HALF_OPEN) {
      // Any failure in HALF_OPEN reopens circuit
      this.state = CircuitState.OPEN;
      this.nextAttemptTime = Date.now() + this.timeout;
      console.error(`🔴 Circuit ${this.name}: OPEN (still failing)`);
    } else if (this.state === CircuitState.CLOSED) {
      // Check if threshold reached
      if (this.failureCount >= this.threshold) {
        this.state = CircuitState.OPEN;
        this.nextAttemptTime = Date.now() + this.timeout;
        console.error(
          `🔴 Circuit ${this.name}: OPEN ` +
          `(${this.failureCount} failures, timeout: ${this.timeout}ms)`
        );
      }
    }
  }
  
  /**
   * Get current circuit breaker state
   * @returns {Object} State information
   */
  getState() {
    return {
      name: this.name,
      state: this.state,
      failureCount: this.failureCount,
      successCount: this.successCount,
      lastFailureTime: this.lastFailureTime,
      nextAttemptTime: this.nextAttemptTime,
      isOpen: this.state === CircuitState.OPEN,
      timeUntilRetry: this.state === CircuitState.OPEN 
        ? Math.max(0, this.nextAttemptTime - Date.now())
        : 0
    };
  }
  
  /**
   * Manually reset circuit breaker to CLOSED
   * Useful for admin/testing purposes
   */
  reset() {
    this.state = CircuitState.CLOSED;
    this.failureCount = 0;
    this.successCount = 0;
    this.lastFailureTime = null;
    this.nextAttemptTime = null;
    console.log(`🔄 Circuit ${this.name}: Manually reset to CLOSED`);
  }
  
  /**
   * Force circuit OPEN (for testing)
   */
  forceOpen() {
    this.state = CircuitState.OPEN;
    this.nextAttemptTime = Date.now() + this.timeout;
    console.log(`🔴 Circuit ${this.name}: Forced OPEN`);
  }
}

// =============================================
// Global Circuit Breaker Instances
// =============================================

/**
 * Backend API circuit breaker
 * Protects against hammering dead Flask backend
 * Threshold increased to 5 to reduce false positives from slow responses
 */
export const apiCircuit = new CircuitBreaker('backend_api', 5, 20000);

/**
 * WebSocket circuit breaker
 * Protects against repeated WebSocket reconnection attempts
 */
export const wsCircuit = new CircuitBreaker('websocket', 5, 30000);

/**
 * Get all circuit breaker states
 * Useful for dashboard/debugging
 */
export function getAllCircuitStates() {
  return {
    backend_api: apiCircuit.getState(),
    websocket: wsCircuit.getState()
  };
}

/**
 * Reset all circuit breakers
 * Useful for admin override
 */
export function resetAllCircuits() {
  apiCircuit.reset();
  wsCircuit.reset();
}

export default CircuitBreaker;
