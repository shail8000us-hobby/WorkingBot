import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';

/**
 * InstanceContext - Global state for selected trading instance (v6.0)
 *
 * V6.0 ARCHITECTURE: Instance = Symbol + Mode
 * Examples: BTCUSD_LONG, BTCUSD_SHORT, ETHUSD_LONG
 *
 * This enables:
 * - Same symbol trading in LONG and SHORT simultaneously
 * - Independent configuration per instance
 * - Separate databases per instance
 * - Opposite RSI thresholds (LONG stops at oversold, SHORT stops at overbought)
 *
 * Manages:
 * - Current selected instance
 * - Available instances list
 * - Instance status updates
 * - Automatic API parameter injection
 * - Instance data caching (30s TTL)
 * - Dirty state tracking for unsaved changes
 */
export const InstanceContext = createContext();

export const useInstance = () => {
  const context = useContext(InstanceContext);
  if (!context) {
    throw new Error('useInstance must be used within InstanceProvider');
  }
  return context;
};

// Safe hook that doesn't throw when used outside provider
export const useInstanceSafe = () => {
  const context = useContext(InstanceContext);
  if (!context) {
    // Return fallback values when not in InstanceProvider
    return {
      selectedInstance: null,
      instances: [],
      loading: true,
      isV6: false,
      fetchWithInstance: (url) => fetch(url),
      withInstance: (url) => url,
      changeInstance: () => false,
      loadInstances: () => {},
      getCurrentInstance: () => null,
      getInstancesForSymbol: () => [],
      markDirty: () => {},
      clearDirty: () => {},
      dirtyState: false,
      instanceDataCache: {},
      cacheInstanceData: () => {},
      getCachedData: () => null,
      invalidateCache: () => {},
    };
  }
  return context;
};

// Parse instance name into symbol and mode
export const parseInstanceName = (instanceName) => {
  if (!instanceName) return { symbol: null, mode: null };
  const parts = instanceName.split('_');
  if (parts.length >= 2) {
    const mode = parts[parts.length - 1];
    const symbol = parts.slice(0, -1).join('_');
    return { symbol, mode };
  }
  return { symbol: instanceName, mode: null };
};

// Create instance name from symbol and mode
export const makeInstanceName = (symbol, mode) => {
  if (!symbol || !mode) return null;
  return `${symbol}_${mode.toUpperCase()}`;
};

