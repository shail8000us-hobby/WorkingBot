/**
 * Instance API Hook (v6.0 Multi-Instance Support)
 *
 * Hook to automatically add instance parameter to API calls.
 * Replaces useSymbolAPI for instance-aware components.
 *
 * Usage:
 *   const api = useInstanceAPI();
 *   const data = await api.fetch('/api/monitoring/status');
 *   // Automatically becomes: /api/monitoring/status?instance=BTCUSD_LONG
 */
import { useCallback } from 'react';
import { useInstance } from '../context/InstanceContext';

export const useInstanceAPI = () => {
  const { selectedInstance, selectedSymbol, selectedMode, withInstance, fetchWithInstance } =
    useInstance();

  /**
   * Add instance parameter to URL
   */
  const addInstanceParam = useCallback(
    (url) => {
      return withInstance(url);
    },
    [withInstance]
  );

  /**
   * Fetch with automatic instance parameter
   */
  const fetch = useCallback(
    async (url, options = {}) => {
      return fetchWithInstance(url, options);
    },
    [fetchWithInstance]
  );

  /**
   * Fetch JSON with automatic instance parameter
   */
  const fetchJSON = useCallback(
    async (url, options = {}) => {
      const response = await fetchWithInstance(url, options);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      return response.json();
    },
    [fetchWithInstance]
  );

  /**
   * POST with automatic instance parameter
   */
  const post = useCallback(
    async (url, data, options = {}) => {
      const response = await fetchWithInstance(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
        body: JSON.stringify(data),
        ...options,
      });
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.message || `HTTP ${response.status}`);
      }
      return response.json();
    },
    [fetchWithInstance]
  );

  /**
   * GET with automatic instance parameter
   */
  const get = useCallback(
    async (url, options = {}) => {
      const response = await fetchWithInstance(url, {
        method: 'GET',
        ...options,
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      return response.json();
    },
    [fetchWithInstance]
  );

  /**
   * PUT with automatic instance parameter
   */
  const put = useCallback(
    async (url, data, options = {}) => {
      const response = await fetchWithInstance(url, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
        body: JSON.stringify(data),
        ...options,
      });
      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.message || `HTTP ${response.status}`);
      }
      return response.json();
    },
    [fetchWithInstance]
  );

  /**
   * DELETE with automatic instance parameter
   */
  const del = useCallback(
    async (url, options = {}) => {
      const response = await fetchWithInstance(url, {
        method: 'DELETE',
        ...options,
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      return response.json();
    },
    [fetchWithInstance]
  );

  return {
    // Current selection info
    selectedInstance,
    selectedSymbol,
    selectedMode,

    // URL helpers
    addInstanceParam,

    // HTTP methods
    fetch,
    fetchJSON,
    post,
    get,
    put,
    del,
  };
};

export default useInstanceAPI;
