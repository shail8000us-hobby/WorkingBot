/**
 * Instrument Workspace Grid
 * 
 * Renders all instruments in a responsive grid layout.
 * Automatically reorders by severity (worst first).
 * 
 * Design principle: "Worst news first"
 */

import React, { useMemo } from 'react';
import { useGlobalStore } from '../../stores/globalStore';
import { getInstrumentStore } from '../../stores/instrumentStore';
import { InstrumentCard } from '../InstrumentCard/InstrumentCard';
import type { InstanceId } from '../../types';
import styles from './InstrumentGrid.module.css';

// ============================================================================
// SEVERITY ORDERING
// ============================================================================

const getSeverityScore = (instanceId: InstanceId): number => {
  const store = getInstrumentStore(instanceId);
  const state = store.getState();
  
  // Higher score = more attention needed = appears first
  let score = 0;
  
  // Connection issues
  if (state.health.connection === 'failed') score += 100;
  if (state.health.connection === 'disconnected') score += 50;
  if (state.health.connection === 'reconnecting') score += 30;
  
  // Trading state
  if (state.tradingState === 'halted') score += 80;
  if (state.tradingState === 'error') score += 70;
  if (state.tradingState === 'paused') score += 10;
  
  // Data freshness
  if (state.health.freshness === 'stale') score += 20;
  
  // Risk
  if (state.risk.level === 'critical') score += 90;
  if (state.risk.level === 'high') score += 40;
  
  return score;
};

// ============================================================================
// EMPTY STATE
// ============================================================================

const EmptyState: React.FC = () => (
  <div className={styles.emptyState}>
    <div className={styles.emptyIcon}>📊</div>
    <h3 className={styles.emptyTitle}>No Instruments Configured</h3>
    <p className={styles.emptyText}>
      Add trading instruments to see them here.
      Each instrument will have its own independent control panel.
    </p>
    <button className={styles.addButton}>
      + Add Instrument
    </button>
  </div>
);

// ============================================================================
// LOADING STATE
// ============================================================================

const LoadingState: React.FC = () => (
  <div className={styles.loadingState}>
    <div className={styles.loadingSpinner} />
    <p>Loading instruments...</p>
  </div>
);

// ============================================================================
// MAIN COMPONENT
// ============================================================================

interface InstrumentGridProps {
  isLoading?: boolean;
}

export const InstrumentGrid: React.FC<InstrumentGridProps> = ({ isLoading = false }) => {
  const instances = useGlobalStore((s) => s.instances);
  
  // Sort by severity - worst first
  const sortedInstances = useMemo(() => {
    return [...instances].sort((a, b) => {
      const scoreA = getSeverityScore(a);
      const scoreB = getSeverityScore(b);
      return scoreB - scoreA; // Descending (highest severity first)
    });
  }, [instances]);
  
  if (isLoading) {
    return <LoadingState />;
  }
  
  if (instances.length === 0) {
    return <EmptyState />;
  }
  
  return (
    <section className={styles.grid}>
      <div className={styles.gridHeader}>
        <h2 className={styles.gridTitle}>
          Instruments
          <span className={styles.gridCount}>({instances.length})</span>
        </h2>
        <div className={styles.gridControls}>
          <button className={styles.controlButton}>
            ↻ Refresh All
          </button>
        </div>
      </div>
      
      <div className={styles.gridContainer}>
        {sortedInstances.map((instanceId) => (
          <InstrumentCard key={instanceId} instanceId={instanceId} />
        ))}
      </div>
    </section>
  );
};

export default InstrumentGrid;
