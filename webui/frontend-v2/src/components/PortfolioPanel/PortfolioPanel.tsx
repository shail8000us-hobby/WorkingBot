/**
 * PortfolioPanel - Multi-Symbol Portfolio Overview
 * 
 * View all symbols and their performance at a glance.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useInstance } from '../../contexts/InstanceContext';
import styles from './PortfolioPanel.module.css';

interface SymbolData {
  symbol: string;
  mode: 'LONG' | 'SHORT';
  status: 'active' | 'paused' | 'stopped';
  price: number;
  change24h: number;
  positions: number;
  unrealizedPnl: number;
  realizedPnl: number;
  totalValue: number;
  rsi?: number;
  gridLevels?: number;
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5555';

const DEMO_DATA: SymbolData[] = [
  { symbol: 'BTCUSD', mode: 'LONG', status: 'active', price: 42500, change24h: 2.5, positions: 3, unrealizedPnl: 245.50, realizedPnl: 1250.00, totalValue: 15000, rsi: 52, gridLevels: 10 },
  { symbol: 'ETHUSD', mode: 'LONG', status: 'active', price: 2250, change24h: -1.2, positions: 2, unrealizedPnl: -45.20, realizedPnl: 680.00, totalValue: 8500, rsi: 48, gridLevels: 8 },
  { symbol: 'SOLUSD', mode: 'SHORT', status: 'paused', price: 98.50, change24h: 5.8, positions: 0, unrealizedPnl: 0, realizedPnl: 125.00, totalValue: 2000, rsi: 72, gridLevels: 6 }
];

export const PortfolioPanel: React.FC = () => {
  const { instances: contextInstances, withInstance, selectedInstanceId } = useInstance();
  const [symbols, setSymbols] = useState<SymbolData[]>([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<'cards' | 'table'>('cards');
  const [sortBy, setSortBy] = useState<'symbol' | 'pnl' | 'value'>('symbol');

  const fetchData = useCallback(async () => {
    try {
      // Try instances API which provides real data
      const response = await fetch(`${API_BASE}/api/instances/list`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      
      if (data.success && data.data && data.data.length > 0) {
        // Map instances to portfolio symbols
        const symbolsFromInstances: SymbolData[] = data.data.map((inst: any) => ({
          symbol: inst.symbol || inst.instanceId.split('_')[0],
          mode: inst.mode || 'LONG',
          status: inst.enabled ? 'active' : 'stopped',
          price: 0, // Would need price API
          change24h: 0,
          positions: 0,
          unrealizedPnl: 0,
          realizedPnl: 0,
          totalValue: 0,
          rsi: 50,
          gridLevels: 10
        }));
        
        if (symbolsFromInstances.length > 0) {
          setSymbols(symbolsFromInstances);
          return;
        }
      }
      // Fall back to demo data
      setSymbols(DEMO_DATA);
    } catch (err) {
      setSymbols(DEMO_DATA);
    } finally {
      setLoading(false);
    }
  }, [withInstance]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [fetchData, selectedInstanceId]);

  const totalUnrealized = symbols.reduce((sum, s) => sum + s.unrealizedPnl, 0);
  const totalRealized = symbols.reduce((sum, s) => sum + s.realizedPnl, 0);
  const totalValue = symbols.reduce((sum, s) => sum + s.totalValue, 0);
  const activeCount = symbols.filter(s => s.status === 'active').length;

  const sortedSymbols = [...symbols].sort((a, b) => {
    switch (sortBy) {
      case 'pnl': return (b.unrealizedPnl + b.realizedPnl) - (a.unrealizedPnl + a.realizedPnl);
      case 'value': return b.totalValue - a.totalValue;
      default: return a.symbol.localeCompare(b.symbol);
    }
  });

  if (loading) {
    return <div className={styles.panel}><div className={styles.loading}>Loading portfolio...</div></div>;
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2>📊 Portfolio Overview</h2>
        <div className={styles.headerActions}>
          <select 
            className={styles.sortSelect}
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
          >
            <option value="symbol">Sort by Symbol</option>
            <option value="pnl">Sort by P&L</option>
            <option value="value">Sort by Value</option>
          </select>
          <div className={styles.viewToggle}>
            <button 
              className={`${styles.viewBtn} ${viewMode === 'cards' ? styles.active : ''}`}
              onClick={() => setViewMode('cards')}
            >
              Cards
            </button>
            <button 
              className={`${styles.viewBtn} ${viewMode === 'table' ? styles.active : ''}`}
              onClick={() => setViewMode('table')}
            >
              Table
            </button>
          </div>
          <button className={styles.refreshBtn} onClick={fetchData}>🔄</button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className={styles.summaryGrid}>
        <div className={styles.summaryCard}>
          <span className={styles.summaryLabel}>Total Value</span>
          <span className={styles.summaryValue}>${totalValue.toLocaleString()}</span>
        </div>
        <div className={styles.summaryCard}>
          <span className={styles.summaryLabel}>Unrealized P&L</span>
          <span className={`${styles.summaryValue} ${totalUnrealized >= 0 ? styles.positive : styles.negative}`}>
            ${totalUnrealized.toFixed(2)}
          </span>
        </div>
        <div className={styles.summaryCard}>
          <span className={styles.summaryLabel}>Realized P&L</span>
          <span className={`${styles.summaryValue} ${totalRealized >= 0 ? styles.positive : styles.negative}`}>
            ${totalRealized.toFixed(2)}
          </span>
        </div>
        <div className={styles.summaryCard}>
          <span className={styles.summaryLabel}>Active Symbols</span>
          <span className={styles.summaryValue}>{activeCount} / {symbols.length}</span>
        </div>
      </div>

      {/* Symbols */}
      {viewMode === 'cards' ? (
        <div className={styles.symbolsGrid}>
          {sortedSymbols.map(symbol => (
            <div key={`${symbol.symbol}-${symbol.mode}`} className={`${styles.symbolCard} ${styles[symbol.status]}`}>
              <div className={styles.cardHeader}>
                <div className={styles.symbolInfo}>
                  <span className={styles.symbolName}>{symbol.symbol}</span>
                  <span className={`${styles.modeBadge} ${symbol.mode === 'LONG' ? styles.long : styles.short}`}>
                    {symbol.mode}
                  </span>
                </div>
                <span className={`${styles.statusBadge} ${styles[symbol.status]}`}>
                  {symbol.status}
                </span>
              </div>

              <div className={styles.priceRow}>
                <span className={styles.price}>${symbol.price.toLocaleString()}</span>
                <span className={`${styles.change} ${symbol.change24h >= 0 ? styles.positive : styles.negative}`}>
                  {symbol.change24h >= 0 ? '+' : ''}{symbol.change24h.toFixed(2)}%
                </span>
              </div>

              <div className={styles.statsGrid}>
                <div className={styles.stat}>
                  <span className={styles.statLabel}>Positions</span>
                  <span className={styles.statValue}>{symbol.positions}</span>
                </div>
                <div className={styles.stat}>
                  <span className={styles.statLabel}>Grid Levels</span>
                  <span className={styles.statValue}>{symbol.gridLevels || '-'}</span>
                </div>
                <div className={styles.stat}>
                  <span className={styles.statLabel}>RSI</span>
                  <span className={styles.statValue}>{symbol.rsi || '-'}</span>
                </div>
                <div className={styles.stat}>
                  <span className={styles.statLabel}>Value</span>
                  <span className={styles.statValue}>${symbol.totalValue.toLocaleString()}</span>
                </div>
              </div>

              <div className={styles.pnlRow}>
                <div className={styles.pnlItem}>
                  <span className={styles.pnlLabel}>Unrealized</span>
                  <span className={`${styles.pnlValue} ${symbol.unrealizedPnl >= 0 ? styles.positive : styles.negative}`}>
                    ${symbol.unrealizedPnl.toFixed(2)}
                  </span>
                </div>
                <div className={styles.pnlItem}>
                  <span className={styles.pnlLabel}>Realized</span>
                  <span className={`${styles.pnlValue} ${symbol.realizedPnl >= 0 ? styles.positive : styles.negative}`}>
                    ${symbol.realizedPnl.toFixed(2)}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className={styles.tableContainer}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Mode</th>
                <th>Status</th>
                <th>Price</th>
                <th>24h Change</th>
                <th>Positions</th>
                <th>RSI</th>
                <th>Unrealized P&L</th>
                <th>Realized P&L</th>
                <th>Value</th>
              </tr>
            </thead>
            <tbody>
              {sortedSymbols.map(symbol => (
                <tr key={`${symbol.symbol}-${symbol.mode}`}>
                  <td className={styles.symbolCell}>{symbol.symbol}</td>
                  <td>
                    <span className={`${styles.modeBadge} ${symbol.mode === 'LONG' ? styles.long : styles.short}`}>
                      {symbol.mode}
                    </span>
                  </td>
                  <td>
                    <span className={`${styles.statusBadge} ${styles[symbol.status]}`}>
                      {symbol.status}
                    </span>
                  </td>
                  <td>${symbol.price.toLocaleString()}</td>
                  <td className={symbol.change24h >= 0 ? styles.positive : styles.negative}>
                    {symbol.change24h >= 0 ? '+' : ''}{symbol.change24h.toFixed(2)}%
                  </td>
                  <td>{symbol.positions}</td>
                  <td>{symbol.rsi || '-'}</td>
                  <td className={symbol.unrealizedPnl >= 0 ? styles.positive : styles.negative}>
                    ${symbol.unrealizedPnl.toFixed(2)}
                  </td>
                  <td className={symbol.realizedPnl >= 0 ? styles.positive : styles.negative}>
                    ${symbol.realizedPnl.toFixed(2)}
                  </td>
                  <td>${symbol.totalValue.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default PortfolioPanel;
