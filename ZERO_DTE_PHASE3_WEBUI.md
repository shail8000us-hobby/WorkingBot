# Phase 3: WebUI Frontend Implementation

**Duration:** 1-2 weeks  
**Deliverables:** React dashboard, real-time displays, control panel, visualizations

---

## 📋 Phase 3 Overview

Build the frontend dashboard for monitoring and controlling the 0DTE bot. Users can start/stop sessions, view real-time premiums, Greeks, P&L, and execute emergency actions.

**Key Components:**
1. Main dashboard container
2. Premium differential gauge
3. Control panel (start/stop/close)
4. Position display table
5. P&L tracker with charts
6. Greeks visualization
7. Rebalancing history log
8. Risk indicators

---

## Module 1: Main Dashboard Container

### **File:** `webui/frontend/src/components/zero_dte/ZeroDTEDashboard.js`

```javascript
/**
 * Zero DTE Bot Dashboard - Main Container
 */
import React, { useState, useEffect } from 'react';
import ControlPanel from './ControlPanel';
import PremiumGauge from './PremiumGauge';
import PositionsTable from './PositionsTable';
import PnLTracker from './PnLTracker';
import GreeksDisplay from './GreeksDisplay';
import RebalanceHistory from './RebalanceHistory';
import RiskIndicators from './RiskIndicators';
import CountdownTimer from './CountdownTimer';
import './ZeroDTE.css';

const ZeroDTEDashboard = () => {
  const [sessionData, setSessionData] = useState(null);
  const [isActive, setIsActive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch session status
  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000); // Poll every 5s
    return () => clearInterval(interval);
  }, []);

  const fetchStatus = async () => {
    try {
      const response = await fetch('/api/zero-dte/status');
      const data = await response.json();
      
      if (data.success) {
        setSessionData(data);
        setIsActive(data.is_active);
        setError(null);
      }
      setLoading(false);
    } catch (err) {
      setError('Failed to fetch status');
      setLoading(false);
    }
  };

  const handleSessionStart = async (config) => {
    try {
      const response = await fetch('/api/zero-dte/session/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      
      const data = await response.json();
      
      if (data.success) {
        setIsActive(true);
        fetchStatus();
      } else {
        setError(data.message || 'Failed to start session');
      }
    } catch (err) {
      setError('Failed to start session');
    }
  };

  const handleSessionStop = async () => {
    try {
      const response = await fetch('/api/zero-dte/session/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          session_id: sessionData?.session_id,
          reason: 'manual' 
        })
      });
      
      const data = await response.json();
      
      if (data.success) {
        setIsActive(false);
        fetchStatus();
      }
    } catch (err) {
      setError('Failed to stop session');
    }
  };

  if (loading) {
    return <div className="zero-dte-loading">Loading 0DTE Bot...</div>;
  }

  return (
    <div className="zero-dte-dashboard">
      <div className="dashboard-header">
        <h1>0DTE Premium Collection Bot</h1>
        <div className="status-badge">
          {isActive ? (
            <span className="badge-active">● ACTIVE</span>
          ) : (
            <span className="badge-inactive">○ STOPPED</span>
          )}
        </div>
      </div>

      {error && (
        <div className="alert alert-error">{error}</div>
      )}

      <div className="dashboard-grid">
        {/* Control Panel */}
        <div className="grid-item full-width">
          <ControlPanel
            isActive={isActive}
            sessionData={sessionData}
            onStart={handleSessionStart}
            onStop={handleSessionStop}
          />
        </div>

        {/* Countdown Timer */}
        {isActive && (
          <div className="grid-item">
            <CountdownTimer
              settlementTime={sessionData?.settlement_time}
              timezone="Asia/Kolkata"
            />
          </div>
        )}

        {/* Premium Gauge */}
        {isActive && sessionData?.positions && (
          <div className="grid-item">
            <PremiumGauge
              ceTotal={sessionData.premium_differential?.ce_total}
              peTotal={sessionData.premium_differential?.pe_total}
              imbalancePct={sessionData.premium_differential?.imbalance_pct}
            />
          </div>
        )}

        {/* Positions Table */}
        {isActive && (
          <div className="grid-item full-width">
            <PositionsTable positions={sessionData?.positions} />
          </div>
        )}

        {/* P&L Tracker */}
        {isActive && (
          <div className="grid-item">
            <PnLTracker
              unrealizedPnL={sessionData?.pnl?.unrealized}
              realizedPnL={sessionData?.pnl?.realized}
              totalPnL={sessionData?.pnl?.total}
            />
          </div>
        )}

        {/* Greeks Display */}
        {isActive && (
          <div className="grid-item">
            <GreeksDisplay greeks={sessionData?.greeks} />
          </div>
        )}

        {/* Risk Indicators */}
        {isActive && (
          <div className="grid-item">
            <RiskIndicators
              marginUtilization={sessionData?.margin?.utilization_pct}
              guardianStatus={sessionData?.guardian?.status}
            />
          </div>
        )}

        {/* Rebalancing History */}
        {isActive && (
          <div className="grid-item full-width">
            <RebalanceHistory sessionId={sessionData?.session_id} />
          </div>
        )}
      </div>
    </div>
  );
};

export default ZeroDTEDashboard;
```

