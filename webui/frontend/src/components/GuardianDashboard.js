/**
 * Guardian Dashboard - System Health Monitor
 *
 * Real-time monitoring of WebUI robustness features:
 * - System health (backend + bot + resources)
 * - Circuit breaker states (live monitoring)
 * - 24h metrics charts (API latency trends)
 * - Resource usage (CPU, memory, disk)
 *
 * Date: November 12, 2025
 * Part of: WebUI Robustness Plan Week 3
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardHeader,
  CardContent,
  Grid,
  Typography,
  Chip,
  LinearProgress,
  Alert,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  CheckCircle as HealthyIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  Refresh as RefreshIcon,
  TrendingUp,
  TrendingDown,
  Speed as Activity,
} from '@mui/icons-material';
import { useHealth } from '../store';
import { getAllCircuitStates } from '../utils/circuitBreaker';
import { dataAggregator } from '../services/dataAggregator';
import apiClient from '../utils/apiClient';

const StatusBadge = ({ status, label }) => {
  const colors = {
    healthy: 'success',
    degraded: 'warning',
    unhealthy: 'error',
    unknown: 'default',
    CLOSED: 'success',
    HALF_OPEN: 'warning',
    OPEN: 'error',
  };

  const icons = {
    healthy: <HealthyIcon fontSize="small" />,
    degraded: <WarningIcon fontSize="small" />,
    unhealthy: <ErrorIcon fontSize="small" />,
    unknown: <Activity fontSize="small" />,
    CLOSED: <HealthyIcon fontSize="small" />,
    HALF_OPEN: <WarningIcon fontSize="small" />,
    OPEN: <ErrorIcon fontSize="small" />,
  };

  return (
    <Chip
      icon={icons[status] || icons.unknown}
      label={label || status}
      color={colors[status] || 'default'}
      size="small"
      sx={{ fontWeight: 'bold' }}
    />
  );
};

const MetricRow = ({ label, value, unit, trend, healthy = true }) => (
  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
    <Typography variant="body2" color="text.secondary">
      {label}
    </Typography>
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <Typography variant="body2" fontWeight="bold" color={healthy ? 'success.main' : 'error.main'}>
        {value}
        {unit}
      </Typography>
      {trend !== undefined &&
        (trend > 0 ? (
          <TrendingUp fontSize="small" color="success" />
        ) : (
          <TrendingDown fontSize="small" color="error" />
        ))}
    </Box>
  </Box>
);

const CircuitBreakerCard = ({ name, state }) => {
  const isHealthy = state.state === 'CLOSED';
  const timeUntilRetry = state.timeUntilRetry || 0;
  const retrySeconds = Math.ceil(timeUntilRetry / 1000);

  return (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="subtitle2" fontWeight="bold">
            {name}
          </Typography>
          <StatusBadge status={state.state} />
        </Box>

        <Box sx={{ mb: 1 }}>
          <MetricRow
            label="Failures"
            value={state.failureCount}
            unit=""
            healthy={state.failureCount === 0}
          />
          {state.state === 'OPEN' && (
            <MetricRow label="Retry in" value={retrySeconds} unit="s" healthy={false} />
          )}
          {state.lastFailureTime && (
            <Typography variant="caption" color="text.secondary">
              Last failure: {new Date(state.lastFailureTime).toLocaleTimeString()}
            </Typography>
          )}
        </Box>
      </CardContent>
    </Card>
  );
};

function GuardianDashboard() {
  const health = useHealth();
  const [circuitStates, setCircuitStates] = useState({});
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [aggregatorStatus, setAggregatorStatus] = useState({});

  // Fetch metrics and circuit states
  useEffect(() => {
    const fetchData = async () => {
      try {
        // Get 24h metrics for charting
        const metricsData = await apiClient.get('/api/metrics/recent', { hours: 24, limit: 1000 });
        setMetrics(metricsData);
      } catch (error) {
        console.error('Failed to fetch metrics:', error);
      }
    };

    fetchData();
    setLoading(false);

    // Update circuit states every second
    const interval = setInterval(() => {
      const states = getAllCircuitStates();
      setCircuitStates(states);
      setAggregatorStatus(dataAggregator.getStatus());
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  const handleRefresh = async () => {
    setLoading(true);
    await dataAggregator.refresh();
    setLoading(false);
  };

  const overallHealthy = health.status === 'healthy';
  const services = health.services || {};
  const resources = health.resources || {};

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h5" fontWeight="bold" gutterBottom>
            🛡️ Guardian Dashboard
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Real-time system health and robustness monitoring
          </Typography>
        </Box>
        <Tooltip title="Refresh data">
          <IconButton onClick={handleRefresh} disabled={loading}>
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Overall Status Alert */}
      <Alert
        severity={overallHealthy ? 'success' : health.status === 'degraded' ? 'warning' : 'error'}
        sx={{ mb: 3 }}
        icon={overallHealthy ? <HealthyIcon /> : <WarningIcon />}
      >
        <Typography variant="subtitle2" fontWeight="bold">
          System Status: {health.status?.toUpperCase() || 'UNKNOWN'}
        </Typography>
        <Typography variant="body2">
          {overallHealthy
            ? 'All systems operational. WebUI is running smoothly.'
            : 'Some issues detected. Check details below.'}
        </Typography>
      </Alert>

      <Grid container spacing={3}>
        {/* Services Status */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardHeader title="Services" />
            <CardContent>
              {Object.entries(services).map(([name, service]) => (
                <Box key={name} sx={{ mb: 2 }}>
                  <Box
                    sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                  >
                    <Typography variant="body2">
                      {name.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                    </Typography>
                    <StatusBadge
                      status={service.healthy ? 'healthy' : 'unhealthy'}
                      label={service.status}
                    />
                  </Box>
                </Box>
              ))}
            </CardContent>
          </Card>
        </Grid>

        {/* Resources */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardHeader title="Resources" />
            <CardContent>
              {/* CPU */}
              {resources.cpu && (
                <Box sx={{ mb: 2 }}>
                  <MetricRow
                    label="CPU Usage"
                    value={resources.cpu.percent}
                    unit="%"
                    healthy={resources.cpu.healthy}
                  />
                  <LinearProgress
                    variant="determinate"
                    value={resources.cpu.percent}
                    color={resources.cpu.healthy ? 'success' : 'error'}
                    sx={{ height: 8, borderRadius: 1 }}
                  />
                </Box>
              )}

              {/* Memory */}
              {resources.memory && (
                <Box sx={{ mb: 2 }}>
                  <MetricRow
                    label="Memory Usage"
                    value={resources.memory.percent_used}
                    unit="%"
                    healthy={resources.memory.healthy}
                  />
                  <LinearProgress
                    variant="determinate"
                    value={resources.memory.percent_used}
                    color={resources.memory.healthy ? 'success' : 'error'}
                    sx={{ height: 8, borderRadius: 1 }}
                  />
                </Box>
              )}

              {/* Disk */}
              {resources.disk && (
                <Box sx={{ mb: 2 }}>
                  <MetricRow
                    label="Disk Usage"
                    value={resources.disk.percent_used}
                    unit="%"
                    healthy={resources.disk.healthy}
                  />
                  <LinearProgress
                    variant="determinate"
                    value={resources.disk.percent_used}
                    color={resources.disk.healthy ? 'success' : 'error'}
                    sx={{ height: 8, borderRadius: 1 }}
                  />
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Circuit Breakers */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardHeader title="Circuit Breakers (Frontend)" />
            <CardContent>
              <Grid container spacing={2}>
                {Object.entries(circuitStates).map(([name, state]) => (
                  <Grid item xs={12} key={name}>
                    <CircuitBreakerCard name={name} state={state} />
                  </Grid>
                ))}
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        {/* Data Aggregator Status */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardHeader title="Data Aggregator" />
            <CardContent>
              <MetricRow
                label="Status"
                value={aggregatorStatus.isRunning ? 'Running' : 'Stopped'}
                unit=""
                healthy={aggregatorStatus.isRunning}
              />
              <MetricRow
                label="Poll Interval"
                value={aggregatorStatus.pollInterval / 1000}
                unit="s"
                healthy={true}
              />
              <MetricRow
                label="Consecutive Errors"
                value={aggregatorStatus.consecutiveErrors || 0}
                unit=""
                healthy={(aggregatorStatus.consecutiveErrors || 0) === 0}
              />

              {aggregatorStatus.isRunning ? (
                <Alert severity="success" sx={{ mt: 2 }}>
                  Data aggregator is actively polling backend
                </Alert>
              ) : (
                <Alert severity="error" sx={{ mt: 2 }}>
                  Data aggregator stopped (too many errors)
                </Alert>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Backend Circuit Breakers (if available) */}
        {health.circuit_breakers && Object.keys(health.circuit_breakers).length > 0 && (
          <Grid item xs={12}>
            <Card>
              <CardHeader title="Circuit Breakers (Backend)" />
              <CardContent>
                <Grid container spacing={2}>
                  {Object.entries(health.circuit_breakers).map(([name, state]) => (
                    <Grid item xs={12} sm={6} md={4} key={name}>
                      <CircuitBreakerCard name={name} state={state} />
                    </Grid>
                  ))}
                </Grid>
              </CardContent>
            </Card>
          </Grid>
        )}

        {/* Metrics Summary */}
        {metrics && metrics.summary && (
          <Grid item xs={12}>
            <Card>
              <CardHeader title="API Performance (24h)" />
              <CardContent>
                <Grid container spacing={2}>
                  {Object.entries(metrics.summary).map(([endpoint, stats]) => (
                    <Grid item xs={12} sm={6} md={4} key={endpoint}>
                      <Card variant="outlined">
                        <CardContent>
                          <Typography variant="caption" color="text.secondary" gutterBottom>
                            {endpoint}
                          </Typography>
                          <MetricRow label="Avg" value={stats.avg} unit="ms" />
                          <MetricRow label="Min" value={stats.min} unit="ms" />
                          <MetricRow label="Max" value={stats.max} unit="ms" />
                          <MetricRow label="Count" value={stats.count} unit="" />
                        </CardContent>
                      </Card>
                    </Grid>
                  ))}
                </Grid>
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>
    </Box>
  );
}

export default GuardianDashboard;
