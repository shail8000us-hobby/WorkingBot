import { request as apiRequest, ApiError } from '../lib/api';
import { ensureAuthToken, buildAuthHeaders } from './authToken';
import { apiCircuit } from './circuitBreaker'; // Week 2: Circuit breaker integration

/**
 * API Client - Robust HTTP request handling with retry logic and circuit breaker
 * Provides automatic retries, error handling, request queueing, and fail-fast protection
 * 
 * Enhanced: November 12, 2025 - Added circuit breaker protection
 */

const DEFAULT_BASE_URL = (process.env.REACT_APP_API_BASE_URL || '').trim();

class APIClient {
  constructor(config = {}) {
    this.config = {
      baseURL: config.baseURL !== undefined ? config.baseURL : DEFAULT_BASE_URL,
      timeout: 30000,  // Increased from 10s to 30s to prevent premature aborts
      maxRetries: 3,
      retryDelay: 1000,
      retryStatusCodes: [408, 429, 500, 502, 503, 504],
      ...config
    };

    this.baseURL = (this.config.baseURL || '').replace(/\/$/, '');
    this.requestQueue = [];
    this.processing = false;
  }

  buildFullUrl(path, params = undefined) {
    let finalPath = path || '';
    const absolute = /^https?:\/\//i.test(finalPath);

    if (!absolute) {
      const normalizedPath = finalPath.startsWith('/') ? finalPath : `/${finalPath}`;
      finalPath = this.baseURL ? `${this.baseURL}${normalizedPath}` : normalizedPath;
    }

    if (params && typeof params === 'object' && Object.keys(params).length > 0) {
      const searchParams = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value === undefined || value === null) {
          return;
        }
        if (Array.isArray(value)) {
          value.forEach((entry) => {
            searchParams.append(key, String(entry));
          });
        } else {
          searchParams.append(key, String(value));
        }
      });

      const query = searchParams.toString();
      if (query) {
        finalPath += finalPath.includes('?') ? `&${query}` : `?${query}`;
      }
    }

    return finalPath;
  }

  /**
   * Make request with retry logic and circuit breaker protection
   * Week 2: Wrapped with circuit breaker to fail fast when backend is down
   */
  async request(method, url, data = null, options = {}) {
    // Wrap entire request logic in circuit breaker
    return await apiCircuit.call(async () => {
      return await this._requestImpl(method, url, data, options);
    });
  }

  /**
   * Internal request implementation (called by circuit breaker)
   * @private
   */
  async _requestImpl(method, url, data = null, options = {}) {
    const normalizedMethod = (method || 'GET').toUpperCase();
    const {
      skipAuth = false,
      maxRetries: overrideRetries,
      headers: optionHeaders = {},
      params: optionParams,
      ...fetchOverrides
    } = options || {};

    const maxRetries = overrideRetries !== undefined ? overrideRetries : this.config.maxRetries;
    let lastError = null;

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      let timeoutId;
      try {
        let headers = {
          'Content-Type': 'application/json',
          ...optionHeaders
        };

        if (!skipAuth) {
          try {
            await ensureAuthToken();
          } catch (authError) {
            console.warn('⚠️  Proceeding without auth token due to discovery error:', authError.message);
          }
          headers = buildAuthHeaders(headers);
        }

        const isGetLike = normalizedMethod === 'GET';
        const params = isGetLike && data && typeof data === 'object' ? data : optionParams;
        const finalUrl = this.buildFullUrl(url, params);

        const requestOptions = {
          ...fetchOverrides,
          method: normalizedMethod,
          headers
        };

        if (!isGetLike && data !== null && data !== undefined) {
          requestOptions.body = data;
        }

        if (!requestOptions.signal && this.config.timeout) {
          const abortController = new AbortController();
          timeoutId = setTimeout(() => abortController.abort(), this.config.timeout);
          requestOptions.signal = abortController.signal;
        }

        console.log(`📤 API ${normalizedMethod} ${finalUrl} (attempt ${attempt + 1}/${maxRetries + 1})`);
        const responseData = await apiRequest(finalUrl, requestOptions);
        if (timeoutId) {
          clearTimeout(timeoutId);
        }
        console.log(`✅ API ${normalizedMethod} ${finalUrl} succeeded`);
        return responseData;
      } catch (error) {
        if (timeoutId) {
          clearTimeout(timeoutId);
        }
        lastError = error;
        const retryable = attempt < maxRetries && this.isRetryableError(error);
        console.error(`❌ API ${method} ${url} failed:`, error.message || error);
        if (retryable) {
          const delay = this.config.retryDelay * Math.pow(2, attempt);
          console.log(`⏳ Retrying in ${delay}ms...`);
          await this.sleep(delay);
          continue;
        }
        throw this.normalizeError(error);
      }
    }

    throw this.normalizeError(lastError);
  }

  /**
   * Check if error is retryable
   */
  isRetryableError(error) {
    if (error instanceof ApiError) {
      if (typeof error.status !== 'number') {
        return true;
      }
      return this.config.retryStatusCodes.includes(error.status);
    }
    if (error && error.name === 'AbortError') {
      return true;
    }
    return !error || typeof error.status !== 'number';
  }

  /**
   * Normalize error for consistent handling
   */
  normalizeError(error) {
    if (error instanceof ApiError) {
      return {
        success: false,
        message: error.details?.message || error.message || 'Request failed',
        code: error.status ? `HTTP_${error.status}` : 'NETWORK_ERROR',
        status: error.status,
        data: error.details,
        original: error
      };
    }
    if (error && error.name === 'AbortError') {
      return {
        success: false,
        message: 'Request timed out',
        code: 'TIMEOUT',
        original: error
      };
    }
    return {
      success: false,
      message: (error && error.message) || 'Network error',
      code: 'NETWORK_ERROR',
      original: error
    };
  }

  /**
   * Sleep helper
   */
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // Convenience methods for different HTTP verbs

  async get(url, params = null, options = {}) {
    return this.request('get', url, params, options);
  }

  async post(url, data = null, options = {}) {
    return this.request('post', url, data, options);
  }

  async put(url, data = null, options = {}) {
    return this.request('put', url, data, options);
  }

  async delete(url, data = null, options = {}) {
    return this.request('delete', url, data, options);
  }

  // Bot-specific API methods

  async getConfig() {
    return this.get('/api/config/flat');
  }

  async updateConfig(updates) {
    return this.post('/api/config', updates);
  }

  async getBotStatus() {
    return this.get('/api/bot/status');
  }

  async startBot() {
    return this.post('/api/bot/start');
  }

  async stopBot() {
    return this.post('/api/bot/stop');
  }

  async startTmuxSession() {
    return this.post('/api/tmux/start');
  }

  async stopTmuxSession() {
    return this.post('/api/tmux/stop');
  }

  // PM2 Process Management API methods

  async getPM2Enabled() {
    return this.get('/api/pm2/enabled');
  }

  async getPM2Status() {
    return this.get('/api/pm2/status');
  }

  async startPM2Process(name) {
    return this.post(`/api/pm2/start/${name}`);
  }

  async stopPM2Process(name) {
    return this.post(`/api/pm2/stop/${name}`);
  }

  async restartPM2Process(name) {
    return this.post(`/api/pm2/restart/${name}`);
  }

  async reloadPM2Process(name) {
    return this.post(`/api/pm2/reload/${name}`);
  }

  async getPM2ProcessDetails(name) {
    return this.get(`/api/pm2/process/${name}`);
  }

  async getPM2Logs(name, lines = 100, type = 'all') {
    return this.get(`/api/pm2/logs/${name}`, { lines, type });
  }

  async flushPM2Logs() {
    return this.post('/api/pm2/flush-logs');
  }

  async savePM2State() {
    return this.post('/api/pm2/save');
  }

  async restartBot() {
    return this.post('/api/bot/restart');
  }

  async getLogs(lines = 50) {
    return this.get('/api/logs', { lines });
  }

  async getPositions() {
    return this.get('/api/positions');
  }

  async getTradingMode() {
    return this.get('/api/trading-mode');
  }

  async setTradingMode(mode) {
    return this.post('/api/trading-mode', { mode });
  }

  async getGuardianStatus() {
    return this.get('/api/guardian/status');
  }

  async startGuardian() {
    return this.post('/api/guardian/start');
  }

  async stopGuardian() {
    return this.post('/api/guardian/stop');
  }

  async getMonitorStatus() {
    return this.get('/api/monitor/status');
  }

  async startMonitor() {
    return this.post('/api/monitor/start');
  }

  async stopMonitor() {
    return this.post('/api/monitor/stop');
  }

  async emergencyStop() {
    return this.post('/api/emergency/stop');
  }

  async closeAllPositions() {
    return this.post('/api/emergency/close-all');
  }

  async cancelAllOrders() {
    return this.post('/api/emergency/cancel-all');
  }

  /**
   * Batch multiple requests with error isolation
   */
  async batchRequest(requests) {
    const results = await Promise.allSettled(
      requests.map(req => this.request(req.method, req.url, req.data, req.options))
    );

    return results.map((result, index) => {
      if (result.status === 'fulfilled') {
        return { success: true, data: result.value, request: requests[index] };
      } else {
        return { success: false, error: result.reason, request: requests[index] };
      }
    });
  }

  /**
   * Health check
   */
  async healthCheck() {
    try {
      const start = Date.now();
      await this.get('/api/health', null, { timeout: 5000, maxRetries: 0 });
      const latency = Date.now() - start;
      return { healthy: true, latency };
    } catch (error) {
      return { healthy: false, error: error.message };
    }
  }
}

// Create singleton instance
const apiClient = new APIClient();

export default apiClient;
export { APIClient };
