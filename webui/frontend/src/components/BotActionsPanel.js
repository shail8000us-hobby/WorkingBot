import React, { useState, useEffect } from 'react';
import './BotActionsPanel.css';
import { useInstance } from '../context/InstanceContext';

const BotActionsPanel = () => {
  const { selectedInstance, withInstance } = useInstance();
  const [nextActions, setNextActions] = useState([]);
  const [marketState, setMarketState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch next actions from the prediction endpoint (v6.0: instance-aware)
  const fetchNextActions = async () => {
    try {
      setError(null);
      const response = await fetch(withInstance('/api/bot-actions/next'));
      const data = await response.json();

      if (data.success && data.actions) {
        setNextActions(data.actions);
        setMarketState(data.market_state);
      } else {
        setError('Failed to load next actions');
      }
      setLoading(false);
    } catch (err) {
      console.error('Failed to fetch next bot actions:', err);
      setError('Failed to load next actions');
      setLoading(false);
    }
  };

  // Initial fetch and auto-refresh every 15 seconds (v6.0: refetch on instance change)
  useEffect(() => {
    fetchNextActions();
    const interval = setInterval(fetchNextActions, 15000);
    return () => clearInterval(interval);
  }, [selectedInstance]); // Refetch when instance changes

  const getImportanceIcon = (importance) => {
    switch (importance) {
      case 'critical':
        return '🔴';
      case 'high':
        return '�';
      case 'normal':
        return '�';
      default:
        return '⚪';
    }
  };

  const getPriorityBadge = (priority) => {
    const colors = {
      1: 'priority-1',
      2: 'priority-2',
      3: 'priority-3',
    };
    return colors[priority] || 'priority-default';
  };

  if (loading) {
    return (
      <div className="bot-actions-panel">
        <div className="panel-header">
          <h2>🔮 Next Bot Actions</h2>
        </div>
        <div className="loading-state">Loading next actions...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bot-actions-panel">
        <div className="panel-header">
          <h2>🔮 Next Bot Actions</h2>
        </div>
        <div className="error-state">{error}</div>
      </div>
    );
  }

  return (
    <div className="bot-actions-panel">
      <div className="panel-header">
        <h2>🔮 Next Bot Actions</h2>
        <div className="header-controls">
          <button className="refresh-button" onClick={fetchNextActions} title="Refresh predictions">
            🔄 Refresh
          </button>
        </div>
      </div>

      {marketState && (
        <div className="market-state-summary">
          <div className="state-item">
            <span className="label">Current Price</span>
            <span className="value">{marketState.current_price}</span>
          </div>
          <div className="state-item">
            <span className="label">Grid Range</span>
            <span className="value">{marketState.grid_range}</span>
          </div>
          <div className="state-item">
            <span className="label">Positions</span>
            <span className="value">{marketState.open_positions}</span>
          </div>
          <div className="state-item">
            <span className="label">Status</span>
            <span className="value status-badge">{marketState.status}</span>
          </div>
        </div>
      )}

      <div className="next-actions-container">
        {nextActions.length === 0 ? (
          <div className="empty-state">
            <p>No predicted actions available. The bot may be idle or waiting.</p>
          </div>
        ) : (
          nextActions.map((action, index) => (
            <div
              key={index}
              className={`action-card ${getPriorityBadge(action.priority)} importance-${action.importance || 'normal'}`}
            >
              <div className="action-header">
                <span className="priority-badge">Priority {action.priority}</span>
                <span className="action-icon">
                  {getImportanceIcon(action.importance || 'normal')}
                </span>
              </div>

              <div className="action-title">{action.action}</div>

              <div className="action-details">
                {action.reason && (
                  <div className="detail-row">
                    <strong>Reason:</strong> {action.reason}
                  </div>
                )}

                {action.condition && (
                  <div className="detail-row">
                    <strong>Condition:</strong> {action.condition}
                  </div>
                )}

                {action.next_step && (
                  <div className="detail-row">
                    <strong>Next Step:</strong> {action.next_step}
                  </div>
                )}

                {action.eta && (
                  <div className="detail-row eta">
                    <strong>ETA:</strong> {action.eta}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      <div className="panel-footer">
        <span className="info-text">Auto-refreshes every 15 seconds</span>
      </div>
    </div>
  );
};

export default BotActionsPanel;