---

## Module 2: Control Panel

### **File:** `webui/frontend/src/components/zero_dte/ControlPanel.js`

```javascript
/**
 * Control Panel - Start/Stop/Emergency Controls
 */
import React, { useState } from 'react';

const ControlPanel = ({ isActive, sessionData, onStart, onStop }) => {
  const [showStartModal, setShowStartModal] = useState(false);
  const [showStopModal, setShowStopModal] = useState(false);
  const [config, setConfig] = useState({
    underlying: 'BTC',
    initial_lots: 5,
    target_premium_min: 15,
    target_premium_max: 30,
    strike_offset_pct: 2.5
  });

  const handleStartClick = () => {
    setShowStartModal(true);
  };

  const handleConfirmStart = () => {
    onStart(config);
    setShowStartModal(false);
  };

  const handleStopClick = () => {
    setShowStopModal(true);
  };

  const handleConfirmStop = () => {
    onStop();
    setShowStopModal(false);
  };

  return (
    <div className="control-panel card">
      <h2>Control Panel</h2>

      <div className="control-buttons">
        {!isActive ? (
          <button
            className="btn btn-success btn-large"
            onClick={handleStartClick}
          >
            ▶ Start New Session
          </button>
        ) : (
          <button
            className="btn btn-danger btn-large"
            onClick={handleStopClick}
          >
            ■ Stop Session
          </button>
        )}
      </div>

      {isActive && sessionData && (
        <div className="session-info">
          <div className="info-row">
            <span className="label">Session ID:</span>
            <span className="value">{sessionData.session_id}</span>
          </div>
          <div className="info-row">
            <span className="label">Underlying:</span>
            <span className="value">{sessionData.session?.underlying}</span>
          </div>
          <div className="info-row">
            <span className="label">Start Time:</span>
            <span className="value">
              {new Date(sessionData.session?.start_time).toLocaleTimeString('en-IN')}
            </span>
          </div>
        </div>
      )}

      {/* Start Modal */}
      {showStartModal && (
        <div className="modal-overlay">
          <div className="modal">
            <h3>Start New 0DTE Session</h3>
            
            <div className="form-group">
              <label>Underlying:</label>
              <select
                value={config.underlying}
                onChange={(e) => setConfig({ ...config, underlying: e.target.value })}
              >
                <option value="BTC">BTC</option>
                <option value="ETH">ETH</option>
              </select>
            </div>

            <div className="form-group">
              <label>Initial Lot Size:</label>
              <input
                type="number"
                value={config.initial_lots}
                onChange={(e) => setConfig({ ...config, initial_lots: parseInt(e.target.value) })}
                min="1"
                max="20"
              />
            </div>

            <div className="form-group">
              <label>Target Premium Range (₹):</label>
              <div className="input-row">
                <input
                  type="number"
                  value={config.target_premium_min}
                  onChange={(e) => setConfig({ ...config, target_premium_min: parseFloat(e.target.value) })}
                  placeholder="Min"
                />
                <span>to</span>
                <input
                  type="number"
                  value={config.target_premium_max}
                  onChange={(e) => setConfig({ ...config, target_premium_max: parseFloat(e.target.value) })}
                  placeholder="Max"
                />
              </div>
            </div>

            <div className="modal-buttons">
              <button
                className="btn btn-secondary"
                onClick={() => setShowStartModal(false)}
              >
                Cancel
              </button>
              <button
                className="btn btn-success"
                onClick={handleConfirmStart}
              >
                Confirm Start
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Stop Modal */}
      {showStopModal && (
        <div className="modal-overlay">
          <div className="modal">
            <h3>⚠️ Confirm Stop Session</h3>
            <p>This will close all positions and stop the bot. Continue?</p>
            
            <div className="modal-buttons">
              <button
                className="btn btn-secondary"
                onClick={() => setShowStopModal(false)}
              >
                Cancel
              </button>
              <button
                className="btn btn-danger"
                onClick={handleConfirmStop}
              >
                Confirm Stop
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ControlPanel;
```

