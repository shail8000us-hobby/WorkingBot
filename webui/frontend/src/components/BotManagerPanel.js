import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Snackbar,
  Alert,
  CircularProgress,
} from '@mui/material';
import { Refresh, Stop, Memory, Computer, Speed, Timer } from '@mui/icons-material';
import axios from 'axios';
import { useInstance, parseInstanceName } from '../context/InstanceContext';

const BotManagerPanel = () => {
  const { selectedInstance } = useInstance();
  const instanceInfo = parseInstanceName(selectedInstance);
  const selectedSymbol = instanceInfo?.symbol; // backward compat
  const [bots, setBots] = useState([]);
  const [totalBots, setTotalBots] = useState(0);
  const [loading, setLoading] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState({ open: false, bot: null });
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'info' });
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Fetch bot status from backend (global, not per-symbol)
  const fetchBotStatus = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/bots/status');

      if (response.data.success) {
        setBots(response.data.bots || []);
        setTotalBots(response.data.totalBots || 0);
      } else {
        showSnackbar('Failed to fetch bot status', 'error');
      }
    } catch (error) {
      console.error('Error fetching bot status:', error);
      showSnackbar(`Error: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  // Stop a specific bot
  const stopBot = async (pid) => {
    try {
      setLoading(true);
      const response = await axios.post('/api/bots/stop', { pid });

      if (response.data.success) {
        showSnackbar(response.data.message || 'Bot stopped successfully', 'success');
        // Refresh the list after stopping
        setTimeout(() => fetchBotStatus(), 1000);
      } else {
        showSnackbar(response.data.message || 'Failed to stop bot', 'error');
      }
    } catch (error) {
      console.error('Error stopping bot:', error);
      showSnackbar(`Error: ${error.message}`, 'error');
    } finally {
      setLoading(false);
      setConfirmDialog({ open: false, bot: null });
    }
  };

  // Show snackbar notification
  const showSnackbar = (message, severity = 'info') => {
    setSnackbar({ open: true, message, severity });
  };

  // Display uptime (already formatted by backend)
  const formatUptime = (uptime) => {
    // Backend sends pre-formatted string like "2h 15m"
    if (!uptime) return 'N/A';
    return uptime;
  };

  // Format memory to MB
  const formatMemory = (mb) => {
    if (!mb) return 'N/A';
    return `${mb.toFixed(1)} MB`;
  };

  // Get bot type color
  const getBotTypeColor = (type) => {
    const colors = {
      live_trading: 'success',
      dry_run: 'warning',
      guardian: 'info',
      monitor: 'secondary',
      webui: 'primary',
    };
    return colors[type] || 'default';
  };

  // Get bot type label
  const getBotTypeLabel = (type) => {
    const labels = {
      live_trading: 'Live Trading',
      dry_run: 'Dry Run',
      guardian: 'Guardian',
      monitor: 'Monitor',
      webui: 'WebUI',
    };
    return labels[type] || type;
  };

  // Handle stop button click
  const handleStopClick = (bot) => {
    setConfirmDialog({ open: true, bot });
  };

  // Auto-refresh every 5 seconds
  useEffect(() => {
    fetchBotStatus(); // Initial fetch

    let interval;
    if (autoRefresh) {
      interval = setInterval(() => {
        fetchBotStatus();
      }, 5000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh]);

  return (
    <Card>
      <CardContent>
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Computer color="primary" />
            <Typography variant="h6">Bot Manager</Typography>
            <Chip
              label={`${totalBots} Active`}
              size="small"
              color={totalBots > 0 ? 'success' : 'default'}
            />
          </Box>

          <Box sx={{ display: 'flex', gap: 1 }}>
            <Tooltip title={autoRefresh ? 'Auto-refresh enabled (5s)' : 'Auto-refresh disabled'}>
              <IconButton
                size="small"
                color={autoRefresh ? 'primary' : 'default'}
                onClick={() => setAutoRefresh(!autoRefresh)}
              >
                <Refresh sx={{ animation: autoRefresh ? 'spin 2s linear infinite' : 'none' }} />
              </IconButton>
            </Tooltip>

            <Button
              variant="outlined"
              size="small"
              startIcon={<Refresh />}
              onClick={fetchBotStatus}
              disabled={loading}
            >
              Refresh
            </Button>
          </Box>
        </Box>

        {/* Loading Indicator */}
        {loading && bots.length === 0 && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        )}

        {/* No Bots Message */}
        {!loading && bots.length === 0 && (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Typography color="text.secondary">No bot processes detected</Typography>
          </Box>
        )}

        {/* Bots Table */}
        {bots.length > 0 && (
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>
                    <strong>Type</strong>
                  </TableCell>
                  <TableCell>
                    <strong>PID</strong>
                  </TableCell>
                  <TableCell>
                    <strong>Status</strong>
                  </TableCell>
                  <TableCell>
                    <strong>Started</strong>
                  </TableCell>
                  <TableCell>
                    <strong>Uptime</strong>
                  </TableCell>
                  <TableCell align="right">
                    <strong>CPU %</strong>
                  </TableCell>
                  <TableCell align="right">
                    <strong>Memory</strong>
                  </TableCell>
                  <TableCell align="center">
                    <strong>Actions</strong>
                  </TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {bots.map((bot) => (
                  <TableRow
                    key={bot.pid}
                    sx={{
                      '&:hover': { backgroundColor: 'action.hover' },
                      opacity: bot.type === 'webui' ? 0.6 : 1,
                    }}
                  >
                    <TableCell>
                      <Chip
                        label={getBotTypeLabel(bot.type)}
                        size="small"
                        color={getBotTypeColor(bot.type)}
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                        {bot.pid}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={bot.status}
                        size="small"
                        color={bot.status === 'running' ? 'success' : 'default'}
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {new Date(bot.startedAt).toLocaleString()}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <Timer fontSize="small" color="action" />
                        <Typography variant="body2">{formatUptime(bot.uptime)}</Typography>
                      </Box>
                    </TableCell>
                    <TableCell align="right">
                      <Box
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'flex-end',
                          gap: 0.5,
                        }}
                      >
                        <Speed fontSize="small" color="action" />
                        <Typography variant="body2">
                          {bot.cpuPercent?.toFixed(1) || '0.0'}%
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell align="right">
                      <Box
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'flex-end',
                          gap: 0.5,
                        }}
                      >
                        <Memory fontSize="small" color="action" />
                        <Typography variant="body2">{formatMemory(bot.memoryMb)}</Typography>
                      </Box>
                    </TableCell>
                    <TableCell align="center">
                      {bot.type === 'webui' ? (
                        <Tooltip title="Cannot stop WebUI backend from itself">
                          <span>
                            <IconButton size="small" disabled>
                              <Stop />
                            </IconButton>
                          </span>
                        </Tooltip>
                      ) : (
                        <Tooltip title="Stop this bot">
                          <IconButton
                            size="small"
                            color="error"
                            onClick={() => handleStopClick(bot)}
                            disabled={loading}
                          >
                            <Stop />
                          </IconButton>
                        </Tooltip>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}

        {/* Bot Cards View (Mobile-friendly alternative) */}
        <Box sx={{ display: { xs: 'block', md: 'none' }, mt: 2 }}>
          {bots.map((bot) => (
            <Card key={bot.pid} variant="outlined" sx={{ mb: 2 }}>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Chip
                    label={getBotTypeLabel(bot.type)}
                    size="small"
                    color={getBotTypeColor(bot.type)}
                  />
                  <Chip
                    label={bot.status}
                    size="small"
                    color={bot.status === 'running' ? 'success' : 'default'}
                    variant="outlined"
                  />
                </Box>

                <Typography variant="body2" color="text.secondary" gutterBottom>
                  PID: {bot.pid} • Started: {new Date(bot.startedAt).toLocaleString()}
                </Typography>

                <Box sx={{ display: 'flex', gap: 2, my: 1 }}>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Uptime
                    </Typography>
                    <Typography variant="body2">{formatUptime(bot.uptime)}</Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      CPU
                    </Typography>
                    <Typography variant="body2">{bot.cpuPercent?.toFixed(1) || '0.0'}%</Typography>
                  </Box>
                  <Box>
                    <Typography variant="caption" color="text.secondary">
                      Memory
                    </Typography>
                    <Typography variant="body2">{formatMemory(bot.memoryMb)}</Typography>
                  </Box>
                </Box>

                {bot.type !== 'webui' && (
                  <Button
                    fullWidth
                    variant="outlined"
                    color="error"
                    size="small"
                    startIcon={<Stop />}
                    onClick={() => handleStopClick(bot)}
                    disabled={loading}
                  >
                    Stop Bot
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </Box>

        {/* Command Reference */}
        {bots.length > 0 && (
          <Box sx={{ mt: 2, p: 1, bgcolor: 'action.hover', borderRadius: 1 }}>
            <Typography variant="caption" color="text.secondary">
              <strong>Tip:</strong> Bots are automatically detected from running Python processes.
              The WebUI backend cannot be stopped from this interface for safety.
            </Typography>
          </Box>
        )}
      </CardContent>

      {/* Confirmation Dialog */}
      <Dialog
        open={confirmDialog.open}
        onClose={() => setConfirmDialog({ open: false, bot: null })}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Confirm Stop Bot</DialogTitle>
        <DialogContent>
          <Typography>Are you sure you want to stop the following bot?</Typography>
          {confirmDialog.bot && (
            <Box sx={{ mt: 2, p: 2, bgcolor: 'action.hover', borderRadius: 1 }}>
              <Typography variant="body2">
                <strong>Type:</strong> {getBotTypeLabel(confirmDialog.bot.type)}
              </Typography>
              <Typography variant="body2">
                <strong>PID:</strong> {confirmDialog.bot.pid}
              </Typography>
              <Typography variant="body2">
                <strong>Command:</strong> {confirmDialog.bot.command}
              </Typography>
              <Typography variant="body2">
                <strong>Uptime:</strong> {formatUptime(confirmDialog.bot.uptime)}
              </Typography>
            </Box>
          )}
          <Alert severity="warning" sx={{ mt: 2 }}>
            This will send a SIGTERM signal to the process. If it doesn't respond within 5 seconds,
            a SIGKILL will be sent.
          </Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDialog({ open: false, bot: null })} disabled={loading}>
            Cancel
          </Button>
          <Button
            onClick={() => stopBot(confirmDialog.bot.pid)}
            color="error"
            variant="contained"
            disabled={loading}
            startIcon={loading ? <CircularProgress size={16} /> : <Stop />}
          >
            {loading ? 'Stopping...' : 'Stop Bot'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar Notifications */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          severity={snackbar.severity}
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>

      {/* CSS Animation for rotating refresh icon */}
      <style>
        {`
          @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
        `}
      </style>
    </Card>
  );
};

export default BotManagerPanel;
