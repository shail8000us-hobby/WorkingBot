/**
 * Instrument Card
 * 
 * A self-contained, independently operable unit for one trading instrument.
 * 
 * Design principles:
 * - Complete isolation from other instruments
 * - All state from its own store
 * - Fails independently without affecting others
 * - Answers key questions in <3 seconds:
 *   1. What is this? (identity)
 *   2. Is it working? (health)
 *   3. Am I making money? (PnL)
 *   4. What's the exposure? (positions)
 *   5. Can I control it? (actions)
 */

import React, { useCallback, useMemo } from 'react';
import { useInstrumentStore, getInstrumentStore } from '../../stores/instrumentStore';
import { useGlobalStore } from '../../stores/globalStore';
import { AuthorityPanel } from '../AuthorityPanel';
import type { InstanceId, TradingState, ConnectionState, Position } from '../../types';
import styles from './InstrumentCard.module.css';

// ============================================================================
// PROPS
// ============================================================================

interface InstrumentCardProps {
  instanceId: InstanceId;
}

// ============================================================================
// SUB-COMPONENTS
// ============================================================================

const ConnectionBadge: React.FC<{ state: ConnectionState }> = ({ state }) => {
  const config = {
    connected: { icon: '●', label: 'Connected', color: 'success' },
    connecting: { icon: '◐', label: 'Connecting...', color: 'warning' },
    disconnected: { icon: '○', label: 'Disconnected', color: 'muted' },
    reconnecting: { icon: '◐', label: 'Reconnecting...', color: 'warning' },
    failed: { icon: '✕', label: 'Connection Failed', color: 'danger' },
  };
  
  const { icon, label, color } = config[state];
  
  return (
    <div className={styles.connectionBadge} data-color={color}>
      <span className={styles.connectionIcon}>{icon}</span>
      <span>{label}</span>
    </div>
  );
};

const _TradingStateBadge: React.FC<{ state: TradingState }> = ({ state }) => {
  const config = {
    active: { icon: '▶', label: 'Active', color: 'success' },
    paused: { icon: '⏸', label: 'Paused', color: 'warning' },
    halted: { icon: '⏹', label: 'HALTED', color: 'danger' },
    error: { icon: '⚠', label: 'Error', color: 'danger' },
    initializing: { icon: '◐', label: 'Starting...', color: 'muted' },
  };
  
  const { icon, label, color } = config[state];
  
  return (
    <div className={styles.tradingBadge} data-color={color}>
      <span>{icon}</span>
      <span>{label}</span>
    </div>
  );
};

const PositionSummary: React.FC<{ positions: Position[] }> = ({ positions }) => {
  if (positions.length === 0) {
    return (
      <div className={styles.positionSummary} data-state="empty">
        <span className={styles.positionLabel}>Position</span>
        <span className={styles.positionValue}>No Position</span>
      </div>
    );
  }
  
  const totalSize = positions.reduce((sum, p) => sum + p.size, 0);
  const avgEntry = positions.reduce((sum, p) => sum + p.entryPrice * p.size, 0) / totalSize;
  const side = positions[0]?.side || 'LONG';
  
  return (
    <div className={styles.positionSummary} data-state={side.toLowerCase()}>
      <span className={styles.positionLabel}>Position</span>
      <span className={styles.positionValue}>
        {totalSize.toFixed(4)} {side}
      </span>
      <span className={styles.positionEntry}>
        Entry: ${avgEntry.toLocaleString(undefined, { maximumFractionDigits: 2 })}
      </span>
    </div>
  );
};

const PnLDisplay: React.FC<{ realized: number; unrealized: number; todayTotal: number }> = ({
  realized: _realized,
  unrealized,
  todayTotal,
}) => {
  const formatPnL = (value: number) => {
    const formatted = Math.abs(value).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return value >= 0 ? `+$${formatted}` : `-$${formatted}`;
  };
  
  return (
    <div className={styles.pnlDisplay}>
      <div className={styles.pnlRow}>
        <span className={styles.pnlLabel}>Today</span>
        <span className={styles.pnlValue} data-positive={todayTotal >= 0}>
          {formatPnL(todayTotal)}
        </span>
      </div>
      <div className={styles.pnlRow}>
        <span className={styles.pnlLabel}>Unrealized</span>
        <span className={styles.pnlValue} data-positive={unrealized >= 0}>
          {formatPnL(unrealized)}
        </span>
      </div>
    </div>
  );
};

const GridStatus: React.FC<{ filled: number; total: number; lower: number; upper: number }> = ({
  filled,
  total,
  lower,
  upper,
}) => {
  const percent = total > 0 ? (filled / total) * 100 : 0;
  
  return (
    <div className={styles.gridStatus}>
      <div className={styles.gridHeader}>
        <span className={styles.gridLabel}>Grid</span>
        <span className={styles.gridRange}>
          ${lower.toLocaleString()} - ${upper.toLocaleString()}
        </span>
      </div>
      <div className={styles.gridProgress}>
        <div className={styles.gridBar}>
          <div className={styles.gridFilled} style={{ width: `${percent}%` }} />
        </div>
        <span className={styles.gridCount}>
          {filled}/{total} ({percent.toFixed(0)}%)
        </span>
      </div>
    </div>
  );
};

