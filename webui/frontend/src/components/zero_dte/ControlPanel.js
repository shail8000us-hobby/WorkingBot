/**
 * Control Panel - Start/Stop Session with Expiry Selector
 *
 * Features:
 * - Expiry/DTE selector with live expiry dates
 * - Underlying selector (BTC/ETH)
 * - Lots configuration
 * - Premium range settings
 * - Emergency stop controls
 */
import React, { useState, useEffect, useCallback } from 'react';

const ControlPanel = ({ isActive, onStart, onStop, loading, sessionId, currentExpiry }) => {
  const [showStartModal, setShowStartModal] = useState(false);
  const [availableExpiries, setAvailableExpiries] = useState([]);
  const [loadingExpiries, setLoadingExpiries] = useState(false);

  const [config, setConfig] = useState({
    underlying: 'BTC',
    expiry: '',
    initial_lots: 5,
    target_premium_min: 15,
    target_premium_max: 30,
    stop_loss: 5000,
    rebalance_threshold: 20,
    skip_time_check: false,
  });

  // Fetch available expiries for the underlying
  const fetchExpiries = useCallback(async (underlying) => {
    setLoadingExpiries(true);
    try {
      const response = await fetch(`/api/zero-dte/expiries?underlying=${underlying}`);
      const data = await response.json();

      if (data.success && data.expiries) {
        setAvailableExpiries(data.expiries);
        // Auto-select 0DTE (today's expiry) if available
        // CRITICAL: Use IST timezone (Asia/Kolkata) for date comparison
        const today = new Date().toLocaleDateString('en-CA', {
          timeZone: 'Asia/Kolkata',
          year: 'numeric',
          month: '2-digit',
          day: '2-digit'
        }); // Returns YYYY-MM-DD format in IST
        const todayExpiry = data.expiries.find((e) => e.date === today || e.dte === 0);
        if (todayExpiry) {
          setConfig((prev) => ({ ...prev, expiry: todayExpiry.date || todayExpiry.symbol }));
        } else if (data.expiries.length > 0) {
          setConfig((prev) => ({
            ...prev,
            expiry: data.expiries[0].date || data.expiries[0].symbol,
          }));
        }
      } else {
        generateFallbackExpiries();
      }
    } catch (err) {
      console.error('Failed to fetch expiries:', err);
      generateFallbackExpiries();
    } finally {
      setLoadingExpiries(false);
    }
  }, []);

  // Generate fallback expiries if API fails
  const generateFallbackExpiries = () => {
    const today = new Date();
    const expiries = [];

    for (let i = 0; i < 7; i++) {
      const date = new Date(today);
      date.setDate(date.getDate() + i);
      // Use IST timezone for date formatting
      const dateStr = date.toLocaleDateString('en-CA', {
        timeZone: 'Asia/Kolkata',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
      });

      expiries.push({
        date: dateStr,
        dte: i,
        symbol: dateStr,
      });
    }

    setAvailableExpiries(expiries);
    if (expiries.length > 0) {
      setConfig((prev) => ({ ...prev, expiry: expiries[0].date || expiries[0].symbol }));
    }
  };

  useEffect(() => {
    if (showStartModal) {
      fetchExpiries(config.underlying);
    }
  }, [config.underlying, showStartModal, fetchExpiries]);

  const handleStartSubmit = (e) => {
    e.preventDefault();
    if (!config.expiry) {
      alert('Please select an expiry date');
      return;
    }
    onStart(config);
    setShowStartModal(false);
  };

  const formatTimeRemaining = () => {
    const now = new Date();
    const settlement = new Date();
    settlement.setHours(17, 30, 0, 0);
    const diff = settlement - now;
    if (diff <= 0) return 'Expired';
    const hours = Math.floor(diff / 3600000);
    const mins = Math.floor((diff % 3600000) / 60000);
    return `${hours}h ${mins}m`;
  };

  return (
    <div className="control-panel card">
      <div className="card-header">
        <h3>
          <span className="card-icon">⚡</span>
          Control Panel
        </h3>
        {isActive && (
          <span className="live-indicator">
            <span className="pulse-dot"></span> LIVE
          </span>
        )}
      </div>

      {!isActive ? (
        <div className="control-inactive">
          <div className="start-prompt">
            <div className="prompt-icon">🚀</div>
            <h4>Ready to Trade</h4>
            <p>Start a new 0DTE session to begin autonomous strangle trading.</p>
          </div>
          <button
            className="btn btn-primary btn-glow"
            onClick={() => setShowStartModal(true)}
            disabled={loading}
          >
            <span className="btn-icon">▶</span>
            Start 0DTE Session
          </button>
        </div>
      ) : (
        <div className="control-active">
          <div className="session-badge">
            <span className="session-label">Session</span>
            <span className="session-id">{sessionId?.slice(-8) || 'N/A'}</span>
          </div>

          {currentExpiry && (
            <div className="current-expiry-display">
              <span className="expiry-label">Trading</span>
              <span className="expiry-value">{currentExpiry}</span>
            </div>
          )}

          <div className="auto-mode-card">
            <div className="auto-header">
              <span className="auto-icon">🤖</span>
              <span>Autonomous Mode</span>
            </div>
            <ul className="auto-actions">
              <li>
                <span className="check">✓</span> Rebalancing at 20% imbalance
              </li>
              <li>
                <span className="check">✓</span> Rolling when premium &lt; ₹5
              </li>
              <li>
                <span className="check">✓</span> Exit when BOTH legs &lt; ₹5
              </li>
              <li>
                <span className="check">✓</span> Force exit at 17:15 IST
              </li>
            </ul>
          </div>

          <div className="stop-controls">
            <button className="btn btn-stop" onClick={() => onStop('manual')} disabled={loading}>
              <span className="btn-icon">⏹</span>
              Stop Session
            </button>
            <button
              className="btn btn-emergency"
              onClick={() => onStop('emergency')}
              disabled={loading}
            >
              <span className="btn-icon">🚨</span>
              Emergency
            </button>
          </div>
        </div>
      )}

      {/* Start Modal */}
      {showStartModal && (
        <div className="modal-overlay" onClick={() => setShowStartModal(false)}>
          <div className="start-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                <span className="modal-icon">⚡</span>
                New 0DTE Session
              </h2>
              <button className="modal-close" onClick={() => setShowStartModal(false)}>
                ×
              </button>
            </div>

            <form onSubmit={handleStartSubmit}>
              {/* Underlying Selector */}
              <div className="form-section">
                <label className="section-label">Asset</label>
                <div className="asset-selector">
                  {['BTC', 'ETH'].map((asset) => (
                    <button
                      key={asset}
                      type="button"
                      className={`asset-btn ${config.underlying === asset ? 'selected' : ''}`}
                      onClick={() => setConfig({ ...config, underlying: asset })}
                    >
                      <span className="asset-icon">{asset === 'BTC' ? '₿' : 'Ξ'}</span>
                      <span className="asset-name">{asset}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Expiry Selector */}
              <div className="form-section">
                <label className="section-label">
                  Expiry Date
                  {loadingExpiries && <span className="loading-text"> (loading...)</span>}
                </label>
                <div className="expiry-selector">
                  {availableExpiries.length > 0 ? (
                    <div className="expiry-grid">
                      {availableExpiries.slice(0, 7).map((exp) => (
                        <button
                          key={exp.symbol || exp.date}
                          type="button"
                          className={`expiry-btn ${config.expiry === exp.symbol || config.expiry === exp.date
                            ? 'selected'
                            : ''
                            } ${exp.dte === 0 ? 'today' : ''}`}
                          onClick={() => setConfig({ ...config, expiry: exp.date || exp.symbol })}
                        >
                          <span className="expiry-dte">
                            {exp.dte === 0 ? '0DTE' : `${exp.dte}DTE`}
                          </span>
                          <span className="expiry-date">
                            {new Date(exp.date + 'T00:00:00').toLocaleDateString('en-IN', {
                              weekday: 'short',
                              day: 'numeric',
                              month: 'short',
                            })}
                          </span>
                          {exp.dte === 0 && <span className="expiry-tag">TODAY</span>}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <div className="expiry-loading">
                      {loadingExpiries ? 'Fetching expiries...' : 'No expiries available'}
                    </div>
                  )}
                </div>

                <div className="expiry-info">
                  <span>Settlement: 17:30 IST</span>
                  <span>Time remaining: {formatTimeRemaining()}</span>
                </div>
              </div>

              {/* Position Size */}
              <div className="form-section">
                <label className="section-label">Position Size</label>
                <div className="lots-selector">
                  <button
                    type="button"
                    className="lots-btn"
                    onClick={() =>
                      setConfig({ ...config, initial_lots: Math.max(1, config.initial_lots - 1) })
                    }
                  >
                    −
                  </button>
                  <div className="lots-display">
                    <span className="lots-value">{config.initial_lots}</span>
                    <span className="lots-label">Lots per leg</span>
                  </div>
                  <button
                    type="button"
                    className="lots-btn"
                    onClick={() =>
                      setConfig({ ...config, initial_lots: Math.min(20, config.initial_lots + 1) })
                    }
                  >
                    +
                  </button>
                </div>
                <div className="lots-hint">Total: {config.initial_lots * 2} lots (CE + PE)</div>
              </div>

              {/* Premium Range */}
              <div className="form-section">
                <label className="section-label">Target Premium Range</label>
                <div className="premium-inputs">
                  <div className="premium-input-group">
                    <label>Min</label>
                    <div className="input-with-unit">
                      <span className="unit">₹</span>
                      <input
                        type="number"
                        min="5"
                        max="50"
                        value={config.target_premium_min}
                        onChange={(e) =>
                          setConfig({ ...config, target_premium_min: parseFloat(e.target.value) })
                        }
                      />
                    </div>
                  </div>
                  <div className="premium-divider">—</div>
                  <div className="premium-input-group">
                    <label>Max</label>
                    <div className="input-with-unit">
                      <span className="unit">₹</span>
                      <input
                        type="number"
                        min="10"
                        max="100"
                        value={config.target_premium_max}
                        onChange={(e) =>
                          setConfig({ ...config, target_premium_max: parseFloat(e.target.value) })
                        }
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Advanced Settings */}
              <details className="advanced-settings">
                <summary>Advanced Settings</summary>
                <div className="advanced-content">
                  <div className="advanced-row">
                    <label>Stop Loss</label>
                    <div className="input-with-unit">
                      <span className="unit">₹</span>
                      <input
                        type="number"
                        value={config.stop_loss}
                        onChange={(e) =>
                          setConfig({ ...config, stop_loss: parseFloat(e.target.value) })
                        }
                      />
                    </div>
                  </div>
                  <div className="advanced-row">
                    <label>Rebalance Threshold</label>
                    <div className="input-with-unit">
                      <input
                        type="number"
                        min="10"
                        max="50"
                        value={config.rebalance_threshold}
                        onChange={(e) =>
                          setConfig({ ...config, rebalance_threshold: parseFloat(e.target.value) })
                        }
                      />
                      <span className="unit">%</span>
                    </div>
                  </div>
                  <div className="advanced-row toggle-row">
                    <label>Allow Entry Anytime</label>
                    <label className="toggle-switch">
                      <input
                        type="checkbox"
                        checked={config.skip_time_check}
                        onChange={(e) =>
                          setConfig({ ...config, skip_time_check: e.target.checked })
                        }
                      />
                      <span className="toggle-slider"></span>
                    </label>
                  </div>
                  {config.skip_time_check && (
                    <div className="time-warning">
                      ⚠️ Time check disabled - Entering outside recommended hours (09:30-16:30 IST)
                    </div>
                  )}
                </div>
              </details>

              {/* Strategy Summary */}
              <div className="strategy-summary">
                <div className="summary-item">
                  <span className="summary-icon">📊</span>
                  <span>Sell strangle (CE + PE)</span>
                </div>
                <div className="summary-item">
                  <span className="summary-icon">🎯</span>
                  <span>Exit when BOTH premiums &lt; ₹5</span>
                </div>
                <div className="summary-item">
                  <span className="summary-icon">⚖️</span>
                  <span>Auto-rebalance at {config.rebalance_threshold}% imbalance</span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="modal-actions">
                <button
                  type="button"
                  className="btn btn-cancel"
                  onClick={() => setShowStartModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-start"
                  disabled={loading || !config.expiry}
                >
                  {loading ? (
                    <>
                      <span className="spinner"></span> Starting...
                    </>
                  ) : (
                    <>
                      <span className="btn-icon">🚀</span> Start Trading
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default ControlPanel;