---

## Module 3: Premium Gauge

### **File:** `webui/frontend/src/components/zero_dte/PremiumGauge.js`

```javascript
/**
 * Premium Gauge - Visual CE vs PE premium comparison
 */
import React from 'react';

const PremiumGauge = ({ ceTotal, peTotal, imbalancePct }) => {
  const maxTotal = Math.max(ceTotal || 0, peTotal || 0);
  const ceWidth = maxTotal > 0 ? (ceTotal / maxTotal) * 100 : 0;
  const peWidth = maxTotal > 0 ? (peTotal / maxTotal) * 100 : 0;

  const getImbalanceColor = (pct) => {
    const absPct = Math.abs(pct);
    if (absPct < 10) return 'green';
    if (absPct < 20) return 'yellow';
    return 'red';
  };

  const imbalanceColor = getImbalanceColor(imbalancePct || 0);

  return (
    <div className="premium-gauge card">
      <h3>Premium Differential</h3>

      <div className="gauge-container">
        {/* CE Bar */}
        <div className="gauge-row">
          <span className="gauge-label">CE Total:</span>
          <div className="gauge-bar-container">
            <div
              className="gauge-bar gauge-bar-ce"
              style={{ width: `${ceWidth}%` }}
            >
              <span className="gauge-value">₹{ceTotal?.toFixed(2)}</span>
            </div>
          </div>
        </div>

        {/* PE Bar */}
        <div className="gauge-row">
          <span className="gauge-label">PE Total:</span>
          <div className="gauge-bar-container">
            <div
              className="gauge-bar gauge-bar-pe"
              style={{ width: `${peWidth}%` }}
            >
              <span className="gauge-value">₹{peTotal?.toFixed(2)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Imbalance Indicator */}
      <div className={`imbalance-indicator imbalance-${imbalanceColor}`}>
        <span className="imbalance-label">Imbalance:</span>
        <span className="imbalance-value">
          {Math.abs(imbalancePct || 0).toFixed(1)}%
        </span>
        {imbalancePct > 0 ? (
          <span className="imbalance-direction">PE Heavy ↑</span>
        ) : (
          <span className="imbalance-direction">CE Heavy ↓</span>
        )}
      </div>

      {/* Balance Status */}
      <div className="balance-status">
        {Math.abs(imbalancePct || 0) < 10 && (
          <span className="status-balanced">✓ Balanced</span>
        )}
        {Math.abs(imbalancePct || 0) >= 10 && Math.abs(imbalancePct || 0) < 20 && (
          <span className="status-warning">⚠ Slight Imbalance</span>
        )}
        {Math.abs(imbalancePct || 0) >= 20 && (
          <span className="status-alert">⚠ Rebalancing Needed</span>
        )}
      </div>
    </div>
  );
};

export default PremiumGauge;
```

---

## Module 4: Countdown Timer

### **File:** `webui/frontend/src/components/zero_dte/CountdownTimer.js`

