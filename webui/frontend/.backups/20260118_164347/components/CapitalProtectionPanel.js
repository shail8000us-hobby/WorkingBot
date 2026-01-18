import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Paper,
  LinearProgress,
  Chip,
  Alert,
  AlertTitle,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  Tab,
  CircularProgress,
  Divider,
  TextField,
  Snackbar,
  IconButton,
  Tooltip
} from '@mui/material';
import {
  Security as SecurityIcon,
  TrendingDown as TrendingDownIcon,
  Speed as SpeedIcon,
  AccountBalance as AccountBalanceIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  People as PeopleIcon,
  Shield as ShieldIcon,
  Book as BookIcon
} from '@mui/icons-material';
import ConfigSection from './ConfigSection';
import HelpIcon from './help/HelpIcon';
import DocumentationViewer from './DocumentationViewer';
import ConfigChangeConfirmDialog from './ConfigChangeConfirmDialog';
import { useSocket } from '../hooks/useSocket';
import apiClient, { APIClient } from '../utils/apiClient';
import EmergencyToggle from './EmergencyToggle';

// Configure apiClient for capital protection APIs
// Use origin-relative URL to work with localhost and Tailscale
const capitalApiClient = new APIClient({
  baseURL: window.location.origin
});

function CapitalProtectionPanel() {
  const [tabValue, setTabValue] = useState(0);
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState({
    equityFloor: null,
    drawdownCap: null,
    exposureLimiter: null,
    pendingBudget: null,
    configGuard: null
  });
  const [editing, setEditing] = useState({});
  const [saving, setSaving] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
  const [docsOpen, setDocsOpen] = useState(false);
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [pendingChanges, setPendingChanges] = useState(null);
  const [changesSummary, setChangesSummary] = useState(null);
  const socket = useSocket();

  const fetchAllData = useCallback(async () => {
    try {
      // Fetch all capital protection data using capitalApiClient
      const [equity, drawdown, exposure, budget, config] = await Promise.all([
        capitalApiClient.get('/api/capital/equity-floor/status'),
        capitalApiClient.get('/api/capital/drawdown/status'),
        capitalApiClient.get('/api/capital/exposure/status'),
        capitalApiClient.get('/api/capital/budget/status'),
        capitalApiClient.get('/api/capital/config-guard/status')
      ]);

      setData({
        equityFloor: equity.success ? equity.data : null,
        drawdownCap: drawdown.success ? drawdown.data : null,
        exposureLimiter: exposure.success ? exposure.data : null,
        pendingBudget: budget.success ? budget.data : null,
        configGuard: config.success ? config.data : null
      });

      setLoading(false);
    } catch (error) {
      console.error('Failed to fetch capital protection data:', error);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAllData();
    const interval = setInterval(fetchAllData, 5000); // Update every 5 seconds
    return () => clearInterval(interval);
  }, [fetchAllData]);

  useEffect(() => {
    if (!socket) return;

    const handleOrdersMemoryUpdate = () => {
      fetchAllData();
    };

    socket.on('orders_memory_update', handleOrdersMemoryUpdate);
    socket.on('reconciliation_update', handleOrdersMemoryUpdate);

    return () => {
      socket.off('orders_memory_update', handleOrdersMemoryUpdate);
      socket.off('reconciliation_update', handleOrdersMemoryUpdate);
    };
  }, [socket, fetchAllData]);

  const handleTabChange = (event, newValue) => {
    setTabValue(newValue);
  };

  const testApiConnection = async () => {
    try {
      const result = await capitalApiClient.get('/api/capital/exposure/status');
      console.log('API connection test successful:', result);
      return true;
    } catch (error) {
      console.error('API connection test failed:', error);
      return false;
    }
  };

  const handleSaveConfig = async (configUpdates, confirmed = false) => {
    setSaving(true);
    try {
      // Test API connection first
      const isConnected = await testApiConnection();
      if (!isConnected) {
        setSnackbar({
          open: true,
          message: '❌ Cannot connect to server. Please check if the backend is running.',
          severity: 'error'
        });
        return;
      }

      // Validate the data before sending
      if (!configUpdates || Object.keys(configUpdates).length === 0) {
        setSnackbar({
          open: true,
          message: '❌ No configuration changes to save',
          severity: 'error'
        });
        return;
      }

      // Convert string values to numbers where appropriate
      const processedUpdates = { ...configUpdates };
      if (processedUpdates.max_notional_per_minute) {
        processedUpdates.max_notional_per_minute = parseFloat(processedUpdates.max_notional_per_minute);
      }
      if (processedUpdates.max_tranches_per_minute) {
        processedUpdates.max_tranches_per_minute = parseInt(processedUpdates.max_tranches_per_minute);
      }

      // Add confirmed flag if this is a confirmed retry
      if (confirmed) {
        processedUpdates.confirmed = true;
      }

      console.log('Sending config update:', processedUpdates);
      const result = await capitalApiClient.post('/api/capital/update-config', processedUpdates);
      console.log('Received response:', result);

      // Check if backend requires confirmation
      if (result.require_confirmation) {
        // Show confirmation dialog with impact summary
        setConfirmDialogOpen(true);
        setPendingChanges(configUpdates);
        setChangesSummary(result.changes_summary);
        setSnackbar({
          open: true,
          message: '⚠️ Please review and confirm your changes',
          severity: 'info'
        });
        return;
      }

      if (result && result.success) {
        setSnackbar({
          open: true,
          message: `${result.message || '✅ Configuration saved successfully'}`,
          severity: 'success'
        });
        // Refresh data after successful save
        await fetchAllData();
        setEditing({});
      } else {
        setSnackbar({
          open: true,
          message: `❌ Failed to update: ${result?.error || 'Unknown error'}`,
          severity: 'error'
        });
      }
    } catch (error) {
      console.error('Error in handleSaveConfig:', error);
      setSnackbar({
        open: true,
        message: `❌ Error saving configuration: ${error.message}`,
        severity: 'error'
      });
    } finally {
      setSaving(false);
    }
  };

  const handleConfirmChanges = async () => {
    setConfirmDialogOpen(false);
    await handleSaveConfig(pendingChanges, true);
    setPendingChanges(null);
    setChangesSummary(null);
  };

  const handleCancelConfirm = () => {
    setConfirmDialogOpen(false);
    setPendingChanges(null);
    setChangesSummary(null);
    setSnackbar({
      open: true,
      message: 'Changes cancelled',
      severity: 'info'
    });
  };

  const renderOverview = () => (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" justifyContent="space-between" mb={3}>
          <Box display="flex" alignItems="center">
            <ShieldIcon sx={{ mr: 1, fontSize: 40, color: 'primary.main' }} />
            <Typography variant="h5">Capital Protection Overview</Typography>
          </Box>
          <Tooltip title="View Documentation">
            <IconButton 
              onClick={() => setDocsOpen(true)}
              color="primary"
              size="large"
            >
              <BookIcon />
            </IconButton>
          </Tooltip>
        </Box>

        <Alert severity="info" sx={{ mb: 3 }}>
          <AlertTitle>🛡️ Multiple Layers of Protection</AlertTitle>
          Your bot has 5 independent safety nets working together to protect your capital.
        </Alert>

        <Grid container spacing={2}>
          {/* Equity Floor Status */}
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 2, bgcolor: data.equityFloor?.breached ? 'error.dark' : 'background.default' }}>
              <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
                <Box display="flex" alignItems="center">
                  <SecurityIcon sx={{ mr: 1 }} />
                  <Typography variant="h6">💎 Equity Floor</Typography>
                </Box>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => setTabValue(1)}
                  startIcon={<SecurityIcon />}
                  sx={{ minWidth: 'auto', px: 2 }}
                >
                  Configure
                </Button>
              </Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Hard stop at minimum equity
              </Typography>
              {data.equityFloor ? (
                <>
                  <Typography variant="h4" sx={{ my: 1 }}>
                    ₹{data.equityFloor.current_equity?.toLocaleString() || 'N/A'}
                  </Typography>
                  <Typography variant="body2">
                    Floor: ₹{data.equityFloor.floor_inr?.toLocaleString() || '0'}
                  </Typography>
                  <Box mt={1} display="flex" gap={1} flexWrap="wrap">
                    {data.equityFloor.enabled ? (
                      <>
                        {data.equityFloor.breached ? (
                          <Chip label="🚨 BREACHED" color="error" size="small" />
                        ) : (
                          <Chip label="✅ SAFE" color="success" size="small" />
                        )}
                        <Chip label="ENABLED" color="primary" size="small" />
                      </>
                    ) : (
                      <Chip label="DISABLED" color="default" size="small" />
                    )}
                  </Box>
                </>
              ) : (
                <CircularProgress size={24} />
              )}
            </Paper>
          </Grid>

          {/* Drawdown Cap Status */}
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 2, bgcolor: data.drawdownCap?.protective_mode ? 'warning.dark' : 'background.default' }}>
              <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
                <Box display="flex" alignItems="center">
                  <TrendingDownIcon sx={{ mr: 1 }} />
                  <Typography variant="h6">📉 Drawdown Cap</Typography>
                </Box>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => setTabValue(2)}
                  startIcon={<TrendingDownIcon />}
                  sx={{ minWidth: 'auto', px: 2 }}
                >
                  Configure
                </Button>
              </Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                30-day rolling window protection
              </Typography>
              {data.drawdownCap ? (
                <>
                  <Typography variant="h4" sx={{ my: 1 }}>
                    {data.drawdownCap.current_drawdown_pct?.toFixed(1)}%
                  </Typography>
                  <Typography variant="body2">
                    Limit: {data.drawdownCap.max_drawdown_pct}%
                  </Typography>
                  <LinearProgress 
                    variant="determinate" 
                    value={Math.min((data.drawdownCap.current_drawdown_pct / data.drawdownCap.max_drawdown_pct) * 100, 100)}
                    sx={{ mt: 1, mb: 1 }}
                    color={data.drawdownCap.protective_mode ? "error" : "success"}
                  />
                  <Box mt={1}>
                    {data.drawdownCap.protective_mode ? (
                      <Chip label="⚠️ PROTECTIVE MODE" color="warning" size="small" />
                    ) : (
                      <Chip label="✅ NORMAL" color="success" size="small" />
                    )}
                  </Box>
                </>
              ) : (
                <CircularProgress size={24} />
              )}
            </Paper>
          </Grid>

          {/* Exposure Growth Status */}
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
              <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
                <Box display="flex" alignItems="center">
                  <SpeedIcon sx={{ mr: 1 }} />
                  <Typography variant="h6">⚡ Exposure Growth</Typography>
                </Box>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => setTabValue(3)}
                  startIcon={<SpeedIcon />}
                  sx={{ minWidth: 'auto', px: 2 }}
                >
                  Configure
                </Button>
              </Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Prevents flash cascade fills
              </Typography>
              {data.exposureLimiter ? (
                <>
                  <Typography variant="h4" sx={{ my: 1 }}>
                    {data.exposureLimiter.current_window?.tranches || 0}/{data.exposureLimiter.max_tranches_per_minute || 0}
                  </Typography>
                  <Typography variant="body2">
                    Tranches this minute
                  </Typography>
                  <LinearProgress 
                    variant="determinate" 
                    value={data.exposureLimiter.current_window?.utilization_pct || 0}
                    sx={{ mt: 1, mb: 1 }}
                  />
                  <Typography variant="caption" color="text.secondary">
                    ₹{(data.exposureLimiter.current_window?.notional_inr || 0).toLocaleString()} / 
                    ₹{(data.exposureLimiter.max_notional_per_minute || 0).toLocaleString()} notional
                  </Typography>
                </>
              ) : (
                <CircularProgress size={24} />
              )}
            </Paper>
          </Grid>

          {/* Pending Budget Status */}
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
              <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
                <Box display="flex" alignItems="center">
                  <AccountBalanceIcon sx={{ mr: 1 }} />
                  <Typography variant="h6">📊 Pending Budget</Typography>
                </Box>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => setTabValue(4)}
                  startIcon={<AccountBalanceIcon />}
                  sx={{ minWidth: 'auto', px: 2 }}
                >
                  Configure
                </Button>
              </Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Limits capital at risk
              </Typography>
              {data.pendingBudget ? (
                <>
                  <Typography variant="h4" sx={{ my: 1 }}>
                    ₹{data.pendingBudget.current_pending?.toLocaleString() || 0}
                  </Typography>
                  <Typography variant="body2">
                    Budget: ₹{data.pendingBudget.max_pending?.toLocaleString()}
                  </Typography>
                  <LinearProgress 
                    variant="determinate" 
                    value={data.pendingBudget.utilization_pct || 0}
                    sx={{ mt: 1, mb: 1 }}
                    color={data.pendingBudget.utilization_pct > 90 ? "warning" : "success"}
                  />
                  <Typography variant="caption" color="text.secondary">
                    {data.pendingBudget.pending_orders_count || 0} pending orders
                  </Typography>
                </>
              ) : (
                <CircularProgress size={24} />
              )}
            </Paper>
          </Grid>

          {/* Config Guard Status */}
          <Grid item xs={12}>
            <Paper sx={{ p: 2, bgcolor: data.configGuard?.has_pending_change ? 'warning.dark' : 'background.default' }}>
              <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
                <Box display="flex" alignItems="center">
                  <PeopleIcon sx={{ mr: 1 }} />
                  <Typography variant="h6">👥 Two-Man Rule</Typography>
                </Box>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => setTabValue(5)}
                  startIcon={<PeopleIcon />}
                  sx={{ minWidth: 'auto', px: 2 }}
                >
                  Configure
                </Button>
              </Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Config change confirmation
              </Typography>
              {data.configGuard ? (
                <>
                  {data.configGuard.has_pending_change ? (
                    <Alert severity="warning" sx={{ mt: 1 }}>
                      <AlertTitle>⏳ Confirmation Required</AlertTitle>
                      Config change detected. Create confirmation file to proceed.
                    </Alert>
                  ) : (
                    <Typography variant="body2" color="success.main">
                      ✅ No pending config changes
                    </Typography>
                  )}
                </>
              ) : (
                <CircularProgress size={24} />
              )}
            </Paper>
          </Grid>

        </Grid>
      </CardContent>
    </Card>
  );

  const renderEquityFloor = () => (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" mb={2}>
          <SecurityIcon sx={{ mr: 1, fontSize: 40, color: 'error.main' }} />
          <Typography variant="h5">💎 Equity Floor (Hard Stop)</Typography>
        </Box>

        <Alert severity="error" sx={{ mb: 2 }}>
          <AlertTitle>CRITICAL SAFETY NET</AlertTitle>
          This is your ABSOLUTE MINIMUM equity. If breached, all trading STOPS immediately.
        </Alert>

        {data.equityFloor ? (
          <Grid container spacing={2}>
            {/* Status Banner */}
            <Grid item xs={12}>
              {data.equityFloor.breached ? (
                <Alert severity="error">
                  <AlertTitle>🚨 EQUITY FLOOR BREACHED!</AlertTitle>
                  Trading stopped. Manual intervention required.
                  <Typography variant="body2" sx={{ mt: 1 }}>
                    Create acknowledgment file: <code>touch .operator_ack_equity_floor</code>
                  </Typography>
                </Alert>
              ) : (
                <Alert severity="success">
                  <AlertTitle>✅ EQUITY ABOVE FLOOR</AlertTitle>
                  Your account is safe. Floor protection active.
                </Alert>
              )}
            </Grid>

            {/* Equity Metrics */}
            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                <Typography variant="subtitle2" color="text.secondary">Current Equity</Typography>
                <Typography variant="h3" color={data.equityFloor.breached ? 'error.main' : 'success.main'}>
                  ₹{data.equityFloor.current_equity?.toLocaleString()}
                </Typography>
              </Paper>
            </Grid>

            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                <Typography variant="subtitle2" color="text.secondary">Equity Floor</Typography>
                <Typography variant="h3">₹{data.equityFloor.floor_inr?.toLocaleString()}</Typography>
              </Paper>
            </Grid>

            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                <Typography variant="subtitle2" color="text.secondary">Buffer Remaining</Typography>
                <Typography variant="h3" color={(data.equityFloor.buffer_inr || 0) < 10000 ? 'warning.main' : 'text.primary'}>
                  ₹{data.equityFloor.buffer_inr?.toLocaleString()}
                </Typography>
              </Paper>
            </Grid>

            {/* Configuration - Editable */}
            <Grid item xs={12}>
              <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                  <Typography variant="h6">⚙️ Configuration</Typography>
                  {!editing.equityFloorEdit ? (
                    <Button
                      variant="outlined"
                      color="primary"
                      size="small"
                      onClick={() => {
                        const ef = data.equityFloor || {};
                        setEditing({
                          ...editing, 
                          equityFloorEdit: true, 
                          equity_floor: ef.floor_inr || 50000,
                          equity_floor_check_interval: ef.check_interval_sec || 60,
                          equity_floor_require_ack: ef.require_ack !== undefined ? ef.require_ack : true
                        });
                      }}
                    >
                      ✏️ Edit
                    </Button>
                  ) : (
                    <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                      <Button
                        variant="outlined"
                        size="small"
                        onClick={() => setEditing({...editing, equityFloorEdit: false})}
                        sx={{ mr: 1 }}
                      >
                        Cancel
                      </Button>
                      <Button
                        variant="contained"
                        color="success"
                        size="small"
                        disabled={saving}
                        data-action-id="capital.equity-floor.save"
                        onClick={() => handleSaveConfig({
                          equity_floor: editing.equity_floor,
                          equity_floor_check_interval: editing.equity_floor_check_interval,
                          equity_floor_require_ack: editing.equity_floor_require_ack
                        })}
                      >
                        {saving ? 'Saving...' : 'Save'}
                      </Button>
                      <HelpIcon actionId="capital.equity-floor.save" size="small" />
                    </Box>
                  )}
                </Box>
                <Grid container spacing={2}>
                  <Grid item xs={12} md={4}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>Equity Floor (INR)</Typography>
                    {editing.equityFloorEdit ? (
                      <TextField
                        type="number"
                        value={editing.equity_floor !== undefined ? editing.equity_floor : data.equityFloor.floor_inr}
                        onChange={(e) => setEditing({...editing, equity_floor: e.target.value})}
                        fullWidth
                        size="small"
                        inputProps={{ min: 0 }}
                        helperText="Set to 0 to disable"
                      />
                    ) : (
                      <Typography variant="h6">₹{data.equityFloor.floor_inr?.toLocaleString()}</Typography>
                    )}
                  </Grid>
                  <Grid item xs={12} md={4}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>Check Interval (sec)</Typography>
                    {editing.equityFloorEdit ? (
                      <TextField
                        type="number"
                        value={editing.equity_floor_check_interval !== undefined ? editing.equity_floor_check_interval : data.equityFloor.check_interval_sec}
                        onChange={(e) => setEditing({...editing, equity_floor_check_interval: e.target.value})}
                        fullWidth
                        size="small"
                        inputProps={{ min: 10, max: 300 }}
                        helperText="10-300 seconds"
                      />
                    ) : (
                      <Typography variant="h6">{data.equityFloor.check_interval_sec}s</Typography>
                    )}
                  </Grid>
                  <Grid item xs={12} md={4}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>Require Acknowledgment</Typography>
                    {editing.equityFloorEdit ? (
                      <Box>
                        <Button
                          variant={editing.equity_floor_require_ack ? "contained" : "outlined"}
                          color={editing.equity_floor_require_ack ? "success" : "default"}
                          size="small"
                          onClick={() => setEditing({...editing, equity_floor_require_ack: !editing.equity_floor_require_ack})}
                          fullWidth
                        >
                          {editing.equity_floor_require_ack ? "✅ Required" : "❌ Not Required"}
                        </Button>
                      </Box>
                    ) : (
                      <Typography variant="h6">
                        {data.equityFloor.require_ack ? (
                          <Chip label="✅ Required" color="success" size="small" />
                        ) : (
                          <Chip label="❌ Not Required" color="default" size="small" />
                        )}
                      </Typography>
                    )}
                  </Grid>
                  <Grid item xs={12}>
                    <Typography variant="caption" color="text.secondary">
                      <strong>Status:</strong> {data.equityFloor.enabled ? (
                        <Chip label="✅ ENABLED" color="success" size="small" sx={{ ml: 1 }} />
                      ) : (
                        <Chip label="❌ DISABLED (Floor = 0)" color="error" size="small" sx={{ ml: 1 }} />
                      )}
                    </Typography>
                  </Grid>
                </Grid>
              </Paper>
            </Grid>

            {/* Explanation */}
            <Grid item xs={12}>
              <Alert severity="info">
                <AlertTitle>How It Works</AlertTitle>
                <Typography variant="body2">
                  <strong>Guardian Bot continuously monitors your total account equity.</strong><br/>
                  If equity falls below the floor:<br/>
                  • Emergency protocol triggered immediately<br/>
                  • All new orders BLOCKED via Safety Gatekeeper<br/>
                  • Non-reduce orders cancelled<br/>
                  • TP orders remain active<br/>
                  • Manual acknowledgment required to resume<br/>
                  <br/>
                  <strong>Example:</strong> Start with 100k INR, set floor at 70k INR → Max loss = 30k INR (30%)
                </Typography>
              </Alert>
            </Grid>
          </Grid>
        ) : (
          <CircularProgress />
        )}
      </CardContent>
    </Card>
  );

  const renderDrawdownCap = () => (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" mb={2}>
          <TrendingDownIcon sx={{ mr: 1, fontSize: 40, color: 'warning.main' }} />
          <Typography variant="h5">📉 Drawdown Cap (30-Day Rolling)</Typography>
        </Box>

        <Alert severity="warning" sx={{ mb: 2 }}>
          <AlertTitle>SOFT STOP - Protective Mode</AlertTitle>
          When drawdown limit is exceeded, bot enters protective mode: No new BUY orders, exits only.
        </Alert>

        {data.drawdownCap ? (
          <Grid container spacing={2}>
            {/* Status Banner */}
            <Grid item xs={12}>
              {data.drawdownCap.protective_mode ? (
                <Alert severity="warning">
                  <AlertTitle>⚠️ PROTECTIVE MODE ACTIVE</AlertTitle>
                  Drawdown limit exceeded. New BUY orders blocked. Allow positions to close naturally.
                  <Typography variant="body2" sx={{ mt: 1 }}>
                    Auto-resumes when drawdown &lt; {data.drawdownCap.hysteresis_pct}%
                  </Typography>
                </Alert>
              ) : (
                <Alert severity="success">
                  <AlertTitle>✅ NORMAL OPERATIONS</AlertTitle>
                  Drawdown within acceptable limits.
                </Alert>
              )}
            </Grid>

            {/* Drawdown Metrics */}
            <Grid item xs={12} md={3}>
              <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                <Typography variant="subtitle2" color="text.secondary">30-Day Peak</Typography>
                <Typography variant="h3">₹{data.drawdownCap.peak_equity?.toLocaleString()}</Typography>
              </Paper>
            </Grid>

            <Grid item xs={12} md={3}>
              <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                <Typography variant="subtitle2" color="text.secondary">Current Equity</Typography>
                <Typography variant="h3">₹{data.drawdownCap.current_equity?.toLocaleString()}</Typography>
              </Paper>
            </Grid>

            <Grid item xs={12} md={3}>
              <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                <Typography variant="subtitle2" color="text.secondary">Current Drawdown</Typography>
                <Typography variant="h3" color={data.drawdownCap.protective_mode ? 'error.main' : 'text.primary'}>
                  {data.drawdownCap.current_drawdown_pct?.toFixed(1)}%
                </Typography>
              </Paper>
            </Grid>

            <Grid item xs={12} md={3}>
              <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                <Typography variant="subtitle2" color="text.secondary">Drawdown (INR)</Typography>
                <Typography variant="h3">₹{data.drawdownCap.current_drawdown_inr?.toLocaleString()}</Typography>
              </Paper>
            </Grid>

            {/* Progress Bar */}
            <Grid item xs={12}>
              <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Drawdown Utilization
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center' }}>
                  <Box sx={{ width: '100%', mr: 1 }}>
                    <LinearProgress 
                      variant="determinate" 
                      value={Math.min((data.drawdownCap.current_drawdown_pct / data.drawdownCap.max_drawdown_pct) * 100, 100)}
                      sx={{ height: 10, borderRadius: 5 }}
                      color={data.drawdownCap.utilization_pct > 100 ? "error" : data.drawdownCap.utilization_pct > 75 ? "warning" : "success"}
                    />
                  </Box>
                  <Box sx={{ minWidth: 35 }}>
                    <Typography variant="body2" color="text.secondary">
                      {data.drawdownCap.utilization_pct?.toFixed(0)}%
                    </Typography>
                  </Box>
                </Box>
              </Paper>
            </Grid>

            {/* Snapshot Info */}
            <Grid item xs={12}>
              <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                <Typography variant="h6" gutterBottom>Snapshot System</Typography>
                <Grid container spacing={2}>
                  <Grid item xs={12} md={4}>
                    <Typography variant="body2" color="text.secondary">Total Snapshots</Typography>
                    <Typography variant="h6">{data.drawdownCap.snapshot_count}</Typography>
                  </Grid>
                  <Grid item xs={12} md={4}>
                    <Typography variant="body2" color="text.secondary">Window</Typography>
                    <Typography variant="h6">{data.drawdownCap.window_days} days</Typography>
                  </Grid>
                  <Grid item xs={12} md={4}>
                    <Typography variant="body2" color="text.secondary">Frequency</Typography>
                    <Typography variant="h6">Hourly</Typography>
                  </Grid>
                </Grid>
              </Paper>
            </Grid>

            {/* Configuration - Editable */}
            <Grid item xs={12}>
              <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                  <Typography variant="h6">⚙️ Configuration</Typography>
                  {!editing.drawdownEdit ? (
                    <Button
                      variant="outlined"
                      color="primary"
                      size="small"
                      onClick={() => {
                        const dd = data.drawdownCap || {};
                        setEditing({
                          ...editing,
                          drawdownEdit: true,
                          drawdown_max_pct: dd.max_drawdown_pct || 20,
                          drawdown_hysteresis_pct: dd.hysteresis_pct || 15,
                          drawdown_window_days: dd.window_days || 30,
                          drawdown_check_interval: dd.check_interval_sec || 300
                        });
                      }}
                    >
                      ✏️ Edit
                    </Button>
                  ) : (
                    <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                      <Button
                        variant="outlined"
                        size="small"
                        onClick={() => setEditing({...editing, drawdownEdit: false})}
                        sx={{ mr: 1 }}
                      >
                        Cancel
                      </Button>
                      <Button
                        variant="contained"
                        color="success"
                        size="small"
                        disabled={saving}
                        data-action-id="capital.drawdown-cap.save"
                        onClick={() => handleSaveConfig({
                          drawdown_max_pct: editing.drawdown_max_pct,
                          drawdown_hysteresis_pct: editing.drawdown_hysteresis_pct,
                          drawdown_window_days: editing.drawdown_window_days,
                          drawdown_check_interval: editing.drawdown_check_interval
                        })}
                      >
                        {saving ? 'Saving...' : 'Save'}
                      </Button>
                      <HelpIcon actionId="capital.drawdown-cap.save" size="small" />
                    </Box>
                  )}
                </Box>
                <Grid container spacing={2}>
                  <Grid item xs={12} md={3}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>Max Drawdown (%)</Typography>
                    {editing.drawdownEdit ? (
                      <TextField
                        type="number"
                        value={editing.drawdown_max_pct || data.drawdownCap.max_drawdown_pct}
                        onChange={(e) => setEditing({...editing, drawdown_max_pct: e.target.value})}
                        fullWidth
                        size="small"
                        inputProps={{ min: 1, max: 100 }}
                      />
                    ) : (
                      <Typography variant="h6">{data.drawdownCap.max_drawdown_pct}%</Typography>
                    )}
                  </Grid>
                  <Grid item xs={12} md={3}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>Hysteresis (%)</Typography>
                    {editing.drawdownEdit ? (
                      <TextField
                        type="number"
                        value={editing.drawdown_hysteresis_pct || data.drawdownCap.hysteresis_pct}
                        onChange={(e) => setEditing({...editing, drawdown_hysteresis_pct: e.target.value})}
                        fullWidth
                        size="small"
                        inputProps={{ min: 0, max: 100 }}
                      />
                    ) : (
                      <Typography variant="h6">{data.drawdownCap.hysteresis_pct}%</Typography>
                    )}
                  </Grid>
                  <Grid item xs={12} md={3}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>Window (days)</Typography>
                    {editing.drawdownEdit ? (
                      <TextField
                        type="number"
                        value={editing.drawdown_window_days || data.drawdownCap.window_days}
                        onChange={(e) => setEditing({...editing, drawdown_window_days: e.target.value})}
                        fullWidth
                        size="small"
                        inputProps={{ min: 7, max: 90 }}
                        helperText="7-90 days"
                      />
                    ) : (
                      <Typography variant="h6">{data.drawdownCap.window_days} days</Typography>
                    )}
                  </Grid>
                  <Grid item xs={12} md={3}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>Check Interval (sec)</Typography>
                    {editing.drawdownEdit ? (
                      <TextField
                        type="number"
                        value={editing.drawdown_check_interval || data.drawdownCap.check_interval_sec}
                        onChange={(e) => setEditing({...editing, drawdown_check_interval: e.target.value})}
                        fullWidth
                        size="small"
                        inputProps={{ min: 60, max: 3600 }}
                        helperText="60-3600 sec"
                      />
                    ) : (
                      <Typography variant="h6">{data.drawdownCap.check_interval_sec || 300}s</Typography>
                    )}
                  </Grid>
                  <Grid item xs={12}>
                    <Typography variant="caption" color="text.secondary">
                      <strong>Status:</strong> {data.drawdownCap.enabled ? (
                        <Chip label="✅ ENABLED" color="success" size="small" sx={{ ml: 1 }} />
                      ) : (
                        <Chip label="❌ NO" color="error" size="small" />
                      )}
                    </Typography>
                  </Grid>
                </Grid>
              </Paper>
            </Grid>

            {/* Explanation */}
            <Grid item xs={12}>
              <Alert severity="info">
                <AlertTitle>How It Works</AlertTitle>
                <Typography variant="body2">
                  <strong>Tracks your 30-day peak equity and calculates current drawdown.</strong><br/>
                  Drawdown = (Peak - Current) / Peak × 100<br/>
                  <br/>
                  <strong>Example:</strong> Peak was 120k INR, now at 100k INR = 16.7% drawdown<br/>
                  If limit is 20% → Still OK<br/>
                  If limit is 15% → Enters protective mode<br/>
                  <br/>
                  <strong>Protective Mode:</strong><br/>
                  • No new BUY orders<br/>
                  • TP (exit) orders still active<br/>
                  • Let positions close naturally<br/>
                  • Auto-resumes when drawdown recovers below hysteresis threshold<br/>
                  <br/>
                  <strong>Hysteresis prevents flapping:</strong> Enter protective at 20%, resume at 15%
                </Typography>
              </Alert>
            </Grid>
          </Grid>
        ) : (
          <CircularProgress />
        )}
      </CardContent>
    </Card>
  );

  const renderExposureGrowth = () => (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" mb={3}>
          <SpeedIcon sx={{ mr: 1, fontSize: 40, color: 'warning.main' }} />
          <Typography variant="h5">Exposure Growth Rate Limiter</Typography>
        </Box>

        {data.exposureLimiter ? (
          <Grid container spacing={2}>
            {/* Status Banner */}
            <Grid item xs={12}>
              {data.exposureLimiter.enabled ? (
                <Alert severity="success">
                  <AlertTitle>✅ EXPOSURE GROWTH LIMITER ACTIVE</AlertTitle>
                  Controlling how fast positions can be opened
                </Alert>
              ) : (
                <Alert severity="warning">
                  <AlertTitle>⚠️ EXPOSURE GROWTH LIMITER DISABLED</AlertTitle>
                  No protection against rapid position accumulation
                </Alert>
              )}
            </Grid>

            {/* Current Usage */}
            <Grid item xs={12} md={6}>
              <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                <Typography variant="h6" gutterBottom>Tranches Per Minute</Typography>
                <Box sx={{ display: 'flex', alignItems: 'baseline', mb: 1 }}>
                  <Typography variant="h3" color={(data.exposureLimiter.current_window?.tranches || 0) >= (data.exposureLimiter.max_tranches_per_minute || 0) ? 'error.main' : 'text.primary'}>
                    {data.exposureLimiter.current_window?.tranches || 0}
                  </Typography>
                  <Typography variant="h5" color="text.secondary" sx={{ ml: 1 }}>
                    / {data.exposureLimiter.max_tranches_per_minute || 0}
                  </Typography>
                </Box>
                <LinearProgress 
                  variant="determinate" 
                  value={Math.min(((data.exposureLimiter.current_window?.tranches || 0) / (data.exposureLimiter.max_tranches_per_minute || 1)) * 100, 100)}
                  sx={{ height: 10, borderRadius: 5 }}
                  color={(data.exposureLimiter.current_window?.tranches || 0) >= (data.exposureLimiter.max_tranches_per_minute || 0) ? "error" : (data.exposureLimiter.current_window?.tranches || 0) > (data.exposureLimiter.max_tranches_per_minute || 0) * 0.8 ? "warning" : "success"}
                />
              </Paper>
            </Grid>

            <Grid item xs={12} md={6}>
              <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                <Typography variant="h6" gutterBottom>Notional Per Minute (INR)</Typography>
                <Box sx={{ display: 'flex', alignItems: 'baseline', mb: 1 }}>
                  <Typography variant="h3" color={(data.exposureLimiter.current_window?.notional_inr || 0) >= (data.exposureLimiter.max_notional_per_minute || 0) ? 'error.main' : 'text.primary'}>
                    ₹{((data.exposureLimiter.current_window?.notional_inr || 0) / 1000).toFixed(0)}k
                  </Typography>
                  <Typography variant="h5" color="text.secondary" sx={{ ml: 1 }}>
                    / ₹{((data.exposureLimiter.max_notional_per_minute || 0) / 1000).toFixed(0)}k
                  </Typography>
                </Box>
                <LinearProgress 
                  variant="determinate" 
                  value={Math.min(((data.exposureLimiter.current_window?.notional_inr || 0) / (data.exposureLimiter.max_notional_per_minute || 1)) * 100, 100)}
                  sx={{ height: 10, borderRadius: 5 }}
                  color={(data.exposureLimiter.current_window?.notional_inr || 0) >= (data.exposureLimiter.max_notional_per_minute || 0) ? "error" : (data.exposureLimiter.current_window?.notional_inr || 0) > (data.exposureLimiter.max_notional_per_minute || 0) * 0.8 ? "warning" : "success"}
                />
              </Paper>
            </Grid>

            {/* Configuration - Editable */}
            <Grid item xs={12}>
              <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                  <Typography variant="h6">⚙️ Configuration</Typography>
                  {!editing.exposureEdit ? (
                    <Button
                      variant="outlined"
                      color="primary"
                      size="small"
                      onClick={() => {
                        const ex = data.exposureLimiter || {};
                        setEditing({
                          ...editing,
                          exposureEdit: true,
                          max_tranches_per_minute: ex.max_tranches_per_minute || 2,
                          max_notional_per_minute: ex.max_notional_per_minute || 300000
                        });
                      }}
                    >
                      ✏️ Edit
                    </Button>
                  ) : (
                    <Box>
                      <Button
                        variant="outlined"
                        size="small"
                        onClick={() => setEditing({...editing, exposureEdit: false})}
                        sx={{ mr: 1 }}
                      >
                        Cancel
                      </Button>
                      <Button
                        variant="contained"
                        color="success"
                        size="small"
                        disabled={saving}
                        onClick={() => {
                          handleSaveConfig({
                            max_tranches_per_minute: editing.max_tranches_per_minute,
                            max_notional_per_minute: editing.max_notional_per_minute
                          });
                        }}
                      >
                        {saving ? 'Saving...' : 'Save'}
                      </Button>
                    </Box>
                  )}
                </Box>
                <Grid container spacing={2}>
                  <Grid item xs={12} md={6}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>Max Tranches/Minute</Typography>
                    {editing.exposureEdit ? (
                      <TextField
                        type="number"
                        value={editing.max_tranches_per_minute !== undefined ? editing.max_tranches_per_minute : (data.exposureLimiter.max_tranches_per_minute || 2)}
                        onChange={(e) => setEditing({...editing, max_tranches_per_minute: e.target.value})}
                        fullWidth
                        size="small"
                        inputProps={{ min: 1 }}
                      />
                    ) : (
                      <Typography variant="h6">{data.exposureLimiter.max_tranches_per_minute || 0}</Typography>
                    )}
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>Max Notional/Minute (INR)</Typography>
                    {editing.exposureEdit ? (
                      <TextField
                        type="number"
                        value={editing.max_notional_per_minute !== undefined ? editing.max_notional_per_minute : (data.exposureLimiter.max_notional_per_minute || 300000)}
                        onChange={(e) => {
                          setEditing({...editing, max_notional_per_minute: e.target.value});
                        }}
                        fullWidth
                        size="small"
                        inputProps={{ min: 1000 }}
                      />
                    ) : (
                      <Typography variant="h6">₹{((data.exposureLimiter.max_notional_per_minute || 0) / 1000).toFixed(0)}k</Typography>
                    )}
                  </Grid>
                </Grid>
              </Paper>
            </Grid>

            {/* Explanation */}
            <Grid item xs={12}>
              <Alert severity="info">
                <AlertTitle>How It Works</AlertTitle>
                <Typography variant="body2">
                  <strong>Prevents "flash cascade" fills during rapid market moves.</strong><br/>
                  <br/>
                  <strong>Two Limits:</strong><br/>
                  1. <strong>Max Tranches/Minute:</strong> Limits number of new positions opened per minute<br/>
                  2. <strong>Max Notional/Minute:</strong> Limits total INR value of new positions per minute<br/>
                  <br/>
                  <strong>Example:</strong><br/>
                  Limit: 2 tranches/minute, 300k INR/minute<br/>
                  Market drops fast, 5 buy orders could fill in 10 seconds<br/>
                  Limiter: Only allows 2 fills, blocks the other 3<br/>
                  <br/>
                  <strong>This protects you from:</strong><br/>
                  • Rapid exposure buildup during crashes<br/>
                  • Exceeding risk limits too quickly<br/>
                  • "Revenge trading" by the bot
                </Typography>
              </Alert>
            </Grid>
          </Grid>
        ) : (
          <CircularProgress />
        )}
      </CardContent>
    </Card>
  );

  const renderPendingBudget = () => (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" mb={3}>
          <AccountBalanceIcon sx={{ mr: 1, fontSize: 40, color: 'info.main' }} />
          <Typography variant="h5">Pending Order Budget</Typography>
        </Box>

        {data.pendingBudget ? (
          <Grid container spacing={2}>
            {/* Status Banner */}
            <Grid item xs={12}>
              {data.pendingBudget.budget_exceeded ? (
                <Alert severity="error">
                  <AlertTitle>🛑 BUDGET EXCEEDED</AlertTitle>
                  Too much capital at risk in pending orders. New orders blocked until some fill or are canceled.
                </Alert>
              ) : data.pendingBudget.utilization_pct > 90 ? (
                <Alert severity="warning">
                  <AlertTitle>⚠️ APPROACHING BUDGET LIMIT</AlertTitle>
                  Pending order budget at {data.pendingBudget.utilization_pct.toFixed(0)}% - new orders may be blocked soon
                </Alert>
              ) : (
                <Alert severity="success">
                  <AlertTitle>✅ BUDGET OK</AlertTitle>
                  Pending capital within limits ({data.pendingBudget.utilization_pct.toFixed(0)}% used)
                </Alert>
              )}
            </Grid>

            {/* Budget Metrics */}
            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                <Typography variant="subtitle2" color="text.secondary">Current Pending</Typography>
                <Typography variant="h3" color={data.pendingBudget.budget_exceeded ? 'error.main' : 'text.primary'}>
                  ₹{(data.pendingBudget.current_pending / 1000).toFixed(0)}k
                </Typography>
              </Paper>
            </Grid>

            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                <Typography variant="subtitle2" color="text.secondary">Budget Limit</Typography>
                <Typography variant="h3">₹{(data.pendingBudget.max_budget / 1000).toFixed(0)}k</Typography>
              </Paper>
            </Grid>

            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                <Typography variant="subtitle2" color="text.secondary">Open Orders</Typography>
                <Typography variant="h3">{data.pendingBudget.open_orders}</Typography>
              </Paper>
            </Grid>

            {/* Progress Bar */}
            <Grid item xs={12}>
              <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                  Budget Utilization
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center' }}>
                  <Box sx={{ width: '100%', mr: 1 }}>
                    <LinearProgress 
                      variant="determinate" 
                      value={Math.min(data.pendingBudget.utilization_pct, 100)}
                      sx={{ height: 10, borderRadius: 5 }}
                      color={data.pendingBudget.budget_exceeded ? "error" : data.pendingBudget.utilization_pct > 90 ? "warning" : "success"}
                    />
                  </Box>
                  <Box sx={{ minWidth: 35 }}>
                    <Typography variant="body2" color="text.secondary">
                      {data.pendingBudget.utilization_pct.toFixed(0)}%
                    </Typography>
                  </Box>
                </Box>
              </Paper>
            </Grid>

            {/* Configuration - Editable */}
            <Grid item xs={12}>
              <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                  <Typography variant="h6">⚙️ Configuration</Typography>
                  {!editing.budgetEdit ? (
                    <Button
                      variant="outlined"
                      color="primary"
                      size="small"
                      onClick={() => {
                        const pb = data.pendingBudget || {};
                        setEditing({
                          ...editing,
                          budgetEdit: true,
                          max_pending_budget: pb.max_budget || 500000,
                          pending_budget_buffer_pct: pb.buffer_pct || 10
                        });
                      }}
                    >
                      ✏️ Edit
                    </Button>
                  ) : (
                    <Box>
                      <Button
                        variant="outlined"
                        size="small"
                        onClick={() => setEditing({...editing, budgetEdit: false})}
                        sx={{ mr: 1 }}
                      >
                        Cancel
                      </Button>
                      <Button
                        variant="contained"
                        color="success"
                        size="small"
                        disabled={saving}
                        onClick={() => handleSaveConfig({
                          max_pending_budget: editing.max_pending_budget,
                          pending_budget_buffer_pct: editing.pending_budget_buffer_pct
                        })}
                      >
                        {saving ? 'Saving...' : 'Save'}
                      </Button>
                    </Box>
                  )}
                </Box>
                <Grid container spacing={2}>
                  <Grid item xs={12} md={6}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>Max Pending Budget (INR)</Typography>
                    {editing.budgetEdit ? (
                      <TextField
                        type="number"
                        value={editing.max_pending_budget || data.pendingBudget.max_budget}
                        onChange={(e) => setEditing({...editing, max_pending_budget: e.target.value})}
                        fullWidth
                        size="small"
                        inputProps={{ min: 10000 }}
                      />
                    ) : (
                      <Typography variant="h6">₹{(data.pendingBudget.max_budget / 1000).toFixed(0)}k</Typography>
                    )}
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>Buffer Alert (%)</Typography>
                    {editing.budgetEdit ? (
                      <TextField
                        type="number"
                        value={editing.pending_budget_buffer_pct !== undefined ? editing.pending_budget_buffer_pct : data.pendingBudget.buffer_pct}
                        onChange={(e) => setEditing({...editing, pending_budget_buffer_pct: e.target.value})}
                        fullWidth
                        size="small"
                        inputProps={{ min: 0, max: 50 }}
                        helperText="Alert at (100-X)% of budget"
                      />
                    ) : (
                      <Typography variant="h6">{data.pendingBudget.buffer_pct}%</Typography>
                    )}
                  </Grid>
                </Grid>
              </Paper>
            </Grid>

            {/* Explanation */}
            <Grid item xs={12}>
              <Alert severity="info">
                <AlertTitle>How It Works</AlertTitle>
                <Typography variant="body2">
                  <strong>Limits total capital at risk in pending BUY orders.</strong><br/>
                  <br/>
                  <strong>Calculation:</strong><br/>
                  Pending Capital = Σ (limit_price × qty) for all pending BUY orders<br/>
                  <br/>
                  <strong>Example:</strong><br/>
                  Budget: 500k INR<br/>
                  Open Orders: 3 BUYs at 111k each = 333k pending<br/>
                  Utilization: 333k / 500k = 67% ✅ OK<br/>
                  <br/>
                  If you try to place 2 more orders (222k more):<br/>
                  Total would be: 555k &gt; 500k limit ❌ BLOCKED<br/>
                  <br/>
                  <strong>This protects you from:</strong><br/>
                  • Too much capital tied up in pending orders<br/>
                  • Overnight exposure risk<br/>
                  • Sudden margin calls if multiple orders fill at once
                </Typography>
              </Alert>
            </Grid>
          </Grid>
        ) : (
          <CircularProgress />
        )}
      </CardContent>
    </Card>
  );

  const renderTwoManRule = () => (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" mb={3}>
          <PeopleIcon sx={{ mr: 1, fontSize: 40, color: 'secondary.main' }} />
          <Typography variant="h5">Two-Man Rule (Config Guard)</Typography>
        </Box>

        {data.configGuard ? (
          <Grid container spacing={2}>
            {/* Status Banner */}
            <Grid item xs={12}>
              {data.configGuard.pending_change ? (
                <Alert severity="warning">
                  <AlertTitle>⚠️ CONFIG CHANGE PENDING CONFIRMATION</AlertTitle>
                  <Typography variant="body2">
                    A risky configuration change was detected and requires your confirmation.
                  </Typography>
                  <Typography variant="body2" sx={{ mt: 1 }}>
                    Time remaining: {Math.max(0, data.configGuard.pending_change.timeout_remaining).toFixed(0)} seconds
                  </Typography>
                  <Typography variant="body2" sx={{ mt: 1 }}>
                    <strong>To confirm:</strong> touch .config_change_confirmed
                  </Typography>
                </Alert>
              ) : data.configGuard.enabled ? (
                <Alert severity="success">
                  <AlertTitle>✅ TWO-MAN RULE ACTIVE</AlertTitle>
                  All risky config changes require confirmation
                </Alert>
              ) : (
                <Alert severity="warning">
                  <AlertTitle>⚠️ TWO-MAN RULE DISABLED</AlertTitle>
                  No protection against impulsive config changes
                </Alert>
              )}
            </Grid>

            {/* Stats */}
            <Grid item xs={12} md={3}>
              <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                <Typography variant="subtitle2" color="text.secondary">Status</Typography>
                <Typography variant="h6">
                  {data.configGuard.enabled ? (
                    <Chip label="✅ ENABLED" color="success" />
                  ) : (
                    <Chip label="❌ DISABLED" color="error" />
                  )}
                </Typography>
              </Paper>
            </Grid>

            <Grid item xs={12} md={3}>
              <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                <Typography variant="subtitle2" color="text.secondary">Timeout</Typography>
                <Typography variant="h6">{data.configGuard.timeout_sec / 60} min</Typography>
              </Paper>
            </Grid>

            <Grid item xs={12} md={3}>
              <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                <Typography variant="subtitle2" color="text.secondary">Auto-Revert</Typography>
                <Typography variant="h6">
                  {data.configGuard.auto_revert ? (
                    <Chip label="YES" color="success" size="small" />
                  ) : (
                    <Chip label="NO" color="warning" size="small" />
                  )}
                </Typography>
              </Paper>
            </Grid>

            <Grid item xs={12} md={3}>
              <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                <Typography variant="subtitle2" color="text.secondary">Pending Change</Typography>
                <Typography variant="h6">
                  {data.configGuard.pending_change ? (
                    <Chip label="YES" color="warning" />
                  ) : (
                    <Chip label="NO" color="success" />
                  )}
                </Typography>
              </Paper>
            </Grid>

            {/* Pending Change Details */}
            {data.configGuard.pending_change && (
              <Grid item xs={12}>
                <Paper sx={{ p: 2, bgcolor: 'warning.light' }}>
                  <Typography variant="h6" gutterBottom>Pending Change Details</Typography>
                  <TableContainer>
                    <Table size="small">
                      <TableHead>
                        <TableRow>
                          <TableCell><strong>Key</strong></TableCell>
                          <TableCell><strong>Old Value</strong></TableCell>
                          <TableCell><strong>New Value</strong></TableCell>
                          <TableCell><strong>Change</strong></TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {data.configGuard.pending_change.changes?.map((change, idx) => (
                          <TableRow key={idx}>
                            <TableCell>{change.key}</TableCell>
                            <TableCell>{change.old_value}</TableCell>
                            <TableCell>{change.new_value}</TableCell>
                            <TableCell>
                              <Chip 
                                label={change.change_type} 
                                size="small"
                                color={change.change_type === 'RISK_INCREASE' ? 'error' : 'warning'}
                              />
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Paper>
              </Grid>
            )}

            {/* Guarded Keys */}
            <Grid item xs={12}>
              <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                <Typography variant="h6" gutterBottom>Protected Configuration Keys</Typography>
                <Typography variant="body2" color="text.secondary" paragraph>
                  These keys require confirmation if increased or disabled:
                </Typography>
                <Box display="flex" flexWrap="wrap" gap={1}>
                  {data.configGuard.guarded_keys?.map((key, idx) => (
                    <Chip key={idx} label={key} size="small" variant="outlined" />
                  ))}
                </Box>
              </Paper>
            </Grid>

            {/* Configuration - Editable */}
            <Grid item xs={12}>
              <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                  <Typography variant="h6">⚙️ Configuration</Typography>
                  {!editing.twoManEdit ? (
                    <Button
                      variant="outlined"
                      color="primary"
                      size="small"
                      onClick={() => {
                        const cg = data.configGuard || {};
                        setEditing({
                          ...editing,
                          twoManEdit: true,
                          two_man_rule_timeout: cg.timeout_sec || 600
                        });
                      }}
                    >
                      ✏️ Edit
                    </Button>
                  ) : (
                    <Box>
                      <Button
                        variant="outlined"
                        size="small"
                        onClick={() => setEditing({...editing, twoManEdit: false})}
                        sx={{ mr: 1 }}
                      >
                        Cancel
                      </Button>
                      <Button
                        variant="contained"
                        color="success"
                        size="small"
                        disabled={saving}
                        onClick={() => handleSaveConfig({
                          two_man_rule_timeout: editing.two_man_rule_timeout
                        })}
                      >
                        {saving ? 'Saving...' : 'Save'}
                      </Button>
                    </Box>
                  )}
                </Box>
                <Grid container spacing={2}>
                  <Grid item xs={12} md={6}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>Confirmation Timeout (seconds)</Typography>
                    {editing.twoManEdit ? (
                      <TextField
                        type="number"
                        value={editing.two_man_rule_timeout || data.configGuard.timeout_sec}
                        onChange={(e) => setEditing({...editing, two_man_rule_timeout: e.target.value})}
                        fullWidth
                        size="small"
                        inputProps={{ min: 60 }}
                      />
                    ) : (
                      <Typography variant="h6">{(data.configGuard.timeout_sec / 60).toFixed(0)} minutes</Typography>
                    )}
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>Auto-Revert</Typography>
                    <Typography variant="h6">
                      {data.configGuard.auto_revert ? (
                        <Chip label="YES" color="success" size="small" />
                      ) : (
                        <Chip label="NO" color="warning" size="small" />
                      )}
                    </Typography>
                  </Grid>
                </Grid>
              </Paper>
            </Grid>

            {/* Explanation */}
            <Grid item xs={12}>
              <Alert severity="info">
                <AlertTitle>How It Works - "Future You Protecting Present You"</AlertTitle>
                <Typography variant="body2">
                  <strong>Prevents impulsive risk increases during emotional trading moments.</strong><br/>
                  <br/>
                  <strong>Protected Changes:</strong><br/>
                  • Increasing loss limits<br/>
                  • Increasing position size or lot size<br/>
                  • Disabling safety features<br/>
                  • Enabling EXECUTE_ORDERS<br/>
                  <br/>
                  <strong>When you make a risky change:</strong><br/>
                  1. Bot detects the change on startup<br/>
                  2. Requires confirmation within {data.configGuard.timeout_sec / 60} minutes<br/>
                  3. Create file: <code>touch .config_change_confirmed</code><br/>
                  4. If not confirmed → Auto-reverts (if enabled)<br/>
                  <br/>
                  <strong>Example:</strong><br/>
                  You're frustrated after a loss and increase loss limit from 5k to 50k.<br/>
                  Two-Man Rule: "Wait {data.configGuard.timeout_sec / 60} minutes and confirm this is really what you want."<br/>
                  After cooling down, you realize it was a bad idea → Change auto-reverts<br/>
                  <br/>
                  <strong>This is your safety net against emotional trading decisions!</strong>
                </Typography>
              </Alert>
            </Grid>
          </Grid>
        ) : (
          <CircularProgress />
        )}
      </CardContent>
    </Card>
  );

  return (
    <Box>
      {/* Emergency Override Toggle */}
      <EmergencyToggle
        featureName="capital_protection"
        displayName="Capital Protection"
        description="Multi-layer protection including equity floor, drawdown cap, exposure limiter, pending budget, and config guard"
        warningMessage="Disabling capital protection removes all safety nets: equity floor, drawdown limits, exposure caps, pending budget controls, and configuration guards. This significantly increases your risk of catastrophic losses."
      />

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs value={tabValue} onChange={handleTabChange} aria-label="capital protection tabs">
          <Tab label="📊 Overview" />
          <Tab label="💎 Equity Floor" />
          <Tab label="📉 Drawdown Cap" />
          <Tab label="⚡ Exposure Growth" />
          <Tab label="📊 Pending Budget" />
          <Tab label="👥 Two-Man Rule" />
        </Tabs>
      </Box>

      {loading ? (
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
          <CircularProgress />
        </Box>
      ) : (
        <>
          {tabValue === 0 && renderOverview()}
          {tabValue === 1 && renderEquityFloor()}
          {tabValue === 2 && renderDrawdownCap()}
          {tabValue === 3 && renderExposureGrowth()}
          {tabValue === 4 && renderPendingBudget()}
          {tabValue === 5 && renderTwoManRule()}
        </>
      )}

      {/* Success/Error Notification */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({...snackbar, open: false})}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        sx={{ maxWidth: '500px' }}
      >
        <Alert 
          onClose={() => setSnackbar({...snackbar, open: false})} 
          severity={snackbar.severity} 
          sx={{ 
            width: '100%', 
            minWidth: '350px',
            '& .MuiAlert-message': { 
              wordBreak: 'break-word',
              whiteSpace: 'normal'
            }
          }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>

      {/* Capital Protection Configuration Section */}
      <ConfigSection
        configKeys={[
          'EQUITY_FLOOR_INR',
          'EQUITY_FLOOR_CHECK_INTERVAL',
          'EQUITY_FLOOR_REQUIRE_ACK',
          'DRAWDOWN_CAP_ENABLED',
          'DRAWDOWN_MAX_PCT',
          'DRAWDOWN_WINDOW_DAYS',
          'DRAWDOWN_HYSTERESIS_PCT',
          'DRAWDOWN_CHECK_INTERVAL',
          'TWO_MAN_RULE_ENABLED',
          'TWO_MAN_RULE_TIMEOUT_SEC',
          'TWO_MAN_RULE_AUTO_REVERT',
          'EXPOSURE_GROWTH_ENABLED',
          'MAX_NEW_TRANCHES_PER_MINUTE',
          'MAX_NOTIONAL_INR_PER_MINUTE',
          'EXPOSURE_GROWTH_QUEUE_ENABLED',
          'MAX_PENDING_NOTIONAL_INR',
          'PENDING_BUDGET_BUFFER_PCT',
        ]}
        title="Capital Protection Configuration"
        defaultExpanded={false}
      />

      {/* Documentation Viewer */}
      <DocumentationViewer
        open={docsOpen}
        onClose={() => setDocsOpen(false)}
        docType="capital-protection"
      />

      {/* Configuration Change Confirmation Dialog */}
      <ConfigChangeConfirmDialog 
        open={confirmDialogOpen}
        onClose={handleCancelConfirm}
        onConfirm={handleConfirmChanges}
        changesSummary={changesSummary}
      />
    </Box>
  );
}

export default CapitalProtectionPanel;
