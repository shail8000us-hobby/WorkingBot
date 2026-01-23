import React, { useState, useEffect } from 'react';
import { Wallet } from 'lucide-react';
import { motion } from 'framer-motion';
import clsx from 'clsx';

/**
 * WalletBalanceIndicator - Real-time wallet balance display
 * Similar to Delta Exchange Trading Bot WebUI
 * 
 * Fetches net equity from backend API and displays with formatting
 */
function WalletBalanceIndicator() {
  const [balance, setBalance] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch wallet balance from backend
  useEffect(() => {
    const fetchBalance = async () => {
      try {
        setLoading(true);
        const response = await fetch('/api/liquidation/status');
        const data = await response.json();
        
        if (data.success && data.margin) {
          setBalance(data.margin.total_balance);
          setError(null);
        } else {
          setError('No data');
        }
      } catch (err) {
        console.error('Failed to fetch wallet balance:', err);
        setError('Error');
      } finally {
        setLoading(false);
      }
    };

    // Initial fetch
    fetchBalance();

    // Refresh every 5 seconds
    const interval = setInterval(fetchBalance, 5000);

    return () => clearInterval(interval);
  }, []);

  // Format balance with K/M suffix
  const formatBalance = (value) => {
    if (!value || isNaN(value)) return '0';
    
    const num = parseFloat(value);
    
    if (num >= 1000000) {
      return `${(num / 1000000).toFixed(2)}M`;
    } else if (num >= 1000) {
      return `${(num / 1000).toFixed(2)}K`;
    } else {
      return num.toFixed(2);
    }
  };

  return (
    <motion.div
      className="flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2"
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
    >
      <Wallet className="h-4 w-4 text-emerald-400" strokeWidth={2} />
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-emerald-400 uppercase tracking-wide">
          Balance
        </span>
        {loading && !balance ? (
          <span className="text-xs text-slate-400">...</span>
        ) : error ? (
          <span className="text-xs text-rose-400">{error}</span>
        ) : (
          <span className="text-sm font-bold text-emerald-300">
            ₹{formatBalance(balance)}
          </span>
        )}
      </div>
    </motion.div>
  );
}

export default WalletBalanceIndicator;
