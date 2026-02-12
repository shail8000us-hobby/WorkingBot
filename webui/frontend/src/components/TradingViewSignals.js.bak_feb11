import React, { useState, useEffect } from 'react';
import { io } from 'socket.io-client';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Button,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Grid,
  IconButton,
  Tooltip,
  CircularProgress,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Badge,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  Refresh,
  Info,
  DeleteOutline,
  FilterList,
  CheckCircle,
  ContentCopy,
  Wifi,
  WifiOff,
} from '@mui/icons-material';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5555';

const TradingViewSignals = () => {
  const [signals, setSignals] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [configDialogOpen, setConfigDialogOpen] = useState(false);
  const [webhookConfig, setWebhookConfig] = useState(null);
  const [socketConnected, setSocketConnected] = useState(false);
  const [filter, setFilter] = useState({
    action: '',
    symbol: '',
    strategy: '',
    limit: 50
  });

  // Fetch signals
  const fetchSignals = async () => {
    setLoading(true);
    setError(null);
    try {
      const queryParams = new URLSearchParams();
      if (filter.action) queryParams.append('action', filter.action);
      if (filter.symbol) queryParams.append('symbol', filter.symbol);
      if (filter.strategy) queryParams.append('strategy', filter.strategy);
      queryParams.append('limit', filter.limit);

      const response = await fetch(`${API_URL}/api/tradingview/signals?${queryParams}`);
      const data = await response.json();

      if (data.success) {
        setSignals(data.signals);
      } else {
        setError(data.error || 'Failed to fetch signals');
      }
    } catch (err) {
      setError(`Failed to fetch signals: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Fetch stats
  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_URL}/api/tradingview/signals/stats`);
      const data = await response.json();

      if (data.success) {
        setStats(data.stats);
      }
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  };

  // Fetch webhook config
  const fetchWebhookConfig = async () => {
    try {
      const response = await fetch(`${API_URL}/api/tradingview/config`);
      const data = await response.json();

      if (data.success) {
        setWebhookConfig(data.config);
      }
    } catch (err) {
      console.error('Failed to fetch config:', err);
    }
  };

  // Delete signal
  const deleteSignal = async (signalId) => {
    if (!window.confirm('Delete this signal?')) return;

    try {
      const response = await fetch(`${API_URL}/api/tradingview/signals/${signalId}`, {
        method: 'DELETE'
      });
      const data = await response.json();

      if (data.success) {
        fetchSignals();
        fetchStats();
      } else {
        setError(data.error || 'Failed to delete signal');
      }
    } catch (err) {
      setError(`Failed to delete signal: ${err.message}`);
    }
  };

  useEffect(() => {
    fetchSignals();
    fetchStats();
    fetchWebhookConfig();

    // Setup WebSocket connection for real-time updates
    const socket = io(API_URL, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 5,
    });

    socket.on('connect', () => {
      console.log('✅ TradingView WebSocket connected');
      setSocketConnected(true);
    });

    socket.on('disconnect', () => {
      console.log('❌ TradingView WebSocket disconnected');
      setSocketConnected(false);
    });

    // Listen for new signals
    socket.on('tradingview_signal', (signal) => {
      console.log('📊 New signal received:', signal);
      
      // Add signal to the beginning of the list
      setSignals(prev => [signal, ...prev]);
      
      // Update stats
      fetchStats();
      
      // Show notification for sell signals (more important)
      if (signal.action === 'sell') {
        // Optional: Add browser notification
        if ('Notification' in window && Notification.permission === 'granted') {
          new Notification('🔻 SELL Signal', {
            body: `${signal.symbol} @ $${signal.price.toLocaleString()}`,
            icon: '/favicon.ico'
          });
        }
      }
    });

    // Auto-refresh every 30 seconds (backup in case WebSocket fails)
    const interval = setInterval(() => {
      fetchSignals();
      fetchStats();
    }, 30000);

    return () => {
      socket.disconnect();
      clearInterval(interval);
    };
  }, [filter]);

  // Format timestamp
  const formatTime = (timestamp) => {
    if (!timestamp) return 'N/A';
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  // Copy to clipboard
  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
  };

  return (
    <Box sx={{ p: 3 }}>
      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Typography variant="h5" component="div" sx={{ fontWeight: 'bold' }}>
                📊 TradingView Signals
              </Typography>
              <Tooltip title={socketConnected ? 'WebSocket Connected - Real-time updates active' : 'WebSocket Disconnected'}>
                <IconButton size="small" color={socketConnected ? 'success' : 'error'}>
                  {socketConnected ? <Wifi /> : <WifiOff />}
                </IconButton>
              </Tooltip>
            </Box>
            <Box>
              <Button
                variant="outlined"
                startIcon={<Info />}
                onClick={() => setConfigDialogOpen(true)}
                sx={{ mr: 1 }}
              >
                Setup
              </Button>
              <Button
                variant="contained"
                startIcon={<Refresh />}
                onClick={() => {
                  fetchSignals();
                  fetchStats();
                }}
                disabled={loading}
              >
                Refresh
              </Button>
            </Box>
          </Box>

          {/* Stats */}
          {stats && (
            <Grid container spacing={2} sx={{ mb: 3 }}>
              <Grid item xs={12} md={3}>
                <Paper sx={{ p: 2, bgcolor: '#f5f5f5' }}>
                  <Typography variant="body2" color="textSecondary">Total Signals</Typography>
                  <Typography variant="h4">{stats.total_signals}</Typography>
                </Paper>
              </Grid>
              <Grid item xs={12} md={3}>
                <Paper sx={{ p: 2, bgcolor: '#e8f5e9' }}>
                  <Typography variant="body2" color="textSecondary">Buy Signals</Typography>
                  <Typography variant="h4" color="success.main">
                    {stats.by_action?.buy || 0}
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={12} md={3}>
                <Paper sx={{ p: 2, bgcolor: '#ffebee' }}>
                  <Typography variant="body2" color="textSecondary">Sell Signals</Typography>
                  <Typography variant="h4" color="error.main">
                    {stats.by_action?.sell || 0}
                  </Typography>
                </Paper>
              </Grid>
              <Grid item xs={12} md={3}>
                <Paper sx={{ p: 2, bgcolor: '#e3f2fd' }}>
                  <Typography variant="body2" color="textSecondary">Last 24h</Typography>
                  <Typography variant="h4" color="primary.main">
                    {stats.last_24h}
                  </Typography>
                </Paper>
              </Grid>
            </Grid>
          )}

          {/* Filters */}
          <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel>Action</InputLabel>
              <Select
                value={filter.action}
                label="Action"
                onChange={(e) => setFilter({ ...filter, action: e.target.value })}
              >
                <MenuItem value="">All</MenuItem>
                <MenuItem value="buy">Buy</MenuItem>
                <MenuItem value="sell">Sell</MenuItem>
              </Select>
            </FormControl>

            <TextField
              size="small"
              label="Symbol"
              value={filter.symbol}
              onChange={(e) => setFilter({ ...filter, symbol: e.target.value.toUpperCase() })}
              placeholder="e.g., BTCUSD"
            />

            <TextField
              size="small"
              label="Strategy"
              value={filter.strategy}
              onChange={(e) => setFilter({ ...filter, strategy: e.target.value })}
              placeholder="e.g., RSI_Strategy"
            />

            <FormControl size="small" sx={{ minWidth: 100 }}>
              <InputLabel>Limit</InputLabel>
              <Select
                value={filter.limit}
                label="Limit"
                onChange={(e) => setFilter({ ...filter, limit: e.target.value })}
              >
                <MenuItem value={25}>25</MenuItem>
                <MenuItem value={50}>50</MenuItem>
                <MenuItem value={100}>100</MenuItem>
              </Select>
            </FormControl>
          </Box>

          {error && (
            <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
              {error}
            </Alert>
          )}

          {/* Signals Table */}
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
              <CircularProgress />
            </Box>
          ) : signals.length === 0 ? (
            <Alert severity="info">
              No signals received yet. Configure your TradingView alerts to send webhooks to this server.
            </Alert>
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow sx={{ bgcolor: '#f5f5f5' }}>
                    <TableCell><strong>Time</strong></TableCell>
                    <TableCell><strong>Symbol</strong></TableCell>
                    <TableCell><strong>Action</strong></TableCell>
                    <TableCell align="right"><strong>Price</strong></TableCell>
                    <TableCell><strong>Strategy</strong></TableCell>
                    <TableCell><strong>Timeframe</strong></TableCell>
                    <TableCell><strong>Message</strong></TableCell>
                    <TableCell align="center"><strong>Actions</strong></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {signals.map((signal) => (
                    <TableRow
                      key={signal.id}
                      sx={{
                        '&:hover': { bgcolor: '#f9f9f9' },
                        bgcolor: signal.processed ? '#f0f0f0' : 'inherit'
                      }}
                    >
                      <TableCell>{formatTime(signal.created_at)}</TableCell>
                      <TableCell>
                        <Chip
                          label={signal.symbol}
                          size="small"
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell>
                        <Chip
                          icon={signal.action === 'buy' ? <TrendingUp /> : <TrendingDown />}
                          label={signal.action.toUpperCase()}
                          size="small"
                          color={signal.action === 'buy' ? 'success' : 'error'}
                        />
                      </TableCell>
                      <TableCell align="right">
                        <strong>${signal.price?.toLocaleString()}</strong>
                      </TableCell>
                      <TableCell>{signal.strategy || 'N/A'}</TableCell>
                      <TableCell>{signal.timeframe || 'N/A'}</TableCell>
                      <TableCell>
                        <Typography variant="body2" noWrap sx={{ maxWidth: 200 }}>
                          {signal.message || '—'}
                        </Typography>
                      </TableCell>
                      <TableCell align="center">
                        <Tooltip title="Delete">
                          <IconButton
                            size="small"
                            color="error"
                            onClick={() => deleteSignal(signal.id)}
                          >
                            <DeleteOutline fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>

      {/* Configuration Dialog */}
      <Dialog
        open={configDialogOpen}
        onClose={() => setConfigDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>TradingView Webhook Setup</DialogTitle>
        <DialogContent>
          {webhookConfig && (
            <Box sx={{ mt: 2 }}>
              <Alert severity="info" sx={{ mb: 3 }}>
                Configure your TradingView alerts to send webhooks to this URL
              </Alert>

              <Box sx={{ mb: 3 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Webhook URL:
                </Typography>
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <TextField
                    fullWidth
                    size="small"
                    value={webhookConfig.webhook_url}
                    InputProps={{ readOnly: true }}
                  />
                  <Tooltip title="Copy URL">
                    <IconButton
                      onClick={() => copyToClipboard(webhookConfig.webhook_url)}
                    >
                      <ContentCopy />
                    </IconButton>
                  </Tooltip>
                </Box>
              </Box>

              <Box sx={{ mb: 3 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Pine Script Example:
                </Typography>
                <Paper sx={{ p: 2, bgcolor: '#f5f5f5', fontFamily: 'monospace', fontSize: '0.875rem', overflow: 'auto', maxHeight: 400 }}>
                  <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                    {webhookConfig.pine_script_example}
                  </pre>
                </Paper>
              </Box>

              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Expected JSON Payload:
                </Typography>
                <Paper sx={{ p: 2, bgcolor: '#f5f5f5', fontFamily: 'monospace', fontSize: '0.875rem' }}>
                  <pre style={{ margin: 0 }}>
                    {JSON.stringify(webhookConfig.example_payload, null, 2)}
                  </pre>
                </Paper>
              </Box>

              <Alert severity="success">
                <Typography variant="body2">
                  <strong>Supported Actions:</strong> {webhookConfig.supported_actions.join(', ')}
                </Typography>
              </Alert>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfigDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default TradingViewSignals;
