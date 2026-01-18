import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  CardHeader,
  Typography,
  Button,
  Chip,
  Grid,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Tooltip,
  Alert,
  Snackbar,
  CircularProgress,
  Divider,
  TextField,
  ToggleButtonGroup,
  ToggleButton,
  FormControlLabel,
  Switch,
} from '@mui/material';
import {
  PlayArrow,
  Stop,
  Refresh,
  Memory,
  Speed,
  Computer,
  BugReport,
  CheckCircle,
  Error,
  Warning,
  TrendingUp,
  TrendingDown,
} from '@mui/icons-material';
import { styled } from '@mui/material/styles';
import api from '../../utils/apiShim';
import { useInstance } from '../../context/InstanceContext';

const StyledCard = styled(Card)(({ theme, status }) => ({
  transition: 'transform 0.2s, box-shadow 0.2s',
  cursor: 'pointer',
  '&:hover': {
    transform: 'translateY(-2px)',
    boxShadow: theme.shadows[8],
  },
  borderLeft: `4px solid ${
    status === 'running' ? theme.palette.success.main : theme.palette.error.main
  }`,
}));

const StatusIndicator = styled(Box)(({ status }) => ({
  width: 12,
  height: 12,
  borderRadius: '50%',
  backgroundColor: status === 'running' ? '#4caf50' : '#f44336',
  display: 'inline-block',
  marginRight: 8,
}));

