/**
 * Circuit Breaker Status Panel
 * 
 * Displays real-time status of all circuit breakers
 * Useful for debugging API resilience
 */

import React, { useEffect, useState } from 'react';
import { circuitBreakerManager } from '../../utils/circuitBreaker';
import styles from './CircuitBreakerStatus.module.css';

interface CircuitStats {
  totalRequests: number;
  successCount: number;
  failureCount: number;
  consecutiveFailures: number;
  consecutiveSuccesses: number;
  lastFailureTime: number | null;
  lastSuccessTime: number | null;
  state: 'CLOSED' | 'OPEN' | 'HALF_OPEN';
}

export const CircuitBreakerStatus: React.FC = () => {
  const [stats, setStats] = useState<Record<string, CircuitStats>>({});
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    const updateStats = () => {
      setStats(circuitBreakerManager.getAllStats());
    };

    // Initial load
    updateStats();

    // Update every 2 seconds
    const interval = setInterval(updateStats, 2000);

    return () => clearInterval(interval);
  }, []);

  const services = Object.keys(stats);

  if (services.length === 0) {
    return null; // No circuit breakers initialized yet
  }

  const getStateColor = (state: string): string => {
    switch (state) {
      case 'CLOSED': return 'var(--success-color)';
      case 'OPEN': return 'var(--error-color)';
      case 'HALF_OPEN': return 'var(--warning-color)';
      default: return 'var(--text-secondary)';
    }
  };

  const getStateIcon = (state: string): string => {
    switch (state) {
      case 'CLOSED': return '✓';
      case 'OPEN': return '✕';
      case 'HALF_OPEN': return '⚠';
      default: return '?';
    }
  };

  const formatTime = (timestamp: number | null): string => {
    if (!timestamp) return 'Never';
    const seconds = Math.floor((Date.now() - timestamp) / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ago`;
  };

  const getSuccessRate = (stat: CircuitStats): number => {
    if (stat.totalRequests === 0) return 100;
    return Math.round((stat.successCount / stat.totalRequests) * 100);
  };

  return (
    <div className={styles.container}>
      <div 
        className={styles.header} 
        onClick={() => setExpanded(!expanded)}
      >
        <span className={styles.title}>
          🛡️ Circuit Breakers
        </span>
        <span className={styles.summary}>
          {services.length} services
        </span>
        <span className={styles.toggle}>
          {expanded ? '▼' : '▶'}
        </span>
      </div>

      {expanded && (
        <div className={styles.content}>
          {services.map(serviceName => {
            const stat = stats[serviceName];
            const successRate = getSuccessRate(stat);

            return (
              <div key={serviceName} className={styles.service}>
                <div className={styles.serviceHeader}>
                  <span 
                    className={styles.state}
                    style={{ color: getStateColor(stat.state) }}
                  >
                    {getStateIcon(stat.state)} {stat.state}
                  </span>
                  <span className={styles.serviceName}>{serviceName}</span>
                </div>

                <div className={styles.metrics}>
                  <div className={styles.metric}>
                    <span className={styles.metricLabel}>Success Rate</span>
                    <span 
                      className={styles.metricValue}
                      style={{ 
                        color: successRate >= 90 ? 'var(--success-color)' : 
                               successRate >= 70 ? 'var(--warning-color)' : 
                               'var(--error-color)' 
                      }}
                    >
                      {successRate}%
                    </span>
                  </div>

                  <div className={styles.metric}>
                    <span className={styles.metricLabel}>Requests</span>
                    <span className={styles.metricValue}>{stat.totalRequests}</span>
                  </div>

                  <div className={styles.metric}>
                    <span className={styles.metricLabel}>Failures</span>
                    <span className={styles.metricValue} style={{ color: 'var(--error-color)' }}>
                      {stat.failureCount}
                    </span>
                  </div>

                  <div className={styles.metric}>
                    <span className={styles.metricLabel}>Consecutive</span>
                    <span className={styles.metricValue}>
                      {stat.consecutiveFailures > 0 
                        ? `${stat.consecutiveFailures} ✕` 
                        : `${stat.consecutiveSuccesses} ✓`}
                    </span>
                  </div>
                </div>

                <div className={styles.timeline}>
                  <div className={styles.timelineItem}>
                    <span>Last Success:</span>
                    <span>{formatTime(stat.lastSuccessTime)}</span>
                  </div>
                  <div className={styles.timelineItem}>
                    <span>Last Failure:</span>
                    <span>{formatTime(stat.lastFailureTime)}</span>
                  </div>
                </div>

                {stat.state === 'OPEN' && (
                  <div className={styles.warning}>
                    ⚠️ Circuit is open - blocking requests to prevent cascading failures
                  </div>
                )}

                {stat.state === 'HALF_OPEN' && (
                  <div className={styles.info}>
                    🔄 Testing recovery - monitoring next requests
                  </div>
                )}
              </div>
            );
          })}

          <div className={styles.actions}>
            <button 
              className={styles.resetButton}
              onClick={() => circuitBreakerManager.resetAll()}
            >
              Reset All Breakers
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
