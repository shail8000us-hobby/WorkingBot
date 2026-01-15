/**
 * Premium Gauge - Visual CE vs PE balance
 * 
 * Shows total premium exposure for each leg.
 * Color codes imbalance level:
 * - Green: < 10% (balanced)
 * - Yellow: 10-20% (watch)
 * - Red: > 20% (rebalancing will trigger)
 */
import React from 'react';

const PremiumGauge = ({ ceTotal, peTotal, imbalancePct, isBalanced, threshold }) => {
  // Calculate bar widths (relative to max)
  const maxTotal = Math.max(ceTotal, peTotal, 1);
  const ceWidth = (ceTotal / maxTotal) * 100;
  const peWidth = (peTotal / maxTotal) * 100;

  // Determine imbalance color
  const getImbalanceColor = () => {
    if (imbalancePct < 10) return 'imbalance-green';
    if (imbalancePct < threshold) return 'imbalance-yellow';
    return 'imbalance-red';
  };

  // Determine which leg is heavier
  const heavierLeg = ceTotal > peTotal ? 'CE' : (peTotal > ceTotal ? 'PE' : 'Equal');

  return (
    <div className="premium-gauge card">
      <h3>Premium Balance</h3>
      
      <div className="gauge-container">
        {/* CE Bar */}
        <div className="gauge-row">
          <span className="gauge-label ce-label">CE</span>
          <div className="gauge-bar-container">
            <div 
              className="gauge-bar gauge-bar-ce"
              style={{ width: `${ceWidth}%` }}
            >
              <span className="gauge-value">₹{ceTotal.toFixed(2)}</span>
            </div>
          </div>
        </div>

        {/* PE Bar */}
        <div className="gauge-row">
          <span className="gauge-label pe-label">PE</span>
          <div className="gauge-bar-container">
            <div 
              className="gauge-bar gauge-bar-pe"
              style={{ width: `${peWidth}%` }}
            >
              <span className="gauge-value">₹{peTotal.toFixed(2)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Imbalance Indicator */}
      <div className={`imbalance-indicator ${getImbalanceColor()}`}>
        <div className="imbalance-header">
          <span>Imbalance</span>
          <span className="imbalance-value">{imbalancePct.toFixed(1)}%</span>
        </div>
        <div className="imbalance-bar-bg">
          <div 
            className="imbalance-bar-fill"
            style={{ width: `${Math.min(imbalancePct, 100)}%` }}
          />
          <div 
            className="threshold-marker"
            style={{ left: `${threshold}%` }}
          />
        </div>
        <div className="imbalance-status">
          {isBalanced ? (
            <span className="status-balanced">✓ Balanced</span>
          ) : (
            <span className="status-unbalanced">⚠ {heavierLeg} heavy - Rebalance pending</span>
          )}
        </div>
      </div>

      {/* Legend */}
      <div className="gauge-legend">
        <span className="legend-item">
          <span className="legend-dot green"></span> &lt;10%
        </span>
        <span className="legend-item">
          <span className="legend-dot yellow"></span> 10-20%
        </span>
        <span className="legend-item">
          <span className="legend-dot red"></span> &gt;20% (rebalance)
        </span>
      </div>
    </div>
  );
};

export default PremiumGauge;
