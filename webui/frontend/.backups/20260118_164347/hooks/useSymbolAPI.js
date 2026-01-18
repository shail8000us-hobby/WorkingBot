import { useCallback } from 'react';
import { useSymbol } from '../context/SymbolContext';

/**
 * Hook to automatically add symbol parameter to API calls (v5.0)
 * 
 * Usage:
 *   const api = useSymbolAPI();
 *   const data = await api.fetch('/api/monitoring/status');
 *   // Automatically becomes: /api/monitoring/status?symbol=BTCUSD
 */
export const useSymbolAPI = () => {
  const { selectedSymbol, withSymbol, fetchWithSymbol } = useSymbol();

  /**
   * Add symbol parameter to URL
   */
  const addSymbolParam = useCallback((url) => {
    return withSymbol(url);
  }, [withSymbol]);

  /**
   * Fetch with automatic symbol parameter
   */
  const fetch = useCallback(async (url, options = {}) => {
    return fetchWithSymbol(url, options);
  }, [fetchWithSymbol]);

  /**
   * Fetch JSON with automatic symbol parameter
   */
  const fetchJSON = useCallback(async (url, options = {}) => {
    const response = await fetchWithSymbol(url, options);
    return response.json();
  }, [fetchWithSymbol]);

  /**
   * POST with automatic symbol parameter
   */
  const post = useCallback(async (url, data, options = {}) => {
    const response = await fetchWithSymbol(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      },
      body: JSON.stringify(data),
      ...options
    });
    return response.json();
  }, [fetchWithSymbol]);

  /**
   * GET with automatic symbol parameter
   */
  const get = useCallback(async (url, options = {}) => {
    const response = await fetchWithSymbol(url, {
      method: 'GET',
      ...options
    });
    return response.json();
  }, [fetchWithSymbol]);

  return {
    selectedSymbol,
    addSymbolParam,
    fetch,
    fetchJSON,
    post,
    get
  };
};

export default useSymbolAPI;
