/**
 * MonitoringDashboard - 5-Layer Monitoring System
 * 
 * Shows comprehensive monitoring from all 5 layers:
 * 1. Price Health
 * 2. Pre-Order Stats
 * 3. TP Verification
 * 4. Anomaly Detection
 * 5. Predictive Map
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useInstance } from '../../contexts/InstanceContext';
import { fetchWithMock, mockPriceHealth, mockPreOrderStats, mockTPVerification, mockAnomalies, mockPredictiveMap } from '../../utils/mockData';
import styles from './MonitoringDashboard.module.css';

interface PriceHealth {
  current_price: number;
  last_update: string;
  price_age_seconds: number;
  is_stale: boolean;
  spread_percent: number;
  volatility_1h: number;
}

interface PreOrderStats {
  pending_buys: number;
  pending_sells: number;
  total_pending_value: number;
  oldest_order_age: number;
  avg_fill_time: number;
}

interface TpVerification {
  last_tp_time: string;
  tp_count_24h: number;
  avg_tp_profit: number;
  missed_tps: number;
  tp_success_rate: number;
}

interface Anomaly {
  id: string;
  type: 'warning' | 'error' | 'info';
  message: string;
  timestamp: string;
  resolved: boolean;
}

interface PredictiveAction {
  action: string;
  probability: number;
  trigger: string;
  eta?: string;
}

interface MonitoringData {
  price_health: PriceHealth | null;
  pre_order_stats: PreOrderStats | null;
  tp_verification: TpVerification | null;
  anomalies: Anomaly[];
  predictive_actions: PredictiveAction[];
  overall_health: 'healthy' | 'degraded' | 'critical';
  last_update: string;
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5555';

export const MonitoringDashboard: React.FC = () => {
  const { withInstance, selectedInstanceId, selectedInstance } = useInstance();
  const [data, setData] = useState<MonitoringData>({
    price_health: null,
    pre_order_stats: null,
    tp_verification: null,
    anomalies: [],
    predictive_actions: [],
    overall_health: 'healthy',
    last_update: new Date().toISOString(),
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeLayer, setActiveLayer] = useState<number>(1);

  const fetchMonitoringData = useCallback(async () => {
    try {
      // Fetch all 5 layers in parallel with mock fallbacks
      const [priceRes, preOrderRes, tpRes, anomalyRes, predictiveRes, statusRes] = await Promise.allSettled([
        fetchWithMock(withInstance(`${API_BASE}/api/monitoring/price-health`), mockPriceHealth),
        fetchWithMock(withInstance(`${API_BASE}/api/monitoring/pre-order-stats`), mockPreOrderStats),
        fetchWithMock(withInstance(`${API_BASE}/api/monitoring/tp-verification`), mockTPVerification),
        fetchWithMock(withInstance(`${API_BASE}/api/monitoring/anomalies`), mockAnomalies),
        fetchWithMock(withInstance(`${API_BASE}/api/monitoring/predictive-map`), mockPredictiveMap),
        fetchWithMock(withInstance(`${API_BASE}/api/monitoring/status`), { success: true, status: 'mock' }),
      ]);

      const newData: Partial<MonitoringData> = {
        last_update: new Date().toISOString(),
      };

      // Parse price health
      if (priceRes.status === 'fulfilled') {
        const priceValue = priceRes.value as any;
        const ph = priceValue.data || priceValue;
        newData.price_health = {
          current_price: ph.current_price || ph.price || 0,
          last_update: ph.last_update || ph.timestamp || new Date().toISOString(),
          price_age_seconds: ph.price_age_seconds || ph.age || 0,
          is_stale: ph.is_stale || ph.stale || false,
          spread_percent: ph.spread_percent || ph.spread || 0,
          volatility_1h: ph.volatility_1h || ph.volatility || 0,
        };
      }

      // Parse pre-order stats
      if (preOrderRes.status === 'fulfilled') {
        const preOrderValue = preOrderRes.value as any;
        const pos = preOrderValue.data || preOrderValue;
        newData.pre_order_stats = {
          pending_buys: pos.pending_buys || 0,
          pending_sells: pos.pending_sells || 0,
          total_pending_value: pos.total_pending_value || pos.total_value || 0,
          oldest_order_age: pos.oldest_order_age || 0,
          avg_fill_time: pos.avg_fill_time || 0,
        };
      }

      // Parse TP verification
      if (tpRes.status === 'fulfilled') {
        const tpValue = tpRes.value as any;
        const tp = tpValue.data || tpValue;
        newData.tp_verification = {
          last_tp_time: tp.last_tp_time || tp.last_tp || 'N/A',
          tp_count_24h: tp.tp_count_24h || tp.count_24h || 0,
          avg_tp_profit: tp.avg_tp_profit || tp.avg_profit || 0,
          missed_tps: tp.missed_tps || 0,
          tp_success_rate: tp.tp_success_rate || tp.success_rate || 100,
        };
      }

      // Parse anomalies
      if (anomalyRes.status === 'fulfilled') {
        const an = anomalyRes.value.data || anomalyRes.value;
        if (Array.isArray(an.anomalies || an)) {
          newData.anomalies = (an.anomalies || an).map((a: any, i: number) => ({
            id: a.id || `anomaly-${i}`,
            type: a.type || a.severity || 'warning',
            message: a.message || a.description || 'Unknown anomaly',
            timestamp: a.timestamp || new Date().toISOString(),
            resolved: a.resolved || false,
          }));
        }
      }

      // Parse predictive map
      if (predictiveRes.status === 'fulfilled') {
        const pm: any = (predictiveRes.value as any).data || predictiveRes.value;
        if (Array.isArray(pm.next_actions || pm.actions)) {
          newData.predictive_actions = (pm.next_actions || pm.actions).map((a: any) => ({
            action: a.action || a.name || 'Unknown',
            probability: a.probability || a.confidence || 0,
            trigger: a.trigger || a.condition || 'On signal',
            eta: a.eta || a.estimated_time,
          }));
        }
      }

      // Parse overall status
      if (statusRes.status === 'fulfilled') {
        const st: any = (statusRes.value as any).data || statusRes.value;
        newData.overall_health = st.health || st.status || st.overall_health || 'healthy';
      }

      setData(prev => ({ ...prev, ...newData }));
      setError(null);
    } catch (err) {
      setError('Failed to fetch monitoring data');
      console.error('Monitoring fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [withInstance]);

  useEffect(() => {
    fetchMonitoringData();
    const interval = setInterval(fetchMonitoringData, 5000);
    return () => clearInterval(interval);
  }, [fetchMonitoringData, selectedInstanceId]);

  const getHealthColor = (health: string): string => {
    switch (health) {
      case 'healthy': return 'var(--color-success)';
      case 'degraded': return 'var(--color-warning)';
      case 'critical': return 'var(--color-danger)';
      default: return 'var(--color-text-muted)';
    }
  };

  if (loading) {
    return (
      <div className={styles.panel}>
        <div className={styles.loading}>Loading monitoring data...</div>
      </div>
    );
  }

  return (
    <div className={styles.panel}>
      <header className={styles.header}>
        <h2 className={styles.title}>📊 5-Layer Monitoring</h2>
        <div className={styles.headerInfo}>
          <span 
            className={styles.healthBadge}
            style={{ backgroundColor: getHealthColor(data.overall_health) }}
          >
            {data.overall_health.toUpperCase()}
          </span>
          <span className={styles.instanceBadge}>
            {selectedInstance?.symbol || 'All'} {selectedInstance?.mode || ''}
          </span>
          <button className={styles.refreshBtn} onClick={fetchMonitoringData}>🔄</button>
        </div>
      </header>

      {error && <div className={styles.error}>{error}</div>}

      {/* Layer Tabs */}
      <div className={styles.layerTabs}>
        {[
          { num: 1, name: 'Price Health', icon: '💰' },
          { num: 2, name: 'Pre-Order', icon: '📋' },
          { num: 3, name: 'TP Verification', icon: '✅' },
          { num: 4, name: 'Anomalies', icon: '⚠️' },
          { num: 5, name: 'Predictive', icon: '🔮' },
        ].map(layer => (
          <button
            key={layer.num}
            className={`${styles.layerTab} ${activeLayer === layer.num ? styles.active : ''}`}
            onClick={() => setActiveLayer(layer.num)}
          >
            <span className={styles.layerIcon}>{layer.icon}</span>
            <span className={styles.layerName}>{layer.name}</span>
          </button>
        ))}
      </div>

      <div className={styles.content}>
        {/* Layer 1: Price Health */}
        {activeLayer === 1 && (
          <div className={styles.layerContent}>
            <h3>💰 Price Health</h3>
            {data.price_health ? (
              <div className={styles.metricsGrid}>
                <div className={styles.metric}>
                  <span className={styles.metricLabel}>Current Price</span>
                  <span className={styles.metricValue}>
                    ${data.price_health.current_price.toLocaleString()}
                  </span>
                </div>
                <div className={styles.metric}>
                  <span className={styles.metricLabel}>Price Age</span>
                  <span className={styles.metricValue} data-stale={data.price_health.is_stale}>
                    {data.price_health.price_age_seconds}s
                    {data.price_health.is_stale && ' ⚠️'}
                  </span>
                </div>
                <div className={styles.metric}>
                  <span className={styles.metricLabel}>Spread</span>
                  <span className={styles.metricValue}>
                    {data.price_health.spread_percent.toFixed(3)}%
                  </span>
                </div>
                <div className={styles.metric}>
                  <span className={styles.metricLabel}>1h Volatility</span>
                  <span className={styles.metricValue}>
                    {data.price_health.volatility_1h.toFixed(2)}%
                  </span>
                </div>
              </div>
            ) : (
              <p className={styles.noData}>No price health data available</p>
            )}
          </div>
        )}

        {/* Layer 2: Pre-Order Stats */}
        {activeLayer === 2 && (
          <div className={styles.layerContent}>
            <h3>📋 Pre-Order Statistics</h3>
            {data.pre_order_stats ? (
              <div className={styles.metricsGrid}>
                <div className={styles.metric}>
                  <span className={styles.metricLabel}>Pending Buys</span>
                  <span className={styles.metricValue}>{data.pre_order_stats.pending_buys}</span>
                </div>
                <div className={styles.metric}>
                  <span className={styles.metricLabel}>Pending Sells</span>
                  <span className={styles.metricValue}>{data.pre_order_stats.pending_sells}</span>
                </div>
                <div className={styles.metric}>
                  <span className={styles.metricLabel}>Total Value</span>
                  <span className={styles.metricValue}>
                    ${data.pre_order_stats.total_pending_value.toLocaleString()}
                  </span>
                </div>
                <div className={styles.metric}>
                  <span className={styles.metricLabel}>Oldest Order</span>
                  <span className={styles.metricValue}>
                    {data.pre_order_stats.oldest_order_age}s
                  </span>
                </div>
                <div className={styles.metric}>
                  <span className={styles.metricLabel}>Avg Fill Time</span>
                  <span className={styles.metricValue}>
                    {data.pre_order_stats.avg_fill_time.toFixed(1)}s
                  </span>
                </div>
              </div>
            ) : (
              <p className={styles.noData}>No pre-order stats available</p>
            )}
          </div>
        )}

        {/* Layer 3: TP Verification */}
        {activeLayer === 3 && (
          <div className={styles.layerContent}>
            <h3>✅ Take Profit Verification</h3>
            {data.tp_verification ? (
              <div className={styles.metricsGrid}>
                <div className={styles.metric}>
                  <span className={styles.metricLabel}>Last TP</span>
                  <span className={styles.metricValue}>
                    {data.tp_verification.last_tp_time}
                  </span>
                </div>
                <div className={styles.metric}>
                  <span className={styles.metricLabel}>24h TPs</span>
                  <span className={styles.metricValue}>{data.tp_verification.tp_count_24h}</span>
                </div>
                <div className={styles.metric}>
                  <span className={styles.metricLabel}>Avg Profit</span>
                  <span className={styles.metricValue}>
                    ${data.tp_verification.avg_tp_profit.toFixed(2)}
                  </span>
                </div>
                <div className={styles.metric}>
                  <span className={styles.metricLabel}>Missed TPs</span>
                  <span className={styles.metricValue} data-alert={data.tp_verification.missed_tps > 0}>
                    {data.tp_verification.missed_tps}
                  </span>
                </div>
                <div className={styles.metric}>
                  <span className={styles.metricLabel}>Success Rate</span>
                  <span className={styles.metricValue}>
                    {data.tp_verification.tp_success_rate.toFixed(1)}%
                  </span>
                </div>
              </div>
            ) : (
              <p className={styles.noData}>No TP verification data available</p>
            )}
          </div>
        )}

        {/* Layer 4: Anomalies */}
        {activeLayer === 4 && (
          <div className={styles.layerContent}>
            <h3>⚠️ Anomaly Detection</h3>
            {data.anomalies.length > 0 ? (
              <div className={styles.anomalyList}>
                {data.anomalies.map(anomaly => (
                  <div 
                    key={anomaly.id} 
                    className={`${styles.anomalyItem} ${styles[anomaly.type]}`}
                    data-resolved={anomaly.resolved}
                  >
                    <span className={styles.anomalyIcon}>
                      {anomaly.type === 'error' ? '❌' : anomaly.type === 'warning' ? '⚠️' : 'ℹ️'}
                    </span>
                    <div className={styles.anomalyContent}>
                      <span className={styles.anomalyMessage}>{anomaly.message}</span>
                      <span className={styles.anomalyTime}>
                        {new Date(anomaly.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    {anomaly.resolved && <span className={styles.resolvedBadge}>Resolved</span>}
                  </div>
                ))}
              </div>
            ) : (
              <p className={styles.noData}>✅ No anomalies detected</p>
            )}
          </div>
        )}

        {/* Layer 5: Predictive Map */}
        {activeLayer === 5 && (
          <div className={styles.layerContent}>
            <h3>🔮 Predictive Actions</h3>
            {data.predictive_actions.length > 0 ? (
              <div className={styles.actionsList}>
                {data.predictive_actions.map((action, i) => (
                  <div key={i} className={styles.actionItem}>
                    <div className={styles.actionHeader}>
                      <span className={styles.actionName}>{action.action}</span>
                      <span className={styles.actionProb}>
                        {(action.probability * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className={styles.actionDetails}>
                      <span className={styles.actionTrigger}>📍 {action.trigger}</span>
                      {action.eta && <span className={styles.actionEta}>⏱️ {action.eta}</span>}
                    </div>
                    <div className={styles.probBar}>
                      <div 
                        className={styles.probFill}
                        style={{ width: `${action.probability * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className={styles.noData}>No predictive actions available</p>
            )}
          </div>
        )}
      </div>

      {/* Last Update Footer */}
      <div className={styles.footer}>
        Last updated: {new Date(data.last_update).toLocaleTimeString()}
      </div>
    </div>
  );
};

export default MonitoringDashboard;
