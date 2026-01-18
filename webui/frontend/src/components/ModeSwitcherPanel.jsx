import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Switch,
  FormControlLabel,
  TextField,
  Button,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Alert,
  LinearProgress,
  Grid,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  RefreshCw,
  Settings,
  History,
  AlertTriangle,
} from 'lucide-react';

const ModeSwitcherPanel = () => {
  // State
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState(null);
  const [history, setHistory] = useState([]);
  const [configDialogOpen, setConfigDialogOpen] = useState(false);
  const [overrideDialogOpen, setOverrideDialogOpen] = useState(false);

  // Configuration
  const [referencePrice, setReferencePrice] = useState(95500);
  const [hysteresis, setHysteresis] = useState(200);
  const [switchDelay, setSwitchDelay] = useState(30);

  // Manual override
  const [overrideMode, setOverrideMode] = useState('LONG');
  const [overrideDuration, setOverrideDuration] = useState(2);
  const [overrideReason, setOverrideReason] = useState('');

  // Fetch status
  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch('/api/mode-switcher/status');
      const data = await response.json();

      if (data.status === 'success') {
        setStatus(data.mode_switcher);
        setEnabled(data.mode_switcher.enabled);

        if (data.mode_switcher.reference_price) {
          setReferencePrice(data.mode_switcher.reference_price);
        }
        if (data.mode_switcher.hysteresis) {
          setHysteresis(data.mode_switcher.hysteresis);
        }
        if (data.mode_switcher.switch_delay) {
          setSwitchDelay(data.mode_switcher.switch_delay);
        }
      }
    } catch (error) {
      console.error('Failed to fetch mode switcher status:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch history
  const fetchHistory = useCallback(async (hours = 24) => {
    try {
      const response = await fetch(`/api/mode-switcher/history?hours=${hours}`);
      const data = await response.json();

      if (data.status === 'success') {
        setHistory(data.switches);
      }
    } catch (error) {
      console.error('Failed to fetch switch history:', error);
    }
  }, []);

  // Toggle enabled
  const handleToggleEnabled = async () => {
    try {
      const endpoint = enabled ? '/api/mode-switcher/disable' : '/api/mode-switcher/enable';
      const response = await fetch(endpoint, { method: 'POST' });
      const data = await response.json();

      if (data.status === 'success') {
        setEnabled(!enabled);
        fetchStatus();
      }
    } catch (error) {
      console.error('Failed to toggle mode switcher:', error);
    }
  };

  // Save configuration
  const handleSaveConfig = async () => {
    try {
      const response = await fetch('/api/mode-switcher/configure', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reference_price: referencePrice,
          hysteresis: hysteresis,
          switch_delay: switchDelay,
        }),
      });

      const data = await response.json();

      if (data.status === 'success') {
        setConfigDialogOpen(false);
        fetchStatus();
      }
    } catch (error) {
      console.error('Failed to save configuration:', error);
    }
  };

  // Manual override
  const handleManualOverride = async () => {
    try {
      const response = await fetch('/api/mode-switcher/manual-override', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode: overrideMode,
          duration_hours: overrideMode === 'AUTO' ? null : overrideDuration,
          reason: overrideReason || 'Manual override from WebUI',
        }),
      });

      const data = await response.json();

      if (data.status === 'success') {
        setOverrideDialogOpen(false);
        setOverrideReason('');
        fetchStatus();
      }
    } catch (error) {
      console.error('Failed to set manual override:', error);
    }
  };

  // Initial load
  useEffect(() => {
    fetchStatus();
    fetchHistory();

    // Auto-refresh every 10 seconds
    const interval = setInterval(() => {
      fetchStatus();
    }, 10000);

    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading) {
    return <LinearProgress />;
  }

  const currentMode = status?.current_mode || 'NONE';
  const pendingSwitch = status?.pending_switch;
  const manualOverrideActive = status?.manual_override_active;
  const longActivatePrice = status?.long_activate_price || 0;
  const shortActivatePrice = status?.short_activate_price || 0;

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h5">🔄 Auto Mode Switcher</Typography>
        <Box>
          <Tooltip title="Configure">
            <IconButton onClick={() => setConfigDialogOpen(true)}>
              <Settings size={20} />
            </IconButton>
          </Tooltip>
          <Tooltip title="Refresh">
            <IconButton onClick={fetchStatus}>
              <RefreshCw size={20} />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Status Card */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <FormControlLabel
                control={
                  <Switch checked={enabled} onChange={handleToggleEnabled} color="primary" />
                }
                label={enabled ? 'Auto-switching ENABLED' : 'Auto-switching DISABLED'}
              />

              <Box sx={{ mt: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Current Mode:
                </Typography>
                <Chip
                  label={currentMode}
                  color={
                    currentMode === 'LONG'
                      ? 'success'
                      : currentMode === 'SHORT'
                        ? 'error'
                        : 'default'
                  }
                  icon={
                    currentMode === 'LONG' ? (
                      <TrendingUp size={16} />
                    ) : currentMode === 'SHORT' ? (
                      <TrendingDown size={16} />
                    ) : (
                      <Minus size={16} />
                    )
                  }
                  sx={{ mt: 1 }}
                />

                {pendingSwitch && (
                  <Chip
                    label={`Pending: ${pendingSwitch}`}
                    color="warning"
                    size="small"
                    sx={{ ml: 1, mt: 1 }}
                  />
                )}
              </Box>

              {manualOverrideActive && (
                <Alert severity="warning" sx={{ mt: 2 }}>
                  <strong>Manual Override Active</strong>
                  <br />
                  Mode: {status.manual_override_mode}
                  {status.manual_override_until && (
                    <>
                      <br />
                      Until: {new Date(status.manual_override_until).toLocaleString()}
                    </>
                  )}
                </Alert>
              )}
            </Grid>

            <Grid item xs={12} md={6}>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Price Thresholds:
              </Typography>
              <Box sx={{ mt: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Chip
                    label={`LONG < $${longActivatePrice.toLocaleString()}`}
                    color="success"
                    size="small"
                  />
                  <Chip
                    label={`SHORT > $${shortActivatePrice.toLocaleString()}`}
                    color="error"
                    size="small"
                  />
                </Box>

                <Typography variant="caption" color="text.secondary">
                  Reference: ${referencePrice.toLocaleString()} ± ${hysteresis.toLocaleString()}
                </Typography>

                <LinearProgress
                  variant="determinate"
                  value={50}
                  sx={{ mt: 2, height: 8, borderRadius: 4 }}
                />
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
                  <Typography variant="caption">LONG Zone</Typography>
                  <Typography variant="caption">Hysteresis</Typography>
                  <Typography variant="caption">SHORT Zone</Typography>
                </Box>
              </Box>
            </Grid>
          </Grid>

          <Box sx={{ mt: 3, display: 'flex', gap: 2 }}>
            <Button
              variant="outlined"
              onClick={() => setOverrideDialogOpen(true)}
              startIcon={<AlertTriangle size={16} />}
            >
              Manual Override
            </Button>
            <Button
              variant="outlined"
              onClick={() => fetchHistory(24)}
              startIcon={<History size={16} />}
            >
              View History
            </Button>
          </Box>
        </CardContent>
      </Card>

      {/* Switch History */}
      {history.length > 0 && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Switch History (Last 24 hours)
            </Typography>
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Time</TableCell>
                    <TableCell>Price</TableCell>
                    <TableCell>From → To</TableCell>
                    <TableCell>Reason</TableCell>
                    <TableCell>Trigger</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {history.slice(0, 10).map((event, index) => (
                    <TableRow key={index}>
                      <TableCell>{new Date(event.timestamp).toLocaleTimeString()}</TableCell>
                      <TableCell>${event.price.toLocaleString()}</TableCell>
                      <TableCell>
                        <Chip
                          label={`${event.from_mode} → ${event.to_mode}`}
                          size="small"
                          color={event.to_mode === 'LONG' ? 'success' : 'error'}
                        />
                      </TableCell>
                      <TableCell>{event.reason}</TableCell>
                      <TableCell>
                        <Chip
                          label={event.trigger}
                          size="small"
                          variant={event.trigger === 'manual' ? 'outlined' : 'filled'}
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      )}

      {/* Configuration Dialog */}
      <Dialog open={configDialogOpen} onClose={() => setConfigDialogOpen(false)}>
        <DialogTitle>Mode Switcher Configuration</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2, display: 'flex', flexDirection: 'column', gap: 2, minWidth: 400 }}>
            <TextField
              label="Reference Price ($)"
              type="number"
              value={referencePrice}
              onChange={(e) => setReferencePrice(Number(e.target.value))}
              fullWidth
            />
            <TextField
              label="Hysteresis ($)"
              type="number"
              value={hysteresis}
              onChange={(e) => setHysteresis(Number(e.target.value))}
              fullWidth
              helperText="Buffer zone to prevent flip-flopping"
            />
            <TextField
              label="Switch Delay (seconds)"
              type="number"
              value={switchDelay}
              onChange={(e) => setSwitchDelay(Number(e.target.value))}
              fullWidth
              helperText="Minimum time between switches"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfigDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleSaveConfig} variant="contained">
            Save
          </Button>
        </DialogActions>
      </Dialog>

      {/* Manual Override Dialog */}
      <Dialog open={overrideDialogOpen} onClose={() => setOverrideDialogOpen(false)}>
        <DialogTitle>Manual Mode Override</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2, display: 'flex', flexDirection: 'column', gap: 2, minWidth: 400 }}>
            <FormControl fullWidth>
              <InputLabel>Override Mode</InputLabel>
              <Select
                value={overrideMode}
                onChange={(e) => setOverrideMode(e.target.value)}
                label="Override Mode"
              >
                <MenuItem value="LONG">LONG (Force long positions)</MenuItem>
                <MenuItem value="SHORT">SHORT (Force short positions)</MenuItem>
                <MenuItem value="AUTO">AUTO (Resume auto-switching)</MenuItem>
              </Select>
            </FormControl>

            {overrideMode !== 'AUTO' && (
              <TextField
                label="Duration (hours)"
                type="number"
                value={overrideDuration}
                onChange={(e) => setOverrideDuration(Number(e.target.value))}
                fullWidth
                helperText="Leave empty for indefinite override"
              />
            )}

            <TextField
              label="Reason (optional)"
              value={overrideReason}
              onChange={(e) => setOverrideReason(e.target.value)}
              fullWidth
              multiline
              rows={2}
            />

            {overrideMode !== 'AUTO' && (
              <Alert severity="warning">
                Auto-switching will be temporarily disabled during manual override
              </Alert>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOverrideDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleManualOverride} variant="contained" color="warning">
            Apply Override
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ModeSwitcherPanel;
