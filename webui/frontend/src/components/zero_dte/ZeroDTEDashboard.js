/**
 * Zero DTE Dashboard - Main Container
 * 
 * Autonomous 0DTE strangle strategy dashboard.
 * After start, bot manages everything. Only manual action: stop/restart.
 */
import React, { useState, useEffect, useCallback } from 'react';
import ControlPanel from './ControlPanel';
import PremiumGauge from './PremiumGauge';
import PositionsTable from './PositionsTable';
import CountdownTimer from './CountdownTimer';
import PnLDisplay from './PnLDisplay';
import RebalanceHistory from './RebalanceHistory';
import './ZeroDTE.css';

const ZeroDTEDashboard = () => {
  // State
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  // Fetch status from API
  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch('/api/zero-dte/status');
      const data = await response.json();
      
      if (data.success) {
        setStatus(data);
        setError(null);
      } else {
        setError(data.error || 'Failed to fetch status');
      }
      setLastUpdate(new Date());
    } catch (err) {
      setError('Connection error: ' + err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Poll status every 5 seconds when active
  useEffect(() => {
    fetchStatus();
    
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  // Handle session start
  const handleStart = async (config) => {
    try {
      setLoading(true);
      const response = await fetch('/api/zero-dte/session/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          underlying: config.underlying,
          expiry_date: config.expiry,
          initial_lots: config.initial_lots,
          target_premium_min: config.target_premium_min,
          target_premium_max: config.target_premium_max,
          stop_loss: config.stop_loss,
          rebalance_threshold: config.rebalance_threshold
        })
      });
      
      const data = await response.json();
      
      if (data.success) {
        await fetchStatus();
      } else {
        setError(data.error || 'Failed to start session');
      }
    } catch (err) {
      setError('Start error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  // Handle session stop
  const handleStop = async (reason = 'manual') => {
    if (!window.confirm('Are you sure you want to stop the session? All positions will be closed.')) {
      return;
    }
    
    try {
      setLoading(true);
      const response = await fetch('/api/zero-dte/session/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason })
      });
      
      const data = await response.json();
      
      if (data.success) {
        await fetchStatus();
        alert(`Session closed. Final P&L: ₹${data.final_pnl?.toFixed(2) || '0.00'}`);
      } else {
        setError(data.error || 'Failed to stop session');
      }
    } catch (err) {
      setError('Stop error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const isActive = status?.is_active;

  return (
    <div className="zero-dte-dashboard">
      {/* Header */}
      <div className="dashboard-header">
        <div className="header-left">
          <h1>
            <span style={{ marginRight: '10px' }}>⚡</span>
            0DTE Strategy
          </h1>
          <span className={`status-badge ${isActive ? 'badge-active' : 'badge-inactive'}`}>
            {isActive ? '● LIVE' : '○ INACTIVE'}
          </span>
        </div>
        <div className="header-right">
          {lastUpdate && (
            <span className="last-update">
              Updated: {lastUpdate.toLocaleTimeString()}
            </span>
          )}
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="alert alert-error">
          ⚠️ {error}
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      {/* Main Content */}
      {loading && !status ? (
        <div className="loading-spinner">Loading...</div>
      ) : (
        <div className="dashboard-grid">
          {/* Control Panel */}
          <div className="grid-item">
            <ControlPanel
              isActive={isActive}
              onStart={handleStart}
              onStop={handleStop}
              loading={loading}
              sessionId={status?.session_id}
              currentExpiry={status?.expiry_date || status?.session?.expiry_date}
            />
          </div>

          {/* Countdown Timer */}
          <div className="grid-item">
            <CountdownTimer
              isActive={isActive}
              timeToExpiryMinutes={status?.time?.time_to_expiry_minutes}
              settlementTime={status?.time?.settlement_time || '17:30'}
            />
          </div>

          {/* Premium Gauge */}
          <div className="grid-item">
            <PremiumGauge
              ceTotal={status?.premium_balance?.ce_total || 0}
              peTotal={status?.premium_balance?.pe_total || 0}
              imbalancePct={status?.premium_balance?.imbalance_pct || 0}
              isBalanced={status?.premium_balance?.is_balanced}
              threshold={20}
            />
          </div>

          {/* P&L Display */}
          <div className="grid-item">
            <PnLDisplay
              status={status}
              positions={status?.positions}
            />
          </div>

          {/* Positions Table */}
          <div className="grid-item full-width">
            <PositionsTable
              positions={status?.positions}
              underlying={status?.underlying}
              spotPrice={status?.spot_price}
            />
          </div>

          {/* Rebalance History */}
          <div className="grid-item full-width">
            <RebalanceHistory
              sessionId={status?.session_id}
              isActive={isActive}
            />
          </div>
        </div>
      )}

      {/* Footer Stats */}
      {isActive && status?.stats && (
        <div className="dashboard-footer">
          <span>Rebalances: {status.stats.total_rebalances || 0}</span>
          <span>Rollovers: {status.stats.total_rollovers || 0}</span>
          <span>Session: {status.session_id?.slice(-8)}</span>
        </div>
      )}
    </div>
  );
};

export default ZeroDTEDashboard;
