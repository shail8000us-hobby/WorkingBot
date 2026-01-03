/**
 * GridLevelChart - Visual Grid Trading Visualization
 * 
 * Shows:
 * - Grid upper/lower bounds
 * - Current price marker
 * - Active entry orders at each level
 * - Grid levels with step size
 * - Position markers
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useInstance } from '../../contexts/InstanceContext';
import { fetchWithMock, mockPriceHealth } from '../../utils/mockData';
import styles from './GridLevelChart.module.css';

interface GridConfig {
  lower: number;
  upper: number;
  step: number;
  levels: number;
  reference_price?: number;
}

interface GridLevel {
  price: number;
  type: 'buy' | 'sell' | 'none';
  hasOrder: boolean;
  hasPosition: boolean;
  orderId?: string;
  positionSize?: number;
}

interface GridOrder {
  id: string;
  price: number;
  side: 'buy' | 'sell';
  size: number;
  state: string;
}

interface GridPosition {
  entry_price: number;
  size: number;
  side: string;
  unrealized_pnl: number;
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5555';

export const GridLevelChart: React.FC = () => {
  const { withInstance, selectedInstanceId, selectedInstance } = useInstance();
  const [gridConfig, setGridConfig] = useState<GridConfig | null>(null);
  const [orders, setOrders] = useState<GridOrder[]>([]);
  const [positions, setPositions] = useState<GridPosition[]>([]);
  const [currentPrice, setCurrentPrice] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchGridData = useCallback(async () => {
    try {
      // Fetch grid config from instance
      const [configRes, ordersRes, positionsRes, priceRes] = await Promise.allSettled([
        fetch(withInstance(`${API_BASE}/api/yaml-config?section=instances`)).then(r => r.json()),
        fetch(withInstance(`${API_BASE}/api/orders`)).then(r => r.json()),
        fetch(withInstance(`${API_BASE}/api/positions`)).then(r => r.json()),
        fetchWithMock(withInstance(`${API_BASE}/api/monitoring/price-health`), mockPriceHealth),
      ]);

      // Parse grid config
      if (configRes.status === 'fulfilled') {
        const data = configRes.value.data || configRes.value;
        // Try to find grid config for selected instance
        let grid = selectedInstance?.grid;
        if (!grid && data?.instances) {
          const inst = Object.values(data.instances).find((i: any) => 
            i.symbol === selectedInstance?.symbol && i.mode === selectedInstance?.mode
          ) as any;
          grid = inst?.grid;
        }
        if (grid) {
          const g = grid as any;
          setGridConfig({
            lower: g.lower || g.min || 0,
            upper: g.upper || g.max || 0,
            step: g.step || g.spacing || 0,
            levels: g.levels || Math.ceil((g.upper - g.lower) / g.step) || 10,
            reference_price: g.reference || g.reference_price,
          });
        } else {
          // Demo grid
          setGridConfig({
            lower: 90000,
            upper: 100000,
            step: 500,
            levels: 20,
          });
        }
      }

      // Parse orders
      if (ordersRes.status === 'fulfilled') {
        const ordersData = ordersRes.value.orders || ordersRes.value.data?.orders || ordersRes.value;
        if (Array.isArray(ordersData)) {
          setOrders(ordersData.map((o: any) => ({
            id: o.id || o.order_id,
            price: o.price || o.limit_price || 0,
            side: o.side?.toLowerCase() || 'buy',
            size: o.size || o.quantity || 0,
            state: o.state || o.status || 'open',
          })));
        }
      }

      // Parse positions
      if (positionsRes.status === 'fulfilled') {
        const posData = positionsRes.value.positions || positionsRes.value.data?.positions || positionsRes.value;
        if (Array.isArray(posData)) {
          setPositions(posData.map((p: any) => ({
            entry_price: p.entry_price || p.avg_entry || 0,
            size: p.size || p.quantity || 0,
            side: p.side || (p.size > 0 ? 'long' : 'short'),
            unrealized_pnl: p.unrealized_pnl || p.pnl || 0,
          })));
        }
      }

      // Parse current price
      if (priceRes.status === 'fulfilled') {
        const priceData: any = (priceRes.value as any).data || priceRes.value;
        setCurrentPrice(priceData.current_price || priceData.price || priceData.mark_price || 0);
      }

      setError(null);
    } catch (err) {
      setError('Failed to fetch grid data');
      console.error('Grid fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [withInstance, selectedInstance]);

  useEffect(() => {
    fetchGridData();
    const interval = setInterval(fetchGridData, 5000);
    return () => clearInterval(interval);
  }, [fetchGridData, selectedInstanceId]);

  // Calculate grid levels
  const gridLevels = useMemo(() => {
    if (!gridConfig) return [];
    
    const levels: GridLevel[] = [];
    const { lower, upper, step } = gridConfig;
    
    for (let price = lower; price <= upper; price += step) {
      const hasOrder = orders.some(o => Math.abs(o.price - price) < step * 0.1);
      const order = orders.find(o => Math.abs(o.price - price) < step * 0.1);
      const hasPosition = positions.some(p => Math.abs(p.entry_price - price) < step * 0.5);
      const position = positions.find(p => Math.abs(p.entry_price - price) < step * 0.5);
      
      levels.push({
        price,
        type: order ? order.side : 'none',
        hasOrder,
        hasPosition,
        orderId: order?.id,
        positionSize: position?.size,
      });
    }
    
    return levels.reverse(); // Higher prices at top
  }, [gridConfig, orders, positions]);

  // Calculate price position percentage
  const pricePositionPercent = useMemo(() => {
    if (!gridConfig || !currentPrice) return 50;
    const { lower, upper } = gridConfig;
    const range = upper - lower;
    return Math.min(100, Math.max(0, ((currentPrice - lower) / range) * 100));
  }, [gridConfig, currentPrice]);

  if (loading) {
    return (
      <div className={styles.panel}>
        <div className={styles.loading}>Loading grid visualization...</div>
      </div>
    );
  }

  if (!gridConfig) {
    return (
      <div className={styles.panel}>
        <div className={styles.noData}>No grid configuration found for this instance</div>
      </div>
    );
  }

  return (
    <div className={styles.panel}>
      <header className={styles.header}>
        <h2 className={styles.title}>📊 Grid Levels</h2>
        <div className={styles.headerInfo}>
          <span className={styles.instanceBadge}>
            {selectedInstance?.symbol || 'BTC'} {selectedInstance?.mode || 'LONG'}
          </span>
          <span className={styles.priceBadge}>
            ${currentPrice.toLocaleString()}
          </span>
          <button className={styles.refreshBtn} onClick={fetchGridData}>🔄</button>
        </div>
      </header>

      {error && <div className={styles.error}>{error}</div>}

      <div className={styles.content}>
        {/* Grid Stats */}
        <div className={styles.statsBar}>
          <div className={styles.stat}>
            <span className={styles.statLabel}>Upper</span>
            <span className={styles.statValue}>${gridConfig.upper.toLocaleString()}</span>
          </div>
          <div className={styles.stat}>
            <span className={styles.statLabel}>Lower</span>
            <span className={styles.statValue}>${gridConfig.lower.toLocaleString()}</span>
          </div>
          <div className={styles.stat}>
            <span className={styles.statLabel}>Step</span>
            <span className={styles.statValue}>${gridConfig.step.toLocaleString()}</span>
          </div>
          <div className={styles.stat}>
            <span className={styles.statLabel}>Levels</span>
            <span className={styles.statValue}>{gridLevels.length}</span>
          </div>
          <div className={styles.stat}>
            <span className={styles.statLabel}>Orders</span>
            <span className={styles.statValue}>{orders.length}</span>
          </div>
          <div className={styles.stat}>
            <span className={styles.statLabel}>Positions</span>
            <span className={styles.statValue}>{positions.length}</span>
          </div>
        </div>

        {/* Grid Visualization */}
        <div className={styles.gridContainer}>
          {/* Current Price Indicator */}
          <div 
            className={styles.currentPriceLine}
            style={{ bottom: `${pricePositionPercent}%` }}
          >
            <span className={styles.currentPriceLabel}>
              ${currentPrice.toLocaleString()}
            </span>
          </div>

          {/* Grid Levels */}
          <div className={styles.levelsContainer}>
            {gridLevels.map((level, i) => (
              <div 
                key={i}
                className={`${styles.gridLevel} ${styles[level.type]}`}
                data-has-order={level.hasOrder}
                data-has-position={level.hasPosition}
              >
                <span className={styles.levelPrice}>
                  ${level.price.toLocaleString()}
                </span>
                <div className={styles.levelBar}>
                  {level.hasOrder && (
                    <div className={`${styles.orderMarker} ${styles[level.type]}`}>
                      {level.type === 'buy' ? '🟢' : level.type === 'sell' ? '🔴' : ''}
                    </div>
                  )}
                  {level.hasPosition && (
                    <div className={styles.positionMarker}>
                      📍 {level.positionSize?.toFixed(4)}
                    </div>
                  )}
                </div>
                <span className={styles.levelStatus}>
                  {level.hasOrder ? (level.type === 'buy' ? 'BUY' : 'SELL') : '-'}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Legend */}
        <div className={styles.legend}>
          <div className={styles.legendItem}>
            <span className={styles.legendDot} data-type="buy" />
            <span>Buy Order</span>
          </div>
          <div className={styles.legendItem}>
            <span className={styles.legendDot} data-type="sell" />
            <span>Sell Order</span>
          </div>
          <div className={styles.legendItem}>
            <span className={styles.legendDot} data-type="position" />
            <span>Position</span>
          </div>
          <div className={styles.legendItem}>
            <span className={styles.legendDot} data-type="price" />
            <span>Current Price</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default GridLevelChart;
