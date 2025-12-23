/**
 * Robust API Client with Retry Logic
 * Handles failed API calls gracefully with exponential backoff
 */

import { request as apiRequest, ApiError } from '../lib/api';
import { ensureAuthToken, buildAuthHeaders } from './authToken';

class RobustApiClient {
  constructor(options = {}) {
    this.maxRetries = options.maxRetries || 1;  // Reduced from 3 to 1
    this.retryDelay = options.retryDelay || 2000;  // Increased from 1000 to 2000
    this.timeout = options.timeout || 30000;  // Increased from 10000 to 30000 (30 seconds)
    this.retryableStatusCodes = [408, 429, 500, 502, 503, 504];
    this.baseURL = (options.baseURL !== undefined ? options.baseURL : process.env.REACT_APP_API_BASE_URL || '').trim();
  }

  async fetchWithRetry(url, options = {}, retries = this.maxRetries) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    const {
      skipAuth = false,
      baseURL,
      headers: originalHeaders = {},
      body,
      method: providedMethod,
      params,
      ...requestOptions
    } = options;

    let headers = { ...originalHeaders };
    if (!skipAuth) {
      try {
        await ensureAuthToken();
      } catch (error) {
        console.warn('⚠️  Proceeding without auth token due to discovery error:', error.message);
      }
      headers = buildAuthHeaders(headers);
    }

    try {
      const normalizedMethod = (providedMethod || 'GET').toUpperCase();
      const payload = body === undefined ? requestOptions.body : body;
      const finalHeaders = { ...headers };

      let finalBody = payload;
      if (finalBody !== undefined && finalBody !== null && normalizedMethod !== 'GET') {
        if (typeof finalBody !== 'string') {
          finalBody = JSON.stringify(finalBody);
        }
        if (!finalHeaders['Content-Type']) {
          finalHeaders['Content-Type'] = 'application/json';
        }
      }

      const finalOptions = {
        ...requestOptions,
        method: normalizedMethod,
        headers: finalHeaders,
        body: normalizedMethod === 'GET' ? undefined : finalBody,
        signal: controller.signal,
      };

      const targetUrl = this.buildUrl(url, baseURL);
      const finalUrl = params ? this.appendParams(targetUrl, params) : targetUrl;

      const data = await apiRequest(finalUrl, finalOptions);
      clearTimeout(timeoutId);
      return data;
    } catch (error) {
      clearTimeout(timeoutId);

      const normalizedError = this.normalizeErrorInstance(error);

      if (retries > 0 && this.shouldRetry(normalizedError)) {
        const delay = this.calculateDelay(this.maxRetries - retries);
        console.log(`⚠️  API call failed, retrying ${url} in ${delay}ms (${retries} attempts left)`);
        
        await this.sleep(delay);
        return this.fetchWithRetry(url, options, retries - 1);
      }

      console.error(`❌ API call failed permanently: ${url}`, normalizedError);
      throw normalizedError;
    }
  }

  appendParams(url, params = {}) {
    const entries = Object.entries(params).filter(([, value]) => value !== undefined && value !== null);
    if (!entries.length) {
      return url;
    }
    const search = new URLSearchParams();
    entries.forEach(([key, value]) => {
      if (Array.isArray(value)) {
        value.forEach((item) => search.append(key, String(item)));
      } else {
        search.append(key, String(value));
      }
    });
    const query = search.toString();
    if (!query) {
      return url;
    }
    const separator = url.includes('?') ? '&' : '?';
    return `${url}${separator}${query}`;
  }

  normalizeErrorInstance(error) {
    if (error instanceof ApiError) {
      return error;
    }
    if (error && typeof error === 'object' && error !== null) {
      if (error.name === 'AbortError') {
        return error;
      }
      if (error.status) {
        return error;
      }
    }
    return error;
  }

  shouldRetry(error) {
    // Retry on network errors
    if (error.name === 'AbortError') {
      console.log('⏱️  Request timeout');
      return true;
    }

    if (error.name === 'TypeError') {
      console.log('🔌 Network error');
      return true;
    }

    // Retry on specific HTTP status codes
    if (error.status && this.retryableStatusCodes.includes(error.status)) {
      console.log(`🔄 Retryable status code: ${error.status}`);
      return true;
    }

    return false;
  }

  calculateDelay(attempt) {
    // Exponential backoff with jitter
    const exponentialDelay = this.retryDelay * Math.pow(2, attempt);
    const jitter = Math.random() * 1000; // Add up to 1 second of jitter
    return Math.min(exponentialDelay + jitter, 30000); // Max 30 seconds
  }

  buildUrl(path, overrideBase) {
    const base = (overrideBase !== undefined ? overrideBase : this.baseURL).trim();
    if (!base || /^https?:\/\//i.test(path)) {
      return path;
    }
    const normalizedBase = base.endsWith('/') ? base.slice(0, -1) : base;
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    return `${normalizedBase}${normalizedPath}`;
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // Convenience methods
  async get(url, options = {}) {
    return this.fetchWithRetry(url, { ...options, method: 'GET' });
  }

  async post(url, data, options = {}) {
    return this.fetchWithRetry(url, {
      ...options,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      body: JSON.stringify(data),
    });
  }

  async put(url, data, options = {}) {
    return this.fetchWithRetry(url, {
      ...options,
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      body: JSON.stringify(data),
    });
  }

  async delete(url, options = {}) {
    return this.fetchWithRetry(url, { ...options, method: 'DELETE' });
  }

  // Batch requests with retry
  async batchFetch(urls, options = {}) {
    const promises = urls.map(url => this.fetchWithRetry(url, options));
    return Promise.allSettled(promises);
  }
}

// Singleton instance
export const apiClient = new RobustApiClient({
  maxRetries: 3,
  retryDelay: 1000,
  timeout: 10000,
});

export default apiClient;
