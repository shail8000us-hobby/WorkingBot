/**
 * Focus Mode View
 * 
 * Expanded view of a single instrument with full details.
 * Still shows other instruments in peripheral awareness mode.
 * 
 * Design principle: Deep dive without losing context.
 */

import React, { useCallback } from 'react';
import { useGlobalStore } from '../../stores/globalStore';
import { useInstrumentStore, getInstrumentStore } from '../../stores/instrumentStore';
import { AuthorityDetailPanel } from './AuthorityDetailPanel';
import type { InstanceId } from '../../types';
import styles from './FocusView.module.css';

// ============================================================================
// PERIPHERAL SIDEBAR
// ============================================================================

interface PeripheralInstrumentProps {
  instanceId: InstanceId;
  isFocused: boolean;
  onClick: () => void;
}

const PeripheralInstrument: React.FC<PeripheralInstrumentProps> = ({
  instanceId,
  isFocused,
  onClick,
}) => {
  const identity = useInstrumentStore(instanceId, (s) => s.identity);
  const health = useInstrumentStore(instanceId, (s) => s.health);
  const pnl = useInstrumentStore(instanceId, (s) => s.pnl);
  const tradingState = useInstrumentStore(instanceId, (s) => s.tradingState);
  
  const statusColor = 
    health.connection !== 'connected' ? 'var(--color-danger)' :
    tradingState === 'halted' ? 'var(--color-danger)' :
    tradingState === 'paused' ? 'var(--color-warning)' :
    'var(--color-success)';
  
  const formatPnL = (value: number) => {
    const sign = value >= 0 ? '+' : '-';
    return `${sign}$${Math.abs(value).toFixed(0)}`;
  };
  
  return (
    <button
      className={styles.peripheralItem}
      onClick={onClick}
      data-focused={isFocused}
    >
      <div 
        className={styles.peripheralStatus}
        style={{ backgroundColor: statusColor }}
      />
      <div className={styles.peripheralInfo}>
        <span className={styles.peripheralSymbol}>{identity.symbol}</span>
        <span 
          className={styles.peripheralPnL}
          data-positive={pnl.todayTotal >= 0}
        >
          {formatPnL(pnl.todayTotal)}
        </span>
      </div>
    </button>
  );
};

const PeripheralSidebar: React.FC<{
  instances: InstanceId[];
  focusedInstance: InstanceId;
  onSelect: (id: InstanceId) => void;
}> = ({ instances, focusedInstance, onSelect }) => {
  return (
    <aside className={styles.sidebar}>
      <h3 className={styles.sidebarTitle}>Other Instruments</h3>
      <div className={styles.sidebarList}>
        {instances.map((id) => (
          <PeripheralInstrument
            key={id}
            instanceId={id}
            isFocused={id === focusedInstance}
            onClick={() => onSelect(id)}
          />
        ))}
      </div>
    </aside>
  );
};

// ============================================================================
// DETAIL PANELS
// ============================================================================

