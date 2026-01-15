# Phase 3: WebUI Frontend - Part 2

**Remaining React components for visualization and interaction**

---

## Module 6: P&L Tracker

### **File:** `webui/frontend/src/components/zero_dte/PnLTracker.js`

```javascript
/**
 * P&L Tracker - Profit/Loss display with chart
 */
import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const PnLTracker = ({ unrealizedPnL, realizedPnL, totalPnL }) => {
  const [pnlHistory, setPnlHistory] = useState([]);

  useEffect(() => {
    // Add current P&L to history
    if (totalPnL !== undefined) {
      const now = new Date().toLocaleTimeString('en-IN', { 
        hour: '2-digit', 
        minute: '2-digit' 
      });
      
      setPnlHistory(prev => {
        const newHistory = [...prev, { time: now, pnl: totalPnL }];
        // Keep last 50 points
        return newHistory.slice(-50);
      });
    }
  }, [totalPnL]);

  const getPnLClass = (value) => {
    if (value > 0) return 'pnl-positive';
    if (value < 0) return 'pnl-negative';
    return 'pnl-neutral';
  };

  return (
    <div className="pnl-tracker card">
      <h3>Profit & Loss</h3>

      <div className="pnl-summary">
        <div className="pnl-item">
          <span className="pnl-label">Unrealized:</span>
          <span className={`pnl-value ${getPnLClass(unrealizedPnL)}`}>
            ₹{unrealizedPnL?.toFixed(2) || '0.00'}
          </span>
        </div>

        <div className="pnl-item">
          <span className="pnl-label">Realized:</span>
          <span className={`pnl-value ${getPnLClass(realizedPnL)}`}>
            ₹{realizedPnL?.toFixed(2) || '0.00'}
          </span>
        </div>

        <div className="pnl-item pnl-total">
          <span className="pnl-label">Total:</span>
          <span className={`pnl-value ${getPnLClass(totalPnL)}`}>
            ₹{totalPnL?.toFixed(2) || '0.00'}
          </span>
        </div>
      </div>

      {/* P&L Chart */}
      {pnlHistory.length > 0 && (
        <div className="pnl-chart">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={pnlHistory}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="time" 
                tick={{ fontSize: 10 }}
                interval="preserveStartEnd"
              />
              <YAxis 
                tick={{ fontSize: 10 }}
                tickFormatter={(value) => `₹${value}`}
              />
              <Tooltip 
                formatter={(value) => [`₹${value.toFixed(2)}`, 'P&L']}
              />
              <Line 
                type="monotone" 
                dataKey="pnl" 
                stroke="#8884d8" 
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};

export default PnLTracker;
```

---

## Module 7: Greeks Display

### **File:** `webui/frontend/src/components/zero_dte/GreeksDisplay.js`

```javascript
/**
 * Greeks Display - Portfolio Greeks visualization
 */
import React from 'react';
import { CircularProgressbar, buildStyles } from 'react-circular-progressbar';
import 'react-circular-progressbar/dist/styles.css';

const GreeksDisplay = ({ greeks }) => {
  if (!greeks) {
    return (
      <div className="greeks-display card">
        <h3>Portfolio Greeks</h3>
        <p>No Greeks data available</p>
      </div>
    );
  }

  const { portfolio_delta, portfolio_gamma, portfolio_theta, portfolio_vega } = greeks;

  // Delta gauge (as percentage, limit ±0.5)
  const deltaLimit = 0.5;
  const deltaPct = Math.min(Math.abs(portfolio_delta || 0) / deltaLimit * 100, 100);
  const deltaColor = deltaPct > 80 ? '#ff4444' : deltaPct > 60 ? '#ffaa00' : '#44ff44';

  return (
    <div className="greeks-display card">
      <h3>Portfolio Greeks</h3>

      <div className="greeks-grid">
        {/* Delta */}
        <div className="greek-item">
          <div className="greek-gauge">
            <CircularProgressbar
              value={deltaPct}
              text={`${Math.abs(portfolio_delta || 0).toFixed(3)}`}
              styles={buildStyles({
                pathColor: deltaColor,
                textColor: deltaColor,
                trailColor: '#d6d6d6',
              })}
            />
          </div>
          <div className="greek-label">
            <span className="greek-name">Delta</span>
            <span className="greek-limit">Limit: ±{deltaLimit}</span>
          </div>
        </div>

        {/* Gamma */}
        <div className="greek-item">
          <div className="greek-value">
            {(portfolio_gamma || 0).toFixed(4)}
          </div>
          <div className="greek-label">
            <span className="greek-name">Gamma</span>
          </div>
        </div>

        {/* Theta */}
        <div className="greek-item">
          <div className="greek-value">
            {(portfolio_theta || 0).toFixed(2)}
          </div>
          <div className="greek-label">
            <span className="greek-name">Theta (daily)</span>
          </div>
        </div>

        {/* Vega */}
        <div className="greek-item">
          <div className="greek-value">
            {(portfolio_vega || 0).toFixed(2)}
          </div>
          <div className="greek-label">
            <span className="greek-name">Vega</span>
          </div>
        </div>
      </div>

      {/* Delta Warning */}
      {Math.abs(portfolio_delta || 0) > deltaLimit * 0.8 && (
        <div className="alert alert-warning">
          ⚠️ Delta approaching limit
        </div>
      )}
    </div>
  );
};

export default GreeksDisplay;
```

