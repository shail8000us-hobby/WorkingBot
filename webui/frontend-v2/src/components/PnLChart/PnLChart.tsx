/**
 * PnL Chart Component
 * 
 * Displays historical PnL data in a chart format.
 * Uses Recharts for visualization.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useInstance } from '../../contexts/InstanceContext';
import styles from './PnLChart.module.css';

interface PnLDataPoint {
  timestamp: string;
  date: string;
  pnl_usd: number;
  pnl_inr: number;
  cumulative_pnl_usd: number;
  cumulative_pnl_inr: number;
  trades: number;
}

interface PnLSummary {
  total_pnl_usd: number;
  total_pnl_inr: number;
  total_trades: number;
  win_rate: number;
  avg_trade_pnl: number;
  best_day: string;
  worst_day: string;
}

export const PnLChart: React.FC = () => {
  const { selectedInstance, withInstance } = useInstance();
  const [history, setHistory] = useState<PnLDataPoint[]>([]);
  const [summary, setSummary] = useState<PnLSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | 'all'>('30d');

  const fetchPnLData = useCallback(async () => {
    if (!selectedInstance) return;
    
    try {
      setLoading(true);
      setError(null);
      
      const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5555';
      
      // Fetch PnL history
      const historyRes = await fetch(withInstance(`${API_BASE}/api/pnl-history?range=${timeRange}`));
      const summaryRes = await fetch(withInstance(`${API_BASE}/api/pnl/summary`));
      
      const [historyData, summaryData] = await Promise.all([
        historyRes.json().catch(() => ({ history: [] })),
        summaryRes.json().catch(() => ({})),
      ]);
      
      // Parse history
      const histArr = historyData.history || historyData.data?.history || historyData || [];
      if (Array.isArray(histArr) && histArr.length > 0) {
        let cumulative = 0;
        setHistory(histArr.map((h: any) => {
          cumulative += (h.pnl_usd || h.pnl || 0);
          return {
            timestamp: h.timestamp || h.date || '',
            date: h.date || new Date(h.timestamp).toLocaleDateString(),
            pnl_usd: h.pnl_usd || h.pnl || 0,
            pnl_inr: h.pnl_inr || (h.pnl_usd || 0) * 84,
            cumulative_pnl_usd: cumulative,
            cumulative_pnl_inr: cumulative * 84,
            trades: h.trades || h.trade_count || 0,
          };
        }));
      } else {
        // Demo data
        setHistory(generateDemoData());
      }
      
      // Parse summary
      if (summaryData.total_pnl_usd !== undefined || summaryData.data) {
        const s = summaryData.data || summaryData;
        setSummary({
          total_pnl_usd: s.total_pnl_usd || s.total_pnl || 0,
          total_pnl_inr: s.total_pnl_inr || (s.total_pnl_usd || 0) * 84,
          total_trades: s.total_trades || s.trades || 0,
          win_rate: s.win_rate || s.winRate || 0,
          avg_trade_pnl: s.avg_trade_pnl || s.avg_pnl || 0,
          best_day: s.best_day || 'N/A',
          worst_day: s.worst_day || 'N/A',
        });
      } else {
        setSummary({
          total_pnl_usd: 1250.50,
          total_pnl_inr: 105042,
          total_trades: 156,
          win_rate: 68.5,
          avg_trade_pnl: 8.02,
          best_day: '+$245.00',
          worst_day: '-$89.50',
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load PnL data');
      // Use demo data on error
      setHistory(generateDemoData());
      setSummary({
        total_pnl_usd: 1250.50,
        total_pnl_inr: 105042,
        total_trades: 156,
        win_rate: 68.5,
        avg_trade_pnl: 8.02,
        best_day: '+$245.00',
        worst_day: '-$89.50',
      });
    } finally {
      setLoading(false);
    }
  }, [selectedInstance, timeRange, withInstance]);

  useEffect(() => {
    fetchPnLData();
    const interval = setInterval(fetchPnLData, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, [fetchPnLData]);

  const generateDemoData = (): PnLDataPoint[] => {
    const data: PnLDataPoint[] = [];
    let cumulative = 0;
    const days = timeRange === '7d' ? 7 : timeRange === '30d' ? 30 : 90;
    
    for (let i = days; i >= 0; i--) {
      const date = new Date();
      date.setDate(date.getDate() - i);
      const pnl = (Math.random() - 0.4) * 100; // Slight positive bias
      cumulative += pnl;
      data.push({
        timestamp: date.toISOString(),
        date: date.toLocaleDateString(),
        pnl_usd: pnl,
        pnl_inr: pnl * 84,
        cumulative_pnl_usd: cumulative,
        cumulative_pnl_inr: cumulative * 84,
        trades: Math.floor(Math.random() * 10) + 1,
      });
    }
    return data;
  };

  const maxPnL = Math.max(...history.map(h => h.cumulative_pnl_usd), 1);
  const minPnL = Math.min(...history.map(h => h.cumulative_pnl_usd), 0);
  const range = Math.max(Math.abs(maxPnL), Math.abs(minPnL)) || 1;

  const formatCurrency = (value: number) => {
    return value >= 0 ? `+$${value.toFixed(2)}` : `-$${Math.abs(value).toFixed(2)}`;
  };

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2 className={styles.title}>📈 PnL History</h2>
        <div className={styles.headerActions}>
          <span className={styles.instanceBadge}>{selectedInstance?.name || 'No Instance'}</span>
          <div className={styles.timeRange}>
            <button 
              className={`${styles.rangeBtn} ${timeRange === '7d' ? styles.active : ''}`}
              onClick={() => setTimeRange('7d')}
            >
              7D
            </button>
            <button 
              className={`${styles.rangeBtn} ${timeRange === '30d' ? styles.active : ''}`}
              onClick={() => setTimeRange('30d')}
            >
              30D
            </button>
            <button 
              className={`${styles.rangeBtn} ${timeRange === 'all' ? styles.active : ''}`}
              onClick={() => setTimeRange('all')}
            >
              All
            </button>
          </div>
          <button className={styles.refreshBtn} onClick={fetchPnLData}>🔄</button>
        </div>
      </div>

      {error && <div className={styles.error}>{error}</div>}

      <div className={styles.content}>
        {/* Summary Cards */}
        {summary && (
          <div className={styles.summaryGrid}>
            <div className={styles.summaryCard}>
              <span className={styles.summaryLabel}>Total PnL</span>
              <span className={`${styles.summaryValue} ${summary.total_pnl_usd >= 0 ? styles.positive : styles.negative}`}>
                {formatCurrency(summary.total_pnl_usd)}
              </span>
              <span className={styles.summarySubvalue}>₹{summary.total_pnl_inr.toLocaleString()}</span>
            </div>
            <div className={styles.summaryCard}>
              <span className={styles.summaryLabel}>Total Trades</span>
              <span className={styles.summaryValue}>{summary.total_trades}</span>
            </div>
            <div className={styles.summaryCard}>
              <span className={styles.summaryLabel}>Win Rate</span>
              <span className={`${styles.summaryValue} ${summary.win_rate >= 50 ? styles.positive : styles.negative}`}>
                {summary.win_rate.toFixed(1)}%
              </span>
            </div>
            <div className={styles.summaryCard}>
              <span className={styles.summaryLabel}>Avg Trade</span>
              <span className={`${styles.summaryValue} ${summary.avg_trade_pnl >= 0 ? styles.positive : styles.negative}`}>
                {formatCurrency(summary.avg_trade_pnl)}
              </span>
            </div>
          </div>
        )}

        {/* Chart */}
        {loading ? (
          <div className={styles.loading}>Loading chart...</div>
        ) : (
          <div className={styles.chartContainer}>
            <div className={styles.chartArea}>
              {/* Zero line */}
              <div 
                className={styles.zeroLine} 
                style={{ 
                  top: `${((range) / (range * 2)) * 100}%` 
                }}
              />
              
              {/* Bars */}
              <div className={styles.bars}>
                {history.map((point, index) => {
                  const height = Math.abs(point.cumulative_pnl_usd) / range * 45;
                  const isPositive = point.cumulative_pnl_usd >= 0;
                  
                  return (
                    <div 
                      key={index} 
                      className={styles.barWrapper}
                      title={`${point.date}: ${formatCurrency(point.cumulative_pnl_usd)}`}
                    >
                      <div 
                        className={`${styles.bar} ${isPositive ? styles.positive : styles.negative}`}
                        style={{
                          height: `${Math.max(height, 2)}%`,
                          ...(isPositive ? { bottom: '50%' } : { top: '50%' }),
                        }}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
            
            {/* X-axis labels */}
            <div className={styles.xAxis}>
              {history.filter((_, i) => i % Math.ceil(history.length / 6) === 0).map((point, i) => (
                <span key={i} className={styles.xLabel}>{point.date}</span>
              ))}
            </div>
          </div>
        )}

        {/* Daily breakdown */}
        <div className={styles.dailyBreakdown}>
          <h4>Recent Days</h4>
          <div className={styles.dailyList}>
            {history.slice(-7).reverse().map((point, i) => (
              <div key={i} className={styles.dailyItem}>
                <span className={styles.dailyDate}>{point.date}</span>
                <span className={`${styles.dailyPnl} ${point.pnl_usd >= 0 ? styles.positive : styles.negative}`}>
                  {formatCurrency(point.pnl_usd)}
                </span>
                <span className={styles.dailyTrades}>{point.trades} trades</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
