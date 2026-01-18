/**
 * ML Model Monitor Component - Phase 5 UI
 *
 * Displays AI learning and monitoring with:
 * - Performance metrics
 * - Model drift detection
 * - Retraining recommendations
 * - Learning statistics
 *
 * Created: January 18, 2026
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  Chip,
  Button,
  CircularProgress,
  Tooltip,
  Grid,
  LinearProgress,
  Divider,
  Card,
  CardContent,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import SchoolIcon from '@mui/icons-material/School';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import AutorenewIcon from '@mui/icons-material/Autorenew';
import InsightsIcon from '@mui/icons-material/Insights';
import MemoryIcon from '@mui/icons-material/Memory';
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActive';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5555';

const MLModelMonitor = () => {
  const [loading, setLoading] = useState(true);
  const [metrics, setMetrics] = useState(null);
  const [drift, setDrift] = useState(null);
  const [retrainStatus, setRetrainStatus] = useState(null);
  const [learningStats, setLearningStats] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [error, setError] = useState(null);

  // Fetch performance metrics
  const fetchMetrics = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/ml/monitor/metrics?days=30`);
      const data = await response.json();
      if (data.success) {
        setMetrics(data.metrics);
      }
    } catch (err) {
      console.error('Error fetching metrics:', err);
    }
  }, []);

  // Fetch drift status
  const fetchDrift = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/ml/monitor/drift`);
      const data = await response.json();
      if (data.success) {
        setDrift(data);
      }
    } catch (err) {
      console.error('Error fetching drift:', err);
    }
  }, []);

  // Fetch retrain status
  const fetchRetrainStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/ml/monitor/should-retrain`);
      const data = await response.json();
      if (data.success) {
        setRetrainStatus(data);
      }
    } catch (err) {
      console.error('Error fetching retrain status:', err);
    }
  }, []);

  // Fetch learning stats
  const fetchLearningStats = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/ml/learning/stats`);
      const data = await response.json();
      if (data.success) {
        setLearningStats(data);
      }
    } catch (err) {
      console.error('Error fetching learning stats:', err);
    }
  }, []);

  // Fetch alerts
  const fetchAlerts = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/ml/monitor/alerts`);
      const data = await response.json();
      if (data.success) {
        setAlerts(data.alerts || []);
      }
    } catch (err) {
      console.error('Error fetching alerts:', err);
    }
  }, []);

  // Refresh all
  const refreshAll = useCallback(async () => {
    setLoading(true);
    await Promise.all([
      fetchMetrics(),
      fetchDrift(),
      fetchRetrainStatus(),
      fetchLearningStats(),
      fetchAlerts(),
    ]);
    setLoading(false);
  }, [fetchMetrics, fetchDrift, fetchRetrainStatus, fetchLearningStats, fetchAlerts]);

  // Initial load
  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  // Helper for metric colors
  const getMetricColor = (value, thresholds) => {
    if (value >= thresholds.good) return '#4caf50';
    if (value >= thresholds.warning) return '#ff9800';
    return '#f44336';
  };

  // Render performance metrics card
  const renderMetricsCard = () => {
    if (!metrics) return null;

    return (
      <Card sx={{ mb: 2, bgcolor: 'rgba(30, 35, 50, 0.9)' }}>
        <CardContent>
          <Box
            sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <TrendingUpIcon />
              <Typography variant="h6">Performance Metrics (30 Days)</Typography>
            </Box>
            <Typography variant="caption" color="text.secondary">
              {metrics.total_trades} trades analyzed
            </Typography>
          </Box>

          <Grid container spacing={3}>
            {/* Win Rate */}
            <Grid item xs={6} md={3}>
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">
                  Win Rate
                </Typography>
                <Box sx={{ position: 'relative', display: 'inline-flex', mt: 1 }}>
                  <CircularProgress
                    variant="determinate"
                    value={metrics.win_rate * 100}
                    size={80}
                    thickness={6}
                    sx={{ color: getMetricColor(metrics.win_rate, { good: 0.5, warning: 0.4 }) }}
                  />
                  <Box
                    sx={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      bottom: 0,
                      right: 0,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <Typography variant="h6">{(metrics.win_rate * 100).toFixed(0)}%</Typography>
                  </Box>
                </Box>
              </Box>
            </Grid>

            {/* Profit Factor */}
            <Grid item xs={6} md={3}>
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">
                  Profit Factor
                </Typography>
                <Typography
                  variant="h4"
                  sx={{
                    mt: 1,
                    color: getMetricColor(metrics.profit_factor, { good: 1.5, warning: 1.0 }),
                  }}
                >
                  {metrics.profit_factor?.toFixed(2) || '0.00'}
                </Typography>
              </Box>
            </Grid>

            {/* Total PnL */}
            <Grid item xs={6} md={3}>
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">
                  Total PnL
                </Typography>
                <Typography
                  variant="h4"
                  sx={{
                    mt: 1,
                    color: metrics.total_pnl >= 0 ? '#4caf50' : '#f44336',
                  }}
                >
                  ${metrics.total_pnl?.toFixed(2) || '0.00'}
                </Typography>
              </Box>
            </Grid>

            {/* Max Drawdown */}
            <Grid item xs={6} md={3}>
              <Box sx={{ textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">
                  Max Drawdown
                </Typography>
                <Typography
                  variant="h4"
                  sx={{
                    mt: 1,
                    color: getMetricColor(1 - metrics.max_drawdown, { good: 0.85, warning: 0.75 }),
                  }}
                >
                  {(metrics.max_drawdown * 100).toFixed(1)}%
                </Typography>
              </Box>
            </Grid>
          </Grid>

          <Divider sx={{ my: 2 }} />

          <Grid container spacing={2}>
            <Grid item xs={4}>
              <Typography variant="caption" color="text.secondary">
                Avg Win
              </Typography>
              <Typography variant="body1" color="success.main">
                +${metrics.avg_win?.toFixed(2) || '0.00'}
              </Typography>
            </Grid>
            <Grid item xs={4}>
              <Typography variant="caption" color="text.secondary">
                Avg Loss
              </Typography>
              <Typography variant="body1" color="error.main">
                -${metrics.avg_loss?.toFixed(2) || '0.00'}
              </Typography>
            </Grid>
            <Grid item xs={4}>
              <Typography variant="caption" color="text.secondary">
                W/L Ratio
              </Typography>
              <Typography variant="body1">
                {metrics.winning_trades}/{metrics.losing_trades}
              </Typography>
            </Grid>
          </Grid>

          {/* AI-Specific Metrics */}
          {(metrics.style_match_avg > 0 || metrics.prediction_accuracy > 0) && (
            <>
              <Divider sx={{ my: 2 }} />
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                AI Performance
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={4}>
                  <Typography variant="caption" color="text.secondary">
                    Style Match
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={metrics.style_match_avg * 100}
                    sx={{ height: 8, borderRadius: 4, mt: 0.5 }}
                  />
                  <Typography variant="body2">
                    {(metrics.style_match_avg * 100).toFixed(0)}%
                  </Typography>
                </Grid>
                <Grid item xs={4}>
                  <Typography variant="caption" color="text.secondary">
                    Confidence Avg
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={metrics.confidence_avg * 100}
                    color="secondary"
                    sx={{ height: 8, borderRadius: 4, mt: 0.5 }}
                  />
                  <Typography variant="body2">
                    {(metrics.confidence_avg * 100).toFixed(0)}%
                  </Typography>
                </Grid>
                <Grid item xs={4}>
                  <Typography variant="caption" color="text.secondary">
                    Prediction Accuracy
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={metrics.prediction_accuracy * 100}
                    color="success"
                    sx={{ height: 8, borderRadius: 4, mt: 0.5 }}
                  />
                  <Typography variant="body2">
                    {(metrics.prediction_accuracy * 100).toFixed(0)}%
                  </Typography>
                </Grid>
              </Grid>
            </>
          )}
        </CardContent>
      </Card>
    );
  };

  // Render drift detection card
  const renderDriftCard = () => {
    const driftDetected = drift?.drift_detected;

    return (
      <Card
        sx={{
          mb: 2,
          bgcolor: driftDetected ? 'rgba(244, 67, 54, 0.1)' : 'rgba(76, 175, 80, 0.1)',
          border: `1px solid ${driftDetected ? '#f44336' : '#4caf50'}40`,
        }}
      >
        <CardContent>
          <Box
            sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {driftDetected ? (
                <WarningAmberIcon sx={{ color: '#f44336' }} />
              ) : (
                <CheckCircleIcon sx={{ color: '#4caf50' }} />
              )}
              <Typography variant="h6">Model Drift Detection</Typography>
            </Box>
            <Chip
              label={driftDetected ? 'DRIFT DETECTED' : 'ALIGNED'}
              color={driftDetected ? 'error' : 'success'}
              size="small"
            />
          </Box>

          {drift ? (
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <Typography variant="caption" color="text.secondary">
                  Call Preference Drift
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={Math.min(drift.call_preference_drift * 100, 100)}
                  color={drift.call_preference_drift > 0.2 ? 'error' : 'success'}
                  sx={{ height: 8, borderRadius: 4, mt: 0.5 }}
                />
                <Typography variant="body2">
                  {(drift.call_preference_drift * 100).toFixed(0)}% deviation
                </Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="caption" color="text.secondary">
                  Timing Match
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={drift.timing_match * 100}
                  color={drift.timing_match < 0.6 ? 'warning' : 'success'}
                  sx={{ height: 8, borderRadius: 4, mt: 0.5 }}
                />
                <Typography variant="body2">
                  {(drift.timing_match * 100).toFixed(0)}% aligned
                </Typography>
              </Grid>
            </Grid>
          ) : (
            <Typography variant="body2" color="text.secondary">
              Analyzing trading patterns...
            </Typography>
          )}

          {drift?.recommendation && (
            <Alert
              severity={driftDetected ? 'warning' : 'info'}
              sx={{ mt: 2, bgcolor: 'transparent' }}
            >
              {drift.recommendation}
            </Alert>
          )}
        </CardContent>
      </Card>
    );
  };

  // Render retrain recommendation card
  const renderRetrainCard = () => {
    if (!retrainStatus) return null;

    const shouldRetrain = retrainStatus.should_retrain;

    return (
      <Card
        sx={{
          mb: 2,
          bgcolor: shouldRetrain ? 'rgba(255, 152, 0, 0.1)' : 'rgba(30, 35, 50, 0.9)',
          border: shouldRetrain ? '2px solid #ff9800' : 'none',
        }}
      >
        <CardContent>
          <Box
            sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <AutorenewIcon sx={{ color: shouldRetrain ? '#ff9800' : '#4caf50' }} />
              <Typography variant="h6">Model Retraining</Typography>
            </Box>

            {shouldRetrain && (
              <Button variant="contained" color="warning" size="small">
                Retrain Now
              </Button>
            )}
          </Box>

          {shouldRetrain ? (
            <Alert severity="warning" sx={{ bgcolor: 'transparent' }}>
              <Typography variant="subtitle2">Retraining Recommended</Typography>
              {retrainStatus.reason}
            </Alert>
          ) : (
            <Alert severity="success" sx={{ bgcolor: 'transparent' }}>
              Model performing within acceptable parameters. No retraining needed.
            </Alert>
          )}
        </CardContent>
      </Card>
    );
  };

  // Render learning stats card
  const renderLearningCard = () => {
    if (!learningStats) return null;

    return (
      <Card sx={{ mb: 2, bgcolor: 'rgba(30, 35, 50, 0.9)' }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
            <MemoryIcon />
            <Typography variant="h6">Reinforcement Learning</Typography>
          </Box>

          <Grid container spacing={2}>
            <Grid item xs={6} md={3}>
              <Typography variant="caption" color="text.secondary">
                Experience Buffer
              </Typography>
              <Typography variant="h5">{learningStats.buffer_size}</Typography>
              <Typography variant="caption" color="text.secondary">
                experiences stored
              </Typography>
            </Grid>
            <Grid item xs={6} md={3}>
              <Typography variant="caption" color="text.secondary">
                States Learned
              </Typography>
              <Typography variant="h5">{learningStats.states_learned}</Typography>
              <Typography variant="caption" color="text.secondary">
                unique states
              </Typography>
            </Grid>
            <Grid item xs={6} md={3}>
              <Typography variant="caption" color="text.secondary">
                Learning Rate
              </Typography>
              <Typography variant="h5">{learningStats.learning_rate}</Typography>
              <Typography variant="caption" color="text.secondary">
                α parameter
              </Typography>
            </Grid>
            <Grid item xs={6} md={3}>
              <Typography variant="caption" color="text.secondary">
                Exploration
              </Typography>
              <Typography variant="h5">
                {(learningStats.exploration_rate * 100).toFixed(0)}%
              </Typography>
              <Typography variant="caption" color="text.secondary">
                ε parameter
              </Typography>
            </Grid>
          </Grid>
        </CardContent>
      </Card>
    );
  };

  // Render alerts
  const renderAlerts = () => {
    if (!alerts || alerts.length === 0) return null;

    return (
      <Card sx={{ bgcolor: 'rgba(30, 35, 50, 0.9)' }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
            <NotificationsActiveIcon />
            <Typography variant="h6">Recent Alerts</Typography>
            <Chip label={alerts.length} size="small" color="warning" />
          </Box>

          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Type</TableCell>
                  <TableCell>Message</TableCell>
                  <TableCell>Severity</TableCell>
                  <TableCell>Time</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {alerts.slice(0, 5).map((alert, i) => (
                  <TableRow key={i}>
                    <TableCell>
                      <Chip label={alert.type?.replace('_', ' ')} size="small" variant="outlined" />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">{alert.message}</Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={alert.severity}
                        size="small"
                        color={
                          alert.severity === 'critical'
                            ? 'error'
                            : alert.severity === 'warning'
                              ? 'warning'
                              : 'info'
                        }
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption">
                        {new Date(alert.timestamp).toLocaleString()}
                      </Typography>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>
    );
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Paper sx={{ p: 2, bgcolor: 'rgba(18, 22, 35, 0.95)' }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <SchoolIcon />
          Model Monitor
        </Typography>

        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={refreshAll}
          disabled={loading}
        >
          Refresh
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Performance Metrics */}
      {renderMetricsCard()}

      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          {/* Drift Detection */}
          {renderDriftCard()}
        </Grid>
        <Grid item xs={12} md={6}>
          {/* Retrain Recommendation */}
          {renderRetrainCard()}
        </Grid>
      </Grid>

      {/* Learning Stats */}
      {renderLearningCard()}

      {/* Alerts */}
      {renderAlerts()}
    </Paper>
  );
};

export default MLModelMonitor;