---

## Module 8: Rebalancing History

### **File:** `webui/frontend/src/components/zero_dte/RebalanceHistory.js`

```javascript
/**
 * Rebalancing History - Log of all rebalancing actions
 */
import React, { useState, useEffect } from 'react';

const RebalanceHistory = ({ sessionId }) => {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all'); // 'all', 'lot_adjustment', 'strike_rollover'

  useEffect(() => {
    if (sessionId) {
      fetchHistory();
      const interval = setInterval(fetchHistory, 10000); // Update every 10s
      return () => clearInterval(interval);
    }
  }, [sessionId]);

  const fetchHistory = async () => {
    try {
      const response = await fetch(`/api/zero-dte/rebalances?session_id=${sessionId}&limit=20`);
      const data = await response.json();
      
      if (data.success) {
        setHistory(data.rebalances || []);
      }
      setLoading(false);
    } catch (err) {
      console.error('Failed to fetch rebalance history:', err);
      setLoading(false);
    }
  };

  const filteredHistory = filter === 'all' 
    ? history 
    : history.filter(r => r.type === filter);

  const getStatusBadge = (status) => {
    const badges = {
      success: <span className="badge badge-success">✓ Success</span>,
      partial: <span className="badge badge-warning">⚠ Partial</span>,
      failed: <span className="badge badge-error">✗ Failed</span>
    };
    return badges[status] || status;
  };

  if (loading) {
    return <div className="rebalance-history card">Loading history...</div>;
  }

  return (
    <div className="rebalance-history card">
      <div className="history-header">
        <h3>Rebalancing History</h3>
        
        <div className="history-filters">
          <button
            className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
          >
            All
          </button>
          <button
            className={`filter-btn ${filter === 'lot_adjustment' ? 'active' : ''}`}
            onClick={() => setFilter('lot_adjustment')}
          >
            Lot Adjustments
          </button>
          <button
            className={`filter-btn ${filter === 'strike_rollover' ? 'active' : ''}`}
            onClick={() => setFilter('strike_rollover')}
          >
            Strike Rollovers
          </button>
        </div>
      </div>

      {filteredHistory.length === 0 ? (
        <p>No rebalancing history</p>
      ) : (
        <div className="history-table-container">
          <table className="table table-compact">
            <thead>
              <tr>
                <th>Time</th>
                <th>Type</th>
                <th>Reason</th>
                <th>Action</th>
                <th>Before</th>
                <th>After</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredHistory.map((entry, idx) => (
                <tr key={entry.id || idx}>
                  <td>
                    {new Date(entry.timestamp).toLocaleTimeString('en-IN')}
                  </td>
                  <td>
                    <span className={`type-badge type-${entry.type}`}>
                      {entry.type === 'lot_adjustment' ? '⚖️ Adjust' : '🔄 Rollover'}
                    </span>
                  </td>
                  <td className="reason-cell">{entry.reason}</td>
                  <td className="action-cell">{entry.action}</td>
                  <td>
                    CE: {entry.before?.ce_lots} lots<br />
                    PE: {entry.before?.pe_lots} lots<br />
                    Imbalance: {entry.before?.imbalance}%
                  </td>
                  <td>
                    CE: {entry.after?.ce_lots} lots<br />
                    PE: {entry.after?.pe_lots} lots<br />
                    Imbalance: {entry.after?.imbalance}%
                  </td>
                  <td>{getStatusBadge(entry.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default RebalanceHistory;
```

---

## Module 9: Risk Indicators

### **File:** `webui/frontend/src/components/zero_dte/RiskIndicators.js`

