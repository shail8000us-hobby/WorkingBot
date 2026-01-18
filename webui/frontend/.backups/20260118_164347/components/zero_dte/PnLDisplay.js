/**
 * P&L Display Component
 * 
 * Shows realized, unrealized, and total P&L.
 * Displays premium collected vs current position value.
 */
import React from 'react';

const PnLDisplay = ({ status, positions }) => {
  // Calculate P&L from positions
  const calculatePnL = () => {
    if (!positions || (!positions.CE && !positions.PE)) {
      return {
        unrealizedPnL: 0,
        realizedPnL: status?.session?.realized_pnl || 0,
        premiumCollected: status?.session?.premium_collected || 0,
        currentExposure: 0,
      };
    }

    let unrealizedPnL = 0;
    let premiumCollected = 0;
    let currentExposure = 0;

    ['CE', 'PE'].forEach(side => {
      const pos = positions[side];
      if (pos) {
        const entryValue = pos.entry_premium * pos.lots;
        const currentValue = pos.current_premium * pos.lots;
        
        // For short positions: profit when current < entry
        unrealizedPnL += (entryValue - currentValue);
        premiumCollected += entryValue;
        currentExposure += currentValue;
      }
    });

    return {
      unrealizedPnL,
      realizedPnL: status?.session?.realized_pnl || 0,
      premiumCollected,
      currentExposure,
    };
  };

  const pnl = calculatePnL();
  const totalPnL = pnl.unrealizedPnL + pnl.realizedPnL;
  
  // Stop loss from config (default 5000)
  const stopLoss = status?.config?.stop_loss || 5000;
  const stopLossUsed = Math.min(100, Math.max(0, (-totalPnL / stopLoss) * 100));
  
  const formatCurrency = (value) => {
    const prefix = value >= 0 ? '+' : '';
    return `${prefix}₹${value.toFixed(2)}`;
  };

  const getPnLClass = (value) => {
    if (value > 0) return 'pnl-positive';
    if (value < 0) return 'pnl-negative';
    return 'pnl-neutral';
  };

  return (
    <div className="pnl-display card">
      <h3>Profit & Loss</h3>

      <div className="pnl-grid">
        {/* Total P&L - Main Display */}
        <div className={`pnl-total ${getPnLClass(totalPnL)}`}>
          <span className="pnl-label">Total P&L</span>
          <span className="pnl-value">{formatCurrency(totalPnL)}</span>
        </div>

        {/* Breakdown */}
        <div className="pnl-breakdown">
          <div className={`pnl-item ${getPnLClass(pnl.unrealizedPnL)}`}>
            <span className="pnl-item-label">Unrealized</span>
            <span className="pnl-item-value">{formatCurrency(pnl.unrealizedPnL)}</span>
          </div>
          
          <div className={`pnl-item ${getPnLClass(pnl.realizedPnL)}`}>
            <span className="pnl-item-label">Realized</span>
            <span className="pnl-item-value">{formatCurrency(pnl.realizedPnL)}</span>
          </div>
        </div>

        {/* Premium Stats */}
        <div className="premium-stats">
          <div className="premium-item">
            <span className="premium-label">Premium Collected</span>
            <span className="premium-value">₹{pnl.premiumCollected.toFixed(2)}</span>
          </div>
          
          <div className="premium-item">
            <span className="premium-label">Current Exposure</span>
            <span className="premium-value">₹{pnl.currentExposure.toFixed(2)}</span>
          </div>
        </div>

        {/* Stop Loss Indicator */}
        <div className="stop-loss-indicator">
          <div className="stop-loss-header">
            <span>Stop Loss Progress</span>
            <span>{stopLossUsed.toFixed(1)}% of ₹{stopLoss}</span>
          </div>
          <div className="stop-loss-bar">
            <div 
              className={`stop-loss-fill ${stopLossUsed > 80 ? 'danger' : stopLossUsed > 50 ? 'warning' : 'safe'}`}
              style={{ width: `${stopLossUsed}%` }}
            />
          </div>
          {stopLossUsed > 80 && (
            <div className="stop-loss-warning">
              ⚠️ Approaching stop loss trigger
            </div>
          )}
        </div>
      </div>

      {/* Session Stats */}
      {status?.session && (
        <div className="session-stats">
          <div className="stat-item">
            <span className="stat-label">Trades</span>
            <span className="stat-value">{status.session.trade_count || 0}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Rebalances</span>
            <span className="stat-value">{status.session.rebalance_count || 0}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Rollovers</span>
            <span className="stat-value">{status.session.rollover_count || 0}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default PnLDisplay;
