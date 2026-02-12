import React, { useState, useEffect, useCallback, useRef } from 'react';
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
  Divider,
  Collapse,
  Tab,
  Tabs,
  Snackbar,
  LinearProgress,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  Refresh,
  Info,
  DeleteOutline,
  CheckCircle,
  ContentCopy,
  Wifi,
  WifiOff,
  PlayArrow,
  BugReport,
  Link as LinkIcon,
  LinkOff,
  ExpandMore,
  ExpandLess,
  Warning,
  CloudDone,
  CloudOff,
  Science,
  HealthAndSafety,
  Settings,
  Speed,
  History,
} from '@mui/icons-material';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5555';

// ──────────────────────────────────────────────────
//  StatusDot: Green/Yellow/Red indicator
// ──────────────────────────────────────────────────
const StatusDot = ({ status, label, tooltip }) => {
  const colors = {
    green: '#4caf50',
    yellow: '#ff9800',
    red: '#f44336',
    grey: '#9e9e9e',
  };
  return (
    <Tooltip title={tooltip || label}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <Box
          sx={{
            width: 10, height: 10, borderRadius: '50%',
            bgcolor: colors[status] || colors.grey,
            boxShadow: status === 'green' ? '0 0 6px #4caf50' : 'none',
          }}
        />
        <Typography variant="caption" color="textSecondary">{label}</Typography>
      </Box>
    </Tooltip>
  );
};