```javascript
/**
 * Risk Indicators - Margin, Guardian, and risk metrics
 */
import React from 'react';

const RiskIndicators = ({ marginUtilization, guardianStatus }) => {
  const getMarginColor = (utilization) => {
    if (utilization < 40) return 'green';
    if (utilization < 60) return 'yellow';
    if (utilization < 80) return 'orange';
    return 'red';
  };

  const marginColor = getMarginColor(marginUtilization || 0);

  return (
    <div className="risk-indicators card">
      <h3>Risk Indicators</h3>

      {/* Margin Utilization */}
      <div className="risk-item">
        <div className="risk-label">Margin Utilization</div>
        <div className="progress-bar-container">
          <div
            className={`progress-bar progress-${marginColor}`}
            style={{ width: `${marginUtilization || 0}%` }}
          >
            <span className="progress-text">
              {(marginUtilization || 0).toFixed(1)}%
            </span>
          </div>
        </div>
        {marginUtilization > 75 && (
          <div className="risk-warning">
            ⚠️ High margin utilization - Risk of auto-halt
          </div>
        )}
      </div>

      {/* Guardian Status */}
      <div className="risk-item">
        <div className="risk-label">Guardian Signal</div>
        <div className="guardian-status">
          {guardianStatus === 'GO' ? (
            <span className="status-go">✓ GO</span>
          ) : guardianStatus === 'STOP' ? (
            <span className="status-stop">✗ STOP</span>
          ) : (
            <span className="status-unknown">? Unknown</span>
          )}
        </div>
      </div>

      {/* Risk Level Summary */}
      <div className="risk-summary">
        {marginUtilization < 40 && guardianStatus === 'GO' && (
          <div className="alert alert-success">
            ✓ All systems operational
          </div>
        )}
        {(marginUtilization >= 60 || guardianStatus === 'STOP') && (
          <div className="alert alert-error">
            ⚠️ Risk limits approaching
          </div>
        )}
      </div>
    </div>
  );
};

export default RiskIndicators;
```

---

## Module 10: CSS Styling

### **File:** `webui/frontend/src/components/zero_dte/ZeroDTE.css`

