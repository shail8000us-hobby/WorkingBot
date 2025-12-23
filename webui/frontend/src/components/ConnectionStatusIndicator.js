/**
 * ConnectionStatusIndicator - Visual indicator for WebSocket connection health
 */

import React, { useState, useEffect } from 'react';
import {
  Box, Chip, Tooltip, IconButton, Collapse, Alert, LinearProgress,
  Typography, Divider
} from '@mui/material';
import {
  SignalWifi4Bar, SignalWifiOff, SignalWifi1Bar, SignalWifi2Bar,
  Refresh, ExpandMore, ExpandLess
} from '@mui/icons-material';

const ConnectionStatusIndicator = ({ connectionManager }) => {
  const [connectionState, setConnectionState] = useState({
    state: 'disconnected',
    connected: false,
    reconnectAttempt: 0,
    lastHeartbeat: null
  });
  const [latency, setLatency] = useState(null);
  const [expanded, setExpanded] = useState(false);
  const [syncStatus, setSyncStatus] = useState({ lastSync: null, error: null });

  useEffect(() => {
    if (!connectionManager) return;

    // Update connection state
    const updateState = () => {
      setConnectionState(connectionManager.getConnectionState());
    };

    const handleConnectionStateChange = () => {
      updateState();
    };

    const handleHeartbeat = (data) => {
      setLatency(data.latency);
      updateState();
    };

    const handleSyncComplete = (data) => {
      setSyncStatus({ lastSync: data.timestamp, error: null });
    };

    const handleSyncError = (data) => {
      setSyncStatus(prev => ({ ...prev, error: data.error }));
    };

    // Register listeners
    connectionManager.on('connection_state_changed', handleConnectionStateChange);
    connectionManager.on('heartbeat', handleHeartbeat);
    connectionManager.on('sync_complete', handleSyncComplete);
    connectionManager.on('sync_error', handleSyncError);

    // Initial state
    updateState();

    // Cleanup
    return () => {
      connectionManager.off('connection_state_changed', handleConnectionStateChange);
      connectionManager.off('heartbeat', handleHeartbeat);
      connectionManager.off('sync_complete', handleSyncComplete);
      connectionManager.off('sync_error', handleSyncError);
    };
  }, [connectionManager]);

  const getStatusColor = () => {
    if (connectionState.state === 'connected' && latency !== null) {
      if (latency < 100) return 'success';
      if (latency < 300) return 'warning';
      return 'error';
    }
    if (connectionState.state === 'connecting') return 'info';
    if (connectionState.state === 'error') return 'error';
    return 'default';
  };

  const getStatusIcon = () => {
    if (connectionState.state === 'connected' && latency !== null) {
      if (latency < 100) return <SignalWifi4Bar />;
      if (latency < 300) return <SignalWifi2Bar />;
      return <SignalWifi1Bar />;
    }
    if (connectionState.state === 'connecting') return <SignalWifi2Bar />;
    return <SignalWifiOff />;
  };

  const getStatusLabel = () => {
    if (connectionState.state === 'connected') {
      return latency !== null ? `${latency}ms` : 'Connected';
    }
    if (connectionState.state === 'connecting') {
      return connectionState.reconnectAttempt > 0 
        ? `Reconnecting (${connectionState.reconnectAttempt})` 
        : 'Connecting...';
    }
    if (connectionState.state === 'error') return 'Error';
    return 'Disconnected';
  };

  const getTimeSinceLastHeartbeat = () => {
    if (!connectionState.lastHeartbeat) return null;
    const seconds = Math.floor((Date.now() - connectionState.lastHeartbeat) / 1000);
    return seconds;
  };

  const handleReconnect = () => {
    if (connectionManager) {
      connectionManager.forceReconnect();
    }
  };

  const timeSinceHeartbeat = getTimeSinceLastHeartbeat();
  const isStale = timeSinceHeartbeat !== null && timeSinceHeartbeat > 10;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Tooltip 
          title={
            <Box>
              <Typography variant="caption" display="block">
                Connection: {connectionState.state}
              </Typography>
              {latency !== null && (
                <Typography variant="caption" display="block">
                  Latency: {latency}ms
                </Typography>
              )}
              {timeSinceHeartbeat !== null && (
                <Typography variant="caption" display="block">
                  Last heartbeat: {timeSinceHeartbeat}s ago
                </Typography>
              )}
              {syncStatus.lastSync && (
                <Typography variant="caption" display="block">
                  Last sync: {new Date(syncStatus.lastSync).toLocaleTimeString()}
                </Typography>
              )}
            </Box>
          }
        >
          <Chip
            icon={getStatusIcon()}
            label={getStatusLabel()}
            color={getStatusColor()}
            size="small"
            sx={{ 
              fontWeight: 'bold',
              cursor: 'pointer'
            }}
            onClick={() => setExpanded(!expanded)}
          />
        </Tooltip>

        {isStale && (
          <Chip
            label="Stale"
            color="warning"
            size="small"
            sx={{ fontWeight: 'bold' }}
          />
        )}

        {connectionState.state !== 'connected' && (
          <Tooltip title="Reconnect">
            <IconButton size="small" onClick={handleReconnect} color="primary">
              <Refresh />
            </IconButton>
          </Tooltip>
        )}

        <IconButton size="small" onClick={() => setExpanded(!expanded)}>
          {expanded ? <ExpandLess /> : <ExpandMore />}
        </IconButton>
      </Box>

      <Collapse in={expanded}>
        <Box sx={{ mt: 1, p: 2, bgcolor: 'background.paper', borderRadius: 1 }}>
          <Typography variant="subtitle2" gutterBottom>
            Connection Details
          </Typography>
          <Divider sx={{ mb: 1 }} />

          {connectionState.state === 'connecting' && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="caption" display="block" gutterBottom>
                Connecting...
              </Typography>
              <LinearProgress />
            </Box>
          )}

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
            <Typography variant="caption">
              <strong>State:</strong> {connectionState.state}
            </Typography>
            <Typography variant="caption">
              <strong>Connected:</strong> {connectionState.connected ? 'Yes' : 'No'}
            </Typography>
            {latency !== null && (
              <Typography variant="caption">
                <strong>Latency:</strong> {latency}ms
              </Typography>
            )}
            {connectionState.reconnectAttempt > 0 && (
              <Typography variant="caption">
                <strong>Reconnect Attempts:</strong> {connectionState.reconnectAttempt}
              </Typography>
            )}
            {timeSinceHeartbeat !== null && (
              <Typography variant="caption">
                <strong>Last Heartbeat:</strong> {timeSinceHeartbeat}s ago
              </Typography>
            )}
            {syncStatus.lastSync && (
              <Typography variant="caption">
                <strong>Last Sync:</strong> {new Date(syncStatus.lastSync).toLocaleTimeString()}
              </Typography>
            )}
          </Box>

          {syncStatus.error && (
            <Alert severity="error" sx={{ mt: 1 }}>
              Sync Error: {syncStatus.error}
            </Alert>
          )}

          {connectionState.state !== 'connected' && (
            <Box sx={{ mt: 2 }}>
              <Alert severity="warning">
                Not connected to server. Attempting to reconnect...
              </Alert>
            </Box>
          )}
        </Box>
      </Collapse>
    </Box>
  );
};

export default ConnectionStatusIndicator;
