/**
 * InstanceManagerPanel - Multi-Instance Bot Management
 * 
 * Run and manage multiple bot instances with different configurations.
 */

import React, { useState, useEffect, useCallback } from 'react';
import styles from './InstanceManagerPanel.module.css';

interface BotInstance {
  id: string;
  name: string;
  symbol: string;
  mode: 'LONG' | 'SHORT';
  status: 'running' | 'stopped' | 'error' | 'starting';
  uptime?: number;
  pnl?: number;
  positions?: number;
  orders?: number;
  config?: string;
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5555';

const DEMO_INSTANCES: BotInstance[] = [
  { id: 'btc-long', name: 'BTC Long Grid', symbol: 'BTCUSD', mode: 'LONG', status: 'running', uptime: 86400, pnl: 245.50, positions: 3, orders: 8 },
  { id: 'btc-short', name: 'BTC Short Grid', symbol: 'BTCUSD', mode: 'SHORT', status: 'stopped', pnl: -12.30, positions: 0, orders: 0 },
  { id: 'eth-long', name: 'ETH Long Grid', symbol: 'ETHUSD', mode: 'LONG', status: 'running', uptime: 43200, pnl: 89.20, positions: 2, orders: 5 }
];

export const InstanceManagerPanel: React.FC = () => {
  const [instances, setInstances] = useState<BotInstance[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newInstance, setNewInstance] = useState({ name: '', symbol: 'BTCUSD', mode: 'LONG', config: 'default' });

  const fetchInstances = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/instances/list`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      
      // Backend returns { instances: [...] } directly
      if (data.instances && Array.isArray(data.instances)) {
        const mapped = data.instances.map((inst: any) => ({
          id: inst.name || `${inst.symbol}_${inst.mode}`,
          name: inst.name || `${inst.symbol}_${inst.mode}`,
          symbol: inst.symbol,
          mode: inst.mode,
          status: inst.enabled ? 'running' : 'stopped',
          uptime: inst.uptime || 0,
          pnl: inst.pnl || 0,
          positions: inst.position_count || 0,
          orders: inst.order_count || 0,
          config: 'default'
        }));
        if (mapped.length > 0) {
          setInstances(mapped);
          return;
        }
      }
      setInstances(DEMO_INSTANCES);
    } catch (err) {
      setInstances(DEMO_INSTANCES);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchInstances();
    const interval = setInterval(fetchInstances, 10000);
    return () => clearInterval(interval);
  }, [fetchInstances]);

  const handleAction = async (instanceId: string, action: 'start' | 'stop' | 'restart' | 'delete') => {
    setActionLoading(`${instanceId}-${action}`);
    setError(null);
    
    try {
      const response = await fetch(`${API_BASE}/api/instances/${instanceId}/${action}`, { method: 'POST' });
      const data = await response.json();
      
      if (data.success) {
        setSuccess(`Instance ${action}ed successfully!`);
        await fetchInstances();
      } else {
        setError(data.error || `Failed to ${action} instance`);
      }
    } catch (err) {
      // Demo mode updates
      setInstances(prev => prev.map(inst => {
        if (inst.id !== instanceId) return inst;
        switch (action) {
          case 'start': return { ...inst, status: 'running' as const };
          case 'stop': return { ...inst, status: 'stopped' as const };
          case 'restart': return { ...inst, status: 'running' as const };
          default: return inst;
        }
      }).filter(inst => action !== 'delete' || inst.id !== instanceId));
      setSuccess(`Instance ${action}ed (demo)`);
    } finally {
      setActionLoading(null);
      setTimeout(() => setSuccess(null), 3000);
    }
  };

  const handleCreate = async () => {
    if (!newInstance.name.trim()) {
      setError('Instance name is required');
      return;
    }
    
    setActionLoading('create');
    
    try {
      const response = await fetch(`${API_BASE}/api/instances/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newInstance)
      });
      
      const data = await response.json();
      if (data.success) {
        setSuccess('Instance created!');
        setShowCreateForm(false);
        setNewInstance({ name: '', symbol: 'BTCUSD', mode: 'LONG', config: 'default' });
        await fetchInstances();
      }
    } catch (err) {
      // Demo mode
      const instance: BotInstance = {
        id: Date.now().toString(),
        name: newInstance.name,
        symbol: newInstance.symbol,
        mode: newInstance.mode as 'LONG' | 'SHORT',
        status: 'stopped',
        pnl: 0,
        positions: 0,
        orders: 0
      };
      setInstances(prev => [...prev, instance]);
      setSuccess('Instance created (demo)');
      setShowCreateForm(false);
      setNewInstance({ name: '', symbol: 'BTCUSD', mode: 'LONG', config: 'default' });
    } finally {
      setActionLoading(null);
      setTimeout(() => setSuccess(null), 3000);
    }
  };

  const formatUptime = (seconds?: number): string => {
    if (!seconds) return '-';
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${mins}m`;
  };

  const getStatusClass = (status: string): string => {
    switch (status) {
      case 'running': return styles.running;
      case 'stopped': return styles.stopped;
      case 'error': return styles.error;
      case 'starting': return styles.starting;
      default: return '';
    }
  };

  if (loading) {
    return <div className={styles.panel}><div className={styles.loading}>Loading instances...</div></div>;
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2>🖥️ Instance Manager</h2>
        <button className={styles.createBtn} onClick={() => setShowCreateForm(!showCreateForm)}>
          {showCreateForm ? '✕ Cancel' : '+ New Instance'}
        </button>
      </div>

      {error && <div className={styles.errorMsg}>{error}</div>}
      {success && <div className={styles.success}>{success}</div>}

      {/* Create Form */}
      {showCreateForm && (
        <div className={styles.createForm}>
          <h3>Create New Instance</h3>
          <div className={styles.formGrid}>
            <div className={styles.formItem}>
              <label>Name</label>
              <input
                type="text"
                value={newInstance.name}
                onChange={(e) => setNewInstance({ ...newInstance, name: e.target.value })}
                placeholder="e.g., BTC Conservative Grid"
              />
            </div>
            <div className={styles.formItem}>
              <label>Symbol</label>
              <select
                value={newInstance.symbol}
                onChange={(e) => setNewInstance({ ...newInstance, symbol: e.target.value })}
              >
                <option value="BTCUSD">BTCUSD</option>
                <option value="ETHUSD">ETHUSD</option>
                <option value="SOLUSD">SOLUSD</option>
              </select>
            </div>
            <div className={styles.formItem}>
              <label>Mode</label>
              <select
                value={newInstance.mode}
                onChange={(e) => setNewInstance({ ...newInstance, mode: e.target.value })}
              >
                <option value="LONG">LONG</option>
                <option value="SHORT">SHORT</option>
              </select>
            </div>
            <div className={styles.formItem}>
              <label>Config Template</label>
              <select
                value={newInstance.config}
                onChange={(e) => setNewInstance({ ...newInstance, config: e.target.value })}
              >
                <option value="default">Default</option>
                <option value="conservative">Conservative</option>
                <option value="aggressive">Aggressive</option>
              </select>
            </div>
          </div>
          <button 
            className={styles.submitBtn} 
            onClick={handleCreate}
            disabled={actionLoading === 'create'}
          >
            {actionLoading === 'create' ? 'Creating...' : 'Create Instance'}
          </button>
        </div>
      )}

      {/* Instances Grid */}
      <div className={styles.instancesGrid}>
        {instances.length === 0 ? (
          <p className={styles.noData}>No instances configured</p>
        ) : (
          instances.map(instance => (
            <div key={instance.id} className={`${styles.instanceCard} ${getStatusClass(instance.status)}`}>
              <div className={styles.cardHeader}>
                <div className={styles.cardTitle}>
                  <span className={styles.instanceName}>{instance.name}</span>
                  <span className={`${styles.statusBadge} ${getStatusClass(instance.status)}`}>
                    {instance.status}
                  </span>
                </div>
                <div className={styles.cardSymbol}>
                  <span className={styles.symbol}>{instance.symbol}</span>
                  <span className={`${styles.modeBadge} ${instance.mode === 'LONG' ? styles.long : styles.short}`}>
                    {instance.mode}
                  </span>
                </div>
              </div>

              <div className={styles.cardStats}>
                <div className={styles.stat}>
                  <span className={styles.statLabel}>Uptime</span>
                  <span className={styles.statValue}>{formatUptime(instance.uptime)}</span>
                </div>
                <div className={styles.stat}>
                  <span className={styles.statLabel}>P&L</span>
                  <span className={`${styles.statValue} ${instance.pnl && instance.pnl >= 0 ? styles.positive : styles.negative}`}>
                    ${instance.pnl?.toFixed(2) || '0.00'}
                  </span>
                </div>
                <div className={styles.stat}>
                  <span className={styles.statLabel}>Positions</span>
                  <span className={styles.statValue}>{instance.positions || 0}</span>
                </div>
                <div className={styles.stat}>
                  <span className={styles.statLabel}>Orders</span>
                  <span className={styles.statValue}>{instance.orders || 0}</span>
                </div>
              </div>

              <div className={styles.cardActions}>
                {instance.status === 'running' ? (
                  <>
                    <button
                      className={styles.actionBtn}
                      onClick={() => handleAction(instance.id, 'stop')}
                      disabled={actionLoading?.startsWith(instance.id)}
                    >
                      ⏹️ Stop
                    </button>
                    <button
                      className={styles.actionBtn}
                      onClick={() => handleAction(instance.id, 'restart')}
                      disabled={actionLoading?.startsWith(instance.id)}
                    >
                      🔄 Restart
                    </button>
                  </>
                ) : (
                  <button
                    className={`${styles.actionBtn} ${styles.startBtn}`}
                    onClick={() => handleAction(instance.id, 'start')}
                    disabled={actionLoading?.startsWith(instance.id)}
                  >
                    ▶️ Start
                  </button>
                )}
                <button
                  className={`${styles.actionBtn} ${styles.deleteBtn}`}
                  onClick={() => handleAction(instance.id, 'delete')}
                  disabled={actionLoading?.startsWith(instance.id)}
                >
                  🗑️
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default InstanceManagerPanel;