const ActionButtons: React.FC<{
  instanceId: InstanceId;
  tradingState: TradingState;
  onFocus: () => void;
}> = ({ instanceId, tradingState, onFocus }) => {
  const store = getInstrumentStore(instanceId);
  
  const handlePause = useCallback(async () => {
    if (window.confirm('Pause trading for this instrument?')) {
      await store.getState().pauseTrading();
    }
  }, [store]);
  
  const handleResume = useCallback(async () => {
    if (window.confirm('Resume trading for this instrument?')) {
      await store.getState().resumeTrading();
    }
  }, [store]);
  
  const handleKill = useCallback(async () => {
    if (window.confirm('⚠️ EMERGENCY STOP this instrument? This will halt all trading.')) {
      await store.getState().killTrading();
    }
  }, [store]);
  
  const isPaused = tradingState === 'paused';
  const isHalted = tradingState === 'halted';
  const isActive = tradingState === 'active';
  
  return (
    <div className={styles.actions}>
      <button className={styles.focusButton} onClick={onFocus}>
        Focus
      </button>
      
      {isActive && (
        <button className={styles.pauseButton} onClick={handlePause}>
          ⏸ Pause
        </button>
      )}
      
      {isPaused && (
        <button className={styles.resumeButton} onClick={handleResume}>
          ▶ Resume
        </button>
      )}
      
      {!isHalted && (
        <button className={styles.killButton} onClick={handleKill}>
          ⏹ Stop
        </button>
      )}
    </div>
  );
};

// ============================================================================
// MAIN COMPONENT
// ============================================================================

/**
 * InstrumentCard - The primary unit of multi-instrument awareness
 * 
 * KEY DESIGN PRINCIPLE: Authority transparency
 * ------------------------------------
 * The trader must ALWAYS know:
 * 1. WHO is in control (Heartbeat? Guardian? Trading? User?)
 * 2. WHY they are in control (error, risk limit, strategy decision, manual)
 * 3. WHAT action to take (different for each authority)
 * 
 * This is achieved through the AuthorityPanel which shows all three
 * decision-makers and highlights the controlling one.
 */
export const InstrumentCard: React.FC<InstrumentCardProps> = ({ instanceId }) => {
  // All state from isolated store
  const identity = useInstrumentStore(instanceId, (s) => s.identity);
  const health = useInstrumentStore(instanceId, (s) => s.health);
  const tradingState = useInstrumentStore(instanceId, (s) => s.tradingState);
  const positions = useInstrumentStore(instanceId, (s) => s.positions);
  const pnl = useInstrumentStore(instanceId, (s) => s.pnl);
  const grid = useInstrumentStore(instanceId, (s) => s.grid);
  
  // NEW: Authority state - the three decision-makers
  const authority = useInstrumentStore(instanceId, (s) => s.authority);
  const controlledBy = useInstrumentStore(instanceId, (s) => s.controlledBy);
  
  // Global action
  const focusInstance = useGlobalStore((s) => s.focusInstance);
  
  const handleFocus = useCallback(() => {
    focusInstance(instanceId);
  }, [focusInstance, instanceId]);
  
  // Determine card severity based on AUTHORITY, not just state
  // This is the key insight: severity depends on WHO is blocking
  const severity = useMemo((): 'critical' | 'warning' | 'paused' | 'normal' => {
    // Connection failure is always critical - nothing works
    if (health.connection === 'failed') return 'critical';
    
    // Severity based on controlling authority
    switch (controlledBy) {
      case 'heartbeat':
        // System is dead - CRITICAL
        return 'critical';
      case 'guardian':
        // Risk protection active - WARNING (not critical, it's protective)
        return 'warning';
      case 'user':
        // Manual pause - PAUSED (intentional, low urgency)
        return 'paused';
      case 'trading':
        // Strategy in control - check for errors
        if (tradingState === 'error' || tradingState === 'halted') return 'warning';
        return 'normal';
      default:
        return 'normal';
    }
  }, [health.connection, controlledBy, tradingState]);
  
  return (
    <article className={styles.card} data-severity={severity}>
      {/* Header: Identity */}
      <header className={styles.header}>
        <div className={styles.identity}>
          <h2 className={styles.symbol}>{identity.symbol}</h2>
          <span className={styles.mode} data-mode={identity.mode}>
            {identity.mode}
          </span>
        </div>
        <ConnectionBadge state={health.connection} />
      </header>
      
      {/* AUTHORITY PANEL - The key insight from v2.1 */}
      {/* Shows WHO is in control and WHY, not just "what state" */}
      <AuthorityPanel authority={authority} controlledBy={controlledBy} />
      
      {/* Legacy error display - for additional context */}
      {health.lastError && (
        <div className={styles.errorMessage}>
          ⚠️ {health.lastError}
        </div>
      )}
      
      {/* Core Metrics */}
      <div className={styles.metrics}>
        <PositionSummary positions={positions} />
        <PnLDisplay
          realized={pnl.realized}
          unrealized={pnl.unrealized}
          todayTotal={pnl.todayTotal}
        />
      </div>
      
      {/* Grid Status */}
      {grid && (
        <GridStatus
          filled={grid.filledLevels}
          total={grid.gridLevels}
          lower={grid.lowerPrice}
          upper={grid.upperPrice}
        />
      )}
      
      {/* Actions - now context-aware based on controlling authority */}
      <footer className={styles.footer}>
        <ActionButtons
          instanceId={instanceId}
          tradingState={tradingState}
          onFocus={handleFocus}
        />
      </footer>
    </article>
  );
};

export default InstrumentCard;
