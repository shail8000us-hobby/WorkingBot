import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  Grid,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  LinearProgress,
  Divider,
} from '@mui/material';
import {
  Play,
  Square,
  RefreshCw,
  Plus,
  Settings,
  FileText,
  TrendingUp,
  Activity,
  Cpu,
  HardDrive,
} from 'lucide-react';

const InstanceCard = ({ instance, onStart, onStop, onRestart, onViewLogs, onConfigure }) => {
  const isRunning = instance.status === 'running';
  const statusColor = isRunning ? 'success' : 'default';

  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', mb: 2 }}>
          <Box>
            <Typography variant="h6" gutterBottom>
              {instance.mode === 'live' ? '🔴' : '🟢'} {instance.name}
            </Typography>
            <Chip
              label={instance.status.toUpperCase()}
              color={statusColor}
              size="small"
              sx={{ mr: 1 }}
            />
            <Chip label={instance.mode.toUpperCase()} size="small" variant="outlined" />
          </Box>
          <Tooltip title="Configure">
            <IconButton size="small" onClick={() => onConfigure(instance)}>
              <Settings size={16} />
            </IconButton>
          </Tooltip>
        </Box>

        {isRunning && (
          <>
            <Divider sx={{ my: 2 }} />
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <Typography variant="caption" color="text.secondary">
                  PID
                </Typography>
                <Typography variant="body2">{instance.pid || 'N/A'}</Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="caption" color="text.secondary">
                  Uptime
                </Typography>
                <Typography variant="body2">{instance.uptime || '0m'}</Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="caption" color="text.secondary">
                  CPU
                </Typography>
                <Typography variant="body2">{instance.cpu || '0'}%</Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="caption" color="text.secondary">
                  Memory
                </Typography>
                <Typography variant="body2">{instance.memory || '0'}MB</Typography>
              </Grid>
            </Grid>

            <Divider sx={{ my: 2 }} />
            <Grid container spacing={2}>
              <Grid item xs={12}>
                <Typography variant="caption" color="text.secondary">
                  Grid Range
                </Typography>
                <Typography variant="body2">
                  ${instance.grid?.lower?.toLocaleString() || '0'} - $
                  {instance.grid?.upper?.toLocaleString() || '0'}
                </Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="caption" color="text.secondary">
                  Step
                </Typography>
                <Typography variant="body2">${instance.grid?.step || '0'}</Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="caption" color="text.secondary">
                  Lot Size
                </Typography>
                <Typography variant="body2">{instance.grid?.lot_size || '0'}</Typography>
              </Grid>
            </Grid>

            <Divider sx={{ my: 2 }} />
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <Typography variant="caption" color="text.secondary">
                  P&L
                </Typography>
                <Typography
                  variant="body2"
                  color={instance.pnl >= 0 ? 'success.main' : 'error.main'}
                  fontWeight="bold"
                >
                  {instance.pnl >= 0 ? '+' : ''}₹{instance.pnl?.toLocaleString() || '0'}
                </Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="caption" color="text.secondary">
                  Positions
                </Typography>
                <Typography variant="body2">{instance.positions || 0}</Typography>
              </Grid>
            </Grid>
          </>
        )}

        <Box sx={{ display: 'flex', gap: 1, mt: 3 }}>
          {!isRunning && (
            <Button
              variant="contained"
              color="success"
              size="small"
              startIcon={<Play size={14} />}
              onClick={() => onStart(instance)}
              fullWidth
            >
              Start
            </Button>
          )}
          {isRunning && (
            <>
              <Button
                variant="outlined"
                color="error"
                size="small"
                startIcon={<Square size={14} />}
                onClick={() => onStop(instance)}
                sx={{ flex: 1 }}
              >
                Stop
              </Button>
              <Button
                variant="outlined"
                size="small"
                startIcon={<RefreshCw size={14} />}
                onClick={() => onRestart(instance)}
                sx={{ flex: 1 }}
              >
                Restart
              </Button>
            </>
          )}
        </Box>
        <Button
          variant="text"
          size="small"
          startIcon={<FileText size={14} />}
          onClick={() => onViewLogs(instance)}
          fullWidth
          sx={{ mt: 1 }}
        >
          View Logs
        </Button>
      </CardContent>
    </Card>
  );
};

