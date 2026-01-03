/**
 * RSIPanel - RSI Monitoring Panel
 * 
 * Monitor RSI values across all instances with thresholds.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useInstance } from '../../contexts/InstanceContext';
import { fetchWithMock, mockRSIStatus } from '../../utils/mockData';
import styles from './RSIPanel.module.css';

interface RSIData {
  symbol: string;
  mode: string;
  rsi: number | null;
  status: 'GO' | 'STOP' | 'UNKNOWN' | 'ERROR';
  statusText: string;
  shouldStop: boolean;
  threshold: number;
  lastUpdate: string;
}

interface RSIConfig {
  enabled: boolean;
  period: number;
  longThreshold: number;
  shortThreshold: number;
  timeframe: string;
  checkInterval: number;
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5555';

export const RSIPanel: React.FC = () => {
  const { selectedInstanceId, withInstance } = useInstance();
  const [rsiData, setRsiData] = useState<Record<string, RSIData>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [config, setConfig] = useState<RSIConfig>({
    enabled: true,
    period: 14,
    longThreshold: 30,
    shortThreshold: 70,
    timeframe: '1h',
    checkInterval: 300
  });
  const [viewMode, setViewMode] = useState<'cards' | 'table'>('cards');
  const [saving, setSaving] = useState(false);

  // Fetch RSI status for all symbols
  const fetchRSIData = useCallback(async () => {
    try {
      const data = await fetchWithMock(
        withInstance(`${API_BASE}/api/guardian/rsi/status`),
        mockRSIStatus
      );
      
      if (data.success && data.symbols) {
        const formattedData: Record<string, RSIData> = {};
        
        Object.entries(data.symbols).forEach(([key, value]: [string, any]) => {
          formattedData[key] = {
            symbol: value.symbol || key.split('_')[0] || key,
            mode: value.mode || key.split('_')[1] || 'LONG',
            rsi: value.rsi,
            status: value.should_stop ? 'STOP' : value.rsi !== null ? 'GO' : 'UNKNOWN',
            statusText: value.status_text || (value.should_stop ? 'Trading Paused' : 'Trading Active'),
            shouldStop: value.should_stop || false,
            threshold: value.threshold || (value.mode === 'SHORT' ? config.shortThreshold : config.longThreshold),
            lastUpdate: value.last_update || new Date().toISOString()
          };
        });
        
        setRsiData(formattedData);
        setError(null);
      }
    } catch (err) {
      setError(`Failed to fetch RSI data: ${err}`);
    } finally {
      setLoading(false);
    }
  }, [config.longThreshold, config.shortThreshold, withInstance]);

  // Fetch RSI config
  const fetchConfig = useCallback(async () => {
    try {
      const response = await fetch(withInstance(`${API_BASE}/api/yaml-config?section=safety.rsi`));
      const data = await response.json();
      
      if (data.success && data.data) {
        setConfig({
          enabled: data.data.enabled ?? true,
          period: data.data.period ?? 14,
          longThreshold: data.data.long_threshold ?? 30,
          shortThreshold: data.data.short_threshold ?? 70,
          timeframe: data.data.timeframe ?? '1h',
          checkInterval: data.data.check_interval ?? 300
        });
      }
    } catch (err) {
      console.error('Failed to fetch RSI config:', err);
    }
  }, [withInstance]);

  useEffect(() => {
    fetchConfig();
    fetchRSIData();
    
    const interval = setInterval(fetchRSIData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, [fetchRSIData, fetchConfig, selectedInstanceId]);

  // Save RSI config
  const handleSaveConfig = async () => {
    setSaving(true);
    try {
      const response = await fetch(withInstance(`${API_BASE}/api/config/update`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          updates: {
            'safety.rsi.enabled': config.enabled,
            'safety.rsi.period': config.period,
            'safety.rsi.long_threshold': config.longThreshold,
            'safety.rsi.short_threshold': config.shortThreshold,
            'safety.rsi.timeframe': config.timeframe,
            'safety.rsi.check_interval': config.checkInterval
          }
        })
      });
      
      const data = await response.json();
      if (data.success) {
        setError(null);
      } else {
        setError(data.error || 'Failed to save config');
      }
    } catch (err) {
      setError(`Failed to save config: ${err}`);
    } finally {
      setSaving(false);
    }
  };

  // Get RSI color based on value
  const getRSIColor = (rsi: number | null, mode: string): string => {
    if (rsi === null) return 'var(--color-text-muted)';
    
    if (mode === 'LONG') {
      if (rsi < 30) return 'var(--color-success)'; // Oversold - good for long
      if (rsi > 70) return 'var(--color-danger)';  // Overbought - bad for long
      return 'var(--color-warning)';
    } else {
      if (rsi > 70) return 'var(--color-success)'; // Overbought - good for short
      if (rsi < 30) return 'var(--color-danger)';  // Oversold - bad for short
      return 'var(--color-warning)';
    }
  };

  // Get status badge class
  const getStatusClass = (status: string): string => {
    switch (status) {
      case 'GO': return styles.statusGo;
      case 'STOP': return styles.statusStop;
      default: return styles.statusUnknown;
    }
  };

  // Render RSI gauge
  const renderRSIGauge = (rsi: number | null, mode: string) => {
    if (rsi === null) {
      return <div className={styles.noData}>N/A</div>;
    }
    
    const rotation = (rsi / 100) * 180 - 90; // -90 to 90 degrees
    const color = getRSIColor(rsi, mode);
    
    return (
      <div className={styles.gauge}>
        <svg viewBox="0 0 100 50" className={styles.gaugeSvg}>
          {/* Background arc */}
          <path
            d="M 10 50 A 40 40 0 0 1 90 50"
            fill="none"
            stroke="var(--color-border)"
            strokeWidth="8"
          />
          {/* Colored zones */}
          <path
            d="M 10 50 A 40 40 0 0 1 28 20"
            fill="none"
            stroke="var(--color-success)"
            strokeWidth="8"
            opacity="0.3"
          />
          <path
            d="M 72 20 A 40 40 0 0 1 90 50"
            fill="none"
            stroke="var(--color-danger)"
            strokeWidth="8"
            opacity="0.3"
          />
          {/* Needle */}
          <line
            x1="50"
            y1="50"
            x2="50"
            y2="15"
            stroke={color}
            strokeWidth="3"
            strokeLinecap="round"
            transform={`rotate(${rotation} 50 50)`}
          />
          <circle cx="50" cy="50" r="4" fill={color} />
        </svg>
        <div className={styles.gaugeValue} style={{ color }}>
          {rsi.toFixed(1)}
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className={styles.panel}>
        <div className={styles.loading}>Loading RSI data...</div>
      </div>
    );
  }

  const rsiEntries = Object.entries(rsiData);

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2>📉 RSI Monitor</h2>
        <div className={styles.headerActions}>
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
          <button 
            className={styles.refreshBtn}
            onClick={fetchRSIData}
            title="Refresh"
          >
            🔄
          </button>
        </div>
      </div>

      {error && <div className={styles.error}>{error}</div>}

      {/* Config Section */}
      <div className={styles.configSection}>
        <h3>⚙️ RSI Settings</h3>
        <div className={styles.configGrid}>
          <div className={styles.configItem}>
            <label>Enabled</label>
            <label className={styles.toggleLabel}>
              <input
                type="checkbox"
                checked={config.enabled}
                onChange={(e) => setConfig({ ...config, enabled: e.target.checked })}
              />
              <span className={styles.toggleSwitch}></span>
            </label>
          </div>
          <div className={styles.configItem}>
            <label>Period</label>
            <input
              type="number"
              value={config.period}
              onChange={(e) => setConfig({ ...config, period: parseInt(e.target.value) || 14 })}
            />
          </div>
          <div className={styles.configItem}>
            <label>Long Threshold</label>
            <input
              type="number"
              value={config.longThreshold}
              onChange={(e) => setConfig({ ...config, longThreshold: parseFloat(e.target.value) || 30 })}
            />
          </div>
          <div className={styles.configItem}>
            <label>Short Threshold</label>
            <input
              type="number"
              value={config.shortThreshold}
              onChange={(e) => setConfig({ ...config, shortThreshold: parseFloat(e.target.value) || 70 })}
            />
          </div>
          <div className={styles.configItem}>
            <label>Timeframe</label>
            <select
              value={config.timeframe}
              onChange={(e) => setConfig({ ...config, timeframe: e.target.value })}
            >
              <option value="5m">5 minutes</option>
              <option value="15m">15 minutes</option>
              <option value="1h">1 hour</option>
              <option value="4h">4 hours</option>
              <option value="1d">1 day</option>
            </select>
          </div>
          <div className={styles.configItem}>
            <button 
              className={styles.saveBtn}
              onClick={handleSaveConfig}
              disabled={saving}
            >
              {saving ? 'Saving...' : '💾 Save'}
            </button>
          </div>
        </div>
      </div>

      {/* RSI Data */}
      <div className={styles.content}>
        {rsiEntries.length === 0 ? (
          <div className={styles.noData}>
            <p>No RSI data available</p>
            <p className={styles.hint}>RSI data will appear when the bot is running</p>
          </div>
        ) : viewMode === 'cards' ? (
          <div className={styles.cardsGrid}>
            {rsiEntries.map(([key, data]) => (
              <div key={key} className={`${styles.card} ${data.shouldStop ? styles.cardStop : styles.cardGo}`}>
                <div className={styles.cardHeader}>
                  <span className={styles.symbol}>{data.symbol}</span>
                  <span className={`${styles.mode} ${data.mode === 'LONG' ? styles.modeLong : styles.modeShort}`}>
                    {data.mode}
                  </span>
                </div>
                
                {renderRSIGauge(data.rsi, data.mode)}
                
                <div className={styles.cardFooter}>
                  <span className={`${styles.status} ${getStatusClass(data.status)}`}>
                    {data.status}
                  </span>
                  <span className={styles.statusText}>{data.statusText}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Mode</th>
                <th>RSI</th>
                <th>Threshold</th>
                <th>Status</th>
                <th>Last Update</th>
              </tr>
            </thead>
            <tbody>
              {rsiEntries.map(([key, data]) => (
                <tr key={key} className={data.shouldStop ? styles.rowStop : ''}>
                  <td className={styles.symbolCell}>{data.symbol}</td>
                  <td>
                    <span className={`${styles.modeBadge} ${data.mode === 'LONG' ? styles.modeLong : styles.modeShort}`}>
                      {data.mode}
                    </span>
                  </td>
                  <td style={{ color: getRSIColor(data.rsi, data.mode), fontWeight: 600 }}>
                    {data.rsi !== null ? data.rsi.toFixed(2) : 'N/A'}
                  </td>
                  <td>{data.threshold}</td>
                  <td>
                    <span className={`${styles.status} ${getStatusClass(data.status)}`}>
                      {data.status}
                    </span>
                  </td>
                  <td className={styles.timeCell}>
                    {new Date(data.lastUpdate).toLocaleTimeString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default RSIPanel;
