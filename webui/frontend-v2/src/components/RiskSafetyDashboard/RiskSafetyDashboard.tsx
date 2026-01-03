/**
 * Risk Safety Dashboard Component
 * 
 * Displays 6-layer protection status:
 * 1. Guardian status
 * 2. Volatility monitoring
 * 3. PnL loss limits
 * 4. Position size monitoring
 * 5. Liquidation protection
 * 6. System health
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useInstance } from '../../contexts/InstanceContext';
import styles from './RiskSafetyDashboard.module.css';

interface SafetyLayer {
  name: string;
  status: 'ok' | 'warning' | 'danger' | 'unknown';
  message: string;
  details?: string;
  lastCheck?: string;
}

interface SafetyDashboardData {
  overall_status: 'SAFE' | 'WARNING' | 'DANGER' | 'CRITICAL';
  layers: SafetyLayer[];
  trading_allowed: boolean;
  circuit_breakers: {
    triggered: boolean;
    reason?: string;
    reset_time?: string;
  };
  recommendations: string[];
}

export const RiskSafetyDashboard: React.FC = () => {
  const { selectedInstance, withInstance } = useInstance();
  const [data, setData] = useState<SafetyDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSafetyData = useCallback(async () => {
    if (!selectedInstance) return;
    
    try {
      setLoading(true);
      setError(null);
      
      const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5555';
      
      const [safetyRes, guardianRes, systemRes] = await Promise.allSettled([
        fetch(withInstance(`${API_BASE}/api/safety/dashboard`)),
        fetch(`${API_BASE}/api/guardian/status`),
        fetch(`${API_BASE}/api/health/detailed`),
      ]);
      
      // Parse responses
      const safetyData = safetyRes.status === 'fulfilled' 
        ? await safetyRes.value.json().catch(() => ({})) 
        : {};
      const guardianData = guardianRes.status === 'fulfilled' 
        ? await guardianRes.value.json().catch(() => ({})) 
        : {};
      const systemRaw = systemRes.status === 'fulfilled' 
        ? await systemRes.value.json().catch(() => ({})) 
        : {};
      const systemData = systemRaw.data?.resources || {};
      
      // Build layers from responses
      const layers: SafetyLayer[] = [];
      
      // Layer 1: Guardian Status
      const guardianStatus = guardianData.global?.risk_status || guardianData.risk_status;
      layers.push({
        name: 'Guardian Bot',
        status: guardianData.running === false ? 'danger' :
                guardianStatus === 'SAFE' ? 'ok' :
                guardianStatus === 'WARNING' ? 'warning' :
                guardianStatus === 'DANGER' || guardianStatus === 'CRITICAL' ? 'danger' : 'unknown',
        message: guardianData.running === false ? 'Guardian not running' :
                 `Risk status: ${guardianStatus || 'Unknown'}`,
        details: guardianData.last_check,
      });
      
      // Layer 2: Volatility
      const volStatus = safetyData.volatility || {};
      layers.push({
        name: 'Volatility Monitor',
        status: volStatus.status || (volStatus.regime === 'extreme' ? 'danger' : 
                volStatus.regime === 'high' ? 'warning' : 'ok'),
        message: volStatus.message || `Regime: ${volStatus.regime || 'Normal'}`,
        details: volStatus.iv ? `IV: ${volStatus.iv}%` : undefined,
      });
      
      // Layer 3: PnL Loss Limits
      const pnlStatus = safetyData.pnl_limits || guardianData.global || {};
      const totalLoss = pnlStatus.total_loss_inr || pnlStatus.total_loss || 0;
      const maxLoss = pnlStatus.max_loss_inr || pnlStatus.max_loss || 50000;
      const lossRatio = Math.abs(totalLoss) / maxLoss;
      layers.push({
        name: 'PnL Loss Limits',
        status: lossRatio > 0.9 ? 'danger' : lossRatio > 0.7 ? 'warning' : 'ok',
        message: `Loss: ₹${Math.abs(totalLoss).toLocaleString()} / ₹${maxLoss.toLocaleString()}`,
        details: `${(lossRatio * 100).toFixed(1)}% of limit`,
      });
      
      // Layer 4: Position Size
      const posStatus = safetyData.position_size || {};
      layers.push({
        name: 'Position Size Monitor',
        status: posStatus.status || 'ok',
        message: posStatus.message || `${posStatus.current_positions || 0} open positions`,
        details: posStatus.max_positions ? `Max: ${posStatus.max_positions}` : undefined,
      });
      
      // Layer 5: Liquidation Protection
      const liqStatus = safetyData.liquidation || {};
      layers.push({
        name: 'Liquidation Protection',
        status: liqStatus.at_risk ? 'danger' : 
                liqStatus.warning ? 'warning' : 'ok',
        message: liqStatus.at_risk ? 'Positions at risk!' :
                 liqStatus.message || 'No liquidation risk',
        details: liqStatus.margin_ratio ? `Margin: ${liqStatus.margin_ratio}%` : undefined,
      });
      
      // Layer 6: System Health (from /api/health/detailed resources)
      const cpu = systemData.cpu?.percent || 0;
      const memory = systemData.memory?.percent_used || 0;
      const disk = systemData.disk?.percent_used || 0;
      layers.push({
        name: 'System Health',
        status: cpu > 90 || memory > 90 ? 'danger' :
                cpu > 70 || memory > 70 ? 'warning' : 'ok',
        message: `CPU: ${cpu.toFixed(0)}%, Memory: ${memory.toFixed(0)}%`,
        details: disk ? `Disk: ${disk.toFixed(0)}%` : undefined,
      });
      
      // Calculate overall status
      const dangerCount = layers.filter(l => l.status === 'danger').length;
      const warningCount = layers.filter(l => l.status === 'warning').length;
      
      setData({
        overall_status: dangerCount > 0 ? 'CRITICAL' :
                       warningCount > 1 ? 'DANGER' :
                       warningCount > 0 ? 'WARNING' : 'SAFE',
        layers,
        trading_allowed: safetyData.trading_allowed !== false && dangerCount === 0,
        circuit_breakers: {
          triggered: safetyData.circuit_breaker?.triggered || dangerCount > 0,
          reason: safetyData.circuit_breaker?.reason || (dangerCount > 0 ? 'Safety layers in danger state' : undefined),
        },
        recommendations: safetyData.recommendations || generateRecommendations(layers),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load safety data');
      setData(generateDemoData());
    } finally {
      setLoading(false);
    }
  }, [selectedInstance, withInstance]);

  useEffect(() => {
    fetchSafetyData();
    const interval = setInterval(fetchSafetyData, 10000);
    return () => clearInterval(interval);
  }, [fetchSafetyData]);

  const generateRecommendations = (layers: SafetyLayer[]): string[] => {
    const recs: string[] = [];
    layers.forEach(l => {
      if (l.status === 'danger') {
        if (l.name.includes('Guardian')) recs.push('Start Guardian bot immediately');
        if (l.name.includes('PnL')) recs.push('Consider reducing position sizes');
        if (l.name.includes('Liquidation')) recs.push('Add margin or close risky positions');
        if (l.name.includes('System')) recs.push('Check system resources');
      }
    });
    return recs.length > 0 ? recs : ['All systems operating normally'];
  };

  const generateDemoData = (): SafetyDashboardData => ({
    overall_status: 'SAFE',
    layers: [
      { name: 'Guardian Bot', status: 'ok', message: 'Risk status: SAFE' },
      { name: 'Volatility Monitor', status: 'ok', message: 'Regime: Normal' },
      { name: 'PnL Loss Limits', status: 'ok', message: 'Loss: ₹2,500 / ₹50,000' },
      { name: 'Position Size Monitor', status: 'ok', message: '3 open positions' },
      { name: 'Liquidation Protection', status: 'ok', message: 'No liquidation risk' },
      { name: 'System Health', status: 'ok', message: 'CPU: 25%, Memory: 45%' },
    ],
    trading_allowed: true,
    circuit_breakers: { triggered: false },
    recommendations: ['All systems operating normally'],
  });

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'SAFE':
      case 'ok': return '#22c55e';
      case 'WARNING':
      case 'warning': return '#f59e0b';
      case 'DANGER':
      case 'CRITICAL':
      case 'danger': return '#ef4444';
      default: return '#6b7280';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'ok': return '✅';
      case 'warning': return '⚠️';
      case 'danger': return '🚨';
      default: return '❓';
    }
  };

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2 className={styles.title}>🛡️ Risk Safety Dashboard</h2>
        <div className={styles.headerActions}>
          <span className={styles.instanceBadge}>{selectedInstance?.name || 'All Instances'}</span>
          <button className={styles.refreshBtn} onClick={fetchSafetyData}>🔄</button>
        </div>
      </div>

      {error && <div className={styles.error}>{error}</div>}

      <div className={styles.content}>
        {loading ? (
          <div className={styles.loading}>Loading safety status...</div>
        ) : data && (
          <>
            {/* Overall Status */}
            <div className={styles.overallSection}>
              <div 
                className={styles.overallBadge}
                style={{ backgroundColor: getStatusColor(data.overall_status) }}
              >
                {data.overall_status}
              </div>
              <div className={styles.overallInfo}>
                <span className={styles.tradingStatus}>
                  Trading: {data.trading_allowed ? '✅ Allowed' : '🚫 Blocked'}
                </span>
                {data.circuit_breakers.triggered && (
                  <span className={styles.circuitBreaker}>
                    ⚡ Circuit Breaker: {data.circuit_breakers.reason}
                  </span>
                )}
              </div>
            </div>

            {/* 6 Safety Layers */}
            <div className={styles.layersSection}>
              <h3>Protection Layers</h3>
              <div className={styles.layersGrid}>
                {data.layers.map((layer, index) => (
                  <div 
                    key={index}
                    className={styles.layerCard}
                    style={{ borderLeftColor: getStatusColor(layer.status) }}
                  >
                    <div className={styles.layerHeader}>
                      <span className={styles.layerIcon}>{getStatusIcon(layer.status)}</span>
                      <span className={styles.layerName}>{layer.name}</span>
                    </div>
                    <div className={styles.layerMessage}>{layer.message}</div>
                    {layer.details && (
                      <div className={styles.layerDetails}>{layer.details}</div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Recommendations */}
            {data.recommendations.length > 0 && (
              <div className={styles.recommendationsSection}>
                <h3>💡 Recommendations</h3>
                <ul className={styles.recommendationsList}>
                  {data.recommendations.map((rec, index) => (
                    <li key={index}>{rec}</li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};