const MultiInstanceManager = () => {
  const [instances, setInstances] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [configDialogOpen, setConfigDialogOpen] = useState(false);
  const [selectedInstance, setSelectedInstance] = useState(null);

  // New instance form
  const [newInstanceName, setNewInstanceName] = useState('');
  const [newInstanceMode, setNewInstanceMode] = useState('demo');
  const [newInstanceTemplate, setNewInstanceTemplate] = useState('balanced');

  // Fetch instances
  const fetchInstances = useCallback(async () => {
    try {
      const response = await fetch('/api/instances/list');

      if (!response.ok) {
        throw new Error(`Failed to fetch instances: ${response.statusText}`);
      }

      const data = await response.json();

      // Transform API response to component format
      const transformedInstances = data.instances.map((inst) => ({
        id: inst.id,
        name: inst.name,
        mode: inst.mode,
        status: inst.status === 'online' ? 'running' : 'stopped',
        pid: inst.pid,
        uptime: formatUptime(inst.uptime),
        cpu: inst.cpu,
        memory: inst.memory,
        grid: {
          lower: inst.grid.lower_range,
          upper: inst.grid.upper_range,
          step: inst.grid.grid_step,
          lot_size: inst.grid.lot_size,
        },
        pnl: inst.pnl,
        positions: inst.positions,
      }));

      setInstances(transformedInstances);
    } catch (error) {
      console.error('Failed to fetch instances:', error);
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Format uptime from seconds to human-readable
  const formatUptime = (seconds) => {
    if (!seconds) return '0s';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
  };

  // Instance actions
  const handleStart = async (instance) => {
    try {
      const response = await fetch(`/api/instances/${instance.id}/start`, {
        method: 'POST',
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to start instance');
      }

      console.log('Started instance:', instance.id);
      // Refresh instances
      fetchInstances();
    } catch (error) {
      console.error('Error starting instance:', error);
      setError(error.message);
    }
  };

  const handleStop = async (instance) => {
    try {
      const response = await fetch(`/api/instances/${instance.id}/stop`, {
        method: 'POST',
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to stop instance');
      }

      console.log('Stopped instance:', instance.id);
      // Refresh instances
      fetchInstances();
    } catch (error) {
      console.error('Error stopping instance:', error);
      setError(error.message);
    }
  };

  const handleRestart = async (instance) => {
    try {
      const response = await fetch(`/api/instances/${instance.id}/restart`, {
        method: 'POST',
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to restart instance');
      }

      console.log('Restarted instance:', instance.id);
      // Refresh instances
      fetchInstances();
    } catch (error) {
      console.error('Error restarting instance:', error);
      setError(error.message);
    }
  };

  const handleViewLogs = (instance) => {
    console.log('Viewing logs for:', instance.id);
    // TODO: Open logs dialog or navigate to logs view
    // For now, could fetch and display in a dialog
  };

  const handleConfigure = (instance) => {
    setSelectedInstance(instance);
    setConfigDialogOpen(true);
  };

  const handleCreateInstance = async () => {
    try {
      const response = await fetch('/api/instances/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: newInstanceName,
          mode: newInstanceMode,
          strategy: newInstanceTemplate,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to create instance');
      }

      console.log('Created instance:', newInstanceName);

      // Close dialog and reset form
      setCreateDialogOpen(false);
      setNewInstanceName('');

      // Refresh instances
      fetchInstances();
    } catch (error) {
      console.error('Error creating instance:', error);
      setError(error.message);
    }
  };

  useEffect(() => {
    fetchInstances();

    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchInstances, 30000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading) {
    return <LinearProgress />;
  }

  const runningInstances = instances.filter((i) => i.status === 'running').length;
  const stoppedInstances = instances.filter((i) => i.status === 'stopped').length;
  const totalCpu = instances.reduce((sum, i) => sum + (i.cpu || 0), 0);
  const totalMemory = instances.reduce((sum, i) => sum + (i.memory || 0), 0);

  return (
    <Box sx={{ p: 3 }}>
      {/* Error Alert */}
      {error && (
        <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h5">🤖 Bot Instance Manager</Typography>
          <Typography variant="body2" color="text.secondary">
            Run multiple bot instances simultaneously (demo + live)
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button variant="outlined" startIcon={<RefreshCw size={16} />} onClick={fetchInstances}>
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={<Plus size={16} />}
            onClick={() => setCreateDialogOpen(true)}
          >
            New Instance
          </Button>
        </Box>
      </Box>

      {/* Summary Stats */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Grid container spacing={3}>
            <Grid item xs={12} sm={3}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Activity size={20} color="#10b981" />
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Total Instances
                  </Typography>
                  <Typography variant="h6">{instances.length}</Typography>
                </Box>
              </Box>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <TrendingUp size={20} color="#3b82f6" />
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Online / Stopped
                  </Typography>
                  <Typography variant="h6">
                    {runningInstances} / {stoppedInstances}
                  </Typography>
                </Box>
              </Box>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Cpu size={20} color="#f59e0b" />
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Total CPU
                  </Typography>
                  <Typography variant="h6">{totalCpu.toFixed(1)}%</Typography>
                </Box>
              </Box>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <HardDrive size={20} color="#8b5cf6" />
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Total Memory
                  </Typography>
                  <Typography variant="h6">{totalMemory.toFixed(0)}MB</Typography>
                </Box>
              </Box>
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Instance Cards */}
      <Grid container spacing={3}>
        {instances.map((instance) => (
          <Grid item xs={12} md={6} lg={4} key={instance.id}>
            <InstanceCard
              instance={instance}
              onStart={handleStart}
              onStop={handleStop}
              onRestart={handleRestart}
              onViewLogs={handleViewLogs}
              onConfigure={handleConfigure}
            />
          </Grid>
        ))}
      </Grid>

      {instances.length === 0 && (
        <Alert severity="info">No bot instances found. Click "New Instance" to create one.</Alert>
      )}

      {/* Create Instance Dialog */}
      <Dialog open={createDialogOpen} onClose={() => setCreateDialogOpen(false)}>
        <DialogTitle>Create New Bot Instance</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2, display: 'flex', flexDirection: 'column', gap: 2, minWidth: 400 }}>
            <TextField
              label="Instance Name"
              value={newInstanceName}
              onChange={(e) => setNewInstanceName(e.target.value)}
              fullWidth
              placeholder="e.g., gridbot-custom-1"
            />

            <FormControl fullWidth>
              <InputLabel>Trading Mode</InputLabel>
              <Select
                value={newInstanceMode}
                onChange={(e) => setNewInstanceMode(e.target.value)}
                label="Trading Mode"
              >
                <MenuItem value="demo">Demo (Testing)</MenuItem>
                <MenuItem value="live">Live (Real Money)</MenuItem>
              </Select>
            </FormControl>

            <FormControl fullWidth>
              <InputLabel>Strategy Template</InputLabel>
              <Select
                value={newInstanceTemplate}
                onChange={(e) => setNewInstanceTemplate(e.target.value)}
                label="Strategy Template"
              >
                <MenuItem value="conservative">Conservative (Wide grid, small lot)</MenuItem>
                <MenuItem value="aggressive">Aggressive (Tight grid, large lot)</MenuItem>
                <MenuItem value="balanced">Balanced (Medium settings)</MenuItem>
                <MenuItem value="custom">Custom (Manual configuration)</MenuItem>
              </Select>
            </FormControl>

            <Alert severity="info">
              Instance will be created with default configuration. You can customize it after
              creation.
            </Alert>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleCreateInstance} variant="contained" disabled={!newInstanceName}>
            Create & Start
          </Button>
        </DialogActions>
      </Dialog>

      {/* Configure Instance Dialog */}
      <Dialog open={configDialogOpen} onClose={() => setConfigDialogOpen(false)}>
        <DialogTitle>Configure {selectedInstance?.name}</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2, minWidth: 400 }}>
            <Alert severity="info">
              Instance configuration editor will be available here. For now, use the Config Editor
              to modify settings.
            </Alert>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfigDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default MultiInstanceManager;