export const InstanceProvider = ({ children }) => {
  const [selectedInstance, setSelectedInstance] = useState(null);
  const [instances, setInstances] = useState([]);
  const [loading, setLoading] = useState(true);
  const [instanceDataCache, setInstanceDataCache] = useState({});
  const [dirtyState, setDirtyState] = useState(false);
  const [isV6, setIsV6] = useState(false);

  // Refs for cache management
  const cacheTimestamps = useRef({});
  const CACHE_TTL = 30000; // 30 seconds

  // Load instances from API
  const loadInstances = useCallback(async () => {
    try {
      // Try v6.0 instances API first
      let response = await fetch('/api/instances');
      let data = await response.json();

      if (data.instances && data.instances.length > 0) {
        setInstances(data.instances);
        setIsV6(true);

        // Auto-select first enabled instance if none selected
        setSelectedInstance((prev) => {
          if (prev) {
            // Verify current selection still exists
            const exists = data.instances.find((i) => i.name === prev);
            if (exists) return prev;
          }

          // Try to restore from localStorage
          const saved = localStorage.getItem('selectedInstance');
          if (saved) {
            const instance = data.instances.find((i) => i.name === saved);
            if (instance && instance.enabled) {
              return saved;
            }
          }

          // Find first enabled instance
          const enabled = data.instances.find((i) => i.enabled);
          if (enabled) {
            localStorage.setItem('selectedInstance', enabled.name);
            return enabled.name;
          }

          // Fallback to first instance
          if (data.instances.length > 0) {
            localStorage.setItem('selectedInstance', data.instances[0].name);
            return data.instances[0].name;
          }

          return prev;
        });
      } else {
        // Fallback to v5.0 symbols API
        response = await fetch('/api/symbols');
        data = await response.json();

        if (data.symbols) {
          // Convert symbols to instance format
          const convertedInstances = data.symbols.map((s) => ({
            name: `${s.name}_${s.mode || 'LONG'}`,
            symbol: s.name,
            mode: s.mode || 'LONG',
            enabled: s.enabled,
            product_id: s.product_id,
            grid: s.grid,
            limits: s.limits,
            safety: s.safety,
          }));

          setInstances(convertedInstances);
          setIsV6(false);

          // Auto-select first enabled
          setSelectedInstance((prev) => {
            if (prev) return prev;
            const enabled = convertedInstances.find((i) => i.enabled);
            if (enabled) {
              localStorage.setItem('selectedInstance', enabled.name);
              return enabled.name;
            }
            return prev;
          });
        }
      }
    } catch (err) {
      console.error('Failed to load instances:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadInstances();
    const interval = setInterval(loadInstances, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, [loadInstances]);

  // Change selected instance (with dirty state check)
  const changeInstance = useCallback(
    (instanceName, options = {}) => {
      const { force = false } = options;

      // Check for unsaved changes
      if (dirtyState && !force) {
        const confirmed = window.confirm(
          `You have unsaved changes. Switch to ${instanceName} anyway?\n\n` +
            'Unsaved changes will be lost.'
        );
        if (!confirmed) return false;
      }

      // Update selected instance
      setSelectedInstance(instanceName);
      localStorage.setItem('selectedInstance', instanceName);

      // Clear dirty state after switch
      setDirtyState(false);

      console.log(`✅ Switched to instance: ${instanceName}`);
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

  // Cache instance data
  const cacheInstanceData = useCallback((instanceName, data) => {
    setInstanceDataCache((prev) => ({
      ...prev,
      [instanceName]: data,
    }));
    cacheTimestamps.current[instanceName] = Date.now();
  }, []);

  // Get cached instance data (if fresh)
  const getCachedData = useCallback(
    (instanceName) => {
      const timestamp = cacheTimestamps.current[instanceName];
      const now = Date.now();

      if (timestamp && now - timestamp < CACHE_TTL) {
        return instanceDataCache[instanceName];
      }
      return null;
    },
    [instanceDataCache]
  );

  // Invalidate cache for instance
  const invalidateCache = useCallback((instanceName) => {
    setInstanceDataCache((prev) => {
      const newCache = { ...prev };
      delete newCache[instanceName];
      return newCache;
    });
    delete cacheTimestamps.current[instanceName];
  }, []);

  // Get current instance details
  const getCurrentInstance = useCallback(() => {
    return instances.find((i) => i.name === selectedInstance) || null;
  }, [instances, selectedInstance]);

  // Get instances for a specific symbol
  const getInstancesForSymbol = useCallback(
    (symbol) => {
      return instances.filter((i) => i.symbol === symbol);
    },
    [instances]
  );

  // Helper: Add instance parameter to API URL
  const withInstance = useCallback(
    (url) => {
      if (!selectedInstance) return url;

      const separator = url.includes('?') ? '&' : '?';
      // Also add symbol for backward compatibility
      const { symbol } = parseInstanceName(selectedInstance);
      return `${url}${separator}instance=${selectedInstance}&symbol=${symbol}`;
    },
    [selectedInstance]
  );

  // Helper: Fetch with automatic instance parameter
  const fetchWithInstance = useCallback(
    async (url, options = {}) => {
      const urlWithInstance = withInstance(url);
      return fetch(urlWithInstance, options);
    },
    [withInstance]
  );

  // Backward compatibility: expose symbol-related helpers
  const selectedSymbol = selectedInstance ? parseInstanceName(selectedInstance).symbol : null;
  const selectedMode = selectedInstance ? parseInstanceName(selectedInstance).mode : null;

  const value = {
    // V6.0 State
    selectedInstance,
    instances,
    loading,
    instanceDataCache,
    dirtyState,
    isV6,

    // Parsed components (for convenience)
    selectedSymbol,
    selectedMode,

    // Actions
    changeInstance,
    loadInstances,
    getCurrentInstance,
    getInstancesForSymbol,
    markDirty,
    clearDirty,

    // Cache management
    cacheInstanceData,
    getCachedData,
    invalidateCache,

    // Helpers
    withInstance,
    fetchWithInstance,

    // Backward compatibility aliases
    changeSymbol: (symbol) => {
      // Find first enabled instance for this symbol
      const inst = instances.find((i) => i.symbol === symbol && i.enabled);
      if (inst) {
        return changeInstance(inst.name);
      }
      return false;
    },
    withSymbol: withInstance,
    fetchWithSymbol: fetchWithInstance,
  };

  return <InstanceContext.Provider value={value}>{children}</InstanceContext.Provider>;
};

export default InstanceProvider;
