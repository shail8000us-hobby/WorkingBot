import React, { useState, useEffect } from 'react';
import { ChevronDown, Activity, AlertCircle, Clock, CheckCircle2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import clsx from 'clsx';
import { SymbolContext } from '../context/SymbolContext'; // Reference for context integration

/**
 * Multi-Symbol Selector Component (v5.0)
 * 
 * Features:
 * - Dropdown symbol selector
 * - Real-time status indicators (active/stale/disabled)
 * - Persists selection in localStorage
 * - Auto-refresh symbol list
 */
const SymbolSelector = ({ onSymbolChange, className }) => {
  const [symbols, setSymbols] = useState([]);
  const [selectedSymbol, setSelectedSymbol] = useState(null);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load symbols from API
  useEffect(() => {
    loadSymbols();
    const interval = setInterval(loadSymbols, 10000); // Refresh every 10s
    return () => clearInterval(interval);
  }, []);

  // Restore selected symbol from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('selectedSymbol');
    if (saved && symbols.length > 0) {
      const symbol = symbols.find(s => s.name === saved);
      if (symbol) {
        setSelectedSymbol(symbol);
        if (onSymbolChange) onSymbolChange(symbol.name);
      }
    } else if (symbols.length > 0 && !selectedSymbol) {
      // Auto-select first enabled symbol
      const firstEnabled = symbols.find(s => s.enabled) || symbols[0];
      setSelectedSymbol(firstEnabled);
      if (onSymbolChange) onSymbolChange(firstEnabled.name);
    }
  }, [symbols, onSymbolChange]);

  const loadSymbols = async () => {
    try {
      const response = await fetch('/api/symbols');
      const data = await response.json();
      
      if (data.symbols) {
        setSymbols(data.symbols);
        setError(null);
      } else {
        setError('No symbols configured');
      }
    } catch (err) {
      console.error('Failed to load symbols:', err);
      setError('Failed to load symbols');
    } finally {
      setLoading(false);
    }
  };

  const handleSymbolSelect = (symbol) => {
    setSelectedSymbol(symbol);
    localStorage.setItem('selectedSymbol', symbol.name);
    setIsOpen(false);
    if (onSymbolChange) onSymbolChange(symbol.name);
  };

  const getStatusIcon = (symbol) => {
    if (!symbol.enabled) return <AlertCircle className="h-4 w-4 text-slate-500" />;
    
    // Check monitoring file status from symbols API
    const status = symbol.status || 'unknown';
    
    switch (status) {
      case 'active':
        return <Activity className="h-4 w-4 text-emerald-400 animate-pulse" />;
      case 'stale':
        return <Clock className="h-4 w-4 text-amber-400" />;
      case 'disabled':
        return <AlertCircle className="h-4 w-4 text-slate-500" />;
      default:
        return <CheckCircle2 className="h-4 w-4 text-slate-400" />;
    }
  };

  const getStatusColor = (symbol) => {
    if (!symbol.enabled) return 'bg-slate-700/50 border-slate-600';
    
    const status = symbol.status || 'unknown';
    switch (status) {
      case 'active':
        return 'bg-emerald-500/10 border-emerald-500/30';
      case 'stale':
        return 'bg-amber-500/10 border-amber-500/30';
      case 'disabled':
        return 'bg-slate-700/50 border-slate-600';
      default:
        return 'bg-slate-700/50 border-slate-600';
    }
  };

  const getStatusText = (symbol) => {
    if (!symbol.enabled) return 'Disabled';
    
    const status = symbol.status || 'unknown';
    switch (status) {
      case 'active':
        return 'Active';
      case 'stale':
        return 'Stale';
      case 'disabled':
        return 'Disabled';
      case 'not_running':
        return 'Not Running';
      default:
        return 'Unknown';
    }
  };

  if (loading) {
    return (
      <div className={clsx('flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-700 bg-slate-800/40', className)}>
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-500 border-t-transparent" />
        <span className="text-xs text-slate-400">Loading symbols...</span>
      </div>
    );
  }

  if (error || symbols.length === 0) {
    return (
      <div className={clsx('flex items-center gap-2 px-3 py-2 rounded-lg border border-rose-700/50 bg-rose-500/10', className)}>
        <AlertCircle className="h-4 w-4 text-rose-400" />
        <span className="text-xs text-rose-400">{error || 'No symbols'}</span>
      </div>
    );
  }

  return (
    <div className={clsx('relative', className)}>
      {/* Selected Symbol Display */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={clsx(
          'flex items-center justify-between gap-3 rounded-lg border px-3 py-2 transition-all',
          'hover:border-slate-600 hover:bg-slate-800/60',
          isOpen ? 'border-slate-600 bg-slate-800/60' : getStatusColor(selectedSymbol),
          'min-w-[180px]'
        )}
      >
        <div className="flex items-center gap-2">
          {selectedSymbol && getStatusIcon(selectedSymbol)}
          <div className="text-left">
            <p className="text-xs font-semibold text-slate-100">
              {selectedSymbol?.name || 'Select Symbol'}
            </p>
            <p className="text-[10px] text-slate-400">
              {selectedSymbol && getStatusText(selectedSymbol)}
            </p>
          </div>
        </div>
        <ChevronDown
          className={clsx(
            'h-4 w-4 text-slate-400 transition-transform',
            isOpen && 'rotate-180'
          )}
        />
      </button>

      {/* Dropdown Menu */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.15 }}
            className="absolute top-full left-0 right-0 z-50 mt-2 rounded-lg border border-slate-700 bg-slate-800 shadow-xl overflow-hidden"
          >
            {symbols.map((symbol) => (
              <button
                key={symbol.name}
                onClick={() => handleSymbolSelect(symbol)}
                className={clsx(
                  'flex w-full items-center justify-between gap-3 px-3 py-2.5 transition-colors',
                  'hover:bg-slate-700/50',
                  selectedSymbol?.name === symbol.name && 'bg-slate-700/30',
                  !symbol.enabled && 'opacity-60'
                )}
              >
                <div className="flex items-center gap-2">
                  {getStatusIcon(symbol)}
                  <div className="text-left">
                    <p className="text-xs font-semibold text-slate-100">
                      {symbol.name}
                    </p>
                    <p className="text-[10px] text-slate-400">
                      Product ID: {symbol.product_id} • {symbol.mode}
                    </p>
                  </div>
                </div>
                <div className="flex flex-col items-end gap-0.5">
                  <span className={clsx(
                    'text-[9px] font-medium uppercase tracking-wider px-1.5 py-0.5 rounded',
                    symbol.enabled ? 'bg-emerald-500/20 text-emerald-300' : 'bg-slate-700 text-slate-400'
                  )}>
                    {getStatusText(symbol)}
                  </span>
                  <span className="text-[9px] text-slate-500">
                    Grid: {symbol.grid?.lower}-{symbol.grid?.upper}
                  </span>
                </div>
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Close dropdown on outside click */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setIsOpen(false)}
        />
      )}
    </div>
  );
};

export default SymbolSelector;
