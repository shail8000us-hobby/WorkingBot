import React, { useState, useEffect } from 'react';
import { ChevronDown, Activity, AlertCircle, Clock, CheckCircle2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import clsx from 'clsx';
import { SymbolContext } from '../context/SymbolContext'; // Reference for context integration

/**
 * Multi-Instance Selector Component (v6.0)
 *
 * Features:
 * - Dropdown instance selector (SYMBOL_MODE format: BTCUSD_LONG, ETHUSD_LONG)
 * - Real-time status indicators (active/stale/disabled)
 * - Persists selection in localStorage
 * - Auto-refresh instance list
 * - Backward compatible with v5.0 symbol-only configs
 */
const SymbolSelector = ({ onSymbolChange, className }) => {
  const [instances, setInstances] = useState([]);
  const [selectedInstance, setSelectedInstance] = useState(null);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isV6, setIsV6] = useState(false);

  // Load instances from API
  useEffect(() => {
    loadInstances();
    const interval = setInterval(loadInstances, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  // Restore selected instance from localStorage (only once on mount)
  useEffect(() => {
    if (instances.length === 0) return; // Wait for instances to load
    if (selectedInstance) return; // Already have selection

    const saved = localStorage.getItem('selectedInstance');
    if (saved) {
      const instance = instances.find((i) => i.name === saved);
      if (instance) {
        setSelectedInstance(instance);
        if (onSymbolChange) onSymbolChange(instance.name);
        return;
      }
    }

    // Auto-select first enabled instance
    const firstEnabled = instances.find((i) => i.enabled) || instances[0];
    if (firstEnabled) {
      setSelectedInstance(firstEnabled);
      if (onSymbolChange) onSymbolChange(firstEnabled.name);
    }
  }, [instances.length]);

  const loadInstances = async () => {
    try {
      const response = await fetch('/api/instances');
      const data = await response.json();

      if (data.instances) {
        // V6.0: Use instances array
        setInstances(data.instances);
        setIsV6(true);
        setError(null);
      } else if (data.symbols) {
        // V5.0 fallback: Convert symbols to pseudo-instances
        const pseudoInstances = data.symbols.map((s) => ({
          name: s.name,
          symbol: s.name,
          mode: 'LONG',
          enabled: s.enabled,
          ...s,
        }));
        setInstances(pseudoInstances);
        setIsV6(false);
        setError(null);
      } else {
        setError('No instances configured');
      }
    } catch (err) {
      console.error('Failed to load instances:', err);
      setError('Failed to load instances');
    } finally {
      setLoading(false);
    }
  };

  const handleInstanceSelect = (instance) => {
    setSelectedInstance(instance);
    localStorage.setItem('selectedInstance', instance.name);
    setIsOpen(false);
    if (onSymbolChange) onSymbolChange(instance.name);
  };

  const getStatusIcon = (instance) => {
    if (!instance || !instance.enabled) return <AlertCircle className="h-4 w-4 text-slate-500" />;

    // Check monitoring file status from instances API
    const status = instance.status || 'unknown';

    switch (status) {
      case 'active':
        return <Activity className="h-4 w-4 text-emerald-400" />;
      case 'stale':
        return <Clock className="h-4 w-4 text-amber-400" />;
      case 'disabled':
        return <AlertCircle className="h-4 w-4 text-slate-500" />;
      default:
        return <CheckCircle2 className="h-4 w-4 text-slate-400" />;
    }
  };

  const getStatusColor = (instance) => {
    if (!instance || !instance.enabled) return 'bg-slate-700/50 border-slate-600';

    const status = instance.status || 'unknown';
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

  const getStatusText = (instance) => {
    if (!instance || !instance.enabled) return 'Disabled';

    const status = instance.status || 'unknown';
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
      <div
        className={clsx(
          'flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-700 bg-slate-800/40',
          className
        )}
      >
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-500 border-t-transparent" />
        <span className="text-xs text-slate-400">Loading instances...</span>
      </div>
    );
  }

  if (error || instances.length === 0) {
    return (
      <div
        className={clsx(
          'flex items-center gap-2 px-3 py-2 rounded-lg border border-rose-700/50 bg-rose-500/10',
          className
        )}
      >
        <AlertCircle className="h-4 w-4 text-rose-400" />
        <span className="text-xs text-rose-400">{error || 'No instances'}</span>
      </div>
    );
  }

  return (
    <div className={clsx('relative', className)}>
      {/* Selected Instance Display */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={clsx(
          'flex items-center justify-between gap-3 rounded-lg border px-3 py-2 transition-all',
          'hover:border-slate-600 hover:bg-slate-800/60',
          isOpen ? 'border-slate-600 bg-slate-800/60' : getStatusColor(selectedInstance),
          'min-w-[200px]'
        )}
      >
        <div className="flex items-center gap-2">
          {selectedInstance && getStatusIcon(selectedInstance)}
          <div className="text-left">
            <p className="text-xs font-semibold text-slate-100">
              {selectedInstance?.name || 'Select Instance'}
            </p>
            <p className="text-[10px] text-slate-400">
              {selectedInstance &&
                (isV6
                  ? `${selectedInstance.symbol} • ${selectedInstance.mode}`
                  : getStatusText(selectedInstance))}
            </p>
          </div>
        </div>
        <ChevronDown
          className={clsx('h-4 w-4 text-slate-400 transition-transform', isOpen && 'rotate-180')}
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
            className="absolute top-full left-0 right-0 z-[28] mt-2 rounded-lg border border-slate-700 bg-slate-800 shadow-xl overflow-hidden"
          >
            {instances.map((instance) => (
              <button
                key={instance.name}
                onClick={() => handleInstanceSelect(instance)}
                className={clsx(
                  'flex w-full items-center justify-between gap-3 px-3 py-2.5 transition-colors',
                  'hover:bg-slate-700/50',
                  selectedInstance?.name === instance.name && 'bg-slate-700/30',
                  instance && !instance.enabled && 'opacity-60'
                )}
              >
                <div className="flex items-center gap-2">
                  {getStatusIcon(instance)}
                  <div className="text-left">
                    <p className="text-xs font-semibold text-slate-100">{instance.name}</p>
                    <p className="text-[10px] text-slate-400">
                      {isV6
                        ? `${instance.symbol} • ${instance.mode}`
                        : `Product ID: ${instance.product_id}`}
                    </p>
                  </div>
                </div>
                <div className="flex flex-col items-end gap-0.5">
                  <span
                    className={clsx(
                      'text-[9px] font-medium uppercase tracking-wider px-1.5 py-0.5 rounded',
                      instance && instance.enabled
                        ? 'bg-emerald-500/20 text-emerald-300'
                        : 'bg-slate-700 text-slate-400'
                    )}
                  >
                    {getStatusText(instance)}
                  </span>
                  {instance.grid && (
                    <span className="text-[9px] text-slate-500">
                      Grid: {instance.grid?.lower}-{instance.grid?.upper}
                    </span>
                  )}
                </div>
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Close dropdown on outside click */}
      {isOpen && <div className="fixed inset-0 z-[18]" onClick={() => setIsOpen(false)} />}
    </div>
  );
};

export default SymbolSelector;
