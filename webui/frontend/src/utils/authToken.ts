/**
 * Auth Token Management
 * 
 * Migrated to TypeScript: January 18, 2026
 * Safe: Pure utility functions for token management
 */

import { request as apiRequest } from '../lib/api';

const STORAGE_KEY = 'WEBUI_AUTH_TOKEN';
const AUTH_CONFIG_PATH = '/api/auth/config';

export interface AuthMetadata {
  checked: boolean;
  authRequired: boolean | null;
  tokenEphemeral?: boolean;
  modes?: string[];
}

export interface AuthConfig {
  auth_required: boolean;
  token_ephemeral?: boolean;
  modes?: string[];
  token?: string;
  basic_username?: string;
}

export interface SetAuthTokenOptions {
  persist?: boolean;
}

let cachedToken: string | undefined;
let authMetadata: AuthMetadata = {
  checked: false,
  authRequired: null,
};
let pendingDiscovery: Promise<string> | null = null;

const normalize = (value: any): string => (typeof value === 'string' ? value.trim() : '');

const resolveBaseUrl = (): string => {
  const base = (process.env.REACT_APP_API_BASE_URL || '').trim();
  return base ? base.replace(/\/+$/, '') : '';
};

export const getAuthToken = (): string => {
  if (cachedToken !== undefined) {
    return cachedToken;
  }

  const envToken = normalize(process.env.REACT_APP_WEBUI_AUTH_TOKEN);
  if (envToken) {
    cachedToken = envToken;
    return cachedToken;
  }

  if (typeof window !== 'undefined') {
    const globalToken = normalize((window as any).__WEBUI_AUTH_TOKEN__ || (window as any).WEBUI_AUTH_TOKEN);
    if (globalToken) {
      cachedToken = globalToken;
      return cachedToken;
    }

    try {
      const stored = normalize(window.localStorage.getItem(STORAGE_KEY));
      if (stored) {
        cachedToken = stored;
        return cachedToken;
      }
    } catch (err) {
      console.warn('⚠️  Unable to access localStorage for auth token', err);
    }
  }

  cachedToken = '';
  return cachedToken;
};

export const setAuthToken = (token: string, { persist = true }: SetAuthTokenOptions = {}): string => {
  const normalized = normalize(token);
  cachedToken = normalized;

  if (typeof window !== 'undefined') {
    try {
      if (normalized && persist) {
        window.localStorage.setItem(STORAGE_KEY, normalized);
      } else {
        window.localStorage.removeItem(STORAGE_KEY);
      }
    } catch (err) {
      console.warn('⚠️  Unable to update stored auth token', err);
    }
    (window as any).__WEBUI_AUTH_TOKEN__ = normalized || undefined;
  }

  return cachedToken;
};

export const clearAuthToken = (): string => setAuthToken('', { persist: false });

export const authIsRequired = (): boolean => Boolean(authMetadata.authRequired);

export const buildAuthHeaders = (headers: Record<string, string> = {}): Record<string, string> => {
  const token = getAuthToken();
  if (!token) {
    return headers;
  }
  return {
    ...headers,
    Authorization: `Bearer ${token}`,
  };
};

export const ensureAuthToken = async (): Promise<string> => {
  const existing = getAuthToken();
  if (authMetadata.checked) {
    if (!authMetadata.authRequired || existing) {
      return existing;
    }
  } else if (existing) {
    // No server discovery yet, but we already have a token (env/local).
    return existing;
  }

  if (pendingDiscovery) {
    return pendingDiscovery;
  }

  const base = resolveBaseUrl();
  const url = `${base}${AUTH_CONFIG_PATH}`;

  pendingDiscovery = (async () => {
    try {
      const data: AuthConfig = await apiRequest(url, {
        headers: { Accept: 'application/json' },
        cache: 'no-store',
      });
      authMetadata = {
        checked: true,
        authRequired: Boolean(data.auth_required),
        tokenEphemeral: Boolean(data.token_ephemeral),
        modes: data.modes || [],
      };

      if (!authMetadata.authRequired) {
        clearAuthToken();
        return '';
      }

      if (data.token) {
        setAuthToken(data.token);
      }

      if (data.basic_username) {
        console.info(`ℹ️  WebUI Basic auth configured for user "${data.basic_username}".`);
      }

      return getAuthToken();
    } catch (error: any) {
      console.warn('⚠️  Unable to fetch auth configuration:', error.message);
      throw error;
    } finally {
      pendingDiscovery = null;
    }
  })();

  return pendingDiscovery;
};

export const getAuthMetadata = (): AuthMetadata => ({ ...authMetadata });
