import React, { useState, useEffect } from 'react';
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
  Select,
  MenuItem,
  FormControl,
  InputLabel
} from '@mui/material';
import {
  PlayArrow,
  Stop,
  Refresh,
  Visibility,
  Memory,
  Speed,
  Computer,
  BugReport,
  CheckCircle,
  Error,
  Warning
} from '@mui/icons-material';
import { styled } from '@mui/material/styles';
import api from '../../utils/apiShim';

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
  const [botStatus, setBotStatus] = useState({});
  const [systemInfo, setSystemInfo] = useState({});
  const [processes, setProcesses] = useState([]);
  const [logs, setLogs] = useState('');
  const [selectedBot, setSelectedBot] = useState('trading');
  const [loading, setLoading] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'info' });

  // Fetch bot status and system info
  const fetchBotStatus = async () => {
    try {
      // Fetch bot processes
      const botsResponse = await api.get('/api/bots/status');
      const bots = botsResponse.data.bots || [];
      
      // Convert array to object keyed by type for compatibility
      const botStatus = {};
      bots.forEach(bot => {
        botStatus[bot.type] = {
          name: bot.name,
          running: bot.status === 'running',
          pid: bot.pid,
          description: bot.command,
          log_size: bot.memoryMb * 1024 * 1024, // Approximate
          last_modified: bot.startedAt,
          uptime: bot.uptime,
          cpu: bot.cpuPercent,
          memory: bot.memoryMb
        };
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
      const processes = bots.map(bot => ({
        pid: bot.pid,
        cpu: bot.cpuPercent,
        memory: (bot.memoryMb / 1024) * 100, // Convert to percentage (approximate)
        command: bot.command
      }));
      
      setProcesses(processes);
    } catch (error) {
      console.error('Error fetching processes:', error);
    }
  };

  // Fetch logs
  const fetchLogs = async (botType) => {
    try {
      // Map bot types to log file paths
      const logFileMap = {
        'trading': 'bot/logs/bot.log',
        'live_trading': 'bot/logs/bot.log',
        'health': 'bot/logs/heartbeat_monitor.log',
        'monitoring': 'bot/logs/heartbeat_monitor.log',
        'guardian': 'bot/logs/guardian.log'
      };
      
      const logFile = logFileMap[botType] || 'bot/logs/bot.log';
      
      // ✅ FIX: Pass bot_type parameter to API
      const response = await api.get(`/api/logs/recent?lines=100&bot_type=${botType}&log_file=${encodeURIComponent(logFile)}`);
      
      if (response.data.success) {
        setLogs(response.data.logs || 'No logs available');
      } else {
        setLogs('Error loading logs');
      }
    } catch (error) {
      console.error('Error fetching logs:', error);
      setLogs('Error loading logs');
    }
  };

  // Bot action handler
  const handleBotAction = async (action, botType) => {
    setLoading(true);
    try {
      let response;
      
      // Map actions to API endpoints
      if (action === 'start') {
        response = await api.post('/api/bot/start', {
          bot_type: botType || 'all'
        });
      } else if (action === 'stop') {
        if (botType) {
          // Stop specific bot by finding its PID
          const statusResponse = await api.get('/api/bots/status');
          const bots = statusResponse.data.bots || [];
          const targetBot = bots.find(b => b.type === botType);
          
          if (targetBot) {
            response = await api.post('/api/bots/stop', {
              pid: targetBot.pid
            });
          } else {
            throw new Error(`Bot ${botType} not found`);
          }
        } else {
          // Stop all - use emergency kill
          response = await api.post('/api/emergency/kill-all');
        }
      } else if (action === 'restart') {
        response = await api.post('/api/bot/restart', {
          bot_type: botType || 'all'
        });
      }
      
      if (response && response.data.success) {
        setSnackbar({
          open: true,
          message: `${action.charAt(0).toUpperCase() + action.slice(1)} ${botType || 'all bots'} successful`,
          severity: 'success'
        });
      } else {
        setSnackbar({
          open: true,
          message: `Failed to ${action} ${botType || 'all bots'}: ${response?.data?.error || 'Unknown error'}`,
          severity: 'error'
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
        severity: 'error'
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

  // Load data on component mount
  useEffect(() => {
    fetchBotStatus();
    fetchProcesses();
    fetchLogs(selectedBot);
    
    // Set up auto-refresh
    const interval = setInterval(() => {
      fetchBotStatus();
      fetchProcesses();
    }, 10000); // Refresh every 10 seconds
    
    return () => clearInterval(interval);
  }, []);

  // Fetch logs when selected bot changes
  useEffect(() => {
    fetchLogs(selectedBot);
  }, [selectedBot]);

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" gutterBottom>
          <Computer sx={{ mr: 1, verticalAlign: 'middle' }} />
          Bot Process Management
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Monitor and control your trading bot processes
        </Typography>
      </Box>

      {/* System Info */}
      <Paper sx={{ p: 2, mb: 3, background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', color: 'white' }}>
        <Grid container spacing={2}>
          <Grid item xs={12} md={8}>
            <Typography variant="h6" gutterBottom>
              System Status
            </Typography>
            <Typography variant="body2">
              Load: {systemInfo.load_avg ? systemInfo.load_avg.map(l => l.toFixed(2)).join(', ') : 'N/A'}
            </Typography>
            <Typography variant="body2">
              Bot Memory: {formatBytes(systemInfo.bot_memory || 0)}
            </Typography>
          </Grid>
          <Grid item xs={12} md={4} sx={{ textAlign: 'right' }}>
            <Typography variant="body2">
              Last Updated: {systemInfo.timestamp || 'N/A'}
            </Typography>
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

      {/* Logs Section */}
      <Paper sx={{ p: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">
            <Visibility sx={{ mr: 1, verticalAlign: 'middle' }} />
            Bot Logs
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>Select Bot</InputLabel>
              <Select
                value={selectedBot}
                label="Select Bot"
                onChange={(e) => setSelectedBot(e.target.value)}
              >
                <MenuItem value="trading">Trading Bot</MenuItem>
                <MenuItem value="guardian">Guardian Bot</MenuItem>
                <MenuItem value="monitoring">Heartbeat Monitor</MenuItem>
              </Select>
            </FormControl>
            <Button
              size="small"
              startIcon={<Refresh />}
              onClick={() => fetchLogs(selectedBot)}
            >
              Refresh
            </Button>
          </Box>
        </Box>
        <Box
          sx={{
            backgroundColor: '#1e1e1e',
            color: '#d4d4d4',
            fontFamily: 'monospace',
            fontSize: '12px',
            maxHeight: 400,
            overflow: 'auto',
            padding: 2,
            borderRadius: 1,
            whiteSpace: 'pre-wrap'
          }}
        >
          {logs || 'Select a bot to view logs...'}
        </Box>
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
            zIndex: 9999
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
