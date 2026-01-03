/**
 * Bot Brain Analyzer - Main Component (v2)
 * 
 * Visualizes the bot's decision-making process in real-time.
 * Shows current state, decision flow, and what-if scenarios.
 * 
 * Auto-refreshes every 5 seconds.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useInstance } from '../../contexts/InstanceContext';
import { fetchWithMock, mockBrainFlowchart } from '../../utils/mockData';
import { DecisionFlowGraph } from './DecisionFlowGraph';
import { TradingSimulator } from './TradingSimulator';
import { BotStatePanel } from './BotStatePanel';
import styles from './BotBrainAnalyzer.module.css';

interface BrainData {
  success: boolean;
  nodes: DecisionNode[];
  edges: DecisionEdge[];
  bot_state: BotState;
  error?: string;
}

interface DecisionNode {
  id: string;
  type: 'decision' | 'action' | 'check';
  label: string;
  realtime_data?: Record<string, any>;
}

interface DecisionEdge {
  source: string;
  target: string;
  label?: string;
}

interface BotState {
  emergency_stop: boolean;
  trading_enabled: boolean;
  volatility_safe: boolean;
  open_positions: number;
  pending_orders: number;
  current_price: number;
  next_buy_level: number;
  next_sell_level: number;
  timestamp: string;
}

interface FileChanges {
  files_changed: string[];
  new_files: string[];
}

export const BotBrainAnalyzer: React.FC = () => {
  const { selectedInstance, withInstance } = useInstance();
  const [brainData, setBrainData] = useState<BrainData | null>(null);
  const [changes, setChanges] = useState<FileChanges | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'flow' | 'simulator' | 'state'>('flow');
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  // Get instance name
  const instanceName = selectedInstance?.name || 'No instance';

  const fetchBrainData = useCallback(async () => {
    if (!selectedInstance) {
      setError('No instance selected');
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const [flowData, changesData] = await Promise.allSettled([
        fetchWithMock(withInstance('/api/brain/flowchart'), mockBrainFlowchart),
        fetchWithMock(withInstance('/api/brain/changes'), { success: true, changes: [] })
      ]);

      if (flowData.status === 'fulfilled') {
        const data: any = flowData.value;
        if (data.success) {
          setBrainData(data);
        } else if (data.error) {
          setError(data.error || 'Failed to load brain data');
        }
      } else {
        setError('Brain analyzer API unavailable');
      }

      if (changesData.status === 'fulfilled') {
        const data: any = changesData.value;
        if (data.success && data.changes) {
          setChanges(data.changes);
        }
      }

      setLastRefresh(new Date());
    } catch (err) {
      console.error('Error fetching brain data:', err);
      setError(err instanceof Error ? err.message : 'Failed to connect to brain analyzer');
    } finally {
      setLoading(false);
    }
  }, [selectedInstance, withInstance]);

  // Auto-refresh every 5 seconds
  useEffect(() => {
    fetchBrainData();
    const interval = setInterval(fetchBrainData, 5000);
    return () => clearInterval(interval);
  }, [fetchBrainData]);

  if (loading && !brainData) {
    return (
      <div className={styles.container}>
        <div className={styles.loading}>
          <div className={styles.spinner} />
          <p>Reading Bot Brain...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.container}>
        <div className={styles.error}>
          <h3>❌ Brain Analyzer Unavailable</h3>
          <p>{error}</p>
          <button onClick={fetchBrainData} className={styles.retryButton}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  const hasChanges = changes && (changes.files_changed.length > 0 || changes.new_files.length > 0);
  const totalChanges = hasChanges ? changes.files_changed.length + changes.new_files.length : 0;

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.titleSection}>
          <h1>🧠 Bot Brain Analyzer</h1>
          <p className={styles.subtitle}>
            Real-time analysis of {instanceName}'s decision-making logic
          </p>
        </div>
        
        <div className={styles.headerActions}>
          {hasChanges && (
            <div className={styles.changesWarning}>
              ⚠️ {totalChanges} File(s) Changed - Restart bot to apply
            </div>
          )}
          <div className={styles.refreshInfo}>
            Last refresh: {lastRefresh.toLocaleTimeString()}
          </div>
        </div>
      </div>

      <div className={styles.tabs}>
        <button
          className={`${styles.tab} ${activeTab === 'flow' ? styles.activeTab : ''}`}
          onClick={() => setActiveTab('flow')}
        >
          📊 Decision Flow
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'simulator' ? styles.activeTab : ''}`}
          onClick={() => setActiveTab('simulator')}
        >
          🎮 Trading Simulator
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'state' ? styles.activeTab : ''}`}
          onClick={() => setActiveTab('state')}
        >
          💡 Current State
        </button>
      </div>

      <div className={styles.content}>
        {activeTab === 'flow' && brainData && (
          <DecisionFlowGraph nodes={brainData.nodes} edges={brainData.edges} />
        )}
        {activeTab === 'simulator' && (
          <TradingSimulator instance={instanceName} />
        )}
        {activeTab === 'state' && brainData && (
          <BotStatePanel state={brainData.bot_state} />
        )}
      </div>
    </div>
  );
};
