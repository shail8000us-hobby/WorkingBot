/**
 * Frontend Circuit Breaker
 * Prevents hammering dead backend by failing fast
 * 
 * Migrated to TypeScript: January 18, 2026
 */

export enum CircuitState {
  CLOSED = 'CLOSED',
  OPEN = 'OPEN',
  HALF_OPEN = 'HALF_OPEN'
}

export class CircuitBreaker {
  name: string;
  threshold: number;
  timeout: number;
  state: CircuitState = CircuitState.CLOSED;
  failureCount: number = 0;
  successCount: number = 0;
  lastFailureTime: number | null = null;
  nextAttemptTime: number | null = null;

  constructor(name: string, threshold: number = 3, timeout: number = 15000) {
    this.name = name;
    this.threshold = threshold;
    this.timeout = timeout;
  }

  async call<T>(func: () => Promise<T>): Promise<T> {
    if (this.state === CircuitState.OPEN) {
      const now = Date.now();
      if (now >= (this.nextAttemptTime || 0)) {
        this.state = CircuitState.HALF_OPEN;
        this.successCount = 0;
        console.log(`🔄 Circuit ${this.name}: HALF_OPEN`);
      } else {
        const waitTime = Math.ceil(((this.nextAttemptTime || 0) - now) / 1000);
        throw new Error(`Circuit ${this.name} is OPEN (retry in ${waitTime}s)`);
      }
    }

    try {
      const result = await func();
      this._onSuccess();
      return result;
    } catch (error) {
      this._onFailure();
      throw error;
    }
  }

  private _onSuccess(): void {
    this.failureCount = 0;
    if (this.state === CircuitState.HALF_OPEN) {
      this.successCount++;
      if (this.successCount >= 2) {
        this.state = CircuitState.CLOSED;
        this.successCount = 0;
        console.log(`✅ Circuit ${this.name}: CLOSED`);
      }
    }
  }

  private _onFailure(): void {
    this.failureCount++;
    this.lastFailureTime = Date.now();
    if (this.state === CircuitState.HALF_OPEN) {
      this.state = CircuitState.OPEN;
      this.nextAttemptTime = Date.now() + this.timeout;
      console.warn(`⚠️ Circuit ${this.name}: OPEN`);
    } else if (this.failureCount >= this.threshold) {
      this.state = CircuitState.OPEN;
      this.nextAttemptTime = Date.now() + this.timeout;
      console.warn(`⚠️ Circuit ${this.name}: OPEN (${this.failureCount} failures)`);
    }
  }

  reset(): void {
    this.state = CircuitState.CLOSED;
    this.failureCount = 0;
    this.successCount = 0;
    this.lastFailureTime = null;
    this.nextAttemptTime = null;
  }

  getState(): CircuitState {
    return this.state;
  }
}

export const apiCircuit = new CircuitBreaker('backend_api', 5, 20000);
export const wsCircuit = new CircuitBreaker('websocket', 5, 30000);

export default CircuitBreaker;
