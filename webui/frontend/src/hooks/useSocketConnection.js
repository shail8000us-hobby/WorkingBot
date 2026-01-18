/**
 * Socket Connection Hook
 *
 * Manages WebSocket connection to backend and handles all real-time events
 */

import { useEffect, useRef } from 'react';
import RobustConnectionManager from '../utils/RobustConnectionManager';
import { transformFlatConfig, buildMetaFromStructured } from '../utils/configHelpers.ts';

export function useSocketConnection({
  config,
  setConfig,
  setConfigMeta,
  setBotStatus,
  setTradingSnapshot,
  setPositionsData,
  setLogs,
  setConnectionState,
  setConnectionQuality,
  setLastUpdated,
  showNotification,
  pushLatencySample,
  debouncedFetchInitialData,
}) {
  const connectionManagerRef = useRef(null);
  const showNotificationRef = useRef(showNotification);
  const pushLatencySampleRef = useRef(pushLatencySample);
  const debouncedFetchInitialDataRef = useRef(debouncedFetchInitialData);

  // Keep refs updated
  useEffect(() => {
    showNotificationRef.current = showNotification;
    pushLatencySampleRef.current = pushLatencySample;
    debouncedFetchInitialDataRef.current = debouncedFetchInitialData;
  }, [showNotification, pushLatencySample, debouncedFetchInitialData]);

  useEffect(() => {
    console.log('🔵 Initializing connection manager');

    const manager = new RobustConnectionManager({
      reconnectDelay: 5000,
      maxReconnectDelay: 30000,
      maxRetries: 3,
      heartbeatInterval: 60000,
      syncInterval: 30000,
      pingTimeout: 15000,
    });

    connectionManagerRef.current = manager;

    // Connection status events
    manager.on('connection', (data) => {
      setConnectionState(data.status);
      if (data.status === 'connected') {
        showNotificationRef.current?.('Connected to GridBot backend', 'success');
        // Only fetch on first connection, not on every reconnect
        if (!config || Object.keys(config).length === 0) {
          debouncedFetchInitialDataRef.current?.();
        }
      } else if (data.status === 'disconnected') {
        showNotificationRef.current?.('Disconnected from server', 'warning');
      } else if (data.status === 'error') {
        showNotificationRef.current?.(`Connection error: ${data.error}`, 'error');
      }
    });

    // State snapshot (full state sync)
    manager.on('state_snapshot', (snapshot) => {
      setLastUpdated(new Date().toISOString());
      if (snapshot.config) {
        const { structured, meta } = transformFlatConfig(snapshot.config);
        setConfig(structured);
        setConfigMeta(meta);
      }
      if (snapshot.bot_status) {
        setBotStatus(snapshot.bot_status);
      }
      if (snapshot.trading_status) {
        setTradingSnapshot(snapshot.trading_status);
      }
    });

    // Incremental updates
    manager.on('positions_update', (data) => {
      setPositionsData(data);
    });

    manager.on('config_updated', (newConfig) => {
      const { structured, meta } = transformFlatConfig(newConfig);
      setConfig(structured);
      setConfigMeta(meta);
    });

    manager.on('bot_status', (status) => {
      setBotStatus(status);
    });

    manager.on('log_entry', (data) => {
      setLogs((prev) => [...prev.slice(-199), data.message]);
    });

    // Error handling
    manager.on('error', (err) => {
      showNotificationRef.current?.(err.message || 'Socket error', 'error');
    });

    manager.on('heartbeat_timeout', () => {
      showNotificationRef.current?.('Connection heartbeat timeout. Reconnecting...', 'warning');
    });

    // Reconnection events
    manager.on('reconnected', () => {
      showNotificationRef.current?.('Reconnected successfully', 'success');
      // Don't auto-fetch on reconnect - rely on WebSocket state updates instead
    });

    manager.on('connection_retry', (data) => {
      if (data.attempt === 1 || data.attempt % 5 === 0) {
        showNotificationRef.current?.(`Reconnecting (${data.attempt}/${data.maxRetries})`, 'info');
      }
    });

    manager.on('connection_failed', () => {
      showNotificationRef.current?.('Connection failed after multiple retries', 'error');
    });

    // Connection quality monitoring
    manager.on('connection_quality', (data) => {
      if (data.quality) {
        setConnectionQuality(data.quality);
      }
      if (typeof data.latency === 'number') {
        pushLatencySampleRef.current?.(data.latency);
      }
    });

    // Network status
    manager.on('network_status', (data) => {
      showNotificationRef.current?.(
        data.online ? 'Network connection restored' : 'Network offline - waiting for reconnection',
        data.online ? 'success' : 'warning'
      );
    });

    manager.connect();

    return () => {
      manager.disconnect();
      connectionManagerRef.current = null;
    };
  }, []); // Empty deps - connection manager should only be created once

  return connectionManagerRef;
}
