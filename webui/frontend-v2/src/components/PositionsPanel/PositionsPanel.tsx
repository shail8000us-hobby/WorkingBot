/**
 * Positions Panel
 * 
 * Displays all positions across all instruments with detailed information.
 * Includes orders, PnL summary, and position management controls.
 * 
 * Uses real API data from backend with instance context support.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useGlobalStore } from '../../stores/globalStore';
import { getInstrumentStore } from '../../stores/instrumentStore';
import { useInstance } from '../../contexts/InstanceContext';
import type { Position, Order, InstanceId } from '../../types';
import styles from './PositionsPanel.module.css';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5555';

interface PositionFromAPI {
  symbol: string;
  size: number;
  entry_price: number;
  mark_price?: number;
  current_price?: number;
  unrealized_pnl: number;
  side?: string;
  delta?: number;
}

interface OrderFromAPI {
  id: string | number;
  symbol?: string;
  product_id?: number;
  side: string;
  order_type?: string;
  price: number;
  size: number;
  filled_size?: number;
  state?: string;
}

interface AggregatedPosition {
  instanceId: InstanceId;
  symbol: string;
  mode: string;
  positions: Position[];
  orders: Order[];
  totalSize: number;
  totalPnl: number;
  avgEntry: number;
}

export const PositionsPanel: React.FC = () => {
  const instances = useGlobalStore((s) => s.instances);
  const instanceData = useGlobalStore((s) => s.instanceData);
  const { selectedInstanceId, withInstance } = useInstance();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [positions, setPositions] = useState<PositionFromAPI[]>([]);
  const [orders, setOrders] = useState<OrderFromAPI[]>([]);

  // Fetch real data from API (respects selected instance)
  const fetchData = useCallback(async () => {
    try {
      const [posRes, ordRes] = await Promise.allSettled([
        fetch(withInstance(`${API_BASE}/api/positions`)).then(r => r.json()),
        fetch(withInstance(`${API_BASE}/api/orders`)).then(r => r.json()),
      ]);

      if (posRes.status === 'fulfilled') {
        const data = posRes.value;
        if (data.positions) {
          setPositions(data.positions);
        } else if (Array.isArray(data)) {
          setPositions(data);
        }
      }

      if (ordRes.status === 'fulfilled') {
        const data = ordRes.value;
        if (data.orders) {
          setOrders(data.orders);
        } else if (Array.isArray(data)) {
          setOrders(data);
        }
      }

      setError(null);
    } catch (err) {
      setError('Failed to fetch positions');
      console.error('Error fetching positions:', err);
    } finally {
      setLoading(false);
    }
  }, [withInstance]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData, selectedInstanceId]);

  // Also try to get data from instrument stores (populated by dataAggregator)
  const aggregatedData: AggregatedPosition[] = instances.map((instanceId) => {
    try {
      const store = getInstrumentStore(instanceId);
      const state = store.getState();
      const storePositions = state.positions;
      const storeOrders = state.orders;

      const totalSize = storePositions.reduce((sum, p) => sum + p.size, 0);
      const totalPnl = storePositions.reduce((sum, p) => sum + p.unrealizedPnl, 0);
      const avgEntry = totalSize > 0 
        ? storePositions.reduce((sum, p) => sum + p.entryPrice * p.size, 0) / totalSize 
        : 0;

      return {
        instanceId,
        symbol: state.identity.symbol,
        mode: state.identity.mode,
        positions: storePositions,
        orders: storeOrders,
        totalSize,
        totalPnl,
        avgEntry
      };
    } catch {
      // Instance store doesn't exist, use API data
      const symbol = instanceId.replace(/_LONG|_SHORT/g, '');
      const mode = instanceId.includes('LONG') ? 'LONG' : 'SHORT';
      
      const instancePositions = positions.filter(p => 
        p.symbol?.includes(symbol)
      );
      const instanceOrders = orders.filter(o => 
        o.symbol?.includes(symbol) || String(o.product_id)?.includes(symbol)
      );

      return {
        instanceId,
        symbol,
        mode,
        positions: instancePositions.map((p, i) => ({
          id: `${p.symbol}_${i}`,
          symbol: p.symbol,
          side: (p.side?.toUpperCase() || 'LONG') as 'LONG' | 'SHORT',
          size: p.size || 0,
          entryPrice: p.entry_price || 0,
          currentPrice: p.mark_price || p.current_price || 0,
          unrealizedPnl: p.unrealized_pnl || 0,
          unrealizedPnlPercent: p.entry_price ? ((p.mark_price || p.current_price || 0) - p.entry_price) / p.entry_price * 100 : 0,
          openedAt: Date.now(),
        })),
        orders: instanceOrders.map(o => ({
          id: String(o.id),
          symbol: o.symbol || symbol,
          side: (o.side?.toUpperCase() === 'BUY' ? 'BUY' : 'SELL') as 'BUY' | 'SELL',
          type: (o.order_type?.includes('limit') ? 'LIMIT' : 'MARKET') as 'LIMIT' | 'MARKET' | 'STOP',
          price: o.price || 0,
          size: o.size || 0,
          filledSize: o.filled_size || 0,
          status: (o.state || 'pending') as 'pending' | 'open' | 'filled' | 'cancelled' | 'rejected',
          createdAt: Date.now(),
          updatedAt: Date.now(),
        })),
        totalSize: instancePositions.reduce((sum, p) => sum + (p.size || 0), 0),
        totalPnl: instancePositions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0),
        avgEntry: 0,
      };
    }
  });

  // If no instances configured, show positions directly from API
  const hasData = aggregatedData.some(d => d.positions.length > 0 || d.orders.length > 0);
  const showRawData = !hasData && (positions.length > 0 || orders.length > 0);

  // Calculate totals
  const totalUnrealizedPnl = aggregatedData.reduce((sum, d) => sum + d.totalPnl, 0) || 
    positions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0);
  const totalPositionCount = aggregatedData.reduce((sum, d) => sum + d.positions.length, 0) || positions.length;
  const totalOrderCount = aggregatedData.reduce((sum, d) => sum + d.orders.length, 0) || orders.length;

  const formatPnl = (value: number) => {
    const formatted = Math.abs(value).toFixed(2);
    return value >= 0 ? `+$${formatted}` : `-$${formatted}`;
  };

  if (loading && positions.length === 0) {
    return (
      <div className={styles.panel}>
        <header className={styles.header}>
          <h2 className={styles.title}>📈 Positions & Orders</h2>
        </header>
        <div className={styles.loading}>Loading positions...</div>
      </div>
    );
  }

  return (
    <div className={styles.panel}>
      <header className={styles.header}>
        <h2 className={styles.title}>📈 Positions & Orders</h2>
        <button className={styles.refreshBtn} onClick={fetchData}>🔄</button>
        <div className={styles.summary}>
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>Positions</span>
            <span className={styles.summaryValue}>{totalPositionCount}</span>
          </div>
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>Open Orders</span>
            <span className={styles.summaryValue}>{totalOrderCount}</span>
          </div>
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>Unrealized PnL</span>
            <span 
              className={styles.summaryValue} 
              data-positive={totalUnrealizedPnl >= 0}
            >
              {formatPnl(totalUnrealizedPnl)}
            </span>
          </div>
        </div>
      </header>

      {error && <div className={styles.error}>{error}</div>}

      <div className={styles.content}>
        {/* Show raw API data if no instances configured */}
        {showRawData && (
          <div className={styles.instrumentSection}>
            <div className={styles.instrumentHeader}>
              <span className={styles.instrumentName}>All Positions</span>
              <span 
                className={styles.instrumentPnl}
                data-positive={totalUnrealizedPnl >= 0}
              >
                {formatPnl(totalUnrealizedPnl)}
              </span>
            </div>
            <table className={styles.positionsTable}>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Size</th>
                  <th>Entry</th>
                  <th>Current</th>
                  <th>PnL</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((pos, i) => (
                  <tr key={i}>
                    <td>{pos.symbol}</td>
                    <td>{pos.size?.toFixed(4)}</td>
                    <td>${pos.entry_price?.toLocaleString()}</td>
                    <td>${(pos.mark_price || pos.current_price)?.toLocaleString()}</td>
                    <td data-positive={(pos.unrealized_pnl || 0) >= 0}>
                      {formatPnl(pos.unrealized_pnl || 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Show by instance */}
        {aggregatedData.map((data) => (
          <div key={data.instanceId} className={styles.instrumentSection}>
            <div className={styles.instrumentHeader}>
              <span className={styles.instrumentName}>
                {data.symbol}
                <span className={styles.modeBadge} data-mode={data.mode}>
                  {data.mode}
                </span>
              </span>
              <span 
                className={styles.instrumentPnl}
                data-positive={data.totalPnl >= 0}
              >
                {formatPnl(data.totalPnl)}
              </span>
            </div>

            {data.positions.length === 0 ? (
              <div className={styles.emptyState}>No open positions</div>
            ) : (
              <table className={styles.positionsTable}>
                <thead>
                  <tr>
                    <th>Side</th>
                    <th>Size</th>
                    <th>Entry</th>
                    <th>Current</th>
                    <th>PnL</th>
                  </tr>
                </thead>
                <tbody>
                  {data.positions.map((position) => (
                    <tr key={position.id}>
                      <td data-side={position.side.toLowerCase()}>
                        {position.side}
                      </td>
                      <td>{position.size.toFixed(4)}</td>
                      <td>${position.entryPrice.toLocaleString()}</td>
                      <td>${position.currentPrice.toLocaleString()}</td>
                      <td data-positive={position.unrealizedPnl >= 0}>
                        {formatPnl(position.unrealizedPnl)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {data.orders.length > 0 && (
              <>
                <div className={styles.ordersHeader}>
                  Open Orders ({data.orders.length})
                </div>
                <table className={styles.ordersTable}>
                  <thead>
                    <tr>
                      <th>Side</th>
                      <th>Type</th>
                      <th>Price</th>
                      <th>Size</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.orders.slice(0, 10).map((order) => (
                      <tr key={order.id}>
                        <td data-side={order.side.toLowerCase()}>{order.side}</td>
                        <td>{order.type}</td>
                        <td>${order.price.toLocaleString()}</td>
                        <td>{order.size.toFixed(4)}</td>
                        <td>{order.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {data.orders.length > 10 && (
                  <div className={styles.moreIndicator}>
                    +{data.orders.length - 10} more orders
                  </div>
                )}
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default PositionsPanel;
