/**
 * AutomationControls Component
 *
 * Controls for strategy automation services:
 * - Strategy Monitor (auto-exit)
 * - Auto-Entry (condition-based entry)
 * - Risk settings
 *
 * Created: January 5, 2026
 * Phase 3: Automation & Monitoring
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  Switch,
  Button,
  FormControlLabel,
  Grid,
  Alert,
  Chip,
  Divider,
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Tooltip,
  CircularProgress,
} from '@mui/material';
import {
  PlayArrow,
  Stop,
  Settings,
  MonitorHeart,
  AutoMode,
  Shield,
  Notifications,
  Refresh,
  CheckCircle,
  Warning,
  Error as ErrorIcon,
} from '@mui/icons-material';

const API_BASE = '/api/options-strategy';

const AutomationControls = ({ onStatusChange }) => {
  // State
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [automationStatus, setAutomationStatus] = useState({
    monitor: { running: false, check_interval: 10, strategies_tracked: 0 },
    auto_entry: { running: false, check_interval: 30, pending_attempts: {} },
  });
  const [riskLimits, setRiskLimits] = useState(null);
  const [showRiskDialog, setShowRiskDialog] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);

  // Fetch automation status
  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/automation/status`);
      const data = await response.json();
      setAutomationStatus(data);
      onStatusChange?.(data);
    } catch (err) {
      console.error('Failed to fetch automation status:', err);
    }
  }, [onStatusChange]);

  // Fetch risk limits
  const fetchRiskLimits = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/risk/limits`);
      const data = await response.json();
      setRiskLimits(data.limits);
    } catch (err) {
      console.error('Failed to fetch risk limits:', err);
    }
  }, []);

  // Fetch notifications
  const fetchNotifications = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/notifications?limit=10`);
      const data = await response.json();
      setNotifications(data.notifications || []);
      setUnreadCount(data.unread_count || 0);
    } catch (err) {
      console.error('Failed to fetch notifications:', err);
    }
  }, []);

  // Initial load
  useEffect(() => {
    const loadAll = async () => {
      setLoading(true);
      await Promise.all([fetchStatus(), fetchRiskLimits(), fetchNotifications()]);
      setLoading(false);
    };
    loadAll();

    // Poll status every 30 seconds
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, [fetchStatus, fetchRiskLimits, fetchNotifications]);

  // Toggle monitor
  const toggleMonitor = async () => {
    setError(null);
    try {
      const endpoint = automationStatus.monitor.running ? '/monitor/stop' : '/monitor/start';

      const response = await fetch(`${API_BASE}${endpoint}`, { method: 'POST' });
      const data = await response.json();

      if (data.success) {
        await fetchStatus();
      } else {
        setError(data.error || 'Failed to toggle monitor');
      }
    } catch (err) {
      setError(err.message);
    }
  };

  // Toggle auto-entry
  const toggleAutoEntry = async () => {
    setError(null);
    try {
      const endpoint = automationStatus.auto_entry.running
        ? '/auto-entry/stop'
        : '/auto-entry/start';

      const response = await fetch(`${API_BASE}${endpoint}`, { method: 'POST' });
      const data = await response.json();

      if (data.success) {
        await fetchStatus();
      } else {
        setError(data.error || 'Failed to toggle auto-entry');
      }
    } catch (err) {
      setError(err.message);
    }
  };

  // Start all automation
  const startAll = async () => {
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/automation/start-all`, { method: 'POST' });
      const data = await response.json();

      if (data.success) {
        await fetchStatus();
      } else {
        setError(data.error || 'Failed to start automation');
      }
    } catch (err) {
      setError(err.message);
    }
  };

  // Stop all automation
  const stopAll = async () => {
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/automation/stop-all`, { method: 'POST' });
      const data = await response.json();

      if (data.success) {
        await fetchStatus();
      } else {
        setError(data.error || 'Failed to stop automation');
      }
    } catch (err) {
      setError(err.message);
    }
  };

  // Update risk limits
  const handleUpdateRiskLimits = async (updates) => {
    try {
      const response = await fetch(`${API_BASE}/risk/limits`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      const data = await response.json();

      if (data.success) {
        setRiskLimits(data.limits);
        setShowRiskDialog(false);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  // Mark notifications as read
  const markAllRead = async () => {
    try {
      await fetch(`${API_BASE}/notifications/read`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mark_all: true }),
      });
      await fetchNotifications();
    } catch (err) {
      console.error('Failed to mark notifications as read:', err);
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" p={3}>
        <CircularProgress />
      </Box>
    );
  }

  const monitorRunning = automationStatus.monitor?.running;
  const autoEntryRunning = automationStatus.auto_entry?.running;
  const allRunning = monitorRunning && autoEntryRunning;

  return (
    <Box>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Grid container spacing={2}>
        {/* Main Controls */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
              <Typography variant="h6">🤖 Automation Services</Typography>
              <IconButton size="small" onClick={fetchStatus}>
                <Refresh />
              </IconButton>
            </Box>

            {/* Global Controls */}
            <Box display="flex" gap={1} mb={2}>
              <Button
                variant="contained"
                color="success"
                startIcon={<PlayArrow />}
                onClick={startAll}
                disabled={allRunning}
                size="small"
              >
                Start All
              </Button>
              <Button
                variant="outlined"
                color="error"
                startIcon={<Stop />}
                onClick={stopAll}
                disabled={!monitorRunning && !autoEntryRunning}
                size="small"
              >
                Stop All
              </Button>
            </Box>

            <Divider sx={{ my: 2 }} />

            {/* Monitor Service */}
            <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
              <Box display="flex" alignItems="center" gap={1}>
                <MonitorHeart color={monitorRunning ? 'success' : 'disabled'} />
                <Box>
                  <Typography variant="subtitle2">Strategy Monitor</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Auto-exit on profit target / stop loss
                  </Typography>
                </Box>
              </Box>
              <FormControlLabel
                control={
                  <Switch checked={monitorRunning} onChange={toggleMonitor} color="success" />
                }
                label={monitorRunning ? 'Running' : 'Stopped'}
              />
            </Box>

            {monitorRunning && (
              <Box ml={4} mb={2}>
                <Chip
                  size="small"
                  icon={<CheckCircle />}
                  label={`Tracking ${automationStatus.monitor.strategies_tracked || 0} strategies`}
                  color="success"
                  variant="outlined"
                />
                <Typography variant="caption" display="block" color="text.secondary" mt={0.5}>
                  Check interval: {automationStatus.monitor.check_interval}s
                </Typography>
              </Box>
            )}

            {/* Auto-Entry Service */}
            <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
              <Box display="flex" alignItems="center" gap={1}>
                <AutoMode color={autoEntryRunning ? 'success' : 'disabled'} />
                <Box>
                  <Typography variant="subtitle2">Auto-Entry</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Execute when entry conditions met
                  </Typography>
                </Box>
              </Box>
              <FormControlLabel
                control={
                  <Switch checked={autoEntryRunning} onChange={toggleAutoEntry} color="success" />
                }
                label={autoEntryRunning ? 'Running' : 'Stopped'}
              />
            </Box>

            {autoEntryRunning && (
              <Box ml={4}>
                <Chip
                  size="small"
                  icon={<CheckCircle />}
                  label="Monitoring pending strategies"
                  color="success"
                  variant="outlined"
                />
                <Typography variant="caption" display="block" color="text.secondary" mt={0.5}>
                  Check interval: {automationStatus.auto_entry.check_interval}s
                </Typography>
              </Box>
            )}
          </Paper>
        </Grid>

        {/* Risk & Notifications */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
              <Typography variant="h6">🛡️ Risk & Notifications</Typography>
            </Box>

            {/* Risk Limits Summary */}
            <Box
              display="flex"
              alignItems="center"
              justifyContent="space-between"
              mb={2}
              p={1.5}
              bgcolor="action.hover"
              borderRadius={1}
            >
              <Box display="flex" alignItems="center" gap={1}>
                <Shield color="primary" />
                <Box>
                  <Typography variant="subtitle2">Risk Limits</Typography>
                  {riskLimits && (
                    <Typography variant="caption" color="text.secondary">
                      Max ${riskLimits.max_strategy_cost?.toLocaleString()} per strategy
                    </Typography>
                  )}
                </Box>
              </Box>
              <Button size="small" startIcon={<Settings />} onClick={() => setShowRiskDialog(true)}>
                Configure
              </Button>
            </Box>

            <Divider sx={{ my: 2 }} />

            {/* Notifications */}
            <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
              <Box display="flex" alignItems="center" gap={1}>
                <Notifications color={unreadCount > 0 ? 'warning' : 'disabled'} />
                <Typography variant="subtitle2">
                  Recent Notifications
                  {unreadCount > 0 && (
                    <Chip
                      size="small"
                      label={unreadCount}
                      color="warning"
                      sx={{ ml: 1, height: 20 }}
                    />
                  )}
                </Typography>
              </Box>
              {unreadCount > 0 && (
                <Button size="small" onClick={markAllRead}>
                  Mark All Read
                </Button>
              )}
            </Box>

            <List dense sx={{ maxHeight: 200, overflow: 'auto' }}>
              {notifications.length === 0 ? (
                <ListItem>
                  <ListItemText secondary="No recent notifications" sx={{ textAlign: 'center' }} />
                </ListItem>
              ) : (
                notifications.slice(0, 5).map((notif) => (
                  <ListItem
                    key={notif.id}
                    sx={{ bgcolor: notif.read ? 'transparent' : 'action.selected' }}
                  >
                    <ListItemIcon sx={{ minWidth: 36 }}>
                      {notif.notification_type === 'success' && (
                        <CheckCircle color="success" fontSize="small" />
                      )}
                      {notif.notification_type === 'warning' && (
                        <Warning color="warning" fontSize="small" />
                      )}
                      {notif.notification_type === 'error' && (
                        <ErrorIcon color="error" fontSize="small" />
                      )}
                      {notif.notification_type === 'info' && (
                        <Notifications color="info" fontSize="small" />
                      )}
                    </ListItemIcon>
                    <ListItemText
                      primary={notif.title}
                      secondary={new Date(notif.timestamp).toLocaleString()}
                      primaryTypographyProps={{ variant: 'body2', noWrap: true }}
                      secondaryTypographyProps={{ variant: 'caption' }}
                    />
                  </ListItem>
                ))
              )}
            </List>
          </Paper>
        </Grid>
      </Grid>

      {/* Risk Limits Dialog */}
      <RiskLimitsDialog
        open={showRiskDialog}
        onClose={() => setShowRiskDialog(false)}
        limits={riskLimits}
        onSave={handleUpdateRiskLimits}
      />
    </Box>
  );
};

