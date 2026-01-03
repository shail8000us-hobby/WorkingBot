/**
 * InstanceContext - Multi-Instance Support for GridBot v6.0
 * 
 * Provides context for selecting and managing trading instances.
 * Each instance = Symbol + Mode (e.g., BTCUSD_LONG, ETHUSD_SHORT)
 */

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5555';

// Instance from backend
export interface Instance {
  name: string;           // "BTCUSD_LONG"
  symbol: string;         // "BTCUSD"
  mode: 'LONG' | 'SHORT';
  enabled: boolean;
  product_id?: number;
  grid?: {
    lower: number;
    upper: number;
    step: number;
    reference?: number;
  };
  safety?: {
    max_account_loss_inr: number;
  };
  rsi?: {
    stop_threshold: number;
    resume_threshold: number;
  };
}

// Context value interface
export interface InstanceContextValue {
  // Instance data
  instances: Instance[];
  selectedInstance: Instance | null;
  selectedInstanceId: string | null;
  
  // Actions
  selectInstance: (instanceId: string) => void;
  refreshInstances: () => Promise<void>;
  
  // Utilities
  withInstance: (url: string) => string;  // Adds ?instance= param
  parseInstanceId: (id: string) => { symbol: string; mode: string };
  makeInstanceId: (symbol: string, mode: string) => string;
  
  // State
  loading: boolean;
  error: string | null;
}

const InstanceContext = createContext<InstanceContextValue | null>(null);

interface InstanceProviderProps {
  children: ReactNode;
}

export const InstanceProvider: React.FC<InstanceProviderProps> = ({ children }) => {
  const [instances, setInstances] = useState<Instance[]>([]);
  const [selectedInstanceId, setSelectedInstanceId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch all instances from backend
  const refreshInstances = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Use /api/symbols endpoint which has the actual trading instances
      const response = await fetch(`${API_BASE}/api/symbols`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      
      const data = await response.json();
      
      // Backend returns { symbols: [...] }
      if (data.symbols && Array.isArray(data.symbols)) {
        const mapped: Instance[] = data.symbols.map((sym: any) => {
          const mode = (sym.mode || 'LONG').toUpperCase();
          const instanceName = sym.name; // Just use symbol name (BTCUSD, ETHUSD)
          
          return {
            name: instanceName,
            symbol: sym.name,
            mode: mode as 'LONG' | 'SHORT',
            enabled: sym.enabled === true,
            product_id: sym.product_id,
            grid: sym.grid ? {
              lower: parseFloat(sym.grid.lower),
              upper: parseFloat(sym.grid.upper),
              step: parseFloat(sym.grid.step),
              reference: sym.grid.reference ? parseFloat(sym.grid.reference) : undefined,
            } : undefined,
            safety: sym.safety,
            rsi: sym.rsi,
          };
        });
        
        setInstances(mapped);
        
        // Auto-select first enabled instance if none selected
        if (!selectedInstanceId && mapped.length > 0) {
          const firstEnabled = mapped.find(i => i.enabled) || mapped[0];
          setSelectedInstanceId(firstEnabled.name);
        }
      } else {
        // Demo/fallback instances
        const fallback: Instance[] = [
          { name: 'BTCUSD', symbol: 'BTCUSD', mode: 'LONG', enabled: true },
          { name: 'ETHUSD', symbol: 'ETHUSD', mode: 'LONG', enabled: false },
        ];
        setInstances(fallback);
        if (!selectedInstanceId) {
          setSelectedInstanceId('BTCUSD');
        }
      }
    } catch (err) {
      console.error('Failed to fetch instances:', err);
      setError(err instanceof Error ? err.message : 'Failed to load instances');
      
      // Fallback instances for demo
      const fallback: Instance[] = [
        { name: 'BTCUSD', symbol: 'BTCUSD', mode: 'LONG', enabled: true },
      ];
      setInstances(fallback);
      if (!selectedInstanceId) {
        setSelectedInstanceId('BTCUSD');
      }
    } finally {
      setLoading(false);
    }
  }, [selectedInstanceId]);

  // Load instances on mount
  useEffect(() => {
    refreshInstances();
  }, []);

  // Select an instance
  const selectInstance = useCallback((instanceId: string) => {
    const instance = instances.find(i => i.name === instanceId);
    if (instance) {
      setSelectedInstanceId(instanceId);
      // Store in localStorage for persistence
      localStorage.setItem('selectedInstance', instanceId);
    }
  }, [instances]);

  // Restore from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem('selectedInstance');
    if (saved && instances.find(i => i.name === saved)) {
      setSelectedInstanceId(saved);
    }
  }, [instances]);

  // Add instance query param to URL
  const withInstance = useCallback((url: string): string => {
    if (!selectedInstanceId) return url;
    const separator = url.includes('?') ? '&' : '?';
    return `${url}${separator}instance=${encodeURIComponent(selectedInstanceId)}`;
  }, [selectedInstanceId]);

  // Parse instance ID into parts
  const parseInstanceId = useCallback((id: string) => {
    const parts = id.split('_');
    if (parts.length >= 2) {
      const mode = parts[parts.length - 1];
      const symbol = parts.slice(0, -1).join('_');
      return { symbol, mode };
    }
    return { symbol: id, mode: 'LONG' };
  }, []);

  // Create instance ID from parts
  const makeInstanceId = useCallback((symbol: string, mode: string): string => {
    return `${symbol}_${mode}`;
  }, []);

  // Get selected instance object
  const selectedInstance = instances.find(i => i.name === selectedInstanceId) || null;

  const value: InstanceContextValue = {
    instances,
    selectedInstance,
    selectedInstanceId,
    selectInstance,
    refreshInstances,
    withInstance,
    parseInstanceId,
    makeInstanceId,
    loading,
    error,
  };

  return (
    <InstanceContext.Provider value={value}>
      {children}
    </InstanceContext.Provider>
  );
};

// Hook to use instance context
export const useInstance = (): InstanceContextValue => {
  const context = useContext(InstanceContext);
  if (!context) {
    throw new Error('useInstance must be used within an InstanceProvider');
  }
  return context;
};

export default InstanceContext;
