import React, { useState, useEffect } from 'react';
import { Box, Paper, Typography, Grid, Chip, LinearProgress, Tooltip } from '@mui/material';
import {
  CheckCircle as HealthyIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  HelpOutline as UnknownIcon,
} from '@mui/icons-material';
import apiClient from '../utils/robustApiClient';
import LatencyChart from './charts/LatencyChart';

/**
 * Health Check Dashboard
 * Monitors all system components in real-time
 */
const HealthCheckDashboard = ({ socket, latencyStats, connectionQuality, botIsRunning }) => {
  const [health, setHealth] = useState({
    backend: { status: 'unknown', message: 'Checking...' },
    websocket: { status: 'unknown', message: 'Checking...' },
    bot: { status: 'unknown', message: 'Checking...' },
    guardian: { status: 'unknown', message: 'Checking...' },
    database: { status: 'unknown', message: 'Checking...' },
    telegram: { status: 'unknown', message: 'Checking...' },
    errorIntelligence: { status: 'unknown', message: 'Checking...' },
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 30000); // Check every 30 seconds
    return () => clearInterval(interval);
  }, [socket]);

  const checkHealth = async () => {
    setLoading(true);
    try {
      // Check backend health
      const backendHealth = await checkBackend();

      // Check WebSocket (now async)
      const websocketHealth = await checkWebSocket();

      // Check bot and guardian status
      const systemHealth = await checkSystemStatus();

      // Check error intelligence
      const errorHealth = await checkErrorIntelligence();

      setHealth({
        backend: backendHealth,
        websocket: websocketHealth,
        bot: systemHealth.bot,
        guardian: systemHealth.guardian,
        database: systemHealth.database,
        telegram: systemHealth.telegram,
        errorIntelligence: errorHealth,
      });
    } catch (error) {
      console.error('Health check failed:', error);
      setHealth((prev) => ({
        ...prev,
        backend: { status: 'error', message: error.message },
      }));
    } finally {
      setLoading(false);
    }
  };

  const checkBackend = async () => {
    try {
      const response = await apiClient.get('/api/health');
      return {
        status: 'healthy',
        message: 'Backend responding normally',
        data: response,
      };
    } catch (error) {
      return {
        status: 'error',
        message: `Backend unreachable: ${error.message}`,
      };
    }
  };

  const checkWebSocket = async () => {
    // Check SocketIO connection first (WebUI)
    const socketIOStatus = !socket ? 'unknown' : socket.connected ? 'healthy' : 'error';
    const socketIOMessage = !socket
      ? 'WebSocket not initialized'
      : socket.connected
        ? 'WebUI Socket connected'
        : 'WebUI Socket disconnected';

    // Try to get production WebSocket health (bot's Delta WebSocket)
    try {
      const wsHealth = await apiClient.get('/api/websocket/health');
      if (wsHealth.success && wsHealth.features) {
        return {
          status: socketIOStatus,
          message: socketIOMessage,
          productionFeatures: wsHealth.features,
          config: wsHealth.config,
          note: wsHealth.note,
        };
      }
    } catch (error) {
      console.log('WebSocket health check unavailable:', error.message);
    }

    return {
      status: socketIOStatus,
      message: socketIOMessage,
    };
  };

  const checkSystemStatus = async () => {
    try {
      const response = await apiClient.get('/api/health');

      // Handle telegram data - two formats possible
      let telegramStatus;
      const telegram = response.telegram;

      if (telegram && typeof telegram === 'object') {
        // Full telegram object from fallback health check
        if (!telegram.enabled) {
          telegramStatus = {
            status: 'warning',
            message: 'Telegram notifications disabled',
            bot_info: telegram.bot_info || null,
          };
        } else if (telegram.connected) {
          telegramStatus = {
            status: 'healthy',
            message: telegram.message || 'Telegram connected',
            bot_info: telegram.bot_info || null,
          };
        } else {
          telegramStatus = {
            status: 'warning',
            message: telegram.message || telegram.error || 'Telegram not connected',
            bot_info: telegram.bot_info || null,
          };
        }
      } else {
        // Cached health checker - only provides telegram_connected boolean
        const connected = response.telegram_connected || false;
        telegramStatus = {
          status: connected ? 'healthy' : 'warning',
          message: connected ? 'Telegram connected' : 'Telegram disconnected',
          bot_info: null,
        };
      }

      return {
        bot: {
          status: response.bot_running ? 'healthy' : 'warning',
          message: response.bot_running ? 'Bot running' : 'Bot not running',
        },
        guardian: {
          status: response.guardian_running ? 'healthy' : 'warning',
          message: response.guardian_running ? 'Guardian active' : 'Guardian inactive',
        },
        database: {
          status: 'healthy',
          message: 'Database accessible',
        },
        telegram: telegramStatus,
      };
    } catch (error) {
      return {
        bot: { status: 'unknown', message: 'Cannot determine status' },
        guardian: { status: 'unknown', message: 'Cannot determine status' },
        database: { status: 'unknown', message: 'Cannot determine status' },
        telegram: { status: 'unknown', message: 'Cannot determine status' },
      };
    }
  };

  const checkErrorIntelligence = async () => {
    try {
      const response = await apiClient.get('/api/errors/statistics');
      const openErrors = response.statistics?.by_status?.open || 0;

      if (openErrors > 10) {
        return {
          status: 'warning',
          message: `${openErrors} open errors`,
        };
      } else if (openErrors > 0) {
        return {
          status: 'healthy',
          message: `${openErrors} open errors (normal)`,
        };
      } else {
        return {
          status: 'healthy',
          message: 'No open errors',
        };
      }
    } catch (error) {
      return {
        status: 'unknown',
        message: 'Cannot check error status',
      };
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy':
        return 'success';
      case 'warning':
        return 'warning';
      case 'error':
        return 'error';
      default:
        return 'default';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy':
        return <HealthyIcon />;
      case 'warning':
        return <WarningIcon />;
      case 'error':
        return <ErrorIcon />;
      default:
        return <UnknownIcon />;
    }
  };

  const getOverallHealth = () => {
    const statuses = Object.values(health).map((h) => h.status);
    if (statuses.includes('error')) return 'error';
    if (statuses.includes('warning')) return 'warning';
    if (statuses.every((s) => s === 'healthy')) return 'healthy';
    return 'unknown';
  };

  const overallHealth = getOverallHealth();

  return (
    <Paper elevation={3} sx={{ p: 2, mb: 2 }}>
      {loading && <LinearProgress sx={{ mb: 2 }} />}

      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {getStatusIcon(overallHealth)}
          System Health
        </Typography>
        <Chip
          label={overallHealth.toUpperCase()}
          color={getStatusColor(overallHealth)}
          size="small"
        />
      </Box>

      <Grid container spacing={2}>
        {Object.entries(health).map(([key, value]) => (
          <Grid item xs={6} sm={4} md={2} key={key}>
            <Tooltip
              title={
                key === 'telegram' && value.bot_info ? (
                  <Box>
                    <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>
                      {value.bot_info.icon} {value.bot_info.name}
                    </Typography>
                    <Typography variant="body2" sx={{ mb: 0.5 }}>
                      <strong>Username:</strong> {value.bot_info.username}
                    </Typography>
                    <Typography variant="body2" sx={{ mb: 0.5 }}>
                      <strong>Mode:</strong> {value.bot_info.mode.toUpperCase()}
                    </Typography>
                    <Typography variant="body2" sx={{ mb: 0.5 }}>
                      <strong>Description:</strong> {value.bot_info.description}
                    </Typography>
                    <Typography variant="body2">
                      <strong>Status:</strong> {value.message}
                    </Typography>
                  </Box>
                ) : key === 'websocket' && value.productionFeatures ? (
                  <Box>
                    <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>
                      🚀 Production-Grade WebSocket
                    </Typography>
                    <Typography variant="body2" sx={{ mb: 0.5 }}>
                      <strong>Status:</strong> {value.message}
                    </Typography>
                    <Typography variant="body2" sx={{ fontWeight: 'bold', mt: 1, mb: 0.5 }}>
                      Features:
                    </Typography>
                    {Object.entries(value.productionFeatures).map(
                      ([feature, enabled]) =>
                        enabled && (
                          <Typography
                            variant="body2"
                            key={feature}
                            sx={{ ml: 1, fontSize: '0.75rem' }}
                          >
                            ✅ {feature.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                          </Typography>
                        )
                    )}
                    {value.config && (
                      <>
                        <Typography variant="body2" sx={{ fontWeight: 'bold', mt: 1, mb: 0.5 }}>
                          Configuration:
                        </Typography>
                        <Typography variant="body2" sx={{ ml: 1, fontSize: '0.75rem' }}>
                          Ping: {value.config.ping_interval}s / Timeout: {value.config.ping_timeout}
                          s
                        </Typography>
                        <Typography variant="body2" sx={{ ml: 1, fontSize: '0.75rem' }}>
                          Reconnect: {value.config.base_reconnect_delay}s-
                          {value.config.max_reconnect_delay}s
                        </Typography>
                        <Typography variant="body2" sx={{ ml: 1, fontSize: '0.75rem' }}>
                          Max Attempts: {value.config.max_reconnect_attempts}
                        </Typography>
                      </>
                    )}
                  </Box>
                ) : (
                  value.message
                )
              }
              arrow
            >
              <Paper
                elevation={2}
                sx={{
                  p: 1.5,
                  textAlign: 'center',
                  border: '2px solid',
                  borderColor:
                    getStatusColor(value.status) === 'success'
                      ? 'success.main'
                      : getStatusColor(value.status) === 'warning'
                        ? 'warning.main'
                        : getStatusColor(value.status) === 'error'
                          ? 'error.main'
                          : 'grey.500',
                  cursor: 'help',
                }}
              >
                <Box sx={{ mb: 1 }}>{getStatusIcon(value.status)}</Box>
                <Typography variant="caption" display="block" fontWeight="bold">
                  {key === 'telegram' && value.bot_info ? (
                    <Box>
                      <Box sx={{ fontSize: '0.75rem', mb: 0.3 }}>Telegram</Box>
                      <Box
                        sx={{
                          fontSize: '0.65rem',
                          fontWeight: 'bold',
                          color: value.bot_info.mode === 'demo' ? 'success.main' : 'error.main',
                          backgroundColor:
                            value.bot_info.mode === 'demo'
                              ? 'rgba(76, 175, 80, 0.1)'
                              : 'rgba(244, 67, 54, 0.1)',
                          padding: '2px 4px',
                          borderRadius: '4px',
                          border:
                            value.bot_info.mode === 'demo'
                              ? '1px solid rgba(76, 175, 80, 0.3)'
                              : '1px solid rgba(244, 67, 54, 0.3)',
                        }}
                      >
                        {value.bot_info.icon} {value.bot_info.mode.toUpperCase()}
                      </Box>
                    </Box>
                  ) : (
                    key.charAt(0).toUpperCase() + key.slice(1)
                  )}
                </Typography>
                <Chip
                  label={value.status}
                  size="small"
                  color={getStatusColor(value.status)}
                  sx={{ mt: 1, height: 20, fontSize: '0.7rem' }}
                />
              </Paper>
            </Tooltip>
          </Grid>
        ))}
      </Grid>

      {overallHealth === 'error' && (
        <Box sx={{ mt: 2 }}>
          <Typography variant="body2" color="error">
            ⚠️ Some components are experiencing issues. Check individual status for details.
          </Typography>
        </Box>
      )}

      {/* Connection Latency Chart */}
      {botIsRunning && latencyStats?.history && (
        <Box sx={{ mt: 3, pt: 3, borderTop: '1px solid rgba(255, 255, 255, 0.1)' }}>
          <Box
            sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}
          >
            <Typography variant="h6" sx={{ fontWeight: 600 }}>
              Connection Latency
            </Typography>
            <Chip
              label={`Quality: ${connectionQuality || 'Unknown'}`}
              size="small"
              color={
                connectionQuality === 'excellent'
                  ? 'success'
                  : connectionQuality === 'good'
                    ? 'info'
                    : connectionQuality === 'fair'
                      ? 'warning'
                      : 'error'
              }
              sx={{ height: 24, fontSize: '0.75rem' }}
            />
          </Box>
          <LatencyChart data={latencyStats.history} />
        </Box>
      )}
    </Paper>
  );
};

export default HealthCheckDashboard;