// Risk Limits Configuration Dialog
const RiskLimitsDialog = ({ open, onClose, limits, onSave }) => {
  const [formData, setFormData] = useState({});

  useEffect(() => {
    if (limits) {
      setFormData(limits);
    }
  }, [limits]);

  const handleChange = (field) => (e) => {
    setFormData((prev) => ({
      ...prev,
      [field]: parseFloat(e.target.value) || 0,
    }));
  };

  const handleSave = () => {
    onSave(formData);
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>⚙️ Risk Limits Configuration</DialogTitle>
      <DialogContent>
        <Box sx={{ pt: 1 }}>
          <Typography variant="subtitle2" color="text.secondary" gutterBottom>
            Capital Limits
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={6}>
              <TextField
                fullWidth
                label="Max Strategy Cost ($)"
                type="number"
                value={formData.max_strategy_cost || ''}
                onChange={handleChange('max_strategy_cost')}
                size="small"
              />
            </Grid>
            <Grid item xs={6}>
              <TextField
                fullWidth
                label="Max Total Exposure ($)"
                type="number"
                value={formData.max_total_exposure || ''}
                onChange={handleChange('max_total_exposure')}
                size="small"
              />
            </Grid>
          </Grid>

          <Typography variant="subtitle2" color="text.secondary" gutterBottom sx={{ mt: 2 }}>
            Position Limits
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={4}>
              <TextField
                fullWidth
                label="Max Active Strategies"
                type="number"
                value={formData.max_active_strategies || ''}
                onChange={handleChange('max_active_strategies')}
                size="small"
              />
            </Grid>
            <Grid item xs={4}>
              <TextField
                fullWidth
                label="Max Per Underlying"
                type="number"
                value={formData.max_strategies_per_underlying || ''}
                onChange={handleChange('max_strategies_per_underlying')}
                size="small"
              />
            </Grid>
            <Grid item xs={4}>
              <TextField
                fullWidth
                label="Max Legs Per Strategy"
                type="number"
                value={formData.max_legs_per_strategy || ''}
                onChange={handleChange('max_legs_per_strategy')}
                size="small"
              />
            </Grid>
          </Grid>

          <Typography variant="subtitle2" color="text.secondary" gutterBottom sx={{ mt: 2 }}>
            Greeks Limits
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={4}>
              <TextField
                fullWidth
                label="Max Portfolio Delta"
                type="number"
                value={formData.max_portfolio_delta || ''}
                onChange={handleChange('max_portfolio_delta')}
                size="small"
              />
            </Grid>
            <Grid item xs={4}>
              <TextField
                fullWidth
                label="Max Portfolio Vega"
                type="number"
                value={formData.max_portfolio_vega || ''}
                onChange={handleChange('max_portfolio_vega')}
                size="small"
              />
            </Grid>
            <Grid item xs={4}>
              <TextField
                fullWidth
                label="Max Neg Theta ($/day)"
                type="number"
                value={formData.max_negative_theta || ''}
                onChange={handleChange('max_negative_theta')}
                size="small"
              />
            </Grid>
          </Grid>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={handleSave} variant="contained" color="primary">
          Save Changes
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default AutomationControls;
