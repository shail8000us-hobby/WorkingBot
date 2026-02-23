/**
 * API Shim
 * Wrapper for API requests with retry logic and circuit breaker protection.
 *
 * Migrated to TypeScript: January 18, 2026
 * Enhanced: Phase 5.4 — Added retry + circuit breaker (delegates to shared apiCircuit)
 */

import { request, ApiError } from '../lib/api';
import { apiCircuit } from './circuitBreaker';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const MAX_RETRIES = 2; // 1 original + 2 retries = 3 total attempts
const RETRY_DELAY_MS = 800;
const RETRYABLE_STATUS_CODES = new Set([408, 429, 500, 502, 503, 504]);

interface RequestConfig {
  params?: Record<string, any>;
  /** Override max retries for this call (0 = no retry) */
  maxRetries?: number;
  /** Skip circuit breaker for this call */
  skipCircuit?: boolean;
  [key: string]: any;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildUrl(url: string, params: Record<string, any> = {}): string {
  if (!params || typeof params !== 'object') {
    return url;
  }

  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null) return;
    if (Array.isArray(value)) {
      value.forEach((entry) => searchParams.append(key, String(entry)));
    } else {
      searchParams.append(key, String(value));
    }
  });

  if (!searchParams.toString()) return url;
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}${searchParams.toString()}`;
}

function wrapResponse<T>(data: T): { data: T } {
  return { data };
}

function isRetryable(error: unknown): boolean {
  if (error instanceof ApiError) {
    return typeof error.status !== 'number' || RETRYABLE_STATUS_CODES.has(error.status);
  }
  if (error && (error as any).name === 'AbortError') return true;
  // Network errors (no status) are retryable
  return !error || typeof (error as any).status !== 'number';
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ---------------------------------------------------------------------------
// Core call — retry + circuit breaker
// ---------------------------------------------------------------------------

async function call<T>(
  url: string,
  method?: string,
  payload?: any,
  config: RequestConfig = {}
): Promise<{ data: T }> {
  const { params, maxRetries: overrideRetries, skipCircuit, ...rest } = config || {};
  const options: any = { ...rest };
  if (method) options.method = method;
  if (payload !== undefined) options.body = payload;

  const finalUrl = buildUrl(url, params);
  const retries = overrideRetries !== undefined ? overrideRetries : MAX_RETRIES;

  const doRequest = async (): Promise<T> => {
    let lastError: unknown;
    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        return await request<T>(finalUrl, options);
      } catch (error) {
        lastError = error;
        if (attempt < retries && isRetryable(error)) {
          const delay = RETRY_DELAY_MS * Math.pow(2, attempt);
          await sleep(delay);
          continue;
        }
        throw error;
      }
    }
    throw lastError; // unreachable but satisfies TypeScript
  };

  const data = skipCircuit
    ? await doRequest()
    : await apiCircuit.call(doRequest);

  return wrapResponse(data);
}

const apiShim = {
  get<T = any>(url: string, config?: RequestConfig): Promise<{ data: T }> {
    return call<T>(url, 'GET', undefined, config);
  },
  delete<T = any>(url: string, config?: RequestConfig): Promise<{ data: T }> {
    return call<T>(url, 'DELETE', undefined, config);
  },
  post<T = any>(url: string, data?: any, config?: RequestConfig): Promise<{ data: T }> {
    return call<T>(url, 'POST', data, config);
  },
  put<T = any>(url: string, data?: any, config?: RequestConfig): Promise<{ data: T }> {
    return call<T>(url, 'PUT', data, config);
  },
  patch<T = any>(url: string, data?: any, config?: RequestConfig): Promise<{ data: T }> {
    return call<T>(url, 'PATCH', data, config);
  },
};

export default apiShim;
