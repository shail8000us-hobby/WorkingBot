/**
 * Global Control Plane
 * 
 * This component NEVER scrolls away. It provides:
 * - System health at a glance
 * - Trading mode indicator
 * - Data freshness
 * - Alert summary
 * - Emergency kill switch
 * 
 * Design principle: Answer "is anything broken?" in 0.5 seconds.
 */

import React, { useCallback, useState } from 'react';
import { useGlobalStore, selectSystemStatus, selectUnacknowledgedAlertCount } from '../../stores/globalStore';
import { InstanceSelector } from '../InstanceSelector/InstanceSelector';
import styles from './GlobalControlPlane.module.css';

// ============================================================================
// SUB-COMPONENTS
// ============================================================================

const SystemHealthBeacon: React.FC = () => {
  const systemHealth = useGlobalStore((s) => s.systemHealth);
  const status = useGlobalStore(selectSystemStatus);
  
  const statusColors = {
    healthy: 'var(--color-success)',
    degraded: 'var(--color-warning)',
    critical: 'var(--color-danger)',
  };
  
  const statusLabels = {
    healthy: 'All Systems Operational',
    degraded: 'Partial Degradation',
    critical: 'System Critical',
  };
  
  return (
    <div className={styles.healthBeacon} data-status={status}>
      <div 
        className={styles.beaconDot} 
        style={{ backgroundColor: statusColors[status] }}
      />
      <div className={styles.beaconInfo}>
        <span className={styles.beaconLabel}>{statusLabels[status]}</span>
        <div className={styles.beaconDetails}>
          <span data-status={systemHealth.backend}>Backend</span>
          <span data-status={systemHealth.database}>DB</span>
          <span data-status={systemHealth.exchange}>Exchange</span>
        </div>
      </div>
    </div>
  );
};

const TradingModeIndicator: React.FC = () => {
  const tradingMode = useGlobalStore((s) => s.tradingMode);
  const _setTradingMode = useGlobalStore((s) => s.setTradingMode);
  
  const modeConfig = {
    LIVE: { color: 'var(--color-danger)', label: '🔴 LIVE', warning: true },
    SIMULATION: { color: 'var(--color-warning)', label: '🟡 SIM', warning: false },
    READ_ONLY: { color: 'var(--color-muted)', label: '⚪ READ', warning: false },
  };
  
  const config = modeConfig[tradingMode];
  
  return (
    <div 
      className={styles.tradingMode} 
      style={{ borderColor: config.color }}
      data-mode={tradingMode}
    >
      <span className={styles.modeLabel}>{config.label}</span>
      {config.warning && (
        <span className={styles.liveWarning}>REAL MONEY</span>
      )}
    </div>
  );
};

const DataFreshnessGauge: React.FC = () => {
  const lastCheck = useGlobalStore((s) => s.systemHealth.lastCheck);
  const [now, setNow] = React.useState(Date.now());
  
  React.useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(interval);
  }, []);
  
  const age = lastCheck ? Math.round((now - lastCheck) / 1000) : null;
  
  let status: 'fresh' | 'aging' | 'stale' = 'fresh';
  if (age === null || age > 5) status = 'stale';
  else if (age > 2) status = 'aging';
  
  return (
    <div className={styles.freshnessGauge} data-status={status}>
      <span className={styles.freshnessIcon}>
        {status === 'fresh' ? '●' : status === 'aging' ? '◐' : '○'}
      </span>
      <span className={styles.freshnessText}>
        {age === null ? 'No data' : `${age}s ago`}
      </span>
    </div>
  );
};

const AlertSummary: React.FC = () => {
  const alertCount = useGlobalStore(selectUnacknowledgedAlertCount);
  const alerts = useGlobalStore((s) => s.alerts);
  
  const hasCritical = alerts.some((a) => !a.acknowledged && a.severity === 'critical');
  const hasWarning = alerts.some((a) => !a.acknowledged && a.severity === 'warning');
  
  if (alertCount === 0) {
    return (
      <div className={styles.alertSummary} data-level="none">
        <span>✓ No Alerts</span>
      </div>
    );
  }
  
  return (
    <div 
      className={styles.alertSummary} 
      data-level={hasCritical ? 'critical' : hasWarning ? 'warning' : 'info'}
    >
      <span className={styles.alertBadge}>{alertCount}</span>
      <span>
        {hasCritical ? '⚠️ Critical' : hasWarning ? '⚠️ Warning' : 'ℹ️ Info'}
      </span>
    </div>
  );
};

const EmergencyKillSwitch: React.FC = () => {
  const killAllTrading = useGlobalStore((s) => s.killAllTrading);
  const tradingMode = useGlobalStore((s) => s.tradingMode);
  
  const [holdProgress, setHoldProgress] = useState(0);
  const [isHolding, setIsHolding] = useState(false);
  
  const HOLD_DURATION = 2000; // 2 seconds
  
  const handleMouseDown = useCallback(() => {
    if (tradingMode === 'READ_ONLY') return;
    
    setIsHolding(true);
    const startTime = Date.now();
    
    const interval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / HOLD_DURATION, 1);
      setHoldProgress(progress);
      
      if (progress >= 1) {
        clearInterval(interval);
        setIsHolding(false);
        setHoldProgress(0);
        killAllTrading();
      }
    }, 50);
    
    const cleanup = () => {
      clearInterval(interval);
      setIsHolding(false);
      setHoldProgress(0);
    };
    
    window.addEventListener('mouseup', cleanup, { once: true });
    window.addEventListener('mouseleave', cleanup, { once: true });
  }, [killAllTrading, tradingMode]);
  
  return (
    <button 
      className={styles.killSwitch}
      onMouseDown={handleMouseDown}
      disabled={tradingMode === 'READ_ONLY'}
      data-holding={isHolding}
    >
      <div 
        className={styles.killProgress}
        style={{ width: `${holdProgress * 100}%` }}
      />
      <span className={styles.killLabel}>
        {isHolding ? 'HOLD TO CONFIRM' : '⚡ EMERGENCY STOP'}
      </span>
    </button>
  );
};

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export const GlobalControlPlane: React.FC = () => {
  return (
    <header className={styles.controlPlane}>
      <div className={styles.leftSection}>
        <SystemHealthBeacon />
        <TradingModeIndicator />
        <InstanceSelector compact />
      </div>
      
      <div className={styles.centerSection}>
        <DataFreshnessGauge />
      </div>
      
      <div className={styles.rightSection}>
        <AlertSummary />
        <EmergencyKillSwitch />
      </div>
    </header>
  );
};

export default GlobalControlPlane;
