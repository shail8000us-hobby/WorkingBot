/**
 * Rebalance History Component
 * 
 * Shows history of rebalancing events.
 * Fetches from /api/zero-dte/rebalances endpoint.
 */
import React, { useState, useEffect, useCallback } from 'react';

const RebalanceHistory = ({ sessionId, isActive }) => {
  const [rebalances, setRebalances] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchRebalances = useCallback(async () => {
    if (!sessionId) return;
    
    setLoading(true);
    try {
      const response = await fetch(`/api/zero-dte/rebalances?session_id=${sessionId}&limit=20`);
      const data = await response.json();
      
      if (data.success) {
        setRebalances(data.rebalances || []);
        setError(null);
      } else {
        setError(data.error || 'Failed to fetch rebalances');
      }
    } catch (err) {
      setError('Network error fetching rebalances');
      console.error('Rebalance fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  // Fetch on mount and when session changes
  useEffect(() => {
    fetchRebalances();
  }, [fetchRebalances]);

  // Refresh periodically when active
  useEffect(() => {
    if (!isActive || !sessionId) return;
    
    const interval = setInterval(fetchRebalances, 30000); // Every 30 seconds
    return () => clearInterval(interval);
  }, [isActive, sessionId, fetchRebalances]);

  const formatTime = (timestamp) => {
    if (!timestamp) return '-';
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-IN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  };

  const formatAction = (action, side) => {
    const actionMap = {
      'ADD': '📈 Added',
      'REDUCE': '📉 Reduced',
      'ROLLOVER': '🔄 Rolled',
    };
    return `${actionMap[action] || action} ${side}`;
  };

  return (
    <div className="rebalance-history card">
      <div className="card-header">
        <h3>Rebalance & Rollover History</h3>
        <button 
          className="refresh-btn"
          onClick={fetchRebalances}
          disabled={loading}
        >
          {loading ? '⏳' : '🔄'} Refresh
        </button>
      </div>

      {error && (
        <div className="error-message">
          ❌ {error}
        </div>
      )}

      {rebalances.length === 0 ? (
        <div className="empty-state">
          <span className="empty-icon">📊</span>
          <span>No rebalances yet</span>
          <span className="empty-hint">
            Rebalances occur when premium imbalance exceeds 20%
          </span>
        </div>
      ) : (
        <div className="rebalance-table-container">
          <table className="rebalance-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Action</th>
                <th>Imbalance</th>
                <th>Lots Δ</th>
                <th>Premium</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {rebalances.map((rb, index) => (
                <tr key={rb.id || index} className={`rebalance-row ${rb.status}`}>
                  <td className="time-col">{formatTime(rb.timestamp)}</td>
                  <td className="action-col">
                    {formatAction(rb.action, rb.side)}
                  </td>
                  <td className="imbalance-col">
                    <span className={`imbalance-value ${rb.imbalance_before > 20 ? 'high' : ''}`}>
                      {rb.imbalance_before?.toFixed(1)}%
                    </span>
                    <span className="imbalance-arrow">→</span>
                    <span className={`imbalance-value ${rb.imbalance_after > 20 ? 'high' : ''}`}>
                      {rb.imbalance_after?.toFixed(1)}%
                    </span>
                  </td>
                  <td className="lots-col">
                    {rb.lots_change > 0 ? '+' : ''}{rb.lots_change}
                  </td>
                  <td className="premium-col">
                    ₹{rb.premium?.toFixed(2) || '-'}
                  </td>
                  <td className="status-col">
                    <span className={`status-badge ${rb.status}`}>
                      {rb.status === 'success' ? '✅' : 
                       rb.status === 'failed' ? '❌' : 
                       rb.status === 'pending' ? '⏳' : '•'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Summary Stats */}
      {rebalances.length > 0 && (
        <div className="rebalance-summary">
          <div className="summary-item">
            <span className="summary-label">Total Rebalances</span>
            <span className="summary-value">{rebalances.length}</span>
          </div>
          <div className="summary-item">
            <span className="summary-label">Successful</span>
            <span className="summary-value success">
              {rebalances.filter(r => r.status === 'success').length}
            </span>
          </div>
          <div className="summary-item">
            <span className="summary-label">Failed</span>
            <span className="summary-value failed">
              {rebalances.filter(r => r.status === 'failed').length}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default RebalanceHistory;