const BotManagementDashboard = () => {
  const { instances } = useInstance();
  const [botStatus, setBotStatus] = useState({});
  const [systemInfo, setSystemInfo] = useState({});
  const [processes, setProcesses] = useState([]);
  const [loading, setLoading] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'info' });
  const [instanceStatus, setInstanceStatus] = useState({}); // Per-instance status

  // Fetch instances from config
  const fetchInstances = useCallback(async () => {
    try {
      const response = await api.get('/api/instances');
      const instancesData = response.data?.instances || [];

      console.log('✅ Fetched instances:', instancesData); // Debug log

      // Initialize instance status from config
      const status = {};
      instancesData.forEach((inst) => {
        status[inst.name] = {
          name: inst.name,
          symbol: inst.symbol,
          mode: inst.mode,
          enabled: inst.enabled,
          running: false,
          pid: null,
        };
      });

      // Ensure ETHUSD instance exists if not in config
      if (!status['ETHUSD_LONG']) {
        status['ETHUSD_LONG'] = {
          name: 'ETHUSD_LONG',
          symbol: 'ETHUSD',
          mode: 'LONG',
          enabled: false,
          running: false,
          pid: null,
        };
      }

      console.log('📊 Instance status initialized:', status); // Debug log
      setInstanceStatus(status);
    } catch (error) {
      console.error('❌ Error fetching instances:', error);
      // Fallback: Add default instances if API fails
      setInstanceStatus({
        BTCUSD_LONG: {
          name: 'BTCUSD_LONG',
          symbol: 'BTCUSD',
          mode: 'LONG',
          enabled: false,
          running: false,
          pid: null,
        },
        ETHUSD_LONG: {
          name: 'ETHUSD_LONG',
          symbol: 'ETHUSD',
          mode: 'LONG',
          enabled: false,
          running: false,
          pid: null,
        },
      });
    }
  }, []);

  // Fetch bot status and system info
  const fetchBotStatus = async () => {
    try {
      // Fetch bot processes
      const botsResponse = await api.get('/api/bots/status');
      const bots = botsResponse.data.bots || [];

      // Convert array to object keyed by type for compatibility
      const botStatus = {};
      bots.forEach((bot) => {
        botStatus[bot.type] = {
          name: bot.name,
          running: bot.status === 'running',
          pid: bot.pid,
          description: bot.command,
          log_size: bot.memoryMb * 1024 * 1024,
          last_modified: bot.startedAt,
          uptime: bot.uptime,
          cpu: bot.cpuPercent,
          memory: bot.memoryMb,
        };

        // Update instance status if this is a trading bot
        if (bot.type === 'gridbot' && bot.status === 'running') {
          // Parse instance from bot name/env
          const instanceMatch = bot.command?.match(/--instance[= ](\w+)/);
          if (instanceMatch) {
            setInstanceStatus((prev) => ({
              ...prev,
              [instanceMatch[1]]: {
                ...prev[instanceMatch[1]],
                running: true,
                pid: bot.pid,
              },
            }));
          }
        }
      });

      setBotStatus(botStatus);

      // Fetch system info
      const systemResponse = await api.get('/api/system/status');
      setSystemInfo(systemResponse.data || {});
    } catch (error) {
      console.error('Error fetching bot status:', error);
    }
  };

  // Fetch processes
  const fetchProcesses = async () => {
    try {
      const response = await api.get('/api/bots/status');
      const bots = response.data.bots || [];

      // Convert to process format
      const processes = bots.map((bot) => ({
        pid: bot.pid,
        cpu: bot.cpuPercent,
        memory: (bot.memoryMb / 1024) * 100, // Convert to percentage (approximate)
        command: bot.command,
      }));

      setProcesses(processes);
    } catch (error) {
      console.error('Error fetching processes:', error);
    }
  };

  // Bot action handler
  const handleBotAction = async (action, botType) => {
    setLoading(true);
    try {
      let response;

      // Map actions to API endpoints based on bot type
      if (action === 'start') {
        if (botType === 'guardian') {
          response = await api.post('/api/guardian/start');
        } else {
          response = await api.post('/api/bot/start', {
            bot_type: botType || 'all',
          });
        }
      } else if (action === 'stop') {
        if (botType === 'guardian') {
          response = await api.post('/api/guardian/stop');
        } else if (botType) {
          // Stop specific bot by finding its PID
          const statusResponse = await api.get('/api/bots/status');
          const bots = statusResponse.data.bots || [];
          const targetBot = bots.find((b) => b.type === botType);

          if (targetBot) {
            response = await api.post('/api/bots/stop', {
              pid: targetBot.pid,
            });
          } else {
            throw new Error(`Bot ${botType} not found`);
          }
        } else {
          // Stop all - use emergency kill
          response = await api.post('/api/emergency/kill-all');
        }
      } else if (action === 'restart') {
        if (botType === 'guardian') {
          response = await api.post('/api/guardian/restart');
        } else {
          response = await api.post('/api/bot/restart', {
            bot_type: botType || 'all',
          });
        }
      }

      if (response && response.data.success) {
        setSnackbar({
          open: true,
          message: `${action.charAt(0).toUpperCase() + action.slice(1)} ${botType || 'all bots'} successful`,
          severity: 'success',
        });
      } else {
        setSnackbar({
          open: true,
          message: `Failed to ${action} ${botType || 'all bots'}: ${response?.data?.error || 'Unknown error'}`,
          severity: 'error',
        });
      }

      // Refresh status after action
      setTimeout(() => {
        fetchBotStatus();
        fetchProcesses();
      }, 1000);
    } catch (error) {
      setSnackbar({
        open: true,
        message: `Error: ${error.message}`,
        severity: 'error',
      });
    } finally {
      setLoading(false);
    }
  };

  // Instance-specific start/stop handler (v6.0 multi-instrument)
  const handleInstanceAction = async (action, instanceName) => {
    setLoading(true);
    try {
      let response;

      if (action === 'start') {
        response = await api.post('/api/bot/start', {
          instance: instanceName,
        });
      } else if (action === 'stop') {
        response = await api.post('/api/bot/stop', {
          instance: instanceName,
        });
      } else if (action === 'toggle_enabled') {
        response = await api.post('/api/instances/toggle', {
          instance: instanceName,
        });
      }

      if (response && response.data.success) {
        setSnackbar({
          open: true,
          message: `${action.charAt(0).toUpperCase() + action.slice(1)} ${instanceName} successful`,
          severity: 'success',
        });

        // Refresh instances
        fetchInstances();
      } else {
        setSnackbar({
          open: true,
          message: `Failed to ${action} ${instanceName}: ${response?.data?.error || 'Unknown error'}`,
          severity: 'error',
        });
      }

      setTimeout(() => {
        fetchBotStatus();
        fetchProcesses();
      }, 1000);
    } catch (error) {
      setSnackbar({
        open: true,
        message: `Error: ${error.message}`,
        severity: 'error',
      });
    } finally {
      setLoading(false);
    }
  };

  // Format bytes
  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // Get instance color by symbol
  const getInstanceColor = (symbol) => {
    const colors = {
      BTCUSD: { bg: '#f7931a20', border: '#f7931a', text: '#f7931a' }, // Bitcoin orange
      ETHUSD: { bg: '#627eea20', border: '#627eea', text: '#627eea' }, // Ethereum purple
    };
    return colors[symbol] || { bg: '#64748b20', border: '#64748b', text: '#64748b' };
  };

  // Load data on component mount
  useEffect(() => {
    fetchInstances();
    fetchBotStatus();
    fetchProcesses();

    // Set up auto-refresh
    const interval = setInterval(() => {
      fetchBotStatus();
      fetchProcesses();
    }, 10000);

    return () => clearInterval(interval);
  }, [fetchInstances]);

  // Group instances by symbol
  const instancesBySymbol = Object.values(instanceStatus).reduce((acc, inst) => {
    if (!acc[inst.symbol]) acc[inst.symbol] = [];
    acc[inst.symbol].push(inst);
    return acc;
  }, {});

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" gutterBottom>
          <Computer sx={{ mr: 1, verticalAlign: 'middle' }} />
          Multi-Instrument Bot Management
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Control trading bots for each instrument and mode (v6.0)
        </Typography>
      </Box>

      {/* Instance Control Cards - Grouped by Symbol */}
      <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
        <TrendingUp /> Trading Instances
      </Typography>
      <Grid container spacing={3} sx={{ mb: 3 }}>
        {Object.entries(instancesBySymbol).map(([symbol, symbolInstances]) => {
          const colors = getInstanceColor(symbol);
          return (
            <Grid item xs={12} md={6} key={symbol}>
              <Card
                sx={{
                  borderLeft: `4px solid ${colors.border}`,
                  bgcolor: colors.bg,
                }}
              >
                <CardHeader
                  title={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography variant="h6" sx={{ color: colors.text, fontWeight: 'bold' }}>
                        {symbol}
                      </Typography>
                      <Chip
                        label={`${symbolInstances.filter((i) => i.enabled).length}/${symbolInstances.length} enabled`}
                        size="small"
                        color="primary"
                        variant="outlined"
                      />
                    </Box>
                  }
                />
                <CardContent>
                  <Grid container spacing={2}>
                    {symbolInstances.map((instance) => (
                      <Grid item xs={12} key={instance.name}>
                        <Paper
                          sx={{
                            p: 2,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            bgcolor: instance.enabled
                              ? 'background.paper'
                              : 'action.disabledBackground',
                          }}
                        >
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                            {instance.mode === 'LONG' ? (
                              <TrendingUp sx={{ color: '#10b981' }} />
                            ) : (
                              <TrendingDown sx={{ color: '#ef4444' }} />
                            )}
                            <Box>
                              <Typography variant="subtitle1" fontWeight="bold">
                                {instance.name}
                              </Typography>
                              <Typography variant="caption" color="text.secondary">
                                {instance.mode} Mode • {instance.running ? 'Running' : 'Stopped'}
                              </Typography>
                            </Box>
                            <Chip
                              label={instance.enabled ? 'Enabled' : 'Disabled'}
                              size="small"
                              color={instance.enabled ? 'success' : 'default'}
                            />
                            {instance.running && (
                              <Chip
                                icon={<CheckCircle sx={{ fontSize: 14 }} />}
                                label={`PID: ${instance.pid}`}
                                size="small"
                                color="info"
                                variant="outlined"
                              />
                            )}
                          </Box>
                          <Box sx={{ display: 'flex', gap: 1 }}>
                            <Tooltip title={instance.running ? 'Stop Instance' : 'Start Instance'}>
                              <Button
                                size="small"
                                variant={instance.running ? 'outlined' : 'contained'}
                                color={instance.running ? 'error' : 'success'}
                                onClick={() =>
                                  handleInstanceAction(
                                    instance.running ? 'stop' : 'start',
                                    instance.name
                                  )
                                }
                                disabled={loading || !instance.enabled}
                                startIcon={instance.running ? <Stop /> : <PlayArrow />}
                              >
                                {instance.running ? 'Stop' : 'Start'}
                              </Button>
                            </Tooltip>
                            <FormControlLabel
                              control={
                                <Switch
                                  size="small"
                                  checked={instance.enabled}
                                  onChange={() =>
                                    handleInstanceAction('toggle_enabled', instance.name)
                                  }
                                  disabled={loading}
                                />
                              }
                              label=""
                            />
                          </Box>
                        </Paper>
                      </Grid>
                    ))}
                  </Grid>
                </CardContent>
              </Card>
            </Grid>
          );
        })}
      </Grid>

      {/* System Info */}
      <Paper
        sx={{
          p: 2,
          mb: 3,
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          color: 'white',
        }}
      >
        <Grid container spacing={2}>
          <Grid item xs={12} md={8}>
            <Typography variant="h6" gutterBottom>
              System Status
            </Typography>
            <Typography variant="body2">
              Load:{' '}
              {systemInfo.load_avg
                ? systemInfo.load_avg.map((l) => l.toFixed(2)).join(', ')
                : 'N/A'}
            </Typography>
            <Typography variant="body2">
              Bot Memory: {formatBytes(systemInfo.bot_memory || 0)}
            </Typography>
          </Grid>
          <Grid item xs={12} md={4} sx={{ textAlign: 'right' }}>
            <Typography variant="body2">Last Updated: {systemInfo.timestamp || 'N/A'}</Typography>
          </Grid>
        </Grid>
      </Paper>

      {/* Bot Status Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        {Object.entries(botStatus).map(([botType, status]) => (
          <Grid item xs={12} md={4} key={botType}>
            <StyledCard status={status.running ? 'running' : 'stopped'}>
              <CardHeader
                title={
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <StatusIndicator status={status.running ? 'running' : 'stopped'} />
                    {status.name}
                  </Box>
                }
                subheader={`PID: ${status.pid || 'N/A'}`}
                action={
                  <Chip
                    label={status.running ? 'Running' : 'Stopped'}
                    color={status.running ? 'success' : 'error'}
                    size="small"
                  />
                }
              />
              <CardContent>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  {status.description}
                </Typography>
                <Typography variant="caption" display="block" sx={{ mb: 2 }}>
                  Log Size: {formatBytes(status.log_size || 0)}
                  <br />
                  Last Modified: {status.last_modified || 'N/A'}
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                  <Button
                    size="small"
                    startIcon={<PlayArrow />}
                    onClick={() => handleBotAction('start', botType)}
                    disabled={loading || status.running}
                    color="success"
                    variant="outlined"
                  >
                    Start
                  </Button>
                  <Button
                    size="small"
                    startIcon={<Refresh />}
                    onClick={() => handleBotAction('restart', botType)}
                    disabled={loading}
                    color="warning"
                    variant="outlined"
                  >
                    Restart
                  </Button>
                  <Button
                    size="small"
                    startIcon={<Stop />}
                    onClick={() => handleBotAction('stop', botType)}
                    disabled={loading || !status.running}
                    color="error"
                    variant="outlined"
                  >
                    Stop
                  </Button>
                </Box>
              </CardContent>
            </StyledCard>
          </Grid>
        ))}
      </Grid>

      {/* Bulk Actions */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Bulk Actions
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <Button
            variant="contained"
            color="success"
            startIcon={<PlayArrow />}
            onClick={() => handleBotAction('start', null)}
            disabled={loading}
          >
            Start All Bots
          </Button>
          <Button
            variant="contained"
            color="warning"
            startIcon={<Refresh />}
            onClick={() => handleBotAction('restart', null)}
            disabled={loading}
          >
            Restart All Bots
          </Button>
          <Button
            variant="contained"
            color="error"
            startIcon={<Stop />}
            onClick={() => handleBotAction('stop', null)}
            disabled={loading}
          >
            Stop All Bots
          </Button>
        </Box>
      </Paper>

      {/* Processes Table */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          <BugReport sx={{ mr: 1, verticalAlign: 'middle' }} />
          System Processes
        </Typography>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>PID</TableCell>
                <TableCell>CPU %</TableCell>
                <TableCell>Memory %</TableCell>
                <TableCell>Command</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {processes.length > 0 ? (
                processes.map((process, index) => (
                  <TableRow key={index}>
                    <TableCell>{process.pid}</TableCell>
                    <TableCell>{process.cpu?.toFixed(1) || 'N/A'}%</TableCell>
                    <TableCell>{process.memory?.toFixed(1) || 'N/A'}%</TableCell>
                    <TableCell>
                      <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                        {process.command}
                      </Typography>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={4} align="center">
                    No bot processes found
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      {/* Loading Overlay */}
      {loading && (
        <Box
          sx={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
          }}
        >
          <CircularProgress color="primary" />
        </Box>
      )}

      {/* Snackbar for notifications */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={5000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
      >
        <Alert
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          severity={snackbar.severity}
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default BotManagementDashboard;
