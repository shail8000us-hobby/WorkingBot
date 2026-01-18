// ═══════════════════════════════════════════════════════════════════════════
// 🎯 Opportunistic Recovery Panel Component
// ═══════════════════════════════════════════════════════════════════════════
//
// "Trading halts due to high volatility are a blessing, not missed opportunities."
//
// ═══════════════════════════════════════════════════════════════════════════

import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Paper,
  Chip,
  Alert,
  Button,
  Switch,
  FormControlLabel,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  CircularProgress,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  CheckCircle as CheckCircleIcon,
  Settings as SettingsIcon,
  Timeline as TimelineIcon
} from '@mui/icons-material';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer
} from 'recharts';
import { useInstance, parseInstanceName } from '../context/InstanceContext';
import SymbolBadge from './common/SymbolBadge';

// ═══════════════════════════════════════════════════════════════════════════
// Main Component
// ═══════════════════════════════════════════════════════════════════════════

const OpportunisticRecoveryPanel = ({ socket }) => {
  const { selectedInstance } = useInstance();
  const instanceInfo = parseInstanceName(selectedInstance);
  const [recoveryHistory, setRecoveryHistory] = useState([]);
  const [stats, setStats] = useState({
    totalHalts: 0,
    successfulRecoveries: 0,
    totalExtraProfit: 0,
    avgExtraProfit: 0,
    levelsFilled: 0
  });
  const [config, setConfig] = useState({
    enabled: true,
    maxOrders: 5,
    delayMs: 300,
    minProfitInr: 500
  });
  const [loading, setLoading] = useState(true);

  // ═════════════════════════════════════════════════════════════════════════
  // WebSocket Event Handlers
  // ═════════════════════════════════════════════════════════════════════════

  useEffect(() => {
    if (!socket) return;

    // v6.0: Filter WebSocket events by instance
    const handleRecoveryHistory = (data) => {
      if (data && data.history) {
        // Filter history for selected instance if provided
        let history = data.history;
        if (selectedInstance && data.instance && data.instance !== selectedInstance) {
          return; // Ignore events from other instances
        }
        setRecoveryHistory(history);
      }
      setLoading(false);
    };

    const handleRecoveryStats = (data) => {
      if (data) {
        // Filter stats for selected instance if provided
        if (selectedInstance && data.instance && data.instance !== selectedInstance) {
          return; // Ignore stats from other instances
        }
        setStats(data);
      }
      setLoading(false);
    };

    const handleRecoveryCompleted = (data) => {
      // Filter recovery events for selected instance
      if (selectedInstance && data.instance && data.instance !== selectedInstance) {
        return; // Ignore events from other instances
      }
      setRecoveryHistory((prev) => [data, ...prev].slice(0, 10));
      updateStats(data);
    };

    const handleRecoveryConfig = (data) => {
      if (data && data.config) {
        setConfig(data.config);
      }
      setLoading(false);
    };

    const handleConfigUpdated = (data) => {
      if (data && data.config) {
        setConfig(data.config);
      }
    };

    socket.on('recovery_history', handleRecoveryHistory);
    socket.on('recovery_stats', handleRecoveryStats);
    socket.on('recovery_completed', handleRecoveryCompleted);
    socket.on('recovery_config', handleRecoveryConfig);
    socket.on('recovery_config_updated', handleConfigUpdated);

    // Request initial data
    socket.emit('get_recovery_history');
    socket.emit('get_recovery_stats');
    socket.emit('get_recovery_config');

    // Fallback timeout
    const timeout = setTimeout(() => {
      setLoading(false);
    }, 3000);

    return () => {
      socket.off('recovery_history', handleRecoveryHistory);
      socket.off('recovery_stats', handleRecoveryStats);
      socket.off('recovery_completed', handleRecoveryCompleted);
      socket.off('recovery_config', handleRecoveryConfig);
      socket.off('recovery_config_updated', handleConfigUpdated);
      clearTimeout(timeout);
    };
  }, [socket]);

  // ═════════════════════════════════════════════════════════════════════════
  // Update Statistics
  // ═════════════════════════════════════════════════════════════════════════

  const updateStats = (newRecovery) => {
    setStats((prev) => ({
      totalHalts: prev.totalHalts + 1,
      successfulRecoveries: prev.successfulRecoveries + 1,
      totalExtraProfit: prev.totalExtraProfit + newRecovery.totalExtraProfit,
      avgExtraProfit:
        (prev.totalExtraProfit + newRecovery.totalExtraProfit) /
        (prev.successfulRecoveries + 1),
      levelsFilled: prev.levelsFilled + newRecovery.levelsFilled
    }));
  };

  // ═════════════════════════════════════════════════════════════════════════
  // Loading State
  // ═════════════════════════════════════════════════════════════════════════

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  // ═════════════════════════════════════════════════════════════════════════
  // Render
  // ═════════════════════════════════════════════════════════════════════════

  return (
    <Box>
      {/* Motivational Quote */}
      <Alert severity="info" sx={{ mb: 3 }} icon={<TrendingUpIcon />}>
        <strong>Trading halts are blessings, not missed opportunities.</strong>
        <Typography variant="body2" sx={{ mt: 0.5 }}>
          When volatility halts trading and price drops, we fill missed grid levels at better prices for extra profit.
        </Typography>
      </Alert>

      <Grid container spacing={3}>
        {/* Statistics Card */}
        <Grid item xs={12} md={6}>
          <StatsCard stats={stats} />
        </Grid>

        {/* Configuration Panel */}
        <Grid item xs={12} md={6}>
          <ConfigPanel config={config} setConfig={setConfig} socket={socket} />
        </Grid>

        {/* Recovery History */}
        <Grid item xs={12}>
          <RecoveryHistory history={recoveryHistory} />
        </Grid>

        {/* Cumulative Profit Chart */}
        <Grid item xs={12}>
          <ProfitChart history={recoveryHistory} />
        </Grid>
      </Grid>
    </Box>
  );
};

