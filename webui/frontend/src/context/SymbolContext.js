import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

/**
 * SymbolContext - Global state for selected trading symbol (v5.0)
 * 
 * Manages:
 * - Current selected symbol
 * - Available symbols list
 * - Symbol status updates
 * - Automatic API parameter injection
 */
const SymbolContext = createContext();

export const useSymbol = () => {
  const context = useContext(SymbolContext);
  if (!context) {
    throw new Error('useSymbol must be used within SymbolProvider');
  }
  return context;
};

export const SymbolProvider = ({ children }) => {
  const [selectedSymbol, setSelectedSymbol] = useState(null);
  const [symbols, setSymbols] = useState([]);
  const [loading, setLoading] = useState(true);

  // Load symbols from API
  const loadSymbols = useCallback(async () => {
    try {
      const response = await fetch('/api/symbols');
      const data = await response.json();
      
      if (data.symbols) {
        setSymbols(data.symbols);
        
        // Auto-select first enabled symbol if none selected
        if (!selectedSymbol && data.symbols.length > 0) {
          const saved = localStorage.getItem('selectedSymbol');
          const symbol = saved 
            ? data.symbols.find(s => s.name === saved)
            : data.symbols.find(s => s.enabled) || data.symbols[0];
          
          if (symbol) {
            setSelectedSymbol(symbol.name);
            localStorage.setItem('selectedSymbol', symbol.name);
          }
        }
      }
    } catch (err) {
      console.error('Failed to load symbols:', err);
    } finally {
      setLoading(false);
    }
  }, [selectedSymbol]);

  useEffect(() => {
    loadSymbols();
    const interval = setInterval(loadSymbols, 10000); // Refresh every 10s
    return () => clearInterval(interval);
  }, [loadSymbols]);

  // Change selected symbol
  const changeSymbol = useCallback((symbolName) => {
    setSelectedSymbol(symbolName);
    localStorage.setItem('selectedSymbol', symbolName);
  }, []);

  // Get current symbol details
  const getCurrentSymbol = useCallback(() => {
    return symbols.find(s => s.name === selectedSymbol) || null;
  }, [symbols, selectedSymbol]);

  // Helper: Add symbol parameter to API URL
  const withSymbol = useCallback((url) => {
    if (!selectedSymbol) return url;
    
    const separator = url.includes('?') ? '&' : '?';
    return `${url}${separator}symbol=${selectedSymbol}`;
  }, [selectedSymbol]);

  // Helper: Fetch with automatic symbol parameter
  const fetchWithSymbol = useCallback(async (url, options = {}) => {
    const urlWithSymbol = withSymbol(url);
    return fetch(urlWithSymbol, options);
  }, [withSymbol]);

  const value = {
    // State
    selectedSymbol,
    symbols,
    loading,
    
    // Actions
    changeSymbol,
    loadSymbols,
    getCurrentSymbol,
    
    // Helpers
    withSymbol,
    fetchWithSymbol
  };

  return (
    <SymbolContext.Provider value={value}>
      {children}
    </SymbolContext.Provider>
  );
};