// ──────────────────────────────────────────────────
//  Main Component
// ──────────────────────────────────────────────────
const TradingViewSignals = () => {
  const [signals, setSignals] = useState([]);
  const [stats, setStats] = useState(null);
  const [health, setHealth] = useState(null);
  const [webhookLogs, setWebhookLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [configDialogOpen, setConfigDialogOpen] = useState(false);
  const [webhookConfig, setWebhookConfig] = useState(null);
  const [socketConnected, setSocketConnected] = useState(false);
  const [activeTab, setActiveTab] = useState(0);
  const [showDiagnostics, setShowDiagnostics] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [testLoading, setTestLoading] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'info' });
  const [filter, setFilter] = useState({ action: '', symbol: '', strategy: '', limit: 50 });

  const socketRef = useRef(null);
  const signalAudioRef = useRef(null);

  // ── API Calls ──

  const fetchSignals = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const queryParams = new URLSearchParams();
      if (filter.action) queryParams.append('action', filter.action);
      if (filter.symbol) queryParams.append('symbol', filter.symbol);
      if (filter.strategy) queryParams.append('strategy', filter.strategy);
      queryParams.append('limit', filter.limit);
      const resp = await fetch(`${API_URL}/api/tradingview/signals?${queryParams}`);
      const data = await resp.json();
      if (data.success) setSignals(data.signals);
      else setError(data.error || 'Failed to fetch signals');
    } catch (err) {
      setError(`Failed to fetch signals: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  const fetchStats = useCallback(async () => {
    try {
      const resp = await fetch(`${API_URL}/api/tradingview/signals/stats`);
      const data = await resp.json();
      if (data.success) setStats(data.stats);
    } catch (err) { /* ignore */ }
  }, []);

  const fetchHealth = useCallback(async () => {
    try {
      const resp = await fetch(`${API_URL}/api/tradingview/health`);
      const data = await resp.json();
      if (data.success) setHealth(data.health);
    } catch (err) { /* ignore */ }
  }, []);

  const fetchWebhookConfig = useCallback(async () => {
    try {
      const resp = await fetch(`${API_URL}/api/tradingview/config`);
      const data = await resp.json();
      if (data.success) setWebhookConfig(data.config);
    } catch (err) { /* ignore */ }
  }, []);

  const fetchWebhookLogs = useCallback(async () => {
    try {
      const resp = await fetch(`${API_URL}/api/tradingview/webhook-logs?limit=30`);
      const data = await resp.json();
      if (data.success) setWebhookLogs(data.logs);
    } catch (err) { /* ignore */ }
  }, []);

  const deleteSignal = async (signalId) => {
    if (!window.confirm('Delete this signal?')) return;
    try {
      const resp = await fetch(`${API_URL}/api/tradingview/signals/${signalId}`, { method: 'DELETE' });
      const data = await resp.json();
      if (data.success) {
        fetchSignals();
        fetchStats();
        setSnackbar({ open: true, message: 'Signal deleted', severity: 'success' });
      } else {
        setError(data.error || 'Failed to delete');
      }
    } catch (err) {
      setError(`Delete failed: ${err.message}`);
    }
  };

  const sendTestSignal = async () => {
    setTestLoading(true);
    setTestResult(null);
    try {
      const resp = await fetch(`${API_URL}/api/tradingview/test-signal`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: 'BTCUSD', action: 'buy', price: 99999.99 }),
      });
      const data = await resp.json();
      setTestResult(data);
      if (data.success) {
        setSnackbar({ open: true, message: 'Test signal sent successfully!', severity: 'success' });
        fetchSignals();
        fetchStats();
      } else {
        setSnackbar({ open: true, message: `Test failed: ${data.error}`, severity: 'error' });
      }
    } catch (err) {
      setTestResult({ success: false, error: err.message });
      setSnackbar({ open: true, message: `Test error: ${err.message}`, severity: 'error' });
    } finally {
      setTestLoading(false);
    }
  };

  // ── WebSocket & Init ──

  useEffect(() => {
    fetchSignals();
    fetchStats();
    fetchHealth();
    fetchWebhookConfig();

    const socket = io(API_URL, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: Infinity,
    });
    socketRef.current = socket;

    socket.on('connect', () => {
      setSocketConnected(true);
    });

    socket.on('disconnect', () => {
      setSocketConnected(false);
    });

    socket.on('tradingview_signal', (signal) => {
      setSignals(prev => [signal, ...prev.slice(0, 199)]);
      fetchStats();
      fetchHealth();

      // Browser notification
      if ('Notification' in window && Notification.permission === 'granted') {
        const icon = signal.action === 'buy' ? '🟢' : '🔴';
        new Notification(`${icon} ${signal.action.toUpperCase()} Signal`, {
          body: `${signal.symbol} @ $${Number(signal.price).toLocaleString()} (${signal.strategy})`,
          icon: '/favicon.ico',
        });
      }
    });

    // Health poll every 30s
    const healthInterval = setInterval(() => {
      fetchHealth();
      fetchStats();
    }, 30000);

    // Signal poll every 60s (backup)
    const signalInterval = setInterval(fetchSignals, 60000);

    // Request notification permission
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }

    return () => {
      socket.disconnect();
      clearInterval(healthInterval);
      clearInterval(signalInterval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Refetch signals when filter changes
  useEffect(() => { fetchSignals(); }, [filter, fetchSignals]);

  const formatTime = (ts) => {
    if (!ts) return 'N/A';
    try {
      const d = new Date(ts.endsWith('Z') ? ts : ts + 'Z');
      return d.toLocaleString();
    } catch { return ts; }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setSnackbar({ open: true, message: 'Copied to clipboard!', severity: 'info' });
  };

  // ── Overall status color ──
  const getOverallStatus = () => {
    if (!health) return 'grey';
    if (!health.server_running) return 'red';
    if (!health.tunnel_active) return 'yellow';
    if (health.signals_24h > 0) return 'green';
    return 'yellow';
  };

  // ─────────────────────────────────────────────────────────
  //  RENDER
  // ─────────────────────────────────────────────────────────

  return (
    <Box sx={{ p: 2 }}>
      {/* ━━━ HEADER ━━━ */}
      <Card sx={{ mb: 2 }}>
        <CardContent sx={{ pb: '12px !important' }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Typography variant="h5" sx={{ fontWeight: 'bold' }}>
                TradingView Signals
              </Typography>
              {/* Status indicators */}
              <StatusDot
                status={health?.server_running ? 'green' : 'red'}
                label="Server"
                tooltip={health?.server_running ? 'Backend server running' : 'Backend server down'}
              />
              <StatusDot
                status={health?.tunnel_active ? 'green' : 'red'}
                label="Tunnel"
                tooltip={health?.tunnel_active ? `Tunnel: ${health.tunnel_url}` : 'No tunnel active — TradingView cannot reach this server'}
              />
              <StatusDot
                status={socketConnected ? 'green' : 'red'}
                label="WS"
                tooltip={socketConnected ? 'WebSocket connected (real-time)' : 'WebSocket disconnected'}
              />
            </Box>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
              <Button size="small" variant="outlined" startIcon={<Science />}
                onClick={sendTestSignal} disabled={testLoading}
              >
                {testLoading ? 'Sending...' : 'Test Signal'}
              </Button>
              <Button size="small" variant="outlined" startIcon={<BugReport />}
                onClick={() => { setShowDiagnostics(!showDiagnostics); if (!showDiagnostics) fetchWebhookLogs(); }}
              >
                Diagnostics
              </Button>
              <Button size="small" variant="outlined" startIcon={<Settings />}
                onClick={() => { setConfigDialogOpen(true); fetchWebhookConfig(); }}
              >
                Setup
              </Button>
              <Button size="small" variant="contained" startIcon={<Refresh />}
                onClick={() => { fetchSignals(); fetchStats(); fetchHealth(); }}
                disabled={loading}
              >
                Refresh
              </Button>
            </Box>
          </Box>

          {/* ━━━ TUNNEL WARNING ━━━ */}
          {health && !health.tunnel_active && (
            <Alert severity="warning" sx={{ mt: 1.5 }} icon={<LinkOff />}>
              <strong>No tunnel detected!</strong> TradingView webhooks cannot reach this server.
              Start ngrok: <code style={{ background: '#fff3cd', padding: '2px 6px', borderRadius: 3 }}>ngrok http 5555</code>
              {' '}then copy the HTTPS URL to your TradingView alert webhook setting.
            </Alert>
          )}

          {/* Webhook URL display */}
          {health?.webhook_url && (
            <Box sx={{ mt: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
              <Chip icon={health.tunnel_active ? <LinkIcon /> : <LinkOff />}
                label={health.webhook_url} size="small" variant="outlined"
                color={health.tunnel_active ? 'success' : 'default'}
                sx={{ fontFamily: 'monospace', fontSize: '0.75rem', maxWidth: 500 }}
              />
              <Tooltip title="Copy webhook URL">
                <IconButton size="small" onClick={() => copyToClipboard(health.webhook_url)}>
                  <ContentCopy fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
          )}
        </CardContent>
      </Card>

      {/* ━━━ DIAGNOSTICS PANEL (collapsible) ━━━ */}
      <Collapse in={showDiagnostics}>
        <Card sx={{ mb: 2, border: '1px solid #e0e0e0' }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>Diagnostics & Health</Typography>
            <Tabs value={activeTab} onChange={(_, v) => { setActiveTab(v); if (v === 1) fetchWebhookLogs(); }}
              sx={{ mb: 2 }} variant="scrollable" scrollButtons="auto"
            >
              <Tab label="Health Status" icon={<HealthAndSafety />} iconPosition="start" />
              <Tab label="Webhook Logs" icon={<History />} iconPosition="start" />
            </Tabs>

            {/* ── Tab 0: Health ── */}
            {activeTab === 0 && health && (
              <Grid container spacing={2}>
                <Grid item xs={12} md={6}>
                  <Paper sx={{ p: 2 }}>
                    <Typography variant="subtitle2" gutterBottom>Pipeline Status</Typography>
                    <Table size="small">
                      <TableBody>
                        {[
                          ['Server', health.server_running ? 'Running' : 'DOWN', health.server_running ? 'green' : 'red'],
                          ['Tunnel', health.tunnel_active ? 'Active' : 'Not Active', health.tunnel_active ? 'green' : 'red'],
                          ['WebSocket', socketConnected ? 'Connected' : 'Disconnected', socketConnected ? 'green' : 'red'],
                          ['IP Whitelist', health.ip_whitelist_enabled ? 'Enabled' : 'Disabled', 'grey'],
                          ['Webhook Secret', health.webhook_secret_configured ? 'Configured' : 'Not Set', 'grey'],
                          ['Dedup Window', `${health.dedup_window_seconds}s`, 'grey'],
                          ['Rate Limit', `${health.rate_limit_per_minute}/min`, 'grey'],
                        ].map(([label, value, color]) => (
                          <TableRow key={label}>
                            <TableCell sx={{ border: 0, py: 0.5, fontWeight: 500 }}>{label}</TableCell>
                            <TableCell sx={{ border: 0, py: 0.5 }}>
                              <Chip label={value} size="small" sx={{
                                bgcolor: color === 'green' ? 'rgba(76, 175, 80, 0.15)' : color === 'red' ? 'rgba(244, 67, 54, 0.15)' : 'rgba(158, 158, 158, 0.1)',
                                color: color === 'green' ? '#81c784' : color === 'red' ? '#e57373' : '#bdbdbd',
                                fontWeight: 500,
                              }} />
                            </TableCell>
                          </TableRow>
                        ))}  
                      </TableBody>
                    </Table>
                  </Paper>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Paper sx={{ p: 2 }}>
                    <Typography variant="subtitle2" gutterBottom>Last Activity</Typography>
                    <Table size="small">
                      <TableBody>
                        {[
                          ['Last Signal', health.last_signal_age || 'Never'],
                          ['Last Symbol', health.last_signal_symbol || '—'],
                          ['Last Action', health.last_signal_action?.toUpperCase() || '—'],
                          ['Last Webhook', health.last_webhook_age || 'Never'],
                          ['Webhook IP', health.last_webhook_ip || '—'],
                          ['Webhook Status', health.last_webhook_status || '—'],
                          ['Signals (24h)', String(health.signals_24h || 0)],
                          ['Total Signals', String(health.total_signals || 0)],
                        ].map(([label, value]) => (
                          <TableRow key={label}>
                            <TableCell sx={{ border: 0, py: 0.5, fontWeight: 500 }}>{label}</TableCell>
                            <TableCell sx={{ border: 0, py: 0.5, fontFamily: 'monospace', fontSize: '0.85rem' }}>{value}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </Paper>
                </Grid>
                {health.tunnel_url && (
                  <Grid item xs={12}>
                    <Alert severity="success" icon={<CloudDone />}>
                      Tunnel active: <strong>{health.tunnel_url}</strong>
                      <br />
                      Webhook URL: <code>{health.webhook_url}</code>
                      <Tooltip title="Copy webhook URL">
                        <IconButton size="small" sx={{ ml: 1 }} onClick={() => copyToClipboard(health.webhook_url)}>
                          <ContentCopy fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </Alert>
                  </Grid>
                )}
                {health?.tradingview_ips && (
                  <Grid item xs={12}>
                    <Alert severity="info" sx={{ fontSize: '0.8rem' }}>
                      TradingView IPs: {health.tradingview_ips.join(', ')}
                      {health.ip_whitelist_enabled
                        ? ' (whitelist ENFORCED - only these IPs accepted)'
                        : ' (whitelist NOT enforced - all IPs accepted for testing)'}
                    </Alert>
                  </Grid>
                )}
              </Grid>
            )}

            {/* ── Tab 1: Webhook Logs ── */}
            {activeTab === 1 && (
              <Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="subtitle2">Recent Webhook Requests</Typography>
                  <Button size="small" startIcon={<Refresh />} onClick={fetchWebhookLogs}>Refresh</Button>
                </Box>
                {webhookLogs.length === 0 ? (
                  <Alert severity="info">No webhook requests logged yet.</Alert>
                ) : (
                  <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 400 }}>
                    <Table size="small" stickyHeader>
                      <TableHead>
                        <TableRow>
                          <TableCell><strong>Time</strong></TableCell>
                          <TableCell><strong>IP</strong></TableCell>
                          <TableCell><strong>Status</strong></TableCell>
                          <TableCell><strong>Signal</strong></TableCell>
                          <TableCell><strong>Error</strong></TableCell>
                          <TableCell align="right"><strong>ms</strong></TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {webhookLogs.map((log) => (
                          <TableRow key={log.id} sx={{
                            bgcolor: log.parsed_ok ? 'inherit' : 'rgba(255, 152, 0, 0.1)',
                          }}>  
                            <TableCell sx={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                              {formatTime(log.received_at)}
                            </TableCell>
                            <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                              {log.source_ip}
                            </TableCell>
                            <TableCell>
                              <Chip
                                label={log.response_code}
                                size="small"
                                color={log.response_code === 200 ? 'success' : 'error'}
                                sx={{ fontWeight: 600, minWidth: 45 }}
                              />
                            </TableCell>
                            <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.7rem' }}>
                              {log.signal_id || '—'}
                            </TableCell>
                            <TableCell sx={{ fontSize: '0.75rem', color: '#c62828', maxWidth: 200 }}>
                              <Typography variant="body2" noWrap sx={{ maxWidth: 200, fontSize: '0.75rem' }}>
                                {log.error_message || '—'}
                              </Typography>
                            </TableCell>
                            <TableCell align="right" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                              {log.processing_ms?.toFixed(1)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                )}
              </Box>
            )}
          </CardContent>
        </Card>
      </Collapse>

      {/* ━━━ STATS CARDS ━━━ */}
      {stats && (
        <Grid container spacing={1.5} sx={{ mb: 2 }}>
          {[
            { label: 'Total', value: stats.total_signals, color: 'rgba(158, 158, 158, 0.08)', textColor: '#bdbdbd' },
            { label: 'Buy', value: stats.by_action?.buy || 0, color: 'rgba(76, 175, 80, 0.12)', textColor: '#81c784' },
            { label: 'Sell', value: stats.by_action?.sell || 0, color: 'rgba(244, 67, 54, 0.12)', textColor: '#e57373' },
            { label: '24h', value: stats.last_24h, color: 'rgba(33, 150, 243, 0.12)', textColor: '#64b5f6' },
          ].map(({ label, value, color, textColor }) => (
            <Grid item xs={6} md={3} key={label}>
              <Paper sx={{ p: 1.5, bgcolor: color, textAlign: 'center' }}>  
                <Typography variant="caption" color="textSecondary">{label}</Typography>
                <Typography variant="h5" sx={{ fontWeight: 700, color: textColor }}>{value}</Typography>
              </Paper>
            </Grid>
          ))}
        </Grid>
      )}

      {/* ━━━ FILTERS ━━━ */}
      <Box sx={{ display: 'flex', gap: 1.5, mb: 2, flexWrap: 'wrap' }}>
        <FormControl size="small" sx={{ minWidth: 100 }}>
          <InputLabel>Action</InputLabel>
          <Select value={filter.action} label="Action"
            onChange={(e) => setFilter({ ...filter, action: e.target.value })}
          >
            <MenuItem value="">All</MenuItem>
            <MenuItem value="buy">Buy</MenuItem>
            <MenuItem value="sell">Sell</MenuItem>
          </Select>
        </FormControl>
        <TextField size="small" label="Symbol" value={filter.symbol}
          onChange={(e) => setFilter({ ...filter, symbol: e.target.value.toUpperCase() })}
          placeholder="e.g. BTCUSD" sx={{ width: 130 }}
        />
        <TextField size="small" label="Strategy" value={filter.strategy}
          onChange={(e) => setFilter({ ...filter, strategy: e.target.value })}
          placeholder="e.g. RSI" sx={{ width: 130 }}
        />
        <FormControl size="small" sx={{ minWidth: 80 }}>
          <InputLabel>Limit</InputLabel>
          <Select value={filter.limit} label="Limit"
            onChange={(e) => setFilter({ ...filter, limit: e.target.value })}
          >
            <MenuItem value={25}>25</MenuItem>
            <MenuItem value={50}>50</MenuItem>
            <MenuItem value={100}>100</MenuItem>
          </Select>
        </FormControl>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>
      )}

      {/* ━━━ SIGNALS TABLE ━━━ */}
      <Card>
        <CardContent sx={{ p: 1, '&:last-child': { pb: 1 } }}>
          {loading && <LinearProgress sx={{ mb: 1 }} />}
          {!loading && signals.length === 0 ? (
            <Alert severity="info" sx={{ m: 1 }}>
              No signals received yet. Start ngrok, configure TradingView alerts, or click "Test Signal" to verify the pipeline.
            </Alert>
          ) : (
            <TableContainer sx={{ maxHeight: 500 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow sx={{ '& th': { bgcolor: 'rgba(0, 0, 0, 0.3)', fontWeight: 700, fontSize: '0.8rem' } }}>
                    <TableCell>Time</TableCell>  
                    <TableCell>Symbol</TableCell>
                    <TableCell>Action</TableCell>
                    <TableCell align="right">Price</TableCell>
                    <TableCell>Strategy</TableCell>
                    <TableCell>TF</TableCell>
                    <TableCell>Source</TableCell>
                    <TableCell>Message</TableCell>
                    <TableCell align="center" sx={{ width: 40 }}></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {signals.map((signal, idx) => {
                    const isTvIp = signal.source_ip && ['52.89.214.238', '34.212.75.30', '54.218.53.128', '52.32.178.7'].includes(signal.source_ip);
                    const isTest = signal.strategy === 'Pipeline_Test' || signal.source_ip === 'test-pipeline';
                    return (
                      <TableRow
                        key={signal.id || idx}
                        sx={{
                          '&:hover': { bgcolor: 'rgba(255, 255, 255, 0.05)' },
                          bgcolor: isTest ? 'rgba(156, 39, 176, 0.08)' : signal.processed ? 'rgba(158, 158, 158, 0.06)' : 'inherit',
                          transition: 'background-color 0.3s',
                        }}
                      >  
                        <TableCell sx={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                          {formatTime(signal.created_at)}
                        </TableCell>
                        <TableCell>
                          <Chip label={signal.symbol || '?'} size="small" variant="outlined" sx={{ fontWeight: 600 }} />
                        </TableCell>
                        <TableCell>
                          <Chip
                            icon={signal.action === 'buy' ? <TrendingUp /> : <TrendingDown />}
                            label={(signal.action || '?').toUpperCase()}
                            size="small"
                            color={signal.action === 'buy' ? 'success' : 'error'}
                            sx={{ fontWeight: 600 }}
                          />
                        </TableCell>
                        <TableCell align="right" sx={{ fontWeight: 600, fontFamily: 'monospace' }}>
                          ${Number(signal.price || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </TableCell>
                        <TableCell sx={{ fontSize: '0.8rem' }}>{signal.strategy || '—'}</TableCell>
                        <TableCell sx={{ fontSize: '0.8rem' }}>{signal.timeframe || '—'}</TableCell>
                        <TableCell>
                          {isTest ? (
                            <Chip label="TEST" size="small" sx={{ bgcolor: 'rgba(156, 39, 176, 0.2)', color: '#ce93d8', fontSize: '0.7rem' }} />
                          ) : isTvIp ? (  
                            <Chip label="TV" size="small" color="primary" sx={{ fontSize: '0.7rem' }} />
                          ) : (
                            <Chip label={signal.source_ip === '127.0.0.1' ? 'Local' : 'Ext'} size="small"
                              variant="outlined" sx={{ fontSize: '0.7rem' }} />
                          )}
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" noWrap sx={{ maxWidth: 180, fontSize: '0.8rem' }}>
                            {signal.message || '—'}
                          </Typography>
                        </TableCell>
                        <TableCell align="center">
                          <IconButton size="small" color="error" onClick={() => deleteSignal(signal.id)}>
                            <DeleteOutline fontSize="small" />
                          </IconButton>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </CardContent>
      </Card>

      {/* ━━━ SETUP DIALOG ━━━ */}
      <Dialog open={configDialogOpen} onClose={() => setConfigDialogOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>TradingView Webhook Setup</DialogTitle>
        <DialogContent>
          {webhookConfig && (
            <Box sx={{ mt: 1 }}>
              {/* Tunnel status */}
              {webhookConfig.tunnel_active ? (
                <Alert severity="success" sx={{ mb: 2 }} icon={<CloudDone />}>
                  Tunnel active! TradingView can send webhooks to your server.
                </Alert>
              ) : (
                <Alert severity="error" sx={{ mb: 2 }} icon={<CloudOff />}>
                  <strong>No tunnel detected.</strong> Run <code>ngrok http 5555</code> in a terminal, then refresh.
                </Alert>
              )}

              {/* Webhook URL */}
              <Typography variant="subtitle2" gutterBottom>Webhook URL (paste into TradingView):</Typography>
              <Box sx={{ display: 'flex', gap: 1, mb: 3 }}>
                <TextField fullWidth size="small" value={webhookConfig.webhook_url}
                  InputProps={{ readOnly: true, sx: { fontFamily: 'monospace', fontSize: '0.85rem' } }}
                />
                <Tooltip title="Copy">
                  <IconButton onClick={() => copyToClipboard(webhookConfig.webhook_url)}><ContentCopy /></IconButton>
                </Tooltip>
              </Box>

              {/* Setup steps */}
              <Typography variant="subtitle2" gutterBottom>Quick Setup Steps:</Typography>
              <Paper sx={{ p: 2, mb: 3, bgcolor: 'rgba(255, 255, 255, 0.03)' }}>
                {(webhookConfig.setup_steps || []).map((step, i) => (
                  <Typography key={i} variant="body2" sx={{ mb: 0.5, fontFamily: 'monospace', fontSize: '0.8rem' }}>
                    {step}
                  </Typography>
                ))}
              </Paper>

              {/* Payload formats */}
              <Typography variant="subtitle2" gutterBottom>Accepted Payload Formats:</Typography>
              <Paper sx={{ p: 2, mb: 3, bgcolor: 'rgba(255, 255, 255, 0.03)' }}>
                {(webhookConfig.alternative_formats || []).map((fmt, i) => (
                  <Box key={i} sx={{ display: 'flex', gap: 1, mb: 0.5, alignItems: 'center' }}>
                    <Chip label={`Format ${i + 1}`} size="small" variant="outlined" sx={{ minWidth: 75 }} />
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{fmt}</Typography>
                  </Box>
                ))}
              </Paper>

              {/* Pine Script */}
              <Typography variant="subtitle2" gutterBottom>Pine Script Example:</Typography>
              <Paper sx={{ p: 2, bgcolor: '#263238', color: '#e0e0e0', fontFamily: 'monospace', fontSize: '0.78rem', overflow: 'auto', maxHeight: 300, borderRadius: 2 }}>
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{webhookConfig.pine_script_example}</pre>
              </Paper>

              {/* Example payload */}
              <Typography variant="subtitle2" sx={{ mt: 2 }} gutterBottom>Example JSON Payload:</Typography>
              <Paper sx={{ p: 2, bgcolor: '#263238', color: '#e0e0e0', fontFamily: 'monospace', fontSize: '0.8rem', borderRadius: 2 }}>
                <pre style={{ margin: 0 }}>{JSON.stringify(webhookConfig.example_payload, null, 2)}</pre>
              </Paper>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => { fetchWebhookConfig(); fetchHealth(); }}>Refresh</Button>
          <Button onClick={() => setConfigDialogOpen(false)} variant="contained">Close</Button>
        </DialogActions>
      </Dialog>

      {/* ━━━ SNACKBAR ━━━ */}
      <Snackbar
        open={snackbar.open} autoHideDuration={3000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert severity={snackbar.severity} onClose={() => setSnackbar({ ...snackbar, open: false })}
          sx={{ width: '100%' }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default TradingViewSignals;
