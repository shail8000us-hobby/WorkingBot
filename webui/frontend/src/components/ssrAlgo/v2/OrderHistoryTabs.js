/**
 * Order History Tabs V2
 * 
 * Three tabs: Pending & Running, History, Clear History
 * With cyan-themed active states and proper table/empty states.
 * 
 * Part of SSR Algo V2 Dashboard
 * Created: February 3, 2026
 */

import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { 
  Clock, 
  History, 
  Trash2, 
  AlertCircle,
  CheckCircle,
  ExternalLink,
  Loader2
} from 'lucide-react';

const OrderHistoryTabs = ({
  pendingSessions = [],
  historySessions = [],
  onViewDetails,
  onClearHistory,
  onClearPending,
  loading = false,
}) => {
  const [activeTab, setActiveTab] = useState('pending');
  const [confirmClear, setConfirmClear] = useState(false);

  const tabs = [
    { 
      id: 'pending', 
      label: 'Pending & Running', 
      count: pendingSessions.length,
      icon: Clock 
    },
    { 
      id: 'history', 
      label: 'History', 
      count: historySessions.length,
      icon: History 
    },
    { 
      id: 'clear', 
      label: 'Clear History', 
      count: historySessions.length,
      icon: Trash2 
    },
  ];

  // Format timestamp
  const formatTime = (timestamp) => {
    if (!timestamp) return '-';
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit',
      hour12: false 
    });
  };

  // Format date
  const formatDate = (timestamp) => {
    if (!timestamp) return '-';
    const date = new Date(timestamp);
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric' 
    });
  };

  // Get status badge
  const getStatusBadge = (status) => {
    const statusConfig = {
      IDLE: { label: 'Ready', color: 'slate' },
      SELECTING_STRIKES: { label: 'Selecting', color: 'blue' },
      EXECUTING_AUTO_LOOP: { label: 'Executing', color: 'yellow' },
      MONITORING: { label: 'Monitoring', color: 'green' },
      PAUSED: { label: 'Paused', color: 'orange' },
      STOPPED: { label: 'Completed', color: 'green' },
    };
    
    const config = statusConfig[status] || { label: status, color: 'slate' };
    const colorClasses = {
      slate: 'bg-slate-500/20 text-slate-400',
      blue: 'bg-blue-500/20 text-blue-400',
      yellow: 'bg-yellow-500/20 text-yellow-400',
      green: 'bg-green-500/20 text-green-400',
      orange: 'bg-orange-500/20 text-orange-400',
    };
    
    return (
      <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${colorClasses[config.color]}`}>
        {config.label}
      </span>
    );
  };

  return (
    <div className="rounded-3xl bg-slate-900/50 border border-slate-700/50 backdrop-blur-sm overflow-hidden">
      {/* Tab Headers */}
      <div className="flex border-b border-slate-700/50">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          
          return (
            <button
              key={tab.id}
              onClick={() => {
                setActiveTab(tab.id);
                setConfirmClear(false);
              }}
              className={`
                flex-1 flex items-center justify-center gap-2 px-4 py-3 
                text-sm font-medium transition-colors
                ${isActive 
                  ? 'text-cyan-400 bg-cyan-500/10 border-b-2 border-cyan-400' 
                  : 'text-slate-400 hover:text-slate-300 hover:bg-slate-800/50'
                }
              `}
            >
              <Icon className="w-4 h-4" />
              <span>{tab.label}</span>
              <span className={`
                px-1.5 py-0.5 rounded text-xs
                ${isActive ? 'bg-cyan-500/20 text-cyan-400' : 'bg-slate-700/50 text-slate-500'}
              `}>
                {tab.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div className="p-4">
        {/* Pending & Running Tab */}
        {activeTab === 'pending' && (
          <>
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 text-cyan-400 animate-spin" />
              </div>
            ) : pendingSessions.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-slate-500">
                <Clock className="w-12 h-12 mb-2 opacity-50" />
                <p className="text-sm">No pending sessions</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800/30">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-medium text-slate-400">Time</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-slate-400">Strategy</th>
                      <th className="px-3 py-2 text-center text-xs font-medium text-slate-400">Underlying</th>
                      <th className="px-3 py-2 text-center text-xs font-medium text-slate-400">Expiry</th>
                      <th className="px-3 py-2 text-center text-xs font-medium text-slate-400">Legs</th>
                      <th className="px-3 py-2 text-center text-xs font-medium text-slate-400">Status</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-slate-400">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-700/30">
                    {pendingSessions.map((session) => (
                      <tr key={session.session_id} className="hover:bg-slate-800/30">
                        <td className="px-3 py-2.5 text-slate-300">
                          <div className="flex flex-col">
                            <span>{formatTime(session.created_at)}</span>
                            <span className="text-xs text-slate-500">{formatDate(session.created_at)}</span>
                          </div>
                        </td>
                        <td className="px-3 py-2.5">
                          <span className="text-slate-300 font-medium">SSR Algo</span>
                        </td>
                        <td className="px-3 py-2.5 text-center">
                          <span className="px-2 py-0.5 bg-orange-500/20 text-orange-400 rounded text-xs font-medium">
                            {session.underlying || 'BTC'}
                          </span>
                        </td>
                        <td className="px-3 py-2.5 text-center text-slate-300">
                          {session.expiry?.substring(0, 5) || '-'}
                        </td>
                        <td className="px-3 py-2.5 text-center text-slate-300">
                          {(session.positions?.length || 0) * 8 || 0}
                        </td>
                        <td className="px-3 py-2.5 text-center">
                          {getStatusBadge(session.status)}
                        </td>
                        <td className="px-3 py-2.5 text-right">
                          <button
                            onClick={() => onViewDetails?.(session)}
                            className="text-cyan-400 hover:text-cyan-300 text-xs flex items-center gap-1 ml-auto"
                          >
                            View Details
                            <ExternalLink className="w-3 h-3" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}

        {/* History Tab */}
        {activeTab === 'history' && (
          <>
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 text-cyan-400 animate-spin" />
              </div>
            ) : historySessions.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-slate-500">
                <History className="w-12 h-12 mb-2 opacity-50" />
                <p className="text-sm">No history yet</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800/30">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-medium text-slate-400">Time</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-slate-400">Strategy</th>
                      <th className="px-3 py-2 text-center text-xs font-medium text-slate-400">Underlying</th>
                      <th className="px-3 py-2 text-center text-xs font-medium text-slate-400">Expiry</th>
                      <th className="px-3 py-2 text-center text-xs font-medium text-slate-400">Legs</th>
                      <th className="px-3 py-2 text-center text-xs font-medium text-slate-400">Status</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-slate-400">P&L</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-slate-400">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-700/30">
                    {historySessions.map((session) => {
                      const pnl = session.total_pnl || session.realized_pnl || 0;
                      return (
                        <tr key={session.session_id} className="hover:bg-slate-800/30">
                          <td className="px-3 py-2.5 text-slate-300">
                            <div className="flex flex-col">
                              <span>{formatTime(session.stopped_at || session.created_at)}</span>
                              <span className="text-xs text-slate-500">{formatDate(session.stopped_at || session.created_at)}</span>
                            </div>
                          </td>
                          <td className="px-3 py-2.5">
                            <span className="text-slate-300 font-medium">SSR Algo</span>
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            <span className="px-2 py-0.5 bg-orange-500/20 text-orange-400 rounded text-xs font-medium">
                              {session.underlying || 'BTC'}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-center text-slate-300">
                            {session.expiry?.substring(0, 5) || '-'}
                          </td>
                          <td className="px-3 py-2.5 text-center text-slate-300">
                            {(session.rounds_completed || 0) * 6 || 0}
                          </td>
                          <td className="px-3 py-2.5 text-center">
                            {getStatusBadge(session.status)}
                          </td>
                          <td className="px-3 py-2.5 text-right">
                            <span className={`font-semibold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                              {pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}
                            </span>
                          </td>
                          <td className="px-3 py-2.5 text-right">
                            <button
                              onClick={() => onViewDetails?.(session)}
                              className="text-cyan-400 hover:text-cyan-300 text-xs flex items-center gap-1 ml-auto"
                            >
                              View Details
                              <ExternalLink className="w-3 h-3" />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}

        {/* Clear History Tab */}
        {activeTab === 'clear' && (
          <div className="flex flex-col items-center justify-center py-8">
            <Trash2 className="w-12 h-12 mb-4 text-red-400 opacity-75" />
            <h3 className="text-lg font-semibold text-white mb-2">Clear History</h3>
            <p className="text-sm text-slate-400 mb-6 text-center max-w-sm">
              This will permanently delete all {historySessions.length} completed sessions from history. This action cannot be undone.
            </p>
            
            {!confirmClear ? (
              <div className="flex gap-3">
                <button
                  onClick={() => setActiveTab('history')}
                  className="px-4 py-2 bg-slate-700/50 hover:bg-slate-700 rounded-lg text-slate-300 text-sm font-medium transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={() => setConfirmClear(true)}
                  disabled={historySessions.length === 0}
                  className="px-4 py-2 bg-red-500/20 hover:bg-red-500/30 border border-red-500/40 rounded-lg text-red-400 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Clear History
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-4">
                <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                  <AlertCircle className="w-5 h-5 text-red-400" />
                  <span className="text-sm text-red-400">Are you sure? This cannot be undone.</span>
                </div>
                <div className="flex gap-3">
                  <button
                    onClick={() => setConfirmClear(false)}
                    className="px-4 py-2 bg-slate-700/50 hover:bg-slate-700 rounded-lg text-slate-300 text-sm font-medium transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => {
                      onClearHistory?.();
                      setConfirmClear(false);
                      setActiveTab('history');
                    }}
                    className="px-4 py-2 bg-red-500 hover:bg-red-600 rounded-lg text-white text-sm font-medium transition-colors flex items-center gap-2"
                  >
                    <Trash2 className="w-4 h-4" />
                    Confirm Clear
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

OrderHistoryTabs.propTypes = {
  pendingSessions: PropTypes.array,
  historySessions: PropTypes.array,
  onViewDetails: PropTypes.func,
  onClearHistory: PropTypes.func,
  onClearPending: PropTypes.func,
  loading: PropTypes.bool,
};

export default OrderHistoryTabs;
