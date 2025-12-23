import React, { useState, useEffect, useCallback } from 'react';
import apiClient from '../utils/apiClient';
import { Terminal, Activity, Cpu, HardDrive, RefreshCw, PlayCircle, StopCircle, RotateCw, FileText, Trash2, CheckCircle, XCircle, AlertCircle, Shield, Heart, TrendingUp, Info } from 'lucide-react';
import './PM2Panel.css';

const PM2Panel = () => {
  const [pm2Status, setPM2Status] = useState(null);
  const [pm2Enabled, setPM2Enabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedProcess, setSelectedProcess] = useState(null);
  const [showLogs, setShowLogs] = useState(false);
  const [logs, setLogs] = useState({ out: [], err: [] });
  const [logsLoading, setLogsLoading] = useState(false);
  const [actionInProgress, setActionInProgress] = useState(null);
  const [activeTab, setActiveTab] = useState('live'); // 'live', 'demo', or 'all'

  // Fetch PM2 status
  const fetchPM2Status = useCallback(async () => {
    try {
      const [statusData, enabledData] = await Promise.all([
        apiClient.getPM2Status(),
        apiClient.getPM2Enabled()
      ]);
      
      setPM2Status(statusData);
      setPM2Enabled(enabledData.enabled);
      setError(null);
      setLoading(false);
    } catch (err) {
      console.error('Error fetching PM2 status:', err);
      setError(err.message || 'Failed to fetch PM2 status');
      setLoading(false);
    }
  }, []);

  // Auto-refresh every 5 seconds
  useEffect(() => {
    fetchPM2Status();
    const interval = setInterval(fetchPM2Status, 5000);
    return () => clearInterval(interval);
  }, [fetchPM2Status]);

  // Process control handlers
  const handleStart = async (name) => {
    setActionInProgress(`start-${name}`);
    try {
      const result = await apiClient.startPM2Process(name);
      if (result.success) {
        showNotification(`${name} started successfully`, 'success');
        fetchPM2Status();
      } else {
        showNotification(result.message || 'Failed to start process', 'error');
      }
    } catch (err) {
      showNotification(err.message || 'Error starting process', 'error');
    }
    setActionInProgress(null);
  };

  const handleStop = async (name) => {
    setActionInProgress(`stop-${name}`);
    try {
      const result = await apiClient.stopPM2Process(name);
      if (result.success) {
        showNotification(`${name} stopped successfully (graceful shutdown)`, 'success');
        fetchPM2Status();
      } else {
        showNotification(result.message || 'Failed to stop process', 'error');
      }
    } catch (err) {
      showNotification(err.message || 'Error stopping process', 'error');
    }
    setActionInProgress(null);
  };

  const handleRestart = async (name) => {
    setActionInProgress(`restart-${name}`);
    try {
      const result = await apiClient.restartPM2Process(name);
      if (result.success) {
        showNotification(`${name} restarted successfully`, 'success');
        fetchPM2Status();
      } else {
        showNotification(result.message || 'Failed to restart process', 'error');
      }
    } catch (err) {
      showNotification(err.message || 'Error restarting process', 'error');
    }
    setActionInProgress(null);
  };

  const handleViewLogs = async (process) => {
    setSelectedProcess(process);
    setShowLogs(true);
    setLogsLoading(true);
    
    try {
      const result = await apiClient.getPM2Logs(process.name, 100, 'all');
      if (result.success) {
        setLogs(result.logs);
      } else {
        setLogs({ out: [], err: ['Failed to load logs'] });
      }
    } catch (err) {
      setLogs({ out: [], err: [`Error: ${err.message}`] });
    }
    setLogsLoading(false);
  };

  const handleFlushLogs = async () => {
    if (!window.confirm('Are you sure you want to clear all PM2 logs?')) return;
    
    setActionInProgress('flush-logs');
    try {
      const result = await apiClient.flushPM2Logs();
      if (result.success) {
        showNotification('All PM2 logs cleared', 'success');
      } else {
        showNotification(result.message || 'Failed to flush logs', 'error');
      }
    } catch (err) {
      showNotification(err.message || 'Error flushing logs', 'error');
    }
    setActionInProgress(null);
  };

  const showNotification = (message, type) => {
    // You can integrate with your notification system here
    console.log(`[${type.toUpperCase()}] ${message}`);
    // Or use alert for now
    if (type === 'error') {
      alert(`Error: ${message}`);
    }
  };

  const formatUptime = (milliseconds) => {
    if (!milliseconds) return 'N/A';
    const now = Date.now();
    const uptime = now - milliseconds;
    const seconds = Math.floor(uptime / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) return `${days}d ${hours % 24}h`;
    if (hours > 0) return `${hours}h ${minutes % 60}m`;
    if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
    return `${seconds}s`;
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'online':
        return <CheckCircle className="status-icon online" />;
      case 'stopped':
        return <XCircle className="status-icon stopped" />;
      case 'errored':
      case 'stopping':
        return <AlertCircle className="status-icon errored" />;
      default:
        return <AlertCircle className="status-icon unknown" />;
    }
  };

  const getProcessIcon = (name) => {
    if (name.includes('gridbot')) return <TrendingUp size={20} />;
    if (name.includes('guardian')) return <Shield size={20} />;
    if (name.includes('heartbeat')) return <Heart size={20} />;
    return <Terminal size={20} />;
  };

  const getProcessDisplayName = (name) => {
    const displayNames = {
      'gridbot-live': 'Trading Bot (Real Money)',
      'gridbot-demo': 'Trading Bot (Demo)',
      'guardian-live': 'Guardian Monitor (Live)',
      'guardian-demo': 'Guardian Monitor (Demo)',
      'heartbeat-monitor': 'Heartbeat Monitor'
    };
    return displayNames[name] || name;
  };

  // Filter processes based on active tab
  const getFilteredProcesses = () => {
    if (!pm2Status?.processes) return [];
    
    switch (activeTab) {
      case 'live':
        // Show gridbot-live, guardian-live, and heartbeat-monitor
        return pm2Status.processes.filter(p => 
          p.name === 'gridbot-live' || 
          p.name === 'guardian-live' || 
          p.name === 'heartbeat-monitor'
        );
      case 'demo':
        // Show gridbot-demo, guardian-demo, and heartbeat-monitor
        return pm2Status.processes.filter(p => 
          p.name === 'gridbot-demo' || 
          p.name === 'guardian-demo' || 
          p.name === 'heartbeat-monitor'
        );
      case 'all':
      default:
        return pm2Status.processes;
    }
  };

  const filteredProcesses = getFilteredProcesses();

  // Render PM2 not enabled state
  if (!pm2Enabled && !loading) {
    return (
      <div className="pm2-panel">
        <div className="pm2-not-enabled">
          <AlertCircle size={48} className="warning-icon" />
          <h3>PM2 Integration Not Enabled</h3>
          <p>PM2 process manager is not currently enabled for this system.</p>
          <div className="enable-instructions">
            <h4>To enable PM2:</h4>
            <ol>
              <li>Run: <code>./toggle_pm2.sh enable</code></li>
              <li>Restart WebUI backend: <code>launchctl restart com.gridbot.webui.enhanced</code></li>
              <li>Refresh this page</li>
            </ol>
          </div>
          <div className="pm2-benefits">
            <h4>PM2 Benefits:</h4>
            <ul>
              <li>✅ Auto-restart on crash</li>
              <li>✅ Graceful shutdown (30s timeout to cancel orders)</li>
              <li>✅ Real-time CPU and memory monitoring</li>
              <li>✅ Process logs management</li>
              <li>✅ Production-ready reliability</li>
            </ul>
          </div>
        </div>
      </div>
    );
  }

  // Render loading state
  if (loading) {
    return (
      <div className="pm2-panel">
        <div className="pm2-loading">
          <RefreshCw className="spin" size={32} />
          <p>Loading PM2 status...</p>
        </div>
      </div>
    );
  }

  // Render error state
  if (error) {
    return (
      <div className="pm2-panel">
        <div className="pm2-error">
          <XCircle size={48} className="error-icon" />
          <h3>Error Loading PM2 Status</h3>
          <p>{error}</p>
          <button onClick={fetchPM2Status} className="retry-button">
            <RefreshCw size={16} /> Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="pm2-panel">
      {/* Header */}
      <div className="pm2-header">
        <div className="pm2-title">
          <Terminal size={24} />
          <h2>PM2 Process Manager</h2>
        </div>
        <button 
          onClick={fetchPM2Status} 
          className="refresh-button"
          disabled={loading}
        >
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Tab Navigation */}
      <div className="pm2-tabs">
        <button
          className={`tab-button ${activeTab === 'live' ? 'active' : ''}`}
          onClick={() => setActiveTab('live')}
        >
          <Activity size={16} />
          Live Trading
          <span className="tab-badge">
            {pm2Status?.processes?.filter(p => 
              p.name === 'gridbot-live' || 
              p.name === 'guardian-live' || 
              p.name === 'heartbeat-monitor'
            ).length || 0}
          </span>
        </button>
        <button
          className={`tab-button ${activeTab === 'demo' ? 'active' : ''}`}
          onClick={() => setActiveTab('demo')}
        >
          <Activity size={16} />
          Demo Trading
          <span className="tab-badge">
            {pm2Status?.processes?.filter(p => 
              p.name === 'gridbot-demo' || 
              p.name === 'guardian-demo' || 
              p.name === 'heartbeat-monitor'
            ).length || 0}
          </span>
        </button>
        <button
          className={`tab-button ${activeTab === 'all' ? 'active' : ''}`}
          onClick={() => setActiveTab('all')}
        >
          <Terminal size={16} />
          All Processes
          <span className="tab-badge">
            {pm2Status?.total || 0}
          </span>
        </button>
      </div>

      {/* Summary Statistics */}
      <div className="pm2-summary">
        <div className="summary-card">
          <div className="summary-icon online">
            <CheckCircle size={20} />
          </div>
          <div className="summary-content">
            <div className="summary-label">Online</div>
            <div className="summary-value">{pm2Status?.online || 0}</div>
          </div>
        </div>

        <div className="summary-card">
          <div className="summary-icon stopped">
            <XCircle size={20} />
          </div>
          <div className="summary-content">
            <div className="summary-label">Stopped</div>
            <div className="summary-value">{pm2Status?.stopped || 0}</div>
          </div>
        </div>

        <div className="summary-card">
          <div className="summary-icon errored">
            <AlertCircle size={20} />
          </div>
          <div className="summary-content">
            <div className="summary-label">Errored</div>
            <div className="summary-value">{pm2Status?.errored || 0}</div>
          </div>
        </div>

        <div className="summary-card">
          <div className="summary-icon cpu">
            <Cpu size={20} />
          </div>
          <div className="summary-content">
            <div className="summary-label">Total CPU</div>
            <div className="summary-value">{pm2Status?.summary?.total_cpu?.toFixed(1) || 0}%</div>
          </div>
        </div>

        <div className="summary-card">
          <div className="summary-icon memory">
            <HardDrive size={20} />
          </div>
          <div className="summary-content">
            <div className="summary-label">Total Memory</div>
            <div className="summary-value">{pm2Status?.summary?.total_memory?.toFixed(1) || 0} MB</div>
          </div>
        </div>

        <div className="summary-card">
          <div className="summary-icon restarts">
            <RotateCw size={20} />
          </div>
          <div className="summary-content">
            <div className="summary-label">Total Restarts</div>
            <div className="summary-value">{pm2Status?.summary?.total_restarts || 0}</div>
          </div>
        </div>
      </div>

      {/* Process List */}
      <div className="pm2-processes">
        {filteredProcesses.length === 0 ? (
          <div className="no-processes">
            <AlertCircle size={48} />
            <h3>No Processes Found</h3>
            <p>
              {activeTab === 'live' && 'No live trading processes are currently running.'}
              {activeTab === 'demo' && 'No demo trading processes are currently running.'}
              {activeTab === 'all' && 'No PM2 processes found.'}
            </p>
          </div>
        ) : (
          filteredProcesses.map((process) => (
          <div key={process.name} className={`process-card ${process.status}`}>
            <div className="process-header">
              <div className="process-name-section">
                {getProcessIcon(process.name)}
                <div className="process-name-details">
                  <h3>{getProcessDisplayName(process.name)}</h3>
                  <span className="process-id">{process.name}</span>
                </div>
              </div>
              <div className="process-status">
                {getStatusIcon(process.status)}
                <span className={`status-text ${process.status}`}>
                  {process.status.toUpperCase()}
                </span>
              </div>
            </div>

            <div className="process-stats">
              <div className="stat">
                <span className="stat-label">PID:</span>
                <span className="stat-value">{process.pid || 'N/A'}</span>
              </div>
              <div className="stat">
                <span className="stat-label">CPU:</span>
                <span className="stat-value">{process.cpu?.toFixed(1) || 0}%</span>
              </div>
              <div className="stat">
                <span className="stat-label">Memory:</span>
                <span className="stat-value">{process.memory?.toFixed(1) || 0} MB</span>
              </div>
              <div className="stat">
                <span className="stat-label">Uptime:</span>
                <span className="stat-value">{formatUptime(process.uptime)}</span>
              </div>
              <div className="stat">
                <span className="stat-label">Restarts:</span>
                <span className={`stat-value ${process.restarts > 0 ? 'has-restarts' : ''}`}>
                  {process.restarts}
                </span>
              </div>
            </div>

            {/* Guardian runs via LaunchAgent - show status only, no controls */}
            {process.name.includes('guardian') ? (
              <div className="process-info-message">
                <Info size={16} />
                <span>Guardian runs automatically via LaunchAgent (always-on protection)</span>
              </div>
            ) : (
              <div className="process-actions">
                <button
                  onClick={() => handleStart(process.name)}
                  disabled={process.status === 'online' || actionInProgress === `start-${process.name}`}
                  className="action-button start"
                  title="Start process"
                >
                  <PlayCircle size={16} />
                  {actionInProgress === `start-${process.name}` ? 'Starting...' : 'Start'}
                </button>

                <button
                  onClick={() => handleStop(process.name)}
                  disabled={process.status !== 'online' || actionInProgress === `stop-${process.name}`}
                  className="action-button stop"
                  title="Stop process (graceful shutdown)"
                >
                  <StopCircle size={16} />
                  {actionInProgress === `stop-${process.name}` ? 'Stopping...' : 'Stop'}
                </button>

                <button
                  onClick={() => handleRestart(process.name)}
                  disabled={actionInProgress === `restart-${process.name}`}
                  className="action-button restart"
                  title="Restart process"
                >
                  <RotateCw size={16} />
                  {actionInProgress === `restart-${process.name}` ? 'Restarting...' : 'Restart'}
                </button>

                <button
                  onClick={() => handleViewLogs(process)}
                  className="action-button logs"
                  title="View process logs"
                >
                  <FileText size={16} />
                  Logs
                </button>
              </div>
            )}
          </div>
        ))
        )}
      </div>

      {/* Quick Control Actions */}
      <div className="pm2-bulk-controls">
        <h3>Quick Controls</h3>
        <div className="bulk-buttons">
          <button
            onClick={() => handleStart('gridbot-live')}
            disabled={actionInProgress === 'start-gridbot-live' || pm2Status?.processes?.find(p => p.name === 'gridbot-live')?.status === 'online'}
            className="bulk-button start"
          >
            <PlayCircle size={16} />
            {actionInProgress === 'start-gridbot-live' ? 'Starting...' : 'Start Trading Bot'}
          </button>

          <button
            onClick={() => handleStop('gridbot-live')}
            disabled={actionInProgress === 'stop-gridbot-live' || pm2Status?.processes?.find(p => p.name === 'gridbot-live')?.status !== 'online'}
            className="bulk-button stop"
          >
            <StopCircle size={16} />
            {actionInProgress === 'stop-gridbot-live' ? 'Stopping...' : 'Stop Trading Bot'}
          </button>

          <button
            onClick={() => handleRestart('heartbeat-monitor')}
            disabled={actionInProgress === 'restart-heartbeat-monitor'}
            className="bulk-button restart"
          >
            <RotateCw size={16} />
            {actionInProgress === 'restart-heartbeat-monitor' ? 'Restarting...' : 'Restart Heartbeat'}
          </button>

          <button
            onClick={handleFlushLogs}
            disabled={actionInProgress === 'flush-logs'}
            className="bulk-button flush"
          >
            <Trash2 size={16} />
            {actionInProgress === 'flush-logs' ? 'Flushing...' : 'Flush Logs'}
          </button>
        </div>
      </div>

      {/* Logs Modal */}
      {showLogs && (
        <div className="logs-modal-overlay" onClick={() => setShowLogs(false)}>
          <div className="logs-modal" onClick={(e) => e.stopPropagation()}>
            <div className="logs-modal-header">
              <h3>
                <FileText size={20} />
                Logs: {selectedProcess?.name}
              </h3>
              <button onClick={() => setShowLogs(false)} className="close-button">
                ×
              </button>
            </div>

            <div className="logs-modal-content">
              {logsLoading ? (
                <div className="logs-loading">
                  <RefreshCw className="spin" size={24} />
                  <p>Loading logs...</p>
                </div>
              ) : (
                <>
                  <div className="logs-section">
                    <h4>Standard Output</h4>
                    <div className="logs-output">
                      {logs.out && logs.out.length > 0 ? (
                        logs.out.map((line, idx) => (
                          <div key={idx} className="log-line">{line}</div>
                        ))
                      ) : (
                        <div className="no-logs">No output logs</div>
                      )}
                    </div>
                  </div>

                  <div className="logs-section">
                    <h4>Error Output</h4>
                    <div className="logs-output error">
                      {logs.err && logs.err.length > 0 ? (
                        logs.err.map((line, idx) => (
                          <div key={idx} className="log-line">{line}</div>
                        ))
                      ) : (
                        <div className="no-logs">No error logs</div>
                      )}
                    </div>
                  </div>
                </>
              )}
            </div>

            <div className="logs-modal-footer">
              <button onClick={() => handleViewLogs(selectedProcess)} className="reload-logs-button">
                <RefreshCw size={16} />
                Reload Logs
              </button>
              <button onClick={() => setShowLogs(false)} className="close-logs-button">
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PM2Panel;