```css
/* Zero DTE Bot Styling */

.zero-dte-dashboard {
  padding: 20px;
  max-width: 1600px;
  margin: 0 auto;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.dashboard-header h1 {
  margin: 0;
  font-size: 28px;
  color: #333;
}

.status-badge {
  font-size: 18px;
  font-weight: bold;
}

.badge-active {
  color: #00cc00;
}

.badge-inactive {
  color: #999;
}

/* Grid Layout */
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 20px;
}

.grid-item {
  min-height: 200px;
}

.grid-item.full-width {
  grid-column: 1 / -1;
}

/* Card Styling */
.card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.card h2, .card h3 {
  margin-top: 0;
  margin-bottom: 15px;
  color: #333;
}

/* Control Panel */
.control-panel {
  text-align: center;
}

.control-buttons {
  margin: 20px 0;
}

.btn {
  padding: 12px 24px;
  font-size: 16px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-large {
  padding: 16px 32px;
  font-size: 18px;
  font-weight: bold;
}

.btn-success {
  background: #00cc44;
  color: white;
}

.btn-success:hover {
  background: #00aa33;
}

.btn-danger {
  background: #ff4444;
  color: white;
}

.btn-danger:hover {
  background: #cc0000;
}

.btn-secondary {
  background: #888;
  color: white;
}

/* Premium Gauge */
.premium-gauge {
  padding: 20px;
}

.gauge-container {
  margin: 20px 0;
}

.gauge-row {
  display: flex;
  align-items: center;
  margin: 10px 0;
}

.gauge-label {
  width: 100px;
  font-weight: bold;
}

.gauge-bar-container {
  flex: 1;
  height: 40px;
  background: #f0f0f0;
  border-radius: 4px;
  overflow: hidden;
}

.gauge-bar {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding-right: 10px;
  transition: width 0.5s ease;
}

.gauge-bar-ce {
  background: linear-gradient(to right, #4a90e2, #6bb6ff);
}

.gauge-bar-pe {
  background: linear-gradient(to right, #e94b3c, #ff6b6b);
}

.gauge-value {
  color: white;
  font-weight: bold;
  font-size: 14px;
}

.imbalance-indicator {
  margin-top: 15px;
  padding: 10px;
  border-radius: 4px;
  text-align: center;
  font-size: 16px;
  font-weight: bold;
}

.imbalance-green {
  background: #d4edda;
  color: #155724;
}

.imbalance-yellow {
  background: #fff3cd;
  color: #856404;
}

.imbalance-red {
  background: #f8d7da;
  color: #721c24;
}

/* Countdown Timer */
.countdown-timer {
  text-align: center;
}

.countdown-display {
  display: flex;
  justify-content: center;
  align-items: center;
  margin: 20px 0;
  font-family: monospace;
}

.time-segment {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin: 0 10px;
}

.time-value {
  font-size: 48px;
  font-weight: bold;
  color: #333;
}

.time-label {
  font-size: 12px;
  color: #666;
  text-transform: uppercase;
}

.time-separator {
  font-size: 48px;
  font-weight: bold;
  color: #333;
}

.countdown-warning {
  background: #fff3cd;
  border-left: 4px solid #ffc107;
}

.countdown-critical {
  background: #f8d7da;
  border-left: 4px solid #dc3545;
}

.countdown-critical .time-value {
  color: #dc3545;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* Positions Table */
.positions-table table {
  width: 100%;
  border-collapse: collapse;
}

.positions-table th,
.positions-table td {
  padding: 10px;
  text-align: left;
  border-bottom: 1px solid #ddd;
}

.positions-table th {
  background: #f5f5f5;
  font-weight: bold;
}

.leg-badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-weight: bold;
  font-size: 12px;
}

.leg-ce {
  background: #4a90e2;
  color: white;
}

.leg-pe {
  background: #e94b3c;
  color: white;
}

.pnl-positive {
  color: #00cc00;
  font-weight: bold;
}

.pnl-negative {
  color: #cc0000;
  font-weight: bold;
}

/* Greeks Display */
.greeks-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
  margin-top: 20px;
}

.greek-item {
  text-align: center;
}

.greek-gauge {
  width: 100px;
  height: 100px;
  margin: 0 auto 10px;
}

.greek-value {
  font-size: 32px;
  font-weight: bold;
  color: #333;
}

.greek-label {
  margin-top: 10px;
}

.greek-name {
  display: block;
  font-weight: bold;
  color: #666;
}

.greek-limit {
  display: block;
  font-size: 12px;
  color: #999;
}

/* Rebalancing History */
.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.history-filters button {
  margin-left: 10px;
  padding: 6px 12px;
  border: 1px solid #ddd;
  background: white;
  border-radius: 4px;
  cursor: pointer;
}

.history-filters button.active {
  background: #4a90e2;
  color: white;
  border-color: #4a90e2;
}

.history-table-container {
  overflow-x: auto;
}

.table-compact {
  font-size: 14px;
}

.table-compact td {
  padding: 8px;
}

.type-badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.badge-success {
  background: #d4edda;
  color: #155724;
}

.badge-warning {
  background: #fff3cd;
  color: #856404;
}

.badge-error {
  background: #f8d7da;
  color: #721c24;
}

/* Risk Indicators */
.progress-bar-container {
  width: 100%;
  height: 30px;
  background: #f0f0f0;
  border-radius: 4px;
  overflow: hidden;
  margin: 10px 0;
}

.progress-bar {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: bold;
  transition: width 0.5s ease;
}

.progress-green {
  background: #00cc44;
}

.progress-yellow {
  background: #ffcc00;
}

.progress-orange {
  background: #ff9900;
}

.progress-red {
  background: #ff4444;
}

.guardian-status {
  text-align: center;
  margin: 15px 0;
  font-size: 24px;
  font-weight: bold;
}

.status-go {
  color: #00cc44;
}

.status-stop {
  color: #ff4444;
}

/* Alerts */
.alert {
  padding: 12px;
  border-radius: 4px;
  margin: 10px 0;
}

.alert-success {
  background: #d4edda;
  color: #155724;
  border-left: 4px solid #28a745;
}

.alert-warning {
  background: #fff3cd;
  color: #856404;
  border-left: 4px solid #ffc107;
}

.alert-error {
  background: #f8d7da;
  color: #721c24;
  border-left: 4px solid #dc3545;
}

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: white;
  padding: 30px;
  border-radius: 8px;
  max-width: 500px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
}

.modal h3 {
  margin-top: 0;
}

.form-group {
  margin: 15px 0;
}

.form-group label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.modal-buttons {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}
```

---

**Continue to:** [ZERO_DTE_PHASE4_TESTING.md](ZERO_DTE_PHASE4_TESTING.md) for testing and deployment.
