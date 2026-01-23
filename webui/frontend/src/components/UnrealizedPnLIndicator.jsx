import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { motion } from 'framer-motion';
import clsx from 'clsx';

/**
 * UnrealizedPnLIndicator - Real-time unrealized PnL from Delta Exchange
 * Displays total unrealized PnL from all open positions
 * 
 * Fetches from /api/positions endpoint
 */
function UnrealizedPnLIndicator() {
  const [upnl, setUpnl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch unrealized PnL from positions endpoint
  useEffect(() => {
    const fetchUpnl = async () => {
      try {
        setLoading(true);
        // Fetch ALL positions (no symbol filter) to get total UPNL
        const response = await fetch('/api/positions?symbol=');
        const data = await response.json();
        
        if (data && data.summary && data.summary.total_pnl_inr !== undefined) {
          setUpnl(data.summary.total_pnl_inr);
          setError(null);
        } else {
          setError('No data');
        }
      } catch (err) {
        console.error('Failed to fetch UPNL:', err);
        setError('Error');
      } finally {
        setLoading(false);
      }
    };

    // Initial fetch
    fetchUpnl();

    // Refresh every 5 seconds
    const interval = setInterval(fetchUpnl, 5000);

    return () => clearInterval(interval);
  }, []);

  // Format UPNL with sign and color
  const formatUpnl = (value) => {
    if (!value || isNaN(value)) return '0.00';
    
    const num = parseFloat(value);
    const absNum = Math.abs(num);
    
    // Format with K/M suffix if needed
    let formatted;
    if (absNum >= 1000000) {
      formatted = `${(num / 1000000).toFixed(2)}M`;
    } else if (absNum >= 1000) {
      formatted = `${(num / 1000).toFixed(2)}K`;
    } else {
      formatted = num.toFixed(2);
    }
    
    // Add sign
    return num >= 0 ? `+${formatted}` : formatted;
  };

  const isPositive = upnl >= 0;
  const Icon = isPositive ? TrendingUp : TrendingDown;
  const colorClass = isPositive ? 'text-emerald-300' : 'text-rose-300';
  const borderColor = isPositive ? 'border-emerald-500/30' : 'border-rose-500/30';
  const bgColor = isPositive ? 'bg-emerald-500/10' : 'bg-rose-500/10';

  return (
    <motion.div
      className={clsx('flex items-center gap-2 rounded-lg border px-3 py-2', borderColor, bgColor)}
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
    >
      <Icon className={clsx('h-4 w-4', colorClass)} strokeWidth={2} />
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wide">
          UPNL
        </span>
        {loading && upnl === null ? (
          <span className="text-xs text-slate-400">...</span>
        ) : error ? (
          <span className="text-xs text-rose-400">{error}</span>
        ) : (
          <span className={clsx('text-sm font-bold', colorClass)}>
            ₹{formatUpnl(upnl)}
          </span>
        )}
      </div>
    </motion.div>
  );
}

export default UnrealizedPnLIndicator;
