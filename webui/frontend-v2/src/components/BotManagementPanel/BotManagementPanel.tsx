/**
 * Bot Management Panel
 * 
 * Controls for starting, stopping, and managing the bot process.
 * Includes PM2 status, emergency controls, and process information.
 */

import React, { useState, useEffect, useCallback } from 'react';
import styles from './BotManagementPanel.module.css';

interface BotStatus {
  running: boolean;
  pm2_status: string;
  pid: number;
  uptime?: number;
  memory?: number;
  cpu?: number;
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5555';

export const BotManagementPanel: React.FC = () => {
  const [botStatus, setBotStatus] = useState<BotStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE}/api/bot/status`);
      if (response.ok) {
        const data = await response.json();
        setBotStatus(data);
      }
    } catch (error) {
      console.error('Failed to fetch bot status:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const performAction = async (action: 'start' | 'stop' | 'restart') => {
    setActionLoading(action);
    setMessage(null);
    
    try {
      const response = await fetch(`${API_BASE}/api/bot/${action}`, {
        method: 'POST',
      });
      
      if (response.ok) {
        setMessage({ type: 'success', text: `Bot ${action} command sent successfully` });
        // Refresh status after action
        setTimeout(fetchStatus, 2000);
      } else {
        const data = await response.json();
        setMessage({ type: 'error', text: data.error || `Failed to ${action} bot` });
      }
    } catch (error) {
      setMessage({ type: 'error', text: `Network error: ${error}` });
    } finally {
      setActionLoading(null);
    }
  };

  const formatUptime = (seconds?: number) => {
    if (!seconds) return 'N/A';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
  };

  const formatMemory = (bytes?: number) => {
    if (!bytes) return 'N/A';
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  return (
    <div className={styles.panel}>
      <header className={styles.header}>
        <h2 className={styles.title}>🤖 Bot Management</h2>
        <button onClick={fetchStatus} className={styles.refreshButton} disabled={loading}>
          ↻ Refresh
        </button>
      </header>

      <div className={styles.content}>
        {/* Status Card */}
        <div className={styles.statusCard}>
          <div className={styles.statusHeader}>
            <span 
              className={styles.statusIndicator}
              data-running={botStatus?.running}
            />
            <span className={styles.statusText}>
              {botStatus?.running ? 'Bot is Running' : 'Bot is Stopped'}
            </span>
          </div>
          
          <div className={styles.statusDetails}>
            <div className={styles.statusItem}>
              <span className={styles.statusLabel}>PM2 Status</span>
              <span className={styles.statusValue}>{botStatus?.pm2_status || 'unknown'}</span>
            </div>
            <div className={styles.statusItem}>
              <span className={styles.statusLabel}>PID</span>
              <span className={styles.statusValue}>{botStatus?.pid || 'N/A'}</span>
            </div>
            <div className={styles.statusItem}>
              <span className={styles.statusLabel}>Uptime</span>
              <span className={styles.statusValue}>{formatUptime(botStatus?.uptime)}</span>
            </div>
            <div className={styles.statusItem}>
              <span className={styles.statusLabel}>Memory</span>
              <span className={styles.statusValue}>{formatMemory(botStatus?.memory)}</span>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className={styles.actions}>
          <button
            className={styles.startButton}
            onClick={() => performAction('start')}
            disabled={!!actionLoading || botStatus?.running}
          >
            {actionLoading === 'start' ? '⏳ Starting...' : '▶ Start Bot'}
          </button>
          
          <button
            className={styles.stopButton}
            onClick={() => performAction('stop')}
            disabled={!!actionLoading || !botStatus?.running}
          >
            {actionLoading === 'stop' ? '⏳ Stopping...' : '⏹ Stop Bot'}
          </button>
          
          <button
            className={styles.restartButton}
            onClick={() => performAction('restart')}
            disabled={!!actionLoading}
          >
            {actionLoading === 'restart' ? '⏳ Restarting...' : '🔄 Restart Bot'}
          </button>
        </div>

        {/* Message */}
        {message && (
          <div className={styles.message} data-type={message.type}>
            {message.text}
          </div>
        )}

        {/* Emergency Section */}
        <div className={styles.emergencySection}>
          <h3 className={styles.sectionTitle}>⚠️ Emergency Controls</h3>
          <p className={styles.emergencyWarning}>
            These actions are immediate and cannot be undone.
          </p>
          <button
            className={styles.emergencyButton}
            onClick={() => {
              if (window.confirm('Are you sure you want to EMERGENCY STOP the bot? This will immediately halt all trading.')) {
                performAction('stop');
              }
            }}
            disabled={!!actionLoading}
          >
            🛑 EMERGENCY STOP
          </button>
        </div>

        {/* Quick Links */}
        <div className={styles.quickLinks}>
          <h3 className={styles.sectionTitle}>Quick Actions</h3>
          <div className={styles.linksGrid}>
            <a href={`${API_BASE}/api/logs`} target="_blank" rel="noopener noreferrer" className={styles.quickLink}>
              📝 View Raw Logs
            </a>
            <a href={`${API_BASE}/api/config`} target="_blank" rel="noopener noreferrer" className={styles.quickLink}>
              ⚙️ View Config
            </a>
            <a href={`${API_BASE}/api/health`} target="_blank" rel="noopener noreferrer" className={styles.quickLink}>
              💚 Health Check
            </a>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BotManagementPanel;
