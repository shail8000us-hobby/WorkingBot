/**
 * Volatility Chart Component
 * 
 * Displays IV vs RV (Implied vs Realized Volatility) comparison.
 * Shows volatility trends and alerts.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useInstance } from '../../contexts/InstanceContext';
import { fetchWithMock, mockVolatilityStatus } from '../../utils/mockData';
import styles from './VolatilityChart.module.css';

interface VolatilityData {
  timestamp: string;
  iv: number; // Implied Volatility %
  rv: number; // Realized Volatility %
  iv_rv_ratio: number;
  percentile: number;
}

interface VolatilitySummary {
  current_iv: number;
  current_rv: number;
  iv_rv_ratio: number;
  iv_percentile: number;
  rv_percentile: number;
  regime: 'low' | 'normal' | 'high' | 'extreme';
  trend: 'rising' | 'falling' | 'stable';
  alert: string | null;
}

export const VolatilityChart: React.FC = () => {
  const { selectedInstance, withInstance } = useInstance();
  const [history, setHistory] = useState<VolatilityData[]>([]);
  const [summary, setSummary] = useState<VolatilitySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchVolatilityData = useCallback(async () => {
    if (!selectedInstance) return;
    
    try {
      setLoading(true);
      setError(null);
      
      const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5555';
      
      // Try to fetch volatility data
      const data = await fetchWithMock(
        withInstance(`${API_BASE}/api/volatility/status`),
        mockVolatilityStatus
      );
      
      if (data.history || data.data?.history) {
        const histArr = data.history || data.data.history;
        setHistory(histArr.map((h: any) => ({
          timestamp: h.timestamp || h.time,
          iv: h.iv || h.implied_volatility || 0,
          rv: h.rv || h.realized_volatility || 0,
          iv_rv_ratio: h.iv_rv_ratio || (h.iv / (h.rv || 1)),
          percentile: h.percentile || 50,
        })));
      } else {
        // Demo data - volatility API not available
        setHistory(generateDemoData());
      }
      
      if (data.current || data.summary) {
        const s: any = data.current || data.summary || data;
        setSummary({
          current_iv: s.iv || s.current_iv || 45.2,
          current_rv: s.rv || s.current_rv || 38.5,
          iv_rv_ratio: s.iv_rv_ratio || 1.17,
          iv_percentile: s.iv_percentile || 65,
          rv_percentile: s.rv_percentile || 52,
          regime: s.regime || 'normal',
          trend: s.trend || 'stable',
          alert: s.alert || null,
        });
      } else {
        setSummary({
          current_iv: 45.2,
          current_rv: 38.5,
          iv_rv_ratio: 1.17,
          iv_percentile: 65,
          rv_percentile: 52,
          regime: 'normal',
          trend: 'stable',
          alert: null,
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load volatility data');
      setHistory(generateDemoData());
      setSummary({
        current_iv: 45.2,
        current_rv: 38.5,
        iv_rv_ratio: 1.17,
        iv_percentile: 65,
        rv_percentile: 52,
        regime: 'normal',
        trend: 'stable',
        alert: null,
      });
    } finally {
      setLoading(false);
    }
  }, [selectedInstance, withInstance]);

  useEffect(() => {
    fetchVolatilityData();
    const interval = setInterval(fetchVolatilityData, 30000);
    return () => clearInterval(interval);
  }, [fetchVolatilityData]);

  const generateDemoData = (): VolatilityData[] => {
    const data: VolatilityData[] = [];
    let iv = 45;
    let rv = 38;
    
    for (let i = 48; i >= 0; i--) {
      const date = new Date();
      date.setHours(date.getHours() - i);
      
      // Random walk
      iv += (Math.random() - 0.5) * 4;
      rv += (Math.random() - 0.5) * 3;
      iv = Math.max(15, Math.min(100, iv));
      rv = Math.max(10, Math.min(80, rv));
      
      data.push({
        timestamp: date.toISOString(),
        iv,
        rv,
        iv_rv_ratio: iv / rv,
        percentile: Math.min(100, Math.max(0, 50 + (iv - 50) * 1.5)),
      });
    }
    return data;
  };

  const getRegimeColor = (regime: string) => {
    switch (regime) {
      case 'low': return '#22c55e';
      case 'normal': return '#6366f1';
      case 'high': return '#f59e0b';
      case 'extreme': return '#ef4444';
      default: return '#6b7280';
    }
  };

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'rising': return '📈';
      case 'falling': return '📉';
      default: return '➡️';
    }
  };

  const maxVol = Math.max(...history.map(h => Math.max(h.iv, h.rv)), 60);

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2 className={styles.title}>📊 Volatility Monitor</h2>
        <div className={styles.headerActions}>
          <span className={styles.instanceBadge}>{selectedInstance?.name || 'No Instance'}</span>
          <button className={styles.refreshBtn} onClick={fetchVolatilityData}>🔄</button>
        </div>
      </div>

      {error && <div className={styles.error}>{error}</div>}
      
      {summary?.alert && (
        <div className={styles.alert}>⚠️ {summary.alert}</div>
      )}

      <div className={styles.content}>
        {loading ? (
          <div className={styles.loading}>Loading volatility data...</div>
        ) : (
          <>
            {/* Summary Cards */}
            {summary && (
              <div className={styles.summaryGrid}>
                <div className={styles.summaryCard}>
                  <span className={styles.summaryLabel}>Implied Volatility</span>
                  <span className={styles.summaryValue}>{summary.current_iv.toFixed(1)}%</span>
                  <span className={styles.summarySubvalue}>
                    {summary.iv_percentile}th percentile
                  </span>
                </div>
                <div className={styles.summaryCard}>
                  <span className={styles.summaryLabel}>Realized Volatility</span>
                  <span className={styles.summaryValue}>{summary.current_rv.toFixed(1)}%</span>
                  <span className={styles.summarySubvalue}>
                    {summary.rv_percentile}th percentile
                  </span>
                </div>
                <div className={styles.summaryCard}>
                  <span className={styles.summaryLabel}>IV/RV Ratio</span>
                  <span className={`${styles.summaryValue} ${summary.iv_rv_ratio > 1.3 ? styles.elevated : ''}`}>
                    {summary.iv_rv_ratio.toFixed(2)}
                  </span>
                  <span className={styles.summarySubvalue}>
                    {summary.iv_rv_ratio > 1.3 ? 'Options expensive' : summary.iv_rv_ratio < 0.8 ? 'Options cheap' : 'Fair'}
                  </span>
                </div>
                <div className={styles.summaryCard}>
                  <span className={styles.summaryLabel}>Regime</span>
                  <span 
                    className={styles.regimeBadge}
                    style={{ backgroundColor: getRegimeColor(summary.regime) }}
                  >
                    {summary.regime.toUpperCase()}
                  </span>
                  <span className={styles.summarySubvalue}>
                    {getTrendIcon(summary.trend)} {summary.trend}
                  </span>
                </div>
              </div>
            )}

            {/* Chart */}
            <div className={styles.chartContainer}>
              <div className={styles.chartLegend}>
                <span className={styles.legendItem}>
                  <span className={styles.legendDot} style={{ background: '#6366f1' }} /> IV
                </span>
                <span className={styles.legendItem}>
                  <span className={styles.legendDot} style={{ background: '#22c55e' }} /> RV
                </span>
              </div>
              
              <div className={styles.chartArea}>
                {/* IV Line */}
                <svg className={styles.chartSvg} viewBox={`0 0 ${history.length * 10} 100`} preserveAspectRatio="none">
                  <polyline
                    className={styles.ivLine}
                    points={history.map((h, i) => `${i * 10},${100 - (h.iv / maxVol) * 100}`).join(' ')}
                    fill="none"
                    stroke="#6366f1"
                    strokeWidth="2"
                  />
                  <polyline
                    className={styles.rvLine}
                    points={history.map((h, i) => `${i * 10},${100 - (h.rv / maxVol) * 100}`).join(' ')}
                    fill="none"
                    stroke="#22c55e"
                    strokeWidth="2"
                  />
                </svg>
              </div>
              
              <div className={styles.yAxis}>
                <span>{maxVol.toFixed(0)}%</span>
                <span>{(maxVol / 2).toFixed(0)}%</span>
                <span>0%</span>
              </div>
            </div>

            {/* Volatility Regimes */}
            <div className={styles.regimeSection}>
              <h4>Volatility Levels Guide</h4>
              <div className={styles.regimeGrid}>
                <div className={styles.regimeItem}>
                  <span className={styles.regimeDot} style={{ background: '#22c55e' }} />
                  <span className={styles.regimeName}>Low (&lt;25%)</span>
                  <span className={styles.regimeDesc}>Tight spreads, small grid steps</span>
                </div>
                <div className={styles.regimeItem}>
                  <span className={styles.regimeDot} style={{ background: '#6366f1' }} />
                  <span className={styles.regimeName}>Normal (25-50%)</span>
                  <span className={styles.regimeDesc}>Standard trading conditions</span>
                </div>
                <div className={styles.regimeItem}>
                  <span className={styles.regimeDot} style={{ background: '#f59e0b' }} />
                  <span className={styles.regimeName}>High (50-75%)</span>
                  <span className={styles.regimeDesc}>Widen grid, reduce size</span>
                </div>
                <div className={styles.regimeItem}>
                  <span className={styles.regimeDot} style={{ background: '#ef4444' }} />
                  <span className={styles.regimeName}>Extreme (&gt;75%)</span>
                  <span className={styles.regimeDesc}>Consider pausing trading</span>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
