import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';

/**
 * SymbolContext - Global state for selected trading symbol (v5.0)
 * Phase 3: Smart Symbol Switching
 *
 * Manages:
 * - Current selected symbol
 * - Available symbols list
 * - Symbol status updates
 * - Automatic API parameter injection
 * - Symbol data caching (30s TTL)
 * - Dirty state tracking for unsaved changes
 */
export const SymbolContext = createContext();

export const useSymbol = () => {
  const context = useContext(SymbolContext);
  if (!context) {
    throw new Error('useSymbol must be used within SymbolProvider');
  }
  return context;
};

// Safe hook that doesn't throw when used outside provider
export const useSymbolSafe = () => {
  const context = useContext(SymbolContext);
  if (!context) {
    // Return fallback values when not in SymbolProvider
    return {
      selectedSymbol: null,
      symbols: [],
      loading: true,
      fetchWithSymbol: (url) => fetch(url),
      withSymbol: (url) => url,
      changeSymbol: () => false,
      loadSymbols: () => {},
      getCurrentSymbol: () => null,
      markDirty: () => {},
      clearDirty: () => {},
      dirtyState: false,
      symbolDataCache: {},
      cacheSymbolData: () => {},
      getCachedData: () => null,
      invalidateCache: () => {},
    };
  }
  return context;
};

export const SymbolProvider = ({ children }) => {
  const [selectedSymbol, setSelectedSymbol] = useState(null);
  const [symbols, setSymbols] = useState([]);
  const [loading, setLoading] = useState(true);
  const [symbolDataCache, setSymbolDataCache] = useState({});
  const [dirtyState, setDirtyState] = useState(false);

  // Refs for cache management
  const cacheTimestamps = useRef({});
  const loadSymbolsInFlightRef = useRef(false);
  const loadSymbolsPendingRef = useRef(false);
  const CACHE_TTL = 30000; // 30 seconds

  // Load symbols from API
  const loadSymbols = useCallback(async () => {
    if (loadSymbolsInFlightRef.current) {
      loadSymbolsPendingRef.current = true;
      return;
    }

    loadSymbolsInFlightRef.current = true;
    try {
      const response = await fetch('/api/symbols');
      const data = await response.json();

      if (data.symbols) {
        setSymbols(data.symbols);

        // Auto-select first enabled symbol if none selected
        setSelectedSymbol((prev) => {
          if (prev) return prev; // Already have selection, keep it

          if (data.symbols.length > 0) {
            const saved = localStorage.getItem('selectedSymbol');
            const symbol = saved
              ? data.symbols.find((s) => s.name === saved)
              : data.symbols.find((s) => s.enabled) || data.symbols[0];

            if (symbol) {
              localStorage.setItem('selectedSymbol', symbol.name);
              return symbol.name;
            }
          }
          return prev;
        });
      }
    } catch (err) {
      console.error('Failed to load symbols:', err);
    } finally {
      setLoading(false);
      loadSymbolsInFlightRef.current = false;
      if (loadSymbolsPendingRef.current) {
        loadSymbolsPendingRef.current = false;
        Promise.resolve().then(() => {
          loadSymbols();
        });
      }
    }
  }, []); // Remove selectedSymbol dependency to prevent loop

  useEffect(() => {
    loadSymbols();
    const interval = setInterval(loadSymbols, 30000); // Refresh every 30s (reduced from 10s)
    return () => clearInterval(interval);
  }, [loadSymbols]);

  // Change selected symbol (Phase 3: Smart Switching)
  const changeSymbol = useCallback(
    (symbolName, options = {}) => {
      const { force = false } = options;

      // Check for unsaved changes
      if (dirtyState && !force) {
        const confirmed = window.confirm(
          `You have unsaved changes. Switch to ${symbolName} anyway?\n\n` +
            'Unsaved changes will be lost.'
        );
        if (!confirmed) return false;
      }

      // Update selected symbol
      setSelectedSymbol(symbolName);
      localStorage.setItem('selectedSymbol', symbolName);

      // Clear dirty state after switch
      setDirtyState(false);

      console.log(`✅ Switched to symbol: ${symbolName}`);
      return true;
    },
    [dirtyState]
  );

  // Mark form as dirty (has unsaved changes)
  const markDirty = useCallback(() => {
    setDirtyState(true);
  }, []);

  // Clear dirty state
  const clearDirty = useCallback(() => {
    setDirtyState(false);
  }, []);

  // Cache symbol data
  const cacheSymbolData = useCallback((symbolName, data) => {
    setSymbolDataCache((prev) => ({
      ...prev,
      [symbolName]: data,
    }));
    cacheTimestamps.current[symbolName] = Date.now();
  }, []);

  // Get cached symbol data (if fresh)
  const getCachedData = useCallback(
    (symbolName) => {
      const timestamp = cacheTimestamps.current[symbolName];
      const now = Date.now();

      if (timestamp && now - timestamp < CACHE_TTL) {
        return symbolDataCache[symbolName];
      }
      return null;
    },
    [symbolDataCache, CACHE_TTL]
  );

  // Invalidate cache for symbol
  const invalidateCache = useCallback((symbolName) => {
    setSymbolDataCache((prev) => {
      const newCache = { ...prev };
      delete newCache[symbolName];
      return newCache;
    });
    delete cacheTimestamps.current[symbolName];
  }, []);

  // Get current symbol details
  const getCurrentSymbol = useCallback(() => {
    return symbols.find((s) => s.name === selectedSymbol) || null;
  }, [symbols, selectedSymbol]);

  // Helper: Add symbol parameter to API URL
  const withSymbol = useCallback(
    (url) => {
      if (!selectedSymbol) return url;

      const separator = url.includes('?') ? '&' : '?';
      return `${url}${separator}symbol=${selectedSymbol}`;
    },
    [selectedSymbol]
  );

  // Helper: Fetch with automatic symbol parameter
  const fetchWithSymbol = useCallback(
    async (url, options = {}) => {
      const urlWithSymbol = withSymbol(url);
      return fetch(urlWithSymbol, options);
    },
    [withSymbol]
  );

  const value = {
    // State
    selectedSymbol,
    symbols,
    loading,
    symbolDataCache,
    dirtyState,

    // Actions
    changeSymbol,
    loadSymbols,
    getCurrentSymbol,
    markDirty,
    clearDirty,

    // Cache management (Phase 3)
    cacheSymbolData,
    getCachedData,
    invalidateCache,

    // Helpers
    withSymbol,
    fetchWithSymbol,
  };

  return <SymbolContext.Provider value={value}>{children}</SymbolContext.Provider>;
};
