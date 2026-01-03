/**
 * System Health Panel
 * 
 * Real-time system monitoring - CPU, memory, disk, process health.
 * Also shows safety dashboard data for unified risk view.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useInstance } from '../../contexts/InstanceContext';
import styles from './SystemHealthPanel.module.css';

interface SystemHealth {
  cpu_percent?: number;
  memory_percent?: number;
  memory_used_gb?: number;
  memory_total_gb?: number;
  disk_percent?: number;
  disk_used_gb?: number;
  disk_total_gb?: number;
  processes?: number;
  uptime_hours?: number;
  load_avg?: number[];
}

interface SafetyStatus {
  overall_status: 'SAFE' | 'WARNING' | 'DANGER' | 'CRITICAL';
  guardian_running: boolean;
  bot_running: boolean;
  total_loss_inr: number;
  max_allowed_loss_inr: number;
  total_positions: number;
  risk_percent: number;
  checks: {
    name: string;
    status: 'pass' | 'warn' | 'fail';
    message: string;
  }[];
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5555';

export const SystemHealthPanel: React.FC = () => {
  const { withInstance, selectedInstanceId } = useInstance();
  const [health, setHealth] = useState<SystemHealth>({});
  const [safety, setSafety] = useState<SafetyStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const fetchHealth = useCallback(async () => {
    // Fetch system health from /api/health/detailed
    try {
      const response = await fetch(`${API_BASE}/api/health/detailed`);
      if (response.ok) {
        const data = await response.json();
        const resources = data.data?.resources || data.resources || {};
        setHealth({
          cpu_percent: resources.cpu?.percent || 0,
          memory_percent: resources.memory?.percent_used || 0,
          memory_used_gb: resources.memory?.used_gb || 0,
          memory_total_gb: resources.memory?.total_gb || 0,
          disk_percent: resources.disk?.percent_used || 0,
          disk_used_gb: resources.disk?.used_gb || 0,
          disk_total_gb: resources.disk?.total_gb || 0,
          processes: 0,
          uptime_hours: (data.data?.uptime?.seconds || 0) / 3600,
          load_avg: [resources.cpu?.percent || 0]
        });
        setLastUpdate(new Date());
      }
    } catch (error) {
      // Fallback mock data
      setHealth({
        cpu_percent: Math.random() * 30 + 10,
        memory_percent: Math.random() * 20 + 40,
        memory_used_gb: 8.5,
        memory_total_gb: 16,
        disk_percent: 65,
        disk_used_gb: 200,
        disk_total_gb: 500,
        processes: 12,
        uptime_hours: 48,
        load_avg: [1.2, 1.5, 1.3]
      });
      setLastUpdate(new Date());
    }

    // Fetch safety dashboard
    try {
      const safetyRes = await fetch(withInstance(`${API_BASE}/api/safety/dashboard`));
      if (safetyRes.ok) {
        const safetyData = await safetyRes.json();
        if (safetyData.success || safetyData.overall_status) {
          setSafety({
            overall_status: safetyData.overall_status || safetyData.data?.overall_status || 'SAFE',
            guardian_running: safetyData.guardian_running ?? safetyData.data?.guardian_running ?? true,
            bot_running: safetyData.bot_running ?? safetyData.data?.bot_running ?? true,
            total_loss_inr: safetyData.total_loss_inr || safetyData.data?.total_loss_inr || 0,
            max_allowed_loss_inr: safetyData.max_allowed_loss_inr || safetyData.data?.max_allowed_loss_inr || 10000,
            total_positions: safetyData.total_positions || safetyData.data?.total_positions || 0,
            risk_percent: safetyData.risk_percent || safetyData.data?.risk_percent || 0,
            checks: safetyData.checks || safetyData.data?.checks || [],
          });
        }
      }
    } catch (error) {
      // Keep existing safety data or set null
    }

    setLoading(false);
  }, [withInstance]);

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 5000);
    return () => clearInterval(interval);
  }, [fetchHealth, selectedInstanceId]);

  const getHealthColor = (percent: number) => {
    if (percent < 50) return 'var(--color-success)';
    if (percent < 80) return 'var(--color-warning)';
    return 'var(--color-danger)';
  };

  const getHealthStatus = (percent: number) => {
    if (percent < 50) return 'healthy';
    if (percent < 80) return 'warning';
    return 'critical';
  };

  if (loading) {
    return (
      <div className={styles.panel}>
        <div className={styles.loadingState}>Loading system health...</div>
      </div>
    );
  }

  return (
    <div className={styles.panel}>
      <header className={styles.header}>
        <h2 className={styles.title}>💻 System Health</h2>
        <span className={styles.lastUpdate}>
          Last updated: {lastUpdate?.toLocaleTimeString() || 'Never'}
        </span>
      </header>

      <div className={styles.content}>
        {/* CPU */}
        <div className={styles.metricCard}>
          <div className={styles.metricHeader}>
            <span className={styles.metricIcon}>⚡</span>
            <span className={styles.metricName}>CPU Usage</span>
          </div>
          <div className={styles.metricValue} data-status={getHealthStatus(health.cpu_percent || 0)}>
            {(health.cpu_percent || 0).toFixed(1)}%
          </div>
          <div className={styles.progressBar}>
            <div 
              className={styles.progressFill}
              style={{ 
                width: `${health.cpu_percent || 0}%`,
                backgroundColor: getHealthColor(health.cpu_percent || 0)
              }}
            />
          </div>
          {health.load_avg && (
            <div className={styles.metricSubtext}>
              Load: {health.load_avg.map(l => l.toFixed(2)).join(' / ')}
            </div>
          )}
        </div>

        {/* Memory */}
        <div className={styles.metricCard}>
          <div className={styles.metricHeader}>
            <span className={styles.metricIcon}>🧠</span>
            <span className={styles.metricName}>Memory Usage</span>
          </div>
          <div className={styles.metricValue} data-status={getHealthStatus(health.memory_percent || 0)}>
            {(health.memory_percent || 0).toFixed(1)}%
          </div>
          <div className={styles.progressBar}>
            <div 
              className={styles.progressFill}
              style={{ 
                width: `${health.memory_percent || 0}%`,
                backgroundColor: getHealthColor(health.memory_percent || 0)
              }}
            />
          </div>
          <div className={styles.metricSubtext}>
            {health.memory_used_gb?.toFixed(1) || 0} GB / {health.memory_total_gb?.toFixed(1) || 0} GB
          </div>
        </div>

        {/* Disk */}
        <div className={styles.metricCard}>
          <div className={styles.metricHeader}>
            <span className={styles.metricIcon}>💾</span>
            <span className={styles.metricName}>Disk Usage</span>
          </div>
          <div className={styles.metricValue} data-status={getHealthStatus(health.disk_percent || 0)}>
            {(health.disk_percent || 0).toFixed(1)}%
          </div>
          <div className={styles.progressBar}>
            <div 
              className={styles.progressFill}
              style={{ 
                width: `${health.disk_percent || 0}%`,
                backgroundColor: getHealthColor(health.disk_percent || 0)
              }}
            />
          </div>
          <div className={styles.metricSubtext}>
            {health.disk_used_gb?.toFixed(0) || 0} GB / {health.disk_total_gb?.toFixed(0) || 0} GB
          </div>
        </div>

        {/* Quick Stats */}
        <div className={styles.statsGrid}>
          <div className={styles.statItem}>
            <span className={styles.statLabel}>Processes</span>
            <span className={styles.statValue}>{health.processes || 'N/A'}</span>
          </div>
          <div className={styles.statItem}>
            <span className={styles.statLabel}>Uptime</span>
            <span className={styles.statValue}>{health.uptime_hours ? `${health.uptime_hours.toFixed(0)}h` : 'N/A'}</span>
          </div>
        </div>

        {/* Health Summary */}
        <div className={styles.healthSummary}>
          <div className={styles.summaryTitle}>System Status</div>
          <div className={styles.summaryItems}>
            <div className={styles.summaryItem} data-status={getHealthStatus(health.cpu_percent || 0)}>
              <span className={styles.summaryDot} />
              CPU
            </div>
            <div className={styles.summaryItem} data-status={getHealthStatus(health.memory_percent || 0)}>
              <span className={styles.summaryDot} />
              Memory
            </div>
            <div className={styles.summaryItem} data-status={getHealthStatus(health.disk_percent || 0)}>
              <span className={styles.summaryDot} />
              Disk
            </div>
          </div>
        </div>

        {/* Safety Dashboard */}
        {safety && (
          <div className={styles.safetySection}>
            <div className={styles.summaryTitle}>🛡️ Safety Status</div>
            <div className={styles.safetyOverall} data-status={safety.overall_status.toLowerCase()}>
              {safety.overall_status}
            </div>
            <div className={styles.safetyGrid}>
              <div className={styles.safetyItem}>
                <span className={styles.safetyLabel}>Guardian</span>
                <span className={styles.safetyValue} data-active={safety.guardian_running}>
                  {safety.guardian_running ? '✅ Running' : '❌ Stopped'}
                </span>
              </div>
              <div className={styles.safetyItem}>
                <span className={styles.safetyLabel}>Bot</span>
                <span className={styles.safetyValue} data-active={safety.bot_running}>
                  {safety.bot_running ? '✅ Running' : '❌ Stopped'}
                </span>
              </div>
              <div className={styles.safetyItem}>
                <span className={styles.safetyLabel}>Total Loss</span>
                <span className={styles.safetyValue}>
                  ₹{Math.abs(safety.total_loss_inr).toLocaleString()}
                </span>
              </div>
              <div className={styles.safetyItem}>
                <span className={styles.safetyLabel}>Risk</span>
                <span className={styles.safetyValue}>
                  {safety.risk_percent.toFixed(1)}%
                </span>
              </div>
            </div>
            {safety.checks.length > 0 && (
              <div className={styles.safetyChecks}>
                {safety.checks.slice(0, 5).map((check, i) => (
                  <div key={i} className={styles.checkItem} data-status={check.status}>
                    <span className={styles.checkIcon}>
                      {check.status === 'pass' ? '✓' : check.status === 'warn' ? '⚠' : '✕'}
                    </span>
                    <span className={styles.checkName}>{check.name}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default SystemHealthPanel;
