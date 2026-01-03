/**
 * Bot State Panel - Shows current bot state in real-time
 */

import React from 'react';
import styles from './BotStatePanel.module.css';

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

interface Props {
  state: BotState;
}

export const BotStatePanel: React.FC<Props> = ({ state }) => {
  const getStatusColor = () => {
    if (state.emergency_stop) return 'var(--error-color)';
    if (!state.trading_enabled || !state.volatility_safe) return 'var(--warning-color)';
    return 'var(--success-color)';
  };

  const getStatusText = () => {
    if (state.emergency_stop) return '🔴 EMERGENCY STOP';
    if (!state.trading_enabled) return '⏸️ TRADING PAUSED';
    if (!state.volatility_safe) return '⚠️ HIGH VOLATILITY';
    return '✅ TRADING ACTIVE';
  };

  return (
    <div className={styles.container}>
      <div className={styles.statusCard} style={{ borderColor: getStatusColor() }}>
        <h2 className={styles.statusText} style={{ color: getStatusColor() }}>
          {getStatusText()}
        </h2>
        <p className={styles.timestamp}>
          Last update: {new Date(state.timestamp).toLocaleString()}
        </p>
      </div>

      <div className={styles.grid}>
        <div className={styles.card}>
          <div className={styles.cardIcon}>💰</div>
          <div className={styles.cardLabel}>Current Price</div>
          <div className={styles.cardValue}>${state.current_price.toLocaleString()}</div>
        </div>

        <div className={styles.card}>
          <div className={styles.cardIcon}>📊</div>
          <div className={styles.cardLabel}>Open Positions</div>
          <div className={styles.cardValue}>{state.open_positions}</div>
        </div>

        <div className={styles.card}>
          <div className={styles.cardIcon}>📝</div>
          <div className={styles.cardLabel}>Pending Orders</div>
          <div className={styles.cardValue}>{state.pending_orders}</div>
        </div>

        <div className={styles.card}>
          <div className={styles.cardIcon}>📉</div>
          <div className={styles.cardLabel}>Next Buy Level</div>
          <div className={styles.cardValue}>${state.next_buy_level.toLocaleString()}</div>
        </div>

        <div className={styles.card}>
          <div className={styles.cardIcon}>📈</div>
          <div className={styles.cardLabel}>Next Sell Level</div>
          <div className={styles.cardValue}>${state.next_sell_level.toLocaleString()}</div>
        </div>

        <div className={styles.card}>
          <div className={styles.cardIcon}>🌊</div>
          <div className={styles.cardLabel}>Volatility Check</div>
          <div className={styles.cardValue}>
            {state.volatility_safe ? '✅ Safe' : '❌ Unsafe'}
          </div>
        </div>
      </div>

      <div className={styles.explanation}>
        <h3>💡 What This Means</h3>
        <ul>
          {state.emergency_stop && (
            <li className={styles.critical}>Emergency stop is active - no trades will execute</li>
          )}
          {!state.trading_enabled && (
            <li className={styles.warning}>Trading is paused - waiting for conditions to improve</li>
          )}
          {!state.volatility_safe && (
            <li className={styles.warning}>Volatility too high - bot is protecting capital</li>
          )}
          {state.trading_enabled && state.volatility_safe && (
            <>
              <li className={styles.info}>
                Bot will BUY if price drops to ${state.next_buy_level.toLocaleString()}
              </li>
              <li className={styles.info}>
                Bot will SELL if price rises to ${state.next_sell_level.toLocaleString()}
              </li>
              <li className={styles.info}>
                Currently managing {state.open_positions} position(s) with {state.pending_orders} pending order(s)
              </li>
            </>
          )}
        </ul>
      </div>
    </div>
  );
};