const PositionsPanel: React.FC<{ instanceId: InstanceId }> = ({ instanceId }) => {
  const positions = useInstrumentStore(instanceId, (s) => s.positions);
  
  if (positions.length === 0) {
    return (
      <div className={styles.panel}>
        <h4 className={styles.panelTitle}>Positions</h4>
        <p className={styles.emptyMessage}>No open positions</p>
      </div>
    );
  }
  
  return (
    <div className={styles.panel}>
      <h4 className={styles.panelTitle}>Positions</h4>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Side</th>
            <th>Size</th>
            <th>Entry</th>
            <th>Current</th>
            <th>PnL</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((pos) => (
            <tr key={pos.id}>
              <td data-side={pos.side.toLowerCase()}>{pos.side}</td>
              <td>{pos.size.toFixed(4)}</td>
              <td>${pos.entryPrice.toLocaleString()}</td>
              <td>${pos.currentPrice.toLocaleString()}</td>
              <td data-positive={pos.unrealizedPnl >= 0}>
                {pos.unrealizedPnl >= 0 ? '+' : ''}${pos.unrealizedPnl.toFixed(2)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

const OrdersPanel: React.FC<{ instanceId: InstanceId }> = ({ instanceId }) => {
  const orders = useInstrumentStore(instanceId, (s) => s.orders);
  const openOrders = orders.filter((o) => o.status === 'open' || o.status === 'pending');
  
  return (
    <div className={styles.panel}>
      <h4 className={styles.panelTitle}>Open Orders ({openOrders.length})</h4>
      {openOrders.length === 0 ? (
        <p className={styles.emptyMessage}>No open orders</p>
      ) : (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Side</th>
              <th>Price</th>
              <th>Size</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {openOrders.slice(0, 10).map((order) => (
              <tr key={order.id}>
                <td data-side={order.side.toLowerCase()}>{order.side}</td>
                <td>${order.price.toLocaleString()}</td>
                <td>{order.size.toFixed(4)}</td>
                <td>{order.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

const TimelinePanel: React.FC<{ instanceId: InstanceId }> = ({ instanceId }) => {
  const timeline = useInstrumentStore(instanceId, (s) => s.timeline);
  
  const formatTime = (timestamp: number) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };
  
  return (
    <div className={styles.panel}>
      <h4 className={styles.panelTitle}>Recent Activity</h4>
      <div className={styles.timeline}>
        {timeline.length === 0 ? (
          <p className={styles.emptyMessage}>No recent activity</p>
        ) : (
          timeline.slice(0, 20).map((event) => (
            <div key={event.id} className={styles.timelineItem} data-severity={event.severity}>
              <span className={styles.timelineTime}>{formatTime(event.timestamp)}</span>
              <span className={styles.timelineMessage}>{event.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

const RiskPanel: React.FC<{ instanceId: InstanceId }> = ({ instanceId }) => {
  const risk = useInstrumentStore(instanceId, (s) => s.risk);
  
  return (
    <div className={styles.panel}>
      <h4 className={styles.panelTitle}>Risk Metrics</h4>
      <div className={styles.riskGrid}>
        <div className={styles.riskItem}>
          <span className={styles.riskLabel}>Exposure</span>
          <span className={styles.riskValue}>
            ${risk.exposure.toLocaleString()} / ${risk.maxExposure.toLocaleString()}
          </span>
          <div className={styles.riskBar}>
            <div 
              className={styles.riskFill}
              style={{ width: `${risk.exposurePercent}%` }}
              data-level={risk.level}
            />
          </div>
        </div>
        <div className={styles.riskItem}>
          <span className={styles.riskLabel}>Daily Loss</span>
          <span className={styles.riskValue}>
            ${Math.abs(risk.dailyLoss).toFixed(2)} / ${risk.maxDailyLoss.toFixed(2)}
          </span>
        </div>
        <div className={styles.riskItem}>
          <span className={styles.riskLabel}>Risk Level</span>
          <span className={styles.riskLevel} data-level={risk.level}>
            {risk.level.toUpperCase()}
          </span>
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// MAIN FOCUS VIEW
// ============================================================================

export const FocusView: React.FC = () => {
  const instances = useGlobalStore((s) => s.instances);
  const focusedInstance = useGlobalStore((s) => s.focusedInstance);
  const focusInstance = useGlobalStore((s) => s.focusInstance);
  const unfocusInstance = useGlobalStore((s) => s.unfocusInstance);
  
  // If no focused instance, this shouldn't render
  if (!focusedInstance) {
    return null;
  }
  
  const identity = useInstrumentStore(focusedInstance, (s) => s.identity);
  const tradingState = useInstrumentStore(focusedInstance, (s) => s.tradingState);
  const pnl = useInstrumentStore(focusedInstance, (s) => s.pnl);
  
  // NEW: Authority layer state
  const authority = useInstrumentStore(focusedInstance, (s) => s.authority);
  const controlledBy = useInstrumentStore(focusedInstance, (s) => s.controlledBy);
  
  const handleBack = useCallback(() => {
    unfocusInstance();
  }, [unfocusInstance]);
  
  const store = getInstrumentStore(focusedInstance);
  
  const handlePause = useCallback(async () => {
    if (window.confirm('Pause trading for this instrument?')) {
      await store.getState().pauseTrading();
    }
  }, [store]);
  
  const handleResume = useCallback(async () => {
    if (window.confirm('Resume trading?')) {
      await store.getState().resumeTrading();
    }
  }, [store]);
  
  return (
    <div className={styles.focusView}>
      {/* Peripheral sidebar - always visible */}
      <PeripheralSidebar
        instances={instances}
        focusedInstance={focusedInstance}
        onSelect={focusInstance}
      />
      
      {/* Main expanded view */}
      <main className={styles.main}>
        {/* Header */}
        <header className={styles.header}>
          <button className={styles.backButton} onClick={handleBack}>
            ← Back to Grid
          </button>
          <div className={styles.headerInfo}>
            <h1 className={styles.title}>
              {identity.symbol}
              <span className={styles.mode} data-mode={identity.mode}>
                {identity.mode}
              </span>
            </h1>
            <div className={styles.headerMeta}>
              <span className={styles.exchange}>{identity.exchange}</span>
              <span 
                className={styles.tradingState}
                data-state={tradingState}
              >
                {tradingState.toUpperCase()}
              </span>
            </div>
          </div>
          <div className={styles.headerActions}>
            {tradingState === 'active' ? (
              <button className={styles.pauseButton} onClick={handlePause}>
                ⏸ Pause Trading
              </button>
            ) : tradingState === 'paused' ? (
              <button className={styles.resumeButton} onClick={handleResume}>
                ▶ Resume Trading
              </button>
            ) : null}
          </div>
        </header>
        
        {/* Summary bar */}
        <div className={styles.summaryBar}>
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>Today's PnL</span>
            <span 
              className={styles.summaryValue}
              data-positive={pnl.todayTotal >= 0}
            >
              {pnl.todayTotal >= 0 ? '+' : ''}${pnl.todayTotal.toFixed(2)}
            </span>
          </div>
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>Unrealized</span>
            <span 
              className={styles.summaryValue}
              data-positive={pnl.unrealized >= 0}
            >
              {pnl.unrealized >= 0 ? '+' : ''}${pnl.unrealized.toFixed(2)}
            </span>
          </div>
          <div className={styles.summaryItem}>
            <span className={styles.summaryLabel}>Realized</span>
            <span 
              className={styles.summaryValue}
              data-positive={pnl.realized >= 0}
            >
              {pnl.realized >= 0 ? '+' : ''}${pnl.realized.toFixed(2)}
            </span>
          </div>
        </div>
        
        {/* Panels grid - Authority panel first for visibility */}
        <div className={styles.panels}>
          <AuthorityDetailPanel 
            authority={authority} 
            controlledBy={controlledBy}
          />
          <PositionsPanel instanceId={focusedInstance} />
          <OrdersPanel instanceId={focusedInstance} />
          <RiskPanel instanceId={focusedInstance} />
          <TimelinePanel instanceId={focusedInstance} />
        </div>
      </main>
    </div>
  );
};

export default FocusView;