```javascript
/**
 * Countdown Timer - Time remaining until settlement
 */
import React, { useState, useEffect } from 'react';

const CountdownTimer = ({ settlementTime = '17:30', timezone = 'Asia/Kolkata' }) => {
  const [timeLeft, setTimeLeft] = useState(null);
  const [urgency, setUrgency] = useState('normal');

  useEffect(() => {
    const calculateTimeLeft = () => {
      const now = new Date();
      
      // Parse settlement time (HH:mm format)
      const [hours, minutes] = settlementTime.split(':').map(Number);
      const settlement = new Date(now);
      settlement.setHours(hours, minutes, 0, 0);

      // If settlement time has passed, assume next day
      if (settlement < now) {
        settlement.setDate(settlement.getDate() + 1);
      }

      const diff = settlement - now;

      if (diff <= 0) {
        return { hours: 0, minutes: 0, seconds: 0, total: 0 };
      }

      const totalSeconds = Math.floor(diff / 1000);
      const hours = Math.floor(totalSeconds / 3600);
      const minutes = Math.floor((totalSeconds % 3600) / 60);
      const seconds = totalSeconds % 60;

      return { hours, minutes, seconds, total: totalSeconds };
    };

    const updateTimer = () => {
      const time = calculateTimeLeft();
      setTimeLeft(time);

      // Set urgency level
      if (time.total <= 900) { // 15 minutes
        setUrgency('critical');
      } else if (time.total <= 3600) { // 1 hour
        setUrgency('warning');
      } else {
        setUrgency('normal');
      }
    };

    updateTimer();
    const interval = setInterval(updateTimer, 1000);

    return () => clearInterval(interval);
  }, [settlementTime]);

  if (!timeLeft) {
    return <div className="countdown-timer card">Loading...</div>;
  }

  return (
    <div className={`countdown-timer card countdown-${urgency}`}>
      <h3>Time to Settlement</h3>
      
      <div className="countdown-display">
        <div className="time-segment">
          <span className="time-value">{String(timeLeft.hours).padStart(2, '0')}</span>
          <span className="time-label">Hours</span>
        </div>
        <span className="time-separator">:</span>
        <div className="time-segment">
          <span className="time-value">{String(timeLeft.minutes).padStart(2, '0')}</span>
          <span className="time-label">Minutes</span>
        </div>
        <span className="time-separator">:</span>
        <div className="time-segment">
          <span className="time-value">{String(timeLeft.seconds).padStart(2, '0')}</span>
          <span className="time-label">Seconds</span>
        </div>
      </div>

      <div className="settlement-info">
        <span>Settlement at {settlementTime} IST</span>
      </div>

      {urgency === 'critical' && (
        <div className="urgency-alert alert-critical">
          🚨 Less than 15 minutes remaining!
        </div>
      )}

      {urgency === 'warning' && (
        <div className="urgency-alert alert-warning">
          ⚠️ Less than 1 hour remaining
        </div>
      )}
    </div>
  );
};

export default CountdownTimer;
```

---

## Module 5: Positions Table

### **File:** `webui/frontend/src/components/zero_dte/PositionsTable.js`

```javascript
/**
 * Positions Table - Display CE and PE positions
 */
import React from 'react';

const PositionsTable = ({ positions }) => {
  if (!positions || (!positions.ce && !positions.pe)) {
    return (
      <div className="positions-table card">
        <h3>Positions</h3>
        <p>No active positions</p>
      </div>
    );
  }

  const { ce, pe } = positions;

  return (
    <div className="positions-table card">
      <h3>Current Positions</h3>

      <table className="table">
        <thead>
          <tr>
            <th>Leg</th>
            <th>Symbol</th>
            <th>Strike</th>
            <th>Lots</th>
            <th>Entry Premium</th>
            <th>Current Premium</th>
            <th>P&L</th>
            <th>Delta</th>
            <th>Gamma</th>
            <th>Theta</th>
            <th>IV</th>
          </tr>
        </thead>
        <tbody>
          {/* CE Row */}
          {ce && (
            <tr className="row-ce">
              <td><span className="leg-badge leg-ce">CE</span></td>
              <td>{ce.symbol}</td>
              <td>₹{ce.strike?.toLocaleString()}</td>
              <td>{ce.lots}</td>
              <td>₹{ce.entry_premium?.toFixed(2)}</td>
              <td>₹{ce.current_premium?.toFixed(2)}</td>
              <td className={ce.unrealized_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}>
                ₹{ce.unrealized_pnl?.toFixed(2)}
              </td>
              <td>{ce.delta?.toFixed(3)}</td>
              <td>{ce.gamma?.toFixed(4)}</td>
              <td>{ce.theta?.toFixed(2)}</td>
              <td>{(ce.iv * 100)?.toFixed(1)}%</td>
            </tr>
          )}

          {/* PE Row */}
          {pe && (
            <tr className="row-pe">
              <td><span className="leg-badge leg-pe">PE</span></td>
              <td>{pe.symbol}</td>
              <td>₹{pe.strike?.toLocaleString()}</td>
              <td>{pe.lots}</td>
              <td>₹{pe.entry_premium?.toFixed(2)}</td>
              <td>₹{pe.current_premium?.toFixed(2)}</td>
              <td className={pe.unrealized_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}>
                ₹{pe.unrealized_pnl?.toFixed(2)}
              </td>
              <td>{pe.delta?.toFixed(3)}</td>
              <td>{pe.gamma?.toFixed(4)}</td>
              <td>{pe.theta?.toFixed(2)}</td>
              <td>{(pe.iv * 100)?.toFixed(1)}%</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
};

export default PositionsTable;
```

---

**Continue to:** [ZERO_DTE_PHASE3_WEBUI_PART2.md](ZERO_DTE_PHASE3_WEBUI_PART2.md) for remaining components.