// ═══════════════════════════════════════════════════════════════════════════
// Statistics Card Component
// ═══════════════════════════════════════════════════════════════════════════

const StatsCard = ({ stats }) => {
  const successRate =
    stats.totalHalts > 0
      ? ((stats.successfulRecoveries / stats.totalHalts) * 100).toFixed(1)
      : 0;

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Recovery Statistics (30 Days)
        </Typography>

        <Grid container spacing={2}>
          <Grid item xs={6}>
            <Paper elevation={0} sx={{ p: 2, bgcolor: 'background.default' }}>
              <Typography variant="caption" color="text.secondary">
                Total Halts
              </Typography>
              <Typography variant="h5" fontWeight="bold">
                {stats.totalHalts}
              </Typography>
            </Paper>
          </Grid>

          <Grid item xs={6}>
            <Paper elevation={0} sx={{ p: 2, bgcolor: 'background.default' }}>
              <Typography variant="caption" color="text.secondary">
                Success Rate
              </Typography>
              <Typography variant="h5" fontWeight="bold" color="success.main">
                {successRate}%
              </Typography>
            </Paper>
          </Grid>

          <Grid item xs={6}>
            <Paper elevation={0} sx={{ p: 2, bgcolor: 'background.default' }}>
              <Typography variant="caption" color="text.secondary">
                Levels Filled
              </Typography>
              <Typography variant="h5" fontWeight="bold">
                {stats.levelsFilled}
              </Typography>
            </Paper>
          </Grid>

          <Grid item xs={6}>
            <Paper elevation={0} sx={{ p: 2, bgcolor: 'background.default' }}>
              <Typography variant="caption" color="text.secondary">
                Avg Extra
              </Typography>
              <Typography variant="h5" fontWeight="bold">
                ₹{Math.round(stats.avgExtraProfit).toLocaleString()}
              </Typography>
            </Paper>
          </Grid>

          <Grid item xs={12}>
            <Paper
              elevation={0}
              sx={{
                p: 2,
                bgcolor: 'success.dark',
                border: '2px solid',
                borderColor: 'success.main'
              }}
            >
              <Typography variant="caption" sx={{ color: 'success.light' }}>
                Total Extra Profit
              </Typography>
              <Typography variant="h4" fontWeight="bold" sx={{ color: 'success.light' }}>
                ₹{stats.totalExtraProfit.toLocaleString()}
              </Typography>
            </Paper>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
};

// ═══════════════════════════════════════════════════════════════════════════
// Recovery History Component
// ═══════════════════════════════════════════════════════════════════════════

const RecoveryHistory = ({ history }) => {
  if (history.length === 0) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Recent Opportunistic Recoveries
          </Typography>
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <TimelineIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 2 }} />
            <Typography variant="body2" color="text.secondary">
              No recoveries yet
            </Typography>
            <Typography variant="caption" color="text.disabled">
              When volatility halts occur and normalize, recoveries will appear here.
            </Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Recent Opportunistic Recoveries
        </Typography>

        <List>
          {history.map((recovery, idx) => (
            <React.Fragment key={idx}>
              <ListItem alignItems="flex-start">
                <ListItemIcon>
                  <CheckCircleIcon color="success" />
                </ListItemIcon>
                <ListItemText
                  primary={
                    <Typography variant="body2" fontWeight="bold">
                      {new Date(recovery.timestamp).toLocaleString()} - Filled{' '}
                      {recovery.levelsFilled} level{recovery.levelsFilled > 1 ? 's' : ''} @{' '}
                      ₹{recovery.fillPrice?.toLocaleString()}
                    </Typography>
                  }
                  secondary={
                    <Box sx={{ mt: 1 }}>
                      {recovery.positions?.map((pos, pidx) => (
                        <Typography key={pidx} variant="caption" display="block">
                          • Grid: ₹{pos.gridLevel?.toLocaleString()} → TP: ₹
                          {pos.tpPrice?.toLocaleString()} (
                          <span style={{ color: '#4ade80' }}>
                            +₹{pos.extraProfit?.toLocaleString()} extra
                          </span>
                          )
                        </Typography>
                      ))}
                      <Chip
                        label={`Total Blessing: ₹${recovery.totalExtraProfit?.toLocaleString()} 🎯`}
                        color="success"
                        size="small"
                        sx={{ mt: 1 }}
                      />
                    </Box>
                  }
                />
              </ListItem>
              {idx < history.length - 1 && <Divider variant="inset" component="li" />}
            </React.Fragment>
          ))}
        </List>
      </CardContent>
    </Card>
  );
};

