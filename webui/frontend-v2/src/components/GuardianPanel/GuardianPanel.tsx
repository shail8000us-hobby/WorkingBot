/**
 * GuardianPanel - Bot Health Guardian
 * 
 * Monitors bot health, circuit breakers, and auto-recovery.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useInstance } from '../../contexts/InstanceContext';
import { fetchWithMock, mockGuardianStatus } from '../../utils/mockData';
import styles from './GuardianPanel.module.css';

interface GuardianStatus {
  enabled: boolean;
  status: 'healthy' | 'warning' | 'critical' | 'unknown';
  lastCheck: string;
  uptime: number;
  circuitBreakers: {
    name: string;
    status: 'closed' | 'open' | 'half-open';
    failures: number;
    lastTrip?: string;
  }[];
  checks: {
    name: string;
    status: 'pass' | 'fail' | 'warn';
    message: string;
    lastRun: string;
  }[];
  autoRestart: boolean;
  restartCount: number;
  metrics: {
    totalChecks: number;
    failedChecks: number;
    avgResponseTime: number;
  };
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5555';

export const GuardianPanel: React.FC = () => {
  const { selectedInstanceId, withInstance } = useInstance();
  const [status, setStatus] = useState<GuardianStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await fetchWithMock(
        withInstance(`${API_BASE}/api/guardian/status`),
        mockGuardianStatus
      );
      
      if (data.success || data.running !== undefined) {
        // Map backend format to our expected format
        const riskStatus = data.global?.risk_status || 'SAFE';
        setStatus({
          enabled: data.running ?? true,
          status: riskStatus === 'SAFE' ? 'healthy' : riskStatus === 'WARNING' ? 'warning' : 'critical',
          lastCheck: data.last_check ?? new Date().toISOString(),
          uptime: data.uptime ?? 3600 * 24,
          circuitBreakers: data.circuit_breakers ?? [
            { name: 'API Rate Limit', status: 'closed', failures: 0 },
            { name: 'Order Placement', status: 'closed', failures: 0 },
            { name: 'Position Sync', status: 'closed', failures: 0 }
          ],
          checks: data.checks ?? [
            { name: 'Guardian Running', status: data.running ? 'pass' : 'fail', message: data.running ? 'Active' : 'Stopped', lastRun: new Date().toISOString() },
            { name: 'Risk Status', status: riskStatus === 'SAFE' ? 'pass' : 'warn', message: riskStatus, lastRun: new Date().toISOString() },
            { name: 'Total Positions', status: 'pass', message: `${data.global?.total_positions ?? 0} open`, lastRun: new Date().toISOString() }
          ],
          autoRestart: data.auto_restart ?? true,
          restartCount: data.restart_count ?? 0,
          metrics: data.metrics ?? { totalChecks: 0, failedChecks: 0, avgResponseTime: 0 }
        });
        setError(null);
        return;
      }
      throw new Error('Invalid response format');
    } catch (err) {
      // Generate mock data for demo
      setStatus({
        enabled: true,
        status: 'healthy',
        lastCheck: new Date().toISOString(),
        uptime: 3600 * 24 * 2.5,
        circuitBreakers: [
          { name: 'API Rate Limit', status: 'closed', failures: 0 },
          { name: 'Order Placement', status: 'closed', failures: 2 },
          { name: 'Position Sync', status: 'closed', failures: 0 }
        ],
        checks: [
          { name: 'Bot Process', status: 'pass', message: 'Running normally', lastRun: new Date().toISOString() },
          { name: 'API Connection', status: 'pass', message: 'Connected', lastRun: new Date().toISOString() },
          { name: 'Position Sync', status: 'pass', message: 'In sync', lastRun: new Date().toISOString() },
          { name: 'Order Queue', status: 'pass', message: '0 pending', lastRun: new Date().toISOString() }
        ],
        autoRestart: true,
        restartCount: 0,
        metrics: { totalChecks: 1250, failedChecks: 3, avgResponseTime: 45 }
      });
      setError('Using demo data - backend unavailable');
    } finally {
      setLoading(false);
    }
  }, [withInstance]);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, [fetchStatus, selectedInstanceId]);

  const handleAction = async (action: string) => {
    setActionLoading(action);
    try {
      await fetch(withInstance(`${API_BASE}/api/guardian/${action}`), { method: 'POST' });
      await fetchStatus();
    } catch (err) {
      setError(`Failed to ${action}`);
    } finally {
      setActionLoading(null);
    }
  };

  const formatUptime = (seconds: number): string => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    return `${days}d ${hours}h ${mins}m`;
  };

  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'healthy':
      case 'pass':
      case 'closed':
        return 'var(--color-success)';
      case 'warning':
      case 'warn':
      case 'half-open':
        return 'var(--color-warning)';
      case 'critical':
      case 'fail':
      case 'open':
        return 'var(--color-danger)';
      default:
        return 'var(--color-text-muted)';
    }
  };

  if (loading) {
    return <div className={styles.panel}><div className={styles.loading}>Loading guardian status...</div></div>;
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2>🛡️ Guardian Dashboard</h2>
        <div className={styles.headerActions}>
          <span className={`${styles.statusBadge} ${styles[status?.status || 'unknown']}`}>
            {status?.status?.toUpperCase() || 'UNKNOWN'}
          </span>
          <button className={styles.refreshBtn} onClick={fetchStatus}>🔄</button>
        </div>
      </div>

      {error && <div className={styles.error}>{error}</div>}

      {/* Status Overview */}
      <div className={styles.overviewGrid}>
        <div className={styles.overviewCard}>
          <span className={styles.overviewLabel}>Uptime</span>
          <span className={styles.overviewValue}>{formatUptime(status?.uptime || 0)}</span>
        </div>
        <div className={styles.overviewCard}>
          <span className={styles.overviewLabel}>Auto Restart</span>
          <span className={styles.overviewValue}>{status?.autoRestart ? '✅ Enabled' : '❌ Disabled'}</span>
        </div>
        <div className={styles.overviewCard}>
          <span className={styles.overviewLabel}>Restarts</span>
          <span className={styles.overviewValue}>{status?.restartCount || 0}</span>
        </div>
        <div className={styles.overviewCard}>
          <span className={styles.overviewLabel}>Avg Response</span>
          <span className={styles.overviewValue}>{status?.metrics.avgResponseTime || 0}ms</span>
        </div>
      </div>

      {/* Circuit Breakers */}
      <div className={styles.section}>
        <h3>⚡ Circuit Breakers</h3>
        <div className={styles.circuitGrid}>
          {status?.circuitBreakers.map((cb, i) => (
            <div key={i} className={styles.circuitCard}>
              <div className={styles.circuitHeader}>
                <span className={styles.circuitName}>{cb.name}</span>
                <span 
                  className={styles.circuitStatus}
                  style={{ color: getStatusColor(cb.status) }}
                >
                  {cb.status.toUpperCase()}
                </span>
              </div>
              <div className={styles.circuitInfo}>
                <span>Failures: {cb.failures}</span>
                {cb.lastTrip && <span>Last trip: {new Date(cb.lastTrip).toLocaleTimeString()}</span>}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Health Checks */}
      <div className={styles.section}>
        <h3>🔍 Health Checks</h3>
        <div className={styles.checksGrid}>
          {status?.checks.map((check, i) => (
            <div key={i} className={`${styles.checkCard} ${styles[check.status]}`}>
              <div className={styles.checkHeader}>
                <span className={styles.checkIcon}>
                  {check.status === 'pass' ? '✅' : check.status === 'warn' ? '⚠️' : '❌'}
                </span>
                <span className={styles.checkName}>{check.name}</span>
              </div>
              <p className={styles.checkMessage}>{check.message}</p>
              <span className={styles.checkTime}>{new Date(check.lastRun).toLocaleTimeString()}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Actions */}
      <div className={styles.actions}>
        <button
          className={styles.actionBtn}
          onClick={() => handleAction('reset-breakers')}
          disabled={actionLoading === 'reset-breakers'}
        >
          {actionLoading === 'reset-breakers' ? '...' : '🔄 Reset Breakers'}
        </button>
        <button
          className={styles.actionBtn}
          onClick={() => handleAction('force-check')}
          disabled={actionLoading === 'force-check'}
        >
          {actionLoading === 'force-check' ? '...' : '🔍 Force Check'}
        </button>
        <button
          className={`${styles.actionBtn} ${styles.toggleBtn}`}
          onClick={() => handleAction(status?.autoRestart ? 'disable-restart' : 'enable-restart')}
        >
          {status?.autoRestart ? '⏸️ Disable Auto-Restart' : '▶️ Enable Auto-Restart'}
        </button>
      </div>
    </div>
  );
};

export default GuardianPanel;
