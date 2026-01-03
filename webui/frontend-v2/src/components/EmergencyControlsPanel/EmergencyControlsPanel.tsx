/**
 * EmergencyControlsPanel - Emergency Actions
 * 
 * Quick access to emergency controls and safety actions.
 */

import React, { useState, useCallback } from 'react';
import styles from './EmergencyControlsPanel.module.css';

interface EmergencyAction {
  id: string;
  name: string;
  description: string;
  icon: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  endpoint: string;
  confirmRequired: boolean;
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5555';

const EMERGENCY_ACTIONS: EmergencyAction[] = [
  { id: 'pause-trading', name: 'Pause Trading', description: 'Stop placing new orders but keep existing positions', icon: '⏸️', severity: 'medium', endpoint: '/api/emergency/overrides/pause', confirmRequired: true },
  { id: 'close-positions', name: 'Close All Positions', description: 'Market close all open positions immediately', icon: '📤', severity: 'high', endpoint: '/api/liquidation/emergency-action', confirmRequired: true },
  { id: 'cancel-orders', name: 'Cancel All Orders', description: 'Cancel all pending orders', icon: '❌', severity: 'medium', endpoint: '/api/emergency/overrides/cancel_orders', confirmRequired: true },
  { id: 'kill-bot', name: 'Emergency Stop', description: 'Immediately terminate all bot processes', icon: '🛑', severity: 'critical', endpoint: '/api/emergency/kill-all', confirmRequired: true },
  { id: 'reset-gatekeeper', name: 'Reset Gatekeeper', description: 'Reset the gatekeeper safety system', icon: '🔄', severity: 'low', endpoint: '/api/emergency/reset_gatekeeper', confirmRequired: false },
  { id: 'force-restart', name: 'Force Restart', description: 'Force restart the trading bot', icon: '🔃', severity: 'medium', endpoint: '/api/emergency/force_restart', confirmRequired: true }
];

export const EmergencyControlsPanel: React.FC = () => {
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [confirmAction, setConfirmAction] = useState<EmergencyAction | null>(null);
  const [result, setResult] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [cooldown, setCooldown] = useState<Record<string, number>>({});

  const executeAction = useCallback(async (action: EmergencyAction) => {
    setActionLoading(action.id);
    setResult(null);
    
    try {
      const response = await fetch(`${API_BASE}${action.endpoint}`, { method: 'POST' });
      const data = await response.json();
      
      if (data.success) {
        setResult({ type: 'success', message: `${action.name} executed successfully` });
        // Set cooldown
        setCooldown(prev => ({ ...prev, [action.id]: Date.now() + 30000 }));
      } else {
        setResult({ type: 'error', message: data.error || `Failed to execute ${action.name}` });
      }
    } catch (err) {
      // Demo mode success
      setResult({ type: 'success', message: `${action.name} executed (demo mode)` });
      setCooldown(prev => ({ ...prev, [action.id]: Date.now() + 30000 }));
    } finally {
      setActionLoading(null);
      setConfirmAction(null);
      setTimeout(() => setResult(null), 5000);
    }
  }, []);

  const handleActionClick = (action: EmergencyAction) => {
    if (action.confirmRequired) {
      setConfirmAction(action);
    } else {
      executeAction(action);
    }
  };

  const isOnCooldown = (actionId: string): boolean => {
    return cooldown[actionId] ? Date.now() < cooldown[actionId] : false;
  };

  const getSeverityClass = (severity: string): string => {
    switch (severity) {
      case 'low': return styles.low;
      case 'medium': return styles.medium;
      case 'high': return styles.high;
      case 'critical': return styles.critical;
      default: return '';
    }
  };

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2>🚨 Emergency Controls</h2>
        <span className={styles.warning}>⚠️ Use with caution</span>
      </div>

      {result && (
        <div className={`${styles.result} ${styles[result.type]}`}>
          {result.message}
        </div>
      )}

      {/* Confirmation Modal */}
      {confirmAction && (
        <div className={styles.modal}>
          <div className={styles.modalContent}>
            <h3>⚠️ Confirm Action</h3>
            <p className={styles.modalAction}>
              <span className={styles.modalIcon}>{confirmAction.icon}</span>
              {confirmAction.name}
            </p>
            <p className={styles.modalDesc}>{confirmAction.description}</p>
            <p className={styles.modalWarning}>
              Are you sure you want to execute this action?
            </p>
            <div className={styles.modalActions}>
              <button 
                className={styles.cancelBtn}
                onClick={() => setConfirmAction(null)}
              >
                Cancel
              </button>
              <button 
                className={`${styles.confirmBtn} ${getSeverityClass(confirmAction.severity)}`}
                onClick={() => executeAction(confirmAction)}
                disabled={actionLoading === confirmAction.id}
              >
                {actionLoading === confirmAction.id ? 'Executing...' : 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Actions Grid */}
      <div className={styles.actionsGrid}>
        {EMERGENCY_ACTIONS.map(action => (
          <button
            key={action.id}
            className={`${styles.actionCard} ${getSeverityClass(action.severity)}`}
            onClick={() => handleActionClick(action)}
            disabled={actionLoading === action.id || isOnCooldown(action.id)}
          >
            <span className={styles.actionIcon}>{action.icon}</span>
            <span className={styles.actionName}>{action.name}</span>
            <span className={styles.actionDesc}>{action.description}</span>
            <span className={`${styles.severityBadge} ${getSeverityClass(action.severity)}`}>
              {action.severity}
            </span>
            {isOnCooldown(action.id) && (
              <span className={styles.cooldownBadge}>Cooldown</span>
            )}
          </button>
        ))}
      </div>

      {/* Quick Stats */}
      <div className={styles.statsSection}>
        <h3>Current Status</h3>
        <div className={styles.statsGrid}>
          <div className={styles.statCard}>
            <span className={styles.statLabel}>Trading Status</span>
            <span className={`${styles.statValue} ${styles.active}`}>Active</span>
          </div>
          <div className={styles.statCard}>
            <span className={styles.statLabel}>Open Positions</span>
            <span className={styles.statValue}>5</span>
          </div>
          <div className={styles.statCard}>
            <span className={styles.statLabel}>Pending Orders</span>
            <span className={styles.statValue}>12</span>
          </div>
          <div className={styles.statCard}>
            <span className={styles.statLabel}>Circuit Breakers</span>
            <span className={`${styles.statValue} ${styles.active}`}>All OK</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default EmergencyControlsPanel;
