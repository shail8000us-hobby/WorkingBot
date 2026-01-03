/**
 * Logs Panel
 * 
 * Live log streaming with filtering and search.
 * Fetches logs from backend API.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import styles from './LogsPanel.module.css';

interface LogEntry {
  id: string;
  timestamp: string;
  level: 'debug' | 'info' | 'warning' | 'error';
  message: string;
  source?: string;
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5555';

export const LogsPanel: React.FC = () => {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [filter, setFilter] = useState<string>('all');
  const [search, setSearch] = useState<string>('');
  const [autoScroll, setAutoScroll] = useState(true);
  const [loading, setLoading] = useState(false);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const fetchLogs = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE}/api/logs?lines=200`);
      if (response.ok) {
        const data = await response.json();
        // Transform raw logs to structured format
        const structured: LogEntry[] = (data.logs || []).map((line: string, index: number) => {
          const levelMatch = line.match(/\[(DEBUG|INFO|WARNING|ERROR)\]/i);
          const level = levelMatch ? levelMatch[1].toLowerCase() as LogEntry['level'] : 'info';
          const timestampMatch = line.match(/\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}/);
          
          return {
            id: `log-${index}-${Date.now()}`,
            timestamp: timestampMatch ? timestampMatch[0] : new Date().toISOString(),
            level,
            message: line,
            source: 'bot'
          };
        });
        setLogs(structured);
      }
    } catch (error) {
      console.error('Failed to fetch logs:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 3000); // Refresh every 3s
    return () => clearInterval(interval);
  }, [fetchLogs]);

  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const filteredLogs = logs.filter((log) => {
    if (filter !== 'all' && log.level !== filter) return false;
    if (search && !log.message.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'error': return 'var(--color-danger)';
      case 'warning': return 'var(--color-warning)';
      case 'info': return 'var(--color-primary)';
      case 'debug': return 'var(--color-text-muted)';
      default: return 'var(--color-text)';
    }
  };

  return (
    <div className={styles.panel}>
      <header className={styles.header}>
        <h2 className={styles.title}>📝 Live Logs</h2>
        <div className={styles.controls}>
          <input
            type="text"
            placeholder="Search logs..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className={styles.searchInput}
          />
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className={styles.filterSelect}
          >
            <option value="all">All Levels</option>
            <option value="error">Errors</option>
            <option value="warning">Warnings</option>
            <option value="info">Info</option>
            <option value="debug">Debug</option>
          </select>
          <label className={styles.autoScrollLabel}>
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
            />
            Auto-scroll
          </label>
          <button onClick={fetchLogs} className={styles.refreshButton}>
            ↻ Refresh
          </button>
        </div>
      </header>

      <div className={styles.logsContainer}>
        {loading && logs.length === 0 ? (
          <div className={styles.loadingState}>Loading logs...</div>
        ) : filteredLogs.length === 0 ? (
          <div className={styles.emptyState}>
            {search || filter !== 'all' 
              ? 'No logs match your filter' 
              : 'No logs available'}
          </div>
        ) : (
          <div className={styles.logsList}>
            {filteredLogs.map((log) => (
              <div 
                key={log.id} 
                className={styles.logEntry}
                data-level={log.level}
              >
                <span 
                  className={styles.logLevel}
                  style={{ color: getLevelColor(log.level) }}
                >
                  [{log.level.toUpperCase()}]
                </span>
                <span className={styles.logMessage}>{log.message}</span>
              </div>
            ))}
            <div ref={logsEndRef} />
          </div>
        )}
      </div>

      <footer className={styles.footer}>
        <span className={styles.logCount}>
          Showing {filteredLogs.length} of {logs.length} logs
        </span>
        <span className={styles.lastUpdate}>
          Last updated: {new Date().toLocaleTimeString()}
        </span>
      </footer>
    </div>
  );
};

export default LogsPanel;
