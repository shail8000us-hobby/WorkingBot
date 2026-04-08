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
  const [botStatus, setBotStatus] = useState({ running: false, pid: null });

  // Derived values
  const botIsRunning = useMemo(
    () =>
      Boolean(
        botStatus?.running ||
        botStatus?.guardian_running ||
        botStatus?.bot_running ||
        tradingSnapshot?.status?.bot_running
      ),
    [botStatus, tradingSnapshot]
  );

  const pendingOrders = useMemo(
    () => tradingSnapshot?.metrics?.pending_orders ?? null,
    [tradingSnapshot]
  );

  const totalPnl = useMemo(
    () => Number(tradingSnapshot?.metrics?.total_pnl_usd ?? tradingSnapshot?.metrics?.total_pnl ?? 0),
    [tradingSnapshot]
  );

  return {
    tradingSnapshot,
    setTradingSnapshot,
    botStatus,
    setBotStatus,
    botIsRunning,
    pendingOrders,
    totalPnl,
  };
}