// ═══════════════════════════════════════════════════════════════════════════
// Profit Chart Component
// ═══════════════════════════════════════════════════════════════════════════

const ProfitChart = ({ history }) => {
  // Calculate cumulative profit
  const chartData = [];
  let cumulative = 0;

  history
    .slice()
    .reverse()
    .forEach((recovery) => {
      cumulative += recovery.totalExtraProfit || 0;
      chartData.push({
        timestamp: new Date(recovery.timestamp).toLocaleDateString(),
        profit: cumulative
      });
    });

  if (chartData.length === 0) {
    return null;
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Cumulative Extra Profit from Volatility
        </Typography>

        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis dataKey="timestamp" stroke="#888" />
            <YAxis stroke="#888" />
            <RechartsTooltip
              contentStyle={{
                backgroundColor: '#1a1a1a',
                border: '1px solid #333',
                borderRadius: '8px'
              }}
              formatter={(value) => `₹${value.toLocaleString()}`}
            />
            <Area
              type="monotone"
              dataKey="profit"
              stroke="#4ade80"
              fill="#4ade8033"
              strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>

        <Alert severity="success" sx={{ mt: 2 }} icon={<TrendingUpIcon />}>
          Volatility turned into ₹{cumulative.toLocaleString()} profit!
        </Alert>
      </CardContent>
    </Card>
  );
};

// ═══════════════════════════════════════════════════════════════════════════
// Configuration Panel Component
// ═══════════════════════════════════════════════════════════════════════════

const ConfigPanel = ({ config, setConfig, socket }) => {
  const [localConfig, setLocalConfig] = useState(config);

  useEffect(() => {
    setLocalConfig(config);
  }, [config]);

  const handleSave = () => {
    if (socket) {
      socket.emit('update_recovery_config', localConfig);
    }
  };

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          <SettingsIcon />
          <Typography variant="h6">
            Recovery Settings
          </Typography>
        </Box>

        <FormControlLabel
          control={
            <Switch
              checked={localConfig.enabled}
              onChange={(e) =>
                setLocalConfig({ ...localConfig, enabled: e.target.checked })
              }
            />
          }
          label="Enable Opportunistic Recovery"
        />

        <Box sx={{ mt: 2 }}>
          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Max Levels per Recovery</InputLabel>
            <Select
              value={localConfig.maxOrders}
              onChange={(e) =>
                setLocalConfig({ ...localConfig, maxOrders: e.target.value })
              }
              label="Max Levels per Recovery"
            >
              <MenuItem value={1}>1</MenuItem>
              <MenuItem value={3}>3</MenuItem>
              <MenuItem value={5}>5</MenuItem>
              <MenuItem value={10}>10</MenuItem>
            </Select>
          </FormControl>

          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Execution Delay (ms)</InputLabel>
            <Select
              value={localConfig.delayMs}
              onChange={(e) =>
                setLocalConfig({ ...localConfig, delayMs: e.target.value })
              }
              label="Execution Delay (ms)"
            >
              <MenuItem value={100}>100</MenuItem>
              <MenuItem value={200}>200</MenuItem>
              <MenuItem value={300}>300</MenuItem>
              <MenuItem value={500}>500</MenuItem>
              <MenuItem value={1000}>1000</MenuItem>
            </Select>
          </FormControl>

          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Min Profit Margin (₹)</InputLabel>
            <Select
              value={localConfig.minProfitInr}
              onChange={(e) =>
                setLocalConfig({ ...localConfig, minProfitInr: e.target.value })
              }
              label="Min Profit Margin (₹)"
            >
              <MenuItem value={100}>100</MenuItem>
              <MenuItem value={500}>500</MenuItem>
              <MenuItem value={1000}>1000</MenuItem>
              <MenuItem value={2000}>2000</MenuItem>
            </Select>
          </FormControl>

          <Button
            variant="contained"
            color="primary"
            fullWidth
            onClick={handleSave}
          >
            Save Changes
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
};

// ═══════════════════════════════════════════════════════════════════════════
// Helper Functions
// ═══════════════════════════════════════════════════════════════════════════

const formatDuration = (seconds) => {
  if (seconds < 60) return `${seconds} seconds`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} minutes`;
  return `${Math.floor(seconds / 3600)} hours`;
};

export default OpportunisticRecoveryPanel;
