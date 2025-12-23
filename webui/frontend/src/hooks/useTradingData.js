/**
 * Trading Data Hook
 * 
 * Manages trading-related state:
 * - Trading snapshot
 * - Positions data
 * - Bot status
 */

import { useState, useMemo } from 'react';

export function useTradingData() {
  const [tradingSnapshot, setTradingSnapshot] = useState(null);
  const [positionsData, setPositionsData] = useState(null);
  const [botStatus, setBotStatus] = useState({ running: false, pid: null });

  // Derived values
  const botIsRunning = useMemo(() => Boolean(
    botStatus?.running ||
    botStatus?.guardian_running ||
    botStatus?.bot_running ||
    tradingSnapshot?.status?.bot_running
  ), [botStatus, tradingSnapshot]);

  const openPositions = useMemo(() => 
    tradingSnapshot?.metrics?.open_positions ?? 
    positionsData?.summary?.total_positions ?? 
    null
  , [tradingSnapshot, positionsData]);

  const pendingOrders = useMemo(() => 
    tradingSnapshot?.metrics?.pending_orders ?? null
  , [tradingSnapshot]);

  const totalPnl = useMemo(() => 
    Number(positionsData?.summary?.total_pnl_inr ?? 
           tradingSnapshot?.metrics?.total_pnl ?? 0)
  , [positionsData, tradingSnapshot]);

  return {
    tradingSnapshot,
    setTradingSnapshot,
    positionsData,
    setPositionsData,
    botStatus,
    setBotStatus,
    botIsRunning,
    openPositions,
    pendingOrders,
    totalPnl
  };
}
