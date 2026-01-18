/**
 * API Shim
 * Wrapper for API requests
 * 
 * Migrated to TypeScript: January 18, 2026
 */

import { request } from '../lib/api';

interface RequestConfig {
  params?: Record<string, any>;
  [key: string]: any;
}

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

async function call<T>(
  url: string,
  method?: string,
  payload?: any,
  config: RequestConfig = {}
): Promise<{ data: T }> {
  const { params, ...rest } = config || {};
  const options: any = { ...rest };
  if (method) options.method = method;
  if (payload !== undefined) options.body = payload;

  const finalUrl = buildUrl(url, params);
  const data = await request<T>(finalUrl, options);
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
  }
};

export default apiShim;
