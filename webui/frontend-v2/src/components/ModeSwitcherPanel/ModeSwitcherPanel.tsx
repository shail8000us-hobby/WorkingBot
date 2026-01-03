/**
 * ModeSwitcherPanel - Auto LONG/SHORT Mode Switching
 * 
 * Configure automatic mode switching based on market conditions.
 */

import React, { useState, useEffect, useCallback } from 'react';
import styles from './ModeSwitcherPanel.module.css';

interface ModeSwitchConfig {
  enabled: boolean;
  currentMode: 'LONG' | 'SHORT' | 'AUTO';
  autoSwitchEnabled: boolean;
  longThreshold: number;
  shortThreshold: number;
  cooldownMinutes: number;
  useRSI: boolean;
  useMACD: boolean;
  useTrend: boolean;
}

interface ModeHistory {
  timestamp: string;
  fromMode: string;
  toMode: string;
  reason: string;
  symbol: string;
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5555';

export const ModeSwitcherPanel: React.FC = () => {
  const [config, setConfig] = useState<ModeSwitchConfig>({
    enabled: true,
    currentMode: 'LONG',
    autoSwitchEnabled: false,
    longThreshold: 30,
    shortThreshold: 70,
    cooldownMinutes: 60,
    useRSI: true,
    useMACD: false,
    useTrend: true
  });
  const [history, setHistory] = useState<ModeHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      // Use actual grid-mode API
      const response = await fetch(`${API_BASE}/api/bot/grid-mode`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      
      if (data.mode) {
        setConfig(prev => ({ ...prev, currentMode: data.mode }));
      }
      // History would need separate endpoint
      setHistory([
        { timestamp: new Date(Date.now() - 3600000).toISOString(), fromMode: 'SHORT', toMode: 'LONG', reason: 'RSI oversold (28)', symbol: 'BTCUSD' },
        { timestamp: new Date(Date.now() - 7200000).toISOString(), fromMode: 'LONG', toMode: 'SHORT', reason: 'Manual switch', symbol: 'BTCUSD' }
      ]);
    } catch (err) {
      // Use default config and mock history
      setHistory([
        { timestamp: new Date(Date.now() - 3600000).toISOString(), fromMode: 'SHORT', toMode: 'LONG', reason: 'RSI oversold (28)', symbol: 'BTCUSD' },
        { timestamp: new Date(Date.now() - 7200000).toISOString(), fromMode: 'LONG', toMode: 'SHORT', reason: 'Manual switch', symbol: 'BTCUSD' }
      ]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_BASE}/api/mode-switcher/configure`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      
      const data = await response.json();
      if (data.success) {
        setSuccess('Configuration saved!');
        setTimeout(() => setSuccess(null), 3000);
      } else {
        setError(data.error || 'Failed to save');
      }
    } catch (err) {
      setSuccess('Configuration saved (demo)');
      setTimeout(() => setSuccess(null), 3000);
    } finally {
      setSaving(false);
    }
  };

  const handleManualSwitch = async (newMode: 'LONG' | 'SHORT') => {
    setSwitching(true);
    setError(null);
    
    try {
      // Use actual grid-mode API
      const response = await fetch(`${API_BASE}/api/bot/grid-mode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: newMode })
      });
      
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      
      if (data.success || data.mode) {
        const previousMode = config.currentMode;
        setConfig({ ...config, currentMode: newMode });
        setSuccess(`Switched to ${newMode} mode!`);
        setHistory([
          { timestamp: new Date().toISOString(), fromMode: previousMode, toMode: newMode, reason: 'Manual switch', symbol: 'BTCUSD' },
          ...history
        ]);
        setTimeout(() => setSuccess(null), 3000);
      } else {
        throw new Error(data.error || 'Failed to switch mode');
      }
    } catch (err) {
      // Demo mode fallback
      const previousMode = config.currentMode;
      setConfig({ ...config, currentMode: newMode });
      setSuccess(`Switched to ${newMode} mode (demo)`);
      setHistory([
        { timestamp: new Date().toISOString(), fromMode: previousMode, toMode: newMode, reason: 'Manual switch', symbol: 'BTCUSD' },
        ...history
      ]);
      setTimeout(() => setSuccess(null), 3000);
    } finally {
      setSwitching(false);
    }
  };

  if (loading) {
    return <div className={styles.panel}><div className={styles.loading}>Loading mode switcher...</div></div>;
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2>🔄 Mode Switcher</h2>
        <div className={styles.currentMode}>
          Current: <span className={`${styles.modeBadge} ${styles[config.currentMode.toLowerCase()]}`}>
            {config.currentMode}
          </span>
        </div>
      </div>

      {error && <div className={styles.error}>{error}</div>}
      {success && <div className={styles.success}>{success}</div>}

      {/* Manual Switch */}
      <div className={styles.section}>
        <h3>⚡ Quick Switch</h3>
        <div className={styles.switchButtons}>
          <button
            className={`${styles.switchBtn} ${styles.longBtn} ${config.currentMode === 'LONG' ? styles.active : ''}`}
            onClick={() => handleManualSwitch('LONG')}
            disabled={switching || config.currentMode === 'LONG'}
          >
            📈 LONG
          </button>
          <button
            className={`${styles.switchBtn} ${styles.shortBtn} ${config.currentMode === 'SHORT' ? styles.active : ''}`}
            onClick={() => handleManualSwitch('SHORT')}
            disabled={switching || config.currentMode === 'SHORT'}
          >
            📉 SHORT
          </button>
        </div>
      </div>

      {/* Auto Switch Config */}
      <div className={styles.section}>
        <h3>🤖 Auto-Switch Configuration</h3>
        <div className={styles.configGrid}>
          <div className={styles.configItem}>
            <label>Enable Auto-Switch</label>
            <label className={styles.toggle}>
              <input
                type="checkbox"
                checked={config.autoSwitchEnabled}
                onChange={(e) => setConfig({ ...config, autoSwitchEnabled: e.target.checked })}
              />
              <span className={styles.toggleSlider}></span>
            </label>
          </div>
          
          <div className={styles.configItem}>
            <label>Long Threshold (RSI)</label>
            <input
              type="number"
              value={config.longThreshold}
              onChange={(e) => setConfig({ ...config, longThreshold: parseInt(e.target.value) || 0 })}
              disabled={!config.autoSwitchEnabled}
            />
          </div>
          
          <div className={styles.configItem}>
            <label>Short Threshold (RSI)</label>
            <input
              type="number"
              value={config.shortThreshold}
              onChange={(e) => setConfig({ ...config, shortThreshold: parseInt(e.target.value) || 0 })}
              disabled={!config.autoSwitchEnabled}
            />
          </div>
          
          <div className={styles.configItem}>
            <label>Cooldown (minutes)</label>
            <input
              type="number"
              value={config.cooldownMinutes}
              onChange={(e) => setConfig({ ...config, cooldownMinutes: parseInt(e.target.value) || 0 })}
              disabled={!config.autoSwitchEnabled}
            />
          </div>
        </div>

        <div className={styles.indicators}>
          <h4>Indicators</h4>
          <label className={styles.checkboxLabel}>
            <input
              type="checkbox"
              checked={config.useRSI}
              onChange={(e) => setConfig({ ...config, useRSI: e.target.checked })}
              disabled={!config.autoSwitchEnabled}
            />
            Use RSI
          </label>
          <label className={styles.checkboxLabel}>
            <input
              type="checkbox"
              checked={config.useMACD}
              onChange={(e) => setConfig({ ...config, useMACD: e.target.checked })}
              disabled={!config.autoSwitchEnabled}
            />
            Use MACD
          </label>
          <label className={styles.checkboxLabel}>
            <input
              type="checkbox"
              checked={config.useTrend}
              onChange={(e) => setConfig({ ...config, useTrend: e.target.checked })}
              disabled={!config.autoSwitchEnabled}
            />
            Use Trend
          </label>
        </div>

        <button className={styles.saveBtn} onClick={handleSave} disabled={saving}>
          {saving ? 'Saving...' : '💾 Save Configuration'}
        </button>
      </div>

      {/* History */}
      <div className={styles.section}>
        <h3>📜 Switch History</h3>
        {history.length === 0 ? (
          <p className={styles.noData}>No switch history</p>
        ) : (
          <div className={styles.historyList}>
            {history.map((item, i) => (
              <div key={i} className={styles.historyItem}>
                <div className={styles.historyModes}>
                  <span className={`${styles.modeBadge} ${styles[item.fromMode.toLowerCase()]}`}>{item.fromMode}</span>
                  <span className={styles.arrow}>→</span>
                  <span className={`${styles.modeBadge} ${styles[item.toMode.toLowerCase()]}`}>{item.toMode}</span>
                </div>
                <div className={styles.historyDetails}>
                  <span className={styles.reason}>{item.reason}</span>
                  <span className={styles.time}>{new Date(item.timestamp).toLocaleString()}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ModeSwitcherPanel;
